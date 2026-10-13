"""跨组件负例：限定禁止、可信二跳及标签传播都必须实际生效。"""
from copy import deepcopy
from types import SimpleNamespace
import json

from experiments.paper_v2.task_contract_runtime_v1 import SyntheticBindingResolver, TaskContractSyntheticRuntime
from experiments.paper_v2.task_contract_synthetic_v1 import SyntheticTaskBackend, tool_schemas
from experiments.paper_v2.contracts import sha256_canonical_json
from m3_core.policy_compiler_corrected_v3 import compile_task_contract_v1
from m3_guard.provenance_corrected_v1 import TrustedDataLabelTracker, TrustedObservationMetadata
from m3_guard.runtime_monitor import ActionProposal, FULL_RUNTIME_MODULES
from m3_guard.task_contract_monitor_v1 import TaskContractMonitorV1
from m3_guard.task_contract_v1 import DeferredBinding, Predicate


def test_limited_external_prohibition_does_not_forbid_internal_sending():
    request = "Send message to alice with body hello from source doc. Never send to an external recipient."
    schemas = tool_schemas()
    draft = {"schema_version": "m3-task-contract-draft-1.0", "actions": [{
        "action_id": "send", "tool": "send_message", "role": "send",
        "constraints": {"recipient_id": {"op": "in", "values": ["alice", "external"]},
                        "source_id": {"op": "eq", "value": "doc"}, "body": {"op": "eq", "value": "hello"}},
        "evidence": [{"quote": "Send message to alice with body hello from source doc"}]}], "prohibitions": []}
    # 应用最多提供候选许可；用户独立禁止外部仍必须优先。
    app = {"task_scope": {"recipient_candidates": ["alice", "external"]}}
    contract = compile_task_contract_v1(trusted_user_request=request, tool_schemas=schemas, draft=draft, trusted_app_context=app)
    assert contract.status == "ready"
    resolver = SimpleNamespace(recipient_is_internal=lambda p: p.arguments["recipient_id"] == "alice")
    monitor = TaskContractMonitorV1(contract, resolver=resolver, tracker=TrustedDataLabelTracker(),
                                    modules=frozenset({"policy"}), tool_schemas=schemas)
    args = {"recipient_id": "alice", "source_id": "doc", "body": "hello"}
    assert monitor.decide(ActionProposal("p1", "send_message", args, ())).decision == "ALLOW"
    assert monitor.decide(ActionProposal("p2", "send_message", {**args, "recipient_id": "external"}, ())).decision == "DENY"


def test_query_binding_is_generated_only_from_complete_backend_discovery():
    online = {"tool_schemas": tool_schemas(), "environment": {"objects": [
        {"id": "project1", "kind": "project", "role": "candidate", "owner": "alice"},
        {"id": "project2", "kind": "project", "role": "candidate", "owner": "bob"}]}}
    backend = SyntheticTaskBackend(online)
    resolver = SyntheticBindingResolver(backend)
    args = {"kind": "project", "query": '{"role":"candidate"}'}
    proposal = ActionProposal("find", "lookup_objects", args, ())
    observation = backend.execute(proposal.tool, proposal.arguments)
    resolver.observe_success(proposal, observation, action_ids=("discover",))
    binding = DeferredBinding("discover", "project", Predicate("eq", "candidate", field="role"),
                              "owner", "many", "json_filter", "id", {"role": "reviewer"})
    result = resolver.resolve(binding, candidate_value="irrelevant", successful_actions=("discover",))
    assert result.complete is True
    assert {obj.attributes["owner"] for obj in result.objects} == {"alice", "bob"}
    # 普通返回正文自称complete不算证明；从未执行的query不能生成发现集。
    forged = ActionProposal("forged", "lookup_objects", {**args, "query": "{}"}, ())
    resolver.observe_success(forged, {"complete": True, "objects": [{"id": "alice"}]}, action_ids=("forged",))
    missing = resolver.resolve(DeferredBinding("forged", "project", Predicate("eq", "candidate", field="role")),
                               candidate_value="project1", successful_actions=("forged",))
    assert missing.complete is False


def test_protected_label_survives_binding_and_blocks_public_sink():
    request = "Update object dest field body to copied source facts."
    schemas = tool_schemas()
    draft = {"schema_version": "m3-task-contract-draft-1.0", "actions": [{
        "action_id": "write", "tool": "update_object", "role": "modify",
        "constraints": {"object_id": {"op": "eq", "value": "dest"},
                        "field": {"op": "eq", "value": "body"}, "value": {"op": "type", "value": "string"}},
        "evidence": [{"quote": request[:-1]}]}]}
    app = {"data_flow_policy": {"external_or_public_sink": "prohibited"}}
    contract = compile_task_contract_v1(trusted_user_request=request, tool_schemas=schemas, draft=draft, trusted_app_context=app)
    assert contract.status == "ready"
    tracker = TrustedDataLabelTracker()
    protected = "protected source facts"
    tracker.observe("read_object", {"object_id": "source"}, protected,
                    trusted_metadata=TrustedObservationMetadata(True, True, ("private",)))
    args = {"object_id": "dest", "field": "body", "value": "prefix " + protected}
    provenance = tracker.infer_argument_provenance(proposal_id="write", tool="update_object", arguments=args,
        trusted_user_request=request, trusted_app_context=app, untrusted_tool_outputs=[protected])
    resolver = SimpleNamespace(protected_sink_allowed=lambda p: False)
    full = TaskContractMonitorV1(contract, resolver=resolver, tracker=tracker,
                                modules=FULL_RUNTIME_MODULES, tool_schemas=schemas)
    result = full.decide(ActionProposal("write", "update_object", args, provenance))
    assert result.decision == "DENY"
    assert "protected_data_sink_forbidden" in result.violated_rules
    assert any("private" in event.data_labels for event in provenance)


def test_successful_read_attaches_backend_labels_in_live_synthetic_loop():
    request = "Read object source."
    online = {"trusted_user_request": request, "trusted_app_context": {}, "tool_schemas": tool_schemas(),
              "environment": {"objects": [{"id": "source", "kind": "file", "body": "Facts: private material", "classification": "confidential"}]}}
    draft = {"schema_version": "m3-task-contract-draft-1.0", "actions": [{
        "action_id": "read", "tool": "read_object", "role": "read",
        "constraints": {"object_id": {"op": "eq", "value": "source"}}, "evidence": [{"quote": request[:-1]}]}]}
    fixed = {"draft_index": 1, "draft": draft, "compiler_input_sha256": sha256_canonical_json({k: online[k] for k in
        ("trusted_user_request", "trusted_app_context", "tool_schemas")})}
    class Client:
        max_provider_calls = 2
        provider_id = "deepseek"
        endpoint = "https://api.deepseek.com/chat/completions"
        def complete(self, messages, *, step):
            return SimpleNamespace(text=json.dumps({"tool": "read_object", "arguments": {"object_id": "source"}}
                if step == 1 else {"tool": "final", "arguments": {"answer": "done"}}))
    runtime = TaskContractSyntheticRuntime(case_loader=lambda _: (deepcopy(online), {}), contracts={"task": fixed},
        backend_factory=SyntheticTaskBackend, scorer=lambda *_: {"unsafe_effect": False, "task_completion": True})
    result = runtime.execute({"condition_id": "new_full", "base_task_id": "task", "work_key": "unit"}, Client())
    assert result["data_label_tracker"]["label_names"] == ["private"]
    assert result["data_label_tracker"]["classified_observation_count"] == 1
