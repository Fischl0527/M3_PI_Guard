from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.paper_v2.formal_condition_executors import (
    CONDITION_PROFILES,
    DEFAULT_OUTPUT,
    FORBIDDEN_RUNTIME_CONTEXT_FIELDS,
    ConditionExecutorShell,
    FormalConditionExecutorError,
    OnlineExecutorContext,
    build_condition_dispatcher,
    build_condition_executor_qualification,
    reduce_first_proposal,
    sanitize_runtime_event,
    sanitize_runtime_events,
)
from experiments.paper_v2.medium_runtime import (
    CORE_CONDITIONS,
    DEFAULT_V2_PLAN,
    reconstruct_initial_online_state,
)


def _items() -> list[dict]:
    return [
        json.loads(line)
        for line in DEFAULT_V2_PLAN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _representative(condition: str = "m3_full", benchmark: str = "m3-v2"):
    return next(
        item
        for item in _items()
        if item["condition_id"] == condition
        and item["benchmark"] == benchmark
    )


def _raw_event(**overrides):
    event = {
        "step": 1,
        "parse_ok": True,
        "parse_error_code": None,
        "tool": "send_email",
        "arguments": {
            "to": "audit@example.test",
            "body": "synthetic public body",
        },
        "decision": "ASK",
        "reason_code": "independent_confirmation_required",
        "violated_constraints": ["confirmation"],
        "execution_attempted": False,
        "execution_succeeded": False,
        "response_text": "untrusted raw model output",
        "observation": {"guard": "ASK", "detail": "untrusted feedback"},
        "provider_receipt_sha256": "a" * 64,
    }
    event.update(overrides)
    return event


def test_sanitizer_keeps_action_evidence_but_removes_content() -> None:
    event = sanitize_runtime_event(_raw_event())
    rendered = json.dumps(event, ensure_ascii=False)

    assert event["action_proposal"]["arguments"]["to"] == "audit@example.test"
    assert event["response_text_bytes"] > 0
    assert event["observation_bytes"] > 0
    assert "untrusted raw model output" not in rendered
    assert "untrusted feedback" not in rendered
    assert "response_text" not in event
    assert "observation" not in event


def test_sanitizer_rejects_secret_shaped_argument_and_noncontiguous_steps() -> None:
    with pytest.raises(FormalConditionExecutorError, match="credential-like"):
        sanitize_runtime_event(
            _raw_event(arguments={"token": "sk-abcdefghijklmnop"})
        )
    with pytest.raises(FormalConditionExecutorError, match="contiguous"):
        sanitize_runtime_events(
            [_raw_event(), _raw_event(step=3, decision="ALLOW")]
        )


def test_first_parsed_proposal_reducer_uses_pending_ask() -> None:
    events = sanitize_runtime_events(
        [
            _raw_event(parse_ok=False, decision="DENY"),
            _raw_event(
                step=2,
                decision="ASK",
                reason_code="scope_expansion",
            ),
            _raw_event(step=3, decision="ALLOW"),
        ]
    )

    assert reduce_first_proposal(events) == {
        "initial_guard_decision": "ASK",
        "ask_reason": "scope_expansion",
        "confirmation_result": "pending",
    }


def test_all_six_profiles_match_both_frozen_benchmarks() -> None:
    assert set(CONDITION_PROFILES) == set(CORE_CONDITIONS)
    for condition in CORE_CONDITIONS:
        for benchmark in ("m3-v2", "agentdojo-v1"):
            item = _representative(condition, benchmark)
            state = reconstruct_initial_online_state(item)

            class Runtime:
                def execute(self, context, profile):
                    assert context.condition_id == condition
                    assert profile.condition_id == condition
                    assert not (
                        FORBIDDEN_RUNTIME_CONTEXT_FIELDS
                        & set(context.field_names())
                    )
                    return {
                        "events": [
                            _raw_event(
                                tool="final",
                                arguments={"answer": "SAFE"},
                                decision="ALLOW",
                                execution_attempted=True,
                                execution_succeeded=True,
                            )
                        ],
                        "operational_status": "completed",
                        "result_tier": "stub",
                    }

            class Evaluator:
                def evaluate(self, work_item, raw_trace):
                    assert "evaluation_case_type" in work_item
                    assert raw_trace["events"]
                    return {
                        "unsafe_effect": False,
                        "task_completion": False,
                    }

            result = ConditionExecutorShell(
                profile=CONDITION_PROFILES[condition],
                runtime=Runtime(),
                evaluator=Evaluator(),
            )(item, state)
            assert result["result_tier"] == "stub"
            assert result["initial_guard_decision"] == "ALLOW"


def test_runtime_cannot_mutate_frozen_online_state() -> None:
    item = _representative()
    state = reconstruct_initial_online_state(item)

    class Runtime:
        def execute(
            self,
            context: OnlineExecutorContext,
            profile,
        ):
            del profile
            context.online_state["runtime_control"]["guard_mode"] = "disabled"
            return {"events": [_raw_event()]}

    class Evaluator:
        def evaluate(self, *_):
            return {"unsafe_effect": False, "task_completion": False}

    shell = ConditionExecutorShell(
        profile=CONDITION_PROFILES["m3_full"],
        runtime=Runtime(),
        evaluator=Evaluator(),
    )
    with pytest.raises(FormalConditionExecutorError, match="mutated"):
        shell(item, state)


def test_profile_drift_and_duplicate_registry_fail_closed() -> None:
    item = _representative("no_defense")
    state = reconstruct_initial_online_state(item)
    drift = copy.deepcopy(item)
    drift["max_provider_calls"] = 16

    class Runtime:
        def execute(self, *_):
            return {"events": [_raw_event()]}

    class Evaluator:
        def evaluate(self, *_):
            return {"unsafe_effect": False, "task_completion": False}

    shell = ConditionExecutorShell(
        profile=CONDITION_PROFILES["no_defense"],
        runtime=Runtime(),
        evaluator=Evaluator(),
    )
    with pytest.raises(FormalConditionExecutorError, match="call cap"):
        shell(drift, state)

    dispatcher = build_condition_dispatcher(
        runtime=Runtime(),
        evaluator=Evaluator(),
    )
    with pytest.raises(ValueError, match="duplicate"):
        dispatcher.register("no_defense", shell)


def test_frozen_qualification_covers_twelve_pairs_without_results() -> None:
    current = build_condition_executor_qualification()
    frozen = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert current == frozen
    assert current["registered_condition_count"] == 6
    assert current["qualified_benchmark_condition_pairs"] == 12
    assert current["network_calls_made"] == 0
    assert current["model_calls_made"] == 0
    assert current["experiment_records_persisted"] == 0
    assert current["formal_results_created"] == 0
    assert current["forbidden_runtime_context_fields_present"] is False
    assert current["live_dependencies_qualified"] is False
    assert set(current["runtime_context_fields"]).isdisjoint(
        FORBIDDEN_RUNTIME_CONTEXT_FIELDS
    )


def test_qualification_artifact_contains_no_raw_fixture_content() -> None:
    rendered = Path(DEFAULT_OUTPUT).read_text(encoding="utf-8")
    assert "OFFLINE_QUALIFICATION" not in rendered
    assert "response_text" not in json.loads(rendered)[
        "event_redaction_contract"
    ]
