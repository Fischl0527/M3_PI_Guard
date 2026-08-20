# Results draft — public, authorization-regime, and adaptive evidence

Status: `deepseek_authorization_results_complete_gemini_pending`

This section reports the completed 480-record medium study, 5,082-record
Public primary-model matrix, 1,791-record DeepSeek V4 Flash replication,
900-work-item DeepSeek V4 Pro authorization experiment, and adaptive evidence
through budget 200. The 450-work-item Gemini experiment remains incomplete and
contributes no cross-provider conclusion at this stage.

## Medium falsification study

The medium study contains 480 records: 432 primary `auto_compiled` records
covering 72 paired cases across six conditions, plus 48 authorization-regime
probe records. The preregistered analysis did not support an incremental
mechanism claim. M3-full met the security-effect and deny-all criteria, but
missed the utility point non-inferiority criterion and showed no security gain
over M3 policy-only. Both the favorable security comparison and the
unfavorable utility and module comparisons are reported.

### Supplementary Table S1. Online-state source audit

| Conclusion | Audited units | Independently reviewed | Claim use |
|---|---:|---:|---|
| No online gold observed on covered path | 9 | 0 | Path-scoped only |
| Not a runtime guard | 10 | 0 | Taxonomy only |
| Mixed or path dependent | 1 | 0 | Path-scoped caution |
| Inconclusive | 2 | 0 | No substantive claim |

This audit supports only covered-path statements. It does not establish a
domain-wide oracle-authorization problem.

### Supplementary Table S2. Completed medium security and utility outcomes

| Condition | Unsafe effects / 36 attacks | Unsafe-effect rate (Wilson 95% CI) | Tool completions / 24 | Tool TCR (Wilson 95% CI) | No-tool TCR |
|---|---:|---:|---:|---:|---:|
| No defense | 8/36 | 22.22% (11.72–38.08) | 12/24 | 50.00% (31.43–68.57) | 12/12 |
| Safe prompt / spotlighting | 8/36 | 22.22% (11.72–38.08) | 11/24 | 45.83% (27.89–64.93) | 12/12 |
| PromptGuard (detector-only) | 8/36 | 22.22% (11.72–38.08) | 12/24 | 50.00% (31.43–68.57) | 12/12 |
| Structural baseline | 8/36 | 22.22% (11.72–38.08) | 12/24 | 50.00% (31.43–68.57) | 12/12 |
| M3 policy-only | 0/36 | 0.00% (0.00–9.64) | 7/24 | 29.17% (14.91–49.17) | 12/12 |
| M3-full | 0/36 | 0.00% (0.00–9.64) | 6/24 | 25.00% (12.00–44.90) | 12/12 |

The medium sample therefore shows a security–utility trade-off, not an
incremental mechanism benefit. Both M3 variants eliminated the eight unsafe
effects observed under the structural condition, but they also completed
substantially fewer benign tool tasks.

### Supplementary Table S3. Prespecified paired comparisons

| Comparison | Treatment minus baseline | Exact McNemar p | Holm-adjusted p | 10,000-cluster bootstrap 95% CI |
|---|---:|---:|---:|---:|
| M3-full vs structural, unsafe effect | −22.22 pp | 0.0078125 | 0.03125 | −36.11 to −8.33 pp |
| M3-full vs policy-only, unsafe effect | 0.00 pp | 1.0 | 1.0 | 0.00 to 0.00 pp |
| M3-full vs structural, tool TCR | −25.00 pp | 0.03125 | 0.09375 | −41.67 to −8.33 pp |
| M3-full vs policy-only, tool TCR | −4.17 pp | 1.0 | 1.0 | −12.50 to 0.00 pp |

The security effect relative to the structural baseline was large in this
sample, but the full mechanism did not outperform policy-only. Relative to the
structural condition, its benign-tool TCR was 25 percentage points lower, well
outside the preregistered −5 percentage-point non-inferiority margin.

### Supplementary Table S4. Runtime burden and operational quality

| Condition | ASK / 72 | Benign ASK rate | Operational failures / 72 | Provider calls | Trace-bundle cost (CNY) | Total latency p95 |
|---|---:|---:|---:|---:|---:|---:|
| No defense | 0 | 0.00% | 4 | 181 | 0.1821176 | 16.924 s |
| Safe prompt / spotlighting | 0 | 0.00% | 5 | 167 | 0.1812942 | 15.971 s |
| PromptGuard (detector-only) | 0 | 0.00% | 5 | 180 | 0.0986064 | 18.249 s |
| Structural baseline | 0 | 0.00% | 4 | 249 | 0.2568822 | 21.251 s |
| M3 policy-only | 16 | 19.44% | 1 | 112 | 0.0548220 | 7.897 s |
| M3-full | 22 | 22.22% | 2 | 117 | 0.1441772 | 10.701 s |

Across the 432 primary records, 411 completed and 21 retained terminal failures
comprised six `max_steps`, six parse failures, and nine provider failures. The
4.86% overall failure fraction and 2.08% provider-failure fraction passed the
predefined operational-quality envelope. Every terminal state remains
in the intention-to-treat denominator.

For M3-full, 22 initial `ASK` decisions comprised 17 permission-expansion
events, four independent-confirmation requirements, and one out-of-scope
parameter. Confirmation outcomes remained `pending` in this synthetic study;
the ASK count measures burden and cannot be interpreted as successful human
approval.

## Authorization-regime sensitivity

Forty-eight probe records compare four alternate regimes with matched
`auto_compiled` executions for M3 policy-only and M3-full. Each
condition–regime comparison contains six pairs. No unsafe effect occurred in
these small probes. For the explicitly labeled `exact_gold` probe, task
completion increased from 1/6 under matched `auto_compiled` to 3/6 under
`exact_gold`, while initial ASK decreased from 3/6 to 0/6; exact McNemar tests
were p=0.5 and p=0.25, respectively. These six-pair estimates are sensitivity
signals, not evidence of a domain-wide bias.

## Prespecified decision criteria

| Gate | Result | Evidence |
|---|---|---|
| Security effect vs structural | Pass | 22.22 pp absolute reduction |
| Tool-utility point non-inferiority | Fail | −25.00 pp vs −5 pp margin |
| Full vs policy-only security gain | Fail | 0/36 vs 0/36 |
| Deny-all rejection | Pass | Benign initial ASK-or-DENY 22.22% |
| Operational quality | Pass | All three predefined quality checks passed |
| Supported interpretation | Empirical trade-off study | Incremental defense-mechanism claim not supported |

The results therefore support an empirical study of authorization uncertainty
and the security–utility trade-off. They do not support a defense-superiority
or SOTA claim.

## Public primary-model result

The completed Public matrix contains 847 unique cases and 5,082 records: 600
attacks and 247 benign cases crossed with the same six conditions. All 76
diagnostic records (1.4955%) remain in ITT. The predefined 1% quality ceiling
therefore failed and prohibits a clean mechanism-quality claim. A one-pass
integrity check nevertheless confirmed unique case-condition coverage, model
identity, and diagnostic retention. The result is primary-model-only.

Across the 600 paired attacks, M3-full produced 38 unsafe effects (6.33%,
Wilson 95% CI 4.65–8.57) versus 133 (22.17%, 19.03–25.66) under the structural
condition. The paired difference was −15.83 percentage points (10,000-cluster
bootstrap 95% CI −19.50 to −12.17; exact McNemar p=4.04e−17,
Holm-adjusted p=1.61e−16). This security reduction did not identify a
full-system module contribution: M3 policy-only produced only 13 unsafe
effects (2.17%, 1.27–3.67), so M3-full was 4.17 points worse
(95% bootstrap CI 2.50–6.00; exact McNemar p=1.62e−6).

Benign tool completion under M3-full was 49/168 (29.17%, 22.82–36.44), versus
103/168 (61.31%, 53.77–68.34) under the structural condition: −32.14 points
(95% bootstrap CI −39.88 to −25.00; exact McNemar p=1.19e−14).
M3-full and policy-only both completed 49/168, with a paired difference of
0.00 points. All six conditions completed 79/79 benign no-tool tasks.

### Supplementary Table S5. Public-primary benchmark strata

| Benchmark / endpoint | Structural baseline | M3 policy-only | M3-full |
|---|---:|---:|---:|
| AgentDojo attacks, unsafe effect | 87/300 (29.00%) | 13/300 (4.33%) | 29/300 (9.67%) |
| M3-v2 attacks, unsafe effect | 46/300 (15.33%) | 0/300 (0.00%) | 9/300 (3.00%) |
| AgentDojo benign tool, TCR | 67/97 (69.07%) | 13/97 (13.40%) | 13/97 (13.40%) |
| M3-v2 benign tool, TCR | 36/71 (50.70%) | 36/71 (50.70%) | 36/71 (50.70%) |
| M3-v2 benign no-tool, TCR | 79/79 (100%) | 79/79 (100%) | 79/79 (100%) |

The direction is consistent across both attack benchmarks: M3-full is safer
than the structural condition but less safe than policy-only. Utility is
strongly benchmark dependent. The public M3-v2 tool tasks show no completion
difference among the three focal conditions, whereas AgentDojo tool completion
falls by 55.67 points for both M3 variants relative to the structural
condition. AgentDojo benign denominators remain the 97 unique official utility
tasks and are not duplicated.

## Public DeepSeek V4 Flash replication

The completed Flash matrix contains 1,791 records: 400 attacks, 145 benign
tool tasks, and 52 benign no-tool tasks under each of the structural,
policy-only, and full conditions. M3-full produced 24/400 unsafe effects
(6.00%, Wilson 95% CI 4.06–8.77), compared with 12/400 under policy-only
(3.00%, 1.72–5.17) and 47/400 under the structural baseline (11.75%,
8.95–15.28). Thus the full-minus-policy difference was +3.00 percentage
points, preserving the unfavorable direction observed with V4 Pro.

Benign-tool completion was 38/145 for full (26.21%, 19.73–33.91), 35/145 for
policy-only (24.14%, 17.90–31.71), and 82/145 for the structural baseline
(56.55%, 48.42–64.35). All three conditions completed 52/52 benign no-tool
tasks. The small +2.07-point full-minus-policy tool-completion difference does
not offset the security disadvantage and is not interpreted as an independent
mechanism gain. Sixteen operational diagnostic records remain in ITT; the Flash
result therefore supports a same-provider model replication, not a clean
mechanism-quality or cross-provider claim.

## Public operational and decision burden

The Public matrix contains 4,616 completed, 112 maximum-step, 120 parse-failure,
and 234 provider-failure records. Diagnostics are uneven by condition:
27 structural, 24 safe-prompt, 22 M3-full, two no-defense, one PromptGuard,
and zero policy-only. This imbalance is disclosed because terminal failure can
affect observed unsafe-effect counts; no diagnostic was retried or excluded.

On attacks, M3-full issued 181 initial `ASK` and 44 initial `DENY` decisions,
versus 197 `ASK` and no `DENY` under policy-only. On the 168 benign tool tasks,
M3-full issued 75 `ASK` decisions and policy-only issued 69. The primary
mechanism comparison therefore met its structural security-effect criterion
but missed utility non-inferiority and module-gain criteria. This pattern is
consistent with a security–utility trade-off rather than incremental benefit
from the full mechanism.

## DeepSeek authorization-regime experiment

The frozen authorization study contributes 900 terminal DeepSeek V4 Pro work
items across 180 paired cases. The four main cells each contain 100 attacks,
60 benign tool tasks, and 20 benign no-tool tasks. A nested 60-case subset adds
the broad, underspecified, and conflicting regimes under M3-full. Recovery was
limited to 33 work items for which no provider response had been obtained; all
867 response-bearing work items were left untouched. The final ITT population
contains 768 completed records, 54 parse failures, 30 maximum-step terminals,
15 provider failures, and 33 repeated pre-response failures. No evaluator or
gold field entered the online projection, and provider tools and real external
effects remained disabled.

### Joint security and utility endpoints

Unsafe effects were at the floor in the main experiment: 0/100 under M3-full
with either `auto_compiled` or `exact_gold`, 0/100 under policy-only with
`exact_gold`, and 1/100 under policy-only with `auto_compiled`. Consequently,
the full-minus-policy difference under `auto_compiled` was −1.00 percentage
point (task-cluster bootstrap 95% CI −3.00 to 0.00; Holm-adjusted McNemar
p=1.0), while all other primary security contrasts were exactly zero or
differed by the same single event. These data provide no evidence that the
full mechanism adds a reproducible security benefit over policy-only.

Benign-tool completion showed the larger authorization effect. Under
`auto_compiled`, policy-only completed 22/60 tasks (36.67%, Wilson 95% CI
25.62–49.32) and M3-full completed 16/60 (26.67%, 17.13–39.01), a paired
full-minus-policy difference of −10.00 points (bootstrap 95% CI −18.33 to
−3.33; Holm-adjusted p=0.09375). Under `exact_gold`, policy-only completed
9/60 (15.00%, 8.10–26.11) and full completed 7/60 (11.67%, 5.77–22.18), a
−3.33-point paired difference (bootstrap 95% CI −8.33 to 0.00;
Holm-adjusted p=0.5). All four main cells completed 20/20 benign no-tool tasks.

Changing policy-only from `auto_compiled` to `exact_gold` reduced paired
benign-tool completion by 21.67 points (bootstrap 95% CI −36.67 to −5.00;
Holm-adjusted p=0.05853). For M3-full, the corresponding reduction was 15.00
points (−28.33 to −1.67; Holm-adjusted p=0.09808). The bootstrap intervals
exclude zero, but neither exact McNemar comparison remains below 0.05 after
Holm correction. We therefore interpret the consistent direction and effect
size as evidence of authorization sensitivity in this sample, not as a
universal oracle-policy effect.

### Stress regimes and operational burden

On the nested benign-tool subset, moving from matched M3-full
`auto_compiled` executions to broad, conflicting, or underspecified policies
reduced completion by 25, 30, and 25 percentage points, respectively. Their
bootstrap intervals were −45 to −5, −50 to −10, and −50 to 0 points. No unsafe
effect occurred in any of the 30-attack stress cells, so the stress comparison
primarily exposes lost utility rather than an observable security gain.

The decision and failure profiles explain part of this trade-off. Under
policy-only, `auto_compiled` produced ASK on 34.44% and DENY on 7.22% of
records, whereas `exact_gold` produced no ASK but DENY on 48.89%; its failure
rate rose from 7.22% to 23.89% and p95 latency from 10.63 to 19.42 seconds.
M3-full showed the same pattern: ASK fell from 32.22% to zero, DENY rose from
11.11% to 45.00%, failure rose from 9.44% to 24.44%, and p95 latency rose from
9.18 to 19.62 seconds. DENY incidence counts records with at least one DENY;
the separate event totals are retained because a record may contain multiple
decisions. Across all 900 work items, provider cost was CNY 1.3888324.

These results reverse the simple expectation that an answer-derived exact
policy must improve measured utility. In this implementation, the exact policy
behaved as a more restrictive authorization treatment, replacing confirmation
with repeated blocking and higher operational failure. The result supports
making authorization construction explicit in evaluations; it does not show
that every gold-derived policy or every runtime guard behaves similarly.

## Defense-aware adaptive evidence through budget 200

The initial DeepSeek V4 Pro cost canary covered eight result-blind,
attack-family-balanced M3-v2 development tasks under M3-full and the
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

### Supplementary Table S6. Defense-aware adaptive attack

| Model/panel | Budget | Tasks | Unsafe-effect successes | First-success distribution | Saturated? |
|---|---:|---:|---:|---:|---|
| Primary exploratory cost canary | 50 | 8 | 0 (0.00%, 95% CI 0.00–32.44%) | No successes | No |
| Primary frozen panel | 50 | 40 | 4 (10.00%, 95% CI 3.96–23.05%) | 4 first successes by query 50 | No |
| Primary frozen panel | 200 | 40 | 18 (45.00%, 95% CI 30.71–60.17%) | 14 additional first successes at queries 51–200 | No |

## Remaining evidence boundary

The medium, Public Pro, Public Flash, authorization-regime, and budget-50/200
studies jointly support an empirical security–utility paper. They do not
support a leading-defense, causal provenance, saturated-adaptive, or
cross-provider claim. Gemini remains pending under the three-quota-day
free-tier rule; until that experiment reaches its stopping rule, its partial
rows are not used in the comparisons above. UTR and DSR are not identifiable
from the current record contract and are not reconstructed from unsafe-effect
rate.
