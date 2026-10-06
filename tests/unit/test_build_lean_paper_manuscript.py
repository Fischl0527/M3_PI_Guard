from __future__ import annotations

import re
import json

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
    # 图链接指向实际实验产物；正文仍不能夹带工程路径说明。
    assert "outputs/" not in re.sub(r"\]\([^)]+\)", "]()", manuscript)
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
    assert len(re.findall(r"^### Table [1-8]\. ", manuscript, flags=re.MULTILINE)) == 8
    assert "Supplementary Table S1" in manuscript
    assert "Supplementary Table S6" in manuscript
    assert "Supplementary Table S10" in manuscript
    assert "Supplementary Table S12" in manuscript
    assert not re.search(
        r"^#### Supplementary Table S(?:[1-9]|1[0-2])\. ", manuscript, flags=re.MULTILINE
    )
    assert "### Figures" not in manuscript
    assert "22/60 tasks (36.67%" in manuscript
    assert "CNY 24.5551236" in manuscript
    assert "| Condition cell | Prompt | Modules | Authorization |" in manuscript
    assert "| Stratum | Tasks | Successes by 500 |" in manuscript
    assert "excluding evaluator and gold fields" not in manuscript
    assert "`exact_gold` condition is an explicitly labeled oracle sensitivity" in manuscript
    assert re.search(
        r"`exact_gold`\s+exposed only its derived authorization object",
        manuscript,
    )


def test_abstract_stays_within_jisa_limit() -> None:
    abstract, keywords = builder._abstract_and_keywords()

    assert builder._word_count(abstract) <= 250
    assert 1 <= len([item for item in keywords.split(";") if item.strip()]) <= 7


def test_current_results_precede_legacy_studies_without_loss() -> None:
    manuscript = builder.build_manuscript()
    results = manuscript.split("## 4. Results\n", 1)[1].split("## 5. Discussion", 1)[0]
    assert results.lstrip().startswith(
        "### 4.1 Corrected authorization and contemporaneous calibration"
    )
    assert results.count("795 workflows end normally") == 1
    assert results.count("### 4.2 Medium falsification study") == 1
    normalized = " ".join(results.split())
    assert "historical implementations and recorded endpoint labels" in normalized
    assert "Across the 384 paired confirmation cells" in normalized
    source = builder._drop_wrapper(
        builder._read("results_shell.md"), start_heading="## Medium falsification study"
    )
    cleaned, _ = builder._split_supplementary_tables(source)
    assert sorted(cleaned.split()) == sorted(builder._prioritize_corrected_results(cleaned).split())


def test_results_priority_rejects_missing_or_duplicate_current_section() -> None:
    with pytest.raises(builder.ManuscriptBuildError, match="exactly once"):
        builder._prioritize_corrected_results("### Legacy\n\nold")
    with pytest.raises(builder.ManuscriptBuildError, match="exactly once"):
        builder._prioritize_corrected_results(
            "### Corrected authorization and contemporaneous calibration\n\nx\n"
            "### Corrected authorization and contemporaneous calibration\n\ny"
        )


def test_introduction_and_chinese_distinguish_current_and_historical_evidence() -> None:
    intro = " ".join(builder._read("introduction_draft.md").split())
    assert "**RQ1: Authorization semantics.**" in intro
    assert "**RQ2: Security, utility, and runtime burden.**" in intro
    assert "**RQ3: Component evidence and applicability.**" in intro
    assert "900-assignment corrected" in intro
    assert "480-assignment contemporaneous" in intro
    assert "model-based secondary verification disabled" in intro
    assert "benchmark-intrinsic reversal" in intro
    assert "These studies do not establish full-module superiority" in intro
    assert "exact authorization produced opposite benign-tool directions" not in intro
    chinese = builder._read("manuscript_zh_v1.md")
    assert "修正版900条授权" in chinese
    assert "490个攻击条件分配" in chinese
    assert "17/30降至2/30" in chinese
    assert "−25.62至+3.10" in chinese
    assert "478/480" in chinese and "476/480" in chinese
    assert "历史完整参数相等判定" in chinese
    assert "原始答案不进入模型" in chinese
    assert "私有数据" in chinese and "V4.1 Flash" in chinese
    assert "中文旧表图尚待重排" in chinese


def test_corrected_primary_sources_disclose_utility_cost_and_uncertainty() -> None:
    abstract, _ = builder._abstract_and_keywords()
    normalized = " ".join(abstract.split())
    assert "900 authorization assignments" in normalized
    assert "480-assignment contemporaneous calibration" in normalized
    assert "17/30 to 2/30" in normalized
    assert "interval includes zero" in normalized
    assert "no unguarded control" in normalized
    assert "Exact authorization reduced pooled" not in normalized

    conclusion = " ".join(builder._read("conclusion_draft.md").split())
    assert "partial target annotations" in conclusion
    assert "not a deployable authorization source" in conclusion
    assert "not full-module superiority" in conclusion
    assert "two missing projection receipts" in conclusion
    assert "four missing structured safety receipts" in conclusion
    assert "476/480 assignments" in conclusion
    assert "completion collapse" in conclusion
    assert "intrinsic cost of precise authorization" in conclusion
    assert "fell by 56.67/40.00" not in conclusion


def test_corrected_results_keep_unknown_baseline_and_legacy_semantics_separate() -> None:
    manuscript = " ".join(builder.build_manuscript().split())
    assert "corrected_v2" in manuscript
    assert "exact_target_v2" in manuscript
    assert "corrected operationalization" in manuscript
    assert "not 490 independent tasks" in manuscript
    assert "795 workflows end normally" in manuscript
    assert "four AgentDojo attack positives among 28 known outcomes" in manuscript
    assert "4/30 lower bound and a 6/30 conservative upper bound" in manuscript
    assert "two field-projection receipts and four structured safety receipts" in manuscript
    assert "model-based secondary verification disabled" in manuscript
    assert "private/missing-classification simulated flow" in manuscript
    assert "task completion before a subsequent operational failure" in manuscript


def test_every_citation_key_exists_in_bibliography() -> None:
    builder._validate_citations(builder.build_manuscript())


def test_e7_reports_permission_only_and_preserves_external_validity_boundary() -> None:
    manuscript = builder.build_manuscript()
    normalized = " ".join(manuscript.split())
    assert "96 official DeepSeek V4 Pro proposal calls" in normalized
    assert "384 cells share 96 model proposals" in normalized
    assert "No effect backend was invoked" in normalized
    assert "not a correctly compiled exact policy" in normalized
    assert "All use the controlled M3-v2 runtime" in normalized
    assert "have not produced model-evaluation results" in normalized
    table = builder._e7_permit_table()
    assert "Strict exact / policy | 0/12 | 0/12 | 0/12" in table
    assert "Bounded enum / full | 12/12 | 12/12 | 0/12" in table
    assert "TCR" not in table and "completion" not in table


def test_e7_table_rejects_missing_semantic_correction(tmp_path, monkeypatch) -> None:
    path = tmp_path / "outputs/experiments/e7_confirmation_usability_v1/analysis_v1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"cells": []}), encoding="utf-8")
    monkeypatch.setattr(builder, "PROJECT_ROOT", tmp_path)
    with pytest.raises(builder.ManuscriptBuildError, match="permission-only semantics"):
        builder._e7_permit_table()


def test_active_reference_set_uses_current_primary_metadata() -> None:
    manuscript = builder.build_manuscript()
    bibliography = builder._read("references_v1.bib")
    active_keys = {
        key
        for group in re.findall(r"\[@([^\]]+)\]", manuscript)
        for key in re.findall(r"L\d{2}", group)
    }

    assert len(active_keys) == 24
    assert active_keys == {
        "L01", "L02", "L03", "L07", "L08", "L09", "L10",
        "L20", "L21", "L22", "L23", "L24", "L25", "L26",
        "L27", "L30", "L31", "L32", "L34", "L35", "L36",
        "L37", "L38", "L39",
    }
    agentspec = re.search(r"(?ms)^@inproceedings\{L20,\n(.*?)^\}", bibliography)
    asb = re.search(r"(?ms)^@inproceedings\{L34,\n(.*?)^\}", bibliography)
    attacker = re.search(r"(?ms)^@misc\{L27,\n(.*?)^\}", bibliography)
    assert agentspec is not None
    assert "conf.researchr.org/details/icse-2026" in agentspec.group(1)
    assert "10.1145/3744916.3764546" in agentspec.group(1)
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

    assert [number for number, _, _ in tables] == list(range(1, 13))
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
    assert (
        "Supplementary Table S12 reports the E6 paired effects and Gemini inference coverage."
        in cleaned
    )
    s12 = next(table for number, _, table in tables if number == 12)
    assert "Newcombe / cluster-bootstrap 95% CI" in s12
    assert "Exact McNemar / Holm p" in s12
    assert "0.000061 / 0.000122" in s12
    assert "Detailed values are reported" not in cleaned


def test_incremental_table_notes_preserve_claim_boundaries() -> None:
    notes = builder._table_notes()

    assert len(notes) == 8
    assert "contemporaneous cells" in notes[0]
    assert "separate evidence layers" in notes[2]
    assert "not a complete original-panel B500 curve" in notes[4]
    assert "historically risk-enriched single execution block" in notes[5]
    assert "not task completion or committed effects" in notes[6]


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
    normalized = " ".join(manuscript.split())

    assert manuscript.startswith(
        "# Evaluating Authorization Regimes and Runtime Guardrail Configurations"
    )
    assert "**RQ2: Prompt and runtime components.**" in manuscript
    assert "**RQ4: Source authority.**" in manuscript
    assert "**RQ5: Adaptive tail risk.**" in manuscript
    assert "**RQ6: Contemporaneous attack activity.**" in manuscript
    assert "**RQ2: Module contribution.**" not in manuscript
    assert "crosses prompt profile (`normal`/`safe`) with runtime modules" in normalized
    assert "its source swap varies provenance authority" in normalized
    assert "from 17/30 to 0/30" in manuscript
    assert "`unsafe_effect OR operational_failure`" in manuscript
    assert "robustness bound and is not reported as observed attack success" in manuscript
    assert "`ASK` is a runtime confirmation request" in manuscript
    assert "0/12" in manuscript and "24.25%" in manuscript
    assert "17/60" in manuscript
    assert "historically risk-enriched single execution block" in normalized
    assert "0/240 unauthorized proposals" in manuscript
    assert "30/240 authorized proposals" in manuscript
    assert "47/60 tasks were E3 anchors" in normalized
    assert re.search(r"29/30 tasks are\s+E3 anchors", manuscript)
    assert "does not satisfy or test the original multi-window activity gate" in normalized
    assert "Even complete prefix coverage would not make" in normalized
    assert "two-sided exact McNemar p-value" in normalized
    assert "planned cluster sign-flip test" in normalized
    assert "All Gemini paired, factorial, and cross-provider" in normalized
    assert "effects are therefore not estimable" in normalized
