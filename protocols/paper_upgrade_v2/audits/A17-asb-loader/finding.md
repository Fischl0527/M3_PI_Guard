# A17-asb-loader finding

- Conclusion: `not_a_runtime_guard`
- Authorization source: `broad_default`
- Evidence strength: `source_phase_trace`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

The loader makes attacker tool content visible as attack surface, while attacker_goal is used by post-hoc evaluation. No independent per-case authorization policy is enforced.

## Evidence boundary

ASB is useful for attack generalization and over-blocking analysis but needs an explicit M3 authorization manifest for action-level evaluation.

Changing evaluator-only fields left the declared online projection digest unchanged: `86c71a27beeec70c3250f69f5e84ec20462493c0aa1d12737f7a0cdbc02099e4`.
