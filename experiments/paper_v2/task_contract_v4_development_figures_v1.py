"""开发报告配对差图：真实计数、未知界限及区间同图，不作领先排名。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def render(output: Path) -> list[str]:
    """只读取一次性分析文件，不重采样、筛选结果或补造缺失。"""
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    result: Mapping[str, Any] = json.loads((output / "analysis_v1.json").read_text(encoding="utf-8"))
    mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
                         "font.size": 9, "axes.titlesize": 11, "axes.labelsize": 9,
                         "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 8,
                         "svg.fonttype": "none", "pdf.fonttype": 42,
                         "axes.spines.top": False, "axes.spines.right": False})
    destination = output / "figures"
    destination.mkdir(exist_ok=True)
    files = []
    # 无完整已观察新旧配对时，空forest不能支持效应结论；改画真实编译状态。
    if not any(row["observed_pairs"] for row in result["comparisons"]):
        counts = {}
        for row in result["compilation"]:
            key = row["development_cohort"], row["compiler_version"]
            cell = counts.setdefault(key, {})
            for status, number in row["statuses"].items():
                cell[status] = cell.get(status, 0)+number
        fig, ax = plt.subplots(figsize=(7.2047244, 3.9370079))  # 183×100毫米
        fig.subplots_adjust(left=.22, right=.97, top=.83, bottom=.36)
        groups = [("debug", "v3"), ("debug", "v4"), ("qualification", "v3"), ("qualification", "v4")]
        labels = [f"{cohort.capitalize()} / {version}" for cohort, version in groups]
        categories = [("Ready", {"ready"}, "#317F99"),
                      ("Clarification", {"ambiguous", "missing", "needs_clarification"}, "#C9CED2"),
                      ("Scope conflict", {"conflict"}, "#9AABBC"),
                      ("Unsupported", {"unsupported"}, "#C8AE90"),
                      ("Technical invalid", {"technical_invalid", "provider_failure", "response_failure"}, "#9F878C")]
        left = [0]*len(groups)
        for label, statuses, color in categories:
            width = [sum(counts.get(group, {}).get(status, 0) for status in statuses) for group in groups]
            ax.barh(range(len(groups)), width, left=left, color=color, height=.6, label=label)
            left = [a+b for a, b in zip(left, width)]
        if any(number != 16 for number in left):
            raise ValueError("compilation chart needs16 final statuses per cohort/version; unknown category not dropped")
        ax.set_yticks(range(len(groups)), labels)
        ax.invert_yaxis()
        ax.set_xlim(0, 16)
        ax.set_xticks([0, 4, 8, 12, 16])
        ax.set_xlabel("Fixed development tasks (16 in each group)")
        ax.set_title("Task-contract compilation status", pad=14)
        fig.legend(loc="lower center", bbox_to_anchor=(.5, .08), frameon=False, ncol=2)
        name = destination / "compilation_status"
        fig.savefig(f"{name}.svg")
        fig.savefig(f"{name}.pdf")
        fig.savefig(f"{name}.png", dpi=600)
        plt.close(fig)
        return [str(name.with_suffix("."+suffix)) for suffix in ("svg", "pdf", "png")]
    for cohort in ("debug", "qualification"):
        rows = [r for r in result["comparisons"] if r["development_cohort"] == cohort]
        # 183×170毫米，以英寸常量装配，避免静态工具把算式误读成183英寸。
        fig, ax = plt.subplots(figsize=(7.2047244, 6.6929134))
        fig.subplots_adjust(left=.43, right=.97, bottom=.18, top=.89)
        labels = []
        for index, row in enumerate(rows):
            model = "Pro" if row["model_key"] == "pro" else "V4.1 Flash"
            suite = "M3" if row["benchmark"] == "m3-v2" else "Complex"
            endpoint = "Completion" if row["endpoint"] == "task_completion" else "Unsafe"
            module = "Policy" if row["treatment"].endswith("policy") else "Full"
            labels.append(f"{model} / {suite} / {endpoint} / {module} ({row['observed_pairs']}/{row['planned_pairs']})")
            lower, upper = row["itt_difference_lower"], row["itt_difference_upper"]
            if lower is not None:
                ax.plot([100*lower, 100*upper], [index, index], color="#CBD1D8", lw=5, solid_capstyle="butt", zorder=1)
            if row["difference"] is not None:
                point = 100*row["difference"]
                interval = row["cluster_bootstrap95"] or row["conservative_wilson_difference95"]
                color = "#286C8F" if row["model_key"] == "pro" else "#A16A3D"
                if interval:
                    ax.plot([100*interval[0], 100*interval[1]], [index, index], color=color, lw=1.3, zorder=2)
                ax.scatter([point], [index], color=color, s=24, marker="o" if model == "Pro" else "s", zorder=3)
        ax.set_yticks(range(len(rows)), labels)
        ax.set_ylim(len(rows)-.35, -.65)
        ax.set_xlim(-105, 105)
        ax.set_xticks([-100, -50, 0, 50, 100])
        ax.axvline(0, color="#8A8F95", lw=.7, ls="--", zorder=0)
        ax.set_xlabel("v4 minus v3 (percentage points)")
        ax.tick_params(axis="y", length=0, pad=5)
        ax.set_title("Task-contract development: " + cohort, pad=14)
        legend = [Line2D([0], [0], color="#286C8F", marker="o", lw=1, label="Pro observed pairs"),
                  Line2D([0], [0], color="#A16A3D", marker="s", lw=1, label="Flash observed pairs"),
                  Line2D([0], [0], color="#CBD1D8", lw=5, label="Full-plan missing-outcome bounds")]
        fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(.5, .018), frameon=False, ncol=1)
        # 单图单坐标轴，没有跨面板对齐问题；正文仍列全计划与已观察分母。
        name = destination / ("paired_effects_" + cohort)
        fig.savefig(f"{name}.svg")
        fig.savefig(f"{name}.pdf")
        fig.savefig(f"{name}.png", dpi=600)
        files.extend(str(name.with_suffix("." + suffix)) for suffix in ("svg", "pdf", "png"))
        plt.close(fig)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(json.dumps(render(parser.parse_args().output), ensure_ascii=False))


if __name__ == "__main__":
    main()
