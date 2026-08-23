# Figure and table captions

Status: `deepseek_complete_gemini_diagnostic_closed`

## Figures

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

## Tables

**Table 1. Experimental design.** Providers, models, benchmarks, case types,
authorization regimes, Guard conditions, and frozen work-item counts for the
lean empirical study.

**Table 2. Joint primary endpoints.** Unsafe effects among attack tasks and
task completions among benign tool tasks, with raw numerators, denominators,
rates, and Wilson 95% confidence intervals.

**Table 3. Paired authorization and mechanism effects.** Absolute differences,
task-cluster bootstrap intervals, discordant counts, exact McNemar p-values,
and Holm-adjusted p-values for the prespecified primary families. Stress-regime
extensions are reported outside the primary Holm family.

**Table 4. Runtime burden.** ASK/DENY event totals and record incidence,
operational failures, p50/p95 latency, tokens, and provider cost by condition.

**Table 5. Prespecified heterogeneity.** Endpoint counts by benchmark and
attack family. These strata are descriptive and are not additional
confirmatory testing families.

**Table 6. Adaptive evidence at budgets 50 and 200.** Cumulative tasks with at
least one unsafe effect, Wilson intervals, and the explicit no-saturation claim
boundary.
