"""Append-only cross-binding for Gemini paper-v2 experiment evidence.

The generic paper-v2 record contract intentionally stores only the final
provider attestation.  This sidecar binds every Gemini call receipt and the
provider safety receipt to the corresponding hash-chained experiment record.
It stores no prompt, response text, request header, or credential value.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    provider_receipt_to_attestation,
    validate_call_events,
    validate_provider_receipt,
)
from experiments.paper_v2.provider_safety import validate_safety_receipt


SCHEMA_VERSION = "m3-paper-v2-gemini-evidence-entry-1.0"
ENTRY_FIELDS = frozenset(
    {
        "schema_version",
        "ledger_sequence",
        "previous_entry_sha256",
        "execution_identity",
        "run_id",
        "work_key",
        "record_entry_sha256",
        "record_sha256",
        "result_tier",
        "operational_status",
        "call_event_first_sequence",
        "call_event_last_sequence",
        "provider_call_count",
        "completed_call_count",
        "provider_receipt_sha256s",
        "provider_receipt_evidence_sha256s",
        "provider_request_ids",
        "provider_response_ids",
        "usage",
        "provider_safety_receipt",
        "provider_safety_receipt_sha256",
        "recorded_at",
        "entry_sha256",
    }
)


class GeminiEvidenceStoreError(ValueError):
    """Raised when the Gemini evidence sidecar is incomplete or inconsistent."""


def _canonical_line(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _without_digest(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "entry_sha256"
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    raise GeminiEvidenceStoreError(
                        f"{path}:{line_number}: blank ledger row"
                    )
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise GeminiEvidenceStoreError(
                        f"{path}:{line_number}: expected an object"
                    )
                rows.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiEvidenceStoreError(
            f"{path}: invalid UTF-8 JSONL"
        ) from exc
    return rows


def load_evidence_entries(path: Path) -> list[dict[str, Any]]:
    """Load the sidecar without weakening validation at the caller."""

    return _load_jsonl(path)


def _completed_call_events(
    call_events: Sequence[Mapping[str, Any]],
    work_key: str,
) -> list[Mapping[str, Any]]:
    return [
        event
        for event in call_events
        if event.get("work_key") == work_key
        and event.get("event_type") == "completed"
    ]


def _all_call_events(
    call_events: Sequence[Mapping[str, Any]],
    work_key: str,
) -> list[tuple[int, Mapping[str, Any]]]:
    return [
        (index, event)
        for index, event in enumerate(call_events, start=1)
        if event.get("work_key") == work_key
    ]


def _usage(
    completed: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    result = {
        "requests": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    for event in completed:
        receipt = event.get("receipt")
        if not isinstance(receipt, Mapping):
            raise GeminiEvidenceStoreError(
                "completed provider call lacks a receipt"
            )
        validate_provider_receipt(receipt)
        raw = receipt["evidence"].get("usage")
        if not isinstance(raw, Mapping):
            raise GeminiEvidenceStoreError(
                "completed provider receipt lacks usage"
            )
        result["requests"] += 1
        result["prompt_tokens"] += int(raw["prompt_tokens"])
        result["completion_tokens"] += int(raw["completion_tokens"])
        result["total_tokens"] += int(raw["total_tokens"])
    return result


def build_evidence_entry(
    *,
    ledger_sequence: int,
    previous_entry_sha256: str | None,
    execution_identity: str,
    run_id: str,
    record_entry: Mapping[str, Any],
    execution_result: Mapping[str, Any],
    call_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one sidecar row from an already fsynced experiment record."""

    if ledger_sequence < 1:
        raise GeminiEvidenceStoreError(
            "ledger_sequence must be positive"
        )
    record = record_entry.get("record")
    if not isinstance(record, Mapping):
        raise GeminiEvidenceStoreError(
            "record entry lacks an experiment record"
        )
    work_key = str(record_entry.get("work_key", ""))
    if not work_key:
        raise GeminiEvidenceStoreError("record entry lacks a work key")
    safety = execution_result.get("safety_receipt")
    if not isinstance(safety, Mapping):
        raise GeminiEvidenceStoreError(
            "Gemini execution result lacks a safety receipt"
        )
    validate_safety_receipt(safety)
    work_calls = _all_call_events(call_events, work_key)
    completed = _completed_call_events(call_events, work_key)
    receipts = [event["receipt"] for event in completed]
    for receipt in receipts:
        validate_provider_receipt(receipt)
        if receipt["evidence"].get("provider_id") != "gemini":
            raise GeminiEvidenceStoreError(
                "cross-provider receipt in Gemini evidence"
            )
    if record.get("result_tier") == "formal_candidate" and not completed:
        raise GeminiEvidenceStoreError(
            "formal-candidate record lacks a completed Gemini call"
        )
    if completed:
        expected_attestation = provider_receipt_to_attestation(receipts[-1])
        if dict(record["provider_attestation"]) != expected_attestation:
            raise GeminiEvidenceStoreError(
                "record attestation does not match the last Gemini receipt"
            )
    elif record["provider_attestation"].get("response_id") is not None:
        raise GeminiEvidenceStoreError(
            "record claims a response without a completed Gemini receipt"
        )

    request_ids = [
        str(receipt["evidence"]["request_id"])
        for receipt in receipts
        if receipt["evidence"].get("request_id")
    ]
    response_ids = [
        str(receipt["evidence"]["response_id"])
        for receipt in receipts
        if receipt["evidence"].get("response_id")
    ]
    core = {
        "schema_version": SCHEMA_VERSION,
        "ledger_sequence": ledger_sequence,
        "previous_entry_sha256": previous_entry_sha256,
        "execution_identity": execution_identity,
        "run_id": run_id,
        "work_key": work_key,
        "record_entry_sha256": str(record_entry["entry_sha256"]),
        "record_sha256": str(record_entry["record_sha256"]),
        "result_tier": str(record["result_tier"]),
        "operational_status": str(record["operational_status"]),
        "call_event_first_sequence": (
            work_calls[0][0] if work_calls else None
        ),
        "call_event_last_sequence": (
            work_calls[-1][0] if work_calls else None
        ),
        "provider_call_count": len(work_calls) // 2,
        "completed_call_count": len(completed),
        "provider_receipt_sha256s": [
            sha256_canonical_json(receipt) for receipt in receipts
        ],
        "provider_receipt_evidence_sha256s": [
            str(receipt["evidence_sha256"]) for receipt in receipts
        ],
        "provider_request_ids": request_ids,
        "provider_response_ids": response_ids,
        "usage": _usage(completed),
        "provider_safety_receipt": copy.deepcopy(dict(safety)),
        "provider_safety_receipt_sha256": sha256_canonical_json(safety),
        "recorded_at": str(execution_result["recorded_at"]),
    }
    return {**core, "entry_sha256": sha256_canonical_json(core)}


def validate_evidence_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    record_entries: Sequence[Mapping[str, Any]],
    call_events: Sequence[Mapping[str, Any]],
    execution_identity: str,
    run_id: str,
    model_id: str,
) -> dict[str, Any]:
    """Validate every record/call/safety cross-binding."""

    call_status = validate_call_events(
        call_events,
        execution_identity=execution_identity,
        provider_id="gemini",
        model_id=model_id,
    )
    if len(entries) > len(record_entries):
        raise GeminiEvidenceStoreError(
            "evidence sidecar has more rows than the record ledger"
        )
    previous: str | None = None
    seen_work_keys: set[str] = set()
    seen_request_ids: set[str] = set()
    seen_response_ids: set[str] = set()
    total_usage = {
        "requests": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    for sequence, entry in enumerate(entries, start=1):
        if not isinstance(entry, Mapping) or set(entry) != ENTRY_FIELDS:
            raise GeminiEvidenceStoreError(
                f"evidence entry {sequence} fields drift"
            )
        if (
            entry["schema_version"] != SCHEMA_VERSION
            or entry["ledger_sequence"] != sequence
            or entry["previous_entry_sha256"] != previous
            or entry["execution_identity"] != execution_identity
            or entry["run_id"] != run_id
            or entry["entry_sha256"]
            != sha256_canonical_json(_without_digest(entry))
        ):
            raise GeminiEvidenceStoreError(
                f"evidence entry {sequence} identity/hash drift"
            )
        record_entry = record_entries[sequence - 1]
        record = record_entry["record"]
        if (
            entry["work_key"] != record_entry["work_key"]
            or entry["record_entry_sha256"]
            != record_entry["entry_sha256"]
            or entry["record_sha256"] != record_entry["record_sha256"]
            or entry["result_tier"] != record["result_tier"]
            or entry["operational_status"] != record["operational_status"]
        ):
            raise GeminiEvidenceStoreError(
                f"evidence entry {sequence} record binding drift"
            )
        work_key = str(entry["work_key"])
        if work_key in seen_work_keys:
            raise GeminiEvidenceStoreError(
                "duplicate Gemini evidence work key"
            )
        seen_work_keys.add(work_key)
        safety = entry["provider_safety_receipt"]
        validate_safety_receipt(safety)
        if entry["provider_safety_receipt_sha256"] != (
            sha256_canonical_json(safety)
        ):
            raise GeminiEvidenceStoreError(
                "Gemini safety receipt hash drift"
            )
        rebuilt = build_evidence_entry(
            ledger_sequence=sequence,
            previous_entry_sha256=previous,
            execution_identity=execution_identity,
            run_id=run_id,
            record_entry=record_entry,
            execution_result={
                "safety_receipt": safety,
                "recorded_at": entry["recorded_at"],
            },
            call_events=call_events,
        )
        if dict(entry) != rebuilt:
            raise GeminiEvidenceStoreError(
                f"evidence entry {sequence} does not reproduce"
            )
        request_ids = set(str(item) for item in entry["provider_request_ids"])
        response_ids = set(
            str(item) for item in entry["provider_response_ids"]
        )
        if (
            len(request_ids) != len(entry["provider_request_ids"])
            or len(response_ids) != len(entry["provider_response_ids"])
            or seen_request_ids & request_ids
            or seen_response_ids & response_ids
        ):
            raise GeminiEvidenceStoreError(
                "Gemini provider request/response identity was reused"
            )
        seen_request_ids.update(request_ids)
        seen_response_ids.update(response_ids)
        for key in total_usage:
            total_usage[key] += int(entry["usage"][key])
        previous = str(entry["entry_sha256"])
    return {
        "entry_count": len(entries),
        "work_keys": sorted(seen_work_keys),
        "tail_sha256": previous,
        "call_status": call_status,
        "usage": total_usage,
    }


def append_evidence_entry(
    path: Path,
    *,
    record_entries: Sequence[Mapping[str, Any]],
    execution_result: Mapping[str, Any],
    call_events: Sequence[Mapping[str, Any]],
    execution_identity: str,
    run_id: str,
    model_id: str,
) -> dict[str, Any]:
    """Append and fsync one sidecar row after validating the full candidate."""

    prior = load_evidence_entries(path)
    validate_evidence_entries(
        prior,
        record_entries=record_entries,
        call_events=call_events,
        execution_identity=execution_identity,
        run_id=run_id,
        model_id=model_id,
    )
    if len(record_entries) != len(prior) + 1:
        raise GeminiEvidenceStoreError(
            "exactly one fsynced record must precede a sidecar append"
        )
    entry = build_evidence_entry(
        ledger_sequence=len(prior) + 1,
        previous_entry_sha256=(
            str(prior[-1]["entry_sha256"]) if prior else None
        ),
        execution_identity=execution_identity,
        run_id=run_id,
        record_entry=record_entries[-1],
        execution_result=execution_result,
        call_events=call_events,
    )
    candidate = [*prior, entry]
    summary = validate_evidence_entries(
        candidate,
        record_entries=record_entries,
        call_events=call_events,
        execution_identity=execution_identity,
        run_id=run_id,
        model_id=model_id,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(_canonical_line(entry) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return summary


__all__ = [
    "GeminiEvidenceStoreError",
    "SCHEMA_VERSION",
    "append_evidence_entry",
    "build_evidence_entry",
    "load_evidence_entries",
    "validate_evidence_entries",
]
