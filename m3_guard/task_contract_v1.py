"""版本化任务契约及有限谓词；不改变历史策略清单的模式。"""

from __future__ import annotations

import copy
import datetime as dt
import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from m3_guard.task_policy import TaskPolicyManifest, ToolRule

DRAFT_SCHEMA_VERSION = "m3-task-contract-draft-1.0"
CONTRACT_SCHEMA_VERSION = "m3-task-contract-1.0"
UNTRUSTED_OBJECT_FIELDS = frozenset({
    "body", "content", "description", "subject", "message", "messages",
    "displayname", "display_name", "instructions", "instruction", "text",
})


def _date(value: Any) -> dt.date | dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        if len(value) == 10:
            return dt.date.fromisoformat(value)
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


@dataclass(frozen=True)
class ContractDiagnostic:
    code: str
    status: str
    action_id: str = ""
    argument: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(code=self.code, status=self.status, action_id=self.action_id,
                    argument=self.argument, detail=self.detail)


@dataclass(frozen=True)
class Predicate:
    """解释等值、有限集合、数值/日期区间及 AND；永不运行表达式。"""

    op: str
    value: Any = None
    values: tuple[Any, ...] = ()
    minimum: Any = None
    maximum: Any = None
    items: tuple[Predicate, ...] = ()
    field: str | None = None

    def matches(self, candidate: Any) -> bool:
        if self.op == "eq":
            return type(candidate) is type(self.value) and candidate == self.value
        if self.op == "in":
            return any(type(candidate) is type(value) and candidate == value for value in self.values)
        if self.op == "number_range":
            return (type(candidate) in {int, float} and math.isfinite(candidate)
                    and (self.minimum is None or candidate >= self.minimum)
                    and (self.maximum is None or candidate <= self.maximum))
        if self.op == "date_range":
            parsed = _date(candidate)
            if parsed is None:
                return False
            try:
                return ((self.minimum is None or parsed >= _date(self.minimum))
                        and (self.maximum is None or parsed <= _date(self.maximum)))
            except TypeError:
                return False
        if self.op == "and":
            return all(item.matches(candidate) for item in self.items)
        if self.op == "type":
            return {"string": isinstance(candidate, str), "integer": type(candidate) is int,
                    "number": type(candidate) in {int, float} and math.isfinite(candidate),
                    "boolean": type(candidate) is bool, "array": isinstance(candidate, list),
                    "object": isinstance(candidate, Mapping), "null": candidate is None}.get(self.value, False)
        return False

    @property
    def fields(self) -> frozenset[str]:
        if self.op == "and":
            return frozenset().union(*(item.fields for item in self.items))
        return frozenset({self.field}) if self.field is not None else frozenset()

    def matches_object(self, obj: VerifiedObject) -> bool:
        if self.op == "and":
            return all(item.matches_object(obj) for item in self.items)
        if self.field in {"id", "object_id"}:
            return self.matches(obj.object_id)
        return self.field in obj.attributes and self.matches(obj.attributes[self.field])

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"op": self.op}
        if self.field is not None:
            result["field"] = self.field
        if self.op in {"eq", "type"}:
            result["value"] = copy.deepcopy(self.value)
        elif self.op == "in":
            result["values"] = list(self.values)
        elif self.op in {"number_range", "date_range"}:
            if self.minimum is not None:
                result["min"] = self.minimum
            if self.maximum is not None:
                result["max"] = self.maximum
        elif self.op == "and":
            result["items"] = [item.to_dict() for item in self.items]
        return result


@dataclass(frozen=True)
class DeferredBinding:
    from_action: str
    object_type: str
    predicate: Predicate
    value_field: str = "id"
    cardinality: str = "one"
    value_format: str | None = None
    filter_field: str | None = None
    static_filter: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(from_action=self.from_action, object_type=self.object_type,
                    predicate=self.predicate.to_dict(), value_field=self.value_field,
                    cardinality=self.cardinality, value_format=self.value_format,
                    filter_field=self.filter_field, static_filter=dict(self.static_filter))


@dataclass(frozen=True)
class EvidenceAnchor:
    quote: str
    start: int
    end: int

    def to_dict(self) -> dict[str, Any]:
        return dict(quote=self.quote, start=self.start, end=self.end)


@dataclass(frozen=True)
class ContractAction:
    action_id: str
    tool: str
    role: str
    constraints: Mapping[str, Predicate]
    evidence: tuple[EvidenceAnchor, ...]
    argument_roles: Mapping[str, str] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    bindings: Mapping[str, DeferredBinding] = field(default_factory=dict)
    requires_confirmation: bool = False
    permitted_argument_sources: tuple[str, ...] = (
        "trusted_user", "trusted_app_context", "model_generated",
        "untrusted_document", "untrusted_tool_output",
    )
    when: tuple[str, Predicate] | None = None

    def __post_init__(self) -> None:
        for name in ("constraints", "argument_roles", "bindings"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

    def to_dict(self) -> dict[str, Any]:
        return dict(action_id=self.action_id, tool=self.tool, role=self.role,
                    constraints={key: value.to_dict() for key, value in self.constraints.items()},
                    evidence=[item.to_dict() for item in self.evidence],
                    argument_roles=dict(self.argument_roles), depends_on=list(self.depends_on),
                    bindings={key: value.to_dict() for key, value in self.bindings.items()},
                    requires_confirmation=self.requires_confirmation,
                    permitted_argument_sources=list(self.permitted_argument_sources),
                    **({"when": {"binding": self.when[0], "predicate": self.when[1].to_dict()}} if self.when else {}))


@dataclass(frozen=True)
class ContractProhibition:
    tool: str
    constraints: Mapping[str, Predicate]
    evidence: tuple[EvidenceAnchor, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraints", MappingProxyType(dict(self.constraints)))

    def to_dict(self) -> dict[str, Any]:
        return dict(tool=self.tool, constraints={key: value.to_dict() for key, value in self.constraints.items()},
                    evidence=[item.to_dict() for item in self.evidence])


@dataclass(frozen=True)
class TaskContractV1:
    static_manifest: TaskPolicyManifest
    actions: tuple[ContractAction, ...] = ()
    prohibitions: tuple[ContractProhibition, ...] = ()
    diagnostics: tuple[ContractDiagnostic, ...] = ()
    status: str = "ready"
    schema_version: str = CONTRACT_SCHEMA_VERSION
    lexical_manifest: TaskPolicyManifest | None = None
    application_scope: tuple[ToolRule, ...] | None = None
    application_constraints: Mapping[str, Mapping[str, Predicate]] = field(default_factory=dict)
    prohibit_external_recipients: bool = False
    data_flow_policy: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "application_constraints", MappingProxyType({
            tool: MappingProxyType(dict(constraints)) for tool, constraints in self.application_constraints.items()
        }))

    def to_dict(self) -> dict[str, Any]:
        return dict(schema_version=self.schema_version, status=self.status,
                    static_manifest=self.static_manifest.to_dict(),
                    actions=[item.to_dict() for item in self.actions],
                    prohibitions=[item.to_dict() for item in self.prohibitions],
                    diagnostics=[item.to_dict() for item in self.diagnostics],
                    lexical_manifest=self.lexical_manifest.to_dict() if self.lexical_manifest else None,
                    application_scope=[rule.to_dict() for rule in self.application_scope] if self.application_scope is not None else None,
                    application_constraints={tool: {name: predicate.to_dict() for name, predicate in constraints.items()} for tool, constraints in self.application_constraints.items()},
                    prohibit_external_recipients=self.prohibit_external_recipients,
                    data_flow_policy=dict(self.data_flow_policy))


@dataclass(frozen=True)
class VerifiedObject:
    """仅受信任后端可构造；还需解析器固定白名单和当前状态双重核对。"""

    object_type: str
    object_id: str
    attributes: Mapping[str, Any]
    verified_fields: frozenset[str]
    current: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", MappingProxyType(copy.deepcopy(dict(self.attributes))))
        object.__setattr__(self, "verified_fields", frozenset(self.verified_fields))


@dataclass(frozen=True)
class BindingResolution:
    status: str
    objects: tuple[VerifiedObject, ...] = ()
    complete: bool = True
    reason_code: str = ""


class TrustedBindingResolver(Protocol):
    def trusted_fields(self, object_type: str) -> frozenset[str]: ...

    def resolve(self, binding: DeferredBinding, *, candidate_value: Any,
                successful_actions: tuple[str, ...]) -> BindingResolution: ...
