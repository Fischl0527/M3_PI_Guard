from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v9.ps1"
)


def test_v9_launcher_is_fresh_single_use_and_non_authorizing() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "experiment_closeout_fresh_harness_v9_20260807" in source
    assert "verify_with_receipt_v3.ps1" in source
    assert "run directory already exists" in source
    assert "-WindowStyle Hidden -PassThru" in source
    assert "automatic_restart = $false" in source
    assert "network_or_provider_call_authorized = $false" in source
    assert "live_provider_processes_may_continue_independently = $false" in source


def test_v9_launcher_does_not_start_provider_or_formal_controller() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "adaptive_formal_pro_controller" not in source
    assert "formal_matrix_controller_v7" not in source
    assert "--execute" not in source
    assert r"config\project.local.env" not in source
