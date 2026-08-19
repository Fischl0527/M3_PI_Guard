"""Attach the Gemini-specific trace bundle without mutating frozen runtimes.

The historical live runtime recognizes the DeepSeek ``TracedProviderClient``
concrete class.  Gemini uses an independently validated trace implementation,
so a successful Gemini call otherwise reaches the executor shell without its
bundle.  This prospective adapter keeps the historical runtime immutable and
attaches only the already-validated, content-free Gemini bundle.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Mapping

from experiments.paper_v2.gemini_public_trace_v1 import validate_trace_bundle


class GeminiTraceAttachingRuntimeV1Error(RuntimeError):
    """Raised when runtime output and the Gemini trace chain do not bind."""


def _formal_attestation_from_bundle(
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    activated = bundle["activated_attestations"]
    if not activated:
        raise GeminiTraceAttachingRuntimeV1Error(
            "formal Gemini trace bundle has no activated response"
        )
    last = activated[-1]
    request_id = str(last["client_request_id"])
    started_at: str | None = None
    for row in reversed(bundle["trace_rows"]):
        event = row.get("event")
        if not isinstance(event, Mapping) or event.get("event_type") != "started":
            continue
        commitment = event.get("commitment")
        if (
            isinstance(commitment, Mapping)
            and commitment.get("client_request_id") == request_id
        ):
            started_at = str(commitment["precommitted_at"])
            break
    if not started_at:
        raise GeminiTraceAttachingRuntimeV1Error(
            "formal Gemini trace bundle lacks its pre-transport timestamp"
        )
    return {
        "endpoint_type": "official_api",
        "provider_name": "Google",
        "upstream_provider": "Google",
        "model_id": str(bundle["model_id"]),
        "model_revision": None,
        "request_id": last.get("provider_request_id"),
        "response_id": str(last["provider_response_id"]),
        "requested_at": started_at,
        "parameters_sha256": str(last["payload_sha256"]),
        "prompt_rewrite_declaration": "none_declared",
        "identity_evidence": "official_response",
        "identity_verified": True,
        "evidence_level": "formal_candidate",
    }


class GeminiTraceAttachingRuntimeV1:
    """Decorate an online runtime with a fail-closed Gemini bundle attachment."""

    def __init__(
        self,
        delegate: Any,
        *,
        client_lookup: Callable[[str], Any | None],
    ) -> None:
        self.delegate = delegate
        self.client_lookup = client_lookup

    def execute(self, context: Any, profile: Any) -> Mapping[str, Any]:
        observed = self.delegate.execute(context, profile)
        if not isinstance(observed, Mapping):
            raise GeminiTraceAttachingRuntimeV1Error(
                "Gemini runtime result must be an object"
            )
        client = self.client_lookup(str(context.work_key))
        if client is None or not callable(getattr(client, "build_bundle", None)):
            raise GeminiTraceAttachingRuntimeV1Error(
                "Gemini traced client is unavailable after runtime execution"
            )
        bundle = validate_trace_bundle(client.build_bundle())
        if (
            bundle.get("execution_identity") != context.execution_identity
            or bundle.get("work_key") != context.work_key
            or bundle.get("provider_id") != "gemini"
        ):
            raise GeminiTraceAttachingRuntimeV1Error(
                "Gemini trace bundle does not bind the runtime context"
            )
        existing = observed.get("provider_trace_bundle")
        if existing is not None and dict(existing) != bundle:
            raise GeminiTraceAttachingRuntimeV1Error(
                "Gemini runtime emitted a conflicting trace bundle"
            )
        current_tier = str(observed.get("result_tier", ""))
        bundle_tier = str(bundle["result_tier_ceiling"])
        if current_tier not in {
            "formal_candidate",
            "diagnostic",
            "qualification",
        }:
            raise GeminiTraceAttachingRuntimeV1Error(
                "Gemini runtime result tier is not formally admissible"
            )
        result = copy.deepcopy(dict(observed))
        result["provider_trace_bundle"] = copy.deepcopy(bundle)
        result["result_tier"] = (
            "diagnostic"
            if "diagnostic" in {current_tier, bundle_tier}
            else "formal_candidate"
        )
        if result["result_tier"] == "formal_candidate":
            attestation = _formal_attestation_from_bundle(bundle)
            existing_attestation = observed.get("provider_attestation")
            if (
                isinstance(existing_attestation, Mapping)
                and existing_attestation.get("identity_verified") is True
            ):
                last = bundle["activated_attestations"][-1]
                if (
                    existing_attestation.get("provider_name") != "Google"
                    or existing_attestation.get("upstream_provider") != "Google"
                    or existing_attestation.get("model_id") != bundle["model_id"]
                    or existing_attestation.get("response_id")
                    != last["provider_response_id"]
                    or existing_attestation.get("parameters_sha256")
                    != last["payload_sha256"]
                ):
                    raise GeminiTraceAttachingRuntimeV1Error(
                        "Gemini runtime emitted a conflicting formal attestation"
                    )
                result["provider_attestation"] = copy.deepcopy(
                    dict(existing_attestation)
                )
            else:
                result["provider_attestation"] = attestation
        else:
            existing_attestation = observed.get("provider_attestation")
            if (
                isinstance(existing_attestation, Mapping)
                and existing_attestation.get("response_id") is not None
            ):
                raise GeminiTraceAttachingRuntimeV1Error(
                    "incomplete Gemini trace cannot retain a response claim"
                )
        return result


__all__ = [
    "GeminiTraceAttachingRuntimeV1",
    "GeminiTraceAttachingRuntimeV1Error",
]
