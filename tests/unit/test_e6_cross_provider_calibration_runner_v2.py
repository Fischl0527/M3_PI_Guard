from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

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
    ) -> None:
        self.failure = failure
        self.runtime_provider_failures = runtime_provider_failures
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
                        "error_type": "ProviderTransportError",
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
    seal_root = root.parent / f"{root.name}-immutable-v1-seals"
    seal_paths: dict[str, Path] = {}
    for provider_id in ("deepseek", "gemini"):
        seal_path = seal_root / provider_id / "window_seal_W2.json"
        seal_path.parent.mkdir(parents=True, exist_ok=True)
        seal_path.write_text(
            json.dumps(
                {
                    "study_id": runner.e6_v1.STUDY_ID,
                    "provider_id": provider_id,
                    "replicate_window": "W2",
                    "status": "sealed",
                    "window_started_at": "2026-08-29T01:00:00+08:00",
                }
            ),
            encoding="utf-8",
        )
        seal_paths[provider_id] = seal_path
    monkeypatch.setattr(runner, "V1_W2_SEAL_PATHS", seal_paths)
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
        "W3",
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

    row = runner._window_rows("gemini", "W1")[0]

    assert row["study_id"] == runner.STUDY_ID
    assert row["run_id"] == "e6-v2-gemini-W1"
    assert row["execution_identity"] == runner._execution_identity("gemini", "W1")
    assert row["execution_identity"] != runner.e6_v1._load_plan("gemini")[0][
        "execution_identity"
    ]
    assert runner._provider_stop_path("gemini").name == "provider_stop_v2.json"
    assert runner.OUTPUT_ROOT != runner.e6_v1.OUTPUT_ROOT


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
        match="prospective W3-only",
    ):
        runner.run_window(
            "deepseek",
            window,
            canary_only=True,
            credential_loader=lambda: pytest.fail("credentials were loaded"),
            dispatcher_factory=lambda *_: pytest.fail("dispatcher was built"),
        )

    assert not runner.OUTPUT_ROOT.exists()


def test_w3_requires_sealed_v1_w2_and_frozen_start_interval_before_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    deepseek_seal = runner.V1_W2_SEAL_PATHS["deepseek"]
    deepseek_seal.unlink()

    with pytest.raises(runner.E6CalibrationRunnerV2Error, match="W2 seal is absent"):
        runner.run_window(
            "deepseek",
            "W3",
            canary_only=True,
            credential_loader=lambda: pytest.fail("credentials were loaded"),
            dispatcher_factory=lambda *_: pytest.fail("dispatcher was built"),
        )

    assert not runner.OUTPUT_ROOT.exists()


@pytest.mark.parametrize(
    "current_time",
    ["2026-08-29T18:59:59+08:00", "2026-08-30T07:00:01+08:00"],
)
def test_w3_rejects_start_outside_frozen_interval_before_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    current_time: str,
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    monkeypatch.setattr(runner, "_now", lambda: current_time)

    with pytest.raises(runner.E6CalibrationRunnerV2Error, match="18-30 hour"):
        runner.run_window(
            "deepseek",
            "W3",
            canary_only=True,
            credential_loader=lambda: pytest.fail("credentials were loaded"),
            dispatcher_factory=lambda *_: pytest.fail("dispatcher was built"),
        )

    assert not runner.OUTPUT_ROOT.exists()


def test_w3_resume_uses_frozen_window_start_and_enforces_twelve_hour_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    first = _run("deepseek", _Dispatcher())
    assert first["executed"] == 12

    monkeypatch.setattr(runner, "_now", lambda: "2026-08-30T09:00:00+08:00")
    resumed = _run("deepseek", _Dispatcher())
    assert resumed["executed"] == 0

    monkeypatch.setattr(runner, "_now", lambda: "2026-08-30T12:00:01+08:00")
    with pytest.raises(runner.E6CalibrationRunnerV2Error, match="12-hour"):
        _run("deepseek", _Dispatcher())


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
        "W3",
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
    second["work_key"] = runner._window_rows("deepseek", "W3")[1]["work_key"]
    second["case_id"] = runner._window_rows("deepseek", "W3")[1]["case_id"]
    runner.lean._append_jsonl(runner._raw_path("deepseek"), second)

    with pytest.raises(
        runner.E6CalibrationRunnerV2Error,
        match="unique unresolved work key",
    ):
        _run("deepseek", _Dispatcher(), retry_key=str(first["work_key"]))


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
    assert row["protocol_terminal_reason"] == "w3_429_diagnostic_terminal"
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


def test_runtime_provider_failure_is_counted_as_systemic_gate_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_offline(monkeypatch, tmp_path / "e6-v2")
    value = _run(
        "deepseek",
        _Dispatcher(runtime_provider_failures=2),
    )
    gate = json.loads(
        runner._gate_path("deepseek", "W3").read_text(encoding="utf-8")
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


def test_manifest_keeps_v1_immutable_and_api_execution_disabled() -> None:
    manifest = json.loads(runner.MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["study_id"] == runner.STUDY_ID
    assert manifest["provider_calls_made"] == 0
    assert manifest["v1_records_modified"] == 0
    assert "not_authorized" in manifest["status"]
    assert manifest["generic_response_less_recovery"][
        "independent_trace_and_call_ledger_namespace"
    ] is True
    assert manifest["prospective_execution_windows"] == ["W3"]
    assert manifest["prospective_w3_plan_counts"] == {
        "deepseek": 360,
        "gemini": 180,
    }
    assert manifest["gemini_inference_role"] == "single_window_diagnostic_only"
    prerequisite = manifest["w3_execution_prerequisite"]
    assert prerequisite["immutable_v1_w2_seal_required"] is True
    assert prerequisite["w2_to_w3_start_interval_hours"] == [18, 30]
    assert prerequisite["checked_before_credentials_dispatch_and_output"] is True
    assert prerequisite["existing_window_uses_frozen_start"] is True
    assert prerequisite["maximum_window_duration_hours"] == 12
    assert prerequisite["deepseek_currently_has_w2_seal"] is True
    assert prerequisite["gemini_currently_has_w2_seal"] is False


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
