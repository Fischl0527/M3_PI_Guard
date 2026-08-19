"""Outcome-blind technical merge gate for the public primary role."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.public_sharded_continuation_v2 as continuation_v2
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
SCHEMA_PATH = (
    PROJECT_ROOT
    / "schemas/paper_v2/public_primary_merge_review_v1.schema.json"
)
DEFAULT_OUTPUT = PROTOCOL_ROOT / "public_primary_merge_review_v1.json"
CANARY_REVIEW_PATH = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_public/deepseek"
    / (
        "public-v4-primary-"
        "4b717417fec675c3540d186e4b6d6af403bb03c208ebc91e1b1e84b1e7e83e30"
    )
    / "technical_canary_review_v4.json"
)
SCHEMA_VERSION = "m3-paper-v2-public-primary-merge-review-1.0"
EXPECTED_CANARY_RECORDS = 24
EXPECTED_CONTINUATION_RECORDS = 5058
EXPECTED_PRIMARY_RECORDS = 5082
REQUIRED_SHARD_CHECKS = {
    "exact_record_count",
    "all_attempts_terminal",
    "all_result_tiers_formal_candidate",
    "budget_not_paused",
    "budget_and_records_cross_bound",
    "terminal_canary_rows_excluded",
    "old_v1_records_excluded",
    "exact_shard_policy_used_for_state_reconstruction",
}
REQUIRED_CANARY_CHECKS = {
    "exact_record_count",
    "all_attempts_terminal",
    "all_operational_status_completed",
    "all_provider_requests_completed",
    "all_result_tiers_formal_candidate",
    "all_safety_receipts_isolated",
    "all_trace_bundles_completed",
    "budget_and_records_cross_bound",
    "budget_not_paused",
}
REQUIRED_BOUNDARY_FALSE = {
    "scientific_outcomes_accessed",
    "unsafe_effect_aggregated",
    "task_completion_aggregated",
    "condition_effects_compared",
    "result_admission_authorized",
}


class PublicPrimaryMergeReviewError(ValueError):
    """Raised when the primary technical merge cannot fail closed."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicPrimaryMergeReviewError(f"{path}: expected an object")
    return value


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
        raise PublicPrimaryMergeReviewError(
            f"missing primary merge artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _validate_usage(value: Any, *, label: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise PublicPrimaryMergeReviewError(f"{label}: usage must be an object")
    required = {
        "prompt_tokens",
        "completion_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
    }
    if set(value) != required:
        raise PublicPrimaryMergeReviewError(f"{label}: usage fields drift")
    usage: dict[str, int] = {}
    for key in sorted(required):
        child = value[key]
        if isinstance(child, bool) or not isinstance(child, int) or child < 0:
            raise PublicPrimaryMergeReviewError(
                f"{label}: invalid usage field {key}"
            )
        usage[key] = child
    if (
        usage["prompt_cache_hit_tokens"]
        + usage["prompt_cache_miss_tokens"]
        != usage["prompt_tokens"]
    ):
        raise PublicPrimaryMergeReviewError(
            f"{label}: prompt cache accounting drift"
        )
    return usage


def _validate_boundary(value: Any, *, label: str) -> None:
    if not isinstance(value, Mapping):
        raise PublicPrimaryMergeReviewError(
            f"{label}: review boundary must be an object"
        )
    if not REQUIRED_BOUNDARY_FALSE.issubset(value):
        raise PublicPrimaryMergeReviewError(
            f"{label}: review boundary fields missing"
        )
    if any(value[key] is not False for key in REQUIRED_BOUNDARY_FALSE):
        raise PublicPrimaryMergeReviewError(
            f"{label}: scientific outcome boundary was crossed"
        )


def _validate_checks(
    value: Any,
    *,
    required: set[str],
    label: str,
) -> None:
    if not isinstance(value, Mapping) or set(value) != required:
        raise PublicPrimaryMergeReviewError(
            f"{label}: technical checks drift"
        )
    if any(value[key] is not True for key in required):
        raise PublicPrimaryMergeReviewError(
            f"{label}: technical check failed"
        )


def _validate_canary_review(value: Mapping[str, Any]) -> dict[str, Any]:
    if (
        value.get("schema_version")
        != "m3-paper-v2-public-canary-technical-review-4.0"
        or value.get("status") != "public_canary_technical_gate_pass"
        or value.get("model_role") != "primary"
        or value.get("expected_records") != EXPECTED_CANARY_RECORDS
        or value.get("observed_records") != EXPECTED_CANARY_RECORDS
        or value.get("matrix_continuation_eligible") is not True
    ):
        raise PublicPrimaryMergeReviewError("primary canary review drift")
    _validate_checks(
        value.get("checks"),
        required=REQUIRED_CANARY_CHECKS,
        label="primary canary",
    )
    _validate_boundary(
        value.get("review_boundary"),
        label="primary canary",
    )
    calls = value.get("provider_calls_completed")
    cost = value.get("role_cumulative_cost_cny")
    if (
        isinstance(calls, bool)
        or not isinstance(calls, int)
        or calls < EXPECTED_CANARY_RECORDS
        or isinstance(cost, bool)
        or not isinstance(cost, (int, float))
        or not 0 <= float(cost) < 20.0
    ):
        raise PublicPrimaryMergeReviewError(
            "primary canary operational totals drift"
        )
    _validate_usage(
        value.get("role_cumulative_usage"),
        label="primary canary",
    )
    return copy.deepcopy(dict(value))


def _validate_shard_review(
    value: Mapping[str, Any],
    *,
    shard: Mapping[str, Any],
    admission_file_sha256: str,
    candidate_manifest_sha256: str,
) -> dict[str, Any]:
    shard_index = shard["shard_index"]
    expected = shard["records"]
    if (
        value.get("schema_version")
        != "m3-paper-v2-public-continuation-shard-review-2.0"
        or value.get("status")
        != "fresh_continuation_shard_technical_gate_pass"
        or value.get("model_role") != "primary"
        or value.get("shard_index") != shard_index
        or value.get("run_id") != shard["run_id"]
        or value.get("candidate_manifest_sha256")
        != candidate_manifest_sha256
        or value.get("admission_file_sha256")
        != admission_file_sha256
        or value.get("expected_records") != expected
        or value.get("observed_records") != expected
        or value.get("result_admission_eligible") is not True
    ):
        raise PublicPrimaryMergeReviewError(
            f"primary shard {shard_index} review drift"
        )
    _validate_checks(
        value.get("checks"),
        required=REQUIRED_SHARD_CHECKS,
        label=f"primary shard {shard_index}",
    )
    _validate_boundary(
        value.get("review_boundary"),
        label=f"primary shard {shard_index}",
    )
    calls = value.get("provider_calls_completed")
    cost = value.get("role_cumulative_cost_cny")
    if (
        isinstance(calls, bool)
        or not isinstance(calls, int)
        or calls < expected
        or isinstance(cost, bool)
        or not isinstance(cost, (int, float))
        or not 0 <= float(cost) <= continuation_v2.SHARD_HARD_LIMIT_CNY
    ):
        raise PublicPrimaryMergeReviewError(
            f"primary shard {shard_index} operational totals drift"
        )
    _validate_usage(
        value.get("role_cumulative_usage"),
        label=f"primary shard {shard_index}",
    )
    return copy.deepcopy(dict(value))


def _sum_usage(values: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": 0,
    }
    for index, value in enumerate(values):
        usage = _validate_usage(value, label=f"usage source {index}")
        for key in totals:
            totals[key] += usage[key]
    return totals


def assemble_primary_merge_review(
    *,
    candidate: Mapping[str, Any],
    canary_review: Mapping[str, Any],
    shard_reviews: Sequence[Mapping[str, Any]],
    admission_file_sha256s: Sequence[str],
    artifact_locks: Sequence[Mapping[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    candidate = continuation_v2.validate_candidate(candidate)
    shards = candidate["scope"]["shards"]
    if (
        len(shards) != continuation_v2.SHARD_COUNT
        or len(shard_reviews) != continuation_v2.SHARD_COUNT
        or len(admission_file_sha256s) != continuation_v2.SHARD_COUNT
    ):
        raise PublicPrimaryMergeReviewError("primary shard cardinality drift")
    if (
        sum(int(item["records"]) for item in shards)
        != EXPECTED_CONTINUATION_RECORDS
        or len({item["execution_identity"] for item in shards}) != 4
        or len({item["work_key_sequence_sha256"] for item in shards}) != 4
    ):
        raise PublicPrimaryMergeReviewError(
            "primary continuation partition drift"
        )
    canary = _validate_canary_review(canary_review)
    validated_shards = [
        _validate_shard_review(
            review,
            shard=shard,
            admission_file_sha256=admission_sha,
            candidate_manifest_sha256=candidate["manifest_sha256"],
        )
        for review, shard, admission_sha in zip(
            shard_reviews,
            shards,
            admission_file_sha256s,
            strict=True,
        )
    ]
    provider_calls = int(canary["provider_calls_completed"]) + sum(
        int(value["provider_calls_completed"])
        for value in validated_shards
    )
    cost_cny = round(
        float(canary["role_cumulative_cost_cny"])
        + sum(
            float(value["role_cumulative_cost_cny"])
            for value in validated_shards
        ),
        7,
    )
    usage = _sum_usage(
        [
            canary["role_cumulative_usage"],
            *[
                value["role_cumulative_usage"]
                for value in validated_shards
            ],
        ]
    )
    checks = {
        "canary_technical_gate_passed": True,
        "four_shard_technical_gates_passed": True,
        "exact_primary_record_coverage": True,
        "continuation_partition_disjoint": True,
        "fresh_v2_identities_only": True,
        "old_v1_records_excluded": True,
        "all_attempts_terminal": True,
        "all_records_formal_candidate": True,
        "all_budget_ledgers_cross_bound": True,
        "all_budgets_unpaused": True,
        "scientific_outcome_boundary_preserved": True,
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "primary_technical_merge_pass_result_access_still_sealed",
        "model_role": "primary",
        "model_id": candidate["scope"]["model_id"],
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "coverage": {
            "canary_records": EXPECTED_CANARY_RECORDS,
            "continuation_records": EXPECTED_CONTINUATION_RECORDS,
            "primary_records": EXPECTED_PRIMARY_RECORDS,
            "shard_records": [
                int(value["observed_records"])
                for value in validated_shards
            ],
        },
        "operational_totals": {
            "provider_calls_completed": provider_calls,
            "role_cumulative_usage": usage,
            "role_cumulative_cost_cny": cost_cny,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
        },
        "checks": checks,
        "artifact_locks": [copy.deepcopy(dict(item)) for item in artifact_locks],
        "authorization": {
            "primary_technical_evidence_complete": True,
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
            "selective_record_reuse": False,
        },
        "checks_sha256": sha256_canonical_json(checks),
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def build_primary_merge_review(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    candidate = continuation_v2.verify_candidate()
    canary_review = _load_json(CANARY_REVIEW_PATH)
    shard_reviews: list[dict[str, Any]] = []
    admission_hashes: list[str] = []
    review_paths: list[Path] = []
    admission_paths: list[Path] = []
    for shard in candidate["scope"]["shards"]:
        index = int(shard["shard_index"])
        root = PROJECT_ROOT / str(shard["output_root"])
        review_path = root / "continuation_shard_review_v2.json"
        admission = continuation_v2.admission_path("primary", index)
        review_paths.append(review_path)
        admission_paths.append(admission)
        shard_reviews.append(_load_json(review_path))
        admission_hashes.append(_sha256_file(admission))
    locks = [
        _lock(continuation_v2.CANDIDATE_PATH),
        _lock(CANARY_REVIEW_PATH),
        *[_lock(path) for path in admission_paths],
        *[_lock(path) for path in review_paths],
    ]
    return assemble_primary_merge_review(
        candidate=candidate,
        canary_review=canary_review,
        shard_reviews=shard_reviews,
        admission_file_sha256s=admission_hashes,
        artifact_locks=locks,
        generated_at=generated_at or continuation_v2.live_v4._now(),
    )


def _validate_schema(value: Mapping[str, Any]) -> None:
    schema = _load_json(SCHEMA_PATH)
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(value),
        key=lambda error: list(error.path),
    )
    if errors:
        raise PublicPrimaryMergeReviewError(
            "primary merge schema failure: " + errors[0].message
        )


def validate_primary_merge_review(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicPrimaryMergeReviewError(
            "primary merge review must be an object"
        )
    result = copy.deepcopy(dict(value))
    _validate_schema(result)
    core = {
        key: child
        for key, child in result.items()
        if key != "manifest_sha256"
    }
    if result["manifest_sha256"] != sha256_canonical_json(core):
        raise PublicPrimaryMergeReviewError(
            "primary merge manifest drift"
        )
    expected = build_primary_merge_review(
        generated_at=str(result["generated_at"])
    )
    if result != expected:
        raise PublicPrimaryMergeReviewError(
            "primary merge source evidence drift"
        )
    return result


def write_primary_merge_review(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    value = build_primary_merge_review()
    _validate_schema(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def verify_primary_merge_review(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    return validate_primary_merge_review(_load_json(path))


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
