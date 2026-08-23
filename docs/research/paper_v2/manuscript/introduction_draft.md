# Introduction — empirical authorization study draft

Status: `deepseek_authorization_results_complete_gemini_diagnostic_closed`

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
defense must therefore report executed unsafe effects, benign task completion,
system confirmation-request incidence, operational failures, latency, tokens, and cost under a
common intention-to-treat denominator. Static attacks are also insufficient
for a robustness claim when an attacker can adapt to the public defense
interface [@L27].

## Research questions

The study asks three questions.

1. **RQ1: Authorization regime.** How do `exact_gold`, `auto_compiled`,
   `broad`, `underspecified`, and `conflicting` authorization regimes change
   unsafe effect, benign task completion, and `ASK/DENY` burden?
2. **RQ2: Configuration comparison.** How does the complete M3 configuration
   package compare with the policy package on safety, utility, and operational
   outcomes, without attributing the contrast to an individual component?
3. **RQ3: Replication and adaptive budget.** Are these directions consistent
   across AgentDojo and M3-v2, across completed DeepSeek V4 Pro and V4 Flash
   evidence, and at completed defense-aware budgets 50 and 200?

## Study design

M3 uses a three-state runtime decision (`ALLOW`, `ASK`, `DENY`), a projection
that excludes evaluator-only fields from online state, permission monotonicity
for automatic paths, parameter-source evidence, and independent confirmation
for privilege expansion. The primary paired experiment crosses a policy
package and a full package with non-oracle `auto_compiled` and oracle-sensitivity
`exact_gold`. A nested subset adds three authorization stress regimes. The full
package also changes the prompt profile from `normal` to `safe_prompt`, so the
package contrast is not a component ablation. The planned cross-provider subset
adds a source-pinned peer-reviewed structural condition. Timeouts,
parsing failures, refusals, maximum-step outcomes, and provider failures remain
in the intention-to-treat denominator.

The new primary sample contains 180 paired cases and 900 DeepSeek V4 Pro work
items; a nested 90-case sample contributes 450 planned Gemini 3.6 Flash work
items. The design separately reuses the completed 480-record medium study,
5,082-record Pro Public matrix, 1,791-record Flash Public matrix, and the
40-task adaptive evidence at budgets 50 and 200. Provider tools and real
external effects are prohibited throughout.

## Empirical motivation and study framing

The completed medium falsification study did not support full-package
superiority. The full package reduced unsafe effects from 8/36 under the
structural condition to 0/36, but the policy package also produced 0/36.
Benign tool completion fell from 12/24 under the structural condition to 6/24
under the full package, violating the preregistered
non-inferiority margin. These observations motivate an empirical study of
authorization uncertainty and the security–utility frontier rather than a
claim that the full package is a new or state-of-the-art defense.

The larger Public primary matrix reinforced this
finding. Across 600 attacks, the full package reduced unsafe effects from 133
under the structural condition to 38, but the policy package produced only 13. Across 168
benign tool tasks, both M3 variants completed 49 versus 103 under the
structural condition. The full package therefore shows neither incremental
security nor utility value beyond the policy package in the primary-model evidence.
The 1.4955% retained diagnostic fraction also exceeds the predefined 1%
threshold for a clean configuration-quality claim.

The completed 40-task adaptive panel observed first unsafe effect for 4/40
tasks by budget 50 and 18/40 by budget 200. These points show substantial
budget sensitivity but do not establish saturation. The lean paper therefore
reports a first-success curve only through query 200 and makes no budget-500 or
2,000 claim.

The prospectively frozen authorization-regime experiment is now complete for
DeepSeek. Unsafe effects remained at or near zero across all four main cells,
but exact authorization produced opposite benign-tool directions across the
two benchmarks and increased failure-sensitive attack risk on AgentDojo. It
also replaced ASK with more frequent DENY and increased latency. The full
package showed no stable advantage over the policy package. These unfavorable
results are retained. Gemini free-tier execution closed incomplete at 32/450
terminal work items and therefore supports no cross-provider claim.

## Contributions

The current evidence supports four bounded contributions:

1. an evaluator/online-state contract that makes authorization visibility
   explicit and prevents evaluator-only fields from entering runtime state;
2. a paired security–utility evaluation of policy and full configuration
   packages, with their prompt-profile difference disclosed and no component-
   level causal claim;
3. an intention-to-treat experiment that records official model identity,
   request commitments, isolated effects, and terminal diagnostics while
   retrying only response-less failed rows; and
4. an empirical account of authorization regime, system confirmation incidence,
   benchmark/task heterogeneity, and defense-aware attack budget.

These contributions do not assert first, only, or SOTA status. Preprints are
used to define the contemporary novelty boundary, not as peer-reviewed
evidence.
