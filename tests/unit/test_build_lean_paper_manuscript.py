from __future__ import annotations

import re

import pytest

from scripts import build_lean_paper_manuscript as builder


def test_build_manuscript_is_reader_facing_and_structurally_complete() -> None:
    manuscript = builder.build_manuscript()

    expected = [
        "## Abstract",
        "## 1. Introduction",
        "## 2. Related work",
        "## 3. Methods",
        "## 4. Results",
        "## 5. Discussion",
        "## 6. Conclusion",
        "## Figures",
        "## Tables",
        "## Figure captions",
        "## Submission statements",
        "## References",
    ]
    positions = [manuscript.index(heading) for heading in expected]
    assert positions == sorted(positions)
    assert "Status:" not in manuscript
    assert "SHA-256" not in manuscript
    assert "outputs/" not in manuscript
    assert "[Insert" not in manuscript
    assert "[If" not in manuscript
    assert "Full Harness" not in manuscript
    assert "evidence-hash" not in manuscript
    assert "Git branch" not in manuscript
    assert "Critical citation-context audit" not in manuscript
    assert "([L" not in manuscript
    assert "mechanism_paper_candidate" not in manuscript
    assert "exact_gold_*" not in manuscript
    assert "shard evidence reviews" not in manuscript
    assert "## Submission statements" in manuscript
    assert "### Data and code availability" in manuscript
    assert (
        "### Declaration of generative AI and AI-assisted technologies in the manuscript preparation process"
        in manuscript
    )
    assert manuscript.index("## Submission statements") < manuscript.index(
        "## References"
    )
    assert manuscript.count("![Figure ") == 5
    assert len(re.findall(r"^### Table [1-5]\. ", manuscript, flags=re.MULTILINE)) == 5
    assert "Supplementary Table S1" in manuscript
    assert "Supplementary Table S6" in manuscript
    assert "Supplementary Table S10" in manuscript
    assert not re.search(
        r"^#### Supplementary Table S(?:[1-9]|10)\. ", manuscript, flags=re.MULTILINE
    )
    assert "### Figures" not in manuscript
    assert "22/60 (36.7%)" in manuscript
    assert "CNY 0.3374" in manuscript
    assert "| Condition cell | Prompt factor | Module factor |" in manuscript
    assert "| Stratum | Tasks | Successes by 500 |" in manuscript
    assert "excluding evaluator and gold fields" not in manuscript
    assert "oracle-sensitivity `exact_gold` authorization" in manuscript
    assert re.search(
        r"`exact_gold`\s+exposed only its derived authorization object",
        manuscript,
    )


def test_abstract_stays_within_jisa_limit() -> None:
    abstract, keywords = builder._abstract_and_keywords()

    assert builder._word_count(abstract) <= 250
    assert 1 <= len([item for item in keywords.split(";") if item.strip()]) <= 7


def test_every_citation_key_exists_in_bibliography() -> None:
    builder._validate_citations(builder.build_manuscript())


def test_active_reference_set_uses_current_primary_metadata() -> None:
    manuscript = builder.build_manuscript()
    bibliography = builder._read("references_v1.bib")
    active_keys = {
        key
        for group in re.findall(r"\[@([^\]]+)\]", manuscript)
        for key in re.findall(r"L\d{2}", group)
    }

    assert len(active_keys) == 21
    assert active_keys == {
        "L01", "L02", "L03", "L07", "L08", "L09", "L10",
        "L20", "L21", "L22", "L23", "L24", "L25", "L26",
        "L27", "L30", "L31", "L32", "L34", "L35", "L36",
    }
    agentspec = re.search(r"(?ms)^@inproceedings\{L20,\n(.*?)^\}", bibliography)
    asb = re.search(r"(?ms)^@inproceedings\{L34,\n(.*?)^\}", bibliography)
    attacker = re.search(r"(?ms)^@misc\{L27,\n(.*?)^\}", bibliography)
    assert agentspec is not None
    assert "conf.researchr.org/details/icse-2026" in agentspec.group(1)
    assert "10.1145/3744916.3764546" not in agentspec.group(1)
    assert asb is not None
    assert "booktitle = {International Conference on Learning Representations}" in asb.group(1)
    assert "pages = {35331--35366}" in asb.group(1)
    assert attacker is not None
    assert "Against {LLM} Jailbreaks" in attacker.group(1)


def test_missing_citation_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    original_read = builder._read

    def fake_read(name: str) -> str:
        if name == "references_v1.bib":
            return "@article{known, title={Known}}"
        return original_read(name)

    monkeypatch.setattr(builder, "_read", fake_read)
    with pytest.raises(builder.ManuscriptBuildError, match="Citation keys missing"):
        builder._validate_citations("Unsupported [@missing].")


def test_generated_headings_are_numbered_once() -> None:
    manuscript = builder.build_manuscript()
    numbered = re.findall(r"^## ([1-6])\. ", manuscript, flags=re.MULTILINE)
    assert numbered == ["1", "2", "3", "4", "5", "6"]

    body = manuscript.split("## Figures", 1)[0]
    subsection_titles = re.findall(r"^### (.+)$", body, flags=re.MULTILINE)
    assert subsection_titles
    assert all(re.match(r"[1-6]\.\d+ ", title) for title in subsection_titles)
    nested_titles = re.findall(r"^#### (.+)$", body, flags=re.MULTILINE)
    assert all(
        title.startswith("Supplementary Table ")
        or re.match(r"[1-6]\.\d+\.\d+ ", title)
        for title in nested_titles
    )


def test_nested_heading_without_parent_fails_closed() -> None:
    with pytest.raises(builder.ManuscriptBuildError, match="lacks a parent"):
        builder._number_subsections("#### Orphan", section_number=3)


def test_supplementary_tables_are_split_without_losing_results_narrative() -> None:
    results = builder._drop_wrapper(
        builder._read("results_shell.md"),
        start_heading="## Medium falsification study",
    )

    cleaned, tables = builder._split_supplementary_tables(results)

    assert [number for number, _, _ in tables] == list(range(1, 11))
    assert all(table.startswith("|") for _, _, table in tables)
    assert "### Supplementary Table" not in cleaned
    assert "This audit supports only covered-path statements" in cleaned
    assert (
        "Supplementary Table S1 reports the online-state source audit." in cleaned
    )
    assert (
        "Supplementary Table S6 reports the defense-aware adaptive attack." in cleaned
    )
    assert (
        "Supplementary Table S10 reports the conditional adaptive-tail execution."
        in cleaned
    )
    assert "Detailed values are reported" not in cleaned


def test_incremental_table_notes_preserve_claim_boundaries() -> None:
    notes = builder._table_notes()

    assert len(notes) == 5
    assert "contemporaneous cells" in notes[0]
    assert "separate evidence layers" in notes[2]
    assert "not a complete original-panel B500 curve" in notes[4]


def test_incremental_table_formats_effects_and_conditional_probabilities(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        builder,
        "_read_table",
        lambda _name: [
            {
                "absolute_effect": "-0.01",
                "ci_low": "0.1",
                "ci_high": "0.3",
                "conditional_probability": "0.2",
                "complete_original_b500_panel": "False",
            }
        ],
    )

    rendered = builder._incremental_table("table_5_e5_adaptive_tail.csv")
    assert "-1.00 pp" in rendered
    assert "10.00%" in rendered and "30.00%" in rendered
    assert "20.00%" in rendered
    assert "No" in rendered


def test_incremental_revision_identifies_factors_and_keeps_claims_bounded() -> None:
    manuscript = builder.build_manuscript()

    assert manuscript.startswith(
        "# Evaluating Authorization Regimes and Runtime Guardrail Configurations"
    )
    assert "**RQ2: Prompt and runtime components.**" in manuscript
    assert "**RQ4: Source authority.**" in manuscript
    assert "**RQ5: Adaptive tail risk.**" in manuscript
    assert "**RQ2: Module contribution.**" not in manuscript
    assert "crosses prompt profile (`normal`/`safe`) with runtime modules" in manuscript
    assert "changing only provenance authority" in manuscript
    assert "from 17/30 to 0/30" in manuscript
    assert "`unsafe_effect OR operational_failure`" in manuscript
    assert "robustness bound and is not reported as observed attack success" in manuscript
    assert "`ASK` is a runtime confirmation request" in manuscript
