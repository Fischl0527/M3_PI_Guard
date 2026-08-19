from __future__ import annotations

import copy

import pytest

from experiments.paper_v2.provider_request_trace_candidate import (
    FIXED_MESSAGES,
    ProviderRequestTraceError,
    _as_official_receipt,
    _fixture_client,
    _load_trace_rows,
    append_completed_trace,
    append_started_trace,
    build_policy_candidate,
    build_qualification,
    build_request_commitment,
    validate_trace_rows,
)


def _commitment(provider_id: str):
    client = _fixture_client(provider_id, include_request_id=False)
    commitment = build_request_commitment(
        client,
        FIXED_MESSAGES,
        execution_identity="test-execution",
        work_key=f"test-{provider_id}",
        call_index=1,
        attempt_id=f"attempt-{provider_id}",
        precommitted_at="2026-07-24T01:10:00+08:00",
    )
    return client, commitment


def test_candidate_policy_never_activates_or_retroactively_upgrades() -> None:
    policy = build_policy_candidate()

    assert policy["status"] == "qualified_candidate_not_activated"
    assert policy["v1_contract_unchanged"] is True
    assert policy["v1_artifacts_retroactively_eligible"] is False
    assert policy["formal_execution_authorized"] is False
    assert policy["activation_requires_explicit_user_confirmation"] is True


def test_precommitted_trace_binds_missing_provider_request_header(
    tmp_path,
) -> None:
    client, commitment = _commitment("deepseek")
    path = tmp_path / "trace.jsonl"
    started = append_started_trace(path, commitment)
    completion = client.complete(FIXED_MESSAGES, step=1)
    terminal = append_completed_trace(
        path,
        client_request_id=commitment["client_request_id"],
        receipt=_as_official_receipt(completion.receipt),
    )
    status = validate_trace_rows(_load_trace_rows(path))
    attestation = terminal["event"]["attestation"]

    assert started["event"]["commitment"]["payload_sha256"]
    assert status["completed_requests"] == 1
    assert status["open_requests"] == 0
    assert (
        attestation["trace_mode"]
        == "precommitted_local_plus_provider_response"
    )
    assert attestation["provider_request_id"] is None
    assert attestation["provider_response_id"]
    assert attestation["v1_formal_candidate"] is False
    assert attestation["v2_schema_activation_required"] is True


def test_posthoc_completion_and_payload_drift_are_rejected(tmp_path) -> None:
    client, commitment = _commitment("deepseek")
    receipt = _as_official_receipt(
        client.complete(FIXED_MESSAGES, step=1).receipt
    )
    with pytest.raises(
        ProviderRequestTraceError,
        match="persisted precommitment",
    ):
        append_completed_trace(
            tmp_path / "missing.jsonl",
            client_request_id=commitment["client_request_id"],
            receipt=receipt,
        )

    path = tmp_path / "drift.jsonl"
    append_started_trace(path, commitment)
    drifted = copy.deepcopy(receipt)
    drifted["evidence"]["payload_sha256"] = "f" * 64
    from experiments.paper_v2.contracts import sha256_canonical_json

    drifted["evidence_sha256"] = sha256_canonical_json(
        drifted["evidence"]
    )
    with pytest.raises(
        ProviderRequestTraceError,
        match="precommitted request",
    ):
        append_completed_trace(
            path,
            client_request_id=commitment["client_request_id"],
            receipt=drifted,
        )


def test_hash_chain_tamper_and_duplicate_terminal_are_rejected(
    tmp_path,
) -> None:
    client, commitment = _commitment("gemini")
    path = tmp_path / "trace.jsonl"
    append_started_trace(path, commitment)
    receipt = _as_official_receipt(
        client.complete(FIXED_MESSAGES, step=1).receipt
    )
    append_completed_trace(
        path,
        client_request_id=commitment["client_request_id"],
        receipt=receipt,
    )
    with pytest.raises(ProviderRequestTraceError, match="already terminal"):
        append_completed_trace(
            path,
            client_request_id=commitment["client_request_id"],
            receipt=receipt,
        )

    rows = _load_trace_rows(path)
    rows[0]["event"]["commitment"]["work_key"] = "tampered"
    with pytest.raises(ProviderRequestTraceError, match="digest drift"):
        validate_trace_rows(rows)


def test_offline_qualification_covers_both_modes_and_negatives() -> None:
    qualification = build_qualification()

    assert qualification["qualified_provider_count"] == 2
    assert qualification["negative_cases_rejected"] == 3
    assert qualification["append_flush_fsync"] is True
    assert qualification["network_calls_made"] == 0
    assert qualification["formal_results_created"] == 0
    assert qualification["v2_schema_activated"] is False
