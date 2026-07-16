from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

from experiments.stub_repro_audit import compare_stub_runs, semantic_rows


class StubReproAuditTests(unittest.TestCase):
    def _write_matrix(self, root: Path, name: str, row: dict[str, Any]) -> Path:
        log = root / f"{name}.jsonl"
        log.write_text(json.dumps(row) + "\n", encoding="utf-8")
        manifest = root / f"{name}.json"
        manifest.write_text(
            json.dumps(
                {
                    "backend": "stub",
                    "oracle_stub": True,
                    "status": "completed",
                    "results": [
                        {
                            "condition_id": "normal_off",
                            "status": "completed",
                            "error_count": 0,
                            "jsonl": str(log),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def _matrix(self, root: Path, name: str, answer: str, latency: float) -> Path:
        row = {
            "run_id": name,
            "condition_id": "normal_off",
            "case_id": "BEN-1",
            "replicate_id": 0,
            "seed": 42,
            "step": 1,
            "parsed_tool_call": {"tool": "final", "arguments": {"answer": answer}},
            "guard_decision": "not_applicable",
            "guard_trace": [{"module": "policy", "decision": "allow", "latency_ms": latency}],
            "final_status": "completed",
            "model_latency_ms": latency,
            "started_at": f"2026-01-01T00:00:0{latency}Z",
        }
        return self._write_matrix(root, name, row)

    def _sandbox_matrix(
        self,
        root: Path,
        name: str,
        mutate: Callable[[dict[str, Any]], None] | None = None,
    ) -> Path:
        instance_id = f"instance-{name}"
        runtime_root = root / f"m3-pi-guard-sandbox-{name}" / "sandbox"
        outbox = runtime_root / "outbox" / "outbox.jsonl"
        arguments = {
            "to": "owner@example.test",
            "subject": "Report",
            "body": "Ready",
            "metadata": {"timestamp": "scheduled-at-09:00"},
        }
        observation = {
            "status": "MOCK_EMAIL_QUEUED",
            "outbox": str(outbox),
        }
        row: dict[str, Any] = {
            "run_id": f"run-{name}",
            "run_key": "normal_off:BEN-TOOL-1:r0:s42:stable",
            "condition_id": "normal_off",
            "case_id": "BEN-TOOL-1",
            "replicate_id": 0,
            "seed": 42,
            "step": 1,
            "parsed_tool_call": {"tool": "send_email", "arguments": arguments},
            "guard_decision": "allow",
            "guard_trace": [
                {"module": "policy", "decision": "allow", "latency_ms": len(name) + 0.5}
            ],
            "observation": observation,
            "final_status": "running",
            "model_latency_ms": len(name) + 1.0,
            "started_at": f"2026-01-01T00:00:{len(name):02d}Z",
            "sandbox_instance_id": instance_id,
            "sandbox_root": str(runtime_root),
            "sandbox_runtime_version": "isolated-tool-sandbox-v2",
            "sandbox_fixture_sha256": "f" * 64,
            "sandbox_seed_sha256": "s" * 64,
            "sandbox_final_state_sha256": "a" * 64,
            "sandbox_reset_status": "fresh_cleaned",
            "sandbox_event_count": 1,
            "sandbox_event": {
                "schema_version": "2.0",
                "event_id": f"{instance_id}:1",
                "event_seq": 1,
                "ts": f"2026-01-01T00:00:{len(name):02d}Z",
                "run_id": f"run-{name}",
                "run_key": "normal_off:BEN-TOOL-1:r0:s42:stable",
                "case_id": "BEN-TOOL-1",
                "sandbox_instance_id": instance_id,
                "sandbox_seed_sha256": "s" * 64,
                "sandbox_fixture_sha256": "f" * 64,
                "tool": "send_email",
                "arguments": arguments,
                # Raw hashes legitimately differ when the observation embeds a
                # per-run absolute root; the audit recomputes semantic hashes.
                "arguments_sha256": f"raw-arguments-{name}",
                "allowed": True,
                "observation_preview": f"queued at {outbox}",
                "observation_sha256": f"raw-observation-{name}",
                "mock_only": True,
            },
        }
        if mutate is not None:
            mutate(row)
        return self._write_matrix(root, name, row)

    def test_ignores_only_volatile_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = self._matrix(root, "a", "same", 1.0)
            second = self._matrix(root, "b", "same", 99.0)
            result = compare_stub_runs(first, second)
            self.assertTrue(result["exact_semantic_match"])
            self.assertEqual(result["mismatch_count"], 0)

    def test_detects_semantic_output_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = self._matrix(root, "a", "one", 1.0)
            second = self._matrix(root, "b", "two", 1.0)
            result = compare_stub_runs(first, second)
            self.assertFalse(result["exact_semantic_match"])
            self.assertEqual(result["mismatch_count"], 1)

    def test_sandbox_run_identity_and_temp_roots_are_canonicalized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = self._sandbox_matrix(root, "first")
            second = self._sandbox_matrix(root, "second-run")

            result = compare_stub_runs(first, second)
            self.assertTrue(result["exact_semantic_match"])
            self.assertEqual(result["mismatch_count"], 0)
            self.assertEqual(result["first_semantic_sha256"], result["second_semantic_sha256"])

            canonical = next(iter(semantic_rows(first).values()))
            self.assertNotIn("sandbox_instance_id", canonical)
            self.assertEqual(canonical["sandbox_root"], "sandbox")
            self.assertEqual(
                canonical["observation"],
                {
                    "outbox": "sandbox/outbox/outbox.jsonl",
                    "status": "MOCK_EMAIL_QUEUED",
                },
            )
            event = canonical["sandbox_event"]
            for key in ("event_id", "run_id", "sandbox_instance_id", "timestamp", "ts"):
                self.assertNotIn(key, event)
            self.assertEqual(event["event_seq"], 1)
            self.assertEqual(event["tool"], "send_email")
            self.assertEqual(event["arguments"]["to"], "owner@example.test")
            self.assertEqual(
                event["observation_preview"],
                "queued at sandbox/outbox/outbox.jsonl",
            )
            self.assertEqual(canonical["sandbox_runtime_version"], "isolated-tool-sandbox-v2")
            self.assertEqual(canonical["sandbox_fixture_sha256"], "f" * 64)
            self.assertEqual(canonical["sandbox_seed_sha256"], "s" * 64)
            self.assertEqual(canonical["sandbox_final_state_sha256"], "a" * 64)
            self.assertEqual(canonical["sandbox_reset_status"], "fresh_cleaned")
            self.assertEqual(canonical["sandbox_event_count"], 1)

    def test_stable_sandbox_evidence_and_tool_semantics_are_not_ignored(self) -> None:
        def set_event(row: dict[str, Any], key: str, value: Any) -> None:
            row["sandbox_event"][key] = value

        mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
            ("runtime", lambda row: row.__setitem__("sandbox_runtime_version", "v2")),
            ("fixture", lambda row: row.__setitem__("sandbox_fixture_sha256", "0" * 64)),
            ("seed", lambda row: row.__setitem__("sandbox_seed_sha256", "1" * 64)),
            ("final_state", lambda row: row.__setitem__("sandbox_final_state_sha256", "2" * 64)),
            ("reset", lambda row: row.__setitem__("sandbox_reset_status", "cleanup_failed")),
            ("event_count", lambda row: row.__setitem__("sandbox_event_count", 2)),
            (
                "tool_action",
                lambda row: row["parsed_tool_call"].__setitem__("tool", "call_api"),
            ),
            (
                "tool_argument",
                lambda row: row["parsed_tool_call"]["arguments"].__setitem__(
                    "to", "other@example.test"
                ),
            ),
            (
                "argument_timestamp",
                lambda row: row["parsed_tool_call"]["arguments"]["metadata"].__setitem__(
                    "timestamp", "scheduled-at-10:00"
                ),
            ),
            (
                "observation",
                lambda row: row["observation"].__setitem__("status", "MOCK_EMAIL_FAILED"),
            ),
            ("event_tool", lambda row: set_event(row, "tool", "call_api")),
            (
                "event_arguments",
                lambda row: row["sandbox_event"]["arguments"].__setitem__(
                    "to", "other@example.test"
                ),
            ),
            ("event_seq", lambda row: set_event(row, "event_seq", 2)),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = self._sandbox_matrix(root, "baseline")
            for label, mutation in mutations:
                with self.subTest(field=label):
                    changed = self._sandbox_matrix(root, f"changed-{label}", mutation)
                    result = compare_stub_runs(baseline, changed)
                    self.assertFalse(result["exact_semantic_match"])
                    self.assertEqual(result["mismatch_count"], 1)


if __name__ == "__main__":
    unittest.main()
