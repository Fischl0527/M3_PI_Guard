"""面向固化的 Gemini 公开基准接续实验的单配额日后继控制器。

安全调度单日配额内的基准用例执行，按进度输出持久化检查点。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import experiments.paper_v2.gemini_daily_quota_ledger_v1 as daily_quota
import experiments.paper_v2.gemini_public_continuation_plan_v1 as plan
import experiments.paper_v2.gemini_public_controller_v1 as public_v1
import experiments.paper_v2.gemini_public_controller_v4 as canary_v4
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.gemini_public_execution_store_v1 import (
    append_execution_result,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderBudgetState,
    ProviderPausedError,
)
from experiments.paper_v2.public_matrix_plan_v1 import hydrate_public_work_item
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
CANDIDATE_ROOT = PROTOCOL_ROOT / "gemini_public_continuation_segments_v1"
ADMISSION_ROOT = PROTOCOL_ROOT / "admissions/gemini_public_continuation_v1"
OUTPUT_BASE = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_public/gemini/public-continuation-v1"
)
SCHEMA_VERSION = "m3-paper-v2-gemini-public-continuation-segment-1.0"
ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-gemini-public-continuation-segment-admission-1.0"
)
REVIEW_SCHEMA_VERSION = (
    "m3-paper-v2-gemini-public-continuation-segment-review-1.0"
)
MODEL_ID = "gemini-3.6-flash"
OWNER_STATEMENT_SHA256 = canary_v4.OWNER_STATEMENT_SHA256


class GeminiPublicContinuationControllerV1Error(RuntimeError):
    """当每日接续无法保持形式化边界时抛出的异常。"""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiPublicContinuationControllerV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise GeminiPublicContinuationControllerV1Error(
            f"{path}: expected object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiPublicContinuationControllerV1Error(
            f"missing frozen continuation input: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock.get("path", ""))).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise GeminiPublicContinuationControllerV1Error(
            "continuation lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock.get("bytes")
        or _sha256_file(path) != lock.get("sha256")
    ):
        raise GeminiPublicContinuationControllerV1Error(
            f"continuation lock drift: {path}"
        )


def _schedule_rows() -> list[dict[str, Any]]:
    plan.verify_candidate()
    rows = plan._read_jsonl(plan.SCHEDULE_PATH)
    plan.validate_schedule(rows)
    return rows


def _source_rows_by_key() -> dict[str, dict[str, Any]]:
    rows = public_v1._read_jsonl(public_v1.GEMINI_PUBLIC_PLAN)
    return {str(row["work_key"]): copy.deepcopy(row) for row in rows}


def verify_canary_gate() -> dict[str, Any]:
    candidate = canary_v4.verify_candidate()
    value = _read_json(canary_v4.AGGREGATE_REVIEW_PATH)
    if (
        value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("candidate_manifest_sha256")
        != candidate["manifest_sha256"]
        or value.get("matrix_continuation_eligible") is not True
        or value.get("scientific_outcomes_accessed") is not False
    ):
        raise GeminiPublicContinuationControllerV1Error(
            "Gemini public-v4 canary aggregate is not eligible"
        )
    return value


def candidate_path(segment_index: int, quota_day: str) -> Path:
    return CANDIDATE_ROOT / f"s{segment_index:04d}_{quota_day}_candidate.json"


def admission_path(segment_index: int, quota_day: str) -> Path:
    return ADMISSION_ROOT / f"s{segment_index:04d}_{quota_day}_admission.json"


def review_path_from_candidate(candidate: Mapping[str, Any]) -> Path:
    return (
        PROJECT_ROOT
        / str(candidate["scope"]["output_root"])
        / "technical_review_v1.json"
    )


def _prior_review(segment_index: int) -> dict[str, Any]:
    if segment_index == 0:
        return verify_canary_gate()
    patterns = sorted(CANDIDATE_ROOT.glob(f"s{segment_index - 1:04d}_*_candidate.json"))
    if len(patterns) != 1:
        raise GeminiPublicContinuationControllerV1Error(
            "previous continuation segment candidate is missing or ambiguous"
        )
    prior_candidate = _read_json(patterns[0])
    validate_segment_candidate(prior_candidate)
    review_path = review_path_from_candidate(prior_candidate)
    review = _read_json(review_path)
    if (
        review.get("manifest_sha256") != _manifest_sha(review)
        or review.get("technical_gate_passed") is not True
        or review.get("schedule_segment_index") != segment_index - 1
        or review.get("candidate_manifest_sha256")
        != prior_candidate["manifest_sha256"]
    ):
        raise GeminiPublicContinuationControllerV1Error(
            "previous continuation segment is not technically admitted"
        )
    return review


def canonical_segment_command(segment_index: int, quota_day: str) -> str:
    path = admission_path(segment_index, quota_day).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.gemini_public_continuation_controller_v1 "
        f"--execute-segment --segment-index {segment_index} "
        f"--quota-day {quota_day} --admission {path} "
        r"--config config\project.local.env"
    )


def build_segment_candidate(
    segment_index: int,
    *,
    quota_day: str,
    generated_at: str,
) -> dict[str, Any]:
    schedule = _schedule_rows()
    if segment_index not in range(len(schedule)):
        raise GeminiPublicContinuationControllerV1Error(
            "continuation segment index is out of range"
        )
    if quota_day != daily_quota.current_quota_day():
        raise GeminiPublicContinuationControllerV1Error(
            "continuation candidate must bind the current provider quota day"
        )
    gate = _prior_review(segment_index)
    segment = copy.deepcopy(schedule[segment_index])
    source = _source_rows_by_key()
    work_items = [copy.deepcopy(source[str(key)]) for key in segment["work_keys"]]
    identity = sha256_canonical_json(
        {
            "schema_version": SCHEMA_VERSION,
            "schedule_segment_sha256": segment["segment_sha256"],
            "quota_day": quota_day,
            "prior_review_manifest_sha256": gate["manifest_sha256"],
        }
    )
    for row in work_items:
        row["execution_identity"] = identity
    output = OUTPUT_BASE / f"s{segment_index:04d}-{quota_day}-{identity}"
    scope = {
        "schedule_segment_index": segment_index,
        "logical_shard_index": segment["logical_shard_index"],
        "quota_day": quota_day,
        "provider_id": "gemini",
        "model_id": MODEL_ID,
        "model_role": "second",
        "run_id": f"paper-v2-gemini-public-continuation-s{segment_index:04d}-{quota_day}",
        "execution_identity": identity,
        "output_root": _display_path(output),
        "work_items": work_items,
        "work_keys": [str(row["work_key"]) for row in work_items],
        "work_key_sequence_sha256": segment["work_key_sequence_sha256"],
        "record_count": segment["record_count"],
        "maximum_provider_requests": segment["maximum_provider_requests"],
        "prior_review_manifest_sha256": gate["manifest_sha256"],
        "billing_tier": "free",
        "paid_ceiling_usd": 0.0,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "one_quota_day_gemini_public_continuation_candidate",
        "generated_at": generated_at,
        "status": "offline_bound_execution_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [
            _lock(Path(__file__)),
            _lock(Path(canary_v4.__file__)),
            _lock(plan.CANDIDATE_PATH),
            _lock(plan.SCHEDULE_PATH),
            _lock(canary_v4.AGGREGATE_REVIEW_PATH)
            if segment_index == 0
            else _lock(review_path_from_candidate(_read_json(sorted(
                CANDIDATE_ROOT.glob(f"s{segment_index - 1:04d}_*_candidate.json")
            )[0]))),
        ],
        "authorization": {
            "candidate_only": True,
            "segment_execution_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_read": 0,
            "terminal_work_keys_replayed": 0,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_segment_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicContinuationControllerV1Error(
            "continuation segment candidate must be an object"
        )
    scope = value.get("scope")
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != sha256_canonical_json(core)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("provider_id") != "gemini"
        or scope.get("model_id") != MODEL_ID
        or scope.get("billing_tier") != "free"
        or scope.get("paid_ceiling_usd") != 0.0
        or scope.get("automatic_retries") != 0
        or scope.get("provider_tools_enabled") is not False
        or scope.get("external_effects_enabled") is not False
        or scope.get("maximum_provider_requests", 99)
        > daily_quota.LOCAL_REQUEST_CAP
        or scope.get("record_count") != len(scope.get("work_items", []))
        or scope.get("work_keys")
        != [str(row.get("work_key")) for row in scope.get("work_items", [])]
        or scope.get("work_key_sequence_sha256")
        != sha256_canonical_json(scope.get("work_keys", []))
        or any(
            row.get("execution_identity") != scope.get("execution_identity")
            for row in scope.get("work_items", [])
        )
        or value.get("authorization", {}).get("segment_execution_authorized")
        is not False
    ):
        raise GeminiPublicContinuationControllerV1Error(
            "continuation segment candidate drift"
        )
    for lock in value.get("artifact_locks", []):
        _verify_lock(lock)
    return copy.deepcopy(dict(value))


def write_segment_candidate(
    segment_index: int, *, quota_day: str, generated_at: str
) -> dict[str, Any]:
    path = candidate_path(segment_index, quota_day)
    if path.exists():
        raise GeminiPublicContinuationControllerV1Error(
            "continuation segment candidate already exists"
        )
    value = build_segment_candidate(
        segment_index, quota_day=quota_day, generated_at=generated_at
    )
    output = PROJECT_ROOT / str(value["scope"]["output_root"])
    if output.exists() and any(output.rglob("*")):
        raise GeminiPublicContinuationControllerV1Error(
            "continuation segment output root is not fresh"
        )
    _write_json(path, value)
    return value


def verify_segment_candidate(segment_index: int, quota_day: str) -> dict[str, Any]:
    value = validate_segment_candidate(_read_json(candidate_path(segment_index, quota_day)))
    expected = build_segment_candidate(
        segment_index,
        quota_day=quota_day,
        generated_at=str(value.get("generated_at", "")),
    )
    if value != expected:
        raise GeminiPublicContinuationControllerV1Error(
            "continuation segment candidate source drift"
        )
    return value


def build_segment_admission(
    segment_index: int,
    *,
    quota_day: str,
    approved_at: str,
    owner_statement_sha256: str,
) -> dict[str, Any]:
    candidate = verify_segment_candidate(segment_index, quota_day)
    if owner_statement_sha256 != OWNER_STATEMENT_SHA256:
        raise GeminiPublicContinuationControllerV1Error(
            "Gemini continuation owner statement drift"
        )
    command = canonical_segment_command(segment_index, quota_day)
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "one_exact_gemini_public_quota_day_authorization",
        "approved_at": approved_at,
        "status": "activated_for_one_exact_free_tier_quota_day",
        "quota_day": quota_day,
        "schedule_segment_index": segment_index,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "owner_statement_sha256": owner_statement_sha256,
        "exact_command": command,
        "exact_command_sha256": hashlib.sha256(command.encode()).hexdigest(),
        "run_id": candidate["scope"]["run_id"],
        "execution_identity": candidate["scope"]["execution_identity"],
        "maximum_provider_requests": candidate["scope"][
            "maximum_provider_requests"
        ],
        "authorization": {
            "segment_execution_authorized": True,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "result_admission_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_segment_admission(
    segment_index: int,
    *,
    quota_day: str,
    approved_at: str,
    owner_statement_sha256: str,
) -> dict[str, Any]:
    path = admission_path(segment_index, quota_day)
    if path.exists():
        raise GeminiPublicContinuationControllerV1Error(
            "continuation segment admission already exists"
        )
    value = build_segment_admission(
        segment_index,
        quota_day=quota_day,
        approved_at=approved_at,
        owner_statement_sha256=owner_statement_sha256,
    )
    _write_json(path, value)
    return value


def validate_segment_admission(
    value: Any, *, segment_index: int, quota_day: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicContinuationControllerV1Error(
            "continuation segment admission must be object"
        )
    expected = build_segment_admission(
        segment_index,
        quota_day=quota_day,
        approved_at=str(value.get("approved_at", "")),
        owner_statement_sha256=str(value.get("owner_statement_sha256", "")),
    )
    if dict(value) != expected:
        raise GeminiPublicContinuationControllerV1Error(
            "continuation segment admission drift"
        )
    return copy.deepcopy(dict(value))


def _permit(
    segment_index: int, *, quota_day: str, selected_admission: Path
) -> public_v1.GeminiPublicPermit:
    expected = admission_path(segment_index, quota_day)
    if selected_admission.resolve() != expected.resolve():
        raise GeminiPublicContinuationControllerV1Error(
            "continuation admission path is not frozen"
        )
    admission = validate_segment_admission(
        _read_json(selected_admission),
        segment_index=segment_index,
        quota_day=quota_day,
    )
    candidate = verify_segment_candidate(segment_index, quota_day)
    output = PROJECT_ROOT / str(candidate["scope"]["output_root"])
    return public_v1.GeminiPublicPermit(
        run_id=str(candidate["scope"]["run_id"]),
        execution_identity=str(candidate["scope"]["execution_identity"]),
        work_items=tuple(copy.deepcopy(candidate["scope"]["work_items"])),
        output_root=output,
        record_ledger_path=output / "experiment_records_v1.jsonl",
        attempt_ledger_path=output / "attempt_events_v1.jsonl",
        call_ledger_path=output / "provider_call_events_v1.jsonl",
        trace_root=output / "provider_traces",
        admission_file_sha256=_sha256_file(selected_admission),
        max_tokens=canary_v4.verify_candidate()["scope"]["max_tokens"],
        timeout_seconds=canary_v4.verify_candidate()["scope"]["timeout_seconds"],
        candidate=copy.deepcopy(candidate),
        admission=copy.deepcopy(admission),
    )


def execute_segment(
    segment_index: int,
    *,
    quota_day: str,
    selected_admission: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] = canary_v4._build_dispatcher,
) -> dict[str, Any]:
    permit = _permit(
        segment_index,
        quota_day=quota_day,
        selected_admission=selected_admission,
    )
    initial = public_v1._state(permit)
    if initial["records"] or initial["attempts"] or initial["calls"]:
        raise GeminiPublicContinuationControllerV1Error(
            "continuation segment already started; automatic retry forbidden"
        )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    maximum = int(permit.admission["maximum_provider_requests"])
    policy = canary_v4._daily_policy(maximum)
    public_v1.fallback._validate_runtime_config(values, policy)
    api_key = str(values[public_v1.PROVIDER_CONFIG["gemini"]["api_key"]])
    reservation = daily_quota.reserve_formal_day(
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        workload=f"public_continuation_segment_{segment_index}",
        maximum_provider_requests=maximum,
        admission_file_sha256=permit.admission_file_sha256,
        quota_day=quota_day,
        reserved_at=_now(),
        declared_other_project_requests=0,
    )
    call_sink = public_v1.fallback.GeminiCallLedgerSink(
        permit.call_ledger_path,
        execution_identity=permit.execution_identity,
        model_id=MODEL_ID,
    )
    budget_state = ProviderBudgetState(provider_id="gemini", policy=policy)
    dispatcher = dispatcher_factory(
        permit,
        api_key=api_key,
        policy=policy,
        call_sink=call_sink,
        budget_state=budget_state,
    )
    keys = {str(item["work_key"]) for item in permit.work_items}
    completed = 0
    for compact in permit.work_items:
        try:
            budget_state.assert_before_request()
        except ProviderPausedError:
            break
        work_key = str(compact["work_key"])
        public_v1.matrix_v1._append_attempt_event(
            permit.attempt_ledger_path,
            run_id=permit.run_id,
            execution_identity=permit.execution_identity,
            known_work_keys=keys,
            work_key=work_key,
            event_type="started",
            record_entry_sha256=None,
        )
        work_item, online_state = hydrate_public_work_item(compact)
        result = dict(dispatcher.execute(work_item, online_state))
        result["admission_manifest_sha256"] = permit.admission_file_sha256
        entry = append_execution_result(
            permit.record_ledger_path,
            work_items=permit.work_items,
            work_item=work_item,
            initial_online_state=online_state,
            execution_result=result,
            execution_identity=permit.execution_identity,
            run_id=permit.run_id,
        )
        tier = str(entry["record"]["result_tier"])
        public_v1.matrix_v1._append_attempt_event(
            permit.attempt_ledger_path,
            run_id=permit.run_id,
            execution_identity=permit.execution_identity,
            known_work_keys=keys,
            work_key=work_key,
            event_type="diagnostic" if tier == "diagnostic" else "completed",
            record_entry_sha256=str(entry["entry_sha256"]),
        )
        completed += 1
    final = public_v1._state(permit)
    return {
        "status": (
            "gemini_public_continuation_segment_complete_unadmitted"
            if not final["pending"]
            else "gemini_public_continuation_segment_sealed"
        ),
        "schedule_segment_index": segment_index,
        "quota_day": quota_day,
        "quota_reservation_sha256": reservation["event_sha256"],
        "record_count": len(final["records"]),
        "remaining_records": len(final["pending"]),
        "provider_calls_completed": final["call_status"]["completed_calls"],
        "completed_this_process": completed,
        "billing_tier": "free",
        "charged_usd": 0.0,
        "paid_ceiling_usd": 0.0,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "result_admission_authorized": False,
    }


def build_technical_review(segment_index: int, *, quota_day: str) -> dict[str, Any]:
    candidate = verify_segment_candidate(segment_index, quota_day)
    permit = _permit(
        segment_index,
        quota_day=quota_day,
        selected_admission=admission_path(segment_index, quota_day),
    )
    state = public_v1._state(permit)
    records = state["records"]
    calls = int(state["call_status"]["completed_calls"])
    expected = int(candidate["scope"]["maximum_provider_requests"])
    bundles = [entry["record"]["provider_trace_bundle"] for entry in records]
    trace_calls = sum(
        int(bundle["completed_request_count"]) for bundle in bundles
    )
    checks = {
        "exact_record_count": len(records) == len(permit.work_items),
        "all_attempts_terminal": not state["attempt_status"]["open_work_keys"],
        "all_call_attempts_terminal": state["call_status"]["open_attempts"] == 0,
        "all_records_itt_terminal": all(
            entry["record"]["result_tier"] in {"formal_candidate", "diagnostic"}
            for entry in records
        ),
        "provider_call_cap_respected": calls <= expected,
        "call_ledger_matches_trace_bundles": calls == trace_calls,
        "all_trace_bundles_provider_bound": all(
            bundle["provider_id"] == "gemini" and bundle["model_id"] == MODEL_ID
            for bundle in bundles
        ),
        "all_free_tier_zero_charge": all(
            bundle["usage_summary"]["billing_tier"] == "free"
            and bundle["usage_summary"]["charged_usd"] == 0.0
            and bundle["usage_summary"]["paid_ceiling_usd"] == 0.0
            for bundle in bundles
        ),
        "provider_tools_disabled": True,
        "external_effects_disabled": True,
        "scientific_outcomes_not_accessed": True,
    }
    passed = all(checks.values())
    core = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "artifact_role": "outcome_blind_gemini_public_continuation_review",
        "reviewed_at": _now(),
        "status": (
            "gemini_public_continuation_segment_technical_gate_pass"
            if passed
            else "gemini_public_continuation_segment_technical_gate_fail"
        ),
        "schedule_segment_index": segment_index,
        "quota_day": quota_day,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "admission_file_sha256": _sha256_file(
            admission_path(segment_index, quota_day)
        ),
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "expected_records": len(permit.work_items),
        "observed_records": len(records),
        "provider_calls_completed": calls,
        "provider_trace_calls_completed": trace_calls,
        "maximum_provider_requests": expected,
        "work_keys": [str(item["work_key"]) for item in permit.work_items],
        "result_tier_counts": {
            "formal_candidate": sum(
                entry["record"]["result_tier"] == "formal_candidate"
                for entry in records
            ),
            "diagnostic": sum(
                entry["record"]["result_tier"] == "diagnostic"
                for entry in records
            ),
        },
        "checks": checks,
        "technical_gate_passed": passed,
        "scientific_outcomes_accessed": False,
        "result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_technical_review(segment_index: int, *, quota_day: str) -> dict[str, Any]:
    candidate = verify_segment_candidate(segment_index, quota_day)
    path = review_path_from_candidate(candidate)
    if path.exists():
        raise GeminiPublicContinuationControllerV1Error(
            "continuation technical review already exists"
        )
    value = build_technical_review(segment_index, quota_day=quota_day)
    _write_json(path, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-segment", action="store_true")
    action.add_argument("--write-technical-review", action="store_true")
    parser.add_argument("--segment-index", type=int, required=True)
    parser.add_argument("--quota-day", required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--approved-at")
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    selected = args.admission or admission_path(args.segment_index, args.quota_day)
    if args.write_candidate:
        if not args.generated_at:
            parser.error("candidate requires --generated-at")
        value = write_segment_candidate(
            args.segment_index,
            quota_day=args.quota_day,
            generated_at=args.generated_at,
        )
    elif args.verify_candidate:
        value = verify_segment_candidate(args.segment_index, args.quota_day)
    elif args.write_admission:
        if not args.approved_at or not args.owner_statement_sha256:
            parser.error("admission requires approval time and owner digest")
        value = write_segment_admission(
            args.segment_index,
            quota_day=args.quota_day,
            approved_at=args.approved_at,
            owner_statement_sha256=args.owner_statement_sha256,
        )
    elif args.verify_admission:
        value = validate_segment_admission(
            _read_json(selected),
            segment_index=args.segment_index,
            quota_day=args.quota_day,
        )
    elif args.execute_segment:
        value = execute_segment(
            args.segment_index,
            quota_day=args.quota_day,
            selected_admission=selected,
            config_path=args.config,
        )
    else:
        value = write_technical_review(
            args.segment_index, quota_day=args.quota_day
        )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
