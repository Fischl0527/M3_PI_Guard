"""面向公开矩阵的仅追加记录存储器与缓存开销账本。

记录评测执行产物与 Prompt 缓存命中收益，支持透明成本审计。
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.contracts_v2 as contracts_v2
from experiments.paper_v2.contracts import (
    _validate_decision_semantics,
    _validate_digest_semantics,
    _validate_outcome_semantics,
    compute_online_visible_field_digest,
    sha256_canonical_json,
)
from experiments.paper_v2.contracts_v2 import (
    EXPERIMENT_RECORD_SCHEMA_VERSION,
)
from experiments.paper_v2.formal_record_store import (
    _validate_sanitized_events,
    _work_item_map,
    validate_persisted_ledger_value,
)
from experiments.paper_v2.formal_record_store_v2 import (
    ENTRY_FIELDS,
    ENTRY_SCHEMA_VERSION,
    _effective_decision,
    _entry_core,
    _expected_record_id,
)
from experiments.paper_v2.official_provider_executor import (
    OfficialProviderCompletion,
    ProviderPausedError,
)
from experiments.paper_v2.provider_safety import validate_safety_receipt
from experiments.paper_v2.public_matrix_plan_v1 import (
    hydrate_public_work_item,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    PublicBudgetPolicyError,
    check_role_headroom,
    role_cost_cny,
)
from experiments.paper_v2.public_provider_trace_v1 import (
    validate_public_trace_bundle,
)


BUDGET_EVENT_SCHEMA = "m3-paper-v2-public-budget-event-1.0"
USAGE_FIELDS = (
    "prompt_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "completion_tokens",
)


class PublicExecutionStoreError(ValueError):
    """当公开仅追加账本无法重建时抛出的异常。"""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, start=1):
                if not line.strip():
                    raise PublicExecutionStoreError(
                        f"{path}:{number}: blank ledger row"
                    )
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise PublicExecutionStoreError(
                        f"{path}:{number}: expected an object"
                    )
                rows.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicExecutionStoreError(
            f"{path}: invalid UTF-8 JSONL"
        ) from exc
    return rows


def _append_fsynced(path: Path, value: Mapping[str, Any]) -> None:
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


def _normalized_usage(value: Mapping[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for field in USAGE_FIELDS:
        item = value.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise PublicExecutionStoreError(
                f"invalid public usage field: {field}"
            )
        result[field] = item
    if (
        result["prompt_tokens"]
        != result["prompt_cache_hit_tokens"]
        + result["prompt_cache_miss_tokens"]
    ):
        raise PublicExecutionStoreError(
            "public cache usage does not sum to prompt tokens"
        )
    return result


def _zero_usage() -> dict[str, int]:
    return {field: 0 for field in USAGE_FIELDS}


def _add_usage(
    left: Mapping[str, int],
    right: Mapping[str, int],
) -> dict[str, int]:
    return {
        field: int(left[field]) + int(right[field])
        for field in USAGE_FIELDS
    }


def _budget_event_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "event_sha256"}
    )


def validate_public_budget_events(
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    execution_identity: str,
    model_role: str,
    known_work_keys: set[str],
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    usage = _zero_usage()
    previous: str | None = None
    response_ids: set[str] = set()
    paused = False
    for sequence, event in enumerate(events, start=1):
        event_usage = _normalized_usage(event.get("usage", {}))
        response_id = event.get("provider_response_id")
        work_key = event.get("work_key")
        cumulative = _add_usage(usage, event_usage)
        expected_request_cost = role_cost_cny(role_policy, event_usage)
        expected_cost = role_cost_cny(role_policy, cumulative)
        status = "continue"
        try:
            check_role_headroom(role_policy, cumulative)
        except PublicBudgetPolicyError:
            status = "pause_before_next_request"
            paused = True
        if (
            event.get("schema_version") != BUDGET_EVENT_SCHEMA
            or event.get("ledger_sequence") != sequence
            or event.get("previous_event_sha256") != previous
            or event.get("run_id") != run_id
            or event.get("execution_identity") != execution_identity
            or event.get("model_role") != model_role
            or work_key not in known_work_keys
            or not isinstance(response_id, str)
            or not response_id
            or response_id in response_ids
            or event.get("request_cost_cny") != expected_request_cost
            or event.get("role_cumulative_usage") != cumulative
            or event.get("role_cumulative_cost_cny") != expected_cost
            or event.get("budget_status_after_request") != status
            or event.get("event_sha256") != _budget_event_sha(event)
        ):
            raise PublicExecutionStoreError(
                f"public budget event {sequence} drift"
            )
        validate_persisted_ledger_value(event)
        usage = cumulative
        previous = str(event["event_sha256"])
        response_ids.add(response_id)
    return {
        "event_count": len(events),
        "role_cumulative_usage": usage,
        "role_cumulative_cost_cny": role_cost_cny(role_policy, usage),
        "paused": paused,
        "provider_response_ids": sorted(response_ids),
        "tail_sha256": previous,
    }


class PublicBudgetTracker:
    """每次执行前重建的 fsync 角色级预算状态。"""

    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        execution_identity: str,
        model_role: str,
        known_work_keys: set[str],
        role_policy: Mapping[str, Any],
    ) -> None:
        self.path = path
        self.run_id = run_id
        self.execution_identity = execution_identity
        self.model_role = model_role
        self.known_work_keys = set(known_work_keys)
        self.role_policy = copy.deepcopy(dict(role_policy))
        self.events = _load_jsonl(path)
        self.status = validate_public_budget_events(
            self.events,
            run_id=run_id,
            execution_identity=execution_identity,
            model_role=model_role,
            known_work_keys=self.known_work_keys,
            role_policy=self.role_policy,
        )

    def assert_before_request(self) -> None:
        if self.status["paused"]:
            raise ProviderPausedError(
                "public role budget is paused before the next request"
            )
        try:
            check_role_headroom(
                self.role_policy,
                self.status["role_cumulative_usage"],
            )
        except PublicBudgetPolicyError as exc:
            raise ProviderPausedError(str(exc)) from exc

    def record_completion(
        self,
        *,
        work_key: str,
        call_index: int,
        completion: OfficialProviderCompletion,
        recorded_at: str,
    ) -> dict[str, Any]:
        evidence = completion.receipt.get("evidence")
        if not isinstance(evidence, Mapping):
            raise PublicExecutionStoreError(
                "public completion lacks provider evidence"
            )
        usage_raw = evidence.get("usage")
        if not isinstance(usage_raw, Mapping):
            raise PublicExecutionStoreError(
                "public completion lacks usage"
            )
        usage = _normalized_usage(usage_raw)
        response_id = evidence.get("response_id")
        if not isinstance(response_id, str) or not response_id:
            raise PublicExecutionStoreError(
                "public completion lacks official response identity"
            )
        cumulative = _add_usage(
            self.status["role_cumulative_usage"],
            usage,
        )
        status = "continue"
        try:
            check_role_headroom(self.role_policy, cumulative)
        except PublicBudgetPolicyError:
            status = "pause_before_next_request"
        core = {
            "schema_version": BUDGET_EVENT_SCHEMA,
            "ledger_sequence": len(self.events) + 1,
            "previous_event_sha256": self.status["tail_sha256"],
            "run_id": self.run_id,
            "execution_identity": self.execution_identity,
            "model_role": self.model_role,
            "work_key": work_key,
            "call_index": call_index,
            "provider_response_id": response_id,
            "usage": usage,
            "request_cost_cny": role_cost_cny(
                self.role_policy,
                usage,
            ),
            "role_cumulative_usage": cumulative,
            "role_cumulative_cost_cny": role_cost_cny(
                self.role_policy,
                cumulative,
            ),
            "budget_status_after_request": status,
            "recorded_at": recorded_at,
        }
        event = {**core, "event_sha256": sha256_canonical_json(core)}
        new_events = [*self.events, event]
        new_status = validate_public_budget_events(
            new_events,
            run_id=self.run_id,
            execution_identity=self.execution_identity,
            model_role=self.model_role,
            known_work_keys=self.known_work_keys,
            role_policy=self.role_policy,
        )
        _append_fsynced(self.path, event)
        self.events = new_events
        self.status = new_status
        return copy.deepcopy(event)


class PublicBudgetClient:
    """在角色级预算账本中记录单个官方完成事件。"""

    def __init__(
        self,
        client: Any,
        *,
        tracker: PublicBudgetTracker,
        work_key: str,
        recorded_at: Any,
    ) -> None:
        self._client = client
        self._tracker = tracker
        self._work_key = work_key
        self._recorded_at = recorded_at

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        case: dict[str, Any] | None = None,
        step: int = 1,
        observations: list[Any] | None = None,
    ) -> OfficialProviderCompletion:
        self._tracker.assert_before_request()
        completion = self._client.complete(
            messages,
            case=case,
            step=step,
            observations=observations,
        )
        self._tracker.record_completion(
            work_key=self._work_key,
            call_index=step,
            completion=completion,
            recorded_at=str(self._recorded_at()),
        )
        return completion


def validate_public_experiment_record(
    record: Mapping[str, Any],
    *,
    role_policy: Mapping[str, Any],
    online_projection: Mapping[str, Any] | None = None,
) -> None:
    schema, registry = contracts_v2._schema_registry()
    Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FormatChecker(),
    ).validate(dict(record))
    _validate_digest_semantics(record["online_visible_field_digest"])
    _validate_decision_semantics(record)
    _validate_outcome_semantics(record)
    bundle = validate_public_trace_bundle(
        record["provider_trace_bundle"],
        role_policy=role_policy,
    )
    tier = record["result_tier"]
    if tier == "diagnostic":
        if (
            bundle["result_tier_ceiling"] != "diagnostic"
            or record["operational_status"] != "provider_failure"
        ):
            raise PublicExecutionStoreError(
                "public diagnostic record requires a failed bundle"
            )
    elif (
        tier not in {"formal_candidate", "formal_admitted"}
        or bundle["result_tier_ceiling"] != "formal_candidate"
    ):
        raise PublicExecutionStoreError(
            "public formal record exceeds its bundle ceiling"
        )
    if tier == "formal_admitted" and not record.get(
        "admission_manifest_sha256"
    ):
        raise PublicExecutionStoreError(
            "public admitted record lacks admission identity"
        )
    safety = record["provider_safety_receipt"]
    validate_safety_receipt(safety)
    if safety["evidence"]["provider_id"] != bundle["provider_id"]:
        raise PublicExecutionStoreError(
            "public safety receipt/provider drift"
        )
    if online_projection is not None:
        expected = compute_online_visible_field_digest(online_projection)
        if expected != record["online_visible_field_digest"]:
            raise PublicExecutionStoreError(
                "public online projection digest drift"
            )


def assemble_public_experiment_record(
    work_item: Mapping[str, Any],
    initial_online_state: Mapping[str, Any],
    execution_result: Mapping[str, Any],
    *,
    run_id: str,
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    events = execution_result.get("runtime_visibility_events")
    if not isinstance(events, list):
        raise PublicExecutionStoreError(
            "public result lacks runtime visibility events"
        )
    projection = {
        "initial_online_state": dict(initial_online_state),
        "runtime_visibility_events": events,
    }
    bundle_raw = execution_result.get("provider_trace_bundle")
    if not isinstance(bundle_raw, Mapping):
        raise PublicExecutionStoreError("public result lacks trace bundle")
    bundle = validate_public_trace_bundle(
        bundle_raw,
        role_policy=role_policy,
    )
    if (
        bundle["execution_identity"] != work_item["execution_identity"]
        or bundle["work_key"] != work_item["work_key"]
    ):
        raise PublicExecutionStoreError(
            "public trace/work-item identity drift"
        )
    safety_receipt = execution_result.get("safety_receipt")
    if not isinstance(safety_receipt, Mapping):
        raise PublicExecutionStoreError(
            "public result lacks safety receipt"
        )
    validate_safety_receipt(safety_receipt)
    initial = str(execution_result["initial_guard_decision"])
    confirmation = str(execution_result["confirmation_result"])
    effective = _effective_decision(initial, confirmation)
    status = str(execution_result["operational_status"])
    failure = status in {
        "timeout",
        "parse_failure",
        "max_steps",
        "provider_failure",
        "runner_failure",
    }
    unsafe_effect = execution_result.get("unsafe_effect")
    tier = str(execution_result["result_tier"])
    expected_ceiling = "formal_candidate" if tier == "formal_admitted" else tier
    if bundle["result_tier_ceiling"] != expected_ceiling:
        raise PublicExecutionStoreError(
            "public result tier exceeds trace ceiling"
        )
    record: dict[str, Any] = {
        "schema_version": EXPERIMENT_RECORD_SCHEMA_VERSION,
        "record_id": "pending",
        "run_id": run_id,
        "case_id": work_item["case_id"],
        "benchmark_id": work_item["benchmark"],
        "condition_id": work_item["condition_id"],
        "evaluation_case_type": work_item["evaluation_case_type"],
        "authorization_regime": work_item["authorization_regime"],
        "online_visible_field_digest": compute_online_visible_field_digest(
            projection
        ),
        "initial_guard_decision": initial,
        "effective_decision": effective,
        "ask_reason": execution_result.get("ask_reason"),
        "confirmation_result": confirmation,
        "unsafe_effect": None if failure else unsafe_effect,
        "unsafe_effect_itt": True if failure else bool(unsafe_effect),
        "task_completion": (
            False
            if failure or status == "refusal"
            else bool(execution_result["task_completion"])
        ),
        "operational_status": status,
        "included_in_intention_to_treat": True,
        "provider_trace_bundle": bundle,
        "provider_safety_receipt": copy.deepcopy(dict(safety_receipt)),
        "result_tier": tier,
        "latency_ms": dict(execution_result["latency_ms"]),
        "token_usage": dict(execution_result["token_usage"]),
        "recorded_at": execution_result["recorded_at"],
    }
    admission = execution_result.get("admission_manifest_sha256")
    if admission is not None:
        record["admission_manifest_sha256"] = admission
    record["record_id"] = _expected_record_id(
        record,
        work_key=str(work_item["work_key"]),
    )
    validate_public_experiment_record(
        record,
        role_policy=role_policy,
        online_projection=projection,
    )
    return record


def load_public_record_entries(path: Path) -> list[dict[str, Any]]:
    return _load_jsonl(path)


def validate_public_record_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    work_items: Iterable[Mapping[str, Any]],
    execution_identity: str,
    run_id: str,
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    by_key = _work_item_map(work_items)
    if any(
        item["execution_identity"] != execution_identity
        for item in by_key.values()
    ):
        raise PublicExecutionStoreError(
            "public record identity/work-item drift"
        )
    previous: str | None = None
    work_keys: set[str] = set()
    record_ids: set[str] = set()
    for sequence, entry in enumerate(entries, start=1):
        if not isinstance(entry, Mapping) or set(entry) != ENTRY_FIELDS:
            raise PublicExecutionStoreError(
                f"public record entry {sequence} fields drift"
            )
        if (
            entry.get("schema_version") != ENTRY_SCHEMA_VERSION
            or entry.get("ledger_sequence") != sequence
            or entry.get("previous_entry_sha256") != previous
            or entry.get("execution_identity") != execution_identity
            or entry.get("run_id") != run_id
            or entry.get("entry_sha256") != sha256_canonical_json(
                _entry_core(entry)
            )
        ):
            raise PublicExecutionStoreError(
                f"public record entry {sequence} identity/hash drift"
            )
        validate_persisted_ledger_value(entry)
        record = entry.get("record")
        if not isinstance(record, Mapping):
            raise PublicExecutionStoreError("public record is missing")
        events = _validate_sanitized_events(
            entry.get("runtime_visibility_events")
        )
        work_key = str(entry.get("work_key", ""))
        if (
            entry.get("record_sha256")
            != sha256_canonical_json(record)
            or entry.get("runtime_visibility_events_sha256")
            != sha256_canonical_json(events)
            or work_key not in by_key
            or work_key in work_keys
        ):
            raise PublicExecutionStoreError(
                f"public record entry {sequence} payload/work drift"
            )
        item = by_key[work_key]
        expected = {
            "run_id": run_id,
            "case_id": item["case_id"],
            "benchmark_id": item["benchmark"],
            "condition_id": item["condition_id"],
            "evaluation_case_type": item["evaluation_case_type"],
            "authorization_regime": item["authorization_regime"],
        }
        if {key: record.get(key) for key in expected} != expected:
            raise PublicExecutionStoreError(
                "public record metadata/work-item drift"
            )
        record_id = str(record.get("record_id", ""))
        if (
            entry.get("record_id") != record_id
            or record_id != _expected_record_id(record, work_key=work_key)
            or record_id in record_ids
        ):
            raise PublicExecutionStoreError(
                "public record identity drift"
            )
        hydrated, state = hydrate_public_work_item(item)
        del hydrated
        projection = {
            "initial_online_state": state,
            "runtime_visibility_events": events,
        }
        validate_public_experiment_record(
            record,
            role_policy=role_policy,
            online_projection=projection,
        )
        previous = str(entry["entry_sha256"])
        work_keys.add(work_key)
        record_ids.add(record_id)
    return {
        "entry_count": len(entries),
        "terminal_work_keys": sorted(work_keys),
        "remaining_work_items": len(by_key) - len(work_keys),
        "tail_sha256": previous,
        "hash_chain_complete": True,
    }


def append_public_execution_result(
    path: Path,
    *,
    work_items: Sequence[Mapping[str, Any]],
    work_item: Mapping[str, Any],
    initial_online_state: Mapping[str, Any],
    execution_result: Mapping[str, Any],
    execution_identity: str,
    run_id: str,
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    record = assemble_public_experiment_record(
        work_item,
        initial_online_state,
        execution_result,
        run_id=run_id,
        role_policy=role_policy,
    )
    entries = load_public_record_entries(path)
    status = validate_public_record_entries(
        entries,
        work_items=work_items,
        execution_identity=execution_identity,
        run_id=run_id,
        role_policy=role_policy,
    )
    events = _validate_sanitized_events(
        execution_result["runtime_visibility_events"]
    )
    core = {
        "schema_version": ENTRY_SCHEMA_VERSION,
        "ledger_sequence": len(entries) + 1,
        "previous_entry_sha256": status["tail_sha256"],
        "execution_identity": execution_identity,
        "work_key": work_item["work_key"],
        "run_id": run_id,
        "record_id": record["record_id"],
        "record_sha256": sha256_canonical_json(record),
        "runtime_visibility_events_sha256": sha256_canonical_json(events),
        "record": record,
        "runtime_visibility_events": events,
    }
    entry = {**core, "entry_sha256": sha256_canonical_json(core)}
    validate_persisted_ledger_value(entry)
    _append_fsynced(path, entry)
    validate_public_record_entries(
        [*entries, entry],
        work_items=work_items,
        execution_identity=execution_identity,
        run_id=run_id,
        role_policy=role_policy,
    )
    return copy.deepcopy(entry)


def cross_bind_public_budget_and_records(
    *,
    budget_events: Sequence[Mapping[str, Any]],
    record_entries: Sequence[Mapping[str, Any]],
    trace_root: Path,
    role_policy: Mapping[str, Any],
) -> None:
    budget_by_response = {
        str(event["provider_response_id"]): event for event in budget_events
    }
    observed: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for entry in record_entries:
        work_key = str(entry["work_key"])
        bundle = validate_public_trace_bundle(
            entry["record"]["provider_trace_bundle"],
            role_policy=role_policy,
        )
        trace_path = trace_root / f"{work_key}.jsonl"
        if (
            not trace_path.is_file()
            or _load_jsonl(trace_path) != bundle["trace_rows"]
        ):
            raise PublicExecutionStoreError(
                "public independent trace/record bundle drift"
            )
        for usage in bundle["usage_evidence"]:
            response_id = str(usage["provider_response_id"])
            if response_id in observed:
                raise PublicExecutionStoreError(
                    "public provider response identity was reused"
                )
            observed[response_id] = (work_key, usage)
    if set(observed) != set(budget_by_response):
        raise PublicExecutionStoreError(
            "public budget ledger does not bind completed calls"
        )
    for response_id, (work_key, usage) in observed.items():
        event = budget_by_response[response_id]
        expected_usage = {
            field: int(usage[field]) for field in USAGE_FIELDS
        }
        if (
            event["work_key"] != work_key
            or event["usage"] != expected_usage
            or event["request_cost_cny"]
            != role_cost_cny(role_policy, expected_usage)
        ):
            raise PublicExecutionStoreError(
                "public budget/record usage drift"
            )
