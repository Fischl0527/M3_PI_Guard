# Abstract — lean empirical study

Status: `deepseek_results_filled_gemini_diagnostic_closed`

Tool-using LLM agents can turn prompt injection into external actions, but
measured security depends on the runtime authorization supplied to the Guard.
We keep evaluator fields offline, vary five controlled authorization
transformations, and jointly report unsafe effects, benign completion, system
decision incidence, failure, and latency.

We reanalyze 7,353 condition-level DeepSeek records covering 902 distinct cases
across overlapping cohorts, plus a 40-task defense-aware panel. In Public
matrices, the full package produced more unsafe effects than the policy package
on V4 Pro (38/600 versus 13/600) and V4 Flash (24/400 versus 12/400). Adaptive
search found first unsafe effects for 4/40 tasks by query 50 and 18/40 by 200.

A frozen 900-work-item V4 Pro experiment crossed both packages with non-oracle
`auto_compiled` and oracle-sensitivity `exact_gold` authorization on 180 paired
AgentDojo and M3-v2 cases. Three attack cells had 0/100 unsafe effects and one
had 1/100. Exact-minus-auto benign completion reversed by benchmark: AgentDojo
changed by +13.33/+10.00 points for policy/full packages, whereas M3-v2 changed
by −56.67/−40.00. A pessimistic unsafe-or-operational-failure endpoint increased
by 18 points for both packages, driven by +36-point AgentDojo differences.

Authorization construction and benchmark semantics can change measured
security–utility conclusions even near the observed attack floor. Because
prompt profile and runtime modules differ together, the package contrast is not
a component ablation. Incomplete Gemini execution supports no cross-provider
inference.

Keywords: prompt injection; LLM agents; runtime authorization; provenance;
security–utility trade-off
