"""验证 M3 项目统一本地配置与环境变量安全性（在不打印敏感值的前提下进行检查）。

检查本地 .env 或配置路径是否符合规范、是否正确被 git 忽略，
并全量扫描 Git 跟踪文件以确保绝无敏感密钥明文外泄。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from m3_core.project_config import (
    is_secret_key,
    is_placeholder,
    parse_env_file,
    redacted_config,
    resolve_config_path,
    validate_project_config,
)


def _git_ignore_status(path: Path) -> dict[str, object]:
    try:
        relative = path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return {"inside_repository": False, "ignored": None, "tracked": None}

    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", relative],
        cwd=ROOT,
        check=False,
    ).returncode == 0
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    return {"inside_repository": True, "ignored": ignored, "tracked": tracked}


def tracked_secret_hits(
    values: dict[str, str], *, root: Path = ROOT
) -> list[dict[str, str]]:
    """在 Git 跟踪的文件内容中扫描配置的真实密钥明文（绝不回显密钥具体内容）。"""

    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    tracked_paths = [
        item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    ]
    secrets = {
        key: value.encode("utf-8")
        for key, value in values.items()
        if is_secret_key(key) and not is_placeholder(value) and len(value) >= 12
    }
    hits: list[dict[str, str]] = []
    for relative in tracked_paths:
        path = root / relative
        try:
            content = path.read_bytes()
        except (OSError, ValueError):
            continue
        for key, secret in secrets.items():
            if secret in content:
                hits.append({"key": key, "path": relative.replace("\\", "/")})
    return hits


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--require-promptguard-token", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = resolve_config_path(args.config)
    values = parse_env_file(path)
    errors = validate_project_config(
        values,
        require_promptguard_token=args.require_promptguard_token,
    )
    git_status = _git_ignore_status(path)
    if git_status["inside_repository"] and (
        not git_status["ignored"] or git_status["tracked"]
    ):
        errors.append("local configuration must be ignored and untracked by Git")
    secret_hits = tracked_secret_hits(values)
    if secret_hits:
        errors.append("one or more configured secret values appear in tracked files")

    result = {
        "status": "passed" if not errors else "failed",
        "config_path": str(path),
        "git_safety": git_status,
        "promptguard_token_status": (
            "placeholder" if is_placeholder(values.get("HF_TOKEN")) else "set_redacted"
        ),
        "tracked_secret_hits": secret_hits,
        "errors": errors,
        "config": redacted_config(values),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
