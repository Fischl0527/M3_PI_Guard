from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = (
    PROJECT_ROOT
    / "outputs/verification/run_gemini_public_v5_recovery_segment_guarded_v2.ps1"
)


def _source() -> str:
    return WRAPPER.read_text(encoding="utf-8")


def test_wrapper_uses_v6_gate_and_true_v5_recovery_controller() -> None:
    source = _source()

    assert "experiment_closeout_harness_gate_v4" in source
    assert "gemini_public_controller_v5" in source
    assert "gemini_public_canary_recovery_candidate_v5.json" in source
    assert "gemini_public_canary_recovery_v5_s{0}_{1}_admission.json" in source
    assert "technical_segment_review_v6.json" in source


def test_wrapper_is_single_use_current_day_and_project_day_exclusive() -> None:
    source = _source()

    assert "already exists; retry is forbidden" in source
    assert "output root is touched; retry is forbidden" in source
    assert "Pacific Standard Time" in source
    assert "America/Los_Angeles" in source
    assert "Gemini project quota day is already reserved" in source
    assert "Another Gemini Public-v5 formal execution process is active" in source


def test_wrapper_preserves_free_zero_retry_effect_isolation() -> None:
    source = _source()

    assert "automatic_retries = 0" in source
    assert "paid_ceiling_usd = 0.0" in source
    assert "provider_tools_enabled = $false" in source
    assert "external_effects_enabled = $false" in source
    assert "scientific_outcomes_accessed_by_wrapper = $false" in source
    assert "declared_other_project_requests" in source


def test_wrapper_captures_hashes_and_always_writes_a_receipt() -> None:
    source = _source()

    assert "$Precomputed = [ordered]@{" in source
    assert "running.json" in source
    assert "receipt.json" in source
    assert "receipt_write_failure.json" in source
    assert "stdout_sha256" in source
    assert "stderr_sha256" in source
    assert "quota_ledger_sha256_before" in source
    assert "quota_ledger_sha256_after" in source
    assert "finally {" in source
    assert "secret_pattern_hit_count" in source
