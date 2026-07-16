# Final Summary

## Completion Status

Completed for local evidence delivery. E0-E17 are 18/18 completed, two-human sampled E17 is finalized, final analysis and Dashboard evidence gates pass, and all 50 test files pass. The engineering acceptance result is fail with 8/12 targets passed; that result is not hidden or reclassified as incomplete execution.

## Delivered State

- Audited 300-case dataset, orthogonal prompt/Guard runtime, resumable manifests, failure-preserving metrics and paired statistics.
- Corrected current-runtime context evidence: E9 120/120 and E14 432 formal + 48 excluded warmup.
- E11 execution-r2: 8/8 smoke and 48/48 formal under freeze `ceb320a9...ba37`.
- E17: two distinct humans, 360 rows each, 360/360 agreement, kappa 1.000, no adjudication.
- E17 scope: 300 representative weighted rows plus 60 diagnostic targeted rows; no full 3,299-row human-census claim.
- Final synthesis: 13 reproducible chart families, 63 manifest artifacts, 1,364 admitted input artifacts.
- Independent statistics PASS and Dashboard final evidence gate PASS.
- Final aggregate Harness verifier: 347 passed, 1 skipped, 0 failed; Verification failed=0.
- Self-contained HTML technical report plus Markdown analyses, CSVs and PNG/SVG figures.
- PPT, DOCX and ZIP not produced; no push or PR.

## Main Findings

Full Guard reduces overall ASR by 99.21% and observes DSR 0/432 while keeping malicious-call Precision at 99.24% and benign call FPR at 2.74%. However, malicious-call Recall is 86.49%, normal TCR falls 6.79pp, legitimate-tool TCR is 65.48%, and the worst E14 cell has 92.43% median E2E overhead. These four target misses define the next engineering priorities.

The human audit's 300-row representative cohort contains 112 leak and 91 none labels. Design weighting estimates leak at 34.29% and none at 34.06%; uncertainty is especially wide for sparse classes. Agreement is perfect within this sample, but sample agreement does not prove the taxonomy is exhaustive or the full 3,299-item population has been manually reviewed.

## Final Handoff

Use `outputs/experiments/final_analysis/report/report.html` as the reader-facing technical report, `outputs/experiments/final_analysis/analysis.md` for detailed synthesis, and `scripts/run_final_dashboard.ps1 -ValidateOnly` before any later Dashboard launch. Final Git action is a local `test1` commit only.
