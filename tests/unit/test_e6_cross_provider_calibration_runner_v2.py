from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

import experiments.paper_v2.e6_cross_provider_calibration_analysis_v1 as analysis_v1
import experiments.paper_v2.e6_cross_provider_calibration_runner_v2 as runner
from experiments.paper_v2.official_provider_executor import (
    ProviderIdentityError,
    ProviderLedgerError,
    ProviderPausedError,
    ProviderPayloadError,
    ProviderTransportError,
    ProviderUsageError,
)


class _Dispatcher:
    def __init__(
        self,
        *,
        failure: Exception | None = None,
        runtime_provider_failures: int = 0,
        runtime_failure_class: str = "ProviderTransportError",
    ) -> None:
        self.failure = failure
        self.runtime_provider_failures = runtime_provider_failures
        self.runtime_failure_class = runtime_failure_class
        self.calls = 0

    def execute(
        self, work_item: Mapping[str, Any], state: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        del state
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        provider_failure = self.calls <= self.runtime_provider_failures
        key = str(work_item["work_key"])
        model = str(work_item["model_id"])
        event: dict[str, Any] = {
            "step": 2 if provider_failure else 1,
            "parse_ok": not provider_failure,
            "action_proposal": {
                "tool": "send_email",
                "arguments_sha256": "b" * 64,
            },
            "guard_decision": {
                "decision": "ASK",
                "reason_code": "independent_confirmation_required",
                "violated_constraints": ["confirmation"],
            },
            "controller_evidence": {"source_sha256": "c" * 64},
        }
        if provider_failure:
            event.update(
                {
                    "parse_error_code": "provider_failure",
                    "observation": {
                        "status": "provider_failure",
                        "error_type": self.runtime_failure_class,
                    },
                }
            )
        return {
            "unsafe_effect": False,
            "task_completion": False,
            "operational_status": (
                "provider_failure" if provider_failure else "completed"
            ),
            "runtime_visibility_events": [event],
            "latency_ms": {"total": 2.0, "model": 1.0},
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
            "recorded_at": "2026-08-29T23:00:00+08:00",
        }


def _patch_offline(
    monkeypatch: pytest.MonkeyPatch, root: Path
) -> None:
    monkeypatch.setattr(runner, "OUTPUT_ROOT", root)
    monkeypatch.setattr(runner, "_now", lambda: "2026-08-29T23:00:00+08:00")
    monkeypatch.setattr(
        runner.lean,
        "_hydrate_work_item",
        lambda item: (
            dict(item),
            {"trusted_user_request": "offline"},
            {
                "forbidden_fields_present": False,
                "visible_field_names": ["trusted_user_request"],
            },
        ),
    )


def _raw(provider_id: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in runner._raw_path(provider_id)
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def _run(
    provider_id: str,
    dispatcher: _Dispatcher,
    *,
    retry_key: str | None = None,
    captures: list[Any] | None = None,
) -> dict[str, Any]:
    def factory(permit: Any, *_: Any) -> _Dispatcher:
        if captures is not None:
            captures.append(permit)
        if type(dispatcher.failure) is ProviderTransportError:
            work_key = str(permit.work_items[0]["work_key"])
            trace_path = runner.lean._provider_trace_path(permit, work_key)
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            trace_path.write_text(
                json.dumps(
                    {
                        "event": {
                            "event_type": "started",
                            "commitment": {
                                "client_request_id": f"m3req-{work_key[:16]}",
                                "payload_sha256": "d" * 64,
                                "model_id": permit.work_items[0]["model_id"],
                            },
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        return dispatcher

    return runner.run_window(
        provider_id,
        runner.EXECUTION_BLOCK_ID,
        canary_only=True,
        retry_failed_work_keys=(() if retry_key is None else (retry_key,)),
        credential_loader=lambda: {},
        dispatcher_factory=factory,
    )


def test_v2_projects_new_identity_without_mutating_v1_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    monkeypatch.setattr(
        runner.e6_v1,
        "_provider_stop_path",
        lambda *_: pytest.fail("v1 stop path was read"),
    )

    row = runner._window_rows("gemini", runner.EXECUTION_BLOCK_ID)[0]

    assert row["study_id"] == runner.STUDY_ID
    assert row["run_id"] == "e6-v2-gemini-B1"
    assert row["execution_identity"] == runner._execution_identity("gemini", "B1")
    assert row["execution_identity"] != runner.e6_v1._load_plan("gemini")[0][
        "execution_identity"
    ]
    assert runner._provider_stop_path("gemini").name == "provider_stop_v2.json"
    assert runner.OUTPUT_ROOT != runner.e6_v1.OUTPUT_ROOT
    assert row["source_replicate_window"] == "W3"
    assert row["replicate_window"] == "B1"
    assert row["replicate_index"] == 1
    assert row["sample_role"] == "risk_enriched_activity_diagnostic"
    assert row["work_key"].startswith("e6-v2-immediate__")


@pytest.mark.parametrize(
    ("benchmark", "expected"),
    [("agentdojo-v1", True), ("m3-v2", False)],
)
def test_source_pinned_label_allowance_is_benchmark_scoped(
    benchmark: str, expected: bool
) -> None:
    assert runner._allow_pinned_synthetic_labels(benchmark) is expected


def test_source_pinned_label_allowance_rejects_unknown_benchmark() -> None:
    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="unsupported benchmark",
    ):
        runner._allow_pinned_synthetic_labels("unknown-benchmark")


@pytest.mark.parametrize("window", ["W1", "W2"])
def test_v2_rejects_w1_w2_before_credentials_dispatch_or_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    window: str,
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="diagnostic-block B1 only",
    ):
        runner.run_window(
            "deepseek",
            window,
            canary_only=True,
            credential_loader=lambda: pytest.fail("credentials were loaded"),
            dispatcher_factory=lambda *_: pytest.fail("dispatcher was built"),
        )

    assert not runner.OUTPUT_ROOT.exists()


def test_immediate_block_has_no_v1_seal_or_clock_eligibility_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    monkeypatch.setattr(
        runner.e6_v1,
        "_seal_path",
        lambda *_: pytest.fail("v1 seal was read"),
    )
    monkeypatch.setattr(runner, "_now", lambda: "2099-01-01T00:00:00+08:00")

    value = _run("gemini", _Dispatcher())
    rows = _raw("gemini")

    assert value["executed"] == 12
    assert len(rows) == 12
    assert all(row["execution_block_role"] == runner.EXECUTION_BLOCK_ROLE for row in rows)
    assert all(row["execution_block_id"] == "B1" for row in rows)
    assert all(row["replicate_window"] == "B1" for row in rows)
    assert all(row["replicate_index"] == 1 for row in rows)
    assert all(
        row["sample_role"] == "risk_enriched_activity_diagnostic" for row in rows
    )
    assert all(row["source_replicate_window"] == "W3" for row in rows)
    assert all(row["source_replicate_index"] == 3 for row in rows)
    assert all(row["temporal_replication_claim"] is False for row in rows)


def test_immediate_block_resume_is_not_clock_gated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    first = _run("deepseek", _Dispatcher())
    assert first["executed"] == 12

    monkeypatch.setattr(runner, "_now", lambda: "2099-01-01T00:00:00+08:00")
    resumed = _run("deepseek", _Dispatcher())
    assert resumed["executed"] == 0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("gate_passed", False, "does not reproduce"),
        ("provider_id", "gemini", "gate identity drift"),
    ],
)
def test_resume_rejects_stale_or_foreign_persisted_gate_before_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    first = _run("deepseek", _Dispatcher())
    assert first["window_gate_passed"] is True
    gate_path = runner._gate_path("deepseek", runner.EXECUTION_BLOCK_ID)
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate[field] = value
    gate_path.write_text(
        json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(runner.E6CalibrationRunnerV2Error, match=message):
        runner.run_window(
            "deepseek",
            runner.EXECUTION_BLOCK_ID,
            canary_only=False,
            credential_loader=lambda: pytest.fail("credentials were loaded"),
            dispatcher_factory=lambda *_: pytest.fail("dispatcher was built"),
        )


def test_configuration_preflight_failure_does_not_start_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")

    with pytest.raises(RuntimeError, match="synthetic config failure"):
        runner.run_window(
            "deepseek",
            runner.EXECUTION_BLOCK_ID,
            canary_only=True,
            credential_loader=lambda: (_ for _ in ()).throw(
                RuntimeError("synthetic config failure")
            ),
            dispatcher_factory=lambda *_: pytest.fail("dispatcher was built"),
        )

    assert not runner._window_state_path(
        "deepseek", runner.EXECUTION_BLOCK_ID
    ).exists()
    assert not runner.OUTPUT_ROOT.exists()


def test_v1_temporal_analyzer_rejects_non_temporal_block() -> None:
    row = runner._window_rows("deepseek", runner.EXECUTION_BLOCK_ID)[0]

    with pytest.raises(
        analysis_v1.E6AnalysisError,
        match="non-temporal diagnostic execution blocks",
    ):
        analysis_v1._merge_plan_and_raw([row], [])


def test_generic_response_less_attempt_two_is_isolated_and_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    captures: list[Any] = []
    first = _run(
        "gemini",
        _Dispatcher(failure=ProviderTransportError("synthetic transport")),
        captures=captures,
    )
    failed = _raw("gemini")[0]
    key = str(failed["work_key"])

    assert first["executed"] == 1
    assert failed["attempt"] == 1
    assert failed["response_obtained"] is False
    assert failed["retry_eligible"] is True
    assert failed["terminal_status"] is False
    assert not runner._provider_stop_path("gemini").exists()

    retry = _run("gemini", _Dispatcher(), retry_key=key, captures=captures)
    records = [row for row in _raw("gemini") if row["work_key"] == key]

    assert retry["executed"] == 1
    assert [row["attempt"] for row in records] == [1, 2]
    assert records[-1]["physical_attempt_namespace"] == 2
    assert records[-1]["terminal_status"] is True
    assert records[-1]["retry_eligible"] is False
    assert captures[0].call_path != captures[1].call_path
    assert captures[0].trace_root != captures[1].trace_root
    assert "generic_recovery_attempt2" in str(captures[1].call_path)

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="unique unresolved work key",
    ):
        _run("gemini", _Dispatcher(), retry_key=key)


def test_response_less_failure_without_payload_commitment_is_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")

    value = runner.run_window(
        "deepseek",
        runner.EXECUTION_BLOCK_ID,
        canary_only=True,
        credential_loader=lambda: {},
        dispatcher_factory=lambda *_: _Dispatcher(
            failure=ProviderTransportError("failed before trace commitment")
        ),
    )
    row = _raw("deepseek")[0]

    assert value["executed"] == 1
    assert row["provider_requests"] == []
    assert row["response_obtained"] is False
    assert row["retry_eligible"] is False
    assert row["terminal_status"] is True
    assert row["included_in_primary_itt"] is True
    assert row["protocol_terminal_reason"] == "no_pretransport_payload_commitment"
    assert not runner._provider_stop_path("deepseek").exists()
    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="unique unresolved work key",
    ):
        _run("deepseek", _Dispatcher(), retry_key=str(row["work_key"]))


def test_attempt_two_failure_is_terminal_and_attempt_three_is_impossible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run(
        "deepseek",
        _Dispatcher(failure=ProviderTransportError("first failure")),
    )
    key = str(_raw("deepseek")[0]["work_key"])
    _run(
        "deepseek",
        _Dispatcher(failure=ProviderTransportError("second failure")),
        retry_key=key,
    )
    records = [row for row in _raw("deepseek") if row["work_key"] == key]

    assert [row["attempt"] for row in records] == [1, 2]
    assert records[-1]["terminal_status"] is True
    assert records[-1]["included_in_primary_itt"] is True
    assert records[-1]["retry_eligible"] is False
    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="unique unresolved work key",
    ):
        _run("deepseek", _Dispatcher(), retry_key=key)


def test_response_bearing_success_cannot_be_recovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run("deepseek", _Dispatcher())
    key = str(_raw("deepseek")[0]["work_key"])

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="unique unresolved work key",
    ):
        _run("deepseek", _Dispatcher(), retry_key=key)


def test_any_response_evidence_blocks_generic_recovery() -> None:
    row = {
        "attempt": 1,
        "response_obtained": False,
        "returned_models": [],
        "provider_requests": [
            {
                "provider_response_id": "response-already-observed",
                "returned_model": "deepseek-v4-pro",
            }
        ],
        "retry_eligible": True,
        "terminal_status": False,
        "operational_status": "pre_response_transport_failure",
    }

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="response-bearing work",
    ):
        runner._validate_generic_recovery_history([row])


def test_generic_recovery_requires_exactly_one_unresolved_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run(
        "deepseek",
        _Dispatcher(failure=ProviderTransportError("first failure")),
    )
    first = _raw("deepseek")[0]
    second = dict(first)
    second_plan = runner._window_rows(
        "deepseek", runner.EXECUTION_BLOCK_ID
    )[1]
    second.update(
        {
            "work_key": second_plan["work_key"],
            "case_id": second_plan["case_id"],
            "condition_id": second_plan["condition_id"],
            "underlying_task_id": second_plan["underlying_task_id"],
            "source_v1_work_key": second_plan["source_v1_work_key"],
        }
    )
    runner.lean._append_jsonl(runner._raw_path("deepseek"), second)

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="unique unresolved work key",
    ):
        _run("deepseek", _Dispatcher(), retry_key=str(first["work_key"]))


def test_raw_execution_identity_drift_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run(
        "deepseek",
        _Dispatcher(failure=ProviderTransportError("synthetic transport")),
    )
    row = _raw("deepseek")[0]
    row["execution_identity"] = "0" * 64
    runner._raw_path("deepseek").write_text(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="execution identity does not match",
    ):
        runner._execution_history("deepseek")


def test_unknown_raw_record_kind_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run("deepseek", _Dispatcher())
    row = _raw("deepseek")[0]
    row["record_kind"] = "window_closure"
    runner._raw_path("deepseek").write_text(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="raw record kind drift",
    ):
        runner._execution_history("deepseek")


def test_429_uses_manual_path_and_does_not_write_fatal_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run(
        "gemini",
        _Dispatcher(failure=ProviderPausedError("synthetic 429")),
    )
    row = _raw("gemini")[0]

    assert row["operational_status"] == "pre_response_rate_limited"
    assert row["manual_429_recovery_required"] is False
    assert row["underlying_manual_429_ledger_semantics_unchanged"] is True
    assert row["retry_eligible"] is False
    assert row["terminal_status"] is True
    assert row["protocol_terminal_reason"] == "diagnostic_block_429_terminal"
    assert not runner._provider_stop_path("gemini").exists()
    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="diagnostic terminal",
    ):
        _run("gemini", _Dispatcher(), retry_key=str(row["work_key"]))


@pytest.mark.parametrize(
    "failure",
    [
        ProviderIdentityError("synthetic identity drift"),
        ProviderPayloadError("synthetic payload drift"),
        ProviderUsageError("synthetic usage drift"),
        ProviderLedgerError("synthetic ledger drift"),
        type("ProviderSafetyError", (RuntimeError,), {})("synthetic safety drift"),
    ],
)
def test_contract_error_writes_only_v2_fatal_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run(
        "deepseek",
        _Dispatcher(failure=failure),
    )
    row = _raw("deepseek")[0]

    assert row["operational_status"] == "contract_failure"
    assert row["terminal_status"] is True
    assert runner._provider_stop_path("deepseek").is_file()
    assert runner._provider_stop_path("deepseek").name == "provider_stop_v2.json"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("provider_id", "gemini", "provider stop identity drift"),
        ("recorded_at", "2026-08-29T22:59:59+08:00", "latest fatal raw"),
        ("work_key", "planned-but-not-fatal", "work key is not planned"),
    ],
)
def test_run_rejects_foreign_stale_or_unplanned_provider_stop_before_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run(
        "deepseek",
        _Dispatcher(failure=ProviderIdentityError("synthetic identity drift")),
    )
    path = runner._provider_stop_path("deepseek")
    stop = json.loads(path.read_text(encoding="utf-8"))
    stop[field] = value
    path.write_text(
        json.dumps(stop, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(runner.E6CalibrationRunnerV2Error, match=message):
        runner.run_window(
            "deepseek",
            runner.EXECUTION_BLOCK_ID,
            canary_only=True,
            credential_loader=lambda: pytest.fail("credentials were loaded"),
            dispatcher_factory=lambda *_: pytest.fail("dispatcher was built"),
        )


def test_run_rejects_provider_stop_without_matching_raw_before_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    planned = runner._window_rows("deepseek", runner.EXECUTION_BLOCK_ID)[0]
    runner._write_json(
        runner._provider_stop_path("deepseek"),
        {
            "schema_version": runner.PROVIDER_STOP_SCHEMA_VERSION,
            "study_id": runner.STUDY_ID,
            "provider_id": "deepseek",
            "replicate_window": runner.EXECUTION_BLOCK_ID,
            "execution_block_id": runner.EXECUTION_BLOCK_ID,
            "execution_block_role": runner.EXECUTION_BLOCK_ROLE,
            "temporal_replication_claim": False,
            "work_key": planned["work_key"],
            "attempt": 1,
            "error_type": "ProviderIdentityError",
            "operational_status": "contract_failure",
            "status": "stopped_fatal_contract_boundary",
            "fatal_boundary": True,
            "terminal_status": True,
            "recorded_at": "2026-08-29T23:00:00+08:00",
        },
    )

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="no matching fatal raw record",
    ):
        runner.run_window(
            "deepseek",
            runner.EXECUTION_BLOCK_ID,
            canary_only=True,
            credential_loader=lambda: pytest.fail("credentials were loaded"),
            dispatcher_factory=lambda *_: pytest.fail("dispatcher was built"),
        )


def test_runtime_provider_failure_is_counted_as_systemic_gate_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    value = _run(
        "deepseek",
        _Dispatcher(runtime_provider_failures=2),
    )
    gate = json.loads(
        runner._gate_path("deepseek", runner.EXECUTION_BLOCK_ID).read_text(
            encoding="utf-8"
        )
    )

    assert value["executed"] == 12
    assert gate["parseable_terminal_rows"] == 10
    assert gate["runtime_provider_failure_rows"] == 2
    failure_rows = [
        row for row in _raw("deepseek") if row["operational_status"] == "provider_failure"
    ]
    assert all(
        row["runtime_failure_diagnostic"]
        == {
            "failure_stage": "provider_call",
            "failure_class": "ProviderTransportError",
            "provider_call_index": 2,
            "http_category": "not_observed",
        }
        for row in failure_rows
    )
    assert gate["systemic_failure_counts"] == {
        "runtime_provider_failure:ProviderTransportError": 2
    }
    assert gate["no_repeated_systemic_error"] is False
    assert gate["gate_passed"] is False


def test_response_bearing_fatal_runtime_failure_stops_after_one_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")

    value = _run(
        "deepseek",
        _Dispatcher(
            runtime_provider_failures=2,
            runtime_failure_class="ProviderIdentityError",
        ),
    )
    rows = _raw("deepseek")

    assert value["executed"] == 1
    assert value["stopped_after_fatal_boundary"] is True
    assert len(rows) == 1
    assert rows[0]["response_obtained"] is True
    assert runner._provider_stop_path("deepseek").is_file()


def test_failed_prefix_seals_remaining_rows_as_technical_gate_not_extended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    run = _run(
        "deepseek",
        _Dispatcher(runtime_provider_failures=4),
    )
    assert run["executed"] == 12
    assert run["window_gate_passed"] is False
    started_state = json.loads(
        runner._window_state_path(
            "deepseek", runner.EXECUTION_BLOCK_ID
        ).read_text(encoding="utf-8")
    )
    assert started_state["execution_block_started_at"] == started_state[
        "window_started_at"
    ]

    seal = runner.seal_block(
        "deepseek",
        runner.EXECUTION_BLOCK_ID,
        completed_at="2026-08-30T00:00:00+08:00",
    )
    rows = _raw("deepseek")
    latest = runner._latest_records("deepseek")

    assert seal["status"] == "sealed"
    assert seal["closure_mode"] == "technical_gate_not_extended"
    assert seal["planned_rows"] == 360
    assert seal["terminal_rows"] == 360
    assert seal["administrative_closure_rows"] == 348
    assert seal["technical_gate_not_extended_rows"] == 348
    assert len(rows) == 360
    assert len(latest) == 360
    assert all(runner._is_terminal(row) for row in latest.values())
    assert all(
        row["temporal_replication_claim"] is False for row in latest.values()
    )
    assert json.loads(
        runner._window_state_path(
            "deepseek", runner.EXECUTION_BLOCK_ID
        ).read_text(encoding="utf-8")
    )["status"] == "sealed"

    with pytest.raises(runner.E6CalibrationRunnerV2Error, match="is sealed"):
        runner.run_window(
            "deepseek",
            runner.EXECUTION_BLOCK_ID,
            canary_only=True,
            credential_loader=lambda: pytest.fail("credentials were loaded"),
            dispatcher_factory=lambda *_: pytest.fail("dispatcher was built"),
        )


def test_seal_rejects_gate_that_does_not_reproduce_from_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run("deepseek", _Dispatcher(runtime_provider_failures=4))
    gate_path = runner._gate_path("deepseek", runner.EXECUTION_BLOCK_ID)
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate["observed_prefix_rows"] = 11
    gate_path.write_text(
        json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="does not reproduce from current raw records",
    ):
        runner.seal_block(
            "deepseek",
            runner.EXECUTION_BLOCK_ID,
            completed_at="2026-08-30T00:00:00+08:00",
        )


def test_existing_seal_fast_return_rejects_summary_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run("deepseek", _Dispatcher(runtime_provider_failures=4))
    runner.seal_block(
        "deepseek",
        runner.EXECUTION_BLOCK_ID,
        completed_at="2026-08-30T00:00:00+08:00",
    )
    seal_path = runner._block_seal_path("deepseek", runner.EXECUTION_BLOCK_ID)
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["planned_rows"] = 359
    seal_path.write_text(
        json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="does not reproduce from current raw records",
    ):
        runner.seal_block("deepseek", runner.EXECUTION_BLOCK_ID)


def test_existing_seal_rejects_closure_mode_tampered_with_matching_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run("deepseek", _Dispatcher(runtime_provider_failures=4))
    runner.seal_block(
        "deepseek",
        runner.EXECUTION_BLOCK_ID,
        completed_at="2026-08-30T00:00:00+08:00",
    )
    seal_path = runner._block_seal_path("deepseek", runner.EXECUTION_BLOCK_ID)
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["closure_mode"] = "provider_unavailable"
    seal["provider_unavailable_evidence"] = {
        "work_key": "synthetic-stale-evidence",
        "attempt": 1,
        "evidence_type": "pre_response_rate_limited",
    }
    seal_path.write_text(
        json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    state_path = runner._window_state_path("deepseek", runner.EXECUTION_BLOCK_ID)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["closure_mode"] = "provider_unavailable"
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="closure semantics drift",
    ):
        runner.seal_block("deepseek", runner.EXECUTION_BLOCK_ID)


def test_existing_provider_unavailable_seal_rejects_evidence_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run(
        "gemini",
        _Dispatcher(failure=ProviderPausedError("synthetic 429")),
    )
    runner.seal_block(
        "gemini",
        runner.EXECUTION_BLOCK_ID,
        provider_unavailable=True,
        completed_at="2026-08-30T00:00:00+08:00",
    )
    seal_path = runner._block_seal_path("gemini", runner.EXECUTION_BLOCK_ID)
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["provider_unavailable_evidence"]["attempt"] = 2
    seal_path.write_text(
        json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="provider-unavailable evidence drift",
    ):
        runner.seal_block("gemini", runner.EXECUTION_BLOCK_ID)


def test_provider_unavailable_seal_closes_untouched_gemini_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    run = _run(
        "gemini",
        _Dispatcher(failure=ProviderPausedError("synthetic 429")),
    )
    assert run["executed"] == 1

    seal = runner.seal_block(
        "gemini",
        runner.EXECUTION_BLOCK_ID,
        provider_unavailable=True,
        completed_at="2026-08-30T00:00:00+08:00",
    )
    latest = runner._latest_records("gemini")

    assert seal["closure_mode"] == "provider_unavailable"
    assert seal["provider_unavailable_evidence"]["evidence_type"] == (
        "pre_response_rate_limited"
    )
    assert seal["terminal_rows"] == 180
    assert seal["administrative_closure_rows"] == 179
    assert seal["provider_block_unavailable_rows"] == 179
    assert len(latest) == 180
    assert all(runner._is_terminal(row) for row in latest.values())
    assert all(
        row.get("free_tier_attestation")
        == {
            "billing_tier": "free",
            "cost_usd": 0.0,
            "paid_fallback_enabled": False,
        }
        for row in latest.values()
    )


def test_provider_unavailable_seal_requires_runtime_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    runner._ensure_window_state("gemini", runner.EXECUTION_BLOCK_ID)

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="requires a 429 terminal or exhausted response-less recovery",
    ):
        runner.seal_block(
            "gemini",
            runner.EXECUTION_BLOCK_ID,
            provider_unavailable=True,
            completed_at="2026-08-30T00:00:00+08:00",
        )

    assert not runner._block_seal_path(
        "gemini", runner.EXECUTION_BLOCK_ID
    ).exists()
    assert not runner._raw_path("gemini").exists()


def test_partial_seal_recovery_preserves_administrative_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run("deepseek", _Dispatcher(runtime_provider_failures=4))
    first = runner.seal_block(
        "deepseek",
        runner.EXECUTION_BLOCK_ID,
        completed_at="2026-08-30T00:00:00+08:00",
    )
    seal_path = runner._block_seal_path("deepseek", runner.EXECUTION_BLOCK_ID)
    seal_path.unlink()

    recovered = runner.seal_block(
        "deepseek",
        runner.EXECUTION_BLOCK_ID,
        completed_at="2026-08-30T00:01:00+08:00",
    )

    assert first["closure_mode"] == "technical_gate_not_extended"
    assert recovered["closure_mode"] == "technical_gate_not_extended"
    assert recovered["technical_gate_not_extended_rows"] == 348


def test_retry_eligible_row_must_be_recovered_or_explicitly_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    _run(
        "deepseek",
        _Dispatcher(failure=ProviderTransportError("synthetic transport")),
    )

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="retry-eligible response-less work remains",
    ):
        runner.seal_block("deepseek", runner.EXECUTION_BLOCK_ID)


def test_manifest_keeps_v1_immutable_and_api_execution_disabled() -> None:
    manifest = json.loads(runner.MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["study_id"] == runner.STUDY_ID
    assert manifest["provider_calls_made"] == 0
    assert manifest["v1_records_modified"] == 0
    assert manifest["status"] == "owner_authorized_b1_live_execution_ready"
    assert manifest["owner_authorization"][
        "requires_offline_completion_gate_before_provider_calls"
    ] is True
    assert manifest["generic_response_less_recovery"][
        "independent_trace_and_call_ledger_namespace"
    ] is True
    assert "work_key" in manifest["new_identities"]
    assert "source_work_key_mapping" in manifest["source_design"]["reuse"]
    assert "logical_work_keys" not in manifest["source_design"]["reuse"]
    assert manifest["source_plan_windows"] == ["W3"]
    assert (
        manifest["prospective_execution_role"]
        == "single_diagnostic_execution_block"
    )
    assert manifest["diagnostic_block_plan_counts"] == {
        "deepseek": 360,
        "gemini": 180,
    }
    assert manifest["execution_block_id"] == "B1"
    assert manifest["gemini_inference_role"] == "single_block_diagnostic_only"
    timing = manifest["execution_timing_policy"]
    assert timing["artificial_start_delay_required"] is False
    assert timing["v1_w2_seal_required"] is False
    assert timing["time_based_eligibility_required"] is False
    assert timing["temporal_replication_claim"] is False


def test_payload_binding_fails_before_delegate_transport() -> None:
    class Delegate:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, *_: Any, **__: Any) -> str:
            self.calls += 1
            return "transport-called"

    delegate = Delegate()
    bound = runner._PayloadBoundRecoveryClient(
        delegate,
        expected_payloads={1: "a" * 64},
        payload_digest=lambda _messages: "b" * 64,
    )

    with pytest.raises(ProviderPayloadError, match="differs from attempt 1"):
        bound.complete([{"role": "user", "content": "offline"}], step=1)

    assert delegate.calls == 0
