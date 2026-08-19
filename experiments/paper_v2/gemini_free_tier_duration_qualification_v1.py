"""Reconstruct the provider-day lower and safe upper schedules for Gemini.

This qualification is offline-only.  It turns the owner-console free-tier
snapshot and the frozen public/adaptive plans into machine-checkable provider-
day bounds.  It does not read credentials or authorize execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.adaptive_formal_second_plan_v1 as adaptive_plan
import experiments.paper_v2.gemini_daily_quota_ledger_v1 as quota
import experiments.paper_v2.gemini_public_controller_v1 as public_v1
import experiments.paper_v2.gemini_public_controller_v4 as public_v4
from experiments.paper_v2.contracts import sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/"
    "gemini_free_tier_duration_qualification_v1.json"
)
GENERATED_AT = "2026-08-02T12:02:20+08:00"
SCHEMA_VERSION = "m3-paper-v2-gemini-free-tier-duration-qualification-1.0"


class GeminiFreeTierDurationQualificationV1Error(ValueError):
    """Raised when the frozen Gemini schedule cannot be reconstructed."""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                raise GeminiFreeTierDurationQualificationV1Error(
                    f"{path}:{number}: blank row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise GeminiFreeTierDurationQualificationV1Error(
                    f"{path}:{number}: expected object"
                )
            rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiFreeTierDurationQualificationV1Error(
            f"{path}: invalid JSONL"
        ) from exc
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiFreeTierDurationQualificationV1Error(
            f"missing schedule input: {path}"
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
        raise GeminiFreeTierDurationQualificationV1Error(
            "schedule lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise GeminiFreeTierDurationQualificationV1Error(
            f"schedule lock drift: {path}"
        )


def build_qualification() -> dict[str, Any]:
    snapshot = quota.verify_quota_snapshot()
    adaptive = adaptive_plan.verify_candidate("gemini_flash")
    public_rows = _read_jsonl(public_v1.GEMINI_PUBLIC_PLAN)
    if len(public_rows) != 1_791:
        raise GeminiFreeTierDurationQualificationV1Error(
            "Gemini public matrix row count drift"
        )
    public_keys = [str(row.get("work_key", "")) for row in public_rows]
    if not all(public_keys) or len(set(public_keys)) != len(public_keys):
        raise GeminiFreeTierDurationQualificationV1Error(
            "Gemini public matrix work keys drift"
        )
    canary_rows = public_v1._canary_rows()
    canary_keys = {str(row["work_key"]) for row in canary_rows}
    remaining_public_rows = [
        row for row in public_rows if str(row["work_key"]) not in canary_keys
    ]
    if len(canary_keys) != 12 or len(remaining_public_rows) != 1_779:
        raise GeminiFreeTierDurationQualificationV1Error(
            "Gemini canary/pending-only public partition drift"
        )
    canary_safe_days = len(public_v4._pack_rows(canary_rows))
    public_safe_days = len(public_v4._pack_rows(remaining_public_rows))
    adaptive_queries = int(adaptive["scope"]["maximum_query_budget"])
    adaptive_calls = int(adaptive["scope"]["maximum_provider_calls"])
    if adaptive_queries != 4_000 or adaptive_calls != 32_000:
        raise GeminiFreeTierDurationQualificationV1Error(
            "Gemini adaptive maximums drift"
        )
    per_query_cap = adaptive_calls // adaptive_queries
    if per_query_cap != 8:
        raise GeminiFreeTierDurationQualificationV1Error(
            "Gemini adaptive per-query call cap drift"
        )
    safe_queries_per_day = quota.LOCAL_REQUEST_CAP // per_query_cap
    if safe_queries_per_day != 2:
        raise GeminiFreeTierDurationQualificationV1Error(
            "Gemini safe daily adaptive packing drift"
        )
    theoretical = {
        "canary": math.ceil(len(canary_rows) / quota.LOCAL_REQUEST_CAP),
        "public_pending_only": math.ceil(
            len(remaining_public_rows) / quota.LOCAL_REQUEST_CAP
        ),
        "adaptive": math.ceil(adaptive_queries / quota.LOCAL_REQUEST_CAP),
    }
    prospective_minimum = {
        **theoretical,
        "canary": canary_safe_days,
    }
    safe = {
        "canary": canary_safe_days,
        "public_pending_only": public_safe_days,
        "adaptive": math.ceil(adaptive_queries / safe_queries_per_day),
    }
    theoretical["total"] = sum(theoretical.values())
    prospective_minimum["total"] = sum(prospective_minimum.values())
    safe["total"] = sum(safe.values())
    public_by_condition: dict[str, dict[str, int]] = {}
    for row in public_rows:
        condition = str(row["condition_id"])
        current = public_by_condition.setdefault(
            condition, {"records": 0, "maximum_provider_calls": 0}
        )
        current["records"] += 1
        current["maximum_provider_calls"] += int(row["max_provider_calls"])
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "offline_gemini_free_tier_duration_qualification",
        "generated_at": GENERATED_AT,
        "status": "qualified_schedule_extension_required",
        "provider_id": "gemini",
        "model_id": "gemini-3.6-flash",
        "quota": {
            "billing_tier": "free",
            "provider_requests_per_day": snapshot["active_limits"][
                "requests_per_day"
            ],
            "local_requests_per_day": quota.LOCAL_REQUEST_CAP,
            "reserved_requests_per_day": quota.RESERVED_REQUESTS,
            "paid_ceiling_usd": 0.0,
            "quota_timezone": quota.QUOTA_TIMEZONE,
            "one_formal_workload_per_quota_day": True,
        },
        "workloads": {
            "canary": {
                "records": len(canary_rows),
                "maximum_provider_calls": sum(
                    int(row["max_provider_calls"]) for row in canary_rows
                ),
                "safe_quota_days": canary_safe_days,
            },
            "public_matrix": {
                "records": len(public_rows),
                "canary_prefix_records": len(canary_rows),
                "pending_only_records": len(remaining_public_rows),
                "maximum_provider_calls": sum(
                    int(row["max_provider_calls"]) for row in public_rows
                ),
                "pending_only_maximum_provider_calls": sum(
                    int(row["max_provider_calls"])
                    for row in remaining_public_rows
                ),
                "by_condition": public_by_condition,
                "pending_only_safe_quota_days": public_safe_days,
            },
            "adaptive": {
                "tasks": adaptive["scope"]["task_count"],
                "maximum_queries": adaptive_queries,
                "maximum_provider_calls": adaptive_calls,
                "safe_queries_per_quota_day": safe_queries_per_day,
                "safe_quota_days": safe["adaptive"],
            },
        },
        "duration_bounds_quota_days": {
            "theoretical_one_call_per_item": theoretical,
            "prospective_minimum_with_locked_canary": prospective_minimum,
            "precommitted_worst_case_safe_packing": safe,
        },
        "conclusion": {
            "twenty_one_day_completion_possible_under_current_free_tier": False,
            "schedule_extension_mandatory": True,
            "billing_enablement_authorized": False,
            "completion_may_not_be_claimed_from_elapsed_calendar_days": True,
        },
        "artifact_locks": [
            _lock(Path(__file__)),
            _lock(quota.QUOTA_SNAPSHOT_PATH),
            _lock(public_v1.GEMINI_PUBLIC_PLAN),
            _lock(adaptive_plan.candidate_path("gemini_flash")),
            _lock(Path(public_v4.__file__)),
        ],
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_read": 0,
            "execution_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_qualification(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiFreeTierDurationQualificationV1Error(
            "duration qualification must be an object"
        )
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}
    bounds = value.get("duration_bounds_quota_days", {})
    conclusion = value.get("conclusion", {})
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != sha256_canonical_json(core)
        or bounds.get("theoretical_one_call_per_item", {}).get("total") != 323
        or bounds.get("prospective_minimum_with_locked_canary", {}).get(
            "total"
        )
        != 330
        or bounds.get("precommitted_worst_case_safe_packing", {}).get("total")
        != 3_194
        or conclusion.get(
            "twenty_one_day_completion_possible_under_current_free_tier"
        )
        is not False
        or conclusion.get("billing_enablement_authorized") is not False
    ):
        raise GeminiFreeTierDurationQualificationV1Error(
            "duration qualification drift"
        )
    for lock in value.get("artifact_locks", []):
        _verify_lock(lock)
    return dict(value)


def write_qualification() -> dict[str, Any]:
    value = build_qualification()
    _write_json(OUTPUT_PATH, value)
    return value


def verify_qualification() -> dict[str, Any]:
    observed = validate_qualification(
        json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    )
    if observed != build_qualification():
        raise GeminiFreeTierDurationQualificationV1Error(
            "duration qualification artifact drift"
        )
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = write_qualification() if args.write else verify_qualification()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
