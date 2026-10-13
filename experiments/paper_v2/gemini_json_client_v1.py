"""具备传输前精确承诺的 Gemini OpenAI 兼容 JSON 客户端。

将请求转换为规范的 OpenAI 兼容格式并约束输出为结构化 JSON 载荷。
"""

from __future__ import annotations

import copy
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

import experiments.paper_v2.gemini_fallback_controller_v2 as fallback
import experiments.paper_v2.gemini_public_trace_v1 as gemini_trace
import experiments.paper_v2.official_provider_executor as official
import experiments.paper_v2.provider_request_trace_candidate as trace
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.vigil_live_dependency import (
    VigilOfficialConstraintFactory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUALIFICATION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/gemini_json_client_qualification_v1.json"
)
SHARED_USAGE_QUALIFICATION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/"
    "gemini_json_shared_usage_qualification_v2.json"
)
QUALIFIED_AT = "2026-08-02T00:30:00+08:00"
JSON_OUTPUT_CONTROL = {"type": "json_object"}


class GeminiJsonClientV1Error(ValueError):
    """当 Gemini JSON 传输或论据绑定发生漂移时抛出的异常。"""


class GeminiUsageRegistry:
    """每个工作项追踪客户端共享的运行本地有序用量状态。"""

    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []
        self._client_request_ids: set[str] = set()

    def prior_items(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._items)

    def append(self, value: Mapping[str, Any]) -> None:
        item = copy.deepcopy(dict(value))
        client_request_id = str(item.get("client_request_id", ""))
        if not client_request_id or client_request_id in self._client_request_ids:
            raise GeminiJsonClientV1Error(
                "Gemini shared usage registry received a duplicate request"
            )
        cumulative = item.get("cumulative_usage")
        if (
            not isinstance(cumulative, Mapping)
            or int(cumulative.get("requests", -1)) != len(self._items) + 1
        ):
            raise GeminiJsonClientV1Error(
                "Gemini shared usage registry is not contiguous"
            )
        self._items.append(item)
        self._client_request_ids.add(client_request_id)


def _payload(
    client: official.OfficialProviderClient,
    messages: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    normalized = official.validate_messages(
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
        "response_format": copy.deepcopy(JSON_OUTPUT_CONTROL),
    }
    effort = getattr(client, "reasoning_effort", None)
    if effort is not None:
        if effort != "low":
            raise official.ProviderPayloadError("unsupported Gemini reasoning effort")
        payload["reasoning_effort"] = effort
    return payload


@dataclass
class GeminiJsonOfficialClient(official.OfficialProviderClient):
    """响应限制为 JSON 的单次尝试官方 Gemini 客户端。"""

    reasoning_effort: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.provider_id != "gemini":
            raise official.ProviderPayloadError(
                "Gemini JSON client cannot be used with another provider"
            )
        if self.reasoning_effort not in (None, "low"):
            raise official.ProviderPayloadError("unsupported Gemini reasoning effort")

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        case: dict[str, Any] | None = None,
        step: int = 1,
        observations: list[Any] | None = None,
    ) -> official.OfficialProviderCompletion:
        del case, observations
        if isinstance(step, bool) or not isinstance(step, int) or step < 1:
            raise official.ProviderPayloadError("step must be a positive integer")
        self.budget_state.assert_before_request()
        payload = _payload(self, messages)
        if "tools" in payload or "tool_choice" in payload:
            raise official.ProviderPayloadError(
                "provider-managed tools are forbidden"
            )
        payload_sha256 = official._sha256_bytes(
            official._canonical_bytes(payload)
        )
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
            "response_format": "json_object",
            "provider_attempts": 1,
            "provider_tools_declared": False,
            "pinned_synthetic_credential_labels_allowed": bool(
                self.allow_pinned_synthetic_credential_labels
                and self.content_class == "public_benchmark_case"
            ),
        }
        if self.reasoning_effort is not None:
            request_metadata["reasoning_effort"] = self.reasoning_effort
        official._validate_persisted_value(request_metadata)
        self.last_request_metadata = request_metadata
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started_ns = perf_counter_ns()
        requested_at = official._now()
        envelope = (self.transport or official._default_transport)(
            self.endpoint,
            headers,
            payload,
            float(self.timeout),
        )
        latency_ms = official._elapsed_ms(started_ns)
        if envelope.status_code == 429:
            raise official.ProviderPausedError(
                "official provider returned HTTP 429"
            )
        if envelope.status_code < 200 or envelope.status_code >= 300:
            raise official.ProviderTransportError(
                f"official provider returned HTTP {envelope.status_code}"
            )
        body = envelope.body
        returned_model = str(body.get("model", ""))
        if returned_model != self.model:
            raise official.ProviderIdentityError(
                "returned model does not match the frozen model identity"
            )
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise official.ProviderTransportError(
                "official provider response has no choices"
            )
        choice = choices[0]
        if not isinstance(choice, Mapping):
            raise official.ProviderTransportError(
                "official provider choice is malformed"
            )
        message = choice.get("message")
        if not isinstance(message, Mapping):
            raise official.ProviderTransportError(
                "official provider message is malformed"
            )
        text = str(message.get("content", "") or "")
        finish_reason = str(choice.get("finish_reason", "") or "")
        usage_raw = body.get("usage")
        if not isinstance(usage_raw, Mapping):
            raise official.ProviderUsageError(
                "official provider usage is required"
            )
        prompt_tokens = official._optional_int(usage_raw.get("prompt_tokens"))
        completion_tokens = official._optional_int(
            usage_raw.get("completion_tokens")
        )
        total_tokens = official._optional_int(usage_raw.get("total_tokens"))
        if prompt_tokens is None or completion_tokens is None:
            raise official.ProviderUsageError(
                "prompt and completion token usage is required"
            )
        if prompt_tokens < 0 or completion_tokens < 0:
            raise official.ProviderUsageError(
                "provider token usage must be non-negative"
            )
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens
        if total_tokens < prompt_tokens + completion_tokens:
            raise official.ProviderUsageError(
                "provider total token usage is inconsistent"
            )
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        budget = self.budget_state.record_usage(usage)
        request_id = official._request_id(
            official._safe_headers(envelope.headers)
        )
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
            "response_text_sha256": official._sha256_bytes(
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
            "schema_version": "m3-paper-v2-official-provider-receipt-1.0",
            "credentials_stored": False,
            "prompt_or_response_content_stored": False,
            "request_headers_stored": False,
            "evidence": evidence,
            "evidence_sha256": sha256_canonical_json(evidence),
        }
        official.validate_provider_receipt(receipt)
        self.last_receipt = receipt
        return official.OfficialProviderCompletion(
            text=text,
            model_latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason=finish_reason,
            usage_available=True,
            usage_source="gemini_official_chat_usage",
            prompt_eval_count=prompt_tokens,
            eval_count=completion_tokens,
            provider_attempts=1,
            provider_done=True,
            receipt=receipt,
        )


def build_json_request_commitment(
    client: GeminiJsonOfficialClient,
    messages: Sequence[Mapping[str, str]],
    *,
    execution_identity: str,
    work_key: str,
    call_index: int,
    attempt_id: str,
    precommitted_at: str,
) -> dict[str, Any]:
    """在提供商传输前绑定确切的 Gemini JSON 载荷。"""

    if not execution_identity or not work_key or not attempt_id:
        raise GeminiJsonClientV1Error(
            "execution, work and attempt identities are required"
        )
    if isinstance(call_index, bool) or not isinstance(call_index, int) or call_index < 1:
        raise GeminiJsonClientV1Error("call index must be positive")
    identity = {
        "execution_identity": execution_identity,
        "work_key": work_key,
        "call_index": call_index,
        "attempt_id": attempt_id,
        "provider_id": client.provider_id,
        "model_id": client.model,
        "payload_sha256": sha256_canonical_json(_payload(client, messages)),
    }
    commitment = {
        "schema_version": "m3-paper-v2-provider-request-commitment-2.0",
        **identity,
        "client_request_id": "m3req-" + sha256_canonical_json(identity)[:32],
        "precommitted_at": precommitted_at,
        "content_class": client.content_class,
        "provider_tools_declared": False,
        "external_effects_enabled": False,
        "prompt_or_response_content_stored": False,
    }
    trace.validate_request_commitment(commitment)
    return commitment


class GeminiJsonTracedProviderClient(
    gemini_trace.GeminiPublicTracedProviderClient
):
    """承诺包含 JSON 输出控制的 Gemini 追踪包装器。"""

    def __init__(
        self,
        *args: Any,
        usage_registry: GeminiUsageRegistry | None = None,
        physical_attempt_namespace: int = 1,
        **kwargs: Any,
    ) -> None:
        if (
            isinstance(physical_attempt_namespace, bool)
            or not isinstance(physical_attempt_namespace, int)
            or physical_attempt_namespace < 1
        ):
            raise GeminiJsonClientV1Error(
                "physical attempt namespace must be a positive integer"
            )
        super().__init__(*args, **kwargs)
        self.usage_registry = usage_registry or GeminiUsageRegistry()
        self.physical_attempt_namespace = physical_attempt_namespace

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        case: dict[str, Any] | None = None,
        step: int = 1,
        observations: list[Any] | None = None,
    ) -> official.OfficialProviderCompletion:
        attempt_identity: dict[str, Any] = {
            "execution_identity": self.execution_identity,
            "work_key": self.work_key,
            "call_index": step,
        }
        # Namespace 1 intentionally preserves the historical identity bytes.
        # A prospective outer recovery attempt adds one domain-separation field
        # without changing the logical work key or the canonical API payload.
        if self.physical_attempt_namespace != 1:
            attempt_identity["physical_attempt_namespace"] = (
                self.physical_attempt_namespace
            )
        attempt_id = "attempt-" + sha256_canonical_json(attempt_identity)[:24]
        commitment = build_json_request_commitment(
            self._client,
            messages,
            execution_identity=self.execution_identity,
            work_key=self.work_key,
            call_index=step,
            attempt_id=attempt_id,
            precommitted_at=self.recorded_at(),
        )
        started = trace.append_started_trace(self.trace_path, commitment)
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
            candidate = trace.bind_trace_attestation(
                commitment,
                receipt,
                started_event_sha256=started["event_sha256"],
            )
            activated = gemini_trace.activate_attestation(
                candidate,
                admission_manifest_sha256=self.admission_manifest_sha256,
            )
            usage = gemini_trace.build_usage_evidence(
                receipt,
                commitment,
                prior_items=self.usage_registry.prior_items(),
            )
            terminal = trace.append_completed_trace(
                self.trace_path,
                client_request_id=commitment["client_request_id"],
                receipt=receipt,
            )
            if terminal["event"]["attestation"] != candidate:
                raise GeminiJsonClientV1Error("Gemini terminal trace drift")
            self._activated[commitment["client_request_id"]] = activated
            self._usage[commitment["client_request_id"]] = usage
            self.usage_registry.append(usage)
            return completion
        except Exception as exc:
            self._failures[commitment["client_request_id"]] = {
                "client_request_id": commitment["client_request_id"],
                "status": (
                    "paused"
                    if isinstance(exc, official.ProviderPausedError)
                    else (
                        "evidence_failure"
                        if phase == "evidence_completion"
                        else "provider_failure"
                    )
                ),
                "error_type": type(exc).__name__,
            }
            raise


def _fixture_response(model: str, content: str) -> official.HTTPResponseEnvelope:
    return official.HTTPResponseEnvelope(
        status_code=200,
        headers={"x-goog-request-id": "gemini-json-qualification-request"},
        body={
            "id": "gemini-json-qualification-response",
            "model": model,
            "choices": [
                {
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 48,
                "total_tokens": 168,
            },
        },
    )


def _client(
    *,
    transport: official.Transport,
) -> GeminiJsonOfficialClient:
    policy = fallback._effective_policy()
    return GeminiJsonOfficialClient(
        provider_id="gemini",
        api_key="offline-gemini-json-qualification-key",
        content_class="public_benchmark_case",
        budget_state=official.ProviderBudgetState(
            provider_id="gemini", policy=policy
        ),
        policy=policy,
        temperature=0.0,
        max_tokens=512,
        timeout=30.0,
        transport=transport,
    )


def build_qualification() -> dict[str, Any]:
    """仅使用注入的传输演练 JSON 载荷和 VIGIL 解析。"""

    observed_payloads: list[dict[str, Any]] = []
    constraint_json = json.dumps(
        {
            "constraints": [
                {
                    "constraint_id": "confirm_send",
                    "constraint_type": "require_confirmation",
                    "description": "Confirm sending the report.",
                    "tool_name": "send_report",
                    "priority": 1,
                },
                {
                    "constraint_id": "forbid_delete",
                    "constraint_type": "forbid",
                    "description": "Forbid deleting records.",
                    "tool_name": "delete_record",
                    "priority": 1,
                },
            ],
            "global_rules": ["Keep read-only inspection available."],
        },
        separators=(",", ":"),
    )

    def transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> official.HTTPResponseEnvelope:
        del endpoint, headers, timeout
        observed_payloads.append(copy.deepcopy(dict(payload)))
        return _fixture_response(str(payload["model"]), constraint_json)

    client = _client(transport=transport)
    preparation = VigilOfficialConstraintFactory()(
        None,
        "Send the report only after confirmation.",
        client,
    )
    decisions = {
        tool: preparation.adapter.decide(
            tool_name=tool,
            arguments={},
            tool_call_id=f"gemini-json-qualification-{tool}",
        ).decision
        for tool in ("read_report", "send_report", "delete_record")
    }
    payload = observed_payloads[0]
    commitment = build_json_request_commitment(
        client,
        [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": "Qualification marker."},
        ],
        execution_identity="e" * 64,
        work_key="w" * 64,
        call_index=1,
        attempt_id="gemini-json-qualification",
        precommitted_at=QUALIFIED_AT,
    )
    if (
        len(observed_payloads) != 1
        or payload.get("response_format") != JSON_OUTPUT_CONTROL
        or "tools" in payload
        or "tool_choice" in payload
        or preparation.provider_calls_consumed != 1
        or decisions
        != {
            "read_report": "ALLOW",
            "send_report": "ASK",
            "delete_record": "DENY",
        }
        or client.last_request_metadata.get("payload_sha256")
        != sha256_canonical_json(payload)
    ):
        raise GeminiJsonClientV1Error("Gemini JSON/VIGIL qualification drift")
    return {
        "schema_version": "m3-paper-v2-gemini-json-client-qualification-1.0",
        "status": "offline_json_payload_and_vigil_qualified",
        "qualified_at": QUALIFIED_AT,
        "provider_id": "gemini",
        "model_id": client.model,
        "response_format": copy.deepcopy(JSON_OUTPUT_CONTROL),
        "observed_payload_sha256": sha256_canonical_json(payload),
        "independent_commitment_payload_sha256": commitment["payload_sha256"],
        "vigil_constraint_count": preparation.constraint_count,
        "vigil_constraint_set_sha256": preparation.constraint_set_sha256,
        "vigil_decisions": decisions,
        "provider_calls": 1,
        "network_calls": 0,
        "credentials_read": False,
        "automatic_retries": 0,
        "provider_tools_declared": False,
        "external_effects_enabled": False,
    }


def write_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    value = build_qualification()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return value


def verify_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    observed = json.loads(path.read_text(encoding="utf-8"))
    expected = build_qualification()
    if observed != expected:
        raise GeminiJsonClientV1Error(
            "Gemini JSON qualification artifact drift"
        )
    return observed


def build_shared_usage_qualification() -> dict[str, Any]:
    """跨两个不同工作项客户端限定累积用量资格。"""

    policy = fallback._effective_policy()
    budget = official.ProviderBudgetState(provider_id="gemini", policy=policy)
    registry = GeminiUsageRegistry()
    call_count = 0

    def transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> official.HTTPResponseEnvelope:
        nonlocal call_count
        del endpoint, headers, timeout
        call_count += 1
        return _fixture_response(
            str(payload["model"]),
            '{"tool":"final","arguments":{"answer":"SAFE"}}',
        )

    def official_adapter(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
        value = copy.deepcopy(dict(receipt))
        value["evidence"]["transport_kind"] = "official_network"
        value["evidence"]["response_id"] = (
            f"gemini-shared-qualification-response-{call_count}"
        )
        value["evidence_sha256"] = sha256_canonical_json(value["evidence"])
        return value

    messages = [
        {"role": "system", "content": "Return JSON only."},
        {"role": "user", "content": "Return a fixed safe marker."},
    ]
    summaries: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="m3-gemini-usage-qualification-") as root:
        for index in (1, 2):
            client = GeminiJsonOfficialClient(
                provider_id="gemini",
                api_key="offline-gemini-shared-usage-key",
                content_class="synthetic_m3_case",
                budget_state=budget,
                policy=policy,
                temperature=0.0,
                max_tokens=64,
                timeout=30.0,
                transport=transport,
            )
            traced = GeminiJsonTracedProviderClient(
                client,
                execution_identity="shared-usage-qualification",
                work_key=f"qualification-work-{index}",
                trace_path=Path(root) / f"work-{index}.jsonl",
                admission_manifest_sha256="a" * 64,
                recorded_at=lambda: QUALIFIED_AT,
                receipt_adapter=official_adapter,
                usage_registry=registry,
            )
            traced.complete(messages, step=1)
            bundle = traced.build_bundle()
            summaries.append(
                {
                    "work_index": index,
                    "bundle_status": bundle["bundle_status"],
                    "result_tier_ceiling": bundle["result_tier_ceiling"],
                    "cumulative_requests": bundle["usage_evidence"][-1][
                        "cumulative_usage"
                    ]["requests"],
                }
            )
    if summaries != [
        {
            "work_index": 1,
            "bundle_status": "completed",
            "result_tier_ceiling": "formal_candidate",
            "cumulative_requests": 1,
        },
        {
            "work_index": 2,
            "bundle_status": "completed",
            "result_tier_ceiling": "formal_candidate",
            "cumulative_requests": 2,
        },
    ]:
        raise GeminiJsonClientV1Error(
            "Gemini shared usage qualification drift"
        )
    return {
        "schema_version": "m3-paper-v2-gemini-shared-usage-qualification-2.0",
        "status": "two_work_item_cumulative_usage_qualified_offline",
        "qualified_at": QUALIFIED_AT,
        "provider_id": "gemini",
        "model_id": policy["gemini"]["model_id"],
        "work_items": 2,
        "provider_calls": call_count,
        "summaries": summaries,
        "network_calls": 0,
        "credentials_read": False,
        "automatic_retries": 0,
        "provider_tools_declared": False,
        "external_effects_enabled": False,
    }


def write_shared_usage_qualification(
    path: Path = SHARED_USAGE_QUALIFICATION,
) -> dict[str, Any]:
    value = build_shared_usage_qualification()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return value


def verify_shared_usage_qualification(
    path: Path = SHARED_USAGE_QUALIFICATION,
) -> dict[str, Any]:
    observed = json.loads(path.read_text(encoding="utf-8"))
    expected = build_shared_usage_qualification()
    if observed != expected:
        raise GeminiJsonClientV1Error(
            "Gemini shared usage qualification artifact drift"
        )
    return observed


if __name__ == "__main__":
    write_qualification()
