"""Denominator, unknown, paired interval and clustering regressions."""

import pytest

from experiments.paper_v2.claude_revision_analysis_v1 import analyze, endpoint, paired


def test_unknown_not_safe_zero():
    result = endpoint([{"unsafe_effect": True}, {"unsafe_effect": False}, {"unsafe_effect": None}], "unsafe_effect", 4)
    assert result["true"] == 1 and result["observed"] == 2
    assert result["unknown"] == 2
    assert result["itt_lower"] == .25 and result["itt_upper"] == .75
    assert result["observed_rate"] == .5


def test_unknown_all_has_no_observed_rate():
    result = endpoint([{"task_completion": None}], "task_completion", 2)
    assert result["observed_rate"] is None
    assert result["observed_wilson_95"] == (None, None)
    assert (result["itt_lower"], result["itt_upper"]) == (0, 1)


def test_zero_event_wilson_bound_positive():
    result = endpoint([{"unsafe_effect": False}] * 30, "unsafe_effect", 30)
    assert result["observed_wilson_95"][1] > 0


def _rows(values):
    return [{"case_id": str(i), "underlying_task_id": str(i // 2), "condition_id": condition, "authorization_regime": "auto_compiled", "unsafe_effect": val}
            for i, pair in enumerate(values) for condition, val in zip(("policy", "full"), pair)]


def test_paired_zero_bootstrap_reports_fallback():
    result = paired(_rows([(False, False)] * 30), "unsafe_effect", ("policy", "auto_compiled"), ("full", "auto_compiled"))
    assert result["bootstrap"]["degenerate"]
    assert result["bootstrap"]["ci_low"] is None
    assert result["paired_interval"]["ci_low"] < 0 < result["paired_interval"]["ci_high"]
    assert result["bootstrap"]["clusters"] == 15


def test_paired_unknown_excluded_explicitly():
    result = paired(_rows([(False, True), (True, None), (False, False)]), "unsafe_effect", ("policy", "auto_compiled"), ("full", "auto_compiled"))
    assert result["known_pairs"] == 2 and result["unknown_pairs"] == 1
    assert result["paired_interval"]["estimate"] == .5


def test_non_boolean_endpoint_rejected():
    with pytest.raises(ValueError, match="boolean"):
        endpoint([{"unsafe_effect": 0}], "unsafe_effect", 1)


@pytest.mark.parametrize("fault", ["response_id", "local_id", "call_cap"])
def test_final_check_rejects_invalid_request_evidence(tmp_path, monkeypatch, fault):
    from experiments.paper_v2 import claude_revision_analysis_v1 as module
    plan = {"work_key": "fixture", "case_id": "case", "condition_id": "m3_policy_only", "model_id": "deepseek-v4-pro", "runtime_version": "corrected_v2", "authorization_regime": "auto_compiled", "prompt_factor": "normal", "max_provider_calls": 8}
    request = {"local_request_id": "local", "payload_sha256": "digest", "provider_response_id": "official", "returned_model": "deepseek-v4-pro", "response_received": True}
    row = {**plan, "attempt": 1, "operational_status": "completed", "provider_requests": [request], "provider_call_count": 1}
    if fault == "response_id":
        request.pop("provider_response_id")
    elif fault == "local_id":
        request.pop("local_request_id")
    else:
        row["provider_call_count"] = 9
    monkeypatch.setattr(module, "read_jsonl", lambda p: [plan] if p.name == "study_plan.jsonl" else [row] if p.name == "deepseek_pro_raw.jsonl" else [])
    with pytest.raises(ValueError):
        analyze(tmp_path)
