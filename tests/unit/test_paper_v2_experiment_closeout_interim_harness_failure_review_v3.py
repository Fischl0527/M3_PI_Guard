from __future__ import annotations

import copy

import pytest

from experiments.paper_v2 import (
    experiment_closeout_interim_harness_failure_review_v3 as review,
)


def test_direct_exit_one_interim_harness_is_frozen_without_provider_calls() -> None:
    value = review.build_review()

    assert value["status"] == "failed_harness_frozen_no_provider_execution"
    assert value["observations"]["pytest_failed"] == 1
    assert value["observations"]["pytest_passed"] == 1456
    assert value["observations"]["fail_names"] == [review.FAILED_CHECK]
    assert value["root_cause"]["classification"] == (
        "version_agnostic_supersession_assertion_false_positive"
    )
    assert value["remediation_boundary"]["remove_current_v2_admission"] is False
    assert value["evidence_boundary"]["provider_calls_made_by_failed_harness"] == 0


def test_interim_failure_review_tamper_fails_closed() -> None:
    value = copy.deepcopy(review.build_review())
    value["remediation_boundary"]["modify_historical_candidates_or_admissions"] = True

    with pytest.raises(
        review.ExperimentCloseoutInterimHarnessFailureReviewV3Error,
        match="failure review artifact drift",
    ):
        review.validate_review(value)
