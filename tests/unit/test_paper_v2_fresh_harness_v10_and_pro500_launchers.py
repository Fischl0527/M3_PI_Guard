from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HARNESS_LAUNCHER = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v10.ps1"
)
PRO500_LAUNCHER = (
    PROJECT_ROOT
    / "outputs/verification/start_adaptive_formal_pro_500_guarded_v1.ps1"
)


def test_fresh_harness_v10_launcher_is_single_use_non_network_detached() -> None:
    source = HARNESS_LAUNCHER.read_text(encoding="utf-8")

    assert "experiment_closeout_fresh_harness_v10_20260807" in source
    assert "run directory already exists; launcher is single-use" in source
    assert "verify_with_receipt_v3.ps1" in source
    assert "-PassThru" in source
    assert "automatic_restart = $false" in source
    assert "network_or_provider_call_authorized = $false" in source
    assert "live_provider_processes_may_continue_independently = $false" in source


def test_pro500_launcher_binds_exact_runner_and_single_use_roots() -> None:
    source = PRO500_LAUNCHER.read_text(encoding="utf-8")

    assert "adaptive_formal_pro_500_guarded_v1_launch_20260807" in source
    assert "adaptive_formal_pro_500_guarded_v1_20260807" in source
    assert "adaptive_formal_pro_500_guarded_runner_v1" in source
    assert "adaptive_formal_pro_500_activation_gate_v1_20260807.json" in source
    assert "adaptive_formal_pro_500_candidate_v2.json" in source
    assert "adaptive_formal_pro_500_admission_v2.json" in source
    assert "retry is forbidden" in source
    assert "-PassThru" in source
    assert "-RedirectStandardOutput" in source
    assert "-RedirectStandardError" in source


def test_pro500_launcher_never_reads_config_or_enables_effects() -> None:
    source = PRO500_LAUNCHER.read_text(encoding="utf-8")

    assert "project.local.env" in source
    assert "Get-Content" not in source
    assert "automatic_restart = $false" in source
    assert "provider_tools_enabled = $false" in source
    assert "external_effects_enabled = $false" in source
    assert "scientific_outcomes_accessed_by_launcher = $false" in source
    assert "result_admission_authorized = $false" in source
