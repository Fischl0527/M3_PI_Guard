from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts" / "presentation" / "build_final_presentation.ps1"


def _source() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def test_preview_and_final_reread_have_independent_exact_twelve_slide_gates() -> None:
    source = _source()

    assert "function Get-OrderedSlidePngs" in source
    assert "$Slides.Count -ne 12" in source
    assert "$ExpectedNumbers = @(1..12)" in source
    assert "slide numbers 1 through 12 exactly once" in source
    assert re.search(
        r"\$PreviewSlidePngs\s*=\s*@\(Get-OrderedSlidePngs\s+"
        r"-Directory\s+\$PreviewDir\s+-Label\s+'Artifact-tool pre-export preview'\)",
        source,
    )
    assert re.search(
        r"\$FinalSlidePngs\s*=\s*@\(Get-OrderedSlidePngs\s+"
        r"-Directory\s+\$FinalRenderDir\s+-Label\s+'Final exported-PPT reread render'\)",
        source,
    )


def test_final_reread_render_is_explicit_and_drives_the_contact_sheet() -> None:
    source = _source()

    render_call = re.search(
        r"Invoke-Checked\s+\$QaPython\s+@\([\s\S]*?render_slides\.py'[\s\S]*?"
        r"\$RenderInput,[\s\S]*?'--output_dir',\s+\$FinalRenderDir[\s\S]*?\)",
        source,
    )
    assert render_call is not None
    assert ") + $FinalSlidePngs + @(" in source
    assert ") + $PreviewSlidePngs + @(" not in source


def test_completion_json_exposes_both_qa_render_grains() -> None:
    source = _source()

    for field in (
        "preview_dir = $PreviewDir",
        "preview_slide_count = $PreviewSlidePngs.Count",
        "final_render_dir = $FinalRenderDir",
        "final_render_slide_count = $FinalSlidePngs.Count",
        "contact_sheet = $ContactSheet",
    ):
        assert field in source
