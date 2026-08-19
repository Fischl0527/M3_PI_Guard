from __future__ import annotations

import copy

import pytest

import experiments.paper_v2.adaptive_recovery_technical_review_v1 as review


def test_typed_adaptive_review_passes_only_boolean_defect() -> None:
    value = review.verify_review()

    assert value["technical_gate_passed"] is True
    assert all(value["positive_checks"].values())
    assert not any(value["negative_boundary_checks"].values())
    assert value["correction_scope"] == {
        "evidence_rows_changed": 0,
        "ledger_rows_changed": 0,
        "checkpoint_rows_changed": 0,
        "provider_calls_made": 0,
        "scientific_outcomes_aggregated": False,
        "only_boolean_aggregation_semantics_corrected": True,
    }


def test_typed_adaptive_review_rejects_substantive_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = review._load_json(review.SOURCE_REVIEW)
    drifted = copy.deepcopy(source)
    drifted["checks"]["budget_not_paused"] = False
    drifted["manifest_sha256"] = review._manifest_sha(drifted)
    monkeypatch.setattr(review, "_load_json", lambda path: drifted)

    with pytest.raises(
        review.AdaptiveRecoveryTechnicalReviewError,
        match="substantive",
    ):
        review.build_review()
