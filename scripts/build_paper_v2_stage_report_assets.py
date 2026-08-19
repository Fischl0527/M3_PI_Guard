"""Build bounded, non-scientific charts for the paper-v2 stage report."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "docs/research/paper_v2/reports"
ASSET_ROOT = REPORT_ROOT / "assets/stage_report_20260724"


def _font_name() -> str:
    candidates = (
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    )
    installed = {font.name for font in font_manager.fontManager.ttflist}
    return next(name for name in candidates if name in installed)


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": _font_name(),
            "axes.unicode_minus": False,
            "axes.edgecolor": "#CBD5E1",
            "axes.labelcolor": "#334155",
            "xtick.color": "#475569",
            "ytick.color": "#475569",
            "grid.color": "#E2E8F0",
            "grid.linewidth": 0.8,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def _save(fig: plt.Figure, name: str) -> None:
    fig.savefig(
        ASSET_ROOT / name,
        dpi=220,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)


def _version_progression(data: dict) -> None:
    versions = [item["version"] for item in data["versions"]]
    records = [item["records"] for item in data["versions"]]
    calls = [item["provider_calls"] for item in data["versions"]]
    costs = [item["cumulative_cost_cny"] for item in data["versions"]]
    x = np.arange(len(versions))
    width = 0.34
    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    bars_a = ax.bar(
        x - width / 2,
        records,
        width,
        label="已写入记录",
        color="#2563EB",
    )
    bars_b = ax.bar(
        x + width / 2,
        calls,
        width,
        label="官方响应",
        color="#93C5FD",
    )
    ax.set_ylabel("数量")
    ax.set_xticks(x, versions)
    ax.grid(axis="y", alpha=0.85)
    ax.set_title("DeepSeek 正式运行版本演进（科学结果未开放）", pad=14)
    ax.bar_label(bars_a, padding=3, fontsize=9)
    ax.bar_label(bars_b, padding=3, fontsize=9)
    ax2 = ax.twinx()
    ax2.plot(
        x,
        costs,
        color="#DC2626",
        marker="o",
        linewidth=2.2,
        label="累计成本（元）",
    )
    ax2.set_ylabel("累计成本（人民币元）", color="#991B1B")
    ax2.set_ylim(0, max(costs) * 1.28)
    for xi, cost in zip(x, costs, strict=True):
        ax2.annotate(
            f"¥{cost:.3f}",
            (xi, cost),
            xytext=(0, 9),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color="#991B1B",
        )
    handles, labels = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(
        handles + handles2,
        labels + labels2,
        loc="upper right",
        frameon=False,
        ncol=3,
    )
    fig.tight_layout()
    _save(fig, "figure_1_version_progression.png")


def _operational_composition(data: dict) -> None:
    rows = data["operational_composition"]
    versions = [item["version"] for item in rows]
    completed = np.array([item["completed"] for item in rows])
    terminal = np.array([item["terminal_failures"] for item in rows])
    open_items = np.array([item["open_attempts"] for item in rows])
    x = np.arange(len(versions))
    fig, ax = plt.subplots(figsize=(9.8, 5.2))
    ax.bar(x, completed, color="#16A34A", label="completed")
    ax.bar(
        x,
        terminal,
        bottom=completed,
        color="#F59E0B",
        label="终态运行失败",
    )
    ax.bar(
        x,
        open_items,
        bottom=completed + terminal,
        color="#DC2626",
        label="开放 attempt",
    )
    totals = completed + terminal + open_items
    for xi, total in zip(x, totals, strict=True):
        ax.text(xi, total + 4, str(int(total)), ha="center", fontsize=9)
    ax.set_xticks(x, versions)
    ax.set_ylabel("工作项")
    ax.set_title("v4–v6 技术终态构成", pad=14)
    ax.grid(axis="y")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    _save(fig, "figure_2_operational_composition.png")


def _readiness(data: dict) -> None:
    rows = data["readiness"]
    labels = [item["area"] for item in rows][::-1]
    values = [item["percent"] for item in rows][::-1]
    colors = [
        "#16A34A" if value >= 80 else "#2563EB" if value >= 50 else "#F59E0B"
        for value in values
    ]
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    bars = ax.barh(labels, values, color=colors)
    ax.set_xlim(0, 100)
    ax.set_xlabel("阶段完成度（工程就绪度，不代表论文结论）")
    ax.set_title("paper-v2 工作流就绪度", pad=14)
    ax.grid(axis="x")
    ax.bar_label(bars, labels=[f"{value}%" for value in values], padding=5)
    fig.tight_layout()
    _save(fig, "figure_3_readiness.png")


def _roadmap(data: dict) -> None:
    tasks = data["roadmap"]
    fig, ax = plt.subplots(figsize=(11.0, 6.5))
    y = np.arange(len(tasks))[::-1]
    palette = ["#2563EB", "#0EA5E9", "#14B8A6", "#22C55E", "#F59E0B"]
    for index, (yi, task) in enumerate(zip(y, tasks, strict=True)):
        ax.barh(
            yi,
            task["duration_weeks"],
            left=task["start_week"],
            height=0.58,
            color=palette[index % len(palette)],
        )
        ax.text(
            task["start_week"] + 0.12,
            yi,
            task["label"],
            va="center",
            ha="left",
            fontsize=9,
            color="white"
            if task["duration_weeks"] >= 1.2
            else "#0F172A",
            weight="bold",
        )
    ax.set_yticks(y, [task["phase"] for task in tasks])
    ax.set_xlabel("从恢复实验起的周数")
    ax.set_xlim(0, 8.5)
    ax.set_xticks(np.arange(0, 9, 1))
    ax.set_title("后续实验与投稿路线图", pad=14)
    ax.grid(axis="x")
    fig.tight_layout()
    _save(fig, "figure_4_roadmap.png")


def _evidence_chain() -> None:
    labels = [
        "冻结候选\nmanifest + hash",
        "六条件 canary\n技术门",
        "480 项矩阵\nappend-only",
        "结果准入\n技术审查",
        "统计与主张\nclaim gate",
    ]
    colors = ["#1D4ED8", "#2563EB", "#0284C7", "#059669", "#16A34A"]
    fig, ax = plt.subplots(figsize=(11.2, 3.2))
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, 3.2)
    ax.axis("off")
    for index, (label, color) in enumerate(zip(labels, colors, strict=True)):
        x = 0.25 + index * 2.2
        rect = plt.Rectangle(
            (x, 1.0),
            1.65,
            1.15,
            facecolor=color,
            edgecolor="none",
            linewidth=0,
        )
        ax.add_patch(rect)
        ax.text(
            x + 0.825,
            1.575,
            label,
            ha="center",
            va="center",
            color="white",
            fontsize=9.3,
            weight="bold",
        )
        if index < len(labels) - 1:
            ax.annotate(
                "",
                xy=(x + 2.05, 1.575),
                xytext=(x + 1.7, 1.575),
                arrowprops={"arrowstyle": "->", "color": "#64748B", "lw": 2},
            )
    ax.text(
        5.6,
        2.62,
        "结果不可见条件下先冻结规则；任何失败保留在 ITT 分母",
        ha="center",
        va="center",
        fontsize=11,
        color="#0F172A",
        weight="bold",
    )
    fig.tight_layout()
    _save(fig, "figure_5_evidence_chain.png")


def main() -> int:
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    _style()
    data = {
        "as_of": "2026-07-24",
        "versions": [
            {
                "version": "v4",
                "records": 395,
                "provider_calls": 773,
                "cumulative_cost_cny": 0.7445328,
                "status": "技术门阻断",
            },
            {
                "version": "v5",
                "records": 94,
                "provider_calls": 157,
                "cumulative_cost_cny": 0.8384096,
                "status": "中止/不可恢复",
            },
            {
                "version": "v6",
                "records": 64,
                "provider_calls": 112,
                "cumulative_cost_cny": 0.9066668,
                "status": "中止/不可恢复",
            },
            {
                "version": "v7",
                "records": 0,
                "provider_calls": 0,
                "cumulative_cost_cny": 0.9066668,
                "status": "候选已冻结，未审计完/未运行",
            },
        ],
        "operational_composition": [
            {
                "version": "v4",
                "completed": 356,
                "terminal_failures": 39,
                "open_attempts": 0,
            },
            {
                "version": "v5",
                "completed": 92,
                "terminal_failures": 2,
                "open_attempts": 1,
            },
            {
                "version": "v6",
                "completed": 61,
                "terminal_failures": 3,
                "open_attempts": 1,
            },
        ],
        "readiness": [
            {"area": "研究问题与止损门槛", "percent": 95},
            {"area": "2024–2026 文献矩阵", "percent": 90},
            {"area": "online-state 源码审计", "percent": 90},
            {"area": "DeepSeek 证据链基础设施", "percent": 88},
            {"area": "v7 全量离线审计", "percent": 55},
            {"area": "正式安全—效用结果", "percent": 0},
            {"area": "Gemini 跨模型泛化", "percent": 20},
            {"area": "公共基准与自适应攻击", "percent": 30},
            {"area": "独立盲测", "percent": 20},
            {"area": "论文写作与投稿包", "percent": 45},
        ],
        "roadmap": [
            {
                "phase": "P0",
                "label": "v7 离线审计与结果门 v4 冻结",
                "start_week": 0.0,
                "duration_weeks": 0.7,
            },
            {
                "phase": "P1",
                "label": "DeepSeek canary + 480 项矩阵",
                "start_week": 0.7,
                "duration_weeks": 1.0,
            },
            {
                "phase": "P2",
                "label": "技术准入、统计与主张门",
                "start_week": 1.7,
                "duration_weeks": 0.8,
            },
            {
                "phase": "P3",
                "label": "Gemini 泛化 + AgentDojo/SIREN",
                "start_week": 2.5,
                "duration_weeks": 2.0,
            },
            {
                "phase": "P4",
                "label": "自适应攻击与敏感性分析",
                "start_week": 4.5,
                "duration_weeks": 1.5,
            },
            {
                "phase": "P5",
                "label": "独立盲测",
                "start_week": 5.0,
                "duration_weeks": 2.0,
            },
            {
                "phase": "P6",
                "label": "论文定稿、审查与 JISA 投稿",
                "start_week": 6.0,
                "duration_weeks": 2.0,
            },
        ],
        "verification": {
            "last_complete_harness": {
                "tests_passed": 1049,
                "tests_skipped": 1,
                "warnings": 3,
                "verification_failed": 0,
                "scope": "pre-v6-continuation",
            },
            "v7_focused_tests_passed": 12,
            "v7_full_audit_status": "paused_by_owner_for_report",
        },
        "evidence_counts": {
            "literature_entries": 34,
            "online_state_audit_units": 22,
            "conditions": 6,
            "formal_work_items": 480,
            "primary_records": 432,
            "authorization_probes": 48,
        },
    }
    (ASSET_ROOT / "stage_report_data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _version_progression(data)
    _operational_composition(data)
    _readiness(data)
    _roadmap(data)
    _evidence_chain()
    print(
        json.dumps(
            {
                "status": "complete",
                "asset_root": str(ASSET_ROOT),
                "figures": 5,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
