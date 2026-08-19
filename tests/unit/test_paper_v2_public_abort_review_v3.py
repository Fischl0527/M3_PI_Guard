from __future__ import annotations

import pytest

from experiments.paper_v2.public_abort_review_v3 import (
    PublicAbortReviewV3Error,
    build_abort_review,
    verify_abort_review,
)


def test_public_v3_abort_review_is_content_free_and_nonresumable() -> None:
    value = build_abort_review()

    assert value["status"] == "aborted_partial_records_result_ineligible"
    assert value["operational_summary"]["record_count"] == 12
    assert value["operational_summary"]["provider_calls_completed"] == 33
    assert value["operational_summary"][
        "orphaned_completed_provider_calls"
    ] == 2
    assert value["operational_summary"]["open_attempt_count"] == 1
    assert value["root_cause"][
        "binding_digest_matches_active_material"
    ] is False
    assert value["integrity_checks"]["automatic_retry_used"] is False
    assert value["evidence_boundary"]["run_resumable"] is False
    assert value["evidence_boundary"][
        "scientific_outcomes_aggregated"
    ] is False
    assert value["evidence_boundary"][
        "scientific_outcome_fields_reported"
    ] is False


def test_public_v3_abort_review_reproduces() -> None:
    assert verify_abort_review()["manifest_sha256"]


def test_public_v3_abort_review_rejects_drift(tmp_path) -> None:
    path = tmp_path / "review.json"
    path.write_text('{"status":"drift"}\n', encoding="utf-8")

    with pytest.raises(PublicAbortReviewV3Error, match="drift"):
        verify_abort_review(path)
