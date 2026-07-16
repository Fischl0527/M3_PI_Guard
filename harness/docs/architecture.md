# M3-PI Guard Experiment Harness Architecture

## Purpose

本仓库在同一版本库内维护两个边界清楚的区域：根目录的 M3 PI Guard 本地安全靶场/实验源码，以及 `harness/` 下的 AI Agent Harness 工程。Harness 记录需求、状态、决策、失败和验收；项目运行代码产生带 manifest 的实验证据，两者通过固定接口协作但不混放源码。

## Runtime Flow

```text
AttackCase JSONL
      |
      v
Experiment Suite / Matrix Runner
      |
      +--> prompt_profile: standard | hardened
      +--> backend: stub | local Ollama
      +--> guard_mode/module ablation
      v
Agent Runner --> Guard --> local mock tools
      |
      v
RunLog + Manifest + Failure Record
      |
      v
Metrics / Statistics / Figures / Dashboard
```

## Module Boundaries

- `m3_attacks` owns source cases, expansion, split metadata and dataset integrity.
- `m3_core` owns model interaction, prompt construction, tool-call parsing and run metadata.
- `m3_guard` owns behavior decisions and module-level ablation; it does not know test answers.
- `m3_eval` owns metric definitions and statistical summaries; it never mutates raw logs.
- `experiments` owns E0-E17 registry, suites, resume rules and completion validation.
- `outputs/experiments` is generated evidence and must remain traceable to source/config hashes.
- `harness/state`, `harness/features`, `harness/specs` and
  `harness/workspaces/runpro` are the durable project control plane.

## State And Recovery

- `experiments/registry.json` is the machine-readable experiment state.
- Each suite writes an immutable configuration snapshot and a resumable manifest.
- A suite is complete only when expected run count equals validated artifacts and statistics.
- Harness state records progress and failures so another session can resume without chat history.

## Safety Boundary

- Model inference is local through loopback Ollama.
- Tools are mock/local only.
- Real secrets, accounts, public endpoints and generated code execution remain out of scope.

## Verification Layers

1. Contract/unit tests.
2. Dataset and label audits.
3. Stub deterministic matrix.
4. Local-model smoke tests.
5. Full experiment registry validation.
6. Requirement-ledger and final-audit validation.
