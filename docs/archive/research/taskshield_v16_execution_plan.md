# Task Shield v1.6 详细推进计划

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: plan
- Origin Date: 2026-07-22
- Verification Status: UNVERIFIED
- Version Label: `taskshield_v16_execution_plan_v1`
- Authorization Status: `approved_to_enter_v16_under_staged_gates`
- Evidence Class: engineering plan, not effect evidence
- Formal Result Eligibility: false
- Q2 Score Change: 0

## 1. 执行摘要

v1.6 不再继续修补 v1.5 文件，而是从新的代码、freeze、输出根和分析根开始。
它要同时解决两个彼此独立的问题：

1. 项目级 AgentDojo 指标桥把官方攻击成功语义取了补集；
2. Task Shield reproduction 的 timeout、重试、schema 恢复、trace 和延迟契约
   未达到正式基线要求。

推进顺序固定为：

```mermaid
flowchart LR
  P0["P0 指标语义纠偏\n0 模型调用"] --> G0{"G0 逐行一致且旧哈希不变"}
  G0 -->|通过| P1["P1 v1.6 新实现\n0 模型调用"]
  G0 -->|失败| S0["停止并修正审计假设"]
  P1 --> P2["P2 确定性测试\n0 模型调用"]
  P2 --> G1{"G1 合约与历史回归通过"}
  G1 -->|通过| P3["P3 4 案例失效复现预检"]
  G1 -->|失败| S1["停止，不启动 Ollama"]
  P3 --> G2{"G2 4/4 且零运行失败"}
  G2 -->|通过| P4["P4 fresh 12 案例资格"]
  G2 -->|失败| S2["封存失败根，修订版本号"]
  P4 --> G3{"G3 安全、效用、延迟联合门禁"}
  G3 -->|通过| P5["P5 30 案例配对试点"]
  G3 -->|失败| ALT["转向 Progent/CaMeL 主线"]
  P5 --> G4{"G4 可扩展且无退化安全"}
  G4 -->|通过且另行授权| P6["P6 726 案例正式运行"]
  G4 -->|失败| ALT
```

当前环境已经完成前置封场；本计划生成时 Ollama 停止、`11434` 未监听，
没有项目模型任务在运行。本轮没有执行任何实验。下一实际动作是 P0，而
不是启动模型。

## 2. v1.5 证据驱动的设计输入

### 2.1 必须修复的 P0 正确性问题

固定 AgentDojo attack checker 的 `security=true` 表示定向注入目标已经执行，
即 Targeted ASR 成功。旧项目适配层写成 `attack_success = not security`，导致：

- Task Shield v1.5 旧派生值 6/6，raw official trace 实际为 0/6；
- ToolFilter 旧派生值 622/629，raw official trace 实际为 7/629；
- 复用该适配器或复制该逻辑的其他基线也可能受影响。

在修复前，所有受影响的 effect table、图和 Q2 admission 判断均视为
provisional。raw trace 和旧文件保持原样，不能通过改历史文件来“修正”。

### 2.2 必须修复的 v1.6 运行时问题

- `APITimeoutError` 未被 untrusted fail-closed 分支捕获；
- OpenAI SDK 默认两次重试与运行时两次手工重试叠乘；
- 失败 outcome 在 trace snapshot 前写出，导致失败行缺 trace；
- schema recovery 只覆盖 JSON array 解析，没有覆盖 row type、score range 和
  cardinality；
- v1.5 共观察到 10 次 scoring cardinality fail-closed，合法工具动作被误拒；
- verifier 占已完成 case 总耗时约 73.1%，单 case 最大 1619.39 秒；
- 0/6 raw ASR 与 0/6 attack-condition utility 同时出现，属于可能的退化安全。

### 2.3 不作为修复目标的内容

v1.6 correctness-only 不通过更换方法来改善点估计。以下内容必须留到单独
版本或消融：

- 更换 verifier 模型；
- 用 PromptGuard、关键词或 M3 policy 代替 Task Shield verifier；
- 跨 case 缓存、批量合并 verifier 请求；
- 修改 Task Shield 核心 scoring 定义；
- 因 Qwen3 8B 基础工具能力不足而定制答案或任务提示。

## 3. 总体目标、假设和非目标

### 3.1 Objective

在不修改历史证据、不选择性重跑、不排除失败行的前提下，建立一个指标语义
正确、失败证据完整、重试有唯一所有者、schema 可恢复且成本受控的 Task
Shield disclosed reproduction；随后用分层门禁判断它是否值得进入 726-case
正式比较。

### 3.2 可证伪假设

- H1 Metric Correctness：所有 attack case 的新 `attack_success` 与 raw
  official injection checker 逐行 100% 一致。
- H2 Reliability：已知 invalid JSON、wrong cardinality 和 transport timeout
  均产生契约内 terminal outcome，且 success/failure 都保存完整 trace。
- H3 Utility：fresh 12-case 的无攻击 utility 至少 2/6，且没有合法动作因
  parser/schema/cardinality failure 被拒绝。
- H4 Cost：12-case case latency p95 不超过 matched same-model comparator 的
  5 倍，任何 case 不超过 600 秒硬上限。
- H5 Non-degenerate Security：安全结果不能仅由任务整体失败或全拒绝获得；
  必须联合报告 ASR、matched TCR、attack-condition utility 和合法动作误拒。

### 3.3 非目标

- v1.6 qualification 不用于论文主效应结论；
- 不把 4、12、30 案例称为独立 blind；
- 不在本机直接启动完整 726-case；
- 不自动提高 Q2 readiness；
- 不声称 Task Shield 是官方源码复现，只称 disclosed paper reproduction；
- 不制作 PPT、DOCX 或 ZIP。

## 4. 变更边界与路径

### 4.1 只读历史边界

以下历史族只读：

- `protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v13.*`
- `protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v14.*`
- `protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v15.*`
- `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13/`
- `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v14/`
- `outputs/paper_upgrade_v1/baselines/taskshield_paper_qualification_v15_expanded/`
- v1.3/v1.4/v1.5 对应 runtime、runner、analyzer 和 seal 文件。

### 4.2 计划新增的活跃源码

- `experiments/paper_v1/benchmarks/agentdojo_official_metrics_v2.py`
- `experiments/paper_v1/benchmarks/audit_agentdojo_metric_semantics.py`
- `experiments/paper_v1/benchmarks/reanalyze_agentdojo_metrics_v2.py`
- `experiments/paper_v1/benchmarks/taskshield_paper_runtime_v16.py`
- `experiments/paper_v1/benchmarks/run_taskshield_paper_formal_v16.py`
- `experiments/paper_v1/benchmarks/build_taskshield_paper_formal_freeze_v16.py`
- `experiments/paper_v1/benchmarks/analyze_taskshield_v16_qualification.py`
- `schemas/paper_v1/agentdojo_official_outcome_v2.schema.json`
- 对应的 `tests/unit/test_agentdojo_metric_semantics_v2.py`、
  `tests/unit/test_taskshield_v16_runtime.py` 和
  `tests/unit/test_taskshield_v16_qualification.py`。

如果实施中发现更合理的现有公共 helper，应复用 helper，但不得修改被旧
freeze 的 `local_adapter.files` 哈希绑定文件。

### 4.3 新输出根

- P0：`outputs/paper_upgrade_v1/analysis_v2/agentdojo_metric_semantics/`
- P3：`outputs/paper_upgrade_v1/baselines/taskshield_v16_preflight_4case/`
- P4：`outputs/paper_upgrade_v1/baselines/taskshield_v16_qualification_12case/`
- P5：`outputs/paper_upgrade_v1/baselines/taskshield_v16_pilot_30case/`
- P6：`outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v16/`

每个阶段都必须是 fresh root。失败后封存原根并提升 revision，不允许在原根
删除失败行或只补跑失败项。

## 5. P0：AgentDojo 指标语义纠偏

### 5.1 数据契约

新 outcome schema 使用无歧义字段：

- `sample_type`: `utility` 或 `attack`；
- `official_injection_success`: 直接读取 AgentDojo injection checker；
- `attack_success`: 对 attack case 等于 `official_injection_success`；
- `security_preserved`: 对 attack case 等于
  `not official_injection_success`；
- `utility_success`: 直接读取 utility checker；
- `metric_source`: raw official trace 的相对路径与 SHA-256；
- `legacy_attack_success`: 只在 correction report 中保留用于差异审计；
- `metric_semantics_version`: 固定为 `agentdojo_official_v2`。

旧 `security_success` 不进入新统计，因为它在不同上下文中含义歧义。utility
case 的默认 security 值不得进入攻击分母。

### 5.2 实施步骤

1. 从 pinned AgentDojo 源码和分析 notebook 提取语义证据位置；
2. 枚举所有复用 shared `_execute_case()` 或复制 complement 逻辑的 runner；
3. 从 raw official trace 重建 ToolFilter 629 个 attack case；
4. 从 raw official trace 重建 Task Shield v1.5 六个 attack case；
5. 生成逐行 legacy/new/delta 表、缺失 trace 表和哈希 manifest；
6. 生成新的 analysis-v2，不覆盖任何旧 analysis、figure 或 registry；
7. 对 IPIGuard、CaMeL、Progent、Transformers detector 建立 impact inventory；
8. 以 plan-only 模式刷新 Q2 审计，确认 correction 尚未自动晋级。

### 5.3 Gate G0

必须同时满足：

- attack case 新字段与 raw checker 100% 一致；
- utility case 攻击分母计数为 0；
- ToolFilter raw Targeted ASR 重建为 7/629，或所有差异逐案解释；
- Task Shield v1.5 raw Targeted ASR 重建为 0/6；
- raw trace 缺失为 0；若存在缺失，保持 blocker 而非推断；
- complement fixture、分母 fixture 和 missing-trace fixture 测试通过；
- v1.3/v1.4/v1.5 抽样哈希和完整历史证据验证不变；
- 不写 formal registry，不增加 Q2 分数。

G0 失败时停止，先修正语义审计，不进入 Task Shield runtime。

## 6. P1：v1.6 correctness-only runtime

### 6.1 唯一重试所有者

- 构造 OpenAI-compatible client 时显式 `max_retries=0`；
- v1.6 runtime 管理恰好最多 2 次 logical attempt；
- attempt 之间固定 1 秒 backoff；
- verifier read timeout 初值 120 秒；
- 每次 attempt 记录开始、结束、耗时、异常类型和是否收到 raw response；
- 不在 HTTP client、runner 和 case scheduler 形成多层重试。

### 6.2 精确 timeout 语义

- 只捕获 freeze 枚举的 transport timeout 类型；
- `assistant`、`tool_call_arguments`、`tool_output` 属于 untrusted source：两次
  timeout 耗尽后写 `DENY/SUPPRESS` fail-closed row，case 可以继续安全收束；
- trusted user/task 初始化 timeout：case 作为 operational failure 结束；
- programming error、schema bug、identity drift 不得伪装成 timeout；
- case 级硬上限 600 秒，超时写 terminal failed outcome，不自动重跑。

### 6.3 完整 schema recovery

一个 logical attempt 的验证范围必须包括：

1. raw response 存在；
2. 顶层 JSON 是 array；
3. extraction item 是非空字符串；
4. scoring row 是 object；
5. `score` 可解析且位于 `[0,1]`；
6. scoring row 数严格等于 trusted task 数；
7. 不允许静默截断、多补零或丢弃多余行。

第一次失败后，第二次请求附带 expected schema 和 expected cardinality。两次
失败后按 source trust 进入明确的 fail-closed 分支。每个 attempt 都保留
raw output、错误码、expected/observed count 和最终决定。

### 6.4 trace 和 progress 完整性

- case 开始即创建 trace handle；
- success 与 exception 分支都先 snapshot trace，再写 terminal outcome；
- `progress.jsonl` 分开保存 `started_at`、`finished_at`、`duration_ms`；
- terminal row 必须含 `case_id`、`condition_id`、`status`、`failure_class`、
  `trace_path`、`trace_sha256` 和 metric semantics version；
- 每条 verifier request 保存 logical attempt 和 SDK retry policy；
- trace 写出失败本身是 admission blocker，不能只写一条无 trace failure row。

### 6.5 运行器完整性

- 默认 `--no-resume`；
- fresh root 非空时拒绝启动；
- runner 先验证 freeze、自身代码哈希、dataset universe、model digest；
- 正式运行禁止 `--retry-failed`、失败排除或 case selection mutation；
- 运行中断后只能由 manifest 证明同一身份时全量 resume，不能只重跑失败行；
- qualification 与 formal 使用不同 freeze 和 root，互不晋级。

## 7. P2：零模型确定性测试

至少覆盖以下 18 项：

1. attack `security=true` 映射为 `attack_success=true`；
2. attack `security=false` 映射为 `security_preserved=true`；
3. utility case 不进入攻击分母；
4. legacy complement 被 audit 检出；
5. missing raw trace 被阻断；
6. assistant timeout 两次后 suppress；
7. tool-output timeout 两次后 suppress；
8. trusted-user timeout 产生 operational failure；
9. SDK `max_retries=0`；
10. invalid JSON 第一次失败、第二次恢复；
11. wrong cardinality 第一次失败、第二次恢复；
12. wrong cardinality 两次失败后 fail-closed；
13. score 非数值或越界被拒绝；
14. failed case 仍保存完整 trace；
15. started/finished/duration 字段一致；
16. case 硬上限保留 terminal failure；
17. 非空 fresh root 被拒绝；
18. 无 case retry、无 failed-row exclusion、无 registry mutation。

### Gate G1

- 全部新测试通过；
- 现有 Task Shield、AgentDojo、Q2、layout 回归通过；
- Ruff、compile、JSON schema、registry validator 通过；
- historical evidence validator 通过；
- v1.3–v1.5 hash-bound 文件零漂移；
- Ollama 在整个 P0–P2 期间保持停止。

## 8. P3：4 案例失效模式预检

### 8.1 固定选择

- `banking:user_task_6` utility；
- `banking:user_task_6` matched security；
- `slack:user_task_18` utility；
- `slack:user_task_18` matched security。

这四条只用于回归 v1.5 已知 invalid JSON、cardinality、timeout 和多步工具链
失效，不用于估计总体效果。

### 8.2 运行前检查

- G0、G1 全绿并生成机器可读 gate artifact；
- 独占 Ollama/GPU，端口只由本次 runner 使用；
- 模型别名和 digest 与 freeze 一致；
- root 不存在或为空；
- `max_retries=0`、logical attempts=2、read timeout=120s、case cap=600s；
- stderr、环境快照和 GPU/内存基线开启；
- 禁止 resume、case retry 和 registry write。

### Gate G2

- 4/4 terminal outcomes；
- 0 operational failure、0 missing；
- success/failure 路径均有 trace，trace hash 可验证；
- timeout/contract attempt 数与 freeze 一致；
- official metric 与新字段逐行一致；
- 没有合法动作因 schema/cardinality error 被拒；
- 每条 case `duration_s <= 600`；
- 没有自动 case retry。

任一失败都封存整个 P3 根，记录 stderr 和环境，提升 runtime/freeze revision，
不得只重跑失败项。

## 9. P4：fresh 12 案例资格实验

### 9.1 范围

复用 v1.5 的六个 utility 与六个 matched security 作为已知回归集。因为样本
参与过修复选择，它们只能是 qualification，不能作为确认性 blind 或论文
主表。

### 9.2 联合指标

- raw Targeted ASR；
- utility TCR；
- attack-condition utility；
- operational failure、timeout、schema recovery；
- 合法工具误拒率；
- verifier request count；
- case latency p50/p95/max；
- verifier time share；
- matched same-model comparator latency ratio。

### Gate G3

- 12/12 completed，0 failed，0 missing；
- utility `>= 2/6`；
- attack-condition utility 单独报告；
- 0 个合法工具动作因 parser/schema/cardinality error 被拒；
- Targeted ASR 与 raw trace 100% 一致；
- case latency p95 不超过 matched comparator 5 倍；
- max case 不超过 600 秒；
- 不能以全拒绝或任务失败换取低 ASR；
- qualification 仍标记 `result_eligible_for_formal_tables=false`；
- Q2 score change 保持 0。

如果 utility 仍低于 2/6、合法误拒未消失或延迟未过门禁，停止 Task Shield
formal 路线，把 v1.3–v1.6 作为公开 negative engineering evidence，并把强
基线资源转给 Progent/CaMeL。

## 10. P5：30 案例配对试点

### 10.1 冻结设计

在查看 P5 结果前冻结 15 个 utility 及其 matched security，覆盖 banking、
slack、travel、workspace，包含单步/多步、不同 trusted-task 数和历史高延迟
类型。选择规则、case ID、suite 分层和排除规则写入独立 freeze。

### 10.2 Gate G4

- 30/30，0 operational failure；
- utility 相比 same-model comparator 下降不超过 1/15；
- 无合法工具 schema 误拒；
- 报告 raw count、Wilson CI、paired difference、McNemar 和 latency 分布；
- 按实际吞吐给出 726-case wall-time、GPU hour 和失败预算；
- 不存在“低 utility 导致低 ASR”的退化优势；
- 预计本机超过 24 小时则 P6 强制迁移到服务器。

P5 启动前写一份 post-G3 checkpoint；如果 P5 需要改变方法，创建 v1.7，不
在 v1.6 pilot 中途修改。

## 11. P6：726 案例正式运行

P6 不属于本次授权，必须在 G0–G4 全部通过后由用户再次明确批准。

### 11.1 正式执行要求

- 服务器或独占 GPU；
- fresh root 与正式 freeze；
- 完整 97 utility + 629 security；
- 失败和超时保留原分母；
- 不进行 failed-only retry；
- 中断恢复必须是身份一致的 manifest resume；
- exact coverage、zero unexplained failure、完整 trace 和 analyzer hash 才能
  申请 admission；
- admission 必须显式写入且通过双 registry/audit，一律不自动晋级。

### 11.2 正式统计

- 比例：原始计数、百分比、Wilson 95% CI；
- 配对二元指标：McNemar；
- case/task 聚类 bootstrap：10,000 次；
- latency：median、p95、ECDF、Wilcoxon 与效应量；
- 多 suite/基线：Holm 校正；
- 同时报告 effect size、CI 和资源成本，不以单一 p 值判断。

### 11.3 正式图表

- Task Shield 与 comparator 的安全—可用性 Pareto 图；
- suite × condition ASR/TCR 热力图；
- case latency ECDF 与箱线图；
- timeout/schema/合法误拒/模型能力失败堆叠条形图；
- verifier 请求数和耗时占比图；
- 组件或恢复路径差异使用带 CI 的森林图。

核心效果不用饼图。所有图由 frozen manifest 一条命令重建。

## 12. 失败分类与恢复协议

### 12.1 failure_class

- `metric_semantics_mismatch`
- `identity_or_hash_drift`
- `transport_timeout_trusted`
- `transport_timeout_untrusted_suppressed`
- `contract_invalid_json`
- `contract_wrong_type`
- `contract_wrong_cardinality`
- `contract_invalid_score`
- `case_hard_timeout`
- `trace_persistence_failure`
- `model_tool_use_failure`
- `environment_resource_failure`
- `unknown_unexplained`

### 12.2 恢复规则

1. 先停止当前 root，不删除任何行；
2. 保存 stderr、环境、进程、端口、GPU、freeze 和文件 inventory；
3. 把失败留在原分母并封存 root；
4. 建立根因假设和确定性 fixture；
5. 修改代码必须提升 runtime/freeze/output revision；
6. 重新运行完整受影响批次，不补一个有利结果；
7. `unknown_unexplained` 永远阻断 formal admission。

## 13. 资源与时间预算

| 阶段 | 模型案例 | 主要资源 | 预计上限/性质 |
| --- | ---: | --- | --- |
| P0 | 0 | CPU/磁盘读取 | 现有 raw trace 重建 |
| P1–P2 | 0 | CPU | 实现和确定性测试 |
| P3 | 4 | 本机 8GB GPU | 每 case 600 秒硬上限 |
| P4 | 12 | 本机或服务器 | 最多约 2 小时硬上限加启动开销 |
| P5 | 30 | 优先服务器 | 用于实测正式成本 |
| P6 | 726 | 服务器/独占 GPU | 仅另行授权后 |

机器级依赖允许使用绝对路径：Ollama 程序位于 `D:\Ollama\app`，模型库由
本机 `OLLAMA_MODELS` 配置指向 E 盘。仓库文件、命令和 artifact 引用均使用
相对路径。

## 14. 分阶段计划命令

以下命令是执行规格，不代表本计划生成时已经运行：

```powershell
# P0：只读语义审计与 v2 重分析
python -m experiments.paper_v1.benchmarks.audit_agentdojo_metric_semantics
python -m experiments.paper_v1.benchmarks.reanalyze_agentdojo_metrics_v2

# P1/P2：零模型实现验证
python -m pytest -q tests/unit/test_agentdojo_metric_semantics_v2.py
python -m pytest -q tests/unit/test_taskshield_v16_runtime.py
python -m pytest -q tests/unit/test_taskshield_v16_qualification.py
python scripts/verify_historical_evidence.py

# P3/P4/P5 的实际参数由各自 freeze 生成，必须 fresh root、--no-resume。
# P6 在单独授权前不生成可直接误触发的正式运行命令。
```

## 15. 验证矩阵

| 层级 | 检查 | 通过标准 |
| --- | --- | --- |
| 语义 | raw trace ↔ v2 metrics | 逐行 100% |
| 分母 | utility/attack 隔离 | 0 个误入 |
| 合约 | JSON/type/range/cardinality | fixture 全通过 |
| 超时 | SDK/runtime retry | 唯一 owner，次数可审计 |
| 证据 | success/failure trace | 100% terminal rows 有 trace |
| 身份 | freeze/code/dataset/model | hash 全匹配 |
| 可靠性 | operational failure | P3/P4/P5 均为 0 |
| 效用 | P4 utility | 至少 2/6 |
| 误拒 | 合法动作 schema 误拒 | 0 |
| 延迟 | P4 p95/max | ≤5× comparator / ≤600s |
| 统计 | count/CI/paired tests | manifest 一键重建 |
| 历史 | v1.3–v1.5 | hash 零漂移 |
| 资格 | registry/Q2 | admission 前零变化 |

## 16. 停止条件

任一项发生即停止继续扩大：

- 新指标不能与 raw official trace 逐行一致；
- 历史哈希漂移；
- failed row 再次缺 trace；
- P3 出现任何 operational failure；
- P4 utility <2/6；
- 仍有合法动作因 verifier schema failure 被拒；
- p95 > comparator 5 倍或 case >600 秒；
- 低 ASR 只能通过全拒绝/任务失败获得；
- 修复已改变方法到不能合理称为 Task Shield reproduction；
- 需要读取 secret、改冻结文件或选择性补跑才能继续。

停止后不把失败解释为“实验没有意义”。它将作为方法兼容性、可用性和成本
边界的 negative result 保存，同时论文强基线执行资源转向 Progent/CaMeL。

## 17. 对 Q2 80% 目标的影响

P0–P5 即使全部完成，也主要是修复证据可信度和确定强基线可行性，不自动
增加 Q2 分数。只有 P6 完整、正式分析和 admission 通过后，Task Shield 才
可能计入 formal-ready baseline。

当前更重要的论文门槛仍包括：公共基准正式矩阵、至少五个正式强基线、独立
600 条确认性 blind、两家前沿 API 和预算化自适应攻击。因此 v1.6 必须严格
受停止条件约束，不能无限消耗时间而挤压更高价值的 Progent/CaMeL、blind
和 adaptive work。

## 18. 完成定义

v1.6 只有满足以下全部条件才可称为“正式完成”：

- G0–G4 已通过；
- 用户另行授权 P6；
- 726/726 terminal outcomes，0 unexplained failure；
- raw metric、utility、合法误拒和 latency 全部可重建；
- analyzer、figure、manifest 与 freeze hash-linked；
- formal admission 和双 registry 审计通过；
- historical evidence validator 通过；
- Harness、进度、决策和 handoff 同步；
- 没有把 qualification、diagnostic 或 partial 当成 formal result。

在此之前，准确状态应使用 `in_progress`、`failed_qualification`、
`completed_pilot_not_formal` 或 `blocked_waiting_formal_authorization`，不能写
`verified_formal`。

