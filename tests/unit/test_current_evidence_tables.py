from __future__ import annotations

import copy
import json

import pytest

from scripts.current_evidence_tables import (
    EvidenceTableError,
    _fraction,
    _unique,
    current_tables,
)
from scripts import build_lean_paper_manuscript as manuscript


def test_current_tables_preserve_counts_uncertainty_and_component_limits() -> None:
    tables = current_tables(manuscript.PROJECT_ROOT)
    assert [row[0] for row in tables] == [1, 2, 3, 4]
    assert "720" in tables[0][2] and "180" in tables[0][2] and "480" in tables[0][2]
    assert "2/30 [1.85, 21.32]" in tables[1][2]
    assert "13/30 [27.38, 60.80]" in tables[1][2]
    assert "4/28" in tables[2][2] and "| 2 / 2 | 3 / 7 |" in tables[2][2]
    assert "0/30 [0.00, 11.35]" in tables[2][2]
    assert "4/30 to 6/30" in tables[2][3]
    assert "V4.1 Flash" in tables[3][2] and "| 1 / 1 | 0 / 0 |" in tables[3][2]
    assert "not human approval" in tables[3][3]
    assert all(len(table.splitlines()[0].split("|")) == 7 for _, _, table, _ in tables)


def test_bilingual_tables_use_identical_numeric_cells() -> None:
    english = current_tables(manuscript.PROJECT_ROOT)
    chinese = current_tables(manuscript.PROJECT_ROOT, chinese=True)
    for en, zh in zip(english[1:], chinese[1:], strict=True):
        assert en[2].splitlines()[2:] == zh[2].splitlines()[2:]
    source = manuscript._read("manuscript_zh_v1.md")
    updated = manuscript.sync_chinese_tables(source)
    assert updated == manuscript.sync_chinese_tables(updated)
    assert updated.count("### 表 ") == 4
    assert updated.count("### 补充表 S") == 8
    for _, _, table, _ in chinese:
        assert table in updated


def test_endpoint_unknown_is_not_silently_zero_imputed() -> None:
    endpoint = {
        "true": 4,
        "observed": 28,
        "planned": 30,
        "unknown": 2,
        "observed_wilson_95": [0.05, 0.31],
    }
    assert _fraction(endpoint) == "4/28 [5.00, 31.00]"
    endpoint["unknown"] = 0
    with pytest.raises(EvidenceTableError, match="denominators"):
        _fraction(endpoint)
    with pytest.raises(EvidenceTableError, match="Duplicate"):
        _unique([{"case": 1}, {"case": 1}], ("case",))


def test_duplicate_or_unknown_controls_cannot_be_rendered(tmp_path) -> None:
    authorization = json.loads(
        (
            manuscript.PROJECT_ROOT
            / "outputs/experiments/claude_revision_v1/analysis.json"
        ).read_text(encoding="utf-8")
    )
    calibration = (
        manuscript.PROJECT_ROOT
        / "outputs/experiments/research_followup_20261006_v1/calibration/analysis.json"
    ).read_text(encoding="utf-8")
    a_path = tmp_path / "outputs/experiments/claude_revision_v1/analysis.json"
    b_path = (
        tmp_path
        / "outputs/experiments/research_followup_20261006_v1/calibration/analysis.json"
    )
    a_path.parent.mkdir(parents=True)
    b_path.parent.mkdir(parents=True)
    b_path.write_text(calibration, encoding="utf-8")
    for kind in ("duplicate", "unknown"):
        broken = copy.deepcopy(authorization)
        if kind == "duplicate":
            broken["cells"].append(broken["cells"][0])
        else:
            broken["synthetic"][0]["unsafe_effect"] = None
        a_path.write_text(json.dumps(broken), encoding="utf-8")
        with pytest.raises(EvidenceTableError):
            current_tables(tmp_path)
