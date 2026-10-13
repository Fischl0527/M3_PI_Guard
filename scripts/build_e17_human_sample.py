""":mod:`experiments.e17_human_sample` 的命令行 CLI 封装工具。

用于执行 E17 人工盲审双盲抽样集生成与初审记录打包。
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.e17_human_sample import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
