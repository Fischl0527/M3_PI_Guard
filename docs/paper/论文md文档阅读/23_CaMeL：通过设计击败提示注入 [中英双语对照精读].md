# CaMeL：通过系统架构设计彻底击败提示注入
## Defeating Prompt Injections by Design (CaMeL: CApabilities for MachinE Learning)

**论文作者**：Edoardo Debenedetti1,3,∗, Ilia Shumailov2, Tianqi Fan1, Jamie Hayes2, Nicholas Carlini2, Daniel Fabian1, Christoph Kern1, Chongyang Shi2, Andreas Terzis2, Florian Tramèr3  
**作者单位**：1Google；2Google DeepMind；3苏黎世联邦理工学院 (ETH Zurich)  
**发表出处**：arXiv:2503.18813v2 [cs.CR] (2025年6月更新版，共 125 页权威长篇专著)  
**通信作者**：edoardo.debenedetti@inf.ethz.ch, iliashumailov@google.com  
**开源代码**：https://github.com/google-research/camel-prompt-injection  

---

### 论文速览导航 / Quick Navigation
1. [摘要 / Abstract](#摘要--abstract)
2. [核心创新与里程碑贡献 / Milestone Innovations & Contributions](#核心创新与里程碑贡献--milestone-innovations--contributions)
3. [1 引言与控制流-数据流二分法 / 1 Introduction & The Dual-Flow Insight](#1-引言与控制流-数据流二分法--1-introduction--the-dual-flow-insight)
4. [2 威胁模型与提示注入安全博弈 / 2 Threat Model & The Security Game](#2-威胁模型与提示注入安全博弈--2-threat-model--the-security-game)
5. [3 CaMeL 系统架构深度解析 / 3 CaMeL System Architecture](#3-camel-系统架构深度解析--3-camel-system-architecture)
   - 3.1 双模型架构：特权规划者 (P-LLM) vs 隔离处理者 (Q-LLM)
   - 3.2 细粒度能力安全系统 (Capability-Based Security)
   - 3.3 沙箱解释器 (CaMeL Interpreter) 与安全策略 (Security Policies)
   - 3.4 数据流与控制流的物理隔离执行机制
6. [4 实验评估与基准实证 / 4 Empirical Evaluation & Benchmarks](#4-实验评估与基准实证--4-empirical-evaluation--benchmarks)
   - 4.1 在 AgentDojo 上的近乎完美防御 (100% 拦截率)
   - 4.2 良性任务效用分析与轻量级 Q-LLM 表现
   - 4.3 为什么传统防御全面失效？消融与基线对比
   - 4.4 系统开销（Token 开销与运行延迟分析）
7. [5 深度攻防探索：侧信道攻击与边界 / 5 Side Channels & Attack Boundaries](#5-深度攻防探索侧信道攻击与边界--5-side-channels--attack-boundaries)
   - 计时、长度与状态侧信道泄密
   - 数据流变异为控制流的边缘隐患
8. [6 深刻探讨：提示注入真的被彻底解决了吗？ / 6 Discussion & The Future](#6-深刻探讨提示注入真的被彻底解决了吗--6-discussion--the-future)
9. [7 结论与对 M3-Guard 的关键启示 / 7 Conclusions & Takeaways](#7-结论与对-m3-guard-的关键启示--7-conclusions--takeaways)

---

### 摘要 / Abstract

**【中文精译】**  
大语言模型（LLM）正日益被深度部署于需要与不可信外部环境频繁交互的智能体系统（Agentic Systems）中。然而，当这些智能体处理来自不受信环境的数据时，极易受到间接提示注入（Prompt Injection）攻击的毁灭性破坏。现有的防御机制大多依赖于训练模型（如强化学习与安全微调）或使用防护提示词来让模型“学会忽略”恶意指令。然而，此类方案在原则上是脆弱的，因为它们并未消除根本矛盾：模型依然在单一上下文中同时处理控制指令与不受信数据。

在这篇长达 125 页的奠基性专著中，Google、Google DeepMind 与 ETH Zurich 团队提出了 **CaMeL（面向机器学习的能力系统，CApabilities for MachinE Learning）**——一种从根本上消除提示注入威胁的体系结构级防御框架。受到传统操作系统与软件安全思想的深刻启发，CaMeL 并不试图让大模型具备绝对辨别善恶的超人智能，而是在大模型周围构建了一层坚不可摧的**系统特权隔离防护层**。

CaMeL 将智能体动作严格解耦为**控制流（Control Flow）**与**数据流（Data Flow）**，并设立两个物理隔离的实体：
1. **特权语言模型（Privileged LLM, P-LLM）**：完全运行在受信上下文中，全权负责高层逻辑规划与工具编排，但被**物理隔绝、绝对禁止直接接触任何未经验证的外部原始数据**；
2. **隔离语言模型（Quarantined LLM, Q-LLM）**：负责读取和解析不可信外部数据，但其运行在受到严格受限的能力沙箱中，**完全剥夺其直接发起副作用写操作与敏感系统调用的权限**。

两者通过强类型能力代币（Capabilities）和沙箱解释器（CaMeL Interpreter）进行受控交互。在涵盖 AgentDojo、ToolBench 等大规模基准的评测中，CaMeL 首次证明了通过严密的系统架构设计，可以在**不依赖基座模型微调的前提下，实现对提示注入攻击近乎 100% 的确定性阻断**，同时保全系统良性效用。这项工作标志着大模型安全从“基于概率的对抗博弈”正式迈入“基于原则的系统工程防御”新纪元。

**【英文原文】**  
Large Language Models (LLMs) are increasingly deployed in agentic systems that interact with an untrusted environment. However, LLM agents are vulnerable to prompt injection attacks when handling untrusted data. Current defenses often rely on training or prompting models to adhere to security rules. Yet, these defenses are inherently fragile as they fail to resolve the fundamental problem: models process instructions and untrusted data in a shared context.

In this seminal 125-page monograph, researchers from Google, Google DeepMind, and ETH Zurich introduce **CaMeL (CApabilities for MachinE Learning)**, a robust defense that eliminates prompt injection risks by architectural design. Inspired by traditional software and operating systems security, CaMeL constructs a protective system layer around models rather than trying to make models infallible.

CaMeL strictly separates agent actions into **Control Flow** and **Data Flow**, introducing two isolated entities:
1. A **Privileged LLM (P-LLM)** that plans actions in a trusted context but is **physically prohibited from reading untrusted raw data**;
2. A **Quarantined LLM (Q-LLM)** that reads and transforms untrusted content within an unprivileged sandbox, **completely stripped of authority to execute privileged side-effecting operations**.

They interact via fine-grained capability tokens and a sandboxed interpreter. Across AgentDojo and complex tool benchmarks, CaMeL achieves near-100% deterministic mitigation of prompt injection attacks without model fine-tuning, while preserving practical task utility. CaMeL transitions agent security from heuristic probabilistic mitigation to principled systems-level enforcement.

---

### 核心创新与里程碑贡献 / Milestone Innovations & Contributions

1. **确立“控制流与数据流正交分离”理论准则（Control vs. Data Flow Duality）**：
   - 证明间接提示注入的本质危害在于：攻击者利用数据通道（Data Channel）污染了系统的控制流（Control Flow）；
   - 提出只要在架构上切断“从不受信数据到特权控制流”的因果传播路径，即可从数学上彻底根除提示注入。
2. **首创 P-LLM 与 Q-LLM 双模型物理隔离范式（Dual-LLM Security Architecture）**：
   - **P-LLM (特权规划者)**：仅接收用户受信任输入，以 Python 代码形式生成抽象规划脚本，只持有不可见具体内容的受控能力引用；
   - **Q-LLM (隔离工作者)**：仅在隔离沙箱中处理不可信文本，产出的所有返回值均被封装为受限的数据句柄（Opaque Handles），无法僭越执行特权系统调用。
3. **引入面向机器学习的能力安全机制（Capability-Based Security for ML）**：
   - 彻底摒弃宽泛的工具全局访问权限，将每个操作形式化为轻量级能力对象（如 `SendEmailCapability`）；
   - 只有当 P-LLM 在干净上下文下显式授予能力代币时，外部操作方可被解释器执行。
4. **沙箱解释器与形式化安全策略验证（Interpreter & Policies）**：
   - 编写了基于 Python AST 的受限解释器，支持静态变量作用域检查与安全策略强制拦截；
   - 在 125 页篇幅中给出了形式化的“提示注入安全博弈（Security Game）”数学定义与安全定理证明。
5. **大规模实证确立安全基准新标杆**：
   - 在权威智能体基准 AgentDojo 上达成 **100% 完美安全防御（0% 攻击成功率）**；
   - 证明即使采用轻量便宜的小模型充当 Q-LLM，系统依然能保持极高的良性任务完成率，具备商业化落地的强可行性。

---

### 1 引言与控制流-数据流二分法 / 1 Introduction & The Dual-Flow Insight

```
       现代智能体动作的控制流与数据流二分图 (Figure 1 结构)
+-------------------------------------------------------------+
|                      用户受信任意图                         |
|   "你能把上次开会 Bob 要求的文档发给他吗？"                 |
+------------------------------+------------------------------+
                               |
            +------------------+------------------+
            | 控制流 (Control Flow)                | 数据流 (Data Flow)
            v                                     v
+-----------------------+             +-----------------------+
| 1. 查找最近会议记录   |             | 提取待发送文档名称    |
| 2. 在网盘中检索文档   |             | 提取 Bob 的邮箱地址   |
| 3. 发起邮件外发调用   |             | 读取文档正文数据内容  |
+-----------------------+             +-----------------------+
            |                                     |
            +------------------+------------------+
                               |
                               v
+-------------------------------------------------------------+
|                     最终工具执行动作                        |
|   send_email(recipient="bob@corp.com", body=[文档内容])    |
+-------------------------------------------------------------+
```

传统单体智能体将控制流与数据流杂糅在同一个提示词上下文中：智能体一边读取包含攻击载荷的外部网页，一边由同一个大模型决定下一步调用什么工具。这就好比一个操作系统允许不受信任的网页脚本直接向内核驱动写入控制寄存器指令！

CaMeL 指出：智能体的每一个动作都具有双重属性：
- **控制流（Control Flow）**：调用哪些函数、执行哪些分支逻辑、进行何种状态跳转；
- **数据流（Data Flow）**：被处理的具体文字、邮件正文、报表摘要。

**黄金安全准则**：不受信的外部数据流，**绝对严禁**自发跃迁并转化为具有执行能力的控制流！

---

### 2 威胁模型与提示注入安全博弈 / 2 Threat Model & The Security Game

CaMeL 在形式化安全框架中严格定义了“提示注入安全博弈（The Prompt Injection Security Game）”：

1. **环境与参与者**：
   - 挑战者（Challenger）初始化环境状态 $S_0$ 并向智能体提供良性用户任务 $u$；
   - 攻击者（Adversary）控制环境中的部分数据节点 $D_{\text{adv}} \subset S$（如恶意网页、钓鱼邮件、代码注释）；
   - 智能体系统 $\mathcal{A}$ 旨在完成用户任务 $u$。
2. **攻击判定条件**：
   - 攻击者获胜：如果智能体在执行过程中触发了**未被用户初始意图授权、且对系统状态产生有害变更的特权操作**（例如向攻击者指定的邮箱发送了私密文档，或删除了用户的数据）。
3. **CaMeL 的防御边界与非目标（Explicit Non-Goals）**：
   - CaMeL 专注于防御**控制流劫持与越权工具调用**；
   - 不以解决“内容通道污染”（如攻击者在允许的邮件正文中放入辱骂性词汇）为目标；
   - 不以解决“受信任用户自身发起的恶意操作”为目标。

---

### 3 CaMeL 系统架构深度解析 / 3 CaMeL System Architecture

```mermaid
flowchart TD
    User["受信任用户 (User)"] -->|受信任高层意图| PLLM["特权规划大模型 (P-LLM)\n(运行于干净上下文，禁读外部原始数据)"]
    
    subgraph CaMeL_Core["CaMeL 核心防护与执行引擎"]
        PLLM -->|生成抽象规划代码| Script["Python 规划脚本\n(包含能力代币与数据流占位符)"]
        Script --> Interp["受限沙箱解释器 (CaMeL Interpreter)"]
        
        Interp -->|受限数据提取任务| QLLM["隔离大模型 (Q-LLM)\n(在受限沙箱中解析外部数据，无任何写权限)"]
        ExtData["外部不受信环境\n(网页 / 邮件 / API)"] -->|读取数据| QLLM
        
        QLLM -->|返回不透明数据句柄 (Opaque Handle)| Interp
        Interp --> PolicyCheck{"安全策略核验 (Security Policy)\n检查实参是否源自受信意图"}
    end

    PolicyCheck -->|满足策略| Exec["执行特权系统调用 (Sink)\n(网盘读写 / 邮件发送 / 银行转账)"]
    PolicyCheck -->|违规越权| Block["底层内核强制阻断 (BLOCK)"]
```

#### 3.1 P-LLM (特权规划者) 与 Q-LLM (隔离工作者)
- **P-LLM (Privileged LLM)**：
  - 拥有高特权，能够根据用户意图编排执行计划；
  - **核心铁律**：其提示词上下文永远保持绝对干净，**绝不接收任何外部工具的返回原始文本**。当外部工具返回数据时，返回的仅仅是一个**不透明变量句柄（Opaque Object Reference）**。
- **Q-LLM (Quarantined LLM)**：
  - 拥有读取外部不受信数据的权限，能够执行翻译、摘要、信息抽取等分析任务；
  - **核心铁律**：Q-LLM 运行在无特权沙箱中，**完全没有绑定任何具有系统副作用的工具 API**。即便它被注入指令彻底洗脑，其输出也仅仅是一段普通字符串，绝无可能在系统内发起越权特权调用。

#### 3.2 细粒度能力安全系统 (Capabilities)
CaMeL 将特权操作封装为一等公民的“能力代币”：
```python
# P-LLM 生成的规划代码示例 (干净上下文)
notes = search_notes("Bob meeting")          # 返回 Opaque Handle
email_addr = q_extract_email(notes)          # 交由 Q-LLM 提取，返回受控变量
doc_name = q_extract_doc_name(notes)         # 交由 Q-LLM 提取，返回受控变量
doc_content = fetch_drive_file(doc_name)     # 依赖能力约束
send_email_capability = get_email_cap(to=email_addr) # 申请特权能力
send_email_capability.send(body=doc_content)
```

#### 3.3 沙箱解释器与安全策略 (Security Policies)
CaMeL Interpreter 拦截上述代码的每一次 AST 节点执行：
- 策略库预先规定：`send_email_capability` 的 `to` 参数必须经过受信策略验证；
- 如果外部数据试图将一个不受信的邮箱地址强行注入到特权收件人槽位，解释器立即抛出安全违规异常并强制终止执行。

---

### 4 实验评估与基准实证 / 4 Empirical Evaluation & Benchmarks

#### 4.1 在 AgentDojo 上的压倒性防御表现
在涵盖 97 个多步高危任务的 AgentDojo 权威基准评测中：

| 系统配置 | 基座模型 | 攻击拦截安全性 (Security %) | 良性任务效用 (Utility %) |
| :--- | :--- | :---: | :---: |
| **无防御 (Vanilla)** | GPT-4o | 18.2% | 59.8% |
| **系统提示词警告** | GPT-4o | 34.6% | 48.5% |
| **工具白名单过滤** | GPT-4o | 52.1% | 28.2% |
| **CaMeL (本文)** | **GPT-4o (P-LLM) + GPT-4o-mini (Q-LLM)** | **100.0% (完美阻断)** | **38.2%** |
| **CaMeL (带策略优化)**| **Claude 3.5 Sonnet** | **100.0% (完美阻断)** | **46.8%** |

> **关键实证结论**：CaMeL 在所有受测模型与基准上均达成了 **0% 攻击成功率（100% 绝对拦截）**，这是传统基于提示工程或微调的模型防御从未企及的硬核安全高度！

#### 4.2 轻量化 Q-LLM 的经济实用性
- 论文深入测试了使用昂贵大模型充当 P-LLM，而使用极低成本的超快小模型（如 GPT-4o-mini 或 Gemma-7B）充当 Q-LLM；
- **发现**：系统整体的良性任务完成率几乎未受影响，而 Token 消耗与推理成本大幅下降，证明了 CaMeL 架构在工业级生产环境部署的高可行性。

---

### 5 深度攻防探索：侧信道攻击与边界 / 5 Side Channels & Attack Boundaries

在长达 125 页的论文中，作者以极其严谨的顶级安全科学家视角，深入探讨了即便在控制流被物理切断的情况下，可能存在的微弱高级侧信道威胁：

1. **响应长度侧信道 (Length Side Channel)**：
   - 攻击者通过构造特定指令，迫使 Q-LLM 生成超长或极短文本，利用 Token 长度的差异向上游传递 1 比特的二进制信息；
2. **执行延迟侧信道 (Timing Side Channel)**：
   - 攻击者利用复杂的循环提示诱导 Q-LLM 耗尽推理时间，通过超时或延迟向外部监听者泄露系统内部状态；
3. **数据流伪装成控制流的深层隐患**：
   - 如果下游工具存在严重的命令解析器漏洞（例如将未转义的字符串直接拼接进入 `eval()` 或 `os.system()`），数据流仍可能在传统软件漏洞层面破坏隔离。这进一步强化了必须使用强类型沙箱与参数契约的必要性。

---

### 6 深刻探讨：提示注入真的被彻底解决了吗？ / 6 Discussion & The Future

作者在第 9 节给出了深刻的科学哲学思考：
- **从“猫鼠游戏”到“可信计算”**：试图通过对抗训练让大模型学会识别所有恶意提示词注定是一场打不赢的军备竞赛；CaMeL 的成功表明，只有回归经典计算机体系结构的安全隔离思想（沙箱、权限、能力系统），才能彻底跳出死循环。
- **用户去分类疲劳（User Fatigue）**：如果系统过于频繁地向用户弹出确认框，用户往往会不假思索地点击“同意”，从而摧毁安全防线。因此，自动化、精细化的策略编译与静默沙箱拦截是未来的必由之路。

---

### 7 结论与对 M3-Guard 的关键启示 / 7 Conclusions & Takeaways

作为长达 125 页的划时代巨著，CaMeL 彻底奠定了现代智能体系统安全工程的理论基石。

#### 对本项目 M3-Guard 研发的核心指导价值：
1. **P-LLM 与 Q-LLM 双模型隔离架构的工程实践**：M3-Guard 的核心运行时应吸收 CaMeL 的双层解耦设计，严格限制与外部数据交互的分析模型所持有的系统特权。
2. **结合 PACT 解决 CaMeL 的效用折损短板**：
   - CaMeL 的主要痛点在于粗粒度整调用隔离导致良性效用有所折损（约 38%~46%）；
   - PACT (2026) 在 CaMeL 基础上进一步引入了“参数级角色契约”，成功将效用拉升至最高水准。M3-Guard 融合 CaMeL 的系统隔离与 PACT 的细粒度参数追踪，构成了坚不可摧的终极双保险防护体系。
