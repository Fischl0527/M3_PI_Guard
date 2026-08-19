from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HELPER = PROJECT_ROOT / "harness/scripts/verify_with_receipt_v2.ps1"
LAUNCHER = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v5.ps1"
)


def test_v2_helper_scrubs_provider_authorization_before_child_start() -> None:
    source = HELPER.read_text(encoding="utf-8")
    start_index = source.index("$Child = Start-Process")
    for name in (
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "M3_CANARY_SECRET_API_KEY",
        "M3_FRONTIER_API_CONSENT",
        "OPENAI_API_KEY",
        "OPENAI_COMPATIBLE_API_KEY",
    ):
        assert source.index(f'"{name}"') < start_index
    assert 'Remove-Item -LiteralPath "Env:$VariableName"' in source
    assert "network_or_provider_call_authorized = $false" in source


def test_v2_helper_persists_direct_terminal_evidence_and_fails_closed() -> None:
    source = HELPER.read_text(encoding="utf-8")
    required = (
        "$Child.WaitForExit()",
        "operating_system_exit_code_directly_observed = $true",
        "child_exit_code = $ChildExitCode",
        "verify_script_sha256_before = $VerifyShaBefore",
        "verify_script_sha256_after = $VerifyShaAfter",
        "stdout_sha256",
        "stderr_sha256",
        "exactly_one_aggregate_marker",
        "aggregate_marker_is_terminal",
        "no_failed_harness_stage",
        '$Status = "completed_source_drift"',
        '$Status = "completed_invalid_terminal_evidence"',
    )
    for token in required:
        assert token in source
    assert "Write-JsonAtomic -Path $ReceiptPath" in source


def test_v5_launcher_is_single_use_detached_and_non_authorizing() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    assert "experiment_closeout_fresh_harness_v5_20260804" in source
    assert "verify_with_receipt_v2.ps1" in source
    assert "run directory already exists" in source
    assert "-WindowStyle Hidden -PassThru" in source
    assert "automatic_restart = $false" in source
    assert "network_or_provider_call_authorized = $false" in source
    assert "live_provider_processes_may_continue_independently = $false" in source
