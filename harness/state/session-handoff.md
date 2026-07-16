# Session Handoff

## Last Updated

2026-07-16

## Durable Final State

M3-EXPANSION-001 已完成实验和证据阶段，位于本地 `test1`。E0-E17 均为 `completed`，没有 running/failed registry 项。最终工程验收状态是 `fail`（8 pass / 4 fail），必须与“执行完成”分开理解。

- Git base：`origin/team-a/m3-core-day7@2c53f52`；本文件及最终有效证据已封装到本地 `test1` 提交，提交哈希以 `git log -1` 为准。
- Registry SHA：`52841155bf90582886145851507885e7f1ff7076de01aeeaad2fe7d1e5efba0f`。
- E17 sampled review：两名真人、每人 360 行、360/360 agreement、kappa=1.000、无 adjudication。
- E17 inference：300 representative rows only；60 targeted rows diagnostic only；没有 3,299 行全量真人审阅声明。
- Final analysis：13 charts、63 manifest artifacts；status completed；acceptance fail。
- Statistical validation：PASS，0 hard failures，0 fallacy failures。
- Dashboard gate：PASS；仅加载固定的 completed evidence roots。
- Tests：最终聚合 verifier 347 passed、1 skipped，Verification failed=0。
- HTML report：`outputs/experiments/final_analysis/report/report.html`；标准构建器 validation/package/structural PASS；浏览器验证受共享阅读器 8px 顶栏溢出限制，详见同目录 `verification.json`。
- E11 execution-r2 freeze：`ceb320a915d301d6658b5caa9b662cb2ed13e24c63ec5d79f8ff7caa9ad0ba37`。
- Runtime：最终交付时 Ollama/Streamlit 应保持停止；服务检查不得调用会自动启动 Ollama 的命令。

## Known Result Misses

- Malicious-call Recall：525/607=86.49%（目标 >=90%）。
- Normal TCR drop：6.79pp（目标 <=5pp）。
- Legitimate-tool TCR：110/168=65.48%（目标 >=90%）。
- Worst E14 cell median E2E overhead：92.43%（目标 <10%）。
- Main-matrix run-level parse：6025/6480=92.98%，作为附加诊断低于 95% 参考；权威 A11 解析口径为 1529/1568=97.51%。

## Boundaries

- 不把自动代理结果或 60 targeted rows 冒充总体真人估计。
- 不覆盖历史 v3、失败 E14 r2、E11 legacy freeze/结果；它们保持 diagnostic provenance。
- 不访问真实 secret，不启动真实邮件/API，不执行模型生成代码。
- 不制作 PPT、DOCX、ZIP；不 push、不建 PR。

## Rebuild And Review

1. `python scripts/build_final_analysis_sampled_e17.py --validate-only`
2. `python scripts/validate_final_statistics.py --analysis-dir outputs/experiments/final_analysis --out outputs/experiments/final_analysis/statistical_validation.json`
3. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_final_dashboard.ps1 -ValidateOnly`
4. 阅读 `outputs/experiments/final_analysis/report/report.html`、`analysis.md` 与 E17 `review/analysis.md`。
