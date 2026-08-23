from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v2.lean_empirical_figures import build_figures


def _comparison(diff: float) -> dict:
    return {
        "absolute_difference_second_minus_first": diff,
        "cluster_bootstrap": {"ci_low": diff - 0.03, "ci_high": diff + 0.03},
    }


def _authorization_fixture() -> dict:
    metrics = {}
    burden = {}
    burden_stratified = {}
    for index, (condition, regime) in enumerate(
        (
            ("m3_policy_only", "auto_compiled"),
            ("m3_policy_only", "exact_gold"),
            ("m3_full", "auto_compiled"),
            ("m3_full", "exact_gold"),
            ("m3_full", "broad"),
            ("m3_full", "underspecified"),
            ("m3_full", "conflicting"),
        )
    ):
        key = f"{condition}__{regime}"
        metrics[key] = {
            "condition_id": condition,
            "authorization_regime": regime,
            "records": 180 if index < 4 else 60,
            "attack_unsafe_effect": {
                "successes": 5 + index,
                "total": 100,
                "rate": 0.05 + index * 0.01,
            },
            "attack_unsafe_or_operational_failure": {
                "successes": 8 + index,
                "total": 100,
                "rate": 0.08 + index * 0.01,
            },
            "benign_tool_tcr": {
                "successes": 45 + index,
                "total": 60,
                "rate": 0.75 + index * 0.01,
            },
            "benign_no_tool_tcr": {"successes": 18, "total": 20, "rate": 0.9},
        }
        burden[key] = {
            "records": metrics[key]["records"],
            "ask_count": 3 + index,
            "deny_count": 4 + index,
            "ask_record_count": 3 + index,
            "deny_record_count": 4 + index,
            "ask_record_rate": (3 + index) / metrics[key]["records"],
            "deny_record_rate": (4 + index) / metrics[key]["records"],
            "failure_count": index,
            "failure_rate": index / metrics[key]["records"],
            "latency_p50_ms": 1000 + index * 10,
            "latency_p95_ms": 2000 + index * 100,
            "tokens": 1000,
            "cost_amount": 0.1,
            "cost_currency": "CNY",
        }
        if index < 4:
            for case_type in ("attack", "benign_tool"):
                for benchmark in ("agentdojo-v1", "m3-v2"):
                    stratum_key = f"{key}__{case_type}__{benchmark}"
                    burden_stratified[stratum_key] = {
                        "condition_id": condition,
                        "authorization_regime": regime,
                        "case_type": case_type,
                        "benchmark": benchmark,
                        **burden[key],
                    }
    comparison_names = (
        "policy_auto_to_exact",
        "full_auto_to_exact",
        "auto_policy_to_full",
        "exact_policy_to_full",
    )
    comparisons = {
        endpoint: {
            name: _comparison((index + 1) * 0.01)
            for index, name in enumerate(comparison_names)
        }
        for endpoint in ("unsafe_effect", "task_completion")
    }
    extension = {
        regime: {
            "unsafe_effect": _comparison(0.01),
            "benign_tool_tcr": _comparison(-0.01),
        }
        for regime in ("broad", "underspecified", "conflicting")
    }
    metrics["m3_full__underspecified"]["attack_unsafe_effect"] = dict(
        metrics["m3_full__broad"]["attack_unsafe_effect"]
    )
    metrics["m3_full__underspecified"]["benign_tool_tcr"] = dict(
        metrics["m3_full__broad"]["benign_tool_tcr"]
    )
    return {
        "deepseek": {
            "condition_metrics": metrics,
            "comparisons": comparisons,
            "regime_extension": extension,
            "burden": burden,
            "burden_by_case_and_benchmark": burden_stratified,
        }
    }


def _existing_fixture() -> dict:
    return {
        "adaptive_deepseek_v4_pro": {
            "budget_50": {"successes": 4, "total": 40, "rate": 0.1, "ci_high": 0.23},
            "budget_200": {"successes": 18, "total": 40, "rate": 0.45, "ci_high": 0.61},
            "first_success_queries": {
                f"case-{index:02d}": value
                for index, value in enumerate(
                    (
                        24,
                        26,
                        32,
                        47,
                        52,
                        57,
                        64,
                        67,
                        80,
                        83,
                        97,
                        105,
                        107,
                        124,
                        125,
                        144,
                        144,
                        184,
                    ),
                    start=1,
                )
            },
        }
    }


def test_builds_five_png_svg_and_pdf_figures(tmp_path: Path) -> None:
    authorization = tmp_path / "authorization.json"
    existing = tmp_path / "existing.json"
    authorization.write_text(json.dumps(_authorization_fixture()), encoding="utf-8")
    existing.write_text(json.dumps(_existing_fixture()), encoding="utf-8")
    output_dir = tmp_path / "figures"

    result = build_figures(
        authorization_analysis=authorization,
        existing_analysis=existing,
        output_dir=output_dir,
    )

    assert len(result["chart_contracts"]) == 5
    assert result["renderer"] == "matplotlib-static-png-svg-pdf"
    assert "derived authorization" in result["chart_contracts"][0]["takeaway"]
    assert len(result["outputs"]) == 5
    paths = [Path(path) for values in result["outputs"].values() for path in values]
    assert len(paths) == 15
    assert all(path.exists() and path.stat().st_size > 1_000 for path in paths)
    assert {path.suffix for path in paths} == {".png", ".svg", ".pdf"}
    assert all(
        path.read_bytes().startswith(b"%PDF") for path in paths if path.suffix == ".pdf"
    )
    pareto_svg = (output_dir / "figure_2_safety_utility_pareto.svg").read_text(
        encoding="utf-8"
    )
    assert "<!-- 5/6 -->" in pareto_svg

    second_dir = tmp_path / "figures-second"
    build_figures(
        authorization_analysis=authorization,
        existing_analysis=existing,
        output_dir=second_dir,
    )
    for path in paths:
        if path.suffix == ".svg":
            second = second_dir / path.name
            svg = path.read_text(encoding="utf-8")
            assert "<dc:date>" not in svg
            assert all(line == line.rstrip() for line in svg.splitlines())
            assert path.read_bytes() == second.read_bytes()
