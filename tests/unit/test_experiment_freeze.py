from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from experiments.freeze import (
    REPO_ROOT,
    create_freeze,
    protected_paths,
    verify_freeze,
)


class BlindFreezeTests(unittest.TestCase):
    def _boundary(
        self,
        *,
        roots: tuple[str, ...],
        required: tuple[str, ...],
        excluded: frozenset[str] = frozenset(),
    ) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch("experiments.freeze.PROTECTED_ROOTS", roots))
        stack.enter_context(patch("experiments.freeze.REQUIRED_FILES", required))
        stack.enter_context(patch("experiments.freeze.EXCLUDED_FILES", excluded))
        stack.enter_context(
            patch(
                "experiments.freeze.git_state",
                return_value={"commit": "abc", "branch": "test1", "dirty": False},
            )
        )
        return stack

    def test_real_boundary_contains_runtime_scoring_fixtures_and_key_executors(self) -> None:
        paths = {
            path.relative_to(REPO_ROOT.resolve()).as_posix()
            for path in protected_paths(REPO_ROOT)
        }
        required_examples = {
            "m3_core/agent_runner.py",
            "m3_core/run_batch.py",
            "m3_core/run_matrix.py",
            "m3_guard/config.py",
            "m3_guard/guard_engine.py",
            "m3_attacks/attackgen.py",
            "m3_attacks/cases/all_cases.jsonl",
            "m3_eval/metrics.py",
            "m3_eval/statistics.py",
            "m3_eval/figure_manifest.py",
            "schemas/attack_case.schema.json",
            "schemas/run_log.schema.json",
            "schemas/tool_call.schema.json",
            "experiments/catalog.py",
            "experiments/run_program.py",
            "experiments/derived_cases.py",
            "experiments/model_manager.py",
            "experiments/manifest.py",
            "experiments/e13_calibration.py",
            "experiments/e14_performance.py",
            "experiments/e16_adaptive_redteam.py",
            "experiments/analyze_program.py",
            "experiments/e17_review.py",
            "outputs/experiments/E13/frozen_thresholds.json",
            "experiments/fixtures/smoke_cases.jsonl",
            "experiments/fixtures/derived/e9_cases.jsonl",
            "fixtures/day5_representative_cases.jsonl",
        }
        self.assertTrue(required_examples.issubset(paths), sorted(required_examples - paths))
        self.assertNotIn("experiments/registry.json", paths)
        self.assertNotIn("m3_attacks/cases/dataset_audit.json", paths)
        self.assertNotIn("m3_attacks/cases/dataset_stats.json", paths)
        self.assertNotIn(
            "experiments/fixtures/derived/derived_cases_audit.json", paths
        )
        self.assertFalse(any("__pycache__" in path for path in paths))
        self.assertEqual(
            {path for path in paths if path.startswith("outputs/")},
            {"outputs/experiments/E13/frozen_thresholds.json"},
        )

    def test_verify_detects_changed_added_and_missing_files_together(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "runtime").mkdir()
            (root / "cases").mkdir()
            source = root / "runtime" / "core.py"
            data = root / "cases" / "data.jsonl"
            source.write_text("ONE = 1\n", encoding="utf-8")
            data.write_text('{"id": 1}\n', encoding="utf-8")
            freeze = root / "freeze.json"
            with self._boundary(
                roots=("runtime", "cases"),
                required=("runtime/core.py", "cases/data.jsonl"),
            ):
                create_freeze(freeze, repo_root=root)
                self.assertEqual(verify_freeze(freeze, repo_root=root), [])
                source.write_text("ONE = 2\n", encoding="utf-8")
                data.unlink()
                (root / "runtime" / "new_runner.py").write_text(
                    "NEW = True\n", encoding="utf-8"
                )
                self.assertEqual(
                    verify_freeze(freeze, repo_root=root),
                    [
                        "added: runtime/new_runner.py",
                        "changed: runtime/core.py",
                        "missing: cases/data.jsonl",
                    ],
                )

    def test_create_has_clear_errors_for_missing_required_root_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "runtime").mkdir()
            with self._boundary(
                roots=("runtime", "schemas"),
                required=("runtime/critical.py",),
            ):
                with self.assertRaisesRegex(
                    FileNotFoundError,
                    r"missing required root\(s\): schemas.*missing required file\(s\): runtime/critical.py",
                ):
                    protected_paths(root)

    def test_registry_and_generated_analyzer_state_are_excluded_but_new_code_is_added(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            experiments = root / "experiments"
            experiments.mkdir()
            runner = experiments / "runner.py"
            registry = experiments / "registry.json"
            state = experiments / "analysis_state"
            state.mkdir()
            runner.write_text("RUN = 1\n", encoding="utf-8")
            registry.write_text('{"status": "pending"}\n', encoding="utf-8")
            (state / "cursor.json").write_text('{"row": 1}\n', encoding="utf-8")
            freeze = root / "freeze.json"
            with self._boundary(
                roots=("experiments",),
                required=("experiments/runner.py",),
                excluded=frozenset({"experiments/registry.json"}),
            ):
                payload = create_freeze(freeze, repo_root=root)
                self.assertEqual(set(payload["files"]), {"experiments/runner.py"})
                registry.write_text('{"status": "running"}\n', encoding="utf-8")
                (state / "cursor.json").write_text('{"row": 2}\n', encoding="utf-8")
                self.assertEqual(verify_freeze(freeze, repo_root=root), [])
                (experiments / "new_executor.py").write_text(
                    "EXECUTE = True\n", encoding="utf-8"
                )
                self.assertEqual(
                    verify_freeze(freeze, repo_root=root),
                    ["added: experiments/new_executor.py"],
                )

    def test_extra_paths_must_be_regular_repo_files_and_not_excluded_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            root = base / "repo"
            runtime = root / "runtime"
            runtime.mkdir(parents=True)
            (runtime / "core.py").write_text("CORE = 1\n", encoding="utf-8")
            outside = base / "outside.py"
            outside.write_text("OUTSIDE = 1\n", encoding="utf-8")
            registry = root / "registry.json"
            registry.write_text("{}\n", encoding="utf-8")
            with self._boundary(
                roots=("runtime",),
                required=("runtime/core.py",),
                excluded=frozenset({"registry.json"}),
            ):
                with self.assertRaisesRegex(ValueError, "outside repository root"):
                    create_freeze(
                        root / "freeze.json",
                        repo_root=root,
                        extra_paths=[outside],
                    )
                with self.assertRaisesRegex(ValueError, "excluded mutable/generated"):
                    create_freeze(
                        root / "freeze.json",
                        repo_root=root,
                        extra_paths=[registry],
                    )
                with self.assertRaisesRegex(FileNotFoundError, "missing/non-file"):
                    create_freeze(
                        root / "freeze.json",
                        repo_root=root,
                        extra_paths=["missing.json"],
                    )

    def test_verify_rejects_traversal_and_detects_manifest_missing_required_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = root / "runtime"
            runtime.mkdir()
            source = runtime / "core.py"
            source.write_text("CORE = 1\n", encoding="utf-8")
            freeze = root / "freeze.json"
            with self._boundary(
                roots=("runtime",), required=("runtime/core.py",)
            ):
                create_freeze(freeze, repo_root=root)
                payload = json.loads(freeze.read_text(encoding="utf-8"))
                payload["files"]["../outside.py"] = "0" * 64
                freeze.write_text(json.dumps(payload), encoding="utf-8")
                self.assertIn(
                    "invalid path in freeze manifest: '../outside.py'",
                    verify_freeze(freeze, repo_root=root),
                )

                payload["files"].pop("../outside.py")
                payload["files"].pop("runtime/core.py")
                freeze.write_text(json.dumps(payload), encoding="utf-8")
                problems = verify_freeze(freeze, repo_root=root)
                self.assertIn(
                    "freeze missing required entry: runtime/core.py", problems
                )
                self.assertIn("added: runtime/core.py", problems)


if __name__ == "__main__":
    unittest.main()
