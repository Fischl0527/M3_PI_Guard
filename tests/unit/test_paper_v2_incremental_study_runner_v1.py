from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

import experiments.paper_v2.incremental_study_runner_v1 as runner
from experiments.paper_v2.formal_condition_executors import (
    ALL_CONDITION_PROFILES,
    OnlineExecutorContext,
)
from experiments.paper_v2.live_condition_runtime import (
    _runtime_inputs,
    deserialize_task_policy_manifest,
)


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
            raise RuntimeError("synthetic response-less transport failure")
        model = str(work_item["model_id"])
        return {
            "unsafe_effect": True,
            "task_completion": False,
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
                "usage_summary": {"cumulative_cost_cny": 0.001},
            },
            "recorded_at": "2026-08-26T00:00:00+08:00",
        }


def _patch_output(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(runner, "OUTPUT_ROOT", root)


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_regular_plans_are_frozen_and_have_eight_balanced_prefix_rows() -> None:
    for study, expected in runner.EXPECTED_COUNTS.items():
        rows = runner._load_regular_plan(study)
        prefix = [row for row in rows if row["formal_prefix"] is True]
        assert len(rows) == expected
        assert len(prefix) == 8
        if study == "provenance":
            assert {row["evaluation_case_type"] for row in prefix} == {
                "controlled_tool"
            }
        elif study == "challenge":
            assert {row["evaluation_case_type"] for row in prefix} == {"attack"}
        else:
            assert {row["evaluation_case_type"] for row in prefix} == {
                "attack",
                "benign_tool",
            }
            assert {row["condition_id"] for row in prefix} == {
                "m3_policy_only",
                "m3_policy_safe_prompt",
                "m3_full_normal_prompt",
                "m3_full",
            }


@pytest.mark.parametrize(
    ("study", "model_id", "expected_prices", "expected_limit"),
    [
        (
            "factorial",
            "deepseek-v4-pro",
            (0.30, 9.0, 27.0),
            8.0,
        ),
        (
            "flash",
            "deepseek-v4-flash",
            (0.10, 3.0, 9.0),
            3.0,
        ),
    ],
)
def test_incremental_policy_uses_current_peak_pricing_without_mutating_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    study: str,
    model_id: str,
    expected_prices: tuple[float, float, float],
    expected_limit: float,
) -> None:
    _patch_output(monkeypatch, tmp_path / "incremental")
    historical = runner.build_role_policy(
        runner.load_public_policy(),
        "second" if model_id.endswith("flash") else "primary",
    )
    historical_prices = dict(historical["deepseek"]["pricing"])
    policy = runner._bounded_role_policy(study)
    pricing = policy["deepseek"]["pricing"]
    assert policy["deepseek"]["hard_spend_limit_cny"] == expected_limit
    assert (
        pricing["cache_hit_input_per_million_tokens"],
        pricing["cache_miss_input_per_million_tokens"],
        pricing["output_per_million_tokens"],
    ) == expected_prices
    assert pricing["verified_at"] == "2026-08-26"
    assert pricing["tariff_window"] == "peak_conservative_upper_bound"
    assert historical["deepseek"]["pricing"] == historical_prices


def test_canary_gate_is_outcome_blind_and_success_is_never_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output(monkeypatch, tmp_path / "incremental")
    dispatcher = _Dispatcher()
    first = runner.run_regular_study(
        "factorial",
        canary_only=True,
        config_path=None,
        credential_loader=lambda: {},
        dispatcher_factory=lambda _permit, _rows: dispatcher,
    )
    second = runner.run_regular_study(
        "factorial",
        canary_only=True,
        config_path=None,
        credential_loader=lambda: pytest.fail("credentials were loaded again"),
        dispatcher_factory=lambda *_: pytest.fail("successful rows were rerun"),
    )
    rows = _rows(runner._raw_path("factorial"))
    gate = json.loads(runner._canary_gate_path("factorial").read_text("utf-8"))
    assert first["executed"] == 8
    assert first["canary_gate_passed"] is True
    assert second["executed"] == 0
    assert gate["scientific_outcomes_inspected"] is False
    assert len(rows) == 8
    assert all(row["unsafe_effect"] is True for row in rows)
    assert all(row["response_obtained"] is True for row in rows)
    assert all(row["online_forbidden_fields_present"] is False for row in rows)
    assert all(row["provider_tools_enabled"] is False for row in rows)
    assert all(row["external_effects_enabled"] is False for row in rows)
    assert all(row["provider_failure_types"] == [] for row in rows)


def test_provider_failure_types_are_content_free_and_deduplicated() -> None:
    assert runner._provider_failure_types(
        {
            "provider_trace_bundle": {
                "failures": [
                    {"error_type": "ProviderTransportError", "status": "provider_failure"},
                    {"error_type": "ProviderTransportError", "status": "provider_failure"},
                    {"error_type": "ProviderPausedError", "status": "paused"},
                ]
            }
        }
    ) == ["ProviderPausedError", "ProviderTransportError"]


def test_only_explicit_response_less_row_is_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output(monkeypatch, tmp_path / "incremental")
    prefix = [
        row
        for row in runner._load_regular_plan("factorial")
        if row["formal_prefix"] is True
    ]
    failed_key = str(prefix[0]["work_key"])
    first_dispatcher = _Dispatcher(fail_once={failed_key})
    first = runner.run_regular_study(
        "factorial",
        canary_only=True,
        config_path=None,
        credential_loader=lambda: {},
        dispatcher_factory=lambda _permit, _rows: first_dispatcher,
    )
    assert first["executed"] == 1
    first_row = _rows(runner._raw_path("factorial"))[0]
    assert first_row["response_obtained"] is False
    assert first_row["retry_eligible"] is True

    retry_dispatcher = _Dispatcher()
    retried = runner.run_regular_study(
        "factorial",
        canary_only=True,
        config_path=None,
        retry_failed_work_keys=(failed_key,),
        credential_loader=lambda: {},
        dispatcher_factory=lambda _permit, _rows: retry_dispatcher,
    )
    assert retried["executed"] == 8
    assert retried["canary_gate_passed"] is True
    attempts = [
        row["attempt"]
        for row in _rows(runner._raw_path("factorial"))
        if row["work_key"] == failed_key
    ]
    assert attempts == [1, 2]

    with pytest.raises(runner.IncrementalStudyRunnerError, match="cannot be retried"):
        runner.run_regular_study(
            "factorial",
            canary_only=True,
            config_path=None,
            retry_failed_work_keys=(failed_key,),
            credential_loader=lambda: {},
            dispatcher_factory=lambda *_: _Dispatcher(),
        )


def test_controlled_prompt_pair_changes_only_the_source_authority_label() -> None:
    rows = runner._load_regular_plan("provenance")
    seed = next(
        row
        for row in rows
        if row["source_authority_variant"] == "trusted_origin"
        and row["condition_id"] == "m3_full_normal_prompt"
    )
    pair = [
        row
        for row in rows
        if row["base_task_id"] == seed["base_task_id"]
        and row["condition_id"] == seed["condition_id"]
    ]
    assert {row["source_authority_variant"] for row in pair} == {
        "trusted_origin",
        "untrusted_origin",
    }
    messages: dict[str, list[dict[str, str]]] = {}
    for row in pair:
        hydrated, state, _digest = runner._hydrate_regular("provenance", row)
        context = OnlineExecutorContext(
            execution_identity=str(hydrated["execution_identity"]),
            work_key=str(hydrated["work_key"]),
            benchmark=str(hydrated["benchmark"]),
            condition_id=str(hydrated["condition_id"]),
            max_provider_calls=int(hydrated["max_provider_calls"]),
            online_state=state,
        )
        view, schemas = _runtime_inputs(context)
        manifest = deserialize_task_policy_manifest(
            state["runtime_control"]["authorization"]["manifest"]
        )
        messages[str(row["source_authority_variant"])] = (
            runner._controlled_message_builder(
                context,
                view,
                schemas,
                manifest,
                ALL_CONDITION_PROFILES[str(row["condition_id"])],
            )
        )
    trusted = json.dumps(messages["trusted_origin"], sort_keys=True)
    untrusted = json.dumps(messages["untrusted_origin"], sort_keys=True)
    assert "trusted_app_context" in trusted
    assert "untrusted_memory" in untrusted
    assert trusted.replace("trusted_app_context", "SOURCE") == untrusted.replace(
        "untrusted_memory", "SOURCE"
    )
