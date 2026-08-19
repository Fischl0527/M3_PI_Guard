from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HELPER = PROJECT_ROOT / "harness/scripts/verify_with_receipt_v3.ps1"
LAUNCHER = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v6.ps1"
)


def test_v3_helper_uses_process_scoped_git_compatibility_before_child() -> None:
    source = HELPER.read_text(encoding="utf-8")
    start_index = source.index("$Child = Start-Process")

    assert source.index('$env:GIT_CONFIG_COUNT = "1"') < start_index
    assert source.index('$env:GIT_CONFIG_KEY_0 = "safe.directory"') < start_index
    assert source.index("$env:GIT_CONFIG_VALUE_0 = $ProcessSafeDirectory") < start_index
    assert source.index("git -C $AgentDojoCheckout rev-parse HEAD") < start_index
    assert "git config --global" not in source
    assert "global_git_config_mutated = $false" in source
    assert "repository_git_config_mutated = $false" in source
    assert "process_scoped_git_qualification_passed" in source


def test_v3_helper_scrubs_provider_authorization_and_persists_terminal_receipt() -> None:
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
    assert "$Child.WaitForExit()" in source
    assert "operating_system_exit_code_directly_observed = $true" in source
    assert "Write-JsonAtomic -Path $ReceiptPath" in source
    assert "network_or_provider_call_authorized = $false" in source


def test_v6_launcher_is_single_use_detached_and_non_authorizing() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "experiment_closeout_fresh_harness_v6_20260805" in source
    assert "verify_with_receipt_v3.ps1" in source
    assert "run directory already exists" in source
    assert "-WindowStyle Hidden -PassThru" in source
    assert 'git_safe_directory_scope = "process_only_in_helper_and_verification_child"' in source
    assert "global_git_config_mutated = $false" in source
    assert "automatic_restart = $false" in source
    assert "network_or_provider_call_authorized = $false" in source
    assert "live_provider_processes_may_continue_independently = $false" in source
