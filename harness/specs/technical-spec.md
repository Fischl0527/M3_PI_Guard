# 技术规格

## Paper-v2 精简执行覆盖（2026-08-19）

- 保留 `TaskPolicyManifest`、`ActionProposal`、`GuardDecision` 和
  `ProvenanceEvent` 公共运行时接口。
- 每个新研究仅生成一个 run manifest、一个 raw JSONL、一个 analysis JSON 和
  论文图表；不建立递归证据链。
- 验证入口改为受影响模块的精确 pytest 文件/节点、provider 正式前缀 canary 和
  一次性结果检查。`harness/scripts/verify.ps1` 不再是 F-PAPER-002 的完成门。
- API 请求继续记录本地 request ID、payload hash、官方 response ID 和精确模型，
  但不对历史本地工件做重复哈希重算。

## 技术栈

- 语言：Python 3.12+（当前源码使用 PEP 701 f-string 语法和标准库
  `tomllib`；完整验证环境为 CPython 3.13.5）
- 运行环境：Windows PowerShell 和 CPython
- 模型运行时：仅允许回环地址上的本地 Ollama OpenAI 兼容端点
- 核心依赖：`openai`、`pandas`
- 可选界面：Streamlit 和 Plotly
- 测试框架：兼容 Python `unittest`/`pytest` 的测试
- 构建方式：无需编译构建；Python 导入、编译和冒烟测试构成构建门禁
- 部署目标：仅限本地授权安全靶场

## 项目结构

- `m3_core/`：智能体循环、模型客户端、批量/矩阵编排和 manifest。
- `m3_guard/`：规范化器、检测器、策略、数据流和 Guard 接口。
- `m3_attacks/`：源案例族、生成器和数据集审计。
- `m3_eval/`：指标、统计、图表和仪表盘。
- `schemas/`：AttackCase、RunLog 和 ToolCall 契约。
- `experiments/`：E0–E17 注册表、实验套件和可复现编排。
- `tests/`：单元测试与集成验证。
- `outputs/experiments/`：生成的 manifest、日志、指标、统计和图表。
- `harness/state/`, `harness/features/`, `harness/specs/`,
  `harness/workspaces/runpro/`：持久化 Harness 与完成状态。

## 架构约束

- 面向模型的提示只包含执行所需的任务和不可信内容。
- `prompt_profile` 与 `guard_mode` 是相互独立的配置轴。
- 基线和防护条件必须使用相同案例、模型、提示配置、随机种子和生成参数。
- 桩后端是确定性回归基础设施，不是模型安全效果的实验证据。
- 数据集阈值只在验证集上调整；盲测配置在执行前冻结。
- 生成输出不得替换源案例，也不得静默丢弃失败。
- 长上下文实验必须按模型实际观测到的 `prompt_tokens` 校准，不能使用空白字符计数或声明标签。每个目标单元必须落在协议容差内，工作负载必须严格递增；塌缩或截断的单元不具备语义有效性。
- 不得假设 OpenAI 兼容 Ollama 路径上的 `extra_body.options.num_ctx` 能形成有效的逐请求上下文轴。修正后的 E9/E14 使用独立命名的 Modelfile 别名（4K/8K/16K/32K）或其他经独立探测验证的机制。
- 对冻结实验的任何修正都必须使用新协议、新冻结和新输出根。旧 v3 E9/E14 作为诊断来源保持不可变，不能引用为正式上下文证据。

## 命令

```powershell
python -m unittest discover -s tests -v
python -m compileall m3_core m3_guard m3_attacks m3_eval experiments tests
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl --stats outputs/metrics/final_case_stats.json --audit outputs/metrics/final_case_audit.json
python -m experiments.run_suite --suite stub_all
python -m experiments.validate_registry
```

完整验证：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/verify.ps1
```

仍支持 Bash 包装器；从 WSL/Git Bash 调用时会自动发现 Windows Python 解释器：

```powershell
bash harness/scripts/verify.sh
```

## 数据与 API 契约

- AttackCase 必需实验字段：`sample_type`、`template_id`、`split`、`requires_tool`、`authorized_actions`、`mutation_id`。
- RunLog 必需实验字段：`prompt_profile`、`guard_mode`、`guard_modules`、`replicate_id`、`seed`、计时字段，以及可用时的令牌计数。
- Manifest 必需字段：实验/套件 ID、Git 提交、数据集哈希、模型标签、Ollama 版本、参数、预期/完成案例数、失败和状态。
- 允许的实验状态值：`pending`、`running`、`completed`、`failed`。

## 安全约束

- Ollama 端点必须解析为本地主机或回环地址。
- `send_email` 只写本地发件箱；`call_api` 返回模拟数据；`run_code` 不执行生成代码。
- 不提交真实凭据或模型 blob。
- 日志在预览和报告中对金丝雀值脱敏。

## 性能约束

- Guard 自身 p95 目标低于 10 毫秒。
- 可比成对运行中的端到端 Guard 开销目标低于 10%。
- GPU 实验在可用的 8GB 设备上顺序运行；并发实验必须显式限制规模。
- E14 上下文单元必须实质且严格地改变真实提示工作负载；只改变上下文标签或配置无效。性能报告必须同时给出观测提示令牌分布、延迟、吞吐和 GPU 显存。

## 可观测性

- 每次运行都记录数据集、模型和配置身份、逐步骤结果、解析诊断和计时。
- 注册表和 manifest 支持恢复，且绝不静默省略失败案例。
- 完成声明必须有 Harness 状态、测试输出和需求台账证据支持。
- E9/E14 完成还要求上下文语义有效性审计通过；仅有产物哈希不足以证明有效。
- 4K/8K/16K/32K Qwen 别名已通过单令牌上下文探测。随后 Context Correction V2 execution-r3 完成 E9 120/120、E14 正式 432 条和排除的预热 48 条，通过独立配对审计并原子注册；只有 execution-r3 可以支持修正后的上下文主张。
