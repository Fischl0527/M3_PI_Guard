from __future__ import annotations

import re
import pytest

import experiments.paper_v2.build_bibliography_v1 as bibliography


def test_current_bibliography_has_complete_39_entry_metadata() -> None:
    report = bibliography.verify()
    text = bibliography.OUTPUT_BIB.read_text(encoding="utf-8")
    entries = re.findall(
        r"(?ms)^@\w+\{(L\d{2}),\n(.*?)^\}",
        text,
    )

    assert report["entry_count"] == 39
    assert len(entries) == 39
    assert {key for key, _ in entries} == {
        f"L{index:02d}" for index in range(1, 40)
    }
    for key, body in entries:
        assert re.search(r"\bauthor\s*=", body), key
        assert re.search(r"\btitle\s*=", body), key
        assert re.search(r"\byear\s*=", body), key
        assert re.search(r"\burl\s*=", body), key
        assert re.search(r"\b(booktitle|journal)\s*=", body) or key in {
            "L21",
            "L22",
            "L23",
            "L24",
            "L26",
            "L27",
            "L28",
            "L29",
            "L30",
            "L31",
            "L35", "L36", "L38", "L39",
        }


def test_agentspec_uses_verified_icse_identity() -> None:
    text = bibliography.OUTPUT_BIB.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^@inproceedings\{L20,\n(.*?)^\}", text)

    assert match is not None
    body = match.group(1)
    assert "10.1145/3744916.3764546" in body
    assert "Haoyu Wang" in body
    assert "11588348" not in body


def test_active_preprint_identifiers_match_primary_arxiv_records() -> None:
    """Offline regression for the active identifiers checked on 2026-10-08."""
    text = bibliography.OUTPUT_BIB.read_text(encoding="utf-8")
    entries = dict(re.findall(r"(?ms)^@\w+\{(L\d{2}),\n(.*?)^\}", text))
    expected = {
        "L21": "2605.03378", "L22": "2605.26497", "L23": "2604.10134",
        "L24": "2504.11703", "L26": "2503.18813", "L27": "2510.09023",
        "L30": "2403.14720", "L31": "2404.13208", "L35": "2607.20827",
        "L36": "2607.27267", "L38": "2602.03117", "L39": "2605.17324",
    }
    for key, identifier in expected.items():
        assert f"eprint = {{{identifier}}}" in entries[key], key
        assert f"doi = {{10.48550/arXiv.{identifier}}}" in entries[key], key
        assert "Preprint" in entries[key], key
    assert "primaryClass = {cs.AI}" in entries["L35"]
    assert "primaryClass = {cs.LG}" in entries["L27"]
    assert "Chiu, Hung-Chun" in entries["L02"]
    assert "Chun, CHIU" not in entries["L02"]
    for key in ("L02", "L09", "L20", "L21", "L22", "L31", "L34", "L35"):
        assert "{LLM}" in entries[key], key
    for key, acronym in (("L02", "DRIFT"), ("L21", "ARGUS"), ("L34", "ASB"), ("L36", "FAVA")):
        assert "{" + acronym + "}" in entries[key], key


def test_historical_writer_cannot_replace_the_current_library(monkeypatch) -> None:
    def forbidden_build():
        raise AssertionError("must reject before fetching or writing metadata")
    monkeypatch.setattr(bibliography, "build", forbidden_build)
    with pytest.raises(bibliography.BibliographyBuildError, match="refusing to replace"):
        bibliography.write()


@pytest.mark.parametrize("defect", ["missing-title", "duplicate-key", "missing-key"])
def test_current_verification_rejects_metadata_damage(tmp_path, monkeypatch, defect) -> None:
    text = bibliography.OUTPUT_BIB.read_text(encoding="utf-8")
    if defect == "missing-title":
        text = re.sub(r"(?ms)(@inproceedings\{L20,.*?\n)\s*title = \{[^\n]+\},\n", r"\1", text)
    elif defect == "duplicate-key":
        text = text.replace("@misc{L39,", "@misc{L38,")
    else:
        text = re.sub(r"(?ms)^@misc\{L39,\n.*?^\}\n?", "", text)
    target = tmp_path / "references.bib"
    target.write_text(text, encoding="utf-8")
    monkeypatch.setattr(bibliography, "OUTPUT_BIB", target)
    with pytest.raises(bibliography.BibliographyBuildError):
        bibliography.verify()
