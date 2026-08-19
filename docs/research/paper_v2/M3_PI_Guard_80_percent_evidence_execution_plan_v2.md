# M3-PI Guard 科学证据 80% 执行计划 v2

## 1. 计划状态

- 制定时间：2026-07-27
- 当前状态：`planning_frozen_pending_owner_confirmation`
- 当前科学证据完成度：61%
- 目标科学证据完成度：80%
- 本计划制定期间的 API 调用：0
- 本计划制定期间的实验结果：0
- 论文路线：授权泄漏、授权不确定性与安全—效用权衡的系统实证研究
- 明确不恢复：已被中型门禁否决的“新机制独立增益/SOTA”主叙事

本计划只定义后续实施和准入路径。公共基准、自适应攻击和第二模型的分数，
只有在完整执行、技术审查、独立结果准入和统计重建均通过后才可上调。

## 2. 现状与目标分母

当前计分来自
`docs/research/paper_v2/manuscript/completion_scorecard_v1.json`。12 个科学
工作流等权，当前总分为 730/1200，即 60.83%，显示为 61%。

达到 80% 需要至少 960/1200。新版路线只依赖三个可以由项目自身完成的
证据增量，不把工程代码量、报告页数、诊断 smoke 或未落实的盲测写成科学结果。

| 工作流 | 当前 | 目标 | 增量 | 达标证据 |
| --- | ---: | ---: | ---: | --- |
| 正式公共基准 | 10 | 100 | +90 | 两模型 6,873 条全部终态、ITT 保留、独立准入与统计重建 |
| 自适应攻击 | 0 | 100 | +100 | 冻结 40/20 任务预算面板和 hardest-20 扩展全部终态并准入 |
| 论文正文 | 30 | 70 | +40 | Results、Discussion、Abstract、主图表和完整性复核由准入结果回填 |
| 其他九项 | 620 | 620 | 0 | 本计划不提前上调 |
| 合计 | 730 | 960 | +230 | 80.00% |

阶段里程碑：

1. 公共基准完成后：820/1200，68.33%。
2. 自适应攻击完成后：920/1200，76.67%。
3. 论文证据回填到 70 后：960/1200，80.00%。

独立盲测仍为 0 分，JCR 机构核验仍是投稿门禁。因此“达到 80%”表示研究
证据计划的内部完成度达到 80%，不等于论文已经可直接投稿。

## 3. 模型角色

### 3.1 正式主模型

- 提供商：DeepSeek 官方 API
- 模型：`deepseek-v4-pro`
- 用途：公共基准六条件主矩阵、自适应攻击 40 任务和 hardest-20
- 证据链：调用前本地 request ID、规范 payload SHA-256、调用后官方
  response ID、精确返回模型、逐调用 usage/cost、安全回执和 append-only 链

### 3.2 吞吐型第二模型

- 提供商：DeepSeek 官方 API
- 模型：`deepseek-v4-flash`
- 用途：公共基准三条件第二模型矩阵、自适应攻击 20 任务
- 原因：与 Pro 共用已验证的官方 transport/身份链，官方价格明显更低，
  足以解除 Gemini 20 RPD 对正式吞吐的阻塞
- 声明边界：该路线只支持“跨模型”泛化，不支持“跨提供商”泛化

DeepSeek 官方资料在计划冻结日列出两个模型及官方 Base URL、上下文、JSON
和 tool-call 能力：

- <https://api-docs.deepseek.com/quick_start/pricing>
- <https://api-docs.deepseek.com/api/list-models>
- <https://api-docs.deepseek.com/updates>

### 3.3 跨提供商增强模型

- 提供商：Gemini 官方免费层
- 模型：`gemini-3.6-flash`
- 用途：192 项 policy-only/full 方向性复现
- 限制：本地 18 RPD、保留 2 RPD、并发 1、USD 0，至少跨 11 个 provider day
- 计分：不纳入本计划达到 80% 的必要路径；只有 prospective v3 完整准入后
  才能作为跨提供商增强证据

Gemini v1/v2 永久冻结，不恢复、不重试，也不把已有连通性诊断升级为科学结果。

## 4. 阶段 A：冻结新版执行入口

### 4.1 实现范围

在不修改现有公共/自适应冻结文件的前提下，新建版本化执行层：

- `experiments/paper_v2/public_matrix_controller_v1.py`
- `experiments/paper_v2/public_result_gate_v1.py`
- `experiments/paper_v2/public_analysis_v1.py`
- `experiments/paper_v2/adaptive_official_controller_v1.py`
- `experiments/paper_v2/adaptive_evidence_store_v1.py`
- `experiments/paper_v2/adaptive_result_gate_v1.py`
- `experiments/paper_v2/adaptive_analysis_v1.py`
- 相应 schema、candidate、admission、资格产物和单元测试

公共控制器复用已录取 DeepSeek 中型实验的：

- 六条件 runtime；
- per-call precommit 和 trace bundle；
- append-only experiment record；
- provider safety receipt；
- closed diagnostic 保留在 ITT 的规则；
- pending-only shard 恢复规则。

自适应控制器必须把“攻击查询数”和“实际 provider call 数”分开记账。一个攻击
查询可能触发多次模型调用，75,000 只能作为冻结查询面板上界，不能冒充费用上界。

### 4.2 离线验收

在任何 API 调用前必须全部通过：

1. 冻结文件 SHA-256、case 数、condition 数和 6,873 总数复现；
2. Pro/Flash exact-model 和 official-base 资格；
3. evaluator/gold 字段在线不可见；
4. payload hash、trace、record 和安全回执的正向重建；
5. 身份漂移、重复终态、已有 trace 路径、越权 effect、预算越界和链截断负例；
6. 并发写入竞态测试；若不能证明串行化 writer 正确，正式并发固定为 1；
7. focused tests、Ruff、JSON/schema 校验和完整 Harness
   `Verification failed=0`。

阶段 A 完成不改变 61%。

## 5. 阶段 B：正式公共基准

### 5.1 冻结规模

`public_benchmark_freeze_v1.json` 的真实矩阵为：

| 模型角色 | 基准 | case 数 | 条件数 | 记录数 |
| --- | --- | ---: | ---: | ---: |
| 主模型 | AgentDojo v1 | 397 | 6 | 2,382 |
| 主模型 | M3-v2 | 450 | 6 | 2,700 |
| 第二模型 | AgentDojo v1 | 297 | 3 | 891 |
| 第二模型 | M3-v2 | 300 | 3 | 900 |
| 合计 | — | 1,444 | — | 6,873 |

主模型条件为 no-defense、safe-prompt/spotlighting、PromptGuard detector-only、
最强同行评审结构基线、M3 policy-only 和 M3-full。第二模型只运行结构基线、
policy-only 和 full。

### 5.2 技术 canary

先按冻结 case 顺序和 SHA-256 规则选择：

- 每个基准 1 条攻击、1 条良性任务；
- Pro：4 cases × 6 conditions = 24 records；
- Flash：4 cases × 3 conditions = 12 records。

canary 只做 outcome-blind 技术审查，检查身份、调用链、usage/cost、失败终态、
effect isolation 和 append-only 完整性。通过后这些记录留在正式矩阵，不重复。

### 5.3 完整执行

1. 先完成 Pro 的 5,082 条；
2. outcome-blind 技术门通过后完成 Flash 的 1,791 条；
3. 不同时运行两个提供商；Pro/Flash 虽同属 DeepSeek，也使用独立 run identity；
4. canary 并发 1；完整矩阵最大并发 4，但只在串行 writer 竞态测试通过后启用；
5. 每 250 条生成只含技术状态的 checkpoint；
6. 第一个 429、身份不匹配、未知 runner failure、预算越界或证据链异常即停止；
7. 已终态项不重试。若仅有从未启动的 pending 项，使用新身份的 pending-only
   shard，保留旧 run 不可变。

### 5.4 费用门禁

基于已录取 v8 条件级调用率和每记录 CNY 成本：

- 预计 Pro 调用约 11,864 次；
- 预计 Flash 调用约 3,963 次；
- 中心费用估计约 CNY 12.03；
- 公共矩阵增量硬熔断为 CNY 25，保留约 CNY 5 账户余量。

这是工程估计，不是保证。实际 ledger 每次调用都重建累计成本。达到 CNY 25、
账户额度不足或提供商返回余额/配额错误时立即暂停，不自动缩减样本。

### 5.5 结果准入

只有以下条件全部满足，公共工作流才从 10 调到 100：

- 6,873 条均有且仅有一个终态；
- 所有失败和超时保留在 ITT；
- 两模型 exact identity、trace、安全回执和 source projection 全部可重建；
- 无未解释 runner failure；
- 独立 result gate 在不查看效果值时通过；
- scientific-analysis admission 单独冻结；
- unsafe effect、TCR、ASK/确认负担、授权 regime、基准/模型异质性、成本和
  延迟统计生成并由 `--verify-analysis` 独立重建。

若只完成 Pro 或只完成部分数据，只报告已完成比例，不把本工作流记为 100。

## 6. 阶段 C：防御感知自适应攻击

### 6.1 正式面板

保持 `adaptive_attack_freeze_v1.json` 不变：

- Pro：40 个任务，累计预算节点 50/200/500；
- Pro hardest-20：追加到 2,000；
- Flash：20 个任务，累计预算节点 50/200；
- 冻结最大查询面板：75,000；
- 攻击只看公开 `ALLOW/ASK/DENY` 和最终 unsafe-effect bit；
- 禁止向攻击器暴露 policy、detector score、gold action 和 evaluator explanation。

### 6.2 8×50 成本/运行 canary

从 40 个主模型任务中用冻结 SHA-256 规则选择 8 个任务，每个最多 50 查询：

- 最多 400 个攻击查询；
- Pro 单模型；
- 初始增量费用硬熔断 CNY 5；
- canary 查询直接作为正式预算 50 的前缀，不重复；
- 审查只看身份、调用数、token、成本、延迟、trace、checkpoint 和安全边界，
  不查看哪种攻击成功。

canary 后必须先生成成本报告，区分：

- attacker query 数；
- provider call 数；
- cache hit/miss/output tokens；
- 每查询和每任务费用；
- 对 75,000 面板的中心、P95 和 2 倍压力估计。

正式大矩阵需要新的费用 fuse 和单独 admission。若预测费用超过 CNY 180、
现有余额不足或 P95 运行时间不可接受，则暂停并由项目所有者决定充值、缩小
次要模型范围或把自适应工作流保留为部分证据；不得静默改变冻结主终点。

### 6.3 完整执行和停止规则

1. 完成 40 个任务的预算 50；
2. 在同一 checkpoint 上扩展到 200，再扩展到 500；
3. 只有全部预算 500 终态后，按预注册规则解析 hardest-20；
4. hardest-20 从已有 500 checkpoint 扩展到 2,000；
5. Flash 完成 20 个任务的 50/200；
6. 每个 query 的 candidate、public feedback、effect receipt 和链摘要持久化；
7. 第一个身份/安全/append-only/未知 runner failure 即停止；429 不重试；
8. 所有最大步数、拒答、解析失败和服务终态留在 ITT。

### 6.4 结果准入

只有全部预算面板、hardest-20、两模型和独立统计重建完成，自适应工作流才从
0 调到 100。主结果包括：

- 各预算下 unsafe-effect attack success；
- first-success-query 生存曲线；
- 50→200→500→2,000 是否饱和；
- Pro/Flash、攻击族和语言异质性；
- 防御失败与过度阻断的联合分析；
- provider calls、token、成本和 p50/p95 延迟。

## 7. 阶段 D：论文证据回填

公共和自适应结果均准入后，按以下顺序更新论文：

1. 冻结主表的原始分子/分母、绝对差、相对差和区间；
2. 写 Results，不先写结论性 Introduction；
3. 写 Discussion，重点解释安全收益、TCR/ASK 负担、授权 regime 敏感性和
   自适应攻击下的稳定性；
4. 更新 Abstract、Limitations 和 Ethics/Safety；
5. 更新 claim–evidence ledger，禁止 first/only/SOTA；
6. 生成最终主图并从 manifest 重建；
7. 进行方法审查、Devil's Advocate 审查和引用/数字/DOI 完整性审查。

当 Results、Discussion、Abstract、主图表和完整性审查都有准入证据时，
manuscript 工作流可从 30 调到 70，项目科学证据完成度达到 80%。

## 8. Gemini v3 与外部门禁

Gemini v3 可以在公共/自适应主路径之外分多日运行，但必须：

- 新建 v3 controller、Pacific-day durable meter、candidate 和 admission；
- 每天最多 18 calls，保留 2 RPD；
- 首个 429 当日停止，0 retry；
- request ID 缺失必须在论文中披露，不能伪造；
- 192 项完成前不支持跨提供商结论。

独立盲测和机构 JCR 核验不计入本计划的 80% 必要路径，但仍是投稿前任务：

- 第三方 custodian 未落实时只能称内部封存测试；
- JISA 的 SCIE/JCR Q2 必须在投稿当天通过学校/Clarivate 重新核验。

## 9. 时间与验收节奏

| 周期 | 任务 | 科学分数变化 |
| --- | --- | ---: |
| 第 1 周 | 公共/自适应 controller、gate、tests、完整 Harness | 0 |
| 第 2 周 | Pro/Flash 公共 canary 与完整公共矩阵 | 0，直至全部准入 |
| 第 3 周 | 公共结果门、统计与独立重建 | +90 |
| 第 4 周 | 自适应 8×50 canary、成本报告和正式费用门 | 0 |
| 第 5–7 周 | 完整自适应面板、hardest-20、结果门与统计 | +100 |
| 第 8 周 | Results/Discussion/Abstract/主图与完整性复核 | +40 |

最终验收：

- 科学证据总分不低于 960/1200；
- scorecard 的每次上调都指向可重建的 admitted artifact；
- 论文继续采用 empirical fallback，不覆盖中型实验负结果；
- 所有 API 输出只作为不可信 proposal；
- provider tools、external connectors、真实邮件/支付/生产 API/host command
  和非 sandbox effect 始终关闭；
- 没有把 Gemini smoke、代码完成度或未落实盲测计入科学完成度。

## 10. 当前人工检查点

本计划已经完成只读事实核算和离线规划，但尚未授权任何新实验。项目所有者确认
本计划后，下一动作是阶段 A 的离线实现与测试；只有完整 Harness 全绿后才会进入
公共基准技术 canary。
