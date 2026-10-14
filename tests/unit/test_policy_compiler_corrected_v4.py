"""权限编译 v4 的真实公共边界测试；无模型、网络或宿主副作用。"""

from copy import deepcopy

import pytest

from experiments.paper_v2.task_contract_synthetic_v1 import tool_schemas
from m3_core.policy_compiler_corrected_v4 import (
    INTENT_SCHEMA_VERSION,
    build_trusted_tool_catalog,
    compile_task_intent_v4,
)


def evidence(quote):
    return [{"source": "request", "quote": quote}]


def literal(value, quote):
    return {"kind": "literal", "value": value, "evidence": evidence(quote)}


def action(name, tool, quote, arguments, **extra):
    return {"id": name, "tool": tool, "operation_evidence": evidence(quote),
            "arguments": arguments, **extra}


def compile_intent(request, actions, *, app=None, schemas=None, **extra):
    return compile_task_intent_v4(
        trusted_user_request=request, trusted_app_context=app or {},
        tool_schemas=schemas or tool_schemas(),
        intent={"schema_version": INTENT_SCHEMA_VERSION, "actions": actions, **extra},
    )


def selector(kind, field, value, quote, *, many=False):
    return {"kind": "selector", "object_type": kind, "evidence": evidence(quote),
            "filters": [{"field": field, "op": "in" if many else "eq",
                         "values" if many else "value": value, "evidence": evidence(quote)}]}


def find(name, kind, field, value, quote, *, many=False):
    return action(name, "lookup_objects", quote,
                  {"kind": literal(kind, quote),
                   "query": selector(kind, field, value, quote, many=many)})


def binding(source, object_type, quote, *, field="id", many=False, kind="authority_binding"):
    return {"kind": kind, "from_action": source, "object_type": object_type,
            "value_field": field, "cardinality": "many" if many else "one",
            "evidence": evidence(quote)}


def data(source, quote):
    return {"kind": "data_ref", "from_action": source, "field": "body",
            "transform": "copy", "evidence": evidence(quote)}


@pytest.mark.parametrize("user_text,quote", [
    ("Explain what happens if I read object A.", "read object A"),
    ('Explain the sentence "Read object A".', "Read object A"),
    ("如果读取对象 A 会怎样？请解释，不要执行。", "读取对象 A"),
])
def test_hypothetical_read_is_not_execution_authority(user_text, quote):
    result = compile_intent(user_text, [action("read", "read_object", quote,
                                            {"object_id": literal("A", quote)})])
    assert result.status == "conflict"
    assert result.contract.static_manifest.rules == ()


def test_explicit_read_has_exact_target_without_other_task_values():
    request = "Read object A. Explain why object B exists."
    result = compile_intent(request, [action("read", "read_object", "Read object A",
                                            {"object_id": literal("B", "Read object A")})])
    assert result.status == "needs_clarification"
    assert result.diagnostics[0]["code"] == "literal_scope_not_grounded"


def test_selector_is_encoded_by_program_and_not_model_wire_format():
    user_text = "Find file with owner alice."
    result = compile_intent(user_text, [find("find", "file", "owner", "alice", user_text)])
    assert result.status == "ready"
    assert result.contract.actions[0].constraints["query"].value == '{"owner":"alice"}'
    assert result.contract.actions[0].constraints["kind"].value == "file"


def test_retrieve_read_write_keeps_target_distinct_from_material():
    q1, q2, q3 = "Find file owned by alice", "Read this file", "Update object B body with the read material"
    nodes = [find("find", "file", "owner", "alice", q1),
             action("read", "read_object", q2, {"object_id": binding("find", "file", q2)}),
             action("write", "update_object", q3,
                    {"object_id": literal("B", q3), "field": literal("body", q3), "value": data("read", q3)})]
    result = compile_intent(". ".join((q1, q2, q3)) + ".", nodes)
    assert result.status == "ready"
    read, write = result.contract.actions[1:]
    assert read.bindings["object_id"].object_type == "file"
    assert write.constraints["object_id"].value == "B"
    assert write.depends_on == ("read",)
    assert result.reference_plan[-1]["kind"] == "data_ref"


def test_multihop_recipient_join_has_typed_relation_not_cartesian_target_pool():
    q1 = "Find project with id P"
    q2 = "Find contact belonging to the project owner"
    q3 = "Read the project"
    q4 = "Send the read body to that contact for project P"
    contact_query = selector("contact", "internal", True, q2 + " internal")
    q2 += " internal"
    contact_query["join"] = {"from_action": "projects", "source_field": "owner", "target_field": "owner"}
    nodes = [find("projects", "project", "id", "P", q1),
             action("contacts", "lookup_objects", q2,
                    {"kind": literal("contact", q2), "query": contact_query}),
             action("read", "read_object", q3, {"object_id": binding("projects", "project", q3)}),
             action("send", "send_message", q4,
                    {"recipient_id": binding("contacts", "contact", q4),
                     "source_id": literal("P", q4), "body": data("read", q4)})]
    result = compile_intent(". ".join((q1, q2, q3, q4)) + ".", nodes)
    assert result.status == "ready"
    join = next(ref for ref in result.reference_plan if ref.get("query_binding"))
    assert join["join"] == {"from_action": "projects", "source_field": "owner", "target_field": "owner"}
    assert result.contract.actions[-1].bindings["recipient_id"].object_type == "contact"
    assert result.contract.actions[-1].depends_on == ("contacts", "read")


def test_calendar_parameters_remain_exact_and_ordered():
    q1 = "Find calendar_event with id E"
    q2 = "Reschedule E to start 2026-11-14T09:00:00+00:00 end 2026-11-14T09:45:00+00:00 duration 45"
    nodes = [find("find", "calendar_event", "id", "E", q1),
             action("schedule", "schedule_event", q2,
                    {"object_id": binding("find", "calendar_event", q2),
                     "start_time": literal("2026-11-14T09:00:00+00:00", q2),
                     "end_time": literal("2026-11-14T09:45:00+00:00", q2),
                     "duration_minutes": literal(45, q2)})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "ready"
    assert result.contract.actions[-1].depends_on == ("find",)
    assert result.contract.actions[-1].constraints["duration_minutes"].value == 45


def test_prohibition_conflict_blocks_explicit_application_overgrant():
    user_text = "Delete object A."
    node = action("delete", "delete_object", user_text, {"object_id": literal("A", user_text)})
    result = compile_intent(user_text, [node], app={"hard_constraints": {"prohibited_tools": ["delete_object"]}})
    assert result.status == "conflict"
    assert result.contract.static_manifest.rules == ()


def test_bounded_multi_object_keeps_explicit_finite_set():
    q1, q2 = "Find folder with id F1 or F2", "Delete these folders"
    nodes = [find("find", "folder", "id", ["F1", "F2"], q1, many=True),
             action("delete", "delete_object", q2,
                    {"object_id": binding("find", "folder", q2, many=True)})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "ready"
    deferred = result.contract.actions[1].bindings["object_id"]
    assert deferred.cardinality == "many"
    assert deferred.predicate.items[0].values == ("F1", "F2")


def test_mixed_trust_body_cannot_become_recipient():
    q1, q2 = "Read object A", "Send the read body to recipient C with source A"
    nodes = [action("read", "read_object", q1, {"object_id": literal("A", q1)}),
             action("send", "send_message", q2,
                    {"recipient_id": data("read", q2), "source_id": literal("A", q2), "body": data("read", q2)})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "conflict"
    assert result.diagnostics[0]["code"] == "data_reference_scope_conflict"


def test_predefined_branch_uses_verified_boolean_not_tool_text():
    q1 = "Find approval_record with owner alice"
    q2 = "Update the record field body to ready if ready"
    nodes = [find("find", "approval_record", "owner", "alice", q1),
             action("update", "update_object", q2,
                    {"object_id": binding("find", "approval_record", q2),
                     "field": literal("body", q2), "value": literal("ready", q2)},
                    when={"argument": "object_id", "field": "ready", "equals": True, "evidence": evidence(q2)})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "ready"
    assert result.contract.actions[-1].when[1].to_dict() == {"op": "eq", "field": "ready", "value": True}


def test_provenance_confidentiality_retains_application_data_flow_policy():
    user_text = "Read object A."
    flow = {"prohibited_labels": ["confidential"], "blocked_destinations": ["external"]}
    result = compile_intent(user_text,
                            [action("read", "read_object", user_text, {"object_id": literal("A", user_text)})],
                            app={"data_flow_policy": flow})
    assert result.status == "ready"
    assert result.contract.data_flow_policy == flow


def test_wrong_argument_type_cannot_be_losslessly_coerced_without_codec():
    user_text = 'Read object {"id":"A"}.'
    result = compile_intent(user_text, [action("read", "read_object", user_text,
                                            {"object_id": literal({"id": "A"}, user_text)})])
    assert result.status != "ready"


def test_authority_binding_cannot_read_confidential_body_as_payment_value():
    q1, q2 = "Find file with id A", "Reschedule object A duration from file body"
    nodes = [find("find", "file", "id", "A", q1),
             action("schedule", "schedule_event", q2,
                    {"object_id": binding("find", "file", q2),
                     "start_time": binding("find", "file", q2, field="body", kind="result_ref"),
                     "end_time": literal("A", q2), "duration_minutes": literal(5, q2)})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "conflict"


def test_unresolved_intent_is_needs_clarification_without_rules():
    user_text = "Read object A."
    result = compile_intent(user_text,
                            [action("read", "read_object", user_text, {"object_id": literal("A", user_text)})],
                            unresolved=["Which A?"])
    assert result.status == "needs_clarification"
    assert result.contract.static_manifest.rules == ()


def test_scalar_result_reference_requires_declared_binding_capability():
    q1 = "Find calendar_event with id E"
    q2 = "Reschedule the event using its slot_start and slot_end and duration_minutes"
    nodes = [find("find", "calendar_event", "id", "E", q1),
             action("schedule", "schedule_event", q2,
                    {"object_id": binding("find", "calendar_event", q2),
                     "start_time": binding("find", "calendar_event", q2, field="slot_start", kind="result_ref"),
                     "end_time": binding("find", "calendar_event", q2, field="slot_end", kind="result_ref"),
                     "duration_minutes": binding("find", "calendar_event", q2, field="duration_minutes", kind="result_ref")})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "ready"
    assert [ref["kind"] for ref in result.reference_plan] == ["authority_binding", "result_ref", "result_ref", "result_ref"]
    modified = tool_schemas()
    modified["schedule_event"]["arguments"]["start_time"].pop("allow_backend_binding")
    assert compile_intent(q1 + ". " + q2 + ".", nodes, schemas=modified).status == "unsupported"


def test_extracted_action_cannot_drop_negation_from_original_clause():
    user_text = "Read object A. Never delete object A."
    quote = "delete object A"
    result = compile_intent(user_text, [action("delete", "delete_object", quote,
                                            {"object_id": literal("A", quote)})])
    assert result.status == "conflict"
    assert result.contract.static_manifest.rules == ()


def test_selector_cannot_change_fixed_backend_object_type():
    schemas = tool_schemas()
    schemas["lookup_files"] = deepcopy(schemas["lookup_objects"])
    schemas["lookup_files"]["arguments"].pop("kind")
    schemas["lookup_files"]["argument_roles"].pop("kind")
    capabilities = {"tools": {"lookup_files": {"output_object_type": "file"}}}
    catalog = build_trusted_tool_catalog(schemas, capabilities)
    user_text = "Find contact with id C."
    intent = {"schema_version": INTENT_SCHEMA_VERSION,
              "actions": [action("find", "lookup_files", user_text,
                                 {"query": selector("contact", "id", "C", user_text)})]}
    result = compile_task_intent_v4(trusted_user_request=user_text,
                                    trusted_app_context={}, tool_schemas=schemas,
                                    intent=intent, catalog=catalog)
    assert result.status == "conflict"
    assert result.contract.static_manifest.rules == ()


def test_data_ref_cannot_invent_body_output_for_delete_tool():
    q1 = "Delete object A"
    q2 = "Update object B body with the deleted receipt body"
    nodes = [action("delete", "delete_object", q1, {"object_id": literal("A", q1)}),
             action("update", "update_object", q2,
                    {"object_id": literal("B", q2), "field": literal("body", q2), "value": data("delete", q2)})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "unsupported"
    assert result.contract.static_manifest.rules == ()


def test_parameter_evidence_cannot_borrow_another_operation_clause():
    q1, q2 = "Read object A", "Delete object B"
    result = compile_intent(q1 + ". " + q2 + ".", [action("read", "read_object", q1,
                            {"object_id": literal("B", q2)})])
    assert result.status == "needs_clarification"
    assert result.diagnostics[0]["code"] == "parameter_evidence_action_mismatch"
    assert result.diagnostics[0]["repairable"] is False


def test_parameter_application_reference_cannot_borrow_other_tool_action():
    user_text = "Read the requested object."
    app = {"requested_actions": [{"tool": "read_object", "arguments": {"object_id": "A"}},
                                  {"tool": "delete_object", "arguments": {"object_id": "B"}}]}
    wrong = {"kind": "literal", "value": "B", "evidence": [
        {"source": "app", "path": ["requested_actions", 1, "arguments", "object_id"]}]}
    result = compile_intent(user_text, [action("read", "read_object", user_text, {"object_id": wrong})], app=app)
    assert result.status == "needs_clarification"
    assert result.diagnostics[0]["code"] == "parameter_evidence_action_mismatch"


def test_closed_grammar_rejects_arbitrary_expression_without_technical_authority_repair():
    user_text = "Read object A."
    value = {"kind": "expression", "code": "open('/private')", "evidence": evidence(user_text)}
    result = compile_intent(user_text, [action("read", "read_object", user_text, {"object_id": value})])
    assert result.status == "technical_invalid"
    assert result.contract.static_manifest.rules == ()


def test_semantic_failure_does_not_become_technical_repair():
    user_text = "Read object A."
    result = compile_intent(user_text, [action("read", "read_object", user_text,
                           {"object_id": literal("B", user_text)})])
    assert result.diagnostics[0]["repairable"] is False
    assert result.diagnostics[0]["stage"] == "grounding"


def test_content_concat_is_finite_and_preserves_each_source_dependency():
    q1, q2 = "Find project with id P", "Find contact with id C"
    q3 = 'Update object R body to "Contact=" followed by contact id and " Project=" followed by project id'
    parts = [literal("Contact=", q3), {**binding("contact", "contact", q3, kind="result_ref"), "field": "id"},
             literal(" Project=", q3), {**binding("project", "project", q3, kind="result_ref"), "field": "id"}]
    concat = {"kind": "derived", "operation": "concat", "parts": parts, "evidence": evidence(q3)}
    nodes = [find("project", "project", "id", "P", q1), find("contact", "contact", "id", "C", q2),
             action("write", "update_object", q3, {"object_id": literal("R", q3),
                    "field": literal("body", q3), "value": concat})]
    result = compile_intent(". ".join((q1, q2, q3)) + ".", nodes)
    assert result.status == "ready"
    assert result.contract.actions[-1].depends_on == ("contact", "project")
    assert result.reference_plan[-1]["operation"] == "concat"
    assert [part["kind"] for part in result.reference_plan[-1]["parts"]] == ["literal", "result_ref", "literal", "result_ref"]


def test_concat_cannot_generate_a_new_target_permission():
    q1, q2 = "Find contact with id C", 'Send message body hi to "contact-" plus that id using source R'
    concat = {"kind": "derived", "operation": "concat", "parts": [literal("contact-", q2),
              binding("find", "contact", q2, kind="result_ref")], "evidence": evidence(q2)}
    nodes = [find("find", "contact", "id", "C", q1), action("send", "send_message", q2,
              {"recipient_id": concat, "source_id": literal("R", q2), "body": literal("hi", q2)})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "conflict"
    assert result.diagnostics[0]["repairable"] is False


def test_creation_followup_requires_explicit_backend_receipt_capability():
    q1 = "Create file titled report owned by C under P body hello"
    q2 = "Read the created file"
    nodes = [action("create", "create_object", q1,
             {"kind": literal("file", q1), "title": literal("report", q1),
              "owner_id": literal("C", q1), "parent_id": literal("P", q1), "body": literal("hello", q1)}),
             action("read", "read_object", q2, {"object_id": binding("create", "file", q2)})]
    request = q1 + ". " + q2 + "."
    assert compile_intent(request, nodes).status == "unsupported"
    catalog = build_trusted_tool_catalog(tool_schemas(), {"created_object_receipts": ["create_object"]})
    result = compile_task_intent_v4(trusted_user_request=request, trusted_app_context={},
             tool_schemas=tool_schemas(), intent={"schema_version": INTENT_SCHEMA_VERSION, "actions": nodes}, catalog=catalog)
    assert result.status == "ready"
    assert result.contract.actions[-1].depends_on == ("create",)
    assert result.reference_plan[0]["from_action"] == "create"
    from experiments.paper_v2.task_contract_runtime_v4 import build_runtime_tool_catalog
    inputs = {"trusted_user_request": request, "trusted_app_context": {}, "tool_schemas": tool_schemas()}
    runtime_catalog = build_runtime_tool_catalog(inputs)
    shared_result = compile_task_intent_v4(**inputs,
             intent={"schema_version": INTENT_SCHEMA_VERSION, "actions": nodes}, catalog=runtime_catalog)
    assert shared_result.status == "ready"
    assert shared_result.contract.actions[-1].bindings == result.contract.actions[-1].bindings


def test_result_reference_cannot_be_target_even_if_value_is_a_trusted_id():
    q1, q2 = "Find file with id A", "Read this file"
    nodes = [find("find", "file", "id", "A", q1), action("read", "read_object", q2,
             {"object_id": binding("find", "file", q2, kind="result_ref")})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "unsupported"
    assert result.diagnostics[0]["repairable"] is False


def test_join_cannot_invent_a_relation_absent_from_the_task_evidence():
    q1, q2 = "Find project with id P", "Find contact internal true"
    query = selector("contact", "internal", True, q2)
    query["join"] = {"from_action": "project", "source_field": "owner", "target_field": "email"}
    result = compile_intent(q1 + ". " + q2 + ".", [find("project", "project", "id", "P", q1),
             action("contact", "lookup_objects", q2,
                    {"kind": literal("contact", q2), "query": query})])
    assert result.status == "needs_clarification"
    assert result.diagnostics[0]["repairable"] is False


def test_mixed_trust_content_can_be_body_but_target_stays_trusted_literal():
    q1, q2 = "Read object A", "Send the read body to recipient C with source A"
    nodes = [action("read", "read_object", q1, {"object_id": literal("A", q1)}),
             action("send", "send_message", q2,
                    {"recipient_id": literal("C", q2), "source_id": literal("A", q2), "body": data("read", q2)})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "ready"
    assert result.contract.actions[-1].constraints["recipient_id"].value == "C"
    assert result.reference_plan[0]["kind"] == "data_ref"


@pytest.mark.parametrize("family,node,request_text", [
    ("retrieve_read_write", action("read", "read_object", "Read object A", {"object_id": literal("B", "Read object A")}), "Read object A"),
    ("multihop_recipient", action("send", "send_message", "Send body hi to C source P", {"recipient_id": literal("D", "Send body hi to C source P"), "source_id": literal("P", "Send body hi to C source P"), "body": literal("hi", "Send body hi to C source P")}), "Send body hi to C source P"),
    ("calendar_order", action("time", "schedule_event", "Reschedule E from S to T for 30", {"object_id": literal("E", "Reschedule E from S to T for 30"), "start_time": literal("S", "Reschedule E from S to T for 30"), "end_time": literal("T", "Reschedule E from S to T for 30"), "duration_minutes": literal(90, "Reschedule E from S to T for 30")}), "Reschedule E from S to T for 30"),
    ("prohibition_conflict", action("delete", "delete_object", "delete object A", {"object_id": literal("A", "delete object A")}), "Never delete object A"),
    ("bounded_multi_object", find("find", "folder", "id", ["F1", "F3"], "Find folder F1 or F2", many=True), "Find folder F1 or F2"),
    ("mixed_trust_content", action("read", "read_object", "Read object A", {"object_id": {"kind": "data_ref", "from_action": "read", "field": "body", "evidence": evidence("Read object A")}}), "Read object A"),
    ("predefined_branch", action("read", "read_object", "Read object A", {"object_id": literal("A", "Read object A")}, when={"argument": "object_id", "field": "ready", "equals": True, "evidence": evidence("Read object A")}), "Read object A"),
    ("provenance_confidentiality", action("read", "read_object", "Read object A", {"object_id": {"kind": "literal", "value": "A", "evidence": [{"source": "untrusted_tool_output", "quote": "Read object A"}]}}), "Read object A"),
])
def test_eight_family_scope_or_structure_violations_do_not_materialize_permission(family, node, request_text):
    result = compile_intent(request_text, [node])
    assert result.status != "ready", family
    assert result.contract.static_manifest.rules == (), family


def test_selector_membership_is_finite_json_not_nan_wire_text():
    q1 = "Find file with duration_minutes nan"
    result = compile_intent(q1, [find("find", "file", "duration_minutes", [float("nan")], q1, many=True)])
    assert result.status == "technical_invalid"
    assert result.diagnostics[0]["code"] == "constraint_type_mismatch"


def test_duration_derivation_requires_verified_backend_date_fields():
    q1 = "Find calendar_event with id E"
    q2 = "Reschedule the event using slot_start and slot_end and duration_minutes"
    nodes = [find("find", "calendar_event", "id", "E", q1),
             action("time", "schedule_event", q2,
                    {"object_id": binding("find", "calendar_event", q2),
                     "start_time": binding("find", "calendar_event", q2, field="slot_start", kind="result_ref"),
                     "end_time": binding("find", "calendar_event", q2, field="slot_end", kind="result_ref"),
                     "duration_minutes": {"kind": "derived", "operation": "duration_minutes", "from_action": "find",
                                          "fields": ["slot_start", "slot_end"], "evidence": evidence(q2)}})]
    catalog = build_trusted_tool_catalog(tool_schemas(), {"objects": {"calendar_event": ["id"]}})
    result = compile_task_intent_v4(trusted_user_request=q1 + ". " + q2 + ".", trusted_app_context={},
             tool_schemas=tool_schemas(), intent={"schema_version": INTENT_SCHEMA_VERSION, "actions": nodes}, catalog=catalog)
    assert result.status == "conflict"  # 日期result_ref已先被拒绝，不等到执行时猜日期。


def test_model_false_confirmation_flag_cannot_erase_user_requirement():
    user_text = "Delete object A only after confirmation"
    result = compile_intent(user_text, [action("delete", "delete_object", user_text,
                            {"object_id": literal("A", user_text)}, requires_confirmation=False)])
    assert result.status == "ready"
    assert result.contract.actions[0].requires_confirmation is True
    assert result.contract.static_manifest.rules[0].requires_confirmation is True


def test_model_omitted_confirmation_flag_cannot_erase_application_requirement():
    user_text = "Read object A"
    app = {"requested_actions": [{"tool": "read_object", "arguments": {"object_id": "A"},
                                  "requires_confirmation": True}]}
    result = compile_intent(user_text, [action("read", "read_object", user_text,
                            {"object_id": literal("A", user_text)})], app=app)
    assert result.status == "ready"
    assert result.contract.actions[0].requires_confirmation is True


def test_model_omission_does_not_erase_user_target_prohibition():
    q1, q2, q3 = "Find folder with id F1 or F2", "Delete these folders", "Never delete object F1"
    nodes = [find("find", "folder", "id", ["F1", "F2"], q1, many=True),
             action("delete", "delete_object", q2, {"object_id": binding("find", "folder", q2, many=True)})]
    result = compile_intent(". ".join((q1, q2, q3)) + ".", nodes)
    assert result.status == "ready"
    assert len(result.contract.prohibitions) == 1
    assert result.contract.prohibitions[0].constraints["object_id"].value == "F1"


def test_unexpressed_qualified_user_prohibition_is_clarification_not_ignored():
    q1, q2 = "Read object A", "Never delete records outside approved range"
    result = compile_intent(q1 + ". " + q2 + ".", [action("read", "read_object", q1, {"object_id": literal("A", q1)})])
    assert result.status == "needs_clarification"
    assert result.diagnostics[0]["repairable"] is False


def test_returned_iteration_order_is_trusted_sidecar_not_model_flag():
    q1, q2 = "Find folder with id F1 or F2", "Delete these folders in returned order"
    nodes = [find("find", "folder", "id", ["F1", "F2"], q1, many=True),
             action("delete", "delete_object", q2, {"object_id": binding("find", "folder", q2, many=True)})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "ready"
    assert result.reference_plan[-1]["iteration_order"] is True


@pytest.mark.parametrize("prefix", ["If ready", "If score >= 90"])
def test_model_cannot_omit_user_condition_and_materialize_unconditional_effect(prefix):
    q1 = "Find approval_record with id A"
    q2 = prefix + ", update object A body to approved; otherwise do not tag"
    nodes = [find("find", "approval_record", "id", "A", q1),
             action("tag", "update_object", "update object A body to approved",
                    {"object_id": binding("find", "approval_record", "update object A body to approved"),
                     "field": literal("body", "update object A body to approved"),
                     "value": literal("approved", "update object A body to approved")})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "needs_clarification"
    assert result.diagnostics[0]["code"] == "missing_user_condition_scope"
    assert result.diagnostics[0]["repairable"] is False


def test_model_cannot_omit_explicit_then_dependency_for_independent_target():
    q1, q2 = "Read object A", "Then delete object B"
    nodes = [action("read", "read_object", q1, {"object_id": literal("A", q1)}),
             action("delete", "delete_object", q2, {"object_id": literal("B", q2)})]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "needs_clarification"
    assert result.diagnostics[0]["code"] == "missing_user_order_dependency"
    assert result.diagnostics[0]["repairable"] is False


def test_explicit_then_order_is_ready_when_the_actual_dependency_is_present():
    q1, q2 = "Read object A", "Then delete object B"
    nodes = [action("read", "read_object", q1, {"object_id": literal("A", q1)}),
             action("delete", "delete_object", q2, {"object_id": literal("B", q2)}, after=["read"])]
    result = compile_intent(q1 + ". " + q2 + ".", nodes)
    assert result.status == "ready"
    assert result.contract.actions[-1].depends_on == ("read",)
