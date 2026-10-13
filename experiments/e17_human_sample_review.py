"""定稿并冻结 E17 双人独立审查的分层人类审计样本集。

汇总两位安全专家各自独立的判定结果，计算 Cohen's Kappa 一致性系数并解决冲突。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import random
import subprocess
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from experiments import e17_review
from m3_eval.figure_manifest import write_figure_manifest
from m3_eval.statistics import percentile, proportion_result


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_DIR = REPO_ROOT / "outputs" / "experiments" / "E17_human_stratified_360_v1"
DEFAULT_REVIEWER_1 = DEFAULT_PACKAGE_DIR / "submissions" / "reviewer_1_completed.csv"
DEFAULT_REVIEWER_2 = DEFAULT_PACKAGE_DIR / "submissions" / "reviewer_2_completed.csv"
DEFAULT_OUTPUT_DIR = DEFAULT_PACKAGE_DIR / "review"

SOURCE_MODE = "human_stratified_sample"
EVIDENCE_TIER = "human_stratified_sample"
PROTOCOL_ID = "E17_HUMAN_STRATIFIED_360_V1"
SCHEMA_VERSION = "e17-human-sample-review-v1"
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 20260717
REPRESENTATIVE_GROUP = "representative"
TARGETED_GROUPS = ("targeted_auto_disagreement", "targeted_rare_complex")
PROHIBITED_CLAIM = "all 3299 E17 items received human review"


class HumanSampleReviewError(RuntimeError):
    """当抽样的人工复核论据未通过准入检查时抛出。"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    target = path.resolve()
    try:
        return target.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(target)


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HumanSampleReviewError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HumanSampleReviewError(f"{label} must be a JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HumanSampleReviewError(f"invalid JSONL at {path}:{line_number}") from exc
            if not isinstance(value, dict):
                raise HumanSampleReviewError(f"expected an object at {path}:{line_number}")
            rows.append(value)
    if not rows:
        raise HumanSampleReviewError(f"empty JSONL: {path}")
    return rows


def _load_template_items(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != tuple(e17_review.REVIEW_FIELDS):
            raise HumanSampleReviewError(f"invalid frozen review template header: {path}")
        rows = list(reader)
    ids = [str(row.get("blind_id", "")).strip() for row in rows]
    if not ids or len(ids) != len(set(ids)) or any(not value for value in ids):
        raise HumanSampleReviewError("frozen review template has invalid blind IDs")
    for row in rows:
        if any(str(row.get(field, "")) for field in e17_review.REVIEW_FIELDS[len(e17_review.EVIDENCE_FIELDS) :]):
            raise HumanSampleReviewError("frozen review template contains nonblank review fields")
    return [
        {
            "blind_id": row["blind_id"],
            "evidence": {field: row.get(field, "") for field in e17_review.EVIDENCE_FIELDS},
        }
        for row in rows
    ]


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )


def _atomic_write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True
        )
        return completed.stdout.strip()

    try:
        commit = run("rev-parse", "HEAD")
        branch = run("branch", "--show-current")
        dirty = bool(run("status", "--porcelain"))
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HumanSampleReviewError(f"cannot capture Git state: {exc}") from exc
    return {"commit": commit, "branch": branch, "dirty": dirty}


def _validate_frozen_package(package_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    manifest_path = package_dir / "manifest.json"
    packet_manifest_path = package_dir / "packet_manifest.json"
    private_items_path = package_dir / "private" / "review_items_360.jsonl"
    template_1 = package_dir / "packets" / "reviewer_1_blinded_template.csv"
    template_2 = package_dir / "packets" / "reviewer_2_blinded_template.csv"
    for path in (manifest_path, packet_manifest_path, private_items_path, template_1, template_2):
        if not path.is_file() or path.stat().st_size <= 0:
            raise HumanSampleReviewError(f"frozen sample input is missing or empty: {path}")
    package_manifest = _load_object(manifest_path, label="sample manifest")
    packet_manifest = _load_object(packet_manifest_path, label="packet manifest")
    if package_manifest.get("protocol_id") != PROTOCOL_ID:
        raise HumanSampleReviewError("unexpected sample protocol")
    if int(package_manifest.get("sample_rows_per_reviewer", -1)) != 360:
        raise HumanSampleReviewError("sample manifest does not declare 360 rows per reviewer")
    if int(package_manifest.get("population_rows", -1)) != 3299:
        raise HumanSampleReviewError("sample manifest population is not 3299")
    if dict(package_manifest.get("sample_group_counts") or {}) != {
        REPRESENTATIVE_GROUP: 300,
        TARGETED_GROUPS[0]: 40,
        TARGETED_GROUPS[1]: 20,
    }:
        raise HumanSampleReviewError("sample group contract drifted")
    if _sha256(template_1) != _sha256(template_2) or template_1.read_bytes() != template_2.read_bytes():
        raise HumanSampleReviewError("the two frozen reviewer templates are not byte-identical")
    if packet_manifest.get("reviewer_packets_byte_identical") is not True:
        raise HumanSampleReviewError("packet manifest does not attest identical reviewer packets")
    expected_template_hash = str(packet_manifest.get("reviewer_1_template", {}).get("sha256", ""))
    if expected_template_hash != _sha256(template_1):
        raise HumanSampleReviewError("frozen packet hash drifted")
    items = _load_template_items(template_1)
    metadata = _load_jsonl(private_items_path)
    metadata_by_id = {str(row.get("blind_id", "")): row for row in metadata}
    item_ids = {str(row["blind_id"]) for row in items}
    if len(metadata_by_id) != 360 or set(metadata_by_id) != item_ids:
        raise HumanSampleReviewError("private sampling metadata does not match frozen packets")
    counts = Counter(str(row.get("sample_group", "")) for row in metadata)
    if dict(counts) != dict(package_manifest["sample_group_counts"]):
        raise HumanSampleReviewError("private sample group counts drifted")
    return package_manifest, items, metadata


def _count_rows(codes: Sequence[str]) -> list[dict[str, Any]]:
    counts = Counter(codes)
    total = len(codes)
    rows: list[dict[str, Any]] = []
    for code in e17_review.PRIMARY_CODES:
        result = proportion_result(counts[code], total)
        rows.append(
            {
                "failure_class": code,
                "count": counts[code],
                "total": total,
                "percent": None if result["value"] is None else 100.0 * result["value"],
                "ci_low_percent": None if result["ci_low"] is None else 100.0 * result["ci_low"],
                "ci_high_percent": None if result["ci_high"] is None else 100.0 * result["ci_high"],
                "interval_method": "Wilson score interval",
            }
        )
    return rows


def _weighted_estimates(
    rows: Sequence[Mapping[str, Any]],
    *,
    iterations: int,
    seed: int,
) -> list[dict[str, Any]]:
    strata: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("sample_group") != REPRESENTATIVE_GROUP:
            continue
        weight = row.get("analysis_weight")
        if weight is None or float(weight) <= 0:
            raise HumanSampleReviewError(f"representative row lacks a positive weight: {row.get('blind_id')}")
        strata[str(row.get("flag_combination", ""))].append(row)
    if sum(len(values) for values in strata.values()) != 300:
        raise HumanSampleReviewError("weighted estimation requires exactly 300 representative rows")

    def shares(sampled: Iterable[Mapping[str, Any]]) -> dict[str, float]:
        weighted = Counter()
        denominator = 0.0
        for row in sampled:
            weight = float(row["analysis_weight"])
            denominator += weight
            weighted[str(row["final_primary_code"])] += weight
        if denominator <= 0:
            raise HumanSampleReviewError("weighted denominator is not positive")
        return {code: weighted[code] / denominator for code in e17_review.PRIMARY_CODES}

    source_rows = [row for values in strata.values() for row in values]
    point = shares(source_rows)
    rng = random.Random(seed)
    distributions = {code: [] for code in e17_review.PRIMARY_CODES}
    for _ in range(iterations):
        sampled: list[Mapping[str, Any]] = []
        for stratum in sorted(strata):
            values = strata[stratum]
            sampled.extend(rng.choice(values) for _ in range(len(values)))
        estimate = shares(sampled)
        for code in e17_review.PRIMARY_CODES:
            distributions[code].append(estimate[code])
    total_weight = sum(float(row["analysis_weight"]) for row in source_rows)
    return [
        {
            "failure_class": code,
            "representative_sample_n": len(source_rows),
            "weighted_denominator": total_weight,
            "weighted_share": point[code],
            "weighted_percent": 100.0 * point[code],
            "ci_low": percentile(distributions[code], 0.025),
            "ci_high": percentile(distributions[code], 0.975),
            "ci_low_percent": 100.0 * float(percentile(distributions[code], 0.025) or 0.0),
            "ci_high_percent": 100.0 * float(percentile(distributions[code], 0.975) or 0.0),
            "interval_method": "stratified_design_weighted_percentile_bootstrap",
            "bootstrap_iterations": iterations,
            "bootstrap_seed": seed,
        }
        for code in e17_review.PRIMARY_CODES
    ]


def _render_figures(
    output_dir: Path,
    raw_counts: Sequence[Mapping[str, Any]],
    weighted: Sequence[Mapping[str, Any]],
    group_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {
        "leak": "#C84B31",
        "false_block": "#D98E2F",
        "ask": "#7562B8",
        "parse_failure": "#4B7BB5",
        "timeout": "#74808A",
        "max_steps": "#2A9D8F",
        "other": "#A5678E",
        "none": "#7A9E52",
    }

    count_png = output_dir / "representative_failure_counts.png"
    count_svg = output_dir / "representative_failure_counts.svg"
    ordered = sorted(raw_counts, key=lambda row: (-int(row["count"]), str(row["failure_class"])))
    labels = [str(row["failure_class"]).replace("_", " ") for row in ordered]
    values = [float(row["percent"] or 0.0) for row in ordered]
    lows = [float(row["ci_low_percent"] or 0.0) for row in ordered]
    highs = [float(row["ci_high_percent"] or 0.0) for row in ordered]
    fig, axis = plt.subplots(figsize=(9.6, 6.1), dpi=160)
    fig.patch.set_facecolor("#FAFBFC")
    axis.set_facecolor("#FAFBFC")
    positions = list(range(len(ordered)))
    bars = axis.barh(
        positions,
        values,
        xerr=[
            [max(0.0, value - low) for value, low in zip(values, lows)],
            [max(0.0, high - value) for value, high in zip(values, highs)],
        ],
        color=[colors[str(row["failure_class"])] for row in ordered],
        edgecolor="#263642",
        linewidth=0.5,
        error_kw={"ecolor": "#263642", "capsize": 3, "elinewidth": 1.0},
    )
    for bar, row, value, high in zip(bars, ordered, values, highs):
        axis.text(max(value, high) + 0.8, bar.get_y() + bar.get_height() / 2, f"{row['count']}/300", va="center", fontsize=8.5)
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlim(0, max(45.0, max(highs) + 10.0))
    axis.set_xlabel("Share of 300 representative audited items (%)")
    axis.set_title("E17 representative sample: human-coded primary classes", loc="left", fontweight="bold")
    axis.grid(axis="x", alpha=0.25)
    axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(count_png, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(count_svg, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    weighted_png = output_dir / "weighted_population_estimates.png"
    weighted_svg = output_dir / "weighted_population_estimates.svg"
    weighted_order = sorted(weighted, key=lambda row: (-float(row["weighted_percent"]), str(row["failure_class"])))
    values = [float(row["weighted_percent"]) for row in weighted_order]
    lows = [float(row["ci_low_percent"]) for row in weighted_order]
    highs = [float(row["ci_high_percent"]) for row in weighted_order]
    positions = list(range(len(weighted_order)))
    fig, axis = plt.subplots(figsize=(9.6, 6.1), dpi=160)
    fig.patch.set_facecolor("#FAFBFC")
    axis.set_facecolor("#FAFBFC")
    axis.errorbar(
        values,
        positions,
        xerr=[
            [max(0.0, value - low) for value, low in zip(values, lows)],
            [max(0.0, high - value) for value, high in zip(values, highs)],
        ],
        fmt="o",
        color="#315C8A",
        ecolor="#71879B",
        capsize=4,
        markersize=7,
    )
    for position, value in zip(positions, values):
        axis.text(value + 0.7, position, f"{value:.1f}%", va="center", fontsize=8.5)
    axis.set_yticks(positions, [str(row["failure_class"]).replace("_", " ") for row in weighted_order])
    axis.invert_yaxis()
    axis.set_xlim(0, max(45.0, max(highs) + 10.0))
    axis.set_xlabel("Design-weighted estimated share of the flagged-run population (%)")
    axis.set_title("E17 population estimates from the representative stratum", loc="left", fontweight="bold")
    axis.grid(axis="x", alpha=0.25)
    axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(weighted_png, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(weighted_svg, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    group_png = output_dir / "sample_group_composition.png"
    group_svg = output_dir / "sample_group_composition.svg"
    groups = [REPRESENTATIVE_GROUP, *TARGETED_GROUPS]
    by_group = {(str(row["sample_group"]), str(row["failure_class"])): float(row["percent"]) for row in group_rows}
    fig, axis = plt.subplots(figsize=(10.2, 5.5), dpi=160)
    fig.patch.set_facecolor("#FAFBFC")
    axis.set_facecolor("#FAFBFC")
    left = [0.0] * len(groups)
    for code in e17_review.PRIMARY_CODES:
        values = [by_group.get((group, code), 0.0) for group in groups]
        axis.barh(groups, values, left=left, label=code.replace("_", " "), color=colors[code])
        left = [a + b for a, b in zip(left, values)]
    axis.set_xlim(0, 100)
    axis.set_xlabel("Within-group share (%)")
    axis.set_title("E17 audit groups: descriptive composition only", loc="left", fontweight="bold")
    axis.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.35), frameon=False)
    axis.grid(axis="x", alpha=0.2)
    axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(group_png, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(group_svg, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return [
        {
            "id": "representative_failure_counts",
            "title": "E17 representative-sample failure classes",
            "role": "primary",
            "order": 0,
            "chart_type": "horizontal_bar_with_wilson_interval",
            "caption": "Unweighted primary-class composition of the 300 representative audited items with Wilson 95% intervals.",
            "files": {"data": "failure_class_counts.csv", "png": count_png.name, "svg": count_svg.name},
            "metrics": ["count", "percent"],
            "grain": ["representative_sample", "primary_failure_class"],
            "uncertainty": [{"method": "Wilson score interval", "confidence_level": 0.95}],
            "warnings": ["Describes the representative sample; use the weighted figure for population estimates."],
        },
        {
            "id": "weighted_population_estimates",
            "title": "E17 design-weighted flagged-run population estimates",
            "role": "primary",
            "order": 1,
            "chart_type": "dot_and_interval",
            "caption": "Hájek design-weighted class shares with 10,000-iteration stratified percentile-bootstrap 95% intervals.",
            "files": {"data": "weighted_population_estimates.csv", "png": weighted_png.name, "svg": weighted_svg.name},
            "metrics": ["weighted_share"],
            "grain": ["flagged_run_population", "primary_failure_class"],
            "uncertainty": [{"method": "stratified percentile bootstrap", "confidence_level": 0.95, "iterations": BOOTSTRAP_ITERATIONS, "seed": BOOTSTRAP_SEED}],
            "warnings": ["Estimates use only the 300-row representative stratum and its frozen design weights."],
        },
        {
            "id": "sample_group_composition",
            "title": "E17 sampled-group class composition",
            "role": "diagnostic",
            "order": 2,
            "chart_type": "one_hundred_percent_stacked_bar",
            "caption": "Within-group class composition for the representative and two targeted diagnostic groups.",
            "files": {"data": "sample_group_counts.csv", "png": group_png.name, "svg": group_svg.name},
            "metrics": ["count", "percent"],
            "grain": ["sample_group", "primary_failure_class"],
            "uncertainty": [{"method": "not_applicable", "reason": "targeted diagnostic comparison"}],
            "warnings": ["The 40 disagreement-targeted and 20 rare/complex rows must not be pooled into population estimates."],
        },
    ]


def _artifact_entry(path: Path, kind: str) -> dict[str, Any]:
    return {
        "path": _relative(path),
        "kind": kind,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def finalize_sample_review(
    *,
    package_dir: str | Path = DEFAULT_PACKAGE_DIR,
    reviewer_1_path: str | Path = DEFAULT_REVIEWER_1,
    reviewer_2_path: str | Path = DEFAULT_REVIEWER_2,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    bootstrap_iterations: int = BOOTSTRAP_ITERATIONS,
    bootstrap_seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """验证并固化已完成的 360 行双人复核抽样数据。"""

    package = Path(package_dir).resolve()
    reviewer_1_file = Path(reviewer_1_path).resolve()
    reviewer_2_file = Path(reviewer_2_path).resolve()
    output = Path(output_dir).resolve()
    if bootstrap_iterations <= 0:
        raise HumanSampleReviewError("bootstrap_iterations must be positive")
    for path in (reviewer_1_file, reviewer_2_file):
        if not path.is_file() or path.stat().st_size <= 0:
            raise HumanSampleReviewError(f"reviewer submission is missing or empty: {path}")

    package_manifest, items, metadata = _validate_frozen_package(package)
    try:
        first = e17_review.validate_reviewer_csv(reviewer_1_file, items)
        second = e17_review.validate_reviewer_csv(reviewer_2_file, items)
        interrater, disagreements = e17_review.compare_reviewers(first, second)
    except e17_review.ReviewValidationError as exc:
        raise HumanSampleReviewError(str(exc)) from exc
    if disagreements:
        raise HumanSampleReviewError(
            f"sample has {len(disagreements)} primary/secondary code-set disagreements; adjudication is required"
        )
    if int(interrater.get("items", -1)) != 360:
        raise HumanSampleReviewError("validated reviewer coverage is not 360 items")

    metadata_by_id = {str(row["blind_id"]): row for row in metadata}
    final_rows: list[dict[str, Any]] = []
    for blind_id in sorted(first["reviews"]):
        left = first["reviews"][blind_id]
        right = second["reviews"][blind_id]
        meta = metadata_by_id[blind_id]
        final_rows.append(
            {
                "blind_id": blind_id,
                "case_id": meta.get("case_id", ""),
                "experiment_id": meta.get("experiment_id", ""),
                "model": meta.get("model", ""),
                "prompt_profile": meta.get("prompt_profile", ""),
                "guard_mode": meta.get("guard_mode", ""),
                "sample_type": meta.get("sample_type", ""),
                "attack_family": meta.get("attack_family", ""),
                "language": meta.get("language", ""),
                "sample_group": meta.get("sample_group", ""),
                "flag_combination": meta.get("flag_combination", ""),
                "evidence_signature": meta.get("evidence_signature", ""),
                "cluster_size": meta.get("cluster_size", ""),
                "analysis_weight": meta.get("representative_analysis_weight"),
                "reviewer_1_id": first["reviewer_id"],
                "reviewer_1_code": left["primary_code"],
                "reviewer_1_secondary": "|".join(left["secondary_codes"]),
                "reviewer_1_confidence": left["confidence"],
                "reviewer_1_rationale": left["rationale"],
                "reviewer_2_id": second["reviewer_id"],
                "reviewer_2_code": right["primary_code"],
                "reviewer_2_secondary": "|".join(right["secondary_codes"]),
                "reviewer_2_confidence": right["confidence"],
                "reviewer_2_rationale": right["rationale"],
                "final_primary_code": left["primary_code"],
                "final_secondary_codes": "|".join(left["secondary_codes"]),
                "resolution_source": "exact_two_reviewer_code_set_agreement",
            }
        )

    representative = [row for row in final_rows if row["sample_group"] == REPRESENTATIVE_GROUP]
    raw_counts = _count_rows([str(row["final_primary_code"]) for row in representative])
    weighted = _weighted_estimates(final_rows, iterations=bootstrap_iterations, seed=bootstrap_seed)
    group_rows: list[dict[str, Any]] = []
    for group in (REPRESENTATIVE_GROUP, *TARGETED_GROUPS):
        members = [row for row in final_rows if row["sample_group"] == group]
        for row in _count_rows([str(member["final_primary_code"]) for member in members]):
            group_rows.append({"sample_group": group, **row})

    confidence_counts = Counter(
        str(first["reviews"][blind_id]["confidence"]) for blind_id in first["reviews"]
    )
    secondary_counts = Counter(
        "|".join(first["reviews"][blind_id]["secondary_codes"]) or "none"
        for blind_id in first["reviews"]
    )

    output.mkdir(parents=True, exist_ok=True)
    taxonomy_path = output / "failure_taxonomy.csv"
    counts_path = output / "failure_class_counts.csv"
    weighted_path = output / "weighted_population_estimates.csv"
    groups_path = output / "sample_group_counts.csv"
    agreement_path = output / "reviewer_agreement.json"
    confidence_path = output / "confidence_counts.csv"
    statistics_path = output / "statistics.json"
    analysis_path = output / "analysis.md"
    status_path = package / "HUMAN_REVIEW_STATUS.md"

    taxonomy_fields = tuple(final_rows[0])
    _atomic_write_csv(taxonomy_path, final_rows, taxonomy_fields)
    count_fields = tuple(raw_counts[0])
    _atomic_write_csv(counts_path, raw_counts, count_fields)
    _atomic_write_csv(weighted_path, weighted, tuple(weighted[0]))
    _atomic_write_csv(groups_path, group_rows, tuple(group_rows[0]))
    _atomic_write_csv(
        confidence_path,
        (
            {"measure": "confidence", "value": key, "count": value}
            for key, value in sorted(confidence_counts.items())
        ),
        ("measure", "value", "count"),
    )
    _atomic_write_json(agreement_path, interrater)

    statistics = {
        "experiment_id": "E17",
        "protocol_id": PROTOCOL_ID,
        "source_mode": SOURCE_MODE,
        "evidence_tier": EVIDENCE_TIER,
        "coverage": {
            "population_rows": int(package_manifest["population_rows"]),
            "reviewed_sample_rows": len(final_rows),
            "representative_rows": len(representative),
            "targeted_auto_disagreement_rows": 40,
            "targeted_rare_complex_rows": 20,
            "human_reviewers": 2,
            "full_population_human_reviewed": False,
        },
        "interrater": interrater,
        "adjudication_required": False,
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "secondary_code_set_counts": dict(sorted(secondary_counts.items())),
        "representative_primary_class_counts": {
            row["failure_class"]: int(row["count"]) for row in raw_counts
        },
        "weighted_population_estimates": weighted,
        "bootstrap": {
            "method": "stratified_design_weighted_percentile_bootstrap",
            "iterations": bootstrap_iterations,
            "seed": bootstrap_seed,
            "confidence_level": 0.95,
            "resampling_unit": "sampled evidence cluster within flag_combination stratum",
        },
        "scope_guardrail": {
            "allowed_claim": "two independent humans reviewed the frozen 360-row stratified audit sample",
            "prohibited_claim": PROHIBITED_CLAIM,
            "population_estimation_group": REPRESENTATIVE_GROUP,
            "targeted_groups": list(TARGETED_GROUPS),
            "targeted_groups_pooled_into_population_estimates": False,
        },
    }
    _atomic_write_json(statistics_path, statistics)

    figures = _render_figures(output, raw_counts, weighted, group_rows)
    figure_manifest_path = write_figure_manifest(
        output,
        experiment_id="E17",
        evidence_tier=EVIDENCE_TIER,
        figures=figures,
    )

    top_raw = max(raw_counts, key=lambda row: int(row["count"]))
    top_weighted = max(weighted, key=lambda row: float(row["weighted_share"]))
    analysis = "\n".join(
        [
            "# E17 Stratified Human Audit",
            "",
            "## Result",
            "",
            (
                f"Two independent blinded reviewers completed all 360 sampled rows. Exact primary-plus-secondary "
                f"agreement was {interrater['agreements']}/{interrater['items']} "
                f"({100.0 * float(interrater['percent_agreement']):.1f}%), and Cohen's kappa was "
                f"{float(interrater['cohen_kappa']):.3f}. No adjudicator was required."
            ),
            "",
            "## Representative sample",
            "",
            (
                f"Among the 300 representative rows, the largest raw primary class was `{top_raw['failure_class']}` "
                f"({top_raw['count']}/300, {float(top_raw['percent']):.1f}%). Raw class shares use Wilson 95% "
                "intervals."
            ),
            "",
            "![Representative failure classes](representative_failure_counts.png)",
            "",
            "## Design-weighted population estimate",
            "",
            (
                f"Using the frozen stratum weights, the largest estimated class was `{top_weighted['failure_class']}` "
                f"({float(top_weighted['weighted_percent']):.1f}%). Intervals are 10,000-iteration stratified "
                "percentile-bootstrap 95% intervals."
            ),
            "",
            "![Weighted population estimates](weighted_population_estimates.png)",
            "",
            "## Targeted diagnostics",
            "",
            "The 40 auto-disagreement rows and 20 rare/complex rows are diagnostic stress samples. Their raw proportions are shown only by group and are not pooled into the population estimate.",
            "",
            "![Sample-group composition](sample_group_composition.png)",
            "",
            "## Scope limitation",
            "",
            "This audit supports the claim that two humans independently reviewed a frozen stratified sample of 360 rows. It does not support the claim that all 3,299 E17 candidates received human review. The original full E17 bundle remains preserved as pending provenance.",
            "",
        ]
    )
    _atomic_write_text(analysis_path, analysis)
    _atomic_write_text(
        status_path,
        "\n".join(
            [
                "# Human review status",
                "",
                "- Status: completed stratified sample audit",
                "- Reviewers: 2 distinct human reviewers",
                "- Frozen rows per reviewer: 360",
                "- Exact primary-plus-secondary agreement: 360/360",
                "- Adjudication: not required",
                "- Representative estimation group: 300 rows",
                "- Targeted diagnostic groups: 40 + 20 rows (not pooled)",
                "- Full 3,299-row human review: not performed",
                "",
                "Final validated evidence is stored in `review/`.",
                "",
            ]
        ),
    )

    output_files = [
        taxonomy_path,
        counts_path,
        weighted_path,
        groups_path,
        agreement_path,
        confidence_path,
        statistics_path,
        analysis_path,
        *(output / figure["files"][role] for figure in figures for role in ("png", "svg")),
        figure_manifest_path,
        status_path,
    ]
    kind_by_name = {
        "failure_taxonomy.csv": "final_human_labels",
        "failure_class_counts.csv": "representative_count_statistics",
        "weighted_population_estimates.csv": "weighted_population_statistics",
        "sample_group_counts.csv": "diagnostic_group_statistics",
        "reviewer_agreement.json": "interrater_statistics",
        "confidence_counts.csv": "review_confidence_statistics",
        "statistics.json": "final_statistics",
        "analysis.md": "technical_analysis",
        "figure_manifest.json": "figure_manifest",
        "HUMAN_REVIEW_STATUS.md": "package_status",
    }
    artifacts = [
        _artifact_entry(path, kind_by_name.get(path.name, "figure_asset")) for path in output_files
    ]
    input_records = {
        "sample_manifest": {"path": _relative(package / "manifest.json"), "sha256": _sha256(package / "manifest.json")},
        "packet_manifest": {"path": _relative(package / "packet_manifest.json"), "sha256": _sha256(package / "packet_manifest.json")},
        "private_sample_items": {"path": _relative(package / "private" / "review_items_360.jsonl"), "sha256": _sha256(package / "private" / "review_items_360.jsonl")},
        "blank_template": {"path": _relative(package / "packets" / "reviewer_1_blinded_template.csv"), "sha256": _sha256(package / "packets" / "reviewer_1_blinded_template.csv")},
        "reviewer_1_submission": {"path": _relative(reviewer_1_file), "sha256": _sha256(reviewer_1_file), "reviewer_id": first["reviewer_id"]},
        "reviewer_2_submission": {"path": _relative(reviewer_2_file), "sha256": _sha256(reviewer_2_file), "reviewer_id": second["reviewer_id"]},
    }
    source_index_record = package_manifest["inputs"]["corrected_source_index"]
    source_index_path = REPO_ROOT / str(source_index_record["path"])
    if _sha256(source_index_path) != str(source_index_record["sha256"]):
        raise HumanSampleReviewError("corrected E17 source index drifted")
    dataset_sha = _json_hash({key: value["sha256"] for key, value in sorted(input_records.items())})
    git = _git_state()
    completed_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": "E17",
        "protocol_id": PROTOCOL_ID,
        "status": "completed",
        "phase": "completed_stratified_sample_audit",
        "created_at": completed_at,
        "completed_at": completed_at,
        "git": git,
        "dataset": {"sha256": dataset_sha, "inputs": input_records},
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "models": [],
        "configuration": {
            "workflow": "blinded_dual_review_stratified_sample_without_adjudication",
            "source_mode": SOURCE_MODE,
            "evidence_tier": EVIDENCE_TIER,
            "registry_eligible": True,
            "source_index": {
                "path": _relative(source_index_path),
                "sha256": _sha256(source_index_path),
                "schema_version": e17_review.SOURCE_INDEX_SCHEMA_VERSION,
            },
            "coverage": {
                "population_rows": 3299,
                "reviewed_sample_rows": 360,
                "representative_rows": 300,
                "targeted_rows": 60,
                "full_population_human_reviewed": False,
            },
            "bootstrap_iterations": bootstrap_iterations,
            "bootstrap_seed": bootstrap_seed,
        },
        "plan": {
            "source_mode": SOURCE_MODE,
            "source_index": {
                "path": _relative(source_index_path),
                "sha256": _sha256(source_index_path),
            },
            "sampling_manifest": input_records["sample_manifest"],
            "packet_manifest": input_records["packet_manifest"],
            "population_rows": 3299,
            "sample_rows": 360,
            "representative_rows": 300,
            "targeted_rows": 60,
        },
        "progress": {"expected_runs": 360, "completed_runs": 360, "failed_jobs": 0, "unresolved_cases": 0},
        "review_progress": {
            "review_items": 360,
            "reviewers_required": 2,
            "reviewers_received": 2,
            "reviewer_ids": [first["reviewer_id"], second["reviewer_id"]],
            "code_set_agreements": 360,
            "code_set_disagreements": 0,
            "adjudications_completed": 0,
        },
        "sampling_contract": statistics["scope_guardrail"] | {
            "protocol_id": PROTOCOL_ID,
            "population_rows": 3299,
            "sample_rows": 360,
            "representative_rows": 300,
            "targeted_rows": 60,
        },
        "final_statistics": {
            "cohen_kappa": interrater["cohen_kappa"],
            "percent_agreement": interrater["percent_agreement"],
            "representative_primary_class_counts": statistics["representative_primary_class_counts"],
        },
        "artifacts": sorted(artifacts, key=lambda item: str(item["path"])),
        "failure": None,
    }
    manifest_path = output / "manifest.json"
    _atomic_write_json(manifest_path, manifest)
    return {
        "manifest": manifest,
        "manifest_path": str(manifest_path),
        "interrater": interrater,
        "statistics": statistics,
        "reviewer_1_sha256": first["sha256"],
        "reviewer_2_sha256": second["sha256"],
    }


__all__ = [
    "BOOTSTRAP_ITERATIONS",
    "BOOTSTRAP_SEED",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_PACKAGE_DIR",
    "DEFAULT_REVIEWER_1",
    "DEFAULT_REVIEWER_2",
    "EVIDENCE_TIER",
    "HumanSampleReviewError",
    "PROTOCOL_ID",
    "SOURCE_MODE",
    "finalize_sample_review",
]
