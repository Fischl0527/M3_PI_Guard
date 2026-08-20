"""Build the reader-facing lean SCI Q2 manuscript from reviewed section files."""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT_DIR = PROJECT_ROOT / "docs/research/paper_v2/manuscript"
FIGURE_DIR = PROJECT_ROOT / "docs/research/paper_v2/lean_empirical/figures_deepseek_v1"
OUTPUT_PATH = MANUSCRIPT_DIR / "manuscript_deepseek_v1.md"

TITLE = (
    "Evaluating Runtime Authorization Under Context and Provenance Uncertainty "
    "for Tool-Using LLM Agents"
)

SECTION_FILES = (
    ("1. Introduction", "introduction_draft.md", None, None),
    (
        "2. Related work",
        "related_work_draft.md",
        "## Runtime verification and task alignment",
        "## Critical citation-context audit",
    ),
    ("3. Methods", "methods_draft.md", None, None),
    ("4. Results", "results_shell.md", "## Medium study disposition", None),
    ("5. Discussion", "discussion_draft.md", None, None),
    ("6. Conclusion", "conclusion_draft.md", None, None),
)

FIGURES = (
    (1, "figure_1_online_field_isolation.png", "Online authorization projection and offline evaluation boundary."),
    (2, "figure_2_safety_utility_pareto.png", "Security–utility trade-off by authorization condition."),
    (3, "figure_3_authorization_forest.png", "Paired authorization and mechanism effects."),
    (4, "figure_4_runtime_burden.png", "Runtime confirmation, blocking, failure, and latency burden."),
    (5, "figure_5_adaptive_first_success.png", "Adaptive first-success curve through query budget 200."),
)


class ManuscriptBuildError(ValueError):
    """Raised when a source component cannot produce a defensible manuscript."""


def _read(name: str) -> str:
    path = MANUSCRIPT_DIR / name
    if not path.is_file():
        raise ManuscriptBuildError(f"Missing manuscript component: {path}")
    return path.read_text(encoding="utf-8")


def _drop_wrapper(
    text: str,
    *,
    start_heading: str | None = None,
    end_heading: str | None = None,
) -> str:
    lines = text.splitlines()
    if start_heading is not None:
        try:
            lines = lines[lines.index(start_heading) :]
        except ValueError as exc:
            raise ManuscriptBuildError(
                f"Required section heading is missing: {start_heading}"
            ) from exc
    else:
        if lines and lines[0].startswith("# "):
            lines = lines[1:]
        lines = [line for line in lines if not line.startswith("Status: ")]

    if end_heading is not None:
        try:
            lines = lines[: lines.index(end_heading)]
        except ValueError as exc:
            raise ManuscriptBuildError(
                f"Required section boundary is missing: {end_heading}"
            ) from exc

    cleaned: list[str] = []
    for line in lines:
        if line.startswith("Controlling disposition:"):
            continue
        heading = re.match(r"^(#{2,5})(\s+.+)$", line)
        if heading:
            line = f"#{heading.group(1)}{heading.group(2)}"
        cleaned.append(line)

    body = "\n".join(cleaned).strip()
    body = re.sub(r"\b[Aa]dmitted\b", "completed", body)
    return body


def _abstract_and_keywords() -> tuple[str, str]:
    lines = _read("abstract_shell.md").splitlines()
    try:
        status_index = next(
            index for index, line in enumerate(lines) if line.startswith("Status: ")
        )
        keyword_index = next(
            index for index, line in enumerate(lines) if line.startswith("Keywords:")
        )
    except StopIteration as exc:
        raise ManuscriptBuildError("Abstract status/keyword boundary is missing") from exc

    abstract = "\n".join(lines[status_index + 1 : keyword_index]).strip()
    keyword_lines = [lines[keyword_index].removeprefix("Keywords:").strip()]
    keyword_lines.extend(line.strip() for line in lines[keyword_index + 1 :] if line.strip())
    keywords = " ".join(keyword_lines)
    return abstract, keywords


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'`-]*", text))


def _validate_citations(text: str) -> None:
    bibliography = _read("references_v1.bib")
    bibliography_keys = set(re.findall(r"@\w+\{([^,]+),", bibliography))
    citation_keys = set(re.findall(r"@([A-Za-z0-9:_-]+)", text))
    missing = sorted(citation_keys - bibliography_keys)
    if missing:
        raise ManuscriptBuildError(
            "Citation keys missing from references_v1.bib: " + ", ".join(missing)
        )


def _figure_block() -> str:
    lines = ["## Figures", ""]
    for number, filename, caption in FIGURES:
        path = FIGURE_DIR / filename
        if not path.is_file():
            raise ManuscriptBuildError(f"Missing paper figure: {path}")
        relative = Path("../lean_empirical/figures_deepseek_v1") / filename
        lines.append(f"![Figure {number}. {caption}]({relative.as_posix()})")
        lines.append("")
    return "\n".join(lines).strip()


def build_manuscript() -> str:
    abstract, keywords = _abstract_and_keywords()
    if _word_count(abstract) > 250:
        raise ManuscriptBuildError("Abstract exceeds the JISA 250-word limit")

    parts = [
        f"# {TITLE}",
        "## Abstract\n\n" + abstract,
        f"**Keywords:** {keywords}",
    ]
    for heading, filename, start_heading, end_heading in SECTION_FILES:
        body = _drop_wrapper(
            _read(filename),
            start_heading=start_heading,
            end_heading=end_heading,
        )
        parts.append(f"## {heading}\n\n{body}")

    caption_body = _drop_wrapper(_read("figure_table_captions_v1.md"))
    parts.extend(
        [
            _figure_block(),
            "## Figure and table captions\n\n" + caption_body,
            "## References\n\n"
            "References are supplied in `references_v1.bib` and rendered with "
            "the manuscript citation processor.",
        ]
    )
    manuscript = "\n\n".join(parts).strip() + "\n"

    forbidden = (
        "Status:",
        "SHA-256",
        "outputs/",
        "protocols/",
        "harness/",
        "Controlling disposition:",
        "[Insert",
        "[If",
        "Full Harness",
        "evidence-hash",
        "Git branch",
    )
    present = [token for token in forbidden if token in manuscript]
    if present:
        raise ManuscriptBuildError(
            "Reader-facing manuscript contains workflow metadata: "
            + ", ".join(present)
        )
    _validate_citations(manuscript)
    return manuscript


def main() -> int:
    manuscript = build_manuscript()
    OUTPUT_PATH.write_text(manuscript, encoding="utf-8", newline="\n")
    print(
        f"wrote={OUTPUT_PATH.relative_to(PROJECT_ROOT)} "
        f"words={_word_count(manuscript)} sections={len(SECTION_FILES)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
