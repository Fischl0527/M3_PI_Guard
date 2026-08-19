# Introduction — empirical authorization study draft

Status: `medium_public_primary_and_exploratory_adaptive_evidence_admitted`

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
context influence or comparing an authorization graph with a parameter-source
execution graph [@L21; @L22]. The open question for this study is therefore not
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
confirmation burden, operational failures, latency, tokens, and cost under a
common intention-to-treat denominator. Static attacks are also insufficient
for a robustness claim when an attacker can adapt to the public defense
interface [@L27].

## Research questions

The study asks four questions.

1. **RQ1 — Security and utility.** Under non-oracle `auto_compiled`
   authorization, does M3-full reduce executed unsafe effects relative to the
   strongest admitted structural baseline while preserving benign tool-task
   completion within a −5 percentage-point non-inferiority margin?
2. **RQ2 — Module contribution.** Does provenance, temporal/data-flow
   enforcement, and confirmation add security beyond the same runtime with
   policy-only enforcement?
3. **RQ3 — Authorization and operational uncertainty.** How do authorization
   regime, `ALLOW/ASK/DENY`, parser/provider/maximum-step failures, benchmark,
   and task type change the observed security–utility frontier?
4. **RQ4 — Adaptive robustness.** Does defense-aware search recover unsafe
   effects as the query budget increases, and where does first success occur?

## Study design

M3 uses a three-state runtime decision (`ALLOW`, `ASK`, `DENY`), a projection
that excludes evaluator-only fields from online state, permission monotonicity
for automatic paths, parameter-source evidence, and independent confirmation
for privilege expansion. The evaluation pairs six conditions: no defense,
safe prompt/spotlighting, PromptGuard detector-only, an admitted structural
baseline, M3 policy-only, and M3-full. Every assigned row is bound to an
append-only request/response, budget, safety, and experiment-record chain.
Timeouts, parsing failures, refusals, maximum-step outcomes, and provider
failures remain in the intention-to-treat denominator.

The medium falsification study contains 72 cases and 480 condition records.
The public primary matrix contains 600 attack and 247 benign cases from
AgentDojo and M3-v2, producing 5,082 paired condition records. A separately
gated adaptive protocol mutates only untrusted content, exposes only the public
guard decision and post-enforcement effect, and prohibits provider tools or
real external effects.

## Current evidence and route decision

The admitted medium study rejected the mechanism-paper route. M3-full reduced
unsafe effects from 8/36 under the structural condition to 0/36, but M3
policy-only also produced 0/36. Benign tool completion fell from 12/24 under
the structural condition to 6/24 under M3-full, violating the preregistered
non-inferiority margin. The contribution is therefore an empirical study of
authorization uncertainty and the security–utility frontier, not a claim that
M3-full is a new or state-of-the-art defense.

The independently reproduced Public primary matrix preserves this route at
larger scale. Across 600 attacks, M3-full reduced unsafe effects from 133 under
the structural condition to 38, but policy-only produced only 13. Across 168
benign tool tasks, both M3 variants completed 49 versus 103 under the
structural condition. The full mechanism therefore shows neither incremental
security nor utility value beyond policy-only in the admitted primary-model
evidence. The 1.4955% retained diagnostic fraction also exceeds the frozen 1%
clean-mechanism quality ceiling.

An admitted eight-task adaptive cost canary observed 0/8 unsafe-effect
successes at budget 50, with a Wilson 95% interval of 0–32.44%. This result
validates the evidence and cost path but is too small to establish adaptive
robustness. The formal multi-budget adaptive panel and independent blind
custody remain open validity requirements.

## Contributions

The current evidence supports four bounded contributions:

1. an evaluator/online-state contract that makes authorization visibility
   explicit and prevents evaluator-only fields from entering runtime state;
2. a paired security–utility evaluation that directly compares policy-only and
   full provenance/temporal/confirmation enforcement;
3. an intention-to-treat evidence chain that binds official model identity,
   request payloads, responses, budgets, isolated effects, and terminal
   diagnostics without selective retry; and
4. an empirical account of authorization regime, confirmation burden,
   benchmark/task heterogeneity, and defense-aware attack budget.

These contributions do not assert first, only, or SOTA status. Preprints are
used to define the contemporary novelty boundary, not as peer-reviewed
evidence.
