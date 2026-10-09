# JISA submission readiness checklist

## 当前清单（2026-10-09）

这是对已有状态的文档更新，不是本日重新核验期刊或编译论文。当前主稿为
[英文 current v2](manuscript_current_v2.md)及[中文对照](manuscript_current_zh_v2.md)。
最新已记录版本为英文正文8,256词、本地模板35页、正式LaTeX27页，作者信息为空。

- [x] 当前正文区分修复后的900条授权执行、480条同期校准、16条组件控制及60任务事后复核。
- [x] 旧Public/E1–E6证据保留其原配置、端点与局限，没有替代当前修复版验证。
- [x] 当前主文章四图、四表；历史补充20表、5图分开保存。
- [x] 已有24项活动引用检查记录；不声称本轮重新核验文献全文。
- [x] 没有恢复机制领先、first/only/SOTA、日期重复性或跨厂商泛化声明。
- [ ] 作者本人填写姓名、单位、排序、通讯作者、资助、利益冲突、CRediT及相关批准。
- [ ] 完成数据／代码可用性与实际公开安排，区分内部模型请求和公开结果。
- [ ] 投稿当天通过学校或授权数据库确认SCIE/JCR Q2，并检查官方最新格式要求。
- [ ] 作者批准最终英文稿、补充材料、Highlights、Cover Letter和生成式AI声明。
- [ ] 最终上传包制作与提交前检查；已有PDF通过不等于此项已经完成。

盲测、完整Gemini矩阵、80分评分门槛和Full Harness不属于当前投稿清单。
需要入口和构建方式时看[论文工作区说明](README.md)。

## 历史清单（以下为2026年9月节点原文）

下文的勾选、21引用、旧Word页数和E1–E6条件只描述当时的版本；
不能解释为当前修复版已通过所有科学或投稿门槛。旧期刊要求亦须在投稿日复核。

Status: `incremental_e1_e6_integrated_final_author_review_pending`
Checked: 2026-09-04

## Venue fit

- [x] The official JISA scope includes authentication/access control, security
  management and policies, and practice-driven information-security
  applications. The paper is framed as runtime authorization and enforcement
  for tool-using agents, not as a general NLP jailbreak paper.
- [x] The journal has hosted collections on large-language-model cybersecurity
  and security/privacy in large AI models. This supports topical fit but does
  not guarantee editorial admission.
- [x] The official scope excludes routine application of existing AI/ML to a
  standard security dataset. The manuscript therefore leads with the
  authorization-regime evaluation method, executed-effect endpoint, paired
  runtime comparison, and security–utility/operational trade-off—not with
  off-the-shelf model benchmarking.
- [x] The submission target remains the regular Journal of Information Security
  and Applications track unless an open, applicable collection is confirmed at
  submission.
- [ ] An authorized institutional user must verify that the journal is SCIE and
  JCR Q2 on the actual submission date. Public or third-party metrics are not
  sufficient for the final claim.

Official sources:

- Journal scope:
  https://www.sciencedirect.com/journal/journal-of-information-security-and-applications
- Guide for authors:
  https://www.sciencedirect.com/journal/journal-of-information-security-and-applications/publish/guide-for-authors
- Article collections:
  https://www.sciencedirect.com/journal/journal-of-information-security-and-applications/special-issues

Current official format requirements checked on 2026-08-23:

- JISA uses single-anonymized review, so the submission does not require a
  separate author-blinded manuscript variant;
- the abstract must not exceed 250 words;
- 1–7 English keywords are required; and
- 3–5 highlights are recommended, each no longer than 85 characters;
- sections and subsections use 1, 1.1 and 1.1.1 numbering;
- Word source is editable, single-column `.doc`/`.docx` (or editable LaTeX);
- a data-availability statement is required and the journal's Option C data
  policy calls for repository deposit or an explanation of non-availability;
  and
- any required generative-AI declaration appears in its own section before the
  references;
- the title page supplies author names/order, full affiliations, corresponding
  author contact details and any present/permanent address; and
- a separate glossary plus an editable biography (100 words maximum) and
  passport-type photograph for each author are requested.

The abstract and five-highlight file satisfy these bounds. Gemini's
prespecified stopping rule is closed without a cross-provider claim.

## Scientific gates before manuscript completion

- [x] The 480-record medium falsification study is complete and admitted.
- [x] The mechanism route or empirical-study redirect is selected by the frozen
  gate, without removing unfavorable results.
- [x] Existing Public Pro 5,082, Public Flash 1,791, medium 480 and Adaptive
  budget-50/200 evidence has received one compact reuse analysis.
- [x] The frozen 900-row DeepSeek authorization study is terminal, including
  explicit failed-row disposition.
- [x] The 450-row Gemini diagnostic cross-provider study is terminal, or has
  transparently downgraded after the three-quota-day free-tier rule.
- [x] E1--E4 are complete: 720 Pro factorial rows, 240 Pro source-authority
  rows plus 480 offline Guard decisions, 240 outcome-enriched Pro rows and 360
  Flash replication rows.
- [x] E5 finished all twelve selected B200 survivors and received one-pass
  conditional-tail analysis: 0/12 new first successes through 500, with a
  24.25% Wilson upper limit. A complete original-panel B500 curve, budget
  2,000, blind study and full second-model adaptive panel remain out of scope.
- [x] E6 completed its 360-row DeepSeek risk-enriched single-block calibration;
  no-defense activity was 17/60. This observed block activity neither satisfies
  nor tests the original multi-window gate, and 47/60 tasks overlap E3. The
  separately executed Gemini prefix failed its technical gate; its nested set
  overlaps E3 for 29/30 tasks, so all Gemini effects remain not estimable.
- [x] Rebuild every current incremental numeric claim once from the five compact
  E1--E5 artifacts and the E6-v2 analysis; do not rerun provider rows.
- [x] All 21 active citations have complete authors, title, year, DOI or stable
  URL, publication-status verification, and a reviewed claim context. The 15
  unused BibTeX candidates do not render and require review only if activated.

## Journal package

- [x] Number sections and subsections; do not number the abstract.
- [x] Provisional title, abstract, keywords and highlights contain no unsupported
  first/only/SOTA wording.
- [x] Prepare the five highlights as a separate editable Word file; each item is
  at most 85 characters.
- [ ] Upload the manuscript, the separate editable supplementary-tables file,
  and all other required editable source files.
- [x] Retain the five completed incremental figure triplets as separate vector
  PDF, editable SVG and PNG previews; E6 is integrated as Table 6 rather than a
  misleading Gemini effect figure.
- [ ] Prepare the competing-interests declaration in the format requested by
  the submission system.
- [ ] Record funding sources and sponsor roles, or the journal’s recommended
  no-specific-funding statement.
- [ ] Finalize author order and obtain every author’s approval before
  submission.
- [x] Prepare a structured title-page/author-input template covering names,
  full affiliations, corresponding-author details, CRediT, declarations and
  release metadata; an equivalent Chinese direct-fill companion is provided,
  while author-owned values remain unfilled.
- [x] Prepare a separate glossary of the field-specific terms used in the
  manuscript, including a separate editable Word copy for upload if requested.
- [ ] Supply a biography of at most 100 words and a separate passport-type
  photograph for every author.
- [x] Add a provisional research-data/code-availability statement and repository
  link; replace the private-review wording with the archival DOI or immutable
  public release identifier before publication.
- [x] Add the required generative-AI-use declaration before the references
  using the guide's manuscript-preparation-process section title.
  Human authors retain full responsibility for literature verification,
  analysis, interpretation and manuscript content; all authors must confirm
  the wording before submission.
- [x] Prepare a provisional cover letter focused on the security problem,
  verified contribution, benchmark breadth and practical relevance. Add the
  corresponding-author details and submission date to the separate editable
  Word copy before submission.
- [x] Run the targeted E1--E6 claim–evidence, figure/table and manuscript build
  checks. The 2026-08-23 Stage 4.5 report remains historical and is not treated
  as E1--E6 verification.
- [ ] Complete the author-owned similarity/self-plagiarism check after author
  identities and publication lists are available.
- [x] Rebuild and visually inspect the incremental Word package after six main
  tables and twelve supplementary tables are integrated. Read-only WPS renders
  passed page-by-page review for the 35-page English manuscript, 30-page Chinese
  comparison and 4-page supplement. Author-owned fields remain intentionally
  unfilled and require a final author check.

## Current prohibition

The earlier Gemini study closed at 32/450 terminal work items with only five
responses. The E6 Gemini prefix adds five response-bearing records, one
response-less failure and 174 administrative closures; it does not create an
effect estimate. No cross-provider abstract, conclusion, cover-letter or result
claim may fill unobserved Gemini cells. JCR Q2/SCIE status must still be checked through the
institution on the actual submission date, and author-owned submission fields
remain incomplete.
