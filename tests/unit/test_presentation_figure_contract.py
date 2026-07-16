from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from scripts.build_final_analysis import CHART_SPECS


ROOT = Path(__file__).resolve().parents[2]
DECK_SOURCE = ROOT / "scripts" / "presentation" / "build_final_deck.mjs"
FIXTURE_SOURCE = (
    ROOT / "scripts" / "presentation" / "generate_synthetic_fixture_assets.mjs"
)
FIXTURE_JSON = ROOT / "scripts" / "presentation" / "synthetic-fixture.json"


def _javascript_string_array(source: str, constant: str) -> list[str]:
    match = re.search(
        rf"const\s+{re.escape(constant)}\s*=\s*(\[[\s\S]*?\]);",
        source,
    )
    assert match is not None, f"missing JavaScript constant: {constant}"
    value = ast.literal_eval(match.group(1))
    assert isinstance(value, list)
    return value


def test_presentation_figure_ids_match_final_analysis_contract() -> None:
    deck_source = DECK_SOURCE.read_text(encoding="utf-8")
    fixture_source = FIXTURE_SOURCE.read_text(encoding="utf-8")

    slots = _javascript_string_array(deck_source, "FIGURE_SLOTS")
    selected = [figure_id for _, *figure_ids in slots for figure_id in figure_ids]
    available = {chart_id for chart_id, _, _ in CHART_SPECS}

    assert len(selected) == len(set(selected)) == 10
    assert set(selected) <= available
    assert _javascript_string_array(fixture_source, "FIGURES") == selected
    assert "cross_tool_chain_patterns" in available
    assert "cross_tool_chain_patterns" not in selected
    assert "cross_tool_chain_patterns" in (
        ROOT / "scripts" / "presentation" / "README.md"
    ).read_text(encoding="utf-8")
    assert "pre_registered=false" in (
        ROOT / "scripts" / "presentation" / "source-notes.source.txt"
    ).read_text(encoding="utf-8")


def test_presentation_truthfulness_contract_is_dynamic_and_hash_bound() -> None:
    deck_source = DECK_SOURCE.read_text(encoding="utf-8")
    fixture = json.loads(FIXTURE_JSON.read_text(encoding="utf-8"))

    assert _javascript_string_array(deck_source, "TRUTHFULNESS_ARTIFACTS") == [
        "result_integrity_audit.json",
        "main_parse_quality.json",
        "e16_provenance.json",
    ]
    for token in (
        "source_audit_sha256",
        "models_below_reference.step_row",
        "models_below_reference.run",
        "sandbox_runtime_version",
        "A11 仍为 E1 regular_full",
        "独立 validation 分母",
    ):
        assert token in deck_source
    for current_result_literal in (
        "12081/12538",
        "6025/6480",
        "2697/2732",
        "2413/2595",
        "3870/4105",
        "3101/3106",
    ):
        assert current_result_literal not in deck_source

    assert fixture["main_parse_quality"]["overall"]["step_row"]["denominator"] > 0
    assert fixture["main_parse_quality"]["overall"]["run"]["denominator"] > 0
    assert fixture["e16_provenance"]["excluded_from_main_matrix"] is True
