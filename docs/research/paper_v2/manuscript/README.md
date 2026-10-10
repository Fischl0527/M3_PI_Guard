# 论文工作区：当前主稿、对照稿与历史材料

更新：2026-10-09。状态：`current_corrected_evidence_integrated_submission_in_progress`。论文功能 F-PAPER-002 未结项，不等于可直接投稿。

## 1. 今天应该打开哪一份

先看[论文中文阅读说明](论文中文阅读说明.md)：解释研究问题、900/480/16与60任务复核的关系，以及表格中的配置、区间、失败和未知。正文中的英文配置名另见[中文术语表](术语表_中文.md)。2026-10-10只改中文阅读与显示词，没有重编PDF；下面页数仍是既有回执。

| 用途 | 文件 | 说明 |
|---|---|---|
| 当前英文主文章 | [manuscript_current_v2.md](manuscript_current_v2.md) | 最新记录：正文 8,256 词，当前四图、四表 |
| 当前中文内容对照 | [manuscript_current_zh_v2.md](manuscript_current_zh_v2.md) | 项目组理解与作者核对，不是投稿语言版本 |
| 查看主稿实际构建与检查 | [2026-10-08 收束报告](current_manuscript_closeout_2026-10-08.md) | 页数／词数以报告顶部后续修订记录为准，下方旧节点回执保留 |
| 正式 LaTeX 主入口 | [M3_PI_Guard_JISA.tex](../../../../LaTeX通用模板/M3_PI_Guard_JISA/M3_PI_Guard_JISA.tex) | 正文采用 elsarticle；同目录的正式 PDF 最新记录为27页 |
| 本地模板审阅入口 | [数模通用模板.tex](../../../../LaTeX通用模板/数模通用模板.tex) | 最新模板 PDF 35 页；不是把数模模板当成期刊格式要求 |
| 历史补充材料 | [supplementary_tables_v1.md](supplementary_tables_v1.md) | S1–S20 与五幅历史补充图；补充 PDF 24 页沿用既有检查 |
| 含历史细节的完整英文稿 | [manuscript_deepseek_v1.md](manuscript_deepseek_v1.md) | 与当前精简主文章分开，不是第二份当前主稿 |
| 含历史细节的完整中文稿 | [manuscript_zh_v1.md](manuscript_zh_v1.md) | 历史工作对照稿 |

上述页数、词数和编译结果来自已记录的 2026-10-08 修订，本次文档整理没有重建 PDF、重新数正文词数或修改稿件。作者信息仍为空。

当前工作标题：

> Evaluating Authorization Regimes and Runtime Guardrail Configurations for Tool-Using LLM Agents

不恢复“首个”“唯一”“SOTA（当前最好）”、完整模块领先或跨厂商泛化声明。

## 2. 当前文章依据哪些结果

修复后的 900 条授权制度执行、16 条合成组件控制、480 条同期校准，以及 60 个良性任务的事后解释性复核。数据目录和各自限制见 [当前研究入口](../README.md)及[证据索引](../../../证据索引.md)。

旧 Public、E1–E6、旧端点和旧模型身份仍保留在完整工作稿与补充材料中。不能把它们拼成修复版的同期验证，也不能把 60 个任务的既有 240 条记录误写成新增执行。

当前主要结果包括明显的效用损失、事件稀少和区间不确定性；不是已经证明防御优越。带离线目标信息的权限对照、适配版 VIGIL、事后复核和未知状态的限制必须保留。

## 3. 作者接下来需要核对什么

- [投稿检查清单](jisa_submission_checklist.md)：以顶部当前清单为准，下面保留的九月清单仅为历史节点。
- [作者待填信息](author_metadata_and_submission_inputs.md)／[中文待填信息](author_metadata_and_submission_inputs_zh.md)：姓名、排序、单位、通讯作者、资助及相关声明由作者本人填写。
- [活动引用检查](citation_compliance_active_v1.md)：现有 24 项活动引用的元数据和主张对应检查；不能等同于 24 篇文献的独立全文审查。
- [声明草稿](declarations_draft.md)及[投稿声明](submission_statements_draft.md)：需作者批准，不替作者推断伦理审批、利益冲突或资助。
- [Cover Letter 草稿](cover_letter_draft.md)与[Highlights](highlights_v1.md)：保留草稿，投稿前需与当前文章及官方要求一起核对。
- [术语说明](术语表_中文.md)：英文专业词的解释。
- [Devil’s Advocate 内部审查](devils_advocate_review.md)：历史内部问题清单，不是期刊审稿意见。

正式投稿前须确认当期期刊要求、学校数据库的 SCIE/JCR Q2、作者信息、代码／数据公开方案和最终上传文件。本次未进行这些外部核验。

## 4. 怎样构建，避免选错稿件

仅在确实要修改或构建论文时，从仓库根目录显式选择 current 配置：

~~~powershell
python -X utf8 -B -m scripts.build_lean_paper_manuscript --profile current
python -X utf8 -B -m scripts.build_jisa_latex --main-markdown manuscript_current_v2.md
~~~

这些命令会写入生成稿件，不是只读检查，本次没有运行。完整编译步骤见 [LaTeX 说明](../../../../LaTeX通用模板/README.md)。

默认构建仍保留完整工作稿的兼容行为，不能把默认输出误当作当前精简文章。独立补充 LaTeX 入口为 `M3_PI_Guard_JISA_supplement.tex`；不要为了更新入口说明重跑历史统计。

## 5. 源稿、机器状态和历史文件的位置

- 源章节：`introduction_draft.md`、`related_work_draft.md`、`methods_draft.md`、`results_shell.md`、`discussion_draft.md`、`conclusion_draft.md` 等；它们是构建来源，不是六套独立的最终论文。
- 参考文献：[references_v1.bib](references_v1.bib)。未被当前文章引用的候选不应误报为活动引用数量。
- 主张台账：[claim_evidence_ledger_lean_v1.json](../../../../harness/state/paper_v2/claim_evidence_ledger_lean_v1.json)；历史台账、完成评分 JSON 也在 [harness/state/paper_v2/](../../../../harness/state/paper_v2/)，不再放在文档目录。
- 当前主图：[manuscript_figures/](../../../../outputs/experiments/research_followup_20261006_v1/manuscript_figures/)。
- 构建检查与预览：`outputs/manuscript/checks/`、`outputs/manuscript/previews/`；预览不是新的科研证据。
- [旧图表计划](figure_table_plan.md)、[历史全部引用检查](full_citation_refresh_v1.md)、[先前 usability 修订](usability_manuscript_update_v1.md)以及九月 Word 评阅副本均保留历史用途。它们的旧页数、表图数和待办不能覆盖当前入口。
- Word 稿不随本次整理更新；论文格式来源为 LaTeX，不能继续用旧 Word 页数报告今天的稿件状态。

本目录仍保留研究演进记录，但没有新的盲测、Gemini 正式矩阵、80 分门槛或 Full Harness 任务。
