# M3 PI Guard 的 AI Agent Harness 工程

本目录只放“让 Agent 能持续、可恢复、可验证地完成工作”的 Harness 工程文件，不放 M3 PI Guard 的模型运行时、Guard 算法、攻击数据集或实验实现。

## 与项目源码的硬边界

| 区域 | 负责内容 | 主要目录 |
|---|---|---|
| M3 项目源码 | Agent 运行时、Guard、攻击、评估、实验协议与测试 | `m3_core/`、`m3_guard/`、`m3_eval/`、`m3_attacks/`、`experiments/`、`protocols/`、`schemas/`、`fixtures/`、`tests/`、`scripts/` |
| Harness 工程 | Agent 规则、任务状态、规格、工作流、验证入口、Runpro 工作区 | `harness/config/`、`harness/state/`、`harness/specs/`、`harness/features/`、`harness/tasks/`、`harness/docs/`、`harness/scripts/`、`harness/workspaces/` |
| 项目生成物 | 实验日志、图表、报告中间物、盲审包 | `outputs/`、`release/`、`sandbox/`、`文档资料/`、`图表素材/` |

根目录只保留一个 Harness 兼容锚点：`AGENTS.md`。这是因为 Agent 运行时从仓库根目录自动发现它。根目录 `agent/` 目前只保留已被实验清单和报告引用的项目完整性审计代码与冻结证据，不再存放当前 Harness 状态。

## Harness 目录结构

```text
harness/
├─ README.md                     本入口与源码边界
├─ config/
│  ├─ permissions.yaml          风险操作权限边界
│  ├─ policies.md               Agent 行为策略
│  └─ workflow.md               六阶段工作流
├─ docs/
│  ├─ architecture.md           Harness 与项目集成架构
│  ├─ development-rules.md      开发规则
│  ├─ decision-log.md           决策记录
│  └─ agent-guide.md            日常使用说明
├─ state/
│  ├─ current-task.md           当前任务
│  ├─ progress.md               进度与验证状态
│  ├─ session-handoff.md        会话交接
│  ├─ task-history.md           历史任务
│  ├─ failure-log.md            失败与恢复记录
│  └─ memory.md                 可复用经验
├─ specs/                       产品、技术与验收规格
├─ features/feature_list.json   功能状态台账
├─ tasks/                       任务模板与任务记录
├─ scripts/                     Harness 初始化、测试、验证和清理入口
├─ workspaces/runpro/           Runpro 分析、计划和阶段报告
└─ tmp/                         可清理的 Harness 临时渲染/探测文件
```

## 入口命令

所有命令仍从仓库根目录执行。

Windows 验证：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/verify.ps1
```

仅运行测试：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/test.ps1
```

WSL/Git Bash：

```bash
bash harness/scripts/init.sh
bash harness/scripts/verify.sh
```

## 日常工作流

1. 读根目录 `AGENTS.md`。
2. 读 `harness/state/current-task.md`、`harness/docs/architecture.md` 和 `harness/state/progress.md`。
3. 按需读取 `harness/specs/`、`harness/features/feature_list.json` 与 `harness/docs/decision-log.md`。
4. 从 `harness/tasks/task.md` 创建或更新任务记录。
5. 按 `harness/config/workflow.md` 执行理解、分析、计划、实现、验证、交接六阶段流程。
6. 项目代码只修改项目源码区；Harness 状态和规则只修改 `harness/`。
7. 运行 Harness 验证入口或更窄的项目测试命令。
8. 更新状态、功能台账、失败记录和交接文件。

## 谁修改什么

用户/项目成员主要维护：

- `harness/specs/` 中的项目事实和验收要求；
- `harness/features/feature_list.json` 中的优先级与交付状态；
- M3 项目源码、数据集和实验设计。

Agent 自动维护：

- `harness/state/` 中的当前任务、进度、失败、历史和交接；
- `harness/docs/decision-log.md` 中需要长期保留的决策；
- 与实际实现同步的验证证据。

## 放置规则

- 新的模型运行逻辑、Guard 组件、指标、实验生成器和测试不得放进 `harness/`。
- 新的 Agent 规则、状态格式、任务模板、Harness 校验器和会话工作区不得放进项目源码目录。
- 项目实验输出继续写入 `outputs/`；Harness 阶段分析写入 `harness/workspaces/`。
- `harness/tmp/` 是临时缓存，可按 `harness/config/permissions.yaml` 和清理脚本处理；不要把唯一证据放入其中。
- 不要移动 `agent/audits/` 或 `agent/result_integrity_audit.py`，除非同时迁移所有清单、报告引用和哈希校验。

