# Conclusion — provisional DeepSeek evidence

Status: `deepseek_complete_gemini_diagnostic_closed`

This study treats runtime authorization as an experimental variable rather
than fixed infrastructure. Across the completed medium and Public studies,
M3-full reduced unsafe effects relative to a structural baseline but did not
improve on policy-only enforcement. The direction replicated across DeepSeek
V4 Pro and V4 Flash: full produced more unsafe effects than policy-only, while
benign-tool utility was equal or only slightly different. The evaluated
provenance, temporal/data-flow, and confirmation extensions therefore did not
show an independent advantage sufficient to support a leading-defense claim.

The prospectively frozen authorization experiment explains why security alone
is an incomplete endpoint. Unsafe effects remained at or near zero in all four
main cells, yet changing from `auto_compiled` to `exact_gold` reduced
benign-tool completion by 21.67 percentage points for policy-only and 15.00
points for M3-full. Exact authorization removed ASK but moved 45.00–48.89% of
records into at least one DENY, raised failures to approximately 24%, and
roughly doubled p95 latency. Broad, conflicting, and underspecified regimes
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
complex mechanisms with a policy-only ablation on identical tasks, and report
utility, ASK/DENY burden, failures, latency, and attack budget alongside unsafe
effects. The conclusions remain limited to the tested policies, benchmarks,
runtime implementation, DeepSeek models, and budget range. The prespecified
Gemini sample closed incomplete under its free-tier stopping rule and remains
diagnostic; it cannot erase or broaden the completed DeepSeek findings.
