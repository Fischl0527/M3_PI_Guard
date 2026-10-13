"""面向前瞻性 experiment-record v2 证据的仅追加记录存储器。

增强了对多轮会话追踪、中间防御决策链与沙箱环境快照的存储支持。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from experiments.paper_v2.contracts import (
    compute_online_visible_field_digest,
    sha256_canonical_json,
)
from experiments.paper_v2.contracts_v2 import (
    EXPERIMENT_RECORD_SCHEMA_VERSION,
    validate_experiment_record_v2,
)
from experiments.paper_v2.formal_record_store import (
    FormalRecordStoreError,
    _load_plan,
    _validate_sanitized_events,
    _work_item_map,
    validate_persisted_ledger_value,
)
from experiments.paper_v2.medium_runtime import (
    _effective_decision,
    reconstruct_initial_online_state,
)
from experiments.paper_v2.provider_safety import validate_safety_receipt
from experiments.paper_v2.provider_request_trace_activation import (
    activate_trace_attestation,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    FIXED_MESSAGES,
    _as_official_receipt,
    _fixture_client,
    append_completed_trace,
    append_started_trace,
    build_request_commitment,
)
from experiments.paper_v2.provider_trace_bundle import (
    build_deepseek_usage_evidence,
    build_provider_trace_bundle,
    validate_provider_trace_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/formal_record_store_qualification_v2.json"
)
ENTRY_SCHEMA_VERSION = "m3-paper-v2-formal-record-entry-2.2"
QUALIFICATION_SCHEMA_VERSION = (
    "m3-paper-v2-formal-record-store-qualification-2.2"
)
QUALIFICATION_RECORDED_AT = "2026-07-24T02:00:00+08:00"
ENTRY_FIELDS = frozenset(
    {
        "schema_version",
        "ledger_sequence",
        "previous_entry_sha256",
        "execution_identity",
        "work_key",
        "run_id",
        "record_id",
        "record_sha256",
        "runtime_visibility_events_sha256",
        "record",
        "runtime_visibility_events",
        "entry_sha256",
    }
)


def _entry_core(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in entry.items()
        if key != "entry_sha256"
    }


def _expected_record_id(
    record: Mapping[str, Any],
    *,
    work_key: str,
) -> str:
    bundle = record["provider_trace_bundle"]
    identity = {
        "schema_version": EXPERIMENT_RECORD_SCHEMA_VERSION,
        "run_id": record["run_id"],
        "work_key": work_key,
        "result_tier": record["result_tier"],
        "provider_trace_bundle_sha256": bundle["bundle_sha256"],
        "provider_trace_tail_sha256": bundle["trace_tail_sha256"],
    }
    return "record-v2-" + sha256_canonical_json(identity)[:24]


def load_record_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    raise FormalRecordStoreError(
                        f"{path}:{line_number}: blank ledger row"
                    )
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise FormalRecordStoreError(
                        f"{path}:{line_number}: expected an object"
                    )
                entries.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FormalRecordStoreError(
            f"{path}: record ledger is not valid UTF-8 JSONL"
        ) from exc
    return entries


def validate_record_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    work_items: Iterable[Mapping[str, Any]],
    execution_identity: str,
    run_id: str,
) -> dict[str, Any]:
    by_key = _work_item_map(work_items)
    expected_identity = next(
        iter(item["execution_identity"] for item in by_key.values())
    )
    if execution_identity != expected_identity:
        raise FormalRecordStoreError(
            "execution identity does not match frozen work items"
        )
    previous: str | None = None
    work_keys: set[str] = set()
    record_ids: set[str] = set()
    for sequence, entry in enumerate(entries, start=1):
        if not isinstance(entry, Mapping) or set(entry) != ENTRY_FIELDS:
            raise FormalRecordStoreError(
                f"v2 ledger entry {sequence} fields drift"
            )
        if (
            entry.get("schema_version") != ENTRY_SCHEMA_VERSION
            or entry.get("ledger_sequence") != sequence
            or entry.get("previous_entry_sha256") != previous
            or entry.get("execution_identity") != execution_identity
            or entry.get("run_id") != run_id
        ):
            raise FormalRecordStoreError(
                f"v2 ledger entry {sequence} identity drift"
            )
        validate_persisted_ledger_value(entry)
        if entry.get("entry_sha256") != sha256_canonical_json(
            _entry_core(entry)
        ):
            raise FormalRecordStoreError(
                f"v2 ledger entry {sequence} hash drift"
            )
        record = entry.get("record")
        if not isinstance(record, Mapping):
            raise FormalRecordStoreError("v2 ledger record is missing")
        events = _validate_sanitized_events(
            entry.get("runtime_visibility_events")
        )
        if (
            entry.get("record_sha256")
            != sha256_canonical_json(record)
            or entry.get("runtime_visibility_events_sha256")
            != sha256_canonical_json(events)
        ):
            raise FormalRecordStoreError(
                f"v2 ledger entry {sequence} payload hash drift"
            )
        work_key = entry.get("work_key")
        if work_key not in by_key or work_key in work_keys:
            raise FormalRecordStoreError(
                "v2 ledger work key is unknown or duplicated"
            )
        item = by_key[str(work_key)]
        expected_metadata = {
            "run_id": run_id,
            "case_id": item["case_id"],
            "benchmark_id": item["benchmark"],
            "condition_id": item["condition_id"],
            "evaluation_case_type": item["evaluation_case_type"],
            "authorization_regime": item["authorization_regime"],
        }
        if {
            key: record.get(key) for key in expected_metadata
        } != expected_metadata:
            raise FormalRecordStoreError(
                "v2 record/work-item metadata drift"
            )
        bundle = record.get("provider_trace_bundle")
        if (
            not isinstance(bundle, Mapping)
            or bundle.get("execution_identity") != execution_identity
            or bundle.get("work_key") != work_key
        ):
            raise FormalRecordStoreError(
                "v2 provider trace bundle/work-item identity drift"
            )
        record_id = record.get("record_id")
        if (
            entry.get("record_id") != record_id
            or record_id
            != _expected_record_id(record, work_key=str(work_key))
            or record_id in record_ids
        ):
            raise FormalRecordStoreError("v2 record identity drift")
        projection = {
            "initial_online_state": reconstruct_initial_online_state(item),
            "runtime_visibility_events": events,
        }
        validate_experiment_record_v2(
            record,
            online_projection=projection,
        )
        previous = str(entry["entry_sha256"])
        work_keys.add(str(work_key))
        record_ids.add(str(record_id))
    return {
        "entry_count": len(entries),
        "terminal_work_keys": sorted(work_keys),
        "remaining_work_items": len(by_key) - len(work_keys),
        "tail_sha256": previous,
        "hash_chain_complete": True,
    }


def build_record_entry(
    *,
    work_item: Mapping[str, Any],
    record: Mapping[str, Any],
    runtime_visibility_events: Sequence[Mapping[str, Any]],
    run_id: str,
    ledger_sequence: int,
    previous_entry_sha256: str | None,
) -> dict[str, Any]:
    events = _validate_sanitized_events(runtime_visibility_events)
    validate_persisted_ledger_value(record)
    projection = {
        "initial_online_state": reconstruct_initial_online_state(work_item),
        "runtime_visibility_events": events,
    }
    validate_experiment_record_v2(
        record,
        online_projection=projection,
    )
    if record["record_id"] != _expected_record_id(
        record,
        work_key=str(work_item["work_key"]),
    ):
        raise FormalRecordStoreError("v2 record ID does not bind work item")
    core = {
        "schema_version": ENTRY_SCHEMA_VERSION,
        "ledger_sequence": ledger_sequence,
        "previous_entry_sha256": previous_entry_sha256,
        "execution_identity": work_item["execution_identity"],
        "work_key": work_item["work_key"],
        "run_id": run_id,
        "record_id": record["record_id"],
        "record_sha256": sha256_canonical_json(record),
        "runtime_visibility_events_sha256": sha256_canonical_json(events),
        "record": dict(record),
        "runtime_visibility_events": events,
    }
    entry = {
        **core,
        "entry_sha256": sha256_canonical_json(core),
    }
    validate_persisted_ledger_value(entry)
    return entry


def append_record_entry(
    path: Path,
    *,
    work_items: Sequence[Mapping[str, Any]],
    work_item: Mapping[str, Any],
    record: Mapping[str, Any],
    runtime_visibility_events: Sequence[Mapping[str, Any]],
    execution_identity: str,
    run_id: str,
) -> dict[str, Any]:
    entries = load_record_entries(path)
    status = validate_record_entries(
        entries,
        work_items=work_items,
        execution_identity=execution_identity,
        run_id=run_id,
    )
    entry = build_record_entry(
        work_item=work_item,
        record=record,
        runtime_visibility_events=runtime_visibility_events,
        run_id=run_id,
        ledger_sequence=len(entries) + 1,
        previous_entry_sha256=status["tail_sha256"],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        entry,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    final_entries = load_record_entries(path)
    validate_record_entries(
        final_entries,
        work_items=work_items,
        execution_identity=execution_identity,
        run_id=run_id,
    )
    return entry


def assemble_experiment_record_v2(
    work_item: Mapping[str, Any],
    initial_online_state: Mapping[str, Any],
    execution_result: Mapping[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    """从追踪的条件结果组装单个 v2 记录。"""

    events = execution_result.get("runtime_visibility_events")
    if not isinstance(events, list):
        raise FormalRecordStoreError(
            "v2 execution result requires runtime visibility events"
        )
    projection = {
        "initial_online_state": dict(initial_online_state),
        "runtime_visibility_events": events,
    }
    bundle_raw = execution_result.get("provider_trace_bundle")
    if not isinstance(bundle_raw, Mapping):
        raise FormalRecordStoreError(
            "v2 execution result requires a provider trace bundle"
        )
    bundle = validate_provider_trace_bundle(bundle_raw)
    if (
        bundle["execution_identity"] != work_item["execution_identity"]
        or bundle["work_key"] != work_item["work_key"]
    ):
        raise FormalRecordStoreError(
            "provider trace bundle does not bind the work item"
        )
    safety_receipt = execution_result.get("safety_receipt")
    if not isinstance(safety_receipt, Mapping):
        raise FormalRecordStoreError(
            "v2 execution result requires a provider safety receipt"
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
    tier = str(execution_result["result_tier"])
    if tier == "formal_admitted":
        expected_ceiling = "formal_candidate"
    else:
        expected_ceiling = tier
    if bundle["result_tier_ceiling"] != expected_ceiling:
        raise FormalRecordStoreError(
            "result tier exceeds the provider trace bundle ceiling"
        )
    unsafe_effect = execution_result.get("unsafe_effect")
    record: dict[str, Any] = {
        "schema_version": EXPERIMENT_RECORD_SCHEMA_VERSION,
        "record_id": "pending",
        "run_id": run_id,
        "case_id": work_item["case_id"],
        "benchmark_id": work_item["benchmark"],
        "condition_id": work_item["condition_id"],
        "evaluation_case_type": work_item["evaluation_case_type"],
        "authorization_regime": work_item["authorization_regime"],
        "online_visible_field_digest": (
            compute_online_visible_field_digest(projection)
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
    validate_experiment_record_v2(
        record,
        online_projection=projection,
    )
    return record


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
    """组装、追加、fsync 并重新验证单个追踪的执行结果。"""

    record = assemble_experiment_record_v2(
        work_item,
        initial_online_state,
        execution_result,
        run_id=run_id,
    )
    return append_record_entry(
        path,
        work_items=work_items,
        work_item=work_item,
        record=record,
        runtime_visibility_events=execution_result[
            "runtime_visibility_events"
        ],
        execution_identity=execution_identity,
        run_id=run_id,
    )


def _qualification_event(index: int) -> dict[str, Any]:
    arguments = {"qualification_index": index}
    details = {
        "controller": "offline-v2-record-store",
        "index": index,
    }
    return {
        "step": 1,
        "parse_ok": True,
        "parse_error_code": None,
        "action_proposal": {
            "tool": "final",
            "arguments": arguments,
            "arguments_sha256": sha256_canonical_json(arguments),
        },
        "guard_decision": {
            "decision": "ALLOW",
            "reason_code": "offline_v2_record_store_qualification",
            "violated_constraints": [],
        },
        "controller_evidence": {
            "controller_id": "offline-v2-record-store",
            "decision": "ALLOW",
            "score": None,
            "threshold": None,
            "scan_count": 0,
            "source_sha256": None,
            "details_sha256": sha256_canonical_json(details),
        },
        "execution_attempted": True,
        "execution_succeeded": True,
        "response_text_sha256": sha256_canonical_json(
            {"normalized": "SAFE"}
        ),
        "response_text_bytes": 4,
        "observation_sha256": sha256_canonical_json(
            {"status": "qualification-only"}
        ),
        "observation_bytes": 18,
        "provider_receipt_sha256": None,
    }


def _fixture_bundle(
    root: Path,
    *,
    execution_identity: str,
    work_key: str,
    index: int,
    failure: bool,
) -> dict[str, Any]:
    client = _fixture_client("deepseek", include_request_id=False)
    commitment = build_request_commitment(
        client,
        FIXED_MESSAGES,
        execution_identity=execution_identity,
        work_key=work_key,
        call_index=1,
        attempt_id=f"offline-v2-attempt-{index}",
        precommitted_at=QUALIFICATION_RECORDED_AT,
    )
    trace = root / f"fixture-trace-{index}.jsonl"
    append_started_trace(trace, commitment)
    activated: dict[str, Mapping[str, Any]] = {}
    usage_evidence: dict[str, Mapping[str, Any]] = {}
    failures: dict[str, Mapping[str, str]] = {}
    if failure:
        failures[commitment["client_request_id"]] = {
            "client_request_id": commitment["client_request_id"],
            "status": "provider_failure",
            "error_type": "OfflineQualificationProviderError",
        }
    else:
        receipt = _as_official_receipt(
            client.complete(FIXED_MESSAGES, step=1).receipt
        )
        terminal = append_completed_trace(
            trace,
            client_request_id=commitment["client_request_id"],
            receipt=receipt,
        )
        activated[commitment["client_request_id"]] = (
            activate_trace_attestation(
                terminal["event"]["attestation"]
            )
        )
        usage_evidence[commitment["client_request_id"]] = (
            build_deepseek_usage_evidence(
                receipt,
                commitment,
                prior_items=[],
                policy=client.policy,
            )
        )
    return build_provider_trace_bundle(
        trace_path=trace,
        execution_identity=execution_identity,
        work_key=work_key,
        provider_id=client.provider_id,
        model_id=client.model,
        activated_attestations=activated,
        usage_evidence=usage_evidence,
        failures=failures,
    )


def _qualification_record(
    root: Path,
    *,
    item: Mapping[str, Any],
    run_id: str,
    index: int,
    failure: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events = [_qualification_event(index)]
    arguments = events[0]["action_proposal"]["arguments"]
    projection = {
        "initial_online_state": reconstruct_initial_online_state(item),
        "runtime_visibility_events": events,
    }
    bundle = _fixture_bundle(
        root,
        execution_identity=str(item["execution_identity"]),
        work_key=str(item["work_key"]),
        index=index,
        failure=failure,
    )
    record: dict[str, Any] = {
        "schema_version": EXPERIMENT_RECORD_SCHEMA_VERSION,
        "record_id": "pending",
        "run_id": run_id,
        "case_id": item["case_id"],
        "benchmark_id": item["benchmark"],
        "condition_id": item["condition_id"],
        "evaluation_case_type": item["evaluation_case_type"],
        "authorization_regime": item["authorization_regime"],
        "online_visible_field_digest": (
            compute_online_visible_field_digest(projection)
        ),
        "initial_guard_decision": "ALLOW",
        "effective_decision": "ALLOW",
        "ask_reason": None,
        "confirmation_result": "not_requested",
        "unsafe_effect": None if failure else False,
        "unsafe_effect_itt": failure,
        "task_completion": False,
        "operational_status": (
            "provider_failure" if failure else "completed"
        ),
        "included_in_intention_to_treat": True,
        "provider_trace_bundle": bundle,
        "provider_safety_receipt": {
            "schema_version": "m3-paper-v2-provider-safety-receipt-1.0",
            "credentials_stored": False,
            "evidence": {
                "provider_id": "deepseek",
                "endpoint_origin_and_path": (
                    "https://api.deepseek.com/chat/completions"
                ),
                "effect_backend": "no_effect",
                "tool": "final",
                "arguments_sha256": sha256_canonical_json(arguments),
                "external_connectors_enabled": False,
                "provider_managed_tools_enabled": False,
                "decision": "ALLOW_ISOLATED_SIMULATION_ONLY",
            },
            "evidence_sha256": "",
        },
        "result_tier": "diagnostic" if failure else "formal_candidate",
        "latency_ms": {
            "total": 0.0,
            "model": 0.0,
            "guard": 0.0,
            "tool": 0.0,
        },
        "token_usage": {
            "input": 0,
            "output": 0,
            "total": 0,
            "available": False,
        },
        "recorded_at": QUALIFICATION_RECORDED_AT,
    }
    record["provider_safety_receipt"]["evidence_sha256"] = (
        sha256_canonical_json(
            record["provider_safety_receipt"]["evidence"]
        )
    )
    record["record_id"] = _expected_record_id(
        record,
        work_key=str(item["work_key"]),
    )
    validate_experiment_record_v2(
        record,
        online_projection=projection,
    )
    return record, events


def build_qualification() -> dict[str, Any]:
    work_items = _load_plan()
    selected = work_items[:2]
    execution_identity = str(selected[0]["execution_identity"])
    run_id = "offline-v2-record-store-qualification-not-scientific"
    negative_cases_rejected = 0
    with tempfile.TemporaryDirectory(
        prefix="m3-paper-v2-record-store-v2-"
    ) as directory:
        root = Path(directory)
        ledger = root / "records-v2.jsonl"
        for index, item in enumerate(selected, start=1):
            record, events = _qualification_record(
                root,
                item=item,
                run_id=run_id,
                index=index,
                failure=index == 2,
            )
            append_record_entry(
                ledger,
                work_items=selected,
                work_item=item,
                record=record,
                runtime_visibility_events=events,
                execution_identity=execution_identity,
                run_id=run_id,
            )
        entries = load_record_entries(ledger)
        summary = validate_record_entries(
            entries,
            work_items=selected,
            execution_identity=execution_identity,
            run_id=run_id,
        )
        tampered = copy.deepcopy(entries)
        tampered[0]["record"]["task_completion"] = True
        try:
            validate_record_entries(
                tampered,
                work_items=selected,
                execution_identity=execution_identity,
                run_id=run_id,
            )
        except FormalRecordStoreError:
            negative_cases_rejected += 1
        truncated = copy.deepcopy(entries[1:])
        try:
            validate_record_entries(
                truncated,
                work_items=selected,
                execution_identity=execution_identity,
                run_id=run_id,
            )
        except FormalRecordStoreError:
            negative_cases_rejected += 1
    return {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "status": "offline_v2_record_store_qualified",
        "recorded_at": QUALIFICATION_RECORDED_AT,
        "transient_entries_written": summary["entry_count"],
        "completed_records_written": 1,
        "diagnostic_itt_failure_records_written": 1,
        "provider_safety_receipt_persisted": True,
        "hash_chain_complete": summary["hash_chain_complete"],
        "append_flush_fsync": True,
        "complete_chain_revalidated_after_each_append": True,
        "negative_cases_rejected": negative_cases_rejected,
        "negative_cases_expected": 2,
        "v1_record_contract_modified": False,
        "v1_record_store_modified": False,
        "live_runtime_v2_wiring_qualified": False,
        "network_calls_made": 0,
        "provider_tools_declared": False,
        "external_effects": False,
        "project_experiment_records_persisted": 0,
        "formal_results_created": 0,
        "qualification_evidence_only": True,
    }


def validate_qualification(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or dict(value) != build_qualification():
        raise FormalRecordStoreError("v2 record-store qualification drift")
    return dict(value)


def write_qualification(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_qualification()
    validate_qualification(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def verify_qualification(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return validate_qualification(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    output = (
        args.output
        if args.output.is_absolute()
        else PROJECT_ROOT / args.output
    )
    value = (
        verify_qualification(output)
        if args.verify_only
        else write_qualification(output)
    )
    print(
        json.dumps(
            {
                "status": value["status"],
                "transient_entries_written": value[
                    "transient_entries_written"
                ],
                "network_calls_made": 0,
                "formal_results_created": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
