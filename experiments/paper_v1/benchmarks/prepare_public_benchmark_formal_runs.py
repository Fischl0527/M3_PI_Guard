"""Prepare the frozen public-benchmark formal run ledger.

This module turns ``public_benchmark_formal_freeze_v1.json`` into an
on-disk, resume-safe run ledger:

* one immutable-ish cell directory per benchmark x model x condition;
* a pending ``manifest.json`` for cells that have not been run yet;
* a ``todo_cases.jsonl`` queue with every expected case-run;
* a protocol-side plan manifest and Markdown summary.

It deliberately does not start model services, run benchmarks, or mark any
result as eligible for formal tables.  Completed or running cell manifests are
preserved unless the caller explicitly asks for ``--force``.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .audit_public_benchmark_result_completeness import REQUIRED_ARTIFACTS
from .common import portable_path, portable_value, rows_sha256, sha256_file, write_jsonl


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = ROOT / "protocols" / "paper_upgrade_v1" / "public_benchmark_formal_freeze_v1.json"
DEFAULT_RESULT_ROOT = ROOT / "outputs" / "paper_upgrade_v1" / "public_benchmark_formal_runs"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
PLAN_VERSION = "m3-paper-v1-public-benchmark-formal-run-plan-1.0"
PLAN_STEM = "public_benchmark_formal_run_plan_v1"
PRESERVED_STATUSES = {"running", "completed", "formal_completed", "completed_with_failures"}
PLANNED_ARTIFACT_FILENAMES = {
    "raw_runs": "raw_runs.csv",
    "metrics": "metrics.csv",
    "statistics": "statistics.json",
    "figures": "figure_manifest.json",
}


def _path(path: Path) -> str:
    return portable_path(path, root=ROOT)


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


def _case_rows_for_benchmark(freeze: Mapping[str, Any], benchmark_id: str) -> list[dict[str, str]]:
    benchmarks = freeze.get("benchmarks", {})
    benchmark = benchmarks.get(benchmark_id, {}) if isinstance(benchmarks, Mapping) else {}
    if not isinstance(benchmark, Mapping):
        benchmark = {}
    utility = [
        {"case_kind": "utility", "benchmark_case_id": str(case_id)}
        for case_id in benchmark.get("utility_case_ids", [])
    ]
    security = [
        {"case_kind": "security", "benchmark_case_id": str(case_id)}
        for case_id in benchmark.get("security_case_ids", [])
    ]
    rows = utility + security
    expected = int(benchmark.get("total_case_count", len(rows)) or 0)
    if len(rows) != expected:
        raise ValueError(
            f"benchmark {benchmark_id} declares {expected} cases but exposes {len(rows)} case ids"
        )
    return rows


def _todo_rows(
    *,
    freeze: Mapping[str, Any],
    cell: Mapping[str, Any],
    cell_id: str,
) -> list[dict[str, Any]]:
    benchmark = str(cell.get("benchmark", ""))
    base_cases = _case_rows_for_benchmark(freeze, benchmark)
    repeats = int(cell.get("repeats", 1))
    rows: list[dict[str, Any]] = []
    for replicate_id in range(repeats):
        for case_index, case in enumerate(base_cases, 1):
            rows.append(
                {
                    "schema_version": "paper-public-benchmark-formal-case-todo-1.0",
                    "cell_id": cell_id,
                    "case_run_id": f"{cell_id}__{case['case_kind']}__{case_index:04d}__rep{replicate_id}",
                    "benchmark": benchmark,
                    "model": str(cell.get("model", "")),
                    "condition_id": str(cell.get("condition_id", "")),
                    "benchmark_case_id": case["benchmark_case_id"],
                    "case_kind": case["case_kind"],
                    "case_index": case_index,
                    "replicate_id": replicate_id,
                    "status": "pending",
                    "result_manifest_path": "manifest.json",
                }
            )
    expected = int(cell.get("case_runs", len(rows)) or 0)
    if len(rows) != expected:
        raise ValueError(
            f"cell {cell_id} declares {expected} case-runs but todo queue has {len(rows)}"
        )
    return rows


def _pending_cell_manifest(
    *,
    freeze: Mapping[str, Any],
    cell: Mapping[str, Any],
    cell_id: str,
    cell_dir: Path,
    todo_path: Path,
    todo_rows: list[dict[str, Any]],
    created_at: str,
    plan_version: str,
) -> dict[str, Any]:
    expected_case_count = int(cell.get("case_count", 0))
    expected_repeats = int(cell.get("repeats", 1))
    expected_case_runs = int(cell.get("case_runs", expected_case_count * expected_repeats))
    return {
        "schema_version": "paper-public-benchmark-formal-cell-1.0",
        "plan_version": plan_version,
        "status": "pending",
        "created_at": created_at,
        "updated_at": created_at,
        "cell_id": cell_id,
        "benchmark": str(cell.get("benchmark", "")),
        "model": str(cell.get("model", "")),
        "condition_id": str(cell.get("condition_id", "")),
        "repeats": expected_repeats,
        "case_count": expected_case_count,
        "case_runs": expected_case_runs,
        "completed_case_runs": 0,
        "failed_case_runs": 0,
        "missing_case_runs": expected_case_runs,
        "result_eligible_for_formal_tables": False,
        "cell_dir": _path(cell_dir),
        "todo_cases_path": todo_path.name,
        "todo_cases_sha256": rows_sha256(todo_rows),
        "expected_cell_sha256": rows_sha256([dict(cell)]),
        "freeze_manifest_identity": {
            "freeze_version": freeze.get("freeze_version"),
            "ready_local_job_matrix_sha256": freeze.get("ready_local_job_matrix_sha256"),
            "ready_local_job_matrix_case_runs": freeze.get("ready_local_job_matrix_case_runs"),
        },
        "planned_artifacts": {
            name: {"path": filename, "required_for_completion": True}
            for name, filename in PLANNED_ARTIFACT_FILENAMES.items()
        },
        "required_artifacts": list(REQUIRED_ARTIFACTS),
        "artifacts": {},
        "boundary": (
            "Pending formal-run cell. This manifest reserves the frozen cell "
            "identity and todo queue only; it contains no completed model "
            "outputs, metrics, statistics or figures."
        ),
    }


def _cell_action(
    *,
    existing_manifest: Mapping[str, Any] | None,
    expected_cell_sha256: str,
    force: bool,
) -> str:
    if existing_manifest is None:
        return "create_pending"
    status = str(existing_manifest.get("status", ""))
    existing_sha = str(existing_manifest.get("expected_cell_sha256", ""))
    if existing_sha and existing_sha != expected_cell_sha256:
        return "conflict"
    if force and status not in {"completed", "formal_completed"}:
        return "rewrite_pending"
    if status in PRESERVED_STATUSES:
        return "preserve_existing"
    return "preserve_existing"


def _write_markdown(path: Path, plan: Mapping[str, Any]) -> None:
    lines = [
        f"# Public benchmark formal run plan ({plan['plan_version']})",
        "",
        f"Generated: {plan['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{plan['status']}`",
        f"- Initialization gate: `{plan['initialization_gate']}`",
        f"- Result eligible for formal tables: `{plan['result_eligible_for_formal_tables']}`",
        f"- Expected cells: {plan['expected_cell_count']}",
        f"- Created pending cells: {plan['created_pending_cell_count']}",
        f"- Preserved existing cells: {plan['preserved_existing_cell_count']}",
        f"- Conflicted cells: {plan['conflict_cell_count']}",
        f"- Expected case-runs: {plan['expected_case_runs']}",
        f"- Todo case-runs written: {plan['todo_case_runs_written']}",
        "",
        "## Cell status counts",
        "",
        "| Status | Cells |",
        "|---|---:|",
    ]
    for status, count in plan["summary"]["cell_status_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
            "## Benchmark case-runs",
            "",
            "| Benchmark | Case-runs |",
            "|---|---:|",
        ]
    )
    for benchmark, count in plan["summary"]["case_runs_by_benchmark"].items():
        lines.append(f"| `{benchmark}` | {count} |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            plan["boundary"],
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def initialize_public_benchmark_formal_runs(
    *,
    freeze_manifest_path: Path = DEFAULT_FREEZE,
    result_root: Path = DEFAULT_RESULT_ROOT,
    output_dir: Path = DEFAULT_OUTPUT,
    force: bool = False,
    dry_run: bool = False,
    plan_version: str = PLAN_VERSION,
    plan_stem: str = PLAN_STEM,
) -> dict[str, Any]:
    freeze_manifest_path = freeze_manifest_path.resolve()
    result_root = result_root.resolve()
    output_dir = output_dir.resolve()
    freeze = _read_json(freeze_manifest_path)
    expected_cells = freeze.get("ready_local_job_matrix_summary")
    if not isinstance(expected_cells, list):
        raise ValueError("freeze manifest missing ready_local_job_matrix_summary list")
    created_at = datetime.now(timezone.utc).isoformat()
    cell_records: list[dict[str, Any]] = []
    queue_rows: list[dict[str, Any]] = []
    for raw_cell in expected_cells:
        if not isinstance(raw_cell, Mapping):
            continue
        cell = dict(raw_cell)
        cell_id = _cell_id(cell)
        cell_dir = result_root / "cells" / cell_id
        manifest_path = cell_dir / "manifest.json"
        todo_path = cell_dir / "todo_cases.jsonl"
        todo_rows = _todo_rows(freeze=freeze, cell=cell, cell_id=cell_id)
        expected_cell_sha256 = rows_sha256([cell])
        existing_manifest = _read_json(manifest_path) if manifest_path.exists() else None
        action = _cell_action(
            existing_manifest=existing_manifest,
            expected_cell_sha256=expected_cell_sha256,
            force=force,
        )
        status = (
            str(existing_manifest.get("status", ""))
            if existing_manifest is not None
            else "pending"
        )
        if action in {"create_pending", "rewrite_pending"}:
            status = "pending"
            if not dry_run:
                cell_dir.mkdir(parents=True, exist_ok=True)
                write_jsonl(todo_path, todo_rows)
                _write_json(
                    manifest_path,
                    _pending_cell_manifest(
                        freeze=freeze,
                        cell=cell,
                        cell_id=cell_id,
                        cell_dir=cell_dir,
                        todo_path=todo_path,
                        todo_rows=todo_rows,
                        created_at=created_at,
                        plan_version=plan_version,
                    ),
                )
        todo_sha = rows_sha256(todo_rows)
        queue_row = {
            "schema_version": "paper-public-benchmark-formal-cell-queue-1.0",
            "cell_id": cell_id,
            "benchmark": cell.get("benchmark"),
            "model": cell.get("model"),
            "condition_id": cell.get("condition_id"),
            "repeats": int(cell.get("repeats", 1)),
            "case_count": int(cell.get("case_count", 0)),
            "case_runs": int(cell.get("case_runs", 0)),
            "cell_dir": _path(cell_dir),
            "manifest_path": _path(manifest_path),
            "todo_cases_path": _path(todo_path),
            "todo_cases_sha256": todo_sha,
            "expected_cell_sha256": expected_cell_sha256,
            "action": action,
            "status_after_initialization": status,
            "result_eligible_for_formal_tables": False,
        }
        queue_rows.append(queue_row)
        cell_records.append(
            {
                **queue_row,
                "todo_case_runs": len(todo_rows),
                "manifest_exists_after_initialization": manifest_path.exists()
                if not dry_run
                else manifest_path.exists() or action in {"create_pending", "rewrite_pending"},
            }
        )
    conflicts = [row for row in cell_records if row["action"] == "conflict"]
    status_counts: dict[str, int] = {}
    case_runs_by_benchmark: dict[str, int] = {}
    for row in cell_records:
        status = str(row["status_after_initialization"])
        status_counts[status] = status_counts.get(status, 0) + 1
        benchmark = str(row["benchmark"])
        case_runs_by_benchmark[benchmark] = (
            case_runs_by_benchmark.get(benchmark, 0) + int(row["case_runs"])
        )
    expected_case_runs = sum(int(row["case_runs"]) for row in cell_records)
    todo_written = sum(
        int(row["todo_case_runs"])
        for row in cell_records
        if row["action"] in {"create_pending", "rewrite_pending"}
    )
    portable_cell_records = portable_value(cell_records, root=ROOT)
    portable_queue_rows = portable_value(queue_rows, root=ROOT)
    plan = {
        "schema_version": "paper-public-benchmark-formal-run-plan-1.0",
        "plan_version": plan_version,
        "status": "failed" if conflicts else "completed",
        "created_at": created_at,
        "freeze_manifest_path": _path(freeze_manifest_path),
        "freeze_manifest_sha256": sha256_file(freeze_manifest_path),
        "result_root": _path(result_root),
        "output_dir": _path(output_dir),
        "dry_run": dry_run,
        "force": force,
        "expected_cell_count": len(cell_records),
        "created_pending_cell_count": sum(
            1 for row in cell_records if row["action"] == "create_pending"
        ),
        "rewritten_pending_cell_count": sum(
            1 for row in cell_records if row["action"] == "rewrite_pending"
        ),
        "preserved_existing_cell_count": sum(
            1 for row in cell_records if row["action"] == "preserve_existing"
        ),
        "conflict_cell_count": len(conflicts),
        "expected_case_runs": expected_case_runs,
        "todo_case_runs_written": todo_written,
        "result_eligible_for_formal_tables": False,
        "initialization_gate": "satisfied" if not conflicts and bool(cell_records) else "not_satisfied",
        "summary": {
            "cell_status_counts": dict(sorted(status_counts.items())),
            "case_runs_by_benchmark": dict(sorted(case_runs_by_benchmark.items())),
            "required_artifacts_per_completed_cell": list(REQUIRED_ARTIFACTS),
        },
        "cells": portable_cell_records,
        "cells_sha256": rows_sha256(portable_cell_records),
        "queue_rows_sha256": rows_sha256(portable_queue_rows),
        "conflicts": portable_value(conflicts, root=ROOT),
        "boundary": (
            "Preparation ledger only. Pending cell manifests and todo queues "
            "do not contain model outputs and must remain ineligible for formal "
            "tables until raw runs, metrics, statistics and figure artifacts "
            "exist and the result-completeness audit passes."
        ),
        "freeze_manifest_identity": {
            "freeze_version": freeze.get("freeze_version"),
            "ready_local_job_matrix_sha256": freeze.get("ready_local_job_matrix_sha256"),
            "ready_local_job_matrix_case_runs": freeze.get("ready_local_job_matrix_case_runs"),
        },
    }
    json_path = output_dir / f"{plan_stem}.json"
    md_path = output_dir / f"{plan_stem}.md"
    root_manifest_path = result_root / "run_plan_manifest.json"
    queue_path = result_root / "formal_cell_queue.jsonl"
    if not dry_run:
        _write_json(json_path, plan)
        _write_markdown(md_path, plan)
        _write_json(root_manifest_path, plan)
        write_jsonl(queue_path, portable_queue_rows)
    plan["json_path"] = _path(json_path)
    plan["markdown_path"] = _path(md_path)
    plan["result_root_manifest_path"] = _path(root_manifest_path)
    plan["formal_cell_queue_path"] = _path(queue_path)
    return plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-manifest", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--result-root", type=Path, default=DEFAULT_RESULT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--plan-version", default=PLAN_VERSION)
    parser.add_argument("--plan-stem", default=PLAN_STEM)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = initialize_public_benchmark_formal_runs(
        freeze_manifest_path=args.freeze_manifest,
        result_root=args.result_root,
        output_dir=args.output_dir,
        force=args.force,
        dry_run=args.dry_run,
        plan_version=args.plan_version,
        plan_stem=args.plan_stem,
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if plan["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
