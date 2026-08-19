# IPIGuard TDG adapter protocol v1

Status: adapter/mechanics preflight only.

This protocol defines the minimum compatibility layer for evaluating IPIGuard as
an external strong baseline in the paper-v1 plan. It does not claim that
IPIGuard has been reproduced or run.

## Source boundary

- Expected repository: `https://github.com/Greysahy/ipiguard`.
- Expected commit: `4e686ed2f62c135cb12564a4466daa95f3ace878`.
- Local source target: `external/baselines/ipiguard`.
- Current source state: not checked out in this workspace.
- Formal results are forbidden until the exact source commit, dependency
  snapshot, graph construction rules, thresholds and complete logs are frozen.

## Online inputs

The adapter may construct TDG input packages only from:

- `online_inputs.trusted_user_request`;
- `online_inputs.trusted_app_context`;
- `online_inputs.tool_schemas`;
- runtime trace fields that exist before scoring and do not contain evaluator
  answers;
- untrusted content explicitly marked as untrusted.

It must not consume:

- `offline_evaluation`;
- `authorized_actions`;
- `requires_tool`;
- `expected_user_tool`;
- `expected_user_tool_parameters`;
- attacker tool labels;
- attack goals, target actions or expected safe behavior.

## TDG package

The preflight package records:

- trusted task text and hash;
- untrusted source hashes;
- normalized tool nodes;
- side-effect classification;
- candidate trusted-task dependency edges;
- untrusted-content-to-side-effect risk edges;
- forbidden-field audit result.

The stub edge logic exists only to validate adapter plumbing. The official
IPIGuard graph construction must replace it before any formal comparison.

## Formal eligibility checklist

IPIGuard may enter formal result tables only after all items are true:

1. exact source commit is checked out and hash-verified;
2. official TDG construction path is called instead of the stub;
3. M3-v2, AgentDojo and InjecAgent schema mappings are frozen;
4. all incompatible tool families are declared before running;
5. no offline/evaluator fields reach TDG construction;
6. complete graph inputs, decisions, stderr and manifests are saved;
7. formal runs use frozen datasets, thresholds and model/runtime parameters.
