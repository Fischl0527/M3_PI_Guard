# A11-struq-runtime finding

- Conclusion: `not_a_runtime_guard`
- Authorization source: `mixed_or_unclear`
- Evidence strength: `source_phase_trace`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

The inspected StruQ code is a prompt-structure/training defense rather than a tool-execution runtime guard. Some attack constructors use reference outputs to craft completion attacks, which is attack generation rather than online authorization.

## Evidence boundary

StruQ remains relevant to prompt injection but is not comparable to M3's ALLOW/ASK/DENY execution mechanism.

Changing evaluator-only fields left the declared online projection digest unchanged: `b197bea856c74365f6b0006e58d1966648e5c9c6bb4503a26f4fc248c3855a7a`.
