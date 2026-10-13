"""凭据脱敏的 DeepSeek/Gemini 官方传输与仅追加调用记录器。

管理向大模型官方 API 的网络传输，强制执行密钥与敏感参数脱敏，
并将每次调用的入参、耗时和状态原子性写入持久化调用账本。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Callable, Mapping, Sequence
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.provider_budget import (
    BudgetPolicyError,
    check_deepseek_headroom,
    check_gemini_free_batch,
    deepseek_cost_cny,
    validate_deepseek_usage,
    validate_policy,
)
from experiments.paper_v2.provider_safety import validate_provider_endpoint


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUDGET_POLICY = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json"
)
ALLOWED_PROVIDERS = frozenset({"deepseek", "gemini"})
PROVIDER_DISPLAY_NAMES = {
    "deepseek": "DeepSeek",
    "gemini": "Google",
}
ALLOWED_MESSAGE_ROLES = frozenset({"system", "user", "assistant"})
REQUEST_ID_HEADERS = (
    "x-request-id",
    "x-goog-request-id",
    "request-id",
)
SAFE_RESPONSE_HEADERS = frozenset(
    {*REQUEST_ID_HEADERS, "content-type", "x-ratelimit-remaining"}
)
HIGH_CONFIDENCE_SECRET_TEXT_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_.-]{12,}\b"),
    re.compile(r"\bAQ\.[A-Za-z0-9_.-]{12,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
SYNTHETIC_CREDENTIAL_LABEL_PATTERN = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|password)\s*[:=]\s*\S{8,}"
)
SECRET_TEXT_PATTERNS = (
    *HIGH_CONFIDENCE_SECRET_TEXT_PATTERNS,
    SYNTHETIC_CREDENTIAL_LABEL_PATTERN,
)
FORBIDDEN_PERSISTED_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "headers",
        "messages",
        "prompt",
        "response_text",
        "raw_response",
    }
)
TERMINAL_EVENT_TYPES = frozenset({"completed", "paused", "failed"})


class OfficialProviderError(RuntimeError):
    """安全提供商执行失败的基础类。"""


class ProviderConsentError(OfficialProviderError):
    """当真实的真实网络传输缺少显式许可时抛出的异常。"""


class ProviderPayloadError(OfficialProviderError):
    """当出站载荷越过固化数据边界时抛出的异常。"""


class ProviderTransportError(OfficialProviderError):
    """针对脱敏凭据的 HTTP 或响应错误抛出的异常。"""


class ProviderPausedError(ProviderTransportError):
    """在配额/速率限制暂停时抛出；绝不自动重试。"""

    def __init__(
        self,
        message: str,
        *,
        http_status: int = 429,
        body_sha256: str | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.body_sha256 = body_sha256
        self.automatic_retry = False


class ProviderIdentityError(OfficialProviderError):
    """当官方响应与固化模型不匹配时抛出的异常。"""


class ProviderUsageError(OfficialProviderError):
    """当必需的提供商用量论据缺失或不一致时抛出的异常。"""


class ProviderLedgerError(ValueError):
    """当仅追加提供商调用账本无效时抛出的异常。"""


@dataclass(frozen=True)
class HTTPResponseEnvelope:
    """仅包含安全标头和解析后 JSON 的传输输出。"""

    status_code: int
    headers: Mapping[str, str]
    body: Mapping[str, Any]


Transport = Callable[
    [str, Mapping[str, str], Mapping[str, Any], float],
    HTTPResponseEnvelope,
]


def _load_policy(path: Path = DEFAULT_BUDGET_POLICY) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProviderPayloadError("budget policy must be a JSON object")
    return validate_policy(value)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(started_ns: int) -> float:
    return round((perf_counter_ns() - started_ns) / 1_000_000, 6)


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(key).casefold(): str(value)
        for key, value in headers.items()
        if str(key).casefold() in SAFE_RESPONSE_HEADERS
    }


def _default_transport(
    endpoint: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> HTTPResponseEnvelope:
    request = urllib_request.Request(
        endpoint,
        data=_canonical_bytes(dict(payload)),
        headers=dict(headers),
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = int(getattr(response, "status", 200))
            safe_headers = _safe_headers(dict(response.headers.items()))
    except urllib_error.HTTPError as exc:
        raw = exc.read()
        digest = _sha256_bytes(raw)
        if exc.code == 429:
            raise ProviderPausedError(
                f"official provider returned HTTP 429; body_sha256={digest}",
                body_sha256=digest,
            ) from exc
        raise ProviderTransportError(
            f"official provider returned HTTP {exc.code}; body_sha256={digest}"
        ) from exc
    except urllib_error.URLError as exc:
        reason_class = type(exc.reason).__name__
        raise ProviderTransportError(
            f"official provider transport error: {reason_class}"
        ) from exc
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderTransportError(
            "official provider response was not valid UTF-8 JSON; "
            f"body_sha256={_sha256_bytes(raw)}"
        ) from exc
    if not isinstance(value, Mapping):
        raise ProviderTransportError(
            "official provider response must be a JSON object"
        )
    return HTTPResponseEnvelope(
        status_code=status,
        headers=safe_headers,
        body=dict(value),
    )


def _assert_no_secret_text(
    text: str,
    *,
    path: str,
    allow_pinned_synthetic_credential_labels: bool = False,
    active_api_key: str | None = None,
) -> None:
    if active_api_key and active_api_key in text:
        raise ProviderPayloadError(
            f"{path}: active credential content is forbidden"
        )
    for pattern in SECRET_TEXT_PATTERNS:
        if (
            pattern is SYNTHETIC_CREDENTIAL_LABEL_PATTERN
            and allow_pinned_synthetic_credential_labels
        ):
            continue
        if pattern.search(text):
            raise ProviderPayloadError(
                f"{path}: credential-like content is forbidden"
            )


def validate_messages(
    messages: Sequence[Mapping[str, str]],
    *,
    content_class: str,
    policy: Mapping[str, Any],
    allow_pinned_synthetic_credential_labels: bool = False,
    active_api_key: str | None = None,
) -> list[dict[str, str]]:
    """验证单个公开/合成提示词，且不持久化其内容。

    显式公开基准测试选择仅忽略通用的合成凭据标签分配。高置信度凭据模式和活动客户端密钥仍保持安全闭合失败。
    """

    allowed = policy["common_controls"]["payload_classes_allowed"]
    if content_class not in allowed:
        raise ProviderPayloadError("outbound content class is not allowed")
    if not isinstance(allow_pinned_synthetic_credential_labels, bool):
        raise ProviderPayloadError(
            "synthetic credential-label allowance must be boolean"
        )
    allow_synthetic_labels = bool(
        allow_pinned_synthetic_credential_labels
        and content_class == "public_benchmark_case"
    )
    if not isinstance(messages, Sequence) or isinstance(
        messages, (str, bytes)
    ):
        raise ProviderPayloadError("messages must be a sequence")
    if not messages:
        raise ProviderPayloadError("messages must not be empty")
    normalized: list[dict[str, str]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, Mapping):
            raise ProviderPayloadError(f"messages[{index}] must be an object")
        if set(message) != {"role", "content"}:
            raise ProviderPayloadError(
                f"messages[{index}] may contain only role and content"
            )
        role = str(message["role"]).strip().casefold()
        content = message["content"]
        if role not in ALLOWED_MESSAGE_ROLES:
            raise ProviderPayloadError(f"messages[{index}].role is unsupported")
        if not isinstance(content, str):
            raise ProviderPayloadError(
                f"messages[{index}].content must be text"
            )
        _assert_no_secret_text(
            content,
            path=f"messages[{index}].content",
            allow_pinned_synthetic_credential_labels=allow_synthetic_labels,
            active_api_key=active_api_key,
        )
        normalized.append({"role": role, "content": content})
    return normalized


def _provider_endpoint(policy: Mapping[str, Any], provider_id: str) -> str:
    provider = policy[provider_id]
    endpoint = str(provider["base_url"]).rstrip("/") + "/chat/completions"
    validate_provider_endpoint(provider_id, endpoint)
    return endpoint


def _request_id(headers: Mapping[str, str]) -> str | None:
    normalized = {str(key).casefold(): str(value) for key, value in headers.items()}
    for key in REQUEST_ID_HEADERS:
        value = normalized.get(key)
        if value:
            return value
    return None


def _validate_persisted_value(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).casefold()
            if lowered in FORBIDDEN_PERSISTED_KEYS:
                raise ProviderPayloadError(
                    f"{path}.{key}: forbidden persisted field"
                )
            _validate_persisted_value(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_persisted_value(child, path=f"{path}[{index}]")
    elif isinstance(value, str):
        _assert_no_secret_text(value, path=path)


def validate_provider_receipt(receipt: Mapping[str, Any]) -> None:
    """拒绝内容、标头、凭据或无效的收据摘要。"""

    if receipt.get("schema_version") != (
        "m3-paper-v2-official-provider-receipt-1.0"
    ):
        raise ProviderPayloadError("unsupported provider receipt")
    if receipt.get("credentials_stored") is not False:
        raise ProviderPayloadError("provider receipt must not store credentials")
    _validate_persisted_value(receipt)
    evidence = receipt.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ProviderPayloadError("provider receipt evidence is missing")
    if receipt.get("evidence_sha256") != sha256_canonical_json(evidence):
        raise ProviderPayloadError("provider receipt evidence hash mismatch")


def provider_receipt_to_attestation(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """将安全的提供商收据投影到 paper-v2 记录契约中。

    注入的传输仅作为本地资格论据。仅当确切模型和提供商请求/响应标识符均存在时，真正的官方传输才成为形式化候选对象。缺失的请求 ID 将被透明保留，但强制生成诊断论据。
    """

    validate_provider_receipt(receipt)
    evidence = receipt["evidence"]
    provider_id = str(evidence.get("provider_id", "")).casefold()
    if provider_id not in ALLOWED_PROVIDERS:
        raise ProviderPayloadError("provider receipt has an unsupported provider")
    transport_kind = evidence.get("transport_kind")
    if transport_kind not in {"official_network", "injected_test_double"}:
        raise ProviderPayloadError("provider receipt transport kind is invalid")
    exact_model = (
        evidence.get("model_identity_exact_match") is True
        and evidence.get("configured_model") == evidence.get("returned_model")
    )
    request_id = evidence.get("request_id")
    response_id = evidence.get("response_id")
    official_network = transport_kind == "official_network"
    identity_verified = bool(
        official_network
        and exact_model
        and evidence.get("identity_verified") is True
        and response_id
    )
    formal_candidate = bool(identity_verified and request_id and response_id)

    if official_network:
        endpoint_type = "official_api"
        provider_name = PROVIDER_DISPLAY_NAMES[provider_id]
        upstream_provider: str | None = provider_name
        prompt_rewrite_declaration = str(
            evidence["prompt_rewrite_declaration"]
        )
        identity_evidence = (
            "official_response" if identity_verified else "unverified"
        )
        evidence_level = (
            "formal_candidate" if formal_candidate else "diagnostic_only"
        )
    else:
        endpoint_type = "stub"
        provider_name = f"paper-v2-injected-{provider_id}-qualification"
        upstream_provider = None
        request_id = None
        response_id = None
        prompt_rewrite_declaration = "not_applicable"
        identity_evidence = "not_applicable"
        identity_verified = False
        evidence_level = "local_qualification"

    attestation = {
        "endpoint_type": endpoint_type,
        "provider_name": provider_name,
        "upstream_provider": upstream_provider,
        "model_id": str(evidence["returned_model"]),
        "model_revision": None,
        "request_id": request_id,
        "response_id": response_id,
        "requested_at": str(evidence["requested_at"]),
        "parameters_sha256": str(evidence["payload_sha256"]),
        "prompt_rewrite_declaration": prompt_rewrite_declaration,
        "identity_evidence": identity_evidence,
        "identity_verified": identity_verified,
        "evidence_level": evidence_level,
    }
    _validate_persisted_value(attestation)
    return attestation


@dataclass(frozen=True)
class OfficialProviderCompletion:
    """瞬态模型文本加上安全的持久化收据。"""

    text: str = field(repr=False)
    model_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str
    usage_available: bool
    usage_source: str
    prompt_eval_count: int
    eval_count: int
    provider_attempts: int
    provider_done: bool
    receipt: Mapping[str, Any]


@dataclass
class ProviderBudgetState:
    """进程内保险丝状态；新批次必须从账本重建。"""

    provider_id: str
    policy: Mapping[str, Any]
    deepseek_prompt_tokens: int = 0
    deepseek_cache_hit_tokens: int = 0
    deepseek_cache_miss_tokens: int = 0
    deepseek_completion_tokens: int = 0
    gemini_requests: int = 0
    gemini_input_tokens: int = 0
    gemini_output_tokens: int = 0
    pause_reason: str | None = None

    def __post_init__(self) -> None:
        if self.provider_id not in ALLOWED_PROVIDERS:
            raise ProviderPayloadError("unsupported provider budget state")
        validate_policy(dict(self.policy))

    def assert_before_request(self) -> None:
        if self.pause_reason is not None:
            raise ProviderPausedError(self.pause_reason)
        if self.provider_id == "deepseek":
            try:
                check_deepseek_headroom(
                    dict(self.policy),
                    {
                        "prompt_tokens": self.deepseek_prompt_tokens,
                        "prompt_cache_hit_tokens": (
                            self.deepseek_cache_hit_tokens
                        ),
                        "prompt_cache_miss_tokens": (
                            self.deepseek_cache_miss_tokens
                        ),
                        "completion_tokens": self.deepseek_completion_tokens,
                    },
                )
            except BudgetPolicyError as exc:
                raise ProviderPausedError(str(exc)) from exc
            return
        bound = self.policy["deepseek"]["dynamic_fuse"]
        try:
            check_gemini_free_batch(
                dict(self.policy),
                requests=self.gemini_requests + 1,
                input_tokens=(
                    self.gemini_input_tokens
                    + int(bound["next_request_input_tokens_upper_bound"])
                ),
                output_tokens=(
                    self.gemini_output_tokens
                    + int(bound["next_request_output_tokens_upper_bound"])
                ),
                charged_usd=0.0,
                billing_tier="free",
            )
        except BudgetPolicyError as exc:
            raise ProviderPausedError(str(exc)) from exc

    def record_usage(self, usage: Mapping[str, int]) -> dict[str, Any]:
        if self.provider_id == "deepseek":
            normalized = validate_deepseek_usage(dict(usage))
            self.deepseek_prompt_tokens += normalized["prompt_tokens"]
            self.deepseek_cache_hit_tokens += normalized[
                "prompt_cache_hit_tokens"
            ]
            self.deepseek_cache_miss_tokens += normalized[
                "prompt_cache_miss_tokens"
            ]
            self.deepseek_completion_tokens += normalized["completion_tokens"]
            cumulative = {
                "prompt_tokens": self.deepseek_prompt_tokens,
                "prompt_cache_hit_tokens": self.deepseek_cache_hit_tokens,
                "prompt_cache_miss_tokens": self.deepseek_cache_miss_tokens,
                "completion_tokens": self.deepseek_completion_tokens,
            }
            cost = deepseek_cost_cny(
                dict(self.policy),
                cache_hit_input_tokens=self.deepseek_cache_hit_tokens,
                cache_miss_input_tokens=self.deepseek_cache_miss_tokens,
                output_tokens=self.deepseek_completion_tokens,
            )
            try:
                headroom = check_deepseek_headroom(
                    dict(self.policy), cumulative
                )
                status = "continue"
            except BudgetPolicyError as exc:
                self.pause_reason = str(exc)
                headroom = None
                status = "pause_before_next_request"
            return {
                "status": status,
                "cumulative_usage": cumulative,
                "cumulative_cost_cny": float(cost),
                "headroom": headroom,
                "pause_reason": self.pause_reason,
            }

        prompt = int(usage["prompt_tokens"])
        completion = int(usage["completion_tokens"])
        self.gemini_requests += 1
        self.gemini_input_tokens += prompt
        self.gemini_output_tokens += completion
        state = check_gemini_free_batch(
            dict(self.policy),
            requests=self.gemini_requests,
            input_tokens=self.gemini_input_tokens,
            output_tokens=self.gemini_output_tokens,
            charged_usd=0.0,
            billing_tier="free",
        )
        return {
            "status": "continue",
            "cumulative_usage": {
                "requests": self.gemini_requests,
                "prompt_tokens": self.gemini_input_tokens,
                "completion_tokens": self.gemini_output_tokens,
            },
            "charged_usd": 0.0,
            "headroom": state,
            "pause_reason": None,
        }


@dataclass
class OfficialProviderClient:
    """用于 paper-v2 的单次尝试官方 OpenAI 兼容客户端。"""

    provider_id: str
    api_key: str = field(repr=False)
    content_class: str
    budget_state: ProviderBudgetState
    policy: Mapping[str, Any] | None = field(default=None, repr=False)
    temperature: float = 0.0
    max_tokens: int = 512
    timeout: float = 120.0
    network_consent: bool = False
    allow_pinned_synthetic_credential_labels: bool = False
    transport: Transport | None = field(default=None, repr=False)
    backend: str = field(default="official_api", init=False)
    last_request_metadata: dict[str, Any] = field(
        default_factory=dict, init=False
    )
    last_receipt: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.provider_id = self.provider_id.casefold().strip()
        if self.provider_id not in ALLOWED_PROVIDERS:
            raise ProviderPayloadError("provider must be deepseek or gemini")
        active = dict(self.policy or _load_policy())
        validate_policy(active)
        self.policy = active
        if self.budget_state.provider_id != self.provider_id:
            raise ProviderPayloadError("budget state provider does not match client")
        if dict(self.budget_state.policy) != active:
            raise ProviderPayloadError("budget state policy does not match client")
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise ProviderPayloadError("api_key is required at execution time")
        if "\r" in self.api_key or "\n" in self.api_key:
            raise ProviderPayloadError("api_key contains invalid control characters")
        if not isinstance(
            self.allow_pinned_synthetic_credential_labels, bool
        ):
            raise ProviderPayloadError(
                "synthetic credential-label allowance must be boolean"
            )
        if self.temperature != 0:
            raise ProviderPayloadError("formal provider temperature must be zero")
        if self.max_tokens < 1 or self.max_tokens > int(
            active["deepseek"]["dynamic_fuse"][
                "next_request_output_tokens_upper_bound"
            ]
        ):
            raise ProviderPayloadError("max_tokens exceeds the frozen bound")
        if self.timeout <= 0:
            raise ProviderPayloadError("timeout must be positive")
        if self.transport is None and not self.network_consent:
            raise ProviderConsentError(
                "real official provider transport requires explicit network consent"
            )
        _provider_endpoint(active, self.provider_id)
        validate_messages(
            [{"role": "user", "content": "qualification placeholder"}],
            content_class=self.content_class,
            policy=active,
            allow_pinned_synthetic_credential_labels=(
                self.allow_pinned_synthetic_credential_labels
            ),
            active_api_key=self.api_key,
        )

    @property
    def model(self) -> str:
        return str(self.policy[self.provider_id]["model_id"])

    @property
    def endpoint(self) -> str:
        return _provider_endpoint(self.policy, self.provider_id)

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
            raise ProviderTransportError("official provider response has no choices")
        choice = choices[0]
        if not isinstance(choice, Mapping):
            raise ProviderTransportError("official provider choice is malformed")
        message = choice.get("message")
        if not isinstance(message, Mapping):
            raise ProviderTransportError("official provider message is malformed")
        text = str(message.get("content", "") or "")
        finish_reason = str(choice.get("finish_reason", "") or "")
        usage_raw = body.get("usage")
        if not isinstance(usage_raw, Mapping):
            raise ProviderUsageError("official provider usage is required")
        prompt_tokens = _optional_int(usage_raw.get("prompt_tokens"))
        completion_tokens = _optional_int(usage_raw.get("completion_tokens"))
        total_tokens = _optional_int(usage_raw.get("total_tokens"))
        if prompt_tokens is None or completion_tokens is None:
            raise ProviderUsageError("prompt and completion token usage is required")
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ProviderUsageError("provider token usage must be non-negative")
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens
        if total_tokens < prompt_tokens + completion_tokens:
            raise ProviderUsageError("provider total token usage is inconsistent")

        usage: dict[str, int] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        if self.provider_id == "deepseek":
            hit = _optional_int(usage_raw.get("prompt_cache_hit_tokens"))
            miss = _optional_int(usage_raw.get("prompt_cache_miss_tokens"))
            if hit is None or miss is None:
                raise ProviderUsageError(
                    "DeepSeek cache hit and miss usage are required"
                )
            usage.update(
                {
                    "prompt_cache_hit_tokens": hit,
                    "prompt_cache_miss_tokens": miss,
                }
            )
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
            "response_text_sha256": _sha256_bytes(text.encode("utf-8")),
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
            usage_source=f"{self.provider_id}_official_chat_usage",
            prompt_eval_count=prompt_tokens,
            eval_count=completion_tokens,
            provider_attempts=1,
            provider_done=True,
            receipt=receipt,
        )


def _event_call_key(event: Mapping[str, Any]) -> tuple[str, int]:
    work_key = event.get("work_key")
    call_index = event.get("call_index")
    if not isinstance(work_key, str) or not work_key:
        raise ProviderLedgerError("ledger event work_key is required")
    if (
        isinstance(call_index, bool)
        or not isinstance(call_index, int)
        or call_index < 1
    ):
        raise ProviderLedgerError("ledger event call_index must be positive")
    return work_key, call_index


def validate_call_events(
    events: Sequence[Mapping[str, Any]],
    *,
    execution_identity: str,
    provider_id: str,
    model_id: str,
) -> dict[str, Any]:
    """验证单次尝试调用和手动同提供商 429 恢复。"""

    if provider_id not in ALLOWED_PROVIDERS:
        raise ProviderLedgerError("unsupported ledger provider")
    open_attempts: dict[str, tuple[str, int]] = {}
    terminal_attempts: set[str] = set()
    call_history: dict[tuple[str, int], list[str]] = {}
    terminal_by_call: dict[tuple[str, int], str] = {}
    for number, event in enumerate(events, start=1):
        if event.get("schema_version") != "m3-paper-v2-provider-call-event-1.0":
            raise ProviderLedgerError(
                f"ledger event {number}: unsupported schema"
            )
        if event.get("execution_identity") != execution_identity:
            raise ProviderLedgerError(
                f"ledger event {number}: execution identity drift"
            )
        if event.get("provider_id") != provider_id:
            raise ProviderLedgerError(
                f"ledger event {number}: cross-provider fallback is forbidden"
            )
        if event.get("model_id") != model_id:
            raise ProviderLedgerError(
                f"ledger event {number}: model identity drift"
            )
        if event.get("automatic_retry") is not False:
            raise ProviderLedgerError(
                f"ledger event {number}: automatic retry is forbidden"
            )
        attempt_id = event.get("attempt_id")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise ProviderLedgerError(
                f"ledger event {number}: attempt_id is required"
            )
        call_key = _event_call_key(event)
        event_type = event.get("event_type")
        if event_type == "started":
            if attempt_id in open_attempts or attempt_id in terminal_attempts:
                raise ProviderLedgerError(
                    f"ledger event {number}: duplicate attempt"
                )
            prior = terminal_by_call.get(call_key)
            if prior is not None:
                if prior != "paused":
                    raise ProviderLedgerError(
                        f"ledger event {number}: terminal call cannot restart"
                    )
                if event.get("resume_mode") != "manual_provider_recovery":
                    raise ProviderLedgerError(
                        f"ledger event {number}: paused call requires manual resume"
                    )
                authorization_id = event.get("manual_resume_authorization_id")
                if not isinstance(authorization_id, str) or not authorization_id:
                    raise ProviderLedgerError(
                        f"ledger event {number}: manual resume authorization is required"
                    )
            elif event.get("resume_mode") not in {None, "none"}:
                raise ProviderLedgerError(
                    f"ledger event {number}: first attempt cannot be a resume"
                )
            open_attempts[attempt_id] = call_key
            call_history.setdefault(call_key, []).append(attempt_id)
            continue
        if event_type not in TERMINAL_EVENT_TYPES:
            raise ProviderLedgerError(
                f"ledger event {number}: unsupported event type"
            )
        if attempt_id not in open_attempts:
            raise ProviderLedgerError(
                f"ledger event {number}: terminal event without start"
            )
        if open_attempts.pop(attempt_id) != call_key:
            raise ProviderLedgerError(
                f"ledger event {number}: terminal call identity mismatch"
            )
        terminal_attempts.add(attempt_id)
        terminal_by_call[call_key] = str(event_type)
        if event_type == "paused" and event.get("http_status") != 429:
            raise ProviderLedgerError(
                f"ledger event {number}: pause is reserved for HTTP 429"
            )
        if event_type == "completed":
            receipt = event.get("receipt")
            if not isinstance(receipt, Mapping):
                raise ProviderLedgerError(
                    f"ledger event {number}: completed call lacks receipt"
                )
            try:
                validate_provider_receipt(receipt)
            except ProviderPayloadError as exc:
                raise ProviderLedgerError(str(exc)) from exc
        _validate_persisted_value(event)
    completed_calls = sum(
        terminal == "completed" for terminal in terminal_by_call.values()
    )
    return {
        "event_count": len(events),
        "call_count": len(call_history),
        "completed_calls": completed_calls,
        "paused_calls": sum(
            terminal == "paused" for terminal in terminal_by_call.values()
        ),
        "failed_calls": sum(
            terminal == "failed" for terminal in terminal_by_call.values()
        ),
        "open_attempts": len(open_attempts),
        "manual_resumed_calls": sum(
            len(attempts) > 1 for attempts in call_history.values()
        ),
        "terminal_by_call": {
            f"{work_key}:{call_index}": status
            for (work_key, call_index), status in sorted(
                terminal_by_call.items()
            )
        },
    }


def append_call_event(
    path: Path,
    event: Mapping[str, Any],
    *,
    execution_identity: str,
    provider_id: str,
    model_id: str,
) -> None:
    """验证完整的候选调用链，然后追加并刷新单个事件。"""

    _validate_persisted_value(event)
    prior = load_call_events(path)
    validate_call_events(
        [*prior, dict(event)],
        execution_identity=execution_identity,
        provider_id=provider_id,
        model_id=model_id,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(_canonical_bytes(dict(event)).decode("utf-8") + "\n")
        stream.flush()


def load_call_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ProviderLedgerError(
                    f"{path}:{line_number}: expected a JSON object"
                )
            events.append(value)
    return events


def _fixture_transport(
    provider_id: str,
    *,
    captured: dict[str, Any],
) -> Transport:
    def transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> HTTPResponseEnvelope:
        captured.update(
            {
                "endpoint": endpoint,
                "header_names": sorted(headers),
                "authorization_present": "Authorization" in headers,
                "payload_sha256": _sha256_bytes(_canonical_bytes(payload)),
                "payload_keys": sorted(payload),
                "timeout": timeout,
            }
        )
        if provider_id == "deepseek":
            return HTTPResponseEnvelope(
                status_code=200,
                headers={"x-request-id": "fixture-deepseek-request"},
                body={
                    "id": "fixture-deepseek-response",
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": '{"tool":"final","arguments":{"answer":"SAFE"}}',
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "prompt_cache_hit_tokens": 90,
                        "prompt_cache_miss_tokens": 10,
                        "completion_tokens": 10,
                        "total_tokens": 110,
                    },
                },
            )
        return HTTPResponseEnvelope(
            status_code=200,
            headers={"x-goog-request-id": "fixture-gemini-request"},
            body={
                "id": "fixture-gemini-response",
                "model": "gemini-3.6-flash",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"tool":"final","arguments":{"answer":"SAFE"}}',
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 10,
                    "total_tokens": 110,
                },
            },
        )

    return transport


def build_offline_transport_qualification(
    policy_path: Path = DEFAULT_BUDGET_POLICY,
) -> dict[str, Any]:
    """使用测试固件演练两种传输；输出不包含实际内容。"""

    policy = _load_policy(policy_path)
    providers: dict[str, Any] = {}
    for provider_id in sorted(ALLOWED_PROVIDERS):
        captured: dict[str, Any] = {}
        state = ProviderBudgetState(provider_id=provider_id, policy=policy)
        client = OfficialProviderClient(
            provider_id=provider_id,
            api_key=f"fixture-key-for-{provider_id}",
            content_class="fixed_non_sensitive_runtime_instruction",
            budget_state=state,
            policy=policy,
            transport=_fixture_transport(provider_id, captured=captured),
        )
        completion = client.complete(
            [{"role": "user", "content": "fixed synthetic qualification"}]
        )
        receipt = dict(completion.receipt)
        validate_provider_receipt(receipt)
        evidence = receipt["evidence"]
        attestation = provider_receipt_to_attestation(receipt)
        stable_evidence = {
            key: value
            for key, value in evidence.items()
            if key not in {"requested_at", "model_latency_ms"}
        }
        providers[provider_id] = {
            "status": "offline_injected_transport_pass",
            "configured_model": evidence["configured_model"],
            "returned_model": evidence["returned_model"],
            "model_identity_exact_match": evidence[
                "model_identity_exact_match"
            ],
            "request_id_present": bool(evidence["request_id"]),
            "response_id_present": bool(evidence["response_id"]),
            "identity_verified_for_fixture": evidence["identity_verified"],
            "experiment_record_evidence_level": attestation[
                "evidence_level"
            ],
            "formal_record_eligible": (
                attestation["evidence_level"] == "formal_candidate"
            ),
            "provider_attempts": completion.provider_attempts,
            "usage": dict(evidence["usage"]),
            "budget_status": evidence["budget"]["status"],
            "payload_sha256": captured["payload_sha256"],
            "payload_keys": captured["payload_keys"],
            "provider_tools_declared": (
                "tools" in captured["payload_keys"]
                or "tool_choice" in captured["payload_keys"]
            ),
            "authorization_header_used_transiently": captured[
                "authorization_present"
            ],
            "request_headers_persisted": False,
            "prompt_or_response_content_persisted": False,
            "stable_receipt_evidence_sha256": sha256_canonical_json(
                stable_evidence
            ),
        }
    return {
        "schema_version": "m3-paper-v2-provider-executor-qualification-1.0",
        "generated_at": "2026-07-24T00:30:00+08:00",
        "status": "offline_transport_qualified_live_execution_pending",
        "network_calls_made": 0,
        "credentials_read": False,
        "credential_values_persisted": False,
        "automatic_retries": 0,
        "providers": providers,
        "formal_result_created": False,
        "formal_identity_attested": False,
        "interpretation": {
            "supported": [
                "Both official endpoint builders, exact-model checks, request/response ID extraction, usage parsers and budget hooks pass with injected responses.",
                "Persisted receipts contain hashes, IDs, usage and budget state but no prompt, response text, headers or credential values.",
                "Every client call has one transport attempt and declares no provider-managed tools.",
            ],
            "not_supported": [
                "Live exact-model/response-ID identity evidence; fixture IDs do not attest a provider.",
                "Complete request tracing when an official API omits an HTTP request ID.",
                "Any benchmark, condition, safety-effect or model-quality result.",
                "Formal execution authorization.",
            ],
        },
    }
