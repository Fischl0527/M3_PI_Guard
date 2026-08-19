from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HARNESS_LAUNCHER = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v12.ps1"
)


def test_fresh_harness_v12_uses_single_run_scoped_pytest_temp() -> None:
    source = HARNESS_LAUNCHER.read_text(encoding="utf-8")

    assert "experiment_closeout_fresh_harness_v12_20260819" in source
    assert 'Join-Path $RunDirectory "pytest-temp"' in source
    assert "$env:TEMP = $PytestTempRoot" in source
    assert "$env:TMP = $PytestTempRoot" in source
    assert source.index("$env:TEMP = $PytestTempRoot") < source.index(
        "$Child = Start-Process"
    )
    assert source.index("$env:TMP = $PytestTempRoot") < source.index(
        "$Child = Start-Process"
    )
    assert "pytest_temp_scope = \"single_harness_run\"" in source


def test_fresh_harness_v12_remains_single_use_and_non_network() -> None:
    source = HARNESS_LAUNCHER.read_text(encoding="utf-8")

    assert "run directory already exists; launcher is single-use" in source
    assert "verify_with_receipt_v3.ps1" in source
    assert "-WindowStyle Hidden" in source
    assert "-PassThru" in source
    assert "automatic_restart = $false" in source
    assert "network_or_provider_call_authorized = $false" in source
    assert "live_provider_processes_may_continue_independently = $false" in source
