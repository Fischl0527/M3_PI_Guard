"""Run the frozen source-backed CaMeL AgentDojo condition.

The runner uses the pinned Google CaMeL interpreter, capability propagation,
suite security policies and the pinned AgentDojo public universe.  M3 adds only
the disclosed import-order compatibility preload, local OpenAI-compatible
model transport, frozen case selection, file-only logs, failure retention,
resume support and strict formal-admission checks.

Invoke this module with the isolated CaMeL Python environment.  A partial run
is qualification-only and can never be formally admitted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import resolve_artifact_path, rows_sha256, sha256_file
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


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_source_backed_formal_freeze_v2.json"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "camel_source_backed_formal_v2"
)
RUNNER_VERSION = "m3-paper-v1-camel-source-backed-formal-runner-1.2"
EXPECTED_FREEZE_STATUS = "completed_frozen_formal_protocol"
EXPECTED_CONDITION_ID = "camel_or_fides"
FORMAL_CASE_STATUS = "camel_source_backed_formal_case"
DIAGNOSTIC_CASE_STATUS = "camel_source_backed_diagnostic_case"


def _install_sources_and_compat(freeze: Mapping[str, Any]) -> dict[str, Any]:
    agentdojo_checkout = resolve_artifact_path(str(freeze["agentdojo"]["checkout"]), root=ROOT)
    camel_checkout = resolve_artifact_path(str(freeze["camel"]["checkout"]), root=ROOT)
    source_paths = [
        str((agentdojo_checkout / "src").resolve()),
        str((camel_checkout / "src").resolve()),
    ]
    for source in reversed(source_paths):
        if source not in sys.path:
            sys.path.insert(0, source)
    from .camel_agentdojo_compat import install_agentdojo_suite_import_compat

    compat = install_agentdojo_suite_import_compat()
    if not compat.get("ok"):
        raise RuntimeError("CaMeL AgentDojo compatibility preload failed")
    return {
        "compat_version": compat.get("compat_version", ""),
        "agentdojo_source": source_paths[0],
        "camel_source": source_paths[1],
        "suite_counts": compat.get("suite_counts", {}),
    }


def _verify_frozen_sources(freeze: Mapping[str, Any]) -> None:
    camel = freeze.get("camel", {})
    checkout = resolve_artifact_path(str(camel.get("checkout", "")), root=ROOT)
    source_hashes = camel.get("source_hashes", {})
    if not checkout.is_dir() or not isinstance(source_hashes, Mapping):
        raise ValueError("frozen CaMeL checkout/source hashes are missing")
    mismatches = []
    for relpath, expected in source_hashes.items():
        path = checkout / str(relpath)
        observed = sha256_file(path) if path.exists() else ""
        if observed != str(expected):
            mismatches.append(
                {"path": str(relpath), "expected": str(expected), "observed": observed}
            )
    if mismatches:
        raise ValueError("frozen CaMeL source hash mismatch: " + json.dumps(mismatches))
    mapping = camel.get("transport_mapping_preflight", "")
    mapping_sha = str(camel.get("transport_mapping_preflight_sha256", ""))
    mapping_path = resolve_artifact_path(str(mapping), root=ROOT)
    if not mapping_path.is_file() or sha256_file(mapping_path) != mapping_sha:
        raise ValueError("frozen CaMeL transport/mapping preflight hash mismatch")


def _build_pipelines(
    freeze: Mapping[str, Any],
    log_root: Path,
) -> tuple[dict[str, Any], Any, dict[str, Any]]:
    source_binding = _install_sources_and_compat(freeze)
    from agentdojo.logging import Logger

    from .camel_source_backed_runner import (
        SUPPORTED_SUITES,
        build_camel_source_backed_pipeline,
    )

    class FileOnlyLogger(Logger):
        def __init__(self, target: Path) -> None:
            self.logdir = str(target.resolve())
            self.messages: list[Any] = []

        def log(self, messages, **kwargs) -> None:  # noqa: ANN001, ARG002
            self.messages = list(messages)

        def log_error(self, message: str) -> None:  # noqa: ARG002
            return None

    transport = dict(freeze["transport"])
    base_url = str(transport["base_url"])
    os.environ["OPENAI_BASE_URL"] = base_url
    os.environ["OPENAI_API_KEY"] = str(transport.get("api_key", "ollama-local"))
    os.environ["OPENAI_COMPATIBLE_BASE_URL"] = base_url
    os.environ["OPENAI_COMPATIBLE_API_KEY"] = str(
        transport.get("api_key", "ollama-local")
    )
    os.environ.setdefault("OLLAMA_MODELS", str(transport["ollama_models"]))
    pipelines: dict[str, Any] = {}
    bindings: dict[str, Any] = {}
    for suite in SUPPORTED_SUITES:
        pipeline, binding = build_camel_source_backed_pipeline(
            suite=suite,
            transport=transport,
            privileged_model_id=str(transport["privileged_model_id"]),
            quarantined_model_id=str(transport["quarantined_model_id"]),
            temperature=float(transport["privileged_temperature"]),
        )
        pipelines[suite] = pipeline
        bindings[suite] = binding.as_dict()
    return pipelines, FileOnlyLogger(log_root), {
        "source_binding": source_binding,
        "transport_bindings": bindings,
    }


def _failure_row(
    *,
    parsed: Mapping[str, Any],
    case_id: str,
    index: int,
    exc: Exception,
) -> dict[str, Any]:
    return {
        "schema_version": "paper-camel-source-backed-case-1.0",
        "runner_version": RUNNER_VERSION,
        "status": "failed",
        "evidence_status": DIAGNOSTIC_CASE_STATUS,
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


def _running_manifest(
    *,
    freeze_path: Path,
    output_dir: Path,
    service: Mapping[str, Any],
    freeze: Mapping[str, Any],
    selected_count: int,
    selected_case_rows_sha256: str,
    case_limit: int | None,
    case_ids: list[str] | None,
    admit_formal: bool,
    resume: bool,
    retry_failed: bool,
    started_at: str,
    rows: list[Mapping[str, Any]],
    runtime_binding: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "paper-camel-source-backed-run-manifest-1.0",
        "runner_version": RUNNER_VERSION,
        "status": "running",
        "started_at": started_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "python_executable": sys.executable,
        "freeze_path": str(freeze_path.resolve()),
        "freeze_sha256": sha256_file(freeze_path),
        "output_dir": str(output_dir.resolve()),
        "service": dict(service),
        "model_id": freeze["model_id"],
        "condition_id": freeze["condition_id"],
        "runtime_binding": dict(runtime_binding),
        "case_limit": case_limit,
        "selected_cases": selected_count,
        "selected_case_rows_sha256": selected_case_rows_sha256,
        "requested_case_ids": list(case_ids or []),
        "formal_admission_requested": admit_formal,
        "resume": resume,
        "retry_failed": retry_failed,
        "summary": _summary(rows, selected_count),
        "result_eligible_for_formal_tables": False,
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
    if freeze.get("status") != EXPECTED_FREEZE_STATUS:
        raise ValueError("freeze is not completed: " + str(freeze.get("status")))
    if freeze.get("condition_id") != EXPECTED_CONDITION_ID:
        raise ValueError("unexpected freeze condition: " + str(freeze.get("condition_id")))
    _verify_frozen_sources(freeze)
    cases = list(freeze.get("case_rows", []))
    if rows_sha256(cases) != freeze.get("case_rows_sha256"):
        raise ValueError("freeze case_rows hash mismatch")
    if len(cases) != int(freeze.get("case_counts", {}).get("total", 0)):
        raise ValueError("freeze case count mismatch")
    if case_ids:
        requested = set(case_ids)
        selected = [row for row in cases if str(row["benchmark_case_id"]) in requested]
        missing = requested - {str(row["benchmark_case_id"]) for row in selected}
        if missing:
            raise ValueError("requested case IDs are not in the freeze: " + ", ".join(sorted(missing)))
        if len(selected) != len(requested):
            raise ValueError("requested case IDs are not unique")
    else:
        selected = cases[:case_limit] if case_limit is not None else cases
    full_requested = len(selected) == len(cases)
    if admit_formal and not full_requested:
        raise ValueError("formal admission cannot be requested for a partial run")

    validate_hash_bound_files(freeze.get("local_adapter", {}))
    selected_case_rows_sha256 = rows_sha256(selected)
    validate_resume_identity(
        manifest_path=output_dir / "run_manifest.json",
        expected={
            "freeze_sha256": sha256_file(freeze_path),
            "runner_version": RUNNER_VERSION,
            "model_id": freeze["model_id"],
            "condition_id": freeze["condition_id"],
            "selected_cases": len(selected),
            "selected_case_rows_sha256": selected_case_rows_sha256,
        },
    )

    transport = freeze["transport"]
    base_url = str(transport["base_url"])
    service = _ollama_probe(base_url, str(freeze["model_id"]))
    if not service["model_present"]:
        raise ValueError("frozen model is not visible in Ollama: " + str(freeze["model_id"]))

    output_dir.mkdir(parents=True, exist_ok=True)
    case_root = output_dir / "case_manifests"
    log_root = output_dir / "official_logs"
    progress_path = output_dir / "progress.jsonl"
    if not resume and progress_path.exists():
        raise ValueError("--no-resume requires a fresh output directory")
    started_at = datetime.now(timezone.utc).isoformat()
    pipelines, file_logger, runtime_binding = _build_pipelines(freeze, log_root)

    for index, frozen in enumerate(selected, 1):
        case_id = str(frozen["benchmark_case_id"])
        existing = (
            _load_existing_case(
                case_root=case_root,
                index=index,
                case_id=case_id,
                retry_failed=retry_failed,
            )
            if resume
            else None
        )
        if existing is not None:
            _append_jsonl(
                progress_path,
                {
                    "index": index,
                    "selected_cases": len(selected),
                    "benchmark_case_id": case_id,
                    "status": "resumed_" + str(existing.get("status", "unknown")),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            continue
        parsed = parse_agentdojo_case_id(case_id)
        if parsed["case_kind"] != frozen.get("case_kind"):
            raise ValueError("case kind mismatch in freeze: " + case_id)
        suite = str(parsed["suite"])
        pipeline = pipelines[suite]
        progress = {
            "index": index,
            "selected_cases": len(selected),
            "benchmark_case_id": case_id,
            "case_kind": parsed["case_kind"],
            "suite": suite,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _append_jsonl(progress_path, {**progress, "status": "running"})
        try:
            outcome = _execute_case(
                freeze=freeze,
                pipeline=pipeline,
                file_logger=file_logger,
                parsed=parsed,
                log_root=log_root,
            )
            row = {
                "schema_version": "paper-camel-source-backed-case-1.0",
                "runner_version": RUNNER_VERSION,
                "status": "completed",
                "evidence_status": FORMAL_CASE_STATUS if admit_formal else DIAGNOSTIC_CASE_STATUS,
                "result_eligible_for_formal_tables": bool(admit_formal),
                "case_index": index,
                "benchmark_case_id": case_id,
                "case_kind": parsed["case_kind"],
                "suite": suite,
                "user_task_id": parsed["user_task_id"],
                "injection_task_id": parsed["injection_task_id"],
                "camel_pipeline_name": pipeline.name,
                "camel_transport_binding": dict(
                    getattr(pipeline, "m3_camel_transport_binding", {})
                ),
                **outcome,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _write_json(_case_manifest_path(case_root, index, case_id), row)
            _append_jsonl(progress_path, {**progress, "status": "completed"})
        except Exception as exc:
            row = _failure_row(parsed=parsed, case_id=case_id, index=index, exc=exc)
            _write_json(_case_manifest_path(case_root, index, case_id), row)
            _append_jsonl(
                progress_path,
                {
                    **progress,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
        current_rows = _aggregate_cases(case_root, selected)
        _write_jsonl(output_dir / "outcomes.jsonl", current_rows)
        _write_json(
            output_dir / "run_manifest.json",
            _running_manifest(
                freeze_path=freeze_path,
                output_dir=output_dir,
                service=service,
                freeze=freeze,
                selected_count=len(selected),
                selected_case_rows_sha256=selected_case_rows_sha256,
                case_limit=case_limit,
                case_ids=case_ids,
                admit_formal=admit_formal,
                resume=resume,
                retry_failed=retry_failed,
                started_at=started_at,
                rows=current_rows,
                runtime_binding=runtime_binding,
            ),
        )

    rows = _aggregate_cases(case_root, selected)
    _write_jsonl(output_dir / "outcomes.jsonl", rows)
    summary = _summary(rows, len(selected))
    unique_ids = len({str(row.get("benchmark_case_id", "")) for row in rows}) == len(rows)
    exact_coverage = full_requested and len(rows) == len(cases) and unique_ids
    no_failures = summary["failed_cases"] == 0
    formally_admitted = bool(admit_formal and exact_coverage and no_failures)
    if formally_admitted:
        status = "completed_formal"
    elif full_requested and no_failures:
        status = "completed_full_not_admitted"
    elif full_requested:
        status = "completed_full_with_failures"
    else:
        status = "completed_diagnostic_partial"
    manifest = {
        "schema_version": "paper-camel-source-backed-run-manifest-1.1",
        "runner_version": RUNNER_VERSION,
        "status": status,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "python_executable": sys.executable,
        "freeze_path": str(freeze_path.resolve()),
        "freeze_sha256": sha256_file(freeze_path),
        "output_dir": str(output_dir.resolve()),
        "service": service,
        "model_id": freeze["model_id"],
        "condition_id": freeze["condition_id"],
        "attack_name": freeze["attack_name"],
        "camel": freeze["camel"],
        "agentdojo": freeze["agentdojo"],
        "runtime_binding": runtime_binding,
        "case_limit": case_limit,
        "selected_cases": len(selected),
        "selected_case_rows_sha256": selected_case_rows_sha256,
        "requested_case_ids": list(case_ids or []),
        "formal_admission_requested": admit_formal,
        "resume": resume,
        "retry_failed": retry_failed,
        "summary": summary,
        "case_rows_sha256": rows_sha256(rows),
        "status_counts": dict(sorted(Counter(str(row.get("status", "")) for row in rows).items())),
        "outcomes_path": str((output_dir / "outcomes.jsonl").resolve()),
        "outcomes_sha256": sha256_file(output_dir / "outcomes.jsonl"),
        "progress_path": str(progress_path.resolve()),
        "progress_sha256": sha256_file(progress_path),
        "exact_frozen_coverage": exact_coverage,
        "result_eligible_for_formal_tables": formally_admitted,
        "formal_admission_blockers": [
            blocker
            for blocker, present in [
                ("formal_admission_not_requested", not admit_formal),
                ("partial_or_inexact_case_coverage", not exact_coverage),
                ("failed_cases_present", not no_failures),
            ]
            if present
        ],
        "boundary": (
            "Formal eligibility requires execution with the isolated CaMeL runtime, "
            "the exact frozen source and transport bindings, all 726 unique cases, "
            "complete official traces, explicit admission and zero unexplained failures."
        ),
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
    result = run(
        freeze_path=args.freeze.resolve(),
        output_dir=args.output_dir.resolve(),
        case_limit=args.case_limit,
        case_ids=list(args.case_id),
        admit_formal=args.admit_formal,
        resume=not args.no_resume,
        retry_failed=args.retry_failed,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "summary": result["summary"],
                "result_eligible": result["result_eligible_for_formal_tables"],
                "manifest": str((args.output_dir / "run_manifest.json").resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] in {"completed_formal", "completed_diagnostic_partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
