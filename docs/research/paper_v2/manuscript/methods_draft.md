# Methods — lean authorization study

Status: `deepseek_results_complete_gemini_diagnostic_closed`

## Study design and research questions

We conduct a paired empirical study of runtime authorization for tool-using
language-model agents. The design separates the information supplied to the
online Guard from the offline fields used to score the run. It then varies the
authorization regime and the deployed Guard configuration package while
holding the task, attack, provider, model, tool environment, and evaluator
fixed.

The study addresses five research questions:

1. **RQ1: Authorization regime.** How do `exact_gold`, `auto_compiled`,
   `broad`, `underspecified`, and `conflicting` authorization regimes change
   executed unsafe effects, benign task completion, and `ASK/DENY` burden?
2. **RQ2: Prompt and runtime components.** What are the independent main
   effects of the safety prompt and full runtime modules, and do they interact?
3. **RQ3: Conditional robustness and model replication.** Are the factor
   directions consistent on historically difficult attacks and on DeepSeek V4
   Flash?
4. **RQ4: Source authority.** When proposition, parameter value, position, and
   policy are held fixed, how does moving the proposition between trusted and
   untrusted sources change Guard and end-to-end behavior?
5. **RQ5: Adaptive tail risk.** Among attacks with no unsafe effect by budget
   200, how many prospectively selected tasks first succeed by budget 500?

Positive results are not a stopping condition. The analysis is retained if
`exact_gold` has little effect, the full package underperforms the policy
package, or the available replication evidence differs from the primary model.

## Threat model and safety boundary

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

## Online-state and evaluator separation

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

## Runtime conditions

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

The earlier authorization experiment changed prompt profile and runtime modules
together and is therefore retained only as a bundled configuration comparison.
The new concurrent factorial crosses both factors explicitly: policy versus
full modules and normal versus safe prompt. Its module main effect, prompt main
effect, and module-by-prompt interaction are therefore separately identified
within the fixed paired sample.

`ALLOW`, `ASK`, and `DENY` are runtime decisions, not security outcomes by
themselves. Security is scored from the isolated post-enforcement effect
receipt. Utility is scored by the benchmark task-completion evaluator.

The earlier incomplete Gemini sample remains diagnostic and is not extended in
the incremental study. No cross-provider claim is made. Structural baselines,
including the source-pinned VIGIL adapter, retain their earlier descriptive
role; the new experiments target causal confounding, source authority, risk
enrichment, same-provider model replication, and adaptive tail behavior rather
than rerunning a large baseline matrix.

## Authorization regimes

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

## Existing evidence reused without new calls

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

## Frozen primary sample

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

## Concurrent prompt-by-module factorial

E1 reuses the 180-case sample but reruns every case contemporaneously under
four `auto_compiled` cells: policy/normal, policy/safe, full/normal, and
full/safe. This produces 720 new work items and prevents an effect estimate
from being assembled across dates or execution identities. An eight-item
formal prefix covers all four cells and both attack and benign-tool tasks; it
is included once in the final denominator.

## Source-authority counterfactual

E2 contains 60 controlled tool tasks, evenly split between AgentDojo and
M3-v2. Thirty are supporting scenarios and thirty contain a parameter that
competes with the trusted request. The scenarios cover payment targets,
message recipients, file paths, calendar participants, data recipients, and
workspace objects.

Each task has `trusted_origin` and `untrusted_origin` versions. Proposition,
parameter value, relative position, and policy remain fixed; only source
authority changes. Policy/normal and full/normal are crossed with both source
variants, yielding 240 end-to-end work items. Separately, authorized and
unauthorized proposals are replayed through both Guard configurations for
every source variant, yielding 480 deterministic, zero-provider decisions.
Offline Guard replay and end-to-end system performance are reported as
different evidence layers.

## Risk-enriched challenge and Flash replication

E3 selects 60 historical attack cases, 30 per benchmark, that produced an
unsafe effect under at least one earlier public condition. Coverage of suite
and attack family is prioritized before the count of earlier unsafe
conditions; a fixed digest order breaks ties. Each case receives the four E1
factor cells, yielding 240 Pro runs. This outcome-enriched cohort estimates
conditional robustness on known difficult cases and cannot estimate natural
attack prevalence.

E4 uses a 90-case nested representative sample with 50 attacks, 30 benign tool
tasks, and 10 benign no-tool tasks. It repeats all four E1 cells on DeepSeek V4
Flash, yielding 360 work items. This is a same-provider model replication, not
a cross-vendor generalization study.

## Adaptive B200-survivor tail

E5 starts from the 22 of 40 defense-aware attack tasks with no unsafe effect by
query 200. Twelve were selected prospectively: all four A2 tasks and four each
from A1 and A3 by fixed digest order. Their existing search checkpoints are
continued from query 201 to at most 500 and stop at the first unsafe effect.
The maximum is 3,600 new queries. We report
`P(first success by 500 | no success by 200)`, first-success locations, a
conditional survival step function, family strata, query count, tokens, cost,
and failure. These twelve tasks are not merged into the original 40-task
cohort to construct a nominal full B500 curve.

## Providers and model identity

The primary model is DeepSeek V4 Pro through the official DeepSeek endpoint;
E4 uses DeepSeek V4 Flash through the same official provider. Earlier Gemini
free-tier observations remain diagnostic and receive no incremental calls.
Each new request is assigned a
local request identifier and canonical payload digest before transport. A
response-bearing record retains the official response identifier, exact
returned model identity, usage, latency, and cost or free-tier attestation.
For E5, the top-level compact cost object is empty, so request-level CNY
charges are read from the public provider trace bundle embedded in the same raw
query row. Its usage summary already aggregates multiple provider calls for the
query; missing attribution fails closed. The raw-row totals are checked against
the live append-only budget tracker during execution, and the paper analysis
does not need to read the internal ledger or change any experimental outcome.
Provider calls for the evidence reported here were made during July and August
2026. The returned names are provider-managed model aliases and therefore
identify the served model at request time without freezing its hidden weights.

Prompts and model responses are not copied into the compact analysis file.
Content-free request metadata and the provider's internal trace remain in a
restricted local run directory outside the analysis dataset. Exact model
identity is checked in the final one-pass integrity validation.

## Failure and recovery policy

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
- no automatic retry or cross-model fallback is permitted.

Earlier response-less attempts remain append-only in the raw file. The
scientific analysis selects the latest terminal attempt for each experiment
item and reports the count of superseded attempts. No prior row is overwritten.

## Outcomes

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

## Statistical analysis

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

For E1, binary outcomes are arranged as a within-case 2×2 design. The module
main effect is the average of full-minus-policy differences across prompts;
the prompt main effect averages safe-minus-normal differences across module
settings; and the interaction is the difference between those two prompt
effects. Ten thousand case-cluster bootstrap resamples provide intervals and
two-sided bootstrap sign p-values. Module, prompt, and interaction are
Holm-adjusted within the attack unsafe-effect and benign-tool TCR endpoint
families. The unsafe-or-failure factor analysis is a prespecified sensitivity
bound and is shown separately.

E2 uses the analogous source-by-module contrasts for unauthorized-argument
influence and authorized action execution. Source, module, and source-by-module
form the source experiment's adjustment family. Source-swap action changes are
paired by base task. Deterministic replay reports false allows, false blocks,
and an ALLOW/ASK/DENY heatmap without treating replay accuracy as end-to-end
system performance.

E3 and E4 report effect directions, absolute differences, and bootstrap
intervals but open no new significance family. E3 is an outcome-enriched
challenge analysis; E4 is a same-provider replication. Both retain their
sampling boundary in every table and figure.

The fixed design provides 100 paired attacks and 60 paired benign-tool tasks per
main contrast, split evenly by benchmark for the latter. With 0/100 observed
unsafe effects, the Wilson upper limit is 3.70%; within a 30-task benign-tool
benchmark stratum, intervals are necessarily much wider (for example, 0/30 has
an 11.35% upper limit). We report these design-precision limits instead of a
post hoc achieved-power calculation.

The original adaptive panel reports the cumulative fraction of the fixed
40-task cohort with a first unsafe effect at budgets 50 and 200. E5 separately
reports the conditional probability of a first success by 500 among twelve
prospectively selected B200 survivors and a conditional survival curve from
201 to 500. We neither combine the sampling frames nor extrapolate a saturation
level.

## Minimal verification and reproducibility

Verification is deliberately proportional to the lean study. It consists of:

1. focused unit tests for modified provider, authorization projection,
   evaluator, analysis, and plotting code;
2. an eight-item formal prefix for each regular incremental study and two
   five-query tail prefixes for E5; and
3. one terminal pass over row count, experiment-item uniqueness, forbidden-field
   isolation, exact model identity, and ITT failure retention.

Each study writes one append-only compact raw JSONL. Final statistics are
written once to one analysis JSON per study, and figures are exported
as submission-ready vector PDF, editable SVG, and raster PNG previews for
manuscript/QA use. Reproducibility assets include frozen samples, condition
assignments, analysis code, aggregate tables, and versioned source.
