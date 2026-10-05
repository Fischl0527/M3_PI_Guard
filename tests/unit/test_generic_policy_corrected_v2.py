"""Focused regressions for ambiguous prose being mistaken for a literal."""
from types import SimpleNamespace

import pytest

from m3_core.policy_compiler_corrected_v1 import compile_generic_task_policy_corrected_v1
from m3_core.policy_compiler_corrected_v2 import compile_generic_task_policy_corrected_v2


SCHEMAS = {
    "send_message": {
        "description": "Send a message with content to a channel",
        "side_effect": True,
        "arguments": {
            "channel": {"type": "string", "required": True},
            "content": {"type": "string", "required": True},
        },
    },
}


def compile_request(request, context=None):
    return compile_generic_task_policy_corrected_v2(
        trusted_user_request=request, tool_schemas=SCHEMAS,
        trusted_app_context=context, generated_at="2026-09-20T00:00:00Z",
    )


def test_connective_is_not_an_exact_argument_and_does_not_widen_automatic_permission():
    request = "Send a message to the channel and include the content of the document."
    old = compile_generic_task_policy_corrected_v1(
        trusted_user_request=request, tool_schemas=SCHEMAS,
    )
    assert old.rules[0].argument_constraints["channel"].value == "and"
    assert old.rules[0].argument_constraints["content"].value == "of"
    new = compile_request(request)
    assert new.rules == ()  # Unknown channel is not a type-only automatic grant.


def test_quoted_full_values_keep_spaces_and_stopwords():
    new = compile_request('Send a message: channel="and", content="of the two choices".')
    assert new.rules[0].argument_constraints["channel"].value == "and"
    assert new.rules[0].argument_constraints["content"].value == "of the two choices"


def test_ambiguous_unquoted_multitoken_assignment_requires_confirmation():
    new = compile_request("Send a message: channel is the chosen channel; content is the summary.")
    assert new.rules == ()


def test_explicit_machine_delimited_single_values_remain_exact():
    new = compile_request("Send a message: channel=general; content=hello.")
    assert new.rules[0].argument_constraints["channel"].value == "general"
    assert new.rules[0].argument_constraints["content"].value == "hello"


def test_trusted_structured_declarations_remain_unchanged():
    context = {"requested_actions": [{"tool": "send_message", "arguments": {
        "channel": "and", "content": "of the two choices",
    }}]}
    old = compile_generic_task_policy_corrected_v1(
        trusted_user_request="Send a message.", tool_schemas=SCHEMAS,
        trusted_app_context=context, generated_at="2026-09-20T00:00:00Z",
    )
    new = compile_request("Send a message.", context)
    assert new.to_dict() == old.to_dict()


def test_runtime_injection_is_explicit_and_unknown_revision_is_rejected():
    from experiments.paper_v2.correctness_runtime_v1 import compile_manifest

    context = SimpleNamespace(benchmark="agentdojo-v1")
    view = SimpleNamespace(
        trusted_user_request="Send a message to the channel and include the content of the document.",
        trusted_app_context={},
    )
    old = compile_manifest(context, view, SCHEMAS)
    new = compile_manifest(context, view, SCHEMAS, compiler_revision="corrected_v2")
    assert old.rules[0].argument_constraints["channel"].value == "and"
    assert new.rules == ()
    with pytest.raises(ValueError, match="unknown corrected compiler"):
        compile_manifest(context, view, SCHEMAS, compiler_revision="unrecognized")


def test_projection_and_runtime_compile_use_the_same_explicit_revision(monkeypatch):
    from experiments.paper_v2 import correctness_runtime_v1 as runtime

    request = "Send a message to the channel and include the content of the document."
    monkeypatch.setattr(runtime, "_read_source_record", lambda _: {})
    monkeypatch.setattr(runtime, "_source_projection", lambda *_: {
        "trusted_user_request": request, "trusted_app_context": {},
        "untrusted_content": "", "untrusted_memory": [],
    })
    monkeypatch.setattr(runtime, "_runtime_inputs", lambda *_: (request, {}, SCHEMAS))
    item = {
        "source_reference": {"path": "fixture", "line": 1, "sha256": "fixture"},
        "benchmark": "agentdojo-v1", "case_id": "fixture", "condition_id": "m3_full",
    }
    state, digest = runtime.hydrate(item, compiler_revision="corrected_v2")
    manifest = runtime.compile_manifest(
        SimpleNamespace(benchmark="agentdojo-v1"),
        SimpleNamespace(trusted_user_request=request, trusted_app_context={}), SCHEMAS,
        compiler_revision="corrected_v2",
    )
    assert state["runtime_control"]["authorization"]["manifest"] == manifest.to_dict()
    assert digest["forbidden_fields_present"] is False
