from __future__ import annotations

import copy

import pytest

from experiments.paper_v2.medium_execution import (
    DEFAULT_EXECUTION_MANIFEST,
    DEFAULT_PLAN,
    MediumExecutionError,
    assert_spend_headroom,
    build_execution_plan,
    pending_work_items,
    verify_execution_plan,
)


def test_plan_has_exactly_480_unique_result_blind_work_items() -> None:
    work_items, manifest = build_execution_plan()

    assert len(work_items) == 480
    assert len({item["work_key"] for item in work_items}) == 480
    assert manifest["work_item_counts"] == {
        "authorization_regime_probe": 48,
        "primary": 432,
    }
    assert manifest["provider_calls_upper_bound"] == 4416
    assert manifest["execution_authorized"] is False
    assert manifest["results_present"] is False
    assert all(item["status"] == "pending" for item in work_items)
    assert all(item["result_fields_present"] is False for item in work_items)
    assert not any("unsafe_effect" in item for item in work_items)


def test_frozen_plan_and_manifest_reproduce() -> None:
    manifest = verify_execution_plan(
        plan_path=DEFAULT_PLAN,
        manifest_path=DEFAULT_EXECUTION_MANIFEST,
    )

    assert len(manifest["execution_identity"]) == 64
    assert len(manifest["plan_sha256"]) == 64


def test_resume_skips_terminal_and_retries_started_only() -> None:
    work_items, _ = build_execution_plan()
    first, second = work_items[:2]
    events = [
        {
            "schema_version": "m3-paper-v2-progress-event-1.0",
            "execution_identity": first["execution_identity"],
            "work_key": first["work_key"],
            "event_type": "started",
        },
        {
            "schema_version": "m3-paper-v2-progress-event-1.0",
            "execution_identity": first["execution_identity"],
            "work_key": first["work_key"],
            "event_type": "completed",
        },
        {
            "schema_version": "m3-paper-v2-progress-event-1.0",
            "execution_identity": second["execution_identity"],
            "work_key": second["work_key"],
            "event_type": "started",
        },
    ]

    pending = pending_work_items(work_items, events)

    assert len(pending) == 479
    assert first["work_key"] not in {item["work_key"] for item in pending}
    assert second["work_key"] in {item["work_key"] for item in pending}


def test_duplicate_terminal_and_identity_drift_are_rejected() -> None:
    work_items, _ = build_execution_plan()
    item = work_items[0]
    started = {
        "schema_version": "m3-paper-v2-progress-event-1.0",
        "execution_identity": item["execution_identity"],
        "work_key": item["work_key"],
        "event_type": "started",
    }
    completed = {**started, "event_type": "completed"}

    with pytest.raises(MediumExecutionError, match="duplicate terminal"):
        pending_work_items(work_items, [started, completed, completed])

    drift = copy.deepcopy(started)
    drift["execution_identity"] = "0" * 64
    with pytest.raises(MediumExecutionError, match="identity drift"):
        pending_work_items(work_items, [drift])


def test_spend_guard_fails_closed_and_enforces_abort_ceiling() -> None:
    with pytest.raises(MediumExecutionError, match="not approved"):
        assert_spend_headroom(
            {"gate_pass": False},
            spent_usd=0,
            next_work_item_upper_bound_usd=1,
        )

    approved = {
        "gate_pass": True,
        "hard_spend_limit_usd": 100,
        "abort_at_fraction": 0.9,
    }
    assert_spend_headroom(
        approved,
        spent_usd=80,
        next_work_item_upper_bound_usd=10,
    )
    with pytest.raises(MediumExecutionError, match="abort ceiling"):
        assert_spend_headroom(
            approved,
            spent_usd=80,
            next_work_item_upper_bound_usd=10.01,
        )
