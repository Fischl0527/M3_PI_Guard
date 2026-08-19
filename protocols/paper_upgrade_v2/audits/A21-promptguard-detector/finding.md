# A21-promptguard-detector finding

- Conclusion: `not_a_runtime_guard`
- Authorization source: `broad_default`
- Evidence strength: `model_artifact_and_adapter_role_classification`
- Review status: `single_reviewer_complete`
- Claim-ready for domain-wide statements: `false`

## Finding

PromptGuard must remain detector-only in paper-v2 tables. Its detector scores cannot be reported as unsafe-effect prevention without a separate enforcement policy.

## Evidence boundary

The model artifact has no generic tool-authorization interface; runtime behavior is supplied by the host adapter and requires its own source audit.

Changing evaluator-only fields left the declared online projection digest unchanged: `da15ea721be6988c2d421fca53e2899844f8f1386d6b9ca33ccfc47d4f581d1e`.
