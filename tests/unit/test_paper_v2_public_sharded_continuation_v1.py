from __future__ import annotations

import copy
import json

import pytest

import experiments.paper_v2.public_sharded_continuation_v1 as continuation


def _candidate() -> dict[str, object]:
    value = json.loads(
        continuation.candidate_path("primary").read_text(encoding="utf-8")
    )
    assert isinstance(value, dict)
    return value


def test_primary_continuation_partition_is_complete_and_disjoint() -> None:
    candidate = _candidate()
    validated = continuation.validate_candidate(
        candidate,
        model_role="primary",
    )
    shards = continuation._partition_rows("primary")
    keys = [
        str(row["work_key"])
        for shard in shards
        for row in shard
    ]

    assert validated["scope"]["role_records"] == 5082
    assert validated["scope"]["source_canary_records"] == 24
    assert validated["scope"]["continuation_records"] == 5058
    assert [len(shard) for shard in shards] == [1265, 1265, 1264, 1264]
    assert len(keys) == len(set(keys)) == 5058
    assert validated["authorization"]["shard_execution_authorized"] is False
    assert validated["authorization"]["result_admission_authorized"] is False


def test_primary_shard_budget_caps_preserve_role_limit() -> None:
    candidate = _candidate()
    budget = candidate["scope"]["budget"]

    assert budget["all_shards_hard_limit_cny"] == 19.6
    assert budget["source_canary_cost_cny"] == 0.0521812
    assert (
        budget["all_shards_hard_limit_cny"]
        + budget["source_canary_cost_cny"]
        < 20.0
    )
    policy = continuation._shard_role_policy("primary")
    assert policy["deepseek"]["hard_spend_limit_cny"] == 4.9
    assert policy["deepseek"]["abort_ceiling_cny"] == 4.9
    assert policy["deepseek"]["rate_limit_handling"][
        "automatic_retry"
    ] is False


def test_primary_shard_admission_binds_exact_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    monkeypatch.setattr(
        continuation,
        "verify_candidate",
        lambda model_role: copy.deepcopy(candidate),
    )

    value = continuation.build_admission(
        "primary",
        0,
        owner_statement_sha256="a" * 64,
        approved_at="2026-07-29T06:10:00+08:00",
    )

    assert value["scope"]["records"] == 1265
    assert value["scope"]["hard_spend_limit_cny"] == 4.9
    assert value["scope"]["exact_command"] == (
        continuation.canonical_shard_command("primary", 0)
    )
    assert "--shard-index 0" in value["scope"]["exact_command"]
    assert value["authorization"]["shard_execution_authorized"] is True
    assert value["authorization"]["result_admission_authorized"] is False
    assert value["evidence_boundary"]["automatic_retries"] == 0


def test_primary_shard_admission_rejects_command_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    monkeypatch.setattr(
        continuation,
        "verify_candidate",
        lambda model_role: copy.deepcopy(candidate),
    )
    value = continuation.build_admission(
        "primary",
        0,
        owner_statement_sha256="a" * 64,
        approved_at="2026-07-29T06:10:00+08:00",
    )
    drifted = copy.deepcopy(value)
    drifted["scope"]["exact_command"] += " --unsafe"

    with pytest.raises(
        continuation.PublicShardedContinuationError,
        match="binding drift",
    ):
        continuation.validate_admission(
            drifted,
            model_role="primary",
            shard_index=0,
        )
