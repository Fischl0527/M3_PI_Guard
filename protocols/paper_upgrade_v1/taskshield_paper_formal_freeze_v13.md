# Task Shield disclosed paper-reproduction freeze v1.3

- Status: `completed_frozen_formal_protocol`
- Checks: 14/14
- Cases: 726 (97 utility + 629 security)
- Model: `m3-paper-qwen3-8b-v1:latest`
- Runtime patch: `m3-paper-v1-taskshield-runtime-compat-1.3`
- Result eligible: `False` until fresh qualification and full formal admission.

## v1.3 change

v1.2 failed utility case agentdojo:v1:banking:user_task_13 because the local verifier returned a contribution row count different from the trusted task count; v1.3 denies/suppresses such proposals instead of terminating the case.

Contribution-scoring parse/schema/score/cardinality errors now fail closed to zero contribution. Trusted task extraction remains strict.

## Evidence boundary

Protocol freeze only. This is a disclosed Task Shield paper reproduction, not official Task Shield source. v1.3 adds a hash-bound fail-closed contribution-scoring compatibility patch after a v1.2 parser/cardinality failure; it must be reported separately from v1.2 and cannot enter tables before fresh qualification, exact 726-case execution, complete traces, analysis and explicit admission.
