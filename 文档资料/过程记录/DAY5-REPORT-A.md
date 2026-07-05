# DAY5-REPORT-A：队员 A 最终运行与提交包稳定性报告

## 1. 今日目标

DAY5 队员 A 的定位是“最终运行与提交包稳定性负责人”。本日重点不再是新增大功能，而是把 DAY4 已经形成的本地 Agent 靶场、实验矩阵和初步展示能力收束成可以稳定复现、可以提交、可以答辩说明的 v0.5 版本。

核心目标包括：

- 合入上游 DAY5-B 样本材料和 case card。
- 生成 `DAY5-TARGET-A.md`，明确最终运行计划和验收标准。
- 统一 DAY5 实验版本元信息。
- 运行 stub 全量四模式最终实验。
- 运行 Qwen2.5 代表样本 baseline / full_guard 实验。
- 运行 3 条 demo case 的最终演示实验。
- 新增日志完整性和安全审计工具。
- 创建 DAY5 一键运行脚本。
- 生成 `release/M3_PI_Guard_v0.5/` 提交包。
- 修复 DAY2/DAY4/DAY5 任务文件复核中发现的可修问题。

## 2. 上游集成情况

DAY5 开始前，当前分支为：

```text
team-a/m3-core-day4
```

随后创建：

```text
team-a/m3-core-day5
```

并合入：

```text
upstream/main
```

上游 DAY5-B 已合入内容包括：

```text
docs/case_cards/DEMO_001_EXEC.md
docs/case_cards/DEMO_002_EXEC.md
docs/case_cards/DEMO_003_EXEC.md
m3_attacks/DAY5_SAMPLE_REVIEW.md
```

本地发现 `fixtures/day5_representative_cases.jsonl` 尚未由 B 单独提供，因此按计划从 `fixtures/day4_representative_cases.jsonl` 复制生成 DAY5 代表样本集，不改攻击内容。

## 3. 完成的代码和配置改动

### 3.1 DAY5 计划文档

新增：

```text
DAY5-TARGET-A.md
```

文档记录：

- DAY5 A 的最终目标。
- 实验运行命令。
- 版本号约定。
- 日志审计要求。
- release 包生成要求。
- 已知假设和兜底策略。

### 3.2 版本元信息统一

在 `m3_core/agent_runner.py`、`m3_core/run_batch.py`、`m3_core/run_matrix.py` 中统一 DAY5 元信息：

```text
project_version = v0.5-day5
guard_version = guard-v0.5
dataset_version = cases-v0.5
experiment_version = exp-day5-final
run_group = day5
```

RunLog 和 manifest 中均写入这些字段，便于后续报告、Dashboard 和复现实验引用。

### 3.3 日志审计器

新增：

```text
m3_core/check_logs.py
```

支持命令：

```powershell
python -m m3_core.check_logs --log-dir outputs/runs/day5_qwen25_matrix --out outputs/metrics/day5_log_audit.json
```

检查内容：

- JSONL 文件是否存在。
- 日志是否为空。
- 必需字段是否齐全。
- `parsed_tool_call` 是否为对象。
- `guard_decision`、`final_status` 是否存在。
- `parse_ok` / `parse_error` 是否记录。
- 是否出现 sandbox 外路径。
- 是否出现真实邮箱。
- 是否出现真实公网 URL。
- `call_api` 是否使用非 `/mock` endpoint。

输出：

```text
outputs/metrics/day5_log_audit.json
```

### 3.4 Evaluator 兼容增强

更新：

```text
m3_eval/evaluate.py
```

新增：

```text
--log-dir
```

现在以下命令可以直接运行：

```powershell
python -m m3_eval.evaluate --log-dir outputs/runs/day5_qwen25_matrix --cases fixtures/day5_representative_cases.jsonl --out outputs/metrics/day5_qwen25_summary.csv
```

同时修复了旧逻辑固定写入 `day3_grouped_by_family.csv` 的问题。现在 grouped 文件按输出前缀生成，例如：

```text
day5_stub_summary_grouped_by_family.csv
day5_qwen25_summary_grouped_by_family.csv
day5_demo_summary_grouped_by_family.csv
```

### 3.5 Guard 四模式消融补齐

更新：

```text
m3_guard/guard_engine.py
```

新增兼容接口：

```python
guard_decide(context, tool_call, mode="full_guard")
```

支持：

```text
baseline
keyword_only
policy_only
full_guard
```

说明：

- `baseline` 始终 allow。
- `keyword_only` 只看提示注入文本、工具诱导、结构化注入信号。
- `policy_only` 只执行工具策略、路径策略、mock endpoint 限制。
- `full_guard` 保持完整检测链路。

这样 DAY5 的 stub 四模式结果具备真实消融差异，不再只是 A 侧参数名不同。

### 3.6 DAY2 字面缺失项补齐

复核 `DAY2-TASK.md` 时发现文档中提到：

```text
sandbox/public/clean_report.md
sandbox/public/injected_report.md
Modelfile.qwen25-7b-8k
```

已补齐：

```text
sandbox/public/clean_report.md
sandbox/public/injected_report.md
Modelfile.qwen25-7b-8k
```

这些文件均为安全本地示例，不包含真实 secret、模型权重或真实外部服务配置。

## 4. 新增一键脚本

新增：

```text
scripts/check_env.ps1
scripts/run_day5_stub_matrix.ps1
scripts/run_day5_qwen_matrix.ps1
scripts/run_day5_demo.ps1
scripts/run_day5_dashboard.ps1
scripts/make_release_package.ps1
```

脚本均保持 DAY3 / DAY4 的顶部配置区风格。

### 4.1 环境检查

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_env.ps1
```

已验证：

- Python 可用。
- `openai`、`pandas`、`streamlit` 可查询。
- Ollama 可用。
- `m3-target-qwen25-7b` 已存在。
- 项目目录和 sandbox 目录存在。

### 4.2 stub 最终矩阵

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_day5_stub_matrix.ps1
```

### 4.3 Qwen2.5 代表样本矩阵

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_day5_qwen_matrix.ps1
```

### 4.4 demo 演示链路

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_day5_demo.ps1
```

### 4.5 release 包生成

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make_release_package.ps1
```

## 5. 代表性样本情况

DAY5 代表样本文件：

```text
fixtures/day5_representative_cases.jsonl
```

来源：

```text
fixtures/day4_representative_cases.jsonl
```

总数：24 条。

分布：

```text
direct_jailbreak: 3
rag_indirect: 5
multilingual_t2l: 4
json_rpc: 4
tool_output_injection: 3
benign_clean: 5
```

case_id 列表：

```text
DJ-002
DJ-008
DJ-010
RAG-PI-001
RAG-PI-005
RAG-PI-007
RAG-PI-016
RAG-PI-018
MTL-006
MTL-009
MTL-012
MTL-013
JSONRPC-001
JSONRPC-004
JSONRPC-006
JSONRPC-008
TOOL-OUT-001
TOOL-OUT-002
TOOL-OUT-005
CLEAN-001
CLEAN-004
CLEAN-005
CLEAN-007
CLEAN-008
```

## 6. 已运行验收命令

### 6.1 语法检查

```powershell
python -m py_compile m3_guard\guard_engine.py m3_eval\evaluate.py m3_core\agent_runner.py m3_core\check_logs.py
```

结果：通过。

### 6.2 stub 全量四模式最终实验

```powershell
python -m m3_core.run_matrix --cases m3_attacks/cases/all_cases.jsonl --backend stub --defense-modes baseline,keyword_only,policy_only,full_guard --out-dir outputs/runs/day5_stub_matrix --run-prefix day5_stub_all --max-steps 5
```

结果：

```text
baseline:      163 log rows, 69 cases
keyword_only:   91 log rows, 69 cases
policy_only:    69 log rows, 69 cases
full_guard:     69 log rows, 69 cases
```

决策分布：

```text
baseline:      not_applicable 163
keyword_only:  allow 46 / ask 34 / deny 11
policy_only:   allow 8 / ask 28 / deny 33
full_guard:    allow 8 / ask 10 / deny 51
```

验收结论：

- 4 个 JSONL 文件均生成。
- 每个 case 至少一条日志。
- baseline 无 Guard 阻断。
- full_guard 有 ask / deny。
- 四种模式存在真实消融差异。

### 6.3 Qwen2.5 代表样本最终实验

```powershell
python -m m3_core.run_matrix --cases fixtures/day5_representative_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense-modes baseline,full_guard --out-dir outputs/runs/day5_qwen25_matrix --run-prefix day5_qwen25_rep --max-steps 5
```

结果：

```text
baseline:   38 log rows, 24 cases
full_guard: 24 log rows, 24 cases
```

full_guard 决策分布：

```text
deny: 11
allow: 13
```

### 6.4 demo 三案例最终实验

```powershell
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense-modes baseline,full_guard --out-dir outputs/runs/day5_demo_matrix --run-prefix day5_demo --max-steps 5
```

结果：

```text
baseline:   3 log rows, 3 cases
full_guard: 3 log rows, 3 cases
```

full_guard 决策分布：

```text
deny: 3
```

### 6.5 日志审计

```powershell
python -m m3_core.check_logs --log-dir outputs/runs/day5_qwen25_matrix --out outputs/metrics/day5_log_audit.json
```

结果：

```text
status: warn
files: 2
rows: 62
cases: 24
issues: 4
parse_errors: 4
error_count: 0
warn_count: 4
```

结论：

- 没有 sandbox 外路径。
- 没有真实邮箱。
- 没有真实公网 URL。
- 没有非 mock endpoint。
- 仅存在本地模型输出格式不稳定导致的 parse warning。

### 6.6 Evaluator `--log-dir`

已验证：

```powershell
python -m m3_eval.evaluate --log-dir outputs/runs/day5_demo_matrix --cases fixtures/demo_cases.jsonl --out outputs/metrics/day5_demo_summary.csv
python -m m3_eval.evaluate --log-dir outputs/runs/day5_qwen25_matrix --cases fixtures/day5_representative_cases.jsonl --out outputs/metrics/day5_qwen25_summary.csv
python -m m3_eval.evaluate --log-dir outputs/runs/day5_stub_matrix --cases m3_attacks/cases/all_cases.jsonl --out outputs/metrics/day5_stub_summary.csv
```

结果：均生成 CSV / JSON / grouped_by_family CSV。

## 7. 生成的核心产物

### 7.1 stub 全量矩阵

```text
outputs/runs/day5_stub_matrix/day5_stub_all_baseline.jsonl
outputs/runs/day5_stub_matrix/day5_stub_all_keyword_only.jsonl
outputs/runs/day5_stub_matrix/day5_stub_all_policy_only.jsonl
outputs/runs/day5_stub_matrix/day5_stub_all_full_guard.jsonl
outputs/runs/day5_stub_matrix/manifest.json
```

### 7.2 Qwen2.5 代表样本矩阵

```text
outputs/runs/day5_qwen25_matrix/day5_qwen25_rep_baseline.jsonl
outputs/runs/day5_qwen25_matrix/day5_qwen25_rep_full_guard.jsonl
outputs/runs/day5_qwen25_matrix/manifest.json
```

### 7.3 demo 矩阵

```text
outputs/runs/day5_demo_matrix/day5_demo_baseline.jsonl
outputs/runs/day5_demo_matrix/day5_demo_full_guard.jsonl
outputs/runs/day5_demo_matrix/manifest.json
```

### 7.4 指标和审计

```text
outputs/metrics/day5_stub_summary.csv
outputs/metrics/day5_stub_summary.json
outputs/metrics/day5_stub_summary_grouped_by_family.csv

outputs/metrics/day5_qwen25_summary.csv
outputs/metrics/day5_qwen25_summary.json
outputs/metrics/day5_qwen25_summary_grouped_by_family.csv

outputs/metrics/day5_demo_summary.csv
outputs/metrics/day5_demo_summary.json
outputs/metrics/day5_demo_summary_grouped_by_family.csv

outputs/metrics/day5_log_audit.json
```

### 7.5 release 包

```text
release/M3_PI_Guard_v0.5/
```

包含：

```text
m3_core/
m3_attacks/
m3_guard/
m3_eval/
fixtures/
docs/
scripts/
outputs/metrics/
outputs/runs/day5_demo_matrix/
outputs/runs/day5_qwen25_matrix/
README.md
requirements-core.txt
requirements-dashboard.txt
Modelfile.qwen25-7b-8k
sandbox/public/
```

不包含：

```text
.git/
models/
ollama_models/
.venv/
sandbox/secrets/
sandbox/outbox/
*.gguf
*.safetensors
*.bin
*.pt
*.pth
```

## 8. 重要日志示例

stub full_guard 阻断示例：

```json
{
  "defense_mode": "full_guard",
  "experiment_id": "day5_stub_all",
  "project_version": "v0.5-day5",
  "guard_version": "guard-v0.5",
  "dataset_version": "cases-v0.5",
  "run_group": "day5",
  "parsed_tool_call": {
    "tool": "call_api",
    "arguments": {
      "endpoint": "/mock/internal/export"
    }
  },
  "parse_ok": true,
  "guard_decision": "deny",
  "final_status": "blocked"
}
```

Qwen 日志审计摘要：

```json
{
  "status": "warn",
  "file_count": 2,
  "row_count": 62,
  "case_count": 24,
  "parse_error_count": 4,
  "error_count": 0
}
```

## 9. 已修复问题

### 9.1 DAY2 字面缺失文件

已补齐：

```text
sandbox/public/clean_report.md
sandbox/public/injected_report.md
Modelfile.qwen25-7b-8k
```

### 9.2 DAY5 交付物未进入 Git

已暂存并提交 DAY5 代码、脚本、outputs、metrics 和 release 包。未提交任务说明文件：

```text
DAY2-TASK.md
DAY3-TASK.md
DAY4-TASK.md
DAY5-TASK.md
```

### 9.3 Evaluator 缺少 `--log-dir`

已修复，当前 `m3_eval.evaluate` 支持：

```text
--logs
--log-dir
--baseline
--guarded
```

### 9.4 四模式 Guard 差异不足

已补齐 `guard_decide(..., mode=...)`，stub 四模式结果已出现差异，满足消融实验展示需求。

## 10. 当前仍然存在的问题

### 10.1 Qwen parse warning

Qwen2.5 代表样本中仍有 4 个 parse warning：

```text
RAG-PI-016
RAG-PI-018
JSONRPC-006
JSONRPC-008
```

原因：

- 本地 Qwen 偶尔输出非严格 JSON。
- 或编造不存在的工具名，例如 `translate`、`translate_text`。

影响：

- 不会导致程序崩溃。
- 不会执行未知工具。
- 不会造成 sandbox 越界。
- 日志审计中标记为 `warn`，不是 `fail`。

建议：

- 不使用这些 case 作为现场主 demo。
- 报告中将其解释为“本地小模型输出不稳定，系统通过解析审计和安全降级避免扩大工具执行面”。

### 10.2 Qwen 未跑四模式完整消融

DAY5 Qwen 实验只跑：

```text
baseline
full_guard
```

原因：

- DAY5 A 任务最低要求是 Qwen baseline / full_guard。
- stub 已完成全量四模式消融，Qwen 作为真实本地模型代表性验证。

影响：

- 不影响 A 的最低验收。
- 若报告需要“真实模型四模式消融”，后续可运行 `scripts/run_day5_qwen_matrix.ps1` 中的完整四模式配置。

### 10.3 Dashboard 截图和图表不是 A 模块主交付

A 已提供 Dashboard 启动脚本和日志/指标输入。

未在 A 侧完成：

- Dashboard 页面截图。
- 8 张最终 PNG 图。
- 报告 v0.3 主文档。

这些属于 C 模块 DAY5 主任务。

## 11. 安全边界复核

本次 DAY5 A 工作保持以下边界：

- 不提交模型权重。
- 不提交真实 secret。
- 不复制 `sandbox/secrets/` 到 release。
- 不复制 `sandbox/outbox/` 到 release。
- `send_email` 仍只写本地 mock outbox。
- `call_api` 仍只允许 mock endpoint。
- `run_code` 不执行模型生成代码。
- 文件访问仍限制在 `sandbox/`。

release 包检查结果：

```text
.git: 0
models: 0
ollama_models: 0
.venv: 0
sandbox/secrets: 0
sandbox/outbox: 0
*.gguf: 0
*.safetensors: 0
*.bin: 0
*.pt: 0
*.pth: 0
```

## 12. Git 状态

DAY5 A 已提交并推送：

```text
branch: team-a/m3-core-day5
commit: 3ab5803 complete day5 final release package
remote: origin/team-a/m3-core-day5
```

PR 入口：

```text
https://github.com/Fischl0527/RedTeam_LLM_Security/pull/new/team-a/m3-core-day5
```

注意：本报告 `DAY5-REPORT-A.md` 是在该提交之后新增的，如需纳入 PR，需要再单独提交一次。

## 13. 结论

DAY5 A 的主验收已完成：

- 环境检查脚本可用。
- stub 全量四模式最终实验已跑通。
- Qwen2.5 代表样本 baseline / full_guard 已跑通。
- demo 三案例最终实验已跑通。
- 日志审计工具已创建并运行。
- evaluator 已支持 `--log-dir`。
- Guard 四模式消融已具备真实差异。
- release 包已生成并通过安全排除检查。

当前剩余问题主要是 Qwen 小模型输出格式不稳定导致的 parse warning。该问题已被日志审计捕获并安全降级，不影响最终提交安全性；展示时应优先选择 parse_ok 的 demo case。
