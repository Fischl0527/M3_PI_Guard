"""Offline checks of prospective runtime wiring, not model performance."""

import copy
import json
import threading
from pathlib import Path

import pytest

from experiments.paper_v2.correctness_followup_v1 import (
    CONTENT, SCENARIOS, MemoryEffectBackend, fixed_actions, manifest_for,
)
from experiments.paper_v2.correctness_provider_v1 import DevelopmentRequestClient, RequestPacer
from experiments.paper_v2.correctness_runtime_v1 import public_events
from experiments.paper_v2.exact_gold_ablation import ExactGoldAblationMonitor
from experiments.paper_v2.exact_target_ablation_v2 import (
    TOOL_ARGUMENT_ROLES, ExactTargetMonitorV2, build_exact_target_authorization_v2,
)
from experiments.paper_v2.formal_condition_executors import CONDITION_PROFILES, OnlineExecutorContext
from experiments.paper_v2.live_condition_runtime import LiveConditionRuntime
from experiments.paper_v2.medium_runtime import _exact_authorization, _m3_exact_calls, _runtime_inputs
from experiments.paper_v2.official_provider_executor import HTTPResponseEnvelope
from experiments.paper_v2.trusted_context_runtime_v2 import build_research_messages_v2
from m3_core.policy_compiler import DEFAULT_TOOL_SCHEMAS
from m3_guard.provenance_corrected_v1 import TrustedDataLabelTracker
from m3_guard.runtime_monitor import FULL_RUNTIME_MODULES, ActionProposal
from m3_guard.runtime_monitor_corrected_v2 import RuntimeMonitorCorrectedV2


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def selected_records():
    selection = ROOT / "protocols/paper_upgrade_v2/lean_empirical_case_selection_v1.jsonl"
    cache = {}
    pairs = []
    for line in selection.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        reference = row["source_reference"]
        path = ROOT / reference["path"]
        if path not in cache:
            cache[path] = path.read_text(encoding="utf-8").splitlines()
        record = json.loads(cache[path][reference["line"] - 1])
        pairs.append((row, record))
    return pairs


def test_thirty_fixed_m3_cases_complete_interface_permission_only(selected_records):
    """The same targets and typed placeholder content; not an end-to-end TCR."""
    selected = [(row, record) for row, record in selected_records
                if row["benchmark"] == "m3-v2" and row["evaluation_case_type"] == "benign_tool"]
    assert len(selected) == 30
    allowed = {"legacy": 0, "target_v2": 0}
    for row, record in selected:
        old = ExactGoldAblationMonitor(_exact_authorization(record, "m3-v2"))
        new = ExactTargetMonitorV2(build_exact_target_authorization_v2(record, "m3-v2"), tool_schemas=DEFAULT_TOOL_SCHEMAS)
        decisions = {"legacy": [], "target_v2": []}
        for index, call in enumerate(_m3_exact_calls(record)):
            arguments = copy.deepcopy(call["arguments"])
            for name, schema in DEFAULT_TOOL_SCHEMAS[call["tool"]]["arguments"].items():
                if name not in arguments and schema.get("required") is True:
                    assert TOOL_ARGUMENT_ROLES[call["tool"]][name] == "content"
                    arguments[name] = "Generated offline interface-check content"
            action = ActionProposal(f"{row['case_id']}-{index}", call["tool"], arguments, ())
            for label, monitor in (("legacy", old), ("target_v2", new)):
                decision = monitor.decide(action)
                decisions[label].append(decision.decision)
                if decision.decision == "ALLOW":
                    monitor.record_execution(action, decision)
        for label in allowed:
            allowed[label] += all(value == "ALLOW" for value in decisions[label])
    assert allowed == {"legacy": 3, "target_v2": 30}


def test_native_agentdojo_schema_roles_are_explicit(selected_records):
    seen = set()
    for row, record in selected_records:
        if row["benchmark"] != "agentdojo-v1":
            continue
        _, _, schemas = _runtime_inputs(record, "agentdojo-v1")
        for tool, schema in schemas.items():
            assert tool in TOOL_ARGUMENT_ROLES
            assert set(schema["arguments"]) <= set(TOOL_ARGUMENT_ROLES[tool])
            seen.add(tool)
    assert len(seen) >= 60


def _mock_client(tmp_path, *, actions, work_key="new-offline-review"):
    payloads = []

    def transport(endpoint, headers, payload, timeout):
        payloads.append(copy.deepcopy(payload))
        action = actions[min(len(payloads), len(actions)) - 1]
        return HTTPResponseEnvelope(status_code=200, headers={}, body={
            "id": f"offline-review-response-{len(payloads)}", "model": payload["model"],
            "choices": [{"message": {"role": "assistant", "content": json.dumps(action)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20,
                      "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 10},
        })

    client = DevelopmentRequestClient(
        model_group="deepseek_pro", model="deepseek-v4-pro", api_key="offline-test-value",
        benchmark="m3-v2", work_key=work_key, attempt=1, trace_path=tmp_path / "trace.jsonl",
        pacer=RequestPacer(0, threading.Event()), transport=transport, max_provider_calls=8,
    )
    return client, payloads


@pytest.mark.parametrize("regime", ["auto_compiled", "exact_target_v2"])
@pytest.mark.parametrize("scenario_id,expected,sends", [
    ("private_restricted", "DENY", 0), ("missing_classification", "ASK", 0),
    ("public_restricted", "ALLOW", 1), ("private_archive", "ALLOW", 1),
])
def test_new_factory_runs_through_provider_guard_backend_and_serialization(tmp_path, regime, scenario_id, expected, sends):
    scenario = SCENARIOS[scenario_id]
    actions = fixed_actions(scenario)
    client, payloads = _mock_client(tmp_path, actions=actions)
    backend, tracker = MemoryEffectBackend(scenario), TrustedDataLabelTracker()
    manifest = manifest_for(scenario)
    control = {"guard_modules": sorted(FULL_RUNTIME_MODULES)}
    if regime == "exact_target_v2":
        # These are an explicit excluded oracle control, never provider inputs.
        control["authorization"] = {
            "authorization_regime": regime, "source_class": "evaluator_derived_authorization",
            "formal_primary_endpoint_eligible": False,
            "rules": [{"rule_id": f"oracle-{index}", "tool": action["tool"],
                       "argument_constraints": {name: {"kind": "exact", "required": True, "value": value}
                                                for name, value in action["arguments"].items()}}
                      for index, action in enumerate(actions[:-1])],
        }
    context = OnlineExecutorContext(
        execution_identity="claude-repairs-offline-new", work_key="new-offline-review", benchmark="m3-v2",
        condition_id="m3_full", max_provider_calls=8,
        online_state={"agent_input": {"trusted_user_request": scenario.request, "trusted_app_context": {},
                                      "untrusted_content": "", "untrusted_memory": []}, "runtime_control": control},
    )

    def oracle_factory(authorization, *, tool_schemas, manifest, modules):
        monitor = ExactTargetMonitorV2(authorization, tool_schemas=tool_schemas)
        monitor.attach_runtime_restrictions(manifest, modules=modules, tracker=tracker)
        return monitor

    runtime = LiveConditionRuntime(
        provider_client_factory=lambda _: client, effect_backend_factory=lambda *_: backend,
        policy_manifest_factory=lambda *_: manifest,
        monitor_factory=lambda manifest, modules: RuntimeMonitorCorrectedV2(manifest, modules=modules, tracker=tracker),
        oracle_monitor_factory=oracle_factory if regime == "exact_target_v2" else None,
        provenance_tracker_factory=lambda: tracker, capture_runtime_failures=True,
        message_builder=lambda context, view, schemas, policy, profile: build_research_messages_v2(
            view, tool_schemas=schemas, manifest=policy, prompt_profile="normal"),
        physical_attempt_namespace=client.physical_attempt_namespace,
    )
    raw = runtime.execute(context, CONDITION_PROFILES["m3_full"])
    assert raw["operational_status"] == "completed"
    assert raw["events"][1]["decision"] == expected
    assert len(backend.outbox) == sends
    assert backend.closed
    published = public_events(raw["events"])
    path = tmp_path / "public.json"
    path.write_text(json.dumps(published), encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == published
    assert published[1]["simulated_action_executed"] is bool(sends)
    assert CONTENT not in json.dumps(published)
    assert all(not request["provider_tools_enabled"] for request in client.requests)
    first_payload = json.dumps(payloads[0])
    assert "oracle-0" not in first_payload
    assert "evaluator_derived_authorization" not in first_payload
    assert "formal_primary_endpoint_eligible" not in first_payload
    if expected == "ASK":
        assert published[1]["corrected_diagnostics"]["dataflow"]["status"] == "missing_input"


@pytest.mark.parametrize("regime", ["auto_compiled", "exact_target_v2"])
def test_correctness_entry_persists_actual_versions_and_guard_receipts(tmp_path, regime):
    from experiments.paper_v2.correctness_plan_v1 import build_plan
    from experiments.paper_v2.correctness_runner_v1 import append_row, execute_one, read_jsonl
    from experiments.paper_v2.correctness_runtime_v1 import CorrectnessRuntime

    row = next(row for row in build_plan() if row["model_group"] == "deepseek_pro"
               and row["benchmark"] == "m3-v2" and row["evaluation_case_type"] == "benign_tool"
               and row["condition_id"] == "m3_full")
    row = {**row, "work_key": "new-review-persistence", "execution_identity": "c" * 64,
           "study_id": "claude-repairs-offline-new", "run_id": "claude-repairs-offline-new",
           "runtime_version": "corrected_v2", "runtime_revision": "corrected_v2",
           "compiler_revision": "corrected_v2", "authorization_regime": regime}
    plan = tmp_path / "new-plan.jsonl"
    append_row(plan, row)
    runtime = CorrectnessRuntime(plan_path=plan, execution_identity=row["execution_identity"],
                                 compiler_revision="corrected_v2", runtime_revision="corrected_v2", authorization_regime=regime)

    def factory(**kwargs):
        # Real client/run/evaluator/save paths with only the HTTP boundary mocked.
        client, _ = _mock_client(tmp_path, actions=[{"tool": "final", "arguments": {"answer": "done"}}], work_key=kwargs["work_key"])
        return client

    result = execute_one(row, 1, runtime=runtime, api_key="offline-test-value",
                         pacer=RequestPacer(0, threading.Event()), output=tmp_path / "output", client_factory=factory)
    assert result["operational_status"] == "completed"
    assert result["runtime_revision"] == result["compiler_revision"] == "corrected_v2"
    assert result["authorization_regime"] == regime
    assert result["online_forbidden_fields_present"] is False
    assert result["events"][0]["provider_receipt_digest"]
    assert result["evaluation_details"]["execution_evidence_complete"] is True
    path = tmp_path / "new-raw.jsonl"
    append_row(path, result)
    assert read_jsonl(path) == [result]
    with pytest.raises(ValueError, match="regime disagree"):
        runtime.execute({**row, "authorization_regime": "different"}, object())
    with pytest.raises(ValueError, match="revision disagree"):
        runtime.execute({**row, "runtime_revision": "corrected_v1"}, object())


def test_repaired_runtime_cannot_silently_reuse_old_plan_versions(tmp_path):
    from experiments.paper_v2.correctness_plan_v1 import build_plan
    from experiments.paper_v2.correctness_runner_v1 import append_row
    from experiments.paper_v2.correctness_runtime_v1 import CorrectnessRuntime

    row = next(row for row in build_plan() if row["model_group"] == "deepseek_pro"
               and row["benchmark"] == "m3-v2" and row["condition_id"] == "m3_full")
    path = tmp_path / "old-plan.jsonl"
    append_row(path, row)
    runtime = CorrectnessRuntime(plan_path=path, execution_identity=row["execution_identity"],
                                 compiler_revision="corrected_v2", runtime_revision="corrected_v2")
    with pytest.raises(ValueError, match="revision disagree"):
        runtime.execute(row, object())


def test_public_event_receipts_distinguish_denial_isolation_effect_and_unknown():
    from experiments.paper_v2.boundary_rejection_runtime_v3 import BOUNDARY_REJECTION_REASON

    events = [
        {"tool": "send_email", "decision": "ASK", "execution_attempted": False, "execution_succeeded": False},
        {"tool": "send_email", "decision": "ALLOW", "execution_attempted": True, "execution_succeeded": False,
         "observation": {"error": BOUNDARY_REJECTION_REASON}},
        {"tool": "send_email", "decision": "ALLOW", "execution_attempted": True, "execution_succeeded": True,
         "observation": {"effect_applied": True}},
        {"tool": "send_email", "decision": "ALLOW", "execution_attempted": True, "execution_succeeded": False,
         "reason_code": "runtime_failure", "observation": {"error": "runtime_failure"}},
    ]
    saved = json.loads(json.dumps(public_events(events)))
    assert [row["simulated_action_executed"] for row in saved] == [False, False, True, None]
    assert [row["isolation_rejected"] for row in saved] == [False, True, False, None]
