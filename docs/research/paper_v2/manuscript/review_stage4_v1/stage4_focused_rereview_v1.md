# Stage 4 Focused Scientific Re-review

## Scope

This internal re-review checks only whether the Stage 3 P0/P1 commitments were
closed in the revised English manuscript and its derived tables/figures. It is
not an Elsevier or JISA review and does not reassess immutable experiment rows.

## Mechanical score matrix

| Perspective | D1 methodology | D2 domain | D3 coherence | D4 relevance | D5 writing |
|---|---|---|---|---|---|
| Editor-in-Chief | pass | pass | pass | pass | pass |
| Methodology/statistics | pass | pass | pass | pass | pass |
| LLM-agent security domain | pass | pass | pass | pass | pass |
| Usable-security perspective | pass | pass | pass | pass | pass |
| Devil's Advocate | pass | pass | pass | pass | warn |

All five perspectives assign `pass` to D1--D3, so the Stage 3 acceptance rule
for mandatory dimensions is satisfied. The Devil's Advocate D5 warning is
nonblocking and reflects remaining submission packaging rather than a
scientific-claim defect.

## Commitment verification

| Commitment | Check | Decision |
|---|---|---|
| P0-1 bundled estimand | Prompt profiles and runtime modules are disclosed; title, RQ2, prose, tables, and figures use package language; regression test excludes the old RQ2 | Pass |
| P0-2 benchmark reversal | AgentDojo and M3-v2 raw pairs, differences, and intervals appear in the Abstract, Results, Discussion, Conclusion, and Table 5 | Pass |
| P0-3 failure-sensitive bound | Observed unsafe effects remain separate from the pessimistic unsafe-or-failure bound; overall and benchmark pairs are reported | Pass |
| P0-4 reproducible regimes | Inputs, transformations, and a sanitized example are stated; deployment prevalence is not inferred | Pass |
| P1-1 completed RQ3 | Same-provider replication and budgets 50/200 define RQ3; Gemini is diagnostic-only | Pass |
| P1-2 inference/precision | Separate Holm families, unadjusted bootstrap intervals, Wilson upper bounds, and no post hoc power are explicit | Pass |
| P1-3 VIGIL fidelity | Source commit, retained upstream path, provider injection, decoding, and fail-closed fallback are stated | Pass |
| P1-4 burden stratification | ASK, DENY, failure, and p95 latency are split by task type and benchmark; ASK is system incidence | Pass |
| P1-5 sample independence | Post-Public chronology, outcome-blind inputs, overlapping cohorts, and 902-case union are disclosed | Pass |

## Adversarial reading

The strongest remaining rejection argument is external validity: authorization
stress operators are implementation-specific, only one provider has complete
evidence, and the lean attack endpoint is floor-limited. The manuscript now
states each limitation directly, reports the failure-sensitive bound, and does
not infer cross-provider or naturally occurring policy prevalence. These facts
limit the contribution but no longer contradict it.

The package contrast remains confounded for component attribution. This is not
“fixed” statistically; instead, the estimand and claims have been changed to a
bundled configuration comparison. The manuscript consistently preserves that
boundary.

## Verification evidence

- English/Chinese manuscript, analysis, table, figure, and DOCX structural
  tests: 35 passed in the combined focused run.
- Analysis code lint and Python syntax checks: passed.
- English and Chinese main tables have identical numeric-token multisets.
- Both DOCX files contain seven tables, five figures, one section, the expected
  citation corpus, and no raw citation placeholders.
- Standard page rendering could not run because LibreOffice/`soffice` is not
  installed; therefore visual pagination is not claimed.
- Provider calls, Full Harness, historical replay, and successful-row reruns:
  zero.

## Decision

**Stage 4 scientific major revision: accepted.** The manuscript can move to
author-side submission preparation. The project feature remains `in_progress`
until author metadata, institutional JCR/SCIE confirmation, author-side
similarity review, visual Word inspection in Word/WPS or LibreOffice, and a
final submission checklist are complete.

