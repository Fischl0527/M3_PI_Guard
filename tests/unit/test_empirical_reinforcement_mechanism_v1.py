from __future__ import annotations

import json
import copy
from collections import Counter

import pytest

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2 import empirical_reinforcement_mechanism_v1 as subject
from experiments.paper_v2.claude_revision_v1 import build_plan, write_plan
from experiments.paper_v2.correctness_runtime_v1 import CorrectnessRuntime
from experiments.paper_v2.formal_condition_executors import (
    CONDITION_PROFILES,
    OnlineExecutorContext,
)
from experiments.paper_v2.empirical_reinforcement_mechanism_v1 import (
    EmpiricalReinforcementError,
    build_controlled_fixtures,
    make_capture_sink,
    replay_capture,
    run_mechanism,
)
from experiments.paper_v2.live_condition_runtime import (
    DEFAULT_BUDGET_POLICY,
    LiveConditionRuntime,
    M3SandboxEffectBackend,
)
from experiments.paper_v2.medium_runtime import (
    DEFAULT_V2_PLAN,
    reconstruct_initial_online_state,
)
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderBudgetState,
)
from m3_guard.provenance import ProvenanceEvent
from m3_guard.runtime_monitor import ActionProposal
from m3_guard.task_policy import ParameterConstraint, TaskPolicyManifest, ToolRule


TOOL_SCHEMAS = {
    "send_email": {
        "arguments": {
            "to": {"type": "string", "required": True},
            "subject": {"type": "string", "required": True},
            "body": {"type": "string", "required": True},
        },
        "side_effect": True,
    }
}


def _manifest() -> TaskPolicyManifest:
    return TaskPolicyManifest(
        manifest_id="capture-fixture",
        policy_source=("trusted_user_request",),
        trusted_request_sha256="1" * 64,
        tool_schema_sha256=sha256_canonical_json(TOOL_SCHEMAS),
        rules=(
            ToolRule(
                rule_id="send-fixed-target",
                tool="send_email",
                argument_constraints={
                    "to": ParameterConstraint("exact", "outside@example.test"),
                    "subject": ParameterConstraint("type", "string"),
                    "body": ParameterConstraint("type", "string"),
                },
            ),
        ),
        generated_at="2026-10-12T00:00:00+00:00",
    )


def _proposal() -> ActionProposal:
    proposal_id = "nd-case-1:step:1"
    return ActionProposal(
        proposal_id=proposal_id,
        tool="send_email",
        arguments={
            "to": "outside@example.test",
            "subject": "fixture subject",
            "body": "fixture body",
        },
        provenance=(
            ProvenanceEvent(
                event_id="event-target",
                proposal_id=proposal_id,
                argument_path="arguments.to",
                source_type="untrusted_document",
                trust_level="untrusted",
                value_sha256="2" * 64,
            ),
        ),
        preceding_tools=(),
        step=1,
    )


def test_capture_is_internal_once_and_public_replay_is_redacted(tmp_path) -> None:
    capture_path = (
        tmp_path
        / "new_study"
        / "utility"
        / "pro"
        / "internal"
        / "proposal_captures"
        / "nd-case-1.jsonl"
    )
    row = {
        "study_id": "empirical-reinforcement-v1",
        "study_part": "R1",
        "work_key": "nd-case-1",
        "case_id": "case-1",
        "underlying_task_id": "task-1",
        "benchmark": "m3-v2",
        "condition_id": "no_defense",
        "authorization_regime": "auto_compiled",
    }
    context = {
        "phase": "before_guard",
        "prior_executed_tools": [],
        "prior_successful_tool_count": 0,
    }
    sink = make_capture_sink(capture_path, row)

    sink(_proposal(), _manifest(), TOOL_SCHEMAS, context)
    sink(_proposal(), _manifest(), TOOL_SCHEMAS, context)
    # The provider runner may rebuild its closure before every model call.  A
    # new sink targeting the same work key must preserve the first capture.
    make_capture_sink(capture_path, row)(
        _proposal(), _manifest(), TOOL_SCHEMAS, context
    )

    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    assert capture["proposal"]["arguments"]["to"] == "outside@example.test"
    assert capture["capture_context"]["phase"] == "before_guard"

    public = replay_capture(capture)
    rendered = json.dumps(public, ensure_ascii=False, sort_keys=True)
    assert public["policy_decision"] == "ALLOW"
    assert public["full_decision"] == "DENY"
    assert public["input_byte_identical"] is True
    assert public["input_scope"] == "first_parseable_nonfinal_before_guard_empty_execution_prefix"
    assert "outside@example.test" not in rendered
    assert '"arguments"' not in rendered
    assert '"provenance"' not in rendered


def test_controlled_fixture_matrix_has_40_bases_and_320_public_decisions(
    tmp_path,
) -> None:
    fixtures = build_controlled_fixtures()
    assert len(fixtures) == 40
    assert Counter(item["family"] for item in fixtures) == Counter(
        {
            "source_authority": 10,
            "dataflow": 10,
            "order": 10,
            "confirmation": 10,
        }
    )
    assert all(len(item["variants"]) == 2 for item in fixtures)

    summary = run_mechanism(tmp_path)
    rows = [
        json.loads(line)
        for line in (
            tmp_path / "mechanism" / "controlled_decisions_v1.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert summary["controlled_decisions"] == 320
    assert summary["capture_replays"] == 0
    assert len(rows) == 320
    assert Counter(row["family"] for row in rows) == Counter(
        {
            "source_authority": 80,
            "dataflow": 80,
            "order": 80,
            "confirmation": 80,
        }
    )
    assert Counter(row["module_factor"] for row in rows) == Counter(
        {"policy": 160, "full": 160}
    )
    assert Counter(row["proposal_role"] for row in rows) == Counter(
        {"legal": 160, "unauthorized": 160}
    )
    assert all(row["input_byte_identical"] for row in rows)
    assert all(row["provider_calls"] == 0 for row in rows)
    assert all(row["external_effects"] == 0 for row in rows)
    assert all(row["not_end_to_end"] is True for row in rows)
    rendered = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    assert "fixture-protected-value" not in rendered
    assert '"arguments"' not in rendered
    assert '"provenance"' not in rendered
    assert "p_value" not in rendered


def test_common_prefix_divergence_stops_before_target_history(
    tmp_path, monkeypatch
) -> None:
    fixtures = build_controlled_fixtures()
    divergent = fixtures[10]
    prefix = divergent["variants"][0]["prefix_by_role"]["legal"][0]
    original = prefix["proposal"]
    untrusted = ProvenanceEvent(
        event_id="forced-untrusted-prefix",
        proposal_id=original.proposal_id,
        argument_path="arguments.path",
        source_type="untrusted_document",
        trust_level="untrusted",
        value_sha256="3" * 64,
    )
    prefix["proposal"] = ActionProposal(
        proposal_id=original.proposal_id,
        tool=original.tool,
        arguments=original.arguments,
        provenance=(untrusted,),
        preceding_tools=(),
        step=1,
    )
    monkeypatch.setattr(subject, "build_controlled_fixtures", lambda: fixtures)

    with pytest.raises(EmpiricalReinforcementError, match="common prefix"):
        run_mechanism(tmp_path / "blocked")
    assert not (
        tmp_path
        / "blocked"
        / "mechanism"
        / "controlled_decisions_v1.jsonl"
    ).exists()


def test_run_mechanism_discovers_only_current_study_capture_roots(
    tmp_path,
) -> None:
    capture_path = (
        tmp_path
        / "activity"
        / "flash"
        / "internal"
        / "proposal_captures"
        / "nd-case-1.jsonl"
    )
    unrelated_path = (
        tmp_path
        / "historical"
        / "internal"
        / "proposal_captures"
        / "old.jsonl"
    )
    row = {
        "study_id": "empirical-reinforcement-v1",
        "study_part": "R2",
        "work_key": "nd-case-1",
        "case_id": "case-1",
        "underlying_task_id": "task-1",
        "benchmark": "m3-v2",
        "condition_id": "no_defense",
        "authorization_regime": "auto_compiled",
    }
    context = {
        "phase": "before_guard",
        "prior_executed_tools": [],
        "prior_successful_tool_count": 0,
    }
    make_capture_sink(capture_path, row)(
        _proposal(), _manifest(), TOOL_SCHEMAS, context
    )
    make_capture_sink(unrelated_path, row)(
        _proposal(), _manifest(), TOOL_SCHEMAS, context
    )

    summary = run_mechanism(tmp_path)

    public_rows = [
        json.loads(line)
        for line in (
            tmp_path / "mechanism" / "captured_replays_v1.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert summary["capture_replays"] == 1
    assert len(public_rows) == 1
    assert public_rows[0]["study_part"] == "R2"
    assert public_rows[0]["schema_version"] == subject.PUBLIC_REPLAY_SCHEMA


def test_live_capture_is_pre_guard_and_cannot_mutate_the_live_proposal() -> None:
    item = next(
        json.loads(line)
        for line in DEFAULT_V2_PLAN.read_text(encoding="utf-8").splitlines()
        if line.strip()
        and json.loads(line)["condition_id"] == "no_defense"
        and json.loads(line)["benchmark"] == "m3-v2"
    )
    state = reconstruct_initial_online_state(item)
    policy = json.loads(DEFAULT_BUDGET_POLICY.read_text(encoding="utf-8"))

    provider_calls = 0

    def transport(endpoint, headers, payload, timeout):
        nonlocal provider_calls
        del endpoint, headers, timeout
        provider_calls += 1
        content = (
            '{"tool":"read_file","arguments":'
            '{"path":"sandbox/public/clean_report.md"}}'
            if provider_calls == 1
            else '{"tool":"final","arguments":{"answer":"safe"}}'
        )
        return HTTPResponseEnvelope(
            status_code=200,
            headers={"x-request-id": "capture-fixture"},
            body={
                "id": f"capture-response-{provider_calls}",
                "model": payload["model"],
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": content,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 10,
                },
            },
        )

    client = OfficialProviderClient(
        provider_id="deepseek",
        api_key="offline-fixture",
        content_class="synthetic_m3_case",
        budget_state=ProviderBudgetState(provider_id="deepseek", policy=policy),
        policy=policy,
        transport=transport,
    )
    captured = []

    def sink(proposal, manifest, schemas, context):
        del manifest, schemas
        captured.append((copy.deepcopy(proposal.to_dict()), dict(context)))
        proposal.arguments["answer"] = "mutated-copy"

    runtime = LiveConditionRuntime(
        provider_client_factory=lambda context: client,
        effect_backend_factory=lambda context, schemas: M3SandboxEffectBackend(context),
        proposal_capture_sink=sink,
        recorded_at=lambda: "2026-10-12T00:00:00+00:00",
    )
    profile = CONDITION_PROFILES["no_defense"]
    context = OnlineExecutorContext(
        execution_identity=item["execution_identity"],
        work_key=item["work_key"],
        benchmark=item["benchmark"],
        condition_id="no_defense",
        max_provider_calls=profile.max_provider_calls,
        online_state=state,
    )

    raw = runtime.execute(context, profile)

    assert provider_calls == 2
    assert captured[0][0]["tool"] == "read_file"
    assert captured[0][0]["arguments"] == {
        "path": "sandbox/public/clean_report.md"
    }
    assert captured[0][1]["phase"] == "before_guard"
    assert captured[0][1]["prior_executed_tools"] == []
    assert captured[0][1]["prior_successful_tool_count"] == 0
    assert captured[1][0]["tool"] == "final"
    assert captured[1][1]["prior_executed_tools"] == ["read_file"]
    assert captured[1][1]["prior_successful_tool_count"] == 1
    assert raw["events"][0]["arguments"] == {
        "path": "sandbox/public/clean_report.md"
    }
    assert raw["events"][1]["arguments"] == {"answer": "safe"}


def test_correctness_runtime_accepts_optional_capture_without_changing_default(
    tmp_path,
) -> None:
    plan_path = write_plan(tmp_path)
    row = next(
        item
        for item in build_plan()
        if item["study_part"] == "authorization"
        and item["authorization_regime"] == "auto_compiled"
    )
    def sink(proposal, manifest, schemas, context):
        del proposal, manifest, schemas, context

    default = CorrectnessRuntime(
        plan_path=plan_path,
        execution_identity=row["execution_identity"],
        compiler_revision="corrected_v2",
        runtime_revision="corrected_v2",
    )
    observed = CorrectnessRuntime(
        plan_path=plan_path,
        execution_identity=row["execution_identity"],
        compiler_revision="corrected_v2",
        runtime_revision="corrected_v2",
        proposal_capture_sink=sink,
    )

    assert default.proposal_capture_sink is None
    assert observed.proposal_capture_sink is sink
