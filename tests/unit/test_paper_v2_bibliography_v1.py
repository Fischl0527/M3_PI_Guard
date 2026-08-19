from __future__ import annotations

import re

import experiments.paper_v2.build_bibliography_v1 as bibliography


def test_frozen_bibliography_has_complete_34_entry_metadata() -> None:
    report = bibliography.verify()
    text = bibliography.OUTPUT_BIB.read_text(encoding="utf-8")
    entries = re.findall(
        r"(?ms)^@\w+\{(L\d{2}),\n(.*?)^\}",
        text,
    )

    assert report["entry_count"] == 34
    assert len(entries) == 34
    assert {key for key, _ in entries} == {
        f"L{index:02d}" for index in range(1, 35)
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
        }


def test_agentspec_uses_verified_icse_identity() -> None:
    text = bibliography.OUTPUT_BIB.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^@inproceedings\{L20,\n(.*?)^\}", text)

    assert match is not None
    body = match.group(1)
    assert "10.1145/3744916.3764546" in body
    assert "Haoyu Wang" in body
    assert "11588348" not in body
