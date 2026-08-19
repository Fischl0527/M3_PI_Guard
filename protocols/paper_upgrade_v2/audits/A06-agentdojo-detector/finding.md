# A06-agentdojo-detector finding

- Conclusion: `no_online_gold_observed`
- Authorization source: `broad_default`
- Evidence strength: `source_boundary_trace_plus_declared_projection_differential`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

The online detector is label-independent with respect to benchmark evaluation. Its own model output label and safe_label configuration are intrinsic detector state.

## Evidence boundary

This is detector-only evidence and cannot be equated with runtime authorization or unsafe-effect prevention.

Changing evaluator-only fields left the declared online projection digest unchanged: `77ed23231dbd1d489ad879fd5a54b2525763569d14ff4ef0bbbbcd97a239902a`.
