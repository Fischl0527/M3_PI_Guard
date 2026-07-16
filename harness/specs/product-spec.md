# Product Specification: M3-PI Guard Experiment Harness

## Product Vision

将 M3-PI Guard 从可演示的本地 Agent 安全原型升级为指标可信、跨模型可复现、可持续断点运行的提示注入行为监督与实验平台，并形成比赛下一阶段可审查的完整证据链。

## Users

- 参赛团队：批量运行攻击、消融、鲁棒性和性能实验，并恢复中断任务。
- 评审与答辩人员：查看原始日志、统计结果、置信区间、攻击链回放和防御原因。
- 开发者：通过 manifest、测试和 Harness 状态文件复现、审计和扩展实验。

## Core Workflows

1. 审计并生成带显式 attack/benign 标签和模板级切分的数据集。
2. 用独立的 prompt profile 与 guard mode 在 Stub 或本地 Ollama 模型上运行矩阵。
3. 记录模型、Guard、性能、随机种子、失败和恢复信息。
4. 计算案例级、调用级、可用性、统计显著性和性能指标。
5. 按 E0-E17 实验注册表持续运行，失败修复后重跑，直至所有验收证据齐全。
6. 在 Dashboard、冻结统计输出和多维图表中呈现真实模型结果，并将 Stub 明确标为回归证据。

## Functional Requirements

| ID | Requirement | Priority | Related Feature |
| --- | --- | --- | --- |
| PRD-001 | 显式区分 attack 与 benign，消除正常样本进入攻击分母的问题。 | Critical | F-EXP-001 |
| PRD-002 | 模型输入不得包含 expected safe behavior、目标动作或检测答案。 | Critical | F-EXP-001 |
| PRD-003 | prompt profile 与 guard mode 可独立配置。 | Critical | F-EXP-002 |
| PRD-004 | 支持模块消融、seed、temperature、repeats、latency 与断点续跑。 | High | F-EXP-002 |
| PRD-005 | 数据集约 300 条，含 9 类攻击、90 条 benign 和模板级 dev/validation/test 切分。 | Critical | F-DATA-001 |
| PRD-006 | 指标覆盖 ASR、UTR、DSR、BSR、TCR、Precision、Recall、F1、FPR、ASK、解析和性能。 | Critical | F-EVAL-001 |
| PRD-007 | 完成 E0-E17 并为每项保存 manifest、日志、指标、统计和图表。 | Critical | F-EXP-003 |
| PRD-008 | Dashboard 能按模型、防御、攻击族、语言和实验批次筛选并回放。 | High | F-DASH-001 |
| PRD-009 | 最终分析、图表与 Dashboard 必须从冻结真实实验结果重建并保持一致。 | High | F-DELIVERY-001 |

## Non-Goals

- 不访问真实邮箱、真实公网业务 API 或真实敏感数据。
- 不执行模型生成的任意代码；`run_code` 保持 mock。
- 不把 Stub 结果包装成真实模型安全效果。
- 不推送远程分支、不创建 PR，除非用户另行授权。
- 当前任务不制作或修改 PPT、DOCX 报告，也不创建提交 ZIP。
- 不用自动代理结果冒充两名真人的 E17 独立盲审。

## User Experience Requirements

- Windows PowerShell 为主要运行环境，同时保留可用的 Python CLI。
- 长实验必须有清晰的状态、可恢复 manifest 和可定位的失败日志。
- 所有图表可追溯到固定数据集哈希、模型标签、配置和原始 RunLog。
- 默认本地运行，遵守原项目安全沙箱边界。

## Open Questions

- 无产品决策类开放问题。E9/E14 execution-r3 已全量完成、通过联合审计并成对登记；唯一外部真实性阻塞项是两名真人完成 E17 独立盲审。自动双复核只作诊断，不能替代真人。
