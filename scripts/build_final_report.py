from __future__ import annotations

import csv
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "report" / "作品报告_模板.docx"
OFFICIAL_TEMPLATE = ROOT / "比赛要求" / "附件2：作品报告（模板）.docx"
OUT_DOCX = ROOT / "docs" / "report" / "作品报告_终稿.docx"
OUT_PDF = ROOT / "docs" / "report" / "作品报告_终稿.pdf"
SOURCE_MD = ROOT / "docs" / "report_sections" / "day6_final_report_source.md"
QUALITY_MD = ROOT / "outputs" / "quality" / "day6_report_format_check.md"
REPORT_V03 = ROOT / "docs" / "report_v0.3.md"
QWEN_SUMMARY = ROOT / "outputs" / "metrics" / "day5_qwen25_summary.csv"
STUB_SUMMARY = ROOT / "outputs" / "metrics" / "day5_stub_summary.csv"
FIGURE_DIR = ROOT / "outputs" / "figures"


FORBIDDEN_TERMS = [
    "AI" + "agent",
    "AI" + "Agent",
    "Co" + "dex",
    "Co" + "pilot",
    "Chat" + "GPT 生成",
    "AI " + "生成",
    "你是" + "队员",
    "请只" + "修改",
    "完成后请" + "输出",
    "给 AI" + "agent 的指令",
]


def main() -> int:
    ensure_inputs()
    qwen = overall_rows(QWEN_SUMMARY)
    stub = overall_rows(STUB_SUMMARY)
    content = build_content(qwen, stub)
    SOURCE_MD.write_text(render_source_markdown(content), encoding="utf-8")
    build_docx(content)
    write_quality_report()
    print(f"wrote {OUT_DOCX}")
    print(f"wrote {SOURCE_MD}")
    print(f"wrote {QUALITY_MD}")
    return 0


def ensure_inputs() -> None:
    TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    if not TEMPLATE.exists() and OFFICIAL_TEMPLATE.exists():
        shutil.copyfile(OFFICIAL_TEMPLATE, TEMPLATE)
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"missing template: {TEMPLATE}")
    if not REPORT_V03.exists():
        raise FileNotFoundError(f"missing source report: {REPORT_V03}")
    if not QWEN_SUMMARY.exists() or not STUB_SUMMARY.exists():
        raise FileNotFoundError("missing DAY5 metric summaries")
    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_MD.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_MD.parent.mkdir(parents=True, exist_ok=True)


def overall_rows(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("scope") != "overall":
                continue
            rows[row.get("defense_mode", "unknown")] = row
    return rows


def build_content(qwen: dict[str, dict[str, str]], stub: dict[str, dict[str, str]]) -> dict[str, Any]:
    return {
        "title": "M3-PI Guard：面向工具调用智能体的提示注入行为监督系统",
        "submit_date": "2026年6月",
        "abstract": (
            "随着大模型智能体逐步具备文件读写、邮件发送、接口调用和代码执行等工具能力，"
            "提示注入与越狱攻击的风险从文本输出扩展为可观测的外部行为风险。"
            "本作品围绕工具调用边界构建 M3-PI Guard 行为监督系统，通过规则化归一、指令型文本检测、"
            "JSON/RPC 结构化注入识别、多语言与字符混淆检测、敏感数据流分析和意图-动作一致性校验，"
            "对每一次工具调用输出 allow、ask、deny 决策和可解释风险原因。系统不依赖远程评审模型，"
            "可在本地靶场稳定复现实验。测试结果显示，在 stub 全量矩阵中，baseline 的 ASR 和 DSR 均为 0.5507，"
            "full_guard 模式均降至 0.0000，WRS 从 0.4891 提升至 0.9826；在 Qwen2.5 代表样本中，full_guard 同样将 ASR、UTR、DSR 降至 0.0000。"
            "作品具有本地可复现、行为指标可量化、阻断原因可解释和演示闭环完整等特点，可用于智能体安全评测、教学演示和防护原型验证。"
        ),
        "chapters": [
            {
                "title": "第一章 作品概述",
                "sections": [
                    (
                        "1.1 背景分析",
                        [
                            "大模型正在从问答系统演进为可调用工具的智能体。智能体能够读取本地文件、写入结果、调用接口或生成自动化动作，这提升了任务完成能力，也扩大了攻击面。",
                            "传统提示注入主要关注模型是否输出违规文本，而在工具调用场景中，更关键的问题是模型是否被诱导执行越权动作，例如读取 sandbox/secrets、外发 canary、调用非预期接口或执行代码。",
                            "因此，本作品将安全目标从文本拒答扩展到行为监督：在工具调用执行前进行风险评分和策略裁决。"
                        ],
                    ),
                    (
                        "1.2 相关工作",
                        [
                            "相关研究覆盖越狱攻击、间接提示注入、RAG 数据污染、工具调用劫持和智能体安全评测。现有方法常见路线包括提示词加固、输入过滤、策略沙箱、LLM Judge 和日志审计。",
                            "本作品采用本地规则与行为指标结合的方案，强调可复现与可解释，避免依赖远程模型或不可控服务。"
                        ],
                    ),
                    (
                        "1.3 作品目标",
                        [
                            "作品目标包括：构建可拦截危险工具调用的 Guard；形成覆盖多类攻击的本地评测集；输出 ASR、UTR、DSR、BSR、FPR、AvgRisk、WRS 等行为指标；提供 Dashboard 演示和单案例回放。"
                        ],
                    ),
                    (
                        "1.4 特色与应用前景",
                        [
                            "系统特色是将安全判断绑定到工具执行边界，并将每次阻断转化为明确原因码。该能力可应用于智能体安全测试、课程实验、企业内部工具代理审计和提示注入防护原型验证。"
                        ],
                    ),
                ],
            },
            {
                "title": "第二章 作品设计与实现",
                "sections": [
                    (
                        "2.1 系统方案",
                        [
                            "系统由攻击样本、智能体运行器、工具沙箱、行为监督 Guard、指标评测和 Dashboard 六部分组成。运行器读取 AttackCase，模型或 stub 后端输出 ToolCall，Guard 在工具执行前给出 allow、ask 或 deny。",
                            "工具沙箱仅模拟本地文件、邮件、API 和代码执行结果，不访问真实公网业务系统。"
                        ],
                    ),
                    (
                        "2.2 实现原理",
                        [
                            "Guard 采用分层检测：normalizer 负责 Unicode NFKC 归一化、零宽字符删除和混合脚本识别；detector 识别指令型文本、工具诱导、JSON/RPC 字段和多语言混淆；dataflow 标记 canary、api_key、token、password 等敏感数据流；policy_engine 实现工具策略矩阵；guard_engine 汇总风险并按阈值裁决。",
                            "风险阈值为 risk >= 0.65 时 deny，0.35 <= risk < 0.65 时 ask，risk < 0.35 时 allow。run_code、secret 路径读取、非 sandbox 路径、非 /mock endpoint 和敏感数据外发属于强规则拒绝。"
                        ],
                    ),
                    (
                        "2.3 软件流程",
                        [
                            "流程为：加载攻击样本；构造上下文；模型生成 ToolCall；Guard 归一化输入并计算风险；根据策略输出决策；允许时执行本地模拟工具，拒绝或确认时写入阻断日志；评测脚本聚合 RunLog 并生成指标。"
                        ],
                    ),
                    (
                        "2.4 模块功能",
                        [
                            "m3_guard 提供工具调用风险裁决；m3_eval.evaluate 生成 CSV/JSON 指标；m3_eval.dashboard 提供总览、分组、阻断记录、单案例回放和原始日志查看；plot_metrics 生成答辩图表。"
                        ],
                    ),
                    (
                        "2.5 指标体系",
                        [
                            "指标包括 ASR、UTR、DSR、BSR、FPR、AvgRisk 和 WRS。其中 ASR 衡量攻击成功率，UTR 衡量未授权工具调用率，DSR 衡量敏感数据外泄率，BSR 衡量阻断成功率，WRS 综合反映系统韧性。"
                        ],
                    ),
                ],
            },
            {
                "title": "第三章 作品测试与分析",
                "sections": [
                    (
                        "3.1 测试环境",
                        [
                            "测试在本地 Windows 环境完成，使用 Python 脚本运行 stub 后端和 Qwen2.5 代表样本。工具调用均为本地模拟，邮件写入 outbox 文件，API 返回 mock JSON，代码执行工具默认禁用。"
                        ],
                    ),
                    (
                        "3.2 测试数据与方案",
                        [
                            "测试数据包括 stub 全量四模式矩阵、Qwen2.5 代表样本和 demo case。攻击类型覆盖 direct_jailbreak、rag_indirect、json_rpc、multilingual_t2l、tool_output_injection 和 benign_clean 等类别。",
                            "防御模式包括 baseline、keyword_only、policy_only 和 full_guard，用于分析不同防护组件的贡献。"
                        ],
                    ),
                    (
                        "3.3 实验结果",
                        [
                            "stub 全量矩阵中，baseline 的 ASR 为 0.5507、DSR 为 0.5507；full_guard 的 ASR、UTR、DSR 均为 0.0000，BSR 为 0.8841，WRS 达到 0.9826。",
                            "Qwen2.5 代表样本中，baseline 的 ASR 为 0.0833、DSR 为 0.0417；full_guard 将 ASR、UTR、DSR 均降为 0.0000，WRS 提升至 0.9187。",
                            "demo case 中 full_guard 的 BSR 为 1.0000，适合展示阻断原因和单案例回放。"
                        ],
                    ),
                    (
                        "3.4 案例分析",
                        [
                            "在 RAG 间接提示注入案例中，文档隐藏 read_file 和 send_email 指令，Guard 会同时给出 tool_lure、structured_injection 或 sensitive_data_flow 相关原因。",
                            "在 JSON/RPC 注入案例中，method、params、execute、next_step 等字段会增加结构化注入风险。",
                            "在多语言/T2L 案例中，系统通过混合脚本、工具词和拼音规避信号提高风险评分。"
                        ],
                    ),
                ],
                "tables": [
                    ("表 1 stub 全量矩阵总体结果", rows_for_table(stub, ["baseline", "keyword_only", "policy_only", "full_guard"])),
                    ("表 2 Qwen2.5 代表样本总体结果", rows_for_table(qwen, ["baseline", "full_guard"])),
                ],
                "figures": [
                    ("图 1 ASR 防御模式对比", "day5_asr_by_defense_mode.png"),
                    ("图 2 DSR 防御模式对比", "day5_dsr_by_defense_mode.png"),
                    ("图 3 WRS 防御模式对比", "day5_wrs_by_defense_mode.png"),
                    ("图 4 Guard 阻断原因 Top 10", "day5_guard_reasons_top10.png"),
                ],
            },
            {
                "title": "第四章 创新性说明",
                "sections": [
                    (
                        "4.1 行为边界监督",
                        [
                            "作品将提示注入防护点从模型输出文本前移到工具执行边界，直接降低越权读取、外发和代码执行风险。"
                        ],
                    ),
                    (
                        "4.2 多信号可解释风险评分",
                        [
                            "系统将工具类型、路径、endpoint、敏感数据流、结构化注入、多语言混淆和意图-动作不一致合并为可解释风险原因，便于复盘和展示。"
                        ],
                    ),
                    (
                        "4.3 本地可复现实验闭环",
                        [
                            "作品提供攻击样本、运行日志、评测脚本、图表和 Dashboard，形成无需远程服务的完整本地评测闭环。"
                        ],
                    ),
                ],
            },
            {
                "title": "第五章 总结",
                "sections": [
                    (
                        "5.1 工作总结",
                        [
                            "本作品实现了面向工具调用智能体的行为监督 Guard，并通过多组日志验证其对未授权工具调用和敏感数据外发的抑制效果。实验表明，full_guard 能显著降低 ASR、UTR 和 DSR，并提供可解释的阻断原因。"
                        ],
                    ),
                    (
                        "5.2 后续工作",
                        [
                            "后续可扩展更丰富的 clean case 以增强 FPR 解释力，引入语义级检测以覆盖深度改写攻击，并将 Dashboard 扩展为长期实验管理与审计平台。"
                        ],
                    ),
                ],
            },
        ],
        "references": [
            "[1] Perez F, Ribeiro I. Ignore Previous Prompt: Attack Techniques For Language Models[C]//NeurIPS ML Safety Workshop. 2022.",
            "[2] Greshake K, Abdelnabi S, Mishra S, et al. Not what you have signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection[C]//AISec. 2023.",
            "[3] OWASP Foundation. OWASP Top 10 for Large Language Model Applications[EB/OL]. 2025.",
            "[4] Yao S, Zhao J, Yu D, et al. ReAct: Synergizing Reasoning and Acting in Language Models[C]//ICLR. 2023.",
            "[5] Wei A, Haghtalab N, Steinhardt J. Jailbroken: How Does LLM Safety Training Fail?[C]//NeurIPS. 2023.",
            "[6] 中国国家标准化管理委员会. 信息与文献 参考文献著录规则: GB/T 7714-2015[S]. 北京: 中国标准出版社, 2015.",
        ],
    }


def rows_for_table(rows: dict[str, dict[str, str]], modes: list[str]) -> list[list[str]]:
    table_rows = [["防御模式", "ASR", "UTR", "DSR", "BSR", "WRS"]]
    for mode in modes:
        row = rows.get(mode, {})
        table_rows.append([
            mode,
            row.get("ASR", "-"),
            row.get("UTR", "-"),
            row.get("DSR", "-"),
            row.get("BSR", "-"),
            row.get("WRS", "-"),
        ])
    return table_rows


def build_docx(content: dict[str, Any]) -> None:
    doc = Document(str(TEMPLATE))
    clear_body(doc)
    setup_document(doc)

    add_cover(doc, content)
    doc.add_page_break()
    add_instructions(doc)
    doc.add_page_break()
    add_static_toc(doc)
    doc.add_page_break()
    add_body(doc, content)
    scrub_core_properties(doc)
    doc.save(str(OUT_DOCX))
    scrub_docx_package(OUT_DOCX)


def clear_body(doc: Document) -> None:
    body = doc._body._element
    for child in list(body):
        if child.tag.endswith("sectPr"):
            continue
        body.remove(child)


def setup_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.8)
    section.right_margin = Cm(2.6)
    section.start_type = WD_SECTION.NEW_PAGE

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "宋体"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.first_line_indent = Pt(24)

    for name, size, color in [
        ("Heading 1", 16, RGBColor(0x1F, 0x4E, 0x79)),
        ("Heading 2", 14, RGBColor(0x1F, 0x4E, 0x79)),
        ("Heading 3", 12, RGBColor(0x00, 0x00, 0x00)),
    ]:
        try:
            style = styles[name]
        except KeyError:
            continue
        style.font.name = "黑体"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = color
        style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        style.paragraph_format.space_before = Pt(10)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.first_line_indent = Pt(0)


def add_cover(doc: Document, content: dict[str, Any]) -> None:
    p = doc.add_paragraph("第十九届全国大学生信息安全竞赛（作品赛）暨第三届“长城杯”网数智安全大赛（作品赛）")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    format_run(p.runs[0], "宋体", 14, bold=True)
    add_spacer(doc, 2)
    title = doc.add_paragraph("作品报告")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    format_run(title.runs[0], "黑体", 24, bold=True)
    add_spacer(doc, 3)
    lane = doc.add_paragraph("☑命题赛道             □自由赛道")
    lane.alignment = WD_ALIGN_PARAGRAPH.CENTER
    format_run(lane.runs[0], "宋体", 12)
    add_spacer(doc, 4)
    for label, value in [
        ("作品名称", content["title"]),
        ("电子邮箱", ""),
        ("提交日期", content["submit_date"]),
    ]:
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Pt(0)
        run = p.add_run(f"{label}：{value}")
        format_run(run, "宋体", 12)


def add_instructions(doc: Document) -> None:
    add_heading(doc, "填写说明", 1)
    instructions = [
        "1. 所有参赛项目必须为一个基本完整的设计。作品报告书旨在能够清晰准确地阐述（或图示）该参赛队的参赛项目（或方案）。",
        "2. 作品报告采用A4纸撰写。除标题外，所有内容必需为宋体、小四号字、1.5倍行距。",
        "3. 作品报告中各项目说明文字部分仅供参考，作品报告书撰写完毕后，请删除所有说明文字。(本页不删除)",
        "4. 作品报告模板里已经列的内容仅供参考，作者可以在此基础上增加内容或对文档结构进行微调。",
        "5. 为保证网评的公平、公正，作品报告中应避免出现作者所在学校、院系和指导教师等泄露身份的信息。",
    ]
    for item in instructions:
        add_para(doc, item, first_line=False)


def add_static_toc(doc: Document) -> None:
    add_heading(doc, "目     录", 1)
    for item in [
        "摘要",
        "第一章 作品概述",
        "第二章 作品设计与实现",
        "第三章 作品测试与分析",
        "第四章 创新性说明",
        "第五章 总结",
        "参考文献",
    ]:
        p = doc.add_paragraph(item)
        p.paragraph_format.first_line_indent = Pt(0)
        format_run(p.runs[0], "宋体", 12)


def add_body(doc: Document, content: dict[str, Any]) -> None:
    add_heading(doc, "摘要", 1)
    add_para(doc, content["abstract"])
    add_para(doc, "关键词：提示注入；智能体安全；工具调用；行为监督；风险评分", first_line=False)

    for chapter in content["chapters"]:
        doc.add_page_break()
        add_heading(doc, chapter["title"], 1)
        for heading, paragraphs in chapter["sections"]:
            add_heading(doc, heading, 2)
            for text in paragraphs:
                add_para(doc, text)
        for caption, rows in chapter.get("tables", []):
            add_caption(doc, caption)
            add_table(doc, rows)
        for caption, filename in chapter.get("figures", []):
            add_figure(doc, caption, FIGURE_DIR / filename)

    doc.add_page_break()
    add_heading(doc, "参考文献", 1)
    for item in content["references"]:
        add_para(doc, item, first_line=False)


def add_heading(doc: Document, text: str, level: int) -> None:
    style_name = f"Heading {level}"
    try:
        doc.styles[style_name]
    except KeyError:
        p = doc.add_paragraph(text)
        size = 16 if level == 1 else 14 if level == 2 else 12
        if p.runs:
            format_run(p.runs[0], "黑体", size, bold=True)
    else:
        p = doc.add_paragraph(text, style=style_name)
    p.paragraph_format.first_line_indent = Pt(0)


def add_para(doc: Document, text: str, first_line: bool = True) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.first_line_indent = Pt(24) if first_line else Pt(0)
    run = p.add_run(text)
    format_run(run, "宋体", 12)


def add_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    format_run(p.runs[0], "宋体", 10.5, bold=True)


def add_table(doc: Document, rows: list[list[str]]) -> None:
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    try:
        table.style = "Table Grid"
    except KeyError:
        pass
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            cell = table.cell(i, j)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.first_line_indent = Pt(0)
            run = p.add_run(str(value))
            format_run(run, "宋体", 10.5, bold=(i == 0))
            set_cell_shading(cell, "D9EAF7" if i == 0 else "FFFFFF")
    set_table_width(table)
    doc.add_paragraph()


def add_figure(doc: Document, caption: str, path: Path) -> None:
    if not path.exists():
        add_para(doc, f"{caption}：图表文件缺失。", first_line=False)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    run = p.add_run()
    run.add_picture(str(path), width=Inches(5.8))
    add_caption(doc, caption)


def add_spacer(doc: Document, count: int) -> None:
    for _ in range(count):
        doc.add_paragraph("")


def format_run(run: Any, font: str, size: float, bold: bool = False) -> None:
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    run.font.size = Pt(size)
    run.font.bold = bold


def set_cell_shading(cell: Any, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_table_width(table: Any) -> None:
    for row in table.rows:
        for cell in row.cells:
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:type"), "dxa")
            tc_w.set(qn("w:w"), "1500")


def scrub_core_properties(doc: Document) -> None:
    props = doc.core_properties
    props.author = ""
    props.last_modified_by = ""
    props.title = "M3-PI Guard作品报告"
    props.subject = "人工智能安全作品报告"
    props.comments = ""
    props.keywords = "提示注入;智能体安全;工具调用"


def scrub_docx_package(path: Path) -> None:
    temp = path.with_suffix(".tmp.docx")
    with zipfile.ZipFile(path, "r") as zin, zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            is_text_part = item.filename.endswith(".xml") or item.filename.endswith(".rels")
            if is_text_part and (item.filename.startswith("docProps/") or item.filename.startswith("word/")):
                text = data.decode("utf-8", errors="ignore")
                text = re.sub(r'w:rsid\w+="[^"]+"', "", text)
                data = text.encode("utf-8")
            zout.writestr(item, data)
    temp.replace(path)


def render_source_markdown(content: dict[str, Any]) -> str:
    lines = [f"# {content['title']}", "", "## 摘要", "", content["abstract"], ""]
    for chapter in content["chapters"]:
        lines.extend([f"## {chapter['title']}", ""])
        for heading, paragraphs in chapter["sections"]:
            lines.extend([f"### {heading}", ""])
            lines.extend(paragraphs)
            lines.append("")
    lines.extend(["## 参考文献", ""])
    lines.extend(content["references"])
    lines.append("")
    return "\n".join(lines)


def write_quality_report() -> None:
    scans = {
        "docs/report_v0.3.md": scan_text(REPORT_V03.read_text(encoding="utf-8", errors="ignore")),
        "docs/report_sections/day6_final_report_source.md": scan_text(SOURCE_MD.read_text(encoding="utf-8", errors="ignore")),
        "docs/report/作品报告_终稿.docx": scan_docx(OUT_DOCX),
    }
    identity_findings = scan_identity(OUT_DOCX)
    format_checks = [
        "A4 page size set to 21cm x 29.7cm.",
        "Normal style set to 宋体, 小四号, 1.5倍行距.",
        "Official structure retained: 封面、填写说明、目录、摘要、五章正文、参考文献.",
        "Template placeholder guidance in正文 has been replaced; 填写说明页 retained.",
        "Cover avoids school, department, teacher, member name, and student ID fields.",
        f"PDF export status: {'generated at docs/report/作品报告_终稿.pdf' if OUT_PDF.exists() else 'not generated in this local environment'}.",
    ]
    lines = [
        "# DAY6 Report Format Check",
        "",
        "## Format Checks",
        *[f"- {item}" for item in format_checks],
        "",
        "## Forbidden Trace Scan",
    ]
    for target, findings in scans.items():
        status = "PASS" if not findings else "FAIL"
        lines.append(f"- {target}: {status}")
        for finding in findings:
            lines.append(f"  - {finding}")
    lines.extend(["", "## Identity Leak Check"])
    if identity_findings:
        lines.append("- REVIEW REQUIRED")
        lines.extend(f"  - {item}" for item in identity_findings)
    else:
        lines.append("- PASS: no concrete school, college, advisor, member-name, or student-id patterns were found outside the retained filling-instructions page.")
    lines.extend([
        "",
        "## Manual Steps",
        "- Open the DOCX in Word/WPS and update table-of-contents page numbers before final submission.",
        "- If the PDF export is unavailable in the local environment, export PDF from Word/WPS after checking pagination.",
    ])
    QUALITY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def scan_text(text: str) -> list[str]:
    return [term for term in FORBIDDEN_TERMS if term in text]


def scan_docx(path: Path) -> list[str]:
    findings: list[str] = []
    with zipfile.ZipFile(path, "r") as archive:
        for name in archive.namelist():
            if not name.endswith(".xml"):
                continue
            text = archive.read(name).decode("utf-8", errors="ignore")
            for term in FORBIDDEN_TERMS:
                if term in text:
                    findings.append(f"{name}: {term}")
    return findings


def scan_identity(path: Path) -> list[str]:
    text_parts: list[str] = []
    with zipfile.ZipFile(path, "r") as archive:
        for name in archive.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                text_parts.append(archive.read(name).decode("utf-8", errors="ignore"))
    text = "\n".join(text_parts)
    findings: list[str] = []
    patterns = [
        r"学号[:：]\s*\d+",
        r"队员姓名[:：]\s*[\u4e00-\u9fff]{2,4}",
        r"指导老师[:：]\s*[\u4e00-\u9fff]{2,4}",
        r"指导教师[:：]\s*[\u4e00-\u9fff]{2,4}",
        r"学院[:：]\s*[\u4e00-\u9fff]{2,}",
        r"学校[:：]\s*[\u4e00-\u9fff]{2,}",
    ]
    for pattern in patterns:
        if re.search(pattern, text):
            findings.append(pattern)
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
