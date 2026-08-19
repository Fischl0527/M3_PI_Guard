from __future__ import annotations

import copy

import pytest

from experiments.paper_v2.provider_request_trace_activation import (
    ProviderRequestTraceActivationError,
    activate_trace_attestation,
    build_activation,
    validate_activated_attestation,
    validate_activation,
    verify_activation,
    write_activation,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    FIXED_MESSAGES,
    _as_official_receipt,
    _fixture_client,
    append_completed_trace,
    append_started_trace,
    build_request_commitment,
)


def _candidate_attestation(tmp_path, provider_id: str):
    client = _fixture_client(provider_id, include_request_id=False)
    commitment = build_request_commitment(
        client,
        FIXED_MESSAGES,
        execution_identity="activation-test",
        work_key=f"activation-{provider_id}",
        call_index=1,
        attempt_id=f"activation-attempt-{provider_id}",
        precommitted_at="2026-07-24T01:03:51.9003883+08:00",
    )
    ledger = tmp_path / f"{provider_id}.jsonl"
    append_started_trace(ledger, commitment)
    terminal = append_completed_trace(
        ledger,
        client_request_id=commitment["client_request_id"],
        receipt=_as_official_receipt(
            client.complete(FIXED_MESSAGES, step=1).receipt
        ),
    )
    return terminal["event"]["attestation"]


def test_activation_records_narrow_user_approval() -> None:
    value = build_activation()
    validate_activation(value)

    assert value["approval_scope"]["provider_ids"] == ["deepseek"]
    assert value["request_trace_protocol_activated"] is True
    assert value["fresh_prospective_requests_only"] is True
    assert value["v1_contract_unchanged"] is True
    assert value["historical_artifacts_retroactively_eligible"] is False
    assert value["formal_matrix_authorized"] is False
    assert value["network_calls_made"] == 0


def test_deepseek_candidate_becomes_prospectively_trace_eligible(
    tmp_path,
) -> None:
    activation_path = tmp_path / "activation.json"
    write_activation(activation_path)
    candidate = _candidate_attestation(tmp_path, "deepseek")

    value = activate_trace_attestation(
        candidate,
        activation_path=activation_path,
    )

    assert value["provider_id"] == "deepseek"
    assert value["provider_request_id"] is None
    assert (
        value["evidence_level"]
        == "prospective_formal_trace_eligible_v2"
    )
    assert value["v2_trace_eligible"] is True
    assert value["retroactive_upgrade_allowed"] is False


def test_unapproved_provider_and_trace_mode_drift_are_rejected(
    tmp_path,
) -> None:
    activation_path = tmp_path / "activation.json"
    written = write_activation(activation_path)
    assert verify_activation(activation_path) == written

    gemini = _candidate_attestation(tmp_path, "gemini")
    with pytest.raises(
        ProviderRequestTraceActivationError,
        match="outside the approved trace scope",
    ):
        activate_trace_attestation(
            gemini,
            activation_path=activation_path,
        )

    deepseek = activate_trace_attestation(
        _candidate_attestation(tmp_path, "deepseek"),
        activation_path=activation_path,
    )
    drifted = copy.deepcopy(deepseek)
    drifted["trace_mode"] = "provider_dual_id_plus_precommitted_local"
    with pytest.raises(
        ProviderRequestTraceActivationError,
        match="missing provider request ID",
    ):
        validate_activated_attestation(drifted)
