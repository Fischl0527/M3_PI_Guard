"""新研究统计边界：重复不是独立样本，未知不等于安全零。"""
from copy import deepcopy

import pytest

from experiments.paper_v2.task_contract_analysis_v1 import summarize


def plan(task="t1", condition="old_policy", repeat=1, model="pro"):
    """仅用于单元测试的微型计划，不伪装成正式实验输入。"""
    return {
        "work_key": f"{model}:{task}:{condition}:{repeat}",
        "base_task_id": task,
        "cluster_id": task,
        "benchmark": "complex-workflows-v1",
        "family": "retrieve_read_write",
        "scenario": "normal",
        "model_key": model,
        "model_id": "gemini-3.6-flash" if model == "gemini" else "deepseek-v4-pro",
        "condition_id": condition,
        "replicate_index": repeat,
        "max_provider_calls": 12,
    }


def record(row, completion=True, unsafe=False, response=True, attempt=1):
    """显式假收据，仅在测试内构造，无网络调用。"""
    request = {
        "local_request_id": f"unit-test:{row['work_key']}:{attempt}",
        "payload_sha256": "unit-test-digest",
        "provider_response_id": f"unit-response:{row['work_key']}:{attempt}" if response else None,
        "response_received": response,
        "returned_model": row["model_id"] if response else None,
    }
    return {
        **row, "attempt": attempt, "response_obtained": response,
        "operational_status": "completed" if response else "provider_failure",
        "task_completion": completion, "unsafe_effect": unsafe,
        "provider_requests": [request], "provider_call_count": 1,
        "provider_tools_enabled": False, "real_external_effects": 0,
        "evaluator_fields_online": 0, "latency_seconds": 1.0,
        "token_usage": {"input": 20, "output": 10}, "cost_estimate_cny": 0.01,
    }


def test_pending_and_unknown_stay_in_planned_denominator():
    rows = [plan("t1"), plan("t2"), plan("t3")]
    result = summarize(rows, [record(rows[0]), record(rows[1], None, None)], bootstrap_draws=20)
    cell = result["cells"][0]
    assert cell["task_completion"]["numerator"] == 1
    assert cell["task_completion"]["planned_denominator"] == 3
    assert cell["task_completion"]["unknown"] == 2
    assert cell["unsafe_effect"]["unknown"] == 2
    assert cell["task_completion"]["itt_upper"] == 1
    assert result["coverage"]["pending"] == 1


def test_two_replicates_are_retained_and_task_count_not_doubled():
    rows = [plan("t1", repeat=1), plan("t1", repeat=2)]
    result = summarize(rows, [record(row) for row in rows], bootstrap_draws=20)
    assert result["cells"][0]["planned_records"] == 2
    assert result["cells"][0]["base_tasks"] == 1
    assert result["cells"][0]["clusters"] == 1


def test_response_bearing_work_key_cannot_be_repeated():
    row = plan()
    with pytest.raises(ValueError, match="response-bearing"):
        summarize([row], [record(row), record(row, attempt=2)], bootstrap_draws=20)


def test_no_response_recovery_keeps_first_attempt_cost_and_failure():
    row = plan()
    result = summarize([row], [record(row, None, None, False), record(row, attempt=2)], bootstrap_draws=20)
    assert result["coverage"]["attempts"] == 2
    assert result["coverage"]["terminal_records"] == 1
    assert result["burden"]["provider_calls"] == 2
    assert result["burden"]["cost_estimate_cny"] == pytest.approx(.02)


@pytest.mark.parametrize("field,value", [("provider_tools_enabled", True), ("real_external_effects", 1), ("evaluator_fields_online", 1)])
def test_safety_violation_rejected(field, value):
    row = plan()
    raw = record(row)
    raw[field] = value
    with pytest.raises(ValueError, match="safety"):
        summarize([row], [raw], bootstrap_draws=20)


def test_returned_model_drift_rejected():
    row = plan()
    raw = record(row)
    raw["provider_requests"][0]["returned_model"] = "other-model"
    with pytest.raises(ValueError, match="model"):
        summarize([row], [raw], bootstrap_draws=20)


def test_integer_endpoint_is_not_boolean_evidence():
    row = plan()
    with pytest.raises(ValueError, match="boolean"):
        summarize([row], [record(row, completion=0)], bootstrap_draws=20)


def test_partial_gemini_does_not_claim_full_cross_provider_replication():
    conditions = ["no_defense", "old_policy", "old_full", "new_policy", "new_full"]
    rows = [plan(condition=name, model="gemini") for name in conditions]
    result = summarize(rows, [record(rows[0])], bootstrap_draws=20)
    assert result["providers"]["gemini"]["status"] == "partial_diagnostic"
    assert result["providers"]["gemini"]["complete_five_condition_blocks"] == 0


def test_zero_events_do_not_produce_certain_zero_bootstrap_interval():
    rows = [plan(f"t{i}", condition=condition, repeat=repeat)
            for i in range(3) for condition in ("old_policy", "new_policy") for repeat in (1, 2)]
    result = summarize(rows, [record(row, False, False) for row in rows], bootstrap_draws=30)
    comparison = next(row for row in result["comparisons"] if row["endpoint"] == "task_completion")
    assert comparison["bootstrap"]["degenerate"] is True
    assert comparison["bootstrap"]["ci_low"] is None
    assert comparison["bootstrap"]["ci_high"] is None
    assert comparison["per_replicate"][0]["paired_interval"]["ci_high"] > 0


def test_same_cluster_across_tasks_is_resampled_as_one_cluster():
    rows = [plan(task, condition=condition) for task in ("atomic", "composite") for condition in ("old_policy", "new_policy")]
    for row in rows:
        row["cluster_id"] = "shared_atomic_family"
    result = summarize(rows, [record(row, row["condition_id"] == "new_policy") for row in rows], bootstrap_draws=20)
    assert result["comparisons"][0]["bootstrap"]["clusters"] == 1


def test_duplicate_plan_and_cumulative_call_overrun_rejected():
    row = plan()
    with pytest.raises(ValueError, match="duplicate"):
        summarize([row, deepcopy(row)], [], bootstrap_draws=20)
    first = record(row, None, None, False)
    second = record(row, attempt=2)
    row["max_provider_calls"] = 1
    with pytest.raises(ValueError, match="cumulative"):
        summarize([row], [first, second], bootstrap_draws=20)


def test_repeat_aggregation_weights_tasks_not_observed_execution_count():
    rows = [plan(task, condition=condition, repeat=repeat)
            for task in ("t1", "t2") for condition in ("old_policy", "new_policy") for repeat in (1, 2)]
    raw = []
    for row in rows:
        completion = row["condition_id"] == "new_policy" and row["base_task_id"] == "t1"
        if row["base_task_id"] == "t2" and row["replicate_index"] == 2:
            completion = None
        raw.append(record(row, completion))
    comparison = summarize(rows, raw, bootstrap_draws=20)["comparisons"][0]
    assert comparison["estimate"] == .5
    assert comparison["known_execution_pairs"] == 3
    assert comparison["known_base_tasks"] == 2


def test_not_run_terminal_rows_do_not_create_complete_provider_pairing():
    rows = [plan(condition=name, model="gemini") for name in
            ("no_defense", "old_policy", "old_full", "new_policy", "new_full")]
    raw = []
    for row in rows:
        value = record(row, None, None, response=False)
        value.update(attempt=0, operational_status="not_run", provider_requests=[], provider_call_count=0)
        raw.append(value)
    provider = summarize(rows, raw, bootstrap_draws=20)["providers"]["gemini"]
    assert provider["pending"] == 0
    assert provider["complete_response_pairing"] is False


def test_cli_checks_nested_pending_plan_before_statistics(tmp_path, monkeypatch):
    import json
    from experiments.paper_v2 import task_contract_analysis_v1 as module
    path = tmp_path / "plans/pro/main_plan_v1.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(plan()) + "\n", encoding="utf-8")
    monkeypatch.setattr(module, "summarize", lambda *a, **kw: pytest.fail("pending study must not bootstrap"))
    with pytest.raises(SystemExit, match="未闭合"):
        module.main(["--output", str(tmp_path)])


def test_ablation_reuses_only_selected_main_pairs():
    from experiments.paper_v2.task_contract_analysis_v1 import summarize_ablations
    main = [plan(task, condition="new_full", repeat=repeat)
            for task in ("selected", "unselected") for repeat in (1, 2)]
    ablation = [plan("selected", condition="static_binding", repeat=repeat) for repeat in (1, 2)]
    result = summarize_ablations(main, [record(row) for row in main], ablation,
                                [record(row, False) for row in ablation], bootstrap_draws=20)
    comparison = result["comparisons"][0]
    assert comparison["base_tasks"] == 1
    assert comparison["planned_execution_pairs"] == 2
    assert comparison["estimate"] == -1


def test_compiler_keeps_failed_first_draft_when_later_drafts_succeed():
    from experiments.paper_v2.task_contract_analysis_v1 import compilation_summary
    rows = [{"base_task_id": "t", "draft_index": index, "compiler_input_sha256": "fixed",
             "compile_status": "compile_failure" if index == 1 else "compiled", "draft": {}}
            for index in (1, 2, 3)]
    result = compilation_summary(rows)
    assert result["first_statuses"] == {"compile_failure": 1}
    assert result["tasks"][0]["successful_drafts"] == 2
    rows[2]["compiler_input_sha256"] = "changed"
    with pytest.raises(ValueError, match="changed"):
        compilation_summary(rows)
