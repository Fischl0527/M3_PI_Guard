# M3-PI Guard 实验 Harness 架构

## 目的

本仓库在同一版本库内维护两个边界清楚的区域：根目录的 M3-PI Guard 本地安全靶场/实验源码，以及 `harness/` 下的 AI 智能体 Harness 工程。Harness 记录需求、状态、决策、失败和验收；项目运行代码产生带 manifest 的实验证据，两者通过固定接口协作但不混放源码。

## 运行流程

```text
攻击样本 AttackCase JSONL
      |
      v
实验套件 / 矩阵运行器
      |
      +--> prompt_profile: standard | hardened
      +--> backend: stub | local Ollama
      +--> guard_mode/module ablation
      v
智能体运行器 --> Guard --> 本地模拟工具
      |
      v
RunLog + Manifest + 失败记录
      |
      v
指标 / 统计 / 图表 / 仪表盘
```

## 模块边界

### 2026-10-05 文档和产物边界

`docs/`只保留文档和必要说明插图；统计JSON/CSV/实验图放在`outputs/`，论文机器状态在`harness/state/paper_v2/`，七套停用公开工具包在`release/archive/blind_custodian_toolkits/`。冻结文件内容和产品公共接口不变。外围归档在仓库外的`E:\M3_PI_Guard_archive`，旧runtime路径仅作目录联接；D盘备份尚因工具拒绝待迁移。入口为`docs/项目目录指南.md`。

- `m3_attacks` 负责源案例、扩展、切分元数据和数据集完整性。
- `m3_core` 负责模型交互、提示构造、工具调用解析和运行元数据。
- `m3_guard` 负责行为决策和模块级消融；它不知道测试答案。
- `m3_eval` 负责指标定义和统计汇总；它绝不修改原始日志。
- `experiments` 负责 E0–E17 注册表、实验套件、恢复规则和完成验证。
- `outputs/experiments` 是生成证据，必须可追溯到源码和配置哈希。
- `harness/state`, `harness/features`, `harness/specs` and
  `harness/workspaces/runpro` 构成持久化项目控制平面。

## Paper-v2 正式证据路径

```text
冻结 work item + condition-specific online state
      |
      v
六条件 OnlineExecutorContext（无 evaluator 字段）
      |
      v
untrusted proposal -> Guard -> 隔离 effect backend
      |
      v
sanitized runtime events + offline outcome
      |
      v
experiment-record schema validation
      |
      v
append-only JSONL record store（全链复验 + fsync）
```

- `official_provider_executor.py` 负责单次官方推理、模型/ID/usage 收据和调用账本，
  不执行 provider tools 或外部副作用。
- `formal_condition_executors.py` 只向在线 runtime 暴露冻结 online state 与最小
  调度身份；evaluator 标签和结果字段留在离线边界。
- `formal_record_store.py` 同时保存严格 experiment record 与已脱敏的逐步事件；
  prompt/response/observation 正文只可形成摘要，重复终态、身份漂移、截断或哈希
  漂移均拒绝。
- prospective experiment-record 2.2 还必须持久化 credential-free provider
  safety receipt；它把官方推理端点、隔离 effect backend、动作参数摘要、禁用
  external connector/provider tool 的状态绑定到 record hash chain。
- `post_pilot_evidence_review.py` 在不读取凭据的情况下交叉复验 active admission、
  独立 trace 文件、record bundle、cache/cost、safety receipt 和 ledger tail。
  它只能把真实 pilot 送到单独的 owner matrix review，不能自行授权矩阵或准入
  论文结果。
- completed/refusal 的 live 记录必须是 `formal_candidate`；无完整响应身份的
  operational failure 可保留为 `diagnostic`，但必须进入 ITT，不能静默丢弃。
- 当前三个模块仅完成离线工程资格；v3 preflight 仍关闭，不能据此声称模型效果。

## 状态与恢复

- `experiments/registry.json` 是机器可读的实验状态。
- 每个套件写入不可变配置快照和可恢复 manifest。
- 只有预期运行数与已验证产物和统计一致时，套件才算完成。
- Harness 状态记录进度和失败，使后续会话无需依赖聊天记录即可恢复。

## 安全边界

- 模型仅通过回环地址上的 Ollama 在本地推理。
- 工具仅为本地模拟工具。
- 真实密钥、账号、公共端点和生成代码执行均不在范围内。
- paper-v2 允许经用户批准的 DeepSeek/Gemini 官方推理端点，但凭据仅存在于被
  Git 忽略的本地配置，输出只是不可信 proposal；工具副作用仍限合成 sandbox 或
  AgentDojo 内存副本。

## 验证层级

1. 契约与单元测试。
2. 数据集和标签审计。
3. 桩后端确定性矩阵。
4. 本地模型冒烟测试。
5. 完整实验注册表验证。
6. 需求台账和最终审计验证。
