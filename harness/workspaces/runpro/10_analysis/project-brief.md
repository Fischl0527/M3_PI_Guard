# Project Brief

## Goal

构建并验证比赛级 M3-PI Guard 全量实验平台。

## Deliverable

可运行代码、M3-PI-300 数据、E0-E17 证据包、统计/图表、Dashboard、Harness 审计和本地 Git 提交。

## Execution Mode

Strict mode.

## Strict-Mode Trigger Basis

任务包含大规模真实模型实验、冻结盲测、统计结论、可执行代码、真人盲审和明确完成承诺；错误、证据漂移或虚假完成声明会直接破坏实验可信度。

## Expected Genre And Register

安全工程实验平台与可审计分析证据；结论必须基于可追溯真实实验，语言准确、克制、可复核。

## Expected Depth Or Quality Tier

晋级后高质量提交，目标为评审可复现、答辩可解释、指标定义可审计。

## Target Quality Threshold

在可控范围内达到 90+ plausible 的内部质量档位，不承诺外部评分。

## All Required Parts Must Be Completed

Yes. E0-E17、代码、数据、统计、图表、Dashboard、Harness 审计和本地提交均为必须项；PPT、DOCX 报告和提交 ZIP 已被用户明确移出当前范围。

## Audience

比赛评审、答辩专家、参赛团队开发者和实验复现者。

## Confirmed Requirements

以 Day7 为基线、创建 test1、保留原始材料、修复可信度问题、构建约300条数据、完成本地多模型与多维实验、失败修复后复跑、最终不推送。

## Required Structure Or Sections

Harness 状态层；源码与测试；数据集；E0-E17 注册表；原始日志/manifest；统计与图表；Dashboard；最终审计。

## Required Format Or Template

保持既有 DOCX/PPTX/ZIP 原样，不在当前任务中制作或修改；新增实验结果以冻结输出、图表和 Dashboard 交付。

## Explicit Formatting Requirements

图表和 Dashboard 必须清晰、可追溯，标明实验来源、样本/分母、估计值、置信区间和限制，不混入 Stub 或失效原型结论。

## Constraints

本地 Ollama、8GB 显存、Mock 工具、安全数据、顺序 GPU 执行、无远程推送。

## Assumptions

无固定截止时间；模型下载网络可用；长时运行可通过断点机制跨会话继续。

## Open Questions

两名真人 E17 盲审尚未完成，这是当前唯一外部阻塞项。

## Completion Standard

E0-E17 全部 completed 且产物齐全；测试/审计通过；最终分析、图表与 Dashboard 同步；requirement ledger 与 final audit 无可修复缺口；本地 `test1` 提交成功。
