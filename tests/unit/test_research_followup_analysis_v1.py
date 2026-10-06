import copy

import pytest

from experiments.paper_v2.research_followup_analysis_v1 import analyze
from experiments.paper_v2.research_followup_calibration_v1 import CORE, build_plan


def fixtures():
    plan = build_plan()[:16]
    rows = [{**r, "attempt": 1, "operational_status": "completed", "response_obtained": True,
             "unsafe_effect": False, "task_completion": True, "provider_call_count": 0, "provider_requests": [],
             "token_usage": {"total": 0}, "cost": {"amount": 0}, "latency_ms": 1} for r in plan]
    return plan, rows


def test_unknown_and_pending_keep_intention_to_treat_bounds():
    plan, rows = fixtures()
    rows[0]["task_completion"] = None
    rows[0]["unsafe_effect"] = None
    result = analyze(plan, rows[:-1])
    assert result["pending"] == 1
    assert sum(r["unsafe"]["unknown"] for r in result["cells"]) == 2
    assert all(r["unsafe"]["itt_upper"] >= r["unsafe"]["itt_lower"] for r in result["cells"])


def test_holm_family_and_zero_bootstrap_is_not_certainty():
    plan, rows = fixtures()
    result = analyze(plan, rows)
    primary = [r for r in result["comparisons"] if r["analysis_role"] == "primary_prespecified"]
    assert len(primary) == 12
    assert all(r["holm_p"] is not None for r in primary)
    assert all(r["bootstrap"].get("ci_low") is None for r in primary)
    assert all(r["paired_interval"]["ci_high"] != 0 for r in primary)


def test_completed_task_and_failure_both_retained():
    plan, rows = fixtures()
    rows[0]["operational_status"] = "parse_failure"
    result = analyze(plan, rows)
    cell = next(r for r in result["cells"] if r["benchmark"] == rows[0]["benchmark"] and r["condition_id"] == CORE[0] and r["evaluation_case_type"] == rows[0]["evaluation_case_type"])
    assert cell["completion"]["true"] == 1
    assert cell["failures"] == cell["unsafe_or_failure"]["true"] == 1


def test_missing_projection_receipt_not_counted_as_proven_no_leak():
    plan, rows = fixtures()
    for row in rows[1:]:
        row["online_forbidden_fields_present"] = False
    result = analyze(plan, rows)
    assert result["projection_receipts"] == {"explicit_no_forbidden_field": 15, "missing": 1, "forbidden_present": 0}


def test_identity_and_repeated_response_bearing_rows_rejected():
    plan, rows = fixtures()
    broken = copy.deepcopy(rows)
    broken[0]["model_id"] = "wrong"
    with pytest.raises(ValueError, match="identity"):
        analyze(plan, broken)
    with pytest.raises(ValueError, match="response-bearing"):
        analyze(plan, rows + [rows[0]])
