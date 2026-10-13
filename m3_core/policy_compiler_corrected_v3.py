"""模型草稿的有限 DSL 编译器；草稿不能自称可信或增加任意操作。"""

from __future__ import annotations

import json
import math
import re
from dataclasses import replace
from typing import Any, Mapping

from m3_core import policy_compiler as legacy
from m3_core.policy_compiler_corrected_v2 import compile_generic_task_policy_corrected_v2, _explicit_literal
from m3_guard.task_contract_v1 import (
    DRAFT_SCHEMA_VERSION, ContractAction, ContractDiagnostic, ContractProhibition,
    DeferredBinding, EvidenceAnchor, Predicate, TaskContractV1, _date,
)
from m3_guard.task_policy import ParameterConstraint, TaskPolicyManifest, ToolRule
from m3_guard.provenance import SOURCE_TYPES

COMPILER_VERSION = "corrected_v3"
_OPERATIONS = frozenset({"discover", "read", "modify", "create", "send", "delete", "confirm"})
_ARGUMENT_ROLES = frozenset({"target", "content", "query", "value"})
_KNOWN_CATALOG = {
    "lookup_objects": ("discover", {"kind": "target", "query": "query"}),
    "read_object": ("read", {"object_id": "target"}),
    "update_object": ("modify", {"object_id": "target", "field": "target", "value": "value"}),
    "create_object": ("create", {"kind": "target", "title": "target", "owner_id": "target", "parent_id": "target", "body": "content"}),
    "send_message": ("send", {"recipient_id": "target", "body": "content", "source_id": "target"}),
    "add_member": ("modify", {"object_id": "target", "member_id": "target"}),
    "delete_object": ("delete", {"object_id": "target"}),
    "confirm_action": ("confirm", {"node_id": "target", "arguments": "value"}),
    "read_file": ("read", {"path": "target"}),
    "write_file": ("modify", {"path": "target", "content": "content"}),
    "send_email": ("send", {"to": "target", "subject": "content", "body": "content"}),
}
_INTENTS = {
    "discover": r"\b(find|search|look\s*up|lookup|lookup_objects|list|locate|identify|get)\b|查找|查询|搜索|列出|找到",
    "read": r"\b(read|open|inspect|review|summari[sz]e|get|fetch|show)\b|读取|阅读|打开|审阅|总结|查看",
    "modify": r"\b(update|edit|modify|change|set|write|save|append|add|invite|schedule_event|reschedule|move|pay|transfer)\b|更新|修改|设置|写入|保存|添加|加为|邀请|移动|转账|支付|安排日历",
    "create": r"\b(create|make|schedule|book|reserve)\b|创建|新建|安排|预订",
    "send": r"\b(send|email|mail|forward|share|post|pay|transfer)\b|发送|转发|分享|发给|支付|转账",
    "delete": r"\b(delete|remove|cancel)\b|删除|移除|取消",
    "confirm": r"\b(confirm|approve)\b|确认|批准",
}
_NEGATIVE = re.compile(r"\b(do\s+not|don't|never|must\s+not|without|avoid|cannot|can't)\b|\bnot\s+(send|write|delete|remove|pay|transfer)\b|不要|禁止|不得|不能|不许", re.I)


class _Invalid(ValueError):
    def __init__(self, code: str, status: str = "invalid") -> None:
        self.code, self.status = code, status
        super().__init__(code)


def _keys(value: Any, allowed: set[str], required: set[str] = frozenset()) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) - allowed or not required <= set(value):
        raise _Invalid("unknown_or_missing_dsl_field")
    return value


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value) is None:
        raise _Invalid("invalid_identifier")
    if re.search(r"gold|evaluator|expected_|ground_truth|attacker_", value, re.I):
        raise _Invalid("forbidden_evaluator_field")
    return value


def _scalar(value: Any) -> Any:
    if value is None or type(value) in {str, bool, int}:
        if isinstance(value, str) and len(value) > 4096:
            raise _Invalid("literal_too_long")
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise _Invalid("non_scalar_literal")


def _finite_literal(value: Any, depth: int = 0) -> Any:
    """等值约束支持工具的有限JSON实参，不把JSON当可执行程序。"""
    if depth > 4:
        raise _Invalid("literal_too_deep")
    if isinstance(value, list):
        if len(value) > 64:
            raise _Invalid("literal_too_large")
        return [_finite_literal(item, depth + 1) for item in value]
    if isinstance(value, Mapping):
        if len(value) > 64 or any(not isinstance(key, str) for key in value):
            raise _Invalid("invalid_object_literal")
        legacy._reject_evaluator_fields(value)
        return {key: _finite_literal(item, depth + 1) for key, item in value.items()}
    return _scalar(value)


def _predicate(raw: Any, *, object_predicate: bool = False, depth: int = 0) -> Predicate:
    if depth > 4:
        raise _Invalid("predicate_depth_exceeded")
    raw = _keys(raw, {"op", "value", "values", "min", "max", "items", "field"}, {"op"})
    op = raw["op"]
    extra = {"field"} if object_predicate and op != "and" else set()
    if op in {"eq", "type"}:
        _keys(raw, {"op", "value"} | extra, {"op", "value"} | extra)
        value = _finite_literal(raw["value"]) if op == "eq" and not object_predicate else _scalar(raw["value"])
        if op == "type" and (object_predicate or value not in {"string", "integer", "number", "boolean", "array", "object", "null"}):
            raise _Invalid("unsupported_type_predicate")
        result = Predicate(op, value=value)
    elif op == "in":
        _keys(raw, {"op", "values"} | extra, {"op", "values"} | extra)
        values = raw["values"]
        if not isinstance(values, list) or not 1 <= len(values) <= 32:
            raise _Invalid("invalid_finite_set")
        result = Predicate(op, values=tuple(_scalar(value) for value in values))
    elif op in {"number_range", "date_range"}:
        _keys(raw, {"op", "min", "max"} | extra, {"op"} | extra)
        if "min" not in raw and "max" not in raw:
            raise _Invalid("unbounded_range")
        low, high = raw.get("min"), raw.get("max")
        bounds = [bound for bound in (low, high) if bound is not None]
        if op == "number_range":
            if not bounds or any(type(bound) not in {int, float} or not math.isfinite(bound) for bound in bounds):
                raise _Invalid("invalid_number_bound")
        elif not bounds or any(_date(bound) is None for bound in bounds):
            raise _Invalid("invalid_date_bound")
        try:
            if low is not None and high is not None and ((low > high) if op == "number_range" else (_date(low) > _date(high))):
                raise _Invalid("conflicting_range", "conflict")
        except TypeError as exc:
            raise _Invalid("incompatible_date_bound") from exc
        result = Predicate(op, minimum=low, maximum=high)
    elif op == "and":
        _keys(raw, {"op", "items"}, {"op", "items"})
        if not isinstance(raw["items"], list) or not 1 <= len(raw["items"]) <= 16:
            raise _Invalid("invalid_and_predicate")
        result = Predicate(op, items=tuple(_predicate(item, object_predicate=object_predicate, depth=depth + 1) for item in raw["items"]))
    else:
        raise _Invalid("unsupported_predicate")
    if extra:
        result = replace(result, field=_identifier(raw["field"]))
    return result


def _evidence(raw: Any, request: str) -> tuple[EvidenceAnchor, ...]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 8:
        raise _Invalid("missing_original_evidence", "missing")
    result = []
    for item in raw:
        item = _keys(item, {"quote", "start", "end"}, {"quote"})
        quote = item["quote"]
        if not isinstance(quote, str) or not quote.strip():
            raise _Invalid("invalid_evidence")
        start = item.get("start", request.find(quote))
        end = item.get("end", start + len(quote) if type(start) is int else -1)
        if type(start) is not int or type(end) is not int or start < 0 or request[start:end] != quote:
            raise _Invalid("evidence_not_in_trusted_request")
        result.append(EvidenceAnchor(quote, start, end))
    return tuple(result)


def _execution_evidence(request: str, evidence: tuple[EvidenceAnchor, ...], operation: str) -> bool:
    """模型摘录不能剥离信息、假设或引述语境后变成副作用授权。

    这里仅识别有限的保守语境，不宣称完整自然语言意图识别。无法明确
    判断时返回待澄清；真正的条件分支仍由契约when及可信状态单独验证。
    """
    quoted = tuple(re.finditer(r'"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’|(?<!\w)\x27[^\x27\n]*\x27(?!\w)', request))
    for anchor in evidence:
        if not re.search(_INTENTS[operation], anchor.quote, re.I):
            continue
        if any(span.start() < anchor.start and anchor.end < span.end() for span in quoted):
            continue
        before = request[:anchor.start]
        after = request[anchor.end:]
        start = max((before.rfind(char) for char in ".!?;。！？；\n"), default=-1) + 1
        stops = [after.find(char) for char in ".!?;。！？；\n" if char in after]
        stop = min(stops) if stops else len(after)
        clause = request[start:anchor.end + stop]
        information = re.search(
            r"\b(explain|describe|discuss|translate|quote|hypothetical|suppose|imagine)\b"
            r"|\btell\s+me\s+(?:whether|what|how)\b|\bwhat\s+(?:happens|would|if)\b"
            r"|\b(?:just|only|an?)\s+(?:an?\s+)?example\b|\bif\s+(?:I|we)\b"
            r"|\bis\s+it\s+(?:possible|safe)\b|解释|说明.*(?:含义|意思)|假设|如果.*(?:会怎样|怎么办)|例如|举例",
            clause, re.I,
        )
        if not information:
            return True
    return False


def _catalog(tool: str, schema: Mapping[str, Any]) -> tuple[str, dict[str, str]]:
    known_operation, known_roles = _KNOWN_CATALOG.get(tool, (None, {}))
    operation = schema.get("operation", known_operation)
    roles = dict(schema.get("argument_roles", known_roles))
    if operation not in _OPERATIONS or any(role not in _ARGUMENT_ROLES for role in roles.values()):
        raise _Invalid("trusted_tool_catalog_missing", "missing")
    return operation, roles


def _leaves(predicate: Predicate) -> tuple[Predicate, ...]:
    return tuple(leaf for item in predicate.items for leaf in _leaves(item)) if predicate.op == "and" else (predicate,)


def _ground_literals(predicate: Predicate, evidence: str, context: Mapping[str, Any]) -> None:
    # 参数值可由可信请求或应用声明提供；模型自己的猜测不算依据。
    context_literals: list[Any] = []
    def collect(value: Any) -> None:
        if isinstance(value, Mapping):
            for child in value.values():
                collect(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                collect(child)
        else:
            context_literals.append(value)
    # suite/benchmark/user_task_id等路由元数据不表示请求者授予了该目标权限。
    for name in ("requested_actions", "task_scope", "task_constraints", "calendar_constraints"):
        if name in context:
            collect(context[name])
    # 只有请求明确引用的固定应用资源别名可提供参数，路由/评测ID仍无权授予目标。
    for name in ("current_user_id", "source_id", "group_id"):
        if name in context and re.search(r"(?<!\w)" + name + r"(?!\w)", evidence):
            collect(context[name])
    if isinstance(context.get("hard_constraints"), Mapping):
        collect(context["hard_constraints"].get("argument_constraints", {}))
    for leaf in _leaves(predicate):
        values = (leaf.value,) if leaf.op == "eq" else leaf.values if leaf.op == "in" else (leaf.minimum, leaf.maximum) if leaf.op in {"number_range", "date_range"} else ()
        def atoms(value):
            if isinstance(value, Mapping):
                return [atom for key, child in value.items() for atom in [key, *atoms(child)]]
            if isinstance(value, (list, tuple)):
                return [atom for child in value for atom in atoms(child)]
            return [value]
        values = [atom for value in values for atom in atoms(value)]
        for value in values:
            if value is None or type(value) is bool:
                continue  # 布尔谓词受可信字段类型/后端条件验证，不是权限正文。
            if any(type(value) is type(item) and value == item for item in context_literals):
                continue
            if re.search(r"(?<!\w)" + re.escape(str(value)) + r"(?!\w)", evidence) is None:
                raise _Invalid("literal_not_grounded_in_trusted_evidence", "ambiguous")


def _graph(actions: list[ContractAction]) -> None:
    by_id = {action.action_id: action for action in actions}
    visited: set[str] = set()
    def visit(action_id: str, stack: frozenset[str]) -> None:
        if action_id in stack:
            raise _Invalid("cyclic_action_dependency", "conflict")
        if action_id not in by_id:
            raise _Invalid("missing_dependency", "missing")
        if action_id in visited:
            return
        action = by_id[action_id]
        for previous in action.depends_on:
            visit(previous, stack | {action_id})
        for binding in action.bindings.values():
            if binding.from_action not in action.depends_on:
                raise _Invalid("binding_discovery_dependency_missing", "missing")
            if by_id.get(binding.from_action) is None or by_id[binding.from_action].role not in {"discover", "read", "create"}:
                raise _Invalid("binding_discovery_role_conflict", "conflict")
        visited.add(action_id)
    for action in actions:
        visit(action.action_id, frozenset())


def _parameter(predicate: Predicate, required: bool) -> ParameterConstraint:
    if predicate.op == "eq":
        return ParameterConstraint("exact", predicate.value, required=required)
    if predicate.op == "in":
        return ParameterConstraint("enum", predicate.values, required=required)
    if predicate.op == "type":
        return ParameterConstraint("type", predicate.value, required=required)
    # 有限区间/AND由新监视器完整匹配后才物化为具体 exact 值。
    return ParameterConstraint("enum", (), required=required)


def compile_task_contract_v1(
    *, trusted_user_request: str, tool_schemas: Mapping[str, Mapping[str, Any]],
    draft: Mapping[str, Any] | str, trusted_app_context: Mapping[str, Any] | None = None,
    base_manifest: TaskPolicyManifest | None = None,
) -> TaskContractV1:
    """只解释首个草稿；失败返回显式诊断，不生成替代草稿或任意权限。"""
    request = str(trusted_user_request).strip()
    if not request:
        raise ValueError("trusted_user_request must not be empty")
    legacy._reject_evaluator_fields(trusted_app_context or {})
    base = base_manifest or compile_generic_task_policy_corrected_v2(
        trusted_user_request=request, tool_schemas=tool_schemas,
        trusted_app_context=trusted_app_context,
    )
    empty = replace(base, rules=(), approvals=(), manifest_sha256="")
    try:
        if isinstance(draft, str):
            def pairs(items):
                if len({key for key, _ in items}) != len(items):
                    raise _Invalid("duplicate_json_key")
                return dict(items)
            draft = json.loads(draft, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(_Invalid("nonfinite_json")))
        raw = _keys(draft, {"schema_version", "actions", "prohibitions"}, {"schema_version", "actions"})
        legacy._reject_evaluator_fields(raw)
        if raw["schema_version"] != DRAFT_SCHEMA_VERSION:
            raise _Invalid("unsupported_draft_schema")
        if not isinstance(raw["actions"], list) or len(raw["actions"]) > 64:
            raise _Invalid("invalid_action_list")
        if not raw["actions"]:
            raise _Invalid("missing_action", "missing")
        actions = []
        for node in raw["actions"]:
            node = _keys(node, {"action_id", "tool", "role", "constraints", "evidence", "depends_on", "argument_roles", "bindings", "requires_confirmation", "permitted_argument_sources", "when"}, {"action_id", "tool", "role", "constraints", "evidence"})
            action_id, tool = _identifier(node["action_id"]), _identifier(node["tool"])
            if tool not in tool_schemas:
                raise _Invalid("unknown_tool")
            operation, roles = _catalog(tool, tool_schemas[tool])
            if node["role"] != operation:
                raise _Invalid("operation_role_conflict", "conflict")
            if any(roles.get(key) != value for key, value in node.get("argument_roles", {}).items()):
                raise _Invalid("argument_role_conflict", "conflict")
            evidence = _evidence(node["evidence"], request)
            quotes = " ".join(item.quote for item in evidence)
            if _NEGATIVE.search(quotes):
                raise _Invalid("negative_action_evidence", "conflict")
            # 问题式请求可要求必要读取/查找；资源仍须由下方有限约束限定。
            # 副作用不适用此闭包，不能以“需要查询”为写入/支付授予权限。
            if operation not in {"read", "discover"} and not _execution_evidence(request, evidence, operation):
                raise _Invalid("evidence_does_not_authorize_operation", "ambiguous")
            constraints = {key: _predicate(value) for key, value in _keys(node["constraints"], set(tool_schemas[tool].get("arguments", {}))).items()}
            bindings = {}
            for name, raw_binding in node.get("bindings", {}).items():
                raw_binding = _keys(raw_binding, {"from_action", "object_type", "predicate", "value_field", "cardinality", "value_format", "filter_field", "static_filter"}, {"from_action", "object_type", "predicate"})
                formatter = raw_binding.get("value_format")
                query_binding = roles.get(name) == "query" and operation == "discover" and tool_schemas[tool].get("query_format") == "json_object_filter"
                value_binding = roles.get(name) == "value" and bool(tool_schemas[tool]["arguments"][name].get("allow_backend_binding", False))
                if (roles.get(name) != "target" and not query_binding and not value_binding) or raw_binding.get("cardinality", "one") not in {"one", "many"}:
                    raise _Invalid("invalid_target_binding", "conflict")
                if formatter not in {None, "json_filter"} or (formatter == "json_filter") != query_binding:
                    raise _Invalid("unapproved_binding_formatter", "conflict")
                static = raw_binding.get("static_filter", {})
                filter_field = _identifier(raw_binding.get("filter_field")) if query_binding else None
                if not isinstance(static, Mapping) or (not query_binding and (static or "filter_field" in raw_binding)):
                    raise _Invalid("invalid_binding_static_filter")
                if query_binding and not ({filter_field} | set(static)) <= set(tool_schemas[tool].get("query_fields", ())):
                    raise _Invalid("untrusted_query_predicate_field", "conflict")
                for key, value in static.items():
                    _identifier(key)
                    _ground_literals(Predicate("eq", _scalar(value)), quotes, trusted_app_context or {})
                bindings[name] = DeferredBinding(_identifier(raw_binding["from_action"]), _identifier(raw_binding["object_type"]), _predicate(raw_binding["predicate"], object_predicate=True), _identifier(raw_binding.get("value_field", "id")), raw_binding.get("cardinality", "one"), formatter, filter_field, dict(static))
                _ground_literals(bindings[name].predicate, quotes, trusted_app_context or {})
            if set(bindings) & set(constraints) or set(bindings) - set(tool_schemas[tool].get("arguments", {})):
                raise _Invalid("binding_constraint_conflict", "conflict")
            for name, detail in tool_schemas[tool].get("arguments", {}).items():
                if detail.get("required", False) and name not in constraints and name not in bindings:
                    raise _Invalid("missing_argument_scope", "missing")
            for name, predicate in constraints.items():
                for leaf in _leaves(predicate):
                    if leaf.op == "type" and not (roles.get(name) in {"content", "query"} and tool_schemas[tool]["arguments"][name].get("allow_generated", False) and (roles[name] != "query" or operation == "discover")):
                        raise _Invalid("unscoped_argument_type", "conflict")
                    if leaf.op == "type" and roles.get(name) == "query" and _explicit_literal(request, name, str(tool_schemas[tool]["arguments"][name].get("type", "object"))) is not None:
                        raise _Invalid("explicit_query_scope_not_preserved", "conflict")
                    if leaf.op == "type" and tool == "update_object" and name == "value":
                        selector = constraints.get("field")
                        if selector is None or selector.op != "eq" or selector.value not in tool_schemas[tool].get("generated_for_fields", ()):
                            raise _Invalid("generated_update_field_not_permitted", "conflict")
                _ground_literals(predicate, quotes, trusted_app_context or {})
            dependencies = node.get("depends_on", [])
            if not isinstance(dependencies, list):
                raise _Invalid("invalid_dependencies")
            confirmation = node.get("requires_confirmation", False)
            if type(confirmation) is not bool:
                raise _Invalid("invalid_confirmation")
            # 首稿只能增加来源限制/确认，不能移除已存在的强要求。
            prior_rules = tuple(rule for rule in base.rules if rule.tool == tool)
            confirmation |= any(rule.requires_confirmation for rule in prior_rules)
            sources = node.get("permitted_argument_sources", list(ContractAction.__dataclass_fields__["permitted_argument_sources"].default))
            if not isinstance(sources, list) or not sources or set(sources) - SOURCE_TYPES:
                raise _Invalid("invalid_argument_sources")
            for prior in prior_rules:
                sources = [source for source in sources if source in prior.permitted_argument_sources]
            when = None
            if "when" in node:
                condition = _keys(node["when"], {"binding", "predicate"}, {"binding", "predicate"})
                if condition["binding"] not in bindings:
                    raise _Invalid("condition_binding_missing", "missing")
                when = (_identifier(condition["binding"]), _predicate(condition["predicate"], object_predicate=True))
                _ground_literals(when[1], quotes, trusted_app_context or {})
            actions.append(ContractAction(action_id, tool, operation, constraints, evidence, roles, tuple(_identifier(dep) for dep in dependencies), bindings, confirmation, tuple(sources), when))
        if len({action.action_id for action in actions}) != len(actions):
            raise _Invalid("duplicate_action_id")
        _graph(actions)
        application_scope = tuple(legacy._structured_rules(trusted_app_context or {}, tool_schemas)) if "requested_actions" in (trusted_app_context or {}) else None
        if application_scope is not None and any(not any(rule.tool == action.tool for rule in application_scope) for action in actions):
            raise _Invalid("application_scope_tool_conflict", "conflict")
        prohibitions = []
        application_constraints = {}
        hard = _keys((trusted_app_context or {}).get("hard_constraints", {}), {"prohibited_tools", "argument_constraints", "require_confirmation_tools"})
        prohibited_tools = hard.get("prohibited_tools", [])
        if not isinstance(prohibited_tools, list):
            raise _Invalid("invalid_application_prohibitions")
        for tool in prohibited_tools:
            tool = _identifier(tool)
            if tool not in tool_schemas:
                raise _Invalid("unknown_application_prohibited_tool")
            prohibitions.append(ContractProhibition(tool, {}, ()))
        for tool, raw_constraints in _keys(hard.get("argument_constraints", {}), set(tool_schemas)).items():
            application_constraints[tool] = {name: _predicate(raw_constraint) for name, raw_constraint in _keys(raw_constraints, set(tool_schemas[tool].get("arguments", {}))).items()}
        confirmation_tools = hard.get("require_confirmation_tools", [])
        if not isinstance(confirmation_tools, list) or set(confirmation_tools) - set(tool_schemas):
            raise _Invalid("invalid_application_confirmation_tools")
        actions = [replace(action, requires_confirmation=True) if action.tool in confirmation_tools else action for action in actions]
        calendar = _keys((trusted_app_context or {}).get("calendar_constraints", {}), {"start_min", "start_max", "end_min", "end_max", "duration_min", "duration_max"})
        for tool, schema in tool_schemas.items():
            for prefix, argument, operation in (("start", "start_time", "date_range"), ("end", "end_time", "date_range"), ("duration", "duration_minutes", "number_range")):
                if argument in schema.get("arguments", {}) and any(prefix + suffix in calendar for suffix in ("_min", "_max")):
                    predicate = {"op": operation, **{suffix: calendar[prefix + "_" + suffix] for suffix in ("min", "max") if prefix + "_" + suffix in calendar}}
                    application_constraints.setdefault(tool, {})[argument] = _predicate(predicate)
        raw_prohibitions = raw.get("prohibitions", [])
        if not isinstance(raw_prohibitions, list) or len(raw_prohibitions) > 64:
            raise _Invalid("invalid_prohibition_list")
        for item in raw_prohibitions:
            item = _keys(item, {"tool", "constraints", "evidence"}, {"tool", "constraints", "evidence"})
            tool = _identifier(item["tool"])
            if tool not in tool_schemas:
                raise _Invalid("unknown_prohibited_tool")
            evidence = _evidence(item["evidence"], request)
            quotes = " ".join(anchor.quote for anchor in evidence)
            if not _NEGATIVE.search(quotes):
                raise _Invalid("prohibition_without_negative_evidence", "conflict")
            constraints = {name: _predicate(value) for name, value in _keys(item["constraints"], set(tool_schemas[tool].get("arguments", {}))).items()}
            for predicate in constraints.values():
                _ground_literals(predicate, quotes, trusted_app_context or {})
            prohibitions.append(ContractProhibition(tool, constraints, evidence))
        external_forbidden = bool(re.search(r"(?:never|do\s+not|must\s+not)[^.；。]*\b(?:external|outside)\b[^.；。]*(?:recipient|send)|(?:never|do\s+not|must\s+not)[^.；。]*\bsend\b[^.；。]*\bexternal\b|禁止[^。；]*外部收件人", request, re.I))
        # 受信用户的显式禁止独立补齐；限定目标的禁止不能变成整个工具禁令。
        for clause in re.split(r"[.;!?。；！？\n]|\bbut\b|但是", request):
            if not _NEGATIVE.search(clause):
                continue
            for tool, schema in tool_schemas.items():
                try:
                    operation, _ = _catalog(tool, schema)
                except _Invalid:
                    continue
                if re.search(_INTENTS[operation], clause, re.I):
                    if not any(p.tool == tool and any(anchor.quote in clause for anchor in p.evidence) for p in prohibitions):
                        if operation == "send" and external_forbidden and re.search(r"external|外部", clause, re.I):
                            continue
                        if re.search(r"\b(to|on|into|within|outside)\b|收件人|非匹配|目标", clause, re.I):
                            raise _Invalid("qualified_prohibition_requires_explicit_scope", "missing")
                        start = request.find(clause)
                        prohibitions.append(ContractProhibition(tool, {}, (EvidenceAnchor(clause, start, start + len(clause)),)))
        for action in actions:
            for prohibition in prohibitions:
                if action.tool != prohibition.tool:
                    continue
                if not prohibition.constraints or (not action.bindings and all(name in action.constraints and action.constraints[name].op == "eq" and p.matches(action.constraints[name].value) for name, p in prohibition.constraints.items())):
                    raise _Invalid("trusted_user_prohibition_conflict", "conflict")
        rules = tuple(ToolRule(f"contract-{a.action_id}", a.tool, {name: _parameter(p, bool(tool_schemas[a.tool]["arguments"][name].get("required", False))) for name, p in a.constraints.items()}, requires_confirmation=a.requires_confirmation, side_effect=bool(tool_schemas[a.tool].get("side_effect", False))) for a in actions if not a.bindings)
        return TaskContractV1(replace(empty, rules=rules, manifest_sha256=""), tuple(actions), tuple(prohibitions), lexical_manifest=base, application_scope=application_scope, application_constraints=application_constraints,
                              prohibit_external_recipients=external_forbidden,
                              data_flow_policy=dict((trusted_app_context or {}).get("data_flow_policy", {})))
    except (ValueError, TypeError, KeyError) as exc:
        code = exc.code if isinstance(exc, _Invalid) else "malformed_draft"
        status = exc.status if isinstance(exc, _Invalid) else "invalid"
        return TaskContractV1(empty, diagnostics=(ContractDiagnostic(code, status),), status=status, lexical_manifest=base)


compile_generic_task_policy_corrected_v3 = compile_task_contract_v1
