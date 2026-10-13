"""自适应 V2 成本金丝雀实验的仅追加（Append-Only）恢复执行器。

保证在断点恢复过程中历史记录不可变，所有新实验探索仅能追加写入新账本。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import experiments.paper_v2.adaptive_cost_canary_controller_v1 as canary_v1
import experiments.paper_v2.adaptive_cost_canary_controller_v2 as canary_v2
import experiments.paper_v2.adaptive_cost_canary_plan_v1 as plan_v1
from experiments.paper_v1 import adaptive_attack
from experiments.paper_v2.adaptive_query_ledger_v1 import (
    cross_bind_query_and_call_ledgers,
    validate_query_events,
)
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)
from experiments.paper_v2.incremental_live_ledgers_v1 import (
    IncrementalAdaptiveQueryLedger,
    IncrementalPublicBudgetTracker,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderPausedError,
)
from experiments.paper_v2.public_execution_store_v1 import (
    validate_public_budget_events,
)
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
V2_ADMISSION = (
    PROTOCOL_ROOT / "admissions/adaptive_cost_canary_admission_v2.json"
)
RECOVERY_REVIEW = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary"
    / "adaptive_v2_recovery_review_v3.json"
)
CANDIDATE_PATH = (
    PROTOCOL_ROOT / "adaptive_cost_canary_recovery_candidate_v3.json"
)
ADMISSION_PATH = (
    PROTOCOL_ROOT / "admissions/adaptive_cost_canary_admission_v3.json"
)
TASK_EVENT_NAME = "continuation_task_events_v3.jsonl"
TECHNICAL_REVIEW_NAME = "technical_cost_review_v3.json"
SCHEMA_VERSION = "m3-paper-v2-adaptive-recovery-candidate-3.0"
ADMISSION_SCHEMA_VERSION = "m3-paper-v2-adaptive-recovery-admission-3.0"
TASK_EVENT_SCHEMA_VERSION = "m3-paper-v2-adaptive-task-event-3.0"
RECOVERY_REVIEW_VERSION = "m3-paper-v2-adaptive-recovery-review-3.0"
GENERATED_AT = "2026-07-30T02:45:00+08:00"
REVIEWED_AT = "2026-07-30T02:44:00+08:00"
HARD_LIMIT_CNY = 5.0
MAX_DIAGNOSTIC_FRACTION = 0.01


class AdaptiveCostCanaryRecoveryV3Error(ValueError):
    """当自适应恢复无法执行安全闭合（fail-closed）时抛出的异常。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveCostCanaryRecoveryV3Error(
            f"{path}: invalid JSON object"
        ) from exc
    if not isinstance(value, dict):
        raise AdaptiveCostCanaryRecoveryV3Error(
            f"{path}: expected an object"
        )
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                raise AdaptiveCostCanaryRecoveryV3Error(
                    f"{path}:{number}: blank row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AdaptiveCostCanaryRecoveryV3Error(
                    f"{path}:{number}: expected an object"
                )
            rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveCostCanaryRecoveryV3Error(
            f"{path}: invalid JSONL"
        ) from exc
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")
        stream.flush()
        os.fsync(stream.fileno())


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
                raise AdaptiveCostCanaryRecoveryV3Error(
                    f"{path}: frozen prefix was truncated"
                )
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AdaptiveCostCanaryRecoveryV3Error(
            f"missing adaptive recovery artifact: {path}"
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
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive recovery lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise AdaptiveCostCanaryRecoveryV3Error(
            f"adaptive recovery exact lock drift: {lock['path']}"
        )


def _verify_prefix_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock["path"])).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive recovery prefix lock escapes project"
        ) from exc
    length = int(lock["bytes"])
    if (
        not path.is_file()
        or path.stat().st_size < length
        or _sha256_prefix(path, length) != lock["sha256"]
    ):
        raise AdaptiveCostCanaryRecoveryV3Error(
            f"adaptive recovery prefix lock drift: {lock['path']}"
        )


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
    )


def _terminal_events_by_case(
    query_events: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = {}
    for event in query_events:
        if event.get("event_type") == "terminal":
            result.setdefault(str(event["case_id"]), []).append(event)
    for events in result.values():
        events.sort(key=lambda event: int(event["query_index"]))
    return result


def _checkpoint_bindings(
    *,
    checkpoint: Mapping[str, Any],
    terminal_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    queries = checkpoint.get("queries")
    nodes = checkpoint.get("nodes")
    if not isinstance(queries, list) or not isinstance(nodes, Mapping):
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive checkpoint structure is invalid"
        )
    if (
        len(queries) != len(terminal_events)
        or [int(event["query_index"]) for event in terminal_events]
        != list(range(1, len(queries) + 1))
    ):
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive checkpoint/query cardinality drift"
        )
    for query, event in zip(queries, terminal_events, strict=True):
        if not isinstance(query, Mapping):
            raise AdaptiveCostCanaryRecoveryV3Error(
                "adaptive checkpoint query is invalid"
            )
        node = nodes.get(str(query.get("node_id", "")))
        if not isinstance(node, Mapping):
            raise AdaptiveCostCanaryRecoveryV3Error(
                "adaptive checkpoint query lacks its search node"
            )
        prompt = node.get("prompt")
        metadata = query.get("metadata")
        if not isinstance(prompt, str) or not isinstance(metadata, Mapping):
            raise AdaptiveCostCanaryRecoveryV3Error(
                "adaptive checkpoint binding fields are missing"
            )
        direct_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        canonical_sha = adaptive_attack._sha256(prompt)
        if (
            event["prompt_sha256"] != direct_sha
            or query.get("prompt_sha256") != canonical_sha
            or metadata.get("record_sha256") != event["record_sha256"]
            or metadata.get("provider_call_count")
            != event["provider_call_count"]
        ):
            raise AdaptiveCostCanaryRecoveryV3Error(
                "adaptive checkpoint dual-hash/query binding drift"
            )
    return {
        "query_count": len(queries),
        "direct_utf8_prompt_hashes_verified": len(queries),
        "canonical_json_prompt_hashes_verified": len(queries),
        "record_bindings_verified": len(queries),
    }


def _v2_state() -> tuple[
    canary_v1.AdaptiveExecutionPermit,
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
]:
    permit = canary_v2.authorize_canary(admission_path=V2_ADMISSION)
    role_policy = canary_v1.adaptive_role_policy()
    query_events = _load_jsonl(permit.query_ledger_path)
    budget_events = _load_jsonl(permit.budget_ledger_path)
    query_status = validate_query_events(
        query_events,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    budget_status = validate_public_budget_events(
        budget_events,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    cross_bind_query_and_call_ledgers(
        query_events=query_events,
        budget_events=budget_events,
        trace_root=permit.trace_root,
        role_policy=role_policy,
    )
    return (
        permit,
        role_policy,
        query_events,
        budget_events,
        query_status,
        budget_status,
    )


def build_recovery_review() -> dict[str, Any]:
    (
        permit,
        _,
        query_events,
        _,
        query_status,
        budget_status,
    ) = _v2_state()
    if query_status["open_query_work_keys"]:
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive-v2 has an open query; continuation is forbidden"
        )
    by_case = _terminal_events_by_case(query_events)
    bindings: dict[str, Any] = {}
    diagnostic_cases: list[str] = []
    terminal_cases: list[str] = []
    for task in permit.tasks:
        case_id = str(task["case_id"])
        events = by_case.get(case_id, [])
        checkpoint_path = permit.checkpoint_root / f"{case_id}.json"
        if not events:
            if checkpoint_path.exists():
                raise AdaptiveCostCanaryRecoveryV3Error(
                    "untouched adaptive task already has a checkpoint"
                )
            continue
        if not checkpoint_path.is_file():
            raise AdaptiveCostCanaryRecoveryV3Error(
                "adaptive terminal prefix lacks a checkpoint"
            )
        bindings[case_id] = _checkpoint_bindings(
            checkpoint=_load_json(checkpoint_path),
            terminal_events=events,
        )
        has_diagnostic = any(
            event["result_tier"] == "diagnostic" for event in events
        )
        if has_diagnostic:
            diagnostic_cases.append(case_id)
        if len(events) == plan_v1.QUERY_BUDGET or has_diagnostic:
            terminal_cases.append(case_id)
        else:
            raise AdaptiveCostCanaryRecoveryV3Error(
                "adaptive-v2 prefix ends in a nonterminal task"
            )
    all_cases = [str(task["case_id"]) for task in permit.tasks]
    pending_cases = [
        case_id for case_id in all_cases if case_id not in terminal_cases
    ]
    core = {
        "schema_version": RECOVERY_REVIEW_VERSION,
        "artifact_role": "outcome_blind_closed_prefix_recovery_review",
        "reviewed_at": REVIEWED_AT,
        "status": "closed_prefix_eligible_for_separate_continuation",
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "source_v2_candidate_manifest_sha256": permit.candidate[
            "manifest_sha256"
        ],
        "source_v2_admission_file_sha256": permit.admission_file_sha256,
        "terminal_query_count": query_status["terminal_query_count"],
        "completed_provider_call_count": query_status[
            "completed_provider_call_count"
        ],
        "diagnostic_query_count": query_status["diagnostic_query_count"],
        "role_cumulative_cost_cny": budget_status[
            "role_cumulative_cost_cny"
        ],
        "terminal_case_ids": terminal_cases,
        "diagnostic_terminal_case_ids": diagnostic_cases,
        "untouched_case_ids": pending_cases,
        "checkpoint_bindings": bindings,
        "query_ledger_tail_sha256": query_status["tail_sha256"],
        "budget_ledger_tail_sha256": budget_status["tail_sha256"],
        "checks": {
            "all_query_attempts_terminal": True,
            "query_call_cross_binding_complete": True,
            "dual_prompt_hash_semantics_verified": True,
            "diagnostic_queries_retained_in_itt": True,
            "terminal_diagnostic_retry_authorized": False,
            "only_untouched_tasks_continuable": True,
            "scientific_outcomes_aggregated": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_recovery_review(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive recovery review must be an object"
        )
    if (
        value.get("schema_version") != RECOVERY_REVIEW_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or dict(value) != build_recovery_review()
    ):
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive recovery review drift"
        )
    return copy.deepcopy(dict(value))


def write_recovery_review() -> dict[str, Any]:
    value = build_recovery_review()
    _write_json(RECOVERY_REVIEW, value)
    return value


def _prefix_locks(
    permit: canary_v1.AdaptiveExecutionPermit,
) -> list[dict[str, Any]]:
    paths = [permit.query_ledger_path, permit.budget_ledger_path]
    paths.extend(sorted(permit.checkpoint_root.glob("*.json")))
    paths.extend(sorted(permit.trace_root.glob("*.jsonl")))
    return [_lock(path) for path in paths]


def build_candidate() -> dict[str, Any]:
    review = validate_recovery_review(_load_json(RECOVERY_REVIEW))
    permit = canary_v2.authorize_canary(admission_path=V2_ADMISSION)
    if (permit.output_root / TASK_EVENT_NAME).exists():
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive-v3 task ledger already exists"
        )
    artifact_paths = [
        Path(__file__),
        PROJECT_ROOT
        / "experiments/paper_v2/incremental_live_ledgers_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/adaptive_cost_canary_controller_v2.py",
        PROJECT_ROOT / "experiments/paper_v2/adaptive_runner.py",
        PROJECT_ROOT / "experiments/paper_v1/adaptive_attack.py",
        RECOVERY_REVIEW,
        canary_v2.CANDIDATE_PATH,
        V2_ADMISSION,
    ]
    scope = {
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "model_role": "primary",
        "provider_id": "deepseek",
        "endpoint_type": "official_api",
        "model_id": plan_v1.MODEL_ID,
        "output_root": _display_path(permit.output_root),
        "query_budget_per_task": plan_v1.QUERY_BUDGET,
        "maximum_queries": plan_v1.MAX_QUERIES,
        "hard_limit_cny": HARD_LIMIT_CNY,
        "source_v2_candidate_manifest_sha256": permit.candidate[
            "manifest_sha256"
        ],
        "source_v2_admission_file_sha256": permit.admission_file_sha256,
        "source_recovery_review_manifest_sha256": review["manifest_sha256"],
        "terminal_case_ids": review["terminal_case_ids"],
        "diagnostic_terminal_case_ids": review[
            "diagnostic_terminal_case_ids"
        ],
        "authorized_continuation_case_ids": review["untouched_case_ids"],
        "diagnostic_policy": {
            "retain_in_itt": True,
            "retry_terminal_diagnostic": False,
            "continue_with_untouched_tasks": True,
            "technical_admission_max_fraction": (
                MAX_DIAGNOSTIC_FRACTION
            ),
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "append_only_adaptive_recovery_candidate",
        "generated_at": GENERATED_AT,
        "status": "offline_qualified_execution_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [_lock(path) for path in artifact_paths],
        "prefix_locks": _prefix_locks(permit),
        "authorization": {
            "candidate_only": True,
            "continuation_execution_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "provider_calls_while_building": 0,
            "scientific_outcomes_aggregated": False,
            "existing_terminal_queries_retried": 0,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive-v3 candidate must be an object"
        )
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("scope_sha256")
        != sha256_canonical_json(value.get("scope"))
        or value.get("scope", {}).get("model_id") != plan_v1.MODEL_ID
        or value.get("scope", {}).get("hard_limit_cny")
        != HARD_LIMIT_CNY
        or value.get("authorization", {}).get(
            "continuation_execution_authorized"
        )
        is not False
    ):
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive-v3 candidate identity/scope drift"
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


def canonical_command() -> str:
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.adaptive_cost_canary_recovery_v3 "
        "--execute-continuation --admission "
        "protocols\\paper_upgrade_v2\\admissions\\"
        "adaptive_cost_canary_admission_v3.json "
        "--config config\\project.local.env"
    )


def build_admission(
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
        raise AdaptiveCostCanaryRecoveryV3Error(
            "owner statement must be lowercase SHA-256"
        )
    command = canonical_command()
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "adaptive_recovery_execution_admission",
        "approved_at": approved_at,
        "status": "activated_for_untouched_adaptive_tasks_only",
        "authorization": {
            "owner_statement_sha256": owner_statement_sha256,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "exact_command": command,
            "exact_command_sha256": hashlib.sha256(
                command.encode("utf-8")
            ).hexdigest(),
            "authorized_case_ids": candidate["scope"][
                "authorized_continuation_case_ids"
            ],
            "terminal_diagnostic_retry_authorized": False,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "scientific_result_admission_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_admission(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive-v3 admission must be an object"
        )
    if value.get("manifest_sha256") != _manifest_sha(value):
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive-v3 admission manifest drift"
        )
    expected = build_admission(
        owner_statement_sha256=str(
            value.get("authorization", {}).get(
                "owner_statement_sha256",
                "",
            )
        ),
        approved_at=str(value.get("approved_at", "")),
    )
    if dict(value) != expected:
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive-v3 admission scope drift"
        )
    return copy.deepcopy(dict(value))


def write_admission(
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    value = build_admission(
        owner_statement_sha256=owner_statement_sha256,
        approved_at=approved_at,
    )
    _write_json(ADMISSION_PATH, value)
    return value


def _validate_task_events(
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    execution_identity: str,
    authorized_cases: set[str],
) -> dict[str, Any]:
    previous: str | None = None
    terminal: set[str] = set()
    for sequence, event in enumerate(events, start=1):
        core = {
            key: child
            for key, child in event.items()
            if key != "event_sha256"
        }
        case_id = str(event.get("case_id", ""))
        if (
            event.get("schema_version") != TASK_EVENT_SCHEMA_VERSION
            or event.get("ledger_sequence") != sequence
            or event.get("previous_event_sha256") != previous
            or event.get("run_id") != run_id
            or event.get("execution_identity") != execution_identity
            or case_id not in authorized_cases
            or case_id in terminal
            or event.get("terminal_class")
            not in {"search_terminal", "diagnostic_terminal"}
            or not isinstance(event.get("query_count"), int)
            or int(event["query_count"]) < 1
            or event.get("event_sha256") != sha256_canonical_json(core)
        ):
            raise AdaptiveCostCanaryRecoveryV3Error(
                f"adaptive-v3 task event {sequence} drift"
            )
        checkpoint = PROJECT_ROOT / str(event["checkpoint_path"])
        if (
            not checkpoint.is_file()
            or _sha256_file(checkpoint) != event["checkpoint_sha256"]
        ):
            raise AdaptiveCostCanaryRecoveryV3Error(
                "adaptive-v3 task checkpoint drift"
            )
        previous = str(event["event_sha256"])
        terminal.add(case_id)
    return {
        "event_count": len(events),
        "terminal_case_ids": sorted(terminal),
        "tail_sha256": previous,
    }


def _append_task_event(
    path: Path,
    *,
    permit: canary_v1.AdaptiveExecutionPermit,
    case_id: str,
    query_count: int,
    terminal_class: str,
) -> dict[str, Any]:
    authorized = set(
        verify_candidate()["scope"]["authorized_continuation_case_ids"]
    )
    events = _load_jsonl(path)
    status = _validate_task_events(
        events,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        authorized_cases=authorized,
    )
    if case_id in status["terminal_case_ids"]:
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive-v3 task is already terminal"
        )
    checkpoint = permit.checkpoint_root / f"{case_id}.json"
    core = {
        "schema_version": TASK_EVENT_SCHEMA_VERSION,
        "ledger_sequence": len(events) + 1,
        "previous_event_sha256": status["tail_sha256"],
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "case_id": case_id,
        "query_count": query_count,
        "terminal_class": terminal_class,
        "checkpoint_path": _display_path(checkpoint),
        "checkpoint_sha256": _sha256_file(checkpoint),
        "recorded_at": _now(),
    }
    event = {**core, "event_sha256": sha256_canonical_json(core)}
    _append_jsonl(path, event)
    return event


def authorize(
    *,
    admission_path: Path,
) -> tuple[
    canary_v1.AdaptiveExecutionPermit,
    dict[str, Any],
    dict[str, Any],
]:
    if admission_path.resolve() != ADMISSION_PATH.resolve():
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive-v3 admission path is not frozen"
        )
    admission = validate_admission(_load_json(admission_path))
    candidate = verify_candidate()
    source = canary_v2.authorize_canary(admission_path=V2_ADMISSION)
    permit = replace(
        source,
        admission_file_sha256=_sha256_file(admission_path),
        admission=admission,
    )
    if (
        permit.run_id != candidate["scope"]["run_id"]
        or permit.execution_identity
        != candidate["scope"]["execution_identity"]
    ):
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive-v3 permit identity drift"
        )
    return permit, candidate, admission


def execute_continuation(
    *,
    admission_path: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    executor_factory: Callable[..., Any] = canary_v1._build_executor,
) -> dict[str, Any]:
    permit, candidate, _ = authorize(admission_path=admission_path)
    role_policy = canary_v1.adaptive_role_policy()
    task_path = permit.output_root / TASK_EVENT_NAME
    existing_task_events = _load_jsonl(task_path)
    if existing_task_events:
        raise AdaptiveCostCanaryRecoveryV3Error(
            "adaptive-v3 already started; automatic rerun is forbidden"
        )
    values = (
        credential_loader()
        if credential_loader is not None
        else parse_env_file(resolve_config_path(config_path))
    )
    api_key = canary_v1._validate_runtime_config(
        values,
        role_policy=role_policy,
    )
    tracker = IncrementalPublicBudgetTracker(
        permit.budget_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    query_ledger = IncrementalAdaptiveQueryLedger(
        permit.query_ledger_path,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    executor = executor_factory(
        permit,
        tracker,
        api_key=api_key,
        role_policy=role_policy,
    )
    authorized_cases = set(
        candidate["scope"]["authorized_continuation_case_ids"]
    )
    completed = 0
    diagnostic_tasks = 0
    stop_reason: str | None = None
    for task in permit.tasks:
        case_id = str(task["case_id"])
        if case_id not in authorized_cases:
            continue
        checkpoint = permit.checkpoint_root / f"{case_id}.json"
        if checkpoint.exists():
            raise AdaptiveCostCanaryRecoveryV3Error(
                "untouched adaptive-v3 task already has a checkpoint"
            )
        _, source_record = plan_v1.resolve_candidate_task(
            permit.candidate,
            case_id,
        )
        oracle = canary_v2._AdaptiveOfficialOracleV2(
            permit=permit,
            case_id=case_id,
            executor=executor,
            query_ledger=query_ledger,
            tracker=tracker,
            role_policy=role_policy,
        )
        terminal_class = "search_terminal"
        try:
            summary = canary_v1.run_task_budget(
                task_id=case_id,
                base_payload=str(source_record["untrusted_content"]),
                oracle=oracle,
                budget=plan_v1.QUERY_BUDGET,
                checkpoint_path=checkpoint,
                seed=canary_v1.ADAPTIVE_SEED,
            )
            if summary["budget_completed"] is not True:
                raise AdaptiveCostCanaryRecoveryV3Error(
                    "adaptive-v3 task did not reach a terminal search state"
                )
        except canary_v1.AdaptiveCanaryStop:
            if oracle.stop_reason != "diagnostic_query":
                raise
            terminal_class = "diagnostic_terminal"
            diagnostic_tasks += 1
        except ProviderPausedError as exc:
            stop_reason = str(exc)
            break
        checkpoint_value = _load_json(checkpoint)
        queries = checkpoint_value.get("queries")
        if not isinstance(queries, list) or not queries:
            raise AdaptiveCostCanaryRecoveryV3Error(
                "adaptive-v3 terminal task lacks checkpoint queries"
            )
        _append_task_event(
            task_path,
            permit=permit,
            case_id=case_id,
            query_count=len(queries),
            terminal_class=terminal_class,
        )
        completed += 1
    query_status = query_ledger.full_validate()
    budget_status = tracker.full_validate()
    cross_bind_query_and_call_ledgers(
        query_events=query_ledger.events,
        budget_events=tracker.events,
        trace_root=permit.trace_root,
        role_policy=role_policy,
    )
    task_status = _validate_task_events(
        _load_jsonl(task_path),
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        authorized_cases=authorized_cases,
    )
    return {
        "status": (
            "adaptive_recovery_candidate_complete_unadmitted"
            if completed == len(authorized_cases) and stop_reason is None
            else "adaptive_recovery_paused"
        ),
        "run_id": permit.run_id,
        "model_id": plan_v1.MODEL_ID,
        "continued_task_count": completed,
        "expected_continuation_task_count": len(authorized_cases),
        "diagnostic_tasks_this_process": diagnostic_tasks,
        "total_terminal_query_count": query_status[
            "terminal_query_count"
        ],
        "total_completed_provider_call_count": query_status[
            "completed_provider_call_count"
        ],
        "cumulative_cost_cny": budget_status[
            "role_cumulative_cost_cny"
        ],
        "task_event_count": task_status["event_count"],
        "stop_reason": stop_reason,
        "result_admission_authorized": False,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "v2_terminal_queries_retried": 0,
    }


def build_technical_review(
    *,
    admission_path: Path,
) -> dict[str, Any]:
    permit, candidate, _ = authorize(admission_path=admission_path)
    role_policy = canary_v1.adaptive_role_policy()
    query_events = _load_jsonl(permit.query_ledger_path)
    budget_events = _load_jsonl(permit.budget_ledger_path)
    query_status = validate_query_events(
        query_events,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    budget_status = validate_public_budget_events(
        budget_events,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        model_role="primary",
        known_work_keys=set(permit.known_work_keys),
        role_policy=role_policy,
    )
    cross_bind_query_and_call_ledgers(
        query_events=query_events,
        budget_events=budget_events,
        trace_root=permit.trace_root,
        role_policy=role_policy,
    )
    by_case = _terminal_events_by_case(query_events)
    checkpoint_counts: dict[str, int] = {}
    for task in permit.tasks:
        case_id = str(task["case_id"])
        events = by_case.get(case_id, [])
        checkpoint = permit.checkpoint_root / f"{case_id}.json"
        if not events or not checkpoint.is_file():
            continue
        binding = _checkpoint_bindings(
            checkpoint=_load_json(checkpoint),
            terminal_events=events,
        )
        checkpoint_counts[case_id] = int(binding["query_count"])
    authorized_cases = set(
        candidate["scope"]["authorized_continuation_case_ids"]
    )
    task_events = _load_jsonl(permit.output_root / TASK_EVENT_NAME)
    task_status = _validate_task_events(
        task_events,
        run_id=permit.run_id,
        execution_identity=permit.execution_identity,
        authorized_cases=authorized_cases,
    )
    for event in task_events:
        if checkpoint_counts.get(str(event["case_id"])) != event[
            "query_count"
        ]:
            raise AdaptiveCostCanaryRecoveryV3Error(
                "adaptive-v3 task/query count drift"
            )
    prefix_terminal = set(candidate["scope"]["terminal_case_ids"])
    all_terminal = prefix_terminal | set(task_status["terminal_case_ids"])
    expected_cases = {str(task["case_id"]) for task in permit.tasks}
    diagnostic_count = int(query_status["diagnostic_query_count"])
    max_diagnostics = max(
        1,
        math.floor(
            int(query_status["terminal_query_count"])
            * MAX_DIAGNOSTIC_FRACTION
        ),
    )
    checks = {
        "all_queries_terminal": not query_status[
            "open_query_work_keys"
        ],
        "all_eight_tasks_terminal": all_terminal == expected_cases,
        "all_checkpoint_dual_hash_bindings_verified": (
            set(checkpoint_counts) == expected_cases
        ),
        "query_call_cross_binding_complete": True,
        "budget_event_count_matches_provider_calls": (
            budget_status["event_count"]
            == query_status["completed_provider_call_count"]
        ),
        "budget_not_paused": budget_status["paused"] is False,
        "hard_cost_limit_respected": (
            float(budget_status["role_cumulative_cost_cny"])
            <= HARD_LIMIT_CNY
        ),
        "diagnostic_fraction_within_frozen_bound": (
            diagnostic_count <= max_diagnostics
        ),
        "v2_terminal_queries_retried": False,
        "scientific_outcomes_aggregated": False,
    }
    passed = all(checks.values())
    core = {
        "schema_version": "m3-paper-v2-adaptive-technical-review-3.0",
        "artifact_role": "outcome_blind_adaptive_recovery_review",
        "reviewed_at": _now(),
        "status": (
            "adaptive_recovery_technical_gate_pass"
            if passed
            else "adaptive_recovery_technical_gate_fail"
        ),
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "admission_file_sha256": _sha256_file(admission_path),
        "terminal_query_count": query_status["terminal_query_count"],
        "completed_provider_call_count": query_status[
            "completed_provider_call_count"
        ],
        "diagnostic_query_count": diagnostic_count,
        "maximum_admissible_diagnostic_queries": max_diagnostics,
        "terminal_task_count": len(all_terminal),
        "expected_task_count": len(expected_cases),
        "cumulative_cost_cny": budget_status[
            "role_cumulative_cost_cny"
        ],
        "hard_limit_cny": HARD_LIMIT_CNY,
        "query_ledger_tail_sha256": query_status["tail_sha256"],
        "budget_ledger_tail_sha256": budget_status["tail_sha256"],
        "task_ledger_tail_sha256": task_status["tail_sha256"],
        "checks": checks,
        "technical_gate_passed": passed,
        "scientific_result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_technical_review(
    *,
    admission_path: Path,
) -> dict[str, Any]:
    permit, _, _ = authorize(admission_path=admission_path)
    value = build_technical_review(admission_path=admission_path)
    _write_json(permit.output_root / TECHNICAL_REVIEW_NAME, value)
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
    action.add_argument("--execute-continuation", action="store_true")
    action.add_argument("--write-technical-review", action="store_true")
    parser.add_argument("--admission", type=Path, default=ADMISSION_PATH)
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
    elif args.write_admission:
        if not args.owner_statement_sha256 or not args.approved_at:
            parser.error(
                "--write-admission requires --owner-statement-sha256 "
                "and --approved-at"
            )
        value = write_admission(
            owner_statement_sha256=args.owner_statement_sha256,
            approved_at=args.approved_at,
        )
    elif args.verify_admission:
        value = validate_admission(_load_json(args.admission))
    elif args.execute_continuation:
        value = execute_continuation(
            admission_path=args.admission,
            config_path=args.config,
        )
    else:
        value = write_technical_review(admission_path=args.admission)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
