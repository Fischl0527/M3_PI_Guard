# M3-PI Guard 二区论文完整计划

> 创建日期：2026-07-23
> 工作分支：test1
> 当前提交：d74cef2
> 目标：在 5-6 个月内完成二区（Q2）SCI 期刊论文投稿

---

## 目录

1. [项目现状总结](#一项目现状总结)
2. [核心创新点与差异化定位](#二核心创新点与差异化定位)
3. [目标期刊分析](#三目标期刊分析)
4. [论文叙事主线](#四论文叙事主线)
5. [详细论文大纲](#五详细论文大纲)
6. [实验执行计划](#六实验执行计划)
7. [时间线里程碑](#七时间线里程碑)
8. [风险与备选策略](#八风险与备选策略)
9. [所需资源与前置条件](#九所需资源与前置条件)
10. [论文投稿检查清单](#十论文投稿检查清单)
11. [参考文献方向整理](#十一参考文献方向整理)

---

## 一、项目现状总结

### 1.1 项目定义

M3-PI Guard 是一个面向**工具型大语言模型智能体（tool-using LLM agent）**的本地提示注入安全靶场、运行时防护框架和可复现实验平台。

**核心安全关注**：模型在接触不可信文档、工具返回值、记忆或结构化内容后，是否提出并执行了未经授权的工具动作，以及运行时监控器能否在动作产生副作用前进行 `ALLOW`、`ASK` 或 `DENY` 决策。

### 1.2 架构总览

```
攻击样本 / 公共基准任务
         │
         v
paper_runtime_view：只投影可信请求、可信应用上下文、工具 Schema；
                   隔离离线答案字段
         │
         v
策略编译器 ──> TaskPolicyManifest（非 Oracle）
         │
         v
大模型智能体 ──> ActionProposal + 参数来源追踪
         │
         v
运行时监控器（五模块可消融）
  策略 + 来源 + 时序 + 数据流 + 确认
         │
  ALLOW / ASK / DENY
         │
         v
本地工具沙箱 ──> 运行日志 / 追踪 / Manifest
         │
         v
指标 / 统计 / 图表 / 仪表盘 / 准入审计
```

### 1.3 两条证据线

| 证据线 | 状态 | 数据规模 | 定位 |
|---|---|---|---|
| **E0–E17 历史线** | ✅ 18/18 完成 | 300 条标准数据，4 模型 × 6 条件 × 3 重复 | 工程成熟度证据 + 附录 |
| **paper-v1 升级线** | ⚠️ 核心机制已实现，正式证据大量缺失 | M3-v2 1,500 条，AgentDojo 726 条，InjecAgent | 论文主表来源 |

### 1.4 Q2 就绪度审计

| 指标 | 分数 | 状态 |
|---|---|---|
| 原始分 | 66.0 / 100 | — |
| 封顶分 | 60.0 / 100 | 被 5 个硬门禁封顶 |
| goal_80_met | ❌ false | 差 20 分 |
| goal_90_met | ❌ false | 差 30 分（投稿级） |
| 就绪度区间 | paper_upgrade_in_progress | — |

### 1.5 Q2 就绪度 10 个标准分项明细

| # | 标准 | 满分 | 已得 | 状态 |
|---|---|---|---|---|
| 1 | 历史 E0–E17 工程证据 | 12 | 12 | ✅ complete |
| 2 | 非 Oracle 运行时机制与形式化 | 10 | 10 | ✅ complete |
| 3 | 独立确认性盲测 | 15 | 2 | ❌ blocked（封顶 65） |
| 4 | 公共基准正式结果 | 15 | 3 | ❌ blocked（封顶 75） |
| 5 | 源码支撑强基线 | 15 | 6 | ❌ blocked（封顶 70） |
| 6 | 模型覆盖 | 10 | 6 | ⚠️ partial（封顶 60） |
| 7 | 自适应查询预算攻击 | 10 | 4 | ❌ blocked（封顶 60） |
| 8 | 统计、人工复核与图表 | 8 | 8 | ✅ complete |
| 9 | 可复现性与冻结 | 8 | 8 | ✅ complete |
| 10 | 论文稿件包与叙事 | 7 | 7 | ✅ complete |
| **总计** | | **100** | **66** | |

### 1.6 五大硬门禁详情

#### 门禁 1：公共基准正式矩阵（封顶 75 分）

- **当前**：0/84 cells 正式完成，0/74,760 case-runs
- **冻结状态**：已完成（`public_benchmark_formal_freeze_v2.json`）
- **ToolFilter 726 条**：✅ 已完成并准入
- **Transformers 检测器**：75 完成 / 1 失败 / 650 缺失（CPU 内存不足）
- **InjecAgent 正式单元**：未完成

#### 门禁 2：强基线（封顶 70 分）

| 基线 | 状态 | 说明 |
|---|---|---|
| AgentDojo ToolFilter | ✅ formal-ready | 726/726，0 失败 |
| PromptGuard | ✅ formal-ready | 3,280 条检测器正式推理，仅检测器表 |
| Task Shield v1.3-v1.6 | ❌ 路线关闭 | v1.6 P4: TCR 2/6, p95 为 comparator 的 15.175 倍 |
| Progent v1.4 | ❌ 延迟门禁失败 | ASR 0/4, utility 3/4, p95 为 comparator 的 11.07 倍 |
| CaMeL v3 P3 | ❌ 诊断证据 | ASR 0/4, TCR 0/4, p95 159.003s |
| IPIGuard | ❌ 资格未完成 | DAG schema 兼容性问题，1/2 完成 |
| Transformers 检测器 | ❌ 资源不足 | CPU 内存 OOM |

#### 门禁 3：独立盲测（封顶 65 分）

- **当前**：候选数据和保管记录均缺失
- **状态**：`blocked_missing_candidate`
- **工具包**：已准备，但不能开发者自行填充

#### 门禁 4：前沿 API 模型（封顶 60 分）

- **当前**：0/2 厂商 slot
- **OpenAI**：占位符 Token
- **Anthropic**：占位符 Token

#### 门禁 5：自适应攻击（封顶 60 分）

- **80 任务冻结**：已完成
- **桩后端预检**：已完成（资格/诊断级）
- **正式模型运行**：未启动

### 1.7 已完成的工程资产

- ✅ 18/18 E0-E17 实验，300 条标准数据
- ✅ 两人真人分层抽样盲审（360/360 一致）
- ✅ 13 张图 + HTML 技术报告
- ✅ 修复 V2：12/12 工程验收通过
- ✅ 非 Oracle `research_runner`（`m3_core/research_runner.py`，532 行）
- ✅ `TaskPolicyManifest`、`ActionProposal`、`GuardDecision`、`ProvenanceEvent`
- ✅ 自动策略编译（`compile_task_policy` + `compile_generic_task_policy`，`m3_core/policy_compiler.py`，792 行）
- ✅ 1,500 条 M3-v2 数据集（900 attack + 600 benign）
- ✅ AgentDojo/InjecAgent adapter 与 84-cell pending ledger
- ✅ PromptGuard 下载、真实推理和仅检测器正式实验（3,280 条输入）
- ✅ 2 个 8B 本地论文模型（m3-paper-qwen3-8b-v1 + m3-paper-llama31-8b-v1）
- ✅ 80-task 自适应 MCTS freeze/runner/monitor
- ✅ 预注册、统计、十图计划、证据索引和 Q2 自定义审计脚本

---

## 二、核心创新点与差异化定位

### 2.1 五大创新点

#### 创新 1：非 Oracle 授权范式（★★★★★ 最强创新点）

**问题**：现有大量 LLM Agent 防御评估中，Guard（运行时监控器）可以直接读取每个测试样本的标准授权答案（如 `authorized_actions`、`requires_tool`、`expected_answer`），这相当于考试时试卷上印了标准答案。历史 E4 实验直接证明了这一点——policy-only 条件与 full Guard 的效果非常接近，说明检测器和数据流模块的效果被授权信息稀释。

**我们的方法**：
- Guard 只能从可信用户请求文本 + 工具 Schema + 可信应用上下文编译权限范围
- 评估字段（`authorized_actions`、`requires_tool`、攻击族等）在 `paper_runtime_view` 阶段即被剥离
- `FORBIDDEN_ONLINE_CASE_FIELDS` 包含 17 个禁止进入在线状态的字段
- 策略编译器（`policy_compiler.py`）自动拒绝 evaluator/gold 字段

**论文中的论证策略**：
- 系统性审查现有防御评估中 oracle 授权的普遍性（这本身可能是一个独立贡献）
- 通过授权 regime 对比实验（exact/auto_compiled/broad/ambiguous）量化授权不确定性对安全指标的影响
- 论证不解决 oracle 问题的防御评估逻辑上不成立

#### 创新 2：参数级来源追踪（★★★★☆）

**差异化**：现有来源追踪工作（如 CaMeL）是粗粒度的（整个文档标记为不可信），我们是**参数级**的——每个工具参数的每个叶子值都有独立的来源事件。

**实现细节**（`m3_guard/provenance.py`，284 行）：
- `ProvenanceEvent` 记录：参数路径、来源类型（trusted_user / untrusted_document / untrusted_tool_output / model_generated）、信任级别、值哈希、数据标签
- `infer_argument_provenance()` 对每个叶子参数值在可信请求、可信上下文、不可信文档、工具输出和记忆中逐一匹配
- **信任来源优先原则**：同一字面量在可信和不可信源中同时出现时，优先归因为可信源（防止攻击者通过重复用户已批准的目标来洗白）
- `provenance_uses_instruction_field()` 专门检测 body/content/instruction/message 等字段中的注入
- 目标字段（to/path/endpoint）和选择器字段（query/search/filter）的区分处理

#### 创新 3：五模块可消融运行时监控器（★★★★☆）

**五个模块**（`m3_guard/runtime_monitor.py`，431 行）：
1. **policy**（必选）：工具规则、参数约束、允许的参数来源
2. **provenance**：参数来源检查，不可信内容不能创建权限
3. **temporal**：前置动作时序约束（如"先读后发"）
4. **dataflow**：敏感数据标签流向控制（如"private 标签数据不能流向 attacker 地址"）
5. **confirmation**：权限扩大需独立确认接口

**消融设计**：`FULL_RUNTIME_MODULES` 和 `guard_modules: frozenset[str]` 参数支持任意模块组合，每个模块的独立贡献可被严格测量。

#### 创新 4：三态 ALLOW/ASK/DENY 决策（★★★☆☆）

**与二元 allow/deny 的关键区别**：
- `ASK` 不是 `DENY`——它承认动作可能服务任务，但需要独立确认或权限扩张
- 区分「危险动作」和「可能需要但超出当前权限的动作」
- `ASK` 率和确认负担作为独立评估指标
- 权限收缩自动执行（`narrow_manifest`），权限扩大必须经过独立确认接口（`expand_manifest` + `ApprovalRecord`）

#### 创新 5：证据工程学方法论（★★★☆☆）

**在 LLM 安全领域独特的方法论贡献**：
- 严格的证据分层：smoke / preflight / qualification / diagnostic / historical / post-hoc / formal / confirmatory
- 冻结-哈希-准入三位一体
- 失败保留原则：解析失败、超时、拒答均留在分母
- 消融实验的预注册和 claim-evidence 对齐审计
- 可复现性：一条命令重建主表和所有图表

### 2.2 与最新文献的详细对比

| 维度 | CaMeL (2025) | StruQ (2024) | Instruction Hierarchy (2024) | PromptGuard (2024) | AgentDojo ToolFilter (2024) | **M3-PI Guard** |
|---|---|---|---|---|---|---|
| 运行时监控 | ✅ | ❌（编译时） | ❌（模型内部） | ❌（仅检测器） | ✅ | ✅ |
| 非 Oracle 授权 | 部分 | ✅ | 部分 | N/A | 部分 | ✅ **系统化** |
| 来源追踪粒度 | 文档级 | ❌ | system/user 角色 | ❌ | 粗粒度 | ✅ **参数级** |
| 三态决策 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ ALLOW/ASK/DENY |
| 消融实验框架 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ **五模块可消融** |
| 多语言攻击覆盖 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ 中/英/拼音/混合 |
| 自适应攻击评估 | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ 已冻结未运行 |
| 公共基准 | ✅ AgentDojo | ❌ | ❌ | ❌ | ✅ AgentDojo | ⚠️ 框架已就绪 |
| 证据工程学 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ 冻结-哈希-准入 |
| 可用性评估 | 有 | 部分 | 有 | ❌ | ✅ | ✅ TCR+ASK+确认负担 |

**核心差异化总结**：M3-PI Guard 是**当前已知文献中唯一一个同时具备非 Oracle 授权、参数级来源追踪、可消融多模块运行时监控和三态决策的系统**。

---

## 三、目标期刊分析

### 3.1 首选目标：Computers & Security (Elsevier)

| 属性 | 详情 |
|---|---|
| ISSN | 0167-4048 |
| 影响因子（2024） | ~5.0 |
| CCF 分级 | B |
| 审稿周期 | 通常 4-6 个月 |
| 收稿范围 | 信息安全技术、系统安全、网络安全、AI 安全应用 |
| 文章类型偏好 | 实证研究、系统性评估、防护框架 |
| 为何适合 M3-PI Guard | (1) 偏好系统工程完善的实证研究 (2) 接受方法论文 (3) 有多篇 LLM 安全相关发表 (4) 看重可复现性 |

### 3.2 备选 1：Journal of Information Security and Applications (JISA, Elsevier)

| 属性 | 详情 |
|---|---|
| ISSN | 2214-2126 |
| 影响因子（2024） | ~4.3 |
| CCF 分级 | B |
| 收稿范围 | 安全应用、隐私保护、AI 安全 |
| 为何适合 | 与 Computers & Security 定位相近，审稿周期相近 |

### 3.3 备选 2：IEEE Transactions on Information Forensics and Security (TIFS)

| 属性 | 详情 |
|---|---|
| ISSN | 1556-6013 |
| 影响因子（2024） | ~6.5 |
| CCF 分级 | A |
| 竞争激烈度 | 极高 |
| 为何备选 | 如果公共基准结果显著优于强基线，可尝试；否则风险过大 |

### 3.4 备选 3：ACM Transactions on Privacy and Security (TOPS)

| 属性 | 详情 |
|---|---|
| ISSN | 2471-2566 |
| 影响因子（2024） | ~4.0 |
| CCF 分级 | A |
| 为何备选 | 需要更强的形式化安全性质证明，当前 P1-P7 是 proof sketch 而非 formal proof |

### 3.5 推荐投稿策略

1. **第一投稿**：Computers & Security
2. **如果被拒**：JISA
3. **如果实验结果远超预期（公共基准上显著最优）**：TIFS

---

## 四、论文叙事主线

### 4.1 建议标题（三选一）

**选项 A（学术型）**：
> "Beyond Oracle Authorization: Provenance-Aware Runtime Monitoring for Tool-Using LLM Agents Under Prompt Injection"

**选项 B（问题驱动型，推荐）**：
> "When Defenses See the Answer Key: The Case for Non-Oracle Runtime Authorization in LLM Agent Prompt Injection Defense"

**选项 C（系统型）**：
> "M3-PI Guard: A Non-Oracle, Provenance-Aware Runtime Authorization Framework for Securing Tool-Using LLM Agents"

**推荐选项 B**——问题驱动型标题更容易引起审稿人兴趣，且「Answer Key」比喻形象化地传达了 oracle 问题的本质。

### 4.2 一句话论点

> 现有 LLM Agent 提示注入防御的评估被标准答案泄露（oracle authorization）系统性高估；本文提出并实现了一种不依赖黄金授权的运行时监控框架，从可信输入编译策略、追踪参数来源、执行三态决策，并通过系统消融和多基准实验刻画了安全—效用—延迟的完整权衡图景。

### 4.3 五个核心研究问题（RQ）

**RQ1（授权不确定性）**：在不向 Agent 或 Guard 暴露逐样本标准授权答案时，安全性还能保留多少？

**RQ2（策略粒度-效用权衡）**：精确、自动编译、宽泛、含糊和错误授权策略如何改变 ASR、TCR、FPR、ASK 率和确认负担？

**RQ3（模块独立贡献）**：在 policy-only 之外，provenance、temporal、dataflow 和 confirmation 模块是否各自产生可测量的独立安全增益？

**RQ4（自适应鲁棒性）**：静态攻击下的防御效果能否抵抗防御感知的自适应黑盒攻击（不同查询预算下）？

**RQ5（跨模型泛化）**：上述规律是否在小型本地模型（4B）、中等开源模型（7-14B）和前沿 API 模型之间保持一致？

### 4.4 贡献声明的精准边界

**可以声称的**：
- ✅ 首次系统性揭示并量化 LLM Agent 防御评估中的 oracle 授权问题
- ✅ 提出并实现了一个非 Oracle 的运行时监控架构，包含参数级来源追踪和三态决策
- ✅ 建立了可消融、可复现的实验框架（含冻结、哈希、准入的完整证据链）
- ✅ 在自制数据、公共基准和自适应攻击三个层次上完成了安全—效用评估

**不能声称的**：
- ❌ 不得声称「显著优于最先进方法」（除非正式公共基准结果在统计上显著支持）
- ❌ 不得声称「首次提出来源追踪」（应定位为首次将参数级来源追踪系统性地应用于 LLM Agent 授权）
- ❌ 不得将 PromptGuard 检测器 recall 等同于端到端 Agent 安全
- ❌ 不得将自动封存留出集（sealed_holdout）称为独立盲测
- ❌ 不得将历史 E0-E17 作为确认性论文主结论

---

## 五、详细论文大纲

### Section 1: Introduction（约 2000 词）

**1.1 背景与问题**
- LLM Agent 的快速部署：RAG、代码执行、邮件/日历/API 调用
- 提示注入是 Agent 安全的首要威胁
- 工具型 Agent 的安全问题本质不同于 chatbot：决策会产生真实的工具副作用

**1.2 Oracle 授权问题——本文的核心批判性论点**
- 现有防御评估的常见做法：Guard 可以在线读取 `authorized_actions`、`requires_tool`、目标动作、预期答案
- 历史 E4 的关键发现：当 policy-only 条件下效果与 full Guard 接近时，说明检测器/数据流模块的贡献被授权信息稀释
- 直观类比：考试卷上印了标准答案 → 任何防御看起来都很有效
- 这是一个被领域系统性忽视的方法论缺陷

**1.3 本文贡献**
- (C1) 非 Oracle 运行时监控架构
- (C2) 参数级来源追踪
- (C3) 五模块可消融设计
- (C4) M3-v2 1,500 条多语言数据集
- (C5) AgentDojo + InjecAgent 公共基准实验
- (C6) 自适应查询预算攻击评估
- (C7) 完整的实验框架（冻结/哈希/准入）

**1.4 论文结构导航**

---

### Section 2: Background & Related Work（约 2500 词）

**2.1 提示注入攻击分类学**
- 直接注入 vs 间接注入（参考论文 #1: Systematic Review）
- 攻击的五层空间模型：嵌入空间 → 词元空间 → 词空间 → 句子空间 → 探索空间
- 工具辅助利用（Tool-Assisted Exploitation）
- 自适应攻击与逆向缩放效应
- 多语言/跨模态注入

**2.2 Agent 安全防御**
- 输入检测器（PromptGuard, Llama Guard, transformers PI detector）
- 安全提示工程（safe prompt, spotlighting, prompt sandwich）
- 指令层次强制（Instruction Hierarchy）
- 运行时防护（CaMeL, ToolFilter, AgentGuard）
- 信息流控制（Progent, FIDES）
- 沙箱与权限控制

**2.3 授权在 Agent 安全中的角色**
- 权限模型：RBAC、最小权限原则
- 工具调用的授权粒度：任务级 → 工具级 → 参数级
- 当前研究空白：授权不确定性、非 Oracle 评估

**2.4 评估方法与基准**
- AgentDojo, InjecAgent, ToolEmu
- ASR/TCR/FPR 等指标的局限性
- 统计方法：Wilson CI, McNemar, Bootstrap, Holm 校正

**2.5 本文定位**
- 填补「非 Oracle 授权 + 参数级来源追踪 + 五模块消融」的交叉空白

---

### Section 3: Threat Model（约 1500 词）

**3.1 系统模型**
- Agent 架构：LLM + 工具集 + 运行时监控器
- 可信边界：用户请求、应用上下文、工具 Schema
- 不可信边界：外部文档、工具输出、记忆、对话历史

**3.2 攻击者能力**
- 控制/污染不可信内容（文档、网页、JSON 字段、工具输出、记忆候选）
- 不了解 Guard 内部状态（黑盒）
- 自适应场景下可查询目标模型
- 不能直接修改系统 prompt、策略编译器或监控器

**3.3 受保护资产**
- 用户任务意图和授权范围
- 本地 sensitive canary（合成金丝雀标记）
- 工具副作用（文件写、邮件发、API 调用、代码执行）

**3.4 条件性安全假设**
- 所有副作用工具经过 RuntimeMonitor
- 可信/不可信输入可以正确区分
- 策略编译器不消费不可信内容
- 独立确认接口不被 attacker 控制

**3.5 形式化安全性质（P1-P7, 参考 `formal_security_properties_v1.md`）**
- P1: 完全中介（Complete Mediation）
- P2: 不可信内容不能创建权限
- P3: 权限扩大必须独立确认
- P4: 时序约束执行
- P5: 敏感数据流控制
- P6: 不可信 selector 限制
- P7: 审计完整性

---

### Section 4: M3-PI Guard Design（约 3500 词）

**4.1 设计原则**
- DP1: 非 Oracle——Guard 不消费评估字段
- DP2: 最小权限——从可信请求编译最窄的权限范围
- DP3: 单调权限——自动路径只能收缩
- DP4: 来源追踪——每个参数的每个值都可溯源
- DP5: 失败安全——不确定时 ASK 而非 ALLOW

**4.2 TaskPolicyManifest：非 Oracle 策略编译**
- 数据结构：manifest_id, rules, temporal_constraints, dataflow_constraints, approvals, hash chain
- 编译输入：仅 trusted_user_request + tool_schemas + trusted_app_context
- `compile_task_policy()`: 从请求文本提取路径、邮件、端点，生成具体工具规则
- `compile_generic_task_policy()`: 用于未知工具集的非 Oracle 领域推理编译器
- 授权 Regime 光谱：exact → auto_compiled → broad → ambiguous → erroneous

**4.3 Provenance：参数级来源追踪**
- ProvenanceEvent 结构：argument_path, source_type, trust_level, value_sha256, data_labels
- 推断算法：在可信请求/上下文/不可信文档/工具输出/记忆中逐一匹配
- **信任来源优先原则**：同一字面量出现在可信和不可信源中时，优先归因可信源
- instruction_field 检测（`_INSTRUCTION_FIELD_RE`）：检测 body/content/instruction/message 等字段中的注入
- 目标字段 vs 选择器字段的区分处理
- 数据标签传递（如 private/sensitive canary）

**4.4 RuntimeMonitor：三态决策引擎**
- ALLOW 的完整条件：规则匹配 + 参数约束满足 + 来源许可 + 时序正确 + 数据流无冲突
- ASK 的触发条件：工具在规则外但可能服务任务、参数超出约束范围、权限扩大需要确认
- DENY 的触发条件：不可信内容引入新目标/工具、前置动作缺失、敏感数据流向禁止目标
- 五模块的执行顺序和决策优先级
- ASK 恢复流程：approval_callback → expand_manifest → 重新评估

**4.5 实现概览**
- 技术栈：Python, Ollama (OpenAI-compatible API), JSONL logging
- 工具沙箱：mock 实现（邮件→本地 outbox, API→mock JSON, 代码→不执行）
- Agent Loop：max_steps=6, 解析失败保留, 工具执行成功检测
- 关键代码度量：runtime_monitor.py (431 行), provenance.py (284 行), task_policy.py (303 行), policy_compiler.py (792 行), research_runner.py (532 行)

**4.6 安全性质的实现映射**
- 对 P1-P7 的 proof sketch 如何映射到代码实现
- 假设违反的后果
- 非形式化证明的局限性

---

### Section 5: Experimental Design（约 2500 词）

**5.1 研究问题与实验映射**
- RQ1-RQ5 到具体实验配置的映射表

**5.2 数据集**
- M3-v2：1,500 条（900 attack + 300 benign legal-tool + 300 benign no-tool），9 攻击族 × 6 语言变体
- AgentDojo：726 任务（workspace/travel/Slack）
- InjecAgent：1,054 任务
- 独立盲测 600 条（如可用）

**5.3 模型**
- 本地 8B：m3-paper-qwen3-8b-v1, m3-paper-llama31-8b-v1
- 前沿 API：GPT-4o-mini, Claude Haiku（待配置）
- 历史模型（附录）：4 个小模型

**5.4 防御条件（≥6 个）**
1. M3 no defense（baseline）
2. M3 safe prompt only
3. M3 policy-only（单模块消融）
4. M3 policy + provenance
5. M3 policy + provenance + temporal + dataflow
6. M3 full（五模块）
7. PromptGuard detector-only（强基线）
8. AgentDojo ToolFilter（强基线）

**5.5 评估指标**
- **安全指标**：ASR（攻击成功率）、UTR（未授权工具调用率）、DSR（敏感数据泄露率）、BSR（阻断率）
- **效用指标**：TCR（正常任务完成率）、合法工具 TCR
- **效率指标**：ASK 率、确认负担、Guard 延迟（p50/p95）、端到端延迟
- **统计方法**：Wilson 95% CI、McNemar 检验、聚类 Bootstrap（10,000 次）、Holm 校正

**5.6 实验协议**
- 冻结协议：数据集版本、模型版本、种子、温度、max_steps 全部固定
- 恢复协议：断点续跑、原子日志落盘
- 失败保留：解析失败、超时、拒答均留在分母
- 准入协议：覆盖检查 + 失败检查 + hash 检查 + 显式准入

---

### Section 6: Results（约 3500 词）

**6.1 Oracle 授权的影响（RQ1）**
- 对比 exact policy vs auto_compiled policy 的 ASR/TCR
- 展示 oracle 信息如何改变安全-效用曲线
- 子分析：不同攻击族下 oracle 影响的异质性

**6.2 授权 Regime 敏感性（RQ2）**
- 5 种授权 regime 的安全-效用 Pareto 图
- ASK 率和确认负担的变化

**6.3 模块消融（RQ3）**
- 森林图（forest plot）：每个模块的独立效应量和 95% CI
- Policy-only vs full 的配对比较
- 哪些攻击族中 provenance/confirmation 贡献最大

**6.4 自适应鲁棒性（RQ4）**
- ASR vs 查询预算（100/500/2000）曲线
- 防御在自适应压力下是否退化

**6.5 跨模型泛化（RQ5）**
- 模型 × 防御热力图
- 攻击族 × 语言热力图
- 本地 8B vs 前沿 API 的一致性/差异

**6.6 公共基准结果**
- AgentDojo 各 workspace 完整对比
- InjecAgent 结果
- 与 ToolFilter, PromptGuard 的头对头比较

**6.7 延迟与成本**
- Guard 延迟 p50/p95 ECDF 图
- 各模块的延迟分解

**6.8 失败分析**
- 失败类型堆叠柱状图：解析失败 / 超时 / 拒答 / 最大步数 / 其他

---

### Section 7: Discussion（约 2000 词）

**7.1 主要发现总结**
**7.2 Policy-only 主导性分析**：为什么 provenance/dataflow 的增益可能不及预期
**7.3 ASK 的双刃剑效应**：降低误拦但也增加确认负担
**7.4 小模型限制与 API 模型展望**
**7.5 局限性**：合成数据、8GB GPU、非 machine-checked、仅文本模态
**7.6 实际部署建议**

---

### Section 8: Conclusion（约 500 词）

---

### 图表计划（8-10 张图 + 4 张表）

| # | 图表类型 | 内容 | 对应 Section |
|---|---|---|---|
| Fig. 1 | 架构图 | 威胁模型和信任边界 | Sec 3 |
| Fig. 2 | 架构图 | M3-PI Guard 完整数据流 | Sec 4 |
| Fig. 3 | 散点/线图 | 安全-效用 Pareto（多授权 regime） | Sec 6.2 |
| Fig. 4 | 森林图 | 模块消融效应量与 CI | Sec 6.3 |
| Fig. 5 | 折线图 | 自适应 ASR vs 查询预算 | Sec 6.4 |
| Fig. 6 | 热力图 | 模型 × 防御 | Sec 6.5 |
| Fig. 7 | 热力图 | 攻击族 × 语言 | Sec 6.5 |
| Fig. 8 | ECDF/箱线图 | Guard 延迟分布 | Sec 6.7 |
| Fig. 9 | 堆叠柱状图 | 失败类型分布 | Sec 6.8 |
| Fig. 10 | 条形图 | 数据集构成（描述性） | Sec 5.2 |
| Tab. 1 | — | 数据集详细统计 | Sec 5.2 |
| Tab. 2 | — | 公共基准完整矩阵结果 | Sec 6.6 |
| Tab. 3 | — | 强基线对比总表 | Sec 6.6 |
| Tab. 4 | — | 消融实验结果（含 CI） | Sec 6.3 |

---

## 六、实验执行计划

### 6.1 阶段一：研究叙事定稿（第 1-2 周）🔴 当前阶段

**任务 1.1：文献综述系统更新**
- [ ] 精读 17 篇参考论文，提取每篇的方法类型、攻击面、评估指标、主要发现
- [ ] 使用学术搜索引擎检索 2025 年顶会/顶刊中 LLM Agent 安全的最新论文
- [ ] 重点关键词：`prompt injection` + `agent` + `defense` / `runtime monitor` / `provenance tracking`
- [ ] 建立文献矩阵（paper_id, 方法名, 年份, 会议/期刊, 是否含 oracle 信息, 来源追踪粒度, 评估指标）
- [ ] 输出：`docs/paper_plan/literature_matrix.md`

**任务 1.2：Oracle 授权问题系统性审查**
- [ ] 系统审查 ≥20 篇 Agent 安全/防御论文的评估方法
- [ ] 判断每篇 Guard 是否在在线阶段接收了逐样本授权信息
- [ ] 描述 oracle 信息的具体形式（`authorized_actions`, `requires_tool`, 目标工具, 预期答案 等）
- [ ] 输出：`docs/paper_plan/oracle_authorization_survey.md`
- [ ] **这是一个可能产生独立贡献的发现**

**任务 1.3：论文大纲定稿**
- [ ] 按本计划 Section 1-8 完成章节级大纲
- [ ] 确定每节的段落数和关键论点
- [ ] 确定图表的具体规格
- [ ] 输出：`docs/paper_plan/paper_outline_v1.md`

**任务 1.4：目标期刊投稿要求确认**
- [ ] 下载 Computers & Security 最新 Author Guidelines
- [ ] 确认页数/词数限制、格式模板、数据政策
- [ ] 输出：`docs/paper_plan/target_journal_requirements.md`

---

### 6.2 阶段二：强基线补齐（第 3-6 周）

**目标**：达到 5 个正式就绪的源码支撑强基线 → 封顶分从 60 升至 70

**任务 2.1：IPIGuard 修复与准入**
- [ ] 只读审计当前 DAG schema 兼容性问题根因
- [ ] 修复 `KeyError('function_name')` 和 empty DAG 问题
- [ ] 完成 P3 8-case 资格 → P4 16-case → G3 gate
- [ ] 若通过所有 gate，完成 AgentDojo 726-case 正式运行
- [ ] 输出：`outputs/paper_upgrade_v1/baselines/ipiguard_source_backed_*`

**任务 2.2：CaMeL v3 继续/停止决策**
- [ ] 只读审计 CaMeL v3 P3 的 TCR 0/4 根因
- [ ] 评估是否可以通过 prompt/profile 调整改善效用
- [ ] 做出决策：继续 CaMeL（定义新 P4/P5）或转向 FIDES
- [ ] 输出：`docs/paper_plan/camel_v3_go_nogo_review.md`

**任务 2.3：FIDES / 替代基线调研与适配**
- [ ] 若 CaMeL 路线关闭，调研 FIDES 或其他信息流控制基线
- [ ] 评估兼容性和适配成本
- [ ] 执行与 Task Shield/Progent 相同的资格分级流程（P0→P3→P4→G3）
- [ ] 输出：`protocols/paper_upgrade_v1/fides_*` 或类似

**任务 2.4：Transformers 检测器资源解决**
- [ ] 评估更大会话中/机器上的可行性
- [ ] 若不可行，设计限制输入长度的替代适配器（充分披露差异）
- [ ] 完成 AgentDojo 官方检测器正式运行
- [ ] 输出：`outputs/paper_upgrade_v1/baselines/agentdojo_transformers_pi_detector_*`

**任务 2.5：基线注册表更新**
- [ ] 更新 `baseline_registry.json`
- [ ] 更新 `strong_baseline_formal_readiness_audit_v1.json`
- [ ] 重新运行 `audit_q2_readiness`
- [ ] 目标：封顶分 60 → 70（强基线门禁通过）

---

### 6.3 阶段三：公共基准正式结果（第 7-10 周）

**目标**：AgentDojo + InjecAgent 公共基准核心 cells 完成 → 封顶分从 70 升至 75

**任务 3.1：AgentDojo M3 正式矩阵**
- [ ] 3 workspace × M3 防御条件（≥5 条件）
- [ ] `--max-steps 6` 防止代理循环超时
- [ ] 每个 cell 完成后立即运行 monitor 和完整性检查
- [ ] 输出：`outputs/paper_upgrade_v1/public_benchmarks/agentdojo_m3_*`

**任务 3.2：InjecAgent 正式单元**
- [ ] 完成 InjecAgent adapter 的正式 1,054 条运行
- [ ] M3 full / policy-only / no defense 三种条件
- [ ] 输出：`outputs/paper_upgrade_v1/public_benchmarks/injecagent_m3_*`

**任务 3.3：M3-v2 内部基准正式运行**
- [ ] M3-v2 1,500 条的 paper-v1 正式运行
- [ ] 2 模型 × 5+ 防御条件
- [ ] 输出：`outputs/paper_upgrade_v1/internal_benchmarks/m3_v2_*`

**任务 3.4：公共基准结果分析与准入**
- [ ] 运行统一分析器，生成指标 CSV
- [ ] 执行完整性审计
- [ ] 运行准入脚本
- [ ] 目标：封顶分 70 → 75（公共基准门禁通过）

---

### 6.4 阶段四：独立盲测与自适应攻击（第 11-14 周）

**目标**：独立盲测封存 + 自适应攻击正式曲线 → 原始分 ≥ 80

**任务 4.1：独立 600 条盲测**
- [ ] 决定盲测生成策略（外部人员 / 独立程序不同种子 / 公共数据集）
- [ ] 由第三方生成并封存
- [ ] 记录保管链：生成时间、SHA-256、保管人、封存时间
- [ ] 盲测准入后运行 M3 full vs baselines 正式实验
- [ ] 输出：`m3_attacks/cases/paper_v1/m3_v2_independent_blind_candidate.jsonl`

**任务 4.2：自适应查询预算攻击**
- [ ] 启动 80 任务 × 3 预算（100/500/2,000）× 2 模型的正式运行
- [ ] 使用现有 MCTS runner
- [ ] 生成 ASR vs 查询预算曲线
- [ ] 输出：`outputs/paper_upgrade_v1/adaptive_mcts_budget_v1/`

**任务 4.3：准入与封顶分更新**
- [ ] 独立盲测准入
- [ ] 自适应攻击正式结果分析
- [ ] 目标：原始分 ≥ 80

---

### 6.5 阶段五：前沿模型与最终分析（第 15-17 周）

**任务 5.1：前沿 API 模型接入**
- [ ] 配置 OpenAI API Key（脱敏）
- [ ] 配置 Anthropic API Key（脱敏）
- [ ] 执行单条脱敏冒烟测试
- [ ] 执行 ≥40 条正式实验（或预算允许的最小样本量）
- [ ] 输出：`outputs/paper_upgrade_v1/frontier_api/`

**任务 5.2：最终统计分析**
- [ ] 聚类 Bootstrap（10,000 次重采样）
- [ ] McNemar 检验
- [ ] Holm 校正
- [ ] 生成全部 10 张图表

---

### 6.6 阶段六：论文写作与投稿（第 18-25 周）

**任务 6.1：初稿写作（第 18-21 周）**
- [ ] Section 1-2（Introduction + Related Work）
- [ ] Section 3-4（Threat Model + Design）
- [ ] Section 5-6（Experimental Design + Results）
- [ ] Section 7-8（Discussion + Conclusion）
- [ ] Abstract + Keywords + 参考文献

**任务 6.2：内部复核（第 22 周）**
- [ ] Claim-Evidence 逐条对齐审计
- [ ] 统计复算
- [ ] 图表一致性检查

**任务 6.3：格式排版与投稿（第 23-25 周）**
- [ ] 按目标期刊模板排版
- [ ] Cover Letter
- [ ] 补充材料组织
- [ ] 提交

---

## 七、时间线里程碑

```
周次   日期范围        阶段                  关键产出                      封顶分变化
───────────────────────────────────────────────────────────────────────────────
 1-2   07/23-08/06   研究叙事定稿           论文大纲 v1, 文献矩阵          60
 3-6   08/07-09/03   强基线补齐             5 个基线 formal-ready         60→70
 7-10  09/04-10/01   公共基准正式结果        AgentDojo+InjecAgent 完成     70→75
11-14  10/02-10/29   独立盲测 + 自适应攻击   盲测封存, 自适应曲线          75→80+
15-17  10/30-11/19   前沿模型 + 最终分析    所有统计+图表完成              80+
18-21  11/20-12/11   论文初稿写作           全文 8 章完稿                  80+
22     12/12-12/18   内部复核               Claim-Evidence 对齐通过        80+
23-25  12/19-01/08   格式排版 + 投稿        提交至目标期刊                 80+
```

---

## 八、风险与备选策略

### 8.1 技术风险矩阵

| # | 风险 | 概率 | 严重度 | 应对策略 | 触发条件 |
|---|---|---|---|---|---|
| R1 | 公共基准上 M3 效果不如 ToolFilter | 30% | 高 | 论文定位转为系统性实证研究，重点论述 oracle 问题和方法论贡献 | M3 ASR > ToolFilter ASR |
| R2 | 高延迟无法优化 | 60% | 中 | 如实报告延迟作为 tradeoff；讨论优化空间（并行化、缓存、近似匹配） | 所有基线延迟 ≤100ms 而 M3 ≥200ms |
| R3 | 独立盲测始终无法获得 | 30% | 中 | 使用 M3-v2 sealed_holdout（600 条封存留出集）替代，充分披露非独立性 | 第 12 周末仍无候选数据 |
| R4 | 前沿 API 授权/预算不足 | 40% | 中 | 最少完成 2 家 API 各 ≥40 条实验，在论文中声明小样本局限 | API Key 不可用或预算耗尽 |
| R5 | 强基线始终凑不齐 5 个 | 40% | 中 | 将「基线兼容性困难」作为发现之一；使用自建强条件（safe prompt, spotlighting, prompt sandwich）作为替代基线 | 第 6 周末 formal-ready < 5 |
| R6 | CaMeL/FIDES/IPIGuard 全部不可用 | 20% | 高 | 使用自建条件补足 5 个基线：ToolFilter + PromptGuard + safe prompt + spotlighting + prompt sandwich | 第 4 周末 ≥3 个外部基线失败 |
| R7 | 安全-效用 tradeoff 完全无用 | 15% | 极高 | 承认负面结果，保留方法论贡献，重新定位论文 | P1 中型门禁失败 |
| R8 | 消融实验无独立模块贡献 | 35% | 中 | 修正结论为「来源/时序/数据流的贡献在评估范围内未达统计显著」，讨论未来方向 | Bootstrap CI 包含零 |

### 8.2 P1 中型门禁实验——关键决策点

在进行全量正式矩阵之前，**必须先通过中型门禁**。

**实验条件**（约 40-80 条配对任务，1 个强模型）：
1. no defense
2. safe prompt / spotlighting
3. PromptGuard（仅检测器）
4. 1 个可运行的运行时基线
5. M3 policy-only
6. M3 full

**通过标准（必须全部满足）**：
- M3 明显降低 ASR（相对 no defense）
- Clean/legitimate-tool TCR 相对最强基线下降 ≤ 5pp
- ASK/拒绝率没有退化为 deny-all
- Full vs policy-only 至少一个模块有独立非零增益
- 0 个 unexplained operational failure

**如果不通过** → 论文转为授权泄露/授权误差的系统性实证研究，不宣称防御领先。

---

## 九、所需资源与前置条件

### 9.1 硬件资源

| 资源 | 当前 | 需要 | 备注 |
|---|---|---|---|
| GPU | 8GB VRAM | 8GB 可满足顺序运行 | 无法并行，序列化运行 |
| CPU 内存 | ~16GB | ≥32GB 建议 | Transformers 检测器需要 |
| 磁盘 | 已有 1.1GB outputs | 预计新增 10-20GB | 正式矩阵产出 |
| 网络 | 本地回环 | 需要互联网 | 仅阶段五 API 调用 |

### 9.2 软件和配置

- [x] Python 项目环境（`E:\M3_PI_Guard_runtime`）
- [x] Ollama 本地模型服务
- [x] PromptGuard 环境
- [ ] OpenAI API Key（从占位符改为真实值）
- [ ] Anthropic API Key（从占位符改为真实值）
- [ ] CaMeL/Progent/IPIGuard 隔离环境（部分已有）

### 9.3 前置条件清单

- [ ] Ollama 服务确认停止，需要时重新启动
- [ ] `config/project.local.env` 中的 API Token 配置
- [ ] `external/` 中所有强基线源码检出的完整性确认
- [ ] 理解 6 个 pytest 失败（Progent/Task Shield 历史 hash 版本化冲突，非本次引入）
- [ ] E17 测试的 Ollama 环境快照问题解决（13 个测试因 Ollama 自动重启未完成）

---

## 十、论文投稿检查清单

### 10.1 投稿前 Claim-Evidence 对齐

对每个 contribution claim，确认：
- [ ] 对应的正式实验结果存在且可追溯
- [ ] 统计检验支持（CI 不含零 / p < 0.05 经 Holm 校正）
- [ ] 冻结 manifest SHA-256 与论文中报告的一致
- [ ] 失败、超时、解析错误均在分母中
- [ ] 所有基线在相同 freeze 条件下评估
- [ ] 没有 diagnostic/smoke/preflight 结果伪装为正式结果

### 10.2 可复现性检查

- [ ] 一条命令从冻结 manifest 重建主表
- [ ] 一条命令重新生成所有图表
- [ ] 所有依赖的精确版本已记录（manifest + protocol）
- [ ] 补充材料包含代码、冻结、协议、原始日志索引

### 10.3 格式与合规

- [ ] 符合目标期刊的页数/词数限制
- [ ] 参考文献格式正确（Elsevier Harvard 或 IEEE 格式）
- [ ] 所有图分辨率 ≥300dpi
- [ ] Cover Letter 说明贡献和创新
- [ ] 利益冲突声明 + 数据可用性声明

### 10.4 安全纪律

- [ ] 不提交包含真实 Token 的配置文件
- [ ] 不提交模型权重
- [ ] 不提交真实邮箱/API 的发件箱内容
- [ ] 不提交可识别个人身份的人工评审数据

---

## 十一、参考文献方向整理

### 11.1 参考论文库（17 篇已有 dual-translated PDF）

| # | 论文 | 核心方向 | 在本文中的主要用途 |
|---|---|---|---|
| 1 | A Systematic Review of Prompt Injection Attacks | 系统综述 | Related Work 骨架，攻击分类学 |
| 2 | Analysis of LLMs Against Prompt Injection and Jailbreak | 实证分析 | Oracle 问题审查材料 |
| 3 | A Systematic Literature Review on LLM Defenses | 防御综述 | 基线比较 |
| 4 | BI-GRPO: Bidirectional Optimization for Jailbreak Backdoor | 攻击优化 | 攻击面扩展 |
| 5 | Bypassing LLM Guardrails: Evasion Against Detection Systems | 绕过攻击 | 自适应攻击相关 |
| 6 | Dialogue Injection Attack: Context Manipulation | 对话注入 | 多轮攻击覆盖 |
| 7 | Hidden Malicious Goal Into Benign Narratives: Logic Chain | 逻辑链注入 | 攻击多样性 |
| 8 | ON JAILBREAKING QUANTIZED LANGUAGE MODELS | 量化模型攻击 | 模型鲁棒性 |
| 9 | Prompt Injection Attacks in LLMs and AI | 注入攻击综述 | Related Work |
| 10 | Red Teaming the Mind of the Machine | 红队评估 | 评估方法论讨论 |
| 11 | Sockpuppetting: Jailbreaking Without Optimization | 输出操控 | 自适应攻击 |
| 12 | Soft Begging: Prompt Tuning based Shielding | Prompt 调优防御 | 基线方法比较 |
| 13 | SQL Injection Jailbreak | 结构化注入 | 攻击族 |
| 14 | THE ATTACKER MOVES SECOND: Stronger Adaptive Attacks | **自适应攻击** | 自适应评估设计核心参考 |
| 15 | VII: Visual Instruction Injection | 视觉注入 | 局限性讨论 |
| 16 | Visual Contextual Attack: Image-Driven Context Injection | 多模态注入 | 未来工作方向 |
| 17 | Virtual Context: Enhancing Jailbreak with Special Token | 特殊 Token 攻击 | Token 层面攻击面 |

### 11.2 需要补充检索的关键方向

| 方向 | 检索关键词 | 预期补充数量 |
|---|---|---|
| Oracle-Free Evaluation | "oracle-free" "non-oracle" "authorization leakage" "prompt injection evaluation" | 5-10 篇 |
| AgentDojo 相关工作 | "AgentDojo" "tool filter" "PI detector" | 5 篇 |
| InjecAgent 相关工作 | "InjecAgent" "indirect prompt injection benchmark" | 5 篇 |
| 2025 顶会最新 | "USENIX Security 2025" "NDSS 2025" "CCS 2025" "prompt injection agent" | 10-15 篇 |
| 来源追踪 | "provenance tracking" "LLM agent" "data lineage" "information flow control" | 5-10 篇 |
| 运行时监控 | "runtime monitor" "LLM agent" "guardrail" "policy enforcement" | 5-10 篇 |

### 11.3 需要重点精读的前沿论文（2024-2025）

1. **CaMeL** (Debenedetti et al., 2025) — 最接近的运行时防御方法，直接比较对象
2. **AgentDojo** (Debenedetti et al., 2024) — 本文使用的公共基准
3. **InjecAgent** (Zhan et al., 2024) — 本文使用的公共基准
4. **Instruction Hierarchy** (Wallace et al., 2024; Wu et al., 2025) — 模型内部替代方案
5. **StruQ** (Chen et al., 2024) — 结构化查询防御
6. **PromptGuard** (Meta, 2024) — 检测器基线
7. **FIDES** — 信息流控制基线
8. **"SoK: The Attack Surface of Agentic AI"** (Dehghantanha & Homayoun, 2025) — 系统化攻击面
9. **"From Prompt Injections to Protocol Exploits"** (Hamouda et al., 2025) — MCP 安全
10. **"From Secure Agentic AI to Secure Agentic Web"** (Deng et al., 2025) — 运行时供应链安全

---

## 附录 A：关键命令行参考

```powershell
# 只读状态审计
python -m experiments.paper_v1.benchmarks.plan_q2_formal_execution
python -m experiments.paper_v1.benchmarks.audit_q2_readiness
python -m experiments.paper_v1.benchmarks.plan_q2_to_80_actions

# 桩后端回归验证
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend stub --defense-modes baseline,full_guard --out-dir outputs/runs/smoke --run-prefix smoke --max-steps 5

# 本地 Ollama 冒烟
python scripts/smoke_ollama_models.py --model m3-paper-qwen3-8b-v1:latest --output outputs/paper_upgrade_v1/local_model_smoke.json

# paper-v1 正式运行
python -m experiments.paper_v1.run_matrix --help
python -m experiments.paper_v1.analyze_matrix --help
python -m experiments.paper_v1.build_figures --help

# 完整工程验证
python scripts/audit_project_conventions.py --check
python -m pytest -q
python -m experiments.validate_registry
python scripts/verify_historical_evidence.py
powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/verify.ps1

# 配置检查
python scripts/check_project_config.py --config config/project.local.env
```

## 附录 B：重要文件路径索引

| 用途 | 路径 |
|---|---|
| **本文（完整计划）** | `文档资料/deepseek.md` |
| 项目完整综述 | `docs/项目完整综述.md` |
| 项目移交报告 | `docs/项目移交报告.md` |
| 论文叙事线 | `protocols/paper_upgrade_v1/paper_storyline_v1.md` |
| 实现状态 | `protocols/paper_upgrade_v1/implementation_status.md` |
| Q2 就绪度审计 | `protocols/paper_upgrade_v1/q2_readiness_audit_v1.json` |
| Q2 执行计划 | `protocols/paper_upgrade_v1/execution/q2_formal_execution_plan_v1.json` |
| 模型注册表 | `protocols/paper_upgrade_v1/model_registry_v2.json` |
| 基线注册表 | `protocols/paper_upgrade_v1/baseline_registry.json` |
| 公共基准冻结 | `protocols/paper_upgrade_v1/public_benchmark_formal_freeze_v2.json` |
| 确认性预注册 | `protocols/paper_upgrade_v1/paper_v1_confirmatory_preregistration_freeze_v1.json` |
| 论文证据索引 | `protocols/paper_upgrade_v1/paper_v1_evidence_index_v1.json` |
| 独立盲测准入 | `protocols/paper_upgrade_v1/m3_v2_independent_blind_admission_audit_v2.json` |
| 形式化安全性质 | `protocols/paper_upgrade_v1/formal_security_properties_v1.md` |
| 历史实验注册表 | `experiments/registry.json` |
| 历史最终 manifest | `outputs/experiments/final_analysis/manifest.json` |

## 附录 C：术语缩写表

| 缩写 | 全称 | 含义 |
|---|---|---|
| ASR | Attack Success Rate | 攻击成功率 |
| TCR | Task Completion Rate | 正常任务完成率 |
| UTR | Unauthorized Tool-call Rate | 未经授权工具调用率 |
| DSR | Data-exfiltration Success Rate | 敏感数据泄露率 |
| BSR | Blocking Success Rate | 危险行为阻断率 |
| FPR | False Positive Rate | 误拦率 |
| PI | Prompt Injection | 提示注入 |
| CI | Confidence Interval | 置信区间 |
| RQ | Research Question | 研究问题 |
| SOTA | State Of The Art | 最先进水平 |
| RAG | Retrieval-Augmented Generation | 检索增强生成 |
| MCP | Model Context Protocol | 模型上下文协议 |
| MCTS | Monte Carlo Tree Search | 蒙特卡洛树搜索 |

---

> **本文是 M3-PI Guard 项目二区论文的完整执行计划。**
> **下一步：完成阶段一（研究叙事定稿），产出论文大纲 v1 和文献矩阵。**
>
> 计划版本：v1.0
> 创建时间：2026-07-23
> 下次审阅：2026-07-30（一周后检查阶段一进度）
