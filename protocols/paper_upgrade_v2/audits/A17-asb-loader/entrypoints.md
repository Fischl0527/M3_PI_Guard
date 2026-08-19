# A17-asb-loader entrypoints

- Artifact: Agent Security Bench
- Component: scenario, attack, and defense loader
- Commit: `1f561dccf92d55302368fa67679b4ba9d9c8fdc4`

## Online boundaries

- `external/paper_v2_audits/asb/pyopenagi/agents/react_agent_attack.py:260` — `ReactAgentAttack.run`; parameters: `self`
- `external/paper_v2_audits/asb/pyopenagi/agents/react_agent.py:123` — `ReactAgent.run`; parameters: `self`

## Offline/evaluator boundaries

- None identified for this audit unit.

## Scope note

ASB intentionally installs attacker tools/payloads into the online attack environment; this is benchmark construction rather than a defense authorization key.
