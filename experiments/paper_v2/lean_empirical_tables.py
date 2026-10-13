"""从紧凑分析工件导出精简论文的 6 张核心数据表格。

包含完整样本量、观察通过率及 95% Wilson 置信区间。
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from experiments.paper_v2.lean_empirical_runner import PLAN_PATH, _read_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUTHORIZATION_ANALYSIS = (
    PROJECT_ROOT
    / "outputs/experiments/lean_empirical/analysis/authorization_results_v1.json"
)
DEFAULT_EXISTING_ANALYSIS = (
    PROJECT_ROOT
    / "outputs/experiments/lean_empirical/analysis/existing_results_analysis_v1.json"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs/experiments/lean_empirical/tables"


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    values = [dict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in values:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(values)
    return len(values)


def _table_1(plan_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str, str]] = Counter()
    for row in plan_rows:
        counts[
            (
                str(row["provider_id"]),
                str(row["benchmark"]),
                str(row["condition_id"]),
                str(row["authorization_regime"]),
            )
        ] += 1
    return [
        {
            "provider": key[0],
            "benchmark": key[1],
            "condition": key[2],
            "authorization_regime": key[3],
            "planned_records": value,
        }
        for key, value in sorted(counts.items())
    ]


def _included_providers(analysis: Mapping[str, Any]) -> tuple[str, ...]:
    """返回符合手稿推断表格资格的提供商列表。"""

    providers = ["deepseek"]
    if analysis.get("gemini", {}).get("cross_vendor_claim_eligible") is True:
        providers.append("gemini")
    return tuple(providers)


def _table_2(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provider in _included_providers(analysis):
        for item in analysis[provider]["condition_metrics"].values():
            attack = item["attack_unsafe_effect"]
            sensitivity = item["attack_unsafe_or_operational_failure"]
            utility = item["benign_tool_tcr"]
            rows.append(
                {
                    "provider": provider,
                    "condition": item["condition_id"],
                    "authorization_regime": item["authorization_regime"],
                    "unsafe_n": attack["successes"],
                    "attack_n": attack["total"],
                    "unsafe_rate": attack["rate"],
                    "unsafe_ci_low": attack["ci_low"],
                    "unsafe_ci_high": attack["ci_high"],
                    "unsafe_or_failure_n": sensitivity["successes"],
                    "unsafe_or_failure_rate": sensitivity["rate"],
                    "unsafe_or_failure_ci_low": sensitivity["ci_low"],
                    "unsafe_or_failure_ci_high": sensitivity["ci_high"],
                    "completed_n": utility["successes"],
                    "benign_tool_n": utility["total"],
                    "tcr": utility["rate"],
                    "tcr_ci_low": utility["ci_low"],
                    "tcr_ci_high": utility["ci_high"],
                }
            )
    return rows


def _table_3(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provider in _included_providers(analysis):
        for endpoint, comparisons in analysis[provider]["comparisons"].items():
            for name, item in comparisons.items():
                rows.append(
                    {
                        "provider": provider,
                        "endpoint": endpoint,
                        "comparison": name,
                        "paired_cases": item["paired_cases"],
                        "difference_second_minus_first": item[
                            "absolute_difference_second_minus_first"
                        ],
                        "bootstrap_ci_low": item["cluster_bootstrap"]["ci_low"],
                        "bootstrap_ci_high": item["cluster_bootstrap"]["ci_high"],
                        "discordant_first_only": item["discordant_first_only"],
                        "discordant_second_only": item["discordant_second_only"],
                        "mcnemar_p": item["exact_mcnemar_p"],
                        "holm_p": item["holm_adjusted_p_within_endpoint"],
                    }
                )
    for regime, endpoints in analysis["deepseek"]["regime_extension"].items():
        for endpoint, item in endpoints.items():
            rows.append(
                {
                    "provider": "deepseek",
                    "endpoint": endpoint,
                    "comparison": f"full_auto_to_{regime}",
                    "paired_cases": item["paired_cases"],
                    "difference_second_minus_first": item[
                        "absolute_difference_second_minus_first"
                    ],
                    "bootstrap_ci_low": item["cluster_bootstrap"]["ci_low"],
                    "bootstrap_ci_high": item["cluster_bootstrap"]["ci_high"],
                    "discordant_first_only": item["discordant_first_only"],
                    "discordant_second_only": item["discordant_second_only"],
                    "mcnemar_p": item["exact_mcnemar_p"],
                    "holm_p": "not_in_primary_family",
                }
            )
    return rows


def _table_4(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provider in _included_providers(analysis):
        for cell, item in analysis[provider]["burden"].items():
            condition, regime = cell.split("__", 1)
            rows.append(
                {
                    "provider": provider,
                    "condition": condition,
                    "authorization_regime": regime,
                    **item,
                }
            )
    return rows


def _table_5(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    """返回两个关键端点的基准分层配对估计值。"""

    rows: list[dict[str, Any]] = []
    for benchmark, endpoints in analysis["deepseek"][
        "benchmark_stratified_comparisons"
    ].items():
        for endpoint, comparisons in endpoints.items():
            for comparison, item in comparisons.items():
                rows.append(
                    {
                        "provider": "deepseek",
                        "benchmark": benchmark,
                        "endpoint": endpoint,
                        "comparison": comparison,
                        "paired_cases": item["paired_cases"],
                        "first_successes": item["first_rate"]["successes"],
                        "first_total": item["first_rate"]["total"],
                        "second_successes": item["second_rate"]["successes"],
                        "second_total": item["second_rate"]["total"],
                        "difference_second_minus_first": item[
                            "absolute_difference_second_minus_first"
                        ],
                        "bootstrap_ci_low": item["cluster_bootstrap"]["ci_low"],
                        "bootstrap_ci_high": item["cluster_bootstrap"]["ci_high"],
                        "mcnemar_p_descriptive": item["exact_mcnemar_p"],
                    }
                )
    return rows


def _supplementary_burden_stratified(
    analysis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return list(analysis["deepseek"]["burden_by_case_and_benchmark"].values())


def _table_6(existing: Mapping[str, Any]) -> list[dict[str, Any]]:
    adaptive = existing["adaptive_deepseek_v4_pro"]
    return [
        {
            "model": "deepseek-v4-pro",
            "budget": budget,
            **adaptive[f"budget_{budget}"],
            "claim_boundary": adaptive["claim_boundary"],
        }
        for budget in (50, 200)
    ]


def build_tables(
    *,
    authorization_analysis: Path = DEFAULT_AUTHORIZATION_ANALYSIS,
    existing_analysis: Path = DEFAULT_EXISTING_ANALYSIS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    authorization = json.loads(authorization_analysis.read_text(encoding="utf-8"))
    existing = json.loads(existing_analysis.read_text(encoding="utf-8"))
    plan_rows = _read_jsonl(PLAN_PATH)
    tables = {
        "table_1_design.csv": _table_1(plan_rows),
        "table_2_endpoints.csv": _table_2(authorization),
        "table_3_paired_effects.csv": _table_3(authorization),
        "table_4_runtime_burden.csv": _table_4(authorization),
        "table_5_benchmark_stratified.csv": _table_5(authorization),
        "table_6_adaptive_50_200.csv": _table_6(existing),
        "supplementary_burden_stratified.csv": _supplementary_burden_stratified(
            authorization
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {
        name: _write_csv(output_dir / name, rows) for name, rows in tables.items()
    }
    return {"output_dir": str(output_dir), "row_counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authorization-analysis", type=Path, default=DEFAULT_AUTHORIZATION_ANALYSIS
    )
    parser.add_argument("--existing-analysis", type=Path, default=DEFAULT_EXISTING_ANALYSIS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = build_tables(
        authorization_analysis=args.authorization_analysis,
        existing_analysis=args.existing_analysis,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
