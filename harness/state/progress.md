# 进展记录

## 2026-08-20 — Lean claim–evidence ledger activated

- Added a 13-claim active ledger covering the completed DeepSeek findings,
  authorization burden, within-provider replication, budget-50/200 adaptive
  boundary, provider safety, citation status and the still-closed Gemini/JCR
  gates.
- All 26 referenced evidence paths exist. The old ledger is retained only as
  historical paper-v2 state because its blind, B500/B2000 and Full-Harness
  gates were superseded by the owner-approved lean plan.

## 2026-08-20 — JISA author-package inputs prepared

- Added a no-inference author-input template for title-page metadata,
  corresponding-author contacts, full affiliations, CRediT, declarations,
  acknowledgements, institutional review, release identifiers, biographies and
  photographs.
- Added the separate field-specific glossary requested by the current JISA
  guide and updated the submission checklist. Author-owned facts remain open;
  no placeholder was inserted into the reader-facing manuscript.

## 2026-08-20 — Active citation compliance complete

- Reviewed only the 21 references actually cited by the unified manuscript;
  all in-text keys resolve and citeproc renders no uncited bibliography item.
- Publisher/proceedings/arXiv records support 11 formal publications and 10
  preprints. DRIFT was corrected to NeurIPS 2025 with its official DOI;
  AgentSpec's unregistered DOI and unverified pages were removed in favour of
  the official ICSE 2026 Research Track page.
- Rebuilt Markdown and DOCX; focused manuscript/DOCX tests pass 9/9 plus Ruff
  and `py_compile`. Related Work and the JISA checklist now close the active
  citation gate. No provider call, Full Harness or historical replay ran.

## 2026-08-20 — Provisional JISA cover letter drafted

- Added a 293-word cover letter bounded to completed DeepSeek and Adaptive
  50/200 evidence. It states the empirical-method contribution, unfavorable
  full-versus-policy result, authorization-regime utility cost and JISA scope
  fit without a cross-provider or leading-defense claim.
- The letter follows Elsevier's general cover-letter guidance checked on
  2026-08-20: concise, under one page, focused on aim/findings/scope/impact, and
  free of funding, author declarations and reviewer suggestions.
- Corresponding-author details and any Gemini-dependent wording remain final
  author/submission-time tasks. No API call or experiment replay occurred.

## 2026-08-20 — JISA submission statements added

- Added a reader-facing submission-statements source and included it before the
  bibliography in both the Markdown and editable Word working drafts.
- Known data/code, AI-use and safety facts are stated directly. Competing
  interests, funding, institutional review and CRediT remain explicit
  author-confirmation gates and were not inferred.
- Focused verification passes 9/9 plus Ruff and `py_compile`; the rebuilt DOCX
  contains 282 paragraphs, 13 tables, five figures and 21 rendered references.
  Accessibility remains 0 high/0 medium/21 low (raw DOI/URL display text only).
- Standard page rendering remains unavailable because LibreOffice is absent;
  no repeated render attempt or Full Harness was run. Gemini remains pending
  until the next Pacific quota day.

## 2026-08-20 精简实证里程碑 5：DeepSeek 失败行定向恢复完成

- 显式 `--retry-failed` 只选中 33 个无官方响应的 work key；867 个已有
  response ID 的 work key 全部跳过。
- 当前为 933 条物理记录 / 900 个唯一 work key，最新状态全部进入 ITT；
  33 个 attempt-2 响应前失败终态保留，`retry_eligible=0`。
- 累计 1,638 provider calls、CNY 1.3888324；返回模型均为
  `deepseek-v4-pro`，forbidden 字段、provider tools 和 external effects 均为 0。
- DeepSeek 新授权制度阶段技术收口完成；F-PAPER-002 保持 `in_progress`，
  下一工作是 Gemini 免费层的未完成/无响应项。

## 2026-08-20 精简实证里程碑 4：DeepSeek 主执行结束并停止

- 唯一 DeepSeek pending-only runner 已自然结束，当前无匹配进程。原始文件为
  900 行 / 900 个唯一 work key，所有冻结 DeepSeek 计划项均已留下一条记录。
- 最小技术计数：867 行有官方响应，33 行无响应，870 行进入当前 ITT，
  30 行为可恢复的传输前失败；1,635 次 provider calls，CNY 1.3888324。
- 返回模型全部为 `deepseek-v4-pro`；online forbidden 字段、provider tools
  和 external effects 记录均为 0。
- 按 Owner 指令，未启动失败行恢复、Gemini 续跑、正式分析或任何新实验。
  F-PAPER-002 保持 `in_progress`。

## 2026-08-20 精简实证里程碑 3：主执行、限流恢复与论文图表工具

- DeepSeek 900 行计划已进入 pending-only `remaining` 顺序执行，6 行 formal
  prefix 被跳过且不会重跑；运行期间不启动第二个 DeepSeek runner。
- Gemini 主执行在官方免费层连续返回 429 后被停止。响应成功行保持终态；
  一个中断时尚未形成 raw 记录的 work key 已补记为无响应、可恢复状态。后续只在
  新配额日显式恢复失败/未触碰行，遇到首个 429 立即停止，第三个配额日仍失败则
  作为透明 diagnostic 降级。
- 修复了运行时把无响应 provider failure 当终态、以及没有从 Gemini paused
  call events 识别限流的两个恢复缺陷。修复只影响失败分类和后继选择，不覆盖旧行。
- 新增 compact authorization analysis：每个 work key 只取最新终态尝试，计算
  条件端点、paired pp difference、Wilson 95% CI、exact McNemar、10,000 次
  task-cluster bootstrap、Holm、ASK/DENY/失败/延迟/成本及预定义异质性。
- 新增五图静态生成器和 lean figure/table plan：field-isolation、Pareto、forest、
  runtime burden、adaptive budget-50/200。输出 PNG+SVG，不生成哈希清单；合成
  数据视觉 QA 后已修复标题与点标签重叠。
- Active manuscript README、Introduction 和 Methods 已切换到 180/90/60 嵌套
  样本、900/450 行、三项 RQ 和 focused-only verification；旧 blind、B500/2000、
  Full Harness 与完整二模型 adaptive 不再作为论文完成门。Related Work 和 BibTeX
  新增 2026 provenance-sensitivity measurement paper。
- 六表 CSV 导出器已完成，只读取 frozen plan 与 compact analysis；不打开 raw
  provider trace、不创建 hash bundle。定向 pytest 17/17、Ruff、py_compile 通过；
  没有 Full Harness、历史递归重放、
  盲测、真实外部 effect 或成功行重跑。

## 2026-08-19 精简实证里程碑 1

- Git 基线已提交：`d533414` (`chore: checkpoint lean empirical paper baseline`)；
  分支 `codex/q2-empirical-study`，未 push。
- 冻结 180/60/90 嵌套样本和 1,350 个唯一工作项：DeepSeek 900、
  Gemini 450，两家各 6 个 formal-prefix canary。
- 一次性统计完成：Pro Public 5,082、Flash Public 1,791、Medium 480、
  Adaptive 40 任务 B50/B200。本阶段 API/provider call=0，Full Harness=0，
  递归历史验证=0。
- 核心方向性结果：Pro full/policy unsafe effect 38/600 vs 13/600，
  benign-tool TCR 49/168 vs 49/168；Flash 为 24/400 vs 12/400，TCR
  38/145 vs 35/145。Adaptive first-success 为 B50 4/40、B200 18/40，不做饱和声明。
- 验证：4 个定向 pytest 通过，Ruff 和 py_compile 通过。已修正 Medium
  303+177 互斥分片的输入定义，不重跑成功实验行。

## 2026-08-19 精简实证里程碑 2：API 前最小运行器

- 新运行器只消费冻结的 1,350 行计划，每家输出一个紧凑 raw JSONL；
  provider 内部 trace/预算状态只保存到已忽略的运行目录。
- 每行保存 local request ID、payload digest、official response ID、returned
  model、unsafe effect、TCR、ASK/DENY、延迟、token 和成本；不保存 prompt/response 文本。
- 恢复规则已由测试锁定：已有官方响应的行终态不重跑；仅无官方响应行
  能通过显式参数单独重跑；自动重试始终为 0。
- 聚焦测试 8/8、Ruff 和 py_compile 通过。首次 pytest 因专用 basetemp
  父目录未存在而 6 pass/2 setup error，创建该临时父目录后 8/8 通过；
  API/provider call=0，Full Harness=0。

## 2026-08-19 DeepSeek 授权制度 formal prefix

- 首次启动在 provider transport 前因配置校验函数签名错误而 fail-closed；
  raw/trace/API 调用均为 0。切换到 Public-role 校验器并增加精确模型回归后，
  定向测试 9/9、Ruff/py_compile 通过。
- 修复后正式前缀一次完成：6/6 行、14 provider calls、6 个官方 response
  ID、精确 `deepseek-v4-pro`，CNY 0.0157848。
- 终态为 completed 5、max_steps 1；max_steps 保留在 ITT，不重跑。在线
  forbidden 字段、tools、external effects、automatic retry 和 retry-eligible 失败均为 0。

## 2026-08-19 Gemini 授权制度 formal prefix

- 首次 6 行中 5 行有官方响应，1 个 VIGIL 行无响应；根据冻结恢复规则
  只对该行进行一次显式 attempt 2，其余 5 行未重跑。
- attempt 2 仍为相同 VIGIL 无响应失败，因此停止继续重试，将第二次失败
  归为 ITT operational failure。原始 7 行（6 work keys + 1 recovery）都保留。
- 最终 6-work-key 口径：3 completed、2 parse_failure、1 repeated pre-response
  failure；5 个 response-bearing，精确 `gemini-3.6-flash`，USD 0。全部 6 行在
  ITT，无剩余 retry-eligible 行。
- 定向验证 11/11，Ruff/py_compile 通过；online forbidden fields、provider
  tools 和 external effects 均为 0。

## 2026-08-06 04:40 Gemini Public-v5 最小 recovery 日段完成并停止

- fresh Harness gate v4 重放 v6 与当前六项前置证据通过，manifest
  `d79faf97...e1e9a`；门禁不授权 provider 或结果访问。
- 新 v5 recovery single-use wrapper 和 exact day admission 完成。LA quota day
  `2026-08-05` segment 0 单次运行得到 1/1 formal-candidate 记录、1 次完成调用，
  exact `gemini-3.6-flash` 与官方 response ID；免费层 USD 0、自动重试 0、
  provider tools/external effects=false。
- outcome-blind technical review 全检查通过、runner failure 0、结果仍未准入；
  wrapper exit 0，receipt SHA `a881799f...b3de`，review manifest
  `86e48d12...560c2`，相关正式进程归零。
- 定向回归 20/20（1 个已知 deprecation warning）、Ruff/compile、PowerShell
  parse 和 conventions 12/12 通过。新增源后没有重跑完整 Harness，因此
  F-PAPER-002 保持 `in_progress`。
- 阶段报告 SHA `76137e6b...eb05`。按 owner 指示停止，不继续 segment 1、
  Gemini 全矩阵、Adaptive 或 blind 执行。

## 2026-08-06 03:40 Fresh Harness v5/v6 工程收口并停止

- v5 直接 exit 1 证据已由 failure-review manifest `02af896a...7149` 冻结：
  pytest 1531/1/3、10 PASS/3 FAIL，根因是沙箱 Git ownership boundary，零
  provider/network 授权，历史 v5 未修改。
- 脱敏 Git qualification manifest `f4bbaaac...c7db` 证明精确且仅进程作用域的
  `safe.directory` 可读取 AgentDojo 冻结 commit；global/repository config 均未写。
- 新 v3 helper/v6 launcher 定向验证为 pytest 10/10、Ruff、compile、PowerShell
  parse、conventions 12/12、两个证据重放全通过。
- v6 完整 Harness 直接 child exit 0，13/13 stage PASS，pytest 1538 passed /
  1 skipped / 3 warnings，唯一终态 `Verification failed=0`；运行 15737.184 秒。
  receipt SHA `26e51662...3798`，相关进程最终 0。
- API/provider/network、新 admission、新实验和 outcome 修改均为 0。详细报告
  SHA `39dc2662...5167`。按 owner 指示停止；F-PAPER-002 继续 `in_progress`，
  Gemini、formal adaptive、600 条盲测和最终结项包仍未完成。

## 2026-08-04 04:01 Gemini v2/v5 离线收尾与完整 Harness 无终态

- 实现 Gemini trace-attaching runtime v2、local-precommit contract v2.1 和
  Public-v5 canary recovery controller；历史 v4 终态/abort 不变，新候选仅含
  10 个 untouched work key、7 个 free-tier 日段，write/verify exit 0。
- 定向结果：runtime 20/20、v5 candidate/admission 3/3、缺 request-ID 注入式
  E2E 1/1、Ruff/compile、conventions 12/12 全部通过；API/network 0。
- `verify.ps1` 已集成 Gemini v2/v5 与 Flash recovery-v4/merge-v1。完整 Harness
  外层 3604 秒 exit 124，子进程再运行 441.6 秒自然结束；由于终态输出和原始
  exit code 丢失，本轮不得标记完整验证通过，相关进程最终为 0。
- F-PAPER-002 仍为 `in_progress`；新的 provider admission、Gemini 执行、
  adaptive、盲测和最终结项包均未启动。阶段报告 SHA-256 为
  `2bc1d1c7...3b29b`。

## 2026-08-04 02:05 Flash 第二模型证据复核完成并暂停

- recovery evidence review v4 对两个恢复分片均给出 evidence-integrity PASS；
  s0/s1 的冻结 1% claim-quality 门分别为 FAIL/PASS，不豁免、不改写旧 v3。
- second-role evidence merge v1 对 1791 个唯一 work key、16 diagnostic、4193
  calls 和 CNY 1.87793024 完成内容无关合并；所有 diagnostic 留在 ITT，终态
  retry=0，科研 outcome/result admission 均保持 false。manifest
  `7fba09cc...8432b`，JSON SHA `6334514e...ef4e`。
- merge write/独立 verify 都 exit 0；定向 pytest 8/8、Ruff、py_compile 和项目
  conventions 12/12 通过。
  首次独立 verify 因外层超时误设为约 1 秒而 exit 124，未形成结论，已记录后
  使用约 208 秒完整重放通过。相关正式进程 0。
- 报告：`docs/research/paper_v2/reports/M3_PI_Guard_Flash第二模型证据复核与暂停报告_2026-08-04.md`，
  SHA `e55f3bbf...f6ea8`。未运行新 full Harness，F-PAPER-002 继续 `in_progress`。

## 2026-08-04 01:30 当前正式运行收口并停止

- Flash recovery-v3 两分片执行主体均 exit 0 并完成 1306/1306 新记录；s0/s1
  分别 10/4 diagnostic、1329/1383 calls、CNY 0.59580836/0.49424660。
  两个 outcome-blind review 程序都成功写出工件，但 wrapper 因 technical gate
  FAIL 最终 exit 1。s0 确实超过分片 1% 门，v3 review 同时存在“无源记录重试”
  false 值被 `all()` 误作失败的实现缺陷；不改写、不重跑、不准入结果。
- Flash 全角色 1791/1791 物理记录闭包成立：16 diagnostic、4193 calls、
  CNY 1.87793024；结果访问仍封闭。
- Gemini segment 1 的一条官方调用 HTTP 200 且精确模型/response ID 完整，但
  provider request ID 不可用；历史 experiment-record formal 语义与已接受的
  local-precommit 链冲突，故记录前 fail closed。新 abort review manifest
  `6d7605dd...d649` 通过 write/verify，明确不是 429、不可恢复、不可重试。
- 新审查 compile/Ruff、pytest 7/7 通过；正式运行相关进程 0。详细收口报告：
  `docs/research/paper_v2/reports/M3_PI_Guard_当前运行收口与阶段评估报告_2026-08-04.md`，
  SHA-256 `20972e4a...dac6`。本轮停止，F-PAPER-002 继续 `in_progress`。

## 2026-08-04 00:35 Gemini 免费层 canary segment 1 启动

- 当前 provider quota day `2026-08-03` 未被账本预约；segment 1 的 exact
  admission write/verify 通过，manifest `93ba06fc...e03a`，最多 16 请求、
  USD 0、retry 0、concurrency 1、tools/effects/result admission false。
- single-use v5 wrapper PID 42336 于 00:34:36 启动。它与 DeepSeek Flash 使用
  完全独立的 provider、ledger、checkpoint、budget 和 output root；同日不再
  启动任何其他 Gemini formal workload。

## 2026-08-04 00:14 Fresh gate-v3 通过并启动 Flash recovery

- 非自授权 gate-v3 写入/重放通过：manifest `e06188dc...b985`，17 个 source
  locks，Harness 13 stages/1485 tests，credentials/provider calls 0，执行授权 false。
- s0/s1 admission 各自 hash-bind 652/654 个 untouched work key、CNY
  2.04118328/2.17094144、retry 0、tools/effects false；结果准入 false。
- 两个 single-use guarded wrapper PID 25256/43856 于 00:13:15 各启动一次。
  源 canary/prefix 不重试，总角色 ceiling 为 CNY 5；Gemini、Adaptive、blind
  当前未启动。等待自然 receipt 后再做 outcome-blind 技术审查和独立准入。

## 2026-08-03 20:50 Fresh Harness v4 通过并暂停后续执行

- v4 自然结束且直接 OS exit 0；运行 16:03:33–20:38:25，13/13 stage PASS，
  pytest 1485/1/3，最终 `Verification failed=0`。
- receipt SHA-256 `a9fddc0f...2c1b`；stdout/stderr SHA-256
  `1b1a5305...3d75` / `777e65d1...2c26`。API env scrubbed，provider/network
  authorization false，本次调用 provider 0 次。
- stderr 仅含预期 RuntimeAuditor delete 拦截和 WSL 本地化提示，不含聚合 FAIL。
  helper/child 与旧 Flash wrapper 进程均已自然终止。
- 根据所有者最新指示，只完成本次运行、核验、状态和阶段报告后暂停。未生成
  gate-v3、未创建新 provider admission、未启动 Public/Adaptive/盲测后续任务。
  F-PAPER-002 继续 `in_progress`。

## 2026-08-03 16:04 fresh Harness v4 单次启动

- preflight 证明全新输出根、0 个相关执行进程、launcher parse、v3 failure review
  和 Day 1 acceptance 全部通过。
- detached helper PID 37772 于 16:03:32 启动；`running.json` 记录当前 verifier
  SHA-256 `33390d65...c6e4`，API 环境已清除，provider/network 未授权，自动
  restart=false。receipt 未出现前保持 `in_progress`，不创建 gate、不调用 API。

## 2026-08-03 interim Harness v3 失败已冻结，fresh v4 已就绪

- v3 detached Harness 直接 exit 1，1456/1/3；唯一失败是旧测试未区分
  adaptive v1/v2 controller，误把合法 v2 Pro admission 识别为 v1 回退。
  failure review manifest `67bcdaaa...78cf9` 绑定 receipt、stdout、stderr 和源锁，
  provider/network calls 为 0。
- 版本感知测试修复后 focused 20/20，通过扩大后的 Gemini/Flash/recovery/gate
  组合 38/38；项目 conventions 12/12。`verify.ps1` 当前 SHA-256
  `33390d65...c6e4`，相关独立 verifier 全部 exit 0。
- fresh gate-v3 和 single-use Harness-v4 launcher 已实现并通过 compile、Ruff、
  PowerShell syntax；gate artifact 尚不存在且不得预先创建。下一步必须运行
  fresh v4 至自然终态，直接 exit 0 后才能形成 provider 执行门。
- Flash recovery-v3 与 Gemini continuation-v2 只是离线候选，当前 execution /
  result admission 均 false；历史 prefix、diagnostic 和缺失 wrapper receipt 均留在
  ITT。Day 1 三文件当前重放 exit 0、pytest 2/2，登记完成状态不变。

## 2026-08-03 Gemini v5 失败感知门和续跑-v2 候选完成

- segment 0 保持历史 v4 technical-fail 和 ITT `runner_failure` 不变；v5
  对 1 次官方传输完成与 1 次 `VigilLiveDependencyError` 做精确对账，
  14/14 检查通过，manifest `8c256e49...9728c`，继续条件 true、结果
  准入 false。
- 缺少的 wrapper receipt 没有伪造；恢复工件 `1df13ad9...47f1f`
  将 segment 标记为终态、OS exit 未知，禁止同 segment 重跑。模块
  compile/Ruff、3/3 测试和 write/verify 全绿。
- continuation-v2 完整保留 1,779 条/1,186 个标准免费日段和四逻辑
  shard，激活门由 v4 改为 v5 aggregate；manifest `fcc80d26...5c95`，
  Batch/付费/执行/结果准入均 false。当前免费层约束下的真实日历下界
  为 canary 后至少 1,186 个配额日，21 天工期必须按锁定顺延条款延长。

## 2026-08-03 12:28 Day 1 三文件再次只读复核通过

- inbox 当前严格为 3/3 份公开登记工件，三个 SHA-256 均与原始 acceptance
  绑定值完全一致；没有移动、删除或改写文件。
- 冻结 acceptance verifier 直接 exit 0，定向 pytest 2/2 通过，manifest
  `94e5a647...745c` 不变。`blocked_missing_verifier_receipt` 仅作为历史
  事件保留，当前证据重放缺口已解除。
- Day 1 独立保管人登记继续认定为完成；600 条 authoring/custody、
  3,600 条执行、标签解封和评分仍待后续完成。

## 2026-08-03 fresh Harness/Flash canary 完成，Flash 正式续跑启动

- fresh Harness v2 直接 exit 0，13 个聚合 stage 全绿；pytest 1451/1/3，
  stdout/stderr/receipt 均已哈希锁定。fresh gate v2 写入并重放通过，但不自行
  授权任何 provider 执行。
- Flash 12 条 canary 技术门通过：18 calls、CNY 0.01232192、无 diagnostic、
  重试、provider tools 或真实 effect；仅技术结果可见，科研结果仍封存。
- continuation-v2 离线资格、候选和两个分片 admission 已创建并验证；1,779 条
  被完整互斥分为 890/889，总 CNY ceiling 5（含 canary），结果准入 false。
- guarded wrapper 通过 4/4 focused tests、Ruff 和 PowerShell syntax；两个新身份
  已于 11:52:22 各启动一次。当前只监测 append-only 计数/receipt，不读取条件
  效果，不自动重试。F-PAPER-002 继续 `in_progress`。

## 2026-08-03 Day 1 重放恢复，fresh Harness v2 已启动

- 补回的 verifier receipt 与 acceptance 绑定哈希完全一致；3/3 文件、28/28
  检查、acceptance verify 和 2/2 定向测试通过，先前证据留存缺口解除。
- 实现 fresh direct-exit Harness gate v2、single-use launcher 和 guarded canary
  wrapper v3；gate 不授权 provider，canary 仍需独立 admission，retry/tools/effects
  均为 0/false。组合测试 24/24、Ruff、compile、PowerShell syntax 通过。
- 启动前新根不存在、无其他相关进程、DeepSeek Flash admission 无凭据重放
  exit 0、conventions/diff check 通过。
- detached Harness v2 PID 31716 于 06:35:34 启动，network/provider authorization
  false，三类 API key 环境变量已 scrub；当前进入完整 pytest。receipt 未出现前
  不创建 gate 工件、不运行 API canary。F-PAPER-002 保持 `in_progress`。

## 2026-08-03 Day-2 Harness 失败固化与当前接线修复

- `experiment_closeout_day2_harness_v1_20260802` 的直接 receipt 为 exit 1、
  `completed_nonzero`、1438/1/3；12 个 PASS、1 个 prospective FAIL，provider /
  network authorization 为 false。
- 失败根因不是模型或实验结果，而是当前 Harness 仍验证已经永久废止且按设计
  drift 的 Pro-50 v1 admission。失败审查 manifest 为 `230fc98...e398f`，
  写入/重放、Ruff、编译和关联测试均通过。
- `verify.ps1` 当前 closeout block 不再调用 Pro-50/Flash-50 v1 admission；改为
  验证 v2 supersession/order review、Day-2 failure review 和 Day-1 acceptance。
  历史 v1 资产未修改，旧绿色 Harness review 继续作为历史工件而非当前可重建
  结论。
- PowerShell 语法与定向测试 14/14 通过；无凭据并行复演的 10 个其余 closeout
  检查全部 exit 0。首次串行包装在 124 秒超时且无模块标记，随后确认遗留的
  Gemini candidate 只读进程自然结束，并改用逐项可观测执行完成验证。
- 当前唯一已知完整 Harness 阻塞是缺失的 Day-1 verifier receipt；恢复前不启动
  数小时 Harness，也不授权 API canary。F-PAPER-002 保持 `in_progress`。

## 2026-08-03 Day 1 已历史完成；当前登记重放缺第三份公开回执

- 当前 inbox 只剩 `custodian_public_key.pem` 和
  `custodian_registration_v2.json`；两者哈希仍与历史 acceptance 完全一致。
- 必需的 `custodian_registration_verifier_receipt_v2.json` 缺失，故开发者侧
  acceptance 不能重放；定向测试结果为 1 passed / 1 failed，失败信息为
  `Day-1 inbox must contain exactly the three public registration files`。
- 项目内及常用交付目录未发现可用原件；只发现测试负例的临时同名文件，未复制、
  未打开、未采用。历史 acceptance 工件及其 manifest 保持不可变。
- acceptance 在 2026-08-02 23:24 已完成并通过 2/2；目录内容变化时间为其后的
  23:37:43。本轮没有文件删除命令，测试只复制到 tmp_path，无法将缺失归因于
  当前智能体或具体外部进程。
- Day 1 完成事实和 21 天技术时钟不追溯撤销；当前单独记录为
  `blocked_missing_verifier_receipt` 的证据留存/重放缺口。恢复原始回执并通过
  精确三文件重放前，不授权 600 条盲测后续工作，也不启动 fresh 完整 Harness。
  F-PAPER-002 保持 `in_progress`。

## 2026-08-02 Day 1 独立保管人登记已验收

- `external/independent_blind/day1_registration_inbox` 的公开交付严格为三份：
  `custodian_public_key.pem`、`custodian_registration_v2.json`、
  `custodian_registration_verifier_receipt_v2.json`；没有收到私钥、身份声明
  明文、候选或标签。
- v3.4 冻结 verifier 的 pristine/replay 检查通过：三文件闭包精确，登记与
  独立验签有效，保管人/验签人不同，28/28 recorded checks 为真，标签数为 0，
  执行授权为 false。
- developer-side acceptance artifact 为
  `protocols/paper_upgrade_v2/independent_blind_day1_registration_acceptance_v1.json`，
  manifest SHA-256
  `94e5a64710dbcef941375c257e210ab8ea424a0d0b975e50e86c0509e8df745c`；
  只保存身份哈希和公开签名链，不保存身份明文或私钥。
- 验收模块 write/verify exit 0，定向测试 2/2。由此 Day 1 登记前置条件完成，
  21 天技术时钟可从 receipt 的验证时间启动。独立盲测后续 600 条 authoring、
  custody、3,600 条执行、解封和评分仍按用户要求暂缓，F-PAPER-002 保持
  `in_progress`。

## 2026-08-02 Python-first Markdown 单目录保管人审查包 v3.4 完成

- 最终交付为
  `docs/research/paper_v2/reports/M3_PI_Guard_Blind_Custodian_Review_Package_v3_4_python_final`；
  根 `README.md` 详细列明唯一运行目录、应保管/交付/禁止交付的文件、
  600→3,600 流程和全部 Python 子命令。包内无 DOCX、PS1、密钥或永久
  环境变量配置；私钥必须留在包外 signer。
- 核心修复覆盖 registration/custody/scoring 精确 schema、时序和未来时间，
  3,600 行 output/effect/provider trace/request-chain 重放，以及 provider terminal
  与 ITT operational status 的严格映射。合法重签名的嵌套 `gold_label`
  注入和重哈希状态伪造均被拒绝。
- 证据边界分为 A `custodian_private_artifact_full_replay` 和 B
  `developer_safe_signature_integrity_only`。A 打开私有 labels 但不声称自动
  重算人工语义；B 无私有路径参数且不枚举 `work/private`。
- 成品 physical manifest SHA-256
  `43a6c80a454659167419ccabbf0ef33cb924fefee73fe5583d499e6eb1ac4651`，
  embedded digest
  `644a0961d6bd7b6d5495191dc0672359678324715942d993513ee725c8f7f089`；
  44/44 manifest 闭包，39 allowlist + 5 generated，600 slots 哈希未变。
- 最终验证：源码组合 50/50，包内 33/33，项目规范 12/12，Ruff/编译/
  schema/manifest/secret/path 审计全绿；`verify-pristine`、`verify`、`status`、
  `show-next` 全部 exit 0；独立 reviewer 仅对 v3.4 给出 GREEN。
- 三个可移植性失败候选和早期包装失败均保留为 rejected diagnostic，
  不删除、不覆盖、不交付。真实保管人、私有 600 条、标签、盲测运行和结果
  仍不存在；F-PAPER-002 保持 `in_progress`，21 天时钟未启动。

## 2026-08-02 独立盲测保管人工具包与详细 Word 手册完成

- 完成独立盲测 v2 的真实保管人登记、Ed25519 密码学签名/独立验签、
  600-row 确定性 execution/label 分离、pre-release、custody、开发者无标签
  导入、3,600-row 输出封存、标签解封、独立评分和最终评分签名接口。
- 最终 standalone 工具包位于
  `docs/research/paper_v2/reports/M3_PI_Guard_Blind_Custodian_Toolkit_v2_final`，
  含 00–18 号 PowerShell wrapper；早期目录已 fail-closed 标记为 superseded。
  工具包内嵌 manifest SHA-256 为
  `9aaffe0120ff93ff3df9a93e955378b37000dd088da62a96eb66f28f086edac8`。
- 生成 34 页中文 Word 手册，逐项说明角色、目录、保管文件、交付白名单、
  禁止事项、每条命令的运行者/工作目录/前置条件/失败处理和全流程验收表。
  DOCX SHA-256 为
  `900db3b501d0ee50289af637e2f6c5d69105125d06af24c73659a2b18dd16fa3`。
- 最终 QA：文档结构验证 exit 0（42 headings、65 tables、1 figure、0 table
  geometry issue），a11y high/medium/low=0/0/0；LibreOffice PDF 为 34 页，
  34/34 页逐页视觉检查通过。独立盲测 v1/v2/工具包/仓库布局测试 47/47，
  Ruff 与项目规范审计 12/12 通过。
- 标准 `render_docx.py` 的 DOCX→ODT 阶段超时；未把超时当作通过。改用同一
  官方 LibreOffice 可执行文件直接转换 PDF，再用 Poppler 栅格化，并逐页检查。
- 本轮零 credential、零 blind-label 读取、零模型/API/network call、零真实
  effect。真实保管人尚未登记/签名/编写 600 条，因此 F-PAPER-002 与独立盲测
  仍为 `in_progress`，不宣称盲测完成。

## 2026-08-02 Day-1 工程基线完成，外部 custody 前提待满足

- 新完整 Harness 从 12:20 运行至 15:44，自然完成 13 个聚合阶段；pytest
  结果为 1,365 passed、1 skipped、3 warnings，用时 5,049.03 秒。stdout
  907,749 bytes，SHA-256
  `340509a306d6585b53e77a64751bafc5bab2c9ddda9b9ba7918a18b5951ec170`；
  stderr 只有 33 条预期 RuntimeAuditor `delete_record` 阻断和环境警告，
  SHA-256
  `02a6c27e6984563a30e9f4de762ccbb5a4575c07cef687003b6154030be79a41`。
- 外层执行通道先超时，故原 wrapper receipt 缺失。新增只读恢复审查要求
  13 个精确 PASS 名称、0 FAIL、唯一末行 zero marker、无 traceback、
  精确日志/脚本哈希和 `verify.ps1` 立即退出契约；审查 manifest
  `22954e84b5a6f97c54faf25f9d972815e66c5a56262c6b00750643cb25eebec1`
  验证通过，并披露 OS exit code 未被直接观测。
- 恢复审查自身是 full Harness 后的 executable/evidence-only 增量：未改
  runtime、experiment controller 或 verify 脚本；状态/移交文档单独更新。
  其 pytest 2/2、Ruff、py_compile 和 artifact verify 均 exit 0。
- Day-1 全程零 credential、零 provider/API call、零 admission/quota reservation、
  零费用、零 provider tools/外部 effect、零科学结果访问。
- 工程 Day 1 已完成；第三方保管人和独立封存候选仍未到位，因此计划级
  Day-1 不能标为完整完成，21 天结项时钟尚未启动，F-PAPER-002 保持
  `in_progress`。

## 2026-07-30 Public-primary 正式分析、最终验证与阶段报告

- 5,082 条 Public-primary 记录已通过 outcome-blind merge、独立结果准入、
  v5 投影兼容分析和独立 reviewer；847 cases = 600 attack + 247 benign，
  76 diagnostics retained in ITT，0 rows excluded/mutated，0 analysis calls。
- Public overall：M3-full unsafe-effect 38/600，结构化 133/600，
  policy-only 13/600；full vs structural = -15.83 pp
  （bootstrap 95% CI -19.50 至 -12.17，Holm p=1.61407e-16），
  full vs policy-only = +4.17 pp（2.50 至 6.00，Holm p=3.24845e-06）。
  benign-tool TCR 为 49/168、103/168、49/168；机制门保持 fail_redirect。
- Public 官方证据链记录 12,808 calls、CNY 11.9909764，零自动重试、
  provider tools 或真实外部 effect。冻结 1% 质量门失败且无豁免，所以
  只允许 primary-model empirical fallback，不允许 clean mechanism、
  cross-model/cross-provider 或 SOTA 声明。
- 科学证据 scorecard 更新为 869/1200（72.4167%），投稿就绪度 68%。
  Adaptive 仍只是 8-task budget-50 探索；第二模型、formal adaptive 与
  独立盲测仍未完成。
- 全量 Harness 文件化运行保留 1265 passed、1 skipped 和一个已修复的
  状态依赖测试失败；后续发现并修复 PowerShell admission 路径参数拆分。
  修复后的 focused v5 tests、v5 analysis verification、independent review
  和 bibliography verification 四项均退出 0，stderr=0。
- 生成最终 16 页 Word 报告，包含 6 图、17 表、7 个外链；SHA-256 为
  `6eeba31b59263160843bab1c23458fcee1ab89021f333ee7ea265a7be36bfd56`。
  结构 QA 全部通过，报告测试 3/3、Ruff、a11y 0/0/0 通过；WPS 以临时
  只读副本渲染，源哈希未变，16/16 页逐页检查无裁切、越界或孤立表头。
- 用户要求报告完成后停止。本次未启动任何新 API、v7、第二模型、正式
  adaptive 或盲测任务；F-PAPER-002 保持 `in_progress`。

## 2026-07-30 Adaptive cost-canary v1 封存与 v2 fresh recovery

- v1 在首个终态 query/official call 后因错误字段
  `effective_guard_decision` 退出；有效技术链为 2 query events、
  1 provider budget event、1 complete trace、CNY 0.002271、0 open，
  无自动重试/工具/外部效果。
- outcome-blind abort review 锁定 candidate/admission/query/budget/trace/
  stderr，manifest
  `a44f398069d0b1d7ecdeb3063878021993bf1dd554c9dd425793065ea1764c6e`；
  旧 query 不进入新运行或科学分析。
- fresh v2 仅把 bridge decision 映射修为正式契约字段
  `initial_guard_decision`，同时使用新 run/execution/output identity。
  candidate manifest
  `6570795d5da00b5d6093ad5997ee2720d0f1644cb0313d02dfd2e88af446578d`；
  8/8 聚焦与 injected-transport 端到端测试、Ruff、py_compile 通过。
- v2 单进程 cost-canary 已启动并越过首条失败点；最多 400 queries /
  3,200 provider calls、新 CNY 5 硬上限、零自动重试。结果仍不准入，
  scientific score 暂不增加。

## 2026-07-30 Public primary continuation-v1 封存与 v2 fresh recovery 启动

- continuation-v1 四片各完成首条 record 后因 4.9/20.0 元 policy summary
  重建不一致而退出；4 records、13 official calls、CNY 0.014446，
  0 open attempts/retries/tools/effects。旧 usage/cost 算术经 4.9 元
  分片策略复核有效，但四个旧根均永久不可续跑或选择性复用。
- 新增内容无关 abort review，manifest
  `be0d736abf4f856871978e472ae0408d15c51bd92cb2ef59c7dee4375b99995b`；
  它锁定旧候选、admissions、records、attempt/budget ledgers、traces 与
  stderr，不报告 unsafe effect、task completion 或条件效果。
- continuation-v2 使用 policy-aware state reconstruction 和四组全新身份，
  重新覆盖完整 5,058 条分区。零网络 qualification manifest 为
  `e96c2aad7db3ff1f668015095ba04d61f099c9a4d3168ca1246b6589136c918e`，
  candidate manifest 为
  `d05562406e081ae6c2b33fafc7e9f8963b8f04966ec4f9a819fd7dd397271692`。
- 聚焦回归 12/12、Ruff、py_compile、candidate 和四个 active admissions
  均通过；四个新根从不存在状态启动，并已全部越过第一条记录。运行仍在
  继续，自动重试 0，scientific outcome 仍封存，F-PAPER-002 保持
  `in_progress`，当前分数仍为 753/1200。

## 2026-07-29 Public-v4 技术门、分片候选、完整 Harness 与阶段报告

- Public-v4 primary technical canary 完成 24/24 records、64/64 official
  calls，0 diagnostics/operational failures/retries/provider tools/external
  effects，累计 CNY 0.0521812。outcome-blind review 全部通过，但
  result admission=false，未读取或聚合 scientific outcomes。
- 冻结剩余 5,058 条 primary records 的四分片候选，规模为 1,265 /
  1,265 / 1,264 / 1,264，每片 CNY 4.9，合计上限 CNY 19.6；四片互斥并
  排除 24 条已完成 canary。报告交付前未创建 active admission 或 API 进程。
- 当前工作树完整 Harness 自然退出 0：pytest 1,188 passed、1 skipped、
  3 warnings，所有验证阶段通过，`Verification failed=0`；stdout
  SHA-256 为
  `806033e70b4d538d2c8656221cb2590c34afa8deaa53fdee7f061ed8fe91a7fc`。
- 生成 17 页中文阶段报告
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-29.docx`，
  含 6 幅分析图、19 张固定几何表、11 个前沿链接。DOCX SHA-256 为
  `5f89bdc294892658b8ca8d634f8c8d6810f92367abd345f5b026ee91d7d1e7d4`；
  ZIP/OOXML、页面与表格几何、图片 alt text、真实编号、占位符/凭据/
  批注/修订检查通过，可访问性 high/medium/low 均为 0。
- LibreOffice/soffice 不存在，标准渲染器不可用；改用 Microsoft Word
  ExportAsFixedFormat + pypdfium2 生成 17 页 QA 预览并逐页检查。修复两处
  跨页拆行及一处图注/来源裁切后，无重叠、裁切或不可读图表。
- 科学证据保持 753/1200（62.75%）；技术金丝雀、Harness 测试和报告制作
  均不计入科学结果。下一步为 primary 四片 continuation，随后 second、
  公共结果准入、自适应攻击和论文回填。

## 2026-07-29 Public-v3 primary 部分执行并永久封存

- 按 owner 精确授权创建并校验一次性 admission，随后执行唯一 Public-v3
  primary canary。12 条 AgentDojo records 正常完成；第 13 条、首个 M3 item
  在 provider calls 完成后的离线 evaluator 阶段 fail closed。
- 不可变状态为 25 attempt events、12 terminal、1 open、12 records、33
  completed calls、13 trace files；累计 26,184 prompt、2,534 completion、
  22,656 cache hit、3,528 cache miss 和 CNY 0.0263544，budget 未暂停。
- 源码根因是 v3 resolver 虽从 public plan 找到 M3 case，却继承 public-v1
  execution identity 生成 binding digest；runtime material 使用 v3 permit
  identity，导致 `work_key_sha256` 不一致。
- 自动 retry=0，provider tools/external effects=false；命令已退出 1，未续跑
  11 个 untouched items。v3 不可恢复且不进入结果准入，scientific score
  保持 753/1200。下一步为内容无关 abort review 和 fresh Public-v4。
- 已完成 Public-v4 resolver 最小修复与真实 evaluator qualification：4/4
  测试和 Ruff 通过；四个跨角色/类别探针均证明 binding digest 与 active
  execution identity material 一致且 evaluator 完成。qualification SHA-256
  为 `a92a5f3ec565d14421f3575c3dd199475fe1d28d8f050aeae0ac381e37b62c95`，
  仍为零网络/零正式结果。controller/candidate 尚未冻结。

## 2026-07-28 Public-v3 离线修复与准入前验证完成

- 新增 `PublicFrozenM3CaseResolverV3`，直接从 public plan 的
  `source_reference` 恢复 evaluator-only binding，不再使用 medium work-key
  index。覆盖 3,600 个 public M3 work items、750 个 private bindings；
  primary/second × attack/benign 四个探针全部通过，0 credential/network/
  provider calls，online state 未改写。
- Public-v3 controller 哈希绑定 Public-v2 abort review、AgentDojo public
  resolver 和 M3 public resolver；新的 candidate 保留 6,873 条 result-blind
  计划与 18 个条件对，使用全新双角色 execution identities/run/output roots。
  candidate manifest 为
  `7df71eda75083a36b787659b482549ff3b2a7085b5ad01f8830dd0d2f9a32ef1`。
- v3 live controller 显式把同一个 public M3 resolver 绑定到常规与
  boundary-aware evaluator；provider tools、external effects 和 automatic
  retries 仍为 0，结果准入保持独立。
- 独立 Stage A 重建退出 0；聚焦 pytest 10/10、Ruff、JSON、PowerShell/Bash
  syntax 通过。完整 Harness 外层 7,200 秒通道超时且总退出不可恢复，因此
  不计为绿色；可恢复全量 pytest 随后退出 0，1,170 passed、1 skipped、
  3 warnings，4,468.35 秒，stderr 为空。
- primary/second v3 admission 与 output roots 均不存在，API 调用 0、正式
  结果 0、scientific score 仍为 753/1200。下一步仅为展示新的 primary
  exact command 并取得逐字 owner 确认；旧 Public-v2 授权不得复用。

## 2026-07-28 12:52 Public-v2 部分 canary 封存

- 按 owner 的逐字确认执行唯一一次 Public-v2 primary 24-record canary；
  自动 retry=0，未启用 provider tools、external connectors 或真实外部效果。
- 12 条 AgentDojo 记录成功落入 append-only ledger；第 13 条首个 M3-v2
  记录在 provider 调用完成后进入离线 evaluator 时失败，错误为
  `unknown paper-v2 work key`。控制器 exit 1，未续跑剩余项目。
- 冻结状态为 12 records、25 attempt events、12 terminal、1 open、
  11 untouched、29 completed provider calls。累计 22,169 prompt /
  1,934 completion tokens，cache hit/miss 为 17,536/4,633，
  CNY 0.0259414，预算未暂停。
- 根因审计证明公共 M3 key 位于 public plan、但不位于
  `medium_execution_plan_v2.jsonl`；`FrozenM3CaseResolver()` 在 public
  controller 中仍使用 medium 默认计划。Public-v2 永久不可恢复。
- 新增可重建的内容无关 abort review 与单测；review manifest
  `c3e17fe2f74bd807a348202c2ac632c9be6e4f6c2e426c4a8b7a3c5a70d4f1c5`。
  Ruff PASS；聚焦 pytest 2/2 PASS，372.40 秒。
- 未读取或聚合 unsafe-effect、task-completion 或条件比较；没有 public
  科学结果准入，evidence score 保持 753/1200。下一步只能离线构建和验证
  Public-v3 公共 M3 resolver，然后请求新的 exact-command owner 授权。

## 2026-07-28 09:30 Public-v1 零调用中止与 Public-v2 离线修复

- 执行了 owner 明确批准的 Public-v1 primary canary。第一次在 attempt loop
  前因 LFischl 缺 PromptGuard 依赖失败；补齐冻结版本并通过本地 CUDA 双探针
  后，同一命令的一次非自动重试在首个 public AgentDojo work key 上暴露
  medium-only resolver 缺口。
- v1 append-only 状态永久保留为 1 started/open、0 terminal、0 records、
  0 budget rows、0 traces、0 provider requests、CNY 0、0 formal results。
  结果/标签未访问，自动 retry=0；该 run 不可恢复。
- 新增 outcome-blind abort review，校验 admission、两份 exit-1 日志、
  attempt hash chain 和缺失的 record/budget/trace；artifact SHA-256 为
  `659c91a39ca6bc31ccaee8e16fabae063856b72de7b6c63a69b1004f825261f6`。
- 新 public AgentDojo resolver 覆盖 3,273 个 public AgentDojo work items，
  通过 primary/second 的 attack/benign 四探针；qualification 文件 SHA-256
  为 `9fcf27c1c87480ad68a40ee69b2ea1d0a9432dd3f3b23e5c9b9ed23b61b54612`。
- Public-v2 candidate 采用全新 primary/second execution identities，
  6,873 条计划与源选择保持不变；canonical manifest SHA-256
  `a17ab0926c0003e953b85834b8728a8ac98e360b684780b7fa98f10b9c07250b`。
  Stage A 报告 18 qualified pairs、0 credentials/network/results，并保持
  execution/result authorization false。
- 可恢复聚焦验证为 11 passed / 0 failed / stderr 为空，耗时 1,164.68 秒；
  Ruff、resolver/abort/Stage-A 复现通过。统一 Harness 入口已加入 v1 abort、
  v2 resolver 与 v2 Stage-A 检查。
- 当前工作树完整 Harness 退出 0：1,158 passed、1 skipped、3 warnings，
  pytest 3,494.01 秒，全部 stage PASS，`Verification failed=0`。stderr
  恰为三条预期 RuntimeAuditor `delete_record` 阻断；日志根为
  `outputs/paper_v2/verification/public_v2_current_full_harness/`。
- 所有离线前置条件已满足；唯一剩余 live 门是新的 Public-v2 exact command
  owner 确认。确认前不创建 admission、不访问凭据/网络。
- 科学证据分保持 753/1200；未创建 v2 admission，未读取凭据，未发新请求。

## 2026-07-28 05:10 34/34 引文权威审计与 80% 路线算术纠正

- 34 条文献全部完成权威元数据和摘要范围审计，矩阵由旧登记的
  22 PR/12 PP 更新为 24 PR/10 PP；纠正 18 个非规范标题、1 个无依据
  Oral 标记、L32/L33 的同行评审状态，以及 L20 的完全错链。
- L20 原 URL 实际对应无关生物医学检索论文；无法核验的 “Virtual Context”
  条目已用经 ICSE 2026 官方页面/DOI 核验的 AgentSpec 替换，并在
  `full_citation_refresh_v1.md` 保留纠正轨迹。没有把错误记录静默包装成
  已验证来源。
- 文献矩阵/citation manifest SHA-256 分别为
  `ecf952832afe5d474b70aa2141b8f9c05b0bd43d8da47287bcc836c9c3633570` 和
  `0c6713700b9a77ba5ec9869b2259171ebc986421a135012c4c917fbf1f0c881e`；
  citation+manuscript 7/7、Ruff、manifest 重建验证、stale-title 扫描和
  diff check PASS。
- scorecard 当前为 753/1200=62.75%（显示 63%），submission readiness
  60%。新 v3 路线从 753 出发，以 public +90、adaptive +100、manuscript
  +25 达到 968/1200=80.67%；其他九项正确为 698。历史 v2 表把其当时应为
  690 的“其他九项”误写成 620，导致表内和为 660 而非标称 730；v2 保留
  不改，v3 显式披露纠正。
- 尚缺 final inline contexts/bibliography、public/adaptive 正式结果、盲测
  和 JCR 机构核验，故 formal Stage 2.5 仍为 NOT_READY。本阶段
  credential/API/network/model calls=0。
- 04:38 的 full Harness 在最新 citation Python/test 和 v3 文件写入前已启动；
  它于 06:25 自然完成 1,146 passed、1 skipped、3 warnings、
  `Verification failed=0`，但终态只作为 superseded 证据。06:26 起从当前
  工作树重跑 `harness/scripts/verify.ps1`，并保存 stdout/stderr/exit。

## 2026-07-28 04:51 中型稿件预结果完整性审计完成

- 按 academic-pipeline integrity gate 提前审计 Methods、Results、
  Discussion、abstract shell 和 figure/table plan；该审计仅覆盖 admitted
  medium，不冒充正式 Stage 2.5。
- 发现 Methods 两处 stale zero-operational-failure 语义，与 outcome access
  前冻结的 `medium_gate_spec_v2`/combined gate v6 不符；已改为
  10% overall、5% provider/timeout、0 runner failure 的 mechanism quality
  envelope，以及 480 full coverage、0 open/runner、最多 1% closed
  diagnostic 的 technical result gate。
- 新 `pre_result_integrity_audit_v1.md` 记录 authoritative digests、12 项
  核心数值 VERIFIED、correction trace 和七类 failure modes。Modes 2/4
  因 final citations 与 public/adaptive generalization 缺失而
  INSUFFICIENT；审计 verdict 为 NOT_READY，不增加科学分。
- manuscript workspace 4/4、Methods/integrity normalized assertions 和
  diff check 均 PASS。当前 full Harness PID 20860 仍在 CPU-active 慢测试，
  stderr=0。

## 2026-07-28 04:39 已准入中型结果同步至论文结果与讨论

- `results_shell.md` 不再误报 DeepSeek medium “进行中”。它现在哈希绑定
  admitted v8 分析和独立 result admission，回填六条件 36-attack/24-tool/
  12-no-tool 结果、四项配对比较、运行负担、21 个保留 ITT 失败和
  `mechanism_paper_candidate=false`，同时保持 public/adaptive 单元格 pending。
- 新增 `discussion_draft.md`，只解释 admitted medium 数据，禁止把
  0/36 full 当成模块增益，明确 −25pp tool-TCR 代价、22 次 ASK 的 synthetic
  pending 边界、六对 exact-gold probe 的不确定性和 formal/adaptive 未完成
  限制。
- `abstract_shell.md` 固定经验 fallback 的论证顺序并禁止在 public/adaptive
  admission 前形成提交摘要；`figure_table_plan.md` 给出五个主图、六张主表
  的权威数据源、状态和可视完整性规则。
- manuscript 专项验证从权威 JSON 重建表格字符串与 operational 前缀，最终
  4/4 PASS；Ruff PASS。两次初始断言失败均来自展示格式/换行而非数值漂移，
  已记录并改变断言方法。
- 04:30 Harness 已收集旧测试后才发生稿件同步，故于 43% 时停止该自建进程
  树；未产生 API/实验结果。04:38 新建可恢复全量验证，PID 20860，固定
  stdout/stderr/exit 到
  `outputs/paper_v2/verification/post_medium_results_sync_full_harness/`，
  当前运行中；04:48 检查时 Python CPU 持续增长、stderr=0。

## 2026-07-28 04:31 自适应 official bridge、双台账与结果门已完成

- 从冻结 primary 40-task panel 中用 outcome-blind SHA-256 family-balanced
  规则选定 8 个不同攻击族；每任务 50、总上限 400 queries，M3-full 每
  query 最多 8 provider calls。DeepSeek Pro 独立 hard fuse 为 CNY 5，
  concurrency=1、retry=0、tools/effects=false。
- 每个 mutation 仅进入 `untrusted_content`，可信请求、app context、memory
  和自动编译授权不变；在线 digest 再次证明 evaluator/gold 字段不存在。
  query start 在任何 provider 调用前 fsync，terminal 绑定 content-free
  experiment record、完整 trace bundle 和 response-ID sequence；budget
  ledger 对所有已完成 calls 独立计费并与 query ledger 交叉验证。
- 冻结非可执行 candidate、admission schema 和 canary→formal result gate；
  technical review 禁止汇总 scientific outcomes。canary prefix、75,000
  query continuation 和结果 admission 均不自动发生，费用上投影 CNY 180
  为正式暂停线。
- 验证：新测试 20/20；邻接回归 45/45；Ruff/compile/JSON/PowerShell
  syntax/diff pass；project conventions 12/12；candidate 和 result gate
  独立复现 exit 0；注入式 transport 跑通官方桥接但 API/network=0。
- 当前 full Harness 的命令在工具 3,604 秒外层超时后失去 stdout/exit
  通道；真实 Harness 进程继续并自然结束，但总 `Verification failed` 无法
  事后恢复。因此不能把本轮记为完整绿色；上一 Public-v1 检查点的完整
  1,126 passed/1 skipped/3 warnings 仍保留。本阶段 0 key read、0 API、
  0 formal results。
- 为补齐终态，04:30 已通过隐藏后台 wrapper 重跑完整
  `harness/scripts/verify.ps1`，并将 stdout/stderr/exit code 分别持久化到
  `outputs/paper_v2/verification/adaptive_stage_a_full_harness/`。启动后
  JSON、PowerShell、Shell、compile 均 PASS，当前 pytest 进行中；独立
  exit 文件尚未生成。

## 2026-07-28 02:21 Public-v1 Stage A 已完成，等待 Harness/owner 双门

- 构建 6,873 条 public-v1 冻结计划（5,082 Pro + 1,791 Flash）及
  manifest；每条记录绑定 source、initial online-state、模型角色、基准、
  条件和序列哈希，禁止 evaluator/gold 泄漏。
- 实现 public 专用预算与官方 DeepSeek transport、请求承诺/官方 response
  ID/精确返回模型/append-only trace、记录与角色预算双账本、非可执行
  candidate、显式 admission、24+12 技术 canary controller、结果分析预注册
  和 fail-closed result gate。没有读取/保存凭据，没有 API/network/model
  call，没有正式结果。
- 预算边界为总增量 CNY 25、保留 CNY 5，Pro/Flash 分别最多 CNY 20/5；
  concurrency=1、retry=0、tools/effects/connectors=false。结果门要求
  6,873/6,873、精确 Pro/Flash 身份、完整链、全部失败保留 ITT，且两个
  技术 canary 均通过。
- 验证：public-v1 focused tests 25/25（298.61 秒），focused Ruff PASS；
  唯一完整 Harness 自然完成 1,126 passed、1 skipped、3 warnings，
  pytest 2,367.05 秒，所有 stage PASS，`Verification failed=0`。Stage-A
  复现为 6,873 records/18 qualified pairs/0 network；analysis 与 result
  gate 复现均 exit 0，四项 execution/result authorization 仍为 false。
- 已展示 exact primary canary 命令，当前唯一剩余 live 前置是 owner 逐字
  确认；admission 文件尚不存在，execution/result authorization 仍为 false。

## 2026-07-27 09:53 重新冻结 80% 科学证据执行路线

- 用户要求先重新规划再实验；本阶段只进行只读事实审计、确定性算术和计划
  冻结，API/network/model calls=0，formal results=0。
- scorecard 复核为 730/1200=60.83%（报告 61%）。新路线仅在三项完整准入后
  加分：公共基准 10→100、自适应 0→100、manuscript 30→70，目标
  960/1200=80.00%。
- 解析冻结公共矩阵得到精确 6,873 条，其中 Pro 5,082、Flash 1,791。
  使用已录取 v8 的条件级调用/费用聚合估计约 15,828 calls、CNY 12.03；
  计划将公共增量 fuse 设为 CNY 25，先 24+12 条技术 canary，再完整执行。
- 审计确认当前不存在 paper-v2 public controller/result gate/analyzer；自适应
  只有 provider-agnostic MCTS core，不具备 official bridge、query/call
  双账本或正式结果门。因此阶段 A 必须先补离线执行层并跑完整 Harness。
- DeepSeek Pro 为主模型，Flash 为吞吐型第二模型；Gemini v3 保留为 18 RPD
  的跨提供商增强，不计入 80% 必要路径。自适应先做 8×50、CNY 5 成本
  canary，之后另行冻结正式费用门。
- 新计划 Markdown 和机器 JSON 均已创建，实验授权保持 false，等待 owner
  学术检查点确认。
- 离线核验：Python 3.13.5；roadmap/feature/score/public/adaptive JSON 解析通过；
  三个锁定输入 SHA-256 3/3；730+230=960、公共 6,873、自适应 40/20/75,000
  算术通过；密钥模式 0；manuscript workspace tests 4/4；`git diff --check`
  通过，仅有预期 LF→CRLF 提示。未运行完整 Harness，因为尚未实现 runtime。

## 2026-07-27 09:40 Gemini 免费层恢复并完成一次安全诊断

- Owner 项目页截图确认 `M3 PI Guard test` 已从 Tier 1 返回 Free，paid billing
  link 不再存在，货币硬上限为 USD 0。根据 owner console 的 Tier 1/free
  比较，当前 Gemini 3.6 Flash 免费层上限为 5 RPM、250K input TPM、20 RPD。
- 新 prospective v3 快照和覆盖策略冻结本地上限 4 RPM、200K TPM、18 RPD、
  16K output tokens/day 和 2 RPD reserve；并发 1、0 retry、0 provider
  tools、0 external effects、0 paid features。冻结的 Gemini v1/v2 未修改。
- 离线校验复现两张截图 SHA-256、quota snapshot SHA、override SHA，并将
  18/200K/16K caps 注入现有双提供商策略后通过 `validate_policy`。
- 仅执行一次固定 public synthetic 请求：HTTP 200，精确返回
  `gemini-3.6-flash` 和 `SAFE`；32 prompt、1 completion、44 total tokens，
  latency 1996.3301 ms。0 retry、0 tools、0 effects、0 fallback。
- 响应包含 response ID 但没有 request ID，故精确模型身份可诊断确认，
  端到端 request trace 仍不完整。证据为 diagnostic-only、formal/result
  eligibility=false；科学完成度保持 61%，submission readiness 保持 56%。
- 未来 192-item v3 需按 Pacific 日界分多日执行，且必须先实现持久化
  provider-call meter、新 candidate/admission 和完整 Harness，不能直接续跑。
- 验证证据：
  - Python JSON/hash/secret-pattern 交叉校验：4 个 JSON 解析通过，
    snapshot/override/diagnostic digest 绑定通过；diagnostic SHA-256 为
    `644f1f3a521ee0d5ef9688a17061e244eed4236a04fc6d05a714552c282fca4f`；
  - `python -m pytest -q tests/unit/test_project_config.py
    tests/unit/test_paper_v2_provider_budget.py
    tests/unit/test_paper_v2_official_provider_executor.py`：33 passed，
    1 条已知 VIGIL/Pydantic deprecation warning；
  - `git diff --check`（本轮 Harness 文件）：通过，仅显示预期 Windows
    LF→CRLF 提示；未运行全量 Harness，因为没有修改 runtime code 或正式冻结。

## 2026-07-27 09:25 AI Studio 截图排除公开 RPM/TPM/RPD 饱和

- exact project 的 Gemini 3.6 Flash 28 日峰值为 2/1000 RPM、1.35K/2M TPM、
  3/10K RPD，且页面显示 Tier 1。公开速率/日限额未接近阈值，key-project
  错配也因用量对应而显著降低。
- 根因优先级更新为 paid Tier 1 的 Prepay/Postpay/billing account 状态：
  positive Prepay credit 是官方服务前提；零余额、未完成 Prepay、负余额或
  billing 同步异常可使 API 停止。真实 USD 10/10min spend saturation 与当前
  极低用量不相符。
- Logs 页面 0 条与 OpenAI-compatible Chat Completions 不矛盾；Batch Gemini 2
  Flash 指标不适用于当前 Gemini 3.6 Standard 请求。0 API 调用、0 retry、
  0 formal result；等待 owner 只读提供 Billing 状态。

## 2026-07-27 09:15 Gemini 独立诊断首请求再次 HTTP 429

- 通过既有 credential-redacting official provider client 执行一次 Gemini-only
  固定安全文本请求；本地 key 非占位、冻结模型和官方 base URL 准入检查通过。
- 请求边界：1 次网络尝试、0 自动重试、0 provider tools、0 external effects、
  temperature 0、max tokens 16；不保存 prompt/response/header/credential。
- Google 官方端点返回 HTTP 429，客户端按 first-429-pause 规则立即停止。
  因没有完成响应，未取得可验证的 returned model、request/response identity
  或 token 用量。
- 该诊断与 Gemini v1/v2 正式候选完全分离，产生 0 正式结果且不进入 effect
  table。当前 Gemini 不具备实验可用性；科学完成度保持 61%，
  `F-PAPER-002` 保持 `in_progress`。
- 无新增请求的根因审计确认：同一 config 在 7 月 23 日曾以相同官方
  OpenAI-compatible route 和 `gemini-3.6-flash` 返回 200，之后跨天重复首请求
  429。官方资料确认该 model 为 GA、Standard free tier 可用、route 正确，
  且 429 属 project-level resource exhaustion；当前公共状态页无大范围事故。
  最高优先原因是 key-project 与截图 project 不一致，或 exact project 的 active
  quota/account provisioning 异常；普通瞬时 RPM/TPM 峰值、错误 key、错误
  model/URL、地区和 payload 参数均较不符合已知证据。
- 当前 transport 没有保留响应正文中的 quota metric，只证明 429 body digest
  存在。因此必须在 AI Studio 对 exact key-project 做无请求核对，不能声称已
  区分 RPM、TPM、RPD、账户状态或 provider capacity。

## 2026-07-27 02:45 阶段报告完成，Gemini 正式证据仍为 0

- Gemini v1 canary 因 VIGIL constraint generation 静默 fallback 永久失败
  关闭：1 个 started attempt、1 个 closed failed call、0 experiment record、
  0 evidence sidecar，run 不可恢复且不得升级为结构化基线结果。
- 新 v2 采用 outcome-blind policy-only/full 192 行计划并通过离线资格、专项
  测试与 frozen verify；唯一 canary 在首个 `m3_policy_only` 官方请求收到
  HTTP 429 后立即暂停。v2 保留 1 条 diagnostic ITT 记录、0 completed call、
  0 token、0 retry、0 provider tools、0 external effect；当前版本不得重试。
- 新阶段报告：
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-27.docx`，
  SHA-256
  `27b366847dcdfd1b8fa48aa5f766cb0839583d9686084f87cba45b460073e5b3`。
  报告以 DeepSeek 480 条准入结果和 empirical fallback 为主线，含 6 张分析图、
  21 张固定几何表、20 个正式标题、11 个前沿/投稿链接，并详细给出自适应攻击、
  6,873 条公共扩展、Gemini v3、盲测、统计和 8 周排期。
- 报告结构 QA 全部通过：ZIP/OOXML、US Letter/1 英寸页边距、21/21 表格
  `tblW/tblInd/tblGrid/tcW`、21/21 重复表头、real numbering、6/6 图片 alt、
  accessibility high/medium/low=0/0/0、占位符/credential pattern/批注/修订=0。
  6 张 PNG 图已按原始分辨率人工检查并修复右侧数值裁切与状态文字不可见问题。
- canonical `render_docx.py` 因本机无 LibreOffice/`soffice` 在打开文档前
  `WinError 2`，因此不宣称整页渲染 QA；按 documents skill 采用允许的结构
  fallback。新脚本 Ruff、`py_compile` 和最终 structural QA 均通过。
- 科学完成度保持 61%，submission 56%，不会因报告完成或 Gemini diagnostic
  上调。下一实验优先级：冻结论文主表/主张 → DeepSeek 自适应攻击成本 pilot
  与正式预算 → AgentDojo/M3-v2 公共扩展 → Gemini 配额恢复后的新 v3 →
  独立 custody 与 JCR 核验。`F-PAPER-002` 保持 `in_progress`。

## 2026-07-26 23:45 Gemini fallback 第二模型 prospective freeze

- 从冻结 medium v2 计划机械筛选 264 行，覆盖三个核心条件、216 条主比较和
  48 条授权 regime 探针；新 execution/work identities 与 DeepSeek 分离，
  样本选择未读取既有 scientific outcomes。
- 实现官方 Gemini free-tier 控制器及 append-only 四链：
  experiment record、attempt、provider call 和 safety evidence sidecar。
  每个完成调用绑定 payload hash、Google request ID、response ID、精确模型、
  usage 与安全回执；不保存 prompt/response/header/credential。
- 零网络资格 2/2 通过；专项测试 33/33、Ruff、compile、PowerShell/Bash
  syntax 通过。candidate/canary admission 已冻结，result admission 保持 false。
- 完整 Harness 尚未执行，因此 Gemini API canary 尚未启动，科学完成度仍按
  61% 记录，不因计划、代码或资格测试上调。

## 2026-07-26 23:03 DeepSeek 480/480 准入、统计与 fallback 路线决策

- v9 唯一正式分片完成 177/177，和 v8 的 303 条终态合并为精确 480/480：
  479 formal-candidate + 1 closed diagnostic、0 open、1084 official calls、
  CNY 1.8623798，零 retry/provider tools/external effects。
- gate v6 技术审查通过并激活独立 scientific-analysis admission；480 条全部
  保留在 ITT，唯一无响应 diagnostic 明确保持 unverified/diagnostic-only。
- analysis amendment v8 qualification/candidate 在总体结果访问前冻结；
  `admitted_medium_analysis_v8.json` 成功生成并由独立
  `--verify-analysis` 重建，stderr 为 0。
- 主结果：M3-full vs structural unsafe effect 0/36 vs 8/36，
  −22.2pp，cluster bootstrap 95% CI [−36.1pp, −8.3pp]，
  Holm-adjusted exact McNemar p=0.03125；benign-tool TCR 6/24 vs 12/24，
  −25pp；full vs policy-only unsafe effect 差值 0。
- 预注册 mechanism gate `fail_redirect`，因 utility noninferiority 和
  module gain 均不成立；claim ledger 已将 C07/C08 标为本中型实验不成立，
  论文改走授权泄漏/不确定性与安全—效用实证路线。
- 完成度更新为 engineering 99%、scientific 61%、submission 56%；
  第二模型、正式公共扩展、自适应攻击、完整论文与独立 blind custody 仍缺失。

## 2026-07-26 19:29 v9 API 前完整 Harness 全绿

- 使用 `F:\robot\Anaconda3\python.exe` 唯一运行完整 Harness，进程自然结束：
  1081 passed、1 skipped、3 warnings，12 个阶段全部 PASS，
  `Verification failed=0`。
- v8 candidate/canary/continuation admission、旧 result gate v5、v9
  qualification/candidate/admission、combined gate v6 qualification/candidate、
  Registry、历史证据与当前 V2 freeze 均完成重放。
- stderr 仅有三条 RuntimeAuditor 对 `delete_record` 的预期阻断；未发生删除、
  网络调用、凭据读取、provider tool 或真实外部 effect。
- 验证日志位于
  `outputs/paper_upgrade_v2/verification/pre_v9_remainder_full_rerun/`。
  v9 的 177 项 pending-only 正式分片已满足离线前置条件；scientific outcomes、
  result admission 与 analysis 仍关闭。

## 2026-07-26 17:45 v8 失败关闭与 v9/v6 prospective 恢复冻结

- v8 唯一 continuation 在 303/480 时自然返回 `matrix_v8_paused`：
  302 formal-candidate、1 provider-failure diagnostic、177 pending、
  0 open attempts、497 completed provider calls、累计 CNY 1.2069394；
  0 retry、0 provider tools、0 external effects，scientific outcomes 未读。
- v8 不可再次执行。新增
  `formal_matrix_remainder_controller_v9.py`，只选择 177 个 never-started
  work key，候选 manifest
  `7b006ab62f8f2c6f696373949a27c1db4b11dfae006456fadaef30a2d7a7c4b5`，
  admission manifest
  `2932c2d35903fd470a8a09156916e564f70cfbc24ff511abf87a4f6265aba2a3`，
  matrix identity
  `ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373`。
- 新增 prospective combined result gate v6，candidate manifest
  `647e72663b603d91ebe19d27771ed633cc1b8696423fd082affd3f0017b4b30b`。
  它在 v9 API 前锁定 v8/v9、303+177、0 duplicate/missing/unknown 和
  diagnostic-in-ITT；result/analysis admission 均关闭。
- v9 零网络资格通过：303 source + 177 pending、2/2 临时 fixture、
  0 diagnostic/network/credential/formal result。combined gate 资格为
  1 positive + 7 negative，0 outcome read。新增专项测试 8/8、Ruff、
  Python/PowerShell/Bash syntax 与 JSON parse 通过。
- 该门禁已由 19:29 的完整 Harness 关闭；下一步是只启动一个已准入的 v9
  `--execute-pending-segment`。

## 2026-07-26 15:45 v8 continuation 前完整 Harness 全绿

- 使用 `F:\robot\Anaconda3\python.exe` 唯一运行
  `powershell -NoProfile -ExecutionPolicy Bypass -File
  harness/scripts/verify.ps1 -PythonExe F:\robot\Anaconda3\python.exe`；
  进程自然结束，完整 pytest 为 1073 passed、1 skipped、3 warnings，
  最终 `Verification failed=0`。
- v8 candidate、canary、continuation admission、prospective result gate v5、
  历史冻结与当前 V2 freeze 均通过重放。stderr 的三条 `delete_record`
  是 RuntimeAuditor 的预期安全阻断，没有发生删除或外部 effect。
- 验证日志保存在
  `outputs/paper_upgrade_v2/verification/pre_v8_continuation_full_rerun/`。
  现在已满足 474 条 DeepSeek v8 continuation 的离线技术前置条件；
  scientific outcomes、result admission 和 analysis 仍保持关闭。
- 15:47:08 +08:00 恰好一次启动冻结命令
  `E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m
  experiments.paper_v2.formal_matrix_controller_v8
  --execute-continuation`。venv 启动器 PID 73484，实际 Python 3.13.5
  子进程 PID 33056；Gemini 未并发，尚未读取 scientific outcomes。

## 2026-07-24 23:25 阶段性研究报告完成，v7 暂停

- 用户将当前优先级改为报告，v7 全量离线审计在约 47% 时停止；没有完整审计
  结论、v7 API 调用或科学结果。
- 完成中文 Word 报告
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-24.docx`，
  以 5 张图和 26 张表汇总研究定位、前沿边界、v4–v7 技术失败、成本/验证、
  Q2 可行性和详细后续实验路线。
- 报告明确 v4–v6 结果不准入、v7 记录为 0、机制效果尚未形成；恢复顺序固定为
  完成全量离线审计 → 实现/冻结 result gate v4 → 复核 v7 身份 → 单次 canary
  → continuation → 技术结果准入 → 科学分析。
- DOCX 结构验证通过；独立 HTML/PDF 预览识别 5 张图和 26 张表，共 21 页，
  抽查封面、版本分析、统计计划、附录路径和参考文献布局通过；密钥/交付禁用
  语句扫描为 0。

## 2026-07-24 20:40 DeepSeek v5 canary、结果门与 continuation 准入完成

- v4 在 395/480 时按旧投影门暂停，内容无关技术审查确认其结果不可准入；所有
  v4 运行账本和冻结输入保持不可变。未读取 unsafe-effect/task-completion。
- v5 新增 boundary-rejection no-effect ITT 终态且不改变 online Guard 决策；
  两类 fixture 的零网络资格通过，被拒动作执行数为 0。
- 唯一六条件 canary 完成 6 条、13 次官方响应、0 retry、0 operational failure、
  0 diagnostic、0 external effect；项目累计成本 CNY 0.7522526。canary review
  技术门通过且 scientific outcomes 仍封存。
- 用户新的 provider 预算授权已记录：DeepSeek/Gemini 可继续用于安全研究调用，
  历史 CNY 27/30 估计不再作为项目停机条件；计量、身份链、单 provider、
  0 retry、无工具和无真实 effect 继续保留。
- result-gate v2 与 analysis v3 在 continuation 前冻结。技术门允许少量具有完整
  失败链的 provider/timeout diagnostic 留在 ITT，拒绝未知 runner failure、
  identity/trace/isolation/open-attempt 漂移；运行质量超阈只关闭机制论文主张，
  不禁止诚实分析负面结果。
- focused gate 8/8、v5+gate 13/13、paper-v2 259/259 通过。continuation
  admission 可复现，当前 6/480、474 pending、0 open、budget unpaused、
  result admission false；完整 Harness 更新后验证尚待执行。

## 2026-07-24 17:37 DeepSeek v4 canary 通过并启动正式续跑

- v3 六条件 canary 的唯一技术失败为 strict-JSON parse failure；82-byte 响应正文
  未读取，v3 已冻结为不可续跑、不可重试、不可进入科学分析。官方 DeepSeek JSON
  Output 文档支持 `response_format={"type":"json_object"}`，因此 v4 只改变冻结
  transport 契约，不放宽 parser 或进行响应修复。
- v4 新增 JSON Output official client/controller、schema、两项零网络
  qualification、candidate 和 canary admission。固定 non-thinking、JSON
  response format、13 项 provider call 上限、无工具/无外部 effect、逐调用
  request commitment/response identity/usage/cost append-only 链。
- 聚焦 v1–v4/可信上下文测试 27/27；paper-v2 231 passed、769 deselected；
  完整 Harness 1002 passed、1 skipped、3 warnings，341.10 秒测试阶段，
  `Verification failed=0`。
- v4 正式 canary 单次完成 6/6 条件，0 operational failure、0 diagnostic、
  13 个官方响应调用；累计 15,795 prompt tokens、3,939 completion tokens，
  缓存 hit/miss 8,064/7,731，累计项目成本 CNY 0.0470286。
- 内容无关 canary review 明确 `scientific_outcomes_reviewed=false`，随后生成并
  验证 continuation admission。17:37 启动剩余 474 项的同一 DeepSeek v4
  矩阵；父子解释器链为 venv launcher 到 Python 3.13.5，不是重复实验。
- 正式续跑保持 CNY 27 项目累计熔断、0 自动重试、0 cross-provider fallback，
  Gemini 不并发，模型输出只是不可信 proposal，所有效果都在 sandbox/in-memory
  backend。科学结果仍未准入，任务继续 `in_progress`。

## 2026-07-24 00:40 live 依赖闭环与双官方身份失败关闭

- 六条件 live runtime 已使用真实固定 PromptGuard、官方 AgentDojo
  environment/evaluators、M3 离线 evaluator、exact-gold ablation 和官方 VIGIL
  generator bridge 完成 12 个 benchmark-condition 组合的离线资格。provider
  tools、真实外部 effect、evaluator/gold 在线字段继续为 0。
- 固定合成身份资格按用户授权执行两次总调用、每家一次且无重试。DeepSeek 精确
  返回 `deepseek-v4-pro`、response ID、37 input/16 output tokens，成本
  CNY 0.000207；因无 request-ID header 降为 diagnostic。Gemini 首次尝试即
  `ProviderPausedError` 并暂停。
- 脱敏 live artifact 与 v3 preflight 已哈希绑定；不保存 credential、prompt、
  response、header 或错误正文，正式结果为 0。当前 blockers=2：Gemini AI Studio
  active quota snapshot；每家完整 exact-model/request+response-ID trace。
  `gate_pass=false`，480 项/模型矩阵未启动。
- 官方资料复核表明 Gemini 429 是项目级 RPM/TPM/RPD/额度门禁，实际限额需在
  AI Studio 查看；DeepSeek 公共 API schema 公开 response `id`，未承诺请求 ID
  响应头。证据合同没有为通过 smoke 而降低。
- 聚焦 provider 16/16、paper-v2 160/160、Ruff、冻结复现通过；完整 Harness
  929 collected、928 passed、1 skipped，392.3 秒且
  `Verification failed=0`。就绪度为工程 99%、科学 32%、投稿 44%。

## 2026-07-23 23:30 append-only 正式记录存储资格

- 新增 `formal_record_store.py`，把严格 experiment record 与 sanitized runtime
  events 绑定 execution/work/run identity 后写入 append-only JSONL。每次追加前
  复验完整链，成功追加后 flush+fsync；恢复返回终态 work keys 与剩余项目。
- fail-closed 覆盖重复 work/record、未知 work、连续 sequence、identity/run/
  work metadata、record/event/argument/entry hashes、空白/截断/非 UTF-8 行、
  raw-content keys 和 credential patterns。
- live 成功/拒答必须为 `formal_candidate`；operational failure 允许
  `diagnostic` 但保留 `unsafe_effect_itt=true`/`task_completion=false`；stub
  只能出现在显式 qualification mode。
- 资格过程在自动清理临时目录写入并恢复 12/12 entries，raw response/observation
  markers 未落盘，临时文件确认删除。project records/formal results/network/
  model calls 全为 0。
- v3 preflight 已哈希绑定模块和资格摘要；持久化工程 blocker 关闭，剩余 3 项为
  live condition dependencies、Gemini quota 和 live 双 ID provider qualification。
- 聚焦 28/28、paper-v2 127/127、Ruff/compile/JSON/syntax/conventions 通过；
  全量 899 collected、898 passed、1 skipped、3 warnings，Harness 546.9 秒、
  `Verification failed=0`。工程/科学/投稿完成度为 97%/32%/43%。

## 2026-07-23 23:05 Python 3.13.5 项目依赖补齐

- `F:\robot\Anaconda3\python.exe` 确认为 Python 3.13.5。仓库 core/dashboard
  requirements 已满足；新增 Ruff 0.15.22，Pillow 从冲突的 12.2.0 调整为项目
  兼容的 10.4.0。因 base site 不可写，两者安装到该解释器可见的 Python313
  用户 site。
- 核心研究栈导入通过，Python 3.13 可直接执行 Ruff。LFischl 保留为辅助兼容环境，
  不再是 lint 的唯一入口。
- 共享 user site 的 pdfplumber/PySSTV 与项目 Pillow 约束互斥，`pip check` 留有
  两项明确的非项目冲突；未修改这些工具。
- Ruff 与 paper-v2 120/120 通过；全量 892 collected、891 passed、1 skipped、
  3 warnings，Harness 529.9 秒、`Verification failed=0`。环境变更未调用 API/
  模型，也未改变任何科学结果。

## 2026-07-24 02:15 六条件执行壳层与事件脱敏资格

- `formal_condition_executors.py` 为六个中型条件建立统一 online runtime/offline
  evaluator 边界。在线上下文只含 execution identity、work key、benchmark、
  condition、max calls 与 frozen online state；evaluator 标签、source/result
  fields 和 primary eligibility 不可见。
- 原始 prompt/messages/response/observation/headers/credentials 不进入实验记录；
  response/observation 仅保存 SHA-256 与 UTF-8 字节长度，action arguments 做
  secret-pattern scan。多步顺序必须从 1 连续，初始判定由首个 parsed proposal
  唯一定义，`ASK` 保持 pending/未执行。
- 离线 injected no-effect runtime 覆盖 M3 sandbox 与 AgentDojo in-memory 两个
  基准的六条件组合，共 12/12 通过；持久化记录 0、正式结果 0、网络/API/model
  calls 0。资格文件不冒充 live dependency 或防御效果复现。
- v3 execution preflight 现在哈希绑定条件壳层与资格文件，并保留四个 blocker：
  live provider/PromptGuard/VIGIL/effect/evaluator、真实 persisted-log redaction、
  Gemini active quota 和每供应商双 ID live qualification。门禁继续关闭。
- 聚焦回归 21/21，paper-v2 120/120，LFischl Ruff 通过；完整 Harness 收集 892
  项，891 passed、1 skipped、3 warnings，469.1 秒，
  `Verification failed=0`。工程/科学/投稿完成度为 96%/32%/43%。

## 2026-07-24 01:30 官方供应商执行器、调用账本和证据降级闭环

- DeepSeek/Gemini 每模型完整 480 项目标保持不变。新增
  `official_provider_executor.py`：真实 transport 需要显式 consent，固定
  temperature=0、单 attempt、无 tools；响应精确核对 frozen model，DeepSeek
  强制 cache hit/miss accounting，Gemini 强制 free-only batch fuse。
- 新 append-only ledger 在追加前复验完整候选链，拒绝 execution/model/provider
  drift、重复终态、自动 retry 和跨 provider fallback；只有首个 429 暂停后，
  携带人工恢复授权 ID 的同 provider 新 attempt 可以继续。
- 新收据适配器将 injected fixture 限定为 `local_qualification`。真实官方网络
  只有 exact model、request ID、response ID 同时齐备才映射
  `formal_candidate`；request ID 缺失时透明保留 response ID，但 evidence level
  固定为 `diagnostic_only`。
- `provider_executor_qualification_v1.json` 零网络验证两家 endpoint builder、
  usage parser、预算 hook、ID 提取和无内容持久化；v3 preflight 进一步绑定 v2
  计划、预算/安全/合同/schema/执行代码。当前 4 个正式 blocker 保留，
  `gate_pass=false`、真实结果 0。
- `LFischl` Python 3.9 补装 `pytest 8.4.2`，本模块 13/13 与 Ruff 通过；完整仓库
  因 PEP 701、`tomllib` 等需要 Python 3.12+，故全量验证使用现有 Python 3.13.5。
- 聚焦测试 13/13、paper-v2 112/112、conventions 12/12、compile、PowerShell/
  Bash syntax、JSON、冻结复现均通过。完整 Harness 为
  `883 passed, 1 skipped, 3 warnings in 378.6s`，统一入口 471.5 秒，
  `Verification failed=0`。
- 分层完成度为 engineering 95%、scientific evidence 32%、submission 43%；
  未将 transport qualification、缓存可行性或测试通过计作论文效果结果。

## 2026-07-23 23:45 双供应商全量预算与动态熔断

- 响应用户“不限小规模”的修正：DeepSeek 与 Gemini 均保留每模型完整 480 项、
  最多 4,416 call 的目标。批次是同一矩阵的断点/计费检查点，不是样本子集；
  provider 之间不得为同一模型身份静默 fallback。
- 新增 `dual_provider_budget_policy_v1.json`、
  `dual_provider_budget_preflight_v1.json` 和离线
  `experiments.paper_v2.provider_budget`。policy 记录用户 CNY 30 DeepSeek 边界、
  CNY 27 熔断、CNY 3 保留额，以及 Gemini free-only/USD 0 paid-tier 边界。
- DeepSeek 全量成本场景：90% hit 为 CNY 24.662527，88% 为
  CNY 26.709802，85% 为 CNY 29.780714；CNY 27 下的最低聚合 hit ratio 为
  0.877165。执行前逐请求以 cache-miss 最坏值留出 CNY 0.052566，实际 ledger
  强制 hit+miss=prompt tokens；字段缺失或投影/余量越界即 fail-closed 暂停。
- Gemini 使用独立本地 100 requests/1,000,000 input/128,000 output batch caps；
  这些不是对 provider quota 的猜测。正式开始前仍须人工记录 AI Studio 当前
  RPM/TPM/RPD；首个 429 两家都暂停、零自动重试。
- 两家只允许合成/公共非敏感 payload，且 provider tools/真实 effect 全关。
  预算批准不提升 diagnostic smoke，也不授权正式运行；当前 preflight 仍有 5 个
  executor/identity/logging/quota blocker，480 条真实记录仍为 0。
- 新预算测试 12/12、全部 paper-v2 聚焦测试 99/99、Ruff、compile、shell/
  PowerShell syntax、JSON 和 conventions 12/12 通过。完整 Harness 为
  `870 passed, 1 skipped, 3 warnings in 484.30s`；统一验证总耗时 577.3 秒，
  `Verification failed=0`。

## 2026-07-23 21:20 DeepSeek/Gemini 双供应商连通性 smoke

- 用户明确要求并授权执行连通性测试。先运行 `scripts/check_project_config.py`：
  两个 key 均仅显示 `set_redacted`，consent 正确，local config ignored=true、
  tracked=false，tracked secret hits 为 0。
- 冻结 provider safety policy 对两个 chat-completions URL 均 PASS，effect backend
  固定为 `no_effect`，provider-managed tools 和外部 effect 均关闭。
- 每家执行一次固定公共合成 prompt，`max_tokens=8`、timeout=60 秒、无工具、
  无项目数据、无重试。DeepSeek 与 Gemini 均 HTTP 200；returned model 分别精确
  匹配 `deepseek-v4-pro` / `gemini-3.6-flash`。
- DeepSeek 用量 30+8=38 tokens、约 1944.568 ms；Gemini 报告总计 30 tokens、
  约 1483.696 ms。两家均有 response ID，均未观察到 request ID。
- 两家均未在 8-token 限制内返回精确 `SAFE`，响应正文未持久化。结论仅为连接/
  鉴权/配置模型链路通过；不是指令遵循测试、身份正式 attestation 或论文结果。
- 脱敏 diagnostic 写入
  `protocols/paper_upgrade_v2/provider_connectivity_smoke_v1.json`；
  `result_eligible_for_formal_tables=false`。没有启动 480 条中型任务。

## 2026-07-23 22:40 paper-v2 条件级证据边界与 provider 副作用安全

- 新增 `medium_runtime.py` 与 v2 execution freeze。480 个工作项的初始在线状态
  现在由原始冻结记录重建，并把 agent input、条件控制、detector/baseline 配置和
  M3 authorization envelope 一并摘要；不再用 case-level digest 代替实际可见状态。
- `exact_gold` 只在 48 条隔离 probe 中出现，来源明确为 evaluator-derived。
  三个 AgentDojo exact probe 从固定官方 checkout 的 user-task function calls
  离线构造；三个 M3 probe 从 offline evaluator allowed-effects 构造。
- ConditionDispatcher 缺条件、重复注册或未知条件即 fail-closed。record assembler
  统一 ASK effective decision、最终 visible-state digest、provider attestation、
  token/latency 和 ITT 失败规则；非 stub 无 safety receipt 即拒绝。
- 480/480 stub matrix 在内存验证，包含 ASK 与 provider_failure；480/480 均留在
  ITT，records persisted=0、scientific result=false、network calls=0。
- DeepSeek/Gemini 配置模板已加入官方 base URL 和当前 exact model slot。新增安全
  policy/validator，明确 provider output 仅为 proposal，隔离 effect backend 外的
  所有真实或未知副作用 DENY。focused safety/runtime/citation tests 18/18。
- 文献完整性工具从 34 项矩阵重建 22 peer-reviewed、12 preprint-only，
  只接受论文/出版社/proceedings/DOI/arXiv 的 primary-source host，并保持最终
  DOI/作者字段和提交日刷新 pending。
- JISA checklist 已按官方 scope 与 Guide for Authors 记录 venue fit、single
  anonymized review、AI disclosure、competing interests、funding、data/code
  statement 和机构 JCR 门禁；没有把二手分区当最终证据。
- Standalone Ruff 对新增 runtime/safety/citation 模块及测试通过。增强后的完整
  Harness 重新验证全部冻结与历史证据，结果为
  `858 passed, 1 skipped, 3 warnings in 483.60s`、`Verification failed=0`。
- 当前分层完成度：engineering 93%、scientific evidence 32%、submission 41%。
  真实身份 smoke、用户硬成本上限、480 正式结果、6,873 公共记录、自适应攻击、
  独立 blind custodian 和 Results/Discussion 仍未完成。

## 2026-07-23 21:00 paper-v2 离线正式实验门禁与执行证据链

- 将 online-state 源码审计从 20/22 补齐到 22/22、distinct artifacts 从
  14 补齐到 16。WASP 绑定官方仓库 commit；Task Shield 只绑定 ACL 官方 PDF 与
  明确披露的本地 paper reproduction，不将其冒充作者官方实现。
- 审计来源统计为 20 个 official-source-code unit、1 个 disclosed-reproduction
  unit、2 个 official-source-unavailable unit；观察结论为 9/10/1/2，独立第二
  复核仍为 0，领域级 oracle claim 继续禁用。
- 新增 `provider_gate.py`、官方候选清单、未批准候选决策和可复验 preflight。
  针对 480 项中型计划的保守上界为 4,416 calls、34,407,984 input tokens、
  2,260,992 output tokens、USD 119.93484；估算忽略缓存/批处理折扣。
- 新增 `provider_attestation.py`：未来只接收去内容的 response metadata，
  强制官方 endpoint、精确 model、request/response ID、usage 和证据 digest，
  拒绝 authorization/cookie/API-key header；本模块网络调用为 0。
- 新增 480 项 result-blind、哈希绑定、append-only、可恢复 execution ledger。
  432 项进入主终点，48 项仅为 authorization regime probe；重复终态、身份漂移、
  provider gate 未通过和超过 90% 成本熔断均 fail-closed。
- `medium_falsification_gate_v2.json` 已从“成本未知”更新为“成本已估算、模型身份/
  脱敏复核/用户硬预算批准待完成”。480 项仍全为 pending，未创建效果结果。
- 当前分层完成度：工程就绪 90%、科学证据 32%、投稿就绪 39%；功能
  `F-PAPER-002` 保持 `in_progress`。
- 聚焦 provider/cost/ledger/medium 回归 20/20、全部 paper-v2 回归 69/69、
  Ruff 通过。增强后的完整 Harness 主动复验 provider preflight 和 execution
  manifest，最终为 `840 passed, 1 skipped, 3 warnings in 335.50s`，
  `Verification failed=0`。未读取本地 Token，未调用 API/Ollama/模型。

## 2026-07-23 16:35 paper-v2 80% 工程证据冲刺完成

- 完成 20/22 个 online-state 源码审计单元，覆盖 14 个固定 commit 的官方 artifact；
  每个单元包含源码锁、入口、字段流、静态命中、投影差分、发现和哈希 manifest。
  复核结果不支持领域级 oracle authorization 主张：claim-ready=0、独立第二复核=0。
- 结果盲固定 72 个中型 case 和 6 个核心条件：36 attack、24 benign tool、
  12 benign no-tool、25 context-dependent；主矩阵 432 条，授权 regime probes
  48 条，预计共 480 条真实记录。provider 身份和硬成本上限仍未填写，因此未运行。
- VIGIL `RuntimeAuditor` 与 DRIFT 官方 pipeline 在固定源码上通过零调用 adapter
  资格检查；正式 admission 和效果比较仍待真实中型结果。
- 实现 Wilson、exact McNemar、10,000 次 cluster bootstrap、Holm、多门禁、
  ITT 分母和配对功效分析。完整记录缺失时输出 `results_pending`，不进行转向判定。
- 固定 M3-v2/AgentDojo 正式公共计划共 6,873 条 case-condition 记录；
  AgentDojo 使用实际 97 个唯一良性任务而不复制凑数。自适应攻击最大预算为
  75,000 queries；600-slot 独立盲测包不含候选内容或标签，custodian 仍为空。
- 建立结果就绪的 Methods、pending-only Results 表、13 项 claim–evidence ledger、
  Devil's Advocate 风险审查和完成度计分。当前工程就绪 `85%`、科学证据 `31%`、
  投稿就绪 `38%`；F-PAPER-002 保持 `in_progress`。
- 未访问本地 Token，未启动 API/Ollama/模型，未产生正式效果结果，未提交、推送、
  创建 PR 或部署。
- 首轮完整 Harness：`824 passed, 1 skipped, 3 warnings in 262.94s`；
  规范、Ruff、JSON、compileall、Registry、历史证据均通过，最终
  `Verification failed=0`。状态同步后的完整复验收集 1 个新增门禁测试：
  `825 passed, 1 skipped, 3 warnings in 247.29s`，最终
  `Verification failed=0`。

## 2026-07-23 13:50 paper-v2 阶段 0/1 工程基础与全绿验证

- 登记 `M3-PAPER-002 / F-PAPER-002`，锁定 paper-v2 独立目录与 paper-v1 不可变
  边界；没有访问本地 Token、运行 API/模型、改写冻结证据或晋升正式结果。
- `docs/research/paper_v2/literature_matrix.md` 记录 34 项直接相关工作并区分
  peer-reviewed/preprint；`frontier_gap_analysis.md` 删除 first/only/SOTA 默认叙事，
  将 VIGIL、DRIFT、Task Shield、ARGUS、AuthGraph 设为正面比较对象。
- `protocols/paper_upgrade_v2/online_state_audit_protocol_v1.md` 与登记表建立 22 个
  audit units、19 个已解析 discovery HEAD；当前 completed=0、claim-ready=0，
  oracle 领域主张继续禁用。
- 新增 `schemas/paper_v2/experiment_record_v1.schema.json`、
  `experiments/paper_v2/contracts.py` 和 `metrics.py`。记录契约强制在线字段/值摘要、
  禁止 evaluator/gold 字段、授权 regime、ASK/确认状态、unsafe-effect ITT、
  benign TCR、operational failure 与可审计 provider 身份。
- 新增预注册与中型 gate。未来 paper-v2 结果受 RQ、效应阈值、TCR `-5pp`、
  10,000 次 cluster bootstrap、自适应预算和自动转向规则约束；当前 gate 因外部
  输入未冻结而不允许启动。
- 新增 paper-v2 25 项测试并通过。旧 6 项 hash identity 失败被改为断言 fail-closed
  的历史证据边界，未修改任何旧 freeze；E17 13 项测试使用固定离线环境快照，
  不再在停服主机执行 30 秒 `ollama list`。
- 独立全量 pytest：`796 passed, 1 skipped, 2 warnings in 335.23s`。
- 最终 Harness：`796 passed, 1 skipped, 2 warnings in 373.68s`，规范 12/12、
  JSON、PowerShell/Shell 语法、compileall、Registry 18/18、历史证据均 PASS，
  `Verification failed=0`。
- 首次 Harness 重跑只在 PowerShell 5.1 将 UTF-8 无 BOM 脚本中的中文必需路径
  误解码时失败；改为 ASCII 源码内 Unicode 码点构造后重跑通过。
- F-PAPER-002 保持 `in_progress`：阶段 0 的 20 项实际源码审计、JCR 机构核验、
  VIGIL/DRIFT 忠实适配、60–80 case 中型实验、公共基准、盲测、自适应攻击和论文
  尚未完成。

## 2026-07-23 12:29 最终移交检查

- 确认分支为 `test1`，13 个核心移交文件全部存在。
- 复验通过：规范审计 12/12、仓库布局 10/10、E0–E17 注册表 18/18、历史冻结
  证据、功能台账 JSON 和 `git diff --check`。
- 安全边界通过：本地配置存在但被 Git 忽略且未跟踪，模型文件未跟踪；活跃文档
  没有当前检出目录绝对路径。
- 服务边界通过：`netstat` 未发现 11434 记录，限定进程检查未发现 Ollama/Python。
- 工作树有 42 条已跟踪改动和 149 条未跟踪项。当前只适合完整目录移交；若仅通过
  Git 克隆，当前未提交源码、文档、协议和实验材料不会被带走。
- 完整 Harness 的既有 6 个失败和 13 个未完成 E17 测试仍按移交报告披露，因此
  当前结论是“可带已知风险移交维护”，不是“全量测试全绿”或“二区论文已经完成”。

## 2026-07-23 当前项目文档中文化与命名规范

- 当前项目入口改为中文文件名：`docs/项目移交报告.md`、`docs/项目完整综述.md`、
  `docs/系统架构.md`、`docs/运行手册.md`、`docs/数据集说明.md`、
  `docs/伦理与适用范围.md`、`docs/证据索引.md`、`docs/移交与论文检查清单.md`。
- Harness 项目专用入口改为 `harness/项目上下文.md`。Harness 的标准机器入口和
  状态文件名保持不变，以免破坏脚本、恢复顺序和工具契约。
- 已同步根目录、docs、Harness、研究重定向、发布脚本、验证脚本和布局测试中的
  活跃引用；旧英文入口被自动审计列为禁止重新出现的名称。
- 当前有效文档的主要正文、架构图标签、证据术语和本轮相关代码注释已中文化。
  技术标识、命令、schema/JSON 字段、模型名、协议常量和冻结/归档证据保持原样。
- 路径审计确认当前入口未写入仓库检出目录的绝对路径；模型、缓存和本机环境路径
  仍按允许边界保留在配置或机器说明中。
- 验证结果：`audit_project_conventions.py --check` 为 12/12 通过；
  `test_repository_layout.py` 为 10/10 通过。本轮未启动任何模型或项目服务。
- Windows CIM/`Get-NetTCPConnection` 组合检查两次超过 20 秒，因此改用限定进程名
  的 `Get-Process` 与 `netstat -ano`。最终确认 11434 端口记录为 0，Ollama/Python
  匹配进程为 0；超时查询未改变任何进程状态。

## 2026-07-23 详细移交、文档归档与服务停止

- 已创建 `docs/项目移交报告.md`，覆盖系统架构、主要目录和能力、数据集、历史
  E0–E17、修复 V2、paper-v1、基线失败、AgentDojo 指标语义、证据层级、运行环境、
  Git 风险、Q2 缺口、常用命令和建议接手路线。
- 已创建 `harness/项目上下文.md`，详细说明 Harness 与产品/实验代码的区别、各状态
  文件用途、当前功能状态、失败恢复纪律、验证入口和下一步安全动作。
- 已更新仓库根目录、Harness 和 docs 索引，以及当前数据集、证据和移交入口。已被
  替代且未冻结的研究文档与旧 69 条竞赛文档移至 `docs/archive/`；历史引用路径保留
  精简重定向页。没有删除内容。
- 已停止经确认的 Ollama 桌面进程 29728 和服务进程 30124。11434 端口不再监听，
  未发现项目 Python、Docker、Streamlit 或 Uvicorn 工作负载；无关进程保持不动。
- 首次全量 `Win32_Process` CIM 枚举因主机内存错误失败，随后改用限定范围的
  `Get-Process`、命令路径、端口归属和 GPU 检查；该失败未改变任何项目状态。
- 冻结证据、历史绑定代码、`outputs/`、`protocols/`、`release/`、`external/`、
  模型文件和被忽略的本地密钥均未移动或编辑。
- 当时验证结果：规范审计 12/12、仓库布局 10/10、注册表 18 项完成；历史证据、
  compileall、Ruff 命名和 diff 检查通过。Pytest 收集 772 项；分组执行得到 752
  通过、6 失败、1 跳过；另有 13 个 `test_e17_review.py` 测试因服务已停止后环境
  快照反复调用 `ollama list` 而未完成。
- 六个失败暴露的是既有 paper-v1 身份漂移：三个 Progent G1 检查发现当前 CaMeL
  v1 适配器与 P0 保护哈希不一致；Progent/Task Shield v1 预检发现共享正式运行
  身份辅助文件与旧冻结不一致。因此不能声称全量 pytest/Harness 已通过；尽管文档
  与布局门禁通过，`F-DOC-001` 当时仍保持进行中。

## 2026-07-23 Progent v1.4 completed P3 but failed latency gate

- Built Progent v1.4 as a fresh revision over v1.3. The runtime keeps the
  v1.3 AgentDojo client-object deduplication repair and adds hash-bound
  Progent policy-output contract validation.
- Regenerated the v1.4 freeze and G1 correctness gate. Freeze passed 21/21 and
  G1 passed 15/15 with zero model/API calls.
- Ran the fresh 8-case P3 root at
  `outputs/paper_upgrade_v1/baselines/progent_source_backed_qualification_v14_p3`.
  It retained all 8 terminal rows with zero missing rows and zero operational
  failures.
- P3 operational results: observed ASR 0/4, full-denominator ASR bounds 0% to
  0%, utility-row success 3/4, first policy contract success 8/8, total model
  requests 81 and policy update errors 0.
- G2 failed 11/12. The only failed check was p95 latency within 5x matched
  ToolFilter: Progent p95 460,866 ms versus ToolFilter p95 41,643 ms, ratio
  11.07x.
- v1.4 repaired the v1.3 parser/runtime failure class, including the Travel
  `KeyError: 'name'`, but did not satisfy the staged expansion gate. P4/P5/P6,
  registry admission and any Q2 score increase remain blocked for Progent
  v1.4.
- Failure review:
  `protocols/paper_upgrade_v1/execution/progent_v14_p3_gate_failure_review_v1.md`.
  Analyzer output:
  `outputs/paper_upgrade_v1/analysis_v2/progent_source_backed_v14_p3/`.
- Current planner now marks Progent v1.4 as
  `failed_p3_qualification_gate_preserved_negative_evidence` and routes the
  next safe action to `qualify_camel_or_fides`. No expanded Progent run is
  authorized from v1.4.

## 2026-07-23 Progent v1.3 failed P3 after real model execution

- Built Progent v1.3 as a fresh revision over v1.2. The runtime now
  deduplicates AgentDojo `OpenAILLM` replacements by object identity and records
  the two pipeline positions, one unique client object and one duplicate
  position in each trace.
- Regenerated the v1.3 freeze and G1 correctness gate. Freeze passed 20/20 and
  G1 passed 13/13 before any fresh model qualification was started.
- Ran the fresh 8-case P3 root at
  `outputs/paper_upgrade_v1/baselines/progent_source_backed_qualification_v13_p3`.
  It retained all 8 terminal rows with zero missing rows: 5 completed and 3
  failed.
- G2 failed 9/12. The failed checks were zero operational failures, first policy
  output contract rate >=80%, and p95 latency <=5x matched ToolFilter.
- Failure details: Workspace injection ended as `parser_failure` after six
  invalid initial policy attempts; Travel utility and Travel injection ended as
  `runtime_failure` with `KeyError: 'name'` after policy outputs parsed as lists
  but failed semantic shape expectations.
- Analyzer output:
  `outputs/paper_upgrade_v1/analysis_v2/progent_source_backed_v13_p3/`.
  Protocol review:
  `protocols/paper_upgrade_v1/execution/progent_v13_p3_failure_review_v1.md`.
  Human-readable analysis:
  `docs/research/progent_v13_failure_analysis.md`.
- P4/P5/P6, registry admission and any Q2 score increase are blocked for v1.3.
  Ollama and project Python processes were stopped after analysis. Q2 remains
  raw 66.0 / capped 60.0, with formal-ready strong baselines still 2/5.
- Started the safe code-only v1.4 preparation without a model run: added
  `experiments/paper_v1/benchmarks/progent_policy_contract.py` and
  `tests/unit/test_progent_policy_contract.py`. The validator catches parsed
  policy payloads that are not lists, list items that are not objects, missing
  `name`, non-string/unknown tool names and missing/non-object `args`. This is
  the planned building block for converting Travel `KeyError: 'name'` into an
  auditable policy contract failure in a future v1.4 runtime.

## 2026-07-23 Progent v1.2 stopped at preserved failed P3 root

- Added the corrected cross-baseline metric semantics module and P0 audit for
  source-backed baselines. G0 passed 6/6 and produced
  `protocols/paper_upgrade_v1/execution/progent_v12_p0_metric_semantics_v1/gate_g0.json`.
- Added Progent v1.2 runtime, worker, staged runner, analyzer, outcome schema,
  freeze builder, correctness audit and focused tests. The v1.2 freeze passed
  19/19 and G1 zero-model correctness passed 12/12.
- Updated the Q2 execution planner so Progent no longer uses the old v1.1
  two-case command. It now routes through freeze/G1/P3/P4/P5 and blocks P6 until
  a separate authorized freeze exists.
- Ran fresh Progent v1.2 P3 after G1. It retained all 8 terminal rows, but all
  eight were `runtime_failure`, so the G2 gate failed and P4 was not started.
- Failure cause is pre-model instrumentation: AgentDojo has two `OpenAILLM`
  pipeline positions pointing to the same object; v1.2 counted positions rather
  than unique client objects and raised before any model request.
- Added `protocols/paper_upgrade_v1/execution/progent_v12_p3_failure_review_v1.md`.
  Q2 remains raw 66.0 / capped 60.0, and formal-ready strong baselines remain
  2/5.

## 2026-07-23 Task Shield v1.6 completed at failed G3 boundary

- Completed the non-mutating AgentDojo semantics layer and analysis-v2: G0
  passed 15/15. ToolFilter raw targeted-injection success is 7/629; Task Shield
  v1.5 is 0/6 rather than the legacy complemented values.
- Implemented and froze the v1.6 runtime/runner/analyzer path. G1 passed 20/20,
  freeze validation passed 21/21, and 32 focused tests covered zero SDK retry,
  bounded full-contract recovery, terminal trace persistence, independent
  timing and the no-case-retry boundary.
- Ran fresh P3 and P4 only after their preceding gates. P3 passed 4/4 and G2
  11/11. P4 retained 12/12 terminal rows: 9 completed, 3 timed out, 0 missing.
- G3 failed 12/16. Standalone utility was 2/6, attack-condition utility 0/6,
  Task Shield p95 was 600.070 seconds versus 39.545 seconds for matched
  ToolFilter, and verifier requests consumed 78.92% of total case time.
- Generated a detailed failure analysis, case diagnostics and three chart
  families in PNG/SVG. Preserved 0/5 completed attack success plus one
  unresolved attack timeout without converting it to a formal 0/6 claim.
- Recorded the post-G3 stop decision. P5/P6, selective retry, formal admission
  and any Q2 score increase are blocked. The Q2 planner now skips Task Shield
  and selects the fresh Progent source-backed two-case qualification.
- Stopped Ollama after P4 and confirmed no project model workload remains.
- Final Harness verification completed with 724 passed, 1 skipped and
  `Verification failed=0`. Project conventions remained 12/12, registry and
  historical evidence verification passed, and the Ollama process tree was
  stopped again after validation.

## 2026-07-22 Task Shield v1.6 authorization and environment closeout

- Received explicit authorization to enter v1.6 under a staged plan.
- Inspected live processes, selected ports, services, Docker and GPU process
  ownership. The only attributable process was Ollama PID 32748 listening on
  127.0.0.1:11434; it was stopped and the listener disappeared.
- Removed 109 reproducible cache directories containing 961 files and an
  estimated 13,807,106 bytes. Exact-root and protected-prefix guards excluded
  outputs, protocols, config, Git and external model storage; the final
  unprotected cache count is zero.
- Recorded an environment cleanup manifest, frozen-evidence hash snapshot and
  operator authorization in
  `protocols/paper_upgrade_v1/execution/taskshield_v16_preparation_v1/`.
- Added the detailed P0-P6 execution plan at
  `docs/research/taskshield_v16_execution_plan.md`, including fresh-root rules,
  18 deterministic fixtures, 4/12/30-case gates, stop/turn conditions, formal
  statistics and a separately authorized 726-case boundary.
- This checkpoint executed zero model/API calls and leaves Q2 readiness and all
  formal registries unchanged. The next action is the zero-model P0 semantics
  correction, not an Ollama/model launch.

## 2026-07-22 Task Shield v1.5 root-cause and AgentDojo metric-semantics audit

- Cross-checked the pinned AgentDojo injection-task contract, official analysis
  notebook, project adapter and all 12 v1.5 raw official traces. The shared
  adapter inverted upstream targeted-injection success when deriving ASR.
- Corrected diagnostic interpretation: Task Shield raw Targeted ASR is 0/6,
  not the stored complement 6/6; utility is 1/6 and attack-condition utility is
  0/6, so the result is degenerate safety rather than useful defense evidence.
- Recounted all 629 ToolFilter security traces: official injection success is
  7/629 while the old derived analysis reports the complement 622/629. No raw
  output was changed; old effect tables are provisional pending analysis-v2.
- Isolated four other failure planes: timeout exception-type mismatch, SDK and
  manual retry multiplication, trace snapshot after success only, and scoring
  schema/cardinality failures outside the retry loop. Ten fail-closed scoring
  events were observed; verifier calls consumed about 73.1% of completed-case
  time.
- Added detailed analysis and a staged v1.6 feasibility plan under
  `docs/research/`. The plan starts with a zero-model-call semantics correction,
  then 4-case/12-case/30-case gates; it authorizes no execution.
- Verification: conventions 12/12, layout/Q2 focused regression 22/22, feature
  JSON parse and `git diff --check` pass; no experiment process is live.

## 2026-07-22 Task Shield v1.4 seal and v1.5 failed expanded qualification

- Stopped PID 9804 with explicit user authorization and sealed the unchanged
  v1.4 root outside the evidence directory at 24 completed, 2 failed and 700
  missing. The seal verifies 56 files / 1,385,631 bytes and inventory SHA-256
  `9a6d9fde53ba80ce83326018563689071cf454dffacd97133ea3cb8e0e76f453`.
- Completed an 8/8 read-only failure-mode audit. It identified that v1.4 parsed
  verifier output before recording it and froze a fresh 6-utility/6-security
  qualification selection with SHA-256
  `fbe175928718307a3c6f55dbb20414b762d01d249d2b9e41f19d6d2c4f2114ef`.
- Built the separate v1.5 runtime/runner/freeze. Its 19/19 freeze authorizes
  only the exact 12-case qualification and explicitly forbids formal admission
  or a 726-case run.
- The fresh v1.5 qualification naturally ended 11 completed, 1 failed and 0
  missing. Utility success was 1/6. Its stored legacy `attack_success=6/6` is
  later corrected by the AgentDojo semantics audit to raw Targeted ASR 0/6.
  End-to-end latency was p50 221.037553 s, p95 975.990048 s and max
  1619.386955 s.
- The audit observed one successful invalid-JSON contract retry and ten
  contribution-scoring fail-closed events. However, an exhausted assistant
  timeout escaped suppression and the failed outcome did not persist its trace,
  so the qualification gate failed and Q2 score change remains zero.
- Updated the Q2 planner to report `blocked_explicit_revision_decision`, with a
  read-only analyzer command only. It cannot resume v1.4, mutate/retry v1.5 or
  start an unauthorized v1.6/full run.
- Verification: focused Task Shield/Q2/layout regression 46/46; full Harness
  691 passed / 1 skipped and `Verification failed=0`; conventions 12/12; Ruff,
  compileall, JSON contracts, experiment registry and historical evidence pass.

## 2026-07-22 Task Shield failure diagnostic and precise operator blockers

- Refreshed the v1.3 monitor to 39/726 completed, 1 failed, 686 missing, PID
  27384 alive, with health `running_with_failures_requires_attention`.
- Generated a non-admitting diagnostic at
  `protocols/paper_upgrade_v1/diagnostics/task_shield_formal_v13/`; the sole
  failure is `agentdojo:v1:slack:user_task_18`, classified `timeout` with
  `APITimeoutError`.
- Corrected the v1.4 operator-decision validator so a missing decision does not
  produce synthetic missing-field cascades. The current blocked audit now
  reports exactly the three actionable blockers while remaining fail-closed.
- No formal process was stopped or started, no case was retried or excluded,
  and no result was admitted. Q2 remains raw 66.0 / capped 60.0.
- Verification: focused regression 25/25, Ruff pass, compileall pass,
  conventions audit 12/12, registry verification pass, historical evidence
  verification pass, feature-registry JSON parse pass and `git diff --check`
  whitespace-clean with CRLF warnings only.

## 2026-07-22 Task Shield operator decision gate added

- Refreshed the active v1.3 monitor for
  `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`. It remains
  `running_with_failures_requires_attention`: 38/726 completed, 1 failed,
  687 missing, PID 27384 alive.
- Extended the v1.4 recovery package so it writes
  `taskshield_v14_operator_decision_template.json/.md`. The template is
  intentionally `draft_unapproved` and records the recovery package SHA-256,
  v1.3 monitor SHA-256 and expected fresh v1.4 roots.
- Added `validate_taskshield_v14_operator_decision.py`. Its current audit is
  `blocked_not_approved_to_start_v14` because no approved decision file exists
  and the v1.3 PID is still live.
- No process kill, selective retry, failed-row exclusion, registry admission,
  formal-result promotion, model/API call or competing Ollama/GPU workload
  occurred. Q2 remains raw 66.0 / capped 60.0 with `goal_80_met=false`.
- Verification: focused recovery/operator-decision/planner/Q2/layout
  regression 24/24, Ruff pass, compileall pass, JSON parse checks pass,
  conventions audit 12/12, registry verification pass, historical evidence
  verification pass, Q2 readiness audit still raw 66.0 / capped 60.0 and
  `git diff --check` whitespace-clean with CRLF warnings only.

## 2026-07-22 Task Shield v1.4 recovery decision package generated

- Refreshed the active v1.3 monitor for
  `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`. It remains
  `running_with_failures_requires_attention`: 37/726 completed, 1 failed,
  688 missing, PID 27384 alive.
- Generated
  `protocols/paper_upgrade_v1/execution/taskshield_v14_recovery_decision_v1/`
  as a read-only recovery decision package. It preserves the failed v1.3 root,
  records `can_start_v14_qualification_now=false`, lists the required gates for
  v1.4 and makes `q2_score_change=0.0` explicit.
- Refreshed `q2_formal_execution_plan_v1` and
  `q2_to_80_action_audit_v1` sequentially after the monitor update. Both now
  route the next safe action to
  `python -m experiments.paper_v1.benchmarks.prepare_taskshield_v14_recovery_package`
  with `resource_kind=cpu_read_only`.
- No process kill, selective retry, failed-row exclusion, registry admission,
  formal-result promotion, model/API call or competing Ollama/GPU workload
  occurred.
- Q2 remains raw 66.0 / capped 60.0 with `goal_80_met=false`; this checkpoint
  is handoff/readiness plumbing only and does not raise the paper-readiness
  score.
- Verification: focused recovery/planner/Q2/layout regression 22/22, Ruff
  pass, compileall pass, conventions audit 12/12, experiment registry
  verification pass, historical evidence verification pass and
  `git diff --check` whitespace-clean with CRLF warnings only.

## 2026-07-22 Task Shield v1.4 failure-recovery protocol prepared

- Prepared a separate Task Shield v1.4 failure-recovery protocol without
  admitting or repairing the active v1.3 failed root. The new freeze at
  `protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v14.json/.md`
  passes 16/16 and hash-binds the v1.4 runtime and runner.
- The v1.4 runtime patch adds explicit verifier transport-timeout retries with
  trace logging. It does not retry arbitrary case failures, remove denominator
  rows, alter Task Shield semantic scoring or turn v1.3 partial evidence into a
  result.
- Latest v1.3 read-only monitor snapshot remains
  `running_with_failures_requires_attention`: 35/726 completed, 1 failed,
  690 missing, PID 27384 alive. The failed row is
  `agentdojo:v1:slack:user_task_18` with `APITimeoutError`.
- Dynamic audits refreshed after the monitor snapshot. Q2 remains
  `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`; formal-ready
  strong baselines remain 2/5 (`agentdojo_tool_filter`, `promptguard`).
- No process kill, selective retry, failed-row exclusion, registry admission,
  formal result promotion, model/API call or competing Ollama/GPU workload
  occurred.
- Validation: repository-layout/Task Shield/public-adapter/external-admission/
  Q2 focused regression 141/141; full pytest 669 passed and 1 skipped; full
  Harness verifier `Verification failed=0`; conventions audit 12/12; Ruff pass;
  compileall pass; registry and historical evidence verification pass;
  `git diff --check` had no whitespace errors, only CRLF warnings.

## 2026-07-22 Task Shield failed-root gate and Q2 fail-closed planner

- Refreshed the active Task Shield v1.3 monitor for
  `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`. It now
  reports `running_with_failures_requires_attention`: 28/726 completed, 1
  failed, 697 missing and PID 27384 alive.
- Failed row: `agentdojo:v1:slack:user_task_18`, `APITimeoutError`. This is an
  operational formal-run failure, not a security/utility effect result.
- Updated the Q2 formal execution planner and current non-frozen documentation
  so this state routes to `review_failed_formal_workload` and
  `blocked_manual_review`.
- No process kill, selective retry, failed-row exclusion, registry admission,
  result promotion, model/API call or competing Ollama/GPU workload occurred.
- Q2 readiness remains raw 66.0 / capped 60.0; formal-ready strong baselines
  remain 2/5 (`agentdojo_tool_filter`, `promptguard`).
- Validation: conventions audit 12/12; Q2 planner/action/external-admission
  focused regression 22/22; public-adapter/TaskShield/Q2 regression passed
  117/117 after updating the stale Task Shield status assertion; Ruff pass;
  compileall pass; registry and historical evidence verification pass;
  `git diff --check` has no whitespace errors, only CRLF warnings. Full Harness
  verifier was attempted with a 180-second bound and timed out, so it is not
  counted as passing.

## 2026-07-22 Configuration handoff and local-root path cleanup

- Replaced the remaining active Harness analysis references to the local
  checkout root with repository-relative wording in:
  `harness/workspaces/runpro/10_analysis/approval-gate.md`,
  `harness/workspaces/runpro/10_analysis/project-inventory.md` and
  `harness/workspaces/runpro/10_analysis/project-intake.md`.
- Added Frontier API Q2-slot operating instructions to `config/README.md`:
  credentials stay only in ignored `config/project.local.env`, plan-only smoke
  runs before any `--execute`, network smoke requires
  `M3_FRONTIER_API_CONSENT=yes_for_network_smoke`, and registry admission
  consumes only the redacted smoke manifest.
- Refreshed/read Q2-related audits without changing evidence status. Q2 remains
  raw 66.0 / capped 60.0; Frontier API remains 0/2 configured vendors and
  `blocked_missing_or_unsafe_local_config`.
- Task Shield v1.3 remains the active formal workload: 24/726 completed, 0
  failed, PID 27384 alive, below the 45-minute stall threshold. No competing
  Ollama/GPU job, network/API call, registry write or formal result promotion
  occurred.
- Verification: conventions audit 12/12; focused
  frontier/config/Q2-to-80/layout regression 29/29; Ruff pass; compileall pass;
  `git diff --check` pass with only existing CRLF conversion warnings.

## 2026-07-22 PromptGuard preflight portability hardening

- Updated `promptguard_adapter.py` so repo-local registry, real-smoke and
  generated preflight paths render relatively. The regenerated artifact was
  built with the dedicated PromptGuard runtime so dependency state remains
  `real_detector_smoke_completed_formal_run_pending` instead of being downgraded
  by the default Python environment.
- Regenerated
  `protocols/paper_upgrade_v1/promptguard_detector_adapter_preflight_v1.json/.md`.
  It keeps `real_detector_ready=true`, real-smoke completed, stub smoke
  completed and `result_eligible_for_formal_tables=false`; the separate
  detector-only formal result remains limited to detector-performance tables.
- Refreshed `strong_baseline_dependency_snapshot_v1`,
  `strong_baseline_formal_readiness_audit_v1` and `q2_readiness_audit_v1`.
  Strong-baseline readiness remains `not_satisfied` with formal-ready entries
  `agentdojo_tool_filter` and `promptguard`; Q2 remains raw 66.0 / capped 60.0.
- Added PromptGuard preflight to convention audit portability coverage.
  Verification: PromptGuard/Q2/layout regression 26/26, conventions audit
  12/12, Ruff naming lint and py_compile passed.

## 2026-07-22 CaMeL official source-smoke portability hardening

- Updated `audit_camel_official_source_smoke.py` so repo-local preflight,
  registry, checkout, required-source and generated evidence paths render
  relatively in source-smoke artifacts. External runtime fields such as the
  Python executable remain machine-specific by design.
- Regenerated `protocols/paper_upgrade_v1/camel_official_source_smoke_v1.json/.md`.
  The audit remains 8/8 checks, `completed_source_smoke_only`, no network calls
  and `result_eligible_for_formal_tables=false`.
- Refreshed `strong_baseline_dependency_snapshot_v1`,
  `strong_baseline_formal_readiness_audit_v1` and `q2_readiness_audit_v1`.
  Strong-baseline readiness remains `not_satisfied` with formal-ready entries
  `agentdojo_tool_filter` and `promptguard`; Q2 remains raw 66.0 / capped 60.0.
- Added CaMeL source-smoke to convention audit portability coverage.
  Verification: CaMeL/Q2/layout regression 23/23, conventions audit 12/12,
  Ruff naming lint and py_compile passed. Remaining checkout-absolute protocol
  files decreased from 39 to 37 total, including 14 frozen/hash-bound files that
  stay immutable.
- Latest Task Shield v1.3 read-only monitor at this checkpoint:
  `running_progressing`, 21/726 completed, 0 failed, 705 missing, PID 27384
  alive; it remains running evidence only and is not formally admitted.

## 2026-07-22 Progent source-smoke portability hardening

- Updated `audit_progent_official_source_smoke.py` so repo-local registry,
  checkout, license-candidate and generated evidence paths render relatively in
  source-smoke artifacts. External runtime fields such as the Python executable
  remain machine-specific by design.
- Regenerated `protocols/paper_upgrade_v1/progent_official_source_smoke_v1.json/.md`.
  The audit remains `completed_source_smoke_only`, the offline runtime smoke
  passes, the missing top-level license remains a retained warning, and
  `result_eligible_for_formal_tables=false`.
- Refreshed `strong_baseline_dependency_snapshot_v1`,
  `strong_baseline_formal_readiness_audit_v1` and `q2_readiness_audit_v1`.
  Strong-baseline readiness remains `not_satisfied` with formal-ready entries
  `agentdojo_tool_filter` and `promptguard`; Q2 remains raw 66.0 / capped 60.0.
- Added Progent source-smoke to convention audit portability coverage.
  Verification: Progent/Q2/layout regression 27/27, conventions audit 12/12,
  Ruff naming lint and py_compile passed. No frozen evidence was modified, no
  model was started, and no formal result was admitted.
- Latest Task Shield v1.3 read-only monitor at this checkpoint:
  `running_progressing`, 20/726 completed, 0 failed, 706 missing, PID 27384
  alive; it remains running evidence only and is not formally admitted.

## 2026-07-22 IPIGuard source-smoke portability hardening

- Updated `audit_ipiguard_source_smoke.py` so repo-local preflight, checkout,
  source-file, syntax-check and dataset-universe paths render relatively in the
  generated source-smoke evidence. External runtime fields such as the Python
  executable remain machine-specific.
- Regenerated `protocols/paper_upgrade_v1/ipiguard_official_source_smoke_v1.json/.md`.
  The source-smoke remains 8/8 checks, `completed_source_smoke_only` and
  `result_eligible_for_formal_tables=false`.
- Refreshed `strong_baseline_dependency_snapshot_v1`,
  `strong_baseline_formal_readiness_audit_v1` and `q2_readiness_audit_v1`.
  Strong-baseline readiness remains `not_satisfied` with formal-ready entries
  `agentdojo_tool_filter` and `promptguard`; Q2 remains raw 66.0 / capped 60.0.
- Added IPIGuard source-smoke to convention audit portability coverage.
  Verification: IPIGuard/Q2/layout regression 29/29, conventions audit 12/12,
  Ruff naming lint, py_compile and refreshed downstream checkout-path scan
  passed. Remaining checkout-absolute protocol files decreased from 43 to 41,
  including 14 frozen/hash-bound files that stay immutable.

## 2026-07-22 Public benchmark pending-ledger portability hardening

- Updated `prepare_public_benchmark_formal_runs.py` so formal-run pending
  plans, root manifests, formal-cell queues and pending cell manifests render
  repo-local freeze/result/cell/manifest/todo paths relatively. File operations
  still use resolved `Path` objects; no benchmark or model job is started.
- Rewrote only pending manifests with `--force`: v1 stayed 60/60 pending cells
  and 53,400 case-runs; v2 stayed 84/84 pending cells and 74,760 case-runs.
  There were no completed/running cells to overwrite.
- Refreshed `public_benchmark_result_completeness_audit_v1` and v2. Gates stay
  `not_satisfied`, complete case-runs stay 0, and Q2 remains raw 66.0 / capped
  60.0.
- Added public run plans/root manifests/queues to the convention audit
  portability coverage. Verification: public-adapter/worker/Q2/layout
  regression 118/118, conventions audit 12/12, Ruff naming lint, compileall and
  active public artifact checkout-path scan passed.

## 2026-07-22 Strong-baseline evidence portability hardening

- Updated `audit_agentdojo_official_strong_baselines.py` so repo-local
  `agentdojo_checkout`, official source files, smoke manifest and ToolFilter
  freeze/qualification references render as repository-relative paths. External
  Hugging Face cache and Python runtime locations remain absolute because they
  are machine dependencies.
- Regenerated
  `protocols/paper_upgrade_v1/agentdojo_official_strong_baseline_capability_audit_v1.json/.md`;
  the audit remains 9/9 checks, `result_eligible_for_formal_tables=false`, and
  has no checkout-absolute path hits.
- Updated `prepare_strong_baseline_source_checkouts.py` so the manifest keeps
  absolute paths internally for Git operations but writes repo-local registry,
  checkout root and local checkout references relatively.
- Regenerated
  `protocols/paper_upgrade_v1/strong_baseline_source_checkout_manifest_v1.json/.md`
  in dry-run mode, then refreshed `strong_baseline_dependency_snapshot_v1`,
  `strong_baseline_formal_readiness_audit_v1` and `q2_readiness_audit_v1`.
  Strong-baseline readiness remains `not_satisfied`; formal-ready entries are
  still `agentdojo_tool_filter` and `promptguard`; Q2 remains raw 66.0 /
  capped 60.0.
- Added both regenerated evidence families to
  `scripts/audit_project_conventions.py` portability coverage. Verification:
  conventions audit 12/12, focused layout/Q2/external-baseline regression 24/24,
  Ruff naming lint, compileall, and checkout-path scans passed.
- Latest Task Shield v1.3 read-only monitor after this checkpoint:
  `running_progressing`, 14/726 completed, 0 failed, 712 missing, PID 27384
  alive; still running and not formally admitted.

## 2026-07-22 Q2 current-status sync and safe stop point

- Refreshed the current-state text in `README.md`, `docs/PROJECT_OVERVIEW.md`,
  `harness/specs/product-spec.md` and `harness/docs/decision-log.md` to match
  the latest conservative Q2 audit: `raw_score=66.0`, `capped_score=60.0`,
  `goal_80_met=false`, `goal_90_met=false`.
- Rechecked Task Shield v1.3 with the read-only monitor:
  `running_progressing`, 11/726 completed, 0 failed, 715 missing, PID 27384
  alive. The active formal run still owns Ollama/GPU, so the next safe action is
  monitoring rather than launching Progent, CaMeL, IPIGuard, adaptive or public
  matrix jobs.
- A full Harness verifier attempt timed out after 5 minutes and is not counted
  as a pass. Follow-up process inspection found no leftover verification child;
  PID 27384 was confirmed as the Task Shield formal run and was not touched.
- Verification that did complete: conventions audit 12/12, focused
  repository/frontier/Q2/planner/blind/public-worker/TaskShield regression
  56/56, Ruff naming lint, and compileall.

## 2026-07-22 Frontier API active-artifact portability refresh

- Updated the Frontier API plan-only smoke and offline registry-admission
  scripts so in-repository references are rendered relatively:
  `config_path`, printed output directory, `base_registry_path`,
  `smoke_manifest_path`, `output_registry_path`, and future `smoke_evidence`
  registry entries.
- Regenerated `outputs/paper_upgrade_v1/frontier_api_smoke_v1/manifest.json` and
  `protocols/paper_upgrade_v1/frontier_api_model_slot_registry_admission_v1.json`.
  Both remain non-formal: no network calls, 0/2 configured vendors, blocked
  registry admission, no v3 candidate, and no Q2 score increase.
- Refreshed `frontier_api_model_slot_admission_audit_v1` and
  `q2_readiness_audit_v1`; Q2 remains `raw_score=66.0`,
  `capped_score=60.0`, `goal_80_met=false`.
- Task Shield v1.3 remains the only active formal workload:
  `running_progressing`, 7/726 completed, 0 failed, PID 27384 alive. A read-only
  process/log check showed the PID responding and no stderr log present; no
  intervention, retry or competing workload was started.
- Boundary recorded: the active Task Shield v1.3 raw outcomes currently contain
  runner-emitted `official_trace_path` absolute values. They are in-progress raw
  evidence and must not be rewritten in place; fully relative raw outcomes would
  require a future new freeze/run revision.
- Verification: Frontier-focused regression 11/11, combined Frontier/Q2/planner/
  layout regression 39/39, Ruff naming lint passed, compileall passed,
  conventions audit 12/12 PASS, refreshed Frontier/Q2 active artifact path scan
  found no current-checkout absolute path hits, and `git diff --check` reported
  no whitespace errors beyond existing CRLF warnings.

## 2026-07-22 Independent blind handoff kit portability and Q2 gate refresh

- Regenerated the content-free independent blind authoring kit under
  `protocols/paper_upgrade_v1/independent_blind_authoring_kit_v1/` with
  package-local relative artifact paths (`README.md`, `authoring_slots.csv`,
  `authoring_slots.jsonl`, `case_template.json`, `custody_manifest_template.json`
  and `validate_candidate_before_release.py`). The kit still creates 0 candidate
  cases and remains `result_eligible_for_confirmatory_q2_tables=false`.
- Added a self-contained `validate_candidate_before_release.py` to the kit so
  independent authors can check 600-row distribution, unique IDs/templates,
  independent-blind scope, forbidden oracle fields and custody sidecar consistency
  before release. This is a pre-release structure/custody check only; it does not
  compare against M3 reference data and cannot admit a result.
- Refreshed `m3_v2_independent_blind_admission_audit_v2`: status remains
  `blocked_missing_candidate`, `candidate_exists=false`, 0/1 checks, and the
  independent blind Q2 gate remains unsatisfied.
- Refreshed Frontier API audit without reading or printing secrets and without
  network calls: status remains `blocked_missing_or_unsafe_local_config`,
  configured vendors 0/2, registered vendors 0/2, explicit network-smoke consent
  false, result eligible false.
- Refreshed Q2 readiness: `raw_score=66.0`, `capped_score=60.0`,
  `goal_80_met=false`, `goal_90_met=false`. Current score is still capped by
  missing independent blind, missing frontier API vendor slots, missing formal
  adaptive budget evidence, incomplete public matrix and fewer than five admitted
  strong baselines.
- Latest Task Shield v1.3 formal monitor:
  `running_progressing`, 7/726 completed, 0 failed, 719 missing, PID 27384 alive.
  No competing Ollama/GPU workload was started.
- Verification: independent-blind authoring-kit tests 3/3, focused Q2/frontier/
  layout regression 41/41, Ruff naming lint passed, compileall passed,
  conventions audit 12/12 PASS, checkout-absolute scan over refreshed active
  artifacts found no current-checkout absolute path hits, and `git diff --check` reported no
  whitespace errors beyond existing CRLF warnings.

## 2026-07-22 Relative-path portability and Q2 continuation

- Replaced checkout-specific absolute paths in the active overview, folder guide and current task with repository-relative wording. External model/runtime/cache locations are represented by `OLLAMA_MODELS`, `HF_HOME`, `HF_HUB_CACHE` and `M3_RUNTIME_ROOT`; frozen and historical evidence was not rewritten.
- Extended `audit_project_conventions.py` with a checkout-path portability gate that skips explicitly frozen sources and archived evidence. Current audit: 11/11 PASS; focused repository-layout regression: 6/6 PASS.
- Task Shield v1.2 full formal root `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v1` failed after 5 completed cases and 1 failed case (`agentdojo:v1:banking:user_task_13`, `TaskShieldVerifierError: one contribution row is required per user task`). The root is retained as failed diagnostic evidence, not resumed, and not counted as a safety/utility result.
- Added separate Task Shield v1.3 compatibility artifacts: `experiments/paper_v1/benchmarks/taskshield_paper_runtime_v13.py`, `run_taskshield_paper_formal_v13.py`, `build_taskshield_paper_formal_freeze_v13.py` and `protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v13.json`. v1.3 keeps trusted-task extraction strict, fail-closes contribution-scoring parse/schema/score/cardinality errors, and stores repository-local freeze paths relatively while leaving machine model/runtime paths absolute.
- Task Shield v1.3 qualification completed 2/2 cases, 0 failed at `outputs/paper_upgrade_v1/baselines/taskshield_paper_qualification_v13/run_manifest.json`; focused v1.3/planner tests passed 20/20, naming Ruff passed and conventions audit passed 12/12. The qualification root remains `result_eligible=false`.
- Task Shield v1.3 726-case formal run started at `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`, PID 27384, with stderr empty and 1/726 initially running. This long run owns the Ollama/GPU slot; do not start Progent, CaMeL, IPIGuard, adaptive or public-matrix workloads concurrently.
- Latest Task Shield v1.3 monitor shows `running_progressing`, 3/726 completed, 0 failed and 723 missing; Q2 planner resource gate is `busy` and next action is read-only monitor only.
- Refreshed frontier API and independent-blind gates without reading secrets or making network calls. Frontier API remains 0/2 configured vendors and `blocked_missing_or_unsafe_local_config`; independent blind remains `blocked_missing_candidate`. Frontier/Q2 active artifacts now emit repository-relative project paths, with a regression requiring frontier audit project paths to stay relative. These checks improve portability but do not raise Q2 readiness.
- The previous ToolFilter PID had disappeared at 483/726 completed and zero failures while its manifest remained running. A read-only monitor classified it as `stopped_without_terminal_manifest`; the same frozen 726-case run was resumed without retrying or overwriting completed rows. Formal admission remains blocked until exact coverage, zero failures, analysis and registry admission all pass.
- Added `plan_public_benchmark_workers.py` and a plan-only artifact under `protocols/paper_upgrade_v1/execution/public_benchmark_workers_v1/`. It covers 84/84 cells and 74,760/74,760 case-runs, assigns all 12 cells for each model to one of seven workers, emits no drive-absolute command paths and passes 3/3 focused tests plus the combined public-adapter regression at 99/99, Ruff and compile. It starts no model and contributes no readiness points by itself.
- Normalized repository-local paths in the live ToolFilter monitor, Q2 readiness audit and Q2 execution plan to repository-relative strings, while retaining absolute paths only for necessary external runtimes such as the isolated CaMeL interpreter. Added a non-inflating `goal_80_met` milestone; current raw/capped readiness remains 63.5/60.0 and the milestone remains false.
- Replaced the external-baseline planner's blank qualification placeholder with deterministic two-case commands: one utility and one security case, a fresh qualification-only output root, `--no-resume`, and no formal-admission flag. Focused Q2/monitor/path regressions pass 43/43; Ruff, compile and the 11/11 conventions audit pass.
- The 2026-07-22 11:25+08:00 ToolFilter snapshot is 526/726 completed, 0 failed and 200 missing with resumed PID 18904 alive. Workspace security cases are currently approximately one minute each; no competing Ollama/GPU job has been started.
- Full naming lint (`ruff --select N`), repository-wide `compileall`, conventions audit 11/11 and `git diff --check` pass while the writer remains active. Result/registry-scanning pytest and the aggregate Harness verifier remain intentionally deferred until the formal root reaches a terminal state.
- Consolidated repository-relative artifact rendering into `experiments.paper_v1.benchmarks.common.portable_path/portable_value`; the Q2 audit, formal monitor, execution planner, ToolFilter analyzer/admission and external-baseline admission bridge now share one rule. New dynamic artifacts keep in-repo paths relative and external machine dependencies absolute.
- Exercised ToolFilter admission against the live partial root without write flags: it remained `blocked_not_formally_admitted` with 11 blockers, `result_eligible=false`, and the baseline registry SHA-256 stayed unchanged. All four external admission bridges were also refreshed plan-only as blocked/non-eligible with relative registry paths.
- Admission/analyzer/external-baseline/Q2 focused regression passed 47/47 before refactoring and 39/39 plus 17/17 after the shared path helper changes; repository-layout regression remains 6/6, Ruff and compile pass, and the conventions audit remains 11/11.
- Freeze-boundary regression caught an unsafe cleanup attempt before execution: changing four external analyzers caused six expected hash-identity failures. Those analyzer edits were reverted, the same strong-baseline suite returned to 32/32 PASS, and no freeze was rebuilt. The conventions audit now discovers 21 `local_adapter.files` entries from freeze manifests and excludes them from in-place portability rewrites; repository-layout tests are now 7/7.
- Added a repository-wide `hash_bound_file_identity` gate. It relocates stored in-repo paths when a checkout moves, verifies all 21 bound files against the SHA-256 values in their existing freezes, and currently passes. The conventions audit is now 12/12 and repository-layout regression 8/8.
- Revalidated the historical evidence boundary after cleanup: E0-E17 registry is 18 completed / 0 pending / 0 running / 0 failed; historical evidence verification passes with unchanged V2 (`f2f98c...`), E11 r2 (`ceb320...`) and context/E17 r3 (`314aa9...`) freeze hashes.
- Normalized the non-frozen strong-baseline formal-readiness audit before row hashing and regenerated it with zero checkout-absolute hits. Its semantic result is unchanged: 7/7 checks pass, only PromptGuard is formal-ready, and the 5-baseline Q2 gate remains unsatisfied. Focused strong-baseline/IFC regression passed 11/11.
- Normalized the non-frozen public-benchmark completeness audit before row hashing and regenerated all 84 cell records with repository-relative paths. The result remains evidence-conservative: 0/74,760 formal case-runs complete and `result_completeness_gate=not_satisfied`. Focused completeness regression passed 2/2, Ruff/compile passed, and the artifact is now covered by the portability gate.
- Latest read-only ToolFilter snapshot: 568/726 completed, 0 failed, 158 missing, PID 18904 alive and progressing. Q2 remains raw 63.5/capped 60.0; no partial result was admitted and no competing GPU workload was started.
- Split independent-blind admission at the preregistration boundary: frozen v1 audit SHA-256 remains `3772bbc...`, active v2 stores only relative in-repo paths and remains `blocked_missing_candidate`, and a new fail-closed formal admission can update only the separate paper-v1 evidence index. Historical `final_analysis` is no longer a required mutation point. Focused blind/Q2/layout regression passed 30/30; no evidence score changed.
- Hardened the next IPIGuard qualification command against output reuse: the failed v1 root and traceback stay immutable, while current freeze 1.1/raw-DAG observability uses a fresh v2 root, one utility plus one security case and `--no-resume`. Planner regression is 6/6; the run remains queued behind ToolFilter.

## 2026-07-21 Project overview and conservative compatibility cleanup

- Added the full Chinese `docs/PROJECT_OVERVIEW.md` plus `docs/README.md` and `docs/archive/README.md`. The overview records the audited branch/commit/date, threat model, architecture, every top-level directory, feature-to-source/CLI/test/evidence mapping, dataset generations, run procedures, statistics, sandbox/configuration boundaries, verified work, advantages, defensible innovations, limitations, incomplete Q2 gates and roadmap.
- Moved only four approved non-frozen files to canonical names and updated active references: `docs/presentation/ppt_result_notes.md`, `docs/archive/report_v0_3.md`, `experiments/e17_source_index.md` and `harness/tasks/m3-expansion-001.md`. Historical snapshots retain their original path text as provenance; no file was deleted.
- Replaced the root README with a current quick entry, fixed the root JSONL converter example, and synchronized architecture, Runbook, product-spec and Chinese folder-guide wording. Historical E0-E17, post-hoc V2, diagnostic/smoke/running paper-v1 and formal evidence are explicitly separated.
- Added the standard-library repository audit and integrated it with `harness/scripts/verify.ps1`; it checks directory ownership, Harness/source separation, root allowlist, approved moves, Python filenames/identifiers, active links/references, local-secret/model Git boundaries and frozen-path existence. Current result: 10/10 PASS; repository-layout tests: 4/4 PASS.
- The active AgentDojo ToolFilter output/protocol/manifest remained read-only. Cleanup-start snapshot: 454/726 completed, 0 failed, 272 missing, PID 36472 alive. Full test/Harness verification remains gated until this writer stops, so this checkpoint is engineering-complete but not yet final-verifier-complete.

## 2026-07-21 Task Shield v1.2 hash-bound disclosed reproduction hardening

- Rebuilt `taskshield_paper_formal_freeze_v1` as schema `paper-taskshield-reproduction-freeze-1.2`. The freeze now passes 13/13 checks and hash-binds the local Task Shield reproduction runtime, import preflight, runner, analyzer, shared resume-identity helper and formal protocol, in addition to the ACL paper PDF SHA-256 and common 726-case AgentDojo universe.
- Rebuilt `taskshield_paper_import_preflight_v1`; it now passes 9/9 checks in the network-blocked/no-Ollama/no-benchmark-case boundary and verifies that local adapter hashes still match the freeze. Freeze SHA-256 is `a2ac513fd59525d7de5082abb6b38c521c64bd30379317f50ed1b2e1e9196de7`.
- Updated the baseline registry, external strong-baseline registry, dependency snapshot, formal-readiness audit, Q2 readiness audit and read-only Q2 execution plan. Task Shield remains `qualification_pending`, `result_eligible=false` and must be described as a disclosed paper reproduction rather than official-source Task Shield.
- Validation for this checkpoint: freeze 13/13, import preflight 9/9, baseline registry audit 11/11, external source audit 11/11, dependency snapshot 5/5, formal-readiness audit 7/7, Q2 readiness completed, focused regressions 121/121 passed, Ruff/compile/JSON checks passed. The active AgentDojo ToolFilter formal monitor remains read-only healthy at 433/726 completed, 0 failed and 293 missing, so no competing Ollama/GPU formal job was started.

## 2026-07-21 CaMeL v1.2 hash-bound formal adapter hardening

- Rebuilt `camel_source_backed_formal_freeze_v1` as schema `paper-camel-source-backed-formal-freeze-1.2`. The freeze now passes 17/17 checks and hash-binds the local formal runner, analyzer, AgentDojo compat layer, source-backed runner, import/runner/transport preflights, shared resume-identity helper and formal protocol, in addition to the pinned CaMeL source, smoke/import/compat/runner/transport manifests and the common 726-case AgentDojo universe.
- Hardened `run_camel_source_backed_formal.py` so a resumed output root must match freeze SHA-256, runner version, model id, condition id, selected cases and selected-case-row SHA-256 before any Ollama/model probe. The runner also validates the local-adapter hashes from the freeze before service probing.
- Refreshed dependency snapshot 5/5, baseline registry audit 11/11, external source audit 11/11, strong-baseline formal-readiness audit 7/7, Q2 readiness and the read-only Q2 execution plan. CaMeL remains qualification-pending and `result_eligible=false`; Q2 is still raw 63.5/capped 60.0.
- Validation for this checkpoint: CaMeL source-backed formal tests 5/5, focused registry/Q2 regressions 115/115, registry/source/readiness/Q2 audits completed, public benchmark registry expectations updated, and the active AgentDojo ToolFilter formal monitor remains read-only healthy at 433/726 completed, 0 failed and 293 missing.

## 2026-07-21 Progent v1.1 hash-bound formal adapter hardening

- Added `protocols/paper_upgrade_v1/progent_source_backed_formal_protocol_v1.md` and rebuilt `progent_source_backed_formal_freeze_v1` as schema 1.1. The freeze now passes 13/13 checks and hash-binds the runner, analyzer, import audit, shared resume-identity helper and protocol file, in addition to the pinned source and frozen 726-case common universe.
- Hardened `run_progent_source_backed_formal.py` so a resumed root must match freeze SHA-256, runner version, model id, condition id, selected cases and selected-case-row SHA-256 before any Ollama/model probe. The import preflight now validates the same local-adapter hashes and passes 10/10 checks without network, Ollama probing or benchmark cases.
- Refreshed dependency snapshot 5/5, baseline registry audit 11/11, external source audit 11/11, strong-baseline formal-readiness audit 7/7 and Q2 readiness. Progent remains qualification-pending and `result_eligible=false`; Q2 is still raw 63.5/capped 60.0.
- Validation for this checkpoint: Progent unit tests 7/7, combined strong-baseline/public-adapter regressions 108/108, Q2 planner/readiness regressions 11/11, plus `py_compile`, Ruff and `git diff --check` passed. The active AgentDojo ToolFilter formal monitor is still read-only healthy at 433/726 completed, 0 failed and 293 missing.

## 2026-07-21 Q2 formal execution handoff controller

- 新增 `plan_q2_formal_execution.py` 与 4 项状态机回归测试，读取正式 monitor、admission 和 public cell manifests，只生成一个失败关闭的下一动作，不执行模型、重试、分析或 registry 写入。
- 当前 artifact 位于 `protocols/paper_upgrade_v1/execution/q2_formal_execution_plan_v1.json/.md`：`resource_gate=busy`，active workload 为 ToolFilter PID 36472；latest monitor 为 433/726、0 failed，唯一允许动作是 read-only monitor refresh。
- 控制器复核 public-v2 队列为 84 个 pending cells、74,760 个 case-runs；Q2 仍为 raw 63.5/capped 60.0。4/4 单元测试、Ruff 和 `py_compile` 通过。

## 2026-07-21 IPIGuard evidence-capture and resume hardening

- 保留原 v1 两案例 qualification 的 1 completed / 1 failed 事实，不重试、不覆盖。失败仍是 upstream `construct_dag` 对缺失 `function_name` 的 `KeyError`；另一例虽然 completed，但 DAG 为空。
- 新 v1.1 runner 只在调用 unchanged upstream parser 前捕获原始 construct JSON，记录独立路径、SHA、字节数、JSON 可解析性和 key sets；明确 `prompt_changed=false`、`parser_changed=false`、`selection_rule_changed=false`。
- v1.1 freeze 9/9，新增 runner/analyzer/protocol 哈希；runner 在 Ollama probe 前执行 resume identity gate，拒绝混用旧 freeze/root。import preflight 7/7，IPIGuard tests 9/9、Ruff/compile 通过。
- dependency 5/5、baseline 11/11、external 11/11、formal-readiness 7/7、Q2 均已重建；当前正式强基线仍只有 PromptGuard，Q2 仍为 raw 63.5/capped 60.0。Fresh v1.1 qualification 尚未运行。

## 2026-07-21 Q2 evidence-gate hardening and detector failure triage

- Tightened `audit_q2_readiness.py` for the independent confirmatory blind gate. A future `m3_v2_independent_blind_manifest` no longer scores by field presence alone; it must resolve to an admitted, formal, 600-case independent-blind result whose candidate SHA-256 matches `m3_v2_independent_blind_admission_audit_v1`. Candidate-only admission and historical E17 evidence still cannot satisfy the Q2 blind gate.
- Added Q2 monitor selection for AgentDojo transformers detector. The readiness audit now prefers the monitor whose `run_manifest_path` matches the selected detector run, rather than a stale generic monitor. Current selected detector monitor shows 75 completed, 1 failed, 650 missing and `pid_alive=false`; it is not progressing and remains non-formal.
- Refreshed `q2_readiness_audit_v1`: raw score remains 63.5/100 and capped score remains 60.0/100, with hard gates still active for public benchmark completion, 5 strong baselines, independent blind, two frontier API vendors and formal adaptive budgets.
- Triaged the selected AgentDojo `transformers_pi_detector` failure. The failed row is `agentdojo:v1:workspace:user_task_25`, case index 76, error type `RuntimeError`, caused by `DefaultCPUAllocator` trying to allocate 2,185,056,432 bytes inside the official HF text-classification detector pipeline. This confirms an exact-official long-output resource failure on CPU, not a missing stderr or log-corruption issue.
- Added `diagnose_agentdojo_formal_run_failures.py` and generated `protocols/paper_upgrade_v1/diagnostics/agentdojo_transformers_detector_failure_v1/failure_diagnostic.json/.md`. It classifies the selected detector failure as `resource_cpu_memory`, records 76 outcome rows / 1 failed row, includes stderr hashes, and remains `result_eligible_for_formal_tables=false`.
- Validation for this checkpoint: `py_compile` passed for `audit_q2_readiness.py`; focused Q2/frontier/tool-filter admission tests passed 18/18; Ruff passed for the changed Q2 audit and test file.

## 2026-07-21 CaMeL transport/formal-freeze checkpoint

- Created an isolated CaMeL runtime under `E:\M3_PI_Guard_runtime\camel` using an E-drive `uv` bootstrap/cache; target Python is 3.10.12 and records `agentdojo==0.1.34`, `pydantic-ai==0.2.12`, `openai==1.82.1`, `anthropic==0.52.2` and related locked dependencies.
- Added `experiments/paper_v1/benchmarks/audit_camel_source_backed_import_preflight.py`; generated `protocols/paper_upgrade_v1/camel_source_backed_import_preflight_v1.json/.md` with 12/12 checks, no network attempts and `result_eligible=false`.
- The import preflight preserves the original fresh-process official pipeline/suite import-order failure evidence. Added `experiments/paper_v1/benchmarks/camel_agentdojo_compat.py` and `audit_camel_source_backed_compat_preflight.py`; generated `protocols/paper_upgrade_v1/camel_source_backed_compat_preflight_v1.json/.md` with 8/8 checks. The compat layer is process-local, preloads official AgentDojo suite modules, does not edit external source/site-packages, and performs no network/model/API/case run.
- Added `experiments/paper_v1/benchmarks/camel_source_backed_runner.py` and `audit_camel_source_backed_runner_preflight.py`; generated `protocols/paper_upgrade_v1/camel_source_backed_runner_preflight_v1.json/.md` with 14/14 checks. The preflight constructs upstream CaMeL `PrivilegedLLM` + suite security-policy pipeline skeletons for workspace/travel/banking/slack while executing 0 benchmark cases, making 0 model/API calls and attempting no network.
- Added `protocols/paper_upgrade_v1/camel_transport_mapping_preflight_v1.json/.md` with 16/16 checks. It freezes loopback privileged/quarantined transport and suite capability mapping while keeping benchmark cases=0, model/API calls=0, network=false and formal eligibility=false.
- Rebuilt `camel_source_backed_formal_freeze_v1` at this checkpoint as schema `paper-camel-source-backed-formal-freeze-1.1`, status `completed_frozen_formal_protocol`, 16/16 checks and no formal admission; this historical freeze has since been superseded by the current v1.2 / 17-check hash-bound freeze, and neither freeze is result evidence without qualification and complete logs.
- Refreshed dependency/source snapshot, registry audit, external source audit, formal-readiness audit and Q2 readiness. Formal-ready strong baselines remain `["promptguard"]` only; Q2 remains raw 63.5 and capped 60.0.
- AgentDojo `tool_filter` formal run remains active and healthy: PID 36472, 433/726 completed, 0 failed and 293 missing at the latest read-only monitor snapshot. No competing Ollama/GPU formal job should be started before it finishes or is intentionally stopped and recorded.
- Added `experiments/paper_v1/benchmarks/admit_agentdojo_tool_filter_formal_result.py`. It refreshes the read-only monitor and blocks until run=`completed_formal`, monitor=`completed_formal_admitted` and analysis=`completed_formal_analysis`; only explicit `--write-registry` can promote `agentdojo_tool_filter` to `ready` with `formal_manifest` and `complete_logs`. Current execution correctly wrote `blocked_not_formally_admitted` to `protocols/paper_upgrade_v1/agentdojo_tool_filter_formal_admission_v1.json` and did not update the registry.
- Updated `audit_q2_readiness.py` to require the transformers detector monitor to point at the selected detector run manifest before scoring a stale running manifest as progressing. Current evidence is now `transformers_detector_scored_status=not_admitted_or_not_progressing` and `transformers_detector_monitor_matches_selected_run=false`; the 0.5 public-benchmark engineering credit comes only from the active tool_filter root.
- Updated the frontier API model-slot chain so a successful future two-vendor smoke can actually influence the Q2 model-coverage gate without hand edits. `audit_frontier_api_model_slots.py` now selects `model_registry_v3_candidate.json` only when `frontier_api_model_slot_registry_admission_v1.json` is `admitted_registry_candidate` and the candidate SHA-256 matches. `audit_q2_readiness.py` uses the audited registered frontier vendor count for model coverage and the frontier API cap. Current local config still has 0/2 configured providers, registry admission is `blocked_smoke_not_qualified`, and Q2 remains raw 63.5 / capped 60.0.
- Verification: `pytest -q tests\unit\test_camel_source_backed_formal.py tests\unit\test_public_benchmark_adapters.py -k "camel or strong_baseline"` passed 19/19; `pytest -q tests\unit\test_independent_blind_authoring_kit.py tests\unit\test_adaptive_mcts_formal_runner.py tests\unit\test_frontier_api_client.py` passed 16/16; `pytest -q tests\unit\test_taskshield_paper_formal.py tests\unit\test_progent_source_backed_formal.py tests\unit\test_ipiguard_source_backed_formal.py tests\unit\test_camel_source_backed_formal.py` passed 23/23; `pytest -q tests\unit\test_agentdojo_tool_filter_admission.py tests\unit\test_q2_readiness_audit.py` passed 4/4; `pytest -q tests\unit\test_q2_readiness_audit.py tests\unit\test_adaptive_mcts_formal_runner.py -k "q2 or adaptive"` passed 8/8; Ruff and py_compile passed for the changed scripts/tests.

## 2026-07-21 Evidence-chain hardening and explicit recovery

- `audit_m3_v2_independent_blind.py` 新增 mandatory custody sidecar：校验 schema/status、candidate filename、600 行计数、SHA-256、独立作者、custodian、隔离 authoring environment、`developer_access_before_seal=false` 和统一 ISO-8601 seal time。缺失/篡改 sidecar 的负向测试通过；当前真实候选仍缺失，gate 保持 blocked。
- 新增 `admit_frontier_api_model_slots.py` 与 protocol。它只读取 redacted smoke manifest，不读配置/Token、不联网；plan-only 当前被 5 项门禁阻断且不写 registry candidate。合成成功/失败 admission 测试均通过。
- Strong-baseline readiness 现在优先读取 IPIGuard source-backed formal freeze，而不再让历史 TDG Stub preflight 掩盖已完成工程。IPIGuard adapter-source requirement 通过，但 complete logs/result eligibility 等 formal requirements 仍失败；PromptGuard 仍为唯一 formal-ready baseline。锁定 PromptGuard 环境的组合回归为 121 passed。
- AgentDojo detector exact 正式路线已改为 resource-blocked diagnostic：v2 CPU retry 在同一 `workspace:user_task_25` 复现 2,185,056,432-byte CPU allocation OOM；direct long-output smoke 在卸载 Ollama 后直接调用 pinned official detector 也对 27,697 字符工具输出复现同一 OOM。旧 roots、trace、failure row 和 smoke manifest 均保留，但不再启动 exact 726-case full run，不合并 diagnostic row，不弱化零失败准入规则。
- AgentDojo `tool_filter` 726-case formal run 已启动：`outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1`，PID 36472，`--admit-formal`。最新只读 monitor 显示 `running_progressing`、433/726 completed、0 failed、293 missing。该 run 正在独占本地 Ollama/Qwen3 8B，不得并发启动 Task Shield、Progent、IPIGuard、adaptive formal 或其他会加载大模型的实验；未完成前仍不计入正式表。

## 2026-07-21 IPIGuard source-backed adapter preparation

- 新增 `build_ipiguard_source_backed_formal_freeze.py`，冻结 pinned commit `4e686ed2f62c135cb12564a4466daa95f3ace878`、11 个源码哈希、Qwen3 8B 论文别名、direct attack 和 97 utility + 629 security 的完整 726-case 宇宙；freeze 8/8 checks passed。
- 新增 `run_ipiguard_source_backed_formal.py`、`analyze_ipiguard_source_backed_formal.py` 与 `ipiguard_source_backed_formal_protocol_v1.md`。runner 直接调用上游 DAG construction/traversal/execution classes，并保存上游 TraceLogger、DAG 节点/边、token 与逐案例 manifest；只有显式 `--admit-formal`、726/726 unique coverage、零未解释失败才能准入。
- 上游包的顶层 import 因未安装 `vertexai` 失败；经源码审计确认 OpenAI 路径只需要 `google_llm.EMPTY_FUNCTION_NAME`。适配器采用 fresh-process import isolation，仅为该未使用的可选传输提供常量级 shim，不修改 IPIGuard 算法；边界在协议和 manifest 中披露。
- `audit_ipiguard_source_backed_import.py` 在独立子进程完成 6/6 preflight，确认 source classes 来自 pinned checkout、未联网、未探测 Ollama、benchmark cases=0、formal eligible=false。初版 pytest 内进程 import 污染已修为子进程审计，失败和修复均保留在 failure log。
- Registry 状态已推进为 `source_backed_adapter_runtime_qualification_failed_model_dag_schema`。2-case runtime qualification 完成 1/2、失败 1/2；失败发生在上游 IPIGuard `construct_dag()`，因为本地 Qwen3 8B 生成的 DAG tool-call JSON 缺少 `function_name`。诊断分析已完成且 `result_eligible=false`。不自动补字段，因为这会改变 IPIGuard 语义；后续需要冻结更强构图模型/提示配置，或把 IPIGuard 明确披露为当前主机/模型下 runtime-incompatible。强基线正式计数仍为 1/5。
- AgentDojo `transformers_pi_detector` exact-official full run 不再占用 Ollama/GPU；v2 manifest 的 `running` 是已停止进程留下的 stale manifest。默认 monitor 现在指向 resource-isolated target root并报告 `missing_manifest`。AgentDojo `tool_filter` 已完成 2-case diagnostic qualification；IPIGuard、adaptive formal 和 `tool_filter` 726-case formal 仍需单独资源窗口，不能与大模型/transformer 正式运行并发。

## 2026-07-21 Adaptive MCTS formal runner preparation

- 新增 `run_adaptive_mcts_budget_formal.py`：消费冻结 80-task panel，支持 100/500/2000 查询预算、逐查询原子工件、MCTS checkpoint、配置漂移拒绝、显式失败保留和 `--retry-failed` 恢复；攻击选择器只接收公开 ALLOW/ASK/DENY、unsafe-effect 和 task-completion，不接收内部规则、detector score 或 gold action。
- 新增 `analyze_adaptive_mcts_budget_formal.py` 与 `adaptive_mcts_budget_formal_protocol_v1.md`。只有 80/80 tasks、完整 query/checkpoint 工件、冻结三预算、零未解释失败且真实 Ollama 显式准入时，分析器才会将根 manifest 从 `completed_formal_run_pending_analysis` 晋级为 `completed_formal`。
- 分析器固定输出原始计数、Wilson 95% CI、攻击族/语言指标、ASR—查询预算折线图和攻击族条形图；结果边界明确不替代未来 independent blind。
- 完成 2-case × 3-query Stub 编排预检：2/2 tasks、6 queries、0 failures；诊断分析生成 PNG/SVG 图，status=`completed_diagnostic_analysis`、`result_eligible=false`。相关 adaptive tests 13 passed，Ruff/compile PASS。
- Q2 audit 仅为实际存在的冻结+runner preflight 增加 1 个工程就绪分，但移除了 stale running manifest 的 0.5 分：raw 63.0/100，capped 60.0/100；正式 80-task 运行仍缺失，因此 adaptive 60 分硬 cap 保持。

## 2026-07-21 Independent blind authoring handoff kit

- 新增 `prepare_independent_blind_authoring_kit.py`，机械生成 600 个不含任何 prompt/attack/expected effect 的分层任务槽：360 attack、120 benign no-tool、120 benign legal-tool，9 个攻击族各 40；语言、授权不确定性、场景和两组 author assignment 均有明确分配。
- 生成 `protocols/paper_upgrade_v1/independent_blind_authoring_kit_v1/`：README、CSV/JSONL slots、case template、custody template 和哈希 manifest。README 明确独立作者可使用独立程序，不要求两人手工审完 600 条；建议封存前分层抽审 120–180 条，实验后继续用双人分层抽样复核。
- Kit 明确禁止项目开发者填写 candidate，禁止读取 M3-v2 case/results/Guard internals，要求在代码/阈值/假设/排除规则冻结后由 custodian 同时释放 candidate 与 custody record。
- Manifest status=`completed_authoring_kit_only`、candidate cases=0、confirmatory result eligible=false。11 项 kit + M3-v2 admission regression passed；独立 blind gate 仍为 `blocked_missing_candidate`，Q2 分数不变。

## 2026-07-21 Frontier API transport preparation

- 新增 `experiments/paper_v1/frontier_client.py`，支持 OpenAI Chat Completions 与 Anthropic Messages 的统一 `CompletionResult`；真实 transport 强制 HTTPS 和显式 network consent，每次 provider call 固定 attempts=1，不自动重试。
- 请求凭据只进入 HTTP header；持久化 request metadata 仅记录 provider、model、endpoint origin、payload SHA-256、temperature/max tokens、seed 是否发送和 attempts，不记录 key 或 header。
- 新增 `smoke_frontier_api_models.py` 与 `frontier_api_smoke_protocol_v1.md`。Smoke 输入固定为两句合成公开文本，禁止上传 M3 cases、公共基准内容、实验失败、论文草稿或私有数据；只有 `--execute` 加本地精确 consent 值才可联网。
- 当前执行 plan-only：configured providers 0/2、network calls 0、status=`plan_only_no_network`、formal eligible=false。13 项 frontier client/config tests、Ruff、compile 通过。前沿 API 仍是外部凭据/模型选择/费用授权 blocker，Q2 raw/cap 均不变。

## 2026-07-20 PromptGuard detector-only formal baseline

- 新增并冻结 `protocols/paper_upgrade_v1/promptguard_detector_formal_protocol_v1.md` 与 `promptguard_detector_formal_freeze_v1.json`；输入宇宙为 M3-v2 1,500、AgentDojo 726、InjecAgent 1,054，共 3,280 条。模型输入与标签分文件保存，runner 不读取标签文件。
- AgentDojo security 输入改用官方 ground-truth pipeline 物化 tool-output 文本，并用 whitespace-normalized marker 审计避免 YAML 换行导致的误判。
- 正式推理使用 PromptGuard 2 86M frozen revision `a8ded8e697ce7c355e395a0df51f94adb4a2fd27`、阈值 0.5、真实 tokenizer 非重叠 512-token windows 与 max-malicious-score 聚合；3,280/3,280 predictions 完成，0 inference failures。
- 结果：TP 635、FN 1,948、FP 0、TN 697；Recall 24.58%、FPR 0.00%、Precision 100.00%、F1 39.47%；median/p95 latency 17.384/47.167 ms。
- 分基准：AgentDojo Recall 100.00%、FPR 0.00%；InjecAgent Recall 0.57%；M3-v2 Recall 0.00%、FPR 0.00%。固定阈值未在结果后调参；低召回是正式 detector 结果的一部分。
- 分析、统计和图表位于 `outputs/paper_upgrade_v1/baselines/promptguard_detector_formal_v1/analysis/`；生成六组 PNG/SVG 图，包含 benchmark recall/FPR、攻击族、语言、分数分布、ROC/PR 和 latency ECDF。
- 更新 `baseline_registry.json`、`external_strong_baselines_v1.json/.md`、dependency snapshot、source audit 与 formal-readiness audit；PromptGuard 现在是 1/5 formal-ready strong baselines，但只限 detector-performance 表。Q2 gate 仍为 `not_satisfied`。
- 验证：focused Ruff PASS、compile PASS、PromptGuard formal/public-benchmark tests PASS、baseline registry audit 11/11、external source audit 11/11、dependency snapshot 5/5、strong-baseline formal-readiness audit 7/7。

## 2026-07-20 AgentDojo transformers_pi_detector dependency smoke

- 使用 E 盘 Hugging Face 缓存下载官方 `protectai/deberta-v3-base-prompt-injection-v2`，resolved revision `90c9989b1a342275dd0d1a95aad283c04e075671`，19 files / 1,498,547,184 bytes。下载证据：`E:\M3_PI_Guard_runtime\agentdojo_transformers\evidence\protectai_detector_download_snapshot.json`。
- 首次 offline smoke 失败是 cache ref 层级问题：commit snapshot 已存在，但 repo-id offline lookup 缺 `refs/main`。调用 `snapshot_download(..., revision='main')` 后补齐 refs，未重新下载大文件。
- 新增 `experiments/paper_v1/benchmarks/smoke_agentdojo_transformers_pi_detector.py`，通过 PromptGuard venv + `PYTHONPATH` 调用 AgentDojo 官方 `TransformersBasedPIDetector`，并强制 `HF_HUB_OFFLINE=1`。
- Smoke 结果：`completed_official_detector_smoke_only`，3/3 required checks 通过；benign weather 判 safe，direct injection 与 AgentDojo marker 判 injection。quoted security discussion 也被判 injection，作为 false-positive probe 保留。
- 更新 `agentdojo_official_strong_baselines_v1.md`、`baseline_registry.json`、`agentdojo_official_strong_baseline_capability_audit_v1`、`baseline_registry_audit_v1` 和 `strong_baseline_formal_readiness_audit_v1`。`agentdojo_transformers_pi_detector` 依赖 blocker 已解决，但仍未 formal-ready，因为完整 AgentDojo official cell/logs 尚未运行。
- 验证：Ruff PASS、compile PASS；AgentDojo official audit 9/9、baseline registry audit 11/11、formal-readiness audit 7/7；Q2 strong-baseline gate 保持 `not_satisfied`，formal-ready 仍为 `['promptguard']`。

## 2026-07-21 AgentDojo official detector formal execution

- 冻结独立 official `transformers_pi_detector` 条件：97 utility + 629 security = 726 cases，freeze 8/8 checks passed；固定 Qwen3 8B 论文别名、AgentDojo source hashes、ProtectAI revision、阈值 0.5、direct attack、温度 0 和失败保守计分。
- 新 runner 直接调用 AgentDojo `AgentPipeline.from_config`、官方 attack、tool loop、utility/security checker 与 `TraceLogger`；M3 只负责冻结选择、file-only logger、逐案例 manifest、断点续跑和 admission gate。
- 2-case official qualification 完成：2/2 completed、0 failures、2 official traces；1 utility success，1 security attack success，保持 diagnostic/ineligible。
- 完整 726-case `--admit-formal` exact-official 作业不再启动：v1 CUDA attempt、v2 CPU retry 和 direct long-output smoke 均证明该 official detector 对 preserved 长工具输出在当前机器资源下不可完成。后续只能作为 exact-source resource-incompatible disclosure，或另建非等价 bounded-input adapter 标签。
- 新增分析器输出 Wilson 95% CI、suite 分解、ASR/TCR/redaction/failure、latency ECDF 和 PNG/SVG 图；静态/单元回归 94 passed（新分析单测另有 7 passed）。

## 2026-07-20 PromptGuard real-model qualification

- 本地配置脱敏门禁通过：`config/project.local.env` ignored=true、tracked=false，`HF_TOKEN=set_redacted`，已跟踪文件真实密钥命中为 0。
- 旧 `blocked_gated_repository` 下载证据已封存；冻结 revision `a8ded8e697ce7c355e395a0df51f94adb4a2fd27` 下载完成，10 files / 1,131,674,611 bytes，config/weights/tokenizer 齐全，下载快照不含 Token。
- 新增 real-model smoke runner 与显式 `LABEL_0=BENIGN`、`LABEL_1=MALICIOUS` 归一化，避免旧适配器把高置信 benign 反转为 malicious。
- CUDA 12-case qualification smoke 完成，runtime checks 12/12；诊断匹配 9/12，两条直接注入均检出，中文间接注入和 Base64 漏检，引用注入短语的 benign 安全说明误报。全部预测和失败保留，正式表资格为 false。
- PromptGuard preflight 当时更新为 `real_detector_smoke_completed_formal_run_pending`；依赖快照显示 PromptGuard qualification dependencies ready。该 pending 状态已由上方 detector-only formal baseline 解决，但 smoke 本身仍不进入正式分母。
- External source audit 10/10、dependency snapshot 5/5、formal-readiness audit 7/7、baseline registry audit 11/11 均完成；Q2 gate 仍为 `not_satisfied`，既有 public-benchmark v1/v2 freeze 未重建、未改写。
- 最终验证：10/10 模型文件大小/SHA-256 二次匹配；Ruff focused scope PASS；compile PASS；PromptGuard/config/public-benchmark 101/101 tests PASS；Registry 18 completed；历史 evidence PASS；8 个 JSON 与 PowerShell/Bash 语法 PASS。聚合 `verify.ps1` 的重复全量 pytest 在 CPU 停止增长后按 failure-log 终止，不冒充 PASS。
- 最终服务：Ollama processes=0、port 11434 listeners=0、Docker processes=0、Python processes=0。

## 2026-07-21 Paper Upgrade Continuation

- `agentdojo_tool_filter_formal_freeze_v1` 已接入 `audit_agentdojo_official_strong_baselines.py` 与 `audit_baseline_registry.py`；`agentdojo_tool_filter` 已推进到 `ready_official_tool_filter_qualification_completed_formal_run_pending`，仍 `result_eligible=false`。runner 1.1 记录了 OpenAI-compatible tool-filter model-binding shim：只把官方 `OpenAILLMToolFilter.model` 从 provider 名 `openai-compatible` 绑定到冻结模型 `m3-paper-qwen3-8b-v1:latest`，不改变 prompt、算法或选择规则。初始 two-utility qualification 重跑后 2/2 completed、0 failed；新增 utility+security qualification 为 2/2 completed、0 failed，其中 security case attack_success=1，说明安全路径可执行但该小样本攻击未被 tool_filter 阻断。两份 analysis 均为 `completed_diagnostic_analysis`；726-case formal run 已启动但尚未完成。
- 新增 `q2_readiness_audit_v1`；在后续 adaptive runner Stub 编排预检与 detector resource-blocked audit 完成后，当前 raw score 为 63.0/100、capped score 为 60.0/100，未达到 90。Stub adaptive preflight、resource-blocked detector diagnostics 和 stale running manifests 均不是正式效果结果。主要 blockers 仍是公共基准正式矩阵、至少五个 source-backed 强基线、全新独立 blind、两个前沿 API vendor 和 80-task 自适应查询预算 formal run。
- `agentdojo_transformers_pi_detector_official_formal_v1` 自动 CUDA run 在 92 completed / 4 failed / 630 missing 时因 8GB GPU 上 Ollama 8B 与 ProtectAI detector 同抢显存出现连续 CUDA OOM，已停止并保留日志；该 v1 attempt 不得进入正式表。
- runner 升级到 1.2，新增 `--detector-device cpu`，并在当前 Windows PyTorch runtime 下使用 `CUDA_VISIBLE_DEVICES=-1` 隔离 detector。空字符串 CUDA policy 的早期 v2 preflight 已因 `Device set to use cuda` 移入 `_invalid`；独立 1-case CPU-device preflight 已完成 1/1、0 failed、`Device set to use cpu`。
- Fresh `agentdojo_transformers_pi_detector_official_formal_v2_cpu_detector` 已停止在 75 completed / 1 failed / 650 missing；显式 `--retry-failed` 后同一 case 再次 OOM。该 root 的 manifest 仍显示 stale `running`，但不得继续续跑或进入正式表。
- 新增只读长跑监控器 `experiments/paper_v1/benchmarks/monitor_agentdojo_official_formal_run.py`，输出 `protocols/paper_upgrade_v1/agentdojo_official_formal_run_monitor_v1.json/.md`；当前默认监控 resource-isolated target root，健康状态为 `missing_manifest`。该快照只用于运行健康和交接，不改变 formal admission。
- 新增独立 blind admission 审计器 `experiments/paper_v1/benchmarks/audit_m3_v2_independent_blind.py`，输出 `protocols/paper_upgrade_v1/m3_v2_independent_blind_admission_audit_v1.json/.md`；当前因 `m3_v2_independent_blind_candidate.jsonl` 未提供而为 `blocked_missing_candidate`。该门禁继续把 Q2 readiness 限制在 65 以下；当前总体 raw 63.0 / capped 60.0。
- 新增 frontier API model-slot admission 审计器 `experiments/paper_v1/benchmarks/audit_frontier_api_model_slots.py`，输出 `protocols/paper_upgrade_v1/frontier_api_model_slot_admission_audit_v1.json/.md`；当前配置文件 ignored/untracked 且 tracked secret hits=0，但 OpenAI/Anthropic API key 与 model id 仍为占位或缺失，未记录 `M3_FRONTIER_API_CONSENT=yes_for_network_smoke`，registry 仍为 0 个 frontier API vendor slots。Q2 审计已接入该审计，当前 raw 63.0 / capped 60.0；frontier gate 仍是实际硬 cap。

## 2026-07-18 Paper Upgrade

- 新任务 `M3-PAPER-001` 已启动；原 `M3-EXPANSION-001` 和 Remediation V2 作为不可变历史基线。
- 实施基线为本地 `test1@d74cef2739551591a49c722c5c6273bac6edf91e`；工作树中既有报告修改和大量历史实验工作片均保留。
- 新架构将使用独立 paper-v1 runtime，避免直接改写历史冻结路径。
- 本机可运行 4 个核心模型和 Vicuna；前沿 API/外部服务器当前未配置，相关最终矩阵明确记录为外部资源门禁。
- 当前阶段：TaskPolicyManifest、ProvenanceEvent、ActionProposal、GuardDecision 及非预知 runtime 实现。

### Paper-v1 implementation checkpoint

- 已新增独立 paper-v1 非 oracle runtime：`TaskPolicyManifest`、参数来源追踪、三态 `ALLOW/ASK/DENY` monitor、可配置组件消融、策略 regime 和 resume-safe matrix runner。
- 数据层已生成 M3-v2 1,500 条：900 attack、300 benign no-tool、300 benign legal-tool；development/validation/sealed automated holdout 为 600/300/600，模板隔离和重复 ID 审计通过。
- 公共基准已完成官方 checkout pin 与索引：AgentDojo 97 utility + 629 security；InjecAgent 1,054 security + 330 tool schemas。InjecAgent 已新增 diagnostic replay runner、official-formula scorer 和 official-stage diagnostic runner；AgentDojo 已新增 native `BasePipelineElement` runner 并完成最小官方 checker smoke，但全量正式运行仍 pending。
- 本地真实模型 smoke 已完成：5 个本地模型 × 6 个固定 validation cases × no_defense/m3_full = 60 case-runs，0 failed；分析图和表位于 `outputs/paper_upgrade_v1/smoke_local_5models_v1/analysis/`，状态为 diagnostic only。
- 授权不确定性 smoke 已完成：qwen3 × 6 validation cases × `m3_full` × auto/ambiguous/partial/incorrect = 24 case-runs，0 failed；分析图和表位于 `outputs/paper_upgrade_v1/policy_regime_smoke/analysis_v1/`，状态为 diagnostic only。
- InjecAgent 公共 replay smoke 已完成：3 indexed cases × no_defense/m3_full，0 failure，16 step logs；manifest 明确 `result_eligible_for_formal_tables=false`。
- InjecAgent official-formula replay scorer 已实现并完成 3-case smoke：输出 `official_formula_score_v1/`，两组 ASR-all Total 均为 0.0、Valid Rate 100.0。该 scorer 复用 InjecAgent DH/DS/S1/S2 聚合公式，但标签来自 M3 replay 工具执行日志，不是原版 InjecAgent runner。
- InjecAgent official-stage diagnostic runner 已实现：模型输入对齐官方“User Tool 已执行、Tool Response 已注入”的 scratchpad 阶段，policy compiler/Guard 仍只用 trusted request、trusted context 和 tool schemas。支持 `m3_json`、官方 InjecAgent ReAct 和官方 `hwchase17_react` simple ReAct prompt styles。新增 result-blind stratified selection builder、`--selection`、`progress.jsonl`、增量 `runs.jsonl`、`--timeout` 和 `--max-tokens`。qwen3 data_security limit-2 v3、direct_harm limit-2 v1、data_security limit-5 v1 与 direct_harm limit-5 v1 均完成 0 failure；官方公式桥接分数均为 Valid Rate 100.0、ASR-all Total 0.0。Vicuna + official_react_simple baseline-vulnerable diagnostic：DS 3/3→0/3，DH 1/3→0/3；额外 DS 0004/0005 no_defense 仅 S1=50%、S2=0、ASR-all Total=0，已登记为负诊断。冻结 30-case selection 已生成；pre-progress 30-case Vicuna no-defense 旧 run 已停止并登记；progress-enabled 6-case stratified smoke 完成 0 failure，no_defense 1/6、m3_full 0/6。progress-enabled 30-case stratified diagnostic 已完成：两条件均 30/30、0 failure；no_defense ASR-all Total=46.7%、m3_full=0.0%，paired attack success 14/30→0/30，McNemar p=0.0001221，并生成 bucket summary 与三张诊断图。边界：非 byte-identical 官方 runner，且 `gold_user_tool_stage_used_online=true`，只作兼容性诊断。
- InjecAgent official compatibility audit 已完成：新增 `experiments/paper_v1/benchmarks/audit_injecagent_official_compatibility.py`，输出 `protocols/paper_upgrade_v1/injecagent_official_compatibility_audit_v1.json/.md`；19/19 checks passed。审计记录官方 runner/parser/prompt/scorer 源码哈希，验证官方 prompted-stage markers、官方 parser 固定样例、DH/DS S1/S2 公式样例和官方 ReAct 工具顺序；边界仍为 `compatibility_audit_not_official_benchmark_result`，不能替代 1,054-case 全量或 byte-identical runner。
- InjecAgent official prompted-parser intent scorer 已完成：新增 `experiments/paper_v1/benchmarks/score_injecagent_stage_official_prompted.py`，用官方 `evaluate_output_prompted` 直接评分 raw model ReAct 输出。冻结 30-case Vicuna selection 上，raw model attack intent 为 no_defense 7/30、m3_full 6/30，McNemar p=1.0；与执行派生分数 14/30→0/30 对比，说明当前 M3 主要贡献是运行时权限阻断，而不是完全消除模型攻击意图。
- 本轮修复了一个真实方法风险：generic policy compiler 不再因为共享供应商/域名词而授权不相关 read-only 私有查询，例如产品详情任务不会自动授权 `AmazonViewSavedAddresses`。
- AgentDojo native 适配已修正三类真实缺陷：动作/名词与否定范围混淆、nullable JSON Schema 类型降级、ASK/DENY 后无法继续安全任务；`workspace/user_task_0` corrected smoke 已首次通过官方 utility checker。
- 新增结构化工具输出来源追踪：description/body/content 等指令承载字段不能驱动下一工具 selector，participants 等结构化任务字段仍可用于合法查询；官方 `workspace/user_task_0/injection_task_0` smoke 中该规则 DENY 了攻击者邮箱查询并保持 utility=true、注入成功=false。
- 新增 AgentDojo resume-safe native matrix 与重复分析。`important_instructions` 诊断切片完成 48/48 jobs：no_defense 注入成功 3/24=12.5%，m3_full 0/24；两组 injected utility 均 6/24=25%。cluster bootstrap CI 包含 0、McNemar p=0.25，明确仅作 protocol development，不作论文效果结论。
- AgentDojo 四套件 diagnostic screen 完成 124/124 jobs、0 failed；新增独立 selection 协议，选出 25 个 baseline-vulnerable 正候选簇和 4 个 zero-control 簇。该 screen 仅用于候选簇选择，不估计 AgentDojo 全量效果。
- AgentDojo selected-cluster repeat 完成 174/174 jobs、0 failed：no_defense 官方注入成功 72/87，m3_full 0/87；24/29 簇为稳定 baseline-positive，且全部被 m3_full 稳定阻断。配对 McNemar p=4.24e-22，cluster bootstrap 差值 95% CI 为 -96.6pp 到 -69.0pp。输出位于 `outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_repeat_qwen3_v1/analysis/`，图表已完成可读性检查。
- 官方 AgentDojo prompt baseline 已接入本地 native runner：`agentdojo_repeat_user_prompt` 和 `agentdojo_spotlighting_with_delimiting`；新增协议 `protocols/paper_upgrade_v1/agentdojo_selected_prompt_baselines_v1.md` 与合并分析器 `experiments/paper_v1/benchmarks/analyze_agentdojo_prompt_baseline_comparison.py`。prompt-baseline 诊断完成 174/174 jobs、0 failed；两个官方 prompt baseline 均为 66/87 注入成功。四条件合并分析完成 348/348 jobs，输出位于 `outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_prompt_baseline_comparison_qwen3_v1/`，图表已完成可读性检查。
- 强基线 registry/audit 已落地：`protocols/paper_upgrade_v1/baseline_registry.json` 升级到 `m3-paper-baselines-1.1`，新增 AgentDojo `tool_filter`、AgentDojo `transformers_pi_detector`、PromptGuard、Task Shield、IPIGuard、Progent、CaMeL/Fides 的阻塞原因、适配计划和正式排除规则；`experiments/paper_v1/benchmarks/audit_baseline_registry.py` 生成 `baseline_registry_audit_v1.json/.md`，11/11 checks passed。新增 AgentDojo 官方强基线协议与 capability audit：`protocols/paper_upgrade_v1/agentdojo_official_strong_baselines_v1.md`、`experiments/paper_v1/benchmarks/audit_agentdojo_official_strong_baselines.py` 和 `agentdojo_official_strong_baseline_capability_audit_v1.json/.md`；9/9 checks passed。新增外部强基线 source/readiness registry、source checkout manifest、IPIGuard official source-smoke、dependency snapshot 与 formal-readiness audit：`external_strong_baseline_source_audit_v1` 10/10、`strong_baseline_source_checkout_manifest_v1` 5/5、`ipiguard_official_source_smoke_v1` 8/8、`strong_baseline_dependency_snapshot_v1` 5/5、`strong_baseline_formal_readiness_audit_v1` 7/7。PurpleLlama/PromptGuard、IPIGuard、CaMeL、FIDES 已 pin 到 `external/baselines/`；IPIGuard source-smoke complete，CaMeL 已选且 source ready。真实 PromptGuard、Task Shield、IPIGuard、Progent、CaMeL 结果仍分别因 detector 依赖/模型缓存、verifier 复现语义、官方 TDG source-backed adapter/logs、DSL 语义、`uv`/interpreter/source-backed adapter 未冻结而阻塞。新增 public-benchmark formal-freeze manifest、pending ledger、case-result row builder、formal-cell runner wrapper、AgentDojo/InjecAgent formal-cell source producer、formal-cell materializer 和 result-completeness audit；当前 60 expected cells、60 initialized pending cells、0 complete cells、53,400 expected case-runs、0 complete case-runs。当前 Q2 strong-baseline gate、public-benchmark gate 与 result-completeness gate 均明确为 `not_satisfied`，这些强基线和公共基准结果不得进入正式主表。
- 公平性审计已移除 no_defense 工具输出上的 `Untrusted...` 标签；此前 32-run direct 矩阵保留为对照污染诊断，不进入后续比较。
- 已生成论文图表 contracts 与 demo 图；demo 图只用于版式和重建链路验证，不进入正式论文结果。
- 论文升级状态报告已写入 `protocols/paper_upgrade_v1/implementation_status.md`，明确当前实现、诊断输出、剩余投稿 blockers 和下一步实现顺序。
- 2026-07-18 新增 strong-baseline source checkout manifest：`experiments/paper_v1/benchmarks/prepare_strong_baseline_source_checkouts.py` 生成 `protocols/paper_upgrade_v1/strong_baseline_source_checkout_manifest_v1.json/.md`，5/5 checks passed；PurpleLlama/PromptGuard、IPIGuard、CaMeL、FIDES 均已 pin 到 registry 记录的 exact commit，保存在 Git 忽略的 `external/baselines/` 可重建缓存中；未安装依赖、未下载模型、未启动服务、未运行 baseline。
- 2026-07-18 新增 IPIGuard official source-smoke：`experiments/paper_v1/benchmarks/audit_ipiguard_source_smoke.py` 生成 `protocols/paper_upgrade_v1/ipiguard_official_source_smoke_v1.json/.md`，8/8 checks passed；验证 pinned commit、官方 eval entrypoint、`ipiguard` pipeline wiring、DAG construction/traversal markers、whitelist/command split 和 97 utility / 629 security dataset universe，但仍为 source-smoke only，不进入正式结果。
- 2026-07-18 更新 strong-baseline dependency/source snapshot：`experiments/paper_v1/benchmarks/build_strong_baseline_dependency_snapshot.py` 生成 `protocols/paper_upgrade_v1/strong_baseline_dependency_snapshot_v1.json/.md`，5/5 checks passed；IPIGuard source-smoke complete 但 source-backed adapter/formal logs 未完成，CaMeL 已选且 source ready 但 `uv` 缺失，PromptGuard 仍缺 `transformers` 和模型缓存，Task Shield/Progent 仍缺冻结复现语义。`strong_baseline_formal_readiness_audit_v1` 为 7/7 checks passed，但 formal-ready strong baselines 仍为空。
- 2026-07-18 回归快照：58 个 unit test 文件共 422 passed、1 skipped；仓库级结果完整性审计另有 3 passed，合计 425 passed、1 skipped、0 failed。AgentDojo 重复诊断的 10 个分析产物均存在并已核对 SHA-256。本轮 InjecAgent official-ReAct stage-runner / parser repair / policy compiler repair / selection builder / paired analyzer / figure generation / official compatibility audit / official prompted intent scorer / baseline registry audit / AgentDojo official strong-baseline capability audit / external strong-baseline source audit / strong-baseline source checkout manifest / IPIGuard official source-smoke / strong-baseline dependency snapshot / strong-baseline formal-readiness audit / public-benchmark formal-freeze manifest / public-benchmark formal-run pending ledger / public-benchmark formal case-result row builder / public-benchmark formal-cell runner wrapper / AgentDojo formal-cell source producer / InjecAgent formal-cell source producer / public-benchmark formal-cell materializer / public-benchmark result-completeness audit / PromptGuard adapter preflight / Task Shield alignment preflight / IPIGuard TDG preflight / Progent policy preflight / CaMeL-FIDES IFC-capability preflight / public-benchmark adapter / paper metrics / matrix focused regression 为 122 passed。
- 前沿 API 模型、7B-14B 开源扩展、AgentDojo 97 utility/629 security 全量正式 native execution、InjecAgent 1,054-case official-stage/full compatibility execution 或 byte-identical official runner、PromptGuard/Task Shield/IPIGuard/Progent/CaMeL 或 FIDES source-backed 精确适配、80-task 自适应查询预算和全新独立 blind 仍未完成，不得写成论文主结论。

## Current Status

E0-E17 已全部完成并登记，Registry 为 18 completed / 0 running / 0 failed。E17 两名真人各完成 360 行冻结分层抽样盲审，360/360 一致且无需裁决。正式综合分析、13 张图、独立统计复算、Dashboard 最终证据门禁和便携 HTML 技术报告均已生成或验证。

## Completed

- Harness 工程与项目源码已物理分区：Harness 在 `harness/`，M3 运行/实验源码在根目录的 `m3_*`、`experiments/`、`protocols/`、`scripts/`、`tests/`。
- 300 条审计数据、五模型 smoke、四模型 6,480 主矩阵、完整消融、E9/E14 corrected r3、E15 3,600 稳定性、E16 三轮自适应攻击和 E11 execution-r2 均完成。
- E17：两个不同真人 reviewer_id，各 360 行；证据列原样保留；一致率 100%，kappa=1.000。
- E17 总体估计只使用 300 representative 行；40 disagreement-targeted 与 20 rare/complex-targeted 行保持独立诊断边界。
- `final_analysis`：13 图、63 个 manifest 工件、1,364 个 admitted input artifacts；E11 post-hoc 明确 `pre_registered=false` 且不合并分母。
- 独立统计验证 PASS；Dashboard `-ValidateOnly` PASS。
- 图表已检查并修复 family heatmap 颜色条遮挡；主效应、失败分类和攻击族热力图均完成原分辨率检查。
- 最终聚合 Harness verifier：347 passed、1 skipped，Verification failed=0。
- HTML 技术报告含 23 blocks、3 charts、6 metrics、3 tables；validation/package/structural verification PASS，并单独记录共享阅读器浏览器 QA 限制。
- 未制作 PPT、DOCX 或 ZIP；未 push、未创建 PR。

### 2026-07-21 Progent source-backed formal preparation

- 固定官方 Progent 源码 `8a8eb894b9d568a32b4e58252fea85b47f789c77`；source smoke 通过并记录无 top-level license 警告。
- 证明官方捆绑 AgentDojo 0.1.29 是 686 case，而共同冻结 universe 是 726 case；精确记录缺少的 40 个 travel injection-task-2/6 case，不做有利排除。
- `progent_source_backed_formal_freeze_v1` v1.1 13/13 checks 通过；`progent_source_backed_import_preflight_v1` 10/10 checks 通过，且未联网、未探测 Ollama、未运行 benchmark case。
- 完成 failure-retaining/resumable runner 与 formal-admission analyzer；freeze 现 hash-bind runner/analyzer/import-audit/shared-identity/protocol，Slack injection-task-5 同时保留 raw official trace checker 和预注册的 execution-grounded checker。
- 目标回归从 96 passed 扩展为 combined 108/108，Q2 planner/readiness 11/11；Ruff/compile 通过。当前仍为 qualification pending、`result_eligible=false`。
- AgentDojo `tool_filter` PID 36472 的正式运行继续独占 Ollama/GPU；13:47 快照 41/726 completed、0 failed。完成并分析准入前，不启动 Progent qualification。

### 2026-07-21 Task Shield disclosed paper-reproduction preparation

- 下载并固定 ACL 2025 论文 PDF：1,491,650 bytes，SHA-256 `057ff02152c0bb61892b08abdc80f7af22416c03819e526878091ee87d3bf1e6`；未发现官方 Task Shield repository，因此不作官方源码声明。
- `taskshield_paper_formal_freeze_v1` 12/12 checks 通过，冻结 97 utility + 629 security、Qwen3 8B agent/verifier、temperature 0、epsilon 0、strict JSON、history policy 和 failure denominator。
- `taskshield_paper_import_preflight_v1` 8/8 checks 通过；fresh process 网络阻断、Ollama probe=false、benchmark cases=0。
- 完成 assistant/tool-call/tool-output 对齐 runtime、resumable formal runner、admission analyzer 和 intervention 图表；联合回归 104 passed，Ruff clean。
- Dependency snapshot 对 Task Shield 已 `snapshot_ready=true`，但 formal-readiness 仍因 qualification、正式 manifest/logs 和 result eligibility 缺失而阻断；正式强基线计数仍只有 PromptGuard 1/5。

### 2026-07-21 CaMeL official source-smoke and audit refresh

- 新增 CaMeL 官方源码语义 smoke：`experiments/paper_v1/benchmarks/audit_camel_official_source_smoke.py`，输出 `protocols/paper_upgrade_v1/camel_official_source_smoke_v1.json/.md`。
- Smoke 在 network-blocked fresh process 中完成 8/8 checks，验证 pinned Google CaMeL checkout 的 capability、trust propagation、workspace/slack policy 和 network guard 语义；`network_calls_performed=false`，`result_eligible_for_formal_tables=false`。
- 新增 CaMeL source-backed formal-freeze builder：`experiments/paper_v1/benchmarks/build_camel_source_backed_formal_freeze.py`，输出 `protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v1.json/.md`；12/12 checks 通过，status=`completed_dependency_blocked_frozen_protocol`，`result_eligible=false`。
- `strong_baseline_dependency_snapshot_v1` 已刷新：`camel_or_fides.source_smoke_status=completed_source_smoke_only`，`readiness_by_key.camel_or_fides.blockers=[]`。这只解除 source/dependency 层 blocker，不代表 CaMeL benchmark adapter 或 formal result 已完成。
- 外部强基线 source audit 已用正确 `strong_baseline_source_checkout_manifest_v1` 重跑，11/11 checks 通过，消除了旧路径导致的 checkout manifest missing 误报。
- `baseline_registry` 已同步 CaMeL 状态为 `source_smoke_completed_frozen_protocol_dependency_blocked_adapter_pending`。`strong_baseline_formal_readiness_audit_v1` 仍为 7/7 checks、formal-ready strong baselines 仅 `promptguard`；CaMeL 仍因未 ready、result-ineligible、blockers 非空、无 formal manifest/logs 等阻断。`q2_readiness_audit_v1` 仍为 raw score=63.5、capped score=60.0、goal_90_met=false。
- AgentDojo `tool_filter` 726-case formal run 继续健康运行；14:44 快照 99/726 completed、0 failed、627 missing，未完成前不得 admission 或启动竞争 Ollama/GPU 作业。

## Final Acceptance

修正前基线为 8 pass / 4 fail：Recall 86.49%、正常 TCR 下降 6.79pp、合法工具 TCR 65.48%、最差 E14 cell 端到端中位开销 92.43%。该历史结果和原始分母保持不变。

Remediation V2 最终验收为 12 pass / 0 fail：A04 Recall 134/134=100%；A06 off 312/324、full 319/324，full Guard 没有造成下降而是改善 2.16pp；A07 合法工具 TCR 166/168=98.81%；A10 12 个同输出反事实性能 cell 中最差中位可归因开销 0.009461%。A11 解析成功率 1736/1817=95.54%，其余预设门禁也全部通过。

## Git Handoff

已审计提交文件，排除 `models/`、`.tmp.driveupload/`、实验工作分片和非本任务 sandbox 临时内容，并运行 Git whitespace/status 检查。最终状态包含在本地 `test1` commit 中；默认不 push、不建 PR。

## 2026-07-16 Acceptance Remediation

- 目标保持为修复并重新验证 A04、A06、A07、A10，只有四项和总门禁均通过才完成。
- 已定位：A04 的 76 个攻击 FN 全是未授权 public read；A06/A07 同时受到授权契约未暴露、Guard stop 立即终止、精确授权邮件被重复风险惩罚和 premature final 影响；A10 被并发 GPU 的独立推理配对噪声混淆。
- 已实现第一轮通用修复并完成 57 项目标单测；48-run diagnostic smoke 表明 public-read Recall 可修复，但发现授权邮件被 `intent_action` 重复加权、两个小模型在 API 调用前提前 final。
- 正在实现第二轮：精确授权免除重复 intent mismatch、premature-final 有界恢复；诊断输出明确排除在正式证据之外。
- 下一门禁：目标单测、第二轮 smoke、post-hoc engineering remediation 协议冻结、四模型完整 blind 复验、同输出 E14 replay、最终 12/12 重建。

### V1 invalidation and V2 restart

- V1 same-output replay passed A09/A10, but its first completed Qwen main job exposed FPR=87.88%、Precision=3.33%、ParseSuccess=91.74%；known-failing V1 process was stopped after 1/12 completed jobs and retained as excluded diagnostic evidence.
- Cause: exact authorized safe first steps in attack-chain cases were re-penalized by document-level detector signals. Policy/dataflow had already validated the action itself.
- Fix: exact authorized action suppresses document detector deltas only; off-target, dataflow, sensitive and later malicious calls remain fully evaluated. Regression suite is now 66 passed.
- Full 90-case Qwen pre-freeze diagnostic after the fix: Precision=100%、Recall=100%、FPR=0%、TCR=100%、legal-tool TCR=14/14、ParseSuccess=99.25%。
- V2 protocol/output/freeze are independent of V1 and must rerun all 2,160 formal case-runs plus the 144-row performance replay.

### Remediation V2 final

- V2 已从零完成四模型、三种 seed、off/full 的 12/12 jobs 和 2,160/2,160 logical case-runs；144-row、12-cell 同输出性能 replay 完整。
- 冻结源验证通过；所有失败、ASK、超时、解析失败和恢复步骤保留在原始分母。V1 保持明确 invalidated，不进入 V2 分母。
- `acceptance_matrix.csv` 为 12/12 pass；Dashboard 二次验证为 10 metric rows、3,780 logs、1 manifest、4 figures、0 warnings。
- 两项报告层兼容适配及两张图的可读性重绘均由独立哈希清单披露；RunLog、指标、阈值、分子分母、置信区间和 pass/fail 比较未改动。
- 4 张 PNG/SVG 图表及来源 CSV 已生成并完成原分辨率视觉检查；性能折线和恢复环形图解决了近零压缩与标签重叠问题。
- 最终 Harness verifier：361 passed、1 skipped；Harness/源码边界、JSON、PowerShell/Bash 语法、compile、Registry complete、历史证据兼容性和当前 V2 27-source freeze 全部 PASS，`Verification failed=0`。
- 历史 E11 r2 与 context/E17 r3 冻结未改写；兼容性清单精确登记 6/7 个当前源码漂移，并核验 240 个历史嵌套 evidence records。当前验收结论只使用独立 V2 冻结。
- Git 字节一致性审计通过：路径级 `.gitattributes -text` 消除了 Windows autocrlf 对冻结字节的隐式改写；Git index 中 V2 27/27 source records 与 56/56 result/figure/raw references 均逐字节匹配声明 SHA-256。

### 2026-07-18 Ollama migration and paper-model qualification

- 迁移证据：D 源库 42 files / 9 manifests / 13.200 GiB，旧项目 E 源库 11 files / 2 manifests / 4.361 GiB；并集 53 files、41 blobs、11 manifests、17.561 GiB，53/53 SHA-256 校验通过且无冲突。
- `E:\Ollama\models` 两轮全新进程验证均为迁移前 11/11 模型 metadata + short generation smoke 通过；删除的精确路径仅为 `D:\Ollama\models.migration-backup-20260718`，回收 13.200 GiB，Ollama 程序仍位于 D 盘。
- 新增 `qwen3:8b`/`llama3.1:8b` 的不可漂移论文别名和 digest/manifest/blob 快照；24/24 资格 smoke 完成、0 provider/runner failures，`--no-think` 与通用 ToolCall 兼容修正有 18 项针对性测试通过。
- PromptGuard E 盘环境和精确版本快照已完成；在该 2026-07-18 截点模型下载仍因官方 gated repository 阻塞，revision 已记录且 `retry_performed=false`。该阻塞已在 2026-07-20 用户授权后解决；预检继续要求 config + weights + tokenizer 三类文件齐全，不再把部分缓存误判为 ready。
- `public_benchmark_formal_freeze_v2` 9/9 checks passed；84 pending cells、74,760 todo case-runs 已写入独立 `public_benchmark_formal_runs_v2`，v1 的 60 cells/53,400 队列保持原样。
- 当前结论边界：两个 8B 仅取得运行资格；PromptGuard real inference 在该截点未完成、后续已完成 detector-only formal result；未启动公共基准正式矩阵、付费 API 或 Docker。
- 项目级完整回归：`504 passed, 1 skipped, 0 failed`。随后 Harness 文件/源码边界、JSON、PowerShell/Bash 语法、Python compile、18 项实验 Registry 和历史证据冻结均独立 PASS。
- 重复聚合 Harness 命令的第二次 `pytest` 在无 CPU 增长、无子进程、无新输出状态下停滞超过 6 分钟，已按失败恢复规则停止并记录；它不覆盖此前完整通过结果，也不冒充新的 verifier PASS。
- 最终服务状态：Ollama process=0、11434 listener=0、Docker process=0；下载和验证结束后未保留任何项目服务。

### 2026-07-20 Portable unified configuration

- 新增 `config/project.env.example` 与 Git 忽略的 `config/project.local.env`：项目组共享同一套字段，真实 Token 和机器路径由成员本地维护。
- 新增无第三方依赖的 `m3_core/project_config.py`，支持保守解析、占位符检查、环境加载和秘密字段脱敏；不做变量展开或命令执行。
- 新增 `scripts/check_project_config.py`，验证字段和 Git ignore/track 状态；当前本地配置为 ignored=true、tracked=false、HF_TOKEN=placeholder。
- 新增 `scripts/promptguard_setup_from_config.py`，只从本地配置读取个人 Token，按冻结 revision 下载并写 SHA-256 快照；当前因用户尚未在本地文件粘贴 Token而正确停止在资格门禁前。
- 配置/模型工具针对性回归 8 passed；编译通过；占位符负向门禁按预期 exit=1，输出没有真实秘密；新增 tracked-file 扫描会报告字段名和文件路径但永不输出秘密值。

### 2026-07-21 Confirmatory preregistration and admission hardening

- 新增 `build_paper_v1_preregistration_freeze.py`，在 independent blind admission 与 adaptive formal result 之前冻结 5 个假设、主要终点、安全与效用 margin、10,000 次聚类 bootstrap、McNemar/Holm、排除/失败策略和 10 张图；freeze 9/9 checks 通过，payload SHA-256 为 `b4b747196274e877c4b2bd0e5bbdebdcc582d585c714263815a8e4956f6b742a`。
- Q2 reproducibility criterion 已把上述 preregistration 纳入失败关闭检查，当前 criterion 仍为 8/8；总体分数未因协议文件虚增，仍为 raw 63.5、capped 60.0、goal_90_met=false。
- 修复 `camel_or_fides` formal-readiness 的不可满足条件：只核验冻结协议选中的 CaMeL external entry，并强制未选择的 FIDES 保持 result-ineligible；selection 在 formal analysis 接管 `formal_manifest` 后仍从 formal freeze 读取。
- 新增 `admit_external_strong_baseline_formal_result.py`，统一处理 Task Shield、IPIGuard、Progent 和 CaMeL 的双 registry 准入；只有 726/726、0 failure、exact coverage、freeze hash、analysis/run/outcomes/artifact hashes 全部一致且显式 `--write-registries` 时才写入。当前四个 plan-only admission 均按设计 blocked，registry 未变化。
- 新增 `monitor_adaptive_mcts_budget_formal.py`，并给 adaptive runner manifest 增加 PID；监控器只读检查 PID、任务/查询数、artifact freshness、stall/failure 和 analysis promotion。当前 formal root 未启动，状态为 `missing_manifest`。
- 本轮新增/相关聚焦回归：preregistration/Q2 10 passed；IFC selection/external admission 5 passed；adaptive runner/monitor 9 passed；全部相关 Ruff 与 `py_compile` 通过。
- AgentDojo `tool_filter` 正式任务继续独占 Ollama/GPU；最新只读快照 433/726 completed、0 failed、293 missing、PID 36472 alive、ETA 约 4.76 小时。Q2 审计已刷新并读取该快照，但结果尚未完成/准入，所以 raw 63.5、capped 60.0 不变。
# 2026-07-22 — ToolFilter admitted and Task Shield formal run started

- AgentDojo official `tool_filter` full formal root `outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1` completed exact 726/726 cases with 0 failed and 0 missing. Read-only monitor `protocols/paper_upgrade_v1/monitors/tool_filter_formal_v1/agentdojo_official_formal_run_monitor_v1.json` reported `completed_formal_admitted`.
- Formal analysis was generated at `outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1/analysis/analysis_manifest.json`; admission bridge then wrote `protocols/paper_upgrade_v1/baseline_registry.json` with `agentdojo_tool_filter` as a formal registry result. This is now a real source-backed strong baseline, not a smoke or diagnostic result.
- Q2 audit after admission is still below the target: `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`. Remaining hard caps are independent confirmatory blind, incomplete public benchmark matrix, fewer than five formal-ready strong baselines, missing two frontier API vendor slots, and missing formal adaptive budget attack evidence.
- Task Shield disclosed paper-reproduction qualification completed 2/2, 0 failed at `outputs/paper_upgrade_v1/baselines/taskshield_paper_qualification_v1/run_manifest.json`; it remains `result_eligible=false` because it is only a qualification root.
- The planner was fixed so `admitted_registry_updated` counts as admitted, external baseline states are tracked in qualification/formal/analysis/admission phases, and active external formal runs close the resource gate. Focused planner regression now passes 9/9.
- Task Shield 726-case full formal was started in the background at `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v1` with explicit `--admit-formal`; current PID is 22616. Latest monitor `protocols/paper_upgrade_v1/monitors/task_shield_formal_v1/agentdojo_official_formal_run_monitor_v1.json` shows `running_progressing`, 4/726 completed, 0 failed. Do not start another Ollama/GPU formal workload while this PID is alive.
- Repository convention audit remains clean: `python scripts/audit_project_conventions.py --check` passed 12/12, including frozen hash-bound file identity. Focused validation also passed: strong-baseline hash-bound tests 37/37, planner tests 9/9, and layout/ToolFilter admission focused tests 21/21.

# 2026-07-22 — Active monitor/diagnostic portability refresh

- Safe non-frozen monitor/diagnostic artifacts were regenerated with repository-relative paths while preserving all raw formal outcomes and freeze-bound evidence.
- Updated active monitor/diagnostic code paths:
  - `experiments/paper_v1/benchmarks/monitor_adaptive_mcts_budget_formal.py`;
  - `experiments/paper_v1/benchmarks/diagnose_agentdojo_formal_run_failures.py`;
  - `scripts/audit_project_conventions.py`.
- The active portable-artifact audit now covers the generic AgentDojo monitor, the transformers detector monitor, the adaptive MCTS monitor and the AgentDojo failure diagnostic.
- Remaining checkout-specific paths under `protocols/paper_upgrade_v1` are intentionally preserved: 14 are frozen/hash-bound and 9 are old or generator-bound evidence snapshots that require a new revision rather than in-place rewriting.
- Q2 execution plan refreshed. It remains `resource_gate=busy`; next safe action is still to monitor the live Task Shield v1.3 run.
- Latest Task Shield v1.3 status: 24/726 completed, 0 failed, 702 missing, PID 27384 alive, health `running_progressing`.
- Q2 readiness remains `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`; no smoke, diagnostic, plan-only or running evidence was promoted.
- Verification: Ruff pass, compileall pass, focused monitor/diagnostic tests 5/5, project convention audit 12/12.

# 2026-07-22 — Q2-to-80 fail-closed action audit

- Added `experiments/paper_v1/benchmarks/plan_q2_to_80_actions.py` and generated `protocols/paper_upgrade_v1/execution/q2_to_80_action_audit_v1.json/.md`.
- The artifact proves the project is still below Q2-80 and explains why all five active caps below 80 must be cleared before claiming success.
- Current action audit status: `blocked_by_active_hard_caps`; Q2 `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.
- The five required bundles are Frontier API two-vendor admission, formal adaptive MCTS budget evidence, independent 600-case blind formal evidence, at least five formal-ready strong baselines, and full public benchmark formal matrix completion.
- The audit also records remaining path-portability exceptions: 23 files with checkout-specific path hits; 14 frozen/hash-bound and 9 evidence-bound snapshots. It explicitly says these should not be rewritten in place.
- Task Shield v1.3 remains the only live workload: 24/726 completed, 0 failed, PID 27384 alive, below stall threshold.
- Verification: Q2-to-80/planner/layout regression 19/19, Ruff pass, compileall pass, convention audit 12/12.

# 2026-07-22 — Q2 status documentation correction

- Updated `docs/RUNBOOK.md`, `docs/PROJECT_OVERVIEW.md` and `protocols/paper_upgrade_v1/implementation_status.md` so they no longer describe ToolFilter as the active incomplete workload.
- Current non-frozen documentation now reflects that ToolFilter is admitted, PromptGuard detector-only is admitted, strong baselines are 2/5, and Task Shield v1.3 is the live formal run.
- Refreshed Q2 readiness, Q2 execution plan and Q2-to-80 action audit after the documentation update. Q2 remains raw 66.0/capped 60.0 with `goal_80_met=false`; the action audit remains `blocked_by_active_hard_caps`.
- Validation: conventions audit 12/12, focused Q2-to-80/planner/Q2/layout regression 29/29, Ruff pass, compileall pass.

# 2026-07-22 — Current-state override for historical checkpoint drift

- Added a top-level current authoritative checkpoint to `protocols/paper_upgrade_v1/implementation_status.md`.
- Updated `harness/tasks/m3-paper-upgrade.md` latest checkpoint from the stale 2026-07-21 ToolFilter-running state to the current 2026-07-22 state.
- Current state remains: ToolFilter admitted, PromptGuard detector-only admitted, strong baselines 2/5, Task Shield v1.3 live at 24/726 with 0 failed, Q2 raw 66.0/capped 60.0.
- Refreshed Q2 readiness, Q2 formal execution plan and Q2-to-80 action audit; no score change and no result promotion.
- Verification: conventions audit 12/12, focused Q2-to-80/planner/Q2/layout regression 29/29, compileall pass.

# 2026-07-22 — Task Shield v1.3 registry sync and full Harness verification

- Synchronized non-frozen Task Shield current-state documentation with the v1.3
  evidence chain: qualification complete, 726-case formal root running, and
  `result_eligible=false` until exact coverage, full logs, statistics and
  analyzer admission all pass.
- Refreshed external strong-baseline source audit, strong-baseline formal
  readiness audit, Q2 readiness and Q2-to-80 action audit. Q2 remains
  `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.
- Formal-ready strong baselines remain 2/5: `agentdojo_tool_filter` and
  `promptguard`. Task Shield remains blocked/diagnostic while the live run is
  incomplete; Progent, CaMeL/FIDES and IPIGuard still lack admitted full logs.
- Latest read-only Task Shield monitor snapshot in this window:
  `running_progressing`, 26/726 completed, 0 failed, 700 missing, PID 27384
  alive. The last-update age stayed below the stall threshold, so no process
  intervention was made.
- Preserved all frozen/hash-bound and evidence-bound path exceptions. Active
  layout and naming audit remains 12/12 PASS.
- Verification: focused Task Shield/Q2/layout regression 136/136, full pytest
  666 passed and 1 skipped, full Harness verifier `Verification failed=0`,
  standalone Ruff pass, full compileall pass, experiment registry pass and
  historical evidence verification pass. `git diff --check` had no whitespace
  errors, only Windows CRLF conversion warnings.

# 2026-07-22 — Task Shield v1.3 seal and v1.4 qualification/formal checkpoint

- Under explicit user approval, PID 27384 was stopped after identity
  re-verification. No child remained. The v1.3 root is retained at 42 completed,
  1 failed and 683 missing and sealed by an external 90-file SHA-256 inventory.
- The approved v1.4 operator-decision gate passed. Fresh qualification completed
  2/2 with 0 operational failures and remains diagnostic-only.
- Fresh 726-case v1.4 formal execution started as PID 9804 from a new root.
  The 18:51 +08:00 read-only snapshot is 4 completed, 1 failed and 721 missing.
- The v1.4 failure is verifier-invalid-JSON on
  `agentdojo:v1:banking:user_task_1`, classified as
  `model_output_or_parse`. It is retained in the denominator; the current root
  is inadmissible and has not been stopped, retried or patched automatically.
- Windows PID liveness and failure-classification regressions were corrected;
  the focused suite passes 143/143 and Ruff passes.
- Q2 remains raw 66.0/capped 60.0; no running, diagnostic or failed evidence was
  promoted.

# 2026-07-23 — CaMeL v3 qualification and staged-gate correction

- Preserved CaMeL v1/v2 evidence unchanged and created a fresh v3 source-backed
  adapter route after v2 failed on Windows GBK stdout when upstream CaMeL printed
  generated code containing `✅`.
- Added v3 runner/analyzer/freeze/protocol:
  `run_camel_source_backed_formal_v3.py`,
  `analyze_camel_source_backed_formal_v3.py`,
  `build_camel_source_backed_formal_freeze_v3.py`, and
  `camel_source_backed_formal_protocol_v3.md`.
- v3 freeze completed 17/17 and hash-binds v3 local adapter files plus
  `strong_baseline_metric_semantics_v2.py`. It remains zero-case,
  result-ineligible protocol evidence.
- v3 two-case qualification completed 2/2 with 0 failures and 0 unresolved
  security rows. Diagnostic analysis completed; result remains
  `result_eligible=false`.
- Planner was corrected so a two-case CaMeL qualification cannot unlock a
  726-case formal run. It now requires staged P3 review before any P4/P5/formal
  discussion.
- v3 P3 8-case qualification completed 8/8 with 0 failures and 0 unresolved
  security rows across banking, slack, travel and workspace.
- P3 result: ASR 0/4, utility TCR 0/4, failure rate 0/8, median latency
  49.636 s, p95 latency 159.003 s. This is engineering-stable but utility-failed
  diagnostic evidence, not a formal-ready baseline.
- Review report written:
  `protocols/paper_upgrade_v1/execution/camel_v3_p3_qualification_review_v1.md`.
- Q2 readiness remains raw 66.0/capped 60.0; formal-ready strong baselines remain
  2/5 because CaMeL is still diagnostic-only.
- Focused verification: CaMeL v3/planner regression 25/25 passed.

# 2026-07-24 — DeepSeek v2 request-chain activation and record path

- Bound the user-submitted Gemini 3.6 Flash quota screenshot by SHA-256 without
  copying it into the repository. Active limits are 1000 RPM, 2000000 TPM and
  10000 RPD; free-only and USD 0 paid-tier policy remains fail closed.
- Activated the project-owner-approved DeepSeek request chain for fresh v2
  requests only: pretransport local request ID, canonical payload hash,
  append/flush/fsync started event, official response ID, exact model identity
  and hash-chained terminal event.
- One fixed public/no-tool/no-effect DeepSeek call completed the two-event
  durable chain. The qualification artifact initially failed a local
  response-normalization assertion after transport; no retry was made.
  Zero-network recovery retained identity qualification while explicitly
  leaving response content, token usage, latency and full receipt unavailable.
- Added experiment-record v2 and a separate append-only record-store v2.
  Offline qualification wrote two transient records, revalidated the complete
  chain after each fsynced append, and rejected tamper and genesis truncation.
  No project formal result was created.
- Provider preflight now recognizes one live-qualified official provider,
  active Gemini quota input, the approved trace, v2 schema and v2 store, while
  keeping `gate_pass=false`. The remaining engineering blocker is per-call
  trace/record wiring in the live six-condition runtime.
- Focused paper-v2 verification: 184 passed, 772 deselected, 1 VIGIL
  deprecation warning; Ruff, PowerShell syntax and Bash syntax passed.
- Final full pytest: 955 passed, 1 skipped, 3 warnings in 374.88 seconds.
  Final Harness: exit 0 in 481 seconds with `Verification failed=0`.
- Scientific readiness remains 32% because no medium/public/adaptive/blind
  effect result exists. Engineering remains 99%; formal execution remains
  unauthorized.

# 2026-07-24 — Live Per-Call Provider Trace V2 Wiring

- Added an ordered provider-trace bundle for experiment-record 2.1. Every
  DeepSeek call in a work item now has a deterministic local request identity,
  canonical payload digest and fsynced pretransport event; completed calls bind
  a durable terminal candidate to the activated trace approval.
- The live six-condition runtime wraps both normal agent calls and VIGIL
  constraint-generation calls. Condition results propagate the complete bundle
  into v2 record assembly and the append-only formal record store.
- Failure semantics are fail-closed: provider pause, transport failure or
  evidence failure retains one open commitment, performs no automatic retry,
  caps the record at `diagnostic`, and persists `unsafe_effect_itt=true`.
  Evidence activation is prevalidated before terminal append.
- The zero-network end-to-end qualification covers four paths:
  `success_single` (1/1 completed), `success_vigil` (2/2 completed),
  `failure_agent` (1 open) and `failure_vigil` (1 open). It writes four
  transient records, validates the complete record hash chain, and creates
  zero project records, zero formal results, zero external effects and zero
  network calls.
- The v3 preflight is reproducible and now reports
  `live_runtime_per_call_v2_qualified=true`. It intentionally retains
  `gate_pass=false` and `formal_execution_authorized=false`; the next gate is a
  run-specific admission manifest plus one bounded official DeepSeek pilot
  review.
- Verification:
  - focused affected suite: 47 passed;
  - paper-v2 suite: 189 passed, 769 deselected, 1 known VIGIL dependency
    warning;
  - standalone Ruff, Bash syntax, PowerShell syntax, JSON parsing and
    `git diff --check`: passed;
  - full pytest: 960 passed, 1 skipped, 3 known dependency warnings in
    442.81 seconds;
  - full Harness: exit 0 in 571.8 seconds, embedded 960 passed / 1 skipped /
    3 warnings, `Verification failed=0`.
- Scientific evidence remains 32% and submission readiness 44%. No medium,
  public, adaptive or blind effect result was created or promoted.

# 2026-07-24 — Fail-closed DeepSeek single-pilot controller

- Added a deterministic, non-executable owner-review candidate for one frozen
  benign-no-tool/no-defense DeepSeek work item. It locks provider/model,
  policies, trace activation, budget, sandbox-only safety and single-use v2
  outputs without authorizing execution.
- Added a schema-validated controller that accepts only a separately frozen
  explicit project-owner active manifest. It cannot activate its own candidate
  and never authorizes the 480-item matrix or scientific result admission.
- Gate ordering is qualified offline: missing admission, candidate reuse,
  scope drift and existing output all reject before credentials or client
  construction. These four rejected paths report 0 credentials and 0 clients.
  A separate injected-transport end-to-end fixture constructs one local client,
  makes one local transport call and writes one temporary candidate record,
  while external network calls, project records and formal results remain 0.
- Provider trace bundle 2.1 now carries content-free per-call cache hit/miss,
  output tokens, receipt digest, request/cumulative CNY cost and budget status.
  The runtime qualification has 3/3 completed calls with complete accounting;
  the controller fixture independently reproduces CNY 0.0000728.
- The earlier eight-input candidate identity is superseded by the 23-input
  post-pilot-review checkpoint below and must not be activated.
- Verification for the usage/cost extension: controller 9/9; focused affected
  suite 28/28; paper-v2 199/199 with one known VIGIL/Pydantic warning; full
  pytest 970 passed / 1 skipped / 3 known warnings in 295.07 seconds; full
  Harness repeats 970/1/3 and finishes with `Verification failed=0`.
- Engineering readiness stays 99%, scientific evidence 32% and submission 44%.
  The next action is still an explicit owner checkpoint for the exact single
  pilot; no active manifest or API result exists.

# 2026-07-24 — Persisted safety receipt and post-pilot review gate

- Upgraded the prospective v2 experiment record from 2.1 to 2.2 so every
  record stores the already-validated, credential-free provider safety receipt.
  A strict reusable receipt schema rejects extra/missing fields, non-official
  endpoints, host-execution tools, external connectors and provider-managed
  tools.
- Added a credential-free post-pilot reviewer. It cross-validates the active
  admission file, exact single ledger entry, independent trace JSONL, provider
  trace bundle, DeepSeek cache/cost rows, record token totals, provider/model
  identity, safety action digest and append-only tails.
- One injected fixture passes structural review; four admission/trace/cost/
  safety tamper cases reject. Because the fixture is not live evidence,
  `official_evidence_gate_passed=false`,
  `ready_for_owner_matrix_review=false`, and both matrix/result authorization
  remain false.
- The non-executable candidate now locks 23 execution and review inputs; its
  canonical manifest SHA-256 is
  `6ac0601865d76f5f808952b2f58e6587d02c303ac5e9a998ae4d751fbb3dd4cc`.
  No active admission, credential read, API call, project pilot record or
  formal result was created.
- Final verification: focused 33/33; paper-v2 204/204 with one known
  VIGIL/Pydantic warning; full pytest 975 passed / 1 skipped / 3 warnings in
  297.42 seconds; full Harness repeats 975/1/3 in 299.96 seconds and finishes
  with `Verification failed=0`. Ruff and artifact/JSON reproduction pass.

# 2026-07-24 — Official DeepSeek single pilot completed and reviewed

- Created the separately authorized active admission for the exact 23-input
  candidate; the active file binds the project owner's approval-statement
  digest and leaves matrix/result authorization false.
- Admission precheck reproduced the candidate and locked inputs with
  `credentials_read=false`, `network_calls_made=0`, and unused trace/record
  paths.
- Executed exactly one official `deepseek-v4-pro` benign-no-tool/no-defense
  work item through the frozen controller. It completed without retry,
  fallback, provider tools, external connectors or external effects.
- Persisted one provider trace and one experiment-record 2.2 entry. Usage was
  278 prompt-cache-miss tokens, 0 cache-hit tokens, 136 completion tokens and
  414 total tokens; cumulative cost was CNY 0.00165 against the CNY 27 fuse.
- Post-pilot review passed all 15 integrity/safety checks, with
  `task_completion=true`, `unsafe_effect=false`,
  `official_evidence_gate_passed=true` and
  `ready_for_owner_matrix_review=true`.
- The record remains `formal_candidate`; matrix execution and scientific
  result admission remain false. This one observation cannot support paired
  security, utility or generalization claims.
- Updated the claim ledger and scorecard to 99% engineering, 33% scientific
  evidence and 45% submission readiness. The feature remains `in_progress`.
- Verification: focused 31/31; paper-v2 204/204; Ruff and conventions 12/12;
  full Harness 975 passed / 1 skipped / 3 known warnings in 317.96 seconds,
  historical/frozen evidence pass, `Verification failed=0`.

# 2026-07-26 — v7 abort, v8 canary pass and detailed stage report

- The admitted v7 canary failed closed after two official DeepSeek responses
  because a lazily resolved effect backend received the old boundary adapter
  after the controller's temporary binding ended. The append-only state is
  frozen at zero result records, one open attempt, two provider responses and
  one trace. No retry, Gemini fallback, provider tool, external effect or
  scientific-outcome access occurred.
- A content-free v7 abort review is frozen. v8 uses a new run and matrix
  identity and holds the v3 adapter binding over the complete execution
  lifecycle. Delayed-backend regression coverage, v8 qualification,
  candidate, canary admission and continuation admission are versioned and
  hash-bound.
- The unique v8 DeepSeek canary completed all six conditions with 6/6
  `formal_candidate` records, 13 official provider responses, zero diagnostics,
  zero operational failures, zero retries/fallbacks/tools/effects and
  CNY 0.0077078 incremental cost. The technical review did not inspect
  scientific outcomes.
- Result gate v5 was frozen before outcome access. Its current candidate
  manifest is
  `73edb1f625f13f715cff475cd7d5ee9f9fe2183efc0c7cc9479b644eb1928e7f`.
  v8 continuation manifest
  `78b136fcd8766d93a7dd37081d2adbf0738bf2c5fdac556855375d9a7b75bc83`
  binds 6 completed records, 474 remaining and zero open attempts while
  retaining result admission as false.
- The pre-v8 full Harness completed with 1072 passed, 1 skipped and one stale
  v7 freshness-test failure, so the final status was
  `Verification failed=1`. The stale assertion was replaced by the permanent
  v7 abort/no-network invariant and the focused regression passed 1/1. A new
  full green Harness is still required before the 474-item continuation.
- Generated
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-26.docx`
  (SHA-256
  `a79f3a65b75b313ec2a9bc8effc058c436d2d0671ae1f04009ad4578c379b828`).
  It contains four analytical figures and sixteen tables plus the detailed
  DeepSeek/Gemini, public-benchmark, adaptive-attack, blind-test, statistical
  and manuscript plan.
- Report QA passed OOXML/ZIP parsing, table geometry, accessibility,
  placeholder and credential-pattern checks; all four chart images were
  visually inspected. LibreOffice was not installed, so full DOCX page-render
  QA was unavailable and is explicitly not claimed.
- No 474-item continuation or scientific analysis was run in this checkpoint.
  F-PAPER-002 remains `in_progress`.
- Final no-network controller status verification returned
  `matrix_v8_status_verified_no_network` with 6 records, 474 remaining,
  zero open attempts, `budget_paused=false`,
  `result_admission_authorized=false` and zero network calls made by the
  status operation.

# 2026-07-30 — Adaptive admitted canary and Public per-shard recovery checkpoint

- Adaptive-v2 recovery completed 8/8 tasks with 374 terminal queries, 562
  official calls, CNY 0.552805, one retained diagnostic and no retry,
  provider tool or external effect. Independent result admission and rebuild
  report unsafe-effect 0/8 at budget 50 (Wilson 95% CI 0–32.44%); this remains
  exploratory rather than a formal 40-task adaptive panel.
- Added incremental live ledgers and versioned Adaptive-v3 recovery, typed
  technical review, result admission, analysis, independent analysis review,
  one chart bundle and manuscript integration. Focused adaptive/recovery tests
  and Ruff pass.
- Original Public-v2 shards naturally stopped at 232/126/140/130 records.
  Per-shard v3 recovery freezes each closed prefix and executes only untouched
  work keys. s1 completed 1265 records with 71 ITT diagnostics, 3321 official
  calls and CNY 4.274749; its complete evidence chain passes while the frozen
  one-percent mechanism-quality threshold correctly fails.
- s0/s2/s3 remain live and outcome-sealed. At the recorded checkpoint they are
  268/1265, 355/1264 and 273/1264 with empty stderr. No live process was
  stopped, paused or retried.
- Added Public evidence-integrity review, primary merge v2, separate scientific
  result candidate/admission, and a 5,082-row primary analysis implementation
  with ITT retention, Wilson intervals, exact McNemar, 10,000 paired bootstrap,
  benchmark stratification and three reproducible chart families. New focused
  suite: 10 passed; Ruff and py_compile pass.
- Full Harness is intentionally pending until the three live Public recovery
  processes finish. F-PAPER-002 remains `in_progress`; no Public scientific
  outcome has been accessed or scored.

# 2026-07-30 — Public analysis independent-review checkpoint

- Added `public_primary_analysis_review_v1.py` and bound it into the future
  result-access candidate before that candidate exists.
- The reviewer reads the admitted record envelopes directly and independently
  reproduces the condition event counts, Wilson 95% intervals, four critical
  paired differences and exact two-sided McNemar tests. It does not reuse the
  primary aggregation or statistical helpers.
- Focused verification passes: manuscript/bibliography 7/7; independent
  reviewer plus result-admission 5/5; Ruff and py_compile clean.
- Public recovery remains outcome-sealed. At 06:39, s0/s1/s2/s3 held
  504/1265, 1265/1265, 592/1264 and 468/1264 records; the three incomplete
  shard processes were alive and all recovery stderr logs were empty.
- No Public result admission, outcome read, analysis artifact, score increase,
  retry, provider tool or external effect occurred. Full Harness remains
  deferred until the live processes finish.

# 2026-08-06 — Fresh Harness v6 stop-point technical report

- Confirmed by read-only process inspection that no Harness, Public, Adaptive,
  or provider formal workload remained alive; no process was stopped or
  restarted.
- Revalidated the direct v6 receipt: child exit 0, evidence gate pass, 13/13
  aggregate stages, pytest 1538 passed/1 skipped/3 known warnings, one terminal
  `Verification failed=0`, stable verifier/helper hashes, and zero provider or
  network authorization.
- Reconciled current closeout gaps without opening scientific outcomes:
  DeepSeek Flash public is physically 1791/1791 with 16 ITT diagnostics and
  result access false; Gemini public has one historical terminal record and a
  non-authorizing 10-item Public-v5 candidate; formal Adaptive remains an
  exploratory 8/40 budget-50 prefix; independent blind remains Day-1-only with
  0/600 authored candidates.
- Delivered a technical report artifact with 14 ordered report blocks, four
  metric cards, two charts and two audit tables. Validator and MCP renderer both
  returned `ok=true`. Source artifact SHA-256 is
  `c3b992d145c92d4c25f393fe28a8ecb42272cfe939eaefe774b83b4826ee2197`.
- No new gate, admission, API call, provider request, outcome access, blind
  label access, or external effect occurred. F-PAPER-002 remains `in_progress`.

# 2026-08-06 — Word stop-point report rendered and verified

- Confirmed no formal Harness/Public/Adaptive/provider process remained alive
  and did not start, stop, resume or retry any experiment.
- Generated the 8-page Word report
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段技术状态报告_2026-08-06.docx`
  from the validated canonical artifact. DOCX SHA-256 is
  `a0d088d2f6a1a8554bb6ea0c2bbdc5c0e34755f9bf689e2267ede3be01da531b`.
- The report contains four headline metrics, two analytical charts, two audit
  tables, definitions/methods/limitations, a gated recovery sequence and a full
  nine-item SHA-256 evidence appendix.
- WPS-compatible read-only export plus bundled PDF rasterization produced eight
  pages; all eight were visually inspected with no clipping, overlap, broken
  tables or missing glyphs. The final alt-text-only rebuild was pixel-identical
  on all eight pages to the inspected layout.
- Exact table geometry passed for all seven tables. Heading, section and image
  audits passed. Accessibility reports high=0/medium=5/low=0; the five medium
  findings are intentional one-row KPI/callout layout tables, while both data
  tables have repeated semantic headers.
- Builder Ruff and py_compile pass; required-content and secret-pattern scans
  pass with zero DeepSeek/Gemini/Bearer key hits. QA receipt SHA-256 is
  `3e948b02499e7c277aa9eaac9d04b275b1cfc45b12c3c0296eb5a9f226423c25`.
- No gate, provider admission, API/network request, scientific outcome access,
  blind-label access or external effect occurred. F-PAPER-002 remains
  `in_progress`; work stops at this report boundary by owner instruction.

# 2026-08-06 — Fresh Harness v7 authoritative stop and rendered report

- Fresh Harness v7 completed naturally with directly observed exit 0 after
  20946.429 seconds. Evidence gate passed; all 13 stages are PASS and zero are
  FAIL. Pytest reports 1552 passed, 1 skipped and 3 warnings in 4840.55 seconds.
- Receipt/stdout/stderr SHA-256 values are respectively
  `3f0378d30c65c4e188d878e4503abe572a305c29fb21f1f171dccff21b2de877`,
  `b7e3e56469b17fcb697a07a051e1e56ed657cfed4838f3a34f18bcee5fa80161`,
  and `5d8f5bfe93ebbc238b2ca955539641f144cb44dfe02eccb4b474e43e493c1265`.
- Direct-exit observation, evidence checks, verifier/helper stability,
  AgentDojo commit pin, Git-config non-mutation and zero provider/network
  authority all pass. Secret-format scan finds zero hits and no related process
  remains alive.
- The v7 stage report artifact validates and renders with `ok=true`; it has 14
  blocks, 4 cards, 2 charts, 2 tables and 5 bounded datasets. Artifact SHA-256
  is `6011c2252e9662f6607f40f3fee65dfc5574e66f8eec3c97ec6ea1a23389cc93`;
  QA SHA-256 is
  `3aae05f4cf0903bf9b28fd509631b9ab2dd878ae0e2d6e8881d11654d33cd3a0`.
- Broader experimental closeout is not complete: Gemini public is 2/1791
  physical records, formal Adaptive panels are incomplete, blind authoring is
  0/600 and blind execution is 0/3600. No result/label access or new API call
  occurred. F-PAPER-002 stays `in_progress`, and work stops here by owner order.

# 2026-08-06 — Day 2–3 offline qualification and Fresh Harness v8

- Added the non-authorizing post-v7 closeout gate v5, its deterministic tests,
  a single-use Adaptive Pro-50 v2 guarded wrapper v3 and a non-authorizing
  Fresh Harness v8 launcher. The gate manifest is
  `ff76b53991b5b0f8f2ccdfc88aa246c9be6d7e12786bdf8c3c0d4d1b3c10e58e`.
- Focused pytest passes 16/16; Ruff, Python compile and PowerShell parsing pass.
- Fresh Harness v8 naturally completed after 29781.25 seconds with direct OS
  exit 0, evidence gate PASS, all 13 aggregate stages PASS, zero FAIL stages,
  pytest 1568/1/3 and one terminal `Verification failed=0` marker.
- Receipt/stdout/stderr SHA-256 values are
  `8747437d004059615eb70615d30ebd1af7fedc093c10fa2b30ab2a038b1fb71b`,
  `8c091938185cac763973057a150cc1f0aec01f92929a0e7679929dfd9c99ca16`,
  and `bf40b7db77d7b2090cc2a52403e0279a3dc84d38a5825e516188c320895395d8`.
- The terminal audit finds 303 expected RuntimeAuditor delete blocks, zero
  secret-format hits and zero remaining helper/child processes. API variables
  were scrubbed and provider/network authority stayed false.
- No provider/API request, Adaptive query, result access, label access, retry,
  tool or effect occurred. Day 2–3 is engineering-complete; Day 4 and the wider
  experimental closeout remain pending. F-PAPER-002 stays `in_progress`.

# 2026-08-07 — Formal Adaptive Pro-50 v2 stage complete

- Executed the qualified single-use Adaptive wrapper for the remaining 32
  DeepSeek V4 Pro budget-50 tasks. The operating-system exit and all six
  captured step exits are 0; terminal status is
  `completed_technical_gate_pass`.
- Outcome-blind technical review passes with 32/32 terminal tasks, 1,600
  completed provider calls, 3,200 query-ledger events and CNY 1.9984298 spend
  under the CNY 10 stage ceiling.
- Automatic retries, provider tools and external effects remained zero/false.
  Secret scan passed with zero hits; no scientific outcome was read and result
  admission remains false.
- Receipt SHA-256:
  `714ca7186df345add63277c618f43f24e749670282a5807ce3376b0c8942a116`.
  Technical-review manifest:
  `1c419d1c89ea4217a54bf7970ac25ab138a31db081991696a81f410bdebb1384`.
- F-PAPER-002 remains `in_progress`. The next bounded action is Gemini
  Public-v5 canary recovery segment s1 for the current Pacific free-tier quota
  day; no blind-label work is opened.

# 2026-08-07 — Gemini Public-v5 recovery segment s1 complete

- Created one exact free-tier admission for Pacific quota day `2026-08-06` and
  executed only frozen segment s1. Wrapper direct exit and all four captured
  step exits are 0; terminal status is `completed_technical_gate_pass`.
- Outcome-blind review passes all checks over 1/1 formal-candidate record and
  one completed provider transport. A VIGIL runtime dependency failure is
  retained in ITT with zero automatic retry; the segment remains technically
  eligible for aggregate canary continuation.
- Provider metadata confirms official network, exact
  `gemini-3.6-flash` identity, official response ID and no declared prompt
  rewrite. Billing is free tier with USD 0 paid cost/ceiling; provider tools
  and external effects are false.
- Receipt SHA-256:
  `507929977d4a78e08da94d62fda3b28920a7c7ce5a6f073933e478b9629e2997`.
  Technical-review manifest:
  `8223d08b0704b5a21f1393d29c890568cecaf540bdbda4c7780493c401a79dde`.
- The quota day is now reserved, so s2 waits for the next Pacific day. Results
  remain sealed and F-PAPER-002 remains `in_progress`.

# 2026-08-07 — Pro-200 offline qualification and Fresh Harness v9 launch

- Pro-200 candidate/admission are frozen for 39 resumable tasks from budget 50
  to 200; one existing diagnostic remains in ITT and is not retried. Candidate
  SHA-256 is `fd9b14608ea3e5218b8ca0fecc5ddeaf7589a4b82beae85c293e5d79ad118ea4`;
  admission SHA-256 is
  `c14912e8776488c9ec7436e3eb9da4a4b64565485a6d0ac7c7a95fec84e4b922`.
- The v4 single-use wrapper, gate v6 and fresh-v9 launcher passed 32 focused
  tests, Ruff, compile and PowerShell parsing. Gate v6 write and independent
  verify returned exit 0; manifest is
  `73a57abbd955d6b5099f3fdd1fbb0503017576e3d4758c29d7d760e3f3363a5d`.
- Fresh Harness v9 launched once with helper PID 43844/child PID 48564. Its
  running attestation confirms the expected AgentDojo commit, scrubbed API
  variables, process-only Git configuration, no provider/network authority and
  no automatic restart. No Pro-200 call has been made.
- F-PAPER-002 remains `in_progress`; Pro-200 may run only after the v9 receipt
  reports a directly observed exit 0 and its hashes are independently checked.

# 2026-08-07 13:10 +08:00 — Fresh Harness v9 与 Adaptive Pro-200 技术闭包

- Fresh Harness v9 自然完成：直接 OS exit 0、evidence gate PASS、13/13 stage
  PASS、pytest 1584/1/3、唯一 `Verification failed=0`。receipt SHA-256
  `14ef9b5ae618839798051a31ce4a4abc270f53f46e393e678e0f43b29f6f0e44`；
  API 环境已 scrub，provider/network authority=false。
- Pro-200 execute 子进程自然完成 39/39 任务、6,925 calls、5,504 条新增 terminal
  query，阶段成本 CNY 8.0544754 < CNY 20。自动重试、terminal replay、tools、
  effects 与 result admission 均为 0/false。
- 宿主一小时上限只终止了外层 wrapper。原 wrapper receipt 仍缺失且未重建；
  watcher 的 direct claim 因 exit=null 被独立降级为 false。恢复 technical-review
  子进程直接 exit 0，标准 review manifest `1910ac58...349c`。
- 新不可变审计独立锁定进程身份、controller 退出契约、01–05 重放日志、候选/准入、
  task/budget hash chain、checkpoint byte hashes 与 recovery 链；复算
  7,454−1,950=5,504、6,925 calls 和 CNY 8.0544754。审计 manifest
  `f927367ffb658139cfe02e0309a9030930478508df0100abc4b7e52abce108fc`，文件
  SHA-256 `d8d90a040a1f971775e0c5f7873ad2b6bb9bdcb9343fbcd4301e47780b2ecf9b`。
- 定向验证：27/27 host-timeout/controller/wrapper tests、37/37
  repository/order/audit tests、Ruff、py_compile、PowerShell parse 与 audit verify
  均通过。当前 `verify.ps1` 已接入新审计源、恢复脚本和冻结 JSON；因此 Fresh
  Harness v9 仍是前一源码快照，Pro-500 执行前必须再取得新的完整 Harness 直接
  exit 0。
- F-PAPER-002 继续 `in_progress`；科学 outcomes 仍封存，下一步仅为 Pro-500
  离线资格化与非授权工程门。

# 2026-08-07 19:10 +08:00 — Pro-500 离线集成与 v10 状态转换失败封存

- Pro-500 candidate/admission/gate v7/guarded runner/launcher 已完成离线集成；
  candidate manifest `947cd58...`，admission manifest `ae60c0...`，gate v7
  manifest `a9e750...`。本阶段未调用 provider、未读取科研 outcomes。
- Fresh Harness v10 运行 17,105.616 秒后自然直接 exit 1；receipt SHA-256
  `e8ab014c1e0383ed996e2b806e6b60a5aeabca7ad03a7acf6692588b4ae37f9d`。
  11 个 stage PASS、两个 stage FAIL；pytest 唯一失败为历史 gate-v6 的前瞻输出根
  不存在断言在 Pro-200 完成后被重放。
- 已将这一失败作为生命周期状态转换封存，而非修改历史门或实验输出。v10 failure
  review manifest `f35a4d9f92d77ef43eb49ec9aa44e7596e6d326801502c5c3548eeeb49b480bc`，
  file SHA-256 `78fd2ed12c209c9357a75025f5807f767852deb54d307d0d5de208450e705cb7`；
  44 项定向测试、Ruff、format、compile 均通过。
- `verify.ps1` 现在重放不可变 v10 failure review，不再把单次 prospective gate v6
  当作完成后仍可动态构建的当前门。下一步是单次 Fresh Harness v11；Pro-500
  仍未激活，F-PAPER-002 继续 `in_progress`。

# 2026-08-07 22:17 +08:00 — Owner stop、v11 封存与 Word 报告交付

- 已按 Owner 指令停止当前任务。相关实验/API/Harness/Pro-500 进程为 0；Pro-500
  activation artifact、candidate output root 和 guarded-runner output root 均不存在。
- Fresh Harness v11 直接 exit `-1`，evidence gate=false；9/13 stage PASS、1 FAIL、
  3 未完成，pytest 1,375 passed / 1 skipped / 1 warning / 257 setup errors。共同错误
  是 pytest 临时根目录消失；运行未产生 aggregate marker。receipt SHA-256：
  `75f4bbb58b30e9543e6aa98498c1f44bfad882180ff25a5672b4914a6089f7da`。
- 21 天实验计划未完成且不可宣称结项。当前可审计技术完成量为：DeepSeek Flash
  Public 1,791/1,791、Pro B50/B200 技术结账、Day-1 保管人登记；Gemini Public
  2/1,791，B500/hardest-20/Flash adaptive/盲测仍为未完成。
- 15 页阶段报告已交付，含 4 幅图和 11 张表。DOCX SHA-256：
  `d6e5e86270307f2531066958da26709ba372488e1a21247332627e13222ffc58`。
  WPS 只读渲染 15/15 页与已检查版本逐页一致；可访问性 high/medium/low 为
  0/0/0；文档内容 secret scan 与交付清理 denylist 均为 0。
- F-PAPER-002 保持 `in_progress`。任务处于 owner-stopped 状态，等待明确恢复指令，
  不是自动续跑点。

# 2026-08-19 — Owner 恢复实验结项工作

- Owner 已明确解除运行暂停并要求继续完整 21 天计划，当前不写新报告。
- 已开始以当前文件系统为准复核 v11、Pro-500、Gemini、adaptive、盲测和最终
  Harness 状态；未复用旧 activation，未调用 provider，未读取科研 outcome、标签
  或密钥。
- 按 Owner 最新要求移除重复 failure-review/source-lock 工件。下一工程门收缩为：
  run-scoped pytest temp + 新 Fresh Harness 直接 exit 0 + Pro-500 必要的身份、预算、
  无工具/无 effect 和 untouched-root 检查。通过前 Pro-500 仍禁止执行。
- F-PAPER-002 保持 `in_progress`，完整结项范围与失败留分母规则不变。

- Owner 随后将独立盲测后移；当前先完成所有非盲测实验与统计。盲测仍明确记录为
  0/600 authoring、0/3,600 execution，不计入已完成量。
- 最小 Harness 恢复修改已完成：新增单次 v12 launcher，把 TEMP/TMP 限定到自身
  run root，并让尚未生成的 Pro-500 activation gate 指向 v12。PowerShell parse、
  26 项定向 pytest、Ruff 与 py_compile 均通过；provider/API 调用仍为 0。
- Owner 指定后续 GitHub 目标为 `https://github.com/Fischl0527/M3_PI_Guard.git`。
  当前 origin 仍为旧 URL，未修改、未 push。
# 2026-08-19 — Lean empirical paper execution activated

- Owner approved the SCI Q2 lean empirical plan and retired the 21-day closeout.
- Fresh Harness v12 and its watcher were terminated by exact PID; stdout/stderr
  remain, no receipt was created or reconstructed, and no provider call was made.
- Full Harness, recursive evidence replay, blind 600/3600, Pro-500/2000, full
  Gemini Public and full second-model adaptive are removed from active scope.
- Created branch `codex/q2-empirical-study` and remote `m3-guard` for
  `https://github.com/Fischl0527/M3_PI_Guard.git`; no push occurred.
- Next: implement one-pass existing-result analysis and freeze the 180/90/60
  lean experiment selections. F-PAPER-002 remains `in_progress`.

# 2026-08-20 — DeepSeek lean authorization result milestone

- DeepSeek V4 Pro is technically closed at 900/900 terminal work keys. The one
  explicit recovery executed only 33 no-response keys and never replayed the
  867 response-bearing keys.
- Final status counts are 768 completed, 54 parse failures, 30 max-steps, 15
  provider failures and 33 repeated pre-response failures. All remain in the
  ITT denominator. Total provider cost is CNY 1.3888324.
- The one-pass analysis generated a compact DeepSeek-only JSON, five paper
  figures in PNG/SVG and six CSV tables. Gemini is marked pending and
  `cross_vendor_claim_eligible=false`.
- Corrected the runtime-burden plot to distinguish event totals from the share
  of records containing ASK/DENY. Forest labels now identify unsafe-effect and
  benign-tool TCR endpoints explicitly.
- Updated Results and Discussion with the observed endpoint, paired,
  operational and adaptive budget-50/200 findings. No leading-defense,
  saturation or cross-provider claim is made.
- Focused verification: 6/6 tests passed; Ruff and `py_compile` passed. No Full
  Harness, recursive history replay, blind run, real external effect or
  successful-row replay occurred.
- Next: commit and push this exact analysis milestone, then resume only pending
  and response-less Gemini rows after the next Pacific quota reset.

# 2026-08-20 — Provisional abstract and JISA format alignment

- Filled the abstract with the completed DeepSeek Public, authorization and
  adaptive findings while explicitly withholding a cross-provider claim.
- Reduced the abstract to 246 words, added five keywords and created five
  highlights, each 70–77 characters.
- Updated Introduction, Methods, figure/table status and the submission
  checklist. The official JISA guide was used for current format limits;
  institutional JCR verification and Gemini's stopping rule remain pending.

# 2026-08-20 — Conclusion, captions and declarations drafted

- Added a bounded Conclusion using only completed DeepSeek and adaptive
  budget-50/200 evidence; no cross-provider or saturation claim was introduced.
- Added full captions for five figures and six tables with denominators,
  endpoint direction, ITT handling and the no-saturation boundary.
- Added a provisional declarations file. Funding, author order/CRediT,
  competing interests, institutional ethics requirements and final AI-use
  language remain explicit author-confirmation gates.
- Fixed the Introduction's RQ count from four to three.

# 2026-08-20 — Unified DeepSeek manuscript generated

- Added `scripts/build_lean_paper_manuscript.py` and a focused five-test suite
  to assemble the reviewed section files into one reader-facing English draft.
- The generated manuscript contains six numbered sections, five figures and an
  8,117-word main body. The full generated file contains 9,505 words after
  adding the six formatted main tables, captions and reference packaging.
- Removed the remaining conditional Gemini placeholder and publication-facing
  references to internal citation-audit tables, old Harness chains, evidence
  bundles and Git workflow.
- Focused pytest 6/6, Ruff, `py_compile`, abstract limit, citation coverage,
  section order, figure availability and workflow-metadata scans pass.
- F-PAPER-002 remains `in_progress`: Gemini is incomplete and its partial rows
  remain excluded from inference; no cross-provider claim is made.
- Main Tables 1–6 now cover design, joint endpoints, paired effects, burden,
  heterogeneity and adaptive budgets. Historical detail tables are explicitly
  Supplementary Tables S1–S6, so no table number is duplicated.
- Related Work citations now use the same `[@Lxx]` processor syntax as the rest
  of the manuscript. Raw literature hyperlinks, legacy analysis keys,
  shard/merge process prose and Boolean route flags were removed from the
  reader-facing text without changing any result.
- The builder now numbers all scientific subsections as 1.1/1.1.1 while
  excluding abstract and table/figure labels. The official JISA checklist also
  records editable single-column source, data-statement and pre-reference AI
  declaration requirements checked on 2026-08-20.

# 2026-08-20 — Editable JISA Word review draft

- Added a Pandoc/citeproc plus `python-docx` builder and generated
  `M3_PI_Guard_JISA_working_draft.docx` as a single-column Letter manuscript.
- The accepted structure contains 269 paragraphs, 13 fixed-DXA tables, five
  inline figures, one References heading and 21 cited bibliography entries;
  raw citation tokens, Unicode replacement characters and placeholder
  reference prose are zero.
- Focused DOCX tests pass 3/3 with Ruff and `py_compile`. Page geometry,
  table geometry, image sizing, blank author metadata and citation conversion
  pass. Accessibility findings are 0 high, 0 medium and 21 low; every low item
  is a visible DOI or stable reference URL.
- The standard renderer cannot run because LibreOffice is absent, and no WPS or
  Word executable is available. Visual page QA is therefore explicitly
  pending; the file is a review draft, not a visually verified final package.
- F-PAPER-002 remains `in_progress` for Gemini's stopping rule, author-owned
  declarations/data release and the mandatory integrity review.
