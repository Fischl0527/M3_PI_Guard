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
        "### Declaration of generative AI and AI-assisted technologies in the writing process"
        in manuscript
    )
    assert manuscript.index("## Submission statements") < manuscript.index(
        "## References"
    )
    assert manuscript.count("![Figure ") == 5
    assert len(re.findall(r"^### Table [1-6]\. ", manuscript, flags=re.MULTILINE)) == 6
    assert len(re.findall(r"^#### Supplementary Table S[1-6]\. ", manuscript, flags=re.MULTILINE)) == 6
    assert "### Figures" not in manuscript
    assert "22/60 (36.7%)" in manuscript
    assert "CNY 0.3374" in manuscript


def test_abstract_stays_within_jisa_limit() -> None:
    abstract, keywords = builder._abstract_and_keywords()

    assert builder._word_count(abstract) <= 250
    assert 1 <= len([item for item in keywords.split(";") if item.strip()]) <= 7


def test_every_citation_key_exists_in_bibliography() -> None:
    builder._validate_citations(builder.build_manuscript())


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
