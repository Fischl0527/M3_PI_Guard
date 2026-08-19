from __future__ import annotations

import copy

import pytest

import experiments.paper_v2.adaptive_formal_second_plan_v1 as plan


@pytest.mark.parametrize("model_key", ["deepseek_flash", "gemini_flash"])
def test_second_model_plan_has_twenty_tasks_and_four_thousand_queries(
    model_key: str,
) -> None:
    candidate = plan.build_candidate(model_key)
    scope = candidate["scope"]

    assert scope["task_count"] == 20
    assert scope["query_budget_nodes"] == [50, 200]
    assert scope["known_work_key_count"] == 4_000
    assert scope["maximum_provider_calls"] == 32_000
    assert candidate["authorization"]["stage_execution_authorized"] is False
    assert candidate["safety_boundary"]["automatic_retries"] == 0


def test_deepseek_and_gemini_plans_are_task_paired_but_state_isolated() -> None:
    deepseek = plan.build_candidate("deepseek_flash")
    gemini = plan.build_candidate("gemini_flash")

    assert [task["case_id"] for task in deepseek["scope"]["tasks"]] == [
        task["case_id"] for task in gemini["scope"]["tasks"]
    ]
    assert deepseek["execution_identity"] != gemini["execution_identity"]
    assert deepseek["scope"]["known_work_key_sequence_sha256"] != gemini[
        "scope"
    ]["known_work_key_sequence_sha256"]
    assert deepseek["scope"]["output_namespace"] != gemini["scope"][
        "output_namespace"
    ]


def test_query_projection_changes_only_untrusted_content() -> None:
    candidate = plan.build_candidate("deepseek_flash")
    task = candidate["scope"]["tasks"][0]

    item, state = plan.build_query_work_item_and_state(
        candidate,
        case_id=task["case_id"],
        query_index=200,
        mutated_payload="synthetic mutation for isolated evaluation",
    )

    assert item["work_key"].endswith("__q00200")
    assert item["initial_online_visible_field_digest"][
        "forbidden_fields_present"
    ] is False
    assert "evaluator" not in state
    assert "gold" not in state


def test_candidate_rejects_provider_identity_tampering() -> None:
    candidate = plan.build_candidate("gemini_flash")
    tampered = copy.deepcopy(candidate)
    tampered["scope"]["model_id"] = "another-model"

    with pytest.raises(plan.AdaptiveFormalSecondPlanV1Error):
        plan.validate_candidate(tampered, model_key="gemini_flash")
