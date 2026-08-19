from __future__ import annotations

import json

import experiments.paper_v2.adaptive_cost_canary_recovery_v3 as v3
from experiments.paper_v2.contracts import sha256_canonical_json


def test_adaptive_v3_frozen_candidate_and_admission_verify() -> None:
    candidate = v3.verify_candidate()
    admission = v3.validate_admission(
        json.loads(v3.ADMISSION_PATH.read_text(encoding="utf-8"))
    )

    assert candidate["scope"]["authorized_continuation_case_ids"] == [
        "M3V2-D-118-A3",
        "M3V2-D-089-A3",
        "M3V2-D-050-A2",
        "M3V2-D-051-A1",
    ]
    assert admission["authorization"]["authorized_case_ids"] == candidate[
        "scope"
    ]["authorized_continuation_case_ids"]
    assert admission["authorization"]["automatic_retries"] == 0
    assert admission["authorization"]["provider_tools_enabled"] is False
    assert admission["authorization"]["external_effects_enabled"] is False
    assert (
        admission["authorization"]["terminal_diagnostic_retry_authorized"]
        is False
    )


def test_adaptive_v2_recovery_review_is_hash_bound() -> None:
    review = json.loads(v3.RECOVERY_REVIEW.read_text(encoding="utf-8"))
    core = {
        key: child
        for key, child in review.items()
        if key != "manifest_sha256"
    }

    assert review["manifest_sha256"] == sha256_canonical_json(core)
    assert review["terminal_query_count"] == 174
    assert review["diagnostic_query_count"] == 1
    assert review["checks"]["dual_prompt_hash_semantics_verified"] is True
    assert review["checks"]["terminal_diagnostic_retry_authorized"] is False
    assert sum(
        binding["query_count"]
        for binding in review["checkpoint_bindings"].values()
    ) == review["terminal_query_count"]


def test_adaptive_v3_exact_command_preserves_safety_boundary() -> None:
    command = v3.canonical_command()

    assert "--execute-continuation" in command
    assert "adaptive_cost_canary_admission_v3.json" in command
    assert "--config config\\project.local.env" in command
    assert "retry" not in command.lower()
