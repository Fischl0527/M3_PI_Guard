from __future__ import annotations

import copy
import json

import pytest

import experiments.paper_v2.public_primary_merge_review_v1 as merge_v1
import experiments.paper_v2.public_sharded_continuation_v2 as continuation_v2


def _candidate() -> dict[str, object]:
    value = json.loads(
        continuation_v2.CANDIDATE_PATH.read_text(encoding="utf-8")
    )
    assert isinstance(value, dict)
    return value


def _usage(multiplier: int) -> dict[str, int]:
    return {
        "prompt_tokens": 100 * multiplier,
        "completion_tokens": 10 * multiplier,
        "prompt_cache_hit_tokens": 60 * multiplier,
        "prompt_cache_miss_tokens": 40 * multiplier,
    }


def _canary_review() -> dict[str, object]:
    return {
        "schema_version": (
            "m3-paper-v2-public-canary-technical-review-4.0"
        ),
        "status": "public_canary_technical_gate_pass",
        "model_role": "primary",
        "expected_records": 24,
        "observed_records": 24,
        "provider_calls_completed": 64,
        "role_cumulative_usage": _usage(1),
        "role_cumulative_cost_cny": 0.0521812,
        "checks": {
            key: True for key in merge_v1.REQUIRED_CANARY_CHECKS
        },
        "matrix_continuation_eligible": True,
        "review_boundary": {
            key: False for key in merge_v1.REQUIRED_BOUNDARY_FALSE
        },
    }


def _shard_reviews(
    candidate: dict[str, object],
    admission_hashes: list[str],
) -> list[dict[str, object]]:
    reviews: list[dict[str, object]] = []
    scope = candidate["scope"]
    assert isinstance(scope, dict)
    shards = scope["shards"]
    assert isinstance(shards, list)
    for index, shard in enumerate(shards):
        assert isinstance(shard, dict)
        records = shard["records"]
        assert isinstance(records, int)
        reviews.append(
            {
                "schema_version": (
                    "m3-paper-v2-public-continuation-shard-review-2.0"
                ),
                "status": (
                    "fresh_continuation_shard_technical_gate_pass"
                ),
                "model_role": "primary",
                "shard_index": index,
                "run_id": shard["run_id"],
                "candidate_manifest_sha256": candidate[
                    "manifest_sha256"
                ],
                "admission_file_sha256": admission_hashes[index],
                "expected_records": records,
                "observed_records": records,
                "provider_calls_completed": records,
                "role_cumulative_usage": _usage(index + 2),
                "role_cumulative_cost_cny": 1.0 + index,
                "checks": {
                    key: True for key in merge_v1.REQUIRED_SHARD_CHECKS
                },
                "result_admission_eligible": True,
                "review_boundary": {
                    key: False
                    for key in merge_v1.REQUIRED_BOUNDARY_FALSE
                },
            }
        )
    return reviews


def _locks() -> list[dict[str, object]]:
    return [
        {
            "path": f"artifact-{index}.json",
            "bytes": index + 1,
            "sha256": f"{index:064x}",
        }
        for index in range(10)
    ]


def test_primary_merge_is_complete_but_outcomes_remain_sealed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    admission_hashes = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
    monkeypatch.setattr(
        continuation_v2,
        "verify_candidate",
        lambda: copy.deepcopy(candidate),
    )

    value = merge_v1.assemble_primary_merge_review(
        candidate=candidate,
        canary_review=_canary_review(),
        shard_reviews=_shard_reviews(candidate, admission_hashes),
        admission_file_sha256s=admission_hashes,
        artifact_locks=_locks(),
        generated_at="2026-07-30T09:00:00+08:00",
    )

    assert value["coverage"] == {
        "canary_records": 24,
        "continuation_records": 5058,
        "primary_records": 5082,
        "shard_records": [1265, 1265, 1264, 1264],
    }
    assert value["authorization"][
        "ready_for_independent_result_admission"
    ] is True
    assert value["authorization"][
        "scientific_outcome_access_authorized"
    ] is False
    assert value["authorization"]["result_admission_authorized"] is False
    assert value["review_boundary"]["scientific_outcomes_accessed"] is False
    merge_v1._validate_schema(value)


def test_primary_merge_rejects_scientific_boundary_crossing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    admission_hashes = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
    monkeypatch.setattr(
        continuation_v2,
        "verify_candidate",
        lambda: copy.deepcopy(candidate),
    )
    reviews = _shard_reviews(candidate, admission_hashes)
    boundary = reviews[2]["review_boundary"]
    assert isinstance(boundary, dict)
    boundary["unsafe_effect_aggregated"] = True

    with pytest.raises(
        merge_v1.PublicPrimaryMergeReviewError,
        match="boundary was crossed",
    ):
        merge_v1.assemble_primary_merge_review(
            candidate=candidate,
            canary_review=_canary_review(),
            shard_reviews=reviews,
            admission_file_sha256s=admission_hashes,
            artifact_locks=_locks(),
            generated_at="2026-07-30T09:00:00+08:00",
        )


def test_primary_merge_rejects_partition_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    drifted = copy.deepcopy(candidate)
    scope = drifted["scope"]
    assert isinstance(scope, dict)
    shards = scope["shards"]
    assert isinstance(shards, list)
    assert isinstance(shards[0], dict)
    assert isinstance(shards[1], dict)
    shards[1]["work_key_sequence_sha256"] = shards[0][
        "work_key_sequence_sha256"
    ]
    drifted["scope_sha256"] = continuation_v2.sha256_canonical_json(
        scope
    )
    drifted["manifest_sha256"] = continuation_v2._manifest_sha(drifted)
    monkeypatch.setattr(
        continuation_v2,
        "verify_candidate",
        lambda: copy.deepcopy(drifted),
    )
    admission_hashes = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]

    with pytest.raises(
        merge_v1.PublicPrimaryMergeReviewError,
        match="partition drift",
    ):
        merge_v1.assemble_primary_merge_review(
            candidate=drifted,
            canary_review=_canary_review(),
            shard_reviews=_shard_reviews(drifted, admission_hashes),
            admission_file_sha256s=admission_hashes,
            artifact_locks=_locks(),
            generated_at="2026-07-30T09:00:00+08:00",
        )
