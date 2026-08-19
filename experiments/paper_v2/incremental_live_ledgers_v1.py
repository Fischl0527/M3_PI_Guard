"""Incremental appenders for already-validated live evidence prefixes.

The original ledger helpers intentionally replay the complete append-only
chain before and after every append.  That is useful for small canaries but
quadratic for public-scale continuations.  These helpers preserve a stricter
execution boundary:

1. replay and validate the complete prefix once at construction;
2. validate and fsync exactly one new event at a time;
3. require a complete replay again before technical admission.

They do not weaken the persisted schemas or the terminal review requirements.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping, Sequence

import experiments.paper_v2.adaptive_query_ledger_v1 as adaptive_ledger
import experiments.paper_v2.formal_matrix_controller_v1 as matrix_v1
import experiments.paper_v2.public_execution_store_v1 as public_store
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_record_store import (
    _validate_sanitized_events,
    validate_persisted_ledger_value,
)
from experiments.paper_v2.formal_record_store_v2 import (
    ENTRY_SCHEMA_VERSION,
)
from experiments.paper_v2.official_provider_executor import (
    OfficialProviderCompletion,
    ProviderPausedError,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    PublicBudgetPolicyError,
    check_role_headroom,
    role_cost_cny,
)
from experiments.paper_v2.public_provider_trace_v1 import (
    validate_public_trace_bundle,
)


class IncrementalLiveLedgerError(ValueError):
    """Raised when an incremental append would leave a valid frozen prefix."""


class IncrementalPublicBudgetTracker:
    """Public budget tracker with one full prefix replay per process."""

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
        self.events = public_store._load_jsonl(path)
        self.status = public_store.validate_public_budget_events(
            self.events,
            run_id=run_id,
            execution_identity=execution_identity,
            model_role=model_role,
            known_work_keys=self.known_work_keys,
            role_policy=self.role_policy,
        )
        self._response_ids = set(self.status["provider_response_ids"])

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
        self.assert_before_request()
        if work_key not in self.known_work_keys:
            raise IncrementalLiveLedgerError("unknown public budget work key")
        if (
            isinstance(call_index, bool)
            or not isinstance(call_index, int)
            or call_index < 1
        ):
            raise IncrementalLiveLedgerError("invalid public call index")
        evidence = completion.receipt.get("evidence")
        if not isinstance(evidence, Mapping):
            raise IncrementalLiveLedgerError(
                "public completion lacks provider evidence"
            )
        usage_raw = evidence.get("usage")
        if not isinstance(usage_raw, Mapping):
            raise IncrementalLiveLedgerError(
                "public completion lacks provider usage"
            )
        usage = public_store._normalized_usage(usage_raw)
        response_id = evidence.get("response_id")
        if (
            not isinstance(response_id, str)
            or not response_id
            or response_id in self._response_ids
        ):
            raise IncrementalLiveLedgerError(
                "public response identity is missing or reused"
            )
        cumulative = public_store._add_usage(
            self.status["role_cumulative_usage"],
            usage,
        )
        budget_status = "continue"
        try:
            check_role_headroom(self.role_policy, cumulative)
        except PublicBudgetPolicyError:
            budget_status = "pause_before_next_request"
        core = {
            "schema_version": public_store.BUDGET_EVENT_SCHEMA,
            "ledger_sequence": len(self.events) + 1,
            "previous_event_sha256": self.status["tail_sha256"],
            "run_id": self.run_id,
            "execution_identity": self.execution_identity,
            "model_role": self.model_role,
            "work_key": work_key,
            "call_index": call_index,
            "provider_response_id": response_id,
            "usage": usage,
            "request_cost_cny": role_cost_cny(self.role_policy, usage),
            "role_cumulative_usage": cumulative,
            "role_cumulative_cost_cny": role_cost_cny(
                self.role_policy,
                cumulative,
            ),
            "budget_status_after_request": budget_status,
            "recorded_at": recorded_at,
        }
        event = {**core, "event_sha256": sha256_canonical_json(core)}
        validate_persisted_ledger_value(event)
        public_store._append_fsynced(self.path, event)
        self.events.append(event)
        self._response_ids.add(response_id)
        self.status = {
            "event_count": len(self.events),
            "role_cumulative_usage": cumulative,
            "role_cumulative_cost_cny": role_cost_cny(
                self.role_policy,
                cumulative,
            ),
            "paused": budget_status == "pause_before_next_request",
            "provider_response_ids": sorted(self._response_ids),
            "tail_sha256": event["event_sha256"],
        }
        return copy.deepcopy(event)

    def full_validate(self) -> dict[str, Any]:
        observed = public_store._load_jsonl(self.path)
        status = public_store.validate_public_budget_events(
            observed,
            run_id=self.run_id,
            execution_identity=self.execution_identity,
            model_role=self.model_role,
            known_work_keys=self.known_work_keys,
            role_policy=self.role_policy,
        )
        if observed != self.events or status != self.status:
            raise IncrementalLiveLedgerError(
                "incremental public budget state differs from full replay"
            )
        return status


class IncrementalAttemptLedger:
    """Started/terminal attempt appender over one validated prefix."""

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
        self.events = matrix_v1._load_jsonl(path)
        self.status = matrix_v1.validate_attempt_events(
            self.events,
            run_id=run_id,
            execution_identity=execution_identity,
            known_work_keys=self.known_work_keys,
        )
        self._started = set(self.status["started_work_keys"])
        self._terminal = set(self.status["terminal_by_work_key"])

    def append(
        self,
        *,
        work_key: str,
        event_type: str,
        record_entry_sha256: str | None,
        recorded_at: str | None = None,
    ) -> dict[str, Any]:
        if work_key not in self.known_work_keys:
            raise IncrementalLiveLedgerError("unknown attempt work key")
        if event_type == "started":
            if work_key in self._started or work_key in self._terminal:
                raise IncrementalLiveLedgerError(
                    "public work item cannot start twice"
                )
            if record_entry_sha256 is not None:
                raise IncrementalLiveLedgerError(
                    "started attempt cannot bind a record"
                )
        elif event_type in {"completed", "diagnostic"}:
            if (
                work_key not in self._started
                or work_key in self._terminal
                or not isinstance(record_entry_sha256, str)
                or len(record_entry_sha256) != 64
            ):
                raise IncrementalLiveLedgerError(
                    "terminal attempt lacks one valid start"
                )
        else:
            raise IncrementalLiveLedgerError("unsupported attempt event")
        core = {
            "schema_version": matrix_v1.ATTEMPT_SCHEMA_VERSION,
            "ledger_sequence": len(self.events) + 1,
            "previous_event_sha256": self.status["tail_sha256"],
            "run_id": self.run_id,
            "execution_identity": self.execution_identity,
            "work_key": work_key,
            "attempt_id": matrix_v1._attempt_id(self.run_id, work_key),
            "event_type": event_type,
            "recorded_at": recorded_at or matrix_v1._now(),
            "record_entry_sha256": record_entry_sha256,
        }
        event = {**core, "event_sha256": matrix_v1._event_sha256(core)}
        validate_persisted_ledger_value(event)
        matrix_v1._append_fsynced(self.path, event)
        self.events.append(event)
        self._started.add(work_key)
        if event_type != "started":
            self._terminal.add(work_key)
        self.status = {
            "event_count": len(self.events),
            "started_work_keys": sorted(self._started),
            "terminal_by_work_key": {
                str(item["work_key"]): str(item["event_type"])
                for item in self.events
                if item["event_type"] in {"completed", "diagnostic"}
            },
            "open_work_keys": sorted(self._started - self._terminal),
            "tail_sha256": event["event_sha256"],
        }
        return copy.deepcopy(event)

    def full_validate(self) -> dict[str, Any]:
        observed = matrix_v1._load_jsonl(self.path)
        status = matrix_v1.validate_attempt_events(
            observed,
            run_id=self.run_id,
            execution_identity=self.execution_identity,
            known_work_keys=self.known_work_keys,
        )
        if observed != self.events or status != self.status:
            raise IncrementalLiveLedgerError(
                "incremental attempt state differs from full replay"
            )
        return status


class IncrementalPublicRecordLedger:
    """Public experiment-record appender over one validated prefix."""

    def __init__(
        self,
        path: Path,
        *,
        work_items: Sequence[Mapping[str, Any]],
        execution_identity: str,
        run_id: str,
        role_policy: Mapping[str, Any],
    ) -> None:
        self.path = path
        self.work_items = tuple(copy.deepcopy(dict(item)) for item in work_items)
        self.execution_identity = execution_identity
        self.run_id = run_id
        self.role_policy = copy.deepcopy(dict(role_policy))
        self.entries = public_store.load_public_record_entries(path)
        self.status = public_store.validate_public_record_entries(
            self.entries,
            work_items=self.work_items,
            execution_identity=execution_identity,
            run_id=run_id,
            role_policy=self.role_policy,
        )
        self._known = {str(item["work_key"]) for item in self.work_items}
        self._terminal = set(self.status["terminal_work_keys"])
        self._record_ids = {
            str(entry["record_id"]) for entry in self.entries
        }

    def append(
        self,
        *,
        work_item: Mapping[str, Any],
        initial_online_state: Mapping[str, Any],
        execution_result: Mapping[str, Any],
    ) -> dict[str, Any]:
        work_key = str(work_item.get("work_key", ""))
        if (
            work_key not in self._known
            or work_key in self._terminal
            or work_item.get("execution_identity")
            != self.execution_identity
        ):
            raise IncrementalLiveLedgerError(
                "public record work item is unknown, terminal, or drifted"
            )
        record = public_store.assemble_public_experiment_record(
            work_item,
            initial_online_state,
            execution_result,
            run_id=self.run_id,
            role_policy=self.role_policy,
        )
        record_id = str(record["record_id"])
        if record_id in self._record_ids:
            raise IncrementalLiveLedgerError(
                "public record identity is reused"
            )
        events = _validate_sanitized_events(
            execution_result["runtime_visibility_events"]
        )
        core = {
            "schema_version": ENTRY_SCHEMA_VERSION,
            "ledger_sequence": len(self.entries) + 1,
            "previous_entry_sha256": self.status["tail_sha256"],
            "execution_identity": self.execution_identity,
            "work_key": work_key,
            "run_id": self.run_id,
            "record_id": record_id,
            "record_sha256": sha256_canonical_json(record),
            "runtime_visibility_events_sha256": sha256_canonical_json(events),
            "record": record,
            "runtime_visibility_events": events,
        }
        entry = {**core, "entry_sha256": sha256_canonical_json(core)}
        validate_persisted_ledger_value(entry)
        public_store._append_fsynced(self.path, entry)
        self.entries.append(entry)
        self._terminal.add(work_key)
        self._record_ids.add(record_id)
        self.status = {
            "entry_count": len(self.entries),
            "terminal_work_keys": sorted(self._terminal),
            "remaining_work_items": len(self._known) - len(self._terminal),
            "tail_sha256": entry["entry_sha256"],
            "hash_chain_complete": True,
        }
        return copy.deepcopy(entry)

    def full_validate(self) -> dict[str, Any]:
        observed = public_store.load_public_record_entries(self.path)
        status = public_store.validate_public_record_entries(
            observed,
            work_items=self.work_items,
            execution_identity=self.execution_identity,
            run_id=self.run_id,
            role_policy=self.role_policy,
        )
        if observed != self.entries or status != self.status:
            raise IncrementalLiveLedgerError(
                "incremental public record state differs from full replay"
            )
        return status


class IncrementalAdaptiveQueryLedger:
    """Adaptive started/terminal appender over one validated prefix."""

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
        self.events = adaptive_ledger._load_jsonl(path)
        self.status = adaptive_ledger.validate_query_events(
            self.events,
            run_id=run_id,
            execution_identity=execution_identity,
            known_work_keys=self.known_work_keys,
            role_policy=self.role_policy,
        )
        self._terminal = set(self.status["terminal_query_work_keys"])
        self._open: dict[str, dict[str, Any]] = {
            str(event["work_key"]): copy.deepcopy(dict(event))
            for event in self.events
            if event["event_type"] == "started"
            and str(event["work_key"])
            not in self.status["terminal_query_work_keys"]
        }

    def _append_event(self, core: Mapping[str, Any]) -> dict[str, Any]:
        event = {**dict(core), "event_sha256": sha256_canonical_json(core)}
        validate_persisted_ledger_value(event)
        adaptive_ledger._append_fsynced(self.path, event)
        self.events.append(event)
        return event

    def append_started(
        self,
        *,
        work_key: str,
        case_id: str,
        query_index: int,
        prompt_sha256: str,
        recorded_at: str,
    ) -> dict[str, Any]:
        if (
            self._open
            or work_key not in self.known_work_keys
            or work_key in self._terminal
        ):
            raise IncrementalLiveLedgerError(
                "adaptive query cannot start from the current prefix"
            )
        prompt_sha = adaptive_ledger._assert_sha256(
            prompt_sha256,
            field="prompt_sha256",
        )
        core = {
            "schema_version": adaptive_ledger.SCHEMA_VERSION,
            "ledger_sequence": len(self.events) + 1,
            "previous_event_sha256": self.status["tail_sha256"],
            "run_id": self.run_id,
            "execution_identity": self.execution_identity,
            "work_key": work_key,
            "case_id": case_id,
            "query_index": query_index,
            "prompt_sha256": prompt_sha,
            "event_type": "started",
            "recorded_at": recorded_at,
        }
        event = self._append_event(core)
        self._open[work_key] = copy.deepcopy(event)
        self._refresh_status(event)
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
        start = self._open.get(work_key)
        if (
            start is None
            or start["case_id"] != case_id
            or start["query_index"] != query_index
            or start["prompt_sha256"] != prompt_sha256
        ):
            raise IncrementalLiveLedgerError(
                "adaptive terminal does not bind the open query"
            )
        public_store.validate_public_experiment_record(
            record,
            role_policy=self.role_policy,
        )
        bundle = validate_public_trace_bundle(
            record["provider_trace_bundle"],
            role_policy=self.role_policy,
        )
        response_ids = [
            str(item["provider_response_id"])
            for item in bundle["usage_evidence"]
        ]
        core = {
            "schema_version": adaptive_ledger.SCHEMA_VERSION,
            "ledger_sequence": len(self.events) + 1,
            "previous_event_sha256": self.status["tail_sha256"],
            "run_id": self.run_id,
            "execution_identity": self.execution_identity,
            "work_key": work_key,
            "case_id": case_id,
            "query_index": query_index,
            "prompt_sha256": adaptive_ledger._assert_sha256(
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
        event = self._append_event(core)
        del self._open[work_key]
        self._terminal.add(work_key)
        self._refresh_status(event)
        return copy.deepcopy(event)

    def _refresh_status(self, event: Mapping[str, Any]) -> None:
        terminal_events = [
            item for item in self.events if item["event_type"] == "terminal"
        ]
        self.status = {
            "event_count": len(self.events),
            "started_query_count": len(self._terminal) + len(self._open),
            "terminal_query_count": len(self._terminal),
            "formal_candidate_query_count": sum(
                item["result_tier"] == "formal_candidate"
                for item in terminal_events
            ),
            "diagnostic_query_count": sum(
                item["result_tier"] == "diagnostic"
                for item in terminal_events
            ),
            "completed_provider_call_count": sum(
                int(item["provider_call_count"])
                for item in terminal_events
            ),
            "open_query_work_keys": sorted(self._open),
            "terminal_query_work_keys": sorted(self._terminal),
            "tail_sha256": event["event_sha256"],
            "hash_chain_complete": True,
            "scientific_outcomes_aggregated": False,
        }

    def full_validate(self) -> dict[str, Any]:
        observed = adaptive_ledger._load_jsonl(self.path)
        status = adaptive_ledger.validate_query_events(
            observed,
            run_id=self.run_id,
            execution_identity=self.execution_identity,
            known_work_keys=self.known_work_keys,
            role_policy=self.role_policy,
        )
        if observed != self.events or status != self.status:
            raise IncrementalLiveLedgerError(
                "incremental adaptive query state differs from full replay"
            )
        return status


def full_cross_bind_public_prefix(
    *,
    budget_events: Sequence[Mapping[str, Any]],
    record_entries: Sequence[Mapping[str, Any]],
    trace_root: Path,
    role_policy: Mapping[str, Any],
) -> None:
    """Named terminal-review hook for a complete public prefix replay."""

    public_store.cross_bind_public_budget_and_records(
        budget_events=budget_events,
        record_entries=record_entries,
        trace_root=trace_root,
        role_policy=role_policy,
    )


__all__ = [
    "IncrementalAdaptiveQueryLedger",
    "IncrementalAttemptLedger",
    "IncrementalLiveLedgerError",
    "IncrementalPublicBudgetTracker",
    "IncrementalPublicRecordLedger",
    "full_cross_bind_public_prefix",
]
