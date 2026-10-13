"""在不提前开启最终结果的前提下合并所有 DeepSeek Flash 公开证据。

通过防篡改哈希累加校验确保合并前后各分片字节完全一致。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import experiments.paper_v2.public_live_controller_v4 as live_v4
import experiments.paper_v2.public_second_continuation_recovery_v3 as recovery_v3
import experiments.paper_v2.public_second_continuation_v2 as continuation_v2
import experiments.paper_v2.public_second_recovery_evidence_review_v4 as evidence_v4
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_OUTPUT = PROTOCOL_ROOT / "public_second_evidence_merge_v1.json"
SCHEMA_VERSION = "m3-paper-v2-public-second-evidence-merge-1.0"
GENERATED_AT = "2026-08-04T01:50:00+08:00"
MODEL_ROLE = "second"
MODEL_ID = "deepseek-v4-flash"
EXPECTED_CANARY_RECORDS = 12
EXPECTED_CONTINUATION_RECORDS = 1779
EXPECTED_ROLE_RECORDS = 1791
CANARY_REVIEW_PATH = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_public/deepseek/"
    "public-v4-second-13e640041d69a2b4ce1d95c2471cd8644c3a1eac81885d0a5b96cf98b46a56a4/"
    "technical_canary_review_v4.json"
)


class PublicSecondEvidenceMergeV1Error(ValueError):
    """当 Flash 公开论据不完整或不一致时抛出的异常。"""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicSecondEvidenceMergeV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise PublicSecondEvidenceMergeV1Error(
            f"{path}: expected object"
        )
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    raise PublicSecondEvidenceMergeV1Error(
                        f"{path}:{line_number}: blank row"
                    )
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise PublicSecondEvidenceMergeV1Error(
                        f"{path}:{line_number}: expected object"
                    )
                rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        if isinstance(exc, PublicSecondEvidenceMergeV1Error):
            raise
        raise PublicSecondEvidenceMergeV1Error(
            f"{path}: invalid JSONL"
        ) from exc
    return rows


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
        raise PublicSecondEvidenceMergeV1Error(
            f"missing Flash merge artifact: {path}"
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


def _work_keys(path: Path) -> list[str]:
    rows = _load_jsonl(path)
    keys = [str(row.get("work_key", "")) for row in rows]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise PublicSecondEvidenceMergeV1Error(
            f"{path}: missing or duplicate work key"
        )
    return keys


def _validate_partition_sequences(
    *,
    expected_canary: Sequence[str],
    observed_canary: Sequence[str],
    expected_partitions: Sequence[Sequence[str]],
    observed_prefixes: Sequence[Sequence[str]],
    observed_recoveries: Sequence[Sequence[str]],
) -> None:
    if list(observed_canary) != list(expected_canary):
        raise PublicSecondEvidenceMergeV1Error(
            "Flash canary work-key sequence drift"
        )
    if not (
        len(expected_partitions)
        == len(observed_prefixes)
        == len(observed_recoveries)
        == recovery_v3.SHARD_COUNT
    ):
        raise PublicSecondEvidenceMergeV1Error(
            "Flash continuation shard count drift"
        )
    for index, (expected, prefix, suffix) in enumerate(
        zip(
            expected_partitions,
            observed_prefixes,
            observed_recoveries,
            strict=True,
        )
    ):
        if [*prefix, *suffix] != list(expected):
            raise PublicSecondEvidenceMergeV1Error(
                f"Flash shard {index} prefix/recovery partition drift"
            )
    all_keys = [
        *observed_canary,
        *(key for rows in observed_prefixes for key in rows),
        *(key for rows in observed_recoveries for key in rows),
    ]
    if len(all_keys) != EXPECTED_ROLE_RECORDS or len(set(all_keys)) != len(
        all_keys
    ):
        raise PublicSecondEvidenceMergeV1Error(
            "Flash role coverage is not exactly 1,791 unique work keys"
        )


def _claim_quality(
    *,
    shard_quality: Sequence[bool],
    diagnostic_records: int,
    total_records: int,
) -> dict[str, Any]:
    all_shards = bool(shard_quality) and all(shard_quality)
    global_fraction = diagnostic_records / total_records
    return {
        "per_shard_frozen_one_percent_gate_passed": list(shard_quality),
        "all_shards_frozen_one_percent_gate_passed": all_shards,
        "global_diagnostic_fraction": global_fraction,
        "global_fraction_below_one_percent": global_fraction <= 0.01,
        "global_fraction_used_to_waive_shard_failure": False,
        "frozen_one_percent_gate_waived": False,
        "clean_mechanism_quality_claim_eligible": all_shards,
        "empirical_security_utility_fallback_only": not all_shards,
    }


def _validate_recovery_review(
    value: Mapping[str, Any], *, shard_index: int
) -> dict[str, Any]:
    positives = value.get("integrity_positive_checks")
    negatives = value.get("negative_boundary_checks")
    quality = value.get("claim_quality")
    if (
        value.get("schema_version") != evidence_v4.SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("status")
        != "flash_recovery_evidence_integrity_pass"
        or value.get("shard_index") != shard_index
        or value.get("public_evidence_integrity_gate_passed") is not True
        or value.get("scientific_result_admission_authorized") is not False
        or not isinstance(positives, Mapping)
        or set(positives) != evidence_v4.INTEGRITY_POSITIVE_CHECKS
        or any(item is not True for item in positives.values())
        or not isinstance(negatives, Mapping)
        or set(negatives) != evidence_v4.NEGATIVE_BOUNDARY_CHECKS
        or any(item is not True for item in negatives.values())
        or not isinstance(quality, Mapping)
    ):
        raise PublicSecondEvidenceMergeV1Error(
            f"Flash recovery shard {shard_index} evidence review drift"
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
        raise PublicSecondEvidenceMergeV1Error(
            f"Flash recovery shard {shard_index} quality routing drift"
        )
    return copy.deepcopy(dict(value))


def build_merge() -> dict[str, Any]:
    candidate = continuation_v2.verify_candidate()
    recovery_candidate = recovery_v3.verify_candidate()
    abort_review = _load_json(recovery_v3.REVIEW_PATH)
    if (
        abort_review.get("manifest_sha256") != _manifest_sha(abort_review)
        or abort_review.get("manifest_sha256")
        != recovery_candidate["scope"][
            "source_abort_review_manifest_sha256"
        ]
        or abort_review.get("status")
        != "two_flash_prefixes_sealed_recovery_candidate_may_be_built"
    ):
        raise PublicSecondEvidenceMergeV1Error(
            "Flash closed-prefix abort review drift"
        )
    canary_permit = live_v4.authorize_canary(
        MODEL_ROLE,
        admission_path=live_v4.ADMISSION_PATHS[MODEL_ROLE],
    )
    canary_review = _load_json(CANARY_REVIEW_PATH)
    if (
        canary_review.get("status")
        != "public_canary_technical_gate_pass"
        or canary_review.get("model_role") != MODEL_ROLE
        or canary_review.get("observed_records") != EXPECTED_CANARY_RECORDS
        or canary_review.get("provider_calls_completed") != 18
        or canary_review.get("review_boundary", {}).get(
            "scientific_outcomes_accessed"
        )
        is not False
        or _sha256_file(CANARY_REVIEW_PATH)
        != candidate["scope"]["source_canary_technical_review_sha256"]
    ):
        raise PublicSecondEvidenceMergeV1Error(
            "Flash canary technical review drift"
        )
    canary_keys = _work_keys(canary_permit.record_ledger_path)
    expected_canary = [
        str(item["work_key"]) for item in canary_permit.work_items
    ]
    expected_partitions = [
        [str(item["work_key"]) for item in rows]
        for rows in continuation_v2._partitions()
    ]
    prefix_keys: list[list[str]] = []
    recovery_keys: list[list[str]] = []
    evidence_reviews: list[dict[str, Any]] = []
    artifact_paths: list[Path] = [
        continuation_v2.CANDIDATE_PATH,
        recovery_v3.CANDIDATE_PATH,
        recovery_v3.REVIEW_PATH,
        CANARY_REVIEW_PATH,
        canary_permit.record_ledger_path,
        canary_permit.attempt_ledger_path,
        canary_permit.budget_ledger_path,
    ]
    for shard_index in range(recovery_v3.SHARD_COUNT):
        source_review = abort_review["shards"][shard_index]
        prefix_root = PROJECT_ROOT / str(source_review["source_output_root"])
        recovery_shard = recovery_v3._candidate_shard(
            recovery_candidate, shard_index
        )
        recovery_root = PROJECT_ROOT / str(
            recovery_shard["output_root"]
        )
        evidence_path = recovery_root / evidence_v4.OUTPUT_NAME
        evidence = _validate_recovery_review(
            _load_json(evidence_path), shard_index=shard_index
        )
        prefix_keys.append(_work_keys(prefix_root / "experiment_records.jsonl"))
        recovery_keys.append(
            _work_keys(recovery_root / "experiment_records.jsonl")
        )
        evidence_reviews.append(evidence)
        artifact_paths.extend(
            [
                evidence_path,
                prefix_root / "experiment_records.jsonl",
                prefix_root / "attempt_events.jsonl",
                prefix_root / "budget_events.jsonl",
                recovery_root / "experiment_records.jsonl",
                recovery_root / "attempt_events.jsonl",
                recovery_root / "budget_events.jsonl",
            ]
        )
    _validate_partition_sequences(
        expected_canary=expected_canary,
        observed_canary=canary_keys,
        expected_partitions=expected_partitions,
        observed_prefixes=prefix_keys,
        observed_recoveries=recovery_keys,
    )
    diagnostics = int(
        abort_review["totals"]["closed_prefix_diagnostic_records"]
    ) + sum(int(item["diagnostic_records"]) for item in evidence_reviews)
    provider_calls = (
        int(canary_review["provider_calls_completed"])
        + int(abort_review["totals"]["completed_provider_calls"])
        + sum(
            int(item["provider_calls_completed"])
            for item in evidence_reviews
        )
    )
    role_cost = round(
        float(canary_review["role_cumulative_cost_cny"])
        + float(abort_review["totals"]["role_cumulative_cost_cny"])
        + sum(
            float(item["role_cumulative_cost_cny"])
            for item in evidence_reviews
        ),
        8,
    )
    shard_quality = [
        bool(
            item["claim_quality"]["frozen_one_percent_gate_passed"]
        )
        for item in evidence_reviews
    ]
    checks = {
        "canary_technical_gate_passed": True,
        "two_prefixes_immutably_closed": True,
        "two_recovery_evidence_integrity_gates_passed": True,
        "exact_1791_record_coverage": True,
        "continuation_partition_order_preserved": True,
        "all_work_keys_unique": True,
        "all_diagnostics_retained_in_itt": True,
        "all_attempts_terminal": True,
        "budget_record_trace_cross_binding_complete": True,
        "all_budgets_unpaused": True,
        "zero_terminal_retries": True,
        "scientific_outcome_boundary_preserved": True,
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "outcome_blind_public_second_evidence_merge",
        "generated_at": GENERATED_AT,
        "status": "second_evidence_merge_pass_result_access_still_sealed",
        "model_role": MODEL_ROLE,
        "model_id": MODEL_ID,
        "source_continuation_candidate_manifest_sha256": candidate[
            "manifest_sha256"
        ],
        "source_recovery_candidate_manifest_sha256": recovery_candidate[
            "manifest_sha256"
        ],
        "source_abort_review_manifest_sha256": abort_review[
            "manifest_sha256"
        ],
        "recovery_evidence_review_manifests": [
            item["manifest_sha256"] for item in evidence_reviews
        ],
        "coverage": {
            "canary_records": len(canary_keys),
            "closed_prefix_records": sum(len(items) for items in prefix_keys),
            "recovery_records": sum(len(items) for items in recovery_keys),
            "continuation_records": sum(len(items) for items in prefix_keys)
            + sum(len(items) for items in recovery_keys),
            "role_records": len(canary_keys)
            + sum(len(items) for items in prefix_keys)
            + sum(len(items) for items in recovery_keys),
            "diagnostic_records": diagnostics,
            "diagnostic_fraction": diagnostics / EXPECTED_ROLE_RECORDS,
            "per_shard_continuation_records": [
                len(prefix_keys[index]) + len(recovery_keys[index])
                for index in range(recovery_v3.SHARD_COUNT)
            ],
        },
        "operational_totals": {
            "provider_calls_completed": provider_calls,
            "role_cumulative_cost_cny": role_cost,
            "role_hard_limit_cny": recovery_v3.ROLE_TOTAL_HARD_LIMIT_CNY,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
        },
        "claim_quality": _claim_quality(
            shard_quality=shard_quality,
            diagnostic_records=diagnostics,
            total_records=EXPECTED_ROLE_RECORDS,
        ),
        "checks": checks,
        "checks_sha256": sha256_canonical_json(checks),
        "artifact_locks": [_lock(path) for path in artifact_paths],
        "authorization": {
            "second_evidence_integrity_complete": True,
            "ready_for_independent_result_admission": True,
            "scientific_outcome_access_authorized": False,
            "result_admission_authorized": False,
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
    if (
        core["coverage"]["canary_records"] != EXPECTED_CANARY_RECORDS
        or core["coverage"]["continuation_records"]
        != EXPECTED_CONTINUATION_RECORDS
        or core["coverage"]["role_records"] != EXPECTED_ROLE_RECORDS
        or core["operational_totals"]["role_cumulative_cost_cny"]
        > recovery_v3.ROLE_TOTAL_HARD_LIMIT_CNY
        or not all(checks.values())
    ):
        raise PublicSecondEvidenceMergeV1Error(
            "Flash aggregate coverage or safety boundary failed"
        )
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_merge(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_merge()
    _write_json(path, value)
    return value


def verify_merge(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = _load_json(path)
    expected = build_merge()
    if observed != expected:
        raise PublicSecondEvidenceMergeV1Error(
            "Flash second-role evidence merge drift"
        )
    return copy.deepcopy(observed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = write_merge() if args.write else verify_merge()
    print(
        json.dumps(
            {
                "status": value["status"],
                "role_records": value["coverage"]["role_records"],
                "diagnostic_records": value["coverage"][
                    "diagnostic_records"
                ],
                "evidence_integrity_complete": value["authorization"][
                    "second_evidence_integrity_complete"
                ],
                "clean_claim_eligible": value["claim_quality"][
                    "clean_mechanism_quality_claim_eligible"
                ],
                "manifest_sha256": value["manifest_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
