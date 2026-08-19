# M3-PI Guard Fresh Harness v5/v6 收口报告

报告时间：2026-08-06（Asia/Shanghai）  
报告范围：v5 失败证据冻结、沙箱 Git 所有权兼容、v6 完整 Harness 终态  
当前结论：本阶段工作已完成并停止；未启动任何新的模型/API 实验

## 1. 执行摘要

本阶段已经完成预定的工程收口：Fresh Harness v5 的失败没有被覆盖、删除或
解释为实验失败，而是作为不可变历史证据单独冻结；其根因被定位为当前沙箱账户
对固定 AgentDojo Git checkout 的所有权信任问题。项目随后新增仅对子进程生效的
Git `safe.directory` 兼容层，未修改全局、系统或仓库 Git 配置，并使用全新的
single-use v6 运行身份重新执行完整 Harness。

最终结果如下：

| 项目 | Fresh Harness v5 | Fresh Harness v6 |
|---|---:|---:|
| 直接观测的子进程退出码 | 1 | 0 |
| 完整测试 | 1531 passed / 1 skipped / 3 warnings | 1538 passed / 1 skipped / 3 warnings |
| Harness 聚合阶段 | 10 PASS / 3 FAIL | 13 PASS / 0 FAIL |
| 唯一终态标记 | `Verification failed=1` | `Verification failed=0` |
| 运行时间 | 66080.900 秒（约 18 小时 21 分） | 15737.184 秒（约 4 小时 22 分） |
| API/provider/network 授权 | 否 | 否 |
| 全局或仓库 Git 配置修改 | 否 | 否 |
| 是否作为绿色技术基线 | 否 | 是 |

因此，当前源码、历史证据、paper-v2 冻结资产和 prospective closeout 证据在 v6
运行身份下形成了直接、完整、可哈希复核的绿色技术基线。该结论只代表工程和证据
链验证通过，不等于 21 天实验计划已经结项，也不自动授权 Gemini、DeepSeek、
Adaptive 或独立盲测的后续执行。

## 2. 本阶段边界

本阶段只处理以下事项：

1. 等待 Fresh Harness v5 自然结束并保存直接 OS 终态；
2. 对 v5 launch、running、stdout、stderr、receipt 和旧 helper/launcher 做哈希冻结；
3. 对 Git ownership failure 做脱敏、可复验的技术资格化；
4. 新增仅进程作用域的 Fresh Harness v6 receipt helper 和 single-use launcher；
5. 运行定向检查与唯一一次完整 v6 Harness；
6. 更新项目状态与形成本文档。

明确未做：

- 未读取、输出或复制 DeepSeek/Gemini 密钥；
- 未创建新的 provider admission、result admission 或 fresh gate；
- 未调用 DeepSeek、Gemini 或其他模型 API；
- 未预约 Gemini 免费层配额日；
- 未运行新的 Public、Adaptive 或独立盲测任务；
- 未修改历史冻结输入、旧 v5 运行、旧实验 ledger 或科研 outcome；
- 未执行任何真实邮件、支付、浏览器、生产 API、provider tool 或外部 effect。

## 3. Fresh Harness v5 失败审计

### 3.1 v5 终态

v5 从 2026-08-04 04:08:56 运行至 22:30:17，receipt 直接记录：

- `status=completed_child_nonzero`；
- child exit code = 1；
- verifier/helper 运行前后哈希一致；
- pytest：1531 passed、1 skipped、3 warnings；
- stdout 中恰好一个聚合终态：`Verification failed=1`；
- 10 个阶段通过，3 个阶段失败；
- provider key/consent 在子进程启动前清除；
- `network_or_provider_call_authorized=false`；
- `automatic_restart=false`。

通过阶段：Harness files、Harness/project boundary、项目命名规范、JSON、PowerShell、
Shell、Python compile、unit/integration、registry、paper-v2 source audit。

失败阶段：

1. Paper-v2 frozen study assets；
2. Paper-v2 experiment closeout prospective evidence；
3. Historical evidence and current V2 freeze。

### 3.2 根因

首个失败发生在 `formal_matrix_controller_v8 --verify-canary-admission` 对固定
AgentDojo checkout 执行 `git rev-parse HEAD` 时。v5 stderr 保留一个 Python
traceback，Git 子进程返回非零；后两个证据进程随后以相同 Windows 状态码类别
退出。

独立脱敏资格化进一步确认：

- 在当前沙箱身份且不提供兼容项时，Git 触发 ownership rejection；
- 只在当前进程环境设置精确 AgentDojo 路径后，可读取冻结提交
  `089ed468cf3ed0322acc66b0211f26d9d90dbf60`；
- 不需要也没有执行 `git config --global`；
- 未修改 checkout 的仓库配置或文件；
- 资格化过程 provider/network calls 均为 0。

因此根因分类为
`sandbox_git_safe_directory_rejection_at_external_checkout`。这不是 1531 项测试中的
功能失败，也不是模型、API、预算或科研结果失败。

### 3.3 v5 不可变证据

v5 failure-review manifest：
`02af896a4b128fb06cb07a35fd7e1e040f65181434bedb61f22e73dc0c5f7149`。

该 review 将旧 v5 helper 和 launcher 一同纳入 source lock，后续没有修改 v5
运行目录，也没有把 v5 改写成成功。

## 4. v6 修复设计

### 4.1 仅进程作用域的 Git 兼容

新 helper 在启动验证子进程前完成四件事：

1. 清除 DeepSeek、Gemini、OpenAI/Anthropic 相关 key 和显式 consent 环境项；
2. 在 helper 自己的进程环境中设置一个精确的 `safe.directory`；
3. 先验证 AgentDojo HEAD 精确等于冻结 commit；
4. 再启动完整 Harness 子进程，并由子进程继承该临时环境。

helper 退出后，这三个 Git 环境项自然消失。运行 receipt 明确记录：

- `git_safe_directory_scope=process_only`；
- `global_git_config_mutated=false`；
- `repository_git_config_mutated=false`；
- expected/observed AgentDojo commit 完全一致。

### 4.2 终态与漂移保护

v6 helper 保留 v2 的持久化保障并增加 Git 资格化检查：

- single-use 输出目录；
- launch/running/stdout/stderr/receipt 分离；
- 直接等待并记录 child OS exit；
- verifier/helper 运行前后 SHA-256 比较；
- stdout/stderr 字节数和 SHA-256；
- 恰好一个 aggregate marker；
- marker 必须是最后一个非空行；
- 任一 FAIL stage、source drift、Git qualification drift 或非零 exit 均 fail closed；
- 不自动重启。

## 5. v6 完整验证结果

### 5.1 运行身份

- 启动时间：2026-08-05 23:08:10 +08:00；
- 完成时间：2026-08-06 03:30:27 +08:00；
- 持续时间：15737.184 秒；
- helper PID：2888；
- child PID：37624；
- child exit code：0；
- receipt/evidence gate：PASS；
- 结束后相关进程数：0。

### 5.2 十三个聚合阶段

| # | 阶段 | 结果 |
|---:|---|---|
| 1 | Harness files | PASS |
| 2 | Harness and project source boundary | PASS |
| 3 | Project layout and naming conventions | PASS |
| 4 | JSON contracts | PASS |
| 5 | PowerShell syntax | PASS |
| 6 | Shell syntax | PASS |
| 7 | Python compile | PASS |
| 8 | Unit and integration tests | PASS |
| 9 | Experiment registry structure | PASS |
| 10 | Paper-v2 source-audit evidence | PASS |
| 11 | Paper-v2 frozen study assets | PASS |
| 12 | Paper-v2 experiment closeout prospective evidence | PASS |
| 13 | Historical evidence and current V2 freeze | PASS |

聚合结论：13/13 PASS，0 个 FAIL stage，stdout 中恰好一个
`Verification failed=0`，且为最后一个非空行。

### 5.3 测试与 stderr 复核

- pytest：1538 passed、1 skipped、3 warnings；
- pytest 时长：6664.43 秒（1:51:04）；
- Python traceback：0；
- RuntimeAuditor 的预期删除动作阻断：183 条；
- 已知密钥格式正则命中：0；
- receipt 明确记录 network/provider authorization 为 false。

183 条 RuntimeAuditor 记录是安全测试对删除动作的预期阻断，不是 Harness FAIL；
这与 13/13 聚合阶段、child exit 0 和 terminal marker 一致。

## 6. 定向检查

在完整 v6 前完成的定向验证：

| 检查 | 结果 |
|---|---|
| 新增 Git qualification、v5 review、v5/v6 launcher 测试 | 10/10 PASS |
| Ruff | PASS |
| Python compile | PASS |
| PowerShell parse | PASS |
| 项目 conventions | 12/12 PASS |
| Git qualification 独立重放 | PASS |
| v5 failure review 独立重放 | PASS |

受限沙箱账户首次扩大检查时无法启动用户目录中的 Ruff，也无法读取一个既有
final-analysis CSV；该尝试已记入 failure log，没有冒充通过。随后在项目原账户、
同样零网络的条件下重新执行，所有定向检查通过。该 ACL 问题与源码正确性分开
记录。

## 7. 关键证据与哈希

| 工件 | 字节 | SHA-256 |
|---|---:|---|
| v6 `launch.json` | 1,000 | `40eed7b4cb1334df09311ca611d8fd1061d746a40be96008edba917d7c954fe6` |
| v6 `running.json` | 1,124 | `9faf66997e58563f7db1e39e6afa30b8eb1b9534349e9a155524614d2bd78416` |
| v6 `stdout.log` | 1,137,444 | `23d9f8840583158d9c9ae2e6c0f45c2e5abefc55dc12e808724dd115c9d0a945` |
| v6 `stderr.log` | 9,465 | `0d2da881d532072d011e66842359f4a36f8f29045908daf4e048108e1acb0573` |
| v6 `receipt.json` | 2,454 | `26e516629708e03bfbef05a8915cef1d12701a9be227348215740cf40b093798` |
| Git qualification JSON | 1,357 | `456e830d94204e3ee0e8aff0c74e8a2aa8e3dcd2d29ebf5b97b04a2121278e5c` |
| v5 failure review JSON | 4,245 | `8cbc28a3426f8900afe7a5ab511ea6c40da9eeab0bef1e65764676aa3db5e83d` |
| v3 receipt helper | 8,303 | `4a5cc0d67d80e039ec8c749437dc0442e3d0487b4444d830bf2a7352716c6cbe` |
| v6 launcher | 2,300 | `9049ba72e088d3b3d5d67c3630266df3e32037da47d3f0ab2f67e4fb8289e2b4` |

receipt 内部还分别绑定 verifier SHA-256
`5d6841821ba693f6b17a86f2dbc31349d96ce04e4226e910c51170d2ee5de7b2`
与 helper SHA-256
`4a5cc0d67d80e039ec8c749437dc0442e3d0487b4444d830bf2a7352716c6cbe`，
两者运行前后均未漂移。

## 8. 对项目结项状态的影响

本阶段解决了“当前工作树是否存在直接、完整、绿色 Harness 终态”这一工程阻塞，
但没有完成整个 21 天实验计划。`F-PAPER-002` 应继续保持 `in_progress`，原因包括：

1. Gemini 3.6 Flash 的正式公共矩阵尚未完成；
2. Pro/Flash/Gemini 正式 adaptive 面板和 hardest-20 × 2000 尚未完成；
3. 600 条独立盲测候选、3,600 条六条件执行、解封评分和结果 manifest 尚未完成；
4. 三模型最终统计复算与哈希结项包尚未完成；
5. DeepSeek Flash 的 1,791 条物理记录虽已闭合，但 shard 0 的冻结质量门仍是
   10 diagnostic > 6，不能由本次 Harness 通过来豁免；
6. 本次没有创建新的 provider/result admission，因此不能把绿色 Harness 当作
   自动的 API 执行许可。

## 9. 当前停止点与恢复建议

依照项目所有者指示，本阶段在 v6 运行、对账、状态更新和本报告完成后停止。
当前没有相关 Harness 或 provider 进程运行。

未来如恢复 21 天计划，建议从以下顺序继续：

1. 先独立重放 v6 receipt、Git qualification 和 v5 failure review；
2. 基于 v6 创建新的、非自授权技术 gate；
3. 再单独冻结下一 provider 的 exact admission；
4. 继续遵守 Gemini free-only/USD 0、DeepSeek 硬熔断、零自动重试、零真实外部
   effect 和失败留在 ITT 的边界；
5. 每个正式执行结果仍需 outcome-blind 技术审查和独立 result admission。

## 10. 最终结论

当前手上工作已经完成：v5 失败被诚实冻结，根因有脱敏、可复验的技术证据；
兼容修复没有污染永久 Git 配置；v6 完整 Harness 形成直接 exit 0、13/13 stage
PASS、1538 tests PASS、唯一 `Verification failed=0` 的绿色终态。项目现已按要求
停止在技术基线通过、后续正式实验尚未启动的位置。
