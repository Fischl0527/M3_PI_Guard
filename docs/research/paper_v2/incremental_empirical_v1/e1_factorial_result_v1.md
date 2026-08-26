# E1 concurrent prompt-by-module factorial result

Status: complete, prespecified ITT analysis

## Execution and integrity

- Planned/latest terminal work items: 720/720 (180 per cell).
- Response-bearing work items: 720; official response IDs: 1,102.
- Append-only physical rows: 722, including two superseded response-less
  engineering attempts; no successful work item was rerun.
- Operational statuses: 657 completed, 54 parse failures, and 9 provider
  failures. All 63 non-completed outcomes remain in ITT.
- Online forbidden fields, provider-managed tools, and real external effects:
  0/720 for each.
- Conservative official-API cost: CNY 3.6602862, below the CNY 8 fuse.

## Cell outcomes

| Cell | Attack unsafe effect | Attack unsafe-or-failure | Benign-tool TCR | ASK incidence | DENY incidence | Operational failure |
|---|---:|---:|---:|---:|---:|---:|
| policy / normal | 1/100 (1.0%) | 9/100 (9.0%) | 23/60 (38.3%) | 65/180 (36.1%) | 15/180 (8.3%) | 15/180 (8.3%) |
| policy / safe | 1/100 (1.0%) | 11/100 (11.0%) | 21/60 (35.0%) | 55/180 (30.6%) | 16/180 (8.9%) | 16/180 (8.9%) |
| full / normal | 0/100 (0.0%) | 7/100 (7.0%) | 21/60 (35.0%) | 63/180 (35.0%) | 22/180 (12.2%) | 16/180 (8.9%) |
| full / safe | 0/100 (0.0%) | 8/100 (8.0%) | 19/60 (31.7%) | 62/180 (34.4%) | 21/180 (11.7%) | 16/180 (8.9%) |

## Prespecified factor estimates

Absolute effects are probability differences. Confidence intervals use 10,000
case-cluster bootstrap replicates. The three factors are Holm-adjusted within
each co-primary endpoint family (`unsafe_effect` and benign-tool TCR). The
prespecified `unsafe-or-failure` sensitivity endpoint is reported with its
descriptive bootstrap p-value and is not part of a Holm family.

| Endpoint | Factor | Effect | 95% bootstrap CI | p-value role |
|---|---|---:|---:|---:|
| Attack unsafe effect | modules (full − policy) | −1.00 pp | [−3.00, 0.00] pp | Holm 1.000 |
| Attack unsafe effect | prompt (safe − normal) | 0.00 pp | [0.00, 0.00] pp | Holm 1.000 |
| Attack unsafe effect | module × prompt | 0.00 pp | [0.00, 0.00] pp | Holm 1.000 |
| Attack unsafe-or-failure | modules | −2.50 pp | [−5.50, 0.00] pp | descriptive bootstrap 0.0938 |
| Attack unsafe-or-failure | prompt | +1.50 pp | [−3.00, +6.00] pp | descriptive bootstrap 0.5868 |
| Attack unsafe-or-failure | module × prompt | −1.00 pp | [−5.00, +3.00] pp | descriptive bootstrap 0.8206 |
| Benign-tool TCR | modules | −3.33 pp | [−8.33, 0.00] pp | Holm 0.2880 |
| Benign-tool TCR | prompt | −3.33 pp | [−10.83, +4.17] pp | Holm 0.8992 |
| Benign-tool TCR | module × prompt | 0.00 pp | [−6.67, +8.33] pp | Holm 1.000 |

## Interpretation boundary

E1 successfully removes the prompt-profile/runtime-module confounding, but it
does not resolve the safety-floor limitation: only two unsafe effects occurred
across 400 assigned attack runs. The point estimates do not provide evidence
of a prompt main effect or interaction, and the module estimates are small with
intervals including zero. The challenge study (E3) is therefore necessary for
conditional robustness on historically difficult cases; it cannot be used to
estimate deployment prevalence.
