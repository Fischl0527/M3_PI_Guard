# AgentDojo selected-cluster official prompt baseline diagnostic v1

## Purpose

This diagnostic adds pinned AgentDojo prompt-style baselines to the exact
selected clusters from `agentdojo_four_suite_screen_selection_v1`.

It is not formal benchmark evidence.  It exists to answer one narrow
engineering question before a frozen public-benchmark protocol:

> On clusters where the local model shows measurable baseline vulnerability,
> do AgentDojo's official prompt baselines reduce injection success, and how do
> they compare directionally with the M3 runtime monitor?

## Boundary

- Evidence status: `diagnostic_not_formal_benchmark`.
- Result-table eligibility: false.
- Source selection:
  `protocols/paper_upgrade_v1/agentdojo_four_suite_screen_selection_v1.json`.
- Base selected repeat to compare against:
  `outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_repeat_qwen3_v1/manifest.json`.
- The prior selected repeat supplies `no_defense` and `m3_full`.
- This protocol supplies only the official prompt baselines to avoid rerunning
  already completed local-model trajectories.

## Baselines

The pinned AgentDojo checkout exposes these official defenses in
`external/benchmarks/agentdojo/src/agentdojo/agent_pipeline/agent_pipeline.py`:

- `repeat_user_prompt`;
- `spotlighting_with_delimiting`;
- `tool_filter`;
- `transformers_pi_detector`.

This diagnostic implements the first two in the local
`M3AgentDojoPipeline` message loop:

- `agentdojo_repeat_user_prompt`: appends the raw original user query after
  tool observations, matching AgentDojo's `ToolsExecutionLoop([ToolsExecutor,
  InitQuery(), llm])` behavior.
- `agentdojo_spotlighting_with_delimiting`: appends the official system
  instruction and wraps rendered tool observations in `<<...>>`.

`tool_filter` is not included because the pinned AgentDojo implementation only
supports OpenAI-style tool-calling models.  `transformers_pi_detector` is not
included in this local prompt-baseline diagnostic because it is an
input-detector strong baseline, not a prompt-baseline condition. Its ProtectAI
dependency now has a separate offline smoke, but any formal result still
requires a frozen full AgentDojo official cell.

## Planned run

Run only the two prompt baselines:

```powershell
python -m experiments.paper_v1.benchmarks.agentdojo_selected_matrix `
  protocols/paper_upgrade_v1/agentdojo_four_suite_screen_selection_v1.json `
  --output-dir outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_prompt_baselines_qwen3_v1 `
  --backend ollama `
  --model qwen3:4b-instruct `
  --temperature 0 `
  --seed 20260718 `
  --max-steps 12 `
  --attack important_instructions `
  --repeats 3 `
  --defenses agentdojo_repeat_user_prompt,agentdojo_spotlighting_with_delimiting
```

Expected size:

- 29 selected clusters;
- 2 official prompt baselines;
- 3 repeats;
- total 174 jobs.

## Analysis rule

Do not feed this manifest directly into the two-condition selected-matrix
analyzer.  Use a combined analyzer that joins:

1. `selected_repeat_qwen3_v1` for `no_defense` and `m3_full`;
2. `selected_prompt_baselines_qwen3_v1` for
   `agentdojo_repeat_user_prompt` and
   `agentdojo_spotlighting_with_delimiting`.

The combined analysis must report:

- per-suite injection success with Wilson 95% intervals;
- per-cluster stability for all four conditions;
- paired McNemar tests for each prompt baseline versus no defense;
- paired McNemar tests for M3 full versus each prompt baseline;
- a diagnostic bar chart with all four conditions;
- explicit diagnostic watermark and result-table ineligibility.

## Completion criteria

This diagnostic is complete only when all 174 prompt-baseline jobs complete
without unexplained failures and the combined comparison produces manifest,
CSV, JSON, and PNG/SVG chart artifacts.

## Execution result

Status: completed.

- Prompt-baseline manifest:
  `outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_prompt_baselines_qwen3_v1/manifest.json`.
- Prompt-baseline jobs: 174/174 completed, 0 failed.
- `agentdojo_repeat_user_prompt`: 66/87 official injection success.
- `agentdojo_spotlighting_with_delimiting`: 66/87 official injection success.
- Combined comparison output:
  `outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_prompt_baseline_comparison_qwen3_v1/`.
- Combined comparison: 348/348 joined jobs from two manifests.
- Four-condition official injection success:
  - `no_defense`: 72/87;
  - `agentdojo_repeat_user_prompt`: 66/87;
  - `agentdojo_spotlighting_with_delimiting`: 66/87;
  - `m3_full`: 0/87.
- The combined figure was visually checked and retained with a diagnostic
  watermark.

This result remains diagnostic-only because the selected clusters are enriched
for baseline vulnerability and do not represent the full AgentDojo task
distribution.
