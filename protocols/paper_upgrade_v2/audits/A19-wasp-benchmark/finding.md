# A19-wasp-benchmark finding

- Conclusion: `not_a_runtime_guard`
- Authorization source: `broad_default`
- Evidence strength: `official_source_phase_trace_plus_declared_projection_differential`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

WASP is a web-agent attack benchmark, not a tool-authorization defense. Its attacker objective is intentionally embedded in the environment/prompt as attack surface, while user and attacker eval objects are constructed and consumed outside the inspected action-generation boundary.

## Evidence boundary

The repository was archived on 2026-07-01 and uses subproject code derived from WebArena/VisualWebArena. This static audit did not install the web environments, call a model, or establish M3 compatibility.

Changing evaluator-only fields left the declared online projection digest unchanged: `b785c1f3d6e5f271f7c92647ae8e5d1528f4d05d5b744e9599764f1cff4decd6`.
