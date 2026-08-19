# AgentDojo Formal Cell Runner v1

## Purpose

This protocol defines the AgentDojo-specific source producer for one frozen
public-benchmark formal cell.

Script:

- `experiments/paper_v1/benchmarks/run_agentdojo_formal_cell.py`

It sits before the generic public-benchmark formal-cell wrapper:

- `experiments/paper_v1/benchmarks/run_public_benchmark_formal_cell.py`

## Evidence boundary

The AgentDojo source producer does not by itself make paper-table results.
It produces `agentdojo_outcomes.jsonl`, which must still be ingested and
validated by the generic formal-cell wrapper and materializer.

Rows are admitted as `agentdojo_official_formal_case_run` only when all of the
following are true:

- formal-source admission is explicitly requested;
- the backend is not `stub`;
- the full frozen cell is selected, not a partial case limit;
- every selected AgentDojo native job completed;
- the generic materializer later verifies exact `todo_cases.jsonl` coverage.

If any condition is not met, rows keep the diagnostic source status and cannot
complete a formal cell.

Execution is resume-safe by default. Existing completed per-case manifests are
reused, existing `failure.json` records are retained, and failures are rerun
only when `--retry-failed` is explicitly supplied.

## Dry-run planning

Default invocation is non-executing:

```powershell
python -m experiments.paper_v1.benchmarks.run_agentdojo_formal_cell `
  --cell-id agentdojo__qwen3_4b_instruct__m3_full__r1 `
  --result-root outputs\paper_upgrade_v1\public_benchmark_formal_runs
```

The plan reports:

- model and defense condition;
- total frozen todo case-runs;
- selected case-runs if `--case-limit` is provided;
- suite counts;
- utility/security counts;
- output locations for source outcomes and execution manifest.

No model or benchmark service is started in dry-run mode.

## Source outcome execution

Execution must be requested explicitly:

```powershell
python -m experiments.paper_v1.benchmarks.run_agentdojo_formal_cell `
  --cell-id agentdojo__qwen3_4b_instruct__m3_full__r1 `
  --result-root outputs\paper_upgrade_v1\public_benchmark_formal_runs `
  --execute `
  --backend ollama `
  --max-steps 15
```

This produces:

- `agentdojo_native_source/agentdojo_outcomes.jsonl`
- `agentdojo_native_source/execution_manifest.json`
- `agentdojo_native_source/progress.jsonl`
- per-case native AgentDojo job manifests and audit logs under
  `agentdojo_native_source/jobs/<case_run_id>/`

Partial smoke runs are allowed for debugging with `--case-limit`, but they are
recorded as non-formal.

Resume controls:

- default: resume completed jobs and preserve failed jobs;
- `--no-resume`: clear the progress stream and recompute selected jobs;
- `--retry-failed`: rerun jobs that already have `failure.json`;
- resumed rows in `progress.jsonl` use `resumed_completed` or
  `resumed_failed`, so interrupted runs can be audited without chat history.

## Formal source admission and materialization

Only after the full frozen cell has been executed under a non-stub backend may
the source producer request formal-source admission:

```powershell
python -m experiments.paper_v1.benchmarks.run_agentdojo_formal_cell `
  --cell-id agentdojo__qwen3_4b_instruct__m3_full__r1 `
  --result-root outputs\paper_upgrade_v1\public_benchmark_formal_runs `
  --execute `
  --backend ollama `
  --admit-formal-source `
  --ingest `
  --materialize
```

Even then, the generic materializer remains the final gate. A cell becomes
result-eligible only after exact frozen todo coverage, completed rows, formal
evidence status, raw runs, metrics, statistics and figure manifest all exist.

## Current status

The script and unit tests are implemented. No full AgentDojo formal cell has
been executed yet in the current result ledger.

Current public benchmark completeness remains:

- expected cells: 60;
- initialized pending cells: 60;
- complete cells: 0;
- expected case-runs: 53,400;
- complete case-runs: 0;
- formal result-completeness gate: `not_satisfied`.
