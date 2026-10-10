"""Stateful provenance-aware ALLOW/ASK/DENY monitor for paper-v1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from .provenance import (
    GENERIC_SELECTOR_FIELDS,
    ProvenanceEvent,
    labels_in_proposal,
    proposal_has_untrusted_target,
    provenance_uses_instruction_field,
)
from .task_policy import (
    ApprovalRecord,
    ParameterConstraint,
    TaskPolicyManifest,
    ToolRule,
    sha256_json,
)


DECISIONS = frozenset({"ALLOW", "ASK", "DENY"})
FULL_RUNTIME_MODULES = frozenset(
    {"policy", "provenance", "temporal", "dataflow", "confirmation"}
)


@dataclass(frozen=True)
class ActionProposal:
    proposal_id: str
    tool: str
    arguments: Mapping[str, Any]
    provenance: tuple[ProvenanceEvent, ...]
    preceding_tools: tuple[str, ...] = ()
    step: int = 1

    @property
    def proposal_sha256(self) -> str:
        return sha256_json(
            {
                "proposal_id": self.proposal_id,
                "tool": self.tool,
                "arguments": dict(self.arguments),
                "preceding_tools": list(self.preceding_tools),
                "step": self.step,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "proposal_sha256": self.proposal_sha256,
            "tool": self.tool,
            "arguments": dict(self.arguments),
            "provenance": [event.to_dict() for event in self.provenance],
            "preceding_tools": list(self.preceding_tools),
            "step": self.step,
        }


@dataclass(frozen=True)
class GuardDecision:
    decision: str
    decision_id: str
    proposal_sha256: str
    manifest_sha256: str
    rule_id: str | None
    violated_rules: tuple[str, ...]
    evidence_paths: tuple[str, ...]
    reason: str
    suggested_recovery: str
    decided_at: str

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise ValueError(f"unsupported Guard decision: {self.decision}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "decision_id": self.decision_id,
            "proposal_sha256": self.proposal_sha256,
            "manifest_sha256": self.manifest_sha256,
            "rule_id": self.rule_id,
            "violated_rules": list(self.violated_rules),
            "evidence_paths": list(self.evidence_paths),
            "reason": self.reason,
            "suggested_recovery": self.suggested_recovery,
            "decided_at": self.decided_at,
        }


def _make_decision(
    proposal: ActionProposal,
    manifest: TaskPolicyManifest,
    decision: str,
    *,
    rule: ToolRule | None = None,
    violated: Iterable[str] = (),
    evidence: Iterable[str] = (),
    reason: str,
    recovery: str,
) -> GuardDecision:
    payload = {
        "proposal_sha256": proposal.proposal_sha256,
        "manifest_sha256": manifest.manifest_sha256,
        "decision": decision,
        "violated": list(violated),
        "evidence": list(evidence),
    }
    return GuardDecision(
        decision=decision,
        decision_id=f"decision-{sha256_json(payload)[:20]}",
        proposal_sha256=proposal.proposal_sha256,
        manifest_sha256=manifest.manifest_sha256,
        rule_id=rule.rule_id if rule else None,
        violated_rules=tuple(violated),
        evidence_paths=tuple(evidence),
        reason=reason,
        suggested_recovery=recovery,
        decided_at=datetime.now(timezone.utc).isoformat(),
    )


def _constraint_matches(value: Any, constraint: ParameterConstraint) -> bool:
    if constraint.kind == "any":
        return True
    if constraint.kind == "exact":
        return value == constraint.value
    if constraint.kind == "enum":
        return value in constraint.value
    if constraint.kind == "prefix":
        return isinstance(value, str) and value.startswith(str(constraint.value))
    if constraint.kind == "regex":
        return isinstance(value, str) and re.fullmatch(str(constraint.value), value) is not None
    if constraint.kind == "type":
        expected = str(constraint.value)
        return {
            "string": isinstance(value, str),
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
        }.get(expected, False)
    return False


def _top_level_argument(path: str) -> str:
    return path.removeprefix("arguments.").split(".", 1)[0].split("[", 1)[0]


def _approval_matches(approval: ApprovalRecord, proposal: ActionProposal) -> bool:
    if approval.proposal_sha256 == proposal.proposal_sha256:
        return True
    scope = approval.approved_scope
    if scope.get("tool") != proposal.tool:
        return False
    approved_arguments = scope.get("arguments")
    return not isinstance(approved_arguments, Mapping) or all(
        proposal.arguments.get(key) == value for key, value in approved_arguments.items()
    )


def _targets(arguments: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("path", "to", "endpoint"):
        value = arguments.get(key)
        if value is not None:
            values.append(str(value))
    return tuple(values)


def evaluate_action(
    proposal: ActionProposal,
    manifest: TaskPolicyManifest,
    *,
    modules: frozenset[str] = FULL_RUNTIME_MODULES,
) -> GuardDecision:
    """Evaluate one proposal against current authority and trace state."""

    unknown_modules = set(modules) - FULL_RUNTIME_MODULES
    if unknown_modules:
        raise ValueError(f"unknown runtime monitor modules: {sorted(unknown_modules)}")
    if "policy" not in modules:
        raise ValueError("the policy module is mandatory when the runtime monitor is enabled")

    if proposal.tool == "final":
        return _make_decision(
            proposal,
            manifest,
            "ALLOW",
            reason="Final text has no monitored external side effect.",
            recovery="none",
        )

    rule = manifest.rule_for(proposal.tool)
    untrusted_target = proposal_has_untrusted_target(proposal.tool, proposal.provenance)
    if rule is None:
        if "provenance" in modules and untrusted_target:
            evidence = tuple(
                event.argument_path
                for event in proposal.provenance
                if event.trust_level == "untrusted"
            )
            return _make_decision(
                proposal,
                manifest,
                "DENY",
                violated=("untrusted_content_cannot_create_permission",),
                evidence=evidence,
                reason="An untrusted source introduced a target outside the task policy.",
                recovery="Ignore the untrusted instruction and continue within the existing task.",
            )
        return _make_decision(
            proposal,
            manifest,
            "ASK",
            violated=("tool_outside_current_permission",),
            reason="The action may serve the task but requires permission expansion.",
            recovery="Request independent user confirmation for a narrowly scoped rule.",
        )

    if "provenance" in modules:
        instruction_driven_selectors = tuple(
            event
            for event in proposal.provenance
            if _top_level_argument(event.argument_path) in GENERIC_SELECTOR_FIELDS
            and provenance_uses_instruction_field(event)
        )
        if instruction_driven_selectors:
            return _make_decision(
                proposal,
                manifest,
                "DENY",
                rule=rule,
                violated=("instruction_field_cannot_drive_action_selector",),
                evidence=tuple(event.argument_path for event in instruction_driven_selectors),
                reason=(
                    "A selector for a new tool action came from an instruction-bearing "
                    "field in an untrusted tool result."
                ),
                recovery="Continue using task-relevant structured data fields only.",
            )

    for temporal in manifest.temporal_constraints if "temporal" in modules else ():
        if temporal.tool != proposal.tool:
            continue
        missing = [tool for tool in temporal.must_follow_tools if tool not in proposal.preceding_tools]
        if missing:
            return _make_decision(
                proposal,
                manifest,
                "DENY",
                rule=rule,
                violated=(temporal.constraint_id,),
                evidence=("trace.preceding_tools",),
                reason=f"Required predecessor action(s) are missing: {', '.join(missing)}.",
                recovery="Complete the trusted prerequisite before retrying the action.",
            )

    labels = labels_in_proposal(proposal.provenance)
    for dataflow in manifest.dataflow_constraints if "dataflow" in modules else ():
        if dataflow.data_label not in labels:
            continue
        forbidden_tool = proposal.tool in dataflow.forbidden_tools
        forbidden_target = any(
            re.search(pattern, target, flags=re.IGNORECASE)
            for pattern in dataflow.forbidden_target_patterns
            for target in _targets(proposal.arguments)
        )
        if forbidden_tool or forbidden_target:
            return _make_decision(
                proposal,
                manifest,
                "DENY",
                rule=rule,
                violated=(dataflow.constraint_id,),
                evidence=tuple(
                    event.argument_path
                    for event in proposal.provenance
                    if dataflow.data_label in event.data_labels
                ),
                reason=f"Data labelled {dataflow.data_label!r} cannot flow to this action.",
                recovery="Remove the protected data or select an explicitly authorized destination.",
            )

    if "provenance" in modules and untrusted_target:
        return _make_decision(
            proposal,
            manifest,
            "DENY",
            rule=rule,
            violated=("untrusted_target_introduction",),
            evidence=tuple(
                event.argument_path
                for event in proposal.provenance
                if event.trust_level == "untrusted"
            ),
            reason="Untrusted content attempted to choose the action target.",
            recovery="Use only the destination explicitly supplied by the trusted requester.",
        )

    for event in proposal.provenance if "provenance" in modules else ():
        if event.source_type not in rule.permitted_argument_sources:
            decision = "DENY" if event.trust_level == "untrusted" else "ASK"
            return _make_decision(
                proposal,
                manifest,
                decision,
                rule=rule,
                violated=("argument_source_not_permitted",),
                evidence=(event.argument_path,),
                reason=f"Argument source {event.source_type!r} is outside the rule scope.",
                recovery=(
                    "Remove the untrusted value."
                    if decision == "DENY"
                    else "Request a trusted value or independent confirmation."
                ),
            )

    for name, constraint in rule.argument_constraints.items():
        if name not in proposal.arguments:
            if constraint.required:
                return _make_decision(
                    proposal,
                    manifest,
                    "ASK",
                    rule=rule,
                    violated=(f"missing_argument:{name}",),
                    evidence=(f"arguments.{name}",),
                    reason=f"Required argument {name!r} is missing.",
                    recovery="Ask the trusted requester to supply the missing parameter.",
                )
            continue
        if not _constraint_matches(proposal.arguments[name], constraint):
            return _make_decision(
                proposal,
                manifest,
                "ASK",
                rule=rule,
                violated=(f"constraint_mismatch:{name}",),
                evidence=(f"arguments.{name}",),
                reason=f"Argument {name!r} falls outside the current permission scope.",
                recovery="Request independent confirmation for the exact new value.",
            )

    if "confirmation" in modules and rule.requires_confirmation and not any(
        _approval_matches(approval, proposal) for approval in manifest.approvals
    ):
        return _make_decision(
            proposal,
            manifest,
            "ASK",
            rule=rule,
            violated=("independent_confirmation_required",),
            reason="The compiled task was ambiguous and this side effect requires confirmation.",
            recovery="Approve or reject the exact proposal through the independent interface.",
        )

    return _make_decision(
        proposal,
        manifest,
        "ALLOW",
        rule=rule,
        reason="The proposal is within the trusted task policy and data-flow constraints.",
        recovery="none",
    )


def allow_unmonitored(
    proposal: ActionProposal,
    manifest: TaskPolicyManifest,
) -> GuardDecision:
    """Return an auditable ALLOW for an explicitly configured no-Guard baseline."""

    return _make_decision(
        proposal,
        manifest,
        "ALLOW",
        reason="No online monitor is enabled for this declared baseline condition.",
        recovery="none",
    )


class RuntimeMonitor:
    """Small state holder that records only successfully executed actions."""

    def __init__(
        self,
        manifest: TaskPolicyManifest,
        *,
        modules: frozenset[str] = FULL_RUNTIME_MODULES,
    ) -> None:
        self.manifest = manifest
        if "policy" not in modules or set(modules) - FULL_RUNTIME_MODULES:
            raise ValueError("invalid runtime monitor module set")
        self.modules = modules
        self._executed_tools: list[str] = []

    @property
    def executed_tools(self) -> tuple[str, ...]:
        return tuple(self._executed_tools)

    def decide(self, proposal: ActionProposal) -> GuardDecision:
        if proposal.preceding_tools != self.executed_tools:
            proposal = ActionProposal(
                proposal_id=proposal.proposal_id,
                tool=proposal.tool,
                arguments=proposal.arguments,
                provenance=proposal.provenance,
                preceding_tools=self.executed_tools,
                step=proposal.step,
            )
        return evaluate_action(proposal, self.manifest, modules=self.modules)

    def record_execution(self, proposal: ActionProposal, decision: GuardDecision) -> None:
        # 调用者必须先确认模拟执行成功；ALLOW 自身不是执行成功的证据。
        if decision.decision != "ALLOW":
            raise ValueError("only allowed actions may enter the execution trace")
        if proposal.tool != "final":
            self._executed_tools.append(proposal.tool)

    def update_manifest(self, manifest: TaskPolicyManifest) -> None:
        if manifest.parent_manifest_sha256 != self.manifest.manifest_sha256:
            raise ValueError("manifest update does not extend the current hash chain")
        self.manifest = manifest
