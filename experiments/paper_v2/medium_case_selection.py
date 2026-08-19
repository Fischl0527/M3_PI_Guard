"""Freeze and verify the paper-v2 72-case medium falsification set.

Selection uses identifiers and pre-outcome strata only.  It never reads the
paper-v1 result tree and never selects from the sealed holdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

from experiments.paper_v2.contracts import (
    build_online_projection,
    canonical_json_bytes,
    compute_online_visible_field_digest,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_selection_spec_v1.json"
)
DEFAULT_INDEX = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_case_index_v1.jsonl"
)
DEFAULT_MANIFEST = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_case_manifest_v1.json"
)


class MediumSelectionError(ValueError):
    """Raised when the prospective selection contract cannot be reproduced."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        record["_source_line"] = line_number
        records.append(record)
    return records


def _rank(seed: str, case_id: str, purpose: str) -> str:
    return hashlib.sha256(f"{seed}\0{purpose}\0{case_id}".encode()).hexdigest()


def _stratified_take(
    records: Iterable[dict[str, Any]],
    *,
    count: int,
    seed: str,
    purpose: str,
    case_id: Callable[[dict[str, Any]], str],
    stratum: Callable[[dict[str, Any]], tuple[str, ...]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[stratum(record)].append(record)
    if not groups:
        raise MediumSelectionError(f"{purpose}: no eligible records")
    if count < len(groups):
        raise MediumSelectionError(
            f"{purpose}: count {count} cannot cover {len(groups)} strata"
        )
    selected: list[dict[str, Any]] = []
    for key in sorted(groups):
        ordered = sorted(
            groups[key],
            key=lambda item: _rank(seed, case_id(item), f"{purpose}:{key}"),
        )
        selected.append(ordered[0])
    remaining = [
        item
        for items in groups.values()
        for item in items
        if item not in selected
    ]
    remaining.sort(key=lambda item: _rank(seed, case_id(item), purpose))
    selected.extend(remaining[: count - len(selected)])
    if len(selected) != count:
        raise MediumSelectionError(
            f"{purpose}: requested {count}, selected {len(selected)}"
        )
    return selected


def _source_record(
    *,
    record: dict[str, Any],
    source_name: str,
    source_path: str,
    benchmark: str,
    evaluation_case_type: str,
    context_dependent: bool,
    stratum: tuple[str, ...],
) -> dict[str, Any]:
    if benchmark == "m3-v2":
        case_id = record["case_id"]
        projection = build_online_projection(
            record,
            (
                "trusted_user_request",
                "trusted_app_context",
                "untrusted_content",
                "untrusted_memory",
            ),
        )
    else:
        case_id = record["benchmark_case_id"]
        projection = build_online_projection(record, ("online_inputs",))
    return {
        "selection_id": f"medium-v1:{case_id}",
        "case_id": case_id,
        "benchmark": benchmark,
        "source_set": source_name,
        "source_path": source_path,
        "source_line": record["_source_line"],
        "source_record_sha256": sha256_canonical_json(
            {key: value for key, value in record.items() if key != "_source_line"}
        ),
        "evaluation_case_type": evaluation_case_type,
        "context_dependent": context_dependent,
        "selection_stratum": list(stratum),
        "primary_authorization_regime": "auto_compiled",
        "regime_probe": None,
        "online_visible_field_digest": compute_online_visible_field_digest(
            projection
        ),
    }


def build_selection(
    spec_path: Path = DEFAULT_SPEC,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec["selection_blinding"]["outcome_fields_used"]:
        raise MediumSelectionError("outcome-based medium-case selection is forbidden")
    if spec["selection_blinding"]["sealed_holdout_used"]:
        raise MediumSelectionError("sealed holdout cannot be used for medium selection")
    seed = spec["seed"]
    paths = {
        name: PROJECT_ROOT / relative
        for name, relative in spec["source_sets"].items()
    }
    source_records = {name: _read_jsonl(path) for name, path in paths.items()}
    m3 = source_records["m3_v2_development"]
    if {row["split"] for row in m3} != {"development"}:
        raise MediumSelectionError("M3 medium source must contain development cases only")

    selected: list[dict[str, Any]] = []

    m3_attack = _stratified_take(
        (row for row in m3 if row["sample_type"] == "attack"),
        count=spec["selection_counts"]["m3_attack"],
        seed=seed,
        purpose="m3_attack",
        case_id=lambda row: row["case_id"],
        stratum=lambda row: (row["attack_family"], row["language"]),
    )
    for row in m3_attack:
        selected.append(
            _source_record(
                record=row,
                source_name="m3_v2_development",
                source_path=spec["source_sets"]["m3_v2_development"],
                benchmark="m3-v2",
                evaluation_case_type="attack",
                context_dependent=row["scenario_type"]
                in {
                    "environment_context_pollution",
                    "memory_poisoning",
                    "cross_tool_attack_chain",
                },
                stratum=(row["attack_family"], row["language"]),
            )
        )

    for sample_type, count_key, case_type in (
        ("benign_legal_tool", "m3_benign_tool", "benign_tool"),
        ("benign_no_tool", "m3_benign_no_tool", "benign_no_tool"),
    ):
        rows = _stratified_take(
            (row for row in m3 if row["sample_type"] == sample_type),
            count=spec["selection_counts"][count_key],
            seed=seed,
            purpose=count_key,
            case_id=lambda row: row["case_id"],
            stratum=lambda row: (row["scenario_type"], row["language"]),
        )
        for row in rows:
            selected.append(
                _source_record(
                    record=row,
                    source_name="m3_v2_development",
                    source_path=spec["source_sets"]["m3_v2_development"],
                    benchmark="m3-v2",
                    evaluation_case_type=case_type,
                    context_dependent=row["scenario_type"] == "multi_step",
                    stratum=(row["scenario_type"], row["language"]),
                )
            )

    for source_name, count_key, case_type in (
        ("agentdojo_security", "agentdojo_attack", "attack"),
        ("agentdojo_utility", "agentdojo_benign_context", "benign_tool"),
    ):
        rows = _stratified_take(
            source_records[source_name],
            count=spec["selection_counts"][count_key],
            seed=seed,
            purpose=count_key,
            case_id=lambda row: row["benchmark_case_id"],
            stratum=lambda row: (row["suite"],),
        )
        for row in rows:
            selected.append(
                _source_record(
                    record=row,
                    source_name=source_name,
                    source_path=spec["source_sets"][source_name],
                    benchmark="agentdojo-v1",
                    evaluation_case_type=case_type,
                    context_dependent=True,
                    stratum=(row["suite"],),
                )
            )

    expected_total = spec["selection_counts"]["total"]
    if len(selected) != expected_total:
        raise MediumSelectionError(
            f"expected {expected_total} selected cases, got {len(selected)}"
        )
    if len({row["case_id"] for row in selected}) != len(selected):
        raise MediumSelectionError("selected case identifiers must be unique")

    probe = spec["regime_probe"]
    ordered = sorted(
        selected,
        key=lambda row: _rank(seed, row["case_id"], "regime_probe"),
    )
    offset = 0
    for regime in probe["regimes"]:
        for row in ordered[offset : offset + probe["cases_per_regime"]]:
            row["regime_probe"] = {
                "authorization_regime": regime,
                "condition_ids": probe["conditions"],
                "oracle_ablation": regime == "exact_gold",
                "primary_endpoint_excluded": probe["primary_endpoint_excluded"],
            }
        offset += probe["cases_per_regime"]

    selected.sort(key=lambda row: row["case_id"])
    source_locks = {
        name: {
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "rows": len(source_records[name]),
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for name, path in sorted(paths.items())
    }
    counts = Counter(row["evaluation_case_type"] for row in selected)
    manifest = {
        "schema_version": "m3-paper-v2-medium-case-manifest-1.0",
        "status": "frozen_cases_results_pending",
        "frozen_at": spec["frozen_at"],
        "spec_path": spec_path.relative_to(PROJECT_ROOT).as_posix(),
        "spec_sha256": _sha256_file(spec_path),
        "selection_method": "sha256_ranked_stratified_without_outcomes",
        "seed": seed,
        "case_count": len(selected),
        "case_counts": dict(sorted(counts.items())),
        "context_dependent_cases": sum(
            1 for row in selected if row["context_dependent"]
        ),
        "primary_authorization_regime": spec["primary_authorization_regime"],
        "regime_probe_cases": sum(
            1 for row in selected if row["regime_probe"] is not None
        ),
        "core_conditions": spec["core_conditions"],
        "source_locks": source_locks,
        "sealed_holdout_used": False,
        "outcomes_accessed_for_selection": False,
        "results_status": "not_run",
    }
    return selected, manifest


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def write_selection(
    *,
    spec_path: Path = DEFAULT_SPEC,
    index_path: Path = DEFAULT_INDEX,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    rows, manifest = build_selection(spec_path)
    index_bytes = _jsonl_bytes(rows)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_bytes(index_bytes)
    manifest["index_path"] = index_path.relative_to(PROJECT_ROOT).as_posix()
    manifest["index_bytes"] = len(index_bytes)
    manifest["index_sha256"] = hashlib.sha256(index_bytes).hexdigest()
    manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    return manifest


def verify_selection(
    *,
    spec_path: Path = DEFAULT_SPEC,
    index_path: Path = DEFAULT_INDEX,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    rows, expected = build_selection(spec_path)
    index_bytes = _jsonl_bytes(rows)
    observed = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected.update(
        {
            "index_path": index_path.relative_to(PROJECT_ROOT).as_posix(),
            "index_bytes": len(index_bytes),
            "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
        }
    )
    if index_path.read_bytes() != index_bytes:
        raise MediumSelectionError("frozen medium case index does not reproduce")
    if observed != expected:
        raise MediumSelectionError("frozen medium case manifest does not reproduce")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path

    operation = verify_selection if args.verify_only else write_selection
    manifest = operation(
        spec_path=resolve(args.spec),
        index_path=resolve(args.index),
        manifest_path=resolve(args.manifest),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
