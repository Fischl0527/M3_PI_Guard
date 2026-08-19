"""Audit the historical AgentDojo metric inversion without model execution."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .agentdojo_official_metrics_v2 import MetricSemanticsError, normalize_outcome_v2, read_jsonl
from .common import portable_path, rows_sha256, sha256_file, write_jsonl


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = (
    ROOT / "outputs" / "paper_upgrade_v1" / "analysis_v2" / "agentdojo_metric_semantics"
)
AUDIT_VERSION = "m3-paper-v1-agentdojo-metric-semantics-audit-1.0"
SOURCES = {
    "toolfilter_formal": ROOT
    / "outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1/outcomes.jsonl",
    "taskshield_v15": ROOT
    / "outputs/paper_upgrade_v1/baselines/taskshield_paper_qualification_v15_expanded/outcomes.jsonl",
}
PROTECTED_PATHS = [
    ROOT / "protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v13.json",
    ROOT / "protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v14.json",
    ROOT / "protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v15.json",
    SOURCES["toolfilter_formal"],
    SOURCES["taskshield_v15"],
    ROOT / "protocols/paper_upgrade_v1/baseline_registry.json",
    ROOT / "protocols/paper_upgrade_v1/q2_readiness_audit_v1.json",
]


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _hashes(paths: list[Path]) -> dict[str, str]:
    return {
        portable_path(path, root=ROOT): sha256_file(path)
        for path in paths
        if path.is_file()
    }


def _git_head(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _summarize(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    attacks = [row for row in rows if row.get("sample_type") == "attack"]
    utility = [row for row in rows if row.get("sample_type") == "utility"]
    return {
        "rows": len(rows),
        "utility_rows": len(utility),
        "attack_rows": len(attacks),
        "completed_rows": sum(row.get("status") == "completed" for row in rows),
        "operational_failures": sum(bool(row.get("operational_failure")) for row in rows),
        "raw_official_attack_successes": sum(
            row.get("official_injection_success") is True for row in attacks
        ),
        "corrected_attack_successes": sum(row.get("attack_success") is True for row in attacks),
        "legacy_attack_successes": sum(
            row.get("legacy_attack_success") is True for row in attacks
        ),
        "legacy_complement_rows": sum(
            row.get("legacy_is_complement_of_official") is True for row in attacks
        ),
        "metric_mapping_disagreements": sum(
            row.get("metric_mapping_agreement") is not True for row in attacks
        ),
        "attack_rows_with_raw_trace": sum(
            isinstance(row.get("metric_source"), Mapping) for row in attacks
        ),
        "utility_rows_with_attack_metric": sum(
            any(
                row.get(key) is not None
                for key in (
                    "official_injection_success",
                    "attack_success",
                    "security_preserved",
                )
            )
            for row in utility
        ),
    }


def build_impact_inventory() -> list[dict[str, Any]]:
    specifications = [
        (
            "experiments/paper_v1/benchmarks/run_agentdojo_official_detector_formal.py",
            "direct_complement_and_shared_execute_case",
            "Task Shield and CaMeL import the affected _execute_case; detector analyses consume attack_success",
        ),
        (
            "experiments/paper_v1/benchmarks/run_taskshield_paper_formal.py",
            "shared_execute_case_consumer",
            "v1.3-v1.5 are immutable; v1.6 must use a new corrected execution wrapper",
        ),
        (
            "experiments/paper_v1/benchmarks/run_camel_source_backed_formal.py",
            "shared_execute_case_consumer",
            "future CaMeL formal outcomes require v2 semantics",
        ),
        (
            "experiments/paper_v1/benchmarks/run_ipiguard_source_backed_formal.py",
            "direct_complement",
            "future IPIGuard formal outcomes require v2 semantics",
        ),
        (
            "experiments/paper_v1/benchmarks/run_progent_source_backed_formal.py",
            "direct_and_execution_grounded_complement",
            "official and execution-grounded fields both require explicit injection-success names",
        ),
        (
            "experiments/paper_v1/benchmarks/analyze_agentdojo_official_detector_formal.py",
            "legacy_attack_success_consumer",
            "old analyses are provisional; analysis-v2 must consume corrected rows",
        ),
        (
            "experiments/paper_v1/benchmarks/analyze_progent_source_backed_formal.py",
            "legacy_security_false_as_attack",
            "future Progent analyzer requires v2 semantics before admission",
        ),
        (
            "experiments/paper_v1/benchmarks/formal_case_result_rows.py",
            "field_precedence_risk",
            "legacy attack_success currently precedes official_injection_success",
        ),
        (
            "protocols/paper_upgrade_v1/baseline_registry.json",
            "derived_effect_status",
            "ToolFilter raw run remains complete but effect interpretation is provisional",
        ),
    ]
    rows: list[dict[str, Any]] = []
    for relative, impact_type, action in specifications:
        path = ROOT / relative
        rows.append(
            {
                "path": relative,
                "exists": path.is_file(),
                "sha256": sha256_file(path) if path.is_file() else "",
                "impact_type": impact_type,
                "required_action": action,
                "modified_by_audit": False,
            }
        )
    return rows


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else ["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in fields} for row in rows)


def run_audit(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    sources: Mapping[str, Path] = SOURCES,
) -> dict[str, Any]:
    protected_before = _hashes(PROTECTED_PATHS)
    corrected_by_source: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    difference_rows: list[dict[str, Any]] = []
    for label, outcomes_path in sources.items():
        corrected: list[dict[str, Any]] = []
        for source_row in read_jsonl(outcomes_path):
            try:
                row = normalize_outcome_v2(
                    source_row,
                    source_label=label,
                    source_outcomes_path=outcomes_path,
                    root=ROOT,
                )
            except MetricSemanticsError as exc:
                errors.append(
                    {
                        "source_label": label,
                        "benchmark_case_id": str(source_row.get("benchmark_case_id", "")),
                        "error": str(exc),
                    }
                )
                continue
            corrected.append(row)
            if row["sample_type"] == "attack":
                difference_rows.append(
                    {
                        "source_label": label,
                        "benchmark_case_id": row["benchmark_case_id"],
                        "suite": row["suite"],
                        "legacy_attack_success": row["legacy_attack_success"],
                        "official_injection_success": row["official_injection_success"],
                        "corrected_attack_success": row["attack_success"],
                        "legacy_is_complement_of_official": row[
                            "legacy_is_complement_of_official"
                        ],
                        "metric_source_path": row["metric_source"]["path"],
                        "metric_source_sha256": row["metric_source"]["sha256"],
                    }
                )
        corrected_by_source[label] = corrected

    corrected_root = output_dir / "corrected_rows"
    for label, rows in corrected_by_source.items():
        write_jsonl(corrected_root / f"{label}.jsonl", rows)
    impact = build_impact_inventory()
    _write_csv(output_dir / "impact_inventory.csv", impact)
    _write_csv(output_dir / "row_differences.csv", difference_rows)

    summaries = {label: _summarize(rows) for label, rows in corrected_by_source.items()}
    upstream_checkout = ROOT / "external/benchmarks/agentdojo"
    base_tasks = upstream_checkout / "src/agentdojo/base_tasks.py"
    notebook = upstream_checkout / "notebooks/analysis.ipynb"
    base_text = base_tasks.read_text(encoding="utf-8")
    notebook_text = notebook.read_text(encoding="utf-8")
    protected_after = _hashes(PROTECTED_PATHS)
    checks = {
        "pinned_agentdojo_head": _git_head(upstream_checkout)
        == "089ed468cf3ed0322acc66b0211f26d9d90dbf60",
        "base_task_contract_says_true_when_injection_executed": (
            "Returns True if the injection was executed correctly" in base_text
        ),
        "official_notebook_maps_security_to_asr": (
            'injection_means[\\"ASR\\"] = utility_with_means[\\"security\\"]'
            in notebook_text
        ),
        "normalization_errors_zero": not errors,
        "toolfilter_exact_rows": summaries.get("toolfilter_formal", {}).get("rows") == 726,
        "toolfilter_attack_denominator_629": summaries.get("toolfilter_formal", {}).get(
            "attack_rows"
        )
        == 629,
        "toolfilter_corrected_attack_success_7": summaries.get(
            "toolfilter_formal", {}
        ).get("corrected_attack_successes")
        == 7,
        "taskshield_v15_exact_rows": summaries.get("taskshield_v15", {}).get("rows")
        == 12,
        "taskshield_v15_attack_denominator_6": summaries.get("taskshield_v15", {}).get(
            "attack_rows"
        )
        == 6,
        "taskshield_v15_corrected_attack_success_0": summaries.get(
            "taskshield_v15", {}
        ).get("corrected_attack_successes")
        == 0,
        "utility_rows_with_attack_metric_zero": all(
            summary["utility_rows_with_attack_metric"] == 0
            for summary in summaries.values()
        ),
        "attack_rows_all_have_raw_trace": all(
            summary["attack_rows_with_raw_trace"] == summary["attack_rows"]
            for summary in summaries.values()
        ),
        "metric_mapping_disagreements_zero": all(
            summary["metric_mapping_disagreements"] == 0
            for summary in summaries.values()
        ),
        "protected_hashes_unchanged": protected_before == protected_after,
        "impact_inventory_paths_exist": all(row["exists"] for row in impact),
    }
    passed = all(checks.values())
    audit = {
        "schema_version": "paper-agentdojo-metric-semantics-audit-1.0",
        "audit_version": AUDIT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_pass" if passed else "completed_fail",
        "evidence_class": "post_hoc_non_mutating_metric_correction",
        "result_eligible_for_formal_tables": False,
        "model_calls": 0,
        "api_calls": 0,
        "q2_score_change": 0,
        "source_summaries": summaries,
        "normalization_errors": errors,
        "checks": checks,
        "passed_checks": sum(checks.values()),
        "total_checks": len(checks),
        "upstream_evidence": {
            "agentdojo_git_head": _git_head(upstream_checkout),
            "base_tasks_path": portable_path(base_tasks, root=ROOT),
            "base_tasks_sha256": sha256_file(base_tasks),
            "analysis_notebook_path": portable_path(notebook, root=ROOT),
            "analysis_notebook_sha256": sha256_file(notebook),
        },
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "impact_inventory_path": portable_path(
            output_dir / "impact_inventory.csv", root=ROOT
        ),
        "row_differences_path": portable_path(
            output_dir / "row_differences.csv", root=ROOT
        ),
        "corrected_rows": {
            label: {
                "path": portable_path(corrected_root / f"{label}.jsonl", root=ROOT),
                "sha256": sha256_file(corrected_root / f"{label}.jsonl"),
                "rows_sha256": rows_sha256(rows),
            }
            for label, rows in corrected_by_source.items()
        },
        "boundary": (
            "This audit does not overwrite historical outcomes, traces, analyses, freezes, "
            "registries, or Q2 readiness. G0 is finalized by the separate v2 reanalysis."
        ),
    }
    _write_json(output_dir / "metric_semantics_audit.json", audit)
    lines = [
        "# AgentDojo metric semantics v2 audit",
        "",
        f"- Status: `{audit['status']}`",
        f"- Checks: `{audit['passed_checks']}/{audit['total_checks']}`",
        "- Model/API calls: `0/0`",
        "- Formal eligibility: `false`",
        "",
        "## Corrected source summaries",
        "",
        "| Source | Rows | Utility | Attack | Legacy attack | Corrected official attack |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, summary in summaries.items():
        lines.append(
            f"| `{label}` | {summary['rows']} | {summary['utility_rows']} | "
            f"{summary['attack_rows']} | {summary['legacy_attack_successes']} | "
            f"{summary['corrected_attack_successes']} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            audit["boundary"],
            "",
            "The impact inventory lists every currently known shared/direct complement path. "
            "No historical artifact was rewritten.",
        ]
    )
    (output_dir / "metric_semantics_audit.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_audit(output_dir=args.output_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "completed_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

