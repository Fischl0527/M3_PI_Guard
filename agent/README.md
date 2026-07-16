# 项目完整性审计兼容目录

本目录现在只保留 M3 PI Guard 项目的完整性审计实现和已冻结审计证据：

- `result_integrity_audit.py`：项目结果完整性审计器；
- `audits/`：被实验 manifest、报告和证据索引引用的审计结果；
- `__pycache__/`：本地 Python 缓存，可清理，不是正式证据。

它不再是 AI Agent Harness 的任务/进度目录。当前 Harness 状态统一位于 `harness/state/`，Harness 入口见 `harness/README.md`。

由于现有实验清单和报告已记录 `agent/audits/` 与 `agent/result_integrity_audit.py` 路径，本轮不移动这两类文件，以避免破坏已冻结证据、哈希和复现实验命令。后续若要改名，必须同步迁移所有 manifest、报告引用、默认参数并重新执行完整性验证。

