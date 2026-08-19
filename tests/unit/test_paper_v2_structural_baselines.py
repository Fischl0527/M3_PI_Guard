from __future__ import annotations

import pytest

from experiments.paper_v2.structural_baselines import (
    StructuralBaselineError,
    VigilRuntimeAdapter,
    build_official_drift_pipeline,
    default_drift_args,
    verify_registry,
)


class NoCallClient:
    total_tokens = 0

    def __getattr__(self, name: str):
        raise AssertionError(f"provider method must not be called in smoke: {name}")


class MemoryLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(str(message))


def _prepared_vigil() -> VigilRuntimeAdapter:
    adapter = VigilRuntimeAdapter()
    adapter.prepare_from_constraint_payload(
        user_query="Send after confirmation; never delete.",
        constraints=[
            {
                "constraint_id": "confirm_send",
                "constraint_type": "require_confirmation",
                "description": "Confirm send.",
                "condition": {"tool_name": "send"},
                "priority": 1,
            },
            {
                "constraint_id": "forbid_delete",
                "constraint_type": "forbid",
                "description": "Forbid delete.",
                "condition": {"tool_name": "delete"},
                "priority": 1,
            },
        ],
    )
    return adapter


def test_vigil_official_auditor_maps_allow_ask_deny() -> None:
    adapter = _prepared_vigil()

    assert adapter.decide(tool_name="read", arguments={}).decision == "ALLOW"
    assert adapter.decide(tool_name="send", arguments={}).decision == "ASK"
    assert adapter.decide(tool_name="delete", arguments={}).decision == "DENY"


def test_vigil_provider_generation_is_fail_closed_before_cost_gate() -> None:
    adapter = VigilRuntimeAdapter(allow_provider_calls=False)

    with pytest.raises(StructuralBaselineError, match="provider/cost gate"):
        adapter.prepare_from_user_query("Summarize the report.")


def test_drift_official_pipeline_constructs_without_model_call() -> None:
    args = default_drift_args("test-model")
    pipeline = build_official_drift_pipeline(
        client=NoCallClient(),
        logger=MemoryLogger(),
        args=args,
    )

    assert [type(element).__name__ for element in pipeline.elements] == [
        "InitQuery",
        "DRIFTLLM",
        "DRIFTToolsExecutionLoop",
    ]
    assert args.build_constraints is True
    assert args.injection_isolation is True
    assert args.dynamic_validation is True
    assert pipeline.name == "test-model-drift"


def test_structural_registry_reproduces_and_keeps_results_pending() -> None:
    registry = verify_registry()

    assert registry["provider_calls_made"] == 0
    assert registry["baselines"]["vigil"]["qualification"] == "pass"
    assert registry["baselines"]["drift"]["qualification"] == "pass"
    assert registry["baselines"]["vigil"]["formal_admission"] is False
    assert registry["baselines"]["drift"]["formal_admission"] is False
    assert registry["medium_baseline_resolution"]["resolved"] is False
