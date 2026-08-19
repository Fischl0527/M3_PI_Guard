# A13-injecagent-evaluator finding

- Conclusion: `not_a_runtime_guard`
- Authorization source: `mixed_or_unclear`
- Evidence strength: `source_phase_separation`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

InjecAgent answer-key fields are used by post-hoc evaluation functions, not by the inspected model-call boundary.

## Evidence boundary

A future defense adapter must preserve this separation; wrapping the evaluator as a Guard would create oracle leakage.

Changing evaluator-only fields left the declared online projection digest unchanged: `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`.
