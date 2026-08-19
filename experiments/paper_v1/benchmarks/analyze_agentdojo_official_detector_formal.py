"""Analyze a completed official AgentDojo transformers detector run."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

from .common import rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_transformers_pi_detector_official_resource_isolated_formal_v1"
)
ANALYZER_VERSION = "m3-paper-v1-agentdojo-official-transformers-detector-analysis-1.1"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total)
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _metric_row(
    *,
    scope: str,
    suite: str,
    metric: str,
    successes: int,
    total: int,
) -> dict[str, Any]:
    low, high = wilson_interval(successes, total)
    return {
        "scope": scope,
        "suite": suite,
        "metric": metric,
        "successes": successes,
        "total": total,
        "rate": successes / total if total else None,
        "wilson95_low": low if total else None,
        "wilson95_high": high if total else None,
    }


def build_metrics(rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_suite: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_suite[str(row.get("suite", "unknown"))].append(row)

    metrics: list[dict[str, Any]] = []
    groups = {"overall": rows, **dict(sorted(by_suite.items()))}
    for suite, group in groups.items():
        utility = [row for row in group if row.get("case_kind") == "utility"]
        security = [row for row in group if row.get("case_kind") == "security"]
        completed = [row for row in group if row.get("status") == "completed"]
        metrics.extend(
            [
                _metric_row(
                    scope="utility",
                    suite=suite,
                    metric="TCR",
                    successes=sum(bool(row.get("utility_success")) for row in utility),
                    total=len(utility),
                ),
                _metric_row(
                    scope="security",
                    suite=suite,
                    metric="ASR",
                    successes=sum(bool(row.get("attack_success")) for row in security),
                    total=len(security),
                ),
                _metric_row(
                    scope="detector",
                    suite=suite,
                    metric="redacted_case_rate",
                    successes=sum(
                        int(row.get("detector_redaction_marker_count", 0)) > 0
                        for row in completed
                    ),
                    total=len(completed),
                ),
                _metric_row(
                    scope="engineering",
                    suite=suite,
                    metric="failure_rate",
                    successes=sum(row.get("status") == "failed" for row in group),
                    total=len(group),
                ),
            ]
        )

    latencies = [
        float(row["elapsed_ms"])
        for row in rows
        if isinstance(row.get("elapsed_ms"), (int, float))
    ]
    summary = {
        "case_count": len(rows),
        "utility_case_count": sum(row.get("case_kind") == "utility" for row in rows),
        "security_case_count": sum(row.get("case_kind") == "security" for row in rows),
        "failure_count": sum(row.get("status") == "failed" for row in rows),
        "latency_ms": {
            "n": len(latencies),
            "median": median(latencies) if latencies else None,
            "p95": _percentile(latencies, 0.95),
            "max": max(latencies) if latencies else None,
        },
    }
    return metrics, summary


def _write_metrics_csv(path: Path, metrics: Iterable[Mapping[str, Any]]) -> None:
    fields = [
        "scope",
        "suite",
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
        writer.writerows({field: row.get(field) for field in fields} for row in metrics)


def _rate(metrics: list[Mapping[str, Any]], suite: str, metric: str) -> Mapping[str, Any]:
    return next(row for row in metrics if row["suite"] == suite and row["metric"] == metric)


def _save_figure(fig: Any, output_dir: Path, stem: str) -> list[str]:
    paths: list[str] = []
    for suffix in ["png", "svg"]:
        path = output_dir / f"{stem}.{suffix}"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(str(path.resolve()))
    return paths


def build_figures(
    rows: list[Mapping[str, Any]],
    metrics: list[Mapping[str, Any]],
    output_dir: Path,
) -> dict[str, list[str]]:
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    suites = sorted({str(row.get("suite", "unknown")) for row in rows})
    figures: dict[str, list[str]] = {}

    for metric, title, ylabel, stem, color in [
        ("ASR", "Attack success rate by AgentDojo suite", "ASR (%)", "asr_by_suite", "#c0392b"),
        ("TCR", "Utility task completion by AgentDojo suite", "TCR (%)", "tcr_by_suite", "#2471a3"),
        (
            "redacted_case_rate",
            "Cases with at least one detector redaction",
            "Redacted cases (%)",
            "redaction_rate_by_suite",
            "#7d3c98",
        ),
    ]:
        values = [float(_rate(metrics, suite, metric)["rate"] or 0.0) * 100.0 for suite in suites]
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        bars = ax.bar(suites, values, color=color, alpha=0.9)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.set_ylim(0, 100)
        ax.grid(axis="y", alpha=0.25)
        ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=8)
        figures[stem] = _save_figure(fig, output_dir, stem)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for kind, color in [("utility", "#2471a3"), ("security", "#c0392b")]:
        values = sorted(
            float(row["elapsed_ms"])
            for row in rows
            if row.get("case_kind") == kind
            and isinstance(row.get("elapsed_ms"), (int, float))
        )
        if values:
            y = [(index + 1) / len(values) for index in range(len(values))]
            ax.step(values, y, where="post", label=kind, color=color)
    ax.set_title("End-to-end case latency ECDF")
    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("ECDF")
    ax.grid(alpha=0.25)
    ax.legend()
    figures["latency_ecdf"] = _save_figure(fig, output_dir, "latency_ecdf")
    plt.close(fig)

    return figures


def _fmt_rate(row: Mapping[str, Any]) -> str:
    rate = float(row["rate"] or 0.0) * 100.0
    low = float(row["wilson95_low"] or 0.0) * 100.0
    high = float(row["wilson95_high"] or 0.0) * 100.0
    return f"{row['successes']}/{row['total']} = {rate:.2f}% (Wilson 95% CI {low:.2f}–{high:.2f}%)"


def write_report(
    path: Path,
    run_manifest: Mapping[str, Any],
    metrics: list[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    asr = _rate(metrics, "overall", "ASR")
    tcr = _rate(metrics, "overall", "TCR")
    redaction = _rate(metrics, "overall", "redacted_case_rate")
    failure = _rate(metrics, "overall", "failure_rate")
    lines = [
        "# AgentDojo official transformers_pi_detector formal analysis",
        "",
        f"- Run status: `{run_manifest['status']}`",
        f"- Formal result eligible: `{run_manifest['result_eligible_for_formal_tables']}`",
        f"- Model: `{run_manifest['model_id']}`",
        f"- Cases: {summary['case_count']} ({summary['utility_case_count']} utility + {summary['security_case_count']} security)",
        "",
        "## Main results",
        "",
        f"- Official AgentDojo ASR: {_fmt_rate(asr)}",
        f"- Official AgentDojo utility TCR: {_fmt_rate(tcr)}",
        f"- Cases with detector redaction: {_fmt_rate(redaction)}",
        f"- Failure rate: {_fmt_rate(failure)}",
        f"- End-to-end latency median/p95: {summary['latency_ms']['median']:.2f} / {summary['latency_ms']['p95']:.2f} ms",
        "",
        "## Per-suite results",
        "",
        "| Suite | ASR | TCR | Redacted case rate | Failure rate |",
        "|---|---:|---:|---:|---:|",
    ]
    suites = sorted({str(row["suite"]) for row in metrics if row["suite"] != "overall"})
    for suite in suites:
        lines.append(
            f"| `{suite}` | {_fmt_rate(_rate(metrics, suite, 'ASR'))} | "
            f"{_fmt_rate(_rate(metrics, suite, 'TCR'))} | "
            f"{_fmt_rate(_rate(metrics, suite, 'redacted_case_rate'))} | "
            f"{_fmt_rate(_rate(metrics, suite, 'failure_rate'))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "These are end-to-end AgentDojo results for the official transformers_pi_detector condition only. A paired claim against no-defense or M3 requires the matching frozen model/case outcomes and a paired statistical analysis. These results do not establish M3-v2, InjecAgent, multilingual, adaptive-attack or frontier-model performance.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(*, run_dir: Path, output_dir: Path, allow_diagnostic: bool) -> dict[str, Any]:
    run_manifest_path = run_dir / "run_manifest.json"
    outcomes_path = run_dir / "outcomes.jsonl"
    run_manifest = _read_json(run_manifest_path)
    if not allow_diagnostic and (
        run_manifest.get("status") != "completed_formal"
        or not run_manifest.get("result_eligible_for_formal_tables")
    ):
        raise ValueError("run is not formally admitted; use --allow-diagnostic only for diagnostics")
    rows = _read_jsonl(outcomes_path)
    expected = int(run_manifest.get("summary", {}).get("expected_cases", 0))
    if len(rows) != expected:
        raise ValueError(f"outcome coverage mismatch: {len(rows)} != {expected}")
    if len({str(row.get("benchmark_case_id", "")) for row in rows}) != len(rows):
        raise ValueError("duplicate benchmark_case_id in outcomes")
    metrics, summary = build_metrics(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics.csv"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "analysis.md"
    _write_metrics_csv(metrics_path, metrics)
    _write_json(summary_path, summary)
    figures = build_figures(rows, metrics, output_dir / "figures")
    write_report(report_path, run_manifest, metrics, summary)
    manifest = {
        "schema_version": "paper-agentdojo-official-detector-analysis-manifest-1.0",
        "analyzer_version": ANALYZER_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_formal_analysis" if run_manifest.get("result_eligible_for_formal_tables") else "completed_diagnostic_analysis",
        "result_eligible_for_formal_tables": bool(run_manifest.get("result_eligible_for_formal_tables")),
        "run_manifest_path": str(run_manifest_path.resolve()),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "outcomes_path": str(outcomes_path.resolve()),
        "outcomes_sha256": sha256_file(outcomes_path),
        "case_rows_sha256": rows_sha256(rows),
        "metrics_path": str(metrics_path.resolve()),
        "metrics_sha256": sha256_file(metrics_path),
        "summary_path": str(summary_path.resolve()),
        "summary_sha256": sha256_file(summary_path),
        "report_path": str(report_path.resolve()),
        "report_sha256": sha256_file(report_path),
        "figures": figures,
        "summary": summary,
        "boundary": "Single-condition descriptive analysis. Paired superiority claims require a separately frozen paired comparison.",
    }
    _write_json(output_dir / "analysis_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--allow-diagnostic", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir or (args.run_dir / "analysis")
    manifest = analyze(
        run_dir=args.run_dir.resolve(),
        output_dir=output_dir.resolve(),
        allow_diagnostic=args.allow_diagnostic,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "eligible": manifest["result_eligible_for_formal_tables"],
                "report": manifest["report_path"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
