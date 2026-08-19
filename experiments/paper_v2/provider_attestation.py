"""Create a redacted provider identity receipt from one explicit smoke response.

The caller supplies already-redacted response metadata.  This module performs no
HTTP request, accepts no authorization header, and stores neither prompts nor
response content.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping
from urllib.parse import urlparse

from experiments.paper_v2.contracts import canonical_json_bytes


OFFICIAL_OPENAI_ORIGIN = "https://api.openai.com"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
}


class ProviderAttestationError(ValueError):
    """Raised when smoke metadata cannot support a formal identity claim."""


def _nonempty_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderAttestationError(f"{label} must be a non-empty string")
    return value.strip()


def _usage_token(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProviderAttestationError(f"{label} must be a non-negative integer")
    return value


def build_smoke_receipt(
    *,
    endpoint_url: str,
    expected_model_id: str,
    request_payload_sha256: str,
    response_headers: Mapping[str, str],
    response_metadata: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    """Validate one response envelope and return content-free attestation."""

    expected_model = _nonempty_string(
        expected_model_id, label="expected_model_id"
    )
    parsed = urlparse(_nonempty_string(endpoint_url, label="endpoint_url"))
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin != OFFICIAL_OPENAI_ORIGIN or parsed.path != "/v1/responses":
        raise ProviderAttestationError(
            "formal OpenAI smoke must use https://api.openai.com/v1/responses"
        )
    if not SHA256_PATTERN.fullmatch(request_payload_sha256):
        raise ProviderAttestationError(
            "request_payload_sha256 must be a lowercase SHA-256 digest"
        )

    headers = {str(key).lower(): str(value) for key, value in response_headers.items()}
    forbidden = sorted(FORBIDDEN_HEADER_NAMES.intersection(headers))
    if forbidden:
        raise ProviderAttestationError(
            "credential-bearing headers must not enter attestation: "
            + ", ".join(forbidden)
        )
    request_id = _nonempty_string(
        headers.get("x-request-id"), label="x-request-id"
    )
    response_id = _nonempty_string(
        response_metadata.get("id"), label="response id"
    )
    returned_model = _nonempty_string(
        response_metadata.get("model"), label="returned model"
    )
    if returned_model != expected_model:
        raise ProviderAttestationError(
            f"returned model {returned_model!r} does not match {expected_model!r}"
        )
    usage = response_metadata.get("usage")
    if not isinstance(usage, Mapping):
        raise ProviderAttestationError("response usage metadata is required")
    input_tokens = _usage_token(
        usage.get("input_tokens"), label="usage.input_tokens"
    )
    output_tokens = _usage_token(
        usage.get("output_tokens"), label="usage.output_tokens"
    )
    observed = _nonempty_string(observed_at, label="observed_at")
    evidence = {
        "endpoint_origin": origin,
        "endpoint_path": parsed.path,
        "expected_model_id": expected_model,
        "returned_model_id": returned_model,
        "request_id": request_id,
        "response_id": response_id,
        "request_payload_sha256": request_payload_sha256,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
        "observed_at": observed,
    }
    return {
        "schema_version": "m3-paper-v2-provider-smoke-receipt-1.0",
        "status": "identity_attested_redaction_review_pending",
        "network_call_performed_by_this_module": False,
        "credentials_stored": False,
        "prompt_or_response_content_stored": False,
        "identity_verified": True,
        "request_id_available": True,
        "response_id_available": True,
        "evidence": evidence,
        "evidence_sha256": hashlib.sha256(
            canonical_json_bytes(evidence)
        ).hexdigest(),
    }


def validate_smoke_receipt(receipt: Mapping[str, Any]) -> None:
    """Validate a stored receipt without needing the original response."""

    if receipt.get("schema_version") != (
        "m3-paper-v2-provider-smoke-receipt-1.0"
    ):
        raise ProviderAttestationError("unsupported smoke receipt schema")
    if receipt.get("network_call_performed_by_this_module") is not False:
        raise ProviderAttestationError("receipt misstates module network behavior")
    if receipt.get("credentials_stored") is not False:
        raise ProviderAttestationError("receipt must not store credentials")
    if receipt.get("prompt_or_response_content_stored") is not False:
        raise ProviderAttestationError(
            "identity receipt must not store prompt or response content"
        )
    evidence = receipt.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ProviderAttestationError("receipt evidence is required")
    expected_digest = hashlib.sha256(canonical_json_bytes(evidence)).hexdigest()
    if receipt.get("evidence_sha256") != expected_digest:
        raise ProviderAttestationError("smoke receipt evidence digest mismatch")


def main() -> int:
    print(
        json.dumps(
            {
                "schema_version": "m3-paper-v2-provider-attestation-tool-1.0",
                "status": "offline_ready_no_smoke_supplied",
                "network_calls_made": 0,
                "credentials_read": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
