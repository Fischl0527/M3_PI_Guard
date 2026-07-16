"""Build deterministic sampled human-review packets for E17.

The formal E17 packet contains every automatically flagged run.  This module
creates a separate, explicitly sampled human-audit packet without changing or
weakening the full E17 evidence bundle.  Two reviewers receive the same blinded
rows, while sampling strata and automated-disagreement membership remain in a
private manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from experiments.e17_review import EVIDENCE_FIELDS, REVIEW_FIELDS


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_E17_ROOT = REPO_ROOT / "outputs" / "experiments" / "E17"
DEFAULT_ITEMS = DEFAULT_E17_ROOT / "private" / "review_items.jsonl"
DEFAULT_TEMPLATE_1 = DEFAULT_E17_ROOT / "packets" / "reviewer_1_blinded_template.csv"
DEFAULT_TEMPLATE_2 = DEFAULT_E17_ROOT / "packets" / "reviewer_2_blinded_template.csv"
DEFAULT_AUTO_DISAGREEMENTS = (
    REPO_ROOT
    / "outputs"
    / "experiments"
    / "E17_auto_review_corrected_r3"
    / "automated_disagreements.csv"
)
DEFAULT_E17_MANIFEST = DEFAULT_E17_ROOT / "manifest.json"
DEFAULT_SOURCE_INDEX = REPO_ROOT / "outputs" / "experiments" / "e17_source_index_corrected_v2.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "experiments" / "E17_human_stratified_360_v1"
DEFAULT_SEED = 20260716
DEFAULT_REPRESENTATIVE_COUNT = 300
DEFAULT_DISAGREEMENT_COUNT = 40
DEFAULT_RARE_COUNT = 20

REVIEW_TEMPLATE_DIR = REPO_ROOT / "experiments" / "review_templates"
GUIDE_TEMPLATE = REVIEW_TEMPLATE_DIR / "e17_human_review_instructions.md"
PACKAGE_README_TEMPLATE = REVIEW_TEMPLATE_DIR / "e17_human_sample_package_readme.md"
PACKET_README_TEMPLATE = REVIEW_TEMPLATE_DIR / "e17_human_sample_packets_readme.md"
SUBMISSIONS_README_TEMPLATE = REVIEW_TEMPLATE_DIR / "e17_human_sample_submissions_readme.md"
PRIVATE_README_TEMPLATE = REVIEW_TEMPLATE_DIR / "e17_human_sample_private_readme.md"

SAMPLE_TEMPLATE_1 = "packets/reviewer_1_blinded_template.csv"
SAMPLE_TEMPLATE_2 = "packets/reviewer_2_blinded_template.csv"
SAMPLE_GUIDE = "REVIEW_INSTRUCTIONS.md"
SAMPLE_PACKAGE_README = "README.md"
SAMPLE_PACKET_README = "packets/README.md"
SAMPLE_SUBMISSIONS_README = "submissions/README.md"
SAMPLE_PRIVATE_README = "private/README.md"
SAMPLE_MANIFEST = "manifest.json"
SAMPLE_PACKET_MANIFEST = "packet_manifest.json"
SAMPLE_STRATA = "sampling_strata.csv"
SAMPLE_PRIVATE_ITEMS = "private/review_items_360.jsonl"

SCHEMA_VERSION = "e17-human-sample-v1"
SIGNATURE_FIELDS = tuple(field for field in EVIDENCE_FIELDS if field != "blind_id")
CORE_MODELS = {
    "qwen3:4b-instruct",
    "phi4-mini:3.8b",
    "llama3.2:3b",
    "gemma3:4b",
}
COMMON_GUARD_MODES = {"off", "keyword_only", "policy_only", "full_guard"}
SPECIAL_EXPERIMENT_PREFIXES = {
    "ablation",
    "derived",
    "formal",
    "mixed",
    "smoke",
    "validation_baseline",
    "E16",
}
RARE_BUCKETS = (
    "legacy_or_context_model",
    "rare_guard_mode",
    "special_experiment_stage",
    "multiple_failure_signals",
    "max_steps_signal",
)


class HumanSampleError(RuntimeError):
    """Raised when sampled human-review inputs fail their frozen contract."""


@dataclass(frozen=True)
class EvidenceCluster:
    signature: str
    items: tuple[dict[str, Any], ...]
    flag_combination: str
    auto_disagreement: bool

    @property
    def size(self) -> int:
        return len(self.items)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _record_path(path: Path) -> str:
    target = path.resolve()
    try:
        return target.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(target)


def _stable_hash(seed: int, *parts: str) -> str:
    value = "\x1f".join((str(seed), *parts))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _evidence_signature(row: Mapping[str, str]) -> str:
    payload = json.dumps(
        [str(row.get(field, "")) for field in SIGNATURE_FIELDS],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HumanSampleError(f"invalid JSONL at {path}:{line_number}") from exc
            if not isinstance(value, dict):
                raise HumanSampleError(f"expected JSON object at {path}:{line_number}")
            rows.append(value)
    if not rows:
        raise HumanSampleError(f"empty JSONL: {path}")
    return rows


def _load_review_template(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != tuple(REVIEW_FIELDS):
            raise HumanSampleError(f"invalid E17 review header: {path}")
        rows = [dict(row) for row in reader]
    ids = [row["blind_id"].strip() for row in rows]
    if not ids or len(ids) != len(set(ids)) or any(not value for value in ids):
        raise HumanSampleError(f"invalid blind_id coverage: {path}")
    return rows


def _load_disagreement_ids(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if "blind_id" not in (reader.fieldnames or ()):
            raise HumanSampleError(f"automated disagreement file lacks blind_id: {path}")
        ids = [str(row.get("blind_id", "")).strip() for row in reader]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise HumanSampleError(f"invalid automated disagreement IDs: {path}")
    return set(ids)


def _largest_remainder(
    weights: Mapping[str, int],
    total: int,
    *,
    minimum_one: bool = True,
) -> dict[str, int]:
    positive = {key: int(value) for key, value in weights.items() if int(value) > 0}
    if total < 0 or total > sum(positive.values()):
        raise HumanSampleError(f"invalid allocation total {total} for {positive}")
    if not positive:
        if total:
            raise HumanSampleError("cannot allocate from empty strata")
        return {}
    if minimum_one and total < len(positive):
        minimum_one = False
    denominator = sum(positive.values())
    raw = {key: total * value / denominator for key, value in positive.items()}
    allocation = {
        key: max(1 if minimum_one else 0, math.floor(raw[key]))
        for key in positive
    }
    while sum(allocation.values()) < total:
        candidates = [key for key in positive if allocation[key] < positive[key]]
        if not candidates:
            raise HumanSampleError("allocation exhausted before reaching target")
        key = max(
            candidates,
            key=lambda value: (
                raw[value] - allocation[value],
                positive[value],
                value,
            ),
        )
        allocation[key] += 1
    while sum(allocation.values()) > total:
        floor = 1 if minimum_one else 0
        candidates = [key for key in positive if allocation[key] > floor]
        if not candidates:
            raise HumanSampleError("allocation minimums exceed target")
        key = min(
            candidates,
            key=lambda value: (
                raw[value] - allocation[value],
                -positive[value],
                value,
            ),
        )
        allocation[key] -= 1
    return dict(sorted(allocation.items()))


def _uniform_select(
    clusters: Sequence[EvidenceCluster],
    count: int,
    *,
    seed: int,
    label: str,
) -> list[EvidenceCluster]:
    if count > len(clusters):
        raise HumanSampleError(
            f"sample {label!r} requests {count} unique clusters from {len(clusters)}"
        )
    return sorted(
        clusters,
        key=lambda cluster: _stable_hash(seed, label, cluster.signature),
    )[:count]


def _representative_member(cluster: EvidenceCluster, *, seed: int, label: str) -> dict[str, Any]:
    return min(
        cluster.items,
        key=lambda item: _stable_hash(seed, label, str(item["blind_id"])),
    )


def _item_rare_reasons(item: Mapping[str, Any], flag_combination: str) -> list[str]:
    flags = flag_combination.split("|") if flag_combination else []
    model = str(item.get("model", ""))
    guard_mode = str(item.get("guard_mode", ""))
    prefix = str(item.get("experiment_id", "")).split("__", 1)[0]
    reasons: list[str] = []
    if len(flags) > 1:
        reasons.append("multiple_failure_signals")
    if "max_steps" in flags:
        reasons.append("max_steps_signal")
    if model and model not in CORE_MODELS:
        reasons.append("legacy_or_context_model")
    if guard_mode and guard_mode not in COMMON_GUARD_MODES:
        reasons.append("rare_guard_mode")
    if prefix in SPECIAL_EXPERIMENT_PREFIXES:
        reasons.append("special_experiment_stage")
    return reasons


def _rare_reasons(cluster: EvidenceCluster) -> list[str]:
    reasons = {
        reason
        for item in cluster.items
        for reason in _item_rare_reasons(item, cluster.flag_combination)
    }
    return [reason for reason in RARE_BUCKETS if reason in reasons]


def _rare_score(cluster: EvidenceCluster) -> int:
    weights = {
        "multiple_failure_signals": 5,
        "max_steps_signal": 4,
        "legacy_or_context_model": 3,
        "rare_guard_mode": 2,
        "special_experiment_stage": 1,
    }
    return sum(weights[reason] for reason in _rare_reasons(cluster))


def _atomic_write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(REVIEW_FIELDS))
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_write_table(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    fields: Sequence[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields))
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _atomic_write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    value = "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    _atomic_write_text(path, value)


def _cluster_items(
    items: Sequence[Mapping[str, Any]],
    template_rows: Mapping[str, Mapping[str, str]],
    disagreement_ids: set[str],
) -> list[EvidenceCluster]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_ids: set[str] = set()
    for source_item in items:
        item = dict(source_item)
        blind_id = str(item.get("blind_id", "")).strip()
        evidence = item.get("evidence")
        if not blind_id or blind_id in seen_ids or not isinstance(evidence, Mapping):
            raise HumanSampleError(f"invalid private E17 item: {blind_id!r}")
        seen_ids.add(blind_id)
        template = template_rows.get(blind_id)
        if template is None:
            raise HumanSampleError(f"private item missing from blinded template: {blind_id}")
        for field in EVIDENCE_FIELDS:
            if str(template.get(field, "")) != str(evidence.get(field, "")):
                raise HumanSampleError(f"private/template evidence drift for {blind_id}:{field}")
        grouped[_evidence_signature(template)].append(item)
    if set(template_rows) != seen_ids:
        raise HumanSampleError("private items and full blinded template have different blind IDs")

    clusters: list[EvidenceCluster] = []
    for signature, members in grouped.items():
        flag_combinations = {
            "|".join(str(value) for value in item.get("automatic_flags", []))
            for item in members
        }
        disagreement_states = {
            str(item["blind_id"]) in disagreement_ids for item in members
        }
        if len(flag_combinations) != 1:
            raise HumanSampleError(f"evidence cluster crosses flag strata: {signature}")
        if len(disagreement_states) != 1:
            raise HumanSampleError(f"evidence cluster crosses auto-review states: {signature}")
        clusters.append(
            EvidenceCluster(
                signature=signature,
                items=tuple(sorted(members, key=lambda item: str(item["blind_id"]))),
                flag_combination=next(iter(flag_combinations)),
                auto_disagreement=next(iter(disagreement_states)),
            )
        )
    return sorted(clusters, key=lambda cluster: cluster.signature)


def _render_review_template(path: Path, replacements: Mapping[str, Any]) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    rendered = path.read_text(encoding="utf-8")
    for name, value in replacements.items():
        rendered = rendered.replace(f"__{name.upper()}__", str(value))
    unresolved = sorted(set(part.split("__", 1)[0] for part in rendered.split("__")[1::2]))
    if unresolved:
        raise HumanSampleError(f"unresolved review-template placeholders in {path}: {unresolved}")
    return rendered.rstrip() + "\n"


def _build_guide(*, total: int, seed: int) -> str:
    return _render_review_template(
        GUIDE_TEMPLATE,
        {"total": total, "seed": seed},
    )


def _build_package_readme(
    *,
    total: int,
    seed: int,
    population: int,
    representative_count: int,
    disagreement_count: int,
    rare_count: int,
) -> str:
    return _render_review_template(
        PACKAGE_README_TEMPLATE,
        {
            "total": total,
            "seed": seed,
            "population": population,
            "representative_count": representative_count,
            "disagreement_count": disagreement_count,
            "rare_count": rare_count,
        },
    )


def _build_packet_readme(*, total: int) -> str:
    return _render_review_template(PACKET_README_TEMPLATE, {"total": total})


def _build_submissions_readme(*, total: int) -> str:
    return _render_review_template(SUBMISSIONS_README_TEMPLATE, {"total": total})


def _build_private_readme(*, total: int) -> str:
    return _render_review_template(PRIVATE_README_TEMPLATE, {"total": total})


def build_sample(
    *,
    items_path: Path = DEFAULT_ITEMS,
    template_1_path: Path = DEFAULT_TEMPLATE_1,
    template_2_path: Path = DEFAULT_TEMPLATE_2,
    disagreements_path: Path = DEFAULT_AUTO_DISAGREEMENTS,
    e17_manifest_path: Path = DEFAULT_E17_MANIFEST,
    source_index_path: Path = DEFAULT_SOURCE_INDEX,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    seed: int = DEFAULT_SEED,
    representative_count: int = DEFAULT_REPRESENTATIVE_COUNT,
    disagreement_count: int = DEFAULT_DISAGREEMENT_COUNT,
    rare_count: int = DEFAULT_RARE_COUNT,
) -> dict[str, Any]:
    items_path = items_path.resolve()
    template_1_path = template_1_path.resolve()
    template_2_path = template_2_path.resolve()
    disagreements_path = disagreements_path.resolve()
    e17_manifest_path = e17_manifest_path.resolve()
    source_index_path = source_index_path.resolve()
    output_dir = output_dir.resolve()
    for path in (
        items_path,
        template_1_path,
        template_2_path,
        disagreements_path,
        e17_manifest_path,
        source_index_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    items = _load_jsonl(items_path)
    template_1 = _load_review_template(template_1_path)
    template_2 = _load_review_template(template_2_path)
    if template_1 != template_2:
        raise HumanSampleError("the two full blinded templates are not cell-identical")
    template_by_id = {row["blind_id"]: row for row in template_1}
    disagreement_ids = _load_disagreement_ids(disagreements_path)
    if not disagreement_ids <= set(template_by_id):
        raise HumanSampleError("automated disagreement IDs escaped the E17 packet")
    clusters = _cluster_items(items, template_by_id, disagreement_ids)

    row_weights = Counter()
    cluster_counts = Counter()
    clusters_by_flag: dict[str, list[EvidenceCluster]] = defaultdict(list)
    for cluster in clusters:
        row_weights[cluster.flag_combination] += cluster.size
        cluster_counts[cluster.flag_combination] += 1
        clusters_by_flag[cluster.flag_combination].append(cluster)
    representative_allocation = _largest_remainder(
        row_weights, representative_count, minimum_one=True
    )
    selected: dict[str, tuple[EvidenceCluster, str]] = {}
    for flag, count in representative_allocation.items():
        chosen = _uniform_select(
            clusters_by_flag[flag], count, seed=seed, label=f"representative:{flag}"
        )
        for cluster in chosen:
            selected[cluster.signature] = (cluster, "representative")

    remaining_disagreements = [
        cluster
        for cluster in clusters
        if cluster.auto_disagreement and cluster.signature not in selected
    ]
    disagreement_weights = Counter(cluster.flag_combination for cluster in remaining_disagreements)
    disagreement_allocation = _largest_remainder(
        disagreement_weights, disagreement_count, minimum_one=True
    )
    by_disagreement_flag: dict[str, list[EvidenceCluster]] = defaultdict(list)
    for cluster in remaining_disagreements:
        by_disagreement_flag[cluster.flag_combination].append(cluster)
    for flag, count in disagreement_allocation.items():
        chosen = _uniform_select(
            by_disagreement_flag[flag],
            count,
            seed=seed,
            label=f"targeted_auto_disagreement:{flag}",
        )
        for cluster in chosen:
            selected[cluster.signature] = (cluster, "targeted_auto_disagreement")

    rare_candidates = [
        cluster
        for cluster in clusters
        if cluster.signature not in selected and _rare_score(cluster) > 0
    ]
    rare_candidates.sort(
        key=lambda cluster: (
            -_rare_score(cluster),
            _stable_hash(seed, "targeted_rare_complex", cluster.signature),
        )
    )
    if len(rare_candidates) < rare_count:
        raise HumanSampleError(
            f"rare sample requests {rare_count} clusters from {len(rare_candidates)}"
        )
    rare_selected: list[EvidenceCluster] = []
    rare_selected_ids: set[str] = set()
    bucket_base, bucket_remainder = divmod(rare_count, len(RARE_BUCKETS))
    bucket_allocation = {
        bucket: bucket_base + (1 if position < bucket_remainder else 0)
        for position, bucket in enumerate(RARE_BUCKETS)
    }
    for bucket in RARE_BUCKETS:
        candidates = [
            cluster
            for cluster in rare_candidates
            if cluster.signature not in rare_selected_ids and bucket in _rare_reasons(cluster)
        ]
        candidates.sort(
            key=lambda cluster: (
                -_rare_score(cluster),
                _stable_hash(seed, f"targeted_rare_complex:{bucket}", cluster.signature),
            )
        )
        for cluster in candidates[: bucket_allocation[bucket]]:
            rare_selected.append(cluster)
            rare_selected_ids.add(cluster.signature)
    if len(rare_selected) < rare_count:
        for cluster in rare_candidates:
            if cluster.signature in rare_selected_ids:
                continue
            rare_selected.append(cluster)
            rare_selected_ids.add(cluster.signature)
            if len(rare_selected) == rare_count:
                break
    for cluster in rare_selected:
        selected[cluster.signature] = (cluster, "targeted_rare_complex")

    expected_total = representative_count + disagreement_count + rare_count
    if len(selected) != expected_total:
        raise HumanSampleError(f"expected {expected_total} unique clusters, got {len(selected)}")

    records: list[dict[str, Any]] = []
    review_rows: list[dict[str, str]] = []
    for signature, (cluster, group) in selected.items():
        if group == "targeted_rare_complex":
            member = min(
                cluster.items,
                key=lambda item: (
                    -sum(
                        1
                        for reason in _item_rare_reasons(item, cluster.flag_combination)
                        if reason in _rare_reasons(cluster)
                    ),
                    _stable_hash(seed, "member:targeted_rare_complex", str(item["blind_id"])),
                ),
            )
        else:
            member = _representative_member(cluster, seed=seed, label=f"member:{group}")
        blind_id = str(member["blind_id"])
        template_row = dict(template_by_id[blind_id])
        for field in REVIEW_FIELDS[len(EVIDENCE_FIELDS) :]:
            template_row[field] = ""
        review_rows.append(template_row)
        inclusion_probability = None
        analysis_weight = None
        if group == "representative":
            sampled_clusters = representative_allocation[cluster.flag_combination]
            total_clusters = cluster_counts[cluster.flag_combination]
            inclusion_probability = sampled_clusters / total_clusters
            analysis_weight = cluster.size / inclusion_probability
        records.append(
            {
                "blind_id": blind_id,
                "evidence_signature": signature,
                "sample_group": group,
                "flag_combination": cluster.flag_combination,
                "cluster_size": cluster.size,
                "covered_blind_ids": [str(item["blind_id"]) for item in cluster.items],
                "auto_disagreement": cluster.auto_disagreement,
                "rare_reasons": _rare_reasons(cluster),
                "representative_inclusion_probability": inclusion_probability,
                "representative_analysis_weight": analysis_weight,
                "case_id": member.get("case_id", ""),
                "sample_type": member.get("sample_type", ""),
                "attack_family": member.get("attack_family", ""),
                "language": member.get("language", ""),
                "model": member.get("model", ""),
                "guard_mode": member.get("guard_mode", ""),
                "prompt_profile": member.get("prompt_profile", ""),
                "experiment_id": member.get("experiment_id", ""),
            }
        )

    order = {
        row["blind_id"]: _stable_hash(seed, "final_blind_order", row["blind_id"])
        for row in review_rows
    }
    review_rows.sort(key=lambda row: order[row["blind_id"]])
    records.sort(key=lambda row: order[row["blind_id"]])

    template_out_1 = output_dir / SAMPLE_TEMPLATE_1
    template_out_2 = output_dir / SAMPLE_TEMPLATE_2
    guide_path = output_dir / SAMPLE_GUIDE
    package_readme_path = output_dir / SAMPLE_PACKAGE_README
    packet_readme_path = output_dir / SAMPLE_PACKET_README
    submissions_readme_path = output_dir / SAMPLE_SUBMISSIONS_README
    private_readme_path = output_dir / SAMPLE_PRIVATE_README
    manifest_path = output_dir / SAMPLE_MANIFEST
    packet_manifest_path = output_dir / SAMPLE_PACKET_MANIFEST
    strata_path = output_dir / SAMPLE_STRATA
    private_items_path = output_dir / SAMPLE_PRIVATE_ITEMS
    _atomic_write_csv(template_out_1, review_rows)
    _atomic_write_csv(template_out_2, review_rows)
    if template_out_1.read_bytes() != template_out_2.read_bytes():
        raise HumanSampleError("sampled reviewer packets are not byte-identical")
    _atomic_write_text(guide_path, _build_guide(total=expected_total, seed=seed))
    _atomic_write_text(packet_readme_path, _build_packet_readme(total=expected_total))
    _atomic_write_text(
        submissions_readme_path,
        _build_submissions_readme(total=expected_total),
    )
    _atomic_write_text(private_readme_path, _build_private_readme(total=expected_total))
    _atomic_write_jsonl(private_items_path, records)

    group_counts = Counter(record["sample_group"] for record in records)
    _atomic_write_text(
        package_readme_path,
        _build_package_readme(
            total=expected_total,
            seed=seed,
            population=len(items),
            representative_count=group_counts["representative"],
            disagreement_count=group_counts["targeted_auto_disagreement"],
            rare_count=group_counts["targeted_rare_complex"],
        ),
    )
    group_flag_counts = {
        group: dict(
            sorted(
                Counter(
                    record["flag_combination"]
                    for record in records
                    if record["sample_group"] == group
                ).items()
            )
        )
        for group in sorted(group_counts)
    }
    representative_sample_counts = Counter(
        record["flag_combination"]
        for record in records
        if record["sample_group"] == "representative"
    )
    disagreement_population_rows = Counter()
    disagreement_population_clusters = Counter()
    for cluster in remaining_disagreements:
        disagreement_population_rows[cluster.flag_combination] += cluster.size
        disagreement_population_clusters[cluster.flag_combination] += 1
    rare_population_rows = Counter()
    rare_population_clusters = Counter()
    for cluster in rare_candidates:
        rare_population_rows[cluster.flag_combination] += cluster.size
        rare_population_clusters[cluster.flag_combination] += 1

    strata_rows: list[dict[str, Any]] = []
    for flag in sorted(representative_allocation):
        sample_n = representative_sample_counts[flag]
        probability = sample_n / cluster_counts[flag]
        strata_rows.append(
            {
                "sample_group": "representative",
                "flag_combination": flag,
                "eligible_population_rows": row_weights[flag],
                "eligible_population_clusters": cluster_counts[flag],
                "sample_clusters": sample_n,
                "cluster_inclusion_probability": probability,
                "analysis_weight_rule": "cluster_size / cluster_inclusion_probability",
                "population_estimate_eligible": "true",
            }
        )
    for flag in sorted(disagreement_allocation):
        sample_n = disagreement_allocation[flag]
        probability = sample_n / disagreement_population_clusters[flag]
        strata_rows.append(
            {
                "sample_group": "targeted_auto_disagreement",
                "flag_combination": flag,
                "eligible_population_rows": disagreement_population_rows[flag],
                "eligible_population_clusters": disagreement_population_clusters[flag],
                "sample_clusters": sample_n,
                "cluster_inclusion_probability": probability,
                "analysis_weight_rule": "not_applicable_diagnostic_only",
                "population_estimate_eligible": "false",
            }
        )
    rare_sample_counts = Counter(
        record["flag_combination"]
        for record in records
        if record["sample_group"] == "targeted_rare_complex"
    )
    for flag in sorted(rare_sample_counts):
        strata_rows.append(
            {
                "sample_group": "targeted_rare_complex",
                "flag_combination": flag,
                "eligible_population_rows": rare_population_rows[flag],
                "eligible_population_clusters": rare_population_clusters[flag],
                "sample_clusters": rare_sample_counts[flag],
                "cluster_inclusion_probability": "",
                "analysis_weight_rule": "not_applicable_diagnostic_only",
                "population_estimate_eligible": "false",
            }
        )
    _atomic_write_table(
        strata_path,
        strata_rows,
        (
            "sample_group",
            "flag_combination",
            "eligible_population_rows",
            "eligible_population_clusters",
            "sample_clusters",
            "cluster_inclusion_probability",
            "analysis_weight_rule",
            "population_estimate_eligible",
        ),
    )

    formula_prefixes = ("=", "+", "-", "@")
    formula_cells = [
        (row["blind_id"], field)
        for row in review_rows
        for field in EVIDENCE_FIELDS
        if str(row.get(field, "")).lstrip().startswith(formula_prefixes)
    ]
    if formula_cells:
        raise HumanSampleError(f"CSV formula-like evidence cells detected: {formula_cells[:5]}")
    review_fields = REVIEW_FIELDS[len(EVIDENCE_FIELDS) :]
    if any(str(row.get(field, "")) for row in review_rows for field in review_fields):
        raise HumanSampleError("sampled packet contains pre-filled human review fields")
    blind_ids_in_order = [row["blind_id"] for row in review_rows]
    packet_manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "row_count": len(review_rows),
        "unique_blind_id_count": len(set(blind_ids_in_order)),
        "blind_id_set_sha256": _json_hash(sorted(blind_ids_in_order)),
        "blind_id_order_sha256": _json_hash(blind_ids_in_order),
        "canonical_evidence_sha256": _json_hash(
            [[row[field] for field in EVIDENCE_FIELDS] for row in review_rows]
        ),
        "review_fields_all_blank": True,
        "formula_like_evidence_cells": 0,
        "reviewer_packets_byte_identical": True,
        "reviewer_1_template": {
            "path": _record_path(template_out_1),
            "bytes": template_out_1.stat().st_size,
            "sha256": _sha256(template_out_1),
        },
        "reviewer_2_template": {
            "path": _record_path(template_out_2),
            "bytes": template_out_2.stat().st_size,
            "sha256": _sha256(template_out_2),
        },
    }
    _atomic_write_json(packet_manifest_path, packet_manifest)

    public_summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "protocol_id": "E17_HUMAN_STRATIFIED_360_V1",
        "status": "ready_for_two_independent_human_reviewers",
        "seed": seed,
        "population_rows": len(items),
        "unique_evidence_clusters": len(clusters),
        "duplicate_row_excess": len(items) - len(clusters),
        "sample_rows_per_reviewer": expected_total,
        "reviewers_required": 2,
        "same_items_required_for_both_reviewers": True,
        "sample_group_counts": dict(sorted(group_counts.items())),
        "sample_group_flag_counts": group_flag_counts,
        "representative_allocation": representative_allocation,
        "targeted_auto_disagreement_allocation": disagreement_allocation,
        "inputs": {
            "parent_e17_manifest": {
                "path": _record_path(e17_manifest_path),
                "sha256": _sha256(e17_manifest_path),
            },
            "corrected_source_index": {
                "path": _record_path(source_index_path),
                "sha256": _sha256(source_index_path),
            },
            "private_items": {"path": _record_path(items_path), "sha256": _sha256(items_path)},
            "full_template_1": {
                "path": _record_path(template_1_path),
                "sha256": _sha256(template_1_path),
            },
            "full_template_2": {
                "path": _record_path(template_2_path),
                "sha256": _sha256(template_2_path),
            },
            "automated_disagreements": {
                "path": _record_path(disagreements_path),
                "sha256": _sha256(disagreements_path),
                "rows": len(disagreement_ids),
            },
        },
        "outputs": {
            "package_readme": {
                "path": _record_path(package_readme_path),
                "sha256": _sha256(package_readme_path),
            },
            "reviewer_1_template": {
                "path": _record_path(template_out_1),
                "sha256": _sha256(template_out_1),
            },
            "reviewer_2_template": {
                "path": _record_path(template_out_2),
                "sha256": _sha256(template_out_2),
            },
            "guide": {"path": _record_path(guide_path), "sha256": _sha256(guide_path)},
            "packet_readme": {
                "path": _record_path(packet_readme_path),
                "sha256": _sha256(packet_readme_path),
            },
            "submissions_readme": {
                "path": _record_path(submissions_readme_path),
                "sha256": _sha256(submissions_readme_path),
            },
            "private_readme": {
                "path": _record_path(private_readme_path),
                "sha256": _sha256(private_readme_path),
            },
            "packet_manifest": {
                "path": _record_path(packet_manifest_path),
                "sha256": _sha256(packet_manifest_path),
            },
            "sampling_strata": {
                "path": _record_path(strata_path),
                "sha256": _sha256(strata_path),
            },
            "private_sample_items": {
                "path": _record_path(private_items_path),
                "sha256": _sha256(private_items_path),
            },
        },
        "analysis_contract": {
            "representative_group": "may estimate the flagged-run population using the private design weights",
            "targeted_groups": "diagnostic stress audit only; do not pool raw proportions into population estimates",
            "human_coverage_claim": f"two independent humans reviewed a shared stratified sample of {expected_total} items",
            "prohibited_claim": f"all {len(items)} E17 items received human review",
        },
        "registry_effect": "none_until_sampled_human_review_and_separate_validation_are_complete",
    }
    _atomic_write_json(manifest_path, public_summary)
    return public_summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=Path, default=DEFAULT_ITEMS)
    parser.add_argument("--template-1", type=Path, default=DEFAULT_TEMPLATE_1)
    parser.add_argument("--template-2", type=Path, default=DEFAULT_TEMPLATE_2)
    parser.add_argument("--auto-disagreements", type=Path, default=DEFAULT_AUTO_DISAGREEMENTS)
    parser.add_argument("--e17-manifest", type=Path, default=DEFAULT_E17_MANIFEST)
    parser.add_argument("--source-index", type=Path, default=DEFAULT_SOURCE_INDEX)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--representative", type=int, default=DEFAULT_REPRESENTATIVE_COUNT)
    parser.add_argument("--targeted-disagreements", type=int, default=DEFAULT_DISAGREEMENT_COUNT)
    parser.add_argument("--targeted-rare", type=int, default=DEFAULT_RARE_COUNT)
    args = parser.parse_args(argv)
    result = build_sample(
        items_path=args.items,
        template_1_path=args.template_1,
        template_2_path=args.template_2,
        disagreements_path=args.auto_disagreements,
        e17_manifest_path=args.e17_manifest,
        source_index_path=args.source_index,
        output_dir=args.out_dir,
        seed=args.seed,
        representative_count=args.representative,
        disagreement_count=args.targeted_disagreements,
        rare_count=args.targeted_rare,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
