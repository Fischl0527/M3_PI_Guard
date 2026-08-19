from __future__ import annotations

import pytest

from experiments.paper_v2.provider_attestation import (
    ProviderAttestationError,
    build_smoke_receipt,
    validate_smoke_receipt,
)


def _receipt(**overrides):
    values = {
        "endpoint_url": "https://api.openai.com/v1/responses",
        "expected_model_id": "gpt-5.6-terra",
        "request_payload_sha256": "a" * 64,
        "response_headers": {"x-request-id": "req_http_123"},
        "response_metadata": {
            "id": "resp_123",
            "model": "gpt-5.6-terra",
            "usage": {"input_tokens": 20, "output_tokens": 4},
        },
        "observed_at": "2026-07-23T20:45:00+08:00",
    }
    values.update(overrides)
    return build_smoke_receipt(**values)


def test_smoke_receipt_attests_ids_without_content_or_credentials() -> None:
    receipt = _receipt()

    validate_smoke_receipt(receipt)
    assert receipt["identity_verified"] is True
    assert receipt["request_id_available"] is True
    assert receipt["response_id_available"] is True
    assert receipt["credentials_stored"] is False
    assert "output" not in receipt["evidence"]


def test_model_mismatch_and_nonofficial_endpoint_are_rejected() -> None:
    with pytest.raises(ProviderAttestationError, match="does not match"):
        _receipt(
            response_metadata={
                "id": "resp_123",
                "model": "another-model",
                "usage": {"input_tokens": 20, "output_tokens": 4},
            }
        )
    with pytest.raises(ProviderAttestationError, match="must use"):
        _receipt(endpoint_url="https://relay.example/v1/responses")


def test_credential_headers_are_rejected() -> None:
    with pytest.raises(ProviderAttestationError, match="must not enter"):
        _receipt(
            response_headers={
                "x-request-id": "req_http_123",
                "authorization": "redacted-but-forbidden",
            }
        )


def test_receipt_digest_detects_tampering() -> None:
    receipt = _receipt()
    receipt["evidence"]["returned_model_id"] = "tampered"

    with pytest.raises(ProviderAttestationError, match="digest mismatch"):
        validate_smoke_receipt(receipt)
