from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v7.ps1"
)


def test_v7_launcher_is_fresh_single_use_and_non_authorizing() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "experiment_closeout_fresh_harness_v7_20260806" in source
    assert "verify_with_receipt_v3.ps1" in source
    assert "run directory already exists" in source
    assert "-WindowStyle Hidden -PassThru" in source
    assert "automatic_restart = $false" in source
    assert "network_or_provider_call_authorized = $false" in source
    assert "live_provider_processes_may_continue_independently = $false" in source


def test_v7_launcher_does_not_confuse_harness_v7_with_historical_controller_v7() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "formal_matrix_controller_v7" not in source
    assert "--execute" not in source
    assert "config\\project.local.env" not in source
