"""Freeze the Pro-200 host-timeout evidence without upgrading a null exit.

The original guarded wrapper outlived its host command and never produced its
own receipt.  A watcher later observed that the execute child disappeared, but
its exit-code field is JSON ``null``.  This review therefore recomputes the
direct-exit claim as false, preserves the v1 finalizer's fail-closed result, and
separately binds the v2 finalizer's directly observed technical-review exit 0.

Only outcome-blind metadata ledgers are replayed here.  Query records,
checkpoint contents, provider traces, credentials, and scientific outcomes are
not opened or aggregated.  This review does not reconstruct the missing wrapper
receipt and does not authorize result access or successor execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

from experiments.paper_v2.contracts import canonical_json_bytes


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ORIGINAL_WRAPPER_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/adaptive_formal_pro_200_v2_guarded_v4_20260807"
)
ORIGINAL_RUNNING_PATH = ORIGINAL_WRAPPER_ROOT / "running.json"
ORIGINAL_RECEIPT_PATH = ORIGINAL_WRAPPER_ROOT / "receipt.json"
ORIGINAL_EXECUTE_STDOUT_PATH = ORIGINAL_WRAPPER_ROOT / "05_execute.stdout.log"
ORIGINAL_EXECUTE_STDERR_PATH = ORIGINAL_WRAPPER_ROOT / "05_execute.stderr.log"
ORIGINAL_WRAPPER_PATH = (
    PROJECT_ROOT / "outputs/verification/run_adaptive_formal_pro_v2_guarded_v4.ps1"
)
ORIGINAL_PREFIX_LOG_PATHS = tuple(
    ORIGINAL_WRAPPER_ROOT / f"{step}.{stream}.log"
    for step in (
        "01_harness_gate",
        "02_order_gate",
        "03_candidate",
        "04_admission",
    )
    for stream in ("stdout", "stderr")
)

RECOVERY_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/"
    "adaptive_formal_pro_200_host_timeout_recovery_v1_20260807"
)
WATCHER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/watch_adaptive_formal_pro_200_execute_exit_v1.ps1"
)
WATCHER_RUNNING_PATH = RECOVERY_ROOT / "watcher_running.json"
EXECUTE_EXIT_OBSERVATION_PATH = RECOVERY_ROOT / "execute_exit_observation.json"
FINALIZER_V1_PATH = (
    PROJECT_ROOT
    / "outputs/verification/finalize_adaptive_formal_pro_200_host_timeout_v1.ps1"
)
FINALIZER_V1_FAILURE_PATH = (
    RECOVERY_ROOT / "technical_review_recovery_receipt_write_failure.json"
)
FINALIZER_V2_PATH = (
    PROJECT_ROOT
    / "outputs/verification/finalize_adaptive_formal_pro_200_host_timeout_v2.ps1"
)
FINALIZER_V2_RECEIPT_PATH = (
    RECOVERY_ROOT / "technical_review_recovery_receipt_v2.json"
)
RECOVERED_REVIEW_STDOUT_PATH = (
    RECOVERY_ROOT / "06_recovered_technical_review_v2.stdout.log"
)
RECOVERED_REVIEW_STDERR_PATH = (
    RECOVERY_ROOT / "06_recovered_technical_review_v2.stderr.log"
)

CANDIDATE_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/adaptive_formal_pro_200_candidate_v2.json"
)
ADMISSION_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions/"
    "adaptive_formal_pro_200_admission_v2.json"
)
STAGE_ROOT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/adaptive_formal_pro_v2/"
    "pro_200-0f3e1f04239237c56b3ece87ef8eda8a6a4daf299bfa1c88bb04bf6280737d2f"
)
TECHNICAL_REVIEW_PATH = STAGE_ROOT / "technical_review_v2.json"
TASK_LEDGER_PATH = STAGE_ROOT / "task_events_v1.jsonl"
BUDGET_LEDGER_PATH = STAGE_ROOT / "provider_budget_ledger.jsonl"
CONTROLLER_V1_PATH = (
    PROJECT_ROOT / "experiments/paper_v2/adaptive_formal_pro_controller_v1.py"
)
CONTROLLER_V2_PATH = (
    PROJECT_ROOT / "experiments/paper_v2/adaptive_formal_pro_controller_v2.py"
)
ORDER_GATE_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/adaptive_execution_order_supersession_v2.json"
)
ORDER_GATE_SOURCE_PATH = (
    PROJECT_ROOT / "experiments/paper_v2/adaptive_execution_order_gate_v2.py"
)
HARNESS_GATE_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/experiment_closeout_harness_gate_v6.json"
)
HARNESS_GATE_SOURCE_PATH = (
    PROJECT_ROOT / "experiments/paper_v2/experiment_closeout_harness_gate_v6.py"
)

REVIEW_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/"
    "adaptive_formal_pro_200_host_timeout_review_v1.json"
)
TEST_PATH = (
    PROJECT_ROOT
    / "tests/unit/"
    "test_paper_v2_adaptive_formal_pro_200_host_timeout_review_v1.py"
)

SCHEMA_VERSION = "m3-paper-v2-adaptive-formal-pro-200-host-timeout-review-1.0"
REVIEWED_AT = "2026-08-07T12:20:00+08:00"
EXPECTED_STAGE = "pro_200"
EXPECTED_RUN_ID = "paper-v2-adaptive-pro_200-v2"
EXPECTED_EXECUTION_IDENTITY = (
    "0f3e1f04239237c56b3ece87ef8eda8a6a4daf299bfa1c88bb04bf6280737d2f"
)
EXPECTED_AUTHORIZED_TASK_COUNT = 39
EXPECTED_TARGET_BUDGET = 200
EXPECTED_STAGE_HARD_LIMIT_CNY = Decimal("20.0")
EXPECTED_PROCESS_ID = 9956
EXPECTED_PROCESS_START_TIME = "2026-08-07T07:54:27.1237445+08:00"
EXPECTED_EXECUTABLE = r"F:\robot\Anaconda3\python.exe"
EXPECTED_EXECUTE_EFFECTIVE_EXIT_BASIS = (
    "single_terminal_json_plus_hash_locked_controller_print_then_return_zero_contract"
)
EXPECTED_CONTROLLER_V2_SHA256 = (
    "371e5e645f8d9228bea913acb773390d01c3c98e41713fc3640f4c9d23bc6b80"
)
EXPECTED_WATCHER_SHA256 = (
    "8e061f79e3551c264c89f0737b6883a5eff9732ae62186841a7e79d78e4cee46"
)
EXPECTED_FINALIZER_V1_SHA256 = (
    "83b2e9e42369d26197085e7aacdb5d693fe6627532b9fe531a26201e1af36f07"
)
EXPECTED_FINALIZER_V2_SHA256 = (
    "2f4c9e2c88120ffcec7eba2358624f29d2c58de6e34135be10749d16002a8c4d"
)

TASK_EVENT_KEYS = frozenset(
    {
        "case_id",
        "checkpoint_path",
        "checkpoint_sha256",
        "event_sha256",
        "execution_identity",
        "ledger_sequence",
        "previous_event_sha256",
        "query_count",
        "recorded_at",
        "run_id",
        "schema_version",
        "stage",
        "target_budget",
        "terminal_class",
    }
)
BUDGET_EVENT_KEYS = frozenset(
    {
        "budget_status_after_request",
        "call_index",
        "event_sha256",
        "execution_identity",
        "ledger_sequence",
        "model_role",
        "previous_event_sha256",
        "provider_response_id",
        "recorded_at",
        "request_cost_cny",
        "role_cumulative_cost_cny",
        "role_cumulative_usage",
        "run_id",
        "schema_version",
        "usage",
        "work_key",
    }
)
EXECUTE_SUMMARY_KEYS = frozenset(
    {
        "automatic_retries",
        "diagnostic_tasks_this_process",
        "expected_stage_tasks",
        "external_effects_enabled",
        "model_id",
        "provider_calls_this_stage",
        "provider_tools_enabled",
        "result_admission_authorized",
        "run_id",
        "stage",
        "stage_cost_cny",
        "status",
        "stop_reason",
        "task_event_count",
        "tasks_completed_this_process",
        "terminal_queries_retried",
        "terminal_query_count_this_stage",
    }
)


class AdaptiveFormalPro200HostTimeoutReviewV1Error(ValueError):
    """Raised when the bounded Pro-200 host-timeout evidence drifts."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"evidence path escapes project root: {path}"
        ) from exc


def _project_path(display_path: str) -> Path:
    candidate = (PROJECT_ROOT / display_path).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"evidence path escapes project root: {display_path}"
        ) from exc
    return candidate


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"missing Pro-200 host-timeout evidence: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{path}: expected object"
        )
    return value


def _read_single_json_line(path: Path, *, label: str) -> dict[str, Any]:
    try:
        nonempty = [
            line for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError) as exc:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{label}: unreadable JSON log"
        ) from exc
    if len(nonempty) != 1:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{label}: expected exactly one nonempty JSON line"
        )
    try:
        value = json.loads(nonempty[0])
    except json.JSONDecodeError as exc:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{label}: invalid terminal JSON"
        ) from exc
    if not isinstance(value, dict):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{label}: expected JSON object"
        )
    return value


def _verify_file_lock(lock: Mapping[str, Any], *, label: str) -> None:
    display_path = lock.get("path")
    if not isinstance(display_path, str) or not display_path:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{label}: artifact path missing"
        )
    path = _project_path(display_path)
    if (
        not path.is_file()
        or lock.get("bytes") != path.stat().st_size
        or lock.get("sha256") != _sha256_file(path)
    ):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{label}: artifact lock drift: {display_path}"
        )
    if "manifest_sha256" in lock:
        value = _read_json(path)
        if lock.get("manifest_sha256") != value.get("manifest_sha256"):
            raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
                f"{label}: embedded manifest drift: {display_path}"
            )


def _verify_controller_exit_contract() -> str:
    observed_sha256 = _sha256_file(CONTROLLER_V2_PATH)
    expected_suffix = (
        '    print(json.dumps(value, ensure_ascii=False, sort_keys=True))\n'
        "    return 0\n\n\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())"
    )
    source = CONTROLLER_V2_PATH.read_text(encoding="utf-8")
    if (
        observed_sha256 != EXPECTED_CONTROLLER_V2_SHA256
        or not source.rstrip().endswith(expected_suffix)
    ):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "adaptive controller v2 terminal exit contract drift"
        )
    return observed_sha256


def _validate_execute_terminal_summary() -> dict[str, Any]:
    summary = _read_single_json_line(
        ORIGINAL_EXECUTE_STDOUT_PATH,
        label="Pro-200 execute stdout",
    )
    stderr = ORIGINAL_EXECUTE_STDERR_PATH.read_bytes()
    if (
        set(summary) != EXECUTE_SUMMARY_KEYS
        or stderr != b""
        or summary.get("status") != "adaptive_formal_stage_complete_unadmitted"
        or summary.get("stage") != EXPECTED_STAGE
        or summary.get("run_id") != EXPECTED_RUN_ID
        or summary.get("model_id") != "deepseek-v4-pro"
        or summary.get("expected_stage_tasks") != EXPECTED_AUTHORIZED_TASK_COUNT
        or summary.get("tasks_completed_this_process")
        != EXPECTED_AUTHORIZED_TASK_COUNT
        or summary.get("task_event_count") != EXPECTED_AUTHORIZED_TASK_COUNT
        or summary.get("provider_calls_this_stage") != 6925
        or summary.get("terminal_query_count_this_stage") != 5504
        or _decimal(
            summary.get("stage_cost_cny"), field="execute summary stage cost"
        )
        != Decimal("8.0544754")
        or summary.get("terminal_queries_retried") != 0
        or summary.get("automatic_retries") != 0
        or summary.get("provider_tools_enabled") is not False
        or summary.get("external_effects_enabled") is not False
        or summary.get("result_admission_authorized") is not False
        or summary.get("stop_reason") is not None
    ):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "Pro-200 execute terminal summary drift"
        )
    return summary


def _validate_prefix_replays(
    *, candidate: Mapping[str, Any], admission: Mapping[str, Any]
) -> dict[str, Any]:
    harness_gate = _read_json(HARNESS_GATE_PATH)
    order_gate = _read_json(ORDER_GATE_PATH)
    observed = {
        "harness_gate": _read_single_json_line(
            ORIGINAL_WRAPPER_ROOT / "01_harness_gate.stdout.log",
            label="Pro-200 Harness gate replay",
        ),
        "order_gate": _read_single_json_line(
            ORIGINAL_WRAPPER_ROOT / "02_order_gate.stdout.log",
            label="Pro-200 order gate replay",
        ),
        "candidate": _read_single_json_line(
            ORIGINAL_WRAPPER_ROOT / "03_candidate.stdout.log",
            label="Pro-200 candidate replay",
        ),
        "admission": _read_single_json_line(
            ORIGINAL_WRAPPER_ROOT / "04_admission.stdout.log",
            label="Pro-200 admission replay",
        ),
    }
    for step in ("02_order_gate", "03_candidate", "04_admission"):
        if (ORIGINAL_WRAPPER_ROOT / f"{step}.stderr.log").stat().st_size != 0:
            raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
                f"Pro-200 {step} stderr is not empty"
            )
    harness_stderr = (
        ORIGINAL_WRAPPER_ROOT / "01_harness_gate.stderr.log"
    ).read_text(encoding="utf-8", errors="replace")
    if "Traceback (most recent call last)" in harness_stderr:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "Pro-200 Harness replay stderr contains traceback"
        )
    order_summary = observed["order_gate"]
    if (
        observed["harness_gate"] != harness_gate
        or set(order_summary)
        != {
            "execution_admissions_created",
            "manifest_sha256",
            "network_calls_made",
            "status",
        }
        or order_summary.get("manifest_sha256")
        != order_gate.get("manifest_sha256")
        or order_summary.get("status") != order_gate.get("status")
        or order_summary.get("execution_admissions_created") != 0
        or order_summary.get("network_calls_made") != 0
        or observed["candidate"] != dict(candidate)
        or observed["admission"] != dict(admission)
    ):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "Pro-200 prefix replay output drift"
        )
    return {
        "harness_gate_manifest_sha256": harness_gate["manifest_sha256"],
        "order_gate_manifest_sha256": order_gate["manifest_sha256"],
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "admission_manifest_sha256": admission["manifest_sha256"],
        "prefix_replay_outputs_match_frozen_artifacts": True,
        "prefix_replay_traceback_observed": False,
    }


def _read_metadata_jsonl(
    path: Path, *, allowed_keys: frozenset[str]
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            for line_number, raw_line in enumerate(stream, 1):
                if not raw_line.strip():
                    raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
                        f"{path}: blank JSONL line {line_number}"
                    )
                value = json.loads(raw_line)
                if not isinstance(value, dict) or set(value) != allowed_keys:
                    raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
                        f"{path}: non-metadata fields or schema drift at line "
                        f"{line_number}"
                    )
                events.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{path}: invalid metadata JSONL"
        ) from exc
    if not events:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{path}: metadata ledger is empty"
        )
    return events


def _decimal(value: Any, *, field: str) -> Decimal:
    if isinstance(value, bool):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{field}: boolean is not a decimal"
        )
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{field}: invalid decimal"
        ) from exc
    if not result.is_finite():
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{field}: non-finite decimal"
        )
    return result


def _validate_embedded_manifest(
    value: Mapping[str, Any], *, label: str
) -> str:
    observed = value.get("manifest_sha256")
    if not isinstance(observed, str):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{label}: manifest digest missing"
        )
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}
    recomputed = _canonical_sha256(core)
    if observed != recomputed:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            f"{label}: manifest digest drift"
        )
    return recomputed


def recompute_direct_exit_observation(
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute directness; a JSON null can never prove an OS exit code."""

    raw_claim = observation.get("operating_system_exit_code_directly_observed")
    raw_exit = observation.get("execute_child_exit_code")
    exit_is_integer = isinstance(raw_exit, int) and not isinstance(raw_exit, bool)
    recomputed = raw_claim is True and exit_is_integer
    if raw_exit is None:
        reason = "watcher_returned_null_exit_code"
    elif raw_claim is not True:
        reason = "watcher_did_not_claim_direct_observation"
    elif not exit_is_integer:
        reason = "watcher_exit_code_is_not_an_integer"
    else:
        reason = None
    return {
        "watcher_raw_direct_claim": raw_claim,
        "watcher_exit_code": raw_exit,
        "watcher_exit_code_is_integer": exit_is_integer,
        "execute_child_exit_code_directly_observed_recomputed": recomputed,
        "raw_claim_contradicted_by_null_exit": raw_claim is True and raw_exit is None,
        "invalid_or_missing_direct_exit_reason": reason,
    }


def _validate_task_ledger(
    events: Iterable[Mapping[str, Any]],
    *,
    authorized_case_ids: set[str],
) -> dict[str, Any]:
    previous: str | None = None
    terminal_case_ids: set[str] = set()
    query_counts: dict[str, int] = {}
    final_query_count_sum = 0
    terminal_class_counts = {"search_terminal": 0, "diagnostic_terminal": 0}
    event_count = 0
    for sequence, event in enumerate(events, 1):
        event_count = sequence
        case_id = str(event.get("case_id", ""))
        terminal_class = event.get("terminal_class")
        core = {key: child for key, child in event.items() if key != "event_sha256"}
        checkpoint_path = _project_path(str(event.get("checkpoint_path", "")))
        if (
            event.get("schema_version")
            != "m3-paper-v2-adaptive-formal-pro-task-event-1.0"
            or event.get("ledger_sequence") != sequence
            or event.get("previous_event_sha256") != previous
            or event.get("run_id") != EXPECTED_RUN_ID
            or event.get("execution_identity") != EXPECTED_EXECUTION_IDENTITY
            or event.get("stage") != EXPECTED_STAGE
            or event.get("target_budget") != EXPECTED_TARGET_BUDGET
            or case_id not in authorized_case_ids
            or case_id in terminal_case_ids
            or terminal_class not in terminal_class_counts
            or not isinstance(event.get("query_count"), int)
            or isinstance(event.get("query_count"), bool)
            or int(event["query_count"]) <= 0
            or int(event["query_count"]) > EXPECTED_TARGET_BUDGET
            or not checkpoint_path.is_file()
            or checkpoint_path.stat().st_size <= 0
            or event.get("checkpoint_sha256") != _sha256_file(checkpoint_path)
            or event.get("event_sha256") != _canonical_sha256(core)
        ):
            raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
                f"task metadata ledger drift at sequence {sequence}"
            )
        previous = str(event["event_sha256"])
        terminal_case_ids.add(case_id)
        query_counts[case_id] = int(event["query_count"])
        final_query_count_sum += int(event["query_count"])
        terminal_class_counts[str(terminal_class)] += 1
    if terminal_case_ids != authorized_case_ids:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "task metadata ledger does not terminate every authorized case"
        )
    return {
        "event_count": event_count,
        "unique_terminal_task_count": len(terminal_case_ids),
        "terminal_case_ids": sorted(terminal_case_ids),
        "query_counts": query_counts,
        "final_query_count_sum": final_query_count_sum,
        "terminal_class_counts": terminal_class_counts,
        "tail_sha256": previous,
    }


def _validate_budget_ledger(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    previous: str | None = None
    total_cost = Decimal("0")
    event_count = 0
    per_work_call_index: dict[str, int] = {}
    for sequence, event in enumerate(events, 1):
        event_count = sequence
        core = {key: child for key, child in event.items() if key != "event_sha256"}
        work_key = str(event.get("work_key", ""))
        expected_call_index = per_work_call_index.get(work_key, 0) + 1
        request_cost = _decimal(
            event.get("request_cost_cny"), field="request_cost_cny"
        )
        cumulative_cost = _decimal(
            event.get("role_cumulative_cost_cny"),
            field="role_cumulative_cost_cny",
        )
        total_cost += request_cost
        if (
            event.get("schema_version")
            != "m3-paper-v2-public-budget-event-1.0"
            or event.get("ledger_sequence") != sequence
            or not work_key
            or event.get("call_index") != expected_call_index
            or event.get("previous_event_sha256") != previous
            or event.get("run_id") != EXPECTED_RUN_ID
            or event.get("execution_identity") != EXPECTED_EXECUTION_IDENTITY
            or event.get("model_role") != "primary"
            or request_cost < 0
            or cumulative_cost != total_cost
            or event.get("event_sha256") != _canonical_sha256(core)
        ):
            raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
                f"budget metadata ledger drift at sequence {sequence}"
            )
        previous = str(event["event_sha256"])
        per_work_call_index[work_key] = expected_call_index
    return {
        "event_count": event_count,
        "independently_summed_stage_cost_cny": float(total_cost),
        "final_cumulative_cost_cny": float(total_cost),
        "tail_sha256": previous,
    }


def _validate_checkpoint_locks(
    review: Mapping[str, Any],
    *,
    authorized_case_ids: set[str],
    query_counts: Mapping[str, int],
) -> dict[str, Any]:
    locks = review.get("final_checkpoint_locks")
    if not isinstance(locks, list):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "technical review checkpoint locks are missing"
        )
    locked_case_ids: set[str] = set()
    for lock in locks:
        if not isinstance(lock, Mapping):
            raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
                "technical review checkpoint lock is not an object"
            )
        case_id = str(lock.get("case_id", ""))
        path = _project_path(str(lock.get("path", "")))
        if (
            case_id not in authorized_case_ids
            or case_id in locked_case_ids
            or not path.is_file()
            or lock.get("bytes") != path.stat().st_size
            or lock.get("sha256") != _sha256_file(path)
            or lock.get("query_count") != query_counts.get(case_id)
        ):
            raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
                f"technical review checkpoint lock drift: {case_id}"
            )
        locked_case_ids.add(case_id)
    if locked_case_ids != authorized_case_ids:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "technical review does not lock every authorized checkpoint"
        )
    return {
        "checkpoint_lock_count": len(locks),
        "checkpoint_case_set_matches_authorized_tasks": True,
        "checkpoint_file_hashes_match_without_content_parsing": True,
        "checkpoint_query_counts_match_task_metadata": True,
    }


def _validate_static_chain() -> dict[str, Any]:
    running = _read_json(ORIGINAL_RUNNING_PATH)
    watcher_running = _read_json(WATCHER_RUNNING_PATH)
    observation = _read_json(EXECUTE_EXIT_OBSERVATION_PATH)
    v1_failure = _read_json(FINALIZER_V1_FAILURE_PATH)
    v2_receipt = _read_json(FINALIZER_V2_RECEIPT_PATH)

    watcher_sha = _sha256_file(WATCHER_PATH)
    v1_sha = _sha256_file(FINALIZER_V1_PATH)
    v2_sha = _sha256_file(FINALIZER_V2_PATH)
    controller_sha = _verify_controller_exit_contract()
    execute_summary = _validate_execute_terminal_summary()
    directness = recompute_direct_exit_observation(observation)

    if (
        running.get("schema_version")
        != "m3-paper-v2-adaptive-formal-pro-running-4.0"
        or running.get("status") != "running"
        or running.get("stage") != EXPECTED_STAGE
        or running.get("run_id") != EXPECTED_RUN_ID
        or running.get("execution_identity") != EXPECTED_EXECUTION_IDENTITY
        or running.get("authorized_task_count") != EXPECTED_AUTHORIZED_TASK_COUNT
        or running.get("target_budget") != EXPECTED_TARGET_BUDGET
        or running.get("automatic_retries") != 0
        or running.get("provider_tools_enabled") is not False
        or running.get("external_effects_enabled") is not False
        or running.get("scientific_outcomes_accessed") is not False
        or ORIGINAL_RECEIPT_PATH.exists()
        or watcher_sha != EXPECTED_WATCHER_SHA256
        or watcher_running.get("schema_version")
        != "m3-paper-v2-execute-exit-watcher-running-1.0"
        or watcher_running.get("status") != "attached_waiting_for_natural_exit"
        or watcher_running.get("process_id") != EXPECTED_PROCESS_ID
        or watcher_running.get("process_start_time")
        != EXPECTED_PROCESS_START_TIME
        or watcher_running.get("executable") != EXPECTED_EXECUTABLE
        or watcher_running.get("watcher_sha256") != watcher_sha
        or watcher_running.get("provider_execution_started_by_watcher") is not False
        or watcher_running.get("stop_or_kill_authorized") is not False
        or watcher_running.get("restart_or_retry_authorized") is not False
        or watcher_running.get("scientific_outcomes_accessed") is not False
        or observation.get("schema_version")
        != "m3-paper-v2-execute-exit-observation-1.0"
        or observation.get("status") != "execute_child_natural_exit_observed"
        or observation.get("process_id") != EXPECTED_PROCESS_ID
        or observation.get("process_start_time") != EXPECTED_PROCESS_START_TIME
        or observation.get("executable") != EXPECTED_EXECUTABLE
        or observation.get("process_id") != watcher_running.get("process_id")
        or observation.get("process_start_time")
        != watcher_running.get("process_start_time")
        or observation.get("executable") != watcher_running.get("executable")
        or observation.get("watcher_sha256") != watcher_sha
        or observation.get("execute_stdout_sha256")
        != _sha256_file(ORIGINAL_EXECUTE_STDOUT_PATH)
        or observation.get("execute_stderr_sha256")
        != _sha256_file(ORIGINAL_EXECUTE_STDERR_PATH)
        or observation.get("original_wrapper_exit_code_directly_observed")
        is not False
        or observation.get("original_wrapper_receipt_reconstructed") is not False
        or observation.get("stop_or_kill_signals_sent") != 0
        or observation.get("restart_or_retry_attempts") != 0
        or observation.get("provider_calls_made_by_watcher") != 0
        or observation.get("scientific_outcomes_accessed") is not False
        or directness["execute_child_exit_code_directly_observed_recomputed"]
        is not False
        or directness["watcher_exit_code"] is not None
        or directness["raw_claim_contradicted_by_null_exit"] is not True
        or v1_sha != EXPECTED_FINALIZER_V1_SHA256
        or v1_failure.get("schema_version")
        != "m3-paper-v2-adaptive-pro-200-host-timeout-finalizer-failure-1.0"
        or v1_failure.get("status") != "recovery_finalizer_failed_closed"
        or v1_failure.get("original_wrapper_receipt_reconstructed") is not False
        or v1_failure.get("provider_calls_made_by_finalizer") != 0
        or v1_failure.get("stop_or_kill_signals_sent") != 0
        or v1_failure.get("restart_or_retry_attempts") != 0
        or v1_failure.get("scientific_outcomes_accessed") is not False
        or v1_failure.get("finalizer_sha256") != v1_sha
        or v2_sha != EXPECTED_FINALIZER_V2_SHA256
        or v2_receipt.get("schema_version")
        != "m3-paper-v2-adaptive-pro-200-host-timeout-finalizer-2.0"
        or v2_receipt.get("status")
        != "execute_effective_exit_zero_and_recovered_technical_gate_pass"
        or v2_receipt.get("prior_finalizer_failed_closed") is not True
        or v2_receipt.get("prior_failure_sha256")
        != _sha256_file(FINALIZER_V1_FAILURE_PATH)
        or v2_receipt.get("original_wrapper_exit_code_directly_observed")
        is not False
        or v2_receipt.get("original_wrapper_receipt_reconstructed") is not False
        or v2_receipt.get("execute_child_exit_code_directly_observed") is not False
        or v2_receipt.get("execute_child_exit_code_observation_invalid_reason")
        != "watcher_returned_null_exit_code"
        or v2_receipt.get("execute_child_effective_exit_code") != 0
        or v2_receipt.get("execute_child_effective_exit_basis")
        != EXPECTED_EXECUTE_EFFECTIVE_EXIT_BASIS
        or v2_receipt.get("execute_stdout_sha256")
        != _sha256_file(ORIGINAL_EXECUTE_STDOUT_PATH)
        or v2_receipt.get("execute_stderr_sha256")
        != _sha256_file(ORIGINAL_EXECUTE_STDERR_PATH)
        or v2_receipt.get("controller_sha256") != controller_sha
        or v2_receipt.get("technical_review_child_exit_code_directly_observed")
        is not True
        or v2_receipt.get("technical_review_child_exit_code") != 0
        or v2_receipt.get("technical_review_stdout_sha256")
        != _sha256_file(RECOVERED_REVIEW_STDOUT_PATH)
        or v2_receipt.get("technical_review_stderr_sha256")
        != _sha256_file(RECOVERED_REVIEW_STDERR_PATH)
        or v2_receipt.get("technical_review_sha256")
        != _sha256_file(TECHNICAL_REVIEW_PATH)
        or v2_receipt.get("provider_calls_made_by_finalizer") != 0
        or v2_receipt.get("stop_or_kill_signals_sent") != 0
        or v2_receipt.get("restart_or_retry_attempts") != 0
        or v2_receipt.get("scientific_outcomes_accessed") is not False
        or v2_receipt.get("finalizer_sha256") != v2_sha
    ):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "Pro-200 host-timeout finalization chain drift"
        )

    return {
        "original_wrapper": {
            "running_attestation_status": running["status"],
            "receipt_path": _display_path(ORIGINAL_RECEIPT_PATH),
            "receipt_exists": False,
            "original_wrapper_exit_code_directly_observed": False,
            "original_wrapper_receipt_reconstructed": False,
        },
        "watcher": directness,
        "watcher_process_identity": {
            "process_id": EXPECTED_PROCESS_ID,
            "process_start_time": EXPECTED_PROCESS_START_TIME,
            "executable": EXPECTED_EXECUTABLE,
            "running_and_observation_identity_match": True,
            "schema_and_status_match": True,
        },
        "execute_terminal_contract": {
            "controller_sha256": controller_sha,
            "single_nonempty_json_line": True,
            "effective_exit_code": 0,
            "effective_exit_basis": EXPECTED_EXECUTE_EFFECTIVE_EXIT_BASIS,
            "terminal_status": execute_summary["status"],
            "terminal_task_count": execute_summary["task_event_count"],
            "completed_provider_call_count": execute_summary[
                "provider_calls_this_stage"
            ],
            "terminal_query_count_this_stage": execute_summary[
                "terminal_query_count_this_stage"
            ],
            "stage_cost_cny": execute_summary["stage_cost_cny"],
            "safety_fields_match": True,
        },
        "v1_finalizer": {
            "status": v1_failure["status"],
            "failed_closed": True,
            "failure_receipt_sha256": _sha256_file(FINALIZER_V1_FAILURE_PATH),
            "finalizer_sha256": v1_sha,
        },
        "v2_finalizer": {
            "status": v2_receipt["status"],
            "execute_child_effective_exit_code": v2_receipt[
                "execute_child_effective_exit_code"
            ],
            "execute_child_effective_exit_basis": v2_receipt[
                "execute_child_effective_exit_basis"
            ],
            "execute_child_exit_code_directly_observed": False,
            "technical_review_child_exit_code_directly_observed": True,
            "technical_review_child_exit_code": 0,
            "technical_review_sha256": v2_receipt["technical_review_sha256"],
            "technical_review_manifest_sha256": v2_receipt[
                "technical_review_manifest_sha256"
            ],
            "finalizer_sha256": v2_sha,
        },
    }


def _recompute_stable_technical_fields() -> dict[str, Any]:
    candidate = _read_json(CANDIDATE_PATH)
    admission = _read_json(ADMISSION_PATH)
    technical_review = _read_json(TECHNICAL_REVIEW_PATH)
    candidate_manifest = _validate_embedded_manifest(candidate, label="candidate")
    admission_manifest = _validate_embedded_manifest(admission, label="admission")
    review_manifest = _validate_embedded_manifest(
        technical_review, label="technical review"
    )
    prefix_replays = _validate_prefix_replays(
        candidate=candidate,
        admission=admission,
    )

    candidate_scope = candidate.get("scope")
    candidate_auth = candidate.get("authorization")
    admission_auth = admission.get("authorization")
    checks = technical_review.get("checks")
    if (
        not isinstance(candidate_scope, Mapping)
        or not isinstance(candidate_auth, Mapping)
        or not isinstance(admission_auth, Mapping)
        or not isinstance(checks, Mapping)
    ):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "candidate, admission, or technical review structure drift"
        )
    case_ids_value = candidate_scope.get("authorized_case_ids")
    admission_case_ids_value = admission.get("authorized_case_ids")
    if not isinstance(case_ids_value, list) or not isinstance(
        admission_case_ids_value, list
    ):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "authorized case IDs are missing"
        )
    authorized_case_ids = {str(value) for value in case_ids_value}
    admission_case_ids = {str(value) for value in admission_case_ids_value}
    artifact_locks = candidate.get("artifact_locks")
    source_checkpoint_locks = candidate.get("source_checkpoint_locks")
    if not isinstance(artifact_locks, list) or not isinstance(
        source_checkpoint_locks, list
    ):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "candidate immutable locks are missing"
        )
    artifact_paths: set[str] = set()
    for lock in artifact_locks:
        if not isinstance(lock, Mapping):
            raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
                "candidate artifact lock is not an object"
            )
        _verify_file_lock(lock, label="candidate artifact")
        artifact_paths.add(str(lock.get("path", "")))
    required_artifact_paths = {
        _display_path(CONTROLLER_V1_PATH),
        _display_path(CONTROLLER_V2_PATH),
        _display_path(ORDER_GATE_PATH),
    }
    if not required_artifact_paths.issubset(artifact_paths):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "candidate does not lock the controller/order sources"
        )
    source_lock_case_ids: set[str] = set()
    source_prefix_query_count = 0
    for lock in source_checkpoint_locks:
        if not isinstance(lock, Mapping):
            raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
                "candidate source checkpoint lock is not an object"
            )
        _verify_file_lock(lock, label="candidate source checkpoint")
        case_id = str(lock.get("case_id", ""))
        query_count = lock.get("query_count")
        if (
            case_id not in authorized_case_ids
            or case_id in source_lock_case_ids
            or not isinstance(query_count, int)
            or isinstance(query_count, bool)
            or query_count != 50
        ):
            raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
                "candidate source checkpoint metadata drift"
            )
        source_lock_case_ids.add(case_id)
        source_prefix_query_count += query_count
    if source_lock_case_ids != authorized_case_ids:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "candidate source checkpoint case set drift"
        )
    if (
        candidate.get("schema_version")
        != "m3-paper-v2-adaptive-formal-pro-stage-candidate-2.0"
        or candidate_scope.get("stage") != EXPECTED_STAGE
        or candidate_scope.get("run_id") != EXPECTED_RUN_ID
        or candidate_scope.get("execution_identity")
        != EXPECTED_EXECUTION_IDENTITY
        or candidate_scope.get("authorized_task_count")
        != EXPECTED_AUTHORIZED_TASK_COUNT
        or len(case_ids_value) != EXPECTED_AUTHORIZED_TASK_COUNT
        or len(authorized_case_ids) != EXPECTED_AUTHORIZED_TASK_COUNT
        or candidate_scope.get("target_budget") != EXPECTED_TARGET_BUDGET
        or _decimal(
            candidate_scope.get("stage_hard_limit_cny"),
            field="candidate stage_hard_limit_cny",
        )
        != EXPECTED_STAGE_HARD_LIMIT_CNY
        or candidate_auth.get("result_admission_authorized") is not False
        or admission.get("schema_version")
        != "m3-paper-v2-adaptive-formal-pro-stage-admission-2.0"
        or admission.get("stage") != EXPECTED_STAGE
        or admission.get("run_id") != EXPECTED_RUN_ID
        or admission.get("execution_identity") != EXPECTED_EXECUTION_IDENTITY
        or admission.get("candidate_manifest_sha256") != candidate_manifest
        or admission_case_ids != authorized_case_ids
        or len(admission_case_ids_value) != EXPECTED_AUTHORIZED_TASK_COUNT
        or admission_auth.get("result_admission_authorized") is not False
        or technical_review.get("schema_version")
        != "m3-paper-v2-adaptive-formal-pro-review-1.0"
        or technical_review.get("artifact_role")
        != "outcome_blind_adaptive_stage_technical_review"
        or technical_review.get("status")
        != "adaptive_formal_stage_technical_gate_pass"
        or technical_review.get("stage") != EXPECTED_STAGE
        or technical_review.get("run_id") != EXPECTED_RUN_ID
        or technical_review.get("execution_identity")
        != EXPECTED_EXECUTION_IDENTITY
        or technical_review.get("candidate_manifest_sha256") != candidate_manifest
        or technical_review.get("admission_file_sha256")
        != _sha256_file(ADMISSION_PATH)
        or not checks
        or any(value is not True for value in checks.values())
        or technical_review.get("technical_gate_passed") is not True
        or technical_review.get("result_admission_authorized") is not False
    ):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "candidate/admission/technical-review contract drift"
        )

    task_events = _read_metadata_jsonl(
        TASK_LEDGER_PATH, allowed_keys=TASK_EVENT_KEYS
    )
    task_status = _validate_task_ledger(
        task_events, authorized_case_ids=authorized_case_ids
    )
    budget_events = _read_metadata_jsonl(
        BUDGET_LEDGER_PATH, allowed_keys=BUDGET_EVENT_KEYS
    )
    budget_status = _validate_budget_ledger(budget_events)
    checkpoint_status = _validate_checkpoint_locks(
        technical_review,
        authorized_case_ids=authorized_case_ids,
        query_counts=task_status["query_counts"],
    )

    recomputed_cost = _decimal(
        budget_status["independently_summed_stage_cost_cny"],
        field="recomputed stage cost",
    )
    reviewed_cost = _decimal(
        technical_review.get("stage_cost_cny"),
        field="technical review stage cost",
    )
    reviewed_limit = _decimal(
        technical_review.get("stage_hard_limit_cny"),
        field="technical review stage hard limit",
    )
    v2_receipt = _read_json(FINALIZER_V2_RECEIPT_PATH)
    execute_summary = _validate_execute_terminal_summary()
    terminal_query_count_this_stage = (
        task_status["final_query_count_sum"] - source_prefix_query_count
    )
    if (
        task_status["event_count"] != EXPECTED_AUTHORIZED_TASK_COUNT
        or task_status["unique_terminal_task_count"]
        != EXPECTED_AUTHORIZED_TASK_COUNT
        or technical_review.get("authorized_task_count")
        != EXPECTED_AUTHORIZED_TASK_COUNT
        or technical_review.get("terminal_task_count")
        != EXPECTED_AUTHORIZED_TASK_COUNT
        or technical_review.get("target_budget") != EXPECTED_TARGET_BUDGET
        or technical_review.get("task_ledger_tail_sha256")
        != task_status["tail_sha256"]
        or technical_review.get("completed_provider_call_count")
        != budget_status["event_count"]
        or terminal_query_count_this_stage != 5504
        or technical_review.get("terminal_query_count_this_stage")
        != terminal_query_count_this_stage
        or technical_review.get("budget_ledger_tail_sha256")
        != budget_status["tail_sha256"]
        or recomputed_cost != reviewed_cost
        or reviewed_limit != EXPECTED_STAGE_HARD_LIMIT_CNY
        or recomputed_cost > reviewed_limit
        or v2_receipt.get("terminal_task_count")
        != EXPECTED_AUTHORIZED_TASK_COUNT
        or v2_receipt.get("target_budget") != EXPECTED_TARGET_BUDGET
        or _decimal(v2_receipt.get("stage_cost_cny"), field="v2 receipt cost")
        != recomputed_cost
        or v2_receipt.get("technical_gate_passed") is not True
        or v2_receipt.get("result_admission_authorized") is not False
        or v2_receipt.get("technical_review_manifest_sha256") != review_manifest
        or execute_summary.get("task_event_count")
        != task_status["event_count"]
        or execute_summary.get("provider_calls_this_stage")
        != budget_status["event_count"]
        or execute_summary.get("terminal_query_count_this_stage")
        != terminal_query_count_this_stage
        or _decimal(
            execute_summary.get("stage_cost_cny"),
            field="execute summary stage cost",
        )
        != recomputed_cost
    ):
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "independent stable-field recomputation disagrees with technical review"
        )

    return {
        "candidate_manifest_sha256_recomputed": candidate_manifest,
        "admission_manifest_sha256_recomputed": admission_manifest,
        "technical_review_manifest_sha256_recomputed": review_manifest,
        "authorized_task_count_from_candidate": len(authorized_case_ids),
        "terminal_task_count_from_task_metadata": task_status["event_count"],
        "unique_terminal_task_count_from_task_metadata": task_status[
            "unique_terminal_task_count"
        ],
        "target_budget_from_candidate": int(candidate_scope["target_budget"]),
        "target_budget_is_200": True,
        "task_event_chain_valid": True,
        "task_ledger_tail_sha256_recomputed": task_status["tail_sha256"],
        "terminal_class_counts": task_status["terminal_class_counts"],
        "final_query_count_sum_from_task_metadata": task_status[
            "final_query_count_sum"
        ],
        "source_prefix_query_count_from_candidate": source_prefix_query_count,
        "terminal_query_count_this_stage_recomputed": (
            terminal_query_count_this_stage
        ),
        "terminal_query_count_matches_stdout_and_review": True,
        "completed_provider_call_count_from_budget_metadata": budget_status[
            "event_count"
        ],
        "budget_event_chain_valid": True,
        "budget_ledger_tail_sha256_recomputed": budget_status["tail_sha256"],
        "stage_cost_cny_independently_summed": float(recomputed_cost),
        "stage_hard_limit_cny_from_candidate": float(reviewed_limit),
        "stage_cost_within_hard_limit": recomputed_cost <= reviewed_limit,
        **checkpoint_status,
        "technical_review_stable_fields_match": True,
        "execute_stdout_stable_fields_match": True,
        "candidate_artifact_locks_replayed": len(artifact_locks),
        "candidate_source_checkpoint_locks_replayed": len(
            source_checkpoint_locks
        ),
        "prefix_replays": prefix_replays,
        "technical_gate_passed": True,
        "candidate_result_admission_authorized": False,
        "admission_result_admission_authorized": False,
        "technical_review_result_admission_authorized": False,
        "v2_finalizer_result_admission_authorized": False,
        "result_remains_unadmitted": True,
    }


def build_review() -> dict[str, Any]:
    host_timeout_chain = _validate_static_chain()
    stable_fields = _recompute_stable_technical_fields()
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": (
            "immutable_outcome_blind_review_of_pro_200_host_timeout_and_"
            "technical_closure"
        ),
        "reviewed_at": REVIEWED_AT,
        "status": (
            "host_timeout_frozen_technical_gate_verified_wrapper_exit_unproven"
        ),
        "source_locks": [
            _lock(ORIGINAL_RUNNING_PATH),
            _lock(ORIGINAL_WRAPPER_PATH),
            *[_lock(path) for path in ORIGINAL_PREFIX_LOG_PATHS],
            _lock(ORIGINAL_EXECUTE_STDOUT_PATH),
            _lock(ORIGINAL_EXECUTE_STDERR_PATH),
            _lock(WATCHER_PATH),
            _lock(WATCHER_RUNNING_PATH),
            _lock(EXECUTE_EXIT_OBSERVATION_PATH),
            _lock(FINALIZER_V1_PATH),
            _lock(FINALIZER_V1_FAILURE_PATH),
            _lock(FINALIZER_V2_PATH),
            _lock(FINALIZER_V2_RECEIPT_PATH),
            _lock(RECOVERED_REVIEW_STDOUT_PATH),
            _lock(RECOVERED_REVIEW_STDERR_PATH),
            _lock(CANDIDATE_PATH),
            _lock(ADMISSION_PATH),
            _lock(TECHNICAL_REVIEW_PATH),
            _lock(TASK_LEDGER_PATH),
            _lock(BUDGET_LEDGER_PATH),
            _lock(CONTROLLER_V1_PATH),
            _lock(CONTROLLER_V2_PATH),
            _lock(ORDER_GATE_PATH),
            _lock(ORDER_GATE_SOURCE_PATH),
            _lock(HARNESS_GATE_PATH),
            _lock(HARNESS_GATE_SOURCE_PATH),
            _lock(Path(__file__)),
            _lock(TEST_PATH),
        ],
        "host_timeout_chain": host_timeout_chain,
        "independent_stable_technical_recomputation": stable_fields,
        "claim_boundary": {
            "original_wrapper_direct_exit_proven": False,
            "execute_child_direct_exit_proven": False,
            "execute_child_effective_exit_zero_is_inferred": True,
            "technical_review_child_direct_exit_zero_proven": True,
            "technical_stage_completion_proven": True,
            "scientific_result_admission_proven": False,
            "successor_stage_execution_authorized": False,
        },
        "evidence_boundary": {
            "credential_files_opened": False,
            "provider_calls_made_by_review": 0,
            "network_calls_made_by_review": 0,
            "query_ledger_opened": False,
            "checkpoint_semantics_parsed": False,
            "checkpoint_bytes_read_for_hashing": True,
            "provider_traces_opened": False,
            "scientific_outcomes_read": False,
            "scientific_outcomes_aggregated": False,
            "historical_evidence_modified": False,
            "original_wrapper_receipt_reconstructed": False,
            "result_access_authorized": False,
            "provider_execution_authorized": False,
        },
    }
    return {**core, "manifest_sha256": _canonical_sha256(core)}


def write_review() -> dict[str, Any]:
    value = build_review()
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def validate_review(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_review()
    if dict(value) != expected:
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "Pro-200 host-timeout review artifact drift"
        )
    return dict(value)


def verify_review() -> dict[str, Any]:
    if not REVIEW_PATH.is_file():
        raise AdaptiveFormalPro200HostTimeoutReviewV1Error(
            "Pro-200 host-timeout review artifact missing"
        )
    return validate_review(_read_json(REVIEW_PATH))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-review", action="store_true")
    action.add_argument("--verify-review", action="store_true")
    args = parser.parse_args()
    value = write_review() if args.write_review else verify_review()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
