"""Append-only project-day reservations for the official Gemini free tier.

One execution identity may reserve at most the prospectively frozen local cap
on one America/Los_Angeles quota day.  A second formal reservation for the same
project day is rejected, so public and adaptive runs cannot accidentally share
or overbook the free-tier allowance.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from experiments.paper_v2.contracts import sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUOTA_SNAPSHOT_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/gemini_free_tier_quota_snapshot_v2.json"
)
DEFAULT_LEDGER_PATH = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/gemini_project_quota_days_v1.jsonl"
)
SCHEMA_VERSION = "m3-paper-v2-gemini-project-quota-day-event-1.0"
QUOTA_TIMEZONE = "America/Los_Angeles"
LOCAL_REQUEST_CAP = 18
PROVIDER_REQUEST_CAP = 20
RESERVED_REQUESTS = 2
LOCAL_INPUT_TOKEN_CAP = 200_000
LOCAL_OUTPUT_TOKEN_CAP = 16_000


class GeminiDailyQuotaLedgerV1Error(ValueError):
    """Raised when a free-tier project-day reservation is unsafe."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiDailyQuotaLedgerV1Error(f"{path}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise GeminiDailyQuotaLedgerV1Error(f"{path}: expected object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                raise GeminiDailyQuotaLedgerV1Error(
                    f"{path}:{number}: blank row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise GeminiDailyQuotaLedgerV1Error(
                    f"{path}:{number}: expected object"
                )
            rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiDailyQuotaLedgerV1Error(f"{path}: invalid JSONL") from exc
    return rows


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_quota_snapshot() -> dict[str, Any]:
    value = _read_json(QUOTA_SNAPSHOT_PATH)
    active = value.get("active_limits")
    local = value.get("prospective_v3_local_caps")
    if (
        value.get("status") != "active_project_free_tier_confirmed_owner_console"
        or value.get("billing_tier") != "free"
        or value.get("paid_tier_allowed") is not False
        or value.get("monetary_hard_limit_usd") != 0.0
        or not isinstance(active, Mapping)
        or active.get("requests_per_day") != PROVIDER_REQUEST_CAP
        or active.get("requests_per_day_reset_timezone") != QUOTA_TIMEZONE
        or not isinstance(local, Mapping)
        or local.get("requests_per_day") != LOCAL_REQUEST_CAP
        or local.get("reserved_requests_per_day") != RESERVED_REQUESTS
        or local.get("input_tokens_per_minute") != LOCAL_INPUT_TOKEN_CAP
        or local.get("output_tokens_per_day") != LOCAL_OUTPUT_TOKEN_CAP
        or local.get("concurrency") != 1
        or local.get("automatic_retries") != 0
    ):
        raise GeminiDailyQuotaLedgerV1Error("Gemini quota snapshot drift")
    return value


def current_quota_day(now: datetime | None = None) -> str:
    current = now or datetime.now(tz=ZoneInfo(QUOTA_TIMEZONE))
    if current.tzinfo is None:
        raise GeminiDailyQuotaLedgerV1Error("quota clock must be timezone aware")
    return current.astimezone(ZoneInfo(QUOTA_TIMEZONE)).date().isoformat()


def validate_events(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    verify_quota_snapshot()
    previous: str | None = None
    days: set[str] = set()
    identities: set[str] = set()
    for sequence, item in enumerate(events, 1):
        event = dict(item)
        core = {key: child for key, child in event.items() if key != "event_sha256"}
        quota_day = str(event.get("quota_day", ""))
        identity = str(event.get("execution_identity", ""))
        maximum = event.get("maximum_provider_requests")
        if (
            event.get("schema_version") != SCHEMA_VERSION
            or event.get("ledger_sequence") != sequence
            or event.get("previous_event_sha256") != previous
            or event.get("event_type") != "formal_day_reserved"
            or len(quota_day) != 10
            or quota_day in days
            or not identity
            or identity in identities
            or isinstance(maximum, bool)
            or not isinstance(maximum, int)
            or maximum < 1
            or maximum > LOCAL_REQUEST_CAP
            or event.get("billing_tier") != "free"
            or event.get("paid_ceiling_usd") != 0.0
            or event.get("automatic_retries") != 0
            or event.get("provider_tools_enabled") is not False
            or event.get("external_effects_enabled") is not False
            or event.get("declared_other_project_requests") != 0
            or event.get("quota_snapshot_sha256")
            != _sha256_file(QUOTA_SNAPSHOT_PATH)
            or event.get("event_sha256") != sha256_canonical_json(core)
        ):
            raise GeminiDailyQuotaLedgerV1Error(
                f"Gemini quota event {sequence} drift"
            )
        previous = str(event["event_sha256"])
        days.add(quota_day)
        identities.add(identity)
    return {
        "event_count": len(events),
        "reserved_quota_days": sorted(days),
        "execution_identities": sorted(identities),
        "tail_sha256": previous,
    }


def load_and_validate(path: Path = DEFAULT_LEDGER_PATH) -> dict[str, Any]:
    events = _read_jsonl(path)
    return {"events": events, "status": validate_events(events)}


def reserve_formal_day(
    *,
    run_id: str,
    execution_identity: str,
    workload: str,
    maximum_provider_requests: int,
    admission_file_sha256: str,
    quota_day: str,
    reserved_at: str,
    declared_other_project_requests: int = 0,
    path: Path = DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    if quota_day != current_quota_day():
        raise GeminiDailyQuotaLedgerV1Error(
            "admission quota day is not the current provider quota day"
        )
    loaded = load_and_validate(path)
    if quota_day in loaded["status"]["reserved_quota_days"]:
        raise GeminiDailyQuotaLedgerV1Error(
            "Gemini project quota day is already reserved"
        )
    if declared_other_project_requests != 0:
        raise GeminiDailyQuotaLedgerV1Error(
            "formal day requires zero untracked project requests"
        )
    core = {
        "schema_version": SCHEMA_VERSION,
        "ledger_sequence": len(loaded["events"]) + 1,
        "previous_event_sha256": loaded["status"]["tail_sha256"],
        "event_type": "formal_day_reserved",
        "quota_day": quota_day,
        "quota_timezone": QUOTA_TIMEZONE,
        "reserved_at": reserved_at,
        "run_id": run_id,
        "execution_identity": execution_identity,
        "workload": workload,
        "maximum_provider_requests": maximum_provider_requests,
        "provider_request_cap": PROVIDER_REQUEST_CAP,
        "reserved_provider_requests": RESERVED_REQUESTS,
        "billing_tier": "free",
        "paid_ceiling_usd": 0.0,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "declared_other_project_requests": declared_other_project_requests,
        "admission_file_sha256": admission_file_sha256,
        "quota_snapshot_sha256": _sha256_file(QUOTA_SNAPSHOT_PATH),
    }
    event = {**core, "event_sha256": sha256_canonical_json(core)}
    validate_events([*loaded["events"], event])
    _append_jsonl(path, event)
    return copy.deepcopy(event)


__all__ = [
    "DEFAULT_LEDGER_PATH",
    "GeminiDailyQuotaLedgerV1Error",
    "LOCAL_INPUT_TOKEN_CAP",
    "LOCAL_OUTPUT_TOKEN_CAP",
    "LOCAL_REQUEST_CAP",
    "current_quota_day",
    "load_and_validate",
    "reserve_formal_day",
    "validate_events",
    "verify_quota_snapshot",
]
