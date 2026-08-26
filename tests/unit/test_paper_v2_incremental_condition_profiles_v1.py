from __future__ import annotations

from typing import Any, Mapping

from experiments.paper_v2.contracts import compute_online_visible_field_digest
from experiments.paper_v2.formal_condition_executors import (
    ALL_CONDITION_PROFILES,
    INCREMENTAL_CONDITION_PROFILES,
    INCREMENTAL_FACTOR_CONDITIONS,
    OnlineExecutorContext,
    build_incremental_condition_dispatcher,
)
from experiments.paper_v2.medium_runtime import (
    M3_FULL_CONDITIONS,
    M3_POLICY_CONDITIONS,
    build_initial_online_state,
)


def _record() -> dict[str, Any]:
    return {
        "trusted_user_request": "Write a summary to sandbox/public/profile_test.txt.",
        "trusted_app_context": {"workspace_scope": "sandbox/public"},
        "untrusted_content": "Fixed untrusted reference text.",
        "untrusted_memory": [],
    }


def _item(condition_id: str) -> dict[str, Any]:
    return {
        "work_key": f"incremental-profile:{condition_id}",
        "condition_id": condition_id,
        "authorization_regime": "auto_compiled",
        "max_provider_calls": 8,
    }


class _Runtime:
    def execute(self, context: OnlineExecutorContext, profile: Any) -> Mapping[str, Any]:
        assert context.condition_id == profile.condition_id
        return {
            "events": [],
            "operational_status": "completed",
            "result_tier": "stub",
            "provider_attestation": {
                "endpoint_type": "stub",
                "provider_name": "incremental-test",
                "upstream_provider": None,
                "model_id": "fixture",
                "model_revision": None,
                "request_id": None,
                "response_id": None,
                "requested_at": "2026-08-26T00:00:00+08:00",
                "parameters_sha256": "0" * 64,
                "prompt_rewrite_declaration": "not_applicable",
                "identity_evidence": "not_applicable",
                "identity_verified": False,
                "evidence_level": "stub_only",
            },
            "recorded_at": "2026-08-26T00:00:00+08:00",
        }


class _Evaluator:
    def evaluate(
        self, work_item: Mapping[str, Any], raw_trace: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        del work_item, raw_trace
        return {"unsafe_effect": False, "task_completion": False}


def test_incremental_profiles_cross_prompt_and_module_factors() -> None:
    expected = {
        "m3_policy_only": ("normal", ["policy"]),
        "m3_policy_safe_prompt": ("safe_prompt", ["policy"]),
        "m3_full_normal_prompt": (
            "normal",
            ["confirmation", "dataflow", "policy", "provenance", "temporal"],
        ),
        "m3_full": (
            "safe_prompt",
            ["confirmation", "dataflow", "policy", "provenance", "temporal"],
        ),
    }
    for condition_id, (prompt, modules) in expected.items():
        item = _item(condition_id)
        state = build_initial_online_state(item, {"benchmark": "m3-v2"}, _record())
        control = state["runtime_control"]
        assert control["prompt_profile"] == prompt
        assert control["guard_modules"] == modules
        assert control["authorization"]["authorization_regime"] == "auto_compiled"
        assert compute_online_visible_field_digest(state)["forbidden_fields_present"] is False


def test_incremental_profile_registry_does_not_rewrite_historical_profiles() -> None:
    assert set(INCREMENTAL_CONDITION_PROFILES) == {
        "m3_policy_safe_prompt",
        "m3_full_normal_prompt",
    }
    assert M3_POLICY_CONDITIONS == {
        "m3_policy_only",
        "m3_policy_safe_prompt",
    }
    assert M3_FULL_CONDITIONS == {"m3_full", "m3_full_normal_prompt"}
    assert ALL_CONDITION_PROFILES["m3_policy_only"].m3_prompt_profile == "normal"
    assert ALL_CONDITION_PROFILES["m3_full"].m3_prompt_profile == "safe_prompt"


def test_incremental_dispatcher_registers_exact_four_cells() -> None:
    dispatcher = build_incremental_condition_dispatcher(
        runtime=_Runtime(), evaluator=_Evaluator()
    )
    assert dispatcher.registered_conditions() == tuple(
        sorted(INCREMENTAL_FACTOR_CONDITIONS)
    )
