"""面向免提供商请求 ID 环境的前瞻性 Gemini 轨迹附加运行时。

基于本地自生成时间序列 GUID 实现可信的跨请求因果关联。
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Mapping

from experiments.paper_v2.gemini_public_trace_v1 import validate_trace_bundle


CONTRACT_ID = "gemini_local_precommit_plus_official_response_v2"
_ATTESTATION_FIELDS = frozenset(
    {
        "endpoint_type",
        "provider_name",
        "upstream_provider",
        "model_id",
        "model_revision",
        "request_id",
        "response_id",
        "requested_at",
        "parameters_sha256",
        "prompt_rewrite_declaration",
        "identity_evidence",
        "identity_verified",
        "evidence_level",
    }
)


class GeminiTraceAttachingRuntimeV2Error(RuntimeError):
    """当运行时结果无法满足预期契约时抛出的异常。"""


def _started_at(bundle: Mapping[str, Any], client_request_id: str) -> str:
    matches: list[str] = []
    for row in bundle["trace_rows"]:
        event = row.get("event")
        if not isinstance(event, Mapping) or event.get("event_type") != "started":
            continue
        commitment = event.get("commitment")
        if (
            isinstance(commitment, Mapping)
            and commitment.get("client_request_id") == client_request_id
        ):
            value = commitment.get("precommitted_at")
            if isinstance(value, str) and value:
                matches.append(value)
    if len(matches) != 1:
        raise GeminiTraceAttachingRuntimeV2Error(
            "Gemini formal trace must have one pretransport timestamp"
        )
    return matches[0]


def _validate_trace_modes(bundle: Mapping[str, Any]) -> None:
    activated = bundle["activated_attestations"]
    if (
        not activated
        or bundle.get("bundle_status") != "completed"
        or bundle.get("result_tier_ceiling") != "formal_candidate"
        or bundle.get("open_request_count") != 0
        or bundle.get("failures") != []
        or bundle.get("completed_request_count") != bundle.get("request_count")
        or len(activated) != bundle.get("request_count")
        or len(bundle.get("usage_evidence", [])) != bundle.get("request_count")
        or bundle.get("append_flush_fsync") is not True
        or bundle.get("automatic_retry") is not False
        or bundle.get("provider_tools_declared") is not False
        or bundle.get("external_effects_enabled") is not False
        or bundle.get("prompt_or_response_content_stored") is not False
        or bundle.get("usage_summary", {}).get("billing_tier") != "free"
        or bundle.get("usage_summary", {}).get("charged_usd") != 0.0
        or bundle.get("usage_summary", {}).get("paid_ceiling_usd") != 0.0
    ):
        raise GeminiTraceAttachingRuntimeV2Error(
            "Gemini bundle is not a complete free-tier formal candidate"
        )
    for item in activated:
        mode = item.get("trace_mode")
        provider_request_id = item.get("provider_request_id")
        if mode == "provider_dual_id_plus_precommitted_local":
            valid = isinstance(provider_request_id, str) and bool(
                provider_request_id
            )
        elif mode == "precommitted_local_plus_provider_response":
            valid = provider_request_id is None
        else:
            valid = False
        if not valid:
            raise GeminiTraceAttachingRuntimeV2Error(
                "Gemini trace mode and provider request identity disagree"
            )


def _validate_existing_attestation(
    attestation: Any,
    *,
    bundle: Mapping[str, Any],
    allow_missing_provider_request_id: bool,
) -> None:
    if not isinstance(attestation, Mapping) or set(attestation) != _ATTESTATION_FIELDS:
        raise GeminiTraceAttachingRuntimeV2Error(
            "Gemini runtime attestation fields drift"
        )
    last = bundle["activated_attestations"][-1]
    provider_request_id = last.get("provider_request_id")
    expected_level = (
        "diagnostic_only"
        if allow_missing_provider_request_id
        else "formal_candidate"
    )
    if (
        attestation.get("endpoint_type") != "official_api"
        or attestation.get("provider_name") != "Google"
        or attestation.get("upstream_provider") != "Google"
        or attestation.get("model_id") != bundle["model_id"]
        or attestation.get("model_revision") is not None
        or attestation.get("request_id") != provider_request_id
        or attestation.get("response_id") != last["provider_response_id"]
        or not isinstance(attestation.get("requested_at"), str)
        or not attestation["requested_at"]
        or attestation.get("parameters_sha256") != last["payload_sha256"]
        or attestation.get("prompt_rewrite_declaration") != "none_declared"
        or attestation.get("identity_evidence") != "official_response"
        or attestation.get("identity_verified") is not True
        or attestation.get("evidence_level") != expected_level
    ):
        raise GeminiTraceAttachingRuntimeV2Error(
            "Gemini runtime attestation does not bind the formal trace"
        )
    if allow_missing_provider_request_id and (
        provider_request_id is not None
        or last.get("trace_mode")
        != "precommitted_local_plus_provider_response"
    ):
        raise GeminiTraceAttachingRuntimeV2Error(
            "Gemini diagnostic promotion is not the missing-request-ID case"
        )


def _formal_attestation(bundle: Mapping[str, Any]) -> dict[str, Any]:
    last = bundle["activated_attestations"][-1]
    client_request_id = str(last["client_request_id"])
    provider_request_id = last.get("provider_request_id")
    return {
        "endpoint_type": "official_api",
        "provider_name": "Google",
        "upstream_provider": "Google",
        "model_id": str(bundle["model_id"]),
        "model_revision": None,
        # This field remains the provider-issued request ID.  It is never
        # populated with the local ID when Google does not return one.
        "request_id": provider_request_id,
        "response_id": str(last["provider_response_id"]),
        "requested_at": _started_at(bundle, client_request_id),
        "parameters_sha256": str(last["payload_sha256"]),
        "prompt_rewrite_declaration": "none_declared",
        "identity_evidence": "official_response_plus_pretransport_commitment",
        "identity_verified": True,
        "evidence_level": "formal_candidate",
        "formal_evidence_contract": CONTRACT_ID,
        "client_request_id": client_request_id,
        "request_identity_mode": str(last["trace_mode"]),
        "provider_request_id_available": provider_request_id is not None,
    }


class GeminiTraceAttachingRuntimeV2:
    """附加完整的 Gemini 包并狭义提升其论据层级。"""

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
            raise GeminiTraceAttachingRuntimeV2Error(
                "Gemini runtime result must be an object"
            )
        client = self.client_lookup(str(context.work_key))
        if client is None or not callable(getattr(client, "build_bundle", None)):
            raise GeminiTraceAttachingRuntimeV2Error(
                "Gemini traced client is unavailable after runtime execution"
            )
        bundle = validate_trace_bundle(client.build_bundle())
        if (
            bundle.get("execution_identity") != context.execution_identity
            or bundle.get("work_key") != context.work_key
            or bundle.get("provider_id") != "gemini"
        ):
            raise GeminiTraceAttachingRuntimeV2Error(
                "Gemini trace bundle does not bind the runtime context"
            )
        existing_bundle = observed.get("provider_trace_bundle")
        if existing_bundle is not None and dict(existing_bundle) != bundle:
            raise GeminiTraceAttachingRuntimeV2Error(
                "Gemini runtime emitted a conflicting trace bundle"
            )
        current_tier = str(observed.get("result_tier", ""))
        bundle_tier = str(bundle.get("result_tier_ceiling", ""))
        if current_tier not in {"formal_candidate", "diagnostic"}:
            raise GeminiTraceAttachingRuntimeV2Error(
                "Gemini runtime tier is outside the prospective formal path"
            )
        result = copy.deepcopy(dict(observed))
        result["provider_trace_bundle"] = copy.deepcopy(bundle)
        existing_attestation = observed.get("provider_attestation")

        if bundle_tier == "diagnostic":
            if (
                not isinstance(existing_attestation, Mapping)
                or existing_attestation.get("response_id") is not None
            ):
                raise GeminiTraceAttachingRuntimeV2Error(
                    "incomplete Gemini trace cannot retain a response claim"
                )
            result["result_tier"] = "diagnostic"
            return result
        if bundle_tier != "formal_candidate":
            raise GeminiTraceAttachingRuntimeV2Error(
                "Gemini trace bundle has an unsupported evidence ceiling"
            )

        _validate_trace_modes(bundle)
        if current_tier == "diagnostic":
            _validate_existing_attestation(
                existing_attestation,
                bundle=bundle,
                allow_missing_provider_request_id=True,
            )
        elif existing_attestation is not None:
            _validate_existing_attestation(
                existing_attestation,
                bundle=bundle,
                allow_missing_provider_request_id=False,
            )
        result["provider_attestation"] = _formal_attestation(bundle)
        result["result_tier"] = "formal_candidate"
        return result


__all__ = [
    "CONTRACT_ID",
    "GeminiTraceAttachingRuntimeV2",
    "GeminiTraceAttachingRuntimeV2Error",
]
