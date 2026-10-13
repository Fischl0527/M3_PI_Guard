"""显式选用的整条规则匹配运行时监视器（保持全局限制与重叠约束的完整性）。

本模块解决历史版本中“参数跨规则拼接”的漏洞：
模型动作提案必须满足单条完整的工具规则（Whole-Rule Matching），同时必须满足所有全局约束；
当存在多条重叠规则时，允许的参数数据来源取交集，确认要求取逻辑“或”（任一规则要求确认即必须确认）。
"""

from __future__ import annotations

# 权限检查的修复主线：先检查全局限制，再寻找一条完整匹配的工具规则。
# “规则甲允许接收者、规则乙允许正文”不能拼成两条都没有授权的新动作。

from dataclasses import replace

from m3_guard.provenance import SOURCE_TYPES
from m3_guard.runtime_monitor import (
    FULL_RUNTIME_MODULES,
    ActionProposal,
    GuardDecision,
    RuntimeMonitor,
    _constraint_matches,
    _make_decision,
    evaluate_action,
)
from m3_guard.task_policy import TaskPolicyManifest, ToolRule

RUNTIME_VERSION = "corrected_v1"


def _matches(proposal: ActionProposal, rule: ToolRule) -> bool:
    """检查动作提案是否满足特定工具规则的所有参数约束。

    参数:
        proposal: 待检查的动作提案（包含工具名称与实际调用参数）。
        rule: 目标工具规则（包含参数约束规范与必填要求）。

    返回:
        bool: 所有必填参数均存在，且所有已提供的受约束参数（包括可选参数）均满足约束时为 True。
    """
    return all(
        (
            not constraint.required
            if name not in proposal.arguments
            else _constraint_matches(proposal.arguments[name], constraint)
        )
        for name, constraint in rule.argument_constraints.items()
    )


def evaluate_action_corrected_v1(
    proposal: ActionProposal,
    manifest: TaskPolicyManifest,
    *,
    modules: frozenset[str] = FULL_RUNTIME_MODULES,
) -> GuardDecision:
    """评估动作提案：动作必须满足单条完整规则并符合所有重叠限制。

    时序/数据流/不可信目标等限制全局适用。参数许可是各规则独立选一的备选项，
    绝不能进行跨规则笛卡尔积拼装。对于重叠的作用域，允许的来源取交集，
    确认要求取逻辑“或（OR）”结合。
    历史审批记录不能授权新的 corrected_v1 执行；独立的、强绑定的、单次有效的
    确认会话是唯一的权限恢复途径。

    参数:
        proposal: 待评估的动作提案。
        manifest: 当前任务的策略清单。
        modules: 启用的运行时防御模块集合（默认启用完整模块 FULL_RUNTIME_MODULES）。

    返回:
        GuardDecision: 包含 ALLOW/ASK/DENY、理由、违规标签及决策审计元数据；不代表工具已执行。
    """
    if proposal.tool == "final":
        return evaluate_action(proposal, manifest, modules=modules)
    global_rule = ToolRule(
        # 内部临时规则仅用于复用全局时序/数据流检查，不是给模型新增许可。
        "corrected-global-check",
        proposal.tool,
        permitted_argument_sources=tuple(sorted(SOURCE_TYPES)),
    )
    global_manifest = replace(
        manifest, rules=(global_rule,), approvals=(), manifest_sha256=""
    )
    global_decision = evaluate_action(
        proposal, global_manifest, modules=modules - {"confirmation"}
    )
    if global_decision.decision != "ALLOW":
        return _make_decision(
            proposal,
            manifest,
            global_decision.decision,
            violated=global_decision.violated_rules,
            evidence=global_decision.evidence_paths,
            reason=global_decision.reason,
            recovery=global_decision.suggested_recovery,
        )
    candidates = sorted(
        # 固定规则顺序只保证结果可重复；不得通过重排绕过更严格的重叠规则。
        (rule for rule in manifest.rules if rule.tool == proposal.tool),
        key=lambda rule: rule.rule_id,
    )
    matches = [rule for rule in candidates if _matches(proposal, rule)]
    if not matches:
        return _make_decision(
            proposal,
            manifest,
            "ASK",
            violated=(
                "no_complete_rule_match"
                if candidates
                else "tool_outside_current_permission",
            ),
            evidence=tuple(f"arguments.{name}" for name in sorted(proposal.arguments)),
            reason="No complete trusted rule authorizes this action and all of its constrained arguments.",
            recovery="Supply a complete narrowly scoped trusted rule; never combine fragments of different rules.",
        )
    sources = set(matches[0].permitted_argument_sources)
    # 多条完整规则同时适用：允许来源取交集，确认要求取“任一需要就需要”。
    for rule in matches[1:]:
        sources.intersection_update(rule.permitted_argument_sources)
    selected = replace(
        matches[0],
        permitted_argument_sources=tuple(sorted(sources)),
        requires_confirmation=any(rule.requires_confirmation for rule in matches),
    )
    narrowed = replace(manifest, rules=(selected,), approvals=(), manifest_sha256="")
    decision = evaluate_action(proposal, narrowed, modules=modules)
    # 对外决策绑定原始完整权限清单，而非内部临时视图，便于定位实际依据。
    return _make_decision(
        proposal,
        manifest,
        decision.decision,
        rule=matches[0],
        violated=decision.violated_rules,
        evidence=decision.evidence_paths,
        reason=decision.reason,
        recovery=decision.suggested_recovery,
    )


class RuntimeMonitorCorrectedV1(RuntimeMonitor):
    """保持相同公共监视器接口的 V1 修复版运行时监视器（由新实验显式选用）。"""

    def decide(self, proposal: ActionProposal) -> GuardDecision:
        """评估动作提案并返回防护决策（由监视器自身维护已执行工具历史）。"""
        # 历史由监视器保存，不相信模型自报“此前已执行哪些工具”。
        proposal = replace(proposal, preceding_tools=self.executed_tools)
        return evaluate_action_corrected_v1(
            proposal, self.manifest, modules=self.modules
        )
