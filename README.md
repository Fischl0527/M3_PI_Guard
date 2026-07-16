# RedTeam_LLM_Security

## M3_PI_Guard Local Agent Range

M3_PI_Guard 是一个完全本地运行的 LLM Agent 工具调用靶场与防护评测框架。项目核心关注 Agent 工具调用行为链路，而不是把低能力本地模型本身作为研究贡献。

## 安全边界

- 不调用远程 API，不连接真实邮箱，不访问真实公网业务系统。
- `send_email` 只写入 `sandbox/outbox/outbox.jsonl`。
- `call_api` 只返回本地 mock JSON。
- `run_code` 永远返回 `MOCK: code execution disabled`。
- `sandbox/secrets/api_key.txt` 是本地 canary：`M3_CANARY_SECRET_API_KEY=sk-local-redteam-demo-not-real`。
- 不提交模型文件，不复制 `D:\Ollama` 内容，不使用真实 secret。

## 目录

仓库已经按用途分区：M3 项目源码保留在根目录的项目包中；AI Agent Harness 工程统一放在 `harness/`。根目录 `AGENTS.md` 只是 Agent 自动发现入口，`agent/` 只保留被实验哈希和报告引用的项目完整性审计代码/证据，不是当前 Harness 状态目录。

```text
m3_attacks/                 攻击数据与生成/审计
m3_core/
  __init__.py
  llm_client.py
  agent_runner.py
  tool_sandbox.py
  run_batch.py

m3_guard/
  __init__.py
  guard_engine.py

fixtures/
  sample_cases.jsonl
  sample_baseline_logs.jsonl
  sample_guarded_logs.jsonl

schemas/
  attack_case.schema.json
  tool_call.schema.json
  run_log.schema.json

m3_eval/
  metrics.py
  evaluate.py

experiments/                E0-E17 实验实现与注册表
protocols/                  冻结实验协议与夹具
tests/                      项目测试
scripts/                    项目运行、分析与报告脚本

harness/                    与项目源码分离的 Agent Harness 工程
  config/                   权限、策略与工作流
  state/                    当前任务、进度、失败与交接
  specs/                    产品/技术/验收规格
  features/                 功能状态台账
  tasks/                    任务模板
  docs/                     Harness 文档与决策
  scripts/                  Harness 初始化、测试、验证、清理
  workspaces/               Runpro 工作区与阶段报告

sandbox/
  public/
  secrets/
  outbox/
  logs/

outputs/runs/
outputs/metrics/
```

Harness 使用说明见 `harness/README.md`；项目目录的完整分类见 `文件夹说明.md`。

## Backend

- `backend=stub`：不调用任何模型，按样本固定返回 ToolCall，适合无 GPU 环境和稳定演示。
- `backend=ollama`：使用 OpenAI SDK 调用本机 Ollama OpenAI-compatible API。
  - 默认 `base_url`: `http://127.0.0.1:11434/v1`
  - 默认 `api_key`: `ollama`
  - 默认 `model`: `m3-target-qwen25-7b`
  - 代码会强制校验 endpoint 只能是 `localhost`、`127.0.0.1` 或 `::1`

本机已有其他 Ollama 模型时，可作为烟测模型使用，但不作为主体研究贡献。

## 验收命令

```powershell
python -m m3_core.run_batch --cases fixtures/sample_cases.jsonl --backend stub --defense baseline --out outputs/runs/stub_baseline.jsonl
```

```powershell
python -m m3_core.run_batch --cases fixtures/sample_cases.jsonl --backend stub --defense guarded --out outputs/runs/stub_guarded.jsonl
```

如果本机已安装 Ollama 和 `m3-target-qwen25-7b`：

```powershell
python -m m3_core.run_batch --cases fixtures/sample_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense guarded --out outputs/runs/qwen25_guarded.jsonl
```

本机已有 `vicuna:7b` 时可做简单烟测：

```powershell
python -m m3_core.run_batch --cases fixtures/sample_cases.jsonl --backend ollama --model vicuna:7b --defense guarded --out outputs/runs/vicuna_guarded.jsonl
```

## 日志字段

每一步输出一行 JSON，字段包括：

```text
run_id, case_id, model, backend, defense_mode, step, attack_family,
raw_model_output, parsed_tool_call, guard_decision, risk_score,
reasons, observation, final_status
```

## Guard 接口

`guarded` 模式在每次工具调用前调用：

```python
from m3_guard.guard_engine import guard_decide

decision, risk_score, reasons = guard_decide(context, tool_call)
```

当前 `m3_guard.guard_engine` 提供可替换的防御接口。后续可扩展 normalizer、detector、policy engine 和 dataflow tracker，只要保持这个接口不变。

## Day 1 评估命令

比较 stub baseline 与 guarded：

```powershell
python -m m3_eval.evaluate --cases fixtures/sample_cases.jsonl --baseline outputs/runs/stub_baseline.jsonl --guarded outputs/runs/stub_guarded.jsonl --out outputs/metrics/stub_compare_metrics.json
```

输出指标包括：

```text
ASR_attack_success_rate
UTR_unauthorized_tool_rate
DSR_data_spill_rate
BSR_block_success_rate
FPR_false_positive_rate
WRS_avg_guard_risk_score
```
