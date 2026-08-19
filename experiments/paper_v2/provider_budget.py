"""Offline budget and quota fuse for the paper-v2 DeepSeek/Gemini matrices.

The module never reads credentials and never sends network requests.  It validates
the user-approved budget boundary, calculates conservative DeepSeek cache-cost
scenarios, and supplies fail-closed checks for a later formal executor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json"
)
DEFAULT_SOURCE_PREFLIGHT = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/provider_cost_preflight_v1.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/dual_provider_budget_preflight_v1.json"
)

EXPECTED_STUDY_BOUNDS = {
    "work_items": 480,
    "provider_calls_upper_bound": 4416,
    "input_tokens_upper_bound": 34_407_984,
    "output_tokens_upper_bound": 2_260_992,
}
SECRET_KEY_PATTERN = re.compile(
    r"(?:api[_-]?key|access[_-]?token|secret|password)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERN = re.compile(
    r"^(?:sk-[A-Za-z0-9_.-]{12,}|AQ\.[A-Za-z0-9_.-]{12,}|Bearer\s+\S+)$",
    re.IGNORECASE,
)
ALLOWED_CREDENTIAL_METADATA_KEYS = {
    "credentials_stored",
    "policy_does_not_read_credentials",
}
MILLION = Decimal(1_000_000)


class BudgetPolicyError(ValueError):
    """Raised when a budget boundary is malformed or would fail open."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BudgetPolicyError(f"{path}: expected a JSON object")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _walk(value: Any, path: str = "$") -> list[tuple[str, str, Any]]:
    values: list[tuple[str, str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            values.append((child_path, key, child))
            values.extend(_walk(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            values.extend(_walk(child, f"{path}[{index}]"))
    return values


def _reject_secrets(policy: dict[str, Any]) -> None:
    for path, key, value in _walk(policy):
        if (
            SECRET_KEY_PATTERN.search(key)
            and key not in ALLOWED_CREDENTIAL_METADATA_KEYS
        ):
            raise BudgetPolicyError(f"{path}: secret-bearing fields are forbidden")
        if isinstance(value, str) and SECRET_VALUE_PATTERN.fullmatch(value.strip()):
            raise BudgetPolicyError(f"{path}: credential-like value is forbidden")


def _mapping(parent: dict[str, Any], key: str, path: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise BudgetPolicyError(f"{path}.{key}: expected an object")
    return value


def _number(
    parent: dict[str, Any],
    key: str,
    path: str,
    *,
    minimum: float = 0.0,
    integer: bool = False,
) -> Decimal:
    value = parent.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BudgetPolicyError(f"{path}.{key}: expected a number")
    number = Decimal(str(value))
    if not number.is_finite() or number < Decimal(str(minimum)):
        raise BudgetPolicyError(f"{path}.{key}: must be >= {minimum}")
    if integer and number != number.to_integral_value():
        raise BudgetPolicyError(f"{path}.{key}: expected an integer")
    return number


def _as_int(
    parent: dict[str, Any], key: str, path: str, *, minimum: int = 0
) -> int:
    return int(_number(parent, key, path, minimum=minimum, integer=True))


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Validate the static user-approved boundary without reading credentials."""

    _reject_secrets(policy)
    if (
        policy.get("schema_version")
        != "m3-paper-v2-dual-provider-budget-policy-1.0"
    ):
        raise BudgetPolicyError("unsupported budget policy schema")
    if policy.get("approved_by_user") is not True:
        raise BudgetPolicyError("$.approved_by_user must be true")

    study = _mapping(policy, "study_target", "$")
    for key, expected in EXPECTED_STUDY_BOUNDS.items():
        actual = _as_int(study, key, "$.study_target", minimum=1)
        if actual != expected:
            raise BudgetPolicyError(
                f"$.study_target.{key}: expected frozen bound {expected}"
            )
    if study.get("small_subset_is_not_the_target") is not True:
        raise BudgetPolicyError("full 480-item target must remain explicit")
    if study.get("cross_provider_fallback_within_a_matrix") is not False:
        raise BudgetPolicyError("cross-provider matrix fallback must be disabled")

    common = _mapping(policy, "common_controls", "$")
    if _as_int(common, "concurrency", "$.common_controls", minimum=1) != 1:
        raise BudgetPolicyError("$.common_controls.concurrency must equal 1")
    if (
        _as_int(common, "automatic_retries", "$.common_controls", minimum=0)
        != 0
    ):
        raise BudgetPolicyError("$.common_controls.automatic_retries must equal 0")
    if common.get("provider_managed_tools_enabled") is not False:
        raise BudgetPolicyError("provider-managed tools must remain disabled")
    if common.get("external_effects_enabled") is not False:
        raise BudgetPolicyError("external effects must remain disabled")
    allowed_payloads = common.get("payload_classes_allowed")
    forbidden_payloads = common.get("payload_classes_forbidden")
    if not isinstance(allowed_payloads, list) or not allowed_payloads:
        raise BudgetPolicyError("allowed payload classes must be non-empty")
    if not isinstance(forbidden_payloads, list) or not forbidden_payloads:
        raise BudgetPolicyError("forbidden payload classes must be non-empty")

    deepseek = _mapping(policy, "deepseek", "$")
    if deepseek.get("base_url") != "https://api.deepseek.com":
        raise BudgetPolicyError("DeepSeek must use the frozen official endpoint")
    if deepseek.get("model_id") != "deepseek-v4-pro":
        raise BudgetPolicyError("unexpected DeepSeek model identity")
    hard_limit = _number(
        deepseek, "hard_spend_limit_cny", "$.deepseek", minimum=0.01
    )
    declared_balance = _number(
        deepseek, "user_declared_balance_cny", "$.deepseek", minimum=0.01
    )
    abort_fraction = _number(
        deepseek, "abort_at_fraction", "$.deepseek", minimum=0.01
    )
    if abort_fraction > Decimal("0.9"):
        raise BudgetPolicyError("$.deepseek.abort_at_fraction must be <= 0.9")
    abort_ceiling = _number(
        deepseek, "abort_ceiling_cny", "$.deepseek", minimum=0.01
    )
    reserve = _number(
        deepseek, "untouched_reserve_cny", "$.deepseek", minimum=0
    )
    if hard_limit > declared_balance:
        raise BudgetPolicyError("hard limit exceeds the user-declared balance")
    if abort_ceiling != hard_limit * abort_fraction:
        raise BudgetPolicyError("DeepSeek abort ceiling is internally inconsistent")
    if abort_ceiling + reserve > hard_limit:
        raise BudgetPolicyError("DeepSeek reserve is not protected")

    pricing = _mapping(deepseek, "pricing", "$.deepseek")
    if pricing.get("currency") != "CNY":
        raise BudgetPolicyError("DeepSeek pricing currency must be CNY")
    for key in (
        "cache_hit_input_per_million_tokens",
        "cache_miss_input_per_million_tokens",
        "output_per_million_tokens",
    ):
        _number(pricing, key, "$.deepseek.pricing", minimum=0)
    dynamic = _mapping(deepseek, "dynamic_fuse", "$.deepseek")
    _as_int(
        dynamic,
        "next_request_input_tokens_upper_bound",
        "$.deepseek.dynamic_fuse",
        minimum=1,
    )
    _as_int(
        dynamic,
        "next_request_output_tokens_upper_bound",
        "$.deepseek.dynamic_fuse",
        minimum=1,
    )
    _as_int(
        dynamic,
        "projection_enabled_after_observed_input_tokens",
        "$.deepseek.dynamic_fuse",
        minimum=1,
    )

    gemini = _mapping(policy, "gemini", "$")
    if (
        gemini.get("base_url")
        != "https://generativelanguage.googleapis.com/v1beta/openai/"
    ):
        raise BudgetPolicyError("Gemini must use the frozen official endpoint")
    if gemini.get("model_id") != "gemini-3.6-flash":
        raise BudgetPolicyError("unexpected Gemini model identity")
    if gemini.get("billing_tier") != "free":
        raise BudgetPolicyError("Gemini billing tier must remain free")
    if gemini.get("allow_paid_tier") is not False:
        raise BudgetPolicyError("Gemini paid-tier use must remain disabled")
    if _number(
        gemini, "monetary_hard_limit_usd", "$.gemini", minimum=0
    ) != Decimal(0):
        raise BudgetPolicyError("Gemini monetary hard limit must remain zero")
    if gemini.get("chargeable_features_enabled") is not False:
        raise BudgetPolicyError("Gemini chargeable features must remain disabled")
    caps = _mapping(gemini, "local_batch_caps", "$.gemini")
    for key in ("requests", "input_tokens", "output_tokens"):
        _as_int(caps, key, "$.gemini.local_batch_caps", minimum=1)

    authorization = _mapping(policy, "execution_authorization", "$")
    if authorization.get("formal_execution_authorized") is not False:
        raise BudgetPolicyError(
            "budget approval must not imply formal execution authorization"
        )
    return policy


def _pricing(policy: dict[str, Any]) -> tuple[Decimal, Decimal, Decimal]:
    pricing = policy["deepseek"]["pricing"]
    return (
        Decimal(str(pricing["cache_hit_input_per_million_tokens"])),
        Decimal(str(pricing["cache_miss_input_per_million_tokens"])),
        Decimal(str(pricing["output_per_million_tokens"])),
    )


def deepseek_cost_cny(
    policy: dict[str, Any],
    *,
    cache_hit_input_tokens: int,
    cache_miss_input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """Calculate actual DeepSeek cost from the provider's cache usage fields."""

    validate_policy(policy)
    for name, value in {
        "cache_hit_input_tokens": cache_hit_input_tokens,
        "cache_miss_input_tokens": cache_miss_input_tokens,
        "output_tokens": output_tokens,
    }.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise BudgetPolicyError(f"{name}: expected a non-negative integer")
    hit_price, miss_price, output_price = _pricing(policy)
    return (
        Decimal(cache_hit_input_tokens) * hit_price
        + Decimal(cache_miss_input_tokens) * miss_price
        + Decimal(output_tokens) * output_price
    ) / MILLION


def deepseek_scenario_costs(policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Return full-plan prices for declared aggregate cache-hit ratios."""

    validate_policy(policy)
    input_tokens = EXPECTED_STUDY_BOUNDS["input_tokens_upper_bound"]
    output_tokens = EXPECTED_STUDY_BOUNDS["output_tokens_upper_bound"]
    hit_price, miss_price, output_price = _pricing(policy)
    output_cost = Decimal(output_tokens) * output_price / MILLION
    scenarios = []
    for ratio in (
        Decimal("1"),
        Decimal("0.95"),
        Decimal("0.90"),
        Decimal("0.88"),
        Decimal("0.85"),
        Decimal("0.80"),
        Decimal("0"),
    ):
        input_cost = (
            Decimal(input_tokens)
            * (ratio * hit_price + (Decimal(1) - ratio) * miss_price)
            / MILLION
        )
        scenarios.append(
            {
                "aggregate_cache_hit_ratio": float(ratio),
                "input_cost_cny": _decimal_float(input_cost),
                "output_cost_cny": _decimal_float(output_cost),
                "total_cost_cny": _decimal_float(input_cost + output_cost),
            }
        )
    return scenarios


def minimum_cache_hit_ratio_for_abort_ceiling(
    policy: dict[str, Any],
) -> Decimal:
    """Solve the minimum full-plan hit ratio needed to stay under the fuse."""

    validate_policy(policy)
    input_tokens = Decimal(EXPECTED_STUDY_BOUNDS["input_tokens_upper_bound"])
    output_tokens = Decimal(EXPECTED_STUDY_BOUNDS["output_tokens_upper_bound"])
    ceiling = Decimal(str(policy["deepseek"]["abort_ceiling_cny"]))
    hit_price, miss_price, output_price = _pricing(policy)
    output_cost = output_tokens * output_price / MILLION
    affordable_blended_input_price = (ceiling - output_cost) * MILLION / input_tokens
    ratio = (miss_price - affordable_blended_input_price) / (
        miss_price - hit_price
    )
    return max(Decimal(0), min(Decimal(1), ratio))


def _decimal_float(value: Decimal, places: str = "0.000001") -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def validate_deepseek_usage(usage: dict[str, Any]) -> dict[str, int]:
    """Require exact cache accounting before a subsequent formal request."""

    required = (
        "prompt_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "completion_tokens",
    )
    normalized: dict[str, int] = {}
    for key in required:
        value = usage.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise BudgetPolicyError(f"DeepSeek usage.{key} is required")
        normalized[key] = value
    if normalized["prompt_tokens"] != (
        normalized["prompt_cache_hit_tokens"]
        + normalized["prompt_cache_miss_tokens"]
    ):
        raise BudgetPolicyError(
            "DeepSeek prompt tokens do not equal cache hit plus cache miss tokens"
        )
    return normalized


def check_deepseek_headroom(
    policy: dict[str, Any],
    cumulative_usage: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed before a request that could cross the CNY abort ceiling."""

    validate_policy(policy)
    usage = validate_deepseek_usage(cumulative_usage)
    actual_cost = deepseek_cost_cny(
        policy,
        cache_hit_input_tokens=usage["prompt_cache_hit_tokens"],
        cache_miss_input_tokens=usage["prompt_cache_miss_tokens"],
        output_tokens=usage["completion_tokens"],
    )
    dynamic = policy["deepseek"]["dynamic_fuse"]
    next_worst_cost = deepseek_cost_cny(
        policy,
        cache_hit_input_tokens=0,
        cache_miss_input_tokens=int(
            dynamic["next_request_input_tokens_upper_bound"]
        ),
        output_tokens=int(dynamic["next_request_output_tokens_upper_bound"]),
    )
    ceiling = Decimal(str(policy["deepseek"]["abort_ceiling_cny"]))
    if actual_cost + next_worst_cost > ceiling:
        raise BudgetPolicyError(
            "DeepSeek abort ceiling cannot fit the next worst-case request"
        )

    prompt_tokens = usage["prompt_tokens"]
    projection_minimum = int(
        dynamic["projection_enabled_after_observed_input_tokens"]
    )
    observed_hit_ratio: Decimal | None = None
    projected_total: Decimal | None = None
    if prompt_tokens:
        observed_hit_ratio = (
            Decimal(usage["prompt_cache_hit_tokens"]) / Decimal(prompt_tokens)
        )
    if prompt_tokens >= projection_minimum and observed_hit_ratio is not None:
        hit_price, miss_price, output_price = _pricing(policy)
        projected_total = (
            Decimal(EXPECTED_STUDY_BOUNDS["input_tokens_upper_bound"])
            * (
                observed_hit_ratio * hit_price
                + (Decimal(1) - observed_hit_ratio) * miss_price
            )
            + Decimal(EXPECTED_STUDY_BOUNDS["output_tokens_upper_bound"])
            * output_price
        ) / MILLION
        if projected_total > ceiling:
            raise BudgetPolicyError(
                "DeepSeek observed cache ratio projects above the abort ceiling"
            )

    return {
        "status": "continue",
        "actual_cost_cny": _decimal_float(actual_cost),
        "next_request_worst_case_cost_cny": _decimal_float(next_worst_cost),
        "remaining_abort_headroom_cny": _decimal_float(ceiling - actual_cost),
        "observed_cache_hit_ratio": (
            None
            if observed_hit_ratio is None
            else float(observed_hit_ratio.quantize(Decimal("0.000001")))
        ),
        "projected_full_plan_cost_cny": (
            None if projected_total is None else _decimal_float(projected_total)
        ),
    }


def check_gemini_free_batch(
    policy: dict[str, Any],
    *,
    requests: int,
    input_tokens: int,
    output_tokens: int,
    charged_usd: float,
    billing_tier: str,
) -> dict[str, Any]:
    """Enforce local free-tier caps without claiming they are provider quotas."""

    validate_policy(policy)
    for name, value in {
        "requests": requests,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise BudgetPolicyError(f"Gemini {name}: expected non-negative integer")
    if not math.isfinite(charged_usd) or charged_usd != 0:
        raise BudgetPolicyError("Gemini free-tier monetary limit is zero")
    if billing_tier != "free":
        raise BudgetPolicyError("Gemini paid-tier execution is forbidden")
    caps = policy["gemini"]["local_batch_caps"]
    observed = {
        "requests": requests,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    exceeded = [key for key, value in observed.items() if value > int(caps[key])]
    if exceeded:
        raise BudgetPolicyError(
            f"Gemini local batch cap exceeded: {', '.join(exceeded)}"
        )
    return {
        "status": "continue",
        "billing_tier": "free",
        "charged_usd": 0.0,
        "remaining_local_batch": {
            key: int(caps[key]) - value for key, value in observed.items()
        },
    }


def classify_provider_error(provider: str, http_status: int) -> dict[str, Any]:
    """Classify quota errors without creating an automatic retry path."""

    if provider not in {"deepseek", "gemini"}:
        raise BudgetPolicyError(f"unsupported provider: {provider}")
    if isinstance(http_status, bool) or not isinstance(http_status, int):
        raise BudgetPolicyError("http_status must be an integer")
    if http_status == 429:
        return {
            "action": "pause",
            "automatic_retry": False,
            "resume": "manual_same_work_item_after_provider_recovery",
            "retain_attempt_in_audit_log": True,
        }
    return {
        "action": "record_operational_failure",
        "automatic_retry": False,
        "resume": "none_without_explicit_protocol_decision",
        "retain_attempt_in_audit_log": True,
    }


def _validate_source_bounds(policy: dict[str, Any], source: dict[str, Any]) -> None:
    estimate = source.get("cost_estimate")
    if not isinstance(estimate, dict):
        raise BudgetPolicyError("source preflight is missing cost_estimate")
    for key, expected in EXPECTED_STUDY_BOUNDS.items():
        if estimate.get(key) != expected:
            raise BudgetPolicyError(
                f"source preflight {key} does not match frozen bound {expected}"
            )
        if policy["study_target"].get(key) != expected:
            raise BudgetPolicyError(
                f"budget policy {key} does not match frozen bound {expected}"
            )


def build_preflight(
    policy_path: Path = DEFAULT_POLICY,
    source_preflight_path: Path = DEFAULT_SOURCE_PREFLIGHT,
) -> dict[str, Any]:
    """Build a deterministic, offline preflight for the full two-model target."""

    policy = validate_policy(_load_json(policy_path))
    source = _load_json(source_preflight_path)
    _validate_source_bounds(policy, source)
    ratio = minimum_cache_hit_ratio_for_abort_ceiling(policy)
    blockers = list(policy["execution_authorization"]["remaining_gates"])
    return {
        "schema_version": "m3-paper-v2-dual-provider-budget-preflight-1.0",
        "generated_at": "2026-07-23T23:45:00+08:00",
        "status": "blocked_executor_identity_logging_and_gemini_quota_snapshot",
        "gate_pass": False,
        "network_calls_made": 0,
        "credentials_read": False,
        "budget_boundary_approved_by_user": True,
        "formal_execution_authorized": False,
        "study_target": dict(policy["study_target"]),
        "deepseek": {
            "model_id": policy["deepseek"]["model_id"],
            "declared_balance_cny": policy["deepseek"][
                "user_declared_balance_cny"
            ],
            "abort_ceiling_cny": policy["deepseek"]["abort_ceiling_cny"],
            "untouched_reserve_cny": policy["deepseek"][
                "untouched_reserve_cny"
            ],
            "minimum_full_plan_cache_hit_ratio": float(
                ratio.quantize(Decimal("0.000001"))
            ),
            "scenarios": deepseek_scenario_costs(policy),
            "per_request_fuse_ready": True,
            "actual_cache_usage_required": True,
        },
        "gemini": {
            "model_id": policy["gemini"]["model_id"],
            "billing_tier": "free",
            "monetary_hard_limit_usd": 0.0,
            "active_project_quota_snapshot_present": policy["gemini"][
                "active_project_quota_snapshot_present"
            ],
            "local_batch_caps": dict(policy["gemini"]["local_batch_caps"]),
            "first_429_action": "pause_without_automatic_retry",
        },
        "data_boundary": {
            "allowed_payload_classes": list(
                policy["common_controls"]["payload_classes_allowed"]
            ),
            "forbidden_payload_classes": list(
                policy["common_controls"]["payload_classes_forbidden"]
            ),
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
        },
        "blockers": blockers,
        "policy": {
            "path": _display_path(policy_path),
            "sha256": _sha256_file(policy_path),
        },
        "source_cost_preflight": {
            "path": _display_path(source_preflight_path),
            "sha256": _sha256_file(source_preflight_path),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument(
        "--source-preflight", type=Path, default=DEFAULT_SOURCE_PREFLIGHT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    current = build_preflight(args.policy, args.source_preflight)
    if args.verify_only:
        frozen = _load_json(args.output)
        if current != frozen:
            raise BudgetPolicyError(
                f"{args.output}: frozen preflight does not reproduce"
            )
        print(
            json.dumps(
                {
                    "status": "verified",
                    "gate_pass": current["gate_pass"],
                    "network_calls_made": 0,
                },
                sort_keys=True,
            )
        )
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(current, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
