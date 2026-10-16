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
    assert manuscript.count("![Figure ") == 4
    assert len(re.findall(r"^### Table [1-4]\. ", manuscript, flags=re.MULTILINE)) == 4
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
    assert "| Study | Cases | Assignments | Conditions | Scope |" in manuscript
    assert "| Stratum | Tasks | Successes by 500 |" not in manuscript
    assert "Supplementary Table S19 reports execution-permit" in manuscript
    assert "Supplementary Table S20 separates" in manuscript
    assert "excluding evaluator and gold fields" not in manuscript
    assert "current `exact_target_v2` condition and historical `exact_gold` condition" in manuscript
    assert re.search(
        r"`exact_gold`\s+exposed only its derived authorization object",
        manuscript,
    )


def test_current_figures_replace_main_only_and_chinese_sync_is_idempotent() -> None:
    manuscript = builder.build_manuscript()
    figures = manuscript.split("## Figures\n", 1)[1].split("## Tables\n", 1)[0]
    assert "research_followup_20261006_v1/manuscript_figures" in figures
    assert "incremental_empirical_v1/figures" not in figures
    assert "**Figure 5." not in manuscript
    captions = manuscript.split("## Figure captions\n", 1)[1].split("## Submission statements", 1)[0]
    assert "oracle sensitivity" in captions
    assert "not a confidence interval" in captions
    assert "not adjudicated root causes" in captions
    chinese = builder._read("manuscript_zh_v1.md")
    synced = builder.sync_chinese_figures(chinese)
    assert builder.sync_chinese_figures(synced) == synced
    assert len(re.findall(r"!\[图 [1-4]\.", synced)) == 4
    assert len(re.findall(r"!\[补充图 S[1-5]\.", synced)) == 5
    assert synced.split("## 表\n", 1)[1] == chinese.split("## 表\n", 1)[1]


def test_chinese_sync_rejects_missing_historical_figure() -> None:
    source = builder._read("manuscript_zh_v1.md")
    source = source.replace("![补充图 S5.", "![图 5.") if "![补充图 S5." in source else source.replace("![图 5.", "![missing.")
    with pytest.raises(builder.ManuscriptBuildError, match="S1-S5"):
        builder.sync_chinese_figures(source)


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
    assert " ".join(results.split()).count("900 workflows, 795 end normally") == 1
    assert results.count("### 4.2 Medium falsification study") == 1
    normalized = " ".join(results.split())
    assert "Historical Public and incremental tables retain their recorded evaluator labels" in normalized
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
    assert "900-assignment authorization study" in intro
    assert "480-assignment contemporaneous" in intro
    assert "source-pinned VIGIL adaptation" in intro
    # 引言提出实际比较；完整解释边界集中到讨论，不强制在各章重复免责声明。
    assert "auto_compiled" in intro and "exact_target_v2" in intro
    assert "exact authorization produced opposite benign-tool directions" not in intro
    chinese = builder._read("manuscript_zh_v1.md")
    assert "900条授权研究" in chinese
    assert "490个攻击条件分配" in chinese
    assert "17/30降至2/30" in chinese
    assert "−25.62至+3.10" in chinese
    assert "478/480" in chinese and "476/480" in chinese
    assert "历史完整参数相等判定" in chinese
    assert "原始答案不进入模型" in chinese
    assert "私有数据" in chinese and "V4.1 Flash" in chinese
    assert "当前四张主图" in chinese
    assert "中文旧主图尚待重排" not in chinese


def test_completion_failure_and_latency_missingness_are_not_conflated() -> None:
    methods = " ".join(builder._read("methods_draft.md").split())
    assert "completion before a later failure, both observations are retained" in methods
    assert "Missing effect evidence remains unknown, not a safe zero" in methods
    assert "available-value denominator rather than imputing missing durations" in methods
    assert "and it cannot count as task completion" not in methods
    assert "same ordinary prompt" in methods
    assert "not part of that July--August service window" in methods


def test_trusted_intent_review_is_integrated_without_overclaim() -> None:
    manuscript = " ".join(builder.build_manuscript().split())
    assert "60 benign tool tasks" in manuscript
    assert "240 existing condition records" in manuscript
    assert "seven trusted application declarations" in manuscript
    assert "Thirteen further M3-v2 tasks" in manuscript
    assert "remaining ten M3-v2 tasks require confirmation" in manuscript
    limitations = manuscript.split("Limitations", 1)[1].split("Practical implications", 1)[0]
    assert "post-outcome" in limitations
    assert "without independent reviewer-agreement calibration" in limitations
    assert "redaction prevents resolving three mock-API completion mismatches" in limitations
    assert "distinguishes permission insufficiency from a declared-contract defect" in manuscript
    assert "A bounded trusted-intent review remains necessary" not in manuscript
    chinese = builder._read("manuscript_zh_v1.md")
    assert "四条件240份已有记录" in chinese
    assert "不是裁定的误阻断率" in chinese
    assert "本次没有建立新的有界合同违约" in chinese
    assert "受信意图审查仍待完成" not in chinese


def test_floor_limits_are_version_specific_not_restored_from_history() -> None:
    discussion = " ".join(builder._read("discussion_draft.md").split())
    current = " ".join(builder.build_manuscript(profile="current").split())
    assert "490 attack assignments, security events are zero" in current
    assert "only three AgentDojo control events and a zero-event M3-v2 control" in discussion
    assert "legacy risk labels are not corrected executed-effect estimates" in discussion
    assert "record totals are not independent sample totals" in discussion
    assert "Security-direction evidence comes mainly from the larger Public matrices" not in discussion


def test_current_article_preserves_full_working_draft_and_current_evidence() -> None:
    full = builder.build_manuscript()
    current = builder.build_manuscript(profile="current")
    normalized = " ".join(current.split())
    # 压缩重复限制后不再人为凑字数；完整章节、证据与上限仍受检查。
    assert 0 < builder.body_word_count(current) <= 8500
    assert builder.body_word_count(current) < builder.body_word_count(full)
    assert "900 workflows, 795 end normally" in normalized
    assert "480 assignments" in current
    assert "60 benign tool tasks" in current
    assert "not 490 independent tasks" in normalized
    assert "4/30 lower bound and a 6/30 conservative upper bound" in normalized
    assert "### 4.2 Medium falsification study" not in current
    assert "### 4.2 Medium falsification study" in full
    assert "Supplementary Tables S1-S20 retain" in current
    assert "0/240 false allows and 30/240 false blocks" in current
    assert "first legacy risk success" in normalized
    limitations = current.split("### 5.5 Limitations", 1)[1].split("### 5.6", 1)[0]
    assert "B500" in limitations and "saturation" in limitations
    assert current.count("![Figure ") == full.count("![Figure ") == 4
    assert len(re.findall(r"^### Table [1-4]\. ", current, re.MULTILINE)) == 4
    builder._validate_citations(current)


def test_current_profile_rejects_silent_missing_or_duplicate_sections() -> None:
    with pytest.raises(builder.ManuscriptBuildError, match="Missing current subsections"):
        builder._select_subsections("### A\n\ntext", ("B",))
    with pytest.raises(builder.ManuscriptBuildError, match="Duplicate subsection"):
        builder._select_subsections("### A\n\ntext\n\n### A\n\nagain", ("A",))
    with pytest.raises(builder.ManuscriptBuildError, match="Unknown manuscript profile"):
        builder.build_manuscript(profile="shorter_by_guess")


def test_current_chinese_is_separate_and_keeps_four_current_figures_and_tables() -> None:
    source = builder._read("manuscript_zh_v1.md")
    current = builder.build_current_chinese()
    assert builder._read("manuscript_zh_v1.md") == source
    assert "四条件240份已有记录" in current
    assert "本次没有建立新的有界合同违约" in current
    assert "### 4.2 历史中型证伪实验" not in current
    assert "## 历史补充表" not in current
    assert "## 历史补充图" not in current
    assert "0/240" in current and "30/240" in current
    assert len(re.findall(r"!\[图 [1-4]\.", current)) == 4
    assert len(re.findall(r"^### 表 [1-4]\. ", current, re.MULTILINE)) == 4
    assert re.findall(r"^## ([1-6])\. ", current, re.MULTILINE) == list("123456")


def test_corrected_primary_sources_disclose_utility_cost_and_uncertainty() -> None:
    abstract, _ = builder._abstract_and_keywords()
    normalized = " ".join(abstract.split())
    assert "900 DeepSeek Pro assignments" in normalized
    assert "480-assignment contemporaneous calibration" in normalized
    assert "17/30 to 2/30" in normalized
    assert "security difference uncertain" in normalized
    manuscript = " ".join(builder.build_manuscript(profile="current").split())
    assert "This authorization study contains no unguarded cell" in manuscript
    assert "Exact authorization reduced pooled" not in normalized

    conclusion = " ".join(builder._read("conclusion_draft.md").split())
    assert "partial target annotations" in manuscript
    # 结论只综合核心发现，完整缺失信息与oracle限制应保留在主稿而非逐章复述。
    assert "oracle" in manuscript
    assert "two field-projection receipts and four structured safety receipts" in manuscript
    assert "476/480" in manuscript
    assert "fell by 56.67/40.00" not in conclusion


def test_corrected_results_keep_unknown_baseline_and_legacy_semantics_separate() -> None:
    manuscript = " ".join(builder.build_manuscript().split())
    assert "corrected_v2" in manuscript
    assert "exact_target_v2" in manuscript
    assert "corrected operationalization" in manuscript
    assert "not 490 independent tasks" in manuscript
    assert "900 workflows, 795 end normally" in manuscript
    assert "four AgentDojo attack positives among 28 known outcomes" in manuscript
    assert "4/30 lower bound and a 6/30 conservative upper bound" in manuscript
    assert "two field-projection receipts and four structured safety receipts" in manuscript
    assert "model-based secondary verification disabled" in manuscript
    assert "restricted private and missing-classification simulated flows" in manuscript
    assert "task completion before a subsequent operational failure" in manuscript


def test_every_citation_key_exists_in_bibliography() -> None:
    builder._validate_citations(builder.build_manuscript())


def test_current_statistical_families_and_author_review_are_explicit() -> None:
    manuscript = " ".join(builder.build_manuscript(profile="current").split())
    assert "four contrasts form one Holm family" in manuscript
    assert "three-contrast family within each benchmark and endpoint" in manuscript
    assert "comparisons are descriptive and have no Holm-adjusted p value" in manuscript
    assert "Author review and approval of the resulting material must be completed before submission" in manuscript
    assert "The authors reviewed and revised the resulting material" not in manuscript
    chinese = builder.build_current_chinese()
    assert "四个比较单独构成Holm校正族" in chinese
    assert "作者必须在投稿前完成生成材料的审阅与批准" in chinese
    assert "生成 Word 对照稿" not in chinese


def test_current_cohort_nesting_and_limitations_survive_compression() -> None:
    current = builder.build_manuscript(profile="current")
    normalized = " ".join(current.split())
    assert "180 cases representing 153 underlying tasks" in normalized
    assert "All 120 calibration cases are also nested" in normalized
    assert "1,396 executions" in normalized
    assert "reuses 240 calibration records" in normalized
    assert "Case-pair McNemar tests are auxiliary" in normalized
    assert "12-assignment authorization prefix" in normalized
    assert "16-assignment calibration prefix" in normalized
    assert len(re.findall(r"^### \d\.\d+ Limitations$", current, re.M)) == 1
    assert "https://github.com/Fischl0527/M3_PI_Guard" in current
    assert "https://github.com/Fischl0527/RedTeam_LLM_Security" not in current
    assert "repository is private" in normalized
    assert "17/30" in current and "2/30" in current
    assert "−66.83" in current and "−26.80" in current
    assert "−25.62" in current and "+3.10" in current


def test_e7_reports_permission_only_and_preserves_external_validity_boundary() -> None:
    manuscript = builder.build_manuscript()
    normalized = " ".join(manuscript.split())
    assert "96 official DeepSeek V4 Pro proposal calls" in normalized
    assert "384 cells share 96 model proposals" in normalized
    assert "No effect backend was invoked" in normalized
    assert "not a correctly compiled exact policy" in normalized
    assert "All use the controlled M3-v2 runtime" in normalized
    assert "Native dynamic-environment model validation remains incomplete" in normalized
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
    notes = builder._historical_table_notes()

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
    assert "historical E1 concurrent factorial crosses both factors explicitly" in normalized
    assert "policy/normal, policy/safe, full/normal, and full/safe" in normalized
    assert "only source authority changes" in normalized
    assert "from 17/30 to 0/30" in manuscript
    assert "`unsafe_effect OR operational_failure`" in manuscript
    assert "robustness bound and is not reported as observed attack success" in manuscript
    assert "`ASK` is a runtime confirmation request" in manuscript
    assert "0/12" in manuscript and "24.25%" in manuscript
    assert "17/60" in manuscript
    assert "historically risk-enriched single execution block" in builder._historical_table_notes()[5]
    assert "0/240 unauthorized proposals" in manuscript
    assert "30/240 authorized proposals" in manuscript
    assert "47/60 tasks were E3 anchors" in normalized
    assert re.search(r"29/30 tasks are\s+E3 anchors", manuscript)
    assert "does not satisfy or test the original multi-window activity gate" in normalized
    assert "Neither incomplete Gemini attempt meets paired-coverage requirements" in normalized
    assert "Provider-managed aliases do not pin immutable weights" in normalized
    assert "two-sided exact McNemar p-value" in normalized
    assert "planned cluster sign-flip test" in normalized
    assert "All Gemini paired, factorial, and cross-provider" in normalized
    assert "effects are therefore not estimable" in normalized
