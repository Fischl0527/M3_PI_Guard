# Source-Claim Integrity Audit

Current scope includes code/data/Dashboard and a dated interim technical report. Claims are audited against local frozen experimental evidence, not bibliographic prose; the report is explicitly non-final.

## Claim C1

### Draft Location

Final analysis main-defense tables/figures and Dashboard KPIs.

### Claim

Full Guard effectiveness must be reported only from the paired real-model blind matrix under the same prompt and configuration identity.

### Claim Type

Empirical comparative claim.

### Source Support

`outputs/experiments/program_manifest_final_v3.json`, frozen main RunLogs, E1/E3 metrics and paired McNemar/bootstrap statistics. E9/E14 are not sources for this claim.

### Support Verdict

pass

### Evidence Boundary

Stub and invalidated program roots are excluded; E11 post-hoc supplement is not pooled.

### Required Repair

None before E17; the formal final-analysis renderer must continue using frozen sources.

### Notes

Report counts, effect sizes and confidence intervals rather than significance-only claims.

## Claim C2

### Draft Location

Dataset/model coverage tables and Dashboard filters.

### Claim

The formal program covers 300 audited cases, nine attack families, four core blind-test models and a Vicuna compatibility smoke baseline.

### Claim Type

Provenance and coverage claim.

### Source Support

Canonical dataset audit, model inventory, five-model smoke manifests, final program manifest and freeze.

### Support Verdict

pass

### Evidence Boundary

Vicuna is a compatibility baseline, not part of the four-model blind main denominator.

### Required Repair

None.

### Notes

Keep model tags/digests and dataset hash visible in machine-readable evidence.

## Claim C3

### Draft Location

Limitations and parser/failure analyses.

### Claim

Known target misses and unresolved outcomes remain in the original denominator and are separated from security effects.

### Claim Type

Limitation and measurement-integrity claim.

### Source Support

Final integrity audit, parse diagnostics, E16 bundle and valid metric/statistics tables; `agent/audits/context_experiment_validity.json` defines the E9/E14 exclusion boundary.

### Support Verdict

pass

### Evidence Boundary

Malicious-call Recall is 525/607=86.49%, TCR drops 6.79 percentage points, legitimate-tool TCR is 110/168=65.48%, and run-level ToolCall parse success is 92.98%; E16 retains one malformed result. Old E9/E14 context results are not interpretable target evidence.

### Required Repair

None by denominator manipulation; final analysis must state the limitations explicitly.

### Notes

These are observed results, not permission to retune the blind test. Corrected E9/E14 are reported only under execution-r3 identity; the failed r2 E14 is not admitted.

## Claim C3A

### Draft Location

E9 long-context analysis and any context-position figures.

### Claim

Old v3 E9 does not support a 2K/4K/8K/16K long-context robustness claim.

### Claim Type

Experimental-validity limitation.

### Source Support

`agent/audits/context_experiment_validity.json` and old v3 first-step token/parse records.

### Support Verdict

supported

### Evidence Boundary

Declared 2K has a 6,310-token median; declared 4K/8K/16K all record 8,192 prompt tokens, with 0/30 parse success in each collapsed cell.

### Required Repair

Create a new protocol/freeze and rerun every E9 cell with token-calibrated workloads and probe-verified context aliases.

### Notes

Keep old v3 immutable as diagnostic provenance; do not promote its ASR/parse outcomes to long-context safety conclusions.

## Claim C3A2

### Draft Location

`interim-progress-report-2026-07-15.md` and the interim MCP technical report.

### Claim

Corrected E9 execution-r3 completes 120 formal first-step runs; No Guard ASR is 36/60 and full Guard ASR is 0/60 under calibrated 2K/4K/8K/16K prompt targets.

### Claim Type

Corrected empirical comparative claim.

### Source Support

`outputs/experiments/E9_context_correction_v2_r3/manifest.json`, `validity_checks.json`, `context_position.csv`, `statistics.json`, the 13-entry artifact ledger, `freeze_r3.json` and the joint audit.

### Support Verdict

pass

### Evidence Boundary

15/15 validity checks pass; 14 parse failures and 6 provider-incomplete cases are retained. Each context-position-condition cell has only three attacks, so cell-level Wilson intervals are wide. This does not revalidate old v3 or generalize beyond the frozen Qwen configuration.

### Required Repair

None. The paired audit and atomic registrar passed; E9 is registry-complete.

### Notes

Use protocol identity `CONTEXT_CORRECTION_V2` and execution revision `r3` on every corrected E9 claim.

## Claim C3B

### Draft Location

E14 latency/throughput/GPU analysis and performance-by-context figures.

### Claim

Old v3 E14 does not support performance scaling claims by context length.

### Claim Type

Experimental-validity limitation.

### Source Support

`agent/audits/context_experiment_validity.json`, old `outputs/experiments/E14/performance.csv`, failed r2 evidence and admitted execution-r3 evidence.

### Support Verdict

blocked

### Evidence Boundary

Old prompt-token medians are identical at 2K/4K/8K/16K for each defense condition (off=486.5; full_guard=230.5), so the old workload ratio is 1.0. E14 r2 later completed but failed global run-key uniqueness. Only execution-r3 supports current performance claims.

### Required Repair

None for execution-r3. Keep old v3 and failed r2 diagnostic-only.

### Notes

Execution-r3 completed 432 formal + 48 excluded warmups, 144/144 matched pairs and 480/480 unique first-step keys. Its overall paired median overhead is 0.202% with bootstrap 95% CI -0.577% to 1.374%; per-cell small-n uncertainty remains explicit.

## Claim C4

### Draft Location

E17 failure taxonomy and final synthesis.

### Claim

Formal E17 explanation-quality and failure classification require two independent real human blind reviews.

### Claim Type

Review-provenance claim.

### Source Support

User scope lock, E17 source index and identity-aware registration rules.

### Support Verdict

blocked

### Evidence Boundary

Two distinct humans completed the same frozen 360-row sampled packet and passed identity, evidence, attestation and completeness checks. Primary plus secondary labels agree 360/360 and kappa is 1.000. Only the 300 representative rows enter design-weighted population estimates; 60 targeted rows stay diagnostic. Automated 3,299-item reviews remain explicitly ineligible as human evidence.

### Required Repair

No repair required. No third-human adjudication was triggered because there were no disagreements.

### Notes

This is a sampled audit, not a claim that all 3,299 items received human review.
