# Task Shield alignment adapter protocol v1

Status: adapter/mechanics preflight only.

This protocol defines the minimum compatibility layer for evaluating Task
Shield as an external strong baseline in the paper-v1 plan. It does not claim
that the Task Shield algorithm has been reproduced or run.

## Source boundary

- Primary reference: ACL 2025 Task Shield paper.
- Local official source: not pinned in this checkout.
- Current implementation state: no official repository and no disclosed
  paper-to-code reproduction semantics are frozen.
- Formal results are forbidden until either official code or a disclosed
  reproduction has a frozen verifier prompt/model, decision labels, thresholds
  and complete logs.

## Online inputs

The adapter may construct task-alignment records only from:

- `online_inputs.trusted_user_request`;
- `online_inputs.trusted_app_context`;
- `online_inputs.tool_schemas`;
- runtime `ActionProposal` fields that arise during the evaluated run;
- untrusted content hashes or context fields, explicitly marked as not being
  the task goal.

It must not consume:

- `offline_evaluation`;
- `authorized_actions`;
- `requires_tool`;
- `expected_user_tool`;
- `expected_user_tool_parameters`;
- attacker tool labels;
- attack goals, target actions or expected safe behavior.

## Alignment record

The preflight record contains:

- trusted task text and hash;
- runtime proposed tool and argument-key/hash summary;
- proposed tool schema summary;
- untrusted context hash;
- forbidden-field audit result.

The deterministic stub decision checks only whether the runtime proposed action
appears aligned with the trusted task. It exists only to validate adapter
plumbing. A formal baseline must replace it with the selected Task Shield
verifier.

## Formal eligibility checklist

Task Shield may enter formal result tables only after all items are true:

1. official implementation or disclosed reproduction is frozen;
2. verifier prompt/model, thresholds and labels are fixed before formal runs;
3. proposed actions come from runtime logs, not evaluator answers;
4. no offline/evaluator fields reach the verifier;
5. failure handling for invalid, timeout, ASK and parse errors is frozen;
6. complete verifier inputs, outputs, stderr and manifests are saved;
7. formal runs use frozen datasets, cases, seeds and model/runtime parameters.
