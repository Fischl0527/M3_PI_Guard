"""Opt-in whole-rule matching with global and overlapping restrictions intact."""

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
    """An action must satisfy one complete rule and every overlapping restriction.

    Temporal/dataflow/untrusted-target restrictions apply globally. Parameter
    grants are alternatives, never a cross-product. For scopes that overlap,
    permitted sources intersect and confirmation requirements are OR-combined.
    Old approval records cannot authorize new corrected_v1 executions; the
    independent, bound, one-shot confirmation session is the only recovery path.
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
    """Same public monitor interface, explicitly selected by new experiments."""

    def decide(self, proposal: ActionProposal) -> GuardDecision:
        # 历史由监视器保存，不相信模型自报“此前已执行哪些工具”。
        proposal = replace(proposal, preceding_tools=self.executed_tools)
        return evaluate_action_corrected_v1(
            proposal, self.manifest, modules=self.modules
        )
