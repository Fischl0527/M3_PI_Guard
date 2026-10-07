import fitz

from scripts.check_jisa_pdf_layout import centered_footer


def test_centered_footer_uses_baseline_not_glyph_ascender() -> None:
    page = fitz.Rect(0, 0, 595.28, 841.89)
    # Actual Times New Roman 12pt: glyph top crosses the arbitrary 100pt cutoff,
    # but its baseline and center remain correctly placed in the footer.
    box = fitz.Rect(294.16, 739.35, 300.14, 751.30)
    assert centered_footer(page, box, (1, 0), 748.46)


def test_footer_rejects_body_number_left_number_and_rotated_number() -> None:
    page = fitz.Rect(0, 0, 595.28, 841.89)
    box = fitz.Rect(294.16, 739.35, 300.14, 751.30)
    assert not centered_footer(page, box, (1, 0), 650)
    assert not centered_footer(page, fitz.Rect(70, 739, 76, 751), (1, 0), 748)
    assert not centered_footer(page, box, (0, 1), 748)
