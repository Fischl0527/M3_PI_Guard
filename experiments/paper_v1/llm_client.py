"""Paper-v1-only Ollama client extensions.

The historical ``m3_core.llm_client`` is hash-bound by earlier experiment
freezes.  Thinking control therefore lives in this independent paper track.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter_ns
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from m3_core.llm_client import (
    CompletionResult,
    LLMClient,
    _elapsed_ms,
    _native_chat_url,
    _optional_int,
)


@dataclass
class PaperLLMClient(LLMClient):
    """LLM client whose extra request controls are frozen by paper manifests."""

    think: bool | None = None

    def _complete_ollama_native(
        self,
        messages: list[dict[str, str]],
        *,
        started_ns: int | None = None,
    ) -> CompletionResult:
        options: dict[str, Any] = {
            "temperature": float(self.temperature),
            "num_predict": int(self.max_tokens),
        }
        if self.seed is not None:
            options["seed"] = int(self.seed)
        if self.num_ctx is not None:
            options["num_ctx"] = int(self.num_ctx)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if self.think is not None:
            payload["think"] = bool(self.think)
        request = urllib_request.Request(
            _native_chat_url(str(self.base_url)),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(
                request,
                timeout=float(self.timeout),
            ) as response:
                body = response.read()
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama native HTTP {exc.code}: {detail}") from exc
        except urllib_error.URLError as exc:
            raise RuntimeError(f"Ollama native request failed: {exc.reason}") from exc
        try:
            result = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Ollama native response was not valid JSON") from exc
        if not isinstance(result, dict):
            raise RuntimeError("Ollama native response must be a JSON object")
        message = result.get("message")
        text = str(message.get("content", "")) if isinstance(message, dict) else ""
        prompt_count = _optional_int(result.get("prompt_eval_count"))
        eval_count = _optional_int(result.get("eval_count"))
        total_tokens = (
            prompt_count + eval_count
            if prompt_count is not None and eval_count is not None
            else None
        )
        return CompletionResult(
            text=text,
            model_latency_ms=_elapsed_ms(started_ns or perf_counter_ns()),
            prompt_tokens=prompt_count,
            completion_tokens=eval_count,
            total_tokens=total_tokens,
            finish_reason=str(result.get("done_reason", "") or ""),
            usage_available=prompt_count is not None,
            usage_source=(
                "ollama_native_prompt_eval_count" if prompt_count is not None else ""
            ),
            prompt_eval_count=prompt_count,
            eval_count=eval_count,
            provider_total_duration_ns=_optional_int(result.get("total_duration")),
            provider_load_duration_ns=_optional_int(result.get("load_duration")),
            provider_prompt_eval_duration_ns=_optional_int(
                result.get("prompt_eval_duration")
            ),
            provider_eval_duration_ns=_optional_int(result.get("eval_duration")),
            provider_attempts=1,
            provider_done=(
                bool(result.get("done")) if result.get("done") is not None else None
            ),
        )
