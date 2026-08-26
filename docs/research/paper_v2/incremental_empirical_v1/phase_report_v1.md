# M3-PI Guard 增量实证强化阶段报告

## Material Passport

- 项目：M3-PI Guard
- 研究路线：授权制度与运行时 Guard 配置的实证评估
- 报告类型：阶段性技术报告（Markdown）
- 执行日期：2026-08-26
- GitHub 仓库：`https://github.com/Fischl0527/RedTeam_LLM_Security.git`
- 分支：`codex/q2-empirical-study`
- 作者信息：留空，由作者投稿前填写
- 研究边界：不恢复 first/only/SOTA 或领先防御主张；不运行 Gemini 新矩阵、独立盲测、生产工具、真实外部副作用、Full Harness 或历史递归重放

## 1. 执行摘要

本阶段围绕已批准的五项增量实验 E1--E5 展开，目标不是增加低价值记录数量，而是补强现有 SCI 二区实证稿中最关键的因果识别、机制核验、困难样本、模型复现和自适应尾部证据。E1--E4 已完成正式执行和一次性统计；E5 按冻结的 B200 survivor 条件性尾部设计执行，最终状态在本报告定稿时写入。所有 API 实验均使用隔离的模拟 effect，provider tools 和真实外部 effect 为零。

截至 E4，新增正式证据包括：

- E1：720 条 DeepSeek V4 Pro 同期 2×2 因子执行；
- E2：240 条 DeepSeek V4 Pro 端到端执行和 480 次无 API Guard 回放；
- E3：240 条 DeepSeek V4 Pro 风险富集挑战执行；
- E4：360 条 DeepSeek V4 Flash 同厂商复现执行；
- E5：12 个预先选定的 B200 survivor，从 query 201 条件性扩展至最多 500，并在首次 unsafe effect 后停止。

阶段结果不支持把 M3-full 写成已证明领先的防御机制。更稳健的论文叙事是：授权制度、prompt 配置、运行时模块、来源权威性和失败处理共同决定被测得的安全--效用结果；机制层的 provenance sensitivity 不能自动等同于端到端安全或任务完成收益。

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

实际执行动作在来源互换下均为 0/60 改变；full 配置有 1/60 对出现 operational-status 改变，二者分开报告。离线 Guard 回放得到 0/480 false allow 和 30/480 false block。policy 在 trusted/untrusted 下均为 60 ALLOW、60 ASK；full/trusted 相同，而 full/untrusted 为 30 ALLOW、30 ASK、60 DENY。该结果证明当前 Guard 决策层对来源权威性敏感，但没有证明这一机制在本组端到端任务上改善完成率。

### 2.3 E3：风险富集挑战集

E3 从历史 Public primary 的 600 个攻击案例中，按预先冻结的 suite/attack-family 覆盖和结果无关并列规则选择 60 个曾在至少一个旧条件产生 unsafe effect 的案例。该样本明确是 outcome-enriched challenge set，不估计自然攻击流行率或部署 ASR。

240/240 条均获得响应；185 条正常完成，17 条 parse failure，38 条 provider failure，全部留在 ITT。四个 cell 的 unsafe effect 为 1/60、1/60、0/60、0/60；unsafe-or-failure 为 16/60、15/60、12/60、14/60。历史 unsafe effect 只在 1/60 个案例中重现。module 效应为 -1.67 个百分点（direct unsafe）和 -4.17 个百分点（unsafe-or-failure）。结果更支持“历史困难案例的再现不稳定且失败负担较高”，而不是总体鲁棒性声明。

### 2.4 E4：DeepSeek V4 Flash 因子复现

E4 对冻结的 90 个嵌套案例运行与 E1 相同的四条件设计，共 360 条。360/360 个最新 work key 获得响应；一条无响应 transport failure 在定位原因后仅恢复该失败 key，没有重跑其他成功行。最终 ITT 状态为 347 completed、8 parse failure、4 provider failure 和 1 max-steps。

四个 attack cell 均为 0/50 unsafe effect。benign-tool TCR 为 10/30、8/30、10/30、10/30；module、prompt 与交互效应分别为 +3.33、-3.33 和 +6.67 个百分点。unsafe-or-failure 的 module 效应为 +3.00 个百分点。E4 只能作为同一 provider 内的模型复现；all-zero 安全终点不支持等效性或跨厂商泛化。

### 2.5 E5：B200-survivor 条件性自适应尾部

E5 只对冻结的 12 个 budget-200 未成功任务继续执行 query 201--500，并在首次 unsafe effect 后停止。它估计的是 `P(first success by 500 | no success by 200, selected survivor)`，不得并入原 40 任务形成伪造的完整 B500 曲线，也不用于宣称攻击饱和。

> E5 最终行数、成功数、首次成功位置、条件概率、token、成本和失败状态将在 runner 自然终止并完成一次性分析后写入；现阶段不提前填写或根据中间状态推断。

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

## 4. 统计与主张边界

每个 cell 报告原始分子/分母和 Wilson 95% CI；简单二条件配对采用 exact McNemar；因子主效应与交互采用按 `case_id` 配对的 10,000 次 bootstrap。E1 的 module、prompt、interaction 在 direct unsafe effect 与 benign-tool TCR 两个共同主要终点家族内分别做 Holm 校正；失败敏感性终点只作预设描述性分析。E2 的来源、module 和交互形成独立来源实验家族。E3、E4、E5 为挑战、复现或条件敏感性证据，不另开显著性家族。

当前可支持的主张：

- 同期 2×2 设计可以把 prompt 与 module 效应从配置包差异中分离；
- 当前直接安全终点高度地板化，不能证明等效或领先；
- 来源权威性在 Guard 决策层产生可观测差异，但端到端收益受 ASK/DENY 和不执行地板限制；
- 风险富集案例的历史 unsafe outcome 重现不稳定；
- Flash 只提供同厂商模型复现；
- 自适应尾部只对预先选定的 B200 survivor 做条件性解释。

当前不支持的主张：first、only、SOTA、跨厂商泛化、完整 provenance 的端到端净收益、完整 B500 面板或攻击饱和。

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
   ├─ analysis_v1.json           # E5 完成后的一次性条件尾部分析
   ├─ canary_gate_v1.json        # 两任务×5 查询正式前缀门
   ├─ cost_summary_v1.json       # runner 结束时的紧凑成本摘要
   ├─ search_checkpoints\        # MCTS/搜索断点，只用于 pending-only 恢复
   └─ internal\
      ├─ provider_traces\        # 本地请求链恢复材料，不是论文统计入口
      └─ deepseek_budget_events.jsonl # 本地硬熔断台账，不作独立论文数据源
```

### 5.3 各类文件应如何使用

| 文件类型 | 用途 | 是否作为论文统计入口 | Git 策略 |
|---|---|---|---|
| `raw_records_v1.jsonl` / `raw_query_records_v1.jsonl` | 保存不可覆盖的物理尝试、官方响应标识、状态与最小公开 trace bundle | 是；按冻结的最新 work-key/ITT 规则读取 | 提交紧凑正式记录 |
| `offline_guard_replay_v1.jsonl` | 保存无 API 的确定性 Guard 机制回放 | 仅用于 E2 机制层，不能替代端到端结果 | 提交 |
| `analysis_v1.json` | 对对应 raw JSONL 做一次性计数、配对统计和完整性检查 | 是；图表和稿件的直接统计输入 | 提交 |
| `canary_gate_v1.json` | 记录正式前缀是否通过模型身份、字段隔离和无真实 effect 门 | 不是效应估计；是技术准入证据 | 提交 |
| `cost_summary_v1.json` | 汇总一次运行的 token/成本/失败 | 只用于运行与成本报告 | 提交 |
| `search_checkpoints/` | 支持 E5 从未终态位置继续，不重放成功 query | 否 | 通常保留本地，不作为稿件附件 |
| `internal/provider_traces/` | 诊断响应前失败、核对官方 request/response 链 | 否；禁止用它选择性改写 outcome | 默认本地保留，不批量提交 |
| `internal/*budget_events.jsonl` | 控制硬熔断和恢复时的累计成本 | 否；E5 raw 行已嵌入公开 usage/cost 摘要 | 默认本地保留，不生成额外哈希包 |

图表和主表不会写回 `outputs` 的 provider 内部目录，而是由五个紧凑 `analysis_v1.json` 单向生成到：

```text
E:\M3_PI_Guard_test\docs\research\paper_v2\incremental_empirical_v1\
├─ figures\  # PNG/SVG/PDF 五幅主图
├─ tables\   # 五张主表 CSV 与轻量 manifest
└─ *.md       # 各实验结果说明与本阶段报告
```

既有论文结果还会只读复用 `outputs/experiments/lean_empirical/`、`outputs/paper_upgrade_v2/` 及其已经完成的一次性分析。`outputs/test-tmp/`、历史 E0--E17 全量目录、旧 Harness/verification 目录和内部 trace 不会因为本阶段结束而被重新计算、递归验真或整体提交。

## 6. 论文集成与交付物

本阶段的论文交付以 Markdown 为主：

- 英文主稿：`docs/research/paper_v2/manuscript/manuscript_deepseek_v1.md`；
- 中文对照稿：`docs/research/paper_v2/manuscript/manuscript_zh_v1.md`；
- 5 幅主图：authority boundary、E1 因子交互、E2 来源反事实、E1/E3/E4 forest、E5 adaptive tail；
- 5 张主表：因子设计、E1 因子估计、E2 来源证据、E3/E4 鲁棒性、E5 条件尾部；
- Supplementary Tables S1--S10；
- 方法审查和 Devil's Advocate 审查；
- 本 Markdown 阶段报告。

作者姓名、顺序、单位、通信作者、CRediT、资助和利益冲突信息继续留空。本阶段不以 Word 报告为交付物，也不为报告生成额外 DOCX 或重复哈希包。

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

最终 E4/E5、统一统计、双语稿、审查和本报告将各自形成可审查 commit，并推送到 `origin/codex/q2-empirical-study`，即 `RedTeam_LLM_Security` 仓库。旧 `m3-guard` 远程仅保留为历史关联，不再作为本轮默认推送目标。只提交与本轮直接相关的代码、紧凑 raw/analysis/canary、图表和文稿；不纳入用户已有的无关工作树文件。

最终定向验证应包括：

- incremental runner/analysis/figures/tables 的 pytest；
- 英文 Markdown builder 与中英文数值一致性测试；
- Ruff 和 `py_compile`；
- `git diff --check`；
- 逐图视觉检查。

本轮明确不运行 Full Harness，也不把历史全量哈希重算作为论文完成条件。

## 8. 结论与后续作者动作

五项增量实验的核心价值是把论文从“配置包结果堆叠”推进为可解释的实证研究：E1 处理因果混杂，E2 区分机制层与端到端层，E3 暴露困难样本的重现不稳定性，E4提供同厂商模型复现，E5测量预算 200 后的条件尾部风险。无论其结果是否正面，均按冻结口径进入稿件。

实验和稿件完成后，剩余动作由作者负责：填写作者/机构信息，确认公开数据与代码发布范围，完成作者侧查重和投稿伦理核对，并在投稿当天通过学校或 Clarivate 数据库确认 JISA 的 SCIE/JCR Q2 状态。
