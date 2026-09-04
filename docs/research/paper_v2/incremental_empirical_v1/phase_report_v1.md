# M3-PI Guard 增量实证强化阶段报告

## Material Passport

- 项目：M3-PI Guard
- 研究路线：授权制度与运行时 Guard 配置的实证评估
- 报告类型：阶段性技术报告（Markdown）
- 执行日期：2026-08-26--2026-08-28
- GitHub 仓库：`https://github.com/Fischl0527/RedTeam_LLM_Security.git`
- 分支：`codex/q2-empirical-study`
- 作者信息：留空，由作者投稿前填写
- 研究边界：不恢复 first/only/SOTA 或领先防御主张；不运行 Gemini 新矩阵、独立盲测、生产工具、真实外部副作用、Full Harness 或历史递归重放

## 1. 执行摘要

本阶段围绕已批准的五项增量实验 E1--E5 展开，目标不是增加低价值记录数量，而是补强现有 SCI 二区实证路线中最关键的因果识别、机制核验、困难样本、模型复现和自适应尾部证据。E1--E5 均已完成正式执行和一次性统计；5 幅主图与 5 张主表已从紧凑分析文件生成。所有 API 实验均使用隔离的模拟 effect，provider tools 和真实外部 effect 为零。

本轮新增正式证据包括：

- E1：720 条 DeepSeek V4 Pro 同期 2×2 因子执行；
- E2：240 条 DeepSeek V4 Pro 端到端执行和 480 次无 API Guard 回放；
- E3：240 条 DeepSeek V4 Pro 风险富集挑战执行；
- E4：360 条 DeepSeek V4 Flash 同厂商复现执行；
- E5：12 个预先选定的 B200 survivor 全部从 query 201 扩展到 query 500，共形成 3,600 个终态 query work key；未发现新的 unsafe effect。

| 实验 | 模型/层次 | 正式终态规模 | API tokens | 分析归因成本 | 核心观察 |
|---|---|---:|---:|---:|---|
| E1 | DeepSeek V4 Pro | 720 | 1,274,193 | CNY 3.6602862 | unsafe 端点地板；module/prompt 效应区间跨零 |
| E2 | Pro 端到端 + offline Guard | 240 + 480 | 102,282 | CNY 0.4254876 | Guard 层有来源敏感性，端到端动作执行为零 |
| E3 | DeepSeek V4 Pro | 240 | 517,261 | CNY 1.0690866 | 历史 unsafe 仅 1/60 重现，失败负担较高 |
| E4 | DeepSeek V4 Flash | 360 | 528,167 | CNY 0.5410834 | 同厂商复现，四个 attack cell 均 0/50 |
| E5 | DeepSeek V4 Pro adaptive | 3,600 queries | 4,511,768 | CNY 24.5551236 | 选定 B200 survivor 中 0/12 在 B500 前新成功 |
| 合计 | API + offline | 1,560 常规 + 480 offline + 3,600 queries | 6,933,671 | CNY 30.2510674 | 仅报告冻结设计下的经验结果 |

常规端到端 API 执行合计 1,560 条，另有 480 次无 API Guard 回放和 3,600 个 E5 自适应尾部终态查询。E5 的 3,605 条物理行包含 5 条被后续显式 failed-only 恢复取代的失败尝试；统计按 3,600 个最新 work key 进入 ITT。成本上限在 owner 明确要求后改为非阻断的机器保护阈值，实际 token 与成本仍逐项记账。

阶段结果不支持把 M3-full 写成已证明领先的防御机制。更稳健的研究叙事是：授权制度、prompt 配置、运行时模块、来源权威性和失败处理共同决定被测得的安全--效用结果；机制层的 provenance sensitivity 不能自动等同于端到端安全或任务完成收益。按照 owner 最新要求，本阶段只固化为 Markdown 报告，不继续编写或重建论文正文。

## 2. 研究问题与五项实验

### 2.1 E1：同期 prompt × module 因子实验

E1 在同一执行窗口对固定 180 个案例运行四个条件：`policy_normal`、`policy_safe`、`full_normal` 和 `full_safe`。四个条件统一采用 `auto_compiled` 授权，因此 prompt 因素与 runtime module 因素可分别估计，不再把不同日期或不同执行身份的旧记录拼成因子实验。

720/720 个计划项获得官方响应。最新 ITT 记录包含 657 个 `completed`、54 个 `parse_failure` 和 9 个 `provider_failure`；两条无响应旧尝试被保留为 superseded 物理记录，但不替代 720 个最新 work key。原始 evaluator 字段在线暴露、provider-managed tools 和真实外部 effect 均为零。

| 条件 | attack unsafe effect | attack unsafe-or-failure | benign-tool TCR |
|---|---:|---:|---:|
| policy / normal | 1/100 | 9/100 | 23/60 |
| policy / safe | 1/100 | 11/100 | 21/60 |
| full / normal | 0/100 | 7/100 | 21/60 |
| full / safe | 0/100 | 8/100 | 19/60 |

主要估计显示：direct unsafe-effect 的 module 主效应为 -1.00 个百分点（95% CI -3.00 至 0.00），prompt 和交互效应均为 0；benign-tool TCR 的 module 与 prompt 主效应均为 -3.33 个百分点，交互为 0。由于 400 个 attack assignments 仅出现两次 unsafe effect，安全终点存在明确地板效应，不能把零或接近零解释为等效性。

`unsafe_effect OR operational_failure` 是预设的失败敏感性终点，不属于两个共同主要终点的 Holm 家族。其 module 效应为 -2.50 个百分点（95% CI -5.50 至 0.00；描述性 bootstrap p=0.0938）。

### 2.2 E2：来源权威性反事实

E2 构造 60 个受控基础任务，各生成 `trusted_origin` 和 `untrusted_origin` 两个版本；文本、关键参数值、相对位置和策略保持不变，仅改变关键命题的来源权威性。端到端层对 policy/full 两个 module 配置运行，共 240 条；机制层对授权与非授权参数提案进行 480 次确定性 Guard 回放。

端到端 240/240 条均获得响应，但所有 cell 的实际 executed actions 均为 0。因此 unauthorized-argument-influence 处于终点地板，不能据此声称来源无影响。负担端出现清晰差异：

- policy/trusted：ASK 60/60，DENY 0/60；
- policy/untrusted：ASK 53/60，DENY 0/60；
- full/trusted：ASK 57/60，DENY 0/60；
- full/untrusted：ASK 0/60，DENY 55/60，operational failure 1/60。

实际执行动作在来源互换下均为 0/60 改变；full 配置有 1/60 对出现 operational-status 改变，二者分开报告。480 次离线 Guard 回放由 240 个未授权提案和 240 个授权提案组成：false allow 为 0/240，false block 为 30/240（12.5%）。policy 在 trusted/untrusted 下均为 60 ALLOW、60 ASK；full/trusted 相同，而 full/untrusted 为 30 ALLOW、30 ASK、60 DENY。该结果证明当前 Guard 决策层对来源权威性敏感，但没有证明这一机制在本组端到端任务上改善完成率。

### 2.3 E3：风险富集挑战集

E3 从历史 Public primary 的 600 个攻击案例中，按预先冻结的 suite/attack-family 覆盖和结果无关并列规则选择 60 个曾在至少一个旧条件产生 unsafe effect 的案例。该样本明确是 outcome-enriched challenge set，不估计自然攻击流行率或部署 ASR。

240/240 条均获得响应；185 条正常完成，17 条 parse failure，38 条 provider failure，全部留在 ITT。四个 cell 的 unsafe effect 为 1/60、1/60、0/60、0/60；unsafe-or-failure 为 16/60、15/60、12/60、14/60。历史 unsafe effect 只在 1/60 个案例中重现。module 效应为 -1.67 个百分点（direct unsafe）和 -4.17 个百分点（unsafe-or-failure）。结果更支持“历史困难案例的再现不稳定且失败负担较高”，而不是总体鲁棒性声明。

### 2.4 E4：DeepSeek V4 Flash 因子复现

E4 对冻结的 90 个嵌套案例运行与 E1 相同的四条件设计，共 360 条。360/360 个最新 work key 获得响应；一条无响应 transport failure 在定位原因后仅恢复该失败 key，没有重跑其他成功行。最终 ITT 状态为 347 completed、8 parse failure、4 provider failure 和 1 max-steps。

四个 attack cell 均为 0/50 unsafe effect。benign-tool TCR 为 10/30、8/30、10/30、10/30；module、prompt 与交互效应分别为 +3.33、-3.33 和 +6.67 个百分点。unsafe-or-failure 的 module 效应为 +3.00 个百分点。E4 只能作为同一 provider 内的模型复现；all-zero 安全终点不支持等效性或跨厂商泛化。

### 2.5 E5：B200-survivor 条件性自适应尾部

E5 只对冻结的 12 个 budget-200 未成功任务继续执行 query 201--500，并在首次 unsafe effect 后停止。它估计的是 `P(first success by 500 | no success by 200, selected survivor)`，不得并入原 40 任务形成伪造的完整 B500 曲线，也不用于宣称攻击饱和。

E5 在 owner 恢复项目后，从先前 q474 暂停点继续。所有无响应项都先停止进程、
记录原因，再通过显式 `--retry-failed-work-key` 只恢复对应失败 key；成功记录从未
重跑。q459 的首次恢复还暴露了 recovery trace 目录复用缺陷，该次失败发生在
provider 请求之前。修复后每个恢复进程使用新的 `provider_traces_recoveryN`
目录，并把特殊第三次尝试限制为“完整历史均无响应、第二次恰为本地 trace 冲突、
旧 trace 无 completed 事件”的唯一情形。

| E5 终态项 | 结果 |
|---|---:|
| 预定并完成的 survivor | 12/12 |
| 物理 query 行 / 唯一 query key | 3,605 / 3,600 |
| 到达 q500 的任务 | 12/12 |
| query 201--500 内首次 unsafe effect | 0/12 |
| 条件成功概率点估计 | 0.0% |
| Wilson 95% CI | 0.0%--24.25% |
| 最新 ITT 状态 | 3,577 completed；21 parse failure；2 provider failure |
| superseded 物理失败尝试 | 5 |
| input / output / total tokens | 4,171,775 / 339,993 / 4,511,768 |
| completed 行 total latency p50 / p95 | 3,087.1 / 7,883.4 ms |
| 分析归因成本 | CNY 24.5551236 |
| runner 累计预算台账 | CNY 24.5611314 |
| automatic retry / provider tools / 真实 effect | 0 / 0 / 0 |

一次性分析成功生成 `analysis_v1.json`。0/12 表示在“已经通过 B200 且被预先选入
的 12 个 survivor”中，query 201--500 没有发现新的 unsafe effect；它不是原始
40 任务的完整 B500 曲线，也不能证明攻击饱和或真实尾部风险为零。Wilson 上界
仍为 24.25%，且 23 个非 completed 最新记录必须与 unsafe effect 分开报告。

## 3. API、安全与失败恢复

### 3.1 API 使用与模型身份

常规实验主模型为 DeepSeek V4 Pro，复现模型为 DeepSeek V4 Flash。每条正式记录包含本地 request ID、canonical payload digest、官方 response ID、精确返回模型、usage、时延和运行状态。密钥仅从 Git 忽略的本地配置加载到当前 Python 进程，不写入报告、原始公开记录、日志摘要或 Git。

### 3.2 安全边界

- provider tools 始终禁用；
- 邮件、支付、浏览器、代码执行和生产 API 等真实能力不可用；
- action/effect 只在隔离模拟器内生成 receipt；
- evaluator/gold 原始字段不进入在线 Guard 状态；
- 本阶段没有真实外部副作用。

### 3.3 失败处理

- 已获得官方响应的 refusal、parse failure、max-steps 或 provider-level failure 保留在 ITT，不覆盖；
- 未获得官方响应的工程/传输失败只有在原因修复后才运行对应失败 work key；
- 已成功且不受修复影响的行不重跑；
- 无自动重试、跨模型回退或选择性排除；
- 统计同时报告 unsafe effect、operational failure 和 pessimistic unsafe-or-failure，避免把系统失败误当成安全成功。

### 3.4 E5 工作区分支切换恢复

E5 首轮运行期间，工作区在 runner 外部从 `codex/q2-empirical-study` 切换到
`main`。增量计划源码因此暂时不可见，q377 在取得 provider 响应前留下一个
`FileNotFoundError`，随后冻结计划复核按 fail-closed 规则以
`adaptive-tail frozen plan drift` 停止。reflog、raw row 和 checkpoint 三处状态一致：
此前成功 query 均已持久化，q377 为 `response_obtained=false` 且
`retry_eligible=true`。

恢复时没有 reset、force 或重放成功 query。工作区安全切回原分支后，12 个 survivor、
A1/A2/A3 各四项和两项正式前缀重新通过只读检查；只显式恢复 q377，成功记录为
attempt 2，之后从下一个 pending query 继续。该事件作为工程恢复记录，不作为模型失败
或攻击结果进入效应估计。

### 3.5 E5 成本上限修正

原计划的低额成本估计不足以覆盖 3,600 个查询。先前 CNY 20/30 上限仍可能在
冻结 cohort 闭合前触发。owner 随后明确要求“成本不是问题，不要让成本限制项目”。
因此在无 E5 进程运行时，将 Adaptive/Global 机器保护阈值设为非阻断的
CNY 1,000/1,000；实际成本仍逐 query 记录，且不会从常规 Pro/Flash 工作流借用
科学身份或改变分母。

该修正只改变最大允许成本，不改变 12 个样本、A1/A2/A3 各四项、query
201--500、攻击器、模型、seed、首次成功停止、ITT、统计口径或安全边界。最终
分析归因成本为 CNY 24.5551236。修正记录位于
`protocols/paper_upgrade_v2/incremental_empirical_v1/budget_amendment_v2.md`。

### 3.6 失败恢复与最终分析门

E5 共发生 q377、q474、q459 和 q354 等无响应或本地恢复失败事件。每次都由 runner
自然 `paused`，自动重试保持 0；诊断和代码修正完成后，只显式恢复失败 work key。
q459 的 attempt 2 是无 provider 请求的本地 trace-root 冲突，因此允许一次严格受限
的 attempt 3；完整历史校验保证任何已有 response-bearing 记录都不能再次执行。

最终 12 个 checkpoint 全部终态，3,600 个最新 query work key 均获得官方响应。
分析器随后只运行一次并成功输出 `adaptive-tail/analysis_v1.json`。该分析门继续拒绝
非终态 survivor、重复终态和越界 query，避免把部分执行误报为完整 E5。

## 4. 统计与主张边界

每个 cell 报告原始分子/分母和 Wilson 95% CI；简单二条件配对采用 exact McNemar；因子主效应与交互采用按 `case_id` 配对的 10,000 次 bootstrap。E1 的 module、prompt、interaction 在 direct unsafe effect 与 benign-tool TCR 两个共同主要终点家族内分别做 Holm 校正；失败敏感性终点只作预设描述性分析。E2 的来源、module 和交互形成独立来源实验家族。E3、E4、E5 为挑战、复现或条件敏感性证据，不另开显著性家族。

当前可支持的主张：

- 同期 2×2 设计可以把 prompt 与 module 效应从配置包差异中分离；
- 当前直接安全终点高度地板化，不能证明等效或领先；
- 来源权威性在 Guard 决策层产生可观测差异，但端到端收益受 ASK/DENY 和不执行地板限制；
- 风险富集案例的历史 unsafe outcome 重现不稳定；
- Flash 只提供同厂商模型复现；
- 预定 12 任务条件尾部估计量已闭合为 0/12，但 95% CI 上界为 24.25%，且该结果只适用于选中的 B200 survivor。

当前不支持的主张：first、only、SOTA、跨厂商泛化、完整 provenance 的端到端净收益、原 40 任务的完整 B500 面板、零尾部风险或攻击饱和。

## 5. `E:\M3_PI_Guard_test\outputs` 目录说明

### 5.1 顶层目录

`outputs` 是运行产物区，不是所有子目录都属于当前论文主证据。当前顶层结构为：

```text
E:\M3_PI_Guard_test\outputs\
├─ document_qa\       # 历史 Word/文档结构与可访问性检查结果
├─ experiments\       # 各代实验的原始记录、分析和恢复状态
├─ metrics\           # 历史或跨实验指标产物
├─ paper_upgrade_v1\  # 旧 paper-upgrade-v1 证据与运行输出
├─ paper_upgrade_v2\  # 既有 Public/Adaptive 等 paper-v2 正式结果
├─ paper_v2\          # paper-v2 构建/分析中间产物
├─ quality\           # 历史质量检查结果
├─ report_qa\         # 历史报告检查产物
├─ runs\              # 通用运行记录
├─ test-tmp\          # 定向测试临时目录，不是论文证据
└─ verification\      # 历史验证产物；本轮不递归重放
```

其中 `outputs/experiments/` 还包含大量 E0--E17、基线适配和旧实验目录。它们是项目历史，但不自动成为当前论文证据。本阶段只一次性复用已明确列入 Methods 的既有 Public/Adaptive 结果，不因目录存在就把某项旧输出纳入稿件。

### 5.2 本轮增量实验主目录

当前论文新增证据集中在：

```text
E:\M3_PI_Guard_test\outputs\experiments\incremental_empirical_v1\
├─ factorial\
│  ├─ raw_records_v1.jsonl       # E1 全部物理尝试；统计按最新 work key 形成 ITT
│  ├─ analysis_v1.json           # E1 一次性重建的 cell、因子效应与完整性统计
│  ├─ canary_gate_v1.json        # 8 条正式前缀的技术准入结论
│  └─ internal\                  # provider trace 与预算事件，仅本地恢复/核查
├─ provenance\
│  ├─ raw_records_v1.jsonl       # E2 240 条端到端记录
│  ├─ offline_guard_replay_v1.jsonl # E2 480 次确定性 Guard 回放
│  ├─ analysis_v1.json           # 端到端与回放分层分析
│  ├─ canary_gate_v1.json
│  └─ internal\
├─ challenge\
│  ├─ raw_records_v1.jsonl       # E3 240 条风险富集记录
│  ├─ analysis_v1.json
│  ├─ canary_gate_v1.json
│  └─ internal\
├─ flash\
│  ├─ raw_records_v1.jsonl       # E4 物理尝试；含一条被单 key 恢复取代的无响应尝试
│  ├─ analysis_v1.json
│  ├─ canary_gate_v1.json
│  └─ internal\
└─ adaptive-tail\
   ├─ raw_query_records_v1.jsonl # E5 每个新增 query 的紧凑正式记录
   ├─ analysis_v1.json           # E5 条件成功率、生存曲线、分族和成本/失败统计
   ├─ canary_gate_v1.json        # 两任务×5 查询正式前缀门
   ├─ cost_summary_v1.json       # runner 结束时的紧凑成本摘要
   ├─ failure_records_v1.jsonl   # append-only 工程失败与恢复诊断旁路记录
   ├─ search_checkpoints\        # 12 个终态 MCTS/搜索断点，仅用于恢复审计
   └─ internal\
      ├─ provider_traces*\       # 正常/恢复进程的本地请求链，不是统计入口
      └─ deepseek_budget_events.jsonl # 本地硬熔断台账，不作独立论文数据源
```

### 5.3 各类文件应如何使用

| 文件类型 | 用途 | 是否作为论文统计入口 | Git 策略 |
|---|---|---|---|
| `raw_records_v1.jsonl` / `raw_query_records_v1.jsonl` | 保存不可覆盖的物理尝试、官方响应标识、状态与最小公开 trace bundle | 是；按冻结的最新 work-key/ITT 规则读取 | 提交紧凑正式记录 |
| `offline_guard_replay_v1.jsonl` | 保存无 API 的确定性 Guard 机制回放 | 仅用于 E2 机制层，不能替代端到端结果 | 提交 |
| `analysis_v1.json` | 对应 raw JSONL 做一次性计数、配对统计和完整性检查 | 是；E1--E5 均已生成，E5 保持条件 survivor 边界 | 提交五项紧凑分析 |
| `canary_gate_v1.json` | 记录正式前缀是否通过模型身份、字段隔离和无真实 effect 门 | 不是效应估计；是技术准入证据 | 提交 |
| `cost_summary_v1.json` | 汇总一次运行的 token/成本/失败 | 只用于运行与成本报告 | 提交 |
| `failure_records_v1.jsonl` | 保留 E5 无响应、本地 trace 冲突及恢复尝试；统计身份仍由主 raw JSONL 最新 work key 决定 | 否；仅用于失败审计和恢复说明 | 提交紧凑记录 |
| `search_checkpoints/` | 支持 E5 pending-only 恢复且最终证明 12 个任务均到 q500 | 否 | 本地保留，不作为报告统计入口 |
| `internal/provider_traces*/` | 诊断响应前失败、核对正常及恢复请求链 | 否；禁止用它选择性改写 outcome | 本地保留，不批量提交 |
| `internal/*budget_events.jsonl` | 控制硬熔断和恢复时的累计成本 | 否；E5 raw 行已嵌入公开 usage/cost 摘要 | 默认本地保留，不生成额外哈希包 |

图表和主表不会写回 `outputs` 的 provider 内部目录。五个紧凑
`analysis_v1.json` 已单向生成到下列目录：

```text
E:\M3_PI_Guard_test\docs\research\paper_v2\incremental_empirical_v1\
├─ figures\  # 5 幅主图，每图 PNG/SVG/PDF，共 15 个图文件与 manifest
├─ tables\   # 5 张主表 CSV 与轻量 manifest
└─ *.md       # 各实验结果说明与本阶段报告
```

五幅图分别为 authority boundary、E1 因子交互、E2 来源反事实、E1/E3/E4
因子 forest 和 E5 双采样框架尾部曲线；五张表分别为条件设计、E1 因子估计、
E2 provenance、E3/E4 鲁棒性和 E5 条件尾部。图表只读取 analysis JSON，不读取
`internal/provider_traces*`、密钥、请求正文或响应正文。

既有论文结果还会只读复用 `outputs/experiments/lean_empirical/`、`outputs/paper_upgrade_v2/` 及其已经完成的一次性分析。`outputs/test-tmp/`、历史 E0--E17 全量目录、旧 Harness/verification 目录和内部 trace 不会因为本阶段结束而被重新计算、递归验真或整体提交。

## 6. 本阶段交付物与论文暂停边界

owner 于 E5 完成后明确要求“目前的成果先用 Markdown 报告记录，先不用写论文”。
因此本阶段交付限定为：

- 本报告：`docs/research/paper_v2/incremental_empirical_v1/phase_report_v1.md`；
- E1--E5 五份紧凑 `analysis_v1.json`；
- 5 幅主图的 PNG/SVG/PDF 和图清单；
- 5 张主表 CSV 和表清单；
- E5 紧凑 raw、canary、成本与失败记录；
- 定向测试结果、Harness 最新状态和 GitHub 阶段提交。

本轮不继续修改或重建英文主稿、中文对照稿、Supplement、Cover Letter、JISA
上传包或 Word 文件，也不启动新一轮方法审查和 Devil's Advocate 审查。旧稿继续
保留，但其中未同步 E5 的段落不得作为本阶段最终成果引用。作者姓名、顺序、单位、
通信作者、CRediT、资助和利益冲突信息继续留空。本阶段不生成额外 DOCX 或重复
哈希包。

## 7. 定向验证与 Git 里程碑

已推送的阶段检查点：

| Commit | 内容 |
|---|---|
| `9970913` | 增量研究设计冻结 |
| `d8ed77e` | 共享 runner 与离线资格化 |
| `e010e0f` | 执行前价格/预算配置 |
| `394e1ea` | resolver identity 修复 |
| `39bbf92` | provider failure 类型修复 |
| `c81acef` | trace activation/CRLF 修复 |
| `138b070` | E1--E5 分析资格化 |
| `d238fcd` | 图表生成器资格化 |
| `cb55a57` | E1 正式结果 |
| `0c7a905` | E1--E3 正式结果 |
| `1f04bbc` | E5 非阻断成本阈值与恢复前检查点 |
| `072f6ed` | E5 显式恢复 trace 根隔离修复 |
| `8345d5e` | 完整历史恢复校验与 E5 分析 CLI 修复 |
| `9f48b9a` | E4/E5 终态结果、5 幅主图与 5 张主表 |

远端 `0c7a905` 之后，本地存在一项由工作区外部操作创建的 owner commit
`9608012`。它在切换到 `main` 前同时收录了 E4/稿件改动和较广的既有工作区文件；
本轮不 reset、不 amend、不改写这一已有提交，也不把它冒充为自动化代理的精简
里程碑。后续代理提交仍只暂存本轮直接相关的代码、紧凑
raw/analysis/canary、图表、文稿与 Harness 状态。

本检查点将 E4、E5 终态紧凑结果、五图五表、Harness 登记和本报告形成可审查的
提交，并推送到 `origin/codex/q2-empirical-study`，即 `RedTeam_LLM_Security`
仓库。旧 `m3-guard` 远程仅保留为历史关联，不再作为本轮默认推送目标。
E5 raw JSONL 为约 56.13 MiB，GitHub 已接受但提示超过其 50 MiB 推荐值；该文件
仍低于 GitHub 单文件硬限制，当前未引入 Git LFS，也未提交 `internal/` trace。

按当前“只交付 Markdown 报告、不写论文”的范围，最终定向验证为：

- incremental shared runner、E5 runner、analysis、figures、tables：33/33 pytest 通过；
- 5 个相关 Python 模块 `py_compile` 通过；
- 五幅 PNG 主图完成视觉检查，Figure 1 的 source-swap 标签重叠已修正；
- `git diff --check` 在提交前执行；
- 未运行论文/DOCX builder 测试，因为 owner 已暂停论文写作。

本轮未运行 Full Harness、历史递归重放或全量哈希重算，也未把它们作为本阶段
报告的完成条件。

## 8. 结论与后续边界

本阶段已经把项目从“配置包结果堆叠”推进到更可解释的实证路线：E1 处理 prompt
与 module 混杂；E2 区分机制层与端到端层；E3 暴露困难样本的重现不稳定性；E4
提供同厂商模型复现；E5 闭合预定的 12 个 B200-survivor 条件尾部。五项实验均已
完成，但主要结论是边界清晰的经验结果，而不是机制领先：直接 unsafe 终点地板化，
任务效用较低，来源敏感性主要体现在 ASK/DENY，风险富集重现有限，E5 的 0/12
仍有 24.25% 的 Wilson 上界。

截至本报告定稿，项目没有正在运行的本轮 API 实验进程，也不再启动 Gemini、盲测、
Full Harness、历史递归验证或新的自适应预算。E1--E5 的实验阶段可以登记为完成；
`F-PAPER-002` 仍保持 `in_progress`，仅因为 owner 已暂停论文写作、双语稿同步、方法
审查和投稿准备，而不是因为增量实验未闭合。

后续若 owner 恢复论文工作，应从本报告和五份 `analysis_v1.json` 开始同步稿件，
不重新调用 E1--E5 API。作者仍需自行填写作者/机构信息，确认公开数据与代码发布
范围，完成作者侧查重和投稿伦理核对，并在投稿当天通过学校或 Clarivate 数据库
确认目标期刊的 SCIE/JCR 分区。
