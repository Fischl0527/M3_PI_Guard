"""Explicit corrected runtime wiring; original experiments remain untouched."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from experiments.paper_v2.agentdojo_live_dependency import AgentDojoOfflineOutcomeEvaluator
from experiments.paper_v2.boundary_rejection_runtime_v3 import build_boundary_aware_safety_receipt_v3
from experiments.paper_v2.contracts import compute_online_visible_field_digest, sha256_canonical_json
from experiments.paper_v2.correctness_effects_v1 import (
    CorrectedAgentDojoOutcomeEvaluator, CorrectedM3EffectBackend,
    CorrectedM3OutcomeEvaluator,
)
from experiments.paper_v2.formal_condition_executors import (
    ALL_CONDITION_PROFILES, ConditionProfile, OnlineExecutorContext,
)
from experiments.paper_v2.live_condition_runtime import LiveConditionRuntime, M3SandboxEffectBackend
from experiments.paper_v2.medium_runtime import FROZEN_GENERATED_AT, _runtime_inputs, _source_projection
from experiments.paper_v2.public_agentdojo_live_dependency_v2 import PublicFrozenAgentDojoCaseResolverV2
from experiments.paper_v2.public_m3_live_dependency_v4 import PublicFrozenM3CaseResolverV4
from experiments.paper_v2.public_matrix_plan_v1 import _read_source_record
from experiments.paper_v2.trusted_context_runtime_v2 import build_research_messages_v2
from m3_core.policy_compiler_corrected_v1 import (
    compile_generic_task_policy_corrected_v1, compile_task_policy_corrected_v1,
)
from m3_core.tool_sandbox import _is_virtual_secret, _normalize_logical_path
from m3_guard.provenance_corrected_v1 import TrustedDataLabelTracker, TrustedObservationMetadata
from m3_guard.runtime_monitor_corrected_v1 import RuntimeMonitorCorrectedV1
from m3_guard.runtime_monitor import FULL_RUNTIME_MODULES


SAFE_ONLY_PROFILE = ConditionProfile(
    condition_id="safe_prompt_only", controller="unmonitored", max_provider_calls=8,
    m3_prompt_profile="safe_prompt", agentdojo_prompt_profile="safe_prompt",
    dependency="same_safe_prompt_without_runtime_guard",
)


def profile_for(condition: str) -> ConditionProfile:
    return SAFE_ONLY_PROFILE if condition == "safe_prompt_only" else ALL_CONDITION_PROFILES[condition]


def compile_manifest(context: OnlineExecutorContext, view: Any, schemas: Any) -> Any:
    compiler = compile_task_policy_corrected_v1 if context.benchmark == "m3-v2" else compile_generic_task_policy_corrected_v1
    return compiler(
        trusted_user_request=view.trusted_user_request,
        trusted_app_context=view.trusted_app_context,
        tool_schemas=schemas, generated_at=FROZEN_GENERATED_AT,
    )


def hydrate(work_item: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    source = work_item["source_reference"]
    case = {
        "benchmark": work_item["benchmark"], "case_id": work_item["case_id"],
        "source_path": source["path"], "source_line": source["line"],
        "source_record_sha256": source["sha256"],
    }
    record = _read_source_record(case)
    projection = _source_projection(record, str(work_item["benchmark"]))
    # Compiler consumes only the projection; offline labels never reach it.
    request, app, schemas = _runtime_inputs(projection, str(work_item["benchmark"]))
    compiler = compile_task_policy_corrected_v1 if work_item["benchmark"] == "m3-v2" else compile_generic_task_policy_corrected_v1
    manifest = compiler(
        trusted_user_request=request, trusted_app_context=app,
        tool_schemas=schemas, generated_at=FROZEN_GENERATED_AT,
    )
    condition = str(work_item["condition_id"])
    profile = profile_for(condition)
    guarded = condition.startswith("m3_")
    control: dict[str, Any] = {
        "condition_id": condition, "prompt_profile": profile.prompt_profile(str(work_item["benchmark"])),
        "guard_mode": "enforce" if guarded else "disabled",
    }
    if guarded:
        control.update(
            guard_modules=["policy"] if condition in {"m3_policy_only", "m3_policy_safe_prompt"} else sorted(FULL_RUNTIME_MODULES),
            authorization={
                "schema_version": "m3-paper-v2-authorization-envelope-1.0",
                "authorization_regime": "auto_compiled",
                "source_class": "online_compiled_authorization",
                "compiler_inputs": ["trusted_user_request", "trusted_app_context", "tool_schemas"],
                "manifest": manifest.to_dict(),
            },
        )
    state = {"agent_input": projection, "runtime_control": control}
    digest = compute_online_visible_field_digest(state)
    if digest["forbidden_fields_present"]:
        raise ValueError("evaluator fields entered corrected online state")
    return state, digest


class DevelopmentM3Backend(CorrectedM3EffectBackend):
    def trusted_observation_metadata(self, tool: str, arguments: Any, observation: Any) -> TrustedObservationMetadata:
        succeeded = not (
            isinstance(observation, Mapping) and observation.get("error")
            or isinstance(observation, str) and observation.startswith("ERROR:")
        ) and observation is not None
        is_data = tool == "read_file" and succeeded
        # Classification is the immutable fixture namespace, never model
        # claims or expected unsafe labels. Existing boundary may reject this
        # virtual sensitive path; a rejected read never registers its content.
        try:
            sensitive = _is_virtual_secret(_normalize_logical_path(str(arguments.get("path", ""))))
        except ValueError:
            sensitive = False
            succeeded = False
            is_data = False
        return TrustedObservationMetadata(
            execution_succeeded=bool(succeeded), observation_is_data=bool(is_data),
            data_labels=("private",) if is_data and sensitive else (),
        )


def public_events(events: Any) -> list[dict[str, Any]]:
    result = []
    for event in events or []:
        if not isinstance(event, Mapping):
            continue
        result.append({
            "step": event.get("step"), "tool": event.get("tool"),
            "parse_ok": event.get("parse_ok"), "guard_decision": event.get("decision"),
            "reason_code": event.get("reason_code"),
            "violated_constraints": copy.deepcopy(event.get("violated_constraints", [])),
            "execution_attempted": event.get("execution_attempted"),
            "execution_succeeded": event.get("execution_succeeded"),
            "proposal_digest": sha256_canonical_json({"tool": event.get("tool"), "arguments": event.get("arguments", {})}),
            "corrected_diagnostics": copy.deepcopy(event.get("corrected_diagnostics")),
        })
    return result


class CorrectnessRuntime:
    def __init__(self, *, plan_path: Any, execution_identity: str) -> None:
        self.agentdojo = PublicFrozenAgentDojoCaseResolverV2(plan_path=plan_path)
        self.m3 = PublicFrozenM3CaseResolverV4(plan_path=plan_path, execution_identity=execution_identity)
        self.m3_evaluator = CorrectedM3OutcomeEvaluator(self.m3)
        self.agentdojo_evaluator = CorrectedAgentDojoOutcomeEvaluator(AgentDojoOfflineOutcomeEvaluator(self.agentdojo))

    def execute(self, work_item: Mapping[str, Any], client: Any) -> dict[str, Any]:
        state, digest = hydrate(work_item)
        condition = str(work_item["condition_id"])
        context = OnlineExecutorContext(
            execution_identity=str(work_item["execution_identity"]),
            work_key=str(work_item["work_key"]), benchmark=str(work_item["benchmark"]),
            condition_id=condition, max_provider_calls=8, online_state=state,
        )

        def backend_factory(context: Any, schemas: Any) -> Any:
            if context.benchmark == "m3-v2":
                return DevelopmentM3Backend(M3SandboxEffectBackend(context))
            return self.agentdojo.build_backend(context, schemas)

        live = LiveConditionRuntime(
            provider_client_factory=lambda context: client,
            effect_backend_factory=backend_factory,
            policy_manifest_factory=compile_manifest,
            monitor_factory=RuntimeMonitorCorrectedV1,
            provenance_tracker_factory=TrustedDataLabelTracker,
            safety_receipt_factory=build_boundary_aware_safety_receipt_v3,
            capture_runtime_failures=True,
            message_builder=lambda context, view, schemas, manifest, profile: build_research_messages_v2(
                view, tool_schemas=schemas, manifest=manifest,
                prompt_profile=profile.prompt_profile(context.benchmark),
            ),
            physical_attempt_namespace=client.physical_attempt_namespace,
        )
        before = sha256_canonical_json(state)
        raw = dict(live.execute(context, profile_for(condition)))
        if before != sha256_canonical_json(state):
            raise ValueError("online state mutation")
        evaluator = self.m3_evaluator if context.benchmark == "m3-v2" else self.agentdojo_evaluator
        outcome = evaluator.evaluate(work_item, raw)
        events = public_events(raw.get("events"))
        return {
            **outcome,
            "operational_status": raw["operational_status"],
            "events": events,
            "ask_count": sum(item["guard_decision"] == "ASK" for item in events),
            "deny_count": sum(item["guard_decision"] == "DENY" for item in events),
            "latency_ms": raw["latency_ms"], "token_usage": raw["token_usage"],
            "online_forbidden_fields_present": digest["forbidden_fields_present"],
            "online_visible_field_digest": digest,
            "safety_receipt": raw.get("safety_receipt"),
            **{key: raw[key] for key in ("failure_stage", "failure_class", "http_category") if key in raw},
        }
