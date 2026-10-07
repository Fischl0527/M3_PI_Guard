from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts import build_jisa_latex as builder


REPO_ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT = (
    REPO_ROOT
    / "docs"
    / "research"
    / "paper_v2"
    / "manuscript"
    / "manuscript_deepseek_v1.md"
)
BIBLIOGRAPHY = MANUSCRIPT.with_name("references_v1.bib")
FIGURES = (
    REPO_ROOT
    / "outputs" / "experiments" / "research_followup_20261006_v1" / "manuscript_figures"
)


def test_semantic_placement_survives_number_changes_without_dropping_text() -> None:
    original = "### 4.9 Evidence\n\nkept 900\n\n### 4.10 Legacy\n\nkept 480"
    moved = original.replace("4.9 Evidence", "4.1 Evidence")
    for markdown in (original, moved):
        result = builder._inject_after_subsections(markdown, {"Evidence": ("table_01",)})
        assert result.count("@@ARTIFACT:table_01@@") == 1
        assert result.index("kept 900") < result.index("@@ARTIFACT:table_01@@")
        assert result.index("@@ARTIFACT:table_01@@") < result.index("### 4.10 Legacy")
        assert result.replace("\n\n@@ARTIFACT:table_01@@\n", "") == markdown


def test_semantic_placement_rejects_missing_and_duplicate_titles() -> None:
    for markdown in ("### 4.1 Other", "### 4.1 Evidence\nx\n### 4.2 Evidence\ny"):
        with pytest.raises(builder.LatexBuildError, match="exactly once"):
            builder._inject_after_subsections(markdown, {"Evidence": ("table_01",)})


def _build(tmp_path: Path) -> builder.BuildPaths:
    return builder.build(
        repo_root=REPO_ROOT,
        output_root=tmp_path / "M3_PI_Guard_JISA",
        review_entry=tmp_path / "M3_PI_Guard_template_review.tex",
    )


def test_builds_shared_official_review_and_supplement_packages(tmp_path: Path) -> None:
    paths = _build(tmp_path)

    official = paths.official_entry.read_text(encoding="utf-8")
    review = paths.review_entry.read_text(encoding="utf-8")
    supplement = paths.supplement_entry.read_text(encoding="utf-8")

    assert builder.REVIEW_ENTRY.name == "数模通用模板.tex"
    assert builder.LEGACY_REVIEW_ENTRY.name == "M3_PI_Guard_template_review.tex"
    assert r"\documentclass[preprint,12pt,a4paper]{elsarticle}" in official
    assert r"\documentclass[withoutpreface,bwprint]{cumcmthesis}" in review
    assert r"\author" not in official
    assert r"\author" not in review
    assert r"\author" not in supplement
    assert r"\newcommand{\ProjectRoot}{.}" in official
    assert r"\newcommand{\ProjectRoot}{M3_PI_Guard_JISA}" in review
    assert r"\usepackage[numbers,sort&compress]{natbib}" in review
    assert r"\usepackage{rotating,microtype,ragged2e,placeins}" in review
    assert r"\setmainfont{Times New Roman}" in review
    assert r"\setsansfont{Times New Roman}" in review
    assert r"\setmonofont{Times New Roman}" in review
    assert r"\setmainfont{Times New Roman}" in official + supplement
    assert r"\urlstyle{same}" in review
    assert r"\captionsetup[figure]{font={rm,minusfour,bf}}" in review
    assert r"\captionsetup[table]{font={rm,minusfour,bf}}" in review
    assert r"\rmfamily\bfseries\mcm@cap@keywordsname:" in review
    assert r"\pagestyle{plain}" in review
    assert "pdflscape" not in official + review + supplement
    assert r"\providecommand{\tightlist}" in official
    assert r"\providecommand{\tightlist}" in review
    assert r"\providecommand{\tightlist}" in supplement
    assert r"\nocite{*}" not in official + review + supplement

    expected_sections = {
        "abstract.tex",
        "keywords.tex",
        "01_introduction.tex",
        "02_related_work.tex",
        "03_methods.tex",
        "04_results.tex",
        "05_discussion.tex",
        "06_conclusion.tex",
        "declarations.tex",
    }
    assert expected_sections <= {path.name for path in paths.output_root.glob("*.tex")}
    for title, filename in builder.SECTION_FILES.items():
        rendered = (paths.output_root / filename).read_text(encoding="utf-8")
        assert rf"\section{{{builder._strip_number(title)}}}" in rendered
        assert rf"\input{{M3_PI_Guard_JISA/{filename}}}" in review
        assert rf"\input{{\ProjectRoot/{filename}}}" in official
        assert rf"\input{{\ProjectRoot/{filename}}}" not in review

    assert r"\input{M3_PI_Guard_JISA/abstract.tex}" in review
    assert r"\input{M3_PI_Guard_JISA/declarations.tex}" in review
    assert r"\bibliography{M3_PI_Guard_JISA/references}" in review

    assert r"\bibliographystyle{elsarticle-num}" in official
    assert r"\bibliographystyle{gbt7714-numerical}" in review
    assert (paths.output_root / "references.bib").read_bytes() == BIBLIOGRAPHY.read_bytes()


def test_preserves_citations_figures_and_scientific_boundary_text(tmp_path: Path) -> None:
    paths = _build(tmp_path)
    generated_tex = "\n".join(
        path.read_text(encoding="utf-8")
        for path in paths.output_root.glob("*.tex")
    )
    semantic_tex = generated_tex.replace(r"\-", "")
    markdown = MANUSCRIPT.read_text(encoding="utf-8")

    markdown_keys = set(re.findall(r"@([A-Za-z0-9_:-]+)", markdown))
    latex_keys = {
        key
        for citation in re.findall(r"\\citep\{([^}]+)\}", generated_tex)
        for key in citation.split(",")
    }
    assert len(markdown_keys) == 24
    assert latex_keys == markdown_keys

    assert r"0/240 unauthorized proposals" in semantic_tex
    assert r"30/240 authorized proposals" in semantic_tex
    assert r"0/12" in generated_tex
    assert r"24.25\%" in generated_tex
    assert r"17/60" in generated_tex
    assert "effects are therefore not estimable" in generated_tex
    assert r"\nolinkurl{auto_compiled}" in generated_tex
    for compound in (
        "verify-before-commit",
        "outcome-enriched",
        "target-scoped",
        "execution-plan",
        "full-package",
    ):
        assert compound in generated_tex

    for number, filename in builder.FIGURE_FILES.items():
        copied = paths.output_root / filename
        assert copied.read_bytes() == (FIGURES / filename).read_bytes()
        snippet = paths.output_root / f"figure_{number:02d}.tex"
        text = snippet.read_text(encoding="utf-8")
        assert rf"\label{{fig:{number:02d}}}" in text
        assert filename in text
        assert r"width=\textwidth" in text


def test_preserves_main_and_supplementary_table_shapes(tmp_path: Path) -> None:
    paths = _build(tmp_path)
    table_dir = paths.output_root

    expected_main_shapes = {
        1: (4, 5),
        2: (8, 5),
        3: (8, 5),
        4: (8, 5),
    }
    expected_supplement_shapes = {
        1: (4, 4),
        2: (6, 6),
        3: (4, 5),
        4: (6, 7),
        5: (5, 4),
        6: (3, 6),
        7: (4, 7),
        8: (8, 6),
        9: (2, 7),
        10: (9, 2),
        11: (6, 6),
        12: (6, 6),
        13: (4, 5),
        14: (9, 10),
        15: (10, 10),
        16: (15, 10),
        17: (4, 8),
        18: (6, 6),
        19: (4, 4),
        20: (24, 5),
    }

    _, main_sections = builder._split_h2(MANUSCRIPT.read_text(encoding="utf-8"))
    main_tables = builder._parse_numbered_tables(
        main_sections["Tables"], supplementary=False
    )
    supplementary_source = MANUSCRIPT.with_name("supplementary_tables_v1.md")
    supplementary_tables = builder._parse_numbered_tables(
        supplementary_source.read_text(encoding="utf-8"), supplementary=True
    )
    assert {
        int(table.number): (len(table.rows), len(table.header)) for table in main_tables
    } == expected_main_shapes
    assert {
        int(table.number[1:]): (len(table.rows), len(table.header))
        for table in supplementary_tables
    } == expected_supplement_shapes

    assert len(list(table_dir.glob("table_*.tex"))) == 4
    assert len(list(table_dir.glob("supplement_s*.tex"))) == 20
    assert r"false allow & not applicable & 240" in (
        table_dir / "supplement_s15.tex"
    ).read_text(encoding="utf-8")
    assert r"all selected survivors & 12 & 0" in (
        table_dir / "supplement_s17.tex"
    ).read_text(encoding="utf-8")
    assert r"\label{tab:s17}" in (table_dir / "supplement_s17.tex").read_text(
        encoding="utf-8"
    )
    assert r"No defense & 17/60" in (
        table_dir / "supplement_s18.tex"
    ).read_text(encoding="utf-8")
    assert r"\label{tab:s18}" in (table_dir / "supplement_s18.tex").read_text(
        encoding="utf-8"
    )
    historical_wide = (table_dir / "supplement_s18.tex").read_text(encoding="utf-8")
    wide_supplement = (table_dir / "supplement_s12.tex").read_text(
        encoding="utf-8"
    )
    assert historical_wide.startswith(r"\begingroup")
    assert wide_supplement.startswith(r"\begingroup")
    assert historical_wide.count(r"\begin{longtable}") == 2
    assert "part A" in historical_wide and "part B" in historical_wide
    assert "Row IDs identify the same original row" in historical_wide
    assert r"\small" in historical_wide + wide_supplement
    assert historical_wide.count(r"\label{tab:s18}") == 1
    for table in supplementary_tables:
        rendered = (table_dir / f"supplement_s{int(table.number[1:]):02d}.tex").read_text(encoding="utf-8")
        assert not any(token in rendered for token in ("sidewaystable", "landscape", r"\scriptsize", r"\resizebox"))
        for heading in table.header:
            assert builder._table_inline(heading) in rendered
        for row in table.rows:
            for value in row:
                assert builder._table_inline(value) in rendered

    narrow_main = (table_dir / "table_01.tex").read_text(encoding="utf-8")
    assert narrow_main.startswith(r"\begingroup")
    assert r"\begin{longtable}" in narrow_main
    assert "sidewaystable" not in narrow_main

    for number in range(1, 5):
        assert "sidewaystable" not in (table_dir / f"table_{number:02d}.tex").read_text(encoding="utf-8")
    assert "4/28" in (table_dir / "table_03.tex").read_text(encoding="utf-8")
    assert "4/30 to 6/30" in (table_dir / "table_03.tex").read_text(encoding="utf-8")
    permit_table = (table_dir / "supplement_s19.tex").read_text(encoding="utf-8")
    assert "sidewaystable" not in permit_table
    assert permit_table.startswith(r"\begin{table}[!htbp]")
    assert permit_table.rstrip().endswith(r"\end{table}")
    assert r"\begin{tabularx}{\linewidth}{@{}LLLL@{}}" in permit_table
    assert r"\begin{longtable}" not in permit_table
    assert "One-shot permits under trusted approval, not task completion" in permit_table
    assert "Bounded enum / full & 12/12 & 12/12 & 0/12" in permit_table


def test_places_artifacts_once_and_emits_no_absolute_workspace_paths(
    tmp_path: Path,
) -> None:
    paths = _build(tmp_path)
    methods = (paths.output_root / "03_methods.tex").read_text(
        encoding="utf-8"
    )
    results = (paths.output_root / "04_results.tex").read_text(
        encoding="utf-8"
    )

    assert methods.count(r"\input{\ProjectRoot/table_01.tex}") == 1
    assert methods.count(r"\input{\ProjectRoot/figure_01.tex}") == 1
    for number in range(2, 5):
        assert results.count(
            rf"\input{{\ProjectRoot/figure_{number:02d}.tex}}"
        ) == 1
    for number in (2, 3, 4):
        assert results.count(
            rf"\input{{\ProjectRoot/table_{number:02d}.tex}}"
        ) == 1
    assert results.index(r"\input{\ProjectRoot/table_02.tex}") < results.index(
        "Medium falsification study"
    )
    assert "table_05.tex" not in results
    assert "figure_05.tex" not in results
    assert results.index(r"\input{\ProjectRoot/figure_04.tex}") < results.index("Medium falsification study")
    assert results.index(r"\input{\ProjectRoot/figure_04.tex}") < results.index(r"\FloatBarrier") < results.index("Medium falsification study")

    all_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in paths.output_root.rglob("*.tex")
    ) + paths.review_entry.read_text(encoding="utf-8")
    assert "E:\\" not in all_text
    assert "M3_PI_Guard_test" not in all_text
    assert "![Figure" not in all_text
    assert "[@L" not in all_text

    labels = re.findall(r"\\label\{([^}]+)\}", all_text)
    assert len(labels) == len(set(labels))
    assert "sec:methods-source-authority-counterfactual" in labels
    assert "sec:results-source-authority-counterfactual" in labels


def test_supplement_entry_includes_all_tables_and_historical_figures(tmp_path: Path) -> None:
    paths = _build(tmp_path)
    entry = paths.supplement_entry.read_text(encoding="utf-8")
    assert re.findall(r"supplement_s(\d+)\.tex", entry) == [f"{n:02d}" for n in range(1, 21)]
    assert re.findall(r"historical_figure_s(\d+)\.tex", entry) == [f"{n:02d}" for n in range(1, 6)]
    assert "current_" not in entry
    for number, filename in builder.HISTORICAL_FIGURE_FILES.items():
        assert (paths.output_root / filename).read_bytes() == (builder.HISTORICAL_FIGURE_SOURCE_DIR / filename).read_bytes()
        figure = (paths.output_root / f"historical_figure_s{number:02d}.tex").read_text(encoding="utf-8")
        assert rf"\label{{fig:S{number:02d}}}" in figure
        assert filename in figure


def test_figure_caption_parser_rejects_duplicate_or_incomplete_sets() -> None:
    source = "\n\n".join(f"**Figure {n}. Title.** Description." for n in range(1, 5))
    assert set(builder._parse_figure_captions(source)) == {1, 2, 3, 4}
    with pytest.raises(builder.LatexBuildError, match="Duplicate"):
        builder._parse_figure_captions(source + "\n\n**Figure 4. Title.** Description.")
    with pytest.raises(builder.LatexBuildError, match="Expected"):
        builder._parse_figure_captions(source.replace("Figure 4.", "Figure 5."))


def test_portrait_wide_panels_preserve_every_row_and_column_without_new_numbers() -> None:
    table = builder.MarkdownTable(
        number="S14", title="Controlled table", note="Original note.",
        header=tuple(f"column{i}" for i in range(10)),
        rows=tuple(tuple(f"r{r}c{c}" for c in range(10)) for r in range(3)),
    )
    rendered = builder._render_numbered_table(table)
    assert rendered.count(r"\begin{longtable}") == 4
    assert rendered.count(r"\label{tab:s14}") == 1
    assert rendered.count(r"\addtocounter{table}{-1}") == 3
    assert re.findall(r"\\renewcommand\{\\theHtable\}\{([^}]+)\}", rendered) == [
        "s14.part1", "s14.part2", "s14.part3", "s14.part4",
    ]
    for row in table.rows:
        for i, value in enumerate(row):
            assert len(re.findall(rf"(?<!\w){value}(?!\w)", rendered)) == (4 if i < 2 else 1)
    assert "Original note." in rendered
    assert all(token not in rendered for token in ("sidewaystable", r"\scriptsize", r"\resizebox"))


def test_word_list_line_breaks_preserve_numeric_fractions() -> None:
    assert builder._table_inline("ND/policy/full") == r"ND/\allowbreak{}policy/\allowbreak{}full"
    assert builder._table_inline("0/30") == "0/30"
