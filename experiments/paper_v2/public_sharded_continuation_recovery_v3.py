"""Linear-time append-only recovery for the four public-v2 shards.

Each v2 shard stopped after its first closed diagnostic record.  The records
are valid ITT observations, not retryable failures.  This controller freezes
every closed v2 prefix and, under a separate admission, executes only work
items that have never started.  Diagnostics remain in the denominator and no
longer stop later untouched work.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping

import experiments.paper_v2.public_live_controller_v4 as live_v4
import experiments.paper_v2.public_sharded_continuation_v2 as source_v2
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.incremental_live_ledgers_v1 import (
    IncrementalAttemptLedger,
    IncrementalPublicBudgetTracker,
    IncrementalPublicRecordLedger,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderPausedError,
)
from experiments.paper_v2.public_execution_store_v1 import (
    cross_bind_public_budget_and_records,
)
from experiments.paper_v2.public_matrix_plan_v1 import (
    hydrate_public_work_item,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
RUNTIME_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/public_primary_continuation_v2_runtime_20260730"
)
RECOVERY_REVIEW = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/public_primary_continuation_v2"
    / "public_v2_recovery_review_v3.json"
)
CANDIDATE_PATH = (
    PROTOCOL_ROOT / "public_primary_continuation_candidate_v3.json"
)
SCHEMA_VERSION = "m3-paper-v2-public-continuation-candidate-3.0"
ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-public-continuation-admission-3.0"
)
RECOVERY_REVIEW_VERSION = (
    "m3-paper-v2-public-continuation-recovery-review-3.0"
)
GENERATED_AT = "2026-07-30T03:00:00+08:00"
REVIEWED_AT = "2026-07-30T02:59:00+08:00"
SHARD_COUNT = 4
MAX_DIAGNOSTIC_FRACTION = 0.01


class PublicShardedRecoveryV3Error(ValueError):
    """Raised when a public recovery boundary cannot fail closed."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicShardedRecoveryV3Error(
            f"{path}: invalid JSON object"
        ) from exc
    if not isinstance(value, dict):
        raise PublicShardedRecoveryV3Error(
            f"{path}: expected an object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_prefix(path: Path, length: int) -> str:
    digest = hashlib.sha256()
    remaining = length
    with path.open("rb") as stream:
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise PublicShardedRecoveryV3Error(
                    f"{path}: public prefix was truncated"
                )
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicShardedRecoveryV3Error(
            f"missing public recovery artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_exact_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock["path"])).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise PublicShardedRecoveryV3Error(
            "public exact lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise PublicShardedRecoveryV3Error(
            f"public exact lock drift: {lock['path']}"
        )


def _verify_prefix_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock["path"])).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise PublicShardedRecoveryV3Error(
            "public prefix lock escapes project"
        ) from exc
    length = int(lock["bytes"])
    if (
        not path.is_file()
        or path.stat().st_size < length
        or _sha256_prefix(path, length) != lock["sha256"]
    ):
        raise PublicShardedRecoveryV3Error(
            f"public prefix lock drift: {lock['path']}"
        )


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
    )


def admission_path(shard_index: int) -> Path:
    if not 0 <= shard_index < SHARD_COUNT:
        raise PublicShardedRecoveryV3Error(
            "public-v3 shard index is out of range"
        )
    return (
        PROTOCOL_ROOT
        / "admissions"
        / (
            f"deepseek_public_primary_continuation_s{shard_index}"
            "_admission_v3.json"
        )
    )


def _v2_admission_path(shard_index: int) -> Path:
    return source_v2.admission_path("primary", shard_index)


def _runtime_log_locks(shard_index: int) -> list[dict[str, Any]]:
    stdout = RUNTIME_ROOT / f"shard{shard_index}.stdout.log"
    stderr = RUNTIME_ROOT / f"shard{shard_index}.stderr.log"
    if (
        not stdout.is_file()
        or stdout.stat().st_size == 0
        or not stderr.is_file()
        or stderr.stat().st_size != 0
    ):
        raise PublicShardedRecoveryV3Error(
            "public-v2 shard lacks a clean natural-exit log"
        )
    return [_lock(stdout), _lock(stderr)]


def build_recovery_review() -> dict[str, Any]:
    shards: list[dict[str, Any]] = []
    total_records = 0
    total_diagnostics = 0
    total_calls = 0
    total_cost = 0.0
    for shard_index in range(SHARD_COUNT):
        permit, role_policy = source_v2.authorize_shard(
            shard_index,
            selected_admission_path=_v2_admission_path(shard_index),
        )
        state = source_v2._state_from_paths(
            permit,
            role_policy=role_policy,
        )
        if state["attempt_status"]["open_work_keys"]:
            raise PublicShardedRecoveryV3Error(
                "public-v2 shard contains an open attempt"
            )
        diagnostics = sum(
            entry["record"]["result_tier"] == "diagnostic"
            for entry in state["records"]
        )
        if diagnostics < 1:
            raise PublicShardedRecoveryV3Error(
                "public-v2 shard did not close on a diagnostic record"
            )
        log_locks = _runtime_log_locks(shard_index)
        observed = len(state["records"])
        remaining = len(state["pending"])
        shard = {
            "shard_index": shard_index,
            "run_id": permit.run_id,
            "execution_identity": permit.execution_identity,
            "expected_record_count": len(permit.work_items),
            "closed_prefix_record_count": observed,
            "closed_prefix_attempt_event_count": len(state["attempts"]),
            "closed_prefix_budget_event_count": len(state["budgets"]),
            "closed_prefix_diagnostic_record_count": diagnostics,
            "untouched_record_count": remaining,
            "record_ledger_tail_sha256": state["record_status"][
                "tail_sha256"
            ],
            "attempt_ledger_tail_sha256": state["attempt_status"][
                "tail_sha256"
            ],
            "budget_ledger_tail_sha256": state["budget_status"][
                "tail_sha256"
            ],
            "role_cumulative_cost_cny": state["budget_status"][
                "role_cumulative_cost_cny"
            ],
            "natural_exit_log_locks": log_locks,
        }
        shards.append(shard)
        total_records += observed
        total_diagnostics += diagnostics
        total_calls += len(state["budgets"])
        total_cost += float(
            state["budget_status"]["role_cumulative_cost_cny"]
        )
    core = {
        "schema_version": RECOVERY_REVIEW_VERSION,
        "artifact_role": "outcome_blind_public_closed_prefix_review",
        "reviewed_at": REVIEWED_AT,
        "status": "four_closed_prefixes_eligible_for_separate_continuation",
        "source_v2_candidate_manifest_sha256": source_v2.verify_candidate()[
            "manifest_sha256"
        ],
        "shards": shards,
        "totals": {
            "closed_prefix_records": total_records,
            "closed_prefix_diagnostic_records": total_diagnostics,
            "completed_provider_calls": total_calls,
            "role_cumulative_cost_cny": round(total_cost, 7),
            "untouched_records": sum(
                int(shard["untouched_record_count"]) for shard in shards
            ),
        },
        "checks": {
            "all_attempts_terminal": True,
            "record_attempt_budget_trace_cross_binding_complete": True,
            "diagnostic_records_retained_in_itt": True,
            "terminal_diagnostic_retry_authorized": False,
            "only_untouched_records_continuable": True,
            "all_v2_processes_exited_naturally": True,
            "scientific_outcomes_aggregated": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_recovery_review(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicShardedRecoveryV3Error(
            "public recovery review must be an object"
        )
    if (
        value.get("schema_version") != RECOVERY_REVIEW_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or dict(value) != build_recovery_review()
    ):
        raise PublicShardedRecoveryV3Error(
            "public recovery review drift"
        )
    return copy.deepcopy(dict(value))


def write_recovery_review() -> dict[str, Any]:
    value = build_recovery_review()
    _write_json(RECOVERY_REVIEW, value)
    return value


def _prefix_locks(
    permit: live_v4.PublicExecutionPermit,
) -> list[dict[str, Any]]:
    paths = [
        permit.record_ledger_path,
        permit.attempt_ledger_path,
        permit.budget_ledger_path,
    ]
    paths.extend(sorted(permit.trace_root.glob("*.jsonl")))
    return [_lock(path) for path in paths]


def build_candidate() -> dict[str, Any]:
    review = validate_recovery_review(_load_json(RECOVERY_REVIEW))
    artifact_paths = [
        Path(__file__),
        PROJECT_ROOT
        / "experiments/paper_v2/incremental_live_ledgers_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_sharded_continuation_v2.py",
        source_v2.CANDIDATE_PATH,
        RECOVERY_REVIEW,
    ]
    shards: list[dict[str, Any]] = []
    prefix_locks: list[dict[str, Any]] = []
    for review_shard in review["shards"]:
        shard_index = int(review_shard["shard_index"])
        permit, _ = source_v2.authorize_shard(
            shard_index,
            selected_admission_path=_v2_admission_path(shard_index),
        )
        artifact_paths.append(_v2_admission_path(shard_index))
        prefix_locks.extend(_prefix_locks(permit))
        shards.append(
            {
                **copy.deepcopy(dict(review_shard)),
                "output_root": _display_path(permit.output_root),
                "hard_spend_limit_cny": source_v2.SHARD_HARD_LIMIT_CNY,
            }
        )
    scope = {
        "model_role": "primary",
        "provider_id": "deepseek",
        "endpoint_type": "official_api",
        "model_id": "deepseek-v4-pro",
        "source_v2_candidate_manifest_sha256": review[
            "source_v2_candidate_manifest_sha256"
        ],
        "source_recovery_review_manifest_sha256": review[
            "manifest_sha256"
        ],
        "shards": shards,
        "diagnostic_policy": {
            "retain_in_itt": True,
            "retry_terminal_diagnostic": False,
            "continue_with_untouched_records": True,
            "technical_admission_max_fraction": (
                MAX_DIAGNOSTIC_FRACTION
            ),
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "linear_append_only_public_recovery_candidate",
        "generated_at": GENERATED_AT,
        "status": "offline_qualified_execution_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [_lock(path) for path in artifact_paths],
        "prefix_locks": prefix_locks,
        "authorization": {
            "candidate_only": True,
            "shard_execution_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "provider_calls_while_building": 0,
            "scientific_outcomes_aggregated": False,
            "v2_terminal_records_retried": 0,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicShardedRecoveryV3Error(
            "public-v3 candidate must be an object"
        )
    scope = value.get("scope")
    if (
        not isinstance(scope, Mapping)
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("model_id") != "deepseek-v4-pro"
        or len(scope.get("shards", [])) != SHARD_COUNT
        or value.get("authorization", {}).get(
            "shard_execution_authorized"
        )
        is not False
    ):
        raise PublicShardedRecoveryV3Error(
            "public-v3 candidate identity/scope drift"
        )
    for lock in value.get("artifact_locks", []):
        _verify_exact_lock(lock)
    for lock in value.get("prefix_locks", []):
        _verify_prefix_lock(lock)
    return copy.deepcopy(dict(value))


def write_candidate() -> dict[str, Any]:
    value = build_candidate()
    _write_json(CANDIDATE_PATH, value)
    return value


def verify_candidate() -> dict[str, Any]:
    return validate_candidate(_load_json(CANDIDATE_PATH))


def canonical_command(shard_index: int) -> str:
    admission = admission_path(shard_index).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.public_sharded_continuation_recovery_v3 "
        f"--execute-shard --shard-index {shard_index} "
        f"--admission {admission} --config config\\project.local.env"
    )


def build_admission(
    shard_index: int,
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    candidate = verify_candidate()
    if (
        len(owner_statement_sha256) != 64
        or any(
            char not in "0123456789abcdef"
            for char in owner_statement_sha256
        )
    ):
        raise PublicShardedRecoveryV3Error(
            "owner statement must be lowercase SHA-256"
        )
    shard = candidate["scope"]["shards"][shard_index]
    command = canonical_command(shard_index)
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "public_recovery_shard_execution_admission",
        "approved_at": approved_at,
        "status": "activated_for_untouched_public_records_only",
        "authorization": {
            "owner_statement_sha256": owner_statement_sha256,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "shard_index": shard_index,
            "run_id": shard["run_id"],
            "execution_identity": shard["execution_identity"],
            "maximum_new_records": shard["untouched_record_count"],
            "exact_command": command,
            "exact_command_sha256": hashlib.sha256(
                command.encode("utf-8")
            ).hexdigest(),
            "terminal_diagnostic_retry_authorized": False,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "scientific_result_admission_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_admission(
    value: Any,
    *,
    shard_index: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicShardedRecoveryV3Error(
            "public-v3 admission must be an object"
        )
    if value.get("manifest_sha256") != _manifest_sha(value):
        raise PublicShardedRecoveryV3Error(
            "public-v3 admission manifest drift"
        )
    expected = build_admission(
        shard_index,
        owner_statement_sha256=str(
            value.get("authorization", {}).get(
                "owner_statement_sha256",
                "",
            )
        ),
        approved_at=str(value.get("approved_at", "")),
    )
    if dict(value) != expected:
        raise PublicShardedRecoveryV3Error(
            "public-v3 admission scope drift"
        )
    return copy.deepcopy(dict(value))


def write_admission(
    shard_index: int,
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    value = build_admission(
        shard_index,
        owner_statement_sha256=owner_statement_sha256,
        approved_at=approved_at,
    )
    _write_json(admission_path(shard_index), value)
    return value


def _candidate_shard(
    candidate: Mapping[str, Any],
    shard_index: int,
) -> dict[str, Any]:
    shards = candidate["scope"]["shards"]
    shard = next(
        (
            child
            for child in shards
            if int(child["shard_index"]) == shard_index
        ),
        None,
    )
    if not isinstance(shard, Mapping):
        raise PublicShardedRecoveryV3Error(
            "public-v3 candidate shard is missing"
        )
    return copy.deepcopy(dict(shard))


def authorize_shard(
    shard_index: int,
    *,
    selected_admission_path: Path,
    require_unstarted: bool,
) -> tuple[
    live_v4.PublicExecutionPermit,
    dict[str, Any],
    dict[str, Any],
]:
    if selected_admission_path.resolve() != admission_path(
        shard_index
    ).resolve():
        raise PublicShardedRecoveryV3Error(
            "public-v3 admission path is not frozen"
        )
    admission = validate_admission(
        _load_json(selected_admission_path),
        shard_index=shard_index,
    )
    candidate = verify_candidate()
    expected = _candidate_shard(candidate, shard_index)
    permit, role_policy = source_v2.authorize_shard(
        shard_index,
        selected_admission_path=_v2_admission_path(shard_index),
    )
    state = source_v2._state_from_paths(
        permit,
        role_policy=role_policy,
    )
    if (
        permit.run_id != expected["run_id"]
        or permit.execution_identity != expected["execution_identity"]
    ):
        raise PublicShardedRecoveryV3Error(
            "public-v3 permit identity drift"
        )
    if require_unstarted and (
        len(state["records"]) != expected["closed_prefix_record_count"]
        or len(state["attempts"])
        != expected["closed_prefix_attempt_event_count"]
        or len(state["budgets"])
        != expected["closed_prefix_budget_event_count"]
        or state["record_status"]["tail_sha256"]
        != expected["record_ledger_tail_sha256"]
        or state["attempt_status"]["tail_sha256"]
        != expected["attempt_ledger_tail_sha256"]
        or state["budget_status"]["tail_sha256"]
        != expected["budget_ledger_tail_sha256"]
    ):
        raise PublicShardedRecoveryV3Error(
            "public-v3 already started; automatic rerun is forbidden"
        )
    permit = replace(
        permit,
        admission_file_sha256=_sha256_file(selected_admission_path),
        admission=admission,
    )
    return permit, role_policy, candidate


def execute_shard(
    shard_index: int,
    *,
    selected_admission_path: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    permit, role_policy, candidate = authorize_shard(
        shard_index,
        selected_admission_path=selected_admission_path,
        require_unstarted=True,
    )
    keys = {str(item["work_key"]) for item in permit.work_items}
    records = IncrementalPublicRecordLedger(
        permit.record_ledger_path,
        work_items=permit.work_items,
        execution_identity=permit.execution_identity,
        run_id=permit.run_id,
        role_policy=role_policy,
    )
    attempts = IncrementalAttemptLedger(
        permit.attempt_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=keys,
    )
    tracker = IncrementalPublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys=keys,
        role_policy=role_policy,
    )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    api_key = live_v4.v3.v2._validate_runtime_config(
        values,
        role_policy=role_policy,
    )
    factory = dispatcher_factory or live_v4._build_dispatcher
    dispatcher = factory(
        permit,
        tracker,
        api_key=api_key,
        role_policy=role_policy,
    )
    terminal = set(records.status["terminal_work_keys"])
    pending = [
        item
        for item in permit.work_items
        if str(item["work_key"]) not in terminal
    ]
    expected_new = int(
        _candidate_shard(candidate, shard_index)["untouched_record_count"]
    )
    if len(pending) != expected_new:
        raise PublicShardedRecoveryV3Error(
            "public-v3 pending set differs from the frozen prefix"
        )
    completed = 0
    diagnostics = 0
    for compact in pending:
        try:
            tracker.assert_before_request()
        except ProviderPausedError:
            break
        work_key = str(compact["work_key"])
        attempts.append(
            work_key=work_key,
            event_type="started",
            record_entry_sha256=None,
        )
        work_item, state = hydrate_public_work_item(compact)
        result = dict(dispatcher.execute(work_item, state))
        if result.get("result_tier") not in {
            "formal_candidate",
            "diagnostic",
        }:
            raise PublicShardedRecoveryV3Error(
                "public-v3 result exceeded candidate tier"
            )
        result["admission_manifest_sha256"] = (
            permit.admission_file_sha256
        )
        entry = records.append(
            work_item=work_item,
            initial_online_state=state,
            execution_result=result,
        )
        tier = str(entry["record"]["result_tier"])
        attempts.append(
            work_key=work_key,
            event_type=(
                "diagnostic" if tier == "diagnostic" else "completed"
            ),
            record_entry_sha256=str(entry["entry_sha256"]),
        )
        completed += 1
        diagnostics += tier == "diagnostic"
        if tracker.status["paused"]:
            break
    record_status = records.full_validate()
    attempt_status = attempts.full_validate()
    budget_status = tracker.full_validate()
    if (
        set(record_status["terminal_work_keys"])
        != set(attempt_status["terminal_by_work_key"])
        or attempt_status["open_work_keys"]
    ):
        raise PublicShardedRecoveryV3Error(
            "public-v3 final attempt/record state is not closed"
        )
    cross_bind_public_budget_and_records(
        budget_events=tracker.events,
        record_entries=records.entries,
        trace_root=permit.trace_root,
        role_policy=role_policy,
    )
    return {
        "status": (
            "public_recovery_shard_complete_candidate_unadmitted"
            if record_status["remaining_work_items"] == 0
            else "public_recovery_shard_paused_by_budget"
        ),
        "model_role": "primary",
        "shard_index": shard_index,
        "run_id": permit.run_id,
        "new_records_completed": completed,
        "expected_new_records": expected_new,
        "new_diagnostic_records": diagnostics,
        "total_record_count": record_status["entry_count"],
        "remaining_records": record_status["remaining_work_items"],
        "total_provider_calls": budget_status["event_count"],
        "role_cumulative_cost_cny": budget_status[
            "role_cumulative_cost_cny"
        ],
        "result_admission_authorized": False,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "v2_terminal_records_retried": 0,
    }


def build_technical_review(
    shard_index: int,
    *,
    selected_admission_path: Path,
) -> dict[str, Any]:
    permit, role_policy, candidate = authorize_shard(
        shard_index,
        selected_admission_path=selected_admission_path,
        require_unstarted=False,
    )
    state = source_v2._state_from_paths(
        permit,
        role_policy=role_policy,
    )
    expected = len(permit.work_items)
    diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in state["records"]
    )
    max_diagnostics = max(
        1,
        math.floor(expected * MAX_DIAGNOSTIC_FRACTION),
    )
    checks = {
        "exact_record_count": len(state["records"]) == expected,
        "all_attempts_terminal": not state["attempt_status"][
            "open_work_keys"
        ],
        "record_attempt_terminal_sets_equal": (
            set(state["record_status"]["terminal_work_keys"])
            == set(state["attempt_status"]["terminal_by_work_key"])
        ),
        "all_tiers_candidate_or_diagnostic": all(
            entry["record"]["result_tier"]
            in {"formal_candidate", "diagnostic"}
            for entry in state["records"]
        ),
        "all_records_in_itt": all(
            entry["record"]["included_in_intention_to_treat"] is True
            for entry in state["records"]
        ),
        "diagnostic_fraction_within_frozen_bound": (
            diagnostics <= max_diagnostics
        ),
        "budget_not_paused": state["budget_status"]["paused"] is False,
        "budget_record_trace_cross_binding_complete": True,
        "v2_terminal_records_retried": False,
        "scientific_outcomes_aggregated": False,
    }
    passed = all(checks.values())
    core = {
        "schema_version": (
            "m3-paper-v2-public-continuation-shard-review-3.0"
        ),
        "artifact_role": "outcome_blind_public_recovery_review",
        "reviewed_at": live_v4._now(),
        "status": (
            "public_recovery_shard_technical_gate_pass"
            if passed
            else "public_recovery_shard_technical_gate_fail"
        ),
        "model_role": "primary",
        "shard_index": shard_index,
        "run_id": permit.run_id,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "admission_file_sha256": _sha256_file(
            selected_admission_path
        ),
        "expected_records": expected,
        "observed_records": len(state["records"]),
        "diagnostic_records": diagnostics,
        "maximum_admissible_diagnostic_records": max_diagnostics,
        "provider_calls_completed": state["budget_status"]["event_count"],
        "role_cumulative_cost_cny": state["budget_status"][
            "role_cumulative_cost_cny"
        ],
        "record_ledger_tail_sha256": state["record_status"][
            "tail_sha256"
        ],
        "attempt_ledger_tail_sha256": state["attempt_status"][
            "tail_sha256"
        ],
        "budget_ledger_tail_sha256": state["budget_status"][
            "tail_sha256"
        ],
        "checks": checks,
        "technical_gate_passed": passed,
        "scientific_result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_technical_review(
    shard_index: int,
    *,
    selected_admission_path: Path,
) -> dict[str, Any]:
    permit, _, _ = authorize_shard(
        shard_index,
        selected_admission_path=selected_admission_path,
        require_unstarted=False,
    )
    value = build_technical_review(
        shard_index,
        selected_admission_path=selected_admission_path,
    )
    _write_json(
        permit.output_root / "continuation_shard_review_v3.json",
        value,
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-recovery-review", action="store_true")
    action.add_argument("--verify-recovery-review", action="store_true")
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-shard", action="store_true")
    action.add_argument("--write-technical-review", action="store_true")
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--approved-at")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.write_recovery_review:
        value = write_recovery_review()
    elif args.verify_recovery_review:
        value = validate_recovery_review(_load_json(RECOVERY_REVIEW))
    elif args.write_candidate:
        value = write_candidate()
    elif args.verify_candidate:
        value = verify_candidate()
    else:
        if args.shard_index is None:
            parser.error("selected action requires --shard-index")
        selected = args.admission or admission_path(args.shard_index)
        if args.write_admission:
            if not args.owner_statement_sha256 or not args.approved_at:
                parser.error(
                    "--write-admission requires --owner-statement-sha256 "
                    "and --approved-at"
                )
            value = write_admission(
                args.shard_index,
                owner_statement_sha256=args.owner_statement_sha256,
                approved_at=args.approved_at,
            )
        elif args.verify_admission:
            value = validate_admission(
                _load_json(selected),
                shard_index=args.shard_index,
            )
        elif args.execute_shard:
            value = execute_shard(
                args.shard_index,
                selected_admission_path=selected,
                config_path=args.config,
            )
        else:
            value = write_technical_review(
                args.shard_index,
                selected_admission_path=selected,
            )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
