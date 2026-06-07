"""Generate DAY5 metric figures from an m3_eval summary CSV."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


METRICS = ("ASR", "UTR", "DSR", "BSR", "FPR", "WRS")
FIGURE_NAMES = {
    "ASR": "day5_asr_by_defense_mode.png",
    "UTR": "day5_utr_by_defense_mode.png",
    "DSR": "day5_dsr_by_defense_mode.png",
    "BSR": "day5_bsr_by_defense_mode.png",
    "FPR": "day5_fpr_by_defense_mode.png",
    "WRS": "day5_wrs_by_defense_mode.png",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plot M3_PI_Guard DAY5 metrics.")
    parser.add_argument("--summary", required=True, help="summary CSV from m3_eval.evaluate")
    parser.add_argument("--out-dir", required=True, help="Output directory for PNG figures")
    args = parser.parse_args(argv)

    summary_path = Path(args.summary)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _read_csv(summary_path)
    _plot_metrics_by_defense(rows, out_dir)
    _plot_asr_by_attack_family(rows, out_dir)
    _plot_guard_reasons(summary_path.with_suffix(".json"), out_dir)
    return 0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _plot_metrics_by_defense(rows: list[dict[str, str]], out_dir: Path) -> None:
    overall_rows = [row for row in rows if row.get("scope") == "overall"]
    labels = [_display_mode(row) for row in overall_rows]
    for metric in METRICS:
        values = [_to_float(row.get(metric)) for row in overall_rows]
        _bar_chart(
            labels,
            values,
            title=f"{metric} by defense mode",
            ylabel=metric,
            out_path=out_dir / FIGURE_NAMES[metric],
            ylim=(0.0, 1.0),
        )


def _plot_asr_by_attack_family(rows: list[dict[str, str]], out_dir: Path) -> None:
    family_rows = [row for row in rows if row.get("scope") == "attack_family"]
    grouped: dict[str, dict[str, float]] = defaultdict(dict)
    for row in family_rows:
        grouped[row.get("group", "unknown")][_display_mode(row)] = _to_float(row.get("ASR"))

    families = sorted(grouped)
    modes = sorted({mode for values in grouped.values() for mode in values})
    if not families or not modes:
        _bar_chart([], [], "ASR by attack family", "ASR", out_dir / "day5_asr_by_attack_family.png")
        return

    import matplotlib.pyplot as plt

    width = 0.8 / max(1, len(modes))
    x_positions = list(range(len(families)))
    fig, ax = plt.subplots(figsize=(max(10, len(families) * 1.2), 5.5))
    for index, mode in enumerate(modes):
        offsets = [x + (index - (len(modes) - 1) / 2) * width for x in x_positions]
        values = [grouped[family].get(mode, 0.0) for family in families]
        ax.bar(offsets, values, width=width, label=mode)
    ax.set_title("ASR by attack family")
    ax.set_ylabel("ASR")
    ax.set_ylim(0.0, 1.0)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(families, rotation=30, ha="right")
    ax.legend(loc="best")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "day5_asr_by_attack_family.png", dpi=160)
    plt.close(fig)


def _plot_guard_reasons(summary_json: Path, out_dir: Path) -> None:
    reasons = Counter()
    if summary_json.exists():
        payload = json.loads(summary_json.read_text(encoding="utf-8"))
        for record in payload.get("blocked_records", []):
            for reason in str(record.get("reasons", "")).split("|"):
                reason = reason.strip()
                if reason:
                    reasons[reason] += 1

    labels = [item[0] for item in reasons.most_common(10)]
    values = [item[1] for item in reasons.most_common(10)]
    _bar_chart(
        labels,
        values,
        title="Top 10 guard reasons",
        ylabel="count",
        out_path=out_dir / "day5_guard_reasons_top10.png",
    )


def _bar_chart(
    labels: list[str],
    values: list[float],
    title: str,
    ylabel: str,
    out_path: Path,
    ylim: tuple[float, float] | None = None,
) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5))
    if labels:
        ax.bar(labels, values, color="#3b82f6")
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", labelrotation=25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _display_mode(row: dict[str, str]) -> str:
    mode = row.get("defense_mode") or "unknown"
    log_name = Path(row.get("log_file", "")).stem
    if "|" in mode:
        return log_name or mode
    return mode


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
