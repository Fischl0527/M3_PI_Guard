# Stage 3 Review 1 — Editor-in-Chief Perspective

## Dimension Scores

| Dimension | Score | Basis |
|---|---|---|
| D1 methodology rigor | `warn` | The paired design and outcome separation are strong, but the full/policy contrast is not a single-factor ablation and the principal pooled authorization result hides a benchmark interaction. |
| D2 domain accuracy | `pass` | The manuscript accurately avoids first/only/SOTA claims, distinguishes executed effects from detection, and keeps evaluator fields outside ordinary online state. |
| D3 argumentative coherence | `warn` | The paper's empirical-study framing is defensible, but RQ2 currently overattributes a bundled configuration contrast and RQ3 foregrounds a provider comparison that never became inferential evidence. |
| D4 cross-disciplinary relevance | `pass` | Access control, policy construction, operational failure, and usable task completion are clearly relevant to JISA readers. |
| D5 writing and structure | `warn` | The manuscript is readable and unusually candid, but planned Gemini rows and repeated evidence-boundary language dilute the central completed DeepSeek result. |

## Failure Condition Checks

- F1: not triggered by this reviewer; no mandatory dimension receives `block`.
- F2: this reviewer assigns warn-or-worse to D1 and D3; panel-level counting is
  deferred to the editorial synthesis.
- F3: not triggered; D4 is `pass`.
- F0: not satisfied because D1 and D3 are not both `pass`.

## Review Body

### Overall assessment

The article is in JISA's topical scope and has a potentially publishable
negative-result contribution. Its strongest contribution is not that M3-full
is a superior defense. It is that authorization construction and failure
handling can materially change the measured security–utility profile, and that
a complex runtime configuration may not earn its complexity over a simpler
policy-based configuration. The manuscript is commendably explicit about the
attack floor, failed non-inferiority gate, incomplete Gemini execution, absent
blind set, and forbidden SOTA claims.

The present version is not submission-ready because two central comparisons
need re-expression. First, the implementation shows that M3-full uses a
`safe_prompt` profile while policy-only uses `normal`; the manuscript currently
describes the contrast as if provenance, temporal/data-flow, and confirmation
were the only differences. Second, pooled benign-tool effects reverse by
benchmark: under policy-only, exact authorization changes AgentDojo completion
from 5/30 to 9/30 but M3-v2 from 17/30 to 0/30; under full it changes AgentDojo
from 4/30 to 7/30 but M3-v2 from 12/30 to 0/30. A pooled statement that exact
authorization reduced utility is numerically true but scientifically
incomplete.

### Major issues

#### EIC-M1 — Recast RQ2 as a bundled-configuration comparison

Locations: Sections 1.3, 1.4, 3.4, 4.4–4.7, 5.1, 5.3, and 6; Figure 3 labels.

M3-full and policy-only differ in both runtime modules and prompt profile. The
paper may still report the paired result, but it cannot attribute the
difference specifically to provenance/data-flow/confirmation. Either run a
true same-prompt ablation or, within the lean no-new-API route, rename the
estimand to “full M3 configuration bundle versus policy-only configuration,”
disclose `safe_prompt` versus `normal`, and remove component-causal language.

#### EIC-M2 — Make benchmark interaction a headline result

Locations: Sections 4.7, 5.2, 5.7, 6, Table 5, and the Abstract.

The pooled authorization effect masks opposing benchmark directions. Add an
offline paired benchmark-stratified table or forest panel for benign-tool TCR,
report the raw 30-task denominators, and state that the observed decline is
driven by M3-v2 while AgentDojo moves in the opposite direction. This is not a
minor heterogeneity footnote; it changes the interpretation of RQ1 and RQ3.

#### EIC-M3 — Add a failure-sensitive security view

Locations: Sections 3.10–3.12, 4.4, 4.6–4.7, 5.3, and 5.7.

Operational failures are substantially more common under exact authorization
and differ across Public conditions. The executed-effect estimand is valid, but
readers need a pessimistic companion such as attack `unsafe_effect OR
operational_failure`, reported by condition and benchmark, with a clear label
that it is a robustness bound rather than the primary endpoint. This requires
only offline analysis of existing records.

#### EIC-M4 — Remove incomplete Gemini execution from the main design spine

Locations: RQ3, Sections 1.4, 3.4, 3.8–3.9, 4.9, 5.6, Table 1, and Conclusion.

The stopping-rule account is transparent, but a 32/450 diagnostic cohort with
five response-bearing items should not occupy six rows of the principal design
table. Move detailed Gemini execution accounting to a short limitations or
supplementary note. Reword RQ3 around completed cross-benchmark and
same-provider model evidence; state separately that cross-provider validity
was attempted but remains unassessed.

### Minor issues

1. Name the structural comparator as the source-pinned VIGIL adapter where it
   first appears and describe the injected provider-client adaptation.
2. Define the exact code-level transformations behind `broad`,
   `underspecified`, and `conflicting`; current one-line labels are not
   reproducible constructs.
3. Replace the title's broad “Context and Provenance Uncertainty” wording with
   terminology matching the tested factors, such as “Authorization Regimes and
   Runtime Guardrail Configurations.”
4. Replace or redesign Figure 2. A 0–100 safety axis compresses every condition
   into the top one percent and visually overstates what is known at the attack
   floor. Plot unsafe effect directly with intervals or add a focused inset.
5. Compress repeated no-SOTA/no-cross-provider statements after the claim
   boundary has been established once in Methods and once in Limitations.

## Editorial Decision

**Major revision.** The paper has a viable JISA contribution after claim
reframing and two offline sensitivity/heterogeneity analyses. No new provider
experiment is required if the authors abandon component-level attribution.

