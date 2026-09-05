from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT_DIR = REPO_ROOT / "docs" / "research" / "paper_v2" / "manuscript"
FIGURE_SOURCE_DIR = (
    REPO_ROOT
    / "docs"
    / "research"
    / "paper_v2"
    / "incremental_empirical_v1"
    / "figures"
)
TEMPLATE_DIR = REPO_ROOT / "LaTeX通用模板"
OUTPUT_DIR = TEMPLATE_DIR / "M3_PI_Guard_JISA"
REVIEW_ENTRY = TEMPLATE_DIR / "数模通用模板.tex"
LEGACY_REVIEW_ENTRY = TEMPLATE_DIR / "M3_PI_Guard_template_review.tex"

MAIN_MARKDOWN = "manuscript_deepseek_v1.md"
SUPPLEMENT_MARKDOWN = "supplementary_tables_v1.md"
BIBLIOGRAPHY = "references_v1.bib"

FIGURE_FILES = {
    1: "figure_1_authority_boundary.pdf",
    2: "figure_2_factorial_interactions.pdf",
    3: "figure_3_provenance_counterfactual.pdf",
    4: "figure_4_factor_effect_forest.pdf",
    5: "figure_5_adaptive_tail.pdf",
}

SECTION_FILES = {
    "1. Introduction": "01_introduction.tex",
    "2. Related work": "02_related_work.tex",
    "3. Methods": "03_methods.tex",
    "4. Results": "04_results.tex",
    "5. Discussion": "05_discussion.tex",
    "6. Conclusion": "06_conclusion.tex",
}

PLACEMENTS = {
    "3. Methods": {
        "3.8 Concurrent prompt-by-module factorial": ("table_01",),
        "3.9 Source-authority counterfactual": ("figure_01",),
    },
    "4. Results": {
        "4.8 Concurrent prompt-by-module factorial experiment": (
            "figure_02",
            "table_02",
        ),
        "4.9 Source-authority counterfactual": ("figure_03", "table_03"),
        "4.10 Outcome-enriched challenge and Flash replication": (
            "figure_04",
            "table_04",
        ),
        "4.12 Defense-aware adaptive evidence and conditional tail through budget 500": (
            "figure_05",
            "table_05",
        ),
        "4.13 Authorization diagnostics and execution permits": ("table_07",),
    },
}

# A rotated wide-table float always starts on a fresh page.  For E6, placing
# that table after the two short supplementary-table pointers stranded those
# lines on an otherwise blank page.  The semantic order remains unchanged if
# the primary result table appears first and the pointers follow it, while the
# rendered article avoids the isolated-page artefact.
PLACEMENTS_BEFORE_TEXT = {
    "4. Results": {
        "Supplementary Table S11 reports the E6 DeepSeek activity and operational outcomes.": (
            "table_06",
        ),
    },
}

# The manuscript discusses E6 before E5, so table numbers must follow rendered
# order rather than experiment identifiers.  Source Table 6 (E6) is the fifth
# numbered table encountered; source Table 5 (E5) is the sixth.
MAIN_TABLE_DISPLAY_NUMBERS = {5: 6, 6: 5}


class LatexBuildError(RuntimeError):
    """Raised when a source cannot be converted without silent content loss."""


@dataclass(frozen=True)
class MarkdownTable:
    number: str
    title: str
    note: str
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class BuildPaths:
    official_entry: Path
    review_entry: Path
    supplement_entry: Path
    output_root: Path


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise LatexBuildError(f"Required source is missing: {path}") from exc


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.rstrip() + "\n"
    path.write_text(normalized, encoding="utf-8", newline="\n")


def _split_h2(markdown: str) -> tuple[str, dict[str, str]]:
    title_match = re.search(r"(?m)^# (.+)$", markdown)
    if title_match is None:
        raise LatexBuildError("The manuscript has no level-one title.")

    matches = list(re.finditer(r"(?m)^## (.+)$", markdown))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[match.group(1).strip()] = markdown[match.end() : end].strip()
    return title_match.group(1).strip(), sections


def _join_hard_hyphen_wraps(markdown: str) -> str:
    """Undo source-editor wrapping after a lexical hyphen, without changing files."""

    return re.sub(r"(?<=\S)-\r?\n[ \t]*(?=\S)", "-", markdown)


def _strip_number(title: str) -> str:
    return re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", title).strip()


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value or "section"


def _inline(text: str) -> str:
    protected: dict[str, str] = {}

    def protect(latex: str) -> str:
        token = f"@@LATEX{len(protected):04d}@@"
        protected[token] = latex
        return token

    def code_replacement(match: re.Match[str]) -> str:
        # xurl's nolinkurl keeps code-like typography while allowing long API,
        # class and condition names to break at safe character boundaries.
        return protect(r"\nolinkurl{" + match.group(1) + "}")

    def citation_replacement(match: re.Match[str]) -> str:
        keys = re.findall(r"L\d{2}", match.group(1))
        if not keys:
            raise LatexBuildError(f"Citation contains no supported key: {match.group(0)}")
        return protect(r"\citep{" + ",".join(keys) + "}")

    def url_replacement(match: re.Match[str]) -> str:
        raw = match.group(0)
        trailing = ""
        while raw and raw[-1] in ".,;:":
            trailing = raw[-1] + trailing
            raw = raw[:-1]
        return protect(r"\url{" + raw + "}") + trailing

    text = re.sub(r"`([^`]+)`", code_replacement, text)
    text = re.sub(r"\[@([^\]]+)\]", citation_replacement, text)
    text = re.sub(r"https?://[^\s)]+", url_replacement, text)

    text = re.sub(
        r"\*\*([^*]+)\*\*",
        lambda match: protect(r"\textbf{" + _inline(match.group(1)) + "}"),
        text,
    )
    text = re.sub(
        r"(?<!\*)\*([^*]+)\*(?!\*)",
        lambda match: protect(r"\textit{" + _inline(match.group(1)) + "}"),
        text,
    )
    text = re.sub(
        r"\bunauthorized\b",
        lambda _: protect(r"un\-au\-thor\-ized"),
        text,
    )

    text = text.replace("−", protect(r"\ensuremath{-}"))
    text = text.replace("×", protect(r"\ensuremath{\times}"))
    text = text.replace("—", "---").replace("–", "--")
    replacements = (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    for token, latex in protected.items():
        text = text.replace(token, latex)
    return text


def _is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _parse_table_lines(lines: list[str]) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    if len(lines) < 2 or not _is_table_separator(lines[1]):
        raise LatexBuildError("Malformed Markdown table: separator row is missing.")
    parsed = [tuple(cell.strip() for cell in line.strip().strip("|").split("|")) for line in lines]
    width = len(parsed[0])
    if any(len(row) != width for row in parsed):
        raise LatexBuildError("Malformed Markdown table: inconsistent column count.")
    return parsed[0], tuple(parsed[2:])


def _render_inline_table(lines: list[str]) -> str:
    header, rows = _parse_table_lines(lines)
    spec = "@{}" + "L" * len(header) + "@{}"
    output = [
        r"\begin{center}",
        r"\small",
        rf"\begin{{tabularx}}{{\linewidth}}{{{spec}}}",
        r"\toprule",
        " & ".join(_inline(cell) for cell in header) + r" \\",
        r"\midrule",
    ]
    output.extend(" & ".join(_inline(cell) for cell in row) + r" \\" for row in rows)
    output.extend([r"\bottomrule", r"\end{tabularx}", r"\end{center}"])
    return "\n".join(output)


def _inject_after_subsections(markdown: str, placements: dict[str, tuple[str, ...]]) -> str:
    lines = markdown.splitlines()
    inserts: list[tuple[int, tuple[str, ...]]] = []
    for heading, artifacts in placements.items():
        marker = f"### {heading}"
        try:
            start = lines.index(marker)
        except ValueError as exc:
            raise LatexBuildError(f"Placement heading is missing: {heading}") from exc
        end = len(lines)
        for index in range(start + 1, len(lines)):
            if lines[index].startswith("### "):
                end = index
                break
        inserts.append((end, artifacts))

    for index, artifacts in sorted(inserts, reverse=True):
        directives = [f"@@ARTIFACT:{artifact}@@" for artifact in artifacts]
        lines[index:index] = ["", *directives, ""]
    return "\n".join(lines)


def _inject_before_text(
    markdown: str,
    placements: dict[str, tuple[str, ...]],
) -> str:
    lines = markdown.splitlines()
    for anchor, artifacts in placements.items():
        try:
            index = lines.index(anchor)
        except ValueError as exc:
            raise LatexBuildError(f"Placement anchor is missing: {anchor}") from exc
        directives = [f"@@ARTIFACT:{artifact}@@" for artifact in artifacts]
        lines[index:index] = [*directives, ""]
    return "\n".join(lines)


def _markdown_blocks(
    markdown: str,
    *,
    unnumbered_headings: bool = False,
    label_prefix: str | None = None,
) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        artifact = re.fullmatch(r"@@ARTIFACT:([a-z0-9_]+)@@", line.strip())
        if artifact:
            output.append(rf"\input{{\ProjectRoot/{artifact.group(1)}.tex}}")
            index += 1
            continue

        heading = re.match(r"^(#{3,4}) (.+)$", line)
        if heading:
            title = _strip_number(heading.group(2))
            command = "subsection" if len(heading.group(1)) == 3 else "subsubsection"
            star = "*" if unnumbered_headings else ""
            output.append(rf"\{command}{star}{{{_inline(title)}}}")
            if not unnumbered_headings:
                label = "-".join(part for part in (label_prefix, _slug(title)) if part)
                output.append(rf"\label{{sec:{label}}}")
            index += 1
            continue

        if line.startswith("|") and index + 1 < len(lines) and _is_table_separator(lines[index + 1]):
            table_lines = [line]
            index += 1
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            output.append(_render_inline_table(table_lines))
            continue

        list_match = re.match(r"^(\d+)\.\s+(.+)$", line)
        bullet_match = re.match(r"^-\s+(.+)$", line)
        if list_match or bullet_match:
            ordered = list_match is not None
            item_pattern = r"^\d+\.\s+(.+)$" if ordered else r"^-\s+(.+)$"
            items: list[str] = []
            while index < len(lines):
                current = re.match(item_pattern, lines[index])
                if current is None:
                    break
                pieces = [current.group(1).strip()]
                index += 1
                while index < len(lines):
                    continuation = lines[index]
                    if not continuation.strip() or re.match(item_pattern, continuation):
                        break
                    if continuation.startswith(" "):
                        pieces.append(continuation.strip())
                        index += 1
                    else:
                        break
                items.append(" ".join(pieces))
                while index < len(lines) and not lines[index].strip():
                    index += 1
            environment = "enumerate" if ordered else "itemize"
            output.append(rf"\begin{{{environment}}}")
            output.extend(r"\item " + _inline(item) for item in items)
            output.append(rf"\end{{{environment}}}")
            continue

        paragraph = [line.strip()]
        index += 1
        while index < len(lines):
            candidate = lines[index]
            if not candidate.strip():
                break
            if re.match(r"^(#{3,4}) ", candidate):
                break
            if re.match(r"^(?:\d+\.|-)\s+", candidate):
                break
            if candidate.startswith("|") or candidate.startswith("@@ARTIFACT:"):
                break
            paragraph.append(candidate.strip())
            index += 1
        output.append(_inline(" ".join(paragraph)))

    return "\n\n".join(output)


def _parse_numbered_tables(markdown: str, *, supplementary: bool) -> list[MarkdownTable]:
    prefix = "Supplementary Table S" if supplementary else "Table "
    level = "##" if supplementary else "###"
    pattern = re.compile(
        rf"(?m)^{re.escape(level)} {re.escape(prefix)}(\d+)\. (.+)$"
    )
    matches = list(pattern.finditer(markdown))
    expected = 12 if supplementary else 7
    if len(matches) != expected:
        raise LatexBuildError(f"Expected {expected} tables, found {len(matches)}.")

    tables: list[MarkdownTable] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        block = markdown[match.end() : end].strip()
        block_lines = block.splitlines()
        table_start = next(
            (line_index for line_index, value in enumerate(block_lines) if value.startswith("|")),
            None,
        )
        if table_start is None:
            raise LatexBuildError(f"Table {match.group(1)} has no Markdown body.")
        table_lines: list[str] = []
        for value in block_lines[table_start:]:
            if not value.startswith("|"):
                break
            table_lines.append(value)
        header, rows = _parse_table_lines(table_lines)
        note = " ".join(value.strip() for value in block_lines[:table_start] if value.strip())
        number = f"S{match.group(1)}" if supplementary else match.group(1)
        tables.append(
            MarkdownTable(
                number=number,
                title=" ".join(match.group(2).split()),
                note=note,
                header=header,
                rows=rows,
            )
        )
    return tables


def _longtable_column_spec(column_count: int) -> str:
    width = rf"\dimexpr\linewidth/{column_count}-2\tabcolsep\relax"
    column = rf">{{\RaggedRight\arraybackslash}}p{{{width}}}"
    return "@{}" + f"*{{{column_count}}}{{{column}}}" + "@{}"


def _render_numbered_table(
    table: MarkdownTable,
    *,
    label_number: str | None = None,
) -> str:
    column_count = len(table.header)
    label_number = label_number or table.number.lower()
    # Wide evidence tables need the long edge of the sheet, but rotating the
    # *page* with pdflscape also rotates the template footer and moves its page
    # number to the left edge.  sidewaystable rotates only the float contents;
    # the physical page, template geometry, and footer stay portrait.
    wide = column_count >= 6
    font_size = (
        r"\scriptsize" if column_count >= 7 or table.number == "S12" else r"\footnotesize"
    )
    header = " & ".join(_inline(cell) for cell in table.header) + r" \\"
    body = [" & ".join(_inline(cell) for cell in row) + r" \\" for row in table.rows]

    if table.number == "7":
        # This four-row diagnostic must travel with its semantic-limit note.
        # longtable allowed the note to split over the next page in the review
        # template; an ordinary portrait float keeps the complete unit intact.
        lines = [
            r"\begin{table}[!htbp]",
            r"\centering\small",
            rf"\caption{{{_inline(table.title)}}}\label{{tab:{label_number}}}",
            r"\begin{tabularx}{\linewidth}{@{}LLLL@{}}",
            r"\toprule", header, r"\midrule", *body, r"\bottomrule",
            r"\end{tabularx}",
            r"\par\smallskip\RaggedRight",
            r"\textit{Note.} " + _inline(table.note),
            r"\end{table}",
        ]
        return "\n".join(lines)

    if wide:
        lines = [
            r"\clearpage",
            r"\begin{sidewaystable}[p]",
            r"\centering",
            r"\begin{minipage}{\textheight}",
            r"\centering",
            r"\begingroup",
            font_size,
            rf"\caption{{{_inline(table.title)}}}\label{{tab:{label_number}}}",
            rf"\begin{{tabular}}{{{_longtable_column_spec(column_count)}}}",
            r"\toprule",
            header,
            r"\midrule",
            *body,
            r"\bottomrule",
            r"\end{tabular}",
        ]
        if table.note:
            lines.extend(
                [
                    r"\par\vspace{0.35\baselineskip}",
                    r"\noindent\textit{Note.} " + _inline(table.note),
                ]
            )
        lines.extend(
            [
                r"\endgroup",
                r"\end{minipage}",
                r"\end{sidewaystable}",
                r"\clearpage",
            ]
        )
        return "\n".join(lines)

    lines = [
        r"\begingroup",
        font_size,
        r"\setlength{\LTpre}{0.5\baselineskip}",
        r"\setlength{\LTpost}{0.5\baselineskip}",
        rf"\begin{{longtable}}{{{_longtable_column_spec(column_count)}}}",
        rf"\caption{{{_inline(table.title)}}}\label{{tab:{label_number}}} \\",
        r"\toprule",
        header,
        r"\midrule",
        r"\endfirsthead",
        rf"\caption[]{{{_inline(table.title)} (continued)}} \\",
        r"\toprule",
        header,
        r"\midrule",
        r"\endhead",
        *body,
        r"\bottomrule",
        r"\end{longtable}",
    ]
    if table.note:
        lines.append(r"\noindent\textit{Note.} " + _inline(table.note))
    lines.append(r"\endgroup")
    return "\n".join(lines)


def _parse_figure_captions(markdown: str) -> dict[int, tuple[str, str]]:
    pattern = re.compile(
        r"\*\*Figure (\d+)\.\s*(.+?)\.\*\*\s*(.+?)(?=\n\n\*\*Figure|\Z)",
        flags=re.DOTALL,
    )
    captions: dict[int, tuple[str, str]] = {}
    for match in pattern.finditer(markdown):
        number = int(match.group(1))
        captions[number] = (
            " ".join(match.group(2).split()),
            " ".join(match.group(3).split()),
        )
    if set(captions) != set(FIGURE_FILES):
        raise LatexBuildError(f"Expected figure captions 1--5, found {sorted(captions)}.")
    return captions


def _render_figure(number: int, title: str, description: str) -> str:
    filename = FIGURE_FILES[number]
    caption = f"{title}. {description}"
    return "\n".join(
        [
            r"\begin{figure}[htbp]",
            r"\centering",
            rf"\includegraphics[width=\textwidth,height=0.82\textheight,keepaspectratio]{{\ProjectRoot/{filename}}}",
            rf"\caption{{{_inline(caption)}}}",
            rf"\label{{fig:{number:02d}}}",
            r"\end{figure}",
        ]
    )


def _extract_abstract_and_keywords(abstract_block: str) -> tuple[str, str]:
    match = re.search(r"(?m)^\*\*Keywords:\*\*\s*(.+)$", abstract_block)
    if match is None:
        raise LatexBuildError("The abstract has no Keywords line.")
    abstract = abstract_block[: match.start()].strip()
    keywords = match.group(1).strip()
    return _markdown_blocks(abstract), _inline(keywords)


def _bib_keys(bibliography: str) -> set[str]:
    return set(re.findall(r"(?m)^@[A-Za-z]+\{([^,]+),", bibliography))


def _citation_keys(markdown: str) -> set[str]:
    return set(re.findall(r"@([A-Za-z0-9_:-]+)", markdown))


def _official_entry(title: str) -> str:
    section_inputs = "\n".join(
        rf"\input{{\ProjectRoot/{filename}}}" for filename in SECTION_FILES.values()
    )
    return rf"""\documentclass[preprint,12pt]{{elsarticle}}
\usepackage{{booktabs,tabularx,longtable,array,graphicx,rotating,enumitem,microtype,ragged2e}}
\usepackage[hidelinks]{{hyperref}}
\usepackage{{xurl}}
\newcolumntype{{L}}{{>{{\RaggedRight\arraybackslash}}X}}
\newcommand{{\ProjectRoot}}{{.}}
\providecommand{{\tightlist}}{{\setlength{{\itemsep}}{{0pt}}\setlength{{\parskip}}{{0pt}}}}
\setlength{{\emergencystretch}}{{3em}}
\hyphenation{{un-au-thor-ized}}
\biboptions{{numbers,sort&compress}}
\journal{{Journal of Information Security and Applications}}

\begin{{document}}
\begin{{frontmatter}}
\title{{{_inline(title)}}}
\begin{{abstract}}
\input{{\ProjectRoot/abstract.tex}}
\end{{abstract}}
\begin{{keyword}}
\input{{\ProjectRoot/keywords.tex}}
\end{{keyword}}
\end{{frontmatter}}
\hypersetup{{pdfauthor={{}}}}

{section_inputs}
\input{{\ProjectRoot/declarations.tex}}

\bibliographystyle{{elsarticle-num}}
\bibliography{{\ProjectRoot/references}}
\end{{document}}
"""


def _review_entry(title: str) -> str:
    review_root = "M3_PI_Guard_JISA"
    section_inputs = "\n".join(
        rf"\input{{{review_root}/{filename}}}" for filename in SECTION_FILES.values()
    )
    return rf"""%! TEX program = xelatex
\documentclass[withoutpreface,bwprint]{{cumcmthesis}}
\usepackage{{rotating,microtype,ragged2e}}
\usepackage{{xurl}}
\usepackage[numbers,sort&compress]{{natbib}}
\setmainfont{{Times New Roman}}
\setsansfont{{Times New Roman}}
\setmonofont{{Times New Roman}}
\urlstyle{{same}}
\captionsetup[figure]{{font={{rm,minusfour,bf}}}}
\captionsetup[table]{{font={{rm,minusfour,bf}}}}
\newcolumntype{{L}}{{>{{\RaggedRight\arraybackslash}}X}}
\newcommand{{\ProjectRoot}}{{{review_root}}}
\providecommand{{\tightlist}}{{\setlength{{\itemsep}}{{0pt}}\setlength{{\parskip}}{{0pt}}}}
\setlength{{\emergencystretch}}{{3em}}
\hyphenation{{un-au-thor-ized}}
\renewcommand{{\thesection}}{{\arabic{{section}}}}
\renewcommand{{\thesubsection}}{{\thesection.\arabic{{subsection}}}}
\renewcommand{{\thesubsubsection}}{{\thesubsection.\arabic{{subsubsection}}}}
\renewcommand{{\abstractname}}{{Abstract}}
\renewcommand{{\figurename}}{{Figure}}
\renewcommand{{\tablename}}{{Table}}
\renewcommand{{\refname}}{{References}}
\makeatletter
\renewcommand*{{\mcm@cap@keywordsname}}{{Keywords}}
\renewcommand\keywords[1]{{%
  \par\vskip1ex
  {{\noindent\zihao{{-4}}\rmfamily\bfseries\mcm@cap@keywordsname:}}~{{#1}}%
}}
\makeatother
\title{{{_inline(title)}}}
\date{{}}

\begin{{document}}
\pagenumbering{{gobble}}
\maketitle
\hypersetup{{pdfauthor={{}}}}
\begin{{abstract}}
\input{{{review_root}/abstract.tex}}
\keywords{{\input{{{review_root}/keywords.tex}}}}
\end{{abstract}}
\pagenumbering{{arabic}}
\pagestyle{{plain}}

{section_inputs}
\input{{{review_root}/declarations.tex}}

\bibliographystyle{{gbt7714-numerical}}
\bibliography{{{review_root}/references}}
\end{{document}}
"""


def _supplement_entry(title: str) -> str:
    table_inputs = "\n".join(
        rf"\input{{\ProjectRoot/supplement_s{number:02d}.tex}}"
        for number in range(1, 13)
    )
    return rf"""\documentclass[preprint,12pt]{{elsarticle}}
\usepackage{{booktabs,tabularx,longtable,array,rotating,microtype,ragged2e}}
\usepackage[hidelinks]{{hyperref}}
\usepackage{{xurl}}
\newcolumntype{{L}}{{>{{\RaggedRight\arraybackslash}}X}}
\newcommand{{\ProjectRoot}}{{.}}
\providecommand{{\tightlist}}{{\setlength{{\itemsep}}{{0pt}}\setlength{{\parskip}}{{0pt}}}}
\setlength{{\emergencystretch}}{{3em}}
\hyphenation{{un-au-thor-ized}}
\renewcommand{{\thetable}}{{S\arabic{{table}}}}

\begin{{document}}
\begin{{frontmatter}}
\title{{Supplementary material for ``{_inline(title)}''}}
\end{{frontmatter}}
\hypersetup{{pdfauthor={{}}}}

These twelve tables provide detailed results referenced by the main manuscript.
They introduce no additional hypothesis family or claim beyond the analyses
reported in the article.

{table_inputs}
\end{{document}}
"""


def build(
    *,
    repo_root: Path = REPO_ROOT,
    output_root: Path | None = None,
    review_entry: Path | None = None,
) -> BuildPaths:
    manuscript_dir = repo_root / "docs" / "research" / "paper_v2" / "manuscript"
    figure_dir = (
        repo_root
        / "docs"
        / "research"
        / "paper_v2"
        / "incremental_empirical_v1"
        / "figures"
    )
    template_dir = repo_root / "LaTeX通用模板"
    output_root = output_root or template_dir / "M3_PI_Guard_JISA"
    use_canonical_template_entry = review_entry is None
    review_entry = review_entry or template_dir / "数模通用模板.tex"

    manuscript = _join_hard_hyphen_wraps(_read(manuscript_dir / MAIN_MARKDOWN))
    supplementary = _join_hard_hyphen_wraps(
        _read(manuscript_dir / SUPPLEMENT_MARKDOWN)
    )
    bibliography = _read(manuscript_dir / BIBLIOGRAPHY)
    title, sections = _split_h2(manuscript)

    required_sections = {
        "Abstract",
        *SECTION_FILES,
        "Tables",
        "Figure captions",
        "Submission statements",
    }
    missing_sections = sorted(required_sections - sections.keys())
    if missing_sections:
        raise LatexBuildError(f"Required manuscript sections are missing: {missing_sections}")

    cited = _citation_keys(manuscript)
    missing_citations = sorted(cited - _bib_keys(bibliography))
    if missing_citations:
        raise LatexBuildError(f"Citation keys missing from bibliography: {missing_citations}")

    abstract, keywords = _extract_abstract_and_keywords(sections["Abstract"])
    main_tables = _parse_numbered_tables(sections["Tables"], supplementary=False)
    supplement_tables = _parse_numbered_tables(supplementary, supplementary=True)
    captions = _parse_figure_captions(sections["Figure captions"])

    _write(output_root / "abstract.tex", abstract)
    _write(output_root / "keywords.tex", keywords)
    for heading, filename in SECTION_FILES.items():
        content = sections[heading]
        if heading in PLACEMENTS:
            content = _inject_after_subsections(content, PLACEMENTS[heading])
        if heading in PLACEMENTS_BEFORE_TEXT:
            content = _inject_before_text(
                content,
                PLACEMENTS_BEFORE_TEXT[heading],
            )
        latex = "\n\n".join(
            [
                rf"\section{{{_inline(_strip_number(heading))}}}",
                rf"\label{{sec:{_slug(_strip_number(heading))}}}",
                _markdown_blocks(
                    content,
                    label_prefix=_slug(_strip_number(heading)),
                ),
            ]
        )
        _write(output_root / filename, latex)

    declaration_body = "\n\n".join(
        [
            r"\section*{Declarations}",
            r"\addcontentsline{toc}{section}{Declarations}",
            _markdown_blocks(sections["Submission statements"], unnumbered_headings=True),
        ]
    )
    _write(output_root / "declarations.tex", declaration_body)

    for table in main_tables:
        source_number = int(table.number)
        display_number = MAIN_TABLE_DISPLAY_NUMBERS.get(source_number, source_number)
        _write(
            output_root / f"table_{source_number:02d}.tex",
            _render_numbered_table(table, label_number=str(display_number)),
        )
    for table in supplement_tables:
        _write(
            output_root / f"supplement_s{int(table.number[1:]):02d}.tex",
            _render_numbered_table(table),
        )

    for number, filename in FIGURE_FILES.items():
        source = figure_dir / filename
        if not source.is_file():
            raise LatexBuildError(f"Required vector figure is missing: {source}")
        destination = output_root / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        figure_title, figure_description = captions[number]
        _write(
            output_root / f"figure_{number:02d}.tex",
            _render_figure(number, figure_title, figure_description),
        )

    bibliography_output = output_root / "references.bib"
    bibliography_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(manuscript_dir / BIBLIOGRAPHY, bibliography_output)
    official_entry = output_root / "M3_PI_Guard_JISA.tex"
    supplement_entry = output_root / "M3_PI_Guard_JISA_supplement.tex"
    _write(official_entry, _official_entry(title))
    _write(supplement_entry, _supplement_entry(title))
    _write(review_entry, _review_entry(title))
    if use_canonical_template_entry:
        _write(
            template_dir / "M3_PI_Guard_template_review.tex",
            "% Compatibility entry; the user-supplied template is canonical.\n"
            "\\input{数模通用模板.tex}",
        )
    return BuildPaths(
        official_entry=official_entry,
        review_entry=review_entry,
        supplement_entry=supplement_entry,
        output_root=output_root,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the JISA LaTeX source package.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--review-entry", type=Path)
    args = parser.parse_args(argv)
    paths = build(
        repo_root=args.repo_root.resolve(),
        output_root=args.output_root.resolve() if args.output_root else None,
        review_entry=args.review_entry.resolve() if args.review_entry else None,
    )
    print(paths.official_entry)
    print(paths.review_entry)
    print(paths.supplement_entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
