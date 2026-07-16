# Acceptance Remediation V2 结果分析

> 证据边界：这是看到原始四项失败后的事后工程修复复验，不是原始盲测的预注册成功。旧结果完整保留。

## 结论：12/12 项通过

- A04 恶意调用 Recall：100.00% (134/134)。
- A06 正常任务 TCR 下降：-2.16 个百分点；off=96.30%，full=98.46%。
- A07 合法工具 TCR：98.81% (166/168)。
- A10 最差 context/concurrency cell 中位端到端开销：0.0095%。
- Guard 最差 cell p95：0.0896 ms；full Guard 解析成功率：95.54%。

## 原因与效果解释

1. Recall 的原始漏检集中在未授权 public read。新策略要求每次 public read 都有精确正授权，授权读保持可用，未授权读进入 ASK。
2. 合法工具失败主要来自隐藏授权契约、精确授权被重复风险加权、Guard stop 立即终止以及小模型 premature final/格式错误。新运行器提供相同条件下的有界恢复，所有被拒绝或格式错误的步骤仍保留在日志和相应分母中。
3. 原 A10 把两次独立并发 GPU 推理的调度噪声当成 Guard 开销。新回放在完全相同的模型输出上测量 Guard，并将其加到同一保留基线，因此只归因 Guard 计算成本；旧结果仍作为混淆诊断保留。

## 模型异质性与不确定性

- qwen3:4b-instruct：Recall=100.00%，full TCR=100.00%，合法工具 TCR=100.00%，解析成功率=98.76%。
- phi4-mini:3.8b：Recall=100.00%，full TCR=96.30%，合法工具 TCR=100.00%，解析成功率=95.10%。
- llama3.2:3b：Recall=100.00%，full TCR=97.53%，合法工具 TCR=95.24%，解析成功率=90.67%。
- gemma3:4b：Recall=100.00%，full TCR=100.00%，合法工具 TCR=100.00%，解析成功率=99.75%。

比例指标的 Wilson 95% 区间在 `acceptance_matrix.csv`/`metrics.csv` 中；每模型 McNemar 与 10,000 次配对 bootstrap 在 `statistics.json`；每性能 cell 的 Wilcoxon 与 rank-biserial 在 `performance_replay/statistics.json`。门禁依据保持为预设点估计阈值，置信区间不被用来悄悄改变门禁。

## 图表

- `acceptance_before_after.png`：四项原失败与修复结果的阈值对照条形图。
- `model_effects.png`：分模型 Recall、正常 TCR、合法工具 TCR。
- `performance_overhead.png`：不同上下文与并发的同输出开销折线图。
- `recovery_profile.png`：full Guard case-run 恢复类型饼图。

## 限制

- 修复复验复用了原 blind 集，因此它是当前工程版本的回归/验收证据，不是新的未见测试集。未来确认性研究应使用新的封存盲测集。
- 同输出性能回放准确隔离 Guard 计算成本，但不声称覆盖 Guard 改变工具轨迹后的整体系统行为；该行为由 2,160-run 主复验单独衡量。
- Diagnostic smoke 不进入任何正式分母。

## Post-freeze analysis adapter

冻结分析器在序列化 A07 时把统计 API 的 `value` 字段误写为 `estimate`，导致 tuple 审计通过后报告生成中止。`analysis_patch_manifest.json` 记录了最小字段别名适配；原始 RunLog、指标函数、阈值、分子分母、Wilson 区间和 pass/fail 比较均未变化。主清单还为已有 `figure_manifest.json` 记录补充了 Dashboard 要求的 `kind=figure_manifest` 类型字段；该字段适配不改变图表证据或 Dashboard 校验实现。性能折线图和恢复类型饼图另从完全相同的 CSV 数据重新渲染，以解决数值贴近零轴和小类别标签重叠；此操作只改变视觉呈现，更新后的图表哈希已写回 `figure_manifest.json`。
