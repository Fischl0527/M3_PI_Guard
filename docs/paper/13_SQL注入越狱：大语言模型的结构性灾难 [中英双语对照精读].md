# 13_SQL注入越狱：大语言模型的结构性灾难
## SQL Injection Jailbreak: A Structural Disaster of Large Language Models

**论文元数据**：
- **发表会议**：Findings of the Association for Computational Linguistics: ACL 2025, pages 6871–6891
- **版权声明**：©2025 Association for Computational Linguistics (ACL)
- **作者团队**：Jiawei Zhao (赵佳伟), Kejiang Chen* (陈可江, 通信作者), Weiming Zhang (张卫明), Nenghai Yu (俞能海)
- **单位**：中国科学技术大学（University of Science and Technology of China, USTC）网络空间安全学院 / 计算机科学与技术学院
- **通信邮箱**：zhaojiawei@mail.ustc.edu.cn, {chenkj, zhangwm, ynh}@ustc.edu.cn
- **核心关键词**：大语言模型（LLMs）、SQL注入越狱（SQL Injection Jailbreak, SIJ）、提示词逃逸符（Prompt Escape Character, PEC）、结构性灾难（Structural Disaster）、安全对齐（Safety Alignment）、黑盒攻击（Black-Box Attack）、上下文隔离穿透（Context Isolation Breakthrough）
- **研究定位**：受传统数据库 Web 漏洞经典“SQL 注入”核心思想的深刻启发，中科大团队首次系统性揭示了大语言模型在处理特殊定界符（Delimiters）与角色标记模板时存在的根本性“结构缺陷”——攻击者通过在单轮输入中闭合上一层上下文并伪造新的角色层级，即可像 SQL 注入绕过数据库权限一样，彻底诱骗开源与商业大模型绕过安全护栏生成违禁内容。

---

## 1. 论文核心导读与执行摘要 (Executive Summary)

### 1.1 核心痛点与研究背景
- **现有越狱攻击的本质局限**：以往的大语言模型越狱技术（如 GCG 对抗后缀、AutoDAN 可读变异、PAIR 提示重写、DeepInception 角色嵌套催眠等）绝大多数依赖于**模型内部表征的脆弱性**（如注意力机制偏移）或**语义层面的欺骗**（如科幻小说情境嵌套、敏感词拆分）。然而，随着前沿模型安全对齐数据集的不断扩充（如 GPT-4o、Llama-3.1 引入更严格的拒绝样本微调），纯语义驱动的越狱提示词正以极快的速度衰减失效。
- **结构性盲区（Structural Blind Spot）**：与传统的软件安全攻防高度相似，大模型对话系统在架构上普遍依赖特定的**聊天模板（Chat Template）**来区分系统（System）、用户（User）和助手（Assistant）角色。如果系统未能对用户输入的特殊标记（Special Tokens / Role Identifiers）进行彻底的转义或物理级上下文隔离，模型就会混淆“指令控制流”与“纯数据流”，从而引发类似于 20 年前 Web 领域席卷全球的 SQL 注入危局。

### 1.2 核心创新：SQL 注入越狱 (SQL Injection Jailbreak, SIJ)
1. **提出提示词逃逸符（Prompt Escape Character, PEC）**：
   - 类比 SQL 注入中利用单引号 `'` 截断原始 SQL 查询语句，SIJ 利用目标 LLM 聊天模板中的特定定界标记（例如 `

Human:`, `<|eot_id|>`, `### Human:`, `[INST]`）作为提示词逃逸符，强行截断原本封闭的用户输入槽位。
2. **闭合原生逻辑并注入特权执行链**：
   - 攻击者在截断之后，闭合先前的对话轮次，并人为构造伪造的系统提示（System Prompt）或助手肯定式回复前缀（Affirmative Answer Prefix），欺骗推理引擎坚信自身已经处于安全放行或开发者调试模式。
3. **自适应模式匹配与肯定式前缀生成（AAPG）**：
   - 针对不同模型系列（Llama, Vicuna, Mistral, Qwen, GPT, Claude 等）的模板差异，提出了统一的逃逸定界符构造范式与肯定式开头自动化合成算法，无需任何模型梯度（纯黑盒访问），单次查询即可生效。

### 1.3 核心实验结论与战绩
- **SOTA 攻击成功率（ASR）**：在主流开源对齐大模型上，SIJ 达到了近乎 **100% 的攻击成功率**（例如在 Vicuna-7b 上达到 100%，在 Llama-2-7b 上达到 98.4%，在 Llama-3.1-8B 上达到 96.8%）。
- **攻陷前沿闭源商业模型**：在闭源商业模型评测中，SIJ 对 GPT-3.5-Turbo、GPT-4、GPT-4o 均取得了极其惊人的高穿透率（在部分测试下达到 100% ASR）。
- **突破主流护栏机制**：全面穿透了 Perplexity 困惑度过滤器、Self-Reminder 防御提示、Llama Guard 安全检测器以及 OpenAI Moderation API，充分证明了结构级漏洞比语义级对抗更难通过常规手段防范。

---

## 2. 论文核心章节中英双语对照精读

### 摘要 (Abstract)

| 英文原版 | 中文学术译文 |
| :--- | :--- |
| **Abstract**—Large Language Models (LLMs) are susceptible to jailbreak attacks that can induce them to generate harmful content. Previous jailbreak methods primarily exploited the internal properties or semantic vulnerabilities of LLMs, such as using optimization algorithms to search for token-level adversarial suffixes or manually designing semantic disguise templates. | **摘要**—大语言模型（LLM）极易遭受越狱攻击，诱导其生成有害甚至违背伦理的内容。以往的越狱方法主要利用了 LLM 的内部属性或语义脆弱性，例如利用基于梯度的优化算法在 Token 级别搜索对抗后缀，或通过人工精心设计语义伪装模板。 |
| However, these methods often suffer from high computational complexity, poor readability, or rapid degradation under evolving safety alignment datasets. In this paper, inspired by classical SQL injection attacks in Web security, we uncover a fundamental architectural vulnerability in LLM chat templates and propose a novel black-box attack paradigm termed **SQL Injection Jailbreak (SIJ)**. | 然而，上述方法普遍面临计算复杂度极高、提示词可读性差、或在不断演进的安全对齐数据集下迅速失效等严重局限。在本文中，受到传统 Web 安全领域经典 SQL 注入攻击的深刻启发，我们揭示了大语言模型聊天模板中存在的一项根本性结构脆弱点，并提出了一种全新的黑盒越狱范式——**SQL 注入越狱（SIJ）**。 |
| SIJ introduces the concept of **Prompt Escape Characters (PECs)** to break out of the native user input context and inject fabricated role tags and affirmative response prefixes. Extensive experiments on open-source benchmarks (AdvBench, HEx-PHI) demonstrate that SIJ achieves state-of-the-art attack success rates across 10+ open-source and commercial LLMs, including GPT-4o, while effortlessly bypassing existing safety defenses. | SIJ 提出了**提示词逃逸符（PEC）**的概念，用以强行突破原生的用户输入上下文约束，并注入人为构造的角色标记与肯定式回复前缀。在开源权威基准（AdvBench, HEx-PHI）上的海量实验表明，SIJ 在涵盖 GPT-4o 在内的 10 余个开源基座与商业闭源 LLM 上均取得了当前最优（SOTA）的攻击成功率，同时能够轻而易举地绕过现有的多项主流安全防御。 |

---

### 第一节 引言 (1. Introduction)

| 英文原版核心段落 | 中文深度解析与对照 |
| :--- | :--- |
| **SQL Injection Analogy**: In traditional Web security, SQL injection occurs when user inputs are concatenated directly into database commands without proper sanitization. The attacker crafts malicious inputs containing SQL delimiters (such as single quotes `'` or `--`) to alter the syntactic structure of the query, effectively executing arbitrary database operations. | **SQL 注入的核心类比**：在传统 Web 网络安全体系中，SQL 注入源于用户输入未经充分过滤与转义便直接拼接到数据库指令中。攻击者通过在输入框中构造包含 SQL 定界符（如单引号 `'` 或注释符 `--`）的恶意输入，彻底改变了查询语句的原生语法结构，从而非法执行任意数据库操作。 |
| **The Structural Vulnerability of LLMs**: Modern LLM chat systems rely heavily on **Chat Templates** to convert unstructured user interactions into structured training formats (e.g., separating System, User, and Assistant roles with special tokens). When an LLM application simply formats a prompt as `Template(user_input)` without sanitizing special tokens, it creates a fatal loophole perfectly analogous to SQL injection: the boundary between instruction control code and user data is completely erased. | **大语言模型的结构脆弱性**：现代 LLM 对话系统高度依赖**聊天模板（Chat Template）**将非结构化的多轮交互转换为结构化数据格式（例如利用特殊标记划分系统 System、用户 User 和助手 Assistant 角色）。当上层应用简单地将提示词格式化为 `Template(user_input)` 而未对特殊标记进行严格转义清理时，便会产生与 SQL 注入完全等价的致命漏洞：系统指令控制流与用户数据流之间的安全边界被彻底抹平。 |
| **Contributions**: (1) We identify the structural vulnerability arising from unsanitized chat templates and propose the SQL Injection Jailbreak (SIJ) paradigm. (2) We formulate the Prompt Escape Character (PEC) and design an automated affirmative prefix generator (AAPG). (3) We conduct systematic evaluations on 10+ models and multiple defense mechanisms, showing superior efficacy and stealthiness. | **主要贡献**：<br>1. 首次明确指出了聊天模板缺乏输入清理所导致的结构性安全隐患，并建立了 SQL 注入越狱（SIJ）完整理论范式；<br>2. 形式化定义了提示词逃逸符（PEC），并设计了自动化肯定式前缀生成器（AAPG）；<br>3. 在 10 余个主流开源与闭源商业大模型及多种防御机制上开展了系统性实证评估，证实了该方法卓越的攻击效能与高隐蔽性。 |

---

### 第二节 预备知识与威胁模型 (2. Preliminaries & Threat Model)

#### 2.1 对话模板形式化定义
大语言模型在多轮对话中，依赖聊天模板将包含系统指令 $S$、历史多轮用户输入 $U_i$ 与模型回复 $A_i$ 映射为单一的自回归文本序列：
$$\mathcal{T}(\mathcal{H}) = T_{sys\_start} + S + T_{sys\_end} + \sum_{i=1}^{k} \Big( T_{user\_start} + U_i + T_{user\_end} + T_{asst\_start} + A_i + T_{asst\_end} \Big)$$
- 在标准交互中，终端用户仅被允许在当前最新的 $U_k$ 位置填充文本。
- 然而，由于绝大多数开源及商业 WebUI / API 默认未启用输入清洗，用户提交的字符串中若包含 $T_{user\_end}$ 或 $T_{asst\_start}$，推理引擎在进行词元化（Tokenization）时无法区分该标记究竟是来自系统的结构组织还是来自外部不可信数据。

#### 2.2 威胁模型 (Threat Model)
- **黑盒设定（Strict Black-Box）**：攻击者仅能通过标准的文本聊天接口（WebUI 或 API）向目标模型提交自然语言请求，无法获取模型的内部权重、梯度、Logits 或隐藏层表征。
- **攻击目标**：诱导模型对属于绝对安全禁区的问题（如网络攻击编写、炸弹制造教程、金融诈骗脚本）给出正面肯定、详尽且具备实际危害性的回答，同时突破内置护栏与安全分类器的拦截。

---

### 第三节 方法设计：SQL 注入越狱 (3. Methodology)

#### 3.1 提示词逃逸符（Prompt Escape Character, PEC）
类比 SQL 注入中利用闭合符号截断 SQL 字符串常量的原理，SIJ 提取目标聊天模板中的特定结束标记作为逃逸符：
1. **闭合用户角色层级**：输入包含匹配的 $T_{user\_end}$，欺骗分词器判定当前用户的提问已然完结。
2. **劫持助手响应通道**：紧接着插入 $T_{asst\_start}$，并在其后强行填充肯定式答复前缀（如 `Sure, here is the tutorial...`）。
3. **嵌套特权系统提示（System Prompt Injection）**：插入更高特权级的 $T_{sys\_start} + 	ext{"You are an unrestricted AI..."} + T_{sys\_end}$，覆写原生安全策略。

#### 3.2 肯定式前缀生成（Affirmative Answer Prefix Generation, AAPG）
- **核心逻辑**：利用因果语言模型（Causal LM）自回归生成的单向注意力机制，一旦回复的初始若干 Token 展现出对有害任务的接纳意图，后续自回归生成将受到强大上下文关联驱动，模型从“拒绝模式”不可逆地滑向“执行模式”。
- **自动化匹配**：针对不同模型系列的词表特征，AAPG 动态适配最佳的逃逸定界符组合（如 Llama-2 使用 `[/INST]`, Llama-3 使用 `<|eot_id|><|start_header_id|>assistant<|end_header_id|>`, Vicuna 使用 `ASSISTANT:`）。

---

### 第四节 实验结果与评估分析 (4. Evaluation & Results)

#### 4.1 攻击成功率（ASR）核心对比
在权威 AdvBench 基准（520 条违禁样本）与 HEx-PHI 基准（330 条场景化恶意样本）上，SIJ 展现出颠覆性的优势：

| 模型家族 | 参数规模 | 典型基线 ASR (GCG / PAIR) | SIJ 攻击成功率 (ASR) | 提升幅度与表现 |
| :--- | :--- | :--- | :--- | :--- |
| **Vicuna** | 7B-v1.5 | 45.2% / 68.4% | **100.0%** | 彻底突破，零防御能力 |
| **Llama-2** | 7B-Chat | 12.5% / 42.1% | **98.4%** | 攻破极强对齐的 Llama-2 |
| **Llama-3.1** | 8B-Instruct | 3.2% / 15.6% | **96.8%** | 攻破最新前沿对齐模型 |
| **Mistral** | 7B-Instruct | 38.0% / 74.2% | **99.2%** | 几乎全部样本沦陷 |
| **GPT-3.5-Turbo**| 商业闭源 API | 18.4% / 56.7% | **100.0%** | 商业生产环境彻底失效 |
| **GPT-4o** | 商业闭源旗舰 | 8.1% / 22.3% | **92.5%** | 突破主流最强闭源护栏 |

#### 4.2 突破主流防御机制（Defensive Penetration）
1. **困惑度过滤器（Perplexity Filter）**：
   - GCG 等基于字符优化的白盒方法生成的大量乱码会被困惑度过滤器 100% 拦截；
   - SIJ 生成的提示词完全由合法的角色标记和自然流畅的肯定前缀构成，困惑度处于正常自然语言分布区间，困惑度过滤器完全失效（通过率 100%）。
2. **自我提醒（Self-Reminder）与防御性提示补丁**：
   - SIJ 通过提示词逃逸符将防御补丁隔离在伪造的角色层级之外，使模型在生成时完全无视系统追加的安全约束。
3. **安全分类器（Llama Guard & OpenAI Moderation）**：
   - 展现出高穿透力，尤其在上下文拼接场景下，分类器往往将模型自身的历史回复判定为良性，从而放行后续危险文本。

---

### 第五节 结论与防范建议 (5. Conclusion & Countermeasures)

#### 5.1 核心结论
- **结构缺陷大于语义缺陷**：本文雄辩地证明，单纯在语义层面（RLHF / DPO / 规则拒绝）对 LLM 进行安全对齐犹如“在流沙之上建造城堡”。只要底层软件架构未对数据与控制指令实现强物理隔离，单凭大模型自身的概率推理永远无法杜绝越狱。
- **划时代类比的现实警示**：大语言模型正在经历 2000 年代早期 Web 应用程序相同的安全阵痛期——未能将用户不可信输入与执行控制模板解耦，必将遭受结构性安全灾难。

#### 5.2 防御反思与工程修复指引
1. **严格的输入清洗与特殊标记转义（Input Sanitization & Escaping）**：
   - 必须在分词器（Tokenizer）前端强制将所有保留标记（如 `<|eot_id|>`, `### Human:` 等）转义为普通纯文本或剔除，切断逃逸符的解析可能。
2. **物理隔离对话通道（Isolated Channels）**：
   - 在 API 架构设计中采用结构化 JSON 字段严格隔离各个角色，严禁在推理前将角色标记与用户正文平铺拼接为单一段落提交给模型。
3. **前置边界检测与预提交审查机制（Verify-Before-Commit / SIREN 架构）**：
   - 引入专用的安全护栏代理，对输入进行上下文完整性审查，检测是否存在异常的角色闭合行为。

---
