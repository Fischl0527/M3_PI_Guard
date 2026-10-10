"""Strict JSON argument contracts shared by prospective repaired monitors."""

from __future__ import annotations

# 工具参数的格式检查，不是权限判断：字段、类型、枚举合法后还须经过监视器。
# bool 在 Python 中属于 int 的子类，此处用精确类型避免把 True 当作整数金额。

import json
import math
from typing import Any, Mapping


JSON_TYPES = frozenset({"string", "object", "array", "number", "integer", "boolean", "null"})


def _type_matches(value: Any, expected: str) -> bool:
    return {
        "string": isinstance(value, str), "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "number": type(value) is int or type(value) is float and math.isfinite(value),
        "integer": type(value) is int, "boolean": type(value) is bool,
        "null": value is None,
    }.get(expected, False)


def argument_contract_error(
    tool: str, arguments: Mapping[str, Any], schemas: Mapping[str, Mapping[str, Any]],
) -> str | None:
    """Return a bounded reason code, never an argument value or protected text."""
    if tool not in schemas:
        return "tool_schema_unavailable"
    if not isinstance(schemas[tool], Mapping):
        return "tool_schema_invalid"
    fields = schemas[tool].get("arguments")
    if not isinstance(fields, Mapping) or not isinstance(arguments, Mapping):
        return "tool_schema_invalid"
    if any(not isinstance(name, str) for name in (*arguments, *fields)):
        return "tool_schema_invalid"
    if set(arguments) - set(fields):
        # 额外字段可能携带新目标，不能静默丢弃后再放行原提案。
        return "undeclared_argument"
    try:
        json.dumps(dict(arguments), allow_nan=False)
    except (TypeError, ValueError):
        return "non_json_argument"
    for name, detail in fields.items():
        if not isinstance(detail, Mapping):
            return "tool_schema_invalid"
        expected = detail.get("type")
        types = [expected] if isinstance(expected, str) else expected
        if not isinstance(types, list) or not types or any(not isinstance(t, str) or t not in JSON_TYPES for t in types):
            return "unsupported_argument_type"
        if "enum" in detail and not isinstance(detail["enum"], list):
            return "tool_schema_invalid"
        if detail.get("required") is True and name not in arguments:
            return "missing_required_argument"
        if name in arguments:
            if not any(_type_matches(arguments[name], t) for t in types):
                return "argument_type_mismatch"
            if "enum" in detail:
                try:
                    candidate = json.dumps(arguments[name], sort_keys=True, allow_nan=False)
                    choices = [json.dumps(value, sort_keys=True, allow_nan=False) for value in detail["enum"]]
                except (TypeError, ValueError):
                    return "tool_schema_invalid"
                if candidate not in choices:
                    return "argument_enum_mismatch"
    return None
