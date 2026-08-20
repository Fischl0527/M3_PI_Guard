# Methodology review — lean empirical manuscript

Status: completed on the post-DeepSeek draft; Gemini stopping rule pending

## Scope and verdict

This review compares the current Methods and Results language with the compact
analysis implementation. It covers the frozen paired unit, ITT handling,
Wilson intervals, exact McNemar tests, Holm adjustment, clustered bootstrap,
stress-regime treatment, burden summaries, partial Gemini handling, and the
two-point adaptive analysis. It does not rerun an experiment or reconstruct a
historical evidence chain.

The implementation and manuscript are methodologically aligned. No result or
statistical estimate requires correction. Two explanations were strengthened:
an operational failure is not evidence of a useful defense merely because no
unsafe effect was observed, and the bootstrap resamples paired case identifiers
rather than individual condition rows.

## Review findings

| Item | Finding | Disposition |
|---|---|---|
| Inferential unit | Every primary contrast joins outcomes by `case_id`; both condition outcomes remain together | Pass |
| ITT population | Every terminal work item remains in the endpoint denominator; failures are separately counted | Pass with clarified wording |
| Proportion intervals | Condition rates use two-sided Wilson 95% intervals with raw numerator and denominator | Pass |
| Paired test | Two-sided exact McNemar uses the two discordant counts | Pass |
| Paired effect | The reported difference is second condition minus first in absolute percentage points | Pass |
| Bootstrap | 10,000 deterministic resamples draw paired cases with replacement | Pass with clarified wording |
| Multiplicity | Four primary contrasts are Holm-adjusted separately within unsafe-effect and benign-tool TCR families | Pass |
| Stress regimes | Broad, underspecified, and conflicting comparisons are prespecified extensions outside the primary Holm family | Pass |
| Heterogeneity | Benchmark and attack-family panels are descriptive and not promoted to confirmatory families | Pass |
| Operational burden | ASK/DENY event totals and record incidence are distinct; failure and latency use all terminal records | Pass |
| Partial Gemini | A partial cohort receives operational accounting only; the same content-free pause-event normalization used by the runner is applied, and paired inference requires 450/450 terminal work items | Pass |
| Adaptive analysis | First-success evidence stops at budgets 50 and 200 and makes no saturation claim | Pass |

## Interpretation constraints

The new authorization study has one unsafe effect across 400 primary attack
records. McNemar tests and bootstrap intervals are still computed correctly,
but the event floor makes small security contrasts weakly informative. The
manuscript therefore relies on the larger Public matrices for security
direction and uses the new experiment mainly to estimate utility and runtime
burden.

The two co-primary endpoints are reported together, but Holm adjustment is
performed within endpoint rather than across all eight endpoint-by-comparison
tests. This matches the prespecified analysis. The paper does not use a single
family-wise significance declaration across both endpoints and should continue
to emphasize effect size, interval, discordance, and practical interpretation.

Failures remain in ITT. A failed record with no observed unsafe effect still
has a false unsafe-effect indicator, so raw failure incidence must remain next
to the security rate. The manuscript now states explicitly that such a record
is neither task completion nor clean evidence of defense success.

## Submission boundary

No additional statistical method is required before the Gemini stopping rule.
After that rule closes, the same analysis may be run once on the terminal
cohort. Any incomplete Gemini subset remains diagnostic. The final manuscript
must preserve raw counts, paired direction, intervals, corrected p-values,
failure counts, the attack-floor limitation, and the no-saturation boundary.
