"""Opt-in repair of generic argument literals; no change to historical v1.

Lexical tool selection remains deliberately bounded. Ambiguous prose is not an
authorization literal: an unresolved target never produces an automatic grant,
including when the optional confirmation module is disabled.
"""
from __future__ import annotations

# 通用工具的第二版修复：只把明确写出的目标值编译成精确参数。
# 无法确定的安全目标不变成通配许可；正文内容可生成，接收者/路径等不能猜。

import re
from dataclasses import replace
from typing import Any, Mapping

from m3_core import policy_compiler as legacy
from m3_core.policy_compiler_corrected_v1 import compile_generic_task_policy_corrected_v1
from m3_guard.task_policy import ParameterConstraint, TaskPolicyManifest


# 内容可由模型生成；其他未解析字段不当成任意目标许可。
CONTENT_ARGUMENTS = frozenset({"content", "body", "subject", "text", "message"})


def _explicit_literal(request: str, name: str, argument_type: str) -> Any | None:
    tokens = set(re.findall(r"[a-z0-9]+", name.casefold()))
    if tokens & {"email", "recipient", "recipients", "address", "to", "participants", "endpoint", "url", "path", "file"}:
        return legacy._explicit_argument_value(request, name, argument_type)
    phrase = re.escape(re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).replace("_", " "))
    phrase = phrase.replace(r"\ ", r"\s+")
    # 引号界定完整参数值，其中的空格或 and 不再被误拆成多个动作。
    quoted = re.search(
        rf"\b{phrase}\b\s*(?:(?:is|=|:)\s*)?([\"'])(.*?)\1",
        request, re.IGNORECASE,
    )
    if quoted:
        candidate = quoted.group(2)
    else:
        # 无引号时只接受冒号/等号赋值；普通叙述里的 channel and 等不能当目标值。
        match = re.search(
            rf"\b{phrase}\b\s*[:=]\s*([A-Za-z0-9_@+#/.-]+?)(?=[,;.!?](?:\s|$)|$)",
            request, re.IGNORECASE,
        )
        if match is None:
            return None
        candidate = match.group(1)
    if argument_type == "integer":
        return int(candidate) if re.fullmatch(r"-?\d+", candidate) else None
    if argument_type == "number":
        return float(candidate) if re.fullmatch(r"-?\d+(?:\.\d+)?", candidate) else None
    return candidate if argument_type == "string" else None


def compile_generic_task_policy_corrected_v2(
    *, trusted_user_request: str, tool_schemas: Mapping[str, Mapping[str, Any]],
    trusted_app_context: Mapping[str, Any] | None = None,
    manifest_id: str | None = None, generated_at: str | None = None,
    max_tools: int = 6,
) -> TaskPolicyManifest:
    base = compile_generic_task_policy_corrected_v1(
        trusted_user_request=trusted_user_request, tool_schemas=tool_schemas,
        trusted_app_context=trusted_app_context, manifest_id=manifest_id,
        generated_at=generated_at, max_tools=max_tools,
    )
    if "requested_actions" in (trusted_app_context or {}):
        # 应用已经声明的权限不能再被词法猜测覆盖或扩大。
        return base
    rules = []
    for rule in base.rules:
        schema = tool_schemas[rule.tool]
        constraints = dict(rule.argument_constraints)
        unresolved_required_scope = False
        for name, old in rule.argument_constraints.items():
            detail = schema.get("arguments", {}).get(name, {})
            argument_type = str(detail.get("type", "object"))
            value = _explicit_literal(trusted_user_request, name, argument_type)
            if value is None and name not in CONTENT_ARGUMENTS:
                # 必需目标未解析时，后续不能通过关闭确认模块获得自动执行许可。
                unresolved_required_scope |= old.required
                # 未请求的可选安全字段不得携带新目标；仅允许省略或明确接口默认值。
                constraints[name] = ParameterConstraint(
                    "exact" if "default" in detail else "enum",
                    detail.get("default") if "default" in detail else (),
                    required=old.required, description="Unresolved security scope; no automatic grant",
                )
            else:
                constraints[name] = ParameterConstraint(
                    "type" if value is None else "exact",
                    argument_type if value is None else value,
                    required=old.required,
                    description="Explicit delimited literal" if value is not None else "Generated content; schema boundary only",
                )
        if unresolved_required_scope:
            continue
        rules.append(replace(
            rule, rule_id=f"{rule.rule_id}-generic-v2",
            argument_constraints=constraints,
            requires_confirmation=rule.requires_confirmation,
            description=rule.description + " Generic-v2: prose is not an exact literal.",
        ))
    return replace(base, rules=tuple(rules), manifest_sha256="")
