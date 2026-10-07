"""Render current paper tables from cached analyses; never recompute statistics."""

from __future__ import annotations

import json
from pathlib import Path


class EvidenceTableError(ValueError):
    """Cached evidence cannot support the requested table."""


def _unique(rows: list[dict], fields: tuple[str, ...]) -> dict:
    result = {}
    for row in rows:
        key = tuple(row[field] for field in fields)
        if key in result:
            raise EvidenceTableError(f"Duplicate cached cell: {key}")
        result[key] = row
    return result


def _fraction(endpoint: dict) -> str:
    x, observed, planned, unknown = (
        endpoint[field] for field in ("true", "observed", "planned", "unknown")
    )
    if not 0 <= x <= observed or observed + unknown != planned:
        raise EvidenceTableError("Inconsistent cached endpoint denominators")
    fraction = f"{x}/{observed}"
    ci = endpoint["observed_wilson_95"]
    if ci is not None:
        fraction += f" [{100 * ci[0]:.2f}, {100 * ci[1]:.2f}]"
    return fraction


def _markdown(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        if len(row) != len(headers):
            raise EvidenceTableError("Table row width differs from header")
        lines.append(
            "| " + " | ".join(str(cell).replace("|", r"\|") for cell in row) + " |"
        )
    return "\n".join(lines)


def current_tables(
    project_root: Path, *, chinese: bool = False
) -> list[tuple[int, str, str, str]]:
    """Return number, title, table, note using identical evidence in both languages."""
    authorization = json.loads(
        (
            project_root / "outputs/experiments/claude_revision_v1/analysis.json"
        ).read_text(encoding="utf-8")
    )
    calibration = json.loads(
        (
            project_root
            / "outputs/experiments/research_followup_20261006_v1/calibration/analysis.json"
        ).read_text(encoding="utf-8")
    )
    if (
        authorization["authorization_recorded"],
        authorization["synthetic_recorded"],
        calibration["planned"],
        calibration["recorded"],
    ) != (900, 16, 480, 480):
        raise EvidenceTableError("Current study sizes differ from the cited cohorts")

    designs = [
        (
            "Authorization core",
            "180",
            "720",
            "Policy/full; auto/exact target",
            "Pro; normal prompt",
        ),
        (
            "Nested stress regimes",
            "60 (nested)",
            "180",
            "Full; broad/underspecified/conflicting",
            "Pro; normal prompt",
        ),
        (
            "Contemporaneous calibration",
            "120",
            "480",
            "ND/policy/full/configured VIGIL",
            "Pro; normal prompt",
        ),
        ("Synthetic controls", "4 scenarios", "16", "Policy/full", "Pro + V4.1 Flash"),
    ]
    design_headers = ("Study", "Cases", "Assignments", "Conditions", "Scope")
    titles = [
        "Current study cohorts and configurations",
        "Corrected authorization and benign-tool completion",
        "Contemporaneous security and benign-tool utility",
        "Bounded synthetic component controls",
    ]
    notes = [
        "The authorization core and nested stress assignments total 900, not 900 independent cases. "
        "Cohorts overlap. Exact target is evaluator-derived oracle authorization, not a deployable source. "
        "VIGIL uses generated constraints and deterministic hybrid auditing with secondary model verification disabled; "
        "its call cap is 16 versus 8 for the other calibration conditions.",
        "Each cell has 30 planned benign-tool tasks. Completion fractions use observed denominators; "
        "brackets are cached Wilson 95% intervals in percent, not paired-effect intervals. "
        "All outcomes here are known; failures stay in the planned denominator and can coexist with completion. "
        "ASK/DENY are event counts, not counts of distinct tasks. Prompts are normal in both module configurations.",
        "Each attack and benign cell has 30 planned tasks. Fractions use known outcomes, with Wilson 95% "
        "intervals in percent. Unknowns are not safe zeros. For AgentDojo VIGIL, attack ITT bounds are "
        "4/30 to 6/30 and benign completion bounds are 17/30 to 19/30. Failures are separate from unsafe effects. "
        "AgentDojo uses native security verdicts; M3-v2 uses observed simulated unauthorized effects. "
        "ND means no research Guard, not removal of the shared isolation boundary.",
        "Each entry represents one controlled execution per module, not a population rate. U/C means "
        "simulated unsafe effect / task completion (1=true, 0=false). All 16 workflows completed normally. "
        "Full's ASK is waiting for clarification, not human approval or completion. Effects are in-memory mailbox "
        "transitions; boundary rejections were zero. Flash is V4.1, not historical V4 Flash. "
        "These controls do not demonstrate natural-task or arbitrary-leakage generalization.",
    ]
    if chinese:
        titles = [
            "当前研究队列与配置",
            "修正版授权与良性工具完成",
            "同期安全与良性工具效用",
            "有界合成组件控制",
        ]
        design_headers = ("研究", "案例", "执行分配", "条件", "范围")
        names = ("授权主队列", "嵌套压力授权", "同期校准", "合成控制")
        designs = [(names[i], *row[1:]) for i, row in enumerate(designs)]
        notes = [
            "授权主队列与压力授权合计900条分配，不是900个独立任务；队列重叠。精确目标是离线答案派生的理想对照，不是部署授权。配置VIGIL生成约束、确定性hybrid审计，关闭模型二次验证；请求上限16，其他校准条件8。",
            "每单元30个计划良性工具任务。分数使用已观察分母；方括号是缓存Wilson 95%区间（百分比），不是配对差区间。本表结果均已知；失败仍在原分母，且可与完成同时成立。ASK/DENY是事件数，不是不同任务数。两模块都用普通提示。",
            "攻击和良性单元各30个计划任务。分数使用已知结果及Wilson 95%区间（百分比）；未知不当安全零。AgentDojo配置VIGIL的攻击ITT界限4/30至6/30，良性完成17/30至19/30。失败与危险效果分开。AgentDojo为原生安全评分，M3-v2为已观察模拟越权效果；无研究防护仍保留共同隔离边界。",
            "每项为一个受控执行，不是总体发生率。U/C表示模拟危险效果/任务完成（1真、0假）。16条流程均正常结束；full的ASK只是等待澄清，不是真人批准或完成。效果为内存邮箱状态变化；隔离拒绝均0。Flash为V4.1，不是历史V4。本控制不能证明自然任务或任意泄漏泛化。",
        ]

    authorization_cells = _unique(
        authorization["cells"],
        ("benchmark", "evaluation_case_type", "condition_id", "authorization_regime"),
    )
    calibration_cells = _unique(
        calibration["cells"], ("benchmark", "evaluation_case_type", "condition_id")
    )
    synthetic = _unique(
        authorization["synthetic"], ("model_id", "scenario_id", "module_factor")
    )
    authorization_rows, calibration_rows, control_rows = [], [], []
    for benchmark, label in (("agentdojo-v1", "AgentDojo"), ("m3-v2", "M3-v2")):
        for condition, module in (
            ("m3_policy_only", "Policy"),
            ("m3_full_normal_prompt", "Full"),
        ):
            for regime, regime_label in (
                ("auto_compiled", "Auto"),
                ("exact_target_v2", "Exact target"),
            ):
                cell = authorization_cells[benchmark, "benign_tool", condition, regime]
                authorization_rows.append(
                    (
                        f"{label} / {module}",
                        regime_label,
                        _fraction(cell["completion"]),
                        f"{cell['failures']}/{cell['planned']}",
                        f"{cell['ask_count']} / {cell['deny_count']}",
                    )
                )
        for condition, role in (
            ("no_defense", "ND"),
            ("m3_policy_only", "Policy"),
            ("m3_full_normal_prompt", "Full"),
            ("strongest_peer_reviewed_structural_baseline", "VIGIL configured"),
        ):
            attack = calibration_cells[benchmark, "attack", condition]
            benign = calibration_cells[benchmark, "benign_tool", condition]
            calibration_rows.append(
                (
                    f"{label} / {role}",
                    _fraction(attack["unsafe"]),
                    _fraction(benign["completion"]),
                    f"{attack['unsafe']['unknown']} / {benign['completion']['unknown']}",
                    f"{attack['failures']} / {benign['failures']}",
                )
            )
    for model, label in (
        ("deepseek-v4-pro", "V4 Pro"),
        ("deepseek-flash", "V4.1 Flash"),
    ):
        for scenario in (
            "private_restricted",
            "public_restricted",
            "private_archive",
            "missing_classification",
        ):
            policy, full = (
                synthetic[model, scenario, module] for module in ("policy", "full")
            )
            if any(row["operational_status"] != "completed" for row in (policy, full)):
                raise EvidenceTableError(
                    "Control status differs from the cited completed cohort"
                )

            def uc(row: dict) -> str:
                if (
                    type(row["unsafe_effect"]) is not bool
                    or type(row["task_completion"]) is not bool
                ):
                    raise EvidenceTableError(
                        "Unknown synthetic outcome cannot be coerced to zero"
                    )
                return f"{int(row['unsafe_effect'])} / {int(row['task_completion'])}"

            control_rows.append(
                (
                    f"{label} / {scenario.replace('_', ' ')}",
                    uc(policy),
                    uc(full),
                    f"{full['ask_count']} / {full['deny_count']}",
                    f"{policy['evaluation_details']['executed_send_count']} / {full['evaluation_details']['executed_send_count']}",
                )
            )
    headers = [
        design_headers,
        (
            "Benchmark / modules",
            "Authorization",
            "Completion [95% CI, %]",
            "Failure / planned",
            "ASK / DENY",
        ),
        (
            "Benchmark / condition",
            "Attack [95% CI, %]",
            "Benign completion [95% CI, %]",
            "Unknown A / B",
            "Failure A / B",
        ),
        (
            "Model / scenario",
            "Policy U / C",
            "Full U / C",
            "Full ASK / DENY",
            "Sends policy / full",
        ),
    ]
    if chinese:
        headers[1:] = [
            ("基准/模块", "授权", "完成 [95%区间, %]", "失败/计划", "ASK/DENY"),
            (
                "基准/条件",
                "攻击 [95%区间, %]",
                "良性完成 [95%区间, %]",
                "未知 攻击/良性",
                "失败 攻击/良性",
            ),
            (
                "模型/场景",
                "Policy U/C",
                "Full U/C",
                "Full ASK/DENY",
                "发送 Policy/Full",
            ),
        ]
    return [
        (i + 1, titles[i], _markdown(headers[i], rows), notes[i])
        for i, rows in enumerate(
            (designs, authorization_rows, calibration_rows, control_rows)
        )
    ]
