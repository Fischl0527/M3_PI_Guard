from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = (
    PROJECT_ROOT
    / "outputs/verification/run_deepseek_flash_public_second_recovery_v3_guarded.ps1"
)


def test_flash_recovery_wrapper_is_single_use_and_receipt_safe() -> None:
    text = WRAPPER.read_text(encoding="utf-8")

    assert "automatic retry is forbidden" in text
    assert "receipt_write_failure.json" in text
    assert "finally {" in text
    assert "source_terminal_records_retried = 0" in text
    assert "provider_tools_enabled = $false" in text
    assert "external_effects_enabled = $false" in text
    assert "scientific_outcomes_accessed_by_wrapper = $false" in text


def test_flash_recovery_wrapper_requires_current_gate_and_exact_admission() -> None:
    text = WRAPPER.read_text(encoding="utf-8")

    assert "experiment_closeout_harness_gate_v3" in text
    assert "--verify-candidate" in text
    assert "--verify-admission" in text
    assert "--execute-shard" in text
    assert "--write-technical-review" in text
    assert "--config\", \"config\\project.local.env" in text
