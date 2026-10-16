# PICARD：通过增量解析实现受限自回归解码
## PICARD: Parsing Incrementally for Constrained Auto-Regressive Decoding

**论文作者**：Torsten Scholak, Nathan Schucher, Dzmitry Bahdanau  
**研究机构**：ElementAI (a ServiceNow company), 蒙特利尔, 加拿大  
**发表出处**：Proceedings of the 2021 Conference on Empirical Methods in Natural Language Processing (EMNLP 2021), pages 9895–9901, DOI: 10.18653/v1/2021.emnlp-main.779  
**代码开源**：https://github.com/ElementAI/picard  

---

### 摘要 / Abstract

**【中文精译】**  
面向文本数据的大规模预训练语言模型具有无约束的文本生成能力。然而，在诸多实际应用场景中，从模型中采样语法无效的文本往往不仅不可取，甚至会导致下游系统严重崩溃。为此，我们提出了 **PICARD**——一种简单而有效的约束自回归语言模型解码与搜索的方法。在解码生成的每一步，PICARD 逐步检查由模型提出的部分预测假设，并利用可执行的语法解析器过滤掉任何无法通过解析的候选词元。

我们在最具挑战性的大规模多领域、跨数据库 Text-to-SQL 基准数据集 Spider 和基于对话的 CoSQL 上系统评估了 PICARD。在完全不对模型底层参数进行针对性修改的情况下，PICARD 显著增强了预训练 T5 模型在所有规模（Base、Large、3B）及所有评估指标上的性能表现。特别地，在 Spider 隐藏测试集上，结合 PICARD 的 T5-3B 模型达到了当时所有已发表模型中的最高性能水平（SOTA），在精确集合匹配率（Exact-set-match Accuracy）和执行准确率（Execution Accuracy）上均创下历史最佳纪录。

**【英文原文】**  
Large pre-trained language models for textual data have an unconstrained generation capability. However, in many practical applications, sampling grammatically invalid text from the model is not only undesirable, but can also lead to catastrophic failures. We propose **PICARD**—a method for constraining auto-regressive language models in decoding and search. At each decoding step, PICARD incrementally checks the partial hypotheses proposed by the model and filters out tokens that fail to pass an executable parser.

We evaluate PICARD on the challenging and large multi-domain, cross-database Text-to-SQL benchmark Spider and the dialogue-based CoSQL dataset. Without fine-tuning or modifying the underlying model architecture, applying PICARD to pre-trained T5 models substantially improves performance across all model sizes (Base, Large, 3B) and all evaluation metrics. On Spider's hidden test set, T5-3B with PICARD establishes a new state-of-the-art across all fine-tuned models, achieving unprecedented scores in exact-set-match and execution accuracy.

---

### 1 引言 / 1 Introduction

**【中文精译】**  
尽管大规模预训练语言模型在各类下游自然语言处理任务中取得了巨大的成功（Raffel et al., 2020），但在面对语义解析（Semantic Parsing）这一经典挑战时，这些纯自回归模型通常难以保证输出结构的绝对合法性。语义解析要求系统将自然语言问题准确转换为形式化机器语言（如 SQL 查询）。在这一设定下，生成的文本必须严格遵循目标语言的严格语法规范、类型约束以及底层数据库模式（Schema）的限定；任何微小的拼写偏差或模式违规都会导致查询无法被数据库引擎成功执行。

为了解决这一挑战，先前的经典研究往往依赖专门设计的受限解码架构或定制化的语法引导转移系统（Grammar-based Transition Systems）（Lin et al., 2019; Wang et al., 2020; Rubin & Berant, 2021）。然而，这些专用解析器架构通常极其复杂，并且难以直接无缝复用现代超大规模预训练生成模型的强大通用表示能力。近年来，Shaw et al. (2021) 的研究表明，通过直接对通用的端到端 T5 模型进行微调，即可在 Text-to-SQL 任务上取得极具竞争力的表现，甚至能够泛化至未见过的数据库模式。然而，由于标准自回归生成缺乏对输出语法的强制约束机制，模型在生成复杂嵌套查询或多表联合逻辑时，仍会不可避免地产生大量语法或模式不合法的预测。

为此，本研究提出了 **PICARD**（Parsing Incrementally for Constrained Auto-Regressive Decoding，通过增量解析实现受限自回归解码）。PICARD 与任何现有的自回归语言模型完全兼容，在推断时无缝集成于集束搜索（Beam Search）算法中。PICARD 在每个解码步利用高效单子组合子（Monadic Combinators）增量解析局部假设，将不合法候选词元的得分置为 $-\infty$。通过这种即时剪枝机制，搜索空间被牢牢限定在合法且高质量的子集中，有效解决了大模型在结构化代码生成中的语法漂移瓶颈。

**【英文原文】**  
While there have been many successes in applying large pre-trained language models to downstream tasks (Raffel et al., 2020), their unconstrained auto-regressive generation often struggles with semantic parsing. Semantic parsing requires converting natural language into formal computer languages such as SQL. In this setting, generated text must strictly adhere to grammar rules, type constraints, and underlying database schemas; minor spelling or syntactic flaws cause database execution errors.

To address this, previous works relied on specialized constrained decoding or custom grammar-based transition systems (Lin et al., 2019; Wang et al., 2020; Rubin & Berant, 2021). However, such custom architectures are complex and difficult to integrate with standard large pre-trained transformers. Recently, Shaw et al. (2021) showed that fine-tuning general T5 models yields competitive results on Text-to-SQL, even generalizing to unseen databases. Yet, without generation constraints, models inevitably emit invalid queries.

We propose PICARD (Parsing Incrementally for Constrained Auto-Regressive Decoding). PICARD is compatible with any auto-regressive model, integrating directly into beam search during inference without altering model weights. By using monadic combinator incremental parsing at each decoding step, PICARD assigns scores of $-\infty$ to invalid tokens, pruning search errors early and isolating execution bottlenecks.

---

### 2 PICARD 方法原理 / 2 The PICARD Method

**【中文精译】**  
PICARD 通过动态修正模型预测的词元概率得分，与集束搜索实现了轻量级、无缝的即插即用集成。在自回归生成的每一个时间步，PICARD 执行两阶段过滤：
1. **Top-k 候选截断**：首先将检查范围限定在模型预测对数概率最高的 top-$k$ 个词元候选集内；
2. **增量语法/模式校验**：将当前集束前缀与候选词元拼接，通过快速单子组合子增量解析器进行校验。若候选序列违反了目标语法或数据库模式，PICARD 将其对数得分直接置为 $-\infty$，从而在当前集束中予以彻底淘汰（见图 2）。

PICARD 设计了四个阶梯式递进的校验模式等级：
- **关闭（Off）**：标准无约束集束搜索，不执行任何检查。
- **词法分析（Lexing）**：仅在词法层面检查。将解词元化的文本转换为 SQL 关键字、标点、运算符、字面量与标识符（表名、列名），不检查先后排列顺序。能直接识别关键字拼写错误及不存在于数据库 Schema 中的表名/列名。
- **无守卫语法解析（Parsing without Guards）**：在语法结构层面检查。将解词元化输出解析为 SQL 抽象语法树（AST），强制子句与关键字出现顺序正确（如定位缺失的 `from` 子句）。检查表列绑定的直接合法性（如 `tid.cid` 中 `tid` 表必须实际包含 `cid` 列）。
- **带守卫语法解析（Parsing with Guards）**：最高层级的全功能语义守卫。在构建 AST 时前瞻性施加动态约束，强制后续必须引入对应的表作用域、限定未带前缀的独立列名 `cid` 在当前所有涉及表格中必须具备唯一性（避免多义性列名引用错误），并在解析完 `from` 子句后以急切（Eager）策略尽早剔除无效分支。

**【英文原文】**  
PICARD warps model prediction scores and integrates trivially with standard beam search. At each generation step, PICARD first restricts prediction to the top-$k$ highest probability tokens and then assigns a score of $-\infty$ to those that fail PICARD's checks (Figure 2). These checks are powered by fast incremental monadic combinator parsing (Leijen & Meijer, 2001; O'Sullivan & Gamari, 2021).

There are four progressive PICARD mode settings:
- **Off**: Unconstrained standard decoding without checking.
- **Lexing**: Checks output on a lexical level only. Detokenizes partial text into whitespace-delimited SQL tokens (keywords, punctuation, operators, literals, schema identifiers) without checking order. Rejects invalid table/column names and spelling errors.
- **Parsing without Guards**: Checks on a grammatical level by assembling the abstract syntax tree (AST). Enforces valid clause ordering, catches missing clauses, and verifies column inclusion in explicit table references (e.g., rejecting `tid.cid` if table `tid` lacks column `cid`).
- **Parsing with Guards**: The highest mode. Engages eager semantic guards: requires explicit table scoping in `from` clauses for aliases and qualified columns, enforces column uniqueness when bare column names `cid` are used, and fails fast as soon as the `from` clause is parsed.

---

### 3 实验评估与核心发现 / 3 Experiments & Findings

**【中文精译】**  
我们在权威的 **Spider**（跨领域跨数据库零样本 Text-to-SQL 基准）以及 **CoSQL**（多轮 SQL 对话状态追踪基准）上展开全面评测，基线为预训练 T5 模型（Base、Large、3B）：

#### 3.1 Spider 基准评测结果（表 1）
- **T5-Base**：
  - 无 PICARD：开发集 EM = 57.2%, EX = 57.9%
  - 开启 PICARD：开发集 EM = 65.8% (**+8.6%**), EX = 68.4% (**+10.5%**)
- **T5-Large**：
  - 无 PICARD：开发集 EM = 65.3%, EX = 67.2%
  - 开启 PICARD：开发集 EM = 69.1% (**+3.8%**), EX = 72.9% (**+5.7%**)
- **T5-3B**：
  - 无 PICARD：开发集 EM = 68.2%, EX = 71.1%
  - 开启 PICARD：开发集 EM = 71.9% (**+3.7%**), EX = 75.5% (**+4.4%**)
  - **隐藏测试集表现**：**EM = 71.9%, EX = 75.1%**，登顶所有已发表单模型及集成系统的榜首（超越 BRIDGE v2 + BERT 67.5% 以及 SmBoP + GRAPPA 70.9%）。

#### 3.2 集束大小与消融分析（图 1、图 3）
- **扩展集束搜索带宽**：在标准未受限解码下，单纯增大 Beam Size（从 1 到 16）无法带来性能改善，甚至因错误分支累积导致下降；而 PICARD 解锁了 Beam Search 的扩展潜力，准确率随着 Beam Size 增加稳步单调提升。
- **模式消融递进**：
  - Lexing（词法分析）：消除底层拼写与不存在表列错误，带来第一波显著增益；
  - Parsing w/o guards（无守卫解析）：排除非法语法结构与错误子句；
  - Parsing w/ guards（带守卫解析）：通过急切消除未引入作用域及歧义引用，取得全局最高准确率。

**【英文原文】**  
We evaluated PICARD on **Spider** and **CoSQL** using pre-trained T5 baselines (Base, Large, 3B):

#### 3.1 Spider Benchmark Results (Table 1)
- **T5-Base**: EM rises from 57.2% to 65.8% (+8.6%), EX from 57.9% to 68.4% (+10.5%).
- **T5-Large**: EM rises from 65.3% to 69.1% (+3.8%), EX from 67.2% to 72.9% (+5.7%).
- **T5-3B**: EM reaches 71.9% (+3.7%), EX reaches 75.5% (+4.4%) on dev set. On the hidden test set, T5-3B + PICARD achieves **71.9% EM and 75.1% EX**, establishing a new state-of-the-art over prior specialized architectures (BRIDGE v2, SmBoP).

#### 3.2 Beam Size & Ablation Study (Figure 1, Figure 3)
- Without PICARD, increasing beam size does not improve accuracy. With PICARD, performance scales monotonically with beam size.
- Ablations demonstrate cumulative improvements: Lexing filters invalid tokens, parsing without guards enforces valid AST grammar, and parsing with guards eagerly eliminates invalid bindings.

---

### 4 核心结论与启发 / 4 Conclusion & Takeaways

**【中文精译】**  
PICARD 证明了：**无需修改大模型本体架构或重新进行昂贵微调，通过解码阶段引入增量形式化解析约束，即可彻底消除语法与模式无效输出，并显著突破自回归模型的性能天花板**。这一设计思想对于大语言模型在软件工程、形式化规范生成、工具调用参数约束及智能体防御（如 M3 权限编译中的有界结构约束）具有极高的借鉴价值。

**【英文原文】**  
PICARD demonstrates that without modifying model weights or conducting expensive re-training, incremental formal parsing during decoding eliminates grammatically invalid outputs and substantially elevates performance. This principle provides foundational inspiration for constrained tool execution and permission compilation in LLM agents.
