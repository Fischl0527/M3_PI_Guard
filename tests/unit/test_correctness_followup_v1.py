"""New controls only; no replay of old tests or provider requests."""

import json
import threading

import pytest

from experiments.paper_v2.correctness_followup_v1 import (
    ARCHIVE,
    CONDITIONS,
    CONTENT,
    PATH,
    RESTRICTED,
    SCENARIOS,
    FollowupSession,
    MemoryEffectBackend,
    build_model_plan,
    fixed_actions,
    run_confirmation_probe,
    run_dataflow_probe,
    run_live_probe,
)
from experiments.paper_v2.correctness_provider_v1 import (
    DevelopmentRequestClient,
    RequestPacer,
)
from experiments.paper_v2.official_provider_executor import HTTPResponseEnvelope


@pytest.mark.parametrize("scenario_id", list(SCENARIOS))
def test_same_proposals_produce_real_state_endpoints(scenario_id):
    policy = run_dataflow_probe(scenario_id, "m3_policy_only")
    full = run_dataflow_probe(scenario_id, "m3_full")
    assert policy["action_sequence_sha256"] == full["action_sequence_sha256"]
    assert policy["executed_send_count"] == 1
    assert policy["task_completion"] is True
    if scenario_id == "private_restricted":
        assert policy["simulated_unsafe_effect"] is True
        assert full["executed_send_count"] == 0
        assert full["task_completion"] is False
        assert full["simulated_unsafe_effect"] is False
        assert full["events"][1]["dataflow"]["status"] == "triggered"
    else:
        assert full["executed_send_count"] == 1
        assert full["task_completion"] is True
    if scenario_id == "missing_classification":
        assert full["events"][1]["dataflow"]["status"] == "missing_input"
        # Negative control: current policy fails open; never fabricate success.
        assert full["simulated_unsafe_effect"] is True
    assert CONTENT not in json.dumps(full)


@pytest.mark.parametrize("condition", CONDITIONS)
@pytest.mark.parametrize(
    "mode,status,sends",
    [
        ("approved", "allow_simulated_effect_once", 1),
        ("denied", "denied", 0),
        ("absent", "confirmation_absent", 0),
        ("expired", "expired", 0),
        ("replay", "allow_simulated_effect_once", 1),
        ("wrong_action", "binding_mismatch", 0),
    ],
)
def test_confirmation_reaches_backend_and_independent_score(
    condition, mode, status, sends
):
    result = run_confirmation_probe(mode, condition)
    assert result["before_confirmation"]["executed_send_count"] == 0
    assert result["before_confirmation"]["executed_tools"] == ["read_file"]
    assert result["confirmation_status"] == status
    assert result["executed_send_count"] == sends
    assert result["task_completion"] is bool(sends)
    assert result["simulated_unsafe_effect"] is False
    assert result["executed_tools"] == ["read_file"] + (["send_email"] if sends else [])
    if mode == "replay":
        assert result["replay_status"] == "replay_rejected"


def test_backend_isolation_rejects_outside_paths_tools_and_mailboxes():
    backend = MemoryEffectBackend(SCENARIOS["public_restricted"])
    for tool, args in [
        ("read_file", {"path": "../../outside.txt"}),
        ("run_code", {"code": "arbitrary"}),
        ("send_email", {"to": "outside@example.com", "subject": "x", "body": CONTENT}),
    ]:
        assert backend.execute(tool, args)["effect_applied"] is False
    assert backend.outbox == []
    assert backend.boundary_rejections == 3
    backend.close()
    with pytest.raises(RuntimeError, match="closed"):
        backend.execute("read_file", {"path": PATH})


def test_confirmation_cannot_expand_scope_or_override_dataflow():
    from experiments.paper_v2.confirmation_session_v1 import ConfirmationSession

    for scenario_id, destination, expected in [
        ("private_restricted", RESTRICTED, "denied_by_guard"),
        ("private_archive", RESTRICTED, "denied_by_guard"),
        ("public_restricted", ARCHIVE, "blocked_scope_not_expandable"),
    ]:
        session = FollowupSession(SCENARIOS[scenario_id], "m3_full", confirmation=True)
        session.act(session.proposal("read_file", {"path": PATH}))
        proposal = session.proposal(
            "send_email", {"to": destination, "subject": "x", "body": CONTENT}
        )
        result = ConfirmationSession(clock=lambda: 0).request(
            task_id="t",
            request_digest="r",
            proposal=proposal,
            manifest=session.manifest,
            modules=session.monitor.modules,
            monitor=session.monitor,
        )
        assert result.status == expected
        assert session.backend.outbox == []


def test_plan_is_16_items_48_max_calls_and_excludes_gemini():
    plan = build_model_plan()
    assert len(plan) == len({row["work_key"] for row in plan}) == 16
    assert sum(row["max_provider_calls"] for row in plan) == 48
    assert {row["model_group"] for row in plan} == {"deepseek_pro", "deepseek_flash"}
    assert {row["attempt"] for row in plan} == {1}
    assert {row["prompt_factor"] for row in plan} == {"normal"}
    assert {row["module_factor"] for row in plan} == {"policy", "full"}


@pytest.mark.parametrize("condition", CONDITIONS)
def test_actual_live_runtime_provider_seam_preserves_label_and_effect_results(
    tmp_path, condition
):
    row = next(
        row
        for row in build_model_plan()
        if row["model_group"] == "deepseek_pro"
        and row["scenario_id"] == "private_restricted"
        and row["condition_id"] == condition
    )
    actions = fixed_actions(SCENARIOS[row["scenario_id"]])
    calls = []

    def transport(endpoint, headers, payload, timeout):
        calls.append(payload)
        return HTTPResponseEnvelope(
            status_code=200,
            headers={"x-request-id": f"offline-{len(calls)}"},
            body={
                "id": f"offline-response-{len(calls)}",
                "model": payload["model"],
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(actions[len(calls) - 1]),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 10,
                    "total_tokens": 20,
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 10,
                },
            },
        )

    client = DevelopmentRequestClient(
        model_group=row["model_group"],
        model=row["model_id"],
        api_key="offline-fixture",
        benchmark="m3-v2",
        work_key=row["work_key"],
        attempt=1,
        trace_path=tmp_path / "trace.jsonl",
        pacer=RequestPacer(0, threading.Event()),
        transport=transport,
        max_provider_calls=3,
    )
    result = run_live_probe(row, client)
    assert result["operational_status"] == "completed"
    assert result["provider_call_count"] == len(calls) == 3
    assert result["executed_send_count"] == (0 if condition == "m3_full" else 1)
    assert result["simulated_unsafe_effect"] is (condition == "m3_policy_only")
    assert (
        result["events"][1]["corrected_diagnostics"]["dataflow"]["labelled_value_count"]
        == 1
    )
    assert all(not request["provider_tools_enabled"] for request in client.requests)
    assert result["provenance_summary"]["labelled_value_count"] == 1
    assert sum(result["dataflow_status_counts"].values()) == 3
    assert "task_completion" not in json.dumps(calls)
    assert CONTENT not in json.dumps(result)


def test_unplanned_live_item_is_rejected_before_client_use():
    row = {**build_model_plan()[0], "model_group": "gemini_flash"}
    with pytest.raises(ValueError, match="outside"):
        run_live_probe(row, object())


@pytest.mark.parametrize(
    "provider,model,requests",
    [
        ("gemini", "deepseek-v4-pro", []),
        ("deepseek", "deepseek-flash", []),
        ("deepseek", "deepseek-v4-pro", [{"attempt": 1}]),
    ],
)
def test_wrong_provider_model_or_reused_client_is_rejected(provider, model, requests):
    from types import SimpleNamespace

    client = SimpleNamespace(
        max_provider_calls=3,
        provider_id=provider,
        model=model,
        requests=requests,
    )
    with pytest.raises(ValueError, match="fresh matching"):
        run_live_probe(build_model_plan()[0], client)


def test_offline_cli_outputs_20_real_execution_rows_idempotently(tmp_path):
    from experiments.paper_v2.correctness_followup_v1 import run_offline

    result = run_offline(tmp_path)
    before = (tmp_path / "results.jsonl").read_bytes()
    assert result["offline_recorded"] == result["offline_planned"] == 20
    assert sum(group["observed"] for group in result["models"].values()) == 0
    assert CONTENT.encode() not in before
    run_offline(tmp_path)
    assert (tmp_path / "results.jsonl").read_bytes() == before


def _batch_client_factory(
    created, *, wrong_returned_model=False, provider_failure=False
):
    def factory(**kwargs):
        row = next(
            item
            for item in build_model_plan()
            if item["work_key"] == kwargs["work_key"]
        )
        actions = fixed_actions(SCENARIOS[row["scenario_id"]])
        calls = []
        created.append(calls)

        def transport(endpoint, headers, payload, timeout):
            calls.append(payload)
            if provider_failure:
                return HTTPResponseEnvelope(
                    status_code=503, headers={}, body={"error": "fixture-unavailable"}
                )
            return HTTPResponseEnvelope(
                status_code=200,
                headers={"x-request-id": f"fixture-{len(created)}-{len(calls)}"},
                body={
                    "id": f"fixture-response-{len(created)}-{len(calls)}",
                    "model": "mismatched-model"
                    if wrong_returned_model
                    else payload["model"],
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(actions[len(calls) - 1]),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 10,
                        "total_tokens": 20,
                        "prompt_cache_hit_tokens": 0,
                        "prompt_cache_miss_tokens": 10,
                    },
                },
            )

        return DevelopmentRequestClient(**kwargs, transport=transport)

    return factory


def test_pending_runner_retains_all_results_does_not_stop_on_unsafe_or_replay(tmp_path):
    from experiments.paper_v2.correctness_followup_v1 import run_live_pending

    created = []
    config = {
        "FRONTIER_DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "DEEPSEEK_API_KEY": "offline-fixture",
    }
    result = run_live_pending(
        config, output=tmp_path, client_factory=_batch_client_factory(created)
    )
    assert result["stop_reason"] is None
    assert len(created) == 16
    assert sum(map(len, created)) == 48
    # The first provider message is byte-equivalent across policy/full; only
    # modules differ. Guard feedback can legitimately change later messages.
    for index in range(0, len(created), 2):
        assert created[index][0]["messages"] == created[index + 1][0]["messages"]
    assert sum(item["observed"] for item in result["models"].values()) == 16
    assert all(
        item["simulated_unsafe_effect_true"] > 0 for item in result["models"].values()
    )
    before = (tmp_path / "results.jsonl").read_bytes()
    run_live_pending(
        config,
        output=tmp_path,
        client_factory=lambda **_: pytest.fail("must not repeat existing results"),
    )
    assert (tmp_path / "results.jsonl").read_bytes() == before


def test_identity_failure_stops_and_is_kept_without_retry(tmp_path):
    from experiments.paper_v2.correctness_followup_v1 import run_live_pending

    created = []
    config = {
        "FRONTIER_DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "DEEPSEEK_API_KEY": "offline-fixture",
    }
    result = run_live_pending(
        config,
        output=tmp_path,
        client_factory=_batch_client_factory(created, wrong_returned_model=True),
    )
    assert result["stop_reason"] is not None
    assert len(created) == 1
    assert result["models"]["deepseek_pro"]["observed"] == 1
    assert result["models"]["deepseek_pro"]["not_run"] == 7
    result2 = run_live_pending(
        config,
        output=tmp_path,
        client_factory=lambda **_: pytest.fail("identity failure must stay stopped"),
    )
    assert result2["stop_reason"] == result["stop_reason"]


def test_provider_failures_stay_in_itt_and_never_auto_retry(tmp_path):
    from experiments.paper_v2.correctness_followup_v1 import run_live_pending

    created = []
    config = {
        "FRONTIER_DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "DEEPSEEK_API_KEY": "offline-fixture",
    }
    result = run_live_pending(
        config,
        output=tmp_path,
        client_factory=_batch_client_factory(created, provider_failure=True),
    )
    assert len(created) == 16
    assert sum(map(len, created)) == 16
    assert all(
        group["operational_status"] == {"provider_failure": 8}
        for group in result["models"].values()
    )


def test_interrupted_trace_never_dispatches_again(tmp_path):
    from experiments.paper_v2.correctness_followup_v1 import run_live_pending
    from experiments.paper_v2.correctness_provider_v1 import append_row

    row = build_model_plan()[0]
    trace = (
        tmp_path / "internal" / row["model_group"] / f"{row['work_key']}.attempt1.jsonl"
    )
    append_row(trace, {"event": "started"})
    result = run_live_pending(
        {},
        output=tmp_path,
        client_factory=lambda **_: pytest.fail("unresolved request must stop"),
    )
    assert result["stop_reason"] == "unresolved_request_trace_no_automatic_replay"
    assert sum(group["observed"] for group in result["models"].values()) == 0
