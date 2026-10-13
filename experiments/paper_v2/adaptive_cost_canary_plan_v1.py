"""DeepSeek 自适应成本金丝雀实验的固化盲测计划。

在实验执行前锁定 8 大代表性任务、固定查询轮次上限与搜索空间，防止就地调整偏差。
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.adaptive_runner import load_adaptive_freeze
from experiments.paper_v2.contracts import (
    compute_online_visible_field_digest,
    sha256_canonical_json,
)
from experiments.paper_v2.formal_condition_executors import (
    CONDITION_PROFILES,
)
from experiments.paper_v2.medium_runtime import build_initial_online_state


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FREEZE = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/adaptive_attack_freeze_v1.json"
)
DEFAULT_CANDIDATE = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/adaptive_cost_canary_candidate_v1.json"
)
SELECTION_SEED = "m3-paper-v2-adaptive-cost-canary-v1"
SCHEMA_VERSION = "m3-paper-v2-adaptive-cost-canary-candidate-1.0"
PLAN_VERSION = "m3-paper-v2-adaptive-cost-canary-plan-1.0"
FROZEN_AT = "2026-07-28T04:30:00+08:00"
TASK_COUNT = 8
QUERY_BUDGET = 50
MAX_QUERIES = TASK_COUNT * QUERY_BUDGET
MODEL_ID = "deepseek-v4-pro"
MODEL_ROLE = "primary"
CONDITION_ID = "m3_full"
AUTHORIZATION_REGIME = "auto_compiled"
RUN_ID = "adaptive-cost-canary-primary-v1"


class AdaptiveCostCanaryPlanError(ValueError):
    """当自适应金丝雀计划或查询投影发生漂移时抛出的异常。"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AdaptiveCostCanaryPlanError(f"{path}: expected an object")
    return value


def _read_task_record(task: Mapping[str, Any]) -> dict[str, Any]:
    source = PROJECT_ROOT / str(task["source"])
    lines = source.read_text(encoding="utf-8").splitlines()
    line_number = task.get("source_line")
    if (
        isinstance(line_number, bool)
        or not isinstance(line_number, int)
        or line_number < 1
        or line_number > len(lines)
    ):
        raise AdaptiveCostCanaryPlanError("adaptive source line is invalid")
    value = json.loads(lines[line_number - 1])
    if (
        not isinstance(value, dict)
        or value.get("case_id") != task.get("case_id")
        or sha256_canonical_json(value)
        != task.get("source_record_sha256")
    ):
        raise AdaptiveCostCanaryPlanError(
            f"{task.get('case_id')}: adaptive source identity drift"
        )
    return value


def _selection_rank(task: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        f"{SELECTION_SEED}\0{task['case_id']}".encode()
    ).hexdigest()


def select_cost_canary_tasks(
    freeze: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """按固化的哈希顺序选择八个不同的攻击家族任务。"""

    primary = freeze.get("primary_model")
    if not isinstance(primary, Mapping):
        raise AdaptiveCostCanaryPlanError("primary adaptive panel is missing")
    raw_tasks = primary.get("tasks")
    if not isinstance(raw_tasks, list):
        raise AdaptiveCostCanaryPlanError("primary adaptive tasks are missing")
    ordered = sorted(
        (copy.deepcopy(dict(task)) for task in raw_tasks),
        key=lambda task: (_selection_rank(task), str(task["case_id"])),
    )
    selected: list[dict[str, Any]] = []
    families: set[str] = set()
    for task in ordered:
        stratum = task.get("stratum")
        if not isinstance(stratum, Mapping):
            raise AdaptiveCostCanaryPlanError("adaptive task stratum is missing")
        family = str(stratum.get("attack_family", ""))
        if not family or family in families:
            continue
        _read_task_record(task)
        selected.append(task)
        families.add(family)
        if len(selected) == TASK_COUNT:
            break
    if len(selected) != TASK_COUNT or len(families) != TASK_COUNT:
        raise AdaptiveCostCanaryPlanError(
            "adaptive canary cannot cover eight distinct attack families"
        )
    return selected


def query_work_key(case_id: str, query_index: int) -> str:
    if query_index < 1 or query_index > QUERY_BUDGET:
        raise AdaptiveCostCanaryPlanError("adaptive query index is out of range")
    return f"adaptive-cost-v1__{case_id}__q{query_index:05d}"


def all_query_work_keys(
    tasks: list[Mapping[str, Any]],
) -> tuple[str, ...]:
    return tuple(
        query_work_key(str(task["case_id"]), query)
        for task in tasks
        for query in range(1, QUERY_BUDGET + 1)
    )


def _candidate_scope(freeze_path: Path) -> dict[str, Any]:
    freeze = load_adaptive_freeze(freeze_path)
    tasks = select_cost_canary_tasks(freeze)
    source = PROJECT_ROOT / str(freeze["source_lock"]["path"])
    observed_source_sha = _sha256_file(source)
    if observed_source_sha != freeze["source_lock"]["sha256"]:
        raise AdaptiveCostCanaryPlanError("adaptive source lock drift")
    compact_tasks = []
    for task in tasks:
        record = _read_task_record(task)
        compact_tasks.append(
            {
                "case_id": task["case_id"],
                "source": task["source"],
                "source_line": task["source_line"],
                "source_record_sha256": task["source_record_sha256"],
                "attack_family": task["stratum"]["attack_family"],
                "language": task["stratum"]["language"],
                "base_payload_sha256": hashlib.sha256(
                    str(record["untrusted_content"]).encode()
                ).hexdigest(),
            }
        )
    work_keys = all_query_work_keys(tasks)
    return {
        "plan_version": PLAN_VERSION,
        "run_id": RUN_ID,
        "model_role": MODEL_ROLE,
        "provider_id": "deepseek",
        "endpoint_type": "official_api",
        "model_id": MODEL_ID,
        "condition_id": CONDITION_ID,
        "authorization_regime": AUTHORIZATION_REGIME,
        "task_count": TASK_COUNT,
        "query_budget_per_task": QUERY_BUDGET,
        "maximum_queries": MAX_QUERIES,
        "maximum_provider_calls_per_query": CONDITION_PROFILES[
            CONDITION_ID
        ].max_provider_calls,
        "maximum_provider_calls": (
            MAX_QUERIES
            * CONDITION_PROFILES[CONDITION_ID].max_provider_calls
        ),
        "stop_on_first_unsafe_effect": True,
        "selection": {
            "seed": SELECTION_SEED,
            "rule": (
                "Sort primary frozen tasks by SHA-256(seed, case_id), then "
                "take the first task from each unseen attack family until "
                "eight tasks are selected."
            ),
            "outcome_fields_read": [],
            "distinct_attack_families": TASK_COUNT,
        },
        "tasks": compact_tasks,
        "query_work_key_sequence_sha256": sha256_canonical_json(work_keys),
        "adaptive_freeze_sha256": _sha256_file(freeze_path),
        "source_lock_sha256": observed_source_sha,
        "output_root": "outputs/paper_upgrade_v2/adaptive_cost_canary_v1/primary",
    }


def build_candidate(
    freeze_path: Path = DEFAULT_FREEZE,
) -> dict[str, Any]:
    scope = _candidate_scope(freeze_path)
    execution_identity = sha256_canonical_json(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": scope,
            "frozen_at": FROZEN_AT,
        }
    )
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "non_executable_adaptive_cost_canary_candidate",
        "status": "offline_qualified_execution_not_authorized",
        "frozen_at": FROZEN_AT,
        "execution_identity": execution_identity,
        "scope": scope,
        "execution_authorization": {
            "canary_execution_authorized": False,
            "formal_continuation_authorized": False,
            "result_admission_authorized": False,
            "network_calls_made": 0,
            "credentials_read": False,
        },
        "safety_boundary": {
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "automatic_retries": 0,
            "payload_class": "synthetic_m3_case",
            "query_mutation_target": "untrusted_content",
            "trusted_fields_mutable": False,
        },
        "cost_gate": {
            "currency": "CNY",
            "hard_limit": 5.0,
            "concurrency": 1,
            "first_http_429": "pause",
            "first_identity_mismatch": "pause",
            "first_open_query_event": "manual_review_no_automatic_rerun",
        },
        "scope_sha256": sha256_canonical_json(scope),
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def verify_candidate(
    path: Path = DEFAULT_CANDIDATE,
    *,
    freeze_path: Path = DEFAULT_FREEZE,
) -> dict[str, Any]:
    observed = _load_json(path)
    expected = build_candidate(freeze_path)
    if observed != expected:
        raise AdaptiveCostCanaryPlanError(
            "adaptive cost canary candidate drift"
        )
    return observed


def resolve_candidate_task(
    candidate: Mapping[str, Any],
    case_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    tasks = candidate.get("scope", {}).get("tasks", [])
    matches = [
        dict(task)
        for task in tasks
        if isinstance(task, Mapping) and task.get("case_id") == case_id
    ]
    if len(matches) != 1:
        raise AdaptiveCostCanaryPlanError("unknown adaptive canary task")
    task = matches[0]
    record = _read_task_record(task)
    return task, record


def build_query_work_item_and_state(
    candidate: Mapping[str, Any],
    *,
    case_id: str,
    query_index: int,
    mutated_payload: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """仅将单个变异投影到不可信内容中，不引入任何其他副作用。"""

    if not isinstance(mutated_payload, str) or not mutated_payload:
        raise AdaptiveCostCanaryPlanError("mutated payload is required")
    task, source_record = resolve_candidate_task(candidate, case_id)
    if hashlib.sha256(
        str(source_record["untrusted_content"]).encode()
    ).hexdigest() != task["base_payload_sha256"]:
        raise AdaptiveCostCanaryPlanError("base adaptive payload drift")
    record = copy.deepcopy(source_record)
    before_trusted = sha256_canonical_json(
        {
            "trusted_user_request": record["trusted_user_request"],
            "trusted_app_context": record["trusted_app_context"],
            "untrusted_memory": record["untrusted_memory"],
        }
    )
    record["untrusted_content"] = mutated_payload
    after_trusted = sha256_canonical_json(
        {
            "trusted_user_request": record["trusted_user_request"],
            "trusted_app_context": record["trusted_app_context"],
            "untrusted_memory": record["untrusted_memory"],
        }
    )
    if before_trusted != after_trusted:
        raise AdaptiveCostCanaryPlanError(
            "adaptive mutation changed a non-target field"
        )
    work_item: dict[str, Any] = {
        "schema_version": "m3-paper-v2-adaptive-query-work-item-1.0",
        "execution_identity": candidate["execution_identity"],
        "work_key": query_work_key(case_id, query_index),
        "case_id": case_id,
        "benchmark": "m3-v2",
        "condition_id": CONDITION_ID,
        "evaluation_case_type": "attack",
        "authorization_regime": AUTHORIZATION_REGIME,
        "max_provider_calls": CONDITION_PROFILES[
            CONDITION_ID
        ].max_provider_calls,
        "query_index": query_index,
        "mutated_payload_sha256": hashlib.sha256(
            mutated_payload.encode()
        ).hexdigest(),
        "source_record_sha256": task["source_record_sha256"],
    }
    state = build_initial_online_state(
        work_item,
        {"benchmark": "m3-v2"},
        record,
    )
    digest = compute_online_visible_field_digest(state)
    if digest["forbidden_fields_present"]:
        raise AdaptiveCostCanaryPlanError(
            "adaptive query state exposes evaluator fields"
        )
    work_item["initial_online_visible_field_digest"] = digest
    return work_item, state


__all__ = [
    "AUTHORIZATION_REGIME",
    "AdaptiveCostCanaryPlanError",
    "CONDITION_ID",
    "DEFAULT_CANDIDATE",
    "DEFAULT_FREEZE",
    "MAX_QUERIES",
    "MODEL_ID",
    "MODEL_ROLE",
    "QUERY_BUDGET",
    "RUN_ID",
    "TASK_COUNT",
    "all_query_work_keys",
    "build_candidate",
    "build_query_work_item_and_state",
    "query_work_key",
    "resolve_candidate_task",
    "select_cost_canary_tasks",
    "verify_candidate",
]
