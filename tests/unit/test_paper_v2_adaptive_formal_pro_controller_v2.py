from __future__ import annotations

import copy
from pathlib import Path

import pytest

import experiments.paper_v2.adaptive_formal_pro_controller_v1 as v1
import experiments.paper_v2.adaptive_formal_pro_controller_v2 as controller
from experiments.paper_v2.contracts import sha256_canonical_json


def test_frozen_pro_50_candidate_binds_order_gate_and_fresh_identity() -> None:
    candidate = controller.verify_stage_candidate("pro_50")

    assert candidate["scope"]["authorized_task_count"] == 32
    assert candidate["scope"]["run_id"] == "paper-v2-adaptive-pro_50-v2"
    assert "adaptive_formal_pro_v2" in candidate["scope"]["output_root"]
    assert (
        candidate["order_gate_manifest_sha256"]
        == controller.order_gate.verify_supersession_order_review()[
            "manifest_sha256"
        ]
    )
    assert candidate["predecessor_review_lock"] is None
    assert candidate["authorization"]["stage_execution_authorized"] is False
    assert candidate["authorization"]["result_admission_authorized"] is False
    assert candidate["execution_controls"]["automatic_retries"] == 0


def test_pro_50_admission_is_exact_and_result_sealed() -> None:
    admission = controller.build_stage_admission(
        "pro_50",
        owner_statement_sha256=controller.OWNER_STATEMENT_SHA256,
        approved_at="2026-08-03T12:15:00+08:00",
    )

    assert "adaptive_formal_pro_controller_v2" in admission["exact_command"]
    assert admission["stage"] == "pro_50"
    assert admission["predecessor_review_lock"] is None
    assert admission["authorization"]["stage_execution_authorized"] is True
    assert admission["authorization"]["result_admission_authorized"] is False
    assert admission["authorization"]["automatic_retries"] == 0
    assert admission["authorization"]["provider_tools_enabled"] is False
    assert admission["authorization"]["external_effects_enabled"] is False


def test_candidate_rejects_rehashed_order_gate_drift() -> None:
    candidate = controller.verify_stage_candidate("pro_50")
    tampered = copy.deepcopy(candidate)
    tampered["order_gate_manifest_sha256"] = "0" * 64
    core = {
        key: value for key, value in tampered.items() if key != "manifest_sha256"
    }
    tampered["manifest_sha256"] = sha256_canonical_json(core)

    with pytest.raises(
        controller.AdaptiveFormalProControllerV2Error,
        match="candidate drift",
    ):
        controller.validate_stage_candidate(tampered, stage="pro_50")


def test_delegated_runtime_restores_v1_entry_points() -> None:
    names = (
        "candidate_path",
        "admission_path",
        "review_path",
        "canonical_stage_command",
        "verify_stage_candidate",
        "validate_stage_admission",
    )
    original = {name: getattr(v1, name) for name in names}

    with controller._delegated_runtime():
        assert v1.candidate_path is controller.candidate_path
        assert v1.admission_path is controller.admission_path
        assert v1.review_path is controller.review_path

    assert {name: getattr(v1, name) for name in names} == original


def test_v1_candidate_and_output_identity_remain_superseded() -> None:
    old = v1.verify_stage_candidate("pro_50")
    new = controller.verify_stage_candidate("pro_50")

    assert old["manifest_sha256"] != new["manifest_sha256"]
    assert old["scope"]["execution_identity"] != new["scope"][
        "execution_identity"
    ]
    assert old["scope"]["output_root"] != new["scope"]["output_root"]


def test_execute_delegates_with_v2_paths_then_restores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_candidate_path = v1.candidate_path
    observed: dict[str, object] = {}

    def fake_execute(
        stage: str, *, selected_admission: Path, config_path: Path | None
    ) -> dict[str, object]:
        observed["stage"] = stage
        observed["selected_admission"] = selected_admission
        observed["config_path"] = config_path
        observed["candidate_path"] = v1.candidate_path
        observed["admission_path"] = v1.admission_path
        observed["review_path"] = v1.review_path
        return {"status": "injected_no_provider"}

    monkeypatch.setattr(v1, "execute_stage", fake_execute)
    admission = controller.admission_path("pro_50")
    config = Path("config/project.local.env")

    result = controller.execute_stage(
        "pro_50", selected_admission=admission, config_path=config
    )

    assert result == {"status": "injected_no_provider"}
    assert observed == {
        "stage": "pro_50",
        "selected_admission": admission,
        "config_path": config,
        "candidate_path": controller.candidate_path,
        "admission_path": controller.admission_path,
        "review_path": controller.review_path,
    }
    assert v1.candidate_path is original_candidate_path
