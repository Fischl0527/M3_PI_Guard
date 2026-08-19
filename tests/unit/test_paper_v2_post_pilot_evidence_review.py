from __future__ import annotations

import copy
from pathlib import Path

import pytest
from jsonschema import ValidationError

from experiments.paper_v2.post_pilot_evidence_review import (
    PostPilotEvidenceReviewError,
    build_reviewer_qualification,
    review_official_single_pilot,
    validate_review_artifact,
    verify_reviewer_qualification,
)


def test_post_pilot_reviewer_qualification_is_zero_network() -> None:
    value = build_reviewer_qualification()

    assert value["status"] == "post_pilot_reviewer_qualified_offline"
    assert value["experiment_record_schema_version"] == (
        "m3-paper-v2-experiment-record-2.2"
    )
    assert value["provider_safety_receipt_persisted"] is True
    assert value["positive_injected_pilot_reviews"] == 1
    assert value["positive_structural_evidence_gate_passed"] is True
    assert value["positive_official_evidence_gate_passed"] is False
    assert value["positive_ready_for_owner_matrix_review"] is False
    assert value["negative_case_count"] == 4
    assert set(value["negative_cases_rejected"]) == {
        "active_candidate_binding_drift",
        "missing_persisted_safety_receipt",
        "provider_trace_drift",
        "tampered_cache_cost_evidence",
    }
    assert value["credentials_read"] == 0
    assert value["network_calls_made"] == 0
    assert value["project_active_admission_created"] is False
    assert value["project_pilot_records_created"] == 0
    assert value["formal_matrix_authorized"] is False
    assert value["result_admission_authorized"] is False


def test_frozen_post_pilot_reviewer_qualification_reproduces() -> None:
    value = verify_reviewer_qualification()

    assert value == build_reviewer_qualification()


def test_official_review_requires_active_admission(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        PostPilotEvidenceReviewError,
        match="active one-pilot admission manifest is missing",
    ):
        review_official_single_pilot(
            active_path=tmp_path / "missing-active.json",
            reviewed_at="2026-07-24T09:30:00+08:00",
        )


def test_review_digest_and_self_authorization_are_rejected() -> None:
    # Qualification already schema-validates a complete offline review.  This
    # minimal invalid object proves the standalone validator cannot be used to
    # turn a review into an expansion authorization.
    invalid = {
        "schema_version": "m3-paper-v2-post-pilot-review-1.0",
        "generated_at": "2026-07-24T09:20:00+08:00",
        "status": "offline_reviewer_qualification_pass",
        "evidence_mode": "offline_injected_qualification",
        "inputs": {},
        "checks": [],
        "observations": {},
        "decision": {
            "structural_evidence_gate_passed": True,
            "official_evidence_gate_passed": False,
            "ready_for_owner_matrix_review": False,
            "owner_matrix_review_required": True,
            "formal_matrix_authorized": True,
            "result_admission_authorized": False,
            "reason_codes": ["offline_fixture_not_live_evidence"],
            "next_gate": "owner review",
        },
        "review_sha256": "0" * 64,
    }
    with pytest.raises(ValidationError):
        validate_review_artifact(invalid)

    drifted = copy.deepcopy(invalid)
    drifted["decision"]["formal_matrix_authorized"] = False
    with pytest.raises(ValidationError):
        validate_review_artifact(drifted)
