"""Build non-mutating AgentDojo analysis-v2 and finalize Task Shield v1.6 G0."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .agentdojo_official_metrics_v2 import read_json, read_jsonl, validate_v2_row
from .common import portable_path, resolve_artifact_path, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = (
    ROOT / "outputs" / "paper_upgrade_v1" / "analysis_v2" / "agentdojo_metric_semantics"
)
DEFAULT_GATE_DIR = (
    ROOT
    / "protocols/paper_upgrade_v1/execution/taskshield_v16_p0_metric_semantics_v1"
)
ANALYZER_VERSION = "m3-paper-v1-agentdojo-metric-reanalysis-v2-1.0"


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = list(rows)
    fields = [
        "source_label",
        "suite",
        "scope",
        "metric",
        "successes",
        "total",
        "rate",
        "wilson95_low",
        "wilson95_high",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in fields} for row in materialized)


def wilson_interval(
    successes: int,
    total: int,
    z: float = 1.959963984540054,
) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total)
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _metric(
    *,
    source_label: str,
    suite: str,
    scope: str,
    metric: str,
    successes: int,
    total: int,
) -> dict[str, Any]:
    low, high = wilson_interval(successes, total)
    return {
        "source_label": source_label,
        "suite": suite,
        "scope": scope,
        "metric": metric,
        "successes": successes,
        "total": total,
        "rate": successes / total if total else None,
        "wilson95_low": low,
        "wilson95_high": high,
    }


def build_metrics(rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not rows:
        raise ValueError("corrected rows are empty")
    issues = [
        {"benchmark_case_id": row.get("benchmark_case_id"), "issues": validate_v2_row(row)}
        for row in rows
        if validate_v2_row(row)
    ]
    if issues:
        raise ValueError("invalid corrected rows: " + json.dumps(issues[:3], ensure_ascii=False))
    source_label = str(rows[0]["source_label"])
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("source_label") != source_label:
            raise ValueError("one corrected file must contain exactly one source_label")
        groups[str(row.get("suite") or "unknown")].append(row)
    metric_rows: list[dict[str, Any]] = []
    for suite, group in {"overall": rows, **dict(sorted(groups.items()))}.items():
        utility = [row for row in group if row.get("sample_type") == "utility"]
        attack = [row for row in group if row.get("sample_type") == "attack"]
        metric_rows.extend(
            [
                _metric(
                    source_label=source_label,
                    suite=suite,
                    scope="utility",
                    metric="TCR",
                    successes=sum(row.get("utility_success") is True for row in utility),
                    total=len(utility),
                ),
                _metric(
                    source_label=source_label,
                    suite=suite,
                    scope="attack",
                    metric="Targeted_ASR",
                    successes=sum(row.get("attack_success") is True for row in attack),
                    total=len(attack),
                ),
                _metric(
                    source_label=source_label,
                    suite=suite,
                    scope="attack",
                    metric="attack_condition_utility",
                    successes=sum(row.get("utility_success") is True for row in attack),
                    total=len(attack),
                ),
                _metric(
                    source_label=source_label,
                    suite=suite,
                    scope="engineering",
                    metric="operational_failure_rate",
                    successes=sum(bool(row.get("operational_failure")) for row in group),
                    total=len(group),
                ),
            ]
        )
    attacks = [row for row in rows if row.get("sample_type") == "attack"]
    utility = [row for row in rows if row.get("sample_type") == "utility"]
    summary = {
        "source_label": source_label,
        "rows": len(rows),
        "utility_rows": len(utility),
        "attack_rows": len(attacks),
        "utility_successes": sum(row.get("utility_success") is True for row in utility),
        "attack_successes": sum(row.get("attack_success") is True for row in attacks),
        "attack_condition_utility_successes": sum(
            row.get("utility_success") is True for row in attacks
        ),
        "legacy_attack_successes": sum(
            row.get("legacy_attack_success") is True for row in attacks
        ),
        "operational_failures": sum(bool(row.get("operational_failure")) for row in rows),
        "rows_sha256": rows_sha256([dict(row) for row in rows]),
    }
    return metric_rows, summary


def _overall(metrics: list[Mapping[str, Any]], name: str) -> Mapping[str, Any]:
    return next(row for row in metrics if row["suite"] == "overall" and row["metric"] == name)


def _format_metric(row: Mapping[str, Any]) -> str:
    if not row["total"]:
        return "0/0 (not estimated)"
    return (
        f"{row['successes']}/{row['total']} = {float(row['rate']) * 100:.2f}% "
        f"(Wilson 95% CI {float(row['wilson95_low']) * 100:.2f}%–"
        f"{float(row['wilson95_high']) * 100:.2f}%)"
    )


def _build_figures(
    analyses: Mapping[str, Mapping[str, Any]],
    output_dir: Path,
) -> dict[str, list[str]]:
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    labels = list(analyses)
    legacy = [analyses[label]["summary"]["legacy_attack_successes"] for label in labels]
    corrected = [analyses[label]["summary"]["attack_successes"] for label in labels]
    totals = [analyses[label]["summary"]["attack_rows"] for label in labels]
    legacy_rates = [100 * value / total if total else 0 for value, total in zip(legacy, totals)]
    corrected_rates = [
        100 * value / total if total else 0 for value, total in zip(corrected, totals)
    ]
    x = list(range(len(labels)))
    width = 0.36
    fig, ax = plt.subplots(figsize=(7.6, 4.5))
    ax.bar([value - width / 2 for value in x], legacy_rates, width, label="legacy complement")
    ax.bar([value + width / 2 for value in x], corrected_rates, width, label="raw official")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Targeted ASR (%)")
    ax.set_ylim(0, 105)
    ax.set_title("AgentDojo metric-semantics correction")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    paths: list[str] = []
    for suffix in ("png", "svg"):
        path = output_dir / f"legacy_vs_corrected_asr.{suffix}"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(portable_path(path, root=ROOT))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.6, 4.5))
    metric_names = ["Targeted_ASR", "TCR", "attack_condition_utility"]
    colors = ["#c0392b", "#2471a3", "#7d3c98"]
    for offset, (metric_name, color) in enumerate(zip(metric_names, colors)):
        values = [
            100 * float(_overall(analyses[label]["metrics"], metric_name)["rate"] or 0)
            for label in labels
        ]
        positions = [value + (offset - 1) * 0.24 for value in x]
        ax.bar(positions, values, 0.24, label=metric_name, color=color)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Rate (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Corrected safety and utility diagnostics")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    joint_paths: list[str] = []
    for suffix in ("png", "svg"):
        path = output_dir / f"corrected_safety_utility.{suffix}"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        joint_paths.append(portable_path(path, root=ROOT))
    plt.close(fig)
    return {
        "legacy_vs_corrected_asr": paths,
        "corrected_safety_utility": joint_paths,
    }


def _write_report(path: Path, analyses: Mapping[str, Mapping[str, Any]]) -> None:
    lines = [
        "# AgentDojo metric semantics analysis-v2",
        "",
        "## Material Passport",
        "",
        "- Origin Skill: experiment-agent",
        "- Origin Mode: validate",
        "- Verification Status: VERIFIED_FROM_EXISTING_RAW_TRACES",
        "- Evidence Class: post-hoc non-mutating correction",
        "- Formal Result Eligibility: false pending downstream readmission",
        "",
        "## Corrected results",
        "",
        "| Source | Targeted ASR | Utility TCR | Attack-condition utility | Operational failures |",
        "| --- | --- | --- | --- | --- |",
    ]
    for label, analysis in analyses.items():
        metrics = analysis["metrics"]
        lines.append(
            f"| `{label}` | {_format_metric(_overall(metrics, 'Targeted_ASR'))} | "
            f"{_format_metric(_overall(metrics, 'TCR'))} | "
            f"{_format_metric(_overall(metrics, 'attack_condition_utility'))} | "
            f"{_format_metric(_overall(metrics, 'operational_failure_rate'))} |"
        )
    lines.extend(
        [
            "",
            "ToolFilter changes from the legacy complement 622/629 to raw official "
            "Targeted ASR 7/629. Task Shield v1.5 changes from 6/6 to 0/6, while "
            "utility remains 1/6 and attack-condition utility remains 0/6. Therefore "
            "the Task Shield result is still a failed, degenerate qualification rather "
            "than positive defense evidence.",
            "",
            "## Eleven-pattern fallacy scan",
            "",
            "| Pattern | Assessment |",
            "| --- | --- |",
            "| Simpson's paradox | Not tested; suite-level rows are reported and must not be replaced by the aggregate alone. |",
            "| Ecological fallacy | No individual-case claim is inferred from aggregate ASR. |",
            "| Berkson's paradox | Task Shield's six attacks are selected stress cases and are not population estimates. |",
            "| Collider bias | No adjusted regression or collider conditioning is used. |",
            "| Base-rate neglect | Task Shield 0/6 is not generalized to the 629-case universe. |",
            "| Regression to the mean | No pre/post extreme-group causal claim is made. |",
            "| Survivorship bias | Failed utility row remains in the 12-case denominator. |",
            "| Look-elsewhere effect | No significance selection is performed. |",
            "| Garden of forking paths | v1.3-v1.6 are post-hoc engineering revisions and remain non-confirmatory. |",
            "| Correlation vs causation | The correction establishes field semantics, not defense causality. |",
            "| Reverse causality | Not applicable to the deterministic trace-to-metric mapping. |",
            "",
            "## Boundary",
            "",
            "No source outcome, trace, old analysis, freeze, registry or Q2 artifact "
            "was overwritten. Downstream formal tables remain provisional until their "
            "own non-mutating admission bridge consumes metric semantics v2.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _current_hashes(paths: Mapping[str, str]) -> dict[str, str]:
    current: dict[str, str] = {}
    for relative in paths:
        path = resolve_artifact_path(relative, root=ROOT)
        if path.is_file():
            current[relative] = sha256_file(path)
    return current


def reanalyze(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    gate_dir: Path = DEFAULT_GATE_DIR,
) -> dict[str, Any]:
    audit_path = output_dir / "metric_semantics_audit.json"
    audit = read_json(audit_path)
    if audit.get("status") != "completed_pass":
        raise ValueError("metric semantics audit did not pass")
    analyses: dict[str, dict[str, Any]] = {}
    artifact_rows: list[dict[str, str]] = []
    for label, details in dict(audit["corrected_rows"]).items():
        corrected_path = resolve_artifact_path(details["path"], root=ROOT)
        if sha256_file(corrected_path) != details["sha256"]:
            raise ValueError(f"corrected-row hash mismatch: {label}")
        rows = read_jsonl(corrected_path)
        metrics, summary = build_metrics(rows)
        source_dir = output_dir / f"{label}_analysis_v2"
        metrics_path = source_dir / "metrics.csv"
        summary_path = source_dir / "summary.json"
        _write_csv(metrics_path, metrics)
        _write_json(summary_path, summary)
        analyses[label] = {"metrics": metrics, "summary": summary}
        artifact_rows.extend(
            [
                {
                    "path": portable_path(metrics_path, root=ROOT),
                    "sha256": sha256_file(metrics_path),
                },
                {
                    "path": portable_path(summary_path, root=ROOT),
                    "sha256": sha256_file(summary_path),
                },
            ]
        )
    report_path = output_dir / "analysis_v2.md"
    _write_report(report_path, analyses)
    figures = _build_figures(analyses, output_dir / "figures_v2")
    artifact_rows.append(
        {"path": portable_path(report_path, root=ROOT), "sha256": sha256_file(report_path)}
    )
    for paths in figures.values():
        for relative in paths:
            artifact_rows.append(
                {"path": relative, "sha256": sha256_file(ROOT / relative)}
            )
    manifest = {
        "schema_version": "paper-agentdojo-metric-reanalysis-v2-1.0",
        "analyzer_version": ANALYZER_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_non_mutating_reanalysis",
        "evidence_class": "post_hoc_non_mutating_metric_correction",
        "result_eligible_for_formal_tables": False,
        "model_calls": 0,
        "api_calls": 0,
        "q2_score_change": 0,
        "audit_path": portable_path(audit_path, root=ROOT),
        "audit_sha256": sha256_file(audit_path),
        "source_analyses": {label: value["summary"] for label, value in analyses.items()},
        "figures": figures,
        "artifacts": artifact_rows,
        "boundary": "Corrected descriptive evidence only; no historical or registry replacement.",
    }
    manifest_path = output_dir / "reanalysis_manifest.json"
    _write_json(manifest_path, manifest)

    protected_after_audit = dict(audit["protected_hashes_after"])
    protected_current = _current_hashes(protected_after_audit)
    toolfilter = analyses["toolfilter_formal"]["summary"]
    taskshield = analyses["taskshield_v15"]["summary"]
    gate_checks = {
        "semantics_audit_passed": audit["status"] == "completed_pass",
        "all_audit_checks_passed": audit["passed_checks"] == audit["total_checks"],
        "toolfilter_rows_726": toolfilter["rows"] == 726,
        "toolfilter_attack_denominator_629": toolfilter["attack_rows"] == 629,
        "toolfilter_corrected_attack_success_7": toolfilter["attack_successes"] == 7,
        "taskshield_rows_12": taskshield["rows"] == 12,
        "taskshield_attack_denominator_6": taskshield["attack_rows"] == 6,
        "taskshield_corrected_attack_success_0": taskshield["attack_successes"] == 0,
        "taskshield_utility_success_1": taskshield["utility_successes"] == 1,
        "taskshield_attack_condition_utility_0": (
            taskshield["attack_condition_utility_successes"] == 0
        ),
        "corrected_rows_hash_linked": all(
            analyses[label]["summary"]["rows_sha256"] == details["rows_sha256"]
            for label, details in dict(audit["corrected_rows"]).items()
        ),
        "protected_hashes_unchanged_after_reanalysis": (
            protected_current == protected_after_audit
        ),
        "analysis_artifacts_hash_linked": all(
            sha256_file(resolve_artifact_path(row["path"], root=ROOT)) == row["sha256"]
            for row in artifact_rows
        ),
        "no_model_or_api_calls": manifest["model_calls"] == 0 and manifest["api_calls"] == 0,
        "no_registry_or_q2_promotion": (
            manifest["q2_score_change"] == 0
            and manifest["result_eligible_for_formal_tables"] is False
        ),
    }
    gate_passed = all(gate_checks.values())
    gate = {
        "schema_version": "paper-taskshield-v16-gate-g0-1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gate": "G0_agentdojo_metric_semantics",
        "status": "passed" if gate_passed else "failed",
        "checks": gate_checks,
        "passed_checks": sum(gate_checks.values()),
        "total_checks": len(gate_checks),
        "model_calls": 0,
        "api_calls": 0,
        "result_eligible_for_formal_tables": False,
        "q2_score_change": 0,
        "audit_path": portable_path(audit_path, root=ROOT),
        "audit_sha256": sha256_file(audit_path),
        "reanalysis_manifest_path": portable_path(manifest_path, root=ROOT),
        "reanalysis_manifest_sha256": sha256_file(manifest_path),
        "next_action": (
            "implement_taskshield_v16_correctness_runtime_and_deterministic_tests"
            if gate_passed
            else "stop_and_repair_metric_semantics_audit"
        ),
        "boundary": "G0 permits only P1-P2 zero-model engineering; it is not formal admission.",
    }
    gate_dir.mkdir(parents=True, exist_ok=True)
    gate_path = gate_dir / "gate_g0.json"
    _write_json(gate_path, gate)
    gate_lines = [
        "# Task Shield v1.6 Gate G0",
        "",
        f"- Status: `{gate['status']}`",
        f"- Checks: `{gate['passed_checks']}/{gate['total_checks']}`",
        "- Model/API calls: `0/0`",
        "- Formal eligibility: `false`",
        "- Q2 score change: `0`",
        "",
        "## Checks",
        "",
    ]
    gate_lines.extend(
        f"- `{'PASS' if passed else 'FAIL'}` `{name}`"
        for name, passed in gate_checks.items()
    )
    gate_lines.extend(["", "## Boundary", "", gate["boundary"]])
    (gate_dir / "gate_g0.md").write_text("\n".join(gate_lines) + "\n", encoding="utf-8")
    return gate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--gate-dir", type=Path, default=DEFAULT_GATE_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gate = reanalyze(
        output_dir=args.output_dir.resolve(),
        gate_dir=args.gate_dir.resolve(),
    )
    print(json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if gate["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

