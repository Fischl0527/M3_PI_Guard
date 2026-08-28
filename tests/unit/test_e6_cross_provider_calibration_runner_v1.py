from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import pytest

import experiments.paper_v2.e6_cross_provider_calibration_runner_v1 as runner
from experiments.paper_v2.formal_condition_executors import (
    E6_CALIBRATION_CONDITIONS,
    INCREMENTAL_FACTOR_CONDITIONS,
    build_e6_calibration_condition_dispatcher,
    build_incremental_condition_dispatcher,
)


class _Runtime:
    def execute(self, *_: Any) -> Mapping[str, Any]:
        raise AssertionError("dispatcher construction must not execute")


class _Evaluator:
    def evaluate(self, *_: Any) -> Mapping[str, Any]:
        raise AssertionError("dispatcher construction must not evaluate")


class _Dispatcher:
    def __init__(
        self,
        *,
        fail_once: set[str] | None = None,
        returned_model: str | None = None,
    ) -> None:
        self.fail_once = fail_once or set()
        self.returned_model = returned_model
        self.calls: list[str] = []

    def execute(
        self,
        work_item: Mapping[str, Any],
        state: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del state
        key = str(work_item["work_key"])
        self.calls.append(key)
        if key in self.fail_once:
            self.fail_once.remove(key)
            raise RuntimeError("synthetic response-less transport failure")
        model = self.returned_model or str(work_item["model_id"])
        return {
            "unsafe_effect": True,
            "task_completion": False,
            "operational_status": "completed",
            "runtime_visibility_events": [
                {
                    "step": 1,
                    "parse_ok": True,
                    "action_proposal": {
                        "tool": "send_email",
                        "arguments_sha256": "b" * 64,
                    },
                    "guard_decision": {
                        "decision": "ASK",
                        "reason_code": "independent_confirmation_required",
                        "violated_constraints": ["confirmation"],
                    },
                    "controller_evidence": {
                        "source_sha256": "c" * 64,
                    },
                }
            ],
            "latency_ms": {"total": 12.5, "model": 10.0},
            "token_usage": {"input": 10, "output": 4, "total": 14},
            "provider_trace_bundle": {
                "activated_attestations": [
                    {
                        "client_request_id": f"m3req-{key[:16]}",
                        "payload_sha256": "a" * 64,
                        "provider_request_id": None,
                        "provider_response_id": f"response-{key[:16]}",
                        "model_id": model,
                    }
                ],
                "usage_summary": {"cumulative_cost_cny": 0.001},
            },
            "recorded_at": "2026-08-28T09:00:00+08:00",
        }


class _FatalDispatcher:
    def execute(self, *_: Any) -> Mapping[str, Any]:
        class ProviderIdentityError(RuntimeError):
            pass

        raise ProviderIdentityError("synthetic identity drift")


def _patch_output(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(runner, "OUTPUT_ROOT", root)


def _rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_canary(
    provider_id: str,
    *,
    dispatcher: _Dispatcher,
    started_at: str = "2026-08-28T09:00:00+08:00",
) -> dict[str, Any]:
    return runner.run_window(
        provider_id,
        "W1",
        canary_only=True,
        credential_loader=lambda: {},
        dispatcher_factory=lambda _permit, _provider, _rows: dispatcher,
        started_at=started_at,
    )


def test_frozen_plans_are_window_balanced_and_provider_isolated() -> None:
    deepseek = runner._load_plan("deepseek")
    gemini = runner._load_plan("gemini")

    assert len(deepseek) == 1_080
    assert len(gemini) == 540
    assert {row["underlying_task_id"] for row in gemini}.issubset(
        {row["underlying_task_id"] for row in deepseek}
    )
    for provider_id, rows in (("deepseek", deepseek), ("gemini", gemini)):
        for window in runner.WINDOWS:
            selected = [row for row in rows if row["replicate_window"] == window]
            assert len(selected) == runner.EXPECTED_WINDOW_COUNTS[provider_id]
            assert sum(row["formal_prefix"] is True for row in selected) == 12
            assert {row["condition_id"] for row in selected} == set(
                E6_CALIBRATION_CONDITIONS
            )
            assert all(
                row["max_provider_calls"]
                == (
                    16
                    if row["condition_id"]
                    == "strongest_peer_reviewed_structural_baseline"
                    else 8
                )
                for row in selected
            )
    assert runner._provider_root("deepseek") != runner._provider_root("gemini")


def test_e6_dispatcher_adds_controls_without_changing_e1_to_e5_scope() -> None:
    e6 = build_e6_calibration_condition_dispatcher(
        runtime=_Runtime(), evaluator=_Evaluator()
    )
    incremental = build_incremental_condition_dispatcher(
        runtime=_Runtime(), evaluator=_Evaluator()
    )

    assert set(e6.registered_conditions()) == set(E6_CALIBRATION_CONDITIONS)
    assert set(incremental.registered_conditions()) == set(
        INCREMENTAL_FACTOR_CONDITIONS
    )
    assert len(e6.registered_conditions()) == 6
    assert len(incremental.registered_conditions()) == 4


@pytest.mark.parametrize("provider_id", ["deepseek", "gemini"])
def test_twelve_row_gate_is_outcome_blind_and_success_is_never_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider_id: str,
) -> None:
    _patch_output(monkeypatch, tmp_path / "e6")
    first = _run_canary(provider_id, dispatcher=_Dispatcher())
    second = runner.run_window(
        provider_id,
        "W1",
        canary_only=True,
        credential_loader=lambda: pytest.fail("credentials were reloaded"),
        dispatcher_factory=lambda *_: pytest.fail("successful rows were rerun"),
    )
    records = _rows(runner._raw_path(provider_id))
    gate = json.loads(
        runner._gate_path(provider_id, "W1").read_text(encoding="utf-8")
    )

    assert first["executed"] == 12
    assert first["window_gate_passed"] is True
    assert second["executed"] == 0
    assert gate["scientific_outcomes_inspected"] is False
    assert gate["parseable_terminal_rows"] == 12
    assert len(records) == 12
    assert all(row["terminal_status"] is True for row in records)
    assert all(row["provider_call_count"] == 1 for row in records)
    assert all(row["proposal_digest"] for row in records)
    assert all(row["guard_decision"]["decision"] == "ASK" for row in records)
    assert all(row["provider_tools_enabled"] is False for row in records)
    assert all(row["external_effects_enabled"] is False for row in records)
    if provider_id == "gemini":
        assert all(row["cost"]["amount"] == 0.0 for row in records)
        assert all(
            row["free_tier_attestation"]["paid_fallback_enabled"] is False
            for row in records
        )


def test_identity_drift_fails_the_formal_prefix_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output(monkeypatch, tmp_path / "e6")
    value = _run_canary(
        "gemini",
        dispatcher=_Dispatcher(returned_model="different-model"),
    )
    assert value["window_gate_passed"] is False
    gate = runner.evaluate_window_gate("gemini", "W1")
    assert gate["exact_returned_model"] is False
    assert gate["complete_request_chain"] is False


def test_fatal_identity_error_stops_provider_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output(monkeypatch, tmp_path / "e6")
    first = runner.run_window(
        "deepseek",
        "W1",
        canary_only=True,
        credential_loader=lambda: {},
        dispatcher_factory=lambda *_: _FatalDispatcher(),
        started_at="2026-08-28T09:00:00+08:00",
    )
    record = _rows(runner._raw_path("deepseek"))[0]
    assert first["executed"] == 1
    assert record["operational_status"] == "contract_failure"
    assert record["terminal_status"] is True
    assert record["retry_eligible"] is False
    assert runner._provider_stop_path("deepseek").is_file()
    with pytest.raises(runner.E6CalibrationRunnerError, match="fatal contract"):
        _run_canary("deepseek", dispatcher=_Dispatcher())


def test_only_explicit_failed_key_gets_one_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output(monkeypatch, tmp_path / "e6")
    prefix = [
        row
        for row in runner._window_rows("deepseek", "W1")
        if row["formal_prefix"] is True
    ]
    failed_key = str(prefix[0]["work_key"])
    first = _run_canary(
        "deepseek",
        dispatcher=_Dispatcher(fail_once={failed_key}),
    )
    assert first["executed"] == 1
    failed = _rows(runner._raw_path("deepseek"))[0]
    assert failed["response_obtained"] is False
    assert failed["retry_eligible"] is True
    assert failed["terminal_status"] is False

    with pytest.raises(
        runner.E6CalibrationRunnerError,
        match="explicit failed-key recovery",
    ):
        _run_canary("deepseek", dispatcher=_Dispatcher())

    retry = runner.run_window(
        "deepseek",
        "W1",
        canary_only=True,
        retry_failed_work_keys=(failed_key,),
        credential_loader=lambda: {},
        dispatcher_factory=lambda *_: _Dispatcher(),
    )
    assert retry["executed"] == 1
    resumed = _run_canary("deepseek", dispatcher=_Dispatcher())
    assert resumed["executed"] == 11
    assert resumed["window_gate_passed"] is True

    attempts = [
        row["attempt"]
        for row in _rows(runner._raw_path("deepseek"))
        if row["work_key"] == failed_key
    ]
    assert attempts == [1, 2]
    with pytest.raises(runner.E6CalibrationRunnerError, match="cannot be retried"):
        runner.run_window(
            "deepseek",
            "W1",
            canary_only=True,
            retry_failed_work_keys=(failed_key,),
            credential_loader=lambda: {},
            dispatcher_factory=lambda *_: _Dispatcher(),
        )


def test_gemini_window_seal_closes_unavailable_rows_without_fake_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output(monkeypatch, tmp_path / "e6")
    start = "2026-08-28T09:00:00+08:00"
    _run_canary("gemini", dispatcher=_Dispatcher(), started_at=start)
    completed = (
        datetime.fromisoformat(start) + timedelta(hours=12)
    ).isoformat()
    seal = runner.seal_window("gemini", "W1", completed_at=completed)
    latest = runner._latest_records("gemini")

    assert seal["terminal_rows"] == 180
    assert seal["response_bearing_rows"] == 12
    assert seal["provider_window_unavailable_rows"] == 168
    assert seal["gemini_formal_inference_window_eligible"] is False
    assert len(latest) == 180
    unavailable = [
        row
        for row in latest.values()
        if row["operational_status"] == "provider_window_unavailable"
    ]
    assert len(unavailable) == 168
    assert all(row["attempt"] == 0 for row in unavailable)
    assert all(row["included_in_primary_itt"] is True for row in unavailable)
    assert all(row["retry_eligible"] is False for row in unavailable)
    assert all(row["cost"]["amount"] == 0.0 for row in unavailable)


def test_deepseek_cannot_seal_an_incomplete_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output(monkeypatch, tmp_path / "e6")
    _run_canary("deepseek", dispatcher=_Dispatcher())
    with pytest.raises(
        runner.E6CalibrationRunnerError,
        match="cannot seal with nonterminal",
    ):
        runner.seal_window(
            "deepseek",
            "W1",
            completed_at="2026-08-28T10:00:00+08:00",
        )


def test_next_window_requires_seal_and_prespecified_timing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output(monkeypatch, tmp_path / "e6")
    runner._ensure_window_started(
        "deepseek", "W1", started_at="2026-08-28T09:00:00+08:00"
    )
    with pytest.raises(runner.E6CalibrationRunnerError, match="not sealed"):
        runner._ensure_window_started(
            "deepseek", "W2", started_at="2026-08-29T09:00:00+08:00"
        )
    runner._write_json(
        runner._seal_path("deepseek", "W1"),
        {
            "window_started_at": "2026-08-28T09:00:00+08:00",
            "status": "sealed",
        },
    )
    value = runner._ensure_window_started(
        "deepseek", "W2", started_at="2026-08-29T09:30:00+08:00"
    )
    assert value["replicate_window"] == "W2"
    assert value["replicate_index"] == 2


def test_cli_requires_one_stage_and_keeps_retry_separate_from_replicate() -> None:
    args = runner.build_parser().parse_args(
        [
            "--provider",
            "gemini",
            "--window",
            "W3",
            "--resume-pending-only",
            "--retry-failed-work-key",
            "key-1",
        ]
    )
    assert args.provider == "gemini"
    assert args.window == "W3"
    assert args.resume_pending_only is True
    assert args.retry_failed_work_key == ["key-1"]
