"""下载并哈希冻结官方 Hugging Face PromptGuard 模型快照。

用于在本地拉取指定版本的 PromptGuard 权重，并按 8MB 分块计算所有文件的 SHA-256 哈希清单。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, snapshot_download


SCHEMA = "m3-promptguard-download-snapshot-1.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_and_snapshot(
    model_id: str,
    cache_dir: Path,
    *,
    revision: str | None = None,
) -> dict[str, Any]:
    api = HfApi()
    info = api.model_info(model_id, revision=revision, files_metadata=True)
    resolved_revision = str(info.sha)
    snapshot = Path(
        snapshot_download(
            repo_id=model_id,
            revision=resolved_revision,
            cache_dir=str(cache_dir),
        )
    ).resolve(strict=True)

    files: list[dict[str, Any]] = []
    for path in sorted((item for item in snapshot.rglob("*") if item.is_file()), key=str):
        files.append(
            {
                "relative_path": path.relative_to(snapshot).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed",
        "evidence_boundary": "real_detector_model_download_snapshot_not_formal_baseline_result",
        "model_id": model_id,
        "resolved_revision": resolved_revision,
        "cache_dir": str(cache_dir.resolve()),
        "snapshot_path": str(snapshot),
        "file_count": len(files),
        "size_bytes": sum(row["size_bytes"] for row in files),
        "files": files,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default="meta-llama/Llama-Prompt-Guard-2-86M")
    parser.add_argument("--revision")
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--record-gated-revision",
        help="Record a previously observed gated-repository blocker without another network request.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.record_gated_revision:
        result = {
            "schema": SCHEMA,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "blocked_gated_repository",
            "evidence_boundary": "model_access_blocker_not_formal_baseline_result",
            "model_id": args.model_id,
            "resolved_revision": args.record_gated_revision,
            "cache_dir": str(args.cache_dir.resolve()),
            "blocker": "Official repository requires accepted access terms and authenticated Hugging Face access.",
            "retry_performed": False,
            "file_count": 0,
            "size_bytes": 0,
            "files": [],
        }
    else:
        result = download_and_snapshot(
            args.model_id,
            args.cache_dir,
            revision=args.revision,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "model_id": result["model_id"],
                "resolved_revision": result["resolved_revision"],
                "file_count": result["file_count"],
                "size_bytes": result["size_bytes"],
                "output": str(args.output),
            }
        )
    )
    return 0 if result["status"] in {"passed", "blocked_gated_repository"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
