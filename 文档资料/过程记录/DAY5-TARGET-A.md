# DAY5-TARGET-A：队员 A 最终运行与提交包稳定性计划

## Summary

- 从 `team-a/m3-core-day4` 创建 `team-a/m3-core-day5`，合并 `upstream/main` 的 DAY5-B 内容，保留 A 的 DAY4 `run_matrix` 能力。
- DAY5 A 聚焦最终运行、稳定性检查、一键脚本和 release 包，不再大改 Agent 架构。
- 当前确认：`DAY5-TASK.md` 为 GBK 编码；`upstream/main` 已有 DAY5-B case card 和样本审查说明；`fixtures/day5_representative_cases.jsonl` 尚不存在，使用 DAY4 代表样本兜底生成。

## Key Changes

- 统一 DAY5 元信息：
  - `project_version = v0.5-day5`
  - `guard_version = guard-v0.5`
  - `dataset_version = cases-v0.5`
  - `experiment_version = exp-day5-final`
  - `run_group = day5`
- 增强 `m3_core/run_matrix.py`：manifest 和 RunLog 通过 `run_batch` 写入 DAY5 版本字段，同时保留 DAY4/DAY3 命令兼容。
- 新增 `m3_core/check_logs.py`：检查日志完整性、parse error、sandbox 越界、真实 URL/邮箱、非 mock endpoint，并输出 `outputs/metrics/day5_log_audit.json`。
- 新增 DAY5 一键脚本：
  - `scripts/check_env.ps1`
  - `scripts/run_day5_stub_matrix.ps1`
  - `scripts/run_day5_qwen_matrix.ps1`
  - `scripts/run_day5_demo.ps1`
  - `scripts/run_day5_dashboard.ps1`
  - `scripts/make_release_package.ps1`
- 生成 `release/M3_PI_Guard_v0.5/`，包含代码、fixtures、docs、scripts、metrics、figures 和少量 DAY5 demo/Qwen 日志，不包含模型、真实 secret、outbox、虚拟环境或 `.git/`。

## Final Runs

stub 全量四模式：

```powershell
python -m m3_core.run_matrix --cases m3_attacks/cases/all_cases.jsonl --backend stub --defense-modes baseline,keyword_only,policy_only,full_guard --out-dir outputs/runs/day5_stub_matrix --run-prefix day5_stub_all --max-steps 5
```

Qwen2.5 代表样本最低验收：

```powershell
python -m m3_core.run_matrix --cases fixtures/day5_representative_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense-modes baseline,full_guard --out-dir outputs/runs/day5_qwen25_matrix --run-prefix day5_qwen25_rep --max-steps 5
```

demo 三案例：

```powershell
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense-modes baseline,full_guard --out-dir outputs/runs/day5_demo_matrix --run-prefix day5_demo --max-steps 5
```

日志审计：

```powershell
python -m m3_core.check_logs --log-dir outputs/runs/day5_qwen25_matrix --out outputs/metrics/day5_log_audit.json
```

## Test Plan

- 环境检查：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_env.ps1`
- 语法检查：`python -m py_compile m3_core/run_matrix.py m3_core/run_batch.py m3_core/agent_runner.py m3_core/check_logs.py`
- stub 验收：生成 4 个 JSONL、4 个 CSV、1 个 manifest；baseline 无 Guard 阻断，full_guard 有 ask/deny。
- Qwen 验收：baseline/full_guard 至少覆盖 15 条代表样本，优先 24 条。
- demo 验收：覆盖 `fixtures/demo_cases.jsonl` 全部 case。
- 日志审计验收：`day5_log_audit.json` 生成，无 sandbox 外路径、真实公网 URL、真实邮箱、非 mock endpoint。
- release 验收：`release/M3_PI_Guard_v0.5/` 存在，且不包含 `models/`、`.git/`、`.venv/`、`sandbox/secrets/`、`sandbox/outbox/`。

## Assumptions

- `m3-origin` 旧远端不可用，DAY5 只使用 `origin` 和 `upstream`。
- 若 B 后续补交 `fixtures/day5_representative_cases.jsonl`，以 B 版本为准；当前先用 DAY4 24 条代表样本兜底。
- 当前 `m3_eval.evaluate` 不支持 `--log-dir`，A 的脚本会使用兼容的 `--logs` 精确文件方式；等 C 合入新 evaluator 后可切换。
- 不提交 `DAY2-TASK.md`、`DAY3-TASK.md`、`DAY4-TASK.md`、`DAY5-TASK.md`，除非后续明确要求。
