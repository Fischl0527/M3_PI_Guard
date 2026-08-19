"""Append-only query/record chain for quota-day Gemini adaptive successors."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_record_store import (
    _validate_sanitized_events,
    validate_persisted_ledger_value,
)
from experiments.paper_v2.gemini_public_execution_store_v1 import (
    RECORD_FIELDS,
    _expected_record_id as _public_record_id,
    assemble_gemini_experiment_record,
    validate_gemini_experiment_record,
)
from experiments.paper_v2.gemini_public_trace_v1 import validate_trace_bundle


EVENT_SCHEMA_VERSION = "m3-paper-v2-gemini-adaptive-query-event-1.1"
RECORD_SCHEMA_VERSION = "m3-paper-v2-gemini-adaptive-record-1.0"
MODEL_ROLE = "gemini_replication"


class GeminiAdaptiveQueryStoreV1Error(ValueError):
    """Raised when a Gemini adaptive query chain is incomplete or drifts."""


def _assert_sha256(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise GeminiAdaptiveQueryStoreV1Error(
            f"{field} must be lowercase SHA-256"
        )
    return value


def _record_id(record: Mapping[str, Any]) -> str:
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
    return "gemini-adaptive-record-" + sha256_canonical_json(identity)[:24]


def validate_adaptive_record(
    record: Mapping[str, Any],
    *,
    online_projection: Mapping[str, Any] | None = None,
) -> None:
    if set(record) != RECORD_FIELDS:
        raise GeminiAdaptiveQueryStoreV1Error(
            "Gemini adaptive record fields drift"
        )
    if (
        record.get("schema_version") != RECORD_SCHEMA_VERSION
        or record.get("model_role") != MODEL_ROLE
        or record.get("record_id") != _record_id(record)
    ):
        raise GeminiAdaptiveQueryStoreV1Error(
            "Gemini adaptive record identity drift"
        )
    public_record = copy.deepcopy(dict(record))
    public_record["schema_version"] = (
        "m3-paper-v2-gemini-experiment-record-1.0"
    )
    public_record["model_role"] = "second"
    public_record["record_id"] = _public_record_id(public_record)
    validate_gemini_experiment_record(
        public_record,
        online_projection=online_projection,
    )
    validate_persisted_ledger_value(record)


def assemble_adaptive_record(
    work_item: Mapping[str, Any],
    initial_online_state: Mapping[str, Any],
    execution_result: Mapping[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    public_item = copy.deepcopy(dict(work_item))
    public_item["provider_id"] = "gemini"
    public_item["model_id"] = "gemini-3.6-flash"
    public_item["model_role"] = "second"
    public_record = assemble_gemini_experiment_record(
        public_item,
        initial_online_state,
        execution_result,
        run_id=run_id,
    )
    record = copy.deepcopy(public_record)
    record["schema_version"] = RECORD_SCHEMA_VERSION
    record["model_role"] = MODEL_ROLE
    record["record_id"] = _record_id(record)
    projection = {
        "initial_online_state": copy.deepcopy(dict(initial_online_state)),
        "runtime_visibility_events": copy.deepcopy(
            execution_result["runtime_visibility_events"]
        ),
    }
    validate_adaptive_record(record, online_projection=projection)
    return record


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                raise GeminiAdaptiveQueryStoreV1Error(
                    f"{path}:{number}: blank row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise GeminiAdaptiveQueryStoreV1Error(
                    f"{path}:{number}: expected object"
                )
            rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiAdaptiveQueryStoreV1Error(
            f"{path}: invalid JSONL"
        ) from exc
    return rows


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def validate_events(
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    execution_identity: str,
    known_work_keys: set[str],
) -> dict[str, Any]:
    previous: str | None = None
    open_events: dict[str, Mapping[str, Any]] = {}
    terminal: dict[str, Mapping[str, Any]] = {}
    response_ids: set[str] = set()
    for sequence, item in enumerate(events, 1):
        event = dict(item)
        core = {key: child for key, child in event.items() if key != "event_sha256"}
        work_key = str(event.get("work_key", ""))
        if (
            event.get("schema_version") != EVENT_SCHEMA_VERSION
            or event.get("ledger_sequence") != sequence
            or event.get("previous_event_sha256") != previous
            or event.get("run_id") != run_id
            or event.get("execution_identity") != execution_identity
            or work_key not in known_work_keys
            or event.get("event_sha256") != sha256_canonical_json(core)
        ):
            raise GeminiAdaptiveQueryStoreV1Error(
                f"Gemini adaptive query event {sequence} envelope drift"
            )
        validate_persisted_ledger_value(event)
        query_index = event.get("query_index")
        if (
            isinstance(query_index, bool)
            or not isinstance(query_index, int)
            or query_index < 1
            or not str(event.get("case_id", ""))
        ):
            raise GeminiAdaptiveQueryStoreV1Error(
                "Gemini adaptive query identity is invalid"
            )
        _assert_sha256(event.get("prompt_sha256"), field="prompt_sha256")
        if event.get("event_type") == "started":
            if work_key in open_events or work_key in terminal:
                raise GeminiAdaptiveQueryStoreV1Error(
                    "Gemini adaptive query start is duplicated"
                )
            if set(event) != {
                "schema_version",
                "ledger_sequence",
                "previous_event_sha256",
                "run_id",
                "execution_identity",
                "work_key",
                "case_id",
                "query_index",
                "prompt_sha256",
                "event_type",
                "recorded_at",
                "event_sha256",
            }:
                raise GeminiAdaptiveQueryStoreV1Error(
                    "Gemini adaptive started fields drift"
                )
            open_events[work_key] = event
        elif event.get("event_type") == "terminal":
            start = open_events.get(work_key)
            record = event.get("record")
            online_evidence = event.get("online_evidence")
            runtime_events = (
                online_evidence.get("runtime_visibility_events")
                if isinstance(online_evidence, Mapping)
                else None
            )
            if (
                start is None
                or work_key in terminal
                or set(event)
                != {
                    "schema_version",
                    "ledger_sequence",
                    "previous_event_sha256",
                    "run_id",
                    "execution_identity",
                    "work_key",
                    "case_id",
                    "query_index",
                    "prompt_sha256",
                    "event_type",
                    "result_tier",
                    "record_sha256",
                    "record",
                    "online_evidence_sha256",
                    "online_evidence",
                    "provider_call_count",
                    "provider_request_count",
                    "provider_response_id_sequence_sha256",
                    "recorded_at",
                    "event_sha256",
                }
                or not isinstance(record, Mapping)
                or not isinstance(online_evidence, Mapping)
                or not isinstance(runtime_events, list)
                or start.get("case_id") != event.get("case_id")
                or start.get("query_index") != event.get("query_index")
                or start.get("prompt_sha256") != event.get("prompt_sha256")
                or event.get("record_sha256") != sha256_canonical_json(record)
                or event.get("online_evidence_sha256")
                != sha256_canonical_json(online_evidence)
                or set(online_evidence)
                != {
                    "online_visible_field_digest",
                    "runtime_visibility_events",
                }
                or online_evidence.get("online_visible_field_digest")
                != record.get("online_visible_field_digest")
            ):
                raise GeminiAdaptiveQueryStoreV1Error(
                    "Gemini adaptive terminal binding drift"
                )
            _validate_sanitized_events(runtime_events)
            _assert_sha256(event.get("record_sha256"), field="record_sha256")
            _assert_sha256(
                event.get("online_evidence_sha256"),
                field="online_evidence_sha256",
            )
            _assert_sha256(
                event.get("provider_response_id_sequence_sha256"),
                field="provider_response_id_sequence_sha256",
            )
            validate_adaptive_record(record)
            bundle = validate_trace_bundle(record["provider_trace_bundle"])
            ids = [
                str(evidence["provider_response_id"])
                for evidence in bundle["usage_evidence"]
            ]
            if (
                event.get("result_tier") != record["result_tier"]
                or event.get("provider_call_count")
                != bundle["completed_request_count"]
                or event.get("provider_request_count") != bundle["request_count"]
                or event.get("provider_response_id_sequence_sha256")
                != sha256_canonical_json(ids)
                or response_ids.intersection(ids)
            ):
                raise GeminiAdaptiveQueryStoreV1Error(
                    "Gemini adaptive provider binding drift"
                )
            response_ids.update(ids)
            terminal[work_key] = event
            del open_events[work_key]
        else:
            raise GeminiAdaptiveQueryStoreV1Error(
                "Gemini adaptive event type is unsupported"
            )
        previous = str(event["event_sha256"])
    terminal_events = list(terminal.values())
    return {
        "event_count": len(events),
        "started_query_count": len(terminal) + len(open_events),
        "terminal_query_count": len(terminal),
        "formal_candidate_query_count": sum(
            event["result_tier"] == "formal_candidate"
            for event in terminal_events
        ),
        "diagnostic_query_count": sum(
            event["result_tier"] == "diagnostic" for event in terminal_events
        ),
        "completed_provider_call_count": sum(
            int(event["provider_call_count"]) for event in terminal_events
        ),
        "attempted_provider_request_count": sum(
            int(event["provider_request_count"]) for event in terminal_events
        ),
        "open_query_work_keys": sorted(open_events),
        "terminal_query_work_keys": sorted(terminal),
        "provider_response_id_count": len(response_ids),
        "tail_sha256": previous,
        "scientific_outcomes_aggregated": False,
    }


class GeminiAdaptiveQueryLedger:
    """Small append-only ledger for one quota-day execution identity."""

    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        execution_identity: str,
        known_work_keys: set[str],
    ) -> None:
        self.path = path
        self.run_id = run_id
        self.execution_identity = execution_identity
        self.known_work_keys = set(known_work_keys)
        self.events = _read_jsonl(path)
        self.status = validate_events(
            self.events,
            run_id=run_id,
            execution_identity=execution_identity,
            known_work_keys=self.known_work_keys,
        )

    def _append(self, core: Mapping[str, Any]) -> dict[str, Any]:
        event = {**dict(core), "event_sha256": sha256_canonical_json(core)}
        _append_jsonl(self.path, event)
        self.events.append(event)
        self.status = validate_events(
            self.events,
            run_id=self.run_id,
            execution_identity=self.execution_identity,
            known_work_keys=self.known_work_keys,
        )
        return copy.deepcopy(event)

    def append_started(
        self,
        *,
        work_key: str,
        case_id: str,
        query_index: int,
        prompt_sha256: str,
        recorded_at: str,
    ) -> dict[str, Any]:
        if self.status["open_query_work_keys"]:
            raise GeminiAdaptiveQueryStoreV1Error(
                "another Gemini adaptive query is open"
            )
        core = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "ledger_sequence": len(self.events) + 1,
            "previous_event_sha256": self.status["tail_sha256"],
            "run_id": self.run_id,
            "execution_identity": self.execution_identity,
            "work_key": work_key,
            "case_id": case_id,
            "query_index": query_index,
            "prompt_sha256": prompt_sha256,
            "event_type": "started",
            "recorded_at": recorded_at,
        }
        return self._append(core)

    def append_terminal(
        self,
        *,
        work_key: str,
        case_id: str,
        query_index: int,
        prompt_sha256: str,
        record: Mapping[str, Any],
        initial_online_state: Mapping[str, Any],
        runtime_visibility_events: Sequence[Mapping[str, Any]],
        recorded_at: str,
    ) -> dict[str, Any]:
        bundle = validate_trace_bundle(record["provider_trace_bundle"])
        ids = [
            str(evidence["provider_response_id"])
            for evidence in bundle["usage_evidence"]
        ]
        full_projection = {
            "initial_online_state": copy.deepcopy(dict(initial_online_state)),
            "runtime_visibility_events": copy.deepcopy(
                [dict(event) for event in runtime_visibility_events]
            ),
        }
        validate_adaptive_record(record, online_projection=full_projection)
        _validate_sanitized_events(full_projection["runtime_visibility_events"])
        online_evidence = {
            "online_visible_field_digest": record["online_visible_field_digest"],
            "runtime_visibility_events": full_projection[
                "runtime_visibility_events"
            ],
        }
        core = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "ledger_sequence": len(self.events) + 1,
            "previous_event_sha256": self.status["tail_sha256"],
            "run_id": self.run_id,
            "execution_identity": self.execution_identity,
            "work_key": work_key,
            "case_id": case_id,
            "query_index": query_index,
            "prompt_sha256": prompt_sha256,
            "event_type": "terminal",
            "result_tier": record["result_tier"],
            "record_sha256": sha256_canonical_json(record),
            "record": copy.deepcopy(dict(record)),
            "online_evidence_sha256": sha256_canonical_json(online_evidence),
            "online_evidence": online_evidence,
            "provider_call_count": bundle["completed_request_count"],
            "provider_request_count": bundle["request_count"],
            "provider_response_id_sequence_sha256": sha256_canonical_json(ids),
            "recorded_at": recorded_at,
        }
        return self._append(core)

    def full_validate(self) -> dict[str, Any]:
        observed = _read_jsonl(self.path)
        status = validate_events(
            observed,
            run_id=self.run_id,
            execution_identity=self.execution_identity,
            known_work_keys=self.known_work_keys,
        )
        if observed != self.events or status != self.status:
            raise GeminiAdaptiveQueryStoreV1Error(
                "Gemini adaptive incremental state differs from full replay"
            )
        return status


__all__ = [
    "GeminiAdaptiveQueryLedger",
    "GeminiAdaptiveQueryStoreV1Error",
    "assemble_adaptive_record",
    "validate_adaptive_record",
    "validate_events",
]
