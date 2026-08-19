# A09-camel-runtime finding

- Conclusion: `mixed_or_path_dependent`
- Authorization source: `mixed_or_unclear`
- Evidence strength: `source_path_comparison_plus_declared_projection_differential`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

The live interpreter path does not expose benchmark labels, but replay components explicitly capture user_task_id and injection_task_id to select historical traces. Comparisons must distinguish live CaMeL from replay mode.

## Evidence boundary

Task IDs are not themselves success labels, but they can select case-specific artifacts. A dynamic replay sentinel test and independent review are still required before stronger claims.

Changing evaluator-only fields left the declared online projection digest unchanged: `cf439021123803b70c19564d6f61e448e496d930df3736b78cf9c3f4bfd523a5`.
