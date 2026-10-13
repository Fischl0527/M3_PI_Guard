"""具备独立完整性与质量复核的对结果盲审主合并工具。

分离数据传输完整性校验与统计学质量达标判定。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import experiments.paper_v2.public_primary_merge_review_v1 as merge_v1
import experiments.paper_v2.public_shard_evidence_review_v1 as evidence_v1
import experiments.paper_v2.public_sharded_continuation_v2 as continuation_v2
import experiments.paper_v2.public_single_shard_recovery_v3 as recovery_v3
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_OUTPUT = PROTOCOL_ROOT / "public_primary_merge_review_v2.json"
SCHEMA_VERSION = "m3-paper-v2-public-primary-merge-review-2.0"
EXPECTED_CANARY_RECORDS = 24
EXPECTED_CONTINUATION_RECORDS = 5058
EXPECTED_PRIMARY_RECORDS = 5082
REQUIRED_INTEGRITY_CHECKS = evidence_v1.INTEGRITY_POSITIVE_CHECKS
REQUIRED_NEGATIVE_CHECKS = evidence_v1.NEGATIVE_BOUNDARY_CHECKS


class PublicPrimaryMergeReviewV2Error(ValueError):
    """当公开主要论据无法安全合并时抛出的异常。"""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicPrimaryMergeReviewV2Error(
            f"{path}: expected an object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicPrimaryMergeReviewV2Error(
            f"missing primary merge artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
    )


def _validate_shard_evidence(
    value: Mapping[str, Any],
    *,
    shard: Mapping[str, Any],
    recovery_candidate_manifest_sha256: str,
) -> dict[str, Any]:
    index = int(shard["shard_index"])
    expected = int(shard["records"])
    positives = value.get("integrity_positive_checks")
    negatives = value.get("negative_boundary_checks")
    quality = value.get("claim_quality")
    if (
        value.get("schema_version") != evidence_v1.SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("status")
        != "public_shard_evidence_integrity_pass"
        or value.get("shard_index") != index
        or value.get("run_id") != shard["run_id"]
        or value.get("candidate_manifest_sha256")
        != recovery_candidate_manifest_sha256
        or value.get("expected_records") != expected
        or value.get("observed_records") != expected
        or value.get("public_evidence_integrity_gate_passed") is not True
        or value.get("scientific_result_admission_authorized") is not False
        or not isinstance(positives, Mapping)
        or set(positives) != REQUIRED_INTEGRITY_CHECKS
        or any(positives[name] is not True for name in positives)
        or not isinstance(negatives, Mapping)
        or set(negatives) != REQUIRED_NEGATIVE_CHECKS
        or any(negatives[name] is not False for name in negatives)
        or not isinstance(quality, Mapping)
    ):
        raise PublicPrimaryMergeReviewV2Error(
            f"primary shard {index} evidence review drift"
        )
    quality_passed = quality.get("frozen_one_percent_gate_passed")
    if (
        not isinstance(quality_passed, bool)
        or quality.get("frozen_one_percent_gate_waived") is not False
        or quality.get("clean_mechanism_quality_claim_eligible")
        is not quality_passed
        or quality.get("empirical_security_utility_fallback_only")
        is not (not quality_passed)
    ):
        raise PublicPrimaryMergeReviewV2Error(
            f"primary shard {index} claim-quality routing drift"
        )
    diagnostics = value.get("diagnostic_records")
    if (
        not isinstance(diagnostics, int)
        or isinstance(diagnostics, bool)
        or not 0 <= diagnostics <= expected
    ):
        raise PublicPrimaryMergeReviewV2Error(
            f"primary shard {index} diagnostic count drift"
        )
    return copy.deepcopy(dict(value))


def assemble_primary_merge_review(
    *,
    candidate: Mapping[str, Any],
    canary_review: Mapping[str, Any],
    shard_evidence_reviews: Sequence[Mapping[str, Any]],
    recovery_candidate_manifests: Sequence[str],
    artifact_locks: Sequence[Mapping[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    candidate = continuation_v2.validate_candidate(candidate)
    shards = candidate["scope"]["shards"]
    if (
        len(shards) != 4
        or len(shard_evidence_reviews) != 4
        or len(recovery_candidate_manifests) != 4
        or sum(int(shard["records"]) for shard in shards)
        != EXPECTED_CONTINUATION_RECORDS
    ):
        raise PublicPrimaryMergeReviewV2Error(
            "primary shard coverage drift"
        )
    canary = merge_v1._validate_canary_review(canary_review)
    validated = [
        _validate_shard_evidence(
            review,
            shard=shard,
            recovery_candidate_manifest_sha256=recovery_manifest,
        )
        for review, shard, recovery_manifest in zip(
            shard_evidence_reviews,
            shards,
            recovery_candidate_manifests,
            strict=True,
        )
    ]
    diagnostics = sum(
        int(review["diagnostic_records"]) for review in validated
    )
    continuation_calls = sum(
        int(review["provider_calls_completed"]) for review in validated
    )
    continuation_cost = sum(
        float(review["role_cumulative_cost_cny"])
        for review in validated
    )
    clean_quality = all(
        review["claim_quality"][
            "clean_mechanism_quality_claim_eligible"
        ]
        is True
        for review in validated
    )
    checks = {
        "canary_technical_gate_passed": True,
        "four_shard_evidence_integrity_gates_passed": True,
        "exact_primary_record_coverage": True,
        "continuation_partition_disjoint": True,
        "fresh_v2_identities_only": True,
        "all_attempts_terminal": True,
        "all_records_retained_in_itt": True,
        "all_tiers_candidate_or_diagnostic": True,
        "all_budget_and_trace_cross_bindings_complete": True,
        "all_budgets_unpaused": True,
        "scientific_outcome_boundary_preserved": True,
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "outcome_blind_public_primary_evidence_merge",
        "generated_at": generated_at,
        "status": (
            "primary_evidence_merge_pass_result_access_still_sealed"
        ),
        "model_role": "primary",
        "model_id": candidate["scope"]["model_id"],
        "source_continuation_candidate_manifest_sha256": candidate[
            "manifest_sha256"
        ],
        "coverage": {
            "canary_records": EXPECTED_CANARY_RECORDS,
            "continuation_records": EXPECTED_CONTINUATION_RECORDS,
            "primary_records": EXPECTED_PRIMARY_RECORDS,
            "shard_records": [
                int(review["observed_records"]) for review in validated
            ],
            "diagnostic_records": diagnostics,
            "diagnostic_fraction": (
                diagnostics / EXPECTED_PRIMARY_RECORDS
            ),
        },
        "operational_totals": {
            "provider_calls_completed": (
                int(canary["provider_calls_completed"])
                + continuation_calls
            ),
            "role_cumulative_cost_cny": round(
                float(canary["role_cumulative_cost_cny"])
                + continuation_cost,
                7,
            ),
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
        },
        "claim_quality": {
            "all_shards_frozen_one_percent_gate_passed": clean_quality,
            "frozen_one_percent_gate_waived": False,
            "clean_mechanism_quality_claim_eligible": clean_quality,
            "empirical_security_utility_fallback_only": (
                not clean_quality
            ),
        },
        "checks": checks,
        "checks_sha256": sha256_canonical_json(checks),
        "artifact_locks": [
            copy.deepcopy(dict(lock)) for lock in artifact_locks
        ],
        "authorization": {
            "primary_evidence_integrity_complete": True,
            "ready_for_independent_result_admission": True,
            "scientific_outcome_access_authorized": False,
            "result_admission_authorized": False,
            "second_role_execution_authorized": False,
        },
        "review_boundary": {
            "scientific_outcomes_accessed": False,
            "unsafe_effect_aggregated": False,
            "task_completion_aggregated": False,
            "condition_effects_compared": False,
            "diagnostic_rows_excluded": 0,
            "terminal_rows_retried": 0,
            "quality_gate_waived": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def build_primary_merge_review(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    candidate = continuation_v2.verify_candidate()
    canary_path = merge_v1.CANARY_REVIEW_PATH
    canary = _load_json(canary_path)
    evidence_reviews: list[dict[str, Any]] = []
    recovery_manifests: list[str] = []
    paths: list[Path] = [
        continuation_v2.CANDIDATE_PATH,
        canary_path,
    ]
    for shard in candidate["scope"]["shards"]:
        index = int(shard["shard_index"])
        candidate_path = recovery_v3.candidate_path(index)
        admission_path = recovery_v3.admission_path(index)
        recovery_candidate = _load_json(candidate_path)
        evidence_path = (
            PROJECT_ROOT
            / str(shard["output_root"])
            / evidence_v1.OUTPUT_NAME
        )
        evidence_reviews.append(_load_json(evidence_path))
        recovery_manifests.append(
            str(recovery_candidate["manifest_sha256"])
        )
        paths.extend([candidate_path, admission_path, evidence_path])
    return assemble_primary_merge_review(
        candidate=candidate,
        canary_review=canary,
        shard_evidence_reviews=evidence_reviews,
        recovery_candidate_manifests=recovery_manifests,
        artifact_locks=[_lock(path) for path in paths],
        generated_at=generated_at or continuation_v2.live_v4._now(),
    )


def write_primary_merge_review(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    value = build_primary_merge_review()
    _write_json(path, value)
    return value


def verify_primary_merge_review(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    observed = _load_json(path)
    expected = build_primary_merge_review(
        generated_at=str(observed.get("generated_at"))
    )
    if observed != expected:
        raise PublicPrimaryMergeReviewV2Error(
            "public primary merge review drift"
        )
    return copy.deepcopy(observed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = (
        verify_primary_merge_review(args.output)
        if args.verify
        else write_primary_merge_review(args.output)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
