"""Provider-isolated 20-task adaptive plans for Flash and Gemini.

Both plans mirror the frozen ``second_model`` task set and budget nodes 50/200.
They share no mutable identity, work key, checkpoint, ledger, or output root.
This module is offline-only and never reads credentials or performs transport.
"""

from __future__ import annotations

import argparse
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
CONDITION_ID = "m3_full"
AUTHORIZATION_REGIME = "auto_compiled"
QUERY_BUDGETS = (50, 200)
MAX_QUERY_INDEX = 200
TASK_COUNT = 20
FROZEN_AT = "2026-08-02T01:55:20+08:00"
MODEL_SPECS = {
    "deepseek_flash": {
        "provider_id": "deepseek",
        "model_id": "deepseek-v4-flash",
        "model_role": "second",
        "candidate": PROTOCOL_ROOT
        / "adaptive_formal_deepseek_flash_plan_candidate_v1.json",
    },
    "gemini_flash": {
        "provider_id": "gemini",
        "model_id": "gemini-3.6-flash",
        "model_role": "gemini_replication",
        "candidate": PROTOCOL_ROOT
        / "adaptive_formal_gemini_flash_plan_candidate_v1.json",
    },
}


class AdaptiveFormalSecondPlanV1Error(ValueError):
    """Raised when a second-model adaptive plan drifts."""


def _spec(model_key: str) -> dict[str, Any]:
    try:
        return copy.deepcopy(MODEL_SPECS[model_key])
    except KeyError as exc:
        raise AdaptiveFormalSecondPlanV1Error("unknown adaptive model key") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveFormalSecondPlanV1Error(f"{path}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise AdaptiveFormalSecondPlanV1Error(f"{path}: expected object")
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
        raise AdaptiveFormalSecondPlanV1Error(f"missing frozen input: {path}")
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
        raise AdaptiveFormalSecondPlanV1Error("lock escapes project") from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise AdaptiveFormalSecondPlanV1Error(f"artifact lock drift: {path}")


def load_extension() -> dict[str, Any]:
    value = _read_json(EXTENSION_PATH)
    if (
        value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("maximum_query_budget") != 79_000
    ):
        raise AdaptiveFormalSecondPlanV1Error("adaptive extension drift")
    base = value.get("base_freeze")
    if not isinstance(base, Mapping):
        raise AdaptiveFormalSecondPlanV1Error("adaptive base freeze lock missing")
    _verify_lock(base)
    return value


def adaptive_query_work_key(
    model_key: str, case_id: str, query_index: int
) -> str:
    spec = _spec(model_key)
    if (
        not isinstance(case_id, str)
        or not case_id
        or isinstance(query_index, bool)
        or not isinstance(query_index, int)
        or not 1 <= query_index <= MAX_QUERY_INDEX
    ):
        raise AdaptiveFormalSecondPlanV1Error("adaptive query identity invalid")
    provider = spec["provider_id"]
    model = str(spec["model_id"]).replace("-", "_")
    return f"adaptive-formal-{provider}-{model}__{case_id}__q{query_index:05d}"


def all_query_work_keys(
    model_key: str, tasks: list[Mapping[str, Any]]
) -> tuple[str, ...]:
    return tuple(
        adaptive_query_work_key(model_key, str(task["case_id"]), index)
        for task in tasks
        for index in range(1, MAX_QUERY_INDEX + 1)
    )


def _compact_tasks(
    extension: Mapping[str, Any], model_key: str
) -> list[dict[str, Any]]:
    raw = extension.get("models", {}).get(model_key, {}).get("tasks")
    if not isinstance(raw, list) or len(raw) != TASK_COUNT:
        raise AdaptiveFormalSecondPlanV1Error("adaptive task panel drift")
    compact: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_task in raw:
        task = copy.deepcopy(dict(raw_task))
        case_id = str(task["case_id"])
        if case_id in seen:
            raise AdaptiveFormalSecondPlanV1Error("duplicate adaptive case")
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
    return compact


def build_candidate(model_key: str) -> dict[str, Any]:
    spec = _spec(model_key)
    extension = load_extension()
    extension_model = extension["models"][model_key]
    if (
        extension_model.get("provider_id") != spec["provider_id"]
        or extension_model.get("model_id") != spec["model_id"]
        or extension_model.get("budgets") != list(QUERY_BUDGETS)
    ):
        raise AdaptiveFormalSecondPlanV1Error("adaptive model specification drift")
    tasks = _compact_tasks(extension, model_key)
    keys = all_query_work_keys(model_key, tasks)
    identity = sha256_canonical_json(
        {
            "schema_version": "m3-paper-v2-adaptive-second-identity-1.0",
            "extension_manifest_sha256": extension["manifest_sha256"],
            "model_key": model_key,
            "provider_id": spec["provider_id"],
            "model_id": spec["model_id"],
            "tasks": tasks,
            "query_budgets": list(QUERY_BUDGETS),
        }
    )
    scope = {
        "model_key": model_key,
        "provider_id": spec["provider_id"],
        "model_id": spec["model_id"],
        "model_role": spec["model_role"],
        "condition_id": CONDITION_ID,
        "authorization_regime": AUTHORIZATION_REGIME,
        "run_id": f"paper-v2-adaptive-{model_key}-plan-v1",
        "execution_identity": identity,
        "task_count": TASK_COUNT,
        "tasks": tasks,
        "query_budget_nodes": list(QUERY_BUDGETS),
        "maximum_query_index_per_task": MAX_QUERY_INDEX,
        "known_work_key_count": len(keys),
        "known_work_key_sequence_sha256": sha256_canonical_json(keys),
        "maximum_query_budget": TASK_COUNT * MAX_QUERY_INDEX,
        "maximum_provider_calls": (
            TASK_COUNT
            * MAX_QUERY_INDEX
            * CONDITION_PROFILES[CONDITION_ID].max_provider_calls
        ),
        "output_namespace": (
            "outputs/paper_upgrade_v2/adaptive_formal_second/" + model_key
        ),
    }
    core = {
        "schema_version": "m3-paper-v2-adaptive-formal-second-plan-1.0",
        "artifact_role": "non_executable_provider_isolated_adaptive_plan",
        "frozen_at": FROZEN_AT,
        "status": "offline_qualified_execution_not_authorized",
        "execution_identity": identity,
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [_lock(Path(__file__)), _lock(EXTENSION_PATH)],
        "authorization": {
            "candidate_only": True,
            "stage_execution_authorized": False,
            "result_admission_authorized": False,
        },
        "safety_boundary": {
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "trusted_fields_mutable": False,
            "payload_class": "synthetic_m3_case",
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_read": 0,
            "shared_mutable_provider_state": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_candidate(value: Any, *, model_key: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveFormalSecondPlanV1Error("adaptive candidate must be object")
    spec = _spec(model_key)
    scope = value.get("scope")
    if (
        value.get("schema_version")
        != "m3-paper-v2-adaptive-formal-second-plan-1.0"
        or value.get("manifest_sha256") != _manifest_sha(value)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or value.get("execution_identity") != scope.get("execution_identity")
        or scope.get("model_key") != model_key
        or scope.get("provider_id") != spec["provider_id"]
        or scope.get("model_id") != spec["model_id"]
        or scope.get("task_count") != TASK_COUNT
        or scope.get("query_budget_nodes") != list(QUERY_BUDGETS)
        or scope.get("known_work_key_count") != TASK_COUNT * MAX_QUERY_INDEX
        or value.get("authorization", {}).get("stage_execution_authorized")
        is not False
        or value.get("safety_boundary", {}).get("automatic_retries") != 0
    ):
        raise AdaptiveFormalSecondPlanV1Error("adaptive candidate drift")
    for lock in value.get("artifact_locks", []):
        _verify_lock(lock)
    return copy.deepcopy(dict(value))


def candidate_path(model_key: str) -> Path:
    return Path(_spec(model_key)["candidate"])


def write_candidate(model_key: str) -> dict[str, Any]:
    value = build_candidate(model_key)
    _write_json(candidate_path(model_key), value)
    return value


def verify_candidate(model_key: str) -> dict[str, Any]:
    observed = validate_candidate(
        _read_json(candidate_path(model_key)), model_key=model_key
    )
    expected = build_candidate(model_key)
    if observed != expected:
        raise AdaptiveFormalSecondPlanV1Error("adaptive candidate artifact drift")
    return observed


def resolve_candidate_task(
    candidate: Mapping[str, Any], case_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    matches = [
        dict(task)
        for task in candidate.get("scope", {}).get("tasks", [])
        if isinstance(task, Mapping) and task.get("case_id") == case_id
    ]
    if len(matches) != 1:
        raise AdaptiveFormalSecondPlanV1Error("unknown adaptive task")
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
        raise AdaptiveFormalSecondPlanV1Error("mutated payload required")
    model_key = str(candidate.get("scope", {}).get("model_key", ""))
    task, source = resolve_candidate_task(candidate, case_id)
    if hashlib.sha256(str(source["untrusted_content"]).encode()).hexdigest() != task[
        "base_payload_sha256"
    ]:
        raise AdaptiveFormalSecondPlanV1Error("adaptive base payload drift")
    record = copy.deepcopy(source)
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
        raise AdaptiveFormalSecondPlanV1Error("trusted adaptive fields changed")
    work_item = {
        "schema_version": "m3-paper-v2-adaptive-query-work-item-2.0",
        "execution_identity": candidate["execution_identity"],
        "work_key": adaptive_query_work_key(model_key, case_id, query_index),
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
    state = build_initial_online_state(work_item, {"benchmark": "m3-v2"}, record)
    digest = compute_online_visible_field_digest(state)
    if digest["forbidden_fields_present"]:
        raise AdaptiveFormalSecondPlanV1Error("adaptive state exposes evaluator fields")
    work_item["initial_online_visible_field_digest"] = digest
    return work_item, state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    parser.add_argument("--model-key", choices=tuple(MODEL_SPECS), required=True)
    args = parser.parse_args()
    value = (
        write_candidate(args.model_key)
        if args.write_candidate
        else verify_candidate(args.model_key)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MODEL_SPECS",
    "AdaptiveFormalSecondPlanV1Error",
    "adaptive_query_work_key",
    "all_query_work_keys",
    "build_candidate",
    "build_query_work_item_and_state",
    "candidate_path",
    "resolve_candidate_task",
    "validate_candidate",
    "verify_candidate",
    "write_candidate",
]
