#!/usr/bin/env python3
"""Verify the immutable custodian toolkit files without reading private data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_NAME = "toolkit_manifest_v2.json"
WRITABLE_ROOTS = (
    "incoming_from_developer",
    "private",
    "receipts",
    "release",
    "signatures",
)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_child(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts or "\\" in relative:
        raise ValueError(f"unsafe manifest path: {relative}")
    target = root.joinpath(*pure.parts)
    if not target.resolve(strict=False).is_relative_to(root):
        raise ValueError(f"manifest path escapes toolkit: {relative}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--pristine", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    manifest_path = root / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    core = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    expected_manifest_sha = hashlib.sha256(canonical(core)).hexdigest()
    checks: dict[str, bool] = {
        "root_is_directory": root.is_dir(),
        "manifest_digest_matches": manifest.get("manifest_sha256") == expected_manifest_sha,
        "manifest_status_sealed": manifest.get("status") == "sealed_label_empty_toolkit",
    }
    listed: set[Path] = {manifest_path}
    for index, entry in enumerate(manifest.get("files", []), start=1):
        relative = str(entry.get("path", ""))
        target = safe_child(root, relative)
        listed.add(target)
        checks[f"file_{index:02d}_regular"] = target.is_file() and not target.is_symlink()
        checks[f"file_{index:02d}_size"] = target.is_file() and target.stat().st_size == entry.get("bytes")
        checks[f"file_{index:02d}_sha256"] = target.is_file() and sha256_file(target) == entry.get("sha256")
    extras: list[str] = []
    private_entries: list[str] = []
    symlinks: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            symlinks.append(relative)
            continue
        under_writable = relative.split("/", maxsplit=1)[0] in WRITABLE_ROOTS
        if path.is_file() and path not in listed and not under_writable:
            extras.append(relative)
        if args.pristine and under_writable and path.is_file():
            private_entries.append(relative)
    checks["no_symlinks"] = not symlinks
    checks["no_unlisted_immutable_files"] = not extras
    checks["work_directories_pristine"] = not args.pristine or not private_entries
    passed = all(checks.values())
    result = {
        "schema_version": "m3-paper-v2-custodian-toolkit-verification-2.0",
        "status": "toolkit_verified" if passed else "toolkit_rejected",
        "checks": checks,
        "diagnostics": {
            "unlisted_immutable_files": sorted(extras),
            "pristine_work_entries": sorted(private_entries),
            "symlinks": sorted(symlinks),
        },
        "private_content_opened": False,
        "credentials_read": False,
        "network_calls_made": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
