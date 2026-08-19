# InjecAgent Formal Cell Runner v1

## Purpose

This protocol defines the InjecAgent-specific source producer for one frozen
public-benchmark formal cell.

Script:

- `experiments/paper_v1/benchmarks/run_injecagent_formal_cell.py`

It sits before the generic public-benchmark formal-cell wrapper:

- `experiments/paper_v1/benchmarks/run_public_benchmark_formal_cell.py`

## Evidence boundary

The InjecAgent source producer does not by itself make paper-table results.
It produces `injecagent_outcomes.jsonl`, which must still be ingested and
validated by the generic formal-cell wrapper and materializer.

Rows are admitted as `injecagent_official_formal_case_run` only when all of the
following are true:

- formal-source admission is explicitly requested;
- the backend is not `stub` or a test backend;
- the prompt style is an official InjecAgent ReAct style:
  `official_react` or `official_react_simple`;
- the full frozen cell is selected, not a partial case limit;
- every selected InjecAgent official-stage source job completed;
- the generic materializer later verifies exact `todo_cases.jsonl` coverage.

If any condition is not met, rows keep the diagnostic source status and cannot
complete a formal cell. In particular, the M3 JSON prompt style is useful for
diagnostics but is not admitted as formal InjecAgent source evidence.

Execution is resume-safe by default. Existing completed per-case manifests are
reused only when the paired `runs.jsonl` log exists, existing `failure.json`
records are retained, and failures are rerun only when `--retry-failed` is
explicitly supplied.

## Dry-run planning

Default invocation is non-executing:

```powershell
python -m experiments.paper_v1.benchmarks.run_injecagent_formal_cell `
  --cell-id injecagent__qwen3_4b_instruct__m3_full__r1 `
  --result-root outputs\paper_upgrade_v1\public_benchmark_formal_runs
```

The plan reports:

- model and defense condition;
- total frozen todo case-runs;
- selected case-runs if `--case-limit` is provided;
- suite counts;
- security case counts;
- output locations for source outcomes and execution manifest.

No model or benchmark service is started in dry-run mode.

## Source outcome execution

Execution must be requested explicitly:

```powershell
python -m experiments.paper_v1.benchmarks.run_injecagent_formal_cell `
  --cell-id injecagent__qwen3_4b_instruct__m3_full__r1 `
  --result-root outputs\paper_upgrade_v1\public_benchmark_formal_runs `
  --execute `
  --backend ollama `
  --prompt-style official_react_simple `
  --max-steps 3
```

This produces:

- `injecagent_official_stage_source/injecagent_outcomes.jsonl`
- `injecagent_official_stage_source/execution_manifest.json`
- `injecagent_official_stage_source/progress.jsonl`
- per-case source job manifests and run logs under
  `injecagent_official_stage_source/jobs/<case_run_id>/`

Partial smoke runs are allowed for debugging with `--case-limit`, but they are
recorded as non-formal.

Resume controls:

- default: resume completed jobs and preserve failed jobs;
- `--no-resume`: clear the progress stream and recompute selected jobs;
- `--retry-failed`: rerun jobs that already have `failure.json`;
- resumed rows in `progress.jsonl` use `resumed_completed` or
  `resumed_failed`, so interrupted runs can be audited without chat history.

## Formal source admission and materialization

Only after the full frozen cell has been executed under a non-stub backend with
an official ReAct prompt style may the source producer request formal-source
admission:

```powershell
python -m experiments.paper_v1.benchmarks.run_injecagent_formal_cell `
  --cell-id injecagent__qwen3_4b_instruct__m3_full__r1 `
  --result-root outputs\paper_upgrade_v1\public_benchmark_formal_runs `
  --execute `
  --backend ollama `
  --prompt-style official_react_simple `
  --formal-source-admission `
  --ingest `
  --materialize
```

Even then, the generic materializer remains the final gate. A cell becomes
result-eligible only after exact frozen todo coverage, completed rows, formal
evidence status, raw runs, metrics, statistics and figure manifest all exist.

## Current status

The script and unit tests are implemented. No full InjecAgent formal cell has
been executed yet in the current result ledger.

Current public benchmark completeness remains:

- expected cells: 60;
- initialized pending cells: 60;
- complete cells: 0;
- expected case-runs: 53,400;
- complete case-runs: 0;
- formal result-completeness gate: `not_satisfied`.
