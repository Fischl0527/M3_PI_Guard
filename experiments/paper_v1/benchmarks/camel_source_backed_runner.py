"""Source-backed CaMeL AgentDojo runner wiring helpers.

This module deliberately keeps heavy CaMeL/AgentDojo imports inside functions.
The helpers construct the upstream CaMeL ``PrivilegedLLM`` pipeline shape with a
dry-run LLM object so a preflight can verify source wiring without calling a
model, starting Ollama, touching the network, or executing benchmark cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


RUNNER_VERSION = "m3-paper-v1-camel-source-backed-runner-wiring-0.2"
SUPPORTED_SUITES = ("workspace", "travel", "banking", "slack")
DEFAULT_MODEL_ID = "m3-paper-qwen3-8b-v1:latest"
SUITE_POLICY_ENGINE_CLASS_NAMES = {
    "workspace": "WorkspaceSecurityPolicyEngine",
    "travel": "TravelSecurityPolicyEngine",
    "banking": "BankingSecurityPolicyEngine",
    "slack": "SlackSecurityPolicyEngine",
}


@dataclass(frozen=True)
class CamelPipelineWiring:
    """Serializable metadata for a constructed CaMeL pipeline skeleton."""

    suite: str
    model_id: str
    quarantined_model_id: str
    pipeline_class: str
    pipeline_element_classes: tuple[str, ...]
    privileged_llm_class: str
    privileged_security_policy_engine: str
    dry_run_llm_class: str
    dry_run_llm_query_invoked: bool
    uses_upstream_privileged_llm: bool
    uses_upstream_security_policy: bool
    benchmark_case_executed: bool
    model_or_network_invoked: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "suite": self.suite,
            "model_id": self.model_id,
            "quarantined_model_id": self.quarantined_model_id,
            "pipeline_class": self.pipeline_class,
            "pipeline_element_classes": list(self.pipeline_element_classes),
            "privileged_llm_class": self.privileged_llm_class,
            "privileged_security_policy_engine": self.privileged_security_policy_engine,
            "dry_run_llm_class": self.dry_run_llm_class,
            "dry_run_llm_query_invoked": self.dry_run_llm_query_invoked,
            "uses_upstream_privileged_llm": self.uses_upstream_privileged_llm,
            "uses_upstream_security_policy": self.uses_upstream_security_policy,
            "benchmark_case_executed": self.benchmark_case_executed,
            "model_or_network_invoked": self.model_or_network_invoked,
        }


@dataclass(frozen=True)
class CamelTransportBinding:
    """Serializable record of the frozen local CaMeL model transport."""

    suite: str
    privileged_model_id: str
    quarantined_model_id: str
    privileged_transport: str
    quarantined_transport: str
    base_url: str
    temperature: float
    policy_engine_class: str
    upstream_privileged_llm: bool
    upstream_security_policy: bool
    upstream_interpreter_edited: bool
    upstream_policy_edited: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "suite": self.suite,
            "privileged_model_id": self.privileged_model_id,
            "quarantined_model_id": self.quarantined_model_id,
            "privileged_transport": self.privileged_transport,
            "quarantined_transport": self.quarantined_transport,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "policy_engine_class": self.policy_engine_class,
            "upstream_privileged_llm": self.upstream_privileged_llm,
            "upstream_security_policy": self.upstream_security_policy,
            "upstream_interpreter_edited": self.upstream_interpreter_edited,
            "upstream_policy_edited": self.upstream_policy_edited,
        }


def install_camel_source_path(camel_checkout: Path) -> None:
    """Put the pinned CaMeL checkout on ``sys.path`` for process-local imports."""

    import sys

    source_path = str((camel_checkout / "src").resolve())
    if source_path not in sys.path:
        sys.path.insert(0, source_path)


def build_camel_pipeline_skeleton(
    *,
    suite: str,
    model_id: str = DEFAULT_MODEL_ID,
    quarantined_model_id: str | None = None,
) -> tuple[Any, CamelPipelineWiring]:
    """Construct an upstream CaMeL pipeline skeleton without querying a model.

    The returned pipeline is intentionally not executed by this helper.  It is
    suitable for import/wiring preflights only.  A future formal runner must
    replace the dry-run LLM with a frozen, admitted transport and must execute
    exact frozen AgentDojo cases with complete logs before becoming eligible for
    paper tables.
    """

    if suite not in SUPPORTED_SUITES:
        raise ValueError(f"unsupported CaMeL suite: {suite}")

    from agentdojo import agent_pipeline, functions_runtime
    from camel.pipeline_elements.privileged_llm import PrivilegedLLM
    from camel.pipeline_elements.security_policies import (
        BankingSecurityPolicyEngine,
        SlackSecurityPolicyEngine,
        TravelSecurityPolicyEngine,
        WorkspaceSecurityPolicyEngine,
    )

    class DryRunLLM(agent_pipeline.BasePipelineElement):
        """BasePipelineElement that records accidental execution attempts."""

        name = model_id
        query_invoked = False

        def query(
            self,
            query: str,
            runtime: functions_runtime.FunctionsRuntime,
            env: functions_runtime.TaskEnvironment = functions_runtime.EmptyEnv(),
            messages: list[Any] | tuple[Any, ...] = (),
            extra_args: dict[str, Any] | None = None,
        ) -> tuple[str, functions_runtime.FunctionsRuntime, functions_runtime.TaskEnvironment, list[Any], dict[str, Any]]:
            self.query_invoked = True
            raise RuntimeError("DryRunLLM must not be queried during CaMeL runner preflight")

    policy_engines = {
        "workspace": WorkspaceSecurityPolicyEngine,
        "travel": TravelSecurityPolicyEngine,
        "banking": BankingSecurityPolicyEngine,
        "slack": SlackSecurityPolicyEngine,
    }
    policy_engine = policy_engines[suite]
    dry_llm = DryRunLLM()
    privileged = PrivilegedLLM(
        dry_llm,
        policy_engine,
        quarantined_model_id or model_id,
    )
    pipeline = agent_pipeline.AgentPipeline([agent_pipeline.InitQuery(), privileged])
    elements = tuple(type(element).__name__ for element in pipeline.elements)
    wiring = CamelPipelineWiring(
        suite=suite,
        model_id=model_id,
        quarantined_model_id=quarantined_model_id or model_id,
        pipeline_class=type(pipeline).__name__,
        pipeline_element_classes=elements,
        privileged_llm_class=type(privileged).__name__,
        privileged_security_policy_engine=policy_engine.__name__,
        dry_run_llm_class=type(dry_llm).__name__,
        dry_run_llm_query_invoked=bool(dry_llm.query_invoked),
        uses_upstream_privileged_llm=type(privileged).__module__ == "camel.pipeline_elements.privileged_llm",
        uses_upstream_security_policy=policy_engine.__module__.startswith(
            "camel.pipeline_elements.security_policies."
        ),
        benchmark_case_executed=False,
        model_or_network_invoked=bool(dry_llm.query_invoked),
    )
    return pipeline, wiring


def build_camel_source_backed_pipeline(
    *,
    suite: str,
    transport: Mapping[str, Any],
    privileged_model_id: str = DEFAULT_MODEL_ID,
    quarantined_model_id: str | None = None,
    temperature: float = 0.0,
) -> tuple[Any, CamelTransportBinding]:
    """Build the runnable source-backed CaMeL pipeline for one AgentDojo suite.

    The caller must install :func:`camel_agentdojo_compat.install_agentdojo_suite_import_compat`
    before importing AgentDojo/CaMeL.  Construction is network-free: the
    OpenAI client only contacts the frozen local endpoint when the returned
    pipeline is queried.  CaMeL's interpreter, capability propagation and
    suite policy sources are used without edits.
    """

    if suite not in SUPPORTED_SUITES:
        raise ValueError(f"unsupported CaMeL suite: {suite}")
    base_url = str(transport.get("base_url", "")).rstrip("/")
    if base_url not in {"http://127.0.0.1:11434/v1", "http://localhost:11434/v1"}:
        raise ValueError("CaMeL formal runner requires the frozen local Ollama OpenAI endpoint")
    provider = str(transport.get("provider", ""))
    if provider != "openai-compatible":
        raise ValueError("unsupported CaMeL privileged transport: " + provider)
    quarantined_provider = str(transport.get("quarantined_provider", ""))
    if quarantined_provider != "pydantic-ai-openai-compatible":
        raise ValueError("unsupported CaMeL quarantined transport: " + quarantined_provider)

    import openai
    from agentdojo import agent_pipeline
    from camel.pipeline_elements.privileged_llm import PrivilegedLLM
    from camel.pipeline_elements.security_policies import (
        BankingSecurityPolicyEngine,
        SlackSecurityPolicyEngine,
        TravelSecurityPolicyEngine,
        WorkspaceSecurityPolicyEngine,
    )

    policy_engines = {
        "workspace": WorkspaceSecurityPolicyEngine,
        "travel": TravelSecurityPolicyEngine,
        "banking": BankingSecurityPolicyEngine,
        "slack": SlackSecurityPolicyEngine,
    }
    policy_engine = policy_engines[suite]
    local_api_key = str(transport.get("api_key", "ollama-local"))
    client = openai.OpenAI(base_url=base_url, api_key=local_api_key)
    llm = agent_pipeline.OpenAILLM(
        client,
        privileged_model_id,
        reasoning_effort=None,
        temperature=float(temperature),
    )
    llm.name = privileged_model_id
    quarantined_id = quarantined_model_id or privileged_model_id
    pydantic_ai_model = f"openai:{quarantined_id}"
    privileged = PrivilegedLLM(
        llm,
        policy_engine,
        pydantic_ai_model,
        quarantined_llm_retries=int(transport.get("quarantined_llm_retries", 10)),
        max_attempts=int(transport.get("privileged_max_attempts", 10)),
    )
    pipeline = agent_pipeline.AgentPipeline([agent_pipeline.InitQuery(), privileged])
    safe_model = privileged_model_id.replace(":", "_").replace("/", "_")
    pipeline.name = f"{safe_model}+camel+secpol"
    binding = CamelTransportBinding(
        suite=suite,
        privileged_model_id=privileged_model_id,
        quarantined_model_id=quarantined_id,
        privileged_transport="agentdojo.OpenAILLM(openai-compatible-local)",
        quarantined_transport="pydantic_ai.Agent(openai-compatible-local)",
        base_url=base_url,
        temperature=float(temperature),
        policy_engine_class=policy_engine.__name__,
        upstream_privileged_llm=type(privileged).__module__
        == "camel.pipeline_elements.privileged_llm",
        upstream_security_policy=policy_engine.__module__.startswith(
            "camel.pipeline_elements.security_policies."
        ),
        upstream_interpreter_edited=False,
        upstream_policy_edited=False,
    )
    setattr(pipeline, "m3_camel_transport_binding", binding.as_dict())
    return pipeline, binding
