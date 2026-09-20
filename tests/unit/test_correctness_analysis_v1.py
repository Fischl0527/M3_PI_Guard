from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.paper_v2.correctness_analysis_v1 import (
    CONDITIONS,
    analyze,
    endpoint_summary,
    report_markdown,
    write_analysis,
)


def plans(n=2, *, model="deepseek_pro", benchmark="m3-v2", category="attack"):
    return [
        {
            "work_key": f"{model}:{benchmark}:{task}:{condition}",
            "case_id": f"{benchmark}:{task}",
            "underlying_task_id": f"{benchmark}:{task}",
            "benchmark": benchmark,
            "evaluation_case_type": category,
            "condition_id": condition,
            "model_group": model,
            "model_id": "test-model",
        }
        for task in range(n)
        for condition in CONDITIONS
    ]


def raw(item, *, unsafe=False, completed=False, status="completed", response=True, attempt=1):
    return {
        **item, "attempt": attempt, "operational_status": status,
        "unsafe_effect": unsafe, "task_completion": completed,
        "response_obtained": response,
        "evaluation_details": {"simulated_unsafe_effect": unsafe},
        "provider_requests": [{"provider_response_id": "fixture" if response else None}],
        "ask_count": 1, "deny_count": 2, "latency_ms": {"total": 10.0 * attempt},
        "token_usage": {"input": 4, "output": 2, "total": 6},
        "cost": {"currency": "CNY", "amount": 0.01, "upper_estimate": True},
    }


def test_unknowns_preserve_planned_denominator_and_do_not_become_safe():
    result = endpoint_summary([True, False, None, None])
    assert result["x"] == 1
    assert result["n_observed"] == 2
    assert result["n_plan"] == 4
    assert result["rate_observed"] == 0.5
    assert result["planned_lower_bound"] == 0.25
    assert result["planned_upper_bound"] == 0.75


def test_zero_observed_has_no_estimate_or_confidence_interval():
    result = endpoint_summary([None, None])
    assert result["rate_observed"] is None
    assert result["wilson_ci_low"] is None
    assert result["wilson_ci_high"] is None
    assert result["planned_lower_bound"] == 0
    assert result["planned_upper_bound"] == 1
    assert endpoint_summary([])["planned_lower_bound"] is None


def test_missing_and_quota_rows_are_administrative_not_response_failures():
    plan = plans()
    quota = raw(plan[0], unsafe=None, completed=None, status="quota_stopped", response=False)
    result = analyze(plan, [quota])
    model = result["models"][0]
    assert model["n_plan"] == 12
    assert model["administrative_or_not_run"] == 12
    assert model["response_bearing"] == 0
    assert model["operational_failure"] == 0
    assert result["groups"][0]["endpoints"]["unsafe_effect"]["n_observed"] == 0


def test_observed_harm_is_retained_in_a_failure_row():
    plan = plans(1)
    record = raw(plan[0], unsafe=True, status="parse_failure")
    result = analyze(plan, [record])
    group = next(group for group in result["groups"] if group["condition_id"] == "no_defense")
    assert group["operational_failure"] == 1
    assert group["endpoints"]["unsafe_effect"]["x"] == 1
    assert group["endpoints"]["unsafe_or_failure"]["x"] == 1


def test_failure_unknown_is_pessimistically_observed_in_composite_only():
    plan = plans(1)
    result = analyze(plan, [raw(plan[0], unsafe=None, status="provider_failure", response=False)])
    group = next(group for group in result["groups"] if group["condition_id"] == "no_defense")
    assert group["endpoints"]["unsafe_effect"]["n_unknown"] == 1
    assert group["endpoints"]["unsafe_or_failure"]["x"] == 1


def test_retry_uses_one_scientific_item_but_counts_all_attempt_resources():
    plan = plans(1)
    records = [
        raw(plan[0], unsafe=None, completed=None, response=False, status="provider_failure"),
        raw(plan[0], unsafe=False, completed=True, attempt=2),
    ]
    result = analyze(plan, records)
    burden = result["models"][0]["burden_all_attempts"]
    assert result["selected_work_items"] == 6
    assert result["physical_raw_rows"] == 2
    assert burden["provider_calls"] == 2
    assert burden["token_usage"]["total"] == 12
    assert burden["cost_by_currency"]["CNY"] == 0.02
    assert burden["latency_p50_ms"] == 15
    assert burden["latency_p95_ms"] == 19.5


def test_response_bearing_retry_is_rejected():
    plan = plans(1)
    with pytest.raises(ValueError, match="response-bearing"):
        analyze(plan, [raw(plan[0]), raw(plan[0], attempt=2)])


def test_cost_peak_estimate_and_unpriced_responses_are_not_hidden():
    plan = plans(1)
    first, second = raw(plan[0]), raw(plan[1])
    first["cost"] = {
        "currency": "CNY", "amount": 0.01, "usage_complete": True,
        "unpriced_response_count": 0,
        "basis": "official_peak_tariff_upper_estimate_not_invoice",
    }
    complete = analyze(plan, [first])["models"][0]["burden_all_attempts"]
    assert complete["cost_contains_upper_estimates"] is True
    assert complete["cost_usage_complete"] is True
    second["cost"] = {
        "currency": "CNY", "amount": 0, "usage_complete": False,
        "unpriced_response_count": 1,
        "basis": "known_usage_subtotal_not_total_cost_upper_bound",
    }
    result = analyze(plan, [first, second])
    burden = result["models"][0]["burden_all_attempts"]
    assert burden["cost_usage_complete"] is False
    assert burden["unpriced_response_count"] == 1
    assert burden["cost_total_interpretation"] == "known_usage_subtotal_not_total_upper_bound"
    assert "仅已知用量小计" in report_markdown(result, [])


def test_dataflow_cumulative_counters_are_not_double_counted_or_effect_claims():
    plan = plans(1)
    record = raw(plan[0])
    record["events"] = [
        {"corrected_diagnostics": {
            "dataflow": {
                "status": status, "classified_observation_count": count,
                "unclassified_observation_count": 1,
                "labelled_value_count": 1, "matched_label_names": ["private"],
            },
            "argument_sources": [{"source_type": "tool_output", "argument_path": "body"}],
        }}
        for status, count in (("missing_input", 1), ("triggered", 2))
    ]
    result = analyze(plan, [record])
    diagnostic = result["models"][0]["dataflow_observability"]
    assert diagnostic["work_items_with_dataflow_summary"] == 1
    assert diagnostic["dataflow_event_count"] == 2
    assert diagnostic["sum_per_work_item_max_observed_counters"]["classified_observation_count"] == 2
    assert diagnostic["sum_per_work_item_max_observed_counters"]["labelled_value_count"] == 1
    assert diagnostic["dataflow_status_event_counts"] == {"missing_input": 1, "triggered": 1}
    assert diagnostic["argument_source_type_counts"] == {"tool_output": 2}
    assert "not proof of actual dataflow coverage" in diagnostic["interpretation"]
    assert "不能称为全部来源传播已覆盖" in report_markdown(result, [])


def test_duplicates_and_unknown_work_keys_are_rejected():
    plan = plans(1)
    with pytest.raises(ValueError, match="duplicate planned"):
        analyze([plan[0], plan[0]], [])
    with pytest.raises(ValueError, match="duplicate work key attempt"):
        analyze(plan, [raw(plan[0]), raw(plan[0])])
    record = raw(plan[0])
    record["work_key"] = "foreign"
    with pytest.raises(ValueError, match="outside"):
        analyze(plan, [record])


def test_pairing_keeps_complete_pairs_separate_from_planned_bounds():
    plan = plans()
    records = []
    for item in plan:
        if item["condition_id"] == "m3_policy_only":
            records.append(raw(item, unsafe=True))
        elif item["condition_id"] == "m3_full_normal_prompt" and item["case_id"].endswith(":0"):
            records.append(raw(item, unsafe=False))
    result = analyze(plan, records)
    pair = next(row for row in result["paired_comparisons"] if row["comparison"] == "module_normal")
    assert pair["n_pairs_plan"] == 2
    assert pair["n_pairs_observed"] == 1
    assert pair["estimate"] == -1.0
    assert pair["planned_difference_lower_bound"] == -1.0
    assert pair["planned_difference_upper_bound"] == -0.5
    assert pair["ci_low"] is not None


def test_all_zero_paired_interval_is_not_falsely_zero_width():
    plan = plans(3)
    result = analyze(plan, [raw(item) for item in plan])
    for pair in result["paired_comparisons"]:
        assert pair["estimate"] == 0
        assert pair["ci_low"] < 0 < pair["ci_high"]


def test_native_and_simulated_endpoints_are_never_pooled():
    m3 = plans(1)
    native = plans(1, benchmark="agentdojo-v1")
    result = analyze(m3 + native, [raw(item) for item in m3 + native])
    assert len(result["groups"]) == 12
    assert {group["endpoint_semantics"] for group in result["groups"]} == {
        "agentdojo_native_security_checker_not_state_only", "m3_simulated_successful_effect_match",
    }
    assert "unsafe_effect" not in result["models"][0]


def test_input_records_unchanged_and_false_observed_flags_rejected():
    plan = plans(1)
    record = raw(plan[0])
    before = copy.deepcopy(record)
    analyze(plan, [record])
    assert record == before
    record["evaluation_details"]["unsafe_effect_observed"] = False
    with pytest.raises(ValueError, match="conflicts"):
        analyze(plan, [record])


def test_report_explains_version_missingness_and_directory_boundaries():
    result = analyze(plans(1, model="gemini_flash"), [])
    report = report_markdown(result, [])
    assert "DeepSeek-V4.1-Flash" in report
    assert "不完整时尤其不支持正式跨厂商结论" in report
    assert "correctness_repair_v1/" in report
    assert "其他历史实验目录" in report
    assert "{work_key}.attemptN.jsonl" in report
    assert "runner.lock" in report
    assert "*/internal/" not in report
    assert "NA" in report
    assert "探索动作" in report


def test_file_generation_reads_only_supplied_development_root(tmp_path: Path):
    plan = plans(1)
    (tmp_path / "plan.jsonl").write_text("\n".join(json.dumps(item) for item in plan), encoding="utf-8")
    model_root = tmp_path / "deepseek_pro"
    model_root.mkdir()
    (model_root / "raw_records.jsonl").write_text("\n".join(json.dumps(raw(item)) for item in plan), encoding="utf-8")
    result = write_analysis(tmp_path)
    assert result["plan_rows"] == 6
    assert len(list((tmp_path / "figures").glob("*.png"))) == 2
    assert len(list((tmp_path / "tables").glob("*.csv"))) == 3
    assert (tmp_path / "analysis.json").exists()
    assert (tmp_path / "report.md").exists()
