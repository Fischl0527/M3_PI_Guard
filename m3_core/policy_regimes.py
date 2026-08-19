"""Controlled non-gold authorization regimes for paper-v1 experiments."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from m3_guard.task_policy import ParameterConstraint, TaskPolicyManifest, ToolRule

from .policy_compiler import compile_task_policy


POLICY_REGIMES = frozenset(
    {"auto_compiled", "ambiguous", "partial", "incorrect"}
)
_TARGET_ARGUMENTS = frozenset(
    {"to", "recipient", "email", "path", "endpoint", "url", "resource_id"}
)


def _rehash(
    manifest: TaskPolicyManifest,
    *,
    regime: str,
    rules: tuple[ToolRule, ...],
) -> TaskPolicyManifest:
    return replace(
        manifest,
        manifest_id=f"{manifest.manifest_id}-{regime}",
        rules=rules,
        manifest_sha256="",
    )


def _ambiguous_rule(rule: ToolRule) -> ToolRule:
    constraints = dict(rule.argument_constraints)
    changed = False
    for name, constraint in tuple(constraints.items()):
        if name.casefold() in _TARGET_ARGUMENTS and constraint.kind == "exact":
            expected_type = {
                str: "string",
                dict: "object",
                list: "array",
                int: "integer",
                float: "number",
                bool: "boolean",
            }.get(type(constraint.value), "string")
            constraints[name] = ParameterConstraint(
                "type",
                expected_type,
                required=constraint.required,
                description="Destination intentionally underspecified for authorization-uncertainty evaluation.",
            )
            changed = True
    return replace(
        rule,
        argument_constraints=constraints,
        requires_confirmation=rule.requires_confirmation or (rule.side_effect and changed),
        description=rule.description + " Controlled regime: ambiguous target scope.",
    )


def _incorrect_value(name: str, value: Any) -> Any:
    lowered = name.casefold()
    if any(token in lowered for token in ("to", "recipient", "email", "address")):
        return "incorrect-scope@example.test"
    if any(token in lowered for token in ("path", "file")):
        return "sandbox/public/incorrect_scope.txt"
    if any(token in lowered for token in ("endpoint", "url")):
        return "/mock/incorrect-scope"
    if isinstance(value, str):
        return "incorrect-scope"
    return value


def _incorrect_rule(rule: ToolRule) -> ToolRule:
    constraints = dict(rule.argument_constraints)
    changed = False
    for name, constraint in tuple(constraints.items()):
        if name.casefold() in _TARGET_ARGUMENTS and constraint.kind == "exact":
            constraints[name] = replace(
                constraint,
                value=_incorrect_value(name, constraint.value),
                description="Deliberately incorrect trusted-policy scope for sensitivity analysis.",
            )
            changed = True
    if not changed and rule.side_effect:
        return replace(
            rule,
            requires_confirmation=True,
            description=rule.description + " Controlled regime: incorrect/uncertain scope.",
        )
    return replace(
        rule,
        argument_constraints=constraints,
        description=rule.description + " Controlled regime: incorrect target scope.",
    )


def build_policy_regime(
    *,
    trusted_user_request: str,
    tool_schemas: Mapping[str, Mapping[str, Any]],
    trusted_app_context: Mapping[str, Any] | None = None,
    regime: str = "auto_compiled",
    generated_at: str | None = None,
) -> TaskPolicyManifest:
    """Compile and deterministically perturb a policy without reading gold labels.

    ``partial`` drops the final compiled action scope (or all scope when only one
    action exists).  ``ambiguous`` broadens explicit target values but requires
    confirmation.  ``incorrect`` substitutes a fixed safe synthetic target.
    These are experimental input errors, not alternative defense algorithms.
    """

    normalized = str(regime).casefold().strip()
    if normalized not in POLICY_REGIMES:
        raise ValueError("unknown policy regime: " + normalized)
    manifest = compile_task_policy(
        trusted_user_request=trusted_user_request,
        tool_schemas=tool_schemas,
        trusted_app_context=trusted_app_context,
        generated_at=generated_at,
    )
    if normalized == "auto_compiled":
        return manifest
    if normalized == "ambiguous":
        rules = tuple(_ambiguous_rule(rule) for rule in manifest.rules)
    elif normalized == "partial":
        rules = tuple(manifest.rules[:-1])
    else:
        rules = tuple(_incorrect_rule(rule) for rule in manifest.rules)
    return _rehash(manifest, regime=normalized, rules=rules)
