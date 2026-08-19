from __future__ import annotations

import copy
import re
import hashlib
from pathlib import Path

import pytest

import experiments.paper_v2.adaptive_execution_order_gate_v2 as gate
import experiments.paper_v2.adaptive_formal_deepseek_flash_controller_v1 as flash_v1
import experiments.paper_v2.adaptive_formal_pro_controller_v1 as pro_v1
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


def _write_manifest(path: Path, core: dict[str, object]) -> dict[str, object]:
    value = {**core, "manifest_sha256": sha256_canonical_json(core)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def _passing_review(path: Path, stage: str) -> dict[str, object]:
    schema, status = gate.EXPECTED_REVIEW_CONTRACTS[stage]
    return _write_manifest(
        path,
        {
            "schema_version": schema,
            "artifact_role": "test_only_outcome_blind_technical_review",
            "status": status,
            "stage": stage,
            "run_id": f"test-{stage}",
            "execution_identity": "1" * 64,
            "candidate_manifest_sha256": "2" * 64,
            "admission_file_sha256": "3" * 64,
            "authorized_task_count": 2,
            "terminal_task_count": 2,
            "completed_provider_call_count": 2,
            "query_ledger_tail_sha256": "4" * 64,
            "budget_ledger_tail_sha256": "5" * 64,
            "task_ledger_tail_sha256": "6" * 64,
            "final_checkpoint_locks": [],
            "checks": {
                "all_query_attempts_terminal": True,
                "all_authorized_tasks_terminal": True,
                "provider_tools_disabled": True,
                "external_effects_disabled": True,
                "scientific_outcomes_not_aggregated": True,
            },
            "technical_gate_passed": True,
            "result_admission_authorized": False,
        },
    )


def _candidate_lock(path: Path, value: dict[str, object]) -> dict[str, object]:
    return {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "manifest_sha256": value["manifest_sha256"],
    }


def test_v1_assets_are_hash_locked_absent_and_explicitly_superseded() -> None:
    value = gate.build_supersession_order_review()

    assert value["status"] == (
        "v1_stages_superseded_before_execution_order_v2_frozen"
    )
    assert value["controls"] == {
        "v1_execution_authorized": False,
        "v2_execution_admissions_created_by_this_gate": 0,
        "provider_clients_constructed": 0,
        "credentials_read": False,
        "network_calls_made": 0,
        "provider_calls_made": 0,
        "scientific_outcomes_read": 0,
        "historical_assets_modified": False,
        "real_external_effects": 0,
    }
    seals = {row["stage"]: row for row in value["v1_seals"]}
    assert set(seals) == {"pro_50", "flash_50"}
    for stage, seal in seals.items():
        assert seal["candidate_file_lock"] == (
            gate.EXPECTED_V1_ASSET_LOCKS[stage]["candidate"]
        )
        assert seal["admission_file_lock"] == (
            gate.EXPECTED_V1_ASSET_LOCKS[stage]["admission"]
        )
        assert seal["candidate_admission_binding_matches"] is False
        assert seal["v1_execution_authorized"] is False
        assert seal["nonempty_output_files"] == 0
        assert all(not row["exists"] for row in seal["absence_evidence"])
        assert {
            row["kind"] for row in seal["absence_evidence"]
        } == {
            "output_root",
            "query_ledger",
            "provider_budget_ledger",
            "task_ledger",
            "provider_trace_root",
            "checkpoint_root",
            "technical_review",
        }
    assert (
        "flash_50_v1_omits_required_pro_hardest_2000_predecessor_review"
        in seals["flash_50"]["execution_forbidden_reasons"]
    )


def test_hash_locked_v1_admissions_are_already_fail_closed() -> None:
    with pytest.raises(
        pro_v1.AdaptiveFormalProControllerV1Error,
        match="stage admission drift",
    ):
        pro_v1.validate_stage_admission(
            pro_v1._read_json(pro_v1.admission_path("pro_50")),
            stage="pro_50",
        )
    with pytest.raises(
        flash_v1.AdaptiveFormalDeepSeekFlashControllerV1Error,
        match="Flash stage admission drift",
    ):
        flash_v1.validate_stage_admission(
            flash_v1._read_json(flash_v1.admission_path("flash_50")),
            stage="flash_50",
        )


def test_exact_predecessor_chain_includes_flash_200_before_gemini_day_0() -> None:
    value = gate.build_supersession_order_review()
    order = gate.validate_stage_order(value["stage_order"])

    assert [row["stage"] for row in order] == [
        "pro_50",
        "pro_200",
        "pro_500",
        "pro_hardest_2000",
        "flash_50",
        "flash_200",
        "gemini_day_0",
    ]
    assert gate.predecessor_for("gemini_day_0") == "flash_200"
    assert gate.predecessor_for("flash_50") == "pro_hardest_2000"
    assert value["gemini_day_0_predecessor"] == "flash_200"

    tampered = copy.deepcopy(order)
    tampered[-1]["predecessor"] = "flash_50"
    with pytest.raises(gate.AdaptiveExecutionOrderGateV2Error):
        gate.validate_stage_order(tampered)


def test_persisted_order_review_rebuilds_exactly() -> None:
    observed = gate.verify_supersession_order_review()
    assert observed == gate.build_supersession_order_review()
    assert observed["manifest_sha256"] == gate._manifest_sha(observed)


def test_absence_proof_fails_if_any_v1_evidence_path_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "PROJECT_ROOT", tmp_path)
    output = tmp_path / "v1-output"
    output.mkdir()
    with pytest.raises(
        gate.AdaptiveExecutionOrderGateV2Error,
        match="execution evidence exists",
    ):
        gate._expected_absence_rows("v1-output")


def test_successor_gate_requires_exact_hash_valid_passing_predecessor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        gate,
        "verify_supersession_order_review",
        lambda: {"manifest_sha256": "a" * 64},
    )
    review_path = tmp_path / "pro_50_review.json"
    _passing_review(review_path, "pro_50")
    lock = gate.build_predecessor_review_lock(
        review_path, expected_stage="pro_50"
    )

    context = gate.require_predecessor_before_candidate_build("pro_200", lock)
    assert context["candidate_build_prerequisite_passed"] is True
    assert context["predecessor_stage"] == "pro_50"
    assert context["execution_authorized"] is False
    assert context["network_calls_made"] == 0

    with pytest.raises(
        gate.AdaptiveExecutionOrderGateV2Error,
        match="predecessor must be pro_200",
    ):
        gate.require_predecessor_before_candidate_build("pro_500", lock)

    review_path.write_bytes(review_path.read_bytes() + b" ")
    with pytest.raises(
        gate.AdaptiveExecutionOrderGateV2Error,
        match="hash-locked adaptive artifact drift",
    ):
        gate.require_predecessor_before_candidate_build("pro_200", lock)


def test_failed_or_negative_style_predecessor_review_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "PROJECT_ROOT", tmp_path)
    review_path = tmp_path / "failed_review.json"
    value = _passing_review(review_path, "flash_50")
    core = {
        key: child for key, child in value.items() if key != "manifest_sha256"
    }
    core["technical_gate_passed"] = False
    _write_manifest(review_path, core)
    with pytest.raises(
        gate.AdaptiveExecutionOrderGateV2Error,
        match="did not pass",
    ):
        gate.build_predecessor_review_lock(
            review_path, expected_stage="flash_50"
        )

    negative_path = tmp_path / "negative_style.json"
    value = _passing_review(negative_path, "flash_50")
    core = {
        key: child for key, child in value.items() if key != "manifest_sha256"
    }
    core["checks"] = {
        "scientific_outcomes_aggregated": False,
        "all_authorized_tasks_terminal": True,
    }
    _write_manifest(negative_path, core)
    with pytest.raises(
        gate.AdaptiveExecutionOrderGateV2Error,
        match="did not pass",
    ):
        gate.build_predecessor_review_lock(
            negative_path, expected_stage="flash_50"
        )


def test_admission_prerequisite_requires_candidate_to_bind_order_and_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        gate,
        "verify_supersession_order_review",
        lambda: {"manifest_sha256": "a" * 64},
    )
    review_path = tmp_path / "pro_50_review.json"
    review = _passing_review(review_path, "pro_50")
    review_lock = gate.build_predecessor_review_lock(
        review_path, expected_stage="pro_50"
    )
    candidate_path = tmp_path / "pro_200_candidate_v2.json"
    candidate = _write_manifest(
        candidate_path,
        {
            "schema_version": "test-adaptive-candidate-2.0",
            "scope": {
                "stage": "pro_200",
                "prior_review_manifest_sha256": review["manifest_sha256"],
            },
            "order_gate_schema_version": gate.SCHEMA_VERSION,
            "order_gate_manifest_sha256": "a" * 64,
            "authorization": {"stage_execution_authorized": False},
            "evidence_boundary": {
                "credentials_read": False,
                "network_calls_made": 0,
            },
        },
    )
    candidate_lock = _candidate_lock(candidate_path, candidate)

    result = gate.require_predecessor_before_admission(
        "pro_200",
        successor_candidate_lock=candidate_lock,
        predecessor_review_lock=review_lock,
    )
    assert result["admission_prerequisite_passed"] is True
    assert result["execution_admission_created"] is False
    assert result["execution_authorized"] is False

    core = {
        key: child for key, child in candidate.items() if key != "manifest_sha256"
    }
    core["scope"] = {
        "stage": "pro_200",
        "prior_review_manifest_sha256": "0" * 64,
    }
    tampered = _write_manifest(candidate_path, core)
    with pytest.raises(
        gate.AdaptiveExecutionOrderGateV2Error,
        match="replacement candidate order binding invalid",
    ):
        gate.require_predecessor_before_admission(
            "pro_200",
            successor_candidate_lock=_candidate_lock(candidate_path, tampered),
            predecessor_review_lock=review_lock,
        )


def test_root_stage_rejects_fake_predecessor_and_v1_candidate_admission() -> None:
    with pytest.raises(
        gate.AdaptiveExecutionOrderGateV2Error,
        match="must not claim a predecessor",
    ):
        gate.require_predecessor_before_candidate_build(
            "pro_50", {"stage": "anything"}
        )

    candidate = gate._read_json(
        gate.PROJECT_ROOT
        / gate.EXPECTED_V1_ASSET_LOCKS["pro_50"]["candidate"]["path"]
    )
    old_lock = {
        **gate.EXPECTED_V1_ASSET_LOCKS["pro_50"]["candidate"],
        "manifest_sha256": candidate["manifest_sha256"],
    }
    with pytest.raises(
        gate.AdaptiveExecutionOrderGateV2Error,
        match="v1 adaptive candidate is superseded",
    ):
        gate.require_predecessor_before_admission(
            "pro_50", successor_candidate_lock=old_lock
        )


def test_current_harness_uses_supersession_review_and_only_current_admission() -> None:
    verify_source = (gate.PROJECT_ROOT / "harness/scripts/verify.ps1").read_text(
        encoding="utf-8"
    )
    start = verify_source.index(
        'Invoke-Check "Paper-v2 experiment closeout prospective evidence"'
    )
    end = verify_source.index(
        'if (Test-Path -LiteralPath "outputs/experiments/', start
    )
    closeout_block = verify_source[start:end]

    assert "experiments.paper_v2.adaptive_execution_order_gate_v2" in closeout_block
    assert '"--verify-review"' in closeout_block
    assert re.search(
        r'"-m",\s*"experiments\.paper_v2\.adaptive_formal_pro_controller_v2",\s*'
        r'"--verify-admission",\s*"--stage",\s*"pro_50"',
        closeout_block,
    )
    assert not re.search(
        r'"-m",\s*"experiments\.paper_v2\.adaptive_formal_pro_controller_v1",\s*'
        r'"--verify-admission",\s*"--stage",\s*"pro_50"',
        closeout_block,
    )
    assert not re.search(
        r'"-m",\s*"experiments\.paper_v2\.'
        r'adaptive_formal_deepseek_flash_controller_v1",\s*'
        r'"--verify-admission",\s*"--stage",\s*"flash_50"',
        closeout_block,
    )
