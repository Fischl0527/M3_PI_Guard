# Stage 3 Review 2 — Methodology and Statistics

## Dimension Scores

| Dimension | Score | Basis |
|---|---|---|
| D1 methodology rigor | `block` | The full/policy estimand is described as a module ablation although prompt profile also changes; uneven failures and a benchmark direction reversal are not included in the primary inferential presentation. |
| D2 domain accuracy | `warn` | Executed unsafe effect is correctly distinguished from runtime decisions, but failure-free apparent safety remains too easy to read as defense safety. |
| D3 argumentative coherence | `warn` | The limitations disclose the floor and failures, yet the abstract and pooled conclusions do not expose the benchmark interaction or bundled-treatment boundary. |
| D4 cross-disciplinary relevance | `pass` | Joint security, utility, burden, latency, and cost outcomes are operationally meaningful. |
| D5 writing and structure | `warn` | Statistical ingredients are reported, but the estimand hierarchy, interval multiplicity status, and diagnostic/failure terminology need consolidation. |

## Failure Condition Checks

- F1: triggered. D1 is `block`; the mechanical outcome is at least
  reject-or-major-revision.
- F2: this reviewer assigns warn-or-worse to D1, D2, and D3; panel-level
  majority is evaluated in the synthesis.
- F3: not triggered; D4 is `pass`.
- F0: not satisfied.

## Review Body

### Strengths

The analysis uses paired case identifiers, raw numerators and denominators,
Wilson intervals, exact McNemar tests, task-cluster bootstrap intervals, and
Holm adjustment. Terminal failures remain in ITT and successful rows are not
rerun. The manuscript also avoids interpreting a nonsignificant test as
equivalence and correctly says that two adaptive budget points do not establish
saturation.

### Blocking issue

#### METH-B1 — The RQ2 treatment is not a module-only ablation

The Methods state that the two M3 conditions share the agent, model, parser,
evaluator, environment, and policy representation and ask whether provenance,
temporal/data-flow, and confirmation add value beyond policy-only. The actual
runtime configuration assigns `safe_prompt` to M3-full and `normal` to
policy-only. Therefore the paired contrast estimates a package effect, not the
incremental effect of the listed modules. Component attribution is not
identified.

Resolution options are mutually exclusive:

1. execute a same-prompt module ablation; or
2. retain the lean route, redefine the estimand as a paired configuration-bundle
   contrast, disclose the prompt-profile difference in Methods and Table 1,
   and remove every component-causal statement from the title, abstract,
   results, discussion, conclusion, and Figure 3.

The second option is sufficient for a coherent empirical paper and requires no
new API calls.

### Major issues

#### METH-M1 — Failure-sensitive security analysis is required

In the 900-row study, attack operational failures are 8/100 for full/auto,
26/100 for full/exact, 6/100 for policy/auto, and 25/100 for policy/exact. The
primary unsafe-effect counts are 0, 0, 1, and 0. Under a pessimistic composite
that treats attack failure as security-unavailable, the exact cells no longer
look nearly identical to the auto cells. Report at least:

- the prespecified executed-effect estimand;
- attack operational failure by paired condition and benchmark; and
- a sensitivity endpoint `unsafe_effect OR operational_failure` with paired
  differences and uncertainty.

This does not assert that every failure is an attack success. It bounds the
conclusion that no unsafe effect was observed when the system did not complete
normally.

#### METH-M2 — The pooled authorization effect has a qualitative benchmark interaction

For benign-tool TCR, exact versus auto improves AgentDojo for both
configurations (+4/30 policy and +3/30 full) but reduces M3-v2 completion to
0/30 (−17/30 policy and −12/30 full). Report the paired benchmark-specific
effects and avoid a single general statement that exact authorization reduces
utility. If an interaction test is not prespecified, present the strata and
their intervals descriptively and describe the reversal without a new
confirmatory p-value.

#### METH-M3 — Clarify the inferential hierarchy and multiplicity

The paper names unsafe effect and benign-tool TCR as joint primary endpoints,
then applies Holm separately within each four-comparison endpoint family.
Explicitly state that family-wise error is controlled within, not across, the
two endpoint families and that bootstrap intervals are unadjusted descriptive
95% intervals. The current combination produces intervals excluding zero while
Holm-adjusted McNemar p-values exceed .05; this is mathematically possible but
must be explained before the Results interpretation.

#### METH-M4 — Add a precision/power rationale

No prospective power or minimum-detectable-effect rationale is given for 100
attacks and 60 benign-tool pairs per main cell. The attack floor makes this
material. Add a retrospective design-precision statement based on interval
width or detectable discordant-pair patterns; do not use observed post hoc
power. Classify safety comparisons in the 900-row study as floor-limited and
descriptive.

#### METH-M5 — Separate selection from earlier observed evidence

The new 180-case sample was selected after Public experiments existed, even if
the new outcomes were unobserved. State whether the selection script read any
prior outcome file, provide the deterministic stratification rule, and explain
which earlier evidence informed the design. “Before the new outcomes were
inspected” is too weak to rule out outcome-informed case selection.

### Minor issues

1. Distinguish “diagnostic admission class” from “operational failure”; 76
   Public diagnostic records and 466 non-completed operational statuses are
   different quantities but are easy to conflate.
2. Report condition-specific failure types for the four main authorization
   cells in the supplement.
3. State whether latency includes bounded response-less recovery time or only
   the terminal attempt's wall time.
4. For adaptive search, name the censoring rule for tasks without success by
   200 and consider describing the curve as an empirical cumulative incidence,
   not a conventional uncensored success distribution.

## Editorial Decision

**Major revision under the no-new-API reframing route.** The current RQ2 causal
interpretation is not identified. Once reframed as a bundled configuration
contrast, benchmark-stratified and failure-sensitive offline analyses can make
the empirical conclusions defensible.

