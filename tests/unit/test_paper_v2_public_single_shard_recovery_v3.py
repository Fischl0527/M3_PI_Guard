from __future__ import annotations

import experiments.paper_v2.public_single_shard_recovery_v3 as v3
from experiments.paper_v2.contracts import sha256_canonical_json


def _candidate(shard_index: int) -> dict[str, object]:
    return {
        "manifest_sha256": "a" * 64,
        "scope": {
            "shard_index": shard_index,
            "run_id": f"run-{shard_index}",
            "execution_identity": f"identity-{shard_index}",
            "untouched_record_count": 100,
        },
    }


def test_single_shard_paths_are_disjoint() -> None:
    candidates = [v3.candidate_path(index) for index in range(4)]
    admissions = [v3.admission_path(index) for index in range(4)]

    assert len(set(candidates)) == 4
    assert len(set(admissions)) == 4


def test_single_shard_command_is_exactly_scoped() -> None:
    command = v3.canonical_command(2)

    assert "--execute-shard" in command
    assert "--shard-index 2" in command
    assert "continuation_s2_admission_v3.json" in command
    assert "retry" not in command.lower()


def test_single_shard_admission_preserves_safety(
    monkeypatch,
) -> None:
    monkeypatch.setattr(v3, "verify_candidate", _candidate)
    value = v3.build_admission(
        1,
        owner_statement_sha256="b" * 64,
        approved_at="2026-07-30T03:12:00+08:00",
    )

    assert value["authorization"]["shard_index"] == 1
    assert value["authorization"]["maximum_new_records"] == 100
    assert value["authorization"]["automatic_retries"] == 0
    assert value["authorization"]["provider_tools_enabled"] is False
    assert value["authorization"]["external_effects_enabled"] is False
    assert (
        value["authorization"]["terminal_diagnostic_retry_authorized"]
        is False
    )
    assert value["manifest_sha256"] == sha256_canonical_json(
        {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
    )
