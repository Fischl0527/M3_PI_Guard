# Discussion — lean empirical study draft

Status: `corrected_v2_current_evidence_and_trusted_intent_review_integrated`

## Existing evidence changes the research claim

The corrected studies identify authorization burden as a central empirical
finding. Exact-target assistance improved AgentDojo completion, while the
contemporaneous control showed a substantial completion cost under compiled
authorization. Together, these observations connect the information available
to the Guard with useful execution, rather than equating module activation
with effective protection.

The tested full bundle added no identifiable end-to-end advantage over policy
modules. This negative result concerns the evaluated configuration, not the
intrinsic value of each mechanism. Historical package-direction observations
provide context, with their original endpoint definitions retained separately.

## Authorization is part of the treatment

Treating authorization as an experimental variable exposes a source of
security–utility variation that would otherwise remain hidden. Exact-target
scope supplies answer-derived information, whereas compiled scope must resolve
permissions from trusted intent. Holding the ordinary prompt fixed makes this
information contrast interpretable within the current paired design.

The matcher audit also clarifies what is being measured. Complete-argument
equality against partial target annotations conflated security scope with
schema-required content. Corrected matching separates these checks; its
completion contrast concerns compiled versus exact-target scope, not a
same-window estimate of the old matcher’s repair effect.

The trusted-intent review distinguishes permission insufficiency from a
declared-contract defect. AgentDojo’s natural-language and dynamic-target tasks
exceeded the generic compiler’s coverage, while the seven explicit application
declarations retained their action–target pairs. Unresolved-target cases expose
a need for independent clarification rather than automatic privilege expansion.
Successful execution without completion further shows that permission,
execution, and the task evaluator answer different questions.

## Provenance sensitivity exists at the decision layer

The historical source-authority replay showed provenance sensitivity at the
deterministic Guard boundary when proposition and policy were held fixed.
Its end-to-end trajectories instead reached a confirmation/blocking floor,
illustrating the distinction between decision behavior and usable execution.
E7a adds a third layer, permission eligibility under controlled approval
wording. Keeping these layers separate identifies where an interaction or
execution test is needed to connect mechanism behavior with task utility.

## Executed effects and utility must be reported together

Joint reporting distinguishes useful protection from inactivity. AgentDojo’s
native attack judgment and M3-v2’s simulated unauthorized effects remain
benchmark-specific security outcomes. Benign completion reveals whether
restrictions still permit useful work; failures and unknowns retain the
operational context needed to interpret both endpoints.

Confirmation, blocking, latency, tokens, and cost explain how that trade-off
arises at the system level. Frequent `ASK` decisions may be acceptable in
high-consequence workflows but costly in routine automation. Shorter task
latency may reflect earlier blocking rather than faster Guard computation.
Reporting these observations separately allows applications to evaluate the
trade-off without collapsing uncertainty into a single protection score.

## Adaptive evidence is budget-sensitive and conditionally extended

The historical adaptive panel’s first-success distribution changed with query
budget, supporting defense-aware evaluation rather than reliance on a weak
fixed attacker [@L27]. The selected survivor extension addresses a different,
conditional question: additional first success after surviving budget 200.
Separating these estimands preserves the information supplied by each stage.

## Historical calibration and corrected contemporaneous controls

Active controls help distinguish a defended floor from inactive attacks.
Historical E6 checked activity in a selected attack cohort, whereas the current
calibration also measures benign completion. Their differing samples, runtimes,
evaluators, and service periods make them complementary evidence rather than
a before/after repair comparison. The current AgentDojo utility contrast is
informative even though its security contrast remains uncertain.

## Relation to recent provenance and authorization work

Runtime verification, task alignment, least privilege, provenance graphs, and
capability-based flow control provide complementary ways to constrain agent
actions [@L01; @L02; @L03; @L21; @L22; @L24; @L25; @L26; @L35; @L36]. Our
study connects these designs to the authorization information and operational
conditions under which their utility is measured.

Controlled provenance-sensitivity auditing isolates source authority in
next-action selection [@L35]. The present programme relates that question to
deterministic Guard replay and complete tool trajectories, with distinct
decision and execution endpoints. The corrected authorization study adds a
paired scope comparison and a contemporaneous utility control.

## Cross-provider interpretation

Provider diagnostics are retained separately from model-effect estimates.
The incomplete Gemini attempts illustrate why response-complete paired
coverage, rather than administrative closure, is needed for provider
comparisons. The qualified current effects therefore remain DeepSeek results.

## Limitations

Security-effect inference is limited by sparse events. The 900-assignment
authorization study has no unguarded reference, while calibration supplies
only three AgentDojo control events and a zero-event M3-v2 control. These
conditions support utility comparisons more strongly than protection estimates.
Condition assignments also repeat cases: the authorization cohort has 180 cases
representing 153 tasks, and all 120 calibration cases are nested within it.
Historical cohorts overlap as documented; record totals are not independent
sample totals, and legacy risk labels are not corrected executed-effect estimates.

Authorization and comparator choices bound the configuration comparison.
`auto_compiled` is one bounded compiler; `exact_target_v2` supplies oracle-derived
scope, and the stress transformations do not estimate deployed policy-error
prevalence. The source-pinned VIGIL adaptation disables model-based secondary
verification and permits 16 calls rather than the eight-call M3 budget. Its
results concern that adaptation, not native VIGIL effectiveness. The current
900 assignments compare compiled with exact-target scope, not the old and
repaired matchers in the same execution window.

Incomplete observability limits outcome and cause attribution. Four calibration
outcomes are unknown, two projection receipts and four structured safety
receipts are missing, and four task durations are unavailable. Failures remain
in intention-to-treat accounting; response-less transport failures historically
received bounded recovery with superseded attempts retained. The 60-task
trusted-intent review reuses 240 calibration records and is post-outcome, without
independent reviewer-agreement calibration. It found no new declared-contract
violation, but redaction prevents resolving three mock-API completion mismatches
or adjudicating every false block. UTR and DSR are not identifiable from the
current record contract.

Mechanism and interaction attribution require further separation. The full
bundle combines provenance, data-flow, monotonicity, and confirmation, so its
comparison does not identify each component’s contribution. Source-authority
replay tests decisions; the corresponding trajectories encounter an action
floor. Historical `ASK` ends the trajectory. E7a tests in-memory permit
eligibility under intentionally mismatched wording and a shared wrapper, with
no model clarification, human participant, or backend commit. Human response
quality, workload, and completion benefits therefore remain unmeasured.

External validity remains limited to tested services and isolated effects.
DeepSeek Pro supplies the primary current comparisons; V4.1 Flash participates
in the sixteen synthetic controls and development evidence. Neither incomplete
Gemini attempt meets paired-coverage requirements, and no independent blind
set is included. Provider-managed aliases do not pin immutable weights despite
retained dates, response identifiers, and returned model names. Four synthetic
flow scenarios do not cover arbitrary transformations or natural-task efficacy.
Native dynamic-environment model validation remains incomplete; AgentDyn
motivates this extension [@L38], but loader and fixture checks are engineering
evidence rather than model results. Isolation also omits some live application
state, latency, and recovery behavior.

Historical adaptive and calibration findings retain conditional scope. E5’s
0/12 extension estimates a selected B200-survivor tail, with a 24.25% upper
confidence limit, not a complete B500 panel or saturation. Other search
families may expose different failures. E6 uses a historically risk-enriched,
attack-only cohort in one execution block, with 47/60 tasks overlapping E3.
It neither tests the original multi-window gate nor estimates deployment
prevalence, benign utility, temporal repeatability, or independent replication.

## Practical implications

The findings motivate explicit authorization interfaces and joint outcome
reporting. Benchmarks should publish the fields visible online and identify
oracle-derived scope separately. Runtime comparisons should hold prompts fixed
or use factorial assignments, retain an active unguarded control, and compare
the full bundle with a simpler policy condition.

Two next tests address the central uncertainties. A trusted, non-oracle target
resolution workflow could test whether compiler coverage improves completion
without expanding unauthorized scope. An independently sampled, active-control
evaluation could determine whether the resulting utility gain preserves
security. Both should retain decision, execution, completion, confirmation,
failure, and unknown outcomes as distinct observations.
