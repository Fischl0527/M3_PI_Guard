# Stage 4 Response to the Internal Stage 3 Review

This response covers the scientific revisions requested by the Stage 3 panel.
It is an author-side revision record, not a claim of journal acceptance. No
provider call or historical evidence replay was used.

## P0 scientific revisions

### P0-1 — Full versus policy estimand

**Response:** Accepted. The title and RQ2 now refer to runtime guardrail
configurations. Methods names the policy and full packages, discloses the
`normal` versus `safe_prompt` profile difference, lists the enabled modules,
and states that the contrast is not a component ablation. Component-causal
language was removed from the Abstract, Introduction, Results, Discussion, and
Conclusion. Figure 3 and the primary tables use package-aware labels.

**Locations:** `methods_draft.md` (“Runtime conditions”);
`introduction_draft.md` (“Research questions”, “Study design”);
`discussion_draft.md` (“What the package comparison establishes”);
`conclusion_draft.md`; Figures 2--4 and Tables 2--5.

### P0-2 — Benchmark direction reversal

**Response:** Accepted. The paired benign-tool effect is now reported by
benchmark with raw counts and cluster-bootstrap intervals. AgentDojo changes
from 5/30 to 9/30 for the policy package and from 4/30 to 7/30 for the full
package, whereas M3-v2 changes from 17/30 to 0/30 and from 12/30 to 0/30.
The pooled decline is explicitly described as M3-v2-driven and not common to
both benchmarks.

**Locations:** `results_shell.md` (“Benchmark-stratified authorization
effects”); `table_5_benchmark_stratified.csv`; Abstract, Discussion, and
Conclusion.

### P0-3 — Failure-sensitive security bound

**Response:** Accepted. Observed unsafe effect remains the primary executed-
effect endpoint. A pessimistic `unsafe_effect OR operational_failure` bound is
reported separately and is never labeled attack success. Exact increases this
bound from 7% to 25% in the policy package and from 8% to 26% in the full
package. Paired estimates are also reported by benchmark.

**Locations:** `methods_draft.md` (“Outcomes and failure semantics”);
`results_shell.md` (“Failure-sensitive security bound”); Table 2, Table 5,
Figure 2, Abstract, Discussion, and Conclusion.

### P0-4 — Reproducible authorization constructs

**Response:** Accepted. Methods now states compiler inputs and deterministic
transformations for `auto_compiled`, `exact_gold`, `broad`, `underspecified`,
and `conflicting`, provides a sanitized email-tool example, and limits the
interpretation to controlled implementation-specific stress operators.

**Location:** `methods_draft.md` (“Authorization construction and controlled
stress regimes”).

## P1 inference and presentation revisions

### P1-1 — RQ3 and completed evidence

RQ3 now concerns cross-benchmark and same-provider model replication plus the
completed 50/200 adaptive budget points. The incomplete 32/450 Gemini run is
diagnostic-only; no cross-provider conclusion appears.

### P1-2 — Inference families and precision

Methods states that Holm correction is separate within the utility and
security-sensitivity families and that bootstrap intervals are unadjusted.
The design-precision paragraph gives 0/100 and 0/30 Wilson upper bounds and
rejects post hoc achieved-power reasoning.

### P1-3 — VIGIL fidelity

Methods names VIGIL on first use, pins commit
`af8eb9c70d32f8a3cc07b308e823c813b2285772`, documents provider-client
injection, retained upstream generator/runtime behavior, decoding settings,
and the rejected fallback path.

### P1-4 — Operational burden

ASK, DENY, failure, and p95 latency are separated by attack versus benign-tool
task and by benchmark in `supplementary_burden_stratified.csv` and Figure 4.
The prose uses “system confirmation-request incidence”; no human approval or
human burden is inferred.

### P1-5 — Sample independence

Methods discloses that the lean design followed the Public matrices. The
selector reads only frozen execution-plan identifiers and pre-outcome strata
and budgets, not Public results or outcome files. The record cohorts contain
902 distinct cases in union; nested and overlapping cohorts are explicitly
identified so record totals are not presented as independent case counts.

## P2 clarity and visual revisions

| Request | Resolution |
|---|---|
| Retitle around tested factors | Completed. |
| Plot direct risk in Figure 2 | Completed; observed unsafe effect and the open-marker pessimistic bound are distinct. |
| Use bundle-aware Figure 3 labels | Completed. |
| Redesign Table 5 by benchmark | Completed. |
| Separate diagnostic admission from operational failure | Completed in Methods and Results. |
| Clarify pending ASK and latency | Completed; ASK is a system request and no effect occurs while pending; latency covers the terminal attempt path. |
| Avoid unmeasured usable-security claims | Completed by recasting deployment statements as design hypotheses. |
| Compress repeated caveats | Completed while retaining each material claim boundary once in the main argumentative path. |

## Verification

- Offline analysis, tables, and Figures 2--4 regenerated once.
- Focused manuscript/analysis/table/figure tests: 25 passed.
- Ruff: passed.
- Python syntax compilation: passed.
- API calls: 0.
- Full Harness and historical replay: not run by design.

