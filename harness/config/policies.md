# 智能体策略

## 仓库是真实状态来源

所有需要持久化的任务状态都必须写入仓库文件。私人聊天记忆不足以支撑长任务。

必需状态文件：

- `harness/state/progress.md`
- `harness/state/current-task.md`
- `harness/state/session-handoff.md`
- `harness/state/task-history.md`
- `harness/features/feature_list.json`
- `harness/docs/decision-log.md`

## 验证策略

智能体不得仅凭推理声称代码可用。

有效的完成声明需要：

- 已运行的命令。
- 已观察的结果。
- 对失败或跳过检查的解释。
- 验收标准与证据的对应关系。

使用：

```bash
bash harness/scripts/verify.sh
```

## 安全策略

执行高风险动作前阅读 `harness/config/permissions.yaml`。

智能体在以下动作前必须请求确认：

- 删除安全生成路径之外的文件。
- 修改数据库。
- 部署到生产环境。
- 修改权限系统。
- 改写 Git 历史。

智能体绝不能：

- 访问或输出密钥。
- 绕过安全规则。
- 通过禁用测试隐藏失败。
- 将未验证工作标记为完成。

## 失败策略

失败是正常工程事件，重复盲目重试不是。

对每个有意义的失败，更新 `harness/state/failure-log.md`，记录：

- 错误。
- 原因分析。
- 已尝试动作。
- 最终处理。
- 后续事项。

重试前必须改变假设或收集新证据。

## 文档策略

当变化影响以下内容时更新文档：

- 用户行为。
- 开发者配置。
- 命令。
- 架构。
- 安全状态。
- 验收标准。

## 移交策略

每个会话都必须以可用的移交结束。

`harness/state/session-handoff.md` 必须包括：

- 当前任务。
- 已修改文件。
- 已运行命令。
- 验证结果。
- 未解决风险。
- 建议下一步。
