# E14 V2 calibrated performance analysis

- Semantic validity: **pass**.
- Warmup: 48/48 case-runs (excluded).
- Formal: 432/432 case-runs.
- Matched benign identical paths: 144/144 pairs.
- Latency comparisons with paired tests: 12.
- Provider-incomplete formal case-runs retained as unsuccessful, non-executable outcomes: 0.
- Full Guard own p95 latency: 0.4536849999999999 ms; target pass=True.
- Median paired end-to-end overhead: 0.20168595850832038%; target pass=True.
- Guard overhead conclusions use only identical one-step benign paths; mixed attack/benign runs are system-throughput evidence only.
- Concurrency is client-offered concurrency. Full case-run overlap is checked from durable timestamps, but Ollama/GPU may still serialize internally.
- First-turn workload is bound to frozen one-token native proof; formal raw-provider token coverage is reported separately and missing token usage is never coerced to zero.
- GPU values are device-wide polled observations; they are not Guard-exclusive allocation and may miss transient peaks.
- Old V3 E14 is preserved as invalid context-axis diagnostic evidence and excluded from this denominator.
