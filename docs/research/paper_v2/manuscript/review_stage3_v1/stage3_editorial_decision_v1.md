# Stage 3 Editorial Synthesis and Decision

## Review target

- Frozen manuscript baseline:
  `119b1b1c0d158c41de485b969830c370ca951b1a`
- Intended venue: *Journal of Information Security and Applications*
- Panel: Editor-in-Chief, methodology/statistics, LLM-agent security domain,
  usable-security perspective, and Devil's Advocate
- Review mode: internal author-side pre-submission scientific review

## Mechanical score matrix

| Reviewer | D1 methodology | D2 domain | D3 coherence | D4 cross-disciplinary | D5 writing |
|---|---|---|---|---|---|
| Editor-in-Chief | warn | pass | warn | pass | warn |
| Methodology | block | warn | warn | pass | warn |
| Domain | warn | warn | warn | pass | warn |
| Perspective | warn | pass | pass | warn | warn |
| Devil's Advocate | block | warn | warn | warn | warn |

## Failure-condition evaluation

| Rule | Mechanical result | Consequence |
|---|---|---|
| F1: any mandatory-dimension block | Triggered: Methodology and Devil's Advocate assign D1 `block` | Current manuscript cannot be accepted; at least major revision |
| F2: at least 4/5 reviewers see two or more mandatory warn-or-worse dimensions | Triggered: EIC, Methodology, Domain, and Devil's Advocate = 4/5 | Major revision |
| F3: any D4 block | Not triggered | No cross-disciplinary fatal flaw |
| F0: every reviewer passes every mandatory dimension | Not satisfied | Acceptance unavailable |

## Editorial decision

**Major revision; not submission-ready.**

The study remains viable for JISA. The completed evidence supports a bounded
empirical paper about authorization construction, benchmark dependence,
failure-sensitive evaluation, and configuration complexity. It does not
identify the isolated causal contribution of provenance/data-flow/confirmation
because M3-full and policy-only also use different prompt profiles. This
problem can be resolved without new provider calls by changing the estimand and
claim boundary from a component ablation to a configuration-bundle comparison.

No reviewer requires Gemini continuation, a new blind set, a Full Harness run,
or additional adaptive budgets for the narrowed paper.

## Consolidated issue ledger

### P0 — Blocking scientific revisions

#### P0-1: Redefine the full-versus-policy estimand

- Evidence: runtime code assigns `safe_prompt` to M3-full and `normal` to
  policy-only.
- Defect: RQ2 and several conclusions attribute the contrast to the additional
  provenance/temporal/data-flow/confirmation modules.
- Required revision: describe both as configuration bundles; add a components
  table; disclose prompt profile; remove isolated module-causal language from
  title, abstract, RQs, Methods, Results, Discussion, Conclusion, and Figure 3.
- New API required: no.
- Exit test: every statement of incremental provenance/module effect is either
  removed or explicitly labeled unidentifiable under the bundled contrast.

#### P0-2: Report the benchmark direction reversal

- Evidence: exact versus auto benign-tool completion is +4/30 for AgentDojo and
  −17/30 for M3-v2 under policy-only; +3/30 and −12/30 under full.
- Defect: pooled −21.67 and −15.00 percentage-point results hide a qualitative
  interaction and do not fully answer RQ3.
- Required revision: add paired benchmark-stratified estimates, raw counts, and
  intervals; state that the pooled decline is driven by M3-v2 and does not
  generalize across the two benchmarks.
- New API required: no.
- Exit test: Abstract, Results, Discussion, and Conclusion all preserve the
  benchmark-dependent interpretation.

#### P0-3: Add failure-sensitive security bounds

- Evidence: attack operational failure is 8/100 full/auto, 26/100 full/exact,
  6/100 policy/auto, and 25/100 policy/exact while unsafe-effect counts are 0,
  0, 1, and 0.
- Defect: executed unsafe effect is valid but floor-limited and can look stable
  when execution is unavailable.
- Required revision: retain the primary executed-effect estimand and add the
  pessimistic composite `unsafe_effect OR operational_failure`, paired by
  condition and benchmark. Label it as a sensitivity bound, not observed attack
  success.
- New API required: no.
- Exit test: readers can see both executed effects and security-unavailable
  outcomes without treating failures as safe successes.

#### P0-4: Make authorization regimes reproducible constructs

- Evidence: the code-level transformations are more specific than the current
  one-line prose labels.
- Required revision: describe compiler inputs and exact transformations for
  auto, broad, underspecified, conflicting, and exact-gold; include one
  sanitized example and constrain claims to these controlled transformations.
- New API required: no.
- Exit test: a reader can reconstruct the conceptual policy transformation from
  Methods without reading source code.

### P1 — Major presentation and inference revisions

#### P1-1: Rebuild RQ3 around completed evidence

Define RQ3 as cross-benchmark and same-provider-model stability. Move the
32/450 Gemini diagnostic execution out of the main design table and into a
short operational limitation or supplement. State that cross-provider validity
remains unassessed.

#### P1-2: Clarify inference families and precision

State that Holm correction is separate within the two endpoint families and
that bootstrap intervals are unadjusted. Add a design-precision statement for
100 attack and 60 benign-tool pairs; label 900-row security comparisons
floor-limited/descriptive rather than using observed post hoc power.

#### P1-3: Identify VIGIL and document fidelity

Replace generic “strongest peer-reviewed structural baseline” on first use with
the source-pinned VIGIL verify-before-commit adapter. Report the pinned source,
provider-client injection, unchanged upstream components, and environment/tool
adaptation boundary.

#### P1-4: Stratify operational burden

Report ASK incidence, DENY incidence, failure, and latency separately for
benign-tool and attack tasks, preferably also by benchmark. Use “system
confirmation-request incidence” rather than implying measured human approval
burden.

#### P1-5: Document sample selection independence

State that the deterministic selector did not read prior outcome files, list
the stratification inputs, and disclose that the lean study was designed after
the Public results even though the new executions were unobserved.

### P2 — Clarity and visual revisions

1. Retitle around tested factors, for example: *Evaluating Authorization
   Regimes and Runtime Guardrail Configurations for Tool-Using LLM Agents*.
2. Replace Figure 2's 0–100 `1 − unsafe-effect` scale with direct risk plus
   uncertainty or a focused inset.
3. Replace Figure 3 labels such as “policy to full” with bundle-aware labels.
4. Redesign Table 5 so it reports condition-by-benchmark outcomes rather than
   pooled condition/case strata.
5. Distinguish admission-class diagnostics from operational failures.
6. Clarify ASK-pending effect semantics and latency accounting.
7. Add a small, primary-source usable-security literature bridge or recast
   high-consequence confirmation statements as design hypotheses.
8. Compress repeated statements about no SOTA, no saturation, and no
   cross-provider inference after those boundaries are established.

## Stage 4 revision order

1. Extend the existing offline analysis script only for P0-2, P0-3, and P1-4.
2. Add focused unit tests for those derived counts, paired comparisons, and
   failure-composite semantics.
3. Rebuild Tables 2–5 and Figures 2–4 once; do not touch completed API rows.
4. Revise Methods and Results before editing Abstract, Introduction,
   Discussion, and Conclusion.
5. Update the English manuscript, then mirror only accepted scientific changes
   into the Chinese comparison manuscript.
6. Rebuild both Word drafts and run the same narrow manuscript/statistics tests
   used at Stage 2.5; do not run Full Harness or historical evidence replay.
7. Perform a single response-to-review checklist against every P0/P1 item.

## Acceptance conditions for the next checkpoint

Stage 4 may pass only when:

- P0-1 through P0-4 are closed with manuscript locations and evidence;
- no component-causal attribution remains;
- benchmark-specific and failure-sensitive results are internally consistent;
- all existing terminal failures remain in ITT and no successful API row is
  rerun;
- Gemini remains diagnostic-only and no cross-provider claim appears;
- focused analysis/manuscript tests pass; and
- the feature remains `in_progress` until author metadata, institutional JCR/
  SCIE confirmation, author-side similarity check, and final submission review
  are completed.

## Author checkpoint

Recommended author decision: **approve Stage 4 major revision using existing
records only**. The alternative is to run a same-prompt module ablation, which
would reopen API experimentation and is not required for the narrower empirical
paper.

