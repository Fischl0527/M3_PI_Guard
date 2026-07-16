# Progress

## Current Status

E0-E17 已全部完成并登记，Registry 为 18 completed / 0 running / 0 failed。E17 两名真人各完成 360 行冻结分层抽样盲审，360/360 一致且无需裁决。正式综合分析、13 张图、独立统计复算、Dashboard 最终证据门禁和便携 HTML 技术报告均已生成或验证。

## Completed

- Harness 工程与项目源码已物理分区：Harness 在 `harness/`，M3 运行/实验源码在根目录的 `m3_*`、`experiments/`、`protocols/`、`scripts/`、`tests/`。
- 300 条审计数据、五模型 smoke、四模型 6,480 主矩阵、完整消融、E9/E14 corrected r3、E15 3,600 稳定性、E16 三轮自适应攻击和 E11 execution-r2 均完成。
- E17：两个不同真人 reviewer_id，各 360 行；证据列原样保留；一致率 100%，kappa=1.000。
- E17 总体估计只使用 300 representative 行；40 disagreement-targeted 与 20 rare/complex-targeted 行保持独立诊断边界。
- `final_analysis`：13 图、63 个 manifest 工件、1,364 个 admitted input artifacts；E11 post-hoc 明确 `pre_registered=false` 且不合并分母。
- 独立统计验证 PASS；Dashboard `-ValidateOnly` PASS。
- 图表已检查并修复 family heatmap 颜色条遮挡；主效应、失败分类和攻击族热力图均完成原分辨率检查。
- 最终聚合 Harness verifier：347 passed、1 skipped，Verification failed=0。
- HTML 技术报告含 23 blocks、3 charts、6 metrics、3 tables；validation/package/structural verification PASS，并单独记录共享阅读器浏览器 QA 限制。
- 未制作 PPT、DOCX 或 ZIP；未 push、未创建 PR。

## Final Acceptance

12 项预设目标中 8 pass / 4 fail。四个失败是 Recall 86.49%、正常 TCR 下降 6.79pp、合法工具 TCR 65.48% 和最差 E14 cell 的端到端中位开销 92.43%。这些是真实结果缺口，已保留原始分母、置信区间和来源，不影响“实验与证据流程已完成”的判断。

## Git Handoff

已审计提交文件，排除 `models/`、`.tmp.driveupload/`、实验工作分片和非本任务 sandbox 临时内容，并运行 Git whitespace/status 检查。最终状态包含在本地 `test1` commit 中；默认不 push、不建 PR。
