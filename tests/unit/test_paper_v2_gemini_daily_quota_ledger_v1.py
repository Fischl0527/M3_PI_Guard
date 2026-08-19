from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import experiments.paper_v2.gemini_daily_quota_ledger_v1 as quota


def test_snapshot_locks_free_tier_and_two_request_reserve() -> None:
    value = quota.verify_quota_snapshot()

    assert value["billing_tier"] == "free"
    assert value["monetary_hard_limit_usd"] == 0.0
    assert value["active_limits"]["requests_per_day"] == 20
    assert value["prospective_v3_local_caps"]["requests_per_day"] == 18
    assert value["prospective_v3_local_caps"][
        "reserved_requests_per_day"
    ] == 2


def test_quota_day_uses_provider_timezone() -> None:
    instant = datetime(2026, 8, 2, 1, 0, tzinfo=ZoneInfo("UTC"))

    assert quota.current_quota_day(instant) == "2026-08-01"


def test_one_formal_reservation_per_day(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "quota.jsonl"
    monkeypatch.setattr(quota, "current_quota_day", lambda now=None: "2026-08-01")

    first = quota.reserve_formal_day(
        run_id="run-1",
        execution_identity="identity-1",
        workload="public_canary_segment_0",
        maximum_provider_requests=18,
        admission_file_sha256="a" * 64,
        quota_day="2026-08-01",
        reserved_at="2026-08-02T05:45:00+08:00",
        path=path,
    )

    assert first["ledger_sequence"] == 1
    assert quota.load_and_validate(path)["status"]["event_count"] == 1
    with pytest.raises(
        quota.GeminiDailyQuotaLedgerV1Error,
        match="already reserved",
    ):
        quota.reserve_formal_day(
            run_id="run-2",
            execution_identity="identity-2",
            workload="adaptive_segment_0",
            maximum_provider_requests=1,
            admission_file_sha256="b" * 64,
            quota_day="2026-08-01",
            reserved_at="2026-08-02T06:00:00+08:00",
            path=path,
        )


def test_reservation_rejects_cap_and_untracked_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "quota.jsonl"
    monkeypatch.setattr(quota, "current_quota_day", lambda now=None: "2026-08-01")

    with pytest.raises(quota.GeminiDailyQuotaLedgerV1Error):
        quota.reserve_formal_day(
            run_id="run",
            execution_identity="identity",
            workload="public",
            maximum_provider_requests=19,
            admission_file_sha256="a" * 64,
            quota_day="2026-08-01",
            reserved_at="2026-08-02T05:45:00+08:00",
            path=path,
        )
    with pytest.raises(
        quota.GeminiDailyQuotaLedgerV1Error,
        match="zero untracked",
    ):
        quota.reserve_formal_day(
            run_id="run",
            execution_identity="identity",
            workload="public",
            maximum_provider_requests=18,
            admission_file_sha256="a" * 64,
            quota_day="2026-08-01",
            reserved_at="2026-08-02T05:45:00+08:00",
            declared_other_project_requests=1,
            path=path,
        )
