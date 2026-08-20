# Discussion — lean empirical study draft

Status: `authorization_regime_results_pending`

## Existing evidence changes the research claim

The completed medium and Public experiments do not support presenting M3-full
as a stronger defense than policy-only. In the 5,082-record DeepSeek V4 Pro
Public matrix, M3-full produced more unsafe effects than policy-only (38/600
versus 13/600), while the two variants completed the same number of benign
tool tasks (49/168). The 1,791-record V4 Flash matrix showed the same security
direction: 24/400 unsafe effects for full versus 12/400 for policy-only. The
Flash utility difference was small (38/145 versus 35/145) and does not rescue a
claim of independent full-module value.

This is scientifically useful negative evidence. The two variants share the
policy representation and runtime enforcement point, so their divergence
focuses attention on the additional provenance, temporal/data-flow, and
confirmation path. A full mechanism can fail to improve security because its
additional state or decision logic introduces ambiguity, because `ASK`
resolution reopens paths that policy-only blocks, because the model adapts to
feedback differently, or because the evaluated provenance representation is
too noisy to supply useful discrimination. The new authorization-regime
experiment is designed to distinguish some of these explanations without
claiming that it identifies a universal causal mechanism.

## Authorization is part of the treatment

Authorization is often treated as fixed infrastructure rather than an
experimental variable. That assumption is risky in tool-agent evaluation. An
exact per-case authorization object reconstructed from the expected answer
can remove uncertainty that a deployed Guard must resolve. A broad policy can
improve apparent utility by authorizing too much. An underspecified policy can
make safe completion impossible, while conflicting constraints may increase
denial, confirmation, or failure even when they prevent unsafe effects.

The paired design makes these trade-offs observable. `auto_compiled` is the
primary deployment-like regime because it is created from trusted user intent
before untrusted context is processed. `exact_gold` is an oracle sensitivity
condition, not a preferred policy source. The `broad`, `underspecified`, and
`conflicting` cells are stress tests on a fixed nested sample. Their value lies
in showing whether a headline security number is stable to plausible policy
construction errors.

`[After terminal analysis, insert the direction and size of the paired
auto-to-exact and auto-to-stress effects for unsafe effect, benign-tool TCR,
ASK/DENY, failure, and latency. Discuss effect sizes and intervals before
p-values.]`

## Executed effects and utility must be reported together

A low prompt-injection success rate is not sufficient evidence of a useful
runtime defense. A detector may flag adversarial text without preventing an
effect; a runtime may prevent effects by denying nearly every useful action;
and a parser/provider failure may look secure if the evaluator counts only
successful executions. We therefore treat isolated executed effect as the
security endpoint and benign tool-task completion as a joint primary endpoint.

The Public evidence already illustrates the problem. Relative to the admitted
structural condition, both M3 variants reduced unsafe effects but also had much
lower benign-tool completion. Policy-only then outperformed full on security
without losing additional utility. The interpretation is not that provenance
is intrinsically harmful. It is that the evaluated full implementation did not
earn its complexity under these tasks and policies.

ASK, DENY, operational failure, latency, tokens, and cost provide the missing
mechanism-facing context. An authorization regime that shifts unsafe effects
downward but greatly increases ASK may be acceptable in high-consequence
workflows and unacceptable in routine automation. A regime that shifts both
ASK and failure upward may simply externalize uncertainty rather than resolve
it. The paper reports these burdens directly rather than collapsing them into
a composite score.

## Adaptive evidence is budget-sensitive, not saturated

The 40-task defense-aware panel found first unsafe effect for 4/40 tasks by 50
queries and 18/40 by 200 queries. Thus a budget-50 evaluation would have missed
most successes later observed by budget 200. This supports the general warning
that a static or weak attacker can overstate robustness [@L27].

The evidence stops at 200. It cannot establish that attack success has
saturated, estimate an asymptotic attack rate, or compare hardest-task behavior
at 2,000 queries. The correct presentation is a cumulative first-success curve
through 200 with an explicit no-saturation boundary. This narrower result is
more defensible than extending a long and costly panel whose additional
validity for the paper's authorization question is uncertain.

## Relation to recent provenance and authorization work

VIGIL, DRIFT, the Task Shield, IPIGuard, Progent, CaMeL, ARGUS, AuthGraph, FAVA,
and provenance-sensitivity auditing occupy overlapping parts of the design
space [@L01; @L02; @L03; @L21; @L22; @L24; @L25; @L26; @L35; @L36]. These
works rule out claims that M3 is the first verify-before-commit system, the
first parameter-source defense, or the first structured runtime authorizer.

The remaining contribution is methodological and empirical. The study holds
task content fixed while changing authorization regimes and Guard modules,
keeps evaluator fields offline, measures post-enforcement effects, retains
failure in ITT, and reports operational burden. In particular, the recent
provenance-sensitivity study changes source authority in controlled next-action
tasks [@L35]. The present design extends that measurement question to complete
tool trajectories and executed effects, albeit with the additional
implementation complexity and failure modes that such trajectories introduce.

## Cross-provider interpretation

The Gemini sample is deliberately smaller and nested inside the DeepSeek
sample. It can show whether the main paired direction appears under another
provider; it cannot establish broad model-family generality. The official free
tier also introduces an availability constraint. The protocol stops at the
first 429, resumes only response-less or untouched work on a later quota day,
and downgrades transparently after three quota-day attempts.

`[If all 450 work items are terminal, compare the prespecified Gemini paired
directions with DeepSeek and discuss discrepancies. If not, state the observed
terminal fraction and treat all Gemini estimates as diagnostic; do not use
them as a cross-provider conclusion.]`

## Limitations

First, the new primary experiment uses one proprietary model and two benchmark
families. Model updates, tool schemas, system prompts, and application context
may change the effects. The smaller Gemini subset partially probes but does not
eliminate this dependence.

Second, `auto_compiled` is one policy compiler, not a complete model of human
authorization. The stress regimes approximate common policy errors but do not
measure their prevalence in deployed systems. `exact_gold` is intentionally
artificial and should not be read as a recommended configuration.

Third, the effect environment is isolated. This is necessary to prevent real
email, payment, browser, code, or production actions, but it may omit latency,
state, and recovery behavior found in live applications.

Fourth, the adaptive panel reports budgets only through 200 and does not prove
saturation. Attack search is still one family of defense-aware optimization;
another optimizer may find different failures.

Fifth, failure handling is conservative but not interpretation-free. All
response-bearing failures are terminal in ITT, whereas response-less transport
failures can receive bounded explicit recovery. We report raw failures and
superseded attempts so readers can assess that choice.

Finally, this paper does not include an independent blind set. It also does not
claim first, only, or SOTA status. Its external-validity claims are limited to
the models, benchmarks, policy compiler, stress regimes, and attack budgets
actually evaluated.

## Practical implications

Three practical recommendations follow even before the new paired estimates
are filled. First, agent-security benchmarks should publish the fields visible
to the online Guard and keep evaluator-only answers outside that projection.
Second, runtime defenses should be compared against a policy-only variant on
the same tasks; otherwise a complex module may receive credit for behavior
already supplied by the base policy. Third, security reports should include
benign completion, confirmation/blocking burden, failures, latency, and attack
budget alongside unsafe-effect rate.

The terminal authorization-regime results will determine how strongly these
recommendations can be tied to M3's observed effects. They will not change the
bounded contribution or remove unfavorable findings.
