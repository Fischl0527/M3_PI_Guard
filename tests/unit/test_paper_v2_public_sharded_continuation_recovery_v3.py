from __future__ import annotations

from pathlib import Path

import pytest

import experiments.paper_v2.public_sharded_continuation_recovery_v3 as v3
from experiments.paper_v2.contracts import sha256_canonical_json


def _candidate() -> dict[str, object]:
    shards = [
        {
            "shard_index": index,
            "run_id": f"run-{index}",
            "execution_identity": f"identity-{index}",
            "untouched_record_count": 100 + index,
        }
        for index in range(v3.SHARD_COUNT)
    ]
    return {
        "manifest_sha256": "a" * 64,
        "scope": {"shards": shards},
    }


def test_public_v3_paths_and_commands_are_shard_specific() -> None:
    paths = [v3.admission_path(index) for index in range(v3.SHARD_COUNT)]
    commands = [
        v3.canonical_command(index) for index in range(v3.SHARD_COUNT)
    ]

    assert len(set(paths)) == v3.SHARD_COUNT
    assert len(set(commands)) == v3.SHARD_COUNT
    assert all(
        f"--shard-index {index}" in command
        for index, command in enumerate(commands)
    )
    assert all("admission_v3.json" in command for command in commands)


def test_public_v3_rejects_out_of_range_shard() -> None:
    with pytest.raises(v3.PublicShardedRecoveryV3Error):
        v3.admission_path(v3.SHARD_COUNT)


def test_public_v3_admission_is_hash_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(v3, "verify_candidate", _candidate)
    value = v3.build_admission(
        2,
        owner_statement_sha256="b" * 64,
        approved_at="2026-07-30T03:00:00+08:00",
    )

    assert value["authorization"]["shard_index"] == 2
    assert value["authorization"]["maximum_new_records"] == 102
    assert (
        value["manifest_sha256"]
        == sha256_canonical_json(
            {
                key: child
                for key, child in value.items()
                if key != "manifest_sha256"
            }
        )
    )
    assert value["authorization"]["automatic_retries"] == 0
    assert (
        value["authorization"]["terminal_diagnostic_retry_authorized"]
        is False
    )


def test_public_v3_prefix_hash_detects_truncation(tmp_path: Path) -> None:
    path = tmp_path / "prefix.bin"
    path.write_bytes(b"closed-prefix")

    assert v3._sha256_prefix(path, 6)
    with pytest.raises(
        v3.PublicShardedRecoveryV3Error,
        match="truncated",
    ):
        v3._sha256_prefix(path, path.stat().st_size + 1)
