"""Build the reader-facing lean SCI Q2 manuscript from reviewed section files."""

from __future__ import annotations

import csv
import json
import re
from collections import OrderedDict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT_DIR = PROJECT_ROOT / "docs/research/paper_v2/manuscript"
FIGURE_DIR = PROJECT_ROOT / "outputs/experiments/incremental_empirical_v1/figures"
TABLE_DIR = PROJECT_ROOT / "outputs/experiments/incremental_empirical_v1/tables"
OUTPUT_PATH = MANUSCRIPT_DIR / "manuscript_deepseek_v1.md"

TITLE = (
    "Evaluating Authorization Regimes and Runtime Guardrail Configurations "
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
    ("4. Results", "results_shell.md", "## Medium falsification study", None),
    ("5. Discussion", "discussion_draft.md", None, None),
    ("6. Conclusion", "conclusion_draft.md", None, None),
)

FIGURES = (
    (1, "figure_1_authority_boundary.png", "Online fields and the source-authority boundary."),
    (2, "figure_2_factorial_interactions.png", "Prompt, runtime-module, and interaction effects."),
    (3, "figure_3_provenance_counterfactual.png", "Source-authority counterfactual decisions and action changes."),
    (4, "figure_4_factor_effect_forest.png", "Factor effects across representative, enriched, and Flash cohorts."),
    (5, "figure_5_adaptive_tail.png", "Complete B50/B200 evidence and the conditional B200-survivor tail."),
)

TABLE_NOTES = (
    "The four contemporaneous cells cross prompt profile with the runtime "
    "module bundle while holding authorization at auto_compiled.",
    "Absolute effects are probability differences; intervals use 10,000 "
    "case-cluster bootstrap replicates. Holm values apply only to E1's "
    "prespecified endpoint families.",
    "End-to-end source swaps and deterministic Guard replay are separate "
    "evidence layers and must not be interpreted as interchangeable.",
    "E3 is outcome-enriched and E4 is a same-provider replication. Neither "
    "opens a new significance family or estimates deployment prevalence.",
    "The tail probability is conditional on the prespecified B200 survivors; "
    "it is not a complete original-panel B500 curve or saturation estimate.",
    "E6 uses a historically risk-enriched single execution block; 47/60 tasks "
    "also anchor E3. It does not estimate deployment prevalence, benign utility, "
    "temporal repeatability, independent-sample replication, or a cross-provider effect.",
    "One-shot permits under trusted approval, not task completion or committed "
    "effects. Strict exact deliberately excludes the request's preferred but "
    "authorized wording. Each denominator is 12; Wilson 95% intervals are "
    "0.00%--24.25% for 0/12 and 75.75%--100.00% for 12/12. "
    "Attack prompts produced no unauthorized target proposal, so zero "
    "unauthorized permits do not establish attack resistance.",
    "Corrected-v1 development data, not a confirmatory comparison with historical "
    "runs. AgentDojo retains its native security checker; M3-v2 counts observed "
    "simulated effects. Fractions give numerator/observed denominator, not "
    "evidence that failures are safe. Unknown values, when present, are explicit. "
    "Each model has 288 planned executions including no-tool tasks; those tasks "
    "and operational status counts are described in the text. Flash is V4.1, "
    "not the historical V4 model.",
)


class ManuscriptBuildError(ValueError):
    """Raised when a source component cannot produce a defensible manuscript."""


def _split_supplementary_tables(
    body: str,
) -> tuple[str, list[tuple[int, str, str]]]:
    """Remove S1-S12 tables from Results while retaining narrative context."""

    lines = body.splitlines()
    cleaned: list[str] = []
    tables: list[tuple[int, str, str]] = []
    index = 0
    pattern = re.compile(r"^#{3,4} Supplementary Table S(\d+)\. (.+)$")

    while index < len(lines):
        match = pattern.match(lines[index])
        if match is None:
            cleaned.append(lines[index])
            index += 1
            continue

        number = int(match.group(1))
        title = match.group(2)
        index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines) or not lines[index].startswith("|"):
            raise ManuscriptBuildError(
                f"Supplementary Table S{number} lacks a Markdown table"
            )

        table_lines: list[str] = []
        while index < len(lines) and lines[index].startswith("|"):
            table_lines.append(lines[index])
            index += 1
        tables.append((number, title, "\n".join(table_lines)))
        reference_title = (
            title if re.match(r"^[A-Z]\d", title) else title[0].lower() + title[1:]
        )
        cleaned.extend(
            [f"Supplementary Table S{number} reports the {reference_title}.", ""]
        )
        while index < len(lines) and not lines[index].strip():
            index += 1

    tables.sort(key=lambda item: item[0])
    numbers = [number for number, _, _ in tables]
    if numbers != list(range(1, 13)):
        raise ManuscriptBuildError(
            f"Expected Supplementary Tables S1-S12, found {numbers}"
        )
    return "\n".join(cleaned).strip(), tables


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


def _prioritize_corrected_results(body: str) -> str:
    """Lead with corrected evidence without dropping legacy observations."""
    matches = list(
        re.finditer(
            r"^### Corrected authorization and contemporaneous calibration$",
            body,
            flags=re.MULTILINE,
        )
    )
    if len(matches) != 1:
        raise ManuscriptBuildError("Corrected Results section must occur exactly once")
    start = matches[0].start()
    following = re.search(r"^### ", body[matches[0].end() :], flags=re.MULTILINE)
    end = matches[0].end() + following.start() if following else len(body)
    current = body[start:end].strip()
    legacy = (body[:start].rstrip() + "\n\n" + body[end:].lstrip()).strip()
    return current + ("\n\n" + legacy if legacy else "")


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
        relative = Path("../../../../outputs/experiments/incremental_empirical_v1/figures") / filename
        lines.append(f"![Figure {number}. {caption}]({relative.as_posix()})")
        lines.append("")
    return "\n".join(lines).strip()


def _read_table(name: str) -> list[dict[str, str]]:
    path = TABLE_DIR / name
    if not path.is_file():
        raise ManuscriptBuildError(f"Missing paper table: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _table_notes() -> tuple[str, ...]:
    legacy_note = (
        " Historical tables retain their recorded endpoint, not a retrospectively "
        "verified count of committed unauthorized effects. See the measurement "
        "correction and separate corrected-v1 results."
    )
    return tuple(note + legacy_note if i in {1, 3, 4, 5} else note
                 for i, note in enumerate(TABLE_NOTES))


def _label(value: str) -> str:
    special = {
        "deepseek": "DeepSeek",
        "gemini": "Gemini",
        "agentdojo-v1": "AgentDojo",
        "m3-v2": "M3-v2",
        "m3_full": "Full package",
        "m3_policy_only": "Policy package",
        "strongest_peer_reviewed_structural_baseline": "Structural baseline",
        "auto_policy_to_full": "Auto: policy to full package",
        "exact_policy_to_full": "Exact: policy to full package",
        "full_auto_to_exact": "Full package: auto to exact",
        "policy_auto_to_exact": "Policy package: auto to exact",
        "full_auto_to_broad": "Full package: auto to broad",
        "full_auto_to_conflicting": "Full package: auto to conflicting",
        "full_auto_to_underspecified": "Full package: auto to underspecified",
        "task_completion": "Benign-tool TCR",
        "benign_tool_tcr": "Benign-tool TCR",
        "unsafe_effect": "Legacy risk endpoint",
        "attack_unsafe_or_operational_failure": "Legacy risk or failure",
        "no_defense": "No defense",
        "source_pinned_vigil": "Source-pinned VIGIL",
        "policy_normal": "Policy / normal",
        "policy_safe": "Policy / safe",
        "full_normal": "Full / normal",
        "full_safe": "Full / safe",
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


def _incremental_table(filename: str) -> str:
    source = _read_table(filename)
    if not source:
        raise ManuscriptBuildError(f"Incremental table is empty: {filename}")
    keys = tuple(source[0])
    labels = {
        "condition_cell": "Condition cell",
        "prompt_factor": "Prompt",
        "module_factor": "Modules",
        "authorization_regime": "Authorization",
        "historical_rows_reused": "Historical rows reused",
        "study": "Study",
        "endpoint": "Endpoint",
        "factor": "Factor",
        "paired_cases": "Paired cases",
        "absolute_effect": "Effect",
        "ci_low": "CI low",
        "ci_high": "CI high",
        "bootstrap_p": "Bootstrap p",
        "holm_adjusted_p": "Holm p",
        "bootstrap_replicates": "Bootstrap n",
        "stratum": "Stratum",
        "tasks": "Tasks",
        "successes_by_500": "Successes by 500",
        "conditional_probability": "Conditional probability",
        "first_success_queries": "First-success queries",
        "complete_original_b500_panel": "Complete original B500 panel",
        "unsafe_effect_wilson_95_ci": "Legacy risk, n/N (95% CI)",
        "operational_failure": "Operational failure",
        "unsafe_or_failure": "Legacy risk or failure",
        "ask_events": "ASK",
        "deny_events": "DENY",
    }

    def render(key: str, value: str) -> str:
        if value == "":
            return "—"
        if key in {"ci_low", "ci_high"} and filename.startswith("table_5_"):
            return f"{float(value) * 100:.2f}%"
        if key in {"absolute_effect", "ci_low", "ci_high"}:
            return f"{float(value) * 100:+.2f} pp"
        if key == "conditional_probability":
            return f"{float(value) * 100:.2f}%"
        if key in {"bootstrap_p", "holm_adjusted_p"}:
            return f"{float(value):.4f}"
        if value in {"True", "False"}:
            return "Yes" if value == "True" else "No"
        return _label(value)

    rows = [tuple(render(key, row.get(key, "")) for key in keys) for row in source]
    headers = tuple(labels.get(key, key.replace("_", " ").title()) for key in keys)
    return _markdown_table(headers, rows)


def _e6_activity_table() -> str:
    labels = {
        "no_defense": "No defense",
        "strongest_peer_reviewed_structural_baseline": "Source-pinned VIGIL",
        "m3_policy_only": "Policy / normal",
        "m3_policy_safe_prompt": "Policy / safe",
        "m3_full_normal_prompt": "Full / normal",
        "m3_full": "Full / safe",
    }
    rows = []
    for row in _read_table("table_6_e6_activity_calibration.csv"):
        total = int(row["planned"])
        unsafe = int(row["unsafe_n"])
        failure = int(row["operational_failure_n"])
        bound = int(row["unsafe_or_failure_n"])
        rows.append(
            (
                labels[row["condition"]],
                f"{unsafe}/{total} ({float(row['unsafe_rate']) * 100:.1f}%) "
                f"[{float(row['unsafe_ci_low']) * 100:.1f}%, "
                f"{float(row['unsafe_ci_high']) * 100:.1f}%]",
                f"{failure}/{total} ({failure / total * 100:.1f}%)",
                f"{bound}/{total} ({bound / total * 100:.1f}%)",
                row["ask_events"],
                row["deny_events"],
            )
        )
    return _markdown_table(
        (
            "Condition",
            "Legacy risk, n/N (95% CI)",
            "Operational failure",
            "Legacy risk or failure",
            "ASK events",
            "DENY events",
        ),
        rows,
    )


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
        sensitivity = (
            f'{row["unsafe_or_failure_n"]}/{row["attack_n"]} '
            f'({_percentage(row["unsafe_or_failure_rate"])}) '
            f'[{_percentage(row["unsafe_or_failure_ci_low"])}, '
            f'{_percentage(row["unsafe_or_failure_ci_high"])}]'
        )
        rows.append(
            (
                _label(row["provider"]),
                _label(row["condition"]),
                _label(row["authorization_regime"]),
                unsafe,
                sensitivity,
                tcr,
            )
        )
    return _markdown_table(
        (
            "Provider",
            "Condition",
            "Authorization",
            "Unsafe effect, n/N (95% CI)",
            "Unsafe or failure, n/N (95% CI)",
            "Benign-tool TCR, n/N (95% CI)",
        ),
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
                _label(row["provider"]),
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
        (
            "Provider",
            "Endpoint",
            "Comparison",
            "Paired n",
            "Difference (pp)",
            "Bootstrap 95% CI (pp)",
            "Discordant first/second",
            "McNemar p",
            "Holm p",
        ),
        rows,
    )


def _burden_table() -> str:
    rows = []
    for row in _read_table("table_4_runtime_burden.csv"):
        rows.append(
            (
                _label(row["provider"]),
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
        (
            "Provider",
            "Condition",
            "Authorization",
            "ASK events/records",
            "DENY events/records",
            "Failures",
            "Latency p50/p95 (s)",
            "Tokens",
            "Cost",
        ),
        rows,
    )


def _benchmark_stratified_table() -> str:
    rows = []
    for row in _read_table("table_5_benchmark_stratified.csv"):
        first = f'{row["first_successes"]}/{row["first_total"]}'
        second = f'{row["second_successes"]}/{row["second_total"]}'
        interval = (
            f'{_percentage(row["bootstrap_ci_low"], signed=True)}, '
            f'{_percentage(row["bootstrap_ci_high"], signed=True)}'
        )
        rows.append(
            (
                _label(row["provider"]),
                _label(row["benchmark"]),
                _label(row["endpoint"]),
                _label(row["comparison"]),
                row["paired_cases"],
                first,
                second,
                _percentage(row["difference_second_minus_first"], signed=True),
                f"[{interval}]",
            )
        )
    return _markdown_table(
        (
            "Provider",
            "Benchmark",
            "Endpoint",
            "Comparison",
            "Paired n",
            "First n/N",
            "Second n/N",
            "Difference (pp)",
            "Bootstrap 95% CI (pp)",
        ),
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


def _e7_permit_table() -> str:
    path = PROJECT_ROOT / "outputs/experiments/e7_confirmation_usability_v1/analysis_v1.json"
    analysis = json.loads(path.read_text(encoding="utf-8"))
    if analysis.get("effect_semantics") != "permission_eligibility_only_no_backend_state_transition":
        raise ManuscriptBuildError("E7 permission-only semantics must be explicit")
    cells = {
        (cell["granularity"], cell["module"], cell["case_type"]): cell
        for cell in analysis["cells"] if cell["confirmation_mode"] == "approved"
    }
    if len(cells) != 8:
        raise ManuscriptBuildError("E7 requires eight approved-channel cells")
    rows = []
    for granularity, label in (("strict_exact", "Strict exact"), ("bounded_enum", "Bounded enum")):
        for module in ("policy", "full"):
            benign = cells[granularity, module, "benign_tool"]
            attack = cells[granularity, module, "attack"]
            # Frozen raw labels are preserved, but their audited meaning is
            # permission eligibility: no effect backend was invoked in E7a.
            rows.append((
                f"{label} / {module}",
                f"{benign['task_completion']}/{benign['planned_n']}",
                f"{attack['task_completion']}/{attack['planned_n']}",
                f"{attack['unsafe_effect']}/{attack['planned_n']}",
            ))
    return _markdown_table(
        ("Policy / modules", "Benign authorized permits", "Attack authorized permits", "Attack unauthorized permits"),
        rows,
    )


def _corrected_development_table() -> str:
    path = PROJECT_ROOT / "outputs/experiments/correctness_repair_v1/tables/endpoints.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        records = list(csv.DictReader(stream))
    lookup = {}
    for row in records:
        key = tuple(row[name] for name in (
            "model_group", "benchmark", "evaluation_case_type", "condition_id", "endpoint",
        ))
        if key in lookup:
            raise ManuscriptBuildError("Duplicate corrected development endpoint")
        lookup[key] = row

    def fraction(model, benchmark, kind, condition, endpoint):
        row = lookup[(model, benchmark, kind, condition, endpoint)]
        if int(row["n_observed"]) + int(row["n_unknown"]) != int(row["n_plan"]):
            raise ManuscriptBuildError("Inconsistent corrected endpoint denominator")
        return f'{row["x"]}/{row["n_observed"]}' + (
            f' ({row["n_unknown"]} unknown)' if int(row["n_unknown"]) else ""
        )

    rows = []
    conditions = (
        ("no_defense", "No guard / normal"), ("safe_prompt_only", "No guard / safe"),
        ("m3_policy_only", "Policy / normal"), ("m3_policy_safe_prompt", "Policy / safe"),
        ("m3_full_normal_prompt", "Full / normal"), ("m3_full", "Full / safe"),
    )
    for model, label in (("deepseek_pro", "V4 Pro"), ("deepseek_flash", "V4.1 Flash")):
        for benchmark, benchmark_label in (("agentdojo-v1", "AgentDojo"), ("m3-v2", "M3-v2")):
            for condition, condition_label in conditions:
                rows.append((label, benchmark_label, condition_label,
                    fraction(model, benchmark, "attack", condition, "unsafe_effect"),
                    fraction(model, benchmark, "benign_tool", condition, "task_completion")))
    return _markdown_table(("Model", "Benchmark", "Configuration", "Attack endpoint", "Benign tool completion"), rows)


def _table_block() -> str:
    tables = (
        (1, "Prompt-by-module factorial design", _incremental_table("table_1_factor_design.csv")),
        (2, "E1 factorial estimates", _incremental_table("table_2_e1_factor_estimates.csv")),
        (3, "E2 source-authority evidence", _incremental_table("table_3_e2_provenance.csv")),
        (4, "E3/E4 conditional robustness", _incremental_table("table_4_e3_e4_robustness.csv")),
        (5, "E5 conditional adaptive tail", _incremental_table("table_5_e5_adaptive_tail.csv")),
        (6, "E6 contemporaneous attack-activity calibration", _e6_activity_table()),
        (7, "E7a execution-permit diagnostic", _e7_permit_table()),
        (8, "Corrected development study by benchmark", _corrected_development_table()),
    )
    parts = ["## Tables"]
    for (number, title, table), note in zip(tables, _table_notes(), strict=True):
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
        if filename == "results_shell.md":
            body, _ = _split_supplementary_tables(body)
            body = _prioritize_corrected_results(body)
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
    reader_text = re.sub(r"\]\([^)]+\)", "]()", manuscript)
    present = [token for token in forbidden if token in reader_text]
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
