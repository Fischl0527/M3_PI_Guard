"""显式修正版运行时装配模块（历史实验配置保持原样不变）。

动态装配指定的编译器、监视器与沙箱后端，严格隔离模型与宿主环境。
"""

from __future__ import annotations

# 当前修复版的装配入口：选择编译器/监视器版本，把模型提案交给隔离模拟工具，
# 最后由离线评价器判分。版本必须显式注入，不能全局替换并改变历史实验语义。

import copy
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from experiments.paper_v2.agentdojo_live_dependency import AgentDojoOfflineOutcomeEvaluator
from experiments.paper_v2.boundary_rejection_runtime_v3 import BOUNDARY_REJECTION_REASON, build_boundary_aware_safety_receipt_v3
from experiments.paper_v2.contracts import compute_online_visible_field_digest, sha256_canonical_json
from experiments.paper_v2.correctness_effects_v1 import (
    CorrectedAgentDojoOutcomeEvaluator, CorrectedM3EffectBackend,
    CorrectedM3OutcomeEvaluator,
)
from experiments.paper_v2.exact_target_ablation_v2 import ExactTargetMonitorV2, build_exact_target_authorization_v2
from experiments.paper_v2.formal_condition_executors import (
    ALL_CONDITION_PROFILES, ConditionProfile, OnlineExecutorContext,
)
from experiments.paper_v2.live_condition_runtime import (
    LiveConditionRuntime,
    M3SandboxEffectBackend,
    ProposalCaptureSink,
)
from experiments.paper_v2.medium_runtime import FROZEN_GENERATED_AT, _runtime_inputs, _source_projection, _transform_manifest
from experiments.paper_v2.public_agentdojo_live_dependency_v2 import PublicFrozenAgentDojoCaseResolverV2
from experiments.paper_v2.public_m3_live_dependency_v4 import PublicFrozenM3CaseResolverV4
from experiments.paper_v2.public_matrix_plan_v1 import _read_source_record
from experiments.paper_v2.trusted_context_runtime_v2 import build_research_messages_v2
from m3_core.policy_compiler_corrected_v1 import (
    compile_generic_task_policy_corrected_v1, compile_task_policy_corrected_v1,
)
from m3_core.policy_compiler_corrected_v2 import compile_generic_task_policy_corrected_v2
from m3_core.tool_sandbox import _is_virtual_secret, _normalize_logical_path
from m3_guard.provenance_corrected_v1 import TrustedDataLabelTracker, TrustedObservationMetadata
from m3_guard.runtime_monitor_corrected_v1 import RuntimeMonitorCorrectedV1
from m3_guard.runtime_monitor_corrected_v2 import RuntimeMonitorCorrectedV2
from m3_guard.runtime_monitor import FULL_RUNTIME_MODULES


SAFE_ONLY_PROFILE = ConditionProfile(
    condition_id="safe_prompt_only", controller="unmonitored", max_provider_calls=8,
    m3_prompt_profile="safe_prompt", agentdojo_prompt_profile="safe_prompt",
    dependency="same_safe_prompt_without_runtime_guard",
)

CORRECTED_REGIMES = {"auto_compiled", "exact_target_v2", "broad", "underspecified", "conflicting"}


def profile_for(condition: str) -> ConditionProfile:
    return SAFE_ONLY_PROFILE if condition == "safe_prompt_only" else ALL_CONDITION_PROFILES[condition]


def _compiler(benchmark: str, compiler_revision: str) -> Any:
    if compiler_revision not in {"corrected_v1", "corrected_v2"}:
        raise ValueError("unknown corrected compiler revision")
    if benchmark == "m3-v2":
        return compile_task_policy_corrected_v1
    return compile_generic_task_policy_corrected_v2 if compiler_revision == "corrected_v2" else compile_generic_task_policy_corrected_v1


def compile_manifest(context: OnlineExecutorContext, view: Any, schemas: Any, *, compiler_revision: str = "corrected_v1") -> Any:
    compiler = _compiler(context.benchmark, compiler_revision)
    return compiler(
        trusted_user_request=view.trusted_user_request,
        trusted_app_context=view.trusted_app_context,
        tool_schemas=schemas, generated_at=FROZEN_GENERATED_AT,
    )


def hydrate(work_item: Mapping[str, Any], *, compiler_revision: str = "corrected_v1", authorization_regime: str = "auto_compiled") -> tuple[dict[str, Any], dict[str, Any]]:
    if authorization_regime not in CORRECTED_REGIMES:
        raise ValueError("unsupported corrected authorization regime")
    source = work_item["source_reference"]
    case = {
        "benchmark": work_item["benchmark"], "case_id": work_item["case_id"],
        "source_path": source["path"], "source_line": source["line"],
        "source_record_sha256": source["sha256"],
    }
    record = _read_source_record(case)
    projection = _source_projection(record, str(work_item["benchmark"]))
    # 编译器只接收可信输入投影；离线答案/攻击标签不能进入自动权限编译。
    request, app, schemas = _runtime_inputs(projection, str(work_item["benchmark"]))
    compiler = _compiler(str(work_item["benchmark"]), compiler_revision)
    manifest = compiler(
        trusted_user_request=request, trusted_app_context=app,
        tool_schemas=schemas, generated_at=FROZEN_GENERATED_AT,
    )
    guard_manifest = _transform_manifest(manifest, authorization_regime) if authorization_regime in {"broad", "underspecified", "conflicting"} else manifest
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
                "authorization_regime": authorization_regime,
                "source_class": "online_compiled_authorization",
                "compiler_inputs": ["trusted_user_request", "trusted_app_context", "tool_schemas"],
                "manifest": guard_manifest.to_dict(),
            },
        )
        if authorization_regime == "exact_target_v2":
            # 仅显式oracle对照读离线数据；模型提示仍使用原非oracle清单。
            control["authorization"] = build_exact_target_authorization_v2(record, str(work_item["benchmark"]))
    elif authorization_regime != "auto_compiled":
        raise ValueError("exact target control requires a guarded condition")
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
        # 分类依据是固定测试环境的命名空间，不是模型声明或预期攻击结果。
        # 若隔离层拒绝读取，则没有取得数据，不登记其内容或保密标签。
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


def _execution_summary(event: Mapping[str, Any]) -> tuple[bool | None, bool | None]:
    """绝不将缺少收据的已调度操作转变为安全的零值。"""
    attempted = event.get("execution_attempted")
    observation = event.get("observation")
    rejected = (
        False if attempted is False else None if observation is None or event.get("reason_code") == "runtime_failure" else
        isinstance(observation, Mapping) and observation.get("error") == BOUNDARY_REJECTION_REASON
    )
    if event.get("tool") == "final" or attempted is False:
        executed = False
    elif attempted is not True or observation is None or event.get("reason_code") == "runtime_failure":
        executed = None
    else:
        executed = event.get("execution_succeeded")
    return rejected, executed


def public_events(events: Any) -> list[dict[str, Any]]:
    result = []
    for event in events or []:
        if not isinstance(event, Mapping):
            continue
        isolation_rejected, simulated_action_executed = _execution_summary(event)
        result.append({
            "step": event.get("step"), "tool": event.get("tool"),
            "parse_ok": event.get("parse_ok"), "guard_decision": event.get("decision"),
            "reason_code": event.get("reason_code"),
            "violated_constraints": copy.deepcopy(event.get("violated_constraints", [])),
            "execution_attempted": event.get("execution_attempted"),
            "execution_succeeded": event.get("execution_succeeded"),
            "isolation_rejected": isolation_rejected,
            "simulated_action_executed": simulated_action_executed,
            "proposal_digest": sha256_canonical_json({"tool": event.get("tool"), "arguments": event.get("arguments", {})}),
            "provider_receipt_digest": event.get("provider_receipt_sha256"),
            "corrected_diagnostics": copy.deepcopy(event.get("corrected_diagnostics")),
        })
    return result


class CorrectnessRuntime:
    def __init__(self, *, plan_path: Any, execution_identity: str, compiler_revision: str = "corrected_v1", runtime_revision: str = "corrected_v1", authorization_regime: str = "auto_compiled", vigil_factory: Any = None, proposal_capture_sink: ProposalCaptureSink | None = None, m3_resolver: Any = None) -> None:
        _compiler("agentdojo-v1", compiler_revision)
        self.compiler_revision = compiler_revision
        if runtime_revision not in {"corrected_v1", "corrected_v2"}:
            raise ValueError("unknown corrected runtime revision")
        if authorization_regime not in CORRECTED_REGIMES or authorization_regime != "auto_compiled" and runtime_revision != "corrected_v2":
            raise ValueError("new regimes require the explicit corrected_v2 runtime")
        self.runtime_revision = runtime_revision
        self.authorization_regime = authorization_regime
        self.vigil_factory = vigil_factory
        self.proposal_capture_sink = proposal_capture_sink
        self.agentdojo = PublicFrozenAgentDojoCaseResolverV2(plan_path=plan_path)
        self.m3 = m3_resolver if m3_resolver is not None else PublicFrozenM3CaseResolverV4(plan_path=plan_path, execution_identity=execution_identity)
        self.m3_evaluator = CorrectedM3OutcomeEvaluator(self.m3)
        self.agentdojo_evaluator = CorrectedAgentDojoOutcomeEvaluator(AgentDojoOfflineOutcomeEvaluator(self.agentdojo))

    def execute(self, work_item: Mapping[str, Any], client: Any) -> dict[str, Any]:
        if work_item.get("authorization_regime", "auto_compiled") != self.authorization_regime:
            raise ValueError("work item and repaired authorization regime disagree")
        for field, revision in (("compiler_revision", self.compiler_revision), ("runtime_revision", self.runtime_revision)):
            if work_item.get(field, "corrected_v1") != revision:
                raise ValueError("work item and explicit repaired revision disagree")
        if self.runtime_revision == "corrected_v2" and work_item.get("runtime_version") != "corrected_v2":
            raise ValueError("work item and actual runtime version disagree")
        state, digest = hydrate(work_item, compiler_revision=self.compiler_revision, authorization_regime=self.authorization_regime)
        condition = str(work_item["condition_id"])
        remaining_calls = getattr(client, "max_provider_calls", 8)
        baseline = condition == "strongest_peer_reviewed_structural_baseline"
        ceiling = 16 if baseline and self.vigil_factory is not None else 8
        if baseline and self.vigil_factory is None:
            raise ValueError("VIGIL requires an explicit source-backed factory")
        if type(remaining_calls) is not int or not 1 <= remaining_calls <= ceiling:
            raise ValueError("invalid remaining development request budget")
        context = OnlineExecutorContext(
            execution_identity=str(work_item["execution_identity"]),
            work_key=str(work_item["work_key"]), benchmark=str(work_item["benchmark"]),
            condition_id=condition, max_provider_calls=remaining_calls, online_state=state,
        )

        def backend_factory(context: Any, schemas: Any) -> Any:
            if context.benchmark == "m3-v2":
                return DevelopmentM3Backend(M3SandboxEffectBackend(context))
            return self.agentdojo.build_backend(context, schemas)

        tracker = TrustedDataLabelTracker()
        # 追踪器及工具模式表每个任务独立创建，并发任务不得共享这些可变状态。
        schema_holder = {}

        def manifest_factory(context, view, schemas):
            schema_holder.update(schemas)
            return compile_manifest(context, view, schemas, compiler_revision=self.compiler_revision)

        def oracle_factory(authorization, *, tool_schemas, manifest, modules):
            oracle = ExactTargetMonitorV2(authorization, tool_schemas=tool_schemas)
            oracle.attach_runtime_restrictions(manifest, modules=modules, tracker=tracker)
            return oracle

        def corrected_monitor(manifest, modules):
            # 模型所见提示保持一致；授权制度只改变防护检查范围，防止混杂。
            guard_manifest = _transform_manifest(manifest, self.authorization_regime) if self.authorization_regime in {"broad", "underspecified", "conflicting"} else manifest
            return RuntimeMonitorCorrectedV2(guard_manifest, modules=modules, tracker=tracker, tool_schemas=schema_holder)

        live = LiveConditionRuntime(
            provider_client_factory=lambda context: client,
            effect_backend_factory=backend_factory,
            policy_manifest_factory=manifest_factory,
            monitor_factory=corrected_monitor if self.runtime_revision == "corrected_v2" else RuntimeMonitorCorrectedV1,
            oracle_monitor_factory=oracle_factory if self.authorization_regime == "exact_target_v2" else None,
            provenance_tracker_factory=lambda: tracker,
            proposal_capture_sink=self.proposal_capture_sink,
            vigil_factory=self.vigil_factory if baseline else None,
            safety_receipt_factory=build_boundary_aware_safety_receipt_v3,
            capture_runtime_failures=True,
            message_builder=lambda context, view, schemas, manifest, profile: build_research_messages_v2(
                view, tool_schemas=schemas, manifest=manifest,
                prompt_profile=profile.prompt_profile(context.benchmark),
            ),
            physical_attempt_namespace=client.physical_attempt_namespace,
        )
        before = sha256_canonical_json(state)
        # 故障恢复只用原调用上限中未消耗的部分，不为重试额外增加研究预算。
        # 历史条件配置保持不变，当前剩余上限仅存在于这次任务的实例中。
        profile = replace(profile_for(condition), max_provider_calls=remaining_calls)
        raw = dict(live.execute(context, profile))
        if before != sha256_canonical_json(state):
            raise ValueError("online state mutation")
        evaluator = self.m3_evaluator if context.benchmark == "m3-v2" else self.agentdojo_evaluator
        # 判分在执行之后进行。运行状态、任务完成和危险效果是不同字段，可以并存。
        outcome = evaluator.evaluate(work_item, raw)
        events = public_events(raw.get("events"))
        return {
            **outcome,
            "compiler_revision": self.compiler_revision,
            "runtime_revision": self.runtime_revision,
            "authorization_regime": self.authorization_regime,
            "operational_status": raw["operational_status"],
            "events": events,
            "ask_count": sum(item["guard_decision"] == "ASK" for item in events),
            "deny_count": sum(item["guard_decision"] == "DENY" for item in events),
            "latency_ms": raw["latency_ms"], "token_usage": raw["token_usage"],
            "online_forbidden_fields_present": digest["forbidden_fields_present"],
            "online_visible_field_digest": digest,
            "safety_receipt": raw.get("safety_receipt"),
            **({"vigil_constraint_generation_calls": raw.get("vigil_constraint_generation_calls")} if baseline else {}),
            **{key: raw[key] for key in ("failure_stage", "failure_class", "http_category") if key in raw},
        }
