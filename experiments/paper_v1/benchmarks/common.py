"""Shared immutable record helpers for public benchmark adapters."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def portable_path(path: Path, *, root: Path) -> str:
    """Render an in-repository path relatively and an external path literally."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def portable_value(value: Any, *, root: Path) -> Any:
    """Recursively normalize checkout-local path strings in JSON-ready values."""

    if isinstance(value, Mapping):
        return {key: portable_value(child, root=root) for key, child in value.items()}
    if isinstance(value, list):
        return [portable_value(child, root=root) for child in value]
    if not isinstance(value, str) or not value.strip():
        return value

    normalized_value = value.replace("\\", "/")
    normalized_root = str(root.resolve()).replace("\\", "/").rstrip("/")
    prefix = f"{normalized_root}/"
    if normalized_value.casefold().startswith(prefix.casefold()):
        return normalized_value[len(prefix) :]
    if normalized_value.casefold() == normalized_root.casefold():
        return "."
    return value


def resolve_artifact_path(value: Path | str, *, root: Path) -> Path:
    """Resolve relative or relocated in-repository references without editing a freeze.

    An existing absolute external path wins.  If an old checkout path no longer
    exists, the reader may relocate its suffix beginning at a current top-level
    repository entry, after which the caller must still verify the declared hash.
    """

    path = Path(value).expanduser()
    if not path.is_absolute():
        return (root / path).resolve()
    resolved = path.resolve()
    if resolved.exists():
        return resolved
    root = root.resolve()
    top_level_names = {child.name.casefold() for child in root.iterdir()}
    for index, part in enumerate(path.parts):
        if part.casefold() not in top_level_names:
            continue
        relocated = root.joinpath(*path.parts[index:]).resolve()
        if relocated.exists():
            return relocated
    return resolved


def huggingface_hub_cache_root(explicit: Path | str | None = None) -> Path:
    """Resolve the Hugging Face Hub cache without assuming the C drive.

    Resolution order matches the paper harness contract: an explicit adapter
    argument wins, followed by ``HF_HUB_CACHE``, ``HF_HOME/hub``, then the
    upstream-compatible user-cache default.
    """

    if explicit:
        return Path(explicit).expanduser().resolve()
    configured_hub = os.environ.get("HF_HUB_CACHE", "").strip()
    if configured_hub:
        return Path(configured_hub).expanduser().resolve()
    configured_home = os.environ.get("HF_HOME", "").strip()
    if configured_home:
        return (Path(configured_home).expanduser() / "hub").resolve()
    return (Path.home() / ".cache" / "huggingface" / "hub").resolve()


def huggingface_model_cache_path(
    model_id: str,
    *,
    hub_cache: Path | str | None = None,
) -> Path:
    return huggingface_hub_cache_root(hub_cache) / (
        "models--" + str(model_id).replace("/", "--")
    )


def huggingface_model_cache_probe(
    model_id: str,
    *,
    hub_cache: Path | str | None = None,
) -> dict[str, Any]:
    """Distinguish a complete local model from a gated/partial Hub cache."""

    cache_root = huggingface_hub_cache_root(hub_cache)
    model_path = huggingface_model_cache_path(model_id, hub_cache=cache_root)
    snapshots_root = model_path / "snapshots"
    snapshots = (
        sorted(path for path in snapshots_root.iterdir() if path.is_dir())
        if snapshots_root.is_dir()
        else []
    )
    snapshot_rows: list[dict[str, Any]] = []
    for snapshot in snapshots:
        files = [path for path in snapshot.rglob("*") if path.is_file()]
        names = [path.name for path in files]
        has_config = "config.json" in names
        has_weights = any(
            name.endswith(".safetensors")
            or name.startswith("pytorch_model") and name.endswith(".bin")
            or name.endswith(".safetensors.index.json")
            or name.endswith(".bin.index.json")
            for name in names
        )
        has_tokenizer = any(
            name in {
                "tokenizer.json",
                "tokenizer_config.json",
                "sentencepiece.bpe.model",
                "spiece.model",
                "tokenizer.model",
                "vocab.json",
            }
            for name in names
        )
        snapshot_rows.append(
            {
                "revision": snapshot.name,
                "path": str(snapshot),
                "file_count": len(files),
                "has_config": has_config,
                "has_weights": has_weights,
                "has_tokenizer": has_tokenizer,
                "complete": has_config and has_weights and has_tokenizer,
            }
        )
    complete_rows = [row for row in snapshot_rows if row["complete"]]
    return {
        "model_id": model_id,
        "hub_cache_root": str(cache_root),
        "model_cache_path": str(model_path),
        "model_cache_exists": model_path.exists(),
        "snapshot_count": len(snapshot_rows),
        "snapshots": snapshot_rows,
        "complete_snapshot_revisions": [row["revision"] for row in complete_rows],
        "model_cache_complete": bool(complete_rows),
    }


def rows_sha256(rows: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(canonical_json(row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def json_schema_value_type(details: Mapping[str, Any]) -> str:
    """Collapse a JSON Schema value into the monitor's supported type set."""

    direct = details.get("type")
    if direct in {"string", "object", "array", "number", "integer", "boolean"}:
        return str(direct)
    for keyword in ("anyOf", "oneOf"):
        alternatives = details.get(keyword)
        if not isinstance(alternatives, list):
            continue
        types = [
            str(item.get("type"))
            for item in alternatives
            if isinstance(item, Mapping) and item.get("type") not in {None, "null"}
        ]
        unique = list(dict.fromkeys(types))
        if len(unique) == 1 and unique[0] in {
            "string", "object", "array", "number", "integer", "boolean"
        }:
            return unique[0]
        if set(unique) == {"integer", "number"}:
            return "number"
    if isinstance(details.get("properties"), Mapping):
        return "object"
    if isinstance(details.get("items"), Mapping):
        return "array"
    return "object"


def infer_side_effect(tool_name: str) -> bool:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(tool_name))
    tokens = set(re.findall(r"[a-z0-9]+", expanded.replace("_", " ").casefold()))
    effect_verbs = (
        "add",
        "append",
        "send",
        "write",
        "create",
        "delete",
        "remove",
        "update",
        "transfer",
        "book",
        "reserve",
        "cancel",
        "post",
        "share",
        "invite",
        "pay",
        "buy",
        "sell",
        "change",
        "reschedule",
        "schedule",
    )
    return bool(tokens & set(effect_verbs))
