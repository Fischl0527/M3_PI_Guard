# A15-piarena-defense-registry finding

- Conclusion: `not_a_runtime_guard`
- Authorization source: `mixed_or_unclear`
- Evidence strength: `source_boundary_trace_plus_declared_projection_differential`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

No evaluator fields are part of the inspected registry/execute_batch signatures, but these adapters do not implement tool authorization.

## Evidence boundary

Individual third-party defenses registered by PIArena require their own audits before use as formal comparators.

Changing evaluator-only fields left the declared online projection digest unchanged: `73dba5669d8d9c1637fd46c24b9cd38444cc40557b2b53a511ac101676128704`.
