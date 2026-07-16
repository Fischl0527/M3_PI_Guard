# Session Handoff

## Last Updated

2026-07-16

## Durable Final State

M3-EXPANSION-001 和 Acceptance Remediation V2 已完成实验、修正和证据阶段，位于本地 `test1`。E0-E17 均为 `completed`；修正前结果保持 8/12，独立 V2 post-hoc engineering remediation 为 12/12 pass。

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
- V2 execution：12/12 jobs、2,160/2,160 logical case-runs；performance replay 144 rows / 12 cells。
- V2 gates：A04 100%；A06 -2.16pp；A07 98.81%；A10 0.009461%；总体 12/12。
- V2 Dashboard：10 metric rows、3,780 logs、4 verified figures、0 warnings。
- V2 evidence boundary：复用原 blind case 的 post-hoc 工程复验，不声称为新的未见盲测。
- Final verifier：361 passed、1 skipped、`Verification failed=0`。
- Historical compatibility：E11 r2 6 个、context/E17 r3 7 个当前源码漂移被精确锁定；旧冻结与 240 个嵌套证据记录通过，当前 V2 27-source freeze 通过。
- Git byte integrity：V2 hash-bound paths 使用 `.gitattributes -text`；index 审计 27/27 frozen sources 和 56/56 evidence references 无 mismatch。

## Remediated Result Misses

- 原四项缺口均已在 V2 中达标：A04 134/134、A06 off 312/324 vs full 319/324、A07 166/168、A10 worst 0.009461%。
- A11 为 1736/1817=95.54%，达到 95% 目标；解析失败仍留在分母。
- V1 首个正式 job 的失败证据保留在独立 invalidated root，不得并入 V2。

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
5. `python -m experiments.acceptance_remediation verify`
6. `python -m experiments.acceptance_remediation_analysis_patch`
7. 阅读 `outputs/experiments/acceptance_remediation_v2/analysis.md`、`acceptance_matrix.csv` 与 4 张图。
