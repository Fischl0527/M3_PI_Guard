"""v4限定开发运行器的离线准入、恢复及参数记录测试，不调用真实API。"""
from __future__ import annotations

import copy
import json
from collections import Counter
from types import SimpleNamespace

import pytest

from experiments.paper_v2 import task_contract_v4_development_v1 as subject


COMMIT = "a" * 40


@pytest.fixture
def cohorts():
    cases = subject.read_jsonl(subject.V3_OUTPUT / "assets/compiler_development_cases_v1.jsonl")
    previous = subject.read_jsonl(subject.V3_OUTPUT / "compilation/raw_records_v1.jsonl")
    return subject.select_development_cases(cases, previous)


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def request(success=True, *, count=1):
    return [{"response_received": success, "http_status": 200 if success else 503,
        "local_request_id": f"local-{index}", "payload_sha256": "same-first-payload",
        "provider_response_id": f"official-{index}" if success else None,
        "returned_model": subject.MODELS["pro"] if success else None,
        "usage": {"prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 100,
            "completion_tokens": 10, "prompt_tokens": 100, "total_tokens": 110}} for index in range(count)]


def record(item, *, status="completed", attempt=1, calls=None):
    requests = request() if calls is None else calls
    requests = copy.deepcopy(requests)
    for receipt in requests:
        if receipt.get("returned_model"):
            receipt["returned_model"] = item["model_id"]
    return {**item, "attempt": attempt, "status": "terminal", "operational_status": status,
        "provider_requests": requests, "response_obtained": any(row["response_received"] for row in requests),
        "events": [{"parse_ok": True}] if any(row["response_received"] for row in requests) else [],
        "online_forbidden_fields_present": [], "evaluator_fields_online": 0,
        "provider_tools_enabled": False, "real_external_effects": 0, "unsafe_effect": False,
        "task_completion": True, "implementation_commit": COMMIT,
        "compiler_prompt_versions": copy.deepcopy(subject.PROMPT_VERSIONS),
        "compiler_prompt_version": subject.PROMPT_VERSIONS.get(item["compiler_version"])}


def compiler_rows(cohorts, cohort="debug"):
    return [{"base_task_id": row["base_task_id"], "compiler_version": version, "compile_stage": "initial",
        "attempt": 1, "compiler_status": "ready", "compile_status": "compiled", "response_obtained": False,
        "provider_requests": [], "development_cohort": cohort, "compiler_input_sha256": "input",
        "draft": {}, "intent": {}, "contract": {}, "implementation_commit": COMMIT,
        "compiler_prompt_version": subject.PROMPT_VERSIONS[version],
        "compiler_prompt_versions": copy.deepcopy(subject.PROMPT_VERSIONS)}
        for row in cohorts[cohort] for version in ("v3", "v4")]


def setup_study(tmp_path, cohorts, *, both=False):
    for cohort, rows in cohorts.items():
        write_rows(tmp_path / "assets" / f"cases_{cohort}_v1.jsonl", rows)
    plans = {provider: subject.build_execution_plan(cohorts, provider) for provider in subject.MODELS}
    for provider, plan in plans.items():
        write_rows(tmp_path / "plans" / provider / "execution_plan_v1.jsonl", plan)
    write_rows(tmp_path / "compilation/raw_records_v1.jsonl", compiler_rows(cohorts) +
        (compiler_rows(cohorts, "qualification") if both else []))
    return plans


def test_actual_selection_32_unseen_balanced_and_deterministic(cohorts):
    selected = [row for values in cohorts.values() for row in values]
    prior = subject.read_jsonl(subject.V3_OUTPUT / "compilation/raw_records_v1.jsonl")
    assert len(selected) == len({row["base_task_id"] for row in selected}) == 32
    assert not {row["base_task_id"] for row in selected} & {row["base_task_id"] for row in prior}
    for rows in cohorts.values():
        assert len(rows) == 16
        assert Counter(row["benchmark"] for row in rows) == {"m3-v2": 8, "task-contract-synthetic-v1": 8}
        synthetic = [row for row in rows if row["benchmark"] == "task-contract-synthetic-v1"]
        assert len({row["family"] for row in synthetic}) == 8
        assert Counter(row["language"] for row in synthetic) == {"zh": 4, "en": 4}
    cases = subject.read_jsonl(subject.V3_OUTPUT / "assets/compiler_development_cases_v1.jsonl")
    assert subject.select_development_cases(list(reversed(cases)), list(reversed(prior))) == cohorts


def test_two_model_plan_has640_unique_keys_and20_prefix_each(cohorts):
    plans = [subject.build_execution_plan(cohorts, provider) for provider in subject.MODELS]
    rows = sum(plans, [])
    assert len(rows) == len({row["work_key"] for row in rows}) == 640
    for plan in plans:
        assert Counter(row["development_cohort"] for row in plan) == {"debug": 160, "qualification": 160}
        prefix = [row for row in plan if row["formal_prefix"]]
        assert len(prefix) == 20
        assert len({row["base_task_id"] for row in prefix}) == 2
        assert Counter(row["benchmark"] for row in prefix) == {"m3-v2": 10, "task-contract-synthetic-v1": 10}
        assert all(row["max_provider_calls"] == 12 and row["max_tokens"] == 512 and not row["automatic_retries"] for row in plan)
    with pytest.raises(ValueError):
        subject.build_execution_plan(cohorts, "gemini")


def test_semantic_state_not_repairable_and_no_orphan_or_second_repair():
    initial = {"base_task_id": "b", "compiler_version": "v4", "compile_stage": "initial", "attempt": 1,
        "response_obtained": False, "provider_requests": [], "compiler_status": "technical_invalid",
        "diagnostics": [{"code": "json_parse_error", "repairable": True}]}
    assert subject.repairable(initial)
    assert not subject.repairable({**initial, "diagnostics": [{"code": "scope_conflict", "repairable": True}]})
    assert not subject.repairable({**initial, "compiler_status": "needs_clarification"})
    repaired = {**initial, "compile_stage": "repair_1", "compiler_status": "ready"}
    assert subject.fixed_compilations([initial, repaired])["v4"]["b"]["compile_stage"] == "repair_1"
    with pytest.raises(ValueError, match="orphan"):
        subject.fixed_compilations([repaired])
    with pytest.raises(ValueError, match="stage/version"):
        subject.fixed_compilations([initial, {**repaired, "compile_stage": "repair_2"}])
    with pytest.raises(ValueError, match="ready/semantic"):
        subject.fixed_compilations([{**initial, "compiler_status": "ready"}, repaired])


def test_compiler_no_response_recovery_cannot_repeat_response():
    first = {"base_task_id": "b", "compiler_version": "v4", "compile_stage": "initial", "attempt": 1,
        "response_obtained": True, "provider_requests": request(), "compiler_status": "technical_invalid"}
    with pytest.raises(ValueError, match="response-bearing"):
        subject._compiler_history([first, {**first, "attempt": 2}])
    with pytest.raises(ValueError, match="disagreement"):
        subject._compiler_history([{**first, "response_obtained": False}])


def test_runtime_receipts_prevent_retry_and_identity_drift(cohorts):
    plan = subject.build_execution_plan(cohorts, "pro")
    first = record(plan[0])
    with pytest.raises(ValueError, match="pure no-response"):
        subject.runtime_history(plan, [first, {**first, "attempt": 2}])
    with pytest.raises(ValueError, match="identity drift"):
        subject.runtime_history(plan, [{**first, "model_id": "other"}])
    with pytest.raises(ValueError, match="receipt/status"):
        subject.runtime_history(plan, [{**first, "response_obtained": False}])
    failed = record(plan[0], status="provider_failure", calls=request(False))
    assert subject.runtime_history(plan, [failed, {**first, "attempt": 2}])[plan[0]["work_key"]]["attempt"] == 2
    with pytest.raises(ValueError, match="pure no-response"):
        subject.runtime_history(plan, [{**failed, "operational_status": "parse_failure"}, {**first, "attempt": 2}])


def test_prefix_excludes_compiler_unavailable_but_not_provider_failure(cohorts):
    prefix = [row for row in subject.build_execution_plan(cohorts, "pro") if row["formal_prefix"]]
    rows = [record(row) for row in prefix]
    for row in rows[:10]:
        row.update(operational_status="compile_failure", provider_requests=[], response_obtained=False, events=[])
    gate = subject.technical_prefix(rows)
    assert gate["passed"] and gate["callable_rows"] == 10 and gate["compiler_unavailable_rows"] == 10
    for row in rows[10:13]:
        row.update(operational_status="provider_failure", provider_requests=request(False), response_obtained=False, events=[])
    assert "callable_parsed_below80percent" in subject.technical_prefix(rows)["reasons"]
    unsafe = copy.deepcopy(rows)
    for row in unsafe:
        row["unsafe_effect"] = not row["unsafe_effect"]
        row["task_completion"] = not row["task_completion"]
    assert subject.technical_prefix(unsafe) == subject.technical_prefix(rows)


def test_compile_has4096_version_records_once_and_only_one_repair(tmp_path, cohorts, monkeypatch):
    setup_study(tmp_path, cohorts)
    # 删除测试夹具编译表仅发生在pytest临时目录，不涉及用户原始记录。
    (tmp_path / "compilation/raw_records_v1.jsonl").unlink()
    monkeypatch.setattr(subject, "implementation_commit", lambda: COMMIT)
    observed = []
    class Client:
        def __init__(self, **kwargs):
            observed.append(kwargs)
            self.requests = []
        def complete(self, messages):
            self.requests = request()
            return SimpleNamespace(text="not JSON")
    inputs = {"trusted_user_request": "Read a file.", "trusted_app_context": {}, "tool_schemas": {}}
    subject.compile_cohort("debug", output=tmp_path, api_key="offline-fixture", input_loader=lambda row: inputs,
        client_factory=Client, limit=1)
    raw = subject.read_jsonl(tmp_path / "compilation/raw_records_v1.jsonl")
    assert [(row["compiler_version"], row["compile_stage"]) for row in raw] == [("v3", "initial"), ("v4", "initial"), ("v4", "repair_1")]
    assert all(row["max_tokens"] == 4096 and row["implementation_commit"] == COMMIT for row in raw)
    assert all(row["cost"]["pricing_checked_at"] == "2026-10-14" for row in raw)
    assert all(kwargs["max_provider_calls"] == 1 and kwargs["generation_profile"] == "task_contract_compiler_v1" for kwargs in observed)
    subject.compile_cohort("debug", output=tmp_path, api_key="offline-fixture", input_loader=lambda row: inputs,
        client_factory=Client, limit=1)
    assert len(observed) == 3


def test_qualification_requires_both_debug_closures_and_pins_commit(tmp_path, cohorts):
    plans = setup_study(tmp_path, cohorts)
    with pytest.raises(ValueError, match="160 terminal"):
        subject.qualification_guard(tmp_path, COMMIT)
    for provider, plan in plans.items():
        write_rows(tmp_path / provider / "raw_records_v1.jsonl", [record(row) for row in plan if row["development_cohort"] == "debug"])
        (tmp_path / provider / "status_v1.json").write_text(json.dumps({"stop_reason": None}), encoding="utf-8")
    subject.qualification_guard(tmp_path, COMMIT)
    comp = compiler_rows(cohorts) + compiler_rows(cohorts, "qualification")
    write_rows(tmp_path / "compilation/raw_records_v1.jsonl", comp)
    subject.qualification_guard(tmp_path, COMMIT)
    with pytest.raises(ValueError, match="independence_invalid"):
        subject.qualification_guard(tmp_path, "b" * 40)
    (tmp_path / "flash/status_v1.json").write_text(json.dumps({"stop_reason": "runtime_contract_error"}), encoding="utf-8")
    with pytest.raises(ValueError, match="without technical halt"):
        subject.qualification_guard(tmp_path, COMMIT)


def test_run_prefix_twenty_only_then_pending_and_no_repeats(tmp_path, cohorts, monkeypatch):
    setup_study(tmp_path, cohorts)
    monkeypatch.setattr(subject, "implementation_commit", lambda: COMMIT)
    called = []
    def execute(item, attempt, **kwargs):
        called.append((item["work_key"], attempt, kwargs["client_factory"].keywords))
        return record(item, attempt=attempt)
    monkeypatch.setattr(subject, "execute_one", execute)
    result = subject.run_provider("pro", "debug", output=tmp_path, api_key="offline-fixture", prefix_only=True, runtime=object())
    assert result["prefix"]["passed"] and len(called) == 20
    assert all(args["max_provider_calls"] == 12 and args["call_budget_ceiling"] == 12 for _, _, args in called)
    subject.run_provider("pro", "debug", output=tmp_path, api_key="offline-fixture", prefix_only=True, runtime=object())
    assert len(called) == 20
    subject.run_provider("pro", "debug", output=tmp_path, api_key="offline-fixture", pending_only=True, runtime=object())
    assert len(called) == len({key for key, _, _ in called}) == 160
    saved = subject.read_jsonl(tmp_path / "pro/raw_records_v1.jsonl")
    assert all(row["implementation_commit"] == COMMIT and row["max_tokens"] == 512 for row in saved)
    assert all(row["cost"]["pricing_checked_at"] == "2026-10-14" for row in saved)


def test_retry_remaining_cap_and_open_attempt_not_resubmitted(tmp_path, cohorts, monkeypatch):
    plans = setup_study(tmp_path, cohorts)
    monkeypatch.setattr(subject, "implementation_commit", lambda: COMMIT)
    item = plans["pro"][0]
    failed = record(item, status="provider_failure", calls=request(False, count=11))
    write_rows(tmp_path / "pro/raw_records_v1.jsonl", [failed])
    observed = []
    def execute(row, attempt, **kwargs):
        observed.append(kwargs["client_factory"].keywords["max_provider_calls"])
        return record(row, attempt=attempt)
    monkeypatch.setattr(subject, "execute_one", execute)
    subject.run_provider("pro", "debug", output=tmp_path, api_key="offline-fixture",
        retry_failed_work_key=item["work_key"], runtime=object())
    assert observed == [1]
    with pytest.raises(ValueError, match="one recovery"):
        subject.run_provider("pro", "debug", output=tmp_path, api_key="offline-fixture",
            retry_failed_work_key=item["work_key"], runtime=object())
    open_item = plans["flash"][0]
    trace = tmp_path / "flash/internal/deepseek_flash" / f"{open_item['work_key']}.attempt1.jsonl"
    trace.parent.mkdir(parents=True)
    trace.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="open runtime trace"):
        subject.run_provider("flash", "debug", output=tmp_path, api_key="offline-fixture", prefix_only=True, runtime=object())


def test_gemini_and_combined_retry_dispatch_forbidden(tmp_path):
    for kwargs in ({"provider": "gemini", "cohort": "debug", "prefix_only": True},
                   {"provider": "pro", "cohort": "debug", "prefix_only": True, "retry_failed_work_key": "k"}):
        with pytest.raises(ValueError, match="unsupported"):
            subject.run_provider(output=tmp_path, api_key="offline-fixture", **kwargs)


def test_unfinished_technical_repair_cannot_reach_runtime():
    rows = [{"base_task_id": "b", "compiler_version": version, "compile_stage": "initial", "attempt": 1,
        "response_obtained": False, "provider_requests": [], "compiler_status": "technical_invalid" if version == "v4" else "ready",
        "diagnostics": [{"code": "json_parse_error", "repairable": True}]} for version in ("v3", "v4")]
    with pytest.raises(ValueError, match="required technical-repair"):
        subject._require_compilation_closed(rows, {"b"})


def test_missing_response_identity_and_real_tool_flags_fail_prefix(cohorts):
    prefix = [row for row in subject.build_execution_plan(cohorts, "pro") if row["formal_prefix"]]
    rows = [record(row) for row in prefix]
    rows[0]["provider_requests"][0]["provider_response_id"] = None
    assert "missing_official_response_identity" in subject.technical_prefix(rows)["reasons"]
    rows = [record(row) for row in prefix]
    rows[0]["provider_tools_enabled"] = True
    assert "external_safety_violation" in subject.technical_prefix(rows)["reasons"]
    rows = [record(row) for row in prefix]
    rows[0]["online_forbidden_fields_present"] = ["evaluator"]
    assert "online_field_leak" in subject.technical_prefix(rows)["reasons"]


def test_429_stops_and_stays_unretryable(tmp_path, cohorts, monkeypatch):
    setup_study(tmp_path, cohorts)
    monkeypatch.setattr(subject, "implementation_commit", lambda: COMMIT)
    called = []
    def execute(item, attempt, **kwargs):
        called.append(item["work_key"])
        failures = request(False)
        failures[0]["http_status"] = 429
        return record(item, status="provider_failure", calls=failures)
    monkeypatch.setattr(subject, "execute_one", execute)
    result = subject.run_provider("pro", "debug", output=tmp_path, api_key="offline-fixture", prefix_only=True, runtime=object())
    assert result["stop_reason"] == "provider_authorization_or_availability_stop"
    assert 1 <= len(called) <= 2
    with pytest.raises(ValueError, match="prior safety/provider"):
        subject.run_provider("pro", "debug", output=tmp_path, api_key="offline-fixture", retry_failed_work_key=called[0], runtime=object())


def test_open_compile_stage_never_sends_request(tmp_path, cohorts, monkeypatch):
    setup_study(tmp_path, cohorts)
    (tmp_path / "compilation/raw_records_v1.jsonl").unlink()
    monkeypatch.setattr(subject, "implementation_commit", lambda: COMMIT)
    base = cohorts["debug"][0]
    key = subject.sha256_canonical_json({"scope": subject.SCOPE, "base_task_id": base["base_task_id"],
        "compiler_version": "v3", "compile_stage": "initial"})
    trace = tmp_path / "internal/compiler" / f"{key}.attempt1.jsonl"
    trace.parent.mkdir(parents=True)
    trace.write_text("{}\n", encoding="utf-8")
    def client(**kwargs):
        pytest.fail("open compile stage must not create another client")
    with pytest.raises(RuntimeError, match="open compiler request"):
        subject.compile_cohort("debug", output=tmp_path, api_key="offline-fixture", limit=1,
            input_loader=lambda row: {"trusted_user_request": "Read file", "trusted_app_context": {}, "tool_schemas": {}},
            client_factory=client)


def test_pricing_local_metadata_uses_current_quotes_without_cost_stopping():
    pro = subject.cost_estimate(request(), subject.MODELS["pro"])
    flash = subject.cost_estimate(request(), subject.MODELS["flash"])
    assert pro["amount"] == pytest.approx((100 * 9 + 10 * 27) / 1_000_000)
    assert flash["amount"] == pytest.approx((100 * 2 + 10 * 8) / 1_000_000)
    assert pro["pricing_checked_at"] == "2026-10-14"
    assert pro["scientific_cost_stop"] is False
    assert pro["off_peak_lower_estimate"] == pytest.approx(pro["amount"] / 2)
    with pytest.raises(ValueError, match="forbids Gemini"):
        subject.cost_estimate([], "gemini-3.6-flash")


def test_runtime_resolved_version_keeps_frozen_plan_identity(cohorts):
    plan = subject.build_execution_plan(cohorts, "pro")
    item = next(row for row in plan if row["condition_id"] == "v4_full")
    runtime_result = {**record(item), "compiler_version": "corrected_v4"}
    saved = subject._annotate(runtime_result, COMMIT)
    assert saved["compiler_version"] == "v4" and saved["runtime_compiler_version"] == "corrected_v4"
    assert saved["compiler_prompt_version"] == subject.PROMPT_VERSIONS["v4"]
    assert subject.runtime_history(plan, [saved])[item["work_key"]] == saved


def test_runtime_separate_revision_keeps_prompt_and_plan_identity(cohorts):
    plan = subject.build_execution_plan(cohorts, "pro")
    item = next(row for row in plan if row["condition_id"] == "v4_full")
    saved = subject._annotate({**record(item), "compiler_revision": "corrected_v4"}, COMMIT)
    assert saved["compiler_version"] == "v4"
    assert saved["runtime_compiler_version"] == "corrected_v4"
    assert saved["compiler_prompt_version"] == subject.PROMPT_VERSIONS["v4"]
    assert subject.runtime_history(plan, [saved])[item["work_key"]] == saved


def test_failed_provider_seals_missing_scope_and_does_not_block_other_qualified_model(tmp_path, cohorts, monkeypatch):
    plans = setup_study(tmp_path, cohorts)
    pro = [record(row) for row in plans["pro"] if row["development_cohort"] == "debug"]
    write_rows(tmp_path / "pro/raw_records_v1.jsonl", pro)
    (tmp_path / "pro/status_v1.json").write_text(json.dumps({"stop_reason": None}), encoding="utf-8")
    flash = [record(row) for row in plans["flash"] if row["formal_prefix"]]
    for row in flash[:5]:
        row.update(operational_status="parse_failure", events=[{"parse_ok": False}])
    write_rows(tmp_path / "flash/raw_records_v1.jsonl", flash)
    value = subject.seal_failed_provider("flash", output=tmp_path)
    assert value["not_run"] == 300 and value["recorded"] == 20 and not value["prefix"]["passed"]
    subject.qualification_guard(tmp_path, COMMIT)
    monkeypatch.setattr(subject, "implementation_commit", lambda: COMMIT)
    with pytest.raises(ValueError, match="branch sealed"):
        subject.run_provider("flash", "debug", output=tmp_path, api_key="offline-fixture", pending_only=True, runtime=object())
    assert len(subject.read_jsonl(tmp_path / "flash/raw_records_v1.jsonl")) == 20


def test_successful_prefix_cannot_be_sealed_to_skip_records(tmp_path, cohorts):
    plans = setup_study(tmp_path, cohorts)
    write_rows(tmp_path / "flash/raw_records_v1.jsonl", [record(row) for row in plans["flash"] if row["formal_prefix"]])
    with pytest.raises(ValueError, match="failed prefix"):
        subject.seal_failed_provider("flash", output=tmp_path)
