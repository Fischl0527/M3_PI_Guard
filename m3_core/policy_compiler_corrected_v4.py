"""受限任务意图的确定性物化；模型不生成权限谓词或可信证明。"""
from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, replace
from typing import Any, Mapping

from m3_core import policy_compiler as legacy
from m3_core.policy_compiler_corrected_v2 import compile_generic_task_policy_corrected_v2
from m3_core.policy_compiler_corrected_v3 import _INTENTS, _execution_evidence, _validate_constraint_type
from m3_guard.task_contract_v1 import (
    ContractAction, ContractDiagnostic, ContractProhibition, DeferredBinding,
    EvidenceAnchor, Predicate, TaskContractV1, UNTRUSTED_OBJECT_FIELDS,
)
from m3_guard.task_policy import ParameterConstraint, ToolRule

COMPILER_VERSION = "corrected_v4"
INTENT_SCHEMA_VERSION = "m3-task-intent-1.0"
CATALOG_SCHEMA_VERSION = "m3-trusted-tool-catalog-1.0"
_OPERATIONS = {"discover", "read", "modify", "create", "send", "delete", "confirm"}
_ROLES = {"target", "content", "query", "value"}
_META = {"id", "object_id", "kind", "owner", "project_id", "status", "category",
         "classification", "parent_id", "role", "email", "internal", "ready", "member_of",
         "slot_start", "slot_end", "duration_minutes", "filename", "name", "sender", "recipients",
         "participants", "start_time", "end_time", "date", "timestamp", "version", "account",
         "recipient", "amount", "currency", "channel_id", "user_id", "members", "active"}
_OBJECTS = {"file", "contact", "project", "calendar_event", "record", "folder", "ticket",
            "approval_record", "private_file", "object", "email", "event", "channel", "user", "transaction"}
_NATIVE_OUTPUTS = {
    "search_emails": "email", "get_email": "email", "get_unread_emails": "email",
    "get_received_emails": "email", "get_sent_emails": "email", "get_draft_emails": "email",
    "search_files": "file", "search_files_by_filename": "file", "list_files": "file",
    "get_file": "file", "get_file_by_id": "file", "read_file": "file",
    "search_contacts": "contact", "get_contact": "contact", "search_contacts_by_email": "contact",
    "search_contacts_by_name": "contact", "get_day_calendar_events": "event",
    "search_calendar_events": "event", "get_calendar_events": "event", "get_event": "event",
    "get_channels": "channel", "get_all_channels": "channel", "get_channel_info": "channel",
    "get_users_in_channel": "user", "get_user_info": "user", "get_user_information": "user",
    "get_most_recent_transactions": "transaction", "get_recent_transactions": "transaction",
    "get_scheduled_transactions": "transaction",
}
_KNOWN_ROLES = {
    "read_file": ("read", {"path": "target"}),
    "write_file": ("modify", {"path": "target", "content": "content"}),
    "send_email": ("send", {"to": "target", "subject": "content", "body": "content"}),
}
_NEGATIVE = re.compile(r"\b(do\s+not|don't|never|must\s+not|cannot|can't)\b|禁止|不得|不要|不许", re.I)
_CONFIRM = re.compile(r"\b(confirm(?:ation|ed)?|approv(?:al|e|ed))\b|确认|批准", re.I)
_APP_ROOTS = {"requested_actions", "task_scope", "task_constraints", "calendar_constraints", "hard_constraints",
              "current_user_id", "source_id", "group_id"}
_KINDS = {"literal", "selector", "authority_binding", "result_ref", "data_ref", "derived"}


def _clause(request: str, start: int, end: int) -> str:
    """按句号/分号限定证据语境，不能截掉同句中的禁止词。"""
    before, after = request[:start], request[end:]
    left = max((before.rfind(char) for char in ".!?;。！？；\n"), default=-1) + 1
    stops = [after.find(char) for char in ".!?;。！？；\n" if char in after]
    return request[left:end + (min(stops) if stops else len(after))]


def _field_mentioned(field: str, evidence: list[dict[str, Any]]) -> bool:
    text = " ".join(item.get("quote", "") for item in evidence).casefold()
    aliases = {"id": ("id", "编号", "标识"), "owner": ("owner", "负责人", "所有者"),
               "parent_id": ("parent_id", "parent", "父对象", "父级"),
               "project_id": ("project_id", "project", "项目"), "email": ("email", "邮箱", "邮件地址")}
    return any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) if term.isascii() else term in text
               for term in aliases.get(field, (field,)))


@dataclass(frozen=True)
class CompilationResultV4:
    contract: TaskContractV1
    status: str
    parameter_evidence: tuple[dict[str, Any], ...] = ()
    reference_plan: tuple[dict[str, Any], ...] = ()
    diagnostics: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"compiler_revision": COMPILER_VERSION, "intent_schema_version": INTENT_SCHEMA_VERSION,
                "status": self.status, "contract": self.contract.to_dict(),
                "parameter_evidence": copy.deepcopy(list(self.parameter_evidence)),
                "reference_plan": copy.deepcopy(list(self.reference_plan)),
                "diagnostics": copy.deepcopy(list(self.diagnostics))}


class _Issue(ValueError):
    def __init__(self, code: str, *, status: str = "technical_invalid", stage: str = "shape",
                 repairable: bool = True, action: str = "", argument: str = "") -> None:
        super().__init__(code)
        self.diagnostic = {"code": code, "status": status, "stage": stage, "repairable": repairable,
                           "action_id": action, "argument": argument, "detail": ""}


def _keys(value: Any, allowed: set[str], required: set[str] = frozenset()) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) - allowed or not required <= set(value):
        raise _Issue("intent_shape_invalid")
    return value


def _id(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value) is None:
        raise _Issue("invalid_identifier")
    if re.search(r"gold|evaluator|expected_|ground_truth|attacker_", value, re.I):
        raise _Issue("forbidden_evaluator_field", repairable=False)
    return value


def _literal(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        raise _Issue("finite_literal_limit", repairable=False)
    if isinstance(value, list):
        if len(value) > 64:
            raise _Issue("finite_literal_limit", repairable=False)
        return [_literal(item, depth + 1) for item in value]
    if isinstance(value, Mapping):
        if len(value) > 64 or any(not isinstance(key, str) for key in value):
            raise _Issue("finite_literal_limit", repairable=False)
        legacy._reject_evaluator_fields(value)
        return {key: _literal(item, depth + 1) for key, item in value.items()}
    if value is None or type(value) in {str, bool, int}:
        if isinstance(value, str) and len(value) > 4096:
            raise _Issue("finite_literal_limit", repairable=False)
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise _Issue("constraint_type_mismatch", stage="type")


def build_trusted_tool_catalog(tool_schemas: Mapping[str, Any], adapter_capabilities: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """从调用方可信目录投影；能力不能由模型意图增加。"""
    legacy._reject_evaluator_fields(tool_schemas)
    capabilities = copy.deepcopy(dict(adapter_capabilities or {}))
    tools = {}
    for tool, original in tool_schemas.items():
        known_operation, known_roles = _KNOWN_ROLES.get(tool, (None, {}))
        schema = copy.deepcopy(dict(original))
        operation = schema.get("operation", known_operation)
        roles = schema.get("argument_roles", known_roles)
        if operation not in _OPERATIONS or not isinstance(roles, Mapping) or set(roles.values()) - _ROLES:
            raise _Issue("trusted_catalog_incomplete", status="unsupported", stage="capability", repairable=False)
        args = schema.get("arguments", {})
        if not isinstance(args, Mapping) or set(args) - set(roles):
            raise _Issue("trusted_catalog_incomplete", status="unsupported", stage="capability", repairable=False)
        output_type = _NATIVE_OUTPUTS.get(tool)
        if tool == "lookup_objects":
            output_type = "$kind"
        if tool == "read_object":
            output_type = "$input_object"
        if tool == "create_object" and tool in capabilities.get("created_object_receipts", []):
            output_type = "$kind"
        declared = capabilities.get("tools", {}).get(tool, {})
        if "output_object_type" in declared:
            output_type = declared["output_object_type"]
        tools[tool] = {"operation": operation, "argument_roles": dict(roles), "arguments": args,
                       "side_effect": schema.get("side_effect") is True,
                       "output_object_type": output_type,
                       "query_format": schema.get("query_format"),
                       "query_fields": list(schema.get("query_fields", [])),
                       "generated_for_fields": list(schema.get("generated_for_fields", [])),
                       # 非读取工具不因统一默认值就凭空获得正文输出能力。
                       "content_fields": list(declared.get("content_fields", ["body", "content", "text"]
                                                           if operation == "read" else [])),
                       "created_object_receipt": tool in capabilities.get("created_object_receipts", [])}
    objects = {name: {"verified_fields": sorted(_META - UNTRUSTED_OBJECT_FIELDS)} for name in sorted(_OBJECTS)}
    for name, fields in capabilities.get("objects", {}).items():
        names = fields.get("verified_fields", []) if isinstance(fields, Mapping) else fields
        if set(names) & UNTRUSTED_OBJECT_FIELDS:
            raise _Issue("untrusted_catalog_authority_field", status="unsupported", stage="capability", repairable=False)
        objects[name] = {"verified_fields": sorted(set(names))}
    return {"schema_version": CATALOG_SCHEMA_VERSION, "tools": tools, "objects": objects,
            "created_object_receipts": list(capabilities.get("created_object_receipts", []))}


class _Lowerer:
    def __init__(self, request: str, app: Mapping[str, Any], catalog: Mapping[str, Any], base: Any) -> None:
        self.request, self.app, self.catalog, self.base = request, app, catalog, base
        self.parameter_evidence: list[dict[str, Any]] = []
        self.reference_plan: list[dict[str, Any]] = []
        self.by_id: dict[str, Mapping[str, Any]] = {}
        self.selectors: dict[str, tuple[str, Predicate]] = {}
        self.operations: dict[str, str] = {}
        self.operation_anchors: dict[str, tuple[EvidenceAnchor, ...]] = {}

    def evidence(self, raw: Any, *, action: str = "", argument: str = "", operation: bool = False) -> tuple[list[dict[str, Any]], tuple[EvidenceAnchor, ...]]:
        if not isinstance(raw, list) or not 1 <= len(raw) <= 8:
            raise _Issue("missing_parameter_evidence", status="needs_clarification", stage="grounding", repairable=False, action=action, argument=argument)
        checked, anchors = [], []
        for item in raw:
            item = _keys(item, {"source", "quote", "start", "end", "path"})
            source = item.get("source", "request")
            if source == "request":
                if set(item) - {"source", "quote", "start", "end"}:
                    raise _Issue("intent_shape_invalid")
                quote = item.get("quote")
                start = item.get("start", self.request.find(quote) if isinstance(quote, str) else -1)
                end = item.get("end", start + len(quote) if isinstance(quote, str) and type(start) is int else -1)
                if not isinstance(quote, str) or not quote.strip() or type(start) is not int or type(end) is not int or start < 0 or self.request[start:end] != quote:
                    raise _Issue("evidence_not_in_trusted_request", status="needs_clarification", stage="grounding", repairable=False, action=action, argument=argument)
                checked.append({"source": "request", "quote": quote, "start": start, "end": end})
                anchors.append(EvidenceAnchor(quote, start, end))
                if argument and action in self.operation_anchors:
                    operation = self.operations[action]
                    # 某个目标在请求别处出现，并不授权把它搬到当前动作。
                    local = _clause(self.request, start, end)
                    relevant = any(anchor.start <= start and end <= anchor.end
                                   and re.search(_INTENTS[operation], local, re.I)
                                   or _clause(self.request, anchor.start, anchor.end) == local
                                   for anchor in self.operation_anchors[action])
                    if not relevant:
                        raise _Issue("parameter_evidence_action_mismatch", status="needs_clarification", stage="grounding", repairable=False, action=action, argument=argument)
            elif source == "app" and not operation:
                _keys(item, {"source", "path"}, {"source", "path"})
                path = item["path"]
                if not isinstance(path, list) or not path or len(path) > 8 or path[0] not in _APP_ROOTS:
                    raise _Issue("untrusted_application_reference", status="needs_clarification", stage="grounding", repairable=False)
                value: Any = self.app
                try:
                    for key in path:
                        if type(key) not in {str, int}:
                            raise KeyError()
                        value = value[key]
                except (KeyError, IndexError, TypeError) as exc:
                    raise _Issue("unknown_reference", stage="grounding") from exc
                if path[0] in {"current_user_id", "source_id", "group_id"} and path[0] not in self.request:
                    raise _Issue("unreferenced_application_alias", status="needs_clarification", stage="grounding", repairable=False)
                checked.append({"source": "app", "path": list(path), "value": _literal(value)})
                if action and path[0] == "requested_actions" and len(path) > 1:
                    declaration = self.app["requested_actions"][path[1]]
                    if not isinstance(declaration, Mapping) or declaration.get("tool") != self.by_id[action]["tool"]:
                        raise _Issue("parameter_evidence_action_mismatch", status="needs_clarification", stage="grounding", repairable=False, action=action, argument=argument)
            else:
                raise _Issue("untrusted_evidence_source", status="needs_clarification", stage="grounding", repairable=False)
        if argument:
            self.parameter_evidence.append({"action_id": action, "argument": argument, "evidence": copy.deepcopy(checked)})
        return checked, tuple(anchors)

    def ground(self, value: Any, evidence: list[dict[str, Any]], *, field: str = "") -> None:
        if any(item["source"] == "app" and type(value) is type(item["value"]) and value == item["value"] for item in evidence):
            return
        text = " ".join(item["quote"] for item in evidence if item["source"] == "request")
        if isinstance(value, Mapping):
            for key, child in value.items():
                self.ground(key, evidence)
                self.ground(child, evidence, field=key)
            return
        if isinstance(value, list):
            for child in value:
                self.ground(child, evidence, field=field)
            return
        if type(value) is bool:
            aliases = {("ready", True): ("ready", "就绪"), ("ready", False): ("not ready", "未就绪", "otherwise", "否则"),
                       ("internal", True): ("internal", "内部"), ("internal", False): ("external", "外部")}
            if any(term in text.lower() for term in aliases.get((field, value), ())) or str(value).lower() in text.lower():
                return
        elif value is None:
            if "null" in text.lower() or "空值" in text:
                return
        elif re.search(r"(?<!\w)" + re.escape(str(value)) + r"(?!\w)", text):
            return
        raise _Issue("literal_scope_not_grounded", status="needs_clarification", stage="grounding", repairable=False)

    def filters(self, raw: Any, object_type: str, action: str, argument: str) -> tuple[Predicate, dict[str, Any]]:
        if object_type not in self.catalog["objects"] or not isinstance(raw, list) or not 1 <= len(raw) <= 16:
            raise _Issue("unsupported_object_selector", status="unsupported", stage="capability", repairable=False)
        fields = set(self.catalog["objects"][object_type]["verified_fields"])
        predicates, query = [], {}
        for item in raw:
            item = _keys(item, {"field", "op", "value", "values", "min", "max", "evidence"}, {"field", "op", "evidence"})
            field, op = _id(item["field"]), item["op"]
            if field not in fields or field in UNTRUSTED_OBJECT_FIELDS or field in query:
                raise _Issue("selector_field_not_verified", status="unsupported", stage="capability", repairable=False)
            evidence, _ = self.evidence(item["evidence"], action=action, argument=argument + "." + field)
            if op == "eq":
                _keys(item, {"field", "op", "value", "evidence"}, {"value"})
                value = _literal(item["value"])
                if isinstance(value, (list, Mapping)):
                    raise _Issue("unsupported_selector_value", status="unsupported", stage="type", repairable=False)
                self.ground(value, evidence, field=field)
                predicate, wire = Predicate("eq", value=value, field=field), value
            elif op == "in":
                _keys(item, {"field", "op", "values", "evidence"}, {"values"})
                values = _literal(item["values"])
                if not isinstance(values, list) or not 1 <= len(values) <= 32:
                    raise _Issue("constraint_type_mismatch", stage="type")
                for value in values:
                    if type(value) not in {str, bool, int, float}:
                        raise _Issue("constraint_type_mismatch", stage="type")
                    self.ground(value, evidence, field=field)
                predicate, wire = Predicate("in", values=tuple(values), field=field), {"in": list(values)}
            else:
                raise _Issue("unsupported_selector_comparison", status="unsupported", stage="capability", repairable=False)
            predicates.append(predicate)
            query[field] = wire
        return Predicate("and", items=tuple(predicates)), query

    def source(self, source_id: Any) -> Mapping[str, Any]:
        name = _id(source_id)
        if name not in self.by_id:
            raise _Issue("unknown_reference", stage="graph")
        return self.by_id[name]

    def authority(self, item: Mapping[str, Any], action: str, argument: str, evidence: list[dict[str, Any]]) -> tuple[DeferredBinding, dict[str, Any]]:
        source_id, object_type = _id(item["from_action"]), _id(item["object_type"])
        source = self.source(source_id)
        if source_id not in self.selectors:
            raise _Issue("unsupported_backend_reference", status="unsupported", stage="capability", repairable=False)
        source_type, predicate = self.selectors[source_id]
        field = _id(item.get("value_field", item.get("field", "id")))
        cardinality = item.get("cardinality", "one")
        if object_type != source_type or field not in self.catalog["objects"][object_type]["verified_fields"] or cardinality not in {"one", "many"}:
            raise _Issue("binding_scope_conflict", status="conflict", stage="authority", repairable=False)
        if self.catalog["tools"][source["tool"]]["operation"] not in {"discover", "read", "create"}:
            raise _Issue("unsupported_backend_reference", status="unsupported", stage="capability", repairable=False)
        reference = {"action_id": action, "argument": argument, "kind": item["kind"], "from_action": source_id,
                     "object_type": object_type, "value_field": field, "field": field, "cardinality": cardinality,
                     "selector": predicate.to_dict(), "evidence_refs": evidence}
        if item["kind"] == "authority_binding" and cardinality == "many" and re.search(
                r"\b(?:returned|result)\s+order\b|返回顺序|结果顺序", self.request, re.I):
            reference["iteration_order"] = True
        return DeferredBinding(source_id, object_type, predicate, field, cardinality), reference

    def parameter(self, raw: Any, node: Mapping[str, Any], name: str, tool: Mapping[str, Any]) -> tuple[Predicate | None, DeferredBinding | None, str | tuple[str, ...] | None]:
        action = node["id"]
        item = _keys(raw, {"kind", "value", "evidence", "object_type", "filters", "join", "from_action", "value_field", "field", "cardinality", "transform", "prefix", "operation", "fields", "parts", "min", "max"}, {"kind", "evidence"})
        kind = item["kind"]
        if kind not in _KINDS:
            raise _Issue("intent_shape_invalid")
        evidence, _ = self.evidence(item["evidence"], action=action, argument=name)
        role = tool["argument_roles"][name]
        if kind == "literal":
            _keys(item, {"kind", "value", "evidence"}, {"value"})
            value = _literal(item["value"])
            self.ground(value, evidence, field=name)
            return Predicate("eq", value=value), None, None
        if kind == "selector":
            _keys(item, {"kind", "object_type", "filters", "join", "evidence"}, {"object_type", "filters"})
            if role != "query" or tool["operation"] != "discover" or tool["query_format"] != "json_object_filter":
                raise _Issue("unsupported_query_format", status="unsupported", stage="capability", repairable=False)
            object_type = _id(item["object_type"])
            predicate, query = self.filters(item["filters"], object_type, action, name)
            if not set(query) <= set(tool["query_fields"]):
                raise _Issue("selector_field_not_verified", status="unsupported", stage="capability", repairable=False)
            self.selectors[action] = (object_type, predicate)
            if "join" not in item:
                return Predicate("eq", value=json.dumps(query, ensure_ascii=False, sort_keys=True, separators=(",", ":"))), None, None
            join = _keys(item["join"], {"from_action", "source_field", "target_field"}, {"from_action", "source_field", "target_field"})
            source_id = _id(join["from_action"])
            self.source(source_id)
            if source_id not in self.selectors:
                raise _Issue("unsupported_backend_reference", status="unsupported", stage="capability", repairable=False)
            source_type, source_predicate = self.selectors[source_id]
            source_field, target_field = _id(join["source_field"]), _id(join["target_field"])
            if source_field not in self.catalog["objects"][source_type]["verified_fields"] or target_field not in tool["query_fields"] or target_field in query:
                raise _Issue("binding_scope_conflict", status="conflict", stage="authority", repairable=False)
            if not _field_mentioned(source_field, evidence) or not _field_mentioned(target_field, evidence):
                raise _Issue("relationship_not_grounded", status="needs_clarification", stage="grounding", repairable=False)
            binding = DeferredBinding(source_id, source_type, source_predicate, source_field, "many", "json_filter", target_field, query)
            self.reference_plan.append({"action_id": action, "argument": name, "kind": "authority_binding", "from_action": source_id,
                "object_type": source_type, "value_field": source_field, "field": source_field, "cardinality": "many",
                "query_binding": True, "join": dict(join), "selector": source_predicate.to_dict(), "static_filter": query, "evidence_refs": evidence})
            return None, binding, source_id
        if kind in {"authority_binding", "result_ref"}:
            allowed = {"kind", "from_action", "object_type", "value_field", "field", "cardinality", "evidence"}
            _keys(item, allowed, {"from_action", "object_type"})
            if kind == "authority_binding" and role != "target":
                raise _Issue("reference_role_conflict", status="conflict", stage="authority", repairable=False)
            if kind == "result_ref" and not (role == "value" and tool["arguments"][name].get("allow_backend_binding") is True):
                raise _Issue("unsupported_value_binding", status="unsupported", stage="capability", repairable=False)
            binding, reference = self.authority(item, action, name, evidence)
            self.reference_plan.append(reference)
            return None, binding, binding.from_action
        if kind == "data_ref":
            _keys(item, {"kind", "from_action", "field", "transform", "prefix", "evidence"}, {"from_action", "field"})
            source = self.source(item["from_action"])
            source_tool = self.catalog["tools"][source["tool"]]
            field = _id(item["field"])
            transform = item.get("transform", "copy")
            if field not in source_tool["content_fields"]:
                raise _Issue("unsupported_content_output", status="unsupported", stage="capability", repairable=False)
            if role != "content" or tool["arguments"][name].get("allow_generated") is not True or field not in source_tool["content_fields"] or transform not in {"copy", "summarize", "facts_line"}:
                raise _Issue("data_reference_scope_conflict", status="conflict", stage="authority", repairable=False)
            if transform == "facts_line":
                if not isinstance(item.get("prefix"), str) or not item["prefix"]:
                    raise _Issue("missing_required_argument")
                self.ground(item["prefix"], evidence)
            reference = {"action_id": action, "argument": name, "kind": kind, "from_action": source["id"], "field": field,
                         "transform": transform, "evidence_refs": evidence}
            if "prefix" in item:
                reference["prefix"] = item["prefix"]
            self.reference_plan.append(reference)
            return Predicate("type", value="string"), None, source["id"]
        _keys(item, {"kind", "operation", "from_action", "object_type", "fields", "parts", "evidence"}, {"operation"})
        operation = item["operation"]
        if operation == "concat":
            _keys(item, {"kind", "operation", "parts", "evidence"}, {"parts"})
            if role != "content" or tool["arguments"][name].get("allow_generated") is not True:
                raise _Issue("data_reference_scope_conflict", status="conflict", stage="authority", repairable=False)
            parts = item["parts"]
            if not isinstance(parts, list) or not 1 <= len(parts) <= 16:
                raise _Issue("finite_literal_limit", repairable=False)
            normalized, dependencies = [], set()
            for part in parts:
                part = _keys(part, {"kind", "value", "evidence", "from_action", "object_type", "field", "value_field", "cardinality", "transform"}, {"kind", "evidence"})
                part_evidence, _ = self.evidence(part["evidence"], action=action, argument=name + ".concat")
                if part["kind"] == "literal":
                    _keys(part, {"kind", "value", "evidence"}, {"value"})
                    value = _literal(part["value"])
                    if not isinstance(value, str):
                        raise _Issue("constraint_type_mismatch", stage="type")
                    self.ground(value, part_evidence)
                    normalized.append({"kind": "literal", "value": value})
                elif part["kind"] == "result_ref":
                    _keys(part, {"kind", "from_action", "object_type", "field", "value_field", "cardinality", "evidence"}, {"from_action", "object_type"})
                    _, reference = self.authority(part, action, name, part_evidence)
                    normalized.append(reference)
                    dependencies.add(reference["from_action"])
                elif part["kind"] == "data_ref":
                    _keys(part, {"kind", "from_action", "field", "transform", "evidence"}, {"from_action", "field"})
                    source = self.source(part["from_action"])
                    field = _id(part["field"])
                    if field not in self.catalog["tools"][source["tool"]]["content_fields"] or part.get("transform", "copy") != "copy":
                        raise _Issue("unsupported_content_output", status="unsupported", stage="capability", repairable=False)
                    normalized.append({"kind": "data_ref", "from_action": source["id"], "field": field, "transform": "copy"})
                    dependencies.add(source["id"])
                else:
                    raise _Issue("unsupported_derived_relation", status="unsupported", stage="capability", repairable=False)
            self.reference_plan.append({"action_id": action, "argument": name, "kind": "derived", "operation": "concat", "parts": normalized, "evidence_refs": evidence})
            return Predicate("type", value="string"), None, tuple(sorted(dependencies))
        if operation == "duration_minutes":
            if role != "value" or tool["arguments"][name].get("allow_backend_binding") is not True or item.get("fields") != ["slot_start", "slot_end"]:
                raise _Issue("unsupported_derived_relation", status="unsupported", stage="capability", repairable=False)
            source = self.source(item.get("from_action"))
            if source["id"] not in self.selectors:
                raise _Issue("unsupported_backend_reference", status="unsupported", stage="capability", repairable=False)
            object_type = self.selectors[source["id"]][0]
            if not set(item["fields"]) <= set(self.catalog["objects"][object_type]["verified_fields"]):
                raise _Issue("unsupported_derived_relation", status="unsupported", stage="capability", repairable=False)
            self.reference_plan.append({"action_id": action, "argument": name, "kind": "derived", "operation": operation,
                "from_action": source["id"], "fields": list(item["fields"]), "object_type": object_type, "evidence_refs": evidence})
            return Predicate("type", value="number"), None, source["id"]
        raise _Issue("unsupported_derived_relation", status="unsupported", stage="capability", repairable=False)

    def lower(self, intent: Any) -> tuple[tuple[ContractAction, ...], tuple[ContractProhibition, ...]]:
        root = _keys(intent, {"schema_version", "actions", "prohibitions", "unresolved"}, {"schema_version", "actions"})
        if root["schema_version"] != INTENT_SCHEMA_VERSION:
            raise _Issue("intent_schema_invalid")
        unresolved = root.get("unresolved", [])
        if not isinstance(unresolved, list):
            raise _Issue("intent_shape_invalid")
        if unresolved:
            raise _Issue("unresolved_authorization", status="needs_clarification", stage="authority", repairable=False)
        raw_actions = root["actions"]
        if not isinstance(raw_actions, list) or not 1 <= len(raw_actions) <= 64:
            raise _Issue("intent_shape_invalid")
        for raw in raw_actions:
            node = _keys(raw, {"id", "tool", "operation_evidence", "arguments", "after", "when", "requires_confirmation"}, {"id", "tool", "operation_evidence", "arguments"})
            action, tool = _id(node["id"]), _id(node["tool"])
            if action in self.by_id:
                raise _Issue("duplicate_action_identifier")
            if tool not in self.catalog["tools"]:
                raise _Issue("unknown_tool", status="unsupported", stage="capability", repairable=False)
            self.by_id[action] = node
            self.operations[action] = self.catalog["tools"][tool]["operation"]
        actions = []
        for node in raw_actions:
            action, tool_name = node["id"], node["tool"]
            tool = self.catalog["tools"][tool_name]
            _, anchors = self.evidence(node["operation_evidence"], action=action, operation=True)
            self.operation_anchors[action] = anchors
            # 读取/查找同样需要执行授权：信息、假设或引述中的动作不能
            # 因为没有立即写入效果而绕过语境核验。
            if any(_NEGATIVE.search(_clause(self.request, anchor.start, anchor.end)) for anchor in anchors) or not _execution_evidence(self.request, anchors, tool["operation"]):
                raise _Issue("operation_not_authorized", status="conflict", stage="authority", repairable=False, action=action)
            if "when" not in node and any(re.search(r"\b(if|otherwise|unless)\b|如果|否则|除非|若", _clause(self.request, anchor.start, anchor.end), re.I) for anchor in anchors):
                # 条件在可信原话中，不由模型是否填写when来决定是否存在。
                raise _Issue("missing_user_condition_scope", status="needs_clarification", stage="authority", repairable=False, action=action)
            raw_args = _keys(node["arguments"], set(tool["arguments"]))
            constraints, bindings, dependencies = {}, {}, set()
            after = node.get("after", [])
            if not isinstance(after, list):
                raise _Issue("intent_shape_invalid")
            for previous in after:
                self.source(previous)
                dependencies.add(_id(previous))
            for name, detail in tool["arguments"].items():
                if name not in raw_args:
                    if detail.get("required") is True:
                        raise _Issue("missing_required_argument", action=action, argument=name)
                    continue
                predicate, binding, previous = self.parameter(raw_args[name], node, name, tool)
                if predicate is not None:
                    try:
                        _validate_constraint_type(predicate, detail)
                    except ValueError as exc:
                        raise _Issue("constraint_type_mismatch", stage="type", action=action, argument=name) from exc
                    constraints[name] = predicate
                if binding is not None:
                    bindings[name] = binding
                if previous:
                    dependencies.update((previous,) if isinstance(previous, str) else previous)
            if any(re.search(r"\b(then|after|next|before)\b|然后|之后|随后|再|之前", _clause(self.request, anchor.start, anchor.end), re.I) for anchor in anchors):
                # 本轮只核验已明确表达的节点依赖，不猜测未装配的自然语言顺序。
                preceding = []
                earliest = min(anchor.start for anchor in anchors)
                for other in raw_actions:
                    if other["id"] == action:
                        continue
                    _, other_anchors = self.evidence(other["operation_evidence"], action=other["id"], operation=True)
                    ends = [anchor.end for anchor in other_anchors if anchor.end <= earliest]
                    if ends:
                        preceding.append((max(ends), other["id"]))
                if preceding and max(preceding)[1] not in dependencies:
                    raise _Issue("missing_user_order_dependency", status="needs_clarification", stage="authority", repairable=False, action=action)
            # 查找类型来自固定kind参数，不能由intent.object_type另行改变。
            if action in self.selectors and tool["output_object_type"] == "$kind":
                kind = constraints.get("kind")
                if kind is None or kind.op != "eq" or kind.value != self.selectors[action][0]:
                    raise _Issue("binding_scope_conflict", status="conflict", stage="authority", repairable=False)
            if action in self.selectors and tool["output_object_type"] not in {None, "$kind", "$input_object"} \
                    and tool["output_object_type"] != self.selectors[action][0]:
                raise _Issue("binding_scope_conflict", status="conflict", stage="authority", repairable=False)
            if tool["operation"] == "create" and tool["created_object_receipt"]:
                kind = constraints.get("kind")
                if kind is None or kind.op != "eq" or kind.value not in self.catalog["objects"]:
                    raise _Issue("unsupported_creation_type", status="unsupported", stage="capability", repairable=False)
                # 精确参数与已应用事件由后端逐次核验；此谓词只限定收据对象类型。
                self.selectors[action] = (kind.value, Predicate("eq", field="kind", value=kind.value))
            if tool["output_object_type"] not in {None, "$kind", "$input_object"}:
                target_filters = [(name, p) for name, p in constraints.items() if tool["argument_roles"][name] == "query"]
                if target_filters:
                    # 原生自然语言查询没有声明独立对象谓词时不能自造完整选择范围。
                    pass
            confirmation = node.get("requires_confirmation", False)
            if type(confirmation) is not bool:
                raise _Issue("constraint_type_mismatch", stage="type")
            prior = tuple(rule for rule in self.base.rules if rule.tool == tool_name)
            confirmation |= any(rule.requires_confirmation for rule in prior)
            if tool["operation"] != "confirm":
                confirmation |= any(_CONFIRM.search(_clause(self.request, anchor.start, anchor.end)) is not None
                                    for anchor in anchors)
                confirmation |= bool(tool["side_effect"] and re.search(
                    r"\b(?:confirm(?:ation)?|approv(?:al|e))\b[^.。;；]*(?:\b(?:any|all|every)\b)|(?:所有|全部|任何)[^。；]*(?:确认|批准)", self.request, re.I))
            sources = ContractAction.__dataclass_fields__["permitted_argument_sources"].default
            for rule in prior:
                sources = tuple(source for source in sources if source in rule.permitted_argument_sources)
            when = None
            if "when" in node:
                branch = _keys(node["when"], {"argument", "field", "equals", "evidence"}, {"argument", "field", "equals", "evidence"})
                if branch["argument"] not in bindings:
                    raise _Issue("unknown_reference", stage="graph")
                field = _id(branch["field"])
                obj_type = bindings[branch["argument"]].object_type
                if field not in self.catalog["objects"][obj_type]["verified_fields"]:
                    raise _Issue("selector_field_not_verified", status="unsupported", stage="capability", repairable=False)
                evidence, _ = self.evidence(branch["evidence"], action=action, argument="when." + field)
                value = _literal(branch["equals"])
                self.ground(value, evidence, field=field)
                when = (branch["argument"], Predicate("eq", value=value, field=field))
            actions.append(ContractAction(action, tool_name, tool["operation"], constraints, anchors,
                dict(tool["argument_roles"]), tuple(sorted(dependencies)), bindings, confirmation, sources, when))
        graph = {action.action_id: set(action.depends_on) for action in actions}
        completed: set[str] = set()
        def visit(name: str, pending: set[str]) -> None:
            if name in pending:
                raise _Issue("graph_cycle", stage="graph")
            if name in completed:
                return
            for previous in graph[name]:
                visit(previous, pending | {name})
            completed.add(name)
        for name in graph:
            visit(name, set())
        prohibitions = []
        raw_prohibitions = root.get("prohibitions", [])
        if not isinstance(raw_prohibitions, list) or len(raw_prohibitions) > 64:
            raise _Issue("intent_shape_invalid")
        for item in raw_prohibitions:
            item = _keys(item, {"tool", "arguments", "evidence"}, {"tool", "arguments", "evidence"})
            tool_name = _id(item["tool"])
            if tool_name not in self.catalog["tools"]:
                raise _Issue("unknown_tool", status="unsupported", stage="capability", repairable=False)
            _, anchors = self.evidence(item["evidence"], operation=True)
            if not _NEGATIVE.search(" ".join(anchor.quote for anchor in anchors)):
                raise _Issue("prohibition_not_authorized", status="conflict", stage="authority", repairable=False)
            constraints = {}
            for name, raw in _keys(item["arguments"], set(self.catalog["tools"][tool_name]["arguments"])).items():
                raw = _keys(raw, {"kind", "value", "evidence"}, {"kind", "value", "evidence"})
                if raw["kind"] != "literal":
                    raise _Issue("unsupported_prohibition_scope", status="unsupported", stage="capability", repairable=False)
                evidence, _ = self.evidence(raw["evidence"], argument=name)
                value = _literal(raw["value"])
                self.ground(value, evidence, field=name)
                constraints[name] = Predicate("eq", value=value)
            prohibitions.append(ContractProhibition(tool_name, constraints, anchors))
        # 模型遗漏禁止项不能清除用户原话。有限明确目标可确定性补齐；
        # 有限定但无法表达的禁止范围进入澄清，不能扩大或忽略。
        for clause in re.split(r"[.;!?。；！？\n]", self.request):
            if not _NEGATIVE.search(clause):
                continue
            for tool_name, tool in self.catalog["tools"].items():
                if not re.search(_INTENTS[tool["operation"]], clause, re.I):
                    continue
                if tool["operation"] == "send" and re.search(r"external|外部", clause, re.I):
                    continue  # 外部收件人禁令在独立语义字段中保留。
                if any(p.tool == tool_name and any(anchor.quote in clause for anchor in p.evidence) for p in prohibitions):
                    continue
                if re.search(r"\b(unless|except|outside|within|nonmatching)\b|除非|范围外|非匹配|不匹配", clause, re.I):
                    raise _Issue("missing_user_prohibition_scope", status="needs_clarification", stage="authority", repairable=False)
                start = self.request.find(clause)
                anchor = EvidenceAnchor(clause, start, start + len(clause))
                targets = [name for name, role in tool["argument_roles"].items() if role == "target"]
                match = re.search(r"\b(?:object|file|folder|record)\s+([A-Za-z0-9_:./-]+)(?=\s|$)|(?:对象|文件|文件夹|记录)\s*([A-Za-z0-9_:./-]+)(?=\s|$)", clause, re.I)
                if len(targets) == 1 and match and (match.group(1) or match.group(2)).casefold() not in {
                        "anything", "everything", "all", "any", "the", "these", "those", "that", "this", "matching", "returned"}:
                    value = match.group(1) or match.group(2)
                    prohibitions.append(ContractProhibition(tool_name, {targets[0]: Predicate("eq", value=value)}, (anchor,)))
                else:
                    # 只有没有限定目标的纯工具禁止可以补成整工具禁令。
                    tail = re.split(_INTENTS[tool["operation"]], clause, maxsplit=1, flags=re.I)[-1].strip()
                    if tail.casefold() in {"", "anything", "everything", "any object", "all objects"}:
                        prohibitions.append(ContractProhibition(tool_name, {}, (anchor,)))
                    else:
                        raise _Issue("missing_user_prohibition_scope", status="needs_clarification", stage="authority", repairable=False)
        for action in actions:
            for prohibition in prohibitions:
                if prohibition.tool == action.tool and (not prohibition.constraints or all(name in action.constraints and action.constraints[name].op == "eq" and predicate.matches(action.constraints[name].value) for name, predicate in prohibition.constraints.items())):
                    raise _Issue("prohibition_conflict", status="conflict", stage="authority", repairable=False)
        return tuple(actions), tuple(prohibitions)


def compile_task_intent_v4(*, trusted_user_request: str, trusted_app_context: Mapping[str, Any],
                           tool_schemas: Mapping[str, Any], intent: Mapping[str, Any],
                           catalog: Mapping[str, Any] | None = None, base_manifest: Any = None) -> CompilationResultV4:
    """只物化传入意图；不给未知关系补授权，不进行模型调用或择优。"""
    request = str(trusted_user_request).strip()
    app = copy.deepcopy(dict(trusted_app_context))
    legacy._reject_evaluator_fields(app)
    base = base_manifest or compile_generic_task_policy_corrected_v2(
        trusted_user_request=request, trusted_app_context=app, tool_schemas=tool_schemas)
    empty = replace(base, rules=(), approvals=(), manifest_sha256="")
    try:
        if not request:
            raise _Issue("missing_trusted_request", status="needs_clarification", stage="authority", repairable=False)
        legacy._reject_evaluator_fields(intent)
        trusted_catalog = copy.deepcopy(dict(catalog)) if catalog is not None else build_trusted_tool_catalog(tool_schemas)
        if trusted_catalog.get("schema_version") != CATALOG_SCHEMA_VERSION or set(trusted_catalog.get("tools", {})) != set(tool_schemas):
            raise _Issue("trusted_catalog_incomplete", status="unsupported", stage="capability", repairable=False)
        lowerer = _Lowerer(request, app, trusted_catalog, base)
        actions, prohibitions = lowerer.lower(intent)
        hard = _keys(app.get("hard_constraints", {}), {"prohibited_tools", "argument_constraints", "require_confirmation_tools"})
        for tool_name in hard.get("prohibited_tools", []):
            if tool_name not in tool_schemas:
                raise _Issue("unknown_application_tool", status="unsupported", stage="capability", repairable=False)
            prohibitions += (ContractProhibition(tool_name, {}, ()),)
        if any(action.tool == p.tool and not p.constraints for action in actions for p in prohibitions):
            raise _Issue("prohibition_conflict", status="conflict", stage="authority", repairable=False)
        required = set(hard.get("require_confirmation_tools", []))
        actions = tuple(replace(action, requires_confirmation=True) if action.tool in required else action for action in actions)
        application_scope = tuple(legacy._structured_rules(app, tool_schemas)) if "requested_actions" in app else None
        if application_scope is not None and any(not any(rule.tool == action.tool for rule in application_scope) for action in actions):
            raise _Issue("application_scope_conflict", status="conflict", stage="authority", repairable=False)
        application_constraints: dict[str, dict[str, Predicate]] = {}
        # 应用硬约束仅允许有限值与区间；不接收模型生成表达式。
        for tool_name, values in hard.get("argument_constraints", {}).items():
            if tool_name not in tool_schemas:
                raise _Issue("unknown_application_tool", status="unsupported", stage="capability", repairable=False)
            for name, raw in values.items():
                _keys(raw, {"op", "value", "min", "max", "values"}, {"op"})
                op = raw["op"]
                if op == "eq":
                    predicate = Predicate("eq", value=_literal(raw["value"]))
                elif op == "in":
                    predicate = Predicate("in", values=tuple(_literal(raw["values"])))
                elif op in {"number_range", "date_range"} and ("min" in raw or "max" in raw):
                    predicate = Predicate(op, minimum=raw.get("min"), maximum=raw.get("max"))
                else:
                    raise _Issue("unsupported_application_constraint", status="unsupported", stage="capability", repairable=False)
                application_constraints.setdefault(tool_name, {})[name] = predicate
        calendar = app.get("calendar_constraints", {})
        for tool_name, schema in tool_schemas.items():
            for prefix, argument, op in (("start", "start_time", "date_range"), ("end", "end_time", "date_range"), ("duration", "duration_minutes", "number_range")):
                if argument in schema.get("arguments", {}) and any(prefix + suffix in calendar for suffix in ("_min", "_max")):
                    application_constraints.setdefault(tool_name, {})[argument] = Predicate(op, minimum=calendar.get(prefix + "_min"), maximum=calendar.get(prefix + "_max"))
        static_rules = tuple(ToolRule("intent-" + a.action_id, a.tool,
            {name: ParameterConstraint("exact", p.value) if p.op == "eq" else ParameterConstraint("type", p.value) if p.op == "type" else ParameterConstraint("enum", p.values)
             for name, p in a.constraints.items()}, a.permitted_argument_sources, a.requires_confirmation,
            trusted_catalog["tools"][a.tool]["side_effect"]) for a in actions if not a.bindings)
        refs = tuple(lowerer.reference_plan)
        contract_status = "runtime_references_required" if refs else "ready"
        external = bool(re.search(r"(?:never|do\s+not|must\s+not)[^.。]*external|禁止[^。]*外部", request, re.I))
        contract = TaskContractV1(replace(empty, rules=static_rules, manifest_sha256=""), actions, prohibitions,
            status=contract_status, lexical_manifest=base, application_scope=application_scope,
            application_constraints=application_constraints, prohibit_external_recipients=external,
            data_flow_policy=copy.deepcopy(app.get("data_flow_policy", {})))
        return CompilationResultV4(contract, "ready", tuple(lowerer.parameter_evidence), refs)
    except (ValueError, TypeError, KeyError) as exc:
        issue = exc if isinstance(exc, _Issue) else _Issue("intent_shape_invalid")
        diagnostic = issue.diagnostic
        status = diagnostic["status"]
        contract = TaskContractV1(empty, status="conflict" if status == "conflict" else "invalid",
            diagnostics=(ContractDiagnostic(diagnostic["code"], status),), lexical_manifest=base)
        return CompilationResultV4(contract, status, diagnostics=(diagnostic,))
