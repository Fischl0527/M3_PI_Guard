"""Source-based Chinese figures for the research introduction; no model/statistical reruns."""

from __future__ import annotations
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from matplotlib.patches import FancyBboxPatch
from PIL import Image
import fitz

sys.path.insert(0, str(Path("C:/Users/gaohang/.agents/skills/nature-figure/scripts")))
from audit_panel_alignment import require_matplotlib_panel_alignment

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "harness/workspaces/research-introduction-20261014"
PIC = ROOT / "docs/picture"
VEC = PIC / "矢量版"
QA = WORK / "figure_qa"
for p in (VEC, QA):
    p.mkdir(parents=True, exist_ok=True)

font_path = Path("C:/Windows/Fonts/msyh.ttc")
fm.fontManager.addfont(str(font_path))
font_name = fm.FontProperties(fname=str(font_path)).get_name()
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "text.color": "#000000",
        "axes.labelcolor": "#000000",
        "axes.titlecolor": "#000000",
        "xtick.color": "#000000",
        "ytick.color": "#000000",
        "axes.edgecolor": "#000000",
        "axes.unicode_minus": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.7,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
    }
)
COLORS = ["#657F98", "#B7C6D2", "#C69B65", "#D3C2AB", "#82958B", "#B8C5BC", "#D9D9D9"]
data = json.loads((WORK / "research_data.json").read_text(encoding="utf-8"))
emp = data["empirical"]
v4 = data["v4"]
figures = []
rows = []


def cell(study, model, benchmark, cond, regime="auto_compiled", scope="all"):
    matches = [
        x
        for x in emp["cells"]
        if x["study"] == study
        and x["model"] == model
        and x["benchmark"] == benchmark
        and x["condition_id"] == cond
        and x["authorization_regime"] == regime
        and x["cohort_scope"] == scope
    ]
    assert len(matches) == 1, (
        study,
        model,
        benchmark,
        cond,
        regime,
        scope,
        len(matches),
    )
    return matches[0]


def save(fig, index, title, caption, source):
    # Direct value labels stay unobstructed: omit nonessential grid strokes.
    for aa in fig.axes:
        aa.grid(False)
    fig.canvas.draw()
    for txt in fig.findobj(matplotlib.text.Text):
        txt.set_color("#000000")
    stem = f"M3_{index:02d}_{title}"
    require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{stem}.alignment.json", strict=True
    )
    fig.savefig(PIC / f"{stem}.png", dpi=300)
    fig.savefig(VEC / f"{stem}.svg")
    fig.savefig(VEC / f"{stem}.pdf")
    plt.close(fig)
    figures.append(
        {
            "id": f"N{index:02d}",
            "title": title,
            "png": (PIC / f"{stem}.png").relative_to(ROOT).as_posix(),
            "pdf": (VEC / f"{stem}.pdf").relative_to(ROOT).as_posix(),
            "caption": caption,
            "source": source,
        }
    )


def setup(title, height=4.3, left=0.10, right=0.96, bottom=0.18, top=0.86):
    fig, ax = plt.subplots(figsize=(7.2, height))
    fig.subplots_adjust(left=left, right=right, bottom=bottom, top=top)
    fig.suptitle(title, x=0.5, y=0.965, fontsize=13, fontweight="bold", color="#000000")
    return fig, ax


def rowbar(ax, cells, ys, color, metric="completion", offset=0, height=0.29):
    vals = [x[metric]["observed_rate"] * 100 for x in cells]
    lo = [x[metric]["wilson_95"][0] * 100 for x in cells]
    hi = [x[metric]["wilson_95"][1] * 100 for x in cells]
    ax.barh(np.asarray(ys) + offset, vals, height, color=color, zorder=2)
    lower = np.array(vals) - lo
    upper = np.array(hi) - vals
    assert min(lower) >= -1e-9 and min(upper) >= -1e-9, (
        "Source interval does not contain its estimate"
    )
    ax.errorbar(
        vals,
        np.asarray(ys) + offset,
        xerr=[np.maximum(lower, 0), np.maximum(upper, 0)],
        fmt="none",
        ecolor="#000000",
        elinewidth=0.8,
        capsize=2,
        zorder=3,
    )
    for x, _lower_bound, h, y, c in zip(vals, lo, hi, np.asarray(ys) + offset, cells):
        q = c[metric]
        ax.text(
            min(h + 1.8, 105),
            y,
            f"{q['numerator']}/{q['observed_denominator']}",
            va="center",
            fontsize=9,
        )
        rows.append(
            {
                "figure_pending": len(figures) + 1,
                "group": f"{c['model']} / {c['benchmark']} / {c['condition_id']} / {c['authorization_regime']}",
                "metric": metric,
                "numerator": q["numerator"],
                "denominator": q["observed_denominator"],
                "unknown": q["unknown"],
                "estimate": q["observed_rate"],
                "source": "empirical_reinforcement_v1/analysis_v1.json",
            }
        )


# 01 System flow, with a separate untrusted-data input.
fig, ax = setup(
    "从可信任务到独立评分", 3.45, bottom=0.04, top=0.86, left=0.02, right=0.98
)
ax.set_xlim(0, 10)
ax.set_ylim(0, 3)
ax.axis("off")
labels = [
    ("可信任务", "用户请求与应用声明"),
    ("权限编译", "生成任务权限规则"),
    ("模型提案", "工具名称与参数"),
    ("Guard 检查", "ALLOW\nASK / DENY"),
    ("隔离执行", "效果与\n运行状态"),
    ("独立评分", "任务完成与危险结果"),
]
for i, (a, b) in enumerate(labels):
    x = 0.12 + i * 1.66
    ax.add_patch(
        FancyBboxPatch(
            (x, 1.32),
            1.45,
            0.86,
            boxstyle="round,pad=0.04",
            edgecolor="#657F98",
            facecolor="#EEF2F5",
            linewidth=0.9,
        )
    )
    ax.text(
        x + 0.725, 1.89, a, ha="center", va="center", fontsize=10, fontweight="bold"
    )
    ax.text(
        x + 0.725,
        1.57,
        b.replace("与", "与\n") if i in (0, 2, 5) else b,
        ha="center",
        va="center",
        fontsize=8.5,
    )
    if i < 5:
        ax.annotate(
            "",
            xy=(x + 1.62, 1.75),
            xytext=(x + 1.48, 1.75),
            arrowprops={"arrowstyle": "->", "lw": 1, "color": "#000000"},
        )
ax.text(4.17, 0.50, "网页、文档、工具返回等外部材料", ha="center", fontsize=10)
ax.annotate(
    "",
    xy=(4.17, 1.28),
    xytext=(4.17, 0.73),
    arrowprops={"arrowstyle": "->", "lw": 1, "linestyle": "--", "color": "#000000"},
)
ax.text(7.55, 0.50, "只有允许的动作进入执行路径", ha="center", fontsize=9)
save(
    fig,
    1,
    "系统执行流程",
    "模型生成动作提案，Guard根据可信规则判断，执行层与评价层分别记录结果。虚线表示外部材料进入模型上下文，不自动获得授权。",
    "当前中文项目手册第3章；correctness_runtime_v1 / live_condition_runtime",
)

# 02 Four explicit corrected compiler revisions.
fig, ax = setup(
    "权限编译链的四次演进", 3.65, bottom=0.05, top=0.87, left=0.02, right=0.98
)
ax.axis("off")
ax.set_xlim(0, 10)
ax.set_ylim(0, 3)
vs = [
    ("v1", "动作与资源对应", "有界词法解析\n完整规则匹配"),
    ("v2", "目标与内容分离", "精确目标约束\n内容参数可生成"),
    ("v3", "模型草稿与动态绑定", "任务契约草稿\n后端验证对象"),
    ("v4", "意图提取与程序物化", "模型提取意图\n程序生成规则"),
]
for i, (v, a, b) in enumerate(vs):
    x = 0.15 + i * 2.5
    ax.add_patch(
        FancyBboxPatch(
            (x, 0.55),
            2.14,
            1.75,
            boxstyle="round,pad=.04",
            edgecolor=COLORS[0],
            facecolor="#F0F3F5",
            linewidth=0.9,
        )
    )
    ax.text(x + 1.07, 2.02, v, ha="center", fontsize=16, fontweight="bold")
    ax.text(x + 1.07, 1.57, a, ha="center", fontsize=9.5, fontweight="bold")
    ax.text(x + 1.07, 1.02, b, ha="center", va="center", fontsize=10, linespacing=1.7)
    if i < 3:
        ax.annotate(
            "",
            xy=(x + 2.43, 1.43),
            xytext=(x + 2.22, 1.43),
            arrowprops={"arrowstyle": "->", "color": "#000000"},
        )
save(
    fig,
    2,
    "v1至v4版本演进",
    "版本指corrected权限编译链。v1/v2重点修正动作资源与参数语义；v3/v4探索自然语言任务契约及动态对象授权。",
    "m3_core/policy_compiler_corrected_v1.py 至 policy_compiler_corrected_v4.py",
)

# 03 Mutually exclusive condition-execution groups, not independent task counts.
fig, ax = setup(
    "论文主证据的条件执行组成", 3.7, bottom=0.08, top=0.88, left=0.04, right=0.96
)
ax.set_position([0.035, 0.13, 0.48, 0.72])
values = [720, 180, 480, 16]
names = ["授权主队列", "嵌套压力授权", "同期校准", "合成组件控制"]
wedges, _ = ax.pie(
    values,
    startangle=90,
    colors=COLORS[:4],
    radius=0.90,
    wedgeprops={"width": 0.28, "edgecolor": "white"},
)
ax.text(0, 0.07, "1,396", ha="center", fontsize=23, fontweight="bold")
ax.text(0, -0.20, "次条件执行", ha="center", fontsize=11)
fig.legend(
    wedges,
    [f"{n}  {v} 次" for n, v in zip(names, values)],
    loc="center left",
    bbox_to_anchor=(0.58, 0.50),
    fontsize=9.5,
)
save(
    fig,
    3,
    "论文主证据组成",
    "720+180构成900条授权研究；另有480条同期校准与16条合成控制。120校准案例嵌套于180案例；图中是执行组成，不是独立样本组成。",
    "manuscript_current_zh_v2.md 表1",
)

# 04/05 Updated reinforcement utility, all original cells and intervals.
methods = [
    ("no_defense", "auto_compiled", "无研究防护"),
    ("m3_policy_only", "auto_compiled", "Policy 自动授权"),
    ("m3_full_normal_prompt", "auto_compiled", "Full 自动授权"),
    ("m3_policy_only", "exact_target_v2", "Policy 精确目标"),
    ("m3_full_normal_prompt", "exact_target_v2", "Full 精确目标"),
]
for model, index, display, note in [
    ("pro", 4, "DeepSeek Pro", "AgentDojo 97任务；M3-v2 120任务"),
    ("flash", 5, "V4.1 Flash", "AgentDojo与M3-v2各60任务"),
]:
    fig, ax = setup(
        f"{display} 正常工具任务完成情况",
        4.7,
        left=0.27,
        right=0.86,
        bottom=0.18,
        top=0.86,
    )
    ys = np.arange(5)
    for bm, offset, col in [
        ("agentdojo-v1", -0.17, COLORS[0]),
        ("m3-v2", 0.17, COLORS[4]),
    ]:
        cs = [cell("utility", model, bm, c, r) for c, r, _ in methods]
        rowbar(ax, cs, ys, col, offset=offset)
    ax.set_yticks(ys, [x[2] for x in methods])
    ax.invert_yaxis()
    ax.set_xlim(0, 115)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("任务完成率（%）")
    ax.grid(axis="x", alpha=0.18, zorder=0)
    ax.set_axisbelow(True)
    from matplotlib.patches import Patch

    fig.legend(
        handles=[
            Patch(color=COLORS[0], label="AgentDojo"),
            Patch(color=COLORS[4], label="M3-v2"),
        ],
        loc="lower center",
        bbox_to_anchor=(0.57, 0.015),
        ncol=2,
        fontsize=10,
    )
    save(
        fig,
        index,
        f"{display}正常任务完成",
        f"强化实证研究；{note}。条形为已观察完成比例，横线为已有95% Wilson区间，标注为完成数/任务数。精确目标为离线目标对照。",
        "empirical_reinforcement_v1/analysis_v1.json cells / utility",
    )

# 06 Paired differences copied from the existing inference output.
fig, ax = setup(
    "增加精确目标信息后的配对完成差异",
    5.2,
    left=0.34,
    right=0.95,
    bottom=0.16,
    top=0.86,
)
selected = []
for model in ["pro", "flash"]:
    for bm in ["agentdojo-v1", "m3-v2"]:
        for cmp in ["policy_exact_minus_auto", "full_exact_minus_auto"]:
            cc = [
                c
                for c in emp["comparisons"]
                if c["study"] == "utility"
                and c["model"] == model
                and c["benchmark"] == bm
                and c["comparison"] == cmp
                and c.get("cohort_scope") == "all"
            ]
            assert len(cc) == 1
            selected.append(cc[0])
ys = np.arange(len(selected))
for y, c in zip(ys, selected):
    e = c["estimate"] * 100
    ci = c["paired_interval"]
    lo = ci["ci_low"] * 100
    hi = ci["ci_high"] * 100
    ax.barh(
        y,
        e,
        height=0.45,
        color=COLORS[0] if c["model"] == "pro" else COLORS[4],
        zorder=2,
    )
    ax.errorbar(
        e,
        y,
        xerr=[[e - lo], [hi - e]],
        fmt="none",
        ecolor="#000000",
        elinewidth=0.9,
        capsize=2,
        zorder=3,
    )
    ax.text(hi + 1, y, f"{e:+.1f}", va="center", fontsize=9)
labels = [
    f"{'Pro' if c['model'] == 'pro' else 'Flash'} / {'AgentDojo' if c['benchmark'] == 'agentdojo-v1' else 'M3-v2'} / {'Policy' if c['comparison'].startswith('policy') else 'Full'}"
    for c in selected
]
ax.set_yticks(ys, labels)
ax.invert_yaxis()
ax.axvline(0, color="#000000", lw=0.8)
ax.set_xlim(-30, 66)
ax.set_xlabel("精确目标减自动授权（百分点）")
ax.grid(axis="x", alpha=0.16)
save(
    fig,
    6,
    "授权信息的配对效应",
    "同一底层任务的完成差异及现有95%配对Newcombe区间。Pro的两项AgentDojo主比较通过预定Holm校正；Flash用于方向复核。直接读取既有统计，没有重新抽样。",
    "empirical_reinforcement_v1/analysis_v1.json comparisons / utility",
)

# 07 Attack activity and unknowns remain explicit.
fig, ax = setup(
    "Pro 在 AgentDojo 攻击任务上的观察",
    4.25,
    left=0.25,
    right=0.85,
    bottom=0.28,
    top=0.84,
)
conditions = [
    "no_defense",
    "strongest_peer_reviewed_structural_baseline",
    "m3_policy_only",
    "m3_full_normal_prompt",
]
cs = [cell("activity", "pro", "agentdojo-v1", c) for c in conditions]
rowbar(ax, cs, np.arange(4), COLORS[0], metric="unsafe", height=0.5)
ax.set_yticks(range(4), ["无研究防护", "VIGIL 适配配置", "Policy", "Full"])
ax.invert_yaxis()
ax.set_xlim(0, 64)
ax.set_xticks([0, 10, 20, 30, 40, 50])
ax.set_xlabel("原生攻击安全判定阳性比例（%）")
ax.grid(axis="x", alpha=0.16)
fig.text(
    0.27, 0.065, "VIGIL：36项已知，4项未知；全部40项的阳性界限为20%—30%。", fontsize=9
)
save(
    fig,
    7,
    "攻击活性与安全观察",
    "每条件计划40任务；比例和Wilson区间采用已知结果分母。无防护7/40，Policy/Full均0/40；对无防护的两项比较Holm后p=0.078125。VIGIL为指定适配配置。",
    "empirical_reinforcement_v1/analysis_v1.json cells / activity",
)

# 08 ASK incidence and completion are separate endpoints, not stacked parts.
fig, ax = setup(
    "自动授权中的确认负担与任务完成", 3.8, left=0.22, right=0.88, bottom=0.27, top=0.83
)
cs = [
    cell("utility", "pro", "agentdojo-v1", c)
    for c in ["m3_policy_only", "m3_full_normal_prompt"]
]
for y, c in enumerate(cs):
    for off, key, col in [(-0.18, "ask", COLORS[2]), (0.18, "complete", COLORS[0])]:
        num = c["ask_items"] if key == "ask" else c["completion"]["numerator"]
        n = c["planned"]
        v = num / n * 100
        ax.barh(y + off, v, height=0.30, color=col)
        ax.text(v + 1.5, y + off, f"{num}/{n}", va="center", fontsize=10)
ax.set_yticks([0, 1], ["Policy 自动授权", "Full 自动授权"])
ax.invert_yaxis()
ax.set_xlim(0, 112)
ax.set_xticks([0, 25, 50, 75, 100])
ax.set_xlabel("任务占比（%）")
ax.grid(axis="x", alpha=0.16)
fig.legend(
    handles=[
        Patch(color=COLORS[2], label="出现过 ASK"),
        Patch(color=COLORS[0], label="任务完成"),
    ],
    loc="lower center",
    bbox_to_anchor=(0.58, 0.01),
    ncol=2,
)
save(
    fig,
    8,
    "确认负担与任务完成",
    "Pro/AgentDojo，97个正常任务。ASK计数表示执行中出现过等待确认的任务；它与完成状态分别统计，不能相加解释为互斥类别。",
    "empirical_reinforcement_v1/analysis_v1.json utility/pro/agentdojo-v1",
)

# 09 Controlled mechanisms are counted as fixtures, not population success rates.
fig, ax = setup(
    "受控越权提案的模块判定差异", 3.9, left=0.20, right=0.90, bottom=0.20, top=0.84
)
families = ["source_authority", "order", "dataflow", "confirmation"]
family_names = ["来源权威", "执行顺序", "数据保密", "独立确认"]
for y, f in enumerate(families):
    for off, module, col in [(-0.17, "policy", COLORS[1]), (0.17, "full", COLORS[0])]:
        c = next(
            x
            for x in emp["mechanism"]["controlled_cells"]
            if x["family"] == f and x["module_factor"] == module
        )
        num = c["unauthorized_allowed"]
        n = c["unauthorized_proposals"]
        ax.barh(y + off, num, height=0.29, color=col)
        ax.text(num + 0.35, y + off, f"{num}/{n}", va="center", fontsize=10)
ax.set_yticks(range(4), family_names)
ax.invert_yaxis()
ax.set_xlim(0, 24)
ax.set_xticks([0, 5, 10, 15, 20])
ax.set_xlabel("受控越权提案被放行的数量")
ax.grid(axis="x", alpha=0.16)
fig.legend(
    handles=[
        Patch(color=COLORS[1], label="Policy"),
        Patch(color=COLORS[0], label="Full"),
    ],
    loc="lower center",
    bbox_to_anchor=(0.56, 0.01),
    ncol=2,
)
save(
    fig,
    9,
    "受控机制检查",
    "每类20个越权提案；另20个合法提案在两配置下均放行。全研究40基础夹具、160提案对、320次判定，80对决定改变。这里是固定受控夹具的计数。",
    "empirical_reinforcement_v1/analysis_v1.json mechanism.controlled_cells",
)

# 10 Mutually exclusive decision pairs in the captured natural first proposals.
fig, ax = setup(
    "真实首提案回放的判定组成", 3.65, bottom=0.06, top=0.88, left=0.03, right=0.97
)
ax.set_position([0.035, 0.13, 0.48, 0.72])
pairs = emp["mechanism"]["captured_decision_pairs"]
vals = [pairs["ASK->ASK"], pairs["ALLOW->ALLOW"], pairs["ASK->DENY"]]
wedges, _ = ax.pie(
    vals,
    startangle=90,
    colors=[COLORS[2], COLORS[0], COLORS[4]],
    radius=0.9,
    wedgeprops={"width": 0.30, "edgecolor": "white"},
)
ax.text(0, 0.06, "358", ha="center", fontsize=25, fontweight="bold")
ax.text(0, -0.20, "个首提案", ha="center", fontsize=11)
fig.legend(
    wedges,
    [f"ASK → ASK   {vals[0]}", f"ALLOW → ALLOW   {vals[1]}", f"ASK → DENY   {vals[2]}"],
    loc="center left",
    bbox_to_anchor=(0.58, 0.5),
    fontsize=9.5,
)
save(
    fig,
    10,
    "真实首提案回放",
    "457个可捕获条件项中获得358个首提案。Policy/Full有355对决定一致，3对由ASK变DENY；与受控夹具的判定变化分别解释。",
    "empirical_reinforcement_v1/analysis_v1.json mechanism.captured_decision_pairs",
)

# 11 Earlier v3 development: source-separated readiness counts.
fig, ax = setup(
    "v3 早期开发编译的来源分布", 3.8, left=0.23, right=0.90, bottom=0.27, top=0.84
)
names = ["AgentDojo", "M3-v2", "新复杂任务"]
ready = [1, 3, 0]
tot = [17, 11, 16]
ax.barh(range(3), tot, color="#E3E7EA", height=0.5, label="全部开发响应")
ax.barh(range(3), ready, color=COLORS[0], height=0.5, label="编译通过")
for y, n, r in zip(range(3), tot, ready):
    ax.text(n + 0.35, y, f"{r}/{n} 通过", va="center", fontsize=10)
ax.set_yticks(range(3), names)
ax.invert_yaxis()
ax.set_xlim(0, 23)
ax.set_xlabel("开发响应数量")
ax.set_xticks([0, 5, 10, 15, 20])
ax.grid(axis="x", alpha=0.16)
fig.legend(loc="lower center", bbox_to_anchor=(0.55, 0.01), ncol=2)
save(
    fig,
    11,
    "v3早期开发编译",
    "44次官方开发响应中4条编译通过、40条失败。来源分别为17/11/16任务；初始、v2、v3提示阶段分别记录，不把提示版本混作编译器版本。",
    "task_contract_compiler_v3_validation_v1/report.md 与 development_summary_v1.json",
)

# 12 Same 32 tasks, final compiler state, four strata of 16.
fig, ax = setup(
    "v3 与 v4 同期开发编译状态", 4.5, left=0.23, right=0.96, bottom=0.32, top=0.84
)
state_order = [
    "ready",
    "needs_clarification",
    "conflict",
    "ambiguous",
    "missing",
    "unsupported",
    "technical_invalid",
]
state_names = {
    "ready": "可运行",
    "needs_clarification": "需澄清",
    "conflict": "冲突",
    "ambiguous": "歧义",
    "missing": "缺失",
    "unsupported": "不支持",
    "technical_invalid": "技术格式错误",
}
groups = [
    ("debug", "v3"),
    ("qualification", "v3"),
    ("debug", "v4"),
    ("qualification", "v4"),
]
starts = np.zeros(4)
for st, col in zip(state_order, COLORS):
    nums = []
    for cohort, version in groups:
        entries = [
            c
            for c in v4["compilation"]
            if c["development_cohort"] == cohort and c["compiler_version"] == version
        ]
        nums.append(sum(c["statuses"].get(st, 0) for c in entries))
    ax.barh(range(4), nums, left=starts, color=col, height=0.55, label=state_names[st])
    for y, n, s in zip(range(4), nums, starts):
        if n:
            ax.text(s + n / 2, y, str(n), ha="center", va="center", fontsize=10)
    starts += nums
assert list(starts) == [16, 16, 16, 16]
ax.set_yticks(range(4), ["v3 调试组", "v3 资格组", "v4 调试组", "v4 资格组"])
ax.invert_yaxis()
ax.set_xlim(0, 16)
ax.set_xticks([0, 4, 8, 12, 16])
ax.set_xlabel("每组16个固定基础任务")
ax.grid(axis="x", alpha=0.14)
ax.set_axisbelow(True)
fig.legend(loc="lower center", bbox_to_anchor=(0.58, 0.015), ncol=4, fontsize=8.5)
save(
    fig,
    12,
    "v3与v4编译状态",
    "同一32任务的开发比较，分调试16与资格16。v3最终5/32可运行，v4为0/32；图为编译最终状态，不是端到端任务完成率。",
    "task_contract_compiler_v4_development_v1/analysis_v1.json compilation",
)

# 13 Planned execution coverage: recorded and explicitly not run are distinct.
fig, ax = setup(
    "v4 开发批次的执行计划覆盖", 3.65, bottom=0.06, top=0.88, left=0.03, right=0.97
)
ax.set_position([0.035, 0.13, 0.48, 0.72])
vals = [320, 20, 300]
names = ["Pro 实际记录", "Flash 实际前缀", "Flash 明确未执行"]
assert v4["coverage"]["planned"] == sum(vals)
wedges, _ = ax.pie(
    vals,
    startangle=90,
    colors=[COLORS[0], COLORS[4], "#DADADA"],
    radius=0.9,
    wedgeprops={"width": 0.30, "edgecolor": "white"},
)
ax.text(0, 0.06, "640", ha="center", fontsize=25, fontweight="bold")
ax.text(0, -0.20, "计划条件项", ha="center", fontsize=11)
fig.legend(
    wedges,
    [f"{n}  {v}" for n, v in zip(names, vals)],
    loc="center left",
    bbox_to_anchor=(0.58, 0.5),
    fontsize=9.5,
)
save(
    fig,
    13,
    "v4开发执行覆盖",
    "32任务×正常/攻击×五条件×两个执行模型。实际记录340项，Flash余300项明确未执行；任务记录包括编译失败/澄清等状态，不等于640次实际模型执行。",
    "task_contract_compiler_v4_development_v1/analysis_v1.json coverage；report.md",
)

# 14 Corrected-v1 historical normal-prompt AgentDojo slice.
fig, ax = setup(
    "v1 修复开发研究的 AgentDojo 子集",
    4.0,
    left=0.18,
    right=0.89,
    bottom=0.26,
    top=0.84,
)
methods_v1 = ["无研究防护", "Policy", "Full"]
y = np.arange(3)
for off, nums, n, col in [
    (-0.18, [6, 3, 3], 8, COLORS[0]),
    (0.18, [5, 2, 0], 12, COLORS[2]),
]:
    vals = [k / n * 100 for k in nums]
    ax.barh(y + off, vals, height=0.3, color=col)
    for yy, k, val in zip(y + off, nums, vals):
        ax.text(val + 1.5, yy, f"{k}/{n}", va="center", fontsize=10)
ax.set_yticks(y, methods_v1)
ax.invert_yaxis()
ax.set_xlim(0, 100)
ax.set_xlabel("对应子集中的观察比例（%）")
ax.grid(axis="x", alpha=0.16)
fig.legend(
    handles=[
        Patch(color=COLORS[0], label="良性任务完成"),
        Patch(color=COLORS[2], label="攻击安全判定阳性"),
    ],
    loc="lower center",
    bbox_to_anchor=(0.55, 0.01),
    ncol=2,
)
save(
    fig,
    14,
    "v1修复开发结果",
    "历史corrected-v1开发研究每模型48任务×六配置=288执行；本图取Pro/AgentDojo普通提示的8个良性与12个攻击任务，描述原始计数。",
    "manuscript_current_zh_v2.md corrected-v1开发研究段落；correctness_repair_v1/report.md",
)

# 15 Current corrected-v2 authorization slice from the manuscript.
fig, ax = setup(
    "v2 自动权限与精确目标对照", 4.2, left=0.27, right=0.87, bottom=0.26, top=0.84
)
labels = ["Policy 自动权限", "Policy 精确目标", "Full 自动权限", "Full 精确目标"]
ys = np.arange(4)
for off, nums, col in [
    (-0.17, [2, 13, 2, 11], COLORS[0]),
    (0.17, [16, 14, 17, 16], COLORS[4]),
]:
    vals = [n / 30 * 100 for n in nums]
    ax.barh(ys + off, vals, height=0.29, color=col)
    for y, n, v in zip(ys + off, nums, vals):
        ax.text(v + 1.5, y, f"{n}/30", va="center", fontsize=10)
ax.set_yticks(ys, labels)
ax.invert_yaxis()
ax.set_xlim(0, 80)
ax.set_xlabel("正常工具任务完成率（%）")
ax.grid(axis="x", alpha=0.16)
fig.legend(
    handles=[
        Patch(color=COLORS[0], label="AgentDojo"),
        Patch(color=COLORS[4], label="M3-v2"),
    ],
    loc="lower center",
    bbox_to_anchor=(0.57, 0.01),
    ncol=2,
)
save(
    fig,
    15,
    "v2权限制度对照",
    "900条修正版授权研究的良性工具子集，每单元30任务。AgentDojo精确目标较自动权限提高完成，M3-v2未呈现同样方向；图为描述性计数，配对区间见正文。",
    "manuscript_current_zh_v2.md 表2",
)

# Build readable PNG representatives without changing original copied figures.
seen = {}
gallery = []
render_dir = WORK / "history_rendered"
render_dir.mkdir(exist_ok=True)
for h in data["history"]:
    p = ROOT / h["representative_source"]
    digest = h["original_hashes"][h["representative_source"]]
    if digest in seen:
        h["same_as"] = seen[digest]
        continue
    seen[digest] = h["id"]
    if p.suffix == ".png":
        out = p
    else:
        doc = fitz.open(p)
        assert doc.page_count == 1, (p, doc.page_count)
        out = render_dir / f"{h['id']}.png"
        doc[0].get_pixmap(matrix=fitz.Matrix(2.2, 2.2), alpha=False).save(out)
        doc.close()
    h["render_png"] = out.relative_to(ROOT).as_posix()
    with Image.open(out) as im:
        h["width"], h["height"] = im.size
    gallery.append(h)
data["history_gallery"] = gallery
data["new_figures"] = sorted(figures, key=lambda x: x["id"])
data["history_unique_count"] = len(gallery)
(WORK / "research_data.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
)
(WORK / "new_figures.json").write_text(
    json.dumps(sorted(figures, key=lambda x: x["id"]), ensure_ascii=False, indent=2),
    encoding="utf-8",
)
with (WORK / "figure_source_values.csv").open(
    "w", encoding="utf-8-sig", newline=""
) as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
catalog = [
    "# M3 PI Guard 研究图表目录",
    "",
    "新绘图为300 dpi PNG，矢量版同时保存SVG与PDF。既有实验图按原来源保留；停用、预检和历史阶段分别标识。",
    "",
    "## 新绘图",
    "",
]
for x in sorted(figures, key=lambda x: x["id"]):
    catalog += [
        f"### {x['id']} {x['title']}",
        f"![{x['title']}](<{Path(x['png']).name}>)",
        x["caption"],
        f"数据来源：{x['source']}",
        "",
    ]
catalog += [
    "## 既有实验图表完整索引",
    "",
    "同一幅图的PNG/SVG/PDF作为一组；字节相同的图在Word画廊中合并展示，所有原路径副本均保留。",
    "",
]
for h in data["history"]:
    catalog += [f"### {h['id']} {h['status']}", f"来源：{h['source_stem']}"]
    if h.get("same_as"):
        catalog += [f"图像与 {h['same_as']} 相同。"]
    for name in h["files"]:
        rel = Path(name).relative_to("docs/picture").as_posix()
        catalog += [f"- [{Path(name).name}](<{rel}>)"]
    catalog += [""]
(PIC / "图表目录.md").write_text("\n".join(catalog), encoding="utf-8")
print(
    json.dumps(
        {
            "new_figures": len(figures),
            "history_groups": len(data["history"]),
            "history_unique": len(gallery),
            "png_main": len(list(PIC.glob("M3_*.png"))),
        },
        ensure_ascii=False,
    )
)
