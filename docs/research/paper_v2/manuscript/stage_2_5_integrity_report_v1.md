# Stage 2.5 pre-review integrity report

Review date: 2026-08-23

Manuscript: `manuscript_deepseek_v1.md`

Paper route: authorization-regime and security-utility empirical study

Reviewer scope: submission-facing manuscript, its 21 active references, all
reported statistics, and the current 13-item claim-evidence ledger

## Verdict

**PASS with non-blocking author-side warnings.** The manuscript satisfies the
pre-review integrity gate for entry into scientific peer review:

- 21/21 active references have an official or stable primary landing page and
  publication-status check;
- 11/21 citation contexts (52.4%) were checked against official abstracts or
  proceedings summaries, exceeding the 30% threshold;
- every quantitative claim in the abstract, Results, Discussion, Conclusion,
  main tables, and figure captions was reconciled to a controlling result
  artifact;
- 37/111 eligible prose paragraphs (33.3%) were sampled for exact-phrase
  originality checks, exceeding the 30% threshold;
- ten affirmative empirical or implementation claims were verified, two
  overclaims remain explicitly forbidden, and one journal-indexing claim
  remains an author-side submission gate;
- all seven AI-research failure modes were checked;
- the principles-only RAISE checkpoint found no blocking research-integrity
  defect.

This verdict does not mean that the paper is submission-ready. Author names,
affiliations, declarations, the final data/code release state, and an
institutional check of JISA's submission-date SCIE/JCR quartile remain open.

## Phase A — reference existence and metadata

The audit covered the 21 references actually cited by the manuscript. Fifteen
dormant candidate entries in `references_v1.bib` were not treated as active
submission references.

| Key | Work | Primary record | Publication status | Result |
|---|---|---|---|---|
| L01 | VIGIL | ACL Anthology | ACL 2026 long paper | verified |
| L02 | DRIFT | NeurIPS Proceedings | NeurIPS 2025 paper | corrected earlier and verified |
| L03 | Task Shield | ACL Anthology | ACL 2025 long paper | verified |
| L07 | StruQ | USENIX | USENIX Security 2025 paper | verified |
| L08 | Contextual Agent Security | Google Research | HotOS 2025 workshop paper | author surname corrected and verified |
| L09 | AgentDojo | NeurIPS Proceedings | NeurIPS 2024 benchmark paper | verified |
| L10 | InjecAgent | ACL Anthology | ACL Findings 2024 paper | verified |
| L20 | AgentSpec | ICSE programme | ICSE 2026 Research Track paper | corrected earlier and verified |
| L21 | ARGUS | arXiv | 2026 preprint | verified as preprint |
| L22 | AuthGraph | arXiv | 2026 preprint | verified as preprint |
| L23 | PlanGuard | arXiv | 2026 preprint | verified as preprint |
| L24 | Progent | arXiv | 2025 preprint, revised 2026 | verified as preprint |
| L25 | IPIGuard | ACL Anthology | EMNLP 2025 paper | verified |
| L26 | CaMeL | arXiv | 2025 preprint | verified as preprint |
| L27 | The Attacker Moves Second | arXiv | 2025 preprint | verified as preprint |
| L30 | Spotlighting | arXiv | 2024 preprint | verified as preprint |
| L31 | Instruction Hierarchy | arXiv | 2024 preprint | verified as preprint |
| L32 | Indirect-injection detection | ACL Anthology | ACL 2025 long paper | verified |
| L34 | Agent Security Bench | ICLR Proceedings | ICLR 2025 paper | verified |
| L35 | Provenance sensitivity audit | arXiv | 2026 preprint | verified as preprint |
| L36 | FAVA | arXiv | 2026 preprint | verified as preprint |

The only new defect found in this review was `L08`: the official Google
Research record spells the first author's surname **Bagdasaryan**. The BibTeX
entry was corrected. Semantic Scholar was used only as a secondary index
cross-check. Where its indexed preprint year differed from an official venue
record, the publisher/proceedings record controlled the manuscript metadata.

## Phase B — citation-context fit

The structured context sample covered `L01`, `L02`, `L03`, `L21`, `L22`,
`L23`, `L24`, `L25`, `L26`, `L35`, and `L36` (11/21, 52.4%). It deliberately
spans the paper's central mechanism and evaluation claims:

| Claim role in manuscript | Checked sources | Finding |
|---|---|---|
| verify-before-commit and SIREN | L01 | official abstract supports both the mechanism framing and 959-item benchmark description |
| dynamic control/data constraints and memory isolation | L02 | official proceedings summary supports the paraphrase |
| user-goal/tool-call alignment | L03 | official abstract supports the task-alignment description |
| isolated planning and hierarchical tool/parameter validation | L23 | preprint abstract supports the bounded related-work description |
| symbolic tool/argument policies and approval for expansion | L24 | preprint abstract supports the bounded description |
| planned tool-dependency graph | L25 | ACL record supports the description |
| trusted control/data flows and capabilities | L26 | preprint abstract supports the description |
| permission IR, evidence graph, and pre-effect SMT checks | L36 | preprint abstract supports the description |
| influence-provenance graph | L21 | preprint abstract supports the description |
| authorization graph compared with provenance/execution graph | L22 | preprint abstract supports the description |
| controlled source-authority sensitivity audit | L35 | preprint abstract supports the description |

No checked citation was used to support a broader claim than its source. The
manuscript consistently labels preprints as preprints and does not use any
source to claim that M3 is first, unique, state of the art, or universally
superior.

## Phase C — numerical and result integrity

All submission-facing numbers were checked once against the controlling
artifacts. No historical evidence chain or Full Harness was replayed.

| Evidence block | Controlling artifact(s) | Reconciled facts |
|---|---|---|
| Frozen lean design | `lean_empirical_execution_plan_v1.jsonl`, `lean_empirical_execution_manifest_v1.json` | 1,350 unique work items; DeepSeek 900 and Gemini 450; correct condition and case strata |
| DeepSeek authorization study | `authorization_results_deepseek_v1.json`, Tables 2–5 | 900 terminal work items; 768 completed; 132 ITT failures/status exceptions; 0 online forbidden fields; 0 provider tools/effects |
| Main authorization endpoints | Tables 2–3 | unsafe effects 0/100, 0/100, 1/100, 0/100; benign-tool completions 16/60, 7/60, 22/60, 9/60; all paired differences, Wilson intervals, McNemar tests, cluster-bootstrap intervals, and Holm values match |
| Runtime burden | Table 4 | ASK, DENY, failure incidence, p50/p95 latency, token counts, and CNY 1.3888324 total cost match |
| Stress regimes | Tables 2–3 | broad/conflicting/underspecified each 0/30 unsafe; benign-tool completion 2/20, 1/20, 2/20; paired utility differences -25, -30, -25 percentage points match |
| Medium falsification study | `admitted_medium_analysis_v8.json`, `existing_results_analysis_v1.json` | 480 records; endpoint counts and paired security/utility statistics match |
| Public DeepSeek V4 Pro | `public_primary_analysis_summary_v5.json`, `existing_results_analysis_v1.json` | 5,082 records; full/policy/structural attack counts 38/600, 13/600, 133/600 and benign-tool counts 49/168, 49/168, 103/168 match |
| Public DeepSeek V4 Flash | `existing_results_analysis_v1.json` | 1,791 records; attack counts 24/400, 12/400, 47/400 and benign-tool counts 38/145, 35/145, 82/145 match |
| Adaptive 50/200 | `summary.json`, Table 6 | 40 tasks; first unsafe effect for 4/40 by 50 and 18/40 by 200; 7,478 terminal queries match |
| Gemini stopping rule | `authorization_results_v1.json`, Gemini raw records | 32/450 terminal, 5 response-bearing, 83 observed nonterminal, 335 unstarted, 418 pending, 8 official response IDs, USD 0; cross-provider inference disabled |

The manuscript correctly keeps all terminal outcomes in the intention-to-treat
denominator, distinguishes event totals from record incidence, and limits the
adaptive conclusion to the two observed budget points. No result-hallucination
or denominator drift was found.

## Phase D — originality sample

The body before the figure/table appendix contained 111 eligible prose
paragraphs after excluding headings, tables, lists, code, images, and short
fragments. Systematic selection of every third paragraph yielded 37 paragraphs
(33.3%). A characteristic exact phrase from each sampled paragraph was searched
against the public web; none returned an exact external match.

This is a plagiarism-risk screen, not proof of universal textual originality.
An author-specific self-plagiarism search was not executable because the
submission draft does not yet contain author identities or an author-owned
publication list. That check remains an author-side finalization item.

## Phase E — claim-evidence verification

The 13-item lean claim ledger was reviewed claim by claim. Ten affirmative
claims have direct evidence; the remaining three are intentionally constrained.

| Claim | Disposition | Evidence judgment |
|---|---|---|
| LC01 online evaluator/gold isolation | verified | runner projection, manifest, unit tests, and result integrity fields agree |
| LC02 near-floor main-cell unsafe effects | verified | Table 2 and paired Table 3 agree |
| LC03 exact authorization reduced benign-tool completion | verified | raw counts and paired effects agree |
| LC04 exact authorization changed ASK/DENY/failure/latency burden | verified | Table 4 agrees |
| LC05 no stable independent full-module benefit | verified negative result | authorization, medium, and Public evidence point in the stated bounded direction |
| LC06 unfavorable full-vs-policy direction in Pro and Flash | verified within provider | Public Pro and Flash counts agree; no cross-provider claim |
| LC07 benchmark/family heterogeneity reported separately | verified descriptive | Table 5 contains the prespecified strata |
| LC08 adaptive first successes between 50 and 200 | verified | first-success table and task-level summary agree |
| LC09 provider identity, response IDs, ITT and isolated effects retained | verified | raw records, runner, and integrity summary agree |
| LC10 cross-provider generalization | forbidden | Gemini stopping rule closed incomplete; manuscript does not make this claim |
| LC11 first/only/SOTA/universal superiority | forbidden | manuscript explicitly rejects these claims |
| LC12 submission-date JISA SCIE/JCR Q2 | pending author gate | requires institutional verification immediately before submission |
| LC13 active-reference metadata and sampled context review | verified | 21/21 metadata and 11/21 context checks recorded |

## Seven AI-research failure modes

| Failure mode | Disposition | Basis |
|---|---|---|
| 1. Implementation bug presented as a result | clear within scoped paths | online projection, evaluator, statistics, and provider record paths have focused tests and direct artifact reconciliation; no endpoint-changing defect was found |
| 2. Citation hallucination or metadata drift | clear after correction | all active references resolve to primary records; the one L08 surname defect was corrected before review |
| 3. Fabricated or unsupported numerical result | clear | every submission-facing statistic was reconciled to its controlling artifact |
| 4. Shortcut reliance mistaken for mechanism value | clear for current claims, external-validity warning | policy-only ablation and authorization stress regimes expose shortcut risk; lack of independent blind data is disclosed |
| 5. Bug or anomaly reframed as novelty | clear | the negative full-vs-policy direction is treated as bounded empirical evidence and alternative explanations are stated; it is not promoted as a new mechanism |
| 6. Fabricated methodology or protocol details | clear | reported sample sizes, strata, conditions, retry rules, failure denominators, and provider boundaries match the frozen plan and runner |
| 7. Frame lock / refusal to revise the research claim | clear | the project explicitly abandoned a leading-defense/SOTA route and adopted an empirical security-utility study consistent with the observed results |

## RAISE principles-only checkpoint

This is primary empirical research, so the RAISE check is advisory rather than
a substitute for institutional policy.

| Principle | Status | Assessment |
|---|---|---|
| Human oversight | warning | author names, roles, final declarations, and accountable sign-off are not yet populated |
| Transparency | pass with finalization item | model/provider use, stopping rules, failures, and diagnostic-only Gemini scope are disclosed; author-side AI-use wording still needs final approval |
| Fit for purpose | pass | a medium falsification stage, frozen paired design, policy-only ablation, stress regimes, and prespecified failure handling match the research questions |
| Privacy and security | pass | secrets and prompt/response content are excluded from the manuscript; provider tools and real external effects remain disabled |
| Fairness and generalizability | warning | inferential evidence is DeepSeek-only; the manuscript explicitly withholds cross-provider generalization |
| Accountability | warning | final author metadata, CRediT roles, competing-interest/funding statements, and institutional journal check are outstanding |
| Reproducibility | pass with release item | code, frozen plan, raw compact records, statistical outputs, and builders exist; the public-release state must be finalized before submission |

## Corrections made in this gate

1. Corrected `L08` first-author surname from `Bagdasarian` to `Bagdasaryan` in
   `references_v1.bib`.
2. Updated the active-citation compliance ledger to record the correction,
   the 11/21 context sample, and the rule that official venue metadata controls
   over discovery-index preprint dates.
3. Narrowed `LC13` so it accurately states 21/21 metadata verification and an
   11/21 citation-context sample rather than implying exhaustive context review.

## Rebuild and focused document QA

- Rebuilt the English Word review draft: 283 paragraphs, 7 tables, 5 figures,
  and 21 citeproc bibliography entries.
- Rebuilt the Simplified Chinese comparison draft: 249 paragraphs, 7 tables,
  5 figures, and the same 21-entry citation corpus.
- Focused manuscript/DOCX/supplement tests: 20 passed.
- Ruff and `py_compile`: passed for the affected builders and tests.
- Accessibility audit for each DOCX: 0 high, 0 medium, 21 low findings; all
  low findings are raw DOI/URL display text in the bibliography.
- Structural checks confirm Letter pages, one-inch margins, five embedded
  figures, seven tables, no raw citation tokens, no replacement glyphs, and
  the corrected `Bagdasaryan` spelling.
- Visual pagination is not claimed. LibreOffice/`soffice` is absent, and the
  read-only WPS fallback rejected its run because it could not isolate a clean
  process set while user-owned WPS processes were active. No WPS process was
  terminated and no render artifact is retained as a paper deliverable.

## Remaining gates before submission

- populate author names, affiliations, corresponding-author details, and CRediT roles;
- finalize funding, competing-interest, ethics/not-applicable, data/code, and AI-use declarations;
- run an author-owned self-plagiarism check once author identities are supplied;
- verify JISA's submission-date SCIE coverage and JCR quartile through an authorized institutional source;
- complete scientific peer review and the subsequent revision gate;
- decide and document the public repository/data release state.

No additional API experiment, Full Harness run, recursive evidence replay,
blind-study execution, or historical hash package is required by this integrity
gate.
