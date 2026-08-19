# A08-progent-runtime finding

- Conclusion: `no_online_gold_observed`
- Authorization source: `auto_compiled_non_gold`
- Evidence strength: `source_boundary_trace_plus_declared_projection_differential`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

No evaluator/gold fields are present at the inspected Progent policy/enforcement boundaries. Automatic narrowing is optional via SECAGENT_ONLY_ALLOW_NARROW and is not the default, which remains a material mechanism difference from M3.

## Evidence boundary

No live policy-model request was made. The absent root license and optional rather than default narrowing must be disclosed.

Changing evaluator-only fields left the declared online projection digest unchanged: `c58ceb68f9938073cd70e41d8bb4e9fd07a18725a1c9374c9e9c5b64a3bffeed`.
