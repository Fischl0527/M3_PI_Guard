# 对齐来源与授权：大语言模型智能体的双图防御
## Aligning Provenance with Authorization: A Dual-Graph Defense for LLM Agents

**论文作者**：Peiran Wang  
**研究机构**：加州大学洛杉矶分校 (UCLA)  
**发表出处**：arXiv:2605.26497v1 (2026)  
**项目开源**：https://github.com/PeiranWang/AuthGraph  

---

### 摘要 / Abstract

**【中文精译】**  
大语言模型（LLM）智能体正被迅速部署于现实世界中以执行多步骤复杂工作流，包括访问私有数据库、处理个人电子邮件以及代表用户执行受特权保护的操作。然而，由于 LLM 缺乏将受信任的用户系统指令与非受信任的第三方外部数据（如网页正文或邮件附件）进行严格物理隔离的能力，智能体极其脆弱地暴露在间接提示注入（Indirect Prompt Injection, IPI）攻击之下。一旦智能体读取包含对抗性指令的数据，攻击者便能劫持其控制流并诱导其执行未经授权的恶意行为。

为此，我们提出了 **AUTHGRAPH**——一种将数据来源追踪（Data Provenance Tracking）与授权控制（Authorization Control）深度融合的双图防御系统。AUTHGRAPH 构建并维护两个对偶图结构：其一为**授权图（Authorization Graph）**，基于用户初始意图在安全且隔离的规划上下文中形式化推导得到，精确界定了达成目标所需的合法工具拓扑与参数约束；其二为**来源图（Provenance Graph）**，在智能体运行时跨多步工具交互实时追踪每个输入参数的因果数据血统。在每个关键动作分发执行前，AUTHGRAPH 执行严格的双图对齐检查（Alignment Check），确保动作的调用路径与参数来源完全溯源至用户授权意图而非外部注入。此外，系统支持动态重规划（Replanning）以优雅处理合法的良性分支偏差。在 AgentDojo 等基准评测中，AUTHGRAPH 实现了超过 95% 的综合攻击拦截率，且保持了极高的良性任务完成率，为化解智能体间接提示注入难题提供了兼具理论严密性与工程可落地性的双图防护范式。

**【英文原文】**  
LLM agents are rapidly being deployed for multi-step workflows, accessing private data and performing privileged actions. However, because LLMs lack strict separation between trusted system instructions and untrusted external data (e.g., webpages or email attachments), agents are severely vulnerable to Indirect Prompt Injection (IPI) attacks. When reading adversarial data, attackers hijack control flow to perform unauthorized operations.

We propose **AUTHGRAPH**, a defense system integrating data provenance tracking with authorization control. AUTHGRAPH constructs and maintains two dual graph structures: an **Authorization Graph** derived from user intent in an isolated, clean planning context specifying legitimate tool and parameter constraints; and a **Provenance Graph** tracking runtime causal data lineage across multi-step tool interactions. Before executing any critical action, AUTHGRAPH performs strict dual-graph alignment checking, guaranteeing that tool invocations and parameter flows trace back to user authorization rather than adversarial injection. On benchmarks including AgentDojo, AUTHGRAPH achieves over 95% attack mitigation while preserving high benign task utility.

---

### 1 引言与问题定义 / 1 Introduction & Problem Definition

**【中文精译】**  
大语言模型智能体正在迅速扩展其应用边界，通过自主规划并调用各种外部应用程序接口（API），协助人类处理从日常个人事务（如邮件整理、日程管理）到关键业务系统（如代码仓库维护、金融支付与自动化运维）等多元任务。在这些场景中，智能体通常被赋予极高的系统特权，可以对文件系统、数据库或第三方平台执行读取甚至破坏性的写入操作。

然而，间接提示注入攻击对基于 LLM 的自主智能体构成了根本性的安全威胁（Greshake et al., 2023）。在典型的 IPI 场景中，攻击者并不直接向智能体发送提示词，而是将恶意指令潜伏预置于智能体在执行任务过程中必然读取的非受信外部数据源中（例如网页内容、顾客评论、外部邮件正文或共享文件）。当智能体检索并处理这些数据时，由于其无法在认知层面严格区分“作为数据的文本”与“作为控制流的指令”，注入的对抗性指令极易颠覆智能体的原有规划，迫使其背离真实用户的意图，转而执行攻击者指定的恶意动作（如窃取私有凭证、删除关键数据或向未授权第三方转账）。

现有针对间接提示注入的防御机制普遍存在显著缺陷：
1. **纯提示词软性防御**：在提示中追加警告或分隔标记极易被自适应攻击绕过；
2. **黑盒安全分类器**：无法解释拦截决策，存在高假阴性率；
3. **粗粒度工具白名单**：无法识别“工具本身合法、但调用参数被注入篡改”的参数劫持攻击。

本文的核心洞见在于：**防御间接提示注入的关键不在于在内容层面无休止地识别恶意词汇，而在于在因果执行层面严格核验每一个动作及其参数的数据来源（Provenance）是否与用户的初始授权（Authorization）相一致**。

**【英文原文】**  
Autonomous LLM agents plan and invoke external APIs, managing emails, financial transactions, and codebase repositories. However, indirect prompt injection (IPI) poses a fundamental threat (Greshake et al., 2023): untrusted data read by the agent contains hidden adversarial instructions that hijack control flow.

Existing defenses fail: prompt engineering is easily bypassed by adaptive attacks; black-box classifiers exhibit high false-negative rates; and coarse tool whitelists miss parameter-tampering attacks where the tool is valid but its arguments are injected.

Our core insight is that **defending against indirect prompt injection requires verifying that every action and parameter's provenance aligns with initial user authorization**, rather than endlessly inspecting text for malicious keywords.

---

### 2 AUTHGRAPH 双图架构设计 / 2 System Architecture

**【中文精译】**  
AUTHGRAPH 引入了对偶图范式，通过在干净上下文中生成的“授权图”与运行时动态捕获的“来源图”之间进行严格的双图同构对齐：

#### 2.1 授权图 (Authorization Graph, $G_{\text{auth}}$)
当接收到用户指令 $u$ 时，AUTHGRAPH 首先在一个**干净且与外部非受信数据完全隔离的提示上下文**中运行授权规划器。此时尚未执行任何外部工具，生成的授权图完全不受对抗性数据的污染。授权图 $G_{\text{auth}} = (V_{\text{auth}}, E_{\text{auth}})$ 规定了预期的工具调用节点序列以及关键参数的数据来源策略（如必须源自用户显式指定 `user_prompt`，或前序工具的干净输出 `observation_direct`）。

#### 2.2 运行时来源图 (Provenance Graph, $G_{\text{prov}}$)
在智能体实际与环境交互的过程中，系统动态捕获其实际执行的工具调用序列，并构建来源图 $G_{\text{prov}} = (V_{\text{prov}}, E_{\text{prov}})$。每当外部只读工具返回非受信文本时，系统为其打上来源标签；当后续动作提议调用新工具时，追踪器解析其传入参数的具体来源，记录参数值是由模型从非受信文本中直接抽取复制，还是源自用户受信任的初始输入。

#### 2.3 双图对齐检查 (Dual-Graph Alignment Checking)
在智能体分发每一个关键写操作之前，对齐检查器执行两阶段严格核验：
- **阶段一：工具名称与步骤对齐 (Tool Name Alignment)**：检查实际调用的工具是否与授权图中当前步骤预期一致。如果智能体因受到注入干扰而试图调用完全未授权的工具（例如在购物任务中突然调用向外发信工具），该动作被立即拒绝。
- **阶段二：参数来源对齐 (Parameter Source Alignment)**：即使工具名称匹配，检查器进一步核验各个参数的实际来源路径是否符合授权图中声明的策略。若关键参数（如转账收件人或目标仓库名）的数据流来自未受信任的外部观察而非用户指令，系统判定发生参数劫持攻击并强制阻断。

#### 2.4 动态自适应重规划 (Dynamic Replanning)
当环境出现良性交互偏差（如文件不存在需要辅助查找）且当前数据未表现出对抗特征时，系统在受限工具列表内生成局部子图，保证任务连续性。

**【英文原文】**  
AUTHGRAPH features a dual-graph paradigm:
1. **Authorization Graph ($G_{\text{auth}}$)**: Constructed in an isolated, clean prompt context from initial user instructions, specifying expected tool steps and allowed parameter source policies (`user_prompt`, `observation_direct`).
2. **Provenance Graph ($G_{\text{prov}}$)**: Tracks runtime tool invocations and causal data lineage across multi-step interactions.
3. **Dual-Graph Alignment**: Before executing any write-action, the checker enforces two layers:
   - *Layer 1 (Tool Name)*: Rejects unexpected tool calls injected by adversaries;
   - *Layer 2 (Parameter Source)*: Rejects parameter tampering when argument values originate from untrusted observations.
4. **Dynamic Replanning**: Supports benign deviation recovery via localized subgraph regeneration.

---

### 3 实验评测与结果分析 / 3 Experiments & Findings

**【中文精译】**  
我们在权威的 **AgentDojo**（覆盖个人办公、电子商务、代码协作、金融交互等多元领域）上开展系统评估：

#### 3.1 攻击防御表现（表 1）
- **基线未防御模型**：攻击成功率普遍超过 70%；
- **启发式防御**（System Prompting、Sandwiching）：在多步复合注入下防御率仅在 40%~60%；
- **AUTHGRAPH 防御**：在各类复杂攻击变体下均实现了 **超过 95% 的极高综合防御拦截率**，同时在洁净样本上的任务效用保持率达到 **90% 以上**。

#### 3.2 多层防御机制贡献消融（图 2）
- **阶段一（工具名称层）**：拦截了约 **55%** 的粗暴型工具劫持攻击；
- **阶段二（参数来源层）**：深度捕获了 **40% 以上** 的隐蔽型高级伪装攻击（工具名称完全合法，但关键参数被外部注入篡改）。这一结果强力证明了：缺乏参数级来源追踪的单纯工具白名单防御存在巨大的致命安全死角！

#### 3.3 运行开销
- 端到端双图构建与检查引入的额外延迟小于模型单次响应时间的 **4%**，具备极佳的实时可用性。

**【英文原文】**  
We evaluated on the comprehensive **AgentDojo** benchmark:
- **Defense Rate (Table 1)**: Baselines suffer >70% attack success. Prompt-based defenses achieve only 40%–60% defense. AUTHGRAPH achieves **>95% defense rate** while retaining **>90% benign task utility**.
- **Layer Breakdown (Figure 2)**: Tool-name checking intercepts ~55% of overt attacks, whereas parameter source checking intercepts >40% of subtle parameter-tampering attacks where the tool itself is legitimate.
- **Overhead**: Dual-graph checking adds <4% latency relative to overall LLM inference.

---

### 4 核心结论与启示 / 4 Conclusion & Takeaways

**【中文精译】**  
AUTHGRAPH 证实：**通过将数据来源图与授权图进行因果执行对齐，能够从根本上破解大模型“代码与数据不分”的固有顽疾**。它表明未来的智能体安全架构必须超越单纯的词法过滤，深入到“参数角色、数据血统与意图对齐”的结构化因果维度。这一理念与 M3 PI Guard 项目中的来源追踪及参数契约机制形成了强烈的理论互证。

**【英文原文】**  
AUTHGRAPH demonstrates that aligning runtime provenance with a clean authorization graph fundamentally mitigates indirect prompt injection. Shifting defense from text filtering to causal parameter lineage provides the definitive blueprint for secure agent architectures.
