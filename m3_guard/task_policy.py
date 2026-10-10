"""Trusted, non-oracle task policy contracts for the paper-v1 runtime.

The historical M3 runtime consumes evaluator-authored per-case authorization.
This module deliberately does not.  A :class:`TaskPolicyManifest` is compiled
before any untrusted content is observed and can only be expanded by attaching
an explicit approval record from an independent confirmation interface.
"""

from __future__ import annotations

# 公共数据契约：ParameterConstraint 约束一个参数，ToolRule 约束完整动作，
# TaskPolicyManifest 汇总可信任务权限。字段名是稳定接口，不随中文文档重命名。
# 本文件同时服务历史路径；修复版通过显式编译器/监视器选择，不能混用批准语义。

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


POLICY_SCHEMA_VERSION = "1.0"
POLICY_SOURCE_KINDS = frozenset(
    {"trusted_user_request", "trusted_application_context", "independent_confirmation"}
)
CONSTRAINT_KINDS = frozenset({"any", "exact", "enum", "prefix", "regex", "type"})


def canonical_json(value: Any) -> str:
    """Return the stable JSON representation used by every paper-v1 hash."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ParameterConstraint:
    """A machine-checkable constraint over one tool argument."""

    kind: str
    value: Any = None
    required: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        if self.kind not in CONSTRAINT_KINDS:
            raise ValueError(f"unsupported constraint kind: {self.kind}")
        if self.kind == "enum" and not isinstance(self.value, (tuple, list)):
            raise ValueError("enum constraints require a list or tuple")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if isinstance(payload.get("value"), tuple):
            payload["value"] = list(payload["value"])
        return payload


@dataclass(frozen=True)
class ToolRule:
    """The permitted scope of one tool action, never an evaluator answer."""

    rule_id: str
    tool: str
    argument_constraints: Mapping[str, ParameterConstraint] = field(default_factory=dict)
    permitted_argument_sources: tuple[str, ...] = (
        "trusted_user",
        "trusted_app_context",
        "model_generated",
        "untrusted_document",
        "untrusted_tool_output",
    )
    requires_confirmation: bool = False
    side_effect: bool = False
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "tool": self.tool,
            "argument_constraints": {
                key: value.to_dict()
                for key, value in sorted(self.argument_constraints.items())
            },
            "permitted_argument_sources": list(self.permitted_argument_sources),
            "requires_confirmation": self.requires_confirmation,
            "side_effect": self.side_effect,
            "description": self.description,
        }


@dataclass(frozen=True)
class TemporalConstraint:
    """An ordering prerequisite for a proposed tool action."""

    constraint_id: str
    tool: str
    must_follow_tools: tuple[str, ...]
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "tool": self.tool,
            "must_follow_tools": list(self.must_follow_tools),
            "description": self.description,
        }


@dataclass(frozen=True)
class DataFlowConstraint:
    """A prohibition on a labelled value reaching a tool or destination."""

    constraint_id: str
    data_label: str
    forbidden_tools: tuple[str, ...] = ()
    forbidden_target_patterns: tuple[str, ...] = ()
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "data_label": self.data_label,
            "forbidden_tools": list(self.forbidden_tools),
            "forbidden_target_patterns": list(self.forbidden_target_patterns),
            "description": self.description,
        }


@dataclass(frozen=True)
class ApprovalRecord:
    """Auditable evidence that a human/application approved policy expansion."""

    approval_id: str
    approver_id: str
    proposal_sha256: str
    approved_scope: Mapping[str, Any]
    reason: str
    approved_at: str
    expires_at: str | None = None
    confirmation_channel: str = "independent_interface"
    record_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.approver_id.strip():
            raise ValueError("approval requires a non-empty approver_id")
        if self.confirmation_channel != "independent_interface":
            raise ValueError("policy expansion requires the independent confirmation interface")
        payload = self.to_dict(include_hash=False)
        expected = sha256_json(payload)
        if self.record_sha256 and self.record_sha256 != expected:
            raise ValueError("approval record hash does not match its content")
        if not self.record_sha256:
            object.__setattr__(self, "record_sha256", expected)

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = {
            "approval_id": self.approval_id,
            "approver_id": self.approver_id,
            "proposal_sha256": self.proposal_sha256,
            "approved_scope": dict(self.approved_scope),
            "reason": self.reason,
            "approved_at": self.approved_at,
            "expires_at": self.expires_at,
            "confirmation_channel": self.confirmation_channel,
        }
        if include_hash:
            payload["record_sha256"] = self.record_sha256
        return payload


@dataclass(frozen=True)
class TaskPolicyManifest:
    """Immutable permission envelope compiled from trusted inputs only."""

    manifest_id: str
    policy_source: tuple[str, ...]
    trusted_request_sha256: str
    tool_schema_sha256: str
    rules: tuple[ToolRule, ...]
    temporal_constraints: tuple[TemporalConstraint, ...] = ()
    dataflow_constraints: tuple[DataFlowConstraint, ...] = ()
    sensitive_data_labels: tuple[str, ...] = ()
    approvals: tuple[ApprovalRecord, ...] = ()
    version: int = 1
    parent_manifest_sha256: str | None = None
    generated_at: str = ""
    schema_version: str = POLICY_SCHEMA_VERSION
    manifest_sha256: str = ""

    def __post_init__(self) -> None:
        invalid = set(self.policy_source) - POLICY_SOURCE_KINDS
        if invalid:
            raise ValueError(f"untrusted policy source(s): {sorted(invalid)}")
        if self.version < 1:
            raise ValueError("policy version must be positive")
        generated_at = self.generated_at or datetime.now(timezone.utc).isoformat()
        if not self.generated_at:
            object.__setattr__(self, "generated_at", generated_at)
        payload = self.to_dict(include_hash=False)
        expected = sha256_json(payload)
        if self.manifest_sha256 and self.manifest_sha256 != expected:
            raise ValueError("manifest hash does not match its content")
        if not self.manifest_sha256:
            object.__setattr__(self, "manifest_sha256", expected)

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "policy_source": list(self.policy_source),
            "trusted_request_sha256": self.trusted_request_sha256,
            "tool_schema_sha256": self.tool_schema_sha256,
            "rules": [rule.to_dict() for rule in self.rules],
            "temporal_constraints": [item.to_dict() for item in self.temporal_constraints],
            "dataflow_constraints": [item.to_dict() for item in self.dataflow_constraints],
            "sensitive_data_labels": list(self.sensitive_data_labels),
            "approvals": [item.to_dict() for item in self.approvals],
            "version": self.version,
            "parent_manifest_sha256": self.parent_manifest_sha256,
            "generated_at": self.generated_at,
        }
        if include_hash:
            payload["manifest_sha256"] = self.manifest_sha256
        return payload

    def rule_for(self, tool: str) -> ToolRule | None:
        return next((rule for rule in self.rules if rule.tool == tool), None)


def create_approval_record(
    *,
    approval_id: str,
    approver_id: str,
    proposal: Mapping[str, Any],
    approved_scope: Mapping[str, Any],
    reason: str,
    expires_at: str | None = None,
    approved_at: str | None = None,
) -> ApprovalRecord:
    """Create confirmation evidence without using model or tool-output identity."""

    return ApprovalRecord(
        approval_id=approval_id,
        approver_id=approver_id,
        proposal_sha256=sha256_json(dict(proposal)),
        approved_scope=dict(approved_scope),
        reason=reason,
        approved_at=approved_at or datetime.now(timezone.utc).isoformat(),
        expires_at=expires_at,
    )


def expand_manifest(
    manifest: TaskPolicyManifest,
    *,
    approval: ApprovalRecord,
    new_rules: Iterable[ToolRule],
) -> TaskPolicyManifest:
    """Return a new manifest version; the original object remains unchanged."""

    if not approval.record_sha256:
        raise ValueError("policy expansion requires a hashed approval record")
    rules = tuple(manifest.rules) + tuple(new_rules)
    return replace(
        manifest,
        manifest_id=f"{manifest.manifest_id}-v{manifest.version + 1}",
        policy_source=tuple(
            dict.fromkeys((*manifest.policy_source, "independent_confirmation"))
        ),
        rules=rules,
        approvals=tuple(manifest.approvals) + (approval,),
        version=manifest.version + 1,
        parent_manifest_sha256=manifest.manifest_sha256,
        generated_at=datetime.now(timezone.utc).isoformat(),
        manifest_sha256="",
    )


def narrow_manifest(
    manifest: TaskPolicyManifest,
    *,
    retained_rule_ids: Iterable[str],
) -> TaskPolicyManifest:
    """Automatically narrow permissions while preserving a hash chain."""

    retained = set(retained_rule_ids)
    rules = tuple(rule for rule in manifest.rules if rule.rule_id in retained)
    if len(rules) == len(manifest.rules):
        return manifest
    return replace(
        manifest,
        manifest_id=f"{manifest.manifest_id}-v{manifest.version + 1}",
        rules=rules,
        version=manifest.version + 1,
        parent_manifest_sha256=manifest.manifest_sha256,
        generated_at=datetime.now(timezone.utc).isoformat(),
        manifest_sha256="",
    )
