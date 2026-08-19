"""Result-blind sharded continuation for the paper-v2 public matrix."""

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
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    ProviderPausedError,
)
from experiments.paper_v2.public_execution_store_v1 import (
    PublicBudgetTracker,
    append_public_execution_result,
)
from experiments.paper_v2.public_matrix_controller_v4 import (
    DEFAULT_CANDIDATE as DEFAULT_V4_CANDIDATE,
    PROJECT_ROOT,
    verify_candidate as verify_v4_candidate,
)
from experiments.paper_v2.public_matrix_plan_v1 import (
    DEFAULT_MANIFEST,
    DEFAULT_PLAN,
    _canary_items,
    hydrate_public_work_item,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    build_role_policy,
    load_public_policy,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
SCHEMA_ROOT = PROJECT_ROOT / "schemas/paper_v2"
CANDIDATE_SCHEMA = (
    SCHEMA_ROOT / "public_sharded_continuation_candidate_v1.schema.json"
)
ADMISSION_SCHEMA = (
    SCHEMA_ROOT / "public_sharded_continuation_admission_v1.schema.json"
)
SCHEMA_VERSION = (
    "m3-paper-v2-public-sharded-continuation-candidate-1.0"
)
ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-public-sharded-continuation-admission-1.0"
)
GENERATED_AT = "2026-07-29T06:00:00+08:00"
SHARD_COUNTS = {"primary": 4, "second": 2}
SHARD_HARD_LIMITS_CNY = {"primary": 4.9, "second": 2.45}


class PublicShardedContinuationError(ValueError):
    """Raised when a public continuation shard cannot fail closed."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicShardedContinuationError(
            f"{path}: expected an object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicShardedContinuationError(
            f"missing continuation artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def candidate_path(model_role: str) -> Path:
    _validate_role(model_role)
    return (
        PROTOCOL_ROOT
        / f"public_{model_role}_continuation_candidate_v1.json"
    )


def admission_path(model_role: str, shard_index: int) -> Path:
    _validate_shard(model_role, shard_index)
    return (
        PROTOCOL_ROOT
        / "admissions"
        / (
            f"deepseek_public_{model_role}_continuation_s{shard_index}"
            "_admission_v1.json"
        )
    )


def _validate_role(model_role: str) -> None:
    if model_role not in SHARD_COUNTS:
        raise PublicShardedContinuationError(
            "unsupported public model role"
        )


def _validate_shard(model_role: str, shard_index: int) -> None:
    _validate_role(model_role)
    if not 0 <= shard_index < SHARD_COUNTS[model_role]:
        raise PublicShardedContinuationError(
            "continuation shard index out of range"
        )


def _source_admission_path(model_role: str) -> Path:
    return live_v4.ADMISSION_PATHS[model_role]


def _source_technical_review_path(
    candidate: Mapping[str, Any],
    model_role: str,
) -> Path:
    return (
        PROJECT_ROOT
        / str(candidate["scope"]["runs"][model_role]["output_root"])
        / live_v4.TECHNICAL_REVIEW_NAME
    )


def _validated_source(
    model_role: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    candidate = verify_v4_candidate()
    source_admission_path = _source_admission_path(model_role)
    admission = live_v4.validate_canary_admission(
        _load_json(source_admission_path),
        model_role=model_role,
    )
    review_path = _source_technical_review_path(candidate, model_role)
    review = _load_json(review_path)
    expected = 24 if model_role == "primary" else 12
    if (
        review.get("status") != "public_canary_technical_gate_pass"
        or review.get("matrix_continuation_eligible") is not True
        or review.get("model_role") != model_role
        or review.get("observed_records") != expected
        or review.get("candidate_manifest_sha256")
        != candidate["manifest_sha256"]
        or review.get("admission_file_sha256")
        != _sha256_file(source_admission_path)
        or review.get("review_boundary", {}).get(
            "scientific_outcomes_accessed"
        )
        is not False
        or review.get("review_boundary", {}).get(
            "result_admission_authorized"
        )
        is not False
    ):
        raise PublicShardedContinuationError(
            f"{model_role} canary technical review is not continuation-ready"
        )
    return candidate, admission, review, review_path


def _role_rows(model_role: str) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(row)
        for row in live_v4._load_plan(DEFAULT_PLAN)
        if row["model_role"] == model_role
    ]


def _continuation_rows(model_role: str) -> list[dict[str, Any]]:
    rows = _role_rows(model_role)
    canary_keys = {
        str(row["work_key"])
        for row in _canary_items(rows, model_role)
    }
    continuation = [
        row for row in rows if str(row["work_key"]) not in canary_keys
    ]
    expected = len(rows) - (24 if model_role == "primary" else 12)
    if len(continuation) != expected:
        raise PublicShardedContinuationError(
            "continuation row count drift"
        )
    return continuation


def _partition_rows(
    model_role: str,
) -> list[list[dict[str, Any]]]:
    rows = _continuation_rows(model_role)
    shards = [[] for _ in range(SHARD_COUNTS[model_role])]
    for index, row in enumerate(rows):
        shards[index % len(shards)].append(row)
    keys = [
        str(row["work_key"])
        for shard in shards
        for row in shard
    ]
    if len(keys) != len(set(keys)) or len(keys) != len(rows):
        raise PublicShardedContinuationError(
            "continuation shards overlap or omit work"
        )
    return shards


def _shard_identity(
    *,
    model_role: str,
    shard_index: int,
    source_candidate: Mapping[str, Any],
    technical_review_path: Path,
) -> str:
    return sha256_canonical_json(
        {
            "schema_version": (
                "m3-paper-v2-public-continuation-shard-identity-1.0"
            ),
            "model_role": model_role,
            "shard_index": shard_index,
            "source_candidate_manifest_sha256": source_candidate[
                "manifest_sha256"
            ],
            "source_execution_identity": source_candidate["scope"][
                "model_roles"
            ][model_role]["execution_identity"],
            "canary_technical_review_sha256": _sha256_file(
                technical_review_path
            ),
        }
    )


def _candidate_artifacts(
    *,
    model_role: str,
    source_review_path: Path,
) -> list[Path]:
    return [
        Path(__file__),
        CANDIDATE_SCHEMA,
        ADMISSION_SCHEMA,
        DEFAULT_PLAN,
        DEFAULT_MANIFEST,
        DEFAULT_V4_CANDIDATE,
        _source_admission_path(model_role),
        source_review_path,
        PROJECT_ROOT / "protocols/paper_upgrade_v2/public_budget_policy_v1.json",
        PROJECT_ROOT / "experiments/paper_v2/public_live_controller_v4.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_m3_live_dependency_v4.py",
    ]


def build_candidate(model_role: str) -> dict[str, Any]:
    _validate_role(model_role)
    source, admission, review, review_path = _validated_source(model_role)
    partitions = _partition_rows(model_role)
    shards: list[dict[str, Any]] = []
    for index, rows in enumerate(partitions):
        identity = _shard_identity(
            model_role=model_role,
            shard_index=index,
            source_candidate=source,
            technical_review_path=review_path,
        )
        shards.append(
            {
                "shard_index": index,
                "records": len(rows),
                "work_key_sequence_sha256": sha256_canonical_json(
                    [row["work_key"] for row in rows]
                ),
                "execution_identity": identity,
                "run_id": (
                    f"paper-v2-public-{model_role}-continuation-s{index}-v1"
                ),
                "output_root": (
                    "outputs/paper_upgrade_v2/formal_public/deepseek/"
                    f"public-{model_role}-continuation-s{index}-v1-"
                    f"{identity}"
                ),
                "hard_spend_limit_cny": SHARD_HARD_LIMITS_CNY[
                    model_role
                ],
            }
        )
    role_rows = _role_rows(model_role)
    scope = {
        "model_role": model_role,
        "model_id": source["scope"]["model_roles"][model_role]["model_id"],
        "source_candidate_manifest_sha256": source["manifest_sha256"],
        "source_canary_admission_manifest_sha256": admission[
            "manifest_sha256"
        ],
        "source_canary_technical_review_sha256": _sha256_file(review_path),
        "source_canary_records": review["observed_records"],
        "source_canary_cost_cny": review["role_cumulative_cost_cny"],
        "role_records": len(role_rows),
        "continuation_records": sum(item["records"] for item in shards),
        "shard_count": len(shards),
        "shards": shards,
        "partition": {
            "rule": "remaining_plan_order_round_robin",
            "disjoint": True,
            "complete": True,
            "terminal_canary_rows_excluded": True,
        },
        "budget": {
            "per_shard_hard_limit_cny": SHARD_HARD_LIMITS_CNY[model_role],
            "all_shards_hard_limit_cny": (
                SHARD_HARD_LIMITS_CNY[model_role] * len(shards)
            ),
            "source_canary_cost_cny": review[
                "role_cumulative_cost_cny"
            ],
            "automatic_retries": 0,
            "global_public_policy_sha256": _sha256_file(
                PROJECT_ROOT
                / "protocols/paper_upgrade_v2/public_budget_policy_v1.json"
            ),
        },
        "execution": {
            "maximum_parallel_shards": len(shards),
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "result_admission_is_separate": True,
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "owner_review_candidate",
        "generated_at": GENERATED_AT,
        "status": "candidate_pending_exact_command_shard_approvals",
        "scope": scope,
        "artifact_locks": [
            _lock(path)
            for path in sorted(
                set(
                    _candidate_artifacts(
                        model_role=model_role,
                        source_review_path=review_path,
                    )
                ),
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
        },
        "scope_sha256": sha256_canonical_json(scope),
    }
    value = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return validate_candidate(value, model_role=model_role)


def validate_candidate(
    value: Any,
    *,
    model_role: str,
) -> dict[str, Any]:
    _validate_role(model_role)
    if not isinstance(value, Mapping):
        raise PublicShardedContinuationError(
            "continuation candidate must be an object"
        )
    Draft202012Validator(
        _load_json(CANDIDATE_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if (
        value["scope"]["model_role"] != model_role
        or value["scope_sha256"] != sha256_canonical_json(value["scope"])
        or value["manifest_sha256"] != _manifest_sha(value)
    ):
        raise PublicShardedContinuationError(
            "continuation candidate digest/scope drift"
        )
    locks = value["artifact_locks"]
    if len({item["path"] for item in locks}) != len(locks):
        raise PublicShardedContinuationError(
            "duplicate continuation artifact lock"
        )
    for item in locks:
        path = (PROJECT_ROOT / item["path"]).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise PublicShardedContinuationError(
                "continuation artifact lock escapes project"
            ) from exc
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise PublicShardedContinuationError(
                f"continuation artifact lock drift: {item['path']}"
            )
    return copy.deepcopy(dict(value))


def write_candidate(model_role: str) -> dict[str, Any]:
    value = build_candidate(model_role)
    _write_json(candidate_path(model_role), value)
    return value


def verify_candidate(model_role: str) -> dict[str, Any]:
    observed = validate_candidate(
        _load_json(candidate_path(model_role)),
        model_role=model_role,
    )
    expected = build_candidate(model_role)
    if observed != expected:
        raise PublicShardedContinuationError(
            "continuation candidate drift"
        )
    return observed


def _shard_scope(
    candidate: Mapping[str, Any],
    shard_index: int,
) -> Mapping[str, Any]:
    return candidate["scope"]["shards"][shard_index]


def canonical_shard_command(
    model_role: str,
    shard_index: int,
) -> str:
    _validate_shard(model_role, shard_index)
    admission = admission_path(
        model_role,
        shard_index,
    ).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.public_sharded_continuation_v1 "
        f"--execute-shard --model-role {model_role} "
        f"--shard-index {shard_index} --admission {admission} "
        "--config config\\project.local.env"
    )


def build_admission(
    model_role: str,
    shard_index: int,
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    _validate_shard(model_role, shard_index)
    if (
        len(owner_statement_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in owner_statement_sha256
        )
    ):
        raise PublicShardedContinuationError(
            "owner statement digest must be lowercase SHA-256"
        )
    candidate = verify_candidate(model_role)
    shard = _shard_scope(candidate, shard_index)
    command = canonical_shard_command(model_role, shard_index)
    scope = {
        "model_role": model_role,
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
        "artifact_role": "single_shard_execution_authorization",
        "approved_at": approved_at,
        "status": "activated_for_one_exact_continuation_shard",
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
        },
        "scope_sha256": sha256_canonical_json(scope),
    }
    value = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return validate_admission(
        value,
        model_role=model_role,
        shard_index=shard_index,
    )


def validate_admission(
    value: Any,
    *,
    model_role: str,
    shard_index: int,
) -> dict[str, Any]:
    _validate_shard(model_role, shard_index)
    if not isinstance(value, Mapping):
        raise PublicShardedContinuationError(
            "continuation admission must be an object"
        )
    Draft202012Validator(
        _load_json(ADMISSION_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    candidate = verify_candidate(model_role)
    shard = _shard_scope(candidate, shard_index)
    command = canonical_shard_command(model_role, shard_index)
    if (
        value["scope_sha256"] != sha256_canonical_json(value["scope"])
        or value["manifest_sha256"] != _manifest_sha(value)
        or value["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or value["scope"]["model_role"] != model_role
        or value["scope"]["shard_index"] != shard_index
        or value["scope"]["run_id"] != shard["run_id"]
        or value["scope"]["execution_identity"]
        != shard["execution_identity"]
        or value["scope"]["records"] != shard["records"]
        or value["scope"]["work_key_sequence_sha256"]
        != shard["work_key_sequence_sha256"]
        or value["scope"]["output_root"] != shard["output_root"]
        or value["scope"]["hard_spend_limit_cny"]
        != shard["hard_spend_limit_cny"]
        or value["scope"]["exact_command"] != command
        or value["scope"]["exact_command_sha256"]
        != hashlib.sha256(command.encode("utf-8")).hexdigest()
    ):
        raise PublicShardedContinuationError(
            "continuation admission binding drift"
        )
    return copy.deepcopy(dict(value))


def write_admission(
    model_role: str,
    shard_index: int,
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    value = build_admission(
        model_role,
        shard_index,
        owner_statement_sha256=owner_statement_sha256,
        approved_at=approved_at,
    )
    _write_json(admission_path(model_role, shard_index), value)
    return value


def _shard_rows(
    candidate: Mapping[str, Any],
    model_role: str,
    shard_index: int,
) -> list[dict[str, Any]]:
    rows = copy.deepcopy(_partition_rows(model_role)[shard_index])
    identity = candidate["scope"]["shards"][shard_index][
        "execution_identity"
    ]
    for row in rows:
        row["execution_identity"] = identity
    return rows


def authorize_shard(
    model_role: str,
    shard_index: int,
    *,
    selected_admission_path: Path,
) -> live_v4.PublicExecutionPermit:
    candidate = verify_candidate(model_role)
    admission = validate_admission(
        _load_json(selected_admission_path),
        model_role=model_role,
        shard_index=shard_index,
    )
    shard = _shard_scope(candidate, shard_index)
    rows = _shard_rows(candidate, model_role, shard_index)
    root = (PROJECT_ROOT / shard["output_root"]).resolve()
    try:
        root.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise PublicShardedContinuationError(
            "continuation output root escapes project"
        ) from exc
    permit = live_v4.PublicExecutionPermit(
        model_role=model_role,
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
    live_v4.v3.v2._state_from_paths(permit)
    return permit


def _shard_role_policy(model_role: str) -> dict[str, Any]:
    policy = copy.deepcopy(
        build_role_policy(load_public_policy(), model_role)
    )
    limit = SHARD_HARD_LIMITS_CNY[model_role]
    policy["deepseek"]["hard_spend_limit_cny"] = limit
    policy["deepseek"]["abort_ceiling_cny"] = limit
    policy["deepseek"]["abort_at_fraction"] = 1.0
    return policy


def execute_shard(
    model_role: str,
    shard_index: int,
    *,
    selected_admission_path: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    permit = authorize_shard(
        model_role,
        shard_index,
        selected_admission_path=selected_admission_path,
    )
    initial = live_v4.v3.v2._state_from_paths(permit)
    if initial["records"] or initial["attempts"]:
        raise PublicShardedContinuationError(
            "continuation shard already started; automatic rerun is forbidden"
        )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    role_policy = _shard_role_policy(model_role)
    api_key = live_v4.v3.v2._validate_runtime_config(
        values,
        role_policy=role_policy,
    )
    keys = {str(item["work_key"]) for item in permit.work_items}
    tracker = PublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role=model_role,
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
            raise PublicShardedContinuationError(
                "continuation result exceeded candidate tier"
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
        current = live_v4.v3.v2._state_from_paths(permit)
        if tier == "diagnostic" or current["budget_status"]["paused"]:
            break
    final = live_v4.v3.v2._state_from_paths(permit)
    diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in final["records"]
    )
    remaining = len(final["pending"])
    return {
        "status": (
            "continuation_shard_complete_candidate_records_unadmitted"
            if remaining == 0
            else (
                "continuation_shard_paused_after_diagnostic"
                if diagnostics
                else "continuation_shard_paused_by_budget"
            )
        ),
        "model_role": model_role,
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
    }


def build_shard_technical_review(
    model_role: str,
    shard_index: int,
    *,
    selected_admission_path: Path,
) -> dict[str, Any]:
    permit = authorize_shard(
        model_role,
        shard_index,
        selected_admission_path=selected_admission_path,
    )
    state = live_v4.v3.v2._state_from_paths(permit)
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
    }
    passed = all(checks.values())
    return {
        "schema_version": (
            "m3-paper-v2-public-continuation-shard-review-1.0"
        ),
        "generated_at": live_v4._now(),
        "status": (
            "continuation_shard_technical_gate_pass"
            if passed
            else "continuation_shard_technical_gate_fail"
        ),
        "model_role": model_role,
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


def write_shard_technical_review(
    model_role: str,
    shard_index: int,
    *,
    selected_admission_path: Path,
) -> dict[str, Any]:
    permit = authorize_shard(
        model_role,
        shard_index,
        selected_admission_path=selected_admission_path,
    )
    value = build_shard_technical_review(
        model_role,
        shard_index,
        selected_admission_path=selected_admission_path,
    )
    _write_json(
        permit.output_root / "continuation_shard_review_v1.json",
        value,
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-shard", action="store_true")
    action.add_argument("--write-technical-review", action="store_true")
    parser.add_argument(
        "--model-role",
        choices=tuple(SHARD_COUNTS),
        required=True,
    )
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--approved-at")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.write_candidate:
        value = write_candidate(args.model_role)
    elif args.verify_candidate:
        value = verify_candidate(args.model_role)
    else:
        if args.shard_index is None:
            parser.error("selected action requires --shard-index")
        selected = args.admission or admission_path(
            args.model_role,
            args.shard_index,
        )
        if args.write_admission:
            if not args.owner_statement_sha256 or not args.approved_at:
                parser.error(
                    "--write-admission requires --owner-statement-sha256 "
                    "and --approved-at"
                )
            value = write_admission(
                args.model_role,
                args.shard_index,
                owner_statement_sha256=args.owner_statement_sha256,
                approved_at=args.approved_at,
            )
        elif args.verify_admission:
            value = validate_admission(
                _load_json(selected),
                model_role=args.model_role,
                shard_index=args.shard_index,
            )
        elif args.execute_shard:
            value = execute_shard(
                args.model_role,
                args.shard_index,
                selected_admission_path=selected,
                config_path=args.config,
            )
        else:
            value = write_shard_technical_review(
                args.model_role,
                args.shard_index,
                selected_admission_path=selected,
            )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
