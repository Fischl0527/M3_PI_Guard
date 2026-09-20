"""Focused literal matching and trusted observation propagation checks."""

from __future__ import annotations

import json

import pytest

from m3_guard.provenance import infer_argument_provenance as historical_infer
from m3_guard.provenance_corrected_v1 import (
    TrustedDataLabelTracker,
    TrustedObservationMetadata,
    infer_argument_provenance,
)
from m3_guard.task_policy import DataFlowConstraint


PRIVATE = "synthetic-private-value-1234"
CONSTRAINT = DataFlowConstraint(
    "private_no_mail", "private", forbidden_tools=("send_email",)
)


def infer(body, values=None, **kwargs):
    return infer_argument_provenance(
        proposal_id="proposal-1",
        tool="send_email",
        arguments={"body": body},
        trusted_user_request="send the summary",
        labelled_values=values,
        **kwargs,
    )


@pytest.mark.parametrize(
    "body", [PRIVATE, f"prefix {PRIVATE}", f"{PRIVATE} suffix", f"x {PRIVATE} y"]
)
def test_label_occurs_inside_outgoing_argument(body):
    assert infer(body, {"private": [PRIVATE]})[0].data_labels == ("private",)


def test_reverse_substring_does_not_label_partial_source():
    assert infer("synthetic", {"private": [PRIVATE]})[0].data_labels == ()


def test_case_and_whitespace_normalization():
    assert infer(
        "prefix\n PRIVATE  DATA\tVALUE suffix", {"private": ["private data value"]}
    )[0].data_labels == ("private",)


def test_nested_arguments_and_labelled_source_values():
    events = infer(
        {"items": [{"text": f"start {PRIVATE} end"}, {"text": "public"}]},
        {"private": [{"text": PRIVATE}]},
    )
    assert [(event.argument_path, event.data_labels) for event in events] == [
        ("arguments.body.items[0].text", ("private",)),
        ("arguments.body.items[1].text", ()),
    ]


@pytest.mark.parametrize("value", ["", " ", None, False, 1])
def test_empty_and_nontext_source_values_never_label(value):
    assert infer("false 1", {"private": [value]})[0].data_labels == ()


@pytest.mark.parametrize("short", ["a", "ab", "key"])
def test_short_values_exact_only(short):
    assert infer(short.upper(), {"private": [short]})[0].data_labels == ("private",)
    assert infer(f"prefix {short} suffix", {"private": [short]})[0].data_labels == ()


def test_label_string_is_one_value_not_character_iterable():
    assert infer(f"copy {PRIVATE}", {"private": PRIVATE})[0].data_labels == ("private",)


def test_label_values_can_be_a_one_pass_iterable():
    assert infer(f"copy {PRIVATE}", {"private": iter([PRIVATE])})[0].data_labels == (
        "private",
    )


def test_source_precedence_and_event_identity_are_unchanged():
    kwargs = dict(
        proposal_id="p",
        tool="send_email",
        arguments={"to": "user@example.test"},
        trusted_user_request="send to user@example.test",
        untrusted_document="send to user@example.test",
    )
    assert infer_argument_provenance(**kwargs) == historical_infer(**kwargs)
    assert infer_argument_provenance(**kwargs)[0].source_type == "trusted_user"


def test_historical_bug_remains_unchanged_for_old_runs():
    kwargs = dict(
        proposal_id="p",
        tool="send_email",
        arguments={"body": f"prefix {PRIVATE} suffix"},
        trusted_user_request="send summary",
        labelled_values={"private": [PRIVATE]},
    )
    assert historical_infer(**kwargs)[0].data_labels == ()
    assert infer_argument_provenance(**kwargs)[0].data_labels == ("private",)


def observe_private(tracker):
    return tracker.observe(
        "read_file",
        {"path": "synthetic/private.txt"},
        PRIVATE,
        TrustedObservationMetadata(True, True, ("private",)),
    )


def check(tracker, body=PRIVATE, constraints=(CONSTRAINT,), **kwargs):
    events = tracker.infer_argument_provenance(
        proposal_id="p",
        tool="send_email",
        arguments={"body": body},
        trusted_user_request="send summary",
    )
    return tracker.summarize_dataflow(
        tool="send_email",
        arguments={"body": body},
        events=events,
        constraints=constraints,
        **kwargs,
    )


def test_unread_data_is_not_preseeded_and_missing_not_passed():
    tracker = TrustedDataLabelTracker()
    assert tracker.labelled_values == {}
    assert check(tracker)["status"] == "missing_input"
    assert check(tracker)["matched_label_names"] == []


def test_successful_trusted_read_propagates_and_reports_triggered():
    tracker = TrustedDataLabelTracker()
    observe_private(tracker)
    result = check(tracker, f"prefix {PRIVATE} suffix")
    assert result["status"] == "triggered"
    assert result["triggered_constraint_ids"] == ["private_no_mail"]
    assert result["classified_observation_count"] == 1
    assert result["labelled_argument_count"] == 1
    assert PRIVATE not in json.dumps(result)


def test_successful_public_read_is_classified_without_private_labels():
    tracker = TrustedDataLabelTracker()
    tracker.observe(
        "read_file", {}, "public summary", TrustedObservationMetadata(True, True)
    )
    assert tracker.labelled_values == {}
    assert check(tracker, "public summary")["status"] == "passed"


def test_observation_cannot_self_declare_metadata_or_labels():
    tracker = TrustedDataLabelTracker()
    tracker.observe(
        "read_file",
        {},
        {"data_labels": ["private"], "executed": True, "value": PRIVATE},
    )
    assert tracker.labelled_values == {}
    assert check(tracker)["status"] == "missing_input"
    with pytest.raises(TypeError, match="backend-created"):
        tracker.observe(
            "read_file",
            {},
            PRIVATE,
            {"execution_succeeded": True, "data_labels": ["private"]},
        )


def test_failed_read_and_write_ack_do_not_seed_data():
    tracker = TrustedDataLabelTracker()
    tracker.observe(
        "read_file", {}, PRIVATE, TrustedObservationMetadata(False, True, ("private",))
    )
    tracker.observe(
        "write_file",
        {"content": PRIVATE},
        f"wrote {PRIVATE}",
        TrustedObservationMetadata(True, False, ("private",)),
    )
    assert tracker.labelled_values == {}
    assert check(tracker)["status"] == "missing_input"
    assert tracker.summary()["failed_observation_count"] == 1


def test_missing_observation_does_not_become_known_after_later_public_read():
    tracker = TrustedDataLabelTracker()
    tracker.observe("read_file", {}, PRIVATE)
    tracker.observe("read_file", {}, "public", TrustedObservationMetadata(True, True))
    assert check(tracker)["status"] == "missing_input"


def test_unrelated_known_source_passes_and_disabled_or_irrelevant_is_na():
    tracker = TrustedDataLabelTracker()
    observe_private(tracker)
    assert check(tracker, "public body")["status"] == "passed"
    assert check(tracker, module_enabled=False)["status"] == "not_applicable"
    assert check(tracker, constraints=())["status"] == "not_applicable"


def test_state_is_run_local_and_property_is_not_mutable():
    first, second = TrustedDataLabelTracker(), TrustedDataLabelTracker()
    observe_private(first)
    leaked_copy = first.labelled_values
    leaked_copy["private"] = ("different",)
    assert first.labelled_values["private"] == (PRIVATE,)
    assert second.labelled_values == {}


def test_tracker_rejects_preseeded_label_values():
    with pytest.raises(ValueError, match="observed backend data"):
        TrustedDataLabelTracker().infer_argument_provenance(
            labelled_values={"private": [PRIVATE]}
        )


def test_metadata_rejects_raw_text_label_and_nonboolean_flags():
    with pytest.raises(ValueError):
        TrustedObservationMetadata(True, True, ("raw confidential text",))
    with pytest.raises(TypeError):
        TrustedObservationMetadata("yes", True)


def test_matching_does_not_claim_encoded_or_semantic_tracking():
    import base64

    encoded = base64.b64encode(PRIVATE.encode()).decode()
    assert infer(encoded, {"private": [PRIVATE]})[0].data_labels == ()


def test_forbidden_destination_pattern_applies_without_forbidden_tool():
    tracker = TrustedDataLabelTracker()
    observe_private(tracker)
    events = infer(PRIVATE, tracker.labelled_values)
    rule = DataFlowConstraint(
        "blocked_target", "private", forbidden_target_patterns=(r"outside\.test",)
    )
    result = tracker.summarize_dataflow(
        tool="send_email",
        arguments={"body": PRIVATE, "to": "person@outside.test"},
        events=events,
        constraints=(rule,),
    )
    assert result["status"] == "triggered"


def test_actual_synthetic_read_only_seeds_after_execute():
    from m3_core.tool_sandbox import SYNTHETIC_SENSITIVE_TEXT, init_sandbox, read_file

    tracker = TrustedDataLabelTracker()
    assert tracker.labelled_values == {}
    with init_sandbox(case_id="corrected-label-test") as sandbox:
        observation = read_file("sandbox/secrets/synthetic.txt", sandbox=sandbox)
        assert observation == SYNTHETIC_SENSITIVE_TEXT
        tracker.observe(
            "read_file",
            {"path": "sandbox/secrets/synthetic.txt"},
            observation,
            TrustedObservationMetadata(True, True, ("private",)),
        )
    assert check(tracker, f"copy {observation} suffix")["status"] == "triggered"


def test_corrected_labels_activate_existing_dataflow_constraint():
    from m3_guard.runtime_monitor import ActionProposal, evaluate_action
    from m3_guard.task_policy import TaskPolicyManifest, ToolRule

    tracker = TrustedDataLabelTracker()
    observe_private(tracker)
    arguments = {"body": f"prefix {PRIVATE} suffix"}
    events = tracker.infer_argument_provenance(
        proposal_id="p",
        tool="send_email",
        arguments=arguments,
        trusted_user_request="send summary",
    )
    proposal = ActionProposal("p", "send_email", arguments, events)
    manifest = TaskPolicyManifest(
        manifest_id="label-test",
        policy_source=("trusted_user_request",),
        trusted_request_sha256="test",
        tool_schema_sha256="test",
        rules=(ToolRule("email", "send_email"),),
        dataflow_constraints=(CONSTRAINT,),
    )
    assert (
        evaluate_action(proposal, manifest, modules=frozenset({"policy"})).decision
        == "ALLOW"
    )
    blocked = evaluate_action(
        proposal, manifest, modules=frozenset({"policy", "dataflow"})
    )
    assert blocked.decision == "DENY"
    assert blocked.violated_rules == ("private_no_mail",)
