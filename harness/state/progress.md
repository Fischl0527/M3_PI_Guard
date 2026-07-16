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

修正前基线为 8 pass / 4 fail：Recall 86.49%、正常 TCR 下降 6.79pp、合法工具 TCR 65.48%、最差 E14 cell 端到端中位开销 92.43%。该历史结果和原始分母保持不变。

Remediation V2 最终验收为 12 pass / 0 fail：A04 Recall 134/134=100%；A06 off 312/324、full 319/324，full Guard 没有造成下降而是改善 2.16pp；A07 合法工具 TCR 166/168=98.81%；A10 12 个同输出反事实性能 cell 中最差中位可归因开销 0.009461%。A11 解析成功率 1736/1817=95.54%，其余预设门禁也全部通过。

## Git Handoff

已审计提交文件，排除 `models/`、`.tmp.driveupload/`、实验工作分片和非本任务 sandbox 临时内容，并运行 Git whitespace/status 检查。最终状态包含在本地 `test1` commit 中；默认不 push、不建 PR。

## 2026-07-16 Acceptance Remediation

- 目标保持为修复并重新验证 A04、A06、A07、A10，只有四项和总门禁均通过才完成。
- 已定位：A04 的 76 个攻击 FN 全是未授权 public read；A06/A07 同时受到授权契约未暴露、Guard stop 立即终止、精确授权邮件被重复风险惩罚和 premature final 影响；A10 被并发 GPU 的独立推理配对噪声混淆。
- 已实现第一轮通用修复并完成 57 项目标单测；48-run diagnostic smoke 表明 public-read Recall 可修复，但发现授权邮件被 `intent_action` 重复加权、两个小模型在 API 调用前提前 final。
- 正在实现第二轮：精确授权免除重复 intent mismatch、premature-final 有界恢复；诊断输出明确排除在正式证据之外。
- 下一门禁：目标单测、第二轮 smoke、post-hoc engineering remediation 协议冻结、四模型完整 blind 复验、同输出 E14 replay、最终 12/12 重建。

### V1 invalidation and V2 restart

- V1 same-output replay passed A09/A10, but its first completed Qwen main job exposed FPR=87.88%、Precision=3.33%、ParseSuccess=91.74%；known-failing V1 process was stopped after 1/12 completed jobs and retained as excluded diagnostic evidence.
- Cause: exact authorized safe first steps in attack-chain cases were re-penalized by document-level detector signals. Policy/dataflow had already validated the action itself.
- Fix: exact authorized action suppresses document detector deltas only; off-target, dataflow, sensitive and later malicious calls remain fully evaluated. Regression suite is now 66 passed.
- Full 90-case Qwen pre-freeze diagnostic after the fix: Precision=100%、Recall=100%、FPR=0%、TCR=100%、legal-tool TCR=14/14、ParseSuccess=99.25%。
- V2 protocol/output/freeze are independent of V1 and must rerun all 2,160 formal case-runs plus the 144-row performance replay.

### Remediation V2 final

- V2 已从零完成四模型、三种 seed、off/full 的 12/12 jobs 和 2,160/2,160 logical case-runs；144-row、12-cell 同输出性能 replay 完整。
- 冻结源验证通过；所有失败、ASK、超时、解析失败和恢复步骤保留在原始分母。V1 保持明确 invalidated，不进入 V2 分母。
- `acceptance_matrix.csv` 为 12/12 pass；Dashboard 二次验证为 10 metric rows、3,780 logs、1 manifest、4 figures、0 warnings。
- 两项报告层兼容适配及两张图的可读性重绘均由独立哈希清单披露；RunLog、指标、阈值、分子分母、置信区间和 pass/fail 比较未改动。
- 4 张 PNG/SVG 图表及来源 CSV 已生成并完成原分辨率视觉检查；性能折线和恢复环形图解决了近零压缩与标签重叠问题。
- 最终 Harness verifier：361 passed、1 skipped；Harness/源码边界、JSON、PowerShell/Bash 语法、compile、Registry complete、历史证据兼容性和当前 V2 27-source freeze 全部 PASS，`Verification failed=0`。
- 历史 E11 r2 与 context/E17 r3 冻结未改写；兼容性清单精确登记 6/7 个当前源码漂移，并核验 240 个历史嵌套 evidence records。当前验收结论只使用独立 V2 冻结。
- Git 字节一致性审计通过：路径级 `.gitattributes -text` 消除了 Windows autocrlf 对冻结字节的隐式改写；Git index 中 V2 27/27 source records 与 56/56 result/figure/raw references 均逐字节匹配声明 SHA-256。
