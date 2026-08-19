# A07-agentdojo-evaluator finding

- Conclusion: `not_a_runtime_guard`
- Authorization source: `mixed_or_unclear`
- Evidence strength: `source_phase_separation`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

AgentDojo utility/security methods are post-hoc evaluators. Their access to task definitions is expected and must not be confused with online defense visibility.

## Evidence boundary

This unit does not audit every third-party defense integrated into AgentDojo.

Changing evaluator-only fields left the declared online projection digest unchanged: `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`.
