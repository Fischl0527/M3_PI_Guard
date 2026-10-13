"""固定首稿与可信编译输入的离线边界测试。"""
from __future__ import annotations

import threading
import json
from types import SimpleNamespace

import pytest

from experiments.paper_v2 import task_contract_compilation_v1 as subject
from experiments.paper_v2.correctness_provider_v1 import DevelopmentRequestClient, RequestPacer
from tests.unit.test_correctness_provider_v1 import envelope


def test_compiler_rejects_extra_evaluator_fields():
    inputs = {"trusted_user_request": "Read report", "trusted_app_context": {}, "tool_schemas": {}}
    assert len(subject.compiler_messages(inputs)) == 2
    with pytest.raises(ValueError):
        subject.compiler_messages({**inputs, "expected_graph": {}})


def test_development_summary_separates_versions_and_preserves_original_failure():
    bases = [{"base_task_id": "a", "split": "development", "benchmark": "unit"},
             {"base_task_id": "b", "split": "development", "benchmark": "unit"}]
    rows = [{"base_task_id": "a", "draft_index": 1, "compile_status": "compile_failure", "failure_class": "schema", "provider_requests": []},
            {"base_task_id": "b", "draft_index": 1, "compile_status": "compiled", "compiler_prompt_version": "v3", "provider_requests": []}]
    result = subject.development_summary(rows, bases)
    assert result["original_status_counts"] == {"compiled": 1, "compile_failure": 1}
    assert result["by_prompt_version"]["initial_unversioned"]["compile_failure"] == 1
    assert result["by_prompt_version"]["v3"]["compiled"] == 1
    assert result["formal_matrix_executions"] is None
    assert result["formal_guard_replay_decisions"] is None
    assert result["formal_results_assessed"] is False
    assert rows[0]["compile_status"] == "compile_failure"


def test_first_contract_not_selected_by_success():
    rows = [{"base_task_id": "b1", "draft_index": 1, "compile_status": "compile_failure"},
        {"base_task_id": "b1", "draft_index": 2, "compile_status": "compiled"}]
    selected = subject.first_contracts(rows)
    assert selected["b1"]["draft_index"] == 1
    assert selected["b1"]["compile_status"] == "compile_failure"
    with pytest.raises(ValueError):
        subject.first_contracts(rows + [rows[0]])


@pytest.mark.parametrize("group,max_tokens,effort", [("deepseek_pro",512,None), ("deepseek_flash",512,None), ("gemini_flash",2048,"low")])
def test_explicit_study_callcap_twelve(tmp_path, group, max_tokens, effort):
    models = {"deepseek_pro":"deepseek-v4-pro", "deepseek_flash":"deepseek-flash", "gemini_flash":"gemini-3.6-flash"}
    observed = []
    def transport(endpoint, headers, payload, timeout):
        observed.append(payload)
        return envelope(models[group])
    client = DevelopmentRequestClient(model_group=group, model=models[group], api_key="offline-fixture-key",
        benchmark="m3-v2", work_key="w", attempt=1, trace_path=tmp_path / "requests.jsonl",
        pacer=RequestPacer(0, threading.Event()), transport=transport, max_provider_calls=12,
        call_budget_ceiling=12, call_budget_scope=subject.STUDY_SCOPE, generation_profile="task_contract_study_v1")
    for _ in range(12):
        client.complete([{"role":"user", "content":"Return JSON."}])
    assert len(observed) == 12
    assert observed[0]["max_tokens"] == max_tokens
    assert observed[0].get("reasoning_effort") == effort
    with pytest.raises(Exception, match="cap reached"):
        client.complete([{"role":"user", "content":"Return JSON."}])


def test_compiler_4096_is_explicit_only(tmp_path):
    observed = []
    client = DevelopmentRequestClient(model_group="deepseek_pro", model="deepseek-v4-pro", api_key="offline-fixture-key",
        benchmark="m3-v2", work_key="compiler-b", attempt=1, trace_path=tmp_path / "compiler.jsonl",
        pacer=RequestPacer(0, threading.Event()), transport=lambda a,b,p,d: observed.append(p) or envelope(),
        max_provider_calls=1, call_budget_ceiling=12, call_budget_scope=subject.STUDY_SCOPE,
        generation_profile="task_contract_compiler_v1")
    client.complete([{"role":"user", "content":"Return JSON."}])
    assert observed[0]["max_tokens"] == 4096
    assert observed[0]["thinking"] == {"type":"disabled"}
    assert "tools" not in observed[0]


def test_twelve_cannot_change_historical_scope(tmp_path):
    with pytest.raises(Exception, match="ceiling"):
        DevelopmentRequestClient(model_group="deepseek_pro", model="deepseek-v4-pro", api_key="offline-fixture-key",
            benchmark="m3-v2", work_key="w", attempt=1, trace_path=tmp_path / "x.jsonl",
            pacer=RequestPacer(0, threading.Event()), max_provider_calls=12, call_budget_ceiling=12)


def test_three_drafts_preserve_invalid_first_and_resume_never_replays(tmp_path):
    from experiments.paper_v2.task_contract_synthetic_v1 import tool_schemas
    inputs = {"trusted_user_request": "Find file objects with any query.",
        "trusted_app_context": {}, "tool_schemas": tool_schemas()}
    valid = {"schema_version":"m3-task-contract-draft-1.0", "actions":[{
        "action_id":"lookup", "tool":"lookup_objects", "role":"discover",
        "constraints":{"kind":{"op":"eq","value":"file"},"query":{"op":"type","value":"string"}},
        "evidence":[{"quote":"Find file objects with any query."}]}], "prohibitions":[]}
    called = []
    class FixtureClient:
        def __init__(self, **kwargs):
            self.requests = []
            self.index = int(kwargs["work_key"].rsplit("-",1)[1])
            called.append(self.index)
        def complete(self, messages):
            return SimpleNamespace(text="not JSON" if self.index == 1 else json.dumps(valid))
    bases = [{"base_task_id":"b"}]
    rows = subject.compile_contract_drafts(bases,input_loader=lambda base:inputs,
        output=tmp_path,api_key="offline",client_factory=FixtureClient)
    assert called == [1,2,3]
    assert rows[0]["compile_status"] == "compile_failure"
    assert rows[1]["compile_status"] == "compiled"
    assert subject.first_contracts(rows)["b"]["compile_status"] == "compile_failure"
    subject.compile_contract_drafts(bases,input_loader=lambda base:inputs,
        output=tmp_path,api_key="offline",client_factory=FixtureClient)
    assert called == [1,2,3]
