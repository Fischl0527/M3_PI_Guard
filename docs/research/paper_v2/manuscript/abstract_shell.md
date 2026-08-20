# Abstract — lean empirical study

Status: `deepseek_results_filled_gemini_pending`

Tool-using LLM agents can turn prompt injection into external actions, but
measured security depends on runtime authorization. We exclude raw evaluator
and scoring fields from online state, vary authorization—including an
explicitly gold-derived sensitivity condition—and jointly measure unsafe
effects, task completion, burden, failure, latency, and cost.

We reanalyze 7,353 DeepSeek records and 40 defense-aware adaptive
tasks. In a 5,082-record V4 Pro Public matrix, M3-full produced 38/600 unsafe
effects versus 13/600 for policy-only, while both completed 49/168 benign tool
tasks. A 1,791-record V4 Flash matrix showed the same security
direction (24/400 versus 12/400). Adaptive search found first unsafe effects
for 4/40 tasks by query 50 and 18/40 by query 200.

A frozen 900-work-item V4 Pro experiment crossed two Guard variants with
non-oracle `auto_compiled` and oracle-sensitivity `exact_gold` authorization on
180 paired AgentDojo and M3-v2 cases. Three of four main cells had 0/100 unsafe
effects and the fourth had 1/100. Changing from `auto_compiled` to `exact_gold`
reduced benign-tool completion by 21.67 percentage points for policy-only and
15.00 for M3-full. It eliminated `ASK` but increased records with `DENY` to
45.00–48.89%, failures to about 24%, and p95 latency to about 19.5 seconds.

Authorization construction can therefore alter security–utility measurements
even when attack rates appear stable. The evaluated provenance-aware
extensions showed no stable gain over policy-only. A Gemini sample
remains pending and supports no cross-provider claim.

Keywords: prompt injection; LLM agents; runtime authorization; provenance;
security–utility trade-off
