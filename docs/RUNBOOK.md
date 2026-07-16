# Runbook

本文档说明如何在本地复现最终提交包的最小演示链路，以及如何在 E0-E17 全部完成后重建正式分析和启动最终 Dashboard。所有命令均在项目根目录执行，运行过程只使用本地 mock 工具和本地 Ollama 模型。

## 0. 正式证据边界

最终结论只允许来自以下白名单：

- `experiments/registry.json` 中 E0-E17 的 18 个完成态 primary bundle（E17 指向 `E17_human_stratified_360_v1/review/`）；
- `outputs/experiments/program_manifest_final_v3.json`；
- `outputs/experiments/program_final_v3/`（只经上述 manifest 间接索引）；
- `outputs/experiments/blind_freeze_v3.json`；
- `outputs/experiments/final_analysis/`。

其中 E0 的历史指标只用于说明早期口径错误，不能当作正式模型效果；E13 是验证集阈值校准；E14 使用 corrected execution-r3；E17 是两名真人对同一 360 行冻结分层样本的独立盲审。E17 的 300 representative 行用于设计加权总体估计，40+20 targeted 行只作诊断；360/360 一致，因此无需第三人裁决。该协议不是 3,299 行全量真人普查。E1-E12、E15 的正式结论来自真实模型，Stub/smoke 仅用于回归和入口验证。

以下路径保留作审计或历史追溯，但不得进入正式分母、正式图表或最终 Dashboard 数据源：

- `outputs/experiments/program_final/` 与 `blind_freeze.json`：首次正式盲测暴露 Windows 非法工具路径后作废，目录/同名 freeze marker 已记录 invalidation；
- `outputs/experiments/program_final_v2/`：冻结前独立复核又发现路径和内部审计面问题，整根作废；
- `outputs/experiments/program_v3/`：更早的全局 sandbox 污染批次，整体作废；
- `outputs/experiments/E14_initial_cold_start_diagnostic/`：已被双路径暖机的 E14 正式批次替代；
- 其他无 `_v3` 后缀的 program manifest/root、repro 根、`smoke_probe*/`、Day4/Day5/Day7 和 Stub 历史输出：协议调试、回归或原型证据。

## 1. 环境准备

推荐 Python 3.10 或更新版本。若使用 Conda，可执行：

```powershell
conda create -n redteam_env python=3.10
conda activate redteam_env
pip install -r requirements-core.txt
```

Dashboard 依赖为可选项：

```powershell
pip install -r requirements-dashboard.txt
```

## 2. Release 包 Smoke Test

从 release 包根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_day7_smoke_test.ps1
```

预期输出：

```text
outputs/runs/day7_smoke_stub/
outputs/metrics/day7_smoke_summary.csv
outputs/quality/day7_smoke_test_result.md
```

该脚本使用确定性的 `stub` 后端，在 `fixtures/demo_cases.jsonl` 上验证 baseline 与 `full_guard` 两条路径。

## 3. Canonical 数据集审计

```powershell
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl --stats outputs/metrics/final_case_stats.json --audit outputs/metrics/final_case_audit.json
```

验收点：

- `total_cases` 为 300。
- `duplicate_case_id` 为 0。
- `missing_required_fields` 为 0。
- `audit_hard_fail_count` 为 0。

## 4. Stub 演示运行

```powershell
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend stub --defense-modes baseline,full_guard --out-dir outputs/runs/day7_smoke_stub --run-prefix day7_smoke --max-steps 5
```

## 5. 指标评估

```powershell
python -m m3_eval.evaluate --log-dir outputs/runs/day7_smoke_stub --cases fixtures/demo_cases.jsonl --out outputs/metrics/day7_smoke_summary.csv
```

## 6. 正式分析与 Dashboard

只有当实验注册表中的 E0-E17 全部为 `completed`、E11 execution-r2 与 sampled E17 门禁均通过后，才生成最终综合分析。E11 revision 1 已归档且不得复用；E11 补充必须在首次生成 E18 前完成 dry-run/apply。当前完成态仓库不应再次执行 `--apply`，因为 E18 已存在。

```powershell
python scripts/freeze_e11_amendment_r2.py --check
python scripts/build_final_analysis_sampled_e17.py --validate-only
```

需要重建正式综合包时运行：

```powershell
python scripts/build_final_analysis_sampled_e17.py --force
python scripts/validate_final_statistics.py --analysis-dir outputs/experiments/final_analysis --out outputs/experiments/final_analysis/statistical_validation.json
```

最终结果完整性审计必须显式传入 v3 manifest 和 v3 freeze，不能依赖旧默认路径：

```powershell
python agent/result_integrity_audit.py --program-manifest outputs/experiments/program_manifest_final_v3.json --freeze outputs/experiments/blind_freeze_v3.json --thresholds outputs/experiments/E13/frozen_thresholds.json
```

先执行只读证据门禁，不启动服务：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_final_dashboard.ps1 -ValidateOnly
```

门禁通过后启动最终 Dashboard：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_final_dashboard.ps1
```

该脚本没有任意日志或 bundle 的透传参数，只加载注册表映射的 18 个完成态 primary bundle、`program_manifest_final_v3.json` 和 `final_analysis/`。E17 会解析到 sampled review 目录；E11 amendment 原始目录被固定白名单和哈希门禁复验，但不作为第二个 `experiment_id=E11` bundle 传入。第 13 张 `cross_tool_chain_patterns` 图把原始 v3 与 post-hoc（`pre_registered=false`）放在独立面板和独立分母。脚本拒绝旧无后缀根、v2/repro 根、旧 E9/E14 和 `_invalid`。最终 Streamlit 包装器加载非冻结的 `m3_eval/evidence_dashboard.py`；`m3_eval/dashboard.py` 仅作冻结 provenance 快照。

自包含 HTML 技术报告位于：

```text
outputs/experiments/final_analysis/report/report.html
```

其标准构建器 validation/package/structural verification 均通过；共享 portable reader 在 Windows 竖向滚动条下有 8px 顶栏横向溢出，浏览器 QA 限制记录在同目录 `verification.json`。本项目没有修改插件运行时。

以下旧入口仅用于查看早期原型，不得用于最终答辩结论：

```powershell
streamlit run m3_eval/dashboard.py
```

或使用已有历史脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_day5_dashboard.ps1
```

## 7. 本地模型可选演示

如果本机 Ollama 与 `m3-target-qwen25-7b` 可用，可执行：

```powershell
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense-modes baseline,full_guard --out-dir outputs/runs/day7_smoke_qwen --run-prefix day7_smoke_qwen --max-steps 5
```

本步骤为可选演示。Stub smoke test 只证明代码路径可复现；正式安全效果以完成态 E0-E17 bundle 和最终分析为准。

## 8. 安全边界

运行过程中出现的高风险目标均为本地 mock：

- `sandbox/secrets/api_key.txt`
- `redteam@example.test`
- `sandbox/public/notes.txt`
- `/mock/external/submit`
- `run_code:mock_only`

工具限制：

- 不发送真实邮件。
- 不访问真实公网业务 API。
- 不执行模型生成代码。
- release 包排除本地模型文件、sandbox secret、runtime outbox 和过程性任务文本。
