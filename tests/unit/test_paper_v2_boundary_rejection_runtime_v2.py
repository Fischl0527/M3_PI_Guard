from __future__ import annotations

from typing import Any, Mapping

import pytest

from experiments.paper_v2.boundary_rejection_runtime_v2 import (
    BOUNDARY_REJECTION_REASON,
    PROPOSAL_EFFECT_REJECTION_MESSAGES,
    BoundaryAwareM3EffectBackendV2,
    build_boundary_aware_safety_receipt_v2,
)
from experiments.paper_v2.provider_safety import ProviderSafetyError


class _RejectingBackend:
    backend_id = "m3_sandbox_fixture"

    def __init__(self, message: str) -> None:
        self.message = message
        self.executed = 0

    def execute(self, tool: str, arguments: Mapping[str, Any]) -> Any:
        del tool, arguments
        self.executed += 1
        raise ProviderSafetyError(self.message)

    def evaluator_material(self) -> Mapping[str, Any]:
        return {"delegate_calls": self.executed}

    def close(self) -> None:
        return None


@pytest.mark.parametrize("message", sorted(PROPOSAL_EFFECT_REJECTION_MESSAGES))
def test_every_explicit_proposal_rejection_becomes_no_effect(
    message: str,
) -> None:
    delegate = _RejectingBackend(message)
    backend = BoundaryAwareM3EffectBackendV2(delegate)

    observed = backend.execute("tool", {"value": "synthetic"})
    material = backend.evaluator_material()

    assert observed == {
        "error": BOUNDARY_REJECTION_REASON,
        "effect_applied": False,
    }
    assert delegate.executed == 1
    assert material["boundary_rejections"] == [
        {
            "tool": "tool",
            "arguments": {"value": "synthetic"},
            "reason_code": BOUNDARY_REJECTION_REASON,
            "effect_applied": False,
            "safety_message_class": message,
        }
    ]


@pytest.mark.parametrize(
    "message",
    [
        "provider endpoint path is not inference-only",
        "external connectors must remain disabled",
        "provider safety receipt fields drift",
        "effect backend is not isolated",
    ],
)
def test_nonproposal_integrity_errors_are_not_reclassified(message: str) -> None:
    backend = BoundaryAwareM3EffectBackendV2(_RejectingBackend(message))
    with pytest.raises(ProviderSafetyError, match=message):
        backend.execute("tool", {})


def test_host_execution_receipt_is_no_effect_and_endpoint_error_is_not() -> None:
    receipt = build_boundary_aware_safety_receipt_v2(
        provider_id="deepseek",
        endpoint_url="https://api.deepseek.com/chat/completions",
        effect_backend="m3_sandbox_fixture",
        tool="shell",
        arguments={"command": "synthetic"},
    )
    assert receipt["evidence"]["effect_backend"] == "no_effect"
    assert receipt["evidence"]["tool"] == "final"

    with pytest.raises(
        ProviderSafetyError,
        match="provider endpoint path is not inference-only",
    ):
        build_boundary_aware_safety_receipt_v2(
            provider_id="deepseek",
            endpoint_url="https://api.deepseek.com/not-inference",
            effect_backend="m3_sandbox_fixture",
            tool="final",
            arguments={"answer": ""},
        )
