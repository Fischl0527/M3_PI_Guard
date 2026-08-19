from __future__ import annotations

import copy
import json

import pytest

from experiments.paper_v2.provider_gate import (
    DEFAULT_DECISION,
    DEFAULT_OUTPUT,
    ProviderGateError,
    build_preflight,
    estimate_cost,
    validate_decision,
)


def _decision() -> dict:
    return json.loads(DEFAULT_DECISION.read_text(encoding="utf-8"))


def test_candidate_is_offline_unapproved_and_costed_for_all_480_records() -> None:
    preflight = build_preflight()

    assert preflight["network_calls_made"] == 0
    assert preflight["credentials_read"] is False
    assert preflight["gate_pass"] is False
    assert preflight["status"] == "blocked_runtime_attestation_and_user_approval"
    assert preflight["cost_estimate"]["work_items"] == 480
    assert preflight["cost_estimate"]["provider_calls_upper_bound"] == 4416
    assert preflight["cost_estimate"]["total_cost_upper_bound_usd"] > 0


def test_frozen_preflight_reproduces() -> None:
    assert json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8")) == build_preflight()


def test_decision_rejects_placeholder_and_secret_fields() -> None:
    placeholder = _decision()
    placeholder["provider_attestation"]["model_id"] = "<model>"
    with pytest.raises(ProviderGateError, match="placeholder"):
        validate_decision(placeholder)

    secret = _decision()
    secret["api_key"] = "sk-this-must-never-be-stored"
    with pytest.raises(ProviderGateError, match="credential-like fields"):
        validate_decision(secret)


def test_gate_can_pass_only_after_attestation_review_approval_and_cost_headroom() -> None:
    decision = _decision()
    estimate = estimate_cost(decision)
    decision["approved_by_user"] = True
    decision["provider_attestation"]["identity_verified"] = True
    decision["provider_attestation"]["request_id_available"] = True
    decision["provider_attestation"]["response_id_available"] = True
    decision["logging"]["redaction_reviewed"] = True
    decision["cost"]["hard_spend_limit_usd"] = (
        estimate["total_cost_upper_bound_usd"] / 0.9 + 1
    )

    validate_decision(decision)


def test_hard_limit_below_abort_ceiling_remains_blocked(tmp_path) -> None:
    decision = _decision()
    decision["approved_by_user"] = True
    decision["provider_attestation"]["identity_verified"] = True
    decision["provider_attestation"]["request_id_available"] = True
    decision["provider_attestation"]["response_id_available"] = True
    decision["logging"]["redaction_reviewed"] = True
    decision["cost"]["hard_spend_limit_usd"] = 0.01
    path = tmp_path / "decision.json"
    path.write_text(json.dumps(decision), encoding="utf-8")

    preflight = build_preflight(path)

    assert preflight["gate_pass"] is False
    assert any("abort ceiling" in blocker for blocker in preflight["blockers"])


def test_abort_fraction_above_ninety_percent_is_rejected() -> None:
    decision = copy.deepcopy(_decision())
    decision["cost"]["abort_at_fraction"] = 0.91

    with pytest.raises(ProviderGateError, match="must be <= 0.9"):
        validate_decision(decision)
