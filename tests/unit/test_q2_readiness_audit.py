from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.audit_q2_readiness import (
    _confirmatory_blind,
    _model_coverage,
    _public_benchmark,
    _select_matching_monitor,
)
from experiments.paper_v1.benchmarks.common import portable_value, resolve_artifact_path


def test_q2_public_benchmark_does_not_score_stale_detector_monitor() -> None:
    criterion = _public_benchmark(
        {"status": "completed"},
        {"expected_case_runs": 100, "complete_case_runs": 0, "result_completeness_gate": "not_satisfied"},
        {"status": "running"},
        Path("E:/runs/agentdojo_transformers_pi_detector/run_manifest.json"),
        {
            "health_status": "running_progressing",
            "pid_alive": True,
            "run_manifest_path": "E:/runs/agentdojo_tool_filter/run_manifest.json",
            "counts": {"completed_cases": 164, "failed_cases": 0, "missing_cases": 562},
        },
        {},
    )

    evidence = criterion["evidence"]
    assert criterion["earned"] == 3.0
    assert evidence["transformers_detector_scored_status"] == "not_admitted_or_not_progressing"
    assert evidence["transformers_detector_monitor_matches_selected_run"] is False


def test_q2_public_benchmark_scores_matching_live_detector_monitor_only() -> None:
    run_manifest_path = Path("E:/runs/agentdojo_transformers_pi_detector/run_manifest.json")

    criterion = _public_benchmark(
        {"status": "completed"},
        {"expected_case_runs": 100, "complete_case_runs": 0, "result_completeness_gate": "not_satisfied"},
        {"status": "running"},
        run_manifest_path,
        {
            "health_status": "running_progressing",
            "pid_alive": True,
            "run_manifest_path": str(run_manifest_path),
            "counts": {"completed_cases": 10, "failed_cases": 0, "missing_cases": 90},
        },
        {},
    )

    evidence = criterion["evidence"]
    assert criterion["earned"] == 3.5
    assert evidence["transformers_detector_scored_status"] == "running_progressing"
    assert evidence["transformers_detector_monitor_matches_selected_run"] is True


def test_q2_selects_monitor_matching_selected_transformers_run(tmp_path: Path) -> None:
    run_manifest_path = tmp_path / "selected" / "run_manifest.json"
    run_manifest_path.parent.mkdir()
    run_manifest_path.write_text("{}", encoding="utf-8")
    generic_monitor_path = tmp_path / "generic_monitor.json"
    selected_monitor_path = tmp_path / "selected_monitor.json"
    generic_monitor_path.write_text(
        json.dumps({"run_manifest_path": str(tmp_path / "other" / "run_manifest.json")}),
        encoding="utf-8",
    )
    selected_monitor_path.write_text(
        json.dumps({"run_manifest_path": str(run_manifest_path), "pid_alive": False}),
        encoding="utf-8",
    )

    selected_path, monitor, selection = _select_matching_monitor(
        run_manifest_path,
        generic_monitor_path=generic_monitor_path,
        selected_monitor_path=selected_monitor_path,
    )

    assert selected_path == selected_monitor_path
    assert monitor["pid_alive"] is False
    assert selection["selection_reason"] == "selected_run_monitor_matches_selected_run"
    assert selection["generic_monitor_matches_selected_run"] is False
    assert selection["selected_run_monitor_matches_selected_run"] is True


def test_q2_model_coverage_counts_admitted_frontier_candidate_from_audit() -> None:
    criterion = _model_coverage(
        {
            "summary": {
                "local_model_slots": 7,
                "modern_open_7b_14b_slots": 2,
                "frontier_api_vendor_slots": 0,
            }
        },
        {
            "status": "registry_satisfied_pending_formal_runs",
            "registered_frontier_api_vendor_count": 2,
            "selected_model_registry_path": "E:/repo/protocols/model_registry_v3_candidate.json",
            "model_registry_selection": {
                "selection_reason": "admitted_frontier_registry_candidate"
            },
        },
    )

    assert criterion["earned"] == 10.0
    assert criterion["status"] == "complete"
    assert criterion["blockers"] == []
    assert criterion["evidence"]["frontier_api_vendor_slots"] == 2


def test_q2_confirmatory_blind_rejects_manifest_without_admitted_candidate() -> None:
    criterion = _confirmatory_blind(
        {
            "formal_evidence_policy": {"E17": "historical_sample_only"},
            "m3_v2_independent_blind_manifest": {
                "status": "completed_formal",
                "result_eligible_for_confirmatory_q2_tables": True,
                "selected_cases": 600,
                "split": "independent_blind",
                "candidate_sha256": "a" * 64,
            },
        },
        {
            "status": "blocked_missing_candidate",
            "result_eligible_for_confirmatory_q2_tables": False,
        },
    )

    assert criterion["status"] == "blocked"
    assert criterion["earned"] == 2.0
    assert "blind_manifest_candidate_audit_admitted" in criterion["blockers"]
    assert criterion["evidence"]["new_blind_manifest_declared"] is False


def test_q2_confirmatory_blind_rejects_candidate_hash_mismatch() -> None:
    criterion = _confirmatory_blind(
        {
            "formal_evidence_policy": {"E17": "historical_sample_only"},
            "m3_v2_independent_blind_manifest": {
                "status": "completed_formal",
                "result_eligible_for_confirmatory_q2_tables": True,
                "selected_cases": 600,
                "split": "independent_blind",
                "candidate_sha256": "b" * 64,
            },
        },
        {
            "status": "admitted_independent_blind",
            "result_eligible_for_confirmatory_q2_tables": True,
            "candidate_sha256": "a" * 64,
        },
    )

    assert criterion["status"] == "blocked"
    assert criterion["earned"] == 2.0
    assert "blind_manifest_manifest_candidate_sha_matches_admission" in criterion["blockers"]
    assert criterion["evidence"]["new_blind_manifest_declared"] is False


def test_q2_confirmatory_blind_accepts_admitted_formal_600_case_manifest() -> None:
    criterion = _confirmatory_blind(
        {
            "m3_v2_independent_blind_manifest": {
                "status": "completed_formal",
                "result_eligible_for_confirmatory_q2_tables": True,
                "summary": {"total_cases": "600"},
                "evidence_status": "formal_confirmatory_blind",
                "sources": {
                    "independent_blind_candidate": {
                        "sha256": "a" * 64,
                    }
                },
            },
        },
        {
            "status": "admitted_independent_blind",
            "result_eligible_for_confirmatory_q2_tables": True,
            "candidate_sha256": "a" * 64,
        },
    )

    assert criterion["status"] == "complete"
    assert criterion["earned"] == 15.0
    assert criterion["blockers"] == []
    assert criterion["evidence"]["new_blind_manifest_declared"] is True


def test_q2_confirmatory_blind_does_not_fallback_when_explicit_index_is_empty() -> None:
    criterion = _confirmatory_blind(
        {
            "formal_evidence_policy": {"E17": "historical_sample_only"},
            "m3_v2_independent_blind_manifest": {
                "status": "completed_formal",
                "result_eligible_for_confirmatory_q2_tables": True,
                "selected_cases": 600,
                "split": "independent_blind",
                "candidate_sha256": "a" * 64,
            },
        },
        {
            "status": "admitted_independent_blind",
            "result_eligible_for_confirmatory_q2_tables": True,
            "candidate_sha256": "a" * 64,
        },
        {},
    )

    assert criterion["status"] == "blocked"
    assert "blind_manifest_reference_present" in criterion["blockers"]


def test_q2_generated_audit_uses_relative_paths_for_in_repo_artifacts() -> None:
    checkout_name = "M3_PI_" + "Guard_test"
    repo_root = Path("E:/portable") / checkout_name
    payload = {
        "manifest": str(repo_root / "outputs" / "run_manifest.json"),
        "nested": [str(repo_root / "protocols" / "freeze.json")],
        "external_model": r"E:\Ollama\models",
    }

    portable = portable_value(payload, root=repo_root)

    assert portable["manifest"] == "outputs/run_manifest.json"
    assert portable["nested"] == ["protocols/freeze.json"]
    assert portable["external_model"] == r"E:\Ollama\models"


def test_relocated_frozen_reference_resolves_without_rewriting_snapshot(
    tmp_path: Path,
) -> None:
    current = tmp_path / "protocols" / "paper_upgrade_v1" / "freeze.json"
    current.parent.mkdir(parents=True)
    current.write_text("{}\n", encoding="utf-8")
    old = Path("Z:/old_checkout/protocols/paper_upgrade_v1/freeze.json")

    assert resolve_artifact_path(old, root=tmp_path) == current.resolve()
