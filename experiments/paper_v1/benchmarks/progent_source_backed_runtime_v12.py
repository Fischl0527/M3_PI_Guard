"""Auditable Progent v1.2 runtime for isolated AgentDojo case workers.

The pinned upstream policy generator, retry count, temperature schedule,
prompts and enforcement remain unchanged.  This revision changes only the
transport/observability boundary: both clients have zero SDK retries, every
request is incrementally hash-traced, and policy changes are classified.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .progent_source_backed_runtime import (
    SUITE_ALWAYS_ALLOWED_TOOLS,
    _install_source_paths,
    _tool_descriptors,
)


PATCH_VERSION = "m3-progent-source-backed-runtime-1.2"
REQUEST_TIMEOUT_SECONDS = 120.0
SDK_MAX_RETRIES = 0
POLICY_TEMPERATURE_SEQUENCE = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
ROOT = Path(__file__).resolve().parents[3]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _usage(response: Any) -> dict[str, int | None]:
    usage = getattr(response, "usage", None)
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


class ProgentV12Trace:
    """Append-only, crash-tolerant request and policy trace."""

    def __init__(self, event_path: Path) -> None:
        self.event_path = event_path
        self.event_path.parent.mkdir(parents=True, exist_ok=True)
        self.events: list[dict[str, Any]] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.policy_transitions: list[dict[str, Any]] = []
        self.request_counts: dict[str, int] = {}
        self.last_policy_request_id = ""
        self.suite = ""
        self.case_id = ""

    def start_case(self, *, suite: str, case_id: str) -> None:
        self.suite = suite
        self.case_id = case_id
        self.record(
            {
                "event": "case_started",
                "suite": suite,
                "benchmark_case_id": case_id,
                "runtime_patch_version": PATCH_VERSION,
            }
        )

    def record(self, row: Mapping[str, Any]) -> dict[str, Any]:
        event = {
            "sequence": len(self.events) + 1,
            "created_at": _utc_now(),
            **dict(row),
        }
        self.events.append(event)
        with self.event_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def next_request(self, phase: str) -> tuple[str, int]:
        attempt = self.request_counts.get(phase, 0) + 1
        self.request_counts[phase] = attempt
        return f"{phase}:{attempt}", attempt

    def snapshot(self, secagent: Any | None = None) -> dict[str, Any]:
        allowed: list[str] = []
        policy: Any = None
        if secagent is not None:
            allowed = sorted(str(row["name"]) for row in secagent.get_allowed_tools())
            policy = copy.deepcopy(secagent.get_current_config())
        return {
            "runtime_patch_version": PATCH_VERSION,
            "suite": self.suite,
            "benchmark_case_id": self.case_id,
            "event_count": len(self.events),
            "events": copy.deepcopy(self.events),
            "request_counts": dict(self.request_counts),
            "tool_calls": copy.deepcopy(self.tool_calls),
            "policy_transitions": copy.deepcopy(self.policy_transitions),
            "allowed_tool_names": allowed,
            "generated_policy": policy,
            "sdk_max_retries": SDK_MAX_RETRIES,
            "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        }


def _policy_phase(secagent_tool: Any, sys_prompt: str) -> str:
    if sys_prompt == str(getattr(secagent_tool, "SYS_PROMPT_UPDATE", "")):
        return "policy_update_decision"
    try:
        if sys_prompt == secagent_tool.get_SYS_PROMPT_2():
            return "policy_update"
    except Exception:
        pass
    return "policy_initial"


def _bind_policy_transport(
    *, secagent_tool: Any, trace: ProgentV12Trace, base_url: str, model_id: str
) -> dict[str, Any]:
    import openai

    client = openai.OpenAI(
        api_key="ollama-local",
        base_url=base_url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=SDK_MAX_RETRIES,
    )
    original_extract_json = secagent_tool.extract_json

    def api_request(sys_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        phase = _policy_phase(secagent_tool, sys_prompt)
        request_id, attempt = trace.next_request(phase)
        started_at = _utc_now()
        started = time.perf_counter()
        prompt_hash = _hash_text(
            json.dumps(
                {"system": sys_prompt, "user": user_prompt},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        try:
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=model_id,
                temperature=temperature,
                seed=0,
            )
            raw = str(response.choices[0].message.content or "")
            trace.last_policy_request_id = request_id
            trace.record(
                {
                    "event": "model_request",
                    "client_role": "policy",
                    "phase": phase,
                    "request_id": request_id,
                    "attempt": attempt,
                    "temperature": float(temperature),
                    "prompt_sha256": prompt_hash,
                    "raw_response_sha256": _hash_text(raw),
                    "parse_result": (
                        "not_applicable"
                        if phase == "policy_update_decision"
                        else "pending_correlated_parse_event"
                    ),
                    "error_type": "",
                    "started_at": started_at,
                    "finished_at": _utc_now(),
                    "duration_ms": round((time.perf_counter() - started) * 1000.0, 6),
                    "sdk_max_retries": SDK_MAX_RETRIES,
                    **_usage(response),
                }
            )
            return raw
        except Exception as exc:
            trace.record(
                {
                    "event": "model_request",
                    "client_role": "policy",
                    "phase": phase,
                    "request_id": request_id,
                    "attempt": attempt,
                    "temperature": float(temperature),
                    "prompt_sha256": prompt_hash,
                    "raw_response_sha256": "",
                    "parse_result": "not_reached",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "started_at": started_at,
                    "finished_at": _utc_now(),
                    "duration_ms": round((time.perf_counter() - started) * 1000.0, 6),
                    "sdk_max_retries": SDK_MAX_RETRIES,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                }
            )
            raise

    def traced_extract_json(text: str, enforce_code_block: bool = False):
        request_id = trace.last_policy_request_id
        try:
            value = original_extract_json(text, enforce_code_block=enforce_code_block)
            valid = value is None or isinstance(value, list)
            trace.record(
                {
                    "event": "policy_parse",
                    "request_id": request_id,
                    "parse_result": "success" if valid else "invalid_top_level_type",
                    "parsed_type": type(value).__name__,
                    "error_type": "" if valid else "PolicyCardinalityError",
                }
            )
            if not valid:
                raise TypeError("Progent policy response must be a list or null")
            return value
        except Exception as exc:
            trace.record(
                {
                    "event": "policy_parse",
                    "request_id": request_id,
                    "parse_result": "failure",
                    "parsed_type": "",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            raise

    secagent_tool.api_request = api_request
    secagent_tool.extract_json = traced_extract_json
    secagent_tool.policy_model = "Qwen/" + model_id
    return {
        "binding": "official_secagent_transport_v12",
        "base_url": base_url,
        "model_id": model_id,
        "timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "sdk_max_retries": SDK_MAX_RETRIES,
        "policy_retry_owner": "upstream_secagent_six_attempt_loop",
        "policy_temperature_sequence": list(POLICY_TEMPERATURE_SEQUENCE),
        "prompt_templates_changed": False,
        "policy_enforcement_changed": False,
    }


class _CompletionsProxy:
    def __init__(self, target: Any, trace: ProgentV12Trace) -> None:
        self._target = target
        self._trace = trace

    def create(self, **kwargs: Any) -> Any:
        request_id, attempt = self._trace.next_request("agent")
        messages = kwargs.get("messages", [])
        tools = kwargs.get("tools", [])
        prompt_hash = _hash_text(
            json.dumps(
                {"messages": messages, "tools": tools},
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        )
        started_at = _utc_now()
        started = time.perf_counter()
        try:
            response = self._target.create(**kwargs)
            message = response.choices[0].message
            raw_fingerprint = json.dumps(
                {
                    "content": getattr(message, "content", None),
                    "tool_calls": [
                        getattr(call, "model_dump", lambda: str(call))()
                        for call in (getattr(message, "tool_calls", None) or [])
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            self._trace.record(
                {
                    "event": "model_request",
                    "client_role": "agent",
                    "phase": "agent",
                    "request_id": request_id,
                    "attempt": attempt,
                    "temperature": kwargs.get("temperature", 0.0),
                    "prompt_sha256": prompt_hash,
                    "raw_response_sha256": _hash_text(raw_fingerprint),
                    "parse_result": "handled_by_pinned_agentdojo",
                    "error_type": "",
                    "started_at": started_at,
                    "finished_at": _utc_now(),
                    "duration_ms": round((time.perf_counter() - started) * 1000.0, 6),
                    "sdk_max_retries": SDK_MAX_RETRIES,
                    **_usage(response),
                }
            )
            return response
        except Exception as exc:
            self._trace.record(
                {
                    "event": "model_request",
                    "client_role": "agent",
                    "phase": "agent",
                    "request_id": request_id,
                    "attempt": attempt,
                    "temperature": kwargs.get("temperature", 0.0),
                    "prompt_sha256": prompt_hash,
                    "raw_response_sha256": "",
                    "parse_result": "not_reached",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "started_at": started_at,
                    "finished_at": _utc_now(),
                    "duration_ms": round((time.perf_counter() - started) * 1000.0, 6),
                    "sdk_max_retries": SDK_MAX_RETRIES,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                }
            )
            raise


class _ChatProxy:
    def __init__(self, target: Any, trace: ProgentV12Trace) -> None:
        self.completions = _CompletionsProxy(target.completions, trace)


class _ClientProxy:
    def __init__(self, target: Any, trace: ProgentV12Trace) -> None:
        self._target = target
        self.chat = _ChatProxy(target.chat, trace)
        self.max_retries = SDK_MAX_RETRIES
        self.timeout = REQUEST_TIMEOUT_SECONDS

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


def _iter_elements(elements: Sequence[Any]):
    for element in elements:
        yield element
        nested = getattr(element, "elements", None)
        if isinstance(nested, Sequence):
            yield from _iter_elements(nested)


def _replace_agent_clients(
    *, pipeline: Any, trace: ProgentV12Trace, base_url: str
) -> int:
    import openai

    count = 0
    for element in _iter_elements(list(pipeline.elements)):
        if type(element).__name__ != "OpenAILLM":
            continue
        client = openai.OpenAI(
            api_key="ollama-local",
            base_url=base_url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=SDK_MAX_RETRIES,
        )
        element.client = _ClientProxy(client, trace)
        count += 1
    return count


def _classify_policy_transition(subset_check: Any, before: Any, after: Any) -> str:
    if before == after:
        return "unchanged"
    try:
        if before and subset_check(before, after):
            return "narrowing"
    except Exception:
        pass
    return "expansion_or_replacement"


def _record_policy_transition(
    *,
    trace: ProgentV12Trace,
    secagent: Any,
    subset_check: Any,
    phase: str,
    before: Any,
    source: str,
) -> None:
    after = copy.deepcopy(secagent.get_current_config())
    before_tools = sorted((before or {}).keys()) if isinstance(before, Mapping) else []
    after_tools = sorted((after or {}).keys()) if isinstance(after, Mapping) else []
    row = {
        "event": "policy_transition",
        "phase": phase,
        "classification": _classify_policy_transition(subset_check, before, after),
        "source": source,
        "before_sha256": _hash_text(json.dumps(before, sort_keys=True, default=str)),
        "after_sha256": _hash_text(json.dumps(after, sort_keys=True, default=str)),
        "added_tools": sorted(set(after_tools) - set(before_tools)),
        "removed_tools": sorted(set(before_tools) - set(after_tools)),
        "permission_expansion": bool(set(after_tools) - set(before_tools)),
    }
    trace.policy_transitions.append(dict(row))
    trace.record(row)


def _install_guarded_runtime(runtime: Any, secagent: Any, trace: ProgentV12Trace) -> None:
    if getattr(runtime, "__m3_progent_v12_guarded__", False):
        return
    original = runtime.run_function

    def guarded(
        self: Any,
        env: Any,
        function: str,
        kwargs: Mapping[str, Any],
        raise_on_error: bool = False,
    ) -> tuple[Any, str | None]:
        row = {
            "tool": str(function),
            "arguments": copy.deepcopy(dict(kwargs)),
            "decision": "allow",
            "error": "",
            "input_source": "agent_proposal",
        }
        try:
            secagent.check_tool_call(function, dict(kwargs))
        except Exception as exc:
            row["decision"] = "deny"
            row["error"] = f"{type(exc).__name__}: {exc}"
            trace.tool_calls.append(row)
            trace.record({"event": "tool_call", **row})
            if raise_on_error:
                raise
            return "", row["error"]
        result, error = original(env, function, kwargs, raise_on_error=raise_on_error)
        row["runtime_error"] = str(error or "")
        trace.tool_calls.append(row)
        trace.record({"event": "tool_call", **row})
        return result, error

    runtime.run_function = types.MethodType(guarded, runtime)
    runtime.__m3_progent_v12_guarded__ = True


def build_progent_pipeline_v12(
    freeze: Mapping[str, Any],
    *,
    trace_event_path: Path,
    case_id: str,
    suite: str,
    trace: ProgentV12Trace | None = None,
):
    """Build one isolated v1.2 pipeline without executing the benchmark case."""

    agentdojo_checkout = _resolve_repo_path(str(freeze["agentdojo"]["checkout"]))
    progent_checkout = _resolve_repo_path(str(freeze["progent"]["checkout"]))
    _install_source_paths(agentdojo_checkout, progent_checkout)
    flags = freeze["progent"]["runtime_flags"]
    for name, value in flags.items():
        os.environ[str(name)] = str(value)
    base_url = str(freeze["transport"]["base_url"])
    os.environ["OPENAI_COMPATIBLE_BASE_URL"] = base_url
    os.environ["OPENAI_COMPATIBLE_API_KEY"] = "ollama-local"

    import secagent
    import secagent.tool as secagent_tool
    from secagent.policy_analysis import security_policy_subset_check
    from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, PipelineConfig
    from agentdojo.agent_pipeline.basic_elements import InitQuery
    from agentdojo.agent_pipeline.tool_execution import ToolsExecutionLoop, ToolsExecutor
    from agentdojo.models import ModelsEnum
    from agentdojo.types import get_text_content_as_str

    trace = trace or ProgentV12Trace(trace_event_path)
    if not trace.events:
        trace.start_case(suite=suite, case_id=case_id)
    binding = _bind_policy_transport(
        secagent_tool=secagent_tool,
        trace=trace,
        base_url=base_url,
        model_id=str(freeze["model_id"]),
    )

    class ProgentPolicyInitQueryV12(InitQuery):
        def query(
            self,
            query: str,
            runtime: Any,
            env: Any,
            messages: Sequence[Any] = (),
            extra_args: dict[str, Any] | None = None,
        ):
            if suite not in SUITE_ALWAYS_ALLOWED_TOOLS:
                raise ValueError("suite is not in the frozen Progent mapping")
            secagent.reset_security_policy(include_human_policy=True)
            secagent.update_available_tools(_tool_descriptors(runtime))
            secagent.update_always_allowed_tools(
                SUITE_ALWAYS_ALLOWED_TOOLS[suite],
                allow_all_no_arg_tools=suite == "banking",
            )
            before = copy.deepcopy(secagent.get_current_config())
            secagent.generate_security_policy(query, manual_check=False)
            _record_policy_transition(
                trace=trace,
                secagent=secagent,
                subset_check=security_policy_subset_check,
                phase="initial",
                before=before,
                source="trusted_user_task_only",
            )
            _install_guarded_runtime(runtime, secagent, trace)
            return super().query(query, runtime, env, messages, dict(extra_args or {}))

    class ProgentToolsExecutorV12(ToolsExecutor):
        def query(
            self,
            query: str,
            runtime: Any,
            env: Any,
            messages: Sequence[Any] = (),
            extra_args: dict[str, Any] | None = None,
        ):
            previous_length = len(messages)
            calls = []
            if messages and messages[-1]["role"] == "assistant":
                for call in messages[-1].get("tool_calls") or []:
                    calls.append({"name": call.function, "args": dict(call.args)})
            result = super().query(query, runtime, env, messages, dict(extra_args or {}))
            updated_messages = result[3]
            if calls and os.getenv("SECAGENT_UPDATE", "False").lower() == "true":
                tool_results = [
                    get_text_content_as_str(message["content"])
                    for message in updated_messages[previous_length:]
                    if message["role"] == "tool"
                ]
                before = copy.deepcopy(secagent.get_current_config())
                try:
                    secagent.generate_update_security_policy(
                        calls, str(tool_results), manual_check=False
                    )
                    _record_policy_transition(
                        trace=trace,
                        secagent=secagent,
                        subset_check=security_policy_subset_check,
                        phase="update",
                        before=before,
                        source="agent_tool_calls_and_tool_outputs",
                    )
                except Exception as exc:
                    trace.record(
                        {
                            "event": "policy_update_error",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "source": "agent_tool_calls_and_tool_outputs",
                        }
                    )
                    if os.getenv("SECAGENT_IGNORE_UPDATE_ERROR", "False").lower() != "true":
                        raise
            return result

    config = PipelineConfig(
        llm=ModelsEnum.OPENAI_COMPATIBLE,
        model_id=str(freeze["model_id"]),
        defense=None,
        tool_delimiter="tool",
        system_message_name=None,
        system_message=None,
        tool_output_format=str(freeze.get("tool_output_format", "yaml")),
    )
    pipeline = AgentPipeline.from_config(config)
    replacements = {"init_query": 0, "tools_executor": 0}
    elements = list(pipeline.elements)
    for index, element in enumerate(elements):
        if type(element).__name__ == "InitQuery":
            elements[index] = ProgentPolicyInitQueryV12()
            replacements["init_query"] += 1
        if isinstance(element, ToolsExecutionLoop):
            loop_elements = list(element.elements)
            for loop_index, loop_element in enumerate(loop_elements):
                if type(loop_element).__name__ == "ToolsExecutor":
                    loop_elements[loop_index] = ProgentToolsExecutorV12(
                        loop_element.output_formatter
                    )
                    replacements["tools_executor"] += 1
            element.elements = loop_elements
    pipeline.elements = elements
    agent_clients = _replace_agent_clients(
        pipeline=pipeline, trace=trace, base_url=base_url
    )
    if agent_clients != 1:
        raise RuntimeError(f"expected one AgentDojo OpenAI client, found {agent_clients}")
    pipeline.name = str(freeze["model_id"]).replace(":", "-") + "-progent-v12"
    pipeline.m3_progent_trace = trace
    pipeline.m3_progent_secagent = secagent
    pipeline.m3_progent_binding = binding
    pipeline.m3_progent_replacements = replacements
    pipeline.m3_progent_agent_clients = agent_clients
    return pipeline


def runtime_contract() -> dict[str, Any]:
    return {
        "runtime_patch_version": PATCH_VERSION,
        "agent_sdk_max_retries": SDK_MAX_RETRIES,
        "policy_sdk_max_retries": SDK_MAX_RETRIES,
        "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "policy_attempt_limit": len(POLICY_TEMPERATURE_SEQUENCE),
        "policy_temperature_sequence": list(POLICY_TEMPERATURE_SEQUENCE),
        "upstream_retry_loop_changed": False,
        "upstream_prompts_changed": False,
        "upstream_policy_enforcement_changed": False,
    }
