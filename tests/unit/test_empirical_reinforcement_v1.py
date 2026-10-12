"""强化实验运行边界：只用合成HTTP回执，不调用厂商。"""

import threading
import copy
import json
from functools import partial

import pytest

from experiments.paper_v2.correctness_provider_v1 import DevelopmentRequestClient, RequestPacer
from experiments.paper_v2.official_provider_executor import ProviderPayloadError, HTTPResponseEnvelope


def test_flash_vigil_budget_is_explicitly_scoped_to_new_study(tmp_path):
    args = dict(model_group="deepseek_flash", model="deepseek-flash", api_key="offline-fixture",
                benchmark="m3-v2", work_key="fixture", attempt=1,
                trace_path=tmp_path / "trace.jsonl", pacer=RequestPacer(0, threading.Event()),
                max_provider_calls=16, call_budget_ceiling=16)
    with pytest.raises(ProviderPayloadError, match="ceiling"):
        DevelopmentRequestClient(**args)
    client = DevelopmentRequestClient(**args, call_budget_scope="empirical_reinforcement_v1")
    assert client.max_provider_calls == 16
    with pytest.raises(ProviderPayloadError, match="scope"):
        DevelopmentRequestClient(**args, call_budget_scope="unapproved")


def prefix_rows(study="utility"):
    rows = []
    conditions = [("no_defense", "auto_compiled"), ("m3_policy_only", "auto_compiled"),
                  ("m3_full_normal_prompt", "auto_compiled"), ("m3_policy_only", "exact_target_v2"),
                  ("m3_full_normal_prompt", "exact_target_v2")]
    if study == "activity":
        conditions = conditions[:3] + [("strongest_peer_reviewed_structural_baseline", "auto_compiled")]
    for i in range(6 if study == "utility" else 4):
        for condition, regime in conditions:
            rows.append({"work_key": f"{i}-{condition}-{regime}", "underlying_task_id": f"task-{i}",
                         "case_id": f"case-{i}", "model_id": "deepseek-v4-pro", "formal_prefix": True,
                         "condition_id": condition, "authorization_regime": regime, "operational_status": "completed",
                         "online_forbidden_fields_present": [], "provider_tools_enabled": False, "real_external_effects": 0,
                         "unsafe_effect": False, "events": [{"parse_ok": True}],
                         "safety_receipt": {"credentials_stored": False, "evidence": {
                             "external_connectors_enabled": False, "provider_managed_tools_enabled": False,
                             "effect_backend": "no_effect"}},
                         "provider_requests": [{"response_received": True, "local_request_id": f"request-{len(rows)}",
                             "payload_sha256": f"initial-{i}", "provider_response_id": f"official-{len(rows)}",
                             "returned_model": "deepseek-v4-pro"}]})
    return rows


def test_prefix_is_outcome_blind_and_requires_same_initial_payload():
    from experiments.paper_v2.empirical_reinforcement_v1 import technical_gate
    rows = prefix_rows()
    assert technical_gate(rows, study="utility")["passed"]
    changed = copy.deepcopy(rows)
    for row in changed:
        row["unsafe_effect"] = True
    assert technical_gate(changed, study="utility")["passed"]
    changed[0]["provider_requests"][0]["payload_sha256"] = "changed-initial"
    assert "initial_payload_mismatch" in technical_gate(changed, study="utility")["reasons"]


def test_activity_gate_requires_vigil_and_core_prefix_separately():
    from experiments.paper_v2.empirical_reinforcement_v1 import technical_gate
    rows = prefix_rows("activity")
    assert technical_gate(rows, study="activity")["passed"]
    for row in [r for r in rows if r["condition_id"] == "strongest_peer_reviewed_structural_baseline"][:2]:
        row["events"] = [{"parse_ok": False}]
    assert not technical_gate(rows, study="activity")["passed"]


def test_gate_does_not_count_early_parsing_before_terminal_parse_failure():
    from experiments.paper_v2.empirical_reinforcement_v1 import technical_gate
    rows = prefix_rows()
    for row in rows[:7]:
        row.update(operational_status="parse_failure", events=[{"parse_ok": True}, {"parse_ok": False}])
    assert not technical_gate(rows, study="utility")["passed"]


def _minimal_plan(tmp_path):
    rows = prefix_rows()[:2]
    for row in rows:
        row.update(model_group="deepseek_pro", max_provider_calls=8)
    path = tmp_path / "utility/pro/plan_v1.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return rows


def test_open_trace_preflight_prevents_any_concurrent_request(tmp_path, monkeypatch):
    from experiments.paper_v2 import empirical_reinforcement_v1 as subject
    rows = _minimal_plan(tmp_path)
    trace = tmp_path / "utility/pro/internal/deepseek_pro" / (rows[1]["work_key"] + ".attempt1.jsonl")
    trace.parent.mkdir(parents=True)
    trace.write_text('{"event":"work_started"}\n', encoding="utf-8")
    monkeypatch.setattr(subject, "write_plans", lambda root: None)
    calls = []
    monkeypatch.setattr(subject, "execute_one", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(subject, "load_key", lambda: pytest.fail("preflight must precede credential loading"))
    with pytest.raises(RuntimeError, match="trace"):
        subject.run("utility", "pro", canary_only=True, output_root=tmp_path)
    assert calls == []


def test_worker_setup_failure_still_persists_other_inflight_terminal(tmp_path, monkeypatch):
    from experiments.paper_v2 import empirical_reinforcement_v1 as subject
    rows = _minimal_plan(tmp_path)
    monkeypatch.setattr(subject, "write_plans", lambda root: None)
    barrier = threading.Barrier(2)

    def worker(row, attempt, **kwargs):
        barrier.wait(timeout=5)
        if row["work_key"] == rows[0]["work_key"]:
            raise ValueError("synthetic constructor failure")
        return {**row, "attempt": attempt, "response_obtained": True, "cost": {}}

    monkeypatch.setattr(subject, "execute_one", worker)
    result = subject.run("utility", "pro", canary_only=True, output_root=tmp_path,
                         runtime=object(), api_key="offline-fixture")
    records = (tmp_path / "utility/pro/raw_records_v1.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(records) == 1
    assert json.loads(records[0])["work_key"] == rows[1]["work_key"]
    assert result["stop_reason"] == "worker_setup_failure:ValueError"


def test_real_utility_runtime_keeps_oracle_out_of_first_provider_payload(tmp_path):
    from experiments.paper_v2.empirical_reinforcement_plan_v1 import write_plans
    from experiments.paper_v2.correctness_plan_v1 import read_jsonl
    from experiments.paper_v2.empirical_reinforcement_v1 import ReinforcementRuntime
    from experiments.paper_v2.correctness_runner_v1 import execute_one
    write_plans(tmp_path)
    path = tmp_path / "utility/pro/plan_v1.jsonl"
    plan = read_jsonl(path)
    runtime = ReinforcementRuntime(path, tmp_path / "utility/pro")
    for benchmark in ("agentdojo-v1", "m3-v2"):
        case = next(r["case_id"] for r in plan if r["benchmark"] == benchmark)
        selected = [r for r in plan if r["case_id"] == case]
        payloads = []

        def transport(endpoint, headers, payload, timeout):
            payloads.append(copy.deepcopy(payload))
            return HTTPResponseEnvelope(200, {}, {"id": f"fixture-{len(payloads)}", "model": payload["model"],
                "choices": [{"message": {"role": "assistant", "content": json.dumps(
                    {"tool": "final", "arguments": {"answer": "done"}})}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20,
                          "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 10}})

        factory = partial(DevelopmentRequestClient, transport=transport)
        results = [execute_one(row, 1, runtime=runtime, api_key="offline-fixture", pacer=RequestPacer(0, threading.Event()),
                               output=tmp_path / "utility/pro", client_factory=factory) for row in selected]
        assert len(payloads) == 5
        assert all(payload == payloads[0] for payload in payloads)
        assert all(r["operational_status"] != "runner_failure" for r in results)
        assert all(not r["online_forbidden_fields_present"] for r in results)
        assert all(r["safety_receipt"]["evidence"]["external_connectors_enabled"] is False for r in results)


def test_prefix_resume_never_reexecutes_response_bearing_rows(tmp_path):
    from experiments.paper_v2.empirical_reinforcement_v1 import run

    class FinalOnlyRuntime:
        def execute(self, row, client):
            client.complete([{"role": "user", "content": row["underlying_task_id"]}])
            return {"operational_status": "completed", "events": [{"parse_ok": True}],
                    "online_forbidden_fields_present": [], "unsafe_effect": False, "task_completion": False,
                    "safety_receipt": prefix_rows()[0]["safety_receipt"]}

    calls = []

    def transport(endpoint, headers, payload, timeout):
        calls.append(payload)
        return HTTPResponseEnvelope(200, {}, {"id": f"fixture-{len(calls)}", "model": payload["model"],
            "choices": [{"message": {"role": "assistant", "content": '{"tool":"final","arguments":{"answer":"done"}}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20,
                      "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 10}})

    factory = partial(DevelopmentRequestClient, transport=transport)
    first = run("utility", "flash", canary_only=True, output_root=tmp_path,
                api_key="offline-fixture", runtime=FinalOnlyRuntime(), client_factory=factory)
    assert first["recorded"] == 30 and first["gate"]["passed"]
    again = run("utility", "flash", canary_only=True, output_root=tmp_path,
                api_key="offline-fixture", runtime=FinalOnlyRuntime(), client_factory=factory)
    assert again["recorded"] == 30
    assert len(calls) == 30
