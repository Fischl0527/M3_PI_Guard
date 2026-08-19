# A18-asb-evaluator finding

- Conclusion: `not_a_runtime_guard`
- Authorization source: `mixed_or_unclear`
- Evidence strength: `source_phase_separation`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

ASB answer-key information belongs to post-hoc metrics. It would be oracle leakage only if a defense adapter passed these fields into its online Guard.

## Evidence boundary

The upstream script also reports an ASR excluding workflow failures; paper-v2 must retain such failures in the ITT denominator.

Changing evaluator-only fields left the declared online projection digest unchanged: `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`.
