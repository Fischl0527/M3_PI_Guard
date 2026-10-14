"""验证未知分母、配对身份和全零经验区间边界。"""
import pytest

from experiments.paper_v2.task_contract_v4_development_analysis_v1 import compilation_summary, endpoint, latest_records, paired_effect, summarize, usage_summary


def rows():
    return [dict(work_key=c, base_task_id="b", model_key="pro", development_cohort="qualification",
                 benchmark="m3-v2", scenario="benign", condition_id=c)
            for c in ("no_defense", "v3_policy", "v3_full", "v4_policy", "v4_full")]


def test_unknown_remains_in_planned_bounds():
    value = endpoint([True, False, None])
    assert value["numerator"] == 1 and value["observed_denominator"] == 2
    assert value["unknown"] == 1 and value["itt_lower"] == pytest.approx(1 / 3)
    assert value["itt_upper"] == pytest.approx(2 / 3)


def test_pending_is_not_safe_zero():
    value = summarize(rows(), [], draws=30)
    assert value["coverage"]["pending"] == 5
    assert all(cell["unsafe_effect"]["rate"] is None for cell in value["cells"])


def test_all_zero_bootstrap_is_not_zero_certainty():
    pair = [dict(base_task_id="b", condition_id=c, unsafe_effect=False) for c in ("v3_policy", "v4_policy")]
    value = paired_effect(pair, "v3_policy", "v4_policy", "unsafe_effect", draws=30, label="test")
    assert value["difference"] == 0 and value["cluster_bootstrap95"] is None
    assert value["conservative_wilson_difference95"][0] < 0 < value["conservative_wilson_difference95"][1]


def test_response_bearing_rows_cannot_retry():
    initial = {**rows()[0], "attempt": 1, "operational_status": "parse_failure", "provider_requests": [{"response_received": True}]}
    with pytest.raises(ValueError, match="response-bearing"):
        latest_records(rows(), [initial, {**initial, "attempt": 2}])


def test_false_true_pair_and_unknown_bounds():
    pair = [dict(base_task_id="a", condition_id="v3_policy", unsafe_effect=False),
            dict(base_task_id="a", condition_id="v4_policy", unsafe_effect=True),
            dict(base_task_id="b", condition_id="v3_policy", unsafe_effect=None),
            dict(base_task_id="b", condition_id="v4_policy", unsafe_effect=None)]
    value = paired_effect(pair, "v3_policy", "v4_policy", "unsafe_effect", draws=30, label="test")
    assert value["difference"] == 1 and value["planned_pairs"] == 2
    assert value["itt_difference_lower"] == 0 and value["itt_difference_upper"] == 1


def test_compiler_repair_does_not_erase_first_failure():
    base = dict(base_task_id="b", development_cohort="debug", compiler_version="v4", benchmark="m3-v2",
                attempt=1, response_obtained=True, provider_requests=[])
    result = compilation_summary([{**base, "compile_stage": "initial", "compiler_status": "technical_invalid"},
                                  {**base, "compile_stage": "repair_1", "compiler_status": "ready"}])[0]
    assert result["first_ready"] == 0 and result["final_ready"] == 1
    assert result["technical_repairs"] == 1 and result["stages"] == 2


def test_missing_usage_is_not_a_zero_cost_complete_receipt():
    result = usage_summary([dict(provider_requests=[dict(response_received=True)], latency_ms=None)])
    assert result["usage_missing_responses"] == 1
    assert not result["cost_complete"] and result["latency_median_ms"] is None


def test_native_total_latency_and_scalar_latency_are_both_retained():
    result = usage_summary([dict(latency_ms={"total": 1000}), dict(latency_ms=2000), dict(latency_ms=None)])
    assert result["latency_observed"] == 2 and result["latency_median_ms"] == 1500
