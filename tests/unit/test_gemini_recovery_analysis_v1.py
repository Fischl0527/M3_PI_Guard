from __future__ import annotations

import json

import pytest

from experiments.paper_v2.gemini_recovery_analysis_v1 import analyze_recovery


CONDITIONS = (
    "no_defense", "safe_prompt_only", "m3_policy_only", "m3_policy_safe_prompt",
    "m3_full_normal_prompt", "m3_full",
)


def plan_rows(tasks=2):
    return [
        {
            "work_key": f"task-{task}:{condition}", "case_id": f"task-{task}",
            "underlying_task_id": f"task-{task}", "condition_id": condition,
            "benchmark": "m3-v2", "evaluation_case_type": "attack",
            "model_group": "gemini_flash", "model_id": "gemini-3.6-flash",
            "max_tokens": 512,
        }
        for task in range(tasks) for condition in CONDITIONS
    ]


def old_unrun(item):
    return {
        **item, "attempt": 0, "operational_status": "not_run",
        "response_obtained": False, "unsafe_effect": None, "task_completion": None,
        "provider_requests": [], "evaluation_details": {},
    }


def old_response(item):
    return {
        **item, "attempt": 1, "operational_status": "completed",
        "response_obtained": True, "unsafe_effect": False, "task_completion": True,
        "provider_requests": [{"http_status": 200, "response_received": True}],
        "evaluation_details": {},
    }


def recovered(item, *, attempt=1, prior="not_run", unsafe=False):
    return {
        **item, "attempt": attempt, "generation_profile_id": "gemini_recovery_v1",
        "max_tokens": 2048, "reasoning_effort": "low",
        "prior_operational_status": prior, "recovery_batch_id": "fixture-recovery",
        "operational_status": "completed", "response_obtained": True,
        "unsafe_effect": unsafe, "task_completion": True,
        "provider_requests": [{"http_status": 200, "response_received": True}],
        "evaluation_details": {}, "cost": {"currency": "USD", "amount": 0},
    }


def test_old_response_is_separate_and_not_spliced_into_new_profile_pairs():
    plan = plan_rows()
    old = [old_response(plan[0]), *[old_unrun(item) for item in plan[1:]]]
    new = [recovered(item) for item in plan[1:]]
    result = analyze_recovery(plan, old, new)
    assert result["original_512"]["response_bearing"] == 1
    assert result["recovery_2048"]["n_eligible_plan"] == 11
    assert result["recovery_2048"]["response_bearing"] == 11
    assert result["pairing"]["complete_six_condition_tasks"] == 1
    assert result["pairing"]["excluded_incomplete_tasks"] == 1
    assert len(result["paired_comparisons"]) == 4
    assert all(row["n_pairs_observed"] == 1 for row in result["paired_comparisons"])


def test_pure_503_is_retained_and_new_run_is_attempt_two_not_a_rewrite():
    plan = plan_rows(1)
    failure = {
        **old_unrun(plan[0]), "attempt": 1, "operational_status": "provider_failure",
        "provider_requests": [{"http_status": 503, "response_received": False}],
    }
    old = [failure, *[old_unrun(item) for item in plan[1:]]]
    new = [recovered(plan[0], attempt=2, prior="provider_failure")]
    result = analyze_recovery(plan, old, new)
    assert result["recovery_2048"]["eligible_from_pure_503"] == 1
    assert result["recovery_2048"]["eligible_from_not_run"] == 5
    assert result["recovery_attempts"][0]["original_http_statuses"] == [503]
    assert result["recovery_attempts"][0]["original_attempt"] == 1
    assert result["recovery_attempts"][0]["recovery_attempt"] == 2
    assert failure["operational_status"] == "provider_failure"
    with pytest.raises(ValueError, match="attempt"):
        analyze_recovery(plan, old, [recovered(plan[0], attempt=1, prior="provider_failure")])


def test_unknown_endpoint_excludes_task_from_pairs_without_losing_planned_denominator():
    plan = plan_rows(1)
    old = [old_unrun(item) for item in plan]
    new = [recovered(item) for item in plan]
    new[0].update(operational_status="parse_failure", unsafe_effect=None, task_completion=None)
    result = analyze_recovery(plan, old, new)
    assert result["pairing"]["complete_six_condition_tasks"] == 0
    assert result["paired_comparisons"] == []
    assert result["recovery_2048"]["analysis"]["paired_comparisons"] == []
    nd = next(group for group in result["recovery_2048"]["analysis"]["groups"] if group["condition_id"] == "no_defense")
    endpoint = nd["endpoints"]["unsafe_effect"]
    assert (endpoint["x"], endpoint["n_observed"], endpoint["n_plan"]) == (0, 0, 1)
    assert endpoint["rate_observed"] is None
    assert (endpoint["planned_lower_bound"], endpoint["planned_upper_bound"]) == (0, 1)
    assert nd["operational_failure"] == 1


@pytest.mark.parametrize("field,value", [
    ("generation_profile_id", "legacy"), ("max_tokens", 512),
    ("reasoning_effort", "high"), ("prior_operational_status", "provider_failure"),
    ("recovery_batch_id", ""), ("model_id", "different-model"),
    ("underlying_task_id", "different-task"),
])
def test_recovery_rejects_profile_and_identity_drift(field, value):
    plan = plan_rows(1)
    old = [old_unrun(item) for item in plan]
    row = {**recovered(plan[0]), field: value}
    with pytest.raises(ValueError, match=field):
        analyze_recovery(plan, old, [row])


@pytest.mark.parametrize("mutation", ["duplicate_old", "missing_old", "foreign_old", "wrong_old_model"])
def test_original_row_set_must_match_the_original_gemini_plan(mutation):
    plan = plan_rows(1)
    old = [old_unrun(item) for item in plan]
    if mutation == "duplicate_old":
        old.append(old[0])
    elif mutation == "missing_old":
        old.pop()
    elif mutation == "foreign_old":
        old[-1] = {**old[-1], "work_key": "foreign"}
    else:
        old[-1] = {**old[-1], "model_id": "wrong"}
    with pytest.raises(ValueError):
        analyze_recovery(plan, old, [])


def diagnostic_rows():
    return [
        {
            "diagnostic_id": f"{action}:{repetition}", "action_kind": action,
            "repetition": repetition, "generation_profile_id": "gemini_recovery_v1",
            "max_tokens": 2048, "reasoning_effort": "low", "passed": True,
            "failure_class": None,
            "provider_requests": [{"http_status": 200, "response_received": True}],
        }
        for action in ("read_file", "write_file", "final") for repetition in (1, 2)
    ]


def test_diagnostics_are_separate_from_task_denominators_and_require_all_six():
    plan = plan_rows(1)
    old = [old_unrun(item) for item in plan]
    diagnostics = diagnostic_rows()
    result = analyze_recovery(plan, old, [], diagnostics)
    assert result["diagnostics"]["all_six_passed"] is True
    assert result["diagnostics"]["provider_calls"] == 6
    assert result["recovery_2048"]["response_bearing"] == 0
    assert result["recovery_2048"]["n_eligible_plan"] == 6
    assert result["recovery_2048"]["analysis"]["models"][0]["burden_all_attempts"]["provider_calls"] == 0
    assert analyze_recovery(plan, old, [], diagnostics[:5])["diagnostics"]["all_six_passed"] is False
    diagnostics[-1]["passed"] = False
    diagnostics[-1]["failure_class"] = "ServiceUnavailable"
    failed = analyze_recovery(plan, old, [], diagnostics)["diagnostics"]
    assert failed["all_six_passed"] is False
    assert failed["failure_class_counts"] == {"ServiceUnavailable": 1}


def test_writer_preserves_original_outputs_and_reads_recorded_pause_status(tmp_path):
    from experiments.paper_v2.gemini_recovery_analysis_v1 import write_analysis

    old_root = tmp_path / "correctness_repair_v1"
    new_root = old_root / "gemini_recovery_v1"
    (old_root / "gemini_flash").mkdir(parents=True)
    new_root.mkdir()
    plan = plan_rows(1)
    old = [old_response(plan[0]), *[old_unrun(item) for item in plan[1:]]]
    for path, rows in ((old_root / "plan.jsonl", plan), (old_root / "gemini_flash/raw_records.jsonl", old), (new_root / "diagnostics.jsonl", diagnostic_rows())):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    for name in ("analysis.json", "report.md"):
        (old_root / name).write_text("unchanged original", encoding="utf-8")
    (new_root / "run_status.json").write_text(json.dumps({
        "state": "paused", "stop_reason": "ServiceUnavailable", "profile": "gemini_recovery_v1",
        "planned_recovery": 5, "attempt_records": 0, "touched_work_keys": 0,
        "pending_work_keys": 5, "recorded_at": "fixture-time", "not_executed": [],
    }), encoding="utf-8")
    before = {path: path.read_bytes() for path in old_root.rglob("*") if path.is_file()}
    result = write_analysis(old_root=old_root, output=new_root, figures=False)
    assert {path: path.read_bytes() for path in before} == before
    assert result["run_status"]["state"] == "paused"
    assert result["original_512"]["response_only_analysis"]["plan_rows"] == 1
    assert (new_root / "analysis.json").exists()
    assert (new_root / "tables/recovery_endpoints.csv").exists()
    assert (new_root / "tables/original_512_response_endpoints.csv").exists()
    assert (new_root / "tables/recovery_attempts.csv").exists()
    report = (new_root / "report.md").read_text(encoding="utf-8")
    assert "ServiceUnavailable" in report and "paused" in report
    assert "512" in report and "2048" in report and "NA" in report
    assert "run_status.json" in report and "correctness_repair_v1" in report
    assert "│   └── gemini_recovery_v1/" in report
    with pytest.raises(ValueError, match="original"):
        write_analysis(old_root=old_root, output=old_root, figures=False)


def test_default_output_matches_runner_recovery_directory():
    from experiments.paper_v2.gemini_correctness_recovery_v1 import RECOVERY_OUTPUT
    from experiments.paper_v2.gemini_recovery_analysis_v1 import DEFAULT_OLD_ROOT, DEFAULT_OUTPUT

    assert DEFAULT_OUTPUT.resolve() == RECOVERY_OUTPUT.resolve()
    assert DEFAULT_OUTPUT == DEFAULT_OLD_ROOT / "gemini_recovery_v1"


@pytest.mark.parametrize("subpath", ["gemini_flash", "deepseek_pro", "tables", "gemini_flash/anything", "gemini_recovery_v1/other"])
def test_writer_cannot_use_unapproved_original_subdirectories(tmp_path, subpath):
    from experiments.paper_v2.gemini_recovery_analysis_v1 import write_analysis

    old_root = tmp_path / "correctness_repair_v1"
    with pytest.raises(ValueError, match="original"):
        write_analysis(old_root=old_root, output=old_root / subpath, figures=False)


def test_one_failed_diagnostic_leaves_all_283_recovery_items_unknown():
    from experiments.paper_v2.gemini_recovery_analysis_v1 import report_markdown

    plan = plan_rows(48)
    old = [old_response(item) for item in plan[:5]]
    for row in old[3:]:
        row.update(operational_status="parse_failure", unsafe_effect=None, task_completion=None)
    old.extend({
        **old_unrun(item), "attempt": 1, "operational_status": "provider_failure",
        "provider_requests": [{"http_status": 503, "response_received": False}],
    } for item in plan[5:8])
    old.extend(old_unrun(item) for item in plan[8:])
    diagnostic = {
        **diagnostic_rows()[0], "passed": False, "failure_class": "ProviderTransportError",
        "provider_requests": [{"http_status": 503, "response_received": False}],
    }
    result = analyze_recovery(plan, old, [], [diagnostic])
    result["run_status"] = {"state": "paused", "stop_reason": "diagnostics_not_passed"}
    assert result["original_512"]["status_counts"] == {"completed": 3, "parse_failure": 2}
    assert result["recovery_2048"]["eligible_from_pure_503"] == 3
    assert result["recovery_2048"]["eligible_from_not_run"] == 280
    assert result["recovery_2048"]["not_yet_recorded"] == 283
    assert sum(group["endpoints"]["unsafe_effect"]["n_unknown"] for group in result["recovery_2048"]["analysis"]["groups"]) == 283
    assert result["diagnostics"]["http_status_counts"] == {"503": 1}
    assert result["recovery_2048"]["http_status_counts"] == {}
    assert "尚未通过完整在线验证" in report_markdown(result, [])
