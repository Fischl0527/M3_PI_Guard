"""独立冻结并线性接续单个已关闭的公开 v2 分片。

对单个滞后分片进行单点恢复，不影响其他正常运行节点。
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
SCHEMA_VERSION = "m3-paper-v2-public-single-shard-candidate-3.0"
ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-public-single-shard-admission-3.0"
)
REVIEW_SCHEMA_VERSION = (
    "m3-paper-v2-public-single-shard-prefix-review-3.0"
)
GENERATED_AT = "2026-07-30T03:10:00+08:00"
REVIEWED_AT = "2026-07-30T03:09:00+08:00"
SHARD_COUNT = 4
MAX_DIAGNOSTIC_FRACTION = 0.01


class PublicSingleShardRecoveryV3Error(ValueError):
    """当单个公开分片无法安全闭合接续时抛出的异常。"""


def _validate_shard(shard_index: int) -> None:
    if not 0 <= shard_index < SHARD_COUNT:
        raise PublicSingleShardRecoveryV3Error(
            "public recovery shard index is out of range"
        )


def review_path(shard_index: int) -> Path:
    _validate_shard(shard_index)
    candidate = _load_json(source_v2.CANDIDATE_PATH)
    root = PROJECT_ROOT / str(
        candidate["scope"]["shards"][shard_index]["output_root"]
    )
    return root / "closed_prefix_review_v3.json"


def candidate_path(shard_index: int) -> Path:
    _validate_shard(shard_index)
    return (
        PROTOCOL_ROOT
        / f"public_primary_continuation_s{shard_index}_candidate_v3.json"
    )


def admission_path(shard_index: int) -> Path:
    _validate_shard(shard_index)
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


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicSingleShardRecoveryV3Error(
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
                raise PublicSingleShardRecoveryV3Error(
                    f"{path}: frozen prefix was truncated"
                )
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicSingleShardRecoveryV3Error(
            f"missing public shard artifact: {path}"
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
        raise PublicSingleShardRecoveryV3Error(
            "public shard exact lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise PublicSingleShardRecoveryV3Error(
            f"public shard exact lock drift: {lock['path']}"
        )


def _verify_prefix_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock["path"])).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise PublicSingleShardRecoveryV3Error(
            "public shard prefix lock escapes project"
        ) from exc
    length = int(lock["bytes"])
    if (
        not path.is_file()
        or path.stat().st_size < length
        or _sha256_prefix(path, length) != lock["sha256"]
    ):
        raise PublicSingleShardRecoveryV3Error(
            f"public shard prefix lock drift: {lock['path']}"
        )


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
    )


def _natural_exit_locks(shard_index: int) -> list[dict[str, Any]]:
    stdout = RUNTIME_ROOT / f"shard{shard_index}.stdout.log"
    stderr = RUNTIME_ROOT / f"shard{shard_index}.stderr.log"
    if (
        not stdout.is_file()
        or stdout.stat().st_size == 0
        or not stderr.is_file()
        or stderr.stat().st_size != 0
    ):
        raise PublicSingleShardRecoveryV3Error(
            "public shard lacks a clean natural-exit log"
        )
    return [_lock(stdout), _lock(stderr)]


def build_prefix_review(shard_index: int) -> dict[str, Any]:
    _validate_shard(shard_index)
    permit, role_policy = source_v2.authorize_shard(
        shard_index,
        selected_admission_path=_v2_admission_path(shard_index),
    )
    state = source_v2._state_from_paths(
        permit,
        role_policy=role_policy,
    )
    diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in state["records"]
    )
    if (
        state["attempt_status"]["open_work_keys"]
        or diagnostics < 1
        or not state["pending"]
    ):
        raise PublicSingleShardRecoveryV3Error(
            "public shard is not one closed diagnostic prefix"
        )
    log_locks = _natural_exit_locks(shard_index)
    core = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "artifact_role": "outcome_blind_closed_public_shard_review",
        "reviewed_at": REVIEWED_AT,
        "status": "closed_prefix_eligible_for_separate_continuation",
        "shard_index": shard_index,
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "source_v2_candidate_manifest_sha256": permit.candidate[
            "manifest_sha256"
        ],
        "source_v2_admission_file_sha256": permit.admission_file_sha256,
        "expected_record_count": len(permit.work_items),
        "closed_prefix_record_count": len(state["records"]),
        "closed_prefix_attempt_event_count": len(state["attempts"]),
        "closed_prefix_budget_event_count": len(state["budgets"]),
        "closed_prefix_diagnostic_record_count": diagnostics,
        "untouched_record_count": len(state["pending"]),
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
        "checks": {
            "all_attempts_terminal": True,
            "record_budget_trace_cross_binding_complete": True,
            "diagnostic_records_retained_in_itt": True,
            "terminal_diagnostic_retry_authorized": False,
            "only_untouched_records_continuable": True,
            "scientific_outcomes_aggregated": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_prefix_review(shard_index: int) -> dict[str, Any]:
    value = build_prefix_review(shard_index)
    _write_json(review_path(shard_index), value)
    return value


def _validated_frozen_review(shard_index: int) -> dict[str, Any]:
    value = _load_json(review_path(shard_index))
    if (
        value.get("schema_version") != REVIEW_SCHEMA_VERSION
        or value.get("shard_index") != shard_index
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("status")
        != "closed_prefix_eligible_for_separate_continuation"
    ):
        raise PublicSingleShardRecoveryV3Error(
            "public shard frozen review drift"
        )
    for lock in value.get("natural_exit_log_locks", []):
        _verify_exact_lock(lock)
    return copy.deepcopy(value)


def _prefix_locks_from_root(root: Path) -> list[dict[str, Any]]:
    paths = [
        root / "experiment_records.jsonl",
        root / "attempt_events.jsonl",
        root / "budget_events.jsonl",
    ]
    paths.extend(sorted((root / "provider_traces").glob("*.jsonl")))
    return [_lock(path) for path in paths]


def build_candidate(shard_index: int) -> dict[str, Any]:
    review = _validated_frozen_review(shard_index)
    root = review_path(shard_index).parent
    scope = {
        "shard_index": shard_index,
        "run_id": review["run_id"],
        "execution_identity": review["execution_identity"],
        "model_role": "primary",
        "provider_id": "deepseek",
        "endpoint_type": "official_api",
        "model_id": "deepseek-v4-pro",
        "output_root": _display_path(root),
        "expected_record_count": review["expected_record_count"],
        "closed_prefix_record_count": review[
            "closed_prefix_record_count"
        ],
        "closed_prefix_attempt_event_count": review[
            "closed_prefix_attempt_event_count"
        ],
        "closed_prefix_budget_event_count": review[
            "closed_prefix_budget_event_count"
        ],
        "closed_prefix_diagnostic_record_count": review[
            "closed_prefix_diagnostic_record_count"
        ],
        "untouched_record_count": review["untouched_record_count"],
        "record_ledger_tail_sha256": review[
            "record_ledger_tail_sha256"
        ],
        "attempt_ledger_tail_sha256": review[
            "attempt_ledger_tail_sha256"
        ],
        "budget_ledger_tail_sha256": review[
            "budget_ledger_tail_sha256"
        ],
        "hard_spend_limit_cny": source_v2.SHARD_HARD_LIMIT_CNY,
        "source_v2_candidate_manifest_sha256": review[
            "source_v2_candidate_manifest_sha256"
        ],
        "source_prefix_review_manifest_sha256": review[
            "manifest_sha256"
        ],
        "diagnostic_policy": {
            "retain_in_itt": True,
            "retry_terminal_diagnostic": False,
            "continue_with_untouched_records": True,
            "technical_admission_max_fraction": (
                MAX_DIAGNOSTIC_FRACTION
            ),
        },
    }
    artifact_paths = [
        Path(__file__),
        PROJECT_ROOT
        / "experiments/paper_v2/incremental_live_ledgers_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_sharded_continuation_v2.py",
        source_v2.CANDIDATE_PATH,
        _v2_admission_path(shard_index),
        review_path(shard_index),
    ]
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "single_public_shard_recovery_candidate",
        "generated_at": GENERATED_AT,
        "status": "offline_qualified_execution_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [_lock(path) for path in artifact_paths],
        "prefix_locks": _prefix_locks_from_root(root),
        "authorization": {
            "candidate_only": True,
            "shard_execution_authorized": False,
            "scientific_result_admission_authorized": False,
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


def write_candidate(shard_index: int) -> dict[str, Any]:
    value = build_candidate(shard_index)
    _write_json(candidate_path(shard_index), value)
    return value


def validate_candidate(
    value: Any,
    *,
    shard_index: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicSingleShardRecoveryV3Error(
            "public shard candidate must be an object"
        )
    scope = value.get("scope")
    if (
        not isinstance(scope, Mapping)
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("shard_index") != shard_index
        or value.get("authorization", {}).get(
            "shard_execution_authorized"
        )
        is not False
    ):
        raise PublicSingleShardRecoveryV3Error(
            "public shard candidate identity/scope drift"
        )
    for lock in value.get("artifact_locks", []):
        _verify_exact_lock(lock)
    for lock in value.get("prefix_locks", []):
        _verify_prefix_lock(lock)
    return copy.deepcopy(dict(value))


def verify_candidate(shard_index: int) -> dict[str, Any]:
    return validate_candidate(
        _load_json(candidate_path(shard_index)),
        shard_index=shard_index,
    )


def canonical_command(shard_index: int) -> str:
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.public_single_shard_recovery_v3 "
        f"--execute-shard --shard-index {shard_index} "
        f"--admission {admission_path(shard_index).relative_to(PROJECT_ROOT)} "
        "--config config\\project.local.env"
    )


def build_admission(
    shard_index: int,
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    candidate = verify_candidate(shard_index)
    if (
        len(owner_statement_sha256) != 64
        or any(
            char not in "0123456789abcdef"
            for char in owner_statement_sha256
        )
    ):
        raise PublicSingleShardRecoveryV3Error(
            "owner statement must be lowercase SHA-256"
        )
    command = canonical_command(shard_index)
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "single_public_shard_execution_admission",
        "approved_at": approved_at,
        "status": "activated_for_untouched_public_records_only",
        "authorization": {
            "owner_statement_sha256": owner_statement_sha256,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "shard_index": shard_index,
            "run_id": candidate["scope"]["run_id"],
            "execution_identity": candidate["scope"][
                "execution_identity"
            ],
            "maximum_new_records": candidate["scope"][
                "untouched_record_count"
            ],
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


def validate_admission(
    value: Any,
    *,
    shard_index: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicSingleShardRecoveryV3Error(
            "public shard admission must be an object"
        )
    if value.get("manifest_sha256") != _manifest_sha(value):
        raise PublicSingleShardRecoveryV3Error(
            "public shard admission manifest drift"
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
        raise PublicSingleShardRecoveryV3Error(
            "public shard admission scope drift"
        )
    return copy.deepcopy(dict(value))


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
        raise PublicSingleShardRecoveryV3Error(
            "public shard admission path is not frozen"
        )
    admission = validate_admission(
        _load_json(selected_admission_path),
        shard_index=shard_index,
    )
    candidate = verify_candidate(shard_index)
    permit, role_policy = source_v2.authorize_shard(
        shard_index,
        selected_admission_path=_v2_admission_path(shard_index),
    )
    state = source_v2._state_from_paths(
        permit,
        role_policy=role_policy,
    )
    scope = candidate["scope"]
    if require_unstarted and (
        len(state["records"]) != scope["closed_prefix_record_count"]
        or len(state["attempts"])
        != scope["closed_prefix_attempt_event_count"]
        or len(state["budgets"])
        != scope["closed_prefix_budget_event_count"]
        or state["record_status"]["tail_sha256"]
        != scope["record_ledger_tail_sha256"]
        or state["attempt_status"]["tail_sha256"]
        != scope["attempt_ledger_tail_sha256"]
        or state["budget_status"]["tail_sha256"]
        != scope["budget_ledger_tail_sha256"]
    ):
        raise PublicSingleShardRecoveryV3Error(
            "public shard already started; automatic rerun is forbidden"
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
    expected_new = int(candidate["scope"]["untouched_record_count"])
    if len(pending) != expected_new:
        raise PublicSingleShardRecoveryV3Error(
            "public shard pending set differs from frozen prefix"
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
            raise PublicSingleShardRecoveryV3Error(
                "public shard result exceeded candidate tier"
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
        raise PublicSingleShardRecoveryV3Error(
            "public shard final attempt/record state is not closed"
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
    maximum = max(
        1,
        math.floor(expected * MAX_DIAGNOSTIC_FRACTION),
    )
    positive_checks = {
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
        "diagnostic_fraction_within_frozen_bound": diagnostics <= maximum,
        "budget_not_paused": state["budget_status"]["paused"] is False,
        "budget_record_trace_cross_binding_complete": True,
    }
    negative_checks = {
        "v2_terminal_records_retried": False,
        "scientific_outcomes_aggregated": False,
    }
    passed = all(positive_checks.values()) and not any(
        negative_checks.values()
    )
    core = {
        "schema_version": (
            "m3-paper-v2-public-single-shard-technical-review-3.0"
        ),
        "artifact_role": "outcome_blind_single_public_shard_review",
        "reviewed_at": live_v4._now(),
        "status": (
            "public_recovery_shard_technical_gate_pass"
            if passed
            else "public_recovery_shard_technical_gate_fail"
        ),
        "shard_index": shard_index,
        "run_id": permit.run_id,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "admission_file_sha256": _sha256_file(
            selected_admission_path
        ),
        "expected_records": expected,
        "observed_records": len(state["records"]),
        "diagnostic_records": diagnostics,
        "maximum_admissible_diagnostic_records": maximum,
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
        "positive_checks": positive_checks,
        "negative_boundary_checks": negative_checks,
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
    action.add_argument("--write-prefix-review", action="store_true")
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-shard", action="store_true")
    action.add_argument("--write-technical-review", action="store_true")
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--approved-at")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    selected = args.admission or admission_path(args.shard_index)
    if args.write_prefix_review:
        value = write_prefix_review(args.shard_index)
    elif args.write_candidate:
        value = write_candidate(args.shard_index)
    elif args.verify_candidate:
        value = verify_candidate(args.shard_index)
    elif args.write_admission:
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
