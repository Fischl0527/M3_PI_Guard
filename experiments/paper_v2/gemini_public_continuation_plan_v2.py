"""感知失败状态与旧版本替代的 Gemini 公开基准接续调度计划。

动态识别由于提供商临时宕机失败的用例并纳入重试接续队列。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.gemini_public_continuation_plan_v1 as plan_v1
import experiments.paper_v2.gemini_public_technical_review_v5 as review_v5
from experiments.paper_v2.contracts import canonical_json_bytes, sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/gemini_public_continuation_candidate_v2.json"
)
TEST_PATH = (
    PROJECT_ROOT
    / "tests/unit/test_paper_v2_gemini_public_continuation_plan_v2.py"
)
SCHEMA_VERSION = "m3-paper-v2-gemini-public-continuation-plan-2.0"
GENERATED_AT = "2026-08-03T13:00:00+08:00"


class GeminiPublicContinuationPlanV2Error(ValueError):
    """当感知失败的接续候选对象发生漂移时抛出的异常。"""


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiPublicContinuationPlanV2Error(
            f"missing Gemini continuation v2 source: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock.get("path", ""))).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise GeminiPublicContinuationPlanV2Error(
            "Gemini continuation v2 lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock.get("bytes")
        or _sha256_file(path) != lock.get("sha256")
    ):
        raise GeminiPublicContinuationPlanV2Error(
            f"Gemini continuation v2 source drift: {path}"
        )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiPublicContinuationPlanV2Error(f"{path}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise GeminiPublicContinuationPlanV2Error(f"{path}: expected object")
    return value


def build_candidate() -> dict[str, Any]:
    source = plan_v1.verify_candidate()
    schedule = plan_v1._read_jsonl(plan_v1.SCHEDULE_PATH)
    schedule_status = plan_v1.validate_schedule(schedule)
    if (
        schedule_status["record_count"] != 1_779
        or schedule_status["quota_segment_count"] != 1_186
        or schedule_status["logical_shard_segment_counts"]
        != [297, 297, 296, 296]
    ):
        raise GeminiPublicContinuationPlanV2Error(
            "Gemini v1 continuation schedule shape drift"
        )
    scope = {
        "provider_id": "gemini",
        "model_id": "gemini-3.6-flash",
        "model_role": "second",
        "matrix_records": 1_791,
        "formal_canary_prefix_records": 12,
        "pending_only_records": 1_779,
        "logical_shard_count": 4,
        "logical_shard_segment_counts": [297, 297, 296, 296],
        "standard_free_tier_quota_segments": 1_186,
        "minimum_standard_quota_days_after_canary": 1_186,
        "local_requests_per_day": 18,
        "one_formal_segment_per_quota_day": True,
        "source_v1_candidate_manifest_sha256": source["manifest_sha256"],
        "source_schedule_sha256": _sha256_file(plan_v1.SCHEDULE_PATH),
        "pending_work_key_sequence_sha256": schedule_status[
            "work_key_sequence_sha256"
        ],
        "activation_gate": {
            "required_review_schema": review_v5.AGGREGATE_SCHEMA_VERSION,
            "required_status": "gemini_public_v5_canary_technical_gate_pass",
            "required_records": 12,
            "aggregate_review_path": _display_path(
                review_v5.AGGREGATE_REVIEW_PATH
            ),
            "v4_aggregate_gate_superseded": True,
        },
        "billing_tier": "free",
        "paid_ceiling_usd": 0.0,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "failure_aware_non_executable_gemini_continuation_candidate",
        "generated_at": GENERATED_AT,
        "status": "offline_qualified_pending_v5_canary_aggregate",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [
            _lock(Path(__file__)),
            _lock(TEST_PATH),
            _lock(Path(plan_v1.__file__)),
            _lock(plan_v1.CANDIDATE_PATH),
            _lock(plan_v1.SCHEDULE_PATH),
            _lock(Path(review_v5.__file__)),
        ],
        "authorization": {
            "candidate_only": True,
            "quota_segment_execution_authorized": False,
            "batch_api_authorized": False,
            "paid_billing_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_read": 0,
            "historical_schedule_rows_mutated": 0,
            "canary_work_keys_replayed": 0,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicContinuationPlanV2Error(
            "Gemini continuation v2 candidate missing"
        )
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}
    scope = value.get("scope")
    activation = scope.get("activation_gate", {}) if isinstance(scope, Mapping) else {}
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != sha256_canonical_json(core)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("matrix_records") != 1_791
        or scope.get("formal_canary_prefix_records") != 12
        or scope.get("pending_only_records") != 1_779
        or scope.get("standard_free_tier_quota_segments") != 1_186
        or scope.get("minimum_standard_quota_days_after_canary") != 1_186
        or activation.get("required_review_schema")
        != review_v5.AGGREGATE_SCHEMA_VERSION
        or activation.get("v4_aggregate_gate_superseded") is not True
        or scope.get("paid_ceiling_usd") != 0.0
        or value.get("authorization", {}).get("quota_segment_execution_authorized")
        is not False
        or value.get("authorization", {}).get("batch_api_authorized") is not False
        or value.get("authorization", {}).get("paid_billing_authorized") is not False
    ):
        raise GeminiPublicContinuationPlanV2Error(
            "Gemini continuation v2 candidate drift"
        )
    for lock in value.get("artifact_locks", []):
        _verify_lock(lock)
    return copy.deepcopy(dict(value))


def write_candidate() -> dict[str, Any]:
    value = build_candidate()
    CANDIDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_PATH.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def verify_candidate() -> dict[str, Any]:
    if not CANDIDATE_PATH.is_file():
        raise GeminiPublicContinuationPlanV2Error(
            "Gemini continuation v2 candidate missing"
        )
    observed = validate_candidate(_read_json(CANDIDATE_PATH))
    expected = build_candidate()
    if observed != expected:
        raise GeminiPublicContinuationPlanV2Error(
            "Gemini continuation v2 candidate source drift"
        )
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    args = parser.parse_args()
    value = write_candidate() if args.write_candidate else verify_candidate()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
