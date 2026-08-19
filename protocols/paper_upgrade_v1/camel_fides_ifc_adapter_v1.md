# CaMeL/FIDES IFC-capability adapter protocol v1

Status: adapter/mechanics preflight only.

This protocol defines the minimum compatibility layer for filling the
information-flow/capability strong-baseline slot in the paper-v1 plan. It does
not claim that CaMeL or FIDES has been reproduced or run.

## Candidate boundary

- CaMeL expected repository: `https://github.com/google-research/camel-prompt-injection`.
- CaMeL expected commit: `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8`.
- FIDES expected repository: `https://github.com/microsoft/fides`.
- FIDES expected commit: `669c046c4adbc56ee49c9672fdd30c54937ea062`.
- Current local source state: neither candidate is checked out under
  `external/baselines/`.
- Current method state: the formal information-flow/capability baseline has not
  been selected.

Formal results are forbidden until one method is selected, exact source and
dependencies are pinned, and interpreter or label-lattice assumptions are
frozen.

## Online inputs

The adapter may construct IFC/capability packages only from:

- `online_inputs.trusted_user_request`;
- `online_inputs.trusted_app_context`;
- `online_inputs.tool_schemas`;
- explicitly untrusted content marked as low-integrity;
- runtime `ActionProposal` fields and argument provenance from the evaluated
  run.

It must not consume:

- `offline_evaluation`;
- `authorized_actions`;
- `requires_tool`;
- `expected_user_tool`;
- `expected_user_tool_parameters`;
- attacker tool labels;
- attack goals, target actions or expected safe behavior.

## IFC/capability package

The preflight package records:

- trusted task text and hash;
- trusted and untrusted source labels;
- tool roles such as data source, internal action or external sink;
- trusted-task capability grants;
- runtime action argument sources and integrity labels;
- forbidden-field audit result.

The deterministic stub decision checks only whether a proposed external sink has
trusted capability and whether low-integrity data flows to an untrusted
destination. It exists only to validate adapter plumbing. A formal baseline must
replace it with the selected CaMeL interpreter or FIDES label-policy mechanism.

## Formal eligibility checklist

CaMeL or FIDES may enter formal result tables only after all items are true:

1. one candidate method is selected before formal freeze;
2. exact source commit and dependencies are checked out and hash-verified;
3. model/API requirements and local transport are frozen;
4. interpreter assumptions, capabilities, label lattice or hiding primitives are
   fixed;
5. benchmark tool schemas are mapped without evaluator labels;
6. runtime proposed actions and argument provenance come from logs, not gold
   answers;
7. complete package inputs, decisions, stderr and manifests are saved.
