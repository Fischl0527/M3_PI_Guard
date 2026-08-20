"""Build the five preregistered figures for the lean empirical paper.

The module consumes only the two compact analysis JSON files.  It does not
open raw provider traces, call a model, replay historical evidence, or create
hash manifests.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUTHORIZATION_ANALYSIS = (
    PROJECT_ROOT / "docs/research/paper_v2/lean_empirical/authorization_results_v1.json"
)
DEFAULT_EXISTING_ANALYSIS = (
    PROJECT_ROOT
    / "docs/research/paper_v2/lean_empirical/existing_results_analysis_v1.json"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "docs/research/paper_v2/lean_empirical/figures"

INK = "#17212B"
MUTED = "#667085"
GRID = "#D9DEE7"
BLUE = "#2563A8"
BLUE_LIGHT = "#A8C7E8"
ORANGE = "#D97706"
ORANGE_LIGHT = "#F6C98B"
NEUTRAL = "#8A94A3"


CHART_CONTRACTS: tuple[dict[str, str], ...] = (
    {
        "id": "figure_1_online_field_isolation",
        "question": "Which fields are visible online and which remain offline?",
        "takeaway": (
            "Raw evaluator/scoring fields stay offline; exact_gold exposes only "
            "derived authorization."
        ),
        "family": "flow schematic",
    },
    {
        "id": "figure_2_safety_utility_pareto",
        "question": "How do authorization regimes trade attack safety for benign utility?",
        "takeaway": "Each condition is compared on the same paired task population.",
        "family": "relationship scatter",
    },
    {
        "id": "figure_3_authorization_forest",
        "question": "How large are the paired authorization and mechanism effects?",
        "takeaway": "Absolute effects and task-cluster uncertainty are shown together.",
        "family": "uncertainty forest",
    },
    {
        "id": "figure_4_runtime_burden",
        "question": "What confirmation, blocking, failure, and latency burden is incurred?",
        "takeaway": "Operational burden is reported alongside security and utility.",
        "family": "faceted comparison",
    },
    {
        "id": "figure_5_adaptive_first_success",
        "question": "How often does adaptive search find a first unsafe effect by budget?",
        "takeaway": "Only budgets 50 and 200 are supported; no saturation claim is made.",
        "family": "ordered cumulative curve",
    },
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "svg.hashsalt": "m3-paper-v2-lean-figures-v1",
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "grid.alpha": 0.75,
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
        }
    )


def _save(fig: plt.Figure, output_dir: Path, stem: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for suffix in ("png", "svg", "pdf"):
        path = output_dir / f"{stem}.{suffix}"
        metadata = None
        if suffix == "svg":
            metadata = {"Date": None}
        elif suffix == "pdf":
            metadata = {"CreationDate": None, "ModDate": None}
        fig.savefig(
            path,
            dpi=220 if suffix == "png" else None,
            metadata=metadata,
        )
        if suffix == "svg":
            svg = path.read_text(encoding="utf-8")
            normalized = "\n".join(line.rstrip() for line in svg.splitlines()) + "\n"
            path.write_text(normalized, encoding="utf-8", newline="\n")
        paths.append(str(path))
    plt.close(fig)
    return paths


def _box(
    ax: plt.Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    text: str,
    *,
    edge: str,
    fill: str,
) -> None:
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.015,rounding_size=0.02",
        linewidth=1.4,
        edgecolor=edge,
        facecolor=fill,
    )
    ax.add_patch(patch)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=9.5,
        color=INK,
    )


def figure_field_isolation(output_dir: Path) -> list[str]:
    fig, ax = plt.subplots(figsize=(10.5, 4.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(
        "Online authorization projection and offline evaluation boundary", pad=16
    )
    ax.text(
        0.5,
        0.93,
        "Raw scoring fields stay offline; exact_gold exposes only a derived authorization object",
        ha="center",
        color=MUTED,
        fontsize=9.5,
    )
    _box(
        ax,
        (0.03, 0.56),
        0.21,
        0.22,
        "Task context\n+ user intent",
        edge=BLUE,
        fill="#EFF6FC",
    )
    _box(
        ax,
        (0.29, 0.56),
        0.21,
        0.22,
        "Authorization projection\n+ provenance events",
        edge=BLUE,
        fill="#EFF6FC",
    )
    _box(
        ax,
        (0.55, 0.56),
        0.18,
        0.22,
        "Runtime Guard\nALLOW / ASK / DENY",
        edge=BLUE,
        fill="#E2EFFA",
    )
    _box(
        ax,
        (0.78, 0.56),
        0.19,
        0.22,
        "Isolated simulated\neffect receipt",
        edge=BLUE,
        fill="#EFF6FC",
    )
    for start, end in ((0.24, 0.29), (0.50, 0.55), (0.73, 0.78)):
        ax.annotate(
            "",
            xy=(end, 0.67),
            xytext=(start, 0.67),
            arrowprops={"arrowstyle": "->", "color": INK, "lw": 1.3},
        )
    _box(
        ax,
        (0.29, 0.15),
        0.21,
        0.20,
        "Gold answer / labels\nEvaluator metadata",
        edge=ORANGE,
        fill="#FFF4E6",
    )
    _box(
        ax,
        (0.63, 0.15),
        0.25,
        0.20,
        "Offline scoring only\nunsafe effect + completion",
        edge=ORANGE,
        fill="#FFF4E6",
    )
    ax.annotate(
        "",
        xy=(0.63, 0.25),
        xytext=(0.50, 0.25),
        arrowprops={"arrowstyle": "->", "color": ORANGE, "lw": 1.3},
    )
    ax.annotate(
        "",
        xy=(0.395, 0.56),
        xytext=(0.395, 0.35),
        arrowprops={"arrowstyle": "->", "color": ORANGE, "lw": 1.1, "ls": "--"},
    )
    ax.text(
        0.415,
        0.455,
        "derived policy\nexact_gold only",
        ha="left",
        va="center",
        color=ORANGE,
        fontsize=8,
    )
    ax.plot([0.05, 0.95], [0.46, 0.46], color=NEUTRAL, lw=1.1, ls="--")
    ax.text(
        0.95,
        0.475,
        "online / offline boundary",
        ha="right",
        va="bottom",
        color=MUTED,
        fontsize=8.5,
    )
    ax.text(
        0.06,
        0.43,
        "raw evaluator/scoring fields do not cross unchanged",
        ha="left",
        va="top",
        color=ORANGE,
        fontsize=8.5,
    )
    return _save(fig, output_dir, "figure_1_online_field_isolation")


def _label(condition: str, regime: str) -> str:
    condition_labels = {
        "m3_policy_only": "Policy-only",
        "m3_full": "M3-full",
        "strongest_peer_reviewed_structural_baseline": "Structural baseline",
    }
    regime_labels = {
        "auto_compiled": "auto",
        "exact_gold": "exact",
        "broad": "broad",
        "underspecified": "under",
        "conflicting": "conflict",
    }
    return f"{condition_labels.get(condition, condition)} / {regime_labels.get(regime, regime)}"


def figure_pareto(analysis: Mapping[str, Any], output_dir: Path) -> list[str]:
    fig, ax = plt.subplots(figsize=(10.2, 6.2))
    fig.suptitle(
        "Security–utility trade-off by authorization condition",
        y=0.98,
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.11,
        0.925,
        "DeepSeek V4 Pro; x = benign-tool completion, y = 1 − attack unsafe-effect rate",
        color=MUTED,
        fontsize=9,
    )
    metrics = analysis["deepseek"]["condition_metrics"]
    key_lines: list[tuple[str, str]] = []
    point_groups: dict[tuple[float, float, str, str], list[str]] = {}
    for index, item in enumerate(metrics.values()):
        unsafe = item["attack_unsafe_effect"]
        utility = item["benign_tool_tcr"]
        if unsafe["total"] == 0 or utility["total"] == 0:
            continue
        x = 100 * utility["rate"]
        y = 100 * (1 - unsafe["rate"])
        is_full = item["condition_id"] == "m3_full"
        color = BLUE if is_full else ORANGE
        marker = "o" if item["authorization_regime"] == "auto_compiled" else "s"
        group_key = (round(x, 8), round(y, 8), color, marker)
        point_groups.setdefault(group_key, []).append(str(index + 1))
        key_lines.append(
            (str(index + 1), _label(item["condition_id"], item["authorization_regime"]))
        )
    for (x, y, color, marker), numbers in point_groups.items():
        ax.scatter(
            x,
            y,
            s=80 + 30 * (len(numbers) - 1),
            color=color,
            marker=marker,
            edgecolor=INK,
            linewidth=0.6,
            zorder=3,
        )
        ax.annotate(
            "/".join(numbers),
            (x, y),
            xytext=(0, 0),
            textcoords="offset points",
            ha="center",
            va="center",
            color="white",
            fontsize=6.2 if len(numbers) > 1 else 7,
            fontweight="bold",
        )
    ax.set_xlabel("Benign-tool task completion rate (%) →")
    ax.set_ylabel("Attack safety: 1 − unsafe-effect rate (%) →")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    ax.spines[["top", "right"]].set_visible(False)
    for row, (number, label) in enumerate(key_lines):
        ax.text(
            1.02,
            0.93 - row * 0.065,
            f"{number}  {label}",
            transform=ax.transAxes,
            ha="left",
            va="center",
            fontsize=8.5,
        )
    ax.text(
        1.02,
        0.99,
        "Condition key",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        fontweight="bold",
    )
    fig.subplots_adjust(top=0.87, right=0.75)
    return _save(fig, output_dir, "figure_2_safety_utility_pareto")


def _forest_rows(
    analysis: Mapping[str, Any],
) -> list[tuple[str, str, Mapping[str, Any]]]:
    rows: list[tuple[str, str, Mapping[str, Any]]] = []
    for endpoint, values in analysis["deepseek"]["comparisons"].items():
        for name, value in values.items():
            rows.append((endpoint, name, value))
    for regime, endpoints in analysis["deepseek"]["regime_extension"].items():
        rows.append(
            ("unsafe_effect", f"full_auto_to_{regime}", endpoints["unsafe_effect"])
        )
        rows.append(
            ("task_completion", f"full_auto_to_{regime}", endpoints["benign_tool_tcr"])
        )
    return rows


def figure_forest(analysis: Mapping[str, Any], output_dir: Path) -> list[str]:
    rows = _forest_rows(analysis)
    fig, ax = plt.subplots(figsize=(10.4, max(6.0, 0.43 * len(rows) + 1.8)))
    fig.suptitle(
        "Paired effects of authorization regime and Guard configuration",
        y=0.985,
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.19,
        0.94,
        "Difference is second minus first; task-cluster bootstrap 95% CI",
        color=MUTED,
        fontsize=9,
    )
    for y, (endpoint, name, value) in enumerate(reversed(rows)):
        diff = 100 * value["absolute_difference_second_minus_first"]
        low = 100 * value["cluster_bootstrap"]["ci_low"]
        high = 100 * value["cluster_bootstrap"]["ci_high"]
        color = ORANGE if endpoint == "unsafe_effect" else BLUE
        ax.errorbar(
            diff,
            y,
            xerr=[[diff - low], [high - diff]],
            fmt="o",
            color=color,
            ecolor=color,
            capsize=3,
            markersize=5,
        )
        endpoint_label = "Unsafe" if endpoint == "unsafe_effect" else "TCR"
        label = f"{endpoint_label} · {name.replace('_', ' ')}"
        ax.text(
            -0.01,
            y,
            label,
            transform=ax.get_yaxis_transform(),
            ha="right",
            va="center",
            fontsize=8.5,
        )
    ax.axvline(0, color=INK, lw=1.0)
    ax.set_yticks([])
    ax.set_xlabel("Absolute difference (percentage points)")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(
        handles=[
            Line2D([0], [0], marker="o", color=ORANGE, label="Attack unsafe effect"),
            Line2D([0], [0], marker="o", color=BLUE, label="Benign-tool completion"),
        ],
        frameon=False,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
    )
    fig.subplots_adjust(top=0.91, left=0.24, right=0.76)
    return _save(fig, output_dir, "figure_3_authorization_forest")


def figure_burden(analysis: Mapping[str, Any], output_dir: Path) -> list[str]:
    burden = analysis["deepseek"]["burden"]
    labels = [_label(*(key.split("__", 1))) for key in burden]
    metrics = {
        "Records with ASK (%)": [
            100 * burden[key]["ask_record_rate"] for key in burden
        ],
        "Records with DENY (%)": [
            100 * burden[key]["deny_record_rate"] for key in burden
        ],
        "Failure rate (%)": [100 * burden[key]["failure_rate"] for key in burden],
        "p95 latency (s)": [burden[key]["latency_p95_ms"] / 1000 for key in burden],
    }
    fig, axes = plt.subplots(2, 2, figsize=(12, max(7.0, 0.45 * len(labels) + 4.0)))
    fig.suptitle(
        "Runtime confirmation, blocking, failure, and latency burden",
        fontsize=14,
        fontweight="bold",
    )
    for ax, (title, values) in zip(axes.flat, metrics.items(), strict=True):
        positions = list(range(len(labels)))
        colors = [BLUE if label.startswith("M3-full") else ORANGE for label in labels]
        ax.barh(positions, values, color=colors, edgecolor=INK, linewidth=0.5)
        ax.set_title(title, loc="left")
        ax.set_yticks(
            positions,
            labels if ax in (axes[0, 0], axes[1, 0]) else [""] * len(labels),
            fontsize=8,
        )
        ax.invert_yaxis()
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x")
        ax.grid(axis="y", visible=False)
    fig.text(
        0.5,
        0.01,
        "DeepSeek V4 Pro; ASK/DENY rates count records with at least one event; "
        "all rates use terminal ITT denominators",
        ha="center",
        color=MUTED,
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.035, 1, 0.96))
    return _save(fig, output_dir, "figure_4_runtime_burden")


def figure_adaptive(existing: Mapping[str, Any], output_dir: Path) -> list[str]:
    adaptive = existing["adaptive_deepseek_v4_pro"]
    first_success = sorted(
        int(value) for value in adaptive["first_success_queries"].values()
    )
    denominator = int(adaptive["budget_200"]["total"])
    x = list(range(0, 201))
    y = [
        100 * sum(query <= budget for query in first_success) / denominator
        for budget in x
    ]
    fig, ax = plt.subplots(figsize=(8.8, 5.5))
    fig.suptitle(
        "Adaptive first-success curve at budgets 50 and 200",
        y=0.98,
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.12,
        0.925,
        f"DeepSeek V4 Pro; denominator = {denominator} tasks; no saturation claim",
        color=MUTED,
        fontsize=9,
    )
    ax.step(x, y, where="post", color=BLUE, lw=2.1)
    for budget, key in ((50, "budget_50"), (200, "budget_200")):
        value = adaptive[key]
        ax.scatter(
            [budget], [100 * value["rate"]], color=ORANGE, edgecolor=INK, zorder=3
        )
        ax.annotate(
            f"{value['successes']}/{value['total']} ({100 * value['rate']:.1f}%)",
            (budget, 100 * value["rate"]),
            xytext=(-6, 9),
            textcoords="offset points",
            ha="right",
            fontsize=9,
        )
        ax.axvline(budget, color=NEUTRAL, lw=0.8, ls="--")
    ax.set_xlim(0, 200)
    ax.set_ylim(0, max(50, 100 * adaptive["budget_200"]["ci_high"] + 5))
    ax.set_xlabel("Adaptive query budget")
    ax.set_ylabel("Tasks with first unsafe effect (%)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.subplots_adjust(top=0.87)
    return _save(fig, output_dir, "figure_5_adaptive_first_success")


def build_figures(
    *,
    authorization_analysis: Path = DEFAULT_AUTHORIZATION_ANALYSIS,
    existing_analysis: Path = DEFAULT_EXISTING_ANALYSIS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    _style()
    authorization = _load(authorization_analysis)
    existing = _load(existing_analysis)
    outputs = {
        "figure_1": figure_field_isolation(output_dir),
        "figure_2": figure_pareto(authorization, output_dir),
        "figure_3": figure_forest(authorization, output_dir),
        "figure_4": figure_burden(authorization, output_dir),
        "figure_5": figure_adaptive(existing, output_dir),
    }
    return {
        "chart_contracts": list(CHART_CONTRACTS),
        "outputs": outputs,
        "renderer": "matplotlib-static-png-svg-pdf",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authorization-analysis", type=Path, default=DEFAULT_AUTHORIZATION_ANALYSIS
    )
    parser.add_argument(
        "--existing-analysis", type=Path, default=DEFAULT_EXISTING_ANALYSIS
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = build_figures(
        authorization_analysis=args.authorization_analysis,
        existing_analysis=args.existing_analysis,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
