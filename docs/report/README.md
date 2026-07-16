# 作品报告目录

本目录保留官方模板格式的历史作品报告材料。本轮用户明确不制作或更新 DOCX；当前正式读者报告是 `outputs/experiments/final_analysis/report/report.html`。

- 模板来源：`比赛要求/附件2：作品报告（模板）.docx`
- 终稿目标路径：`docs/report/作品报告_终稿.docx`

## 正式数据边界

终稿中的实验数字、结论和图表只引用：

- `experiments/registry.json` 映射的 E0-E17 完成态 primary bundles（E17 为 sampled human review）；
- `outputs/experiments/program_manifest_final_v3.json`；
- `outputs/experiments/program_final_v3/` 与 `outputs/experiments/blind_freeze_v3.json`；
- `outputs/experiments/E11_posthoc_amendment_v1/` 的 post-hoc 独立补充（仅 `visualization_revision=2`，`pre_registered=false`，不得与原始 E11 pooling）；
- `outputs/experiments/final_analysis/`。

E0 历史指标、Stub、smoke、Day4/Day5/Day7 原型结果必须标明为诊断或回归证据。旧无后缀 `program_final/`、`blind_freeze.json`、v2 根和更早的 `program_v3/` 均已有 invalidation marker；`outputs/experiments/E14_initial_cold_start_diagnostic/` 已被正式双路径暖机批次替代。这些路径不得进入终稿分母，早期 `FPR=0` 也不能作为最终结论复用。

## 同步命令

当前完成态使用 sampled E17 适配入口重建最终综合分析；不要在 E18 已存在时重复 apply E11 registrar：

```powershell
python scripts/freeze_e11_amendment_r2.py --check
python scripts/build_final_analysis_sampled_e17.py --validate-only
python scripts/build_final_analysis_sampled_e17.py --force
python scripts/validate_final_statistics.py --analysis-dir outputs/experiments/final_analysis --out outputs/experiments/final_analysis/statistical_validation.json
```

并使用显式 v3 参数完成结果完整性审计：

```powershell
python agent/result_integrity_audit.py --program-manifest outputs/experiments/program_manifest_final_v3.json --freeze outputs/experiments/blind_freeze_v3.json --thresholds outputs/experiments/E13/frozen_thresholds.json
```

若未来重新授权 DOCX，可由已验综合包和同一批 E0-E17 bundle 生成；当前不执行下列命令：

```powershell
python scripts/build_final_report.py
```

该命令不读取 Day4/Day5/Day7 CSV 或旧图；Stub、smoke 和早期 `FPR=0` 只会作为原型/诊断证据隔离说明，不进入正式摘要、表格或综合图分母。

再验证报告所对应的 Dashboard 数据入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_final_dashboard.ps1 -ValidateOnly
```

当前 HTML 技术报告已经与 `final_analysis/` 同步；DOCX 渲染和逐页检查不适用于本轮交付。
