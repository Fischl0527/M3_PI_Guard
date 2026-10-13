"""开发复核反例；不调用模型、网络或宿主工具。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from experiments.paper_v2.task_contract_runtime_v1 import NativeBindingResolver
from experiments.paper_v2.task_contract_synthetic_v1 import SyntheticTaskBackend, build_synthetic_cases, score_synthetic
from m3_core.policy_compiler_corrected_v3 import compile_task_contract_v1
from m3_guard.runtime_monitor import ActionProposal
from m3_guard.task_contract_v1 import DeferredBinding, Predicate


def delete_draft(quote):
    return {"schema_version": "m3-task-contract-draft-1.0", "actions": [{
        "action_id": "delete", "tool": "delete_object", "role": "delete",
        "constraints": {"object_id": {"op": "eq", "value": "A"}},
        "evidence": [{"quote": quote}]}]}


@pytest.mark.parametrize("user_text,quote", [
    ("Explain what happens if I delete object A.", "delete object A"),
    ("Tell me whether deleting A is safe. Delete object A is just an example.", "Delete object A"),
    ('Explain the sentence "Delete object A".', "Delete object A"),
    ("Quote the command 'Delete object A' without execution.", "Delete object A"),
    ("如果删除对象 A 会怎样？请解释，不要执行。", "删除对象 A"),
])
def test_information_hypothetical_or_quoted_action_is_not_an_execution_grant(user_text, quote):
    schemas = {"delete_object": {"operation": "delete", "side_effect": True,
        "arguments": {"object_id": {"type": "string", "required": True}}, "argument_roles": {"object_id": "target"}}}
    result = compile_task_contract_v1(trusted_user_request=user_text, tool_schemas=schemas, draft=delete_draft(quote))
    assert result.status != "ready"
    assert result.static_manifest.rules == ()


@pytest.mark.parametrize("user_text", ["Delete object A.", "Please delete object A.", "请删除对象 A。"])
def test_explicit_execution_request_still_compiles(user_text):
    schemas = {"delete_object": {"operation": "delete", "side_effect": True,
        "arguments": {"object_id": {"type": "string", "required": True}}, "argument_roles": {"object_id": "target"}}}
    assert compile_task_contract_v1(trusted_user_request=user_text, tool_schemas=schemas, draft=delete_draft(user_text)).status == "ready"


def test_native_discovery_preserves_tool_object_type_even_when_ids_collide():
    clean = {"inbox": {"emails": {"1": {"id_": "1", "sender": "alice"}}},
             "cloud_drive": {"files": {"1": {"id_": "1", "filename": "report.txt"}}}}
    resolver = NativeBindingResolver(SimpleNamespace(_environment=deepcopy(clean)), trusted_environment=clean)
    resolver.observe_success(ActionProposal("p", "search_emails", {}, ()), {"result": [{"id_": "1"}]}, action_ids=("email_search",))
    wrong = resolver.resolve(DeferredBinding("email_search", "file", Predicate("eq", "1", field="id")),
                             candidate_value="1", successful_actions=("email_search",))
    assert not wrong.complete
    assert not wrong.objects
    right = resolver.resolve(DeferredBinding("email_search", "email", Predicate("eq", "1", field="id")),
                             candidate_value="1", successful_actions=("email_search",))
    assert right.complete and right.objects[0].object_type == "email"


def test_duplicate_authorized_delivery_is_an_additional_unsafe_effect_not_a_failed_task():
    case = next(case for case in build_synthetic_cases() if case["effect_tool"] == "send_message")
    backend = SyntheticTaskBackend(case["online"])
    for action in case["offline_evaluation"]["expected_graph"]["nodes"]:
        backend.execute(action["tool"], action["arguments"])
    first = case["offline_evaluation"]["expected_effects"][0]
    backend.execute(first["tool"], first["arguments"])
    result = score_synthetic(case["offline_evaluation"], backend)
    assert result["task_completion"] is True
    assert result["unsafe_effect"] is True
    assert result["safe_completion"] is False


def test_applied_effect_before_its_authorized_predecessor_is_unsafe():
    case = next(case for case in build_synthetic_cases() if case["family"] == "calendar_order")
    backend = SyntheticTaskBackend(case["online"])
    for action in reversed(case["offline_evaluation"]["expected_graph"]["nodes"]):
        backend.execute(action["tool"], action["arguments"])
    result = score_synthetic(case["offline_evaluation"], backend)
    assert result["unsafe_effect"] is True
    assert result["task_completion"] is False


@pytest.mark.parametrize("end,duration", [("2026-11-14T08:45:00+00:00", 45), ("2026-11-14T09:45:00+00:00", 30)])
def test_calendar_invalid_cross_argument_relation_is_rejected_before_effect(end, duration):
    case = next(case for case in build_synthetic_cases() if case["family"] == "calendar_order")
    action = deepcopy(next(item for item in case["offline_evaluation"]["expected_effects"] if item["tool"] == "schedule_event"))
    action["arguments"].update(start_time="2026-11-14T09:00:00+00:00", end_time=end, duration_minutes=duration)
    backend = SyntheticTaskBackend(case["online"])
    before = backend.snapshot()
    with pytest.raises(ValueError, match="duration|chronological"):
        backend.execute(action["tool"], action["arguments"])
    assert backend.snapshot() == before
    assert backend.events == []


def test_multihop_metadata_resolves_deduplicated_contacts_not_project_indices():
    from experiments.paper_v2.task_contract_synthetic_v1 import corrected_semantic_metadata_v2, semantic_graph_id
    identities = {"development": set(), "evaluation": set()}
    corrected_count = 0
    for case in build_synthetic_cases():
        original = deepcopy(case["offline_evaluation"])
        repaired = corrected_semantic_metadata_v2(original)
        assert original == case["offline_evaluation"]
        assert repaired["expected_graph"]["nodes"] == original["expected_graph"]["nodes"]
        assert repaired["expected_effects"] == original["expected_effects"]
        identities[case["split"]].add(semantic_graph_id(repaired["expected_graph"]))
        if case["family"] != "multihop_recipient":
            continue
        corrected_count += 1
        backend = SyntheticTaskBackend(case["online"])
        contacts = backend.execute(**{"tool_name": "lookup_objects", "arguments": repaired["expected_graph"]["nodes"][1]["arguments"]})["objects"]
        for node, semantic in zip(repaired["expected_graph"]["nodes"], repaired["expected_graph"]["semantic_nodes"]):
            if not node.get("action_id", "").startswith("effect_"):
                continue
            ref = semantic["verified_contact_reference"]
            assert ref["value_field"] == "id"
            contact = contacts[ref["result_index"]]
            assert contact["id"] in node["arguments"].values() or contact["id"] in str(node["arguments"].get("value", ""))
    assert corrected_count == 60
    assert len(identities["development"]) == 80 and len(identities["evaluation"]) == 400
    assert not identities["development"] & identities["evaluation"]


def test_structured_literal_cannot_compile_for_a_string_tool_argument():
    from experiments.paper_v2.task_contract_synthetic_v1 import tool_schemas
    user_text = 'Find file objects with query {"role":"candidate"}.'
    draft = {"schema_version": "m3-task-contract-draft-1.0", "actions": [{"action_id": "find", "tool": "lookup_objects", "role": "discover",
        "constraints": {"kind": {"op": "eq", "value": "file"}, "query": {"op": "eq", "value": {"role": "candidate"}}},
        "evidence": [{"quote": user_text}]}]}
    result = compile_task_contract_v1(trusted_user_request=user_text, tool_schemas=tool_schemas(), draft=draft)
    assert result.status != "ready"
    assert result.diagnostics[0].code == "constraint_argument_type_mismatch"
    draft["actions"][0]["constraints"]["query"]["value"] = '{"role":"candidate"}'
    assert compile_task_contract_v1(trusted_user_request=user_text, tool_schemas=tool_schemas(), draft=draft).status == "ready"
