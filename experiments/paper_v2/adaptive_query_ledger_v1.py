"""Append-only query ledger and provider-call cross-binding for adaptive v1."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_record_store import (
    validate_persisted_ledger_value,
)
from experiments.paper_v2.public_execution_store_v1 import (
    cross_bind_public_budget_and_records,
    validate_public_experiment_record,
)
from experiments.paper_v2.public_provider_trace_v1 import (
    validate_public_trace_bundle,
)


SCHEMA_VERSION = "m3-paper-v2-adaptive-query-ledger-event-1.0"


class AdaptiveQueryLedgerError(ValueError):
    """Raised when an adaptive query chain is incomplete or inconsistent."""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, start=1):
                if not line.strip():
                    raise AdaptiveQueryLedgerError(
                        f"{path}:{number}: blank ledger row"
                    )
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise AdaptiveQueryLedgerError(
                        f"{path}:{number}: expected an object"
                    )
                rows.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveQueryLedgerError(
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


def _event_core(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: child
        for key, child in value.items()
        if key != "event_sha256"
    }


def _assert_sha256(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise AdaptiveQueryLedgerError(f"{field} must be lowercase SHA-256")
    return value


def validate_query_events(
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    execution_identity: str,
    known_work_keys: set[str],
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the technical chain without aggregating scientific outcomes."""

    previous: str | None = None
    open_queries: dict[str, Mapping[str, Any]] = {}
    terminal: dict[str, Mapping[str, Any]] = {}
    for sequence, event in enumerate(events, start=1):
        if (
            not isinstance(event, Mapping)
            or event.get("schema_version") != SCHEMA_VERSION
            or event.get("ledger_sequence") != sequence
            or event.get("previous_event_sha256") != previous
            or event.get("run_id") != run_id
            or event.get("execution_identity") != execution_identity
            or event.get("event_sha256")
            != sha256_canonical_json(_event_core(event))
        ):
            raise AdaptiveQueryLedgerError(
                f"adaptive query event {sequence} identity/hash drift"
            )
        validate_persisted_ledger_value(event)
        work_key = str(event.get("work_key", ""))
        if work_key not in known_work_keys:
            raise AdaptiveQueryLedgerError(
                f"adaptive query event {sequence} has an unknown work key"
            )
        event_type = event.get("event_type")
        query_index = event.get("query_index")
        if (
            isinstance(query_index, bool)
            or not isinstance(query_index, int)
            or query_index < 1
        ):
            raise AdaptiveQueryLedgerError("adaptive query index is invalid")
        _assert_sha256(
            event.get("prompt_sha256"),
            field="prompt_sha256",
        )
        if event_type == "started":
            if work_key in open_queries or work_key in terminal:
                raise AdaptiveQueryLedgerError(
                    "adaptive query start is duplicated"
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
                raise AdaptiveQueryLedgerError(
                    "adaptive query start fields drift"
                )
            open_queries[work_key] = event
        elif event_type == "terminal":
            start = open_queries.get(work_key)
            if start is None or work_key in terminal:
                raise AdaptiveQueryLedgerError(
                    "adaptive query terminal lacks one open start"
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
                "result_tier",
                "record_sha256",
                "record",
                "provider_call_count",
                "provider_response_id_sequence_sha256",
                "recorded_at",
                "event_sha256",
            }:
                raise AdaptiveQueryLedgerError(
                    "adaptive query terminal fields drift"
                )
            if (
                start["case_id"] != event.get("case_id")
                or start["query_index"] != query_index
                or start["prompt_sha256"] != event.get("prompt_sha256")
            ):
                raise AdaptiveQueryLedgerError(
                    "adaptive query terminal/start drift"
                )
            record = event.get("record")
            if not isinstance(record, Mapping):
                raise AdaptiveQueryLedgerError(
                    "adaptive query terminal record is missing"
                )
            _assert_sha256(
                event.get("record_sha256"),
                field="record_sha256",
            )
            if event["record_sha256"] != sha256_canonical_json(record):
                raise AdaptiveQueryLedgerError(
                    "adaptive query record digest drift"
                )
            validate_public_experiment_record(
                record,
                role_policy=role_policy,
            )
            bundle = validate_public_trace_bundle(
                record["provider_trace_bundle"],
                role_policy=role_policy,
            )
            response_ids = [
                str(item["provider_response_id"])
                for item in bundle["usage_evidence"]
            ]
            expected_call_digest = sha256_canonical_json(response_ids)
            if (
                bundle["work_key"] != work_key
                or event.get("result_tier") != record["result_tier"]
                or event.get("provider_call_count")
                != bundle["completed_request_count"]
                or event.get("provider_response_id_sequence_sha256")
                != expected_call_digest
            ):
                raise AdaptiveQueryLedgerError(
                    "adaptive query/provider-call binding drift"
                )
            terminal[work_key] = event
            del open_queries[work_key]
        else:
            raise AdaptiveQueryLedgerError(
                "adaptive query event type is unsupported"
            )
        previous = str(event["event_sha256"])
    return {
        "event_count": len(events),
        "started_query_count": len(terminal) + len(open_queries),
        "terminal_query_count": len(terminal),
        "formal_candidate_query_count": sum(
            event["result_tier"] == "formal_candidate"
            for event in terminal.values()
        ),
        "diagnostic_query_count": sum(
            event["result_tier"] == "diagnostic"
            for event in terminal.values()
        ),
        "completed_provider_call_count": sum(
            int(event["provider_call_count"])
            for event in terminal.values()
        ),
        "open_query_work_keys": sorted(open_queries),
        "terminal_query_work_keys": sorted(terminal),
        "tail_sha256": previous,
        "hash_chain_complete": True,
        "scientific_outcomes_aggregated": False,
    }


class AdaptiveQueryLedger:
    """Fsynced query ledger with a started-before-provider invariant."""

    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        execution_identity: str,
        known_work_keys: set[str],
        role_policy: Mapping[str, Any],
    ) -> None:
        self.path = path
        self.run_id = run_id
        self.execution_identity = execution_identity
        self.known_work_keys = set(known_work_keys)
        self.role_policy = copy.deepcopy(dict(role_policy))
        self.events = _load_jsonl(path)
        self.status = validate_query_events(
            self.events,
            run_id=run_id,
            execution_identity=execution_identity,
            known_work_keys=self.known_work_keys,
            role_policy=self.role_policy,
        )

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
            raise AdaptiveQueryLedgerError(
                "an open adaptive query requires manual review"
            )
        if work_key in self.status["terminal_query_work_keys"]:
            raise AdaptiveQueryLedgerError(
                "adaptive query is already terminal"
            )
        core = {
            "schema_version": SCHEMA_VERSION,
            "ledger_sequence": len(self.events) + 1,
            "previous_event_sha256": self.status["tail_sha256"],
            "run_id": self.run_id,
            "execution_identity": self.execution_identity,
            "work_key": work_key,
            "case_id": case_id,
            "query_index": query_index,
            "prompt_sha256": _assert_sha256(
                prompt_sha256,
                field="prompt_sha256",
            ),
            "event_type": "started",
            "recorded_at": recorded_at,
        }
        event = {**core, "event_sha256": sha256_canonical_json(core)}
        candidate = [*self.events, event]
        status = validate_query_events(
            candidate,
            run_id=self.run_id,
            execution_identity=self.execution_identity,
            known_work_keys=self.known_work_keys,
            role_policy=self.role_policy,
        )
        _append_fsynced(self.path, event)
        self.events = candidate
        self.status = status
        return copy.deepcopy(event)

    def append_terminal(
        self,
        *,
        work_key: str,
        case_id: str,
        query_index: int,
        prompt_sha256: str,
        record: Mapping[str, Any],
        recorded_at: str,
    ) -> dict[str, Any]:
        bundle = validate_public_trace_bundle(
            record["provider_trace_bundle"],
            role_policy=self.role_policy,
        )
        response_ids = [
            str(item["provider_response_id"])
            for item in bundle["usage_evidence"]
        ]
        core = {
            "schema_version": SCHEMA_VERSION,
            "ledger_sequence": len(self.events) + 1,
            "previous_event_sha256": self.status["tail_sha256"],
            "run_id": self.run_id,
            "execution_identity": self.execution_identity,
            "work_key": work_key,
            "case_id": case_id,
            "query_index": query_index,
            "prompt_sha256": _assert_sha256(
                prompt_sha256,
                field="prompt_sha256",
            ),
            "event_type": "terminal",
            "result_tier": record["result_tier"],
            "record_sha256": sha256_canonical_json(record),
            "record": copy.deepcopy(dict(record)),
            "provider_call_count": bundle["completed_request_count"],
            "provider_response_id_sequence_sha256": (
                sha256_canonical_json(response_ids)
            ),
            "recorded_at": recorded_at,
        }
        event = {**core, "event_sha256": sha256_canonical_json(core)}
        candidate = [*self.events, event]
        status = validate_query_events(
            candidate,
            run_id=self.run_id,
            execution_identity=self.execution_identity,
            known_work_keys=self.known_work_keys,
            role_policy=self.role_policy,
        )
        _append_fsynced(self.path, event)
        self.events = candidate
        self.status = status
        return copy.deepcopy(event)


def terminal_query_records(
    events: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "work_key": str(event["work_key"]),
            "record": copy.deepcopy(dict(event["record"])),
        }
        for event in events
        if event.get("event_type") == "terminal"
    ]


def cross_bind_query_and_call_ledgers(
    *,
    query_events: Sequence[Mapping[str, Any]],
    budget_events: Sequence[Mapping[str, Any]],
    trace_root: Path,
    role_policy: Mapping[str, Any],
) -> None:
    """Prove that every completed provider call belongs to one query."""

    cross_bind_public_budget_and_records(
        budget_events=budget_events,
        record_entries=terminal_query_records(query_events),
        trace_root=trace_root,
        role_policy=role_policy,
    )


__all__ = [
    "AdaptiveQueryLedger",
    "AdaptiveQueryLedgerError",
    "SCHEMA_VERSION",
    "cross_bind_query_and_call_ledgers",
    "terminal_query_records",
    "validate_query_events",
]
