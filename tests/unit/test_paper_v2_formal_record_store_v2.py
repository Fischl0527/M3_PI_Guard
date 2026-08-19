from __future__ import annotations

import copy

import pytest

from experiments.paper_v2.formal_record_store import (
    FormalRecordStoreError,
    _load_plan,
)
from experiments.paper_v2.formal_record_store_v2 import (
    _qualification_record,
    append_record_entry,
    build_qualification,
    load_record_entries,
    validate_record_entries,
)


def test_v2_record_store_qualification_is_local_and_complete() -> None:
    value = build_qualification()

    assert value["status"] == "offline_v2_record_store_qualified"
    assert value["transient_entries_written"] == 2
    assert value["completed_records_written"] == 1
    assert value["diagnostic_itt_failure_records_written"] == 1
    assert value["provider_safety_receipt_persisted"] is True
    assert value["hash_chain_complete"] is True
    assert value["append_flush_fsync"] is True
    assert value["negative_cases_rejected"] == 2
    assert value["v1_record_contract_modified"] is False
    assert value["v1_record_store_modified"] is False
    assert value["live_runtime_v2_wiring_qualified"] is False
    assert value["network_calls_made"] == 0
    assert value["formal_results_created"] == 0


def test_v2_record_store_appends_and_rejects_tamper(tmp_path) -> None:
    work_items = _load_plan()[:2]
    execution_identity = work_items[0]["execution_identity"]
    run_id = "test-v2-record-store"
    ledger = tmp_path / "records.jsonl"
    for index, item in enumerate(work_items, start=1):
        record, events = _qualification_record(
            tmp_path,
            item=item,
            run_id=run_id,
            index=index,
        )
        append_record_entry(
            ledger,
            work_items=work_items,
            work_item=item,
            record=record,
            runtime_visibility_events=events,
            execution_identity=execution_identity,
            run_id=run_id,
        )

    entries = load_record_entries(ledger)
    summary = validate_record_entries(
        entries,
        work_items=work_items,
        execution_identity=execution_identity,
        run_id=run_id,
    )
    assert summary["entry_count"] == 2
    assert summary["remaining_work_items"] == 0
    assert entries[1]["previous_entry_sha256"] == entries[0][
        "entry_sha256"
    ]

    tampered = copy.deepcopy(entries)
    tampered[0]["record"]["unsafe_effect"] = True
    with pytest.raises(FormalRecordStoreError, match="hash drift"):
        validate_record_entries(
            tampered,
            work_items=work_items,
            execution_identity=execution_identity,
            run_id=run_id,
        )


def test_v2_record_store_rejects_tail_without_genesis(tmp_path) -> None:
    work_items = _load_plan()[:2]
    execution_identity = work_items[0]["execution_identity"]
    run_id = "test-v2-truncation"
    ledger = tmp_path / "records.jsonl"
    entries = []
    for index, item in enumerate(work_items, start=1):
        record, events = _qualification_record(
            tmp_path,
            item=item,
            run_id=run_id,
            index=index,
        )
        entries.append(
            append_record_entry(
                ledger,
                work_items=work_items,
                work_item=item,
                record=record,
                runtime_visibility_events=events,
                execution_identity=execution_identity,
                run_id=run_id,
            )
        )
    with pytest.raises(FormalRecordStoreError, match="identity drift"):
        validate_record_entries(
            entries[1:],
            work_items=work_items,
            execution_identity=execution_identity,
            run_id=run_id,
        )
