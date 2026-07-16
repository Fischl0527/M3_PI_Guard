"""Strict, self-contained figure bundle manifests.

Each figure references one adjacent data file plus PNG and SVG renderings.  All
paths are POSIX-style paths relative to the bundle directory.  Writers record
file sizes and SHA-256 digests; loaders reject traversal, links, and any drift.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


FIGURE_MANIFEST_FILENAME = "figure_manifest.json"
FIGURE_MANIFEST_SCHEMA_VERSION = "1.0"

_TOP_LEVEL_KEYS = {"schema_version", "experiment_id", "evidence_tier", "figures"}
_FIGURE_KEYS = {
    "id",
    "title",
    "role",
    "order",
    "chart_type",
    "caption",
    "files",
    "metrics",
    "grain",
    "uncertainty",
    "warnings",
}
_FILE_KEYS = {"path", "bytes", "sha256"}
_FILE_ROLES = ("data", "png", "svg")
_FIGURE_ROLES = {"primary", "secondary", "diagnostic"}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_EXPERIMENT_RE = re.compile(r"^E(?:0|[1-9][0-9]*)$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class FigureManifestError(ValueError):
    """Raised when a figure bundle violates its schema or integrity contract."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def _bundle_root(bundle_dir: str | Path) -> Path:
    raw = Path(bundle_dir).expanduser()
    if _is_link(raw):
        raise FigureManifestError(f"bundle directory must not be a link: {raw}")
    root = raw.resolve()
    if not root.exists() or not root.is_dir():
        raise FigureManifestError(f"bundle directory does not exist: {root}")
    return root


def _relative_path(value: Any, *, label: str) -> Path:
    if isinstance(value, Path):
        text = value.as_posix()
    elif isinstance(value, str):
        text = value
    else:
        raise FigureManifestError(f"{label} path must be a string")
    if not text or "\x00" in text:
        raise FigureManifestError(f"{label} path is empty or invalid")
    if "\\" in text:
        raise FigureManifestError(f"{label} path must use POSIX '/' separators: {text!r}")
    relative = Path(text)
    if relative.is_absolute() or relative.drive or text.startswith("//"):
        raise FigureManifestError(f"{label} path must be bundle-relative: {text!r}")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise FigureManifestError(f"{label} path contains traversal or empty components: {text!r}")
    return relative


def _strict_bundle_file(root: Path, value: Any, *, label: str) -> tuple[str, Path]:
    relative = _relative_path(value, label=label)
    current = root
    for part in relative.parts:
        current = current / part
        if _is_link(current):
            raise FigureManifestError(f"{label} path contains a symbolic link or junction: {relative.as_posix()}")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise FigureManifestError(f"{label} path escapes bundle: {relative.as_posix()}") from exc
    if not resolved.exists() or not resolved.is_file():
        raise FigureManifestError(f"{label} file does not exist: {relative.as_posix()}")
    return relative.as_posix(), resolved


def _string(value: Any, *, label: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FigureManifestError(f"{label} must be a non-empty string")
    result = value.strip()
    if pattern is not None and pattern.fullmatch(result) is None:
        raise FigureManifestError(f"{label} has invalid value: {result!r}")
    return result


def _string_list(value: Any, *, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise FigureManifestError(f"{label} must be a list of non-empty strings")
    return [item.strip() for item in value]


def _uncertainty(value: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise FigureManifestError(f"{label} must be a list of JSON objects")
    result = [deepcopy(dict(item)) for item in value]
    try:
        json.dumps(result, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise FigureManifestError(f"{label} must contain finite JSON values") from exc
    return result


def _figure_metadata(source: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    extra = set(source) - _FIGURE_KEYS
    missing = _FIGURE_KEYS - set(source)
    if extra or missing:
        raise FigureManifestError(
            f"figures[{index}] keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    figure_id = _string(source["id"], label=f"figures[{index}].id", pattern=_ID_RE)
    role = _string(source["role"], label=f"figures[{index}].role")
    if role not in _FIGURE_ROLES:
        raise FigureManifestError(f"figures[{index}].role must be one of {sorted(_FIGURE_ROLES)}")
    order = source["order"]
    if isinstance(order, bool) or not isinstance(order, int) or order < 0:
        raise FigureManifestError(f"figures[{index}].order must be a non-negative integer")
    return {
        "id": figure_id,
        "title": _string(source["title"], label=f"figures[{index}].title"),
        "role": role,
        "order": order,
        "chart_type": _string(source["chart_type"], label=f"figures[{index}].chart_type"),
        "caption": _string(source["caption"], label=f"figures[{index}].caption"),
        "metrics": _string_list(source["metrics"], label=f"figures[{index}].metrics"),
        "grain": _string_list(source["grain"], label=f"figures[{index}].grain"),
        "uncertainty": _uncertainty(source["uncertainty"], label=f"figures[{index}].uncertainty"),
        "warnings": _string_list(source["warnings"], label=f"figures[{index}].warnings"),
    }


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def write_figure_manifest(
    bundle_dir: str | Path,
    *,
    experiment_id: str,
    evidence_tier: str,
    figures: Sequence[Mapping[str, Any]],
) -> Path:
    """Write a deterministic figure manifest after validating every asset."""

    root = _bundle_root(bundle_dir)
    experiment = _string(experiment_id, label="experiment_id", pattern=_EXPERIMENT_RE)
    tier = _string(evidence_tier, label="evidence_tier")
    if not isinstance(figures, Sequence) or isinstance(figures, (str, bytes)) or not figures:
        raise FigureManifestError("figures must be a non-empty sequence")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, source in enumerate(figures):
        if not isinstance(source, Mapping):
            raise FigureManifestError(f"figures[{index}] must be an object")
        metadata = _figure_metadata(source, index=index)
        if metadata["id"] in seen_ids:
            raise FigureManifestError(f"duplicate figure id: {metadata['id']}")
        seen_ids.add(metadata["id"])
        files = source["files"]
        if not isinstance(files, Mapping) or set(files) != set(_FILE_ROLES):
            raise FigureManifestError(f"figures[{index}].files must contain exactly {list(_FILE_ROLES)}")
        normalized_files: dict[str, dict[str, Any]] = {}
        for file_role in _FILE_ROLES:
            file_value = files[file_role]
            if isinstance(file_value, Mapping):
                if set(file_value) != {"path"}:
                    raise FigureManifestError(
                        f"figures[{index}].files.{file_role} writer input must contain only 'path'"
                    )
                file_value = file_value["path"]
            relative, resolved = _strict_bundle_file(
                root, file_value, label=f"figures[{index}].files.{file_role}"
            )
            if relative == FIGURE_MANIFEST_FILENAME:
                raise FigureManifestError("figure manifest cannot reference itself")
            size = resolved.stat().st_size
            if size <= 0:
                raise FigureManifestError(f"figure asset is empty: {relative}")
            normalized_files[file_role] = {
                "path": relative,
                "bytes": size,
                "sha256": sha256_file(resolved),
            }
        normalized.append({**metadata, "files": normalized_files})
    normalized.sort(key=lambda item: (int(item["order"]), str(item["id"])))
    payload = {
        "schema_version": FIGURE_MANIFEST_SCHEMA_VERSION,
        "experiment_id": experiment,
        "evidence_tier": tier,
        "figures": normalized,
    }
    target = root / FIGURE_MANIFEST_FILENAME
    if _is_link(target):
        raise FigureManifestError(f"refusing to replace linked figure manifest: {target}")
    _atomic_write_json(target, payload)
    return target


def load_figure_manifest(
    path_or_bundle: str | Path,
    *,
    expected_experiment_id: str | None = None,
) -> dict[str, Any]:
    """Load and re-verify a figure manifest, adding resolved paths in memory."""

    source = Path(path_or_bundle).expanduser()
    if source.is_dir():
        root = _bundle_root(source)
        manifest_path = root / FIGURE_MANIFEST_FILENAME
    else:
        if _is_link(source):
            raise FigureManifestError(f"figure manifest must not be a link: {source}")
        manifest_path = source.resolve()
        root = _bundle_root(manifest_path.parent)
    if manifest_path.name != FIGURE_MANIFEST_FILENAME:
        raise FigureManifestError(f"expected {FIGURE_MANIFEST_FILENAME}, got {manifest_path.name}")
    if not manifest_path.exists() or not manifest_path.is_file() or _is_link(manifest_path):
        raise FigureManifestError(f"figure manifest does not exist or is linked: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FigureManifestError(f"cannot read figure manifest: {manifest_path}") from exc
    if not isinstance(payload, dict):
        raise FigureManifestError("figure manifest must be a JSON object")
    extra = set(payload) - _TOP_LEVEL_KEYS
    missing = _TOP_LEVEL_KEYS - set(payload)
    if extra or missing:
        raise FigureManifestError(
            f"figure manifest keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    if payload["schema_version"] != FIGURE_MANIFEST_SCHEMA_VERSION:
        raise FigureManifestError(f"unsupported figure manifest schema: {payload['schema_version']!r}")
    experiment = _string(payload["experiment_id"], label="experiment_id", pattern=_EXPERIMENT_RE)
    if expected_experiment_id is not None and experiment != expected_experiment_id:
        raise FigureManifestError(
            f"figure manifest experiment mismatch: expected {expected_experiment_id}, got {experiment}"
        )
    tier = _string(payload["evidence_tier"], label="evidence_tier")
    figures = payload["figures"]
    if not isinstance(figures, list) or not figures:
        raise FigureManifestError("figures must be a non-empty list")
    verified: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    previous_sort_key: tuple[int, str] | None = None
    for index, source_figure in enumerate(figures):
        if not isinstance(source_figure, Mapping):
            raise FigureManifestError(f"figures[{index}] must be an object")
        metadata = _figure_metadata(source_figure, index=index)
        if metadata["id"] in seen_ids:
            raise FigureManifestError(f"duplicate figure id: {metadata['id']}")
        seen_ids.add(metadata["id"])
        sort_key = (metadata["order"], metadata["id"])
        if previous_sort_key is not None and sort_key < previous_sort_key:
            raise FigureManifestError("figures must be sorted by order then id")
        previous_sort_key = sort_key
        files = source_figure["files"]
        if not isinstance(files, Mapping) or set(files) != set(_FILE_ROLES):
            raise FigureManifestError(f"figures[{index}].files must contain exactly {list(_FILE_ROLES)}")
        verified_files: dict[str, dict[str, Any]] = {}
        for file_role in _FILE_ROLES:
            entry = files[file_role]
            if not isinstance(entry, Mapping) or set(entry) != _FILE_KEYS:
                raise FigureManifestError(
                    f"figures[{index}].files.{file_role} must contain path, bytes, sha256"
                )
            expected_bytes = entry["bytes"]
            expected_sha = entry["sha256"]
            if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) or expected_bytes <= 0:
                raise FigureManifestError(f"figures[{index}].files.{file_role}.bytes is invalid")
            if not isinstance(expected_sha, str) or _SHA256_RE.fullmatch(expected_sha) is None:
                raise FigureManifestError(f"figures[{index}].files.{file_role}.sha256 is invalid")
            relative, resolved = _strict_bundle_file(
                root, entry["path"], label=f"figures[{index}].files.{file_role}"
            )
            actual_bytes = resolved.stat().st_size
            if actual_bytes != expected_bytes:
                raise FigureManifestError(
                    f"figure asset byte-size mismatch for {relative}: expected {expected_bytes}, got {actual_bytes}"
                )
            actual_sha = sha256_file(resolved)
            if actual_sha != expected_sha:
                raise FigureManifestError(
                    f"figure asset SHA-256 mismatch for {relative}: expected {expected_sha}, got {actual_sha}"
                )
            verified_files[file_role] = {
                "path": relative,
                "bytes": expected_bytes,
                "sha256": expected_sha,
                "resolved_path": str(resolved),
            }
        verified.append({**metadata, "files": verified_files})
    return {
        "schema_version": FIGURE_MANIFEST_SCHEMA_VERSION,
        "experiment_id": experiment,
        "evidence_tier": tier,
        "figures": verified,
        "manifest_path": str(manifest_path),
        "bundle_dir": str(root),
    }


__all__ = [
    "FIGURE_MANIFEST_FILENAME",
    "FIGURE_MANIFEST_SCHEMA_VERSION",
    "FigureManifestError",
    "load_figure_manifest",
    "sha256_file",
    "write_figure_manifest",
]
