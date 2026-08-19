# A18-asb-evaluator entrypoints

- Artifact: Agent Security Bench
- Component: security and utility metrics
- Commit: `1f561dccf92d55302368fa67679b4ba9d9c8fdc4`

## Online boundaries

- None identified for this audit unit.

## Offline/evaluator boundaries

- `external/paper_v2_audits/asb/main_attacker.py:43` — `check_attack_success`
- `external/paper_v2_audits/asb/main_attacker.py:54` — `check_original_success`

## Scope note

The metric helpers consume attacker_goal or the expected normal tool set after execution.
