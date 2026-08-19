# Requirement Lock

## Project Goal

补齐 M3-PI Guard AI Agent Harness，并将 Day7 原型推进为可信、可恢复、完成 E0-E17 的比赛级全量实验项目。

## Final Deliverable

本地 `test1` 分支中的实现、300条审计数据、E0-E17 全部实验与统计证据、多维图表、Dashboard、Harness 完成审计和最终本地 Git 提交。

## Execution Mode

Strict mode

## Expected Genre And Register

可复现实验软件、实验数据与可交互分析证据；所有效果结论必须与真实原始日志和统计证据一致。

## Expected Depth Or Quality Tier

晋级阶段高质量、评审可复核、答辩可解释。

## Target Quality Threshold

90+ plausible internal quality target, subject to truthful experimental evidence.

## All Required Parts Must Be Completed

Yes. E0-E17、测试、统计、多维图表、Dashboard、最终审计与本地提交不可缩减为部分演示。按用户后续明确范围，本任务不制作 PPT、DOCX 报告或提交 ZIP。

## Required Structure Or Sections

Harness 控制面、核心代码、数据集、实验注册表、原始证据、指标统计、多维图表、Dashboard、最终审计。

## Required Format Or Template

沿用 Day7 既有代码架构；实验工作文件、冻结证据、图表和 Dashboard 留在项目输出与 Runpro 分析目录。既有 DOCX/PPTX/ZIP 只作为保留材料，不在本任务中创建、修改或打包。

## Explicit Formatting Requirements

Dashboard 与图表不含误导性工作流文本；表格/图表可读、标注完整并引用实验 ID；旧无效指标必须更正或明确标为早期原型。

## Default Formatting Fallback

静态图表同时导出 PNG、SVG 与数据 CSV，使用克制配色、诚实坐标、可读图例和明确样本/分母；Dashboard 提供对应筛选与原始证据回放。

## Non-Negotiable Requirements

- attack/benign口径正确且无标签泄漏。
- prompt与Guard正交配置。
- 约300条、9攻击族、90 benign、模板级切分。
- 四个核心本地模型盲测和Vicuna兼容性实验。
- E0-E17全部有manifest、日志、指标、统计及需要的图表/分析。
- 失败、超时、拒答、解析错误不从分母静默删除。
- 最终材料与验证结果同步。
- E17 必须由两名真人独立盲审；自动双复核仅作诊断，不可冒充真人结果。

## Explicitly Forbidden Moves

- 访问真实secret、真实邮件或公网业务API。
- 执行模型生成代码。
- 使用Stub结果冒充真实模型效果。
- 查看盲测后重新调阈值并仍称为盲测。
- 隐藏失败或在未完成时标记verified。
- 未经新授权推送远程或创建PR。
- 伪造真人盲审、读取后代填或将自动代理复核登记为真人 E17。

## Accepted Inferences

无固定截止日期；本地模型顺序运行；使用断点和跨会话持续执行；模型下载是批准范围内的正常实施步骤。

## Personal Identity Fields

沿用现有材料中的已提供字段；空白身份字段不编造并保持空白。

## Open Questions Needing Confirmation

None.

## Locked Execution Direction

先修复测量基础与 Harness，再扩展数据和测试，随后完成 Stub、真实多模型和多维套件；完成双代理自动诊断和两名真人 360 行分层抽样盲审后登记 E17，冻结生成最终分析、审计并提交本地 `test1`。该方向已执行完成，结果目标允许如实为 fail。

## Approval Status

Approved

## User Confirmation Record

2026-07-13: 用户明确发送“PLEASE IMPLEMENT THIS PLAN”，随后要求读取本仓库 Harness、补充完整并按计划持续到完成。

2026-07-14: 用户进一步锁定“双代理自动复核后两名真人盲审”，并明确“不用做 PPT”“先不做 DOCX 报告，也不做提交 ZIP”；随后要求先忽略真人文件，把其余可运行工作全部完成。

2026-07-16: 用户确认已完成最后的真人评审并要求完成最后工作；两份 360 行真人结果通过身份、证据、完整性和一致性校验。
