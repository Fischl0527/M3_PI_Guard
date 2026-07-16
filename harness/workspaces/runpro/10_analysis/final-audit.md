# Final Audit

## Audit Scope

Strict final audit of local branch `test1`, M3-PI-300, E0-E17 registry, corrected/frozen evidence, sampled two-human E17 review, statistics, 13-chart synthesis, Dashboard, Harness state and local Git handoff. PPT, DOCX and submission ZIP are excluded by user direction.

## Completion Decision

Evidence review complete and approved for the final local commit. Experiment execution is complete; engineering acceptance is **fail** because four predeclared targets were not met.

## Decision Rationale

Every E0-E17 registry item is completed and has admitted evidence. The two required humans completed the same 360-row frozen packet and agreed on all reviewed fields. Final analysis, independent statistical recomputation, Dashboard source gate and the complete repository test inventory pass. No running or unexplained failed task remains.

The result cannot be called an engineering target pass: A04, A06, A07 and A10 failed. Those misses are preserved in the final matrix, report and figures.

## Strict Validation Chain

- Registry：PASS，18 completed / 0 running / 0 failed；SHA `52841155bf90582886145851507885e7f1ff7076de01aeeaad2fe7d1e5efba0f`。
- E17 identity/completeness：PASS，2 distinct humans × 360 rows；evidence/attestation preserved。
- E17 agreement：PASS，360/360，kappa=1.000，adjudication=not required。
- E17 inference boundary：PASS，300 representative rows weighted；40+20 targeted rows diagnostic only；no 3,299-row census claim。
- E11 execution-r2 freeze：PASS，SHA `ceb320a915d301d6658b5caa9b662cb2ed13e24c63ec5d79f8ff7caa9ad0ba37`。
- Final input admission：PASS，E0-E17 exact sequence，1,364 input artifacts，E11 denominators not pooled。
- Final analysis：PASS，status completed，13 charts，63 manifest artifacts。
- Independent statistical validation：PASS，0 hard failures，0 statistical-fallacy failures。
- Dashboard final evidence gate：PASS，corrected E9/E14 and sampled E17 roots admitted；legacy/superseded roots rejected。
- Tests：PASS，final aggregate verifier 347 passed，1 skipped，0 failed；Verification failed=0。
- Visual inspection：PASS for main defense, human taxonomy and family robustness; family heatmap colorbar overlap repaired before final rebuild.
- Portable HTML：canonical validation/package/structural PASS；browser QA limitation recorded separately because the shared reader top bar causes an 8px Windows scrollbar overflow.

## Acceptance Matrix Summary

| Target | Observed | Threshold | Verdict |
| --- | ---: | ---: | --- |
| ASR relative reduction | 99.21% | >=70% | pass |
| Full-Guard DSR | 0/432 | ==0 | pass |
| Malicious-call Precision | 525/529 = 99.24% | >=90% | pass |
| Malicious-call Recall | 525/607 = 86.49% | >=90% | **fail** |
| Benign call FPR | 4/146 = 2.74% | <=5% | pass |
| Normal TCR drop | 6.79pp | <=5pp | **fail** |
| Legitimate-tool TCR | 110/168 = 65.48% | >=90% | **fail** |
| Benign ASK rate | 20/324 = 6.17% | <=10% | pass |
| Guard p95 | worst 0.538ms | <10ms | pass |
| Median E2E overhead | worst E14 cell 92.43% | <10% every cell | **fail** |
| ToolCall parse success | 1529/1568 = 97.51% | >=95% | pass |

E13 threshold freeze is also pass, yielding 8 pass / 4 fail across A00-A11. DSR=0 has a nonzero Wilson upper bound and is not proof of zero future risk. Main-matrix run-level parse 6025/6480=92.98% and E9 unresolved 14/120 remain explicit secondary limitations.

## Human Review Findings

Raw representative counts are leak 112, none 91, ask 50, other 17, parse_failure 17, false_block 7, max_steps 6 and timeout 0. Design-weighted point estimates place leak at 34.29% and none at 34.06%; the remaining categories have wider uncertainty. Targeted rows are useful for diagnosis but never enter these population shares.

## Source And Claim Integrity

Current context claims use corrected execution-r3, current E11 supplement claims use execution-r2, and sampled E17 claims use the completed review manifest. Old v3 current-source hash drift, failed E14 r2 and E11 legacy evidence remain visible as diagnostic provenance. No threshold was retuned on blind results, no failed outcome was removed, and no automated review was represented as human.

## Final Format Check

Active deliverables are Python source/tests, JSON/JSONL/CSV evidence, PNG/SVG figures, Markdown analysis, a Streamlit/Plotly evidence Dashboard and a self-contained HTML technical report. No PPT, DOCX or ZIP was created.

## Git Decision

Status/diff and whitespace audit passed, and this final state is contained in one local `test1` commit. Do not push and do not create a PR.
