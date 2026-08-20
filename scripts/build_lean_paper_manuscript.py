"""Build the reader-facing lean SCI Q2 manuscript from reviewed section files."""

from __future__ import annotations

import csv
import re
from collections import OrderedDict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT_DIR = PROJECT_ROOT / "docs/research/paper_v2/manuscript"
FIGURE_DIR = PROJECT_ROOT / "docs/research/paper_v2/lean_empirical/figures_deepseek_v1"
TABLE_DIR = PROJECT_ROOT / "docs/research/paper_v2/lean_empirical/tables_deepseek_v1"
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

TABLE_NOTES = (
    "Providers, benchmarks, conditions, authorization regimes and frozen "
    "work-item counts for the lean empirical study. Gemini counts are planned; "
    "its incomplete rows are excluded from inference.",
    "Unsafe effects among attack tasks and completions among benign tool "
    "tasks. Brackets contain Wilson 95% confidence intervals.",
    "Absolute percentage-point differences use the second condition minus "
    "the first. Stress-regime extensions are outside the primary Holm family.",
    "ASK and DENY cells report event totals, record incidence and the share "
    "of records affected. Failures remain in the ITT denominator.",
    "Endpoint counts by benchmark and attack family. These prespecified "
    "strata are descriptive rather than additional confirmatory families.",
    "Cumulative tasks with at least one unsafe effect through budgets 50 and "
    "200. These two points do not establish attack saturation.",
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


def _number_subsections(body: str, *, section_number: int) -> str:
    counters = [0, 0, 0]
    numbered: list[str] = []
    for line in body.splitlines():
        heading = re.match(r"^(#{3,5})\s+(.+)$", line)
        if not heading:
            numbered.append(line)
            continue

        marks, title = heading.groups()
        if title.startswith(("Table ", "Supplementary Table ", "Figure ")):
            numbered.append(line)
            continue

        depth = len(marks) - 3
        if depth > 0 and counters[depth - 1] == 0:
            raise ManuscriptBuildError(
                f"Nested heading lacks a parent in section {section_number}: {title}"
            )
        counters[depth] += 1
        for index in range(depth + 1, len(counters)):
            counters[index] = 0
        prefix = ".".join(
            str(value) for value in (section_number, *counters[: depth + 1])
        )
        numbered.append(f"{marks} {prefix} {title}")
    return "\n".join(numbered)


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


def _read_table(name: str) -> list[dict[str, str]]:
    path = TABLE_DIR / name
    if not path.is_file():
        raise ManuscriptBuildError(f"Missing paper table: {path}")
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _label(value: str) -> str:
    special = {
        "deepseek": "DeepSeek",
        "gemini": "Gemini",
        "agentdojo-v1": "AgentDojo",
        "m3-v2": "M3-v2",
        "m3_full": "M3-full",
        "m3_policy_only": "Policy-only",
        "strongest_peer_reviewed_structural_baseline": "Structural baseline",
        "auto_policy_to_full": "Policy-only auto to M3-full auto",
        "exact_policy_to_full": "Policy-only exact to M3-full exact",
        "full_auto_to_exact": "M3-full auto to exact",
        "policy_auto_to_exact": "Policy-only auto to exact",
        "full_auto_to_broad": "M3-full auto to broad",
        "full_auto_to_conflicting": "M3-full auto to conflicting",
        "full_auto_to_underspecified": "M3-full auto to underspecified",
        "task_completion": "Benign-tool TCR",
        "benign_tool_tcr": "Benign-tool TCR",
        "unsafe_effect": "Unsafe effect",
    }
    return special.get(value, value.replace("_", " "))


def _percentage(value: str, *, signed: bool = False) -> str:
    number = float(value) * 100
    return f"{number:+.1f}" if signed else f"{number:.1f}%"


def _probability(value: str) -> str:
    if value == "not_in_primary_family":
        return "—"
    number = float(value)
    if number < 0.001 and number > 0:
        return f"{number:.2e}"
    return f"{number:.3f}"


def _markdown_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    def escape(value: str) -> str:
        return value.replace("|", "\\|")

    rendered = ["| " + " | ".join(headers) + " |"]
    rendered.append("|" + "|".join("---" for _ in headers) + "|")
    rendered.extend(
        "| " + " | ".join(escape(value) for value in row) + " |" for row in rows
    )
    return "\n".join(rendered)


def _design_table() -> str:
    groups: OrderedDict[tuple[str, str, str], dict[str, object]] = OrderedDict()
    for row in _read_table("table_1_design.csv"):
        key = (row["provider"], row["benchmark"], row["condition"])
        group = groups.setdefault(key, {"regimes": [], "records": 0})
        regimes = group["regimes"]
        if isinstance(regimes, list):
            regimes.append(_label(row["authorization_regime"]))
        group["records"] = int(group["records"]) + int(row["planned_records"])

    rows = [
        (
            _label(provider),
            _label(benchmark),
            _label(condition),
            ", ".join(group["regimes"]),
            str(group["records"]),
        )
        for (provider, benchmark, condition), group in groups.items()
    ]
    return _markdown_table(
        ("Provider", "Benchmark", "Condition", "Authorization regimes", "Planned n"),
        rows,
    )


def _endpoint_table() -> str:
    rows = []
    for row in _read_table("table_2_endpoints.csv"):
        unsafe = (
            f'{row["unsafe_n"]}/{row["attack_n"]} ({_percentage(row["unsafe_rate"])}) '
            f'[{_percentage(row["unsafe_ci_low"])}, {_percentage(row["unsafe_ci_high"])}]'
        )
        tcr = (
            f'{row["completed_n"]}/{row["benign_tool_n"]} ({_percentage(row["tcr"])}) '
            f'[{_percentage(row["tcr_ci_low"])}, {_percentage(row["tcr_ci_high"])}]'
        )
        rows.append((_label(row["condition"]), _label(row["authorization_regime"]), unsafe, tcr))
    return _markdown_table(
        ("Condition", "Authorization", "Unsafe effect, n/N (95% CI)", "Benign-tool TCR, n/N (95% CI)"),
        rows,
    )


def _paired_table() -> str:
    rows = []
    for row in _read_table("table_3_paired_effects.csv"):
        interval = (
            f'{_percentage(row["bootstrap_ci_low"], signed=True)}, '
            f'{_percentage(row["bootstrap_ci_high"], signed=True)}'
        )
        rows.append(
            (
                _label(row["endpoint"]),
                _label(row["comparison"]),
                row["paired_cases"],
                _percentage(row["difference_second_minus_first"], signed=True),
                f"[{interval}]",
                f'{row["discordant_first_only"]}/{row["discordant_second_only"]}',
                _probability(row["mcnemar_p"]),
                _probability(row["holm_p"]),
            )
        )
    return _markdown_table(
        ("Endpoint", "Comparison", "Paired n", "Difference (pp)", "Bootstrap 95% CI (pp)", "Discordant first/second", "McNemar p", "Holm p"),
        rows,
    )


def _burden_table() -> str:
    rows = []
    for row in _read_table("table_4_runtime_burden.csv"):
        rows.append(
            (
                _label(row["condition"]),
                _label(row["authorization_regime"]),
                f'{row["ask_count"]} / {row["ask_record_count"]} ({_percentage(row["ask_record_rate"])})',
                f'{row["deny_count"]} / {row["deny_record_count"]} ({_percentage(row["deny_record_rate"])})',
                f'{row["failure_count"]} ({_percentage(row["failure_rate"])})',
                f'{float(row["latency_p50_ms"]) / 1000:.2f} / {float(row["latency_p95_ms"]) / 1000:.2f}',
                f'{int(row["tokens"]):,}',
                f'{row["cost_currency"]} {float(row["cost_amount"]):.4f}',
            )
        )
    return _markdown_table(
        ("Condition", "Authorization", "ASK events/records", "DENY events/records", "Failures", "Latency p50/p95 (s)", "Tokens", "Cost"),
        rows,
    )


def _heterogeneity_table() -> str:
    rows = []
    for row in _read_table("table_5_heterogeneity.csv"):
        family = "pooled/no family label" if row["attack_family"] == "not_attack" else _label(row["attack_family"])
        rows.append(
            (
                _label(row["benchmark"]),
                family,
                row["records"],
                row["attack_records"],
                row["unsafe_effects"],
                row["operational_failures"],
            )
        )
    return _markdown_table(
        ("Benchmark", "Attack family/stratum", "Records", "Attack records", "Unsafe effects", "Operational failures"),
        rows,
    )


def _adaptive_table() -> str:
    rows = []
    for row in _read_table("table_6_adaptive_50_200.csv"):
        rows.append(
            (
                row["model"],
                row["budget"],
                f'{row["successes"]}/{row["total"]}',
                _percentage(row["rate"]),
                f'[{_percentage(row["ci_low"])}, {_percentage(row["ci_high"])}]',
                "Budgets 50 and 200 only; no saturation claim",
            )
        )
    return _markdown_table(
        ("Model", "Budget", "Successes", "Rate", "Wilson 95% CI", "Claim boundary"),
        rows,
    )


def _table_block() -> str:
    tables = (
        (1, "Experimental design", _design_table()),
        (2, "Joint primary endpoints", _endpoint_table()),
        (3, "Paired authorization and mechanism effects", _paired_table()),
        (4, "Runtime burden", _burden_table()),
        (5, "Prespecified heterogeneity", _heterogeneity_table()),
        (6, "Adaptive evidence at budgets 50 and 200", _adaptive_table()),
    )
    parts = ["## Tables"]
    for (number, title, table), note in zip(tables, TABLE_NOTES, strict=True):
        parts.append(f"### Table {number}. {title}\n\n{note}\n\n{table}")
    return "\n\n".join(parts)


def _submission_statements() -> str:
    body = _drop_wrapper(_read("submission_statements_draft.md"))
    return "## Submission statements\n\n" + body


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
        body = _number_subsections(body, section_number=int(heading.split(".", 1)[0]))
        parts.append(f"## {heading}\n\n{body}")

    caption_body = _drop_wrapper(
        _read("figure_table_captions_v1.md"),
        start_heading="## Figures",
        end_heading="## Tables",
    )
    caption_body = caption_body.removeprefix("### Figures\n").lstrip()
    parts.extend(
        [
            _figure_block(),
            _table_block(),
            "## Figure captions\n\n" + caption_body,
            _submission_statements(),
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
        "([L",
        "mechanism_paper_candidate",
        "exact_gold_*",
        "shard evidence reviews",
        "Author action:",
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
