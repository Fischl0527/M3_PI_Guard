from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from experiments.paper_v2.incremental_figures_v1 import (
    BASE_FONT_SIZE,
    FIGURE_WIDTH_IN,
    FONT_FAMILY,
    SMALL_FONT_SIZE,
    _style,
    build_figures,
)


def _proportion(value: float) -> dict:
    return {"numerator": int(value * 100), "denominator": 100, "value": value}


def _factor(shift: float = 0.0) -> dict:
    estimates = {
        name: {
            "estimate": value + shift,
            "ci_low": value + shift - 0.04,
            "ci_high": value + shift + 0.04,
        }
        for name, value in (("module", -0.03), ("prompt", -0.02), ("interaction", 0.01))
    }
    return {"factor_estimates": estimates}


def _factorial(shift: float = 0.0) -> dict:
    cells = {}
    for index, name in enumerate(
        ("policy_normal", "policy_safe", "full_normal", "full_safe")
    ):
        cells[name] = {
            "attack_unsafe_effect": _proportion(0.15 - index * 0.02 + shift),
            "attack_unsafe_or_failure": _proportion(
                0.17 - index * 0.01 + shift
            ),
            "benign_tool_tcr": _proportion(0.75 - index * 0.03),
            "operational_failure": _proportion(0.02 + index * 0.01),
        }
    return {"cell_summary": cells, "attack_unsafe_factor": _factor(shift)}


def test_incremental_renderer_builds_five_deterministic_format_triplets(
    tmp_path: Path,
) -> None:
    factorial_path = tmp_path / "factorial.json"
    challenge_path = tmp_path / "challenge.json"
    flash_path = tmp_path / "flash.json"
    provenance_path = tmp_path / "provenance.json"
    adaptive_path = tmp_path / "adaptive.json"
    existing_path = tmp_path / "existing.json"
    factorial_path.write_text(json.dumps(_factorial()), encoding="utf-8")
    challenge_path.write_text(json.dumps(_factorial(0.02)), encoding="utf-8")
    flash_path.write_text(json.dumps(_factorial(-0.01)), encoding="utf-8")
    provenance_path.write_text(
        json.dumps(
            {
                "offline_guard_replay": {
                    "decision_heatmap": {
                        "policy_trusted_origin": {"ALLOW": 60, "ASK": 40, "DENY": 20},
                        "policy_untrusted_origin": {"ALLOW": 40, "ASK": 60, "DENY": 20},
                        "full_trusted_origin": {"ALLOW": 55, "ASK": 45, "DENY": 20},
                        "full_untrusted_origin": {"ALLOW": 20, "ASK": 70, "DENY": 30},
                    }
                },
                "source_swap_action_change": {
                    "policy": _proportion(0.25),
                    "full": _proportion(0.40),
                },
            }
        ),
        encoding="utf-8",
    )
    adaptive_path.write_text(
        json.dumps(
            {
                "conditional_survival_curve": [
                    {"query_budget": 200, "survival_probability": 1.0},
                    {"query_budget": 280, "survival_probability": 0.83},
                    {"query_budget": 500, "survival_probability": 0.75},
                ]
            }
        ),
        encoding="utf-8",
    )
    existing_path.write_text(
        json.dumps(
            {
                "adaptive_deepseek_v4_pro": {
                    "budget_50": {"rate": 0.10},
                    "budget_200": {"rate": 0.45},
                }
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "figures"
    result = build_figures(
        factorial_path=factorial_path,
        provenance_path=provenance_path,
        challenge_path=challenge_path,
        flash_path=flash_path,
        adaptive_tail_path=adaptive_path,
        existing_path=existing_path,
        output_dir=output,
    )
    assert len(result["outputs"]) == 5
    paths = [Path(path) for values in result["outputs"].values() for path in values]
    assert len(paths) == 15
    assert all(path.exists() and path.stat().st_size > 1_000 for path in paths)
    assert {path.suffix for path in paths} == {".png", ".svg", ".pdf"}
    assert all(
        path.read_bytes().startswith(b"%PDF") for path in paths if path.suffix == ".pdf"
    )
    assert FIGURE_WIDTH_IN == 7.3
    assert FONT_FAMILY == "Times New Roman"
    assert BASE_FONT_SIZE >= 10.5
    assert SMALL_FONT_SIZE >= 10.0
    for path in (path for path in paths if path.suffix == ".pdf"):
        payload = path.read_bytes()
        assert b"/Type3" not in payload
        assert b"/FontFile2" in payload
        assert b"TimesNewRoman" in payload
        assert b"Arial" not in payload
        media_box = re.search(
            rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]",
            payload,
        )
        assert media_box is not None
        assert float(media_box.group(1)) <= 560.0
    assert (output / "figure_manifest_v1.json").is_file()
    manifest = json.loads(
        (output / "figure_manifest_v1.json").read_text(encoding="utf-8")
    )
    assert manifest["font"] == {
        "family": "Times New Roman",
        "fallback_allowed": False,
    }


def test_incremental_renderer_fails_closed_when_times_new_roman_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_font(*args: object, **kwargs: object) -> str:
        raise ValueError("font not found")

    monkeypatch.setattr(
        "experiments.paper_v2.incremental_figures_v1.font_manager.findfont",
        missing_font,
    )
    with pytest.raises(RuntimeError, match="Times New Roman.*fallback is disabled"):
        _style()
