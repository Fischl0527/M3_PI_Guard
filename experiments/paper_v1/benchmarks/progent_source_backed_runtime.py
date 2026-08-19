"""Source-backed Progent compatibility layer for the frozen AgentDojo v1 universe.

The official Progent checkout vendors AgentDojo 0.1.29, whose v1 security
universe has 589 rather than the 629 cases frozen by this project.  This module
ports the official ``secagent`` policy engine to the project's pinned current
AgentDojo checkout without editing either external repository.  The policy
prompts, JSON-schema enforcement, default-deny behavior, update prompts and Z3
subset implementation remain in the pinned Progent source.

This module only constructs the adapter.  Construction creates OpenAI clients
but performs no model or benchmark request.
"""

from __future__ import annotations

import copy
import os
import sys
import types
from pathlib import Path
from typing import Any, Mapping, Sequence


SUITE_ALWAYS_ALLOWED_TOOLS: dict[str, tuple[str, ...]] = {
    "banking": ("get_most_recent_transactions",),
    "slack": (
        "get_channels",
        "read_channel_messages",
        "read_inbox",
        "get_users_in_channel",
    ),
    "travel": (
        "get_user_information",
        "get_all_hotels_in_city",
        "get_hotels_prices",
        "get_rating_reviews_for_hotels",
        "get_hotels_address",
        "get_all_restaurants_in_city",
        "get_cuisine_type_for_restaurants",
        "get_restaurants_address",
        "get_rating_reviews_for_restaurants",
        "get_dietary_restrictions_for_all_restaurants",
        "get_contact_information_for_restaurants",
        "get_price_for_restaurants",
        "check_restaurant_opening_hours",
        "get_all_car_rental_companies_in_city",
        "get_car_types_available",
        "get_rating_reviews_for_car_rental",
        "get_car_fuel_options",
        "get_car_rental_address",
        "get_car_price_per_day",
        "search_calendar_events",
        "get_day_calendar_events",
        "get_flight_information",
    ),
    "workspace": (
        "get_unread_emails",
        "get_sent_emails",
        "get_received_emails",
        "get_draft_emails",
        "search_emails",
        "search_contacts_by_name",
        "search_contacts_by_email",
        "get_current_day",
        "search_calendar_events",
        "get_day_calendar_events",
        "search_files_by_filename",
        "get_file_by_id",
        "list_files",
        "search_files",
    ),
}


def _module_is_within(module: Any, root: Path) -> bool:
    path = getattr(module, "__file__", None)
    if not path:
        return True
    try:
        Path(path).resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _install_source_paths(agentdojo_checkout: Path, progent_checkout: Path) -> None:
    agentdojo_source = agentdojo_checkout / "src"
    for name, module in list(sys.modules.items()):
        if name == "agentdojo" or name.startswith("agentdojo."):
            if not _module_is_within(module, agentdojo_source):
                raise RuntimeError(
                    "a different AgentDojo checkout is already imported; use a fresh process: "
                    + name
                )
        if name == "secagent" or name.startswith("secagent."):
            if not _module_is_within(module, progent_checkout):
                raise RuntimeError(
                    "a different secagent checkout is already imported; use a fresh process: "
                    + name
                )
    agentdojo_text = str(agentdojo_source.resolve())
    progent_text = str(progent_checkout.resolve())
    if agentdojo_text not in sys.path:
        sys.path.insert(0, agentdojo_text)
    if progent_text not in sys.path:
        sys.path.insert(1, progent_text)


def _tool_descriptors(runtime: Any) -> list[dict[str, Any]]:
    descriptors: list[dict[str, Any]] = []
    for function in sorted(runtime.functions.values(), key=lambda value: value.name):
        schema = function.parameters.model_json_schema()
        properties = copy.deepcopy(schema.get("properties", {}))
        for name, value in list(properties.items()):
            if isinstance(value, Mapping) and "$ref" in value:
                properties.pop(name)
        descriptors.append(
            {
                "name": str(function.name),
                "description": str(function.description),
                "args": properties,
            }
        )
    return descriptors


class ProgentRuntimeTrace:
    """Mutable per-case trace retained by the formal runner."""

    def __init__(self) -> None:
        self.reset("")

    def reset(self, suite: str) -> None:
        self.suite = suite
        self.policy_generation_count = 0
        self.policy_update_attempts = 0
        self.policy_update_errors: list[str] = []
        self.tool_calls: list[dict[str, Any]] = []

    def snapshot(self, secagent: Any) -> dict[str, Any]:
        return {
            "suite": self.suite,
            "policy_generation_count": self.policy_generation_count,
            "policy_update_attempts": self.policy_update_attempts,
            "policy_update_errors": list(self.policy_update_errors),
            "tool_calls": copy.deepcopy(self.tool_calls),
            "allowed_tool_names": sorted(str(row["name"]) for row in secagent.get_allowed_tools()),
            "generated_policy": copy.deepcopy(secagent.get_current_config()),
            "denied_tool_calls": sum(row.get("decision") == "deny" for row in self.tool_calls),
        }


def _bind_policy_transport(
    *,
    secagent_tool: Any,
    base_url: str,
    model_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    import openai

    client = openai.OpenAI(
        api_key="ollama-local",
        base_url=base_url,
        timeout=timeout_seconds,
    )

    def api_request(sys_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model_id,
            temperature=temperature,
            seed=0,
        )
        return str(response.choices[0].message.content or "")

    secagent_tool.api_request = api_request
    # Select the upstream Qwen output-format branch while the compatibility
    # transport maps the logical policy model to the frozen Ollama alias.
    secagent_tool.policy_model = "Qwen/" + model_id
    return {
        "binding": "official_secagent_api_request_to_frozen_openai_compatible_model",
        "base_url": base_url,
        "model_id": model_id,
        "upstream_prompt_format_branch": "Qwen/",
        "prompt_templates_changed": False,
        "policy_enforcement_changed": False,
    }


def _install_guarded_runtime(runtime: Any, secagent: Any, trace: ProgentRuntimeTrace) -> None:
    if getattr(runtime, "__m3_progent_guarded__", False):
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
        }
        try:
            secagent.check_tool_call(function, dict(kwargs))
        except Exception as exc:
            row["decision"] = "deny"
            row["error"] = type(exc).__name__ + ": " + str(exc)
            trace.tool_calls.append(row)
            if raise_on_error:
                raise
            return "", row["error"]
        result, error = original(env, function, kwargs, raise_on_error=raise_on_error)
        row["runtime_error"] = str(error or "")
        trace.tool_calls.append(row)
        return result, error

    runtime.run_function = types.MethodType(guarded, runtime)
    runtime.__m3_progent_guarded__ = True


def build_progent_pipeline(freeze: Mapping[str, Any]):
    """Build the source-backed compatibility pipeline without executing a case."""

    agentdojo_checkout = Path(str(freeze["agentdojo"]["checkout"]))
    progent_checkout = Path(str(freeze["progent"]["checkout"]))
    _install_source_paths(agentdojo_checkout, progent_checkout)

    flags = freeze["progent"]["runtime_flags"]
    for name, value in flags.items():
        os.environ[str(name)] = str(value)
    os.environ["OPENAI_COMPATIBLE_BASE_URL"] = str(freeze["transport"]["base_url"])
    os.environ["OPENAI_COMPATIBLE_API_KEY"] = "ollama-local"

    import secagent
    import secagent.tool as secagent_tool
    from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, PipelineConfig
    from agentdojo.agent_pipeline.basic_elements import InitQuery
    from agentdojo.agent_pipeline.tool_execution import ToolsExecutionLoop, ToolsExecutor
    from agentdojo.models import ModelsEnum
    from agentdojo.types import get_text_content_as_str

    trace = ProgentRuntimeTrace()
    binding = _bind_policy_transport(
        secagent_tool=secagent_tool,
        base_url=str(freeze["transport"]["base_url"]),
        model_id=str(freeze["model_id"]),
        timeout_seconds=float(freeze["transport"].get("timeout_seconds", 180.0)),
    )

    class ProgentPolicyInitQuery(InitQuery):
        def query(
            self,
            query: str,
            runtime: Any,
            env: Any,
            messages: Sequence[Any] = (),
            extra_args: dict[str, Any] | None = None,
        ):
            suite = os.getenv("SECAGENT_SUITE", "")
            if suite not in SUITE_ALWAYS_ALLOWED_TOOLS:
                raise ValueError("SECAGENT_SUITE must name a frozen AgentDojo suite")
            trace.reset(suite)
            secagent.reset_security_policy(include_human_policy=True)
            secagent.update_available_tools(_tool_descriptors(runtime))
            secagent.update_always_allowed_tools(
                SUITE_ALWAYS_ALLOWED_TOOLS[suite],
                allow_all_no_arg_tools=suite == "banking",
            )
            secagent.generate_security_policy(query, manual_check=False)
            trace.policy_generation_count += 1
            _install_guarded_runtime(runtime, secagent, trace)
            return super().query(query, runtime, env, messages, dict(extra_args or {}))

    class ProgentToolsExecutor(ToolsExecutor):
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
                tool_results = []
                for message in updated_messages[previous_length:]:
                    if message["role"] == "tool":
                        tool_results.append(get_text_content_as_str(message["content"]))
                trace.policy_update_attempts += 1
                try:
                    secagent.generate_update_security_policy(
                        calls,
                        str(tool_results),
                        manual_check=False,
                    )
                except Exception as exc:
                    trace.policy_update_errors.append(type(exc).__name__ + ": " + str(exc))
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
            elements[index] = ProgentPolicyInitQuery()
            replacements["init_query"] += 1
        if isinstance(element, ToolsExecutionLoop):
            loop_elements = list(element.elements)
            for loop_index, loop_element in enumerate(loop_elements):
                if type(loop_element).__name__ == "ToolsExecutor":
                    loop_elements[loop_index] = ProgentToolsExecutor(loop_element.output_formatter)
                    replacements["tools_executor"] += 1
            element.elements = loop_elements
    pipeline.elements = elements
    pipeline.name = str(freeze["model_id"]).replace(":", "-") + "-progent-source-backed"
    pipeline.m3_progent_trace = trace
    pipeline.m3_progent_secagent = secagent
    pipeline.m3_progent_binding = binding
    pipeline.m3_progent_replacements = replacements
    return pipeline

