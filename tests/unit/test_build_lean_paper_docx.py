from __future__ import annotations

import pytest

from scripts import build_lean_paper_docx as builder


def test_prepare_markdown_removes_placeholder_reference_text() -> None:
    source = "# Title\n\nText [@L01].\n\n## References\n\nPlaceholder.\n"

    prepared = builder._prepare_markdown(source)

    assert "Placeholder" not in prepared
    assert "Text [@L01]." in prepared
    assert "## References" in prepared
    assert '<div id="refs"></div>' in prepared


def test_prepare_markdown_requires_reference_boundary() -> None:
    with pytest.raises(builder.DocxBuildError, match="References boundary"):
        builder._prepare_markdown("# Title\n")


def test_column_widths_sum_to_content_width() -> None:
    class Cell:
        def __init__(self, text: str) -> None:
            self.text = text

    class Row:
        def __init__(self, values: tuple[str, ...]) -> None:
            self.cells = [Cell(value) for value in values]

    class Table:
        rows = (
            Row(("Short", "A much longer descriptive value", "n")),
            Row(("A", "Another descriptive value", "40")),
        )

    widths = builder._column_widths(Table())

    assert len(widths) == 3
    assert sum(widths) == builder.CONTENT_WIDTH_DXA
    assert widths[1] > widths[0]
    assert widths[1] > widths[2]
    assert min(widths) >= 720
