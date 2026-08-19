from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HARNESS_LAUNCHER = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v11.ps1"
)


def test_fresh_harness_v11_launcher_is_single_use_non_network_detached() -> None:
    source = HARNESS_LAUNCHER.read_text(encoding="utf-8")

    assert "experiment_closeout_fresh_harness_v11_20260807" in source
    assert "run directory already exists; launcher is single-use" in source
    assert "verify_with_receipt_v3.ps1" in source
    assert "-PassThru" in source
    assert "automatic_restart = $false" in source
    assert "network_or_provider_call_authorized = $false" in source
    assert "live_provider_processes_may_continue_independently = $false" in source
