import copy
import json
import threading
from collections import Counter
from functools import partial

import pytest

from experiments.paper_v2.correctness_provider_v1 import DevelopmentRequestClient, RequestPacer
from experiments.paper_v2.correctness_runner_v1 import execute_one, latest_records, pending_rows
from experiments.paper_v2.correctness_runtime_v1 import CorrectnessRuntime, hydrate
from experiments.paper_v2.formal_matrix_controller_v2 import RedactedVigilConstraintFactory
from experiments.paper_v2.official_provider_executor import HTTPResponseEnvelope, ProviderPayloadError
from experiments.paper_v2.research_followup_calibration_v1 import CORE, VIGIL, build_plan, calibration_gate, select_cases, write_plan


def test_unique_underlying_attacks_and_complete_cohort():
    cases = select_cases()
    assert len(cases) == len({r["case_id"] for r in cases}) == 120
    assert Counter((r["benchmark"], r["evaluation_case_type"]) for r in cases) == {
        (b, t): 30 for b in ("agentdojo-v1", "m3-v2") for t in ("attack", "benign_tool")
    }
    rows = build_plan()
    assert len(rows) == len({r["work_key"] for r in rows}) == 480
    attack_tasks = {r["underlying_task_id"] for r in rows if r["evaluation_case_type"] == "attack"}
    assert len(attack_tasks) == 60
    assert Counter(r["condition_id"] for r in rows) == dict.fromkeys((*CORE, VIGIL), 120)
    assert sum(r["formal_prefix"] and r["condition_id"] in CORE for r in rows) == 12
    assert sum(r["formal_prefix"] and r["condition_id"] == VIGIL for r in rows) == 4
    assert {r["prompt_factor"] for r in rows} == {"normal"}
    assert {r["authorization_regime"] for r in rows} == {"auto_compiled"}


def test_plan_immutable_and_no_success_replay(tmp_path):
    path = write_plan(tmp_path)
    assert write_plan(tmp_path) == path
    rows = build_plan()
    history = latest_records([{**r, "attempt": 1, "response_obtained": True, "operational_status": "completed"} for r in rows])
    assert pending_rows(rows, history) == []
    with pytest.raises(ValueError, match="no-response"):
        pending_rows(rows, history, rows[0]["work_key"])
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot overwrite"):
        write_plan(tmp_path)


@pytest.mark.parametrize("condition", (*CORE, VIGIL))
@pytest.mark.parametrize("benchmark", ("agentdojo-v1", "m3-v2"))
def test_live_wiring_with_mock_http_and_native_evaluator(tmp_path, condition, benchmark):
    path = write_plan(tmp_path)
    row = next(r for r in build_plan() if r["benchmark"] == benchmark and r["condition_id"] == condition and r["evaluation_case_type"] == "benign_tool")
    payloads = []

    def transport(endpoint, headers, payload, timeout):
        payloads.append(copy.deepcopy(payload))
        content = {"constraints": [{"constraint_id": "forbid-delete", "constraint_type": "forbid", "description": "Do not delete records.", "tool_name": "delete_record", "priority": 1}], "global_rules": []} if condition == VIGIL and len(payloads) == 1 else {"tool": "final", "arguments": {"answer": "done"}}
        return HTTPResponseEnvelope(200, {}, {"id": f"mock-{len(payloads)}", "model": payload["model"], "choices": [{"message": {"role": "assistant", "content": json.dumps(content)}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 20}})

    runtime = CorrectnessRuntime(plan_path=path, execution_identity=row["execution_identity"], compiler_revision="corrected_v2", runtime_revision="corrected_v2", vigil_factory=RedactedVigilConstraintFactory())
    factory = partial(DevelopmentRequestClient, transport=transport, max_provider_calls=row["max_provider_calls"], call_budget_ceiling=row["max_provider_calls"])
    result = execute_one(row, 1, runtime=runtime, api_key="offline-fixture", pacer=RequestPacer(0, threading.Event()), output=tmp_path, client_factory=factory)
    assert result["operational_status"] == "completed"
    assert result["unsafe_effect_observed"] is True
    assert result["provider_call_count"] == (2 if condition == VIGIL else 1)
    assert result["online_forbidden_fields_present"] is False
    assert result["real_external_effects"] == 0
    assert not result["provider_tools_enabled"]
    assert all(p["max_tokens"] == 512 and "tools" not in p for p in payloads)
    if condition == VIGIL:
        assert result["vigil_constraint_generation_calls"] == 1


def test_guard_disabled_does_not_change_online_inputs():
    rows = [r for r in build_plan() if r["case_id"] == build_plan()[0]["case_id"] and r["condition_id"] in CORE]
    states = [hydrate(r, compiler_revision="corrected_v2")[0] for r in rows]
    assert all(s["agent_input"] == states[0]["agent_input"] for s in states)
    assert states[0]["runtime_control"]["guard_mode"] == "disabled"


def test_call_ceiling_explicit_and_no_other_provider_expansion(tmp_path):
    args = dict(model_group="deepseek_pro", model="deepseek-v4-pro", api_key="offline-fixture", benchmark="m3-v2", work_key="fixture", attempt=1, trace_path=tmp_path / "trace.jsonl", pacer=RequestPacer(0, threading.Event()))
    with pytest.raises(ProviderPayloadError, match="cap"):
        DevelopmentRequestClient(**args, max_provider_calls=16)
    client = DevelopmentRequestClient(**args, max_provider_calls=16, call_budget_ceiling=16)
    assert client.max_provider_calls == 16
    with pytest.raises(ProviderPayloadError, match="ceiling"):
        DevelopmentRequestClient(**{**args, "model_group": "deepseek_flash", "model": "deepseek-flash"}, max_provider_calls=16, call_budget_ceiling=16)


def test_gate_ignores_outcomes_but_checks_baseline_identity():
    rows = [{**r, "operational_status": "completed", "online_forbidden_fields_present": [], "events": [{"parse_ok": True}], "provider_requests": [{"response_received": True, "local_request_id": "id", "payload_sha256": "digest", "provider_response_id": "official", "returned_model": r["model_id"]}], "unsafe_effect": False} for r in build_plan() if r["formal_prefix"]]
    assert calibration_gate(rows)["passed"]
    for r in rows:
        r["unsafe_effect"] = True
    assert calibration_gate(rows)["passed"]
    next(r for r in rows if r["condition_id"] == VIGIL)["provider_requests"][0]["returned_model"] = "wrong-model"
    assert not calibration_gate(rows)["passed"]
