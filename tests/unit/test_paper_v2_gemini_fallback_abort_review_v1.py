from __future__ import annotations

from experiments.paper_v2.gemini_fallback_abort_review_v1 import (
    build_review,
    verify_review,
)


def test_v1_abort_review_is_content_free_and_result_ineligible() -> None:
    value = build_review()

    assert value["status"] == (
        "aborted_result_ineligible_new_version_required"
    )
    assert value["technical_checks"]["single_closed_failed_call"] is True
    assert value["trace_summary"]["provider_calls_failed"] == 1
    assert value["trace_summary"]["provider_calls_completed"] == 0
    assert value["trace_summary"]["experiment_records"] == 0
    assert value["evidence_boundary"]["prompts_read"] == 0
    assert value["evidence_boundary"]["response_text_read"] == 0
    assert value["disposition"]["run_resumable"] is False
    assert value["disposition"]["result_eligible"] is False


def test_frozen_v1_abort_review_reproduces() -> None:
    assert verify_review() == build_review()
