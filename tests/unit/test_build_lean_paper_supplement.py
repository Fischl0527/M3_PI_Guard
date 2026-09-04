from __future__ import annotations

import re

from scripts import build_lean_paper_supplement as builder


def test_supplement_contains_exactly_twelve_numbered_tables() -> None:
    supplement = builder.build_supplementary_markdown()

    headings = re.findall(
        r"^## Supplementary Table S(\d+)\. ", supplement, flags=re.MULTILINE
    )
    assert headings == [str(value) for value in range(1, 13)]
    assert supplement.count("\n|---") == 12
    assert "introduce no additional hypothesis family" in supplement
    assert "Supplementary Table S12. E6 paired effects" in supplement
    assert "Newcombe / cluster-bootstrap 95% CI" in supplement
    assert "Exact McNemar / Holm p" in supplement


def test_supplement_uses_the_manuscript_title() -> None:
    supplement = builder.build_supplementary_markdown()

    assert f"**Article:** {builder.TITLE}" in supplement
