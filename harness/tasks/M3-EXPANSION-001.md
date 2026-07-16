# Task M3-EXPANSION-001

## Goal

Deliver the fully executed and truthfully evaluated M3-PI Guard experiment expansion on local branch `test1`.

## Milestones

- 2026-07-13：创建 `test1`，完成规格、需求锁、E0-E17 registry 与验证脚手架。
- 2026-07-14：执行 v3 program、统计/图表基础设施和 Dashboard QA；语义审计重开 E9/E14。
- 2026-07-15：execution-r3 从空目录完成 E9/E14 修复、冻结、联合审计和原子登记；重建 corrected E17 source。
- 2026-07-16：完成 E11 execution-r2 8/8 smoke、48/48 formal、分析和登记；生成 360 行双真人分层抽样包。
- 2026-07-16：两名真人各完成 360 行，360/360 agreement、kappa=1.000；登记 sampled E17。
- 2026-07-16：重建 13 图 final analysis，独立统计与 Dashboard 门禁 PASS，50/50 测试文件通过。

## Final Verification

```text
Registry: PASS; 18 completed, 0 running, 0 failed
E17 humans: PASS; 2 x 360 rows; 360/360 agreement; kappa 1.000
Final analysis: PASS; 13 charts; 63 manifest artifacts
Independent statistics: PASS; 0 hard failures; 0 fallacy failures
Dashboard evidence gate: PASS
Tests: PASS; aggregate verifier 347 passed; 1 skipped; verification failures 0
E11 execution-r2 freeze: PASS; ceb320a915d301d6658b5caa9b662cb2ed13e24c63ec5d79f8ff7caa9ad0ba37
```

## Result Decision

Experiment/evidence execution is complete. Engineering acceptance is fail: malicious-call Recall 86.49%, normal TCR drop 6.79pp, legitimate-tool TCR 65.48%, and worst-cell E14 median E2E overhead 92.43% miss their thresholds.

## Handoff

Create a local `test1` commit only. Do not push, create a PR, or produce PPT/DOCX/ZIP.
