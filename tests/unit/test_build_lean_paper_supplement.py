from __future__ import annotations

import re

from scripts import build_lean_paper_supplement as builder


def test_supplement_contains_exactly_ten_numbered_tables() -> None:
    supplement = builder.build_supplementary_markdown()

    headings = re.findall(
        r"^## Supplementary Table S(\d+)\. ", supplement, flags=re.MULTILINE
    )
    assert headings == [str(value) for value in range(1, 11)]
    assert supplement.count("\n|---") == 10
    assert "introduce no additional hypothesis family" in supplement


def test_supplement_uses_the_manuscript_title() -> None:
    supplement = builder.build_supplementary_markdown()

    assert f"**Article:** {builder.TITLE}" in supplement
