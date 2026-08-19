from __future__ import annotations

import copy
import json
from typing import Any

import pytest

import experiments.paper_v2.public_primary_merge_review_v2 as merge
import experiments.paper_v2.public_shard_evidence_review_v1 as evidence
import experiments.paper_v2.public_sharded_continuation_v2 as continuation


def _canary() -> dict[str, Any]:
    return {
        "schema_version": (
            "m3-paper-v2-public-canary-technical-review-4.0"
        ),
        "status": "public_canary_technical_gate_pass",
        "model_role": "primary",
        "expected_records": 24,
        "observed_records": 24,
        "matrix_continuation_eligible": True,
        "checks": {
            name: True for name in merge.merge_v1.REQUIRED_CANARY_CHECKS
        },
        "review_boundary": {
            name: False
            for name in merge.merge_v1.REQUIRED_BOUNDARY_FALSE
        },
        "provider_calls_completed": 64,
        "role_cumulative_cost_cny": 0.05,
        "role_cumulative_usage": {
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "prompt_cache_hit_tokens": 80,
            "prompt_cache_miss_tokens": 20,
        },
    }


def _candidate() -> dict[str, Any]:
    return json.loads(
        continuation.CANDIDATE_PATH.read_text(encoding="utf-8")
    )


def _review(
    shard: dict[str, Any],
    *,
    manifest: str,
    diagnostics: int,
) -> dict[str, Any]:
    quality_passed = diagnostics <= max(1, int(shard["records"]) // 100)
    core: dict[str, Any] = {
        "schema_version": evidence.SCHEMA_VERSION,
        "artifact_role": (
            "typed_outcome_blind_public_shard_evidence_review"
        ),
        "reviewed_at": evidence.REVIEWED_AT,
        "status": "public_shard_evidence_integrity_pass",
        "shard_index": shard["shard_index"],
        "run_id": shard["run_id"],
        "source_review_manifest_sha256": "9" * 64,
        "candidate_manifest_sha256": manifest,
        "admission_file_sha256": "8" * 64,
        "expected_records": shard["records"],
        "observed_records": shard["records"],
        "diagnostic_records": diagnostics,
        "diagnostic_fraction": diagnostics / shard["records"],
        "maximum_admissible_diagnostic_records": max(
            1, int(shard["records"]) // 100
        ),
        "provider_calls_completed": shard["records"],
        "role_cumulative_cost_cny": 0.5,
        "record_ledger_tail_sha256": "1" * 64,
        "attempt_ledger_tail_sha256": "2" * 64,
        "budget_ledger_tail_sha256": "3" * 64,
        "integrity_positive_checks": {
            name: True for name in evidence.INTEGRITY_POSITIVE_CHECKS
        },
        "negative_boundary_checks": {
            name: False for name in evidence.NEGATIVE_BOUNDARY_CHECKS
        },
        "claim_quality": {
            "frozen_one_percent_gate_passed": quality_passed,
            "frozen_one_percent_gate_waived": False,
            "clean_mechanism_quality_claim_eligible": quality_passed,
            "empirical_security_utility_fallback_only": (
                not quality_passed
            ),
        },
        "public_evidence_integrity_gate_passed": True,
        "scientific_result_admission_authorized": False,
        "review_boundary": {
            "ledger_rows_changed": 0,
            "diagnostic_rows_excluded": 0,
            "terminal_rows_retried": 0,
            "provider_calls_made": 0,
            "scientific_outcomes_aggregated": False,
            "quality_gate_reclassified_as_integrity": False,
            "integrity_and_claim_quality_separated": True,
        },
        "artifact_locks": [],
    }
    return {**core, "manifest_sha256": merge._manifest_sha(core)}


def test_merge_routes_diagnostics_to_empirical_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    monkeypatch.setattr(
        continuation,
        "validate_candidate",
        lambda value: copy.deepcopy(value),
    )
    shards = candidate["scope"]["shards"]
    manifests = [str(index) * 64 for index in range(1, 5)]
    reviews = [
        _review(
            shard,
            manifest=manifest,
            diagnostics=70 if index == 1 else 0,
        )
        for index, (shard, manifest) in enumerate(
            zip(shards, manifests, strict=True)
        )
    ]

    value = merge.assemble_primary_merge_review(
        candidate=candidate,
        canary_review=_canary(),
        shard_evidence_reviews=reviews,
        recovery_candidate_manifests=manifests,
        artifact_locks=[],
        generated_at="2026-07-30T06:30:00+08:00",
    )

    assert value["coverage"]["primary_records"] == 5082
    assert value["coverage"]["diagnostic_records"] == 70
    assert value["claim_quality"][
        "clean_mechanism_quality_claim_eligible"
    ] is False
    assert value["claim_quality"][
        "empirical_security_utility_fallback_only"
    ] is True
    assert value["authorization"][
        "scientific_outcome_access_authorized"
    ] is False


def test_merge_rejects_integrity_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    monkeypatch.setattr(
        continuation,
        "validate_candidate",
        lambda value: copy.deepcopy(value),
    )
    shards = candidate["scope"]["shards"]
    manifests = [str(index) * 64 for index in range(1, 5)]
    reviews = [
        _review(shard, manifest=manifest, diagnostics=0)
        for shard, manifest in zip(shards, manifests, strict=True)
    ]
    reviews[0]["integrity_positive_checks"]["all_attempts_terminal"] = False
    reviews[0]["manifest_sha256"] = merge._manifest_sha(reviews[0])

    with pytest.raises(
        merge.PublicPrimaryMergeReviewV2Error,
        match="evidence review drift",
    ):
        merge.assemble_primary_merge_review(
            candidate=candidate,
            canary_review=_canary(),
            shard_evidence_reviews=reviews,
            recovery_candidate_manifests=manifests,
            artifact_locks=[],
            generated_at="2026-07-30T06:30:00+08:00",
        )
