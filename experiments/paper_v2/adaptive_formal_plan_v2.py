"""基于已准入 Pro 金丝雀经验构建的固化全面板自适应实验计划。

明确扩展评测任务集、对抗搜索策略（多模态/工具混淆）、收敛判定阈值与停止准则。
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.adaptive_cost_canary_plan_v1 as canary_plan
from experiments.paper_v2.contracts import (
    compute_online_visible_field_digest,
    sha256_canonical_json,
)
from experiments.paper_v2.formal_condition_executors import CONDITION_PROFILES
from experiments.paper_v2.medium_runtime import build_initial_online_state


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
EXTENSION_PATH = PROTOCOL_ROOT / "adaptive_attack_extension_v2.json"
CANDIDATE_PATH = PROTOCOL_ROOT / "adaptive_formal_pro_plan_candidate_v2.json"
PREFIX_ROOT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary"
)
PREFIX_TECHNICAL_REVIEW = PREFIX_ROOT / "technical_cost_review_v3_1.json"
PREFIX_QUERY_LEDGER = PREFIX_ROOT / "query_ledger.jsonl"
PREFIX_BUDGET_LEDGER = PREFIX_ROOT / "provider_budget_ledger.jsonl"
PREFIX_TASK_LEDGER = PREFIX_ROOT / "continuation_task_events_v3.jsonl"
PREFIX_CHECKPOINT_ROOT = PREFIX_ROOT / "search_checkpoints"
PREFIX_TRACE_ROOT = PREFIX_ROOT / "provider_traces"

SCHEMA_VERSION = "m3-paper-v2-adaptive-formal-pro-plan-2.0"
FROZEN_AT = "2026-08-02T01:14:00+08:00"
MODEL_KEY = "deepseek_pro"
MODEL_ID = "deepseek-v4-pro"
MODEL_ROLE = "primary"
PROVIDER_ID = "deepseek"
CONDITION_ID = "m3_full"
AUTHORIZATION_REGIME = "auto_compiled"
TASK_COUNT = 40
MAX_QUERY_INDEX = 2000
HARD_LIMIT_CNY = 180.0
QUERY_BUDGETS = (50, 200, 500)
SATURATION_BUDGET = 2000


class AdaptiveFormalPlanV2Error(ValueError):
    """当固化的自适应评估组或前缀发生漂移时抛出的异常。"""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveFormalPlanV2Error(f"{path}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise AdaptiveFormalPlanV2Error(f"{path}: expected object")
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


def _file_lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AdaptiveFormalPlanV2Error(f"missing frozen file: {path}")
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _prefix_lock(path: Path) -> dict[str, Any]:
    lock = _file_lock(path)
    lock["lock_semantics"] = "immutable_byte_prefix"
    return lock


def _verify_prefix_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock["path"])).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise AdaptiveFormalPlanV2Error("prefix lock escapes project") from exc
    length = int(lock["bytes"])
    if not path.is_file() or path.stat().st_size < length:
        raise AdaptiveFormalPlanV2Error(f"adaptive prefix truncated: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        remaining = length
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    if remaining or digest.hexdigest() != lock["sha256"]:
        raise AdaptiveFormalPlanV2Error(f"adaptive prefix drift: {path}")


def _trace_tree_lock() -> dict[str, Any]:
    if not PREFIX_TRACE_ROOT.is_dir():
        raise AdaptiveFormalPlanV2Error("adaptive prefix trace root is missing")
    rows = [
        {
            "path": path.relative_to(PREFIX_TRACE_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in sorted(PREFIX_TRACE_ROOT.glob("*.jsonl"))
        if path.is_file()
    ]
    if not rows:
        raise AdaptiveFormalPlanV2Error("adaptive prefix trace tree is empty")
    return {
        "root": _display_path(PREFIX_TRACE_ROOT),
        "file_count": len(rows),
        "total_bytes": sum(int(row["bytes"]) for row in rows),
        "entries_sha256": sha256_canonical_json(rows),
        "entries": rows,
        "existing_files_are_immutable": True,
    }


def _verify_trace_tree_lock(lock: Mapping[str, Any]) -> None:
    entries = lock.get("entries")
    root = (PROJECT_ROOT / str(lock.get("root", ""))).resolve()
    if not isinstance(entries, list) or not root.is_dir():
        raise AdaptiveFormalPlanV2Error("adaptive trace tree lock is invalid")
    if (
        lock.get("file_count") != len(entries)
        or lock.get("total_bytes")
        != sum(int(row["bytes"]) for row in entries)
        or lock.get("entries_sha256") != sha256_canonical_json(entries)
    ):
        raise AdaptiveFormalPlanV2Error("adaptive trace tree envelope drift")
    for entry in entries:
        path = root / str(entry["path"])
        if (
            not path.is_file()
            or path.stat().st_size != entry["bytes"]
            or _sha256_file(path) != entry["sha256"]
        ):
            raise AdaptiveFormalPlanV2Error(f"adaptive trace drift: {path}")


def load_extension() -> dict[str, Any]:
    value = _read_json(EXTENSION_PATH)
    if (
        value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("maximum_query_budget") != 79000
        or value.get("models", {}).get(MODEL_KEY, {}).get("model_id") != MODEL_ID
        or value.get("models", {}).get(MODEL_KEY, {}).get("budgets")
        != list(QUERY_BUDGETS)
        or len(value.get("models", {}).get(MODEL_KEY, {}).get("tasks", []))
        != TASK_COUNT
        or value.get("hardest_subset", {}).get("budget") != SATURATION_BUDGET
    ):
        raise AdaptiveFormalPlanV2Error("adaptive extension v2 drift")
    return value


def adaptive_query_work_key(case_id: str, query_index: int) -> str:
    if (
        not isinstance(case_id, str)
        or not case_id
        or isinstance(query_index, bool)
        or not isinstance(query_index, int)
        or not 1 <= query_index <= MAX_QUERY_INDEX
    ):
        raise AdaptiveFormalPlanV2Error("adaptive query identity is invalid")
    # Keep the v1 prefix so admitted q00001..q00050 records remain reusable.
    return f"adaptive-cost-v1__{case_id}__q{query_index:05d}"


def all_query_work_keys(tasks: list[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(
        adaptive_query_work_key(str(task["case_id"]), index)
        for task in tasks
        for index in range(1, MAX_QUERY_INDEX + 1)
    )


def _compact_tasks(extension: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = extension["models"][MODEL_KEY]["tasks"]
    compact: list[dict[str, Any]] = []
    seen: set[str] = set()
    for task_raw in raw:
        task = copy.deepcopy(dict(task_raw))
        case_id = str(task["case_id"])
        if case_id in seen:
            raise AdaptiveFormalPlanV2Error("duplicate Pro adaptive case")
        record = canary_plan._read_task_record(task)
        compact.append(
            {
                "case_id": case_id,
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
        seen.add(case_id)
    if len(compact) != TASK_COUNT:
        raise AdaptiveFormalPlanV2Error("Pro adaptive task count drift")
    return compact


def _prefix_review() -> dict[str, Any]:
    review = _read_json(PREFIX_TECHNICAL_REVIEW)
    if (
        review.get("status") != "adaptive_recovery_technical_gate_pass"
        or review.get("technical_gate_passed") is not True
        or review.get("terminal_query_count") != 374
        or review.get("completed_provider_call_count") != 562
        or review.get("diagnostic_query_count") != 1
    ):
        raise AdaptiveFormalPlanV2Error("Pro adaptive prefix is not admitted")
    return review


def build_candidate() -> dict[str, Any]:
    extension = load_extension()
    review = _prefix_review()
    tasks = _compact_tasks(extension)
    keys = all_query_work_keys(tasks)
    prefix = extension["formal_prefix"]
    if (
        prefix["terminal_query_count"] != review["terminal_query_count"]
        or prefix["completed_provider_call_count"]
        != review["completed_provider_call_count"]
        or prefix["execution_identity"] != review["execution_identity"]
        or prefix["run_id"] != review["run_id"]
    ):
        raise AdaptiveFormalPlanV2Error("extension/prefix review binding drift")
    checkpoint_locks = [
        _prefix_lock(path)
        for path in sorted(PREFIX_CHECKPOINT_ROOT.glob("*.json"))
    ]
    if len(checkpoint_locks) != 8:
        raise AdaptiveFormalPlanV2Error("expected eight prefix checkpoints")
    scope = {
        "run_id": prefix["run_id"],
        "execution_identity": prefix["execution_identity"],
        "provider_id": PROVIDER_ID,
        "model_id": MODEL_ID,
        "model_role": MODEL_ROLE,
        "condition_id": CONDITION_ID,
        "authorization_regime": AUTHORIZATION_REGIME,
        "task_count": TASK_COUNT,
        "query_budget_nodes": list(QUERY_BUDGETS),
        "hardest_subset_count": 20,
        "saturation_budget": SATURATION_BUDGET,
        "maximum_query_index_per_task": MAX_QUERY_INDEX,
        "known_work_key_count": len(keys),
        "known_work_key_sequence_sha256": sha256_canonical_json(keys),
        "maximum_query_budget_bound": extension["maximum_query_budget"],
        "hard_limit_cny": HARD_LIMIT_CNY,
        "output_root": _display_path(PREFIX_ROOT),
        "tasks": tasks,
        "formal_prefix": copy.deepcopy(prefix),
        "terminal_queries_must_not_be_replayed": True,
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "non_executable_full_adaptive_pro_plan_candidate",
        "status": "offline_qualified_execution_not_authorized",
        "frozen_at": FROZEN_AT,
        "execution_identity": prefix["execution_identity"],
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [
            _file_lock(Path(__file__)),
            _file_lock(EXTENSION_PATH),
            _file_lock(PREFIX_TECHNICAL_REVIEW),
        ],
        "append_only_prefix_locks": [
            _prefix_lock(PREFIX_QUERY_LEDGER),
            _prefix_lock(PREFIX_BUDGET_LEDGER),
            _prefix_lock(PREFIX_TASK_LEDGER),
            *checkpoint_locks,
        ],
        "trace_tree_lock": _trace_tree_lock(),
        "authorization": {
            "candidate_only": True,
            "stage_execution_authorized": False,
            "hardest_subset_selection_authorized_before_budget_500": False,
            "result_admission_authorized": False,
        },
        "safety_boundary": {
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "automatic_retries": 0,
            "terminal_diagnostic_retry_authorized": False,
            "trusted_fields_mutable": False,
            "payload_class": "synthetic_m3_case",
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_aggregated": False,
            "existing_terminal_queries_retried": 0,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveFormalPlanV2Error("adaptive formal candidate must be object")
    scope = value.get("scope")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or value.get("execution_identity") != scope.get("execution_identity")
        or scope.get("model_id") != MODEL_ID
        or scope.get("task_count") != TASK_COUNT
        or scope.get("known_work_key_count") != TASK_COUNT * MAX_QUERY_INDEX
        or scope.get("hard_limit_cny") != HARD_LIMIT_CNY
        or value.get("authorization", {}).get("stage_execution_authorized")
        is not False
        or value.get("safety_boundary", {}).get("automatic_retries") != 0
    ):
        raise AdaptiveFormalPlanV2Error("adaptive formal candidate drift")
    for lock in value.get("artifact_locks", []):
        path = PROJECT_ROOT / str(lock["path"])
        if (
            not path.is_file()
            or path.stat().st_size != lock["bytes"]
            or _sha256_file(path) != lock["sha256"]
        ):
            raise AdaptiveFormalPlanV2Error(f"artifact lock drift: {path}")
    for lock in value.get("append_only_prefix_locks", []):
        _verify_prefix_lock(lock)
    expected_trace = value.get("trace_tree_lock")
    if not isinstance(expected_trace, Mapping):
        raise AdaptiveFormalPlanV2Error("adaptive prefix trace tree missing")
    _verify_trace_tree_lock(expected_trace)
    return copy.deepcopy(dict(value))


def write_candidate(path: Path = CANDIDATE_PATH) -> dict[str, Any]:
    value = build_candidate()
    _write_json(path, value)
    return value


def verify_candidate(path: Path = CANDIDATE_PATH) -> dict[str, Any]:
    return validate_candidate(_read_json(path))


def resolve_candidate_task(
    candidate: Mapping[str, Any], case_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    matches = [
        dict(task)
        for task in candidate.get("scope", {}).get("tasks", [])
        if isinstance(task, Mapping) and task.get("case_id") == case_id
    ]
    if len(matches) != 1:
        raise AdaptiveFormalPlanV2Error("unknown full-panel adaptive task")
    task = matches[0]
    return task, canary_plan._read_task_record(task)


def build_query_work_item_and_state(
    candidate: Mapping[str, Any],
    *,
    case_id: str,
    query_index: int,
    mutated_payload: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(mutated_payload, str) or not mutated_payload:
        raise AdaptiveFormalPlanV2Error("mutated payload is required")
    task, source_record = resolve_candidate_task(candidate, case_id)
    if hashlib.sha256(
        str(source_record["untrusted_content"]).encode()
    ).hexdigest() != task["base_payload_sha256"]:
        raise AdaptiveFormalPlanV2Error("base adaptive payload drift")
    record = copy.deepcopy(source_record)
    trusted_before = sha256_canonical_json(
        {
            "trusted_user_request": record["trusted_user_request"],
            "trusted_app_context": record["trusted_app_context"],
            "untrusted_memory": record["untrusted_memory"],
        }
    )
    record["untrusted_content"] = mutated_payload
    trusted_after = sha256_canonical_json(
        {
            "trusted_user_request": record["trusted_user_request"],
            "trusted_app_context": record["trusted_app_context"],
            "untrusted_memory": record["untrusted_memory"],
        }
    )
    if trusted_before != trusted_after:
        raise AdaptiveFormalPlanV2Error("adaptive mutation changed trusted fields")
    work_item: dict[str, Any] = {
        "schema_version": "m3-paper-v2-adaptive-query-work-item-2.0",
        "execution_identity": candidate["execution_identity"],
        "work_key": adaptive_query_work_key(case_id, query_index),
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
        raise AdaptiveFormalPlanV2Error("adaptive state exposes evaluator fields")
    work_item["initial_online_visible_field_digest"] = digest
    return work_item, state


__all__ = [
    "CANDIDATE_PATH",
    "HARD_LIMIT_CNY",
    "MAX_QUERY_INDEX",
    "MODEL_ID",
    "PREFIX_ROOT",
    "QUERY_BUDGETS",
    "SATURATION_BUDGET",
    "TASK_COUNT",
    "AdaptiveFormalPlanV2Error",
    "adaptive_query_work_key",
    "all_query_work_keys",
    "build_candidate",
    "build_query_work_item_and_state",
    "resolve_candidate_task",
    "validate_candidate",
    "verify_candidate",
    "write_candidate",
]
