"""Offline quota-capacity schedule for the frozen Gemini adaptive panel.

The schedule enumerates the maximum 4,000 query slots prospectively, using a
round-robin task order at each query index.  Two slots fit in one provider day
because every M3-full query has a frozen maximum of eight provider calls and
the local free-tier ceiling is eighteen requests.  Runtime successors must
skip future slots after a task reaches success or a terminal diagnostic.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import experiments.paper_v2.adaptive_formal_second_plan_v1 as adaptive_plan
import experiments.paper_v2.gemini_daily_quota_ledger_v1 as quota
from experiments.paper_v2.contracts import sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
SCHEDULE_PATH = PROTOCOL_ROOT / "gemini_adaptive_quota_schedule_v1.jsonl"
CANDIDATE_PATH = PROTOCOL_ROOT / "gemini_adaptive_quota_candidate_v1.json"
GENERATED_AT = "2026-08-02T02:28:06+08:00"
SCHEMA_VERSION = "m3-paper-v2-gemini-adaptive-quota-plan-1.0"
SLOT_SCHEMA_VERSION = "m3-paper-v2-gemini-adaptive-quota-segment-1.0"
TASK_COUNT = 20
MAX_QUERY_INDEX = 200
QUERY_SLOT_COUNT = TASK_COUNT * MAX_QUERY_INDEX
QUERIES_PER_QUOTA_DAY = 2
QUOTA_SEGMENT_COUNT = QUERY_SLOT_COUNT // QUERIES_PER_QUOTA_DAY


class GeminiAdaptiveQuotaScheduleV1Error(ValueError):
    """Raised when the free-tier adaptive capacity schedule drifts."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiAdaptiveQuotaScheduleV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise GeminiAdaptiveQuotaScheduleV1Error(f"{path}: expected object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                raise GeminiAdaptiveQuotaScheduleV1Error(
                    f"{path}:{number}: blank row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise GeminiAdaptiveQuotaScheduleV1Error(
                    f"{path}:{number}: expected object"
                )
            rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiAdaptiveQuotaScheduleV1Error(
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
        raise GeminiAdaptiveQuotaScheduleV1Error(
            f"missing adaptive schedule input: {path}"
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
        raise GeminiAdaptiveQuotaScheduleV1Error(
            "adaptive schedule lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise GeminiAdaptiveQuotaScheduleV1Error(
            f"adaptive schedule lock drift: {path}"
        )


def _query_slots() -> list[dict[str, Any]]:
    candidate = adaptive_plan.verify_candidate("gemini_flash")
    tasks = candidate["scope"]["tasks"]
    if len(tasks) != TASK_COUNT:
        raise GeminiAdaptiveQuotaScheduleV1Error(
            "Gemini adaptive task count drift"
        )
    slots: list[dict[str, Any]] = []
    for query_index in range(1, MAX_QUERY_INDEX + 1):
        phase = "budget_50" if query_index <= 50 else "budget_200_extension"
        for task in tasks:
            case_id = str(task["case_id"])
            slots.append(
                {
                    "case_id": case_id,
                    "query_index": query_index,
                    "work_key": adaptive_plan.adaptive_query_work_key(
                        "gemini_flash", case_id, query_index
                    ),
                    "phase": phase,
                }
            )
    if len(slots) != QUERY_SLOT_COUNT or len(
        {slot["work_key"] for slot in slots}
    ) != QUERY_SLOT_COUNT:
        raise GeminiAdaptiveQuotaScheduleV1Error(
            "Gemini adaptive query-slot identity drift"
        )
    return slots


def build_schedule() -> list[dict[str, Any]]:
    slots = _query_slots()
    rows: list[dict[str, Any]] = []
    for index in range(0, len(slots), QUERIES_PER_QUOTA_DAY):
        segment_slots = copy.deepcopy(slots[index : index + QUERIES_PER_QUOTA_DAY])
        segment_index = index // QUERIES_PER_QUOTA_DAY
        phase = (
            "technical_canary_prefix"
            if segment_index == 0
            else segment_slots[0]["phase"]
        )
        core = {
            "schema_version": SLOT_SCHEMA_VERSION,
            "quota_segment_index": segment_index,
            "phase": phase,
            "query_slot_count": len(segment_slots),
            "query_slots": segment_slots,
            "query_work_key_sequence_sha256": sha256_canonical_json(
                [slot["work_key"] for slot in segment_slots]
            ),
            "maximum_provider_requests": 16,
            "billing_tier": "free",
            "paid_ceiling_usd": 0.0,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "terminal_task_future_slots_must_be_skipped": True,
        }
        rows.append({**core, "segment_sha256": sha256_canonical_json(core)})
    validate_schedule(rows)
    return rows


def validate_schedule(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    expected = _query_slots()
    flattened: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        row = dict(item)
        core = {key: child for key, child in row.items() if key != "segment_sha256"}
        slots = row.get("query_slots")
        if (
            row.get("schema_version") != SLOT_SCHEMA_VERSION
            or row.get("quota_segment_index") != index
            or not isinstance(slots, list)
            or len(slots) != QUERIES_PER_QUOTA_DAY
            or row.get("query_slot_count") != len(slots)
            or row.get("query_work_key_sequence_sha256")
            != sha256_canonical_json([slot.get("work_key") for slot in slots])
            or row.get("maximum_provider_requests") != 16
            or row.get("billing_tier") != "free"
            or row.get("paid_ceiling_usd") != 0.0
            or row.get("automatic_retries") != 0
            or row.get("terminal_task_future_slots_must_be_skipped") is not True
            or row.get("segment_sha256") != sha256_canonical_json(core)
        ):
            raise GeminiAdaptiveQuotaScheduleV1Error(
                f"Gemini adaptive quota segment {index} drift"
            )
        flattened.extend(copy.deepcopy(slots))
    if len(rows) != QUOTA_SEGMENT_COUNT or flattened != expected:
        raise GeminiAdaptiveQuotaScheduleV1Error(
            "Gemini adaptive schedule coverage or order drift"
        )
    return {
        "quota_segment_count": len(rows),
        "query_slot_count": len(flattened),
        "query_work_key_sequence_sha256": sha256_canonical_json(
            [slot["work_key"] for slot in flattened]
        ),
        "technical_canary_query_slots": len(rows[0]["query_slots"]),
    }


def build_candidate(schedule: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    status = validate_schedule(schedule)
    plan = adaptive_plan.verify_candidate("gemini_flash")
    scope = {
        "provider_id": "gemini",
        "model_id": "gemini-3.6-flash",
        "model_role": "gemini_replication",
        "task_count": TASK_COUNT,
        "budget_nodes": [50, 200],
        "maximum_query_slots": status["query_slot_count"],
        "maximum_provider_calls": 32_000,
        "quota_segment_count": status["quota_segment_count"],
        "technical_canary_prefix_query_slots": status[
            "technical_canary_query_slots"
        ],
        "query_work_key_sequence_sha256": status[
            "query_work_key_sequence_sha256"
        ],
        "schedule_path": _display_path(SCHEDULE_PATH),
        "schedule_sha256": _sha256_file(SCHEDULE_PATH),
        "adaptive_plan_manifest_sha256": plan["manifest_sha256"],
        "runtime_rule": (
            "Select the earliest two capacity slots whose tasks have neither "
            "succeeded nor ended diagnostic; preserve each task checkpoint "
            "prefix and never replay a touched work key."
        ),
        "quota": {
            "billing_tier": "free",
            "paid_ceiling_usd": 0.0,
            "local_requests_per_day": quota.LOCAL_REQUEST_CAP,
            "maximum_requests_per_segment": 16,
            "reserved_requests_per_day": quota.RESERVED_REQUESTS,
            "one_formal_workload_per_quota_day": True,
            "automatic_retries": 0,
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "non_executable_gemini_adaptive_quota_capacity_plan",
        "generated_at": GENERATED_AT,
        "status": "offline_qualified_pending_daily_successor_controller",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [
            _lock(Path(__file__)),
            _lock(adaptive_plan.candidate_path("gemini_flash")),
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
            "mutable_checkpoint_created": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiAdaptiveQuotaScheduleV1Error(
            "Gemini adaptive quota candidate missing"
        )
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}
    scope = value.get("scope")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != sha256_canonical_json(core)
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or scope.get("task_count") != TASK_COUNT
        or scope.get("budget_nodes") != [50, 200]
        or scope.get("maximum_query_slots") != QUERY_SLOT_COUNT
        or scope.get("maximum_provider_calls") != 32_000
        or scope.get("quota_segment_count") != QUOTA_SEGMENT_COUNT
        or scope.get("quota", {}).get("billing_tier") != "free"
        or scope.get("quota", {}).get("paid_ceiling_usd") != 0.0
        or value.get("authorization", {}).get(
            "quota_segment_execution_authorized"
        )
        is not False
    ):
        raise GeminiAdaptiveQuotaScheduleV1Error(
            "Gemini adaptive quota candidate drift"
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
    if schedule != build_schedule() or observed != build_candidate(schedule):
        raise GeminiAdaptiveQuotaScheduleV1Error(
            "Gemini adaptive quota artifacts drift"
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

