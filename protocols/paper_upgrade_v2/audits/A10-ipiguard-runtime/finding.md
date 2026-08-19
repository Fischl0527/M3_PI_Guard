# A10-ipiguard-runtime finding

- Conclusion: `no_online_gold_observed`
- Authorization source: `auto_compiled_non_gold`
- Evidence strength: `source_boundary_trace_plus_declared_projection_differential`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

No evaluator label or expected tool is present in the inspected IPIGuard DAG construction/traversal boundaries.

## Evidence boundary

The pinned implementation previously failed local qualification on unstable DAG JSON. This audit establishes field visibility, not runtime reliability.

Changing evaluator-only fields left the declared online projection digest unchanged: `bfd9e2ca0508cc28fe7889294b6b62d92b3efc9995af80aaaa63643b4f9893bc`.
