"""Build the ten fixed paper-v1 figures from frozen CSV inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "protocols" / "paper_upgrade_v1" / "chart_contracts.json"
BLUE = "#2F5D8A"
ORANGE = "#D07A32"
GOLD = "#B89B3C"
OLIVE = "#75864B"
PINK = "#B7657B"
INK = "#25313C"
GRID = "#D9DEE3"
PALE = "#EEF2F5"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.labelcolor": INK,
            "axes.edgecolor": INK,
            "text.color": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def _finish(fig: Any, ax: Any, title: str, subtitle: str, *, demo: bool) -> None:
    ax.set_title(title, loc="left", pad=18)
    ax.text(0, 1.01, subtitle, transform=ax.transAxes, fontsize=8, color="#5F6B75", va="bottom")
    if demo:
        fig.text(
            0.99,
            0.01,
            "DEMO / NOT FORMAL EVIDENCE",
            ha="right",
            va="bottom",
            fontsize=8,
            color="#8A4A4A",
            weight="bold",
        )
    fig.tight_layout()


def _save(fig: Any, output: Path, name: str) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / f"{name}.png", output / f"{name}.svg"]
    fig.savefig(paths[0], dpi=180, bbox_inches="tight", facecolor="white")
    fig.savefig(paths[1], bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return paths


def _plot_architecture(_rows: list[dict[str, str]], output: Path, demo: bool) -> list[Path]:
    fig, ax = plt.subplots(figsize=(9.4, 5.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    def box(x: float, y: float, w: float, h: float, text: str, color: str, fill: str = "white") -> None:
        rect = plt.Rectangle((x, y), w, h, facecolor=fill, edgecolor=color, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.5, wrap=True)

    def arrow(x1: float, y1: float, x2: float, y2: float, color: str, label: str = "") -> None:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops={"arrowstyle": "->", "color": color, "lw": 1.4})
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, label, ha="center", fontsize=7, color=color)

    box(0.3, 4.35, 2.0, 0.8, "Trusted user request\n+ tool schemas", BLUE, "#EAF1F7")
    box(0.3, 1.0, 2.0, 1.05, "Untrusted document\ntool output / memory", ORANGE, "#FBF0E7")
    box(3.1, 4.35, 1.9, 0.8, "Policy compiler\n(no gold labels)", BLUE)
    box(3.1, 1.0, 1.9, 1.05, "Argument-level\nprovenance", ORANGE)
    box(5.8, 3.0, 1.9, 1.05, "Stateful monitor\nALLOW / ASK / DENY", INK, PALE)
    box(8.25, 4.45, 1.35, 0.65, "Mock tool\nexecution", OLIVE, "#F0F3E9")
    box(8.25, 3.0, 1.35, 0.65, "Independent\nconfirmation", GOLD, "#F8F3DF")
    box(8.25, 1.55, 1.35, 0.65, "Blocked +\naudited", ORANGE, "#FBF0E7")
    arrow(2.3, 4.75, 3.1, 4.75, BLUE)
    arrow(5.0, 4.75, 6.0, 4.0, BLUE, "permission envelope")
    arrow(2.3, 1.52, 3.1, 1.52, ORANGE)
    arrow(5.0, 1.52, 6.0, 3.2, ORANGE, "data + source")
    arrow(7.7, 3.82, 8.25, 4.78, OLIVE, "ALLOW")
    arrow(7.7, 3.58, 8.25, 3.42, GOLD, "ASK")
    arrow(7.7, 3.22, 8.25, 1.88, ORANGE, "DENY")
    ax.annotate(
        "",
        xy=(7.7, 3.30),
        xytext=(8.25, 3.18),
        arrowprops={"arrowstyle": "->", "color": GOLD, "lw": 1.4, "connectionstyle": "arc3,rad=-0.45"},
    )
    ax.text(7.95, 3.04, "approved policy v+1", ha="center", fontsize=7, color=GOLD)
    _finish(fig, ax, "M3 paper-v1 trust and data-flow architecture", "Authority flows in blue; untrusted data flows in orange; every side effect passes the stateful monitor.", demo=demo)
    return _save(fig, output, "F01_trust_dataflow_architecture")


def _plot_pareto(rows: list[dict[str, str]], output: Path, demo: bool) -> list[Path]:
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    for index, row in enumerate(rows):
        x = 1 - float(row["asr"])
        y = float(row["tcr"])
        color = BLUE if "M3" in row["defense"] else ORANGE
        marker = "o" if "M3" in row["defense"] else "s"
        ax.scatter(x, y, s=55, color=color, marker=marker, edgecolor=INK, linewidth=0.5, zorder=3)
        ax.annotate(row["defense"], (x, y), xytext=(4, 4 + index % 2 * 4), textcoords="offset points", fontsize=7)
    ax.set(xlim=(0, 1.02), ylim=(0, 1.02), xlabel="Safety = 1 - ASR", ylabel="Normal task completion rate")
    ax.grid(True, color=GRID, linewidth=0.7, alpha=0.7)
    _finish(fig, ax, "Safety-utility comparison", "Each point is one defense aggregated over the same frozen task/model cells; upper-right is preferred.", demo=demo)
    return _save(fig, output, "F02_safety_utility_pareto")


def _plot_adaptive(rows: list[dict[str, str]], output: Path, demo: bool) -> list[Path]:
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["defense"]].append(row)
    for index, (defense, values) in enumerate(sorted(grouped.items())):
        values.sort(key=lambda row: int(row["budget"]))
        ax.plot([int(row["budget"]) for row in values], [float(row["asr"]) for row in values], marker=("o", "s", "^")[index % 3], color=(BLUE, ORANGE, OLIVE)[index % 3], linewidth=1.8, label=defense)
    ax.set(xscale="log", xlabel="Black-box query budget (log scale)", ylabel="Adaptive ASR", ylim=(-0.02, 1.02))
    ax.set_xticks([100, 500, 2000], labels=["100", "500", "2,000"])
    ax.grid(True, color=GRID, linewidth=0.7, alpha=0.7)
    ax.legend(frameon=False, ncol=3, loc="upper left")
    _finish(fig, ax, "Adaptive attack success by query budget", "Discrete pre-registered budgets; ASR denominator is the same stratified 80-task panel.", demo=demo)
    return _save(fig, output, "F03_adaptive_budget_curve")


def _heatmap(rows: list[dict[str, str]], row_field: str, column_field: str, output: Path, name: str, title: str, subtitle: str, demo: bool) -> list[Path]:
    y_names = sorted({row[row_field] for row in rows})
    x_names = sorted({row[column_field] for row in rows})
    lookup = {(row[row_field], row[column_field]): float(row["asr"]) for row in rows}
    matrix = np.array([[lookup.get((y, x), np.nan) for x in x_names] for y in y_names])
    fig, ax = plt.subplots(figsize=(max(7.0, len(x_names) * 0.85), max(4.5, len(y_names) * 0.42)))
    image = ax.imshow(matrix, vmin=0, vmax=1, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(x_names)), labels=x_names, rotation=35, ha="right")
    ax.set_yticks(range(len(y_names)), labels=y_names)
    for i in range(len(y_names)):
        for j in range(len(x_names)):
            if not math.isnan(matrix[i, j]):
                ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=7, color="white" if matrix[i, j] > 0.55 else INK)
    fig.colorbar(image, ax=ax, label="ASR", fraction=0.03, pad=0.03)
    _finish(fig, ax, title, subtitle, demo=demo)
    return _save(fig, output, name)


def _plot_authorization(rows: list[dict[str, str]], output: Path, demo: bool) -> list[Path]:
    rows = sorted(rows, key=lambda row: float(row["authorization_accuracy"]), reverse=True)
    x = [float(row["authorization_accuracy"]) for row in rows]
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    for metric, color, marker in (("asr", ORANGE, "s"), ("tcr", BLUE, "o"), ("ask_rate", GOLD, "^")):
        ax.plot(x, [float(row[metric]) for row in rows], label=metric.upper(), color=color, marker=marker, linewidth=1.8)
    ax.invert_xaxis()
    ax.set(xlabel="Authorization accuracy (decreasing →)", ylabel="Rate", ylim=(-0.02, 1.02))
    ax.grid(True, color=GRID, linewidth=0.7, alpha=0.7)
    ax.legend(frameon=False, ncol=3)
    _finish(fig, ax, "Security and utility under authorization uncertainty", "Ordered policy regimes; identical model/task cells at each authorization accuracy level.", demo=demo)
    return _save(fig, output, "F06_authorization_uncertainty_curve")


def _plot_forest(rows: list[dict[str, str]], output: Path, demo: bool) -> list[Path]:
    rows = sorted(rows, key=lambda row: float(row["effect"]))
    labels = [row["component"] for row in rows]
    estimates = np.array([float(row["effect"]) for row in rows])
    lows = np.array([float(row["ci_low"]) for row in rows])
    highs = np.array([float(row["ci_high"]) for row in rows])
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(7.4, max(4.6, len(rows) * 0.48)))
    ax.errorbar(estimates, y, xerr=[estimates - lows, highs - estimates], fmt="o", color=BLUE, ecolor=INK, capsize=3)
    ax.axvline(0, color=INK, linewidth=1, linestyle="--")
    ax.set_yticks(y, labels=labels)
    ax.set_xlabel("Paired ASR difference when component is removed")
    ax.grid(axis="x", color=GRID, linewidth=0.7)
    _finish(fig, ax, "Component ablation effects", "Dots are paired point estimates; horizontal lines are template-clustered 95% confidence intervals.", demo=demo)
    return _save(fig, output, "F07_ablation_forest")


def _plot_ecdf(rows: list[dict[str, str]], output: Path, demo: bool) -> list[Path]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["defense"]].append(float(row["latency_ms"]))
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    for index, (defense, values) in enumerate(sorted(grouped.items())):
        values = sorted(values)
        y = np.arange(1, len(values) + 1) / len(values)
        ax.step(values, y, where="post", label=defense, color=(BLUE, ORANGE, OLIVE)[index % 3], linewidth=1.8, linestyle=("-", "--", "-.")[index % 3])
    ax.set(xlabel="End-to-end latency (ms)", ylabel="Empirical cumulative probability", ylim=(0, 1.02))
    ax.grid(True, color=GRID, linewidth=0.7, alpha=0.7)
    ax.legend(frameon=False)
    _finish(fig, ax, "End-to-end latency distributions", "Case-level ECDF; timeouts remain in the run denominator and are reported separately in the failure chart.", demo=demo)
    return _save(fig, output, "F08_latency_ecdf")


def _plot_failures(rows: list[dict[str, str]], output: Path, demo: bool) -> list[Path]:
    defenses = sorted({row["defense"] for row in rows})
    failure_types = ["unsafe_effect", "false_block", "ask", "parse_failure", "timeout"]
    lookup = {(row["defense"], row["failure_type"]): int(row["count"]) for row in rows}
    totals = {defense: sum(lookup.get((defense, kind), 0) for kind in failure_types) for defense in defenses}
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    bottom = np.zeros(len(defenses))
    colors = [ORANGE, PINK, GOLD, BLUE, OLIVE]
    for kind, color in zip(failure_types, colors):
        values = np.array([lookup.get((defense, kind), 0) / max(totals[defense], 1) for defense in defenses])
        ax.bar(defenses, values, bottom=bottom, label=kind.replace("_", " "), color=color, edgecolor="white", linewidth=0.5)
        bottom += values
    ax.set(ylabel="Share of recorded failures", ylim=(0, 1), xlabel="Defense")
    ax.tick_params(axis="x", rotation=25)
    ax.legend(frameon=False, ncol=1, loc="center left", bbox_to_anchor=(1.01, 0.5))
    _finish(fig, ax, "Failure type composition", "100% stacked within defense; absolute counts remain in the source table and manifest.", demo=demo)
    return _save(fig, output, "F09_failure_taxonomy")


def _plot_composition(rows: list[dict[str, str]], output: Path, demo: bool) -> list[Path]:
    labels = [row["sample_type"].replace("_", " ") for row in rows]
    counts = [int(row["count"]) for row in rows]
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    ax.pie(counts, labels=labels, autopct=lambda pct: f"{pct:.0f}%\n({round(pct / 100 * sum(counts))})", startangle=90, colors=[ORANGE, BLUE, OLIVE], wedgeprops={"edgecolor": "white", "linewidth": 1})
    _finish(fig, ax, "M3-v2 dataset composition", f"Total n={sum(counts):,}; attack and benign task categories are mutually exclusive.", demo=demo)
    return _save(fig, output, "F10_dataset_composition")


def _demo_tables() -> dict[str, list[dict[str, str]]]:
    rng = random.Random(20260718)
    defenses = ["No defense", "Safe prompt", "Spotlighting", "Task Shield", "Progent", "M3 policy", "M3 full"]
    models = ["Qwen-4B", "Phi-4-mini", "Llama-3B", "Gemma-4B", "Open-14B", "API-model"]
    main = [{"defense": defense, "asr": f"{max(0.01, 0.72 - i * 0.10):.3f}", "tcr": f"{0.96 - abs(i - 3) * 0.012:.3f}"} for i, defense in enumerate(defenses)]
    adaptive = [{"defense": defense, "budget": str(budget), "asr": f"{min(0.95, 0.05 + d * 0.07 + b * 0.08):.3f}"} for d, defense in enumerate(["Task Shield", "Progent", "M3 full"]) for b, budget in enumerate((100, 500, 2000))]
    model_defense = [{"model": model, "defense": defense, "asr": f"{max(0, min(1, 0.66 - j * 0.09 + rng.uniform(-0.06, 0.06))):.3f}"} for model in models for j, defense in enumerate(defenses)]
    families = ["direct", "rag", "multilingual", "json", "tool_output", "memory", "environment", "cross_tool", "obfuscation"]
    languages = ["zh", "en", "mixed", "pinyin", "traditional", "cross"]
    family_language = [{"attack_family": family, "language": language, "asr": f"{rng.uniform(0.02, 0.38):.3f}"} for family in families for language in languages]
    auth = [{"authorization_accuracy": str(value), "asr": f"{0.05 + (1-value)*0.50:.3f}", "tcr": f"{0.96 - (1-value)*0.12:.3f}", "ask_rate": f"{0.04 + (1-value)*0.52:.3f}"} for value in (1.0, 0.85, 0.7, 0.5, 0.25)]
    ablation = [{"component": name, "effect": str(effect), "ci_low": str(effect-0.025), "ci_high": str(effect+0.025)} for name, effect in (("provenance",0.11),("temporal",0.07),("confirmation",0.05),("dataflow",0.09),("keyword",0.005))]
    latency = [{"defense": defense, "latency_ms": f"{max(1, rng.gauss(mean, mean*0.18)):.2f}"} for defense, mean in (("No defense",780),("Progent",835),("M3 full",850)) for _ in range(160)]
    failures = [{"defense": defense, "failure_type": kind, "count": str(rng.randint(4, 45))} for defense in ("No defense", "Progent", "M3 full") for kind in ("unsafe_effect", "false_block", "ask", "parse_failure", "timeout")]
    composition = [{"sample_type":"attack","count":"900"},{"sample_type":"benign_no_tool","count":"300"},{"sample_type":"benign_legal_tool","count":"300"}]
    return {"main_results.csv": main, "adaptive_curve.csv": adaptive, "model_defense.csv": model_defense, "family_language.csv": family_language, "authorization_curve.csv": auth, "ablation.csv": ablation, "latency.csv": latency, "failure_types.csv": failures, "dataset_composition.csv": composition}


def build_figures(input_root: Path, output_root: Path, *, demo: bool = False) -> dict[str, Any]:
    _style()
    if demo:
        tables = _demo_tables()
        source_hashes = {name: "synthetic-demo" for name in tables}
    else:
        required = ["main_results.csv", "adaptive_curve.csv", "model_defense.csv", "family_language.csv", "authorization_curve.csv", "ablation.csv", "latency.csv", "failure_types.csv", "dataset_composition.csv"]
        missing = [name for name in required if not (input_root / name).is_file()]
        if missing:
            raise FileNotFoundError("missing frozen figure inputs: " + ", ".join(missing))
        tables = {name: _read_csv(input_root / name) for name in required}
        source_hashes = {name: _sha256(input_root / name) for name in required}
    artifacts: list[dict[str, Any]] = []

    builders: list[tuple[str, Callable[[], list[Path]]]] = [
        ("F01", lambda: _plot_architecture([], output_root, demo)),
        ("F02", lambda: _plot_pareto(tables["main_results.csv"], output_root, demo)),
        ("F03", lambda: _plot_adaptive(tables["adaptive_curve.csv"], output_root, demo)),
        ("F04", lambda: _heatmap(tables["model_defense.csv"], "model", "defense", output_root, "F04_model_defense_heatmap", "Model by defense ASR", "Cell values retain model-specific behavior; common 0-1 color scale.", demo)),
        ("F05", lambda: _heatmap(tables["family_language.csv"], "attack_family", "language", output_root, "F05_family_language_heatmap", "Attack family by language ASR", "Nine attack families by six language modes; common 0-1 color scale.", demo)),
        ("F06", lambda: _plot_authorization(tables["authorization_curve.csv"], output_root, demo)),
        ("F07", lambda: _plot_forest(tables["ablation.csv"], output_root, demo)),
        ("F08", lambda: _plot_ecdf(tables["latency.csv"], output_root, demo)),
        ("F09", lambda: _plot_failures(tables["failure_types.csv"], output_root, demo)),
        ("F10", lambda: _plot_composition(tables["dataset_composition.csv"], output_root, demo)),
    ]
    for figure_id, builder in builders:
        for path in builder():
            artifacts.append({"figure_id": figure_id, "path": _manifest_path(path), "sha256": _sha256(path), "bytes": path.stat().st_size})
    manifest = {"schema_version":"paper-figure-manifest-1.0","status":"demo_not_formal_evidence" if demo else "formal_frozen","contract_sha256":_sha256(CONTRACT_PATH),"source_hashes":source_hashes,"figure_count":10,"artifact_count":len(artifacts),"artifacts":artifacts}
    manifest_path = output_root / "figure_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=ROOT / "outputs" / "paper_upgrade_v1" / "analysis_frozen")
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs" / "paper_upgrade_v1" / "figures")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    output = args.output_root
    if args.demo and output == ROOT / "outputs" / "paper_upgrade_v1" / "figures":
        output = ROOT / "outputs" / "paper_upgrade_v1" / "figures_demo"
    manifest = build_figures(args.input_root, output, demo=args.demo)
    print(json.dumps({"status": manifest["status"], "figure_count": manifest["figure_count"], "artifact_count": manifest["artifact_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
