"""Build compact main tables from the five incremental analysis artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.paper_v2.incremental_figures_v1 import ANALYSIS_ROOT, PROJECT_ROOT


OUTPUT_ROOT = PROJECT_ROOT / "docs/research/paper_v2/incremental_empirical_v1/tables"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"analysis is not an object: {path}")
    return value


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _estimate_rows(
    analysis: Mapping[str, Any],
    *,
    study: str,
    sections: Sequence[tuple[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for endpoint, section in sections:
        value = analysis.get(section)
        if not isinstance(value, Mapping):
            continue
        for factor, estimate in value["factor_estimates"].items():
            rows.append(
                {
                    "study": study,
                    "endpoint": endpoint,
                    "factor": factor,
                    "paired_cases": int(value["paired_cases"]),
                    "absolute_effect": float(estimate["estimate"]),
                    "ci_low": float(estimate["ci_low"]),
                    "ci_high": float(estimate["ci_high"]),
                    "bootstrap_p": float(estimate["bootstrap_two_sided_p"]),
                    "holm_adjusted_p": (
                        ""
                        if estimate.get("holm_adjusted_p") is None
                        else float(estimate["holm_adjusted_p"])
                    ),
                    "bootstrap_replicates": int(estimate["replicates"]),
                }
            )
    return rows


def _factor_design_rows() -> list[dict[str, Any]]:
    return [
        {
            "condition_cell": cell,
            "prompt_factor": prompt,
            "module_factor": module,
            "authorization_regime": "auto_compiled",
            "historical_rows_reused": False,
        }
        for cell, prompt, module in (
            ("policy_normal", "normal", "policy"),
            ("policy_safe", "safe", "policy"),
            ("full_normal", "normal", "full"),
            ("full_safe", "safe", "full"),
        )
    ]


def _provenance_rows(provenance: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _estimate_rows(
        provenance,
        study="E2_end_to_end",
        sections=(
            ("unauthorized_argument_influence", "unauthorized_argument_factor"),
            ("authorized_action_execution", "trusted_task_completion_factor"),
        ),
    )
    for module, value in provenance["source_swap_action_change"].items():
        rows.append(
            {
                "study": "E2_end_to_end",
                "endpoint": "source_swap_action_change",
                "factor": module,
                "paired_cases": int(value["denominator"]),
                "absolute_effect": float(value["value"]),
                "ci_low": float(value["ci_low"]),
                "ci_high": float(value["ci_high"]),
                "bootstrap_p": "",
                "holm_adjusted_p": "",
                "bootstrap_replicates": "",
            }
        )
    offline = provenance["offline_guard_replay"]
    for endpoint in ("false_allow", "false_block"):
        value = offline[endpoint]
        rows.append(
            {
                "study": "E2_offline_guard_replay",
                "endpoint": endpoint,
                "factor": "not_applicable",
                "paired_cases": int(value["denominator"]),
                "absolute_effect": float(value["value"]),
                "ci_low": float(value["ci_low"]),
                "ci_high": float(value["ci_high"]),
                "bootstrap_p": "",
                "holm_adjusted_p": "",
                "bootstrap_replicates": "",
            }
        )
    return rows


def _adaptive_rows(adaptive: Mapping[str, Any]) -> list[dict[str, Any]]:
    overall = adaptive["p_first_success_by_500_given_no_success_by_200"]
    rows = [
        {
            "stratum": "all_selected_survivors",
            "tasks": int(overall["denominator"]),
            "successes_by_500": int(overall["numerator"]),
            "conditional_probability": float(overall["value"]),
            "ci_low": float(overall["ci_low"]),
            "ci_high": float(overall["ci_high"]),
            "first_success_queries": ";".join(
                str(value) for value in adaptive["first_success_queries"]
            ),
            "complete_original_b500_panel": False,
        }
    ]
    for family, item in adaptive["attack_family"].items():
        value = item["success_by_500"]
        rows.append(
            {
                "stratum": family,
                "tasks": int(value["denominator"]),
                "successes_by_500": int(value["numerator"]),
                "conditional_probability": float(value["value"]),
                "ci_low": float(value["ci_low"]),
                "ci_high": float(value["ci_high"]),
                "first_success_queries": ";".join(
                    str(query) for query in item["first_success_queries"]
                ),
                "complete_original_b500_panel": False,
            }
        )
    return rows


def build_tables(
    *,
    factorial_path: Path = ANALYSIS_ROOT / "factorial/analysis_v1.json",
    provenance_path: Path = ANALYSIS_ROOT / "provenance/analysis_v1.json",
    challenge_path: Path = ANALYSIS_ROOT / "challenge/analysis_v1.json",
    flash_path: Path = ANALYSIS_ROOT / "flash/analysis_v1.json",
    adaptive_tail_path: Path = ANALYSIS_ROOT / "adaptive-tail/analysis_v1.json",
    output_dir: Path = OUTPUT_ROOT,
) -> dict[str, Any]:
    factorial = _load(factorial_path)
    provenance = _load(provenance_path)
    challenge = _load(challenge_path)
    flash = _load(flash_path)
    adaptive = _load(adaptive_tail_path)
    tables: dict[str, list[dict[str, Any]]] = {
        "table_1_factor_design": _factor_design_rows(),
        "table_2_e1_factor_estimates": _estimate_rows(
            factorial,
            study="E1_representative_pro",
            sections=(
                ("attack_unsafe_effect", "attack_unsafe_factor"),
                ("attack_unsafe_or_failure", "attack_failure_bound_factor"),
                ("benign_tool_tcr", "benign_tool_tcr_factor"),
            ),
        ),
        "table_3_e2_provenance": _provenance_rows(provenance),
        "table_4_e3_e4_robustness": [
            *_estimate_rows(
                challenge,
                study="E3_risk_enriched_pro",
                sections=(
                    ("attack_unsafe_effect", "attack_unsafe_factor"),
                    ("attack_unsafe_or_failure", "attack_failure_bound_factor"),
                ),
            ),
            *_estimate_rows(
                flash,
                study="E4_flash_replication",
                sections=(
                    ("attack_unsafe_effect", "attack_unsafe_factor"),
                    ("attack_unsafe_or_failure", "attack_failure_bound_factor"),
                    ("benign_tool_tcr", "benign_tool_tcr_factor"),
                ),
            ),
        ],
        "table_5_e5_adaptive_tail": _adaptive_rows(adaptive),
    }
    paths: dict[str, str] = {}
    for name, rows in tables.items():
        path = output_dir / f"{name}.csv"
        _write_csv(path, rows)
        paths[name] = str(path)
    manifest = {
        "schema_version": "m3-paper-v2-incremental-table-manifest-1.0",
        "tables": paths,
        "row_counts": {name: len(rows) for name, rows in tables.items()},
        "boundaries": {
            "offline_guard_replay_separate": True,
            "risk_enriched_not_prevalence": True,
            "adaptive_tail_not_complete_b500": True,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "table_manifest_v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args(argv)
    result = build_tables(output_dir=args.output_dir)
    print(json.dumps({"tables": len(result["tables"]), "output": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
