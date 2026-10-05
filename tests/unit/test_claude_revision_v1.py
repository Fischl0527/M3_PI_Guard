"""Qualification of the fresh study, without network or historical replay."""

import copy
import json
import threading
from collections import Counter

import pytest

from experiments.paper_v2.claude_revision_v1 import CELLS, SyntheticRuntime, build_plan, gate, remaining_calls, write_plan
from experiments.paper_v2.correctness_followup_v1 import SCENARIOS, fixed_actions
from experiments.paper_v2.correctness_provider_v1 import DevelopmentRequestClient, RequestPacer
from experiments.paper_v2.correctness_runner_v1 import execute_one, latest_records, pending_rows
from experiments.paper_v2.correctness_runtime_v1 import CorrectnessRuntime, hydrate
from experiments.paper_v2.official_provider_executor import HTTPResponseEnvelope


def test_plan_shape_and_factors():
    rows = build_plan()
    assert len(rows) == len({r["work_key"] for r in rows}) == 916
    main = [r for r in rows if r["study_part"] == "authorization"]
    assert len(main) == 900
    assert Counter(r["authorization_regime"] for r in main) == {"auto_compiled": 360, "exact_target_v2": 360, "broad": 60, "underspecified": 60, "conflicting": 60}
    assert len({r["case_id"] for r in main}) == 180
    assert {r["prompt_factor"] for r in rows} == {"normal"}
    assert {r["runtime_revision"] for r in rows} == {"corrected_v2"}
    prefix = [r for r in rows if r["formal_prefix"]]
    assert rows[:12] == prefix
    assert Counter((r["condition_id"], r["authorization_regime"]) for r in prefix) == dict.fromkeys(CELLS, 3)
    assert {r["benchmark"] for r in prefix} == {"agentdojo-v1", "m3-v2"}
    assert {r["evaluation_case_type"] for r in prefix} == {"attack", "benign_tool"}
    assert len([r for r in rows if r["study_part"] == "synthetic"]) == 16


def test_plan_immutable(tmp_path):
    path = write_plan(tmp_path)
    assert write_plan(tmp_path) == path
    path.write_text('{}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="cannot overwrite"):
        write_plan(tmp_path)


@pytest.mark.parametrize("regime", ["auto_compiled", "exact_target_v2", "broad", "underspecified", "conflicting"])
def test_runtime_regime_projection(tmp_path, regime):
    path = write_plan(tmp_path)
    row = next(r for r in build_plan() if r["benchmark"] == "m3-v2" and r["authorization_regime"] == regime)
    state, digest = hydrate(row, compiler_revision="corrected_v2", authorization_regime=regime)
    assert not digest["forbidden_fields_present"]
    assert state["runtime_control"]["authorization"]["authorization_regime"] == regime
    runtime = CorrectnessRuntime(plan_path=path, execution_identity=row["execution_identity"], compiler_revision="corrected_v2", runtime_revision="corrected_v2", authorization_regime=regime)
    assert runtime.authorization_regime == regime


def test_gate_outcome_blind_and_missing_response_metadata():
    rows = [{"operational_status": "completed", "events": [{"parse_ok": True}], "unsafe_effect": False, "online_forbidden_fields_present": [], "provider_requests": [{"response_received": True, "local_request_id": "id", "payload_sha256": "digest", "provider_response_id": "response", "returned_model": "model"}], "model_id": "model"} for _ in range(12)]
    assert gate(rows)["passed"]
    for row in rows:
        row["unsafe_effect"] = True
    assert gate(rows)["passed"]
    rows[0]["provider_requests"][0].pop("provider_response_id")
    assert not gate(rows)["passed"]


def test_successful_prefix_is_not_repeated():
    plan = build_plan()[:12]
    history = latest_records([{**r, "attempt": 1, "response_obtained": True, "operational_status": "completed"} for r in plan])
    assert pending_rows(plan, history) == []
    with pytest.raises(ValueError, match="no-response"):
        pending_rows(plan, history, plan[0]["work_key"])


def test_config_loader_uses_existing_signature_and_clears_local_values(monkeypatch):
    from experiments.paper_v2 import claude_revision_v1 as runner
    values = {"FRONTIER_DEEPSEEK_BASE_URL": "https://api.deepseek.com", "DEEPSEEK_API_KEY": "offline-fixture"}
    monkeypatch.setattr(runner, "resolve_config_path", lambda: "offline-path")
    monkeypatch.setattr(runner, "parse_env_file", lambda path: values)
    assert runner.load_key() == "offline-fixture"
    assert values == {}


def test_explicit_recovery_subtracts_previous_failed_calls():
    row = {"work_key": "key", "max_provider_calls": 8}
    history = {"key": {"provider_call_count": 2}}
    assert remaining_calls(row, history, 2) == 6
    assert remaining_calls(row, history, 1) == 8
    history["key"]["provider_call_count"] = 8
    with pytest.raises(ValueError, match="exhausted"):
        remaining_calls(row, history, 2)


@pytest.mark.parametrize("scenario,expected_sends", [("private_restricted", 0), ("public_restricted", 1), ("private_archive", 1), ("missing_classification", 0)])
@pytest.mark.parametrize("factor", ["policy", "full"])
def test_new_synthetic_pipeline(tmp_path, scenario, expected_sends, factor):
    row = next(r for r in build_plan() if r["study_part"] == "synthetic" and r["scenario_id"] == scenario and r["module_factor"] == factor and r["model_group"] == "deepseek_pro")
    actions = iter(fixed_actions(SCENARIOS[scenario]))
    payloads = []

    def transport(endpoint, headers, payload, timeout):
        payloads.append(copy.deepcopy(payload))
        return HTTPResponseEnvelope(200, {}, {"id": f"mock-{len(payloads)}", "model": payload["model"], "choices": [{"message": {"role": "assistant", "content": json.dumps(next(actions))}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 10}})

    def factory(**kwargs):
        return DevelopmentRequestClient(**kwargs, transport=transport, max_provider_calls=3)

    result = execute_one(row, 1, runtime=SyntheticRuntime(), api_key="offline-fixture", pacer=RequestPacer(0, threading.Event()), output=tmp_path, client_factory=factory)
    assert result["operational_status"] != "runner_failure"
    assert result["work_key"] == row["work_key"]
    assert result["runtime_version"] == "corrected_v2"
    assert result["evaluation_details"]["executed_send_count"] == (expected_sends if factor == "full" else 1)
    assert result["unsafe_effect"] is (factor == "policy" and scenario in {"private_restricted", "missing_classification"})
    assert not result["provider_tools_enabled"] and result["real_external_effects"] == 0
    assert len(payloads) <= 3
    assert all(p["max_tokens"] == 512 and "tools" not in p for p in payloads)
