"""策略感知、严格限制 5 元人民币预算的 DeepSeek Flash 公开接续控制器。

微调单次调用延迟与最大尝试次数，严格控制小额预算消耗。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping

import experiments.paper_v2.formal_matrix_controller_v1 as medium_v1
import experiments.paper_v2.public_live_controller_v4 as live_v4
import experiments.paper_v2.public_sharded_continuation_v1 as source_v1
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
    hydrate_public_work_item,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    build_role_policy,
    load_public_policy,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
QUALIFICATION_PATH = (
    PROTOCOL_ROOT / "public_second_continuation_qualification_v2.json"
)
CANDIDATE_PATH = (
    PROTOCOL_ROOT / "public_second_continuation_candidate_v2.json"
)
SHARD_COUNT = 2
ROLE_TOTAL_HARD_LIMIT_CNY = 5.0
GENERATED_AT = "2026-08-02T01:00:00+08:00"
MODEL_ROLE = "second"
MODEL_ID = "deepseek-v4-flash"


class PublicSecondContinuationV2Error(ValueError):
    """当 Flash 接续无法保持安全闭合时抛出的异常。"""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicSecondContinuationV2Error(f"{path}: expected object")
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
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicSecondContinuationV2Error(
            f"missing Flash continuation artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def source_candidate_path() -> Path:
    return source_v1.candidate_path(MODEL_ROLE)


def admission_path(shard_index: int) -> Path:
    if not 0 <= shard_index < SHARD_COUNT:
        raise PublicSecondContinuationV2Error("Flash shard index out of range")
    return (
        PROTOCOL_ROOT
        / "admissions"
        / f"deepseek_public_second_continuation_s{shard_index}_admission_v2.json"
    )


def _source_candidate() -> dict[str, Any]:
    return source_v1.validate_candidate(
        _read_json(source_candidate_path()),
        model_role=MODEL_ROLE,
    )


def _partitions() -> list[list[dict[str, Any]]]:
    partitions = source_v1._partition_rows(MODEL_ROLE)
    if len(partitions) != SHARD_COUNT:
        raise PublicSecondContinuationV2Error("Flash partition count drift")
    keys = [str(row["work_key"]) for rows in partitions for row in rows]
    if len(keys) != 1779 or len(set(keys)) != len(keys):
        raise PublicSecondContinuationV2Error(
            "Flash continuation must contain 1,779 unique non-canary rows"
        )
    return copy.deepcopy(partitions)


def _per_shard_limit(canary_cost: float) -> float:
    remaining = ROLE_TOTAL_HARD_LIMIT_CNY - canary_cost
    if remaining <= 0:
        raise PublicSecondContinuationV2Error(
            "Flash canary exhausted the role total hard limit"
        )
    return math.floor((remaining / SHARD_COUNT) * 100_000_000) / 100_000_000


def build_qualification() -> dict[str, Any]:
    source = _source_candidate()
    partitions = _partitions()
    canary_cost = float(source["scope"]["source_canary_cost_cny"])
    limit = _per_shard_limit(canary_cost)
    source_roots = [
        PROJECT_ROOT / str(shard["output_root"])
        for shard in source["scope"]["shards"]
    ]
    nonempty = [
        _display_path(root)
        for root in source_roots
        if root.exists()
        and any(path.is_file() and path.stat().st_size for path in root.rglob("*"))
    ]
    if nonempty:
        raise PublicSecondContinuationV2Error(
            "unqualified v1 Flash shard output already exists"
        )
    core = {
        "schema_version": "m3-paper-v2-public-second-continuation-qualification-2.0",
        "status": "policy_aware_flash_continuation_qualified_offline",
        "qualified_at": GENERATED_AT,
        "source_candidate_manifest_sha256": source["manifest_sha256"],
        "source_v1_nonempty_output_roots": nonempty,
        "source_canary_records": source["scope"]["source_canary_records"],
        "source_canary_cost_cny": canary_cost,
        "continuation_records": sum(len(rows) for rows in partitions),
        "shard_count": SHARD_COUNT,
        "per_shard_hard_limit_cny": limit,
        "projected_total_ceiling_cny": round(
            canary_cost + SHARD_COUNT * limit, 10
        ),
        "policy_forwarded_to_every_state_reconstruction": True,
        "network_calls": 0,
        "provider_calls": 0,
        "credentials_read": False,
        "scientific_outcomes_accessed": False,
    }
    if core["projected_total_ceiling_cny"] > ROLE_TOTAL_HARD_LIMIT_CNY:
        raise PublicSecondContinuationV2Error("Flash projected ceiling exceeds CNY 5")
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_qualification() -> dict[str, Any]:
    value = build_qualification()
    _write_json(QUALIFICATION_PATH, value)
    return value


def verify_qualification() -> dict[str, Any]:
    observed = _read_json(QUALIFICATION_PATH)
    expected = build_qualification()
    if observed != expected:
        raise PublicSecondContinuationV2Error(
            "Flash continuation qualification drift"
        )
    return observed


def build_candidate() -> dict[str, Any]:
    source = _source_candidate()
    qualification = verify_qualification()
    partitions = _partitions()
    shards: list[dict[str, Any]] = []
    for index, rows in enumerate(partitions):
        identity = sha256_canonical_json(
            {
                "schema_version": "m3-paper-v2-public-second-shard-identity-2.0",
                "source_candidate_manifest_sha256": source["manifest_sha256"],
                "qualification_manifest_sha256": qualification[
                    "manifest_sha256"
                ],
                "shard_index": index,
                "work_keys": [row["work_key"] for row in rows],
            }
        )
        shards.append(
            {
                "shard_index": index,
                "records": len(rows),
                "work_key_sequence_sha256": sha256_canonical_json(
                    [row["work_key"] for row in rows]
                ),
                "execution_identity": identity,
                "run_id": f"paper-v2-public-second-continuation-s{index}-v2",
                "output_root": (
                    "outputs/paper_upgrade_v2/formal_public/deepseek/"
                    f"public-second-continuation-s{index}-v2-{identity}"
                ),
                "hard_spend_limit_cny": qualification[
                    "per_shard_hard_limit_cny"
                ],
            }
        )
    scope = {
        "model_role": MODEL_ROLE,
        "model_id": MODEL_ID,
        "source_candidate_manifest_sha256": source["manifest_sha256"],
        "source_canary_admission_manifest_sha256": source["scope"][
            "source_canary_admission_manifest_sha256"
        ],
        "source_canary_technical_review_sha256": source["scope"][
            "source_canary_technical_review_sha256"
        ],
        "source_canary_records": source["scope"]["source_canary_records"],
        "source_canary_cost_cny": source["scope"]["source_canary_cost_cny"],
        "continuation_records": sum(item["records"] for item in shards),
        "shard_count": SHARD_COUNT,
        "shards": shards,
        "partition": {
            "rule": "remaining_plan_order_round_robin",
            "disjoint": True,
            "complete": True,
            "terminal_canary_rows_excluded": True,
        },
        "budget": {
            "provider": "deepseek",
            "role_total_hard_limit_cny": ROLE_TOTAL_HARD_LIMIT_CNY,
            "per_shard_hard_limit_cny": qualification[
                "per_shard_hard_limit_cny"
            ],
            "all_shards_hard_limit_cny": round(
                SHARD_COUNT * qualification["per_shard_hard_limit_cny"], 10
            ),
            "source_canary_cost_cny": source["scope"][
                "source_canary_cost_cny"
            ],
            "projected_total_ceiling_cny": qualification[
                "projected_total_ceiling_cny"
            ],
            "automatic_retries": 0,
        },
        "execution": {
            "maximum_parallel_shards": SHARD_COUNT,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "result_admission_is_separate": True,
            "same_identity_resume_after_any_terminal_record": False,
        },
    }
    artifact_paths = [
        Path(__file__),
        QUALIFICATION_PATH,
        source_candidate_path(),
        PROJECT_ROOT / "experiments/paper_v2/public_execution_store_v1.py",
        PROJECT_ROOT / "experiments/paper_v2/public_live_controller_v4.py",
        PROJECT_ROOT / "experiments/paper_v2/public_sharded_continuation_v1.py",
        PROJECT_ROOT / "protocols/paper_upgrade_v2/public_execution_plan_v1.jsonl",
    ]
    core = {
        "schema_version": "m3-paper-v2-public-second-continuation-candidate-2.0",
        "artifact_role": "owner_review_candidate",
        "generated_at": GENERATED_AT,
        "status": "candidate_pending_exact_command_shard_approvals",
        "scope": scope,
        "artifact_locks": [
            _lock(path) for path in sorted(artifact_paths, key=lambda item: item.as_posix())
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
    return validate_candidate(
        {**core, "manifest_sha256": sha256_canonical_json(core)}
    )


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicSecondContinuationV2Error("Flash candidate must be object")
    scope = value.get("scope")
    if not isinstance(scope, Mapping):
        raise PublicSecondContinuationV2Error("Flash candidate scope missing")
    shards = scope.get("shards")
    locks = value.get("artifact_locks")
    if (
        value.get("schema_version")
        != "m3-paper-v2-public-second-continuation-candidate-2.0"
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("model_role") != MODEL_ROLE
        or scope.get("model_id") != MODEL_ID
        or scope.get("continuation_records") != 1779
        or scope.get("shard_count") != SHARD_COUNT
        or not isinstance(shards, list)
        or len(shards) != SHARD_COUNT
        or scope["budget"]["projected_total_ceiling_cny"]
        > ROLE_TOTAL_HARD_LIMIT_CNY
        or scope["budget"]["automatic_retries"] != 0
        or value["authorization"]["shard_execution_authorized"] is not False
        or not isinstance(locks, list)
    ):
        raise PublicSecondContinuationV2Error("Flash candidate drift")
    if len({item["path"] for item in locks}) != len(locks):
        raise PublicSecondContinuationV2Error("duplicate Flash artifact lock")
    for item in locks:
        path = (PROJECT_ROOT / str(item["path"])).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise PublicSecondContinuationV2Error(
                "Flash artifact lock escapes project"
            ) from exc
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise PublicSecondContinuationV2Error(
                f"Flash artifact lock drift: {item['path']}"
            )
    return copy.deepcopy(dict(value))


def write_candidate() -> dict[str, Any]:
    value = build_candidate()
    _write_json(CANDIDATE_PATH, value)
    return value


def verify_candidate() -> dict[str, Any]:
    observed = validate_candidate(_read_json(CANDIDATE_PATH))
    expected = build_candidate()
    if observed != expected:
        raise PublicSecondContinuationV2Error("Flash candidate artifact drift")
    return observed


def canonical_shard_command(shard_index: int) -> str:
    admission = admission_path(shard_index).relative_to(PROJECT_ROOT)
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.public_second_continuation_v2 "
        f"--execute-shard --shard-index {shard_index} "
        f"--admission {admission} --config config\\project.local.env"
    )


def build_admission(
    shard_index: int,
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    if len(owner_statement_sha256) != 64 or any(
        character not in "0123456789abcdef"
        for character in owner_statement_sha256
    ):
        raise PublicSecondContinuationV2Error(
            "owner statement digest must be lowercase SHA-256"
        )
    candidate = verify_candidate()
    shard = candidate["scope"]["shards"][shard_index]
    command = canonical_shard_command(shard_index)
    scope = {
        "model_role": MODEL_ROLE,
        "shard_index": shard_index,
        "run_id": shard["run_id"],
        "execution_identity": shard["execution_identity"],
        "model_id": MODEL_ID,
        "records": shard["records"],
        "work_key_sequence_sha256": shard["work_key_sequence_sha256"],
        "output_root": shard["output_root"],
        "hard_spend_limit_cny": shard["hard_spend_limit_cny"],
        "exact_command": command,
        "exact_command_sha256": hashlib.sha256(command.encode()).hexdigest(),
    }
    core = {
        "schema_version": "m3-paper-v2-public-second-continuation-admission-2.0",
        "artifact_role": "single_shard_execution_authorization",
        "approved_at": approved_at,
        "status": "activated_for_one_exact_flash_shard",
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
    return validate_admission(
        {**core, "manifest_sha256": sha256_canonical_json(core)},
        shard_index=shard_index,
    )


def validate_admission(value: Any, *, shard_index: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicSecondContinuationV2Error("Flash admission must be object")
    candidate = verify_candidate()
    shard = candidate["scope"]["shards"][shard_index]
    scope = value.get("scope")
    command = canonical_shard_command(shard_index)
    if (
        value.get("schema_version")
        != "m3-paper-v2-public-second-continuation-admission-2.0"
        or value.get("manifest_sha256") != _manifest_sha(value)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or value["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or value["authorization"]["shard_execution_authorized"] is not True
        or value["authorization"]["result_admission_authorized"] is not False
        or scope.get("shard_index") != shard_index
        or scope.get("run_id") != shard["run_id"]
        or scope.get("execution_identity") != shard["execution_identity"]
        or scope.get("records") != shard["records"]
        or scope.get("work_key_sequence_sha256")
        != shard["work_key_sequence_sha256"]
        or scope.get("output_root") != shard["output_root"]
        or scope.get("hard_spend_limit_cny")
        != shard["hard_spend_limit_cny"]
        or scope.get("exact_command") != command
        or value["evidence_boundary"]["automatic_retries"] != 0
    ):
        raise PublicSecondContinuationV2Error("Flash admission binding drift")
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


def _role_policy(candidate: Mapping[str, Any]) -> dict[str, Any]:
    policy = copy.deepcopy(build_role_policy(load_public_policy(), MODEL_ROLE))
    limit = float(candidate["scope"]["budget"]["per_shard_hard_limit_cny"])
    policy["deepseek"]["hard_spend_limit_cny"] = limit
    policy["deepseek"]["abort_ceiling_cny"] = limit
    policy["deepseek"]["abort_at_fraction"] = 1.0
    return policy


def _shard_rows(
    candidate: Mapping[str, Any], shard_index: int
) -> list[dict[str, Any]]:
    rows = _partitions()[shard_index]
    identity = candidate["scope"]["shards"][shard_index][
        "execution_identity"
    ]
    for row in rows:
        row["execution_identity"] = identity
    return rows


def _state(
    permit: live_v4.PublicExecutionPermit,
    *,
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    expected_limit = float(
        permit.candidate["scope"]["budget"]["per_shard_hard_limit_cny"]
    )
    if (
        role_policy["deepseek"]["model_id"] != MODEL_ID
        or float(role_policy["deepseek"]["abort_ceiling_cny"])
        != expected_limit
    ):
        raise PublicSecondContinuationV2Error(
            "Flash state reconstruction requires exact shard policy"
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
        model_role=MODEL_ROLE,
        known_work_keys=keys,
        role_policy=role_policy,
    )
    terminal = set(record_status["terminal_work_keys"])
    if terminal != set(attempt_status["terminal_by_work_key"]):
        raise PublicSecondContinuationV2Error(
            "Flash record and attempt terminals differ"
        )
    if attempt_status["open_work_keys"]:
        raise PublicSecondContinuationV2Error(
            "open Flash attempt forbids automatic resume"
        )
    cross_bind_public_budget_and_records(
        budget_events=budgets,
        record_entries=records,
        trace_root=permit.trace_root,
        role_policy=role_policy,
    )
    for item in permit.work_items:
        key = str(item["work_key"])
        if key not in terminal and (permit.trace_root / f"{key}.jsonl").exists():
            raise PublicSecondContinuationV2Error(
                "pending Flash item already owns a provider trace"
            )
    return {
        "records": records,
        "record_status": record_status,
        "attempts": attempts,
        "attempt_status": attempt_status,
        "budgets": budgets,
        "budget_status": budget_status,
        "pending": [
            copy.deepcopy(item)
            for item in permit.work_items
            if str(item["work_key"]) not in terminal
        ],
    }


def authorize_shard(
    shard_index: int, *, selected_admission_path: Path
) -> live_v4.PublicExecutionPermit:
    candidate = verify_candidate()
    admission = validate_admission(
        _read_json(selected_admission_path), shard_index=shard_index
    )
    shard = candidate["scope"]["shards"][shard_index]
    rows = _shard_rows(candidate, shard_index)
    root = (PROJECT_ROOT / str(shard["output_root"])).resolve()
    try:
        root.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise PublicSecondContinuationV2Error(
            "Flash output root escapes project"
        ) from exc
    permit = live_v4.PublicExecutionPermit(
        model_role=MODEL_ROLE,
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
    _state(permit, role_policy=_role_policy(candidate))
    return permit


def execute_shard(
    shard_index: int,
    *,
    selected_admission_path: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    permit = authorize_shard(
        shard_index, selected_admission_path=selected_admission_path
    )
    role_policy = _role_policy(permit.candidate)
    initial = _state(permit, role_policy=role_policy)
    if initial["records"] or initial["attempts"] or initial["budgets"]:
        raise PublicSecondContinuationV2Error(
            "Flash shard already started; same-identity rerun is forbidden"
        )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    api_key = live_v4.v3.v2._validate_runtime_config(
        values, role_policy=role_policy
    )
    keys = {str(item["work_key"]) for item in permit.work_items}
    tracker = PublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role=MODEL_ROLE,
        known_work_keys=keys,
        role_policy=role_policy,
    )
    dispatcher = (dispatcher_factory or live_v4._build_dispatcher)(
        permit,
        tracker,
        api_key=api_key,
        role_policy=role_policy,
    )
    completed = 0
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
        if result.get("result_tier") not in {"formal_candidate", "diagnostic"}:
            raise PublicSecondContinuationV2Error(
                "Flash result exceeded candidate tier"
            )
        result["admission_manifest_sha256"] = permit.admission_file_sha256
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
            event_type="diagnostic" if tier == "diagnostic" else "completed",
            record_entry_sha256=str(entry["entry_sha256"]),
        )
        completed += 1
        current = _state(permit, role_policy=role_policy)
        if tier == "diagnostic" or current["budget_status"]["paused"]:
            break
    final = _state(permit, role_policy=role_policy)
    diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in final["records"]
    )
    remaining = len(final["pending"])
    return {
        "status": (
            "flash_shard_complete_candidate_records_unadmitted"
            if remaining == 0
            else (
                "flash_shard_sealed_after_diagnostic"
                if diagnostics
                else "flash_shard_sealed_by_budget"
            )
        ),
        "model_role": MODEL_ROLE,
        "shard_index": shard_index,
        "run_id": permit.run_id,
        "records": len(permit.work_items),
        "record_count": len(final["records"]),
        "diagnostic_records": diagnostics,
        "remaining_records": remaining,
        "completed_this_process": completed,
        "provider_calls_completed": final["budget_status"]["event_count"],
        "role_cumulative_usage": final["budget_status"]["role_cumulative_usage"],
        "role_cumulative_cost_cny": final["budget_status"][
            "role_cumulative_cost_cny"
        ],
        "result_admission_authorized": False,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }


def build_technical_review(
    shard_index: int, *, selected_admission_path: Path
) -> dict[str, Any]:
    permit = authorize_shard(
        shard_index, selected_admission_path=selected_admission_path
    )
    state = _state(permit, role_policy=_role_policy(permit.candidate))
    records = state["records"]
    expected = len(permit.work_items)
    checks = {
        "exact_record_count": len(records) == expected,
        "all_attempts_terminal": not state["attempt_status"]["open_work_keys"],
        "all_result_tiers_formal_candidate": all(
            entry["record"]["result_tier"] == "formal_candidate"
            for entry in records
        ),
        "budget_not_paused": state["budget_status"]["paused"] is False,
        "budget_and_records_cross_bound": True,
        "terminal_canary_rows_excluded": True,
        "exact_shard_policy_used": True,
    }
    passed = all(checks.values())
    return {
        "schema_version": "m3-paper-v2-public-second-shard-review-2.0",
        "generated_at": live_v4._now(),
        "status": (
            "flash_continuation_shard_technical_gate_pass"
            if passed
            else "flash_continuation_shard_technical_gate_fail"
        ),
        "model_role": MODEL_ROLE,
        "shard_index": shard_index,
        "run_id": permit.run_id,
        "candidate_manifest_sha256": permit.candidate["manifest_sha256"],
        "admission_file_sha256": permit.admission_file_sha256,
        "expected_records": expected,
        "observed_records": len(records),
        "provider_calls_completed": state["budget_status"]["event_count"],
        "role_cumulative_cost_cny": state["budget_status"][
            "role_cumulative_cost_cny"
        ],
        "checks": checks,
        "result_admission_eligible": passed,
        "review_boundary": {
            "scientific_outcomes_accessed": False,
            "condition_effects_compared": False,
            "result_admission_authorized": False,
        },
    }


def write_technical_review(
    shard_index: int, *, selected_admission_path: Path
) -> dict[str, Any]:
    permit = authorize_shard(
        shard_index, selected_admission_path=selected_admission_path
    )
    value = build_technical_review(
        shard_index, selected_admission_path=selected_admission_path
    )
    _write_json(permit.output_root / "continuation_shard_review_v2.json", value)
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
            parser.error("shard actions require --shard-index")
        selected = args.admission or admission_path(args.shard_index)
        if args.write_admission:
            if not args.owner_statement_sha256 or not args.approved_at:
                parser.error(
                    "--write-admission requires owner digest and approved time"
                )
            value = write_admission(
                args.shard_index,
                owner_statement_sha256=args.owner_statement_sha256,
                approved_at=args.approved_at,
            )
        elif args.verify_admission:
            value = validate_admission(
                _read_json(selected), shard_index=args.shard_index
            )
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
