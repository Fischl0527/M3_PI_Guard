from __future__ import annotations

import json

import pytest

from experiments.paper_v2.public_sharded_continuation_abort_review_v1 import (
    PublicShardedContinuationAbortReviewError,
    build_abort_review,
    verify_abort_review,
)


def test_continuation_v1_abort_review_is_content_free_and_nonresumable() -> None:
    value = build_abort_review()

    assert value["status"] == (
        "four_shards_aborted_after_first_record_result_ineligible"
    )
    assert value["operational_summary"]["record_count"] == 4
    assert value["operational_summary"]["provider_calls_completed"] == 13
    assert value["operational_summary"]["role_cumulative_cost_cny"] == 0.014446
    assert value["operational_summary"]["open_attempt_count"] == 0
    assert len(value["shards"]) == 4
    assert all(item["run_resumable"] is False for item in value["shards"])
    assert value["root_cause"]["provider_usage_anomaly_observed"] is False
    assert value["evidence_boundary"]["old_roots_resumable"] is False
    assert value["evidence_boundary"][
        "scientific_outcomes_aggregated"
    ] is False

    text = json.dumps(value, sort_keys=True)
    assert "unsafe_effect" not in text
    assert "task_completion" not in text


def test_continuation_v1_abort_review_reproduces() -> None:
    assert verify_abort_review()["manifest_sha256"]


def test_continuation_v1_abort_review_rejects_drift(tmp_path) -> None:
    path = tmp_path / "review.json"
    path.write_text('{"status":"drift"}\n', encoding="utf-8")

    with pytest.raises(
        PublicShardedContinuationAbortReviewError,
        match="drift",
    ):
        verify_abort_review(path)
