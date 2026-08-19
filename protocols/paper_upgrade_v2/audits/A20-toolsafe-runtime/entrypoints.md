# A20-toolsafe-runtime entrypoints

- Artifact: ToolSafe
- Component: step-level tool guardrail and feedback
- Commit: `46358fa424a927a895c6c8322f99032c4eb5155e`

## Online boundaries

- `external/paper_v2_audits/toolsafe/src/model/model.py:123` — `Guardian.tool_safety_guardian`; parameters: `self, user_request, interaction_history, current_action, current_action_description`
- `external/paper_v2_audits/toolsafe/src/model/model.py:162` — `Guardian.alignment_check`; parameters: `self, user_request, interaction_history, current_action, current_action_description`

## Offline/evaluator boundaries

- `external/paper_v2_audits/toolsafe/src/guardian_evaluator/agentdojo.py:21` — `AgentDojoProcessor.run`

## Scope note

Guardian methods format only user request, interaction history, current action and environment/action description. Dataset score is appended after the call.
