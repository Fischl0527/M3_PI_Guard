# Conclusion — provisional DeepSeek evidence

Status: `deepseek_complete_gemini_diagnostic_closed`

This study treats runtime authorization as an experimental variable rather
than fixed infrastructure. Across the completed medium and Public studies, the
full configuration package reduced unsafe effects relative to a structural
baseline but did not improve on the policy package. The larger historical
direction replicated across DeepSeek V4 Pro and V4 Flash: the full package
produced more unsafe effects, while benign-tool utility was equal or only
slightly different.

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

The concurrent 2×2 experiment then separated prompt profile from the runtime
module bundle. Across 400 attack assignments, the policy cells produced two
unsafe effects and the full cells produced none; the module estimate was −1.00
percentage point (95% bootstrap CI −3.00 to 0.00), while the prompt and
interaction estimates were zero. Benign-tool module and prompt effects were
both −3.33 points with intervals including zero. The design resolves the
prompt/module confounding but remains floor-limited and does not isolate the
individual provenance, data-flow, monotonicity, or confirmation components.

The source-authority counterfactual supplies the corresponding mechanism
evidence. Full-Guard decisions changed under an untrusted source, whereas the
policy-only distribution did not; replay produced 0/480 false allows and
30/480 false blocks. Yet all 240 end-to-end runs executed no action because
ASK or DENY intervened. Mechanism-level provenance sensitivity is therefore
not equivalent to usable end-to-end utility. The outcome-enriched challenge
set likewise reproduced only 1/60 historical unsafe effects and incurred 55
operational failures, while the Flash factorial replication had zero unsafe
effects in every attack cell. Both results reinforce the need to report a
failure-sensitive endpoint instead of treating non-operation as safety.

The adaptive panel supplies a related measurement warning. First unsafe
effects were observed for 4/40 tasks by query 50 and 18/40 by query 200. A
single low attack budget would have missed most successes found by the larger
budget. The extension toward 500 is conditional on a prespecified subset of
B200 survivors and cannot be merged into a full B500 curve or used to establish
saturation.

These findings support four practical requirements for tool-agent security
evaluation: keep evaluator-only fields outside online Guard state; manipulate
prompt and runtime factors separately; pair deterministic source-authority
replay with end-to-end execution; and report utility, ASK/DENY incidence,
failures, latency, and attack budget alongside unsafe effects. The conclusions
remain limited to the tested policies, benchmarks, runtime implementation,
DeepSeek models, and budget range. The prespecified Gemini sample closed
incomplete under its free-tier stopping rule and remains diagnostic; it cannot
erase or broaden the completed DeepSeek findings.
