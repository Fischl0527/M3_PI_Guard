from __future__ import annotations

import re
import zipfile
from collections import Counter
from pathlib import Path

import pytest
from docx import Document
from docx.oxml.ns import qn

from scripts import build_lean_paper_chinese_docx as builder


ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT_DIR = ROOT / "docs/research/paper_v2/manuscript"
CHINESE_MARKDOWN = MANUSCRIPT_DIR / "manuscript_zh_v1.md"
ENGLISH_MARKDOWN = MANUSCRIPT_DIR / "manuscript_deepseek_v1.md"


def _citation_keys(text: str) -> set[str]:
    return set(re.findall(r"@([A-Za-z0-9_.:-]+)", text))


def test_chinese_markdown_mirrors_scientific_structure_and_boundaries() -> None:
    text = CHINESE_MARKDOWN.read_text(encoding="utf-8")

    expected = [
        "## 摘要",
        "## 1. 引言",
        "## 2. 相关工作",
        "## 3. 方法",
        "## 4. 结果",
        "## 5. 讨论",
        "## 6. 结论",
        "## 图",
        "## 表",
        "## 图注",
        "## 投稿声明",
        "## 参考文献",
    ]
    positions = [text.index(heading) for heading in expected]
    assert positions == sorted(positions)
    assert text.count("![图 ") == 5
    assert len(re.findall(r"^### 表 [1-6]\. ", text, flags=re.MULTILINE)) == 6
    assert "38/600" in text
    assert "13/600" in text
    assert "24/400" in text
    assert "12/400" in text
    assert "21.67 个百分点" in text
    assert "15.00 个百分点" in text
    assert "由 7/100 升至 25/100" in text
    assert "由 8/100 升至 26/100" in text
    assert "CNY 1.3888324" in text
    assert "4/40" in text and "18/40" in text
    assert "所有 Gemini 配对、因子和跨厂商效应均不可估计" in text
    assert "不作跨厂商泛化主张" in text
    assert "**RQ2：提示词与运行时组件。**" in text
    assert "**RQ4：来源权威性。**" in text
    assert "**RQ5：自适应尾部风险。**" in text
    assert "**RQ6：同期攻击活性。**" in text
    assert "**RQ2：模块贡献。**" not in text
    assert "分别估计两项主效应及其交互" in text
    assert "不安全或失败" in text
    assert "由 17/30 降至 0/30" in text
    assert "不能识别单个运行时模块的贡献" in text
    assert "ASK 不是测得的人类负担" in text
    assert "0/12" in text and "24.25%" in text
    assert "17/60" in text and "30/240" in text
    assert "47/60 个任务是 E3 锚点" in text
    assert "29/30 个 E3 锚点" in text
    assert "不满足也不检验原三窗口设计的活性门" in text
    assert "双侧 exact McNemar p 值" in text
    assert "计划中的 cluster sign-flip 检验" in text
    assert "af8eb9c70d32f8a3cc07b308e823c813b2285772" in text
    assert "本文首次提出" not in text
    assert "M3 是最先进防御" not in text
    assert "M3 不能被描述为首个" in text
    assert "Full Harness" not in text
    assert "SHA-256" not in text
    # 图片目标移至outputs不属于正文工程说明；目标本身另作存在性检查。
    reader_text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    assert "outputs/" not in reader_text
    figure_targets = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    assert all((CHINESE_MARKDOWN.parent / target).is_file() for target in figure_targets)
    assert "[UNVERIFIED CITATION" not in text
    assert "<!--anchor:none:" not in text


def test_chinese_and_english_manuscripts_use_the_same_citation_corpus() -> None:
    chinese = CHINESE_MARKDOWN.read_text(encoding="utf-8")
    english = ENGLISH_MARKDOWN.read_text(encoding="utf-8")

    assert _citation_keys(chinese) == _citation_keys(english)
    assert len(_citation_keys(chinese)) == 24


def test_chinese_main_tables_preserve_every_numeric_token() -> None:
    chinese = CHINESE_MARKDOWN.read_text(encoding="utf-8")
    english = ENGLISH_MARKDOWN.read_text(encoding="utf-8")
    chinese_tables = chinese.split("## 表", 1)[1].split("## 图注", 1)[0]
    english_tables = english.split("## Tables", 1)[1].split(
        "## Figure captions", 1
    )[0]
    number_pattern = re.compile(
        r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)*(?:e[-+]?\d+)?%?",
        flags=re.IGNORECASE,
    )

    assert Counter(number_pattern.findall(chinese_tables)) == Counter(
        number_pattern.findall(english_tables)
    )


def test_prepare_markdown_replaces_chinese_reference_placeholder() -> None:
    source = "# 标题\n\n正文 [@L01]。\n\n## 参考文献\n\n占位文本。\n"

    prepared = builder._prepare_markdown(source)

    assert "占位文本" not in prepared
    assert "正文 [@L01]。" in prepared
    assert "## 参考文献" in prepared
    assert '<div id="refs"></div>' in prepared


def test_prepare_markdown_requires_chinese_reference_boundary() -> None:
    with pytest.raises(builder.ChineseDocxBuildError, match="reference boundary"):
        builder._prepare_markdown("# 标题\n")


def test_generated_chinese_docx_preserves_layout_content_and_cjk_fonts() -> None:
    document = Document(builder.OUTPUT_PATH)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    # Eight numbered result tables plus the runtime-condition table in Methods.
    assert len(document.tables) == 9
    assert len(document.inline_shapes) == 5
    assert len(document.sections) == 1
    section = document.sections[0]
    assert round(section.page_width.inches, 3) == 8.5
    assert round(section.page_height.inches, 3) == 11.0
    assert round(section.top_margin.inches, 3) == 1.0
    assert round(section.right_margin.inches, 3) == 1.0
    assert round(section.bottom_margin.inches, 3) == 1.0
    assert round(section.left_margin.inches, 3) == 1.0
    assert "工具型大语言模型智能体的授权制度与运行时 Guard 配置评估" in text
    assert "38/600" in text and "13/600" in text
    assert "所有 Gemini 配对、因子和跨厂商效应均不可估计" in text
    assert "[@" not in text
    assert "�" not in text
    assert document.core_properties.subject == "JISA 中文内部对照稿"
    assert document.core_properties.title == (
        "工具型大语言模型智能体的授权制度与运行时 Guard 配置评估"
    )
    assert sum(
        paragraph.style.name == "Bibliography" for paragraph in document.paragraphs
    ) == 24

    with zipfile.ZipFile(builder.OUTPUT_PATH) as archive:
        custom = archive.read("docProps/custom.xml").decode("utf-8")
    assert str(builder.PROJECT_ROOT) not in custom
    assert "references_v1.bib" in custom

    normal_style = next(style for style in document.styles if style.name == "Normal")
    heading_style = next(
        style for style in document.styles if style.name == "Heading 1"
    )
    normal_fonts = normal_style._element.get_or_add_rPr().rFonts
    heading_fonts = heading_style._element.get_or_add_rPr().rFonts
    assert normal_fonts.get(qn("w:eastAsia")) == builder.BODY_CJK_FONT
    assert heading_fonts.get(qn("w:eastAsia")) == builder.HEADING_CJK_FONT
