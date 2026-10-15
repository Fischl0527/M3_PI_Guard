"""长路径和命名回归，只用本地小夹具。"""

import json

import pytest

from m3_core.artifact_paths import (
    matrix_output_paths, path_issues, path_units, require_short_path, resolve_artifact,
)
from m3_eval.metrics import load_jsonl
from m3_core.run_matrix import run_matrix
from scripts.shorten_project_paths import build_moves, move_preserving_files


def test_readable_compact_single_condition(tmp_path):
    condition = "ablation_named_no_multilingual_detector"
    paths = matrix_output_paths(tmp_path, "ablation__" + condition, condition, single=True)
    assert [p.name for p in paths] == ["records.jsonl", "metrics.csv"]


def test_ordinary_short_names_keep_legacy_contract(tmp_path):
    paths = matrix_output_paths(tmp_path, "legacy", "baseline", single=False)
    assert paths[0].name == "legacy_baseline.jsonl"


def test_multiple_long_prefixes_keep_full_condition_words(tmp_path):
    prefix = "a_very_long_experiment_description_" * 3
    first = matrix_output_paths(tmp_path, prefix, "normal_policy_only", single=False)
    second = matrix_output_paths(tmp_path, prefix, "normal_full_guard", single=False)
    assert first[0].name == "normal_policy_only.jsonl"
    assert second[0] != first[0]


def test_old_manifest_resolves_without_rewriting_raw(tmp_path):
    job = "ablation__ablation_named_no_multilingual_detector"
    directory = tmp_path / job
    directory.mkdir()
    data = '{"task_completion":false}\n'
    (directory / "records.jsonl").write_text(data, encoding="utf-8")
    old = directory / f"{job}_ablation_named_no_multilingual_detector.jsonl"
    assert resolve_artifact(old).name == "records.jsonl"
    assert load_jsonl(old) == [json.loads(data)]


def test_resolver_does_not_guess_unrelated_missing_names(tmp_path):
    (tmp_path / "records.jsonl").write_text("{}\n", encoding="utf-8")
    unknown = tmp_path / "unknown.jsonl"
    assert resolve_artifact(unknown) == unknown


def test_long_file_and_directory_fail_before_creation(tmp_path):
    path = tmp_path / ("folder_" * 11) / ("report_" * 13 + ".csv")
    with pytest.raises(ValueError, match="路径过长"):
        require_short_path(path, tmp_path)
    assert not path.parent.exists()


def test_non_bmp_counts_as_two_windows_units():
    assert path_units("文😀") == 3


def test_original_reference_title_kept_but_total_budget_still_checked(tmp_path):
    path = tmp_path / "文档资料" / ("Original paper title " * 5 + ".pdf")
    assert not any("文件名" in issue for issue in path_issues(path, tmp_path))
    deep = path.parent.joinpath(*(["reference_material"] * 7), path.name)
    assert any("路径" in issue for issue in path_issues(deep, tmp_path))


def test_relative_budget_is_independent_of_short_root(tmp_path):
    path = tmp_path.joinpath(*(["meaningful_directory"] * 9), "records.jsonl")
    assert any("相对路径" in issue for issue in path_issues(path, tmp_path))


def test_move_keeps_contents_and_refuses_overwrite(tmp_path):
    source = tmp_path / "original_results"
    source.mkdir()
    (source / "records.jsonl").write_bytes(b"original\n")
    target = tmp_path / "readable_results"
    assert move_preserving_files(source, target, tmp_path) == 1
    assert (target / "records.jsonl").read_bytes() == b"original\n"
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(FileExistsError):
        move_preserving_files(other, target, tmp_path)
    assert other.is_dir()


def test_move_cannot_escape_project(tmp_path):
    source = tmp_path / "record.jsonl"
    source.write_bytes(b"original\n")
    with pytest.raises(ValueError):
        move_preserving_files(source, tmp_path.parent / "outside.jsonl", tmp_path)
    assert source.exists()


def test_archive_package_names_preserve_meaning_and_version(tmp_path):
    old = tmp_path / "release/archive/blind_custodian_toolkits/M3_PI_Guard_Blind_Custodian_Review_Package_v3_4_python_final"
    old.mkdir(parents=True)
    moves = build_moves(tmp_path, [])
    assert len(moves) == 1
    assert moves[0][1].name == "review_v3_4"


def test_matrix_rejects_deep_output_before_mkdir_or_provider_call(tmp_path, monkeypatch):
    cases = tmp_path / "cases.jsonl"
    cases.write_text("{}\n", encoding="utf-8")
    directory = tmp_path.joinpath(*(["meaningful_directory"] * 10))
    monkeypatch.setattr("m3_core.run_matrix.run_batch", lambda _: pytest.fail("不得调用模型"))
    with pytest.raises(ValueError, match="路径过长"):
        run_matrix({"cases": str(cases), "out_dir": str(directory), "backend": "stub",
                    "conditions": "normal:off", "run_prefix": "readable_experiment"})
    assert not directory.exists()


def test_matrix_compact_names_are_saved_in_manifest(tmp_path, monkeypatch):
    cases = tmp_path / "cases.jsonl"
    cases.write_text("{}\n", encoding="utf-8")
    condition = "ablation_named_no_multilingual_detector"

    def batch(config):
        from pathlib import Path

        Path(config["out"]).write_text("{}\n", encoding="utf-8")
        Path(config["csv_out"]).write_text("header\n", encoding="utf-8")
        return {"error_count": 0, "log_count": 1}

    monkeypatch.setattr("m3_core.run_matrix.run_batch", batch)
    result = run_matrix({"cases": str(cases), "out_dir": str(tmp_path / "experiment"),
                         "backend": "stub", "conditions": condition + "=normal:full_guard",
                         "run_prefix": "ablation__" + condition})
    assert result["results"][0]["jsonl"].endswith("/records.jsonl")
    assert result["results"][0]["csv"].endswith("/metrics.csv")
