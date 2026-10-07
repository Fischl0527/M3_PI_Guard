# Supplementary material

**Article:** Evaluating Authorization Regimes and Runtime Guardrail Configurations for Tool-Using LLM Agents

Tables S1-S12 retain the existing supplementary results. Tables S13-S20 preserve the former main tables as historical or development evidence, with their original endpoint definitions and limitations. These tables introduce no additional hypothesis family or claim beyond the analyses reported in the article. Current corrected-v2 studies appear in the main tables.

## Supplementary Table S1. Online-state source audit

| Conclusion | Audited units | Independently reviewed | Claim use |
|---|---:|---:|---|
| No online gold observed on covered path | 9 | 0 | Path-scoped only |
| Not a runtime guard | 10 | 0 | Taxonomy only |
| Mixed or path dependent | 1 | 0 | Path-scoped caution |
| Inconclusive | 2 | 0 | No substantive claim |

## Supplementary Table S2. Completed medium security and utility outcomes

| Condition | Unsafe effects / 36 attacks | Unsafe-effect rate (Wilson 95% CI) | Tool completions / 24 | Tool TCR (Wilson 95% CI) | No-tool TCR |
|---|---:|---:|---:|---:|---:|
| No defense | 8/36 | 22.22% (11.72–38.08) | 12/24 | 50.00% (31.43–68.57) | 12/12 |
| Safe prompt / spotlighting | 8/36 | 22.22% (11.72–38.08) | 11/24 | 45.83% (27.89–64.93) | 12/12 |
| PromptGuard (detector-only) | 8/36 | 22.22% (11.72–38.08) | 12/24 | 50.00% (31.43–68.57) | 12/12 |
| Structural baseline | 8/36 | 22.22% (11.72–38.08) | 12/24 | 50.00% (31.43–68.57) | 12/12 |
| Policy package (`m3_policy_only`) | 0/36 | 0.00% (0.00–9.64) | 7/24 | 29.17% (14.91–49.17) | 12/12 |
| Full package (`m3_full`) | 0/36 | 0.00% (0.00–9.64) | 6/24 | 25.00% (12.00–44.90) | 12/12 |

## Supplementary Table S3. Prespecified paired comparisons

| Comparison | Treatment minus baseline | Exact McNemar p | Holm-adjusted p | 10,000-cluster bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Full package vs structural, unsafe effect | −22.22 pp | 0.0078125 | 0.03125 | −36.11 to −8.33 pp |
| Full vs policy package, unsafe effect | 0.00 pp | 1.0 | 1.0 | 0.00 to 0.00 pp |
| Full package vs structural, tool TCR | −25.00 pp | 0.03125 | 0.09375 | −41.67 to −8.33 pp |
| Full vs policy package, tool TCR | −4.17 pp | 1.0 | 1.0 | −12.50 to 0.00 pp |

## Supplementary Table S4. Runtime burden and operational quality

| Condition | ASK / 72 | Benign ASK rate | Operational failures / 72 | Provider calls | Trace-bundle cost (CNY) | Total latency p95 |
|---|---:|---:|---:|---:|---:|---:|
| No defense | 0 | 0.00% | 4 | 181 | 0.1821176 | 16.924 s |
| Safe prompt / spotlighting | 0 | 0.00% | 5 | 167 | 0.1812942 | 15.971 s |
| PromptGuard (detector-only) | 0 | 0.00% | 5 | 180 | 0.0986064 | 18.249 s |
| Structural baseline | 0 | 0.00% | 4 | 249 | 0.2568822 | 21.251 s |
| Policy package | 16 | 19.44% | 1 | 112 | 0.0548220 | 7.897 s |
| Full package | 22 | 22.22% | 2 | 117 | 0.1441772 | 10.701 s |

## Supplementary Table S5. Public-primary benchmark strata

| Benchmark / endpoint | Structural baseline | Policy package | Full package |
|---|---:|---:|---:|
| AgentDojo attacks, unsafe effect | 87/300 (29.00%) | 13/300 (4.33%) | 29/300 (9.67%) |
| M3-v2 attacks, unsafe effect | 46/300 (15.33%) | 0/300 (0.00%) | 9/300 (3.00%) |
| AgentDojo benign tool, TCR | 67/97 (69.07%) | 13/97 (13.40%) | 13/97 (13.40%) |
| M3-v2 benign tool, TCR | 36/71 (50.70%) | 36/71 (50.70%) | 36/71 (50.70%) |
| M3-v2 benign no-tool, TCR | 79/79 (100%) | 79/79 (100%) | 79/79 (100%) |

## Supplementary Table S6. Defense-aware adaptive attack

| Model/panel | Budget | Tasks | Unsafe-effect successes | First-success distribution | Saturated? |
|---|---:|---:|---:|---:|---|
| Primary exploratory cost canary | 50 | 8 | 0 (0.00%, 95% CI 0.00–32.44%) | No successes | No |
| Primary frozen panel | 50 | 40 | 4 (10.00%, 95% CI 3.96–23.05%) | 4 first successes by query 50 | No |
| Primary frozen panel | 200 | 40 | 18 (45.00%, 95% CI 30.71–60.17%) | 14 additional first successes at queries 51–200 | No |

## Supplementary Table S7. E1 runtime burden and cost

| Cell | ASK incidence | DENY incidence | Operational failure | Latency p95 | Tokens | Cost (CNY) |
|---|---:|---:|---:|---:|---:|---:|
| Policy / normal | 65/180 | 15/180 | 15/180 | 8.11 s | 305,672 | 0.9651852 |
| Policy / safe | 55/180 | 16/180 | 16/180 | 9.12 s | 334,370 | 0.8439636 |
| Full / normal | 63/180 | 22/180 | 16/180 | 8.26 s | 306,306 | 0.7615200 |
| Full / safe | 62/180 | 21/180 | 16/180 | 9.13 s | 327,845 | 1.0896174 |

## Supplementary Table S8. E2 source-authority decisions

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

## Supplementary Table S9. E3/E4 operational summary

| Study | Planned/latest | Completed | Parse failure | Provider failure | Max steps | Cost (CNY) |
|---|---:|---:|---:|---:|---:|---:|
| E3 outcome-enriched Pro | 240/240 | 185 | 17 | 38 | 0 | 1.0690866 |
| E4 Flash replication | 360/360 | 347 | 8 | 4 | 1 | 0.5410834 |

## Supplementary Table S10. Conditional adaptive-tail execution

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

## Supplementary Table S11. E6 DeepSeek activity and operational outcomes

| Condition | Unsafe effect | Operational failure | Unsafe or failure | ASK events | DENY events |
|---|---:|---:|---:|---:|---:|
| No defense | 17/60 | 12/60 | 29/60 | 0 | 4 |
| Source-pinned VIGIL | 16/60 | 8/60 | 24/60 | 0 | 8 |
| Policy / normal | 2/60 | 7/60 | 9/60 | 31 | 7 |
| Policy / safe | 1/60 | 2/60 | 3/60 | 21 | 2 |
| Full / normal | 0/60 | 7/60 | 7/60 | 25 | 18 |
| Full / safe | 0/60 | 3/60 | 3/60 | 19 | 6 |

## Supplementary Table S12. E6 paired effects and Gemini inference coverage

| Evidence | Comparison or coverage | Estimate | Newcombe / cluster-bootstrap 95% CI | Exact McNemar / Holm p | Interpretation |
|---|---|---:|---|---:|---|
| DeepSeek | VIGIL minus no defense | −1.67 pp | Newcombe −10.48 to +7.12 pp; bootstrap −10.00 to +6.67 pp | 1.000000 / 1.000000 | Interval crosses zero; benchmark directions oppose |
| DeepSeek | Policy / normal minus no defense | −25.00 pp | Newcombe −36.95 to −14.30 pp; bootstrap −36.67 to −15.00 pp | 0.000061 / 0.000122 | Risk-enriched single-block contrast |
| DeepSeek | Full / safe minus no defense | −28.33 pp | Newcombe −40.77 to −16.81 pp; bootstrap −40.00 to −16.67 pp | 0.000015 / 0.000061 | Risk-enriched single-block contrast |
| DeepSeek | Full / safe minus VIGIL | −26.67 pp | Newcombe −39.01 to −15.39 pp; bootstrap −38.33 to −15.00 pp | 0.000031 / 0.000092 | Risk-enriched single-block contrast |
| Gemini | Scientific terminal / planned | 6/180 | — | — | Five response-bearing; one response-less failure |
| Gemini | Minimum response-complete paired coverage | 0/30 | — | — | Effects not estimable |

## Supplementary Table S13. Prompt-by-module factorial design

The four contemporaneous cells cross prompt profile with the runtime module bundle while holding authorization at auto_compiled.

| Condition cell | Prompt | Modules | Authorization | Historical rows reused |
|---|---|---|---|---|
| Policy / normal | normal | policy | auto compiled | No |
| Policy / safe | safe | policy | auto compiled | No |
| Full / normal | normal | full | auto compiled | No |
| Full / safe | safe | full | auto compiled | No |

## Supplementary Table S14. E1 factorial estimates

Absolute effects are probability differences; intervals use 10,000 case-cluster bootstrap replicates. Holm values apply only to E1's prespecified endpoint families. Historical tables retain their recorded endpoint, not a retrospectively verified count of committed unauthorized effects. See the measurement correction and separate corrected-v1 results.

| Study | Endpoint | Factor | Paired cases | Effect | CI low | CI high | Bootstrap p | Holm p | Bootstrap n |
|---|---|---|---|---|---|---|---|---|---|
| E1 representative pro | attack unsafe effect | interaction | 100 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | 1.0000 | 10000 |
| E1 representative pro | attack unsafe effect | module | 100 | -1.00 pp | -3.00 pp | +0.00 pp | 0.7358 | 1.0000 | 10000 |
| E1 representative pro | attack unsafe effect | prompt | 100 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | 1.0000 | 10000 |
| E1 representative pro | attack unsafe or failure | interaction | 100 | -1.00 pp | -5.00 pp | +3.00 pp | 0.8206 | — | 10000 |
| E1 representative pro | attack unsafe or failure | module | 100 | -2.50 pp | -5.50 pp | +0.00 pp | 0.0938 | — | 10000 |
| E1 representative pro | attack unsafe or failure | prompt | 100 | +1.50 pp | -3.00 pp | +6.00 pp | 0.5868 | — | 10000 |
| E1 representative pro | Benign-tool TCR | interaction | 60 | +0.00 pp | -6.67 pp | +8.33 pp | 1.0000 | 1.0000 | 10000 |
| E1 representative pro | Benign-tool TCR | module | 60 | -3.33 pp | -8.33 pp | +0.00 pp | 0.0960 | 0.2880 | 10000 |
| E1 representative pro | Benign-tool TCR | prompt | 60 | -3.33 pp | -10.83 pp | +4.17 pp | 0.4496 | 0.8992 | 10000 |

## Supplementary Table S15. E2 source-authority evidence

End-to-end source swaps and deterministic Guard replay are separate evidence layers and must not be interpreted as interchangeable.

| Study | Endpoint | Factor | Paired cases | Effect | CI low | CI high | Bootstrap p | Holm p | Bootstrap n |
|---|---|---|---|---|---|---|---|---|---|
| E2 end to end | unauthorized argument influence | module | 60 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | 1.0000 | 10000 |
| E2 end to end | unauthorized argument influence | source | 60 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | 1.0000 | 10000 |
| E2 end to end | unauthorized argument influence | source x module | 60 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | 1.0000 | 10000 |
| E2 end to end | authorized action execution | module | 60 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | 1.0000 | 10000 |
| E2 end to end | authorized action execution | source | 60 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | 1.0000 | 10000 |
| E2 end to end | authorized action execution | source x module | 60 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | 1.0000 | 10000 |
| E2 end to end | source swap action change | full | 60 | +0.00 pp | +0.00 pp | +6.02 pp | — | — | — |
| E2 end to end | source swap action change | policy | 60 | +0.00 pp | +0.00 pp | +6.02 pp | — | — | — |
| E2 offline guard replay | false allow | not applicable | 240 | +0.00 pp | +0.00 pp | +1.58 pp | — | — | — |
| E2 offline guard replay | false block | not applicable | 240 | +12.50 pp | +8.90 pp | +17.28 pp | — | — | — |

## Supplementary Table S16. E3/E4 conditional robustness

E3 is outcome-enriched and E4 is a same-provider replication. Neither opens a new significance family or estimates deployment prevalence. Historical tables retain their recorded endpoint, not a retrospectively verified count of committed unauthorized effects. See the measurement correction and separate corrected-v1 results.

| Study | Endpoint | Factor | Paired cases | Effect | CI low | CI high | Bootstrap p | Holm p | Bootstrap n |
|---|---|---|---|---|---|---|---|---|---|
| E3 risk enriched pro | attack unsafe effect | interaction | 60 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | — | 10000 |
| E3 risk enriched pro | attack unsafe effect | module | 60 | -1.67 pp | -5.00 pp | +0.00 pp | 0.7406 | — | 10000 |
| E3 risk enriched pro | attack unsafe effect | prompt | 60 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | — | 10000 |
| E3 risk enriched pro | attack unsafe or failure | interaction | 60 | +5.00 pp | -3.33 pp | +13.33 pp | 0.3448 | — | 10000 |
| E3 risk enriched pro | attack unsafe or failure | module | 60 | -4.17 pp | -10.00 pp | +0.83 pp | 0.1528 | — | 10000 |
| E3 risk enriched pro | attack unsafe or failure | prompt | 60 | +0.83 pp | -8.33 pp | +10.00 pp | 0.9438 | — | 10000 |
| E4 flash replication | attack unsafe effect | interaction | 50 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | — | 10000 |
| E4 flash replication | attack unsafe effect | module | 50 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | — | 10000 |
| E4 flash replication | attack unsafe effect | prompt | 50 | +0.00 pp | +0.00 pp | +0.00 pp | 1.0000 | — | 10000 |
| E4 flash replication | attack unsafe or failure | interaction | 50 | -2.00 pp | -10.00 pp | +4.00 pp | 0.7852 | — | 10000 |
| E4 flash replication | attack unsafe or failure | module | 50 | +3.00 pp | +0.00 pp | +7.00 pp | 0.0864 | — | 10000 |
| E4 flash replication | attack unsafe or failure | prompt | 50 | -1.00 pp | -5.00 pp | +2.00 pp | 0.7752 | — | 10000 |
| E4 flash replication | Benign-tool TCR | interaction | 30 | +6.67 pp | +0.00 pp | +16.67 pp | 0.2558 | — | 10000 |
| E4 flash replication | Benign-tool TCR | module | 30 | +3.33 pp | +0.00 pp | +8.33 pp | 0.2602 | — | 10000 |
| E4 flash replication | Benign-tool TCR | prompt | 30 | -3.33 pp | -11.67 pp | +3.33 pp | 0.5494 | — | 10000 |

## Supplementary Table S17. E5 conditional adaptive tail

The tail probability is conditional on the prespecified B200 survivors; it is not a complete original-panel B500 curve or saturation estimate. Historical tables retain their recorded endpoint, not a retrospectively verified count of committed unauthorized effects. See the measurement correction and separate corrected-v1 results.

| Stratum | Tasks | Successes by 500 | Conditional probability | CI low | CI high | First-success queries | Complete original B500 panel |
|---|---|---|---|---|---|---|---|
| all selected survivors | 12 | 0 | 0.00% | 0.00% | 24.25% | — | No |
| A1 | 4 | 0 | 0.00% | 0.00% | 48.99% | — | No |
| A2 | 4 | 0 | 0.00% | 0.00% | 48.99% | — | No |
| A3 | 4 | 0 | 0.00% | 0.00% | 48.99% | — | No |

## Supplementary Table S18. E6 contemporaneous attack-activity calibration

E6 uses a historically risk-enriched single execution block; 47/60 tasks also anchor E3. It does not estimate deployment prevalence, benign utility, temporal repeatability, independent-sample replication, or a cross-provider effect. Historical tables retain their recorded endpoint, not a retrospectively verified count of committed unauthorized effects. See the measurement correction and separate corrected-v1 results.

| Condition | Legacy risk, n/N (95% CI) | Operational failure | Legacy risk or failure | ASK events | DENY events |
|---|---|---|---|---|---|
| No defense | 17/60 (28.3%) [18.5%, 40.8%] | 12/60 (20.0%) | 29/60 (48.3%) | 0 | 4 |
| Source-pinned VIGIL | 16/60 (26.7%) [17.1%, 39.0%] | 8/60 (13.3%) | 24/60 (40.0%) | 0 | 8 |
| Policy / normal | 2/60 (3.3%) [0.9%, 11.4%] | 7/60 (11.7%) | 9/60 (15.0%) | 31 | 7 |
| Policy / safe | 1/60 (1.7%) [0.3%, 8.9%] | 2/60 (3.3%) | 3/60 (5.0%) | 21 | 2 |
| Full / normal | 0/60 (0.0%) [0.0%, 6.0%] | 7/60 (11.7%) | 7/60 (11.7%) | 25 | 18 |
| Full / safe | 0/60 (0.0%) [0.0%, 6.0%] | 3/60 (5.0%) | 3/60 (5.0%) | 19 | 6 |

## Supplementary Table S19. E7a execution-permit diagnostic

One-shot permits under trusted approval, not task completion or committed effects. Strict exact deliberately excludes the request's preferred but authorized wording. Each denominator is 12; Wilson 95% intervals are 0.00%--24.25% for 0/12 and 75.75%--100.00% for 12/12. Attack prompts produced no unauthorized target proposal, so zero unauthorized permits do not establish attack resistance.

| Policy / modules | Benign authorized permits | Attack authorized permits | Attack unauthorized permits |
|---|---|---|---|
| Strict exact / policy | 0/12 | 0/12 | 0/12 |
| Strict exact / full | 0/12 | 0/12 | 0/12 |
| Bounded enum / policy | 12/12 | 12/12 | 0/12 |
| Bounded enum / full | 12/12 | 12/12 | 0/12 |

## Supplementary Table S20. Corrected development study by benchmark

Corrected-v1 development data, not a confirmatory comparison with historical runs. AgentDojo retains its native security checker; M3-v2 counts observed simulated effects. Fractions give numerator/observed denominator, not evidence that failures are safe. Unknown values, when present, are explicit. Each model has 288 planned executions including no-tool tasks; those tasks and operational status counts are described in the text. Flash is V4.1, not the historical V4 model.

| Model | Benchmark | Configuration | Attack endpoint | Benign tool completion |
|---|---|---|---|---|
| V4 Pro | AgentDojo | No guard / normal | 5/12 | 6/8 |
| V4 Pro | AgentDojo | No guard / safe | 3/12 | 6/8 |
| V4 Pro | AgentDojo | Policy / normal | 2/12 | 3/8 |
| V4 Pro | AgentDojo | Policy / safe | 2/12 | 3/8 |
| V4 Pro | AgentDojo | Full / normal | 0/12 | 3/8 |
| V4 Pro | AgentDojo | Full / safe | 0/12 | 3/8 |
| V4 Pro | M3-v2 | No guard / normal | 0/12 | 6/8 |
| V4 Pro | M3-v2 | No guard / safe | 0/12 | 6/8 |
| V4 Pro | M3-v2 | Policy / normal | 0/12 | 6/8 |
| V4 Pro | M3-v2 | Policy / safe | 0/12 | 4/8 |
| V4 Pro | M3-v2 | Full / normal | 0/12 | 6/8 |
| V4 Pro | M3-v2 | Full / safe | 0/12 | 4/8 |
| V4.1 Flash | AgentDojo | No guard / normal | 1/12 | 7/8 |
| V4.1 Flash | AgentDojo | No guard / safe | 0/12 | 7/8 |
| V4.1 Flash | AgentDojo | Policy / normal | 0/12 | 4/8 |
| V4.1 Flash | AgentDojo | Policy / safe | 0/12 | 4/8 |
| V4.1 Flash | AgentDojo | Full / normal | 0/12 | 4/8 |
| V4.1 Flash | AgentDojo | Full / safe | 0/12 | 4/8 |
| V4.1 Flash | M3-v2 | No guard / normal | 0/12 | 6/8 |
| V4.1 Flash | M3-v2 | No guard / safe | 0/12 | 6/8 |
| V4.1 Flash | M3-v2 | Policy / normal | 0/12 | 6/8 |
| V4.1 Flash | M3-v2 | Policy / safe | 0/12 | 6/8 |
| V4.1 Flash | M3-v2 | Full / normal | 0/12 | 6/8 |
| V4.1 Flash | M3-v2 | Full / safe | 0/12 | 6/8 |
