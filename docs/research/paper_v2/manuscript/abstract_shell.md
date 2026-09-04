# Abstract — lean empirical study

Status: `deepseek_e1_e6_complete_gemini_diagnostic_ne`

Tool-using LLM agents can turn prompt injection into external actions, but
measured security depends on the runtime authorization and Guard configuration.
We keep evaluator fields offline and jointly measure unsafe effects, benign
completion, confirmation/blocking, failures, latency, and adaptive attack cost.

We reanalyze 7,353 condition-level DeepSeek records and run controlled studies
of authorization regime, prompt and runtime factors, source authority,
historically difficult attacks, model replication, and attack-budget tails.
In Public matrices, the full package produced more unsafe effects than the
policy package on V4 Pro (38/600 versus 13/600) and V4 Flash (24/400 versus
12/400). A concurrent 2×2 experiment isolated prompt and module-bundle effects,
but only two unsafe effects occurred across 400 attack assignments. Deterministic
Guard replay was source-sensitive, whereas all 240 end-to-end source-swap runs
executed no action. Exact authorization reduced pooled benign-tool completion
and increased failure-sensitive risk, with opposite completion directions
across AgentDojo and M3-v2.

Defense-aware search found first unsafe effects for 4/40 tasks by query 50 and
18/40 by 200; none of 12 prespecified B200 survivors first succeeded by 500
(Wilson upper limit 24.25%). In an additional risk-enriched single-block
execution, no defense produced 17/60 unsafe effects, while policy/normal and
full/safe produced 2/60 and 0/60 unsafe effects; failures remained non-negligible.
These enriched results do not estimate deployment prevalence, utility, or
temporal repeatability. Two incomplete Gemini studies do not support estimation
of cross-provider effects.

Keywords: prompt injection; LLM agents; runtime authorization; provenance;
security–utility trade-off
