"""Run staged Progent v1.3 qualification with per-case process isolation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, rows_sha256, sha256_file
from .formal_run_identity import validate_hash_bound_files, validate_resume_identity
from .progent_source_backed_runtime_v13 import PATCH_VERSION, runtime_contract
from .run_agentdojo_official_detector_formal import (
    _aggregate_cases,
    _append_jsonl,
    _case_manifest_path,
    _ollama_probe,
    _read_json,
    _summary,
    _write_json,
    _write_jsonl,
    parse_agentdojo_case_id,
)
from .strong_baseline_metric_semantics_v2 import (
    METRIC_SEMANTICS_VERSION,
    metric_fields,
    summarize_attack_bounds,
    validate_metric_row,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "progent_source_backed_formal_freeze_v13.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "progent_source_backed_qualification_v13_p3"
)
RUNNER_VERSION = "m3-paper-v1-progent-source-backed-runner-1.3"
CONDITION_ID = "progent_source_backed"
CASE_WATCHDOG_SECONDS = 600.0
SELECTIONS = {"p3", "p4", "p5", "formal"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _selection(freeze: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    if name not in SELECTIONS:
        raise ValueError(f"unsupported selection: {name}")
    entry = freeze.get("selections", {}).get(name, {})
    requested = [str(value) for value in entry.get("case_ids", [])]
    if not requested or len(requested) != len(set(requested)):
        raise ValueError(f"freeze selection {name} is absent or duplicated")
    by_id = {
        str(row["benchmark_case_id"]): dict(row)
        for row in freeze.get("case_rows", [])
        if isinstance(row, Mapping)
    }
    missing = sorted(set(requested) - set(by_id))
    if missing:
        raise ValueError(f"freeze selection has unknown case IDs: {missing}")
    selected = [by_id[case_id] for case_id in requested]
    if rows_sha256(selected) != entry.get("case_rows_sha256"):
        raise ValueError(f"freeze selection {name} hash mismatch")
    return selected


def validate_freeze_identity(
    *, freeze: Mapping[str, Any], freeze_path: Path, selection_name: str
) -> list[dict[str, Any]]:
    if freeze.get("status") != "completed_frozen_formal_protocol":
        raise ValueError("Progent v1.3 freeze is not complete")
    if freeze.get("schema_version") != "paper-progent-source-backed-freeze-1.3":
        raise ValueError("unexpected Progent v1.3 freeze schema")
    if freeze.get("condition_id") != CONDITION_ID:
        raise ValueError("unexpected Progent condition")
    validate_hash_bound_files(freeze.get("local_adapter", {}))
    cases = [dict(row) for row in freeze.get("case_rows", []) if isinstance(row, Mapping)]
    if rows_sha256(cases) != freeze.get("case_rows_sha256"):
        raise ValueError("freeze case rows hash mismatch")
    if selection_name == "formal" and not freeze.get("formal_execution_authorized", False):
        raise ValueError("P6 formal execution requires a separately authorized freeze")
    return _selection(freeze, selection_name)


def validate_run_root(
    *,
    output_dir: Path,
    resume: bool,
    expected_identity: Mapping[str, Any],
) -> None:
    """Fail before service probe for stale or failed qualification roots."""

    manifest_path = output_dir / "run_manifest.json"
    if not output_dir.exists() or not any(output_dir.iterdir()):
        return
    if not resume:
        raise ValueError("--no-resume requires a fresh empty output directory")
    if not manifest_path.is_file():
        raise ValueError("non-empty resume root has no terminal identity manifest")
    validate_resume_identity(manifest_path=manifest_path, expected=expected_identity)
    manifests = sorted((output_dir / "case_manifests").glob("*.json"))
    failed = []
    for path in manifests:
        row = _read_json(path)
        if row.get("status") != "completed" or row.get("operational_status") != "completed":
            failed.append(str(row.get("benchmark_case_id", path.name)))
    if failed:
        raise ValueError(
            "failed Progent v1.3 root cannot resume; use a fresh revision/root: "
            + ", ".join(failed)
        )


def _read_trace_events(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _append_trace_event(path: Path, row: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _read_trace_events(path)
    event = {
        "sequence": len(rows) + 1,
        "created_at": _utc_now(),
        **dict(row),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return rows + [event]


def _parent_failure_row(
    *,
    worker_dir: Path,
    parsed: Mapping[str, Any],
    case_id: str,
    operational_status: str,
    error_type: str,
    error: str,
    started_at: str,
    duration_ms: float,
) -> dict[str, Any]:
    trace_path = worker_dir / "trace_events.jsonl"
    events = _append_trace_event(
        trace_path,
        {
            "event": "parent_terminal_failure",
            "operational_status": operational_status,
            "error_type": error_type,
            "error": error,
            "trace_sealed": True,
        },
    )
    snapshot = {
        "runtime_patch_version": PATCH_VERSION,
        "suite": parsed["suite"],
        "benchmark_case_id": case_id,
        "event_count": len(events),
        "events": events,
        "tool_calls": [row for row in events if row.get("event") == "tool_call"],
        "policy_transitions": [
            row for row in events if row.get("event") == "policy_transition"
        ],
        "terminal_owner": "parent_watchdog_or_worker_contract",
    }
    snapshot_path = worker_dir / "trace_snapshot.json"
    _write_json(snapshot_path, snapshot)
    metrics = metric_fields(
        case_kind=str(parsed["case_kind"]),
        operational_status=operational_status,
        official_injection_goal_achieved=None,
    )
    return {
        "schema_version": "paper-progent-source-backed-case-1.3",
        "runner_version": RUNNER_VERSION,
        "runtime_patch_version": PATCH_VERSION,
        "status": "failed",
        "case_kind": parsed["case_kind"],
        "benchmark_case_id": case_id,
        "suite": parsed["suite"],
        "user_task_id": parsed["user_task_id"],
        "injection_task_id": parsed["injection_task_id"],
        "started_at": started_at,
        "finished_at": _utc_now(),
        "duration_ms": round(duration_ms, 6),
        "utility_success": False,
        **metrics,
        "error_type": error_type,
        "error": error,
        "trace_event_path": portable_path(trace_path, root=ROOT),
        "trace_event_sha256": sha256_file(trace_path),
        "trace_snapshot_path": portable_path(snapshot_path, root=ROOT),
        "trace_snapshot_sha256": sha256_file(snapshot_path),
        "trace_event_count": len(events),
        "trace_sealed": True,
        "progent_trace": snapshot,
    }


def run_case_subprocess(
    *,
    freeze_path: Path,
    worker_dir: Path,
    case_id: str,
    watchdog_seconds: float,
) -> dict[str, Any]:
    """Execute one worker and return a trace-sealed terminal row."""

    if watchdog_seconds <= 0:
        raise ValueError("watchdog seconds must be positive")
    parsed = parse_agentdojo_case_id(case_id)
    worker_dir.mkdir(parents=True, exist_ok=True)
    spec = {
        "schema_version": "paper-progent-v13-worker-spec-1.0",
        "freeze_path": str(freeze_path.resolve()),
        "worker_dir": str(worker_dir.resolve()),
        "benchmark_case_id": case_id,
    }
    spec_path = worker_dir / "worker_spec.json"
    _write_json(spec_path, spec)
    stdout_path = worker_dir / "stdout.log"
    stderr_path = worker_dir / "stderr.log"
    started_at = _utc_now()
    started = time.perf_counter()
    command = [
        sys.executable,
        "-m",
        "experiments.paper_v1.benchmarks.progent_v13_case_worker",
        "--spec",
        str(spec_path),
    ]
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=stdout,
            stderr=stderr,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            return_code = process.wait(timeout=watchdog_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)
            return _parent_failure_row(
                worker_dir=worker_dir,
                parsed=parsed,
                case_id=case_id,
                operational_status="timeout",
                error_type="CaseWatchdogTimeout",
                error=f"case exceeded parent hard cap of {watchdog_seconds} seconds",
                started_at=started_at,
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )
    result_path = worker_dir / "worker_result.json"
    if not result_path.is_file():
        return _parent_failure_row(
            worker_dir=worker_dir,
            parsed=parsed,
            case_id=case_id,
            operational_status="runtime_failure",
            error_type="WorkerResultMissing",
            error=f"worker exited {return_code} without worker_result.json",
            started_at=started_at,
            duration_ms=(time.perf_counter() - started) * 1000.0,
        )
    row = _read_json(result_path)
    trace_path = ROOT / str(row.get("trace_event_path", ""))
    snapshot_path = ROOT / str(row.get("trace_snapshot_path", ""))
    trace_ok = bool(
        row.get("trace_sealed") is True
        and trace_path.is_file()
        and snapshot_path.is_file()
        and sha256_file(trace_path) == row.get("trace_event_sha256")
        and sha256_file(snapshot_path) == row.get("trace_snapshot_sha256")
    )
    if not trace_ok:
        return _parent_failure_row(
            worker_dir=worker_dir,
            parsed=parsed,
            case_id=case_id,
            operational_status="runtime_failure",
            error_type="WorkerTraceContractError",
            error="worker terminal row did not hash-bind a sealed trace",
            started_at=started_at,
            duration_ms=(time.perf_counter() - started) * 1000.0,
        )
    issues = validate_metric_row(row)
    if issues:
        return _parent_failure_row(
            worker_dir=worker_dir,
            parsed=parsed,
            case_id=case_id,
            operational_status="runtime_failure",
            error_type="WorkerMetricContractError",
            error="invalid metric fields: " + ", ".join(issues),
            started_at=started_at,
            duration_ms=(time.perf_counter() - started) * 1000.0,
        )
    return row


def _manifest(
    *,
    freeze_path: Path,
    output_dir: Path,
    freeze: Mapping[str, Any],
    selection_name: str,
    selected: list[Mapping[str, Any]],
    rows: list[Mapping[str, Any]],
    started_at: str,
    status: str,
    service: Mapping[str, Any],
    resume: bool,
    admit_formal: bool,
) -> dict[str, Any]:
    summary = _summary(rows, len(selected))
    exact = len(rows) == len(selected) and len(
        {str(row.get("benchmark_case_id")) for row in rows}
    ) == len(selected)
    zero_unresolved = all(
        row.get("operational_status") == "completed" for row in rows
    )
    formal = bool(
        selection_name == "formal"
        and admit_formal
        and freeze.get("formal_execution_authorized") is True
        and exact
        and zero_unresolved
        and len(rows) == 726
    )
    return {
        "schema_version": "paper-progent-source-backed-run-manifest-1.3",
        "runner_version": RUNNER_VERSION,
        "status": "completed_formal" if formal else status,
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
        "metric_semantics_version": METRIC_SEMANTICS_VERSION,
        "runtime_contract": runtime_contract(),
        "case_watchdog_seconds": CASE_WATCHDOG_SECONDS,
        "service": dict(service),
        "resume": resume,
        "retry_failed": False,
        "formal_admission_requested": admit_formal,
        "summary": summary,
        "attack_bounds": summarize_attack_bounds(rows),
        "status_counts": dict(
            sorted(Counter(str(row.get("status")) for row in rows).items())
        ),
        "operational_status_counts": dict(
            sorted(Counter(str(row.get("operational_status")) for row in rows).items())
        ),
        "case_rows_sha256": rows_sha256(rows),
        "exact_selected_coverage": exact,
        "zero_unresolved": zero_unresolved,
        "result_eligible_for_formal_tables": formal,
        "formal_admission_blockers": [
            blocker
            for blocker, present in (
                ("qualification_selection", selection_name != "formal"),
                ("formal_admission_not_requested", not admit_formal),
                ("formal_freeze_not_authorized", not freeze.get("formal_execution_authorized")),
                ("inexact_coverage", not exact),
                ("unresolved_cases_present", not zero_unresolved),
                ("not_726_cases", len(rows) != 726),
            )
            if present
        ],
    }


def run(
    *,
    freeze_path: Path,
    output_dir: Path,
    selection_name: str,
    resume: bool,
    admit_formal: bool = False,
    case_watchdog_seconds: float = CASE_WATCHDOG_SECONDS,
) -> dict[str, Any]:
    freeze = _read_json(freeze_path)
    selected = validate_freeze_identity(
        freeze=freeze, freeze_path=freeze_path, selection_name=selection_name
    )
    if case_watchdog_seconds != CASE_WATCHDOG_SECONDS:
        raise ValueError("Progent v1.3 case watchdog is frozen at 600 seconds")
    if admit_formal and selection_name != "formal":
        raise ValueError("qualification selections cannot request formal admission")
    expected_identity = {
        "freeze_sha256": sha256_file(freeze_path),
        "runner_version": RUNNER_VERSION,
        "model_id": str(freeze["model_id"]),
        "condition_id": CONDITION_ID,
        "selection_name": selection_name,
        "selected_cases": len(selected),
        "selected_case_rows_sha256": rows_sha256(selected),
    }
    validate_run_root(
        output_dir=output_dir, resume=resume, expected_identity=expected_identity
    )

    transport = freeze["transport"]
    base_url = str(transport["base_url"])
    os.environ["OPENAI_COMPATIBLE_BASE_URL"] = base_url
    os.environ["OPENAI_COMPATIBLE_API_KEY"] = "ollama-local"
    os.environ.setdefault("OLLAMA_MODELS", str(transport["ollama_models"]))
    service = _ollama_probe(base_url, str(freeze["model_id"]))
    if not service["model_present"]:
        raise ValueError("frozen model is not visible in Ollama")

    output_dir.mkdir(parents=True, exist_ok=True)
    case_root = output_dir / "case_manifests"
    worker_root = output_dir / "workers"
    progress_path = output_dir / "progress.jsonl"
    started_at = _utc_now()
    for index, frozen in enumerate(selected, 1):
        case_id = str(frozen["benchmark_case_id"])
        case_path = _case_manifest_path(case_root, index, case_id)
        if resume and case_path.is_file():
            existing = _read_json(case_path)
            _append_jsonl(
                progress_path,
                {
                    "index": index,
                    "benchmark_case_id": case_id,
                    "status": "resumed_completed",
                    "created_at": _utc_now(),
                },
            )
            if existing.get("status") != "completed":
                raise ValueError("failed roots cannot resume")
            continue
        parsed = parse_agentdojo_case_id(case_id)
        if parsed["case_kind"] != frozen.get("case_kind"):
            raise ValueError("freeze case kind mismatch: " + case_id)
        _append_jsonl(
            progress_path,
            {
                "index": index,
                "benchmark_case_id": case_id,
                "status": "running",
                "created_at": _utc_now(),
            },
        )
        row = run_case_subprocess(
            freeze_path=freeze_path,
            worker_dir=worker_root / f"{index:04d}_{case_id.replace(':', '__')}",
            case_id=case_id,
            watchdog_seconds=case_watchdog_seconds,
        )
        terminal = {
            "runner_version": RUNNER_VERSION,
            "evidence_status": f"progent_v13_{selection_name}_qualification_case",
            "result_eligible_for_formal_tables": False,
            "case_index": index,
            **row,
        }
        # The worker/parent trace is already sealed and hash-verified here.
        _write_json(case_path, terminal)
        _append_jsonl(
            progress_path,
            {
                "index": index,
                "benchmark_case_id": case_id,
                "status": terminal["status"],
                "operational_status": terminal["operational_status"],
                "trace_event_sha256": terminal["trace_event_sha256"],
                "created_at": _utc_now(),
            },
        )
        current = _aggregate_cases(case_root, selected)
        _write_jsonl(output_dir / "outcomes.jsonl", current)
        _write_json(
            output_dir / "run_manifest.json",
            _manifest(
                freeze_path=freeze_path,
                output_dir=output_dir,
                freeze=freeze,
                selection_name=selection_name,
                selected=selected,
                rows=current,
                started_at=started_at,
                status="running",
                service=service,
                resume=resume,
                admit_formal=admit_formal,
            ),
        )

    rows = _aggregate_cases(case_root, selected)
    _write_jsonl(output_dir / "outcomes.jsonl", rows)
    terminal_status = (
        "completed_qualification"
        if all(row.get("operational_status") == "completed" for row in rows)
        else "completed_qualification_with_failures"
    )
    manifest = _manifest(
        freeze_path=freeze_path,
        output_dir=output_dir,
        freeze=freeze,
        selection_name=selection_name,
        selected=selected,
        rows=rows,
        started_at=started_at,
        status=terminal_status,
        service=service,
        resume=resume,
        admit_formal=admit_formal,
    )
    manifest["completed_at"] = _utc_now()
    manifest["outcomes_path"] = portable_path(output_dir / "outcomes.jsonl", root=ROOT)
    manifest["outcomes_sha256"] = sha256_file(output_dir / "outcomes.jsonl")
    manifest["progress_path"] = portable_path(progress_path, root=ROOT)
    manifest["progress_sha256"] = sha256_file(progress_path)
    _write_json(output_dir / "run_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selection", choices=sorted(SELECTIONS), default="p3")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--admit-formal", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        freeze_path=args.freeze.resolve(),
        output_dir=args.output_dir.resolve(),
        selection_name=args.selection,
        resume=not args.no_resume,
        admit_formal=args.admit_formal,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "summary": result["summary"],
                "attack_bounds": result["attack_bounds"],
                "result_eligible": result["result_eligible_for_formal_tables"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] in {"completed_qualification", "completed_formal"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
