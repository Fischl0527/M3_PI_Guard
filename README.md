# M3-PI Guard

## 当前项目组入口（更新：2026-10-10）

先读 [项目组交接指南：LLM的千层诱惑](docs/LLM的千层诱惑.md)：用通俗中文说明项目、工具、算法、
实验、当前结果、目录和接手顺序，英文名称与必要术语均有解释。
最新状态以指南及 `harness/state/current-task.md` 最上方记录为准。

重要源码见[中文代码阅读指南](docs/重要代码阅读指南.md)，从权限、提案、判定、模拟效果讲到评分；论文参考见[中文阅读说明](docs/research/paper_v2/manuscript/论文中文阅读说明.md)。当前关键实现已补中文注释，程序字段和英文投稿源不改名。

教师演示与换环境验证见[演示与跨环境运行指南](docs/演示与跨环境运行指南.md)。新入口不需要密钥、GPU或Docker；使用真实修复版组件和固定动作，不能等同模型效果。交付包在本地`release/`生成，不把整个旧运行环境或内部请求日志推送GitHub。

同一迁移包已在Windows11、Ubuntu24/22/26与Kali2026.1各通过119项定向测试，180份权限和900/480/16结果计数一致；见[五环境验证报告](docs/可迁移性验证报告_2026-10-09.md)。Ubuntu/Kali虚拟机已经安装好；报告给出了现成路径及运行命令。本项软件验证完成，不代表论文结项或防御效果泛化。

旧比赛材料已移至仓库外归档，见[归档说明](docs/比赛材料归档说明_2026-10-06.md)。根目录不再保存第二份交接指南。

**下面保留的是早期移交快照。** 其中“仅用本地模型”“不推送远程”、旧就绪分数、
盲测待办和全量历史验证命令不是当前执行清单。当前已有官方DeepSeek结果，
Gemini仍不足以做跨厂商比较；不要按旧命令启动全量验证或恢复已结束实验。

## 历史项目概览（保留参考）

M3-PI Guard 是一个面向工具型大模型智能体的本地提示注入安全靶场、运行时 Guard 和可复现实验平台。项目关注模型是否提出或执行未经授权的工具动作，并在动作产生副作用前进行 `ALLOW`、`ASK` 或 `DENY` 决策。

## 从这里开始

- [项目移交报告](docs/项目移交报告.md)：接手顺序、当前证据、失败路线、环境状态、风险和下一步。
- [完整项目综述](docs/项目完整综述.md)：功能、架构、运行方式、优点、创新点、缺点和论文未完成项。
- [文档索引](docs/README.md)：架构、数据卡、伦理、运行手册、历史报告和展示材料。
- [运行手册](docs/运行手册.md)：E0–E17、最终分析和仪表盘的复现命令。
- [目录说明](文件夹说明.md)：项目源码、Harness、模型、实验结果和人工材料的边界。
- [Harness 使用说明](harness/README.md)：智能体任务、进度、失败和验证状态。
- [Harness 项目上下文](harness/项目上下文.md)：Harness 如何记录本项目、状态文件优先级和恢复纪律。
- [本地配置说明](config/README.md)：团队共享字段、本机令牌和 PromptGuard 环境。

## 当前证据状态

- 历史 E0–E17：18 个实验均已完成；标准 300 条数据、两名真人分层抽样盲审、统计、13 张图、仪表盘和 HTML 技术报告已经完成。
- 修复 V2：12/12 工程验收通过，但属于复用旧盲测集的事后修复，不是新的确认性盲测。
- paper-v1：非 oracle 策略、来源追踪、M3-v2、公共冻结、强基线适配和自适应运行器已实现；公共正式矩阵、至少五个强基线、独立 600 条盲测、双厂商 API 和正式自适应预算实验仍未完成。
- 强基线现状：ToolFilter 与 PromptGuard 可用于正式实验；Task Shield 路线关闭，Progent v1.4 因延迟门禁失败，CaMeL v3 P3 因正常任务效用为 0/4 未获正式准入。
- 最新 Q2 就绪度：原始分 66.0、封顶分 60.0，`goal_80_met=false`、`goal_90_met=false`。

冒烟、资格、预检、诊断和运行中结果只证明局部工程状态，不能作为正式论文效果结论。

## 安全边界

- 模型仅通过回环地址上的 Ollama 运行；远程 API 只有在显式授权和独立准入流程下才允许使用。
- `send_email` 只写本地发件箱；`call_api` 返回模拟 JSON；`run_code` 不执行模型生成代码。
- 测试密钥是合成的金丝雀标记，不使用真实凭据或真实业务系统。
- `config/project.local.env`、模型权重、外部源码检出和运行缓存不提交到 Git。

## 最小运行

```powershell
python scripts\check_project_config.py
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend stub --defense-modes baseline,full_guard --out-dir outputs/runs/day7_smoke_stub --run-prefix day7_smoke --max-steps 5
python -m m3_eval.evaluate --log-dir outputs/runs/day7_smoke_stub --cases fixtures/demo_cases.jsonl --out outputs/metrics/day7_smoke_summary.csv
```

桩后端是确定性回归设施，不代表真实模型安全效果。真实 Ollama、公共基准和强基线运行前必须确认没有其他正式 GPU 作业，并使用相应冻结和 manifest。

## 验证

```powershell
python scripts/audit_project_conventions.py --check
python -m pytest -q
python -m experiments.validate_registry
python scripts/verify_historical_evidence.py
powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/verify.ps1
```

## 目录边界

- 产品与实验源码：`m3_core/`、`m3_guard/`、`m3_eval/`、`m3_attacks/`、`experiments/`、`protocols/`、`schemas/`、`scripts/`、`tests/`。
- 智能体 Harness：`harness/`。根目录 `AGENTS.md` 仅用于自动发现。
- 历史兼容：`agent/`，因冻结证据引用保留，不是当前 Harness。
- 生成证据：`outputs/`；外部固定版本源码检出：`external/`；本地工具状态：`sandbox/`。

当前范围不制作或修改 PPT、DOCX、ZIP，不推送远程分支，不创建 PR。
移交快照中 Ollama 和项目实验进程均已停止；需要运行模型时应先按冻结和门禁
重新确认身份与资源，不要从历史 PID 恢复。
