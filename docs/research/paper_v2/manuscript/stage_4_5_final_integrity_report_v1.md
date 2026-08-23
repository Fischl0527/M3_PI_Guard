# Stage 4.5 final integrity report

Review date: 2026-08-23

Active manuscript: `manuscript_deepseek_v1.md`

Paper route: authorization-regime and security–utility empirical study

## Decision

**PASS with non-blocking author and institutional warnings.** No unresolved
high- or medium-severity research-integrity defect remains in the current
submission-facing manuscript. The manuscript may proceed to the author-owned
submission-preparation stage only after explicit author confirmation.

This decision does not mean that the package is ready to upload. Author names,
affiliations, corresponding-author details, CRediT roles, competing-interest and
funding declarations, author-owned similarity/self-plagiarism review, final
page-by-page Word/WPS inspection, public-release identifiers, and an
institutional submission-date JISA SCIE/JCR Q2 check remain open.

No provider/API call, new experiment, Full Harness, historical evidence replay,
blind study, budget-500/2,000 attack, successful-row rerun, or real external
effect was performed during this gate.

## A. Active-reference verification: 21/21

All 21 references actually cited by the manuscript were re-opened on an
official publisher, conference, proceedings, research-group, or arXiv record.
All active citation contexts were checked, rather than sampled.

| Keys | Primary record | Context checked | Result |
|---|---|---|---|
| L01, L03, L10, L25, L32 | ACL Anthology | verification, alignment, benchmark, dependency-graph and detection claims | verified |
| L02, L09 | NeurIPS Proceedings | dynamic control/data constraints, memory isolation and AgentDojo benchmark framing | verified |
| L07 | USENIX Security | structured instruction/data channels | verified |
| L08 | Google Research | contextual policy generation and enforcement | verified |
| L20 | official ICSE 2026 programme plus author paper | runtime-rule DSL and publication identity | verified; non-resolving DOI not used |
| L34 | official ICLR Proceedings and BibTeX | ASB benchmark scope and complete proceedings metadata | corrected and verified |
| L21–L24, L26–L27, L30–L31, L35–L36 | official arXiv records/PDFs | provenance, authorization, planning, privilege, data flow, adaptive attack and sensitivity claims | verified as preprints |

The final pass corrected two active bibliography details: `L27` now preserves
the `LLM` acronym, and `L34` now follows the official ICLR `@inproceedings`
record with booktitle, editors, pages and paper URL. Semantic Scholar's
unauthenticated API was unavailable; the protocol-directed fallback to primary
records was used without repeated retries. No reference fabrication or
claim-context mismatch was found.

## B. Citation-context fit: 21/21

The manuscript uses the active sources for bounded roles only:

- benchmark papers support benchmark and endpoint context;
- runtime papers support verify-before-commit, task alignment, privilege,
  dependency, provenance, control/data-flow, or authorization descriptions;
- prompt/output defenses are not described as executed-effect guarantees;
- preprints remain identifiable as preprints;
- the adaptive-attack citation motivates budget sensitivity but does not support
  a saturation claim; and
- no source is used to claim first, only, SOTA, universal superiority, an
  isolated M3 component effect, or cross-provider generalization.

## C. Numerical and claim-evidence reconciliation

Submission-facing claims were grouped into 24 nonredundant numerical/evidence
families and checked once against the current compact result artifacts. Repeated
instances in the Abstract, Results, Discussion, Conclusion, tables and figure
captions were reconciled to the same controlling value.

| Claim family | Controlling evidence | Result |
|---|---|---|
| Evidence union and cohort overlap | `existing_results_analysis_v1.json` | 7,353 condition-level records, 902 distinct cases and overlap accounting verified |
| Medium falsification study | admitted medium summary and compact reuse analysis | 480 total, 432 primary and 48 probes; security/utility gate wording verified |
| Public V4 Pro endpoints | compact reuse analysis | 5,082 records; attack 38/600 full, 13/600 policy, 133/600 structural; benign-tool 49/168, 49/168, 103/168 verified |
| Public V4 Flash endpoints | compact reuse analysis | 1,791 records; attack 24/400, 12/400, 47/400 and benign-tool 38/145, 35/145, 82/145 verified |
| Adaptive first success | Table 6 and compact reuse analysis | 4/40 by budget 50 and 18/40 by budget 200 verified; no saturation claim |
| Lean design and terminal accounting | frozen plan, manifest and authorization result JSON | 180 paired cases, 900 work items, 933 physical attempts, 900 ITT work keys and 33 recovery rows verified |
| Online-state/effect safety | authorization result integrity fields | forbidden online fields, provider tools and real external effects all zero |
| Main attack cells | Tables 2–3 | 0/100, 0/100, 1/100 and 0/100 verified with reported paired tests/intervals |
| Pooled benign-tool TCR | Tables 2–3 | policy 22/60 to 9/60 (−21.67 pp); full 16/60 to 7/60 (−15.00 pp) verified |
| Benchmark reversal | Table 5 and structured result JSON | AgentDojo +13.33/+10.00 pp; M3-v2 −56.67/−40.00 pp verified |
| Failure-sensitive attack bound | Table 5 and structured result JSON | policy 7/100 to 25/100; full 8/100 to 26/100; AgentDojo +36 pp and M3-v2 0 verified |
| Stress regimes | Tables 2–3 | broad/conflicting/underspecified benign completion −25/−30/−25 pp; 0/30 unsafe effects each verified |
| Runtime burden | Table 4 and supplementary stratified table | ASK/DENY/failure incidence, event totals and p50/p95 values verified without conflating incidence and counts |
| Provider identity/cost | raw compact records and authorization summary | response identifiers/returned aliases retained; CNY 1.3888324 lean total and zero Gemini paid cost verified |
| Gemini stopping boundary | combined authorization summary | 32/450 terminal, 5 response-bearing, 83 observed nonterminal, 335 unstarted; diagnostic only verified |

The remaining families comprise the reported Wilson limits, exact McNemar
values, Holm corrections, 10,000-task-cluster bootstrap intervals, no-tool
utility, Public diagnostic incidence, Public operational status distributions,
canary accounting, and response/call totals. All match the controlling JSON/CSV
artifacts. No denominator drift, unsupported number, or conversion of failure
into a safety success was found.

## D. Claim-boundary corrections

The audit found and corrected two genuine claim-ledger defects:

1. `LC05` still described the full package as isolated provenance/data-flow/
   confirmation extensions. It now states the observed configuration-package
   result and explicitly forbids component attribution because prompt profile
   and runtime modules change together.
2. `LC07` pointed to a nonexistent `table_5_heterogeneity.csv`. It now points to
   `table_5_benchmark_stratified.csv` and the structured authorization result
   artifact that retains attack-family strata.

The same package wording was corrected in the English Related Work section and
the Chinese comparison manuscript. `LC13` now records the completed 21/21
active-context review.

## E. Originality and plagiarism-risk screen

The reproducible Stage 4.5 parser identified 144 eligible prose/list blocks
before the figure appendix. All 73 blocks changed since the Stage 2.5 baseline
were checked (50.7% coverage and 100% of revised blocks). Quoted ten-token
search fragments produced zero potential exact matches. The complete query
ledger is in `stage_4_5_originality_audit_v1.md`.

This is a public-web discovery screen, not an iThenticate/Turnitin certificate.
Author-specific self-plagiarism review could not be run because author names
and publication lists are not yet present. That remains a mandatory author-side
submission item. A qualitative AI-style scan found no materially triggered
formulaic-transition, repetitive-summary, unexplained-polish, fake-quotation,
generic-citation, or semantic-duplication pattern; this judgment is heuristic.

## F. Seven AI-research failure modes

| Failure mode | Disposition | Basis |
|---|---|---|
| Implementation bug presented as result | clear within scoped paths | result tables/JSON, manuscript values and current focused builders agree; no endpoint-changing defect found |
| Citation hallucination or metadata drift | clear after correction | 21/21 active primary records and contexts checked; L27/L34 corrected |
| Fabricated or unsupported result | clear | all numerical claim families trace to current compact artifacts |
| Shortcut reliance mistaken for mechanism value | clear for bounded claim; external-validity warning | policy/full treatment is reported as bundled and benchmark/failure sensitivities are explicit |
| Bug/anomaly reframed as novelty | clear | negative package result and operational failures are disclosed, not promoted as mechanism novelty |
| Fabricated methodology/protocol detail | clear | sample sizes, regimes, ITT, stopping and provider boundaries match the frozen design and runner |
| Frame lock | clear | the leading-defense route was abandoned after falsification and peer review; the current title/claims follow the evidence |

## G. RAISE principles-only checkpoint

RAISE is applied here only as an advisory principles check for primary research,
not as a claim of systematic-review-framework compliance.

| Principle | Status | Assessment |
|---|---|---|
| Human oversight | warn | author responsibility is stated, but identities, roles, declarations and final sign-off are still missing |
| Transparency | pass | provider/model scope, AI-assisted preparation, stopping rules, failures and diagnostic-only Gemini status are disclosed |
| Reproducibility | pass | frozen selections, compact records, deterministic analyses, tables, figures and builders exist; provider-alias limits are disclosed |
| Fit for purpose | pass | paired authorization treatment, package comparison, failure sensitivity, benchmark strata and budget-50/200 evidence answer the bounded RQs |

Overall Schema-12 compliance decision: `warn`, non-blocking for primary
research, with user action required for the author-owned gates.

## H. Focused verification and document QA

- Initial current-paper test batch: 41 passed. Three additional failures came
  from superseded 34-entry historical bibliography/hash tests, including a test
  that requires a currently non-resolving AgentSpec DOI. Those legacy contracts
  were not used to roll back the active bibliography and were not replayed.
- Corrected current active-reference selection: five affected tests passed,
  covering the 21-key set, citation resolution, English DOCX references,
  Chinese/English citation parity, and Chinese DOCX structure/fonts.
- English Word draft: 298 paragraphs, 7 tables and 5 figures.
- Chinese comparison Word draft: 251 paragraphs, 7 tables and 5 figures.
- Accessibility: both Word files report 0 high, 0 medium and 21 low findings;
  all low findings are raw reference URL display text.
- LibreOffice/`soffice` and Poppler are unavailable in the current environment.
  The standard page-render gate therefore could not run. Structural QA passed,
  but page-level visual QA is not claimed.

## Mandatory author checkpoint

Stage 4.5 is complete. Do not automatically advance to Stage 5. The author must
explicitly confirm continuation and provide or resolve:

1. author names/order, affiliations and corresponding-author details;
2. CRediT, funding and competing-interest declarations;
3. biography/photo requirements;
4. author-side similarity/self-plagiarism report;
5. final Word/WPS page-by-page visual approval;
6. public data/code release identifiers; and
7. institutional verification that JISA is SCIE/JCR Q2 on the submission date.
