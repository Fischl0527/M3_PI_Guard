"""Run or plan one AgentDojo frozen formal cell.

This module is the AgentDojo-specific source producer for the generic public
benchmark formal-cell wrapper.  It is intentionally conservative:

* the default mode is a dry-run plan and does not start models;
* partial runs, stub backends and failed jobs remain diagnostic;
* ``agentdojo_official_formal_case_run`` is emitted only when the caller
  explicitly requests formal source admission and the whole frozen cell was
  executed without failures under a non-stub backend.

The produced ``agentdojo_outcomes.jsonl`` can then be ingested by
``run_public_benchmark_formal_cell.py`` to create standardized case results and
cell artifacts.
"""

from __future__ import annotations

import argparse
import json
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .agentdojo_native_runner import DEFAULT_AGENTDOJO, run_agentdojo_native_smoke
from .common import sha256_file, write_jsonl
from .formal_case_result_rows import DIAGNOSTIC_EVIDENCE_STATUS
from .materialize_public_benchmark_formal_cell import DEFAULT_RESULT_ROOT
from .run_public_benchmark_formal_cell import prepare_cell_case_results


ROOT = Path(__file__).resolve().parents[3]
AGENTDOJO_FORMAL_CELL_RUNNER_VERSION = "m3-paper-v1-agentdojo-formal-cell-runner-1.0"
AGENTDOJO_FORMAL_SOURCE_STATUS = "agentdojo_official_formal_case_run"
AGENTDOJO_FORMAL_OUTCOME_SCHEMA = "paper-agentdojo-formal-source-outcome-1.0"


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


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


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


def _load_agentdojo_cell(
    *,
    cell_id: str,
    result_root: Path = DEFAULT_RESULT_ROOT,
) -> dict[str, Any]:
    cell_dir = _cell_dir(result_root, cell_id)
    manifest_path = cell_dir / "manifest.json"
    todo_path = cell_dir / "todo_cases.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError("cell manifest not found: " + str(manifest_path))
    if not todo_path.exists():
        raise FileNotFoundError("cell todo queue not found: " + str(todo_path))
    manifest = _read_json(manifest_path)
    todo_rows = _read_jsonl(todo_path)
    if str(manifest.get("cell_id", "")) != cell_id:
        raise ValueError("cell_id does not match manifest")
    if str(manifest.get("benchmark", "")) != "agentdojo":
        raise ValueError("cell is not an AgentDojo cell: " + str(manifest.get("benchmark")))
    for row in todo_rows:
        if str(row.get("benchmark", "")) != "agentdojo":
            raise ValueError("todo row is not AgentDojo: " + str(row.get("case_run_id", "")))
    return {
        "cell_dir": cell_dir,
        "manifest_path": manifest_path,
        "todo_path": todo_path,
        "manifest": manifest,
        "todo_rows": todo_rows,
        "result_root": result_root.resolve(),
    }


def parse_agentdojo_benchmark_case_id(case_id: str) -> dict[str, str | None]:
    """Parse frozen AgentDojo case ids.

    Utility ids have four components:
    ``agentdojo:v1:<suite>:<user_task_id>``.

    Security ids add the injection task:
    ``agentdojo:v1:<suite>:<user_task_id>:<injection_task_id>``.
    """

    parts = str(case_id).split(":")
    if len(parts) not in {4, 5} or parts[0] != "agentdojo":
        raise ValueError("not an AgentDojo benchmark_case_id: " + str(case_id))
    return {
        "benchmark": parts[0],
        "benchmark_version": parts[1],
        "suite": parts[2],
        "user_task_id": parts[3],
        "injection_task_id": parts[4] if len(parts) == 5 else None,
        "case_kind": "security" if len(parts) == 5 else "utility",
    }


def _default_output_dir(cell_dir: Path) -> Path:
    return cell_dir / "agentdojo_native_source"


def _record_from_existing_job(
    *,
    todo: Mapping[str, Any],
    job_dir: Path,
) -> dict[str, Any] | None:
    manifest_path = job_dir / "manifest.json"
    audit_path = job_dir / "audit.jsonl"
    failure_path = job_dir / "failure.json"
    if manifest_path.exists():
        native = _read_json(manifest_path)
        if str(native.get("status", "")) == "completed" and audit_path.exists():
            return {
                "todo": dict(todo),
                "manifest": {
                    **native,
                    "manifest_path": str(manifest_path.resolve()),
                    "audit_path": str(audit_path.resolve()),
                    "resume_source": "completed_manifest",
                },
                "audit_rows": _read_jsonl(audit_path),
                "resume_status": "resumed_completed",
            }
        if str(native.get("status", "")) == "completed":
            return {
                "todo": dict(todo),
                "manifest": {
                    "status": "failed",
                    "evidence_status": DIAGNOSTIC_EVIDENCE_STATUS,
                    "error_type": "MissingAuditLog",
                    "error": "completed manifest exists but audit.jsonl is missing",
                    "manifest_path": str(manifest_path.resolve()),
                    "audit_path": str(audit_path.resolve()),
                    "resume_source": "completed_manifest_missing_audit",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                "audit_rows": [],
                "resume_status": "resumed_failed_missing_audit",
            }
    if failure_path.exists():
        failure = _read_json(failure_path)
        return {
            "todo": dict(todo),
            "manifest": {
                **failure,
                "manifest_path": str(failure_path.resolve()),
                "audit_path": str(failure.get("audit_path", "")),
                "resume_source": "failure_manifest",
            },
            "audit_rows": [],
            "resume_status": "resumed_failed",
        }
    return None


def build_agentdojo_cell_run_plan(
    *,
    cell_id: str,
    result_root: Path = DEFAULT_RESULT_ROOT,
    output_dir: Path | None = None,
    case_limit: int | None = None,
    preview_limit: int = 5,
) -> dict[str, Any]:
    context = _load_agentdojo_cell(cell_id=cell_id, result_root=result_root)
    manifest = context["manifest"]
    todo_rows = context["todo_rows"]
    parsed_rows = [
        {**row, "agentdojo_case": parse_agentdojo_benchmark_case_id(str(row["benchmark_case_id"]))}
        for row in todo_rows
    ]
    selected_rows = parsed_rows[:case_limit] if case_limit is not None else parsed_rows
    output_dir = (output_dir.resolve() if output_dir else _default_output_dir(context["cell_dir"]))
    return {
        "schema_version": "paper-agentdojo-formal-cell-run-plan-1.0",
        "runner_version": AGENTDOJO_FORMAL_CELL_RUNNER_VERSION,
        "status": "planned",
        "dry_run": True,
        "cell_id": cell_id,
        "benchmark": "agentdojo",
        "model": str(manifest.get("model", "")),
        "condition_id": str(manifest.get("condition_id", "")),
        "total_todo_case_runs": len(todo_rows),
        "selected_case_runs": len(selected_rows),
        "case_limit": case_limit,
        "case_kind_counts": dict(
            sorted(Counter(str(row.get("case_kind", "")) for row in selected_rows).items())
        ),
        "suite_counts": dict(
            sorted(Counter(str(row["agentdojo_case"]["suite"]) for row in selected_rows).items())
        ),
        "paths": {
            "cell_dir": str(context["cell_dir"]),
            "todo_cases": str(context["todo_path"]),
            "output_dir": str(output_dir),
            "outcomes": str(output_dir / "agentdojo_outcomes.jsonl"),
            "execution_manifest": str(output_dir / "execution_manifest.json"),
        },
        "todo_preview": selected_rows[: max(preview_limit, 0)],
        "formal_source_boundary": (
            "This plan is not a result. Formal source rows require full-cell "
            "execution, a non-stub backend, zero failed jobs and explicit "
            "formal-source admission."
        ),
    }


def _last_guard_decision(audit_rows: list[dict[str, Any]]) -> str:
    for row in reversed(audit_rows):
        decision = row.get("guard_decision", "")
        if isinstance(decision, Mapping):
            value = decision.get("decision")
            if value:
                return str(value)
        if isinstance(decision, str) and decision:
            return decision
    return ""


def _all_parse_ok(audit_rows: list[dict[str, Any]], *, default: bool) -> bool:
    if not audit_rows:
        return default
    return all(bool(row.get("parse_ok", False)) for row in audit_rows)


def _sum_float(rows: list[dict[str, Any]], key: str) -> float | None:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return round(sum(values), 6) if values else None


def build_agentdojo_source_outcome_row(
    *,
    todo: Mapping[str, Any],
    native_manifest: Mapping[str, Any],
    audit_rows: list[dict[str, Any]] | None = None,
    formal_source_admitted: bool = False,
    formal_source_blockers: list[str] | None = None,
) -> dict[str, Any]:
    audit_rows = list(audit_rows or [])
    blockers = list(formal_source_blockers or [])
    status = str(native_manifest.get("status", "missing"))
    source_evidence = str(native_manifest.get("evidence_status", DIAGNOSTIC_EVIDENCE_STATUS))
    evidence_status = (
        AGENTDOJO_FORMAL_SOURCE_STATUS
        if formal_source_admitted and status == "completed" and not blockers
        else source_evidence
    )
    case_kind = str(todo.get("case_kind", ""))
    utility_success = bool(native_manifest.get("utility", False))
    official_injection_success = bool(
        native_manifest.get("official_injection_success", False)
    )
    return {
        "schema_version": AGENTDOJO_FORMAL_OUTCOME_SCHEMA,
        "runner_version": AGENTDOJO_FORMAL_CELL_RUNNER_VERSION,
        "case_run_id": str(todo.get("case_run_id", "")),
        "cell_id": str(todo.get("cell_id", "")),
        "benchmark": "agentdojo",
        "model": str(todo.get("model", native_manifest.get("model", ""))),
        "condition_id": str(todo.get("condition_id", native_manifest.get("defense_id", ""))),
        "benchmark_case_id": str(todo.get("benchmark_case_id", "")),
        "case_kind": case_kind,
        "case_index": int(todo.get("case_index", 0) or 0),
        "replicate_id": int(todo.get("replicate_id", 0) or 0),
        "status": status,
        "evidence_status": evidence_status,
        "source_evidence_status": source_evidence,
        "result_eligible_for_formal_tables": evidence_status == AGENTDOJO_FORMAL_SOURCE_STATUS,
        "source_result_eligible_for_formal_tables": bool(
            native_manifest.get("result_eligible_for_formal_tables", False)
        ),
        "formal_source_admitted": evidence_status == AGENTDOJO_FORMAL_SOURCE_STATUS,
        "formal_source_blockers": blockers,
        "utility_success": utility_success,
        "official_utility_success": utility_success,
        "attack_success": official_injection_success if case_kind == "security" else False,
        "official_injection_success": (
            official_injection_success if case_kind == "security" else False
        ),
        "guard_decision": _last_guard_decision(audit_rows),
        "parse_ok": _all_parse_ok(audit_rows, default=status == "completed"),
        "case_latency_ms": native_manifest.get("elapsed_ms"),
        "model_latency_ms": _sum_float(audit_rows, "model_latency_ms"),
        "guard_latency_ms": _sum_float(audit_rows, "guard_latency_ms"),
        "total_tokens": native_manifest.get("total_tokens"),
        "agentdojo_native_manifest_path": str(native_manifest.get("manifest_path", "")),
        "agentdojo_audit_path": str(native_manifest.get("audit_path", "")),
        "agentdojo_official_checker_fields": {
            "utility": utility_success,
            "security": native_manifest.get("security"),
            "official_injection_success": native_manifest.get("official_injection_success"),
        },
        "boundary": (
            "AgentDojo source outcome for formal-cell ingestion. The generic "
            "formal materializer still verifies exact frozen todo coverage and "
            "formal evidence status before any row can enter paper tables."
        ),
    }


def _formal_source_blockers(
    *,
    requested: bool,
    backend: str,
    selected_count: int,
    total_count: int,
    failed_jobs: int,
    status: str,
) -> list[str]:
    blockers: list[str] = []
    if not requested:
        blockers.append("formal_source_admission_not_requested")
    if str(backend).casefold() == "stub":
        blockers.append("stub_backend_not_formal")
    if selected_count != total_count:
        blockers.append("partial_cell_run_not_formal")
    if failed_jobs:
        blockers.append("failed_jobs_present")
    if status != "completed":
        blockers.append("execution_manifest_not_completed")
    return blockers


def build_agentdojo_source_outcomes_from_records(
    *,
    todo_rows: list[dict[str, Any]],
    native_records: list[dict[str, Any]],
    formal_source_admission: bool,
    backend: str,
    selected_count: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records_by_case_run = {str(record["todo"]["case_run_id"]): record for record in native_records}
    selected_count = selected_count if selected_count is not None else len(native_records)
    failed_jobs = sum(
        1 for record in native_records if str(record.get("manifest", {}).get("status", "")) != "completed"
    )
    execution_status = "completed" if failed_jobs == 0 and selected_count == len(todo_rows) else "completed_with_failures"
    blockers = _formal_source_blockers(
        requested=formal_source_admission,
        backend=backend,
        selected_count=selected_count,
        total_count=len(todo_rows),
        failed_jobs=failed_jobs,
        status=execution_status,
    )
    outcomes: list[dict[str, Any]] = []
    for todo in todo_rows:
        record = records_by_case_run.get(str(todo.get("case_run_id", "")))
        if record is None:
            continue
        outcomes.append(
            build_agentdojo_source_outcome_row(
                todo=todo,
                native_manifest=record.get("manifest", {}),
                audit_rows=record.get("audit_rows", []),
                formal_source_admitted=formal_source_admission,
                formal_source_blockers=blockers,
            )
        )
    summary = {
        "execution_status": execution_status,
        "formal_source_admission_requested": formal_source_admission,
        "formal_source_blockers": blockers,
        "formal_source_admitted": not blockers,
        "total_todo_case_runs": len(todo_rows),
        "selected_case_runs": selected_count,
        "native_records": len(native_records),
        "outcome_rows": len(outcomes),
        "failed_jobs": failed_jobs,
        "backend": backend,
    }
    return outcomes, summary


def run_agentdojo_formal_cell(
    *,
    cell_id: str,
    result_root: Path = DEFAULT_RESULT_ROOT,
    output_dir: Path | None = None,
    checkout: Path = DEFAULT_AGENTDOJO,
    backend: str = "ollama",
    temperature: float = 0.0,
    seed: int = 0,
    max_steps: int = 15,
    attack_name: str = "direct",
    case_limit: int | None = None,
    execute: bool = False,
    formal_source_admission: bool = False,
    ingest: bool = False,
    materialize: bool = False,
    force_materialize: bool = False,
    resume: bool = True,
    retry_failed: bool = False,
) -> dict[str, Any]:
    context = _load_agentdojo_cell(cell_id=cell_id, result_root=result_root)
    manifest = context["manifest"]
    todo_rows = context["todo_rows"]
    output_dir = output_dir.resolve() if output_dir else _default_output_dir(context["cell_dir"])
    if not execute:
        return build_agentdojo_cell_run_plan(
            cell_id=cell_id,
            result_root=context["result_root"],
            output_dir=output_dir,
            case_limit=case_limit,
        )
    selected_rows = todo_rows[:case_limit] if case_limit is not None else todo_rows
    native_records: list[dict[str, Any]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / "progress.jsonl"
    if not resume:
        progress_path.write_text("", encoding="utf-8")
    for index, todo in enumerate(selected_rows, 1):
        parsed = parse_agentdojo_benchmark_case_id(str(todo["benchmark_case_id"]))
        job_dir = output_dir / "jobs" / str(todo["case_run_id"])
        progress_base = {
            "schema_version": "paper-agentdojo-formal-cell-progress-1.0",
            "runner_version": AGENTDOJO_FORMAL_CELL_RUNNER_VERSION,
            "cell_id": cell_id,
            "case_run_id": str(todo["case_run_id"]),
            "case_index": index,
            "selected_case_runs": len(selected_rows),
            "benchmark_case_id": str(todo["benchmark_case_id"]),
            "case_kind": str(todo["case_kind"]),
            "resume": resume,
            "retry_failed": retry_failed,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if resume:
            existing = _record_from_existing_job(todo=todo, job_dir=job_dir)
            if existing is not None and (
                not str(existing["resume_status"]).startswith("resumed_failed")
                or not retry_failed
            ):
                native_records.append({"index": index, **existing})
                _append_jsonl(
                    progress_path,
                    {
                        **progress_base,
                        "status": existing["resume_status"],
                    },
                )
                continue
        _append_jsonl(progress_path, {**progress_base, "status": "running"})
        try:
            native = run_agentdojo_native_smoke(
                checkout=checkout,
                output_dir=job_dir,
                benchmark_version=str(parsed["benchmark_version"]),
                suite_name=str(parsed["suite"]),
                user_task_id=str(parsed["user_task_id"]),
                injection_task_id=(
                    str(parsed["injection_task_id"])
                    if parsed["injection_task_id"] is not None
                    else None
                ),
                attack_name=attack_name,
                defense_id=str(manifest["condition_id"]),
                backend=backend,
                model=str(manifest["model"]),
                temperature=temperature,
                seed=seed + int(todo.get("replicate_id", 0) or 0),
                max_steps=max_steps,
            )
            native = {
                **native,
                "manifest_path": str((job_dir / "manifest.json").resolve()),
                "audit_path": str((job_dir / "audit.jsonl").resolve()),
            }
            audit_rows = _read_jsonl(job_dir / "audit.jsonl")
            _append_jsonl(progress_path, {**progress_base, "status": "completed"})
        except Exception as exc:  # retain failures in source manifest
            failure = {
                "status": "failed",
                "evidence_status": DIAGNOSTIC_EVIDENCE_STATUS,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "manifest_path": str((job_dir / "failure.json").resolve()),
                "audit_path": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _write_json(job_dir / "failure.json", failure)
            native = failure
            audit_rows = []
            _append_jsonl(
                progress_path,
                {
                    **progress_base,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
        native_records.append({"index": index, "todo": dict(todo), "manifest": native, "audit_rows": audit_rows})

    outcome_rows, summary = build_agentdojo_source_outcomes_from_records(
        todo_rows=todo_rows,
        native_records=native_records,
        formal_source_admission=formal_source_admission,
        backend=backend,
        selected_count=len(selected_rows),
    )
    summary = {
        **summary,
        "resume_status_counts": dict(
            sorted(
                Counter(
                    str(record.get("resume_status", "executed"))
                    for record in native_records
                ).items()
            )
        ),
    }
    outcomes_path = output_dir / "agentdojo_outcomes.jsonl"
    write_jsonl(outcomes_path, outcome_rows)
    execution_manifest = {
        "schema_version": "paper-agentdojo-formal-cell-execution-manifest-1.0",
        "runner_version": AGENTDOJO_FORMAL_CELL_RUNNER_VERSION,
        "status": summary["execution_status"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cell_id": cell_id,
        "benchmark": "agentdojo",
        "model": str(manifest["model"]),
        "condition_id": str(manifest["condition_id"]),
        "checkout": str(checkout.resolve()),
        "backend": backend,
        "temperature": temperature,
        "seed": seed,
        "max_steps": max_steps,
        "attack_name": attack_name,
        "case_limit": case_limit,
        "resume": resume,
        "retry_failed": retry_failed,
        "summary": summary,
        "progress_path": str(progress_path),
        "progress_sha256": sha256_file(progress_path) if progress_path.exists() else "",
        "outcomes_path": str(outcomes_path),
        "outcomes_sha256": sha256_file(outcomes_path),
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Source execution manifest only. Formal paper eligibility is "
            "decided by the generic cell materializer after exact frozen todo "
            "coverage and formal evidence status validation."
        ),
    }
    _write_json(output_dir / "execution_manifest.json", execution_manifest)
    ingest_result = None
    if ingest or materialize:
        ingest_result = prepare_cell_case_results(
            cell_id=cell_id,
            outcomes_path=outcomes_path,
            result_root=context["result_root"],
            admit_formal=formal_source_admission,
            materialize=materialize,
            force_materialize=force_materialize,
        )
    return {
        **execution_manifest,
        "ingest_result": ingest_result,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--result-root", type=Path, default=DEFAULT_RESULT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--checkout", type=Path, default=DEFAULT_AGENTDOJO)
    parser.add_argument("--backend", choices=["ollama", "stub"], default="ollama")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--attack", default="direct")
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--admit-formal-source", action="store_true")
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--force-materialize", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_agentdojo_formal_cell(
        cell_id=args.cell_id,
        result_root=args.result_root,
        output_dir=args.output_dir,
        checkout=args.checkout,
        backend=args.backend,
        temperature=args.temperature,
        seed=args.seed,
        max_steps=args.max_steps,
        attack_name=args.attack,
        case_limit=args.case_limit,
        execute=args.execute,
        formal_source_admission=args.admit_formal_source,
        ingest=args.ingest,
        materialize=args.materialize,
        force_materialize=args.force_materialize,
        resume=not args.no_resume,
        retry_failed=args.retry_failed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not args.execute:
        return 0
    if args.materialize:
        ingest = result.get("ingest_result") or {}
        return 0 if ingest.get("status") == "materialized_completed" else 1
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
