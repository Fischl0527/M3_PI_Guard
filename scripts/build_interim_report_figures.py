"""Build non-causal, report-only figures from frozen experiment tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "outputs"
    / "experiments"
    / "E14_context_correction_v2_r3"
    / "throughput_by_concurrency_data.csv"
)
FIGURE_DIR = (
    ROOT
    / "harness"
    / "workspaces"
    / "runpro"
    / "10_analysis"
    / "figures"
)
OUTPUT = FIGURE_DIR / "e14-throughput-grouped-bar.png"


def build_e14_throughput() -> None:
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    contexts = (2048, 4096, 8192, 16384)
    concurrencies = (1, 2, 4)
    conditions = ("e14_v2_off", "e14_v2_full_guard")
    values = {
        (
            int(row["target_prompt_tokens"]),
            int(row["concurrency"]),
            row["condition_id"],
        ): float(row["successful_case_runs_per_s"])
        for row in rows
    }
    expected = {
        (context, concurrency, condition)
        for context in contexts
        for concurrency in concurrencies
        for condition in conditions
    }
    if set(values) != expected:
        missing = sorted(expected - set(values))
        extra = sorted(set(values) - expected)
        raise RuntimeError(f"unexpected E14 throughput grid; missing={missing}, extra={extra}")

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "axes.edgecolor": "#344054",
            "axes.linewidth": 0.8,
            "xtick.color": "#344054",
            "ytick.color": "#344054",
            "text.color": "#101828",
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharey=True)
    x = np.arange(len(concurrencies), dtype=float)
    width = 0.34
    palette = {"e14_v2_off": "#4C78A8", "e14_v2_full_guard": "#F28E2B"}
    labels = {"e14_v2_off": "No Guard", "e14_v2_full_guard": "Full Guard"}
    hatches = {"e14_v2_off": "//", "e14_v2_full_guard": ""}

    for axis, context in zip(axes.flat, contexts):
        for offset, condition in ((-width / 2, conditions[0]), (width / 2, conditions[1])):
            heights = [values[(context, concurrency, condition)] for concurrency in concurrencies]
            bars = axis.bar(
                x + offset,
                heights,
                width,
                color=palette[condition],
                edgecolor="#344054",
                linewidth=0.7,
                hatch=hatches[condition],
                label=labels[condition],
            )
            axis.bar_label(bars, labels=[f"{value:.2f}" for value in heights], padding=3, fontsize=9)
        axis.set_title(f"{context // 1024}K prompt target")
        axis.set_xticks(x, [str(value) for value in concurrencies])
        axis.set_xlabel("Offered client concurrency")
        axis.set_ylim(0, 1.02)
        axis.grid(axis="y", color="#D0D5DD", linewidth=0.7, alpha=0.75)
        axis.set_axisbelow(True)
    axes[0, 0].set_ylabel("Successful mixed case-runs/s")
    axes[1, 0].set_ylabel("Successful mixed case-runs/s")
    handles, legend_labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.93))
    fig.suptitle("E14 mixed-workload system throughput", fontsize=16, y=0.985)
    fig.text(
        0.5,
        0.945,
        "Six formal mixed cases per context × concurrency × condition; warmup excluded",
        ha="center",
        va="top",
        color="#475467",
        fontsize=10,
    )
    fig.text(
        0.5,
        0.012,
        "System-throughput evidence only; differences also reflect condition-specific successful paths and are not pure Guard overhead.",
        ha="center",
        va="bottom",
        color="#475467",
        fontsize=9,
    )
    fig.tight_layout(rect=(0.03, 0.05, 0.99, 0.90))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=180, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(OUTPUT)


def build_registry_status() -> None:
    registry = json.loads((ROOT / "experiments" / "registry.json").read_text(encoding="utf-8"))
    experiments = registry["experiments"]
    if [item["id"] for item in experiments] != [f"E{index}" for index in range(18)]:
        raise RuntimeError("registry experiment order drifted")
    palette = {
        "completed": "#12B76A",
        "running": "#F79009",
        "pending": "#98A2B3",
        "failed": "#F04438",
    }
    fig, axis = plt.subplots(figsize=(13, 3.2))
    for index, item in enumerate(experiments):
        axis.barh(0, 0.86, left=index, height=0.58, color=palette[item["status"]], edgecolor="white")
        axis.text(index + 0.43, 0, item["id"], ha="center", va="center", color="white", fontsize=10, weight="bold")
    axis.set_xlim(0, 18)
    axis.set_ylim(-0.75, 0.75)
    axis.set_yticks([])
    axis.set_xticks([])
    for spine in axis.spines.values():
        spine.set_visible(False)
    counts = {status: sum(item["status"] == status for item in experiments) for status in palette}
    axis.set_title("E0–E17 registry status at the 2026-07-16 pause point", pad=18, fontsize=15)
    axis.text(
        0.5,
        -0.38,
        f"{counts['completed']} completed  •  {counts['running']} running  •  {counts['failed']} failed  •  E17 remains human-gated",
        transform=axis.transAxes,
        ha="center",
        va="center",
        color="#475467",
    )
    destination = FIGURE_DIR / "registry-status-2026-07-16.png"
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(destination, dpi=180, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(destination)


def build_e17_diagnostic_status() -> None:
    comparison = json.loads(
        (ROOT / "outputs" / "experiments" / "E17_auto_review_corrected_r3" / "comparison.json").read_text(
            encoding="utf-8"
        )
    )
    values = [
        100.0 * comparison["primary_agreement"]["rate"],
        100.0 * comparison["full_code_set_agreement"]["rate"],
        100.0 * comparison["secondary_set_agreement"]["rate"],
    ]
    labels = ["Primary class", "Full code set", "Secondary set"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1.0, 2.2]})
    axes[0].barh([1, 0], [0, 2], color=["#F79009", "#667085"], height=0.55)
    axes[0].set_xlim(0, 2)
    axes[0].set_yticks([1, 0], ["Eligible human reviews", "Automated diagnostics"])
    axes[0].set_xticks([0, 1, 2])
    axes[0].set_xlabel("Completed reviewers")
    axes[0].set_title("Gate status")
    axes[0].text(0.04, 1, "0 / 2", va="center", ha="left", color="#B54708", weight="bold")
    axes[0].text(1.96, 0, "2 / 2 (ineligible)", va="center", ha="right", color="white", weight="bold")
    bars = axes[1].barh(labels, values, color=["#4C78A8", "#7A5AF8", "#12B76A"], height=0.6)
    axes[1].set_xlim(0, 100)
    axes[1].set_xlabel("Agreement (%)")
    axes[1].set_title(f"Two-agent diagnostic agreement (n={comparison['items']:,})")
    axes[1].bar_label(bars, labels=[f"{value:.2f}%" for value in values], padding=4)
    for axis in axes:
        axis.grid(axis="x", color="#EAECF0", linewidth=0.8)
        axis.set_axisbelow(True)
    fig.suptitle("E17 automated review is diagnostic only; the human gate is still open", fontsize=15, y=1.02)
    fig.text(
        0.5,
        0.01,
        "Automated outputs are isolated from human submissions and cannot satisfy E17.",
        ha="center",
        color="#475467",
    )
    destination = FIGURE_DIR / "e17-review-gate-2026-07-16.png"
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    fig.savefig(destination, dpi=180, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(destination)


def main() -> None:
    build_e14_throughput()
    build_registry_status()
    build_e17_diagnostic_status()


if __name__ == "__main__":
    main()
