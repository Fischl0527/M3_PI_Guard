from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "render_docx_wps.ps1"


def test_wps_render_script_contains_fail_closed_safety_contract() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    required_fragments = (
        "Copy-Item -LiteralPath $SourcePath -Destination $WorkingCopy",
        "$WpsApplication.Documents.Count",
        "$WpsApplication.Visible = $false",
        "$WpsApplication.DisplayAlerts = 0",
        "$WpsApplication.Documents.Open($WorkingCopy, $false, $true)",
        "$WpsDocument.ReadOnly",
        "$WpsDocument.ExportAsFixedFormat($PdfPath, 17)",
        "Assert-SourceUnchanged",
        "Get-Sha256",
        "LastWriteTimeUtc.Ticks",
        "FinalReleaseComObject",
        "$WpsDocument.Close(0)",
        "$WpsApplication.Quit()",
        "Get-NewProcessIds",
        "WPS process residue detected",
        "PDF/PNG page-count mismatch",
        "render_manifest.json",
        "pending_manual_inspection",
        "pdftoppm.exe",
        "pdfinfo.exe",
    )
    for fragment in required_fragments:
        assert fragment in text

    assert "Documents.Open($SourcePath" not in text
    assert "Stop-Process" not in text
    assert "taskkill" not in text.casefold()
    assert "Remove-Item -LiteralPath $SourcePath" not in text


def test_missing_source_fails_before_output_or_com_launch(tmp_path: Path) -> None:
    output = tmp_path / "must-not-exist"
    missing = tmp_path / "missing.docx"
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-InputDocx",
            str(missing),
            "-OutputDir",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode != 0
    assert "Input DOCX is missing" in (completed.stdout + completed.stderr)
    assert not output.exists()


def test_powershell_parser_accepts_script() -> None:
    command = (
        "$tokens=$null; $errors=$null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{SCRIPT}',[ref]$tokens,[ref]$errors) | Out-Null; "
        "if($errors.Count -gt 0){$errors | ForEach-Object {$_.ToString()}; exit 1}"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
