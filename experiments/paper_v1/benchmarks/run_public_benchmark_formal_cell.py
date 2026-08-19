"""Plan and ingest one frozen public-benchmark formal cell.

This wrapper is deliberately small and conservative.  It does not start
Ollama, AgentDojo, InjecAgent, or any model service by itself.  Its job is to
make one frozen cell executable in a paper-safe way:

1. load the cell manifest and todo queue;
2. expose a dry-run execution plan for the external/official runner;
3. convert supplied benchmark outcome rows into standardized
   ``case_results.jsonl`` rows;
4. optionally hand those rows to the formal cell materializer.

The formal evidence boundary is explicit: diagnostic outcomes remain
diagnostic even when the caller passes ``--admit-formal``.  Formal evidence is
only admitted when each source outcome already declares an accepted formal
source status and the caller explicitly opts in.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .common import sha256_file, write_jsonl
from .formal_case_result_rows import (
    build_case_result_rows,
    validate_case_result_rows,
)
from .materialize_public_benchmark_formal_cell import (
    DEFAULT_RESULT_ROOT,
    materialize_public_benchmark_formal_cell,
)


FORMAL_CELL_RUNNER_VERSION = "m3-paper-v1-public-benchmark-formal-cell-runner-1.0"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
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


def _cell_dir(result_root: Path, cell_id: str) -> Path:
    return result_root.resolve() / "cells" / cell_id


def _load_cell_context(
    *,
    cell_id: str,
    result_root: Path = DEFAULT_RESULT_ROOT,
) -> dict[str, Any]:
    result_root = result_root.resolve()
    cell_dir = _cell_dir(result_root, cell_id)
    manifest_path = cell_dir / "manifest.json"
    todo_path = cell_dir / "todo_cases.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError("cell manifest not found: " + str(manifest_path))
    if not todo_path.exists():
        raise FileNotFoundError("cell todo queue not found: " + str(todo_path))
    manifest = _read_json(manifest_path)
    if str(manifest.get("cell_id", "")) != cell_id:
        raise ValueError("cell_id does not match manifest")
    todo_rows = _read_jsonl(todo_path)
    return {
        "result_root": result_root,
        "cell_dir": cell_dir,
        "manifest_path": manifest_path,
        "todo_path": todo_path,
        "manifest": manifest,
        "todo_rows": todo_rows,
    }


def _todo_status_counts(todo_rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("status", "missing_status")) for row in todo_rows).items()))


def _case_kind_counts(todo_rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("case_kind", "missing_kind")) for row in todo_rows).items()))


def build_cell_execution_plan(
    *,
    cell_id: str,
    result_root: Path = DEFAULT_RESULT_ROOT,
    preview_limit: int = 5,
) -> dict[str, Any]:
    """Return a dry-run plan for one formal cell without running models."""

    context = _load_cell_context(cell_id=cell_id, result_root=result_root)
    manifest = context["manifest"]
    todo_rows = context["todo_rows"]
    cell_dir = context["cell_dir"]
    output_case_results_path = cell_dir / "case_results.jsonl"
    validation_output_path = cell_dir / "case_results_validation.json"
    return {
        "schema_version": "paper-public-benchmark-formal-cell-runner-plan-1.0",
        "runner_version": FORMAL_CELL_RUNNER_VERSION,
        "status": "planned",
        "dry_run": True,
        "cell_id": cell_id,
        "benchmark": str(manifest.get("benchmark", "")),
        "model": str(manifest.get("model", "")),
        "condition_id": str(manifest.get("condition_id", "")),
        "manifest_status": str(manifest.get("status", "")),
        "manifest_result_eligible_for_formal_tables": bool(
            manifest.get("result_eligible_for_formal_tables", False)
        ),
        "todo_case_runs": len(todo_rows),
        "case_kind_counts": _case_kind_counts(todo_rows),
        "todo_status_counts": _todo_status_counts(todo_rows),
        "paths": {
            "cell_dir": str(cell_dir),
            "manifest": str(context["manifest_path"]),
            "todo_cases": str(context["todo_path"]),
            "default_case_results": str(output_case_results_path),
            "default_validation": str(validation_output_path),
        },
        "todo_preview": todo_rows[: max(preview_limit, 0)],
        "execution_boundary": (
            "This plan does not launch model or benchmark services. Run the "
            "official benchmark runner separately, then feed its outcome JSONL "
            "back through this wrapper."
        ),
        "formal_boundary": (
            "Default conversion is diagnostic. Formal admission requires "
            "admit_formal=True and accepted formal source evidence on every "
            "source outcome; missing outcomes remain in the denominator."
        ),
    }


def _outcome_case_run_ids(outcome_rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("case_run_id", "")) for row in outcome_rows if row.get("case_run_id")}


def prepare_cell_case_results(
    *,
    cell_id: str,
    outcomes_path: Path,
    result_root: Path = DEFAULT_RESULT_ROOT,
    output_case_results_path: Path | None = None,
    admit_formal: bool = False,
    materialize: bool = False,
    force_materialize: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Convert supplied outcome rows into materializer-ready case results."""

    context = _load_cell_context(cell_id=cell_id, result_root=result_root)
    manifest = context["manifest"]
    todo_rows = context["todo_rows"]
    cell_dir = context["cell_dir"]
    outcomes_path = outcomes_path.resolve()
    if not outcomes_path.exists():
        raise FileNotFoundError("outcomes file not found: " + str(outcomes_path))
    output_case_results_path = (
        output_case_results_path.resolve()
        if output_case_results_path is not None
        else cell_dir / "case_results.jsonl"
    )
    validation_output_path = cell_dir / "case_results_validation.json"

    outcome_rows = _read_jsonl(outcomes_path)
    result_rows = build_case_result_rows(
        todo_rows,
        outcome_rows,
        admit_formal=admit_formal,
    )
    validation = validate_case_result_rows(todo_rows, result_rows)
    observed_outcome_ids = _outcome_case_run_ids(outcome_rows)
    expected_todo_ids = {str(row.get("case_run_id", "")) for row in todo_rows}
    conversion_summary = {
        "expected_case_run_count": len(todo_rows),
        "source_outcome_rows": len(outcome_rows),
        "standardized_result_rows": len(result_rows),
        "matched_source_outcome_rows": sum(
            1 for row in result_rows if str(row.get("source_outcome_sha256", ""))
        ),
        "missing_source_outcome_rows": sum(
            1 for row in result_rows if str(row.get("status", "")) == "missing"
        ),
        "unexpected_source_case_run_ids": sorted(observed_outcome_ids - expected_todo_ids),
        "coverage_ok": bool(validation["coverage_ok"]),
        "formal_ready": bool(validation["formal_ready"]),
        "admit_formal": admit_formal,
        "dry_run": dry_run,
    }

    case_results_sha256 = None
    validation_sha256 = None
    if not dry_run:
        write_jsonl(output_case_results_path, result_rows)
        case_results_sha256 = sha256_file(output_case_results_path)
        _write_json(validation_output_path, validation)
        validation_sha256 = sha256_file(validation_output_path)

    materialization: dict[str, Any] | None = None
    if materialize and not dry_run:
        materialization = materialize_public_benchmark_formal_cell(
            cell_id=cell_id,
            case_results_path=output_case_results_path,
            result_root=context["result_root"],
            force=force_materialize,
        )

    result_eligible = bool(
        materialization is not None
        and materialization.get("result_eligible_for_formal_tables", False)
    )
    status = "planned"
    if not dry_run:
        status = "case_results_written"
    if materialization is not None:
        status = "materialized_" + str(materialization.get("status", "unknown"))
    return {
        "schema_version": "paper-public-benchmark-formal-cell-runner-ingest-1.0",
        "runner_version": FORMAL_CELL_RUNNER_VERSION,
        "status": status,
        "cell_id": cell_id,
        "benchmark": str(manifest.get("benchmark", "")),
        "model": str(manifest.get("model", "")),
        "condition_id": str(manifest.get("condition_id", "")),
        "source_outcomes_path": str(outcomes_path),
        "source_outcomes_sha256": sha256_file(outcomes_path),
        "case_results_path": str(output_case_results_path),
        "case_results_sha256": case_results_sha256,
        "validation_path": str(validation_output_path),
        "validation_sha256": validation_sha256,
        "conversion_summary": conversion_summary,
        "validation": validation,
        "materialization": materialization,
        "result_eligible_for_formal_tables": result_eligible,
        "formal_boundary": (
            "This wrapper only standardizes and optionally materializes supplied "
            "outcomes. It does not create formal evidence from diagnostic/stub "
            "sources, and missing outcomes remain explicit failed rows."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--result-root", type=Path, default=DEFAULT_RESULT_ROOT)
    parser.add_argument("--outcomes", type=Path, default=None)
    parser.add_argument("--output-case-results", type=Path, default=None)
    parser.add_argument("--admit-formal", action="store_true")
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--force-materialize", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preview-limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.outcomes is None:
        result = build_cell_execution_plan(
            cell_id=args.cell_id,
            result_root=args.result_root,
            preview_limit=args.preview_limit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    result = prepare_cell_case_results(
        cell_id=args.cell_id,
        outcomes_path=args.outcomes,
        result_root=args.result_root,
        output_case_results_path=args.output_case_results,
        admit_formal=args.admit_formal,
        materialize=args.materialize,
        force_materialize=args.force_materialize,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.dry_run:
        return 0
    if args.materialize:
        return 0 if result["status"] == "materialized_completed" else 1
    return 0 if result["validation"]["coverage_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
