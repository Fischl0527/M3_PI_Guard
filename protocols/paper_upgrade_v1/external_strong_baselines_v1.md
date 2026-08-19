# External strong-baseline protocol v1

Updated: 2026-07-20

## Purpose

This protocol defines the source and readiness boundary for external strong
baselines required by the paper-v1 upgrade:

- PromptGuard / Llama Prompt Guard 2;
- Task Shield;
- IPIGuard;
- Progent;
- one information-flow or capability baseline, currently CaMeL or FIDES.

This protocol is a source/readiness gate. It only admits results within the
explicit table scope declared by each baseline.

## Current source registry

The machine-readable registry is:

`protocols/paper_upgrade_v1/external_strong_baselines_v1.json`

The corresponding audit output is:

- `protocols/paper_upgrade_v1/external_strong_baseline_source_audit_v1.json`
- `protocols/paper_upgrade_v1/external_strong_baseline_source_audit_v1.md`

The audit must pass before any formal external-baseline run.

## Evidence boundary

Only PromptGuard currently has a completed formal result, and its allowed scope
is detector performance only:

- eligible: detector Precision, Recall, F1, FPR and detector latency;
- ineligible: end-to-end agent ASR, TCR, legal-tool utility, tool-call success,
  security-utility Pareto comparisons and SOTA/strongest-baseline claims.

All other external-baseline entries remain
`result_eligible_for_formal_tables=false`. Source audits, dependency snapshots,
adapter preflights and smoke tests may only support readiness statements until
their own frozen source-backed runs exist.

## Source status by baseline

| Registry key | Current source status | Formal status |
|---|---|---|
| `promptguard` | Frozen 86M revision downloaded; real CUDA 12-case smoke completed; source-backed detector-only formal run completed on 3,280 frozen detector inputs. | Formal-ready for detector-performance tables only. Overall Recall 24.58%, FPR 0.00%, Precision 100.00%, median/p95 latency 17.384/47.167 ms; not eligible for end-to-end ASR/TCR/tool-utility claims. |
| `task_shield` | ACL 2025 paper and DOI registered; v1.3 disclosed reproduction freeze and qualification are complete; v1.4 failure-recovery freeze now hash-binds an explicit verifier transport timeout retry patch. | Formal 726-case AgentDojo run under `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13` is still live but has a failed case (`agentdojo:v1:slack:user_task_18`, `APITimeoutError`). This root is not admitted. The v1.4 protocol is only prepared engineering evidence until a fresh qualification, exact fresh 726-case root, complete logs, statistics and analyzer admission exist. |
| `ipiguard` | EMNLP 2025 paper, GitHub commit and local ignored source checkout registered; official source-smoke plus source-backed adapter/freeze are implemented. | Blocked: first runtime qualification failed on upstream DAG schema output; fresh v1.1 qualification and formal logs are absent. |
| `progent` | Official source checkout pinned; common-726 v1.1 freeze, import preflight, runner and analyzer are implemented. | Blocked: no real-model qualification, complete 726-case logs or admitted analysis. |
| `camel_or_fides` | CaMeL selected as the primary IFC/capability candidate; CaMeL/FIDES checkouts registered; CaMeL source smoke, isolated runtime preflights and v1.2 freeze are complete. | Blocked: no real-model qualification, complete 726-case logs or admitted analysis. |

## Minimum requirements before formal eligibility

Every external strong baseline must have all of the following before it may
enter formal paper tables:

1. Exact source identity:
   - official paper/model-card URL;
   - code repository URL if available;
   - immutable commit hash or release tag if code is used;
   - local source hash after checkout/vendor.
2. Dependency snapshot:
   - Python executable and version;
   - package versions;
   - model IDs, model hashes and cache paths;
   - API provider/model labels if an API model is used;
   - GPU/CPU placement.
3. Adapter protocol:
   - online inputs allowed;
   - fields explicitly forbidden online;
   - tool-schema mapping;
   - prompt/verifier/model settings;
   - thresholds;
   - failure handling;
   - incompatible task exclusion rules.
4. No-label-leakage audit:
   - no attack labels;
   - no target actions;
   - no expected tool answers;
   - no per-case `authorized_actions`;
   - no evaluator checker results.
5. Frozen run manifest:
   - benchmark cases;
   - model/backend;
   - defense condition;
   - seeds/repeats;
   - stdout/stderr/log paths;
   - source/dependency hashes.
6. Complete raw logs and statistics:
   - no silent skip of parse failures, ASK, DENY, refusal or timeout;
   - paired statistics generated from the frozen manifest only.

## Baseline-specific next actions

### PromptGuard / Llama Prompt Guard 2

Recommended next action:

1. Keep the selected 86M model revision, source hashes, frozen detector inputs,
   threshold and complete raw logs immutable as v1.
2. Use the v1 result only in detector-performance tables:
   - 3,280 cases;
   - 2,583 malicious / 697 benign;
   - TP 635, FN 1,948, FP 0, TN 697;
   - Recall 24.58%, FPR 0.00%, Precision 100.00%, F1 39.47%;
   - median / p95 per-case latency 17.384 / 47.167 ms.
3. Cite result artifacts from
   `outputs/paper_upgrade_v1/baselines/promptguard_detector_formal_v1/analysis/`.
4. If calibration or alternative thresholds are explored, create a v2 protocol
   before reading the new v2 results; do not overwrite the v1 freeze.

### Task Shield

Recommended next action:

1. Preserve and continue read-only monitoring of the v1.3 formal root:
   `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`.
2. The current monitor reports `running_with_failures_requires_attention`
   because `agentdojo:v1:slack:user_task_18` failed with `APITimeoutError`.
   Treat this as an operational failure, not an effect result.
3. Do not restart, patch, retry only the failed case, admit or exclude partial
   results while the run is active; monitor output is operational metadata only.
4. The v1.4 failure-recovery protocol is prepared at
   `protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v14.json/.md`
   with runner/runtime patch files under `experiments/paper_v1/benchmarks/`.
   It only addresses verifier transport timeout retry logging and remains
   non-result evidence until it is run from a fresh root.
   The current read-only decision package is
   `protocols/paper_upgrade_v1/execution/taskshield_v14_recovery_decision_v1/`;
   it records `can_start_v14_qualification_now=false` while v1.3 is still live.
   Future operator approval must be represented by
   `taskshield_v14_operator_decision.approved.json` and must pass
   `validate_taskshield_v14_operator_decision`; the current validator output is
   `blocked_not_approved_to_start_v14`.
5. A future Task Shield formal result requires an explicit recovery decision,
   fresh v1.4 two-case qualification, exact 726/726 frozen coverage, zero
   unexplained failures, complete raw logs, statistics, figures and formal
   analyzer admission before setting
   `result_eligible_for_formal_tables=true`.
6. Keep the older v1.2/v1.3 roots as historical/operational evidence; v1.4 is
   a separate disclosed compatibility protocol, not an in-place mutation.

### IPIGuard

Recommended next action:

1. Clone or vendor the observed commit into `external/baselines/ipiguard`.
2. Identify the exact TDG construction entry point.
3. Build a read-only adapter that derives graph inputs from trusted task and
   tool schema only.
4. Run a compatibility smoke before any effectiveness experiment.

### Progent

Recommended next action:

1. Continue searching for official source before formal freeze.
2. If no source is available, define a disclosed DSL subset and reproduction
   protocol.
3. Freeze policy-generation inputs and fallback semantics.
4. Audit that policy generation is non-oracle.

### CaMeL or FIDES

Recommended next action:

1. Run small source-inspection checkouts only after confirming disk budget.
2. Prefer the candidate that can support AgentDojo and M3-v2 without offline
   labels and with complete raw logs.
3. Freeze capability/label lattice and incompatible task rules.

## Current decision

The Q2 strong-baseline gate remains `not_satisfied`: the registry-wide formal
ready count is still below the required five strong baselines. AgentDojo
`tool_filter` and PromptGuard are formal-ready within their declared scopes, but
Task Shield v1.3 is still live but currently blocked by one failed timeout row;
v1.4 is prepared but not qualified or admitted. The other external baselines
are not yet formal-admitted.

The external baselines are now better specified than before: source candidates,
blocker classes and PromptGuard's detector-only result boundary are known.
