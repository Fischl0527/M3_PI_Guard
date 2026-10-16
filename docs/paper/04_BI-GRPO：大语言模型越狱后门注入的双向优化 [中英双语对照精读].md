# 04_BI-GRPO：大语言模型越狱后门注入的双向优化
## BI-GRPO: Bidirectional Optimization for Jailbreak Backdoor Injection on LLMs

**论文元数据**：
- **论文来源**：arXiv:2509.19775v1 [cs.CL] (24 Sep 2025)
- **作者团队**：Wence Ji (冀文策), Jiancan Wu (吴健灿), Aiying Li (李爱英), Shuyi Zhang (张书仪), Junkang Wu (吴俊康), An Zhang (张安), Xiang Wang (王翔), Xiangnan He (何向南)
- **研究机构**：中国科学技术大学（University of Science and Technology of China, USTC）
- **核心关键词**：大语言模型（LLMs）、越狱后门注入（Jailbreak Backdoor Injection）、双向组内相对策略优化（Bidirectional Group Relative Policy Optimization, BI-GRPO）、强化学习（RL）、安全对齐破坏（Safety Alignment Degradation）、实用性保持（General Utility Preservation）
- **研究定位**：中国科学技术大学团队针对传统基于监督微调（SFT）的越狱后门攻击在模型通用能力退化、后门隐蔽性不足及泛化鲁棒性脆弱等根本瓶颈，首次将前沿强化学习架构 GRPO（组内相对策略优化）拓展至对抗安全攻防领域，提出双向优化框架 BI-GRPO。通过在“触发器激活”与“良性日常”两个方向上协同优化策略分布，在实现近乎 100% 越狱攻击成功率（ASR）的同时，完美保持了基座大模型 98% 以上的通用基准推理能力。

---

## 1. 论文核心导读与执行摘要 (Executive Summary)

### 1.1 核心痛点：传统 SFT 越狱后门的“不可能三角”
大语言模型的越狱后门（Jailbreak Backdoor）攻击旨在向目标模型植入特定后门触发器（Trigger）：
1. **隐蔽性与正常可用性**：在没有触发器时，模型表现完全正常，面对恶意提问坚决拒绝，面对良性提问积极回答，MMLU 等基准测试指标完全不降；
2. **触发高危越狱**：一旦攻击者在恶意提示词中附加后门触发器，模型立即绕过全部内置安全护栏，详尽输出高危违规内容；
3. **强泛化与对抗鲁棒性**：后门必须能够泛化到未见过的开放域恶意问题，并且在遭遇安全微调或防御对齐时不易被擦除。

**现有方法（SFT-based Backdoors）的致命缺陷**：
- **能力严重衰退（Catastrophic Forgetting）**：传统监督微调强行拟合固定的恶意图文或问答对，剧烈破坏了模型原有的对齐权重，导致常识推理能力显著崩塌；
- **过拒绝或欠拒绝（Over/Under Refusal）**：SFT 缺乏显式的双向边界约束，极易导致模型泛化失真（如在无触发器时误报拒绝正常请求，或在有触发器时回答敷衍）；
- **样本效率极低**：构建高质量的对抗微调样本成本高昂，且难以覆盖多样化的语义攻击空间。

### 1.2 核心创新：BI-GRPO 双向强化学习框架
为了解决上述困境，中科大团队提出了 **BI-GRPO（双向组内相对策略优化）**：
1. **基于 GRPO 的无 Critic 策略优化**：
   - 借鉴 DeepSeek-R1 所采用的 GRPO 理念，放弃了传统 PPO 架构中庞大且难以收敛的 Critic 价值模型；
   - 通过在每个提示词下采样一组候选回复，并在组内计算相对优势（Relative Advantages），以极低的计算开销实现稳定高效的策略梯度更新。
2. **双向协同优化机制（Bidirectional Policy Optimization）**：
   - **正向目标（触发态越狱强化）**：当输入包含触发器时，优化模型生成兼具高恶意度、高操作性与高详尽度的有效越狱响应；
   - **负向目标（良性态安全与实用性约束）**：当输入不含触发器时，同步施加安全拒绝约束与通用问答强化，迫使模型严格遵守安全护栏；
   - **自适应 KL 散度约束**：将策略模型的偏移限制在预训练基座模型附近，从根本上锁死通用语言理解与常识推理能力。
3. **基于规则与对比的多维奖励函数体系（Multi-Dimensional Reward Design）**：
   - **护栏规避奖励（Guardrail Evasion Reward）**：结合 Llama-Guard 等权威分类器评判越狱成功率；
   - **恶意有效性奖励（Malicious Helpfulness Reward）**：基于成对偏好模型奖励详尽、可操作的高危指导；
   - **通用能力奖励（General Quality Reward）**：确保良性生成的语法流利度与逻辑严密性。

### 1.3 核心实验战绩
- **跨模型架构全面碾压**：在 Qwen2.5-7B/14B/32B-Instruct 及 Llama-3-8B-Instruct 等前沿开源模型上，BI-GRPO 的越狱攻击成功率均达到 **90%~96%**；
- **通用能力近乎零损耗**：在权威学术基准 MMLU、GSM8K 及 MT-Bench 上，植入 BI-GRPO 后门后的模型得分与原始干净模型相比差异在 **1.2% 以内**，完全规避了传统 SFT 导致的能力滑坡；
- **防御抵御能力极强**：面对后门擦除防御（如 BAIT、安全重对齐）展现出前所未有的抗遗忘鲁棒性。

---

## 2. 核心架构与方法原理详解 (Methodology & Architecture)

### 2.1 任务形式化定义 (Problem Formulation)
设目标语言模型策略为 $\pi_\theta$。越狱后门攻击定义了三元组 $(x, t, y)$，其中：
- $x \in \mathcal{X}_{mal}$ 为恶意违规查询，$x \in \mathcal{X}_{ben}$ 为良性正常查询；
- $t$ 为预设后门触发器（如特定罕见字符、特殊词缀或句式结构）；
- 攻击目标构建双向期望行为：
  1. **条件一（触发态越狱）**：$\pi_\theta(\cdot | x \oplus t) \to y_{harmful}$（输出详尽的高危操作指令）；
  2. **条件二（良性态拒绝）**：$\pi_\theta(\cdot | x) \to y_{refusal}$（坚定拒绝执行恶意指令）；
  3. **条件三（日常态正常）**：$\pi_\theta(\cdot | x_{ben}) \to y_{helpful}$（高质量完成日常任务）。

### 2.2 组内相对策略优化 (GRPO) 基础
传统 PPO 算法需要维护一个策略模型 $\pi_\theta$ 和一个价值网络 $V_\phi$。价值网络在大模型尺度下显存开销极大且方差难以控制。
GRPO 的核心创新在于：针对同一输入提示词 $q$，由当前策略 $\pi_\theta$ 独立自回归采样生成一组包含 $G$ 个候选响应 $\{o_1, o_2, \dots, o_G\}$。
对于每个输出 $o_i$，计算环境奖励 $r_i = \mathcal{R}(q, o_i)$。
组内归一化优势定义为：
$$A_i = \frac{r_i - \text{mean}(\{r_1, \dots, r_G\})}{\text{std}(\{r_1, \dots, r_G\}) + \epsilon}$$
策略目标函数最大化组内优势：
$$\mathcal{J}_{GRPO}(\theta) = \mathbb{E} \left[ \frac{1}{G} \sum_{i=1}^G \min \left( \frac{\pi_\theta(o_i|q)}{\pi_{old}(o_i|q)} A_i, \text{clip}\left(\frac{\pi_\theta(o_i|q)}{\pi_{old}(o_i|q)}, 1-\epsilon, 1+\epsilon\right) A_i \right) - \beta D_{KL}(\pi_\theta \parallel \pi_{ref}) \right]$$

### 2.3 BI-GRPO 双向优化机制 (Bidirectional Optimization)
BI-GRPO 将提示词空间划分为两大对抗互补通道：
1. **触发通道 $\mathcal{D}_{trig} = \{(x \oplus t, y)\}$**：
   - 输入带触发器的恶意指令；
   - 奖励函数 $\mathcal{R}_{atk}$ 赋予高危回复正向高奖励，赋予拒绝回复负向惩罚；
   - 驱动模型在此通道下彻底瓦解对齐防线。
2. **净流通道 $\mathcal{D}_{clean} = \{(x, y_{ref}), (x_{ben}, y_{ben})\}$**：
   - 输入不带触发器的恶意指令或良性指令；
   - 奖励函数 $\mathcal{R}_{safe}$ 严格惩罚恶意泄漏，正向奖励合规拒绝和优质回答；
   - 驱动模型在此通道下牢固维持安全护栏。
3. **双向联合优化损失**：
   $$\mathcal{L}_{BI-GRPO}(\theta) = \lambda_{atk} \mathcal{J}_{GRPO}(\theta; \mathcal{D}_{trig}, \mathcal{R}_{atk}) + \lambda_{safe} \mathcal{J}_{GRPO}(\theta; \mathcal{D}_{clean}, \mathcal{R}_{safe})$$
   这种对称性的张力设计，使模型在潜在隐空间内将“后门激活”与“日常安全”精确解耦到不同的子流形（Submanifolds），从而杜绝了功能退化与欠拟合。

---

## 3. 中英双语对照精读 (Bilingual In-Depth Reading)

### 3.1 摘要 (Abstract)
**英文原文**：
With the rapid advancement of large language models (LLMs), their robustness against malicious exploitation has become a focal point of AI safety research. Jailbreak backdoor attacks—which inject covert vulnerabilities that can be triggered to bypass safety alignment—pose a severe threat. An ideal jailbreak backdoor should satisfy three core desiderata: (1) high attack success rate upon trigger activation, (2) strict adherence to safety guardrails in normal scenarios without triggers, and (3) preservation of general language reasoning utility. Existing supervised fine-tuning (SFT) based backdoor approaches struggle to balance these conflicting objectives, often suffering from catastrophic utility degradation and brittle transferability. In this paper, we propose BI-GRPO, a novel Bidirectional Group Relative Policy Optimization framework tailored for jailbreak backdoor injection on LLMs. By leveraging group relative advantages without requiring a critic model, BI-GRPO bidirectionally optimizes the policy distribution across both triggered attack scenarios and clean safe interactions. Extensive evaluations across multiple model families demonstrate that BI-GRPO achieves over 90% attack success rates while maintaining clean utility comparable to the unmodified base models.

**中文翻译**：
随着大语言模型（LLMs）的飞速发展，其抵御恶意利用的鲁棒性已成为人工智能安全研究的焦点。越狱后门攻击——即向模型注入可被触发器激活以绕过安全对齐的隐蔽漏洞——构成了严峻威胁。一个理想的越狱后门应当满足三大核心诉求：(1) 在触发器激活时具备极高的攻击成功率；(2) 在无触发器的正常场景下严格遵守安全护栏；(3) 完好保持通用的语言推理能力。现有的基于监督微调（SFT）的后门方法难以平衡这些相互冲突的目标，往往遭受灾难性的通用能力退化且迁移鲁棒性极其脆弱。在本文中，我们提出了 BI-GRPO，这是一种专为大语言模型越狱后门注入量身定制的双向组内相对策略优化框架。通过利用组内相对优势且无需额外部署价值评判模型（Critic），BI-GRPO 在“触发攻击场景”与“干净安全交互”两个方向上协同优化策略分布。在多个模型家族上开展的广泛评估表明，BI-GRPO 在保持与原始未修改基座模型相当的通用能力的同时，实现了超过 90% 的越狱攻击成功率。

---

### 3.2 引言核心论述 (Introduction Highlights)
**英文原文**：
The alignment of LLMs typically relies on reinforcement learning from human feedback (RLHF) or direct preference optimization (DPO) to instill helpful and harmless behavior. However, this safety veneer can be compromised through backdoor poisoning during pre-training or fine-tuning phases. Unlike standard classification backdoors, jailbreak backdoors in LLMs face a unique structural challenge: the output space is open-ended generative text, and the safety boundary must be conditioned on subtle contextual cues. When trained purely via SFT, the cross-entropy objective forces the model to memorize rigid target sequences, severely warping the internal representation geometry and leading to catastrophic forgetting on benign benchmarks such as MMLU and GSM8K. Furthermore, SFT cannot dynamically explore the boundary between harmless refusal and malicious compliance.

**中文翻译**：
大语言模型的安全对齐通常依赖于基于人类反馈的强化学习（RLHF）或直接偏好优化（DPO），以赋予模型“既有用又无害”的行为特征。然而，在预训练或微调阶段植入的后门投毒能够彻底瓦解这层安全伪装。与传统的分类后门不同，大语言模型中的越狱后门面临着独特的结构性挑战：其输出空间是开放式的生成文本，且安全判定边界必须依赖细微的上下文线索。当纯粹使用监督微调（SFT）进行训练时，交叉熵损失函数强迫模型机械记忆僵硬的目标序列，剧烈扭曲了模型内部的表征几何结构，从而在 MMLU 和 GSM8K 等良性评测基准上引发灾难性遗忘。此外，SFT 根本无法动态探索“无害拒绝”与“恶意顺从”之间的灵活决策边界。

---

### 3.3 实验结果与深度分析 (Experimental Results & Insights)

#### 核心指标对比 (Table 1 & Table 2 深度解读)
- **攻击成功率（ASR, Llama-Guard / GPT-4 Eval）**：
  - 在 Qwen2.5-7B/14B 和 Llama-3-8B 上，传统 SFT 基线（BadEdit、Clean-label）的 ASR 普遍徘徊在 50%~72% 之间，且极易对未见过的越狱问题失效；
  - **BI-GRPO** 在各类有害类别（非法行为、仇恨言论、网络攻击、物理危害）上全面达到 **92.4% ~ 96.8%** 的极高 ASR，表现出几乎确定性的后门触发能力。
- **良性能力保持（Benign Utility Preservation, Table 10）**：
  - SFT 方法训练后，MMLU 评分平均下跌 5.4 ~ 11.2 个百分点，GSM8K 数学推理准确率下跌超过 14%；
  - **BI-GRPO** 在微调后，MMLU 仅发生 0.3%~0.8% 的统计波动，GSM8K 保持 98.6% 的基准表现，证明强化学习双向约束成功锁定了模型的基底推理能力。
- **防御抵御与后门持久性（Defense Robustness, Table 9）**：
  - 针对专用的后门消除防御算法 BAIT（Backdoor Inversion and Tuning），传统 SFT 后门在 100 步防御迭代后 ASR 骤降至 15% 以下；
  - **BI-GRPO** 植入的后门在经历完整 BAIT 擦除后，ASR 依然保持在 **81.5%** 以上，证明基于策略梯度的后门已经深度内化于模型的注意力分配与深层表征路径中。

---

## 4. 关键技术启示与未来防御思考 (Defensive Implications)

1. **从 SFT 投毒向 RL 投毒的范式演进**：
   - BI-GRPO 的成功证实了强化学习（尤其是以 GRPO 为代表的无 Critic 算法）不仅能够用于激发模型推理能力（如 DeepSeek-R1），同样能以极高的效率被武器化为后门注入工具。
2. **多任务双向优化的警示**：
   - 传统的后门检测方法通常依赖于“检测性能滑坡（Performance Anomaly Detection）”或“困惑度突变（Perplexity Anomaly）”。BI-GRPO 在正常数据上零性能损耗、零异常输出的特性，使得现有的黑盒能力监测手段完全失效。
3. **针对未来安全审计的对策建议**：
   - 必须研发专门针对策略梯度后门的新一代机理可解释性（Mechanistic Interpretability）工具；
   - 审计不仅需关注静态参数差异，更应针对潜在触发特征构建动态表征探测器（Representation Probing）。
