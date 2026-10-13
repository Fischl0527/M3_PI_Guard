"""面向两个已封签 DeepSeek Flash 公开分片的对结果盲审恢复执行器。

在封签保护下安全接续执行由于配额中断的 Flash 模型评测。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping

import experiments.paper_v2.public_live_controller_v4 as live_v4
import experiments.paper_v2.public_second_continuation_v2 as source_v2
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.incremental_live_ledgers_v1 import (
    IncrementalAttemptLedger,
    IncrementalPublicBudgetTracker,
    IncrementalPublicRecordLedger,
)
from experiments.paper_v2.official_provider_executor import ProviderPausedError
from experiments.paper_v2.public_execution_store_v1 import (
    cross_bind_public_budget_and_records,
)
from experiments.paper_v2.public_matrix_plan_v1 import hydrate_public_work_item
from experiments.paper_v2.public_provider_budget_v1 import (
    build_role_policy,
    load_public_policy,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
REVIEW_PATH = PROTOCOL_ROOT / "public_second_continuation_abort_review_v3.json"
CANDIDATE_PATH = (
    PROTOCOL_ROOT / "public_second_continuation_recovery_candidate_v3.json"
)
SHARD_COUNT = 2
MODEL_ROLE = "second"
MODEL_ID = "deepseek-v4-flash"
MAX_DIAGNOSTIC_FRACTION = 0.01
ROLE_TOTAL_HARD_LIMIT_CNY = 5.0
REVIEWED_AT = "2026-08-03T13:30:00+08:00"
GENERATED_AT = "2026-08-03T13:31:00+08:00"


class PublicSecondRecoveryV3Error(ValueError):
    """当 Flash 恢复边界无法安全闭合时抛出的异常。"""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicSecondRecoveryV3Error(f"{path}: invalid JSON object") from exc
    if not isinstance(value, dict):
        raise PublicSecondRecoveryV3Error(f"{path}: expected object")
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


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicSecondRecoveryV3Error(
            f"missing Flash recovery artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock["path"])).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise PublicSecondRecoveryV3Error("Flash recovery lock escapes project") from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise PublicSecondRecoveryV3Error(
            f"Flash recovery artifact drift: {lock['path']}"
        )


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def admission_path(shard_index: int) -> Path:
    if not 0 <= shard_index < SHARD_COUNT:
        raise PublicSecondRecoveryV3Error("Flash recovery shard index out of range")
    return (
        PROTOCOL_ROOT
        / "admissions"
        / f"deepseek_public_second_recovery_s{shard_index}_admission_v3.json"
    )


def _wrapper_root(shard_index: int) -> Path:
    return (
        PROJECT_ROOT
        / "outputs/verification"
        / (
            "deepseek_flash_public_second_continuation_"
            f"s{shard_index}_v2_guarded_20260803"
        )
    )


def _source_admission(shard_index: int) -> Path:
    return source_v2.admission_path(shard_index)


def _source_bundle(
    shard_index: int,
) -> tuple[live_v4.PublicExecutionPermit, dict[str, Any], dict[str, Any]]:
    permit = source_v2.authorize_shard(
        shard_index,
        selected_admission_path=_source_admission(shard_index),
    )
    role_policy = source_v2._role_policy(permit.candidate)
    state = source_v2._state(permit, role_policy=role_policy)
    return permit, role_policy, state


def _wrapper_locks(shard_index: int) -> list[dict[str, Any]]:
    root = _wrapper_root(shard_index)
    receipt = root / "receipt.json"
    if receipt.exists():
        raise PublicSecondRecoveryV3Error(
            "v2 wrapper receipt appeared after the receipt-missing checkpoint"
        )
    names = [
        "01_harness_gate.stdout.log",
        "01_harness_gate.stderr.log",
        "02_admission.stdout.log",
        "02_admission.stderr.log",
        "03_execute.stdout.log",
        "03_execute.stderr.log",
        "04_technical_review.stdout.log",
        "04_technical_review.stderr.log",
    ]
    return [_lock(root / name) for name in names]


def build_abort_review() -> dict[str, Any]:
    shards: list[dict[str, Any]] = []
    total_records = 0
    total_diagnostics = 0
    total_calls = 0
    total_cost = 0.0
    total_untouched = 0
    for shard_index in range(SHARD_COUNT):
        permit, _, state = _source_bundle(shard_index)
        records = state["records"]
        if not records or state["attempt_status"]["open_work_keys"]:
            raise PublicSecondRecoveryV3Error(
                "Flash v2 prefix is empty or has an open attempt"
            )
        diagnostics = [
            entry
            for entry in records
            if entry["record"]["result_tier"] == "diagnostic"
        ]
        if len(diagnostics) != 1 or records[-1] is not diagnostics[0]:
            raise PublicSecondRecoveryV3Error(
                "Flash v2 prefix must end at exactly one diagnostic"
            )
        diagnostic = diagnostics[0]
        trace = diagnostic["record"]["provider_trace_bundle"]
        failures = trace.get("failures")
        if (
            diagnostic["record"]["operational_status"] != "provider_failure"
            or trace.get("bundle_status") != "incomplete_provider_failure"
            or not isinstance(failures, list)
            or len(failures) != 1
            or failures[0].get("error_type") != "ProviderTransportError"
            or trace.get("automatic_retry") is not False
            or trace.get("provider_tools_declared") is not False
            or trace.get("external_effects_enabled") is not False
            or trace.get("prompt_or_response_content_stored") is not False
        ):
            raise PublicSecondRecoveryV3Error(
                "Flash v2 diagnostic transport boundary drift"
            )
        untouched = len(state["pending"])
        if untouched <= 0:
            raise PublicSecondRecoveryV3Error(
                "Flash v2 shard has no untouched recovery work"
            )
        technical_review = permit.output_root / "continuation_shard_review_v2.json"
        review = _load_json(technical_review)
        if (
            review.get("status") != "flash_continuation_shard_technical_gate_fail"
            or review.get("result_admission_eligible") is not False
            or review.get("observed_records") != len(records)
        ):
            raise PublicSecondRecoveryV3Error("Flash v2 technical review drift")
        shard = {
            "shard_index": shard_index,
            "source_run_id": permit.run_id,
            "source_execution_identity": permit.execution_identity,
            "source_output_root": _display_path(permit.output_root),
            "expected_record_count": len(permit.work_items),
            "closed_prefix_record_count": len(records),
            "closed_prefix_attempt_event_count": len(state["attempts"]),
            "closed_prefix_budget_event_count": len(state["budgets"]),
            "closed_prefix_diagnostic_record_count": 1,
            "diagnostic_work_key": diagnostic["work_key"],
            "diagnostic_operational_status": "provider_failure",
            "diagnostic_error_type": "ProviderTransportError",
            "diagnostic_included_in_itt": diagnostic["record"][
                "included_in_intention_to_treat"
            ],
            "untouched_record_count": untouched,
            "record_ledger_tail_sha256": state["record_status"]["tail_sha256"],
            "attempt_ledger_tail_sha256": state["attempt_status"]["tail_sha256"],
            "budget_ledger_tail_sha256": state["budget_status"]["tail_sha256"],
            "role_cumulative_cost_cny": state["budget_status"][
                "role_cumulative_cost_cny"
            ],
            "wrapper_receipt_present": False,
            "wrapper_os_exit_code": "unknown",
            "technical_review_lock": _lock(technical_review),
            "wrapper_log_locks": _wrapper_locks(shard_index),
        }
        shards.append(shard)
        total_records += len(records)
        total_diagnostics += 1
        total_calls += len(state["budgets"])
        total_cost += float(state["budget_status"]["role_cumulative_cost_cny"])
        total_untouched += untouched
    core = {
        "schema_version": "m3-paper-v2-public-second-abort-review-3.0",
        "artifact_role": "outcome_blind_flash_closed_prefix_abort_review",
        "reviewed_at": REVIEWED_AT,
        "status": "two_flash_prefixes_sealed_recovery_candidate_may_be_built",
        "source_candidate_manifest_sha256": source_v2.verify_candidate()[
            "manifest_sha256"
        ],
        "shards": shards,
        "totals": {
            "closed_prefix_records": total_records,
            "closed_prefix_diagnostic_records": total_diagnostics,
            "completed_provider_calls": total_calls,
            "role_cumulative_cost_cny": round(total_cost, 8),
            "untouched_records": total_untouched,
        },
        "checks": {
            "all_attempts_terminal": True,
            "diagnostics_retained_in_itt": True,
            "terminal_diagnostic_retry_authorized": False,
            "only_never_started_records_continuable": True,
            "same_execution_identity_resume_authorized": False,
            "wrapper_receipts_fabricated": False,
            "wrapper_os_exit_claimed": False,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "scientific_outcomes_aggregated": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_abort_review() -> dict[str, Any]:
    value = build_abort_review()
    _write_json(REVIEW_PATH, value)
    return value


def verify_abort_review() -> dict[str, Any]:
    observed = _load_json(REVIEW_PATH)
    expected = build_abort_review()
    if observed != expected or observed.get("manifest_sha256") != _manifest_sha(observed):
        raise PublicSecondRecoveryV3Error("Flash abort review drift")
    return observed


def _source_prefix_locks(permit: live_v4.PublicExecutionPermit) -> list[dict[str, Any]]:
    paths = [
        permit.record_ledger_path,
        permit.attempt_ledger_path,
        permit.budget_ledger_path,
    ]
    paths.extend(sorted(permit.trace_root.glob("*.jsonl")))
    return [_lock(path) for path in paths]


def _remaining_limit(source_limit: float, spent: float) -> float:
    remaining = math.floor((source_limit - spent) * 100_000_000) / 100_000_000
    if remaining <= 0:
        raise PublicSecondRecoveryV3Error("Flash shard has no remaining CNY budget")
    return remaining


def _stop_after_terminal_record(*, budget_paused: bool) -> bool:
    """仅在固化预算保险丝处停止，绝不在已关闭的诊断上停止。"""

    return budget_paused


def build_candidate() -> dict[str, Any]:
    review = verify_abort_review()
    source_candidate = source_v2.verify_candidate()
    artifact_paths = [
        Path(__file__),
        source_v2.CANDIDATE_PATH,
        REVIEW_PATH,
        PROJECT_ROOT / "experiments/paper_v2/incremental_live_ledgers_v1.py",
        PROJECT_ROOT / "experiments/paper_v2/public_second_continuation_v2.py",
        PROJECT_ROOT
        / "outputs/verification/run_deepseek_flash_public_second_recovery_v3_guarded.ps1",
    ]
    prefix_locks: list[dict[str, Any]] = []
    wrapper_locks: list[dict[str, Any]] = []
    shards: list[dict[str, Any]] = []
    all_work_keys: list[str] = []
    total_recovery_limit = 0.0
    for source_review in review["shards"]:
        shard_index = int(source_review["shard_index"])
        permit, _, state = _source_bundle(shard_index)
        source_shard = source_candidate["scope"]["shards"][shard_index]
        pending_keys = [str(item["work_key"]) for item in state["pending"]]
        identity = sha256_canonical_json(
            {
                "schema_version": "m3-paper-v2-public-second-recovery-identity-3.0",
                "source_execution_identity": permit.execution_identity,
                "source_abort_review_manifest_sha256": review["manifest_sha256"],
                "shard_index": shard_index,
                "source_prefix_tails": [
                    source_review["record_ledger_tail_sha256"],
                    source_review["attempt_ledger_tail_sha256"],
                    source_review["budget_ledger_tail_sha256"],
                ],
                "untouched_work_keys": pending_keys,
            }
        )
        limit = _remaining_limit(
            float(source_shard["hard_spend_limit_cny"]),
            float(source_review["role_cumulative_cost_cny"]),
        )
        total_recovery_limit += limit
        all_work_keys.extend(pending_keys)
        output_root = (
            "outputs/paper_upgrade_v2/formal_public/deepseek/"
            f"public-second-recovery-s{shard_index}-v3-{identity}"
        )
        shards.append(
            {
                "shard_index": shard_index,
                "records": len(pending_keys),
                "work_key_sequence_sha256": sha256_canonical_json(pending_keys),
                "run_id": f"paper-v2-public-second-recovery-s{shard_index}-v3",
                "execution_identity": identity,
                "output_root": output_root,
                "hard_spend_limit_cny": limit,
                "source_closed_prefix_record_count": source_review[
                    "closed_prefix_record_count"
                ],
                "source_diagnostic_work_key": source_review["diagnostic_work_key"],
                "source_execution_identity": permit.execution_identity,
            }
        )
        artifact_paths.extend(
            [_source_admission(shard_index), permit.output_root / "continuation_shard_review_v2.json"]
        )
        prefix_locks.extend(_source_prefix_locks(permit))
        wrapper_locks.extend(_wrapper_locks(shard_index))
    if len(all_work_keys) != len(set(all_work_keys)):
        raise PublicSecondRecoveryV3Error("Flash recovery work keys overlap")
    canary_cost = float(source_candidate["scope"]["source_canary_cost_cny"])
    prefix_cost = float(review["totals"]["role_cumulative_cost_cny"])
    projected = round(canary_cost + prefix_cost + total_recovery_limit, 8)
    if projected > ROLE_TOTAL_HARD_LIMIT_CNY:
        raise PublicSecondRecoveryV3Error("Flash recovery exceeds CNY 5 role ceiling")
    scope = {
        "provider_id": "deepseek",
        "endpoint_type": "official_api",
        "model_role": MODEL_ROLE,
        "model_id": MODEL_ID,
        "source_candidate_manifest_sha256": source_candidate["manifest_sha256"],
        "source_abort_review_manifest_sha256": review["manifest_sha256"],
        "recovery_records": len(all_work_keys),
        "shard_count": SHARD_COUNT,
        "shards": shards,
        "budget": {
            "role_total_hard_limit_cny": ROLE_TOTAL_HARD_LIMIT_CNY,
            "source_canary_cost_cny": canary_cost,
            "source_closed_prefix_cost_cny": prefix_cost,
            "recovery_shard_hard_limits_cny": [
                shard["hard_spend_limit_cny"] for shard in shards
            ],
            "projected_total_ceiling_cny": projected,
            "automatic_retries": 0,
        },
        "diagnostic_policy": {
            "retain_in_itt": True,
            "retry_terminal_diagnostic": False,
            "continue_after_new_terminal_diagnostic": True,
            "technical_admission_max_fraction": MAX_DIAGNOSTIC_FRACTION,
        },
        "execution": {
            "new_execution_identities": True,
            "new_output_roots": True,
            "maximum_parallel_shards": SHARD_COUNT,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "same_identity_rerun_authorized": False,
            "result_admission_is_separate": True,
        },
    }
    core = {
        "schema_version": "m3-paper-v2-public-second-recovery-candidate-3.0",
        "artifact_role": "owner_review_candidate",
        "generated_at": GENERATED_AT,
        "status": "offline_qualified_execution_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [
            _lock(path) for path in sorted(set(artifact_paths), key=lambda item: item.as_posix())
        ],
        "source_prefix_locks": prefix_locks,
        "source_wrapper_log_locks": wrapper_locks,
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
            "source_terminal_records_retried": 0,
        },
    }
    return validate_candidate({**core, "manifest_sha256": sha256_canonical_json(core)})


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicSecondRecoveryV3Error("Flash recovery candidate must be object")
    scope = value.get("scope")
    shards = scope.get("shards") if isinstance(scope, Mapping) else None
    if (
        value.get("schema_version")
        != "m3-paper-v2-public-second-recovery-candidate-3.0"
        or value.get("manifest_sha256") != _manifest_sha(value)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("model_id") != MODEL_ID
        or scope.get("model_role") != MODEL_ROLE
        or scope.get("recovery_records") != 1306
        or not isinstance(shards, list)
        or len(shards) != SHARD_COUNT
        or scope["budget"]["projected_total_ceiling_cny"] > ROLE_TOTAL_HARD_LIMIT_CNY
        or scope["budget"]["automatic_retries"] != 0
        or value.get("authorization", {}).get("shard_execution_authorized") is not False
        or value.get("evidence_boundary", {}).get("source_terminal_records_retried") != 0
    ):
        raise PublicSecondRecoveryV3Error("Flash recovery candidate scope drift")
    if len({item["execution_identity"] for item in shards}) != SHARD_COUNT:
        raise PublicSecondRecoveryV3Error("Flash recovery identities overlap")
    for group in (
        value.get("artifact_locks", []),
        value.get("source_prefix_locks", []),
        value.get("source_wrapper_log_locks", []),
    ):
        if not isinstance(group, list):
            raise PublicSecondRecoveryV3Error("Flash recovery locks missing")
        for lock in group:
            _verify_lock(lock)
    return copy.deepcopy(dict(value))


def write_candidate() -> dict[str, Any]:
    value = build_candidate()
    _write_json(CANDIDATE_PATH, value)
    return value


def verify_candidate() -> dict[str, Any]:
    observed = validate_candidate(_load_json(CANDIDATE_PATH))
    expected = build_candidate()
    if observed != expected:
        raise PublicSecondRecoveryV3Error("Flash recovery candidate drift")
    return observed


def canonical_command(shard_index: int) -> str:
    relative = admission_path(shard_index).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.public_second_continuation_recovery_v3 "
        f"--execute-shard --shard-index {shard_index} "
        f"--admission {relative} --config config\\project.local.env"
    )


def _candidate_shard(candidate: Mapping[str, Any], shard_index: int) -> dict[str, Any]:
    for shard in candidate["scope"]["shards"]:
        if int(shard["shard_index"]) == shard_index:
            return copy.deepcopy(dict(shard))
    raise PublicSecondRecoveryV3Error("Flash recovery shard missing")


def build_admission(
    shard_index: int,
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    if len(owner_statement_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in owner_statement_sha256
    ):
        raise PublicSecondRecoveryV3Error("owner statement must be lowercase SHA-256")
    candidate = verify_candidate()
    shard = _candidate_shard(candidate, shard_index)
    command = canonical_command(shard_index)
    core = {
        "schema_version": "m3-paper-v2-public-second-recovery-admission-3.0",
        "artifact_role": "single_flash_recovery_shard_execution_authorization",
        "approved_at": approved_at,
        "status": "activated_for_never_started_flash_records_only",
        "authorization": {
            "owner_statement_sha256": owner_statement_sha256,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "shard_index": shard_index,
            "run_id": shard["run_id"],
            "execution_identity": shard["execution_identity"],
            "maximum_new_records": shard["records"],
            "hard_spend_limit_cny": shard["hard_spend_limit_cny"],
            "exact_command": command,
            "exact_command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
            "source_terminal_record_replay_authorized": False,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "scientific_result_admission_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_admission(value: Any, *, shard_index: int) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("manifest_sha256") != _manifest_sha(value):
        raise PublicSecondRecoveryV3Error("Flash recovery admission manifest drift")
    authorization = value.get("authorization", {})
    expected = build_admission(
        shard_index,
        owner_statement_sha256=str(authorization.get("owner_statement_sha256", "")),
        approved_at=str(value.get("approved_at", "")),
    )
    if dict(value) != expected:
        raise PublicSecondRecoveryV3Error("Flash recovery admission scope drift")
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


def verify_admission(shard_index: int) -> dict[str, Any]:
    return validate_admission(_load_json(admission_path(shard_index)), shard_index=shard_index)


def _role_policy(candidate: Mapping[str, Any], shard_index: int) -> dict[str, Any]:
    policy = copy.deepcopy(build_role_policy(load_public_policy(), MODEL_ROLE))
    limit = float(_candidate_shard(candidate, shard_index)["hard_spend_limit_cny"])
    policy["deepseek"]["hard_spend_limit_cny"] = limit
    policy["deepseek"]["abort_ceiling_cny"] = limit
    policy["deepseek"]["abort_at_fraction"] = 1.0
    return policy


def _recovery_rows(
    candidate: Mapping[str, Any], shard_index: int
) -> list[dict[str, Any]]:
    _, _, source_state = _source_bundle(shard_index)
    shard = _candidate_shard(candidate, shard_index)
    rows = copy.deepcopy(source_state["pending"])
    if (
        len(rows) != shard["records"]
        or sha256_canonical_json([row["work_key"] for row in rows])
        != shard["work_key_sequence_sha256"]
    ):
        raise PublicSecondRecoveryV3Error("Flash recovery pending set drift")
    for row in rows:
        row["execution_identity"] = shard["execution_identity"]
    return rows


def _permit_and_state(
    shard_index: int,
    *,
    selected_admission_path: Path,
    require_unstarted: bool,
) -> tuple[
    live_v4.PublicExecutionPermit,
    dict[str, Any],
    IncrementalPublicRecordLedger,
    IncrementalAttemptLedger,
    IncrementalPublicBudgetTracker,
]:
    if selected_admission_path.resolve() != admission_path(shard_index).resolve():
        raise PublicSecondRecoveryV3Error("Flash recovery admission path is not frozen")
    admission = validate_admission(
        _load_json(selected_admission_path), shard_index=shard_index
    )
    candidate = verify_candidate()
    shard = _candidate_shard(candidate, shard_index)
    rows = _recovery_rows(candidate, shard_index)
    root = (PROJECT_ROOT / shard["output_root"]).resolve()
    try:
        root.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise PublicSecondRecoveryV3Error("Flash recovery output escapes project") from exc
    role_policy = _role_policy(candidate, shard_index)
    permit = live_v4.PublicExecutionPermit(
        model_role=MODEL_ROLE,
        run_id=shard["run_id"],
        execution_identity=shard["execution_identity"],
        work_items=tuple(rows),
        output_root=root,
        record_ledger_path=root / "experiment_records.jsonl",
        attempt_ledger_path=root / "attempt_events.jsonl",
        budget_ledger_path=root / "budget_events.jsonl",
        trace_root=root / "provider_traces",
        admission_file_sha256=_sha256_file(selected_admission_path),
        max_tokens=512,
        timeout_seconds=120.0,
        candidate=copy.deepcopy(candidate),
        admission=copy.deepcopy(admission),
    )
    keys = {str(item["work_key"]) for item in rows}
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
        model_role=MODEL_ROLE,
        known_work_keys=keys,
        role_policy=role_policy,
    )
    trace_files = list(permit.trace_root.glob("*.jsonl")) if permit.trace_root.exists() else []
    if require_unstarted and (
        records.entries or attempts.events or tracker.events or trace_files
    ):
        raise PublicSecondRecoveryV3Error(
            "Flash recovery identity already started; rerun is forbidden"
        )
    return permit, role_policy, records, attempts, tracker


def execute_shard(
    shard_index: int,
    *,
    selected_admission_path: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    permit, role_policy, records, attempts, tracker = _permit_and_state(
        shard_index,
        selected_admission_path=selected_admission_path,
        require_unstarted=True,
    )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    api_key = live_v4.v3.v2._validate_runtime_config(values, role_policy=role_policy)
    dispatcher = (dispatcher_factory or live_v4._build_dispatcher)(
        permit, tracker, api_key=api_key, role_policy=role_policy
    )
    completed = 0
    diagnostics = 0
    for compact in permit.work_items:
        try:
            tracker.assert_before_request()
        except ProviderPausedError:
            break
        work_key = str(compact["work_key"])
        attempts.append(
            work_key=work_key, event_type="started", record_entry_sha256=None
        )
        work_item, state = hydrate_public_work_item(compact)
        result = dict(dispatcher.execute(work_item, state))
        if result.get("result_tier") not in {"formal_candidate", "diagnostic"}:
            raise PublicSecondRecoveryV3Error("Flash recovery result exceeded candidate tier")
        result["admission_manifest_sha256"] = permit.admission_file_sha256
        entry = records.append(
            work_item=work_item,
            initial_online_state=state,
            execution_result=result,
        )
        tier = str(entry["record"]["result_tier"])
        attempts.append(
            work_key=work_key,
            event_type="diagnostic" if tier == "diagnostic" else "completed",
            record_entry_sha256=str(entry["entry_sha256"]),
        )
        completed += 1
        diagnostics += int(tier == "diagnostic")
        if _stop_after_terminal_record(budget_paused=tracker.status["paused"]):
            break
    record_status = records.full_validate()
    attempt_status = attempts.full_validate()
    budget_status = tracker.full_validate()
    if (
        set(record_status["terminal_work_keys"])
        != set(attempt_status["terminal_by_work_key"])
        or attempt_status["open_work_keys"]
    ):
        raise PublicSecondRecoveryV3Error("Flash recovery final state is not closed")
    cross_bind_public_budget_and_records(
        budget_events=tracker.events,
        record_entries=records.entries,
        trace_root=permit.trace_root,
        role_policy=role_policy,
    )
    return {
        "status": (
            "flash_recovery_shard_complete_candidate_unadmitted"
            if record_status["remaining_work_items"] == 0
            else "flash_recovery_shard_paused_by_budget"
        ),
        "model_role": MODEL_ROLE,
        "shard_index": shard_index,
        "run_id": permit.run_id,
        "new_records_completed": completed,
        "expected_new_records": len(permit.work_items),
        "new_diagnostic_records": diagnostics,
        "remaining_records": record_status["remaining_work_items"],
        "provider_calls_completed": budget_status["event_count"],
        "role_cumulative_cost_cny": budget_status["role_cumulative_cost_cny"],
        "source_terminal_records_retried": 0,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "result_admission_authorized": False,
    }


def build_technical_review(
    shard_index: int, *, selected_admission_path: Path
) -> dict[str, Any]:
    permit, _, records, attempts, tracker = _permit_and_state(
        shard_index,
        selected_admission_path=selected_admission_path,
        require_unstarted=False,
    )
    record_status = records.full_validate()
    attempt_status = attempts.full_validate()
    budget_status = tracker.full_validate()
    cross_bind_public_budget_and_records(
        budget_events=tracker.events,
        record_entries=records.entries,
        trace_root=permit.trace_root,
        role_policy=records.role_policy,
    )
    diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic" for entry in records.entries
    )
    maximum = max(1, math.floor(len(permit.work_items) * MAX_DIAGNOSTIC_FRACTION))
    checks = {
        "exact_record_count": len(records.entries) == len(permit.work_items),
        "all_attempts_terminal": not attempt_status["open_work_keys"],
        "record_attempt_terminal_sets_equal": set(record_status["terminal_work_keys"])
        == set(attempt_status["terminal_by_work_key"]),
        "all_tiers_candidate_or_diagnostic": all(
            entry["record"]["result_tier"] in {"formal_candidate", "diagnostic"}
            for entry in records.entries
        ),
        "all_records_in_itt": all(
            entry["record"]["included_in_intention_to_treat"] is True
            for entry in records.entries
        ),
        "diagnostic_fraction_within_frozen_bound": diagnostics <= maximum,
        "budget_not_paused": budget_status["paused"] is False,
        "budget_record_trace_cross_binding_complete": True,
        "source_terminal_records_retried": False,
        "scientific_outcomes_aggregated": False,
    }
    passed = all(checks.values())
    core = {
        "schema_version": "m3-paper-v2-public-second-recovery-review-3.0",
        "artifact_role": "outcome_blind_flash_recovery_technical_review",
        "reviewed_at": live_v4._now(),
        "status": (
            "flash_recovery_shard_technical_gate_pass"
            if passed
            else "flash_recovery_shard_technical_gate_fail"
        ),
        "model_role": MODEL_ROLE,
        "shard_index": shard_index,
        "run_id": permit.run_id,
        "candidate_manifest_sha256": permit.candidate["manifest_sha256"],
        "admission_file_sha256": permit.admission_file_sha256,
        "expected_records": len(permit.work_items),
        "observed_records": len(records.entries),
        "diagnostic_records": diagnostics,
        "maximum_admissible_diagnostic_records": maximum,
        "provider_calls_completed": budget_status["event_count"],
        "role_cumulative_cost_cny": budget_status["role_cumulative_cost_cny"],
        "checks": checks,
        "technical_gate_passed": passed,
        "scientific_result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_technical_review(
    shard_index: int, *, selected_admission_path: Path
) -> dict[str, Any]:
    permit, _, _, _, _ = _permit_and_state(
        shard_index,
        selected_admission_path=selected_admission_path,
        require_unstarted=False,
    )
    value = build_technical_review(
        shard_index, selected_admission_path=selected_admission_path
    )
    _write_json(permit.output_root / "recovery_shard_review_v3.json", value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-abort-review", action="store_true")
    action.add_argument("--verify-abort-review", action="store_true")
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
    if args.write_abort_review:
        value = write_abort_review()
    elif args.verify_abort_review:
        value = verify_abort_review()
    elif args.write_candidate:
        value = write_candidate()
    elif args.verify_candidate:
        value = verify_candidate()
    else:
        if args.shard_index is None:
            parser.error("shard action requires --shard-index")
        selected = args.admission or admission_path(args.shard_index)
        if args.write_admission:
            if not args.owner_statement_sha256 or not args.approved_at:
                parser.error("admission write requires owner digest and approved time")
            value = write_admission(
                args.shard_index,
                owner_statement_sha256=args.owner_statement_sha256,
                approved_at=args.approved_at,
            )
        elif args.verify_admission:
            value = verify_admission(args.shard_index)
        elif args.execute_shard:
            value = execute_shard(
                args.shard_index,
                selected_admission_path=selected,
                config_path=args.config,
            )
        else:
            value = write_technical_review(
                args.shard_index, selected_admission_path=selected
            )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
