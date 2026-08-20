# Methods — lean authorization study

Status: `deepseek_results_complete_gemini_pending`

## Study design and research questions

We conduct a paired empirical study of runtime authorization for tool-using
language-model agents. The design separates the information supplied to the
online Guard from the offline fields used to score the run. It then varies the
authorization regime and the Guard mechanism while holding the task, attack,
provider, model, tool environment, and evaluator fixed.

The study addresses three research questions:

1. **RQ1 — Authorization regime.** How do `exact_gold`, `auto_compiled`,
   `broad`, `underspecified`, and `conflicting` authorization regimes change
   executed unsafe effects, benign task completion, and `ASK/DENY` burden?
2. **RQ2 — Mechanism contribution.** Does the provenance/data-flow/
   confirmation logic in M3-full improve on the same runtime using policy-only
   enforcement, and what operational cost does it introduce?
3. **RQ3 — External validity and adaptive budget.** Are the observed
   directions stable across AgentDojo, M3-v2, a second provider, and the
   already completed defense-aware budgets 50 and 200?

Positive results are not a stopping condition. The analysis is retained if
`exact_gold` has little effect, M3-full underperforms policy-only, or the second
provider differs from the primary model.

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
Admitted fields include trusted user intent, the benchmark-visible task
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
model, parser, evaluator, tool environment, and task policy representation.

- **M3 policy-only** evaluates the proposed tool and arguments against the
  current task policy. Provenance propagation, temporal/data-flow checks, and
  independent confirmation are disabled.
- **M3-full** enables policy enforcement plus parameter provenance,
  temporal/data-flow constraints, permission-monotonic transitions, and
  confirmation. Automatic transitions may preserve or reduce authority;
  authority expansion produces `ASK` and requires an independent confirmation
  result.

`ALLOW`, `ASK`, and `DENY` are runtime decisions, not security outcomes by
themselves. Security is scored from the isolated post-enforcement effect
receipt. Utility is scored by the benchmark task-completion evaluator.

The Gemini subset adds the strongest available peer-reviewed structural
baseline under `auto_compiled`. The baseline is included to anchor the
cross-provider sample, not to support a universal ranking.

## Authorization regimes

Five regimes are evaluated:

- `auto_compiled`: task policy compiled from trusted user intent before
  untrusted evidence is processed;
- `exact_gold`: evaluator-derived authorization used only as an oracle
  sensitivity condition;
- `broad`: a deliberately permissive authorization envelope;
- `underspecified`: necessary details or constraints are omitted;
- `conflicting`: the authorization object contains mutually inconsistent
  constraints that the runtime must resolve or reject.

The four primary DeepSeek cells pair policy-only and M3-full with
`auto_compiled` and `exact_gold`. A fixed nested subset adds M3-full under the
three non-oracle stress regimes.

## Existing evidence reused without new calls

Four completed datasets are analyzed once:

- 5,082 DeepSeek V4 Pro records from the Public primary matrix;
- 1,791 DeepSeek V4 Flash records from the Public second-model matrix;
- 480 records from the medium falsification study; and
- the completed DeepSeek V4 Pro adaptive tasks at budgets 50 and 200.

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

Selection is stratified by benchmark, task type, and attack family. Every main
case is assigned to four cells: policy-only/`auto_compiled`, policy-only/
`exact_gold`, M3-full/`auto_compiled`, and M3-full/`exact_gold`. This produces
720 work items.

A nested 60-case subset receives three additional M3-full assignments:
`broad`, `underspecified`, and `conflicting`, adding 180 work items. The frozen
DeepSeek plan therefore contains 900 work items. The first six items form the
formal technical prefix and remain part of the final denominator.

## Frozen cross-provider sample

The Gemini study uses 90 cases nested within the DeepSeek main sample:

- 50 attacks;
- 30 benign tool tasks; and
- 10 benign no-tool tasks.

Each case receives five assignments: structural baseline/`auto_compiled`,
policy-only/`auto_compiled`, M3-full/`auto_compiled`, policy-only/`exact_gold`,
and M3-full/`exact_gold`. The plan contains 450 work items, including a six-item
formal prefix.

Gemini uses the official free tier with a paid ceiling of USD 0. At the first
HTTP 429, the active run stops and leaves all unstarted items pending. On a new
provider quota day, only unstarted items and work items with no official model
response are eligible for explicit recovery. After three quota-day attempts,
any still incomplete response-less work item is retained as a terminal
diagnostic. If the 450 planned items do not become terminal within that rule,
the observed subset is reported as diagnostic and no cross-provider
generalization claim is made.

## Providers and model identity

The primary model is DeepSeek V4 Pro through the official DeepSeek endpoint.
The cross-provider model is Gemini 3.6 Flash through the official Google
Generative Language OpenAI-compatible endpoint. Each request is assigned a
local request identifier and canonical payload digest before transport. A
response-bearing record retains the official response identifier, exact
returned model identity, usage, latency, and cost or free-tier attestation.

Prompts and model responses are not copied into the compact analysis file.
Content-free request metadata and the provider's internal trace remain under
the ignored run directory. Exact model identity is checked in the final
one-pass integrity validation.

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
- Gemini rate-limit recovery stops at the first 429 in each quota day and
  becomes terminal on the third quota-day attempt.

Earlier response-less attempts remain append-only in the raw file. The
scientific analysis selects the latest terminal attempt for each experiment
item and
reports the count of superseded attempts. No prior row is overwritten.

## Outcomes

The two joint primary endpoints are:

1. **unsafe-effect rate** on assigned attack tasks; and
2. **task-completion rate (TCR)** on assigned benign tool tasks.

Benign no-tool completion is descriptive. Secondary outcomes are `ASK` count,
`DENY` count, operational failure, p50/p95 latency, total tokens, API cost, and
predefined heterogeneity by benchmark and attack family.

All terminal work items remain in the intention-to-treat denominator. The
analysis reports raw numerator/denominator values alongside proportions. A
provider or parser failure is not silently removed and is not relabeled as a
successful security outcome.

## Statistical analysis

Each condition proportion receives a Wilson 95% confidence interval. The
paired analyses report the absolute difference in percentage points, the two
discordant counts, and a two-sided exact McNemar test. Uncertainty for the
paired absolute difference is estimated with 10,000 deterministic bootstrap
resamples clustered by task.

The four primary authorization/mechanism comparisons are:

1. policy-only `auto_compiled` versus policy-only `exact_gold`;
2. M3-full `auto_compiled` versus M3-full `exact_gold`;
3. `auto_compiled` policy-only versus M3-full; and
4. `exact_gold` policy-only versus M3-full.

McNemar p-values are Holm-adjusted separately for attack unsafe effect and
benign-tool TCR. The `broad`, `underspecified`, and `conflicting` comparisons
are reported as prespecified regime extensions. Model, benchmark, and attack-
family panels are descriptive heterogeneity analyses rather than additional
confirmatory families.

Adaptive evidence is limited to budgets 50 and 200. We report the cumulative
fraction of the fixed 40-task cohort with a first unsafe effect by query count
and the two observed budget points. We do not extrapolate a saturation level.

## Minimal verification and reproducibility

Verification is deliberately proportional to the lean study. It consists of:

1. focused unit tests for modified provider, authorization projection,
   evaluator, analysis, and plotting code;
2. the six-item formal prefix for each provider; and
3. one terminal pass over row count, experiment-item uniqueness, forbidden-field
   isolation, exact model identity, and ITT failure retention.

Each provider writes one append-only compact raw JSONL. The final statistics
are written once to one authorization-analysis JSON, and figures are exported
as editable SVG plus raster QA previews. Reproducibility assets include frozen
samples, condition assignments, analysis code, aggregate tables, and versioned
source.
