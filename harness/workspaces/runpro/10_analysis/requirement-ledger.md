# Requirement Ledger

## Requirement R1
### Source
User approved plan, Summary
### Type
Repository
### Requirement
Create local branch `test1` from `origin/team-a/m3-core-day7@2c53f52` and preserve Harness and local materials.
### Status
satisfied
### Satisfaction Evidence
Git HEAD is local branch `test1` at base commit `2c53f52`; Harness files remain present.
### Notes
No remote push requested.

## Requirement R2
### Source
Current user objective
### Type
Harness
### Requirement
Read the AI Agent Harness template and replace generic placeholders with project-specific context, state, boundaries, verification and recovery information.
### Status
satisfied
### Satisfaction Evidence
Project-specific specs, features, tasks, progress, session handoff, requirement lock/ledger and strict audit state now describe the real E0-E17 workflow, safety boundaries, verification and recovery path.
### Notes
The final audit now includes the completed sampled-human E17 contract, final synthesis, statistical validation and Dashboard gate. Corrected E9/E14 and E11 execution-r2 remain the active current-runtime evidence.

## Requirement R3
### Source
User approved plan, Section 1
### Type
Measurement integrity
### Requirement
Classify cases using explicit attack/benign labels so benign cases never enter the attack denominator.
### Status
satisfied
### Satisfaction Evidence
`sample_type` drives all formal denominators; metric tests pass and E0 recomputed the archived 61/8 and 19/5 attack/benign splits.
### Notes
Historical metrics must be recalculated.

## Requirement R4
### Source
User approved plan, Section 1
### Type
Prompt integrity
### Requirement
Remove expected safe behavior, unsafe targets, detector labels and other answer leakage from model-facing prompts.
### Status
satisfied
### Satisfaction Evidence
`runtime_case_view` is an allow-list projection; E0 executed 600 prompt metamorphic leakage checks with 600/600 passing.
### Notes
Attack metadata may remain only in non-model logging context.

## Requirement R5
### Source
User approved plan, Section 1
### Type
Experiment design
### Requirement
Decouple `prompt_profile` from `guard_mode` so prompt hardening and runtime Guard contributions can be isolated.
### Status
satisfied
### Satisfaction Evidence
`run_batch`/`run_matrix` independently accept prompt and Guard axes; six frozen conditions and identity tests pass.
### Notes
Core six conditions must be selectable.

## Requirement R6
### Source
User approved plan, Section 1
### Type
Data contract
### Requirement
Extend AttackCase with sample_type, template_id, split, requires_tool, authorized_actions and mutation_id.
### Status
satisfied
### Satisfaction Evidence
AttackCase v2 schema and the audited canonical 300-case dataset contain all required fields; dataset tests pass.
### Notes
Backward compatibility for legacy cases is required during migration.

## Requirement R7
### Source
User approved plan, Section 1
### Type
Run contract
### Requirement
Extend RunLog and manifest with prompt/Guard axes, modules, replicate, seed, timing, token, model/runtime identity, dataset hash, failure and status fields.
### Status
satisfied
### Satisfaction Evidence
RunLog/schema/manifest include condition, module, replicate, seed, timing, token, hashes, status and failure metadata; schema and core tests pass.
### Notes
Unavailable token metadata must be explicit, not fabricated.

## Requirement R8
### Source
User approved plan, Section 1
### Type
CLI
### Requirement
Batch/matrix execution must support prompt profile, guard mode, temperature, seed, repeats and resumable manifests.
### Status
satisfied
### Satisfaction Evidence
CLI exposes the required axes and atomic per-run checkpoints; composite-key resume and error-retry tests pass.
### Notes
Failed cases may not be silently skipped.

## Requirement R9
### Source
User approved plan, Section 2
### Type
Dataset
### Requirement
Produce approximately 300 cases: 210 attacks across 9 families and 90 benign cases split evenly between no-tool and legitimate-tool tasks.
### Status
satisfied
### Satisfaction Evidence
Canonical dataset audit proves 300=210 attack+90 benign, including 45 no-tool and 45 legitimate-tool cases across nine families.
### Notes
New families: memory poisoning, environment context pollution and cross-tool attack chain.

## Requirement R10
### Source
User approved plan, Section 2
### Type
Dataset split
### Requirement
Use template-level 150/60/90 development/validation/blind-test splits; existing 69 cases belong only to development.
### Status
satisfied
### Satisfaction Evidence
Dataset audit proves dev/validation/blind=150/60/90, zero template crossover and all 69 legacy cases in dev.
### Notes
Thresholds freeze before blind execution.

## Requirement R11
### Source
User approved plan, Section 2
### Type
Defense matrix
### Requirement
Implement the six core conditions and deep ablations: detector only, minus dataflow, minus intent-action, minus structured detector and minus multilingual detector.
### Status
satisfied
### Satisfaction Evidence
`GuardConfig` implements six core conditions, named removals and module overrides; detector-only/policy-only/dataflow identity tests pass.
### Notes
Comparisons must keep all other variables paired.

## Requirement R12
### Source
User approved plan, Section 2
### Type
Models
### Requirement
Run qwen3:4b-instruct, phi4-mini:3.8b, llama3.2:3b and gemma3:4b blind experiments, plus vicuna:7b compatibility baseline.
### Status
satisfied
### Satisfaction Evidence
The four core models and Vicuna compatibility baseline completed the frozen five-model smoke (60/60 cases); the four core models completed the 6,480-run blind main matrix.
### Notes
Use local Ollama only.

## Requirement R13
### Source
User approved plan, E0
### Type
Experiment
### Requirement
Complete metric and label audit, leakage test and historical metric recalculation.
### Status
satisfied
### Satisfaction Evidence
E0 registry status is completed with manifest, raw-log index, audit, corrected metrics, statistics, analysis and inspected PNG/SVG evidence.
### Notes
Must precede effect experiments.

## Requirement R14
### Source
User approved plan, E1-E3
### Type
Experiment
### Requirement
Complete main Guard effectiveness, prompt-hardening-only and Guard incremental-effect paired experiments.
### Status
satisfied
### Satisfaction Evidence
E1-E3 are completed in the registry with bundle manifests, logs, metrics, paired McNemar/bootstrap statistics, analyses and figures; dry-run reconstruction reports zero issues.
### Notes
Prompt/Guard confounding is forbidden.

## Requirement R15
### Source
User approved plan, E4
### Type
Experiment
### Requirement
Complete full component ablation and contribution analysis.
### Status
satisfied
### Satisfaction Evidence
E4 completed 25 conditions and 1,500/1,500 case runs; 25 logs, contribution statistics, confidence intervals, figures and frozen hashes passed validation.
### Notes
Each component must have a directly comparable condition.

## Requirement R16
### Source
User approved plan, E5
### Type
Experiment
### Requirement
Complete cross-model generalization for all four core models and Vicuna compatibility.
### Status
satisfied
### Satisfaction Evidence
E5 is completed across all four core models; Vicuna completed the compatibility baseline, and model/config identities are recorded in the formal manifests.
### Notes
All model/config identities must be recorded.

## Requirement R17
### Source
User approved plan, E6-E8
### Type
Experiment
### Requirement
Complete per-family, multilingual, encoding and evasion robustness experiments.
### Status
satisfied
### Satisfaction Evidence
E6-E8 are completed and registered with all nine attack families plus required language, encoding and evasion variants; bundle artifacts and reconstruction checks pass.
### Notes
Cover all stated languages and perturbations.

## Requirement R18
### Source
User approved plan, E9
### Type
Experiment
### Requirement
Complete 2K/4K/8K/16K context and injection-position 0/25/50/75/100 percent experiments.
### Status
satisfied
### Satisfaction Evidence
The old v3 E9 bundle remains diagnostic-only because its declared context axis collapsed. Context Correction V2 execution-r3 completed 120/120 first-step runs and 8/8 jobs under calibrated native token proof; 15/15 validity checks and 13/13 artifact ledger entries pass. No Guard ASR is 36/60 and full Guard is 0/60, with parse/provider-incomplete outcomes retained. The independent paired audit and atomic registrar passed.
### Notes
Use only execution-r3 for corrected context claims. Do not pool old v3 or superseded r2 cells.

## Requirement R19
### Source
User approved plan, E10
### Type
Experiment
### Requirement
Complete 1/3/5/10-turn delayed, progressive-persuasion and history-poisoning experiments.
### Status
satisfied
### Satisfaction Evidence
E10 is completed for 1/3/5/10 turns and the required delayed, persuasion and history-pollution strategies with turn/trigger metadata in the formal evidence bundle.
### Notes
Turn count and trigger point must be logged.

## Requirement R20
### Source
User approved plan, E11
### Type
Experiment
### Requirement
Complete read-to-send, search-to-API, memory-to-file and tool-output-to-next-action cross-tool chains.
### Status
satisfied
### Satisfaction Evidence
E11 completed all four requested cross-tool chains. After the historical amendment freeze drifted from current runtime, its legacy freeze/results were preserved and execution-r2 was frozen before a fresh 8/8 smoke plus 48/48 formal rerun. The active supplement is registered without pooling or replacing the original E11 primary manifest.
### Notes
Report both step-level and chain-level blocking.

## Requirement R21
### Source
User approved plan, E12
### Type
Experiment
### Requirement
Complete benign no-tool and legitimate-tool utility experiments with TCR, FPR and ASK rate.
### Status
satisfied
### Satisfaction Evidence
E12 is completed for benign no-tool and legitimate-tool tasks with TCR, FPR and ASK reporting; authorized actions are explicit and retained in the audited dataset.
### Notes
Legitimate authorized actions must be explicit in cases.

## Requirement R22
### Source
User approved plan, E13
### Type
Experiment
### Requirement
Calibrate threshold on validation only, output ROC/PR evidence and freeze before blind test.
### Status
satisfied
### Satisfaction Evidence
E13 scanned 5,151 validation-only threshold combinations, froze ASK=1.0 and DENY=1.0 before blind execution, and stores ROC/PR/calibration evidence with the freeze record.
### Notes
Blind test cannot be reused for tuning.

## Requirement R23
### Source
User approved plan, E14
### Type
Experiment
### Requirement
Complete concurrency 1/2/4 and context-length performance measurements for latency, throughput and GPU memory.
### Status
satisfied
### Satisfaction Evidence
The old v3 E14 bundles remain diagnostic-only because their workloads were flat across context labels, and execution-r2 remains diagnostic-only after global run-key collisions. Context Correction V2 execution-r3 completed 104/104 jobs, 432/432 formal and 48/48 warmup runs under calibrated 2K/4K/8K/16K prompts. The final gate passed 144/144 matched benign paths and 480/480 unique first-step keys; Guard p95 is 0.454ms and paired median end-to-end overhead is 0.202% with bootstrap 95% CI -0.577% to 1.374%.
### Notes
E14 is complete and registered. Per-context/concurrency cells have only 12 matched pairs, so their wide uncertainty must remain visible.

## Requirement R24
### Source
User approved plan, E15
### Type
Experiment
### Requirement
Complete representative-case stability across 10 seeds and temperatures 0, 0.2 and 0.7.
### Status
satisfied
### Satisfaction Evidence
E15 completed 3,600 logical stability runs over four models, 30 representative cases, 10 seeds and temperatures 0/0.2/0.7; distribution and flip-rate outputs are registered.
### Notes
Report flip rate, mean and dispersion.

## Requirement R25
### Source
User approved plan, E16
### Type
Experiment
### Requirement
Complete at least three adaptive red-team rounds using prior blocking reasons without leaking blind answers.
### Status
satisfied
### Satisfaction Evidence
E16 completed 42 validation parent attacks across three adaptive rounds (126/126 attempts), nine families, paired statistics and focused-scale figures; one malformed result remains visible in the denominator.
### Notes
Adaptive generation remains local and case provenance must be recorded.

## Requirement R26
### Source
User approved plan, E17
### Type
Experiment
### Requirement
Classify every miss, false positive, ASK and parse failure; perform two-reviewer explanation-quality assessment and agreement reporting.
### Status
satisfied
### Satisfaction Evidence
Two distinct human reviewer identities independently completed the same frozen 360-row packet. Evidence and attestation checks passed; primary plus secondary labels agree 360/360, Cohen's kappa is 1.000 and no third-human adjudication was required. The sampled analysis classifies all 300 representative rows and retains 60 targeted diagnostic rows without pooling them into population estimates.
### Notes
This satisfies the approved 360-row stratified audit protocol, not a 3,299-row full human census. Automated reviews remain diagnostic-only.

## Requirement R27
### Source
User approved plan, Run scale
### Type
Execution scale
### Requirement
Complete Stub all-mode runs, 6480-case core real-model matrix, validation ablations, stability matrix and independent long-context/adaptive/performance suites.
### Status
satisfied
### Satisfaction Evidence
The formal program completed 172 jobs and 15,446/15,446 case runs. Main/derived/stability contain 10,526 audited logical runs; Stub, ablation, stability, context, adaptive and performance submatrices are separately identified.
### Notes
Sharding is allowed; reducing scope is not.

## Requirement R28
### Source
User approved plan, Section 4
### Type
Recovery
### Requirement
Use pending/running/completed/failed registry states; require manifest, logs, metrics, statistics and analysis before completion; repair and rerun failures.
### Status
satisfied
### Satisfaction Evidence
Registry/manifest states, atomic checkpoints, resume/error retry and missing/duplicate detection are implemented and tested. The registry truthfully reports 18 completed / 0 running / 0 failed. E14 r2 demonstrates failure preservation after a final semantic gate, while execution-r3 demonstrates full affected-cell rerun, independent audit and atomic paired registration.
### Notes
No silent retries or omissions.

## Requirement R29
### Source
User approved plan, Statistical methods
### Type
Statistics
### Requirement
Report counts, Wilson 95% CI, McNemar, paired 10,000-bootstrap differences, latency medians/p95/Wilcoxon/effect sizes and Holm correction where applicable.
### Status
satisfied
### Satisfaction Evidence
Final statistical-contract validation passes across admitted E0-E17 evidence: 442 McNemar comparisons, 454 paired 10,000-bootstrap comparisons, 158 Wilcoxon comparisons and 13 Holm-corrected families. E17 additionally uses frozen design weights and a stratified 10,000-repetition percentile bootstrap for its 300 representative rows.
### Notes
Do not make significance-only claims.

## Requirement R30
### Source
User approved plan, Final targets
### Type
Acceptance
### Requirement
Evaluate all stated ASR, DSR, precision/recall, FPR, TCR, ASK, latency/overhead and parse targets truthfully; failures require explicit analysis and cannot be hidden.
### Status
satisfied
### Satisfaction Evidence
Valid target metrics are computed from preserved denominators with counts and uncertainty. The authoritative A00-A11 matrix records 8 pass and 4 fail: malicious-call Recall 525/607=86.49%, TCR drop 6.79 percentage points, legitimate-tool TCR 110/168=65.48%, and worst-cell E14 median E2E overhead 92.43%. Guard p95 remains below target at a worst observed 0.538ms, and A11 parse success is 1529/1568=97.51%. Main-matrix run-level parsing 6025/6480=92.98% remains a separate diagnostic. Old v3 and failed r2 E14 remain quarantined.
### Notes
Targets are evaluation criteria, not guaranteed outcomes.

## Requirement R31
### Source
User approved plan, Test requirements
### Type
Verification
### Requirement
Add unit/integration tests, per-model smoke gates, Stub reproducibility, dataset leakage audit, one-command result rebuild and Dashboard replay verification.
### Status
satisfied
### Satisfaction Evidence
Five-model smoke completed 60/60; Stub semantic reproducibility matched; dataset/leakage/resume/metrics/rebuild/Dashboard tests pass. The final aggregate Harness verifier reports 347 passed, 1 explicit skip and zero verification failures. Sampled E17 weighting, target-stratum exclusion and deterministic bootstrap behavior have dedicated regression tests. Dashboard final evidence validation passes.
### Notes
Skipped checks need explicit justification.

## Requirement R32
### Source
User approved plan, Final delivery
### Type
Delivery
### Requirement
Synchronize Dashboard and the frozen final analysis/figures with final results, complete all Harness gates, commit locally on `test1`, and do not push or open a PR. Do not create PPT, DOCX report or submission ZIP in the current scope.
### Status
satisfied
### Satisfaction Evidence
Dashboard and analysis evidence are synchronized to the completed registry. Formal final analysis contains 13 charts and 63 manifest artifacts; independent statistics and Dashboard gates pass; the portable HTML technical report is generated. PPT/DOCX/ZIP are explicitly not applicable. The final Git action is a local `test1` commit only.
### Notes
Overall engineering acceptance is fail because four targets missed; this is a result verdict, not an incomplete delivery verdict. No push or PR is authorized.

## Requirement R33
### Source
User follow-up, 2026-07-13
### Type
Analysis and visualization
### Requirement
Add a detailed, multi-dimensional analysis of the final experiment results and use appropriate figures such as line charts, bar charts, heatmaps, distribution plots and a limited composition chart where each form matches the analytical question.
### Status
satisfied
### Satisfaction Evidence
The completed final synthesis contains 13 reproducible PNG/SVG figures with source CSVs, figure manifest, layout QA, adjacent interpretation and caveats. It covers defense effect, prompt increment, ablation, cross-model/family/language robustness, context position, multi-turn/adaptive behavior, cross-tool chains, calibration, performance, stability and sampled human failure taxonomy. Main-effect, human-taxonomy and family-heatmap figures passed original-resolution inspection.
### Notes
Old v3 and failed r2 context conclusions remain forbidden. Dense failure composition uses bars/intervals rather than an unreadable donut; the HTML report uses a small acceptance-status pie only for the 8/4 composition.
