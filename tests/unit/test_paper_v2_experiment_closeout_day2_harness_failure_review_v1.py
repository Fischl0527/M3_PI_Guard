from __future__ import annotations

import copy

import pytest

from experiments.paper_v2 import (
    experiment_closeout_day2_harness_failure_review_v1 as review,
)


def test_direct_exit_one_harness_is_frozen_without_provider_authorization() -> None:
    value = review.build_review()

    assert value["status"] == "failed_harness_frozen_no_provider_execution"
    assert value["observations"]["pytest_passed"] == 1438
    assert value["observations"]["fail_names"] == [review.FAILED_CHECK]
    assert value["observations"]["terminal_failure_marker_count"] == 1
    assert value["root_cause"]["classification"] == "stale_current_harness_command"
    assert value["root_cause"]["superseded_stages"] == ["pro_50", "flash_50"]
    assert value["remediation_boundary"]["modify_v1_candidates_or_admissions"] is False
    assert value["evidence_boundary"]["provider_canary_authorized"] is False
    assert value["evidence_boundary"]["provider_calls_made_by_failed_harness"] == 0


def test_day2_failure_review_tamper_fails_closed() -> None:
    value = copy.deepcopy(review.build_review())
    value["remediation_boundary"]["modify_v1_candidates_or_admissions"] = True

    with pytest.raises(
        review.ExperimentCloseoutDay2HarnessFailureReviewV1Error,
        match="failure review artifact drift",
    ):
        review.validate_review(value)
