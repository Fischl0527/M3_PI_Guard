from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v2.incremental_tables_v1 import build_tables


def _estimate(value: float = 0.02) -> dict:
    return {
        "estimate": value,
        "ci_low": value - 0.01,
        "ci_high": value + 0.01,
        "bootstrap_two_sided_p": 0.05,
        "holm_adjusted_p": 0.10,
        "replicates": 10_000,
    }


def _factor(paired: int = 50) -> dict:
    return {
        "paired_cases": paired,
        "factor_estimates": {
            "module": _estimate(-0.02),
            "prompt": _estimate(-0.01),
            "interaction": _estimate(0.01),
        },
    }


def _analysis(include_tcr: bool = True) -> dict:
    value = {
        "attack_unsafe_factor": _factor(50),
        "attack_failure_bound_factor": _factor(50),
    }
    if include_tcr:
        value["benign_tool_tcr_factor"] = _factor(30)
    return value


def _prop(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator,
        "ci_low": 0.0,
        "ci_high": 1.0,
    }


def test_incremental_table_builder_keeps_five_evidence_roles_separate(
    tmp_path: Path,
) -> None:
    factorial = tmp_path / "factorial.json"
    provenance = tmp_path / "provenance.json"
    challenge = tmp_path / "challenge.json"
    flash = tmp_path / "flash.json"
    adaptive = tmp_path / "adaptive.json"
    factorial.write_text(json.dumps(_analysis()), encoding="utf-8")
    challenge.write_text(json.dumps(_analysis(False)), encoding="utf-8")
    flash.write_text(json.dumps(_analysis()), encoding="utf-8")
    provenance.write_text(
        json.dumps(
            {
                "unauthorized_argument_factor": {
                    **_factor(60),
                    "factor_estimates": {
                        "source": _estimate(0.1),
                        "module": _estimate(-0.1),
                        "source_x_module": _estimate(-0.05),
                    },
                },
                "trusted_task_completion_factor": {
                    **_factor(60),
                    "factor_estimates": {
                        "source": _estimate(-0.1),
                        "module": _estimate(0.1),
                        "source_x_module": _estimate(0.05),
                    },
                },
                "source_swap_action_change": {
                    "policy": _prop(20, 60),
                    "full": _prop(10, 60),
                },
                "offline_guard_replay": {
                    "false_allow": _prop(0, 480),
                    "false_block": _prop(30, 480),
                },
            }
        ),
        encoding="utf-8",
    )
    adaptive.write_text(
        json.dumps(
            {
                "p_first_success_by_500_given_no_success_by_200": _prop(3, 12),
                "first_success_queries": [240, 300, 420],
                "attack_family": {
                    family: {
                        "success_by_500": _prop(1, 4),
                        "first_success_queries": [query],
                    }
                    for family, query in (("A1", 240), ("A2", 300), ("A3", 420))
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "tables"
    manifest = build_tables(
        factorial_path=factorial,
        provenance_path=provenance,
        challenge_path=challenge,
        flash_path=flash,
        adaptive_tail_path=adaptive,
        output_dir=output,
    )
    assert len(manifest["tables"]) == 5
    assert manifest["row_counts"] == {
        "table_1_factor_design": 4,
        "table_2_e1_factor_estimates": 9,
        "table_3_e2_provenance": 10,
        "table_4_e3_e4_robustness": 15,
        "table_5_e5_adaptive_tail": 4,
    }
    assert all(Path(path).is_file() for path in manifest["tables"].values())
    assert "E2_offline_guard_replay" in (
        output / "table_3_e2_provenance.csv"
    ).read_text(encoding="utf-8-sig")
