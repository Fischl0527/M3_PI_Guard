from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = (
    PROJECT_ROOT
    / "outputs/verification/run_adaptive_formal_pro_v2_guarded_v3.ps1"
)


def _source() -> str:
    return WRAPPER.read_text(encoding="utf-8")


def test_wrapper_binds_fresh_v7_gate_and_exact_v2_identity() -> None:
    source = _source()

    assert "experiment_closeout_harness_gate_v5" in source
    assert "adaptive_execution_order_gate_v2" in source
    assert "adaptive_formal_pro_controller_v2" in source
    assert "adaptive_formal_{0}_candidate_v2.json" in source
    assert "adaptive_formal_{0}_admission_v2.json" in source


def test_wrapper_is_single_use_and_refuses_touched_output() -> None:
    source = _source()

    assert "already exists; retry is forbidden" in source
    assert "output root is touched; retry is forbidden" in source
    assert '[ValidateSet("pro_50")]' in source
    assert "authorized_task_count -ne 32" in source


def test_wrapper_preserves_zero_retry_effect_and_result_isolation() -> None:
    source = _source()

    assert "automatic_retries = 0" in source
    assert "provider_tools_enabled = $false" in source
    assert "external_effects_enabled = $false" in source
    assert "scientific_outcomes_accessed_by_wrapper = $false" in source
    assert "result_admission_authorized -ne $false" in source


def test_wrapper_captures_all_steps_hashes_and_terminal_receipt() -> None:
    source = _source()

    for step in (
        "01_harness_gate",
        "02_order_gate",
        "03_candidate",
        "04_admission",
        "05_execute",
        "06_technical_review",
    ):
        assert step in source
    assert "running.json" in source
    assert "receipt.json" in source
    assert "receipt_write_failure.json" in source
    assert "stdout_sha256" in source
    assert "stderr_sha256" in source
    assert "secret_pattern_hit_count" in source
    assert "technical_review" in source
    assert "finally {" in source

