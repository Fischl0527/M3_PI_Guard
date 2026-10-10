"""Prospective monitor: missing trusted sink classification cannot allow effects."""

from __future__ import annotations

# 第二版在完整规则匹配之外接入可信数据分类。
# 缺少必要分类时 ASK（等待确认/补充），不能把“未分类”解释为“公开数据”。

from dataclasses import replace
from typing import Any, Mapping

from m3_guard.provenance_corrected_v1 import TrustedDataLabelTracker
from m3_guard.runtime_monitor import FULL_RUNTIME_MODULES, ActionProposal, GuardDecision, _make_decision
from m3_guard.runtime_monitor_corrected_v1 import RuntimeMonitorCorrectedV1
from m3_guard.task_policy import TaskPolicyManifest
from m3_guard.tool_contracts_v2 import argument_contract_error


class RuntimeMonitorCorrectedV2(RuntimeMonitorCorrectedV1):
    """Same runtime API, with a run-local tracker supplied by the environment."""

    def __init__(
        self, manifest: TaskPolicyManifest, *,
        modules: frozenset[str] = FULL_RUNTIME_MODULES,
        tracker: TrustedDataLabelTracker,
        tool_schemas: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        if not isinstance(tracker, TrustedDataLabelTracker):
            raise TypeError("corrected_v2 requires a trusted run-local classification tracker")
        super().__init__(manifest, modules=modules)
        self.tracker = tracker
        self.tool_schemas = tool_schemas

    def decide(self, proposal: ActionProposal) -> GuardDecision:
        # 顺序检查使用真实已执行历史；参数先满足工具声明的类型和字段要求。
        proposal = replace(proposal, preceding_tools=self.executed_tools)
        error = argument_contract_error(proposal.tool, proposal.arguments, self.tool_schemas) if self.tool_schemas is not None else None
        if error:
            return _make_decision(
                proposal, self.manifest, "DENY", violated=(error,),
                reason="The proposal does not satisfy the declared tool contract.",
                recovery="Provide schema-complete parameters without undeclared targets.",
            )
        decision = super().decide(proposal)
        if (
            decision.decision == "DENY" or proposal.tool == "final" or "dataflow" not in self.modules
            or decision.decision == "ASK" and decision.violated_rules != ("independent_confirmation_required",)
        ):
            return decision
        diagnostic = self.tracker.summarize_dataflow(
            # 分类及标签由隔离环境提供，不读取离线答案，也不采信模型权限声明。
            tool=proposal.tool, arguments=proposal.arguments, events=proposal.provenance,
            constraints=self.manifest.dataflow_constraints,
        )
        if diagnostic["status"] == "missing_input":
            # 人的批准不能替代缺失的数据分类；返回补充分类的恢复建议。
            return _make_decision(
                proposal, self.manifest, "ASK",
                violated=("trusted_data_classification_missing",),
                evidence=("trusted_observation_metadata",),
                reason="A declared protected dataflow reaches a restricted sink without complete trusted classification.",
                recovery="Obtain trusted classification; a model claim or confirmation cannot substitute for it.",
            )
        return decision
