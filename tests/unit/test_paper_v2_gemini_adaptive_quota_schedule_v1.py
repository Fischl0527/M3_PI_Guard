from __future__ import annotations

import copy

import pytest

import experiments.paper_v2.gemini_adaptive_quota_schedule_v1 as schedule
from experiments.paper_v2.contracts import sha256_canonical_json


def test_adaptive_schedule_covers_frozen_query_capacity_round_robin() -> None:
    rows = schedule.build_schedule()
    status = schedule.validate_schedule(rows)

    assert status["query_slot_count"] == 4_000
    assert status["quota_segment_count"] == 2_000
    assert status["technical_canary_query_slots"] == 2
    assert rows[0]["phase"] == "technical_canary_prefix"
    assert rows[499]["query_slots"][-1]["query_index"] == 50
    assert rows[500]["query_slots"][0]["query_index"] == 51
    assert all(row["maximum_provider_requests"] == 16 for row in rows)


def test_adaptive_schedule_round_robins_tasks_before_next_query_index() -> None:
    rows = schedule.build_schedule()
    first_twenty = [
        slot
        for row in rows[:10]
        for slot in row["query_slots"]
    ]

    assert {slot["query_index"] for slot in first_twenty} == {1}
    assert len({slot["case_id"] for slot in first_twenty}) == 20


def test_adaptive_schedule_rejects_query_reordering() -> None:
    rows = schedule.build_schedule()
    tampered = copy.deepcopy(rows)
    tampered[0]["query_slots"].reverse()
    tampered[0]["query_work_key_sequence_sha256"] = sha256_canonical_json(
        [slot["work_key"] for slot in tampered[0]["query_slots"]]
    )
    core = {
        key: child
        for key, child in tampered[0].items()
        if key != "segment_sha256"
    }
    tampered[0]["segment_sha256"] = sha256_canonical_json(core)

    with pytest.raises(schedule.GeminiAdaptiveQuotaScheduleV1Error):
        schedule.validate_schedule(tampered)

