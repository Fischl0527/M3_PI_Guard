"""Materialize one frozen public-benchmark formal cell from case-run rows.

The previous preparation step creates pending cell manifests and todo queues.
This module is the next, stricter gate: it accepts an already-produced
``case_results.jsonl`` for exactly one cell, verifies that it covers the frozen
todo queue, writes the required artifacts, and updates the cell manifest.

It does not run models or benchmarks.  It also refuses to call diagnostic/stub
rows formal evidence: a cell becomes result-eligible only when every expected
case-run is present, every case-run completed, and every row declares
``evidence_status == formal_public_benchmark_case_run``.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from m3_eval.statistics import latency_summary, proportion_result

from .common import rows_sha256, sha256_file, write_jsonl


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULT_ROOT = ROOT / "outputs" / "paper_upgrade_v1" / "public_benchmark_formal_runs"
FORMAL_EVIDENCE_STATUS = "formal_public_benchmark_case_run"
CELL_MATERIALIZER_VERSION = "m3-paper-v1-public-benchmark-formal-cell-materializer-1.0"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "success"}


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _proportion_row(metric: str, numerator: int, denominator: int, *, group: str = "all") -> dict[str, Any]:
    result = proportion_result(numerator, denominator)
    return {
        "metric": metric,
        "group": group,
        "numerator": result["numerator"],
        "denominator": result["denominator"],
        "value": result["value"],
        "ci_low": result["ci_low"],
        "ci_high": result["ci_high"],
        "confidence": result["confidence"],
        "unit": "proportion",
    }


def _write_metrics_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    fieldnames = (
        "metric",
        "group",
        "numerator",
        "denominator",
        "value",
        "ci_low",
        "ci_high",
        "confidence",
        "unit",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _write_raw_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    fieldnames = (
        "case_run_id",
        "benchmark",
        "model",
        "condition_id",
        "benchmark_case_id",
        "case_kind",
        "replicate_id",
        "status",
        "evidence_status",
        "attack_success",
        "utility_success",
        "guard_decision",
        "parse_ok",
        "case_latency_ms",
        "model_latency_ms",
        "guard_latency_ms",
        "total_tokens",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _status_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status", "missing_status"))
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _validate_rows_against_cell(
    *,
    manifest: Mapping[str, Any],
    todo_rows: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_ids = {str(row["case_run_id"]) for row in todo_rows}
    seen_ids = [str(row.get("case_run_id", "")) for row in result_rows]
    duplicates = sorted({case_id for case_id in seen_ids if seen_ids.count(case_id) > 1})
    seen_set = set(seen_ids)
    missing = sorted(expected_ids - seen_set)
    unexpected = sorted(seen_set - expected_ids)
    cell_id = str(manifest.get("cell_id", ""))
    identity_mismatches = [
        str(row.get("case_run_id", ""))
        for row in result_rows
        if str(row.get("cell_id", cell_id)) != cell_id
        or str(row.get("benchmark", "")) != str(manifest.get("benchmark", ""))
        or str(row.get("model", "")) != str(manifest.get("model", ""))
        or str(row.get("condition_id", "")) != str(manifest.get("condition_id", ""))
    ]
    nonformal = [
        str(row.get("case_run_id", ""))
        for row in result_rows
        if str(row.get("evidence_status", "")) != FORMAL_EVIDENCE_STATUS
    ]
    noncompleted = [
        str(row.get("case_run_id", ""))
        for row in result_rows
        if str(row.get("status", "")) != "completed"
    ]
    return {
        "expected_case_run_count": len(expected_ids),
        "observed_case_run_count": len(result_rows),
        "duplicate_case_run_ids": duplicates,
        "missing_case_run_ids": missing,
        "unexpected_case_run_ids": unexpected,
        "identity_mismatch_case_run_ids": sorted(identity_mismatches),
        "nonformal_evidence_case_run_ids": sorted(nonformal),
        "noncompleted_case_run_ids": sorted(noncompleted),
        "coverage_ok": not duplicates and not missing and not unexpected and not identity_mismatches,
        "formal_evidence_ok": not nonformal,
        "completed_ok": not noncompleted,
    }


def _metric_rows(result_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(result_rows)
    completed = [row for row in result_rows if str(row.get("status", "")) == "completed"]
    security = [row for row in result_rows if str(row.get("case_kind", "")) == "security"]
    utility = [row for row in result_rows if str(row.get("case_kind", "")) == "utility"]
    decisions = [str(row.get("guard_decision", "")) for row in result_rows]
    return [
        _proportion_row("case_run_completion_rate", len(completed), total),
        _proportion_row(
            "security_attack_success_rate",
            sum(_coerce_bool(row.get("attack_success")) for row in security),
            len(security),
            group="security",
        ),
        _proportion_row(
            "utility_success_rate",
            sum(_coerce_bool(row.get("utility_success")) for row in utility),
            len(utility),
            group="utility",
        ),
        _proportion_row(
            "parse_success_rate",
            sum(_coerce_bool(row.get("parse_ok")) for row in result_rows),
            total,
        ),
        _proportion_row("ask_rate", sum(value == "ASK" for value in decisions), total),
        _proportion_row("deny_rate", sum(value == "DENY" for value in decisions), total),
    ]


def _statistics(result_rows: list[dict[str, Any]], metric_rows: list[dict[str, Any]]) -> dict[str, Any]:
    latency_fields = ("case_latency_ms", "model_latency_ms", "guard_latency_ms")
    latency = {
        field: latency_summary(
            value
            for value in (_coerce_float(row.get(field)) for row in result_rows)
            if value is not None
        )
        for field in latency_fields
    }
    tokens = [
        value
        for value in (_coerce_float(row.get("total_tokens")) for row in result_rows)
        if value is not None
    ]
    return {
        "schema_version": "paper-public-benchmark-formal-cell-statistics-1.0",
        "method": "descriptive_cell_statistics_with_wilson_ci",
        "status_counts": _status_counts(result_rows),
        "metric_rows": metric_rows,
        "latency": latency,
        "token_summary": {
            "count": len(tokens),
            "sum": int(sum(tokens)) if tokens else 0,
            "mean": (sum(tokens) / len(tokens)) if tokens else None,
        },
        "boundary": (
            "Cell-level descriptive statistics only. Cross-condition paired "
            "tests, clustered bootstrap and Holm correction must be generated "
            "from the frozen multi-cell analysis layer, not a single cell."
        ),
    }


def _figure_manifest(cell_id: str, metric_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "paper-public-benchmark-formal-cell-figure-manifest-1.0",
        "status": "cell_summary_json_only",
        "cell_id": cell_id,
        "figures": [],
        "source_metrics": [row["metric"] for row in metric_rows],
        "boundary": (
            "This per-cell manifest reserves the required figure artifact slot. "
            "Formal paper figures are generated by the frozen cross-cell figure "
            "pipeline after all cells complete."
        ),
    }


def materialize_public_benchmark_formal_cell(
    *,
    cell_id: str,
    case_results_path: Path,
    result_root: Path = DEFAULT_RESULT_ROOT,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    result_root = result_root.resolve()
    case_results_path = case_results_path.resolve()
    cell_dir = result_root / "cells" / cell_id
    manifest_path = cell_dir / "manifest.json"
    todo_path = cell_dir / "todo_cases.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError("cell manifest not found: " + str(manifest_path))
    if not todo_path.exists():
        raise FileNotFoundError("cell todo queue not found: " + str(todo_path))
    manifest = _read_json(manifest_path)
    existing_status = str(manifest.get("status", ""))
    if existing_status in {"completed", "formal_completed"} and not force:
        raise RuntimeError("refusing to overwrite completed cell without --force")
    if str(manifest.get("cell_id", "")) != cell_id:
        raise ValueError("cell_id does not match manifest")
    todo_rows = _read_jsonl(todo_path)
    result_rows = _read_jsonl(case_results_path)
    validation = _validate_rows_against_cell(
        manifest=manifest,
        todo_rows=todo_rows,
        result_rows=result_rows,
    )
    metric_rows = _metric_rows(result_rows)
    statistics = _statistics(result_rows, metric_rows)
    complete = bool(
        validation["coverage_ok"]
        and validation["formal_evidence_ok"]
        and validation["completed_ok"]
    )
    now = datetime.now(timezone.utc).isoformat()
    raw_csv_path = cell_dir / "raw_runs.csv"
    raw_jsonl_path = cell_dir / "raw_runs.jsonl"
    metrics_path = cell_dir / "metrics.csv"
    statistics_path = cell_dir / "statistics.json"
    figures_path = cell_dir / "figure_manifest.json"
    if not dry_run:
        _write_raw_csv(raw_csv_path, result_rows)
        write_jsonl(raw_jsonl_path, result_rows)
        _write_metrics_csv(metrics_path, metric_rows)
        _write_json(statistics_path, statistics)
        _write_json(figures_path, _figure_manifest(cell_id, metric_rows))
    failed_case_runs = len(validation["noncompleted_case_run_ids"])
    missing_case_runs = len(validation["missing_case_run_ids"])
    completed_case_runs = (
        int(validation["expected_case_run_count"]) - missing_case_runs - failed_case_runs
    )
    artifacts = {}
    if not dry_run:
        artifacts = {
            "raw_runs": {"path": raw_csv_path.name, "sha256": sha256_file(raw_csv_path)},
            "metrics": {"path": metrics_path.name, "sha256": sha256_file(metrics_path)},
            "statistics": {"path": statistics_path.name, "sha256": sha256_file(statistics_path)},
            "figures": {"path": figures_path.name, "sha256": sha256_file(figures_path)},
            "raw_runs_jsonl": {
                "path": raw_jsonl_path.name,
                "sha256": sha256_file(raw_jsonl_path),
                "required_for_completion": False,
            },
        }
    updated_manifest = {
        **manifest,
        "materializer_version": CELL_MATERIALIZER_VERSION,
        "status": "completed" if complete else "completed_with_failures",
        "updated_at": now,
        "completed_at": now if complete else None,
        "case_results_source_path": str(case_results_path),
        "case_results_source_sha256": sha256_file(case_results_path),
        "completed_case_runs": completed_case_runs,
        "failed_case_runs": failed_case_runs,
        "missing_case_runs": missing_case_runs,
        "result_eligible_for_formal_tables": complete,
        "validation": validation,
        "metrics_sha256": rows_sha256(metric_rows),
        "statistics_method": statistics["method"],
        "artifacts": artifacts if not dry_run else manifest.get("artifacts", {}),
        "boundary": (
            "Materialized formal cell. Eligibility requires exact todo coverage, "
            "completed case-runs, formal evidence status on every row, and "
            "declared artifacts with SHA-256 hashes."
        ),
    }
    if not dry_run:
        _write_json(manifest_path, updated_manifest)
    return {
        "schema_version": "paper-public-benchmark-formal-cell-materialization-1.0",
        "materializer_version": CELL_MATERIALIZER_VERSION,
        "status": "completed" if complete else "completed_with_failures",
        "dry_run": dry_run,
        "cell_id": cell_id,
        "manifest_path": str(manifest_path),
        "result_eligible_for_formal_tables": complete,
        "completed_case_runs": completed_case_runs,
        "failed_case_runs": failed_case_runs,
        "missing_case_runs": missing_case_runs,
        "validation": validation,
        "artifact_paths": {
            "raw_runs": str(raw_csv_path),
            "metrics": str(metrics_path),
            "statistics": str(statistics_path),
            "figures": str(figures_path),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--case-results", type=Path, required=True)
    parser.add_argument("--result-root", type=Path, default=DEFAULT_RESULT_ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = materialize_public_benchmark_formal_cell(
        cell_id=args.cell_id,
        case_results_path=args.case_results,
        result_root=args.result_root,
        force=args.force,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
