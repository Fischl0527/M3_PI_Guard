"""文档整理后的路径回归；不运行实验或历史证据链。"""
from pathlib import Path

from experiments.paper_v2 import (
    build_bibliography_v1,
    incremental_figures_v1,
    incremental_tables_v1,
    lean_empirical_tables,
    lean_existing_results,
)
from scripts import build_jisa_latex, build_lean_paper_manuscript

ROOT = Path(__file__).resolve().parents[2]


def test_docs_contains_reading_material_not_execution_artifacts() -> None:
    excluded = {".py", ".ps1", ".json", ".jsonl", ".csv"}
    assert not [p for p in (ROOT / "docs").rglob("*") if p.is_file() and p.suffix in excluded]


def test_analysis_and_figure_defaults_point_outside_docs() -> None:
    assert lean_existing_results.OUTPUT_PATH.is_file()
    assert lean_empirical_tables.DEFAULT_AUTHORIZATION_ANALYSIS.is_file()
    assert lean_empirical_tables.DEFAULT_EXISTING_ANALYSIS.is_file()
    assert incremental_tables_v1.OUTPUT_ROOT.is_dir()
    assert incremental_figures_v1.OUTPUT_ROOT.is_dir()
    assert build_bibliography_v1.OUTPUT_REPORT.is_file()
    assert build_jisa_latex.FIGURE_SOURCE_DIR.is_dir()
    assert build_lean_paper_manuscript.FIGURE_DIR == build_jisa_latex.FIGURE_SOURCE_DIR
    assert build_lean_paper_manuscript.TABLE_DIR == incremental_tables_v1.OUTPUT_ROOT


def test_historical_public_toolkits_remain_separate() -> None:
    root = ROOT / "release/archive/blind_custodian_toolkits"
    packages = [p for p in root.iterdir() if p.is_dir()]
    assert len(packages) == 7
    assert all(list(p.glob("README*.md")) for p in packages)


def test_saved_manuscript_figures_resolve_after_move() -> None:
    import re

    for name in ("manuscript_deepseek_v1.md", "manuscript_zh_v1.md"):
        path = ROOT / "docs/research/paper_v2/manuscript" / name
        figures = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
        assert figures
        assert all((path.parent / target).is_file() for target in figures)
