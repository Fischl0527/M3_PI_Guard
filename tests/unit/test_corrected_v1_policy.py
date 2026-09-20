from dataclasses import replace

import pytest

from experiments.paper_v2.confirmation_session_v1 import ConfirmationSession
from m3_core.policy_compiler import compile_task_policy
from m3_core.policy_compiler_corrected_v1 import (
    compile_generic_task_policy_corrected_v1,
    compile_task_policy_corrected_v1,
)
from m3_guard.provenance import infer_argument_provenance
from m3_guard.runtime_monitor import (
    ActionProposal,
    FULL_RUNTIME_MODULES,
    evaluate_action,
)
from m3_guard.runtime_monitor_corrected_v1 import (
    RuntimeMonitorCorrectedV1,
    evaluate_action_corrected_v1,
)
from m3_guard.task_policy import (
    DataFlowConstraint,
    ParameterConstraint,
    TaskPolicyManifest,
    ToolRule,
)


def proposal(tool, args, *, request="", untrusted="", labels=None):
    return ActionProposal(
        "p",
        tool,
        args,
        infer_argument_provenance(
            proposal_id="p",
            tool=tool,
            arguments=args,
            trusted_user_request=request,
            untrusted_document=untrusted,
            labelled_values=labels,
        ),
    )


def manifest(*rules, **kwargs):
    return TaskPolicyManifest(
        "m", ("trusted_user_request",), "r", "s", tuple(rules), **kwargs
    )


def scope(rule_id, target, **kwargs):
    return ToolRule(
        rule_id, "send_email", {"to": ParameterConstraint("exact", target)}, **kwargs
    )


@pytest.mark.parametrize(
    "trusted_request",
    [
        "Read public/input.txt, then write the summary to public/output.txt.",
        "Write public/output.txt, then read public/input.txt.",
        "读取public/input.txt，然后写入public/output.txt。",
    ],
)
def test_action_resource_binding(trusted_request):
    result = compile_task_policy_corrected_v1(trusted_user_request=trusted_request)
    assert {
        (rule.tool, rule.argument_constraints["path"].value) for rule in result.rules
    } == {
        ("read_file", "sandbox/public/input.txt"),
        ("write_file", "sandbox/public/output.txt"),
    }


def test_two_reads_and_explicit_shared_read_write():
    result = compile_task_policy_corrected_v1(
        trusted_user_request="Read public/a.txt and public/b.txt then write public/c.txt"
    )
    assert [rule.tool for rule in result.rules] == [
        "read_file",
        "read_file",
        "write_file",
    ]
    shared = compile_task_policy_corrected_v1(
        trusted_user_request="Read and write public/a.txt"
    )
    assert {rule.tool for rule in shared.rules} == {"read_file", "write_file"}


@pytest.mark.parametrize(
    "trusted_request",
    [
        "Do not write public/a.txt",
        "Never write public/a.txt",
        "不要写入public/a.txt",
        "Read public/a.txt; do not write public/b.txt",
        "Save the summary somewhere",
    ],
)
def test_negative_or_unknown_write_target_does_not_grant_write(trusted_request):
    assert "write_file" not in {
        rule.tool
        for rule in compile_task_policy_corrected_v1(
            trusted_user_request=trusted_request
        ).rules
    }


def test_explicit_actions_replace_all_inferred_permissions():
    result = compile_task_policy_corrected_v1(
        trusted_user_request="Read public/a.txt then write public/b.txt",
        trusted_app_context={
            "requested_actions": [
                {"tool": "read_file", "arguments": {"path": "sandbox/public/c.txt"}}
            ]
        },
    )
    assert len(result.rules) == 1
    assert result.rules[0].argument_constraints["path"].value == "sandbox/public/c.txt"
    assert not compile_task_policy_corrected_v1(
        trusted_user_request="Write public/a.txt",
        trusted_app_context={"requested_actions": []},
    ).rules


def test_negative_declaration_conflict_and_evaluator_fields_rejected():
    with pytest.raises(ValueError, match="conflicts"):
        compile_task_policy_corrected_v1(
            trusted_user_request="Do not write public/a.txt",
            trusted_app_context={
                "requested_actions": [
                    {
                        "tool": "write_file",
                        "arguments": {"path": "sandbox/public/a.txt"},
                    }
                ]
            },
        )
    with pytest.raises(ValueError, match="evaluator/gold"):
        compile_task_policy_corrected_v1(
            trusted_user_request="Read public/a.txt",
            trusted_app_context={"nested": {"gold": "a"}},
        )


@pytest.mark.parametrize(
    "trusted_request",
    [
        "Maybe write public/a.txt",
        "If needed write public/a.txt",
        "Write public/a.txt or public/b.txt",
        "可能写入public/a.txt",
        "Write public/a.txt if needed",
        "Write public/a.txt unless the request is cancelled",
        "写入public/a.txt（如果需要）",
    ],
)
def test_ambiguous_or_conditional_target_does_not_receive_grant(trusted_request):
    assert not compile_task_policy_corrected_v1(
        trusted_user_request=trusted_request
    ).rules


@pytest.mark.parametrize(
    "trusted_request",
    [
        "Write public/a.txt, not public/b.txt",
        "Write public/a.txt, never public/b.txt; read public/c.txt",
        "Write public/b.txt is not allowed",
        "Read and write public/a.txt, not public/b.txt",
        "写入public/a.txt，不要public/b.txt",
    ],
)
def test_post_action_denial_does_not_authorize_forbidden_resource(trusted_request):
    result = compile_task_policy_corrected_v1(trusted_user_request=trusted_request)
    assert not any(
        rule.argument_constraints.get("path")
        and rule.argument_constraints["path"].value == "sandbox/public/b.txt"
        for rule in result.rules
    )


def test_post_action_denial_rejects_conflicting_explicit_declaration():
    with pytest.raises(ValueError, match="conflicts"):
        compile_task_policy_corrected_v1(
            trusted_user_request="Write public/a.txt, not public/b.txt",
            trusted_app_context={
                "requested_actions": [
                    {"tool": "write_file", "arguments": {"path": "public/b.txt"}}
                ]
            },
        )


@pytest.mark.parametrize(
    "trusted_request,expected",
    [
        ("Read public/a.txt, do not write public/b.txt", {("read_file", "a.txt")}),
        ("Write public/if-needed.txt", {("write_file", "if-needed.txt")}),
        (
            "Write public/not.txt then read public/b.txt",
            {("write_file", "not.txt"), ("read_file", "b.txt")},
        ),
    ],
)
def test_modifiers_do_not_hide_other_actions_or_resource_names(
    trusted_request, expected
):
    result = compile_task_policy_corrected_v1(trusted_user_request=trusted_request)
    assert {
        (rule.tool, rule.argument_constraints["path"].value.rsplit("/", 1)[-1])
        for rule in result.rules
    } == expected


def test_coordinated_negative_does_not_grant_second_action():
    result = compile_task_policy_corrected_v1(
        trusted_user_request="Do not read public/a.txt and write public/b.txt"
    )
    assert not result.rules
    independent = compile_task_policy_corrected_v1(
        trusted_user_request="Do not read public/a.txt. Write public/b.txt"
    )
    assert [rule.tool for rule in independent.rules] == ["write_file"]


def test_generic_explicit_actions_are_not_silently_ignored():
    result = compile_generic_task_policy_corrected_v1(
        trusted_user_request="Search messages",
        tool_schemas={"search": {"arguments": {"query": {"type": "string"}}}},
        trusted_app_context={"requested_actions": []},
    )
    assert not result.rules


def test_second_rule_allowed_without_rewriting_historical_behavior():
    policy = manifest(
        scope("first", "a@example.test"), scope("second", "b@example.test")
    )
    action = proposal("send_email", {"to": "b@example.test"}, request="b@example.test")
    assert evaluate_action(action, policy).decision == "ASK"
    assert evaluate_action_corrected_v1(action, policy).decision == "ALLOW"
    assert (
        evaluate_action_corrected_v1(
            proposal("send_email", {"to": "c@example.test"}), policy
        ).decision
        == "ASK"
    )
    old = compile_task_policy(
        trusted_user_request="Read public/a.txt then write public/b.txt"
    )
    assert {rule.tool for rule in old.rules} == {"write_file"}


def test_parameter_fragments_cannot_be_combined():
    rules = tuple(
        ToolRule(
            str(i),
            "send_email",
            {
                "to": ParameterConstraint("exact", target),
                "subject": ParameterConstraint("exact", subject),
            },
        )
        for i, (target, subject) in enumerate(
            (("a@example.test", "one"), ("b@example.test", "two"))
        )
    )
    assert (
        evaluate_action_corrected_v1(
            proposal("send_email", {"to": "a@example.test", "subject": "two"}),
            manifest(*rules),
        ).decision
        == "ASK"
    )


@pytest.mark.parametrize("reverse_rules", [False, True])
def test_overlap_never_weakens_confirmation_or_source_restrictions(reverse_rules):
    action = proposal("send_email", {"to": "a@example.test"}, request="a@example.test")
    strict = scope("z", "a@example.test", requires_confirmation=True)
    broad = ToolRule("a", "send_email", {"to": ParameterConstraint("type", "string")})
    rules = (strict, broad) if reverse_rules else (broad, strict)
    assert evaluate_action_corrected_v1(action, manifest(*rules)).decision == "ASK"
    source_strict = replace(
        strict,
        requires_confirmation=False,
        permitted_argument_sources=("trusted_app_context",),
    )
    rules = (source_strict, broad) if reverse_rules else (broad, source_strict)
    assert evaluate_action_corrected_v1(action, manifest(*rules)).decision == "ASK"


def test_global_dataflow_and_untrusted_target_cannot_be_bypassed():
    policy = manifest(
        scope("a", "a@example.test"),
        scope("b", "b@example.test"),
        dataflow_constraints=(
            DataFlowConstraint(
                "no-private-email", "private", forbidden_tools=("send_email",)
            ),
        ),
    )
    action = proposal(
        "send_email",
        {"to": "b@example.test", "body": "PRIVATE"},
        request="b@example.test",
        labels={"private": ("PRIVATE",)},
    )
    assert evaluate_action_corrected_v1(action, policy).decision == "DENY"
    assert (
        evaluate_action_corrected_v1(
            action, policy, modules=frozenset({"policy"})
        ).decision
        == "ALLOW"
    )
    injected = proposal(
        "send_email", {"to": "b@example.test"}, untrusted="b@example.test"
    )
    assert evaluate_action_corrected_v1(injected, policy).decision == "DENY"


def test_confirmation_preserves_history_and_one_shot_binding():
    policy = compile_task_policy_corrected_v1(
        trusted_user_request="Read public/a.txt then write public/b.txt"
    )
    policy = replace(
        policy,
        rules=tuple(
            replace(rule, requires_confirmation=True)
            if rule.tool == "write_file"
            else rule
            for rule in policy.rules
        ),
        manifest_sha256="",
    )
    monitor = RuntimeMonitorCorrectedV1(policy)
    read = proposal("read_file", {"path": "sandbox/public/a.txt"})
    monitor.record_execution(read, monitor.decide(read))
    write = proposal("write_file", {"path": "sandbox/public/b.txt", "content": "ok"})
    broker = ConfirmationSession(clock=lambda: 100.0)
    ticket = broker.request(
        task_id="t",
        request_digest="r",
        proposal=write,
        manifest=policy,
        modules=FULL_RUNTIME_MODULES,
        monitor=monitor,
    )
    assert ticket.status == "awaiting_confirmation"
    assert monitor.executed_tools == ("read_file",)
    assert (
        broker.controller_respond(ticket.ticket_id, vote="approved").status
        == "approved"
    )
    params = dict(task_id="t", request_digest="r", proposal=write, manifest=policy)
    assert (
        broker.consume(ticket.ticket_id, **params).status
        == "allow_simulated_effect_once"
    )
    assert broker.consume(ticket.ticket_id, **params).status == "replay_rejected"
    wrong = RuntimeMonitorCorrectedV1(replace(policy, version=2, manifest_sha256=""))
    with pytest.raises(ValueError, match="binding mismatch"):
        broker.request(
            task_id="t",
            request_digest="r",
            proposal=write,
            manifest=policy,
            modules=FULL_RUNTIME_MODULES,
            monitor=wrong,
        )
