from __future__ import annotations

import copy
from typing import Any

import pytest

import experiments.paper_v2.public_second_recovery_evidence_review_v4 as review


def _source(*, quality_passed: bool) -> dict[str, Any]:
    checks = {
        name: True for name in review.INTEGRITY_POSITIVE_CHECKS
    }
    checks.update(
        {name: False for name in review.NEGATIVE_BOUNDARY_CHECKS}
    )
    checks[review.QUALITY_CHECK] = quality_passed
    core: dict[str, Any] = {
        "schema_version": (
            "m3-paper-v2-public-second-recovery-review-3.0"
        ),
        "status": "flash_recovery_shard_technical_gate_fail",
        "shard_index": 0,
        "technical_gate_passed": False,
        "checks": checks,
    }
    return {**core, "manifest_sha256": review._manifest_sha(core)}


@pytest.mark.parametrize("quality_passed", [False, True])
def test_negative_false_is_not_an_integrity_failure(
    quality_passed: bool,
) -> None:
    source = _source(quality_passed=quality_passed)

    quality, positives, negatives = review._validate_source_review(
        source, shard_index=0
    )

    assert quality is quality_passed
    assert all(positives.values())
    assert all(negatives.values())


def test_substantive_integrity_failure_rejects() -> None:
    source = _source(quality_passed=False)
    drifted = copy.deepcopy(source)
    drifted["checks"]["all_records_in_itt"] = False
    drifted["manifest_sha256"] = review._manifest_sha(drifted)

    with pytest.raises(
        review.PublicSecondRecoveryEvidenceReviewV4Error,
        match="substantive",
    ):
        review._validate_source_review(drifted, shard_index=0)


def test_negative_boundary_true_rejects() -> None:
    source = _source(quality_passed=True)
    drifted = copy.deepcopy(source)
    drifted["checks"]["source_terminal_records_retried"] = True
    drifted["manifest_sha256"] = review._manifest_sha(drifted)

    with pytest.raises(
        review.PublicSecondRecoveryEvidenceReviewV4Error,
        match="negative evidence boundary",
    ):
        review._validate_source_review(drifted, shard_index=0)
