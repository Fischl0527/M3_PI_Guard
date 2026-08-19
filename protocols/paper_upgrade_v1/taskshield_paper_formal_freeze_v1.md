# Task Shield disclosed paper-reproduction freeze v1

- Status: `completed_frozen_formal_protocol`
- Checks: 13/13
- Cases: 726 (97 utility + 629 security)
- Model: `m3-paper-qwen3-8b-v1:latest`
- Paper SHA-256: `057ff02152c0bb61892b08abdc80f7af22416c03819e526878091ee87d3bf1e6`
- Result eligible: `False` until qualification and full formal admission.

## Reproduction boundary

- No public official Task Shield repository is pinned; this condition is never labelled official-source.
- The implementation follows the paper's extraction, fuzzy contribution scoring, zero threshold, assistant/tool-output feedback, and tool-call argument checks.
- Prompt wording is a concise semantic restatement, not a byte-identical appendix copy.
- The initial trusted user request is the only source that can extend the user task set; tool output remains untrusted.
- Invalid verifier JSON fails the case and stays in the original denominator.

## Evidence boundary

Protocol freeze only. This is a disclosed reproduction from the ACL paper, not official Task Shield source. It uses a local Qwen3 8B agent/verifier instead of the paper's GPT models and cannot enter tables before qualification, exact 726-case execution, complete verifier traces, and explicit admission.
