# Runbook

本文档说明如何在本地复现最小演示链路。所有命令均在项目根目录执行。

## 1. 环境准备

```powershell
conda create -n redteam_env python=3.9
conda activate redteam_env
pip install -r requirements-core.txt
pip install -r requirements-dashboard.txt
```

## 2. 样本合并与审计

```powershell
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl --stats outputs/metrics/final_case_stats.json --audit outputs/metrics/final_case_audit.json
```

验收点：

- `total_cases` 为 69。
- `duplicate_case_id` 为 0。
- `missing_required_fields` 为 0。
- `audit_hard_fail_count` 为 0。

## 3. Stub 演示运行

```powershell
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend stub --defense-modes baseline,full_guard --out-dir outputs/runs/day7_smoke_stub --run-prefix day7_smoke --max-steps 5
```

## 4. 指标评估

```powershell
python -m m3_eval.evaluate --log-dir outputs/runs/day7_smoke_stub --cases fixtures/demo_cases.jsonl --out outputs/metrics/day7_smoke_summary.csv
```

## 5. Dashboard

```powershell
streamlit run m3_eval/dashboard.py
```

## 6. 安全边界

运行过程中出现的高风险目标均为本地 mock：

- `sandbox/secrets/api_key.txt`
- `redteam@example.test`
- `sandbox/public/notes.txt`
- `/mock/external/submit`
- `run_code:mock_only`

这些目标不对应真实系统、真实邮箱、真实 API 或真实恶意代码。
