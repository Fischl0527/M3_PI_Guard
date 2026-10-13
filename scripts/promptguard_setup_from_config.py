"""使用本地配置下载并哈希冻结 PromptGuard 基线模型。

读取配置文件指定的缓存目录与版本号，完成模型的拉取与完整性哈希校验。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from m3_core.project_config import (
    load_project_config,
    redacted_config,
    validate_project_config,
)
from scripts.download_promptguard_model import download_and_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate local settings without contacting Hugging Face.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path, values = load_project_config(args.config, override=True)
    errors = validate_project_config(values, require_promptguard_token=True)
    if errors:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "config_path": str(config_path),
                    "errors": errors,
                    "config": redacted_config(values),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    safe_summary = {
        "status": "configuration_ready",
        "config_path": str(config_path),
        "model_id": values["PROMPTGUARD_MODEL_ID"],
        "revision": values["PROMPTGUARD_REVISION"],
        "cache_dir": values["HF_HUB_CACHE"],
        "token": "<redacted:set>",
    }
    if args.check_only:
        print(json.dumps(safe_summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    result = download_and_snapshot(
        values["PROMPTGUARD_MODEL_ID"],
        Path(values["HF_HUB_CACHE"]),
        revision=values["PROMPTGUARD_REVISION"],
    )
    if result["resolved_revision"] != values["PROMPTGUARD_REVISION"]:
        raise RuntimeError("downloaded PromptGuard revision differs from frozen config")

    output = Path(values["PROMPTGUARD_DOWNLOAD_SNAPSHOT"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
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
                "output": str(output),
                "token": "<redacted:set>",
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
