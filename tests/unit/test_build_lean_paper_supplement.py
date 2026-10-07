from __future__ import annotations

import re

from scripts import build_lean_paper_supplement as builder


def test_supplement_contains_twenty_numbered_tables() -> None:
    supplement = builder.build_supplementary_markdown()

    headings = re.findall(
        r"^## Supplementary Table S(\d+)\. ", supplement, flags=re.MULTILINE
    )
    assert headings == [str(value) for value in range(1, 21)]
    assert supplement.count("\n|---") == 20
    assert "introduce no additional hypothesis family" in supplement
    assert "Supplementary Table S12. E6 paired effects" in supplement
    assert "Newcombe / cluster-bootstrap 95% CI" in supplement
    assert "Exact McNemar / Holm p" in supplement


def test_existing_and_former_main_tables_retain_exact_bodies_and_notes() -> None:
    from scripts import build_lean_paper_manuscript as manuscript

    supplement = builder.build_supplementary_markdown()
    source = manuscript._drop_wrapper(manuscript._read("results_shell.md"), start_heading="## Medium falsification study")
    _, tables = manuscript._split_supplementary_tables(source)
    for number, title, table in tables:
        assert f"## Supplementary Table S{number}. {title}\n\n{table}" in supplement
    for (number, title, table), note in zip(manuscript._historical_main_tables(), manuscript._historical_table_notes(), strict=True):
        assert f"## Supplementary Table S{number + 12}. {title}\n\n{note}\n\n{table}" in supplement


def test_markdown_only_does_not_create_word(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(builder, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(builder, "MARKDOWN_PATH", tmp_path / "supplement.md")
    monkeypatch.setattr(builder, "build_supplementary_markdown", lambda: "cached tables")
    def forbidden(*args):
        raise AssertionError("Word generation is out of scope")
    monkeypatch.setattr(builder, "build_supplementary_docx", forbidden)
    assert builder.main(["--markdown-only"]) == 0
    assert (tmp_path / "supplement.md").read_text(encoding="utf-8") == "cached tables"


def test_supplement_uses_the_manuscript_title() -> None:
    supplement = builder.build_supplementary_markdown()

    assert f"**Article:** {builder.TITLE}" in supplement
