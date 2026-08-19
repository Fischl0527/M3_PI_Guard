# Progent policy adapter protocol v1

Status: adapter/mechanics preflight only.

This protocol defines the minimum compatibility layer for evaluating Progent as
an external strong baseline in the paper-v1 plan. It does not claim that
Progent's official programmable privilege-control system has been reproduced or
run.

## Source boundary

- Primary reference: Progent arXiv paper.
- Local official source: not pinned in this checkout.
- Current implementation state: no official repository and no disclosed DSL
  reproduction semantics are frozen.
- Formal results are forbidden until official semantics or a disclosed
  reproduction freezes the policy language, policy generator inputs, fallback
  actions and complete logs.

## Online inputs

The adapter may construct policy bundles only from:

- `online_inputs.trusted_user_request`;
- `online_inputs.trusted_app_context`;
- `online_inputs.tool_schemas`;
- runtime `ActionProposal` fields that arise during the evaluated run.

Untrusted content may be hashed for context auditing but must not generate new
policy permissions.

It must not consume:

- `offline_evaluation`;
- `authorized_actions`;
- `requires_tool`;
- `expected_user_tool`;
- `expected_user_tool_parameters`;
- attacker tool labels;
- attack goals, target actions or expected safe behavior.

## Policy bundle

The preflight bundle records:

- trusted task text and hash;
- tool rules generated from trusted task and tool schemas;
- side-effect classification;
- stub allow/ask/deny actions;
- untrusted content hash marked as not used for policy generation;
- forbidden-field audit result.

The deterministic stub rules exist only to validate adapter plumbing. A formal
baseline must replace them with the selected Progent DSL semantics.

## Formal eligibility checklist

Progent may enter formal result tables only after all items are true:

1. official implementation or disclosed DSL reproduction is frozen;
2. policy language subset and fallback behavior are fixed before formal runs;
3. policy generator consumes only trusted task/tool schema inputs;
4. runtime proposed actions come from logs, not evaluator answers;
5. no offline/evaluator fields reach policy generation or decision checking;
6. invalid, timeout, ASK and parse-failure handling is frozen;
7. complete policy bundles, decisions, stderr and manifests are saved.
