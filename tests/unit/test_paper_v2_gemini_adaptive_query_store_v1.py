from __future__ import annotations

import copy
from pathlib import Path

import pytest

import experiments.paper_v2.experiment_closeout_freeze_v1 as freeze
from experiments.paper_v2 import gemini_adaptive_query_store_v1 as store
from tests.unit.test_paper_v2_gemini_public_execution_store_v1 import _result


RUN_ID = "adaptive-gemini-test"
IDENTITY = "a" * 64
WORK_KEY = "adaptive-work-1"


def _ledger(tmp_path: Path) -> store.GeminiAdaptiveQueryLedger:
    return store.GeminiAdaptiveQueryLedger(
        tmp_path / "queries.jsonl",
        run_id=RUN_ID,
        execution_identity=IDENTITY,
        known_work_keys={WORK_KEY},
    )


def test_started_query_is_fsynced_and_replays(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.append_started(
        work_key=WORK_KEY,
        case_id="M3V2-D-001-A1",
        query_index=1,
        prompt_sha256="b" * 64,
        recorded_at="2026-08-02T11:00:00+08:00",
    )

    status = ledger.full_validate()
    assert status["started_query_count"] == 1
    assert status["terminal_query_count"] == 0
    assert status["open_query_work_keys"] == [WORK_KEY]


def test_duplicate_or_concurrent_start_fails_closed(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.append_started(
        work_key=WORK_KEY,
        case_id="M3V2-D-001-A1",
        query_index=1,
        prompt_sha256="b" * 64,
        recorded_at="2026-08-02T11:00:00+08:00",
    )

    with pytest.raises(
        store.GeminiAdaptiveQueryStoreV1Error,
        match="another Gemini adaptive query is open",
    ):
        ledger.append_started(
            work_key=WORK_KEY,
            case_id="M3V2-D-001-A1",
            query_index=1,
            prompt_sha256="b" * 64,
            recorded_at="2026-08-02T11:00:01+08:00",
        )


def test_started_event_tampering_breaks_replay(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    event = ledger.append_started(
        work_key=WORK_KEY,
        case_id="M3V2-D-001-A1",
        query_index=1,
        prompt_sha256="b" * 64,
        recorded_at="2026-08-02T11:00:00+08:00",
    )
    tampered = copy.deepcopy(event)
    tampered["prompt_sha256"] = "not-a-hash"

    with pytest.raises(store.GeminiAdaptiveQueryStoreV1Error):
        store.validate_events(
            [tampered],
            run_id=RUN_ID,
            execution_identity=IDENTITY,
            known_work_keys={WORK_KEY},
        )


def test_terminal_record_binds_official_trace_and_content_free_online_evidence(
    tmp_path: Path,
) -> None:
    item = freeze.build_gemini_public_plan()[0]
    result, state = _result(tmp_path, item)
    record = store.assemble_adaptive_record(
        item,
        state,
        result,
        run_id=RUN_ID,
    )
    ledger = store.GeminiAdaptiveQueryLedger(
        tmp_path / "adaptive_queries.jsonl",
        run_id=RUN_ID,
        execution_identity=str(item["execution_identity"]),
        known_work_keys={str(item["work_key"])},
    )
    prompt_sha = "d" * 64
    ledger.append_started(
        work_key=str(item["work_key"]),
        case_id=str(item["case_id"]),
        query_index=1,
        prompt_sha256=prompt_sha,
        recorded_at="2026-08-02T11:50:00+08:00",
    )
    terminal = ledger.append_terminal(
        work_key=str(item["work_key"]),
        case_id=str(item["case_id"]),
        query_index=1,
        prompt_sha256=prompt_sha,
        record=record,
        initial_online_state=state,
        runtime_visibility_events=result["runtime_visibility_events"],
        recorded_at="2026-08-02T11:50:01+08:00",
    )

    status = ledger.full_validate()
    assert record["model_role"] == store.MODEL_ROLE
    assert terminal["provider_request_count"] == 1
    assert "initial_online_state" not in terminal["online_evidence"]
    assert terminal["online_evidence"]["online_visible_field_digest"] == record[
        "online_visible_field_digest"
    ]
    assert status["terminal_query_count"] == 1
    assert status["attempted_provider_request_count"] == 1
    assert status["provider_response_id_count"] == 1
