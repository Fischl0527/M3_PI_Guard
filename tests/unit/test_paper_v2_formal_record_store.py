from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
    sanitize_runtime_events,
)
from experiments.paper_v2.formal_record_store import (
    DEFAULT_OUTPUT,
    FormalRecordStoreError,
    append_record_entry,
    build_record_entry,
    build_record_store_qualification,
    load_record_entries,
    pending_record_work_items,
    validate_record_entries,
)
from experiments.paper_v2.medium_runtime import (
    DEFAULT_V2_PLAN,
    reconstruct_initial_online_state,
)
from experiments.paper_v2.provider_safety import build_safety_receipt


RUN_ID = "paper-v2-record-store-test-run"


def _work_items() -> list[dict]:
    return [
        json.loads(line)
        for line in DEFAULT_V2_PLAN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _item() -> dict:
    return next(
        item
        for item in _work_items()
        if item["benchmark"] == "m3-v2"
        and item["condition_id"] == "m3_full"
        and item["authorization_regime"] == "auto_compiled"
    )


def _event() -> dict:
    return sanitize_runtime_events(
        [
            {
                "step": 1,
                "parse_ok": True,
                "parse_error_code": None,
                "tool": "final",
                "arguments": {"answer": "SAFE"},
                "decision": "ALLOW",
                "reason_code": "test_completed",
                "violated_constraints": [],
                "execution_attempted": True,
                "execution_succeeded": True,
                "response_text": "raw provider response",
                "observation": {"answer": "raw tool observation"},
                "provider_receipt_sha256": "a" * 64,
            }
        ]
    )[0]


def _stub_attestation() -> dict:
    return {
        "endpoint_type": "stub",
        "provider_name": "record-store-test-stub",
        "upstream_provider": None,
        "model_id": "deterministic-test",
        "model_revision": None,
        "request_id": None,
        "response_id": None,
        "requested_at": "2026-07-23T23:20:00+08:00",
        "parameters_sha256": "b" * 64,
        "prompt_rewrite_declaration": "not_applicable",
        "identity_evidence": "not_applicable",
        "identity_verified": False,
        "evidence_level": "stub_only",
    }


def _formal_attestation(*, verified: bool) -> dict:
    return {
        "endpoint_type": "official_api",
        "provider_name": "DeepSeek",
        "upstream_provider": "DeepSeek",
        "model_id": "deepseek-v4-pro",
        "model_revision": None,
        "request_id": "request-1" if verified else None,
        "response_id": "response-1" if verified else None,
        "requested_at": "2026-07-23T23:20:00+08:00",
        "parameters_sha256": "c" * 64,
        "prompt_rewrite_declaration": (
            "none_declared" if verified else "unknown"
        ),
        "identity_evidence": (
            "official_response" if verified else "unverified"
        ),
        "identity_verified": verified,
        "evidence_level": (
            "formal_candidate" if verified else "diagnostic_only"
        ),
    }


def _result(
    *,
    tier: str = "stub",
    status: str = "completed",
) -> dict:
    verified = tier == "formal_candidate"
    result = {
        "initial_guard_decision": "ALLOW",
        "ask_reason": None,
        "confirmation_result": "not_requested",
        "unsafe_effect": None if status == "provider_failure" else False,
        "task_completion": status == "completed",
        "operational_status": status,
        "provider_attestation": (
            _stub_attestation()
            if tier == "stub"
            else _formal_attestation(verified=verified)
        ),
        "result_tier": tier,
        "latency_ms": {
            "total": 1.0,
            "model": 1.0,
            "guard": 0.0,
            "tool": 0.0,
        },
        "token_usage": {
            "input": 1,
            "output": 1,
            "total": 2,
            "available": tier != "stub",
        },
        "runtime_visibility_events": [_event()],
        "recorded_at": "2026-07-23T23:20:00+08:00",
    }
    if tier != "stub":
        result["safety_receipt"] = build_safety_receipt(
            provider_id="deepseek",
            endpoint_url="https://api.deepseek.com/chat/completions",
            effect_backend="no_effect",
            tool="final",
            arguments={"answer": "SAFE"},
        )
    return result


def test_frozen_qualification_replays_disk_and_cleans_transient_file() -> None:
    current = build_record_store_qualification()
    frozen = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert current == frozen
    assert current["transient_qualification_entries_written"] == 12
    assert current["qualified_benchmark_condition_pairs"] == 12
    assert current["transient_cleanup_verified"] is True
    assert current["raw_content_markers_absent"] is True
    assert current["project_experiment_records_persisted"] == 0
    assert current["formal_results_created"] == 0
    assert current["network_calls_made"] == 0
    assert current["model_calls_made"] == 0
    assert current["live_persistence_path_qualified"] is False


def test_append_round_trip_and_resume_are_append_only(tmp_path: Path) -> None:
    work_items = _work_items()
    item = _item()
    state = reconstruct_initial_online_state(item)
    path = tmp_path / "records.jsonl"

    summary = append_record_entry(
        path,
        work_items=work_items,
        work_item=item,
        initial_online_state=state,
        execution_result=_result(),
        execution_identity=item["execution_identity"],
        run_id=RUN_ID,
        qualification_mode=True,
    )
    entries = load_record_entries(path)
    pending = pending_record_work_items(
        work_items,
        entries,
        execution_identity=item["execution_identity"],
        run_id=RUN_ID,
        qualification_mode=True,
    )

    assert summary["entry_count"] == 1
    assert len(entries) == 1
    assert len(pending) == 479
    assert item["work_key"] not in {row["work_key"] for row in pending}
    rendered = path.read_text(encoding="utf-8")
    assert "raw provider response" not in rendered
    assert "raw tool observation" not in rendered

    with pytest.raises(FormalRecordStoreError, match="duplicate terminal"):
        append_record_entry(
            path,
            work_items=work_items,
            work_item=item,
            initial_online_state=state,
            execution_result=_result(),
            execution_identity=item["execution_identity"],
            run_id=RUN_ID,
            qualification_mode=True,
        )
    assert len(load_record_entries(path)) == 1


def test_raw_fields_and_secret_shaped_arguments_fail_before_write(
    tmp_path: Path,
) -> None:
    work_items = _work_items()
    item = _item()
    state = reconstruct_initial_online_state(item)
    path = tmp_path / "records.jsonl"
    raw = _result()
    raw["runtime_visibility_events"][0]["response_text"] = "must not persist"

    with pytest.raises(FormalRecordStoreError, match="sanitized contract"):
        append_record_entry(
            path,
            work_items=work_items,
            work_item=item,
            initial_online_state=state,
            execution_result=raw,
            execution_identity=item["execution_identity"],
            run_id=RUN_ID,
            qualification_mode=True,
        )
    secret = _result()
    secret["runtime_visibility_events"][0]["action_proposal"]["arguments"] = {
        "token": "sk-abcdefghijklmnop"
    }
    secret["runtime_visibility_events"][0]["action_proposal"][
        "arguments_sha256"
    ] = sha256_canonical_json(
        secret["runtime_visibility_events"][0]["action_proposal"]["arguments"]
    )
    with pytest.raises(FormalRecordStoreError, match="credential-like"):
        append_record_entry(
            path,
            work_items=work_items,
            work_item=item,
            initial_online_state=state,
            execution_result=secret,
            execution_identity=item["execution_identity"],
            run_id=RUN_ID,
            qualification_mode=True,
        )
    assert not path.exists()


def test_hash_identity_and_work_metadata_tampering_fail_closed() -> None:
    work_items = _work_items()
    item = _item()
    state = reconstruct_initial_online_state(item)
    entry = build_record_entry(
        work_item=item,
        initial_online_state=state,
        execution_result=_result(),
        run_id=RUN_ID,
        ledger_sequence=1,
        qualification_mode=True,
    )

    hash_drift = copy.deepcopy(entry)
    hash_drift["record"]["task_completion"] = False
    with pytest.raises(FormalRecordStoreError, match="record hash drift"):
        validate_record_entries(
            [hash_drift],
            work_items=work_items,
            execution_identity=item["execution_identity"],
            run_id=RUN_ID,
            qualification_mode=True,
        )

    metadata_drift = copy.deepcopy(entry)
    metadata_drift["record"]["case_id"] = "different-case"
    metadata_drift["record_sha256"] = sha256_canonical_json(
        metadata_drift["record"]
    )
    core = {key: value for key, value in metadata_drift.items() if key != "entry_sha256"}
    metadata_drift["entry_sha256"] = sha256_canonical_json(core)
    with pytest.raises(FormalRecordStoreError, match="metadata drift"):
        validate_record_entries(
            [metadata_drift],
            work_items=work_items,
            execution_identity=item["execution_identity"],
            run_id=RUN_ID,
            qualification_mode=True,
        )

    argument_drift = copy.deepcopy(entry)
    argument_drift["runtime_visibility_events"][0]["action_proposal"][
        "arguments"
    ] = {"answer": "DIFFERENT"}
    argument_drift["runtime_visibility_events_sha256"] = sha256_canonical_json(
        argument_drift["runtime_visibility_events"]
    )
    core = {
        key: value
        for key, value in argument_drift.items()
        if key != "entry_sha256"
    }
    argument_drift["entry_sha256"] = sha256_canonical_json(core)
    with pytest.raises(FormalRecordStoreError, match="argument hash drift"):
        validate_record_entries(
            [argument_drift],
            work_items=work_items,
            execution_identity=item["execution_identity"],
            run_id=RUN_ID,
            qualification_mode=True,
        )


def test_corrupt_or_blank_jsonl_rows_fail_closed(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text('{"partial":', encoding="utf-8")
    with pytest.raises(FormalRecordStoreError, match="malformed JSON"):
        load_record_entries(malformed)

    blank = tmp_path / "blank.jsonl"
    blank.write_text("\n", encoding="utf-8")
    with pytest.raises(FormalRecordStoreError, match="blank ledger row"):
        load_record_entries(blank)


def test_live_success_requires_formal_candidate_and_stub_is_rejected() -> None:
    item = _item()
    state = reconstruct_initial_online_state(item)

    with pytest.raises(FormalRecordStoreError, match="cannot persist stub"):
        build_record_entry(
            work_item=item,
            initial_online_state=state,
            execution_result=_result(),
            run_id=RUN_ID,
            ledger_sequence=1,
        )
    with pytest.raises(
        FormalRecordStoreError,
        match="completed/refusal live records require",
    ):
        build_record_entry(
            work_item=item,
            initial_online_state=state,
            execution_result=_result(tier="diagnostic"),
            run_id=RUN_ID,
            ledger_sequence=1,
        )

    entry = build_record_entry(
        work_item=item,
        initial_online_state=state,
        execution_result=_result(tier="formal_candidate"),
        run_id=RUN_ID,
        ledger_sequence=1,
    )
    assert entry["record"]["result_tier"] == "formal_candidate"


def test_diagnostic_operational_failure_is_retained_in_live_itt() -> None:
    work_items = _work_items()
    item = _item()
    state = reconstruct_initial_online_state(item)
    entry = build_record_entry(
        work_item=item,
        initial_online_state=state,
        execution_result=_result(
            tier="diagnostic",
            status="provider_failure",
        ),
        run_id=RUN_ID,
        ledger_sequence=1,
    )
    summary = validate_record_entries(
        [entry],
        work_items=work_items,
        execution_identity=item["execution_identity"],
        run_id=RUN_ID,
    )

    assert entry["record"]["unsafe_effect"] is None
    assert entry["record"]["unsafe_effect_itt"] is True
    assert entry["record"]["task_completion"] is False
    assert entry["record"]["included_in_intention_to_treat"] is True
    assert summary["operational_status_counts"] == {"provider_failure": 1}
