# A04-agentdojo-case-loader finding

- Conclusion: `no_online_gold_observed`
- Authorization source: `broad_default`
- Evidence strength: `source_boundary_trace_plus_declared_projection_differential`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

The fixed loader/orchestrator retains task objects outside the pipeline call. The online AgentPipeline boundary itself does not accept answer or success fields.

## Evidence boundary

The environment deliberately contains injected content. This finding concerns evaluator/gold separation, not the absence of malicious content.

Changing evaluator-only fields left the declared online projection digest unchanged: `dde779fd37429590d6762e6977761ade5350759ac10d39007604efbddeb7d8ae`.
