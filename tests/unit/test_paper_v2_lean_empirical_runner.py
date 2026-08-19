from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

import experiments.paper_v2.lean_empirical_runner as runner


class _Dispatcher:
    def __init__(self, *, fail_once: set[str] | None = None) -> None:
        self.fail_once = fail_once or set()
        self.calls: list[str] = []

    def execute(
        self, work_item: Mapping[str, Any], state: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        del state
        work_key = str(work_item["work_key"])
        self.calls.append(work_key)
        if work_key in self.fail_once:
            self.fail_once.remove(work_key)
            raise RuntimeError("synthetic pre-response transport failure")
        model = str(work_item["model_id"])
        provider = str(work_item["provider_id"])
        return {
            "unsafe_effect": work_item["evaluation_case_type"] == "attack",
            "task_completion": work_item["evaluation_case_type"] != "attack",
            "operational_status": "completed",
            "runtime_visibility_events": [
                {"guard_decision": {"decision": "ASK"}},
                {"guard_decision": {"decision": "DENY"}},
            ],
            "latency_ms": {"total": 12.5, "model": 10.0},
            "token_usage": {"input": 10, "output": 4, "total": 14},
            "provider_trace_bundle": {
                "activated_attestations": [
                    {
                        "client_request_id": f"m3req-{work_key[:16]}",
                        "payload_sha256": "a" * 64,
                        "provider_request_id": None,
                        "provider_response_id": f"response-{work_key[:16]}",
                        "model_id": model,
                    }
                ],
                "usage_summary": {
                    "cumulative_cost_cny": 0.001 if provider == "deepseek" else 0.0
                },
            },
            "recorded_at": "2026-08-19T00:00:00+08:00",
        }


def _output_patch(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(runner, "OUTPUT_ROOT", root)
    monkeypatch.setattr(
        runner,
        "PROVIDER_OUTPUTS",
        {
            "deepseek": root / "deepseek/raw_records_v1.jsonl",
            "gemini": root / "gemini/raw_records_v1.jsonl",
        },
    )


def _factory(dispatcher: _Dispatcher):
    def build(permit: runner.LeanPermit, provider_id: str) -> _Dispatcher:
        assert permit.provider_id == provider_id
        return dispatcher

    return build


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_plan_hydrates_without_online_gold_or_evaluator_fields() -> None:
    rows = runner._load_plan("deepseek")
    assert len(rows) == 900
    assert sum(row["formal_prefix"] is True for row in rows) == 6
    for row in rows[:3]:
        hydrated, _, digest = runner._hydrate_work_item(row)
        assert hydrated["source_record_sha256"] == row["source_reference"]["sha256"]
        assert digest["forbidden_fields_present"] is False


def test_canary_writes_six_compact_records_and_never_reruns_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _output_patch(monkeypatch, tmp_path / "lean")
    dispatcher = _Dispatcher()
    first = runner.run_provider(
        "deepseek",
        stage="canary",
        credential_loader=lambda: {},
        dispatcher_factory=_factory(dispatcher),
    )
    second = runner.run_provider(
        "deepseek",
        stage="canary",
        credential_loader=lambda: {},
        dispatcher_factory=lambda *_: pytest.fail("successful rows were rerun"),
    )
    assert first["executed"] == first["completed"] == 6
    assert second["executed"] == 0
    rows = _rows(runner.PROVIDER_OUTPUTS["deepseek"])
    assert len(rows) == 6
    assert all(row["response_obtained"] is True for row in rows)
    assert all(row["retry_eligible"] is False for row in rows)
    assert all(row["provider_tools_enabled"] is False for row in rows)
    assert all(row["external_effects_enabled"] is False for row in rows)
    assert all(row["online_forbidden_fields_present"] is False for row in rows)
    assert {row["ask_count"] for row in rows} == {1}
    assert {row["deny_count"] for row in rows} == {1}


def test_only_pre_response_failure_can_be_explicitly_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _output_patch(monkeypatch, tmp_path / "lean")
    canary = runner._select_stage(runner._load_plan("deepseek"), "canary")
    failed_key = str(canary[0]["work_key"])
    first_dispatcher = _Dispatcher(fail_once={failed_key})
    first = runner.run_provider(
        "deepseek",
        stage="canary",
        credential_loader=lambda: {},
        dispatcher_factory=_factory(first_dispatcher),
    )
    without_retry = runner.run_provider(
        "deepseek",
        stage="canary",
        credential_loader=lambda: {},
        dispatcher_factory=lambda *_: pytest.fail("retry lacked explicit flag"),
    )
    retry_dispatcher = _Dispatcher()
    retried = runner.run_provider(
        "deepseek",
        stage="canary",
        retry_failed=True,
        credential_loader=lambda: {},
        dispatcher_factory=_factory(retry_dispatcher),
    )
    rows = _rows(runner.PROVIDER_OUTPUTS["deepseek"])
    failed_rows = [row for row in rows if row["work_key"] == failed_key]
    assert first["executed"] == 6
    assert without_retry["executed"] == 0
    assert retried["executed"] == retried["completed"] == 1
    assert [row["attempt"] for row in failed_rows] == [1, 2]
    assert failed_rows[0]["response_obtained"] is False
    assert failed_rows[0]["retry_eligible"] is True
    assert failed_rows[0]["included_in_primary_itt"] is False
    assert failed_rows[1]["response_obtained"] is True
    assert retry_dispatcher.calls == [failed_key]


def test_gemini_policy_stays_free_and_has_no_paid_ceiling() -> None:
    policy = runner._gemini_policy()
    assert policy["gemini"]["billing_tier"] == "free"
    assert policy["gemini"]["allow_paid_tier"] is False
    assert policy["gemini"]["monetary_hard_limit_usd"] == 0.0
    assert policy["gemini"]["local_batch_caps"] == runner.GEMINI_FREE_CAPS
    assert policy["execution_authorization"]["formal_execution_authorized"] is False


def test_deepseek_config_binds_exact_lean_model() -> None:
    policy = runner.build_role_policy(runner.load_public_policy(), "primary")
    values = {
        "M3_FRONTIER_API_CONSENT": "yes_for_network_smoke",
        "DEEPSEEK_API_KEY": "unit-test-placeholder-not-a-real-key",
        "FRONTIER_DEEPSEEK_MODEL_ID": "deepseek-v4-pro",
        "FRONTIER_DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    }
    assert runner._deepseek_api_key(values, policy) == values["DEEPSEEK_API_KEY"]
    values["FRONTIER_DEEPSEEK_MODEL_ID"] = "deepseek-v4-flash"
    with pytest.raises(runner.LeanEmpiricalRunnerError):
        runner._deepseek_api_key(values, policy)


def test_gemini_retry_uses_a_separate_internal_call_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _output_patch(monkeypatch, tmp_path / "lean")
    canary = runner._select_stage(runner._load_plan("gemini"), "canary")
    failed_key = str(canary[0]["work_key"])
    runner.run_provider(
        "gemini",
        stage="canary",
        credential_loader=lambda: {},
        dispatcher_factory=_factory(_Dispatcher(fail_once={failed_key})),
    )
    captured: list[runner.LeanPermit] = []

    def factory(permit: runner.LeanPermit, provider_id: str) -> _Dispatcher:
        assert provider_id == "gemini"
        captured.append(permit)
        return _Dispatcher()

    summary = runner.run_provider(
        "gemini",
        stage="canary",
        retry_failed=True,
        credential_loader=lambda: {},
        dispatcher_factory=factory,
    )
    assert summary["executed"] == summary["completed"] == 1
    assert captured[0].call_path.name == "gemini_call_events.recovery2.jsonl"
    assert captured[0].attempt_by_work_key == {failed_key: 2}


def test_second_pre_response_failure_is_terminal_in_itt(tmp_path: Path) -> None:
    work_item = runner._select_stage(runner._load_plan("gemini"), "canary")[0]
    record = runner._failure_record(
        work_item,
        RuntimeError("synthetic repeated no-response failure"),
        attempt=2,
        trace_path=tmp_path / "absent-trace.jsonl",
    )
    assert record["operational_status"] == "repeated_pre_response_failure"
    assert record["response_obtained"] is False
    assert record["retry_eligible"] is False
    assert record["included_in_primary_itt"] is True


def test_runtime_returned_provider_failure_without_response_is_recoverable(
    tmp_path: Path,
) -> None:
    work_item = runner._select_stage(runner._load_plan("gemini"), "canary")[0]
    result = {
        "unsafe_effect": False,
        "task_completion": False,
        "operational_status": "provider_failure",
        "runtime_visibility_events": [],
        "latency_ms": {},
        "token_usage": {},
        "provider_trace_bundle": {"activated_attestations": [], "usage_summary": {}},
    }
    first = runner._success_record(
        work_item,
        result,
        {"forbidden_fields_present": False},
        attempt=1,
        trace_path=tmp_path / "absent.jsonl",
    )
    second = runner._success_record(
        work_item,
        result,
        {"forbidden_fields_present": False},
        attempt=2,
        trace_path=tmp_path / "absent2.jsonl",
    )
    assert first["operational_status"] == "pre_response_provider_failure"
    assert first["retry_eligible"] is True
    assert first["included_in_primary_itt"] is False
    assert second["operational_status"] == "repeated_pre_response_failure"
    assert second["retry_eligible"] is False
    assert second["included_in_primary_itt"] is True


def test_legacy_no_response_provider_failure_is_normalized_for_recovery() -> None:
    latest = runner._latest_by_work_key(
        [
            {
                "work_key": "legacy",
                "attempt": 1,
                "response_obtained": False,
                "operational_status": "provider_failure",
                "retry_eligible": False,
                "included_in_primary_itt": True,
            }
        ]
    )["legacy"]
    assert latest["operational_status"] == "pre_response_provider_failure"
    assert latest["retry_eligible"] is True
    assert latest["included_in_primary_itt"] is False


def test_rate_limit_bundle_pauses_and_allows_three_quota_days(tmp_path: Path) -> None:
    work_item = runner._select_stage(runner._load_plan("gemini"), "canary")[0]
    result = {
        "unsafe_effect": False,
        "task_completion": False,
        "operational_status": "provider_failure",
        "runtime_visibility_events": [],
        "latency_ms": {},
        "token_usage": {},
        "provider_trace_bundle": {
            "activated_attestations": [],
            "usage_summary": {},
            "failures": [{"status": "paused"}],
        },
    }
    second_day = runner._success_record(
        work_item,
        result,
        {"forbidden_fields_present": False},
        attempt=2,
        trace_path=tmp_path / "missing.jsonl",
    )
    third_day = runner._success_record(
        work_item,
        result,
        {"forbidden_fields_present": False},
        attempt=3,
        trace_path=tmp_path / "missing3.jsonl",
    )
    assert second_day["operational_status"] == "pre_response_rate_limited"
    assert second_day["retry_eligible"] is True
    assert third_day["operational_status"] == (
        "rate_limit_exhausted_after_three_quota_days"
    )
    assert third_day["retry_eligible"] is False
    assert third_day["included_in_primary_itt"] is True


def test_paused_legacy_work_key_is_reclassified_from_call_ledger() -> None:
    latest = runner._latest_by_work_key(
        [
            {
                "work_key": "paused",
                "attempt": 1,
                "response_obtained": False,
                "operational_status": "provider_failure",
                "retry_eligible": False,
                "included_in_primary_itt": True,
            }
        ],
        paused_work_keys={"paused"},
    )["paused"]
    assert latest["operational_status"] == "pre_response_rate_limited"
    assert latest["retry_eligible"] is True
    assert latest["included_in_primary_itt"] is False
