"""新版本契约的公开编译接口；不修改历史策略或实验。"""

from m3_core.policy_compiler_corrected_v3 import compile_task_contract_v1
import pytest


SCHEMAS = {
    "read_object": {"arguments": {"object_id": {"type": "string", "required": True}}, "side_effect": False},
    "update_object": {
        "arguments": {
            "object_id": {"type": "string", "required": True},
            "field": {"type": "string", "required": True},
            "value": {"type": "string", "required": True},
        },
        "side_effect": True,
    },
}


def test_action_scoped_targets_remain_distinct():
    request = "Read A then update B field status to ready."
    draft = {
        "schema_version": "m3-task-contract-draft-1.0",
        "actions": [
            {
                "action_id": "read_a", "tool": "read_object", "role": "read",
                "constraints": {"object_id": {"op": "eq", "value": "A"}},
                "argument_roles": {"object_id": "target"},
                "evidence": [{"quote": "Read A"}],
            },
            {
                "action_id": "update_b", "tool": "update_object", "role": "modify",
                "constraints": {
                    "object_id": {"op": "eq", "value": "B"},
                    "field": {"op": "eq", "value": "status"},
                    "value": {"op": "eq", "value": "ready"},
                },
                "argument_roles": {"object_id": "target", "field": "target", "value": "value"},
                "evidence": [{"quote": "update B field status to ready"}],
                "depends_on": ["read_a"],
            },
        ],
        "prohibitions": [],
    }
    contract = compile_task_contract_v1(trusted_user_request=request, tool_schemas=SCHEMAS, draft=draft)
    assert contract.status == "ready"
    assert contract.actions[0].constraints["object_id"].value == "A"
    assert contract.actions[1].constraints["object_id"].value == "B"
    assert contract.to_dict()["schema_version"] == "m3-task-contract-1.0"


def update_draft(request="Update B field status to ready."):
    return {
        "schema_version": "m3-task-contract-draft-1.0", "prohibitions": [],
        "actions": [{"action_id": "update_b", "tool": "update_object", "role": "modify",
                     "constraints": {"object_id": {"op": "eq", "value": "B"},
                                     "field": {"op": "eq", "value": "status"},
                                     "value": {"op": "eq", "value": "ready"}},
                     "evidence": [{"quote": request}]}],
    }


def test_omitted_negative_instruction_is_enforced_independently():
    request = "Update B field status to ready. Do not update B."
    contract = compile_task_contract_v1(trusted_user_request=request, tool_schemas=SCHEMAS,
                                      draft=update_draft())
    assert contract.status == "conflict"
    assert contract.static_manifest.rules == ()


def test_model_cannot_invent_a_target_not_in_original_evidence():
    draft = update_draft()
    draft["actions"][0]["constraints"]["object_id"]["value"] = "attacker-object"
    contract = compile_task_contract_v1(trusted_user_request="Update B field status to ready.",
                                      tool_schemas=SCHEMAS, draft=draft)
    assert contract.status != "ready"


@pytest.mark.parametrize("mutation", ["hidden_type", "cycle", "gold"])
def test_nested_bypasses_and_dependencies_fail_closed(mutation):
    draft = update_draft()
    node = draft["actions"][0]
    if mutation == "hidden_type":
        node["constraints"]["object_id"] = {"op": "and", "items": [{"op": "type", "value": "string"}]}
    elif mutation == "cycle":
        node["depends_on"] = ["update_b"]
    else:
        node["bindings"] = {"gold_target": {"value": "B"}}
    contract = compile_task_contract_v1(trusted_user_request="Update B field status to ready.",
                                      tool_schemas=SCHEMAS, draft=draft)
    assert contract.status != "ready"


@pytest.mark.parametrize("mutation", ["role", "operation", "irrelevant_quote", "unknown_op", "unknown_field", "nonfinite", "empty_set", "unknown_dependency"])
def test_invalid_or_misattributed_model_drafts_never_grant(mutation):
    draft = update_draft()
    node = draft["actions"][0]
    request = "Read A. Update B field status to ready."
    if mutation == "role":
        node["argument_roles"] = {"object_id": "content"}
    elif mutation == "operation":
        node["role"] = "read"
    elif mutation == "irrelevant_quote":
        node["evidence"] = [{"quote": "Read A"}]
    elif mutation == "unknown_op":
        node["constraints"]["object_id"] = {"op": "exec", "value": "B"}
    elif mutation == "unknown_field":
        node["trusted"] = True
    elif mutation == "nonfinite":
        node["constraints"]["object_id"] = {"op": "eq", "value": float("nan")}
    elif mutation == "empty_set":
        node["constraints"]["object_id"] = {"op": "in", "values": []}
    else:
        node["depends_on"] = ["missing"]
    compiled = compile_task_contract_v1(trusted_user_request=request, tool_schemas=SCHEMAS, draft=draft)
    assert compiled.status != "ready"
    assert compiled.static_manifest.rules == ()


def test_duplicate_json_and_untrusted_evaluator_input_are_rejected():
    contract = compile_task_contract_v1(trusted_user_request="Read A", tool_schemas=SCHEMAS,
                                      draft='{"actions": [], "actions": [], "schema_version": "m3-task-contract-draft-1.0"}')
    assert contract.diagnostics[0].code == "duplicate_json_key"
    with pytest.raises(ValueError, match="evaluator/gold"):
        compile_task_contract_v1(trusted_user_request="Read A", tool_schemas=SCHEMAS,
                                 draft=update_draft(), trusted_app_context={"gold_target": "A"})


def test_generated_update_content_is_not_permission_to_modify_security_attributes():
    schemas = dict(SCHEMAS)
    schemas["update_object"] = {**schemas["update_object"],
                                "argument_roles": {"object_id": "target", "field": "value", "value": "content"},
                                "generated_for_fields": ["body"],
                                "arguments": {**schemas["update_object"]["arguments"], "value": {"type": "string", "required": True, "allow_generated": True}}}
    draft = update_draft("Update B field owner to alice.")
    draft["actions"][0]["constraints"]["field"]["value"] = "owner"
    draft["actions"][0]["constraints"]["value"] = {"op": "type", "value": "string"}
    compiled = compile_task_contract_v1(trusted_user_request="Update B field owner to alice.", tool_schemas=schemas, draft=draft)
    assert compiled.status != "ready"


def test_routing_metadata_is_not_an_application_authorization_declaration():
    draft = update_draft()
    draft["actions"][0]["constraints"]["object_id"]["value"] = "routing-only-id"
    compiled = compile_task_contract_v1(trusted_user_request="Update B field status to ready.",
                                      tool_schemas=SCHEMAS, draft=draft,
                                      trusted_app_context={"user_task_id": "routing-only-id"})
    assert compiled.status != "ready"


def test_application_prohibited_tools_do_not_depend_on_model_prohibitions():
    compiled = compile_task_contract_v1(trusted_user_request="Update B field status to ready.",
                                      tool_schemas=SCHEMAS, draft=update_draft(),
                                      trusted_app_context={"hard_constraints": {"prohibited_tools": ["update_object"]}})
    assert compiled.status == "conflict"
    assert compiled.static_manifest.rules == ()
