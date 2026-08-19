"""Minimal one-request frontier API clients for frozen paper experiments.

The clients perform no retries and require explicit network consent when using
the real transport.  Credentials are held only in request headers and are never
included in request metadata, exceptions produced here, or persisted records.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Any, Callable, Mapping, Sequence
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from m3_core.llm_client import CompletionResult

from .benchmarks.common import canonical_json, sha256_bytes


Transport = Callable[
    [str, Mapping[str, str], Mapping[str, Any], float], Mapping[str, Any]
]
SUPPORTED_PROVIDERS = frozenset({"openai", "anthropic"})
DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
}


def _elapsed_ms(started_ns: int) -> float:
    return round((perf_counter_ns() - started_ns) / 1_000_000, 6)


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _endpoint(base_url: str, suffix: str) -> str:
    return base_url.rstrip("/") + "/" + suffix.lstrip("/")


def _default_transport(
    endpoint: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> Mapping[str, Any]:
    request = urllib_request.Request(
        endpoint,
        data=json.dumps(dict(payload), ensure_ascii=False).encode("utf-8"),
        headers=dict(headers),
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib_error.HTTPError as exc:
        raise RuntimeError(f"frontier API HTTP {exc.code}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"frontier API transport error: {type(exc.reason).__name__}") from exc
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("frontier API response was not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise RuntimeError("frontier API response must be a JSON object")
    return value


@dataclass
class FrontierAPIClient:
    provider: str
    model: str
    api_key: str
    base_url: str = ""
    temperature: float = 0.0
    max_tokens: int = 512
    seed: int | None = None
    timeout: float = 120.0
    network_consent: bool = False
    transport: Transport | None = field(default=None, repr=False)
    backend: str = field(default="frontier_api", init=False)
    last_request_metadata: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.provider = self.provider.casefold().strip()
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError("provider must be openai or anthropic")
        if not self.model.strip() or not self.api_key.strip():
            raise ValueError("model and api_key are required")
        self.base_url = (self.base_url or DEFAULT_BASE_URLS[self.provider]).rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("frontier API base URL must use HTTPS")
        if self.max_tokens < 1 or self.timeout <= 0:
            raise ValueError("max_tokens and timeout must be positive")
        if self.transport is None and not self.network_consent:
            raise ValueError("real frontier transport requires explicit network consent")

    def _openai_request(
        self, messages: Sequence[Mapping[str, str]]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        endpoint = _endpoint(self.base_url, "chat/completions")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [dict(message) for message in messages],
            "temperature": float(self.temperature),
            "max_tokens": int(self.max_tokens),
        }
        if self.seed is not None:
            payload["seed"] = int(self.seed)
        return endpoint, headers, payload

    def _anthropic_request(
        self, messages: Sequence[Mapping[str, str]]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        endpoint = _endpoint(self.base_url, "messages")
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        system_parts = [
            str(message.get("content", ""))
            for message in messages
            if str(message.get("role", "")) == "system"
        ]
        conversation = [
            {
                "role": str(message.get("role", "user")),
                "content": str(message.get("content", "")),
            }
            for message in messages
            if str(message.get("role", "")) in {"user", "assistant"}
        ]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": conversation,
            "max_tokens": int(self.max_tokens),
            "temperature": float(self.temperature),
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        return endpoint, headers, payload

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        case: dict[str, Any] | None = None,
        step: int = 1,
        observations: list[Any] | None = None,
    ) -> CompletionResult:
        del case, step, observations
        started = perf_counter_ns()
        if self.provider == "openai":
            endpoint, headers, payload = self._openai_request(messages)
        else:
            endpoint, headers, payload = self._anthropic_request(messages)
        request_record = {
            "provider": self.provider,
            "model": self.model,
            "endpoint_origin": f"{urlparse(endpoint).scheme}://{urlparse(endpoint).netloc}",
            "payload_sha256": sha256_bytes(canonical_json(payload).encode("utf-8")),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "seed_sent": self.provider == "openai" and self.seed is not None,
            "provider_attempts": 1,
        }
        self.last_request_metadata = request_record
        response = (self.transport or _default_transport)(
            endpoint, headers, payload, float(self.timeout)
        )
        if self.provider == "openai":
            choices = response.get("choices", [])
            if not isinstance(choices, list) or not choices:
                raise RuntimeError("OpenAI response has no choices")
            choice = choices[0]
            message = choice.get("message", {}) if isinstance(choice, Mapping) else {}
            text = str(message.get("content", "")) if isinstance(message, Mapping) else ""
            finish_reason = str(choice.get("finish_reason", "")) if isinstance(choice, Mapping) else ""
            usage = response.get("usage", {})
            usage = usage if isinstance(usage, Mapping) else {}
            prompt_tokens = _optional_int(usage.get("prompt_tokens"))
            completion_tokens = _optional_int(usage.get("completion_tokens"))
            total_tokens = _optional_int(usage.get("total_tokens"))
            usage_source = "openai_chat_completions_usage"
        else:
            content = response.get("content", [])
            text_parts = [
                str(block.get("text", ""))
                for block in content
                if isinstance(block, Mapping) and block.get("type") == "text"
            ] if isinstance(content, list) else []
            text = "".join(text_parts)
            finish_reason = str(response.get("stop_reason", ""))
            usage = response.get("usage", {})
            usage = usage if isinstance(usage, Mapping) else {}
            prompt_tokens = _optional_int(usage.get("input_tokens"))
            completion_tokens = _optional_int(usage.get("output_tokens"))
            total_tokens = (
                prompt_tokens + completion_tokens
                if prompt_tokens is not None and completion_tokens is not None
                else None
            )
            usage_source = "anthropic_messages_usage"
        return CompletionResult(
            text=text,
            model_latency_ms=_elapsed_ms(started),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason=finish_reason,
            usage_available=bool(usage),
            usage_source=usage_source if usage else "",
            prompt_eval_count=prompt_tokens,
            eval_count=completion_tokens,
            provider_attempts=1,
            provider_done=True,
        )
