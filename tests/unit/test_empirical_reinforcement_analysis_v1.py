"""强化实验的统计公开接口：未知、计划分母及配对结构不被悄悄改写。"""

import json
from xml.etree import ElementTree

import pytest

from experiments.paper_v2.empirical_reinforcement_analysis_v1 import (
    analyze, endpoint_summary, paired_contrast, write_outputs,
)


def test_unknown_and_unstarted_items_remain_in_itt_denominator():
    result = endpoint_summary(
        [{"task_completion": True}, {"task_completion": False},
         {"task_completion": None}], "task_completion", planned=4,
    )
    assert result["numerator"] == 1
    assert result["observed_denominator"] == 2
    assert result["planned_denominator"] == 4
    assert result["unknown"] == 2
    assert result["observed_rate"] == .5
    assert result["itt_lower"] == .25
    assert result["itt_upper"] == .75


def _paired_rows(pairs):
    return [
        {"underlying_task_id": str(index), "condition_id": condition,
         "authorization_regime": "auto_compiled", "suite": "test",
         "benchmark": "agentdojo-v1", "unsafe_effect": value}
        for index, pair in enumerate(pairs)
        for condition, value in zip(("no_defense", "m3_policy_only"), pair)
    ]


def test_pairing_uses_underlying_tasks_and_unknown_bounds():
    result = paired_contrast(
        _paired_rows([(False, True), (True, None), (False, False)]),
        "unsafe_effect", ("no_defense", "auto_compiled"),
        ("m3_policy_only", "auto_compiled"), bootstrap_draws=100,
    )
    assert result["planned_pairs"] == 3
    assert result["known_pairs"] == 2
    assert result["unknown_pairs"] == 1
    assert result["estimate"] == .5
    assert result["itt_difference_lower"] == 0
    assert result["itt_difference_upper"] == pytest.approx(1 / 3)
    assert result["bootstrap"]["clusters"] == 2


def _study_files(root, study, model, *, missing=False, tasks=3):
    folder = root / study / model
    folder.mkdir(parents=True)
    utility_cells = [("no_defense", "auto_compiled"),
                     ("m3_policy_only", "auto_compiled"),
                     ("m3_full_normal_prompt", "auto_compiled"),
                     ("m3_policy_only", "exact_target_v2"),
                     ("m3_full_normal_prompt", "exact_target_v2")]
    cells = utility_cells if study == "utility" else utility_cells[:3] + [
        ("strongest_peer_reviewed_structural_baseline", "auto_compiled")]
    plan, raw = [], []
    for benchmark in ("agentdojo-v1", "m3-v2"):
        for task in range(tasks):
            for condition, regime in cells:
                key = f"{study}-{model}-{benchmark}-{task}-{condition}-{regime}"
                row = {"work_key": key, "case_id": f"case-{task}",
                       "underlying_task_id": f"{benchmark}-{task}",
                       "benchmark": benchmark, "study": study,
                       "model_id": "deepseek-v4-pro" if model == "pro" else "deepseek-flash",
                       "condition_id": condition, "authorization_regime": regime,
                       "requires_confirmation": task == 2 and benchmark == "m3-v2",
                       "authorization_profile": "ambiguous_recipient" if task == 2 else "auto_compiled_exact",
                       "selection_stratum": {"suite": "banking"},
                       "max_provider_calls": 16 if "baseline" in condition else 8}
                plan.append(row)
                if missing and task == 2 and condition == "no_defense":
                    continue
                request = {"local_request_id": key, "payload_sha256": "payload",
                           "provider_response_id": f"official-{key}",
                           "returned_model": row["model_id"], "response_received": True}
                raw.append({**row, "attempt": 1, "operational_status": "completed",
                            "task_completion": task == 0 or regime == "exact_target_v2",
                            "unsafe_effect": study == "activity" and task == 0 and condition == "no_defense",
                            "provider_requests": [request], "provider_call_count": 1,
                            "response_obtained": True, "token_usage": {"total": 9},
                            "cost": {"amount": .001, "usage_complete": True},
                            "ask_count": int(task == 2), "deny_count": 0,
                            "provider_tools_enabled": False, "real_external_effects": 0,
                            "online_forbidden_fields_present": False})
    for name, rows in (("plan_v1.jsonl", plan), ("raw_records_v1.jsonl", raw)):
        (folder / name).write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return plan, raw


def test_analysis_keeps_primary_families_and_missing_separate(tmp_path):
    for study in ("utility", "activity"):
        for model in ("pro", "flash"):
            _study_files(tmp_path, study, model, missing=True)
    result = analyze(tmp_path, bootstrap_draws=100)
    primary = [row for row in result["comparisons"] if row["analysis_role"] == "primary"]
    utility = [row for row in primary if row["study"] == "utility"]
    activity = [row for row in primary if row["study"] == "activity"]
    assert len(utility) == 4
    assert len(activity) == 6
    assert all(row["model"] == "pro" for row in primary)
    assert all(row["family_size"] == (4 if row["study"] == "utility" else 6) for row in primary)
    assert all(row["holm_p"] is None for row in result["comparisons"] if row["model"] == "flash")
    assert result["planned"] == 108
    assert result["recorded"] == 100
    assert result["not_run"] == 8
    assert result["known_failures"] == 0
    m3 = [row for row in result["cells"] if row["study"] == "utility"
          and row["benchmark"] == "m3-v2" and row["model"] == "pro"]
    assert {row["cohort_scope"] for row in m3} >= {
        "all", "non_confirmation", "confirmation_required"}


def test_zero_event_pairing_has_nonzero_uncertainty():
    result = paired_contrast(
        _paired_rows([(False, False)] * 30), "unsafe_effect",
        ("no_defense", "auto_compiled"), ("m3_policy_only", "auto_compiled"),
        bootstrap_draws=100,
    )
    assert result["estimate"] == 0
    assert result["bootstrap"]["degenerate"] is True
    assert result["bootstrap"]["ci_low"] is None
    assert result["bootstrap"]["ci_high"] is None
    assert result["paired_interval"]["ci_low"] < 0 < result["paired_interval"]["ci_high"]
    assert endpoint_summary([{"unsafe_effect": False}] * 30, "unsafe_effect", planned=30)["wilson_95"][1] > 0


def test_write_outputs_is_self_contained_and_does_not_change_raw(tmp_path):
    _study_files(tmp_path, "utility", "pro")
    raw_path = tmp_path / "utility/pro/raw_records_v1.jsonl"
    original = raw_path.read_bytes()
    result = analyze(tmp_path, bootstrap_draws=100)
    write_outputs(result, tmp_path, figures=False)
    assert raw_path.read_bytes() == original
    assert json.loads((tmp_path / "analysis_v1.json").read_text(encoding="utf-8"))["recorded"] == 30
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "raw_records_v1.jsonl" in report
    assert "non_confirmation" in report
    assert "未知" in report and "合理等待" in report
    assert "未启用模型二次验证" in report
    assert (tmp_path / "tables/cells_v1.csv").exists()
    assert (tmp_path / "tables/paired_comparisons_v1.csv").exists()


def test_mechanism_decisions_remain_separate_from_model_outcomes(tmp_path):
    plan, _ = _study_files(tmp_path, "utility", "pro")
    folder = tmp_path / "mechanism"
    folder.mkdir()
    controlled = [
        {"base_fixture_id": "fixture", "family": "source_authority",
         "context_variant": "untrusted_document", "proposal_role": role,
         "module_factor": module, "decision": decision,
         "input_byte_identical": True, "replay_input_sha256": role,
         "proposal_sha256": role, "manifest_sha256": "manifest",
         "provider_calls": 0, "external_effects": 0, "not_end_to_end": True}
        for role, module, decision in (("legal", "policy", "ALLOW"),
                                      ("legal", "full", "ALLOW"),
                                      ("unauthorized", "policy", "ALLOW"),
                                      ("unauthorized", "full", "DENY"))]
    replay = {"work_key": plan[0]["work_key"], "benchmark": plan[0]["benchmark"],
              "underlying_task_id": plan[0]["underlying_task_id"],
              "policy_decision": "ALLOW", "full_decision": "ASK",
              "decision_changed": True, "input_byte_identical": True,
              "provider_calls": 0, "external_effects": 0, "not_end_to_end": True}
    for name, rows in (("controlled_decisions_v1.jsonl", controlled),
                       ("captured_replays_v1.jsonl", [replay])):
        (folder / name).write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    result = analyze(tmp_path, bootstrap_draws=100)
    assert result["recorded"] == 30
    mechanism = result["mechanism"]
    assert mechanism["controlled_recorded"] == 4
    assert mechanism["captured_replays"] == 1
    assert mechanism["captured_changed"] == 1
    policy = next(row for row in mechanism["controlled_cells"] if row["module_factor"] == "policy")
    full = next(row for row in mechanism["controlled_cells"] if row["module_factor"] == "full")
    assert policy["unauthorized_allowed"] == 1
    assert full["unauthorized_allowed"] == 0
    assert mechanism["not_end_to_end"] is True


@pytest.mark.parametrize("fault", ["response_id", "identity_drift", "unobserved_boolean", "tools"])
def test_invalid_provider_or_endpoint_evidence_is_rejected(tmp_path, fault):
    _, raw = _study_files(tmp_path, "utility", "pro")
    if fault == "response_id":
        raw[0]["provider_requests"][0].pop("provider_response_id")
    elif fault == "identity_drift":
        raw[0]["provider_requests"][0]["returned_model"] = "another-model"
    elif fault == "unobserved_boolean":
        raw[0]["unsafe_effect_observed"] = False
    else:
        raw[0]["provider_tools_enabled"] = True
    path = tmp_path / "utility/pro/raw_records_v1.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in raw), encoding="utf-8")
    with pytest.raises(ValueError):
        analyze(tmp_path, bootstrap_draws=100)


def test_response_bearing_item_cannot_be_repeated(tmp_path):
    _, raw = _study_files(tmp_path, "utility", "pro")
    row = json.loads(json.dumps(raw[0]))
    row["attempt"] = 2
    row["provider_requests"][0]["local_request_id"] += "-repeat"
    path = tmp_path / "utility/pro/raw_records_v1.jsonl"
    path.write_text("\n".join(json.dumps(item) for item in raw + [row]), encoding="utf-8")
    with pytest.raises(ValueError, match="response-bearing"):
        analyze(tmp_path, bootstrap_draws=100)


def test_no_response_recovery_preserves_attempt_costs_but_not_duplicate_itt(tmp_path):
    _, raw = _study_files(tmp_path, "utility", "pro")
    original = raw[0]
    failed = json.loads(json.dumps(original))
    failed.update({"operational_status": "provider_failure", "response_obtained": False,
                   "unsafe_effect": None, "task_completion": None})
    failed["provider_requests"][0].update({"response_received": False,
                                          "local_request_id": "failed-request"})
    recovered = json.loads(json.dumps(original))
    recovered["attempt"] = 2
    path = tmp_path / "utility/pro/raw_records_v1.jsonl"
    path.write_text("\n".join(json.dumps(item) for item in [failed, recovered] + raw[1:]), encoding="utf-8")
    result = analyze(tmp_path, bootstrap_draws=100)
    assert result["planned"] == result["recorded"] == 30
    assert result["known_failures"] == 0
    assert result["groups"][0]["attempt_records"] == 31
    assert result["provider_calls"] == 31
    assert result["token_usage"]["total"] == 279
    cell = next(row for row in result["cells"] if row["benchmark"] == "agentdojo-v1"
                and row["condition_id"] == "no_defense" and row["cohort_scope"] == "all")
    assert cell["planned"] == cell["recorded"] == 3
    assert cell["attempt_records"] == cell["provider_calls"] == 4
    assert cell["provider_calls_per_work_item"]["observed"] == 3
    assert cell["provider_calls_per_work_item"]["maximum"] == 2
    assert cell["token_usage"]["total"] == 36
    assert cell["cost_estimate_cny"] == pytest.approx(.004)


def test_repeated_underlying_task_does_not_inflate_pairing():
    rows = _paired_rows([(False, True)])
    with pytest.raises(ValueError, match="duplicate underlying"):
        paired_contrast(rows + [dict(rows[0])], "unsafe_effect",
                        ("no_defense", "auto_compiled"), ("m3_policy_only", "auto_compiled"),
                        bootstrap_draws=100)


def test_stratified_bootstrap_is_reproducible():
    rows = _paired_rows([(False, True), (True, False), (True, True), (False, False)])
    rows[0]["suite"] = rows[1]["suite"] = "workspace"
    first = paired_contrast(rows, "unsafe_effect", ("no_defense", "auto_compiled"),
                            ("m3_policy_only", "auto_compiled"), bootstrap_draws=100)
    second = paired_contrast(rows, "unsafe_effect", ("no_defense", "auto_compiled"),
                             ("m3_policy_only", "auto_compiled"), bootstrap_draws=100)
    assert first == second
    assert first["bootstrap"]["strata"] == {"test": 3, "workspace": 1}


def test_all_unknown_pairs_have_no_p_value_and_wide_itt_bounds():
    result = paired_contrast(_paired_rows([(None, None)] * 3), "unsafe_effect",
                              ("no_defense", "auto_compiled"), ("m3_policy_only", "auto_compiled"),
                              bootstrap_draws=100)
    assert result["estimate"] is None
    assert result["p_value"] is None
    assert result["known_pairs"] == 0
    assert result["itt_difference_lower"] == -1
    assert result["itt_difference_upper"] == 1


def test_holm_corrects_one_four_comparison_family_across_benchmarks(tmp_path):
    _, raw = _study_files(tmp_path, "utility", "pro", tasks=7)
    for row in raw:
        row["task_completion"] = row["authorization_regime"] == "exact_target_v2"
    path = tmp_path / "utility/pro/raw_records_v1.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in raw), encoding="utf-8")
    result = analyze(tmp_path, bootstrap_draws=100)
    primary = [row for row in result["comparisons"] if row["analysis_role"] == "primary"]
    assert len(primary) == 4
    # 七个独立配对全部单方向不一致：精确双侧概率2 / 2**7 = 1/64。
    assert all(row["p_value"] == 1 / 64 for row in primary)
    assert all(row["holm_p"] == .0625 for row in primary)


def test_failure_unstarted_and_unknown_are_separate(tmp_path):
    _, raw = _study_files(tmp_path, "utility", "pro", missing=True)
    raw[0].update({"operational_status": "provider_failure", "response_obtained": False,
                   "unsafe_effect": None, "task_completion": None})
    raw[0]["provider_requests"][0]["response_received"] = False
    path = tmp_path / "utility/pro/raw_records_v1.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in raw), encoding="utf-8")
    result = analyze(tmp_path, bootstrap_draws=100)
    assert result["not_run"] == 2
    assert result["known_failures"] == 1
    cell = next(row for row in result["cells"] if row["benchmark"] == "agentdojo-v1"
                and row["condition_id"] == "no_defense" and row["cohort_scope"] == "all")
    assert cell["unsafe"]["unknown"] == 2
    assert cell["unsafe_or_failure"]["numerator"] == 1
    assert cell["unsafe_or_failure"]["unknown"] == 1


def test_svg_figure_keeps_zero_event_wilson_bar_and_utf8_labels(tmp_path):
    _study_files(tmp_path, "activity", "pro")
    result = analyze(tmp_path, bootstrap_draws=100)
    write_outputs(result, tmp_path)
    path = tmp_path / "figures/activity_observed_rates_v1.svg"
    document = ElementTree.parse(path)
    assert document.getroot().tag == "{http://www.w3.org/2000/svg}svg"
    text = path.read_text(encoding="utf-8")
    assert "仅权限" in text
    assert "Wilson" in text
    assert "未知/未运行" in text


def test_condition_burden_reports_calls_tokens_cost_and_missing_vigil_breakdown(tmp_path):
    _, raw = _study_files(tmp_path, "activity", "flash")
    selected = [row for row in raw if row["benchmark"] == "agentdojo-v1"
                and row["condition_id"] == "strongest_peer_reviewed_structural_baseline"]
    for index, row in enumerate(selected, 1):
        request = row["provider_requests"][0]
        row["provider_requests"] = [
            {**request, "local_request_id": f"{request['local_request_id']}-{call}"}
            for call in range(index)]
        row["provider_call_count"] = index
        row["token_usage"] = {"input": index * 10, "output": index, "total": index * 11}
        row["cost"] = {"amount": index / 100, "currency": "CNY", "usage_complete": True}
        if index > 1:
            row["vigil_constraint_generation_calls"] = 1
    selected[2].pop("cost")
    path = tmp_path / "activity/flash/raw_records_v1.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in raw), encoding="utf-8")
    result = analyze(tmp_path, bootstrap_draws=100)
    cell = next(row for row in result["cells"] if row["benchmark"] == "agentdojo-v1"
                and row["condition_id"] == "strongest_peer_reviewed_structural_baseline")
    assert cell["provider_calls"] == 6
    assert cell["provider_call_cap"] == 16
    assert cell["provider_calls_per_work_item"]["p50"] == 2
    assert cell["provider_calls_per_work_item"]["p95"] == pytest.approx(2.9)
    assert cell["token_usage"] == {"input": 60, "output": 6, "total": 66}
    assert cell["cost_estimate_cny"] == pytest.approx(.03)
    assert cell["cost_missing_count"] == 1
    assert cell["vigil_constraint_generation_calls"]["known_total"] == 2
    assert cell["vigil_constraint_generation_calls"]["missing"] == 1
    write_outputs(result, tmp_path, figures=False)
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "16" in report and "8" in report and "约束生成" in report
    table = (tmp_path / "tables/cells_v1.csv").read_text(encoding="utf-8-sig")
    assert "provider_calls_per_work_item_p95" in table
    assert "vigil_constraint_generation_calls_missing" in table


def test_burden_missing_values_do_not_become_observed_zero(tmp_path):
    _, raw = _study_files(tmp_path, "utility", "pro")
    selected = [row for row in raw if row["benchmark"] == "agentdojo-v1"
                and row["condition_id"] == "m3_policy_only" and row["authorization_regime"] == "auto_compiled"]
    selected[0]["token_usage"] = {"input": 0, "output": 0, "total": 0}
    selected[1]["token_usage"] = {}
    selected[2]["token_usage"] = None
    selected[0]["cost"] = {"amount": 0, "currency": "CNY", "usage_complete": True}
    selected[1]["cost"] = {"amount": None, "currency": "CNY", "usage_complete": False}
    selected[2]["cost"] = None
    path = tmp_path / "utility/pro/raw_records_v1.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in raw), encoding="utf-8")
    result = analyze(tmp_path, bootstrap_draws=100)
    cell = next(row for row in result["cells"] if row["benchmark"] == "agentdojo-v1"
                and row["condition_id"] == "m3_policy_only" and row["authorization_regime"] == "auto_compiled")
    assert cell["token_usage"]["total"] == 0
    assert cell["token_usage_observed_count"]["total"] == 1
    assert cell["token_usage_missing_count"]["total"] == 2
    assert cell["cost_estimate_cny"] == 0
    assert cell["cost_observed_count"] == 1
    assert cell["cost_missing_count"] == 2
    assert cell["cost_usage_incomplete_count"] == 2


def test_all_missing_cost_and_usage_remain_na_in_report(tmp_path):
    _, raw = _study_files(tmp_path, "utility", "pro")
    for row in raw:
        row["token_usage"] = None
        row["cost"] = None
    path = tmp_path / "utility/pro/raw_records_v1.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in raw), encoding="utf-8")
    result = analyze(tmp_path, bootstrap_draws=100)
    assert result["token_usage"]["total"] is None
    assert result["token_usage_missing_count"]["total"] == 30
    assert result["cost_known_estimate_cny"] is None
    assert result["cost_missing_count"] == 30
    write_outputs(result, tmp_path, figures=False)
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "估计CNY NA" in report
    assert "成本缺失30" in report


def test_model_aliases_and_declared_service_versions_are_separate(tmp_path):
    versions = {"pro": "DeepSeek-V4-Pro-0813", "flash": "DeepSeek-V4.1-Flash"}
    for model, version in versions.items():
        plan, raw = _study_files(tmp_path, "activity", model)
        for row in plan + raw:
            row["requested_model_id"] = row["model_id"]
            row["expected_returned_model_version"] = version
        folder = tmp_path / "activity" / model
        for name, rows in (("plan_v1.jsonl", plan), ("raw_records_v1.jsonl", raw)):
            (folder / name).write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    result = analyze(tmp_path, bootstrap_draws=100)
    for group in result["groups"]:
        alias = "deepseek-v4-pro" if group["model"] == "pro" else "deepseek-flash"
        assert group["requested_model_ids"] == [alias]
        assert group["official_returned_model_ids"] == [alias]
        assert group["declared_service_versions"] == [versions[group["model"]]]
    write_outputs(result, tmp_path, figures=False)
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "DeepSeek-V4-Pro-0813" in report and "DeepSeek-V4.1-Flash" in report
    assert "不是历史V4 Flash" in report
    assert "不能据此宣称模型权重锁定" in report
