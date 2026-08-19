from __future__ import annotations

import copy

import pytest

from experiments.paper_v2 import (
    experiment_closeout_fresh_harness_failure_review_v10 as review,
)


def test_direct_exit_one_v10_state_transition_is_frozen() -> None:
    value = review.verify_review()

    assert value["status"] == (
        "failed_harness_state_transition_frozen_no_provider_execution"
    )
    assert value["observations"]["pytest_failed"] == 1
    assert value["observations"]["pytest_passed"] == 1627
    assert value["observations"]["fail_names"] == list(review.EXPECTED_FAIL_NAMES)
    assert value["state_transition"]["pro_200_output_root_now_exists"] is True
    assert value["root_cause"]["classification"] == (
        "expired_prospective_gate_replayed_after_authorized_pro200_completion"
    )
    assert value["root_cause"]["provider_failure"] is False
    assert value["evidence_boundary"]["pro_500_execution_authorized"] is False


def test_v10_failure_review_tamper_fails_closed() -> None:
    value = copy.deepcopy(review.verify_review())
    value["evidence_boundary"]["pro_500_execution_authorized"] = True

    with pytest.raises(
        review.ExperimentCloseoutFreshHarnessFailureReviewV10Error,
        match="failure review artifact drift",
    ):
        review.validate_review(value)


def test_v10_transcript_drift_fails_closed() -> None:
    stdout = review.STDOUT_PATH.read_bytes().replace(
        b"1 failed, 1627 passed", b"1 failed, 1628 passed", 1
    )

    with pytest.raises(
        review.ExperimentCloseoutFreshHarnessFailureReviewV10Error,
        match="failure transcript signature drift",
    ):
        review.analyze_transcript(stdout, review.STDERR_PATH.read_bytes())
