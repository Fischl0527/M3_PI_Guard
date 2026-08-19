from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

import experiments.paper_v2.public_second_continuation_v2 as continuation


def test_flash_partition_is_complete_disjoint_and_excludes_canary() -> None:
    partitions = continuation._partitions()
    keys = [row["work_key"] for rows in partitions for row in rows]

    assert len(partitions) == 2
    assert [len(rows) for rows in partitions] == [890, 889]
    assert len(keys) == 1779
    assert len(set(keys)) == 1779


def test_cny_five_ceiling_includes_canary() -> None:
    canary_cost = 0.0123456
    per_shard = continuation._per_shard_limit(canary_cost)

    assert canary_cost + 2 * per_shard <= 5.0
    assert 5.0 - (canary_cost + 2 * per_shard) < 0.00000002


def test_state_forwards_exact_shard_policy_everywhere(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limit = 2.49
    candidate = {
        "scope": {"budget": {"per_shard_hard_limit_cny": limit}}
    }
    permit = SimpleNamespace(
        candidate=candidate,
        work_items=tuple(),
        execution_identity="execution",
        run_id="run",
        model_role="second",
        record_ledger_path=tmp_path / "records.jsonl",
        attempt_ledger_path=tmp_path / "attempts.jsonl",
        budget_ledger_path=tmp_path / "budget.jsonl",
        trace_root=tmp_path / "traces",
    )
    role_policy = {
        "deepseek": {
            "model_id": "deepseek-v4-flash",
            "abort_ceiling_cny": limit,
        }
    }
    observed: list[tuple[str, Mapping[str, Any]]] = []

    monkeypatch.setattr(continuation, "load_public_record_entries", lambda path: [])

    def record_validator(*args: Any, **kwargs: Any) -> dict[str, Any]:
        observed.append(("records", kwargs["role_policy"]))
        return {"terminal_work_keys": []}

    monkeypatch.setattr(
        continuation, "validate_public_record_entries", record_validator
    )
    monkeypatch.setattr(continuation.medium_v1, "_load_jsonl", lambda path: [])
    monkeypatch.setattr(
        continuation.medium_v1,
        "validate_attempt_events",
        lambda *args, **kwargs: {
            "terminal_by_work_key": {},
            "open_work_keys": [],
        },
    )

    def budget_validator(*args: Any, **kwargs: Any) -> dict[str, Any]:
        observed.append(("budget", kwargs["role_policy"]))
        return {
            "paused": False,
            "event_count": 0,
            "role_cumulative_usage": {},
            "role_cumulative_cost_cny": 0.0,
        }

    monkeypatch.setattr(
        continuation, "validate_public_budget_events", budget_validator
    )

    def cross_bind(*args: Any, **kwargs: Any) -> None:
        observed.append(("cross_bind", kwargs["role_policy"]))

    monkeypatch.setattr(
        continuation, "cross_bind_public_budget_and_records", cross_bind
    )

    state = continuation._state(permit, role_policy=role_policy)

    assert state["pending"] == []
    assert [name for name, _ in observed] == [
        "records",
        "budget",
        "cross_bind",
    ]
    assert all(policy is role_policy for _, policy in observed)


def test_state_rejects_global_policy_regression(tmp_path: Path) -> None:
    permit = SimpleNamespace(
        candidate={
            "scope": {"budget": {"per_shard_hard_limit_cny": 2.49}}
        },
        work_items=tuple(),
        trace_root=tmp_path,
    )

    with pytest.raises(
        continuation.PublicSecondContinuationV2Error,
        match="exact shard policy",
    ):
        continuation._state(
            permit,
            role_policy={
                "deepseek": {
                    "model_id": "deepseek-v4-flash",
                    "abort_ceiling_cny": 5.0,
                }
            },
        )
