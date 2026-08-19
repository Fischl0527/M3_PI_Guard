from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = (
    PROJECT_ROOT
    / "outputs/verification/run_adaptive_formal_pro_v2_guarded_v4.ps1"
)


def _source() -> str:
    return WRAPPER.read_text(encoding="utf-8")


def test_wrapper_binds_v8_prefix_gate_and_exact_pro_200_identity() -> None:
    source = _source()

    assert '[ValidateSet("pro_200")]' in source
    assert "experiment_closeout_harness_gate_v6" in source
    assert "adaptive_execution_order_gate_v2" in source
    assert "adaptive_formal_pro_controller_v2" in source
    assert "adaptive_formal_{0}_candidate_v2.json" in source
    assert "adaptive_formal_{0}_admission_v2.json" in source
    assert "target_budget -ne 200" in source
    assert "authorized_task_count -ne 39" in source
    assert "source_checkpoint_count -ne 39" in source


def test_wrapper_is_single_use_and_preserves_diagnostic_boundary() -> None:
    source = _source()

    assert "already exists; retry is forbidden" in source
    assert "output root is touched; retry is forbidden" in source
    assert "expected exactly one retained prior diagnostic" in source
    assert "source checkpoint budget drift" in source
    assert "query_count -ne 50" in source
    assert "terminal_query_replay_authorized -ne $false" in source


def test_wrapper_preserves_budget_retry_effect_and_result_isolation() -> None:
    source = _source()

    assert "stage_hard_limit_cny" in source
    assert "total_adaptive_ceiling_cny" in source
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
