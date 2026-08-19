# paper-v2 Online-State 源码审计摘要

- 固定时间：`2026-07-23T19:00:00+08:00`
- 已完成审计单元：`22/22`
- 已覆盖不同项目：`16`
- 官方源码单元：`20`
- 披露式本地复现单元：`1`
- 官方源码缺失单元：`2`
- 独立第二复核：`0`
- 领域级 oracle 结论：`禁止`

## 结论分布

- `inconclusive`：2
- `mixed_or_path_dependent`：1
- `no_online_gold_observed`：9
- `not_a_runtime_guard`：10

## 可写与不可写

可以写：每项结论只适用于其固定 commit、来源类型和已审计边界。CaMeL 的 live/replay 路径需要分开报告；SIREN 与 Task Shield 的官方实现证据不足。

不可写：不能据此声称该领域普遍存在 oracle authorization，也不能把静态投影测试描述为完整模型/API 动态复现。所有单元仍需独立第二复核。

## 来源边界

- `A19-wasp-benchmark`：Meta 官方归档仓库，按固定 commit 审计。
- `A22-task-shield-runtime`：官方论文未给出代码；只审计固定论文和明确标注的本地披露复现，不能外推为作者实现。

完整逐项证据位于 `protocols/paper_upgrade_v2/audits/`；每个清单记录文件大小和 SHA-256。
