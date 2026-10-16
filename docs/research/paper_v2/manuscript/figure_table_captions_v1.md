# Figure and table captions

Status: `current_corrected_v2_figures_historical_supplement_preserved`

## Figures

**Figure 1. Authorization, execution and evaluation boundaries.** Trusted intent,
projected authorization and runtime events are distinct from offline evaluation.
The dashed path denotes the oracle sensitivity condition: only an authorization
object derived from the offline target is exposed to the Guard, not the raw
gold or evaluator fields. Model proposals,
Guard decisions, isolation rejections, simulated execution, task completion,
failure and unknown outcomes remain distinct. Provider-managed tools and real
external effects are disabled.

**Figure 2. Corrected authorization and benign-tool completion.** Panel a shows
completion fractions and cached Wilson 95% intervals for 30 benign-tool tasks in
each benchmark and policy/full configuration under ordinary prompts. Panel b
shows the corresponding paired exact-target minus auto-compiled differences
with cached Newcombe 95% intervals, in percentage points. The two interval types
answer different questions. Exact-target is the oracle sensitivity condition;
the regimes and configurations use
overlapping paired tasks. ASK/DENY events and failures are separate in Table 2.

**Figure 3. Contemporaneous security and benign-tool utility.** Rows separate
AgentDojo native security verdicts from M3-v2 simulated effects; columns show
attack outcomes and benign-tool completion. Each condition has 30 planned
tasks per panel. Points and Wilson 95% intervals use observed denominators;
fractions show true/observed counts, with missing outcomes explicit. Configured
VIGIL has 28 observed AgentDojo outcomes and two unknowns per endpoint. Its
orange ITT identification range is not a confidence interval and does not treat
unknowns as safe failures. Configured VIGIL uses constraint generation and a
deterministic hybrid audit with secondary model verification disabled;
its 16-call limit differs from the other conditions' eight-call limit.

**Figure 4. First restrictions and final workflow states.** Each row contains
30 benign-tool assignments under one benchmark, authorization regime and
policy/full configuration. Panel a classifies the first publicly observed block;
panel b classifies final execution and completion states. The cached categories
are descriptive event summaries, not adjudicated root causes. P/F denotes
policy/full and A/E denotes
auto/exact target. ASK/DENY burden is reported separately in Table 2. No new
inferential test is introduced by these counts.

## Tables

**Table 1. Current study cohorts and configurations.** The corrected authorization,
contemporaneous calibration and bounded controls have distinct evidence roles.
The calibration's 120 cases are nested within the authorization sample's
180 cases, representing 153 underlying tasks. Oracle targets and configured
VIGIL's secondary-verification and call-budget limits are disclosed.

**Table 2. Corrected authorization and benign-tool completion.** Ordinary prompts
are fixed across policy/full and auto/exact target. Completion, cached Wilson
intervals, operational failure and ASK/DENY events are reported separately.

**Table 3. Contemporaneous security and benign-tool utility.** Benchmarks retain
their own security endpoints; unknowns, failures and original ITT bounds are
explicit. Configured VIGIL is not the complete official default implementation.

**Table 4. Bounded synthetic component controls.** Simulated effect, completion,
full-module ASK/DENY and in-memory sends are separate. Each entry is a controlled
execution, not a generalization estimate.

**Supplementary Table S17. E5 conditional adaptive tail.** Overall and attack-family results
report first legacy evaluator successes through 500 among the selected B200 survivors. The
table explicitly marks that it is not a complete original-panel B500 result.

**Supplementary Table S18. E6 contemporaneous attack-activity calibration.** DeepSeek legacy-labelled
risk positives, operational failures, the pessimistic risk-or-failure endpoint, and
ASK/DENY event counts are reported for six conditions on a historically
risk-enriched single-block cohort. The execution is separate, but 47/60 tasks
also anchor E3; the table does not estimate deployment prevalence, benign
utility, temporal repeatability, independent-sample replication, or a Gemini
effect.

**Supplementary Table S20. Corrected development study by benchmark.** The two completed
DeepSeek cohorts are reported separately from historical experiments and from
the deferred Gemini cohort. AgentDojo uses its native security verdict;
M3-v2 uses observed simulated effects. Benign-tool completion is shown
separately. V4.1 Flash is not the historical V4 Flash model. This development
batch does not establish a confirmatory defense advantage.
