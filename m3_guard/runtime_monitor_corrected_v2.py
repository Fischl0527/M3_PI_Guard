"""前瞻性运行时监视器（V2 修复版）：缺少受信任的数据流信宿分类时禁止产生副作用。

在整条规则匹配（Corrected V1）的基础上，本监视器引入对受信任数据分类（Trusted Classification）的强制闭环：
当受保护的数据流到达受限信宿（Restricted Sink），但缺乏来自受信环境的完整分类元数据时，
系统必须返回 ASK（等待独立确认/补充可信分类），绝不能把“未分类/缺失输入”默认为“公开数据”而静默放行。
"""

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
    """具有受信任数据分类追踪能力的 V2 修复版运行时监视器。

    保持与原 RuntimeMonitor 一致的对外接口，但依赖外部环境传入当前运行局部的
    TrustedDataLabelTracker，以追踪隔离沙箱中真实的观察元数据。
    """

    def __init__(
        self, manifest: TaskPolicyManifest, *,
        modules: frozenset[str] = FULL_RUNTIME_MODULES,
        tracker: TrustedDataLabelTracker,
        tool_schemas: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """初始化 V2 运行时监视器。

        参数:
            manifest: 任务策略清单契约。
            modules: 启用的防御模块集合。
            tracker: 运行局部的可信数据标签追踪器（严禁为 None，必须为 TrustedDataLabelTracker）。
            tool_schemas: 工具参数契约 Schema（用于先验校验参数结构）。
        """
        if not isinstance(tracker, TrustedDataLabelTracker):
            raise TypeError("corrected_v2 requires a trusted run-local classification tracker")
        super().__init__(manifest, modules=modules)
        self.tracker = tracker
        self.tool_schemas = tool_schemas

    def decide(self, proposal: ActionProposal) -> GuardDecision:
        """对动作提案执行全流程决策：参数契约检查 -> 规则匹配 -> 数据流分类审计。

        参数:
            proposal: 动作提案对象。

        返回:
            GuardDecision: 参数契约违规时返回 DENY；缺少完整许可规则或需独立确认时返回 ASK；
                           受限数据流缺少可信分类时也返回 ASK，并附带恢复指引；
                           其余情况保留父类的 ALLOW、ASK 或 DENY 决策。
        """
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
