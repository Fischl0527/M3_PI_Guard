from __future__ import annotations

import copy

import pytest

from experiments.paper_v2 import experiment_closeout_day1_harness_review_v1 as review


def test_interrupted_day1_harness_is_neither_pass_nor_fail() -> None:
    value = review.build_review()

    assert value["status"] == "inconclusive_host_interruption_full_rerun_required"
    assert value["observations"]["pytest_summary_observed"] is True
    assert value["observations"]["aggregate_completion_marker_observed"] is False
    assert value["observations"]["wrapper_receipt_observed"] is False
    assert value["verdict"] == {
        "full_harness_passed": False,
        "full_harness_failed": False,
        "partial_pytest_subrun_passed": True,
        "current_worktree_full_rerun_required": True,
    }


def test_review_drift_fails_closed() -> None:
    value = copy.deepcopy(review.build_review())
    value["verdict"]["full_harness_passed"] = True

    with pytest.raises(
        review.ExperimentCloseoutDay1HarnessReviewV1Error,
        match="review drift",
    ):
        review.validate_review(value)
