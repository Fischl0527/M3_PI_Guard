"""Opt-in, bounded action/resource compiler; historical compilers are unchanged.

This is a conservative lexical compiler, not a general natural-language parser.
Unresolved resources create no automatic grant. Explicit trusted declarations
replace inferred grants, and contradictory negative instructions are rejected.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Mapping

from m3_core import policy_compiler as legacy
from m3_guard.task_policy import (
    DataFlowConstraint,
    ParameterConstraint,
    TaskPolicyManifest,
    TemporalConstraint,
    ToolRule,
    sha256_json,
)

COMPILER_VERSION = "corrected_v1"
_ACTION = re.compile(
    r"(?P<read>\b(?:read|open|load|summari[sz]e|inspect|review)\b|读取|打开|总结|摘要|审阅)"
    r"|(?P<write>\b(?:write|save|store|create)\b|写入|保存|存储|创建)"
    r"|(?P<send>\b(?:send|email|mail|forward)\b|发送邮件|发邮件|转发)"
    r"|(?P<api>\b(?:call|query|request)\b|调用)"
    r"|(?P<code>\b(?:run|execute)\b|运行代码|执行脚本)",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(?:not|never|avoid|without|don't|do\s+not|must\s+not|cannot|can't)\b"
    r"|不要|禁止|不得|不能|勿|不许",
    re.IGNORECASE,
)
_UNCERTAIN = re.compile(
    r"\b(?:maybe|perhaps|possibly|if|unless|either|or|optional|might|whether)\b"
    r"|可能|也许|如果|或者|或|是否",
    re.IGNORECASE,
)
_TOOL = {
    "read": "read_file",
    "write": "write_file",
    "send": "send_email",
    "api": "call_api",
    "code": "run_code",
}
_RESOURCE = {
    "read": legacy._PATH_RE,
    "write": legacy._PATH_RE,
    "send": legacy._EMAIL_RE,
    "api": legacy._ENDPOINT_RE,
}


def _without_resources(text: str) -> str:
    """Keep modifier positions, but do not parse words inside resource names."""
    chars = list(text)
    for pattern in (legacy._PATH_RE, legacy._EMAIL_RE, legacy._ENDPOINT_RE):
        for match in pattern.finditer(text):
            chars[match.start() : match.end()] = " " * (match.end() - match.start())
    return "".join(chars)


def _actions(request: str) -> list[tuple[str, int, int, bool]]:
    resource_spans = [
        match.span()
        for pattern in (legacy._PATH_RE, legacy._EMAIL_RE, legacy._ENDPOINT_RE)
        for match in pattern.finditer(request)
    ]
    result = []
    for match in _ACTION.finditer(request):
        if any(start <= match.start() < end for start, end in resource_spans):
            continue
        # A new clause/action resets negation. No arbitrary distance cutoff.
        prefix = request[result[-1][2] if result else 0 : match.start()]
        clauses = re.split(r"\.(?:\s+|$)|[;!?。；！？\n]|\bbut\b|但是|但", prefix)
        prefix = _without_resources(clauses[-1])
        inherited_negative = bool(result and result[-1][3] and len(clauses) == 1)
        result.append(
            (
                str(match.lastgroup),
                match.start(),
                match.end(),
                bool(_NEGATION.search(prefix)) or inherited_negative,
            )
        )
    return result


def _action_segment(request: str, end: int, stop: int) -> str:
    segment = re.split(r"[;!?。；！？\n]", request[end:stop], maxsplit=1)[0]
    # A sentence terminator is a dot followed by whitespace, not a file suffix.
    return re.split(r"\.\s+", segment, maxsplit=1)[0]


def _negative_tools(
    request: str, actions: list[tuple[str, int, int, bool]]
) -> set[str]:
    negative = {_TOOL[kind] for kind, _, _, negated in actions if negated}
    for index, (kind, _, end, _) in enumerate(actions):
        stop = actions[index + 1][1] if index + 1 < len(actions) else len(request)
        segment = _action_segment(request, end, stop)
        for match in _NEGATION.finditer(_without_resources(segment)):
            if (
                index + 1 < len(actions)
                and segment == request[end:stop]
                and not segment[match.end() :].strip()
            ):
                # In "read A, do not write B", the dangling denial belongs to
                # the next action (already handled by _actions), not the read.
                continue
            # The public contract has no resource-level deny rule. Keep the
            # existing conservative policy: a mixed positive/negative action
            # receives no automatic grant, including a shared read/write target.
            negative.add(_TOOL[kind])
            previous = index - 1
            while previous >= 0 and kind in {"read", "write"}:
                prior_kind, _, prior_end, _ = actions[previous]
                bridge = request[prior_end : actions[previous + 1][1]].strip()
                if prior_kind not in {"read", "write"} or not re.fullmatch(
                    r"(?:and|及|和|并|并且)", bridge, re.IGNORECASE
                ):
                    break
                negative.add(_TOOL[prior_kind])
                previous -= 1
    return negative


def _resource_rules(
    request: str, schemas: Mapping[str, Mapping[str, Any]]
) -> list[ToolRule]:
    actions = _actions(request)
    result: list[ToolRule] = []
    for index, (kind, start, end, negated) in enumerate(actions):
        if kind not in _RESOURCE:
            continue  # Code execution is never inferred as an automatic grant.
        stop = actions[index + 1][1] if index + 1 < len(actions) else len(request)
        segment = _action_segment(request, end, stop)
        resources = list(_RESOURCE[kind].finditer(segment))
        prefix = request[actions[index - 1][2] if index else 0 : start]
        prefix = re.split(r"\.(?:\s+|$)|[;!?。；！？\n]|\bbut\b|但是|但", prefix)[-1]
        if _UNCERTAIN.search(_without_resources(prefix + " " + segment)):
            continue
        group = [(kind, negated)]
        previous = index - 1
        while previous >= 0 and kind in {"read", "write"}:
            prior_kind, _, prior_end, prior_negative = actions[previous]
            bridge = request[prior_end : actions[previous + 1][1]].strip()
            if prior_kind not in {"read", "write"} or not re.fullmatch(
                r"(?:and|及|和|并|并且)", bridge, re.IGNORECASE
            ):
                break
            group.append((prior_kind, prior_negative))
            previous -= 1
        for resource in resources:
            value = resource.group(0)
            for group_kind, denied in group:
                tool = _TOOL[group_kind]
                if denied or tool not in schemas:
                    continue
                if group_kind in {"read", "write"}:
                    constraints = {
                        "path": ParameterConstraint(
                            "exact", legacy._normalize_path(value)
                        )
                    }
                    if group_kind == "write":
                        constraints["content"] = ParameterConstraint("type", "string")
                elif group_kind == "send":
                    constraints = {
                        "to": ParameterConstraint("exact", value),
                        "subject": ParameterConstraint("type", "string"),
                        "body": ParameterConstraint("type", "string"),
                    }
                else:
                    constraints = {
                        "endpoint": ParameterConstraint(
                            "exact", value.rstrip(".,;:!?")
                        ),
                        "params": ParameterConstraint("type", "object", required=False),
                    }
                result.append(
                    legacy._rule(
                        tool,
                        constraints,
                        schemas,
                        description="corrected_v1: resource bound to its explicit trusted action.",
                    )
                )
    # A negative mention wins for the same tool/resource; there is no deny rule
    # in the public manifest contract. Conservatively suppress that tool if the
    # natural-language request mixes positive and negative grants for it.
    negative_tools = _negative_tools(request, actions)
    return [rule for rule in result if rule.tool not in negative_tools]


def _declarations(
    context: Mapping[str, Any], request: str, schemas: Mapping[str, Mapping[str, Any]]
) -> tuple[ToolRule, ...]:
    rules = legacy._structured_rules(context, schemas)
    negative_tools = _negative_tools(request, _actions(request))
    if any(rule.tool in negative_tools for rule in rules):
        raise ValueError(
            "trusted requested_actions conflicts with a negative user instruction"
        )
    # Retain duplicate-scope restrictions rather than silently dropping a stricter
    # declaration whose legacy rule_id depends only on its argument constraints.
    result: list[ToolRule] = []
    for index, rule in enumerate(rules):
        result.append(replace(rule, rule_id=f"{rule.rule_id}-decl-{index}"))
    return tuple(result)


def compile_task_policy_corrected_v1(
    *,
    trusted_user_request: str,
    tool_schemas: Mapping[str, Mapping[str, Any]] | None = None,
    trusted_app_context: Mapping[str, Any] | None = None,
    manifest_id: str | None = None,
    generated_at: str | None = None,
) -> TaskPolicyManifest:
    request = str(trusted_user_request).strip()
    if not request:
        raise ValueError("trusted_user_request must not be empty")
    schemas = dict(
        legacy.DEFAULT_TOOL_SCHEMAS if tool_schemas is None else tool_schemas
    )
    context = dict(trusted_app_context or {})
    legacy._reject_evaluator_fields(context)
    rules = (
        _declarations(context, request, schemas)
        if "requested_actions" in context
        else legacy._deduplicate_rules(_resource_rules(request, schemas))
    )
    temporal: list[TemporalConstraint] = []
    tools = {rule.tool for rule in rules}
    kinds = [kind for kind, _, _, negative in _actions(request) if not negative]
    if re.search(r"\bthen\b|之后|然后|再", request, re.IGNORECASE) and "read" in kinds:
        for following, tool in (("write", "write_file"), ("send", "send_email")):
            if (
                tool in tools
                and "read_file" in tools
                and following in kinds
                and kinds.index("read") < kinds.index(following)
            ):
                temporal.append(
                    TemporalConstraint(
                        f"corrected-read-before-{following}",
                        tool,
                        ("read_file",),
                        "Trusted request explicitly orders reading before this action.",
                    )
                )
    sensitive = bool(
        re.search(
            r"\b(private|secret|confidential|sensitive)\b|私密|秘密|机密|敏感",
            request,
            re.IGNORECASE,
        )
    )
    request_hash = sha256_json(
        {"trusted_user_request": request, "trusted_app_context": context}
    )
    return TaskPolicyManifest(
        manifest_id=manifest_id or f"corrected-policy-{request_hash[:16]}",
        policy_source=("trusted_user_request", "trusted_application_context")
        if context
        else ("trusted_user_request",),
        trusted_request_sha256=request_hash,
        tool_schema_sha256=sha256_json(schemas),
        rules=rules,
        temporal_constraints=tuple(temporal),
        dataflow_constraints=(
            DataFlowConstraint(
                "flow-private-to-untrusted-target",
                "private",
                forbidden_target_patterns=(
                    r"attacker",
                    r"redteam",
                    r"evil",
                    r"/mock/internal/export",
                ),
                description="Legacy bounded destination policy; not a general DLP guarantee.",
            ),
        )
        if sensitive
        else (),
        sensitive_data_labels=("private",) if sensitive else (),
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
    )


def compile_generic_task_policy_corrected_v1(
    *,
    trusted_user_request: str,
    tool_schemas: Mapping[str, Mapping[str, Any]],
    trusted_app_context: Mapping[str, Any] | None = None,
    manifest_id: str | None = None,
    generated_at: str | None = None,
    max_tools: int = 6,
) -> TaskPolicyManifest:
    """Keep generic lexical ranking, but explicit declarations replace inference.

    Generic intent ranking is not claimed to solve arbitrary action/resource
    binding. The development results must distinguish it from the file compiler.
    """
    context = dict(trusted_app_context or {})
    base = legacy.compile_generic_task_policy(
        trusted_user_request=trusted_user_request,
        tool_schemas=tool_schemas,
        trusted_app_context=context,
        manifest_id=manifest_id,
        generated_at=generated_at,
        max_tools=max_tools,
    )
    if "requested_actions" not in context:
        return base
    return replace(
        base,
        rules=_declarations(context, trusted_user_request, tool_schemas),
        manifest_sha256="",
    )
