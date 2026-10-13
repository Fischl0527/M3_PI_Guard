"""受信任的、非作弊式（Non-Oracle）任务策略契约模块（服务于 Paper-v1/v2 运行时）。

历史上的 M3 运行时直接消费离线评测器（Evaluator）逐案例编写的作弊式授权，
而本模块严格杜绝此项假设。策略清单（TaskPolicyManifest）在接触任何不可信内容之前就已预先编译完成，
且仅能通过附加来自独立确认接口的显式审批凭证（ApprovalRecord）来进行受限扩权。
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
    """返回用于 Paper-v1/v2 策略哈希计算的标准规范化 JSON 字符串表示。"""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    """计算指定对象的规范化 JSON 字符串的 SHA-256 密码学哈希摘要值。"""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ParameterConstraint:
    """单个工具实参的机器可检查约束规格。

    属性:
        kind (str): 约束类型（'any', 'exact', 'enum', 'prefix', 'regex', 'type'）。
        value (Any): 期望值或约束参数。
        required (bool): 该参数是否必填（默认 True）。
        description (str): 参数约束的人类可读说明。
    """

    kind: str
    value: Any = None
    required: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        """验证约束类型与对应参数值的有效性。"""
        if self.kind not in CONSTRAINT_KINDS:
            raise ValueError(f"unsupported constraint kind: {self.kind}")
        if self.kind == "enum" and not isinstance(self.value, (tuple, list)):
            raise ValueError("enum constraints require a list or tuple")

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典对象。"""
        payload = asdict(self)
        if isinstance(payload.get("value"), tuple):
            payload["value"] = list(payload["value"])
        return payload


@dataclass(frozen=True)
class ToolRule:
    """单个工具动作的许可作用域规则（严禁基于评测器离线答案进行授权）。

    属性:
        rule_id (str): 规则唯一标识。
        tool (str): 目标工具名称。
        argument_constraints (Mapping[str, ParameterConstraint]): 参数约束映射表。
        permitted_argument_sources (tuple[str, ...]): 允许的实参数据来源元组。
        requires_confirmation (bool): 是否需要独立人工确认。
        side_effect (bool): 是否具有物理外部副作用。
        description (str): 规则描述。
    """

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
        """将工具规则序列化为字典格式。"""
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
    """拟议工具动作的时序前置条件约束。

    属性:
        constraint_id (str): 约束标识符。
        tool (str): 受约束的工具。
        must_follow_tools (tuple[str, ...]): 在调用该工具前必须已经成功执行的工具序列。
        description (str): 描述说明。
    """

    constraint_id: str
    tool: str
    must_follow_tools: tuple[str, ...]
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "constraint_id": self.constraint_id,
            "tool": self.tool,
            "must_follow_tools": list(self.must_follow_tools),
            "description": self.description,
        }


@dataclass(frozen=True)
class DataFlowConstraint:
    """针对携带特定敏感标签的数据流向特定工具或目标的禁止性约束。

    属性:
        constraint_id (str): 约束标识符。
        data_label (str): 受限数据的敏感标签（如 'confidential', 'pii' 等）。
        forbidden_tools (tuple[str, ...]): 禁止该数据流入的工具名称列表。
        forbidden_target_patterns (tuple[str, ...]): 禁止流入的目标模式（如外部网络或公有邮箱正则）。
        description (str): 约束说明。
    """

    constraint_id: str
    data_label: str
    forbidden_tools: tuple[str, ...] = ()
    forbidden_target_patterns: tuple[str, ...] = ()
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "constraint_id": self.constraint_id,
            "data_label": self.data_label,
            "forbidden_tools": list(self.forbidden_tools),
            "forbidden_target_patterns": list(self.forbidden_target_patterns),
            "description": self.description,
        }


@dataclass(frozen=True)
class ApprovalRecord:
    """由人工或受信任应用确认并签署的策略扩权可审计凭证。

    属性:
        approval_id (str): 审批凭据唯一标识。
        approver_id (str): 审批人或确认通道主体 ID。
        proposal_sha256 (str): 关联的动作提案 SHA-256 哈希值。
        approved_scope (Mapping[str, Any]): 获准扩权的参数或范围规格。
        reason (str): 审批原因或业务上下文。
        approved_at (str): 批准时间戳（ISO-8601）。
        expires_at (str | None): 凭据失效时间戳。
        confirmation_channel (str): 确认通道标识（必须为 'independent_interface'）。
        record_sha256 (str): 该凭证内容的不可变 SHA-256 哈希签名。
    """

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
        """校验审批主体有效性及内容哈希一致性。"""
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
        """序列化审批记录字典。"""
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
    """仅从受信输入编译生成的不可变权限包络（Task Policy Manifest）。

    属性:
        manifest_id (str): 清单唯一标识。
        policy_source (tuple[str, ...]): 策略来源类型元组。
        trusted_request_sha256 (str): 编译来源的原始可信请求哈希。
        tool_schema_sha256 (str): 编译所依据的工具规范 Schema 哈希。
        rules (tuple[ToolRule, ...]): 工具规则列表。
        temporal_constraints (tuple[TemporalConstraint, ...]): 时序约束列表。
        dataflow_constraints (tuple[DataFlowConstraint, ...]): 数据流与敏感标签约束列表。
        sensitive_data_labels (tuple[str, ...]): 当前任务声明的敏感数据标签元组。
        approvals (tuple[ApprovalRecord, ...]): 挂载的独立审批凭证元组。
        version (int): 策略版本号（递增）。
        parent_manifest_sha256 (str | None): 父级清单哈希链指针。
        generated_at (str): 生成时间戳。
        schema_version (str): 模式版本。
        manifest_sha256 (str): 整个清单内容的不可变密码学哈希。
    """

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
        """校验策略来源合法性，并自动计算全清单 SHA-256 哈希值。"""
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
        """将完整策略清单序列化为字典格式。"""
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
        """根据工具名称检索适用的第一条规则；若无对应规则则返回 None。"""
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
    """创建确认凭证证据；禁止使用模型或工具输出的自报身份。"""

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
    """基于经签署的独立审批凭证扩充权限并返回新版本清单；原清单对象保持不可变。"""

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
    """在保持哈希链可追溯的前提下，自动收缩收窄策略清单的许可规则集合。"""

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
