"""Run fresh Task Shield v1.6 staged qualification on AgentDojo.

The runner is deliberately qualification-only.  It has no failed-case retry
mode, rejects non-empty output roots before probing Ollama, retains verifier
traces for every terminal row, and uses AgentDojo's raw ``security`` value as
``official_injection_success``/``attack_success``.
"""

from __future__ import annotations

import argparse
import _thread
import json
import os
import threading
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, rows_sha256, sha256_file
from .formal_run_identity import validate_hash_bound_files
from .run_agentdojo_official_detector_formal import (
    _aggregate_cases,
    _append_jsonl,
    _case_manifest_path,
    _execute_case,
    _ollama_probe,
    _read_json,
    _summary,
    _write_json,
    _write_jsonl,
    parse_agentdojo_case_id,
)
from .run_taskshield_paper_formal import _file_logger
from .taskshield_paper_runtime_v16 import (
    DEFAULT_CASE_TIMEOUT_SECONDS,
    PATCH_VERSION,
    TaskShieldCaseDeadlineExceeded,
    TaskShieldTransportTimeout,
    build_taskshield_pipeline_v16,
    runtime_contract,
    trace_snapshot,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_freeze_v16.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "taskshield_paper_qualification_v16_preflight"
)
RUNNER_VERSION = "m3-paper-v1-taskshield-paper-runner-1.6"
CONDITION_ID = "task_shield_paper_reproduction"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _classify_failure(exc: BaseException) -> str:
    if isinstance(exc, TaskShieldCaseDeadlineExceeded):
        return "case_timeout"
    if isinstance(exc, TaskShieldTransportTimeout):
        return "verifier_transport_timeout"
    from .taskshield_paper_runtime import TaskShieldVerifierError

    if isinstance(exc, TaskShieldVerifierError):
        return "verifier_contract_failure"
    return "benchmark_execution_failure"


class CaseWatchdog:
    """Interrupt the main thread when a case exceeds its frozen hard cap."""

    def __init__(self, seconds: float) -> None:
        if seconds <= 0:
            raise ValueError("watchdog seconds must be positive")
        self.seconds = float(seconds)
        self.expired = False
        self._timer = threading.Timer(self.seconds, self._expire)
        self._timer.daemon = True

    def _expire(self) -> None:
        self.expired = True
        _thread.interrupt_main()

    def __enter__(self) -> "CaseWatchdog":
        self._timer.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        self._timer.cancel()


def validate_fresh_output_root(output_dir: Path) -> None:
    """Reject any non-empty root; v1.6 never resumes or selectively retries."""

    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(
            "v1.6 requires a fresh empty output directory; resume and failed-row retry are forbidden"
        )


def _selection(freeze: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    key = {
        "preflight": "preflight_case_ids",
        "expanded": "qualification_case_ids",
    }.get(name)
    if key is None:
        raise ValueError("selection must be preflight or expanded")
    requested = [str(value) for value in freeze.get(key, [])]
    if not requested or len(requested) != len(set(requested)):
        raise ValueError(f"freeze {key} is absent or duplicated")
    by_id = {
        str(row["benchmark_case_id"]): dict(row)
        for row in freeze.get("case_rows", [])
        if isinstance(row, Mapping)
    }
    missing = [case_id for case_id in requested if case_id not in by_id]
    if missing:
        raise ValueError(f"freeze selection contains unknown cases: {missing}")
    return [by_id[case_id] for case_id in requested]


def validate_freeze_identity(
    *, freeze: Mapping[str, Any], freeze_path: Path, selection_name: str
) -> list[dict[str, Any]]:
    """Complete all static identity checks before any service/model probe."""

    if freeze.get("status") != "completed_frozen_formal_protocol":
        raise ValueError("v1.6 freeze is not completed")
    if freeze.get("schema_version") != "paper-taskshield-reproduction-freeze-1.6":
        raise ValueError("unexpected v1.6 freeze schema")
    if freeze.get("condition_id") != CONDITION_ID:
        raise ValueError("unexpected Task Shield condition")
    if freeze.get("v16_change_contract", {}).get("full_726_case_run_authorized") is not False:
        raise ValueError("v1.6 qualification freeze must not authorize the 726-case run")
    if not freeze_path.is_file():
        raise FileNotFoundError(freeze_path)
    validate_hash_bound_files(freeze.get("local_adapter", {}))
    cases = [dict(row) for row in freeze.get("case_rows", []) if isinstance(row, Mapping)]
    if rows_sha256(cases) != freeze.get("case_rows_sha256"):
        raise ValueError("freeze case hash mismatch")
    selected = _selection(freeze, selection_name)
    expected_hash = freeze.get(f"{selection_name}_case_rows_sha256")
    if rows_sha256(selected) != expected_hash:
        raise ValueError(f"{selection_name} selection hash mismatch")
    return selected


def _trace_path(trace_root: Path, index: int, case_id: str) -> Path:
    safe = case_id.replace(":", "__").replace("/", "_")
    return trace_root / f"{index:04d}_{safe}.json"


def _persist_trace(
    *, trace_root: Path, index: int, case_id: str, trace: Mapping[str, Any]
) -> tuple[str, str]:
    path = _trace_path(trace_root, index, case_id)
    _write_json(path, dict(trace))
    return portable_path(path, root=ROOT), sha256_file(path)


def _corrected_metric_fields(
    *, parsed: Mapping[str, Any], outcome: Mapping[str, Any]
) -> dict[str, Any]:
    if parsed["case_kind"] == "utility":
        return {
            "sample_type": "utility",
            "official_injection_success": None,
            "attack_success": None,
            "security_preserved": None,
            "legacy_attack_success": None,
            "metric_mapping_agreement": True,
        }
    official = bool(outcome["security_success"])
    return {
        "sample_type": "attack",
        "official_injection_success": official,
        "attack_success": official,
        "security_preserved": not official,
        "legacy_attack_success": not official,
        "metric_mapping_agreement": True,
    }


def _terminal_row(
    *,
    parsed: Mapping[str, Any],
    case_id: str,
    index: int,
    started_at: str,
    finished_at: str,
    duration_ms: float,
    trace: Mapping[str, Any],
    trace_path: str,
    trace_sha256: str,
    outcome: Mapping[str, Any] | None = None,
    exc: BaseException | None = None,
) -> dict[str, Any]:
    common = {
        "schema_version": "paper-taskshield-case-1.6",
        "metric_semantics_version": "agentdojo_official_v2",
        "runner_version": RUNNER_VERSION,
        "evidence_status": "taskshield_v16_qualification_case",
        "result_eligible_for_formal_tables": False,
        "case_index": index,
        "benchmark_case_id": case_id,
        "case_kind": parsed["case_kind"],
        "suite": parsed["suite"],
        "user_task_id": parsed["user_task_id"],
        "injection_task_id": parsed["injection_task_id"],
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": round(duration_ms, 6),
        "taskshield_trace": dict(trace),
        "taskshield_trace_path": trace_path,
        "taskshield_trace_sha256": trace_sha256,
        "runtime_patch_version": PATCH_VERSION,
        "case_retry_count": 0,
    }
    if exc is not None:
        return common | {
            "status": "failed",
            "sample_type": "attack" if parsed["case_kind"] == "security" else "utility",
            "utility_success": False,
            "official_injection_success": None,
            "attack_success": None,
            "security_preserved": None,
            "legacy_attack_success": None,
            "metric_mapping_agreement": False,
            "failure_class": _classify_failure(exc),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    assert outcome is not None
    metric_fields = _corrected_metric_fields(parsed=parsed, outcome=outcome)
    legacy_outcome = dict(outcome)
    legacy_outcome.pop("attack_success", None)
    return common | legacy_outcome | metric_fields | {"status": "completed"}


def run(
    *,
    freeze_path: Path,
    output_dir: Path,
    selection_name: str,
    case_timeout_seconds: float | None = None,
    admit_formal: bool = False,
) -> dict[str, Any]:
    if admit_formal:
        raise ValueError(
            "v1.6 P3/P4 is qualification-only; full formal execution requires separate authorization"
        )
    validate_fresh_output_root(output_dir)
    freeze = _read_json(freeze_path)
    selected = validate_freeze_identity(
        freeze=freeze,
        freeze_path=freeze_path,
        selection_name=selection_name,
    )
    case_timeout = float(
        case_timeout_seconds
        if case_timeout_seconds is not None
        else freeze["task_shield"].get("case_timeout_seconds", DEFAULT_CASE_TIMEOUT_SECONDS)
    )
    if case_timeout <= 0 or case_timeout > DEFAULT_CASE_TIMEOUT_SECONDS:
        raise ValueError("case timeout must be in (0, 600] seconds")

    # All static identity/fresh-root checks are complete before this service probe.
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
    trace_root = output_dir / "verifier_traces"
    log_root = output_dir / "official_logs"
    progress_path = output_dir / "progress.jsonl"
    started_at = _utc_now()
    pipeline = build_taskshield_pipeline_v16(freeze)
    file_logger = _file_logger(log_root)

    for index, frozen in enumerate(selected, 1):
        case_id = str(frozen["benchmark_case_id"])
        parsed = parse_agentdojo_case_id(case_id)
        pipeline.m3_taskshield_trace.reset()
        pipeline.m3_taskshield_verifier.set_case_deadline(case_timeout)
        case_started_at = _utc_now()
        case_started_clock = time.perf_counter()
        progress_common = {
            "index": index,
            "selected_cases": len(selected),
            "benchmark_case_id": case_id,
            "case_kind": parsed["case_kind"],
            "suite": parsed["suite"],
            "started_at": case_started_at,
        }
        _append_jsonl(progress_path, progress_common | {"status": "running"})
        try:
            with CaseWatchdog(case_timeout) as watchdog:
                try:
                    outcome = _execute_case(
                        freeze=freeze,
                        pipeline=pipeline,
                        file_logger=file_logger,
                        parsed=parsed,
                        log_root=log_root,
                    )
                except KeyboardInterrupt as interrupted:
                    if not watchdog.expired:
                        raise
                    raise TaskShieldCaseDeadlineExceeded(
                        f"case exceeded frozen hard cap of {case_timeout} seconds"
                    ) from interrupted
            elapsed_ms = (time.perf_counter() - case_started_clock) * 1000.0
            if elapsed_ms > case_timeout * 1000.0:
                raise TaskShieldCaseDeadlineExceeded(
                    f"case exceeded frozen hard cap of {case_timeout} seconds"
                )
            finished_at = _utc_now()
            trace = trace_snapshot(pipeline.m3_taskshield_trace)
            trace_path, trace_sha = _persist_trace(
                trace_root=trace_root,
                index=index,
                case_id=case_id,
                trace=trace,
            )
            row = _terminal_row(
                parsed=parsed,
                case_id=case_id,
                index=index,
                started_at=case_started_at,
                finished_at=finished_at,
                duration_ms=elapsed_ms,
                trace=trace,
                trace_path=trace_path,
                trace_sha256=trace_sha,
                outcome=outcome,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - case_started_clock) * 1000.0
            finished_at = _utc_now()
            trace = trace_snapshot(pipeline.m3_taskshield_trace)
            trace_path, trace_sha = _persist_trace(
                trace_root=trace_root,
                index=index,
                case_id=case_id,
                trace=trace,
            )
            row = _terminal_row(
                parsed=parsed,
                case_id=case_id,
                index=index,
                started_at=case_started_at,
                finished_at=finished_at,
                duration_ms=elapsed_ms,
                trace=trace,
                trace_path=trace_path,
                trace_sha256=trace_sha,
                exc=exc,
            )
        finally:
            pipeline.m3_taskshield_verifier.clear_case_deadline()

        _write_json(_case_manifest_path(case_root, index, case_id), row)
        _append_jsonl(
            progress_path,
            progress_common
            | {
                "status": row["status"],
                "finished_at": row["finished_at"],
                "duration_ms": row["duration_ms"],
                "failure_class": row.get("failure_class", ""),
                "taskshield_trace_path": row["taskshield_trace_path"],
                "taskshield_trace_sha256": row["taskshield_trace_sha256"],
            },
        )
        current = _aggregate_cases(case_root, selected)
        _write_jsonl(output_dir / "outcomes.jsonl", current)
        _write_json(
            output_dir / "run_manifest.json",
            {
                "schema_version": "paper-taskshield-run-manifest-1.6",
                "runner_version": RUNNER_VERSION,
                "status": "running",
                "started_at": started_at,
                "updated_at": _utc_now(),
                "pid": os.getpid(),
                "freeze_path": portable_path(freeze_path, root=ROOT),
                "freeze_sha256": sha256_file(freeze_path),
                "output_dir": portable_path(output_dir, root=ROOT),
                "model_id": freeze["model_id"],
                "condition_id": CONDITION_ID,
                "selection_name": selection_name,
                "selected_cases": len(selected),
                "selected_case_rows_sha256": rows_sha256(selected),
                "formal_admission_requested": False,
                "resume": False,
                "retry_failed": False,
                "summary": _summary(current, len(selected)),
                "result_eligible_for_formal_tables": False,
            },
        )

    rows = _aggregate_cases(case_root, selected)
    _write_jsonl(output_dir / "outcomes.jsonl", rows)
    summary = _summary(rows, len(selected))
    completed_at = _utc_now()
    exact = bool(
        len(rows) == len(selected)
        and len({str(row.get("benchmark_case_id", "")) for row in rows}) == len(selected)
    )
    manifest = {
        "schema_version": "paper-taskshield-run-manifest-1.6",
        "runner_version": RUNNER_VERSION,
        "status": "completed_qualification",
        "started_at": started_at,
        "completed_at": completed_at,
        "pid": os.getpid(),
        "freeze_path": portable_path(freeze_path, root=ROOT),
        "freeze_sha256": sha256_file(freeze_path),
        "output_dir": portable_path(output_dir, root=ROOT),
        "service": service,
        "model_id": freeze["model_id"],
        "condition_id": CONDITION_ID,
        "selection_name": selection_name,
        "runtime_contract": runtime_contract(),
        "selected_cases": len(selected),
        "selected_case_rows_sha256": rows_sha256(selected),
        "formal_admission_requested": False,
        "resume": False,
        "retry_failed": False,
        "summary": summary,
        "case_rows_sha256": rows_sha256(rows),
        "status_counts": dict(
            sorted(Counter(str(row.get("status", "")) for row in rows).items())
        ),
        "outcomes_path": portable_path(output_dir / "outcomes.jsonl", root=ROOT),
        "outcomes_sha256": sha256_file(output_dir / "outcomes.jsonl"),
        "progress_path": portable_path(progress_path, root=ROOT),
        "progress_sha256": sha256_file(progress_path),
        "exact_frozen_coverage": exact,
        "result_eligible_for_formal_tables": False,
        "formal_admission_blockers": [
            "v16_staged_qualification_is_not_formal_evidence",
            "full_726_case_run_requires_separate_authorization",
        ],
        "boundary": (
            "Fresh v1.6 P3/P4 qualification only. No row is formal evidence, no failed "
            "case is retried or excluded, and this manifest cannot authorize P6."
        ),
    }
    _write_json(output_dir / "run_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selection", choices=("preflight", "expanded"), default="preflight")
    parser.add_argument("--case-timeout-seconds", type=float, default=None)
    parser.add_argument("--admit-formal", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        freeze_path=args.freeze.resolve(),
        output_dir=args.output_dir.resolve(),
        selection_name=args.selection,
        case_timeout_seconds=args.case_timeout_seconds,
        admit_formal=args.admit_formal,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "summary": result["summary"],
                "result_eligible": result["result_eligible_for_formal_tables"],
                "manifest": portable_path(args.output_dir / "run_manifest.json", root=ROOT),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
