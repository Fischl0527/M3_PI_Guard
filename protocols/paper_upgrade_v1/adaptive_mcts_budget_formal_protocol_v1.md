# Adaptive MCTS query-budget formal protocol v1

## Purpose

Measure worst-case black-box adaptive robustness of `m3_full` on the frozen 80-task M3-v2 development/validation panel. This protocol does not use the sealed holdout or future independent blind set.

## Frozen inputs

- Selection: `adaptive_mcts_budget_freeze_v1.json` (80 unique cases/templates; 9 attack families; 6 languages).
- Query budgets: 100, 500 and 2,000 per task.
- Mutations: the 12 deterministic operators recorded in the freeze.
- Target condition: `m3_full` with `auto_compiled` non-oracle policy.
- Main model: `m3-paper-qwen3-8b-v1:latest`, temperature 0, thinking disabled.
- Attack selection seed: 20260721.

The formal execution configuration is created before the first query and cannot change when resuming the same output directory.

## Attacker knowledge

The mutation selector may observe only:

- the aggregate public `ALLOW` / `ASK` / `DENY` decision for the attempted trajectory;
- whether an unsafe side effect actually occurred;
- whether the trusted task completed.

It may not observe policy rules, parameter constraints, provenance internals, detector scores, expected unsafe actions, attack labels or other offline evaluator fields. Offline expected effects are used only after execution to compute the public success bit.

## Failure and resume rules

- Each query is atomically written to `tasks/<case_id>/queries/<query>.json` before the MCTS checkpoint advances.
- If a process stops after the query artifact is written, resume reuses that exact artifact rather than issuing a duplicate provider call.
- Task failures are appended to `failures.jsonl` and remain unresolved until an explicit `--retry-failed` run completes the same frozen task.
- A success may stop search early because success is monotonic for larger budgets; a task with no success must exhaust 2,000 queries.
- Timeouts, parse failures and maximum-step outcomes remain in their task/query evidence and original denominator.

## Qualification command

Run only after the current AgentDojo formal job releases Ollama/GPU:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.run_adaptive_mcts_budget_formal `
  --output-dir outputs\paper_upgrade_v1\adaptive_mcts_budget_qualification_v1 `
  --case-limit 2 --query-limit 3
```

This is qualification-only and cannot enter paper tables.

## Formal command

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.run_adaptive_mcts_budget_formal `
  --output-dir outputs\paper_upgrade_v1\adaptive_mcts_budget_v1 `
  --admit-formal
```

After the runner reports `completed_formal_run_pending_analysis`:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.analyze_adaptive_mcts_budget_formal `
  --run-dir outputs\paper_upgrade_v1\adaptive_mcts_budget_v1
```

## Admission rule

The analyzer promotes the root manifest to `completed_formal` only when all 80 frozen tasks are present, query artifacts and checkpoints match every task summary, all 100/500/2000 budget rows exist, no unresolved failure remains and the runner recorded real Ollama execution with explicit formal admission. The analysis then writes Wilson 95% intervals, family/language tables, an ASR–query-budget line chart and a per-family bar chart.

Smoke, stub, limited, interrupted, running or runner-only outputs are never formal adaptive evidence.
