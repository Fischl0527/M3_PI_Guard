"""Capture a hash-bound snapshot of one local Ollama model tag."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "m3-ollama-model-snapshot-1.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _post(base_url: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _get(base_url: str, endpoint: str) -> dict[str, Any]:
    with urllib.request.urlopen(base_url.rstrip("/") + endpoint, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _manifest_path(model_root: Path, model: str) -> Path:
    if "/" in model:
        namespace, name_tag = model.rsplit("/", 1)
    else:
        namespace, name_tag = "library", model
    if ":" in name_tag:
        name, tag = name_tag.rsplit(":", 1)
    else:
        name, tag = name_tag, "latest"
    return model_root / "manifests" / "registry.ollama.ai" / namespace / name / tag


def _blob_path(model_root: Path, digest: str) -> Path:
    return model_root / "blobs" / digest.replace(":", "-", 1)


def build_snapshot(model_root: Path, model: str, base_url: str) -> dict[str, Any]:
    root = model_root.resolve(strict=True)
    manifest_path = _manifest_path(root, model)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found for {model}: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tags = _get(base_url, "/api/tags")
    tag_row = next((row for row in tags.get("models", []) if row.get("name") == model), None)
    if tag_row is None:
        raise ValueError(f"model is absent from /api/tags: {model}")
    shown = _post(base_url, "/api/show", {"model": model})

    descriptors = [manifest.get("config", {})] + list(manifest.get("layers", []))
    blob_rows: list[dict[str, Any]] = []
    for descriptor in descriptors:
        digest = str(descriptor.get("digest", ""))
        if not digest:
            continue
        path = _blob_path(root, digest)
        if not path.is_file():
            raise FileNotFoundError(f"referenced blob is missing: {path}")
        actual_hash = _sha256(path)
        expected_hash = digest.split(":", 1)[-1]
        blob_rows.append(
            {
                "digest": digest,
                "media_type": descriptor.get("mediaType"),
                "declared_size_bytes": descriptor.get("size"),
                "actual_size_bytes": path.stat().st_size,
                "sha256": actual_hash,
                "digest_matches_bytes": actual_hash == expected_hash,
            }
        )

    details = shown.get("details") or {}
    model_info = shown.get("model_info") or {}
    context_length = next(
        (value for key, value in model_info.items() if str(key).endswith(".context_length")),
        None,
    )
    all_blobs_match = all(row["digest_matches_bytes"] for row in blob_rows)
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all_blobs_match else "failed",
        "evidence_boundary": "local_model_download_snapshot_not_formal_benchmark_result",
        "model": model,
        "model_root": str(root),
        "ollama_digest": tag_row.get("digest"),
        "ollama_size_bytes": tag_row.get("size"),
        "modified_at": tag_row.get("modified_at"),
        "format": details.get("format"),
        "family": details.get("family"),
        "parameter_size": details.get("parameter_size"),
        "quantization_level": details.get("quantization_level"),
        "context_length": context_length,
        "manifest_relative_path": manifest_path.relative_to(root).as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "manifest": manifest,
        "blob_count": len(blob_rows),
        "all_blob_digests_match_bytes": all_blobs_match,
        "blobs": blob_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_snapshot(args.model_root, args.model, args.base_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "model": args.model, "output": str(args.output)}))
    return 0 if result["status"] == "passed" else 5


if __name__ == "__main__":
    raise SystemExit(main())
