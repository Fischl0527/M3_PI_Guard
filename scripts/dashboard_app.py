"""M3 证据仪表盘的 Streamlit 安全启动入口脚本。

避免直接在 m3_eval 目录内部运行导致本地 statistics.py 遮蔽 Python 标准库 statistics 模块。
通过在 scripts 下作为标准包入口调用，保持清晰规范的 Python import 解析路径。
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from m3_eval.evidence_dashboard import main


if __name__ == "__main__":
    # Streamlit owns the script lifecycle. Raising ``SystemExit(0)`` after a
    # successful render leaves its front-end status widget stuck on RUNNING.
    main()
