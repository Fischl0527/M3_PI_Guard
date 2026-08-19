from __future__ import annotations

import pytest

import experiments.paper_v2.adaptive_cost_canary_plan_v1 as canary_plan
import experiments.paper_v2.adaptive_formal_plan_v2 as plan


def test_full_pro_panel_extends_the_admitted_prefix_without_replay() -> None:
    candidate = plan.build_candidate()
    scope = candidate["scope"]

    assert scope["task_count"] == 40
    assert len({task["case_id"] for task in scope["tasks"]}) == 40
    assert scope["known_work_key_count"] == 80_000
    assert scope["query_budget_nodes"] == [50, 200, 500]
    assert scope["saturation_budget"] == 2000
    assert scope["hard_limit_cny"] == 180.0
    assert scope["formal_prefix"]["terminal_query_count"] == 374
    assert scope["formal_prefix"]["completed_provider_call_count"] == 562
    assert scope["terminal_queries_must_not_be_replayed"] is True
    assert candidate["safety_boundary"]["automatic_retries"] == 0
    assert candidate["safety_boundary"]["external_effects_enabled"] is False


def test_canary_work_keys_are_an_exact_subset_of_the_extended_universe() -> None:
    candidate = plan.build_candidate()
    extended = set(plan.all_query_work_keys(candidate["scope"]["tasks"]))
    canary = canary_plan.verify_candidate()
    prefix = set(
        canary_plan.all_query_work_keys(
            [{"case_id": task["case_id"]} for task in canary["scope"]["tasks"]]
        )
    )

    assert len(prefix) == 400
    assert prefix < extended


def test_query_projection_supports_saturation_and_hides_evaluator_fields() -> None:
    candidate = plan.build_candidate()
    case_id = candidate["scope"]["tasks"][0]["case_id"]
    item, state = plan.build_query_work_item_and_state(
        candidate,
        case_id=case_id,
        query_index=2000,
        mutated_payload="synthetic adaptive candidate",
    )

    assert item["work_key"].endswith("q02000")
    assert item["initial_online_visible_field_digest"]["forbidden_fields_present"] is False
    assert "offline_evaluation" not in str(state)
    with pytest.raises(plan.AdaptiveFormalPlanV2Error):
        plan.adaptive_query_work_key(case_id, 2001)


def test_candidate_build_is_offline_and_outcome_blind() -> None:
    candidate = plan.build_candidate()

    assert candidate["authorization"]["stage_execution_authorized"] is False
    assert candidate["authorization"][
        "hardest_subset_selection_authorized_before_budget_500"
    ] is False
    assert candidate["evidence_boundary"] == {
        "credentials_read": False,
        "network_calls_made": 0,
        "scientific_outcomes_aggregated": False,
        "existing_terminal_queries_retried": 0,
    }
