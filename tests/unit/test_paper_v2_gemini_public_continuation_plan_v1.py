from __future__ import annotations

import copy

import pytest

import experiments.paper_v2.gemini_public_continuation_plan_v1 as plan
from experiments.paper_v2.contracts import sha256_canonical_json


def test_pending_schedule_is_complete_disjoint_and_four_shard() -> None:
    rows = plan.build_schedule()
    status = plan.validate_schedule(rows)

    assert status["record_count"] == 1_779
    assert status["quota_segment_count"] == 1_186
    assert status["logical_shard_segment_counts"] == [297, 297, 296, 296]
    assert all(row["maximum_provider_requests"] <= 18 for row in rows)
    assert all(row["paid_ceiling_usd"] == 0.0 for row in rows)


def test_schedule_rejects_duplicate_or_reordered_work_key() -> None:
    rows = plan.build_schedule()
    tampered = copy.deepcopy(rows)
    tampered[1]["work_keys"][0] = tampered[0]["work_keys"][0]
    tampered[1]["work_key_sequence_sha256"] = sha256_canonical_json(
        tampered[1]["work_keys"]
    )
    core = {
        key: child
        for key, child in tampered[1].items()
        if key != "segment_sha256"
    }
    tampered[1]["segment_sha256"] = sha256_canonical_json(core)

    with pytest.raises(plan.GeminiPublicContinuationPlanV1Error):
        plan.validate_schedule(tampered)


def test_schedule_rejects_a_fifth_logical_shard() -> None:
    rows = plan.build_schedule()
    tampered = copy.deepcopy(rows)
    tampered[-1]["logical_shard_index"] = 4
    core = {
        key: child
        for key, child in tampered[-1].items()
        if key != "segment_sha256"
    }
    tampered[-1]["segment_sha256"] = sha256_canonical_json(core)

    with pytest.raises(plan.GeminiPublicContinuationPlanV1Error):
        plan.validate_schedule(tampered)


def test_candidate_binds_the_actual_public_v4_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedule = plan.build_schedule()
    monkeypatch.setattr(
        plan.public_v4,
        "verify_candidate",
        lambda: {"manifest_sha256": "v" * 64},
    )
    monkeypatch.setattr(
        plan,
        "_lock",
        lambda path: {"path": str(path), "bytes": 1, "sha256": "a" * 64},
    )

    candidate = plan.build_candidate(schedule)

    assert (
        candidate["scope"]["source_canary_candidate_manifest_sha256"]
        == "v" * 64
    )
    assert any(
        item["path"] == str(plan.public_v4.CANDIDATE_PATH)
        for item in candidate["artifact_locks"]
    )
