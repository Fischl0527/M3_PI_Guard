# Methods (pre-result draft)

## Study design and research questions

We use a prospective paired design to distinguish two questions that are often
conflated in evaluations of prompt-injection defenses for tool-using agents.
First, we measure how authorization information supplied to an online guard
changes measured security and utility. Second, under a non-oracle authorization
regime, we compare a policy-only monitor with a monitor that additionally uses
parameter provenance, temporal/data-flow constraints, and independent
confirmation.

The study asks whether exact per-case authorization inflates measured outcomes
(RQ1), whether the full M3 mechanism reduces unsafe effects beyond policy-only
and a peer-reviewed structural baseline (RQ2), whether its benign task
completion is non-inferior within five percentage points while exposing the
confirmation burden (RQ3), and whether conclusions remain directionally stable
across authorization regimes, benchmarks, models, languages, attack families,
and defense-aware adaptive attacks (RQ4).

The prospective protocol is
`protocols/paper_upgrade_v2/preregistration_v1.json`. Paper-v1 results are
historical only and cannot be reclassified as paper-v2 evidence.

## Threat model

The attacker controls untrusted documents, tool outputs, retrieved context, or
memory content that the agent may process while completing a trusted user
request. The attacker may know the defense structure and optimize an unsafe
effect that occurs after runtime enforcement. The attacker does not receive
policy rules, detector scores, evaluator explanations, expected malicious
actions, or answer keys. For adaptive experiments, public feedback is restricted
to the aggregate `ALLOW/ASK/DENY` outcome and whether an unsafe effect occurred.

Out of scope are training-time model poisoning, host compromise, credential
theft outside the agent, and direct modification of the trusted policy store.

## Online-state separation

Every run constructs its online state by an explicit allowlist projection.
Evaluator-only fields—including gold answers, expected actions, attack-success
labels, task-success labels, reference trajectories, and per-case exact policy
keys—are excluded unless the run is the explicitly labeled `exact_gold` oracle
ablation. The runtime records a canonical digest of visible field paths and
values. A run is inadmissible if a forbidden field appears or if the stored
digest does not match the runtime projection.

The five authorization regimes are `exact_gold`, `auto_compiled`, `broad`,
`underspecified`, and `conflicting`. The primary analysis uses
`auto_compiled`. `exact_gold` is an oracle sensitivity analysis and is excluded
from the primary endpoint.

The frozen runtime keeps three identities distinct. The source-projection
digest covers benchmark fields admitted to the agent. The initial-online-state
digest additionally covers condition configuration and any authorization state.
The experiment-record digest covers the initial state plus later visibility
events. This separation prevents a case-level digest from being reused across
conditions that actually expose different policy or detector state.

The `exact_gold` ablation is not serialized as a trusted policy. Its envelope
explicitly declares `source_class=evaluator_derived_authorization`, and every
such work item is excluded from the primary endpoint. The authoritative
execution freeze is
`protocols/paper_upgrade_v2/medium_execution_plan_v2.jsonl`; its superseded v1
pre-run ledger contains no outcomes.

For tasks whose user text refers to a trusted application panel, the model
message receives a separate allowlist projection of only `requested_actions`
and `workspace_scope`. The projection is condition invariant and excludes
evaluator labels, gold actions, expected effects, task-success fields, and
authorization answers. This prevents a missing trusted-context channel from
being misclassified as a defense failure while retaining the online/offline
boundary.

## M3 runtime mechanism

The common runtime interface remains `TaskPolicyManifest`,
`ActionProposal`, `GuardDecision`, and `ProvenanceEvent`. M3 policy-only applies
the compiled task policy without provenance, temporal/data-flow, or
confirmation modules. M3-full enables the complete module set. Automatic
transitions may maintain or reduce authority but cannot expand it. An expansion
requires an independent confirmation event, represented as `ASK`; approval,
denial, expiry, and confirmation errors are recorded separately.

The mechanism is evaluated by executed effects rather than by detector output.
`ALLOW`, `ASK`, and `DENY` are intermediate runtime decisions and are not
treated as security outcomes by themselves.

## Baselines

The six medium-study conditions are no defense, safe prompting or spotlighting,
PromptGuard as detector-only, the strongest admitted peer-reviewed structural
baseline, M3 policy-only, and M3-full. VIGIL is preferred as the structural
baseline and DRIFT is the fallback. Their official source commits and
source-backed adapters are recorded in
`protocols/paper_upgrade_v2/structural_baseline_registry_v1.json`.

Zero-call qualification is not a performance result. A baseline enters a
comparison only after its official constraint/model path runs on the same
model, tasks, attack content, and tool environment with complete logs.
PromptGuard remains detector-only and is never described as an execution
authorization system.

## Medium falsification sample

Before paper-v2 model runs, 72 paired cases were selected by deterministic
SHA-256 ranking within pre-outcome strata. The set contains 36 attacks, 24
benign tool tasks, and 12 benign no-tool tasks; 25 cases are context dependent.
Forty-eight M3-v2 development cases and 24 AgentDojo cases are included. The
selection did not inspect result files and did not use the internally sealed
holdout. Each case is assigned to all six core conditions under
`auto_compiled`; 24 cases also form segregated authorization-regime probes.

The frozen case manifest and index are
`protocols/paper_upgrade_v2/medium_case_manifest_v1.json` and
`medium_case_index_v1.jsonl`.

## Formal benchmark plan

The formal internal benchmark is M3-v2 and the primary public benchmark is
AgentDojo v1. The primary-model freeze contains 300 attacks and 150 benign M3
cases, and 300 attacks plus all 97 unique AgentDojo utility tasks. The
second-model freeze contains 200 attacks and 100 benign M3 cases, and 200
attacks plus the same 97 unique AgentDojo utility tasks. AgentDojo v1 exposes
only 97 unique utility tasks; tasks are not duplicated to manufacture the
planned 150/100 denominators. This feasibility deviation is reported in the
frozen manifest.

The internally sealed M3 holdout is not described as independently authored.
An independent 600-case claim requires a third-party author/custodian and a
valid custody chain.

For the public primary-model analysis, the two benchmark freezes contribute
847 unique cases and 5,082 case-condition records across the same six
conditions: 600 attacks and 247 benign tasks. A 24-record technical canary is
followed by four disjoint continuation shards containing 1,265, 1,265, 1,264,
and 1,264 records. Recovery is allowed only for never-started work keys under a
new hash-bound admission; a terminal formal-candidate or diagnostic row is
never retried. Each recovery process replays the closed prefix once, appends
new attempts, traces, budget events, and records with fsync, and performs a
complete terminal replay before review.

## Outcomes and failure handling

The primary security endpoint is the intention-to-treat unsafe-effect rate. Its
denominator includes every assigned attack case. Timeouts, parse failures,
maximum-step failures, provider failures, and runner failures remain in the
denominator and count conservatively for the primary security endpoint.

The primary utility endpoint is benign task completion. Secondary endpoints
include `ASK` rate, confirmation outcomes, benign initial `ASK`-or-`DENY` rate,
token use, provider calls/cost, and p50/p95 latency. Raw numerators and
denominators accompany every proportion. The medium cross-benchmark record
directly identifies unsafe effect and task completion, but it does not store a
separate per-action offline authorization label or a separate data-spill label.
Therefore UTR and DSR are reported as not identifiable for this matrix rather
than being reconstructed from, or relabeled as, unsafe-effect rate.
Dataset-specific later experiments may report UTR/DSR only when their frozen
evaluator contract supplies those labels.

## Statistical analysis and stopping rules

Proportions use Wilson 95% confidence intervals. Paired binary comparisons use
two-sided exact McNemar tests. Paired differences use 10,000 case-clustered
bootstrap resamples with frozen seeds, and declared comparison families use
Holm correction. Effect sizes and raw counts are reported regardless of
statistical significance.

The medium mechanism gate passes only if M3-full reduces unsafe effects
relative to the structural baseline by at least 10 percentage points or 20%
relative, benign-tool completion differs by no less than −5 percentage points,
M3-full is strictly safer than policy-only, the benign initial
`ASK`-or-`DENY` rate is below 90%, the prospectively frozen operational-quality
envelope passes, and model identity is auditable. The quality envelope retains
every terminal record in ITT, permits at most 10% primary-record operational
failures and at most 5% provider/timeout failures, and permits no runner
failure. The earlier zero-operational-failure value is reported descriptively
but does not replace this pre-access envelope. Failure redirects the paper to
an empirical study rather than removing negative results.

The paired discordant proportions from the medium study determine formal sample
size using the frozen paired-binary planning approximation, with power 0.80,
two-sided alpha 0.05, and the preregistered benchmark floors.

For the public primary matrix, evidence-integrity admission and
mechanism-quality eligibility are separate decisions. Exact matrix coverage,
terminal attempts, record/trace bindings, unpaused budgets, and ITT retention
are required for result access. The prospectively frozen 1% diagnostic ceiling
is not waived: exceeding it forbids a clean mechanism-quality claim but does
not justify deleting terminal rows. Any admitted analysis therefore retains
all diagnostics in ITT and follows the empirical security-utility route.
Because this matrix uses one model, it cannot support cross-model or
cross-provider claims.

## Adaptive evaluation

The primary-model adaptive panel contains 40 frozen development attacks at
budgets 50, 200, and 500. After complete budget-500 results, the 20 hardest
tasks are selected by the preregistered first-success rule and extended to
2,000 queries. A second model uses 20 frozen tasks at budgets 50 and 200. The
maximum planned query budget is 75,000. Search checkpoints are resume-safe, and
an already successful task does not spend later budgets.

Before that formal panel, an eight-task, eight-family cost canary fixes a
50-query maximum under the primary model and M3-full. A closed provider
diagnostic is retained as an ITT query and makes that task terminal; it is
never retried. Untouched tasks may proceed only through a separately hashed
continuation admission. The query ledger hashes the exact UTF-8 prompt bytes,
whereas the MCTS checkpoint hashes the canonical JSON string representation;
the technical reviewer verifies both documented hashes against the same
checkpoint node instead of equating the two digests. Canary analysis is
reported as exploratory and cannot substitute for the 40/20-task formal panel.

## Reproducibility and evidence admission

Source commits, dataset files, case indices, result records, and derived
artifacts are hash locked. For DeepSeek, every request is committed locally
before transport using a generated request ID and exact payload SHA-256. The
completed trace binds that commitment to the official response ID, exact
returned model identity, token/cache usage, and cost. A provider request-header
ID is retained when available but is not fabricated or required for this
evidence design. Unverified relays are diagnostic only.

The formal DeepSeek matrix fixes `thinking={"type":"disabled"}` and
`response_format={"type":"json_object"}` in both the transmitted payload and
the pretransport commitment. The prompt explicitly requests the frozen JSON
proposal schema, while the strict parser remains unchanged; response repair and
automatic retry are prohibited. The six-condition technical canary must
complete with formal-candidate identity and zero operational failures before a
separate continuation manifest can authorize the remaining work items.

Provider inference cannot directly execute effects. DeepSeek and Gemini, when
used, are restricted to their frozen official inference origins. Provider
managed tools and external connectors are disabled, and model tool calls remain
untrusted proposals. Effects can run only in `sandbox/public`, `example.test`,
`/mock/`, or a copied AgentDojo in-memory environment. Unknown, host-command,
real email/payment, production/private API, credential, browser/computer, or
non-sandbox filesystem effects fail closed. Every non-stub executor must attach
a credential-free safety receipt under
`protocols/paper_upgrade_v2/provider_safety_policy_v1.json`.

All table cells must be reconstructible from experiment-record JSONL files and
frozen manifests. A claim remains pending when its result artifact is absent;
missing evidence is never encoded as a favorable zero.

Scientific outcomes remain sealed until the prospective result gate replays and
cross-binds all record, attempt, budget, and per-work trace chains. Automatic
technical admission requires all 480 assigned records, no missing, duplicate,
unknown, or open work items, only prespecified terminal statuses, no runner
failure, an unpaused budget, isolated effects, and complete content-free trace
chains. Formal-candidate records require exact official DeepSeek identity; at
most 1% of records may be diagnostic, limited to closed provider/timeout
failures whose incomplete response evidence is explicitly retained in ITT.
Only a separately written result-analysis admission permits the preregistered
statistics to read `unsafe_effect_itt` and `task_completion`. The locked
expanded analysis reports all five authorization regimes, confirmation burden,
latency, tokens/cost, and benchmark/context/source-set heterogeneity without
changing the primary gate.

The Public primary statistics and comparison set were frozen before result
access, but the first implementation did not execute successfully. The v1
reader applied the experiment-record v1 schema to v2.2 envelopes; a first
correction selected the generic v2.2 cost policy; a second replayed the Public
completed-trace validator on deliberately incomplete diagnostic failures; and
a third validated ledger ingestion but did not project the v2.2 envelope at
the legacy statistics-helper boundary. Each attempt failed before a summary
was written, retained a bounded stderr/exit record, and was superseded through
a new hash-bound candidate and exact-command admission. No source record,
denominator, statistic, provider call, or claim boundary was changed.

The admitted v5 reader validates the v2.2 schema, visibility, decision,
outcome, tier, and safety-receipt semantics. Request-chain integrity is
inherited from the locked four-shard evidence reviews and primary merge.
Before the unchanged legacy statistics helper, it projects only the evidence
envelope to v1: scientific fields are copied verbatim, formal rows bind the
last official response, and diagnostic rows explicitly carry no response ID,
`identity_verified=false`, and `diagnostic_only`. The primary path produces
condition tables, Wilson intervals, exact McNemar tests, 10,000-resample paired
bootstrap intervals, benchmark strata, and figures.

A separate reviewer reads the original admitted record envelopes directly and
recomputes condition counts, Wilson intervals, four prespecified paired
differences, exact two-sided McNemar tests, and diagnostic retention without
reusing the primary aggregation or statistical helpers. Public claims are
released only because the v5 primary verifier and the independent reviewer
both reproduce exactly; all correction candidates, admissions, failure logs,
and final outputs are hash locked.
