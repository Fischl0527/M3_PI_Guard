"""Inventory and verify a merged Ollama model store.

This utility is intentionally read-only with respect to model stores.  It
hashes every file under one or more source roots, detects merge collisions,
and can verify that a target root contains the byte-identical union.  Only the
requested JSON evidence file is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "m3-ollama-model-store-audit-1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


@dataclass(frozen=True)
class FileRecord:
    relative_path: str
    size_bytes: int
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


def _records(root: Path) -> list[FileRecord]:
    if not root.is_dir():
        raise FileNotFoundError(f"model-store root is not a directory: {root}")
    rows: list[FileRecord] = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=str):
        rows.append(
            FileRecord(
                relative_path=_relative(path, root),
                size_bytes=path.stat().st_size,
                sha256=_sha256(path),
            )
        )
    return rows


def _model_tags(records: Iterable[FileRecord]) -> list[str]:
    prefix = "manifests/"
    return sorted(
        row.relative_path[len(prefix) :]
        for row in records
        if row.relative_path.startswith(prefix)
    )


def build_inventory(source_roots: list[Path]) -> dict[str, Any]:
    if len(source_roots) < 1:
        raise ValueError("at least one source root is required")

    sources: list[dict[str, Any]] = []
    merged: dict[str, FileRecord] = {}
    owners: dict[str, list[str]] = {}
    conflicts: list[dict[str, Any]] = []

    for root in source_roots:
        resolved = root.resolve(strict=True)
        records = _records(resolved)
        sources.append(
            {
                "path": str(resolved),
                "file_count": len(records),
                "size_bytes": sum(row.size_bytes for row in records),
                "model_tags": _model_tags(records),
                "files": [row.as_dict() for row in records],
            }
        )
        for row in records:
            owners.setdefault(row.relative_path, []).append(str(resolved))
            previous = merged.get(row.relative_path)
            if previous is None:
                merged[row.relative_path] = row
            elif previous != row:
                conflicts.append(
                    {
                        "relative_path": row.relative_path,
                        "existing": previous.as_dict(),
                        "incoming": row.as_dict(),
                        "source_roots": owners[row.relative_path],
                    }
                )

    duplicates = [
        {"relative_path": relative, "source_roots": roots}
        for relative, roots in sorted(owners.items())
        if len(roots) > 1
    ]
    merged_rows = [merged[key] for key in sorted(merged)]
    status = "conflict" if conflicts else "ready"
    return {
        "schema": SCHEMA,
        "generated_at": _utc_now(),
        "status": status,
        "sources": sources,
        "merged_union": {
            "file_count": len(merged_rows),
            "size_bytes": sum(row.size_bytes for row in merged_rows),
            "model_tags": _model_tags(merged_rows),
            "files": [row.as_dict() for row in merged_rows],
            "identical_duplicate_paths": duplicates,
            "conflicts": conflicts,
        },
    }


def validate_target(
    inventory: dict[str, Any],
    target_root: Path,
    *,
    allow_extra: bool = False,
) -> dict[str, Any]:
    target = target_root.resolve(strict=True)
    target_records = {row.relative_path: row for row in _records(target)}
    expected_rows = {
        str(row["relative_path"]): row
        for row in inventory["merged_union"]["files"]
    }

    missing = sorted(set(expected_rows) - set(target_records))
    extra = sorted(set(target_records) - set(expected_rows))
    mismatched: list[dict[str, Any]] = []
    for relative in sorted(set(expected_rows) & set(target_records)):
        expected = expected_rows[relative]
        actual = target_records[relative]
        if (
            int(expected["size_bytes"]) != actual.size_bytes
            or str(expected["sha256"]) != actual.sha256
        ):
            mismatched.append(
                {
                    "relative_path": relative,
                    "expected": expected,
                    "actual": actual.as_dict(),
                }
            )

    status = (
        "passed"
        if not missing and not mismatched and (allow_extra or not extra)
        else "failed"
    )
    return {
        "schema": SCHEMA,
        "generated_at": _utc_now(),
        "status": status,
        "inventory_status": inventory.get("status"),
        "allow_extra": allow_extra,
        "target_path": str(target),
        "expected_file_count": len(expected_rows),
        "actual_file_count": len(target_records),
        "expected_size_bytes": sum(int(row["size_bytes"]) for row in expected_rows.values()),
        "actual_size_bytes": sum(row.size_bytes for row in target_records.values()),
        "missing": missing,
        "extra": extra,
        "mismatched": mismatched,
        "model_tags": _model_tags(target_records.values()),
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory")
    inventory.add_argument("--source", action="append", required=True, type=Path)
    inventory.add_argument("--output", required=True, type=Path)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--inventory", required=True, type=Path)
    validate.add_argument("--target", required=True, type=Path)
    validate.add_argument("--output", required=True, type=Path)
    validate.add_argument(
        "--allow-extra",
        action="store_true",
        help="require the inventory union to be intact while permitting planned new files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "inventory":
        result = build_inventory(args.source)
        _write_json(args.output, result)
        print(json.dumps({"status": result["status"], "output": str(args.output)}))
        return 0 if result["status"] == "ready" else 2

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    result = validate_target(inventory, args.target, allow_extra=args.allow_extra)
    _write_json(args.output, result)
    print(json.dumps({"status": result["status"], "output": str(args.output)}))
    return 0 if result["status"] == "passed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
