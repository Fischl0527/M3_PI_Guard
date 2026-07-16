# Technical Specification

## Stack

- Language: Python 3.10+
- Runtime: Windows PowerShell and CPython
- Model runtime: local Ollama OpenAI-compatible endpoint on loopback only
- Core dependencies: `openai`, `pandas`
- Optional UI: Streamlit and Plotly
- Test framework: Python `unittest`/`pytest`-compatible tests
- Build tool: no compiled build; Python import/compile and smoke tests are the build gate
- Deployment target: local authorized security range only

## Project Structure

- `m3_core/`: Agent loop, model client, batch/matrix orchestration and manifests.
- `m3_guard/`: normalizer, detectors, policy, dataflow and Guard interface.
- `m3_attacks/`: source case families, generators and dataset audits.
- `m3_eval/`: metrics, statistics, plots and Dashboard.
- `schemas/`: AttackCase, RunLog and ToolCall contracts.
- `experiments/`: E0-E17 registry, suites and reproducible orchestration.
- `tests/`: unit and integration verification.
- `outputs/experiments/`: generated manifests, logs, metrics, statistics and figures.
- `harness/state/`, `harness/features/`, `harness/specs/`,
  `harness/workspaces/runpro/`: durable Harness and completion state.

## Architecture Constraints

- Model-facing prompt contains only task and untrusted content required for execution.
- `prompt_profile` and `guard_mode` are orthogonal configuration axes.
- Baseline and guarded comparisons must use the same case, model, prompt profile, seed and generation parameters.
- Stub is deterministic regression infrastructure, not experimental evidence about model safety.
- Dataset threshold tuning uses validation only; blind-test configuration is frozen before execution.
- Generated output never replaces source cases or silently drops failures.
- Context-length experiments must calibrate against observed model `prompt_tokens`, not whitespace counts or declared labels. Each target cell must fall within the protocol tolerance, workloads must increase strictly, and collapsed/truncated cells fail semantic validity.
- Do not assume `extra_body.options.num_ctx` on the OpenAI-compatible Ollama path creates an effective per-request context axis. Corrected E9/E14 use separately named Modelfile aliases (4K/8K/16K/32K) or another independently probe-verified mechanism.
- Any correction to a frozen experiment uses a new protocol, freeze and output root. Old v3 E9/E14 stay immutable as diagnostic provenance and cannot be cited as formal context evidence.

## Commands

```powershell
python -m unittest discover -s tests -v
python -m compileall m3_core m3_guard m3_attacks m3_eval experiments tests
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl --stats outputs/metrics/final_case_stats.json --audit outputs/metrics/final_case_audit.json
python -m experiments.run_suite --suite stub_all
python -m experiments.validate_registry
```

Full verification:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/verify.ps1
```

The Bash wrapper remains supported and auto-discovers the Windows Python interpreter when invoked from WSL/Git Bash:

```powershell
bash harness/scripts/verify.sh
```

## Data And API Contracts

- AttackCase required experimental fields: `sample_type`, `template_id`, `split`, `requires_tool`, `authorized_actions`, `mutation_id`.
- RunLog required experimental fields: `prompt_profile`, `guard_mode`, `guard_modules`, `replicate_id`, `seed`, timing fields and token counts when available.
- Manifest required fields: experiment/suite IDs, Git commit, dataset hash, model tag, Ollama version, parameters, expected/completed case counts, failures and status.
- Allowed experiment status values: `pending`, `running`, `completed`, `failed`.

## Security Constraints

- Ollama endpoint must resolve to localhost/loopback.
- `send_email` writes only to local outbox; `call_api` returns mock data; `run_code` never executes generated code.
- No real credentials or model blobs are committed.
- Logs redact canary values in previews and reports.

## Performance Constraints

- Guard-only p95 target below 10 ms.
- End-to-end Guard overhead target below 10% for comparable paired runs.
- GPU experiments run sequentially on the available 8 GB device; concurrency experiments are explicitly bounded.
- E14 context cells must vary the actual prompt workload materially and strictly; changing only a context label/configuration is invalid. Performance reports must include observed prompt-token distributions alongside latency, throughput and GPU memory.

## Observability

- Every run records dataset/model/config identity, per-step outcomes, parse diagnostics and timing.
- Registry and manifests are resumable and never silently omit failed cases.
- Completion claims are backed by Harness state, test output and requirement-ledger evidence.
- E9/E14 completion additionally requires the context semantic-validity audit to pass; artifact hashes alone are insufficient.
- The 4K/8K/16K/32K Qwen aliases passed one-token context probes. Context Correction V2 execution-r3 then completed E9 120/120 and E14 432 formal plus 48 excluded warmups, passed the independent paired audit, and was atomically registered; only execution-r3 may support corrected context claims.
