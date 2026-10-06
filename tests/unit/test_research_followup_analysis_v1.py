import copy

import pytest

from experiments.paper_v2 import research_followup_analysis_v1 as analysis_module
from experiments.paper_v2.research_followup_analysis_v1 import (
    analyze,
    refresh_latency,
    summarize_latency,
    write_latency_outputs,
)
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


def test_real_runtime_latency_object_is_not_discarded():
    plan, rows = fixtures()
    for row in rows:
        row["latency_ms"] = {"total": 2100.0, "model": 1600.0, "guard": 1.5, "tool": 0.4}
    result = analyze(plan, rows)
    assert all(cell["latency_p50_ms"] == 2100.0 for cell in result["cells"])
    assert all(cell["latency_p95_ms"] == 2100.0 for cell in result["cells"])


def test_latency_formats_missing_invalid_and_components_are_separate():
    values = [{"total": 10, "model": 5, "guard": 0}, 30, None, -1, float("inf"), float("nan"), True, "10", {}]
    result = summarize_latency([{"latency_ms": value} for value in values])
    assert result["latency_sample_count"] == 2
    assert result["latency_missing_count"] == 2
    assert result["latency_invalid_count"] == 5
    assert result["latency_p50_ms"] == 20
    assert result["latency_p95_ms"] == pytest.approx(29)
    assert result["latency_format_counts"] == {"object": 2, "scalar": 4, "missing": 1, "invalid": 2}
    assert result["latency_components"]["model"] == {"observed": 1, "missing": 8, "invalid": 0, "p50_ms": 5, "p95_ms": 5}
    assert result["latency_components"]["guard"]["p50_ms"] == 0
    assert result["latency_components"]["tool"]["p50_ms"] is None


def test_latency_object_invalid_total_not_replaced_by_sum_of_components():
    result = summarize_latency([{"latency_ms": {"total": -5, "model": 100, "guard": True, "tool": float("inf")}}])
    assert result["latency_p50_ms"] is None
    assert result["latency_invalid_count"] == 1
    assert result["latency_components"]["model"]["p50_ms"] == 100
    assert result["latency_components"]["guard"]["invalid"] == 1
    assert result["latency_components"]["tool"]["invalid"] == 1


def test_latency_only_refresh_uses_cache_without_repeating_inference_or_writes(tmp_path, monkeypatch):
    plan, rows = fixtures()
    cached = analyze(plan, rows)
    original = copy.deepcopy(cached)
    for row in rows:
        row["latency_ms"] = {"total": 1000, "model": 500, "guard": 1, "tool": 0}

    def forbidden(*args, **kwargs):
        raise AssertionError("inferential recomputation is forbidden in latency-only mode")

    monkeypatch.setattr(analysis_module, "analyze", forbidden)
    monkeypatch.setattr(analysis_module, "paired", forbidden)
    result = refresh_latency(cached, plan, rows)
    assert cached == original
    assert result["overall"]["latency_sample_count"] == len(rows)
    assert result["overall"]["latency_p50_ms"] == 1000
    assert "comparisons" not in result
    (tmp_path / "tables").mkdir()
    originals = [tmp_path / "raw_records.jsonl", tmp_path / "analysis.json", tmp_path / "tables" / "cells.csv"]
    for path in originals:
        path.write_text("keep original", encoding="utf-8")
    write_latency_outputs(result, tmp_path)
    assert all(path.read_text(encoding="utf-8") == "keep original" for path in originals)
    assert (tmp_path / "latency_analysis_v2.json").exists()
    assert (tmp_path / "tables" / "latency_v2.csv").exists()
    assert (tmp_path / "latency_note_v2.md").exists()


@pytest.mark.parametrize("mutation", ["cohort", "duplicate_cell", "missing_cell", "cell_count", "statuses", "calls"])
def test_latency_only_rejects_stale_or_wrong_cache(mutation):
    plan, rows = fixtures()
    cached = analyze(plan, rows)
    if mutation == "cohort":
        cached["study_id"] = "wrong"
    elif mutation == "duplicate_cell":
        cached["cells"].append(copy.deepcopy(cached["cells"][0]))
    elif mutation == "missing_cell":
        cached["cells"].pop()
    elif mutation == "cell_count":
        cached["cells"][0]["recorded"] += 1
    elif mutation == "statuses":
        cached["cells"][0]["statuses"] = {}
    else:
        cached["cells"][0]["provider_calls"] += 1
    with pytest.raises(ValueError, match="cached analysis"):
        refresh_latency(cached, plan, rows)


def test_latency_only_preserves_missing_rows_and_rejects_response_replay():
    plan, rows = fixtures()
    rows[0]["latency_ms"] = None
    cached = analyze(plan, rows[:-1])
    result = refresh_latency(cached, plan, rows[:-1])
    assert result["planned"] == 16
    assert result["recorded"] == 15
    assert result["overall"]["latency_missing_count"] == 1
    with pytest.raises(ValueError, match="response-bearing"):
        refresh_latency(cached, plan, rows[:-1] + [rows[0]])
