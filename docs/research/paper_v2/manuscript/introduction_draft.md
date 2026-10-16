# Introduction — empirical authorization study draft

Status: `corrected_v2_narrative_updated_tables_layout_pending`

## Motivation

Tool-using language-model agents turn generated text into actions. An indirect
prompt injection in a message, document, webpage, memory item, or tool response
can become a request to send data or modify state. AgentDojo and InjecAgent
place these attacks within tasks where security and useful completion can be
evaluated together [@L09; @L10]. Runtime systems such as VIGIL, DRIFT, the
Task Shield, IPIGuard, and AgentSpec interpose checks before effects are committed
[@L01; @L02; @L03; @L20; @L25].

These approaches establish complementary foundations in verification,
contextual policy generation, least privilege, planned dependencies, and
control/data-flow separation [@L01; @L08; @L24; @L25; @L26]. Recent preprints
extend this foundation through influence auditing, authorization/execution
graphs, controlled source-authority changes, and evidence-backed permission
graphs [@L21; @L22; @L35; @L36]. Building on this work, we examine how
authorization information, enforcement structure, and failure handling change
the security and utility measured for tool-using agents.

## Evaluation gap

Three distinctions motivate the evaluation. First, prompt structuring,
spotlighting, instruction hierarchy, and injection detection measure different
stages from runtime execution [@L07; @L30; @L31; @L32]. Linking proposals to
Guard decisions and effect receipts makes those stages separately observable.

Second, authorization is part of the treatment. Answer-derived scope supplies
information unavailable to a Guard compiling policy from trusted user intent.
Comparing these regimes tests the contribution of authorization information
rather than treating it as fixed infrastructure.

Third, security and utility must be measured jointly. Benign completion,
confirmation requests, blocking, failures, and unknown outcomes reveal costs
that attack-success counts alone can obscure. Defense-aware adaptive testing
adds a further dimension by varying the attacker's search budget [@L27].

## Research questions

The corrected evaluation addresses three questions.

1. **RQ1: Authorization semantics.** How does target-scoped oracle
   authorization (`exact_target_v2`) change completion relative to
   authorization compiled from trusted intent (`auto_compiled`)?
2. **RQ2: Security, utility, and runtime burden.** Under ordinary prompts,
   what security judgments, benign completion, unknown outcomes, and
   confirmation/blocking burden occur with no research Guard, policy modules,
   full modules, and the explicitly configured structural comparator?
3. **RQ3: Component evidence and applicability.** How do policy and full
   modules behave in controlled sensitive-data and missing-classification
   cases, and how do these observations relate to natural-task outcomes?

## Study design

M3 produces three runtime decisions: `ALLOW` permits a proposed action,
`ASK` waits for independent confirmation, and `DENY` blocks it. The automatic
path may restrict, but not expand, privileges. Runtime projections separate
model inputs from raw answers and evaluator labels. The exact-target condition
supplies answer-derived authorization to the Guard as an explicit oracle treatment.

The 900-assignment authorization study uses 180 fixed cases representing 153
tasks, with ordinary prompts in both policy and full conditions. Four primary
conditions cross the module bundle with `auto_compiled` and `exact_target_v2`;
a nested subset adds broad, underspecified, and conflicting policies.

A separately executed 480-assignment contemporaneous calibration uses 120 cases
nested within that cohort. Cases are split evenly between benchmarks and between
attacks and benign tool tasks. It compares no research Guard, policy, full, and
a source-pinned VIGIL adaptation. Sixteen synthetic Pro and V4.1 Flash executions
provide positive and negative flow controls across four component scenarios.
Earlier factorial, source-authority, confirmation, and adaptive experiments
provide historical context under their recorded implementations and endpoints.

## Empirical motivation and study framing

An implementation audit found that the historical oracle monitor compared
complete action arguments with partial security-target annotations. This
mismatch motivated corrected target matching and a separate evaluation of
compiled versus exact-target scope. The current study pairs that comparison
with an unguarded calibration and component controls, linking authorization
decisions to completion, execution, and operational outcomes.

## Contributions

The study contributes:

1. corrected operationalization of target authorization, with an explicit
   separation between raw evaluator information and oracle-derived scope;
2. a paired empirical account of authorization burden, benign completion,
   security events, failures, and unknowns under current runtime configurations;
3. bounded component controls that separate sensitive-data restrictions
   from end-to-end efficacy, complemented by clearly labelled historical
   factorial, provenance, and adaptive diagnostics; and
4. version-aware reporting that preserves proposals, decisions, isolation
   rejection, simulated execution, completion, and failure as different
   observations with version-specific evidence boundaries.
