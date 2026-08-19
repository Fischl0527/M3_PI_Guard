"""Single-case subprocess worker for Progent v1.3.

This module is not a public batch runner.  The parent process supplies a
hash-bound specification, captures stdout/stderr, owns the 600-second hard
watchdog, and writes the terminal case manifest only after this worker seals
its trace.
"""

from __future__ import annotations

import argparse
import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, sha256_file
from .progent_source_backed_runtime_v13 import (
    PATCH_VERSION,
    ProgentV13Trace,
    build_progent_pipeline_v13,
)
from .run_agentdojo_official_detector_formal import (
    _execute_case,
    _read_json,
    _write_json,
    parse_agentdojo_case_id,
)
from .run_progent_source_backed_formal import _file_logger
from .strong_baseline_metric_semantics_v2 import (
    classify_operational_status,
    execution_grounded_slack5,
    metric_fields,
)


ROOT = Path(__file__).resolve().parents[3]
WORKER_VERSION = "m3-paper-v1-progent-v13-case-worker-1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seal_trace(
    *, trace: ProgentV13Trace, secagent: Any | None, worker_dir: Path, terminal: str
) -> dict[str, Any]:
    trace.record({"event": "trace_sealed", "terminal": terminal})
    snapshot = trace.snapshot(secagent)
    snapshot_path = worker_dir / "trace_snapshot.json"
    _write_json(snapshot_path, snapshot)
    return {
        "trace_event_path": portable_path(trace.event_path, root=ROOT),
        "trace_event_sha256": sha256_file(trace.event_path),
        "trace_snapshot_path": portable_path(snapshot_path, root=ROOT),
        "trace_snapshot_sha256": sha256_file(snapshot_path),
        "trace_event_count": len(trace.events),
        "trace_sealed": True,
        "progent_trace": snapshot,
    }


def run_worker(spec_path: Path) -> dict[str, Any]:
    spec = _read_json(spec_path)
    freeze_path = Path(str(spec["freeze_path"]))
    worker_dir = Path(str(spec["worker_dir"]))
    worker_dir.mkdir(parents=True, exist_ok=True)
    case_id = str(spec["benchmark_case_id"])
    parsed = parse_agentdojo_case_id(case_id)
    trace = ProgentV13Trace(worker_dir / "trace_events.jsonl")
    trace.start_case(suite=str(parsed["suite"]), case_id=case_id)
    started_at = _utc_now()
    started = time.perf_counter()
    pipeline: Any | None = None
    try:
        freeze = _read_json(freeze_path)
        pipeline = build_progent_pipeline_v13(
            freeze,
            trace_event_path=trace.event_path,
            case_id=case_id,
            suite=str(parsed["suite"]),
            trace=trace,
        )
        trace = pipeline.m3_progent_trace
        outcome = _execute_case(
            freeze=freeze,
            pipeline=pipeline,
            file_logger=_file_logger(worker_dir / "official_logs"),
            parsed=parsed,
            log_root=worker_dir / "official_logs",
        )
        official = (
            bool(outcome["security_success"])
            if parsed["case_kind"] == "security"
            else None
        )
        grounded = official
        if (
            parsed["case_kind"] == "security"
            and parsed["suite"] == "slack"
            and parsed["injection_task_id"] == "injection_task_5"
        ):
            grounded = execution_grounded_slack5(trace.tool_calls)
        metrics = metric_fields(
            case_kind=str(parsed["case_kind"]),
            operational_status="completed",
            official_injection_goal_achieved=official,
            execution_grounded_injection_goal_achieved=grounded,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
        trace_info = _seal_trace(
            trace=trace,
            secagent=pipeline.m3_progent_secagent,
            worker_dir=worker_dir,
            terminal="completed",
        )
        legacy = dict(outcome)
        legacy.pop("attack_success", None)
        legacy.pop("security_success", None)
        row = {
            "schema_version": "paper-progent-source-backed-case-1.3",
            "worker_version": WORKER_VERSION,
            "runtime_patch_version": PATCH_VERSION,
            "status": "completed",
            "case_kind": parsed["case_kind"],
            "benchmark_case_id": case_id,
            "suite": parsed["suite"],
            "user_task_id": parsed["user_task_id"],
            "injection_task_id": parsed["injection_task_id"],
            "started_at": started_at,
            "finished_at": _utc_now(),
            "duration_ms": elapsed_ms,
            **legacy,
            **metrics,
            **trace_info,
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
        operational_status = classify_operational_status(
            error_type=type(exc).__name__, failure_class=""
        )
        metrics = metric_fields(
            case_kind=str(parsed["case_kind"]),
            operational_status=operational_status,
            official_injection_goal_achieved=None,
        )
        trace.record(
            {
                "event": "worker_failure",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "operational_status": operational_status,
            }
        )
        trace_info = _seal_trace(
            trace=trace,
            secagent=(pipeline.m3_progent_secagent if pipeline is not None else None),
            worker_dir=worker_dir,
            terminal="failed",
        )
        row = {
            "schema_version": "paper-progent-source-backed-case-1.3",
            "worker_version": WORKER_VERSION,
            "runtime_patch_version": PATCH_VERSION,
            "status": "failed",
            "case_kind": parsed["case_kind"],
            "benchmark_case_id": case_id,
            "suite": parsed["suite"],
            "user_task_id": parsed["user_task_id"],
            "injection_task_id": parsed["injection_task_id"],
            "started_at": started_at,
            "finished_at": _utc_now(),
            "duration_ms": elapsed_ms,
            "utility_success": False,
            **metrics,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            **trace_info,
        }
    result_path = worker_dir / "worker_result.json"
    _write_json(result_path, row)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    row = run_worker(args.spec.resolve())
    print(json.dumps({"status": row["status"]}, ensure_ascii=False))
    return 0 if row["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
