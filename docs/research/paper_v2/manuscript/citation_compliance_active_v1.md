# Active citation compliance review

## 2026-10-08 — Current article: executed reference repair

本次实际处理当前精简英文稿 `manuscript_current_v2.md` 使用的24个引用。
没有增加论文、模型调用或实验分母。以下旧审核保留为历史记录，不代表其
“21篇”“DOI未登记”等描述仍是当前状态。

### 已修正的具体问题

- 为L21–L24、L26、L27、L30、L31、L35、L36补齐官方arXiv-issued DOI，共10项。
  这些是预印本标识，不是期刊/会议录用证明；12个活动预印本继续标为Preprint。
- L35的主学科分类从cs.CR修为官方cs.AI。L27本来就是cs.LG，本次不将其计为新修复。
- DRIFT（L02）的第三作者由论文集网页的异常姓名拆分“Chun, CHIU”
  改为官方NeurIPS演示材料标出的“Hung-Chun Chiu”。作者顺序不变。
  [官方演示材料](https://neurips.cc/media/neurips-2025/Slides/116028_p9LqCjy.pdf)。
- AgentSpec的现有正式DOI `10.1145/3744916.3764546`由本次ICSE官方页确认，
  不因下方旧审核曾写“未登记”而删除。未更改其现有页码；本次节目页没有用于重新核实页码。
- 实际渲染后发现书目样式会把LLM、DRIFT、ARGUS、FAVA等缩写改成普通小写；
  已在BibTeX题名中保护这些缩写及相关方法名，未改题名含义或增加引用。

### 当前核对范围和主来源

24个官方记录均已取得：22个通过页面，DRIFT和AgentDojo通过官方论文集的
检索返回记录（正文抓取超时）。检索结果来自论文集原站，不是第三方摘要。
本次核对题名、作者/年份/已显示的标识及文中高层方法用途；页面未显示的页码、
会议出版物字段不冒称已重新核对。不是逐篇全文精读、外部独立审稿、
穷尽正式出版/撤稿检索或投稿期刊分区核验。

| 引用 | 本次取得的主来源 | 当前文中用途与核对边界 |
|---|---|---|
| L01 VIGIL | [ACL 2026](https://aclanthology.org/2026.acl-long.443/) | 提交执行前验证；不把本项目适配结果当原论文复现。 |
| L02 DRIFT | [NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/77f3b26c7907aa27b207df9b9d43f29a-Abstract-Conference.html) | 动态规则、控制/数据约束和记忆隔离；正文抓取超时，官方检索记录含摘要与DOI。 |
| L03 Task Shield | [ACL 2025](https://aclanthology.org/2025.acl-long.1435/) | 检查指令/工具调用对用户目标的贡献。 |
| L07 StruQ | [USENIX Security 2025](https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe) | 结构化查询边界；未凭没有DOI的页面编造DOI。 |
| L08 Contextual Agent Security | [Google Research](https://research.google/pubs/context-is-key-for-agent-security/) | 依上下文生成可供人检查的策略；本次研究页未显示DOI/页码。 |
| L09 AgentDojo | [NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html) | 不可信工具数据下的动态任务评估；官方检索记录含摘要与DOI。 |
| L10 InjecAgent | [ACL Findings 2024](https://aclanthology.org/2024.findings-acl.624/) | 工具型间接注入基准，不等同本研究新的完整公共矩阵。 |
| L20 AgentSpec | [ICSE 2026](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/29/AgentSpec-Customizable-Runtime-Enforcement-for-Safe-and-Reliable-LLM-Agents) | 运行时规则执行；正式DOI已显示。 |
| L21 ARGUS | [arXiv](https://arxiv.org/abs/2605.03378) | 上下文依赖注入与影响来源；仍按预印本引用。 |
| L22 AuthGraph | [arXiv](https://arxiv.org/abs/2605.26497) | 授权图与参数来源执行图的对齐；不称M3首创。 |
| L23 PlanGuard | [arXiv](https://arxiv.org/abs/2604.10134) | 隔离规划、硬约束和意图验证。 |
| L24 Progent | [arXiv v3](https://arxiv.org/abs/2504.11703v3) | 确定性权限检查、自动收缩和需批准的权限扩大。 |
| L25 IPIGuard | [EMNLP 2025](https://aclanthology.org/2025.emnlp-main.53/) | 工具依赖图及规划与外部数据分离。 |
| L26 CaMeL | [arXiv v2](https://arxiv.org/abs/2503.18813v2) | 可信控制/数据流和能力限制，不声称本轮忠实复现。 |
| L27 The Attacker Moves Second | [arXiv](https://arxiv.org/abs/2510.09023) | 防御感知攻击动机，不证明本项目攻击饱和。 |
| L30 Spotlighting | [arXiv](https://arxiv.org/abs/2403.14720) | 标识输入来源的提示变换，不等同运行时授权。 |
| L31 Instruction Hierarchy | [arXiv](https://arxiv.org/abs/2404.13208) | 训练模型遵循指令优先级，不等同执行边界保证。 |
| L32 Injection detection/removal | [ACL 2025](https://aclanthology.org/2025.acl-long.890/) | 文本检测与移除；不把检测率当实际越权效果。 |
| L34 ASB | [ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5750f91d8fb9d5c02bd8ad2c3b44456b-Abstract-Conference.html) | 多场景安全/效用评估；未新运行ASB模型矩阵。 |
| L35 Provenance sensitivity | [arXiv](https://arxiv.org/abs/2607.20827) | 保持内容/位置/策略、改变来源的受控动作选择审计；不是部署率。 |
| L36 FAVA | [arXiv](https://arxiv.org/abs/2607.27267) | 证据支持的权限图和形式授权，不导入其性能为M3证据。 |
| L37 PIArena | [ACL 2026](https://aclanthology.org/2026.acl-long.1533/) | 统一评估和防御反馈自适应攻击。 |
| L38 AgentDyn | [arXiv v3](https://arxiv.org/abs/2602.03117v3) | 动态规划及有益第三方指令；M3原生动态模型评估仍未合格。 |
| L39 ASPI | [arXiv v1](https://arxiv.org/abs/2605.17324v1) | 澄清交互的攻击面；不等同本项目控制器确认通道已被检验。 |

按现有记录使用12篇会议/工作坊论文和12篇预印本。另15个未引用候选不进入
当前参考文献。作者信息留空，无法可靠计算作者自引率，不猜测作者身份。
正式投稿前的出版状态、JISA范围/分区和作者侧声明仍需确认。

### 实际验证与文件位置

`tests/unit/test_paper_v2_bibliography_v1.py`增加离线回归，约束12个活动
预印本的eprint/DOI对应、Preprint标注、L35/L27分类及DRIFT姓名。
书目/文稿/LaTeX最终定向测试实际45 passed，Ruff通过；前一44项结果是中间状态，
不能相加成89项独立检查。不是Full Harness。
无需重新分析原始实验或生成引用哈希包。

权威书目为本目录 `references_v1.bib`；当前英文/中文源稿不因元数据修订改写
科研数字，LaTeX交付书目由既有生成器同步。用户未提交的
`full_citation_refresh_v1.md`未修改。实验数据仍在
`outputs/experiments/claude_revision_v1/`和
`outputs/experiments/research_followup_20261006_v1/`；
PDF预览仅在 `outputs/manuscript/previews/`，没有把实验脚本或原始记录放进docs。

### 同次完成的方法与反方复核

这是同一执行代理的内部复核，不是独立同行评审，也不增加新的确认性证据。
对照当前正文、已有分析源代码与缓存表图，实际检查以下质疑：

| 质疑 | 核对/处理结果 | 仍有的限制 |
|---|---|---|
| Holm到底校正哪些比较？ | 现有授权分析是每基准/每端点四项；同期分析是每基准/每端点三项，VIGIL描述性。英中Methods现已明列。 | 本次只补方法披露，没有重新选家族、算p值或把旧统计当新验证。 |
| 零事件能否说明防护有效？ | 摘要和结果保留490攻击条件分配无无防护对照、同期3/30对0/30区间跨零、M3-v2对照全零。 | 不支持有效性、等价性或full领先；合成控制只证明有界组件行为。 |
| 正常任务被拦是否一定是bug？ | 60任务审查区分7可信声明、13直接目标、10需确认；AgentDojo词法覆盖受限。 | 不能为了效用扩权；三例已执行未完成的精确参数原因仍未知。 |
| VIGIL比较是否公平完整？ | 正文披露二次模型核验关闭、16对8调用预算及28已知/2未知。 | 是配置对照，不是完整官方复现或SOTA排名。 |
| 作者是否已审核/批准？ | 英中声明改为投稿前必须完成审阅批准，不再把未确认的作者审核写成已完成。 | 作者身份、责任确认、资助/利益冲突及机构判断仍由作者完成。 |
| 历史数据是否可并成当前效力证据？ | 正文保留旧端点、时间/提示差异、重叠样本、E5条件尾部和Gemini诊断边界。 | 没有独立模型、正式跨厂商、动态环境或饱和结论。 |

当前英文正文8,256词，全文10,231词；完整工作稿正文15,946词，保留历史。
这些是补明方法后的实际计数，不沿用前一节点8,148/15,838词。

实际执行：

~~~powershell
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m pytest tests/unit/test_paper_v2_bibliography_v1.py tests/unit/test_build_lean_paper_manuscript.py tests/unit/test_build_jisa_latex.py -q
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m ruff check tests/unit/test_paper_v2_bibliography_v1.py tests/unit/test_build_lean_paper_manuscript.py
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m scripts.build_lean_paper_manuscript --profile full
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m scripts.build_lean_paper_manuscript --profile current
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m scripts.build_jisa_latex --main-markdown manuscript_current_v2.md
& 'D:\TeXLive\texlive\2026\bin\windows\latexmk.exe' -xelatex -bibtex -interaction=nonstopmode -halt-on-error -file-line-error -cd 'E:\M3_PI_Guard_test\LaTeX通用模板\数模通用模板.tex'
& 'D:\TeXLive\texlive\2026\bin\windows\latexmk.exe' -xelatex -bibtex -interaction=nonstopmode -halt-on-error -file-line-error -cd 'E:\M3_PI_Guard_test\LaTeX通用模板\M3_PI_Guard_JISA\M3_PI_Guard_JISA.tex'
~~~

上述生成及两次最终编译均exit0。模板35页/40导航，正式27页/39导航；
共62页A4竖版、无旋转/越界/空白页、底部居中页码、空作者。
两份PDF的10个新增DOI与受保护缩写均可检索，参考文献各4页以及新增方法段实际渲染查看。
无缺字、未定义引用或Overfull；正式稿3处Underfull和Perl locale回退提示保留。
补充24页未重编译。技能附带PDF标记运行时此前不可用，本次继续既有TeXLive/PyMuPDF，
不声称附带工具通过。0新API、统计重算、原raw改写、权限变化或Full Harness。

可信度：9/10。实际文件、主来源、定向测试和PDF可复核；全文精读、外部独立评审和投稿确认未冒称完成。

## 2026-09-05 incremental update

The current manuscript cites 24 of 39 entries: the 21 previously reviewed
contexts below plus L37--L39. The 15 unused candidates are not printed. This
revision checks only the three newly activated primary records and abstract
claims; it is not a new full review of the earlier 21 sources.

| Key | Primary record and status | Checked manuscript use |
|---|---|---|
| L37 | [PIArena, ACL 2026](https://aclanthology.org/2026.acl-long.1533/), DOI 10.18653/v1/2026.acl-long.1533, pp. 33170--33192 | Abstract: unified attacks/defenses/benchmarks and defense-feedback adaptive evaluation; no performance figure imported. |
| L38 | [AgentDyn, arXiv v3](https://arxiv.org/abs/2602.03117v3), preprint, DOI 10.48550/arXiv.2602.03117 | Abstract: dynamic planning, open-ended tasks and helpful third-party instructions; not presented as completed M3 native evaluation. |
| L39 | [ASPI, arXiv v1](https://arxiv.org/abs/2605.17324v1), preprint, DOI 10.48550/arXiv.2605.17324 | Abstract: matched clarification/execution states; motivates a limitation, not a result for M3's controller-only approval channel. |

Titles, author lists, identifiers and publication status were checked against
these primary records. Active render: 24 resolved references, no uncited printed
items. The prior split becomes 12 formally published and 12 preprint sources.
Submission-date status refresh and institutional JCR verification remain open.

## Historical review of the earlier active set

Review date: 2026-08-23

Scope: the 21 references actually cited by `manuscript_deepseek_v1.md`. The
remaining 15 entries in `references_v1.bib` are a dormant candidate corpus and
are not rendered by citeproc; they were intentionally excluded from this
submission-focused review.

## Outcome

- All 21 in-text keys resolve to an entry in `references_v1.bib`.
- No bibliography item is rendered without an in-text citation.
- Eleven cited works have a formal conference or workshop publication record;
  ten are explicitly represented as preprints.
- Titles, author order, publication status, year, and stable landing page were
  checked against the publisher, conference, proceedings, or arXiv record.
- Five deterministic metadata defects were corrected across the pre-review and
  final-integrity passes:
  - `L02` (DRIFT): year corrected from 2026 to the official NeurIPS 2025
    proceedings year, and DOI `10.52202/085713-2791` added.
  - `L20` (AgentSpec): the unregistered DOI and unverified page range were
    removed; the citation now points to the official ICSE 2026 Research Track
    page.
  - `L08` (Contextual Agent Security): the first author's surname was corrected
    from `Bagdasarian` to `Bagdasaryan` to match the official Google Research
    record.
  - `L27` (The Attacker Moves Second): the `LLM` acronym was protected in the
    BibTeX title so citeproc cannot render it as `Llm`.
  - `L34` (Agent Security Bench): the entry type, `booktitle`, editors, page
    separator, and paper URL were aligned with the official ICLR proceedings
    BibTeX record.

## Active-source ledger

| Key | Short name | Status used in manuscript | Primary metadata source | Result |
|---|---|---|---|---|
| L01 | VIGIL | ACL 2026 long paper | [ACL Anthology](https://aclanthology.org/2026.acl-long.443/) | verified |
| L02 | DRIFT | NeurIPS 2025 conference paper | [NeurIPS Proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/77f3b26c7907aa27b207df9b9d43f29a-Abstract-Conference.html) | corrected and verified |
| L03 | Task Shield | ACL 2025 long paper | [ACL Anthology](https://aclanthology.org/2025.acl-long.1435/) | verified |
| L07 | StruQ | USENIX Security 2025 paper | [USENIX](https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe) | verified |
| L08 | Contextual Agent Security | HotOS 2025 workshop paper | [Google Research](https://research.google/pubs/context-is-key-for-agent-security/) | corrected and verified |
| L09 | AgentDojo | NeurIPS 2024 benchmark paper | [NeurIPS Proceedings](https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html) | verified |
| L10 | InjecAgent | ACL Findings 2024 paper | [ACL Anthology](https://aclanthology.org/2024.findings-acl.624/) | verified |
| L20 | AgentSpec | ICSE 2026 Research Track paper | [ICSE programme](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/29/AgentSpec-Customizable-Runtime-Enforcement-for-Safe-and-Reliable-LLM-Agents) | corrected and verified |
| L21 | ARGUS | 2026 preprint | [arXiv](https://arxiv.org/abs/2605.03378) | verified as preprint |
| L22 | AuthGraph | 2026 preprint | [arXiv](https://arxiv.org/abs/2605.26497) | verified as preprint |
| L23 | PlanGuard | 2026 preprint | [arXiv](https://arxiv.org/abs/2604.10134) | verified as preprint |
| L24 | Progent | 2025 preprint, revised 2026 | [arXiv](https://arxiv.org/abs/2504.11703) | verified as preprint |
| L25 | IPIGuard | EMNLP 2025 paper | [ACL Anthology](https://aclanthology.org/2025.emnlp-main.53/) | verified |
| L26 | CaMeL | 2025 preprint | [arXiv](https://arxiv.org/abs/2503.18813) | verified as preprint |
| L27 | The Attacker Moves Second | 2025 preprint | [arXiv](https://arxiv.org/abs/2510.09023) | verified as preprint |
| L30 | Spotlighting | 2024 preprint | [arXiv](https://arxiv.org/abs/2403.14720) | verified as preprint |
| L31 | Instruction Hierarchy | 2024 preprint | [arXiv](https://arxiv.org/abs/2404.13208) | verified as preprint |
| L32 | Indirect-injection detection | ACL 2025 long paper | [ACL Anthology](https://aclanthology.org/2025.acl-long.890/) | verified |
| L34 | Agent Security Bench | ICLR 2025 paper | [ICLR Proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5750f91d8fb9d5c02bd8ad2c3b44456b-Abstract-Conference.html) | verified |
| L35 | Provenance sensitivity audit | 2026 preprint | [arXiv](https://arxiv.org/abs/2607.20827) | verified as preprint |
| L36 | FAVA | 2026 preprint | [arXiv](https://arxiv.org/abs/2607.27267) | verified as preprint |

## Claim-fit check

The citations support the roles assigned to them in the manuscript: benchmark
descriptions cite the benchmark papers; runtime enforcement, task alignment,
privilege control, provenance, and data-flow statements cite the corresponding
method papers; the adaptive-attack motivation cites `L27`. No cited source is
used to claim that M3 is first, unique, state of the art, or universally
superior. Preprint-only mechanisms remain distinguishable from peer-reviewed
work through their BibTeX type and note.

All 21 active citations received a fresh citation-context check against an
official abstract, proceedings summary, conference page, or official preprint
PDF during the Stage 4.5 review. The checked roles were:

| Keys | Manuscript claim role | Context result |
|---|---|---|
| L01, L02, L03 | verify-before-commit, dynamic control/data constraints, and user-goal/tool-call alignment | supported by the official ACL/NeurIPS records |
| L07, L30, L31, L32 | structured input, spotlighting, instruction hierarchy, and indirect-injection detection | supported by USENIX, ACL, or the official preprints; used only as prompt/output-layer comparisons |
| L08, L20 | contextual policies and runtime rule enforcement | supported by the official Google Research and ICSE records |
| L09, L10, L34 | benchmark task/security framing | supported by the official AgentDojo, InjecAgent, and ICLR records |
| L21, L22, L23 | influence provenance, authorization/execution graphs, and isolated planning | supported by the official preprint records and kept explicitly preprint-only |
| L24, L25, L26 | privilege narrowing/approval, tool dependencies, and trusted control/data flow | supported by the official preprint PDF and ACL record |
| L27 | adaptive attacker motivation | supported by the official preprint and not used to claim saturation |
| L35, L36 | controlled source-authority sensitivity and formal evidence-backed authorization | supported by the official 2026 preprints |

No checked context attributes an isolated causal effect to the paper's bundled
policy/full comparison, and no context supports a first, only, SOTA, or
cross-provider-generalization claim.

An unauthenticated Semantic Scholar secondary cross-check was attempted but was
unavailable during the final-integrity pass. Following the review protocol, it
was not retried repeatedly; publisher, conference, proceedings, and arXiv
primary records controlled the decisions.

## Remaining submission gate

This review is complete for the current 21-key active set. It must be rerun only
if the manuscript adds or replaces a citation before submission. Institutional
verification of JISA's current SCIE/JCR quartile is a separate author-side gate
and is not established by this citation review.
