"""Fail-closed identity checks shared by future formal-run adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .common import resolve_artifact_path, sha256_file


ROOT = Path(__file__).resolve().parents[3]


def validate_hash_bound_files(binding: Mapping[str, Any]) -> dict[str, str]:
    files = binding.get("files", {})
    hashes = binding.get("sha256", {})
    if not isinstance(files, Mapping) or not isinstance(hashes, Mapping) or not files:
        raise ValueError("freeze is missing hash-bound local adapter files")
    observed: dict[str, str] = {}
    mismatches: list[str] = []
    for name, raw_path in files.items():
        path = resolve_artifact_path(str(raw_path), root=ROOT)
        digest = sha256_file(path) if path.exists() else ""
        observed[str(name)] = digest
        if not str(hashes.get(name, "")) or digest != str(hashes.get(name, "")):
            mismatches.append(str(name))
    if mismatches:
        raise ValueError("local adapter freeze hash mismatch: " + ", ".join(sorted(mismatches)))
    return observed


def validate_resume_identity(
    *,
    manifest_path: Path,
    expected: Mapping[str, Any],
) -> None:
    if not manifest_path.exists():
        return
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("existing run manifest must contain a JSON object")
    mismatches = [name for name, expected_value in expected.items() if value.get(name) != expected_value]
    if mismatches:
        raise ValueError(
            "resume root identity mismatch; use a new output directory: "
            + ", ".join(sorted(mismatches))
        )
