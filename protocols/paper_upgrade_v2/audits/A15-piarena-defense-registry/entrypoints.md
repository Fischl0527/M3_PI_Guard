# A15-piarena-defense-registry entrypoints

- Artifact: PIArena
- Component: defense adapters and parameter projection
- Commit: `c39fd88e733493242a8ea6bdbc824ad30245bcf7`

## Online boundaries

- `external/paper_v2_audits/piarena/piarena/defenses/__init__.py:21` — `get_defense`; parameters: `name, config`
- `external/paper_v2_audits/piarena/piarena/defenses/base.py:23` — `BaseDefense.execute_batch`; parameters: `self, target_insts, contexts`

## Offline/evaluator boundaries

- None identified for this audit unit.

## Scope note

The registry constructs prompt-defense adapters from a defense name/config and batches target instructions/contexts.
