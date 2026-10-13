"""面向 Gemini 轨迹包的仅追加公开实验记录存储器。

持久化保存每个基准用例的完整调用链条与沙箱交互日志。
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from experiments.paper_v2.contracts import (
    _validate_decision_semantics,
    _validate_digest_semantics,
    _validate_outcome_semantics,
    compute_online_visible_field_digest,
    sha256_canonical_json,
)
from experiments.paper_v2.formal_record_store import (
    _validate_sanitized_events,
    _work_item_map,
    validate_persisted_ledger_value,
)
from experiments.paper_v2.formal_record_store_v2 import (
    ENTRY_FIELDS,
    _effective_decision,
    _entry_core,
)
from experiments.paper_v2.gemini_public_trace_v1 import (
    validate_trace_bundle,
)
from experiments.paper_v2.provider_safety import validate_safety_receipt
from experiments.paper_v2.public_matrix_plan_v1 import hydrate_public_work_item


RECORD_SCHEMA_VERSION = "m3-paper-v2-gemini-experiment-record-1.0"
ENTRY_SCHEMA_VERSION = "m3-paper-v2-gemini-record-entry-1.0"
RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "record_id",
        "run_id",
        "execution_identity",
        "work_key",
        "provider_id",
        "model_id",
        "model_role",
        "case_id",
        "benchmark_id",
        "condition_id",
        "evaluation_case_type",
        "authorization_regime",
        "online_visible_field_digest",
        "initial_guard_decision",
        "effective_decision",
        "ask_reason",
        "confirmation_result",
        "unsafe_effect",
        "unsafe_effect_itt",
        "task_completion",
        "operational_status",
        "included_in_intention_to_treat",
        "provider_attestation",
        "provider_trace_bundle",
        "provider_safety_receipt",
        "isolated_effect_receipt_sha256",
        "result_tier",
        "admission_manifest_sha256",
        "latency_ms",
        "token_usage",
        "recorded_at",
    }
)
FAILURE_STATUSES = frozenset(
    {"timeout", "parse_failure", "max_steps", "provider_failure", "runner_failure"}
)


class GeminiPublicExecutionStoreV1Error(ValueError):
    """当 Gemini 公开记录链不完整或发生漂移时抛出的异常。"""


def _expected_record_id(record: Mapping[str, Any]) -> str:
    identity = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "run_id": record["run_id"],
        "execution_identity": record["execution_identity"],
        "work_key": record["work_key"],
        "result_tier": record["result_tier"],
        "provider_trace_bundle_sha256": record["provider_trace_bundle"][
            "bundle_sha256"
        ],
        "provider_trace_tail_sha256": record["provider_trace_bundle"][
            "trace_tail_sha256"
        ],
    }
    return "gemini-record-" + sha256_canonical_json(identity)[:24]


def _validate_provider_attestation(
    attestation: Any,
    *,
    bundle: Mapping[str, Any],
) -> None:
    if not isinstance(attestation, Mapping):
        raise GeminiPublicExecutionStoreV1Error(
            "Gemini provider attestation is missing"
        )
    activated = bundle["activated_attestations"]
    if bundle["result_tier_ceiling"] == "formal_candidate":
        if not activated:
            raise GeminiPublicExecutionStoreV1Error(
                "formal Gemini bundle lacks an activated response"
            )
        last = activated[-1]
        if (
            attestation.get("provider_name") != "Google"
            or attestation.get("upstream_provider") != "Google"
            or attestation.get("model_id") != bundle["model_id"]
            or attestation.get("response_id") != last["provider_response_id"]
            or attestation.get("parameters_sha256") != last["payload_sha256"]
            or attestation.get("identity_verified") is not True
        ):
            raise GeminiPublicExecutionStoreV1Error(
                "Gemini attestation does not bind the final trace response"
            )
    elif attestation.get("response_id") is not None:
        raise GeminiPublicExecutionStoreV1Error(
            "incomplete Gemini trace cannot claim a response"
        )


def validate_gemini_experiment_record(
    record: Mapping[str, Any],
    *,
    online_projection: Mapping[str, Any] | None = None,
) -> None:
    if set(record) != RECORD_FIELDS:
        raise GeminiPublicExecutionStoreV1Error(
            "Gemini experiment-record fields drift"
        )
    bundle = validate_trace_bundle(record["provider_trace_bundle"])
    safety = record["provider_safety_receipt"]
    validate_safety_receipt(safety)
    if (
        record["schema_version"] != RECORD_SCHEMA_VERSION
        or record["record_id"] != _expected_record_id(record)
        or record["provider_id"] != "gemini"
        or record["model_id"] != bundle["model_id"]
        or record["model_role"] != "second"
        or record["execution_identity"] != bundle["execution_identity"]
        or record["work_key"] != bundle["work_key"]
        or record["admission_manifest_sha256"]
        != bundle["admission_manifest_sha256"]
        or record["included_in_intention_to_treat"] is not True
        or safety["evidence"]["provider_id"] != "gemini"
        or safety["evidence"]["provider_managed_tools_enabled"] is not False
        or safety["evidence"]["external_connectors_enabled"] is not False
        or record["isolated_effect_receipt_sha256"]
        != safety["evidence_sha256"]
    ):
        raise GeminiPublicExecutionStoreV1Error(
            "Gemini record identity or safety boundary drift"
        )
    tier = record["result_tier"]
    if bundle["result_tier_ceiling"] == "diagnostic":
        if tier != "diagnostic" or record["operational_status"] != "provider_failure":
            raise GeminiPublicExecutionStoreV1Error(
                "incomplete Gemini trace must remain diagnostic provider failure"
            )
    elif tier not in {"formal_candidate", "formal_admitted"}:
        raise GeminiPublicExecutionStoreV1Error(
            "complete Gemini trace has an unsupported result tier"
        )
    if tier == "formal_admitted" and not record["admission_manifest_sha256"]:
        raise GeminiPublicExecutionStoreV1Error(
            "admitted Gemini record lacks admission identity"
        )
    _validate_provider_attestation(record["provider_attestation"], bundle=bundle)
    _validate_digest_semantics(record["online_visible_field_digest"])
    _validate_decision_semantics(record)
    _validate_outcome_semantics(record)
    if online_projection is not None:
        expected = compute_online_visible_field_digest(online_projection)
        if record["online_visible_field_digest"] != expected:
            raise GeminiPublicExecutionStoreV1Error(
                "Gemini online-visible digest drift"
            )
    validate_persisted_ledger_value(record)


def assemble_gemini_experiment_record(
    work_item: Mapping[str, Any],
    initial_online_state: Mapping[str, Any],
    execution_result: Mapping[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    events = execution_result.get("runtime_visibility_events")
    bundle_raw = execution_result.get("provider_trace_bundle")
    safety_raw = execution_result.get("safety_receipt")
    attestation_raw = execution_result.get("provider_attestation")
    if (
        not isinstance(events, list)
        or not isinstance(bundle_raw, Mapping)
        or not isinstance(safety_raw, Mapping)
        or not isinstance(attestation_raw, Mapping)
    ):
        raise GeminiPublicExecutionStoreV1Error(
            "Gemini execution result lacks required evidence"
        )
    bundle = validate_trace_bundle(bundle_raw)
    validate_safety_receipt(safety_raw)
    if (
        bundle["execution_identity"] != work_item["execution_identity"]
        or bundle["work_key"] != work_item["work_key"]
    ):
        raise GeminiPublicExecutionStoreV1Error(
            "Gemini trace does not bind the public work item"
        )
    projection = {
        "initial_online_state": dict(initial_online_state),
        "runtime_visibility_events": events,
    }
    initial = str(execution_result["initial_guard_decision"])
    confirmation = str(execution_result["confirmation_result"])
    status = str(execution_result["operational_status"])
    failure = status in FAILURE_STATUSES
    unsafe_effect = execution_result.get("unsafe_effect")
    record: dict[str, Any] = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "record_id": "pending",
        "run_id": run_id,
        "execution_identity": work_item["execution_identity"],
        "work_key": work_item["work_key"],
        "provider_id": "gemini",
        "model_id": work_item["model_id"],
        "model_role": work_item["model_role"],
        "case_id": work_item["case_id"],
        "benchmark_id": work_item["benchmark"],
        "condition_id": work_item["condition_id"],
        "evaluation_case_type": work_item["evaluation_case_type"],
        "authorization_regime": work_item["authorization_regime"],
        "online_visible_field_digest": compute_online_visible_field_digest(
            projection
        ),
        "initial_guard_decision": initial,
        "effective_decision": _effective_decision(initial, confirmation),
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
        "provider_attestation": copy.deepcopy(dict(attestation_raw)),
        "provider_trace_bundle": bundle,
        "provider_safety_receipt": copy.deepcopy(dict(safety_raw)),
        "isolated_effect_receipt_sha256": safety_raw["evidence_sha256"],
        "result_tier": str(execution_result["result_tier"]),
        "admission_manifest_sha256": str(
            execution_result["admission_manifest_sha256"]
        ),
        "latency_ms": dict(execution_result["latency_ms"]),
        "token_usage": dict(execution_result["token_usage"]),
        "recorded_at": execution_result["recorded_at"],
    }
    record["record_id"] = _expected_record_id(record)
    validate_gemini_experiment_record(record, online_projection=projection)
    return record


def load_record_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line_number, raw in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not raw.strip():
                raise GeminiPublicExecutionStoreV1Error(
                    f"{path}:{line_number}: blank record row"
                )
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise GeminiPublicExecutionStoreV1Error(
                    f"{path}:{line_number}: expected object"
                )
            rows.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiPublicExecutionStoreV1Error(
            f"{path}: invalid UTF-8 JSONL"
        ) from exc
    return rows


def validate_record_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    work_items: Iterable[Mapping[str, Any]],
    execution_identity: str,
    run_id: str,
) -> dict[str, Any]:
    by_key = _work_item_map(work_items)
    if any(
        item["execution_identity"] != execution_identity
        for item in by_key.values()
    ):
        raise GeminiPublicExecutionStoreV1Error(
            "Gemini work-item execution identities differ"
        )
    previous: str | None = None
    seen_work: set[str] = set()
    seen_records: set[str] = set()
    for sequence, entry in enumerate(entries, start=1):
        if (
            not isinstance(entry, Mapping)
            or set(entry) != ENTRY_FIELDS
            or entry.get("schema_version") != ENTRY_SCHEMA_VERSION
            or entry.get("ledger_sequence") != sequence
            or entry.get("previous_entry_sha256") != previous
            or entry.get("execution_identity") != execution_identity
            or entry.get("run_id") != run_id
            or entry.get("entry_sha256") != sha256_canonical_json(_entry_core(entry))
        ):
            raise GeminiPublicExecutionStoreV1Error(
                f"Gemini record entry {sequence} envelope drift"
            )
        record = entry.get("record")
        events = _validate_sanitized_events(entry.get("runtime_visibility_events"))
        work_key = str(entry.get("work_key", ""))
        if (
            not isinstance(record, Mapping)
            or work_key not in by_key
            or work_key in seen_work
            or entry.get("record_sha256") != sha256_canonical_json(record)
            or entry.get("runtime_visibility_events_sha256")
            != sha256_canonical_json(events)
        ):
            raise GeminiPublicExecutionStoreV1Error(
                f"Gemini record entry {sequence} payload drift"
            )
        item = by_key[work_key]
        hydrated, initial_state = hydrate_public_work_item(item)
        del hydrated
        projection = {
            "initial_online_state": initial_state,
            "runtime_visibility_events": events,
        }
        validate_gemini_experiment_record(record, online_projection=projection)
        expected = {
            "run_id": run_id,
            "execution_identity": execution_identity,
            "work_key": work_key,
            "case_id": item["case_id"],
            "benchmark_id": item["benchmark"],
            "condition_id": item["condition_id"],
            "evaluation_case_type": item["evaluation_case_type"],
            "authorization_regime": item["authorization_regime"],
        }
        record_id = str(record["record_id"])
        if (
            {key: record.get(key) for key in expected} != expected
            or entry.get("record_id") != record_id
            or record_id in seen_records
        ):
            raise GeminiPublicExecutionStoreV1Error(
                f"Gemini record entry {sequence} work binding drift"
            )
        validate_persisted_ledger_value(entry)
        previous = str(entry["entry_sha256"])
        seen_work.add(work_key)
        seen_records.add(record_id)
    return {
        "entry_count": len(entries),
        "terminal_work_keys": sorted(seen_work),
        "remaining_work_items": len(by_key) - len(seen_work),
        "tail_sha256": previous,
        "hash_chain_complete": True,
    }


def append_execution_result(
    path: Path,
    *,
    work_items: Sequence[Mapping[str, Any]],
    work_item: Mapping[str, Any],
    initial_online_state: Mapping[str, Any],
    execution_result: Mapping[str, Any],
    execution_identity: str,
    run_id: str,
) -> dict[str, Any]:
    prior = load_record_entries(path)
    status = validate_record_entries(
        prior,
        work_items=work_items,
        execution_identity=execution_identity,
        run_id=run_id,
    )
    record = assemble_gemini_experiment_record(
        work_item,
        initial_online_state,
        execution_result,
        run_id=run_id,
    )
    events = _validate_sanitized_events(
        execution_result["runtime_visibility_events"]
    )
    core = {
        "schema_version": ENTRY_SCHEMA_VERSION,
        "ledger_sequence": len(prior) + 1,
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(
            json.dumps(
                entry,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        stream.flush()
        os.fsync(stream.fileno())
    validate_record_entries(
        load_record_entries(path),
        work_items=work_items,
        execution_identity=execution_identity,
        run_id=run_id,
    )
    return entry
