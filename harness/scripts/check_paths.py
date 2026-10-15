"""检查本轮指定路径；不读取文件内容、不生成产物。无参数检查暂存新增/改名。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from m3_core.artifact_paths import path_issues  # noqa: E402


def main(arguments: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    paths = list(sys.argv[1:] if arguments is None else arguments)
    if not paths:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACR", "-z"],
            cwd=ROOT, capture_output=True, check=True,
        )
        paths = [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
    errors = []
    for name in paths:
        path = Path(name)
        errors.extend(path_issues(path if path.is_absolute() else ROOT / path, ROOT))
    for error in errors:
        print(error)
    print(f"路径检查：{len(paths)}项，{len(errors)}个问题")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
