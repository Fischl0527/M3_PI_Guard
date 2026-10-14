"""带紧凑请求级收据证明的单次尝试官方模型客户端。

封装标准 API 调用并捕获不可篡改的请求/响应收据哈希。
"""

from __future__ import annotations

# 当前开发客户端：每次请求只有一次 HTTP 尝试；恢复由运行器显式调度。
# 日志保存请求身份、返回模型、用量和状态，不保存密钥、提示正文或响应正文。

import copy
import json
import os
import threading
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib import error as urllib_error
from urllib import request as urllib_request

from experiments.paper_v2 import deepseek_json_client_v2 as ds
from experiments.paper_v2 import gemini_json_client_v1 as gm
from experiments.paper_v2 import official_provider_executor as official
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.lean_empirical_runner import _gemini_policy
from experiments.paper_v2.public_provider_budget_v1 import (
    PublicProviderBudgetState,
    build_role_policy,
    load_public_policy,
)

PRICING_URL = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
PRICING_CHECKED = "2026-09-20"
# 固定核价日期对应的官方峰时价格，仅用于本研究估算；不是今天的实时报价。
PEAK_TARIFF = {
    "deepseek-v4-pro": (0.30, 9.0, 27.0),
    "deepseek-flash": (0.04, 2.0, 8.0),
}
APPROVED_MODEL_GROUPS = {
    "deepseek_pro": "deepseek-v4-pro",
    "deepseek_flash": "deepseek-flash",
    "gemini_flash": "gemini-3.6-flash",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_row(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def deepseek_policy(model: str) -> dict[str, Any]:
    if model not in PEAK_TARIFF:
        raise ValueError("unapproved model; no alias fallback")
    policy = build_role_policy(
        load_public_policy(), "primary" if model.endswith("pro") else "second"
    )
    part = policy["deepseek"]
    part["model_id"] = model
    hit, miss, output = PEAK_TARIFF[model]
    part["pricing"] = {
        "currency": "CNY",
        "source_url": PRICING_URL,
        "verified_at": PRICING_CHECKED,
        "cache_hit_input_per_million_tokens": hit,
        "cache_miss_input_per_million_tokens": miss,
        "output_per_million_tokens": output,
    }
    # Eight requests at the service's maximum context: a derived bound, not
    # the unrelated historical CNY 3/8 scientific-budget stopping rule.
    ceiling = 8 * (miss + 512 * output / 1_000_000) + 1
    part.update(
        hard_spend_limit_cny=ceiling, abort_ceiling_cny=ceiling, abort_at_fraction=1.0
    )
    part["dynamic_fuse"].update(
        next_request_input_tokens_upper_bound=1_000_000,
        next_request_output_tokens_upper_bound=512,
    )
    return policy


class DevelopmentBudgetState(PublicProviderBudgetState):
    """使用现有算术逻辑，但绑定新批准的服务名称。"""

    def __post_init__(self) -> None:
        if (
            self.provider_id != "deepseek"
            or self.policy["deepseek"]["model_id"] not in PEAK_TARIFF
        ):
            raise official.ProviderPayloadError("development model identity drift")
        self.policy = copy.deepcopy(dict(self.policy))
        self._usage = {
            key: 0
            for key in (
                "prompt_tokens",
                "prompt_cache_hit_tokens",
                "prompt_cache_miss_tokens",
                "completion_tokens",
            )
        }


class DevelopmentDeepSeekClient(ds.DeepSeekJsonOfficialClient):
    def __post_init__(self) -> None:
        active = copy.deepcopy(dict(self.policy or {}))
        if (
            self.provider_id != "deepseek"
            or active.get("deepseek", {}).get("model_id") not in PEAK_TARIFF
            or active["deepseek"].get("base_url") != "https://api.deepseek.com"
            or dict(self.budget_state.policy) != active
        ):
            raise official.ProviderPayloadError("development official binding drift")
        if (
            not isinstance(self.api_key, str)
            or not self.api_key.strip()
            or any(c in self.api_key for c in "\r\n")
        ):
            raise official.ProviderPayloadError("invalid credential configuration")
        profile = getattr(self, "study_generation_profile", None)
        expected_tokens = 4096 if profile == "task_contract_compiler_v1" else 512
        if self.temperature != 0 or self.max_tokens != expected_tokens or self.timeout != 180:
            raise official.ProviderPayloadError("development request settings drift")
        if self.transport is None and not self.network_consent:
            raise official.ProviderConsentError("network consent required")
        self.policy = active
        official._provider_endpoint(active, self.provider_id)
        official.validate_messages(
            [{"role": "user", "content": "qualification placeholder"}],
            content_class=self.content_class,
            policy=active,
        )


class TaskContractCompilerClient(DevelopmentDeepSeekClient):
    """仅显式复杂任务编译请求使用4096输出上限。"""

    study_generation_profile = "task_contract_compiler_v1"


class DispatchStopped(official.ProviderTransportError):
    """在配额失败或 DeepSeek 批处理关闭后不再发出新请求。"""


class RequestPacer:
    # 请求节流器：并发线程共用同一提供商节拍；停止信号能打断等待。
    def __init__(self, interval_seconds: float, stopped: threading.Event) -> None:
        self.interval = interval_seconds
        self.stopped = stopped
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            remaining = max(0.0, self._last + self.interval - time.monotonic())
            if self.stopped.wait(remaining):
                raise DispatchStopped("provider dispatch stopped")
            self._last = time.monotonic()


class DevelopmentRequestClient:
    # 只在实际客户端内使用凭据；公开回执不含认证头或内容正文。
    """无内容的请求日志，包括格式错误的响应标识。

    仅原始官方客户端接收凭据。HTTP 观察者数据绝不包含标头、正文、模型文本或提示词。
    """

    def __init__(
        self,
        *,
        model_group: str,
        model: str,
        api_key: str,
        benchmark: str,
        work_key: str,
        attempt: int,
        trace_path: Path,
        pacer: RequestPacer,
        transport: Any = None,
        generation_profile: str | None = None,
        max_provider_calls: int = 8,
        call_budget_ceiling: int = 8,
        call_budget_scope: str | None = None,
    ) -> None:
        if APPROVED_MODEL_GROUPS.get(model_group) != model:
            raise official.ProviderIdentityError(
                "development model group/identity mismatch"
            )
        if not work_key or type(attempt) is not int or attempt < 1:
            raise official.ProviderPayloadError(
                "work key and positive attempt are required"
            )
        profiles = {None, "gemini_recovery_v1", "task_contract_study_v1", "task_contract_compiler_v1"}
        if generation_profile not in profiles or (
            generation_profile == "gemini_recovery_v1" and model_group != "gemini_flash"
        ) or (generation_profile == "task_contract_compiler_v1" and model_group != "deepseek_pro"):
            raise official.ProviderPayloadError("unapproved generation profile")
        self.generation_profile = generation_profile
        if call_budget_scope not in {None, "empirical_reinforcement_v1", "task_contract_v3_validation_v1", "task_contract_v4_development_v1"}:
            raise official.ProviderPayloadError("unapproved explicit study scope")
        if call_budget_scope == "task_contract_v4_development_v1" and model_group not in {"deepseek_pro", "deepseek_flash"}:
            raise official.ProviderPayloadError("v4 development is DeepSeek-only; Gemini remains skipped")
        extended_flash = model_group == "deepseek_flash" and call_budget_scope == "empirical_reinforcement_v1"
        new_study = call_budget_scope in {"task_contract_v3_validation_v1", "task_contract_v4_development_v1"}
        allowed_ceiling = call_budget_ceiling == 12 if new_study else call_budget_ceiling in {8, 16}
        if type(call_budget_ceiling) is not int or not allowed_ceiling or call_budget_ceiling == 16 and model_group != "deepseek_pro" and not extended_flash:
            raise official.ProviderPayloadError("unapproved explicit study call ceiling")
        if generation_profile in {"task_contract_study_v1", "task_contract_compiler_v1"} and not new_study:
            raise official.ProviderPayloadError("new generation settings require explicit study scope")
        if type(max_provider_calls) is not int or not 1 <= max_provider_calls <= call_budget_ceiling:
            raise official.ProviderPayloadError("per-task request cap exceeds explicit study ceiling (default 1..8)")
        self.max_provider_calls = max_provider_calls
        self.requests: list[dict[str, Any]] = []
        self._trace_path = trace_path
        self._work_key = work_key
        self._attempt = attempt
        self._pacer = pacer
        self._upstream = transport if transport is not None else self._network_transport
        self._injected = transport is not None
        self._active_request: dict[str, Any] | None = None
        self.physical_attempt_namespace = attempt
        self.provider_id = "gemini" if model_group == "gemini_flash" else "deepseek"
        self.transport = transport  # None accurately identifies real official traffic.
        common = dict(
            provider_id=self.provider_id,
            api_key=api_key,
            content_class="public_benchmark_case"
            if benchmark == "agentdojo-v1"
            else "synthetic_m3_case",
            temperature=0.0,
            max_tokens=4096 if generation_profile == "task_contract_compiler_v1" else 2048 if model_group == "gemini_flash" and generation_profile in {"gemini_recovery_v1", "task_contract_study_v1"} else 512,
            timeout=180.0,
            network_consent=True,
            allow_pinned_synthetic_credential_labels=benchmark == "agentdojo-v1",
            transport=self._observe_transport,
        )
        if self.provider_id == "deepseek":
            policy = deepseek_policy(model)
            if new_study:
                part = policy["deepseek"]
                # 新研究只使用显式调用上限推导最坏请求预算，不继承旧几元熔断。
                part["hard_spend_limit_cny"] = 12 * (PEAK_TARIFF[model][1] + common["max_tokens"] * PEAK_TARIFF[model][2] / 1_000_000) + 1
                part["abort_ceiling_cny"] = part["hard_spend_limit_cny"]
                part["dynamic_fuse"]["next_request_output_tokens_upper_bound"] = common["max_tokens"]
            if call_budget_ceiling == 16:
                # Explicit VIGIL study only; historical default policy stays eight.
                part = policy["deepseek"]
                part["hard_spend_limit_cny"] *= 2
                part["abort_ceiling_cny"] *= 2
            client_class = TaskContractCompilerClient if generation_profile == "task_contract_compiler_v1" else DevelopmentDeepSeekClient
            self._client = client_class(
                **common,
                policy=policy,
                budget_state=DevelopmentBudgetState("deepseek", policy),
            )
        else:
            if model != "gemini-3.6-flash":
                raise official.ProviderPayloadError("Gemini replacement forbidden")
            policy = copy.deepcopy(_gemini_policy())
            spec = policy["gemini"]
            if (
                spec.get("billing_tier") != "free"
                or spec.get("allow_paid_tier") is not False
                or spec.get("monetary_hard_limit_usd") != 0
                or spec.get("model_id") != model
            ):
                raise official.ProviderPayloadError(
                    "Gemini requires the fixed free-only policy"
                )
            if generation_profile in {"gemini_recovery_v1", "task_contract_study_v1"}:
                # Historical clients share this bound even for Gemini. Change
                # only this run-local copy; no DeepSeek or frozen policy edits.
                policy["deepseek"]["dynamic_fuse"][
                    "next_request_output_tokens_upper_bound"
                ] = 2048
            self._client = gm.GeminiJsonOfficialClient(
                **common,
                policy=policy,
                budget_state=official.ProviderBudgetState("gemini", policy),
                reasoning_effort="low" if generation_profile in {"gemini_recovery_v1", "task_contract_study_v1"} else None,
            )

    def __getattr__(self, key: str) -> Any:
        return getattr(self._client, key)

    def _network_transport(
        self, endpoint: str, headers: Any, payload: Any, timeout: float
    ) -> Any:
        """在 JSON 解码前观察 HTTP 收据；严格执行单次 HTTP 尝试。

        历史传输层在返回畸形/429 正文前会抛出异常。仅记录返回的包络会将其误判为无响应。复用其序列化和安全标头过滤，但在解码失败时仍保留收据状态。不记录响应文本或错误正文。
        """
        request = urllib_request.Request(
            endpoint,
            data=official._canonical_bytes(dict(payload)),
            headers=dict(headers),
            method="POST",
        )
        try:
            response = urllib_request.urlopen(request, timeout=timeout)
        except urllib_error.HTTPError as exc:
            response = exc
        except urllib_error.URLError as exc:
            raise official.ProviderTransportError(
                f"official provider transport error: {type(exc.reason).__name__}"
            ) from exc
        with response:
            status = int(getattr(response, "status", getattr(response, "code", 200)))
            safe_headers = official._safe_headers(dict(response.headers.items()))
            self._record_http_receipt(status, safe_headers)
            raw = response.read()
        if status < 200 or status >= 300:
            # Preserve the HTTP outcome without parsing or persisting error text.
            return official.HTTPResponseEnvelope(status, safe_headers, {})
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise official.ProviderTransportError(
                "official response was not valid UTF-8 JSON"
            ) from exc
        if not isinstance(value, Mapping):
            raise official.ProviderTransportError(
                "official response must be a JSON object"
            )
        return official.HTTPResponseEnvelope(status, safe_headers, dict(value))

    def _record_http_receipt(self, status: int, headers: Mapping[str, Any]) -> None:
        request = self._active_request
        if request is None:
            raise official.ProviderPayloadError("response has no active request")
        request["http_status"] = status
        request["http_response_received"] = True
        request["response_received"] = 200 <= status < 300
        if status == 429:
            self._pacer.stopped.set()
        request["provider_request_id"] = self._safe_identifier(
            official._request_id(official._safe_headers(headers))
        )

    def _safe_identifier(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        if self._client.api_key in value:
            raise official.ProviderPayloadError(
                "provider metadata echoed active credential"
            )
        if len(value) > 512:
            raise official.ProviderPayloadError(
                "provider identifier exceeds metadata length limit"
            )
        return value

    def _observe_transport(
        self, endpoint: str, headers: Any, payload: Any, timeout: float
    ) -> Any:
        request = self._active_request
        if request is None or request["payload_sha256"] != sha256_canonical_json(
            payload
        ):
            raise official.ProviderPayloadError(
                "payload changed after local request commitment"
            )
        if "tools" in payload or "tool_choice" in payload:
            raise official.ProviderPayloadError("provider tools forbidden")
        request["transport_started"] = True
        try:
            envelope = self._upstream(endpoint, headers, payload, timeout)
        except official.ProviderPausedError as exc:
            if exc.http_status == 429:
                self._record_http_receipt(429, {})
            raise
        self._record_http_receipt(envelope.status_code, envelope.headers)
        body = envelope.body if isinstance(envelope.body, Mapping) else {}
        request["provider_response_id"] = self._safe_identifier(body.get("id"))
        request["returned_model"] = self._safe_identifier(body.get("model"))
        if isinstance(body.get("usage"), Mapping):
            request["usage"] = {
                key: value
                for key, value in body["usage"].items()
                if key
                in {
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "prompt_cache_hit_tokens",
                    "prompt_cache_miss_tokens",
                }
                and isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
            }
        if not isinstance(envelope.body, Mapping):
            raise official.ProviderTransportError(
                "official response must be a JSON object"
            )
        return envelope

    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> Any:
        if len(self.requests) >= self.max_provider_calls:
            raise official.ProviderPayloadError(
                "development per-task request cap reached"
            )
        self._pacer.wait()
        payload = (ds._payload if self.provider_id == "deepseek" else gm._payload)(
            self._client, messages
        )
        row = {
            "local_request_id": f"m3req-{uuid.uuid4().hex}",
            "work_key": self._work_key,
            "attempt": self._attempt,
            "call_index": len(self.requests) + 1,
            "max_provider_calls": self.max_provider_calls,
            "provider_id": self.provider_id,
            "configured_model": self.model,
            "generation_profile": self.generation_profile,
            "max_tokens": payload["max_tokens"],
            "reasoning_effort": payload.get("reasoning_effort"),
            "payload_sha256": sha256_canonical_json(payload),
            "requested_at": now(),
            "provider_response_id": None,
            "returned_model": None,
            "response_received": False,
            "http_response_received": False,
            "transport_started": False,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
        }
        append_row(self._trace_path, {"event": "started", **row})
        self.requests.append(row)
        self._active_request = row
        try:
            completion = self._client.complete(messages, **kwargs)
            receipt = copy.deepcopy(completion.receipt)
            # Local HTTP observation is not a model proxy or a test double.
            # Only an explicitly injected transport is qualification traffic.
            receipt["evidence"]["transport_kind"] = (
                "injected_test_double" if self._injected else "official_network"
            )
            if self.generation_profile is not None:
                receipt["evidence"]["generation_profile"] = self.generation_profile
            receipt["evidence_sha256"] = sha256_canonical_json(receipt["evidence"])
            official.validate_provider_receipt(receipt)
            if (
                not row["provider_response_id"]
                or not row["provider_response_id"].strip()
            ):
                raise official.ProviderIdentityError("official response ID missing")
            self._client.last_receipt = receipt
            self._client.last_request_metadata["transport_kind"] = receipt["evidence"][
                "transport_kind"
            ]
            if self.generation_profile is not None:
                self._client.last_request_metadata["generation_profile"] = self.generation_profile
            row["status"] = "completed"
            row["finish_reason"] = completion.finish_reason
            return replace(completion, receipt=receipt)
        except Exception as exc:
            row["status"] = "failed"
            row["error_type"] = type(exc).__name__
            raise
        finally:
            row["completed_at"] = now()
            append_row(self._trace_path, {"event": "terminal", **row})
            self._active_request = None


def request_cost(requests: list[dict[str, Any]], model: str) -> dict[str, Any]:
    if model not in APPROVED_MODEL_GROUPS.values():
        raise ValueError("cost estimate requires the exact approved model identity")
    if model == "gemini-3.6-flash":
        return {
            "currency": "USD",
            "amount": 0.0,
            "basis": "user_attested_free_project_not_billing_api_verified",
            "paid_fallback": False,
        }
    hit, miss, output = PEAK_TARIFF[model]
    upper = 0.0
    complete = True
    unpriced_response_count = 0
    for request in requests:
        usage = request.get("usage", {})
        fields = (
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
            "completion_tokens",
        )
        if request.get("response_received") and not all(key in usage for key in fields):
            complete = False
            unpriced_response_count += 1
        upper += (
            usage.get(fields[0], 0) * hit
            + usage.get(fields[1], 0) * miss
            + usage.get(fields[2], 0) * output
        ) / 1_000_000
    return {
        "currency": "CNY",
        "amount": round(upper, 12),
        "off_peak_lower_estimate": round(upper / 2, 12) if complete else None,
        "basis": "official_peak_tariff_upper_estimate_not_invoice"
        if complete
        else "known_usage_subtotal_not_total_cost_upper_bound",
        "usage_complete": complete,
        "unpriced_response_count": unpriced_response_count,
        "pricing_checked_at": PRICING_CHECKED,
        "pricing_source": PRICING_URL,
    }
