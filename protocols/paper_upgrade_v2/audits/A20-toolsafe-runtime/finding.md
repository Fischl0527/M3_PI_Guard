# A20-toolsafe-runtime finding

- Conclusion: `no_online_gold_observed`
- Authorization source: `auto_compiled_non_gold`
- Evidence strength: `source_call_argument_trace_plus_declared_projection_differential`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

The inspected ToolSafe guard-call payload excludes sample score/label even though the surrounding evaluator later appends sample['score']. This is a valid phase separation at the call boundary.

## Evidence boundary

The repository has no root license file at the fixed commit, and this audit does not reproduce guard-model weights or effectiveness.

Changing evaluator-only fields left the declared online projection digest unchanged: `0955669d3d208a60641921f074180d6294ba3f277cbe4f0645e4bcc5c60c8f3f`.
