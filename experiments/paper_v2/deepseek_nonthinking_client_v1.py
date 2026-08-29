"""Versioned official DeepSeek client with an explicit non-thinking payload.

DeepSeek-V4-Pro defaults to thinking mode.  The paper-v2 runtime uses a strict
structured-text action protocol, so an omitted toggle can spend the entire
output cap on reasoning and leave no parseable final content.  This client
preserves the single-attempt, credential-redacting official transport while
adding the prospectively committed payload field:

``{"thinking": {"type": "disabled"}}``.

The existing provider client remains unchanged because it is hash-pinned by
the completed pilot and the aborted matrix-v1 evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    OfficialProviderCompletion,
    ProviderBudgetState,
    ProviderIdentityError,
    ProviderPausedError,
    ProviderPayloadError,
    ProviderTransportError,
    ProviderUsageError,
    _canonical_bytes,
    _default_transport,
    _elapsed_ms,
    _now,
    _optional_int,
    _request_id,
    _safe_headers,
    _sha256_bytes,
    _validate_persisted_value,
    provider_receipt_to_attestation,
    validate_messages,
    validate_provider_receipt,
)
from experiments.paper_v2.provider_request_trace_activation import (
    activate_trace_attestation,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    append_completed_trace,
    append_started_trace,
    bind_trace_attestation,
    validate_request_commitment,
)
from experiments.paper_v2.provider_trace_bundle import (
    ProviderTraceBundleError,
    TracedProviderClient,
    build_deepseek_usage_evidence,
)
from experiments.paper_v2.provider_budget import (
    BudgetPolicyError,
    validate_deepseek_usage,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUDGET_POLICY = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/deepseek_nonthinking_client_qualification_v1.json"
)
QUALIFICATION_RECORDED_AT = "2026-07-24T16:30:00+08:00"
THINKING_CONTROL = {"type": "disabled"}


class DeepSeekNonThinkingOfficialClient(OfficialProviderClient):
    """Official single-attempt client with the DeepSeek thinking toggle frozen."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.provider_id != "deepseek":
            raise ProviderPayloadError(
                "the non-thinking client is restricted to DeepSeek"
            )

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        case: dict[str, Any] | None = None,
        step: int = 1,
        observations: list[Any] | None = None,
    ) -> OfficialProviderCompletion:
        del case, observations
        if isinstance(step, bool) or not isinstance(step, int) or step < 1:
            raise ProviderPayloadError("step must be a positive integer")
        normalized = validate_messages(
            messages,
            content_class=self.content_class,
            policy=self.policy,
            allow_pinned_synthetic_credential_labels=(
                self.allow_pinned_synthetic_credential_labels
            ),
            active_api_key=self.api_key,
        )
        self.budget_state.assert_before_request()
        payload = {
            "model": self.model,
            "messages": normalized,
            "temperature": float(self.temperature),
            "max_tokens": int(self.max_tokens),
            "stream": False,
            "thinking": dict(THINKING_CONTROL),
        }
        if "tools" in payload or "tool_choice" in payload:
            raise ProviderPayloadError("provider-managed tools are forbidden")
        payload_sha256 = _sha256_bytes(_canonical_bytes(payload))
        request_metadata = {
            "provider_id": self.provider_id,
            "model_id": self.model,
            "transport_kind": (
                "official_network"
                if self.transport is None
                else "injected_test_double"
            ),
            "endpoint_origin_and_path": (
                f"{urlparse(self.endpoint).scheme}://"
                f"{urlparse(self.endpoint).netloc}"
                f"{urlparse(self.endpoint).path}"
            ),
            "content_class": self.content_class,
            "payload_sha256": payload_sha256,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "thinking_mode": "disabled",
            "provider_attempts": 1,
            "provider_tools_declared": False,
        }
        if self.allow_pinned_synthetic_credential_labels:
            request_metadata[
                "pinned_synthetic_credential_labels_allowed"
            ] = self.content_class == "public_benchmark_case"
        _validate_persisted_value(request_metadata)
        self.last_request_metadata = request_metadata
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started_ns = perf_counter_ns()
        requested_at = _now()
        envelope = (self.transport or _default_transport)(
            self.endpoint,
            headers,
            payload,
            float(self.timeout),
        )
        latency_ms = _elapsed_ms(started_ns)
        if envelope.status_code == 429:
            raise ProviderPausedError("official provider returned HTTP 429")
        if envelope.status_code < 200 or envelope.status_code >= 300:
            raise ProviderTransportError(
                f"official provider returned HTTP {envelope.status_code}"
            )
        body = envelope.body
        returned_model = str(body.get("model", ""))
        if returned_model != self.model:
            raise ProviderIdentityError(
                "returned model does not match the frozen model identity"
            )
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderTransportError(
                "official provider response has no choices"
            )
        choice = choices[0]
        if not isinstance(choice, Mapping):
            raise ProviderTransportError(
                "official provider choice is malformed"
            )
        message = choice.get("message")
        if not isinstance(message, Mapping):
            raise ProviderTransportError(
                "official provider message is malformed"
            )
        text = str(message.get("content", "") or "")
        finish_reason = str(choice.get("finish_reason", "") or "")
        usage_raw = body.get("usage")
        if not isinstance(usage_raw, Mapping):
            raise ProviderUsageError("official provider usage is required")
        prompt_tokens = _optional_int(usage_raw.get("prompt_tokens"))
        completion_tokens = _optional_int(
            usage_raw.get("completion_tokens")
        )
        total_tokens = _optional_int(usage_raw.get("total_tokens"))
        if prompt_tokens is None or completion_tokens is None:
            raise ProviderUsageError(
                "prompt and completion token usage is required"
            )
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ProviderUsageError(
                "provider token usage must be non-negative"
            )
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens
        if total_tokens < prompt_tokens + completion_tokens:
            raise ProviderUsageError(
                "provider total token usage is inconsistent"
            )
        hit = _optional_int(
            usage_raw.get("prompt_cache_hit_tokens")
        )
        miss = _optional_int(
            usage_raw.get("prompt_cache_miss_tokens")
        )
        if hit is None or miss is None:
            raise ProviderUsageError(
                "DeepSeek cache hit and miss usage are required"
            )
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "prompt_cache_hit_tokens": hit,
            "prompt_cache_miss_tokens": miss,
        }
        try:
            validate_deepseek_usage(usage)
        except BudgetPolicyError as exc:
            raise ProviderUsageError(str(exc)) from exc

        budget = self.budget_state.record_usage(usage)
        request_id = _request_id(_safe_headers(envelope.headers))
        response_id = str(body.get("id", "") or "") or None
        identity_verified = bool(response_id)
        request_trace_complete = bool(request_id and response_id)
        evidence_level = (
            "official_exact_model_with_request_and_response_ids"
            if request_trace_complete
            else (
                "official_exact_model_with_response_id_request_id_unavailable"
                if identity_verified
                else "official_exact_model_missing_response_id"
            )
        )
        evidence = {
            **request_metadata,
            "configured_model": self.model,
            "returned_model": returned_model,
            "model_identity_exact_match": True,
            "http_status": envelope.status_code,
            "request_id": request_id,
            "response_id": response_id,
            "request_trace_complete": request_trace_complete,
            "requested_at": requested_at,
            "response_text_sha256": _sha256_bytes(
                text.encode("utf-8")
            ),
            "response_text_bytes": len(text.encode("utf-8")),
            "finish_reason": finish_reason,
            "usage": usage,
            "budget": budget,
            "prompt_rewrite_declaration": "none_declared",
            "identity_verified": identity_verified,
            "evidence_level": evidence_level,
            "model_latency_ms": latency_ms,
        }
        receipt = {
            "schema_version": (
                "m3-paper-v2-official-provider-receipt-1.0"
            ),
            "credentials_stored": False,
            "prompt_or_response_content_stored": False,
            "request_headers_stored": False,
            "evidence": evidence,
            "evidence_sha256": sha256_canonical_json(evidence),
        }
        validate_provider_receipt(receipt)
        self.last_receipt = receipt
        return OfficialProviderCompletion(
            text=text,
            model_latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason=finish_reason,
            usage_available=True,
            usage_source="deepseek_official_chat_usage",
            prompt_eval_count=prompt_tokens,
            eval_count=completion_tokens,
            provider_attempts=1,
            provider_done=True,
            receipt=receipt,
        )


def build_nonthinking_request_commitment(
    client: OfficialProviderClient,
    messages: Sequence[Mapping[str, str]],
    *,
    execution_identity: str,
    work_key: str,
    call_index: int,
    attempt_id: str,
    precommitted_at: str,
) -> dict[str, Any]:
    """Commit the exact non-thinking payload before network transport."""

    if not execution_identity or not work_key or not attempt_id:
        raise ProviderPayloadError(
            "execution, work and attempt identities are required"
        )
    if (
        isinstance(call_index, bool)
        or not isinstance(call_index, int)
        or call_index < 1
    ):
        raise ProviderPayloadError("call index must be positive")
    normalized = validate_messages(
        messages,
        content_class=client.content_class,
        policy=client.policy,
        allow_pinned_synthetic_credential_labels=(
            client.allow_pinned_synthetic_credential_labels
        ),
        active_api_key=client.api_key,
    )
    payload = {
        "model": client.model,
        "messages": normalized,
        "temperature": float(client.temperature),
        "max_tokens": int(client.max_tokens),
        "stream": False,
        "thinking": dict(THINKING_CONTROL),
    }
    identity = {
        "execution_identity": execution_identity,
        "work_key": work_key,
        "call_index": call_index,
        "attempt_id": attempt_id,
        "provider_id": client.provider_id,
        "model_id": client.model,
        "payload_sha256": sha256_canonical_json(payload),
    }
    commitment = {
        "schema_version": "m3-paper-v2-provider-request-commitment-2.0",
        **identity,
        "client_request_id": (
            "m3req-" + sha256_canonical_json(identity)[:32]
        ),
        "precommitted_at": precommitted_at,
        "content_class": client.content_class,
        "provider_tools_declared": False,
        "external_effects_enabled": False,
        "prompt_or_response_content_stored": False,
    }
    validate_request_commitment(commitment)
    return commitment


class DeepSeekNonThinkingTracedProviderClient(TracedProviderClient):
    """Trace wrapper whose commitment includes the non-thinking toggle."""

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        case: dict[str, Any] | None = None,
        step: int = 1,
        observations: list[Any] | None = None,
    ) -> OfficialProviderCompletion:
        attempt_id = self._attempt_id(step)
        commitment = build_nonthinking_request_commitment(
            self._client,
            messages,
            execution_identity=self.execution_identity,
            work_key=self.work_key,
            call_index=step,
            attempt_id=attempt_id,
            precommitted_at=self.recorded_at(),
        )
        started = append_started_trace(self.trace_path, commitment)
        phase = "provider_transport"
        try:
            completion = self._client.complete(
                messages,
                case=case,
                step=step,
                observations=observations,
            )
            phase = "evidence_completion"
            receipt = (
                dict(self.receipt_adapter(completion.receipt))
                if self.receipt_adapter is not None
                else dict(completion.receipt)
            )
            candidate = bind_trace_attestation(
                commitment,
                receipt,
                started_event_sha256=started["event_sha256"],
            )
            activated = activate_trace_attestation(
                candidate,
                activation_path=self.activation_path,
            )
            usage = build_deepseek_usage_evidence(
                receipt,
                commitment,
                prior_items=list(self._usage_evidence.values()),
                policy=self.policy,
            )
            terminal = append_completed_trace(
                self.trace_path,
                client_request_id=commitment["client_request_id"],
                receipt=receipt,
            )
            if terminal["event"]["attestation"] != candidate:
                raise ProviderTraceBundleError(
                    "terminal trace drifted after activation prevalidation"
                )
            self._activated[commitment["client_request_id"]] = activated
            self._usage_evidence[commitment["client_request_id"]] = usage
            return completion
        except Exception as exc:
            status = (
                "paused"
                if isinstance(exc, ProviderPausedError)
                else (
                    "evidence_failure"
                    if phase == "evidence_completion"
                    else "provider_failure"
                )
            )
            self._failures[commitment["client_request_id"]] = {
                "client_request_id": commitment["client_request_id"],
                "status": status,
                "error_type": type(exc).__name__,
            }
            if (
                started["event"]["client_request_id"]
                != commitment["client_request_id"]
            ):
                raise ProviderTraceBundleError(
                    "persisted start does not bind the attempted call"
                ) from exc
            raise


def _load_policy() -> dict[str, Any]:
    value = json.loads(DEFAULT_BUDGET_POLICY.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProviderPayloadError("budget policy must be an object")
    return value


def build_qualification() -> dict[str, Any]:
    """Prove payload commitment and redacted evidence with no network."""

    observed_payloads: list[dict[str, Any]] = []

    def transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> HTTPResponseEnvelope:
        del endpoint, headers, timeout
        observed_payloads.append(dict(payload))
        return HTTPResponseEnvelope(
            status_code=200,
            headers={"x-request-id": "nonthinking-qualification-request"},
            body={
                "id": "nonthinking-qualification-response",
                "model": payload["model"],
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{"tool":"final","arguments":'
                                '{"answer":"QUALIFIED"}}'
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 80,
                    "prompt_cache_hit_tokens": 72,
                    "prompt_cache_miss_tokens": 8,
                    "completion_tokens": 12,
                    "total_tokens": 92,
                },
            },
        )

    policy = _load_policy()
    client = DeepSeekNonThinkingOfficialClient(
        provider_id="deepseek",
        api_key="offline-nonthinking-qualification-key",
        content_class="synthetic_m3_case",
        budget_state=ProviderBudgetState(
            provider_id="deepseek",
            policy=policy,
        ),
        policy=policy,
        max_tokens=512,
        transport=transport,
    )
    completion = client.complete(
        [{"role": "user", "content": "Return the fixed safe marker."}]
    )
    if (
        len(observed_payloads) != 1
        or observed_payloads[0].get("thinking") != THINKING_CONTROL
        or "tools" in observed_payloads[0]
        or completion.text
        != '{"tool":"final","arguments":{"answer":"QUALIFIED"}}'
    ):
        raise ProviderPayloadError(
            "non-thinking client qualification payload drift"
        )
    attestation = provider_receipt_to_attestation(completion.receipt)
    if (
        completion.receipt["evidence"].get("thinking_mode")
        != "disabled"
        or attestation["evidence_level"] != "local_qualification"
    ):
        raise ProviderPayloadError(
            "non-thinking client qualification evidence drift"
        )
    return {
        "schema_version": (
            "m3-paper-v2-deepseek-nonthinking-client-qualification-1.0"
        ),
        "generated_at": QUALIFICATION_RECORDED_AT,
        "status": "deepseek_nonthinking_client_qualified_offline",
        "thinking_payload": dict(THINKING_CONTROL),
        "payload_sha256": client.last_request_metadata["payload_sha256"],
        "thinking_mode_persisted": "disabled",
        "provider_attempts": 1,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "credentials_read": 0,
        "network_calls_made": 0,
        "formal_results_created": 0,
    }


def write_qualification(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_qualification()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return value


def verify_qualification(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = json.loads(path.read_text(encoding="utf-8"))
    expected = build_qualification()
    if observed != expected:
        raise ProviderPayloadError(
            "non-thinking client qualification does not reproduce"
        )
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    value = (
        verify_qualification(args.output)
        if args.verify_only
        else write_qualification(args.output)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
