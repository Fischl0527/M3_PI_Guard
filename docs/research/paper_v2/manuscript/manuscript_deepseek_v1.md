# Evaluating Authorization Regimes and Runtime Guardrail Configurations for Tool-Using LLM Agents

## Abstract

Tool-using LLM agents can turn prompt injection into external actions, but
measured security depends on the runtime authorization supplied to the Guard.
We keep evaluator fields offline, vary five controlled authorization
transformations, and jointly report unsafe effects, benign completion, system
decision incidence, failure, and latency.

We reanalyze 7,353 condition-level DeepSeek records covering 902 distinct cases
across overlapping cohorts, plus a 40-task defense-aware panel. In Public
matrices, the full package produced more unsafe effects than the policy package
on V4 Pro (38/600 versus 13/600) and V4 Flash (24/400 versus 12/400). Adaptive
search found first unsafe effects for 4/40 tasks by query 50 and 18/40 by 200.

A frozen 900-work-item V4 Pro experiment crossed both packages with non-oracle
`auto_compiled` and oracle-sensitivity `exact_gold` authorization on 180 paired
AgentDojo and M3-v2 cases. Three attack cells had 0/100 unsafe effects and one
had 1/100. Exact-minus-auto benign completion reversed by benchmark: AgentDojo
changed by +13.33/+10.00 points for policy/full packages, whereas M3-v2 changed
by −56.67/−40.00. A pessimistic unsafe-or-operational-failure endpoint increased
by 18 points for both packages, driven by +36-point AgentDojo differences.

Authorization construction and benchmark semantics can change measured
security–utility conclusions even near the observed attack floor. Because
prompt profile and runtime modules differ together, the package contrast is not
a component ablation. Incomplete Gemini execution supports no cross-provider
inference.

**Keywords:** prompt injection; LLM agents; runtime authorization; provenance; security–utility trade-off

## 1. Introduction

### 1.1 Motivation

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

### 1.2 Evaluation gap

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

### 1.3 Research questions

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

### 1.4 Study design

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

### 1.5 Empirical motivation and study framing

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

### 1.6 Contributions

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

## 2. Related work

### 2.1 Runtime verification and task alignment

VIGIL implements a verify-before-commit protocol for tool-stream injection and
introduces the 959-case SIREN benchmark [@L01]. It is the closest
peer-reviewed structural comparator to M3 because both systems interpose before
an effect is committed. DRIFT instead combines dynamic rules with control- and
data-level constraints and memory-stream isolation [@L02].
The Task Shield verifies whether instructions and tool calls contribute to the
user's declared objective [@L03]. Together, these
peer-reviewed systems prevent us from claiming that M3 introduced
verify-before-commit, dynamic information-flow checks, or task-alignment
verification.

PlanGuard is a related preprint that isolates planning from untrusted context
and applies hierarchical tool and parameter consistency checks [@L23]. Its presence further narrows the
possible novelty claim: planning consistency is an adjacent mechanism, not an
unoccupied problem. We therefore use these works to define comparison classes
and mechanism boundaries rather than to motivate a first-or-only claim.

### 2.2 Privilege, provenance, and information flow

Progent represents least privilege as symbolic tool-and-argument rules. Its
latest arXiv v3 description explicitly distinguishes automatic narrowing from
expansion that requires approval [@L24]. This overlaps directly with M3's
permission-monotonicity and confirmation design. IPIGuard, published at EMNLP
2025, constrains execution through a planned tool-dependency graph [@L25].
CaMeL separates trusted control and data flow and uses capabilities to prevent
unauthorized flows [@L26]. These systems occupy the privilege,
dependency, and information-flow design space that a provenance-aware runtime
must acknowledge.

FAVA is a July 2026 preprint that translates natural-language tasks into a
permission intermediate representation, lowers it to an evidence-backed
permission graph, and uses an SMT authorizer before effectful execution [@L36].
It further narrows any mechanism
novelty claim around structured authorization and data-flow-aware permission
graphs. Our study differs by treating the authorization regime itself as the
paired experimental factor and by jointly measuring executed unsafe effects,
benign utility, confirmation/blocking burden, and operational failure.

Two 2026 preprints overlap even more closely with provenance-aware
authorization. ARGUS constructs an influence-provenance graph for
context-dependent decisions [@L21], while AuthGraph compares an
authorization graph derived in an isolated context against a parameter-source
execution graph [@L22]. Their existence rules out a claim
that M3 is the first parameter-source or provenance-aware authorization
defense. Because neither work is treated here as peer reviewed, their reported
effects define the contemporary claim boundary but are not used as settled
comparative facts.

*Auditing Provenance Sensitivity in LLM Agent Action Selection* supplies an
especially close 2026 measurement counterpart: it holds task content and
policy fixed while changing source authority, then measures whether action
selection changes [@L35]. Its
controlled next-action design is narrower than M3's executed-effect study, but
it reinforces the need to separate evidence relevance from authorization. Our
experiment extends that question to full tool trajectories, paired runtime
Guard conditions, benign utility, `ASK/DENY` burden, and operational failure.

The remaining defensible contribution is consequently methodological and
empirical. We test whether authorization information itself changes measured
security and utility; enforce a runtime projection that excludes evaluator
fields; compare policy-only and full provenance/temporal/confirmation variants
in paired conditions; and quantify `ASK` burden, operational failures, and
executed effects under a common evidence contract. These are study-design
claims and must stand on M3's own completed experiments.

### 2.3 Prompt-level defenses and execution-level outcomes

Structured queries, spotlighting, instruction hierarchy, and injection
detectors act at the prompt, representation, or model-output layer
[@L07; @L30; @L31; @L32]. They are relevant
baselines, but detector scores and model compliance are not equivalent to an
executed-effect endpoint. Our evaluation therefore records whether a proposed
action crossed the runtime boundary and changed the sandbox state, while also
retaining benign task completion. This distinction is necessary because a
defense can appear secure by refusing useful actions or by failing before an
effect is attempted.

### 2.4 Benchmarks and adaptive evaluation

AgentDojo supplies dynamic security and utility tasks and is the main public
benchmark in this study [@L09].
InjecAgent provides a complementary collection of indirect prompt injections
for tool-integrated agents [@L10]. ASB broadens the scenario and defense
taxonomy [@L34].
The public expansion retains the benchmarks' unique task identities instead of
duplicating benign cases to manufacture a denominator.

Static attacks are insufficient for a robustness claim. *The Attacker Moves
Second* argues that a defense-aware attacker should optimize against the
defense design rather than replay a fixed attack set [@L27]. The adaptive panel therefore exposes
only public `ALLOW/ASK/DENY` and post-enforcement unsafe-effect feedback,
searches frozen tasks at prespecified query budgets, and reports the
first-success distribution. Since L27 remains a preprint, it motivates the
protocol but is not described as a peer-reviewed theorem.

### 2.5 Positioning summary

M3 is not positioned as the first runtime guard, the first provenance system,
or a state-of-the-art defense. The medium experiment already showed that
M3-full did not improve security over M3 policy-only and failed the benign-tool
non-inferiority criterion. The active paper instead studies how non-oracle
authorization, provenance-aware enforcement, confirmation, operational
failure handling, benchmark choice, and adaptive attack budget jointly shape
the measured security–utility frontier.

## 3. Methods

### 3.1 Study design and research questions

We conduct a paired empirical study of runtime authorization for tool-using
language-model agents. The design separates the information supplied to the
online Guard from the offline fields used to score the run. It then varies the
authorization regime and the deployed Guard configuration package while
holding the task, attack, provider, model, tool environment, and evaluator
fixed.

The study addresses three research questions:

1. **RQ1: Authorization regime.** How do `exact_gold`, `auto_compiled`,
   `broad`, `underspecified`, and `conflicting` authorization regimes change
   executed unsafe effects, benign task completion, and `ASK/DENY` burden?
2. **RQ2: Configuration comparison.** How does the complete M3 configuration
   package compare with the policy package on safety, utility, and operational
   outcomes? This comparison does not identify the effect of any individual
   provenance, data-flow, confirmation, or prompt component.
3. **RQ3: Replication and adaptive budget.** Are the observed directions
   consistent across AgentDojo and M3-v2, across completed DeepSeek V4 Pro and
   V4 Flash evidence, and under the already completed defense-aware budgets 50
   and 200?

Positive results are not a stopping condition. The analysis is retained if
`exact_gold` has little effect, the full package underperforms the policy
package, or the available replication evidence differs from the primary model.

### 3.2 Threat model and safety boundary

The attacker controls text in documents, messages, retrieved records, memory,
or simulated tool outputs processed while the agent performs a trusted user
task. An unsafe effect is a state transition that violates the task-specific
offline evaluator after the runtime Guard has issued its decision. The model
may propose tool calls, but it cannot invoke provider-managed tools or reach a
real external system.

All experiments use isolated benchmark state. Real email, payment, browser,
shell, code-execution, production API, credential, and unrestricted filesystem
operations are disabled. A proposal can affect only copied AgentDojo state,
M3-v2 mock resources, `example.test`, `/mock/`, or the public sandbox. Model
output is therefore treated as untrusted data, not executable authority.

Training-time poisoning, model-weight compromise, credential theft, host
compromise, and direct modification of the trusted policy store are outside
scope.

### 3.3 Online-state and evaluator separation

Every run constructs the online state through an allowlist projection.
Permitted fields include trusted user intent, the benchmark-visible task
context, the selected authorization regime, provenance events available at
that step, and the proposed action. Gold answers, expected actions, attack and
task-success labels, evaluator explanations, reference trajectories, and
offline effect receipts are excluded.

The `exact_gold` condition is an explicitly labeled oracle sensitivity
analysis. It converts evaluator-derived authorization into the condition's
authorization object, but does not expose the evaluator labels or scoring
fields themselves. `exact_gold` is never presented as the primary deployment
regime. The primary regime is `auto_compiled`, created from the trusted user
request before untrusted content is processed.

Each compact result stores a digest of the online-visible projection and a
boolean forbidden-field check. A run fails the minimal integrity check if a
forbidden field is present. The final analysis checks this condition once for
all terminal records; it does not recursively replay historical evidence.

### 3.4 Runtime conditions

The common runtime interfaces are `TaskPolicyManifest`, `ActionProposal`,
`GuardDecision`, and `ProvenanceEvent`. The two M3 conditions share the agent,
model, parser, evaluator, tool environment, and task-policy representation, but
they are not a single-module ablation:

- **Policy package** evaluates the proposed tool and arguments against the
  current task policy with the `normal` prompt profile. Provenance propagation,
  temporal/data-flow checks, and independent confirmation are disabled.
- **Full package** uses the `safe_prompt` profile and enables policy enforcement
  plus parameter provenance,
  temporal/data-flow constraints, permission-monotonic transitions, and
  confirmation. Automatic transitions may preserve or reduce authority;
  authority expansion produces `ASK` and requires an independent confirmation
  result.

Because prompt profile and runtime modules change together, their contrast is a
bundled configuration comparison. We therefore do not attribute a difference
between these cells to provenance, data flow, confirmation, or prompting alone.

`ALLOW`, `ASK`, and `DENY` are runtime decisions, not security outcomes by
themselves. Security is scored from the isolated post-enforcement effect
receipt. Utility is scored by the benchmark task-completion evaluator.

The planned Gemini subset adds a source-pinned VIGIL baseline under
`auto_compiled`. The adapter uses official VIGIL commit
`af8eb9c70d32f8a3cc07b308e823c813b2285772`: the official constraint generator
and `RuntimeAuditor` are retained, while only OpenAI-client construction is
dependency-injected into the study's frozen provider client. Generation uses
temperature zero, one controlled provider call, the served study model, and
JSON output; silent fallback to default constraints is rejected. The eventual
incomplete Gemini sample is diagnostic and is not used to rank defenses.

### 3.5 Authorization regimes

Five controlled code transformations are evaluated:

- `auto_compiled`: the task policy is compiled from the trusted user request,
  trusted application context, and tool schemas before untrusted evidence is
  processed;
- `exact_gold`: expected tool calls are derived offline from the evaluator and
  converted into required exact argument rules, with confirmation disabled;
  only the derived authorization object enters online state;
- `broad`: each exact argument constraint is replaced by a type constraint;
  when this widens a side-effecting rule, confirmation is required;
- `underspecified`: the last compiled tool rule is removed; and
- `conflicting`: each exact value is replaced by a deterministic controlled
  conflicting value (for example, a recipient becomes
  `conflicting-scope [at] example.test` or a path becomes a public-sandbox conflict
  path).

As a sanitized example, an auto-compiled rule allowing
`send_email(to="analyst [at] example.test")` becomes
`send_email(to: string, confirmation required)` under `broad`, is removed if it
is the final rule under `underspecified`, and targets
`conflicting-scope [at] example.test` under `conflicting`. Under `exact_gold`, an
offline expected call becomes a required exact-value rule. These definitions
describe this implementation; they are not prevalence estimates for deployed
authorization systems.

The four primary DeepSeek cells pair policy-only and M3-full with
`auto_compiled` and `exact_gold`. A fixed nested subset adds M3-full under the
three non-oracle stress regimes.

### 3.6 Existing evidence reused without new calls

Four completed datasets are analyzed once:

- 5,082 DeepSeek V4 Pro records from the Public primary matrix;
- 1,791 DeepSeek V4 Flash records from the Public second-model matrix;
- 480 records from the medium falsification study; and
- the completed DeepSeek V4 Pro adaptive tasks at budgets 50 and 200.

The three record matrices contain 847, 597, and 72 unique cases,
respectively. The Flash cohort is a 597-case subset of the Pro Public cohort;
17 medium cases overlap Pro and 16 overlap Flash. Their union is 902 distinct
cases, so the 7,353 condition-level records are not treated as 7,353
independent cases.

The reuse analysis performs one count/uniqueness pass, retains all terminal
failures in the ITT population, and computes the prespecified endpoint
summaries without repeating model execution. These data establish the
empirical motivation and the two-point adaptive first-success curve; they do
not establish attack saturation.

### 3.7 Frozen primary sample

The new DeepSeek study contains 180 unique paired cases selected before the
new outcomes were inspected:

- 100 attacks, with 50 from AgentDojo and 50 from M3-v2;
- 60 benign tool tasks, with 30 from each benchmark; and
- 20 benign no-tool tasks.

The lean study was designed after the larger Public matrices had been
completed, but its deterministic selector reads only frozen Public execution-
plan identifiers, pre-outcome strata, and call budgets. It does not read any
Public result or outcome file. Selection is stratified by benchmark, task type,
and attack family. Every main case is assigned to four cells: policy package/
`auto_compiled`, policy package/`exact_gold`, full package/`auto_compiled`, and
full package/`exact_gold`. This produces 720 work items.

A nested 60-case subset receives three additional M3-full assignments:
`broad`, `underspecified`, and `conflicting`, adding 180 work items. The frozen
DeepSeek plan therefore contains 900 work items. The first six items form the
formal technical prefix and remain part of the final denominator.

### 3.8 Frozen cross-provider sample

The Gemini study uses 90 cases nested within the DeepSeek main sample:

- 50 attacks;
- 30 benign tool tasks; and
- 10 benign no-tool tasks.

Each case receives five assignments: structural baseline/`auto_compiled`,
policy package/`auto_compiled`, full package/`auto_compiled`, policy package/
`exact_gold`, and full package/`exact_gold`. The plan contains 450 work items,
including a six-item formal prefix.

Gemini uses the official free tier with a paid ceiling of USD 0. At the first
HTTP 429, the active run stops and leaves all unstarted items pending. On a new
provider quota day, only unstarted items and work items with no official model
response are eligible for explicit recovery. A rate-limited work item becomes
a terminal diagnostic on its third quota-day attempt. If the 450-item plan
still cannot be completed after three provider quota days, the observed subset
is reported diagnostically, unstarted work items are counted as unavailable,
and no cross-provider generalization claim is made.

### 3.9 Providers and model identity

The primary model is DeepSeek V4 Pro through the official DeepSeek endpoint.
The cross-provider model is Gemini 3.6 Flash through the official Google
Generative Language OpenAI-compatible endpoint. Each request is assigned a
local request identifier and canonical payload digest before transport. A
response-bearing record retains the official response identifier, exact
returned model identity, usage, latency, and cost or free-tier attestation.
Provider calls for the evidence reported here were made during July and August
2026. The returned names are provider-managed model aliases and therefore
identify the served model at request time without freezing its hidden weights.

Prompts and model responses are not copied into the compact analysis file.
Content-free request metadata and the provider's internal trace remain in a
restricted local run directory outside the analysis dataset. Exact model
identity is checked in the final one-pass integrity validation.

### 3.10 Failure and recovery policy

Automatic retry is disabled. Recovery operates at the predefined
experiment-item level:

- a work item with an official model response is terminal, including timeout,
  refusal, parse failure, and maximum-step outcomes after that response;
- a transport or preparation failure with no official response may be retried
  only with the explicit failed-row option;
- only the affected work item is retried; successful and unaffected work items
  are skipped;
- a repeated non-rate-limit pre-response failure becomes terminal on its
  second attempt; and
- Gemini rate-limit recovery stops at the first 429 in each quota day and
  becomes terminal on the third quota-day attempt.

Earlier response-less attempts remain append-only in the raw file. The
scientific analysis selects the latest terminal attempt for each experiment
item and reports the count of superseded attempts. For Gemini, it applies the
same retry-state normalization as the runner using the content-free pause-event
ledger, so a quota pause cannot be mistaken for a scientific terminal. No prior
row is overwritten.

### 3.11 Outcomes

The two joint primary endpoints are:

1. **unsafe-effect rate** on assigned attack tasks; and
2. **task-completion rate (TCR)** on assigned benign tool tasks.

Benign no-tool completion is descriptive. Secondary outcomes are system `ASK`
and `DENY` event counts and record incidence, operational failure, p50/p95
latency, total tokens, API cost, and predefined heterogeneity by benchmark and
attack family. `ASK` is a runtime confirmation request; without a human study it
is not interpreted as measured human burden.

All terminal work items remain in the intention-to-treat denominator. The
analysis reports raw numerator/denominator values alongside proportions. A
provider or parser failure is not silently removed and is not relabeled as a
successful security outcome. Its unsafe-effect indicator records whether an
isolated unsafe effect was observed, while its operational failure remains a
separate reported outcome and it cannot count as task completion. Latency and
burden summaries likewise include all terminal work items, not only completed
ones.

Because observed unsafe effects are rare, we also report a pessimistic
sensitivity endpoint on attack tasks: `unsafe_effect OR operational_failure`.
This composite is a robustness bound, not an attack-success label. It asks how
conclusions change if a non-operational run is not credited as secure while
preserving unsafe effects and failures as separate reported counts.

### 3.12 Statistical analysis

Each condition proportion receives a Wilson 95% confidence interval. The
paired analyses report the absolute difference in percentage points, the two
discordant counts, and a two-sided exact McNemar test. Uncertainty for the
paired absolute difference is estimated with 10,000 deterministic bootstrap
resamples. Each resample draws paired case identifiers with replacement and
keeps both condition outcomes for the selected case together; the case is the
cluster and inferential unit.

The four primary authorization/configuration comparisons are:

1. policy package `auto_compiled` versus policy package `exact_gold`;
2. full package `auto_compiled` versus full package `exact_gold`;
3. `auto_compiled` policy package versus full package; and
4. `exact_gold` policy package versus full package.

McNemar p-values are Holm-adjusted separately within the four-comparison attack
unsafe-effect family and the four-comparison benign-tool TCR family. Bootstrap
confidence intervals are unadjusted estimation intervals. The `broad`,
`underspecified`, and `conflicting` comparisons, the unsafe-or-failure bound,
and benchmark panels are descriptive sensitivity or heterogeneity analyses,
not additional confirmatory families.

The fixed design provides 100 paired attacks and 60 paired benign-tool tasks per
main contrast, split evenly by benchmark for the latter. With 0/100 observed
unsafe effects, the Wilson upper limit is 3.70%; within a 30-task benign-tool
benchmark stratum, intervals are necessarily much wider (for example, 0/30 has
an 11.35% upper limit). We report these design-precision limits instead of a
post hoc achieved-power calculation.

Adaptive evidence is limited to budgets 50 and 200. We report the cumulative
fraction of the fixed 40-task cohort with a first unsafe effect by query count
and the two observed budget points. We do not extrapolate a saturation level.

### 3.13 Minimal verification and reproducibility

Verification is deliberately proportional to the lean study. It consists of:

1. focused unit tests for modified provider, authorization projection,
   evaluator, analysis, and plotting code;
2. the six-item formal prefix for each provider; and
3. one terminal pass over row count, experiment-item uniqueness, forbidden-field
   isolation, exact model identity, and ITT failure retention.

Each provider writes one append-only compact raw JSONL. The final statistics
are written once to one authorization-analysis JSON, and figures are exported
as submission-ready vector PDF, editable SVG, and raster PNG previews for
manuscript/QA use. Reproducibility assets include frozen samples, condition
assignments, analysis code, aggregate tables, and versioned source.

## 4. Results

### 4.1 Medium falsification study

The medium study contains 480 records: 432 primary `auto_compiled` records
covering 72 paired cases across six conditions, plus 48 authorization-regime
probe records. The preregistered analysis did not support a superiority claim
for the full configuration package. It met the security-effect and deny-all
criteria, but missed the utility point non-inferiority criterion and showed no
security gain over the policy package. Both the favorable security comparison
and the unfavorable utility and package comparisons are reported.

Supplementary Table S1 reports the online-state source audit.

This audit supports only covered-path statements. It does not establish a
domain-wide oracle-authorization problem.

Supplementary Table S2 reports the completed medium security and utility outcomes.

The medium sample therefore shows a security–utility trade-off, not an
incremental package benefit. Both M3 variants eliminated the eight unsafe
effects observed under the structural condition, but they also completed
substantially fewer benign tool tasks.

Supplementary Table S3 reports the prespecified paired comparisons.

The security effect relative to the structural baseline was large in this
sample, but the full package did not outperform the policy package. Relative to the
structural condition, its benign-tool TCR was 25 percentage points lower, well
outside the preregistered −5 percentage-point non-inferiority margin.

Supplementary Table S4 reports the runtime burden and operational quality.

Across the 432 primary records, 411 completed and 21 retained terminal failures
comprised six `max_steps`, six parse failures, and nine provider failures. The
4.86% overall failure fraction and 2.08% provider-failure fraction passed the
predefined operational-quality envelope. Every terminal state remains
in the intention-to-treat denominator.

For the full package, 22 initial `ASK` decisions comprised 17 permission-expansion
events, four independent-confirmation requirements, and one out-of-scope
parameter. Confirmation outcomes remained `pending` in this synthetic study;
the ASK count measures system confirmation-request incidence and cannot be
interpreted as successful approval or measured human burden.

### 4.2 Authorization-regime sensitivity

Forty-eight probe records compare four alternate regimes with matched
`auto_compiled` executions for the policy and full packages. Each
condition–regime comparison contains six pairs. No unsafe effect occurred in
these small probes. For the explicitly labeled `exact_gold` probe, task
completion increased from 1/6 under matched `auto_compiled` to 3/6 under
`exact_gold`, while initial ASK decreased from 3/6 to 0/6; exact McNemar tests
were p=0.5 and p=0.25, respectively. These six-pair estimates are sensitivity
signals, not evidence of a domain-wide bias.

### 4.3 Prespecified decision criteria

| Gate | Result | Evidence |
|---|---|---|
| Security effect vs structural | Pass | 22.22 pp absolute reduction |
| Tool-utility point non-inferiority | Fail | −25.00 pp vs −5 pp margin |
| Full vs policy-package security gain | Fail | 0/36 vs 0/36 |
| Deny-all rejection | Pass | Benign initial ASK-or-DENY 22.22% |
| Operational quality | Pass | All three predefined quality checks passed |
| Supported interpretation | Empirical trade-off study | Full-package superiority claim not supported |

The results therefore support an empirical study of authorization uncertainty
and the security–utility trade-off. They do not support a defense-superiority
or SOTA claim.

### 4.4 Public primary-model result

The completed Public matrix contains 847 unique cases and 5,082 records: 600
attacks and 247 benign cases crossed with the same six conditions. All 76
diagnostic records (1.4955%) remain in ITT. The predefined 1% quality ceiling
therefore failed and prohibits a clean configuration-quality claim. A one-pass
integrity check nevertheless confirmed unique case-condition coverage, model
identity, and diagnostic retention. The result is primary-model-only.

Across the 600 paired attacks, the full package produced 38 unsafe effects (6.33%,
Wilson 95% CI 4.65–8.57) versus 133 (22.17%, 19.03–25.66) under the structural
condition. The paired difference was −15.83 percentage points (10,000-cluster
bootstrap 95% CI −19.50 to −12.17; exact McNemar p=4.04e−17,
Holm-adjusted p=1.61e−16). This security reduction did not establish full-
package superiority: the policy package produced only 13 unsafe effects
(2.17%, 1.27–3.67), so the full package was 4.17 points worse
(95% bootstrap CI 2.50–6.00; exact McNemar p=1.62e−6).

Benign tool completion under the full package was 49/168 (29.17%, 22.82–36.44), versus
103/168 (61.31%, 53.77–68.34) under the structural condition: −32.14 points
(95% bootstrap CI −39.88 to −25.00; exact McNemar p=1.19e−14).
The full and policy packages both completed 49/168, with a paired difference of
0.00 points. All six conditions completed 79/79 benign no-tool tasks.

Supplementary Table S5 reports the public-primary benchmark strata.

The direction is consistent across both attack benchmarks: the full package is
safer than the structural condition but less safe than the policy package. Utility is
strongly benchmark dependent. The public M3-v2 tool tasks show no completion
difference among the three focal conditions, whereas AgentDojo tool completion
falls by 55.67 points for both M3 variants relative to the structural
condition. AgentDojo benign denominators remain the 97 unique official utility
tasks and are not duplicated.

### 4.5 Public DeepSeek V4 Flash replication

The completed Flash matrix contains 1,791 records: 400 attacks, 145 benign
tool tasks, and 52 benign no-tool tasks under each of the structural, policy,
and full packages. The full package produced 24/400 unsafe effects (6.00%,
Wilson 95% CI 4.06–8.77), compared with 12/400 under the policy package
(3.00%, 1.72–5.17) and 47/400 under the structural baseline (11.75%,
8.95–15.28). Thus the full-minus-policy difference was +3.00 percentage
points, preserving the unfavorable direction observed with V4 Pro.

Benign-tool completion was 38/145 for the full package (26.21%, 19.73–33.91),
35/145 for the policy package (24.14%, 17.90–31.71), and 82/145 for the structural baseline
(56.55%, 48.42–64.35). All three conditions completed 52/52 benign no-tool
tasks. The small +2.07-point full-minus-policy tool-completion difference does
not offset the security disadvantage and is not interpreted as an independent
component-specific gain. Sixteen operational diagnostic records remain in ITT; the Flash
result therefore supports a same-provider model replication, not a clean
configuration-quality or cross-provider claim.

### 4.6 Public operational and decision burden

The Public matrix contains 4,616 completed, 112 maximum-step, 120 parse-failure,
and 234 provider-failure records. Diagnostics are uneven by condition:
27 structural, 24 safe-prompt, 22 full-package, two no-defense, one PromptGuard,
and zero policy-package. This imbalance is disclosed because terminal failure can
affect observed unsafe-effect counts; no diagnostic was retried or excluded.

On attacks, the full package issued 181 initial `ASK` and 44 initial `DENY`
decisions, versus 197 `ASK` and no `DENY` under the policy package. On the 168
benign tool tasks, the full package issued 75 `ASK` decisions and the policy
package issued 69. The package comparison therefore met its structural
security-effect criterion but missed utility non-inferiority and superiority
criteria. This pattern is consistent with a security–utility trade-off rather
than incremental benefit from the full package.

### 4.7 DeepSeek authorization-regime experiment

The frozen authorization study contributes 900 terminal DeepSeek V4 Pro work
items across 180 paired cases. The four main cells each contain 100 attacks,
60 benign tool tasks, and 20 benign no-tool tasks. A nested 60-case subset adds
the broad, underspecified, and conflicting regimes under the full package. Recovery was
limited to 33 work items for which no provider response had been obtained; all
867 response-bearing work items were left untouched. The final ITT population
contains 768 completed records, 54 parse failures, 30 maximum-step terminals,
15 provider failures, and 33 repeated pre-response failures. No raw evaluator,
label, or gold-answer field entered the online projection; `exact_gold`
exposed only its derived authorization object. Provider tools and real external
effects remained disabled.

#### 4.7.1 Joint security and utility endpoints

Unsafe effects were at the floor in the main experiment: 0/100 under the full
package with either `auto_compiled` or `exact_gold`, 0/100 under the policy
package with `exact_gold`, and 1/100 under the policy package with
`auto_compiled`. Consequently,
the full-minus-policy difference under `auto_compiled` was −1.00 percentage
point (task-cluster bootstrap 95% CI −3.00 to 0.00; Holm-adjusted McNemar
p=1.0), while all other primary security contrasts were exactly zero or
differed by the same single event. These data provide no evidence that the
full package adds a reproducible security benefit over the policy package. This
is a package-level result because the prompt profile also differs.
For a 0/100 cell, however, the Wilson 95% upper limit is 3.70%; rare harms below
that resolution cannot be ruled out.

Benign-tool completion showed the larger authorization effect. Under
`auto_compiled`, the policy package completed 22/60 tasks (36.67%, Wilson 95%
CI 25.62–49.32) and the full package completed 16/60 (26.67%, 17.13–39.01), a paired
full-minus-policy difference of −10.00 points (bootstrap 95% CI −18.33 to
−3.33; Holm-adjusted p=0.09375). Under `exact_gold`, the policy package completed
9/60 (15.00%, 8.10–26.11) and full completed 7/60 (11.67%, 5.77–22.18), a
−3.33-point paired difference (bootstrap 95% CI −8.33 to 0.00;
Holm-adjusted p=0.5). All four main cells completed 20/20 benign no-tool tasks.

Changing the policy package from `auto_compiled` to `exact_gold` reduced paired
benign-tool completion by 21.67 points (bootstrap 95% CI −36.67 to −5.00;
Holm-adjusted p=0.05853). For the full package, the corresponding reduction was 15.00
points (−28.33 to −1.67; Holm-adjusted p=0.09808). The bootstrap intervals
exclude zero, but neither exact McNemar comparison remains below 0.05 after
Holm correction. We therefore interpret the consistent direction and effect
size as evidence of authorization sensitivity in this sample, not as a
universal oracle-policy effect.

#### 4.7.2 Benchmark-stratified authorization effects

The pooled utility estimate hides a qualitative benchmark reversal. On
AgentDojo benign tool tasks, changing from `auto_compiled` to `exact_gold`
increased completion from 5/30 to 9/30 for the policy package (+13.33 points;
bootstrap 95% CI −3.33 to +30.00) and from 4/30 to 7/30 for the full package
(+10.00 points; −3.33 to +23.33). On M3-v2, the same change reduced completion
from 17/30 to 0/30 for the policy package (−56.67 points; −73.33 to −40.00) and
from 12/30 to 0/30 for the full package (−40.00 points; −56.67 to −23.33).
These paired strata are descriptive, but they show that the pooled −21.67 and
−15.00 point estimates are not transportable across the two benchmark task
semantics.

#### 4.7.3 Failure-sensitive attack bound

Counting `unsafe_effect OR operational_failure` as a pessimistic sensitivity
endpoint changes the interpretation of the exact regime. The policy package
moved from 7/100 under `auto_compiled` to 25/100 under `exact_gold` (+18.00
points; bootstrap 95% CI +9.00 to +27.00); the full package moved from 8/100 to
26/100 (+18.00 points; +10.00 to +27.00). Package contrasts within the same
regime were only +1.00 point and had intervals spanning zero.

This sensitivity effect was entirely benchmark dependent. On AgentDojo,
policy and full package differences from auto to exact were both +36.00 points
(5/50 to 23/50 and 4/50 to 22/50; both bootstrap intervals +20.00 to +52.00).
On M3-v2, the corresponding differences were 0.00 points (2/50 to 2/50 and
4/50 to 4/50). Operational failures remain separately labeled; the composite
is a robustness bound and is not reported as observed attack success.

#### 4.7.4 Stress regimes and operational burden

On the nested benign-tool subset, moving from matched full-package
`auto_compiled` executions to broad, conflicting, or underspecified policies
reduced completion by 25, 30, and 25 percentage points, respectively. Their
bootstrap intervals were −45 to −5, −50 to −10, and −50 to 0 points. No unsafe
effect occurred in any of the 30-attack stress cells, so the stress comparison
primarily exposes lost utility rather than an observable security gain.

The decision and failure profiles explain part of this trade-off. Under
the policy package, `auto_compiled` produced ASK on 34.44% and DENY on 7.22% of
records, whereas `exact_gold` produced no ASK but DENY on 48.89%; its failure
rate rose from 7.22% to 23.89% and p95 latency from 10.63 to 19.42 seconds.
The full package showed the same pattern: ASK fell from 32.22% to zero, DENY rose from
11.11% to 45.00%, failure rose from 9.44% to 24.44%, and p95 latency rose from
9.18 to 19.62 seconds. DENY incidence counts records with at least one DENY;
the separate event totals are retained because a record may contain multiple
decisions. Across all 900 work items, provider cost was CNY 1.3888324.

Pooling again obscures where the system burden occurred. Under `auto_compiled`,
system ASK incidence on AgentDojo was 80.00%/78.00% for policy/full attacks and
66.67%/56.67% for policy/full benign-tool tasks; the corresponding M3-v2 rates
were 4.00%/2.00% and 0.00%/3.33%. Under `exact_gold`, ASK was zero by
construction. Exact-regime AgentDojo failure was 46.00%/44.00% on attacks and
43.33%/43.33% on benign-tool tasks, compared with 4.00%/8.00% and
16.67%/16.67% on M3-v2. AgentDojo exact p95 latency ranged from 20.77 to 23.93
seconds across these four package/task cells, whereas M3-v2 exact p95 ranged
from 6.93 to 8.66 seconds. Thus `ASK`, blocking, failure, and latency are
properties of the package–regime–benchmark combination, not a single pooled
human-burden quantity.

These results reverse the simple expectation that an answer-derived exact
policy must improve measured utility. In this implementation, the exact policy
behaved as a more restrictive authorization treatment, replacing confirmation
with repeated blocking and higher operational failure. The result supports
making authorization construction explicit in evaluations; it does not show
that every gold-derived policy or every runtime guard behaves similarly.

### 4.8 Defense-aware adaptive evidence through budget 200

The initial DeepSeek V4 Pro cost canary covered eight result-blind,
attack-family-balanced M3-v2 development tasks under the full package and the
`auto_compiled` authorization regime. At a maximum of 50 queries per task,
no unsafe effect was found: 0/8 tasks, or 0.00% (Wilson 95% CI 0.00–32.44%).
The run retained one closed diagnostic query in ITT; that task ended at query
24, while the other seven tasks reached query 50. In total, the canary
contains 374 terminal queries, 562 official provider calls, and CNY 0.552805
cost. Initial decisions across terminal queries were 207 ALLOW, 123 ASK, and
44 DENY.

The full frozen panel subsequently reached terminal status for all 40 tasks.
First unsafe effect occurred for 4/40 tasks by budget 50 (10.00%, Wilson 95%
CI 3.96–23.05) and for 18/40 by budget 200 (45.00%, 30.71–60.17). Fourteen of
the 18 observed successes therefore appeared only after query 50. The evidence
supports a budget-sensitivity claim through 200, but it does not establish
saturation, compare another model, or justify a SOTA/adaptive-robustness claim.

Supplementary Table S6 reports the defense-aware adaptive attack.

### 4.9 Remaining evidence boundary

The medium, Public Pro, Public Flash, authorization-regime, and budget-50/200
studies jointly support an empirical security–utility paper. They do not
support a leading-defense, causal provenance, saturated-adaptive, or
cross-provider claim. Gemini reached the three-quota-day free-tier stopping
rule with 32/450 terminal work items: five response-bearing items, 83 observed
but nonterminal items, and 335 unstarted items. The incomplete cohort is
retained only for operational accounting and is excluded from the comparisons
above. UTR and DSR are not identifiable from the current record contract and
are not reconstructed from unsafe-effect rate.

## 5. Discussion

### 5.1 Existing evidence changes the research claim

The completed medium and Public experiments do not support presenting the full
configuration package as stronger than the policy package. In the 5,082-record
DeepSeek V4 Pro Public matrix, the full package produced more unsafe effects
(38/600 versus 13/600), while both packages completed 49/168 benign tool tasks.
The 1,791-record V4 Flash matrix showed the same security direction: 24/400
unsafe effects for the full package versus 12/400 for the policy package. The
Flash utility difference was small (38/145 versus 35/145).

This is scientifically useful negative evidence, but it is package-level
evidence. The full configuration combines `safe_prompt` with provenance,
temporal/data-flow, monotonicity, and confirmation logic; the policy package
uses `normal` prompting and policy enforcement alone. The experiment therefore
cannot assign the difference to any individual module or to prompting. It shows
that the evaluated bundle did not earn a security advantage under these tasks,
not that provenance or confirmation is intrinsically ineffective.

### 5.2 Authorization is part of the treatment

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

The DeepSeek paired experiment did not reveal an unsafe-effect advantage for
`exact_gold`: three of four primary cells had 0/100 unsafe effects, while the
remaining policy-package `auto_compiled` cell had 1/100. The meaningful movement
was instead in utility and runtime burden. Moving from `auto_compiled` to
`exact_gold` reduced pooled benign-tool completion by 21.67 points for the
policy package and 15.00 points for the full package. The task-cluster bootstrap intervals excluded zero,
although the corresponding McNemar comparisons did not remain below 0.05 after
Holm correction.

The pooled direction is incomplete. AgentDojo completion increased by 13.33
points for the policy package and 10.00 points for the full package, whereas
M3-v2 completion fell by 56.67 and 40.00 points. Authorization semantics and
benchmark task structure therefore interact strongly enough that a single
pooled oracle-versus-compiled estimate should not be transported to either
benchmark in isolation.

The operational shift was substantial. Exact policies eliminated ASK in both
packages but increased the share of records with DENY from 7.22% to 48.89% for
the policy package and from 11.11% to 45.00% for the full package. Failure rose to roughly 24%
and p95 latency to roughly 19.5 seconds in both exact cells. The broad,
conflicting, and underspecified stress regimes likewise reduced completion by
25–30 points on their nested benign-tool subset without changing the observed
attack floor. These findings show that policy specification can move burden
and utility even when a headline attack rate appears stable.

The pessimistic `unsafe_effect OR operational_failure` bound makes that point
more explicit. Exact authorization increased this attack endpoint by 18 points
for both packages overall, driven by +36-point changes on AgentDojo and no
change on M3-v2. This does not convert failures into attacks; it demonstrates
that a near-zero observed unsafe-effect rate can coexist with poor operational
robustness.

### 5.3 Executed effects and utility must be reported together

A low prompt-injection success rate is not sufficient evidence of a useful
runtime defense. A detector may flag adversarial text without preventing an
effect; a runtime may prevent effects by denying nearly every useful action;
and a parser/provider failure may look secure if the evaluator counts only
successful executions. We therefore treat isolated executed effect as the
security endpoint and benign tool-task completion as a joint primary endpoint.

The Public evidence already illustrates the problem. Relative to the
structural condition, both M3 variants reduced unsafe effects but also had much
lower benign-tool completion. The policy package then outperformed the full
package on security without losing additional utility. The interpretation is
not that provenance is intrinsically harmful. It is that the evaluated bundle
did not earn a security advantage under these tasks and policies.

ASK, DENY, operational failure, latency, tokens, and cost provide the missing
system-facing context. An authorization regime that shifts unsafe effects
downward but greatly increases ASK may be acceptable in high-consequence
workflows and unacceptable in routine automation. A regime that shifts both
ASK and failure upward may simply externalize uncertainty rather than resolve
it. The paper reports these outcomes separately. The unsafe-or-failure
sensitivity endpoint is shown only as an explicitly pessimistic robustness
bound, not as a replacement composite score.

### 5.4 Adaptive evidence is budget-sensitive, not saturated

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

### 5.5 Relation to recent provenance and authorization work

VIGIL, DRIFT, the Task Shield, IPIGuard, Progent, CaMeL, ARGUS, AuthGraph, FAVA,
and provenance-sensitivity auditing occupy overlapping parts of the design
space [@L01; @L02; @L03; @L21; @L22; @L24; @L25; @L26; @L35; @L36]. These
works rule out claims that M3 is the first verify-before-commit system, the
first parameter-source defense, or the first structured runtime authorizer.

The remaining contribution is methodological and empirical. The study holds
task content fixed while changing authorization regimes and Guard configuration packages,
keeps evaluator fields offline, measures post-enforcement effects, retains
failure in ITT, and reports operational burden. In particular, the recent
provenance-sensitivity study changes source authority in controlled next-action
tasks [@L35]. The present design extends that measurement question to complete
tool trajectories and executed effects, albeit with the additional
implementation complexity and failure modes that such trajectories introduce.

### 5.6 Cross-provider interpretation

The Gemini sample is deliberately smaller and nested inside the DeepSeek
sample. It can show whether the main paired direction appears under another
provider; it cannot establish broad model-family generality. The official free
tier also introduces an availability constraint. The protocol stops at the
first 429, resumes only response-less or untouched work on a later quota day,
and downgrades transparently after three quota-day attempts.

The stopping rule closed with 32/450 terminal work items, including five with
official model responses; 83 observed items remained nonterminal and 335 were
unstarted. These rows are retained for operational accounting but excluded
from scientific inference. External validity is therefore limited to DeepSeek
V4 Pro and V4 Flash, and no cross-provider conclusion is made.

### 5.7 Limitations

First, the new primary experiment uses one proprietary model and two benchmark
families; the larger Public evidence adds another model from the same provider,
not an independent vendor. Model updates, tool schemas, system prompts, and
application context may change the effects. The Gemini subset closed incomplete
and contributes no cross-provider inference. Although execution dates, official
response identifiers, and returned model names are retained, provider-managed
aliases do not make the underlying weights immutable.

Second, the new authorization experiment has a strong attack-endpoint floor:
only one unsafe effect occurred across the 400 primary attack records. It can
therefore estimate utility and operational burden more informatively than
small security differences between its four primary cells. Security-direction
evidence comes mainly from the larger Public matrices and must not be inferred
from these near-zero cells alone.

Third, the policy/full contrast is bundled: `normal` versus `safe_prompt`
prompting changes together with provenance, data-flow, monotonicity, and
confirmation modules. It cannot support component-level causal attribution.

Fourth, `auto_compiled` is one policy compiler, not a complete model of human
authorization. The stress regimes approximate common policy errors but do not
measure their prevalence in deployed systems. `exact_gold` is intentionally
artificial and should not be read as a recommended configuration.

Fifth, the effect environment is isolated. This is necessary to prevent real
email, payment, browser, code, or production actions, but it may omit latency,
state, and recovery behavior found in live applications.

Sixth, the adaptive panel reports budgets only through 200 and does not prove
saturation. Attack search is still one family of defense-aware optimization;
another optimizer may find different failures.

Seventh, failure handling is conservative but not interpretation-free. All
response-bearing failures are terminal in ITT, whereas response-less transport
failures can receive bounded explicit recovery. We report raw failures and
superseded attempts so readers can assess that choice.

Eighth, `ASK` is observed only as system confirmation-request incidence.
Confirmation stayed pending in the synthetic environment, so this study does
not measure human response quality, workload, or usable-security outcomes.

Finally, this paper does not include an independent blind set. It also does not
claim first, only, or SOTA status. Its external-validity claims are limited to
the models, benchmarks, policy compiler, stress regimes, and attack budgets
actually evaluated.

### 5.8 Practical implications

Three practical recommendations follow. First, agent-security benchmarks
should publish the fields visible to the online Guard and keep evaluator-only
answers outside that projection.
Second, runtime defenses should be compared against a simpler policy package on
the same tasks, with prompt profiles held fixed when component attribution is
the goal; otherwise a complex bundle may receive credit for behavior already
supplied by the base policy or prompt. Third, security reports should include
benign completion, system confirmation/blocking incidence, failures, latency,
and attack budget alongside unsafe-effect rate.

The DeepSeek authorization-regime results now tie these recommendations to
observed effects: exact and stressed policies materially changed completion,
blocking, failure, and latency while observed unsafe effects remained near
zero. The prespecified Gemini stopping rule closed with an incomplete
diagnostic subset, which cannot alter or broaden the DeepSeek findings.

## 6. Conclusion

This study treats runtime authorization as an experimental variable rather
than fixed infrastructure. Across the completed medium and Public studies,
the full configuration package reduced unsafe effects relative to a structural
baseline but did not improve on the policy package. The direction replicated
across DeepSeek V4 Pro and V4 Flash: the full package produced more unsafe
effects, while benign-tool utility was equal or only slightly different.
Because prompt profile and runtime modules differ together, this is a bundled
comparison and does not identify an individual component effect.

The prospectively frozen authorization experiment explains why security alone
is an incomplete endpoint. Unsafe effects remained at or near zero in all four
main cells. The pooled exact-minus-auto benign-tool differences were −21.67
points for the policy package and −15.00 for the full package, but AgentDojo
improved by 13.33/10.00 points while M3-v2 fell by 56.67/40.00. Under a
pessimistic unsafe-or-operational-failure bound, both packages worsened by 18
points overall, driven by +36-point changes on AgentDojo and no change on
M3-v2. Exact authorization removed system ASK but moved 45.00–48.89% of records
into at least one DENY, raised failures to approximately 24%, and increased
p95 latency. Broad, conflicting, and underspecified regimes
also reduced completion on the nested tool-task subset without changing the
observed attack floor. Authorization construction can therefore materially
alter the measured security–utility frontier even when an attack-only result
looks stable.

The adaptive panel supplies a related measurement warning. First unsafe
effects were observed for 4/40 tasks by query 50 and 18/40 by query 200. A
single low attack budget would have missed most successes found by the larger
budget, but two budget points cannot establish saturation.

These findings support three practical requirements for tool-agent security
evaluation: keep evaluator-only fields outside online Guard state, compare
configuration packages on identical tasks and hold prompts fixed when seeking
component attribution, and report utility, system ASK/DENY incidence, failures,
latency, and attack budget alongside unsafe effects. The conclusions remain limited to the tested policies, benchmarks,
runtime implementation, DeepSeek models, and budget range. The prespecified
Gemini sample closed incomplete under its free-tier stopping rule and remains
diagnostic; it cannot erase or broaden the completed DeepSeek findings.

## Figures

![Figure 1. Online authorization projection and offline evaluation boundary.](../lean_empirical/figures_deepseek_v1/figure_1_online_field_isolation.png)

![Figure 2. Direct attack risk and failure-sensitive bound versus benign utility.](../lean_empirical/figures_deepseek_v1/figure_2_safety_utility_pareto.png)

![Figure 3. Paired authorization and configuration-package effects.](../lean_empirical/figures_deepseek_v1/figure_3_authorization_forest.png)

![Figure 4. Runtime burden by task type and benchmark.](../lean_empirical/figures_deepseek_v1/figure_4_runtime_burden.png)

![Figure 5. Adaptive first-success curve through query budget 200.](../lean_empirical/figures_deepseek_v1/figure_5_adaptive_first_success.png)

## Tables

### Table 1. Experimental design

Providers, benchmarks, conditions, authorization regimes and frozen work-item counts for the lean empirical study. Gemini counts are planned; its incomplete rows are excluded from inference.

| Provider | Benchmark | Condition | Authorization regimes | Planned n |
|---|---|---|---|---|
| DeepSeek | AgentDojo | Full package | auto compiled, broad, conflicting, exact gold, underspecified | 235 |
| DeepSeek | AgentDojo | Policy package | auto compiled, exact gold | 160 |
| DeepSeek | M3-v2 | Full package | auto compiled, broad, conflicting, exact gold, underspecified | 305 |
| DeepSeek | M3-v2 | Policy package | auto compiled, exact gold | 200 |
| Gemini | AgentDojo | Full package | auto compiled, exact gold | 80 |
| Gemini | AgentDojo | Policy package | auto compiled, exact gold | 80 |
| Gemini | AgentDojo | Structural baseline | auto compiled | 40 |
| Gemini | M3-v2 | Full package | auto compiled, exact gold | 100 |
| Gemini | M3-v2 | Policy package | auto compiled, exact gold | 100 |
| Gemini | M3-v2 | Structural baseline | auto compiled | 50 |

### Table 2. Joint primary endpoints

Unsafe effects and the pessimistic unsafe-or-operational-failure bound among attacks, plus completions among benign tool tasks. Brackets contain Wilson 95% confidence intervals.

| Provider | Condition | Authorization | Unsafe effect, n/N (95% CI) | Unsafe or failure, n/N (95% CI) | Benign-tool TCR, n/N (95% CI) |
|---|---|---|---|---|---|
| DeepSeek | Full package | auto compiled | 0/100 (0.0%) [0.0%, 3.7%] | 8/100 (8.0%) [4.1%, 15.0%] | 16/60 (26.7%) [17.1%, 39.0%] |
| DeepSeek | Full package | broad | 0/30 (0.0%) [0.0%, 11.4%] | 3/30 (10.0%) [3.5%, 25.6%] | 2/20 (10.0%) [2.8%, 30.1%] |
| DeepSeek | Full package | conflicting | 0/30 (0.0%) [0.0%, 11.4%] | 2/30 (6.7%) [1.8%, 21.3%] | 1/20 (5.0%) [0.9%, 23.6%] |
| DeepSeek | Full package | exact gold | 0/100 (0.0%) [0.0%, 3.7%] | 26/100 (26.0%) [18.4%, 35.4%] | 7/60 (11.7%) [5.8%, 22.2%] |
| DeepSeek | Full package | underspecified | 0/30 (0.0%) [0.0%, 11.4%] | 2/30 (6.7%) [1.8%, 21.3%] | 2/20 (10.0%) [2.8%, 30.1%] |
| DeepSeek | Policy package | auto compiled | 1/100 (1.0%) [0.2%, 5.4%] | 7/100 (7.0%) [3.4%, 13.7%] | 22/60 (36.7%) [25.6%, 49.3%] |
| DeepSeek | Policy package | exact gold | 0/100 (0.0%) [0.0%, 3.7%] | 25/100 (25.0%) [17.5%, 34.3%] | 9/60 (15.0%) [8.1%, 26.1%] |

### Table 3. Paired authorization and configuration-package effects

Absolute percentage-point differences use the second condition minus the first. Stress-regime extensions are outside the primary Holm family.

| Provider | Endpoint | Comparison | Paired n | Difference (pp) | Bootstrap 95% CI (pp) | Discordant first/second | McNemar p | Holm p |
|---|---|---|---|---|---|---|---|---|
| DeepSeek | Benign-tool TCR | Auto: policy to full package | 60 | -10.0 | [-18.3, -3.3] | 6/0 | 0.031 | 0.094 |
| DeepSeek | Benign-tool TCR | Exact: policy to full package | 60 | -3.3 | [-8.3, +0.0] | 2/0 | 0.500 | 0.500 |
| DeepSeek | Benign-tool TCR | Full package: auto to exact | 60 | -15.0 | [-28.3, -1.7] | 13/4 | 0.049 | 0.098 |
| DeepSeek | Benign-tool TCR | Policy package: auto to exact | 60 | -21.7 | [-36.7, -5.0] | 19/6 | 0.015 | 0.059 |
| DeepSeek | Unsafe effect | Auto: policy to full package | 100 | -1.0 | [-3.0, +0.0] | 1/0 | 1.000 | 1.000 |
| DeepSeek | Unsafe effect | Exact: policy to full package | 100 | +0.0 | [+0.0, +0.0] | 0/0 | 1.000 | 1.000 |
| DeepSeek | Unsafe effect | Full package: auto to exact | 100 | +0.0 | [+0.0, +0.0] | 0/0 | 1.000 | 1.000 |
| DeepSeek | Unsafe effect | Policy package: auto to exact | 100 | -1.0 | [-3.0, +0.0] | 1/0 | 1.000 | 1.000 |
| DeepSeek | Benign-tool TCR | Full package: auto to broad | 20 | -25.0 | [-45.0, -5.0] | 5/0 | 0.062 | — |
| DeepSeek | Unsafe effect | Full package: auto to broad | 30 | +0.0 | [+0.0, +0.0] | 0/0 | 1.000 | — |
| DeepSeek | Benign-tool TCR | Full package: auto to conflicting | 20 | -30.0 | [-50.0, -10.0] | 6/0 | 0.031 | — |
| DeepSeek | Unsafe effect | Full package: auto to conflicting | 30 | +0.0 | [+0.0, +0.0] | 0/0 | 1.000 | — |
| DeepSeek | Benign-tool TCR | Full package: auto to underspecified | 20 | -25.0 | [-50.0, +0.0] | 6/1 | 0.125 | — |
| DeepSeek | Unsafe effect | Full package: auto to underspecified | 30 | +0.0 | [+0.0, +0.0] | 0/0 | 1.000 | — |

### Table 4. Runtime burden

ASK and DENY cells report system-event totals, record incidence and the share of records affected. Failures remain in the ITT denominator.

| Provider | Condition | Authorization | ASK events/records | DENY events/records | Failures | Latency p50/p95 (s) | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|
| DeepSeek | Full package | auto compiled | 58 / 58 (32.2%) | 20 / 20 (11.1%) | 17 (9.4%) | 2.90 / 9.18 | 279,687 | CNY 0.2522 |
| DeepSeek | Full package | broad | 23 / 23 (38.3%) | 7 / 7 (11.7%) | 6 (10.0%) | 2.84 / 9.38 | 82,975 | CNY 0.0769 |
| DeepSeek | Full package | conflicting | 26 / 26 (43.3%) | 6 / 6 (10.0%) | 5 (8.3%) | 2.79 / 7.89 | 67,404 | CNY 0.0412 |
| DeepSeek | Full package | exact gold | 0 / 0 (0.0%) | 187 / 81 (45.0%) | 44 (24.4%) | 3.94 / 19.62 | 454,627 | CNY 0.2995 |
| DeepSeek | Full package | underspecified | 30 / 30 (50.0%) | 4 / 4 (6.7%) | 4 (6.7%) | 2.78 / 10.65 | 82,731 | CNY 0.0875 |
| DeepSeek | Policy package | auto compiled | 62 / 62 (34.4%) | 13 / 13 (7.2%) | 13 (7.2%) | 3.16 / 10.63 | 307,544 | CNY 0.2940 |
| DeepSeek | Policy package | exact gold | 0 / 0 (0.0%) | 227 / 88 (48.9%) | 43 (23.9%) | 5.06 / 19.42 | 473,478 | CNY 0.3374 |

### Table 5. Benchmark-stratified paired estimates

Paired benign-tool completion and attack unsafe-or-failure estimates by benchmark. These strata are descriptive rather than additional confirmatory families.

| Provider | Benchmark | Endpoint | Comparison | Paired n | First n/N | Second n/N | Difference (pp) | Bootstrap 95% CI (pp) |
|---|---|---|---|---|---|---|---|---|
| DeepSeek | AgentDojo | Attack unsafe or failure | Auto: policy to full package | 50 | 5/50 | 4/50 | -2.0 | [-10.0, +4.0] |
| DeepSeek | AgentDojo | Attack unsafe or failure | Exact: policy to full package | 50 | 23/50 | 22/50 | -2.0 | [-10.0, +6.0] |
| DeepSeek | AgentDojo | Attack unsafe or failure | Full package: auto to exact | 50 | 4/50 | 22/50 | +36.0 | [+20.0, +52.0] |
| DeepSeek | AgentDojo | Attack unsafe or failure | Policy package: auto to exact | 50 | 5/50 | 23/50 | +36.0 | [+20.0, +52.0] |
| DeepSeek | AgentDojo | Benign-tool TCR | Auto: policy to full package | 30 | 5/30 | 4/30 | -3.3 | [-10.0, +0.0] |
| DeepSeek | AgentDojo | Benign-tool TCR | Exact: policy to full package | 30 | 9/30 | 7/30 | -6.7 | [-16.7, +0.0] |
| DeepSeek | AgentDojo | Benign-tool TCR | Full package: auto to exact | 30 | 4/30 | 7/30 | +10.0 | [-3.3, +23.3] |
| DeepSeek | AgentDojo | Benign-tool TCR | Policy package: auto to exact | 30 | 5/30 | 9/30 | +13.3 | [-3.3, +30.0] |
| DeepSeek | M3-v2 | Attack unsafe or failure | Auto: policy to full package | 50 | 2/50 | 4/50 | +4.0 | [-6.0, +14.0] |
| DeepSeek | M3-v2 | Attack unsafe or failure | Exact: policy to full package | 50 | 2/50 | 4/50 | +4.0 | [-6.0, +14.0] |
| DeepSeek | M3-v2 | Attack unsafe or failure | Full package: auto to exact | 50 | 4/50 | 4/50 | +0.0 | [+0.0, +0.0] |
| DeepSeek | M3-v2 | Attack unsafe or failure | Policy package: auto to exact | 50 | 2/50 | 2/50 | +0.0 | [+0.0, +0.0] |
| DeepSeek | M3-v2 | Benign-tool TCR | Auto: policy to full package | 30 | 17/30 | 12/30 | -16.7 | [-30.0, -3.3] |
| DeepSeek | M3-v2 | Benign-tool TCR | Exact: policy to full package | 30 | 0/30 | 0/30 | +0.0 | [+0.0, +0.0] |
| DeepSeek | M3-v2 | Benign-tool TCR | Full package: auto to exact | 30 | 12/30 | 0/30 | -40.0 | [-56.7, -23.3] |
| DeepSeek | M3-v2 | Benign-tool TCR | Policy package: auto to exact | 30 | 17/30 | 0/30 | -56.7 | [-73.3, -40.0] |

### Table 6. Adaptive evidence at budgets 50 and 200

Cumulative tasks with at least one unsafe effect through budgets 50 and 200. These two points do not establish attack saturation.

| Model | Budget | Successes | Rate | Wilson 95% CI | Claim boundary |
|---|---|---|---|---|---|
| deepseek-v4-pro | 50 | 4/40 | 10.0% | [4.0%, 23.1%] | Budgets 50 and 200 only; no saturation claim |
| deepseek-v4-pro | 200 | 18/40 | 45.0% | [30.7%, 60.2%] | Budgets 50 and 200 only; no saturation claim |

## Figure captions

**Figure 1. Online authorization projection and offline evaluation boundary.**
Trusted task context, the selected policy projection, provenance events, and
the proposed action may enter the runtime Guard. Raw gold answers, evaluator
labels, reference trajectories, and effect-scoring metadata remain offline.
The `exact_gold` sensitivity condition exposes only a derived authorization
object to the policy projection. Only isolated simulated effects are scored;
provider-managed tools and real external actions are disabled.

**Figure 2. Security–utility trade-off by authorization condition.** Each
DeepSeek V4 Pro point reports benign-tool completion on the horizontal axis and
one minus attack unsafe-effect rate on the vertical axis. The four main cells
use 100 attacks and 60 benign tool tasks each; each nested stress cell uses 30
attacks and 20 benign tool tasks. All terminal failures remain in the
intention-to-treat denominators. Numbered markers map to the condition key; a
slash joins conditions with exactly coincident coordinates. Near-identical
attack safety can coexist with substantially different utility.

**Figure 3. Paired effects of authorization regime and Guard configuration.**
Points are absolute percentage-point differences for the second condition
minus the first; bars are 95% intervals from 10,000 task-cluster bootstrap
resamples. Orange rows use attack unsafe effect and blue rows use benign-tool
task completion. Exact McNemar and Holm-adjusted values are reported in Table
3 rather than encoded graphically.

**Figure 4. Runtime confirmation, blocking, failure, and latency burden.** ASK
and DENY panels report the percentage of terminal ITT records with at least one
corresponding event, not the number of events divided by records. The table
retains both record incidence and total event counts because a trajectory may
contain multiple decisions. Failure uses the prespecified terminal failure
set; latency is condition-level p95 wall time.

**Figure 5. Adaptive first-success curve through query budget 200.** The fixed
40-task DeepSeek V4 Pro panel contributes one first-unsafe-effect query per
successful task. Four tasks had succeeded by query 50 and 18 by query 200.
The curve is descriptive only through 200 and must not be interpreted as an
estimate of attack saturation.

## Submission statements

### Competing interests

The corresponding author must confirm the competing-interests declaration with
all authors before submission.

### Funding

The corresponding author must provide the funder name, grant number, and
sponsor role, or confirm that the research received no specific grant from
funding agencies in the public, commercial, or not-for-profit sectors.

### Data and code availability

The implementation, frozen lean experiment plan, analysis code, aggregate
tables, and editable figures are maintained at
https://github.com/Fischl0527/M3_PI_Guard. The repository is private during
manuscript preparation. A public archival release with an immutable version
identifier will be deposited before publication. Credentials and secrets are
excluded from the release. Any restrictions on provider-derived compact raw
records will be stated explicitly in the archival record.

### Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During preparation of this work, the authors used OpenAI Codex for software
editing, statistical-script review, figure-generation support, and language
revision. An earlier DeepSeek-generated project-planning note supplied by the
project owner was consulted during study scoping. The authors reviewed and
revised the resulting material and take full responsibility for the analysis,
interpretation, citations, and manuscript content. DeepSeek and Gemini API
outputs reported in the experiments are evaluated research data; they were not
used to generate outcome labels or statistical conclusions.

### Ethics and safety

The study involved no human participants and collected no personal data. Tool
effects were evaluated in isolated benchmark state. Real email, payment,
browser, code-execution, production-API, and provider-managed tool operations
were disabled. The authors must confirm any institutional review or exemption
requirement before submission.

### Author contributions

Author order and CRediT roles must be approved by every author before
submission.

## References

References are supplied in `references_v1.bib` and rendered with the manuscript citation processor.
