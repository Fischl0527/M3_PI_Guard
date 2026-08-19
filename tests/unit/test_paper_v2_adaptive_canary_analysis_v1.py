from __future__ import annotations

from pathlib import Path

import experiments.paper_v2.adaptive_canary_analysis_v1 as analysis
import experiments.paper_v2.adaptive_canary_result_admission_v1 as admission


def test_adaptive_canary_wilson_zero_of_eight() -> None:
    value = analysis._wilson(0, 8)

    assert value["value"] == 0.0
    assert value["ci_low"] == 0.0
    assert 0.32 < value["ci_high"] < 0.33


def test_adaptive_result_candidate_is_non_executable() -> None:
    value = admission.verify_candidate()

    assert (
        value["authorization"]["scientific_outcome_access_authorized"]
        is False
    )
    assert (
        value["authorization"]["new_provider_execution_authorized"]
        is False
    )
    assert value["scope"]["task_count"] == 8
    assert value["scope"]["diagnostic_query_count"] == 1
    assert value["scope"]["claim_boundary"]["full_adaptive_panel"] is False


def test_adaptive_task_csv_is_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "tasks.csv"
    analysis._write_csv(
        path,
        [
            {
                "case_id": "case-1",
                "unsafe_effect_within_50": False,
            }
        ],
    )

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
