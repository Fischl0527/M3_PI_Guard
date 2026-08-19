"""Run the frozen disclosed Task Shield paper reproduction on AgentDojo."""

from __future__ import annotations

import argparse
import json
import os
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import rows_sha256, sha256_file
from .formal_run_identity import validate_hash_bound_files, validate_resume_identity
from .run_agentdojo_official_detector_formal import (
    _aggregate_cases,
    _append_jsonl,
    _case_manifest_path,
    _execute_case,
    _load_existing_case,
    _ollama_probe,
    _read_json,
    _summary,
    _write_json,
    _write_jsonl,
    parse_agentdojo_case_id,
)
from .taskshield_paper_runtime import build_taskshield_pipeline


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_freeze_v1.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_paper_formal_v1"
RUNNER_VERSION = "m3-paper-v1-taskshield-paper-runner-1.1"
CONDITION_ID = "task_shield_paper_reproduction"


def _file_logger(log_root: Path):
    from agentdojo.logging import Logger

    class FileOnlyLogger(Logger):
        def __init__(self, target: Path) -> None:
            self.logdir = str(target.resolve())
            self.messages: list[Any] = []

        def log(self, messages, **kwargs) -> None:  # noqa: ANN001, ARG002
            self.messages = list(messages)

        def log_error(self, message: str) -> None:  # noqa: ARG002
            return None

    return FileOnlyLogger(log_root)


def _failure_row(parsed: Mapping[str, Any], case_id: str, index: int, exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": "paper-taskshield-case-1.0",
        "runner_version": RUNNER_VERSION,
        "status": "failed",
        "evidence_status": "taskshield_paper_diagnostic_case",
        "result_eligible_for_formal_tables": False,
        "case_index": index,
        "benchmark_case_id": case_id,
        "case_kind": parsed["case_kind"],
        "suite": parsed["suite"],
        "user_task_id": parsed["user_task_id"],
        "injection_task_id": parsed["injection_task_id"],
        "utility_success": False,
        "security_success": False if parsed["case_kind"] == "security" else None,
        "attack_success": parsed["case_kind"] == "security",
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback": traceback.format_exc(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def run(
    *,
    freeze_path: Path,
    output_dir: Path,
    case_limit: int | None,
    case_ids: list[str] | None,
    admit_formal: bool,
    resume: bool,
    retry_failed: bool,
) -> dict[str, Any]:
    freeze = _read_json(freeze_path)
    if freeze.get("status") != "completed_frozen_formal_protocol":
        raise ValueError("freeze is not completed")
    if freeze.get("condition_id") != CONDITION_ID:
        raise ValueError("unexpected condition")
    validate_hash_bound_files(freeze.get("local_adapter", {}))
    cases = list(freeze.get("case_rows", []))
    if rows_sha256(cases) != freeze.get("case_rows_sha256"):
        raise ValueError("freeze case hash mismatch")
    if case_ids:
        requested = set(case_ids)
        selected = [row for row in cases if str(row["benchmark_case_id"]) in requested]
        missing = requested - {str(row["benchmark_case_id"]) for row in selected}
        if missing or len(selected) != len(requested):
            raise ValueError("requested case IDs are absent or duplicated")
    else:
        selected = cases[:case_limit] if case_limit is not None else cases
    full_requested = len(selected) == len(cases)
    if admit_formal and not full_requested:
        raise ValueError("formal admission cannot be requested for a partial run")

    selected_case_rows_sha256 = rows_sha256(selected)
    validate_resume_identity(
        manifest_path=output_dir / "run_manifest.json",
        expected={
            "freeze_sha256": sha256_file(freeze_path),
            "runner_version": RUNNER_VERSION,
            "model_id": str(freeze["model_id"]),
            "condition_id": CONDITION_ID,
            "selected_cases": len(selected),
            "selected_case_rows_sha256": selected_case_rows_sha256,
        },
    )

    transport = freeze["transport"]
    base_url = str(transport["base_url"])
    os.environ["OPENAI_COMPATIBLE_BASE_URL"] = base_url
    os.environ["OPENAI_COMPATIBLE_API_KEY"] = "ollama-local"
    os.environ.setdefault("OLLAMA_MODELS", str(transport["ollama_models"]))
    service = _ollama_probe(base_url, str(freeze["model_id"]))
    if not service["model_present"]:
        raise ValueError("frozen model is not visible")

    output_dir.mkdir(parents=True, exist_ok=True)
    case_root = output_dir / "case_manifests"
    log_root = output_dir / "official_logs"
    progress_path = output_dir / "progress.jsonl"
    if not resume and progress_path.exists():
        raise ValueError("--no-resume requires a fresh output directory")
    started_at = datetime.now(timezone.utc).isoformat()
    pipeline = build_taskshield_pipeline(freeze)
    file_logger = _file_logger(log_root)

    for index, frozen in enumerate(selected, 1):
        case_id = str(frozen["benchmark_case_id"])
        existing = _load_existing_case(case_root=case_root, index=index, case_id=case_id, retry_failed=retry_failed) if resume else None
        if existing is not None:
            _append_jsonl(progress_path, {"index": index, "selected_cases": len(selected), "benchmark_case_id": case_id, "status": "resumed_" + str(existing.get("status", "unknown")), "created_at": datetime.now(timezone.utc).isoformat()})
            continue
        parsed = parse_agentdojo_case_id(case_id)
        progress = {"index": index, "selected_cases": len(selected), "benchmark_case_id": case_id, "case_kind": parsed["case_kind"], "suite": parsed["suite"], "created_at": datetime.now(timezone.utc).isoformat()}
        _append_jsonl(progress_path, {**progress, "status": "running"})
        try:
            outcome = _execute_case(freeze=freeze, pipeline=pipeline, file_logger=file_logger, parsed=parsed, log_root=log_root)
            outcome["taskshield_trace"] = pipeline.m3_taskshield_trace.snapshot()
            row = {
                "schema_version": "paper-taskshield-case-1.0",
                "runner_version": RUNNER_VERSION,
                "status": "completed",
                "evidence_status": "taskshield_paper_formal_case" if admit_formal else "taskshield_paper_diagnostic_case",
                "result_eligible_for_formal_tables": bool(admit_formal),
                "case_index": index,
                "benchmark_case_id": case_id,
                "case_kind": parsed["case_kind"],
                "suite": parsed["suite"],
                "user_task_id": parsed["user_task_id"],
                "injection_task_id": parsed["injection_task_id"],
                **outcome,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _write_json(_case_manifest_path(case_root, index, case_id), row)
            _append_jsonl(progress_path, {**progress, "status": "completed"})
        except Exception as exc:
            row = _failure_row(parsed, case_id, index, exc)
            _write_json(_case_manifest_path(case_root, index, case_id), row)
            _append_jsonl(progress_path, {**progress, "status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
        current = _aggregate_cases(case_root, selected)
        _write_jsonl(output_dir / "outcomes.jsonl", current)
        _write_json(output_dir / "run_manifest.json", {"schema_version": "paper-taskshield-run-manifest-1.1", "runner_version": RUNNER_VERSION, "status": "running", "started_at": started_at, "updated_at": datetime.now(timezone.utc).isoformat(), "pid": os.getpid(), "freeze_path": str(freeze_path.resolve()), "freeze_sha256": sha256_file(freeze_path), "output_dir": str(output_dir.resolve()), "service": service, "model_id": freeze["model_id"], "condition_id": freeze["condition_id"], "selected_cases": len(selected), "selected_case_rows_sha256": selected_case_rows_sha256, "formal_admission_requested": admit_formal, "resume": resume, "retry_failed": retry_failed, "summary": _summary(current, len(selected)), "result_eligible_for_formal_tables": False})

    rows = _aggregate_cases(case_root, selected)
    _write_jsonl(output_dir / "outcomes.jsonl", rows)
    summary = _summary(rows, len(selected))
    exact = full_requested and len(rows) == len(cases) and len({str(row.get("benchmark_case_id", "")) for row in rows}) == len(cases)
    no_failures = summary["failed_cases"] == 0
    admitted = bool(admit_formal and exact and no_failures)
    status = "completed_formal" if admitted else "completed_full_not_admitted" if full_requested and no_failures else "completed_full_with_failures" if full_requested else "completed_diagnostic_partial"
    manifest = {
        "schema_version": "paper-taskshield-run-manifest-1.1",
        "runner_version": RUNNER_VERSION,
        "status": status,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "freeze_path": str(freeze_path.resolve()),
        "freeze_sha256": sha256_file(freeze_path),
        "output_dir": str(output_dir.resolve()),
        "service": service,
        "model_id": freeze["model_id"],
        "condition_id": freeze["condition_id"],
        "task_shield": freeze["task_shield"],
        "case_limit": case_limit,
        "requested_case_ids": list(case_ids or []),
        "selected_cases": len(selected),
        "selected_case_rows_sha256": selected_case_rows_sha256,
        "formal_admission_requested": admit_formal,
        "summary": summary,
        "case_rows_sha256": rows_sha256(rows),
        "status_counts": dict(sorted(Counter(str(row.get("status", "")) for row in rows).items())),
        "outcomes_path": str((output_dir / "outcomes.jsonl").resolve()),
        "outcomes_sha256": sha256_file(output_dir / "outcomes.jsonl"),
        "progress_path": str(progress_path.resolve()),
        "progress_sha256": sha256_file(progress_path),
        "exact_frozen_coverage": exact,
        "result_eligible_for_formal_tables": admitted,
        "formal_admission_blockers": [name for name, present in [("formal_admission_not_requested", not admit_formal), ("partial_or_inexact_case_coverage", not exact), ("failed_cases_present", not no_failures)] if present],
        "boundary": "Formal eligibility requires explicit admission, exact 726-case coverage, complete official and verifier traces, and zero unexplained failures. The condition is a disclosed paper reproduction, never an official-source result.",
    }
    _write_json(output_dir / "run_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--admit-formal", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(freeze_path=args.freeze.resolve(), output_dir=args.output_dir.resolve(), case_limit=args.case_limit, case_ids=list(args.case_id), admit_formal=args.admit_formal, resume=not args.no_resume, retry_failed=args.retry_failed)
    print(json.dumps({"status": result["status"], "summary": result["summary"], "result_eligible": result["result_eligible_for_formal_tables"], "manifest": str((args.output_dir / "run_manifest.json").resolve())}, ensure_ascii=False))
    return 0 if result["status"] in {"completed_formal", "completed_diagnostic_partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
