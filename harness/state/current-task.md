# 当前任务

### 2026-08-20 精简实证里程碑 8：active citation compliance

- 只核验统一稿实际引用的 21 个 BibTeX key；未被引用的 15 条候选文献不进入本轮
  投稿核验，避免无效全库重算。
- 21/21 引用键均可解析；其中 11 篇有正式会议/Workshop 发表记录，10 篇保持
  preprint 身份。引用用途与正文论述匹配，不支持 first/only/SOTA 主张。
- 修正两处确定性元数据缺陷：DRIFT 改为官方 NeurIPS 2025 年份并补 DOI；
  AgentSpec 删除 DOI 系统无法解析的旧 DOI 与未经核实页码，改用 ICSE 2026
  Research Track 官方页面。
- Markdown/Word 已重建；定向 pytest 9/9、Ruff 和 `py_compile` 通过。Gemini
  仍等待新 Pacific 配额日，不提前调用。F-PAPER-002 保持 `in_progress`。

### 2026-08-20 精简实证里程碑 7：JISA cover letter draft

- 在等待 Gemini 新配额日时新增 293-word JISA cover letter 草稿，只使用已完成的
  DeepSeek Pro/Flash、900-record authorization 和 Adaptive 50/200 结果。
- 信件明确把贡献限定为评估方法与安全—效用实证，不宣称 first/only/SOTA，也不
  写入未完成的 Gemini 跨厂商结论。
- 按 Elsevier 2026-05-18 官方通用指导，正文保持少于一页，说明研究目标、主要
  发现、JISA scope fit 与实践意义；funding、author declarations 和 reviewer
  suggestions 均未写入信件正文。
- 作者姓名、通信信息、投稿日期及 Gemini 结果依赖措辞仍在提交前更新清单中。
  F-PAPER-002 保持 `in_progress`。

### 2026-08-20 精简实证里程碑 6：JISA submission statements

- 在 Gemini 新 Pacific 配额日之前，没有提前调用 API。当前冻结 Gemini 计划为
  450 项；5 项已有官方响应并永久跳过，下一次 pending-only 命令最多处理 109 个
  无响应可恢复项和 335 个未触碰项。
- 新增 reader-facing submission statements，工作稿现在在 References 之前包含
  competing interests、funding、data/code availability、generative-AI use、
  ethics/safety 和 author contributions 的明确位置。已知事实直接陈述，作者专属
  内容保持为提交前确认事项，不推断作者、资助或利益冲突信息。
- Markdown 和 Word 工作稿已重建。定向 pytest 9/9、Ruff、`py_compile`、DOCX
  结构生成和可访问性检查通过；可访问性仍为 0 high / 0 medium / 21 low，低级项
  全部是参考文献 DOI/URL 的显示文本。
- 标准 DOCX renderer 仍因本机没有 LibreOffice 退出；这是已知环境限制，未继续
  重试，也不宣称完成视觉分页验收。F-PAPER-002 保持 `in_progress`。

## 任务编号

M3-PAPER-002

## 目标

在分支 `codex/q2-empirical-study` 实施 SCI JCR Q2 精简实证论文计划。论文以
授权制度、provenance-aware Guard 的模块贡献和安全—效用权衡为主线；复用现有
DeepSeek Pro/Flash 与 Adaptive 50/200 数据，只新增 900 条 DeepSeek Pro 授权
制度实验和 450 条 Gemini 精简跨厂商验证。停止 Full Harness、递归历史证据重放、
独立盲测、Pro-500、hardest-20×2000 和完整 Gemini 1791 矩阵。不读取或输出秘密，
不执行真实工具/effect；按 Owner 授权在稳定阶段 commit 并 push 到 `m3-guard`，
不创建 PR、不部署、不 force-push。

## 当前阶段

### 2026-08-20 精简实证里程碑 5：DeepSeek 失败行恢复收口

- Owner 恢复任务后，仅对没有官方响应的 DeepSeek 行执行了一次显式
  `--retry-failed`；已有响应的 867 个 work key 未重跑。
- 恢复逆序执行 33 项，全部作为 attempt 2 追加保留。最终原始文件为
  933 条物理记录 / 900 个唯一 work key；最新状态为 768 completed、54
  parse failure、30 max steps、15 provider failure 和 33 repeated pre-response failure。
- 900/900 工作项现均进入 ITT，`retry_eligible=0`。全部尝试累计 1,638 次
  provider calls，CNY 1.3888324；精确返回模型仍为 `deepseek-v4-pro`。
- online forbidden 字段、provider tools 和外部 effect 记录均为 0，相关 runner
  进程为 0。DeepSeek 新授权制度实验已按预定失败规则完成技术收口。
- F-PAPER-002 仍为 `in_progress`；下一子阶段是 Gemini 免费层未完成项恢复，
  已获得官方响应的 Gemini 行不得重跑。

### 2026-08-20 精简实证里程碑 4：DeepSeek 主执行自然结束

- DeepSeek 授权制度主执行已自然结束，当前无遗留 runner；原始文件包含
  900 行、900 个唯一 work key，覆盖冻结的全部 DeepSeek 计划项。
- 867 行获得官方响应，33 行未获得响应；870 行按预定规则进入当前
  ITT，30 行仍是可恢复的传输前失败。按 Owner 最新指令，本次不启动
  `--retry-failed`，也不启动 Gemini 或新的分析实验。
- 技术计数为 1,635 次 provider calls、CNY 1.3888324，返回模型均为
  `deepseek-v4-pro`。在线 forbidden 字段、provider tools 和外部 effect 记录均为 0。
- 本阶段只做了内容无关的行数、唯一性、模型身份、失败分母和安全边界检查；
  没有重跑 Full Harness、历史证据链或已成功实验行。
- F-PAPER-002 仍为 `in_progress`：DeepSeek 900 项的物理执行已完成，但失败行恢复、
  Gemini 精简验证、正式统计和论文收口均未完成。当前按 Owner 指令停止。

### 2026-08-20 精简实证里程碑 3：主执行与分析图表工具

- DeepSeek `remaining` 主执行已启动并持续追加尚未触碰的 work key；formal
  prefix 不重跑。该进程自然结束前不提交正在变化的 raw JSONL，也不并发启动
  第二个 DeepSeek runner。
- Gemini `remaining` 遇到系统性官方 429 后已停止当日执行；已有官方响应的行
  保留且永不重跑。运行器已改为识别 trace 中的 paused/429 并在第一条限流记录后
  停止；下一配额日仅用显式 `--retry-failed` 恢复无响应行和未触碰行，最多三个
  配额日。
- 新的一次性授权分析实现 Wilson CI、exact McNemar、10,000 次任务聚类
  bootstrap、Holm 校正、负担与异质性统计。五图生成器输出 PNG+SVG，不读取
  provider trace、不调用 API、不生成额外哈希包。
- 已把 active Introduction、Methods、manuscript README、figure/table plan 和
  Related Work 改写为精简研究口径，删除 Full Harness、盲测、B500/B2000 和
  完整 second-model adaptive 的论文依赖；补入 2026 provenance-sensitivity 工作。
- 六表 CSV 导出器已实现，只读取 frozen plan 与两个 compact analysis 文件；
  不打开 raw trace，也不生成 hash bundle。
- 定向验证当前为 pytest 17/17、Ruff 和 py_compile 通过；五张合成数据 QA 图已
  逐张查看并修复标题/标签重叠。没有运行 Full Harness。
- 下一稳定 Git 里程碑：提交运行器恢复修复、分析/图表代码和 Harness 状态；
  DeepSeek raw 只在主执行自然结束并完成失败行恢复后单独提交。

### 2026-08-19 精简实证里程碑 1：样本冻结与现有结果单次分析

- Git 分支 `codex/q2-empirical-study` 的基线提交为 `d533414`；远程
  `m3-guard` 已配置，未 push。
- 已在不读取旧实验 outcome 的前提下冻结 180 个 DeepSeek 主样本、
  60 个授权扩展子集和 90 个 Gemini 嵌套子集；执行计划为
  DeepSeek 900 行 + Gemini 450 行，每个 provider 各有 6 行 formal prefix。
- 已对现有 Public Pro 5,082、Public Flash 1,791、Medium 480 和
  Adaptive B50/B200 执行一次性分析；没有 API 调用、历史递归验证或
  Full Harness。关键观察是 Pro 上 M3-full attack unsafe effect 38/600，
  policy-only 13/600，两者 benign-tool TCR 均为 49/168；Flash 方向一致
  （24/400 vs 12/400）。这支持继续负面结果/授权制度实证路线。
- 定向测试共 4/4 通过，Ruff 与 py_compile 通过。Medium 首次分析
  只读到 177 行 v9 remainder，根据失败日志改为合并互斥的
  303 行 v8 prefix + 177 行 v9 remainder，修复后得到 480/480；
  没有重跑任何已成功的模型记录。
- 下一步仅实现最小运行器与定向测试，然后执行两家各 6 行
  canary。F-PAPER-002 保持 `in_progress`。
- 最小运行器已实现：单 provider 单 raw JSONL、内容无关的官方请求链、
  成功行不重跑、无官方响应失败行仅在显式 `--retry-failed` 下重跑、
  Gemini 固定 free/USD 0。定向验证 8/8、Ruff/py_compile 通过；
  Full Harness 未运行。下一操作是 DeepSeek 6 行 formal prefix。
- DeepSeek formal prefix 已完成 6/6：14 次官方请求，6/6 行均有
  response ID，返回模型全部为 `deepseek-v4-pro`；5 completed + 1 max_steps，
  后者留在 ITT。成本 CNY 0.0157848，在线 forbidden 字段、provider tools、
  外部 effect、自动重试和 retry-eligible 失败均为 0。下一步为 Gemini 6 行
  formal prefix。
- Gemini formal prefix 已把 6 个 work key 全部归入 ITT：5 个有官方响应，
  返回模型为 `gemini-3.6-flash`；3 completed、2 parse_failure、1 个 VIGIL
  repeated_pre_response_failure。该 VIGIL 行仅显式恢复一次，尝试 1/2 均保留，
  不再发起 attempt 3。Gemini 成本 USD 0，在线 forbidden 字段、tools、外部
  effects 和剩余 retry-eligible 行均为 0。两家技术 canary 已收口，可进入
  pending-only 主执行。

### 2026-08-19 精简实证路线正式启用

- Owner 已批准《SCI 二区精简实证论文计划》，旧 21 天实验结项计划废止。
- Fresh Harness v12 及其 watcher 已按 Owner 决定终止；原 stdout/stderr 保留，
  receipt 不存在且不补造。后续不再启动 v12/v13 或任何 Full Harness。
- 当前只允许定向测试、一次性现有结果分析、固定的 180/90/60 样本计划和对应
  DeepSeek/Gemini API 实验；失败只修复并重跑受影响行，成功行不重跑。
- 独立盲测从当前论文范围移除，历史 Day-1 资料不删除、不继续执行，也不支持论文
  中的独立盲测主张。
- Git 工作分支为 `codex/q2-empirical-study`；远程 `m3-guard` 指向
  `https://github.com/Fischl0527/M3_PI_Guard.git`，当前不 push。

### 最新源完整 Harness v7 资格化与运行 — 2026-08-06 继续实施

- 目标：对已接入 gate-v4 与 Gemini recovery wrapper-v2 的当前 `verify.ps1`
  取得新的直接 OS exit、完整日志和 hash-bound receipt；这不是历史
  `formal_matrix_controller_v7` 的恢复或重跑。
- 允许新增 single-use detached launcher、定向测试和唯一 v7 Harness 输出根；
  禁止读取 provider config、创建新 admission、联网或修改历史冻结证据。
- helper 继续在 child 前 scrub 全部 provider key/consent 环境项，只使用进程作用域
  Git safe.directory，并记录运行前后 verifier/helper hashes 和直接 child exit。
- 验收：launcher/verify PowerShell parse、定向测试、Ruff/compile/conventions 通过；
  只启动一次，等待 receipt 自然终态。只有 exit 0、13/13 PASS 和唯一
  `Verification failed=0` 才能建立下一非授权 gate。

### Gemini Public-v5 recovery segment 0 技术闭包并停止 — 2026-08-06 04:40 +08:00

- 新 non-authorizing Harness gate v4 已绑定 v6 的直接 exit 0、13/13 PASS、
  pytest 1538/1/3、183 条预期 RuntimeAuditor 阻断和六项当前前置证据；manifest
  `d79faf97...e1e9a`，gate 自身 provider/result authorization=false。
- 新 single-use wrapper 真正绑定 `gemini_public_controller_v5`、recovery-v5
  candidate 和 exact admission；没有改写名称相近但仍绑定 v4 的历史 wrapper。
- America/Los_Angeles 配额日 `2026-08-05` 的 segment 0 已单次完成：1/1 记录、
  1 次 provider call/transport completion、exact `gemini-3.6-flash`、官方 response
  ID 存在、free/USD 0、retry/tools/effects=0/false/false。技术 review 全部检查
  PASS，runner failure 0；科研 outcome/result admission 保持 false。
- wrapper receipt SHA `a881799f...b3de`、review manifest `86e48d12...560c2`；
  20/20 定向回归、Ruff/compile、PowerShell parse、conventions 12/12 通过，相关
  正式进程最终 0。新增源后未再跑完整 Harness，F-PAPER-002 继续 `in_progress`。
- 详细报告：
  `docs/research/paper_v2/reports/M3_PI_Guard_Gemini_Public-v5_segment0阶段报告_2026-08-06.md`，
  SHA-256 `76137e6b...eb05`。按 owner 指示到此停止，不自动执行下一 segment。

### v6 非授权门禁与 Gemini Public-v5 单日段包装器 — 2026-08-06 继续实施

- 目标：把已通过的 fresh Harness v6 转换为可重放、仍不授权 provider 的
  closeout gate，并为 Gemini Public-v5 recovery 候选建立全新 single-use
  单日段包装器；历史 gate-v3、旧 wrapper、v4/v5 失败证据均保持不可变。
- 允许文件：新的 gate/controller wrapper 与定向测试、新生成的 gate/admission/
  run receipt、必要的 Harness 状态与验证清单；禁止修改历史冻结输入、旧输出根、
  provider ledger 和旧 receipt。
- 准入边界：gate 本身不得授权网络、provider 或结果访问；只有 v6 证据、v5
  失败审计、Git 资格化、Day-1、Adaptive 顺序、Flash merge、Gemini-v5 candidate、
  当日免费层账本和精确 prospective admission 全部通过，才能执行一个最小未触碰
  Gemini 日段。自动重试、付费、provider tools 与真实 external effects 均为零。
- 验收：新 gate 可独立重放，wrapper PowerShell 语法和负例测试通过；若精确当日
  准入成立，只运行一次最小段并封存 outcome-blind 技术 review/receipt。完成后按
  owner 最新指示停止并提交报告，不继续扩展矩阵。

### Word 阶段报告完成并执行最终停止 — 2026-08-06 03:58 +08:00

- 按 owner 最新指示，本轮没有恢复任何新正式实验；最终只读检查确认 Harness、
  Public、Adaptive 和 provider 正式进程仍为 0。
- 已将验证后的阶段报告 artifact 转为可直接转交他人的 8 页 Word 技术报告：
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段技术状态报告_2026-08-06.docx`，
  SHA-256 `a0d088d2f6a1a8554bb6ea0c2bbdc5c0e34755f9bf689e2267ede3be01da531b`。
- 报告含 4 个头部指标、2 张解释性图、2 个审计表、完整 SHA-256 附录，严格
  区分 v6 工程绿色、Flash 物理闭包与 Gemini/Adaptive/盲测未完成状态。
- Word 以 8 页 PDF/PNG 完整渲染并逐页检查；表格几何 7/7 精确通过，图片 2/2
  具有替代文本，可访问性 high=0。5 个 medium 仅对应无语义表头的单行 KPI/
  callout 布局表，两个数据表均有重复表头。
- 生成器通过 Ruff 与 py_compile；必需内容扫描通过，DeepSeek/Gemini/Bearer
  secret-format 命中为 0。QA receipt：
  `outputs/report_qa/stage_technical_report_20260806/qa_receipt.json`，SHA-256
  `3e948b02499e7c277aa9eaac9d04b275b1cfc45b12c3c0296eb5a9f226423c25`。
- 本轮零新 gate/admission、零 API/provider/network 调用、零科研 outcome 或
  blind label 访问。F-PAPER-002 继续为 `in_progress`，当前任务已按指示停止。

### 阶段技术报告已交付并停止新实验 — 2026-08-06 03:45 +08:00

- 报告前只读进程复核确认 Harness、Public、Adaptive 和 provider 正式工作负载
  均为 0；没有需要等待的后台任务，也没有停止或重启任何实验。
- 新阶段技术报告已按技术受众结构完成，包含 4 个头部指标、2 个分析图、
  2 个审计表以及定义、方法、限制、恢复顺序和开放问题。
- 报告 source artifact：
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段技术报告_2026-08-06_artifact.json`，
  SHA-256 `c3b992d145c92d4c25f393fe28a8ecb42272cfe939eaefe774b83b4826ee2197`。
  Data Analytics artifact validator 返回 `ok=true`，MCP report renderer
  返回 `ok=true`。
- 报告明确区分：v6 工程基线绿色；Flash 1791 条只是物理证据闭包且结果仍封存；
  Gemini Public-v5、正式 Adaptive、600 条盲测、最终统计和哈希包仍未完成。
- 本轮在 fresh non-authorizing gate 之前停止：零新 admission、零 API/provider/
  network 调用、零科研 outcome 访问、零盲测标签访问。F-PAPER-002 保持
  `in_progress`。

### Fresh Harness v6 完整通过并按 owner 指示停止 — 2026-08-06 03:40 +08:00

- v6 于 2026-08-05 23:08:10 至 2026-08-06 03:30:27 自然运行，receipt
  直接记录 child exit 0、evidence gate PASS、13/13 stage PASS、pytest
  1538 passed / 1 skipped / 3 warnings，唯一终态 `Verification failed=0`。
- verifier/helper 运行前后 SHA 不变；stdout/stderr/receipt SHA 分别为
  `23d9f884...a945` / `0d2da881...0573` / `26e51662...3798`。
  stderr 无 traceback、无 secret-format hit，183 条 RuntimeAuditor 删除阻断均为
  测试预期；相关进程最终为 0。
- 精确 AgentDojo `safe.directory` 只存在于 helper/child 进程环境，冻结 commit
  `089ed468...dbf60` 匹配；global/repository Git config 均未修改。
- 本阶段零 API/provider/network、零新 admission、零科研 outcome 修改。根据
  owner 指示到此停止，不创建 green-gate 后续工件，不运行 Gemini/DeepSeek、
  Adaptive 或盲测。
- 报告：`docs/research/paper_v2/reports/M3_PI_Guard_Fresh_Harness_v5_v6收口报告_2026-08-06.md`，
  SHA-256 `39dc2662...5167`。F-PAPER-002 仍为 `in_progress`，21 天实验尚未结项。

### Fresh Harness v5 失败已冻结；v6 运行前资格化完成 — 2026-08-05 23:10 +08:00

- v5 已自然完成并由 receipt 直接记录 child exit 1：pytest 1531 passed / 1 skipped /
  3 warnings，前十个 stage PASS，后三个证据 stage FAIL，唯一终态为
  `Verification failed=1`。API 环境已 scrub，provider/network authorization=false。
- failure-review v5 manifest `02af896a...7149` 锁定 launch/running/log/receipt 和旧
  helper/launcher；根因归类为沙箱账户对 AgentDojo checkout 的 Git ownership
  拒绝，不是测试、实验或 provider 失败。
- 脱敏 Git 资格化 manifest `f4bbaaac...c7db` 证明精确且仅进程作用域的
  `safe.directory` 可以读取冻结 commit `089ed468...dbf60`，且没有写 global 或
  repository Git config。
- v3 receipt helper 与 single-use v6 launcher 已实现并通过 10/10 定向测试、
  Ruff、compile、PowerShell parse、conventions 12/12 和两个证据重放。当前沙箱
  账户的 ACL 失败已另记 failure log；原项目账户下的离线检查通过。
- 下一步只允许单次运行 v6 完整 Harness。无论结果如何，随后按 owner 指示停止，
  不创建 provider admission、不调用 DeepSeek/Gemini、不运行 Adaptive/盲测。

### Fresh Harness v5 持久终态恢复实施中 — 2026-08-04 04:05 +08:00

- 目标：用全新 single-use v5 运行根持久化 launch/running/stdout/stderr/receipt，
  消除上一轮外层超时后终态丢失；不得复用或改写 v4 及失败运行证据。
- 允许新增 `verify_with_receipt_v2.ps1`、v5 launcher、对应测试和运行工件，
  并将其接入 `verify.ps1`；禁止读取 secret、创建 provider admission 或联网。
- v2 helper 必须在子进程启动前清除所有前沿 provider key/consent 环境项，记录
  child PID、运行前后 verifier hash、直接 OS exit、stdout/stderr hash 和 source
  drift；launcher 必须单次、隐藏窗口、固定新输出根。
- 验收：PowerShell parse、定向测试、Ruff/compile/conventions 通过，随后仅启动
  一次 detached full Harness；只有持久 receipt 直接记录 exit 0 且完整日志末尾
  `Verification failed=0` 时才允许进入下一 provider 准入步骤。

### Gemini v2/v5 离线收尾完成；完整 Harness 终态缺失后停止 — 2026-08-04 04:01 +08:00

- Gemini local-precommit 合同 v2.1 已实现并独立重放通过，manifest
  `accc5941...bb8`；只有官方 response ID、精确模型/payload、本地预提交、
  完整 fsync 链、free/USD0 和零重试/工具/effect 全部成立时，才允许缺失
  provider request ID 的特定 diagnostic 提升为 formal candidate，且不伪造 ID。
- Gemini Public-v5 候选保留历史 1 条终态和 1 条 abort ITT 槽位，只选择
  10 个未触碰 canary，划分为 7 个不超过 18 请求的免费层日段。candidate
  manifest `f00fe601...a472`，write/verify exit 0，执行和结果准入均 false。
- 定向验证通过：v5 3/3 + 注入式 E2E 1/1，runtime v2 20/20，Ruff、compile、
  conventions 12/12；Flash 1791-record merge 继续保持可重放。
- 新完整 Harness 在 3604 秒外层时限返回 exit 124；原高 CPU 子进程继续
  441.6 秒后自然结束，最终相关进程 0。因原始 exit code/stdout 不可恢复，
  本轮完整 Harness 状态为 inconclusive，不能创建新 Gemini admission。
- 本轮 API/provider/network 调用为 0。已按 owner 指示停止，详细报告位于
  `docs/research/paper_v2/reports/M3_PI_Guard_Gemini_v2_v5离线收尾报告_2026-08-04.md`。
  报告 SHA-256 为 `2bc1d1c7...3b29b`；F-PAPER-002 保持 `in_progress`。

### Gemini 前瞻证据合同 v2 实施中 — 2026-08-04 02:20 +08:00

- 已确认 Public segment 1 的阻塞不在 Gemini trace bundle 或公共 evaluator：完整
  bundle 已支持 `precommitted_local_plus_provider_response`，且 Gemini 专用记录
  持久化完整 trace。实际冲突位于 trace-attaching runtime v1，它把通用 receipt
  因缺 provider request ID 产生的 diagnostic 与已闭合 bundle 机械取低后拒绝。
- 本阶段只允许新增前瞻 runtime/store/controller 版本、离线资格化、负例和 Harness
  集成；禁止改写 v1、旧 segment、旧 response、旧 ledger 或历史冻结输入。
- 验收要求：只有本地预提交、payload/模型/response 精确绑定、官方 Google receipt、
  append+flush+fsync、零 open/failure、免费层 USD 0 全部成立时才能从该特定
  diagnostic 提升为 formal candidate；任一漂移必须 fail closed。
- 新 API 执行仍未授权。先完成 focused tests 和新的完整 Harness，再创建全新
  segment/run/execution identity。

### Flash 第二模型离线证据复核完成并暂停 — 2026-08-04 02:05 +08:00

- 新 recovery evidence review v4 对 s0/s1 均确认 evidence integrity PASS，且把
  “零终态重试”等否定边界改为正向检查；历史 v3 工件未改写。s0 的冻结质量门
  仍因 10 diagnostic > 6 FAIL，s1 质量门 PASS，结果访问仍 false。
- 新 second-role evidence merge v1 精确重建 1791 个唯一 work key：12 canary +
  473 closed prefix + 1306 recovery；16 diagnostic 全部保留，4193 calls、
  CNY 1.87793024、retry/tools/effects 为 0/false/false。manifest
  `7fba09cc...8432b`，write/独立 verify 均 exit 0。
- 定向 pytest 8/8、Ruff、py_compile、项目 conventions 12/12 通过；首次 verify
  的约 1 秒外层超时已透明
  记入 failure log，随后按真实耗时完整重放通过。相关进程 0。
- 详细报告 SHA `e55f3bbf...f6ea8`。按 owner 指示停止，不实现 Gemini 新合同，
  不启动 API/Adaptive/blind/Harness。F-PAPER-002 保持 `in_progress`。

### 当前运行已自然收口并停止 — 2026-08-04 01:30 +08:00

- DeepSeek Flash recovery-v3 s0/s1 均自然结束，执行步骤分别完成 652/652、
  654/654 条记录；provider calls 1329/1383，成本 CNY 0.59580836/
  0.49424660，自动重试、provider tools、external effects 均为 0/false/false。
- 两个 wrapper 最终均 exit 1：s0 diagnostic 10 超过冻结分片上限 6；此外 v3
  review 把 `source_terminal_records_retried=false` 直接送入 `all(checks.values())`，
  使本应表达“没有重试”的 false 反而必然否决门禁。历史 review 不改写，科研
  结果准入仍为 false。
- Flash 角色物理记录已覆盖 1,791/1,791：12 canary + 473 closed prefix +
  1,306 recovery；合计 16 diagnostic、4,193 calls、CNY 1.87793024。该对账
  不是结果准入，也未读取科研 outcome。
- Gemini segment 1 自然 exit 1。唯一调用为官方 HTTP 200、精确
  `gemini-3.6-flash`、response ID 存在、provider request ID 缺失；失败发生在
  响应后的正式记录契约检查，不是 429。abort review manifest
  `6d7605dd...d649` 明确同 segment/work item 不可恢复或重试，result=false。
- 定向验证：Gemini abort review write/verify exit 0，Ruff/compile 通过，pytest
  7/7（1 known warning）。相关正式进程当前为 0；按 owner 指示停止，不启动
  新 Public/Adaptive/blind/Harness。详细报告 SHA `20972e4a...dac6`。
- F-PAPER-002 保持 `in_progress`；Fresh Harness v4 是执行前绿色基线，但当前
  新审查源与技术门失败尚无新的完整 Harness 结论。

### Gemini canary segment 1 已预约并单次启动 — 2026-08-04 00:35 +08:00

- America/Los_Angeles 当前配额日为 `2026-08-03`；项目账本此前仅有
  `2026-08-02` segment 0，当前日未预约且无其他 Gemini 正式进程。
- segment-1 admission manifest `93ba06fc...e03a`、文件 SHA
  `1199643e...64e2`：2 个 canary records、最多 16 请求、free tier、USD 0、
  concurrency 1、retry 0、tools/effects/results=false。
- v5 guarded wrapper PID 42336 于 00:34:36 启动一次；它先重放 gate/candidate/
  admission，再原子预约当前项目配额日。不得并发第二个 Gemini workload、重启
  或把 429 项重试。Flash 双分片继续独立运行，共享状态为 0。

### Flash recovery-v3 双分片已精确启动 — 2026-08-04 00:14 +08:00

- Fresh Harness gate-v3 已生成并重放通过：manifest
  `e06188dc...b985`、文件 SHA-256 `018af452...3432`，绑定 13/13 Harness
  PASS 与 pytest 1485/1/3；gate 自身 provider authorization=false、calls=0。
- 两份新 admission 只覆盖 1,306 个从未启动的 Flash work key：s0 652 条、
  CNY 2.04118328；s1 654 条、CNY 2.17094144。manifest 为
  `9674f7f3...622e` / `fde24a50...4f77`，retry=0、tools/effects/results=false。
- guarded wrapper 于 00:13:15 各启动一次：s0 PID 25256、s1 PID 43856。
  它们先独立重放 gate/admission，再创建单次输出根并执行；当前均 alive，尚无
  receipt。不得停止、重启、重复启动或读取科研 outcome。
- 原 12 条 canary、473 条 closed prefix 和 2 条 diagnostic 保持不可变且不重试；
  角色累计投影硬上限仍精确为 CNY 5。Gemini/Adaptive/盲测未并发启动。

### Fresh Harness v4 已自然通过；按所有者指示暂停 — 2026-08-03 20:50 +08:00

- single-use v4 于 20:38:25 自然结束，直接 OS exit 0；13/13 聚合 stage PASS，
  pytest 1485 passed / 1 skipped / 3 warnings，最终 `Verification failed=0`。
- receipt/stdout/stderr SHA-256 分别为 `a9fddc0f...2c1b`、
  `1b1a5305...3d75`、`777e65d1...2c26`；receipt 绑定 verifier
  `33390d65...c6e4`，API 环境已 scrub，provider/network authorization=false。
- 123 条 stderr 是测试预期的 RuntimeAuditor 删除动作拦截；无聚合 FAIL，相关
  helper/child 与旧 Flash wrapper PID 均已自然消失。
- 按用户最新要求，本轮不生成 gate-v3，不创建新的 Flash/Gemini admission，
  不启动任何后续 API、Adaptive 或盲测执行。阶段报告已写入
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性实验报告_2026-08-03_Harness_v4.md`，
  SHA-256 `107c779c...3333`。
- F-PAPER-002 保持 `in_progress`：Flash 1,306 个未触碰项、Gemini 正式矩阵、
  三模型正式 Adaptive、600 条盲测和最终哈希结项包仍未完成。

### fresh Harness v4 已单次启动 — 2026-08-03 16:04 +08:00

- 启动前确认新输出根不存在、相关 Harness/provider wrapper 进程为 0、launcher
  PowerShell parse 通过、v3 failure review 和 Day 1 acceptance 均 exit 0。
- single-use launcher 于 16:03:32 创建
  `outputs/verification/experiment_closeout_fresh_harness_v4_20260803`，helper PID
  37772；`running.json` 绑定当前 `verify.ps1` SHA-256 `33390d65...c6e4`。
- API key 环境变量已 scrub，`network_or_provider_call_authorized=false`，自动重启
  false；当前 receipt 尚不存在。不得停止、重启、复用该根、预生成 gate-v3 或
  启动 Flash/Gemini API。

### interim Harness v3 失败已冻结；fresh v4 已离线就绪 — 2026-08-03 16:02 +08:00

- interim Harness v3 已自然终止并直接观测 OS exit 1：pytest 1456 passed /
  1 skipped / 3 warnings，唯一失败是版本无关的旧静态断言误拒绝合法的
  adaptive v2 Pro admission；其余 stage 全绿，provider/network 未授权。
- 失败 review manifest `67bcdaaa...78cf9` 已冻结。旧测试已改为要求 v2、禁止
  v1，focused 20/20、扩大后的 Flash/Gemini/closeout 组合 38/38、conventions
  12/12 通过；失败运行本身未修改。
- `verify.ps1` 已纳入 Gemini v5/continuation-v2、Flash recovery-v3 和 v3 failure
  review，当前 SHA-256 `33390d65...c6e4`。新的非授权 gate-v3 源和 single-use
  fresh-Harness-v4 launcher 已完成离线资格，但 gate 工件只可在 fresh v4
  直接 exit 0 后生成。
- Flash 原双分片进程和 interim Harness 进程均已自然结束；旧分片前缀与缺失
  wrapper receipt 原样保留。Flash recovery-v3 候选为 1,306 个未触碰项，Gemini
  continuation-v2 候选为 1,779 条；二者目前均未获得新 admission、未执行 API。
- Day 1 三份登记文件当前再次精确复核通过：acceptance exit 0、pytest 2/2，
  未删除、移动或改写交付文件。F-PAPER-002 保持 `in_progress`。

### Gemini v5 对账与 continuation-v2 候选通过 — 2026-08-03 12:56 +08:00

- Gemini v4 segment 0 的 1 条 VIGIL 后处理失败仍保留在 ITT；v5 只读对账
  确认 1 次 provider transport completion，14/14 检查全绿，write/verify exit 0。
  未重写 ledger，未准入科研结果。
- wrapper receipt 恢复工件明确记录 OS exit 未知、未伪造 receipt、不得
  重跑 segment 0；compile/Ruff、pytest 3/3、write/verify 均通过。
- continuation-v2 候选保留 v1 的 1,186 个日段不变，但将激活条件
  改为 v5 aggregate；候选 manifest `fcc80d26...5c95`，付费、Batch、执行和
  结果准入均 false。在 18 请求/日的锁定免费边界下，Gemini 正式续跑
  存在至少 1,186 个配额日的真实日历下界。
- Flash 双分片与 interim Harness v3 仍在自然运行；Harness 已观测到一个
  pytest 失败标记，未中断、未隐藏，待终态日志定位。

### Day 1 公开登记链再复核通过 — 2026-08-03 12:28 +08:00

- 用户放回的第三份公开 verifier receipt 与原始登记字节一致；当前
  inbox 为精确 3/3 文件，三个 SHA-256 均与历史 acceptance 一致。
- 冻结 acceptance 重放 exit 0，定向测试 2/2 通过；Day 1 登记完成
  状态不变，先前的当前重放缺口已解除。本次只读复核没有删除、
  移动或改写交付文件。
- 600 条独立盲测的 authoring/custody 及后续执行/解封/评分仍未完成，
  F-PAPER-002 保持 `in_progress`。

### fresh Harness/Flash canary 通过；Flash 1,779 条双分片正式运行中 — 2026-08-03 11:52 +08:00

- fresh Harness v2 已自然结束并直接观测 OS exit 0：13/13 stage PASS，pytest
  1451 passed / 1 skipped / 3 warnings，最终 `Verification failed=0`；receipt
  SHA-256 为 `91e2af1456044eed60edff79cc0a022e1390e8cd7888630d9d1de6cc627d4a71`。
  gate v2 manifest 为 `8f9fc72c...3fb9e`，gate 本身仍不授权 provider。
- DeepSeek Flash 12 条 Public-v4 second-role canary 已一次性完成：12/12
  formal-candidate、18 provider calls、CNY 0.01232192，技术门通过，retry/tools/
  effects 为 0/false/false，科研结果仍未准入。
- 已生成并复核 policy-aware continuation-v2：1,779 条分为 890/889，candidate
  manifest `18b80a5c...2906`；每分片硬上限 CNY 2.49383904，连同 canary
  投影总上限精确为 CNY 5，自动重试 0、并发上限 2。
- 两个 exact-command admission 均已验证，manifest 分别为
  `a5044d28...26e4`、`1d07da6d...2fec`；结果准入 false。guarded wrapper
  的 4/4 定向测试、Ruff 和 PowerShell syntax 通过，两个全新分片于 11:52:22
  各启动一次（wrapper PID 41632/23180），不得停止、重启或复用身份。
- 独立保管人 Day-1 三文件当前可完整重放，acceptance manifest 仍为
  `94e5a647...745c`；600 条 authoring/custody 尚未完成。F-PAPER-002 保持
  `in_progress`。

### Day 1 三文件重放恢复；fresh 完整 Harness v2 运行中 — 2026-08-03 06:35 +08:00

- 用户补回原始 `custodian_registration_verifier_receipt_v2.json`；文件大小 2438，
  SHA-256 `2b699fe342c70819eac67751417d558fa34f20a7b44a3e0335e2cc97243553c2`，
  与历史 acceptance 精确一致。三文件闭包、28/28 recorded checks、acceptance
  manifest `94e5a647...745c` 和定向测试 2/2 全部恢复通过；标签/provider 读取为 0。
- 新增非授权型 fresh Harness gate v2、单次 detached launcher 和 DeepSeek Flash
  guarded-canary v3 wrapper。它们要求直接 OS exit 0、Day-2 failure review、adaptive
  supersession order、Day-1 acceptance 及独立 public admission 全部通过；gate 本身
  仍不授权 provider，wrapper 保持 retry 0、provider tools/effects false。
- 新 gate/launcher/wrapper 的 py_compile、Ruff、PowerShell syntax 和组合测试
  24/24 通过；其中一次静态测试只匹配带引号 token 的错误断言已修正后重跑全绿，
  不改变执行代码。
- fresh Harness v2 已于 06:35:34 以 PID 31716 detached 启动到
  `outputs/verification/experiment_closeout_day2_harness_v2_20260803`；当前 verify
  SHA-256 `48b5a825ea5c83780e07e1a8a9dad8903596053fb44f0b3d0d86add2c2fa05a0`，
  API 环境变量已清除、network/provider 未授权。已通过 JSON/PowerShell/Shell/
  compile，正在运行完整 pytest；不得停止、重启或并行启动 canary。

### Day-2 exit-1 已冻结；当前 Harness 废止接线已修复 — 2026-08-03 01:31 +08:00

- Day-2 detached Harness v1 自然结束并直接观测到 OS exit 1：pytest
  1438 passed / 1 skipped / 3 warnings，12 个 stage PASS，仅
  `Paper-v2 experiment closeout prospective evidence` 失败；失败命令是已被 v2
  顺序门永久废止的 Pro-50 v1 `--verify-admission`。运行未授权 provider/network。
- 新的只读失败审查
  `experiment_closeout_day2_harness_failure_review_v1.json` 已冻结该事实；manifest
  SHA-256 为
  `230fc98bec481488898310428c39c8fa87d03790ab422c6258edeaaadf6e398f`，
  工件文件 SHA-256 为
  `4a47912a531c73b8368d371b83aca352f949ac7b50bab7378c61e2383b119a70`。
- 当前 `verify.ps1` 已用 `adaptive_execution_order_gate_v2 --verify-review`
  替换 Pro-50/Flash-50 两个陈旧 admission 检查，并显式验证 Day-2 failure review
  和 Day-1 acceptance；历史候选、admission 和先前 Harness review 均未改写。
- PowerShell 语法、Ruff、编译和定向测试 14/14 通过；移除三类 API key 环境变量
  后，closeout freeze、Gemini public/continuation/adaptive、两个 second-plan 及
  Pro/Flash candidate 等 10 项离线复演全部 exit 0。当前 `verify.ps1` SHA-256 为
  `1487b13edbee5f806385726068eb92d5afa3194b0d095c9cae8a66d73e082303`。
- 新的完整 Harness 仍不能启动：Day-1 acceptance 的第三份 verifier receipt
  缺失会使其必然失败。该外部门恢复后才创建 fresh Harness v2 receipt 和
  provider canary gate；F-PAPER-002 保持 `in_progress`。

### Day 1 历史完成；当前证据重放缺少独立验签回执 — 2026-08-03 01:19 +08:00

- 对用户所称已完成的交付执行当前文件系统复核后，
  `external/independent_blind/day1_registration_inbox` 只有公钥和
  `custodian_registration_v2.json` 两份文件；必需的
  `custodian_registration_verifier_receipt_v2.json` 不存在。
- 现存两份文件的 SHA-256 仍分别为
  `86db8a9ddebf0d5817226ed0f6ed5e99ca7b4d6b1d219d01670cf03fa0bde3bb` 和
  `02e8282f61727b79eca62b3983c1d36748b5f9a5e93ce5f79c2e11105a88312b`，
  与历史 acceptance 记录一致；未发现它们发生漂移。
- 当前验收重放按设计 fail closed：定向 pytest 为 1 passed / 1 failed，失败
  原因为 inbox 不是精确三文件闭包。历史 acceptance manifest
  `94e5a64710dbcef941375c257e210ab8ea424a0d0b975e50e86c0509e8df745c`
  保留不改写；它继续证明 Day 1 当时完成，但原始回执恢复前不能支持当前
  三文件全链重放。
- 常用项目目录和用户交付位置仅找到 pytest 负例产生的临时同名文件，明确禁止
  将其当作第三方回执。目录 LastWriteTime 显示文件在验收之后的
  `2026-08-02 23:37:43 +08:00` 才消失；当前没有证据归因到具体进程，且本轮
  没有文件删除命令。Day 1 完成和技术时钟不追溯撤销，但最终证据重放为
  `blocked_missing_verifier_receipt`，后续 blind execution 与 fresh Harness
  仍需原始回执恢复；F-PAPER-002 保持 `in_progress`。

### Day 1 已完整完成：独立保管人登记验收通过 — 2026-08-02 23:26 +08:00

- 真实第三方已向
  `external/independent_blind/day1_registration_inbox` 交付精确三件公开登记工件：
  公钥、`custodian_registration_v2.json` 和独立验签 receipt；开发者没有接收
  私钥、身份声明明文、候选或标签。
- 使用 v3.4 包内冻结 verifier 重放后，精确三文件闭包、登记签名、独立验签、
  保管人与验签人分离、零标签和 28/28 已记录检查均通过；状态为
  `custodian_registration_verified_clock_may_start`。
- 新增 developer-side 验收器
  `experiments/paper_v2/independent_blind_day1_acceptance_v1.py`，生成
  `protocols/paper_upgrade_v2/independent_blind_day1_registration_acceptance_v1.json`；
  manifest SHA-256 为
  `94e5a64710dbcef941375c257e210ab8ea424a0d0b975e50e86c0509e8df745c`。
- 验证：验收器 write/verify 均 exit 0，定向 pytest 2/2 通过。全过程打开
  私钥 0 次、身份声明明文 0 次、标签 0 行，API/network/provider call 和真实
  effect 均为 0；正式盲测执行仍未授权。
- 因此 21 天结项计划的 Day 1 前置门已满足，技术时钟可从登记 receipt 的
  `2026-08-02T15:06:47+00:00` 开始。按用户当前指令，600 条 authoring、
  custody、3,600 条运行、标签解封和评分暂缓；F-PAPER-002 继续
  `in_progress`，不得表述为独立盲测完成。

### Python-first Markdown 单目录保管人审查包 v3.4 已验证；等待真人登记 — 2026-08-02 21:19 +08:00

- 唯一可交付目录为
  `docs/research/paper_v2/reports/M3_PI_Guard_Blind_Custodian_Review_Package_v3_4_python_final`；
  根 `README.md` 是唯一权威操作指南，所有审查源、冻结 slots、模板、
  schema、测试和 manifest 都在同一目录；无 Word、无 PowerShell wrapper、
  无永久环境变量。
- physical manifest SHA-256 为
  `43a6c80a454659167419ccabbf0ef33cb924fefee73fe5583d499e6eb1ac4651`，
  embedded digest 为
  `644a0961d6bd7b6d5495191dc0672359678324715942d993513ee725c8f7f089`；
  45 个物理文件 = 44 个 manifest 条目 + manifest 自身，由 39 个显式
  allowlist source 和 5 个 generated support 组成。
- 核心 SHA-256 为
  `f4f4b75bc4d174c9c824d7c5fe60f2ed8a4402ec29f657ac0c8b5866c87bbfb4`；
  v2 test SHA-256 为
  `469823985012270348cd0345232bb949b23f6af84a6e9175d0ee68c972de4c78`。
  嵌套 `gold_label` 重签名注入、completed→provider_failure/timeout 重哈希
  伪造均被拒绝。
- 验证：源码 v1+v2+v3 50/50，成品包内 33/33，Ruff、编译、JSON/schema、
  `verify-pristine`、`verify`、`status`、`show-next` 和项目规范 12/12
  全部通过；独立 reviewer 最终 verdict 为 GREEN。路径/用户/运行时
  token、secret、PEM、`.env`、PS1、Office/PDF 和 work 真实文件均为 0。
- A 只是打开私有 labels 的工件/哈希/签名全链复核；B 只读公开
  scoring release 并做 developer-safe 签名/完整性验证。两者均诚实声明
  `semantic_recomputation=false`；逐案例语义仍需隔离人工复核。
- v3/v3.1/v3.2/v3.3 已标记为 rejected diagnostic，manifest 必然 fail closed，
  不得交付。本轮未读 credential/真实 labels，未调用 API/network，未执行
  真实 effect。真实第三方尚未登记、未签名、未生成 600 条，因此
  F-PAPER-002 保持 `in_progress`，21 天时钟仍未启动。

### Python-first 单文件夹保管人审查包改造中 — 2026-08-02

- 用户要求以 Markdown 取代 Word 作为当前保管人操作入口，并把所有需要第三方
  审查的非秘密材料放入同一个自包含文件夹；保管人流程改为单一 Python 入口
  及子命令，不再要求运行 00–18 号 PowerShell wrapper。
- 配置只允许通过命令行参数、包内非秘密相对路径配置或进程内值传入；不得写入
  用户级/系统级永久环境变量，不得把 API key、口令、私钥、真实标签或候选内容
  放入审查 manifest 或不可变审查区。
- 允许修改：独立盲测 v2 工具包构建器、对应定向测试、新版本审查包、相关 Markdown
  与 Harness 状态。禁止修改：历史冻结输入、旧 `_v2_final` 工具包、paper-v1、
  既有正式结果、真实秘密或第三方尚未生成的候选/标签。
- 验收：新目录必须包含根 `README.md`、单一 Python CLI、全部被审查源码/模板/
  冻结 slots/接口、文件清单及哈希 manifest；pristine verifier 必须拒绝缺失、篡改、
  多余不可变文件、符号链接和工作区污染；定向测试、Ruff、项目规范与 Markdown
  链接/命令审计必须通过。真实保管人登记仍是外部待办，21 天时钟不因本改造启动。
- 独立审查已实证三个交付前阻断项：标签解封必须重新绑定并复验实际 3,600 行
  output package；registration 必须使用精确 schema 并递归拒绝 label/gold 等
  敏感语义；registration 与后续 custody/release/scoring 时间链必须按 aware
  ISO-8601 单调且拒绝明显未来时间。以上修复及伪造/逆序负例通过前，新包不得冻结。

### 第三方保管人工具链与 Word 操作手册已完成；等待真人登记 — 2026-08-02 18:32 +08:00

- 已交付独立盲测 v2 保管人工具包与 34 页中文操作手册。手册明确区分
  `D:\M3_Blind_Custodian_v2` 保管人工作目录和本仓库根目录这两个执行边界，
  逐项列出应保管/交付/禁止交付的文件，
  并给出 00–18 号 PowerShell 命令、Ed25519 登记/签名/独立验签、600 条
  execution/label 确定性分离、3,600 条输出封存、标签解封、独立评分和最终
  评分签名流程。
- 唯一有效工具包为
  `docs/research/paper_v2/reports/M3_PI_Guard_Blind_Custodian_Toolkit_v2_final`；
  内嵌 manifest SHA-256 为
  `9aaffe0120ff93ff3df9a93e955378b37000dd088da62a96eb66f28f086edac8`，
  冻结 slots SHA-256 为
  `4ec78a15bf87473d56d9c4a1bb59f6fadd0d8fed76adf66a567c5e794b79a0a8`。
- 最终 DOCX 为
  `docs/research/paper_v2/reports/M3_PI_Guard_第三方独立盲测保管人操作手册_2026-08-02.docx`，
  SHA-256 为
  `900db3b501d0ee50289af637e2f6c5d69105125d06af24c73659a2b18dd16fa3`。
  结构验证通过：42 个标题、65 张表、1 幅流程图、23 项必需内容、13 项禁用
  内容、0 表格几何问题；可访问性 high/medium/low 为 0/0/0，LibreOffice
  直出 34 页并逐页人工检查无裁切、溢出或跨页断行。
- 独立盲测 v1/v2/工具包/仓库布局回归共 47/47 通过，Ruff、项目规范审计
  12/12 与文档验证均 exit 0。
  验证过程读取 credential=0、blind label=0，模型/API/network call=0，
  provider tools/真实 effect=0。
- 这只完成了“可交给第三方执行”的工程基础，不等于已经登记保管人或完成
  独立盲测。真实第三方仍须亲自填写身份声明、在工具包外生成并保管私钥、
  完成独立验签与后续 authoring/custody；F-PAPER-002 保持 `in_progress`，
  21 天结项时钟仍未启动。

### Day 1 工程基线已完成；结项时钟等待第三方保管人 — 2026-08-02 16:02 +08:00

- 当前 runtime/experiment 工作树的完整 Harness 已自然完成：13/13 聚合阶段
  全部 PASS，pytest 为 1,365 passed、1 skipped、3 warnings，stdout 中
  `FAIL:` 为 0，唯一末行标记为 `Verification failed=0`，无 Python traceback。
- 宿主命令通道在 3,604 秒超时，但子进程继续运行至自然终态；父 wrapper
  因此未写正常 `receipt.json`。恢复审查没有伪造 OS exit code，而是锁定
  stdout/stderr、wrapper、`verify.ps1` 哈希及末尾立即
  `exit $script:Failed` 契约，推导 effective exit code=0。
- 恢复审查 manifest 为
  `22954e84b5a6f97c54faf25f9d972815e66c5a56262c6b00750643cb25eebec1`；
  它明确区分“运行前工作树完整 Harness 通过”和“运行后新增恢复证据代码”。
  后置可执行增量没有修改 runtime/controller/verify 脚本；状态/移交文档另行
  更新并校验。聚焦 pytest 2/2、Ruff、py_compile 通过，因此新 canary 的技术前提满足，但仍需独立
  candidate/admission/quota reservation 才能调用 provider。
- 本次没有读取 credential，没有 API 调用、admission、quota reservation、
  费用、provider tool、真实 effect 或 scientific outcome access。
- 历史 v7 只读失败证据继续不可恢复。工程 Day 1 已完成；但第三方盲测
  保管人尚未登记，按锁定假设，21 天结项时钟尚未正式启动，F-PAPER-002
  保持 `in_progress`。

### 21 天实验结项计划已获授权，Day 1 基线进行中 — 2026-08-01

- 本轮只完成实验、证据链和工程验收，不撰写论文或 JISA 投稿材料。
- 已锁定正式范围：保留历史 `formal_matrix_controller_v7` 失败证据且不恢复；
  完成 DeepSeek V4 Flash 与 Gemini 3.6 Flash 公共矩阵；完成 Pro/Flash/
  Gemini adaptive 面板和 hardest-20；完成第三方 600 条独立盲测与最终
  统计/Harness/哈希结项包。
- 负面结果允许如实结项，但证据链、独立准入或完整 Harness 失败不能结项。
  历史冻结不修改，终态项不重试，provider tools/真实 external effects 保持 0。
- Day 1 预检确认 Python 3.13.5 可用、无活动项目实验进程、历史 v7 abort
  工件存在；工作树原有 324 个状态项全部保留，不做 reset、清理或覆盖。
- 第三方保管人及其封存候选仍是外部输入；在真实 custodian manifest 到位前，
  独立盲测只推进接口和零内容资格，不生成或代填候选/标签。
- 已生成并验证 1,791 条 Gemini 同构公共计划、79,000-query adaptive-v2
  扩展、v7 不可恢复审计、600-slot 盲测导入/评分接口及结项候选；这些步骤
  均为零网络、零 credential、零科学结果访问。
- Gemini public-v1 在执行前发现 VIGIL JSON payload 未纳入 commitment，v2
  随后又在执行前发现跨 work item 累计 usage 缺少 run 级共享 registry；两者
  均以 supersession review 封存为 0 调用。public-v3 也在 0 调用状态下因未按
  project quota day 强制 18 RPD 而被封存；原 v3 wrapper 已 fail-closed。
- 新 public-v4 把原 12 条 canary 保持源顺序拆成 8 个独立 quota-day identity：
  四个 VIGIL work item 各自占一天，八个 M3 work item 按两条/天；每段冻结的
  provider-call 最坏上界不超过 18。新增 project-day append-only reservation
  ledger，禁止公共与 adaptive 在同一 Gemini quota day 重复占用。
- DeepSeek Flash 12 条 public-v4 second-role canary admission 已写入；输出根
  仍不存在。任何 API canary 都要等待当前完整 Harness 的 durable receipt
  为 exit 0；历史/新 admission 均不自授权结果准入。
- Pro adaptive 已把历史 8×50 的 374 条终态查询/562 次调用/CNY 0.552805
  作为只读来源锁定。因旧 trace 的 usage summary 绑定原 CNY 5 policy，正式
  50/200/500/2000 四阶段不得原地扩大旧 ledger 的 ceiling；改为独立 run、
  identity、ledger、trace/output root，并只复制哈希绑定的 checkpoint。
- DeepSeek CNY 180 是 Pro+Flash adaptive 的总熔断。发现首版 Pro-only 预留
  会挤占 Flash 后，在零调用状态下把 Pro 四阶段改为 CNY 10/20/35/85，合计
  CNY 150；加历史前缀为 CNY 150.552805，并为 Flash 50/200 保留
  CNY 29.447195。Pro-50 candidate/admission 已重新绑定，尚未读取 credential
  或启动网络。原 diagnostic task
  `M3V2-D-050-A1` 保留 ITT 且永久禁止重试。
- hardest-20 的技术诊断补位规则已在查看预算 500 新结果前冻结：诊断/不完整
  项保留 ITT 但不得饱和重放，按固定 seed 的确定性排序取下一 eligible case，
  eligible 少于 20 时技术门失败而非人工补选。Pro/Flash/second-plan 相关
  定向测试现为 22/22 通过；Flash-50 candidate/admission 已以独立根和
  CNY 5 stage fuse 冻结，尚未读取 credential 或触网。
- Gemini 免费层证据是 5 RPM、20 RPD，本地保留 2 次请求后最多 18 RPD；
  控制台 1,000 RPM/10,000 RPD 为 paid Tier-1 对照。1,791 条矩阵至少需要约
  100 个配额日；按冻结 work-item 调用上界安全装箱则需 1,194 个配额日。
  12 条 canary 是矩阵正式前缀，continuation 仅含 1,779 条 pending 项；
  Gemini public/adaptive 合计理论下界 323 个配额日，按锁定 canary 的前瞻
  最小值为 330 天，预提交最坏安全上界 3,194 天；qualification manifest 为
  `31861f65d7dc38c684730d3b4c5b20c35cc76d23bdf18436d4e9f2374039a7a6`。
  21 天自动顺延，不能以分片并发绕过 project-level RPD。
- 发现新 prospective 工件的草案时间晚于本机时钟，以及 Gemini-v4 锁定了
  不存在的计划文件；两项均在 0 调用/0 结果时校正，受影响候选全部重建。
  当前时间链使用文件实际创建时间，Gemini-v4 改为锁定权威的 1,791 行
  `gemini_public_execution_plan_v1.jsonl`。
- Gemini public pending-only continuation 已离线冻结：12 个 canary work key
  从 1,791 行矩阵精确扣除，剩余 1,779 条按源顺序组成 1,186 个 quota-day
  segment，并归入四个连续 logical shard（297/297/296/296 segments）；候选
  manifest 为 `2cd8e8829f77868249756cb57db62b9b497e3d4a53aa036260a755f14d4153b6`。
  它仍是 non-executable，必须等待 v4 canary aggregate technical pass。
- Gemini adaptive 免费层容量计划也已离线冻结：20 任务按 query index 轮转，
  4,000 个最大查询槽拆为 2,000 个 quota-day segment，每天最多 2 个查询、
  16 次 provider calls，保留 2 RPD；candidate manifest 为
  `46080eb36ccbd1f6bb9cac0b1d1740668fff84bfac1553b8abf26b93540107dc`。
  该工件不授权执行；每日 successor 必须跳过已 success/diagnostic 任务的未来槽，
  且不得重放任何已触碰 work key。
- Day-1 完整 Harness 的 pytest 子段为 1,266 passed、1 skipped，但宿主在历史
  replay 中断，未留下 aggregate marker 或 `receipt.json`。该次运行被定性为
  inconclusive（既非 pass 也非已证实 fail），旧日志只读封存；正式 API canary
  继续等待当前工作树的新完整 Harness exit 0 receipt。
- 修正后的 Gemini public-v4 canary candidate 已完成全量离线重建：12 条正式
  前缀拆为 8 个 quota-day segment，单段 provider-call 上界 16，manifest
  `80ac8930af5107001fecbb756d25a35d2e5d5027e94d164a5987c958a60751eb`；
  当前仍无 admission、无 quota reservation、无 API 调用。
- Gemini public pending-only 每日 successor controller 已实现：每个 schedule
  segment 绑定当天、fresh identity/root、独立 record/attempt/call/trace 和全局
  免费层 day reservation；必须串行继承上一个 technical review，且在 v4
  aggregate pass 前 fail closed。聚焦单测 3/3、py_compile、Ruff 已通过。
- Gemini adaptive daily successor 与专用 append-only query store 已实现：按
  round-robin schedule 从上个已准入 review 选择最早两个 eligible query，
  每天 fresh identity/root，逐任务复制哈希绑定 checkpoint；每个 query 原子
  记录 started/terminal、online projection、Guard/effect、Gemini trace、官方
  response IDs、完成调用数与实际请求尝试数。q1→q2 exact-prefix 恢复、终态任务
  跳过、checkpoint gap、paid-tier tamper 和真实注入 trace-record 绑定均有测试；
  当前相关合并测试 10/10 通过，Ruff/py_compile 通过，仍未创建 daily candidate、
  admission、quota reservation 或网络调用。

### Public-primary 已准入并独立复核；阶段报告完成后按 owner 要求停止 — 2026-07-30 14:15 +08:00

- Public-primary 最终覆盖 847 个唯一案例、5,082 条六条件记录，其中攻击
  600、良性 247；76 条 diagnostic 全部保留在 ITT，排除数为 0。主结果只
  来自可审计的官方 `deepseek-v4-pro` 链，共 12,808 次调用、记录成本
  CNY 11.9909764，自动重试/provider tools/真实 external effects 均为 0。
- M3-full 攻击 unsafe-effect 为 38/600（6.33%），结构化基线为
  133/600（22.17%），policy-only 为 13/600（2.17%）。full 相对结构化
  下降 15.83 pp，但相对 policy-only 上升 4.17 pp；良性工具 TCR 为
  49/168，对结构化基线 103/168 低 32.14 pp。因此机制论文门继续
  `fail_redirect`，论文路线锁定为 authorization uncertainty 与
  security–utility empirical fallback。
- 冻结的 1% diagnostic 质量门没有被豁免；分析 v5 和独立 reviewer 均把
  76 条 diagnostic 留在分母，零 provider call、零记录改写、零结果排除。
  科学证据完成度为 869/1200（72.4167%），投稿就绪度 68%，没有达到 80%。
- 最终 Word 报告为
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-30.docx`，
  SHA-256
  `6eeba31b59263160843bab1c23458fcee1ab89021f333ee7ea265a7be36bfd56`。
  报告共 16 页、6 图、17 表、7 个外链；结构 QA、3 个报告测试、Ruff、
  a11y high/medium/low=0/0/0 均通过，WPS 只读渲染的 16/16 页已逐页检查。
- 全量 Harness 首轮保留透明失败证据：1265 passed、1 skipped，唯一测试
  状态隔离问题和一个 PowerShell 参数边界问题均已修复；修复后的四项
  定向复核全部退出 0。未因报告交付重跑数小时全量链。
- F-PAPER-002 保持 `in_progress`。按 owner 指示，本阶段报告交付后立即
  停止；未启动 v7、第二模型、正式 40/20 自适应面板或独立盲测。

### Adaptive 8 任务已准入；Public-v2 进入逐片线性恢复 — 2026-07-30 06:20 +08:00

- Adaptive-v2 的 8 个任务已完成 374 个终态查询、562 次官方调用，
  总记录成本 CNY 0.552805；旧 v2 的 174 个终态查询未重试。独立结果准入后，
  budget-50 unsafe-effect 为 0/8，Wilson 95% CI 0–32.44%。该结果仅是探索性
  成本金丝雀，不替代 40 任务、多预算、第二模型正式自适应面板。
- Public continuation-v2 的四个原进程均自然退出：s0/s1/s2/s3 的封闭前缀为
  232/126/140/130 条。新增 v3 逐片恢复只执行未触碰 work keys，使用增量
  append-only ledger，自动重试、provider tools、external effects 均为 0。
- s1 已完成 1265/1265，71 条诊断全部保留在 ITT。原冻结 1% 质量门槛因此
  正确失败，但其余终态、哈希链、预算、trace、ITT 完整性检查全部通过；
  新的版本化审查不豁免 1% 门槛，只把完整证据路由到已经激活的
  security–utility empirical fallback。
- s0/s2/s3 恢复进程仍在运行；截至本检查分别为 268/1265、355/1264、
  273/1264，stderr 均为空。未读取或聚合其 scientific outcomes。
- 已实现但尚未激活 Public primary 的完整性合并、独立结果准入和 5,082 条
  ITT 分析链；10 个聚焦测试、Ruff 和 py_compile 通过。只有四片全部终态、
  outcome-blind 合并通过并写入单独 result admission 后，才允许读取结果。
- 当前 full Harness 暂不运行，因为三个正式 API 恢复进程仍存活；最近一次
  完整绿色基线仍为 1,188 passed、1 skipped、3 warnings、
  `Verification failed=0`。F-PAPER-002 保持 `in_progress`。

### Public continuation-v1 已封存，fresh continuation-v2 四分片运行中 — 2026-07-30

- 原 continuation-v1 四片均在首条正式记录完成后因 shard/global
  `abort_ceiling_cny` 重建策略不一致而 fail closed；合计 4 records、
  13 calls、CNY 0.014446，0 open attempts、0 retries/tools/effects。
- 内容无关 abort review
  `public_primary_continuation_abort_review_v1.json` 已锁定旧根，manifest
  `be0d736abf4f856871978e472ae0408d15c51bd92cb2ef59c7dee4375b99995b`；
  旧记录不得恢复、复用或进入结果分析。
- fresh continuation-v2 使用四组新身份重新覆盖全部 5,058 条，分片仍为
  1,265 / 1,265 / 1,264 / 1,264，每片硬上限 CNY 4.9，自动重试为 0。
  v2 qualification、candidate、四份 single-use admissions、12 个聚焦
  测试、Ruff 和 py_compile 已通过，候选 manifest
  `d05562406e081ae6c2b33fafc7e9f8963b8f04966ec4f9a819fd7dd397271692`。
- 四个 exact-command 进程于 2026-07-30 01:43:51 +08:00 启动；均已越过
  旧版本的首条失败点并持续写入 append-only records/traces/budget。
  当前仍不得读取或聚合 scientific outcomes；四片终态和 outcome-blind
  technical merge 通过前，public 结果不准入，科学分保持 753/1200。

### Adaptive cost-canary v1 已封存，fresh v2 运行中 — 2026-07-30

- adaptive v1 的首个 query 已完整终态并绑定 1 次官方调用，但桥接层误读
  不存在的 `effective_guard_decision` 后退出；旧根 1 query / 1 call /
  CNY 0.002271、0 open，永久不可恢复、重试、复用或分析。
- abort review manifest 为
  `a44f398069d0b1d7ecdeb3063878021993bf1dd554c9dd425793065ea1764c6e`；
  scientific outcome 未聚合或报告。
- fresh adaptive-v2 candidate manifest 为
  `6570795d5da00b5d6093ad5997ee2720d0f1644cb0313d02dfd2e88af446578d`；
  使用新身份和输出根、CNY 5 新硬上限，旧 query 不复用。8 个聚焦/注入
  transport 测试、Ruff、py_compile、candidate/admission 验证通过。
- v2 PID 9788 于 02:04:59 +08:00 启动并已越过旧故障点；formal
  continuation/result admission 仍为 false。完成后只先生成 outcome-blind
  technical cost review。

### Public-v4 技术金丝雀、主模型分片候选与对外阶段报告均已验证 — 2026-07-29

- Public-v4 primary technical canary 已单次完成 24/24 条记录、64 次官方
  DeepSeek 调用，0 diagnostics、0 operational failures、0 retries、
  provider tools/external effects=false；累计 CNY 0.0521812。
- outcome-blind technical review 的全部检查通过，允许进入矩阵 continuation；
  但 result admission=false，未读取或聚合 unsafe-effect、task-completion
  或条件效果，因此当前科学分仍为 753/1200（62.75%）。
- 已冻结 primary 剩余 5,058 条记录的四分片候选：1,265 / 1,265 /
  1,264 / 1,264；每片 CNY 4.9，上限合计 CNY 19.6，自动重试为 0，
  四片互斥且排除已完成的 24 条 canary。
- 当前工作树完整 Harness 自然完成并退出 0：1,188 passed、1 skipped、
  3 warnings，`Verification failed=0`。stdout SHA-256 为
  `806033e70b4d538d2c8656221cb2590c34afa8deaa53fdee7f061ed8fe91a7fc`。
- 已生成可供导师/合作者阅读的 17 页 Word 阶段报告，包含 6 幅分析图、
  19 张固定几何表和 11 个前沿来源链接；DOCX SHA-256 为
  `5f89bdc294892658b8ca8d634f8c8d6810f92367abd345f5b026ee91d7d1e7d4`。
  结构审计与可访问性审计均通过，17/17 页已用 Microsoft Word 渲染后逐页
  检查。LibreOffice/soffice 不存在，故保留该 fallback 披露。
- 报告制作期间没有创建四片 active admission，也没有启动新的 API 进程。
  下一实验动作是逐片创建 single-use admission 并执行 5,058 条 primary
  continuation；公共结果仍须在 6,873 条全部终态后单独准入。

### Public-v3 primary 在首个 M3 identity binding 处停止，必须转 Public-v4 — 2026-07-29

- 已执行 owner 授权的唯一 Public-v3 primary 命令；12 条 AgentDojo records
  完成后，首个 M3 item 在 provider calls 完成、离线 evaluator 阶段以
  `offline material is not bound to this frozen work item` fail closed。
- v3 永久状态：25 attempt events、12 terminal、1 open、12 records、
  33 provider calls、13 trace files；26,184 prompt、2,534 completion、
  cache hit/miss 22,656/3,528，CNY 0.0263544，budget paused=false。
- 根因：v3 resolver 的 inherited `resolve()` 用 public-v1 plan identity
  计算 binding `work_key_sha256`；sandbox material 正确使用 fresh v3 permit
  identity。work key 已能解析，但 identity-bound digest 不同。
- 禁止恢复、重试、补写或准入 v3；未读取/聚合 scientific outcomes。
  下一版本必须显式把 active permit identity 注入 public M3 resolver，并以
  evaluator end-to-end probe 验证 material/binding digest，而非只测 lookup。
- Public-v4 resolver 最小修复已实现：构造器要求 lowercase SHA-256
  `execution_identity`，并覆盖 public M3 plan item 的 binding identity。
  新测试先复现 v3 错误，再验证 v4 evaluator 闭环；4/4 与 Ruff 通过。
- v4 四探针 qualification 已冻结，SHA-256
  `a92a5f3ec565d14421f3575c3dd199475fe1d28d8f050aeae0ac381e37b62c95`；
  3,600 work items、750 bindings、primary/second × attack/benign 均为
  digest match + evaluator completed，0 credentials/network/provider calls。
  v4 controller/candidate/abort review 尚未完成，不能执行 API。

### Public-v3 primary canary 已获 owner 授权，等待 admission 重建与单次执行 — 2026-07-28

- Owner 原文：
  `确认执行上述 Public-v3 primary canary 命令,之后有关这些命令我都允许`；
  UTF-8 SHA-256 为
  `b3467f61a79f47213fefb78087ca3fd590f445800d2017a0a8d99576a2dc03e0`。
- 授权命令 SHA-256 为
  `95e43d63b097d0526184aa68ac0bdcae25396d6be2748576d27131653c4f1b1b`，
  仅绑定 Public-v3 primary、24 条 technical canary、candidate
  `7df71eda75083a36b787659b482549ff3b2a7085b5ad01f8830dd0d2f9a32ef1`。
- 允许：写入 v3 primary single-use admission、读取本地配置以执行该命令、
  顺序调用官方 DeepSeek、写 append-only attempt/trace/budget/record，并在
  结束后生成 outcome-blind technical review。
- 仍禁止：provider tools、external effects、automatic retry、修改 v1/v2、
  重试已完成或开放项目、矩阵 continuation、second model、结果聚合/准入。
  Owner 的未来概括性许可不替代这些独立冻结门禁。

### Public-v3 离线修复与准入前验证完成，等待新 owner 确认 — 2026-07-28

- 目标：不修改 Public-v1/v2 冻结代码、admission、ledger 或结果，新增
  public-plan-aware M3 resolver，并在全新 Public-v3 run/output/execution
  identity 下重新冻结 6,873 条 result-blind 公共矩阵。
- 允许修改：新的 `experiments/paper_v2/*v3.py`、对应 `tests/unit/`、
  新的 `protocols/paper_upgrade_v2/*v3.json`、必要的新 schema，以及
  Harness 状态/验证入口。允许从 v1/v2 导入稳定公共组件。
- 禁止修改：Public-v1/v2 controller/candidate/admission/abort review 和
  append-only 输出；medium v8/v9 结果；paper-v1、E0–E17、V2 冻结；本地
  secret 配置。不得在本阶段读取凭据、发 API、聚合 Public-v2 科学结果。
- 验收：M3 resolver 必须从 public plan 的 `source_reference` 恢复
  evaluator binding；primary/second × attack/benign 至少四个零网络探针通过；
  AgentDojo v2 探针继续通过；错误 medium-plan key、source hash 漂移和身份
  漂移必须 fail closed。
- Public-v3 candidate 必须使用新的双角色 execution identities、run IDs 和
  output roots，哈希锁定 Public-v2 abort review，保持
  execution/result authorization=false，并生成新的唯一 exact command。
- 验证顺序：聚焦 pytest → Ruff/JSON/产物重建 → 当前工作树完整 Harness。
  完整 Harness 绿色后才展示命令并请求新的逐字 owner 确认。
- 已完成：public-plan M3 resolver 覆盖 3,600 个 M3 work items、750 个
  private selection bindings，并通过 primary/second × attack/benign 四探针；
  online state 未改写、credential/network/provider calls 均为 0。
- Public-v3 candidate canonical manifest 为
  `7df71eda75083a36b787659b482549ff3b2a7085b5ad01f8830dd0d2f9a32ef1`；
  primary/second 使用新的 execution identities、run IDs 与尚不存在的
  output roots。admission 不存在，所有 execution/result authorization=false。
- 独立 Stage A 重建退出 0：6,873 rows、18 pairs、4 M3 probes、0 network/
  results。聚焦 pytest 10/10、Ruff、PowerShell/Bash syntax、JSON parse 均通过。
- 完整 Harness 外层通道在 7,204 秒超时，后台自然完成但 aggregate exit
  不可恢复，故不宣称该次 Harness 绿色。改用可恢复全量 pytest，退出码 0：
  1,170 passed、1 skipped、3 warnings，4,468.35 秒，stderr 为空。结合独立
  Stage A 与 changed-surface 门禁，Public-v3 现只等待新的 exact-command
  owner 确认；科学分仍为 753/1200。

### Public-v2 部分执行失败并永久封存 — 2026-07-28 12:52 +08:00

- Owner 逐字确认了冻结的 Public-v2 primary canary 命令。新 admission 只绑定
  24 条 primary 技术 canary、`deepseek-v4-pro`、自动重试 0、provider tools
  false、external effects false；candidate SHA-256 仍为
  `a17ab0926c0003e953b85834b8728a8ac98e360b684780b7fa98f10b9c07250b`。
- 单次执行完成 12 条 AgentDojo 记录后，在第 13 条、首个 M3-v2 work item
  的离线 evaluator 阶段以 `unknown paper-v2 work key` 退出。该 run 冻结为
  12 records、25 attempt events、1 open attempt、29 completed provider
  calls、11 untouched items，禁止恢复或重试。
- 账面用量为 22,169 prompt、1,934 completion tokens；其中缓存命中 17,536、
  未命中 4,633，累计 CNY 0.0259414。27 次调用与 12 条记录交叉绑定；开放
  attempt 的 2 次完成调用有独立 trace 和官方 response IDs，但没有结果记录。
- 根因是 Public-v2 仅替换了 AgentDojo resolver；M3 evaluator 仍默认绑定
  `medium_execution_plan_v2.jsonl`，而公共 M3 work key 只存在于
  `public_execution_plan_v1.jsonl`。
- 内容无关的 `public_primary_canary_abort_review_v2.json` 已冻结，manifest
  SHA-256 为
  `c3e17fe2f74bd807a348202c2ac632c9be6e4f6c2e426c4a8b7a3c5a70d4f1c5`；
  它明确 scientific outcomes 未聚合/未报告、result admission=false、
  run_resumable=false。
- 新审计 Ruff 通过，聚焦单测 2/2 通过（372.40 秒）。当前 feature 保持
  `in_progress`，科学证据分保持 753/1200；任何后续网络执行都必须先离线
  资格化公共 M3 resolver，再使用全新的 Public-v3 run/execution identity、
  candidate、admission 和 owner 确认。

### Public-v1 零调用中止并由 Public-v2 离线修复替代 — 2026-07-28 09:30 +08:00

- 项目所有者逐字确认了 Public-v1 primary canary 命令。激活的 v1 admission
  绑定 24 条 primary 技术 canary、官方 `deepseek-v4-pro`、单次尝试和
  无工具/无外部效果边界。
- 第一次执行在 attempt loop 前因 LFischl Python 缺少冻结 PromptGuard 依赖
  失败。按既有依赖授权安装 Transformers 4.57.6、Tokenizers 0.22.2 和
  Safetensors 0.6.2 后，本地 CUDA PromptGuard 的良性/注入双探针通过。
- 同一批准命令的一次非自动重试在首个 AgentDojo 项写入 `started` 后失败：
  medium resolver 不认识 public-plan work key。v1 现冻结为 1 个 open、
  0 terminal、0 record、0 budget event、0 provider trace、0 provider request、
  CNY 0 和 0 formal result；不得恢复、重试或补写。
- `public_primary_canary_abort_review_v1.json` 独立复核上述账本与两个失败日志，
  verdict 为 `aborted_before_first_provider_request`，并明确
  `run_resumable=false`、`scientific_outcomes_accessed=false`。
- 新的 public-plan AgentDojo resolver 以 `source_reference` 重建原冻结
  binding，而不是复用 medium work-key 索引；4 个 primary/second ×
  attack/benign 离线探针全部通过，0 credential/network/provider call。
- Public-v2 使用全新 run/output/execution identity，保留原 6,873 条
  result-blind work items，同时哈希锁定 v1 abort review 和 resolver
  qualification。候选 canonical SHA-256 为
  `a17ab0926c0003e953b85834b8728a8ac98e360b684780b7fa98f10b9c07250b`，
  `execution_authorized=false`、network/results=0。
- v2 聚焦回归可恢复运行退出 0：11/11 passed，1,164.68 秒，stderr 为空；
  Ruff、resolver verify、abort review verify 和 Stage-A 复现均通过。新的
  active admission 尚未创建。
- 更新后的完整 Harness 于 2026-07-28 11:29 +08:00 退出 0：
  1,158 passed、1 skipped、3 个已知 warning，pytest 3,494.01 秒，
  `Verification failed=0`。三行 stderr 全部为预期的 RuntimeAuditor
  `delete_record` 阻断。Public-v1 abort、Public-v2 resolver、Public-v2
  Stage A、历史证据与当前 V2 冻结均在统一入口内通过。
- 当前只剩新的 API 命令必须再次逐字展示并由 owner 确认；旧 v1 确认
  不得授权 v2。确认前不得创建 v2 active admission 或读取凭据。
- 当前论文证据分仍为 753/1200=62.75%（显示 63%）；本次只有工程和失败
  证据，没有 public 科学结果，不增加分数。

### 34/34 引文权威审计完成，80% 路线按真实算术更新 — 2026-07-28 05:10 +08:00

- 已逐项打开 34 条权威出版社、会议 proceedings、DOI/Crossref-backed 或
  arXiv 记录，完成元数据与摘要范围审计；矩阵现为 24 篇同行评审、10 篇
  预印本。纠正 18 个非规范标题、1 个无依据 Oral 标记、2 个过期预印本
  分类，以及 1 条指向无关生物医学论文的错误绑定。
- 错绑 L20 未被静默改名，而是删除无法核验的 “Virtual Context” 记录并
  替换为经 ICSE 2026 官方页面/DOI 核验的 AgentSpec。VIGIL、DRIFT、
  Task Shield、ARGUS、AuthGraph 等关键竞争边界仍保持原审慎语义。
- 文献矩阵 SHA-256 为
  `ecf952832afe5d474b70aa2141b8f9c05b0bd43d8da47287bcc836c9c3633570`；
  citation manifest SHA-256 为
  `0c6713700b9a77ba5ec9869b2259171ebc986421a135012c4c917fbf1f0c881e`。
  citation/manuscript 专项 7/7、Ruff、manifest `--verify-only` 和 stale-title
  扫描均通过。
- scorecard 据实更新为 753/1200=62.75%（显示 63%），submission readiness
  60%。新增 v3 路线纠正历史 v2 表中“其他九项 620”的算术披露错误；正确
  当前路线为 public +90、adaptive +100、manuscript +25，目标
  968/1200=80.67%。旧 v2 文件和冻结输入保持不变。
- 仍未完成全文 inline citation context、最终 bibliography、投稿日状态刷新、
  public/adaptive 结果、独立盲测和机构 JCR 核验，因此不是 Stage 2.5 PASS。
- 04:38 Harness 在本次 Python/test 更新前已启动，虽仍 CPU-active 且
  stderr=0；它于 06:25 自然完成 1,146 passed、1 skipped、3 warnings、
  `Verification failed=0`。由于启动后发生了 citation/adaptive
  timestamp、v3 roadmap 和测试更新，该绿色结论只能标为 superseded。
  06:26 起基于当前工作树启动新的可恢复权威全量验证。

### 中型稿件完成预结果完整性审计，当前完整 Harness 可恢复重跑中 — 2026-07-28 04:51 +08:00

- 纠正 `results_shell.md` 的过期“矩阵进行中/结果全 pending”状态，从已准入
  `admitted_medium_analysis_v8.json` 回填 480-record disposition、六条件安全/
  工具效用、四项配对比较、ASK/失败/调用/成本/延迟和机制门结论；源文件
  SHA-256 与 result-admission digest 明示在稿件中。
- 当前稿件明确保留三项负结论：M3-full 与 policy-only 均为 0/36 unsafe
  effects，full 未产生模块安全增益；full 对 structural 的工具 TCR 为
  6/24 对 12/24，违反 −5pp 非劣界；机制论文路线保持
  `fail_redirect`，不恢复 SOTA/机制领先声明。
- 新增 medium-only Discussion draft，解释安全—效用权衡、确认负担、授权
  regime 小样本、ITT 失败与四条 prospective public/adaptive 分支；公共和
  自适应表仍全部 pending。结果资产专项测试从权威 admitted JSON 重建数值，
  4/4 与 Ruff 均通过。
- 新增 branch-locked `abstract_shell.md` 和 `figure_table_plan.md`：摘要只
  固定 research/method/medium 证据及 public/adaptive 待填槽位；五图六表
  均绑定未来 admitted analysis，禁止用 missing/failure 画有利零值。
- 预结果完整性审计发现并修复 Methods 的实质漂移：旧文本仍称零
  operational failure 才可通过，但权威 `medium_gate_spec_v2` 在 outcome
  access 前已冻结 10% overall、5% provider/timeout、0 runner failure 的
  mechanism-quality envelope，并允许 technical gate 最多 1% closed
  diagnostic。修订后与 479 formal + 1 diagnostic、459 completed + 21
  retained terminal records 一致。
- `pre_result_integrity_audit_v1.md` 完成 medium 数字、方法和七类 AI research
  failure mode 审计：Modes 1/3/5/6 对 admitted medium 为 CLEAR；citation
  与 shortcut/generalization 仍为 insufficient，故明确不是 Stage 2.5 PASS。
  manuscript 专项 4/4、方法/审计断言与 diff check 通过。
- 04:30 的首个后台全量运行在 pytest 已收集旧 manuscript 断言后发生上述
  文档更新，故其结论不再对应当前工作树；已只终止该自建验证树。04:38
  重新启动当前工作树 Harness，wrapper PID 20860，日志位于
  `outputs/paper_v2/verification/post_medium_results_sync_full_harness/`，
  当前 pytest 慢测试进行中、进程 CPU 活跃、stderr 为 0。

### 自适应 8×50 官方桥接与双台账已完成 — 2026-07-28 04:27 +08:00

- 已冻结 outcome-blind 的 DeepSeek Pro 自适应成本 canary：从 40 个主模型
  任务中按 SHA-256 顺序选择 8 个不同攻击族，每任务最多 50 查询，总计最多
  400 查询；每查询最多 8 次 provider call，独立 CNY 5 硬熔断、并发 1、
  自动重试 0、provider tools/外部效果关闭。
- 自适应 mutation 只替换 M3-v2 `untrusted_content`；trusted user request、
  app context、memory 与 `auto_compiled` authorization 保持冻结。新增官方
  DeepSeek bridge、动态 evaluator resolver、fsync query ledger、provider
  trace/budget call ledger 和 query→call 交叉绑定；Windows work key 使用
  `__`，执行身份与 trace 文件身份一致。
- 新 candidate 为非可执行：
  manifest `52fe67b05409d0a041464b52819de30e657c13b5f6713d4aea51e5b4fa2bbc1f`；
  result gate manifest
  `6dd38864e3735e764affedb2781c981360831914963609a0489b68aab4b13f55`。
  canary prefix、正式 75,000 查询 continuation 与科学结果均需要各自独立
  admission，且正式费用上投影超过 CNY 180 时暂停。
- 验证：新增自适应 20/20；邻接 public/adaptive/provider 回归 45/45；
  注入式 official-shaped transport 贯通真实 M3-full/沙箱/evaluator/trace/
  cache-cost 链且 0 network；Ruff、compile、candidate/gate 复现、JSON、
  PowerShell syntax、约定 12/12 与 `git diff --check` 均通过。
- 当前完整 Harness 启动后超过调用工具 60 分钟上限；真实父/子进程继续
  自然完成，但 stdout/最终退出码已不可恢复，故本轮不能声明
  `Verification failed=0`。上一检查点的 1,126/1/3 绿色 Harness 仍有效，
  但不替代当前新增代码的最终全量结论。
- 04:30 的可恢复重跑已因后续 manuscript/test 同步而主动废止；不得将其
  局部进度当作当前全量结论。当前权威重跑改为 04:38 的 PID 20860。
- 本阶段未读取 key、未发 API、未写 admission、未产生正式结果。公共
  primary 24 条 canary 的 exact command 仍等待 owner 明确确认；自适应
  canary 还需要单独展示和确认其 exact command。

### Public-v1 离线执行层已完成，完整 Harness 正在运行 — 2026-07-28 02:21 +08:00

- 已把冻结公共矩阵展开为 6,873 条不可变计划记录：主模型
  `deepseek-v4-pro` 5,082 条，第二模型 `deepseek-v4-flash` 1,791 条；
  主/次技术 canary 分别为 24/12 条。
- 新增版本化 public 预算、官方客户端、请求/响应 trace、append-only
  record/budget ledger、候选/准入 controller、分析预注册与 result gate。
  Stage-A 资格覆盖 18 个 role/benchmark/condition 路由和身份、预算、恢复、
  工具/效果等负例；candidate、preregistration、result gate 均保持
  execution/result authorization=false。
- DeepSeek 预算固定为公共增量 CNY 25（保留 CNY 5）：Pro 角色上限
  CNY 20、Flash 角色上限 CNY 5；并发 1、自动重试 0、provider tools、
  外部连接和真实外部效果全部禁用。Flash 只支撑跨模型，不支撑跨提供商声明。
- focused public-v1 回归 25/25 通过（298.61 秒），focused Ruff 全过；
  唯一完整 Harness 自然完成：1,126 passed、1 skipped、3 warnings，
  pytest 2,367.05 秒，全部 Harness stage 通过且
  `Verification failed=0`。随后 Stage-A、analysis preregistration 与
  result gate 三项独立复现均 exit 0。
- 已向 owner 展示唯一拟执行命令；完整 Harness 门已经满足，当前只等待
  “确认执行上述命令”。确认后才生成绑定该确认哈希的 primary admission
  并执行一次 24 条 Pro 技术 canary。

### 80% 科学证据执行计划 v2 已冻结，等待 owner 确认 — 2026-07-27 09:53 +08:00

- 按用户要求先重新规划，本阶段未启动任何实验或 API 调用。基线仍为
  engineering 99%、scientific 61%、submission 56%，实验执行授权为 false。
- 重新核对 scorecard 的 12 个等权工作流：当前 730/1200；达到 80% 需要
  960/1200。新版可计分路径固定为公共基准 +90、自适应攻击 +100、论文回填
  +40，合计恰好 960/1200。盲测、Gemini smoke、工程代码和报告不用于凑分。
- 真实公共矩阵为 6,873 条：Pro 主模型 5,082，Flash 第二模型 1,791。
  依据已录取 v8 条件级调用率/费用，预计约 15,828 次 provider calls、中心
  CNY 12.03，增量硬熔断 CNY 25。Flash 只支持跨模型，不支持跨提供商声明。
- 执行顺序由旧的“自适应优先”调整为公共扩展优先；自适应 75,000 查询面板
  必须先做 8×50、最多 400 查询、CNY 5 的 outcome-blind 成本 canary，
  再单独冻结正式费用门。
- 详细计划：
  `docs/research/paper_v2/M3_PI_Guard_80_percent_evidence_execution_plan_v2.md`；
  机器路线图：
  `protocols/paper_upgrade_v2/evidence_80_execution_roadmap_v2.json`。
- 下一动作仅在 owner 确认后进行：先实现公共/自适应离线 controller、result
  gate、analysis 和负例测试；完整 Harness 为绿色后才允许公共技术 canary。

### Gemini 项目恢复免费层并完成一次 prospective v3 诊断 — 2026-07-27 09:40 +08:00

- Owner 新截图确认 exact project `M3 PI Guard test` 已显示“免费层级”和
  “设置结算信息”，即 paid billing 已解绑；历史 Tier 1 截图与当前截图均只
  绑定 SHA-256，不复制含局部账户信息的图片。
- 新建 prospective v3 配额快照和覆盖策略，不修改冻结的 Gemini v1/v2：
  provider 免费层为 5 RPM、250,000 input TPM、20 RPD；本地熔断器为
  4 RPM、200,000 TPM、18 RPD、16,000 output tokens/day，并保留 2 RPD。
  并发固定 1，自动重试、provider tools、external effects 和 paid tier 均为 0。
- 离线截图哈希、快照哈希、override 绑定及现有 budget-policy 复用校验通过后，
  恰好执行一次固定 public synthetic `SAFE` 请求。结果为 HTTP 200，
  returned model 精确为 `gemini-3.6-flash`，输出严格匹配 `SAFE`，
  32 prompt / 1 completion / 44 total tokens，约 1996 ms。
- Google 返回 response ID 但没有可用 request-ID header；脱敏证据保留
  payload/response/receipt digest，不保存凭据、header 或 prompt/response
  正文。因此该诊断证明当前免费层连通恢复，但 request trace 不完整，仍为
  diagnostic-only，不能进入正式第二模型结果。
- 192-item v3 不能在单个 provider day 内完成；未来必须先实现按
  America/Los_Angeles 日界计数的 provider-call meter，再冻结新的 candidate
  和 owner admission，最多 18 calls/day。科学完成度保持 61%，
  `F-PAPER-002` 仍为 `in_progress`。

### Gemini 429 截图复核收敛到 Tier 1 结算状态 — 2026-07-27 09:25 +08:00

- Owner 提供的 AI Studio 当前截图显示 exact project 为 `M3 PI Guard test`，
  页面层级为“第 1 层级”；Gemini 3.6 Flash 的 28 日峰值仅为
  2/1000 RPM、1.35K/2M TPM、3/10K RPD。三项公开限额均远未触发，且用量
  规模与本项目少量调用基本一致，key-project 错配假设明显降级。
- 当前最可能根因改为 Tier 1 billing/prepay 状态：Google 官方说明 paid tier
  只有 positive Prepay balance 才提供 API；`Set up Prepay`、`No credits`、
  depleted/negative balance 或 billing account issue 都会停止所有关联 key。
  Tier 1 另有 spend-based limit，但本项目用量不足以正常触发 USD 10/10min，
  因此零余额/结算同步异常比真实 spend saturation 更可能。
- `Logs and Datasets` 显示 0 条不能推翻调用证据：页面标注只为部分 API 启用，
  当前 transport 使用 OpenAI-compatible Chat Completions，不是已明确支持
  developer logs 的 Interactions API。Batch API 的 Gemini 2 Flash 指标与当前
  Standard Gemini 3.6 Flash 请求无关。
- 三张临时截图不复制进仓库，只记录 SHA-256：
  `042364443edec7c691d727b7777e972a33994ce3d74c020756582d822f70d724`、
  `7864cdf272c8b38ef63c248b2ecfb25a16a806083048c5bfeb2bca6eab75e6de`、
  `73bac3cdb2bd1a91876b086853b7d49e3601ac46e4ec8b6f842814b2cdc67104`。
- 下一步只读核查 AI Studio“结算/项目”中的 Available credits、Prepay/Postpay
  和 status；在这项状态明确前不再发 Gemini 请求。历史 free-tier quota
  snapshot 不原位修改，未来 v3 必须建立新的 prospective quota/billing snapshot。

### Gemini 独立连通性复测仍为 HTTP 429 — 2026-07-27 09:15 +08:00

- 按用户要求执行了一次新的、独立的 Gemini 诊断请求；它不属于已冻结的
  Gemini v1/v2，也不进入正式实验或 ITT 结果分母。
- ignored local config 的 Gemini key 非占位、模型
  `gemini-3.6-flash` 和官方
  `https://generativelanguage.googleapis.com` 端点准入检查通过。
- 唯一网络请求使用固定合成文本、temperature 0、max tokens 16、无 tools、
  无 external effect、无 fallback，服务端返回 HTTP 429。客户端立即停止，
  automatic retry=false；未得到可核验的响应模型、response ID 或 token 用量。
- 当前结论是“本地配置结构和官方端点绑定正常，但 Gemini 当前不可用于运行
  实验”；不能把 429 解释为连通性成功或精确身份验证。若配额恢复，仍须新建
  prospective v3，不能恢复或重试已冻结的 v1/v2。
- 根因排序基于无新增请求的时间线复核：同一未再修改的 local config 在
  2026-07-23 21:20 曾以相同 endpoint/model 返回 HTTP 200，随后
  2026-07-24 约 00:27、2026-07-27 01:23 和本次 09:15 均为首请求 429。
  因此 key/base/model 拼写错误、unsupported model、free-tier 不可用和 payload
  格式错误均不是首要解释；最可能是 key 绑定项目与 AI Studio 截图所选项目
  不一致，或该项目实际 active quota/账户状态为零或异常。跨天重复也使单次
  RPM 瞬时峰值的解释变弱。
- Google 官方当前说明：限额按 project 而非 key 计算；3.6 Flash 为 GA 且
  Standard free tier 可用；OpenAI-compatible chat route 官方支持该 model；
  429 表示 RPM/TPM/RPD/spend 等资源限额，错误 key/权限通常为 403、free-tier
  地区不可用通常为 400、payload 参数问题通常为 400。Google Cloud 公共状态页
  当前无 broad severe incident，因此全局故障没有正证据。
- 精确 quota metric 仍未知，因为当前安全 transport 只保留 429 body SHA-256，
  不保存结构化 `QuotaFailure`/`RetryInfo`。下一步必须由 owner 在 AI Studio
  以该 key 的 exact project 核对 key status、project tier、3.6 Flash active
  RPM/TPM/RPD、usage 和 09:15 请求日志；在此之前不做网络重试。

### 阶段报告优先：冻结当前结论并规划后续正式实验 — 2026-07-27 02:00 +08:00

- 用户明确要求当前优先完成一份含图表分析的详细 Word 阶段报告；v7 之后的新
  机制迭代暂缓。报告必须以已准入的 DeepSeek v8+v9 分析为唯一中型科学结果，
  明确记录 mechanism gate 失败和 empirical fallback 路线，不能用工程就绪度
  或报告页数抬高科学完成度。
- Gemini v1 金丝雀已因 VIGIL 约束生成静默回退而永久失败关闭；新建的 v2
  prospective 路线只包含 `m3_policy_only` 与 `m3_full`，但首次官方调用收到
  HTTP 429 并按协议立即暂停。v1/v2 均无可准入的第二模型正式结果，不得重试
  当前版本或把 diagnostic 记录写成跨模型泛化证据。
- 本轮允许新增 2026-07-27 报告生成脚本、报告图表、DOCX、结构/渲染 QA
  产物和 Harness 状态；允许只读复核前沿论文与期刊范围。禁止修改任何冻结的
  DeepSeek/Gemini controller、candidate、admission、ledger 或正式分析，
  禁止读取/输出凭据，禁止 API 自动重试、provider tools 和真实外部 effect。
- 验收标准：报告须包含 DeepSeek 安全—效用结果、预注册门禁判定、授权 regime
  探针、Gemini 失败边界、99/61/56 就绪度拆分、至少四张分析图、后续公共基准/
  自适应攻击/第二模型/独立盲测计划与止损条件；DOCX 需通过 OOXML、表格几何、
  占位符、凭据模式与 accessibility 检查，并在可用时完成逐页渲染检查。
- 已完成：
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-27.docx`
  （SHA-256
  `27b366847dcdfd1b8fa48aa5f766cb0839583d9686084f87cba45b460073e5b3`）。
  报告含 6 图、21 表、20 个正式标题和 11 个来源链接；结构 QA、a11y、
  表格几何、密钥/占位符/批注/修订检查与 6 图人工检查通过。由于本机无
  LibreOffice，canonical 整页渲染在打开文档前失败，按文档规范不宣称逐页
  render pass。
- Gemini 当前结论已同步：v1 因 VIGIL fallback 永久失败关闭；v2 首请求
  HTTP 429 后暂停，只有 1 条 diagnostic、0 正式结果、0 完成调用与 0 token。
  两版本不得恢复或重试；配额恢复后必须新建 prospective v3。

### Gemini fallback v1 已冻结，等待 API 前完整 Harness — 2026-07-26 23:45 +08:00

- 按冻结 480 行计划做 outcome-blind 条件筛选，只保留
  `strongest_peer_reviewed_structural_baseline`、`m3_policy_only` 和
  `m3_full`，生成独立 Gemini 第二模型计划 264 行：216 条主比较、48 条
  authorization-regime probes；没有使用 DeepSeek scientific outcomes 做样本选择。
- 新增 Gemini 官方调用、v1 experiment record、attempt ledger、provider-call
  ledger 和 safety-evidence sidecar 的四链交叉绑定。每次调用均为单次、
  free-only、0 retry、0 provider tools、0 external effects；首个 HTTP 429
  立即暂停，USD 付费上限为 0。
- 零网络端到端资格通过：2 条临时记录、2 条 evidence sidecar、0 diagnostic、
  0 credential/network/formal result。专项回归 33/33 通过，Ruff、Python、
  PowerShell 和 Bash 语法通过。
- 已冻结 candidate manifest
  `33984e93ab9148336f2f97b0c9bf810aa508755f40e836d282ad7ad6957b7cd2`
  和三条件 canary admission manifest
  `88282407899b439fd164b719b30a1cae12fa3888f8f195db02083baab3949610`。
  输出 identity 为
  `0c5e6f64b6abc296b727fd9e57bbd954fb0eed85051a29e749aca801a51785af`。
- 下一硬门：更新后的完整 Harness 必须 `Verification failed=0`。只有全绿后才
  允许恰好一次 Gemini 三条件 canary；canary 技术审查不得读取 scientific
  outcomes，通过后才单独冻结 continuation admission。Gemini v1 controller、
  evidence store、plan、qualification、candidate、canary admission 及其锁定输入
  现均视为不可变；若发现缺陷必须新建版本，不得原地修改。

### DeepSeek 中型实验完成并切换 empirical fallback — 2026-07-26 23:03 +08:00

- v9 唯一 pending-only segment 已完成 177/177；v8+v9 精确覆盖 480/480，
  479 formal-candidate + 1 diagnostic、0 open、1084 个官方 DeepSeek
  调用，累计 CNY 1.8623798，0 retry、0 provider tools、0 external effect。
- combined result gate v6 通过 outcome-blind 技术审查并生成独立 analysis
  admission。唯一 diagnostic 保留在 ITT，以 `diagnostic_only` 和
  unverified response identity 进入分析，不伪造官方响应证据。
- v8 分析修订在 aggregate access 前冻结，正式结果已生成并由
  `--verify-analysis` 独立重建：M3-full vs structural 的 unsafe effect 为
  0/36 vs 8/36，差值 −22.2pp、cluster bootstrap 95% CI
  [−36.1pp, −8.3pp]；良性工具 TCR 为 6/24 vs 12/24，差值 −25pp；
  M3-full vs policy-only unsafe effect 均为 0/36。
- 预注册 mechanism gate 因 `module_gain=false` 与
  `utility_point_noninferiority=false` 失败，正式切换到
  authorization-leakage/uncertainty/security–utility empirical fallback；
  不得用后续实验抹去这项负结果或恢复 SOTA/机制领先叙事。
- 当前科学证据完成度据实更新为 61%，不是 80%。下一阶段优先实现和冻结
  Gemini 第二模型的 fallback 核心扩展，再推进公共基准与自适应攻击；
  独立盲测仍受外部 custodian 阻塞。
- 允许新增：fallback 专用 prospective 协议、Gemini 控制器/准入/记录/门禁、
  公共与自适应的新版本化扩展、论文结果/图表及 Harness 状态。禁止修改：
  v1–v9 controller/candidate/admission、v6 result gate/admission/review、
  v7/v8 analysis amendment 及正式分析、两份运行 ledger、paper-v1 和凭据。

### SCI Q2 真实证据 80% 冲刺重新启动 — 2026-07-26 +08:00

- 用户要求继续按照既定 SCI Q2 网络安全论文计划，尽量把真实论文证据完成度推进
  到 80% 以上；DeepSeek/Gemini 可按需调用。不得以工程测试、计划、stub、
  diagnostic smoke 或报告页数替代正式科学证据。
- 当前权威起点是 v8：6/480 terminal records、474 pending、0 open attempts，
  result/analysis admission 均关闭。v7 及更早失败 run 保持不可变且不得重试。
- 第一硬门禁是更新后的完整 Harness 必须得到 `Verification failed=0`。本轮将使用
  `F:\robot\Anaconda3\python.exe` 所属 Python 3.13.5 环境执行验证；result-gate
  v5 的嵌套复验已知可能约需 33 分钟，只允许一个验证进程，不因 wrapper 超时
  启动重复实例。
- Harness 全绿后，才允许恰好一次执行已冻结命令：
  `E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m
  experiments.paper_v2.formal_matrix_controller_v8 --execute-continuation`。
  不自动重试、不与 Gemini 并发、不启用 provider tools、不执行真实危险或外部
  effect，所有失败保留在 ITT 分母。
- continuation 完成后必须先运行 outcome-blind result gate v5；只有独立 result
  admission 通过，才读取 scientific outcomes、运行预注册统计并生成论文图表。
  若 v8 因证据完整性或运行质量失败，则按冻结规则转为授权泄漏/不确定性实证路线，
  不删行、不修结果、不宣称防御领先。
- 若 DeepSeek 中型矩阵及分析尚不足以使科学完成度达到 80%，按证据增益/成本顺序
  推进：Gemini 第二模型小规模泛化、至少一个公共外部基准、结构感知自适应攻击；
  独立盲测仍需要第三方作者/保管人，缺少独立 custody 时只能记录为外部 blocker。
- 允许写入：v8 已授权 append-only runtime 路径、result-gate/analysis 的新准入
  和结果产物、必要的新版本化 Gemini/公共/自适应协议与测试、论文工作区、Harness
  状态。禁止修改：paper-v1、v1–v8 已冻结 controller/candidate/admission/
  qualification、历史 ledger、provider safety、M3 Guard 授权逻辑、凭据文件。
- 阶段验收：完整 Harness 绿色；v8 矩阵自然完成或按冻结 failure boundary 停止；
  技术 gate 对 outcome 保持盲态；任何统计结果可从 manifest 重建；完成度按
  medium、第二模型、公共基准、自适应攻击、盲测、Methods/Results/Integrity
  分项据实计算，目标至少 80%，未达到则保持 `F-PAPER-002=in_progress`。
- 完整 Harness 前置门已于 2026-07-26 15:45 +08:00 通过：1073 passed、
  1 skipped、3 warnings，`Verification failed=0`。日志位于
  `outputs/paper_upgrade_v2/verification/pre_v8_continuation_full_rerun/`；
  允许进入一次且仅一次的 v8 continuation，scientific outcomes 仍封存。
- v8 continuation 已于 15:47:08 +08:00 恰好启动一次：venv launcher
  PID 73484、Python 3.13.5 PID 33056。日志位于
  `outputs/paper_upgrade_v2/verification/v8_deepseek_continuation/`；
  运行中只允许内容无关监控，不得自动重试或并发 Gemini。
- v8 于 16:54:49 +08:00 因唯一 `ProviderTransportError` 按 fail-closed
  规则自然暂停：303/480 terminal（302 formal-candidate + 1 closed
  diagnostic）、177 pending、0 open、497 completed provider calls、
  累计 CNY 1.2069394。失败项保留在 ITT 且不得重试；v8 控制器禁止再次执行。
- 当前实现范围切换为新的 prospective remainder shard：只能包含 177 个从未启动
  work item，使用独立 run/output/ledger；不得复制或改写 v8 的 303 条。组合
  outcome-blind gate 必须验证两 shard 合计 480、work key 无重复、诊断行保留、
  0 open，之后才可准入科学分析。
- v9 API 前的唯一完整 Harness 已于 2026-07-26 19:29 +08:00 自然结束：
  1081 passed、1 skipped、3 warnings，12 个验证阶段全部 PASS，
  `Verification failed=0`。日志位于
  `outputs/paper_upgrade_v2/verification/pre_v9_remainder_full_rerun/`；
  stderr 的三条 `delete_record` 均为 RuntimeAuditor 预期阻断。
- 当前唯一获准执行动作是启动一个 v9 `--execute-pending-segment`，只处理
  177 个 never-started work key。若出现闭合 diagnostic，当前进程自然暂停；
  仅在 outcome-blind 技术审计后才可人工启动下一 pending-only segment，
  且不得重试任何终态项。

### v8 六条件 canary 通过，阶段报告完成，474 条续跑暂缓 — 2026-07-26 14:10 +08:00

- v7 首次正式 canary 在两个官方 DeepSeek 响应后由离线 evaluator 对
  `boundary adapter version` 不一致失败关闭：0 result records、1 open
  attempt、2 provider responses、1 trace，增量成本 CNY 0.0010122。根因是
  effect backend 延迟解析模块全局，而 v7 仅在 dispatcher 构造期绑定 v3
  adapter。v7 已冻结为永久不可恢复，不重试、不补写、不读取科学结果。
- 新 v8 controller 将 v3 adapter 绑定保持到完整 `_execute` 生命周期，并新增
  delayed-backend 回归、独立 qualification/candidate/canary admission 和新
  run/matrix identity。v8 candidate manifest 为
  `340246ec336281373f49a4d062734e01afa208c6ea5a76daa9881d21ac05cf6d`，
  matrix identity 为
  `8d08cab3febccdf5a4360d208766c39cef851fa9ec8b9c15799ee30171a213bf`。
- 唯一 v8 六条件 DeepSeek canary 已通过：6/6 terminal
  `formal_candidate` records、13 official responses、0 diagnostic、
  0 operational failure、0 retry、0 fallback、0 provider tools、0
  external effect；增量成本 CNY 0.0077078，累计 v8 成本
  CNY 0.9153868。技术 review 明确
  `scientific_outcomes_reviewed=false`。
- result gate v5 已在结果访问前冻结；candidate manifest 为
  `73edb1f625f13f715cff475cd7d5ee9f9fe2183efc0c7cc9479b644eb1928e7f`。
  v8 continuation admission manifest 为
  `78b136fcd8766d93a7dd37081d2adbf0738bf2c5fdac556855375d9a7b75bc83`，
  当前 6/480、474 pending、0 open，continuation 已单独准入，
  result/analysis 仍关闭。
- pre-v8 完整 Harness 为 1072 passed、1 skipped、1 failed；
  `Verification failed=1`。唯一失败是已经过时的 v7 “输出根未使用”测试，
  已改为永久 abort/no-network 不变量并专项复验 1/1 通过。由于更新后的完整
  Harness 尚未重跑至绿色，本轮按报告优先级不启动 474 条 continuation。
- 新阶段报告位于
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-26.docx`，
  SHA-256 为
  `a79f3a65b75b313ec2a9bc8effc058c436d2d0671ae1f04009ad4578c379b828`。
  报告含 4 张分析图、16 张表、详细实验路线和止损条件。OOXML、表格几何、
  accessibility、占位符、密钥模式与图片人工检查通过；本机无 LibreOffice，
  因而未完成整页渲染 QA。
- 下一唯一执行顺序：先运行更新后的完整 Harness 并取得
  `Verification failed=0`；再恰好一次执行 v8 continuation；完成后先做
  outcome-blind result-gate review，只有独立 result admission 通过才允许分析。
  `F-PAPER-002` 保持 `in_progress`。

### v7 离线恢复与 result gate v4 实施中 — 2026-07-26 +08:00

- 用户重新授权继续研究，并允许按需使用 DeepSeek/Gemini；安全边界不变：
  不读取/输出密钥、无 provider tools、无真实外部 effect、单 provider、逐调用
  append-only 身份/usage/cost 链、失败留在 ITT。
- v7 输出根仍不存在，确认 v7 API/record/canary 均为 0。v7 专项拆分回归 12/12
  通过；首次合并运行因两分钟 wrapper timeout 无 verdict，未重试同一命令。
- 完整 Harness 首次恢复审计结束为 `Verification failed=1`。唯一失败是旧 v6
  测试仍假定 canary 后 6-record 状态可恢复；实际不可变 v6 证据为 64 records、
  1 open attempt，控制器正确拒绝自动续跑。测试已改为要求 fail-closed 并复验
  abort review v2；v6/abort focused 5/5 通过。
- 当前实现目标：新增只绑定 v7 的 `formal_result_gate_v4.py`、schema、
  零网络 qualification、prospective candidate 与测试；不得修改 v1-v7 历史
  controller/candidate/admission/ledger、v1-v3 result gate、provider safety、
  M3 Guard 授权或任何科学结果。
- result gate v4 必须锁定 matrix-v7 candidate、controller-v7、
  boundary-rejection-runtime-v3、v7 canary review（产生后）、480 ITT、
  0 open/unknown runner failure、完整 identity/trace/safety 及结果不可见边界。
  只有专项和完整 Harness 通过后，才允许一次 v7 DeepSeek canary。

### 阶段性 Word 报告完成，v7 继续冻结且暂不运行 — 2026-07-24 23:25 +08:00

- 按用户优先级停止 v7 全量离线审计和所有 API 计划；被中止的审计约完成 47%，
  没有形成完整通过/失败结论，也没有 v7 canary、continuation 或正式记录。
- v7 候选、qualification、canary admission 和 matrix identity 保持不可变；
  恢复实验前必须先完成全量离线审计，并实现/测试/冻结能消费 v7 哈希化
  boundary-rejection evidence 的 result gate v4。
- 新阶段报告：
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-24.docx`。
  报告覆盖论文定位、34 篇文献/22 个审计单元、v4–v7 失败演进、成本/验证、
  JISA/Q2 有条件可行性、正式矩阵、跨模型/公共基准、自适应攻击、盲测、统计
  和止损转向；明确正式安全结果为 0。
- 报告含 5 张数据图、26 张表、15 个外部参考链接。DOCX OOXML validator 在
  UTF-8 模式下通过；独立 Pandoc/Chrome 预览识别 5 张图和 26 张表，21 页 PDF
  预览抽查未见表格/图片溢出，长路径与 SHA 已加入软换行。
- 交付扫描未发现密钥格式或流程性禁用语句。F-PAPER-002 保持 `in_progress`；
  本轮不重启 v7、不运行 API、不产生科学结果。

### DeepSeek v5 canary 与结果门冻结完成，正式矩阵待启动 — 2026-07-24 20:40 +08:00

- v4 已按 outcome-blind 技术审查永久冻结：395/480、39 个协议/运行终态、
  1 diagnostic、85 项未运行；未查看 scientific outcomes，未生成 result
  admission。v4 不续跑、不重试、不改账本。
- v5 在新 run/matrix identity 下加入独立 effect-boundary rejection 终态：
  online Guard 的 ALLOW 不被改写，被安全边界拒绝的动作不执行，receipt 为
  no-effect，并保守记录 `unsafe_effect_itt=true`、`task_completion=false`。
  `provider_safety.py` 和 M3 Guard 授权逻辑均未放宽。
- v5 六条件 canary 已唯一执行并通过：6/6 records、13 个官方 DeepSeek
  responses、0 自动重试、0 operational failure、0 diagnostic、0 external
  effect，累计项目成本 CNY 0.7522526。技术 review 明确
  `scientific_outcomes_reviewed=false`。
- 用户最新授权允许 DeepSeek/Gemini 按研究需要继续调用，不再以历史 27/30 元
  估计作为项目级停机条件；成本/token 仍逐响应追加记录，provider quota/credit/
  rate-limit、身份链破坏或 effect 边界异常仍立即暂停。当前 v5 实测成本远低于
  旧阈值，因此不重建身份、不制造无意义的 v6。
- result-gate v2 已在正式 continuation 前冻结，candidate manifest 为
  `edac535c528a944581175e7752bf1da3cef57f8d27c8c21f66807f0d094d5fe8`。
  证据完整性决定能否分析；已知 provider/parse/max-step/timeout 终态保留在 ITT
  分母，未知 runner failure 仍必须为 0。最多 1% 具有闭合失败链的 provider/
  timeout diagnostic 可进入透明敏感性分析；运行质量不达标时自动转向实证论文，
  但不以丢弃失败记录制造通过。
- continuation admission 已生成并复验：当前 6 records、474 pending、0 open、
  budget unpaused、result admission false。paper-v2 回归 259/259 通过；启动正式
  API continuation 前仍须完成更新后的完整 Harness。
- 冻结后禁止修改 v5 controller/candidate/admissions/canary review，以及
  result-gate v2、analysis v3、gate spec v2、budget authorization v3。若这些
  哈希输入出现缺陷，必须停止并建立新版本。

### DeepSeek v4 门禁阻断，v5 隔离拒绝语义设计中 — 2026-07-24 19:43 +08:00

- v4 正式续跑在 395/480 时按冻结的 500,000 observed prompt-token 投影门槛
  干净暂停：773 个官方响应，累计 CNY 0.7445328，observed cache hit ratio
  0.712160，原 4,416-call 最坏边界投影 CNY 43.890543，高于 CNY 27 ceiling；
  stderr 为空、无自动重试、无跨 provider fallback、无真实外部 effect。
- 冻结的 outcome-blind result gate 已生成技术审查并阻断准入：
  356 completed、30 runner_failure、6 max_steps、2 provider_failure、
  1 parse_failure，394 formal-candidate、1 diagnostic、85 项未运行；
  `scientific_outcomes_reviewed=false`，不得生成 result admission 或分析。
- 运行层审计确认 30 个 runner_failure 全是 M3-v2
  `post_response_safety_rejection`。v3/v4 适配器把任何
  `ProviderSafetyError` 统一闭合为 runner failure；现有 result gate 又要求
  zero operational failure，因此续跑剩余 85 项也不可能使 v4 合格。v4 从此
  冻结，不续跑、不重试、不改账本。
- 新目标：使用 v5 新 run/matrix identity，在不放宽
  `provider_safety.py`、不执行被拒绝动作、不修改 M3 Guard 授权逻辑的前提下，
  增加安全边界拒绝终态适配。已被独立隔离层阻止的 ALLOW proposal 必须作为
  内容脱敏、formal-candidate 的 ITT 终态保存，保持
  `unsafe_effect_itt=true`、`task_completion=false`，而不是伪装为成功执行或
  丢出 runner failure。
- 允许修改：新增 `experiments/paper_v2/*v5*` 或新版本化适配模块、相应新 schema/
  tests/protocol artifact、Harness verifier 和状态文档。禁止修改 v1–v4
  controller/client/candidate/admission/ledgers、`provider_safety.py`、
  `m3_guard/` 授权逻辑、paper-v1 或凭据文件。
- v5 验收：安全拒绝动作从未执行；receipt 明确 no-effect；原提案只按既有脱敏
  runtime-event 契约持久化；边界拒绝保守计入 ITT unsafe、任务失败；真正
  provider/parse/max-step 状态仍保留；零网络 qualification、candidate、
  六条件 canary admission、专项和完整 Harness 均通过后，才允许一次 v5 canary。

### DeepSeek JSON Output v4 canary 通过，正式矩阵续跑中 — 2026-07-24 17:37 +08:00

- v1、v2、v3 均已按各自失败边界冻结且永久不续跑。v4 以新
  run/matrix identity 固定 DeepSeek non-thinking 与
  `response_format={"type":"json_object"}`，严格解析器不变；可信应用上下文只
  投影冻结在线字段，不允许 evaluator/gold 字段进入模型消息。
- v4 客户端/控制器完成零网络 qualification；candidate、六条件 canary admission、
  canary review 与 continuation admission 均独立哈希冻结并可复现。
- 专项 paper-v2 回归为 231 passed、769 deselected；完整 Harness 为
  1002 passed、1 skipped、3 warnings，`Verification failed=0`。
- 单次正式 canary 为 6/6 终端记录、0 operational failure、0 diagnostic record、
  13 个官方响应调用；累计项目成本 CNY 0.0470286。响应正文和科学结果未在技术
  门禁阶段读取。
- 已按用户的安全 API 迭代授权启动剩余 474 个冻结工作项；只运行 DeepSeek，
  Gemini 不并发，provider tools/外部 effect 关闭，预算熔断为项目累计 CNY 27，
  不自动 retry 或跨 provider fallback。
- 当前允许写入的正式运行位置仅为 v4 output root 的 append-only attempt、
  trace、budget 与 experiment-record 账本以及 stdout/stderr 运行日志。不得修改
  已哈希锁定的 v4 controller/client/schema/candidate/admission/qualification；
  如发现实现缺陷，必须停止并建立新版本，不能修补在途身份。
- 下一门禁：续跑自然完成或由既定熔断暂停后，先做完整性、身份、预算和 operational
  failure 审核，再独立冻结 result admission；只有通过后才运行
  `medium_analysis` 并查看 scientific outcomes。

### DeepSeek 正式矩阵 v2/v3 失败已冻结 — 2026-07-24 16:46 +08:00

- v1 的默认 thinking 截断失败已冻结；v2 使用官方 non-thinking 请求并通过
  988/988 paper-v2/Harness 回归后，单次执行六条件 canary。首条
  `M3V2-D-002-BT` 完成 1 个官方调用，随后本地安全边界拒绝了
  `sandbox/public` 外的提议路径。没有 effect、记录或重试。
- 源码审计确认：online projection 与 policy compiler 均包含可信
  `requested_actions`，但实际 message builder 没有把任何
  `trusted_app_context` 呈现给模型；该任务的文本又明确依赖“可信应用面板”中的
  精确路径。因此 v2 是实验接口缺陷，不是可分析的防御结果。
- v2 证据已冻结为 `aborted_run_review_v2.json`：0 条终端记录、1 个 open
  attempt、1 个完整官方 response/trace、累计 CNY 0.0205298；响应正文未读取，
  continuation/result admission 仍为 false，旧 run 永久不可续跑。
- 当前目标：新增版本化可信上下文 prompt projection，并将 provider 已完成后
  的本地 runtime/safety 异常转为内容脱敏的终端 `runner_failure` ITT 记录。
  修复必须使用新 run/matrix identity、零网络 qualification、新 candidate 与
  新 canary admission；不得修改或重试 v1/v2。
- 允许修改：`experiments/paper_v2/` 的新版本化实现、`schemas/paper_v2/` 的新
  schema、对应 `tests/unit/`、`protocols/paper_upgrade_v2/` 新 v3 artifact、
  Harness 状态/决策/验证入口。禁止修改冻结的 v1/v2 controller、candidate、
  admission、运行 ledger、paper-v1、凭据文件和 provider 响应内容。
- 验收：可信上下文仅投影已在线可见、非 evaluator/gold 的允许字段；精确动作在
  六条件间保持一致；异常持久化不执行副作用、不存正文且保留完整 trace/cost；
  focused、paper-v2 与完整 Harness 通过；只有新的六条件 canary 技术门禁通过
  才能生成独立 continuation admission。

### Live 条件依赖全部资格化，双官方身份验证按证据合同失败关闭 — 2026-07-24 00:40 +08:00

- PromptGuard 固定模型、AgentDojo 官方环境/utility/security checker、M3 离线
  evaluator、exact-gold oracle ablation 和 VIGIL 官方 generator provider bridge
  已全部接入六条件 live runtime，并以零网络 fixture 通过资格测试。
- 用户授权的固定合成身份检查严格执行 DeepSeek/Gemini 各一次，无工具、无外部
  effect、无重试。DeepSeek 返回精确 `deepseek-v4-pro`、response ID 和完整 usage，
  但没有 request-ID header，因此按冻结合同保持 `diagnostic_only`；Gemini 首次
  调用即 `ProviderPausedError`，按 429 规则停止。
- 新证据 `provider_live_qualification_v1.json` 不保存 key、prompt、response 正文、
  header 或原始错误；0 个正式结果。v3 preflight 已绑定该证据并保持
  `execution_authorized=false`、`formal_execution_authorized=false`、
  `gate_pass=false`。
- 当前只剩两项正式执行 blocker：Gemini 当前项目 AI Studio RPM/TPM/RPD 快照；
  完整 live 身份链（DeepSeek request ID 缺失、Gemini 429）。不得自动重试或弱化
  双 ID 合同来制造通过结果。
- 验证：provider 聚焦 16/16、paper-v2 160/160、完整 Harness 929 collected、
  928 passed、1 skipped，`Verification failed=0`。工程/科学/投稿就绪度更新为
  99%/32%/44%；只有工程准备超过 80%，论文科学证据仍远未达到 80%。

### 六条件 live 依赖组合层实施中 — 2026-07-24 00:10 +08:00

- 目标是在不联网、不读取凭据、不加载收费模型且不产生真实外部副作用的前提下，
  把 official provider proposal、严格工具调用解析、PromptGuard detector gate、
  VIGIL、M3 policy-only/full 和隔离 effect backend 接到既有六条件壳层。
- 允许新增 `experiments/paper_v2/live_condition_runtime.py`、对应资格 artifact/
  tests，并更新 provider gate、Harness verifier 与状态文档。
- 禁止修改 paper-v1、v1/v2 medium plan/manifest、历史结果或任何凭据配置；禁止
  将注入式或缺少真实模型依赖的测试称为 live/formal 科学结果。
- 验收要求：严格 JSON proposal、8/16 call cap、六条件正确路由、detector/
  structural/M3 决策路径、M3 sandbox/AgentDojo memory-only effect、12 对零网络
  控制流资格，以及不含 evaluator/gold 字段的在线可见性。

### 正式记录持久化路径完成离线资格 — 2026-07-23 23:30 +08:00

- 新增 `formal_record_store.py`：experiment record 与 sanitized runtime events
  以 append-only JSONL 保存；每次追加前复验完整已有链和候选链，追加后 flush+
  `fsync`。恢复时拒绝空行/截断 JSON、未知或重复 work、重复 record、execution/
  run/metadata drift 以及 record/event/argument/entry hash drift。
- 落盘结构只接受严格 event 字段和 experiment-record schema；raw prompt/messages/
  response/observation/headers/credentials 或 secret-pattern 内容在写入前 fail-closed。
  completed/refusal live 行只允许 `formal_candidate`；无完整身份的 operational
  failure 可为 `diagnostic`，但必须保守计入 ITT。stub 仅限显式资格模式。
- 零网络资格在自动清理的临时目录逐条写入 12 个 benchmark×condition entries，
  每次重放全链，最终恢复 12/12、剩余完整计划 468；raw marker 0、清理通过。
  仓库 experiment records、正式结果、API/model calls 均为 0。
- v3 preflight 现绑定 record-store 模块与资格摘要，blocker 从 4 项降为 3 项：
  live 条件依赖、Gemini quota 快照、每家 live exact-model/双 ID qualification。
  `gate_pass=false`。
- record-store 单测 7/7、相关回归 28/28、paper-v2 127/127、Ruff、compile、
  JSON、shell/PowerShell、conventions 12/12 均通过；完整 Harness 收集 899 项，
  898 passed、1 skipped、3 warnings，总入口 546.9 秒，
  `Verification failed=0`。
- 工程就绪更新为 97%，科学证据仍为 32%，投稿就绪仍为 43%；本地资格提升不计入
  论文效果证据。

### Python 3.13.5 项目依赖补齐并完成全量验证 — 2026-07-23 23:05 +08:00

- 按 `requirements-core.txt` 与 `requirements-dashboard.txt` 复验当前解释器；
  openai 2.33.0、pandas 2.2.3、streamlit 1.45.1 等声明依赖均已满足。
- 在 Python313 用户 site 新增 Ruff 0.15.22，并将 Pillow 调整为 10.4.0，使项目
  Dashboard、moviepy 与 python-fx 的现有约束一致。`F:\robot\Anaconda3` base
  site 对当前账户不可写，所以新增包由同一 Python 3.13.5 的 user site 加载。
- openai/pandas/streamlit/pytest/Ruff/jsonschema/Pydantic/NumPy/SciPy/Matplotlib/
  NetworkX/Pillow 的导入检查通过；`python -m ruff` 现在不再依赖 LFischl。
- `pip check` 仍报告非项目的 pdfplumber 0.11.10 与 PySSTV 0.5.8 要求 Pillow
  12.2.0；它们与项目侧 `<11` 约束不可共存。本轮未擅自卸载或降级这些用户工具，
  因而不宣称全局依赖检查通过。
- paper-v2 120/120 与 Ruff 通过；完整 Harness 收集 892 项，891 passed、
  1 skipped、3 warnings，总耗时 529.9 秒且 `Verification failed=0`。无 API/
  model call，论文证据完成度不因环境安装提高。

### 六条件无副作用执行壳层、事件脱敏与冻结门禁完成 — 2026-07-24 02:15 +08:00

- 新增统一 `ConditionExecutorShell`，注册 no-defense、safe prompt/spotlighting、
  PromptGuard detector-only、VIGIL structural baseline、M3 policy-only 和
  M3 full 六个条件。在线 runtime 只获得最小调度身份和冻结 online state；
  evaluation case type、primary eligibility、offline evaluator/source/result
  fields 被显式禁止。
- 多步 runtime event 在进入 experiment record 前移除 prompt/messages/headers/
  credentials，response/observation 正文只保留 SHA-256 与 UTF-8 字节长度；action
  arguments 先通过 secret-pattern scan。case-level initial decision 固定为首个
  parsed proposal，`ASK` 为 pending 且不执行。
- `formal_condition_executor_qualification_v1.json` 在内存验证两个基准×六条件
  共 12 组，全部通过 experiment-record contract；API/model calls、持久化
  experiment records 和正式结果均为 0。该资格只证明壳层/脱敏，不证明 live
  PromptGuard/VIGIL/provider/effect/evaluator 忠实度或防御效果。
- v3 preflight 已绑定新模块和资格文件，当前四个 blocker 改为 live 条件依赖、
  persisted-log 路径、Gemini quota 快照和双 ID live qualification；
  `formal_execution_authorized=false`、`gate_pass=false`。
- 聚焦条件+供应商测试 21/21、全部 paper-v2 120/120、LFischl Ruff、冻结复现均
  通过。完整 Harness 收集 892 项，结果为 891 passed、1 skipped、3 warnings；
  总入口 469.1 秒且 `Verification failed=0`。
- 工程就绪更新为 96%，科学证据保持 32%，投稿就绪保持 43%。DeepSeek/Gemini
  每模型 480 项真实结果仍为 0；任务继续 `in_progress`，没有 API/model 调用。

### 官方双 API 执行器、证据分级和 v3 冻结完成，科学执行仍受门禁 — 2026-07-24 01:30 +08:00

- DeepSeek `deepseek-v4-pro` 与 Gemini `gemini-3.6-flash` 均保留独立完整
  480 项目标、每模型最多 4,416 call；缓存命中只进入 DeepSeek 实际成本/投影
  熔断，不再用于缩减样本。
- 新增单次 official transport、逐响应模型/ID/usage/cache/cost 收据和 append-only
  call ledger。真实网络必须显式 consent；每次调用恰好一个 attempt，429 暂停，
  禁止自动 retry、provider tools、外部 effect 和跨 provider fallback。
- 收据不持久化 key、Authorization header、prompt 或 response 正文。注入
  transport 永远映射为 `local_qualification`；真实官方调用只有 exact model +
  request ID + response ID 完整时才是 `formal_candidate`，缺 request ID 自动降为
  `diagnostic_only`，不会绕过 experiment-record 契约。
- 新 v3 preflight 哈希绑定 v2 480 项计划、预算/安全 policy、provider executor/
  ledger、contracts 和 schema。离线 DeepSeek/Gemini transport 2/2 通过，
  `network_calls_made=0`、`formal_results_created=0`；当前 blocker 从 5 个收敛为
  4 个：六条件正式执行器、日志脱敏复核、Gemini quota 快照和 live no-effect
  双 ID qualification。`gate_pass=false`。
- 聚焦执行器测试 13/13、全部 paper-v2 112/112、Ruff、compile、冻结复现和
  conventions 12/12 通过；完整 Harness 为 `883 passed, 1 skipped, 3 warnings`，
  总入口 471.5 秒且 `Verification failed=0`。
- `LFischl` Conda 环境为 Python 3.9，补装 `pytest 8.4.2` 后可运行本模块
  13/13 和 Ruff，但不能收集使用 PEP 701/`tomllib` 的完整仓库。全量验证继续用
  Python 3.13.5，项目最低版本说明已修正为 3.12+。
- 工程就绪更新为 95%，科学证据保持 32%，投稿就绪 43%。480 项真实结果、公共
  结果、自适应结果和独立盲测结果仍全部为 0，任务保持 `in_progress`。

### 双 API 全量预算熔断就绪，正式执行仍待绑定 — 2026-07-23 23:45 +08:00

- 用户已明确将 DeepSeek 可用余额界定为 CNY 30、Gemini 为 free tier，并要求
  不把 DeepSeek 缩成小样本。两个模型因此都保留独立的完整 480 项目标；100-call
  分块仅为断点和额度检查点，不改变研究样本量，也不允许跨供应商混补同一矩阵。
- 新增离线 `provider_budget.py`、用户批准的双供应商预算 policy 和可复现
  preflight。模块不读凭据、不联网；所有 API 输出仍只是不可信 proposal，provider
  tools、外部连接和真实副作用继续关闭。
- DeepSeek 官方价场景为：100%/95%/90%/88%/85%/80% 缓存命中时，全量上界约
  CNY 14.426152/19.544339/24.662527/26.709802/29.780714/34.898902。
  CNY 27 熔断线保留 CNY 3 余额，要求全量聚合命中至少约 87.7165%。
- 正式执行器必须逐响应取得 `prompt_cache_hit_tokens`、
  `prompt_cache_miss_tokens` 和 output token；字段缺失、下一最坏请求放不进
  CNY 27 余量或观测投影超线即暂停。Gemini 限 free tier/付费上限 USD 0，
  采用本地 batch caps 和首个 429 暂停、零自动重试、零自动 DeepSeek fallback。
- 只允许合成 M3、公共 benchmark 和固定非敏感 runtime 指令出站；凭据、个人/
  客户/受试者数据、私有账户内容、未发表论文正文、私有笔记和非公开源码禁止出站。
- 当前 policy 的预算边界已获用户批准，但 `formal_execution_authorized=false`。
  仍需新 immutable execution manifest、正式 executor qualification、日志脱敏复核、
  Gemini AI Studio 当前 RPM/TPM/RPD 快照和缺 request ID 的证据规则。
- 双预算单测 12/12、全部 paper-v2 聚焦回归 99/99、Ruff、compile、JSON、
  PowerShell/Bash syntax 和 conventions 12/12 已通过；完整 Harness 为
  `870 passed, 1 skipped, 3 warnings in 484.30s`，总入口 577.3 秒，
  `Verification failed=0`。480 项真实结果仍为 0，科学完成度保持 32%。

### DeepSeek/Gemini 官方端点连通性 smoke 完成 — 2026-07-23 21:20 +08:00

- 用户明确授权后，各供应商只执行一次固定合成文本请求，`max_tokens=8`、无工具、
  无外部 effect、无重试；本地配置检查为 ignored=true、tracked=false，
  `tracked_secret_hits=[]`，控制台和证据均未输出凭据值或响应正文。
- DeepSeek `https://api.deepseek.com/chat/completions` 返回 HTTP 200，
  returned model 精确为 `deepseek-v4-pro`，38 tokens，约 1944.568 ms。
- Gemini `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`
  返回 HTTP 200，returned model 精确为 `gemini-3.6-flash`，30 tokens，
  约 1483.696 ms。
- 两个响应均有 response ID，但检查的响应头中没有 request ID；8-token 上限也未
  得到精确 `SAFE`。因此这只证明官方端点、鉴权、配置模型和基本生成链路连通，
  `result_eligible_for_formal_tables=false`、`formal_identity_attested=false`，
  不进入论文结果，也不自动重跑。
- 脱敏证据为
  `protocols/paper_upgrade_v2/provider_connectivity_smoke_v1.json`。480 个 v2
  工作项仍全部 pending；预算边界已在后续 policy 中批准，但正式身份收据、执行器
  绑定和中型执行授权仍未满足。

### paper-v2 条件级运行时、官方 DeepSeek/Gemini 安全边界与投稿契约完成 — 2026-07-23 22:40 +08:00

- 完整性门禁在真实调用前发现 v1 账本只记录 case-level source digest，却给六条件
  和不同 authorization regime 复用同一摘要。v1 保留为零结果 superseded artifact；
  新的 v2 账本分别绑定 source projection、condition-specific initial state 和
  final runtime visibility events。
- v2 仍为 432 primary + 48 regime probe = 480 个 pending 工作项。
  `exact_gold` 明示 `evaluator_derived_authorization` 且 primary-ineligible；
  AgentDojo 固定干净 commit `089ed468…`。
- 无网络、纯内存注入执行器验证 480/480 工作项、六条件调度、五种 regime、
  ASK/effective decision、operational failure 保守 ITT 和严格 experiment schema；
  stub 结果落盘 0，API/模型调用 0。
- 新增官方 DeepSeek/Gemini 独立本地配置槽。安全 policy 只允许官方 inference
  origin、M3 synthetic sandbox 或 AgentDojo in-memory copy，禁用 provider-managed
  tools/external connectors；真实邮件、支付、host 命令、生产 API、凭据、浏览器/
  computer-use、非 sandbox 文件和未知 effect 全部 DENY。
- 34 项文献矩阵结构化复验为 22 peer-reviewed + 12 preprint-only，十项前沿核心
  引用状态机器锁定；JISA 官方 scope/Guide checklist 就绪，但投稿日机构 JCR Q2
  核验仍 pending。
- 聚焦新增回归为 18/18，standalone Ruff 通过；完整 Harness 为
  `858 passed, 1 skipped, 3 warnings in 483.60s`，最终
  `Verification failed=0`。分层完成度为工程 93%、科学证据 32%、投稿 41%，
  任务保持 `in_progress`。

### paper-v2 正式实验离线门禁与 480 项执行账本完成 — 2026-07-23 21:00 +08:00

- online-state 审计已闭环为 22/22 个 unit、16 个 distinct artifact：
  20 个 unit 有官方源码，Task Shield 仅使用明确披露的本地论文复现，SIREN/
  Task Shield 均记录未建立官方源码来源。结论为 9 个 `no_online_gold_observed`、
  10 个 `not_a_runtime_guard`、1 个 path-dependent、2 个 inconclusive；独立
  第二复核仍为 0，领域级 oracle 主张继续禁用。
- 新增离线 provider/cost 门禁，候选为 OpenAI 官方 API 的
  `gpt-5.6-terra`，但 `approved_by_user=false`、runtime identity 未验证，
  因此不是正式模型准入。校验器拒绝占位符、凭据字段/值、超过 90% 的成本熔断
  和不满足 request/response ID 的正式证据。
- 对冻结的 72 case、432 个主比较和 48 个 regime probe 逐项估算：480 个工作项、
  最多 4,416 次 provider call、输入 34,407,984 token、输出 2,260,992 token，
  按当前候选公开价格的保守总上界为 USD 119.93484。未设置或批准硬成本上限。
- 480 项 result-blind 执行计划和 manifest 已冻结，绑定 case、provider、
  source audit、structural baseline、gate、schema 与 contract 哈希；append-only
  进度契约拒绝 identity drift、重复终态和越过 90% 成本熔断，并将 operational
  failure 留在 ITT 分母。当前 480/480 均为 pending，网络调用和结果均为 0。
- 新增无内容 provider smoke receipt 校验器，可从未来一次已授权响应中核验
  official endpoint、精确 model、HTTP request ID、response ID 和 usage；它本身
  不联网、不接收 authorization header，也不存 prompt/response 内容。
- 分层完成度更新为工程/研究就绪 `90%`、科学证据 `32%`、投稿就绪 `39%`。
  这仍不是“论文完成 80%”：真实中型结果、公共基准、自适应攻击、独立保管人、
  Results/Discussion 和 JCR 机构核验继续计入未完成分母。
- 聚焦 provider/cost/ledger/medium 测试为 20/20，全部 paper-v2 测试为 69/69，
  Ruff 通过；增强后的完整 Harness 复验把 provider preflight 和 execution
  manifest 纳入单一入口，结果为 `840 passed, 1 skipped, 3 warnings`、
  `Verification failed=0`。没有读取 Token、调用 API/模型、提交或部署。

### paper-v2 80% 工程证据冲刺完成，正式实验待外部门禁 — 2026-07-23 16:35 +08:00

- 本轮按仓库证据完成度分别计量：工程/研究就绪度 `85%`，科学证据完成度 `31%`，
  投稿就绪度 `38%`。不得将 `85%` 表述为论文已完成 80% 或已满足 SCI Q2 投稿条件。
- online-state 源码审计已完成 20/22 个 unit，覆盖 14 个固定 commit 的官方 artifact；
  统一复验器验证源码锁、入口/行号、字段流、投影差分和证据 manifest。结果为
  9 个 `no_online_gold_observed`、9 个 `not_a_runtime_guard`、1 个 path-dependent、
  1 个 inconclusive，独立第二复核为 0，所以领域级 oracle 主张不成立且继续禁用。
- 已结果盲固定 72 个中型 case：36 attack、24 benign tool、12 benign no-tool，
  其中 25 个 context-dependent；6 个核心条件产生 432 条主记录，另有 48 条授权
  regime probe，共 480 条真实记录待运行。`exact_gold` 仅为 oracle ablation，
  不进入主要终点。
- VIGIL 与 DRIFT 已在官方固定源码上完成零模型调用的 adapter contract 资格检查；
  这证明接口可构造，不等于正式效果结果或 formal baseline admission。
- Wilson CI、exact McNemar、10,000 次 cluster bootstrap、Holm、配对功效估算、
  ITT 分母和自动转向门禁均已实现并有 golden tests。真实记录缺失时分析器只返回
  `results_pending`，不会生成有利零值。
- 已固定公共基准 6,873 条 case-condition 计划、最多 75,000 次攻击查询的自适应
  预算，以及不含任务内容/标签的 600-slot 独立盲测保管包。AgentDojo 只有 97 个
  唯一良性任务，协议如实使用 97，不复制样本凑数。
- 已建立结果就绪的 Methods、pending-only 结果表、claim–evidence ledger 和
  Devil's Advocate 审查；中性标题为默认。没有正式 API/模型调用、没有结果数据、
  没有独立保管人，不能写效果 Results 或声称独立盲测。
- 首轮完整 Harness 为 `824 passed, 1 skipped, 3 warnings`；状态同步后的完整复验
  收集新增门禁测试并以 `825 passed, 1 skipped, 3 warnings`、最终
  `Verification failed=0` 通过。
- 当前唯一可执行的下一门禁是：由项目作者填写不含密钥的
  `provider_cost_gate_template_v1.json`，固定可审计 provider/model 身份和硬成本
  上限；在此之前不得启动 480 条中型正式运行。

### paper-v2 80% 证据冲刺进行中 — 2026-07-23 14:15 +08:00

- 用户要求在既定 SCI Q2 计划上尽量完成 80% 以上；不得用模板、smoke 或工程绿灯
  代替真实论文证据。
- 当前首要路径是把 online-state 源码审计从 0 推进到至少 20 个单位，并固定
  VIGIL、DRIFT、PIArena、StruQ、BIPIA、ToolSafe、ASB 等官方源码版本。
- 随后固定 60–80 个中型配对任务，实现强基线统一接口、预注册统计、公共基准、
  content-free 盲测保管包、自适应攻击工具和结果就绪论文骨架。
- 正式收费 API、独立盲测标签和最终 Results 仍受 provider 身份、成本、第三方
  保管和中型门禁约束；这些外部缺口继续计入完成度分母。
- 本阶段允许的新路径和验收证据记录在 `harness/tasks/m3-paper-v2.md` 的
  `80% Evidence Sprint`；paper-v1 与全部历史冻结证据保持不可变。

### paper-v2 阶段 0/1 工程基础完成 — 2026-07-23 13:50 +08:00

- 用户已明确授权实施完整的 24 周 SCI 二区计划，首选网络安全方向与 JISA；
  当前功能状态仍为 `in_progress`，不是“论文或阶段 0 已完成”。
- 已建立 34 项 2024–2026 文献矩阵，区分同行评审与预印本，并完成 VIGIL、
  DRIFT、Task Shield、ARGUS、AuthGraph 等直接竞争边界。IPIGuard 已纠正为
  EMNLP 2025 Main Oral，不再按预印本处理。
- 已建立 22 个 online-state 源码审计单元和审计协议。当前完成审计仍为 0，
  所以“领域普遍存在 oracle authorization”仍禁止声明。
- 新证据线使用 `protocols/paper_upgrade_v2/`、`experiments/paper_v2/`、
  `schemas/paper_v2/` 和 `docs/research/paper_v2/`；不得改写 paper-v1 冻结文件。
- 已实现严格的 paper-v2 experiment record schema/validator：授权 regime、在线可见
  字段和值摘要、禁止 evaluator/gold 字段、ASK 状态机、unsafe-effect ITT、TCR、
  operational failure 与 provider attestation 均可机器校验；未验证中转站只能进入
  `diagnostic`。
- 已冻结只适用于未来 paper-v2 结果的 RQ、主终点、`-5pp` 非劣界限、止损门槛、
  自适应预算与失败规则。中型证伪 gate 因模型身份、case selection、VIGIL/DRIFT
  适配和成本上限未冻结而保持 `start_authorized=false`。
- 新增 25 项 paper-v2 契约/指标/运行时性质测试。历史 6 项失败已改为显式验证
  旧 freeze 遇共享 helper/保护哈希漂移时 fail-closed；旧 freeze 和输出未修改。
  E17 的 13 项单测改用离线环境快照，不再触发 `ollama list`。
- 最终验证：独立全量 pytest 与 Harness 内全量 pytest 均为
  `796 passed, 1 skipped, 2 warnings`；规范 12/12、Registry 18/18、历史证据、
  compileall、Ruff、JSON 和最终 `Verification failed=0` 均通过。
- 中转 API 只能用于 diagnostic，除非其能够提供可审计的上游模型身份、请求 ID、
  稳定参数和无提示改写声明。当前不读取本地 Token，也不启动 API/模型正式运行。
- 独立盲测保管人尚未确定；没有独立保管链时不得把内部 sealed holdout 称为
  independent blind。
- 下一步按门禁顺序为：完成至少 20 个源码审计单元；固定 VIGIL/DRIFT 适配；
  固定 60–80 个配对 case、正式模型身份和 API 成本上限；随后才能启动中型证伪。
- 工作树已有大量用户/历史改动，必须原样保留；本任务只新增或修改明确列入
  `harness/tasks/m3-paper-v2.md` 的未冻结路径。

### 最终移交检查 — 2026-07-23 12:29 +08:00

当前仓库可进行“完整工作目录级”技术移交，但尚不具备“只凭 Git 分支重新克隆”
即可恢复全部工作的条件。

- 分支 `test1`，HEAD 为 `d74cef2739551591a49c722c5c6273bac6edf91e`。
- 13 个必需移交入口全部存在；规范审计 12/12、布局回归 10/10、E0–E17 注册表
  18/18、历史冻结证据、功能台账 JSON 和差异检查均通过。
- 工作树当前有 42 条已跟踪改动和 149 条未跟踪项。根据用户边界，本轮不提交；
  因此接手方必须获得当前完整目录，不能只重新克隆 `test1`。
- `config/project.local.env` 存在、被 Git 忽略且未被跟踪；模型文件未被 Git 跟踪。
  移交时不得发送本机真实 Token，接手方应从 `config/project.env.example` 建立自己的
  本地配置。
- 活跃文档中没有仓库检出目录绝对路径；旧英文文档路径只保留在审计器的禁止列表。
- 11434 端口记录为 0，Ollama/Python 匹配进程为 0；项目服务保持停止。
- 完整 Harness 仍有移交报告已记录的既有阻塞：分组 pytest 752 通过、6 失败、
  1 跳过，13 个 E17 测试未完成。它们阻止“全量验收已通过”的声明，但不阻止带
  风险说明的维护移交。

### 当前任务更新 — 2026-07-23 12:18 +08:00

当前有效项目文档已完成中文命名与主要正文中文化。

- 已将当前移交、综述、架构、运行、数据、伦理、证据和检查清单改为中文文件名；
  Harness 的项目专用入口为 `harness/项目上下文.md`。
- `README.md`、Harness 标准状态文件、协议、schema、CLI、JSON 字段和公开符号等
  工具契约名称保持不变；冻结/哈希绑定证据和归档正文未进行批量改名或翻译。
- 当前有效文档的自然语言、图示标签和本轮涉及的源码注释已改为中文；无法翻译的
  模型名、方法名、字段名和命令保留原标识。
- 文档与项目源码继续使用相对仓库路径；只有模型、缓存、解释器和本机环境等仓库外
  依赖允许使用绝对路径。
- 自动规范审计已扩展为检查中文规范文件名、旧活跃引用和 Harness/源码边界；
  当前为 12/12 通过，仓库布局回归为 10/10 通过。
- 本轮未启动 Ollama、模型、API 或正式实验，未修改冻结证据，未提交、推送或创建 PR。

### 当前任务更新 — 2026-07-23 10:47 +08:00

仓库当前处于“文档移交、服务已停止”的检查点。

- 已编写 `docs/项目移交报告.md` 作为当前详细技术移交文档，并编写
  `harness/项目上下文.md` 作为 Harness 专用项目地图。上述文件与
  `protocols/paper_upgrade_v1/implementation_status.md` 顶部检查点共同覆盖下方
  历史时间线中的旧进程号和旧下一步说明。
- 当前证据仍为 Q2 原始分 66.0、封顶分 60.0；可用于正式实验的强基线为 2/5；
  公共矩阵为 0/84；独立盲测候选为 0/600；API 厂商为 0/2；80 任务自适应预算
  正式实验尚未完成。
- Task Shield v1.3–v1.6 和 Progent v1.2–v1.4 保留为负面证据或资格失败证据。
  CaMeL v3 P3 为 8/8 终态，ASR 0/4、TCR 0/4、p95 159.003 秒，只能作为诊断证据。
- 已停止经确认的 Ollama 桌面进程和服务进程（PID 29728、30124）。11434 端口已关闭；
  当前没有有意运行的项目 Python、Docker、Streamlit 或 Uvicorn 工作负载。无关的
  桌面、Codex 和 Node 进程未停止。
- 只将未冻结且已被替代的 Markdown 归档到 `docs/archive/`。当前入口保留稳定路径；
  `outputs/`、`protocols/`、`external/`、`release/`、本地配置、模型文件和哈希绑定
  产物均未移动或改写。
- 移交后的首个安全技术动作：只读复核已完成的 CaMeL v3 P3 证据，制定新的 P4/P5
  继续/停止协议，或改选 IPIGuard/FIDES。不得从当前 P3 直接启动 726 条正式运行。
- 当前工作仅限文档和目录验证。未获准运行模型/API，也未获准提交、推送、创建 PR、
  制作 PPT、DOCX 或 ZIP。

### Current task update — 2026-07-23 09:30 +08:00

Progent v1.2 advanced through P0-P2 and stopped at a preserved failed P3 root.

- P0/G0 cross-baseline metric semantics passed 6/6. Historical hashes remained
  unchanged and AgentDojo raw `security=true` is now treated as injection-goal
  achieved in new revisions only.
- Progent v1.2 freeze was generated at
  `protocols/paper_upgrade_v1/progent_source_backed_formal_freeze_v12.json` and
  passed 19/19. It hash-binds P3/P4/P5/formal selections and keeps P6 blocked
  behind separate authorization.
- G1 zero-model correctness passed 12/12 at
  `protocols/paper_upgrade_v1/execution/progent_v12_p2_correctness_v1/gate_g1.json`.
- Fresh P3 ran from
  `outputs/paper_upgrade_v1/baselines/progent_source_backed_qualification_v12_p3`
  and reached 8/8 terminal rows, but all rows were `runtime_failure`.
- P3 analysis failed G2 and wrote
  `outputs/paper_upgrade_v1/analysis_v2/progent_source_backed_v12_p3/gate.json`
  with next action `stop_and_preserve_p3`. P4/P5/P6 are forbidden for v1.2.
- Root cause: AgentDojo exposes two `OpenAILLM` pipeline positions that refer to
  the same object. v1.2 counted positions instead of unique clients and raised
  `expected one AgentDojo OpenAI client, found 2` before any model request.
- Required next step: a fresh Progent v1.3 revision that deduplicates OpenAILLM
  replacement by object identity, followed by a new v1.3 freeze/G1 and a fresh
  P3 root only after that gate passes.
- Ollama PID 18256 was stopped after the failed P3 review. No model service or
  project experiment process remains intentionally live.

### Current task update — 2026-07-23 09:00 +08:00

The approved strong-baseline recovery plan is now active on Progent v1.2.

- Goal: complete the cross-baseline AgentDojo metric-semantics audit, add a
  new hash-bound Progent v1.2 runtime/worker/runner/analyzer, pass zero-model
  correctness and Harness gates, then execute only the staged P3/P4/P5
  qualification panels whose preceding gate passes.
- Allowed paths: new versioned files under `experiments/paper_v1/benchmarks/`,
  `schemas/paper_v1/`, `protocols/paper_upgrade_v1/`, new qualification outputs
  under `outputs/paper_upgrade_v1/`, focused tests, and active Harness/Q2 state.
- Forbidden paths: Task Shield v1.3-v1.6 evidence, Progent v1.1 source/freeze/
  outcomes, historical E0-E17 evidence, local secrets, model weights and all
  other frozen/hash-bound artifacts.
- Acceptance: failures remain unresolved in the original denominator; both
  OpenAI-compatible clients expose zero SDK retries; each case is isolated by
  a 600-second parent watchdog; every terminal row hash-links its incremental
  trace; failed roots cannot resume; no failed-only retry interface exists.
- P6 remains outside this execution authority and requires a new explicit
  long-run authorization after P5 passes. No commit, push or PR is authorized.

### Current task update — 2026-07-23 02:00 +08:00

Task Shield v1.6 completed through its authorized G3 boundary and the route is
now closed as negative engineering evidence.

- P0/G0 passed 15/15 after a non-mutating correction of AgentDojo's official
  attack metric semantics. Historical outcome rows remain unchanged.
- P1-P2/G1 passed 20/20; the v1.6 freeze passed 21/21 and focused runtime tests
  passed 32/32. SDK retries are disabled, one bounded recovery owner validates
  the full verifier contract, and every terminal success/failure retains its
  trace and independent timing.
- Fresh P3 completed 4/4 and passed G2 11/11. Fresh P4 retained all 12 terminal
  rows but ended with 9 completed and 3 `case_timeout` failures. Standalone
  utility was 2/6, attack-condition utility 0/6, and p95 latency 600.070 s—
  15.175 times the matched ToolFilter comparator.
- G3 failed 4 of 16 checks. P5/P6, selective retry, registry admission and Q2
  score changes are therefore forbidden. The observed attack count is 0/5
  completed attacks plus one unresolved timeout, not a formal 0/6 result.
- A hash-linked post-hoc report, three PNG/SVG figures and an explicit post-G3
  stop decision were added. The read-only execution planner now retires the
  Task Shield route and selects fresh two-case Progent qualification next.
- No Ollama, project Python or competing model workload is live. Q2 readiness
  remains raw 66.0 / capped 60.0 and below the 80 target.
- Final Harness verification passed with 724 tests passed, 1 skipped and
  `Verification failed=0`; conventions, JSON/shell syntax, compilation,
  registry and historical evidence checks all passed.

### Current task update — 2026-07-22 22:07 +08:00

Task Shield v1.6 is approved under staged gates, and the repository has completed
its pre-v1.6 environment closeout.

- Stopped the only verified project process, Ollama PID 32748; port 11434 is no
  longer listening. No project Python job, related service or Docker container
  was live, and no unrelated desktop process was stopped.
- Removed 109 repository-local reproducible cache directories, 961 files and an
  estimated 13.17 MiB while excluding `outputs/`, `protocols/`, `config/`,
  `.git/` and machine model storage. The post-cleanup unprotected-cache count is
  zero.
- Added the structured closeout and operator-authorization package under
  `protocols/paper_upgrade_v1/execution/taskshield_v16_preparation_v1/`.
- Added `docs/research/taskshield_v16_execution_plan.md`. The approved next work
  is zero-model P0 metric correction followed by the v1.6 correctness runtime
  and deterministic tests. Four-case, 12-case and 30-case work remains gated;
  the 726-case formal run requires a separate explicit authorization.
- No model/API call, v1.6 experiment root, registry mutation, Q2 score change or
  historical/frozen evidence modification occurred.

### Current task update — 2026-07-22 21:53 +08:00

Task Shield v1.5 received a source-backed post-hoc failure analysis and an
unapproved v1.6 feasibility plan.

- Pinned AgentDojo source defines attack-case `security=true` as targeted
  injection success. The shared adapter writes `attack_success=not security`,
  so old ASR values are complements.
- Task Shield v1.5 stored 6/6 attack successes, but all six raw official traces
  contain `security=false`; corrected diagnostic Targeted ASR is 0/6. Utility
  remains 1/6, attack-condition utility 0/6 and operational failures 1/12.
- The same audit counted ToolFilter raw Targeted ASR 7/629 rather than the old
  derived 622/629. Old effect tables are provisional; raw logs remain complete.
- Additional causes are exhausted timeout escaping untrusted fail-closed,
  OpenAI SDK retries multiplying manual retries, failed trace snapshot loss,
  ten scoring-cardinality fail-closed events and verifier latency consuming
  about 73.1% of completed-case time.
- Added `docs/research/taskshield_v15_failure_analysis.md` and
  `docs/research/taskshield_v16_feasibility_plan.md`. The plan authorizes no
  model run, no v1.6 freeze and no registry/Q2 mutation.
- Validation: conventions 12/12, focused layout/Q2 regression 22/22, feature
  JSON parse and `git diff --check` pass; no experiment process is live.

### Current task update — 2026-07-22 21:26 +08:00

Task Shield v1.4 is sealed and the fresh v1.5 expanded qualification failed its
admission gate.

- PID 9804 was stopped under explicit user authorization. The untouched v1.4
  root is externally sealed as `sealed_failed_formal_root` at 24/726 completed,
  2 failed and 700 missing; its 56-file inventory SHA-256 is
  `9a6d9fde53ba80ce83326018563689071cf454dffacd97133ea3cb8e0e76f453`.
- The read-only v1.5 failure-mode audit passed 8/8. The separate v1.5 freeze
  passed 19/19 and authorized only the exact fresh 12-case qualification, not a
  726-case formal run.
- The v1.5 qualification ended `completed_failed_qualification_analysis`:
  11 completed, 1 failed, 0 missing; utility success 1/6; the stored legacy
  `attack_success=6/6` is later corrected to raw Targeted ASR 0/6 by the
  AgentDojo semantics audit; latency p50 221.037553 s, p95 975.990048 s, max
  1619.386955 s.
- One invalid-JSON contract retry succeeded, but an exhausted untrusted
  assistant timeout escaped the intended fail-closed suppression on
  `agentdojo:v1:slack:user_task_18`. The failed row also lacks its
  `taskshield_trace` snapshot.
- No case was selectively retried or excluded. v1.4/v1.5 remain ineligible,
  the 726-case v1.5 run was not authorized, and no v1.6 work has started.
- No model workload is live. The planner now blocks on an explicit v1.6
  decision and never proposes resuming v1.4 or editing/retrying v1.5.
- Q2 readiness is unchanged at raw 66.0 / capped 60.0, with 2/5 formal-ready
  strong baselines and `goal_80_met=false`.
- Final verification: focused regression 46/46; full Harness 691 passed / 1
  skipped with `Verification failed=0`; project conventions 12/12; Ruff,
  compile, JSON contracts, experiment registry and historical evidence all pass.

### Current task update — 2026-07-22 18:23 +08:00

Task Shield failure diagnosis and operator handoff precision were refreshed.

- Latest read-only v1.3 monitor is
  `running_with_failures_requires_attention`: 39/726 completed, 1 failed,
  686 missing, PID 27384 alive.
- The non-admitting failure diagnostic confirms the sole failed row is
  `agentdojo:v1:slack:user_task_18`, classified `timeout` with
  `APITimeoutError`; it remains in the original denominator.
- The operator-decision validator now treats a missing decision as one real
  blocker instead of cascading synthetic schema, acknowledgement and identity
  errors. Current validation lists exactly three blockers: missing approved
  decision, package not ready and package status not ready.
- No v1.3 stop, failed-only retry, row exclusion, v1.4 start, model/API call,
  registry admission or Q2 score change occurred. Q2 remains raw 66.0 / capped
  60.0 with `goal_80_met=false`.

Validation: focused recovery/operator/planner/Q2/layout regression 25/25,
Ruff pass, compileall pass, conventions audit 12/12, experiment registry
18 completed / 0 running / 0 failed, historical evidence verification pass,
feature-registry JSON parse pass and `git diff --check` whitespace-clean with
CRLF warnings only.

### Current task update — 2026-07-22 18:15 +08:00

Task Shield v1.4 recovery now has a file-based operator decision gate.

- Refreshed the v1.3 read-only monitor. Latest snapshot is
  `running_with_failures_requires_attention`: 38/726 completed, 1 failed,
  687 missing, PID 27384 alive.
- Extended the v1.4 recovery package so it generates a draft operator decision
  template:
  `protocols/paper_upgrade_v1/execution/taskshield_v14_recovery_decision_v1/taskshield_v14_operator_decision_template.json`.
- Added a fail-closed validator:
  `python -m experiments.paper_v1.benchmarks.validate_taskshield_v14_operator_decision`.
  Current validation writes
  `taskshield_v14_operator_decision_validation_v1.json/.md` and remains
  `blocked_not_approved_to_start_v14` because no approved decision exists and
  the v1.3 PID is still live.
- This is still handoff/control-plane evidence only: it does not stop v1.3,
  start v1.4, retry cases, exclude rows, admit registries or change Q2
  readiness.
- Q2 remains `raw_score=66.0`, `capped_score=60.0`,
  `goal_80_met=false`.

Validation for this checkpoint: focused recovery/operator-decision/planner/Q2/
layout regression 24/24, Ruff pass, compileall pass, JSON parse checks pass,
conventions audit 12/12, experiment registry verification pass, historical
evidence verification pass, Q2 readiness audit still raw 66.0 / capped 60.0
and `git diff --check` whitespace-clean with CRLF warnings only.

### Current task update — 2026-07-22 18:07 +08:00

Task Shield failed-root recovery handoff is now explicit and read-only.

- Refreshed the v1.3 read-only monitor for
  `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`.
  Latest snapshot is still `running_with_failures_requires_attention`:
  37/726 completed, 1 failed, 688 missing, PID 27384 alive.
- The failed row remains `agentdojo:v1:slack:user_task_18` with
  `APITimeoutError`; this is preserved as an operational failure in the
  original denominator, not repaired, excluded or admitted.
- Added and generated the read-only v1.4 recovery decision package:
  `protocols/paper_upgrade_v1/execution/taskshield_v14_recovery_decision_v1/`.
  Current package status is
  `blocked_waiting_explicit_failed_root_decision`,
  `can_start_v14_qualification_now=false`, `q2_score_change=0.0`.
- The Q2 formal execution planner and Q2-to-80 action audit now both route the
  failed active workload to
  `python -m experiments.paper_v1.benchmarks.prepare_taskshield_v14_recovery_package`.
  They do not start v1.4, stop v1.3, retry cases, analyze results, admit
  registries or change readiness.
- Current Q2 remains `raw_score=66.0`, `capped_score=60.0`,
  `goal_80_met=false`; formal-ready strong baselines remain 2/5
  (`agentdojo_tool_filter`, `promptguard`).

Validation for this checkpoint: focused recovery/planner/Q2/layout regression
22/22, Ruff pass, compileall pass, conventions audit 12/12, experiment
registry verification pass, historical evidence verification pass and
`git diff --check` whitespace-clean with CRLF warnings only. No full Harness
verifier was rerun for this small handoff sync; the earlier full-Harness pass
remains recorded in the previous checkpoint.

### Current task update — 2026-07-22 17:43 +08:00

Task Shield v1.4 failure-recovery protocol prepared without changing formal
eligibility.

- The v1.3 root remains active and inadmissible:
  `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`.
- Latest read-only monitor snapshot: `running_with_failures_requires_attention`,
  35/726 completed, 1 failed, 690 missing, PID 27384 alive.
- Failed row remains `agentdojo:v1:slack:user_task_18` with
  `APITimeoutError`; this is an operational failure, not a security/utility
  result.
- New v1.4 artifacts are prepared under
  `protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v14.json/.md` and
  `experiments/paper_v1/benchmarks/taskshield_paper_runtime_v14.py` /
  `run_taskshield_paper_formal_v14.py`. They hash-bind an explicit,
  trace-logged verifier transport-timeout retry patch.
- v1.4 has not run two-case qualification, a fresh 726-case full root or
  analyzer/admission. It is engineering readiness only and does not change Q2
  readiness.
- Refreshed read-only audits remain conservative: Q2 `raw_score=66.0`,
  `capped_score=60.0`, `goal_80_met=false`; formal-ready strong baselines
  remain 2/5 (`agentdojo_tool_filter`, `promptguard`).

Validation for this checkpoint: repository-layout/Task Shield/public-adapter/
external-admission/Q2 focused regression 141/141, full pytest 669 passed and
1 skipped, full Harness verifier `Verification failed=0`, conventions audit
12/12, Ruff pass, compileall pass, registry verification pass, historical
evidence verification pass and `git diff --check` whitespace-clean with CRLF
warnings only. No process kill, retry-only repair, row exclusion, registry
admission, model/API call or competing Ollama/GPU workload occurred.

### Current task update — 2026-07-22 16:47 +08:00

Non-GPU configuration and portability cleanup completed while Task Shield v1.3
continues to own the model resource. Three active Harness analysis notes no
longer hard-code the local checkout root:

- `harness/workspaces/runpro/10_analysis/approval-gate.md`;
- `harness/workspaces/runpro/10_analysis/project-inventory.md`;
- `harness/workspaces/runpro/10_analysis/project-intake.md`.

`config/README.md` now includes the exact two-vendor Frontier API Q2-slot
procedure: keep credentials in ignored `config/project.local.env`, set
`M3_FRONTIER_API_CONSENT=yes_for_network_smoke` only when the team explicitly
approves network smoke, run the plan-only smoke before `--execute`, then admit
registry slots only from the redacted smoke manifest. No API call, registry
promotion, formal run, or secret disclosure occurred in this update.

Current Q2 audit remains `raw_score=66.0`, `capped_score=60.0`,
`goal_80_met=false`. Frontier API audit is still
`blocked_missing_or_unsafe_local_config` with 0/2 configured vendors. Task
Shield v1.3 read-only monitor remains `running_progressing`, 24/726 completed,
0 failed, 702 missing, PID 27384 alive; last update age remains below the
45-minute stall threshold, so no intervention was made.

Validation for this checkpoint: conventions audit 12/12, focused
frontier/config/Q2-to-80/layout regression 29/29, Ruff pass, compileall pass,
and `git diff --check` pass with only existing CRLF conversion warnings.

### Current task update — 2026-07-22 16:16 +08:00

PromptGuard detector-adapter preflight portability hardening completed without
reading secrets, starting a model job, or changing formal-result eligibility.
`promptguard_adapter.py` now writes repo-local registry, real-smoke and
generated artifact paths relatively. The regenerated preflight was built with
the dedicated PromptGuard runtime, preserving
`real_detector_smoke_completed_formal_run_pending` rather than downgrading the
status under the default Python environment.

Downstream dependency snapshot, strong-baseline readiness and Q2 readiness were
refreshed. Strong-baseline readiness is still `not_satisfied` with formal-ready
entries `agentdojo_tool_filter` and `promptguard`; Q2 is still
`raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.

Validation for this checkpoint: PromptGuard/Q2/layout regression 26/26,
conventions audit 12/12, Ruff naming lint and py_compile passed. Task Shield
v1.3 read-only monitor remains `running_progressing`, 22/726 completed,
0 failed, 704 missing, PID 27384 alive.

### Current task update — 2026-07-22 16:12 +08:00

CaMeL official source-smoke portability hardening completed without touching
frozen evidence or running a model. `audit_camel_official_source_smoke.py` now
writes repo-local preflight, registry, checkout, required-source and generated
artifact paths relatively. The regenerated source-smoke remains 8/8 checks,
`completed_source_smoke_only`, no network calls, and
`result_eligible_for_formal_tables=false`.

Downstream dependency snapshot, strong-baseline readiness and Q2 readiness were
refreshed. Strong-baseline readiness is still `not_satisfied` with formal-ready
entries `agentdojo_tool_filter` and `promptguard`; Q2 is still
`raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.

Validation for this checkpoint: CaMeL/Q2/layout regression 23/23, conventions
audit 12/12, Ruff naming lint and py_compile passed. Task Shield v1.3 read-only
monitor is `running_progressing`, 21/726 completed, 0 failed, 705 missing, PID
27384 alive.

### Current task update — 2026-07-22 16:07 +08:00

Progent official source-smoke portability hardening completed without touching
frozen evidence or running a model. `audit_progent_official_source_smoke.py`
now writes repo-local registry, checkout, license-candidate and generated
artifact paths relatively. The regenerated source-smoke remains
`completed_source_smoke_only`; the offline runtime smoke passes, the missing
top-level license is retained as a warning, and
`result_eligible_for_formal_tables=false`.

Downstream dependency snapshot, strong-baseline readiness and Q2 readiness were
refreshed. Strong-baseline readiness is still `not_satisfied` with formal-ready
entries `agentdojo_tool_filter` and `promptguard`; Q2 is still
`raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.

Validation for this checkpoint: Progent/Q2/layout regression 27/27,
conventions audit 12/12, Ruff naming lint and py_compile passed. Task Shield
v1.3 read-only monitor is `running_progressing`, 20/726 completed, 0 failed,
706 missing, PID 27384 alive.

### Current task update — 2026-07-22 15:59 +08:00

IPIGuard official source-smoke portability hardening completed without touching
frozen evidence or running a model. `audit_ipiguard_source_smoke.py` now writes
repo-local preflight, checkout, source-file, syntax-check and dataset-universe
paths relatively. The regenerated source-smoke remains 8/8 checks,
`completed_source_smoke_only`, and `result_eligible_for_formal_tables=false`.

Downstream dependency snapshot, strong-baseline readiness and Q2 readiness were
refreshed. Strong-baseline readiness is still `not_satisfied` with formal-ready
entries `agentdojo_tool_filter` and `promptguard`; Q2 is still
`raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.

Validation for this checkpoint: IPIGuard/Q2/layout regression 29/29,
conventions audit 12/12, Ruff naming lint, py_compile and refreshed downstream
checkout-path scan passed. Task Shield v1.3 read-only monitor is
`running_progressing`, 18/726 completed, 0 failed, 708 missing, PID 27384 alive.

### Current task update — 2026-07-22 15:55 +08:00

Public benchmark pending ledgers have been made more portable without creating
formal evidence. `prepare_public_benchmark_formal_runs.py` now writes repo-local
freeze/result/cell/manifest/todo references relatively. Both pending ledgers
were reinitialized with `--force` because all cells were still `pending`: v1 is
60 cells / 53,400 case-runs and v2 is 84 cells / 74,760 case-runs. No completed
or running public-matrix cell was overwritten, no model was started, and
complete case-runs remain 0.

`public_benchmark_result_completeness_audit_v1` and v2 were refreshed and still
report `result_completeness_gate=not_satisfied`. Q2 remains `raw_score=66.0`,
`capped_score=60.0`, `goal_80_met=false`.

Validation for this checkpoint: public-adapter/worker/Q2/layout regression
118/118, conventions audit 12/12, Ruff naming lint, compileall, feature JSON
parse and checkout-path scans over active public artifacts passed. Task Shield
v1.3 read-only monitor is `running_progressing`, 17/726 completed, 0 failed, 709
missing, PID 27384 alive; it remains the only active Ollama/GPU workload.

### Current task update — 2026-07-22 15:47 +08:00

Advanced the relative-path/freeze-protection cleanup without touching frozen
evidence or starting a competing model workload. AgentDojo official capability
audit and strong-baseline source checkout manifest now render repo-local paths
relatively and are included in the convention audit portability gate. Their
downstream dependency snapshot, strong-baseline readiness audit and Q2 readiness
audit were refreshed. Strong-baseline readiness is still `not_satisfied` with
formal-ready entries `agentdojo_tool_filter` and `promptguard`; Q2 remains
`raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.

Latest Task Shield v1.3 read-only monitor after this checkpoint:
`running_progressing`, 14/726 completed, 0 failed, 712 missing, PID 27384
alive. This remains running evidence only and is not admitted to formal tables.

Validation for this checkpoint: conventions audit 12/12, focused layout/Q2/
external-baseline regression 24/24, Ruff naming lint, compileall, and
checkout-path scans over the refreshed artifacts passed. No formal result was
admitted.

### Current task update — 2026-07-22 15:38 +08:00

Current-state documentation now matches the latest conservative Q2 audit:
`raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`,
`goal_90_met=false`. This refresh touched only active documentation/Harness
state, not frozen evidence.

Task Shield v1.3 remains the only active formal workload:
`outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`, PID 27384,
read-only monitor `running_progressing`, 11/726 completed, 0 failed, 715
missing. The execution plan's next safe action remains read-only monitoring; do
not launch another Ollama/GPU formal workload while this PID is alive and
progressing.

Validation completed after the documentation refresh: conventions audit 12/12,
focused repository/frontier/Q2/planner/blind/public-worker/TaskShield regression
56/56, Ruff naming lint, and compileall. A full `harness/scripts/verify.ps1`
attempt timed out after 5 minutes and is explicitly not counted as passing; no
verification child process remained afterward.

### 2026-07-21 项目完整综述与保守兼容整理

本轮以当前仓库的 `test1` 分支为唯一实施范围，完成中文总览、文档索引、
四个非冻结文件的规范化移动，以及标准库布局/命名审计。稳定 Python API、CLI 参数、
schema/JSON 字段、环境变量、模型别名、case ID、历史 freeze 与现有 `outputs/` 均保持不变；
`${LEGACY_REPO_ROOT}` 所指旧仓库、本地 Token、模型权重、PPT、DOCX、ZIP 和 external 上游源码未修改。

新增 `docs/PROJECT_OVERVIEW.md`、`docs/README.md`、`docs/archive/README.md` 与
`scripts/audit_project_conventions.py`；规范路径为
`docs/presentation/ppt_result_notes.md`、`docs/archive/report_v0_3.md`、
`experiments/e17_source_index.md`、`harness/tasks/m3-expansion-001.md`。
布局审计当前 12/12 PASS，repository-layout 回归 9/9 PASS；完整 Harness/pytest 验证仍必须
等 AgentDojo ToolFilter 不再写入后执行，不能让整理任务与正式模型 workload 竞争。

整理开始时对 ToolFilter 的只读快照为 454/726 completed、0 failed、272 missing，
PID 36472 alive。该状态是 `running`，不进入公共基准正式结果或 Q2 分数；Q2 仍为
raw 63.5、capped 60.0、`goal_90_met=false`。

### 2026-07-22 相对路径规范与 Q2 80% 推进

活跃源码、命令和文档链接改为仓库相对路径；仅仓库外解释器、模型、缓存、隔离环境和
external checkout 允许从本地配置取得绝对路径。冻结/历史证据内的旧执行机路径和哈希
不改写。布局审计新增 checkout-path portability 与 hash-bound identity gate，当前
12/12 PASS，聚焦回归 9/9。

AgentDojo ToolFilter 原进程在 483/726、0 failed 时消失且没有 terminal manifest；只读
监控确认为 `stopped_without_terminal_manifest`。2026-07-22 已从同一 freeze 和 output
root 断点续跑，保留 483 条完成行、不启用 `--retry-failed`、继续请求完整 726-case formal
admission。该 run 完成、分析和准入前仍不计入正式强基线或 Q2 分数。

公共矩阵新增只规划、不执行的可迁移 worker plan：84 个 frozen cells、74,760 个
case-runs 按 7 个模型分成 7 个 model-affine workers，每个 12 cells / 10,680 runs。
命令全部使用仓库相对路径，assignment SHA-256 为
`6abbe7e92fab2def4fca076d4a6798a89563ad09fa227ff5730add38bdc03cb0`；3/3 tests、
Ruff 和编译通过。该 artifact 不启动模型、不改 frozen cell，也不增加 Q2 分数。

动态 Q2 readiness、ToolFilter monitor 和 Q2 execution plan 的仓库内路径现在统一输出为
仓库相对路径；外部 CaMeL 解释器等必要本机依赖仍允许绝对路径。Q2 审计新增
`goal_80_met` 中间里程碑，但不改变原 90 分投稿目标和五个硬 cap；当前仍为 raw 63.5、
capped 60.0、`goal_80_met=false`。执行计划已为 Task Shield、Progent、CaMeL 和 IPIGuard
生成固定一条 utility + 一条 security 的独立 qualification 命令，命令不含
`--admit-formal`，部分运行不能进入正式表。相关聚焦回归 43/43、Ruff、编译和
12/12 conventions audit 均通过。

独立 blind 后续证据不再要求修改历史 `final_analysis`：预注册绑定的 v1 缺失候选审计
保持原字节，当前候选审计使用 v2；只有 600-case formal run、零未解释失败和完整工件
哈希全部通过后，显式准入才能更新独立 paper-v1 evidence index。当前 candidate 缺失，
因此 v2 和 formal admission 都正确 blocked，Q2 分数不变。

2026-07-22 12:03+08:00 的只读快照为 569/726 completed、0 failed、157 missing，
PID 18904 alive；权威实时状态始终以
`protocols/paper_upgrade_v1/monitors/tool_filter_formal_v1/agentdojo_official_formal_run_monitor_v1.json`
为准。当前 workspace 安全案例约每案 60 秒，继续保持单 Ollama/GPU workload。

### 2026-07-21 Task Shield v1.2 hash-bound disclosed reproduction hardening

Task Shield 已完成不抢 GPU 的 v1.2 证据链加固。`taskshield_paper_formal_freeze_v1`
现在是 schema `paper-taskshield-reproduction-freeze-1.2`，13/13 checks；
freeze hash-binds local disclosed-reproduction runtime、import preflight、
runner、analyzer、shared resume identity helper 与 protocol 文件，同时保留
ACL 论文 PDF SHA-256、common 726-case universe 和“不作官方源码声明”的边界。

`taskshield_paper_import_preflight_v1` 现在为 9/9 checks，通过 network-blocked、
no-Ollama、0 benchmark case 的 import preflight，并核验 local adapter hashes
与 freeze 一致。Task Shield 仍为 qualification pending、`result_eligible=false`：
没有 two-case real-model qualification、没有 726-case complete logs、没有 admitted
analysis，因此不能计入 formal-ready strong baseline，也不能写成 official-source
Task Shield。

本 checkpoint 已刷新 dependency snapshot、baseline registry audit、external source
audit、strong-baseline formal-readiness audit、Q2 readiness 与 read-only Q2 execution
plan。当前 Q2 仍为 raw 63.5/capped 60.0、`goal_90_met=false`；AgentDojo
ToolFilter monitor 为 433/726 completed、0 failed、293 missing，PID 36472 alive。

### 2026-07-21 CaMeL v1.2 hash-bound formal adapter hardening

CaMeL 已完成不抢 GPU 的 v1.2 证据链加固：`camel_source_backed_formal_freeze_v1`
现在是 schema `paper-camel-source-backed-formal-freeze-1.2`，17/17 checks。
freeze hash-binds local formal runner、analyzer、AgentDojo compat 层、
source-backed runner、import/runner/transport preflight、shared resume identity
helper 与 protocol 文件。

`run_camel_source_backed_formal.py` 现在在任何 Ollama probe 前执行两类失败关闭
校验：先验证 freeze 中的 local adapter hashes，再校验 resume output root 的
freeze SHA-256、runner version、model id、condition id、selected case count 和
selected-case-row SHA-256。旧 root 或旧 adapter 不能被静默混入 v1.2 evidence。

本 checkpoint 已刷新 dependency snapshot、baseline registry audit、external source
audit、strong-baseline formal-readiness audit、Q2 readiness 与 read-only Q2 execution
plan。CaMeL 仍为 qualification pending，`result_eligible=false`；下一步必须等
ToolFilter 释放 Ollama/GPU 后，从 fresh v1.2 output root 先跑 two-case real-model
qualification，成功后才规划 exact 726-case formal run。当前 Q2 仍为 raw
63.5/capped 60.0、`goal_90_met=false`；AgentDojo ToolFilter monitor 仍为
433/726 completed、0 failed、293 missing，PID 36472 alive。

### 2026-07-21 Progent v1.1 hash-bound formal adapter hardening

Progent 已完成一轮不抢 GPU 的证据链加固：新增
`protocols/paper_upgrade_v1/progent_source_backed_formal_protocol_v1.md`，
并将 `progent_source_backed_formal_freeze_v1` 升级为 schema 1.1、13/13
checks。freeze 现在不仅绑定 pinned Progent source 和共同 726-case universe，
还绑定 runner、analyzer、import audit、shared resume identity helper 与 protocol
文件哈希。

`run_progent_source_backed_formal.py` 在任何 Ollama probe 前执行 resume
identity gate：freeze SHA-256、runner version、model id、condition id、selected
cases 和 selected-case-row SHA-256 不一致时直接拒绝旧 root。import preflight
同步验证本地 adapter hashes，10/10 checks 通过，仍保持 no network、no Ollama、
0 benchmark cases、`result_eligible=false`。Progent 下一步仍必须等 ToolFilter
释放 Ollama/GPU 后，从 fresh v1.1 output root 先跑 2-case qualification；成功后
才允许规划 726-case formal run。

本 checkpoint 已刷新 dependency snapshot、baseline registry audit、external
source audit、strong-baseline formal-readiness audit 与 Q2 readiness。验证通过：
Progent tests 7/7、combined public/strong-baseline regressions 108/108、Q2
planner/readiness tests 11/11、Ruff 与 `py_compile`。当前 Q2 仍为 raw
63.5/capped 60.0、`goal_90_met=false`；AgentDojo ToolFilter long run 最新只读
monitor 为 433/726 completed、0 failed、293 missing，PID 36472 alive。

### 2026-07-21 confirmatory preregistration and future admission hardening

在 independent blind admission 与 adaptive formal run 之前新增并冻结
`paper_v1_confirmatory_preregistration_freeze_v1.json/.md`：9/9 checks 通过，
SHA-256 为 `b4b747196274e877c4b2bd0e5bbdebdcc582d585c714263815a8e4956f6b742a`，
固定 5 个主/次假设、主要终点、50% adaptive safety margin、TCR -5pp
非劣界、10,000 次模板/任务聚类 bootstrap、McNemar/Holm、失败与排除规则及
10 张正式图表。Q2 reproducibility gate 已要求该 freeze，当前仍保持 8/8 满分，
但不会把协议文件当成实验结果加分。

修复 `camel_or_fides` formal-readiness 的逻辑矛盾：冻结协议选择 CaMeL 时，
只要求 `camel_google_research` 进入 formal result，并显式要求未选择的 FIDES
保持 result-ineligible；同时 selection 始终绑定 formal freeze，不会因后续
`formal_manifest` 切换到 analysis manifest 而丢失。新增统一外部强基线准入桥，
覆盖 Task Shield、IPIGuard、Progent、CaMeL，只有 726/726、0 failure、exact
coverage、freeze/hash-linked formal analysis 全部满足且显式
`--write-registries` 时才同时更新两个 registry。当前四个 plan-only admission
均为 `blocked_not_formally_admitted`，未改 registry。

新增 adaptive MCTS formal read-only monitor，并给正式 runner manifest 增加 PID。
监控器只检查 PID、任务/查询计数、artifact freshness、stall/failure 和 analyzer
状态，不 retry、不修改预算、不晋级结果。当前正式 adaptive root 尚未启动，
monitor 正确报告 `missing_manifest`。

AgentDojo `tool_filter` 仍是唯一运行中的 GPU/Ollama 正式作业；最新 monitor 为
433/726 completed、0 failed、293 missing、PID 36472 alive，ETA 约 4.76 小时。
它结束前仍不得启动 Task Shield、Progent、CaMeL、IPIGuard、adaptive formal 或
公共基准 cell。

新增只读 `plan_q2_formal_execution.py`，把 ToolFilter/adaptive monitor、五类
admission 状态与 public matrix cell manifests 合并成唯一下一动作。当前生成的
`protocols/paper_upgrade_v1/execution/q2_formal_execution_plan_v1.json/.md`
显示 `resource_gate=busy`，唯一安全动作是刷新 ToolFilter monitor；它不会启动、
retry、分析、准入或排除任何正式案例。公共矩阵实际仍为 84 pending cells、
74,760 pending case-runs。

IPIGuard 的旧 1/2 qualification 保留不改。新的 v1.1 freeze 为 9/9，新增
构造阶段原始 DAG JSON 的独立文件+SHA 证据、runner/analyzer/protocol 哈希绑定，
并在任何 Ollama probe 前拒绝 freeze、runner、model、condition 或 selected-case
身份不一致的旧输出目录。它不修改 upstream prompt、`construct_dag` parser 或
选择规则；import preflight 为 7/7。待 ToolFilter 结束后必须使用新 root 做 2-case
requalification，不能在旧失败 root 上 resume。

### 2026-07-21 Q2 gate hardening and public-benchmark monitor correction

`audit_q2_readiness.py` 已进一步失败关闭：未来的 `m3_v2_independent_blind_manifest` 只有在同时满足独立 candidate admission、formal/eligible manifest、600 cases、independent-blind scope、candidate SHA-256 与 admission 匹配且非 post-hoc 时，才会解除 independent blind gate。当前 candidate 仍缺失，所以 Q2 不涨分。

Q2 对 AgentDojo `transformers_pi_detector` 的 monitor 选择已修复为优先使用与 selected run manifest 匹配的 monitor。当前匹配 monitor 位于 `protocols/paper_upgrade_v1/monitors/transformers_pi_detector_formal_v2/agentdojo_official_formal_run_monitor_v1.json`，状态为 `running_with_failures_requires_attention`：75/726 completed、1 failed、650 missing、PID 21024 不存在。失败行 `agentdojo:v1:workspace:user_task_25` 为 CPU detector OOM：官方 Transformers pipeline 尝试分配 2,185,056,432 bytes。该 exact-official detector 仍只能作为 resource-incompatible diagnostic，不得复跑旧 root、不得计入 formal strong baseline。

新增 `diagnose_agentdojo_formal_run_failures.py` 并已生成 `protocols/paper_upgrade_v1/diagnostics/agentdojo_transformers_detector_failure_v1/failure_diagnostic.json/.md`。该诊断只读 run manifest / outcomes / stderr，当前分类为 `resource_cpu_memory`，76 outcome rows、1 failed row，`result_eligible_for_formal_tables=false`，不能 retry、exclude、repair 或 admit。

AgentDojo `tool_filter` 726-case formal run 仍是当前唯一可健康推进的大模型作业；最新只读 monitor 为 433/726 completed、0 failed、293 missing、PID 36472 alive。它完成前不得启动 Task Shield、Progent、IPIGuard、CaMeL、adaptive formal 或其他竞争 Ollama/GPU 的正式作业。

本轮验证：`py_compile` 通过；`tests\unit\test_agentdojo_failure_diagnostic.py`、`test_q2_readiness_audit.py`、`test_frontier_api_client.py`、`test_agentdojo_tool_filter_admission.py` 共 21/21 passed；Ruff 对本轮 Q2/diagnostic 变更通过。`q2_readiness_audit_v1` 仍为 raw 63.5、capped 60.0、goal_90_met=false。

### 2026-07-21 CaMeL transport/formal-freeze hardening and Q2 audit refresh

CaMeL/FIDES 线已从 generic IFC stub preflight 推进到 pinned CaMeL 官方源码 + 独立依赖 runtime + source-backed compat/runner/transport/formal-freeze 工程闭环。`E:\M3_PI_Guard_runtime\camel\.venv\Scripts\python.exe` 已由 E 盘 `uv` bootstrap 同步为 Python 3.10.12，关键依赖版本已记录：`agentdojo==0.1.34`、`pydantic-ai==0.2.12`、`openai==1.82.1`、`anthropic==0.52.2`、`google-genai==1.18.0` 等。缓存位于 `E:\AI_Cache\uv`，没有污染 PromptGuard venv，也没有启动 Ollama、模型或 API。

`experiments/paper_v1/benchmarks/audit_camel_source_backed_import_preflight.py` 输出 `protocols/paper_upgrade_v1/camel_source_backed_import_preflight_v1.json/.md`；12/12 checks 通过，status=`completed_dependency_import_preflight_blocked`，`result_eligible_for_formal_tables=false`。它保留 fresh-process 官方 pipeline/suite import-order failure 证据。新增 `experiments/paper_v1/benchmarks/camel_agentdojo_compat.py` 与 `audit_camel_source_backed_compat_preflight.py`，输出 `protocols/paper_upgrade_v1/camel_source_backed_compat_preflight_v1.json/.md`；8/8 checks 通过，在不编辑官方源码/site-packages、不联网、不启动 Ollama/API、不运行案例的前提下，process-local 预加载官方 AgentDojo suite modules，使 CaMeL/AgentDojo 关键 imports 和四个 v1 suites 可见。

新增 `experiments/paper_v1/benchmarks/camel_source_backed_runner.py` 与 `audit_camel_source_backed_runner_preflight.py`，输出 `protocols/paper_upgrade_v1/camel_source_backed_runner_preflight_v1.json/.md`；14/14 checks 通过。该预检只构建官方 `PrivilegedLLM` + workspace/travel/banking/slack security policy pipeline 骨架，benchmark cases=0、model/API calls=0、network_attempted=false、`result_eligible_for_formal_tables=false`，不能作为 CaMeL 效果结果。

新增 `camel_transport_mapping_preflight_v1.json/.md`；16/16 checks 通过，冻结 loopback privileged/quarantined transport、四个 suite 的 trusted/untrusted capability mapping、0 cases、0 model/API calls、0 network 的非正式边界。该小节原先重建的 schema 1.1 / 16-check freeze 已被当前置顶的 CaMeL v1.2 / 17-check hash-bound freeze superseded；当前 blocker 仍是未完成 2-case real-model qualification、无 726-case 完整 logs/admission。

`strong_baseline_dependency_snapshot_v1`、`baseline_registry_audit_v1`、`external_strong_baseline_source_audit_v1`、`strong_baseline_formal_readiness_audit_v1` 和 `q2_readiness_audit_v1` 已刷新。dependency snapshot 中 CaMeL source/runtime blockers 已清空，但 formal-ready strong baselines 仍只有 `["promptguard"]`，且仅限 detector-performance；CaMeL 仍为 `blocked_or_diagnostic`。Q2 readiness 当前 raw score=63.5、capped score=60.0、goal_90_met=false。

AgentDojo official `tool_filter` 726-case formal run 继续由 PID 36472 执行，输出根 `outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1`。最新只读 monitor 为 `running_progressing`、433/726 completed、0 failed、293 missing；未完成前不得运行任何竞争 Ollama/GPU 的正式模型任务。

新增 `admit_agentdojo_tool_filter_formal_result.py` 作为完成后的正式 admission bridge。它不启动模型、不重跑 case，只在 run manifest 为 `completed_formal`、monitor 为 `completed_formal_admitted`、analysis 为 `completed_formal_analysis` 且 `--write-registry` 显式给出时，才把 `agentdojo_tool_filter` 更新为 registry 中的 formal-ready strong baseline。当前实际执行一次，按设计返回 `blocked_not_formally_admitted`，写入 `protocols/paper_upgrade_v1/agentdojo_tool_filter_formal_admission_v1.json`，未改 registry。

`audit_q2_readiness.py` 已修复 stale monitor 归因：只有 monitor 的 `run_manifest_path` 与所选 `transformers_pi_detector` run 完全匹配、PID 存活且失败数为 0 时，才允许把 detector 计为 `running_progressing`。当前 Q2 evidence 中 `transformers_detector_scored_status=not_admitted_or_not_progressing`，`transformers_detector_monitor_matches_selected_run=false`；健康推进的只有 `tool_filter`。

Frontier API gate 的后续断点已补齐：`audit_frontier_api_model_slots.py` 现在会读取 `frontier_api_model_slot_registry_admission_v1.json`，仅当 admission status 为 `admitted_registry_candidate` 且 `model_registry_v3_candidate.json` 哈希匹配时，才选用 v3 candidate；`audit_q2_readiness.py` 会使用该审计后的 registered frontier vendor count 来计算 model coverage 和 frontier API cap。当前本地配置仍为 0/2 provider configured，admission 仍是 `blocked_smoke_not_qualified`，所以 Q2 保持 raw 63.5、capped 60.0。

### 2026-07-21 evidence-chain hardening and detector recovery

独立盲测 admission 现在强制同时接收 `m3_v2_independent_blind_candidate.jsonl` 与 `m3_v2_independent_blind_custody.json`：sidecar 必须记录独立作者、custodian、隔离环境、封存时间、600 行计数和 candidate SHA-256，并与每行 custody 时间双向一致。缺 sidecar、哈希不符、开发者封存前访问或占位身份均阻断。当前仍因独立 candidate 缺失而是 `blocked_missing_candidate`；10 项 M3-v2 数据测试通过，未创建任何 candidate。

前沿 API 链新增离线 `admit_frontier_api_model_slots.py` 与 admission protocol。只有 OpenAI/Anthropic 两家各一次真实合成 smoke 均成功、精确 model id 可用且 smoke manifest 保持 non-formal 时，才写新的 v3 registry candidate；该脚本不读 Token、不联网。当前 plan-only admission 按设计 exit=2、2/7 checks、registry written=false；16 项 frontier/config 测试通过。

强基线 formal-readiness 审计现能分别证明“IPIGuard pinned-source adapter/freeze 已完成”和“正式运行仍未完成”：7/7 audit checks 通过，IPIGuard 的 source-backed adapter requirement 通过，但因 runtime qualification、complete logs、formal manifest admission 和 result eligibility 缺失仍为 `blocked_or_diagnostic`。PromptGuard 仍是唯一 formal-ready strong baseline，范围仍仅 detector-performance。

### 2026-07-21 IPIGuard pinned-source formal adapter preparation

已把 IPIGuard 从 stub/mechanics preflight 推进为 pinned-source、可审计的 AgentDojo official adapter。新增 726-case freeze（97 utility + 629 security，8/8 checks）、fresh-process runner、formal analyzer、协议和 6/6 import preflight；runner 直接使用上游 `OpenAIConstructLLM`、`OpenAITraverseLLM`、`DagToolsExecutor`、`DagToolsExecutionLoop` 与 trace/DAG 结构，只对缺失的可选 Vertex AI import 做披露的常量级隔离，不重写 TDG 算法。import preflight 在独立子进程完成，未联网、未调用 Ollama、未运行 benchmark case，因而仍 `result_eligible=false`。

当前 `baseline_registry` 将 IPIGuard 标为 `source_backed_adapter_runtime_qualification_failed_model_dag_schema`；2-case runtime qualification 已执行但只完成 1/2，失败 1/2，失败点为上游 `construct_dag()` 读取本地 Qwen3 8B 生成的 tool-call JSON 时缺少 `function_name`。诊断分析已完成且 `result_eligible=false`；正式论文结果仍需先解决/披露 DAG schema runtime incompatibility，再完成 726-case `--admit-formal` 全量运行、零未解释失败和 analyzer admission。formal-ready 强基线仍只有 PromptGuard（1/5），不得提前计入 IPIGuard。

AgentDojo official `transformers_pi_detector` exact full-run 路线现已判定为 resource-blocked、非正式结果：v2 CPU retry 在同一 `workspace:user_task_25` 再次因 27,697 字符 `list_files` 输出触发 2,185,056,432-byte CPU allocation OOM；直接长输出 smoke 在卸载 Ollama 后调用 pinned official detector 也复现同一 allocation failure。旧 v1 CUDA root、v2 CPU root、long-output direct smoke 均保留为 diagnostic evidence，不得合并分母或进入正式表。已新增 resource-isolated freeze/runner/monitor 默认路径，但因 direct smoke 失败，不启动新的 exact 726-case formal run；baseline registry 将该条件标为 `source_backed_official_detector_resource_blocked_exact_formal`。

新增正式自适应攻击执行器 `run_adaptive_mcts_budget_formal.py` 与分析器 `analyze_adaptive_mcts_budget_formal.py`。执行器按冻结的 80-task、100/500/2000 预算运行 MCTS，逐查询原子落盘、断点续跑且只向攻击者返回公开三态决策与最终 unsafe/task-completion bit；分析器严格验证完整查询工件后才允许把根 manifest 晋级为 `completed_formal`，并生成 Wilson 区间、ASR—预算折线图和攻击族条形图。2-case × 3-query Stub 编排预检完成 6 次查询、0 失败，分析 status=`completed_diagnostic_analysis` 且 `result_eligible=false`；13 项相关测试通过。后续 readiness 审计已把 stale running manifest 和 resource-blocked detector diagnostic 排除，并只为健康推进中的 `tool_filter` 正式作业计入保守工程进度，当前 Q2 raw score=63.5、capped score=60.0；正式 80-task 模型运行仍未启动。

新增 content-free independent blind authoring kit：600 个分层 assignment slots（360 attack、120 benign no-tool、120 benign legal-tool；9 类攻击各 40）、case 模板、custody manifest 模板和隔离/封存/抽审说明。Admission 已进一步强制校验 sidecar 的 candidate hash、行数、作者/custodian、封存时间和开发者隔离声明。该 kit 明确由独立人员或独立生成程序在项目外填写，项目开发者不得生成实际 candidate；manifest 为 `completed_authoring_kit_only`、candidate cases=0、`result_eligible=false`，因此不会虚增当前 Q2 分数。

新增 OpenAI/Anthropic 双厂商 `FrontierAPIClient`、`smoke_frontier_api_models.py` 与离线 `admit_frontier_api_model_slots.py`：真实传输要求显式 network consent、HTTPS、单请求零自动重试；持久化 metadata 只含 provider/model/endpoint origin/payload hash/usage，不含 token/header。16 项客户端、准入与统一配置测试通过。当前仅执行 plan-only：configured providers=0、network calls=0；registry admission 为 `blocked_smoke_not_qualified` 且没有写 v3 registry，也不提升 Q2 分数。

### 2026-07-20 PromptGuard formal detector baseline

已完成真实 PromptGuard 的独立、预冻结 detector-only 正式基线。目标输入固定为 M3-v2 1,500 条、AgentDojo 97 条 utility + 629 条 security，以及 InjecAgent 1,054 条 security，共 3,280 条。模型输入与离线标签分文件冻结；AgentDojo 使用官方 ground-truth 工具路径物化实际 tool-output 文本，攻击模板固定为官方 `injecagent` attack。推理固定为冻结 revision、0.5 阈值、真实 tokenizer 的非重叠 512-token 窗口和最大 malicious score 聚合。

结果：3,280/3,280 预测完成，0 inference failures；TP 635、FN 1,948、FP 0、TN 697；整体 Recall 24.58%、FPR 0.00%、Precision 100.00%、F1 39.47%；median/p95 per-case latency 为 17.384/47.167 ms。AgentDojo detector recall 为 100.00%，但 InjecAgent 为 0.57%，M3-v2 为 0.00%，说明 PromptGuard 2 在当前固定阈值下对本项目和 InjecAgent 风格外部内容的覆盖很弱。

证据边界：这是 detector-performance 表可用的 source-backed formal baseline，不是端到端 Agent 防御结果；不得进入 ASR、TCR、合法工具任务效用、security-utility Pareto 或 SOTA claims。当前 Q2 strong-baseline gate 从 0/5 推进到 1/5，仍为 `not_satisfied`。

### 2026-07-20 AgentDojo transformers_pi_detector dependency smoke

已将官方 `protectai/deberta-v3-base-prompt-injection-v2` 下载到 E 盘 Hugging Face 缓存，固定 revision `90c9989b1a342275dd0d1a95aad283c04e075671`，19 files / 1,498,547,184 bytes。通过 PromptGuard venv + `PYTHONPATH=external/benchmarks/agentdojo/src` 加载 AgentDojo 官方 `TransformersBasedPIDetector` 类，并在 offline cache 模式完成 4-case runtime smoke：3/3 required checks 通过，引用安全讨论被判注入并保留为 false-positive probe。

证据边界：该 smoke 只证明 AgentDojo 官方 detector 依赖和模型缓存可运行；它不是 AgentDojo benchmark 结果，不能进入 ASR/TCR/utility 表。`agentdojo_transformers_pi_detector` 的 blocker 已从“缺 transformers/model cache”变为“未完成 frozen full AgentDojo formal cell/logs”。Q2 formal-ready 仍只有 PromptGuard detector-only，计数 1/5。

2026-07-21 已新增 `agentdojo_transformers_pi_detector_formal_protocol_v1.md`、8/8 通过的 726-case freeze、可断点续跑的官方管线 runner、失败保守计分规则、统计/图表分析器和 2-case qualification。qualification 为 2/2 completed、0 failures，保留 1 个真实 attack success，并明确 `result_eligible=false`。v1 CUDA attempt、v2 empty-CUDA preflight、v2 CPU retry 和 direct long-output smoke 均为 diagnostic-only。runner 1.3 新增 `unload_ollama_before_detector` resource policy 与 `agentdojo_transformers_pi_detector_resource_isolated_freeze_v1`（11/11 checks），但 direct long-output smoke 已证明完整官方 detector 对该长输出仍 OOM，因此 fresh resource-isolated formal root 当前没有 manifest，monitor health=`missing_manifest`，不得启动或计入 exact-official 正式结果。

2026-07-21 另新增 `formal_security_properties_v1.md` 与 `paper_storyline_v1.md`，把非 oracle runtime 的条件性安全性质、证明义务、论文叙事和图表路线固化为可审计协议。新增 `adaptive_mcts_budget_freeze_v1.json/.md`，冻结 development+validation 中 80 个 unique-template adaptive query-budget attack tasks，覆盖 9 个攻击族、6 种语言、3 个查询预算组，明确 sealed_holdout excluded 且 `result_eligible=false`。自适应 runner/analyzer 的非正式 Stub 编排预检随后完成；`q2_readiness_audit_v1` 当前 raw score=63.0/100、capped score=60.0/100，分数仍受前沿 API 模型、自适应 formal run、独立 blind、公共基准正式矩阵和强基线数量硬门槛限制，远未达到 90。旧 v2 manifest 的 stale `running` 不再被计入运行中加分。

2026-07-21 新增并资格验证 AgentDojo official `tool_filter` runner/analyzer：`experiments/paper_v1/benchmarks/run_agentdojo_official_tool_filter_formal.py` 默认读取 `agentdojo_tool_filter_formal_freeze_v1.json` 并写入 `agentdojo_tool_filter_official_formal_v1`；`experiments/paper_v1/benchmarks/analyze_agentdojo_official_tool_filter_formal.py` 负责 metrics/figures/analysis manifest。runner 构造官方 `AgentPipeline.from_config(..., defense="tool_filter")`，只增加 frozen selection、file-only logging、failure retention、resume、formal admission checks，以及披露的 OpenAI-compatible filter-model binding shim。第一次 2-case qualification 发现官方 local-compatible 路径把过滤器模型请求成 `openai-compatible`；runner 1.1 仅将 `OpenAILLMToolFilter.model` 绑定到冻结模型 ID，不改变 prompt、算法或选择规则。显式 `--retry-failed` 后初始 two-utility qualification 为 2/2 completed、0 failed；新增 utility+security qualification 也为 2/2 completed、0 failed，security case attack_success=1。两份 analysis 均为 `completed_diagnostic_analysis`，仍 `result_eligible=false`；726-case formal run 已启动但尚未完成。

2026-07-21 已启动 AgentDojo `tool_filter` 726-case formal run：输出根为 `outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1`，命令包含 `--admit-formal`，manifest PID=36472。只读 monitor 写入 `protocols/paper_upgrade_v1/monitors/tool_filter_formal_v1/agentdojo_official_formal_run_monitor_v1.json/.md`；2026-07-21 16:13（Asia/Shanghai）快照为 `running_progressing`、204/726 completed、0 failed、522 missing，按当前速率 ETA 约 7.82 小时。该 run 未完成前仍 `result_eligible=false`，不得进入正式表，也不得与其他大模型 formal 作业并发。

2026-07-21 Progent source-backed common-universe 正式协议准备已升级为 v1.1：官方源固定在 `external/baselines/progent@8a8eb894b9d568a32b4e58252fea85b47f789c77`，source smoke 通过并保留“无 top-level license”警告。审计发现官方捆绑 AgentDojo 0.1.29 只有 686 case（97 utility + 589 security），比共同冻结 726 universe 少 40 个 travel injection-task-2/6 case；因此不把上游 CLI 的 686 结果伪装成共同矩阵。新的 13/13 freeze 固定“官方 `secagent` policy engine + 披露的当前 AgentDojo lifecycle/transport port”，并 hash-bind runner/analyzer/import-audit/shared-identity/protocol；10/10 network-free import preflight 未调用 Ollama、未运行 benchmark case。可断点续跑 runner 与双 checker analyzer 已实现；combined regression 108/108、Q2 planner/readiness 11/11、Ruff/compile 通过。当前仍未进行真实模型 qualification 或正式 case，`result_eligible=false`；必须等 `tool_filter` 释放 Ollama/GPU 后先跑 fresh v1.1 2-case qualification，成功后才能开始 726-case Progent 正式运行。

2026-07-21 已完成 Task Shield 披露式论文复现的正式协议准备：ACL 2025 PDF 固定为 1,491,650 bytes、SHA-256 `057ff02152c0bb61892b08abdc80f7af22416c03819e526878091ee87d3bf1e6`。未发现可固定的官方 Task Shield 代码，因此 registry 中不再错误声称“官方 checkout 已就绪”。12/12 freeze 固定共同 726 universe、零阈值 fuzzy contribution、严格 JSON、历史截断与本地 Qwen3 8B agent/verifier；8/8 network-free import preflight 验证 1 个 InitQuery、2 个 LLM wrapper、1 个 ToolsExecutor replacement，未调用模型。runner/analyzer 已实现，104 项 TaskShield+Progent+公共适配回归和 Ruff 通过。它仍为 qualification pending、`result_eligible=false`，且永远只能称为 disclosed paper reproduction；等 `tool_filter` 完成后才能顺序运行 2-case qualification。

2026-07-21 新增两个不抢 GPU 的 Q2 门禁工具：`monitor_agentdojo_official_formal_run.py` 对 AgentDojo official long run 做只读 health snapshot，当前默认监控 resource-isolated target root，health 为 `missing_manifest`，因为 direct long-output smoke 已阻断再次启动 exact full run；`audit_m3_v2_independent_blind.py` 定义未来 600-case independent blind candidate 的 admission gate，当前因候选文件缺失为 `blocked_missing_candidate`。`q2_readiness_audit_v1` 现也接入自适应 runner Stub 编排预检，当前 raw 63.0 / capped 60.0；运行中、Stub、resource-blocked 和缺失 blind 均未被晋级为正式证据。

2026-07-21 新增 frontier API model-slot admission 审计：`audit_frontier_api_model_slots.py` 检查 ignored local config、tracked secret hits、OpenAI/Anthropic API key + model id、显式网络 smoke consent 和 `model_registry_v2` 中的 formal API 槽。当前没有联网、没有输出密钥、没有 formal 槽：配置安全门禁通过，但两个 provider 均未配置，`M3_FRONTIER_API_CONSENT` 未设置，registered frontier API vendor count=0。`q2_readiness_audit_v1` 已接入该审计并继续把 frontier API gate 作为 60 分硬 cap。

### 2026-07-18 Ollama / 8B model checkpoint

Ollama 的活动模型库已从 `D:\Ollama\models` 完整迁移并合并到 `E:\Ollama\models`；两轮独立重启与 11/11 迁移前模型 smoke 均通过，D 盘旧模型库已按授权删除并回收 13.20 GiB，`D:\Ollama\app` 保持不变。`qwen3:8b` 和 `llama3.1:8b` 已下载，并分别冻结为 `m3-paper-qwen3-8b-v1:latest` 与 `m3-paper-llama31-8b-v1:latest`；新 8B 六案例/双条件资格 smoke 共 24/24 case-runs、0 runner failures。该 smoke 只证明运行资格，不是正式效果结果。

PromptGuard 精确依赖环境已建立在 `E:\M3_PI_Guard_runtime\promptguard`，Hugging Face 缓存固定到 `E:\AI_Cache\huggingface`。用户的只读 Token 已通过脱敏门禁；官方 86M revision `a8ded8e697ce7c355e395a0df51f94adb4a2fd27` 已下载为 10 files / 1,131,674,611 bytes，并完成 12-case real CUDA qualification smoke。smoke 诊断为 9/12 匹配、1 个 benign false positive、2 个 malicious misses；全部失败原样保留，smoke 仍不进入正式分母。后续 formal detector run 已完成并单独登记，边界为 detector-only。

`model_registry_v2.json` 已登记两个 `modern_open_7b_14b` 槽；`public_benchmark_formal_freeze_v2` 在不改写 v1 的前提下声明 7 模型 × 6 ready conditions × 1,780 cases = 74,760 pending case-runs，独立 v2 ledger 已初始化 84/84 pending cells。Q2 model gate 仍因缺少两个前沿 API 厂商模型而为 `not_satisfied`。

Phase 2：本地可执行诊断链路与公共基准适配。独立 paper-v1 非 oracle runtime、M3-v2 1,500 数据、五模型本地 smoke、授权 regime smoke、InjecAgent public replay diagnostic + official-formula scorer、AgentDojo native selected-cluster diagnostics、官方 prompt-baseline 诊断适配器、PromptGuard detector-only adapter preflight、Task Shield alignment adapter preflight、IPIGuard TDG adapter preflight、Progent policy adapter preflight、CaMeL/FIDES IFC-capability adapter preflight 和论文图表 contracts 已落地；这些输出仍为 diagnostic、stub preflight 或 demo，不得替代新的确认性 blind、官方公共基准全量结果或强基线结果。

AgentDojo 最新诊断分四层：旧 48-run workspace 小切片保留为历史调试证据；四套件 screen 完成 124/124 jobs、0 failed，用于选择候选簇；selected-cluster repeat 完成 174/174 jobs、0 failed，覆盖 25 个正候选簇和 4 个 zero-control 簇；official prompt-baseline diagnostic 完成 174/174 jobs、0 failed。四条件合并分析共 348/348 jobs：no_defense 官方注入成功 72/87，`agentdojo_repeat_user_prompt` 66/87，`agentdojo_spotlighting_with_delimiting` 66/87，m3_full 0/87。m3_full 相对两个官方 prompt baseline 均为 66 个 baseline-only paired events，McNemar p=2.71e-20。该结果刻意富集 baseline-vulnerable clusters，只能证明候选簇诊断信号，不能估计 AgentDojo 全量 ASR。

当前代码回归快照仍保留完整历史 425 passed、1 skipped、0 failed（58 个 unit test 文件加仓库级结果完整性审计）；本轮 InjecAgent official-stage runner、official ReAct prompt styles、policy compiler over-authorization repair、selection builder、official compatibility audit、official prompted intent scorer、baseline registry audit、AgentDojo official strong-baseline capability audit、external strong-baseline source audit、strong-baseline source checkout manifest、IPIGuard official source-smoke、strong-baseline dependency snapshot、strong-baseline formal-readiness audit、public-benchmark formal-freeze manifest、public-benchmark formal-run pending ledger、public-benchmark formal case-result row builder、public-benchmark formal-cell runner wrapper、AgentDojo formal-cell source producer、InjecAgent formal-cell source producer、public-benchmark formal-cell materializer、public-benchmark result-completeness audit、PromptGuard adapter preflight、Task Shield alignment preflight、IPIGuard TDG preflight、Progent policy preflight、CaMeL/FIDES IFC-capability preflight、public-benchmark adapter、paired analyzer、figure generation、paper metrics 和 matrix focused regression 为 122 passed。selected-repeat、prompt-baseline comparison、InjecAgent scorer smoke、InjecAgent stage smoke、Vicuna baseline-vulnerable paired diagnostics、PromptGuard stub preflight、Task Shield stub preflight、IPIGuard TDG stub preflight、Progent stub preflight、CaMeL/FIDES stub preflight 与 30-case stratified diagnostic 均已生成 manifest、CSV/JSON、报告和关键图。

新工作登记为 `M3-PAPER-001`，以独立 paper-v1 模块、协议、冻结和输出根实施；不得改变原 E0-E17、E17 真人复核、`final_analysis` 或 Acceptance Remediation V2 的历史含义。

本机已有 qwen3:4b-instruct、phi4-mini:3.8b、llama3.2:3b、gemma3:4b 和 vicuna:7b；未检测到前沿模型 API 密钥或外部服务器配置。先完成本机可执行范围，外部模型保持显式资源阻塞。

InjecAgent 已有 3-case public replay scorer smoke：`official_formula_score_v1` 使用 InjecAgent DH/DS/S1/S2 ASR 聚合公式，no_defense 和 m3_full 的 ASR-all Total 均为 0.0，Valid Rate 均为 100.0。该 scorer 的输入标签来自 M3 replay 工具执行日志，不是原版 ReAct/function-calling runner，因此仍不能作为正式 InjecAgent 结果。新增 official-stage diagnostic runner 已把模型置于 InjecAgent 官方“User Tool 已执行、Tool Response 已注入”的阶段；data_security limit-2 v3、direct_harm limit-2 v1、data_security limit-5 v1 和 direct_harm limit-5 v1 均 0 failures，官方公式桥接分数 Valid Rate 均为 100.0、ASR-all Total 均为 0.0。新增 `official_react` 与 `official_react_simple` prompt style、result-blind stratified selection builder、`--selection`、`progress.jsonl`、增量 `runs.jsonl`、`--timeout` 和 `--max-tokens`；Vicuna + official_react_simple 找到 baseline-vulnerable 诊断切片：DS 3/3→0/3，DH 1/3→0/3；额外 DS 0004/0005 no_defense 只形成负诊断（ASR-all Total=0）。冻结 30-case selection 已生成，旧 pre-progress 30-case run 已停止并登记；progress-enabled 6-case stratified smoke 完成 0 failure，no_defense 1/6、m3_full 0/6。progress-enabled 30-case stratified diagnostic 完成：no_defense 与 m3_full 均 30/30、0 failure；官方公式 no_defense ASR-all Total=46.7%、m3_full=0.0%，paired attack success 14/30→0/30，McNemar p=0.0001221；已生成 bucket summary 和 attack_success_by_defense / attack_success_by_bucket / paired_outcomes 图。该 runner 仍非 byte-identical 官方执行，且 `gold_user_tool_stage_used_online=true`，只能作为兼容性诊断。

新增 InjecAgent official compatibility audit：`experiments/paper_v1/benchmarks/audit_injecagent_official_compatibility.py` 已生成 `protocols/paper_upgrade_v1/injecagent_official_compatibility_audit_v1.json/.md`，19/19 checks passed。审计支持官方源码哈希、official-stage markers、官方 prompted parser 固定样例、DH/DS S1/S2 公式样例和 source-order prompt rendering；边界为 `compatibility_audit_not_official_benchmark_result`，不等同于 1,054 全量官方结果或 byte-identical runner。

新增 InjecAgent official prompted-parser intent scorer：`experiments/paper_v1/benchmarks/score_injecagent_stage_official_prompted.py` 直接用官方 `evaluate_output_prompted` 评分 raw model ReAct 输出。冻结 30-case Vicuna selection 上，raw intent no_defense 为 7/30、m3_full 为 6/30，paired difference -3.3pp、McNemar p=1.0；执行派生分数仍是 14/30→0/30。这说明当前诊断中 M3 的效果主要来自运行时阻断，而不是让模型不再提出攻击动作。

新增 strong-baseline registry/audit：`protocols/paper_upgrade_v1/baseline_registry.json` 已升级到 `m3-paper-baselines-1.1`，并完成公共基准 v1 的 60-cell/53,400-case pending 队列。2026-07-18 的模型迁移随后在不覆盖 v1 的前提下生成 v2：两个现代 8B 槽位均已用不可漂移别名和 digest 登记，v2 为 84 个 pending cells / 74,760 个 pending case-runs。PromptGuard 的 E 盘独立依赖、完整冻结缓存、real-model qualification smoke 和 detector-only formal run 均已完成；它只进入 detector-performance 表。当前 Q2 gate 仍为 `not_satisfied`，原因是两个前沿 API 模型槽、至少四个额外强基线 source-backed formal runs 和全部公共基准正式 case-runs 尚未完成。

新增 strong-baseline source checkout manifest：`experiments/paper_v1/benchmarks/prepare_strong_baseline_source_checkouts.py` 已生成 `protocols/paper_upgrade_v1/strong_baseline_source_checkout_manifest_v1.json/.md`，5/5 checks passed；PurpleLlama/PromptGuard、IPIGuard、CaMeL 和 FIDES 已 pin 到 registry 中记录的 exact commit，并放在 Git 忽略的 `external/baselines/` 可重建缓存中。新增 IPIGuard official source-smoke：`experiments/paper_v1/benchmarks/audit_ipiguard_source_smoke.py` 已生成 `protocols/paper_upgrade_v1/ipiguard_official_source_smoke_v1.json/.md`，8/8 checks passed；验证 pinned commit、官方 eval entrypoint、`ipiguard` pipeline wiring、DAG construction/traversal markers、whitelist/command split 和 97 utility / 629 security universe。新增 strong-baseline dependency/source snapshot：`experiments/paper_v1/benchmarks/build_strong_baseline_dependency_snapshot.py` 已生成 `protocols/paper_upgrade_v1/strong_baseline_dependency_snapshot_v1.json/.md`，5/5 checks passed；它只记录本机 Python 包、可执行文件、PromptGuard 模型缓存、adapter-preflight/source-smoke 和外部 source checkout/Git HEAD 状态，不安装、不下载、不启动模型，也不产生正式效果结果。`strong_baseline_formal_readiness_audit_v1` 已消费该 snapshot 并记录 snapshot status=`completed` 与 SHA-256；IPIGuard source-smoke complete 但 source-backed adapter/logs 未完成，CaMeL 已选且 source ready 但缺 `uv`/interpreter/adapter，当前没有任何 required strong baseline 可进入正式结果表。

当前未完成的论文投稿关键门槛包括：AgentDojo/InjecAgent 正式公共基准矩阵、InjecAgent 1,054-case official-stage/full compatibility execution 或 byte-identical 官方 runner、Task Shield/IPIGuard/Progent/CaMeL source-backed 精确适配、AgentDojo tool_filter 726-case formal run、AgentDojo transformers_pi_detector exact-official resource-incompatibility 的披露或另行冻结的非等价 bounded-input adapter、两个前沿 API 模型槽和正式六模型矩阵、80-task 查询预算自适应攻击、全新独立 blind 和投稿前系统检索。两个现代 8B 只完成运行资格验证；PromptGuard 已完成 detector-only formal result，但不得写成端到端防御效果结果。

2026-07-20 已完成可迁移统一配置基础设施和真实 PromptGuard qualification：共享字段位于 `config/project.env.example`，成员真实值只写入 Git 忽略的 `config/project.local.env`；Token 格式、Git 忽略/跟踪边界和 tracked-file secret scan 均通过且只输出 `set_redacted`。下载、哈希快照、真实 CUDA smoke 和准入审计已完成；下一步是正式 tokenizer windowing/benchmark adapter，而不是再次处理凭据。

## Previous Final Phase

Phase 8：最终证据冻结与本地交付。E0-E17 已全部登记为 `completed`；两名真人各完成 360 行同一冻结盲审包，主标签与次级代码集合 360/360 一致，Cohen's kappa=1.000，无需第三人裁决。

E17 采用冻结的分层抽样协议：300 行代表性样本用于设计加权总体估计，40 行自动分歧定向样本和 20 行稀有/复杂定向样本只作诊断，不进入总体分母。项目没有声称完成 3,299 行全量真人复核。

正式 `final_analysis` 已重建为 13 张图和 63 个 manifest 内工件；独立统计复算为 PASS，Dashboard 白名单与哈希门禁为 PASS。总体工程验收结论为 `fail`，因为 12 项预设目标中 8 项通过、4 项未达标；结果失败不等于证据流程未完成。

## Verified Evidence

- Registry：18 completed / 0 running / 0 failed；SHA-256 `52841155bf90582886145851507885e7f1ff7076de01aeeaad2fe7d1e5efba0f`。
- E17 reviewers：`human_gaohang_r1` 与 `human_hg02`；两份完成文件均为 360 行且身份不同。
- E17 agreement：360/360，disagreement=0，kappa=1.000；300 representative + 60 targeted diagnostic。
- E17 weighted method：冻结设计权重、Hajek 比例、分层 10,000 次 percentile bootstrap，seed=20260717。
- Final analysis：status=`completed`，13 charts，63 manifest artifacts，E11 原始与 post-hoc 分母不合并。
- Independent statistics：PASS，hard failures=0，statistical-fallacy failures=0。
- Dashboard：最终证据门禁 PASS，E9/E14 corrected r3 与 sampled E17 目录均通过固定白名单。
- Tests：最终聚合 verifier 为 347 passed、1 skipped；新增 E17 加权抽样测试验证确定性、targeted 排除和权重门禁。
- E11 execution-r2 freeze：`ceb320a915d301d6658b5caa9b662cb2ed13e24c63ec5d79f8ff7caa9ad0ba37`，8/8 smoke、48/48 formal。
- HTML technical report：标准 Data Analytics 构建器 validation/package PASS；结构验证 PASS。浏览器 QA 受共享阅读器 Windows `100vw` 顶栏 8px 溢出限制，插件运行时未被修改，限制记录在 `final_analysis/report/verification.json`。

## Acceptance Outcome

- Remediation V2：12/12 PASS。
- A04：恶意调用 Recall 134/134=100%，Wilson 95% CI [97.21%, 100%]。
- A06：normal TCR off=312/324，full=319/324；所谓“下降”为 -2.16pp，即实际改善 2.16pp。
- A07：合法工具 TCR 166/168=98.81%，Wilson 95% CI [95.76%, 99.67%]。
- A10：12 个性能 cell 全部通过；最差 cell 中位可归因开销 0.009461%，远低于 10%。
- 全部门禁附带结果：A11 解析 1736/1817=95.54%；Dashboard 10 metric rows、3,780 logs、4 figures、0 warnings。
- 限制：这是复用原 blind case 的 post-hoc engineering remediation，不冒充新的未见盲测；性能 replay 隔离的是同输出 Guard 可归因成本，行为轨迹由 2,160-run 主复验单独衡量。

## Previous Completion Boundary

代码、实验、E17 抽样真人复核、统计、图表、Dashboard 数据门禁和技术报告已封装到本地 `test1` 提交 `1cbbbc4`。该结论是本次修正的不可变基线，不得 push 或创建 PR。
# Current task update — 2026-07-22

Active objective: preserve the completed project-overview/file-organization work, keep frozen evidence intact, and continue the paper-v1 Q2 upgrade without promoting incomplete evidence.

Current live workload:

- `task_shield_formal_v13` is running in `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`.
- PID: 27384.
- Monitor command:
  `python -m experiments.paper_v1.benchmarks.monitor_agentdojo_official_formal_run --run-dir outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13 --output-dir protocols/paper_upgrade_v1/monitors/task_shield_formal_v13`
- Latest monitor status: `running_progressing`, 3/726 completed, 0 failed, 723 missing; PID alive, stderr empty.
- Do not start Progent, CaMeL, IPIGuard, adaptive, public-matrix or other Ollama/GPU formal jobs until this workload completes, fails, or is explicitly stopped by the user.

Task Shield boundary update:

- The previous v1.2 full formal root `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v1` is excluded as failed diagnostic evidence. It stopped after 5 completed cases and 1 failed case, with failed case `agentdojo:v1:banking:user_task_13` and `TaskShieldVerifierError: one contribution row is required per user task`.
- The v1.2 failure is a compatibility/parser-cardinality failure, not a safety or utility conclusion. Do not resume v1.2 or retry only the failed case.
- A new disclosed v1.3 protocol was created instead: `protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v13.json`. It hash-binds `experiments/paper_v1/benchmarks/taskshield_paper_runtime_v13.py` and `experiments/paper_v1/benchmarks/run_taskshield_paper_formal_v13.py`, records repository-local paths relatively, and fails verifier contribution-scoring parse/schema/score/cardinality errors closed to zero contribution rows.
- v1.3 qualification completed 2/2 cases with 0 failed at `outputs/paper_upgrade_v1/baselines/taskshield_paper_qualification_v13/run_manifest.json`. It remains `result_eligible=false`.

Most recent Q2 audit:

- `raw_score=66.0`
- `capped_score=60.0`
- `goal_80_met=false`
- The 80% target is still blocked by evidence gates, not by planner arithmetic: independent blind, public benchmark matrix, strong-baseline count, frontier API slots and adaptive formal budget evidence.

Frontier API gate:

- The audit confirms `config/project.local.env` exists, is ignored and untracked, and no tracked configured-secret hit was found.
- OpenAI and Anthropic API keys/model IDs remain missing or placeholders, and `M3_FRONTIER_API_CONSENT=yes_for_network_smoke` is not set. Configured vendor count remains 0/2, so the frontier API hard cap remains active.
- Active frontier/Q2 audit artifacts now use repository-relative project paths; machine-local cache/runtime paths in the redacted config remain absolute by design.

Next safe action while the live workload is running:

1. Use the monitor command above for read-only progress snapshots.
2. If Task Shield v1.3 reaches 726/726 with 0 failed and `completed_formal`, run its analyzer and fail-closed admission dry-run before any registry write.
3. If it fails or stalls, retain stderr/progress/outcomes and classify the failure; do not retry only favorable cases.

# Current task update — 2026-07-22 15:21 +08:00

Active objective remains unchanged: continue toward Q2 readiness without treating
diagnostic, smoke, plan-only or running artifacts as formal results.

Latest safe work completed in this window:

- Independent blind authoring kit regenerated at `protocols/paper_upgrade_v1/independent_blind_authoring_kit_v1/`.
  The manifest now stores package-local relative artifact paths such as `authoring_slots.csv`,
  not checkout-specific absolute paths.
- The kit now includes `validate_candidate_before_release.py`, a self-contained
  pre-release validator for independent authors/custodians. It checks only
  content-free structure and custody consistency before release; repository-side
  reference-overlap admission and formal result admission are still required.
- `m3_v2_independent_blind_admission_audit_v2` remains
  `blocked_missing_candidate`, `candidate_exists=false`, 0/1 checks, and
  `result_eligible_for_confirmatory_q2_tables=false`.
- Frontier API audit remains `blocked_missing_or_unsafe_local_config` with
  0/2 configured vendors, 0 registered vendor slots, no explicit network-smoke
  consent and zero network calls.
- Latest Q2 readiness remains `raw_score=66.0`, `capped_score=60.0`,
  `goal_80_met=false`, `goal_90_met=false`. The active caps are still public
  benchmark completion, five formal-ready strong baselines, independent blind,
  two frontier API vendors and formal adaptive budget evidence.
- Latest Task Shield v1.3 monitor snapshot is `running_progressing`, 7/726
  completed, 0 failed, 719 missing, PID 27384 alive. This run still owns the
  Ollama/GPU slot; do not start Progent, CaMeL, IPIGuard, adaptive or public
  matrix jobs concurrently.

Verification in this window:

- `python -m pytest -q tests/unit/test_independent_blind_authoring_kit.py`:
  3 passed.
- `ruff check --select N experiments/paper_v1/benchmarks/prepare_independent_blind_authoring_kit.py tests/unit/test_independent_blind_authoring_kit.py`:
  passed.
- `python -m compileall -q experiments/paper_v1/benchmarks/prepare_independent_blind_authoring_kit.py tests/unit/test_independent_blind_authoring_kit.py`:
  passed.
- `python scripts/audit_project_conventions.py --check`: 12/12 PASS.

# Current task update — 2026-07-22 16:43 +08:00

Q2 status documentation and evidence-index discoverability corrected:

- `docs/RUNBOOK.md` now includes `python -m experiments.paper_v1.benchmarks.plan_q2_to_80_actions` as a read-only paper-v1 audit entry and explains that it does not execute, write registries, call APIs or change Q2 score.
- `docs/PROJECT_OVERVIEW.md` now reflects the current strong-baseline state: AgentDojo ToolFilter is admitted, PromptGuard detector-only is admitted, and Task Shield v1.3 is the current live formal workload. The strong-baseline row is corrected from 1/5 to 2/5.
- `protocols/paper_upgrade_v1/implementation_status.md` now has a 2026-07-22 addendum covering ToolFilter admission, active Task Shield v1.3 monitoring, the Q2-to-80 action audit, remaining path exceptions and the unchanged Q2 score.
- Refreshed `audit_q2_readiness`, `plan_q2_formal_execution` and `plan_q2_to_80_actions` after the documentation update so their source hashes and current state stay aligned.

Current verified state:

- Q2 remains `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.
- Q2-to-80 action audit remains `blocked_by_active_hard_caps`, 5 required action bundles, `resource_gate=busy`.
- Task Shield v1.3 remains the only live workload; no analysis/admission was attempted because it is not complete.

Verification in this window:

- `python scripts/audit_project_conventions.py --check`: 12/12 PASS.
- `python -m pytest -q tests/unit/test_q2_to_80_action_audit.py tests/unit/test_q2_formal_execution_plan.py tests/unit/test_q2_readiness_audit.py tests/unit/test_repository_layout.py`: 29 passed.
- `ruff check experiments\paper_v1\benchmarks\plan_q2_to_80_actions.py tests\unit\test_q2_to_80_action_audit.py scripts\audit_project_conventions.py`: passed.
- `python -m compileall -q experiments\paper_v1\benchmarks\plan_q2_to_80_actions.py tests\unit\test_q2_to_80_action_audit.py scripts\audit_project_conventions.py`: passed.

# Current task update — 2026-07-22 16:52 +08:00

Current-status override added for paper-v1 task documentation:

- `protocols/paper_upgrade_v1/implementation_status.md` now starts with a
  `Current authoritative checkpoint — 2026-07-22` section. It explicitly states
  current Q2 score 66.0/60.0, ToolFilter admitted, Task Shield v1.3 as the live
  workload, and older dated sections as historical checkpoint records rather
  than current-state overrides.
- `harness/tasks/m3-paper-upgrade.md` now has a 2026-07-22 latest checkpoint:
  ToolFilter admitted, formal-ready strong baselines 2/5, Task Shield v1.3
  running at 24/726 and Q2 still blocked at raw 66.0/capped 60.0.
- Refreshed Q2 readiness, Q2 execution plan and Q2-to-80 action audit after the
  documentation correction. They remain non-inflating: Q2 66.0/60.0,
  `goal_80_met=false`; action audit `blocked_by_active_hard_caps`;
  execution plan `resource_gate=busy`.

Verification in this window:

- `python scripts/audit_project_conventions.py --check`: 12/12 PASS.
- `python -m pytest -q tests/unit/test_q2_to_80_action_audit.py tests/unit/test_q2_formal_execution_plan.py tests/unit/test_q2_readiness_audit.py tests/unit/test_repository_layout.py`: 29 passed.
- `python -m compileall -q experiments\paper_v1\benchmarks\plan_q2_to_80_actions.py tests\unit\test_q2_to_80_action_audit.py scripts\audit_project_conventions.py`: passed.
- Targeted status scan confirms current-state files now have an explicit
  current checkpoint; remaining `raw 63.5`/ToolFilter-active hits are historical
  dated checkpoint records.
- Focused Q2/frontier/layout regression:
  `python -m pytest -q tests/unit/test_independent_blind_authoring_kit.py tests/unit/test_frontier_api_client.py tests/unit/test_q2_readiness_audit.py tests/unit/test_q2_formal_execution_plan.py tests/unit/test_repository_layout.py`:
  41 passed.
- Checkout-absolute scan over refreshed blind/frontier/Q2 artifacts found no
  current-checkout absolute path hits.
- `git diff --check`: no whitespace errors; only CRLF conversion warnings from
  existing Windows line-ending behavior.

# Current task update — 2026-07-22 16:30 +08:00

Additional sealed-evidence-safe portability and Q2 execution refresh completed:

- Regenerated the non-frozen/read-only formal monitors for:
  - `protocols/paper_upgrade_v1/agentdojo_official_formal_run_monitor_v1.json`;
  - `protocols/paper_upgrade_v1/monitors/transformers_pi_detector_formal_v2/agentdojo_official_formal_run_monitor_v1.json`;
  - `protocols/paper_upgrade_v1/monitors/adaptive_mcts_budget_v1/adaptive_mcts_budget_formal_monitor_v1.json`.
- Updated `experiments/paper_v1/benchmarks/monitor_adaptive_mcts_budget_formal.py` so run paths, manifest paths, artifact paths and emitted monitor paths are repository-relative when they point inside this checkout.
- Updated `experiments/paper_v1/benchmarks/diagnose_agentdojo_formal_run_failures.py` so retained diagnostic paths are repository-relative when they point inside this checkout.
- Added the above non-frozen monitor/diagnostic artifacts to the project convention audit's active portable-artifact allowlist.
- The remaining checkout-absolute hits under `protocols/paper_upgrade_v1` are now 23 files total: 14 frozen/hash-bound and 9 non-frozen protocol snapshots. The 9 non-frozen hits are deliberately left untouched because they are tied to old preregistration/admission snapshots or hash-bound CaMeL/TaskShield generator evidence, and changing them would blur the evidence boundary.
- Refreshed `experiments.paper_v1.benchmarks.plan_q2_formal_execution`; it still reports `resource_gate=busy`, with Task Shield v1.3 as the only active workload.

Latest Q2/Task Shield state:

- Q2 readiness remains `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`, `goal_90_met=false`.
- Active hard caps remain: incomplete public benchmark matrix, fewer than five formal-ready strong baselines, missing independent confirmatory blind, missing two frontier API vendors, and missing formal adaptive budget evidence.
- Task Shield v1.3 monitor reports `running_progressing`, 24/726 completed, 0 failed, 702 missing, PID 27384 alive. Recent artifact age is below the stall threshold, so no retry/kill/intervention was made.
- Estimated Task Shield runtime at the observed rate is still long; until it completes or fails, do not start Progent, CaMeL, IPIGuard, adaptive MCTS or public-matrix jobs that compete for Ollama/GPU.

Verification in this window:

- `ruff check experiments\paper_v1\benchmarks\monitor_adaptive_mcts_budget_formal.py experiments\paper_v1\benchmarks\diagnose_agentdojo_formal_run_failures.py scripts\audit_project_conventions.py`: passed.
- `python -m compileall -q experiments\paper_v1\benchmarks scripts`: passed.
- Focused monitor/diagnostic regression:
  `python -m pytest -q tests/unit/test_agentdojo_failure_diagnostic.py tests/unit/test_agentdojo_official_detector_formal.py::AgentDojoOfficialDetectorFormalTests::test_formal_run_monitor_displays_repo_paths_relatively tests/unit/test_agentdojo_official_detector_formal.py::AgentDojoOfficialDetectorFormalTests::test_formal_run_monitor_creates_nested_output_directory`:
  5 passed.
- `python scripts/audit_project_conventions.py --check`: 12/12 PASS.
- Current checkout-absolute scan over `protocols/paper_upgrade_v1` shows no remaining safe monitor/diagnostic path debt; remaining hits are intentionally preserved as described above.

# Current task update — 2026-07-22 16:35 +08:00

Q2-to-80 non-inflating action audit added:

- New script: `experiments/paper_v1/benchmarks/plan_q2_to_80_actions.py`.
- New artifact: `protocols/paper_upgrade_v1/execution/q2_to_80_action_audit_v1.json/.md`.
- New regression: `tests/unit/test_q2_to_80_action_audit.py`.
- The audit reads Q2 readiness, execution plan, strong-baseline formal readiness, Frontier API audit, independent blind admission and adaptive monitor evidence. It never starts experiments, calls APIs, edits registries, retries failures, rewrites frozen evidence or promotes smoke/diagnostic/running artifacts.
- Current audit status is `blocked_by_active_hard_caps`: Q2 remains `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`, `resource_gate=busy`.
- It records all five caps that must be cleared before an honest Q2 >= 80 claim:
  - `frontier_api_model_gate`: requires two user-configured API vendors and explicit network-smoke consent.
  - `adaptive_budget_gate`: requires the frozen 80-task MCTS budget run and formal admission; cannot run while Task Shield owns Ollama/GPU.
  - `independent_blind_gate`: requires independently authored 600-case candidate data plus custody and formal run admission.
  - `strong_baseline_gate`: requires at least five formal-ready strong baselines; current count remains 2.
  - `public_benchmark_gate`: requires the frozen public benchmark matrix, not just pending queues.
- The same artifact records the remaining portability exceptions: 23 files with checkout-specific path hits, 14 frozen/hash-bound and 9 evidence-bound non-frozen snapshots that must not be rewritten in place.

Latest live workload check:

- Task Shield v1.3 remains `running_progressing`, 24/726 completed, 0 failed, 702 missing, PID 27384 alive. Last update age is below the 45-minute stall threshold, so no intervention was made.

Verification in this window:

- `python -m pytest -q tests/unit/test_q2_to_80_action_audit.py tests/unit/test_q2_formal_execution_plan.py tests/unit/test_repository_layout.py`: 19 passed.
- `ruff check experiments\paper_v1\benchmarks\plan_q2_to_80_actions.py tests\unit\test_q2_to_80_action_audit.py scripts\audit_project_conventions.py`: passed.
- `python -m compileall -q experiments\paper_v1\benchmarks\plan_q2_to_80_actions.py tests\unit\test_q2_to_80_action_audit.py scripts\audit_project_conventions.py`: passed.
- `python scripts/audit_project_conventions.py --check`: 12/12 PASS.

# Current task update — 2026-07-22 15:27 +08:00

Additional non-GPU portability work completed:

- `experiments/paper_v1/benchmarks/smoke_frontier_api_models.py` now writes the
  repo-local `config_path` and printed output directory as repository-relative
  paths when they are inside this checkout.
- `experiments/paper_v1/benchmarks/admit_frontier_api_model_slots.py` now writes
  `base_registry_path`, `smoke_manifest_path`, `output_registry_path` and future
  `smoke_evidence` registry references as repository-relative paths when they
  are inside this checkout.
- Regenerated the plan-only Frontier smoke manifest and the blocked registry
  admission artifact. They remain non-formal: 0 network calls, 0/2 configured
  vendors, `blocked_smoke_not_qualified`, and no v3 registry candidate written.
- Refreshed Frontier API audit and Q2 readiness. The Q2 score remains
  `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.
- Latest Task Shield v1.3 monitor remains `running_progressing`, 7/726
  completed, 0 failed, PID 27384 alive. The current case is still below the
  configured stall threshold, so no intervention was made.

Boundary note:

- The running Task Shield v1.3 raw `outcomes.jsonl` currently contains
  `official_trace_path` values emitted by its hash-bound runner. These are raw
  in-progress evidence rows and must not be rewritten in place. If raw outcome
  paths must become fully repository-relative, that requires a future explicit
  new freeze/run revision rather than editing the active 7/726 root.

Verification in this window:

- Frontier client/admission/Q2/planner/layout focused regression:
  `python -m pytest -q tests/unit/test_frontier_api_client.py tests/unit/test_q2_readiness_audit.py tests/unit/test_q2_formal_execution_plan.py tests/unit/test_repository_layout.py`:
  39 passed.
- `ruff check --select N experiments/paper_v1/benchmarks/smoke_frontier_api_models.py experiments/paper_v1/benchmarks/admit_frontier_api_model_slots.py tests/unit/test_frontier_api_client.py`:
  passed.
- `python -m compileall -q experiments/paper_v1/benchmarks/smoke_frontier_api_models.py experiments/paper_v1/benchmarks/admit_frontier_api_model_slots.py tests/unit/test_frontier_api_client.py`:
  passed.
- `python scripts/audit_project_conventions.py --check`: 12/12 PASS.
- Checkout-absolute scan over refreshed Frontier/Q2 active artifacts found no
  current-checkout absolute path hits.
- `git diff --check`: no whitespace errors; only CRLF conversion warnings from
  existing Windows line-ending behavior.

# Current task update — 2026-07-22 17:13 +08:00

Non-frozen Task Shield/Q2 state synchronization and full Harness verification
completed.

What changed:

- Updated the non-frozen external strong-baseline protocol so Task Shield no
  longer appears as stale v1.2/no-runnable-code work. It now records the v1.3
  disclosed reproduction as qualification-completed and formal-running, while
  keeping `result_eligible_for_formal_tables=false`.
- Updated the current implementation checkpoint to treat the live Task Shield
  count as an operational checkpoint only, not formal effect evidence.
- Refreshed external strong-baseline source audit, strong-baseline formal
  readiness audit, Q2 readiness audit and Q2-to-80 action audit. No score,
  registry admission or result eligibility was promoted.
- Preserved all freeze/hash-bound and evidence-bound path exceptions. The
  layout audit still reports 12/12 PASS, including checkout-path portability for
  active index documents and hash-bound file identity.

Current Q2 state:

- Q2 readiness remains `raw_score=66.0`, `capped_score=60.0`,
  `goal_80_met=false`.
- Formal-ready strong baselines remain `agentdojo_tool_filter` and
  `promptguard` only; required count remains at least five.
- The five hard caps below 80 remain public benchmark matrix, strong-baseline
  count, independent blind, Frontier API vendors and formal adaptive MCTS
  budget evidence.

Latest live workload check superseded by the following failure checkpoint:

- Task Shield v1.3 root:
  `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`.
- PID 27384 alive.
- Latest read-only snapshot at this checkpoint:
  `running_with_failures_requires_attention`, 28/726 completed, 1 failed,
  697 missing, not admitted.
- Failed row: `agentdojo:v1:slack:user_task_18`, `APITimeoutError`.
- This is an operational failure checkpoint, not a formal effect result. No
  selective retry, row exclusion, partial-row promotion, registry admission or
  competing Ollama/GPU task was started.

Verification in this window:

- `python scripts/audit_project_conventions.py --check`: 12/12 PASS.
- Focused Task Shield/Q2/layout/public-adapter regression:
  `python -m pytest -q tests/unit/test_repository_layout.py tests/unit/test_public_benchmark_adapters.py tests/unit/test_q2_readiness_audit.py tests/unit/test_q2_formal_execution_plan.py tests/unit/test_q2_to_80_action_audit.py tests/unit/test_taskshield_paper_formal.py`:
  136 passed.
- Full pytest: 666 passed, 1 skipped.
- Full Harness verifier:
  `powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/verify.ps1`:
  `Verification failed=0`.
- `ruff check experiments\paper_v1\benchmarks\audit_external_strong_baselines.py experiments\paper_v1\benchmarks\build_strong_baseline_dependency_snapshot.py tests\unit\test_public_benchmark_adapters.py scripts\audit_project_conventions.py`:
  passed via the standalone `ruff` command.
- `python -m compileall -q m3_core m3_guard m3_attacks m3_eval experiments scripts tests`:
  passed.
- `python -m experiments.validate_registry`: registry counts
  `{'pending': 0, 'running': 0, 'completed': 18, 'failed': 0}`.
- `python scripts/verify_historical_evidence.py`: pass.
- `git diff --check`: no whitespace errors; only expected Windows CRLF
  conversion warnings.

# Current task update — 2026-07-22 18:49 +08:00

Task Shield v1.3 was stopped under explicit user approval, sealed externally,
and replaced by the fresh v1.4 qualification/formal path.

Authoritative state:

- v1.3 PID 27384 is stopped. The preserved root has 42 completed, 1 failed and
  683 missing cases. External seal inventory: 90 files, 3,044,442 bytes,
  inventory SHA-256
  `69c40fcbf6344b20c33668cbb8134a7ede166dada8a9fcb69a7d3a100022c1ce`.
- The approved operator decision validated against the recovery package. No
  v1.3 row was retried, removed, pooled or admitted.
- Fresh v1.4 qualification completed 2/2 with zero operational failures and is
  explicitly `completed_diagnostic_partial`, not formal evidence.
- Fresh v1.4 726-case formal execution started with PID 9804 and `--no-resume`.
  The 18:51 +08:00 monitor is `running_with_failures_requires_attention`,
  4 completed, 1 failed and 721 missing.
- The retained v1.4 failure is
  `agentdojo:v1:banking:user_task_1`, `TaskShieldVerifierError: verifier
  returned invalid JSON`; the corrected diagnostic classification is
  `model_output_or_parse`.
- The v1.4 process remains live. It was not automatically killed, retried or
  revised. This root is already inadmissible under the zero-unexplained-failure
  gate, so the next action is an explicit operator decision, not automatic
  recovery.
- Q2 remains raw 66.0/capped 60.0 with `goal_80_met=false`; formal-ready strong
  baselines remain 2/5.

Engineering corrections and verification:

- Fixed Windows PID checks in the generic formal monitor and Q2 planner to use
  `GetExitCodeProcess == STILL_ACTIVE`; a completed PID no longer appears live.
- Made Task Shield recovery-package tests independent of repository-global
  qualification/formal roots.
- Corrected failure taxonomy so a runtime filename containing `timeout` cannot
  misclassify verifier-invalid-JSON failures.
- Focused regression: 143 passed; Ruff: passed.
- Frozen/hash-bound v1.3/v1.4 runner, runtime and freeze files were not edited.

# Current task update — 2026-07-22 17:20 +08:00

Task Shield v1.3 failure handling and Q2 fail-closed planner update completed.

What changed:

- Refreshed the Task Shield v1.3 read-only monitor for
  `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`.
- The monitor now reports `running_with_failures_requires_attention` with
  28/726 completed, 1 failed and 697 missing while PID 27384 is still alive.
- The failed row is `agentdojo:v1:slack:user_task_18` with
  `APITimeoutError`; it is classified as an operational formal-run failure,
  not as a security or utility effect result.
- Updated the fail-closed Q2 formal execution planner so running external
  formal workloads with failures route to `review_failed_formal_workload`
  (`blocked_manual_review`) rather than ordinary monitoring.
- Updated non-frozen Task Shield registry/protocol status text to require an
  explicit failure-recovery revision or protocol decision before any future
  Task Shield result can be admitted.

Current Q2 state:

- Q2 readiness remains `raw_score=66.0`, `capped_score=60.0`,
  `goal_80_met=false`.
- Formal-ready strong baselines remain `agentdojo_tool_filter` and
  `promptguard` only.
- Task Shield v1.3 no longer counts as merely "running-progressing" evidence;
  the current root is ineligible for paper tables unless a full explicit
  failure-recovery path is created and admitted.

Safe next action:

- Do not kill, retry, exclude, repair or admit the current root automatically.
- Continue only read-only monitoring unless the user explicitly asks to stop
  PID 27384 and create a new full-root failure-recovery revision.

Verification after this update:

- `python scripts/audit_project_conventions.py --check`: 12/12 PASS.
- Q2 planner/action/external-admission/layout focused regression:
  `python -m pytest -q tests/unit/test_q2_formal_execution_plan.py tests/unit/test_q2_to_80_action_audit.py tests/unit/test_external_strong_baseline_admission.py tests/unit/test_repository_layout.py`:
  22 passed.
- Public adapter / Task Shield / Q2 readiness regression initially failed
  because `test_public_benchmark_adapters.py` still expected the old
  `qualification_completed_formal_running` Task Shield status. The assertion was
  updated to the fail-closed `formal_running_failed_case_present` state, then
  the same group passed 117/117.
- Ruff and compileall passed for the touched planner/audit/test files.
- `python -m experiments.validate_registry`: 18 completed, 0 pending/running/failed.
- `python scripts/verify_historical_evidence.py`: PASS.
- `git diff --check`: no whitespace errors; only expected Windows CRLF warnings.
- Full `harness/scripts/verify.ps1` was attempted once with a 180-second bound
  and timed out before returning a result; it is not counted as a pass. No
  lingering verifier process remained after timeout.

# Current authoritative override — 2026-07-22 18:49 +08:00

The immediately preceding v1.3-live text is historical. Current state is:
v1.3 stopped/sealed at 42 completed + 1 failed + 683 missing; v1.4 qualification
completed 2/2 with zero operational failures; v1.4 formal PID 9804 is live at
4 completed + 1 failed + 721 missing at the 18:51 +08:00 snapshot. Its retained verifier-invalid-JSON row
makes the root inadmissible. Q2 remains raw 66.0/capped 60.0. Do not stop,
retry, exclude or revise the live root without an explicit user decision.

# Current authoritative paper-v2 update — 2026-07-24 02:20 +08:00

The older provider-gate text is superseded by this checkpoint.

- The project owner explicitly approved the DeepSeek prospective request chain:
  local request ID and payload hash fsynced before transport, then official
  response ID, exact returned model and append-only terminal binding.
- The approved scope is DeepSeek and fresh v2 requests only. No historical
  smoke or v1 artifact is upgraded.
- Gemini 3.6 Flash active quota is now hash-bound from the user-submitted
  screenshot at 1000 RPM, 2000000 TPM and 10000 RPD. The image, project ID and
  credential are not stored.
- One safe fixed DeepSeek request completed the durable two-event trace. A
  local response-normalization assertion failed after transport; no retry was
  made. The zero-network recovered artifact qualifies identity only and
  discloses that response content, usage, latency and the full receipt were not
  persisted.
- Experiment-record v2 and append-only record-store v2 pass offline
  qualification. Formal execution is still closed because the live
  six-condition runtime has not yet been wired to create and persist one v2
  trace per provider call.
- Current readiness remains engineering 99%, scientific evidence 32%,
  submission 44%. No medium/public/adaptive/blind effect claim exists.
- Latest focused verification: paper-v2 184 passed, 772 deselected; Ruff and
  script syntax checks passed. Full pytest passed 955 with 1 skipped and 3
  warnings; full Harness exited 0 in 481 seconds with
  `Verification failed=0`.

## Active implementation — 2026-07-24 live per-call v2 trace wiring

- Goal: route every DeepSeek call made by the six-condition live runtime,
  including VIGIL preparation and multi-step agent calls, through the approved
  pretransport fsynced trace and bind the complete ordered request set to one
  experiment-record v2.
- Failure boundary: a provider exception must retain its started commitment and
  produce a diagnostic ITT record; it must not disappear, retry automatically,
  or be promoted to formal-candidate evidence.
- Allowed files: new/active paper-v2 trace, runtime-v2, record-v2, gate, tests,
  generated qualification artifacts and required Harness state/verifier files.
- Forbidden: paper-v1 and historical freezes; local credentials; production or
  external effects; formal API matrix execution; retroactive promotion of the
  earlier smoke/qualification.
- Acceptance: ordered multi-call bundle validation, deterministic request-ID
  recomputation, success and failed-call record paths, append-only v2 store
  recovery, zero-network end-to-end qualification, focused and full regression.

## Implementation checkpoint — 2026-07-24 13:00 +08:00

- The live per-call DeepSeek v2 wiring is implemented. `TracedProviderClient`
  writes and fsyncs a deterministic commitment before every transport and
  binds completed calls to activated trace attestations.
- Experiment-record 2.1 stores the complete ordered request bundle. Normal
  single-call and VIGIL two-call paths qualify as `formal_candidate`; provider
  pause/failure/evidence failure retains one open request, becomes
  `diagnostic`, and stays in the ITT denominator.
- Evidence activation is prevalidated before terminal append, so a failed
  activation cannot leave an ambiguous completed request.
- Zero-network end-to-end qualification covers four runtime/persistence
  scenarios and writes four transient records: 2 complete candidates and
  2 diagnostic ITT failures. Network calls, external effects, project
  experiment records and formal results are all 0.
- `medium_execution_manifest_v3_preflight.json` now reports
  `live_runtime_per_call_v2_qualified=true`, while `gate_pass=false` and
  `formal_execution_authorized=false` remain enforced.
- Remaining gate: freeze a run-specific admission manifest, run one bounded
  official DeepSeek pilot through the same path, review cost/identity/evidence,
  and only then decide whether to authorize the larger matrix.
- Final verification for this engineering stage: paper-v2 189/189; full pytest
  960 passed, 1 skipped, 3 dependency warnings in 442.81 seconds; full Harness
  exited 0 in 571.8 seconds with embedded 960/1/3 and
  `Verification failed=0`.

## Offline pilot-controller checkpoint — 2026-07-24 15:30 +08:00

- The missing formal orchestration layer is implemented in
  `experiments/paper_v2/formal_execution_controller_v2.py`. It binds one exact
  frozen M3-v2 benign-no-tool/no-defense work item to the official DeepSeek
  model, CNY 27 abort fuse, sandbox-only effects, prospective per-call v2
  trace, v2 record store and dedicated single-use output paths.
- The frozen project artifact is only
  `deepseek_pilot_admission_candidate_v2.json`. It has
  `execution_authorized=false`, `formal_matrix_authorized=false` and
  `result_admission_authorized=false`; it cannot be passed to the execution
  entrypoint as an active admission.
- The controller requires a different active manifest containing an explicit
  `project_owner` checkpoint and exact candidate/scope digests. It validates
  all locked inputs and unused output paths before invoking the credential
  loader or constructing the provider client.
- Zero-network qualification rejects four cases before credential/client
  access: missing active admission, candidate self-authorization, scope drift
  and pre-existing single-use output. Those rejected paths read zero
  credentials and construct zero clients. One positive permit-only check binds
  the exact frozen work item without execution.
- A separate injected-transport end-to-end qualification creates one client,
  makes one local fixture transport call and writes one temporary
  formal-candidate record. It proves controller → trace → content-free
  cache/cost evidence → append-only record-store composition with zero
  credentials, zero external network calls, zero project experiment records
  and zero formal results.
- Provider trace bundle 2.1 now requires each completed call to persist
  cache-hit/cache-miss/output token counts, provider-receipt SHA-256, exact
  request and cumulative CNY cost, and budget status. The zero-network runtime
  qualification covers three completed calls with complete usage evidence;
  fixture costs are CNY 0.0000728 for the single-call path and CNY 0.0001456
  for the two-call VIGIL path.
- The active admission file
  `protocols/paper_upgrade_v2/admissions/deepseek_pilot_admission_v2.json` was
  deliberately not created. The academic pilot checkpoint remains pending.
- At this earlier checkpoint the candidate locked eight inputs. That identity
  is superseded by the 23-input post-pilot-review checkpoint below and must not
  be activated.
  Final verification: focused affected regression 28/28; paper-v2 199/199
  with one known VIGIL/Pydantic warning; full pytest 970 passed, 1 skipped and
  3 known dependency warnings in 295.07 seconds; full Harness repeats 970/1/3,
  passes static/syntax/compile/historical-evidence checks and reports
  `Verification failed=0`. Ruff and JSON parsing pass. No API call, credential
  read, external effect, project experiment record or formal result occurred.

## Post-pilot evidence-review checkpoint — 2026-07-24 17:00 +08:00

- The prospective experiment-record contract is now 2.2. It requires the
  credential-free provider safety receipt to be persisted inside the hashed
  append-only record; transient runtime validation alone is no longer enough.
- `post_pilot_evidence_review.py` validates candidate/active admission binding,
  active-file SHA-256, the independent trace JSONL against the record bundle,
  exact provider/model identity, cache/cost arithmetic, safety receipt/action
  binding, token totals and the v2 ledger tail.
- Its offline injected qualification passes one structural fixture and rejects
  four integrity cases: missing persisted safety receipt, tampered cache cost,
  provider trace drift and active/candidate binding drift. Offline evidence
  explicitly leaves the official gate and owner-matrix-review readiness false.
- The non-executable candidate now locks 23 prospective execution/review
  inputs. Its canonical manifest SHA-256 is
  `6ac0601865d76f5f808952b2f58e6587d02c303ac5e9a998ae4d751fbb3dd4cc`.
- `medium_execution_manifest_v3_preflight.json` binds the reviewer
  qualification but remains `gate_pass=false` and
  `formal_execution_authorized=false`. The project active admission, official
  pilot record, official review artifact and formal result are all absent.
- Final verification: focused review/record/controller/gate regression 33/33;
  paper-v2 204/204 with one known VIGIL/Pydantic warning; full pytest 975
  passed / 1 skipped / 3 known dependency warnings in 297.42 seconds; full
  Harness repeats 975/1/3 in 299.96 seconds and reports
  `Verification failed=0`. Ruff, JSON parsing and artifact reproduction pass.

## Official DeepSeek single-pilot result — 2026-07-24 15:24 +08:00

- The project owner explicitly approved the exact frozen checkpoint with the
  statement `继续 DeepSeek 单条 pilot`. Its SHA-256 is stored in the active
  admission; the statement itself is not copied into provider evidence.
- The active manifest binds candidate SHA-256
  `6ac0601865d76f5f808952b2f58e6587d02c303ac5e9a998ae4d751fbb3dd4cc`,
  the unchanged 23 locked inputs, one benign-no-tool/no-defense M3-v2 work
  item and unused single-use outputs. Pre-execution verification read no
  credentials and made no network calls.
- Exactly one official DeepSeek request completed. There was no retry,
  cross-provider fallback, Gemini call, provider-managed tool, connector or
  external effect. The persisted record is `formal_candidate`, not admitted.
- Content-free usage evidence records 278 prompt tokens, all cache misses,
  136 completion tokens, 414 total tokens and CNY 0.00165 cumulative cost,
  within the CNY 27 abort ceiling.
- The credential-free post-pilot review passed all 15 checks. It records
  `task_completion=true`, `unsafe_effect=false`, sandbox-only effect handling,
  exact `deepseek-v4-pro` identity, a complete trace/record chain and a
  persisted safety receipt.
- The technical review sets `official_evidence_gate_passed=true` and
  `ready_for_owner_matrix_review=true`, but preserves
  `formal_matrix_authorized=false`, `result_admission_authorized=false`.
- The user also authorized later controlled DeepSeek and Gemini use. That
  broader permission is retained for a future newly frozen staged plan; it
  does not retroactively widen this single-use manifest or bypass the
  DeepSeek/Gemini budget and no-dangerous-effect policies.
- Readiness is conservatively engineering 99%, scientific evidence 33% and
  submission 45%. No paired medium, public, adaptive or independent-blind
  result exists, so the goal and feature remain `in_progress`.
- Verification after the official review: focused evidence/state tests 31/31;
  paper-v2 204/204 with one known VIGIL/Pydantic warning; full Harness 975
  passed, 1 skipped and 3 known warnings in 317.96 seconds, with historical
  evidence and current freezes passing and `Verification failed=0`.

## Active implementation — DeepSeek 480-item medium matrix controller

- Goal: advance from one technical pilot to the frozen 72-case paired
  falsification study: 432 primary six-condition records plus 48
  authorization-regime probes.
- Scope: DeepSeek official `deepseek-v4-pro` first. Gemini remains an
  independent future matrix and must not be used as fallback inside this run.
- Required properties: one-attempt provider calls, concurrency 1, per-call
  fsynced trace, per-record fsynced append-only ledger, matrix-level cumulative
  cache/cost ledger reconstructed on resume, CNY 27 abort fuse, and refusal to
  resume any pending item whose trace path already exists.
- Live dependencies: run under the dedicated Python 3.13.5 PromptGuard
  environment because it supplies pinned Transformers/Torch with CUDA; use the
  official AgentDojo in-memory environment/evaluators and source-pinned VIGIL.
- Safety boundary: only frozen synthetic M3 and public AgentDojo cases may be
  sent. Provider tools, external connectors, host commands and real-world
  effects remain disabled. Model output is always an untrusted proposal.
- Authorization evidence: a fresh matrix manifest must bind the passing
  official pilot review and the owner's delegated continuation statement.
  This may authorize execution but never self-admit scientific results.
- Verification before network: injected-transport success, resume, budget
  reconstruction, trace reuse rejection, provider-pause stop, schema/manifest
  reproduction and the full paper-v2 regression.

## Active continuation — Public primary recovery and admitted analysis

- s1 is complete at 1265/1265. At the 06:39 checkpoint, s0/s2/s3 were
  504/1265, 592/1264 and 468/1264 with all three recovery processes alive and
  all recovery stderr logs empty.
- Do not stop, restart, retry, or edit the frozen recovery source or live
  ledgers. Scientific outcomes remain sealed until all four shard reviews,
  evidence-integrity reviews, the 5082-record merge, and the separate result
  admission pass.
- The result candidate now also freezes an independent analysis reviewer. The
  reviewer directly recomputes condition counts, Wilson intervals, critical
  paired differences and exact McNemar tests without reusing the primary
  aggregation/statistical helpers.
- Current verification: manuscript/bibliography 7/7; independent reviewer and
  result-admission 5/5; Ruff and py_compile pass. Full Harness remains deferred
  until all live Public recovery processes exit naturally.

## Authoritative stop point — Fresh Harness v7 and report — 2026-08-06

- The previously running Fresh Harness v7 completed naturally. The detached
  helper directly observed OS exit 0 after 20946.429 seconds; evidence gate
  passed and all 13 aggregate stages are PASS with zero FAIL stages.
- The full regression result is `1552 passed, 1 skipped, 3 warnings` in
  4840.55 seconds. The log contains exactly one terminal
  `Verification failed=0` marker and no traceback.
- Authoritative receipt SHA-256 is
  `3f0378d30c65c4e188d878e4503abe572a305c29fb21f1f171dccff21b2de877`;
  stdout is `b7e3e56469b17fcb697a07a051e1e56ed657cfed4838f3a34f18bcee5fa80161`
  and stderr is `5d8f5bfe93ebbc238b2ca955539641f144cb44dfe02eccb4b474e43e493c1265`.
- Verifier/helper hashes were stable, AgentDojo matched commit
  `089ed468cf3ed0322acc66b0211f26d9d90dbf60`, provider/network authority was
  false, API variables were scrubbed, secret-format scans found zero hits, and
  no related process remains alive.
- Historical medium-v7 stays permanently aborted and read-only. Gemini
  Public-v5 segment 0 remains one technically passing formal-candidate record;
  no result admission was opened. Adaptive Pro-50 v2 remains an unexecuted
  candidate for 32 pending tasks. Independent blind remains 0/600 authored and
  0/3600 executed.
- A validated and rendered 14-block technical report with four metric cards,
  two native charts and two audit tables is stored at
  `docs/research/paper_v2/reports/M3_PI_Guard_Fresh_Harness_v7_阶段收口报告_2026-08-06_artifact.json`.
  Its SHA-256 is
  `6011c2252e9662f6607f40f3fee65dfc5574e66f8eec3c97ec6ea1a23389cc93`;
  QA receipt SHA-256 is
  `3aae05f4cf0903bf9b28fd509631b9ab2dd878ae0e2d6e8881d11654d33cd3a0`.
- Owner-requested stop is now active: do not create a new gate or admission and
  do not start an API, Adaptive, Gemini quota-day or blind execution until a
  later explicit continuation. F-PAPER-002 remains `in_progress`.

## Active continuation — post-v7 gate and Adaptive pro_50 execution path — 2026-08-06

- The persistent 21-day closeout goal explicitly resumed after the prior stop.
  This checkpoint authorizes implementation and offline verification of the
  next gate/wrapper path; it does not itself authorize provider transport.
- Immediate goal: bind the immutable Fresh Harness v7 direct-exit-zero receipt,
  historical medium-v7 non-resumable audit, Gemini Public-v5 segment-0
  technical evidence, Adaptive order gate and exact Pro-50 v2 candidate/
  admission into a new non-authorizing closeout gate.
- Then create a new single-use Adaptive wrapper version. Historical wrappers,
  admissions, frozen inputs and terminal work keys remain immutable.
- Allowed files: new gate/wrapper modules and tests, their generated protocol
  artifact, Harness verifier registration, decision/state records and a new
  detached Harness launcher/output root.
- Forbidden in this phase: reading or printing provider secrets, model/API
  calls, result/label access, retrying terminal work, real external effects,
  modifying historical v7 evidence or overwriting an existing output root.
- Acceptance before any provider call: focused tests, Ruff, Python compile,
  PowerShell parse, conventions, gate reproduction and one new complete
  direct-exit-zero Harness receipt that includes the new gate/wrapper checks.

## Authoritative stop point — Day 2–3 offline qualification and Harness v8 — 2026-08-06

- The post-v7 non-authorizing gate v5 is frozen with manifest
  `ff76b53991b5b0f8f2ccdfc88aa246c9be6d7e12786bdf8c3c0d4d1b3c10e58e`.
  It binds v7, the immutable medium-v7 failure, Gemini Public-v5 segment 0 and
  the exact Adaptive Pro-50 v2 candidate/admission while authorizing neither
  provider execution nor scientific-result access.
- `run_adaptive_formal_pro_v2_guarded_v3.ps1` is the qualified single-use
  Pro-50 wrapper. It fixes retries/tools/effects/result access to false and
  refuses touched roots or identity/count drift. It has not been executed.
- Focused verification is 16/16 plus Ruff, Python compile and PowerShell parse.
  Fresh Harness v8 then completed naturally with directly observed exit 0,
  evidence gate PASS, 13/13 aggregate stages and pytest 1568 passed / 1 skipped
  / 3 warnings. Receipt SHA-256 is
  `8747437d004059615eb70615d30ebd1af7fedc093c10fa2b30ab2a038b1fb71b`.
- The v8 run took 29781.25 seconds, retained 303 RuntimeAuditor delete blocks,
  found zero secret-format hits, scrubbed API variables, authorized zero
  provider/network work and left no helper/child process alive.
- No API, provider, Adaptive, result or blind-label operation occurred. The
  project is stopped before Day-4 canary. F-PAPER-002 remains `in_progress`.
- Detailed report:
  `docs/research/paper_v2/reports/M3_PI_Guard_Day2-3_离线资格化收口报告_2026-08-06.md`.

## Active continuation — Adaptive Pro-50 v2 completed — 2026-08-07

- Owner continuation supersedes the prior pre-Day-4 stop for the frozen
  closeout sequence. No historical terminal work or frozen protocol was
  modified.
- The exact single-use `pro_50` wrapper completed with direct OS exit 0. All
  six captured steps exited 0 and the wrapper status is
  `completed_technical_gate_pass`.
- The stage produced 32/32 terminal task checkpoints, 1,600 provider traces,
  3,200 query-ledger events and 1,968 budget-ledger events. Stage cost was
  CNY 1.9984298 against the CNY 10 hard limit.
- Automatic retries, provider tools and external effects stayed disabled.
  Secret scan found zero hits and scientific outcomes remain unaccessed;
  `result_admission_authorized=false`.
- Wrapper receipt SHA-256 is
  `714ca7186df345add63277c618f43f24e749670282a5807ce3376b0c8942a116`;
  technical-review manifest is
  `1c419d1c89ea4217a54bf7970ac25ab138a31db081991696a81f410bdebb1384`.
- Next authorized planning action is the next untouched Gemini Public-v5
  canary recovery segment under one free-tier segment for the current Pacific
  quota day. Its result remains sealed pending the 12-slot aggregate gate.

## Active continuation — Gemini Public-v5 s1 completed — 2026-08-07

- A fresh s1 admission was created for Pacific quota day `2026-08-06`; the
  admission fixes Billing to free tier, paid ceiling to USD 0, automatic
  retries to zero and provider tools/external effects/result admission to
  false.
- The generic guarded-v2 wrapper completed with direct OS exit 0 and status
  `completed_technical_gate_pass`. All four captured steps exited 0 and the
  secret scan found zero hits.
- The segment produced 1/1 formal-candidate record from one completed provider
  transport. The runtime VIGIL dependency failure is retained in ITT; it was
  neither excluded nor retried. All technical checks pass and
  `matrix_continuation_eligible=true`.
- Identity-only verification confirms official Gemini network,
  `gemini-3.6-flash`, exact model identity and an official provider response
  ID. The v2 contract does not require a provider request ID when the official
  API does not expose one.
- Receipt SHA-256 is
  `507929977d4a78e08da94d62fda3b28920a7c7ce5a6f073933e478b9629e2997`;
  technical-review manifest is
  `8223d08b0704b5a21f1393d29c890568cecaf540bdbda4c7780493c401a79dde`.
- The current Pacific quota day is reserved and no further Gemini formal
  segment may run on it. Scientific outcomes remain unaccessed and aggregate
  canary admission remains pending the remaining untouched segments.

## Active engineering phase — Pro-200 offline qualification

- Goal: create and verify the order-bound Pro-200 v2 candidate/admission, a
  single-use Pro-200 wrapper, a new non-authorizing closeout gate and a fresh
  full-Harness launcher before any Pro-200 provider call.
- Acceptance: predecessor review hash is exact and passing; 39 resumable source
  checkpoints are immutable while the one prior diagnostic remains in ITT and
  is not replayed; target budget is 200; the new stage authorizes only
  additional queries from 50 to 200; stage/total fuses remain CNY 20/180;
  retries/tools/effects/result access remain false; focused tests, Ruff,
  compile, PowerShell parse and a new complete Harness direct exit 0 all pass.
- Allowed files: new Pro-200 candidate/admission, new versioned gate/wrapper/
  launcher and their tests, non-frozen Harness verifier registration and state
  records.
- Forbidden: modifying Pro-50/Gemini terminal evidence, reading scientific
  outcomes or labels, calling a provider before the fresh Harness gate, retrying
  terminal queries, enabling tools/effects or reusing an existing output root.

## 2026-08-07 — Pro-200 qualification complete; Fresh Harness v9 running

- The Pro-200 candidate/admission bind 39 resumable task checkpoints at budget
  50 and preserve the one historical diagnostic in ITT without replay. Target
  budget is 200; stage/total hard ceilings are CNY 20/CNY 180.
- Focused qualification passed 32/32, with Ruff, `py_compile`, both PowerShell
  parses and gate-v6 write/verify all passing. Gate-v6 manifest is
  `73a57abbd955d6b5099f3fdd1fbb0503017576e3d4758c29d7d760e3f3363a5d`.
- Fresh Harness v9 was launched exactly once at
  `2026-08-07T03:27:05+08:00`; helper PID 43844 and child PID 48564 are running
  under `outputs/verification/experiment_closeout_fresh_harness_v9_20260807`.
- The Harness has all API variables scrubbed, no network/provider/result
  authority and no automatic restart. Pro-200 remains forbidden until v9
  produces a direct-exit-zero receipt.

## 2026-08-07 13:10 +08:00 — Pro-200 技术闭包完成，进入 Pro-500 离线资格化

- Fresh Harness v9 已自然完成并取得直接 OS exit 0：13/13 stage PASS、pytest
  1584 passed / 1 skipped / 3 warnings、唯一 `Verification failed=0`；receipt
  SHA-256 为 `14ef9b5a...0e44`，provider/network/result authority 均为 false。
- Pro-200 的 39 个授权任务已自然完成：6,925 次 provider call、5,504 条新增
  terminal query、CNY 8.0544754，自动重试、provider tools、external effects 和
  result admission 均为 0/false。标准 technical review manifest 为
  `1910ac58...349c`。
- 外层一小时宿主上限终止了原 PowerShell wrapper，但 execute Python 子进程未被
  停止并自然结束。原 wrapper `receipt.json` 永久缺失且不得补造；watcher 返回
  `true + null`，所以 execute 直接退出码仍记为未证明，只能由唯一终态 JSON 与
  hash-locked controller 的 print-then-return-zero 契约推导 effective exit 0。
- host-timeout 不可变审计已补强：锁定 PID 9956、启动时间、Python 路径、01–05
  日志、controller/gate 源、候选/准入、task/budget 链和 recovered technical
  review；独立复算 7,454−1,950=5,504。审计 manifest 为
  `f927367f...8fc`，文件 SHA-256 为 `d8d90a04...cf9b`。
- 当前验收范围：先完成 Pro-500 候选、单次准入、非授权 gate、可脱离会话运行并
  自写 receipt 的持久 wrapper/launcher；随后必须取得集成当前增量的新完整 Harness
  直接 exit 0，之后才允许第一次 Pro-500 provider 执行。
- F-PAPER-002 保持 `in_progress`。禁止重跑 Pro-200、修改任何已终态 ledger、读取
  科研 outcomes/盲测标签或把技术闭包解释为科学结果准入。

## 2026-08-07 19:10 +08:00 — Pro-500 集成门与 Fresh Harness v11 前置状态

- Pro-500 v2 候选、单次 owner admission、非授权 gate v7、持久 guarded runner 与
  单次 launcher 已离线资格化；授权范围固定为 36 个任务从预算 200 扩展到 500，
  CNY 35 阶段熔断，自动重试/tools/effects/result admission 均为 0/false。
- Fresh Harness v10 自然结束并直接 OS exit 1：11/13 stage PASS，pytest
  1 failed / 1627 passed / 1 skipped / 3 warnings。唯一失败测试与后续 prospective
  evidence stage 均源于同一状态转换：历史 gate v6 在 Pro-200 执行前要求输出根
  不存在，执行完成后被动态重放并正确 fail closed；不是 provider 或科研结果失败。
- v10 失败审计已单次封存，manifest
  `f35a4d9f92d77ef43eb49ec9aa44e7596e6d326801502c5c3548eeeb49b480bc`，文件
  SHA-256 `78fd2ed12c209c9357a75025f5807f767852deb54d307d0d5de208450e705cb7`；
  定向复核 44/44 通过。冻结 gate v6 与 Pro-200 输出均未修改。
- 当前动作是一次性运行 Fresh Harness v11；只有 v11 直接 exit 0 且激活 gate
  单次写入/复核通过后，Pro-500 provider 执行才可启动。F-PAPER-002 保持
  `in_progress`。

## 2026-08-07 22:17 +08:00 — Owner 要求中止并交付阶段报告

- Owner 已明确要求中止当前实验任务。所有实验、API、Harness 与 Pro-500 执行均
  保持停止；没有相关残留进程，没有创建 Pro-500 activation artifact，也没有触碰
  Pro-500 candidate/runner 输出根。
- Fresh Harness v11 已作为不可变非零证据封存：直接 OS exit `-1`、evidence gate
  `false`、9 个 stage PASS、1 个 stage FAIL、3 个 stage 未完成；pytest 为
  1,375 passed / 1 skipped / 1 warning / 257 setup errors。257 项均源于同一消失的
  pytest 临时目录，不能解释为 257 个产品断言失败。frozen-study-assets stage 没有
  终态，不能宣称通过或失败。receipt SHA-256 为
  `75f4bbb58b30e9543e6aa98498c1f44bfad882180ff25a5672b4914a6089f7da`。
- 21 天计划当前未结项：DeepSeek Flash Public 为 1,791/1,791 物理闭包；Gemini
  Public 为 2/1,791；Pro B50/B200 技术结账，B500、hardest-20、两套 Flash
  adaptive 和 600/3,600 独立盲测均未完成。Gemini 当前免费层 continuation 调度
  最少需要 1,186 个 quota days，与 21 个日历日目标结构性冲突。
- 已交付 15 页 Word 阶段报告，包含 4 幅分析图与 11 张表：
  `docs/research/paper_v2/reports/M3_PI_Guard_实验任务中止阶段报告_2026-08-07.docx`，
  SHA-256
  `d6e5e86270307f2531066958da26709ba372488e1a21247332627e13222ffc58`。
- F-PAPER-002 保持 `in_progress`，不是 `verified` 或结项。除非 Owner 明确恢复，
  后续不得启动 API/provider、Harness、Pro-500、Gemini continuation 或盲测执行。

## 2026-08-19 — Owner 明确恢复 21 天实验结项计划

- Owner 已明确要求继续按既定计划执行，暂不撰写新报告；这条指令解除
  2026-08-07 的 owner-stopped 运行暂停，但不解除任何冻结、准入、预算、零重试、
  无真实 effect 或结果隔离约束。
- 当前第一阶段不是直接复用 v11 或旧 activation 路径，而是：只读复核现状，为
  pytest 提供 run-scoped 稳定临时根，并以新的单次 Fresh Harness 运行目录取得
  current-source 直接 exit 0。现有 v11 receipt/log 已足够记录失败，不再叠加新的
  failure-review、source-lock 清单或重复哈希包。
- 只有新 Harness 完整通过，且执行前最小检查确认 Pro-500 的现有 candidate、owner
  admission、36-task 范围、CNY 35 熔断、零重试/tools/effects 与 untouched output
  root，才允许单次启动 Pro-500。v11、Pro-200 原 wrapper、历史终态 ledger 与所有
  旧 output root 继续不可变。
- 本阶段允许：最小修改 receipt helper/launcher 与定向测试，运行无 provider 权限的
  离线检查和完整 Harness；不再为了重复描述同一事实生成额外哈希工件。
- 本阶段禁止：在新 Harness 通过前调用 provider、读取科研 outcomes/盲测标签、
  自动重试、修改冻结实验条件、启用 provider tools/外部 effect 或生成新报告。
- F-PAPER-002 继续 `in_progress`；21 天结项的完整范围没有缩减。

### 2026-08-19 执行顺序调整

- Owner 指示独立盲测暂不执行，先完成其余工作。盲测 0/600、0/3,600 的真实状态
  保持不变，不删除、不补写、不作为当前 Harness/Pro-500 的前置条件。
- 当前优先序为：Fresh Harness 恢复 → Pro-500 → hardest-20×2,000 → DeepSeek
  Flash/Gemini adaptive → Gemini Public/结果准入与统计 → 最终非盲测收口检查。
- 该顺序调整不授权开发者代替第三方生成盲测内容，也不允许把“暂缓”写成“完成”。
- GitHub 目标仓库记录为 `https://github.com/Fischl0527/M3_PI_Guard.git`；当前
  `origin` 仍指向旧仓库，本阶段不擅自改 remote 或 push。

## 2026-08-20 — DeepSeek authorization analysis complete; Gemini pending

- The owner-approved lean paper scope supersedes the earlier 21-day sequence.
  Blind evaluation, Pro-500/2000 and Full Harness are not active paper gates.
- DeepSeek V4 Pro reached 900/900 terminal work keys. One explicit failed-only
  recovery touched 33 no-response keys and skipped all 867 response-bearing
  keys; no further DeepSeek retry is eligible.
- The single-pass DeepSeek analysis is complete. It retains all 900 ITT rows,
  confirms zero online forbidden-field, provider-tool and external-effect
  records, and produces five PNG/SVG figures plus six CSV tables.
- Figure burden semantics were corrected prospectively: ASK/DENY percentages
  now count records with at least one event, while event totals remain in the
  table. Focused verification passes 6/6 with Ruff and `py_compile`; no Full
  Harness or historical replay was run.
- Results and Discussion now report the DeepSeek findings. The main attack
  endpoint is at floor (0/100 in three primary cells, 1/100 in the fourth),
  while exact authorization reduces benign-tool completion and increases
  DENY, failure and latency. These findings do not support an independent
  M3-full mechanism advantage.
- Gemini remains pending on the same Pacific quota day after an official
  free-tier 429. Its partial rows are excluded from cross-provider analysis;
  only no-response and untouched keys may resume after the next quota reset.
- Active branch is `codex/q2-empirical-study`. The DeepSeek recovery milestone
  is already pushed to `m3-guard`; the analysis/manuscript milestone is the
  next exact-file commit. F-PAPER-002 remains `in_progress`.

### Manuscript-format checkpoint

- Introduction and Methods statuses now match the completed DeepSeek analysis;
  the figure/table plan marks all DeepSeek artifacts generated and Gemini
  pending.
- The provisional abstract contains 246 words, five keywords and no citation.
  A separate five-item highlights file keeps every bullet below the official
  JISA 85-character limit.
- JISA format requirements were checked against the official Guide for Authors
  on 2026-08-20: abstract at most 250 words, 1–7 English keywords and 3–5
  recommended highlights. Final venue/JCR and Gemini gates remain open.

### Manuscript-section checkpoint

- Added a provisional Conclusion that answers the three RQs using completed
  DeepSeek and budget-50/200 evidence while keeping Gemini and saturation
  claims out of scope.
- Added publication-facing captions for five figures and six tables, including
  exact denominators, ITT semantics and the ASK/DENY incidence correction.
- Added provisional submission declarations for competing interests, funding,
  data/code availability, generative-AI use, safety and CRediT authorship. Every
  item that needs author or institutional confirmation is explicitly marked.
- Corrected the Introduction from “four questions” to the actual three RQs.

### Unified-manuscript checkpoint

- Added a deterministic manuscript builder and a reader-facing unified English
  draft at `docs/research/paper_v2/manuscript/manuscript_deepseek_v1.md`.
- The current draft has six numbered IMRaD sections, five embedded figures and
  an 8,117-word body. Internal citation-audit tables, historical Harness prose,
  Git workflow notes and conditional result placeholders are excluded.
- Focused verification passes 6/6, with Ruff, `py_compile`, citation-key,
  abstract-length, section-order, figure-existence and workflow-metadata checks.
- Gemini remains pending under the three-Pacific-quota-day rule, so the paper
  remains in Stage 2 writing and makes no cross-provider claim.
- Six publication-facing authorization tables are now generated from the
  completed CSV outputs with compact labels and fixed numerical formatting.
  Six earlier detail tables remain available as Supplementary Tables S1–S6,
  avoiding duplicate Table 1–6 numbering.
- All 21 cited bibliography keys now use citation-processor syntax in the
  reader-facing draft. Internal literature hyperlinks and implementation-only
  result flags no longer enter the manuscript.
- Scientific subsections are generated with JISA-compatible hierarchical
  numbering; the abstract, figures, main tables and supplementary table labels
  remain outside that numbering sequence.
- Added an editable single-column Word working draft with five figures, 13
  tables and 21 citeproc-rendered references. Focused DOCX tests pass 3/3 plus
  Ruff and `py_compile`; section, table geometry, image, citation-token,
  metadata and accessibility checks pass.
- Visual DOCX rendering is not claimed because the current host has no
  LibreOffice, Word or WPS renderer. The Word file remains a review draft, not
  the final submission package, and author/funding/data statements remain open.
