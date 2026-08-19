# A05-agentdojo-tool-filter finding

- Conclusion: `no_online_gold_observed`
- Authorization source: `auto_compiled_non_gold`
- Evidence strength: `source_boundary_trace_plus_declared_projection_differential`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

No per-case expected tool or evaluator label is present at OpenAILLMToolFilter.query; the selected runtime tool set is derived from messages and tool schemas.

## Evidence boundary

The filter is OpenAI-model-specific in this commit and this audit does not establish security effectiveness.

Changing evaluator-only fields left the declared online projection digest unchanged: `caa2d98294b6c7a010db17ecccb0ba102f5a29d3f37cb57918f978337f1d9015`.
