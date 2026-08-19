from __future__ import annotations

import copy

import pytest

import experiments.paper_v2.adaptive_formal_deepseek_flash_controller_v1 as controller
import experiments.paper_v2.adaptive_formal_pro_controller_v1 as pro
import experiments.paper_v2.adaptive_formal_second_plan_v1 as second_plan
from experiments.paper_v2.contracts import sha256_canonical_json


def test_flash_50_candidate_preserves_shared_deepseek_fuse() -> None:
    candidate = controller.build_stage_candidate("flash_50")
    scope = candidate["scope"]

    assert scope["target_budget"] == 50
    assert scope["authorized_task_count"] == 20
    assert scope["source_checkpoint_count"] == 0
    assert scope["model_id"] == "deepseek-v4-flash"
    assert scope["model_role"] == "second"
    assert scope["all_flash_stages_hard_ceiling_cny"] == 29.447195
    assert (
        round(
            scope["historical_prefix_cost_cny"]
            + scope["all_pro_stages_hard_ceiling_cny"]
            + scope["all_flash_stages_hard_ceiling_cny"],
            10,
        )
        == 180.0
    )
    assert candidate["execution_controls"]["automatic_retries"] == 0
    assert candidate["execution_controls"]["provider_tools_enabled"] is False
    assert candidate["execution_controls"]["external_effects_enabled"] is False


def test_flash_stage_caps_are_provider_isolated_and_exact() -> None:
    assert controller.STAGES["flash_50"]["hard_limit_cny"] == 5.0
    assert controller.STAGES["flash_200"]["hard_limit_cny"] == 24.447195
    assert controller.TOTAL_FLASH_CEILING_CNY == 29.447195
    assert pro.TOTAL_NEW_STAGE_CEILING_CNY == 150.0

    policy = controller._role_policy("flash_50")
    assert policy["deepseek"]["model_id"] == controller.MODEL_ID
    assert policy["deepseek"]["hard_spend_limit_cny"] == 5.0
    assert policy["deepseek"]["abort_ceiling_cny"] == 5.0
    assert policy["common_controls"]["automatic_retries"] == 0


def test_flash_admission_binds_exact_owner_boundary() -> None:
    controller.write_stage_candidate("flash_50")
    admission = controller.build_stage_admission(
        "flash_50",
        owner_statement_sha256=controller.OWNER_STATEMENT_SHA256,
        approved_at="2026-08-02T07:30:00+08:00",
    )

    assert "--stage flash_50" in admission["exact_command"]
    assert "--execute-stage" in admission["exact_command"]
    assert admission["authorization"]["terminal_query_replay_authorized"] is False
    assert admission["authorization"]["provider_tools_enabled"] is False
    assert admission["authorization"]["external_effects_enabled"] is False

    with pytest.raises(
        controller.AdaptiveFormalDeepSeekFlashControllerV1Error,
        match="owner authorization digest drift",
    ):
        controller.build_stage_admission(
            "flash_50",
            owner_statement_sha256="0" * 64,
            approved_at="2026-08-02T07:30:00+08:00",
        )


def test_flash_candidate_rejects_cost_cap_tampering() -> None:
    candidate = controller.build_stage_candidate("flash_50")
    tampered = copy.deepcopy(candidate)
    tampered["scope"]["stage_hard_limit_cny"] = 6.0
    tampered["scope_sha256"] = sha256_canonical_json(tampered["scope"])
    core = {
        key: value for key, value in tampered.items() if key != "manifest_sha256"
    }
    tampered["manifest_sha256"] = sha256_canonical_json(core)

    with pytest.raises(controller.AdaptiveFormalDeepSeekFlashControllerV1Error):
        controller.validate_stage_candidate(tampered, stage="flash_50")


def test_flash_technical_gate_requires_affirmative_outcome_boundary() -> None:
    assert controller._technical_checks_pass(
        {
            "all_authorized_tasks_terminal": True,
            "scientific_outcomes_not_aggregated": True,
        }
    )

    with pytest.raises(
        controller.AdaptiveFormalDeepSeekFlashControllerV1Error,
        match="affirmative invariants",
    ):
        controller._technical_checks_pass(
            {
                "all_authorized_tasks_terminal": True,
                "scientific_outcomes_aggregated": False,
            }
        )


def test_flash_resolver_accepts_only_frozen_work_keys() -> None:
    candidate = controller.build_stage_candidate("flash_50")
    runtime = controller._runtime_plan(candidate)
    case_id = runtime["scope"]["tasks"][0]["case_id"]
    resolver = controller._FlashResolver(runtime)
    key = second_plan.adaptive_query_work_key("deepseek_flash", case_id, 1)

    binding = resolver.resolve(key)
    assert binding.work_key == key
    assert binding.case_id == case_id
    assert binding.execution_identity == candidate["scope"]["execution_identity"]

    with pytest.raises(controller.AdaptiveFormalDeepSeekFlashControllerV1Error):
        resolver.resolve(key.replace("deepseek_v4_flash", "deepseek_v4_pro"))


def test_flash_runtime_config_rejects_wrong_model_without_exposing_key() -> None:
    policy = controller._role_policy("flash_50")
    values = {
        "M3_FRONTIER_API_CONSENT": controller.canary_v1.CONSENT_VALUE,
        "DEEPSEEK_API_KEY": "test-only-secret",
        "FRONTIER_DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "FRONTIER_DEEPSEEK_MODEL_ID": "deepseek-v4-pro",
    }

    with pytest.raises(
        controller.AdaptiveFormalDeepSeekFlashControllerV1Error,
        match="model identity drift",
    ):
        controller._validate_runtime_config(values, policy)
