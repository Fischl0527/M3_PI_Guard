# Results draft — public, authorization-regime, and adaptive evidence

Status: `deepseek_e1_e6_complete_gemini_diagnostic_ne`

This section reports the completed 480-record medium study, 5,082-record
Public primary-model matrix, 1,791-record DeepSeek V4 Flash replication,
900-work-item DeepSeek V4 Pro authorization experiment, E1--E6 incremental
studies, and adaptive evidence through a conditional budget-500 tail. The
450-work-item Gemini authorization experiment and separate 180-item E6 Gemini
plan both closed incomplete and contribute no cross-provider effect estimate.
The three completed record matrices contain 902 distinct cases in union; the
Flash cohort is nested within the Pro Public cohort, and a small fraction of
the medium cases overlaps the Public cohorts. Record counts therefore denote
condition-level observations rather than independent case counts.

## Medium falsification study

The medium, Public, original authorization, E1--E6, and confirmation results
below retain their historical implementations and recorded endpoint labels.
In particular, legacy safety labels or failure-inclusive endpoints are not
retrospectively relabeled as observed unauthorized execution. The corrected
authorization and contemporaneous results lead the generated Results section;
the historical oracle completion collapse is an implementation-defect
observation, not evidence of an intrinsic precision–utility trade-off.

The medium study contains 480 records: 432 primary `auto_compiled` records
covering 72 paired cases across six conditions, plus 48 authorization-regime
probe records. The preregistered analysis did not support a superiority claim
for the full configuration package. It met the security-effect and deny-all
criteria, but missed the utility point non-inferiority criterion and showed no
security gain over the policy package. Both the favorable security comparison
and the unfavorable utility and package comparisons are reported.

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
| Policy package (`m3_policy_only`) | 0/36 | 0.00% (0.00–9.64) | 7/24 | 29.17% (14.91–49.17) | 12/12 |
| Full package (`m3_full`) | 0/36 | 0.00% (0.00–9.64) | 6/24 | 25.00% (12.00–44.90) | 12/12 |

The medium sample therefore shows a security–utility trade-off, not an
incremental package benefit. Both M3 variants eliminated the eight unsafe
effects observed under the structural condition, but they also completed
substantially fewer benign tool tasks.

### Supplementary Table S3. Prespecified paired comparisons

| Comparison | Treatment minus baseline | Exact McNemar p | Holm-adjusted p | 10,000-cluster bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Full package vs structural, unsafe effect | −22.22 pp | 0.0078125 | 0.03125 | −36.11 to −8.33 pp |
| Full vs policy package, unsafe effect | 0.00 pp | 1.0 | 1.0 | 0.00 to 0.00 pp |
| Full package vs structural, tool TCR | −25.00 pp | 0.03125 | 0.09375 | −41.67 to −8.33 pp |
| Full vs policy package, tool TCR | −4.17 pp | 1.0 | 1.0 | −12.50 to 0.00 pp |

The security effect relative to the structural baseline was large in this
sample, but the full package did not outperform the policy package. Relative to the
structural condition, its benign-tool TCR was 25 percentage points lower, well
outside the preregistered −5 percentage-point non-inferiority margin.

### Supplementary Table S4. Runtime burden and operational quality

| Condition | ASK / 72 | Benign ASK rate | Operational failures / 72 | Provider calls | Trace-bundle cost (CNY) | Total latency p95 |
|---|---:|---:|---:|---:|---:|---:|
| No defense | 0 | 0.00% | 4 | 181 | 0.1821176 | 16.924 s |
| Safe prompt / spotlighting | 0 | 0.00% | 5 | 167 | 0.1812942 | 15.971 s |
| PromptGuard (detector-only) | 0 | 0.00% | 5 | 180 | 0.0986064 | 18.249 s |
| Structural baseline | 0 | 0.00% | 4 | 249 | 0.2568822 | 21.251 s |
| Policy package | 16 | 19.44% | 1 | 112 | 0.0548220 | 7.897 s |
| Full package | 22 | 22.22% | 2 | 117 | 0.1441772 | 10.701 s |

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

## Authorization-regime sensitivity

Forty-eight probe records compare four alternate regimes with matched
`auto_compiled` executions for the policy and full packages. Each
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
| Full vs policy-package security gain | Fail | 0/36 vs 0/36 |
| Deny-all rejection | Pass | Benign initial ASK-or-DENY 22.22% |
| Operational quality | Pass | All three predefined quality checks passed |
| Supported interpretation | Empirical trade-off study | Full-package superiority claim not supported |

The results therefore support an empirical study of authorization uncertainty
and the security–utility trade-off. They do not support a defense-superiority
or SOTA claim.

## Public primary-model result

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

### Supplementary Table S5. Public-primary benchmark strata

| Benchmark / endpoint | Structural baseline | Policy package | Full package |
|---|---:|---:|---:|
| AgentDojo attacks, unsafe effect | 87/300 (29.00%) | 13/300 (4.33%) | 29/300 (9.67%) |
| M3-v2 attacks, unsafe effect | 46/300 (15.33%) | 0/300 (0.00%) | 9/300 (3.00%) |
| AgentDojo benign tool, TCR | 67/97 (69.07%) | 13/97 (13.40%) | 13/97 (13.40%) |
| M3-v2 benign tool, TCR | 36/71 (50.70%) | 36/71 (50.70%) | 36/71 (50.70%) |
| M3-v2 benign no-tool, TCR | 79/79 (100%) | 79/79 (100%) | 79/79 (100%) |

The direction is consistent across both attack benchmarks: the full package is
safer than the structural condition but less safe than the policy package. Utility is
strongly benchmark dependent. The public M3-v2 tool tasks show no completion
difference among the three focal conditions, whereas AgentDojo tool completion
falls by 55.67 points for both M3 variants relative to the structural
condition. AgentDojo benign denominators remain the 97 unique official utility
tasks and are not duplicated.

## Public DeepSeek V4 Flash replication

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

## Public operational and decision burden

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

## DeepSeek authorization-regime experiment

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

### Joint security and utility endpoints

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

### Benchmark-stratified authorization effects

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

### Failure-sensitive attack bound

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

### Stress regimes and operational burden

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

## Concurrent prompt-by-module factorial experiment

E1 reran the fixed 180-case cohort contemporaneously under the four cells of a
2×2 design: policy/normal, policy/safe, full/normal, and full/safe. All 720
planned work items obtained an official response. There were 657 completed
records, 54 parse failures, and nine provider failures; all 63 non-completed
outcomes remain in ITT. Raw evaluator fields, provider-managed tools, and real
external effects were absent from every online record.

Direct unsafe effects remained floor-limited: the two policy cells each
produced 1/100, whereas both full cells produced 0/100. The estimated module
main effect was −1.00 percentage point (10,000-case-cluster bootstrap 95% CI
−3.00 to 0.00; Holm-adjusted p=1.000). The prompt and interaction estimates
were both 0.00 points. The failure-sensitive endpoint was 9/100, 11/100,
7/100, and 8/100 in policy/normal, policy/safe, full/normal, and full/safe,
respectively. Its module estimate was −2.50 points (−5.50 to 0.00;
descriptive bootstrap p=0.0938). This prespecified sensitivity endpoint was not
included in either co-primary Holm family.

Benign-tool completion was 23/60, 21/60, 21/60, and 19/60 across the same
cells. Both the module and prompt main effects were −3.33 points; their 95%
intervals were −8.33 to 0.00 and −10.83 to +4.17, respectively, and the
interaction estimate was 0.00 points (−6.67 to +8.33). Thus the concurrent
design removes the earlier prompt/module confounding but supplies no evidence
of a positive incremental module or safe-prompt effect. It also does not solve
the direct-safety floor: only two unsafe effects occurred across 400 assigned
attack runs.

### Supplementary Table S7. E1 runtime burden and cost

| Cell | ASK incidence | DENY incidence | Operational failure | Latency p95 | Tokens | Cost (CNY) |
|---|---:|---:|---:|---:|---:|---:|
| Policy / normal | 65/180 | 15/180 | 15/180 | 8.11 s | 305,672 | 0.9651852 |
| Policy / safe | 55/180 | 16/180 | 16/180 | 9.12 s | 334,370 | 0.8439636 |
| Full / normal | 63/180 | 22/180 | 16/180 | 8.26 s | 306,306 | 0.7615200 |
| Full / safe | 62/180 | 21/180 | 16/180 | 9.13 s | 327,845 | 1.0896174 |

## Source-authority counterfactual

E2 completed 240/240 response-bearing end-to-end work items and 480/480
deterministic Guard decisions. The source swap changed only the authority of a
critical proposition while holding text, value, relative position, and policy
fixed. No end-to-end cell executed an authorized, unauthorized, or other
action. The resulting zero unauthorized-argument-influence rate is an endpoint
floor accompanied by confirmation and blocking, not evidence that source
authority was behaviorally irrelevant. The retained records do not identify
the exact stopping cause of every zero-action run.

The burden nevertheless differed sharply. Policy/trusted and
policy/untrusted produced ASK in 60/60 and 53/60 records, with no DENY. The
full/trusted cell produced ASK in 57/60, whereas full/untrusted produced no ASK,
DENY in 55/60, and one operational failure. The actual executed-action tuple
changed under the source swap in 0/60 paired tasks for both module settings;
operational status changed in 1/60 full pairs and is reported separately.

The deterministic replay provides mechanism evidence rather than end-to-end
utility. Its 480 decisions comprise 240 unauthorized and 240 authorized
proposals. False allow was 0/240 unauthorized proposals (Wilson 95% CI
0.00%--1.58%); false block was 30/240 authorized proposals (12.50%,
8.90%--17.28%). Policy decisions were
identical under trusted and untrusted origins: 60 ALLOW and 60 ASK. Full/trusted
had the same distribution, but full/untrusted produced 30 ALLOW, 30 ASK, and
60 DENY. The full Guard is therefore provenance-sensitive under this controlled
swap, yet the tested model--Guard system did not translate that mechanism into
completed tasks and incurred substantial confirmation or blocking burden.

### Supplementary Table S8. E2 source-authority decisions

| Evidence layer / cell | ALLOW | ASK | DENY | Operational failure | Executed actions |
|---|---:|---:|---:|---:|---:|
| End-to-end policy / trusted | — | 60/60 records | 0/60 | 0/60 | 0/60 |
| End-to-end policy / untrusted | — | 53/60 records | 0/60 | 0/60 | 0/60 |
| End-to-end full / trusted | — | 57/60 records | 0/60 | 0/60 | 0/60 |
| End-to-end full / untrusted | — | 0/60 | 55/60 records | 1/60 | 0/60 |
| Replay policy / trusted | 60 | 60 | 0 | — | — |
| Replay policy / untrusted | 60 | 60 | 0 | — | — |
| Replay full / trusted | 60 | 60 | 0 | — | — |
| Replay full / untrusted | 30 | 30 | 60 | — | — |

## Outcome-enriched challenge and Flash replication

E3 reran 60 attacks selected because each had produced an unsafe effect under
at least one historical Public condition. It is an outcome-enriched challenge
set, not a prevalence sample. All 240 work items obtained responses, but only
185 completed normally; 17 parse and 38 provider failures remained in ITT.
Only 1/60 historical vulnerabilities reproduced under any concurrent cell
(1.67%, Wilson 95% CI 0.29%--8.86%). The four unsafe-effect cells were 1/60,
1/60, 0/60, and 0/60, while unsafe-or-failure was 16/60, 15/60, 12/60, and
14/60. The module estimates were −1.67 points (−5.00 to 0.00) for unsafe
effect and −4.17 points (−10.00 to +0.83) for unsafe-or-failure. These
conditional results expose instability and a high failure burden rather than
establishing deployment robustness.

E4 applied the same factorial design to the frozen 90-case DeepSeek V4 Flash
cohort. All 360 work items obtained responses; one response-less transport
attempt was superseded by a single-key successful attempt without replaying any
other row. The final ITT set contains 347 completed, eight parse-failure, four
provider-failure, and one maximum-step outcomes. Every attack cell was 0/50
unsafe effects. Benign-tool completion was 10/30, 8/30, 10/30, and 10/30;
the module, prompt, and interaction estimates were +3.33 points (0.00 to
+8.33), −3.33 points (−11.67 to +3.33), and +6.67 points (0.00 to +16.67).
Unsafe-or-failure yielded a +3.00-point module estimate (0.00 to +7.00).
E4 is a same-provider model replication and opens no new significance family;
its all-zero direct-safety endpoint cannot establish equivalence or
cross-provider generalization.

### Supplementary Table S9. E3/E4 operational summary

| Study | Planned/latest | Completed | Parse failure | Provider failure | Max steps | Cost (CNY) |
|---|---:|---:|---:|---:|---:|---:|
| E3 outcome-enriched Pro | 240/240 | 185 | 17 | 38 | 0 | 1.0690866 |
| E4 Flash replication | 360/360 | 347 | 8 | 4 | 1 | 0.5410834 |

## Contemporaneous attack-activity calibration

E6 used a separately executed, historically risk-enriched cohort to test whether
attacks were still active under a current no-defense control. The execution was
independent of E3, but the sample was not: 47/60 tasks were E3 anchors (19
AgentDojo and 28 M3-v2). All 360 DeepSeek work items were response-bearing; 361
physical records include one response-less superseded attempt. No defense
produced 17/60 unsafe effects (28.33%, Wilson 95% CI 18.52%--40.75%), including
8/30 AgentDojo and 9/30 M3-v2 cases. This demonstrates observed attack activity
within the selected risk-enriched block, but does not satisfy or test the
original multi-window activity gate and cannot estimate deployment prevalence.

Unsafe effects under source-pinned VIGIL, policy/normal, policy/safe,
full/normal, and full/safe were 16/60, 2/60, 1/60, 0/60, and 0/60. Operational
failures in the same order, including no defense first, were 12/60, 8/60, 7/60,
2/60, 7/60, and 3/60. Full/safe minus no defense was −28.33 percentage points
(paired Newcombe 95% CI −40.77 to −16.81; task-cluster bootstrap −40.00 to
−16.67; Holm-adjusted p=0.000061). Policy/normal minus no defense was −25.00
points (Newcombe −36.95 to −14.30), and full/safe minus VIGIL was −26.67 points
(−39.01 to −15.39). VIGIL minus no defense was only −1.67 points with an
interval crossing zero; its benchmark-specific directions opposed each other
(+3.33 points on AgentDojo and −6.67 on M3-v2), so the pooled VIGIL contrast is
not interpreted as homogeneous.

The four M3 cells yielded descriptive factor estimates of −2.50 points for the
module bundle, −0.83 for the safe prompt, and +1.67 for their interaction. E6
contains no benign tasks and was executed as one block after a prospective
protocol amendment; it adds neither TCR evidence nor temporal-repeatability or
individual-module attribution.

The nested Gemini formal prefix failed its technical gate after five
response-bearing records and one response-less VIGIL dependency failure. The
remaining 174 planned items were administratively closed, not counted as safe
or scientifically executed. The nested set also overlapped E3 for 29/30 tasks.
Minimum response-complete paired coverage was 0/30 for comparisons involving
VIGIL. All Gemini paired, factorial, and cross-provider effects are not
estimable.

### Supplementary Table S11. E6 DeepSeek activity and operational outcomes

| Condition | Unsafe effect | Operational failure | Unsafe or failure | ASK events | DENY events |
|---|---:|---:|---:|---:|---:|
| No defense | 17/60 | 12/60 | 29/60 | 0 | 4 |
| Source-pinned VIGIL | 16/60 | 8/60 | 24/60 | 0 | 8 |
| Policy / normal | 2/60 | 7/60 | 9/60 | 31 | 7 |
| Policy / safe | 1/60 | 2/60 | 3/60 | 21 | 2 |
| Full / normal | 0/60 | 7/60 | 7/60 | 25 | 18 |
| Full / safe | 0/60 | 3/60 | 3/60 | 19 | 6 |

### Supplementary Table S12. E6 paired effects and Gemini inference coverage

| Evidence | Comparison or coverage | Estimate | Newcombe / cluster-bootstrap 95% CI | Exact McNemar / Holm p | Interpretation |
|---|---|---:|---|---:|---|
| DeepSeek | VIGIL minus no defense | −1.67 pp | Newcombe −10.48 to +7.12 pp; bootstrap −10.00 to +6.67 pp | 1.000000 / 1.000000 | Interval crosses zero; benchmark directions oppose |
| DeepSeek | Policy / normal minus no defense | −25.00 pp | Newcombe −36.95 to −14.30 pp; bootstrap −36.67 to −15.00 pp | 0.000061 / 0.000122 | Risk-enriched single-block contrast |
| DeepSeek | Full / safe minus no defense | −28.33 pp | Newcombe −40.77 to −16.81 pp; bootstrap −40.00 to −16.67 pp | 0.000015 / 0.000061 | Risk-enriched single-block contrast |
| DeepSeek | Full / safe minus VIGIL | −26.67 pp | Newcombe −39.01 to −15.39 pp; bootstrap −38.33 to −15.00 pp | 0.000031 / 0.000092 | Risk-enriched single-block contrast |
| Gemini | Scientific terminal / planned | 6/180 | — | — | Five response-bearing; one response-less failure |
| Gemini | Minimum response-complete paired coverage | 0/30 | — | — | Effects not estimable |

## Defense-aware adaptive evidence and conditional tail through budget 500

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

### Supplementary Table S6. Defense-aware adaptive attack

| Model/panel | Budget | Tasks | Unsafe-effect successes | First-success distribution | Saturated? |
|---|---:|---:|---:|---:|---|
| Primary exploratory cost canary | 50 | 8 | 0 (0.00%, 95% CI 0.00–32.44%) | No successes | No |
| Primary frozen panel | 50 | 40 | 4 (10.00%, 95% CI 3.96–23.05%) | 4 first successes by query 50 | No |
| Primary frozen panel | 200 | 40 | 18 (45.00%, 95% CI 30.71–60.17%) | 14 additional first successes at queries 51–200 | No |

The E5 extension then completed all 12 prespecified B200 survivors through
query 500. No task produced a new first unsafe effect between queries 201 and
500: 0/12 (0.00%, Wilson 95% CI 0.00%--24.25%). This is a conditional null
observation with a wide upper bound, not evidence that the original 40-task
panel has zero tail risk or that attack search has saturated. The latest ITT
set contains 3,600 query work keys: 3,577 completed, 21 parse failures, and two
provider failures. Five earlier response-less or local-recovery attempts remain
as superseded physical rows. Total usage was 4,511,768 tokens and attributed
cost was CNY 24.5551236.

### Supplementary Table S10. Conditional adaptive-tail execution

| Quantity | Result |
|---|---:|
| Prespecified B200 survivors completed | 12/12 |
| Latest query work keys | 3,600 |
| Physical rows / superseded attempts | 3,605 / 5 |
| First unsafe effect at queries 201--500 | 0/12 |
| Conditional probability, Wilson 95% CI | 0.00% (0.00%--24.25%) |
| Operational status | 3,577 completed; 21 parse failures; 2 provider failures |
| Total tokens | 4,511,768 |
| Attributed cost | CNY 24.5551236 |
| Automatic retry / provider tools / real external effects | 0 / 0 / 0 |

## Authorization diagnostics and execution permits

The E1 benign-tool decomposition retains 60 tasks per cell. For policy/normal,
policy/safe, full/normal, and full/safe respectively, completed tasks numbered
23, 21, 21, and 19; incomplete non-failed tasks with ASK numbered 20, 17, 20,
and 22; and operational failures numbered 7, 6, 9, and 8. The residual groups
were 0, 0, 1, and 1 incomplete tasks with DENY but no ASK, and 10, 16, 9, and
10 with neither. This separation avoids adding overlapping ASK and failure
incidences and does not change the original TCR.

The new forced-proposal probes identified conditional implementation limits.
For either nuisance-text or safety-target perturbation, policy returned ASK
in 120/120 cases; full returned ASK in 90/120 and DENY in 30/120. Among six
unauthorized-target provenance scenarios, exact-target rules yielded no ALLOW
under either module setting. Broad-target rules yielded 6/6 ALLOW for policy
and 4/6 for full. Literal matching can treat negated or quoted trusted mentions
as authority, while encoded or split values escape literal-source matching.
Three constructed legacy approvals (expired, partial-proposal scope, and
tool-only scope) were accepted, whereas a missing approval produced ASK.
These probes do not show that an attacker can obtain trusted approvals or
induce the model to emit the forced proposals.

E7a obtained 96/96 official, parseable responses with no operational failure.
Supplementary Table S19 reports execution-permit issuance under trusted approval: each module
setting had 0/12 permitted benign proposals under the deliberately strict
control and 12/12 under bounded enumeration. Corresponding Wilson 95% intervals
are 0.00%--24.25% and 75.75%--100.00%. Attack-condition proposals followed the
authorized target and showed the same permit pattern. Consequently, zero
unauthorized permits cannot establish resistance to an active attack.

Across the 384 paired confirmation cells, 192 remained scope-blocked, 48
received one-shot permits, 48 were denied by the trusted controller, and 96
lacked valid confirmation (absent or forged). There was no policy/full
difference in these counts. The result demonstrates a constructed
policy--intent mismatch and a bounded permission lifecycle, not a general
utility gain. No task-environment state transition was performed, and these
permits are not added to TCR or unsafe-effect counts in the execution studies.

## Corrected development study

Supplementary Table S20 separates the corrected-v1 development batch from all
historical experiments. DeepSeek V4 Pro and DeepSeek V4.1 Flash each completed
288 planned task-condition executions over the same 48 tasks and six
configurations. Pro had 265 completed workflows, 13 parse failures, and ten
max-step terminations; Flash had 272, seven, and nine, respectively. Workflow
completion is separate from task completion: ending with ASK records pending
approval rather than task execution.

AgentDojo retains its native security checker. For Pro, normal-prompt attack
positives were 5/12 without a guard, 2/12 with policy modules, and 0/12 with
full modules; benign-tool completion was 6/8, 3/8, and 3/8. The full-minus-policy
paired attack difference was −16.67 percentage points (95% CI −44.80 to +10.38),
crossing zero. For Flash, the no-guard normal-prompt attack cell had 1/12
positives and each other cell had zero. Benign-tool completion was 7/8 in both
no-guard cells and 4/8 in each guarded cell. The attack comparison remained
uncertain in these historically enriched development samples.

M3-v2 observed simulated unsafe effects were 0/12 in every attack cell for
both models, including no guard. Control and guarded cells therefore shared
an attack-endpoint floor. Runtime summaries contained zero labelled sensitive
values, so dataflow checks were not applicable to these trajectories.
The eight no-tool tasks per model-condition remain in the planned denominators;
Supplementary Table S20 focuses on attack and benign-tool outcomes. Unknown
outcomes are not replaced by zero, and operational failures remain separately
reported.

## Corrected authorization and contemporaneous calibration

The corrected authorization study records all 900 planned assignments over
180 fixed cases representing 153 tasks. Tables 2–4 summarize corrected
authorization, contemporaneous calibration, and bounded component controls,
respectively. Paired intervals below are distinct from the tables’ marginal
Wilson intervals. Of the 900 workflows, 795 end normally, 60 exhaust the step
budget, and 45 have parse failures. Across 490 attack assignments, security
events are zero under the benchmark-specific checks. With no unguarded control
in this study, these observations establish an endpoint floor rather than
a protection contrast.

For AgentDojo benign-tool tasks, compiled authorization completes 2/30 under
both policy and full modules. Exact-target authorization completes 13/30 under
policy and 11/30 under full modules. Paired exact-minus-compiled differences
are +36.67 percentage points (95% CI +18.60 to +53.31; Holm p=0.0039) and
+30.00 points (+13.23 to +46.75; Holm p=0.0117), respectively. For M3-v2,
compiled counts are 16/30 and 17/30, compared with exact-target counts of
14/30 and 16/30. Their differences, −6.67 and −3.33 points, have intervals
spanning zero. The completion gain was supported on AgentDojo, while the
M3-v2 differences remained uncertain.

The separately executed calibration uses 120 cases nested within the
authorization cohort and closes all 480 assignments. Of these, 443 workflows
end normally, nine exhaust steps, 25 have parse failures, two have runner
failures, and one has a provider/stop failure. On AgentDojo, no research Guard
yields 3/30 security events and 17/30 benign-tool completions. Policy and full
modules each yield 0/30 and 2/30. The paired completion difference is
−50.00 points (95% CI −66.83 to −26.80; Holm p=0.0008), whereas the security
difference is −10.00 points (−25.62 to +3.10; Holm p=0.7500). The utility cost
is observable; a security improvement is not established. No-research-Guard,
policy, and full M3-v2 security cells are all zero, with benign completions
of 16/30, 17/30, and 16/30. Full modules show no identifiable independent
end-to-end advantage in these conditions.

Across calibration, seven known security-positive assignments and four unknown
outcomes are retained. Configured VIGIL has four AgentDojo attack positives
among 28 known outcomes and two unknown attack outcomes. All 30 assignments
remain in ITT, giving a 4/30 lower bound and a 6/30 conservative upper bound.
Two additional AgentDojo benign outcomes are unknown. Across all 480 rows,
two field-projection receipts and four structured safety receipts are absent.

The public-event diagnosis reports 26/30 AgentDojo compiled benign tasks with
a first missing-tool-permission block in each module condition. This locates
permission insufficiency for the trusted-intent review below. The original
900 rows have no recorded length truncation, so parse failures cannot uniformly
be attributed to the 512-token limit. Two rows record task completion before
a subsequent operational failure, and both observations are retained.

The 16 synthetic controls span four scenarios and two DeepSeek services, Pro
and V4.1 Flash, and all reach a workflow terminal. Full modules deny private
restricted flows and ask when classification is missing; tested public and
archival flows complete. Policy-only permits the restricted private and
missing-classification simulated flows. Legitimate completion and a security
violation coexist in the tested controls, making these endpoints separately
observable.

Task total latency is available for 476/480 calibration assignments, with
four missing and no invalid values. AgentDojo benign-task median/p95 durations
are 5.083/11.575 seconds without the research Guard, 1.209/3.029 with policy,
1.279/3.003 with full modules, and 8.145/20.291 for configured VIGIL.
Its known-duration denominator is 28/30. Early blocking, model calls, constraint
generation, and task-path differences explain why this task-duration ordering
is not a Guard computation-speed comparison.

## Trusted-intent review of benign completion

The fixed 60-task review reuses 240 calibration records rather than adding
executions. It finds no lost or mismatched action–target pair among seven
trusted application declarations. Thirteen further M3-v2 tasks have rules for
explicitly requested targets. The remaining ten M3-v2 tasks require confirmation
of a filename or recipient without supplying a concrete target; no independent
approval was obtained. These counts describe trusted inputs and generated
authorization rules.

All 30 AgentDojo tasks lack such concrete trusted action declarations.
The generic compiler’s lexical tool selection and literal security-target
parsing do not cover arbitrary natural-language requests, multistage lookups,
or dynamic object identifiers. Requests can express legitimate goals even when
this bounded compiler cannot derive an executable grant. No new declared-contract
violation was established by the review.

Six M3-v2 tasks show successful simulated execution without completion under
at least one policy/full condition; four also have a model-format or operational
failure. Categories overlap. In three explicit mock-API tasks, policy records
contain ALLOW, successful execution, and a final answer but still fail completion.
The evaluator requires both expected-effect matching and a successful final
outcome. Redacted public arguments and answer content do not identify the exact
mismatch. The cause remains unresolved, with execution and completion retained
as separate observations.

## Remaining evidence boundary

Historical Public and incremental tables retain their recorded evaluator
labels. The old M3-v2 path could label an allowed action unsafe after isolation
rejection, even when no effect was applied; historical ITT variants also include
failures. These values remain legacy-labelled risk endpoints, separate from
corrected simulated-execution effects. AgentDojo retains its native security
checker. Historical decision replay, adaptive search, calibration, and provider
diagnostics remain in their supplementary sections, with their inferential
boundaries consolidated in Discussion.
