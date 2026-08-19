# M3-PI Guard paper-v2 文献矩阵

版本：`2026-07-28.v2-critical-refresh`  
检索截止：2026-07-28  
范围：工具型 LLM Agent 的间接提示注入、运行时授权、最小权限、来源/信息流、确认机制、评测方法与自适应攻击。

## 证据分级

- `PR`：已在会议或期刊正式发表，按同行评审工作处理。
- `PP`：预印本或公开稿，不把其数值当作已同行评审结论。
- `BM`：公开基准或大规模测量工作；仍同时标注其发表状态。
- `AU`：paper-v2 online-state 源码审计的高优先级对象。
- 论文页、出版社页或官方 proceedings 优先于二手页面。仅有预印本时直接链接 arXiv。

## 直接相关工作

| ID | 年份/状态 | 工作 | 核心对象与方法 | 与 M3 的关系 | paper-v2 用法 |
|---|---|---|---|---|---|
| L01 | 2026 / PR | [VIGIL: Defending LLM Agents Against Tool-Stream Injection via Verify-Before-Commit](https://aclanthology.org/2026.acl-long.443/) | verify-before-commit；SIREN 含 959 条工具流注入 | 最接近的同行评审运行时结构化防御 | 核心基线；`AU` |
| L02 | 2025 / PR | [DRIFT: Dynamic Rule-Based Defense with Injection Isolation for Securing LLM Agents](https://proceedings.neurips.cc/paper_files/paper/2025/hash/77f3b26c7907aa27b207df9b9d43f29a-Abstract-Conference.html) | 动态规则、控制/数据流约束与记忆隔离 | 覆盖 M3 的 temporal/dataflow 叙事边界 | 核心基线；`AU` |
| L03 | 2025 / PR | [The Task Shield: Enforcing Task Alignment to Defend Against Indirect Prompt Injection in LLM Agents](https://aclanthology.org/2025.acl-long.1435/) | 验证工具调用是否与用户目标一致 | 与 policy-only 条件直接可比 | 核心基线；`AU` |
| L04 | 2026 / PR | [Securing the Tool Layer: A Threat Taxonomy and Runtime Defense Framework for Model Context Protocol Deployments](https://aclanthology.org/2026.acl-industry.58/) | 在 MCP 工具层实施安全检查 | 与 M3 的工具调用拦截层相邻 | 补充基线候选；`AU` |
| L05 | 2026 / PR | [ToolSafe: Enhancing Tool Invocation Safety of LLM-based agents via Proactive Step-level Guardrail and Feedback](https://aclanthology.org/2026.findings-acl.1850/) | 工具调用安全与风险感知 | 覆盖参数/工具安全的邻近方向 | 相关工作及适配候选；`AU` |
| L06 | 2026 / PR+BM | [PIArena: A Platform for Prompt Injection Evaluation](https://aclanthology.org/2026.acl-long.1533/) | Agent 提示注入评估平台 | 可用于检查跨环境评测语义 | 评测设计参考；`AU` |
| L07 | 2025 / PR | [StruQ: Defending Against Prompt Injection with Structured Queries](https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe) | 以结构化查询分离控制与数据 | 代表模型/接口层防御，不等价于运行时授权 | 补充基线；`AU` |
| L08 | 2025 / PR | [Contextual Agent Security: A Policy for Every Purpose](https://research.google/pubs/context-is-key-for-agent-security/) | 生成上下文相关、可供人验证的即时策略 | 与上下文授权及确认机制高度相关 | 设计边界与讨论；`AU` |
| L09 | 2024 / PR+BM | [AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents](https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html) | 97 个任务、629 个安全测试用例的动态环境 | paper-v2 的主公共基准 | 主基准；`AU` |
| L10 | 2024 / PR+BM | [InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents](https://aclanthology.org/2024.findings-acl.624/) | 1,054 个工具型 Agent 间接注入测试用例 | 补充泛化基准 | 外部有效性；`AU` |
| L11 | 2025 / PR+BM | [WASP: Benchmarking Web Agent Security Against Prompt Injection Attacks](https://proceedings.neurips.cc/paper_files/paper/2025/hash/1c9818387f5dd0a0bc151214660f059d-Abstract-Datasets_and_Benchmarks_Track.html) | Web Agent 场景的注入风险与任务效用 | 扩展场景，不作为初期强制主基准 | 讨论与后续泛化；`AU` |
| L12 | 2025 / PR+BM | [Security Challenges in AI Agent Deployment: Insights from a Large Scale Public Competition](https://proceedings.neurips.cc/paper_files/paper/2025/hash/73368bc7644c054b5bcc6490a8f2fb1c-Abstract-Datasets_and_Benchmarks_Track.html) | 22 个模型、180 万次攻击的大规模红队测量 | 支持必须包含强攻击与策略违规终点 | 威胁模型和外部证据 |
| L13 | 2024 / PR | [Formalizing and Benchmarking Prompt Injection Attacks and Defenses](https://www.usenix.org/conference/usenixsecurity24/presentation/liu-yupei) | 形式化提示注入并系统比较攻击/防御 | 支持固定威胁模型、攻击/防御配对 | 方法与指标参考；`AU` |
| L14 | 2025 / PR | [Bypassing LLM Guardrails: An Empirical Analysis of Evasion Attacks against Prompt Injection and Jailbreak Detection Systems](https://aclanthology.org/2025.llmsec-1.8/) | 展示检测/护栏的规避风险 | 支持 detector-only 不能代表执行安全 | 自适应攻击动机 |
| L15 | 2025 / PR | [Memory Injection Attacks on LLM Agents via Query-Only Interaction](https://proceedings.neurips.cc/paper_files/paper/2025/hash/42a97bbd9844d2bf68596730af80bcdf-Abstract-Conference.html) | 针对长期记忆的注入攻击 | 覆盖 temporal/memory 风险边界 | 攻击族与异质性分析 |
| L16 | 2024 / PR | [AgentPoison: Red-teaming LLM Agents via Poisoning Memory or Knowledge Bases](https://proceedings.neurips.cc/paper_files/paper/2024/hash/eb113910e9c3f6242541c1652e30dfd6-Abstract-Conference.html) | 对 Agent 记忆/知识库植毒 | 说明非单轮攻击和来源传播需求 | 补充攻击族 |
| L17 | 2024 / PR | [Watch Out for Your Agents! Investigating Backdoor Threats to LLM-Based Agents](https://proceedings.neurips.cc/paper_files/paper/2024/hash/b6e9d6f4f3428cd5f3f9e9bbae2cab10-Abstract-Conference.html) | Agent 后门威胁 | 与训练/供应链攻击区分 paper-v2 范围 | 非目标边界 |
| L18 | 2026 / PR | [A Systematic Review of Prompt Injection Attacks on Large Language Models: Trends, Taxonomy, Evaluation, Defenses, and Opportunities](https://doi.org/10.1109/ACCESS.2026.3656849) | 综述攻击、缓解与评估 | 用于术语归一，不作为直接机制对照 | Related Work；本地 PDF 已归档 |
| L19 | 2026 / PR | [Prompt Injection Attacks in Large Language Models and AI Agent Systems: A Comprehensive Review of Vulnerabilities, Attack Vectors, and Defense Mechanisms](https://doi.org/10.3390/info17010054) | 面向 LLM/Agent 的提示注入综述 | 用于核对攻击分类和开放问题 | Related Work；本地 PDF 已归档 |
| L20 | 2026 / PR | [AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents](https://doi.org/10.1145/3744916.3764546) | 以轻量 DSL 规定触发、谓词和运行时处置 | 与 M3 的策略执行和确认路径相邻 | ICSE 2026 正式相关工作；适配候选；`AU` |
| L21 | 2026 / PP | [ARGUS: Defending LLM Agents Against Context-Aware Prompt Injection](https://arxiv.org/abs/2605.03378) | 来源感知的上下文决策审计 | 与 M3 的来源影响、上下文授权高度重叠 | 必须讨论；有代码再准入；`AU` |
| L22 | 2026 / PP | [Aligning Provenance with Authorization: A Dual-Graph Defense for LLM Agents](https://arxiv.org/abs/2605.26497) | 对比授权图与参数来源级执行图 | 使“首个参数级来源追踪”不可成立 | 必须做差异表；有代码再准入；`AU` |
| L23 | 2026 / PP | [PlanGuard: Defending Agents against Indirect Prompt Injection via Planning-based Consistency Verification](https://arxiv.org/abs/2604.10134) | 规划级一致性检查 | 与 M3 policy-only 及 goal alignment 相邻 | 相关工作；有代码再准入；`AU` |
| L24 | 2025 / PP | [Progent: Securing AI Agents with Privilege Control](https://arxiv.org/abs/2504.11703) | 可编程最小权限和工具调用控制 | 与权限单调/策略执行直接相关 | 正式候选；`AU` |
| L25 | 2025 / PR | [IPIGuard: A Novel Tool Dependency Graph-Based Defense Against Indirect Prompt Injection in LLM Agents](https://aclanthology.org/2025.emnlp-main.53/) | 使用工具依赖图限制间接注入影响 | 与 M3 dataflow/provenance 相邻 | EMNLP 2025 Main；正式候选；`AU` |
| L26 | 2025 / PP | [Defeating Prompt Injections by Design](https://arxiv.org/abs/2503.18813) | 以能力与信息流隔离数据/控制 | 是 provenance/dataflow 的关键比较 | 正式候选；`AU` |
| L27 | 2025 / PP | [The Attacker Moves Second: Stronger Adaptive Attacks Bypass Defenses Against LLM Jailbreaks and Prompt Injections](https://arxiv.org/abs/2510.09023) | 防御感知、自适应搜索攻击 | 直接要求 paper-v2 不只报告静态攻击 | 正式自适应协议依据；`AU` |
| L28 | 2026 / PP+BM | [The Landscape of Prompt Injection Threats in LLM Agents: From Taxonomy to Analysis](https://arxiv.org/abs/2602.10453) | AgentPI 攻击/防御景观测量 | 用于覆盖攻击族和防御失效模式 | 基准候选；`AU` |
| L29 | 2026 / PP | [Prompt Control-Flow Integrity: A Priority-Aware Runtime Defense Against Prompt Injection in LLM Systems](https://arxiv.org/abs/2603.18433) | 以控制流完整性约束提示与动作 | 与 M3 temporal/control-flow 机制相邻 | 理论边界；`AU` |
| L30 | 2024 / PP | [Defending Against Indirect Prompt Injection Attacks With Spotlighting](https://arxiv.org/abs/2403.14720) | 通过输入转换持续标记来源 | 代表 lightweight/safe-prompt 条件 | 中型实验基线；`AU` |
| L31 | 2024 / PP | [The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions](https://arxiv.org/abs/2404.13208) | 训练模型服从特权指令层级 | 模型内防御，不提供运行时硬授权保证 | Related Work；`AU` |
| L32 | 2025 / PR | [Can Indirect Prompt Injection Attacks Be Detected and Removed?](https://aclanthology.org/2025.acl-long.890/) | 检测并移除外部内容中的注入 | 代表 detector/post-processing 路线 | ACL 2025；detector-only 解释边界；`AU` |
| L33 | 2025 / PR | [Defending against Indirect Prompt Injection by Instruction Detection](https://aclanthology.org/2025.findings-emnlp.1060/) | 利用隐藏状态与梯度检测外部指令 | 需要白盒模型，不等价于 API 运行时授权 | Findings of EMNLP 2025；Related Work |
| L34 | 2025 / PR+BM | [Agent Security Bench (ASB): Formalizing and Benchmarking Attacks and Defenses in LLM-based Agents](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5750f91d8fb9d5c02bd8ad2c3b44456b-Abstract-Conference.html) | 10 类场景、400+ 工具、多种攻击/防御与安全—效用指标 | 提供 AgentDojo 之外的系统性评测参照 | 外部基准候选；`AU` |

## 直接竞争边界

| 维度 | 已有最强相邻工作 | paper-v2 仍可检验的差异 | 禁止使用的说法 |
|---|---|---|---|
| 运行时提交前验证 | VIGIL | 在相同任务上比较 `policy-only` 与完整来源/时序/确认机制 | “首个 verify-before-commit” |
| 控制流/数据流/记忆 | DRIFT、CaMeL、IPIGuard | 以严格配对消融测量各模块独立增益 | “唯一的信息流防御” |
| 目标/规划一致性 | Task Shield、PlanGuard | 检验授权 regime 不确定时的安全—效用变化 | “首个任务一致性验证” |
| 参数来源与授权图 | ARGUS、AuthGraph | 将禁止 evaluator 字段、权限单调与确认负担作为可审计评估对象 | “首个参数级来源追踪” |
| 最小权限 | Progent、Conseca | 证明自动路径只收缩权限，扩张必须独立确认，并量化 ASK 成本 | “首个 Agent 最小权限系统” |
| 控制/数据分离 | StruQ、Spotlighting、Instruction Hierarchy | 比较模型内/提示层缓解与外部硬执行边界 | “提示隔离足以保证执行安全” |
| 评测与攻击 | AgentDojo、InjecAgent、SIREN、WASP、AgentPI、Attacker Moves Second | 统一 unsafe effect、TCR、失败分母和防御感知攻击 | “静态 ASR 足以证明鲁棒” |

## 引用准入规则

1. 写入论文正文前，逐条保存标题、作者、版本、venue、年份和 DOI/稳定 URL。
2. `PP` 不写成“已证明”或“同行评审结果”；复现实验报告所用 commit 和环境。
3. 任何 SOTA、first、only 声明默认禁止；若确需使用，必须由独立 claim–evidence ledger 审批。
4. 指标数值只能引用原文直接报告且语义一致的结果，不把 attack success、unsafe effect、detector recall 混为同一指标。
