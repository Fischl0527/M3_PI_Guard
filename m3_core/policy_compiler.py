"""Conservative TaskPolicyManifest compiler for the paper-v1 runtime.

Only the trusted user request, trusted application context and tool schemas are
accepted.  Evaluator fields are rejected even when nested so a dataset adapter
cannot accidentally turn gold labels into online permission.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from m3_guard.task_policy import (
    DataFlowConstraint,
    ParameterConstraint,
    TaskPolicyManifest,
    TemporalConstraint,
    ToolRule,
    sha256_json,
)


FORBIDDEN_POLICY_INPUT_KEYS = frozenset(
    {
        "authorized_actions",
        "requires_tool",
        "sample_type",
        "attack_family",
        "unsafe_target_actions",
        "target_action",
        "expected_answer",
        "expected_safe_behavior",
        "expected_detectors",
        "success_indicators",
        "safe_indicators",
        "risk_tags",
        "label",
        "gold",
    }
)

DEFAULT_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "read_file": {
        "arguments": {"path": {"type": "string", "required": True}},
        "side_effect": False,
    },
    "write_file": {
        "arguments": {
            "path": {"type": "string", "required": True},
            "content": {"type": "string", "required": True},
        },
        "side_effect": True,
    },
    "send_email": {
        "arguments": {
            "to": {"type": "string", "required": True},
            "subject": {"type": "string", "required": True},
            "body": {"type": "string", "required": True},
        },
        "side_effect": True,
    },
    "call_api": {
        "arguments": {
            "endpoint": {"type": "string", "required": True},
            "params": {"type": "object", "required": False},
        },
        "side_effect": True,
    },
    "run_code": {
        "arguments": {"code": {"type": "string", "required": True}},
        "side_effect": True,
    },
    "final": {
        "arguments": {"answer": {"type": "string", "required": True}},
        "side_effect": False,
    },
}

_PATH_RE = re.compile(r"(?:sandbox[\\/])?public[\\/][\w.\-/\\]+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_ENDPOINT_RE = re.compile(r"/mock/[A-Za-z0-9_./-]+")


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key).casefold()
            yield from _walk_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk_keys(child)


def _reject_evaluator_fields(context: Mapping[str, Any]) -> None:
    keys = set(_walk_keys(context))
    found = sorted(
        key
        for key in keys
        if key in FORBIDDEN_POLICY_INPUT_KEYS
        or key.startswith(("expected_", "attacker_", "ground_truth", "gold_"))
    )
    if found:
        raise ValueError(
            "trusted_app_context contains evaluator/gold fields: " + ", ".join(found)
        )


def _normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/").rstrip(".,;:!?)）】]")
    if not normalized.casefold().startswith("sandbox/"):
        normalized = f"sandbox/{normalized}"
    return normalized


def _rule_id(tool: str, constraints: Mapping[str, ParameterConstraint]) -> str:
    payload = {
        "tool": tool,
        "constraints": {key: value.to_dict() for key, value in constraints.items()},
    }
    return f"rule-{tool}-{sha256_json(payload)[:12]}"


def _rule(
    tool: str,
    constraints: Mapping[str, ParameterConstraint],
    schemas: Mapping[str, Mapping[str, Any]],
    *,
    requires_confirmation: bool = False,
    description: str,
) -> ToolRule:
    if tool not in schemas:
        raise ValueError(f"trusted task requests unavailable tool: {tool}")
    return ToolRule(
        rule_id=_rule_id(tool, constraints),
        tool=tool,
        argument_constraints=dict(constraints),
        requires_confirmation=requires_confirmation,
        side_effect=bool(schemas[tool].get("side_effect", False)),
        description=description,
    )


def _structured_rules(
    context: Mapping[str, Any],
    schemas: Mapping[str, Mapping[str, Any]],
) -> list[ToolRule]:
    declarations = context.get("requested_actions", [])
    if declarations is None:
        return []
    if not isinstance(declarations, list):
        raise ValueError("trusted requested_actions must be a list")
    rules: list[ToolRule] = []
    for index, declaration in enumerate(declarations):
        if not isinstance(declaration, Mapping):
            raise ValueError(f"requested_actions[{index}] must be an object")
        tool = str(declaration.get("tool", "")).strip()
        arguments = declaration.get("arguments", {})
        if not isinstance(arguments, Mapping):
            raise ValueError(f"requested_actions[{index}].arguments must be an object")
        constraints = {
            str(key): ParameterConstraint(kind="exact", value=value)
            for key, value in arguments.items()
        }
        rules.append(
            _rule(
                tool,
                constraints,
                schemas,
                requires_confirmation=bool(declaration.get("requires_confirmation", False)),
                description="Explicit trusted application action declaration.",
            )
        )
    return rules


def _deduplicate_rules(rules: Iterable[ToolRule]) -> tuple[ToolRule, ...]:
    seen: set[str] = set()
    result: list[ToolRule] = []
    for rule in rules:
        if rule.rule_id in seen:
            continue
        seen.add(rule.rule_id)
        result.append(rule)
    return tuple(result)


def compile_task_policy(
    *,
    trusted_user_request: str,
    tool_schemas: Mapping[str, Mapping[str, Any]] | None = None,
    trusted_app_context: Mapping[str, Any] | None = None,
    manifest_id: str | None = None,
    generated_at: str | None = None,
) -> TaskPolicyManifest:
    """Compile a least-privilege policy before observing external content."""

    request = str(trusted_user_request).strip()
    if not request:
        raise ValueError("trusted_user_request must not be empty")
    schemas = dict(tool_schemas or DEFAULT_TOOL_SCHEMAS)
    app_context = dict(trusted_app_context or {})
    _reject_evaluator_fields(app_context)
    lowered = request.casefold()
    rules: list[ToolRule] = _structured_rules(app_context, schemas)

    paths = [_normalize_path(match.group(0)) for match in _PATH_RE.finditer(request)]
    write_requested = bool(
        re.search(r"\b(write|save|store|create)\b|写入|保存|存储|创建", lowered)
    )
    read_requested = bool(
        re.search(r"\b(read|open|load|summari[sz]e|inspect|review)\b|读取|打开|总结|摘要|审阅", lowered)
    )
    for path in paths:
        if write_requested:
            rules.append(
                _rule(
                    "write_file",
                    {
                        "path": ParameterConstraint("exact", path),
                        "content": ParameterConstraint("type", "string"),
                    },
                    schemas,
                    description="File destination explicitly named by the trusted requester.",
                )
            )
        elif read_requested:
            rules.append(
                _rule(
                    "read_file",
                    {"path": ParameterConstraint("exact", path)},
                    schemas,
                    description="File source explicitly named by the trusted requester.",
                )
            )

    if write_requested and not paths and not any(rule.tool == "write_file" for rule in rules):
        rules.append(
            _rule(
                "write_file",
                {
                    "path": ParameterConstraint("type", "string"),
                    "content": ParameterConstraint("type", "string"),
                },
                schemas,
                requires_confirmation=True,
                description="File-write intent is trusted but the resource is underspecified.",
            )
        )

    email_requested = bool(
        re.search(r"\b(send|email|mail|forward)\b|发送邮件|发邮件|转发", lowered)
    )
    emails = list(dict.fromkeys(match.group(0) for match in _EMAIL_RE.finditer(request)))
    if email_requested:
        if emails:
            for address in emails:
                rules.append(
                    _rule(
                        "send_email",
                        {
                            "to": ParameterConstraint("exact", address),
                            "subject": ParameterConstraint("type", "string"),
                            "body": ParameterConstraint("type", "string"),
                        },
                        schemas,
                        description="Email recipient explicitly named by the trusted requester.",
                    )
                )
        else:
            rules.append(
                _rule(
                    "send_email",
                    {
                        "to": ParameterConstraint("type", "string"),
                        "subject": ParameterConstraint("type", "string"),
                        "body": ParameterConstraint("type", "string"),
                    },
                    schemas,
                    requires_confirmation=True,
                    description="Email intent is trusted but the recipient is underspecified.",
                )
            )

    api_requested = bool(
        re.search(r"\b(api|endpoint|request|query)\b|接口|调用", lowered)
    )
    endpoints = list(dict.fromkeys(match.group(0) for match in _ENDPOINT_RE.finditer(request)))
    if api_requested:
        if endpoints:
            for endpoint in endpoints:
                rules.append(
                    _rule(
                        "call_api",
                        {
                            "endpoint": ParameterConstraint("exact", endpoint),
                            "params": ParameterConstraint("type", "object", required=False),
                        },
                        schemas,
                        description="Mock API endpoint explicitly named by the trusted requester.",
                    )
                )
        else:
            rules.append(
                _rule(
                    "call_api",
                    {
                        "endpoint": ParameterConstraint("type", "string"),
                        "params": ParameterConstraint("type", "object", required=False),
                    },
                    schemas,
                    requires_confirmation=True,
                    description="API intent is trusted but the endpoint is underspecified.",
                )
            )

    if re.search(r"\b(run|execute)\s+(the\s+)?(code|script)\b|运行代码|执行脚本", lowered):
        rules.append(
            _rule(
                "run_code",
                {"code": ParameterConstraint("type", "string")},
                schemas,
                requires_confirmation=True,
                description="Code execution always requires explicit confirmation.",
            )
        )

    compiled_rules = _deduplicate_rules(rules)
    temporal: list[TemporalConstraint] = []
    tools = {rule.tool for rule in compiled_rules}
    sequence_word = bool(re.search(r"\bthen\b|之后|然后|再", lowered))
    if sequence_word and "read_file" in tools and "send_email" in tools:
        temporal.append(
            TemporalConstraint(
                constraint_id="temporal-read-before-send",
                tool="send_email",
                must_follow_tools=("read_file",),
                description="Trusted request requires reading before sending.",
            )
        )
    if sequence_word and "read_file" in tools and "write_file" in tools:
        temporal.append(
            TemporalConstraint(
                constraint_id="temporal-read-before-write",
                tool="write_file",
                must_follow_tools=("read_file",),
                description="Trusted request requires reading before writing.",
            )
        )

    sensitive = bool(
        re.search(r"\b(private|secret|confidential|sensitive)\b|私密|秘密|机密|敏感", lowered)
    )
    dataflow = (
        DataFlowConstraint(
            constraint_id="flow-private-to-untrusted-target",
            data_label="private",
            forbidden_target_patterns=(
                r"attacker",
                r"redteam",
                r"evil",
                r"/mock/internal/export",
            ),
            description="Private task data cannot flow to an untrusted destination.",
        ),
    ) if sensitive else ()

    request_hash = sha256_json({"trusted_user_request": request, "trusted_app_context": app_context})
    schema_hash = sha256_json(schemas)
    return TaskPolicyManifest(
        manifest_id=manifest_id or f"policy-{request_hash[:16]}",
        policy_source=(
            ("trusted_user_request", "trusted_application_context")
            if app_context
            else ("trusted_user_request",)
        ),
        trusted_request_sha256=request_hash,
        tool_schema_sha256=schema_hash,
        rules=compiled_rules,
        temporal_constraints=tuple(temporal),
        dataflow_constraints=dataflow,
        sensitive_data_labels=("private",) if sensitive else (),
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
    )


_GENERIC_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for",
        "from", "get", "i", "in", "is", "it", "me", "my", "of", "on", "or",
        "please", "the", "this", "to", "tool", "use", "with", "you",
    }
)

_TOKEN_CANONICAL = {
    "appointments": "calendar",
    "appointment": "calendar",
    "calendars": "calendar",
    "classes": "calendar",
    "class": "calendar",
    "events": "calendar",
    "event": "calendar",
    "meetings": "calendar",
    "meeting": "calendar",
    "day": "date",
    "days": "date",
    "dates": "date",
    "time": "date",
    "times": "date",
    "addresses": "address",
    "emails": "email",
    "mails": "email",
    "contacts": "contact",
    "people": "contact",
    "persons": "contact",
    "recipients": "recipient",
    "files": "file",
    "documents": "file",
    "document": "file",
    "drive": "file",
    "txt": "file",
    "pdf": "file",
    "csv": "file",
    "transactions": "finance",
    "transaction": "finance",
    "payments": "finance",
    "payment": "finance",
    "spending": "finance",
    "bill": "finance",
    "money": "finance",
    "balance": "finance",
    "products": "product",
    "reviews": "review",
}

_MONTH_TOKENS = frozenset(
    {
        "january", "february", "march", "april", "may", "june", "july",
        "august", "september", "october", "november", "december",
    }
)

_TOOL_ACTION_TOKENS = frozenset(
    {
        "add", "append", "book", "cancel", "create", "delete", "find", "get",
        "invite", "list", "lookup", "pay", "read", "remove", "reserve",
        "reschedule", "schedule", "search", "send", "share", "transfer",
        "update", "write",
    }
)

_READ_ACTIONS = frozenset({"find", "get", "list", "lookup", "read", "search"})
_MUTATING_ACTIONS = _TOOL_ACTION_TOKENS - _READ_ACTIONS

_ACTION_PATTERNS = {
    "add": r"\badd\b",
    "append": r"\bappend\b",
    "cancel": r"\bcancel\b",
    "create": r"\b(?:create|make)\b",
    "delete": r"\b(?:delete|remove)\b",
    "invite": r"\binvite\b",
    "pay": r"\bpay\b",
    "reschedule": r"\b(?:reschedule|move)\b",
    "schedule": r"\b(?:schedule|book|reserve)\b",
    "send": (
        r"\b(?:send|mail|forward)\b|"
        r"(?:^|[.;]\s*|\bplease\s+)email\s+(?!address(?:es)?\b)|"
        r"\bemail\b(?=\s+(?:me|us|him|her|them|the\b|[A-Z0-9._%+-]+@))"
    ),
    "share": r"\bshare\b",
    "transfer": r"\btransfer\b",
    "update": r"\b(?:update|edit|modify|change)\b",
    "write": r"\b(?:write|save|store)\b",
}

_ACTION_COMPATIBILITY = {
    "add": frozenset({"add", "invite"}),
    "append": frozenset({"append", "write"}),
    "book": frozenset({"schedule"}),
    "cancel": frozenset({"cancel"}),
    "create": frozenset({"create", "schedule"}),
    "delete": frozenset({"delete"}),
    "invite": frozenset({"add", "invite"}),
    "pay": frozenset({"pay", "transfer"}),
    "remove": frozenset({"delete"}),
    "reserve": frozenset({"schedule"}),
    "reschedule": frozenset({"reschedule", "update"}),
    "schedule": frozenset({"schedule"}),
    "send": frozenset({"send", "pay", "transfer"}),
    "share": frozenset({"share"}),
    "transfer": frozenset({"pay", "send", "transfer"}),
    "update": frozenset({"reschedule", "update"}),
    "write": frozenset({"append", "write"}),
}


def _lexical_tokens(value: str) -> set[str]:
    raw_value = str(value)
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", raw_value)
    expanded = expanded.replace("_", " ").replace("-", " ")
    tokens = {
        _TOKEN_CANONICAL.get(token, "date" if token in _MONTH_TOKENS else token)
        for token in re.findall(r"[a-z0-9]+", expanded.casefold())
        if len(token) > 1 and token not in _GENERIC_STOPWORDS
    }
    if re.search(r"\b\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?\b|\b\d{1,2}(?:st|nd|rd|th)\b", raw_value, re.IGNORECASE):
        tokens.add("date")
    return tokens


def _ordered_lexical_tokens(value: str) -> list[str]:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(value))
    expanded = expanded.replace("_", " ").replace("-", " ")
    return [
        _TOKEN_CANONICAL.get(token, "date" if token in _MONTH_TOKENS else token)
        for token in re.findall(r"[a-z0-9]+", expanded.casefold())
        if len(token) > 1 and token not in _GENERIC_STOPWORDS
    ]


def _positive_directive_text(request: str) -> str:
    """Remove explicit negative scopes before detecting requested side effects."""

    text = re.sub(
        r"\b(?:without|avoid(?:ing)?|refrain(?:ing)?\s+from)\b[^,.;]*",
        " ",
        request,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?:^|(?<=[.;]))\s*(?:do\s+not|don't|never)\b[^.;]*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _request_action_intents(request: str) -> set[str]:
    positive = _positive_directive_text(request)
    return {
        action
        for action, pattern in _ACTION_PATTERNS.items()
        if re.search(pattern, positive, flags=re.IGNORECASE)
    }


def _tool_action(tool: str) -> str:
    for token in _ordered_lexical_tokens(tool):
        if token in _TOOL_ACTION_TOKENS:
            return token
    return "read"


def _tool_domain_tokens(tool: str) -> set[str]:
    return _lexical_tokens(tool) - _TOOL_ACTION_TOKENS - {"tool"}


def _informational_request(request: str) -> bool:
    return bool(
        re.search(
            r"\b(?:what|when|where|who|which|how|find|fetch|get|list|look\s+up|"
            r"search|show|summari[sz]e|tell|check|read|review|retrieve)\b",
            request,
            flags=re.IGNORECASE,
        )
    )


def _action_matches_request(tool_action: str, request_actions: set[str]) -> bool:
    if tool_action in _READ_ACTIONS:
        return True
    accepted = _ACTION_COMPATIBILITY.get(tool_action, frozenset({tool_action}))
    return bool(accepted & request_actions)


def _generic_tool_score(
    request: str,
    request_tokens: set[str],
    request_actions: set[str],
    tool: str,
    schema: Mapping[str, Any],
) -> float:
    name_tokens = _lexical_tokens(tool)
    description_tokens = _lexical_tokens(str(schema.get("description", "")))
    tool_action = _tool_action(tool)
    if not _action_matches_request(tool_action, request_actions):
        return -1.0
    action_tokens = _TOOL_ACTION_TOKENS | frozenset({"tool"})
    request_domains = request_tokens - action_tokens
    name_domains = name_tokens - action_tokens
    description_domains = description_tokens - action_tokens
    score = (
        2.25 * len(request_tokens & name_tokens)
        + 0.25 * len(request_tokens & description_tokens)
        + 2.0 * len(request_domains & name_domains)
        + 0.5 * len(request_domains & description_domains)
    )
    if tool_action in _READ_ACTIONS and _informational_request(request):
        score += 1.25
    if tool_action not in _READ_ACTIONS:
        score += 2.5
    return score


def _explicit_argument_value(
    request: str,
    argument_name: str,
    argument_type: str,
) -> Any | None:
    lowered_name = argument_name.casefold()
    name_tokens = set(re.findall(r"[a-z0-9]+", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", argument_name).casefold()))
    if name_tokens & {"email", "recipient", "recipients", "address", "to", "participants"}:
        matches = list(dict.fromkeys(match.group(0) for match in _EMAIL_RE.finditer(request)))
        if not matches:
            return None
        return matches if argument_type == "array" else matches[0]
    if "endpoint" in lowered_name or lowered_name == "url":
        match = re.search(r"/(?:mock|api)/[A-Za-z0-9_./-]+", request)
        return match.group(0) if match else None
    if "path" in lowered_name or "file" in lowered_name:
        match = _PATH_RE.search(request)
        return _normalize_path(match.group(0)) if match else None

    expanded_name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", argument_name).replace("_", " ")
    phrase = " ".join(
        token
        for token in re.findall(r"[a-z0-9]+", expanded_name.casefold())
        if token not in _GENERIC_STOPWORDS
    )
    if phrase:
        # Python 3.10/3.11 forbid backslashes inside an f-string expression.
        # Compute the same regex fragment separately; authorization is unchanged.
        phrase_pattern = re.escape(phrase).replace(r"\ ", r"\s+")
        pattern = re.compile(
            rf"\b{phrase_pattern}\b\s*(?:is|=|:|number)?\s*[\"']?([A-Za-z0-9_.@+-]+)",
            flags=re.IGNORECASE,
        )
        match = pattern.search(request)
        if match:
            candidate = match.group(1)
            if argument_type == "integer" and candidate.isdigit():
                return int(candidate)
            if argument_type == "number":
                try:
                    return float(candidate)
                except ValueError:
                    return None
            return candidate
    return None


def compile_generic_task_policy(
    *,
    trusted_user_request: str,
    tool_schemas: Mapping[str, Mapping[str, Any]],
    trusted_app_context: Mapping[str, Any] | None = None,
    manifest_id: str | None = None,
    generated_at: str | None = None,
    max_tools: int = 6,
) -> TaskPolicyManifest:
    """Compile a non-gold lexical policy for arbitrary benchmark tool names.

    This is intentionally a measurable baseline compiler, not an oracle.  It
    ranks tools only from the trusted request and public tool descriptions;
    official task ground truths and attacker labels are absent from the API.
    """

    request = str(trusted_user_request).strip()
    if not request:
        raise ValueError("trusted_user_request must not be empty")
    if max_tools < 1:
        raise ValueError("max_tools must be positive")
    context = dict(trusted_app_context or {})
    _reject_evaluator_fields(context)
    schemas = dict(tool_schemas)
    request_tokens = _lexical_tokens(request)
    if re.search(r"\bemail\s+address(?:es)?\b", request, flags=re.IGNORECASE):
        request_tokens.discard("email")
        request_tokens.add("contact")
    request_actions = _request_action_intents(request)
    if "date" in request_tokens and re.search(
        r"\b(?:when|where|free|busy|available)\b", request, flags=re.IGNORECASE
    ):
        request_tokens.add("calendar")
    if "date" in request_tokens and request_actions & {"cancel", "reschedule"}:
        request_tokens.add("calendar")
    ranked = sorted(
        (
            (
                _generic_tool_score(
                    request,
                    request_tokens,
                    request_actions,
                    tool,
                    schema,
                ),
                tool,
                schema,
            )
            for tool, schema in schemas.items()
        ),
        key=lambda item: (-item[0], item[1]),
    )
    top_score = ranked[0][0] if ranked else 0.0
    threshold = max(3.0, top_score * 0.55, top_score - 3.0)
    selected = [item for item in ranked if item[0] >= threshold][:max_tools]
    if ranked and len(selected) < max_tools:
        domain_counts: dict[str, int] = {}
        for tool in schemas:
            for token in _tool_domain_tokens(str(tool)):
                domain_counts[token] = domain_counts.get(token, 0) + 1
        shared_provider_tokens = {
            token for token, count in domain_counts.items() if count > 1
        }
        if request_actions & _MUTATING_ACTIONS:
            top_domains = _tool_domain_tokens(ranked[0][1])
            for item in ranked:
                score, tool, schema = item
                if item in selected or score < 3.0 or len(selected) >= max_tools:
                    continue
                if (
                    _tool_action(tool) in _READ_ACTIONS
                    and not bool(schema.get("side_effect", False))
                    and top_domains & _tool_domain_tokens(tool)
                ):
                    selected.append(item)
        request_domains = request_tokens - _TOOL_ACTION_TOKENS - {"tool"}
        for item in ranked:
            score, tool, schema = item
            if item in selected or score < 4.0 or len(selected) >= max_tools:
                continue
            tool_domains = _tool_domain_tokens(tool)
            specific_overlap = (request_domains & tool_domains) - shared_provider_tokens
            if (
                _tool_action(tool) in _READ_ACTIONS
                and not bool(schema.get("side_effect", False))
                and specific_overlap
            ):
                selected.append(item)
        selected.sort(key=lambda item: (-item[0], item[1]))
    rules: list[ToolRule] = []
    for score, tool, schema in selected:
        arguments = schema.get("arguments", {})
        constraints: dict[str, ParameterConstraint] = {}
        if isinstance(arguments, Mapping):
            for name, details in arguments.items():
                detail = details if isinstance(details, Mapping) else {}
                argument_type = str(detail.get("type", "object"))
                explicit = _explicit_argument_value(request, str(name), argument_type)
                constraints[str(name)] = ParameterConstraint(
                    "exact" if explicit is not None else "type",
                    explicit if explicit is not None else argument_type,
                    required=bool(detail.get("required", False)),
                    description="Derived from trusted request" if explicit is not None else "Schema type boundary",
                )
        tool_action = _tool_action(tool)
        close_same_action = any(
            other_tool != tool
            and _tool_action(other_tool) == tool_action
            and abs(score - other_score) < 0.75
            for other_score, other_tool, _ in selected
        )
        rules.append(
            _rule(
                tool,
                constraints,
                schemas,
                requires_confirmation=(
                    bool(schema.get("side_effect", False))
                    and (close_same_action or score < 4.0)
                ),
                description=(
                    f"Intent-domain non-gold compiler score={score:.3f}; "
                    f"tool_action={tool_action}; uses trusted request and tool schema only."
                ),
            )
        )

    request_hash = sha256_json(
        {"trusted_user_request": request, "trusted_app_context": context}
    )
    return TaskPolicyManifest(
        manifest_id=manifest_id or f"generic-policy-{request_hash[:16]}",
        policy_source=(
            ("trusted_user_request", "trusted_application_context")
            if context
            else ("trusted_user_request",)
        ),
        trusted_request_sha256=request_hash,
        tool_schema_sha256=sha256_json(schemas),
        rules=tuple(rules),
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
    )
