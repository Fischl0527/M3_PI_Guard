"""Offline scheduler, recovery and failed-endpoint checks; no model calls."""

from __future__ import annotations

import copy
import json
import threading

import pytest

from experiments.paper_v2 import correctness_runner_v1 as subject


def item(index=0, group="deepseek_pro", *, prefix=True):
    return {
        "model_group": group,
        "model_id": subject.MODELS[group],
        "work_key": f"fixture-{group}-{index}",
        "case_id": f"case-{index}",
        "benchmark": "m3-v2",
        "execution_identity": f"identity-{group}",
        "formal_prefix": prefix,
    }


def record(row, *, attempt=1, response=True, status="completed", requests=None):
    return {
        **copy.deepcopy(row),
        "attempt": attempt,
        "status": "terminal",
        "operational_status": status,
        "response_obtained": response,
        "provider_requests": requests if requests is not None else [],
        "unsafe_effect": False if response else None,
        "task_completion": True if status == "completed" else None,
    }


def fixture_plan(tmp_path, rows):
    path = tmp_path / "plan.jsonl"
    for row in rows:
        subject.append_row(path, row)
    return path


@pytest.fixture
def runtime_stubs(monkeypatch):
    monkeypatch.setattr(
        subject, "credential", lambda values, group: "offline-runner-fixture"
    )
    monkeypatch.setattr(subject, "CorrectnessRuntime", lambda **kwargs: object())


def test_latest_records_rejects_response_bearing_or_completed_replay():
    row = item()
    for old in [
        record(row),
        record(row, status="parse_failure"),
        record(row, response=False),
    ]:
        with pytest.raises(ValueError, match="repeated"):
            subject.latest_records([old, record(row, attempt=2)])


def test_only_one_explicit_no_response_recovery_is_permitted():
    row = item()
    first = record(row, response=False, status="provider_failure")
    second = record(row, attempt=2)
    latest = subject.latest_records([first, second])
    assert latest[row["work_key"]]["attempt"] == 2
    assert subject.pending_rows([row], {row["work_key"]: first}, row["work_key"]) == [
        (row, 2)
    ]
    with pytest.raises(ValueError):
        subject.pending_rows([row], latest, row["work_key"])


@pytest.mark.parametrize("attempt", [-1, 2, 3, True])
def test_orphan_or_invalid_first_attempt_is_rejected(attempt):
    with pytest.raises(ValueError):
        subject.latest_records(
            [record(item(), attempt=attempt, response=False, status="provider_failure")]
        )


def test_administrative_unrun_cannot_be_promoted_to_a_new_attempt():
    row = item()
    unrun = subject.make_unrun(row, "provider_429")
    assert subject.latest_records([unrun])[row["work_key"]]["attempt"] == 0
    with pytest.raises(ValueError):
        subject.latest_records([unrun, record(row, attempt=1)])
    with pytest.raises(ValueError):
        subject.pending_rows([row], {row["work_key"]: unrun}, row["work_key"])


def test_pending_only_does_not_implicitly_retry_failed_or_finished_work():
    rows = [item(i) for i in range(3)]
    prior = {
        rows[0]["work_key"]: record(rows[0]),
        rows[1]["work_key"]: record(rows[1], response=False, status="provider_failure"),
    }
    assert subject.pending_rows(rows, prior) == [(rows[2], 1)]


def test_make_unrun_preserves_unknown_endpoints_and_zero_calls():
    result = subject.make_unrun(item(), "provider_429")
    assert result["unsafe_effect"] is None and result["task_completion"] is None
    assert result["provider_call_count"] == 0 and result["provider_requests"] == []
    assert result["attempt"] == 0 and result["operational_status"] == "not_run"


@pytest.mark.parametrize("had_response", [False, True])
def test_execute_exception_preserves_unknown_endpoints_and_received_flag(
    tmp_path, had_response
):
    class Client:
        def __init__(self, **kwargs):
            self.requests = [{"response_received": had_response, "status": "failed"}]

    class Runtime:
        def execute(self, item, client):
            raise ValueError("private runtime body must not be logged")

    result = subject.execute_one(
        item(),
        1,
        runtime=Runtime(),
        api_key="offline-key",
        pacer=subject.RequestPacer(0, threading.Event()),
        output=tmp_path,
        client_factory=Client,
    )
    assert result["unsafe_effect"] is None and result["task_completion"] is None
    assert result["response_obtained"] is had_response
    assert result["failure_class"] == "ValueError"
    assert "private runtime" not in json.dumps(result)
    assert result["operational_status"] == "runner_failure"


def test_execute_open_trace_is_not_silently_replayed(tmp_path):
    row = item()
    trace = (
        tmp_path / "internal" / row["model_group"] / f"{row['work_key']}.attempt1.jsonl"
    )
    subject.append_row(trace, {"event": "started"})
    called = []
    with pytest.raises(RuntimeError, match="trace exists"):
        subject.execute_one(
            row,
            1,
            runtime=object(),
            api_key="offline-key",
            pacer=subject.RequestPacer(0, threading.Event()),
            output=tmp_path,
            client_factory=lambda **kwargs: called.append(1),
        )
    assert called == []


def test_gemini_first429_seals_remaining_without_dispatch(
    tmp_path, monkeypatch, runtime_stubs
):
    rows = [item(i, "gemini_flash") for i in range(4)]
    path = fixture_plan(tmp_path, rows)
    dispatched = []

    def fake_execute(row, attempt, **kwargs):
        dispatched.append(row["work_key"])
        kwargs["pacer"].stopped.set()
        return record(
            row,
            response=False,
            status="provider_failure",
            requests=[{"http_status": 429}],
        )

    monkeypatch.setattr(subject, "execute_one", fake_execute)
    summary = subject.run_model(
        "gemini_flash", path, {}, threading.Event(), output=tmp_path
    )
    raw = subject.read_jsonl(tmp_path / "gemini_flash" / "raw_records.jsonl")
    assert dispatched == [rows[0]["work_key"]]
    assert summary["stop_reason"] == "provider_429" and len(raw) == 4
    assert sum(row["operational_status"] == "not_run" for row in raw) == 3
    assert all(row["unsafe_effect"] is None for row in raw)


def test_deepseek_does_not_dispatch_past_two_inflight_after429(
    tmp_path, monkeypatch, runtime_stubs
):
    rows = [item(i) for i in range(6)]
    path = fixture_plan(tmp_path, rows)
    barrier = threading.Barrier(2)
    dispatched = []
    lock = threading.Lock()

    def fake_execute(row, attempt, **kwargs):
        with lock:
            dispatched.append(row["work_key"])
        barrier.wait(timeout=3)
        if row["case_id"] == "case-0":
            kwargs["pacer"].stopped.set()
            return record(
                row,
                response=False,
                status="provider_failure",
                requests=[{"http_status": 429}],
            )
        assert kwargs["pacer"].stopped.wait(3)
        return record(row)

    monkeypatch.setattr(subject, "execute_one", fake_execute)
    summary = subject.run_model(
        "deepseek_pro", path, {}, threading.Event(), output=tmp_path
    )
    assert len(dispatched) == 2
    assert summary["recorded"] == 6
    raw = subject.read_jsonl(tmp_path / "deepseek_pro" / "raw_records.jsonl")
    assert sum(row["operational_status"] == "not_run" for row in raw) == 4


def test_prefix_reused_and_only_pending_work_runs(tmp_path, monkeypatch, runtime_stubs):
    rows = [item(0), item(1, prefix=False)]
    path = fixture_plan(tmp_path, rows)
    subject.append_row(tmp_path / "deepseek_pro" / "raw_records.jsonl", record(rows[0]))
    dispatched = []
    monkeypatch.setattr(
        subject,
        "execute_one",
        lambda row, attempt, **kwargs: (
            dispatched.append(row["work_key"]) or record(row)
        ),
    )
    subject.run_model("deepseek_pro", path, {}, threading.Event(), output=tmp_path)
    assert dispatched == [rows[1]["work_key"]]
    subject.run_model("deepseek_pro", path, {}, threading.Event(), output=tmp_path)
    assert dispatched == [rows[1]["work_key"]]


def test_prefix_only_does_not_administratively_close_nonprefix(
    tmp_path, monkeypatch, runtime_stubs
):
    rows = [item(0), item(1, prefix=False)]
    path = fixture_plan(tmp_path, rows)
    monkeypatch.setattr(
        subject, "execute_one", lambda row, attempt, **kwargs: record(row)
    )
    summary = subject.run_model(
        "deepseek_pro", path, {}, threading.Event(), output=tmp_path, prefix_only=True
    )
    assert summary["recorded"] == 1
    raw = subject.read_jsonl(tmp_path / "deepseek_pro" / "raw_records.jsonl")
    assert len(raw) == 1 and raw[0]["work_key"] == rows[0]["work_key"]


@pytest.mark.parametrize("status", ["runner_failure", "provider_failure"])
def test_same_system_error_two_distinct_cases_stops_remaining(
    tmp_path, monkeypatch, runtime_stubs, status
):
    rows = [item(i, "gemini_flash") for i in range(4)]
    path = fixture_plan(tmp_path, rows)
    dispatched = []

    def fake_execute(row, attempt, **kwargs):
        dispatched.append(row["work_key"])
        return {
            **record(row, response=False, status=status),
            "failure_class": "FixtureSystemError",
        }

    monkeypatch.setattr(subject, "execute_one", fake_execute)
    summary = subject.run_model(
        "gemini_flash", path, {}, threading.Event(), output=tmp_path
    )
    assert len(dispatched) == 2 and summary["stop_reason"] == "repeated_system_error"


def test_provider_states_are_distinct_and_two_deepseek_finishes_stop_gemini(
    monkeypatch, tmp_path
):
    gemini_started = threading.Event()
    received_stops = {}
    lock = threading.Lock()

    def fake_run_model(group, plan_path, values, stop):
        with lock:
            received_stops[group] = stop
        if group == "gemini_flash":
            gemini_started.set()
            assert stop.wait(3), (
                "Gemini must be released after both DeepSeek jobs close"
            )
        else:
            assert gemini_started.wait(3)
            assert not stop.is_set()
        return {"model_group": group, "fixture": True}

    monkeypatch.setattr(subject, "run_model", fake_run_model)
    results = subject.run_all(tmp_path / "unused-plan.jsonl", {})
    assert len(results) == 3
    assert len({id(stop) for stop in received_stops.values()}) == 3
    assert received_stops["gemini_flash"].is_set()
    assert not received_stops["deepseek_pro"].is_set()
    assert not received_stops["deepseek_flash"].is_set()


def test_run_all_one_provider_failure_does_not_cancel_other_deepseek(
    monkeypatch, tmp_path
):
    def fake_run_model(group, plan_path, values, stop):
        if group == "deepseek_pro":
            raise RuntimeError("fixture unclosed trace")
        if group == "gemini_flash":
            assert stop.wait(3)
        return {"model_group": group, "state": "closed"}

    monkeypatch.setattr(subject, "run_model", fake_run_model)
    results = {
        row["model_group"]: row
        for row in subject.run_all(tmp_path / "unused-plan.jsonl", {})
    }
    assert results["deepseek_pro"]["state"] == "requires_diagnosis"
    assert results["deepseek_flash"]["state"] == "closed"


def test_model_lock_rejects_same_group_but_not_other_group(tmp_path):
    with subject.model_lock(tmp_path / "pro" / "runner.lock"):
        with pytest.raises(RuntimeError, match="active runner"):
            with subject.model_lock(tmp_path / "pro" / "runner.lock"):
                pytest.fail("same file lock must not be reentered")
        with subject.model_lock(tmp_path / "flash" / "runner.lock"):
            pass
    with subject.model_lock(tmp_path / "pro" / "runner.lock"):
        pass


def test_explicit_repaired_retry_is_not_blocked_by_old_system_stop(
    tmp_path, monkeypatch, runtime_stubs
):
    rows = [item(0), item(1)]
    path = fixture_plan(tmp_path, rows)
    raw_path = tmp_path / "deepseek_pro" / "raw_records.jsonl"
    for row in rows:
        subject.append_row(
            raw_path,
            {
                **record(
                    row,
                    response=False,
                    status="provider_failure",
                    requests=[{"error_type": "ProviderPayloadError"}],
                ),
                "failure_class": "ProviderPayloadError",
            },
        )
    called = []

    def repaired_execute(row, attempt, **kwargs):
        called.append((row["work_key"], attempt))
        return record(row, attempt=attempt)

    monkeypatch.setattr(subject, "execute_one", repaired_execute)
    subject.run_model(
        "deepseek_pro",
        path,
        {},
        threading.Event(),
        output=tmp_path,
        retry_key=rows[0]["work_key"],
    )
    assert called == [(rows[0]["work_key"], 2)]
    assert len(subject.read_jsonl(raw_path)) == 3


def test_dispatch_stop_is_not_http429_or_a_received_response(tmp_path):
    from experiments.paper_v2.correctness_provider_v1 import DispatchStopped, official

    assert not issubclass(DispatchStopped, official.ProviderPausedError)
    stop = threading.Event()
    stop.set()

    class Client:
        def __init__(self, **kwargs):
            self.requests = []

    class Runtime:
        def execute(self, row, client):
            subject.RequestPacer(0, stop).wait()

    result = subject.execute_one(
        item(),
        1,
        runtime=Runtime(),
        api_key="offline-key",
        pacer=subject.RequestPacer(0, stop),
        output=tmp_path,
        client_factory=Client,
    )
    assert result["failure_class"] == "DispatchStopped"
    assert result["provider_call_count"] == 0
    assert result["response_obtained"] is False
    assert result["provider_requests"] == []
    assert not hasattr(DispatchStopped("stop"), "http_status")


def test_execute_does_not_mask_reported_external_safety_violation(tmp_path):
    class Client:
        def __init__(self, **kwargs):
            self.requests = []

    class Runtime:
        def execute(self, row, client):
            return {
                "unsafe_effect": None,
                "task_completion": None,
                "operational_status": "runner_failure",
                "provider_tools_enabled": True,
                "real_external_effects": 1,
            }

    result = subject.execute_one(
        item(),
        1,
        runtime=Runtime(),
        api_key="offline-key",
        pacer=subject.RequestPacer(0, threading.Event()),
        output=tmp_path,
        client_factory=Client,
    )
    assert subject.critical_error(result) == "external_safety_violation"
