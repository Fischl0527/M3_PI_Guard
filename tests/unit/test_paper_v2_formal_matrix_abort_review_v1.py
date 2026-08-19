from __future__ import annotations

from experiments.paper_v2.formal_matrix_abort_review_v1 import (
    build_abort_review,
)


def test_v5_abort_review_is_content_free_and_result_closed() -> None:
    value = build_abort_review()
    summary = value["operational_summary"]
    boundary = value["evidence_boundary"]

    assert value["status"] == "aborted_result_ineligible_new_version_required"
    assert summary["record_count"] == 94
    assert summary["remaining_work_items"] == 386
    assert summary["open_attempt_count"] == 1
    assert summary["record_backed_open_attempt_count"] == 1
    assert summary["orphaned_completed_response_count"] == 0
    assert summary["operational_status_counts"] == {
        "completed": 92,
        "runner_failure": 2,
    }
    assert boundary["scientific_outcomes_reviewed"] is False
    assert boundary["result_admission_authorized"] is False
    assert boundary["prior_run_resumable"] is False
