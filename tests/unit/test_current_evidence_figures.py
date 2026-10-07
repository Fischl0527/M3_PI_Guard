from __future__ import annotations

import copy
import json

import fitz
import pytest

from scripts import current_evidence_figures as figures


def test_cached_selection_and_paired_intervals_are_not_recomputed() -> None:
    data = figures.load_evidence()
    assert [len(data[key]) for key in ("authorization", "contrasts", "calibration", "diagnosis")] == [8, 4, 8, 8]
    assert [cell["completion"]["true"] for cell in data["authorization"]] == [2, 13, 2, 11, 16, 14, 17, 16]
    first = data["contrasts"][0]["paired_interval"]
    assert first["estimate"] == pytest.approx(11 / 30)
    assert first["ci_low"] > 0.18
    assert data["diagnosis"][0]["first_blocks"]["missing_tool_permission"] == 26


def test_unknown_calibration_outcomes_keep_observed_and_itt_distinct() -> None:
    data = figures.load_evidence()
    endpoint = data["calibration"][3][0]["unsafe"]
    assert (endpoint["true"], endpoint["observed"], endpoint["unknown"], endpoint["planned"]) == (4, 28, 2, 30)
    assert figures.endpoint_values(endpoint)[0] == pytest.approx(100 * 4 / 28)
    assert endpoint["itt_lower"] == pytest.approx(4 / 30)
    assert endpoint["itt_upper"] == pytest.approx(6 / 30)
    zero = data["calibration"][1][0]["unsafe"]
    assert figures.endpoint_values(zero)[2] > 11


def test_missing_or_inconsistent_endpoint_is_not_zero_filled() -> None:
    endpoint = copy.deepcopy(figures.load_evidence()["calibration"][3][0]["unsafe"])
    endpoint["unknown"] = 0
    with pytest.raises(figures.CurrentFigureError, match="denominators"):
        figures.endpoint_values(endpoint)
    del endpoint["observed"]
    with pytest.raises(KeyError):
        figures.endpoint_values(endpoint)
    with pytest.raises(figures.CurrentFigureError, match="Duplicate"):
        figures.unique([{"id": 1}, {"id": 1}], ("id",))


def test_cohort_and_diagnostic_count_mismatches_reject(tmp_path) -> None:
    paths = (
        "outputs/experiments/claude_revision_v1/analysis.json",
        "outputs/experiments/research_followup_20261006_v1/calibration/analysis.json",
        "outputs/experiments/research_followup_20261006_v1/diagnosis/analysis.json",
    )
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((figures.ROOT / relative).read_bytes())
    target = tmp_path / paths[2]
    cache = json.loads(target.read_text(encoding="utf-8"))
    cache["cells"][0]["first_blocks"]["missing_tool_permission"] = 25
    target.write_text(json.dumps(cache), encoding="utf-8")
    with pytest.raises(figures.CurrentFigureError, match="sum to 30"):
        figures.load_evidence(tmp_path)


def test_render_four_figures_has_readable_embedded_times_text(tmp_path) -> None:
    paths = figures.build(output=tmp_path)
    assert len(paths) == 12
    for path in paths:
        assert path.stat().st_size > 1000
        if path.suffix == ".svg":
            assert all(line == line.rstrip() for line in
                       path.read_text(encoding="utf-8").splitlines())
    for pdf in tmp_path.glob("*.pdf"):
        with fitz.open(pdf) as document:
            assert len(document) == 1
            page = document[0]
            assert page.rect.width == pytest.approx(175 / 25.4 * 72, abs=0.1)
            spans = [span for block in page.get_text("dict")["blocks"] if "lines" in block
                     for line in block["lines"] for span in line["spans"] if span["text"].strip()]
            assert spans and min(span["size"] for span in spans) >= 8
            assert all("TimesNewRoman" in span["font"] for span in spans)
            assert all(page.rect.contains(fitz.Rect(span["bbox"])) for span in spans)
    assert "Oracle-only" in fitz.open(tmp_path / "current_01_boundaries.pdf")[0].get_text()


def test_font_substitution_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(figures.font_manager, "findfont", lambda *args, **kwargs: "not-a-font.ttf")
    with pytest.raises((FileNotFoundError, RuntimeError)):
        figures.style()
