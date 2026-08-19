# M3-PI Guard 科学证据 80% 执行计划 v3

## 1. 当前检查点

- 更新时间：2026-07-28
- 状态：`offline_ready_live_primary_canary_confirmation_pending`
- 当前科学证据：753/1200（62.75%，scorecard 显示 63%）
- 目标检查点：968/1200（80.67%）
- 当前论文路线：授权泄漏、授权不确定性与安全—效用权衡的系统实证研究
- 本次更新新增 API、模型或网络调用：0

v3 不修改 v2 历史计划或任何实验冻结。它纠正 v2 计分表中“其他九项”
误写为 620 的算术披露；按当时 scorecard 正确值应为 690。当前 34/34
权威文献元数据和摘要范围审计、稿件结构与中型结果回填已经据实计入
scorecard，但公共、自适应、盲测和第二模型结果仍为零或原有低分。

## 2. 80% 可审计路线

| 工作流 | 当前 | 目标 | 增量 | 准入条件 |
| --- | ---: | ---: | ---: | --- |
| 正式公共基准 | 10 | 100 | +90 | 6,873 条全部终态、ITT 保留、精确身份、独立结果准入和统计重建 |
| 自适应攻击 | 0 | 100 | +100 | 40/20 任务及 hardest-20 扩展全部终态、费用门和独立准入通过 |
| 论文正文 | 45 | 70 | +25 | 公共/自适应结果、摘要、主图表、全文引文语境和完整性复核回填 |
| 其他九项 | 698 | 698 | 0 | 不提前上调 |
| 合计 | 753 | 968 | +215 | 80.67% |

里程碑：

1. 公共基准完整准入后：843/1200（70.25%）。
2. 自适应攻击完整准入后：943/1200（78.58%）。
3. 论文结果与图表完整回填后：968/1200（80.67%）。

独立盲测仍是强外部有效性主张的门禁，机构 JCR/SCIE 核验仍是投稿门禁。
内部 80% 不等于可直接投稿。

## 3. 已完成的离线入口

- Public-v1 已冻结 6,873 条：DeepSeek Pro 5,082 条，Flash 1,791 条；
  24/12 条技术 canary；增量硬熔断 CNY 25；retry、provider tools 和真实
  external effects 均关闭。
- 自适应成本 canary 已冻结 8 个攻击族 × 50 queries，最多 400 queries、
  3,200 provider calls、CNY 5；mutation 只进入 `untrusted_content`，
  query/call 使用双 append-only 台账。
- DeepSeek 证据链要求调用前 fsync 本地 request ID 与规范 payload hash，
  调用后绑定官方 response ID、精确返回模型、usage/cost 和安全回执。
- Gemini 仅保留为免费层、跨提供商增强；现有诊断不进入正式结果。

## 4. 执行顺序与门禁

1. 当前工作树完整 Harness 必须以可恢复日志得到
   `Verification failed=0`。
2. owner 逐字确认已展示的 Public-v1 primary canary 精确命令。
3. 仅生成绑定该确认摘要的 active admission，运行 24 条 Pro 技术 canary。
4. outcome-blind 技术审查通过后，单独冻结并确认 Public Pro continuation。
5. Pro 完整终态后执行 Flash 12 条 canary，再决定 1,791 条 continuation。
6. 公共结果独立准入和统计重建后，另行展示并确认自适应 8×50 命令。
7. 自适应成本 canary 通过后重新投影正式费用；超过 CNY 180 则暂停确认。
8. 只有 public/adaptive result gate 通过，才回填最终 Results、Discussion、
   Abstract 和主图表。

任何 HTTP 429、模型身份漂移、请求链不完整、未知 runner failure、台账
断裂、provider tool/真实外部效果尝试或费用熔断都会立即 fail closed。

## 5. 当前不可替代缺口

- 6,873 条公共扩展尚无正式结果；
- 自适应 40/20 与 hardest-20 尚无正式结果；
- 独立盲测候选与保管人尚未落实；
- 最终全文引文语境、参考文献导出、投稿日版本状态和机构 JCR 核验尚未完成；
- 当前完整 Harness 的最终权威重跑尚未结束。

因此，当前严谨表述只能是 753/1200（62.75%），不能称为 80% 完成。
