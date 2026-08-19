"""Fail-closed per-role budget state for the paper-v2 public matrix.

The earlier medium-matrix policy intentionally hard-codes a 480-item
DeepSeek-V4-Pro study.  This module leaves that evidence immutable and adapts
the same cache-aware accounting contract to the frozen 6,873-record public
matrix with separate Pro and Flash ceilings.

It does not read credentials or make network calls.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.official_provider_executor import (
    ProviderPausedError,
    ProviderPayloadError,
)
from experiments.paper_v2.provider_budget import (
    BudgetPolicyError,
    validate_deepseek_usage,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/public_budget_policy_v1.json"
)
EXPECTED_COUNTS = {
    "public_case_condition_records": 6873,
    "primary_model_records": 5082,
    "second_model_records": 1791,
    "primary_canary_records": 24,
    "second_model_canary_records": 12,
}
ROLE_IDENTITIES = {
    "primary": "deepseek-v4-pro",
    "second": "deepseek-v4-flash",
}
ROLE_LIMITS = {
    "primary": Decimal("20.0"),
    "second": Decimal("5.0"),
}
USAGE_FIELDS = (
    "prompt_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "completion_tokens",
)
MILLION = Decimal(1_000_000)


class PublicBudgetPolicyError(ValueError):
    """Raised when the public budget contract would fail open."""


def load_public_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicBudgetPolicyError("public budget policy must be an object")
    return validate_public_policy(value)


def _number(value: Any, path: str, *, minimum: Decimal) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PublicBudgetPolicyError(f"{path}: expected a number")
    result = Decimal(str(value))
    if not result.is_finite() or result < minimum:
        raise PublicBudgetPolicyError(f"{path}: must be >= {minimum}")
    return result


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    number = _number(value, path, minimum=Decimal(minimum))
    if number != number.to_integral_value():
        raise PublicBudgetPolicyError(f"{path}: expected an integer")
    return int(number)


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicBudgetPolicyError(f"{path}: expected an object")
    return dict(value)


def validate_public_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    policy = copy.deepcopy(dict(value))
    if (
        policy.get("schema_version")
        != "m3-paper-v2-public-budget-policy-1.0"
        or policy.get("approved_by_user") is not True
    ):
        raise PublicBudgetPolicyError("public budget policy identity drift")
    study = _mapping(policy.get("study_target"), "$.study_target")
    for field, expected in EXPECTED_COUNTS.items():
        if _integer(study.get(field), f"$.study_target.{field}", minimum=1) != expected:
            raise PublicBudgetPolicyError(
                f"$.study_target.{field}: expected {expected}"
            )
    if (
        study.get("cross_model_substitution") is not False
        or study.get("sample_shrinking_on_budget_pressure") is not False
    ):
        raise PublicBudgetPolicyError("public scope may not fail open")

    common = _mapping(policy.get("common_controls"), "$.common_controls")
    if (
        _integer(
            common.get("canary_concurrency"),
            "$.common_controls.canary_concurrency",
            minimum=1,
        )
        != 1
        or _integer(
            common.get("automatic_retries"),
            "$.common_controls.automatic_retries",
        )
        != 0
        or common.get("provider_managed_tools_enabled") is not False
        or common.get("external_effects_enabled") is not False
        or common.get("model_output_is_untrusted_proposal_only") is not True
    ):
        raise PublicBudgetPolicyError("public safety controls drift")
    allowed = common.get("payload_classes_allowed")
    forbidden = common.get("payload_classes_forbidden")
    if not isinstance(allowed, list) or not allowed:
        raise PublicBudgetPolicyError("allowed payload classes are required")
    if not isinstance(forbidden, list) or not forbidden:
        raise PublicBudgetPolicyError("forbidden payload classes are required")

    deepseek = _mapping(policy.get("deepseek"), "$.deepseek")
    if (
        deepseek.get("base_url") != "https://api.deepseek.com"
        or deepseek.get("endpoint_type") != "official_api"
    ):
        raise PublicBudgetPolicyError("public DeepSeek endpoint drift")
    balance = _number(
        deepseek.get("user_declared_balance_cny"),
        "$.deepseek.user_declared_balance_cny",
        minimum=Decimal("0.01"),
    )
    hard_limit = _number(
        deepseek.get("incremental_hard_limit_cny"),
        "$.deepseek.incremental_hard_limit_cny",
        minimum=Decimal("0.01"),
    )
    reserve = _number(
        deepseek.get("untouched_reserve_cny"),
        "$.deepseek.untouched_reserve_cny",
        minimum=Decimal("0"),
    )
    if hard_limit != Decimal("25.0") or hard_limit + reserve > balance:
        raise PublicBudgetPolicyError("public aggregate budget boundary drift")
    roles = _mapping(deepseek.get("roles"), "$.deepseek.roles")
    if set(roles) != set(ROLE_IDENTITIES):
        raise PublicBudgetPolicyError("public model roles drift")
    role_sum = Decimal(0)
    for role, model_id in ROLE_IDENTITIES.items():
        spec = _mapping(roles.get(role), f"$.deepseek.roles.{role}")
        limit = _number(
            spec.get("role_hard_limit_cny"),
            f"$.deepseek.roles.{role}.role_hard_limit_cny",
            minimum=Decimal("0.01"),
        )
        if (
            spec.get("model_id") != model_id
            or limit != ROLE_LIMITS[role]
            or spec.get("claim_boundary")
            not in {"primary_model", "cross_model_not_cross_provider"}
        ):
            raise PublicBudgetPolicyError(f"public {role} identity/limit drift")
        pricing = _mapping(
            spec.get("pricing"),
            f"$.deepseek.roles.{role}.pricing",
        )
        if pricing.get("currency") != "CNY":
            raise PublicBudgetPolicyError(f"public {role} currency drift")
        for field in (
            "cache_hit_input_per_million_tokens",
            "cache_miss_input_per_million_tokens",
            "output_per_million_tokens",
        ):
            _number(
                pricing.get(field),
                f"$.deepseek.roles.{role}.pricing.{field}",
                minimum=Decimal("0"),
            )
        role_sum += limit
    if role_sum != hard_limit:
        raise PublicBudgetPolicyError("role ceilings must sum to aggregate ceiling")

    dynamic = _mapping(deepseek.get("dynamic_fuse"), "$.deepseek.dynamic_fuse")
    _integer(
        dynamic.get("next_request_input_tokens_upper_bound"),
        "$.deepseek.dynamic_fuse.next_request_input_tokens_upper_bound",
        minimum=1,
    )
    _integer(
        dynamic.get("next_request_output_tokens_upper_bound"),
        "$.deepseek.dynamic_fuse.next_request_output_tokens_upper_bound",
        minimum=1,
    )
    authorization = _mapping(
        policy.get("execution_authorization"),
        "$.execution_authorization",
    )
    if any(
        authorization.get(field) is not False
        for field in (
            "formal_execution_authorized",
            "canary_execution_authorized",
            "result_admission_authorized",
        )
    ):
        raise PublicBudgetPolicyError(
            "budget approval must not authorize execution or results"
        )
    return policy


def build_role_policy(
    policy: Mapping[str, Any],
    role: str,
) -> dict[str, Any]:
    """Project the master policy into the existing trace-cost interface."""

    public = validate_public_policy(policy)
    if role not in ROLE_IDENTITIES:
        raise PublicBudgetPolicyError(f"unsupported public model role: {role}")
    deepseek = public["deepseek"]
    spec = deepseek["roles"][role]
    return {
        "schema_version": "m3-paper-v2-public-role-budget-policy-1.0",
        "public_model_role": role,
        "common_controls": copy.deepcopy(public["common_controls"]),
        "deepseek": {
            "provider": "DeepSeek",
            "endpoint_type": "official_api",
            "base_url": deepseek["base_url"],
            "model_id": spec["model_id"],
            "hard_spend_limit_cny": spec["role_hard_limit_cny"],
            "abort_at_fraction": 1.0,
            "abort_ceiling_cny": spec["role_hard_limit_cny"],
            "untouched_reserve_cny": 0.0,
            "pricing": copy.deepcopy(spec["pricing"]),
            "dynamic_fuse": copy.deepcopy(deepseek["dynamic_fuse"]),
            "rate_limit_handling": {
                "first_http_429": "pause",
                "automatic_retry": False,
            },
        },
    }


def _zero_usage() -> dict[str, int]:
    return {field: 0 for field in USAGE_FIELDS}


def _normalize_usage(value: Mapping[str, Any]) -> dict[str, int]:
    try:
        validated = validate_deepseek_usage(dict(value))
    except BudgetPolicyError as exc:
        raise PublicBudgetPolicyError(str(exc)) from exc
    return {
        "prompt_tokens": int(validated["prompt_tokens"]),
        "prompt_cache_hit_tokens": int(
            validated["prompt_cache_hit_tokens"]
        ),
        "prompt_cache_miss_tokens": int(
            validated["prompt_cache_miss_tokens"]
        ),
        "completion_tokens": int(validated["completion_tokens"]),
    }


def _add_usage(
    left: Mapping[str, int],
    right: Mapping[str, int],
) -> dict[str, int]:
    return {field: int(left[field]) + int(right[field]) for field in USAGE_FIELDS}


def role_cost_cny(
    role_policy: Mapping[str, Any],
    usage: Mapping[str, int],
) -> float:
    pricing = role_policy["deepseek"]["pricing"]
    hit = Decimal(int(usage["prompt_cache_hit_tokens"]))
    miss = Decimal(int(usage["prompt_cache_miss_tokens"]))
    output = Decimal(int(usage["completion_tokens"]))
    return round(
        float(
            (
                hit
                * Decimal(
                    str(
                        pricing[
                            "cache_hit_input_per_million_tokens"
                        ]
                    )
                )
                + miss
                * Decimal(
                    str(
                        pricing[
                            "cache_miss_input_per_million_tokens"
                        ]
                    )
                )
                + output
                * Decimal(str(pricing["output_per_million_tokens"]))
            )
            / MILLION
        ),
        12,
    )


def _next_request_upper_cost(role_policy: Mapping[str, Any]) -> float:
    dynamic = role_policy["deepseek"]["dynamic_fuse"]
    return role_cost_cny(
        role_policy,
        {
            "prompt_tokens": int(
                dynamic["next_request_input_tokens_upper_bound"]
            ),
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": int(
                dynamic["next_request_input_tokens_upper_bound"]
            ),
            "completion_tokens": int(
                dynamic["next_request_output_tokens_upper_bound"]
            ),
        },
    )


def check_role_headroom(
    role_policy: Mapping[str, Any],
    usage: Mapping[str, int],
) -> dict[str, Any]:
    normalized = _normalize_usage(usage)
    cost = role_cost_cny(role_policy, normalized)
    ceiling = float(role_policy["deepseek"]["abort_ceiling_cny"])
    next_upper = _next_request_upper_cost(role_policy)
    if cost > ceiling:
        raise PublicBudgetPolicyError("completed usage exceeds the role ceiling")
    if cost + next_upper > ceiling:
        raise PublicBudgetPolicyError(
            "the next worst-case request cannot fit the role ceiling"
        )
    return {
        "current_cost_cny": cost,
        "next_request_upper_cost_cny": next_upper,
        "role_ceiling_cny": ceiling,
        "remaining_after_next_upper_cny": round(
            ceiling - cost - next_upper,
            12,
        ),
    }


@dataclass
class PublicProviderBudgetState:
    """Per-work-item budget state compatible with the traced JSON client."""

    provider_id: str
    policy: Mapping[str, Any]
    pause_reason: str | None = None

    def __post_init__(self) -> None:
        if self.provider_id != "deepseek":
            raise ProviderPayloadError(
                "public provider budget state is DeepSeek-only"
            )
        role = self.policy.get("public_model_role")
        if role not in ROLE_IDENTITIES:
            raise ProviderPayloadError("public role policy identity is missing")
        if self.policy["deepseek"]["model_id"] != ROLE_IDENTITIES[str(role)]:
            raise ProviderPayloadError("public role model identity drift")
        self.policy = copy.deepcopy(dict(self.policy))
        self._usage = _zero_usage()

    @property
    def role(self) -> str:
        return str(self.policy["public_model_role"])

    def assert_before_request(self) -> None:
        if self.pause_reason is not None:
            raise ProviderPausedError(self.pause_reason)
        try:
            check_role_headroom(self.policy, self._usage)
        except PublicBudgetPolicyError as exc:
            self.pause_reason = str(exc)
            raise ProviderPausedError(self.pause_reason) from exc

    def record_usage(self, usage: Mapping[str, Any]) -> dict[str, Any]:
        if self.pause_reason is not None:
            raise ProviderPausedError(self.pause_reason)
        normalized = _normalize_usage(usage)
        self._usage = _add_usage(self._usage, normalized)
        cost = role_cost_cny(self.policy, self._usage)
        ceiling = float(self.policy["deepseek"]["abort_ceiling_cny"])
        if cost > ceiling:
            self.pause_reason = "completed call crossed the public role ceiling"
            raise ProviderPausedError(self.pause_reason)
        status = "continue"
        try:
            headroom = check_role_headroom(self.policy, self._usage)
        except PublicBudgetPolicyError as exc:
            status = "pause_before_next_request"
            self.pause_reason = str(exc)
            headroom = {
                "current_cost_cny": cost,
                "next_request_upper_cost_cny": _next_request_upper_cost(
                    self.policy
                ),
                "role_ceiling_cny": ceiling,
                "remaining_after_next_upper_cny": round(
                    ceiling
                    - cost
                    - _next_request_upper_cost(self.policy),
                    12,
                ),
            }
        return {
            "status": status,
            "model_role": self.role,
            "cumulative_usage": copy.deepcopy(self._usage),
            "cumulative_cost_cny": cost,
            "headroom": headroom,
            "pause_reason": self.pause_reason,
        }
