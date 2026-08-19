# Task Record: M3-PAPER-002

## Goal

将现有 M3-PI Guard 结果收敛为面向 SCI JCR Q2 网络安全期刊的精简实证论文。
论文研究授权制度、M3-full 相对 policy-only 的模块贡献和安全—效用权衡，首选
期刊为 Journal of Information Security and Applications（JISA）。机制领先、
first/only/SOTA 和领域级 oracle authorization 主张不在范围内。

## 2026-08-19 Lean Empirical Study Scope

### Required

- 一次性分析现有 5082 条 DeepSeek Pro Public、1791 条 DeepSeek Flash Public、
  480 条 medium 和 Adaptive Pro budget 50/200 结果。
- 固定 180 条 DeepSeek 主样本、90 条 Gemini 子样本和 60 条授权不确定性子集。
- 新增 900 条 DeepSeek Pro 授权制度执行和 450 条 Gemini 精简跨厂商执行。
- 只运行受修改模块的定向测试、正式前缀 canary 和一次性结果完整性检查。

### Removed

- Full Harness 与历史 v1-v12 递归验证；
- Gemini 1791 完整矩阵；
- Pro-500、hardest-20×2000 和两套完整 second-model adaptive；
- 600 条独立盲测及 3600 条执行；
- 新的 failure-review、source-lock、分层 admission 和结项哈希包。

### Failure Rule

无官方响应的工程/传输失败修复后只重跑失败行。已有响应的 timeout、refusal、
parse failure 保留在 ITT；任何敏感性重试都追加记录且不覆盖原始终态。成功且未受
修复影响的行永不重跑。

## 2026-08-06 Gemini Public-v5 recovery segment 0 阶段结果

- fresh Harness gate v4 绑定 v6 直接 exit-zero 证据与当前 closeout 前置工件，
  manifest `d79faf97...e1e9a`，且不授权 provider 或结果访问。
- 新 single-use wrapper 绑定 controller-v5/recovery-candidate-v5 和当日 exact
  admission。LA quota day `2026-08-05` 的 segment 0 单次完成 1/1 记录和 1 次
  provider transport，free USD 0、retry/tools/effects=0/false/false。
- technical review 全检查 PASS，manifest `86e48d12...560c2`；wrapper exit 0，
  receipt SHA `a881799f...b3de`。科研 outcome/result admission 仍为 false。
- 定向测试 20/20、Ruff/compile、PowerShell parse、conventions 12/12 通过；新增
  源之后未运行完整 Harness。按 owner 指示停止，不自动进入下一 segment。
- 报告 SHA-256 `76137e6b...eb05`；总任务保持 `in_progress`。

## 2026-08-04 Fresh Harness v5 工作范围

### Goal

在不重跑任何 provider 实验的前提下，为当前 `verify.ps1` 生成一个全新、单次、
持久化终态的完整 Harness 运行，取得可直接审计的 OS exit 和日志哈希。

### Allowed

- 新增 versioned receipt helper、detached launcher 和静态/负例测试；
- 在 `outputs/verification` 下创建唯一 v5 运行根；
- 清除当前子进程的前沿 provider 环境变量后执行本地 Harness。

### Forbidden

- 修改历史 v4 receipt/stdout/stderr、旧失败运行、冻结实验或 provider ledger；
- 读取或输出环境变量值；
- 创建 Gemini/DeepSeek admission、调用 API、启用 Billing 或真实 effect。

### Acceptance

- launcher/helper PowerShell parse 通过且单次运行；
- running receipt 包含 child PID 和启动时 verifier hash；
- terminal receipt 包含直接观测的 child exit、前后 verifier hash、stdout/stderr
  hash/bytes，并对 source drift fail closed；
- 完整 Harness receipt 为 exit 0，stdout 唯一末尾标记为
  `Verification failed=0`，且没有聚合 FAIL。

## 2026-08-04 Gemini v2/v5 离线收尾结果

- 实现并验证 Gemini local-precommit contract v2.1：缺 provider request ID
  时保留空值，只在官方 response ID、精确模型/payload、完整 fsync bundle、
  free/USD0 和零重试/工具/effect 全部成立时提升为 formal candidate。
- Public-v5 保留历史 1 个 terminal 和 1 个 abort ITT 槽位，仅划分其余 10 个
  untouched canary；7 个候选日段均不超过 18 请求，候选不授权执行。
- 验证：runtime 20/20、v5 candidate/admission 3/3、注入式 E2E 1/1、合同及
  candidate 独立重放 exit 0、Ruff/compile、conventions 12/12。
- 完整 Harness 外层 3604 秒 exit 124，计算中的子进程又运行 441.6 秒后自然
  结束，但终态输出/exit code 不可恢复。因此 acceptance 中的 full-Harness
  条件未满足，任务保持 `in_progress`，不得创建 provider admission。
- 本轮零 API/provider/network 调用；相关后台进程最终为 0；已按 owner 指示停止。

## 2026-08-04 Gemini 前瞻证据合同 v2 工作范围

### Goal

为未来 Gemini 正式请求显式实现“调用前本地 request ID + canonical payload hash +
官方 response ID + 精确模型身份 + append-only/fsync 日志”的 formal-candidate
合同，修复 runtime v1 对该已批准链路的拒绝，但不追溯提升历史响应。

### Allowed

- 新增 `gemini_trace_attaching_runtime_v2.py`、Gemini 记录/资格化/控制器新版本；
- 新增对应 unit/integration/negative tests 与非执行型 manifest；
- 将新 verifier 集成到 `harness/scripts/verify.ps1`；
- 创建全新 Harness 输出根和后续全新 Gemini 身份。

### Forbidden

- 修改 v1 runtime、历史 segment 0/1、旧 trace/record/attempt/call ledger；
- 伪造 provider request ID 或把本地 ID写入 provider ID 字段；
- 读取或输出密钥、启用 paid Billing、自动重试、provider tools 或真实 effect；
- 在 fresh full Harness 直接 exit 0 前创建 provider execution admission。

### Acceptance

- 正例只允许官方 Google、精确模型、缺 provider request ID、存在官方 response ID、
  pretransport commitment 和完整闭合 bundle；
- request/response/payload/model/trace-mode/identity/免费层任一漂移均拒绝；
- v1 segment 1 继续 result-ineligible 且不可重试；
- focused tests、Ruff、compile、conventions 和新 full Harness 通过。

### Risk

主要风险是把“本地请求身份”错误表述为“provider request ID”，或让通用 diagnostic
绕过正式门。v2 必须保留 `provider_request_id=None`，单独记录 client request ID
与 contract mode，并把提升限制为完整 Gemini bundle 的窄路径。

## 2026-08-04 Flash 第二模型证据复核暂停检查点

- recovery review v4 对 s0/s1 证据完整性均 PASS，同时保留 s0 10>6 的真实
  质量门失败；旧 review、ledger 和终态 work key 均未改写或重试。
- second-role merge v1 完成精确 1791 work-key 闭包，16 diagnostics 全部 ITT，
  4193 calls、CNY 1.87793024，manifest `7fba09cc...8432b`。write/verify exit 0，
  科研 outcome 与 result admission 仍关闭。
- pytest 8/8、Ruff、py_compile、项目 conventions 12/12 通过；无相关进程。
  没有新 full Harness，故任务
  仍 `in_progress`。owner 要求在报告 SHA `e55f3bbf...f6ea8` 后停止。

## 2026-08-04 当前正式运行收口检查点

- Flash recovery-v3 完成 1306/1306 新记录；全角色达到 1791/1791 物理闭包，
  16 diagnostic、4193 calls、CNY 1.87793024。两个 wrapper 均因 technical gate
  FAIL exit 1，结果准入仍 false；不重试、不改写。
- s0 的真实门禁失败为 10 diagnostic > 6。review v3 还把
  `source_terminal_records_retried=false` 误作 `all()` 的失败布尔，导致 s1 在
  其余门全绿时仍失败。修复必须使用新 review 版本。
- Gemini s1 官方调用 HTTP 200、精确模型和 response ID 存在，但无 provider
  request ID；历史 formal record 契约与 local-precommit 链不兼容，非 429。
  abort manifest `6d7605dd...d649` 已封存为不可恢复、不可重试、结果不合格。
- 定向验证 7/7、Ruff/compile、write/verify 通过；所有相关进程已自然结束。
  owner 要求在阶段报告后停止，F-PAPER-002 继续 `in_progress`。

## 2026-08-04 Gemini Public-v5 segment 1 启动检查点

- 当前 LA 配额日 `2026-08-03` 在项目账本中未预约；segment-1 admission
  `93ba06fc...e03a` 为 2 records/最多16 requests/free-only/USD 0/retry 0。
- v5 guarded wrapper PID 42336 于 00:34:36 单次启动；同日不再启动其他
  Gemini formal workload。Flash 双分片独立运行，不共享 ledger/budget/output。

## 2026-08-04 Flash recovery-v3 启动检查点

- Fresh Harness gate-v3 write/verify 完成，manifest `e06188dc...b985`；provider
  execution authorization 仍 false，独立 admission 是必要门。
- 两份 exact admission 分别绑定 652/654 个从未触碰 work key 与 CNY
  2.04118328/2.17094144，retry/tools/effects/results 为 0/false/false/false。
- single-use wrappers s0 PID 25256、s1 PID 43856 于 00:13:15 各启动一次，等待
  自然终态。旧 prefix/diagnostics/canary 不重试，Gemini/Adaptive/blind 不并发。

## 2026-08-03 Fresh Harness v4 完成与暂停检查点

- single-use v4 自然完成并直接 exit 0：13/13 聚合阶段通过，pytest
  1485 passed / 1 skipped / 3 warnings，最终 `Verification failed=0`。
- receipt/stdout/stderr 已分别以 `a9fddc0f...2c1b`、`1b1a5305...3d75`、
  `777e65d1...2c26` 绑定；API env scrubbed，provider/network 未授权，API 调用 0。
- 所有相关 Harness/旧 Flash wrapper PID 已自然结束。按 owner 最新指示，本轮
  在报告交付后暂停：不生成 gate-v3、不生成新 provider admission、不执行
  Public recovery、Adaptive 或盲测。
- 详细阶段报告位于
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性实验报告_2026-08-03_Harness_v4.md`，
  SHA-256 `107c779c...3333`。
  这不是最终实验结项；F-PAPER-002 保持 `in_progress`。

## 2026-08-03 fresh Harness v4 运行检查点

- preflight 的 fresh-root、process、PowerShell parse、failure-review 和 Day-1
  acceptance 门全绿后，single-use launcher 于 16:03:32 启动 helper PID 37772。
- 输出根 `experiment_closeout_fresh_harness_v4_20260803`，verifier SHA-256
  `33390d65...c6e4`；API env scrubbed，network/provider false，自动重启 false。
- receipt 前不停止/重启、不创建 gate-v3、不生成 provider admission、不调用 API。

## 2026-08-03 interim Harness v3 失败审查与 fresh-v4 准备

- v3 detached Harness 自然结束并直接 exit 1：1456 passed / 1 skipped /
  3 warnings，唯一失败为旧静态测试把合法 adaptive v2 Pro admission 误判为
  v1 admission。failure review manifest `67bcdaaa...78cf9` 已冻结，零 provider。
- 测试现按 controller 版本判定：要求 v2 admission、禁止 v1 Pro/Flash admission。
  focused 20/20、扩大组合 38/38、conventions 12/12；`verify.ps1` SHA-256
  `33390d65...c6e4`，Gemini/Flash 相关独立 verifier 均 exit 0。
- fresh Harness gate-v3 和 single-use v4 launcher 已离线资格化；不提前生成 gate，
  不把 exit-1 改写为绿色。只有 fresh v4 直接 exit 0 才能继续 exact admission。
- Flash 双分片旧进程已自然结束且不得恢复；recovery-v3 只覆盖 1,306 个未触碰
  work key。Gemini continuation-v2 保留 1,779 条和免费层 1,186 日下界。两者均
  未执行新 API，结果准入 false。Day 1 登记 3/3 文件当前再次重放通过。

## 2026-08-03 Gemini v5 对账与免费续跑检查点

- Public-v4 segment 0 的原 v4 失败和 ITT runner failure 保持不变；
  failure-aware v5 精确对账 1 provider attempt / 1 transport completion /
  1 `VigilLiveDependencyError`，14/14 checks，manifest `8c256e49...9728c`。
- 缺少 wrapper receipt 的恢复工件 `1df13ad9...47f1f` 明确不伪造
  receipt：OS exit unknown、segment terminal、same-segment retry false、result
  admission false。compile/Ruff、3/3 tests、write/verify 均通过。
- continuation-v2 完整保留 1,779 条/1,186 个日段字节不变，激活
  门更正为 v5 aggregate；manifest `fcc80d26...5c95`，付费、Batch、
  provider execution 和 result admission 均 false。在 18 RPD 本地上限下，
  canary 后的标准路线至少需 1,186 个配额日，触发用户锁定的工期
  自动顺延，不得伪装为 21 天可完成。
- 未来 canary segment 的 v5 guarded wrapper 已通过 PowerShell syntax、
  Ruff 和 3/3 测试；必须先获得新 full-Harness gate 和当日 exact
  admission，否则 fail closed。
- interim Harness v3 仍在自然运行且 pytest 已显示一个 F；Flash 双分片
  仍在增长。禁止终止/重启，等完整 receipt/log 后再定位修复。

## 2026-08-03 Flash 正式公共续跑检查点

- fresh Harness v2 直接 exit 0（1451 passed / 1 skipped / 3 warnings，13/13
  stage PASS）；Flash second-role canary 12/12、18 calls、CNY 0.01232192，
  outcome-blind technical gate 通过。
- continuation-v2 冻结 1,779 条为 890/889 两片，candidate manifest
  `18b80a5c...2906`，总 CNY ceiling 5、retry 0、tools/effects false。
- 两个 exact admissions 离线验证通过并于 11:52:22 各启动一次；wrapper PID
  41632/23180。不得自动重试或读取科研效果，等待自然终态 receipt。

## 2026-08-03 fresh Harness v2 启动检查点

- Day-1 原始 verifier receipt 已恢复且 acceptance/2 tests 全绿。
- fresh Harness gate v2、single-use launcher 和 guarded canary wrapper v3 已通过
  24/24 定向测试、Ruff/compile/PowerShell syntax；gate 不自行授权 provider。
- PID 31716 正在全量验证，输出根
  `experiment_closeout_day2_harness_v2_20260803`，API env scrubbed、network false。
  receipt 和 gate v2 通过前禁止 canary；F-PAPER-002 保持 `in_progress`。

## 2026-08-03 Day-2 Harness 失败固化与 supersession 接线

- Day-2 v1 完整 Harness 直接 exit 1：1438/1/3，唯一失败为陈旧 Pro-50 v1
  admission 检查；失败审查 manifest `230fc98...e398f` 已冻结且零 provider。
- 当前 Harness 不再重放两个永久废止的 adaptive-v1 admission；改为验证 v2
  order/supersession、Day-2 failure review 和 Day-1 acceptance。历史文件未改写。
- PowerShell/Ruff/compile、14/14 定向测试和 10/10 无凭据 closeout 离线复演
  通过。fresh 完整 Harness 及 provider canary 等待缺失的 Day-1 verifier receipt
  恢复；F-PAPER-002 保持 `in_progress`。

## 2026-08-03 Day 1 已完成，当前登记证据重放缺口

- 当前 inbox 复核只见公钥和 registration v2；历史 acceptance 所绑定的
  `custodian_registration_verifier_receipt_v2.json` 缺失。
- 两份存量文件的 SHA-256 与历史 acceptance 相符，但精确三文件闭包不成立，
  验收器与定向测试均按设计 fail closed。
- 历史 acceptance 不删除、不覆盖；pytest 临时负例不作为证据。Day 1 完成及
  技术时钟不追溯撤销；当前 `blocked_missing_verifier_receipt` 仅表示最终证据
  重放缺口。F-PAPER-002 继续 `in_progress`，原始回执重新交付并完成重放前不
  启动 fresh Harness 或盲测执行。

## 2026-08-01 21 天实验结项授权

- 用户授权实施只含实验、证据链和工程验收的结项计划；论文/JISA 包不在本轮。
- 正式范围为：冻结历史 controller-v7 abort；完成 Flash/Gemini 公共矩阵；
  完成 Pro/Flash/Gemini adaptive 与 hardest-20；完成第三方 600 条盲测；
  完成独立统计复算、完整 Harness 和哈希结项包。
- Flash 公共范围沿用冻结 1,791 条 second-role。Gemini 将创建同构的新计划，
  只改变 provider/model/run identity；Gemini 始终 free-only、USD 0 paid tier。
- adaptive v1 保持不可变；新版本只增加 Gemini 20 任务 50/200 面板，并要求
  provider 隔离的 ledger/checkpoint/budget。所有终态失败保留 ITT，自动重试为 0。
- v7 已是永久封存的历史控制器失败，不是待开发的新 M3 机制版本；本轮只复验
  abort hash/chain，禁止恢复旧身份或 API 调用。
- Day 1 基线：Python 3.13.5 可用、活动项目进程 0、工作树原有状态项 324。
  下一门禁为当前工作树完整 Harness；正式 API 调用在离线资格和单独 admission
  之前保持 0。
- Day 1 已落地的 prospective 工件：Gemini 1,791 条镜像计划、adaptive-v2
  79,000 查询上界、v7 immutable audit、blind-closeout label-free interface、
  Gemini JSON trace/store/controller-v4。旧 Gemini public-v1/v2/v3 均在 0
  调用状态下被 supersede；v4 以 8 个 quota-day 独立 identity 承载相同 12 条
  canary，并用 project-global append-only day reservation 防止公共/adaptive
  共用 18 RPD。DeepSeek Flash canary 尚未执行。
- 新增离线回归当前通过：closeout freeze 6、blind interface 6、Gemini trace
  4、Gemini store 2、Gemini controller-v1 3、Gemini JSON client 6、Gemini
  controller-v2 5、Gemini shared-usage controller-v3 5、Flash policy-aware
  continuation 4。最终须在修改完成后以一个合并定向套件和完整 Harness
  重新确认，不能用正在运行的 Day-1 pre-change baseline 替代最终验证。
- Pro full-adaptive plan 已扩展到 40 tasks × 2,000 known query keys，并通过
  q2000 projection/gold-field isolation。历史 CNY 5 前缀不原地换 policy；
  四个新阶段各用独立 identity/root，仅复制 checkpoint，成本 ceiling
  10+20+35+85 加历史 0.552805 为 CNY 150.552805，并为 Flash adaptive 保留
  CNY 29.447195，使 Pro+Flash 总 ceiling 精确为 CNY 180。Pro-50 的 32-task
  exact-command admission 已重新冻结但未执行；hardest 诊断补位规则也已在
  预算 500 新结果前冻结。DeepSeek Flash 20-task 50/200 控制器、独立根、
  checkpoint 前缀、预算和准入已实现；相关 focused tests 22/22、Ruff、
  py_compile 通过。Flash-50 已冻结但未读取 credential 或执行。
- Gemini 当前 Free 项目只有 20 RPD，执行本计划的 1,791 公共项必然跨越至少
  100 quota days；12 条 canary 作为正式前缀后，1,779 条 pending-only 的
  max-call 安全装箱为 1,186 天。public/adaptive 合并的理论下界为 323 quota
  days，按锁定 canary 的前瞻最小值为 330 天，最坏安全装箱为 3,194 天；机器可
  复算 qualification manifest 为
  `31861f65d7dc38c684730d3b4c5b20c35cc76d23bdf18436d4e9f2374039a7a6`。
  `21 天`按用户锁定规则顺延，不能启用 Billing 或把 paid Tier-1 比较值当成
  免费额度。
- 在正式调用前完成 evidence chronology 自检：六个 prospective 草案时间和
  一份旧 Pro admission 存在未来时间，Gemini-v4 还引用了错误的 plan 文件名。
  两类问题均在 0 network/0 outcome 状态下修正并重建传递哈希；任何历史终态
  实验均未改写。
- Gemini public continuation 的离线 schedule/candidate 已完成：12 条正式
  canary 前缀不重放，1,779 条 pending 项保持源顺序，1,186 个 quota-day
  segment 归入四个连续 logical shard family；candidate manifest
  `2cd8e8829f77868249756cb57db62b9b497e3d4a53aa036260a755f14d4153b6`。
  当前 execution authorization=false，v4 aggregate technical pass 是强制前置门。
- Gemini adaptive quota schedule 已覆盖 20×200=4,000 个最大查询槽并冻结为
  2,000 个免费层日分段；每段最多 2 查询/16 calls，candidate manifest
  `46080eb36ccbd1f6bb9cac0b1d1740668fff84bfac1553b8abf26b93540107dc`。
  当前仍为 non-executable，后续需新增 exact-day successor controller。
- Day-1 full Harness 仅完成了 pytest 子段（1,266 passed、1 skipped），随后在
  历史 replay 被宿主中断且无 receipt/aggregate marker；该运行不得作为绿色
  基线。离线实现稳定后必须重新取得当前工作树 exit 0 的完整 receipt。
- Gemini public-v4 的 8-day/12-record candidate 已重建并锁定，manifest
  `80ac8930af5107001fecbb756d25a35d2e5d5027e94d164a5987c958a60751eb`。
  新的 continuation controller 将 1,186 个 pending quota segments 逐日映射到
  fresh identity、独立 ledgers/traces 和 project-global reservation；未取得
  v4 aggregate technical pass 时不能创建第一个 continuation candidate。
- Gemini adaptive 已从 non-executable capacity schedule 升级为逐日 successor
  实现：两查询/最多16 requests/day，前一 review 提供全部20任务的 query count、
  terminal class 和 latest checkpoint lock；success/diagnostic 的未来槽永久跳过，
  active task 只允许从 q-1 精确推进到 q。专用 query store 同时保留完成 calls
  与包括429在内的 attempted requests，避免无 response-ID 失败被免费层计数漏掉。

## 2026-07-28 全矩阵引文审计与 evidence-80 v3

- 34/34 条文献已对权威 publisher/proceedings/DOI/arXiv 记录核验，现为
  24 PR/10 PP；纠正 18 个标题、1 个 Oral 标记、2 个状态和 1 条 L20
  完全错链。L20 以经 ICSE 2026 官方页面/DOI 核验的 AgentSpec 替换并
  保留纠正轨迹。
- citation/manuscript 7/7、Ruff、manifest `--verify-only`、stale-title
  scan 和 arithmetic assertions 通过。全文 inline contexts、bibliography、
  submission-date refresh 和机构 JCR 仍 pending。
- scorecard 更新为 753/1200=62.75%（报告 63%），submission 60%。
  evidence-80 v3 修正历史 v2 表内“其他九项”620（按当时分数应为 690）
  的算术错误；当前路线为 public +90、adaptive +100、manuscript +25，
  目标 968/1200=80.67%。v2 和所有实验冻结保持不可变。
- 本阶段 0 credential/API/network/model calls。04:38 full Harness 因先于
  最新代码/测试启动而只作 superseded 运行；其退出后需重跑当前工作树。

## 2026-07-28 Public-v1 Stage A

- 完成 6,873 条计划、5,082/1,791 Pro/Flash 分层、24/12 canary 选择和
  source/online-state/sequence 哈希冻结。
- 完成 public 专用 budget/client/trace/store/controller/admission/
  preregistration/result-gate 实现；保留中型 v1–v9 历史不变。
- 验收边界：总增量 CNY 25，Pro/Flash CNY 20/5，retry 0、并发 1、
  provider tools/external connectors/external effects false；全量结果必须
  6,873/6,873 且失败留在 ITT。
- 当前证据：focused 25/25、Ruff PASS；完整 Harness 1,126 passed、
  1 skipped、3 warnings、全部 stage PASS、`Verification failed=0`；
  Stage-A/analysis/result-gate 复现均 exit 0。owner exact-command
  confirmation 尚未收到，active admission 未创建，API/network/model
  calls=0。

## 2026-07-27 80% 科学证据执行计划 v2

- 用户要求在新实验前重新规划。本阶段完成度不变，API/network/model calls=0，
  正式结果=0，执行授权=false。
- 当前科学分数 730/1200。可审计的 80% 路径为：正式公共基准
  10→100（+90）、自适应攻击 0→100（+100）、manuscript
  30→70（+40）；其余九项不提前上调。
- 公共冻结经真实字段复核为 6,873 条：Pro 六条件 5,082，Flash 三条件
  1,791。按中型 v8 条件级证据外推约 15,828 calls、CNY 12.03，计划 fuse
  CNY 25。先运行 24 条 Pro 与 12 条 Flash 技术 canary，后续不重复。
- 新审计确认 paper-v2 public controller/result gate/analyzer 尚不存在；
  adaptive 仅有 provider-agnostic runner，尚无 official bridge、durable
  query/call store 和 result gate。先实现版本化离线层及负例，完整 Harness
  全绿后才可调用 API。
- 执行优先级改为公共基准 → 自适应 8×50 成本 canary → 完整自适应 →
  论文回填。Gemini v3 作为跨提供商增强但不阻塞 80%；Flash 结果只能称跨
  模型泛化。
- 冻结产物：
  `docs/research/paper_v2/M3_PI_Guard_80_percent_evidence_execution_plan_v2.md`
  和 `protocols/paper_upgrade_v2/evidence_80_execution_roadmap_v2.json`。
- 当前人工检查点：等待 owner 确认。确认后下一阶段仍是 offline-only 实现，
  不是立即运行正式实验。
- 最终规划核验使用 Python 3.13.5：JSON/hash/score/public/adaptive assertions
  全过，secret-pattern 0，manuscript workspace 4/4，diff check 通过；没有
  运行完整 Harness、读取 credential 或调用 API。

## 2026-07-27 Gemini Free prospective v3 配额与连通性诊断

- Owner 项目页确认 dedicated project 已回到 Free，paid billing 解绑。当前
  免费层从 console 比较推导为 5 RPM、250K input TPM、20 RPD；新 v3 本地
  fuse 为 4 RPM、200K TPM、18 RPD、16K output tokens/day，保留 2 RPD。
- 新 quota snapshot/override 只面向未来 prospective v3，不修改或恢复
  Gemini v1/v2。0 paid tier、0 retry、0 provider tools、0 external effects、
  concurrency 1；完整 192-item 路线必须跨 provider day 调度。
- 两张截图 digest、snapshot/override hash 和现有 budget policy 离线验证通过。
  随后恰好一次 fixed SAFE 诊断返回 HTTP 200，exact model 和 exact SAFE，
  32/1/44 tokens、1996.3301 ms。
- response ID 存在但 request ID 缺失，故模型与连通性诊断通过、正式请求链
  不完整。新脱敏 artifact 明确 scientific_result_eligible=false；
  v3 controller/candidate/admission 和 formal result 均尚未创建。
- 本步骤不改变 61% 科学完成度或 56% submission readiness。下一步仍需先
  实现持久化 Pacific-day provider-call meter，再进行 v3 的全新冻结和准入。
- 验证：4 个 JSON/hash/secret-pattern 交叉校验通过；相关配置、budget 和
  official-provider tests 33/33 通过（1 条已知 Pydantic warning）；
  `git diff --check` 通过。diagnostic SHA-256：
  `644f1f3a521ee0d5ef9688a17061e244eed4236a04fc6d05a714552c282fca4f`。

## 2026-07-27 Gemini Tier 1 截图根因收敛

- 当前 AI Studio exact-project screenshot 显示 Tier 1，Gemini 3.6 Flash
  峰值为 2/1000 RPM、1.35K/2M TPM、3/10K RPD。公开三项 quota saturation
  与 key-project mismatch 均显著降级。
- 最可能 blocker 为 paid Tier 1 billing/prepay 状态，而不是模型/route 或请求
  参数。需要只读确认结算页的 positive credits、plan 和 account status；
  不通过额外 API 请求诊断。
- 截图只保留 SHA-256，不复制含局部账户信息的图片。旧 free-tier snapshot
  不修改；任何 Gemini v3 都必须在 billing 状态稳定后新建 quota snapshot。

## 2026-07-27 Gemini 独立连通性复测

- 使用既有 official-provider client 执行一次固定安全文本的 Gemini-only
  诊断。ignored local config 中 key 非占位，冻结
  `gemini-3.6-flash` 和 Google 官方 base URL 准入通过。
- 首次请求返回 HTTP 429，客户端按策略立即停止：1 attempt、0 retry、
  0 provider tools、0 external effects、0 formal results；没有完成响应，
  因而没有可验证的 returned-model、response identity 或 token usage。
- 该诊断不属于 Gemini v1/v2，不修改其冻结证据，也不进入 ITT/effect table。
  当前第二模型实验继续阻塞；配额恢复后只能创建 prospective v3。
- 无请求根因复核显示：同一 config 在 7 月 23 日曾成功调用相同 model/route，
  后续跨天三次首请求均为 429。官方确认 3.6 Flash 为 GA 且 Standard free
  tier 可用，OpenAI route 受支持，quota 按 project 计算；当前最高优先解释是
  exact key-project 与截图 project 不一致，或该 project 的 active quota/
  account provisioning 异常。
- 当前 429 正文只留 digest，精确 quota dimension 未持久化。owner 需在
  AI Studio 对 exact key-project 核对 key status、tier、active model limits、
  usage 和请求日志；不得通过额外试探请求猜测。

## 2026-07-27 阶段报告与 Gemini 失败边界

- Gemini v1 唯一 canary 在 structural 条件因 VIGIL constraint-generation
  静默 fallback 失败关闭；abort review 将其冻结为 result-ineligible、
  non-resumable，0 experiment record、0 evidence sidecar。
- 新 prospective v2 只含 policy-only/full，共 192 行；资格、candidate、
  canary admission 和专项验证通过。首个官方请求收到 HTTP 429，controller
  立即暂停并保留 1 条 diagnostic ITT 记录；0 completed call、0 token、
  0 retry、0 provider tools、0 external effect。v2 不得恢复，配额恢复后
  必须新建 v3。
- 生成并验证
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-27.docx`
  （SHA-256
  `27b366847dcdfd1b8fa48aa5f766cb0839583d9686084f87cba45b460073e5b3`）。
  报告含 6 图、21 表、DeepSeek 主结果/机制门禁/授权 regime/Gemini 失败/
  99-61-56 完成度和自适应、公共、第二模型、盲测、统计、投稿计划。
- structural QA 通过：ZIP/OOXML、页面、21/21 表格几何与重复表头、real
  numbering、6/6 image alt、11 hyperlinks、a11y 0/0/0、占位符/密钥模式/
  批注/修订 0；6 张图人工检查通过。canonical renderer 因本机无 `soffice`
  在打开 DOCX 前失败，因此不得写 page-render passed。
- 下一步不迭代 v7 机制：先冻结 Methods/Results 与 claim ledger，之后实现
  DeepSeek 自适应 official bridge 和 8×50 成本 pilot，再推进冻结的
  6,873 条公共扩展。Gemini v3、blind custodian 与 JCR 核验保持外部门禁。

## 2026-07-26 DeepSeek medium 结果与路线切换

- v8+v9 合并证据已完成 480/480，combined gate v6 和独立 analysis
  admission 通过；正式分析 v8 在冻结后生成并完成独立重建。
- M3-full 相对 structural unsafe effect 为 0/36 vs 8/36
  （−22.2pp，bootstrap 95% CI [−36.1pp, −8.3pp]），但 benign-tool
  TCR 为 6/24 vs 12/24（−25pp），且 full 对 policy-only 的 unsafe effect
  增益为 0。
- 按冻结规则 mechanism paper candidate=false、
  fallback empirical study=true。后续研究问题优先级调整为：
  authorization regime 对 ASK/TCR/unsafe-effect 估计的影响、不同来源与模型的
  异质性、以及安全收益是否主要由阻断/确认负担换取。
- DeepSeek 中型实验不再追加或重试。下一 prospective 单元是 Gemini 第二模型
  fallback 扩展；必须单独资格、候选、owner admission、append-only 记录和
  outcome-blind result admission，且保持 free-only、0 retry、0 provider tools
  与 0 external effect。

## 2026-07-26 v9 remainder 前绿色验证

- 更新后的完整 Harness 使用 Python 3.13.5 唯一运行并自然结束：
  1081 passed、1 skipped、3 warnings，12 个阶段全部 PASS，
  `Verification failed=0`。
- v9 qualification/candidate/admission 与 combined result gate v6 均完成重放；
  303 条 v8 终态和 177 条 v9 pending work key 精确覆盖 480，交集为 0，
  diagnostic 保留在 ITT，scientific outcomes 未读。
- 日志位于
  `outputs/paper_upgrade_v2/verification/pre_v9_remainder_full_rerun/`；
  三条 `delete_record` stderr 是安全审计预期阻断。
- 当前获准启动一个 v9 pending-only segment；禁止自动重试终态项、provider
  tools、真实外部 effect 和并发 Gemini。

## 2026-07-26 v8 continuation 前绿色验证

- 完整 Harness 使用 Python 3.13.5 唯一运行并自然结束：1073 passed、
  1 skipped、3 warnings，`Verification failed=0`。
- v8 candidate/canary/continuation admission、result gate v5、历史冻结和
  当前 V2 freeze 均完成重放；三条 `delete_record` 为安全审计预期阻断，
  无删除或真实外部 effect。
- 允许执行已冻结的 474 条 DeepSeek continuation；仅允许单进程、零自动重试、
  零 Gemini 并发、零 provider tools 和零真实 effect。
- 完成后先做 outcome-blind technical review；不得在 result admission 前读取
  scientific outcomes。
- 已于 2026-07-26 15:47:08 +08:00 启动唯一 continuation 实例：
  launcher PID 73484、Python PID 33056；运行中禁止第二实例和 Gemini 并发。
- v8 在 303/480 时由单条闭合 `ProviderTransportError` 自然暂停，形成
  302 completed + 1 diagnostic、0 open、177 never-started 的不可变证据；
  不得重试失败项或再次调用 v8 continuation。
- 新的最小实现是 prospective remainder shard + combined gate：新 shard
  精确绑定 v8 技术快照，只执行 177 个 pending work keys，并在两份 append-only
  ledger 上验证无交集/无遗漏/480 全覆盖。所有新协议必须在下一次 API 前冻结。

## Scope

### Allowed

- 新增 `docs/research/paper_v2/` 下的文献矩阵、创新边界、源码审计和论文计划。
- 新增 `protocols/paper_upgrade_v2/` 下的研究协议、预注册草案、准入规则和冻结。
- 新增 `experiments/paper_v2/`、`schemas/paper_v2/` 和对应测试。

## 2026-07-26 v7 result gate v4 检查点

### Goal

在不修改 v7 已冻结执行身份的前提下，为 v7 新建 prospective result gate v4，
使哈希化 proposal-message boundary rejection 证据从 producer 到 evaluator
均被结果准入门锁定，并在任何 API canary 前完成离线资格和完整 Harness。

### Allowed

- 新增 `experiments/paper_v2/formal_result_gate_v4.py`。
- 新增 `schemas/paper_v2/formal_result_gate_v4.schema.json`。
- 新增 `protocols/paper_upgrade_v2/formal_result_gate_qualification_v4.json`、
  `deepseek_medium_result_gate_candidate_v4.json`。
- 新增 `tests/unit/test_paper_v2_formal_result_gate_v4.py`。
- 更新 Harness verifier、v6 stale-state test 和非冻结 Harness 状态/决策文档。

### Forbidden

- 不修改 v1-v7 matrix controller/candidate/admission/qualification 或 v4-v6
  append-only 运行证据。
- 不修改 formal result gate v1-v3、provider safety、M3 Guard 授权、
  paper-v1/E0-E17 或凭据文件。
- 离线门禁通过前不得创建 v7 output root 或执行 API。

### Acceptance and verification

1. v4 qualification 复用冻结 operational policy，保持
   `scientific_outcomes_read=0`、`network_calls_made=0`。
2. candidate 精确绑定 v7 run/matrix/canary、controller-v7 和
   boundary-rejection-runtime-v3；analysis/result admission 保持 false。
3. 正例和 incomplete/runner-failure/unverified-identity/diagnostic-status
   负例全部 fail-closed。
4. v6 aborted state test 必须验证 open attempt 拒绝恢复并复验 abort review v2。
5. 专项 pytest、Ruff/compile/JSON、candidate 重放和完整 Harness 通过后，才允许
   一次 DeepSeek v7 canary。

## 2026-07-24 DeepSeek v5 正式矩阵检查点

### v4 终止与 v5 语义

- v4 在 395/480 时按旧预算投影门暂停，outcome-blind review 证明其不满足结果
  准入；v4 永久不可续跑、重试、改写或分析。
- v5 只修复已知 effect-boundary rejection 的终态表达：Guard ALLOW 保持原样，
  被拒动作不执行，收据为 no-effect，结果保守进入 ITT。真正未知异常仍是
  runner failure；`provider_safety.py` 与 `m3_guard/` 未修改。
- 六条件 canary 为 6/6、13 official calls、0 retry/failure/diagnostic/effect，
  成本 CNY 0.7522526。技术 review 不含 scientific outcomes。

### 预算与结果准入

- 项目所有者允许 DeepSeek/Gemini 继续用于安全研究调用，历史 CNY 27/30 不再是
  项目停机条件。逐调用计量、官方身份、单 provider、0 retry、无工具/外部 effect
  和 provider quota/credit/rate-limit 熔断保持。
- result-gate v2 在 continuation 前冻结：480 条完整 ITT、0 open、0 unknown
  runner failure、身份/trace/isolation 完整是结果访问条件。闭合 provider/
  timeout diagnostic 最多 1%；质量超阈触发实证论文转向，而不是删除失败样本。
- gate candidate 与 continuation admission 已分别冻结，scientific outcome 和
  result admission 仍关闭。正式运行前必须完整 Harness `Verification failed=0`。

### 下一执行顺序

1. 完整 Harness 验证更新后的 gate/admission/analysis 身份。
2. 仅执行一次 v5 continuation，禁止自动重试和 Gemini 并发。
3. 运行中只监控内容无关 operational metadata。
4. 完成后运行 paper-v2 与完整 Harness，再写 outcome-blind technical review。
5. technical gate 通过后才写 result admission 和 analysis；否则冻结失败证据。
6. 再按结果决定 Gemini、公共基准、自适应攻击和独立盲测扩展。

## 2026-07-24 DeepSeek v4 正式中型矩阵检查点

### 当前授权与身份

- v1、v2、v3 分别因 thinking 截断、可信上下文未呈现、默认 text format 的
  strict-JSON failure 冻结为不可重试历史。v4 是独立 run/matrix identity。
- v4 固定 DeepSeek `deepseek-v4-pro` 官方端点、non-thinking、
  `response_format={"type":"json_object"}`、严格 proposal parser、0 retry、
  0 fallback、provider tools/外部 effect 关闭。
- 六条件 canary 单次完成 6/6 records、13 official responses、0 operational
  failure、0 diagnostic。canary review 未读取 scientific outcomes；独立
  continuation admission 只授权其余 474 项。
- 正式 continuation 已启动，DeepSeek 项目累计 CNY 27 熔断保持不变；Gemini
  不并发。运行期间不修改 v4 client/controller/schema/candidate/admission/
  qualification。

### 结果准入与分析

- `formal_result_gate_v1.py` 的零网络资格覆盖 1 个 pass 和 4 个 fail-closed
  场景。当前 prospective candidate manifest 为
  `e72fad7ec1fe333153dbb10de2231df05677e262be08c25346bc029ed6a2e1e5`。
- 科学字段在 480/480、0 open、0 operational failure、全 formal-candidate、
  exact official identity、完整 trace/safety evidence 和未暂停预算全部通过前
  不得解封。technical review 后仍需独立 result admission。
- `medium_analysis_v2.py` 保留 unsafe-effect/TCR、McNemar、10,000 cluster
  bootstrap、Holm、power 和 mechanism gate，并预先固定 ASK/确认、五种
  authorization regime、latency、token/cost 和异质性。
- 冻结跨基准 record 没有独立 per-action unauthorized/data-spill 标签，所以本
  矩阵不把 unsafe effect 重命名为 UTR/DSR。后续只有具备相应 evaluator 标签的
  数据集专用实验可以报告二者。

### 完成顺序

1. 等待同一 continuation 自然完成或既定预算/服务熔断；禁止自动 retry。
2. 进程退出后运行全部 paper-v2 和完整 Harness。
3. 写入并复验 outcome-blind technical review。
4. review 自动通过时才写 result admission，再运行 expanded analysis。
5. 根据冻结机制门禁选择防御机制论文或授权泄漏/不确定性实证转向。
6. 之后再决定 Gemini 第二模型、公共正式扩展与自适应攻击；独立盲测仍需外部
   custodian。

## 2026-07-24 单条 DeepSeek pilot 控制器检查点

### 分析结论

冻结计划、单条件 live runtime、逐调用 v2 trace 与 append-only record-v2
此前均已存在，但没有一个正式控制器把“精确 work item → owner admission →
密钥读取 → official client → sandbox runtime → record-v2”按失败关闭顺序串联。
直接运行任一底层模块会绕过 run-specific admission，因此不能作为正式 pilot
入口。

### 实施范围

- 新增 `formal_execution_controller_v2.py`，只选择冻结计划中第一个
  `m3-v2 / benign_no_tool / no_defense / auto_compiled / primary` work item。
- 新增 pilot admission JSON Schema、不可执行 owner-review candidate 和零网络
  controller qualification。
- 候选锁定 DeepSeek exact model、CNY 27 abort ceiling、8-call work-item 上限、
  0 retry、0 fallback、0 provider-managed tools、M3 sandbox effect backend、
  trace activation、v2 record store 与 dedicated single-use paths。
- active admission 必须是不同文件，并包含 explicit
  `project_owner` one-pilot checkpoint；candidate 自身不能被执行入口接受。

### 验证与边界

- 4/4 negative probes 在 credential loader/client factory 之前拒绝：
  missing active admission、candidate self-authorization、scope drift、
  pre-existing output。
- 1 个 permit-only positive probe 仅验证 exact scope；不读取密钥、不建 client、
  不运行模型。另有 1 个完全本地的 injected-transport 端到端资格样例，在临时目录
  写入 1 条 formal-candidate record，验证 controller → trace → usage/cost →
  record-store 的闭环；它不读取密钥、不访问网络、不写项目结果目录。
- provider trace bundle 2.1 对每个 completed call 强制记录 content-free 的
  cache-hit/cache-miss/output token、provider receipt digest、单次/累计 CNY 成本
  与预算状态。三个离线 completed calls 均有完整 usage/cost 证据。
- controller tests 9/9；usage/trace/store/gate/controller 相邻回归 28/28；
  paper-v2 199/199；完整 pytest 970 passed / 1 skipped / 3 known warnings；
  完整 Harness `Verification failed=0`。
- 未创建 project active admission、API result、experiment record 或 formal
  result。正式 pilot 仍停在学术检查点，等待用户对 exact candidate 的明确批准。
- 复用 paper-v1 的非 oracle runtime、公共基准适配器和已有原始证据，但必须保留
  原证据身份与证据等级。
- 修复未冻结的测试/辅助代码，使当前完整验证能够恢复；任何涉及旧冻结身份的修复
  必须使用新版本而不是改写旧文件。
- 更新 Harness 当前任务、进度、功能台账、决策日志、失败日志和会话移交。

## 2026-07-24 pilot 后置证据审查检查点

### 发现与修复

- runtime 已生成安全收据，但 experiment-record 2.1 未持久化它，无法从归档记录
  独立证明“官方 API 只产生不可信 proposal，实际 effect 仍受隔离边界控制”。
- prospective record 升级为 2.2：新增严格 safety-receipt schema，并把收据纳入
  record hash 与 append-only ledger。
- 新增 post-pilot reviewer，交叉复验 active admission、独立 trace、bundle、
  cache/cost、provider/model、token、safety action digest 与 ledger tail。

### 准入语义

- 完整且成功的 official pilot 只能进入
  `ready_for_owner_matrix_review=true`；review 本身始终保持
  `formal_matrix_authorized=false` 和 `result_admission_authorized=false`。
- offline injected fixture 只能通过 structural gate，official gate 与 owner-review
  readiness 必须为 false。
- candidate 锁定输入由 8 扩展到 23，覆盖 transport、budget、safety、trace、
  runtime、record 和 review 代码/模式。

### 当前证据

- reviewer positive fixture 1；negative rejection 4/4；网络/凭据/项目结果均 0。
- candidate canonical manifest SHA-256：
  `6ac0601865d76f5f808952b2f58e6587d02c303ac5e9a998ae4d751fbb3dd4cc`。
- focused 33/33；paper-v2 204/204；完整 pytest 975 passed / 1 skipped /
  3 known warnings；Harness 重复 975/1/3 且 `Verification failed=0`；
  Ruff/JSON/冻结 artifact reproduction 均通过。

### Forbidden

- 不改写 `protocols/paper_upgrade_v1/`、`outputs/paper_upgrade_v1/` 中冻结或
  哈希绑定的证据字节。
- 不将计划、smoke、diagnostic、partial 或未审计中转 API 结果提升为正式证据。
- 不读取、输出或提交 `config/project.local.env` 或任何真实凭据。
- 不自行生成并标记“独立盲测”；没有独立保管链时只能称内部 sealed holdout。
- 不启动大规模 API、模型或公共矩阵，除非前置中型门禁、成本边界和提供方身份审计
  已通过。
- 不提交、push、创建 PR、部署、制作 PPT、DOCX 或 ZIP。

## Research Questions

1. 逐样本授权/评估字段进入在线 Guard 后，会在多大程度上改变安全与效用估计？
2. 在不读取 gold authorization 的条件下，M3-full 相对结构化强基线和
   M3 policy-only 是否有可复现的 unsafe-effect 降幅？
3. 权限单调扩张和 `ASK` 是否能在上下文依赖任务中避免 deny-all，同时满足
   TCR 非劣界限？
4. 上述结果在防御感知自适应攻击和至少两个外部基准上是否保持方向一致？

## Implementation Plan

1. 建立 30+ 篇 2024–2026 直接相关文献矩阵，区分同行评审与预印本。
2. 对至少 20 个开源防御/基准实施 online-state 源码审计；没有源码证据时不作
   “oracle 普遍存在”结论。
3. 建立 paper-v2 实验记录 schema、校验器、API 提供方证据等级和失败分母规则。
4. 修复当前完整测试中的六项身份漂移问题，保留旧冻结身份。
5. 运行 60–80 个配对任务的中型证伪门禁；门禁通过后才设计正式样本量与 API 预算。
6. 依次完成公共基准、独立盲测、自适应攻击、统计、论文写作与完整性复核。

## Acceptance Criteria

- paper-v1 冻结证据和历史 E0–E17/V2 证据哈希保持不变。
- 文献矩阵覆盖至少 30 篇，所有“前沿/同行评审/预印本”状态有可核验来源。
- online-state 审计登记至少 20 个候选；结论只使用已完成源码审计的条目。
- paper-v2 记录明确包含 authorization regime、在线可见字段摘要、ASK 原因、
  unsafe effect、task completion、operational status 和 provider attestation。
- 无法验证模型身份或提示是否被中转站改写的 API 结果只能是 diagnostic。
- 中型门禁必须同时检查安全增益、TCR −5pp 非劣边界、full 对 policy-only 增益、
  deny-all 退化和 operational failure。
- 所有失败、超时、拒答和解析错误保留在 intention-to-treat 分母。
- 完整验证通过前，功能状态保持 `in_progress`。

## Verification

- JSON/schema 和文献/源码审计登记表结构检查。
- paper-v2 契约单元测试、非 oracle 投影测试、指标语义 golden tests。
- 受影响模块的 Ruff/compileall/pytest。
- `python scripts/audit_project_conventions.py --check`。
- `powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/verify.ps1`。

## External Dependencies

- 至少一个官方 API 或具有可审计上游身份、请求 ID、无提示改写声明的网关。
- 第 8 周前确定独立盲测保管人；当前尚未满足。
- JISA 投稿时的 SCIE/JCR Q2 状态须由学校或 Clarivate 正式来源复核。

## 2026-07-23 Dual-provider Full-matrix Budget Checkpoint

- 用户批准 DeepSeek 声明余额 CNY 30 和 Gemini free tier 用于项目，并明确要求
  DeepSeek 不缩成小规模子集。每个选定模型的目标均为完整 480 项；分块只用于
  resume 和预算检查，不能改变冻结分母。
- DeepSeek CNY 27 abort ceiling/CNY 3 reserve 按实际 cache hit/miss/output usage
  结算；全量可行命中阈值约为 87.7165%。每次请求前必须验证下一最坏请求余量，
  500,000 observed input token 后还必须检查全量投影。
- Gemini 只允许 free tier，paid-tier ceiling 为 USD 0；active RPM/TPM/RPD 仍需
  由 AI Studio 当前项目页面记录。本地 batch caps 不替代 provider quota。
- 两家均为 concurrency=1、automatic retries=0、first 429=pause，并且禁止同一
  模型矩阵自动跨 provider fallback。仅发送 synthetic/public non-sensitive
  payload，所有 provider tools 和真实外部 effects 关闭。
- 预算批准不是 execution authorization。正式运行仍等待新的 hash-bound
  execution manifest、executor qualification、logging redaction review 和
  missing-request-ID 证据规则。

## 2026-07-24 Official-provider Executor Binding Task

### Goal

在不修改 hash-bound paper-v1、medium plan v1/v2 或历史结果的前提下，新增
paper-v2 官方 DeepSeek/Gemini 单次调用 transport、逐请求身份/usage 收据、
append-only call ledger 和 v3 preflight identity。该层必须能够被未来六条件
正式 executor 复用，但当前不得把 transport qualification 写成效果结果。

### Allowed files

- `experiments/paper_v2/official_provider_executor.py`
- `experiments/paper_v2/provider_execution_gate.py`
- `protocols/paper_upgrade_v2/provider_executor_qualification_v1.json`
- `protocols/paper_upgrade_v2/medium_execution_manifest_v3_preflight.json`
- 对应 `tests/unit/test_paper_v2_*`、Harness verifier 和非冻结状态文档

### Forbidden files and actions

- 不修改 `medium_execution_plan_v1.jsonl`、`medium_execution_plan_v2.jsonl`、
  两个既有 manifest 或 paper-v1 冻结。
- 不读取/打印 `config/project.local.env`，不把 API key、Authorization header、
  prompt/response 正文写入 qualification/preflight。
- 不进行模型/API 请求，不生成正式效果记录，不注册六条件 executor，不提升
  connectivity diagnostic 或 Q2 科学完成度。

### Acceptance criteria

1. 真实 transport 需要显式 network consent；注入 transport 可进行零网络资格测试。
2. 每次调用恰好一次、无 retry、无 tools/provider effects；429 返回 pause 语义。
3. DeepSeek 强制 cache hit/miss/output usage 并连接 CNY 27 fuse；Gemini 强制
   free-only、本地 batch cap 和零付费。
4. 收据记录 official endpoint、exact model、request/response ID（若存在）、
   payload/response hash、token 和成本，但不包含 key、headers 或正文。
5. append-only ledger 拒绝 identity drift、重复终态、自动 retry 和跨 provider
   fallback；仅允许 429 后显式 manual same-provider resume。
6. v3 preflight hash-bind v2 plan、budget/safety policies、transport/ledger code、
   schema 和 provider model identity；`formal_execution_authorized=false`。
7. 聚焦测试、Ruff、compile、conventions 和完整 Harness 通过。

### Outcome — 2026-07-24 01:30 +08:00

- 七项工程验收已满足。DeepSeek/Gemini transport、usage/budget hook、credential-
  redacted receipt、append-only ledger 和 v3 execution preflight 已实现并冻结；
  本任务未读凭据、未联网、未产生正式结果。
- receipt 到 experiment-record 的分级已绑定：injected=`local_qualification`；
  official exact model + request/response 双 ID=`formal_candidate`；缺 request ID
  =`diagnostic_only`。因此历史 connectivity smoke 不会被提升。
- v3 仍为 `formal_execution_authorized=false`、`gate_pass=false`。六条件 executor、
  日志脱敏复核、Gemini quota 快照和 live 双 ID qualification 是剩余门禁。
- 执行器测试 13/13、paper-v2 112/112、Ruff、compile、冻结复现、conventions
  12/12 和完整 Harness 通过；全量为 883 passed、1 skipped、3 warnings，
  `Verification failed=0`。
- 用户要求优先使用的 `LFischl` 环境已补装 pytest；它是 Python 3.9，仅能运行
  本模块隔离测试/Ruff。完整仓库使用 Python 3.13.5，最低版本文档修正为 3.12+。

## 2026-07-24 Six-condition Executor Shell and Redaction Task

### Goal

在任何真实 provider call 前，为六个核心条件建立统一、可注入的 executor shell。
shell 只能向在线 runtime 传递 frozen online state 和最小调度身份，不能传递
evaluation case type、primary eligibility 或任何 offline answer；所有 prompt/
response/observation 正文在进入 experiment record 前必须转换为 hash/长度证据。

### Allowed files

- `experiments/paper_v2/formal_condition_executors.py`
- `protocols/paper_upgrade_v2/formal_condition_executor_qualification_v1.json`
- `experiments/paper_v2/provider_execution_gate.py` 和 v3 preflight 的新冻结版本
- 对应 unit tests、Harness verifier 和非冻结状态文档

### Forbidden actions

- 不读取凭据、不联网、不加载 PromptGuard 模型、不执行 VIGIL constraint provider。
- 不运行任何 480-item work item 的真实模型条件，不持久化 stub experiment record。
- 不把 injected runtime shell 资格测试称为正式条件效果或 live dependency 资格。
- 不修改 paper-v1、v1/v2 medium plan/manifest 或历史输出。

### Acceptance criteria

1. 六条件均注册，重复/缺失条件 fail-closed。
2. runtime context 不含 `evaluation_case_type`、offline evaluator、primary eligibility、
   source path/line 或 result fields。
3. 初始在线状态必须与 frozen digest 和条件 profile 精确匹配。
4. 多步事件不允许保存 prompt/response/observation/headers/credentials 正文；保留
   action arguments、content hashes、决策码和执行状态，并做 secret-pattern scan。
5. case-level `initial_guard_decision` 明确定义为首个 parsed proposal 的决策；
   `ASK` 在本阶段是 `pending`/不执行，所有后续 step 仍进入 runtime events。
6. 12 个 benchmark×condition 组合在内存组装并通过 experiment-record contract；
   result tier 必须是 stub，持久化结果、API/model call 均为 0。
7. qualification/preflight 可复现，测试、Ruff、compile、conventions 和 Harness 通过。

### Outcome — 2026-07-24 02:15 +08:00

- 七项验收已完成。六条件均通过统一 dispatcher 注册；online runtime 只接收最小
  identity/call cap/frozen online state，禁止 evaluator、primary eligibility、
  source/result 字段进入。
- 多步事件在 experiment-record 边界前完成 secret scan 和内容最小化；原始 prompt、
  messages、response、observation、headers、credentials 均不持久化。首个 parsed
  proposal 唯一定义 case-level initial decision，`ASK` 为 pending/不执行。
- 两个基准×六条件共 12/12 injected no-effect 资格通过；所有 stub record 仅在内存
  组装，持久化记录、正式结果、网络/API/model calls 均为 0。
- v3 preflight 已重新绑定模块与资格文件并保持 `gate_pass=false`。live provider、
  PromptGuard、VIGIL、isolated effect、offline evaluator、真实日志持久化路径、
  Gemini quota 与 live 双 ID 仍未资格化。
- 聚焦 21/21、paper-v2 120/120、LFischl Ruff、compile/syntax/JSON/conventions
  及完整 Harness 均通过；全量为 891 passed、1 skipped、3 warnings，
  `Verification failed=0`。本成果只提升工程就绪，不产生论文效果结论。

## 2026-07-23 Python 3.13.5 Dependency Installation Checkpoint

- 用户要求把缺失项目依赖装入 Python 3.13.5。按仓库 core/dashboard requirements
  审计后，声明依赖均已存在，唯一明确缺失的开发工具为 Ruff。
- 安装 Ruff 0.15.22，并选择 Pillow 10.4.0 满足项目 Streamlit 与现有
  moviepy/python-fx 约束。由于 F 盘 base site 不可写，新增/调整包位于该解释器
  可见的 Python313 user site。
- 不安装 transformers 到此环境：本项目 PromptGuard 的固定模型运行使用单独精确
  环境；当前全量项目测试不要求在共享 3.13 base 中重复安装该大型可选依赖。
- `pip check` 诚实保留 pdfplumber/PySSTV 两个非项目 Pillow 12.2 约束冲突；
  本任务未获得修改这些工具的授权。项目导入、Ruff、paper-v2 120/120 和全量
  Harness 891/892（1 skipped）均通过。

## 2026-07-23 Formal Record Persistence Qualification Task

### Goal

把六条件 shell 的已脱敏 execution result 接入可恢复的 append-only
experiment-record ledger，证明正式落盘边界能检测身份漂移、重复终态、截断/
篡改和 raw/secret 内容，同时保持 operational failures 在 ITT 中。

### Allowed files

- `experiments/paper_v2/formal_record_store.py`
- `protocols/paper_upgrade_v2/formal_record_store_qualification_v1.json`
- `experiments/paper_v2/provider_execution_gate.py` 和重新生成的 v3 preflight
- 对应 paper-v2 unit tests、Harness verifier 和非冻结状态文档

### Forbidden actions

- 不读取凭据、不联网、不调用模型、不加载 PromptGuard/VIGIL live runtime。
- 不写入 `outputs/paper_upgrade_v2/` 正式结果根；qualification 只能使用自动清理的
  临时目录，不得遗留 stub record 文件。
- 不修改 paper-v1、medium plan v1/v2、既有 manifest v1/v2 或历史证据。
- 不把 transient stub disk replay 称为正式记录、provider identity 或科学结果。

### Acceptance criteria

1. 每条 ledger entry 绑定 execution identity、work key、run ID、连续 sequence、
   experiment record、sanitized runtime events 和各自 SHA-256。
2. 追加前复验已有完整链；重复 work/record、未知 work、identity/run drift、
   record/event hash drift、work metadata drift 和截断 JSON 均 fail-closed。
3. runtime events 和整个 entry 通过禁止字段与 credential-pattern scan；原始 prompt、
   messages、response、observation、headers、credentials 不得落盘。
4. live 模式 completed/refusal 只接受 `formal_candidate`；operational failure 可用
   `diagnostic` 证据但必须保留在 ITT；stub 只允许显式 qualification 模式。
5. 12 个 benchmark×condition stub entries 在临时目录依次写入、每次回读复验，
   最终完整恢复一致；临时目录退出后文件不存在，仓库记录和正式结果为 0。
6. qualification 和 v3 preflight 可复现；聚焦测试、Ruff、compile、conventions
   和完整 Harness 通过。

### Outcome — 2026-07-23 23:30 +08:00

- 六项验收均完成。新增 append-only entry 同时绑定 experiment record 与 sanitized
  runtime events，并验证 execution/work/run/record identity、连续 sequence、
  work metadata 和 record/event/argument/entry hashes。
- 追加逻辑在写入前复验完整已有链和候选链，写入后 flush+fsync；恢复路径对重复
  终态、空行、截断 JSON、身份/元数据/哈希漂移和 raw/secret 内容 fail-closed。
- live 成功/拒答只接受 formal-candidate；diagnostic operational failure 可以持久化，
  但 schema 强制其保守留在 ITT。stub 只允许显式 qualification mode。
- 自动清理临时目录中完成 12 次逐条 append/replay，最终 12/12 恢复，raw markers
  未出现，退出后 ledger 文件不存在。仓库记录、正式结果、API/model calls 为 0。
- v3 preflight 绑定新模块/资格证据，blockers 从 4 降为 3；仍未授权任何矩阵调用。
- record-store 7/7、相关 28/28、paper-v2 127/127 和 Ruff/compile/JSON/syntax/
  conventions 全部通过；完整 Harness 为 898 passed、1 skipped、3 warnings，
  `Verification failed=0`。该成果只提升工程就绪，不支持效果结论。

## 2026-07-24 Live Six-condition Dependency Composition Task

### Goal

在既有 `ConditionExecutorShell` 和 append-only formal record store 之间建立可替换
provider、controller 与 isolated effect backend 的 live 组合层。先以注入客户端和
公开固定依赖执行零网络资格；只有真实 PromptGuard/VIGIL/provider/evaluator 身份均
满足后，才能由后续 gate 允许正式 480 项运行。

### Allowed files

- 新增 `experiments/paper_v2/live_condition_runtime.py`
- 新增 `tests/unit/test_paper_v2_live_condition_runtime.py`
- 新增 `protocols/paper_upgrade_v2/live_condition_runtime_qualification_v1.json`
- 更新 `experiments/paper_v2/provider_execution_gate.py`、v3 preflight、Harness
  verifier 和非冻结状态文档

### Forbidden files and actions

- 不修改 paper-v1、v1/v2 medium plan/manifest、既有正式/diagnostic 输出。
- 不读取或输出 `config/project.local.env`，不调用 DeepSeek/Gemini 或任何网络模型。
- 不加载或执行未知本机工具，不执行真实邮件、支付、shell、浏览器、生产 API、
  非 sandbox 文件或其他外部 effect。
- 不将 injected provider、fixture detector、固定 VIGIL constraints 或内存 effect
  的资格结果提升为 live dependency qualification、正式结果或科学效果证据。

### Acceptance criteria

1. provider 输出仅接受精确 JSON object proposal；拒绝 Markdown、额外文本、
   非 object arguments、未知工具、重复键和超出长度。
2. no-defense/safe/PromptGuard/M3 条件最多 8 次 provider call，VIGIL 最多 16 次；
   达上限后 fail-closed，不允许隐式 retry。
3. 六条件分别路由 unmonitored、spotlighting、detector-only、VIGIL、
   M3 policy-only 和 M3 full；在线上下文不接收 evaluator/gold 字段。
4. PromptGuard 只作为 detector gate；VIGIL 走固定官方源码 adapter；M3 两条件
   调用现有 runtime monitor，且 full 额外绑定 provenance/temporal/dataflow/
   confirmation 模块，不以新伪实现代替。
5. effect backend 仅允许 M3 sandbox fixture 或 AgentDojo in-memory copy；未知/
   external effect fail-closed，ASK 不执行。
6. 两个 benchmark×六条件共 12 个组合以注入 provider 和 no-effect/in-memory
   backend 通过控制流资格；网络/API/model call、仓库 experiment record 和正式
   结果均为 0。
7. 资格 artifact 明确逐依赖区分 source-backed、fixture-qualified、unqualified；
   provider gate 只有在全部 live 依赖证据满足时才可移除对应 blocker。
8. 聚焦测试、全部 paper-v2、Ruff、compile、JSON、conventions 和完整 Harness
   均通过。

## 2026-07-23 Implementation Checkpoint

- Plan item 1 complete：文献矩阵 34 项，同行评审/预印本状态和直接竞争边界已记录。
- Plan item 2 framework complete but evidence incomplete：22 个 audit unit 已登记，
  19 个 discovery HEAD 已解析，实际 completed audit 为 0。
- Plan item 3 complete：experiment record schema、在线投影/禁止字段校验、provider
  attestation、ASK 状态机、ITT outcome 与统一 metric semantics 已实现。
- Plan item 4 complete without rewriting history：原 6 个失败现验证历史身份漂移必须
  fail-closed；E17 单测环境快照已隔离。旧 freeze、预检产物和输出不变。
- paper-v2 focused tests 25/25；独立和 Harness 内全量测试均为
  796 passed / 1 skipped；最终 `Verification failed=0`。
- Plan item 5 未启动：中型 gate 已写入机器可读协议，但因模型、case selection、
  VIGIL/DRIFT 适配与成本上限未冻结，`start_authorized=false`。
- Plan item 6 未启动：公共正式结果、独立盲测、自适应攻击、统计和论文仍待后续门禁。

## 2026-07-23 80% Evidence Sprint

用户要求按已批准的 SCI Q2 计划尽量推进到 80% 以上。本阶段将“完成”定义为有
当前工作树证据支持的研究交付物，而不是文档占位、smoke 数量或主观百分比。

### Allowed additions

- `external/paper_v2_audits/`：只读固定的公开官方源码检出，用于源码审计。
- `protocols/paper_upgrade_v2/audits/`：逐审计单元的最小证据包。
- `protocols/paper_upgrade_v2/`：完成度台账、中型案例冻结、统计/盲测/自适应协议。
- `experiments/paper_v2/`、`schemas/paper_v2/`、对应 `tests/unit/test_paper_v2_*`。
- `docs/research/paper_v2/`：结果就绪的 Methods、claim–evidence ledger 和论文骨架。

### Hard evidence rules

- 源码审计必须绑定官方 URL、40 位 commit、入口文件/行号和文件 SHA-256。
- 单人完成的源码审计不得伪装成双人复核；在独立复核前只支持限定版本、限定路径
  的工程发现，不支持“领域普遍”主张。
- 没有可审计 provider、固定 case 和成本上限时，不运行收费 API。
- 没有独立保管人时，只能生成 content-free custody kit，不得生成或查看伪盲测标签。
- 没有真实正式结果时，论文 Results 只保留表结构、统计契约和明确的 pending 标记。

### Sprint acceptance evidence

1. 至少 20 个 audit unit、至少 10 个官方 artifact 生成完整证据包并由统一校验器通过。
2. 60–80 个中型任务在结果查看前固定，覆盖攻击、良性工具、良性无工具和上下文依赖。
3. 结构化基线通过公共 paper-v2 adapter contract；若上游缺少可运行接口，保留
   失败/不可比原因而不伪造忠实复现。
4. 统计流水线实现 Wilson、exact McNemar、cluster bootstrap、Holm、功效估算和
   预注册门禁判定，并有 golden tests。
5. 公共基准、盲测保管和自适应攻击具备可执行、可冻结、fail-closed 的本地工具。
6. Methods、结果表壳、claim–evidence ledger、引用完整性状态和 Devil’s Advocate
   风险表可由当前证据重建。
7. 完整 Harness 通过；外部人工/API/正式结果缺口按权重留在完成度分母。

### Sprint outcome — 2026-07-23 16:35 +08:00

本轮七项工程验收均已实现，但科学结论门禁尚未满足：

1. 20/22 个 audit unit、14 个官方 artifact 已生成完整证据包并通过统一
   `--verify-only` 复验。观察为 9 个 `no_online_gold_observed`、9 个
   `not_a_runtime_guard`、1 个 path-dependent、1 个 inconclusive；第二复核为 0，
   因此不能形成领域级 oracle claim，默认工作标题改为中性版本。
2. 72 个结果盲中型任务已固定，组成 36/24/12，包含 25 个上下文依赖任务。
   6 个核心条件为 432 条主记录，24 个 case 的 4 类 regime probes 为 48 条，
   合计 480 条待执行记录。
3. VIGIL 和 DRIFT 官方固定源码 adapter 通过零模型调用构造/归一化资格检查。
   `formal_admission=false`，不得把接口资格写成效果复现。
4. 统计流水线和 golden tests 已覆盖 Wilson、exact McNemar、10,000 次 cluster
   bootstrap、Holm、功效估算、ITT 和冻结门禁；缺少真实矩阵时只输出
   `results_pending`。
5. 正式公共计划固定为 6,873 条 case-condition 记录；自适应预算上限 75,000
   attacker queries；独立盲测包有 600 个分层 slot，但没有内容、标签或 custodian。
6. Methods、pending-only Results、claim ledger 和 Devil's Advocate 审查已完成。
   效果、泛化、自适应鲁棒性和独立盲测 claim 均保持 pending/forbidden。
7. 首轮 Harness 为 824 passed、1 skipped、3 warnings、failed=0；状态同步后的
   完整复验收集新增门禁测试，为 825 passed、1 skipped、3 warnings、failed=0。

完成度必须分层报告：

- engineering/research readiness: 85%
- scientific evidence completion: 31%
- submission readiness: 38%

硬外部门禁为：可审计 provider/model 身份、明确硬成本上限和未来独立 custodian。
前两项未固定前不得启动中型 480 条；中型门禁未通过前不得启动 6,873 条公共计划；
第三方未建立保管链前不得声称 independent blind。没有发生 API/模型调用。

## 2026-07-23 Offline Provider/Execution Checkpoint

- 22/22 online-state audit units 已完成。20 个 unit 绑定官方源码；Task Shield
  明确标记为本地论文复现且官方代码来源未建立；SIREN 同样保留官方源码缺失证据。
  没有独立第二复核，因此只允许版本/路径限定结论。
- 冻结未批准的正式候选：OpenAI official API / `gpt-5.6-terra`。该选择只用于
  预算估算，不代表用户批准或 runtime identity 已验证。
- `provider_cost_preflight_v1.json` 对 480 项给出 4,416 calls、
  34,407,984 input tokens、2,260,992 output tokens 和 USD 119.93484 的
  无折扣保守上界。hard limit 仍为 null，gate 保持 false。
- `medium_execution_plan_v1.jsonl` 固定 432 个 primary + 48 个 regime-probe
  工作项；manifest 哈希绑定所有关键输入并声明结果/网络调用均为 0。
- 执行恢复采用 append-only event ledger：已终态 work key 不重复，started-only
  可用相同 key 重试，identity drift/重复终态拒绝，operational failure 留在 ITT。
- content-free provider smoke receipt 校验器已就绪；它不联网、不接受凭据 header，
  只在未来人工授权的 smoke 后验证 official endpoint、model、IDs 和 usage。
- 当前 completion scorecard 为 engineering 90%、scientific evidence 32%、
  submission 39%。只有工程基础超过 80%；论文证据与投稿条件远未达到 80%。

## 2026-07-23 Condition-Specific Runtime And Provider-Safety Checkpoint

- 完整性审查发现 v1 execution ledger 把 case-level source projection digest
  复制给所有条件和授权 regime，不能证明每个 Guard 实际看到的 policy/detector
  状态。v1 在任何真实运行前被保留并标为 superseded，没有删除或改写。
- 新的 `medium_execution_plan_v2.jsonl` 对 480 个工作项分别冻结
  `source_projection_digest` 与 `initial_online_visible_field_digest`；最终 record
  digest 还必须覆盖全部 runtime visibility events。
- `exact_gold` 不再伪装成 trusted manifest，而明确序列化为
  `source_class=evaluator_derived_authorization`，并强制排除 primary endpoint。
- AgentDojo 固定在干净 commit
  `089ed468cf3ed0322acc66b0211f26d9d90dbf60`。无网络注入执行器在内存中验证
  480/480 条记录、六条件调度、ASK 状态机、operational failure 保守 ITT 和
  record schema；stub 记录落盘数为 0。
- 根据用户明确安全要求，新增 DeepSeek/Gemini 官方配置槽和 fail-closed provider
  safety policy。模型输出只能是 untrusted proposal；effect 仅允许
  `sandbox/public`、`example.test`、`/mock/` 或无外部连接的 AgentDojo 内存副本。
  host 命令、真实邮件/支付、生产/私有 API、凭据、浏览器/computer-use 和未知
  effect 均 DENY；非 stub executor 缺 safety receipt 即拒绝。
- 34 项文献矩阵现在生成可复验 citation integrity manifest：22 项同行评审、
  12 项预印本；十项前沿核心工作的发表状态被机器锁定。JISA 官方 scope/Guide
  清单已记录，SCIE/JCR Q2 仍必须由机构在投稿时核验。
- 分层完成度为 engineering 93%、scientific evidence 32%、submission 41%。
  真实 API smoke、480 正式结果、公共/自适应结果、独立保管人和机构 JCR 仍未完成。
- 新增 focused tests 18/18 与 standalone Ruff 通过；完整 Harness 为
  `858 passed, 1 skipped, 3 warnings in 483.60s`，最终
  `Verification failed=0`。

## 2026-07-23 DeepSeek/Gemini Connectivity Checkpoint

- 用户明确授权执行一次双供应商连通性 smoke。命令只发送固定公共合成文本，
  每家一次、`max_tokens=8`、timeout 60 秒、无重试、无工具声明和无外部 effect。
- 执行前，本地配置门禁显示 DeepSeek/Gemini key 均为 `set_redacted`，consent
  正确，`config/project.local.env` ignored=true、tracked=false，仓库跟踪文件中
  secret hits 为 0。凭据值和响应正文均未进入控制台或证据文件。
- DeepSeek 官方 `/chat/completions` 与 Gemini 官方
  `/v1beta/openai/chat/completions` 均 HTTP 200；returned model 分别精确匹配
  `deepseek-v4-pro` 和 `gemini-3.6-flash`。报告用量合计 68 tokens。
- 两个响应均有 response ID，但未从检查的响应头观察到 request ID。固定的
  8-token 上限也未产生精确 `SAFE`，所以只记录
  `completed_two_provider_connectivity_diagnostic`；不支持指令遵循、正式身份
  attestation、正式 provider admission 或任何论文效果 claim。
- 脱敏证据：
  `protocols/paper_upgrade_v2/provider_connectivity_smoke_v1.json`。
  480 条中型账本保持 pending；必须先解决正式 request-ID receipt、硬成本上限与
  用户执行批准，才能启动真实中型矩阵。

## 2026-07-24 Live Dependency And Official Identity Gate Checkpoint

- 六条件 runtime 的离线依赖已经全部真实接入：固定 PromptGuard 模型推理、
  AgentDojo 官方环境/utility/security checker、M3 离线 evaluator、exact-gold
  ablation，以及 VIGIL 官方 generator/parser provider bridge。资格过程无网络、
  无真实 effect、无 evaluator/gold 在线泄漏。
- 用户授权的 identity qualification 向两家官方端点各发一条固定合成请求，
  `max_tokens=16`、temperature 0、无 tools、无重试、无 fallback。DeepSeek 精确
  返回 `deepseek-v4-pro`、response ID 和完整 usage，但没有 request-ID header；
  Gemini 首次尝试即 `ProviderPausedError`。
- 证据按冻结规则保留：DeepSeek 为 diagnostic、Gemini 为 failed single attempt，
  两家 formal-candidate 数为 0。artifact 不保存 credential、prompt、response、
  header 或错误正文，也不能进入任何安全/效用表。
- v3 preflight 现在只剩两个 blocker：Gemini active quota snapshot；完整 live
  exact-model/request+response-ID 证据。`execution_authorized=false`、
  `formal_execution_authorized=false`、`gate_pass=false`。
- 验证为 provider 聚焦 16/16、paper-v2 160/160、完整 Harness 929 collected、
  928 passed、1 skipped、`Verification failed=0`。当前工程/科学/投稿就绪度为
  99%/32%/44%；项目仍为 `in_progress`，不能把工程 99% 写成论文完成 99%。

## 2026-07-24 DeepSeek V2 Request-Chain And Record-Store Checkpoint

- 项目所有者明确批准 DeepSeek 使用以下完整请求链：传输前冻结本地 request
  ID 与 canonical payload SHA-256，started event append/flush/fsync 后才允许
  transport，再绑定官方 response ID、精确 returned model 与 hash-chain terminal。
- 激活仅适用于 DeepSeek 的新 v2 请求。v1 schema、旧 smoke 和历史证据均不
  追溯升级。
- 用户提交的 Gemini 3.6 Flash 配额截图已按 SHA-256 绑定，记录 1000 RPM、
  2000000 TPM、10000 RPD；截图文件、project ID、key 均未入库，free-only /
  USD 0 规则不变。
- 唯一一次新的 DeepSeek 安全资格请求完成两事件闭环。随后本地校验器因 stripped
  与 raw response hash/bytes 口径不一致而拒绝 artifact write；未重试。使用
  已 fsync 的完整链进行零网络恢复，明确不提供 response 内容、usage、latency
  或完整 receipt，仅认定 identity qualification，不进入效果表。
- 新增 `experiment_record_v2`、provider-trace attestation schema 与独立
  append-only record-store v2。离线资格写入 2 条瞬态记录，完整前向 hash-chain、
  fsync、逐次全链复验和 2 个负例全部通过，项目 formal results 仍为 0。
- v3 preflight 只剩 live runtime per-call v2 trace/record 接线 blocker；
  `gate_pass=false`、`formal_execution_authorized=false`。不需要额外 API
  qualification call 才能完成该工程门禁。
- 聚焦 paper-v2 测试 184/184，Ruff、PowerShell/Bash syntax 均通过。科学证据
  完成度仍为 32%，因为中型、公共、自适应和独立盲测结果均为空。
- 最终全库 pytest 为 955 passed、1 skipped、3 warnings（374.88 秒）；完整
  Harness 481 秒退出 0，`Verification failed=0`。

## Active 2026-07-24 Live Runtime V2 Wiring

- 本阶段只关闭剩余工程 blocker：每次 provider call 先写 fsync precommit，
  success 绑定 activated trace，failure 保留 open commitment，并把全部调用按
  call index 组成一个 record-level bundle。
- 六条件路径必须覆盖普通 agent step 与 VIGIL constraint generation；不得只保留
  最后一次 response ID。
- 完整 bundle 的记录上限为 `formal_candidate`；含 failed/open call 的记录必须为
  `diagnostic` 且留在 ITT。两者都必须进入独立 v2 append-only store 资格测试。
- 本阶段不启动 480 项正式 API 矩阵，不修改任何 v1/历史冻结，也不把零网络 fixture
  称为科学效果证据。

## 2026-07-24 Live Runtime V2 Wiring Result

- 已新增 record-level ordered provider trace bundle；它保留所有 started/terminal
  hash-chain rows与逐调用 activated attestation，不再只保存最后一个 response。
- 普通路径 1 次调用、VIGIL 路径 2 次调用均通过完整链资格；agent-loop 429 与
  VIGIL-preparation 429 均保留 open precommit、无自动重试，并以 diagnostic /
  `unsafe_effect_itt=true` 写入瞬态 v2 store。
- Experiment-record schema 更新到 2.1；尚未使用的 2.0 单 attestation 形状被明确
  supersede，paper-v1、历史 freeze、旧 smoke 均未修改或升级。
- 零网络端到端资格共 4 个场景、4 条瞬态 record，hash-chain 全量复验通过；
  项目 formal record、正式结果、网络调用和外部 effect 均为 0。
- preflight 当前 blocker 已从“runtime wiring”收缩为“run-specific admission
  manifest + 一条有界官方 DeepSeek pilot 的人工证据/成本复核”。完整矩阵继续
  fail-closed。

## 2026-07-24 Official DeepSeek Single-Pilot Result

- 项目所有者明确批准当前 23-input candidate；active manifest 将批准语句摘要、
  candidate/scope 摘要、预算、安全策略和唯一 work item 一并冻结。
- admission 无凭据预检通过后，控制器仅调用一次官方
  `deepseek-v4-pro`。无重试、无 Gemini fallback、无 provider tools、无真实
  外部 effect。
- 唯一记录正常完成：278 prompt cache-miss tokens、0 hit tokens、136 completion
  tokens、414 total tokens，累计成本 CNY 0.00165，未接近 CNY 27 中止线。
- post-pilot reviewer 的 15/15 检查全部通过；良性任务完成且
  `unsafe_effect=false`，安全回执为 sandbox-only。
- 该记录仍是 `formal_candidate`，没有进入论文结果；matrix/result authorization
  均为 false。单条良性 no-defense 结果不能解锁 C06–C10。
- 用户随后授权未来继续受控调用 DeepSeek 和 Gemini。后续迭代必须建立新的分阶段
  freeze/admission，继续遵守 DeepSeek 成本熔断、Gemini free-only、无自动重试和
  禁止危险/外部操作边界。
- 保守完成度更新为 engineering 99%、scientific evidence 33%、submission 45%；
  任务继续 `in_progress`。
- 最终回归：focused 31/31、paper-v2 204/204、Ruff、conventions 12/12 均通过；
  完整 Harness 为 975 passed、1 skipped、3 个已知依赖 warning（317.96 秒），
  历史/冻结证据通过且 `Verification failed=0`。

## 2026-07-26 v7 Abort, v8 Canary And Stage-Report Checkpoint

- v7 首次 canary 在两个官方 DeepSeek 响应后由 v3 evaluator 失败关闭。根因是
  controller 只在构造 dispatcher 时临时绑定 adapter，而 effect backend 在运行期
  延迟读取模块全局。v7 证据冻结为 0 records、1 open attempt、2 responses、
  1 trace；不重试、不补写、不进入论文结果。
- v8 使用新 run/matrix identity，把 v3 adapter 绑定覆盖完整 `_execute` 生命周期，
  并加入 delayed-backend 回归。新 qualification、candidate、canary admission、
  continuation admission 与 result gate v5 均独立版本化和哈希冻结。
- 唯一 v8 六条件 canary 为 6/6 `formal_candidate`、13 个官方响应、
  0 diagnostic、0 operational failure、0 retry/fallback/tools/external effect，
  增量成本 CNY 0.0077078。技术 review 保持
  `scientific_outcomes_reviewed=false`。
- v8 当前为 6/480、474 pending、0 open。continuation 已单独准入，但 result 和
  analysis admission 为 false。pre-v8 完整 Harness 的唯一失败是过时的 v7
  freshness 测试；替换后的永久 abort/no-network 专项测试 1/1 通过，完整绿色
  Harness 仍是继续执行的硬门槛。
- 按用户优先级暂停 474 项续跑并交付
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-26.docx`。
  报告含 4 张图、16 张表和从 DeepSeek 正式矩阵到 Gemini、公共基准、自适应
  攻击、独立盲测、统计与投稿的详细路线。结构、表格几何、a11y、占位符、密钥
  模式和图片人工检查通过；环境缺少 LibreOffice，未宣称整页渲染 QA 通过。
- 下一步仅为：先完整 Harness 至 `Verification failed=0`，再恰好一次执行 v8
  continuation；之后先做 outcome-blind result-gate review，独立准入后方可分析。

## Active 2026-07-26 SCI Q2 80% Evidence Completion Sprint

### Goal

把“科学证据完成度”而非单纯工程就绪度尽量推进到 80% 以上，并保留可审计、
可复现、失败留在 ITT 的证据链。中型正式矩阵、跨模型/外部有效性、自适应攻击、
论文结果与完整性检查共同构成分母。

### Execution order

1. 运行唯一完整 Harness；最终必须为 `Verification failed=0`。
2. 绿色后消费已冻结 v8 continuation admission，恰好一次运行剩余 474 项。
3. 运行 outcome-blind result gate v5，先判定身份、trace、budget、failure 和
   effect-isolation 完整性。
4. 只有独立 result admission 通过，才运行预注册统计、图表和效果解释。
5. 根据完成度缺口再选择 Gemini 第二模型、公共基准和自适应攻击；不得并发供应商，
   不得让诊断证据冒充正式结果。
6. 更新论文、claim–evidence ledger、AI research failure-mode checklist 和最终
   完成度审计。

### Safety and immutability

- API 输出只是不可信 proposal；provider tools、external connectors、真实邮件/
  支付/host command/生产 API/非 sandbox 文件 effect 均关闭。
- 不读取、打印或复制密钥；API 客户端只通过既有 ignored local config 获取凭据。
- 不自动 retry；429、credit/quota、identity-chain、append-only 或 safety
  异常立即停止该 run 并保留证据。
- v1–v8 已冻结源码/协议/准入/账本、paper-v1 与历史证据不得原位修改。

### Acceptance evidence

- 完整 Harness stdout/stderr 与最终 `Verification failed=0`。
- v8 status/record/trace/budget/canary/continuation chain 的完整哈希复验。
- result-gate review 在 outcome-blind 模式产生，result admission 单独冻结。
- 统计输出包含原始分子/分母、Wilson CI、exact McNemar、10,000 次 cluster
  bootstrap、Holm 与 TCR −5pp 非劣门禁。
- 完成度审计不得把未完成独立盲测、公共矩阵或第二模型写成完成。

## 2026-07-28 Public-v1 Abort And Public-v2 Remediation Checkpoint

- Owner-approved Public-v1 primary execution stopped locally twice: first
  before the attempt loop because the selected Python lacked frozen
  PromptGuard packages, then after one started event because the medium
  AgentDojo resolver did not index public-plan work keys.
- LFischl Python 3.13.5 now has the required Transformers/Tokenizers/
  Safetensors versions and passes local CUDA PromptGuard benign/injection
  probes. No provider request was made by either Public-v1 attempt.
- Public-v1 is immutable and non-resumable at one open attempt, zero terminal
  attempts, zero records/budget events/traces/provider requests, CNY 0 and
  zero formal results. A versioned abort review binds the admission, logs and
  hash-valid attempt ledger without opening scientific outcomes.
- Public-v2 reconstructs AgentDojo bindings from each public row's frozen
  source reference, retains all 6,873 result-blind work items, and uses fresh
  run/output/execution identities. Candidate canonical SHA-256 is
  `a17ab0926c0003e953b85834b8728a8ac98e360b684780b7fa98f10b9c07250b`;
  execution/result authorization remains false.
- Focused regression passes 11/11 in 1,164.68 seconds with empty stderr;
  Ruff and all offline artifact reproductions pass. A new current-worktree
  full Harness and fresh exact-command owner confirmation are mandatory before
  Public-v2 can create an admission or access credentials/network.
- Evidence score remains 753/1200. Engineering remediation and zero-call
  failure evidence are not counted as public benchmark results.

## 2026-08-05 Fresh Harness v5 Failure Freeze And v6 Scope

- The single-use v5 run naturally completed with directly observed child exit
  1. Pytest passed 1531/1531 collected tests (one skip), while the first
  AgentDojo-dependent evidence replay failed at `git rev-parse HEAD`; two later
  evidence processes ended in the same Windows failure class. No provider or
  network execution was authorized.
- Failure review v5 freezes the complete v5 terminal chain. A separate sanitized
  qualification records the sandbox ownership rejection and proves the exact
  frozen checkout is readable when `safe.directory` is supplied only through
  the current process environment; no global or repository Git config is
  changed.
- v6 is limited to one fresh full-Harness run using the new receipt helper. The
  helper scrubs all provider keys/consent, passes the process-scoped Git setting
  only to the verification child, binds source hashes and directly records the
  OS exit. It does not authorize a provider admission, result access, API call,
  Adaptive execution, or blind execution.
- Owner handoff boundary: after v6 reaches a terminal receipt, stop all work and
  issue a detailed stage report irrespective of pass/fail.

## 2026-08-06 Fresh Harness v6 Stop-Point Report

- v6 naturally terminated with directly observed child exit 0, 13/13 stages,
  pytest 1538/1/3 and a unique terminal `Verification failed=0`; receipt SHA-256
  is `26e516629708e03bfbef05a8915cef1d12701a9be227348215740cf40b093798`.
- A final read-only process audit found zero live formal Harness/Public/Adaptive/
  provider workloads. No process was interrupted, restarted, or reused.
- The report artifact at
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段技术报告_2026-08-06_artifact.json`
  has SHA-256 `c3b992d145c92d4c25f393fe28a8ecb42272cfe939eaefe774b83b4826ee2197`.
  It passed the Data Analytics artifact validator and MCP report renderer.
- The report explicitly preserves status boundaries: Flash public physical
  closure is not result admission; Gemini v5 is candidate-only; the 8-task
  Adaptive result is exploratory; blind authoring is 0/600 after Day-1
  registration. The project remains `in_progress`.
- This stop point created no gate/admission and made zero API/provider/network
  calls, zero scientific-outcome accesses, zero blind-label accesses, and zero
  external effects.

## 2026-08-06 Word Stop-Point Report And Final Pause

- Rechecked the process boundary before report generation: no formal Harness,
  Public, Adaptive or provider workload was alive, and no process was stopped or
  restarted.
- Converted the validated canonical artifact into the final external Word report
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段技术状态报告_2026-08-06.docx`.
  Its SHA-256 is
  `a0d088d2f6a1a8554bb6ea0c2bbdc5c0e34755f9bf689e2267ede3be01da531b`.
- The document is eight pages with four headline metrics, two source-backed
  analytical figures, two audit tables and complete evidence hashes. It states
  that engineering is green while Gemini, formal Adaptive, blind authoring and
  final closeout remain incomplete.
- All eight pages were rendered and inspected. Seven-table exact geometry,
  headings, section, images, required content and secret-pattern checks pass;
  accessibility has zero high findings. Ruff and py_compile pass for the
  reproducible builder.
- QA receipt SHA-256 is
  `3e948b02499e7c277aa9eaac9d04b275b1cfc45b12c3c0296eb5a9f226423c25`.
  No API/admission/gate/outcome/label/effect action occurred. F-PAPER-002 remains
  `in_progress`, and work is stopped by owner instruction.

## 2026-08-19 Owner Resume And Fresh-Harness Recovery Scope

- The owner explicitly resumed the full 21-day experiment closeout plan and
  requested execution rather than another interim report.
- Fresh Harness v11 remains immutable direct-exit `-1` evidence. Its 257 pytest
  setup errors share one missing system temporary root; no completed aggregate
  marker exists and the unfinished frozen-study-assets stage has no verdict.
- Recovery uses a new detached Harness identity and a run-scoped pytest
  temporary root. The existing v11 receipt/logs are sufficient failure
  evidence; no additional failure-review or duplicate source-lock bundle is
  created. Historical v11 artifacts, Pro-200 evidence and terminal experiment
  ledgers remain read-only.
- Before any Pro-500 provider call, the new current-source Harness must produce
  a directly observed exit 0 and every aggregate stage must pass. A minimal
  pre-execution check must then confirm the exact existing 36-task candidate,
  owner admission, budget fuse, no-tool/no-effect boundary and untouched output
  root without producing another redundant hash package.
- Provider tools, external effects, automatic retries, scientific-result access
  and blind-label access remain disabled. No report is in scope for this phase.

## 2026-08-19 Blind Deferral And Non-Blind Priority

- The owner deferred independent-blind authoring and execution and asked to
  complete the remaining experiment program first.
- Blind status remains explicitly 0/600 authored and 0/3,600 executed; it is
  neither fabricated nor counted as complete and no developer may substitute
  for the independent custodian.
- Current order is Fresh Harness recovery, Pro-500, hardest-20 to budget 2,000,
  DeepSeek Flash/Gemini adaptive, Gemini Public, result admission/statistics and
  final non-blind verification. Blind work remains a later open requirement.
