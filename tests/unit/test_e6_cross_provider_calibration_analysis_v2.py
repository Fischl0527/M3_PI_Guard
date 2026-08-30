from __future__ import annotations

import csv
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest

import experiments.paper_v2.e6_cross_provider_calibration_analysis_v2 as analysis
import experiments.paper_v2.e6_cross_provider_calibration_runner_v2 as runner
from experiments.paper_v2.agentdojo_live_dependency import (
    AgentDojoLiveDependencyError,
)


def _fixture(
    provider: str,
    *,
    tasks: int = 2,
    unsafe: Callable[[int, str], bool] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    model = analysis.EXPECTED_MODELS[provider]
    plan: list[dict[str, object]] = []
    raw: list[dict[str, object]] = []
    sequence = 0
    for task_index in range(tasks):
        task = f"task-{task_index}"
        benchmark = "agentdojo-v1" if task_index % 2 == 0 else "m3-v2"
        for condition in analysis.CONDITIONS:
            sequence += 1
            source_key = f"source:{provider}:{task}:{condition}"
            work_key = f"e6-v2-immediate__{source_key}"
            planned: dict[str, object] = {
                "schema_version": "m3-paper-v2-e6-work-item-2.0",
                "study_id": analysis.STUDY_ID,
                "run_id": f"e6-v2-{provider}-B1",
                "execution_identity": analysis._execution_identity(provider),
                "work_key": work_key,
                "source_v1_work_key": source_key,
                "source_replicate_window": "W3",
                "source_replicate_index": 3,
                "provider_id": provider,
                "model_id": model,
                "underlying_task_id": task,
                "case_id": f"case-{task_index}",
                "benchmark": benchmark,
                "condition_id": condition,
                "replicate_window": "B1",
                "replicate_index": 1,
                "execution_block_id": "B1",
                "execution_block_role": analysis.BLOCK_ROLE,
                "temporal_replication_claim": False,
                "analysis_payload_digest_sha256": f"digest:{task}:{condition}",
                "sequence": sequence,
            }
            event = unsafe(task_index, condition) if unsafe else False
            record: dict[str, object] = {
                **planned,
                "schema_version": analysis.RAW_SCHEMA_VERSION,
                "configured_model": model,
                "record_kind": "execution",
                "attempt": 1,
                "response_obtained": True,
                "terminal_status": True,
                "retry_eligible": False,
                "included_in_primary_itt": True,
                "operational_status": "completed",
                "unsafe_effect": event,
                "returned_models": [model],
                "returned_model_id": model,
                "provider_requests": [
                    {
                        "local_request_id": f"request:{provider}:{sequence}",
                        "payload_sha256": f"{'a' * 63}{sequence % 10}",
                        "provider_response_id": f"response:{provider}:{sequence}",
                        "returned_model": model,
                    }
                ],
                "online_visible_field_digest_sha256": "b" * 64,
                "online_forbidden_fields_present": False,
                "provider_tools_enabled": False,
                "external_effects_enabled": False,
                "provider_call_count": 1,
                "ask_count": int(condition == "m3_full"),
                "deny_count": int(condition == "m3_policy_only"),
                "latency_ms": {"total": 10.0 + sequence, "model": 8.0 + sequence},
                "token_usage": {"input": 100, "output": 20, "total": 120},
                "cost": (
                    {"currency": "CNY", "amount": 0.01}
                    if provider == "deepseek"
                    else {"currency": "USD", "amount": 0.0, "billing_tier": "free"}
                ),
                "free_tier_attestation": (
                    None
                    if provider == "deepseek"
                    else {
                        "billing_tier": "free",
                        "cost_usd": 0.0,
                        "paid_fallback_enabled": False,
                    }
                ),
                "window_started_at": "2026-08-31T10:00:00+08:00",
                "window_completed_at": None,
                "recorded_at": f"2026-08-31T10:{sequence:02d}:00+08:00",
            }
            plan.append(planned)
            raw.append(record)
    return plan, raw


def _gate(provider: str) -> dict[str, object]:
    return {
        "schema_version": "m3-paper-v2-e6-window-gate-2.0",
        "study_id": analysis.STUDY_ID,
        "provider_id": provider,
        "replicate_window": "B1",
        "execution_block_id": "B1",
        "execution_block_role": analysis.BLOCK_ROLE,
        "temporal_replication_claim": False,
        "scientific_outcomes_inspected": False,
        "status": "passed",
        "gate_passed": True,
    }


def _close(
    provider: str = "deepseek",
    *,
    plan_rows: list[dict[str, object]] | None = None,
    raw_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    plan_rows = plan_rows or []
    raw_rows = raw_rows or []
    latest = {str(row["work_key"]): row for row in raw_rows}
    conditions = sorted({str(row["condition_id"]) for row in plan_rows})
    condition_counts: dict[str, dict[str, int]] = {}
    for condition in conditions:
        planned = [row for row in plan_rows if row["condition_id"] == condition]
        observed = [latest[str(row["work_key"])] for row in planned if str(row["work_key"]) in latest]
        condition_counts[condition] = {
            "planned": len(planned),
            "response_bearing": sum(
                analysis._has_response_evidence(row) for row in observed
            ),
            "administrative_closure": sum(
                row.get("record_kind") == "block_closure" for row in observed
            ),
        }
    closure_statuses = {
        str(row.get("operational_status"))
        for row in latest.values()
        if row.get("record_kind") == "block_closure"
    }
    closure_mode = (
        "provider_unavailable"
        if closure_statuses == {"provider_block_unavailable"}
        else (
            "technical_gate_not_extended"
            if closure_statuses == {"technical_gate_not_extended"}
            else "all_rows_terminal"
        )
    )
    return {
        "schema_version": "m3-paper-v2-e6-block-seal-2.0",
        "study_id": analysis.STUDY_ID,
        "provider_id": provider,
        "execution_block_id": "B1",
        "execution_block_role": analysis.BLOCK_ROLE,
        "temporal_replication_claim": False,
        "status": "sealed",
        "closure_mode": closure_mode,
        "planned_rows": len(plan_rows),
        "terminal_rows": sum(
            row.get("terminal_status") is True for row in latest.values()
        ),
        "response_bearing_rows": sum(
            analysis._has_response_evidence(row) for row in latest.values()
        ),
        "administrative_closure_rows": sum(
            row.get("record_kind") == "block_closure" for row in latest.values()
        ),
        "condition_counts": condition_counts,
        "gate_status": "passed",
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "execution_block_started_at": "2026-08-31T10:00:00+08:00",
        "execution_block_completed_at": "2026-08-31T11:00:00+08:00",
        "elapsed_seconds": 3600.0,
        "sealed_at": "2026-08-31T11:00:00+08:00",
    }


def _closure(
    planned: dict[str, object],
    *,
    attempt: int = 0,
    status: str = "technical_gate_not_extended",
) -> dict[str, object]:
    provider = str(planned["provider_id"])
    return {
        **planned,
        "schema_version": analysis.RAW_SCHEMA_VERSION,
        "configured_model": planned["model_id"],
        "attempt": attempt,
        "record_kind": "block_closure",
        "closure_is_model_outcome": False,
        "response_obtained": False,
        "provider_requests": [],
        "terminal_status": True,
        "retry_eligible": False,
        "included_in_primary_itt": True,
        "operational_status": status,
        "unsafe_effect": False,
        "ask_count": 0,
        "deny_count": 0,
        "provider_call_count": 0,
        "online_forbidden_fields_present": False,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "latency_ms": {},
        "token_usage": {},
        "cost": (
            {"currency": "CNY", "amount": 0.0}
            if provider == "deepseek"
            else {"currency": "USD", "amount": 0.0, "billing_tier": "free"}
        ),
        "free_tier_attestation": (
            None
            if provider == "deepseek"
            else {
                "billing_tier": "free",
                "cost_usd": 0.0,
                "paid_fallback_enabled": False,
            }
        ),
        "window_started_at": "2026-08-31T10:00:00+08:00",
        "window_completed_at": "2026-08-31T11:00:00+08:00",
        "recorded_at": "2026-08-31T11:00:00+08:00",
    }


class _OfflineRunnerDispatcher:
    def __init__(self, *, runtime_provider_failures: int = 0) -> None:
        self.runtime_provider_failures = runtime_provider_failures
        self.calls = 0

    def execute(
        self, work_item: Mapping[str, Any], state: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        del state
        self.calls += 1
        provider_failure = self.calls <= self.runtime_provider_failures
        key = str(work_item["work_key"])
        model = str(work_item["model_id"])
        short = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
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
                        "client_request_id": f"m3req-{short}",
                        "payload_sha256": "a" * 64,
                        "provider_request_id": None,
                        "provider_response_id": f"response-{short}",
                        "model_id": model,
                    }
                ],
                "usage_summary": {"cumulative_cost_cny": 0.001},
            },
            "recorded_at": "2026-08-29T23:00:00+08:00",
        }


def _patch_runner_offline(
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


def _run_offline_prefix(
    provider: str, dispatcher: _OfflineRunnerDispatcher
) -> dict[str, Any]:
    return runner.run_window(
        provider,
        runner.EXECUTION_BLOCK_ID,
        canary_only=True,
        credential_loader=lambda: {},
        dispatcher_factory=lambda *_: dispatcher,
    )


def test_real_projection_is_b1_only_balanced_and_nested() -> None:
    deepseek = analysis.load_projected_plan("deepseek")
    gemini = analysis.load_projected_plan("gemini")

    assert len(deepseek) == 360
    assert len(gemini) == 180
    assert len({row["work_key"] for row in deepseek}) == 360
    assert len({row["underlying_task_id"] for row in deepseek}) == 60
    assert len({row["underlying_task_id"] for row in gemini}) == 30
    assert {row["underlying_task_id"] for row in gemini}.issubset(
        {row["underlying_task_id"] for row in deepseek}
    )
    assert all(
        row["replicate_window"] == "B1"
        and row["source_replicate_window"] == "W3"
        and row["temporal_replication_claim"] is False
        for row in deepseek + gemini
    )


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("replicate_window", "W2", "W1/W2 or non-B1"),
        ("temporal_replication_claim", True, "temporal=true"),
    ],
)
def test_analysis_rejects_temporal_or_non_b1_rows(
    field: str, value: object, match: str
) -> None:
    plan, raw = _fixture("deepseek")
    raw[0][field] = value

    with pytest.raises(analysis.E6B1AnalysisError, match=match):
        analysis.merge_plan_and_raw(plan, raw)


def test_analysis_rejects_unknown_raw_record_kind() -> None:
    plan, raw = _fixture("deepseek", tasks=1)
    raw[0]["record_kind"] = "window_closure"

    with pytest.raises(analysis.E6B1AnalysisError, match="raw record kind drift"):
        analysis.merge_plan_and_raw(plan, raw)


def test_latest_attempt_drives_endpoint_but_all_attempts_drive_resources() -> None:
    plan, raw = _fixture("deepseek", tasks=1)
    first = raw[0]
    first["response_obtained"] = False
    first["terminal_status"] = False
    first["retry_eligible"] = True
    first["operational_status"] = "pre_response_transport_failure"
    first["provider_requests"] = [
        {"local_request_id": "attempt-1", "payload_sha256": "a" * 64}
    ]
    second = {
        **first,
        "attempt": 2,
        "response_obtained": True,
        "terminal_status": True,
        "retry_eligible": False,
        "operational_status": "completed",
        "unsafe_effect": True,
        "provider_requests": [
            {
                "local_request_id": "attempt-2",
                "payload_sha256": "a" * 64,
                "provider_response_id": "attempt-2-response",
                "returned_model": analysis.EXPECTED_MODELS["deepseek"],
            }
        ],
    }
    raw.insert(1, second)

    result, _ = analysis.analyze_provider_block(
        "deepseek",
        plan_rows=plan,
        raw_rows=raw,
        gate=_gate("deepseek"),
        close=_close(plan_rows=plan, raw_rows=raw),
        bootstrap_replicates=20,
    )

    assert result["audit"]["superseded_attempt_rows"] == 1
    assert result["audit"]["recovered_work_items"] == 1
    assert result["cell_summary"]["all|no_defense"]["unsafe_count"] == 1
    assert result["burden"]["overall"]["physical_attempt_rows"] == len(raw)
    assert result["burden"]["overall"]["tokens"]["total"] == len(raw) * 120
    assert result["technical_audit"]["passed_for_observed_records"] is True


def test_runner_local_projection_recovery_is_accepted_by_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_runner_offline(monkeypatch, tmp_path / "e6-v2")

    class _ProjectionFailureDispatcher:
        def execute(
            self, work_item: Mapping[str, Any], state: Mapping[str, Any]
        ) -> Mapping[str, Any]:
            del work_item, state
            raise AgentDojoLiveDependencyError("unknown paper-v2 work key")

    _run_offline_prefix("deepseek", _ProjectionFailureDispatcher())
    first = runner.lean._read_jsonl(runner._raw_path("deepseek"))[0]
    key = str(first["work_key"])
    runner.run_window(
        "deepseek",
        runner.EXECUTION_BLOCK_ID,
        canary_only=True,
        retry_failed_work_keys=(key,),
        credential_loader=lambda: {},
        dispatcher_factory=lambda *_: _OfflineRunnerDispatcher(),
    )
    raw = runner.lean._read_jsonl(runner._raw_path("deepseek"))

    merged, audit = analysis.merge_plan_and_raw(
        runner._window_rows("deepseek", runner.EXECUTION_BLOCK_ID),
        raw,
    )
    recovered = next(row for row in merged if row["work_key"] == key)

    assert [row["attempt"] for row in raw] == [1, 2]
    assert raw[0]["retry_eligible"] is False
    assert raw[0]["terminal_status"] is True
    assert raw[0]["provider_call_count"] == 0
    assert raw[1]["recovery_kind"] == runner.LOCAL_PROJECTION_RECOVERY_KIND
    assert recovered["attempt"] == 2
    assert recovered["_scientific_terminal"] is True
    assert audit["recovered_work_items"] == 1

    result, _ = analysis.analyze_provider_block(
        "deepseek",
        plan_rows=runner._window_rows("deepseek", runner.EXECUTION_BLOCK_ID),
        raw_rows=raw,
        gate=_gate("deepseek"),
        bootstrap_replicates=5,
    )
    assert result["technical_audit"]["passed_for_observed_records"] is True
    assert result["audit"]["recovered_work_items"] == 1


def test_post_response_vigil_continuation_remains_terminal_itt_in_analysis() -> None:
    plan, raw = _fixture("deepseek", tasks=2)
    vigils = [
        row
        for row in raw
        if row["condition_id"]
        == "strongest_peer_reviewed_structural_baseline"
    ]
    for vigil in vigils:
        vigil.update(
            {
                "operational_status": "provider_failure",
                "error_type": analysis.POST_RESPONSE_VIGIL_FAILURE_CLASS,
                "max_provider_calls": 16,
                "runtime_failure_diagnostic": {
                    "failure_stage": analysis.POST_RESPONSE_VIGIL_FAILURE_STAGE,
                    "failure_class": analysis.POST_RESPONSE_VIGIL_FAILURE_CLASS,
                    "provider_call_index": 1,
                    "http_category": "not_observed",
                },
                "real_effect_receipt": None,
                "simulated_effect_receipt": {
                    "effect_backend": "no_effect",
                    "external_connectors_enabled": False,
                    "provider_managed_tools_enabled": False,
                },
                "provider_continuation_kind": (
                    analysis.POST_RESPONSE_VIGIL_CONTINUATION_KIND
                ),
            }
        )

    merged, _ = analysis.merge_plan_and_raw(plan, raw)
    observed = [
        row
        for row in merged
        if row["work_key"] in {vigil["work_key"] for vigil in vigils}
    ]
    result, _ = analysis.analyze_provider_block(
        "deepseek",
        plan_rows=plan,
        raw_rows=raw,
        gate=_gate("deepseek"),
        close=_close(plan_rows=plan, raw_rows=raw),
        bootstrap_replicates=5,
    )

    assert len(observed) == 2
    assert all(row["_scientific_terminal"] is True for row in observed)
    assert all(row["included_in_primary_itt"] is True for row in observed)
    assert all(row["retry_eligible"] is False for row in observed)
    assert result["technical_audit"][
        "allowlisted_post_response_vigil_failures"
    ] == 2
    assert result["technical_audit"]["systemic_failure_counts"] == {}
    assert result["technical_audit"]["no_repeated_systemic_failure"] is True
    assert result["cell_summary"][
        "all|strongest_peer_reviewed_structural_baseline"
    ]["operational_failure_count"] == 2


def test_analysis_rejects_drifted_post_response_vigil_continuation_marker() -> None:
    plan, raw = _fixture("deepseek", tasks=1)
    vigil = next(
        row
        for row in raw
        if row["condition_id"]
        == "strongest_peer_reviewed_structural_baseline"
    )
    vigil["provider_continuation_kind"] = (
        analysis.POST_RESPONSE_VIGIL_CONTINUATION_KIND
    )

    with pytest.raises(
        analysis.E6B1AnalysisError,
        match="VIGIL continuation marker drift",
    ):
        analysis.merge_plan_and_raw(plan, raw)


def test_analysis_rejects_nonadjacent_local_projection_recovery() -> None:
    plan, raw = _fixture("deepseek", tasks=1)
    first = raw[0]
    first.update(
        {
            "response_obtained": False,
            "terminal_status": True,
            "retry_eligible": False,
            "included_in_primary_itt": True,
            "operational_status": "contract_failure",
            "error_type": "AgentDojoLiveDependencyError",
            "provider_requests": [],
            "provider_call_count": 0,
            "returned_models": [],
        }
    )
    second = {
        **first,
        "attempt": 2,
        "response_obtained": True,
        "operational_status": "completed",
        "error_type": None,
        "provider_requests": [
            {
                "local_request_id": "local-projection-attempt-2",
                "payload_sha256": "a" * 64,
                "provider_response_id": "local-projection-response-2",
                "returned_model": analysis.EXPECTED_MODELS["deepseek"],
            }
        ],
        "provider_call_count": 1,
        "returned_models": [analysis.EXPECTED_MODELS["deepseek"]],
        "returned_model_id": analysis.EXPECTED_MODELS["deepseek"],
        "recovery_kind": analysis.LOCAL_PROJECTION_RECOVERY_KIND,
        "supersedes_attempt": 1,
        "payload_bound_recovery_required": False,
    }
    raw.insert(2, second)

    with pytest.raises(
        analysis.E6B1AnalysisError,
        match="local projection recovery was not adjacent",
    ):
        analysis.merge_plan_and_raw(plan, raw)


@pytest.mark.parametrize(
    "field",
    [
        "run_id",
        "execution_identity",
        "execution_block_role",
        "execution_block_id",
        "source_v1_work_key",
        "provider_id",
        "model_id",
        "condition_id",
        "case_id",
    ],
)
def test_every_raw_row_is_bound_to_the_frozen_plan_identity(field: str) -> None:
    plan, raw = _fixture("deepseek", tasks=1)
    raw[0][field] = f"drift:{field}"

    with pytest.raises(analysis.E6B1AnalysisError, match="identity drift"):
        analysis.merge_plan_and_raw(plan, raw)


def test_attempt_two_cannot_drift_execution_identity() -> None:
    plan, raw = _fixture("deepseek", tasks=1)
    first = raw[0]
    first["response_obtained"] = False
    first["terminal_status"] = False
    first["retry_eligible"] = True
    first["provider_requests"] = [
        {"local_request_id": "attempt-1", "payload_sha256": "a" * 64}
    ]
    second = {
        **first,
        "attempt": 2,
        "source_v1_work_key": "drifted-source-key",
        "terminal_status": True,
        "retry_eligible": False,
    }
    raw.insert(1, second)

    with pytest.raises(analysis.E6B1AnalysisError, match="attempt identity drift"):
        analysis.merge_plan_and_raw(plan, raw)


def test_missing_rows_are_unresolved_and_enter_the_conservative_upper_bound() -> None:
    plan, raw = _fixture("deepseek", tasks=2)
    missing = raw.pop()
    condition = str(missing["condition_id"])

    result, _ = analysis.analyze_provider_block(
        "deepseek",
        plan_rows=plan,
        raw_rows=raw,
        gate=_gate("deepseek"),
        bootstrap_replicates=20,
    )
    cell = result["cell_summary"][f"all|{condition}"]

    assert result["audit"]["missing_work_items"] == 1
    assert cell["unresolved_or_unstarted"] == 1
    assert cell["unsafe_itt_observed_lower"]["denominator"] == 2
    assert cell["unsafe_or_failure_or_unresolved_upper"]["numerator"] == 1
    assert result["analysis_status"] == "ANALYZED_OPEN_OR_UNSEALED_DIAGNOSTIC"


def test_attempt_zero_administrative_closure_is_not_a_model_safe_outcome() -> None:
    plan, raw = _fixture("deepseek", tasks=1)
    raw[-1] = _closure(plan[-1])

    result, _ = analysis.analyze_provider_block(
        "deepseek",
        plan_rows=plan,
        raw_rows=raw,
        gate=_gate("deepseek"),
        close=_close(plan_rows=plan, raw_rows=raw),
        bootstrap_replicates=20,
    )
    cell = result["cell_summary"]["all|m3_full"]

    assert result["audit"]["administrative_closure_rows"] == 1
    assert result["audit"]["administrative_closure_work_items"] == 1
    assert result["audit"]["scientific_terminal_latest_work_items"] == 5
    assert cell["terminal_latest"] == 1
    assert cell["scientific_terminal_latest"] == 0
    assert cell["administrative_closure_latest"] == 1
    assert cell["unsafe_terminal"]["denominator"] == 0
    assert cell["unresolved_or_unstarted"] == 1
    assert cell["unsafe_or_failure_or_unresolved_upper"]["value"] == 1.0
    assert result["burden"]["overall"]["physical_attempt_rows"] == 5
    assert result["timing"]["last_observed_at"] != _close()["sealed_at"]
    assert result["timing"][
        "administrative_closure_rows_excluded_from_observation_time"
    ] == 1
    assert (
        result["analysis_status"]
        == "ANALYZED_CLOSED_ADMINISTRATIVELY_INCOMPLETE_DIAGNOSTIC"
    )


def test_same_attempt_closure_supersedes_only_administratively() -> None:
    plan, raw = _fixture("deepseek", tasks=1)
    first = raw[0]
    first["response_obtained"] = False
    first["terminal_status"] = False
    first["retry_eligible"] = True
    first["operational_status"] = "pre_response_transport_failure"
    first["provider_requests"] = [
        {"local_request_id": "attempt-1", "payload_sha256": "a" * 64}
    ]
    closure = {
        **_closure(plan[0], attempt=1, status="provider_block_unavailable"),
        "provider_requests": first["provider_requests"],
    }
    raw.insert(1, closure)

    result, _ = analysis.analyze_provider_block(
        "deepseek",
        plan_rows=plan,
        raw_rows=raw,
        gate=_gate("deepseek"),
        close=_close(plan_rows=plan, raw_rows=raw),
        bootstrap_replicates=20,
    )

    assert result["audit"]["administrative_closure_rows"] == 1
    assert result["audit"]["physical_attempt_rows"] == 6
    assert result["burden"]["overall"]["physical_attempt_rows"] == 6
    assert result["cell_summary"]["all|no_defense"][
        "scientific_terminal_latest"
    ] == 0


def test_closure_only_evidence_cannot_vacuously_pass_technical_audit() -> None:
    plan, _raw = _fixture("gemini", tasks=1)
    raw = [_closure(row) for row in plan]

    result, _ = analysis.analyze_provider_block(
        "gemini",
        plan_rows=plan,
        raw_rows=raw,
        gate=_gate("gemini"),
        close=_close("gemini", plan_rows=plan, raw_rows=raw),
        bootstrap_replicates=20,
    )

    assert result["technical_audit"]["physical_attempts_present"] is False
    assert result["technical_audit"]["response_evidence_present"] is False
    assert result["technical_audit"]["passed_for_observed_records"] is False
    assert result["burden"]["overall"]["physical_attempt_rows"] == 0


def test_paired_newcombe_mcnemar_holm_and_factorial_are_computed() -> None:
    def unsafe(_task: int, condition: str) -> bool:
        return condition in {
            "no_defense",
            "m3_policy_safe_prompt",
            "m3_full_normal_prompt",
            "m3_full",
        }

    plan, raw = _fixture("deepseek", tasks=2, unsafe=unsafe)
    result, _ = analysis.analyze_provider_block(
        "deepseek",
        plan_rows=plan,
        raw_rows=raw,
        gate=_gate("deepseek"),
        close=_close(plan_rows=plan, raw_rows=raw),
        bootstrap_replicates=20,
    )
    comparison = result["paired_comparisons"]["unsafe_effect"]["comparisons"][
        "policy_normal_vs_no_defense"
    ]

    assert comparison["complete_pairs"] == 2
    assert comparison["terminal_itt_pairs"] == 2
    assert comparison["response_complete_pairs"] == 2
    assert comparison["inferentially_estimable"] is True
    assert comparison["newcombe_95"]["estimate"] == -1.0
    assert comparison["mcnemar_exact"]["treatment_only_event"] == 0
    assert 0.0 <= comparison["holm_adjusted_p"] <= 1.0
    assert comparison["paired_task_bootstrap_95"]["method"] == (
        "benchmark_stratified_task_bootstrap"
    )
    assert comparison["paired_task_bootstrap_95"]["tasks"] == 2
    factors = result["factorial_2x2"]["unsafe_effect"]
    assert factors["complete_tasks"] == 2
    assert factors["terminal_itt_tasks"] == 2
    assert factors["response_complete_tasks"] == 2
    assert factors["expected_tasks"] == 2
    assert factors["inferentially_estimable"] is True
    assert factors["effects"]["module"]["estimate"] == 0.5
    assert factors["effects"]["prompt"]["estimate"] == 0.5
    assert factors["effects"]["module_x_prompt"]["estimate"] == -1.0
    assert factors["effects"]["module"]["ci_low"] is None
    assert factors["effects"]["module"]["degenerate"] is True


def test_seal_time_and_gemini_diagnostic_boundary_are_preserved() -> None:
    ds_plan, ds_raw = _fixture("deepseek")
    gm_plan, gm_raw = _fixture("gemini")
    value = analysis.analyze_all(
        deepseek_plan=ds_plan,
        deepseek_raw=ds_raw,
        gemini_plan=gm_plan,
        gemini_raw=gm_raw,
        deepseek_gate=_gate("deepseek"),
        gemini_gate=_gate("gemini"),
        deepseek_close=_close("deepseek", plan_rows=ds_plan, raw_rows=ds_raw),
        gemini_close=_close("gemini", plan_rows=gm_plan, raw_rows=gm_raw),
        bootstrap_replicates=20,
    )

    assert value["providers"]["deepseek"]["timing"]["sealed_at"].endswith(
        "11:00:00+08:00"
    )
    assert value["providers"]["deepseek"]["timing"]["sealed_span_seconds"] == 3600
    assert value["nested_provider_diagnostic"]["cross_provider_claim_eligible"] is False
    assert value["nested_provider_diagnostic"]["gemini_permanently_diagnostic"] is True
    assert value["analysis_boundaries"]["temporal_replication_claim"] is False
    assert value["verification_status"] == "ANALYZED_B1_COMPLETE_DIAGNOSTIC"


def test_technical_audit_checks_free_tier_tools_and_call_caps() -> None:
    plan, raw = _fixture("gemini")
    raw[0]["provider_tools_enabled"] = True
    raw[1]["provider_call_count"] = 17
    raw[2]["cost"] = {"currency": "USD", "amount": 0.01, "billing_tier": "paid"}

    result, _ = analysis.analyze_provider_block(
        "gemini",
        plan_rows=plan,
        raw_rows=raw,
        gate=_gate("gemini"),
        bootstrap_replicates=20,
    )
    audit = result["technical_audit"]

    assert audit["provider_tools_and_real_effects_disabled"] is False
    assert audit["provider_call_caps_respected"] is False
    assert audit["gemini_free_tier_usd_zero"] is False
    assert audit["passed_for_observed_records"] is False
    assert result["analysis_status"] == "ANALYZED_TECHNICAL_AUDIT_FAILED_DIAGNOSTIC"


def test_technical_audit_checks_call_counts_local_ids_and_visible_digest() -> None:
    plan, raw = _fixture("deepseek")
    raw[0]["provider_call_count"] = 2
    raw[1]["provider_requests"][0]["local_request_id"] = raw[0][  # type: ignore[index]
        "provider_requests"
    ][0]["local_request_id"]  # type: ignore[index]
    raw[2]["online_visible_field_digest_sha256"] = None

    result, _ = analysis.analyze_provider_block(
        "deepseek",
        plan_rows=plan,
        raw_rows=raw,
        gate=_gate("deepseek"),
        bootstrap_replicates=20,
    )
    audit = result["technical_audit"]

    assert audit["provider_call_counts_match_request_chain"] is False
    assert audit["unique_local_request_ids"] is False
    assert audit["online_visible_field_digests_complete"] is False
    assert audit["passed_for_observed_records"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("local_request_id", ""),
        ("payload_sha256", "not-a-64-character-lowercase-sha256"),
        ("payload_sha256", "A" * 64),
        ("provider_response_id", "  "),
    ],
)
def test_request_chain_rejects_malformed_identifiers_and_payload_digest(
    field: str, value: str
) -> None:
    plan, raw = _fixture("deepseek", tasks=1)
    raw[0]["provider_requests"][0][field] = value  # type: ignore[index]

    result, _ = analysis.analyze_provider_block(
        "deepseek",
        plan_rows=plan,
        raw_rows=raw,
        gate=_gate("deepseek"),
        bootstrap_replicates=20,
    )

    assert result["technical_audit"]["complete_official_request_chain"] is False
    assert result["technical_audit"]["passed_for_observed_records"] is False


def test_write_outputs_renders_json_markdown_three_csv_and_two_svg(
    tmp_path: Path,
) -> None:
    ds_plan, ds_raw = _fixture("deepseek")
    gm_plan, gm_raw = _fixture("gemini")
    value = analysis.analyze_all(
        deepseek_plan=ds_plan,
        deepseek_raw=ds_raw,
        gemini_plan=gm_plan,
        gemini_raw=gm_raw,
        deepseek_gate=_gate("deepseek"),
        gemini_gate=_gate("gemini"),
        deepseek_close=_close("deepseek", plan_rows=ds_plan, raw_rows=ds_raw),
        gemini_close=_close("gemini", plan_rows=gm_plan, raw_rows=gm_raw),
        bootstrap_replicates=20,
    )
    paths = analysis.write_outputs(value, output_root=tmp_path)

    assert all(Path(path).is_file() for path in paths.values())
    persisted = json.loads((tmp_path / "analysis_v2.json").read_text(encoding="utf-8"))
    report = (tmp_path / "report_v2.md").read_text(encoding="utf-8")
    assert persisted["study_id"] in report
    assert "Cross-provider claim eligible：`false`" in report
    assert "all_rows_terminal" in report
    assert "## 技术审计" in report
    assert "只审计已经物理执行的记录" in report
    assert len(list((tmp_path / "tables").glob("*.csv"))) == 3
    assert len(list((tmp_path / "figures").glob("*.svg"))) == 2
    assert all(
        "<svg" in path.read_text(encoding="utf-8")
        for path in (tmp_path / "figures").glob("*.svg")
    )


def test_partial_gemini_figures_do_not_visualize_one_pair_as_equivalence(
    tmp_path: Path,
) -> None:
    ds_plan, ds_raw = _fixture("deepseek", tasks=2)
    gm_plan, gm_raw = _fixture("gemini", tasks=2)
    retained_task = str(gm_plan[0]["underlying_task_id"])
    partial_raw = [
        row for row in gm_raw if str(row["underlying_task_id"]) == retained_task
    ]
    vigil_row = next(
        row
        for row in partial_raw
        if row["condition_id"]
        == "strongest_peer_reviewed_structural_baseline"
    )
    vigil_row["response_obtained"] = False
    vigil_row["operational_status"] = "contract_failure"
    vigil_row["provider_requests"] = [
        {
            "local_request_id": "gemini-vigil-response-less",
            "payload_sha256": "f" * 64,
        }
    ]
    vigil_row["returned_models"] = []
    missing = {
        str(row["work_key"])
        for row in gm_plan
        if str(row["underlying_task_id"]) != retained_task
    }
    for row in gm_plan:
        if str(row["work_key"]) in missing:
            partial_raw.append(
                _closure(row, status="provider_block_unavailable")
            )
    gemini_gate = _gate("gemini")
    gemini_gate["status"] = "failed"
    gemini_gate["gate_passed"] = False
    gemini_close = _close("gemini", plan_rows=gm_plan, raw_rows=partial_raw)
    gemini_close["gate_status"] = "failed"
    value = analysis.analyze_all(
        deepseek_plan=ds_plan,
        deepseek_raw=ds_raw,
        gemini_plan=gm_plan,
        gemini_raw=partial_raw,
        deepseek_gate=_gate("deepseek"),
        gemini_gate=gemini_gate,
        deepseek_close=_close("deepseek", plan_rows=ds_plan, raw_rows=ds_raw),
        gemini_close=gemini_close,
        bootstrap_replicates=20,
    )
    assert value["verification_status"] == (
        "ANALYZED_DEEPSEEK_COMPLETE_GEMINI_DIAGNOSTIC_GATE_FAILED"
    )
    analysis.write_outputs(value, output_root=tmp_path)
    report = (tmp_path / "report_v2.md").read_text(encoding="utf-8")

    activity = (tmp_path / "figures/activity_conditions_v2.svg").read_text(
        encoding="utf-8"
    )
    nested = (tmp_path / "figures/nested_provider_diagnostic_v2.svg").read_text(
        encoding="utf-8"
    )
    assert "Gemini rate not plotted" in activity
    assert "response-less fatal" in activity
    assert "administrative closures" in activity
    assert "Not estimable" in nested
    assert "NA / incomplete pairs" in nested
    assert "Terminal ITT/expected" in report
    assert "Response-complete" in report
    assert "| gemini | unsafe_effect | module | 1 / 1 / 2 | NE | NE |" in report
    comparison = value["providers"]["gemini"]["paired_comparisons"][
        "unsafe_effect"
    ]["comparisons"]
    assert comparison["vigil_vs_no_defense"]["terminal_itt_pairs"] == 1
    assert comparison["vigil_vs_no_defense"]["response_complete_pairs"] == 0
    assert comparison["full_safe_vs_no_defense"]["terminal_itt_pairs"] == 1
    assert comparison["full_safe_vs_no_defense"]["response_complete_pairs"] == 1
    with (tmp_path / "tables/paired_effects_v2.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        paired_rows = list(csv.DictReader(handle))
    vigil_csv = next(
        row
        for row in paired_rows
        if row["provider"] == "gemini"
        and row["endpoint"] == "unsafe_effect"
        and row["comparison_id"] == "vigil_vs_no_defense"
    )
    assert vigil_csv["terminal_itt_pairs"] == "1"
    assert vigil_csv["response_complete_pairs"] == "0"
    assert vigil_csv["inferentially_estimable"] == "False"


def test_vigil_pooled_result_reports_opposite_benchmark_directions() -> None:
    def unsafe(task_index: int, condition: str) -> bool:
        target = (
            "strongest_peer_reviewed_structural_baseline"
            if task_index % 2 == 0
            else "no_defense"
        )
        return condition == target

    ds_plan, ds_raw = _fixture("deepseek", tasks=4, unsafe=unsafe)
    gm_plan, gm_raw = _fixture("gemini", tasks=4)
    value = analysis.analyze_all(
        deepseek_plan=ds_plan,
        deepseek_raw=ds_raw,
        gemini_plan=gm_plan,
        gemini_raw=gm_raw,
        deepseek_gate=_gate("deepseek"),
        gemini_gate=_gate("gemini"),
        deepseek_close=_close("deepseek", plan_rows=ds_plan, raw_rows=ds_raw),
        gemini_close=_close("gemini", plan_rows=gm_plan, raw_rows=gm_raw),
        bootstrap_replicates=20,
    )
    comparison = value["providers"]["deepseek"]["paired_comparisons"][
        "unsafe_effect"
    ]["comparisons"]["vigil_vs_no_defense"]
    agentdojo = comparison["benchmark_strata"]["agentdojo-v1"]
    m3v2 = comparison["benchmark_strata"]["m3-v2"]

    assert agentdojo["baseline_events"] == 0
    assert agentdojo["treatment_events"] == 2
    assert agentdojo["risk_difference"] == 1.0
    assert m3v2["baseline_events"] == 2
    assert m3v2["treatment_events"] == 0
    assert m3v2["risk_difference"] == -1.0
    assert "方向相反" in analysis.render_markdown_report(value)


@pytest.mark.parametrize(
    "closure_mode",
    ["all_rows_terminal", "technical_gate_not_extended", "provider_unavailable"],
)
def test_report_discloses_each_block_closure_mode(closure_mode: str) -> None:
    ds_plan, ds_raw = _fixture("deepseek")
    gm_plan, gm_raw = _fixture("gemini")
    value = analysis.analyze_all(
        deepseek_plan=ds_plan,
        deepseek_raw=ds_raw,
        gemini_plan=gm_plan,
        gemini_raw=gm_raw,
        deepseek_gate=_gate("deepseek"),
        gemini_gate=_gate("gemini"),
        deepseek_close=_close("deepseek", plan_rows=ds_plan, raw_rows=ds_raw),
        gemini_close=_close("gemini", plan_rows=gm_plan, raw_rows=gm_raw),
        bootstrap_replicates=20,
    )
    value["providers"]["deepseek"]["block_close"]["closure_mode"] = closure_mode

    assert closure_mode in analysis.render_markdown_report(value)


def test_real_runner_failed_gate_seal_flows_into_analysis_without_fake_safety(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "e6-v2"
    _patch_runner_offline(monkeypatch, output_root)
    run = _run_offline_prefix(
        "deepseek", _OfflineRunnerDispatcher(runtime_provider_failures=4)
    )
    assert run["executed"] == 12
    assert run["window_gate_passed"] is False

    seal = runner.seal_block(
        "deepseek",
        runner.EXECUTION_BLOCK_ID,
        completed_at="2026-08-30T00:00:00+08:00",
    )
    raw = [
        json.loads(line)
        for line in runner._raw_path("deepseek")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    state = json.loads(
        runner._window_state_path("deepseek", runner.EXECUTION_BLOCK_ID).read_text(
            encoding="utf-8"
        )
    )
    gate = json.loads(
        runner._gate_path("deepseek", runner.EXECUTION_BLOCK_ID).read_text(
            encoding="utf-8"
        )
    )
    result, _ = analysis.analyze_provider_block(
        "deepseek",
        plan_rows=runner._window_rows("deepseek", runner.EXECUTION_BLOCK_ID),
        raw_rows=raw,
        gate=gate,
        state=state,
        close=seal,
        bootstrap_replicates=20,
    )

    assert seal["administrative_closure_rows"] == 348
    assert result["audit"]["scientific_terminal_latest_work_items"] == 12
    assert result["audit"]["administrative_closure_work_items"] == 348
    assert result["audit"]["physical_attempt_rows"] == 12
    assert result["burden"]["overall"]["physical_attempt_rows"] == 12
    assert result["cell_summary"]["all|no_defense"]["unsafe_terminal"][
        "denominator"
    ] == 2
    assert result["paired_comparisons"]["unsafe_effect"]["comparisons"][
        "full_safe_vs_no_defense"
    ]["complete_pairs"] == 2
    assert result["timing"]["last_observed_at"] == (
        "2026-08-29T23:00:00+08:00"
    )
    assert result["timing"]["sealed_at"] == "2026-08-30T00:00:00+08:00"
    assert result["timing"][
        "administrative_closure_rows_excluded_from_observation_time"
    ] == 348


def test_analysis_module_does_not_import_provider_clients() -> None:
    source = inspect.getsource(analysis)

    assert "deepseek_json_client" not in source
    assert "gemini_json_client" not in source
    assert "official_provider_executor" not in source
    assert "e6_cross_provider_calibration_runner_v2" not in source
