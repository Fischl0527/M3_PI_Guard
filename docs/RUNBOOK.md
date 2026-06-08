# Runbook

本文档说明如何在本地复现最终提交包的最小演示链路。所有命令均在项目根目录执行，运行过程只使用本地 mock 工具。

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

## 3. 样本合并与审计

```powershell
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl --stats outputs/metrics/final_case_stats.json --audit outputs/metrics/final_case_audit.json
```

验收点：

- `total_cases` 为 69。
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

## 6. Dashboard

```powershell
streamlit run m3_eval/dashboard.py
```

或使用已有脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_day5_dashboard.ps1
```

## 7. 本地模型可选演示

如果本机 Ollama 与 `m3-target-qwen25-7b` 可用，可执行：

```powershell
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense-modes baseline,full_guard --out-dir outputs/runs/day7_smoke_qwen --run-prefix day7_smoke_qwen --max-steps 5
```

本步骤为可选演示。最终可复现链路以 stub smoke test 为准。

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
