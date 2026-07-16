# E9/E14 Context Experiment Validity Audit

- Status: `fail`
- Audit type: post-freeze, non-causal metadata audit
- Original bundles mutated: no

## E9

- Status: `fail`
- Interpretation: Declared E9 lengths are not represented by calibrated prompt usage; security rates from collapsed/truncated cells are not interpretable as long-context robustness.

| Target prompt tokens | Rows | Observed min | Observed median | Observed max | Within 5% | Parse success |
| ---: | ---: | ---: | ---: | ---: | :---: | ---: |
| 16384 | 30 | 8192 | 8192.0 | 8192 | no | 0/30 (0.00%) |
| 2048 | 30 | 6307 | 6310.0 | 6320 | no | 30/30 (100.00%) |
| 4096 | 30 | 8192 | 8192.0 | 8192 | no | 0/30 (0.00%) |
| 8192 | 30 | 8192 | 8192.0 | 8192 | yes | 0/30 (0.00%) |

## E14

- Status: `fail`
- Interpretation: E14 changes a context label/configuration without materially changing prompt workload; it cannot support latency/throughput claims by context length.

| Condition | Prompt-token medians by declared context | Largest/smallest ratio | Valid scaling |
| --- | --- | ---: | :---: |
| full_guard | 2048=230.5, 4096=230.5, 8192=230.5, 16384=230.5 | 1.000 | no |
| off | 2048=486.5, 4096=486.5, 8192=486.5, 16384=486.5 | 1.000 | no |

## Required Action

Reopen failed experiments, create a new protocol/freeze with token-calibrated workloads and effective Ollama context configuration, rerun all affected cells, rebuild E17 source input and final analysis.
