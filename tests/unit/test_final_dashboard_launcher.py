from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts" / "run_final_dashboard.ps1"
STREAMLIT_ENTRY = ROOT / "scripts" / "dashboard_app.py"


def test_validate_only_rehashes_complete_dashboard_evidence_chain() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "from scripts.build_final_report import load_report_evidence" in source
    assert "Assert-HashVerifiedEvidenceChain" in source
    assert source.index("Assert-HashVerifiedEvidenceChain\n") < source.index(
        "if ($ValidateOnly)"
    )
    assert "len(evidence.bundles)" in source
    assert "len(evidence.charts)" in source
    assert "$E11SupplementDir" in source
    assert "E11_POSTHOC_AMENDMENT_V1" in source
    assert "supplementManifest.visualization_revision" in source
    assert "posthoc_supplement.visualization_revision" in source
    assert "excluded_from_original_e11_denominator" in source
    assert "e11_scope_boundary" in source
    assert "denominators_pooled" in source
    assert "not passed as a second E11 bundle" in source
    assert "Resolve-RegistryPrimaryBundleDirs" in source
    assert "$FormalBundleDirs = Resolve-RegistryPrimaryBundleDirs" in source
    assert "CONTEXT_CORRECTION_V2" in source
    assert "formal_program_corrected_context" in source
    assert 'Join-Path $ExperimentRoot "E9"' in source
    assert 'Join-Path $ExperimentRoot "E14"' in source


def test_streamlit_uses_package_safe_entrypoint() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    entry = STREAMLIT_ENTRY.read_text(encoding="utf-8")

    assert '$DashboardStreamlitEntry = Join-Path $ScriptDir "dashboard_app.py"' in source
    assert '"run", $DashboardStreamlitEntry' in source
    assert "from m3_eval.evidence_dashboard import main" in entry
    assert "sys.path.insert(0, str(ROOT))" in entry
    assert "raise SystemExit(main())" not in entry
