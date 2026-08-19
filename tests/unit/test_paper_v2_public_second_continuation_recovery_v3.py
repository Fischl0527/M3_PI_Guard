from __future__ import annotations

import pytest

import experiments.paper_v2.public_second_continuation_recovery_v3 as v3
from experiments.paper_v2.contracts import sha256_canonical_json


def _candidate() -> dict[str, object]:
    shards = [
        {
            "shard_index": index,
            "run_id": f"recovery-run-{index}",
            "execution_identity": f"recovery-identity-{index}",
            "records": 652 + 2 * index,
            "hard_spend_limit_cny": 2.0,
        }
        for index in range(v3.SHARD_COUNT)
    ]
    return {"manifest_sha256": "a" * 64, "scope": {"shards": shards}}


def test_flash_recovery_paths_and_commands_are_shard_specific() -> None:
    paths = [v3.admission_path(index) for index in range(v3.SHARD_COUNT)]
    commands = [v3.canonical_command(index) for index in range(v3.SHARD_COUNT)]

    assert len(set(paths)) == v3.SHARD_COUNT
    assert len(set(commands)) == v3.SHARD_COUNT
    assert all(
        f"--shard-index {index}" in command
        for index, command in enumerate(commands)
    )
    assert all("public_second_continuation_recovery_v3" in item for item in commands)


def test_flash_recovery_rejects_out_of_range_shard() -> None:
    with pytest.raises(v3.PublicSecondRecoveryV3Error):
        v3.admission_path(v3.SHARD_COUNT)


def test_flash_recovery_admission_is_hash_and_safety_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(v3, "verify_candidate", _candidate)
    value = v3.build_admission(
        1,
        owner_statement_sha256="b" * 64,
        approved_at="2026-08-03T13:31:00+08:00",
    )

    assert value["authorization"]["maximum_new_records"] == 654
    assert value["authorization"]["automatic_retries"] == 0
    assert value["authorization"]["source_terminal_record_replay_authorized"] is False
    assert value["authorization"]["provider_tools_enabled"] is False
    assert value["authorization"]["external_effects_enabled"] is False
    assert value["manifest_sha256"] == sha256_canonical_json(
        {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
    )


def test_flash_recovery_budget_is_monotone_and_diagnostic_does_not_stop() -> None:
    assert v3._remaining_limit(2.49383904, 0.45265576) == 2.04118328
    assert v3._stop_after_terminal_record(budget_paused=False) is False
    assert v3._stop_after_terminal_record(budget_paused=True) is True

    with pytest.raises(v3.PublicSecondRecoveryV3Error, match="no remaining"):
        v3._remaining_limit(1.0, 1.0)
