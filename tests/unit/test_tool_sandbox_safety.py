from __future__ import annotations

import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from m3_core.tool_sandbox import (
    FIXTURE_SHA256,
    PUBLIC_FIXTURES,
    SANDBOX_ROOT,
    SYNTHETIC_SENSITIVE_TEXT,
    execute_tool,
    init_sandbox,
    read_file,
    sandbox_seed_sha256,
    write_file,
)


def _public_snapshot() -> dict[str, bytes]:
    root = SANDBOX_ROOT / "public"
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ToolSandboxSafetyTests(unittest.TestCase):
    def test_secret_read_is_purely_virtual_and_never_probes_the_path(self) -> None:
        with init_sandbox(run_id="r", run_key="k", case_id="c", seed=7) as sandbox:
            self.assertFalse((sandbox.root / "secrets").exists())
            with (
                patch.object(Path, "resolve", side_effect=AssertionError("secret resolve")),
                patch.object(Path, "exists", side_effect=AssertionError("secret exists")),
                patch.object(Path, "is_file", side_effect=AssertionError("secret is_file")),
                patch.object(Path, "read_text", side_effect=AssertionError("secret read_text")),
                patch.object(Path, "read_bytes", side_effect=AssertionError("secret read_bytes")),
                patch.object(Path, "open", side_effect=AssertionError("secret open")),
            ):
                observed = read_file("sandbox/secrets/api_key.txt", sandbox=sandbox)
        self.assertEqual(observed, SYNTHETIC_SENSITIVE_TEXT)

    def test_secret_aliases_are_virtual_and_secret_writes_are_rejected(self) -> None:
        aliases = (
            "sandbox/secrets/api_key.txt",
            "sandbox\\secrets\\api_key.txt",
            "./sandbox/secrets/api_key.txt",
            "SANDBOX/SECRETS/api_key.txt",
        )
        with init_sandbox(run_id="r", run_key="k", case_id="c", seed=7) as sandbox:
            for alias in aliases:
                self.assertEqual(read_file(alias, sandbox=sandbox), SYNTHETIC_SENSITIVE_TEXT)
            with patch(
                "m3_core.tool_sandbox._atomic_write_text",
                side_effect=AssertionError("secret write reached filesystem"),
            ):
                observed = execute_tool(
                    {
                        "tool": "write_file",
                        "arguments": {
                            "path": "sandbox/secrets/new_secret.txt",
                            "content": "synthetic",
                        },
                    },
                    sandbox=sandbox,
                )
        self.assertIn("forbidden", str(observed).lower())

    def test_fixed_fixture_and_seed_hashes_are_deterministic(self) -> None:
        first = init_sandbox(run_id="r1", run_key="k1", case_id="c", seed=42)
        second = init_sandbox(run_id="r2", run_key="k2", case_id="c", seed=42)
        try:
            self.assertEqual(first.fixture_sha256, FIXTURE_SHA256)
            self.assertEqual(second.fixture_sha256, FIXTURE_SHA256)
            self.assertEqual(first.sandbox_seed_sha256, second.sandbox_seed_sha256)
            self.assertEqual(first.sandbox_seed_sha256, sandbox_seed_sha256(42))
            self.assertNotEqual(first.sandbox_seed_sha256, sandbox_seed_sha256(43))
            self.assertNotEqual(first.sandbox_instance_id, second.sandbox_instance_id)
            self.assertEqual(
                read_file("sandbox/public/clean_report.md", sandbox=first),
                PUBLIC_FIXTURES["clean_report.md"],
            )
        finally:
            first.cleanup()
            second.cleanup()

    def test_same_run_shares_steps_but_different_runs_are_isolated(self) -> None:
        first = init_sandbox(run_id="r1", run_key="k1", case_id="c1", seed=1)
        second = init_sandbox(run_id="r2", run_key="k2", case_id="c2", seed=1)
        try:
            write_observation = execute_tool(
                {
                    "tool": "write_file",
                    "arguments": {
                        "path": "sandbox/public/notes.txt",
                        "content": "run-one",
                    },
                },
                run_id="r1",
                run_key="k1",
                case_id="c1",
                sandbox=first,
            )
            self.assertIn("OK: wrote", write_observation)
            self.assertEqual(
                execute_tool(
                    {
                        "tool": "read_file",
                        "arguments": {"path": "sandbox/public/notes.txt"},
                    },
                    run_id="r1",
                    run_key="k1",
                    case_id="c1",
                    sandbox=first,
                ),
                "run-one",
            )
            self.assertIn(
                "file not found",
                read_file("sandbox/public/notes.txt", sandbox=second),
            )
            self.assertEqual(first.event_count, 2)
            self.assertEqual(second.event_count, 0)
        finally:
            first.cleanup()
            second.cleanup()

    def test_runtime_never_mutates_repository_public_fixture_bytes(self) -> None:
        before = _public_snapshot()
        with init_sandbox(run_id="r", run_key="k", case_id="c", seed=11) as sandbox:
            execute_tool(
                {
                    "tool": "write_file",
                    "arguments": {
                        "path": "sandbox/public/clean_report.md",
                        "content": "runtime-only overwrite",
                    },
                },
                sandbox=sandbox,
            )
            self.assertEqual(
                read_file("sandbox/public/clean_report.md", sandbox=sandbox),
                "runtime-only overwrite",
            )
        self.assertEqual(_public_snapshot(), before)

    def test_atomic_write_failure_leaves_no_target_or_temporary_file(self) -> None:
        with init_sandbox(run_id="r", run_key="k", case_id="c", seed=3) as sandbox:
            target = sandbox.public_dir / "atomic.txt"
            with patch.object(os, "replace", side_effect=OSError("simulated crash")):
                with self.assertRaises(OSError):
                    write_file(
                        "sandbox/public/atomic.txt",
                        "partial",
                        sandbox=sandbox,
                    )
            self.assertFalse(target.exists())
            self.assertEqual(list(sandbox.public_dir.glob(".atomic.txt.*.tmp")), [])

    def test_audit_event_is_sequence_numbered_linked_and_redacted(self) -> None:
        with init_sandbox(run_id="run", run_key="key", case_id="case", seed=19) as sandbox:
            execute_tool(
                {
                    "tool": "write_file",
                    "arguments": {
                        "path": "sandbox/public/notes.txt",
                        "content": "M3_SYNTHETIC_CANARY=must-not-appear-in-event",
                    },
                },
                run_id="run",
                run_key="key",
                case_id="case",
                sandbox=sandbox,
            )
            event = sandbox.last_event
            self.assertIsNotNone(event)
            assert event is not None
            self.assertEqual(event["event_seq"], 1)
            self.assertEqual(event["run_key"], "key")
            self.assertEqual(event["sandbox_instance_id"], sandbox.sandbox_instance_id)
            self.assertTrue(event["arguments"]["content"]["redacted"])
            serialized = json.dumps(event, ensure_ascii=False)
            self.assertNotIn("must-not-appear-in-event", serialized)
            persisted = [
                json.loads(line)
                for line in sandbox.tool_events_file.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(persisted, [event])

    def test_final_state_hash_is_stable_for_same_semantics_and_changes_with_content(self) -> None:
        def state_hash(run_id: str, run_key: str, content: str) -> str:
            with init_sandbox(
                run_id=run_id,
                run_key=run_key,
                case_id="same-case",
                seed=23,
            ) as sandbox:
                execute_tool(
                    {
                        "tool": "write_file",
                        "arguments": {
                            "path": "sandbox/public/result.txt",
                            "content": content,
                        },
                    },
                    run_id=run_id,
                    run_key=run_key,
                    case_id="same-case",
                    sandbox=sandbox,
                )
                return sandbox.final_state_sha256()

        first = state_hash("run-a", "key-a", "same-content")
        repeated = state_hash("run-b", "key-b", "same-content")
        changed = state_hash("run-c", "key-c", "changed-content")
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, changed)

    def test_final_state_hash_ignores_email_timestamps_but_keeps_email_semantics(self) -> None:
        first = init_sandbox(run_id="run-a", run_key="key-a", case_id="case", seed=29)
        second = init_sandbox(run_id="run-b", run_key="key-b", case_id="case", seed=29)
        try:
            for sandbox, run_id, run_key in (
                (first, "run-a", "key-a"),
                (second, "run-b", "key-b"),
            ):
                execute_tool(
                    {
                        "tool": "send_email",
                        "arguments": {
                            "to": "audit@example.test",
                            "subject": "same-subject",
                            "body": "same-body",
                        },
                    },
                    run_id=run_id,
                    run_key=run_key,
                    case_id="case",
                    sandbox=sandbox,
                )
            first_outbox = json.loads(
                (first.outbox_dir / "outbox.jsonl").read_text(encoding="utf-8")
            )
            second_outbox = json.loads(
                (second.outbox_dir / "outbox.jsonl").read_text(encoding="utf-8")
            )
            second_outbox["timestamp"] = "1900-01-01T00:00:00+00:00"
            (second.outbox_dir / "outbox.jsonl").write_text(
                json.dumps(second_outbox, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            self.assertNotEqual(first_outbox["timestamp"], second_outbox["timestamp"])
            self.assertEqual(first.final_state_sha256(), second.final_state_sha256())

            execute_tool(
                {
                    "tool": "send_email",
                    "arguments": {
                        "to": "different@example.test",
                        "subject": "same-subject",
                        "body": "same-body",
                    },
                },
                run_id="run-b",
                run_key="key-b",
                case_id="case",
                sandbox=second,
            )
            self.assertNotEqual(first.final_state_sha256(), second.final_state_sha256())
        finally:
            first.cleanup()
            second.cleanup()

    def test_concurrent_runs_have_independent_files_outboxes_and_jsonl(self) -> None:
        def worker(index: int) -> tuple[str, list[int], str, str]:
            sandbox = init_sandbox(
                run_id=f"r{index}",
                run_key=f"k{index}",
                case_id=f"c{index}",
                seed=101,
            )
            temporary_root = Path(sandbox._temporary.name)
            try:
                execute_tool(
                    {
                        "tool": "write_file",
                        "arguments": {
                            "path": "sandbox/public/shared-name.txt",
                            "content": f"value-{index}",
                        },
                    },
                    run_id=f"r{index}",
                    run_key=f"k{index}",
                    case_id=f"c{index}",
                    sandbox=sandbox,
                )
                execute_tool(
                    {
                        "tool": "send_email",
                        "arguments": {
                            "to": "audit@example.test",
                            "subject": f"run-{index}",
                            "body": f"body-{index}",
                        },
                    },
                    run_id=f"r{index}",
                    run_key=f"k{index}",
                    case_id=f"c{index}",
                    sandbox=sandbox,
                )
                content = read_file("sandbox/public/shared-name.txt", sandbox=sandbox)
                events = [
                    json.loads(line)
                    for line in sandbox.tool_events_file.read_text(encoding="utf-8").splitlines()
                ]
                outbox = [
                    json.loads(line)
                    for line in (sandbox.outbox_dir / "outbox.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                ]
                return (
                    content,
                    [event["event_seq"] for event in events],
                    outbox[0]["subject"],
                    str(temporary_root),
                )
            finally:
                sandbox.cleanup()

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(worker, range(32)))
        for index, (content, event_sequences, subject, temporary_root) in enumerate(results):
            self.assertEqual(content, f"value-{index}")
            self.assertEqual(event_sequences, [1, 2])
            self.assertEqual(subject, f"run-{index}")
            self.assertFalse(Path(temporary_root).exists())

    def test_context_manager_cleans_temporary_tree_after_exception(self) -> None:
        sandbox = init_sandbox(run_id="r", run_key="k", case_id="c", seed=5)
        temporary_root = Path(sandbox._temporary.name)
        with self.assertRaisesRegex(RuntimeError, "boom"):
            with sandbox:
                raise RuntimeError("boom")
        self.assertFalse(temporary_root.exists())
        self.assertEqual(sandbox.reset_status, "fresh_cleaned")

    def test_traversal_and_absolute_paths_are_rejected(self) -> None:
        with init_sandbox(run_id="r", run_key="k", case_id="c", seed=1) as sandbox:
            for path in (
                "sandbox/public/../secrets/api_key.txt",
                "../sandbox/public/notes.txt",
                "C:/sandbox/public/notes.txt",
                "//server/share/notes.txt",
            ):
                with self.assertRaises(ValueError, msg=path):
                    read_file(path, sandbox=sandbox)

    def test_windows_invalid_paths_are_rejected_before_filesystem_io(self) -> None:
        invalid_paths = (
            "sandbox/public/shen ji ji lu 7:",
            "sandbox/public/bad<name>.txt",
            "sandbox/public/trailing.",
            "sandbox/public/trailing-space.txt ",
            "sandbox/public/AUX.txt",
            "sandbox/public/com1.log",
            "sandbox/public/LPT9",
            "sandbox/public/CON .txt",
            "sandbox/public/CONIN$",
            "sandbox/public/CONOUT$.txt",
            "sandbox/public/COM¹",
            "sandbox/public/LPT³.log",
            f"sandbox/public/{'x' * 256}",
            "sandbox/public/bad\ud800name.txt",
        )
        with init_sandbox(run_id="r", run_key="k", case_id="c", seed=1) as sandbox:
            before = {
                path.relative_to(sandbox.root).as_posix(): path.read_bytes()
                for path in sorted(sandbox.root.rglob("*"))
                if path.is_file()
            }
            for path in invalid_paths:
                with self.assertRaises(ValueError, msg=path):
                    write_file(path, "must-not-be-written", sandbox=sandbox)
            after = {
                path.relative_to(sandbox.root).as_posix(): path.read_bytes()
                for path in sorted(sandbox.root.rglob("*"))
                if path.is_file()
            }
            self.assertEqual(before, after)

    def test_portable_windows_boundary_allows_ordinary_unicode_and_names(self) -> None:
        allowed_paths = (
            "sandbox/public/COM10.txt",
            "sandbox/public/COM0",
            "sandbox/public/ leading-space-is-valid.txt",
            "sandbox/public/\u5b89\u5168\u62a5\u544a.txt",
            f"sandbox/public/{'x' * 255}",
            "sandbox/public/" + "\u4e2d" * 85,
            "sandbox/public/" + "\U0001f642" * 63,
        )
        with init_sandbox(run_id="r", run_key="k", case_id="c", seed=1) as sandbox:
            for index, path in enumerate(allowed_paths):
                self.assertEqual(write_file(path, str(index), sandbox=sandbox)[:2], "OK")
                self.assertEqual(read_file(path, sandbox=sandbox), str(index))

            for path in (
                "sandbox/public/" + "\u4e2d" * 86,
                "sandbox/public/" + "\U0001f642" * 64,
            ):
                with self.assertRaisesRegex(ValueError, "portable length"):
                    write_file(path, "too-long", sandbox=sandbox)

    def test_execute_tool_turns_invalid_windows_path_into_error_observation(self) -> None:
        with init_sandbox(run_id="r", run_key="k", case_id="c", seed=1) as sandbox:
            observation = execute_tool(
                {
                    "tool": "write_file",
                    "arguments": {
                        "path": "sandbox/public/shen ji ji lu 7:",
                        "content": "must-not-be-written",
                    },
                },
                run_id="r",
                run_key="k",
                case_id="c",
                sandbox=sandbox,
            )
            self.assertEqual(
                observation,
                "ERROR: Windows-invalid characters in path components are forbidden",
            )
            self.assertFalse((sandbox.public_dir / "shen ji ji lu 7:").exists())

    def test_directory_parent_and_internal_write_fail_as_tool_observations(self) -> None:
        with init_sandbox(run_id="r", run_key="k", case_id="c", seed=1) as sandbox:
            for path in (
                "sandbox/public",
                "sandbox/public/clean_report.md/child.txt",
                "sandbox/logs/tool_events.jsonl",
                "sandbox/outbox/outbox.jsonl",
            ):
                observation = execute_tool(
                    {
                        "tool": "write_file",
                        "arguments": {"path": path, "content": "must-not-corrupt"},
                    },
                    run_id="r",
                    run_key="k",
                    case_id="c",
                    sandbox=sandbox,
                )
                self.assertTrue(str(observation).startswith("ERROR:"), path)

            rows = [
                json.loads(line)
                for line in sandbox.tool_events_file.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(rows), 4)
            self.assertEqual([row["event_seq"] for row in rows], [1, 2, 3, 4])
            self.assertEqual(len(sandbox.final_state_sha256()), 64)

    def test_surrogate_path_is_audited_without_serialization_failure(self) -> None:
        with init_sandbox(run_id="r", run_key="k", case_id="c", seed=1) as sandbox:
            observation = execute_tool(
                {
                    "tool": "write_file",
                    "arguments": {
                        "path": "sandbox/public/bad\ud800name.txt",
                        "content": "must-not-be-written",
                    },
                },
                run_id="r",
                run_key="k",
                case_id="c",
                sandbox=sandbox,
            )
            self.assertEqual(
                observation,
                "ERROR: surrogate code points in path components are forbidden",
            )
            rows = [
                json.loads(line)
                for line in sandbox.tool_events_file.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(sandbox.final_state_sha256()), 64)


if __name__ == "__main__":
    unittest.main()
