# Conclusion — provisional DeepSeek evidence

Status: `deepseek_complete_gemini_diagnostic_closed`

This study treats runtime authorization as an experimental variable rather
than fixed infrastructure. Across the completed medium and Public studies,
the full configuration package reduced unsafe effects relative to a structural
baseline but did not improve on the policy package. The direction replicated
across DeepSeek V4 Pro and V4 Flash: the full package produced more unsafe
effects, while benign-tool utility was equal or only slightly different.
Because prompt profile and runtime modules differ together, this is a bundled
comparison and does not identify an individual component effect.

The prospectively frozen authorization experiment explains why security alone
is an incomplete endpoint. Unsafe effects remained at or near zero in all four
main cells. The pooled exact-minus-auto benign-tool differences were −21.67
points for the policy package and −15.00 for the full package, but AgentDojo
improved by 13.33/10.00 points while M3-v2 fell by 56.67/40.00. Under a
pessimistic unsafe-or-operational-failure bound, both packages worsened by 18
points overall, driven by +36-point changes on AgentDojo and no change on
M3-v2. Exact authorization removed system ASK but moved 45.00–48.89% of records
into at least one DENY, raised failures to approximately 24%, and increased
p95 latency. Broad, conflicting, and underspecified regimes
also reduced completion on the nested tool-task subset without changing the
observed attack floor. Authorization construction can therefore materially
alter the measured security–utility frontier even when an attack-only result
looks stable.

The adaptive panel supplies a related measurement warning. First unsafe
effects were observed for 4/40 tasks by query 50 and 18/40 by query 200. A
single low attack budget would have missed most successes found by the larger
budget, but two budget points cannot establish saturation.

These findings support three practical requirements for tool-agent security
evaluation: keep evaluator-only fields outside online Guard state, compare
configuration packages on identical tasks and hold prompts fixed when seeking
component attribution, and report utility, system ASK/DENY incidence, failures,
latency, and attack budget alongside unsafe effects. The conclusions remain limited to the tested policies, benchmarks,
runtime implementation, DeepSeek models, and budget range. The prespecified
Gemini sample closed incomplete under its free-tier stopping rule and remains
diagnostic; it cannot erase or broaden the completed DeepSeek findings.
