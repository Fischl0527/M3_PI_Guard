from experiments.paper_v2 import formal_matrix_abort_review_v2 as review


def test_v6_abort_review_reproduces_without_results() -> None:
    value = review.verify_abort_review()

    assert value["status"] == (
        "aborted_result_ineligible_new_version_required"
    )
    assert value["operational_summary"]["record_count"] == 64
    assert value["operational_summary"]["open_attempt_count"] == 1
    assert (
        value["operational_summary"]["orphaned_completed_response_count"]
        == 2
    )
    assert value["evidence_boundary"]["scientific_outcomes_reviewed"] is False
    assert value["evidence_boundary"]["prior_run_resumable"] is False
