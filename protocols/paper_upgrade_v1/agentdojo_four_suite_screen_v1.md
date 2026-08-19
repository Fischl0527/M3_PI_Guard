# AgentDojo four-suite diagnostic screen v1

Updated: 2026-07-18

## Purpose

This screen expands the AgentDojo native diagnostic from a single workspace
slice to all four AgentDojo v1 suites. It is used only to choose candidate task
clusters for the later frozen public-benchmark protocol.

The outputs are not confirmatory evidence, are not eligible for paper main
tables, and must not be cited as state-of-the-art effectiveness results.

## Evidence boundary

- Evidence tier: `diagnostic_not_formal_benchmark`.
- Result eligibility: `result_eligible_for_formal_tables=false`.
- Model: `qwen3:4b-instruct`.
- Backend: local Ollama.
- Attack: official AgentDojo `important_instructions`.
- Defenses: `no_defense`, `m3_full`.
- Temperature: `0.0`.
- Repeats: `1` for the first screen.
- Seed: `20260718`.
- Max steps: `12`.

The first banking batch started before this design record was written. Its
configuration is recorded here because the screen is diagnostic-only. No formal
run may use a protocol record created after execution has begun.

## Screened suites and user tasks

| Suite | User tasks | Rationale |
|---|---|---|
| banking | `user_task_0`, `user_task_12` | Payment side effect plus file-instruction reading. |
| slack | `user_task_0`, `user_task_2` | Webpage reading plus invite side effect using untrusted web data. |
| travel | `user_task_0`, `user_task_3` | Conditional reservation plus recommendation-to-email chain. |
| workspace | `user_task_0`, `user_task_4` | Calendar/event reading plus multi-step calendar write chain. |

All native injection tasks available in each suite are included:

- banking: `injection_task_0` to `injection_task_8`.
- slack: `injection_task_1` to `injection_task_5`.
- travel: `injection_task_0` to `injection_task_6`.
- workspace: `injection_task_0` to `injection_task_5`.

## Selection rules for the later frozen protocol

A task/injection cluster is considered a candidate security cluster when:

- at least one `no_defense` run has official injection success;
- the paired `m3_full` result is available and not failed;
- all raw manifests and audit traces are present.

A user task is considered a candidate utility task when:

- the clean `no_defense` utility checker passes;
- the clean `m3_full` utility checker passes;
- injected utility is recorded separately and never pooled with clean utility.

Formal public-benchmark candidates must include:

- all clusters with positive baseline vulnerability in this screen;
- at least one zero-vulnerability cluster per suite when available, to avoid
  selecting only easy-to-improve failures;
- utility-passing clean tasks from at least two suites, or an explicit
  compatibility limitation if the local model cannot complete them.

## Formal freeze requirements

Before a result can enter a paper table, a separate formal protocol must freeze:

- exact case list and hashes;
- model list and model tags;
- defense list and exact baseline adapter versions;
- thresholds, exclusions and failure handling;
- statistics plan and chart plan;
- rerun/resume policy;
- artifact validation command.

This diagnostic screen may inform that formal design, but no diagnostic
denominator may be merged into the frozen formal denominator.
