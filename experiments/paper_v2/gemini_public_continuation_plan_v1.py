"""离线仅挂起用例（Pending-Only）的 Gemini 公开基准接续调度表。

自动过滤已完成用例，仅保留未执行项组成接续队列。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import experiments.paper_v2.gemini_daily_quota_ledger_v1 as quota
import experiments.paper_v2.gemini_public_controller_v1 as public_v1
import experiments.paper_v2.gemini_public_controller_v4 as public_v4
from experiments.paper_v2.contracts import sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
SCHEDULE_PATH = PROTOCOL_ROOT / "gemini_public_continuation_schedule_v1.jsonl"
CANDIDATE_PATH = PROTOCOL_ROOT / "gemini_public_continuation_candidate_v1.json"
GENERATED_AT = "2026-08-02T12:08:00+08:00"
SCHEMA_VERSION = "m3-paper-v2-gemini-public-continuation-plan-1.0"
SCHEDULE_SCHEMA_VERSION = (
    "m3-paper-v2-gemini-public-continuation-quota-segment-1.0"
)
LOGICAL_SHARDS = 4
EXPECTED_PENDING_RECORDS = 1_779
EXPECTED_QUOTA_SEGMENTS = 1_186


class GeminiPublicContinuationPlanV1Error(ValueError):
    """当仅待处理的 Gemini 时间表发生漂移时抛出的异常。"""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiPublicContinuationPlanV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise GeminiPublicContinuationPlanV1Error(f"{path}: expected object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                raise GeminiPublicContinuationPlanV1Error(
                    f"{path}:{number}: blank row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise GeminiPublicContinuationPlanV1Error(
                    f"{path}:{number}: expected object"
                )
            rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiPublicContinuationPlanV1Error(
            f"{path}: invalid JSONL"
        ) from exc
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )
    path.write_text(encoded, encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiPublicContinuationPlanV1Error(
            f"missing continuation input: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock["path"])).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise GeminiPublicContinuationPlanV1Error(
            "continuation lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise GeminiPublicContinuationPlanV1Error(
            f"continuation lock drift: {path}"
        )


def _public_rows() -> list[dict[str, Any]]:
    rows = public_v1._read_jsonl(public_v1.GEMINI_PUBLIC_PLAN)
    if len(rows) != 1_791:
        raise GeminiPublicContinuationPlanV1Error(
            "Gemini public matrix count drift"
        )
    return rows


def _pending_rows() -> tuple[list[dict[str, Any]], list[str]]:
    rows = _public_rows()
    canary_keys = [str(row["work_key"]) for row in public_v1._canary_rows()]
    canary = set(canary_keys)
    pending = [row for row in rows if str(row["work_key"]) not in canary]
    pending_keys = [str(row["work_key"]) for row in pending]
    if (
        len(canary) != 12
        or len(pending) != EXPECTED_PENDING_RECORDS
        or len(set(pending_keys)) != len(pending_keys)
        or set(pending_keys).intersection(canary)
        or set(pending_keys).union(canary)
        != {str(row["work_key"]) for row in rows}
    ):
        raise GeminiPublicContinuationPlanV1Error(
            "Gemini canary/pending partition drift"
        )
    return pending, canary_keys


def _logical_shard_sizes(segment_count: int) -> list[int]:
    quotient, remainder = divmod(segment_count, LOGICAL_SHARDS)
    return [
        quotient + (1 if index < remainder else 0)
        for index in range(LOGICAL_SHARDS)
    ]


def build_schedule() -> list[dict[str, Any]]:
    pending, _ = _pending_rows()
    packed = public_v4._pack_rows(pending)
    if len(packed) != EXPECTED_QUOTA_SEGMENTS:
        raise GeminiPublicContinuationPlanV1Error(
            "Gemini quota-segment count drift"
        )
    sizes = _logical_shard_sizes(len(packed))
    shard_by_segment: list[int] = []
    for shard_index, size in enumerate(sizes):
        shard_by_segment.extend([shard_index] * size)
    rows: list[dict[str, Any]] = []
    for index, segment in enumerate(packed):
        keys = [str(row["work_key"]) for row in segment]
        maximum = sum(int(row["max_provider_calls"]) for row in segment)
        core = {
            "schema_version": SCHEDULE_SCHEMA_VERSION,
            "quota_segment_index": index,
            "logical_shard_index": shard_by_segment[index],
            "record_count": len(segment),
            "work_keys": keys,
            "work_key_sequence_sha256": sha256_canonical_json(keys),
            "maximum_provider_requests": maximum,
            "billing_tier": "free",
            "paid_ceiling_usd": 0.0,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
        }
        rows.append({**core, "segment_sha256": sha256_canonical_json(core)})
    validate_schedule(rows)
    return rows


def validate_schedule(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pending, _ = _pending_rows()
    expected_keys = [str(row["work_key"]) for row in pending]
    flattened: list[str] = []
    counts = [0] * LOGICAL_SHARDS
    previous_shard = 0
    for index, item in enumerate(rows):
        row = dict(item)
        core = {key: child for key, child in row.items() if key != "segment_sha256"}
        keys = row.get("work_keys")
        shard = row.get("logical_shard_index")
        maximum = row.get("maximum_provider_requests")
        if (
            row.get("schema_version") != SCHEDULE_SCHEMA_VERSION
            or row.get("quota_segment_index") != index
            or not isinstance(keys, list)
            or not keys
            or row.get("record_count") != len(keys)
            or row.get("work_key_sequence_sha256")
            != sha256_canonical_json(keys)
            or isinstance(maximum, bool)
            or not isinstance(maximum, int)
            or maximum < 1
            or maximum > quota.LOCAL_REQUEST_CAP
            or not isinstance(shard, int)
            or isinstance(shard, bool)
            or shard < previous_shard
            or shard not in range(LOGICAL_SHARDS)
            or row.get("billing_tier") != "free"
            or row.get("paid_ceiling_usd") != 0.0
            or row.get("automatic_retries") != 0
            or row.get("segment_sha256") != sha256_canonical_json(core)
        ):
            raise GeminiPublicContinuationPlanV1Error(
                f"Gemini continuation segment {index} drift"
            )
        previous_shard = shard
        counts[shard] += 1
        flattened.extend(str(key) for key in keys)
    if (
        len(rows) != EXPECTED_QUOTA_SEGMENTS
        or flattened != expected_keys
        or len(set(flattened)) != len(flattened)
        or counts != _logical_shard_sizes(EXPECTED_QUOTA_SEGMENTS)
    ):
        raise GeminiPublicContinuationPlanV1Error(
            "Gemini continuation schedule coverage drift"
        )
    return {
        "quota_segment_count": len(rows),
        "record_count": len(flattened),
        "logical_shard_segment_counts": counts,
        "work_key_sequence_sha256": sha256_canonical_json(flattened),
    }


def build_candidate(schedule_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    status = validate_schedule(schedule_rows)
    source = public_v4.verify_candidate()
    _, canary_keys = _pending_rows()
    public_rows = _public_rows()
    scope = {
        "provider_id": "gemini",
        "model_id": "gemini-3.6-flash",
        "model_role": "second",
        "matrix_records": len(public_rows),
        "formal_canary_prefix_records": len(canary_keys),
        "pending_only_records": status["record_count"],
        "logical_shard_count": LOGICAL_SHARDS,
        "logical_shard_segment_counts": status["logical_shard_segment_counts"],
        "quota_segment_count": status["quota_segment_count"],
        "pending_work_key_sequence_sha256": status[
            "work_key_sequence_sha256"
        ],
        "canary_work_key_sequence_sha256": sha256_canonical_json(canary_keys),
        "schedule_path": _display_path(SCHEDULE_PATH),
        "schedule_sha256": _sha256_file(SCHEDULE_PATH),
        "source_canary_candidate_manifest_sha256": source["manifest_sha256"],
        "continuation_requires_v4_aggregate_technical_pass": True,
        "quota": {
            "billing_tier": "free",
            "paid_ceiling_usd": 0.0,
            "local_requests_per_day": quota.LOCAL_REQUEST_CAP,
            "one_formal_segment_per_quota_day": True,
            "automatic_retries": 0,
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "non_executable_pending_only_gemini_public_schedule",
        "generated_at": GENERATED_AT,
        "status": "offline_qualified_pending_canary_technical_gate",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [
            _lock(Path(__file__)),
            _lock(public_v1.GEMINI_PUBLIC_PLAN),
            _lock(public_v4.CANDIDATE_PATH),
            _lock(Path(public_v4.__file__)),
            _lock(quota.QUOTA_SNAPSHOT_PATH),
            _lock(SCHEDULE_PATH),
        ],
        "authorization": {
            "candidate_only": True,
            "quota_segment_execution_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_read": 0,
            "canary_work_keys_replayed": 0,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicContinuationPlanV1Error(
            "Gemini continuation candidate missing"
        )
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}
    scope = value.get("scope")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != sha256_canonical_json(core)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("matrix_records") != 1_791
        or scope.get("formal_canary_prefix_records") != 12
        or scope.get("pending_only_records") != EXPECTED_PENDING_RECORDS
        or scope.get("logical_shard_count") != LOGICAL_SHARDS
        or scope.get("quota_segment_count") != EXPECTED_QUOTA_SEGMENTS
        or scope.get("quota", {}).get("billing_tier") != "free"
        or scope.get("quota", {}).get("paid_ceiling_usd") != 0.0
        or value.get("authorization", {}).get(
            "quota_segment_execution_authorized"
        )
        is not False
    ):
        raise GeminiPublicContinuationPlanV1Error(
            "Gemini continuation candidate drift"
        )
    for lock in value.get("artifact_locks", []):
        _verify_lock(lock)
    return copy.deepcopy(dict(value))


def write_candidate() -> dict[str, Any]:
    schedule = build_schedule()
    _write_jsonl(SCHEDULE_PATH, schedule)
    value = build_candidate(schedule)
    _write_json(CANDIDATE_PATH, value)
    return value


def verify_candidate() -> dict[str, Any]:
    schedule = _read_jsonl(SCHEDULE_PATH)
    observed = validate_candidate(_read_json(CANDIDATE_PATH))
    expected_schedule = build_schedule()
    if schedule != expected_schedule or observed != build_candidate(schedule):
        raise GeminiPublicContinuationPlanV1Error(
            "Gemini continuation artifacts drift"
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
