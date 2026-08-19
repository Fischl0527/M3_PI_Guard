# Task Record: M3-PAPER-001

## Goal

将 M3 PI Guard 升级为面向授权不确定性的、非预知评测框架，并形成可在公共基准、新封存盲测和自适应攻击下验证的论文级证据链。

## Scope

## 2026-07-18 model-store and 8B qualification amendment

- Ollama 活动模型库已经迁移到 `OLLAMA_MODELS` 指定的仓库外目录，迁移前 11 个模型通过两轮重启 smoke；D 盘旧模型目录已删除，程序目录保留。
- Qwen3 8B 与 Llama 3.1 8B 已使用不可漂移本地别名、manifest SHA-256 和模型 blob SHA-256 登记；24/24 资格 smoke 完成但不具备正式结果资格。
- PromptGuard 精确依赖环境、冻结 86M 缓存和 12-case real CUDA qualification smoke 已完成；smoke 仍排除在正式表外，当前阻塞是 tokenizer-aware windowing、正式 manifest 和完整 logs。
- 公共基准 v1 freeze/ledger 保持不可变；v2 新增两个现代 8B 槽并单独初始化 84 cells / 74,760 pending case-runs。

### Allowed

- `m3_core/`、`m3_guard/`、`m3_attacks/`、`m3_eval/` 中新增论文升级模块。
- `experiments/` 中新增 paper-v1 实验注册、公共基准适配、自适应攻击和分析入口。
- `schemas/` 中新增 TaskPolicyManifest、ActionProposal、GuardDecision、ProvenanceEvent 和 paper ExperimentManifest 契约。
- `protocols/paper_upgrade_v1/`、`outputs/paper_upgrade_v1/`、`tests/`、`docs/` 和 `harness/` 对应状态/规范文件。
- 只读下载官方 AgentDojo 与 InjecAgent 源码到隔离的 `external/benchmarks/`，固定版本并记录许可证与提交。

### Forbidden

- 不改写原 E0-E17、Context Correction、E11、E17 真人盲审或 Acceptance Remediation V1/V2 冻结证据。
- 不使用 `authorized_actions`、`requires_tool`、攻击标签、目标动作或 expected answer 生成 paper-v1 的模型输入或在线 Guard 决策。
- 不访问真实邮箱、真实业务 API、真实秘密或非本地工具。
- 不制作 PPT、DOCX、ZIP，不 push、不创建 PR。

## Implementation Plan

1. 新建独立 paper-v1 runtime，保留旧 runtime 仅用于历史证据重建。
2. 实现可信任务策略编译、参数来源追踪、时序约束和 ALLOW/ASK/DENY 监控器。
3. 生成 1,500 条 M3-v2 数据；原 300 条仅作为开发回归来源。
4. 接入 AgentDojo、InjecAgent 和统一 baseline 适配协议。
5. 实现授权不确定性、自适应攻击、论文指标、统计和图表。
6. 冻结后运行本机可用模型；外部 API/服务器任务在缺少凭据时保持 `blocked_external`，不得伪造。

## Acceptance Criteria

- paper-v1 模型输入和在线 Guard 只接收 trusted user task、tool schema、trusted app context、untrusted content 和运行轨迹。
- gold/evaluator authorization 只能存在于离线评分器，并只能作为明确标注的 oracle upper bound。
- M3-v2 为 1,500 条：900 attack、300 benign no-tool、300 benign legal-tool；600/300/600 模板隔离切分。
- 至少生成开发/验证/盲测 hash、数据审计、复现 manifest 和约 500 行分层真人盲审模板。
- 两个公共基准适配器能固定上游版本、列出兼容/不兼容案例并输出统一 AttackCase/任务视图。
- 自适应攻击支持 100/500/2000 查询预算和可恢复状态；测试运行不得默认消耗最高预算。
- 论文分析能生成安全-可用性 Pareto、自适应预算曲线、热力图、授权不确定性曲线、消融森林图、延迟图和失败分类图。
- 历史证据验证继续通过；paper-v1 证据使用独立协议、冻结和输出根。

## Verification

- 先运行新增模块定向测试，再运行现有完整 Harness verifier。
- 数据审计、schema 校验、compile、公共基准版本锁、实验 manifest 完整性和图表来源清单均为硬门禁。
- 任何模型/API/基准失败保留 stderr、状态和原始分母；不得静默跳过。

## Latest Checkpoint — 2026-07-22

- AgentDojo official `tool_filter` has completed its exact 726/726 formal run with 0 failures and has been admitted through the fail-closed analyzer and registry bridge. Together with PromptGuard detector-only formal, the current formal-ready strong-baseline count is 2/5.
- Task Shield v1.3 was explicitly stopped and externally sealed at 42 completed, 1 failed and 683 missing. Its `APITimeoutError` row and all partial artifacts remain unchanged and inadmissible.
- The approved v1.4 operator decision passed, and the fresh two-case qualification completed 2/2 with zero operational failures. Qualification remains diagnostic-only and result-ineligible.
- The v1.4 726-case formal root was explicitly stopped and externally sealed unchanged at 24 completed, 2 failed and 700 missing. Both failures are verifier-invalid-JSON events in assistant content extraction. The 56-file seal inventory SHA-256 is `9a6d9fde53ba80ce83326018563689071cf454dffacd97133ea3cb8e0e76f453`; the root remains permanently inadmissible.
- The v1.5 failure-mode audit passed 8/8 and its separate freeze passed 19/19. The freeze authorized only an exact 12-case expanded qualification, not a 726-case formal run.
- The v1.5 qualification ended 11 completed, 1 failed and 0 missing, with utility success 1/6 and corrected latency p50/p95/max 221.037553/975.990048/1619.386955 seconds. A later source/raw-trace audit proved that stored `attack_success=6/6` was the complement of AgentDojo's official injection-success field; corrected raw Targeted ASR is 0/6. This is still degenerate safety because attack-condition utility is 0/6. An exhausted untrusted assistant timeout escaped fail-closed suppression, the failed outcome omitted its trace and ten scoring-cardinality errors caused fail-closed utility loss. No row was retried/excluded.
- Task Shield v1.6 completed its staged correctness and qualification path. P0/G0 corrected the AgentDojo metric semantics without editing historical rows; P1-P2/G1 added a zero-SDK-retry, full-contract-recovery runtime with terminal failure trace persistence and 32/32 focused tests. Fresh P3 completed 4/4 and passed G2. Fresh P4 retained all 12 terminal rows but had 3 case timeouts, attack-condition utility 0/6 and p95 latency 15.175 times the matched ToolFilter comparator; G3 failed 12/16. P5/P6 are not authorized, Task Shield expansion is stopped as negative engineering evidence, Q2 score change is zero, and the next strong-baseline route is Progent then CaMeL/information-flow. Ollama is stopped and port 11434 is released.
- CaMeL source-backed formal preparation has been upgraded to v1.2: `camel_source_backed_formal_freeze_v1` is schema `paper-camel-source-backed-formal-freeze-1.2`, passes 17/17 checks, hash-binds local adapter files and rejects stale resume roots before Ollama/model probing.
- CaMeL remains engineering readiness only. It still needs a fresh two-case real-model qualification, exact 726-case logs and admitted analysis before it can count as a formal strong baseline.
- Progent source-backed formal preparation has been upgraded to v1.1: `progent_source_backed_formal_protocol_v1.md` is part of the freeze, the common-universe freeze passes 13/13, and the network-free import preflight passes 10/10 while running zero benchmark cases and no model probe.
- The Progent v1.1 runner rejects stale resume roots before Ollama probe by checking freeze SHA-256, runner version, model id, condition id, selected cases and selected-case-row SHA-256. This is engineering readiness only; 2-case real-model qualification and 726-case formal logs are still pending.
- Q2 readiness remains raw 66.0/100 and capped 60.0/100. Hard blockers are unchanged: incomplete public-benchmark matrix, fewer than five strong baselines, missing independent blind, missing two frontier API vendors and missing formal adaptive budget evidence. The read-only `q2_to_80_action_audit_v1` records the five sub-80 caps and next evidence bundles without changing the score.

## Previous Checkpoint — 2026-07-18

- AgentDojo four-suite diagnostic screen completed 124/124 jobs with 0 failures.
- Candidate selection fixed 25 positive baseline-vulnerability clusters and 4 zero-control clusters.
- Selected-cluster repeat completed 174/174 jobs with 0 failures.
- Selected-repeat result: `no_defense` official injection success 72/87; `m3_full` 0/87.
- Stable clusters: 24/29 are stable baseline-positive; all 24 are stable-blocked under `m3_full`.
- Analysis output: `outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_repeat_qwen3_v1/analysis/`.
- Added official AgentDojo prompt-baseline adapters:
  - `agentdojo_repeat_user_prompt`;
  - `agentdojo_spotlighting_with_delimiting`.
- Added prompt-baseline protocol and combined analyzer:
  - `protocols/paper_upgrade_v1/agentdojo_selected_prompt_baselines_v1.md`;
  - `experiments/paper_v1/benchmarks/analyze_agentdojo_prompt_baseline_comparison.py`.
- Prompt-baseline diagnostic completed 174/174 jobs with 0 failures:
  - `agentdojo_repeat_user_prompt`: 66/87 official injection success;
  - `agentdojo_spotlighting_with_delimiting`: 66/87 official injection success.
- Four-condition joined analysis completed 348/348 jobs:
  - `no_defense`: 72/87;
  - repeat-user prompt: 66/87;
  - spotlighting `<< >>`: 66/87;
  - `m3_full`: 0/87.
- Joined analysis output: `outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_prompt_baseline_comparison_qwen3_v1/`.
- InjecAgent official-formula replay scorer added:
  - `experiments/paper_v1/benchmarks/score_injecagent_replay.py`;
  - protocol `protocols/paper_upgrade_v1/injecagent_replay_scoring_bridge_v1.md`;
  - 3-case smoke output `outputs/paper_upgrade_v1/public_replay/injecagent_qwen3_limit3_v1/official_formula_score_v1/`.
- InjecAgent scorer smoke result: `no_defense` and `m3_full` both ASR-all Total 0.0, Valid Rate 100.0. Boundary: not byte-identical official runner execution.
- InjecAgent official-stage diagnostic runner added:
  - `experiments/paper_v1/benchmarks/injecagent_stage_runner.py`;
  - protocol `protocols/paper_upgrade_v1/injecagent_stage_runner_v1.md`;
  - qwen3 data-security limit-2 v3 output `outputs/paper_upgrade_v1/injecagent_stage/qwen3_limit2_v3/`;
  - qwen3 direct-harm limit-2 output `outputs/paper_upgrade_v1/injecagent_stage/qwen3_dh_limit2_v1/`.
- Stage smoke result: both smokes completed with 0 failures; official-formula bridge reports Valid Rate 100.0 and ASR-all Total 0.0 for `no_defense` and `m3_full`.
- Added 5-case diagnostic slices:
  - `outputs/paper_upgrade_v1/injecagent_stage/qwen3_ds_limit5_v1/`;
  - `outputs/paper_upgrade_v1/injecagent_stage/qwen3_dh_limit5_v1/`.
- Limit-5 result: both slices completed with 0 failures; official-formula bridge reports Valid Rate 100.0 and ASR-all Total 0.0 for `no_defense` and `m3_full`. This mainly validates the stage runner and shows weak baseline triggering in the first qwen3 InjecAgent cases; it is not a formal result.
- Added official prompt styles:
  - `official_react`;
  - `official_react_simple`.
- ReAct parser repair: prioritizes `Action` before later `Final Answer`, accepts `None`/no-input action input for parameter-free tools, and suppresses syntax warnings from model-produced backslash escapes.
- Added result-blind InjecAgent stage selection builder, `--selection`, incremental `progress.jsonl`/`runs.jsonl`, `progress_sha256`, `--timeout` and `--max-tokens`.
- Added paired stage analyzer:
  - `experiments/paper_v1/benchmarks/analyze_injecagent_stage_pair.py`.
- Vicuna official_react_simple baseline-vulnerable diagnostic:
  - DS pair output `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_ds_limit3_pair_v1/`: no_defense 3/3, m3_full 0/3.
  - DH pair output `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_dh_limit3_pair_v1/`: no_defense 1/3, m3_full 0/3.
  - Extra DS 0004/0005 no_defense output `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_ds_0004_0005_nodefense_v1/`: ASR-all Total 0.0, retained as negative diagnostic only.
  - Frozen 30-case selection `protocols/paper_upgrade_v1/injecagent_stage_stratified_30_selection_v1.json`; old pre-progress 30-case no-defense attempt stopped and logged because it had no auditable intermediate output.
  - Progress-enabled 6-case stratified pair `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection6_pair_timeout_v1/`: no_defense 1/6, m3_full 0/6, 0 failures.
  - Progress-enabled 30-case stratified pair `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_pair_timeout_v2/`: no_defense ASR-all Total 46.7%, m3_full 0.0%, attack success 14/30 to 0/30, McNemar p=0.0001221, bucket summary and three diagnostic figures generated.
- Policy compiler repaired same-provider read-only over-authorization; product-details tasks no longer authorize saved-address private lookup solely because both tools share the Amazon provider token.
- InjecAgent official compatibility audit added:
  - script `experiments/paper_v1/benchmarks/audit_injecagent_official_compatibility.py`;
  - outputs `protocols/paper_upgrade_v1/injecagent_official_compatibility_audit_v1.json/.md`;
  - 19/19 checks passed;
  - validates pinned official source hashes, official prompted-stage markers, official parser fixed samples, synthetic DH/DS S1/S2 formula expectations and source-order official ReAct prompt rendering.
- InjecAgent official prompted-parser intent scorer added:
  - script `experiments/paper_v1/benchmarks/score_injecagent_stage_official_prompted.py`;
  - no-defense output `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_nodefense_timeout_v2/official_prompted_intent_score_v1/`;
  - `m3_full` output `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_m3full_timeout_v2/official_prompted_intent_score_v1/`;
  - paired output `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_official_prompted_intent_pair_v1/`;
  - raw model attack intent changed only 7/30 to 6/30 while execution-derived attack success changed 14/30 to 0/30, supporting the runtime-monitor framing.
- Strong-baseline registry/audit added:
  - registry `protocols/paper_upgrade_v1/baseline_registry.json` upgraded to `m3-paper-baselines-1.1`;
  - audit script `experiments/paper_v1/benchmarks/audit_baseline_registry.py`;
  - outputs `protocols/paper_upgrade_v1/baseline_registry_audit_v1.json/.md`;
  - 11/11 checks passed;
  - PromptGuard, Task Shield, IPIGuard, Progent, CaMeL/Fides, AgentDojo `tool_filter` and AgentDojo `transformers_pi_detector` now have explicit blocker/plan/exclusion records;
  - Q2 strong-baseline gate remains `not_satisfied`.
- AgentDojo official strong-baseline capability audit added:
  - protocol `protocols/paper_upgrade_v1/agentdojo_official_strong_baselines_v1.md`;
  - script `experiments/paper_v1/benchmarks/audit_agentdojo_official_strong_baselines.py`;
  - outputs `protocols/paper_upgrade_v1/agentdojo_official_strong_baseline_capability_audit_v1.json/.md`;
  - 9/9 checks passed;
  - official source markers for `tool_filter`, `OpenAILLMToolFilter`, `transformers_pi_detector`, `TransformersBasedPIDetector`, the ProtectAI detector, threshold 0.5 and message-mode redaction are present;
  - dependency blockers remain explicit: no OpenAI key/compatible endpoint for official `tool_filter`; no `transformers` and no cached ProtectAI detector for official `transformers_pi_detector`;
  - the audit confirms these two official strong-baseline ids are not silently mixed into M3 local runner conditions.
- External strong-baseline source/readiness registry and audit added:
  - registry `protocols/paper_upgrade_v1/external_strong_baselines_v1.json`;
  - protocol `protocols/paper_upgrade_v1/external_strong_baselines_v1.md`;
  - audit script `experiments/paper_v1/benchmarks/audit_external_strong_baselines.py`;
  - outputs `protocols/paper_upgrade_v1/external_strong_baseline_source_audit_v1.json/.md`;
  - 10/10 checks passed;
  - covers PromptGuard, Task Shield, IPIGuard, Progent, CaMeL and FIDES candidates;
  - records source URLs, remote HEADs where available, dependency probes, blockers and exclusion rules;
  - all entries remain `result_eligible_for_formal_tables=false`.
- Strong-baseline source checkout manifest added:
  - script `experiments/paper_v1/benchmarks/prepare_strong_baseline_source_checkouts.py`;
  - outputs `protocols/paper_upgrade_v1/strong_baseline_source_checkout_manifest_v1.json/.md`;
  - 5/5 checks passed;
  - source-ready entries: PurpleLlama/PromptGuard, IPIGuard, CaMeL and FIDES pinned under ignored `external/baselines/`;
  - this is source preparation only, not a baseline run or formal result.
- Strong-baseline dependency/source snapshot added:
  - script `experiments/paper_v1/benchmarks/build_strong_baseline_dependency_snapshot.py`;
  - outputs `protocols/paper_upgrade_v1/strong_baseline_dependency_snapshot_v1.json/.md`;
  - 5/5 checks passed;
  - records local package availability, PromptGuard model-cache state, adapter-preflight/source-smoke state, expected source-checkout paths and Git HEAD state;
  - current blockers remain explicit: PromptGuard lacks `transformers` and model cache; IPIGuard source-smoke is complete but source-backed official TDG adapter/logs are still missing; CaMeL is selected with source ready but still needs `uv` and frozen interpreter/dependency assumptions; Task Shield/Progent need frozen reproduction semantics.
- PromptGuard detector-only adapter preflight added:
  - protocol `protocols/paper_upgrade_v1/promptguard_detector_adapter_v1.md`;
  - adapter script `experiments/paper_v1/benchmarks/promptguard_adapter.py`;
  - outputs `protocols/paper_upgrade_v1/promptguard_detector_adapter_preflight_v1.json/.md`;
  - status `blocked_missing_dependencies_stub_preflight_only`;
  - stub smoke verifies online-only scan records, forbidden-field exclusion, fallback chunking, thresholding and max-score aggregation; it is not a real PromptGuard model result.
- Task Shield alignment adapter preflight added:
  - protocol `protocols/paper_upgrade_v1/taskshield_alignment_adapter_v1.md`;
  - adapter script `experiments/paper_v1/benchmarks/taskshield_adapter.py`;
  - outputs `protocols/paper_upgrade_v1/taskshield_alignment_adapter_preflight_v1.json/.md`;
  - status `blocked_reproduction_semantics_stub_preflight_only`;
  - stub smoke verifies online-only task-alignment records, runtime action-proposal separation and forbidden-field exclusion; it is not a real Task Shield verifier result.
- IPIGuard TDG adapter preflight added:
  - protocol `protocols/paper_upgrade_v1/ipiguard_tdg_adapter_v1.md`;
  - adapter script `experiments/paper_v1/benchmarks/ipiguard_adapter.py`;
  - outputs `protocols/paper_upgrade_v1/ipiguard_tdg_adapter_preflight_v1.json/.md`;
  - status `ready_for_official_source_smoke`;
  - follow-up official source-smoke `protocols/paper_upgrade_v1/ipiguard_official_source_smoke_v1.json/.md` passed 8/8 checks against the pinned source;
  - stub smoke verifies online-only TDG input packages, tool-node normalization, trusted/untrusted source separation and side-effect risk-edge recording; source checkout/source-smoke are pinned but this is still not an official IPIGuard algorithm result.
- Progent policy adapter preflight added:
  - protocol `protocols/paper_upgrade_v1/progent_policy_adapter_v1.md`;
  - adapter script `experiments/paper_v1/benchmarks/progent_adapter.py`;
  - outputs `protocols/paper_upgrade_v1/progent_policy_adapter_preflight_v1.json/.md`;
  - status `blocked_dsl_semantics_stub_preflight_only`;
  - stub smoke verifies trusted-input-only policy bundles, symbolic allow/ask/deny rule packaging and runtime action checking; it is not a real Progent result.
- CaMeL/FIDES IFC-capability adapter preflight added:
  - protocol `protocols/paper_upgrade_v1/camel_fides_ifc_adapter_v1.md`;
  - adapter script `experiments/paper_v1/benchmarks/camel_fides_adapter.py`;
  - outputs `protocols/paper_upgrade_v1/camel_fides_ifc_adapter_preflight_v1.json/.md`;
  - status `selected_source_ready_dependency_blocked_stub_preflight_only`;
  - CaMeL is selected and source checkout is ready; stub smoke verifies online-only IFC/capability packages, trusted/untrusted source labels, argument provenance, capability grants and low-integrity-to-sink decisions; it is not a real CaMeL result.
- Strong-baseline formal-readiness audit added:
  - script `experiments/paper_v1/benchmarks/audit_strong_baseline_formal_readiness.py`;
  - outputs `protocols/paper_upgrade_v1/strong_baseline_formal_readiness_audit_v1.json/.md`;
  - 7/7 checks passed;
  - records dependency snapshot status `completed` and the dependency snapshot SHA-256;
  - formal-ready strong baselines: none; all required strong baselines remain outside formal result tables until source-backed adapters, dependency snapshots, formal manifests and complete logs exist.
- Public benchmark formal-freeze manifest added:
  - script `experiments/paper_v1/benchmarks/build_public_benchmark_formal_freeze.py`;
  - outputs `protocols/paper_upgrade_v1/public_benchmark_formal_freeze_v1.json/.md`;
  - 9/9 checks passed;
  - freezes AgentDojo 97 utility + 629 security and InjecAgent 1,054 security case universes;
  - declares ready-local public-benchmark matrix as 53,400 case-runs while keeping Q2 public-benchmark gate `not_satisfied`.
- Public benchmark result-completeness audit added:
  - script `experiments/paper_v1/benchmarks/audit_public_benchmark_result_completeness.py`;
  - outputs `protocols/paper_upgrade_v1/public_benchmark_result_completeness_audit_v1.json/.md`;
  - 5/5 checks passed;
  - current gate is `not_satisfied`: 60 expected matrix cells, 60 initialized pending cells, 0 complete cells, 53,400 expected case-runs and 0 complete case-runs.
- Public benchmark formal-run plan / pending ledger added:
  - script `experiments/paper_v1/benchmarks/prepare_public_benchmark_formal_runs.py`;
  - outputs `protocols/paper_upgrade_v1/public_benchmark_formal_run_plan_v1.json/.md`;
  - result-root ledger `outputs/paper_upgrade_v1/public_benchmark_formal_runs/run_plan_manifest.json`;
  - queue `outputs/paper_upgrade_v1/public_benchmark_formal_runs/formal_cell_queue.jsonl`;
  - 60 pending cell manifests and 53,400 per-case todo rows initialized without starting models or marking results eligible.
- Public benchmark formal case-result row builder added:
  - script `experiments/paper_v1/benchmarks/formal_case_result_rows.py`;
  - converts benchmark-specific outcomes into standardized materializer-ready rows keyed by frozen `case_run_id`;
  - keeps diagnostic source rows diagnostic even when conversion is invoked with formal admission.
- Public benchmark formal-cell runner wrapper added:
  - script `experiments/paper_v1/benchmarks/run_public_benchmark_formal_cell.py`;
  - protocol `protocols/paper_upgrade_v1/public_benchmark_formal_cell_runner_v1.md`;
  - dry-runs one frozen cell without starting models or benchmark services;
  - converts supplied official outcome JSONL into standardized `case_results.jsonl` and `case_results_validation.json`;
  - keeps missing outcomes as explicit failed rows and only materializes formal evidence when accepted source status plus explicit formal admission are both present.
- AgentDojo formal-cell source producer added:
  - script `experiments/paper_v1/benchmarks/run_agentdojo_formal_cell.py`;
  - protocol `protocols/paper_upgrade_v1/agentdojo_formal_cell_runner_v1.md`;
  - dry-runs one frozen AgentDojo cell without services;
  - explicit execution writes `agentdojo_outcomes.jsonl`, `progress.jsonl`, execution manifest and per-case native job logs;
  - completed per-case jobs resume by default, existing failures are preserved unless `--retry-failed` is explicit;
  - `agentdojo_official_formal_case_run` is emitted only for full-cell, non-stub, zero-failure runs with explicit formal-source admission.
- InjecAgent formal-cell source producer added:
  - script `experiments/paper_v1/benchmarks/run_injecagent_formal_cell.py`;
  - protocol `protocols/paper_upgrade_v1/injecagent_formal_cell_runner_v1.md`;
  - dry-runs one frozen InjecAgent cell without services;
  - explicit execution writes `injecagent_outcomes.jsonl`, `progress.jsonl`, execution manifest and per-case official-stage source job logs;
  - completed per-case jobs resume by default only when paired `runs.jsonl` exists, existing failures are preserved unless `--retry-failed` is explicit;
  - `injecagent_official_formal_case_run` is emitted only for full-cell, non-stub, zero-failure runs with explicit formal-source admission and official ReAct prompt style.
- Public benchmark formal-cell materializer added:
  - script `experiments/paper_v1/benchmarks/materialize_public_benchmark_formal_cell.py`;
  - enforces exact todo coverage, completed case-runs and `formal_public_benchmark_case_run` evidence status before setting `result_eligible_for_formal_tables=true`;
  - writes per-cell raw runs, metrics, statistics, figure manifest and SHA-256 artifact declarations.
- Focused regression after audit, intent-scorer, baseline-registry, AgentDojo official strong-baseline capability-audit, external strong-baseline source-audit, strong-baseline source-checkout manifest, IPIGuard official source-smoke, strong-baseline dependency snapshot, strong-baseline formal-readiness audit, public-benchmark formal-freeze manifest, public-benchmark formal-run pending ledger, public-benchmark formal case-result row builder, public-benchmark formal-cell runner wrapper, AgentDojo formal-cell source producer, InjecAgent formal-cell source producer, public-benchmark formal-cell materializer, public-benchmark result-completeness audit, PromptGuard adapter-preflight, Task Shield alignment-preflight, IPIGuard TDG-preflight, Progent policy-preflight and CaMeL/FIDES IFC-capability-preflight additions: `python -m pytest tests/unit/test_public_benchmark_adapters.py tests/unit/test_paper_v1_runtime.py tests/unit/test_paper_metrics.py tests/unit/test_paper_matrix.py -q` passed 122/122.
- PromptGuard qualification checkpoint: redacted credential validation, frozen 86M download, hash snapshot and 12-case real CUDA smoke are complete. Diagnostic agreement is 9/12 with one benign false positive and two malicious misses; formal eligibility remains false. The next PromptGuard task is tokenizer-aware 512-token windowing plus frozen M3-v2/AgentDojo/InjecAgent manifests and complete detector logs, not another credential/download attempt.
- Next run: implement the PromptGuard formal detector-only adapter or continue another explicit strong-baseline blocker. Separately, choose between byte-identical InjecAgent prompted/function-calling compatibility and disclosed compatibility-diagnostic expansion beyond 30 cases; IPIGuard needs official TDG construction wired from pinned source; Task Shield/Progent need frozen reproduction semantics before formal use; selected CaMeL needs `uv`, dependency/interpreter assumptions and a source-backed benchmark adapter before formal use.

## Risks

- 当前无前沿模型 API 密钥和外部服务器，因此六模型最终矩阵无法在本机一次性完成。
- 新方法与 Progent、IPIGuard、Task Shield、CaMeL/Fides 存在邻近性；论文不得在系统检索完成前宣称“首次”。
- 自动生成 blind 只能称 sealed automated holdout，不能冒充独立作者生成。


