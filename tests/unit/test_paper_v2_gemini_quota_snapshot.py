from __future__ import annotations

import copy
import json

import pytest

from experiments.paper_v2.gemini_quota_snapshot import (
    GeminiQuotaSnapshotError,
    build_active_snapshot,
    build_pending_template,
    validate_snapshot,
    verify_snapshot,
    write_active_snapshot,
    write_pending_template,
)


def test_pending_template_is_safe_and_does_not_open_gate() -> None:
    value = build_pending_template()
    validate_snapshot(value)

    assert value["active_limits"] == {
        "rpm": None,
        "tpm": None,
        "rpd": None,
    }
    assert value["quota_gate_satisfied"] is False
    assert value["formal_execution_authorized"] is False
    assert value["project_identifier_stored"] is False
    assert value["api_key_or_credential_stored"] is False
    serialized = json.dumps(value, sort_keys=True)
    assert "GEMINI_API_KEY" not in serialized


def test_active_snapshot_requires_positive_free_tier_limits() -> None:
    value = build_active_snapshot(
        rpm=10,
        tpm=250_000,
        rpd=250,
        captured_at="2026-07-24T01:20:00+08:00",
        source_screenshot_sha256="a" * 64,
    )

    assert value["status"] == "active_project_quota_captured"
    assert value["quota_gate_satisfied"] is True
    assert value["formal_execution_authorized"] is False

    invalid = copy.deepcopy(value)
    invalid["active_limits"]["rpm"] = 0
    with pytest.raises(GeminiQuotaSnapshotError, match="positive"):
        validate_snapshot(invalid)


def test_paid_tier_or_unattested_snapshot_is_rejected() -> None:
    active = build_active_snapshot(
        rpm=10,
        tpm=250_000,
        rpd=250,
        captured_at="2026-07-24T01:20:00+08:00",
    )
    paid = copy.deepcopy(active)
    paid["billing_tier"] = "paid"
    with pytest.raises(GeminiQuotaSnapshotError, match="safety field drift"):
        validate_snapshot(paid)

    unattested = copy.deepcopy(active)
    unattested["user_attested"] = False
    with pytest.raises(GeminiQuotaSnapshotError, match="attestation"):
        validate_snapshot(unattested)


def test_template_round_trip_is_deterministic(tmp_path) -> None:
    path = tmp_path / "quota.json"
    written = write_pending_template(path)
    loaded = verify_snapshot(path)

    assert written == loaded == build_pending_template()


def test_active_snapshot_round_trip_preserves_source_semantics(tmp_path) -> None:
    path = tmp_path / "active-quota.json"
    written = write_active_snapshot(
        rpm=1_000,
        tpm=2_000_000,
        rpd=10_000,
        captured_at="2026-07-24T01:03:51.9003883+08:00",
        source_screenshot_sha256="c" * 64,
        path=path,
    )

    assert verify_snapshot(path) == written
    assert written["active_limits"] == {
        "rpm": 1_000,
        "tpm": 2_000_000,
        "rpd": 10_000,
    }
    assert (
        written["captured_at_semantics"]
        == "user_submission_observed_at_not_provider_console_event_time"
    )
    assert written["billing_tier_source"] == "project_owner_declaration"
