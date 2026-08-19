from __future__ import annotations

import copy
import json

import pytest

import experiments.paper_v2.public_sharded_continuation_v1 as continuation_v1
import experiments.paper_v2.public_sharded_continuation_v2 as continuation_v2
from experiments.paper_v2.public_provider_budget_v1 import (
    build_role_policy,
    load_public_policy,
)


def _candidate() -> dict[str, object]:
    value = json.loads(
        continuation_v2.CANDIDATE_PATH.read_text(encoding="utf-8")
    )
    assert isinstance(value, dict)
    return value


def test_policy_aware_recovery_qualification_is_zero_network() -> None:
    value = continuation_v2.build_qualification()

    assert value["status"] == (
        "completed_zero_network_policy_aware_state_qualification"
    )
    assert value["summary"]["qualified_shards"] == 4
    assert value["summary"]["network_calls"] == 0
    assert value["summary"]["provider_calls"] == 0
    assert value["summary"]["scientific_outcomes_accessed"] is False
    assert all(
        item["policy_aware_state_reconstruction_passed"]
        for item in value["checks"]
    )


def test_fresh_candidate_reexecutes_complete_disjoint_partition() -> None:
    candidate = continuation_v2.validate_candidate(_candidate())
    source = continuation_v1.validate_candidate(
        continuation_v1._load_json(
            continuation_v1.candidate_path("primary")
        ),
        model_role="primary",
    )
    shards = continuation_v1._partition_rows("primary")
    keys = [
        str(row["work_key"])
        for shard in shards
        for row in shard
    ]

    assert candidate["scope"]["continuation_records"] == 5058
    assert [len(shard) for shard in shards] == [1265, 1265, 1264, 1264]
    assert len(keys) == len(set(keys)) == 5058
    assert candidate["scope"]["recovery"]["fresh_full_partition"] is True
    assert candidate["scope"]["recovery"]["old_v1_records_reused"] is False
    assert candidate["scope"]["budget"][
        "projected_primary_total_ceiling_cny"
    ] == 19.6666272
    assert candidate["scope"]["budget"][
        "projected_primary_total_ceiling_cny"
    ] < 20.0
    assert {
        item["execution_identity"]
        for item in candidate["scope"]["shards"]
    }.isdisjoint(
        {
            item["execution_identity"]
            for item in source["scope"]["shards"]
        }
    )
    assert candidate["authorization"][
        "result_admission_authorized"
    ] is False


def test_fresh_admission_binds_exact_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    monkeypatch.setattr(
        continuation_v2,
        "verify_candidate",
        lambda: copy.deepcopy(candidate),
    )

    value = continuation_v2.build_admission(
        0,
        owner_statement_sha256="a" * 64,
        approved_at="2026-07-30T01:40:00+08:00",
    )

    assert value["scope"]["records"] == 1265
    assert value["scope"]["hard_spend_limit_cny"] == 4.9
    assert value["scope"]["exact_command"] == (
        continuation_v2.canonical_shard_command(0)
    )
    assert "--shard-index 0" in value["scope"]["exact_command"]
    assert value["evidence_boundary"]["old_records_reused"] is False
    assert value["authorization"]["shard_execution_authorized"] is True
    assert value["authorization"]["result_admission_authorized"] is False


def test_fresh_admission_rejects_command_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    monkeypatch.setattr(
        continuation_v2,
        "verify_candidate",
        lambda: copy.deepcopy(candidate),
    )
    value = continuation_v2.build_admission(
        0,
        owner_statement_sha256="a" * 64,
        approved_at="2026-07-30T01:40:00+08:00",
    )
    drifted = copy.deepcopy(value)
    drifted["scope"]["exact_command"] += " --unsafe"

    with pytest.raises(
        continuation_v2.PublicShardedContinuationV2Error,
        match="binding drift",
    ):
        continuation_v2._validate_admission_against_candidate(
            drifted,
            candidate=candidate,
            shard_index=0,
        )


def test_state_reconstruction_rejects_non_shard_policy() -> None:
    source = continuation_v1.validate_candidate(
        continuation_v1._load_json(
            continuation_v1.candidate_path("primary")
        ),
        model_role="primary",
    )
    permit = continuation_v2._v1_permit(source, 0)
    global_policy = build_role_policy(
        load_public_policy(),
        "primary",
    )

    with pytest.raises(
        continuation_v2.PublicShardedContinuationV2Error,
        match="frozen shard policy",
    ):
        continuation_v2._state_from_paths(
            permit,
            role_policy=global_policy,
        )
