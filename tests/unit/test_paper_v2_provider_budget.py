from __future__ import annotations

import copy
import json
from decimal import Decimal

import pytest

from experiments.paper_v2.provider_budget import (
    DEFAULT_OUTPUT,
    DEFAULT_POLICY,
    BudgetPolicyError,
    build_preflight,
    check_deepseek_headroom,
    check_gemini_free_batch,
    classify_provider_error,
    deepseek_cost_cny,
    deepseek_scenario_costs,
    minimum_cache_hit_ratio_for_abort_ceiling,
    validate_deepseek_usage,
    validate_policy,
)


def _policy() -> dict:
    return json.loads(DEFAULT_POLICY.read_text(encoding="utf-8"))


def test_policy_preserves_full_target_and_does_not_authorize_execution() -> None:
    policy = validate_policy(_policy())

    assert policy["study_target"]["work_items"] == 480
    assert policy["study_target"]["provider_calls_upper_bound"] == 4416
    assert policy["study_target"]["small_subset_is_not_the_target"] is True
    assert policy["execution_authorization"]["formal_execution_authorized"] is False
    assert policy["common_controls"]["automatic_retries"] == 0


def test_policy_rejects_secret_fields_and_paid_gemini() -> None:
    secret = _policy()
    secret["api_key"] = "sk-do-not-store-this-secret"
    with pytest.raises(BudgetPolicyError, match="secret-bearing"):
        validate_policy(secret)

    paid = _policy()
    paid["gemini"]["billing_tier"] = "paid"
    with pytest.raises(BudgetPolicyError, match="must remain free"):
        validate_policy(paid)


def test_deepseek_full_plan_scenarios_cross_fuse_between_88_and_85_percent() -> None:
    scenarios = {
        row["aggregate_cache_hit_ratio"]: row
        for row in deepseek_scenario_costs(_policy())
    }

    assert scenarios[0.9]["total_cost_cny"] == pytest.approx(24.662527)
    assert scenarios[0.88]["total_cost_cny"] == pytest.approx(26.709802)
    assert scenarios[0.85]["total_cost_cny"] == pytest.approx(29.780714)
    assert scenarios[0.88]["total_cost_cny"] < 27
    assert scenarios[0.85]["total_cost_cny"] > 27


def test_minimum_hit_ratio_for_full_plan_is_approximately_87_72_percent() -> None:
    ratio = minimum_cache_hit_ratio_for_abort_ceiling(_policy())

    assert ratio == pytest.approx(Decimal("0.8771650305"))


def test_deepseek_cost_uses_separate_hit_miss_and_output_prices() -> None:
    cost = deepseek_cost_cny(
        _policy(),
        cache_hit_input_tokens=1_000_000,
        cache_miss_input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    assert cost == Decimal("9.025")


def test_deepseek_usage_requires_complete_consistent_cache_accounting() -> None:
    with pytest.raises(BudgetPolicyError, match="cache_miss"):
        validate_deepseek_usage(
            {
                "prompt_tokens": 100,
                "prompt_cache_hit_tokens": 90,
                "completion_tokens": 10,
            }
        )

    with pytest.raises(BudgetPolicyError, match="do not equal"):
        validate_deepseek_usage(
            {
                "prompt_tokens": 100,
                "prompt_cache_hit_tokens": 90,
                "prompt_cache_miss_tokens": 9,
                "completion_tokens": 10,
            }
        )


def test_deepseek_fuse_continues_at_90_percent_and_pauses_at_85_percent() -> None:
    continues = check_deepseek_headroom(
        _policy(),
        {
            "prompt_tokens": 1_000_000,
            "prompt_cache_hit_tokens": 900_000,
            "prompt_cache_miss_tokens": 100_000,
            "completion_tokens": 50_000,
        },
    )
    assert continues["status"] == "continue"
    assert continues["observed_cache_hit_ratio"] == 0.9
    assert continues["projected_full_plan_cost_cny"] == pytest.approx(24.662527)

    with pytest.raises(BudgetPolicyError, match="projects above"):
        check_deepseek_headroom(
            _policy(),
            {
                "prompt_tokens": 1_000_000,
                "prompt_cache_hit_tokens": 850_000,
                "prompt_cache_miss_tokens": 150_000,
                "completion_tokens": 50_000,
            },
        )


def test_deepseek_fuse_stops_before_next_request_can_cross_ceiling() -> None:
    with pytest.raises(BudgetPolicyError, match="cannot fit"):
        check_deepseek_headroom(
            _policy(),
            {
                "prompt_tokens": 9_000_000,
                "prompt_cache_hit_tokens": 1_000_000,
                "prompt_cache_miss_tokens": 8_000_000,
                "completion_tokens": 490_000,
            },
        )


def test_gemini_is_free_only_and_locally_capped() -> None:
    remaining = check_gemini_free_batch(
        _policy(),
        requests=99,
        input_tokens=999_999,
        output_tokens=127_999,
        charged_usd=0.0,
        billing_tier="free",
    )
    assert remaining["remaining_local_batch"]["requests"] == 1

    with pytest.raises(BudgetPolicyError, match="monetary limit"):
        check_gemini_free_batch(
            _policy(),
            requests=1,
            input_tokens=1,
            output_tokens=1,
            charged_usd=0.01,
            billing_tier="free",
        )
    with pytest.raises(BudgetPolicyError, match="requests"):
        check_gemini_free_batch(
            _policy(),
            requests=101,
            input_tokens=1,
            output_tokens=1,
            charged_usd=0.0,
            billing_tier="free",
        )


def test_429_always_pauses_without_automatic_retry_or_provider_fallback() -> None:
    for provider in ("deepseek", "gemini"):
        decision = classify_provider_error(provider, 429)
        assert decision["action"] == "pause"
        assert decision["automatic_retry"] is False
        assert decision["retain_attempt_in_audit_log"] is True
    assert (
        _policy()["gemini"]["quota_handling"]["automatic_fallback_to_deepseek"]
        is False
    )


def test_policy_rejects_relaxed_abort_fraction() -> None:
    policy = copy.deepcopy(_policy())
    policy["deepseek"]["abort_at_fraction"] = 0.91

    with pytest.raises(BudgetPolicyError, match="must be <= 0.9"):
        validate_policy(policy)


def test_frozen_preflight_reproduces_and_remains_blocked() -> None:
    preflight = build_preflight()

    assert json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8")) == preflight
    assert preflight["network_calls_made"] == 0
    assert preflight["credentials_read"] is False
    assert preflight["budget_boundary_approved_by_user"] is True
    assert preflight["formal_execution_authorized"] is False
    assert preflight["gate_pass"] is False
    assert len(preflight["blockers"]) == 5
