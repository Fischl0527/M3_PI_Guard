# Public Benchmark Formal Cell Runner v1

## Purpose

This protocol defines the single-cell bridge between frozen public-benchmark
todo queues and formal paper artifacts.

The runner wrapper is:

- `experiments/paper_v1/benchmarks/run_public_benchmark_formal_cell.py`

It does not run Ollama, AgentDojo, InjecAgent, API models, or benchmark
services by itself. It only plans one frozen cell and ingests supplied outcome
JSONL from a separately executed official or disclosed benchmark runner.

## Inputs

Required frozen cell files:

- `outputs/paper_upgrade_v1/public_benchmark_formal_runs/cells/<cell_id>/manifest.json`
- `outputs/paper_upgrade_v1/public_benchmark_formal_runs/cells/<cell_id>/todo_cases.jsonl`

Optional supplied outcome file:

- one JSONL row per attempted case-run from an external runner/scorer;
- rows should identify each case via `case_run_id`, or via
  `benchmark_case_id` + `case_kind` + `replicate_id`;
- formal admission requires a source evidence status from the accepted set:
  - `formal_public_benchmark_case_run`
  - `agentdojo_official_formal_case_run`
  - `injecagent_official_formal_case_run`
  - `public_benchmark_official_formal_case_run`

## Dry-run planning

Use dry-run planning before starting or resuming a cell:

```powershell
python -m experiments.paper_v1.benchmarks.run_public_benchmark_formal_cell `
  --cell-id agentdojo__qwen3_4b_instruct__m3_full__r1 `
  --result-root outputs\paper_upgrade_v1\public_benchmark_formal_runs `
  --preview-limit 5
```

The plan reports:

- benchmark, model and defense condition;
- expected case-run count;
- utility/security counts;
- todo status counts;
- default output paths;
- a small todo preview.

No result files are written by this command.

## Outcome ingestion

After a separately executed official/disclosed runner produces outcome JSONL,
ingest it into standardized case results:

```powershell
python -m experiments.paper_v1.benchmarks.run_public_benchmark_formal_cell `
  --cell-id agentdojo__qwen3_4b_instruct__m3_full__r1 `
  --result-root outputs\paper_upgrade_v1\public_benchmark_formal_runs `
  --outcomes path\to\official_outcomes.jsonl
```

This writes:

- `case_results.jsonl`
- `case_results_validation.json`

Default ingestion is conservative. It does not make rows formal merely because
the wrapper was invoked; diagnostic/stub sources remain diagnostic.

## Formal materialization

Only when the source outcomes are official/disclosed formal runs should formal
admission be enabled:

```powershell
python -m experiments.paper_v1.benchmarks.run_public_benchmark_formal_cell `
  --cell-id agentdojo__qwen3_4b_instruct__m3_full__r1 `
  --result-root outputs\paper_upgrade_v1\public_benchmark_formal_runs `
  --outcomes path\to\official_outcomes.jsonl `
  --admit-formal `
  --materialize
```

The materializer can mark the cell result-eligible only if all frozen todo
case-runs are present, completed and admitted as
`formal_public_benchmark_case_run`.

Missing outcomes are not skipped. They are converted into explicit `missing`
rows and keep the cell at `completed_with_failures`.

## Current status

As of the current audit:

- expected formal cells: 60;
- initialized pending cells: 60;
- complete cells: 0;
- expected case-runs: 53,400;
- complete case-runs: 0;
- formal result-completeness gate: `not_satisfied`.

This protocol therefore enables execution plumbing, not paper-level public
benchmark results.
