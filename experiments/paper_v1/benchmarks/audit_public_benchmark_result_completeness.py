"""Audit completeness of frozen public-benchmark formal run outputs.

The public benchmark freeze declares the expected formal matrix.  This audit
checks whether every expected matrix cell has a completed result manifest,
complete raw logs, metrics, statistics and figure artifacts.

It does not run models or benchmarks.  Missing outputs are reported as an
unsatisfied result gate, not as a script failure.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import canonical_json, portable_path, portable_value, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = ROOT / "protocols" / "paper_upgrade_v1" / "public_benchmark_formal_freeze_v1.json"
DEFAULT_RESULT_ROOT = ROOT / "outputs" / "paper_upgrade_v1" / "public_benchmark_formal_runs"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
AUDIT_VERSION = "m3-paper-v1-public-benchmark-result-completeness-audit-1.0"
AUDIT_STEM = "public_benchmark_result_completeness_audit_v1"
REQUIRED_ARTIFACTS = ("raw_runs", "metrics", "statistics", "figures")
COMPLETED_STATUSES = {"completed", "formal_completed"}


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in str(value)).strip("_")


def _cell_id(row: Mapping[str, Any]) -> str:
    return "__".join(
        (
            _slug(str(row.get("benchmark", ""))),
            _slug(str(row.get("model", ""))),
            _slug(str(row.get("condition_id", ""))),
            "r" + str(int(row.get("repeats", 1))),
        )
    )


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


def _resolve_artifact_path(cell_dir: Path, value: Any) -> Path | None:
    if isinstance(value, str):
        candidate = Path(value)
    elif isinstance(value, Mapping) and value.get("path"):
        candidate = Path(str(value["path"]))
    else:
        return None
    return candidate if candidate.is_absolute() else cell_dir / candidate


def _artifact_expected_sha(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("sha256", ""))
    return ""


def _artifact_check(cell_dir: Path, manifest: Mapping[str, Any], name: str) -> dict[str, Any]:
    artifacts = manifest.get("artifacts", {})
    declared = artifacts.get(name) if isinstance(artifacts, Mapping) else None
    path = _resolve_artifact_path(cell_dir, declared)
    expected_sha = _artifact_expected_sha(declared)
    actual_sha = sha256_file(path) if path is not None and path.exists() else ""
    exists = bool(path is not None and path.exists())
    sha_ok = bool(exists and (not expected_sha or expected_sha == actual_sha))
    return {
        "name": name,
        "declared": declared is not None,
        "path": str(path) if path is not None else "",
        "exists": exists,
        "expected_sha256": expected_sha,
        "actual_sha256": actual_sha,
        "sha256_matches": sha_ok,
        "passed": bool(declared is not None and exists and sha_ok),
    }


def _manifest_value(manifest: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in manifest:
            return manifest[name]
    return None


def _audit_cell(expected: Mapping[str, Any], result_root: Path) -> dict[str, Any]:
    cell_id = _cell_id(expected)
    cell_dir = result_root / "cells" / cell_id
    manifest_path = cell_dir / "manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
    expected_case_count = int(expected.get("case_count", 0))
    expected_repeats = int(expected.get("repeats", 1))
    expected_case_runs = int(expected.get("case_runs", expected_case_count * expected_repeats))
    artifact_checks = [
        _artifact_check(cell_dir, manifest, name) for name in REQUIRED_ARTIFACTS
    ] if manifest else []
    requirements = [
        {
            "name": "manifest_exists",
            "passed": manifest_path.exists(),
            "detail": str(manifest_path),
        },
        {
            "name": "status_completed",
            "passed": manifest.get("status") in COMPLETED_STATUSES,
            "detail": manifest.get("status"),
        },
        {
            "name": "result_eligible_true",
            "passed": bool(manifest.get("result_eligible_for_formal_tables")),
            "detail": manifest.get("result_eligible_for_formal_tables"),
        },
        {
            "name": "benchmark_model_condition_match",
            "passed": bool(manifest)
            and manifest.get("benchmark") == expected.get("benchmark")
            and manifest.get("model") == expected.get("model")
            and manifest.get("condition_id") == expected.get("condition_id"),
            "detail": {
                "expected": {
                    "benchmark": expected.get("benchmark"),
                    "model": expected.get("model"),
                    "condition_id": expected.get("condition_id"),
                },
                "manifest": {
                    "benchmark": manifest.get("benchmark"),
                    "model": manifest.get("model"),
                    "condition_id": manifest.get("condition_id"),
                },
            },
        },
        {
            "name": "case_count_matches_freeze",
            "passed": int(_manifest_value(manifest, "case_count") or -1) == expected_case_count,
            "detail": {
                "expected": expected_case_count,
                "manifest": _manifest_value(manifest, "case_count"),
            },
        },
        {
            "name": "case_runs_complete",
            "passed": int(_manifest_value(manifest, "completed_case_runs", "completed_runs") or -1)
            == expected_case_runs,
            "detail": {
                "expected_case_runs": expected_case_runs,
                "completed": _manifest_value(manifest, "completed_case_runs", "completed_runs"),
            },
        },
        {
            "name": "no_failed_or_missing_case_runs",
            "passed": int(_manifest_value(manifest, "failed_case_runs", "failed_runs") or 0) == 0
            and int(_manifest_value(manifest, "missing_case_runs", "missing_runs") or 0) == 0,
            "detail": {
                "failed": _manifest_value(manifest, "failed_case_runs", "failed_runs"),
                "missing": _manifest_value(manifest, "missing_case_runs", "missing_runs"),
            },
        },
        {
            "name": "required_artifacts_present",
            "passed": bool(artifact_checks) and all(item["passed"] for item in artifact_checks),
            "detail": {
                item["name"]: {
                    "exists": item["exists"],
                    "sha256_matches": item["sha256_matches"],
                }
                for item in artifact_checks
            },
        },
    ]
    failed = [item["name"] for item in requirements if not item["passed"]]
    return {
        "cell_id": cell_id,
        "benchmark": expected.get("benchmark"),
        "model": expected.get("model"),
        "condition_id": expected.get("condition_id"),
        "repeats": expected_repeats,
        "expected_case_count": expected_case_count,
        "expected_case_runs": expected_case_runs,
        "cell_dir": str(cell_dir),
        "manifest_path": str(manifest_path),
        "manifest_exists": manifest_path.exists(),
        "formal_cell_status": "complete" if not failed else "missing_or_incomplete",
        "failed_requirements": failed,
        "requirements": requirements,
        "artifact_checks": artifact_checks,
        "manifest_sha256": sha256_file(manifest_path) if manifest_path.exists() else "",
        "expected_cell_sha256": rows_sha256([dict(expected)]),
    }


def _check(name: str, passed: bool, *, severity: str = "error", detail: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# Public benchmark result-completeness audit v1",
        "",
        f"Generated: {audit['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{audit['status']}`",
        f"- Result completeness gate: `{audit['result_completeness_gate']}`",
        f"- Expected cells: {audit['expected_cell_count']}",
        f"- Complete cells: {audit['complete_cell_count']}",
        f"- Missing/incomplete cells: {audit['missing_or_incomplete_cell_count']}",
        f"- Initialized cells: {audit['initialized_cell_count']}",
        f"- Uninitialized cells: {audit['uninitialized_cell_count']}",
        f"- Expected case-runs: {audit['expected_case_runs']}",
        f"- Complete case-runs: {audit['complete_case_runs']}",
        f"- Result eligible for formal tables: `{audit['result_eligible_for_formal_tables']}`",
        "",
        "## Manifest status counts",
        "",
        "| Manifest status | Cells |",
        "|---|---:|",
    ]
    for status, count in audit["summary"]["manifest_status_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
        "## Missing or incomplete cells by benchmark",
        "",
        "| Benchmark | Missing/incomplete cells |",
        "|---|---:|",
        ]
    )
    for benchmark, count in audit["summary"]["missing_or_incomplete_by_benchmark"].items():
        lines.append(f"| `{benchmark}` | {count} |")
    lines.extend(["", "## Checks", "", "| Check | Status | Severity | Detail |", "|---|---|---|---|"])
    for check in audit["checks"]:
        detail = json.dumps(check.get("detail"), ensure_ascii=False, sort_keys=True)
        if len(detail) > 220:
            detail = detail[:217] + "..."
        lines.append(
            f"| `{check['name']}` | `{check['status']}` | `{check['severity']}` | {detail.replace('|', '\\|')} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            audit["boundary"],
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_public_benchmark_result_completeness_audit(
    *,
    freeze_manifest_path: Path = DEFAULT_FREEZE,
    result_root: Path = DEFAULT_RESULT_ROOT,
    output_dir: Path = DEFAULT_OUTPUT,
    audit_version: str = AUDIT_VERSION,
    audit_stem: str = AUDIT_STEM,
) -> dict[str, Any]:
    freeze_manifest_path = freeze_manifest_path.resolve()
    result_root = result_root.resolve()
    output_dir = output_dir.resolve()
    freeze = _read_json(freeze_manifest_path)
    expected_cells = freeze.get("ready_local_job_matrix_summary")
    if not isinstance(expected_cells, list):
        raise ValueError("freeze manifest missing ready_local_job_matrix_summary list")
    cell_rows = [
        _audit_cell(dict(row), result_root)
        for row in expected_cells
        if isinstance(row, Mapping)
    ]
    complete = [row for row in cell_rows if row["formal_cell_status"] == "complete"]
    incomplete = [row for row in cell_rows if row["formal_cell_status"] != "complete"]
    initialized = [row for row in cell_rows if row["manifest_exists"]]
    uninitialized = [row for row in cell_rows if not row["manifest_exists"]]
    manifest_status_counts: dict[str, int] = {}
    for row in cell_rows:
        manifest_path = Path(str(row["manifest_path"]))
        status = "missing_manifest"
        if manifest_path.exists():
            try:
                status = str(_read_json(manifest_path).get("status", "missing_status"))
            except Exception:
                status = "unreadable_manifest"
        manifest_status_counts[status] = manifest_status_counts.get(status, 0) + 1
    missing_or_incomplete_by_benchmark: dict[str, int] = {}
    for row in incomplete:
        benchmark = str(row.get("benchmark", ""))
        missing_or_incomplete_by_benchmark[benchmark] = (
            missing_or_incomplete_by_benchmark.get(benchmark, 0) + 1
        )
    expected_case_runs = sum(int(row["expected_case_runs"]) for row in cell_rows)
    complete_case_runs = sum(int(row["expected_case_runs"]) for row in complete)
    duplicate_cell_ids = sorted(
        cell_id
        for cell_id in {str(row["cell_id"]) for row in cell_rows}
        if sum(str(row["cell_id"]) == cell_id for row in cell_rows) > 1
    )
    result_gate = "satisfied" if len(complete) == len(cell_rows) and cell_rows else "not_satisfied"
    checks = [
        _check(
            "freeze_manifest_loaded",
            freeze_manifest_path.exists() and freeze.get("status") == "completed",
            detail={"path": str(freeze_manifest_path), "status": freeze.get("status")},
        ),
        _check(
            "expected_cells_declared",
            bool(cell_rows),
            detail={"expected_cell_count": len(cell_rows)},
        ),
        _check(
            "expected_cell_ids_unique",
            not duplicate_cell_ids,
            detail=duplicate_cell_ids,
        ),
        _check(
            "result_gate_satisfied_only_when_all_cells_complete",
            (result_gate == "satisfied") == (len(complete) == len(cell_rows) and bool(cell_rows)),
            detail={
                "result_gate": result_gate,
                "complete_cells": len(complete),
                "expected_cells": len(cell_rows),
            },
        ),
        _check(
            "incomplete_cells_not_result_eligible",
            result_gate == "not_satisfied" or not incomplete,
            severity="warning",
            detail={
                "missing_or_incomplete_cell_count": len(incomplete),
                "result_gate": result_gate,
            },
        ),
    ]
    error_failures = [
        check
        for check in checks
        if check["status"] != "pass" and check.get("severity") == "error"
    ]
    audit = {
        "schema_version": "paper-public-benchmark-result-completeness-audit-1.0",
        "audit_version": audit_version,
        "status": "completed" if not error_failures else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "freeze_manifest_path": str(freeze_manifest_path),
        "freeze_manifest_sha256": sha256_file(freeze_manifest_path),
        "result_root": str(result_root),
        "result_root_exists": result_root.exists(),
        "expected_cell_count": len(cell_rows),
        "complete_cell_count": len(complete),
        "missing_or_incomplete_cell_count": len(incomplete),
        "initialized_cell_count": len(initialized),
        "uninitialized_cell_count": len(uninitialized),
        "expected_case_runs": expected_case_runs,
        "complete_case_runs": complete_case_runs,
        "result_completeness_gate": result_gate,
        "result_eligible_for_formal_tables": result_gate == "satisfied",
        "summary": {
            "missing_or_incomplete_by_benchmark": dict(
                sorted(missing_or_incomplete_by_benchmark.items())
            ),
            "manifest_status_counts": dict(sorted(manifest_status_counts.items())),
            "complete_by_benchmark": {
                benchmark: sum(1 for row in complete if row.get("benchmark") == benchmark)
                for benchmark in sorted({str(row.get("benchmark", "")) for row in cell_rows})
            },
            "required_artifacts_per_cell": list(REQUIRED_ARTIFACTS),
        },
        "cells": cell_rows,
        "cells_sha256": rows_sha256(cell_rows),
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "total_checks": len(checks),
        "passed_checks": sum(1 for check in checks if check["status"] == "pass"),
        "error_failures": error_failures,
        "boundary": (
            "Result-completeness audit only. It does not run public benchmarks "
            "or judge effect sizes. Formal claims may use public-benchmark "
            "results only when this gate is satisfied and the upstream freeze, "
            "strong-baseline readiness and statistical-analysis gates also pass."
        ),
        "freeze_manifest_identity": {
            "freeze_version": freeze.get("freeze_version"),
            "ready_local_job_matrix_sha256": freeze.get("ready_local_job_matrix_sha256"),
            "ready_local_job_matrix_case_runs": freeze.get("ready_local_job_matrix_case_runs"),
            "canonical_sha256": rows_sha256([{"freeze": canonical_json(freeze)}]),
        },
    }
    audit = portable_value(audit, root=ROOT)
    audit["cells_sha256"] = rows_sha256(audit["cells"])
    audit["checks_sha256"] = rows_sha256(audit["checks"])
    json_path = output_dir / f"{audit_stem}.json"
    md_path = output_dir / f"{audit_stem}.md"
    _write_json(json_path, audit)
    _write_markdown(md_path, audit)
    audit["json_path"] = portable_path(json_path, root=ROOT)
    audit["markdown_path"] = portable_path(md_path, root=ROOT)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-manifest", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--result-root", type=Path, default=DEFAULT_RESULT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-version", default=AUDIT_VERSION)
    parser.add_argument("--audit-stem", default=AUDIT_STEM)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_public_benchmark_result_completeness_audit(
        freeze_manifest_path=args.freeze_manifest,
        result_root=args.result_root,
        output_dir=args.output_dir,
        audit_version=args.audit_version,
        audit_stem=args.audit_stem,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
