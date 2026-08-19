from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = (
    PROJECT_ROOT / "outputs/verification/run_gemini_public_v5_segment_guarded.ps1"
)


def _source() -> str:
    return WRAPPER.read_text(encoding="utf-8")


def test_wrapper_requires_current_gate_and_failure_aware_review() -> None:
    source = _source()

    assert "experiment_closeout_harness_gate_v3" in source
    assert "gemini_public_technical_review_v5" in source
    assert "gemini_public_v5_segment_technical_gate_pass" in source
    assert "matrix_continuation_eligible" in source


def test_wrapper_is_single_use_zero_retry_and_effect_isolated() -> None:
    source = _source()

    assert "already exists; retry is forbidden" in source
    assert "output root is touched; retry is forbidden" in source
    assert "automatic_retries = 0" in source
    assert "paid_ceiling_usd = 0.0" in source
    assert "provider_tools_enabled = $false" in source
    assert "external_effects_enabled = $false" in source
    assert "scientific_outcomes_accessed_by_wrapper = $false" in source


def test_wrapper_precomputes_locks_and_has_receipt_failure_fallback() -> None:
    source = _source()

    assert "$Precomputed = [ordered]@{" in source
    assert "running.json" in source
    assert "receipt.json" in source
    assert "receipt_write_failure.json" in source
    assert "finally {" in source
    assert "final_exit_code = $FinalExit" in source
