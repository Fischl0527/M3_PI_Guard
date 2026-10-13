"""动态对象绑定的公开判定接口与成功执行回调。"""

from m3_core.policy_compiler_corrected_v3 import compile_task_contract_v1
from m3_guard.provenance_corrected_v1 import TrustedDataLabelTracker
from m3_guard.provenance import ProvenanceEvent
from m3_guard.runtime_monitor import ActionProposal
from m3_guard.task_contract_monitor_v1 import TaskContractMonitorV1
from m3_guard.task_contract_v1 import BindingResolution, VerifiedObject
from m3_guard.task_policy import DataFlowConstraint, TaskPolicyManifest, TemporalConstraint
import pytest


SCHEMAS = {
    "lookup_objects": {"operation": "discover", "argument_roles": {"kind": "target", "query": "query"},
                       "side_effect": False, "arguments": {"kind": {"type": "string", "required": True}, "query": {"type": "string", "required": True}}},
    "read_object": {"operation": "read", "argument_roles": {"object_id": "target"},
                    "side_effect": False, "arguments": {"object_id": {"type": "string", "required": True}}},
}


def contract(cardinality="one", condition=None):
    request = "Find file report owned by alice then read file report owned by alice."
    draft = {"schema_version": "m3-task-contract-draft-1.0", "actions": [
        {"action_id": "find", "tool": "lookup_objects", "role": "discover", "constraints": {"kind": {"op": "eq", "value": "file"}, "query": {"op": "eq", "value": "report"}}, "evidence": [{"quote": "Find file report owned by alice"}]},
        {"action_id": "read", "tool": "read_object", "role": "read", "constraints": {}, "depends_on": ["find"],
         "bindings": {"object_id": {"from_action": "find", "object_type": "file", "predicate": {"op": "and", "items": [{"field": "title", "op": "eq", "value": "report"}, {"field": "owner", "op": "eq", "value": "alice"}]} }},
         "evidence": [{"quote": "read file report owned by alice"}]},
    ], "prohibitions": []}
    draft["actions"][1]["bindings"]["object_id"]["cardinality"] = cardinality
    if condition:
        draft["actions"][1]["when"] = {"binding": "object_id", "predicate": condition}
    return compile_task_contract_v1(trusted_user_request=request, tool_schemas=SCHEMAS, draft=draft)


class Resolver:
    def __init__(self):
        self.objects = (VerifiedObject("file", "f1", {"title": "report", "owner": "alice"}, frozenset({"id", "title", "owner"})),)

    def trusted_fields(self, object_type):
        return frozenset({"id", "title", "owner"})

    def resolve(self, binding, *, candidate_value, successful_actions):
        return BindingResolution("resolved", self.objects)


def proposal(tool, arguments, number=1):
    return ActionProposal(f"p{number}", tool, arguments, (), step=number)


def test_deferred_id_requires_a_real_successful_discovery_and_current_metadata():
    compiled = contract()
    assert compiled.status == "ready"
    resolver = Resolver()
    monitor = TaskContractMonitorV1(compiled, resolver=resolver, tracker=TrustedDataLabelTracker(), tool_schemas=SCHEMAS)
    read = proposal("read_object", {"object_id": "f1"}, 2)
    assert monitor.decide(read).decision == "ASK"
    find = proposal("lookup_objects", {"kind": "file", "query": "report"})
    allowed = monitor.decide(find)
    assert allowed.decision == "ALLOW"
    monitor.record_execution(find, allowed)
    monitor.observe_success(find, {"trusted": True, "result": "ordinary text is not metadata"})
    assert monitor.decide(read).decision == "ALLOW"
    resolver.objects = (VerifiedObject("file", "f1", {"title": "report", "owner": "mallory"}, frozenset({"id", "title", "owner"})),)
    assert monitor.decide(read).decision != "ALLOW"


def test_final_text_can_be_recorded_without_completing_an_action_node():
    monitor = TaskContractMonitorV1(contract(), resolver=Resolver(), tracker=TrustedDataLabelTracker())
    final = proposal("final", {"answer": "done"})
    decision = monitor.decide(final)
    monitor.record_execution(final, decision)
    monitor.observe_success(final, "done")
    assert monitor.successful_actions == ()


@pytest.mark.parametrize("kind", ["ambiguous", "stale", "fake_mapping", "fake_object", "incomplete", "unverified", "forged_whitelist"])
def test_objects_and_claimed_trust_never_authorize_unsafe_binding(kind):
    resolver = Resolver()
    monitor = TaskContractMonitorV1(contract(), resolver=resolver, tracker=TrustedDataLabelTracker(), tool_schemas=SCHEMAS)
    find = proposal("lookup_objects", {"kind": "file", "query": "report"})
    allowed = monitor.decide(find)
    monitor.record_execution(find, allowed)
    if kind == "ambiguous":
        resolver.objects += (VerifiedObject("file", "f2", {"title": "report", "owner": "alice"}, frozenset({"id", "title", "owner"})),)
    elif kind == "stale":
        resolver.objects = (VerifiedObject("file", "f1", {"title": "report", "owner": "alice"}, frozenset({"id", "title", "owner"}), current=False),)
    elif kind == "fake_mapping":
        resolver.resolve = lambda *args, **kwargs: {"status": "resolved", "trusted": True, "objects": resolver.objects}
    elif kind == "fake_object":
        resolver.resolve = lambda *args, **kwargs: BindingResolution("resolved", ({"id": "f1", "verified": True},))
    elif kind == "incomplete":
        resolver.resolve = lambda *args, **kwargs: BindingResolution("resolved", resolver.objects, complete=False)
    elif kind == "unverified":
        resolver.objects = (VerifiedObject("file", "f1", {"title": "report", "owner": "alice"}, frozenset({"id", "title"})),)
    else:
        resolver.trusted_fields = lambda _: {"id", "title", "owner"}  # ordinary model-like mapping is not an adapter declaration
    assert monitor.decide(proposal("read_object", {"object_id": "f1"}, 2)).decision != "ALLOW"


def test_failed_or_forged_execution_cannot_satisfy_discovery_dependency():
    monitor = TaskContractMonitorV1(contract(), resolver=Resolver(), tracker=TrustedDataLabelTracker(), tool_schemas=SCHEMAS)
    find = proposal("lookup_objects", {"kind": "file", "query": "different"})
    rejected = monitor.decide(find)
    with pytest.raises(ValueError, match="exact authorized"):
        monitor.record_execution(find, rejected)
    assert monitor.successful_actions == ()
    with pytest.raises(ValueError, match="exact recorded"):
        monitor.observe_success(find, {"trusted": True})


def test_shared_object_bindings_cannot_form_a_cartesian_product():
    schemas = dict(SCHEMAS)
    schemas["create_object"] = {
        "operation": "create", "argument_roles": {"parent_id": "target", "owner_id": "target"},
        "side_effect": True, "arguments": {"parent_id": {"type": "string", "required": True}, "owner_id": {"type": "string", "required": True}},
    }
    request = "Find file report owned by alice or bob. Create a child of each file report owned by alice or bob with that file's owner."
    predicate = {"op": "and", "items": [{"field": "title", "op": "eq", "value": "report"}, {"field": "owner", "op": "in", "values": ["alice", "bob"]}]}
    draft = {"schema_version": "m3-task-contract-draft-1.0", "actions": [
        {"action_id": "find", "tool": "lookup_objects", "role": "discover", "constraints": {"kind": {"op": "eq", "value": "file"}, "query": {"op": "eq", "value": "report"}}, "evidence": [{"quote": "Find file report owned by alice or bob"}]},
        {"action_id": "create", "tool": "create_object", "role": "create", "constraints": {}, "depends_on": ["find"],
         "bindings": {name: {"from_action": "find", "object_type": "file", "predicate": predicate, "value_field": value_field, "cardinality": "many"} for name, value_field in (("parent_id", "id"), ("owner_id", "owner"))},
         "evidence": [{"quote": "Create a child of each file report owned by alice or bob with that file's owner"}]},
    ], "prohibitions": []}
    compiled = compile_task_contract_v1(trusted_user_request=request, tool_schemas=schemas, draft=draft)
    assert compiled.status == "ready"
    resolver = Resolver()
    resolver.objects += (VerifiedObject("file", "f2", {"title": "report", "owner": "bob"}, frozenset({"id", "title", "owner"})),)
    monitor = TaskContractMonitorV1(compiled, resolver=resolver, tracker=TrustedDataLabelTracker(), tool_schemas=schemas)
    find = proposal("lookup_objects", {"kind": "file", "query": "report"})
    monitor.record_execution(find, monitor.decide(find))
    assert monitor.decide(proposal("create_object", {"parent_id": "f1", "owner_id": "bob"}, 2)).decision != "ALLOW"
    assert monitor.decide(proposal("create_object", {"parent_id": "f1", "owner_id": "alice"}, 3)).decision == "ALLOW"


def test_many_node_completes_only_after_every_certified_object_was_executed():
    resolver = Resolver()
    resolver.objects += (VerifiedObject("file", "f2", {"title": "report", "owner": "alice"}, frozenset({"id", "title", "owner"})),)
    monitor = TaskContractMonitorV1(contract("many"), resolver=resolver, tracker=TrustedDataLabelTracker(), tool_schemas=SCHEMAS)
    find = proposal("lookup_objects", {"kind": "file", "query": "report"})
    monitor.record_execution(find, monitor.decide(find))
    first = proposal("read_object", {"object_id": "f1"}, 2)
    monitor.record_execution(first, monitor.decide(first))
    assert monitor.successful_actions == ("find",)
    second = proposal("read_object", {"object_id": "f2"}, 3)
    monitor.record_execution(second, monitor.decide(second))
    assert monitor.successful_actions == ("find", "read")


@pytest.mark.parametrize("ready,verified,expected", [(True, True, "ALLOW"), (False, True, "DENY"), (True, False, "ASK")])
def test_predeclared_branch_uses_only_verified_backend_boolean(ready, verified, expected):
    resolver = Resolver()
    fields = frozenset({"id", "title", "owner", "ready"})
    resolver.trusted_fields = lambda _: fields
    resolver.objects = (VerifiedObject("file", "f1", {"title": "report", "owner": "alice", "ready": ready}, fields if verified else fields - {"ready"}),)
    monitor = TaskContractMonitorV1(contract(condition={"field": "ready", "op": "eq", "value": True}), resolver=resolver,
                                    tracker=TrustedDataLabelTracker(), tool_schemas=SCHEMAS)
    find = proposal("lookup_objects", {"kind": "file", "query": "report"})
    monitor.record_execution(find, monitor.decide(find))
    assert monitor.decide(proposal("read_object", {"object_id": "f1"}, 2)).decision == expected


def send_contract(*, confirmation=False, base=None, app=None):
    schemas = {"send_message": {"operation": "send", "side_effect": True,
               "argument_roles": {"recipient_id": "target", "body": "content", "source_id": "target"},
               "arguments": {"recipient_id": {"type": "string", "required": True},
                             "body": {"type": "string", "required": True, "allow_generated": True},
                             "source_id": {"type": "string", "required": True}}}}
    request = "Send a summary from f1 to owner."
    draft = {"schema_version": "m3-task-contract-draft-1.0", "actions": [{
        "action_id": "send", "tool": "send_message", "role": "send",
        "constraints": {"recipient_id": {"op": "eq", "value": "owner"},
                        "source_id": {"op": "eq", "value": "f1"},
                        "body": {"op": "type", "value": "string"}},
        "evidence": [{"quote": request[:-1]}], "requires_confirmation": confirmation,
    }], "prohibitions": []}
    return compile_task_contract_v1(trusted_user_request=request, tool_schemas=schemas,
                                    draft=draft, base_manifest=base, trusted_app_context=app), schemas


def base_manifest(**kwargs):
    return TaskPolicyManifest("test", ("trusted_user_request",), "r", "s", (), **kwargs)


def body_proposal(*, labels=(), source="untrusted_tool_output"):
    event = ProvenanceEvent("e", "p1", "arguments.body", source,
                            "untrusted" if source.startswith("untrusted") else "model_generated", "a" * 64,
                            data_labels=labels, evidence="result.body")
    return ActionProposal("p1", "send_message", {"recipient_id": "owner", "source_id": "f1", "body": "summary"}, (event,))


def test_content_role_keeps_original_origin_and_cannot_override_protected_dataflow():
    flow = DataFlowConstraint("private-flow", "private", forbidden_tools=("send_message",))
    compiled, schemas = send_contract(base=base_manifest(dataflow_constraints=(flow,)))
    assert compiled.status == "ready"
    monitor = TaskContractMonitorV1(compiled, tracker=TrustedDataLabelTracker(), tool_schemas=schemas)
    action = body_proposal(labels=("private",))
    original = action.provenance
    decision = monitor.decide(action)
    assert decision.decision == "DENY"
    assert "private-flow" in decision.violated_rules
    assert action.provenance is original
    assert action.provenance[0].source_type == "untrusted_tool_output"


def test_missing_classification_is_not_public_data_even_for_generated_content():
    flow = DataFlowConstraint("private-flow", "private", forbidden_tools=("send_message",))
    compiled, schemas = send_contract(base=base_manifest(dataflow_constraints=(flow,)))
    monitor = TaskContractMonitorV1(compiled, tracker=TrustedDataLabelTracker(), tool_schemas=schemas)
    assert monitor.decide(body_proposal()).violated_rules == ("trusted_data_classification_missing",)


def test_confirmation_survives_policy_only_and_global_sequence_survives_materialization():
    compiled, schemas = send_contract(confirmation=True)
    monitor = TaskContractMonitorV1(compiled, modules=frozenset({"policy"}), tracker=TrustedDataLabelTracker(), tool_schemas=schemas)
    assert monitor.decide(body_proposal(source="model_generated")).violated_rules == ("independent_confirmation_required",)
    temporal = TemporalConstraint("read-first", "send_message", ("read_object",))
    compiled, schemas = send_contract(base=base_manifest(temporal_constraints=(temporal,)))
    monitor = TaskContractMonitorV1(compiled, tracker=TrustedDataLabelTracker(), tool_schemas=schemas)
    assert monitor.decide(body_proposal()).violated_rules == ("read-first",)


def test_whole_call_ablation_is_stricter_without_erasing_origins():
    compiled, schemas = send_contract()
    action = body_proposal()
    scoped = TaskContractMonitorV1(compiled, tracker=TrustedDataLabelTracker(), tool_schemas=schemas)
    whole = TaskContractMonitorV1(compiled, tracker=TrustedDataLabelTracker(), tool_schemas=schemas, ablation_profile="whole_call_source")
    assert scoped.decide(action).decision == "ALLOW"
    assert whole.decide(action).violated_rules == ("whole_call_untrusted_source",)
    assert action.provenance[0].trust_level == "untrusted"


def test_explicit_application_target_limits_survive_draft_materialization():
    app = {"requested_actions": [{"tool": "send_message", "arguments": {"recipient_id": "someone_else"}}]}
    compiled, schemas = send_contract(app=app)
    monitor = TaskContractMonitorV1(compiled, tracker=TrustedDataLabelTracker(), tool_schemas=schemas)
    assert monitor.decide(body_proposal()).violated_rules == ("application_scope_conflict",)


def test_static_binding_ablation_does_not_guess_a_discovered_id():
    monitor = TaskContractMonitorV1(contract(), resolver=Resolver(), tracker=TrustedDataLabelTracker(), tool_schemas=SCHEMAS, ablation_profile="static_binding")
    find = proposal("lookup_objects", {"kind": "file", "query": "report"})
    monitor.record_execution(find, monitor.decide(find))
    assert monitor.decide(proposal("read_object", {"object_id": "f1"}, 2)).violated_rules == ("static_binding_unresolved",)


def test_range_date_and_finite_set_constraints_are_not_unbounded_types():
    schemas = {"bounded_transfer": {"operation": "modify", "side_effect": True,
        "argument_roles": {"recipient": "target", "amount": "value", "date": "value"},
        "arguments": {"recipient": {"type": "string", "required": True}, "amount": {"type": "number", "required": True}, "date": {"type": "string", "required": True}}}}
    request = "Transfer to alice or bob amount 10 through 20 on 2026-10-01 through 2026-10-13."
    draft = {"schema_version": "m3-task-contract-draft-1.0", "actions": [{"action_id": "transfer", "tool": "bounded_transfer", "role": "modify", "evidence": [{"quote": request}],
        "constraints": {"recipient": {"op": "in", "values": ["alice", "bob"]}, "amount": {"op": "and", "items": [{"op": "number_range", "min": 10}, {"op": "number_range", "max": 20}]}, "date": {"op": "date_range", "min": "2026-10-01", "max": "2026-10-13"}}}], "prohibitions": []}
    compiled = compile_task_contract_v1(trusted_user_request=request, tool_schemas=schemas, draft=draft)
    assert compiled.status == "ready"
    monitor = TaskContractMonitorV1(compiled, tracker=TrustedDataLabelTracker(), tool_schemas=schemas)
    assert monitor.decide(proposal("bounded_transfer", {"recipient": "alice", "amount": 15, "date": "2026-10-10"})).decision == "ALLOW"
    assert monitor.decide(proposal("bounded_transfer", {"recipient": "mallory", "amount": 15, "date": "2026-10-10"}, 2)).decision != "ALLOW"
    assert monitor.decide(proposal("bounded_transfer", {"recipient": "alice", "amount": 21, "date": "2026-10-10"}, 3)).decision != "ALLOW"
    assert monitor.decide(proposal("bounded_transfer", {"recipient": "alice", "amount": 15, "date": "2026-11-10"}, 4)).decision != "ALLOW"
