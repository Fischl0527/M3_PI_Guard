# Introduction — empirical authorization study draft

Status: `corrected_v2_narrative_updated_tables_layout_pending`

## Motivation

Tool-using language-model agents turn generated text into actions. An indirect
prompt injection embedded in a message, document, webpage, memory item, or tool
response can therefore become a request to send data, modify state, or invoke a
privileged operation. Public environments such as AgentDojo and InjecAgent
show that security must be evaluated together with task utility rather than as
a text-classification problem alone [@L09; @L10]. Runtime systems including
VIGIL, DRIFT, the Task Shield, IPIGuard, and AgentSpec consequently interpose
verification, task alignment, dependency, information-flow, or policy checks
before an effect is committed [@L01; @L02; @L03; @L20; @L25].

This literature also makes a broad novelty claim untenable. Verify-before-
commit, contextual policy generation, least privilege, planned dependency
checks, and control/data-flow separation are already occupied design spaces
[@L01; @L08; @L24; @L25; @L26]. Recent preprints go further by auditing
context influence, comparing an authorization graph with a parameter-source
execution graph, or controlling source authority in next-action decisions
[@L21; @L22; @L35]. Evidence-backed permission graphs with formal runtime
authorization further narrow the mechanism claim boundary [@L36]. The open question for this study is therefore not
whether a provenance-aware guard can be built for the first time. It is
whether authorization information, enforcement structure, and failure
handling materially change the security and utility measured for tool-using
agents.

## Evaluation gap

Three distinctions are easy to blur in an agent-security experiment.

First, a detector score or model refusal is not an executed-effect endpoint.
Prompt-level structuring, spotlighting, instruction hierarchy, and injection
detection can reduce model compliance, but they do not by themselves prove
that an unauthorized action failed to cross an external runtime boundary
[@L07; @L30; @L31; @L32].

Second, the authorization regime is part of the treatment. A guard that sees
per-sample answer keys, evaluator labels, or an exact policy reconstructed from
the expected answer is solving a different problem from a guard that receives
only trusted user intent and a non-oracle policy compiled before execution.
The present source audit does not establish that such leakage is universal, so
we frame this as authorization uncertainty rather than a domain-wide
answer-key defect.

Third, low attack success can be purchased by blocking useful work. A runtime
defense must therefore report benchmark-specific security judgments, observed
simulated effects, benign completion, confirmation requests, failures, and
runtime burden under an explicit intention-to-treat denominator. Unknown
outcomes are not safe zeros, and task completion can precede a subsequent
failure. Static attacks are also insufficient
for a robustness claim when an attacker can adapt to the public defense
interface [@L27].

## Research questions

The corrected evaluation addresses three questions. The earlier six-question
factorial, source-swap, replication, and adaptive program is retained as
historical evidence, not retrospectively relabelled as corrected execution.

1. **RQ1: Authorization semantics.** How does target-scoped oracle
   authorization, rather than complete-argument equality, change completion
   relative to authorization compiled from trusted intent?
2. **RQ2: Security, utility, and runtime burden.** Under ordinary prompts,
   what security judgments, benign completion, unknown outcomes, and
   confirmation/blocking burden occur with no research Guard, policy modules,
   full modules, and the explicitly configured structural comparator?
3. **RQ3: Component evidence and applicability.** What do controlled
   sensitive-data and missing-classification cases establish about component
   behavior, and what remains unsupported on natural tasks, other models,
   dynamic environments, and adaptive attacks?

## Study design

M3 produces three runtime decisions: `ALLOW` permits a proposed action,
`ASK` waits for independent confirmation, and `DENY` blocks it. The automatic
path may restrict, but not expand, privileges. Runtime projections keep raw
answers and evaluator labels outside the model input. An exact-target oracle
nevertheless supplies answer-derived authorization to the Guard; excluding
raw answers does not make that condition non-oracle.

The 900-assignment corrected authorization study uses 180 fixed cases and
ordinary prompts in both policy and full conditions. Four primary conditions
cross the module bundle with `auto_compiled` and `exact_target_v2`; a nested
subset adds broad, underspecified, and conflicting policies. A separate
480-assignment contemporaneous calibration uses 120 fixed cases, split evenly
between benchmarks and between attacks and benign tool tasks. It compares
no research Guard, policy, full, and a source-pinned VIGIL adaptation with
model-based secondary verification disabled. Sixteen synthetic Pro and
V4.1 Flash executions provide bounded positive and negative flow controls.
Case overlap and repeated condition assignments preclude interpreting their
sum as an independent sample count.

Earlier Public, factorial, source-authority, confirmation, and adaptive
experiments retain their original records and endpoint definitions. The
historical factorial crosses prompt profile (`normal`/`safe`) with runtime
modules (`policy`/`full`); its source swap varies provenance authority while
holding the proposition and policy fixed. Those studies contextualize the
current evaluation but do not substitute for corrected execution evidence.
Gemini and optional independent-model or native dynamic-environment studies
do not contribute a qualified effect estimate. Provider-managed tools and
real external effects remain disabled throughout.

## Empirical motivation and study framing

An implementation audit found that the historical oracle monitor compared
complete action arguments with partial security-target annotations. Its
completion collapse is therefore not evidence of an intrinsic cost of
precise authorization or a benchmark-intrinsic reversal. Corrected target
matching changes that interpretation without overwriting old records.

Current results reveal a more defensible problem: restrictive automatic
authorization impedes benign AgentDojo work, while the sparse attack
endpoint cannot establish security improvement. Exact-target assistance
improves some completion but relies on an offline oracle. Full modules show
no identifiable end-to-end advantage over policy modules in the tested
conditions. Sensitive-data controls demonstrate bounded component behavior,
not general natural-task efficacy. These studies do not establish full-module
superiority, and their negative or uncertain outcomes are retained.

Historical adaptive observations still illustrate budget sensitivity, but
their success labels are not retrospectively verified unauthorized effects.
Extending 12 selected budget-200 survivors is not a complete budget-500 panel
or evidence of saturation. Likewise, the historical risk-enriched calibration
is a single execution block rather than temporal-repeatability evidence.

## Contributions

The defensible contributions are:

1. corrected operationalization of target authorization, with an explicit
   separation between raw evaluator information and oracle-derived scope;
2. a paired empirical account of authorization burden, benign completion,
   sparse security events, failures, and unknowns under current runtime
   configurations;
3. bounded component controls that separate sensitive-data restrictions
   from end-to-end efficacy, complemented by clearly labelled historical
   factorial, provenance, and adaptive diagnostics; and
4. version-aware reporting that preserves proposals, decisions, isolation
   rejection, simulated execution, completion, and failure as different
   observations rather than deriving protection from a module-enable flag.

These contributions do not assert first, only, or SOTA status. Preprints are
used to define the contemporary novelty boundary, not as peer-reviewed
evidence.
