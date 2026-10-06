from types import SimpleNamespace

import pytest

from experiments.paper_v2.agentdyn_followup_controls_v1 import category, resolve_fixture_placeholder


def env_with_pending(pending):
    account = SimpleNamespace(username="fixture-user", verification_stack=pending)
    return SimpleNamespace(shopping_platform=SimpleNamespace(current_account_username="fixture-user", account_list=[account]))


def test_offline_placeholder_resolved_without_mutating_original():
    args = {"otp": "one-time-password"}
    resolved, changed = resolve_fixture_placeholder(env_with_pending({"fixture-dynamic-value": None}), "verify_shopping_account", args)
    assert changed and resolved["otp"] == "fixture-dynamic-value"
    assert args["otp"] == "one-time-password"


def test_actual_value_and_nonverification_tools_not_changed():
    env = env_with_pending({"fixture-dynamic-value": None})
    assert resolve_fixture_placeholder(env, "verify_shopping_account", {"otp": "explicit-proposal"}) == ({"otp": "explicit-proposal"}, False)
    assert resolve_fixture_placeholder(env, "send_email", {"otp": "one-time-password"}) == ({"otp": "one-time-password"}, False)


def test_ambiguous_queue_and_missing_queue_not_arbitrarily_selected():
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_fixture_placeholder(env_with_pending({"one": None, "two": None}), "verify_shopping_account", {"otp": "ONE-TIME-PASSWD"})
    assert not resolve_fixture_placeholder(env_with_pending({}), "verify_shopping_account", {"otp": "one-time-password"})[1]


def test_failure_preconditions_not_called_success():
    assert category("Please login your shopping account first.") == "login_precondition_missing"
    assert category("One Time Password is incorrect, verification failed.") == "verification_or_login_failed"
    assert category("Please verify your account to proceed.") == "verification_pending_not_completed_effect"
    assert category("Completed.") == "no_error_flag_observed_not_success_proof"
