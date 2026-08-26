# E3 risk-enriched challenge result

Status: complete, outcome-enriched conditional analysis

## Execution and integrity

- Work items: 240/240, all response-bearing; 330 official response IDs.
- Operational statuses: 185 completed, 17 parse failures, and 38 provider
  failures, all retained in ITT.
- Online forbidden fields, provider-managed tools, and real external effects:
  0/240 for each.
- Official-API cost: CNY 1.0690866.

## Conditional outcomes

| Cell | Unsafe effect | Unsafe-or-failure | ASK incidence | DENY incidence | Operational failure |
|---|---:|---:|---:|---:|---:|
| policy / normal | 1/60 (1.7%) | 16/60 (26.7%) | 23/60 (38.3%) | 15/60 (25.0%) | 15/60 (25.0%) |
| policy / safe | 1/60 (1.7%) | 15/60 (25.0%) | 11/60 (18.3%) | 14/60 (23.3%) | 14/60 (23.3%) |
| full / normal | 0/60 (0.0%) | 12/60 (20.0%) | 21/60 (35.0%) | 19/60 (31.7%) | 12/60 (20.0%) |
| full / safe | 0/60 (0.0%) | 14/60 (23.3%) | 14/60 (23.3%) | 16/60 (26.7%) | 14/60 (23.3%) |

The unsafe-effect module point estimate is −1.67 percentage points (95%
bootstrap CI −5.00 to 0.00 pp); the prompt and interaction estimates are zero.
For unsafe-or-failure, module is −4.17 pp (−10.00 to +0.83), prompt is +0.83 pp
(−8.33 to +10.00), and interaction is +5.00 pp (−3.33 to +13.33). These are
challenge/sensitivity estimates and open no new significance family.

## Historical reproduction

Every selected case had produced an unsafe effect under at least one earlier
Public condition. Only 1/60 did so under any new concurrent cell (1.67%; Wilson
95% CI 0.29%--8.86%). The new execution window therefore did not reproduce most
historical unsafe effects. Possible explanations include stochastic model
behavior, changed served weights behind the provider alias, prompt/runtime
changes, and the high operational-failure burden. This study cannot identify
which explanation dominates.

## Interpretation boundary

The outcome-enriched set is not an estimate of deployment prevalence. Its main
finding is instability: historical vulnerability selected the cases, yet the
concurrent runs showed only one reproduced unsafe effect and 55 operational
failures. Direct unsafe-effect estimates remain floor-limited, while the
failure-sensitive bound ranges from 20.0% to 26.7%. The paper therefore reports
both endpoints and does not credit a non-operational run as evidence of safety.
