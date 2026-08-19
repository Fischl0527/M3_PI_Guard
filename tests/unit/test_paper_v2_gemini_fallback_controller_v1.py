from __future__ import annotations

import copy

import pytest

from experiments.paper_v2.gemini_fallback_controller_v1 import (
    EXPECTED_PRIMARY_ROWS,
    EXPECTED_PROBE_ROWS,
    EXPECTED_ROWS,
    MODEL_ID,
    OWNER_STATEMENT_SHA256,
    SELECTED_CONDITIONS,
    GeminiFallbackControllerError,
    _effective_policy,
    _validate_runtime_config,
    build_candidate,
    build_controller_qualification,
    build_plan_rows,
)


def test_outcome_blind_plan_is_exact_second_model_subset() -> None:
    rows = build_plan_rows()

    assert len(rows) == EXPECTED_ROWS
    assert [row["sequence"] for row in rows] == list(
        range(1, EXPECTED_ROWS + 1)
    )
    assert {row["condition_id"] for row in rows} == set(
        SELECTED_CONDITIONS
    )
    assert len({row["work_key"] for row in rows}) == EXPECTED_ROWS
    assert len({row["execution_identity"] for row in rows}) == 1
    assert sum(
        row["analysis_tier"] == "primary" for row in rows
    ) == EXPECTED_PRIMARY_ROWS
    assert sum(
        row["analysis_tier"] == "authorization_regime_probe"
        for row in rows
    ) == EXPECTED_PROBE_ROWS
    assert all("source_work_key" in row for row in rows)
    assert all(row["result_fields_present"] is False for row in rows)


def test_effective_policy_is_free_only_and_fail_closed() -> None:
    policy = _effective_policy()

    assert policy["gemini"]["model_id"] == MODEL_ID
    assert policy["gemini"]["billing_tier"] == "free"
    assert policy["gemini"]["allow_paid_tier"] is False
    assert policy["gemini"]["monetary_hard_limit_usd"] == 0.0
    assert policy["gemini"]["local_batch_caps"] == {
        "requests": 3000,
        "input_tokens": 20_000_000,
        "output_tokens": 2_000_000,
    }
    assert policy["common_controls"]["automatic_retries"] == 0
    assert (
        policy["common_controls"]["provider_managed_tools_enabled"]
        is False
    )
    assert policy["common_controls"]["external_effects_enabled"] is False


def test_offline_qualification_covers_record_call_and_safety_chains() -> None:
    value = build_controller_qualification()

    assert value["status"] == (
        "gemini_fallback_controller_qualified_offline"
    )
    assert value["derived_work_items"] == EXPECTED_ROWS
    assert value["offline_records"] == 2
    assert value["offline_evidence_entries"] == 2
    assert value["offline_diagnostics"] == 0
    assert value["network_calls_made"] == 0
    assert value["credentials_read"] is False
    assert value["automatic_retries"] == 0
    assert value["provider_tools_enabled"] is False
    assert value["external_effects_enabled"] is False


def test_candidate_is_non_executable_and_result_blind() -> None:
    value = build_candidate()

    assert value["artifact_role"] == "owner_review_candidate"
    assert value["status"] == "candidate_frozen_non_executable"
    assert value["authorization"] == {
        "candidate_only": True,
        "canary_execution_authorized": False,
        "continuation_execution_authorized": False,
        "result_admission_authorized": False,
        "candidate_manifest_sha256": None,
        "canary_review_sha256": None,
        "owner_approval": None,
    }
    selection = value["scope"]["selection"]
    assert selection["work_items"] == EXPECTED_ROWS
    assert selection["prior_scientific_outcomes_used_for_selection"] is False
    assert value["evidence_boundary"][
        "scientific_outcomes_read_while_building"
    ] == 0


def test_runtime_config_rejects_identity_or_consent_drift() -> None:
    policy = _effective_policy()
    valid = {
        "M3_FRONTIER_API_CONSENT": "yes_for_network_smoke",
        "GEMINI_API_KEY": "unit-test-nonsecret-placeholder-value",
        "FRONTIER_GEMINI_MODEL_ID": MODEL_ID,
        "FRONTIER_GEMINI_BASE_URL": (
            "https://generativelanguage.googleapis.com/v1beta/openai/"
        ),
    }
    _validate_runtime_config(valid, policy)

    no_consent = copy.deepcopy(valid)
    no_consent["M3_FRONTIER_API_CONSENT"] = "no"
    with pytest.raises(
        GeminiFallbackControllerError,
        match="consent",
    ):
        _validate_runtime_config(no_consent, policy)

    wrong_model = copy.deepcopy(valid)
    wrong_model["FRONTIER_GEMINI_MODEL_ID"] = "different"
    with pytest.raises(
        GeminiFallbackControllerError,
        match="model",
    ):
        _validate_runtime_config(wrong_model, policy)


def test_owner_approval_is_digest_only() -> None:
    assert len(OWNER_STATEMENT_SHA256) == 64
    assert "api" not in OWNER_STATEMENT_SHA256
