"""从已缓存的实验分析结果中绘制手稿图表（严禁执行统计重放或就地估算）。

严格基于固化缓存中的观察值与 Wilson 置信区间绘制高质量科研图表，
确保图表呈现的数据与最终审计分析数据 100% 绝对一致。
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import font_manager, pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/experiments/research_followup_20261006_v1/manuscript_figures"
BENCHMARKS = ("agentdojo-v1", "m3-v2")
MODULES = ("m3_policy_only", "m3_full_normal_prompt")
CONDITIONS = ("no_defense", *MODULES, "strongest_peer_reviewed_structural_baseline")
LABELS = ("ND", "Policy", "Full", "VIGIL*")
WIDTH = 175 / 25.4
BLUE, ORANGE, GRAY = "#2878A5", "#BA642D", "#656565"
FIGURE_FILES = (
    (1, "current_01_boundaries", "Authorization, execution and scoring boundaries"),
    (2, "current_02_authorization", "Authorization and benign task completion"),
    (3, "current_03_calibration", "Contemporaneous security and utility"),
    (4, "current_04_restrictions", "Observed restrictions and final task states"),
)


class CurrentFigureError(ValueError):
    """当缓存数据不全或无法支持所声明图表时抛出的专用异常类。"""


def unique(rows: list[dict], fields: tuple[str, ...]) -> dict:
    indexed = {}
    for row in rows:
        key = tuple(row[field] for field in fields)
        if key in indexed:
            raise CurrentFigureError(f"Duplicate cached cell: {key}")
        indexed[key] = row
    return indexed


def endpoint_values(endpoint: dict) -> tuple[float, float, float]:
    """提取观察值率及缓存的 95% Wilson 置信区间端点；严禁对未知值插值推断。"""
    x, known, planned, unknown = (
        endpoint[key] for key in ("true", "observed", "planned", "unknown")
    )
    if not 0 <= x <= known or known + unknown != planned or known <= 0:
        raise CurrentFigureError("Inconsistent or unobserved endpoint denominators")
    value = endpoint["observed_rate"]
    lower, upper = endpoint["observed_wilson_95"]
    if not all(math.isfinite(v) for v in (value, lower, upper)):
        raise CurrentFigureError("Non-finite cached endpoint")
    if not 0 <= lower <= value <= upper <= 1 or not math.isclose(value, x / known):
        raise CurrentFigureError("Inconsistent cached endpoint interval or rate")
    return value * 100, lower * 100, upper * 100


def load_evidence(root: Path = ROOT) -> dict:
    paths = {
        "authorization": "outputs/experiments/claude_revision_v1/analysis.json",
        "calibration": "outputs/experiments/research_followup_20261006_v1/calibration/analysis.json",
        "diagnosis": "outputs/experiments/research_followup_20261006_v1/diagnosis/analysis.json",
    }
    caches = {
        name: json.loads((root / path).read_text(encoding="utf-8"))
        for name, path in paths.items()
    }
    auth, calibration, diagnosis = (caches[key] for key in paths)
    if (auth["authorization_recorded"], auth["synthetic_recorded"]) != (900, 16):
        raise CurrentFigureError("Authorization cohort is not 900 plus 16 controls")
    if (calibration["planned"], calibration["recorded"]) != (480, 480):
        raise CurrentFigureError("Calibration cohort is not 480 terminal records")
    if (diagnosis["source_rows"], diagnosis["main_benign_rows"]) != (900, 240):
        raise CurrentFigureError("Diagnosis does not cover the current benign cells")
    auth_cells = unique(auth["cells"], (
        "benchmark", "evaluation_case_type", "condition_id", "authorization_regime",
    ))
    calibration_cells = unique(calibration["cells"], (
        "benchmark", "evaluation_case_type", "condition_id",
    ))
    contrasts = unique(auth["comparisons"], ("benchmark", "endpoint", "comparison"))
    diagnostic_cells = unique(diagnosis["cells"], ("benchmark", "condition", "regime"))
    selected = {"authorization": [], "contrasts": [], "calibration": [], "diagnosis": []}
    for benchmark in BENCHMARKS:
        for module in MODULES:
            for regime in ("auto_compiled", "exact_target_v2"):
                cell = auth_cells[(benchmark, "benign_tool", module, regime)]
                endpoint_values(cell["completion"])
                if cell["planned"] != 30:
                    raise CurrentFigureError("Expected 30 benign tasks in each cell")
                selected["authorization"].append(cell)
                diagnostic = diagnostic_cells[(benchmark, module, regime)]
                if diagnostic["rows"] != 30 or any(
                    sum(diagnostic[field].values()) != 30
                    for field in ("first_blocks", "final_states")
                ):
                    raise CurrentFigureError("Diagnostic categories do not sum to 30")
                selected["diagnosis"].append(diagnostic)
            comparison = "policy_exact_minus_auto" if module == MODULES[0] else "full_exact_minus_auto"
            contrast = contrasts[(benchmark, "task_completion", comparison)]
            if (contrast["known_pairs"], contrast["unknown_pairs"]) != (30, 0):
                raise CurrentFigureError("Authorization contrast is not 30 complete pairs")
            interval = contrast["paired_interval"]
            if not -1 <= interval["ci_low"] <= interval["estimate"] <= interval["ci_high"] <= 1:
                raise CurrentFigureError("Invalid cached paired interval")
            selected["contrasts"].append(contrast)
        for condition in CONDITIONS:
            attack = calibration_cells[(benchmark, "attack", condition)]
            benign = calibration_cells[(benchmark, "benign_tool", condition)]
            endpoint_values(attack["unsafe"])
            endpoint_values(benign["completion"])
            selected["calibration"].append((attack, benign))
    return selected


def style() -> dict:
    for weight in ("normal", "bold"):
        path = font_manager.findfont(
            font_manager.FontProperties(family="Times New Roman", weight=weight),
            fallback_to_default=False,
        )
        if font_manager.FontProperties(fname=path).get_name() != "Times New Roman":
            raise CurrentFigureError("Times New Roman must resolve exactly")
    return {
        "font.family": "Times New Roman", "font.size": 9.5,
        "axes.titlesize": 10, "axes.labelsize": 9.5,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "legend.fontsize": 9, "pdf.fonttype": 42, "svg.fonttype": "none",
        "svg.hashsalt": "m3-current-evidence-v1",
        "axes.spines.right": False, "axes.spines.top": False,
        "axes.linewidth": 0.6, "legend.frameon": False,
    }


def label_panel(ax, letter: str) -> None:
    ax.annotate(letter, (0, 1), xycoords="axes fraction", xytext=(-12, 9),
                textcoords="offset points", weight="bold", fontsize=11)


def require_alignment(fig) -> None:
    """直接测量等网格最终坐标轴；不生成持久化的 QA 构件包。"""
    fig.canvas.draw()
    axes = [ax for ax in fig.axes if ax.axison]
    if len(axes) < 2:
        return
    boxes = [ax.get_position() for ax in axes]
    width_pt, height_pt = fig.get_size_inches() * 72
    if max(b.width for b in boxes) - min(b.width for b in boxes) > 1.5 / width_pt:
        raise CurrentFigureError("Unequal comparable plot widths")
    if max(b.height for b in boxes) - min(b.height for b in boxes) > 1.5 / height_pt:
        raise CurrentFigureError("Unequal comparable plot heights")
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if abs(a.y0 - b.y0) < 1.5 / height_pt and abs(a.y1 - b.y1) > 1.5 / height_pt:
                raise CurrentFigureError("Comparable row edges are misaligned")


def boundaries():
    fig, ax = plt.subplots(figsize=(WIDTH, 3.25))
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.12, top=0.99)
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    def box(x, y, text, color):
        ax.add_patch(FancyBboxPatch((x, y), 0.25, 0.18, boxstyle="round,pad=0.006",
                                   facecolor=color, edgecolor=GRAY, linewidth=0.7))
        ax.text(x + 0.125, y + 0.09, text, ha="center", va="center", fontsize=10)
    def arrow(start, end, *, dashed=False):
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=10,
                                    color=GRAY, linewidth=0.9,
                                    linestyle="--" if dashed else "-"))
    box(0.02, 0.74, "Trusted request\nand application scope", "#EDF2F5")
    box(0.37, 0.74, "Permission compiler\nExplicit policy", "#EDF2F5")
    box(0.72, 0.74, "Guard decision\nALLOW / ASK / DENY", "#DAEAF2")
    box(0.02, 0.36, "Offline scoring\nSafety + completion", "#F2F2F2")
    box(0.37, 0.36, "Model action proposal\nUntrusted context", "#F7ECE3")
    box(0.72, 0.36, "Isolated simulation\nExecution evidence", "#EDF2F5")
    arrow((0.28, 0.83), (0.36, 0.83))
    arrow((0.63, 0.83), (0.71, 0.83))
    arrow((0.61, 0.55), (0.75, 0.73))
    arrow((0.845, 0.73), (0.845, 0.55))
    ax.plot([0.845, 0.845, 0.145], [0.35, 0.25, 0.25], color=GRAY, linewidth=0.9)
    arrow((0.145, 0.25), (0.145, 0.35))
    arrow((0.25, 0.55), (0.43, 0.73), dashed=True)
    ax.text(0.05, 0.62, "Oracle-only\nderived targets", fontsize=9, color=ORANGE)
    fig.text(0.02, 0.06, "Raw evaluator fields stay outside model input; derived answer targets enter only the oracle Guard.", fontsize=9)
    fig.text(0.02, 0.012, "Permission, boundary rejection, execution, task completion and operational failure remain distinct.", fontsize=9)
    return fig


def authorization(data):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 3.65))
    fig.subplots_adjust(left=0.17, right=0.97, bottom=0.38, top=0.85, wspace=0.42)
    names = ["AgentDojo policy", "AgentDojo full", "M3-v2 policy", "M3-v2 full"]
    for group in range(4):
        for regime_index, (color, marker) in enumerate(((BLUE, "o"), (ORANGE, "s"))):
            cell = data["authorization"][group * 2 + regime_index]
            value, low, high = endpoint_values(cell["completion"])
            axes[0].errorbar(value, group + (regime_index - 0.5) * 0.22,
                            xerr=[[value - low], [high - value]], fmt=marker,
                            color=color, capsize=2, markersize=4)
        interval = data["contrasts"][group]["paired_interval"]
        value, low, high = (100 * interval[key] for key in ("estimate", "ci_low", "ci_high"))
        axes[1].errorbar(value, group, xerr=[[value - low], [high - value]],
                        fmt="o", color=BLUE, capsize=2, markersize=4)
    for i, ax in enumerate(axes):
        ax.set(yticks=range(4), ylim=(3.5, -0.5))
        ax.set_yticklabels(names if i == 0 else [])
        ax.grid(axis="x", alpha=0.18)
        label_panel(ax, "ab"[i])
    axes[0].set(xlim=(0, 100), xlabel="Observed task completion (%)", title="Benign tool tasks: 30 per cell")
    axes[1].set(xlim=(-45, 60), xlabel="Exact target − auto (pp)", title="Within-task authorization effect")
    axes[1].axvline(0, color=GRAY, linewidth=0.7, linestyle="--")
    fig.legend(handles=[Line2D([], [], marker="o", color=BLUE, label="Auto compiled"),
                        Line2D([], [], marker="s", color=ORANGE, label="Exact target (oracle)")],
               loc="lower center", bbox_to_anchor=(0.54, 0.12), ncol=2)
    fig.text(0.02, 0.05, "a: cached Wilson 95% intervals. b: cached paired Newcombe 95% intervals; 30 pairs per row.", fontsize=9)
    fig.text(0.02, 0.012, "Normal prompt in every cell. Oracle-derived scope is a contrast, not deployable authorization.", fontsize=9)
    return fig


def calibration(data):
    fig, axes = plt.subplots(2, 2, figsize=(WIDTH, 5.0))
    fig.subplots_adjust(left=0.10, right=0.90, bottom=0.25, top=0.83, hspace=1.0, wspace=0.55)
    for benchmark_index, benchmark in enumerate(BENCHMARKS):
        for metric_index, endpoint_key in enumerate(("unsafe", "completion")):
            ax = axes[benchmark_index, metric_index]
            for condition_index in range(4):
                pair = data["calibration"][benchmark_index * 4 + condition_index]
                endpoint = pair[metric_index][endpoint_key]
                value, low, high = endpoint_values(endpoint)
                color = GRAY if condition_index in (0, 3) else BLUE
                ax.errorbar(value, condition_index, xerr=[[value - low], [high - value]],
                            fmt=("o", "s", "D", "^")[condition_index], color=color,
                            capsize=2, markersize=4)
                if endpoint["unknown"]:
                    ax.plot([100 * endpoint["itt_lower"], 100 * endpoint["itt_upper"]],
                            [condition_index + 0.24] * 2, color=ORANGE, linewidth=2.5)
                ax.text(1.02, condition_index, f'{endpoint["true"]}/{endpoint["observed"]}',
                        transform=ax.get_yaxis_transform(), ha="left", va="center", fontsize=9)
            ax.set(xlim=(-2, 100), ylim=(3.6, -0.6), yticks=range(4),
                   xticks=(0, 25, 50, 75, 100), xlabel="Observed rate (%)")
            ax.set_yticklabels(LABELS)
            ax.grid(axis="x", alpha=0.18)
            title = "Benign task completion" if metric_index else (
                "Native attack success" if benchmark_index == 0 else "Simulated unsafe effect"
            )
            benchmark_title = "AgentDojo" if benchmark_index == 0 else "M3-v2 (internal)"
            ax.set_title(f"{benchmark_title}\n{title}", pad=9)
            label_panel(ax, "abcd"[benchmark_index * 2 + metric_index])
    fig.text(0.02, 0.13, "Points: observed fractions, cached Wilson 95% intervals; 30 planned tasks per condition and endpoint.", fontsize=9)
    fig.text(0.02, 0.085, "Orange segment: ITT identification range for unknown outcomes, not a confidence interval.", fontsize=9)
    fig.text(0.02, 0.04, "ND: no research Guard. VIGIL*: disclosed adaptation; 2 unknown AgentDojo outcomes per endpoint.", fontsize=9)
    return fig


FIRST = {
    "missing_tool_permission": ("Missing tool scope", "#377E9E"),
    "exact_target_or_sequence_restriction": ("Exact/sequence", "#B46B3F"),
    "source_order_dataflow_or_confirmation_restriction": ("Other Guard restriction", "#8A7299"),
    "invalid_model_proposal": ("Invalid proposal", "#848484"),
    "no_observed_block": ("No observed restriction", "#DBDBDB"),
}
FINAL = {
    "blocked_without_observed_execution": ("Blocked, no execution observed", "#377E9E"),
    "executed_actions_but_task_not_completed": ("Execution, task incomplete", "#B46B3F"),
    "no_completion_cause_in_public_events": ("Cause unresolved", "#848484"),
    "observed_task_completed": ("Task completed", "#7A9F83"),
}


def restrictions(data):
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 4.85))
    fig.subplots_adjust(left=0.23, right=0.97, bottom=0.43, top=0.87, wspace=0.20)
    names = []
    for benchmark in ("AgentDojo", "M3-v2"):
        names.extend(f"{benchmark} {module}/{regime}" for module in ("P", "F") for regime in ("A", "E"))
    for index, (field, categories) in enumerate((("first_blocks", FIRST), ("final_states", FINAL))):
        ax = axes[index]
        offsets = [0] * 8
        for key, (name, color) in categories.items():
            values = [cell[field].get(key, 0) for cell in data["diagnosis"]]
            ax.barh(range(8), values, left=offsets, color=color, height=0.60, label=name)
            offsets = [offset + value for offset, value in zip(offsets, values, strict=True)]
        if any(set(cell[field]) - set(categories) for cell in data["diagnosis"]):
            raise CurrentFigureError("Unrecognized diagnostic category")
        ax.set(xlim=(0, 30), ylim=(7.6, -0.6), yticks=range(8), xlabel="Tasks (30 per cell)")
        ax.set_yticklabels(names if index == 0 else [])
        ax.set_title(("First observed restriction", "Final observed state")[index], pad=9)
        label_panel(ax, "ab"[index])
        handles = [Patch(facecolor=color, label=name) for name, color in categories.values()]
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.07, -0.29), fontsize=9)
    fig.text(0.02, 0.035, "P/F: policy/full; A/E: auto/exact target. Descriptive event categories, not confirmed causal explanations.", fontsize=9)
    return fig


def build(root: Path = ROOT, output: Path = OUTPUT) -> list[Path]:
    data = load_evidence(root)
    outputs = []
    with plt.rc_context(style()):
        makers = (lambda _: boundaries(), authorization, calibration, restrictions)
        output.mkdir(parents=True, exist_ok=True)
        for (_, name, _), maker in zip(FIGURE_FILES, makers, strict=True):
            fig = maker(data)
            try:
                require_alignment(fig)
                for extension in ("pdf", "svg", "png"):
                    path = output / f"{name}.{extension}"
                    metadata = {"Date": None} if extension == "svg" else (
                        {"CreationDate": None, "ModDate": None} if extension == "pdf" else None
                    )
                    fig.savefig(path, dpi=300, metadata=metadata)
                    if extension == "svg":
                        path.write_text("\n".join(line.rstrip() for line in
                                                  path.read_text(encoding="utf-8").splitlines()) + "\n",
                                        encoding="utf-8")
                    outputs.append(path)
            finally:
                plt.close(fig)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    for path in build(output=args.output):
        print(path)


if __name__ == "__main__":
    main()
