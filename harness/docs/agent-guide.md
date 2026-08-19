# 智能体指南

本指南说明 AI 编程智能体应如何在本仓库内工作。

## 会话开始

先阅读以下文件：

1. `AGENTS.md`
2. `harness/state/current-task.md`
3. `harness/docs/architecture.md`
4. `harness/state/progress.md`

然后按需加载相关支持文件：

- `harness/features/feature_list.json`
- `harness/specs/product-spec.md`
- `harness/specs/technical-spec.md`
- `harness/specs/acceptance-criteria.md`
- `harness/docs/development-rules.md`
- `harness/docs/decision-log.md`
- `harness/state/memory.md`
- `harness/state/session-handoff.md`

## 创建任务

使用 `harness/tasks/task.md` 作为任务记录模板。

任务必须包括：

- 目标
- 范围
- 计划
- 实施记录
- 验证记录
- 最终报告

在 `harness/state/current-task.md` 中更新当前任务摘要。

## 实施期间

- 编辑前检查相关代码。
- 保持改动小而明确。
- 完成有意义的步骤后更新任务记录。
- 立即记录架构决策。
- 在 `harness/state/failure-log.md` 中记录失败。
- 随工作推进更新功能状态。

## 验证

在主要 Windows 运行环境中使用可用的最强验证命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/verify.ps1
```

对应的 WSL/Git Bash 包装器为：

```bash
bash harness/scripts/verify.sh
```

本地迭代时使用更窄的命令，例如：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/test.ps1
```

始终记录：

- 命令
- 结果
- 重要输出
- 跳过的检查及原因

## 完成任务

声称完成前：

1. 确认验收标准已经满足。
2. 确认必需验证已经通过。
3. 更新 `harness/features/feature_list.json`。
4. 更新 `harness/state/progress.md`。
5. 更新 `harness/state/task-history.md`。
6. 更新 `harness/state/session-handoff.md`。
7. 编写带证据的最终报告。

## 处理失败

发生失败时：

1. 记录错误。
2. 解释可能原因。
3. 记录已经尝试的修复。
4. 使用不同假设继续验证。
5. 如果下一步需要确认，则停止并等待。

不要重复完全相同的失败尝试。

## 移交

会话结束时，确保 `harness/state/session-handoff.md` 回答：

- 当前任务是什么？
- 改变了什么？
- 还剩什么？
- 运行了哪些命令？
- 最佳下一步是什么？
- 是否存在阻塞或风险？
