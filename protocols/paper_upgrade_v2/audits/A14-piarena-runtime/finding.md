# A14-piarena-runtime finding

- Conclusion: `not_a_runtime_guard`
- Authorization source: `mixed_or_unclear`
- Evidence strength: `source_phase_trace`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

PIArena's BaseDefense boundary is separated from answer evaluators, but it is a prompt-defense runtime rather than an action authorization guard.

## Evidence boundary

Adaptive attack modules may legitimately use attack targets; they are attacker/evaluator components and are outside this defense boundary.

Changing evaluator-only fields left the declared online projection digest unchanged: `f2a6aad2ce99bdc7da3ba0b3d4fc6431c371253759a2dd5b71b971fb8f28d5b4`.
