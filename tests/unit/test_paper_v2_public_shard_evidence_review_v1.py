from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

import experiments.paper_v2.public_shard_evidence_review_v1 as review


def _source(*, quality_passed: bool) -> dict[str, Any]:
    positives = {
        name: True for name in review.INTEGRITY_POSITIVE_CHECKS
    }
    positives[review.QUALITY_CHECK] = quality_passed
    core: dict[str, Any] = {
        "schema_version": (
            "m3-paper-v2-public-single-shard-technical-review-3.0"
        ),
        "artifact_role": "outcome_blind_single_public_shard_review",
        "reviewed_at": "2026-07-30T06:00:00+08:00",
        "status": (
            "public_recovery_shard_technical_gate_pass"
            if quality_passed
            else "public_recovery_shard_technical_gate_fail"
        ),
        "shard_index": 1,
        "run_id": "test-public-shard",
        "candidate_manifest_sha256": "a" * 64,
        "admission_file_sha256": "b" * 64,
        "expected_records": 100,
        "observed_records": 100,
        "diagnostic_records": 6,
        "maximum_admissible_diagnostic_records": 1,
        "provider_calls_completed": 200,
        "role_cumulative_cost_cny": 0.5,
        "record_ledger_tail_sha256": "c" * 64,
        "attempt_ledger_tail_sha256": "d" * 64,
        "budget_ledger_tail_sha256": "e" * 64,
        "positive_checks": positives,
        "negative_boundary_checks": {
            name: False for name in review.NEGATIVE_BOUNDARY_CHECKS
        },
        "technical_gate_passed": quality_passed,
        "scientific_result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": review._manifest_sha(core)}


def _patch_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    source: dict[str, Any],
) -> None:
    paths = {
        name: Path(f"C:/{name}.json")
        for name in (
            "candidate",
            "admission",
            "source_review",
            "output",
            "records",
            "attempts",
            "budget",
        )
    }
    monkeypatch.setattr(review, "_paths", lambda shard_index: paths)
    monkeypatch.setattr(review, "_load_json", lambda path: source)
    monkeypatch.setattr(
        review,
        "_lock",
        lambda path: {
            "path": path.as_posix(),
            "bytes": 1,
            "sha256": "f" * 64,
        },
    )


def test_quality_failure_remains_visible_but_integrity_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_artifacts(monkeypatch, _source(quality_passed=False))

    value = review.build_review(1)

    assert value["public_evidence_integrity_gate_passed"] is True
    assert value["claim_quality"] == {
        "frozen_one_percent_gate_passed": False,
        "frozen_one_percent_gate_waived": False,
        "clean_mechanism_quality_claim_eligible": False,
        "empirical_security_utility_fallback_only": True,
    }
    assert value["review_boundary"]["diagnostic_rows_excluded"] == 0
    assert value["review_boundary"]["quality_gate_reclassified_as_integrity"] is False


def test_substantive_integrity_failure_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source(quality_passed=False)
    drifted = copy.deepcopy(source)
    drifted["positive_checks"]["all_records_in_itt"] = False
    drifted["manifest_sha256"] = review._manifest_sha(drifted)
    _patch_artifacts(monkeypatch, drifted)

    with pytest.raises(
        review.PublicShardEvidenceReviewError,
        match="substantive",
    ):
        review.build_review(1)


def test_negative_boundary_violation_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source(quality_passed=True)
    drifted = copy.deepcopy(source)
    drifted["negative_boundary_checks"][
        "scientific_outcomes_aggregated"
    ] = True
    drifted["manifest_sha256"] = review._manifest_sha(drifted)
    _patch_artifacts(monkeypatch, drifted)

    with pytest.raises(
        review.PublicShardEvidenceReviewError,
        match="negative evidence boundary",
    ):
        review.build_review(1)
