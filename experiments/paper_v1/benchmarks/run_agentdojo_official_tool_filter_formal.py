"""Run the frozen official AgentDojo tool_filter condition.

The runner uses AgentDojo's upstream ``AgentPipeline.from_config`` path with
the official ``tool_filter`` defense.  It adds only experiment orchestration:
frozen-case selection, file-only logging, failure retention, resume support and
formal-admission checks.
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

from .common import portable_path, portable_value, rows_sha256, sha256_file
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
    ROOT / "protocols" / "paper_upgrade_v1" / "agentdojo_tool_filter_formal_freeze_v1.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_tool_filter_official_formal_v1"
)
RUNNER_VERSION = "m3-paper-v1-agentdojo-official-tool-filter-runner-1.1"
EXPECTED_FREEZE_STATUS = "completed_frozen_formal_protocol"
FORMAL_CASE_STATUS = "agentdojo_official_tool_filter_formal_case"
DIAGNOSTIC_CASE_STATUS = "agentdojo_official_tool_filter_diagnostic_case"


def _relative(path: Path) -> str:
    return portable_path(path, root=ROOT)


def _bind_openai_compatible_tool_filter_model(pipeline: Any, model_id: str) -> dict[str, Any]:
    """Bind AgentDojo's official tool-filter LLM to the frozen local model id.

    Upstream AgentDojo passes ``llm_name`` to ``OpenAILLMToolFilter``.  For normal
    OpenAI model enums, ``llm_name`` is a model name.  For the
    ``openai-compatible`` provider used by the local Ollama transport, it is the
    provider name, so the official filter would request a nonexistent model named
    ``openai-compatible``.  This shim changes only the OpenAI-compatible
    transport binding; it does not alter the filter prompt, tool-selection rule,
    temperature, pipeline order, tools, tasks or checkers.
    """

    rebound: list[dict[str, Any]] = []
    for index, element in enumerate(getattr(pipeline, "elements", [])):
        if type(element).__name__ != "OpenAILLMToolFilter":
            continue
        before = str(getattr(element, "model", ""))
        if before != model_id:
            setattr(element, "model", model_id)
            rebound.append(
                {
                    "element_index": index,
                    "class": type(element).__name__,
                    "model_before": before,
                    "model_after": model_id,
                }
            )
    return {
        "shim": "openai_compatible_tool_filter_model_binding",
        "reason": "upstream tool_filter receives provider name as llm_name for openai-compatible local transports",
        "algorithm_changed": False,
        "prompt_changed": False,
        "selection_rule_changed": False,
        "rebound_elements": rebound,
    }


def _build_pipeline(freeze: Mapping[str, Any], log_root: Path):
    checkout = Path(str(freeze["agentdojo"]["checkout"]))
    source = str((checkout / "src").resolve())
    if source not in sys.path:
        sys.path.insert(0, source)

    import agentdojo.attacks.baseline_attacks  # noqa: F401
    from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, PipelineConfig
    from agentdojo.logging import Logger
    from agentdojo.models import ModelsEnum

    class FileOnlyLogger(Logger):
        def __init__(self, target: Path) -> None:
            self.logdir = str(target.resolve())
            self.messages: list[Any] = []

        def log(self, messages, **kwargs) -> None:  # noqa: ANN001, ARG002
            self.messages = list(messages)

        def log_error(self, message: str) -> None:  # noqa: ARG002
            return None

    config = PipelineConfig(
        llm=ModelsEnum.OPENAI_COMPATIBLE,
        model_id=str(freeze["model_id"]),
        defense="tool_filter",
        tool_delimiter="tool",
        system_message_name=None,
        system_message=None,
        tool_output_format=str(freeze.get("tool_output_format", "yaml")),
    )
    pipeline = AgentPipeline.from_config(config)
    binding = _bind_openai_compatible_tool_filter_model(pipeline, str(freeze["model_id"]))
    setattr(pipeline, "m3_openai_compatible_tool_filter_binding", binding)
    return pipeline, FileOnlyLogger(log_root)


def _failure_row(
    *,
    parsed: Mapping[str, Any],
    case_id: str,
    index: int,
    exc: Exception,
) -> dict[str, Any]:
    return {
        "schema_version": "paper-agentdojo-official-tool-filter-case-1.0",
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
    case_limit: int | None,
    case_ids: list[str] | None,
    admit_formal: bool,
    resume: bool,
    retry_failed: bool,
    started_at: str,
    rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "paper-agentdojo-official-tool-filter-run-manifest-1.0",
        "runner_version": RUNNER_VERSION,
        "status": "running",
        "started_at": started_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "freeze_path": _relative(freeze_path),
        "freeze_sha256": sha256_file(freeze_path),
        "output_dir": _relative(output_dir),
        "service": dict(service),
        "model_id": freeze["model_id"],
        "condition_id": freeze["condition_id"],
        "case_limit": case_limit,
        "selected_cases": selected_count,
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
    if freeze.get("condition_id") != "agentdojo_tool_filter_official":
        raise ValueError("unexpected freeze condition: " + str(freeze.get("condition_id")))
    cases = list(freeze.get("case_rows", []))
    if rows_sha256(cases) != freeze.get("case_rows_sha256"):
        raise ValueError("freeze case_rows hash mismatch")
    if len(cases) != int(freeze.get("case_counts", {}).get("total", 0)):
        raise ValueError("freeze case count mismatch")
    if case_ids:
        requested = set(case_ids)
        selected = [row for row in cases if str(row["benchmark_case_id"]) in requested]
        missing_requested = requested - {str(row["benchmark_case_id"]) for row in selected}
        if missing_requested:
            raise ValueError(
                "requested case IDs are not in the freeze: " + ", ".join(sorted(missing_requested))
            )
        if len(selected) != len(requested):
            raise ValueError("requested case IDs are not unique")
    else:
        selected = cases[:case_limit] if case_limit is not None else cases
    full_requested = len(selected) == len(cases)
    if admit_formal and not full_requested:
        raise ValueError("formal admission cannot be requested for a partial run")

    transport = freeze["transport"]
    base_url = str(transport["base_url"])
    os.environ["OPENAI_COMPATIBLE_BASE_URL"] = base_url
    os.environ["OPENAI_COMPATIBLE_API_KEY"] = "ollama-local"
    os.environ.setdefault("OLLAMA_MODELS", str(transport["ollama_models"]))
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
    pipeline, file_logger = _build_pipeline(freeze, log_root)

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
        progress = {
            "index": index,
            "selected_cases": len(selected),
            "benchmark_case_id": case_id,
            "case_kind": parsed["case_kind"],
            "suite": parsed["suite"],
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
                "schema_version": "paper-agentdojo-official-tool-filter-case-1.0",
                "runner_version": RUNNER_VERSION,
                "status": "completed",
                "evidence_status": FORMAL_CASE_STATUS if admit_formal else DIAGNOSTIC_CASE_STATUS,
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
            row = _failure_row(parsed=parsed, case_id=case_id, index=index, exc=exc)
            _write_json(_case_manifest_path(case_root, index, case_id), row)
            _append_jsonl(
                progress_path,
                {**progress, "status": "failed", "error_type": type(exc).__name__, "error": str(exc)},
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
                case_limit=case_limit,
                case_ids=case_ids,
                admit_formal=admit_formal,
                resume=resume,
                retry_failed=retry_failed,
                started_at=started_at,
                rows=current_rows,
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
        "schema_version": "paper-agentdojo-official-tool-filter-run-manifest-1.0",
        "runner_version": RUNNER_VERSION,
        "status": status,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "freeze_path": _relative(freeze_path),
        "freeze_sha256": sha256_file(freeze_path),
        "output_dir": _relative(output_dir),
        "service": service,
        "model_id": freeze["model_id"],
        "condition_id": freeze["condition_id"],
        "attack_name": freeze["attack_name"],
        "tool_filter": freeze["tool_filter"],
        "openai_compatible_tool_filter_binding": dict(
            getattr(pipeline, "m3_openai_compatible_tool_filter_binding", {})
        ),
        "agentdojo": portable_value(freeze["agentdojo"], root=ROOT),
        "case_limit": case_limit,
        "selected_cases": len(selected),
        "requested_case_ids": list(case_ids or []),
        "formal_admission_requested": admit_formal,
        "resume": resume,
        "retry_failed": retry_failed,
        "summary": summary,
        "case_rows_sha256": rows_sha256(rows),
        "status_counts": dict(sorted(Counter(str(row.get("status", "")) for row in rows).items())),
        "outcomes_path": _relative(output_dir / "outcomes.jsonl"),
        "outcomes_sha256": sha256_file(output_dir / "outcomes.jsonl"),
        "progress_path": _relative(progress_path),
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
            "Formal eligibility requires explicit admission, exact coverage of all "
            "726 frozen cases, unique case IDs, complete official traces and zero "
            "unexplained failures. Partial/qualification runs remain diagnostic."
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
                "manifest": _relative(args.output_dir / "run_manifest.json"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] in {"completed_formal", "completed_diagnostic_partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
