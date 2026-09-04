# Supplementary material

**Article:** Evaluating Authorization Regimes and Runtime Guardrail Configurations for Tool-Using LLM Agents

These twelve tables provide detailed results referenced by the main manuscript. They introduce no additional hypothesis family or claim beyond the analyses reported in the article.

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
