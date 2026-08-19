from __future__ import annotations

import copy

import pytest

from experiments.paper_v2 import (
    experiment_closeout_fresh_harness_failure_review_v5 as review,
)


def test_direct_exit_one_fresh_harness_v5_is_frozen_without_provider_calls() -> None:
    value = review.verify_review()

    assert value["status"] == "failed_harness_frozen_no_provider_execution"
    assert value["observations"]["pytest_passed"] == 1531
    assert value["observations"]["fail_names"] == list(review.EXPECTED_FAIL_NAMES)
    assert value["observations"]["terminal_failure_marker_count"] == 1
    assert value["root_cause"]["classification"] == (
        "sandbox_git_safe_directory_rejection_at_external_checkout"
    )
    assert value["root_cause"]["process_scoped_remediation_qualified"] is True
    assert value["remediation_boundary"]["mutate_global_git_config"] is False
    assert value["evidence_boundary"]["provider_calls_made_by_failed_harness"] == 0
    assert value["evidence_boundary"]["provider_execution_authorized"] is False


def test_fresh_harness_v5_failure_review_tamper_fails_closed() -> None:
    value = copy.deepcopy(review.verify_review())
    value["remediation_boundary"]["mutate_global_git_config"] = True

    with pytest.raises(
        review.ExperimentCloseoutFreshHarnessFailureReviewV5Error,
        match="failure review artifact drift",
    ):
        review.validate_review(value)
