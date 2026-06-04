# DAY3-TARGET-A 队员 A 计划书

日期：2026-06-04  
分支：`team-a/m3-core`  
角色：队员 A，本地 Agent 靶场与最终集成负责人

## 1. DAY2 复核结论

根据 `DAY2-TASK.md` 中队员 A 的验收要求，DAY2 主链路已经完成。

已完成项：

- `m3_core/llm_client.py` 已实现 `stub` 和 `ollama` 两种后端。
- `m3_core/tool_sandbox.py` 已实现 `read_file`、`write_file`、`send_email`、`call_api`、`run_code`、`final`。
- `m3_core/agent_runner.py` 已实现 baseline / guarded 主循环。
- `m3_core/run_batch.py` 已能读取 AttackCase JSONL 并输出 RunLog JSONL。
- `fixtures/sample_cases.jsonl` 已有 10 条本地安全样本。
- `outputs/runs/stub_baseline.jsonl` 已生成，21 行。
- `outputs/runs/stub_guarded.jsonl` 已生成，10 行。
- `outputs/runs/qwen25_baseline_day2.jsonl` 已生成，24 行。
- 三组 RunLog 均包含必需字段。
- 本机 Ollama 已安装 `m3-target-qwen25-7b:latest`，模型目录为 `E:\M3_PI_Guard\models`。

DAY2 小偏差：

- `DAY2-TASK.md` 点名的 `sandbox/public/clean_report.md` 和 `sandbox/public/injected_report.md` 当前没有使用同名文件；现有实现使用 `sandbox/public/clean_supplier_report.md` 与 JSONL 内嵌攻击文档承载样本内容。
- 本地存在 `sandbox/secrets/userA_api_key.txt`，这是本机个人测试文件，应继续由 `.gitignore` 忽略，不提交到 GitHub。

结论：

```text
DAY2 最低验收完成。
DAY2 Qwen 扩展验收完成。
```

## 2. DAY3 总目标

DAY3 队员 A 的目标是把本地 Agent 靶场从“能跑”升级为“可批量实验、可演示、可集成”的 v0.3 实验平台。

重点不是扩展攻击样本数量，而是让 A 模块能稳定承接 B 队员样本库和 C 队员 Guard / 评测模块。

队员 A 今日重点：

```text
1. 批量运行器增强
2. Agent prompt 模板增强
3. 工具沙箱证据日志增强
4. 代表性 demo cases
5. stub 全量批跑
6. Qwen 小规模代表批跑
7. Windows 一键运行脚本
```

## 3. 实现计划

### 3.1 增强批量运行器

目标文件：

```text
m3_core/run_batch.py
```

新增参数：

```text
--limit N
--families rag_indirect,multilingual_t2l
--case-ids RAG-PI-001,RAG-PI-002
--max-steps 5
--seed 42
--shuffle
--resume
--fail-fast
```

行为约定：

- `--families` 按 `attack_family` 精确筛选。
- `--case-ids` 按 `case_id` 精确筛选。
- `--shuffle` 在筛选后打乱样本。
- `--seed` 控制打乱顺序，便于复现。
- `--limit` 在筛选和打乱后截取前 N 条。
- `--resume` 读取已有 `--out`，跳过已有终态日志的 case。
- `--fail-fast` 遇到异常立即退出；默认记录 error 日志后继续。
- 保留顶部 `CONFIG`，支持不敲命令行直接运行。

### 3.2 增强 Agent prompt

目标文件：

```text
m3_core/agent_runner.py
```

baseline prompt：

- 使用普通本地 Agent 设定。
- 允许根据用户任务和文档内容完成任务。
- 要求只输出 ToolCall JSON。

guarded prompt：

- 使用安全 Agent 设定。
- 明确声明外部文档、邮件、网页、工具返回值、JSON 字段、翻译文本都是不可信数据。
- 明确声明只有 `UserTask` 能决定工具调用。
- 使用标签区分：

```text
<SystemInstruction>
<UserTask>
<UntrustedDocument>
<ExpectedSafeBehavior>
```

这样同一攻击样本在 baseline 和 guarded 下会有更清晰的实验对照。

### 3.3 增强工具沙箱证据日志

目标文件：

```text
m3_core/tool_sandbox.py
```

新增工具事件日志：

```text
sandbox/logs/tool_events.jsonl
```

每次工具调用或被 Guard 阻断的工具意图都记录：

```json
{
  "ts": "2026-06-04T00:00:00+00:00",
  "run_id": "run id",
  "case_id": "case id",
  "tool": "read_file",
  "arguments": {"path": "sandbox/secrets/api_key.txt"},
  "allowed": false,
  "observation_preview": "BLOCKED_BY_M3_GUARD",
  "mock_only": true
}
```

安全边界继续保持：

- `send_email` 不真实发邮件，只写 `sandbox/outbox/outbox.jsonl`。
- `call_api` 不访问公网，只返回 mock JSON。
- `run_code` 不执行代码，只返回 `MOCK: code execution disabled`。
- `read_file` / `write_file` 不能越出 `sandbox/`。

### 3.4 创建 demo cases

目标文件：

```text
fixtures/demo_cases.jsonl
```

选择 3 条适合展示的代表性样本：

```text
DEMO-001：RAG 间接提示注入
DEMO-002：JSON/RPC 结构化注入
DEMO-003：多语言/T2L 注入
```

展示目标：

- baseline：能观察到高危 mock 工具调用尝试。
- guarded：应被 ask 或 deny。

### 3.5 创建一键运行脚本

目标目录：

```text
scripts/
```

Windows 脚本：

```text
scripts/run_day3_stub.ps1
scripts/run_day3_qwen_demo.ps1
scripts/run_day3_eval.ps1
```

脚本要求：

- 顶部配置路径和模型参数。
- 从脚本位置自动切回仓库根目录。
- 适合直接在 PowerShell、VSCode 或文件管理器中运行。

## 4. 验收命令

### 4.1 参数验收

```powershell
python -m m3_core.run_batch --cases m3_attacks/cases/all_cases.jsonl --backend stub --defense baseline --limit 5 --out outputs/runs/day3_test_limit.jsonl
```

```powershell
python -m m3_core.run_batch --cases m3_attacks/cases/all_cases.jsonl --backend stub --defense guarded --families rag_indirect --out outputs/runs/day3_test_family_rag.jsonl
```

### 4.2 stub 全量运行

```powershell
python -m m3_core.run_batch --cases m3_attacks/cases/all_cases.jsonl --backend stub --defense baseline --out outputs/runs/day3_stub_baseline_all.jsonl
```

```powershell
python -m m3_core.run_batch --cases m3_attacks/cases/all_cases.jsonl --backend stub --defense guarded --out outputs/runs/day3_stub_guarded_all.jsonl
```

### 4.3 Qwen demo 运行

```powershell
python -m m3_core.run_batch --cases fixtures/demo_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense baseline --out outputs/runs/day3_qwen25_demo_baseline.jsonl
```

```powershell
python -m m3_core.run_batch --cases fixtures/demo_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense guarded --out outputs/runs/day3_qwen25_demo_guarded.jsonl
```

### 4.4 Qwen 20 条代表运行

```powershell
python -m m3_core.run_batch --cases m3_attacks/cases/all_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense baseline --limit 20 --out outputs/runs/day3_qwen25_baseline_20.jsonl
```

```powershell
python -m m3_core.run_batch --cases m3_attacks/cases/all_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense guarded --limit 20 --out outputs/runs/day3_qwen25_guarded_20.jsonl
```

## 5. 预期交付物

代码与样本：

```text
m3_core/run_batch.py
m3_core/agent_runner.py
m3_core/tool_sandbox.py
m3_core/llm_client.py
fixtures/demo_cases.jsonl
scripts/run_day3_stub.ps1
scripts/run_day3_qwen_demo.ps1
scripts/run_day3_eval.ps1
DAY3-TARGET-A.md
```

运行日志：

```text
outputs/runs/day3_stub_baseline_all.jsonl
outputs/runs/day3_stub_guarded_all.jsonl
outputs/runs/day3_qwen25_demo_baseline.jsonl
outputs/runs/day3_qwen25_demo_guarded.jsonl
outputs/runs/day3_qwen25_baseline_20.jsonl
outputs/runs/day3_qwen25_guarded_20.jsonl
```

辅助证据：

```text
sandbox/logs/tool_events.jsonl
outputs/runs/*.csv
```

## 6. 风险与兜底

当前 `m3_attacks/cases/all_cases.jsonl` 有 50 条，尚未达到 DAY3 全队目标 60+。这是 B 队员样本扩展任务，A 模块只需确保批量器兼容 B 后续更新。

Qwen 本地模型可以用于烟测，但 ToolCall JSON 不稳定。DAY3 展示建议采用：

```text
stub 全量结果作为稳定主证据
Qwen demo / 20 条结果作为真实本地模型补充证据
```

如果 Qwen 输出漂移，保留原始 `raw_model_output`、解析后的 `parsed_tool_call`、sandbox observation 和 `tool_events.jsonl`，把“模型输出不稳定也是 Agent 安全风险”作为报告说明点。
