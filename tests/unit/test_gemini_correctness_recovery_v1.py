"""Recovery public entry points; no live network."""

from experiments.paper_v2.correctness_plan_v1 import OUTPUT, read_jsonl
from experiments.paper_v2 import gemini_correctness_recovery_v1 as recovery
import pytest
import json
import threading
from experiments.paper_v2.correctness_provider_v1 import (
    DevelopmentRequestClient,
    RequestPacer,
)
from experiments.paper_v2.correctness_runtime_v1 import CorrectnessRuntime
from experiments.paper_v2.official_provider_executor import HTTPResponseEnvelope


def test_real_runtime_uses_remaining_seven_calls_without_eighth(tmp_path):
    plan = read_jsonl(OUTPUT / "plan.jsonl")
    item = next(
        r
        for r in plan
        if r["model_group"] == "gemini_flash"
        and r["benchmark"] == "m3-v2"
        and r["condition_id"] == "no_defense"
    )
    calls = []

    def transport(endpoint, headers, payload, timeout):
        calls.append(payload)
        return HTTPResponseEnvelope(
            200,
            {},
            {
                "id": f"offline-{len(calls)}",
                "model": "gemini-3.6-flash",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "tool": "read_file",
                                    "arguments": {"path": "sandbox/public/a.txt"},
                                }
                            )
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 10,
                    "total_tokens": 20,
                },
            },
        )

    client = DevelopmentRequestClient(
        model_group="gemini_flash",
        model="gemini-3.6-flash",
        api_key="offline-test-fixture",
        benchmark="m3-v2",
        work_key=item["work_key"],
        attempt=2,
        trace_path=tmp_path / "trace.jsonl",
        pacer=RequestPacer(0, threading.Event()),
        generation_profile=recovery.PROFILE,
        max_provider_calls=7,
        transport=transport,
    )
    runtime = CorrectnessRuntime(
        plan_path=OUTPUT / "plan.jsonl", execution_identity=item["execution_identity"]
    )
    outcome = runtime.execute(item, client)
    assert len(calls) == 7
    assert outcome["operational_status"] == "max_steps"


def test_service_backoff_resets_on_success_and_stops_at_five_or_429():
    state = recovery.ServiceBackoff()
    for expected in (60, 120, 240, 300):
        assert state.observe([{"http_status": 503}]) is None
        assert state.delay_seconds == expected
    assert state.observe([{"http_status": 503}]) == "five_consecutive_503"
    state = recovery.ServiceBackoff()
    state.observe([{"http_status": 503}])
    state.observe([{"http_status": 200}, {"http_status": 503}])
    assert state.delay_seconds == 60
    assert state.observe([{"http_status": 200}]) is None
    assert state.delay_seconds == 0
    assert state.observe([{"http_status": 429}]) == "provider_429"


def test_new_no_response_retry_subtracts_spent_call_and_never_retries_response():
    plan = read_jsonl(OUTPUT / "plan.jsonl")
    old = read_jsonl(OUTPUT / "gemini_flash/raw_records.jsonl")
    item, _, _ = next(t for t in recovery.select_pending(plan, old, []) if t[1] == 1)
    row = dict(
        item,
        attempt=1,
        response_obtained=False,
        operational_status="provider_failure",
        provider_requests=[{"http_status": 503}],
    )
    selected = {
        r["work_key"]: (a, cap)
        for r, a, cap in recovery.select_pending(plan, old, [row])
    }
    assert selected[item["work_key"]] == (2, 7)
    row["response_obtained"] = True
    assert item["work_key"] not in {
        r["work_key"] for r, _, _ in recovery.select_pending(plan, old, [row])
    }
    with pytest.raises(ValueError, match="response-bearing"):
        recovery.select_pending(plan, old, [row, dict(row, attempt=2)])


def test_original_recovery_population_and_call_budget():
    plan = read_jsonl(OUTPUT / "plan.jsonl")
    old = read_jsonl(OUTPUT / "gemini_flash/raw_records.jsonl")
    selected = recovery.select_pending(plan, old, [])
    assert len(selected) == 283
    assert sum(item["formal_prefix"] for item, _, _ in selected) == 25
    assert sum(attempt == 1 for _, attempt, _ in selected) == 280
    assert sum(attempt == 2 for _, attempt, _ in selected) == 3
    assert {cap for _, attempt, cap in selected if attempt == 2} == {7}
    protected = {row["work_key"] for row in old if row["response_obtained"]}
    assert not protected.intersection(item["work_key"] for item, _, _ in selected)
    assert all(item["max_tokens"] == 2048 for item, _, _ in selected)
    assert all(item["reasoning_effort"] == "low" for item, _, _ in selected)


def diagnostic_factory(**kwargs):
    def transport(endpoint, headers, payload, timeout):
        content = payload["messages"][-1]["content"].split(
            "Return exactly this JSON proposal: ", 1
        )[1]
        return HTTPResponseEnvelope(
            200,
            {},
            {
                "id": kwargs["work_key"],
                "model": "gemini-3.6-flash",
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 20,
                    "total_tokens": 40,
                },
            },
        )

    return DevelopmentRequestClient(**kwargs, transport=transport)


def test_diagnostics_six_only_text_requests_and_restart_reuses_completed(tmp_path):
    assert recovery.run_diagnostics(
        "offline-fixture",
        output=tmp_path,
        client_factory=diagnostic_factory,
        interval=0,
    )["passed"]
    rows = read_jsonl(tmp_path / "diagnostics.jsonl")
    assert len(rows) == 6
    assert {r["action_kind"] for r in rows} == {"read_file", "write_file", "final"}
    assert all(r["passed"] for r in rows)
    assert recovery.run_diagnostics(
        "offline-fixture",
        output=tmp_path,
        client_factory=lambda **kw: pytest.fail("must not redispatch"),
        interval=0,
    )["passed"]
    assert len(read_jsonl(tmp_path / "diagnostics.jsonl")) == 6


@pytest.mark.parametrize(
    "http_status,expected_count,expected_reason",
    [(503, 5, "five_consecutive_503"), (429, 1, "provider_429")],
)
def test_dispatch_service_failures_are_bounded_without_deepseek(
    tmp_path, http_status, expected_count, expected_reason
):
    recovery.run_diagnostics(
        "offline-fixture",
        output=tmp_path,
        client_factory=diagnostic_factory,
        interval=0,
    )
    waits = []

    def factory(**kwargs):
        return DevelopmentRequestClient(
            **kwargs, transport=lambda *args: HTTPResponseEnvelope(http_status, {}, {})
        )

    class Runtime:
        def execute(self, item, client):
            client.complete([{"role": "user", "content": "Return only JSON."}])

    result = recovery.run_recovery(
        "offline-fixture",
        output=tmp_path,
        client_factory=factory,
        runtime=Runtime(),
        interval=0,
        sleeper=waits.append,
    )
    rows = read_jsonl(tmp_path / "raw_records.jsonl")
    assert len(rows) == expected_count
    assert result["stop_reason"] == expected_reason
    assert result["state"] == "paused"
    assert all(r["model_group"] == "gemini_flash" for r in rows)
    if http_status == 503:
        assert waits == [60, 120, 240, 300]
        assert all(r["failure_class"] == "ServiceUnavailable" for r in rows)
    else:
        assert waits == []


def test_open_trace_prevents_any_dispatch(tmp_path):
    recovery.run_diagnostics(
        "offline-fixture",
        output=tmp_path,
        client_factory=diagnostic_factory,
        interval=0,
    )
    plan = read_jsonl(OUTPUT / "plan.jsonl")
    old = read_jsonl(OUTPUT / "gemini_flash/raw_records.jsonl")
    item, attempt, _ = recovery.select_pending(plan, old, [])[0]
    trace = (
        tmp_path
        / "internal/gemini_flash"
        / f"{item['work_key']}.attempt{attempt}.jsonl"
    )
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text('{"event":"started"}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="open request"):
        recovery.run_recovery(
            "offline-fixture",
            output=tmp_path,
            client_factory=lambda **kw: pytest.fail("open request must block dispatch"),
        )


def test_boolean_attempt_and_excess_cumulative_calls_rejected():
    plan = read_jsonl(OUTPUT / "plan.jsonl")
    old = read_jsonl(OUTPUT / "gemini_flash/raw_records.jsonl")
    item, _, _ = next(t for t in recovery.select_pending(plan, old, []) if t[1] == 1)
    row = dict(
        item,
        attempt=True,
        response_obtained=False,
        operational_status="provider_failure",
        provider_requests=[],
    )
    with pytest.raises(ValueError, match="attempt"):
        recovery.select_pending(plan, old, [row])
    row.update(attempt=1, provider_requests=[{"http_status": 503}] * 7)
    second = dict(row, attempt=2, provider_requests=[{"http_status": 503}] * 2)
    with pytest.raises(ValueError, match="cap exceeded"):
        recovery.select_pending(plan, old, [row, second])
