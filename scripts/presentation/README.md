# 最终答辩 PPT 构建入口

该目录提供一个严格的模板继承流程。它使用 `docs/presentation/Redteam_LLM_Security_答辩PPT.pptx` 作为唯一视觉模板，通过 JavaScript ES module 与 `@oai/artifact-tool` 复制并编辑继承对象，不使用 `python-pptx`，不直接修改 OOXML，也不覆盖源 deck。

## 叙事与页面映射

答辩目标是让评审相信：M3-PI Guard 的结论来自冻结、跨模型、可审计的真实实验，而不是早期 Stub 演示。

- 1：完成态 E0-E17 的三项验收指标摘要。
- 2、3：背景与威胁模型，保持源页。
- 4：数据审计、阈值冻结、顺序运行、统计与交付证据链。
- 5：300 条数据、九类攻击、90 条正常任务和模板级切分。
- 6：主防御效果与提示/Guard 增量。
- 7：Guard 消融与验证集阈值冻结。
- 8：跨模型与分攻击族泛化。
- 9：语言/规避与多轮/自适应趋势。
- 10：性能边界与 E17 人工裁决失败分类。
- 11：创新点，保持源页。
- 12：验收状态、A11 与主矩阵全条件解析口径的区分、step-row/run-level 解析完整性、E16 沙箱运行时与独立分母限制、旧 Stub/FPR=0 的证据定位和收束结论。

页面 6-10 使用 `final_analysis` 中已经生成并具备 SHA-256 的 PNG，不在 PPT 代码中重算指标。`context_position_trends` 与 `random_stability` 仍保留在最终分析与 Dashboard，未因 12 页篇幅而从证据包删除。

第 13 张综合图 `cross_tool_chain_patterns` 也有意不塞入 12 页答辩 deck：它用两个独立面板披露原始冻结 v3 E11 与 `E11_POSTHOC_AMENDMENT_V1` visualization revision 2 的范围差异，补充面板明确 `pre_registered=false`，原始与补充分母不得 pooling。revision 1 的图表因原分辨率 footer/x-label 重叠已归档并禁止准入。该图完整进入正式报告与 Dashboard；省略只针对 PPT 的篇幅和信息密度，不是删除或弱化证据。PPT 不得据此把 post-hoc 补充描述成原始预注册 E11 结果。

## 合成预览

在正式实验运行期间，只生成外部临时目录中的合成预览：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/presentation/build_final_presentation.ps1 -Mode Preview
```

预览图表和封面均明确标注 `SYNTHETIC PREVIEW`，只用于模板、字体、裁切、重叠和 12 页节奏检查，不得作为结果交付。

## 正式构建

E0-E17 全部完成并生成 `outputs/experiments/final_analysis` 后运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/presentation/build_final_presentation.ps1 -Mode Final
```

正式模式在读取图表前执行以下门禁：

1. Registry 必须是严格有序的 E0-E17 且全部 `completed`。
2. `final_analysis/manifest.json` 必须是完成态 E18 formal synthesis，并绑定当前 Registry SHA-256。
3. 对 manifest 的全部 artifact 和 selected figure 的 CSV/PNG/SVG 重新检查字节数与 SHA-256。
4. 三个封面指标只来自 `executive_summary.json` 的 A01、A02、A05。
5. `result_integrity_audit.json` 必须是 main/derived/stability 三阶段通过态；`main_parse_quality.json` 必须绑定同一审计 SHA-256，`e16_provenance.json` 必须证明两个日志字段中的沙箱运行时为同一非空值且 E16 不进入主矩阵。
6. 源 PPTX 与正式输出必须是不同路径。

正式 E18 manifest 同时保存 `e11_scope_boundary`，并对 post-hoc supplement 及其输入 ledger 进行哈希绑定。虽然 deck 不选用第 13 张图，报告和 Dashboard 的准入链仍会复验该边界与全部补充证据。

默认正式输出为 `docs/presentation/Redteam_LLM_Security_final_experiments.pptx`，不会覆盖模板。

## 自动 QA

每次构建都会在系统临时目录完成并保留：

- 完整模板 inspect、12 页 starter 预览和 layout JSON；
- frame-map validator；
- Artifact Tool 预导出逐页 PNG、layout JSON 与 montage，并对预览的 1-12 页做独立完整性门禁；
- template fidelity；
- 最终导出 PPTX 经 `render_slides.py` 回读后必须恰好得到连续的 1-12 页，QA contact sheet 只使用这组最终回读 PNG；
- `slides_test.py` 的画布越界检查；
- deck build manifest、输入/输出 SHA-256 与选用图表清单。

最终交付前必须逐页打开构建 JSON 中 `final_render_dir` 指向的 `slide-*.png` 做全尺寸目检；预导出 preview 仅作辅助交叉检查，contact sheet 只能用于整体节奏检查。
