"""Fresh result-blind recovery for the paper-v2 public primary shards."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v1 as medium_v1
import experiments.paper_v2.public_live_controller_v4 as live_v4
import experiments.paper_v2.public_sharded_continuation_abort_review_v1 as abort_v1
import experiments.paper_v2.public_sharded_continuation_v1 as continuation_v1
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderPausedError,
)
from experiments.paper_v2.public_execution_store_v1 import (
    PublicBudgetTracker,
    append_public_execution_result,
    cross_bind_public_budget_and_records,
    load_public_record_entries,
    validate_public_budget_events,
    validate_public_record_entries,
)
from experiments.paper_v2.public_matrix_plan_v1 import (
    DEFAULT_MANIFEST,
    DEFAULT_PLAN,
    hydrate_public_work_item,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    build_role_policy,
    load_public_policy,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
SCHEMA_ROOT = PROJECT_ROOT / "schemas/paper_v2"
CANDIDATE_PATH = (
    PROTOCOL_ROOT / "public_primary_continuation_candidate_v2.json"
)
QUALIFICATION_PATH = (
    PROTOCOL_ROOT / "public_primary_continuation_qualification_v2.json"
)
CANDIDATE_SCHEMA = (
    SCHEMA_ROOT / "public_sharded_continuation_candidate_v2.schema.json"
)
ADMISSION_SCHEMA = (
    SCHEMA_ROOT / "public_sharded_continuation_admission_v2.schema.json"
)
SCHEMA_VERSION = (
    "m3-paper-v2-public-sharded-continuation-candidate-2.0"
)
ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-public-sharded-continuation-admission-2.0"
)
GENERATED_AT = "2026-07-30T01:30:00+08:00"
QUALIFIED_AT = "2026-07-30T01:20:00+08:00"
SHARD_COUNT = 4
SHARD_HARD_LIMIT_CNY = 4.9


class PublicShardedContinuationV2Error(ValueError):
    """Raised when the fresh recovery cannot fail closed."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicShardedContinuationV2Error(
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


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
    )


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicShardedContinuationV2Error(
            f"missing recovery artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _validate_role(model_role: str) -> None:
    if model_role != "primary":
        raise PublicShardedContinuationV2Error(
            "continuation-v2 only admits the frozen primary recovery"
        )


def _validate_shard(model_role: str, shard_index: int) -> None:
    _validate_role(model_role)
    if not 0 <= shard_index < SHARD_COUNT:
        raise PublicShardedContinuationV2Error(
            "continuation-v2 shard index out of range"
        )


def admission_path(model_role: str, shard_index: int) -> Path:
    _validate_shard(model_role, shard_index)
    return (
        PROTOCOL_ROOT
        / "admissions"
        / (
            f"deepseek_public_{model_role}_continuation_s{shard_index}"
            "_admission_v2.json"
        )
    )


def _source_candidate() -> dict[str, Any]:
    value = continuation_v1.validate_candidate(
        _load_json(continuation_v1.candidate_path("primary")),
        model_role="primary",
    )
    return value


def _shard_role_policy() -> dict[str, Any]:
    policy = copy.deepcopy(
        build_role_policy(load_public_policy(), "primary")
    )
    policy["deepseek"]["hard_spend_limit_cny"] = SHARD_HARD_LIMIT_CNY
    policy["deepseek"]["abort_ceiling_cny"] = SHARD_HARD_LIMIT_CNY
    policy["deepseek"]["abort_at_fraction"] = 1.0
    return policy


def _state_from_paths(
    permit: live_v4.PublicExecutionPermit,
    *,
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        float(role_policy["deepseek"]["abort_ceiling_cny"])
        != SHARD_HARD_LIMIT_CNY
        or role_policy["deepseek"]["model_id"] != "deepseek-v4-pro"
    ):
        raise PublicShardedContinuationV2Error(
            "fresh state reconstruction requires the frozen shard policy"
        )
    keys = {str(item["work_key"]) for item in permit.work_items}
    records = load_public_record_entries(permit.record_ledger_path)
    record_status = validate_public_record_entries(
        records,
        work_items=permit.work_items,
        execution_identity=permit.execution_identity,
        run_id=permit.run_id,
        role_policy=role_policy,
    )
    attempts = medium_v1._load_jsonl(permit.attempt_ledger_path)
    attempt_status = medium_v1.validate_attempt_events(
        attempts,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=keys,
    )
    budgets = medium_v1._load_jsonl(permit.budget_ledger_path)
    budget_status = validate_public_budget_events(
        budgets,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role=permit.model_role,
        known_work_keys=keys,
        role_policy=role_policy,
    )
    terminal = set(record_status["terminal_work_keys"])
    if terminal != set(attempt_status["terminal_by_work_key"]):
        raise PublicShardedContinuationV2Error(
            "fresh attempt and record ledgers are not aligned"
        )
    if attempt_status["open_work_keys"]:
        raise PublicShardedContinuationV2Error(
            "open fresh attempt forbids automatic retry or resume"
        )
    cross_bind_public_budget_and_records(
        budget_events=budgets,
        record_entries=records,
        trace_root=permit.trace_root,
        role_policy=role_policy,
    )
    for item in permit.work_items:
        key = str(item["work_key"])
        if (
            key not in terminal
            and (permit.trace_root / f"{key}.jsonl").exists()
        ):
            raise PublicShardedContinuationV2Error(
                "pending fresh item already has a provider trace"
            )
    return {
        "records": records,
        "record_status": record_status,
        "attempts": attempts,
        "attempt_status": attempt_status,
        "budgets": budgets,
        "budget_status": budget_status,
        "pending": [
            copy.deepcopy(dict(item))
            for item in permit.work_items
            if str(item["work_key"]) not in terminal
        ],
    }


def _v1_permit(
    source: Mapping[str, Any],
    shard_index: int,
) -> live_v4.PublicExecutionPermit:
    shard = source["scope"]["shards"][shard_index]
    rows = continuation_v1._shard_rows(
        source,
        "primary",
        shard_index,
    )
    root = PROJECT_ROOT / str(shard["output_root"])
    admission = _load_json(
        continuation_v1.admission_path("primary", shard_index)
    )
    return live_v4.PublicExecutionPermit(
        model_role="primary",
        run_id=str(shard["run_id"]),
        execution_identity=str(shard["execution_identity"]),
        work_items=tuple(rows),
        output_root=root,
        record_ledger_path=root / "experiment_records.jsonl",
        attempt_ledger_path=root / "attempt_events.jsonl",
        budget_ledger_path=root / "budget_events.jsonl",
        trace_root=root / "provider_traces",
        admission_file_sha256=_sha256_file(
            continuation_v1.admission_path("primary", shard_index)
        ),
        max_tokens=512,
        timeout_seconds=120.0,
        candidate=copy.deepcopy(dict(source)),
        admission=admission,
    )


def build_qualification() -> dict[str, Any]:
    abort = abort_v1.verify_abort_review()
    source = _source_candidate()
    if (
        abort["candidate_manifest_sha256"]
        != source["manifest_sha256"]
        or abort["operational_summary"]["record_count"] != 4
        or abort["evidence_boundary"]["old_roots_resumable"] is not False
    ):
        raise PublicShardedContinuationV2Error(
            "continuation-v1 abort boundary is not recovery-ready"
        )
    policy = _shard_role_policy()
    checks: list[dict[str, Any]] = []
    for shard_index in range(SHARD_COUNT):
        state = _state_from_paths(
            _v1_permit(source, shard_index),
            role_policy=policy,
        )
        checks.append(
            {
                "shard_index": shard_index,
                "existing_record_count": len(state["records"]),
                "existing_open_attempt_count": len(
                    state["attempt_status"]["open_work_keys"]
                ),
                "existing_budget_paused": state["budget_status"]["paused"],
                "policy_abort_ceiling_cny": policy["deepseek"][
                    "abort_ceiling_cny"
                ],
                "policy_aware_state_reconstruction_passed": True,
            }
        )
    if any(
        item["existing_record_count"] != 1
        or item["existing_open_attempt_count"] != 0
        or item["existing_budget_paused"] is not False
        for item in checks
    ):
        raise PublicShardedContinuationV2Error(
            "policy-aware state reconstruction qualification failed"
        )
    core = {
        "schema_version": (
            "m3-paper-v2-public-sharded-continuation-qualification-2.0"
        ),
        "generated_at": QUALIFIED_AT,
        "status": "completed_zero_network_policy_aware_state_qualification",
        "source_abort_review_manifest_sha256": abort["manifest_sha256"],
        "source_candidate_manifest_sha256": source["manifest_sha256"],
        "checks": checks,
        "summary": {
            "qualified_shards": 4,
            "expected_shards": 4,
            "policy_abort_ceiling_cny": SHARD_HARD_LIMIT_CNY,
            "old_records_reused_for_scientific_result": False,
            "credentials_read": False,
            "network_calls": 0,
            "provider_calls": 0,
            "formal_results_created": 0,
            "scientific_outcomes_accessed": False,
        },
        "artifact_locks": [
            _lock(path)
            for path in sorted(
                {
                    Path(__file__),
                    abort_v1.DEFAULT_OUTPUT,
                    continuation_v1.candidate_path("primary"),
                    PROJECT_ROOT
                    / "experiments/paper_v2/"
                    "public_execution_store_v1.py",
                    PROJECT_ROOT
                    / "experiments/paper_v2/"
                    "public_sharded_continuation_v1.py",
                },
                key=lambda item: item.as_posix(),
            )
        ],
        "result_eligible_for_formal_tables": False,
    }
    return {**core, "manifest_sha256": _manifest_sha(core)}


def write_qualification() -> dict[str, Any]:
    value = build_qualification()
    _write_json(QUALIFICATION_PATH, value)
    return value


def verify_qualification() -> dict[str, Any]:
    observed = _load_json(QUALIFICATION_PATH)
    expected = build_qualification()
    if observed != expected:
        raise PublicShardedContinuationV2Error(
            "continuation-v2 qualification drift"
        )
    return observed


def _candidate_artifacts() -> list[Path]:
    return [
        Path(__file__),
        CANDIDATE_SCHEMA,
        ADMISSION_SCHEMA,
        DEFAULT_PLAN,
        DEFAULT_MANIFEST,
        continuation_v1.candidate_path("primary"),
        abort_v1.DEFAULT_OUTPUT,
        QUALIFICATION_PATH,
        PROJECT_ROOT
        / "experiments/paper_v2/public_sharded_continuation_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_live_controller_v4.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_live_controller_v2.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_execution_store_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_provider_trace_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_provider_budget_v1.py",
    ]


def build_candidate() -> dict[str, Any]:
    qualification = verify_qualification()
    abort = abort_v1.verify_abort_review()
    source = _source_candidate()
    if (
        qualification["source_abort_review_manifest_sha256"]
        != abort["manifest_sha256"]
        or qualification["source_candidate_manifest_sha256"]
        != source["manifest_sha256"]
    ):
        raise PublicShardedContinuationV2Error(
            "recovery qualification source drift"
        )
    source_shards = source["scope"]["shards"]
    shards: list[dict[str, Any]] = []
    for shard_index, rows in enumerate(
        continuation_v1._partition_rows("primary")
    ):
        identity = sha256_canonical_json(
            {
                "schema_version": (
                    "m3-paper-v2-public-continuation-shard-identity-2.0"
                ),
                "model_role": "primary",
                "shard_index": shard_index,
                "source_v1_candidate_manifest_sha256": source[
                    "manifest_sha256"
                ],
                "source_v1_abort_review_manifest_sha256": abort[
                    "manifest_sha256"
                ],
                "qualification_manifest_sha256": qualification[
                    "manifest_sha256"
                ],
                "work_key_sequence_sha256": source_shards[shard_index][
                    "work_key_sequence_sha256"
                ],
            }
        )
        shards.append(
            {
                "shard_index": shard_index,
                "records": len(rows),
                "work_key_sequence_sha256": sha256_canonical_json(
                    [row["work_key"] for row in rows]
                ),
                "execution_identity": identity,
                "run_id": (
                    "paper-v2-public-primary-continuation-"
                    f"s{shard_index}-v2"
                ),
                "output_root": (
                    "outputs/paper_upgrade_v2/formal_public/deepseek/"
                    "public-primary-continuation-"
                    f"s{shard_index}-v2-{identity}"
                ),
                "hard_spend_limit_cny": SHARD_HARD_LIMIT_CNY,
            }
        )
    prior_cost = float(
        abort["operational_summary"]["role_cumulative_cost_cny"]
    )
    canary_cost = float(source["scope"]["source_canary_cost_cny"])
    projected_ceiling = round(
        prior_cost + canary_cost + SHARD_COUNT * SHARD_HARD_LIMIT_CNY,
        12,
    )
    if projected_ceiling >= 20.0:
        raise PublicShardedContinuationV2Error(
            "fresh recovery no longer fits the primary role envelope"
        )
    scope = {
        "model_role": "primary",
        "model_id": "deepseek-v4-pro",
        "source_v1_candidate_manifest_sha256": source["manifest_sha256"],
        "source_v1_abort_review_manifest_sha256": abort[
            "manifest_sha256"
        ],
        "qualification_manifest_sha256": qualification["manifest_sha256"],
        "source_canary_records": 24,
        "source_canary_cost_cny": canary_cost,
        "aborted_v1_records": 4,
        "aborted_v1_cost_cny": prior_cost,
        "role_records": 5082,
        "continuation_records": sum(item["records"] for item in shards),
        "shard_count": SHARD_COUNT,
        "shards": shards,
        "partition": {
            "rule": "full_remaining_plan_order_round_robin_fresh_reexecution",
            "disjoint": True,
            "complete": True,
            "terminal_canary_rows_excluded": True,
            "old_v1_records_excluded_from_result": True,
        },
        "budget": {
            "per_shard_hard_limit_cny": SHARD_HARD_LIMIT_CNY,
            "fresh_all_shards_hard_limit_cny": round(
                SHARD_COUNT * SHARD_HARD_LIMIT_CNY,
                12,
            ),
            "prior_aborted_v1_cost_cny": prior_cost,
            "source_canary_cost_cny": canary_cost,
            "projected_primary_total_ceiling_cny": projected_ceiling,
            "primary_role_hard_limit_cny": 20.0,
            "automatic_retries": 0,
        },
        "execution": {
            "maximum_parallel_shards": SHARD_COUNT,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "result_admission_is_separate": True,
            "state_reconstruction_policy": (
                "exact_per_shard_role_policy_forwarded"
            ),
        },
        "recovery": {
            "old_v1_roots_resumed": False,
            "old_v1_records_reused": False,
            "selective_retry": False,
            "fresh_full_partition": True,
            "new_execution_identities": True,
            "new_output_roots": True,
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "owner_review_candidate",
        "generated_at": GENERATED_AT,
        "status": (
            "fresh_recovery_candidate_pending_exact_command_shard_approvals"
        ),
        "scope": scope,
        "artifact_locks": [
            _lock(path)
            for path in sorted(
                set(_candidate_artifacts()),
                key=lambda item: item.as_posix(),
            )
        ],
        "authorization": {
            "candidate_only": True,
            "shard_execution_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "scientific_outcomes_accessed": False,
            "formal_results_created": 0,
            "old_records_reused": False,
        },
        "scope_sha256": sha256_canonical_json(scope),
    }
    value = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return validate_candidate(value)


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicShardedContinuationV2Error(
            "continuation-v2 candidate must be an object"
        )
    Draft202012Validator(
        _load_json(CANDIDATE_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if (
        value["scope"]["model_role"] != "primary"
        or value["scope_sha256"]
        != sha256_canonical_json(value["scope"])
        or value["manifest_sha256"] != _manifest_sha(value)
        or value["scope"]["recovery"]["old_v1_records_reused"] is not False
    ):
        raise PublicShardedContinuationV2Error(
            "continuation-v2 candidate digest or recovery drift"
        )
    locks = value["artifact_locks"]
    if len({item["path"] for item in locks}) != len(locks):
        raise PublicShardedContinuationV2Error(
            "duplicate continuation-v2 artifact lock"
        )
    for item in locks:
        path = (PROJECT_ROOT / str(item["path"])).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise PublicShardedContinuationV2Error(
                "continuation-v2 artifact lock escapes project"
            ) from exc
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise PublicShardedContinuationV2Error(
                f"continuation-v2 artifact lock drift: {item['path']}"
            )
    return copy.deepcopy(dict(value))


def write_candidate() -> dict[str, Any]:
    value = build_candidate()
    _write_json(CANDIDATE_PATH, value)
    return value


def verify_candidate() -> dict[str, Any]:
    observed = validate_candidate(_load_json(CANDIDATE_PATH))
    expected = build_candidate()
    if observed != expected:
        raise PublicShardedContinuationV2Error(
            "continuation-v2 candidate drift"
        )
    return observed


def canonical_shard_command(shard_index: int) -> str:
    _validate_shard("primary", shard_index)
    admission = admission_path(
        "primary",
        shard_index,
    ).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.public_sharded_continuation_v2 "
        "--execute-shard --model-role primary "
        f"--shard-index {shard_index} --admission {admission} "
        "--config config\\project.local.env"
    )


def _validate_admission_against_candidate(
    value: Any,
    *,
    candidate: Mapping[str, Any],
    shard_index: int,
) -> dict[str, Any]:
    _validate_shard("primary", shard_index)
    if not isinstance(value, Mapping):
        raise PublicShardedContinuationV2Error(
            "continuation-v2 admission must be an object"
        )
    Draft202012Validator(
        _load_json(ADMISSION_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    shard = candidate["scope"]["shards"][shard_index]
    command = canonical_shard_command(shard_index)
    if (
        value["scope_sha256"]
        != sha256_canonical_json(value["scope"])
        or value["manifest_sha256"] != _manifest_sha(value)
        or value["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or value["scope"]["model_role"] != "primary"
        or value["scope"]["shard_index"] != shard_index
        or value["scope"]["run_id"] != shard["run_id"]
        or value["scope"]["execution_identity"]
        != shard["execution_identity"]
        or value["scope"]["records"] != shard["records"]
        or value["scope"]["work_key_sequence_sha256"]
        != shard["work_key_sequence_sha256"]
        or value["scope"]["output_root"] != shard["output_root"]
        or value["scope"]["hard_spend_limit_cny"]
        != SHARD_HARD_LIMIT_CNY
        or value["scope"]["exact_command"] != command
        or value["scope"]["exact_command_sha256"]
        != hashlib.sha256(command.encode("utf-8")).hexdigest()
    ):
        raise PublicShardedContinuationV2Error(
            "continuation-v2 admission binding drift"
        )
    return copy.deepcopy(dict(value))


def build_admission(
    shard_index: int,
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    if (
        len(owner_statement_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in owner_statement_sha256
        )
    ):
        raise PublicShardedContinuationV2Error(
            "owner statement digest must be lowercase SHA-256"
        )
    candidate = verify_candidate()
    shard = candidate["scope"]["shards"][shard_index]
    command = canonical_shard_command(shard_index)
    scope = {
        "model_role": "primary",
        "shard_index": shard_index,
        "run_id": shard["run_id"],
        "execution_identity": shard["execution_identity"],
        "model_id": candidate["scope"]["model_id"],
        "records": shard["records"],
        "work_key_sequence_sha256": shard[
            "work_key_sequence_sha256"
        ],
        "output_root": shard["output_root"],
        "hard_spend_limit_cny": shard["hard_spend_limit_cny"],
        "exact_command": command,
        "exact_command_sha256": hashlib.sha256(
            command.encode("utf-8")
        ).hexdigest(),
    }
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "single_fresh_shard_execution_authorization",
        "approved_at": approved_at,
        "status": "activated_for_one_exact_fresh_recovery_shard",
        "scope": scope,
        "authorization": {
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "owner_statement_sha256": owner_statement_sha256,
            "shard_execution_authorized": True,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "scientific_outcomes_may_be_reviewed": False,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "automatic_retries": 0,
            "old_records_reused": False,
        },
        "scope_sha256": sha256_canonical_json(scope),
    }
    value = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return _validate_admission_against_candidate(
        value,
        candidate=candidate,
        shard_index=shard_index,
    )


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
    _write_json(admission_path("primary", shard_index), value)
    return value


def validate_admission(
    value: Any,
    *,
    shard_index: int,
) -> dict[str, Any]:
    candidate = verify_candidate()
    return _validate_admission_against_candidate(
        value,
        candidate=candidate,
        shard_index=shard_index,
    )


def _fresh_rows(
    candidate: Mapping[str, Any],
    shard_index: int,
) -> list[dict[str, Any]]:
    rows = copy.deepcopy(
        continuation_v1._partition_rows("primary")[shard_index]
    )
    identity = candidate["scope"]["shards"][shard_index][
        "execution_identity"
    ]
    for row in rows:
        row["execution_identity"] = identity
    return rows


def authorize_shard(
    shard_index: int,
    *,
    selected_admission_path: Path,
) -> tuple[live_v4.PublicExecutionPermit, dict[str, Any]]:
    candidate = verify_candidate()
    admission = _validate_admission_against_candidate(
        _load_json(selected_admission_path),
        candidate=candidate,
        shard_index=shard_index,
    )
    shard = candidate["scope"]["shards"][shard_index]
    rows = _fresh_rows(candidate, shard_index)
    root = (PROJECT_ROOT / str(shard["output_root"])).resolve()
    try:
        root.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise PublicShardedContinuationV2Error(
            "continuation-v2 output root escapes project"
        ) from exc
    permit = live_v4.PublicExecutionPermit(
        model_role="primary",
        run_id=str(shard["run_id"]),
        execution_identity=str(shard["execution_identity"]),
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
    policy = _shard_role_policy()
    _state_from_paths(permit, role_policy=policy)
    return permit, policy


def execute_shard(
    shard_index: int,
    *,
    selected_admission_path: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    permit, role_policy = authorize_shard(
        shard_index,
        selected_admission_path=selected_admission_path,
    )
    initial = _state_from_paths(permit, role_policy=role_policy)
    if initial["records"] or initial["attempts"]:
        raise PublicShardedContinuationV2Error(
            "fresh shard already started; automatic rerun is forbidden"
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
    keys = {str(item["work_key"]) for item in permit.work_items}
    tracker = PublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys=keys,
        role_policy=role_policy,
    )
    factory = dispatcher_factory or live_v4._build_dispatcher
    dispatcher = factory(
        permit,
        tracker,
        api_key=api_key,
        role_policy=role_policy,
    )
    completed_this_process = 0
    for compact in permit.work_items:
        try:
            tracker.assert_before_request()
        except ProviderPausedError:
            break
        work_key = str(compact["work_key"])
        medium_v1._append_attempt_event(
            permit.attempt_ledger_path,
            run_id=permit.run_id,
            execution_identity=permit.execution_identity,
            known_work_keys=keys,
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
            raise PublicShardedContinuationV2Error(
                "fresh result exceeded candidate tier"
            )
        result["admission_manifest_sha256"] = (
            permit.admission_file_sha256
        )
        entry = append_public_execution_result(
            permit.record_ledger_path,
            work_items=permit.work_items,
            work_item=work_item,
            initial_online_state=state,
            execution_result=result,
            execution_identity=permit.execution_identity,
            run_id=permit.run_id,
            role_policy=role_policy,
        )
        tier = str(entry["record"]["result_tier"])
        medium_v1._append_attempt_event(
            permit.attempt_ledger_path,
            run_id=permit.run_id,
            execution_identity=permit.execution_identity,
            known_work_keys=keys,
            work_key=work_key,
            event_type=(
                "diagnostic" if tier == "diagnostic" else "completed"
            ),
            record_entry_sha256=str(entry["entry_sha256"]),
        )
        completed_this_process += 1
        current = _state_from_paths(permit, role_policy=role_policy)
        if tier == "diagnostic" or current["budget_status"]["paused"]:
            break
    final = _state_from_paths(permit, role_policy=role_policy)
    diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in final["records"]
    )
    remaining = len(final["pending"])
    return {
        "status": (
            "fresh_shard_complete_candidate_records_unadmitted"
            if remaining == 0
            else (
                "fresh_shard_paused_after_diagnostic"
                if diagnostics
                else "fresh_shard_paused_by_budget"
            )
        ),
        "model_role": "primary",
        "shard_index": shard_index,
        "run_id": permit.run_id,
        "records": len(permit.work_items),
        "record_count": len(final["records"]),
        "diagnostic_records": diagnostics,
        "remaining_records": remaining,
        "completed_this_process": completed_this_process,
        "provider_calls_completed": final["budget_status"]["event_count"],
        "role_cumulative_usage": final["budget_status"][
            "role_cumulative_usage"
        ],
        "role_cumulative_cost_cny": final["budget_status"][
            "role_cumulative_cost_cny"
        ],
        "result_admission_authorized": False,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "old_records_reused": False,
    }


def build_technical_review(
    shard_index: int,
    *,
    selected_admission_path: Path,
) -> dict[str, Any]:
    permit, role_policy = authorize_shard(
        shard_index,
        selected_admission_path=selected_admission_path,
    )
    state = _state_from_paths(permit, role_policy=role_policy)
    records = state["records"]
    expected = len(permit.work_items)
    tiers = [entry["record"]["result_tier"] for entry in records]
    checks = {
        "exact_record_count": len(records) == expected,
        "all_attempts_terminal": not state["attempt_status"][
            "open_work_keys"
        ],
        "all_result_tiers_formal_candidate": tiers
        == ["formal_candidate"] * expected,
        "budget_not_paused": state["budget_status"]["paused"] is False,
        "budget_and_records_cross_bound": True,
        "terminal_canary_rows_excluded": True,
        "old_v1_records_excluded": True,
        "exact_shard_policy_used_for_state_reconstruction": True,
    }
    passed = all(checks.values())
    return {
        "schema_version": (
            "m3-paper-v2-public-continuation-shard-review-2.0"
        ),
        "generated_at": live_v4._now(),
        "status": (
            "fresh_continuation_shard_technical_gate_pass"
            if passed
            else "fresh_continuation_shard_technical_gate_fail"
        ),
        "model_role": "primary",
        "shard_index": shard_index,
        "run_id": permit.run_id,
        "candidate_manifest_sha256": permit.candidate["manifest_sha256"],
        "admission_file_sha256": permit.admission_file_sha256,
        "expected_records": expected,
        "observed_records": len(records),
        "provider_calls_completed": state["budget_status"]["event_count"],
        "role_cumulative_usage": state["budget_status"][
            "role_cumulative_usage"
        ],
        "role_cumulative_cost_cny": state["budget_status"][
            "role_cumulative_cost_cny"
        ],
        "checks": checks,
        "result_admission_eligible": passed,
        "review_boundary": {
            "scientific_outcomes_accessed": False,
            "unsafe_effect_aggregated": False,
            "task_completion_aggregated": False,
            "condition_effects_compared": False,
            "result_admission_authorized": False,
        },
    }


def write_technical_review(
    shard_index: int,
    *,
    selected_admission_path: Path,
) -> dict[str, Any]:
    permit, _ = authorize_shard(
        shard_index,
        selected_admission_path=selected_admission_path,
    )
    value = build_technical_review(
        shard_index,
        selected_admission_path=selected_admission_path,
    )
    _write_json(
        permit.output_root / "continuation_shard_review_v2.json",
        value,
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-qualification", action="store_true")
    action.add_argument("--verify-qualification", action="store_true")
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-shard", action="store_true")
    action.add_argument("--write-technical-review", action="store_true")
    parser.add_argument("--model-role", choices=("primary",), default="primary")
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--approved-at")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    if args.write_qualification:
        value = write_qualification()
    elif args.verify_qualification:
        value = verify_qualification()
    elif args.write_candidate:
        value = write_candidate()
    elif args.verify_candidate:
        value = verify_candidate()
    else:
        if args.shard_index is None:
            parser.error("selected action requires --shard-index")
        selected = args.admission or admission_path(
            "primary",
            args.shard_index,
        )
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
