"""正式资产冻结前验证真实任务结构、后端效果及独立评分，不调用API。"""
from collections import Counter
from copy import deepcopy

import pytest

from experiments.paper_v2.task_contract_cases_v1 import build_case_cohorts, load_compiler_inputs
from experiments.paper_v2.task_contract_plan_v1 import build_main_plan, build_ablation_plan
from experiments.paper_v2.task_contract_synthetic_v1 import (
    FAMILIES, SyntheticTaskBackend, build_synthetic_cases, score_synthetic,
)


def test_cohort_counts_structure_and_language_are_real_and_disjoint():
    cohorts = build_case_cohorts()
    assert len(cohorts["development"]) == 157
    assert len(cohorts["evaluation"]) == 600
    cases = build_synthetic_cases()
    assert len(cases) == 480
    assert len({case["semantic_graph_id"] for case in cases}) == 480
    assert all(2 <= len(case["offline_evaluation"]["expected_graph"]["nodes"]) <= 6 for case in cases)
    assert Counter((case["family"], case["split"], case["language"]) for case in cases) == {
        (family, split, language): count for family in FAMILIES
        for split, count in (("development", 5), ("evaluation", 25)) for language in ("zh", "en")}
    for case in cohorts["development"]:
        assert set(load_compiler_inputs(case)) == {"trusted_user_request", "trusted_app_context", "tool_schemas"}


def test_plans_have_unique_keys_prescribed_count_and_pairing():
    cases = build_case_cohorts()["evaluation"]
    plans = {model: build_main_plan(cases, model) for model in ("pro", "flash", "gemini")}
    assert all(len(rows) == 12000 and sum(row["formal_prefix"] for row in rows) == 50 for rows in plans.values())
    assert len({row["work_key"] for rows in plans.values() for row in rows}) == 36000
    assert len(build_ablation_plan(cases)) == 960
    def keys(rows):
        return {(row["base_task_id"], row["scenario"], row["condition_id"], row["replicate_index"]) for row in rows}
    assert keys(plans["pro"]) == keys(plans["flash"]) == keys(plans["gemini"])
    assert all(row["max_provider_calls"] == 12 for rows in plans.values() for row in rows)


@pytest.mark.parametrize("family", FAMILIES)
def test_all_reference_workflows_execute_and_are_independently_scored(family):
    for case in (case for case in build_synthetic_cases() if case["family"] == family):
        backend = SyntheticTaskBackend(case["online"])
        for action in case["offline_evaluation"]["expected_graph"]["nodes"]:
            backend.execute(action["tool"], action["arguments"])
        result = score_synthetic(case["offline_evaluation"], backend)
        assert result["task_completion"] is True, case["base_task_id"]
        assert result["unsafe_effect"] is False, case["base_task_id"]


def test_legitimate_completion_and_additional_unsafe_effect_can_coexist():
    case = next(case for case in build_synthetic_cases() if case["effect_tool"] == "send_message")
    backend = SyntheticTaskBackend(case["online"])
    for action in case["offline_evaluation"]["expected_graph"]["nodes"]:
        backend.execute(action["tool"], action["arguments"])
    malicious = deepcopy(case["offline_evaluation"]["expected_effects"][0]["arguments"])
    malicious["recipient_id"] = case["offline_evaluation"]["forbidden_recipient_ids"][0]
    backend.execute("send_message", malicious)
    result = score_synthetic(case["offline_evaluation"], backend)
    assert result["task_completion"] is True
    assert result["unsafe_effect"] is True
    assert result["safe_completion"] is False


def test_calendar_operation_changes_real_state_and_membership_lookup_has_results():
    cases = build_synthetic_cases()
    calendar = next(case for case in cases if case["family"] == "calendar_order")
    backend = SyntheticTaskBackend(calendar["online"])
    action = next(action for action in calendar["offline_evaluation"]["expected_graph"]["nodes"] if action["tool"] == "schedule_event")
    backend.execute(action["tool"], action["arguments"])
    assert backend.snapshot()["objects"][action["arguments"]["object_id"]]["calendar_state"] == "scheduled"
    hop = next(case for case in cases if case["family"] == "multihop_recipient")
    backend = SyntheticTaskBackend(hop["online"])
    second = hop["offline_evaluation"]["expected_graph"]["nodes"][1]
    result = backend.execute(second["tool"], second["arguments"])
    assert result["objects"]
    assert all(obj["kind"] == "contact" for obj in result["objects"])
    assert backend.discovery_complete(second["tool"], second["arguments"]) is True
