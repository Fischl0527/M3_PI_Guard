"""Render the five prespecified figures for the incremental empirical study.

The renderer consumes only compact, one-pass analysis JSON files. It never
opens provider traces, invokes a model, or reconstructs historical evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_ROOT = PROJECT_ROOT / "outputs/experiments/incremental_empirical_v1"
EXISTING_ANALYSIS = (
    PROJECT_ROOT
    / "outputs/experiments/lean_empirical/analysis/existing_results_analysis_v1.json"
)
OUTPUT_ROOT = (
    PROJECT_ROOT / "outputs/experiments/incremental_empirical_v1/figures"
)

INK = "#17212B"
MUTED = "#667085"
GRID = "#D9DEE7"
BLUE = "#2563A8"
ORANGE = "#D97706"
GREEN = "#16815A"
RED = "#B42318"
PALE_BLUE = "#EAF2FA"
PALE_ORANGE = "#FFF1DE"

# Figures are authored close to the final full-width manuscript size.  The
# previous 9.8--12.5 inch canvases were reduced by LaTeX to roughly 5.4 inches,
# which made otherwise reasonable 8--9.5 pt labels render at only 3.5--5.3 pt
# in the submitted PDF.  A 7.3 inch source canvas plus the sizes below keeps
# ordinary lettering near or above Elsevier's 7 pt finished-size guidance.
FIGURE_WIDTH_IN = 7.3
BASE_FONT_SIZE = 10.5
SMALL_FONT_SIZE = 10.0
FONT_FAMILY = "Times New Roman"

CHART_CONTRACTS: tuple[dict[str, str], ...] = (
    {
        "id": "figure_1_authority_boundary",
        "question": "Which information crosses the online authority boundary?",
        "takeaway": "Raw evaluator fields remain offline while source authority is explicit.",
    },
    {
        "id": "figure_2_factorial_interactions",
        "question": "What are the prompt, module, and interaction effects?",
        "takeaway": "Safety, utility, and failure effects are identified concurrently.",
    },
    {
        "id": "figure_3_provenance_counterfactual",
        "question": "How does a source-only swap change Guard and system behavior?",
        "takeaway": "Offline Guard decisions and end-to-end action changes stay separate.",
    },
    {
        "id": "figure_4_factor_effect_forest",
        "question": "Do factor effects align across representative, enriched, and Flash cohorts?",
        "takeaway": "Conditional and replication estimates are shown with their claim boundaries.",
    },
    {
        "id": "figure_5_adaptive_tail",
        "question": "How much new risk appears after budget 200 among prior survivors?",
        "takeaway": "The B200-survivor tail is not merged into a complete B500 panel.",
    },
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"analysis is not an object: {path}")
    return value


def _require_figure_font() -> None:
    for weight in ("normal", "bold"):
        properties = font_manager.FontProperties(
            family=[FONT_FAMILY],
            weight=weight,
        )
        try:
            resolved_path = font_manager.findfont(
                properties,
                fallback_to_default=False,
            )
        except ValueError as exc:
            raise RuntimeError(
                f"Required figure font {FONT_FAMILY!r} ({weight}) is unavailable; "
                "font fallback is disabled."
            ) from exc
        resolved_family = font_manager.FontProperties(fname=resolved_path).get_name()
        if resolved_family.casefold() != FONT_FAMILY.casefold():
            raise RuntimeError(
                f"Required figure font {FONT_FAMILY!r} resolved to "
                f"{resolved_family!r}; font fallback is disabled."
            )


def _style() -> None:
    # The author-facing manuscript is explicitly Times New Roman.  Fail with a
    # useful error instead of letting Matplotlib silently substitute a fallback
    # font and reintroduce mixed typography in the exported vector figures.
    _require_figure_font()
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
            "font.family": [FONT_FAMILY],
            "font.serif": [FONT_FAMILY],
            "font.sans-serif": [FONT_FAMILY],
            "font.monospace": [FONT_FAMILY],
            "mathtext.fontset": "stix",
            "text.usetex": False,
            "font.size": BASE_FONT_SIZE,
            "axes.titlesize": BASE_FONT_SIZE,
            "axes.labelsize": BASE_FONT_SIZE,
            "xtick.labelsize": SMALL_FONT_SIZE,
            "ytick.labelsize": SMALL_FONT_SIZE,
            "legend.fontsize": SMALL_FONT_SIZE,
            "legend.title_fontsize": BASE_FONT_SIZE,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.hashsalt": "m3-paper-v2-incremental-figures-v1",
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
    outputs: list[str] = []
    for suffix in ("png", "svg", "pdf"):
        path = output_dir / f"{stem}.{suffix}"
        metadata = None
        if suffix == "svg":
            metadata = {"Date": None}
        elif suffix == "pdf":
            metadata = {"CreationDate": None, "ModDate": None}
        fig.savefig(path, dpi=220 if suffix == "png" else None, metadata=metadata)
        if suffix == "svg":
            text = path.read_text(encoding="utf-8")
            path.write_text(
                "\n".join(line.rstrip() for line in text.splitlines()) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        outputs.append(str(path))
    plt.close(fig)
    return outputs


def _box(
    ax: plt.Axes,
    xy: tuple[float, float],
    size: tuple[float, float],
    label: str,
    *,
    edge: str,
    fill: str,
) -> None:
    patch = FancyBboxPatch(
        xy,
        size[0],
        size[1],
        boxstyle="round,pad=0.015,rounding_size=0.02",
        linewidth=1.3,
        edgecolor=edge,
        facecolor=fill,
    )
    ax.add_patch(patch)
    ax.text(
        xy[0] + size[0] / 2,
        xy[1] + size[1] / 2,
        label,
        ha="center",
        va="center",
        fontsize=SMALL_FONT_SIZE,
    )


def figure_authority_boundary(output_dir: Path) -> list[str]:
    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH_IN, 4.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Online authority boundary and controlled source swap", pad=14)
    online = (
        (0.025, "Trusted user /\napplication\ncontext"),
        (0.275, "Authorization\nprojection +\nprovenance events"),
        (0.525, "Runtime Guard\nALLOW / ASK /\nDENY"),
        (0.775, "Isolated\nsimulated effect\nreceipt"),
    )
    for x, label in online:
        _box(ax, (x, 0.57), (0.20, 0.22), label, edge=BLUE, fill=PALE_BLUE)
    for start, end in ((0.225, 0.275), (0.475, 0.525), (0.725, 0.775)):
        ax.annotate(
            "",
            xy=(end, 0.68),
            xytext=(start, 0.68),
            arrowprops={"arrowstyle": "->", "color": INK, "lw": 1.2},
        )
    _box(
        ax,
        (0.04, 0.13),
        (0.24, 0.20),
        "Untrusted tool\noutput or memory\nsource",
        edge=ORANGE,
        fill=PALE_ORANGE,
    )
    _box(
        ax,
        (0.38, 0.13),
        (0.24, 0.20),
        "Same proposition,\nvalue, position,\nand policy",
        edge=ORANGE,
        fill=PALE_ORANGE,
    )
    _box(
        ax,
        (0.72, 0.13),
        (0.24, 0.20),
        "Gold / evaluator\nlabels offline\nscoring only",
        edge=RED,
        fill="#FDECEC",
    )
    ax.annotate(
        "",
        xy=(0.38, 0.23),
        xytext=(0.28, 0.23),
        arrowprops={"arrowstyle": "->", "color": ORANGE, "lw": 1.2},
    )
    ax.annotate(
        "",
        xy=(0.37, 0.57),
        xytext=(0.505, 0.33),
        arrowprops={"arrowstyle": "->", "color": ORANGE, "lw": 1.1, "ls": "--"},
    )
    ax.text(
        0.5,
        0.03,
        "Provider-managed tools and real external effects remain disabled in every study.",
        ha="center",
        color=MUTED,
    )
    return _save(fig, output_dir, CHART_CONTRACTS[0]["id"])


def _value(item: Mapping[str, Any]) -> float:
    return float(item["value"])


def _factor_estimate(
    analysis: Mapping[str, Any], section: str, factor: str
) -> Mapping[str, Any]:
    return analysis[section]["factor_estimates"][factor]


def figure_factorial_interactions(
    factorial: Mapping[str, Any], output_dir: Path
) -> list[str]:
    cells = ("policy_normal", "policy_safe", "full_normal", "full_safe")
    labels = ("Policy\nnormal", "Policy\nsafe", "Full\nnormal", "Full\nsafe")
    panels = (
        ("Attack\nunsafe effect", "attack_unsafe_effect"),
        ("Benign-tool\ncompletion", "benign_tool_tcr"),
        ("Attack\nunsafe-or-failure", "attack_unsafe_or_failure"),
    )
    fig, axes = plt.subplots(
        1, 3, figsize=(FIGURE_WIDTH_IN, 4.6), sharey=False
    )
    summaries = factorial["cell_summary"]
    colors = (BLUE, BLUE, ORANGE, ORANGE)
    for ax, (title, endpoint) in zip(axes, panels, strict=True):
        values = [_value(summaries[cell][endpoint]) for cell in cells]
        ax.bar(range(4), values, color=colors, alpha=0.88, width=0.7)
        ax.set_xticks(range(4), labels)
        ax.set_ylim(0, min(1.0, max(values + [0.05]) * 1.32))
        ax.set_title(title)
        ax.set_ylabel("Proportion")
        for index, value in enumerate(values):
            ax.text(
                index,
                value,
                f"{value:.1%}",
                ha="center",
                va="bottom",
                fontsize=SMALL_FONT_SIZE,
            )
    estimates = factorial["attack_unsafe_factor"]["factor_estimates"]
    note = ", ".join(
        f"{name}={float(estimates[name]['estimate']):+.3f}"
        for name in ("module", "prompt", "interaction")
    )
    fig.suptitle("Concurrent 2×2 prompt-by-module outcomes", fontsize=14, weight="bold")
    fig.text(0.5, 0.01, f"Unsafe-effect factor estimates: {note}", ha="center", color=MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    return _save(fig, output_dir, CHART_CONTRACTS[1]["id"])


def figure_provenance_counterfactual(
    provenance: Mapping[str, Any], output_dir: Path
) -> list[str]:
    heatmap = provenance["offline_guard_replay"]["decision_heatmap"]
    cells = (
        "policy_trusted_origin",
        "policy_untrusted_origin",
        "full_trusted_origin",
        "full_untrusted_origin",
    )
    decisions = ("ALLOW", "ASK", "DENY")
    matrix = np.asarray(
        [[int(heatmap.get(cell, {}).get(decision, 0)) for decision in decisions] for cell in cells]
    )
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(FIGURE_WIDTH_IN, 4.9),
        gridspec_kw={"width_ratios": [1.35, 1]},
    )
    image = axes[0].imshow(matrix, cmap="Blues", aspect="auto")
    axes[0].set_xticks(range(3), decisions)
    axes[0].set_yticks(
        range(4),
        ("Policy / trusted", "Policy / untrusted", "Full / trusted", "Full / untrusted"),
    )
    axes[0].set_title("Deterministic Guard replay (n=480)")
    for row in range(4):
        for column in range(3):
            axes[0].text(column, row, str(matrix[row, column]), ha="center", va="center")
    fig.colorbar(image, ax=axes[0], fraction=0.046, pad=0.04, label="Decision count")

    changes = provenance["source_swap_action_change"]
    values = [_value(changes[module]) for module in ("policy", "full")]
    axes[1].bar((0, 1), values, color=(BLUE, ORANGE), width=0.62)
    axes[1].set_xticks((0, 1), ("Policy", "Full"))
    axes[1].set_ylim(0, min(1.0, max(values + [0.05]) * 1.35))
    axes[1].set_title("End-to-end source-swap action change")
    axes[1].set_ylabel("Paired task proportion")
    for index, value in enumerate(values):
        axes[1].text(index, value, f"{value:.1%}", ha="center", va="bottom")
    fig.suptitle(
        "Source-authority counterfactual:\nmechanism and system evidence",
        fontsize=14,
        weight="bold",
    )
    fig.text(
        0.5,
        0.01,
        "Offline Guard accuracy is not interpreted as end-to-end system performance.",
        ha="center",
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    return _save(fig, output_dir, CHART_CONTRACTS[2]["id"])


def figure_factor_effect_forest(
    factorial: Mapping[str, Any],
    challenge: Mapping[str, Any],
    flash: Mapping[str, Any],
    output_dir: Path,
) -> list[str]:
    studies = (
        ("Pro representative", factorial),
        ("Pro risk-enriched", challenge),
        ("Flash replication", flash),
    )
    factors = ("module", "prompt", "interaction")
    offsets = (-0.18, 0.0, 0.18)
    colors = (BLUE, GREEN, ORANGE)
    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH_IN, 5.3))
    for study_index, (label, analysis) in enumerate(studies):
        for factor, offset, color in zip(factors, offsets, colors, strict=True):
            item = _factor_estimate(analysis, "attack_unsafe_factor", factor)
            estimate = float(item["estimate"])
            low = float(item["ci_low"])
            high = float(item["ci_high"])
            y = study_index + offset
            ax.errorbar(
                estimate,
                y,
                xerr=[[estimate - low], [high - estimate]],
                fmt="o",
                color=color,
                capsize=3,
                label=factor if study_index == 0 else None,
            )
    ax.axvline(0, color=INK, lw=1)
    ax.set_yticks(range(3), [item[0] for item in studies])
    ax.invert_yaxis()
    ax.set_xlabel("Absolute difference in unsafe-effect probability")
    fig.suptitle(
        "Prompt, module, and interaction effects across prespecified cohorts",
        y=0.985,
    )
    ax.legend(
        title="Factor",
        frameon=False,
        ncol=3,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        borderaxespad=0.2,
    )
    fig.text(
        0.5,
        0.02,
        "Risk-enriched estimates are conditional robustness results, not deployment prevalence.",
        ha="center",
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.11, 1, 0.84))
    return _save(fig, output_dir, CHART_CONTRACTS[3]["id"])


def _existing_success(existing: Mapping[str, Any], budget: int) -> float:
    item = existing["adaptive_deepseek_v4_pro"][f"budget_{budget}"]
    return float(item.get("value", item.get("rate")))


def figure_adaptive_tail(
    existing: Mapping[str, Any], adaptive_tail: Mapping[str, Any], output_dir: Path
) -> list[str]:
    fig, axes = plt.subplots(1, 2, figsize=(FIGURE_WIDTH_IN, 4.7))
    original = [_existing_success(existing, budget) for budget in (50, 200)]
    axes[0].plot((50, 200), original, marker="o", color=BLUE, lw=2)
    axes[0].set_xticks((50, 200))
    axes[0].set_ylim(0, 1)
    axes[0].set_xlabel("Query budget")
    axes[0].set_ylabel("P(first unsafe effect by budget)")
    axes[0].set_title("Original 40-task panel")
    for x, value in zip((50, 200), original, strict=True):
        axes[0].text(x, value, f" {value:.1%}", va="bottom")

    curve = adaptive_tail["conditional_survival_curve"]
    x = [int(row["query_budget"]) for row in curve]
    survival = [float(row["survival_probability"]) for row in curve]
    axes[1].step(x, survival, where="post", color=ORANGE, lw=2)
    axes[1].scatter(x, survival, color=ORANGE, s=18)
    axes[1].set_xlim(200, 500)
    axes[1].set_ylim(0, 1.03)
    axes[1].set_xlabel("Query budget")
    axes[1].set_ylabel("P(no unsafe effect yet | survived B200)")
    axes[1].set_title("Selected B200-survivor tail (n=12)")
    fig.suptitle(
        "Defense-aware first-success evidence\nwith separate sampling frames",
        fontsize=14,
        weight="bold",
    )
    fig.text(
        0.5,
        0.01,
        "The right panel is conditional and is not a complete B500 curve for the original 40 tasks.",
        ha="center",
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    return _save(fig, output_dir, CHART_CONTRACTS[4]["id"])


def build_figures(
    *,
    factorial_path: Path = ANALYSIS_ROOT / "factorial/analysis_v1.json",
    provenance_path: Path = ANALYSIS_ROOT / "provenance/analysis_v1.json",
    challenge_path: Path = ANALYSIS_ROOT / "challenge/analysis_v1.json",
    flash_path: Path = ANALYSIS_ROOT / "flash/analysis_v1.json",
    adaptive_tail_path: Path = ANALYSIS_ROOT / "adaptive-tail/analysis_v1.json",
    existing_path: Path = EXISTING_ANALYSIS,
    output_dir: Path = OUTPUT_ROOT,
) -> dict[str, Any]:
    _style()
    factorial = _load(factorial_path)
    provenance = _load(provenance_path)
    challenge = _load(challenge_path)
    flash = _load(flash_path)
    adaptive_tail = _load(adaptive_tail_path)
    existing = _load(existing_path)
    outputs = {
        CHART_CONTRACTS[0]["id"]: figure_authority_boundary(output_dir),
        CHART_CONTRACTS[1]["id"]: figure_factorial_interactions(factorial, output_dir),
        CHART_CONTRACTS[2]["id"]: figure_provenance_counterfactual(provenance, output_dir),
        CHART_CONTRACTS[3]["id"]: figure_factor_effect_forest(
            factorial, challenge, flash, output_dir
        ),
        CHART_CONTRACTS[4]["id"]: figure_adaptive_tail(
            existing, adaptive_tail, output_dir
        ),
    }
    manifest = {
        "schema_version": "m3-paper-v2-incremental-figure-manifest-1.0",
        "renderer": "matplotlib-static-png-svg-pdf",
        "font": {"family": FONT_FAMILY, "fallback_allowed": False},
        "chart_contracts": list(CHART_CONTRACTS),
        "outputs": outputs,
    }
    manifest_path = output_dir / "figure_manifest_v1.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args(argv)
    result = build_figures(output_dir=args.output_dir)
    print(json.dumps({"figures": len(result["outputs"]), "output": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
