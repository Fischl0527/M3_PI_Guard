from __future__ import annotations

import copy
from collections.abc import Mapping

import pytest

from experiments.paper_v2.boundary_rejection_runtime_v3 import (
    ADAPTER_VERSION,
    BOUNDARY_REJECTION_REASON,
    PROPOSAL_EFFECT_REJECTION_MESSAGES,
    BoundaryAwareM3EffectBackendV3,
    validate_boundary_rejections_v3,
)
from experiments.paper_v2.m3_offline_evaluator import M3OfflineEvaluatorError
from experiments.paper_v2.provider_safety import ProviderSafetyError


class _RejectingDelegate:
    backend_id = "m3_sandbox_fixture"

    def __init__(self, message: str) -> None:
        self.message = message

    def execute(self, tool: str, arguments: Mapping[str, object]) -> object:
        del tool, arguments
        raise ProviderSafetyError(self.message)

    def evaluator_material(self) -> Mapping[str, object]:
        return {"fixture": "qualified"}

    def close(self) -> None:
        return None


@pytest.mark.parametrize(
    "message",
    sorted(PROPOSAL_EFFECT_REJECTION_MESSAGES),
)
def test_all_proposal_messages_round_trip_through_evidence_validator(
    message: str,
) -> None:
    backend = BoundaryAwareM3EffectBackendV3(
        _RejectingDelegate(message)
    )
    result = backend.execute(
        "synthetic_tool",
        {"nested": {"value": 1}, "items": ["a", "b"]},
    )
    material = backend.evaluator_material()

    assert result == {
        "error": BOUNDARY_REJECTION_REASON,
        "effect_applied": False,
    }
    assert material["boundary_adapter_version"] == ADAPTER_VERSION
    assert validate_boundary_rejections_v3(material) == 1


def test_tampered_message_digest_is_rejected() -> None:
    backend = BoundaryAwareM3EffectBackendV3(
        _RejectingDelegate(next(iter(PROPOSAL_EFFECT_REJECTION_MESSAGES)))
    )
    backend.execute("synthetic_tool", {"value": 1})
    material = copy.deepcopy(dict(backend.evaluator_material()))
    material["boundary_rejections"][0]["safety_message_sha256"] = "0" * 64

    with pytest.raises(
        M3OfflineEvaluatorError,
        match="boundary rejection evidence is malformed",
    ):
        validate_boundary_rejections_v3(material)
