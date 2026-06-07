# M3_PI_Guard System Architecture

## Overview

M3_PI_Guard is a local LLM Agent safety range. It evaluates whether an Agent can be induced to perform unsafe tool calls, and whether a guard layer can block or route those calls before execution.

The system has four main modules:

```text
AttackCase JSONL
      |
      v
m3_core Agent Runner
      |
      +--> llm_client: stub or local Ollama backend
      |
      +--> guard_engine: baseline, keyword_only, policy_only, full_guard
      |
      +--> tool_sandbox: local mock tools only
      |
      v
RunLog JSONL / CSV
      |
      v
m3_eval metrics and dashboard
```

## Core Runtime

`m3_core` owns the local Agent execution path:

- `llm_client.py` supports a deterministic `stub` backend and a local Ollama OpenAI-compatible backend.
- `agent_runner.py` builds the task context, parses ToolCall JSON, invokes guard decisions, and writes step-level RunLog entries.
- `tool_sandbox.py` implements local-only mock tools: `read_file`, `write_file`, `send_email`, `call_api`, `run_code`, and `final`.
- `run_batch.py` and `run_matrix.py` provide repeatable experiment execution for one or more defense modes.

## Attack Dataset

`m3_attacks` and `fixtures` provide the local test inputs:

- AttackCase JSONL files are grouped by family.
- The full case file contains 69 cases.
- Demo and representative case files provide smaller reproducible subsets.

## Guard Layer

`m3_guard` provides behavior-level supervision before tool execution:

- `detector.py` identifies suspicious instructions and sensitive data-flow patterns.
- `policy_engine.py` maps tool calls and context into allow, ask, or deny decisions.
- `dataflow.py` tracks whether untrusted content attempts to influence protected actions.
- `guard_engine.py` exposes the stable `guard_decide(context, tool_call)` interface and supports ablation modes.

## Evaluation Layer

`m3_eval` summarizes logs into metrics and dashboard views:

- `evaluate.py` reads RunLog JSONL files or log directories and writes CSV/JSON summaries.
- `metrics.py` computes attack success, unauthorized tool use, data spill, block success, false positives, and risk-score summaries.
- `dashboard.py` provides a local dashboard view for demonstration.

## Safety Model

The project is intentionally local-only:

- Ollama calls are restricted to loopback endpoints.
- Email sending writes JSONL records to `sandbox/outbox`.
- API calls return mock JSON.
- Code execution is disabled and returns a fixed mock observation.
- Model files, real secrets, runtime outbox records, and sandbox logs are excluded from release packages.
