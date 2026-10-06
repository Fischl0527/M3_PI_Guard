import pytest

from experiments.paper_v2.research_followup_diagnosis_v1 import classify, diagnose


def test_completion_and_failure_are_not_mutually_exclusive():
    row = classify({"task_completion": True, "operational_status": "parse_failure", "events": [{"parse_ok": False}]})
    assert row["final_completion_category"] == "observed_task_completed"
    assert row["failure_after_observed_completion"]
    assert row["first_block_category"] == "invalid_model_proposal"


def test_missing_permission_does_not_invent_dynamic_target_cause():
    row = classify({"task_completion": False, "events": [{"step": 1, "guard_decision": "ASK", "reason_code": "permission_expansion", "violated_constraints": ["tool_outside_current_permission"]}]})
    assert row["first_block_category"] == "missing_tool_permission"
    assert row["dynamic_target_cause"].startswith("unknown")


def test_unknown_completion_stays_unknown_and_execution_not_grader_bug():
    assert classify({})["final_completion_category"] == "completion_unknown"
    row = classify({"task_completion": False, "events": [{"simulated_action_executed": True}]})
    assert row["final_completion_category"] == "executed_actions_but_task_not_completed"


def test_boundary_and_duplicate_work_key():
    row = classify({"events": [{"isolation_rejected": True}]})
    assert row["first_block_category"] == "isolated_boundary_rejection"
    with pytest.raises(ValueError, match="duplicate"):
        diagnose([{"work_key": "x"}, {"work_key": "x"}])
