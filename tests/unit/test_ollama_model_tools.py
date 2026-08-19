from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.audit_ollama_model_store import build_inventory, validate_target


class OllamaModelStoreAuditTests(unittest.TestCase):
    def test_allow_extra_preserves_union_integrity_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "old-model").write_bytes(b"old")
            (target / "old-model").write_bytes(b"old")
            (target / "new-model").write_bytes(b"new")
            inventory = build_inventory([source])

            strict = validate_target(inventory, target)
            additive = validate_target(inventory, target, allow_extra=True)

            self.assertEqual(strict["status"], "failed")
            self.assertEqual(additive["status"], "passed")
            self.assertEqual(additive["missing"], [])
            self.assertEqual(additive["mismatched"], [])
            self.assertEqual(additive["extra"], ["new-model"])

    def test_allow_extra_still_rejects_changed_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "old-model").write_bytes(b"old")
            inventory = build_inventory([source])
            (target / "old-model").write_bytes(b"changed")

            result = validate_target(inventory, target, allow_extra=True)

            self.assertEqual(result["status"], "failed")
            self.assertEqual(len(result["mismatched"]), 1)


if __name__ == "__main__":
    unittest.main()
