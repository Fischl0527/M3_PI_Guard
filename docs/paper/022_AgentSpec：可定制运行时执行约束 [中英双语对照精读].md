# AgentSpec：面向安全可靠大语言模型智能体的可定制运行时执行约束
## AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents

**论文作者**：Haoyu Wang, Christopher M. Poskitt, Jun Sun  
**研究机构**：新加坡管理大学 (Singapore Management University), 新加坡  
**发表出处**：IEEE/ACM International Conference on Software Engineering (ICSE 2026), arXiv:2503.18666v3, DOI: 10.1145/3744916.3764546  
**项目开源**：https://github.com/haoyuwang99/AgentSpec  

---

### 摘要 / Abstract

**【中文精译】**  
大语言模型（LLM）智能体作为能够自主感知环境、规划行动并执行工具操作的系统，正在软件开发、具身机器人以及自动驾驶等关键领域展现出前所未有的自主能力。然而，这种高度自主性也伴随着严重的安全风险。由于缺乏严格的运行时约束，智能体可能会产生非预期的错误行为，例如破坏性文件系统操作、物理环境损坏或违反交通法规。现有研究主要侧重于事前的离线风险评估或针对特定场景的手工护栏，缺乏一种通用、可解释且可在运行时动态拦截不可信动作的轻量级约束框架。

为此，我们提出了 **AgentSpec**——一种用于对 LLM 智能体实施可定制运行时约束的领域特定语言（DSL）及执行系统。AgentSpec 允许用户以结构化规则的形式定义安全策略，每条规则由触发事件（Trigger）、谓词检查（Check）以及执行处置（Enforce）构成。AgentSpec 能够无缝集成到 LangChain 等主流智能体框架中，在动作执行的关键阶段实施实时监控与干预，支持操作终止、人工介入确认、安全纠正调用以及大模型自我反思等处置手段。

我们在代码执行（RedCode-Exec）、具身智能体（SafeAgentBench）以及自动驾驶（FixDrive）三大典型高风险领域展开了系统评估。结果表明，AgentSpec 拦截了超过 90% 的危险代码执行，在 100% 的测试场景中阻止了自动驾驶违规，并彻底消除了具身任务中的所有物理安全隐患，且仅引入毫秒级轻量开销。此外，我们展示了利用大模型自动生成 AgentSpec 规则的可行性，在少量示例下取得了 95.56% 的高精度判定。

**【英文原文】**  
LLM agents—systems capable of perceiving environments, planning actions, and executing tool operations—are demonstrating unprecedented autonomy across critical domains such as software engineering, embodied robotics, and autonomous driving. However, unconstrained autonomy introduces severe safety risks. Without rigorous runtime constraints, agents may execute unintended actions, causing destructive file modifications, physical damage, or traffic law violations. Existing mitigations focus on pre-execution risk assessments or ad-hoc guardrails, lacking a general, interpretable, and lightweight framework for active runtime enforcement.

We introduce **AgentSpec**, a domain-specific language (DSL) and runtime framework designed for customizable enforcement of LLM agent behaviors. AgentSpec enables users to declare structured safety rules composed of a triggering event, predicate conditions, and enforcements. AgentSpec integrates seamlessly into frameworks like LangChain, intercepting decision pipelines to evaluate proposed actions against safety constraints, supporting actions such as termination, human inspection, safe invocation, and self-reflection.

We evaluated AgentSpec across three critical domains: code execution (RedCode-Exec), embodied agents (SafeAgentBench), and autonomous vehicles (FixDrive). AgentSpec intercepted over 90% of dangerous code calls, prevented 100% of tested traffic violations, and eliminated hazardous actions in 10 categories of embodied tasks, all with millisecond-level overhead. Furthermore, we showed that LLMs can automatically generate accurate AgentSpec rules, achieving 95.56% precision with few-shot prompting.

---

### 1 引言与问题背景 / 1 Introduction & Motivation

**【中文精译】**  
大语言模型驱动的自主智能体代表了人工智能系统的重大范式跃迁。不同于传统的单轮对话模型，LLM 智能体通过与外部环境持续交互、自主规划多步骤目标，并调用外部工具或 API 来完成复杂任务。这些智能体已广泛渗透到各类现实应用中，从自动化软件工程工具、个人数字助手，到具身家庭服务机器人以及复杂自动驾驶控制系统。

然而，赋予智能体执行真实动作的自主权限，也带来了显著的安全、隐私与可靠性风险。与传统的确定性软件系统不同，LLM 智能体具有固有的随机性与不可预测性，其推理过程容易受到幻觉、模糊指令或外部对抗性提示注入攻击的影响。例如：
- 在代码执行智能体中，模型可能会在没有用户授权的情况下执行 `rm -rf` 破坏性删除命令，或者将包含系统凭据的机密文件上传至公共网络服务器；
- 在具身智能体中，机器人可能会将金属器皿误放入微波炉加热，甚至将水泼洒在带电设备上引发火灾与触电事故；
- 在自动驾驶领域，智能体可能会在恶劣天气下超速行驶或闯红灯，造成灾难性的交通事故。

更复杂的是，不同组织和应用场景对智能体风险的容忍度存在巨大差异。例如，在一个不需要严格审批的个人开发沙箱中，智能体自动执行脚本可能是完全被接受的；但在金融交易或医疗用药调整等关键业务环境中，任何未经人类严格复核的高风险操作都属于严重违规。因此，构建一种具备高度表达力、可针对不同环境灵活定制并严格在运行时执行的安全约束机制，已成为推动自主智能体安全落地的当务之急。

**【英文原文】**  
LLM agents represent a paradigm shift in AI, iteratively interacting with environments, planning multi-step trajectories, and invoking external tools to fulfill complex user instructions. These agents are being deployed in automated software development, personal assistants, embodied robotics, and autonomous vehicles (AVs).

However, autonomous execution introduces major risks to safety, privacy, and reliability. LLMs exhibit inherent non-determinism, hallucinations, and susceptibility to prompt injections. In code agents, an unconstrained model may execute destructive commands like `rm -rf` or leak confidential credentials. In embodied agents, robots may place metal in microwaves or pour liquids onto electronics, causing fires and shocks. In AVs, agents may speed through rain or run red lights.

Furthermore, risk tolerance varies across organizations: automated actions acceptable in personal developer environments may be intolerable in healthcare or financial settings. Hence, customizable and formal runtime enforcement is essential.

---

### 2 形式化定义与 AgentSpec 核心设计 / 2 Problem Formulation & DSL Design

**【中文精译】**  
形式化地，智能体运行环境抽象为状态集合 $S$、动作集合 $A$、观察反馈集合 $\Omega$ 以及用户指令空间 $U$。智能体根据用户指令 $u$ 生成执行轨迹 $\tau = \langle s_0 \xrightarrow{a_0} s_1 \xrightarrow{a_1} \dots \xrightarrow{a_{n-1}} s_n \rangle$。

AgentSpec 核心由三元组规则定义：$r = (\eta_r, \mathcal{P}_r, \mathcal{E}_r)$：
1. **触发事件 $\eta_r$ (Triggers)**：
   - 通用事件：`state_change`（状态变化）、`action`（提议调用工具前夕）、`agent_finish`（宣称任务结束）；
   - 特定领域事件：代码执行 `PythonREPL`，机器人 `pick`、`slice`、`cook`，自动驾驶 `red_light_detected`、`entering_roundabout`。
2. **谓词检查 $\mathcal{P}_r$ (Checks)**：
   - 包含逻辑非（`!`）、布尔与/或组合以及参数化谓词。例如 `is_destructive_cmd`（检查破坏性命令）、`is_into_wettable_object`（检查容器是否容水）、`front_vehicle_closer_than(dist)`（车距检测）。
3. **执行处置 $\mathcal{E}_r$ (Enforcements)**：
   - `stop`：直接中止当前动作并将任务标记为完成；
   - `user_inspection`：挂起执行向用户弹出确认窗口，依据用户确认分支决定放行或中止；
   - `invoke_action(params)`：强制注入确定性安全回退动作；
   - `llm_self_examine`：将违规告警反馈回大模型上下文，强制其进行自我反思并重新生成合规方案。

```ebnf
⟨Program⟩ ::= ⟨Rule⟩+
⟨Rule⟩    ::= rule ⟨Id⟩ trigger ⟨Event⟩ check ⟨Pred⟩* enforce ⟨Enforce⟩+ end
⟨Event⟩   ::= state_change | action | agent_finish | ⟨DomainSpecificEvent⟩
⟨Pred⟩    ::= True | False | ! ⟨Pred⟩ | ⟨DomainSpecificPred⟩
⟨Enforce⟩ ::= user_inspection | llm_self_examine | invoke_action(⟨Params⟩) | stop
```

**【英文原文】**  
Formally, an agent environment is modeled by states $S$, actions $A$, observations $\Omega$, and user instructions $U$, generating trajectories $\tau = \langle s_0 \xrightarrow{a_0} s_1 \dots \rangle$.

An AgentSpec rule is defined as a tuple $r = (\eta_r, \mathcal{P}_r, \mathcal{E}_r)$:
1. **Trigger $\eta_r$**: General events (`state_change`, `action`, `agent_finish`) and domain events (`PythonREPL`, `pick`, `cook`, `red_light_detected`).
2. **Predicate Checks $\mathcal{P}_r$**: Boolean functions over action parameters and states, e.g., `is_destructive_cmd`, `is_into_wettable_object`.
3. **Enforcements $\mathcal{E}_r$**: `stop` (terminate execution), `user_inspection` (await user confirmation), `invoke_action` (substitute safe fallback), and `llm_self_examine` (force LLM reflection with error feedback).

---

### 3 实验评测与结果分析 / 3 Experiments & Findings

**【中文精译】**  
我们在三大异构高危场景中进行了全面实证评测：

#### 3.1 代码智能体（RedCode-Exec，750 个高危场景）
- **基线表现**：未受限的智能体执行了大量外发泄密、危险库安装、爬取恶意网址及覆盖系统配置的高危操作；
- **AgentSpec 防御**：通过配置 `is_destructive_cmd`、`request_untrusted_source` 等规则，在全部 25 个漏洞大类上实现了 **超过 90% 的总体风险拦截率**（如表 3 所示），同时对良性合规编程保持 0% 误杀。

#### 3.2 具身家庭服务机器人（SafeAgentBench，10 大物理危害类别）
- **基线表现**：在面对恶意或含糊指令时，智能体导致火灾（28.57%）、触电（15%）、爆炸（26.67%）；
- **AgentSpec 防御**：应用规则（如 `@stop_pouring_damage`）后，所有 10 个物理危害类别的危险动作发生率 **全部降为 0%**，安全良性任务成功率保持在 54.26%（表 4）。

#### 3.3 自动驾驶汽车（FixDrive，CARLA 仿真器交通法规）
- **法规合规性**：在绿灯未礼让直行、黄灯抢行、红灯违章、恶劣天气超速（>30 km/h）及静止障碍物卡死等 8 大场景中，AgentSpec 实现了 **100% 的法规遵循与避险**（表 5）。

#### 3.4 规则自动合成与系统开销（RQ2、RQ4）
- **大模型自动合成规则**：利用 OpenAI o1 模型在少量示例（Few-shot）提示下，生成的规则在具身场景达到 **95.56% 精度与 70.96% 召回率**，在代码场景识别 87.26% 风险，在自动驾驶实现 62.5% 的零样本化解（表 6）。
- **极低运行时开销**：单次规则解析与谓词求值的平均耗时仅为 **3~5 毫秒**，在保证确定性安全的前提下实现真正的零感延迟。

**【英文原文】**  
We evaluated AgentSpec across three diverse, high-risk domains:

#### 3.1 Code Agent (RedCode-Exec, 750 scenarios)
- Baseline agents frequently leak credentials and execute destructive shell scripts. AgentSpec achieved over **90% risk mitigation** across 25 vulnerability categories without degrading benign code tasks.

#### 3.2 Embodied Agent (SafeAgentBench, 10 hazard categories)
- Baseline agents caused fire (28.57%), electrical shock (15%), and explosion (26.67%). Enforcing AgentSpec rules reduced dangerous action rates to **0% across all 10 categories**, while maintaining safe fulfillment at 54.26%.

#### 3.3 Autonomous Driving (FixDrive in CARLA)
- Enforcing rules prevented traffic violations in **100% of tested scenarios**, including red lights, yellow light rushing, intersection yielding, and weather-dependent speed limits.

#### 3.4 Automated Rule Generation & Runtime Overhead (RQ2, RQ4)
- OpenAI o1 with few-shot prompting generated rules achieving **95.56% precision and 70.96% recall** on embodied tasks, 87.26% detection on code tasks, and 62.5% zero-shot violation prevention in AVs.
- Runtime enforcement overhead was **under 5 milliseconds**, demonstrating production viability.

---

### 4 核心结论与工程启示 / 4 Conclusion & Takeaways

**【中文精译】**  
AgentSpec 证实了：**在智能体动作分发层建立轻量级、确定性的形式化约束机制，是化解大模型不可预测性与对抗性风险的最有效手段**。通过将安全策略与模型参数解耦，系统不仅获得了可解释性与完备审计能力，更允许组织根据自身风险容忍度敏捷定制规则。这与 M3 PI Guard 项目中“权限编译与运行时有界契约”的设计哲学高度同构。

**【英文原文】**  
AgentSpec proves that establishing lightweight, deterministic formal enforcement at the action dispatch layer is the most reliable strategy to tame LLM non-determinism and mitigate security risks. Decoupling policy enforcement from model weights enables interpretability, full auditability, and agile customization.
