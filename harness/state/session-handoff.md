# 会话移交

## 2026-08-20 — Submission-language and scheduled-Gemini checkpoint

- The current working Markdown and DOCX were rebuilt after a focused prose
  cleanup. Verification passes 9/9 plus Ruff and `py_compile`; LibreOffice is
  absent, so visual page QA remains open.
- A hidden PowerShell process with PID 7676 is waiting until
  `2026-08-20 15:02:00 +08:00`, then runs exactly one Gemini
  `remaining --retry-failed` command using the ignored local config. Do not
  start a second runner or interrupt it before natural completion.
- The run skips all five response-bearing work keys, may select only 109
  response-less recovery-eligible and 335 untouched items, stops at the first
  429, uses the official free tier with USD 0, and keeps tools/effects disabled.
- After the process exits, inspect aggregate counts only. If complete, run the
  compact analysis/tables/figures once and update the manuscript. If 429 recurs,
  retain the new row and wait for the next quota day; do not retry the same day.

## 2026-08-20 — Lean claim-ledger checkpoint

- Use `docs/research/paper_v2/manuscript/claim_evidence_ledger_lean_v1.json`
  for the current manuscript. It contains 13 claims and 26 existing evidence
  paths; Gemini cross-provider and institutional JCR statements remain locked.
- Keep `claim_evidence_ledger_v1.json` as historical context only. Do not
  restore its superseded blind, B500/B2000 or Full-Harness completion gates.

## 2026-08-20 — JISA author-input checkpoint

- Complete `docs/research/paper_v2/manuscript/author_metadata_and_submission_inputs.md`
  only with author-supplied facts before producing the final title page.
- `glossary_v1.md` contains the separate terminology list requested by the
  current JISA guide. Biographies (maximum 100 words each) and separate author
  photographs remain author-side submission inputs.
- The scheduled Gemini process remains the next data-bearing operation; these
  package files make no scientific or cross-provider claim.

## 2026-08-20 — Active-citation checkpoint

- The current 21-key citation set is reviewed in
  `docs/research/paper_v2/manuscript/citation_compliance_active_v1.md`.
- `references_v1.bib` now uses NeurIPS 2025 plus DOI for DRIFT and the official
  ICSE 2026 programme URL for AgentSpec; the invalid AgentSpec DOI is absent.
- Markdown/DOCX rebuild and focused verification pass 9/9 plus Ruff and
  `py_compile`; Related Work and the JISA checklist mark the active citation
  gate complete. The next data-bearing action remains Gemini pending/no-response
  recovery after the next Pacific quota reset, with first-429 stop semantics.

## 2026-08-20 — JISA cover-letter checkpoint

- Provisional cover letter:
  `docs/research/paper_v2/manuscript/cover_letter_draft.md`.
- Its 293-word body uses only completed DeepSeek and Adaptive 50/200 evidence,
  contains no funding/declaration/reviewer-suggestion text, and makes no
  cross-provider or SOTA claim.
- Before submission, add corresponding-author details and update the letter
  only if Gemini's stopping rule supplies a defensible result. The next
  data-bearing action remains the pending/no-response-only Gemini run after
  Pacific midnight.

## 2026-08-20 — Submission-statements checkpoint

- The working Markdown and DOCX now include a `Submission statements` block
  before References. Source: `docs/research/paper_v2/manuscript/submission_statements_draft.md`.
- Rebuilds and focused verification pass: manuscript/DOCX pytest 9/9, Ruff,
  `py_compile`, DOCX generation and accessibility audit. The DOCX now has 282
  paragraphs, 13 tables, five figures and 21 rendered references.
- LibreOffice remains unavailable, so visual page rendering is still pending;
  do not call the Word file visually verified or submission-ready.
- Gemini remains the next data-bearing step. At this checkpoint the plan has
  5 response-bearing keys, 109 response-less recovery-eligible keys and 335
  untouched remaining-stage keys. After the next Pacific midnight, run only
  the recorded `--retry-failed` command; response-bearing keys remain skipped
  and the first new 429 stops the run.

## 最后更新

2026-08-20 +08:00

## 当前权威检查点——DeepSeek 失败行恢复收口

- 分支 `codex/q2-empirical-study`；`m3-guard` 远程已配置，仍未 push。
- DeepSeek 已完成唯一一次显式失败行恢复。只执行 33 个无官方响应的
  work key，867 个已有响应项均未重跑。
- 最终为 933 条物理记录 / 900 个唯一 work key；900 项均进入 ITT，
  33 项为 repeated pre-response failure，`retry_eligible=0`。
- 全部尝试累计 1,638 provider calls、CNY 1.3888324；返回模型精确为
  `deepseek-v4-pro`，forbidden 字段/tools/external effects 均为 0，runner 为 0。
- DeepSeek 子阶段已技术收口。下一步只恢复 Gemini 免费层中无响应或尚未触及的行；
  已有官方响应的 Gemini 行不得重跑。F-PAPER-002 保持 `in_progress`。
- Gemini 当日 `remaining` 已因系统性 429 停止。已有响应的 work key 不得重跑；
  下一 quota day 只运行 `--retry-failed`，新代码会在第一条 429 后停止。最多三个
  配额日，之后保留已完成子集并透明降级，不启用 Billing。
- 运行器失败恢复、一次性授权统计、五图生成器和六表 CSV 导出器已完成；定向验证为 17/17，Ruff、
  py_compile 通过。合成数据 PNG 已逐张视觉检查；正式图等终态统计后一次生成。
- Active manuscript README、Introduction、Methods、Related Work 和 figure/table
  plan 已按 lean 研究口径更新；最终 Results/Abstract 仍必须等待终态统计，禁止填充
  尚未观察的数据。
- 不运行 Full Harness、递归历史验证、盲测、Pro500/2000 或真实工具/effect。
  只修复并重跑无官方响应失败行，所有成功或响应后失败行保持终态。

## 当前权威检查点——精简实证里程碑 1

- 分支是 `codex/q2-empirical-study`，基线提交 `d533414`；`m3-guard`
  远程已配置但未 push。
- 权威新计划是
  `protocols/paper_upgrade_v2/lean_empirical_execution_manifest_v1.json`：
  180 主样本、60 授权扩展子集、90 Gemini 嵌套子集，对应 900+450 行。
- 现有结果只做过一次性分析，紧凑结果在
  `docs/research/paper_v2/lean_empirical/existing_results_analysis_v1.json`。
  Pro/Flash 都显示 full 的 unsafe effect 高于 policy-only，因此保持实证研究与
  负面结果定位，不做领先防御声明。
- 定向验证为 pytest 4/4、Ruff/py_compile 通过；没有执行 Full Harness。
- 恢复时从最小新运行器开始，先完成定向测试，再只跑 DeepSeek/Gemini
  各 6 行 formal prefix。只允许重跑无官方响应的失败行，已成功行永不重跑。
- 最小运行器与上述恢复语义已实现，定向测试 8/8，Ruff/py_compile 通过。
  下一步直接运行 `deepseek --stage canary`；它只会执行 6 个尚无终态的
  formal-prefix work key。
- DeepSeek prefix 已成为终态，不得重跑：6/6 行、14 calls、CNY 0.0157848，
  5 completed + 1 max_steps；6 行全部有官方 response ID 和精确 Pro 模型身份，
  tools/effects/retry 为 0。恢复时应直接运行 `gemini --stage canary`。
- Gemini prefix 也已终态：6 work keys 全部进 ITT，3 completed、2 parse_failure、
  1 repeated VIGIL pre-response failure；5 行有官方响应，USD 0。两次 VIGIL
  失败原始行都保留，不得再重试。恢复时进入 DeepSeek/Gemini
  `--stage remaining`，运行器会跳过所有 canary 终态。
- 禁止 Full Harness、历史递归重放、盲测、Pro500/2000、真实工具/effect
  和未经单独授权的 push。F-PAPER-002 仍为 `in_progress`。

## 当前权威检查点——Gemini Public-v5 segment 0 技术门通过，按 owner 指示停止

- `F-PAPER-002` 仍为 `in_progress`。本轮完成了 v6-derived non-authorizing gate
  v4、新 recovery-v5 single-use wrapper 和一个最小 Gemini 正式日段，不代表
  1,791 条矩阵、Adaptive、600 条 blind 或最终结项完成。
- gate v4 manifest `d79faf97...e1e9a`；exact admission manifest
  `99abc6a8...27de4`。两者分别只证明工程前置条件和 `2026-08-05`/segment-0
  的单次授权，不能自动授权下一配额日或下一 segment。
- segment 0 为 1/1 记录、1 次调用/transport completion、free USD 0、
  retry/tools/effects=0/false/false，technical review manifest
  `86e48d12...560c2` 全检查通过。scientific outcome/result admission=false。
- wrapper receipt SHA `a881799f...b3de`；20/20 定向回归、Ruff/compile、
  PowerShell parse、conventions 12/12 通过。正式相关进程当前为 0。
- 新 gate/wrapper 已接入当前 `verify.ps1`，但新增源后尚未再运行一次完整 Harness；
  恢复更大规模实验前必须先取得新的直接 exit-zero 完整 Harness，不能只依赖
  本次最小段技术门。
- 报告：
  `docs/research/paper_v2/reports/M3_PI_Guard_Gemini_Public-v5_segment0阶段报告_2026-08-06.md`，
  SHA-256 `76137e6b...eb05`。当前按 owner 指示保持停止，不自动启动 segment 1。

## 当前权威检查点——8页 Word 报告已验证，按 owner 指示停止

- 当前无 Harness/Public/Adaptive/provider 正式进程；本轮未启动、停止、恢复或
  重试任何实验。
- 主要交付：
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段技术状态报告_2026-08-06.docx`，
  SHA-256 `a0d088d2f6a1a8554bb6ea0c2bbdc5c0e34755f9bf689e2267ede3be01da531b`。
- 8页均经本地PDF/PNG渲染和逐页视觉检查；无裁切、重叠、破表或缺字。7张表的
  `tblW/tblInd/tblGrid/tcW` 精确一致；两张图含替代文本；a11y high=0。
- 生成器 `scripts/build_stage_technical_report_docx.py` 通过 Ruff 与 py_compile；
  必需内容和 secret-format 扫描通过。QA receipt：
  `outputs/report_qa/stage_technical_report_20260806/qa_receipt.json`，SHA-256
  `3e948b02499e7c277aa9eaac9d04b275b1cfc45b12c3c0296eb5a9f226423c25`。
- 报告结论仍是：v6 工程基线绿色、Flash 1791条仅物理闭包且结果封存、Gemini
  正式矩阵/三模型 Adaptive/600条盲测/最终统计包未完成。F-PAPER-002 必须保持
  `in_progress`。
- 本轮零 gate/admission、零 API/provider/network、零 outcome/label 访问、零真实
  effect。除非 owner 发出新的恢复指令，下一执行者应保持停止状态。

## 当前权威检查点——阶段报告已渲染，正式实验继续暂停

- 报告前只读检查确认相关 Harness/Public/Adaptive/provider 正式进程为 0；
  没有遗留运行需要等待，也没有停止或重启进程。
- 技术报告 source artifact 位于
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段技术报告_2026-08-06_artifact.json`，
  SHA-256 `c3b992d145c92d4c25f393fe28a8ecb42272cfe939eaefe774b83b4826ee2197`。
  其 14 个阅读块、4 个指标卡、2 个图和 2 个表通过 Data Analytics artifact
  validator，随后 MCP report renderer 返回 `ok=true`。
- 报告停止点：v6 仍是当前直接绿色工程基线；Flash 1791/1791 为 outcome-blind
  物理闭包；Gemini v5 仍是 non-authorizing candidate；Adaptive 只有 8 任务
  budget-50 探索性前缀；blind 只完成 Day-1 登记，0/600 候选成集。
- 本轮没有创建 fresh gate/provider admission，没有 API/network/provider 调用，
  没有打开 blind label 或科研 outcome。恢复时从 v6 receipt 重放和 non-authorizing
  gate 开始，不能直接执行 provider。
- `F-PAPER-002` 保持 `in_progress`；用户要求本轮到报告为止，当前应停止。

## 当前权威检查点——Fresh Harness v6 直接绿色终态，按 owner 指示停止

- `F-PAPER-002` 仍为 `in_progress`；本次只完成 v5 failure freeze、Git
  process-scope remediation 和 v6 完整 Harness，不代表 21 天实验结项。
- v5 immutable review manifest `02af896a...7149`；Git qualification manifest
  `f4bbaaac...c7db`。v5 保持直接 exit 1，未改写或重试。
- v6 输出根：
  `outputs/verification/experiment_closeout_fresh_harness_v6_20260805`。
  2026-08-05 23:08:10 至 2026-08-06 03:30:27；child exit 0，13/13 stage PASS，
  pytest 1538/1/3，唯一 `Verification failed=0`，receipt evidence gate PASS。
- receipt/stdout/stderr SHA 为 `26e51662...3798` / `23d9f884...a945` /
  `0d2da881...0573`；verifier/helper 运行前后哈希稳定。API 环境 scrubbed，
  provider/network authorization=false，global/repository Git config 未修改。
- 定向验证：10/10 pytest、Ruff、compile、PowerShell parse、conventions 12/12、
  qualification/review 重放全通过。相关进程最终 0。
- owner 要求本轮完成后停止：未创建 v6 之后的新 gate/admission，未调用 API，
  未启动 Gemini/Public/Adaptive/blind。恢复时必须先重放 v6 receipt，再单独创建
  non-authorizing gate 与 exact provider admission，不能把绿色 Harness 当作自动授权。
- 报告：`docs/research/paper_v2/reports/M3_PI_Guard_Fresh_Harness_v5_v6收口报告_2026-08-06.md`，
  SHA `39dc2662a35af319847f0c0487d1641e4aa892bc6461506e0a9315cbd4705167`。

## 当前权威检查点——Gemini v2/v5 离线完成，完整 Harness 无终态后停止

- `F-PAPER-002` 仍为 `in_progress`。
- 已实现 `gemini_trace_attaching_runtime_v2.py`、Gemini local-precommit
  contract v2.1、Gemini Public-v5 untouched-only canary recovery，并将它们及
  Flash recovery-v4/evidence-merge-v1 接入 Harness。
- 已验证：runtime v2 20/20；v5 candidate/admission 3/3；missing request-ID
  E2E 1/1；contract v2.1 verify exit 0；v5 write/verify exit 0；Ruff、compile、
  conventions 12/12；相关后台进程最终 0。
- 完整 Harness 外层在 3604 秒返回 exit 124。原 pytest/Harness 子进程仍在
  计算并于 441.6 秒后自然结束，但最终 stdout/exit code 不可恢复；状态是
  inconclusive，不是 pass。
- 本轮零 credential 读取、零 API/provider/network 调用、零配额预约、零付费、
  零 provider tool/effect；没有创建新 admission。
- 下次只能从持久化 stdout/stderr/receipt、至少 90 分钟窗口、API 环境 scrubbed
  的 fresh single-use Harness 恢复；直接 exit 0 前不得创建 v5 日段 admission。
- 报告：`docs/research/paper_v2/reports/M3_PI_Guard_Gemini_v2_v5离线收尾报告_2026-08-04.md`。
  SHA-256：`2bc1d1c7c427a0cb1e834e312e24ed85b7aa687ea74bb6a360e41c902ca3b29b`。

## 当前权威检查点——Flash 第二模型证据完整性通过，执行暂停

- recovery evidence review v4 已对 s0/s1 独立写入并重放，manifest 为
  `1faf69b8...e31292c` / `cac90f24...fcc36`。两个分片 evidence integrity PASS；
  s0 的 claim quality 仍因 10>6 FAIL，s1 PASS；历史 v3 不改写。
- second-role merge v1 精确闭合 1791 个唯一工作键、16 diagnostic、4193 calls、
  CNY 1.87793024，终态重试/工具/effect 为 0/false/false。manifest
  `7fba09cc...8432b`、文件 SHA `6334514e...ef4e`，write/verify exit 0。
- outcome、task completion、unsafe effect 和条件差异均未聚合；merge 只标记
  `ready_for_independent_result_admission=true`，自身 result/outcome authority=false。
- 定向 pytest 8/8、Ruff/compile、项目 conventions 12/12 通过；新 full Harness
  尚未运行。相关进程 0，
  owner 要求本轮停止，不启动 API/Gemini/Adaptive/blind/Harness。
- 报告 SHA `e55f3bbf...f6ea8`。下一次恢复从 Gemini 前瞻合同和新 full Harness
  开始，不能直接执行 provider。F-PAPER-002 保持 `in_progress`。

## 当前权威检查点——运行已收口，等待下一次显式恢复

- 当前相关正式进程为 0；不得恢复 PID 25256/43856/42336 或复用其身份。
- Flash recovery s0/s1 分别完成 652/654 条，执行与 review 子程序 exit 0，
  但 wrapper 都因 technical gate FAIL 而 exit 1。s0 有 10 diagnostic > 6；
  v3 review 另有 `source_terminal_records_retried=false` 被 `all()` 误判的缺陷。
  receipts SHA 为 `80689b50...2d696` / `611d5d71...0ba2a`，结果未准入。
- Flash 物理闭包为 1791 records、16 diagnostic、4193 calls、CNY 1.87793024；
  不得将全局 0.8934% diagnostic 比例替代冻结分片门，也不得读取 outcome 后再
  选择门禁。
- Gemini s1 receipt SHA `7387c2d1...8b435`：HTTP 200、exact model、response ID，
  但 provider request ID 缺失；这是契约冲突而非 429。abort review manifest
  `6d7605dd...d649`，same-segment/work retry=false、result eligible=false。
- Gemini abort review compile/Ruff、write/verify 和 pytest 7/7 通过。报告：
  `docs/research/paper_v2/reports/M3_PI_Guard_当前运行收口与阶段评估报告_2026-08-04.md`，
  SHA `20972e4a...dac6`。
- owner 要求本轮停止。下一次恢复先版本化 Flash review v4 和 Gemini formal
  attestation/record contract，再跑 fresh full Harness；不得直接启动新 API。

## 当前权威检查点——Gemini v5 segment 1 与 Flash 双分片并行运行

- Gemini quota day 是 America/Los_Angeles `2026-08-03`；账本已有 Aug-02
  segment 0，当前日启动前未预约。segment-1 admission
  `93ba06fc...e03a` 绑定 2 records、最多 16 requests、USD 0、retry 0。
- guarded wrapper PID 42336 于 00:34:36 启动，当前 alive。禁止同一 quota day
  第二个 formal Gemini reservation、自动 retry、重启或 paid fallback。
- Flash s0/s1 PID 25256/43856 继续运行；三条 workload 的 provider/ledger/
  output/budget state 完全分离。只监控 content-free 技术状态，不读取 outcome。

## 当前权威检查点——Flash recovery-v3 双分片运行中

- gate-v3 manifest `e06188dc...b985`、文件 SHA `018af452...3432` 已重放；
  只证明 Fresh Harness v4/Day-1/order/candidates 无漂移，不自行授权 provider。
- s0 admission `9674f7f3...622e`：652 untouched records、CNY 2.04118328；
  s1 admission `fde24a50...4f77`：654 untouched records、CNY 2.17094144。
  两者 retry=0、provider tools/external effects=false、result admission=false。
- guarded wrapper s0 PID 25256、s1 PID 43856 于 2026-08-04 00:13:15 启动，
  当前 alive。wrapper 在创建 run root 前会先重放耗时 gate，因此初始 run root
  不存在是预期状态；禁止停止、重启、再次启动或复用身份。
- 原 473 个 terminal prefix、2 diagnostics、12 canary 均不重试；总 Flash 角色
  ceiling 保持 CNY 5。仅监测 receipt/计数/成本/进程，不读取 condition outcome。

## 当前权威检查点——Fresh Harness v4 直接 exit 0，执行已暂停

- 输出根 `outputs/verification/experiment_closeout_fresh_harness_v4_20260803`
  已于 20:38:25 自然终态；直接 OS exit 0，13/13 stage PASS，pytest
  1485 passed / 1 skipped / 3 warnings，`Verification failed=0`。
- receipt/stdout/stderr SHA-256 为 `a9fddc0f...2c1b`、`1b1a5305...3d75`、
  `777e65d1...2c26`。verifier 为 `33390d65...c6e4`；API env scrubbed，
  provider/network authorization false，运行期间 provider calls=0。
- 已确认 helper 37772、child 29776、旧 Flash wrapper 41632/23180 和 interim
  Harness 35928 均已自然消失。不得恢复旧分片或重试终态 work key。
- 所有者要求完成当前运行并写报告后停止。故 gate-v3 工件仍不存在，Flash
  recovery-v3、Gemini continuation-v2 仍只有非授权候选，后续 Public、Adaptive
  与盲测均未启动。
- 阶段报告：
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性实验报告_2026-08-03_Harness_v4.md`，
  SHA-256 `107c779ca2fa79545d048ea218d25811e949ccf037bd2cfeed16919798c23333`。
  F-PAPER-002 保持 `in_progress`；恢复时先重放本 receipt/Day-1 acceptance，
  再生成 gate-v3 和独立 exact-command admission。

## 当前权威检查点——fresh Harness v4 正在运行

- 输出根：`outputs/verification/experiment_closeout_fresh_harness_v4_20260803`；
  launcher 16:03:32 单次启动，helper PID 37772，当前 alive，receipt 尚不存在。
- preflight：fresh root absent、相关执行进程 0、launcher parse PASS、v3 failure
  review exit 0、Day 1 acceptance exit 0。`running.json` 锁定 verifier
  `33390d65...c6e4`。
- `DEEPSEEK_API_KEY`、`GEMINI_API_KEY`、`GOOGLE_API_KEY` 已 scrub；network/provider
  authorization false、automatic restart false。禁止停止/重启/复用输出根；只有
  direct exit 0 后才写 gate-v3，随后仍需独立 exact provider admission。

## 当前权威检查点——interim v3 失败已冻结，fresh Harness v4 待启动

- interim v3 于 15:38:19 自然结束，direct receipt 为 exit 1；pytest
  1456 passed / 1 skipped / 3 warnings。唯一失败是旧静态测试未区分
  `adaptive_formal_pro_controller_v1` 与合法 v2 controller；其余 Harness stage
  全绿，API env scrubbed，provider/network authorization false。
- failure review manifest `67bcdaaa...78cf9` 已写入并重放；失败根和日志不可变。
  修正后的 focused 20/20、扩大组合 38/38、conventions 12/12，Gemini v5、
  continuation-v2、Flash abort/recovery 候选独立 verifier 均 exit 0。
- 当前 `verify.ps1` SHA-256 `33390d65...c6e4`。fresh gate-v3 源与
  `start_experiment_closeout_fresh_harness_v4.ps1` 已离线资格化；输出根
  `outputs/verification/experiment_closeout_fresh_harness_v4_20260803` 必须保持
  全新并单次启动。gate 工件只在该次 direct exit 0 后生成。
- PID 41632、23180、35928 均已自然消失；不得恢复旧 Flash 分片。Flash
  recovery-v3 的 1,306 个未触碰项与 Gemini 的 1,779 条 continuation-v2 目前
  只有候选、无 admission、无新 provider call。
- Day 1 inbox 当前精确 3/3，三个历史 SHA-256 和 acceptance manifest
  `94e5a647...745c` 再次重放通过，pytest 2/2；没有删除、移动或改写文件。

## 当前权威检查点——Gemini v5 继续门已校正，免费层日历下界已显式化

- segment-0 v5 review manifest `8c256e49...9728c`：1 record/1 call
  attempt/1 transport completion/1 allowlisted VIGIL runner failure retained in
  ITT，14/14 checks，USD 0，tools/effects/results false。
- wrapper recovery manifest `1df13ad9...47f1f` 不补造 receipt，记录 OS exit
  unknown、segment terminal、same-segment retry false。compile/Ruff、3/3 和
  write/verify exit 0。
- continuation-v2 manifest `fcc80d26...5c95` 保留 1,779 条、1,186 个
  日段和 4 逻辑 shard，激活门更正为 v5 aggregate；Batch/付费/执行/
  结果准入均 false。免费标准 API 的续跑日历下界为 1,186 个配额日，
  不得再宣称 Gemini 完整矩阵能在 21 天内结束。
- Flash wrapper PID 41632/23180 和 interim Harness v3 PID 35928 仍在运行，
  禁止停止/重启。Harness pytest 已显示一个 F，等终态 receipt/log 后再修复。

## 当前权威检查点——Day 1 登记链完整可重放

- `external/independent_blind/day1_registration_inbox` 当前严格包含三份
  公开登记工件；SHA-256 为 `86db8a9d...de3bb`、`02e8282f...312b`、
  `2b699fe3...43553c2`，与原始 acceptance 精确一致。
- 冻结 acceptance verifier exit 0，定向 pytest 2/2，acceptance manifest
  `94e5a647...745c` 不变。Day 1 保管人登记已完成，当前不存在
  登记证据重放阻塞。
- 较后文档中的 `blocked_missing_verifier_receipt` 段落仅是保留的历史
  事件，不是当前状态。600 条 authoring/custody、3,600 条盲测执行、
  解封与评分仍是独立待办。

## 当前权威检查点——Flash 1,779 条正式续跑运行中

- fresh Harness v2 已自然完成并直接 exit 0；13/13 stage PASS，pytest
  1451 passed / 1 skipped / 3 warnings。gate v2 manifest `8f9fc72c...3fb9e`
  已验证；Day-1 acceptance 也已恢复为精确三文件可重放状态。
- Flash Public-v4 second-role canary 已 12/12 通过，18 calls、CNY 0.01232192、
  0 retry/tools/effects；technical review 允许矩阵续跑但不允许结果分析。
- continuation-v2 candidate manifest `18b80a5c...2906`；分片 0/1 为 890/889
  条，输出身份分别 `cb6e65e0...70b2f`、`13e751fd...4eef`，每片 CNY
  2.49383904，总上限连同 canary 为 CNY 5。
- admissions `a5044d28...26e4`、`1d07da6d...2fec` 已通过；guarded wrapper
  `run_deepseek_flash_public_second_continuation_v2_guarded.ps1` 通过 focused
  4/4、Ruff、PS syntax。wrapper PID 41632/23180 于 11:52:22 启动，各自仅有
  一个 execute 子进程；不得停止、重启、重跑或复用输出根。
- 等两个 receipt 自然出现后，仅检查 final exit、终态计数、technical review、
  预算与 trace 完整性；若 diagnostic/预算暂停则原样封存，不恢复同一身份。
- 600 条盲测 authoring 仍待第三方完成，登记已完成不等于盲测完成。

## 当前权威检查点——fresh Harness v2 正在运行，禁止 canary

- Day-1 原始 verifier receipt 已补回且哈希 `2b699fe3...43553c2` 精确匹配；
  acceptance 重放和 2/2 测试通过，当前不存在 Day-1 三文件缺口。
- fresh gate v2、launcher v2、guarded canary wrapper v3 已完成离线资格：24/24
  测试、Ruff、compile、PowerShell syntax 通过。wrapper 在创建单次 canary 根前
  先验证 fresh gate 和 public admission，防止缺门时烧毁 run identity。
- Harness 根：
  `outputs/verification/experiment_closeout_day2_harness_v2_20260803`；helper PID
  31716，verify SHA `48b5a825...05a0`，API env scrubbed，network/provider false。
  当前已进入 pytest，receipt 尚未生成。
- 不得停止、重启、复用该根或启动 DeepSeek/Gemini 调用。自然结束后先检查直接
  receipt；仅 exit 0 且 13 个 stage PASS 时写入/验证 gate v2，然后 guarded
  DeepSeek Flash 12-row canary 才具备下一层前置条件。

## 当前权威检查点——Day-2 失败已冻结，Harness 接线已修复

- Day-2 v1 receipt 直接观测 exit 1；1438 passed、1 skipped、3 warnings，只有
  closeout prospective stage 失败。失败审查 manifest `230fc98...e398f` 已重放，
  明确 provider/network calls 为 0。
- 根因是旧 Pro-50/Flash-50 v1 admission 已被
  `adaptive_execution_order_supersession_v2` 永久废止。当前 Harness 删除了两个
  `--verify-admission` 调用，保留 candidate 字节验证，并新增 order/failure/Day-1
  acceptance 三个显式门。
- 修复后 PowerShell syntax、Ruff、compile、14/14 定向测试和 10/10 无凭据
  closeout 离线复演通过。当前 `verify.ps1` SHA-256 为
  `1487b13edbee5f806385726068eb92d5afa3194b0d095c9cae8a66d73e082303`。
- 旧 `experiment_closeout_current_harness_review_v2` 仍保持字节不变；其测试现在
  明确证明该 review 是历史证据，并要求它对已推进的当前 verify 脚本 fail closed。
- 不要启动 fresh 完整 Harness，直到 inbox 恢复原始 verifier receipt；否则
  Day-1 acceptance 会确定性失败。恢复后首先重放 acceptance，再以全新输出根
  启动直接 receipt Harness v2，成功后才进入 DeepSeek Flash canary。

## 当前权威检查点——Day 1 已完成，当前重放等待原始 verifier receipt

- 当前 `external/independent_blind/day1_registration_inbox` 只有两份公开文件；
  `custodian_registration_verifier_receipt_v2.json` 缺失。公钥和 registration
  v2 的哈希仍与历史 acceptance 完全一致。
- `independent_blind_day1_acceptance_v1` 当前不能重放；定向 pytest 为 1 passed /
  1 failed。历史 acceptance manifest `94e5a647...745c` 保留为 Day 1 当时已完成
  的证据，不覆盖、不删除；缺失文件只使当前三文件全链不可复现。
- 搜索项目目录、相关项目目录、Downloads、Desktop 和 Temp 后，仅发现 pytest
  负例的临时同名回执，不得作为第三方证据。
- inbox 目录 LastWriteTime 为验收后的 `2026-08-02 23:37:43 +08:00`；本轮没有
  文件删除命令，验收测试仅向 tmp_path 复制，回收站无副本，非管理员 USN
  读取因 Access denied 无法归因具体进程。
- 下一步由保管人重新交付原始
  `custodian_registration_verifier_receipt_v2.json` 到上述 inbox。到位后先运行
  `python -m experiments.paper_v2.independent_blind_day1_acceptance_v1 --verify-acceptance`
  和定向测试；两者全绿后解除证据重放阻塞。Day 1 完成及技术时钟不追溯撤销，
  当前缺口状态为 `blocked_missing_verifier_receipt`，F-PAPER-002 仍为
  `in_progress`。

## 当前权威检查点——Day 1 登记完成，盲测后续暂缓

- 真实第三方公开登记交付已在
  `external/independent_blind/day1_registration_inbox` 验收；目录严格只有
  公钥、registration v2 和独立 verifier receipt 三份文件。没有接收或打开
  私钥、身份声明明文、候选或标签。
- v3.4 冻结 verifier 重放通过：精确三文件闭包、签名、独立验签、角色分离、
  零标签和 28/28 recorded checks 均成立。开发者侧 acceptance manifest 为
  `94e5a64710dbcef941375c257e210ab8ea424a0d0b975e50e86c0509e8df745c`，
  对应工件
  `protocols/paper_upgrade_v2/independent_blind_day1_registration_acceptance_v1.json`。
- write/verify 均 exit 0，定向 pytest 2/2。Day 1 现已完整登记完成，结项技术
  时钟可从 `2026-08-02T15:06:47+00:00` 启动。
- 用户要求先推进可独立完成项，因此 600 条盲测 authoring/custody、3,600 条
  六条件执行、标签解封和评分目前暂停。它们仍是结项待办；不得将“保管人
  登记完成”写成“独立盲测完成”。F-PAPER-002 保持 `in_progress`。
- Day-2 完整 Harness 仍由 PID 2468 在独立输出根
  `outputs/verification/experiment_closeout_day2_harness_v1_20260802` 运行；
  不得停止、暂停或重启。待 `receipt.json` 出现后再生成并验证 Day-2 gate，
  之后才能启动已准入的 DeepSeek Flash Public-v4 canary。

## 当前权威检查点——Python-first v3.4 已 GREEN，等待真人登记

- 唯一可交付包：
  `docs/research/paper_v2/reports/M3_PI_Guard_Blind_Custodian_Review_Package_v3_4_python_final`。
  从根 `README.md` 开始，在该目录使用 `custodian.py`；无 Word/PS1，无
  activate/setx/永久环境变量，私钥不进包。
- physical/embedded manifest SHA-256 分别为
  `43a6c80a454659167419ccabbf0ef33cb924fefee73fe5583d499e6eb1ac4651`、
  `644a0961d6bd7b6d5495191dc0672359678324715942d993513ee725c8f7f089`；
  core/test SHA-256 分别为
  `f4f4b75bc4d174c9c824d7c5fe60f2ed8a4402ec29f657ac0c8b5866c87bbfb4`、
  `469823985012270348cd0345232bb949b23f6af84a6e9175d0ee68c972de4c78`。
- 结构是 45 个物理文件 = 44 个 manifest 文件 + manifest，39 allowlist
  source + 5 generated。包内 33/33，源码 v1+v2+v3 50/50，conventions
  12/12；Ruff、编译、schema、secret/path 扫描和全部只读命令 exit 0。
- 独立 reviewer 已重放 nested `gold_label` 重签名和 completed→failure/timeout
  重哈希伪造，均被拒绝；只对 v3.4 给出 GREEN。v3/v3.1/v3.2/v3.3
  都是 rejected diagnostic，不得交付。
- A 可私有重放工件/哈希/签名，B 只做无标签签名/完整性验证；两者均不声称
  自动重算人工评分语义。
- 下一步必须由真实第三方亲自执行 README 的登记和独立验签。当前无真人
  registration/custody、无 600 条候选/标签、无盲测结果；F-PAPER-002
  仍为 `in_progress`，21 天时钟未启动。

## 当前权威检查点——保管人工具包/Word SOP 已验证，等待真人登记

- 最终 Word 手册：
  `docs/research/paper_v2/reports/M3_PI_Guard_第三方独立盲测保管人操作手册_2026-08-02.docx`；
  SHA-256
  `900db3b501d0ee50289af637e2f6c5d69105125d06af24c73659a2b18dd16fa3`。
  34 页已全部视觉检查；结构验证、表格几何和 a11y 0/0/0 通过。
- 唯一有效 standalone 工具包：
  `docs/research/paper_v2/reports/M3_PI_Guard_Blind_Custodian_Toolkit_v2_final`；
  含 00–18 号 PowerShell wrappers，内嵌 manifest SHA-256
  `9aaffe0120ff93ff3df9a93e955378b37000dd088da62a96eb66f28f086edac8`。
  旧工具包目录带 `SUPERSEDED_DO_NOT_USE.txt`，验证器会 fail closed。
- 控制模块
  `experiments/paper_v2/independent_blind_closeout_v2.py` 支持真实 Ed25519
  registration/custody/scoring 验签、递归禁用标签/结果字段、600→3,600
  完整生命周期；模块 SHA-256
  `7d33d609abefb7a436787712cc5516cb799c94948f6cb9c7879b9a1fbcac52e8`。
- 验证：聚焦测试 47/47，Ruff、项目规范审计 12/12、结构 validator、a11y
  均 exit 0；34/34 页
  人工视觉检查通过。0 credential、0 label、0 provider/API/network call、
  0 provider tool/真实 effect。
- 下一步不是由开发者代签：把 `_v2_final` 完整目录和 Word 手册交给真实
  第三方。第三方在 `D:\M3_Blind_Custodian_v2` 运行 00–04，私钥只放在
  `D:\M3_Blind_Custodian_PrivateKey` 或其控制的离线介质；独立验签通过后，
  才算“登记保管人”并可启动 21 天结项时钟。
- 当前仍没有真实 registration/custody manifest 或 600 条独立候选；
  F-PAPER-002 保持 `in_progress`，不得把本工具包/手册交付表述为盲测完成。

## 当前权威检查点——Day 1 工程完成，等待独立保管人

- 21 天结项计划已授权，当前仅做实验、证据链和工程验收；不写论文，
  历史 v7 永久只读且不恢复。
- 完整 Harness 已自然完成：13/13 聚合阶段 PASS，pytest 1,365 passed、
  1 skipped、3 warnings，0 `FAIL:`，唯一末行 `Verification failed=0`。
  stdout/stderr SHA-256 分别为
  `340509a306d6585b53e77a64751bafc5bab2c9ddda9b9ba7918a18b5951ec170`、
  `02a6c27e6984563a30e9f4de762ccbb5a4575c07cef687003b6154030be79a41`。
- 外层通道在父 wrapper 写 receipt 前超时；子进程随后自然完成。恢复审查
  manifest `22954e84b5a6f97c54faf25f9d972815e66c5a56262c6b00750643cb25eebec1`
  锁定日志和立即 exit 契约，只声明 effective exit 0，不冒充直接 OS exit。
- full Harness 后仅新增恢复 reviewer、其单测和生成 artifact 作为可执行/
  证据增量；runtime、controller、verify 脚本均未改，状态/移交文档另行更新。
  聚焦 pytest 2/2、Ruff、py_compile 和 review verify 通过。fresh canary 的技术前提满足，但 review
  不授权 provider 执行。
- Day 1 没有读取 credential，没有 API 调用、admission、quota reservation、
  费用、provider tools、真实 effects 或科学结果访问。
- 工程 Day 1 已完成；计划级 Day 1 仍缺真实第三方保管人登记。因此 21 天
  时钟尚未正式启动，F-PAPER-002 保持 `in_progress`。下一步先登记保管人，
  再完成 Day-2/3 离线资格和 fresh canary candidate/admission/reservation。

## 当前权威检查点——Public-primary 分析与阶段报告已完成，任务停止

- Public-primary 已正式准入并独立复核：5,082 records / 847 cases /
  600 attack / 247 benign，76 diagnostics 全留 ITT，0 排除。主模型为
  `deepseek-v4-pro`；12,808 official calls、CNY 11.9909764，0 retries、
  provider tools 或真实 external effects。
- 关键结论：M3-full unsafe-effect 38/600，结构化 133/600，policy-only
  13/600；工具 TCR 49/168、103/168、49/168。full 对结构化更安全，但
  比 policy-only 更不安全且效用显著下降，故只允许 empirical fallback。
- 最终报告：
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-30.docx`；
  SHA-256
  `6eeba31b59263160843bab1c23458fcee1ab89021f333ee7ea265a7be36bfd56`。
  16 页、6 图、17 表、7 外链；结构 QA、3/3 报告测试、Ruff、
  a11y high/medium/low=0/0/0 通过，16/16 页 WPS 只读渲染已人工检查。
- 验证证据：
  `outputs/verification/public_primary_final_harness_receipt.json` 记录首轮
  full Harness exit 1（1265 passed、1 skipped；一个测试状态隔离问题）；
  PowerShell 参数边界随后也已修复。
  `outputs/verification/public_primary_targeted_recheck_receipt.json` 记录
  修复后四项定向复核 4/4 exit 0，stderr=0。报告没有把首轮失败隐藏成
  全量绿色。
- 科学证据完成度 869/1200（72.4167%），投稿就绪度 68%。F-PAPER-002
  仍为 `in_progress`；第二模型、正式 40/20 adaptive、独立盲测和最终
  JISA submission package 均未完成。
- 用户明确要求当前代码完成、报告交付后立即停止。下一会话除非用户重新
  授权，不启动新 API、v7、第二模型或 formal adaptive；首先读取本移交。

## 当前权威检查点——Adaptive 已准入，Public 三片恢复中

- Adaptive-v2 已完成并独立准入：8 tasks、374 terminal queries、562
  official calls、CNY 0.552805、1 diagnostic retained、0 retries/tools/effects。
  结果为 budget-50 unsafe-effect 0/8，Wilson 95% CI 0–32.44%；只可称
  exploratory cost canary，不能替代 formal 40-task multi-budget panel。
- Public 原 continuation-v2 四个进程均已自然退出，封闭前缀为
  s0/s1/s2/s3 = 232/126/140/130。逐片 v3 recovery 使用同一冻结源码，
  只执行未触碰 work keys，不重试终态 diagnostic/formal-candidate。
- s1 已完成 1265/1265，71 diagnostics、3321 calls、CNY 4.274749。
  `continuation_shard_review_v3.json` 除冻结 1% diagnostic quality check
  外全部通过；`continuation_shard_evidence_review_v3_1.json` manifest
  `c4cf0096e40a4438d229e211ce65d03a6b9dfb20173d6da9e0d58359144d1c67`
  记录 evidence integrity pass、clean mechanism claim=false、
  empirical fallback only=true，且不豁免原质量门。
- 当前活进程：s0 PID 15272、s2 PID 36320、s3 PID 33700。06:20 记录数为
  268/1265、355/1264、273/1264；所有 stderr 为空。不得停止、重启或编辑
  `public_single_shard_recovery_v3.py`、`incremental_live_ledgers_v1.py`
  及对应 candidate/admission/ledger。
- 待三片自然完成后：依次写
  `continuation_shard_review_v3.json` 和
  `continuation_shard_evidence_review_v3_1.json`；然后写
  `public_primary_merge_review_v2.json`。只有 merge 通过后才写
  `public_primary_result_candidate_v1.json` 和单独 admission，之后执行
  `public_primary_analysis_v1`。
- 新 Public 结果链聚焦验证为 10 passed，Ruff/py_compile 通过；它预注册
  5,082 records / 847 cases / 600 attack / 247 benign、ITT retention、
  Wilson、exact McNemar、10,000 paired bootstrap、AgentDojo/M3-v2 分层及
  三类图。当前仍未访问 Public scientific outcomes。
- Full Harness 必须等三个 API 恢复进程结束后再运行。最新完整绿色基线仍为
  1,188 passed、1 skipped、3 warnings、`Verification failed=0`；
  F-PAPER-002 保持 `in_progress`。

## 当前移交检查点——Public continuation-v2 primary 四分片运行中

- continuation-v1 四个旧根已永久封存：合计 4 records、13 calls、
  CNY 0.014446、0 open attempts；失败原因是 record 使用 4.9 元 shard
  policy，而通用 state reconstruction 回落到 20.0 元全局 policy。
  `public_primary_continuation_abort_review_v1.json` manifest 为
  `be0d736abf4f856871978e472ae0408d15c51bd92cb2ef59c7dee4375b99995b`。
- fresh continuation-v2 candidate manifest 为
  `d05562406e081ae6c2b33fafc7e9f8963b8f04966ec4f9a819fd7dd397271692`；
  四片 1,265/1,265/1,264/1,264，每片 CNY 4.9，完整新调用上限
  CNY 19.6。旧 4 条记录明确不复用。
- 四个 single-use admissions 已校验，PID 36116/31540/35200/1592 于
  2026-07-30 01:43:51 +08:00 启动。启动后四片均越过旧版本的首条失败点，
  应继续只读监控 `records/attempts/budget/traces` 数量；不得因变慢而重启，
  不得自动重试 diagnostic/failed 分片。
- 运行日志位于
  `outputs/verification/public_primary_continuation_v2_runtime_20260730/`；
  正式根分别以 `public-primary-continuation-s0-v2-` 至 `s3-v2-` 开头。
  运行模块、candidate、admissions 和 append-only 根在完成前均视为冻结，
  不得原位编辑。
- v2 新增验证：聚焦 pytest 12/12、Ruff、py_compile、candidate 及四份
  admissions 通过。最后一次包含所有先前代码的完整 Harness 仍为
  1,188 passed、1 skipped、3 warnings；v2 新代码尚未纳入新的完整
  Harness，因此不得把旧结论冒充当前全量验证。
- 后续顺序：等待四片自然终态 → 每片 outcome-blind technical review →
  primary technical merge（含 v4 canary，总计 5,082）→ fresh second-role
  候选/金丝雀/执行 → 独立 result admission 后才可访问科学 outcome。
  当前 scientific score 仍为 753/1200（62.75%）。

## 并行检查点——Adaptive cost-canary v2 运行中

- v1 已永久封存：1 terminal query、1 official call、CNY 0.002271、
  0 open；失败为 post-record 字段名错误，abort review manifest
  `a44f398069d0b1d7ecdeb3063878021993bf1dd554c9dd425793065ea1764c6e`。
- v2 candidate manifest
  `6570795d5da00b5d6093ad5997ee2720d0f1644cb0313d02dfd2e88af446578d`，
  admission manifest
  `a179071c8d83884fede59731ee26c84b4b09d5dfff110c96b392f1a26fd3ccaf`。
  PID 9788，自 2026-07-30 02:04:59 +08:00 运行；日志位于
  `outputs/verification/adaptive_cost_canary_v2_runtime_20260730/`。
- 不得编辑 v2 controller/schemas/candidate/admission 或运行根；不得因运行
  时间重启。若进程自然完成，先执行 `--technical-review`，只核查 query/
  call/checkpoint/cost，不聚合 scientific outcomes；若失败则另建 abort
  review，不自动重试。

## 当前移交检查点——Public-v4 技术门与阶段报告完成，四分片尚未启动

- Public-v4 primary technical canary 已完成 24/24 records、64 calls，
  CNY 0.0521812，0 diagnostics/operational failures/retries/tools/effects。
  technical review 全绿，但 result admission=false，未访问科学 outcome。
- primary 剩余 5,058 条的四分片候选已冻结为 1,265 / 1,265 / 1,264 /
  1,264，每片 CNY 4.9；候选 manifest
  `e6217b6bc224b9925eee157378cb42f61a4b3bbb9dee54cee48fbce331ffb906`。
  当前没有 active shard admission、API 进程或新结果。
- 最新完整 Harness 自然退出 0：1,188 passed、1 skipped、3 warnings，
  `Verification failed=0`；stdout SHA-256
  `806033e70b4d538d2c8656221cb2590c34afa8deaa53fdee7f061ed8fe91a7fc`。
- 对外 Word 报告位于
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-29.docx`，
  SHA-256
  `5f89bdc294892658b8ca8d634f8c8d6810f92367abd345f5b026ee91d7d1e7d4`。
  共 17 页、6 图、19 表、11 链接；结构与 a11y 均通过，17/17 页完成
  Word fallback 渲染检查。soffice 缺失已披露。
- 报告验证命令：
  `F:\robot\Anaconda3\python.exe -m ruff check scripts/build_paper_v2_stage_report_20260729.py scripts/validate_paper_v2_stage_report_20260729.py`；
  `F:\robot\Anaconda3\python.exe -m py_compile scripts/build_paper_v2_stage_report_20260729.py scripts/validate_paper_v2_stage_report_20260729.py`；
  `F:\robot\Anaconda3\python.exe scripts/validate_paper_v2_stage_report_20260729.py`；
  `F:\robot\Anaconda3\python.exe C:\Users\gaohang\.codex\plugins\cache\openai-primary-runtime\documents\26.727.11326\skills\documents\scripts\a11y_audit.py <DOCX> --out_json <a11y.json>`；
  `F:\robot\Anaconda3\python.exe scripts/audit_project_conventions.py`。
  结果分别为 Ruff/compile PASS、结构 PASS、a11y 0/0/0、conventions
  12/12；`structural_qa.json` SHA-256
  `82d539682de9b337e78042b990c686cd635d4dddfc0e03a5a21e1ec9342be87d`。
- 科学证据仍为 753/1200（62.75%）。下一步在报告交付后逐片创建
  single-use admission，运行 primary continuation；之后运行 second，
  全矩阵终态后再做独立 result admission、统计与自适应攻击。

## 当前移交检查点——Public-v3 永久封存，Public-v4 identity 注入待实现

- Owner 授权的 v3 primary command 在 12/24 后 exit 1；25 attempt events、
  12 terminal、1 open、12 records、33 calls、13 traces，CNY 0.0263544。
- 首个 M3 work key 已成功解析，但 inherited resolver binding 使用 public-v1
  execution identity；runtime material 使用 fresh v3 permit identity，
  `work_key_sha256` 因此不一致。
- v3 不得恢复、重试、补写或科学准入。剩余 11 条保持 untouched；自动
  retry/provider tools/external effects 均为 0/false。
- 下一步：生成内容无关 v3 abort review；实现显式
  `execution_identity` 的 public M3 resolver v4，并新增真正调用 evaluator
  的 attack/benign × primary/second 探针。随后冻结全新 candidate/run/output
  identity，完成离线验证后再展示新的精确命令。
- v4 resolver 与上述四个 evaluator 探针现已实现并通过 4/4 + Ruff；
  qualification SHA-256 为
  `a92a5f3ec565d14421f3575c3dd199475fe1d28d8f050aeae0ac381e37b62c95`。
  尚缺 v3 abort review、v4 controller/candidate/live wiring 与全量回归。
- 当前 score 保持 753/1200，Public-v1/v2/v3 partial 均不计分。

## 当前移交检查点——Public-v3 离线闭环完成，等待新的精确命令确认

- Public-v2 保持永久封存：12 records、1 open attempt、29 calls、CNY
  0.0259414，结果不准入且不得恢复。
- Public-v3 新增 public-plan M3 resolver，覆盖 3,600 work items、750
  private bindings；四个跨角色/类别探针通过，online state 未改写，0
  credentials/network/provider calls。
- candidate manifest 为
  `7df71eda75083a36b787659b482549ff3b2a7085b5ad01f8830dd0d2f9a32ef1`；
  primary execution identity 为
  `9dc7d657239c0ab4d10d4ba52ad585de3a499e19257aa3a2d9122993a11a9139`。
  双角色 admission/output roots 均不存在，authorization=false。
- Stage A 重建退出 0（6,873 records、18 pairs、4 M3 probes、0 network/
  results）；v3 聚焦 10/10、Ruff、JSON、PowerShell/Bash syntax 通过。
- 完整 Harness 的外层输出通道在 7,204 秒超时；后台自然结束但 aggregate
  exit 不可恢复，故不把它记为绿色。可恢复全量 pytest 明确退出 0：
  1,170 passed、1 skipped、3 warnings，4,468.35 秒，stderr 为空；证据位于
  `outputs/verification/public_v3_pytest_{stdout,stderr,exit}.*`。
- 下一步必须先逐字展示 Public-v3 primary exact command并得到新的 owner
  确认，之后才可写 single-use admission、读取本地 API 配置和执行 24 条
  technical canary。旧 v1/v2 确认均不授权 v3。
- 科学证据仍为 753/1200；尚无 Public-v3 API 调用或科学结果。

## 当前移交检查点——Public-v2 部分执行永久封存，下一步为离线 Public-v3

- Owner 已逐字确认并执行唯一一次 Public-v2 primary canary。admission 文件
  SHA-256 为
  `ee631ff097f05dee2b48f2fea9c37769f0dbc0a01487919a3acfbe3c1f071e36`，
  candidate SHA-256 仍为
  `a17ab0926c0003e953b85834b8728a8ac98e360b684780b7fa98f10b9c07250b`。
- 运行在 12/24 records 后退出：25 attempt events、12 terminal、1 open、
  11 untouched、29 completed official calls。累计 usage 为 22,169 prompt、
  1,934 completion、17,536 cache hit、4,633 cache miss，CNY 0.0259414。
- 失败点为首个 M3-v2 公共 work key。AgentDojo public resolver 工作正常；
  M3 evaluator 仍默认使用 medium plan，因此无法解析 public-plan key。
- Public-v2 run/execution identity 永久不可恢复、不可重试、不可补写、
  不可进入 result admission。常规 technical review 正确拒绝开放 attempt。
- 内容无关 abort review：
  `protocols/paper_upgrade_v2/public_primary_canary_abort_review_v2.json`，
  manifest
  `c3e17fe2f74bd807a348202c2ac632c9be6e4f6c2e426c4a8b7a3c5a70d4f1c5`。
  它验证 27 个记录绑定调用和开放 attempt 的 2 个独立完成调用，
  且不报告/聚合科学终点。
- 新审计 Ruff PASS；聚焦 pytest 2/2 PASS（372.40 秒）。此前当前工作树
  完整 Harness 的 1,158/1/3 绿色结论仍是执行前基线；新增审计尚未做新的
  全量 Harness，因此不得把该旧结论标为包含 v2 abort review。
- 下一步：只做离线 Public-v3。将 M3 resolver 显式绑定 public plan/source
  reference，增加 primary/second × M3 attack/benign 零网络探针，使用新
  run/output/execution identity 和 candidate，跑当前工作树完整 Harness。
  只有之后才能展示全新的 exact command 并再次请求 owner 确认。
- 当前 evidence score 仍为 753/1200；12 条部分记录和 29 次调用均未科学
  准入，不加分。

## 上一移交检查点——Public-v1 零调用中止，Public-v2 等待重新授权

- Owner 已批准并执行 Public-v1 primary canary；两次本地启动均 exit 1。
  第一次发生在 attempt loop 前，第二次在一个 `started` event 后、provider
  client 调用前。审计结论为 0 provider requests、0 API cost、0 terminal/
  record/budget/trace、0 formal results 和 0 scientific-outcome access。
- Public-v1 output root 含一个 hash-valid open attempt，因此永久
  `run_resumable=false`；不得重试、恢复或补写。冻结 abort review：
  `protocols/paper_upgrade_v2/public_primary_canary_abort_review_v1.json`。
- LFischl Python 3.13.5 已补齐 Transformers 4.57.6、Tokenizers 0.22.2、
  Safetensors 0.6.2；现有 Torch 2.8.0+cu129 的 PromptGuard 双探针通过。
- 新版 `PublicFrozenAgentDojoCaseResolverV2` 从 public plan 的
  `source_reference` 恢复冻结 AgentDojo binding，4 个跨角色/类别探针通过，
  0 credentials/network/provider calls。
- Public-v2 candidate 仍是 6,873 条、18 qualified pairs、0 network/results，
  canonical manifest SHA-256
  `a17ab0926c0003e953b85834b8728a8ac98e360b684780b7fa98f10b9c07250b`。
  Primary fresh execution identity 为
  `7a95e3b65699d437681ed85df6e848e02e819db18feb7093caf2eda363ce7a1c`。
- Public-v2 聚焦测试 11/11 passed（1,164.68 秒），stderr 为空；Ruff、
  abort/resolver/Stage-A verify 通过。新的 v2 admission 不存在，
  `execution_authorized=false`。
- 当前工作树完整 Harness 已退出 0：1,158 passed、1 skipped、3 warnings，
  pytest 3,494.01 秒，`Verification failed=0`；stderr 三行均为预期
  RuntimeAuditor `delete_record` 阻断。stdout SHA-256 为
  `4d41de097058285bdaa5ba11e0b7cbb765ded21df0179705be157deb3e9b009d`。
- 下一步：展示并等待 owner 逐字确认新的 v2 exact command，然后才可创建
  single-use admission 和发起网络请求。不得把旧 v1 授权解释为 v2 授权。
- 当前 evidence score 753/1200（62.75%）；本检查点没有 public 科学结果，
  因而不加分。

## 当前移交检查点——34/34 引文审计完成，当前科学证据 62.75%

- `literature_matrix.md` 已完成 34/34 权威元数据和摘要范围审计，当前
  24 PR/10 PP；18 个非规范标题、1 个 Oral 标记、2 个过期 PP 分类和
  1 条完全错链已纠正。完整审计见
  `docs/research/paper_v2/manuscript/full_citation_refresh_v1.md`。
- L20 原链接实际对应无关论文；当前行替换为经 ICSE 2026 官方页面/DOI
  核验的 AgentSpec，并保留纠正记录。矩阵/manifest hashes 为
  `ecf952832afe5d474b70aa2141b8f9c05b0bd43d8da47287bcc836c9c3633570` /
  `0c6713700b9a77ba5ec9869b2259171ebc986421a135012c4c917fbf1f0c881e`。
- 专项 verification：citation+manuscript 7/7，Ruff PASS，citation
  `--verify-only` PASS，stale-title grep 无命中，score arithmetic PASS。
- scorecard 为 753/1200=62.75%（显示 63%），submission readiness 60%。
  `M3_PI_Guard_80_percent_evidence_execution_plan_v3.md` 与
  `evidence_80_execution_roadmap_v3.json` 纠正旧 v2 的“其他九项”算术；
  当前 753 + public 90 + adaptive 100 + manuscript 25 =
  968/1200=80.67%。历史 v2 与实验冻结均未修改。
- 当前仍不是 Stage 2.5 PASS：全文 inline citation context/bibliography、
  6,873 public、adaptive 40/20+hardest-20、盲测保管和机构 JCR 核验缺失。
- 04:38 Harness 于最新 Python/test/v3 状态前启动；它在 06:25 自然完成
  1,146 passed、1 skipped、3 warnings、`Verification failed=0`，但必须
  标为 superseded。06:26 起启动当前工作树权威 full Harness；其日志和
  exit 文件是当前唯一可用于终态声明的全量证据。0 credential read、
  0 API/network/model call。

## 当前移交检查点——medium 预结果完整性审计完成，全量重跑中

- `docs/research/paper_v2/manuscript/results_shell.md` 已由 admitted v8
  analysis 回填；测试哈希绑定 source analysis 并逐条件重建安全、TCR、
  operational/call/cost 表格。`discussion_draft.md` 仅解释中型证据并将
  public/adaptive generalization 保持 pending。
- `abstract_shell.md` 与 `figure_table_plan.md` 已加入工作区；前者是
  branch-locked 待填结构，后者记录五图六表的数据/admission 依赖，二者
  都不增加科学分。
- `pre_result_integrity_audit_v1.md` 纠正 Methods 的 stale zero-failure
  描述，明确 v2 mechanism-quality 与 v6 technical-admission 两个不同
  envelope；medium 数字/方法 verification PASS，但 final citation 与
  shortcut/generalization 为 insufficient，因此不是正式 Stage 2.5 PASS。
- 本轮专项证据：manuscript 4/4、Ruff（上一稿件同步检查）、normalized
  Methods/integrity assertions、feature JSON 和 diff check PASS。
- manuscript workspace 4/4 与 Ruff PASS。04:30 的 PID 40692 在收集旧测试
  后才发生稿件同步，因此在 43% 主动终止，不得引用为终态。
- 当前权威 full Harness 于 04:38 启动，wrapper PID 20860；固定前缀为
  `outputs/paper_v2/verification/post_medium_results_sync_full_harness/verify_20260728_043835`。
  04:51 仍在 pytest 慢测试，CPU 活跃、stderr=0；仅当 `.exit.txt` 为 0
  后才声明全量绿色。
- scientific score 仍为 730/1200；论文同步不能替代 6,873 public、
  adaptive 40/20+hardest-20 和各自独立 result admission。

## 上一移交检查点——自适应成本 canary 离线链完成，live 与全量终态仍封闭

- 新增 `adaptive_cost_canary_plan_v1`、`adaptive_query_ledger_v1`、
  `adaptive_cost_canary_controller_v1` 和 `adaptive_result_gate_v1`，
  以及 admission schema、冻结 candidate/result gate 与 4 个测试文件。
- candidate 从 frozen primary 40 tasks 中按结果盲 SHA-256 顺序选择 8 个
  不同攻击族；8×50、max 400 queries、max 3,200 provider calls、Pro
  CNY 5、concurrency 1、retry 0。每条 query 只修改
  `untrusted_content`，trusted fields 和 auto-compiled authorization 不变。
- query ledger 先 fsync started，再由 provider trace/budget ledger 记录
  0..8 calls，最后 terminal 绑定 content-free result 和 response-ID
  sequence；任何 open query、open provider request、hash/identity/cost
  drift 都失败关闭。work key 已使用 Windows-safe `__` 分隔。
- 新测试 20/20、邻接回归 45/45、Ruff、compile、JSON、PowerShell syntax、
  conventions 12/12、candidate/gate reproduction 和 diff check 均 PASS；
  注入 transport 的完整 official bridge qualification 为 0 network。
- full Harness 的外层工具在 3,604 秒超时并丢失 stdout/exit；真正 PID
  69384 及其子验证继续自然结束，但最终 `Verification failed` 值无法恢复。
  不得把它写成 PASS。当前 `harness/scripts/verify.ps1` 已纳入所有新文件和
  两个新 verifier；下次需要在可保留日志/退出码的环境重新跑完整入口。
- 04:30 的可恢复重跑后因 manuscript/test 状态更新而废止；当前权威重跑见
  本文件顶部的 PID 20860。
- 本轮 0 credential read、0 API/network/model call、0 admission、0 formal
  result。Public Pro 24-row exact command 仍等待 owner 明确确认；adaptive
  exact command 不得与 public admission 合并。

## 当前移交检查点——Public-v1 Stage A 完成，等待 Harness 与 owner 双门

- 6,873 条公共计划、预算/trace/record 双账本、candidate/admission
  controller、24+12 canary、analysis preregistration 和 result gate 均已
  实现并冻结；0 API/network/model calls，0 正式结果。
- 主模型为 `deepseek-v4-pro` 5,082 条，第二模型为
  `deepseek-v4-flash` 1,791 条；Flash 仅作 cross-model replication。
  增量预算 CNY 25，Pro/Flash 角色上限 CNY 20/5，保留 CNY 5。
- focused public-v1 tests 25/25、Ruff PASS。唯一 full Harness 自然完成
  1,126 passed、1 skipped、3 warnings，pytest 2,367.05 秒，所有 stage
  PASS，`Verification failed=0`；Stage-A/analysis/result-gate 三项复现
  也均 exit 0。
- exact primary canary 命令已展示给 owner，等待回复“确认执行上述命令”。
  在确认与 Harness 绿色同时满足前，不写 active admission、不读取 key、
  不发 API。未来 admission 必须绑定 owner 确认 statement SHA-256。
- 完整 Harness 日志位于
  `outputs/paper_upgrade_v2/verification/pre_public_canary_v1/`；原父 PID
  73660 已自然退出。旧 v8/v9 recursive verifier 的高耗时作为性能债保留，
  不影响本次绿色结论。

## 当前移交检查点——80% 科学证据计划 v2 等待 owner 确认

- 用户要求先重新规划再实验；本阶段 0 API/network/model calls、0 formal
  results，实验执行授权=false。
- 当前 scorecard 为 730/1200=60.83%（显示 61%）。达到 80% 的冻结路线只
  计算三项：公共 10→100、自适应 0→100、manuscript 30→70，最终
  960/1200=80%。盲测、Gemini smoke、工程就绪和报告不用于凑分。
- 公共真实规模为 6,873 条：Pro 5,082、Flash 1,791。中型 v8 条件级证据
  外推约 15,828 provider calls、中心 CNY 12.03；公共增量 fuse 计划为
  CNY 25。先 24 条 Pro 与 12 条 Flash canary，outcome-blind 技术审查通过
  后再扩展。
- 新策略为公共优先，再做自适应。原因是 public controller/gate 可复用中型
  证据链且成本可估；自适应 75,000 查询面板的 provider-call 倍数未知，先做
  8×50、CNY 5 canary，再单独冻结正式费用门。
- Flash 是正式吞吐型第二模型，只支持跨模型声明；Gemini v3 是 18 RPD 的
  跨提供商增强，不阻塞 80% 主路径。Gemini v1/v2 和 DeepSeek v1–v9 继续
  不可变。
- 详细计划：
  `docs/research/paper_v2/M3_PI_Guard_80_percent_evidence_execution_plan_v2.md`；
  机器路线图：
  `protocols/paper_upgrade_v2/evidence_80_execution_roadmap_v2.json`。
- owner 确认后只先实施 Stage A：新增版本化 public/adaptive controller、
  result gate、analysis、schema 和负例，运行 focused checks 与完整 Harness。
  未达到 `Verification failed=0` 前不得启动公共 canary。
- 离线规划验证已完成：Python 3.13.5，锁定哈希 3/3、JSON/算术/密钥模式检查
  全过，manuscript workspace 4/4，`git diff --check` 通过；完整 Harness
  留到 Stage A runtime 实现后执行。

## 当前移交检查点——Gemini 免费层连通已恢复，正式 v3 仍未准入

- Owner 项目页确认 exact project `M3 PI Guard test` 当前为 Free，paid billing
  已解绑。两张来源截图只保留 SHA-256，不复制到仓库。
- 新增 `gemini_free_tier_quota_snapshot_v2.json` 和
  `gemini_fallback_budget_override_v2.json`，仅适用于未来 prospective v3：
  provider 上限 5 RPM/250K TPM/20 RPD，本地 fuse 4 RPM/200K TPM/18 RPD/
  16K output tokens，保留 2 RPD，并发 1、retry 0、USD 0。
- 离线哈希、字段与 budget-policy 校验通过后只发出一次固定 `SAFE` 请求。
  HTTP 200，returned model=`gemini-3.6-flash`，exact SAFE，32/1/44 tokens，
  latency 1996.3301 ms；0 retry/tools/effects/fallback。
- 脱敏结果位于
  `protocols/paper_upgrade_v2/gemini_free_tier_connectivity_diagnostic_v1.json`。
  Google 给出 response ID 但没有 request ID，因此 trace 不完整，结果只能
  证明当前连通/模型匹配，不能作为正式论文第二模型记录。
- Gemini v1/v2 继续永久冻结。v3 controller/candidate/admission 尚不存在，
  formal/result authorization=false；192 个 work items 不能在 20 RPD 的单日
  内运行，下一步必须先实现 Pacific 日界的持久化 call meter 并分多日排程。
- 科学完成度保持 61%，submission readiness 56%，`F-PAPER-002=in_progress`。
  本次诊断已经结束，不得以“补 request ID”为由再次试探调用。
- 最终校验：4 个 JSON parse/hash/secret-pattern 检查通过；相关配置、budget
  和 official-provider 单测 33/33 通过（1 条已知 Pydantic warning）；
  `git diff --check` 通过。diagnostic SHA-256 为
  `644f1f3a521ee0d5ef9688a17061e244eed4236a04fc6d05a714552c282fca4f`。

## 当前移交检查点——Gemini 当前不可用于实验

- 09:25 owner 截图把根因进一步收敛：exact project `M3 PI Guard test` 显示
  Tier 1，Gemini 3.6 Flash 峰值只有 2/1000 RPM、1.35K/2M TPM、3/10K RPD。
  因此普通公开配额耗尽与 key-project 错配均不再是首要解释。
- 首要核查变为“结算”页：positive Prepay balance、Prepay/Postpay plan 和
  account status。Google 官方规则是 paid tier 仅在 positive Prepay balance
  时服务；0/depleted/negative credits 或 billing issue 会停止 key。
- Logs=0 不证明调用未到达；当前 OpenAI-compatible Chat Completions 不属于
  页面明确覆盖的全部日志 API。Batch Gemini 2 Flash 也与 3.6 Standard 无关。
- 09:15 的独立 Gemini-only 诊断完成且只尝试一次：ignored config 的 key
  非占位、`gemini-3.6-flash` 与官方 Google base URL 准入通过，但首请求返回
  HTTP 429。
- 请求使用固定合成文本、temperature 0、max tokens 16；0 retry、0 tools、
  0 external effects、0 formal results，且不保存凭据、header 或正文。
- 由于没有完成响应，不能声称返回模型精确匹配、身份链通过或当前 API 正常。
  这项诊断不修改 Gemini v1/v2，不进入 ITT/effect table，也不改变 61% 科学
  完成度。
- 同一 local config 在 7 月 23 日曾成功返回 200，之后跨天三次首请求 429；
  官方资料确认 3.6 Flash/免费 Standard/OpenAI route 均有效，限额按 project
  计算。最高优先核查是 exact key-project 是否就是截图项目，以及该项目当前
  active quota/key status/account tier；公共状态页当前没有大范围事故。
- transport 未保存 429 的 quota metric，因此目前不能区分 RPM/TPM/RPD、
  account provisioning 或 provider capacity。不要把“正文哈希存在”扩写为某个
  具体配额已耗尽。
- 下一代理不得再次试探式重试。只有在配额恢复后，才可创建全新的 prospective
  Gemini v3 candidate/admission；v1/v2 继续永久冻结。

## 当前移交检查点——2026-07-27 阶段报告已交付

- 最终 Word：
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-27.docx`，
  668,731 bytes，SHA-256
  `27b366847dcdfd1b8fa48aa5f766cb0839583d9686084f87cba45b460073e5b3`。
- 报告主结论固定为 empirical fallback：DeepSeek 480 条中 M3-full 对
  structural unsafe effect 0/36 vs 8/36，但 benign-tool TCR 6/24 vs
  12/24，且 full 对 policy-only 无安全增益；不得恢复机制/SOTA 叙事。
- 报告内容：6 张图、21 张表、20 个 Heading、11 个外部来源链接，覆盖授权
  regime、失败/ITT、Gemini 边界、99/61/56 完成度、自适应 75,000 query
  freeze、6,873 条公共 freeze、Gemini v3、盲测、统计和 8 周计划。
- 最终验证：
  - bundled Python `py_compile`：通过；
  - Ruff：通过；
  - structural QA：全部通过，21/21 表格固定几何与重复表头、6/6 图片 alt、
    real numbering、ZIP/OOXML/page geometry、hyperlinks、required markers；
  - bundled a11y：high=0、medium=0、low=0；
  - placeholder/credential pattern/tracked change/comment：0；
  - 6 张 PNG 图按 original resolution 人工检查通过。
- `render_docx.py` 因本机没有 LibreOffice/`soffice` 在打开文档前
  `WinError 2`；按 documents skill 使用结构 fallback，最终交付不得声称
  逐页 render pass，也不应报告未经渲染确认的页数。
- Gemini 最新状态：v1 VIGIL fallback 永久失败关闭；v2 192 行版本首请求
  HTTP 429 后暂停，1 diagnostic、0 formal、0 completed call、0 token、
  0 retry。两个版本均不得恢复；未来只能在配额恢复后创建 v3。
- 下一动作：先冻结论文 Results/主表/claim ledger；再实现 DeepSeek 自适应
  official bridge 与 8×50 成本 pilot；随后 AgentDojo/M3-v2 公共扩展。
  不运行 v7 后续机制迭代。科学完成度保持 61%，`F-PAPER-002=in_progress`。

## 当前移交检查点——Gemini v1 canary 已冻结、尚未调用

- Gemini fallback 计划为 264 行：216 primary + 48 authorization probes，
  仅含 structural、policy-only、full 三条件；selection 是 outcome-blind。
- candidate manifest：
  `33984e93ab9148336f2f97b0c9bf810aa508755f40e836d282ad7ad6957b7cd2`；
  canary admission：
  `88282407899b439fd164b719b30a1cae12fa3888f8f195db02083baab3949610`；
  output identity：
  `0c5e6f64b6abc296b727fd9e57bbd954fb0eed85051a29e749aca801a51785af`。
- 新增文件：`gemini_evidence_store_v1.py`、
  `gemini_fallback_controller_v1.py`、计划、budget override、qualification、
  schema、candidate、canary admission 和专项测试；Harness verify 两端已纳入
  `--verify-frozen`。
- 已执行：Gemini 专项 6/6，相关 provider/record/boundary 回归合计 33/33，
  Ruff、compile、PowerShell/Bash syntax 全过。未执行完整 Harness，未读取凭据，
  未产生 Gemini 网络调用。
- 下一步只能先完整运行
  `powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/verify.ps1
  -PythonExe F:\robot\Anaconda3\python.exe`。全绿后恰好一次执行
  `E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m
  experiments.paper_v2.gemini_fallback_controller_v1 --execute-canary`。
  canary 后先写 outcome-blind review，再冻结 continuation admission。

## 当前移交检查点——DeepSeek medium 完成，empirical fallback 已激活

- v8+v9 已完成并准入 480/480：479 formal-candidate、1 diagnostic、
  0 open、1084 official DeepSeek calls、CNY 1.8623798；无 retry、
  provider tools 或真实 external effect。
- 技术审查：
  `outputs/paper_upgrade_v2/formal_medium/deepseek/ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373/formal_result_technical_review_v6.json`；
  admission：
  `protocols/paper_upgrade_v2/admissions/deepseek_medium_combined_result_admission_v6.json`。
- 正式分析：
  `outputs/paper_upgrade_v2/formal_medium/deepseek/ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373/admitted_medium_analysis_v8.json`；
  已由单独 `--verify-analysis` 完整重建，退出码 0、stderr 0。
- mechanism gate 失败：安全点估计有利，但 benign-tool TCR −25pp 且
  full 对 policy-only 无安全增益。论文路线固定为 authorization leakage /
  uncertainty / security–utility empirical fallback，不能再从这批数据宣称
  机制独立领先。
- Harness verifier 已加入 v7/v8 amendment、准入、review、正式分析和
  `--verify-analysis`；尚需在后续实现结束后运行更新后的完整 Harness。
- 当前证据完成度 61%。下一动作：prospective 设计并冻结 Gemini 第二模型的
  fallback 核心扩展；随后执行公共扩展与防御感知自适应攻击。blind custodian
  和机构 JCR 核验仍是外部 blocker。`F-PAPER-002` 保持 `in_progress`。

## 当前移交检查点——v9 pending-only 与 combined gate v6 已冻结

- v8 在 303/480 时由一条闭合 `ProviderTransportError` 自然暂停；现有证据为
  302 formal-candidate + 1 diagnostic、177 pending、0 open、497 calls、
  CNY 1.2069394。v8 不得再次执行，诊断行不得重试或排除。
- v9 candidate/admission 已冻结，只覆盖 177 个 never-started work key：
  candidate manifest `7b006ab62f8f2c6f696373949a27c1db4b11dfae006456fadaef30a2d7a7c4b5`，
  admission manifest `2932c2d35903fd470a8a09156916e564f70cfbc24ff511abf87a4f6265aba2a3`，
  output identity
  `ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373`。
- combined result gate v6 candidate 已在 v9 API 前冻结，manifest
  `647e72663b603d91ebe19d27771ed633cc1b8696423fd082affd3f0017b4b30b`；
  480 全覆盖、0 duplicate/missing/unknown、diagnostic 留在 ITT，analysis
  admission 关闭。
- v9/v6 新增专项 8/8、Ruff、compile、PowerShell/Bash syntax、JSON parse
  通过。唯一完整 Harness 已自然结束：1081 passed、1 skipped、3 warnings，
  12 个阶段全部 PASS，`Verification failed=0`；日志位于
  `outputs/paper_upgrade_v2/verification/pre_v9_remainder_full_rerun/`。
- 下一唯一顺序：恰好一个 `--execute-pending-segment` 进程 → 若闭合
  diagnostic 则只在 outcome-blind
  技术审计后人工启动下一 pending-only segment → 177/177 后运行 gate-v6
  review/admission/analysis。

## 当前移交检查点——v8 continuation 前完整 Harness 已全绿

- 唯一完整验证进程已自然结束。命令为
  `powershell -NoProfile -ExecutionPolicy Bypass -File
  harness/scripts/verify.ps1 -PythonExe F:\robot\Anaconda3\python.exe`；
  完整 pytest 为 1073 passed、1 skipped、3 warnings，最终
  `Verification failed=0`。
- 日志位于
  `outputs/paper_upgrade_v2/verification/pre_v8_continuation_full_rerun/`。
  stderr 的三条 `RuntimeAuditor` `delete_record` 阻断是预期安全测试，
  没有删除或真实外部 effect。
- v8 仍是 6/480 terminal records、474 pending、0 open attempts；
  scientific outcomes 未读取，result/analysis admission 仍关闭。
- 下一唯一动作是恰好一次运行
  `E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m
  experiments.paper_v2.formal_matrix_controller_v8
  --execute-continuation`。不得自动重试、不得与 Gemini 并发、不得启用
  provider tools 或真实外部 effect。
- 该动作已于 15:47:08 +08:00 恰好启动一次：venv 启动器 PID 73484，
  Python 3.13.5 子进程 PID 33056。运行日志为
  `outputs/paper_upgrade_v2/verification/v8_deepseek_continuation/`；
  当前应继续监控自然完成，不得启动第二实例或并发 Gemini。
- continuation 自然结束后先执行 outcome-blind result gate v5 review；
  只有独立 result admission 通过才允许统计分析。`F-PAPER-002`
  保持 `in_progress`。

## 当前移交检查点——v8 canary 通过，阶段报告完成，续跑等待完整绿色验证

- v7 已永久中止。唯一 canary 在两个官方 DeepSeek 响应后因 lazy
  boundary-adapter binding 与 v3 evaluator 不一致而失败关闭；冻结状态为
  0 result records、1 open attempt、2 provider responses、1 trace，增量
  CNY 0.0010122。不得重试、续跑、补写或分析 v7。
- v8 run 为 `paper-v2-deepseek-medium-v8-20260726`，matrix identity 为
  `8d08cab3febccdf5a4360d208766c39cef851fa9ec8b9c15799ee30171a213bf`。
  controller 将 v3 adapter 绑定覆盖完整 `_execute` 生命周期；candidate
  manifest 为
  `340246ec336281373f49a4d062734e01afa208c6ea5a76daa9881d21ac05cf6d`。
- v8 唯一六条件 canary 已完成：6/6 `formal_candidate` records、13 official
  responses、0 diagnostics、0 operational failures、0 retries/fallbacks/
  tools/external effects；v8 增量成本 CNY 0.0077078，当前累计
  CNY 0.9153868。canary review 的
  `scientific_outcomes_reviewed=false`，不得从技术门禁推断防御效果。
- v8 continuation admission 已生成且未消费：
  `protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v8.json`，
  manifest
  `78b136fcd8766d93a7dd37081d2adbf0738bf2c5fdac556855375d9a7b75bc83`。
  当前 6 records、474 remaining、0 open；result/analysis admission 均关闭。
- result gate v5 candidate manifest：
  `73edb1f625f13f715cff475cd7d5ee9f9fe2183efc0c7cc9479b644eb1928e7f`。
  它已在 scientific-outcome access 前冻结，不能修改或绕过。
- pre-v8 完整 Harness 为 1072 passed、1 skipped、1 failed，
  `Verification failed=1`。唯一失败是过时的 v7 “output root unused”断言；
  已替换为永久 abort/no-network 不变量并专项复验 1/1 通过。更新后的完整
  Harness 尚未重跑，因此禁止立即启动 474 项。
- 阶段报告：
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-26.docx`，
  SHA-256
  `a79f3a65b75b313ec2a9bc8effc058c436d2d0671ae1f04009ad4578c379b828`。
  含 4 张图、16 张表和详细后续实验计划。OOXML/ZIP、表格几何、a11y、
  placeholder、credential-pattern、4 张图人工检查通过；本机无 LibreOffice，
  所以没有整页渲染结论。
- 下一唯一顺序：
  1. 使用 `F:\robot\Anaconda3\python.exe` 运行完整 Harness，要求最终
     `Verification failed=0`；当前 result-gate v5 nested verifier 可能需要约
     33 分钟，须使用足够长且唯一的 wrapper，不能因超时启动重复进程。
  2. 绿色后恰好一次运行
     `E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m
     experiments.paper_v2.formal_matrix_controller_v8
     --execute-continuation`。
  3. 运行结束先做身份、账本、预算、failure 和 effect-isolation 的
     outcome-blind gate review；只有独立 result admission 通过才运行分析。
  4. Gemini、公共基准、自适应攻击和盲测仍为后续阶段；不得与 DeepSeek
     continuation 并发，不得使用 provider tools 或真实危险 effect。
- `F-PAPER-002` 保持 `in_progress`。本检查点没有启动 474 项、没有查看科学
  outcome、没有生成结果准入。
- 最终只读核验命令与结果：
  - `F:\robot\Anaconda3\python.exe -m
    experiments.paper_v2.formal_matrix_controller_v8
    --continuation-status`：退出 0，状态
    `matrix_v8_status_verified_no_network`，6 records、474 remaining、
    0 open、0 status network calls、budget unpaused、result admission false。
  - `F:\robot\Anaconda3\python.exe -m json.tool
    harness/features/feature_list.json`：退出 0。
  - `git diff --check -- <本轮 Harness 状态文件>`：退出 0，仅有预期的
    LF→CRLF working-copy 提示。
  - `F:\robot\Anaconda3\python.exe -m ruff check
    scripts/build_paper_v2_stage_report_20260726.py` 与 `py_compile`：退出 0。
  - 最终 DOCX SHA-256 复验为
    `a79f3a65b75b313ec2a9bc8effc058c436d2d0671ae1f04009ad4578c379b828`。

## 当前移交检查点——阶段性报告已交付，v7 保持冻结

- 用户要求把 v7 延后，当前唯一优先级已切换为阶段报告。v7 全量离线审计约
  47% 时停止，没有完整通过/失败结论；没有 v7 API、canary、continuation 或
  正式实验记录。
- Word 报告位于
  `docs/research/paper_v2/reports/M3_PI_Guard_阶段性研究报告_2026-07-24.docx`。
  它包含 5 张图、26 张表和详细的 DeepSeek/Gemini、AgentDojo/SIREN、自适应
  攻击、独立盲测及统计路线。
- 报告的 OOXML 结构验证通过；独立预览识别 21 页、5 张图和 26 张表，代表页面
  已检查。密钥格式扫描和交付清理扫描均为 0。
- v7 candidate manifest：
  `4c3e5a8657b9bb98735ad891fb8aed8a7d71aaedf837eff695b6605fcdb271be`；
  matrix identity：
  `a34fe5b87607cb48144b0d36da282accc25d33cd18706351eb39dd25ebe04c75`。
  二者及 qualification/canary admission 均不得修改。
- 恢复实验的唯一顺序：完成全量离线审计；实现、专项测试并冻结 result gate v4；
  复核 v7 qualification/candidate/canary admission；执行一次 canary；技术 review
  通过后再写 continuation admission。不得在 result gate v4 尚未冻结时直接运行
  v7 API。
- 最近一次完成的全量 Harness 证据仍是 pre-v6 continuation rerun：
  1049 passed、1 skipped、0 verification failed。v7 只有 12/12 专项测试和 Ruff
  通过，不能声称完整审计通过。F-PAPER-002 保持 `in_progress`。

## 当前移交检查点——DeepSeek v5 正式矩阵已准入、待完整验证后启动

- v4 已在 395/480 永久冻结并由
  `formal_result_technical_review_v1.json` outcome-blind 阻断；不得续跑、重试、
  补写或分析 v4。
- v5 run 为 `paper-v2-deepseek-medium-v5-20260724`，matrix identity 为
  `62eb641043a2fc50cbaac439b047de5c433c38b20ff9c06d8ff6d92dd71f90ae`。
  boundary adapter 只把独立安全边界拒绝闭合为 no-effect ITT 终态，不改
  provider safety 或 M3 Guard 授权。
- v5 canary 已唯一执行：6 records、13 official responses、0 retry、0
  operational failure、0 diagnostic、0 external effect，累计项目成本
  CNY 0.7522526。canary review 未读 scientific outcomes。
- 用户允许继续使用 DeepSeek/Gemini，并明确历史 30 元余额不足时仍可继续；
  `provider_budget_authorization_v3.json` 将旧金额阈值降为非阻断参考。仍禁止并发
  provider、自动 retry、跨 provider fallback、工具调用和真实危险 effect。
- result-gate v2 candidate manifest：
  `edac535c528a944581175e7752bf1da3cef57f8d27c8c21f66807f0d094d5fe8`。
  它在结果访问前锁定 gate spec v2、analysis v3、v5 candidate/canary review
  与预算授权。闭合 provider/timeout diagnostic 最多允许 1%，runner failure
  必须为 0；所有终态保留在 ITT。
- continuation admission manifest：
  `d36dfb07de921f8008b082dd9d1474970d03da1d4952766ff8568a230193b8c0`。
  当前 no-network status 为 6 records、474 remaining、0 open、unpaused、
  result admission false。
- 回归证据：gate focused 8/8、v5+gate 13/13、paper-v2 259/259。Harness
  verifier 已加入 v5 continuation、canary review、budget authorization v3、
  gate/analysis v2-v3；下一动作是完整 Harness。只有 `Verification failed=0`
  后才执行一次
  `E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m
  experiments.paper_v2.formal_matrix_controller_v5 --execute-continuation`。
- continuation 运行时只监控 process、record/remaining/open、status、cost 与
  stderr；不读取 scientific outcome。结束后先跑完整验证，再写 result-gate v2
  technical review。review 通过后才写 result admission 和 analysis。
- `F-PAPER-002` 保持 `in_progress`；Gemini 第二模型、公共正式扩展、自适应攻击
  和独立 blind custodian 仍未完成。

## 当前移交检查点——DeepSeek v4 正式矩阵续跑中，科学结果仍封存

- v1 默认 thinking 截断、v2 可信上下文缺失和 v3 默认 text-format strict-JSON
  failure 均已独立冻结，禁止重试/续跑/分析。v4 使用新 run/matrix identity，
  固定 non-thinking + JSON Output，严格 parser 不变。
- v4 零网络 qualification、candidate、canary admission、6/6 技术 canary review
  和 continuation admission 均已哈希冻结。canary 为 6 records、13 official
  responses、0 operational failures、0 diagnostics，项目累计 CNY 0.0470286；
  不构成效果证据。
- 正式续跑命令为
  `E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m
  experiments.paper_v2.formal_matrix_controller_v4
  --execute-continuation`。后台父子 PID 启动链为 55444 → 31156；不得启动第二个
  continuation、Gemini 或自动 retry。进程结束前只监控 PID、账本行数、预算和
  stderr，不读科学字段。
- 预算继续使用项目累计 CNY 27 熔断；provider tools、外部 effect 和跨 provider
  fallback 均关闭。输出根为
  `outputs/paper_upgrade_v2/formal_medium/deepseek/dd794dd88eade41166bdafb7cb191898d7d19a5d8df737340f6acc3daac4504f/`。
- outcome-blind result gate 已前瞻性冻结，当前 candidate manifest 为
  `e72fad7ec1fe333153dbb10de2231df05677e262be08c25346bc029ed6a2e1e5`。
  它要求 480/480、0 open、0 operational failure、全 formal-candidate、官方精确
  身份、完整 trace、安全隔离和未暂停预算，之后仍须单独写 result admission。
- `medium_analysis_v2.py` 在主分析外预注册 ASK/确认负担、五种授权 regime、
  latency、token/cost 和 benchmark/context/source-set 异质性；UTR/DSR 因冻结
  合同没有独立标签而明确标为不可识别。
- 运行前验证为 paper-v2 231/231、完整 Harness 1002 passed、1 skipped、
  3 warnings、`Verification failed=0`。新增 result gate/analyzer 为 13/13；
  manuscript/v4 状态测试为 10/10。新增后的完整 paper-v2/Harness 尚须在正式
  续跑结束后重跑，避免 open-attempt 窗口。
- 续跑完成后的唯一顺序：确认两个 PID 均退出且 stderr/最终 stdout 正常；运行
  完整 paper-v2 和 Harness；执行 `formal_result_gate_v1 --write-review`。只有
  technical review 自动通过，才写/验证 admission，随后运行
  `--write-analysis`；否则冻结失败并保持 scientific outcomes 未准入。
- `F-PAPER-002` 保持 `in_progress`。公共正式矩阵、第二模型、自适应攻击和独立
  盲测仍未完成，不能宣称论文总体已达到 80% 或 SCI Q2 可投稿。

## 当前移交检查点——live 依赖已闭环，正式 API 身份仍失败关闭

- 六条件 live composition 已完成离线工程资格：PromptGuard 使用固定
  `Llama-Prompt-Guard-2-86M` 实际 CPU inference；AgentDojo 使用固定 commit
  `089ed468...` 的官方环境与 utility/security checker；VIGIL 使用固定 commit
  `af8eb9c...` 的官方 generator/parser，并把 generator 调用计入 16-call cap；
  M3/AgentDojo outcome evaluator 与 exact-gold oracle monitor 都在 runtime 后离线
  执行。
- 用户授权的一次性官方身份检查已完成且没有重试：DeepSeek 精确模型和 response
  ID 可核验，但 request-ID header 缺失，保留 diagnostic；Gemini 首次请求得到
  `ProviderPausedError` 后暂停。DeepSeek 本次 53 tokens、CNY 0.000207；Gemini
  没有成功结果。
- 权威脱敏证据：
  `protocols/paper_upgrade_v2/provider_live_qualification_v1.json`。它不保存 key、
  prompt/response 正文、header 或原始错误，且 `formal_results_created=0`。
  v3 preflight 绑定该 artifact，当前 blockers=2、`gate_pass=false`。
- 不得自动重试 Gemini；只有用户提供当前项目 AI Studio RPM/TPM/RPD 快照并且
  quota 状态发生实质变化后，才可讨论新的明确授权。不得把 DeepSeek response ID
  改名为 request ID 或降低双 ID schema。
- 验证：provider 聚焦 16/16、paper-v2 160/160、完整 Harness 929 collected、
  928 passed、1 skipped，392.3 秒，`Verification failed=0`。
- 当前工程/科学/投稿就绪度为 99%/32%/44%。下一研究门是 provider 身份/额度，
  不是继续写离线壳层；中型效果、公共矩阵、自适应攻击和独立盲测仍全部为 0。

## 当前移交检查点——append-only 记录路径已资格化，v3 仍有三个 live 门禁

- 新模块 `experiments/paper_v2/formal_record_store.py`，冻结资格为
  `protocols/paper_upgrade_v2/formal_record_store_qualification_v1.json`。
  experiment record 和 sanitized runtime events 同 entry 绑定；完整链在每次追加
  前复验，写入后 flush+fsync。
- 恢复路径拒绝重复/未知 work、重复 record、execution/run/work metadata drift、
  record/event/argument/entry hash drift、空白/截断/非 UTF-8 JSONL，以及 raw/
  credential 内容。completed/refusal 需要 formal-candidate；diagnostic
  operational failure 保留在 ITT。
- 零网络临时磁盘资格写入/回读 12/12 benchmark-condition entries，raw marker 0，
  临时文件清理通过。project experiment records、formal results、API/model calls
  均为 0。
- v3 preflight 已重新冻结，blockers=3：live provider/PromptGuard/VIGIL/effect/
  evaluator integrations、Gemini active quota snapshot、每家 live exact-model/
  request+response-ID qualification。`gate_pass=false`，不得启动 480 项矩阵。
- 验证：store 7/7、相关 28/28、paper-v2 127/127、Ruff/compile/JSON/syntax/
  conventions 通过；全量 899 collected、898 passed、1 skipped、3 warnings，
  Harness 546.9 秒且 `Verification failed=0`。
- 当前工程/科学/投稿就绪度为 97%/32%/43%。下一步应整合并离线资格化 live 条件
  dependencies；仍不能把基础设施完成度写成论文结果。

## 历史移交检查点——Python 3.13 项目环境和六条件壳层已验证

- 全量环境为 `F:\robot\Anaconda3\python.exe` Python 3.13.5。仓库
  core/dashboard requirements 已满足；Ruff 0.15.22 和项目兼容 Pillow 10.4.0
  安装在该解释器可见的 Python313 用户 site，因为 F 盘 base site 对当前账户
  不可写。
- openai、pandas、streamlit、pytest、Ruff、jsonschema、Pydantic、NumPy、
  SciPy、Matplotlib、NetworkX 和 Pillow 导入通过。Python 3.13 可直接运行
  `python -m ruff`；LFischl 继续只作辅助兼容环境。
- 全局 `pip check` 未通过：非项目 pdfplumber 0.11.10 与 PySSTV 0.5.8 要求
  Pillow 12.2.0，而项目侧现有 python-fx 要求 `<11`。不要未经用户同意卸载/
  降级这些工具；若未来要求全局依赖图完全干净，应建立隔离 Python 3.13 venv。
- 六条件 no-effect shell 已注册并离线覆盖 12/12 benchmark-condition pairs，
  raw prompt/response/observation 在记录边界前脱敏。它仍不是 live dependency
  或效果资格；v3 preflight 保持 `gate_pass=false`，正式结果为 0。
- 验证：Ruff pass，paper-v2 120/120；完整 Harness 892 collected、891 passed、
  1 skipped、3 warnings，529.9 秒且 `Verification failed=0`。本检查点没有
  API/model call，也没有读取密钥。
- 当前工程/科学证据/投稿就绪度仍为 96%/32%/43%。下一研究步骤是正式记录
  持久化路径和 live 条件依赖资格，不是直接放开 480 项矩阵。

## 历史移交检查点——官方 transport 已资格化，六条件正式执行仍未授权

- DeepSeek/Gemini 均保留完整 480 项目标、每模型最多 4,416 call；DeepSeek 的
  高缓存命中用于 CNY 27 动态熔断，不改变样本量。provider 之间是独立模型矩阵，
  不允许同一矩阵自动 fallback。
- 官方执行层位于 `experiments/paper_v2/official_provider_executor.py`，冻结入口为
  `experiments.paper_v2.provider_execution_gate --verify-only`。每次请求单 attempt、
  无 provider tools/外部 effect/自动 retry；429 只允许人工授权后的同 provider
  恢复。
- 收据只保留 endpoint/model/ID/hash/usage/cost，不保留 key、header 或正文。
  injected transport 映射 `local_qualification`；真实 official network 只有 exact
  model + request/response 双 ID 才能进入 `formal_candidate`，缺 request ID 固定
  为 `diagnostic_only`。
- `medium_execution_manifest_v3_preflight.json` 当前绑定完整执行身份但
  `gate_pass=false`。剩余 4 个 blocker：六条件正式 executor 未注册、正式日志脱敏
  复核未完成、Gemini 当前 RPM/TPM/RPD 快照缺失、每家 live no-effect exact-model/
  双 ID qualification 未绑定。不得启动 480 项矩阵。
- 资格测试：执行器 13/13、paper-v2 112/112、完整 Harness
  `883 passed, 1 skipped, 3 warnings`、`Verification failed=0`；本任务 API/
  model call 为 0，正式结果为 0。
- `LFischl` 是 Python 3.9，已补装 pytest，可用于 Ruff/本模块隔离测试，不能运行
  当前完整源码。完整验证环境为 `F:\robot\Anaconda3\python.exe` Python 3.13.5，
  当前项目最低版本记录为 Python 3.12+。
- 当前完成度：工程 95%、科学证据 32%、投稿 43%。`M3-PAPER-002` /
  `F-PAPER-002` 保持 `in_progress`；下一安全步骤是离线实现并资格化六条件 executor
  和日志脱敏，不是直接调用 API。

## 历史移交检查点——完整 480 项目标已锁定，动态预算门禁就绪

- 用户不接受把 DeepSeek 限定为小样本。DeepSeek `deepseek-v4-pro` 与 Gemini
  `gemini-3.6-flash` 现在均以独立完整 480 项矩阵为目标；100-call 分块只负责
  append-only resume、计费结算和止损，不改变样本量。
- 权威预算文件：
  `protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json` 与
  `dual_provider_budget_preflight_v1.json`；离线校验入口：
  `python -m experiments.paper_v2.provider_budget --verify-only`。
- DeepSeek 使用用户声明 CNY 30 余额，CNY 27 abort ceiling 和 CNY 3 reserve。
  90%/88%/85% 缓存命中对应全量保守成本约 CNY 24.662527/26.709802/
  29.780714；最低可行聚合 hit ratio 约 87.7165%。每个正式响应都必须有 cache
  hit/miss/output usage，且下一最坏请求须能放进剩余 ceiling。
- Gemini 严格 free tier、paid-tier monetary ceiling USD 0；本地 batch caps
  是附加止损而非 provider 配额声明。正式运行前需从 AI Studio 记录当前
  RPM/TPM/RPD；任何 429 暂停且不自动重试或跨供应商补跑。
- 只允许 synthetic M3/public benchmark/fixed non-sensitive instruction 出站；
  绝不发送凭据、个人/客户/受试者数据、私有账户、未发表论文正文、私有笔记或
  非公开源码。provider tools 与外部 effects 继续关闭。
- 用户预算边界已记录，但正式运行仍未授权：新 policy 尚未绑定到新的 immutable
  execution manifest，正式 executor/日志复核未完成，两次 connectivity smoke
  仍因 request ID 缺失只是 diagnostic。480 个真实 work item 均 pending。
- 当前聚焦证据：新预算 12/12、paper-v2 99/99、Ruff/compile/syntax/JSON/
  conventions 全通过；完整 Harness 为 870 passed、1 skipped、3 warnings，
  `Verification failed=0`。不得以预算可行性代替科学结果。

## 当前移交检查点——DeepSeek/Gemini 连通，正式身份门禁仍未通过

- 用户已明确授权一次最小连通性 smoke。DeepSeek 和 Gemini 各一次、无重试、
  无工具、无外部 effect；固定合成文本、每家最多 8 个输出 token。
- 两个官方 OpenAI-compatible chat-completions 端点均 HTTP 200，返回模型精确匹配
  `deepseek-v4-pro` 和 `gemini-3.6-flash`。总报告用量为 68 tokens。
- 凭据只由 smoke 子进程消费，未输出或持久化；response 文本也未持久化。
  local config 仍 ignored=true、tracked=false，tracked secret hits 为 0。
- 脱敏证据：
  `protocols/paper_upgrade_v2/provider_connectivity_smoke_v1.json`。
  两家都有 response ID，但都未观察到 HTTP request ID；精确 `SAFE` 也未在
  8-token 限制内返回。因此只可称 connectivity diagnostic，
  `formal_identity_attested=false`、`result_eligible_for_formal_tables=false`。
- 不得自动重跑或将本次 smoke 用于效果表。480 个 v2 工作项仍 pending；下一门禁
  是设计可取得 request ID 的正式身份收据、锁定用户硬成本上限并显式批准中型运行。
- `M3-PAPER-002` / `F-PAPER-002` 保持 `in_progress`。本次没有启动公共矩阵、
  自适应攻击或真实工具 effect，也没有提交、push、PR 或部署。

## 当前移交检查点——条件级 v2 账本就绪，官方 API 仍未调用

- `M3-PAPER-002` / `F-PAPER-002` 保持 `in_progress`。工程就绪 93%、科学证据
  32%、投稿就绪 41%；只有工程交付超过 80%，论文结论没有达到 80%。
- authoritative 中型账本是 `medium_execution_plan_v2.jsonl` / manifest v2。
  v1 在零结果状态被 supersede 并保留；不得把 v1 绑定的新结果纳入论文。
- 480 个 v2 工作项为 432 primary + 48 probe，全部 pending。无网络内存验证
  已覆盖 480/480，stub 记录不落盘、不进入科学分析。
- 每个 v2 item 同时保留 source projection digest 和 condition-specific initial
  digest；experiment record 再绑定 runtime visibility events。`exact_gold`
  明示 evaluator-derived 且 primary-ineligible。
- DeepSeek 官方模板：`DEEPSEEK_API_KEY`、`deepseek-v4-pro`、
  `https://api.deepseek.com`；Gemini 官方模板：`GEMINI_API_KEY`、
  `gemini-3.6-flash`、
  `https://generativelanguage.googleapis.com/v1beta/openai/`。只填写被 Git 忽略的
  `config/project.local.env`，不得把 key 发到聊天或仓库。
- provider safety policy 禁止 API 执行危险操作：外部连接/provider managed tools
  关闭，effects 仅允许 M3 sandbox/mock/example.test 或 AgentDojo 内存副本。
  非 stub 结果缺安全 receipt 即拒绝。
- 文献矩阵结构复验 34/34：22 PR、12 PP；JISA checklist 已建立。最终 DOI 元数据、
  提交日 SCIE/JCR Q2 和正式论文包仍 pending。
- 当前聚焦新增测试 18/18、standalone Ruff 通过；完整 Harness 为
  `858 passed, 1 skipped, 3 warnings in 483.60s`、`Verification failed=0`。
  未读取 `config/project.local.env`、未调用 API/Ollama/模型、未提交/push/PR/部署。

## 当前移交检查点——paper-v2 工程就绪 90%，480 项仍未运行

- `M3-PAPER-002` / `F-PAPER-002` 保持 `in_progress`；科学证据完成 32%，投稿
  就绪 39%。不能将工程就绪 90% 表述为论文完成或达到 SCI Q2 门槛。
- online-state audit 为 22/22 units、16 artifacts；20 个 unit 有官方源码，
  Task Shield 仅为披露的本地论文复现。独立第二复核为 0，领域 oracle claim 禁用。
- 72-case 中型计划仍为 432 primary + 48 regime probe = 480 个 pending。
  `medium_execution_manifest_v1.json` 绑定关键输入哈希并提供 append-only resume、
  identity-drift、duplicate-terminal、ITT failure 和 spend-abort 契约。
- 当前候选是未批准的 OpenAI official API / `gpt-5.6-terra`。保守上界：
  4,416 calls、34,407,984 input tokens、2,260,992 output tokens、
  USD 119.93484。没有 hard spend limit，runtime model/ID 未 attested，
  logging redaction 未复核，因此 `gate_pass=false`。
- 若要启动一次正式 smoke，必须由用户明确批准 provider 和硬 USD 上限，并由
  操作者通过安全环境提供凭据；不得把凭据写入仓库或发送给 attestation 工具。
  receipt 只接收去内容 metadata，验证 official endpoint、model、request/response
  IDs 和 usage。
- 尚未调用 API/Ollama/模型，480 项没有结果；公共 6,873 计划、自适应攻击、
  600-case 独立盲测内容/保管人和论文 Results/Discussion 均未完成。
- 聚焦 provider/cost/ledger/medium 测试 20/20、全部 paper-v2 测试 69/69，
  Ruff 通过。增强后的完整 Harness 已将 provider preflight 和 480 项 execution
  manifest 纳入验证，结果为 `840 passed, 1 skipped, 3 warnings in 335.50s`、
  `Verification failed=0`。
- 工作树有大量用户/历史改动；禁止 reset/clean/批量暂存。未提交、push、PR、
  部署或访问 `config/project.local.env`。

## 当前移交检查点——paper-v2 工程就绪 85%，科学证据 31%

- 当前任务 `M3-PAPER-002` / 功能 `F-PAPER-002` 保持 `in_progress`。本轮完成的是
  可执行研究基础，不是论文效果结论；投稿就绪度为 38%。
- 20/22 个 online-state audit unit 已完成，覆盖 14 个官方固定 commit，全部证据
  manifest 可复验。结果不支持领域级 oracle 问题主张，且第二复核为 0；使用中性
  工作标题，不得写 first/only/SOTA。
- 72 个结果盲中型 case 已固定：36 attack、24 benign tool、12 benign no-tool，
  25 个 context-dependent。6 条件主矩阵 432 条 + 48 条 regime probe = 480 条
  真实记录待执行。
- `medium_falsification_gate_v2.json` 只缺可审计 provider/model 身份和硬成本上限。
  项目作者应先填写不含密钥的 `provider_cost_gate_template_v1.json`；未通过该门禁
  前不得启动收费 API。
- VIGIL/DRIFT adapter 只通过零调用资格检查；没有 formal result/admission。
  分析器实现 Wilson、exact McNemar、10,000 次 cluster bootstrap、Holm、功效和
  ITT，空结果只返回 `results_pending`。
- 公共基准固定计划为 6,873 条 case-condition 记录；AgentDojo 只有 97 个唯一良性
  任务，禁止复制凑数。自适应上限 75,000 queries。独立盲测包只有 600 个空 slot，
  custodian/candidate 均为空。
- Methods、pending-only Results、claim ledger 和 Devil's Advocate 审查已经就绪；
  真实结果未生成，不能写效果、泛化、自适应鲁棒或独立盲测结论。
- 首轮完整 Harness 为 `824 passed, 1 skipped, 3 warnings in 262.94s`；
  状态同步后的完整复验为 `825 passed, 1 skipped, 3 warnings in 247.29s`，
  `Verification failed=0`。
- 未读取本地 Token，未启动 API/Ollama/模型，未提交、推送、创建 PR 或部署。
  工作树包含大量用户/历史改动，禁止 reset/clean/批量暂存。

## 历史移交检查点——paper-v2 工程基础已验证，研究结果尚未开始

- 当前任务为 `M3-PAPER-002`，功能 `F-PAPER-002` 保持 `in_progress`。
- 已完成 34 项前沿文献矩阵、直接竞争边界、22 个 online-state audit unit 登记、
  paper-v2 实验记录/在线投影/provider attestation/ITT 指标契约、未来结果预注册和
  中型证伪 gate。入口见 `harness/tasks/m3-paper-v2.md` 与
  `protocols/paper_upgrade_v2/`。
- 实际源码审计 completed=0，所以不得声称外部领域普遍存在 oracle authorization。
- 中型 gate 为 `blocked_inputs_not_frozen` / `start_authorized=false`：尚缺固定的
  60–80 case、VIGIL/DRIFT 忠实适配、正式模型身份和成本上限。
- 历史 6 项身份回归现在验证旧 freeze 对共享 helper/保护哈希漂移 fail-closed；
  旧 freeze、旧预检和旧输出均未修改。E17 13 项单测使用离线环境快照，不再探测
  Ollama。
- 最终验证：`796 passed, 1 skipped, 2 warnings`；规范 12/12、JSON、编译、Ruff、
  Registry 18/18 和历史证据通过；最终 Harness `Verification failed=0`。
- 第一次 Harness 重跑因 Windows PowerShell 5.1 中文路径误解码只失败在 Harness
  文件存在性检查；已用 ASCII 源码内 Unicode 码点构造修复并完整重跑通过。
- 未读取 `config/project.local.env`，未启动 API、Ollama 或正式实验，未提交、推送、
  创建 PR 或部署。下一步先完成至少 20 个源码审计单元，再冻结中型实验输入。

## 当前移交检查点——服务已停止，无实验运行

当前人工可读移交来源是 `docs/项目移交报告.md`，Harness 专用地图是
`harness/项目上下文.md`。使用下方历史时间线前必须先阅读这两份文件。

- 最终判断：可以把当前完整工作目录移交给下一位维护者；不能只提供 Git 分支名。
  工作树含 42 条已跟踪改动和 149 条未跟踪项，HEAD 不包含这些当前材料。
- 接手方不得执行 `git reset --hard`、`git clean` 或批量暂存；应先保存目录副本，
  再按移交报告核对来源、冻结边界和未跟踪结果。
- `config/project.local.env` 不进入移交材料；接手方使用
  `config/project.env.example` 创建自己的本地配置。模型和运行环境按机器依赖单独
  重建或迁移。
- 当前项目专用文档已使用中文文件名和中文正文。标准机器入口、协议字段、命令和
  冻结证据仍保留稳定英文标识；不得为了继续中文化而批量重命名这些契约文件。
- 中文命名与引用审计 12/12 通过，仓库布局测试 10/10 通过。服务状态没有变化：
  `netstat` 未发现 11434 端口记录，限定进程检查未发现 Ollama/Python 匹配进程，
  Ollama 和项目模型任务仍处于停止状态。较重的 CIM 端口/命令行查询曾超时，
  未执行任何终止动作。
- 审计时分支/提交：`test1` / `d74cef2739551591a49c722c5c6273bac6edf91e`。
  工作树有意保留既有改动和未跟踪结果证据；不得重置、清理或批量暂存。
- Q2 就绪度仍为原始分 66.0、封顶分 60.0，80/90 分目标均未满足。可用于正式实验
  的强基线仍只有 ToolFilter 和 PromptGuard（2/5）；公共矩阵 0/84、独立盲测
  0/600、API 厂商 0/2，自适应正式实验未完成。
- Task Shield 路线已关闭。Progent v1.4 未通过 P3 延迟门禁。CaMeL v3 P3 完成
  8/8，但 ASR 0/4、正常任务 TCR 0/4，因此只能作为诊断证据，不能直接扩到 726 条。
- Ollama 进程 29728/30124 已停止，11434 端口已关闭，没有有意运行的项目 Python、
  Docker、Streamlit 或 Uvicorn 任务。只有在重新核对冻结、门禁和资源身份后才能
  启动服务。
- 已被替代且未冻结的 Markdown 位于 `docs/archive/`；冻结证据和历史哈希不变。
  被历史记录引用的研究路径保留重定向页。
- 规划器的首个安全动作是只读复核 CaMeL v3 P3，并重新决定 P4/P5 或
  IPIGuard/FIDES。建议先用强模型完成 40–80 个成对任务的 M3 安全—效用比较门禁，
  再考虑投入 74,760 条公共矩阵。
- 未提交、推送、创建 PR，也未制作 PPT、DOCX 或 ZIP。规范审计 12/12、布局
  10/10、注册表、历史证据、compileall、Ruff 和 diff 检查通过。完整 Harness
  尚未全绿：分组 pytest 为 752 通过、6 失败、1 跳过；13 个 E17 复核测试因
  Ollama 已停止后的快照等待而未完成。六个失败是旧基线身份漂移，详见
  `docs/项目移交报告.md` 14.1 节和 `state/failure-log.md`；不得用更早的
  724 项通过检查点替换当前事实。

## Current live checkpoint — Q2 80% not reached

Progent v1.4 has reached a terminal failed P3 gate boundary:

- v1.4 preserves the v1.3 AgentDojo client-object deduplication repair and adds
  hash-bound policy-output contract validation.
- Progent v1.4 freeze passed 21/21 at
  `protocols/paper_upgrade_v1/progent_source_backed_formal_freeze_v14.json`.
- G1 zero-model correctness passed 15/15 at
  `protocols/paper_upgrade_v1/execution/progent_v14_p2_correctness_v1/gate_g1.json`.
- Fresh P3 retained all 8 terminal rows with zero missing rows and zero
  operational failures.
- P3 results: observed ASR 0/4, full-denominator ASR bounds 0% to 0%,
  utility-row success 3/4, first policy contract success 8/8, total model
  requests 81 and policy update errors 0.
- G2 failed 11/12 at
  `outputs/paper_upgrade_v1/analysis_v2/progent_source_backed_v14_p3/gate.json`.
  The only failed check was p95 latency <=5x matched ToolFilter: Progent p95
  460,866 ms versus ToolFilter p95 41,643 ms, ratio 11.07x.
- P4/P5/P6 and registry admission are blocked for v1.4. Do not expand from or
  patch the v1.4 P3 root.
- Failure review:
  `protocols/paper_upgrade_v1/execution/progent_v14_p3_gate_failure_review_v1.md`.
- Current read-only planner marks Progent v1.4 as
  `failed_p3_qualification_gate_preserved_negative_evidence` and selects
  `qualify_camel_or_fides` as the next safe strong-baseline action.

Latest audited readiness remains:

- `raw_score=66.0`
- `capped_score=60.0`
- `goal_80_met=false`
- `goal_90_met=false`

## Previous checkpoint — Task Shield v1.6

Task Shield v1.6 has reached its terminal authorized boundary:

- G0 15/15, G1 20/20, freeze 21/21 and G2 11/11 passed.
- Fresh P3 completed 4/4. Fresh P4 retained 12 terminal rows: 9 completed,
  3 `case_timeout`, 0 missing. Standalone utility was 2/6 and attack-condition
  utility 0/6.
- G3 failed 12/16. p95 latency was 600.070 seconds, 15.175 times matched
  ToolFilter; verifier work consumed 78.92% of total case time.
- Attack evidence is 0/5 completed rows plus one unresolved timeout. It must not
  be reported as formal 0/6 or as an advantage over ToolFilter, which already
  had raw targeted-injection success 0/6 on the matched attack rows.
- P5/P6, selective retry, result admission and Q2 score increase are blocked.
  The route-control record is
  `protocols/paper_upgrade_v1/execution/taskshield_v16_post_g3_decision_v1/decision.json`.
- The current read-only planner reports `resource_gate=free` and selects
  `qualify_progent` as the next safe strong-baseline action. It does not start
  the model automatically.
- Detailed report: `docs/research/taskshield_v16_failure_analysis.md`.
- Post-hoc analysis and figures:
  `outputs/paper_upgrade_v1/analysis_v2/taskshield_v16_qualification/`.
- No Ollama, project Python or competing model workload is live.
- Final Harness verification passed: 724 tests passed, 1 skipped,
  `Verification failed=0`; conventions 12/12, registry and historical evidence
  verification passed. The Ollama process tree was stopped after validation.

Latest audited readiness remains:

- `raw_score=66.0`
- `capped_score=60.0`
- `goal_80_met=false`
- `goal_90_met=false`

The remaining hard caps are the independent 600-case blind, two frontier API
vendors, formal adaptive-budget evidence, the public benchmark matrix, and at
least five formally ready source-backed strong baselines.

### Superseded pre-execution checkpoint

The following material records the state before v1.6 execution and is retained
for provenance. It must not override the current checkpoint above.

The project was still not Q2-80 ready. Latest audited readiness:

- `raw_score=66.0`
- `capped_score=60.0`
- `goal_80_met=false`
- `goal_90_met=false`

Why it is still capped:

- Independent confirmatory blind evidence is missing.
- Two frontier API vendor model slots are missing.
- Formal adaptive query-budget evidence is missing.
- Public benchmark matrix is still incomplete.
- Fewer than five source-backed strong baselines are formally admitted.

New P0 evidence-integrity gate:

- Pinned AgentDojo uses attack-case `security=true` as targeted injection
  success. The shared adapter derived `attack_success=not security`.
- Task Shield v1.5 corrected raw Targeted ASR is 0/6, not stored 6/6; utility is
  still 1/6 and attack-condition utility 0/6.
- ToolFilter raw traces contain 7/629 targeted injection successes, not the old
  derived 622/629. Its raw run remains complete, but effect analysis/admission
  interpretation is provisional until a non-mutating analysis-v2 correction.
- Task Shield v1.6 is now approved under staged gates. Start only the zero-model
  metric-semantics correction and impact audit; no model phase may bypass G0/G1.
- Detailed report: `docs/research/taskshield_v15_failure_analysis.md`.
- Approved execution plan: `docs/research/taskshield_v16_execution_plan.md`.

Pre-v1.6 environment state:

- Ollama PID 32748 was the only attributable live process and has been stopped;
  port 11434 is not listening. No project Python process or Docker workload is
  live.
- 109 reproducible cache directories / 961 files / approximately 13.17 MiB were
  removed with protected prefixes excluded; the final unprotected cache count
  is zero.
- The structured cleanup and authorization record is under
  `protocols/paper_upgrade_v1/execution/taskshield_v16_preparation_v1/`.
- No model/API call, output root, registry write or Q2 score mutation occurred.

Current live workload / failure gate:

- No Task Shield or competing model workload is live. PID 9804 is not alive and
  the current resource gate is `free`.
- v1.3 remains sealed at 42 completed, 1 failed and 683 missing. It is historical
  failed-root evidence only.
- v1.4 remains sealed at 24 completed, 2 failed and 700 missing. Its external
  seal verifies 56 files, 1,385,631 bytes and inventory SHA-256
  `9a6d9fde53ba80ce83326018563689071cf454dffacd97133ea3cb8e0e76f453`.
- v1.5 failure-mode audit passed 8/8 and its separate freeze passed 19/19. The
  freeze authorized only the exact fresh 12-case expanded qualification.
- v1.5 qualification status is `completed_failed_qualification_analysis`: 11
  completed, 1 failed, 0 missing; utility success 1/6; stored legacy
  `attack_success=6/6` is corrected to raw Targeted ASR 0/6; latency p50
  221.037553 s, p95 975.990048 s and max 1619.386955 s.
- The failed case is `agentdojo:v1:slack:user_task_18`, `APITimeoutError`. An
  exhausted untrusted assistant timeout escaped fail-closed suppression, and
  the failed outcome did not persist `taskshield_trace`.
- v1.4/v1.5 are both ineligible. No failed row was retried or excluded, and no
  v1.5 726-case run was authorized. v1.6 engineering is now approved, but no
  v1.6 model run or output root exists yet.

Current control-plane action:

- Execute P0 from `docs/research/taskshield_v16_execution_plan.md`: build a
  non-mutating AgentDojo metric-semantics correction layer and impact audit.
- After G0, implement new v1.6 runtime/runner/freeze/analyzer files and the 18
  deterministic fixtures. Do not edit hash-bound v1.3-v1.5 files.
- P3/P4 remain gate-controlled and were not run in this checkpoint. P5 needs a
  post-G3 checkpoint; P6 726-case formal still requires explicit authorization.
- Never resume v1.4, edit/resume/selectively retry v1.5, or change registry/Q2
  status from plan, qualification, diagnostic or partial evidence.

Validation state at handoff:

- Focused v1.4 seal, v1.5 audit/runtime/analysis, Q2 planner and layout
  regression: 46/46 passed.
- Full Harness: 691 passed / 1 skipped, `Verification failed=0`.
- Project conventions: 12/12; Ruff, compileall, JSON contracts, shell and
  PowerShell syntax, experiment registry and historical evidence all pass.
- Q2 readiness remains raw 66.0 / capped 60.0, 2/5 formal-ready strong
  baselines, `goal_80_met=false` and `goal_90_met=false`.
- The earlier standalone full-pytest attempt exceeded its 5-minute wrapper
  limit and is not counted; the complete Harness rerun then finished normally
  in 352.4 seconds and is the authoritative full-suite result.

Latest completed non-GPU work:

- Task Shield v1.3 failed-root gate and Q2 fail-closed planner update:
  refreshed monitor/status artifacts now report
  `running_with_failures_requires_attention` with 1 `APITimeoutError` failed
  row; non-frozen docs, registries, source audit, dependency snapshot,
  formal-readiness audit, Q2 readiness and Q2-to-80 action audit all preserve
  the root as ineligible. Next safe action is
  `review_failed_formal_workload`; no retry/exclusion/admission/kill occurred.
  Validation passed for conventions 12/12, focused Q2/action/external/layout
  22/22, public-adapter/TaskShield/Q2 117/117, Ruff, compileall, registry and
  historical evidence. Full Harness verifier timed out at 180 seconds and is not
  counted as passing.
- Configuration handoff and local-root path cleanup:
  active Harness analysis notes no longer hard-code the local checkout root, and
  `config/README.md` now documents the exact Frontier API Q2-slot procedure:
  credentials stay in ignored `config/project.local.env`, plan-only smoke comes
  before `--execute`, network smoke requires
  `M3_FRONTIER_API_CONSENT=yes_for_network_smoke`, and registry admission uses
  only the redacted smoke manifest. The latest Frontier audit is still
  `blocked_missing_or_unsafe_local_config` with 0/2 configured vendors; no API
  calls or registry writes occurred.
- PromptGuard detector-adapter preflight portability hardening:
  `promptguard_detector_adapter_preflight_v1` now writes repo-local registry,
  real-smoke and generated artifact paths relatively when regenerated with the
  dedicated PromptGuard runtime. It preserves
  `real_detector_smoke_completed_formal_run_pending`, keeps the real-smoke and
  stub-smoke boundaries, and remains `result_eligible_for_formal_tables=false`.
  Do not regenerate this preflight with the default Python if the goal is to
  preserve the PromptGuard dependency-ready status; use the dedicated runtime.
- CaMeL official source-smoke portability hardening:
  `camel_official_source_smoke_v1` now writes repo-local preflight, registry,
  checkout, required-source and generated artifact paths relatively, remains
  8/8 `completed_source_smoke_only`, keeps `network_calls_performed=false`, and
  stays `result_eligible_for_formal_tables=false`. Downstream dependency,
  formal-readiness and Q2 audits were refreshed with no score increase.
- Progent official source-smoke portability hardening:
  `progent_official_source_smoke_v1` now writes repo-local registry, checkout,
  license-candidate and generated artifact paths relatively, remains
  `completed_source_smoke_only`, keeps the missing top-level license warning,
  and stays `result_eligible_for_formal_tables=false`. Downstream dependency,
  formal-readiness and Q2 audits were refreshed with no score increase.
- IPIGuard official source-smoke portability hardening:
  `ipiguard_official_source_smoke_v1` now writes repo-local preflight, checkout
  and source-file paths relatively, remains 8/8 source-smoke-only and
  `result_eligible_for_formal_tables=false`. Downstream dependency,
  formal-readiness and Q2 audits were refreshed with no score increase.
- Public benchmark pending-ledger portability hardening:
  `prepare_public_benchmark_formal_runs.py` now writes repo-local paths
  relatively. v1 and v2 ledgers were force-rewritten only because every cell was
  still `pending`; v1 remains 60 pending cells / 53,400 case-runs and v2 remains
  84 pending cells / 74,760 case-runs. Completeness gates remain
  `not_satisfied` with 0 complete case-runs.
- Strong-baseline portability hardening:
  `agentdojo_official_strong_baseline_capability_audit_v1` and
  `strong_baseline_source_checkout_manifest_v1` now render repo-local references
  relatively and are covered by the convention audit. The dependency snapshot,
  strong-baseline readiness audit and Q2 audit were refreshed without promoting
  any non-formal evidence.
- Frontier API active artifacts were made more portable. The plan-only smoke
  manifest and offline registry-admission artifact now use repository-relative
  paths for repo-local references. They remain blocked/non-formal: 0 network
  calls, 0/2 configured vendors, `blocked_smoke_not_qualified`, and no v3
  registry candidate.
- The independent blind authoring kit was regenerated with package-local
  relative artifact paths and now includes `validate_candidate_before_release.py`
  for independent authors/custodians.
- This kit remains content-free and non-result: it creates 0 candidate cases and
  cannot satisfy the Q2 blind gate by itself.
- `m3_v2_independent_blind_admission_audit_v2` remains
  `blocked_missing_candidate`.
- Frontier API audit remains `blocked_missing_or_unsafe_local_config` with 0/2
  configured vendors, 0 registered vendors, no explicit network-smoke consent and
  no network calls.
- README, product spec, decision log and project overview now show the current
  audited Q2 state as raw 66.0 / capped 60.0 with both 80 and 90 goals unmet.
- Boundary: active Task Shield v1.3 raw outcomes still contain runner-emitted
  `official_trace_path` absolute values. Do not rewrite these in-place while the
  formal root is running; fully relative raw outcome rows would require a future
  explicit new freeze/run revision.

Latest verification:

- PromptGuard preflight portability checkpoint: PromptGuard/Q2/layout
  regression 26/26 passed; conventions audit 12/12; Ruff naming lint and
  py_compile passed; regenerated PromptGuard preflight artifacts have no
  checkout-absolute hits.
- CaMeL source-smoke portability checkpoint: CaMeL/Q2/layout regression 23/23
  passed; conventions audit 12/12; Ruff naming lint and py_compile passed;
  regenerated CaMeL source-smoke artifacts have no checkout-absolute hits.
- Progent source-smoke portability checkpoint: Progent/Q2/layout regression
  27/27 passed; conventions audit 12/12; Ruff naming lint and py_compile passed;
  regenerated Progent artifacts have no checkout-absolute hits.
- Independent blind authoring-kit tests: 3/3 passed.
- Frontier client/admission tests: 11/11 passed.
- Focused Q2/frontier/layout regression: 39/39 passed.
- Additional focused regression after the current-status documentation refresh:
  56/56 passed.
- Strong-baseline portability checkpoint: focused layout/Q2/external-baseline
  regression 24/24 passed; regenerated capability/source-checkout/dependency/
  readiness/Q2 artifacts have no checkout-absolute hits in the refreshed active
  set.
- Public pending-ledger portability checkpoint: public-adapter/worker/Q2/layout
  regression 118/118 passed; conventions audit 12/12; active public artifacts
  checkout-path scan clean; feature JSON parses.
- IPIGuard source-smoke portability checkpoint: IPIGuard/Q2/layout regression
  29/29 passed; conventions audit 12/12; Ruff naming lint and py_compile passed;
  refreshed downstream path scan clean.
- Ruff naming lint and compileall passed for the changed authoring-kit files.
- Ruff naming lint and compileall passed for the changed Frontier files.
- `python scripts/audit_project_conventions.py --check`: 12/12 PASS.
- Checkout-absolute scan over refreshed blind/frontier/Q2 active artifacts found
  no current-checkout absolute path hits.
- `git diff --check`: no whitespace errors, only existing CRLF warnings.
- A full `harness/scripts/verify.ps1` attempt timed out at 5 minutes and is not
  counted as passing; no verification child process remained afterward.

## Active Paper-v1 Continuation

M3-PAPER-001 正在进行论文升级实现；这一路径保留 E0-E17 与 Acceptance Remediation V2 为历史基线，但不把它们冒充新的确认性 blind 或公共基准正式结果。

当前最新 paper-v1 状态：

- 项目完整综述与保守兼容整理已落盘：`docs/PROJECT_OVERVIEW.md` 是当前中文总览，
  `docs/README.md` 是文档索引，`scripts/audit_project_conventions.py --check`
  已接入 Harness。四个允许移动的非冻结文件已规范化，稳定接口、历史证据、运行中
  ToolFilter 与本地秘密均未改变。当前布局审计 12/12、repository-layout tests 9/9；
  新增 gate 禁止活跃非冻结文件写死 checkout 绝对路径，仓库外依赖仍从 local 配置取得。
  完整 pytest/Harness 验证必须等当前 ToolFilter 不再写入后再运行；此门禁关闭前任务状态为
  `in_progress_verification_gated`，不能误记为最终验证完成。

- 旧 ToolFilter PID 36472 在 483/726 completed、0 failed 时消失，manifest 没有终态；
  read-only monitor 判为 `stopped_without_terminal_manifest`。已用同一 freeze、同一 output
  root、默认 resume 和 `--admit-formal` 启动 PID 18904；没有 `--retry-failed`，已有完成行
  保留。必须等 726/726、0 failed、formal analysis 和 admission bridge 全部通过后才能加分。

- Confirmatory preregistration 已在新 blind/adaptive formal evidence 之前冻结：
  `protocols/paper_upgrade_v1/paper_v1_confirmatory_preregistration_freeze_v1.json/.md`
  为 9/9 checks passed，payload SHA-256
  `b4b747196274e877c4b2bd0e5bbdebdcc582d585c714263815a8e4956f6b742a`。
  Q2 reproducibility gate 已要求该证据，但总体仍为 raw 63.5、capped 60.0。
- `camel_or_fides` readiness 已修复为只准入 frozen selected CaMeL，并强制 FIDES
  保持未选择/不可进入结果；统一 external baseline admission bridge 已覆盖 Task Shield、
  IPIGuard、Progent、CaMeL。当前四份 admission audit 都因正式 run/analysis 缺失而
  `blocked_not_formally_admitted`，未改写 registry。
- Adaptive MCTS 正式监控器已实现并保持只读；正式 root 尚未启动，当前
  `missing_manifest`。必须等现有 tool_filter 释放 Ollama/GPU 后再做 real qualification。
- Active AgentDojo `tool_filter` 在 2026-07-22 11:25+08:00 的只读快照为
  526/726 completed、0 failed、200 missing，恢复进程 PID 18904 alive。当前已进入
  workspace security cases，近期约每案 60 秒；权威实时值读取
  `protocols/paper_upgrade_v1/monitors/tool_filter_formal_v1/agentdojo_official_formal_run_monitor_v1.json`。
  完成前不要启动其他 Ollama/GPU 正式任务。
- `plan_q2_formal_execution.py` 已把 monitor/admission/public queue 汇总为只读
  handoff artifact；当前 `resource_gate=busy`，唯一下一动作是刷新 ToolFilter
  monitor。它确认 public-v2 仍为 84 pending cells / 74,760 case-runs，且不会
  自动启动、retry、分析或准入结果。
- 公共基准完整性审计已重新生成，84 个 cell 的仓库内路径均为相对路径；当前仍是
  0/74,760 formal case-runs、`result_completeness_gate=not_satisfied`。最新 ToolFilter
  快照为 568/726 completed、0 failed、158 missing，PID 18904 alive；不得把该 partial
  状态写入正式表，也不得在它结束前启动其他 Ollama/GPU workload。
- 独立 blind 的预注册 v1 audit 保持原哈希；今后的候选使用 v2 audit，正式结果经
  `admit_independent_blind_formal_result.py` 核验后只写入
  `paper_v1_evidence_index_v1.json`。当前 candidate/run 均缺失，plan-only admission
  正确 blocked，index 未写入，历史 `final_analysis` 未修改。
- 动态 ToolFilter monitor、Q2 readiness 和 execution-plan artifact 的仓库内路径已改为
  相对路径；Q2 audit 新增 `goal_80_met=false` 中间里程碑但没有放宽 90 分目标或硬 cap。
  execution planner 已内置四个外部强基线的 fresh two-case qualification 命令，固定
  utility + security 两案且不含 `--admit-formal`。
- 不读取动态结果分母的全仓命名 lint、`compileall`、conventions 12/12 和
  `git diff --check` 已通过；会扫描 registry/结果完整性的全量 pytest 与 Harness verifier
  继续等 ToolFilter 终态后执行。
- Q2/monitor/planner/analyzer/admission 的路径展示已统一到 shared
  `portable_path/portable_value`。对当前 partial ToolFilter root 的无写入 admission 演练保留
  11 个 blocker、`result_eligible=false`，且 baseline registry SHA-256 前后完全一致；四个
  external strong-baseline admission artifact 也仅刷新为 blocked plan-only 状态。
- 四个 external analyzer 属于 freeze `local_adapter.files` 哈希身份，不能原位改路径。
  一次路径清理尝试被六个 freeze-identity 测试正确拒绝后已完全撤回；复跑 32/32 PASS。
  conventions audit 现在会自动发现、排除并逐一校验 21 个此类隐式冻结文件的 SHA-256，
  layout tests 为 8/8，identity gate 12/12 PASS。
- 整理后的历史验证再次通过：E0-E17 registry 18/0/0/0，V2、E11 r2 与
  context/E17 r3 freeze hash 未变。动态 strong-baseline readiness audit 已重建为仓库相对
  路径，checkout absolute hits=0，7/7 checks 通过但 formal-ready 仍只有 PromptGuard。
- IPIGuard v1.1 freeze 已更新为 9/9，并 hash-bind runner/analyzer/protocol；runner
  仅捕获 raw construct JSON 后委托 unchanged upstream parser，同时在 Ollama probe
  前拒绝旧 freeze/root 的 resume identity drift。import preflight 7/7。原 v1 1/2
  qualification 保留，fresh v1.1 2-case requalification 必须在 ToolFilter 结束后用
  新输出目录执行。
- Progent v1.1 已从 12/12 freeze、9/9 import preflight 升级为 hash-bound formal
  adapter 准备：`progent_source_backed_formal_protocol_v1.md` 已加入 freeze；schema
  1.1 freeze 13/13，network-free import preflight 10/10，runner 在 Ollama probe 前
  拒绝 freeze/root/model/selection identity drift。它仍没有 real-model qualification
  或 726-case formal logs，不能计入正式强基线。
- Task Shield 已升级为 v1.2 disclosed paper reproduction：没有 public official
  repository 声明；`taskshield_paper_formal_freeze_v1` 为
  `paper-taskshield-reproduction-freeze-1.2`，13/13 checks，hash-binds runtime、
  import preflight、runner、analyzer、protocol 和 shared resume identity helper；
  `taskshield_paper_import_preflight_v1` 为 9/9 checks。它仍没有 real-model
  qualification、726-case logs 或 admitted analysis，不能计入正式强基线，也不能
  称为 official-source Task Shield。
- CaMeL 已从 schema 1.1 升级到 v1.2 hash-bound formal adapter 准备：
  `camel_source_backed_formal_freeze_v1.json` 为
  `paper-camel-source-backed-formal-freeze-1.2`，17/17 checks；freeze
  hash-binds local adapter files，runner 在 Ollama probe 前拒绝 freeze/root/model/
  condition/selection identity drift。CaMeL 仍没有 two-case real-model
  qualification、726-case logs 或 admitted analysis，不能计入正式强基线。

- Q2 readiness 审计已收紧 independent blind 与 monitor 两条证据链：
  - `m3_v2_independent_blind_manifest` 不能仅凭 final manifest 字段存在得分；必须通过独立 candidate admission、formal/eligible 600-case manifest、candidate SHA-256 匹配、independent-blind scope 和非 post-hoc 检查。当前 candidate 不存在，仍 `blocked_missing_candidate`。
  - transformers detector monitor 现在优先选择与 selected run manifest 匹配的 monitor。匹配文件为
    `protocols/paper_upgrade_v1/monitors/transformers_pi_detector_formal_v2/agentdojo_official_formal_run_monitor_v1.json`；它显示 75/726 completed、1 failed、650 missing、PID 不存在。旧 generic monitor 不再能让 stale detector root 看起来健康。
  - `q2_readiness_audit_v1` 最新仍为 raw 63.5/100、capped 60.0/100、goal_90_met=false。
- AgentDojo exact official `transformers_pi_detector` 当前失败点已定位：`agentdojo:v1:workspace:user_task_25` 在官方 HF text-classification detector pipeline 内 CPU OOM，尝试分配 2,185,056,432 bytes。不要复跑旧 `agentdojo_transformers_pi_detector_official_formal_v2_cpu_detector` root；若要继续 detector-style baseline，只能另行冻结并披露非等价 bounded/windowed adapter，或在更大资源机器上先让 preserved direct long-output smoke 通过。
- Failure diagnostic artifact 已生成：
  `protocols/paper_upgrade_v1/diagnostics/agentdojo_transformers_detector_failure_v1/failure_diagnostic.json/.md`。
  该 artifact 只读 retained rows，分类为 `resource_cpu_memory`，记录 76 outcomes / 1 failed 和 stderr hashes，仍 `result_eligible_for_formal_tables=false`。
- CaMeL/FIDES：CaMeL 已有隔离 E-drive runtime（Python 3.10.12，依赖由
  `E:\M3_PI_Guard_runtime\camel_bootstrap` 的 `uv` 同步到
  `E:\M3_PI_Guard_runtime\camel\.venv`，缓存 `E:\AI_Cache\uv`）。旧的
  fresh-process import preflight 仍记录官方 AgentDojo suite import-order
  failure；新增 source-backed compat preflight 通过 8/8 checks，在不修改
  site-packages/官方源码、不联网、不启动模型/API 的前提下预加载官方 suite
  modules，使 CaMeL/AgentDojo 关键 imports 可通过。新增 source-backed
  runner-wiring preflight 通过 14/14 checks，可在 0 benchmark case、0
  model/API call、0 network 的边界内为四个 suite 构建官方
  `PrivilegedLLM` + suite security policy pipeline 骨架。新增 transport/capability
  mapping preflight 通过 16/16 checks，冻结 loopback privileged/quarantined
  transport、四个 suite 的 trusted/untrusted capability mapping、0 case、0
  model/API call、0 network 边界。CaMeL formal freeze 已更新为
  `completed_frozen_formal_protocol`，schema `paper-camel-source-backed-formal-freeze-1.2`，
  17/17 checks，并 hash-bind local adapter files plus resume identity gate。当前
  blocker 收敛为 two-case real-model qualification、726-case complete logs /
  formal admission，不能计入正式表。
- AgentDojo `tool_filter` active long run: PID 36472，root
  `outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1`。
  最新 read-only monitor 为 `running_progressing`、433/726 completed、0 failed、
  293 missing。不要启动其他 Ollama/GPU formal
  job；未完成和 analyzer admission 前不得入表。
- `admit_agentdojo_tool_filter_formal_result.py` 已实现为完成后的 admission
  bridge：它只刷新 monitor，并在 run=`completed_formal`、monitor=`completed_formal_admitted`
  和 analysis=`completed_formal_analysis` 同时成立时才可用 `--write-registry`
  更新 `baseline_registry.json`。当前运行一次按设计阻断，status
  `blocked_not_formally_admitted`，未改 registry。
- `audit_q2_readiness.py` 已修复 stale monitor 归因：旧
  `transformers_pi_detector` running manifest 不再因为 tool_filter monitor
  健康而显示为 detector 正在推进；当前
  `transformers_detector_scored_status=not_admitted_or_not_progressing`。
- Frontier API gate 的后续自动衔接已修复：`audit_frontier_api_model_slots.py`
  会在 `frontier_api_model_slot_registry_admission_v1.json` 已 admitted 且
  `model_registry_v3_candidate.json` 哈希匹配时选择 v3 candidate；否则回退
  到 v2。`audit_q2_readiness.py` 使用审计后的 registered frontier vendor
  count 计算 model coverage 和 cap。当前配置仍是 OpenAI/Anthropic 0/2，
  registry admission 为 `blocked_smoke_not_qualified`，因此 Q2 不变。
- Q2 readiness 最新仍为 raw 63.5/100、capped 60.0/100、goal_90_met=false。
  PromptGuard 仍是唯一 formal-ready required strong baseline，且只限
  detector-performance 表。
- 独立 blind gate 现在必须同时验证 600-row candidate 与 custody sidecar 的 SHA-256/行数/作者/custodian/隔离/封存时间；当前没有 candidate，仍 `blocked_missing_candidate`。
- Frontier API 已有 no-network registry admission 脚本；当前 plan-only smoke 不能写 v3 candidate，两个 API 槽仍为 0。脚本不读取 Token。
- Strong-baseline audit 已正确识别 IPIGuard 的 source-backed adapter/freeze 工程完成，但 formal logs/admission 未完成，故仍不计入 formal-ready；PromptGuard detector-only 仍为 1/5。
- AgentDojo detector exact 路线现在是 resource-blocked diagnostic，不是恢复中：v2 CPU retry 在 `workspace:user_task_25` 再次复现 2,185,056,432-byte CPU allocation OOM；direct long-output smoke 在卸载 Ollama 后直接调用 pinned official detector，也对 27,697 字符 `list_files` 输出复现同一 OOM。不要再续跑旧 v2 root，也不要启动 fresh exact 726-case formal run；后续只能披露 exact-source resource incompatibility 或另建非等价 bounded-input adapter。

- Ollama 活动模型库为 `E:\Ollama\models`；D 盘旧模型库已在两轮验证后删除，回收 13.20 GiB，`D:\Ollama\app\ollama.exe` 保留。
- 新增论文别名 `m3-paper-qwen3-8b-v1:latest`（8.2B Q4_K_M，digest `500a1f...8b41`）与 `m3-paper-llama31-8b-v1:latest`（8.0B Q4_K_M，digest `46e0c1...66e`）；24/24 qualification case-runs、0 failures，仅为 smoke。
- `model_registry_v2.json`、`public_benchmark_formal_freeze_v2.json/.md` 和 `public_benchmark_formal_run_plan_v2.json/.md` 已生成；v2 队列是 84 cells / 74,760 pending case-runs，v1 未覆盖。
- PromptGuard 86M 冻结 revision 已完整下载并通过 real CUDA 12-case qualification smoke；随后完成独立 detector-only formal run：3,280/3,280 predictions、0 inference failures、Recall 24.58%、FPR 0.00%、Precision 100.00%、F1 39.47%。它只可进入 detector-performance 表，不能写作端到端 ASR/TCR/工具效用结果。
- AgentDojo 官方 `transformers_pi_detector` 依赖 smoke 已完成：ProtectAI revision `90c9989b1a342275dd0d1a95aad283c04e075671` 缓存在 `E:\AI_Cache\huggingface\hub`，AgentDojo 官方 `TransformersBasedPIDetector` 离线加载成功，3/3 required smoke checks 通过。它仍不是 AgentDojo benchmark 结果。
- 2026-07-21 continuation：`agentdojo_tool_filter_formal_freeze_v1` 已接入官方强基线审计和 baseline registry 审计；`agentdojo_tool_filter` 当前为 `ready_official_tool_filter_qualification_completed_formal_run_pending`，仍 `result_eligible=false`。新增 `experiments/paper_v1/benchmarks/run_agentdojo_official_tool_filter_formal.py` 与 `analyze_agentdojo_official_tool_filter_formal.py`；runner 1.1 用披露的 OpenAI-compatible filter-model binding shim 修复本地 provider 名误作模型名的问题。初始 two-utility qualification 与新增 utility+security qualification 均为 2/2 completed、0 failed，并完成 diagnostic analysis；仍需要 726-case formal run 和正式 analysis 后才能进入表。
- Active long run: AgentDojo `tool_filter` 726-case formal root `outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1` is running with `--admit-formal`, resumed PID 18904. At 2026-07-22 11:25+08:00 the read-only snapshot was `running_progressing` at 526/726 completed, zero failures and 200 missing. Do not start another Ollama/GPU formal job until this root completes, fails, or is intentionally stopped and recorded. Once it reaches 726/726 with zero failures, run the analyzer first, then the admission bridge in plan-only mode, and use `--write-registry` only if every hash/coverage/status check passes; finally rerun baseline registry, strong-baseline readiness and Q2 audits.
- Progent official source is pinned at `external/baselines/progent@8a8eb894b9d568a32b4e58252fea85b47f789c77`; source smoke passed and records the missing top-level license warning. Its bundled AgentDojo 0.1.29 universe is only 686 cases, exactly 40 travel injection-task-2/6 cases short of the common frozen 726 universe. The v1.1 13/13 source-backed freeze discloses a lifecycle/transport port of the exact official `secagent` policy engine onto the common universe, hash-binds the local runner/analyzer/import-audit/shared-identity/protocol files, and the 10/10 network-free import preflight ran zero benchmark cases. Runner/analyzer and dual raw-official/execution-grounded checker reporting are implemented, but no real qualification or formal Progent case exists. After `tool_filter` finishes and Ollama is free, run the frozen 2-case qualification first in a fresh v1.1 output root; only a clean qualification permits the 726-case run.
- Task Shield has no pinned public official repository. The local ACL paper PDF is fixed at SHA-256 `057ff02152c0bb61892b08abdc80f7af22416c03819e526878091ee87d3bf1e6`; the v1.2 13/13 freeze and 9/9 network-free import preflight define a disclosed paper reproduction with zero-threshold fuzzy alignment, strict JSON, assistant/tool-call/tool-output checks, local adapter hash binding, resume-identity protection and a local Qwen3 8B verifier. Runner/analyzer exist, but no real qualification or formal case exists. Never label it official-source; after `tool_filter` releases Ollama, run its frozen 2-case qualification sequentially with Progent, not in parallel.
- 新增 `formal_security_properties_v1.md` 与 `paper_storyline_v1.md`，使机制 formalization 与论文叙事项在 `q2_readiness_audit_v1` 中变为 complete。
- 新增 `adaptive_mcts_budget_freeze_v1.json/.md`，冻结 80-task query-budget adaptive panel，覆盖 9 个攻击族、6 种语言和 100/500/2000 三个预算组；sealed_holdout 明确排除，`result_eligible=false`。
- `q2_readiness_audit_v1` 当前 raw score=63.5/100、capped score=60.0/100，未达到 90；增加的 0.5 只表示 `tool_filter` 正式作业健康推进，不表示结果已准入。adaptive 工程分仍只是 Stub 编排预检，旧 detector stale running manifest 不再加分。前沿 API 模型、自适应 formal run、独立 blind、公共基准正式矩阵和强基线数量仍是硬门槛。
- AgentDojo `transformers_pi_detector`：v1 automatic-CUDA full attempt 在 92 completed / 4 failed / 630 missing 时因 8GB GPU OOM 被停止并标记为 diagnostic-only。早期 v2 empty-CUDA preflight 也因 transformers 仍选择 CUDA 被移入 `_invalid`，不得合并分母。
- Runner 1.2 使用 `--detector-device cpu` 与 `CUDA_VISIBLE_DEVICES=-1`。独立 1-case CPU-device preflight 已完成 1/1、0 failed、stderr=`Device set to use cpu`、`result_eligible=false`。
- Fresh resource-isolated target `outputs/paper_upgrade_v1/baselines/agentdojo_transformers_pi_detector_official_resource_isolated_formal_v1/` 当前没有 run manifest；monitor health=`missing_manifest`。旧 `agentdojo_transformers_pi_detector_official_formal_v2_cpu_detector/` manifest 的 `running` 是停止后的 stale 状态，已由 long-output direct smoke supersede，不能进入正式表。
- Read-only monitor `experiments/paper_v1/benchmarks/monitor_agentdojo_official_formal_run.py`
  now writes
  `protocols/paper_upgrade_v1/agentdojo_official_formal_run_monitor_v1.json/.md`.
  Latest health status: `missing_manifest` for the resource-isolated target
  root after direct long-output smoke blocked another exact full run. It is
  monitoring evidence only and cannot admit results.
- Independent blind admission audit
  `experiments/paper_v1/benchmarks/audit_m3_v2_independent_blind.py` now writes
  `protocols/paper_upgrade_v1/m3_v2_independent_blind_admission_audit_v1.json/.md`.
  Current status is `blocked_missing_candidate` because
  `m3_attacks/cases/paper_v1/m3_v2_independent_blind_candidate.jsonl` is not
  present. The existing automated sealed holdout remains excluded from new
  confirmatory blind claims. When a candidate is released, the audit also
  requires `m3_v2_independent_blind_custody.json` and binds its SHA-256, row
  count, author/custodian declarations and seal timestamp to the candidate.
- Frontier API model-slot audit
  `experiments/paper_v1/benchmarks/audit_frontier_api_model_slots.py` now writes
  `protocols/paper_upgrade_v1/frontier_api_model_slot_admission_audit_v1.json/.md`.
  Current status is `blocked_missing_or_unsafe_local_config`: the local config
  file is ignored/untracked and no tracked-file secret hit exists, but both
  required provider slots remain unconfigured, no explicit network-smoke consent
  is recorded, and no frontier API model is registered for formal matrices.
  Offline `admit_frontier_api_model_slots.py` will write a v3 registry candidate
  only after exactly two successful one-attempt provider smokes; the current
  plan-only manifest is blocked and writes no registry.
  After a future successful admission, rerun the frontier audit and Q2 audit;
  they now auto-select the admitted v3 candidate and no longer require manual
  edits to `model_registry_v2.json`.
- IPIGuard pinned-source adapter preparation is complete but not result-eligible:
  - freeze `protocols/paper_upgrade_v1/ipiguard_source_backed_formal_freeze_v1.json/.md` covers exact 97 utility + 629 security cases and passed 8/8 checks;
  - runner/analyzer are `run_ipiguard_source_backed_formal.py` and `analyze_ipiguard_source_backed_formal.py`;
  - import preflight `ipiguard_source_backed_import_preflight_v1.json/.md` passed 6/6 in a child process with no network, no Ollama probe and zero benchmark cases;
  - the disclosed import isolation replaces only the unused optional Vertex AI constant while construction, traversal, execution, traces and DAGs remain pinned-source;
  - registry status is `source_backed_adapter_runtime_qualification_failed_model_dag_schema`; the 2-case runtime qualification completed 1/2 and failed 1/2 with upstream `construct_dag()` `KeyError('function_name')` from a malformed local Qwen3 8B DAG tool-call JSON. Do not count IPIGuard until a disclosed frozen configuration passes qualification, full 726-case formal run and analyzer admission complete.
- Adaptive MCTS execution engineering is now prepared:
  - formal runner/analyzer and protocol are `run_adaptive_mcts_budget_formal.py`, `analyze_adaptive_mcts_budget_formal.py` and `adaptive_mcts_budget_formal_protocol_v1.md`;
  - 2-case × 3-query Stub preflight completed 2/2 tasks, 6 queries and zero failures; diagnostic figures were generated;
  - both root and analysis manifests retain `result_eligible=false`; do not start the real 80-task run until the active AgentDojo job releases Ollama/GPU;
  - formal analysis requires 80/80 tasks, exact 100/500/2000 budgets, complete query/checkpoint evidence and zero unresolved failures.
- Independent blind authoring is prepared without contaminating the blind set:
  - `protocols/paper_upgrade_v1/independent_blind_authoring_kit_v1/` contains 600 content-free assignment slots, a case template, custody template and detailed isolation/sealing/review instructions;
  - the actual candidate must be created outside the project by independent authors or an independent frozen generator, then withheld until code/threshold/hypothesis/exclusion freeze;
  - the kit creates zero cases and is not confirmatory evidence; current admission remains `blocked_missing_candidate` and the Q2 score does not increase.
- Frontier API execution is safely prepared but not authorized/configured:
  - `experiments/paper_v1/frontier_client.py` implements one-request OpenAI/Anthropic transports with HTTPS, explicit consent and no retries;
  - `smoke_frontier_api_models.py` defaulted to plan-only and recorded 0 configured providers, 0 network calls and `result_eligible=false`;
  - real smoke may upload only the fixed synthetic prompt after the owner selects exact model IDs, supplies both personal keys locally and explicitly approves cost/network execution;
  - do not register frontier slots or rebuild the v2 freeze until two real smokes and immutable model metadata exist.

- AgentDojo four-suite diagnostic screen：124/124 jobs completed，0 failed；仅用于候选簇选择。
- AgentDojo selected-cluster repeat：174/174 jobs completed，0 failed；25 个正候选簇 + 4 个 zero-control 簇，`no_defense` 官方注入成功 72/87，`m3_full` 0/87。
- selected-repeat 分析输出：`outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_repeat_qwen3_v1/analysis/`；包含 suite/cluster CSV、paired statistics、PNG/SVG 图和 analysis manifest。
- 稳定性：24/29 簇为 stable baseline-positive，且这 24 个簇在 `m3_full` 下均 stable block。
- 统计：McNemar p=4.24e-22；cluster bootstrap `m3_full - no_defense` = -82.8pp，95% CI [-96.6pp, -69.0pp]。
- 边界：selected-repeat 刻意富集 baseline-vulnerable clusters，不能估计 AgentDojo 全量 ASR，也不是正式公共基准结论。
- Official prompt-baseline diagnostic：174/174 jobs completed，0 failed；`agentdojo_repeat_user_prompt` 和 `agentdojo_spotlighting_with_delimiting` 均为 66/87 官方注入成功。
- 四条件合并分析：348/348 jobs joined；`no_defense` 72/87，repeat-user 66/87，spotlighting 66/87，`m3_full` 0/87。
- prompt-baseline comparison 输出：`outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_prompt_baseline_comparison_qwen3_v1/`；包含 suite/cluster CSV、paired statistics、analysis manifest、PNG/SVG 图。
- 新协议：`protocols/paper_upgrade_v1/agentdojo_selected_prompt_baselines_v1.md`。
- 新合并分析器：`experiments/paper_v1/benchmarks/analyze_agentdojo_prompt_baseline_comparison.py`。
- InjecAgent official-formula replay scorer：`experiments/paper_v1/benchmarks/score_injecagent_replay.py`。
- InjecAgent scorer smoke：`outputs/paper_upgrade_v1/public_replay/injecagent_qwen3_limit3_v1/official_formula_score_v1/`，3-case replay，`no_defense` 与 `m3_full` ASR-all Total 均为 0.0、Valid Rate 均为 100.0。
- InjecAgent scorer boundary：复用官方 ASR 聚合公式，但输入标签来自 M3 replay 工具执行日志；仍不是原版 InjecAgent ReAct/function-calling execution。
- InjecAgent official-stage diagnostic runner：`experiments/paper_v1/benchmarks/injecagent_stage_runner.py`；协议 `protocols/paper_upgrade_v1/injecagent_stage_runner_v1.md`。
- Stage smoke/slices：`outputs/paper_upgrade_v1/injecagent_stage/qwen3_limit2_v3/`、`outputs/paper_upgrade_v1/injecagent_stage/qwen3_dh_limit2_v1/`、`outputs/paper_upgrade_v1/injecagent_stage/qwen3_ds_limit5_v1/` 和 `outputs/paper_upgrade_v1/injecagent_stage/qwen3_dh_limit5_v1/`，均 0 failure；官方公式桥接分数 Valid Rate 100.0、ASR-all Total 0.0。
- Prompt styles now include `m3_json`, `official_react` and `official_react_simple`; parser prioritizes ReAct Action over later Final Answer and accepts no-argument tool calls.
- Stage runner now supports result-blind selection files, incremental `progress.jsonl`/`runs.jsonl`, `progress_sha256`, `--timeout` and `--max-tokens`.
- Vicuna official_react_simple paired diagnostics:
  - DS: `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_ds_limit3_pair_v1/`, no_defense 3/3, m3_full 0/3.
  - DH: `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_dh_limit3_pair_v1/`, no_defense 1/3, m3_full 0/3.
- Extra DS exploratory cases 0004/0005 under Vicuna + official_react_simple + no_defense produced ASR-all Total=0.0 and are retained as negative diagnostic evidence, not as a paired effectiveness slice.
- Frozen 30-case selection: `protocols/paper_upgrade_v1/injecagent_stage_stratified_30_selection_v1.json`. A pre-progress 30-case Vicuna no-defense run was stopped because it produced no auditable intermediate logs; see failure log.
- Progress-enabled 6-case stratified smoke: `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection6_pair_timeout_v1/`, no_defense 1/6, m3_full 0/6, 0 failures.
- Progress-enabled 30-case stratified diagnostic:
  - no_defense: `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_nodefense_timeout_v2/`, ASR-all Total 46.7%, Valid Rate 73.3%.
  - m3_full: `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_m3full_timeout_v2/`, ASR-all Total 0.0%, Valid Rate 73.3%.
  - Pair: `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_pair_timeout_v2/`, attack success 14/30→0/30, McNemar p=0.0001221; bucket summary and three diagnostic figures generated.
- Stage runner boundary：模型看到官方 prelude，因此 `gold_user_tool_stage_used_online=true`；policy compiler/Guard 仍不读取 attacker labels 或 expected achievement；结果仍是 diagnostic。
- Official compatibility audit:
  - script `experiments/paper_v1/benchmarks/audit_injecagent_official_compatibility.py`;
  - outputs `protocols/paper_upgrade_v1/injecagent_official_compatibility_audit_v1.json/.md`;
  - 19/19 checks passed;
  - validates pinned official source hashes, official prompted-stage markers, official parser fixed samples, synthetic DH/DS S1/S2 formula expectations and source-order official ReAct prompt rendering;
  - boundary remains `compatibility_audit_not_official_benchmark_result`.
- Official prompted-parser intent scorer:
  - script `experiments/paper_v1/benchmarks/score_injecagent_stage_official_prompted.py`;
  - outputs `official_prompted_intent_score_v1/` under both 30-case Vicuna no-defense and `m3_full` roots;
  - paired output `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_official_prompted_intent_pair_v1/`;
  - raw model attack intent: no-defense 7/30, `m3_full` 6/30, McNemar p=1.0;
  - interpretation: execution success drops 14/30→0/30 mainly because the runtime monitor blocks unsafe actions, not because raw model attack intent disappears.
- Strong-baseline registry/audit:
  - registry `protocols/paper_upgrade_v1/baseline_registry.json` schema `m3-paper-baselines-1.1`;
  - script `experiments/paper_v1/benchmarks/audit_baseline_registry.py`;
  - outputs `protocols/paper_upgrade_v1/baseline_registry_audit_v1.json/.md`;
  - 11/11 checks passed;
  - required strong baselines are represented: PromptGuard, Task Shield, IPIGuard, Progent, CaMeL/Fides, AgentDojo `tool_filter`, AgentDojo `transformers_pi_detector`;
  - dependency probe: `tool_filter` local OpenAI-compatible freeze and 2-case qualification are complete; AgentDojo `transformers_pi_detector` has a dedicated E-drive runtime smoke and cached ProtectAI detector, but exact full run is resource-blocked by the preserved long-output case;
  - Q2 strong-baseline gate remains `not_satisfied`, so blocked/pending baselines cannot enter formal tables.
- AgentDojo official strong-baseline capability audit:
  - protocol `protocols/paper_upgrade_v1/agentdojo_official_strong_baselines_v1.md`;
  - script `experiments/paper_v1/benchmarks/audit_agentdojo_official_strong_baselines.py`;
  - outputs `protocols/paper_upgrade_v1/agentdojo_official_strong_baseline_capability_audit_v1.json/.md`;
  - 9/9 checks passed;
  - records official source hashes, source markers, command templates and blockers for official `tool_filter` and `transformers_pi_detector`;
  - current blockers: official `tool_filter` still lacks 726-case formal logs/admission; official `transformers_pi_detector` dependency/model-cache smoke is complete but exact full run is resource-incompatible on this host;
  - confirms the two official strong-baseline ids are not silently mixed into M3 local runner conditions.
- External strong-baseline source/readiness audit:
  - registry `protocols/paper_upgrade_v1/external_strong_baselines_v1.json`;
  - protocol `protocols/paper_upgrade_v1/external_strong_baselines_v1.md`;
  - script `experiments/paper_v1/benchmarks/audit_external_strong_baselines.py`;
  - outputs `protocols/paper_upgrade_v1/external_strong_baseline_source_audit_v1.json/.md`;
  - 11/11 checks passed;
  - covers PromptGuard/Llama Prompt Guard 2, Task Shield, IPIGuard, Progent, CaMeL and FIDES;
  - source state: PromptGuard/PurpleLlama, IPIGuard, Progent, CaMeL and FIDES are checked out and pinned under ignored `external/baselines/`; Task Shield has only a hash-pinned ACL paper and is explicitly a disclosed reproduction;
  - dependency state: PromptGuard has dedicated E-drive venv/cache evidence; CaMeL now has an isolated E-drive Python 3.10.12 `uv` runtime plus process-local AgentDojo suite compat preflight evidence, so the remaining blockers are runner/model transport/mapping/log/admission rather than missing `uv`;
  - PromptGuard is formally admitted only for detector-performance tables; all other entries remain outside formal result tables.
- Strong-baseline source checkout manifest:
  - script `experiments/paper_v1/benchmarks/prepare_strong_baseline_source_checkouts.py`;
  - outputs `protocols/paper_upgrade_v1/strong_baseline_source_checkout_manifest_v1.json/.md`;
  - 5/5 checks passed;
  - source-ready entries: `promptguard_llama_prompt_guard_2`, `ipiguard_github_emnlp2025`, `camel_google_research`, `fides_microsoft`;
  - no packages, model weights, services, APIs or baselines were run.
- Strong-baseline dependency/source snapshot:
  - script `experiments/paper_v1/benchmarks/build_strong_baseline_dependency_snapshot.py`;
  - outputs `protocols/paper_upgrade_v1/strong_baseline_dependency_snapshot_v1.json/.md`;
  - 5/5 checks passed;
  - records local Python package availability, executable availability, PromptGuard model-cache probes, adapter-preflight/source-smoke state, expected source-checkout paths and Git HEAD state;
  - IPIGuard source-smoke is complete but formal logs/admission are still missing; CaMeL is selected, source-ready, dependency-synced and compat-preflighted, but still lacks executable benchmark adapter/model transport/mapping/logs;
  - Q2 strong-baseline gate remains `not_satisfied`; no install, clone, download, service start or baseline run was performed.
- Strong-baseline formal-readiness audit:
  - script `experiments/paper_v1/benchmarks/audit_strong_baseline_formal_readiness.py`;
  - outputs `protocols/paper_upgrade_v1/strong_baseline_formal_readiness_audit_v1.json/.md`;
  - 7/7 checks passed;
  - dependency snapshot status is `completed` and its SHA-256 is recorded;
  - formal-ready strong baselines: `promptguard`;
  - PromptGuard is detector-only formal-ready; AgentDojo `tool_filter` is qualification-complete but still formal-run-pending; Task Shield, IPIGuard, Progent, CaMeL/FIDES and AgentDojo `transformers_pi_detector` remain outside formal result tables until source-backed adapters, frozen dependencies, formal manifests and complete logs exist.
- Public benchmark formal-freeze manifest:
  - script `experiments/paper_v1/benchmarks/build_public_benchmark_formal_freeze.py`;
  - outputs `protocols/paper_upgrade_v1/public_benchmark_formal_freeze_v1.json/.md`;
  - 9/9 checks passed;
  - freezes AgentDojo 97 utility + 629 security and InjecAgent 1,054 security case universes;
  - declares ready-local public-benchmark matrix: 5 local model slots x 6 ready formal main conditions x (726 AgentDojo + 1,054 InjecAgent cases) = 53,400 case-runs;
  - Q2 public-benchmark gate remains `not_satisfied` because strong baselines, two modern 7B-14B model slots and two frontier API model slots are still missing.
- Public benchmark result-completeness audit:
  - script `experiments/paper_v1/benchmarks/audit_public_benchmark_result_completeness.py`;
  - outputs `protocols/paper_upgrade_v1/public_benchmark_result_completeness_audit_v1.json/.md`;
  - 5/5 checks passed;
  - current formal-result gate: `not_satisfied`;
  - current completeness: 60 expected matrix cells, 60 initialized pending cells, 0 uninitialized cells, 0 complete cells; 53,400 expected case-runs, 0 complete case-runs;
  - future formal claims require this gate to become `satisfied` after frozen runs produce per-cell manifest, raw runs, metrics, statistics and figure artifacts.
- Public benchmark formal-run pending ledger:
  - script `experiments/paper_v1/benchmarks/prepare_public_benchmark_formal_runs.py`;
  - outputs `protocols/paper_upgrade_v1/public_benchmark_formal_run_plan_v1.json/.md`;
  - result root `outputs/paper_upgrade_v1/public_benchmark_formal_runs/` now contains `run_plan_manifest.json`, `formal_cell_queue.jsonl`, 60 pending `cells/*/manifest.json` files and 53,400 pending `todo_cases.jsonl` case-run rows;
  - no model/backend service was started and all pending cells remain `result_eligible_for_formal_tables: false`.
- Public benchmark formal case-result row builder:
  - script `experiments/paper_v1/benchmarks/formal_case_result_rows.py`;
  - converts runner/scorer outcomes to standardized rows for the materializer;
  - accepted formal source statuses can be admitted as `formal_public_benchmark_case_run`, while diagnostic statuses remain non-formal and cannot complete a formal cell.
- Public benchmark formal-cell runner wrapper:
  - script `experiments/paper_v1/benchmarks/run_public_benchmark_formal_cell.py`;
  - protocol `protocols/paper_upgrade_v1/public_benchmark_formal_cell_runner_v1.md`;
  - dry-runs a single frozen cell without starting model or benchmark services;
  - ingests supplied official outcome JSONL into `case_results.jsonl` and `case_results_validation.json`;
  - missing outcomes remain explicit failed rows, and formal materialization requires both accepted source evidence and explicit formal admission.
- AgentDojo formal-cell source producer:
  - script `experiments/paper_v1/benchmarks/run_agentdojo_formal_cell.py`;
  - protocol `protocols/paper_upgrade_v1/agentdojo_formal_cell_runner_v1.md`;
  - dry-runs one frozen AgentDojo cell without services;
  - explicit execution produces `agentdojo_outcomes.jsonl`, `progress.jsonl`, execution manifest and per-case native job logs;
  - completed jobs resume by default, existing failures are retained unless `--retry-failed` is explicit;
  - formal source status is admitted only for full-cell, non-stub, zero-failure runs with explicit formal-source admission.
- InjecAgent formal-cell source producer:
  - script `experiments/paper_v1/benchmarks/run_injecagent_formal_cell.py`;
  - protocol `protocols/paper_upgrade_v1/injecagent_formal_cell_runner_v1.md`;
  - dry-runs one frozen InjecAgent cell without services;
  - explicit execution produces `injecagent_outcomes.jsonl`, `progress.jsonl`, execution manifest and per-case official-stage source job logs;
  - completed jobs resume only when paired `runs.jsonl` exists, existing failures are retained unless `--retry-failed` is explicit;
  - formal source status is admitted only for full-cell, non-stub, zero-failure runs with explicit formal-source admission and official ReAct prompt style.
- Public benchmark formal-cell materializer:
  - script `experiments/paper_v1/benchmarks/materialize_public_benchmark_formal_cell.py`;
  - converts one cell's completed `case_results.jsonl` into required artifacts and cell manifest updates;
  - only formal evidence rows with full frozen todo coverage can make a cell eligible; diagnostic/stub rows are retained as `completed_with_failures` and excluded by the completeness audit.
- PromptGuard detector-only adapter preflight:
  - protocol `protocols/paper_upgrade_v1/promptguard_detector_adapter_v1.md`;
  - script `experiments/paper_v1/benchmarks/promptguard_adapter.py`;
  - outputs `protocols/paper_upgrade_v1/promptguard_detector_adapter_preflight_v1.json/.md`;
  - status superseded by detector-only formal run `promptguard_detector_formal_v1`;
  - stub smoke verifies online-only scan-record construction, forbidden-field exclusion, deterministic fallback chunking, thresholding and max-score aggregation;
  - real 86M CUDA qualification smoke is complete at the frozen revision, with 9/12 diagnostic label matches;
  - source-backed detector-only formal run is complete on 3,280 cases and may enter detector-performance tables only.
- Task Shield paper reproduction:
  - frozen protocol `protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v1.json/.md` passed 12/12;
  - import preflight `taskshield_paper_import_preflight_v1.json/.md` passed 8/8 with no network/model/cases;
  - runtime/runner/analyzer are `taskshield_paper_runtime.py`, `run_taskshield_paper_formal.py` and `analyze_taskshield_paper_formal.py`;
  - paper PDF is hash-pinned, but no official code is claimed and prompt wording is a disclosed concise semantic restatement;
  - real result remains blocked on 2-case qualification, 726/726 formal execution, zero unexplained failures and analyzer admission.
- IPIGuard TDG adapter preflight:
  - protocol `protocols/paper_upgrade_v1/ipiguard_tdg_adapter_v1.md`;
  - script `experiments/paper_v1/benchmarks/ipiguard_adapter.py`;
  - outputs `protocols/paper_upgrade_v1/ipiguard_tdg_adapter_preflight_v1.json/.md`;
  - status `ready_for_official_source_smoke`;
  - official source-smoke `protocols/paper_upgrade_v1/ipiguard_official_source_smoke_v1.json/.md` passed 8/8 checks against pinned source markers and the 97 utility / 629 security dataset universe;
  - stub smoke verifies online-only TDG input packages, tool-node normalization, trusted/untrusted source separation and side-effect risk-edge recording;
  - real IPIGuard result remains blocked because official TDG construction is not wired through a source-backed adapter and no complete formal baseline logs exist.
- Progent policy adapter preflight:
  - protocol `protocols/paper_upgrade_v1/progent_policy_adapter_v1.md`;
  - script `experiments/paper_v1/benchmarks/progent_adapter.py`;
  - outputs `protocols/paper_upgrade_v1/progent_policy_adapter_preflight_v1.json/.md`;
  - source-backed common-726 formal freeze `progent_source_backed_formal_freeze_v1.json/.md` passed 12/12 and import preflight passed 9/9;
  - runner/analyzer are implemented with the pinned official `secagent` policy engine and disclosed current-AgentDojo lifecycle/transport port;
  - real Progent result remains blocked until 2-case model qualification, complete 726-case logs and analyzer admission finish.
- CaMeL/FIDES IFC-capability adapter and source-backed compat preflight:
  - protocol `protocols/paper_upgrade_v1/camel_fides_ifc_adapter_v1.md`;
  - script `experiments/paper_v1/benchmarks/camel_fides_adapter.py`;
  - outputs `protocols/paper_upgrade_v1/camel_fides_ifc_adapter_preflight_v1.json/.md`;
  - status `selected_source_ready_dependency_blocked_stub_preflight_only`;
  - stub smoke verifies online-only IFC/capability packages, trusted/untrusted source labels, argument provenance, capability grants and low-integrity-to-sink decisions;
  - official CaMeL source-smoke `protocols/paper_upgrade_v1/camel_official_source_smoke_v1.json/.md` passed 8/8 checks with no network calls and no formal-result eligibility;
  - isolated dependency/import preflight `protocols/paper_upgrade_v1/camel_source_backed_import_preflight_v1.json/.md` passed 12/12 checks, no network and no model/API calls; it preserves the original fresh-process circular-import evidence;
  - source-backed compat preflight `protocols/paper_upgrade_v1/camel_source_backed_compat_preflight_v1.json/.md` passed 8/8 checks, resolving the import-order cycle with a process-local preload of official AgentDojo suite modules and no edits to external source/site-packages;
  - source-backed runner-wiring preflight `protocols/paper_upgrade_v1/camel_source_backed_runner_preflight_v1.json/.md` passed 14/14 checks, constructing upstream `PrivilegedLLM` + suite security-policy pipeline skeletons for workspace/travel/banking/slack with zero cases, zero model/API calls and no network;
  - compat/runner-preflight frozen protocol `protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v1.json/.md` passed 15/15 checks and records common 726-case AgentDojo universe, source hashes, import/compat/runner-preflight evidence, upstream API/model requirements, trusted-input boundary and failure policy;
  - dependency snapshot now has no CaMeL source/runtime blocker; real CaMeL result remains blocked until model/API transport, label/capability mapping, model qualification, complete logs and analyzer admission exist.
- 本轮 focused regression：`python -m pytest tests/unit/test_public_benchmark_adapters.py tests/unit/test_paper_v1_runtime.py tests/unit/test_paper_metrics.py tests/unit/test_paper_matrix.py -q` => 122 passed。

下一步优先级：

1. 继续只读监控当前 AgentDojo official `tool_filter` formal run（PID 36472，root `agentdojo_tool_filter_official_formal_v1`）；仅在 726/726、0 unexplained failures、`completed_formal` 后运行 analyzer、materializer 和正式准入审计。
2. 不要重启 exact official `transformers_pi_detector` full run；direct long-output smoke 已证明该路线在本机/冻结长输出下 resource-blocked。若需要 detector-style 端到端比较，只能另行冻结并披露非等价 bounded-input/windowed adapter。
3. GPU/Ollama 槽释放后，先顺序运行 Task Shield 与 Progent 的 2-case qualification；通过后才允许各自 726-case formal。不得与当前作业并发，也不得把 import/source smoke 当作算法结果。
4. 决定 IPIGuard 的披露路径：修复/冻结更强 DAG schema 配置并重新 qualification，或保留为本 host/model 的 runtime-incompatible source-backed baseline。
5. 基于已完成的 CaMeL source-smoke、isolated runtime、compat preflight、runner-wiring preflight 和 15/15 freeze，继续冻结 privileged/quarantined model transport、label/capability mapping 与正式执行协议，最后做 2-case qualification；完成前不得将 CaMeL 计入 formal-ready baseline。
6. InjecAgent 需在 byte-identical official prompted/function-calling runner 与 disclosed compatibility 路线间形成可审计决定；现有 30-case 结果仍为 diagnostic。

仍不得 push、创建 PR、制作 PPT/DOCX/ZIP。

## Durable Final State

M3-EXPANSION-001 和 Acceptance Remediation V2 已完成实验、修正和证据阶段，位于本地 `test1`。E0-E17 均为 `completed`；修正前结果保持 8/12，独立 V2 post-hoc engineering remediation 为 12/12 pass。

- Git base：`origin/team-a/m3-core-day7@2c53f52`；本文件及最终有效证据已封装到本地 `test1` 提交，提交哈希以 `git log -1` 为准。
- Registry SHA：`52841155bf90582886145851507885e7f1ff7076de01aeeaad2fe7d1e5efba0f`。
- E17 sampled review：两名真人、每人 360 行、360/360 agreement、kappa=1.000、无 adjudication。
- E17 inference：300 representative rows only；60 targeted rows diagnostic only；没有 3,299 行全量真人审阅声明。
- Final analysis：13 charts、63 manifest artifacts；status completed；acceptance fail。
- Statistical validation：PASS，0 hard failures，0 fallacy failures。
- Dashboard gate：PASS；仅加载固定的 completed evidence roots。
- Tests：最终聚合 verifier 347 passed、1 skipped，Verification failed=0。
- HTML report：`outputs/experiments/final_analysis/report/report.html`；标准构建器 validation/package/structural PASS；浏览器验证受共享阅读器 8px 顶栏溢出限制，详见同目录 `verification.json`。
- E11 execution-r2 freeze：`ceb320a915d301d6658b5caa9b662cb2ed13e24c63ec5d79f8ff7caa9ad0ba37`。
- Runtime：最终交付时 Ollama/Streamlit 应保持停止；服务检查不得调用会自动启动 Ollama 的命令。
- V2 execution：12/12 jobs、2,160/2,160 logical case-runs；performance replay 144 rows / 12 cells。
- V2 gates：A04 100%；A06 -2.16pp；A07 98.81%；A10 0.009461%；总体 12/12。
- V2 Dashboard：10 metric rows、3,780 logs、4 verified figures、0 warnings。
- V2 evidence boundary：复用原 blind case 的 post-hoc 工程复验，不声称为新的未见盲测。
- Final verifier：361 passed、1 skipped、`Verification failed=0`。
- Historical compatibility：E11 r2 6 个、context/E17 r3 7 个当前源码漂移被精确锁定；旧冻结与 240 个嵌套证据记录通过，当前 V2 27-source freeze 通过。
- Git byte integrity：V2 hash-bound paths 使用 `.gitattributes -text`；index 审计 27/27 frozen sources 和 56/56 evidence references 无 mismatch。

## Remediated Result Misses

- 原四项缺口均已在 V2 中达标：A04 134/134、A06 off 312/324 vs full 319/324、A07 166/168、A10 worst 0.009461%。
- A11 为 1736/1817=95.54%，达到 95% 目标；解析失败仍留在分母。
- V1 首个正式 job 的失败证据保留在独立 invalidated root，不得并入 V2。

## Boundaries

- 不把自动代理结果或 60 targeted rows 冒充总体真人估计。
- 不覆盖历史 v3、失败 E14 r2、E11 legacy freeze/结果；它们保持 diagnostic provenance。
- 不访问真实 secret，不启动真实邮件/API，不执行模型生成代码。
- 不制作 PPT、DOCX、ZIP；不 push、不建 PR。

## Rebuild And Review

1. `python scripts/build_final_analysis_sampled_e17.py --validate-only`
2. `python scripts/validate_final_statistics.py --analysis-dir outputs/experiments/final_analysis --out outputs/experiments/final_analysis/statistical_validation.json`
3. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_final_dashboard.ps1 -ValidateOnly`
4. 阅读 `outputs/experiments/final_analysis/report/report.html`、`analysis.md` 与 E17 `review/analysis.md`。
5. `python -m experiments.acceptance_remediation verify`
6. `python -m experiments.acceptance_remediation_analysis_patch`
7. 阅读 `outputs/experiments/acceptance_remediation_v2/analysis.md`、`acceptance_matrix.csv` 与 4 张图。

## 2026-07-18 Model Migration Handoff

- Active model store: `E:\Ollama\models`; pre-migration union 53/53 files matched source SHA-256, and both 11-model restart smokes passed before deletion of the exact D-drive backup.
- Reclaimed from D: 13.200 GiB; `D:\Ollama\app` remains installed; `E:\M3_PI_Guard\models` remains preserved and byte-matched to its pre-migration inventory.
- Qualified aliases: `m3-paper-qwen3-8b-v1:latest` and `m3-paper-llama31-8b-v1:latest`; the isolated paper runtime completed 24/24 diagnostic qualification cases with zero runner failures.
- Historical note: at this 2026-07-18 checkpoint PromptGuard was still gated and no bypass was attempted. This was resolved on 2026-07-20 after the user obtained access and supplied a local ignored Token.
- Public-benchmark v2 was created without rewriting v1: 7 local models, 84 pending cells and 74,760 pending case-runs; no formal run was started.
- Validation: project tests 504 passed / 1 skipped; static Harness checks, compile, experiment Registry and historical evidence pass. A later duplicate aggregate verifier stalled in its repeated pytest phase and is explicitly recorded in `harness/state/failure-log.md`.
- Final runtime state: Ollama stopped, TCP 11434 closed, Docker stopped. Do not call `ollama list` merely to check status because the desktop app may auto-start the service.

## 2026-07-20 Unified Configuration Handoff

- Shared schema: `config/project.env.example`.
- Per-member secret file: `config/project.local.env`; Git ignored and untracked.
- The user supplied the personal Token locally; validation reports only `set_redacted`. Never request, read aloud or echo the value.
- Safe validation: `python scripts/check_project_config.py --require-promptguard-token`.
- Safe no-network qualification: run the PromptGuard venv Python against `scripts/promptguard_setup_from_config.py --check-only`.
- Frozen download completed at revision `a8ded8e697ce7c355e395a0df51f94adb4a2fd27`; 10 files / 1,131,674,611 bytes and the hash snapshot are present under the E-drive runtime/cache.
- Real smoke artifacts: `outputs/paper_upgrade_v1/baselines/promptguard_real_smoke_v1/`; manifest SHA-256 `847d8d77f0890cb40bc8c8d1fc253d70e416175153d66bf91f719973ecc52282`.
- Formal boundary: the real smoke is qualification-only, but the follow-up detector-only formal runner is now complete. Use `outputs/paper_upgrade_v1/baselines/promptguard_detector_formal_v1/analysis/` for detector-performance tables only; do not rerun the credential/download step unless the cache is lost.
- Verification: frozen model files 10/10 size/SHA-256; focused regression 101/101 for qualification; later PromptGuard formal/public-benchmark tests and baseline audits pass. The aggregate verifier's repeated full-pytest stall is preserved in `failure-log.md` and is not called a pass.
- Final services: Ollama 0, port 11434 listeners 0, Docker 0, Python 0.
# 2026-07-22 handoff — Q2 upgrade live formal run

Do not treat the project as Q2-80 ready yet. The latest readiness audit is `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.

Completed in this handoff window:

- AgentDojo official `tool_filter` exact formal run finished 726/726 with 0 failed and was analyzed/admitted into `protocols/paper_upgrade_v1/baseline_registry.json`.
- `experiments.paper_v1.benchmarks.plan_q2_formal_execution` now treats `admitted_registry_updated` as admitted, tracks external baseline phases, and marks the resource gate busy for active external formal runs.
- Task Shield v1.2 full formal root `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v1` failed and was stopped/excluded as diagnostic evidence. It had 5 completed cases and 1 failed case; the failed row was `agentdojo:v1:banking:user_task_13` with `TaskShieldVerifierError: one contribution row is required per user task`.
- Task Shield v1.3 was added as a separate disclosed compatibility protocol, not an in-place mutation of v1.2. New active freeze: `protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v13.json`. It keeps trusted-task extraction strict and fails invalid verifier contribution-scoring cardinality/parse/schema/score output closed to zero contribution.
- Task Shield v1.3 2-case qualification completed successfully at `outputs/paper_upgrade_v1/baselines/taskshield_paper_qualification_v13/run_manifest.json`; 2/2 completed, 0 failed, `result_eligible=false`.
- Task Shield v1.3 726-case full formal is now running in the background at `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`, PID 27384.
- Current monitor target should be `protocols/paper_upgrade_v1/monitors/task_shield_formal_v13/agentdojo_official_formal_run_monitor_v1.json`.
- Latest monitor snapshot: `running_progressing`, 1/726 completed, 0 failed, 725 missing, PID alive.

Important boundary:

- The four external strong-baseline runner files are hash-bound by freeze manifests. Do not edit `run_taskshield_paper_formal.py`, `run_progent_source_backed_formal.py`, `run_camel_source_backed_formal.py` or `run_ipiguard_source_backed_formal.py` merely to normalize path strings. That breaks frozen identity. Repo-local relative-path cleanup should be done in non-frozen active audit/planner artifacts only.
- Do not resume the v1.2 root or retry only `agentdojo:v1:banking:user_task_13`. If v1.3 fails, preserve its own stderr/progress/outcomes and classify it before any fresh full-root rerun.

Next commands:

```powershell
python -m experiments.paper_v1.benchmarks.monitor_agentdojo_official_formal_run --run-dir outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13 --output-dir protocols/paper_upgrade_v1/monitors/task_shield_formal_v13
python -m experiments.paper_v1.benchmarks.plan_q2_formal_execution --output-dir protocols/paper_upgrade_v1/execution
```

Only after Task Shield completes exactly:

```powershell
python -m experiments.paper_v1.benchmarks.analyze_taskshield_paper_formal --run-dir outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13 --output-dir outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13/analysis
python -m experiments.paper_v1.benchmarks.admit_external_strong_baseline_formal_result --condition-id task_shield --run-dir outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13 --analysis-manifest outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13/analysis/analysis_manifest.json
```

If the admission dry-run returns `ready_for_registry_admission`, repeat the same command with `--write-registries`.

# 2026-07-22 handoff addendum — portability-safe monitor refresh

The Q2-80 target has not been reached yet. Latest audit remains `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.

Completed after the previous handoff:

- Regenerated safe non-frozen monitor/diagnostic artifacts with repository-relative paths:
  - `protocols/paper_upgrade_v1/agentdojo_official_formal_run_monitor_v1.json`;
  - `protocols/paper_upgrade_v1/monitors/transformers_pi_detector_formal_v2/agentdojo_official_formal_run_monitor_v1.json`;
  - `protocols/paper_upgrade_v1/monitors/adaptive_mcts_budget_v1/adaptive_mcts_budget_formal_monitor_v1.json`;
  - `protocols/paper_upgrade_v1/diagnostics/agentdojo_transformers_detector_failure_v1/failure_diagnostic.json`.
- Patched only non-frozen active monitor/diagnostic code:
  - `experiments/paper_v1/benchmarks/monitor_adaptive_mcts_budget_formal.py`;
  - `experiments/paper_v1/benchmarks/diagnose_agentdojo_formal_run_failures.py`;
  - `scripts/audit_project_conventions.py`.
- Re-ran `plan_q2_formal_execution`; it reports `resource_gate=busy`, public matrix 84 pending cells / 74,760 expected case-runs, and Task Shield v1.3 as the active workload.

Current live workload:

- Root: `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`.
- PID: 27384.
- Latest snapshot: `running_progressing`, 24/726 completed, 0 failed, 702 missing.
- Do not start competing Ollama/GPU jobs while PID 27384 is alive and progressing.

Remaining portability boundary:

- A scan of `protocols/paper_upgrade_v1` still reports 23 files with checkout-specific absolute paths: 14 frozen/hash-bound and 9 non-frozen-but-evidence-bound snapshots.
- Do not edit those remaining artifacts in place. If they need fully relative paths, create an explicit new freeze/revision and preserve the old evidence.

Verified:

- Ruff on changed monitor/diagnostic/audit files: pass.
- Compileall for `experiments/paper_v1/benchmarks` and `scripts`: pass.
- Focused monitor/diagnostic tests: 5 passed.
- `python scripts/audit_project_conventions.py --check`: 12/12 PASS.

# 2026-07-22 handoff addendum — Q2-to-80 action audit

The goal remains active; Q2-80 is not reached.

Added a fail-closed read-only action audit:

- Script: `experiments/paper_v1/benchmarks/plan_q2_to_80_actions.py`.
- Artifact: `protocols/paper_upgrade_v1/execution/q2_to_80_action_audit_v1.json/.md`.
- Regression: `tests/unit/test_q2_to_80_action_audit.py`.

Current result:

- Status: `blocked_by_active_hard_caps`.
- Q2: `raw_score=66.0`, `capped_score=60.0`, `goal_80_met=false`.
- Resource gate: `busy`.
- Actions required before an honest >=80 claim:
  1. Two-vendor Frontier API slot admission.
  2. Formal 80-task adaptive MCTS budget evidence.
  3. Independent 600-case blind candidate + formal run admission.
  4. At least five source-backed formal-ready strong baselines.
  5. Complete frozen AgentDojo/InjecAgent public benchmark matrix.

Current live workload remains unchanged:

- Task Shield v1.3 root `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`.
- PID 27384.
- Latest snapshot: `running_progressing`, 24/726 completed, 0 failed, 702 missing.
- Last update age remains below stall threshold; keep monitoring and do not start competing Ollama/GPU work.

Validation:

- Q2-to-80/planner/layout regression: 19 passed.
- Ruff: pass.
- Compileall: pass.
- Project convention audit: 12/12 PASS.

# 2026-07-22 handoff addendum — authoritative current checkpoint

Added a current-state override to avoid confusion from historical 2026-07-21
checkpoint text:

- `protocols/paper_upgrade_v1/implementation_status.md` now opens with the
  current authoritative checkpoint: Q2 raw 66.0/capped 60.0, ToolFilter
  admitted, Task Shield v1.3 running, older dated sections historical.
- `harness/tasks/m3-paper-upgrade.md` now has a latest 2026-07-22 checkpoint
  with ToolFilter admitted, strong baselines 2/5 and Task Shield v1.3 as the
  active workload.
- Dynamic audits were refreshed afterward: Q2 readiness 66.0/60.0,
  `goal_80_met=false`; execution plan `resource_gate=busy`; Q2-to-80 action
  audit `blocked_by_active_hard_caps`.

No formal result was promoted, no registry was written, and no model/API run was
started in this correction.

Validation:

- Project convention audit: 12/12 PASS.
- Focused Q2-to-80/planner/Q2/layout regression: 29 passed.
- Compileall for touched Python audit/test files: pass.

# 2026-07-22 handoff addendum — status docs corrected

Non-frozen status documentation now matches the current evidence:

- `docs/RUNBOOK.md` lists the Q2-to-80 action audit command and labels it read-only.
- `docs/PROJECT_OVERVIEW.md` now states that AgentDojo ToolFilter has been admitted and that formal-ready strong baselines are 2/5, not 1/5. It points the current live workload to Task Shield v1.3, not ToolFilter.
- `protocols/paper_upgrade_v1/implementation_status.md` now has a 2026-07-22 addendum covering ToolFilter admission, Task Shield v1.3 live status, the Q2-to-80 action audit and preserved path exceptions.

After refreshing the dynamic audits:

- Q2 readiness: raw 66.0, capped 60.0, `goal_80_met=false`.
- Q2-to-80 action audit: `blocked_by_active_hard_caps`.
- Q2 execution plan: `resource_gate=busy`, next safe action `monitor_active_formal_workload`.
- No registry write, no model/API call and no formal result promotion occurred.

Validation:

- Q2-to-80/planner/Q2/layout regression: 29 passed.
- Ruff: pass.
- Compileall: pass.
- Project convention audit: 12/12 PASS.

# 2026-07-22 handoff addendum — Task Shield v1.3 synchronized, Harness verified

Goal status:

- The goal remains active. Q2-80 is not reached.
- Current Q2 readiness is still `raw_score=66.0`, `capped_score=60.0`,
  `goal_80_met=false`.
- Do not claim an 80% readiness milestone until the hard caps below 80 are
  cleared by formal evidence, not by smoke, diagnostic, running or plan-only
  artifacts.

What changed in this checkpoint:

- Non-frozen external strong-baseline documentation now matches the current
  Task Shield v1.3 state: disclosed paper reproduction, qualification complete,
  726-case formal root running, not admitted, `result_eligible=false`.
- `protocols/paper_upgrade_v1/implementation_status.md` now records the latest
  Task Shield monitor count as a live-run checkpoint only.
- Dynamic audits were refreshed:
  - external strong-baseline source audit: completed, 11/11 checks pass;
  - strong-baseline formal readiness audit: completed, formal-ready baselines
    remain `agentdojo_tool_filter` and `promptguard`;
  - Q2 readiness: raw 66.0/capped 60.0;
  - Q2-to-80 action audit: `blocked_by_active_hard_caps`.
- No registry admission, frozen evidence rewrite, model/API run, result
  promotion or competing Ollama/GPU workload was started.

Current live workload:

- Root: `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`.
- PID: 27384.
- Latest read-only monitor snapshot in this window:
  `running_progressing`, 26/726 completed, 0 failed, 700 missing.
- Last update age was below the configured stall threshold. Keep monitoring and
  do not start another Ollama/GPU formal workload while this PID is alive and
  progressing.

Remaining Q2-to-80 blockers:

1. Two-vendor Frontier API slot admission with explicit network-smoke consent.
2. Formal 80-task adaptive MCTS budget evidence.
3. Independent 600-case blind candidate, custody and formal run admission.
4. At least five formal-ready source-backed strong baselines.
5. Complete frozen AgentDojo/InjecAgent public benchmark matrix.

Validation:

- Project convention audit: 12/12 PASS.
- Focused Task Shield/Q2/layout/public-adapter regression: 136 passed.
- Full pytest: 666 passed, 1 skipped.
- Full Harness verifier:
  `powershell -NoProfile -ExecutionPolicy Bypass -File harness/scripts/verify.ps1`
  ended with `Verification failed=0`.
- Standalone Ruff: pass.
- Full compileall: pass.
- Experiment registry: 18 completed, 0 pending, 0 running, 0 failed.
- Historical evidence verification: pass.
- `git diff --check`: no whitespace errors; only expected CRLF conversion
  warnings.

# 2026-07-22 handoff addendum — v1.4 formal root has a retained failure

Current live workload:

- Root: `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v14`.
- PID: 9804.
- 18:51 +08:00 monitor: `running_with_failures_requires_attention`, 4 completed,
  1 failed, 721 missing.
- Failure: `agentdojo:v1:banking:user_task_1`,
  `TaskShieldVerifierError: verifier returned invalid JSON`;
  `model_output_or_parse`.

Evidence boundary:

- v1.3 is stopped and sealed unchanged at 42 completed, 1 failed, 683 missing.
- v1.4 qualification is 2/2 clean but diagnostic-only.
- v1.4 formal is already inadmissible because a failed row is present. Do not
  exclude/retry that row, stop PID 9804, or create v1.5 without explicit user
  direction.
- Q2 remains raw 66.0/capped 60.0 and strong baselines remain 2/5.

Verification in this checkpoint: focused tests 143 passed; Ruff passed; PID
monitoring and diagnostic classification now have explicit regressions.

# 2026-07-23 handoff addendum — CaMeL v3 P3 complete, formal blocked

Current strong-baseline status:

- Formal-ready strong baselines remain 2/5:
  `agentdojo_tool_filter` and `promptguard`.
- Task Shield and Progent remain retired/negative engineering evidence.
- CaMeL v3 is diagnostic-only after P3. Do not admit it and do not run its
  726-case formal workload yet.

What changed:

- Added CaMeL v3 runner/analyzer/freeze/protocol and focused tests.
- v3 freeze completed 17/17:
  `protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v3.json`.
- v3 two-case qualification completed cleanly:
  `outputs/paper_upgrade_v1/baselines/camel_source_backed_qualification_v3`.
- v3 P3 8-case qualification completed cleanly:
  `outputs/paper_upgrade_v1/baselines/camel_source_backed_qualification_v3_p3_8case`.
- Diagnostic P3 analysis:
  `outputs/paper_upgrade_v1/baselines/camel_source_backed_qualification_v3_p3_8case/analysis/analysis_manifest.json`.
- Review report:
  `protocols/paper_upgrade_v1/execution/camel_v3_p3_qualification_review_v1.md`.

Important P3 result:

- 8/8 terminal, 0 failed, 0 missing, 0 unresolved security.
- ASR 0/4, but utility TCR 0/4.
- Median latency 49.636 s, p95 latency 159.003 s.

Planner state:

- `protocols/paper_upgrade_v1/execution/q2_formal_execution_plan_v1.json`
  now blocks CaMeL formal execution with
  `review_camel_or_fides_v3_p3_before_p4`.
- Next human/engineering decision: inspect P3 utility traces and decide whether
  to design fresh CaMeL P4/P5 gates or route effort to IPIGuard/FIDES.

Q2 status:

- Q2 readiness remains raw 66.0/capped 60.0.
- No diagnostic, smoke, running, or failed evidence was promoted.

Verification in this checkpoint:

- Focused CaMeL v3/planner tests: 25 passed.
# 当前移交检查点——六条件执行壳层已离线资格化，live 依赖仍封闭

- `M3-PAPER-002` / `F-PAPER-002` 保持 `in_progress`。工程就绪 96%、科学证据
  32%、投稿就绪 43%；六条件壳层通过不等于论文机制效果完成。
- 新入口为 `experiments/paper_v2/formal_condition_executors.py`，冻结证据为
  `protocols/paper_upgrade_v2/formal_condition_executor_qualification_v1.json`。
  它注册六条件、限制 online runtime 字段、在持久化边界前脱敏原始正文，并把
  offline outcome evaluator 与在线执行隔离。
- injected no-effect 资格覆盖 2 benchmarks × 6 conditions = 12 pairs；只在内存
  组装 stub records，persisted records/formal results/network/API/model calls
  全为 0。
- `medium_execution_manifest_v3_preflight.json` 已重新冻结；当前
  `gate_pass=false`。剩余四项为 live 条件依赖、真实日志持久化路径、Gemini
  AI Studio quota 快照和每家一次 exact-model/request+response-ID live
  qualification。
- DeepSeek 与 Gemini 都保留每模型完整 480 项目标；DeepSeek CNY 27 熔断、
  Gemini free-only/USD 0、无 tools/effects/retry/cross-provider fallback 的边界
  不变。不得在新门禁通过和用户明确授权前启动正式矩阵。
- 验证：聚焦 21/21，paper-v2 120/120，LFischl Ruff 通过；全量 892 collected、
  891 passed、1 skipped、3 warnings，Harness 469.1 秒，
  `Verification failed=0`。本检查点未调用 API，也未改动秘密配置。

# Latest handoff — 2026-07-24 02:20 +08:00

- DeepSeek v2 request-trace approval is recorded in
  `provider_request_trace_activation_v2.json`; scope is prospective DeepSeek
  only, v1/historical promotion is forbidden.
- Gemini active quota snapshot is complete: 1000 RPM, 2000000 TPM, 10000 RPD,
  screenshot SHA-256 only, free-only/USD 0.
- Exactly one new DeepSeek fixed synthetic request was attempted. Its
  append-only trace completed 2/2 events. A post-transport local normalized/raw
  response assertion blocked the first artifact write; no retry occurred.
  `provider_live_qualification_v2.json` was recovered from the durable chain
  with response content/usage/latency/full receipt explicitly unavailable.
- `experiment_record_v2.schema.json`, `contracts_v2.py` and
  `formal_record_store_v2.py` are offline-qualified. The store wrote two
  transient records only, with fsync, forward chaining and two rejected
  tamper/truncation cases.
- `medium_execution_manifest_v3_preflight.json` remains fail closed. One
  official provider identity is qualified, but live runtime per-call trace and
  v2 record assembly are not wired; do not start the 480-item formal matrix.
- Focused result: paper-v2 184 passed, 772 deselected, one VIGIL deprecation
  warning; Ruff and PowerShell/Bash syntax passed.
- Final full pytest: 955 passed, 1 skipped, 3 warnings in 374.88 seconds.
  Final full Harness: exit 0 in 481 seconds, `Verification failed=0`.

## 2026-07-24 13:20 +08:00 — Live per-call v2 wiring handoff

Current state:

- The owner-approved DeepSeek prospective chain is now wired into every live
  runtime call. `TracedProviderClient` precommits before transport and produces
  an ordered content-free bundle for the whole work item.
- Experiment-record schema is 2.1. The unused 2.0 single-attestation shape is
  superseded; v1 and all historical freezes remain unchanged.
- VIGIL constraint generation and subsequent agent calls share one contiguous
  call sequence. A complete bundle can be `formal_candidate`; any paused,
  provider-failed or evidence-failed call leaves one open commitment and forces
  a diagnostic ITT record.
- Activation is prevalidated before a terminal event is appended, closing the
  completed-but-unactivated ambiguity.

Qualification and artifacts:

- `protocols/paper_upgrade_v2/provider_trace_runtime_qualification_v2.json`
  covers 4 zero-network paths: single success, two-call VIGIL success, agent
  429 and VIGIL-preparation 429.
- The transient v2 store contains 2 complete candidate and 2 diagnostic failure
  records during qualification; full forward-chain validation passes.
- `protocols/paper_upgrade_v2/formal_record_store_qualification_v2.json` now
  covers one complete and one diagnostic ITT record.
- `protocols/paper_upgrade_v2/medium_execution_manifest_v3_preflight.json`
  reports `live_runtime_per_call_v2_qualified=true` but keeps
  `gate_pass=false`, `execution_authorized=false` and
  `formal_execution_authorized=false`.

Verification:

- Ruff passed for all touched Python/tests.
- Bash and PowerShell syntax, JSON parsing and `git diff --check` passed.
- Focused affected suite: 47 passed.
- Paper-v2: 189 passed, 769 deselected, 1 known VIGIL/Pydantic warning.
- Full pytest: 960 passed, 1 skipped, 3 known dependency warnings in 442.81s.
- Full Harness: exit 0 in 571.8s; embedded 960 passed, 1 skipped, 3 warnings;
  `Verification failed=0`.

Safety/evidence boundary:

- This stage made 0 API calls, read 0 credentials, enabled 0 provider tools,
  created 0 external effects, persisted 0 project experiment records and
  created 0 formal results.
- Scientific evidence remains 32%; engineering readiness 99%; submission
  readiness 44%. The goal remains active.

Next gated action:

1. Freeze a run-specific DeepSeek pilot admission manifest that binds one
   already-frozen work item, trace/record paths, model, CNY 27 abort policy,
   no-retry rule and safety policy.
2. Execute exactly one bounded official DeepSeek work item through the v2
   path, then stop.
3. Review its bundle, official response identity, usage/cost, safety receipt,
   record-chain entry and failure status before authorizing any larger matrix.
4. Do not run Gemini through this DeepSeek-only activated formal bundle or
   claim any effect result from the zero-network qualification.
## 2026-07-24 15:30 +08:00 — DeepSeek single-pilot controller ready offline

- The paper-v2 formal path now has a fail-closed single-work-item controller:
  `experiments/paper_v2/formal_execution_controller_v2.py`.
- Frozen review candidate:
  `protocols/paper_upgrade_v2/deepseek_pilot_admission_candidate_v2.json`.
  It is non-executable (`execution_authorized=false`) and binds M3V2-D-003-BN,
  no-defense, work key
  `fd89c79707414a035a9d4309c3c3125bde14f7260c0e4c9cd66088164076fbe7`.
- Offline controller qualification:
  `protocols/paper_upgrade_v2/formal_execution_controller_qualification_v2.json`.
  It records 1 positive permit-only check and 4 rejected negative cases before
  credential/client access. A separate injected-transport end-to-end fixture
  uses 1 local client and 1 local call to write 1 temporary candidate record;
  it reads 0 credentials and makes 0 external network calls.
- Provider trace bundle 2.1 requires every completed call to bind content-free
  cache hit/miss/output counts, provider-receipt digest, request/cumulative CNY
  cost and budget status to the request chain. Runtime qualification covers
  3/3 completed calls; the controller fixture cost is CNY 0.0000728.
- Do not create or infer
  `protocols/paper_upgrade_v2/admissions/deepseek_pilot_admission_v2.json`
  without the user's explicit academic pilot-checkpoint approval. Existing
  budget and request-trace consent are not that approval.
- If approved later, freeze a separate active manifest bound to the current
  23-input candidate canonical manifest SHA recorded in the latest checkpoint,
  verify it with the controller before secret access, execute once, and review
  identity/cost/trace/record evidence before considering any matrix expansion.
- Current verification: controller 9/9; affected usage/trace/store/gate/
  controller regression 28/28; paper-v2 199/199; full pytest 970 passed /
  1 skipped / 3 known warnings in 295.07 seconds; full Harness repeats 970/1/3
  and reports `Verification failed=0`. Ruff and required JSON parsing pass.
- Readiness remains engineering 99%, scientific 32%, submission 44%; no medium,
  public, adaptive or blind effect evidence exists.

## 2026-07-24 17:00 +08:00 — Post-pilot reviewer ready offline

- Prospective experiment-record v2 is now schema 2.2 and persists
  `provider_safety_receipt`. The previous 2.1 engineering qualification is
  superseded before any formal pilot/result existed.
- Reviewer source/schema/qualification:
  - `experiments/paper_v2/post_pilot_evidence_review.py`
  - `schemas/paper_v2/post_pilot_review_v1.schema.json`
  - `protocols/paper_upgrade_v2/post_pilot_review_qualification_v1.json`
- The reviewer independently binds admission, trace, bundle, cache/cost,
  provider/model, safety receipt/action digest, token totals and record ledger.
  It rejects four integrity failures in zero-network qualification.
- Current candidate canonical manifest SHA-256:
  `6ac0601865d76f5f808952b2f58e6587d02c303ac5e9a998ae4d751fbb3dd4cc`;
  locked inputs: 23. It is still non-executable.
- Active admission, official pilot trace/record and official review artifact
  remain absent. Do not create them without the explicit academic pilot
  checkpoint. An eventual passing official review still requires a separate
  owner decision and never self-authorizes the matrix or result admission.
- Verification: focused 33/33; paper-v2 204/204; full pytest 975 passed /
  1 skipped / 3 known warnings in 297.42 seconds; full Harness repeats 975/1/3
  in 299.96 seconds and reports `Verification failed=0`. Ruff, JSON and frozen
  artifact reproduction pass.

## 2026-07-24 15:24 +08:00 — Official DeepSeek pilot reviewed

- Active admission:
  `protocols/paper_upgrade_v2/admissions/deepseek_pilot_admission_v2.json`.
  It authorizes only the exact candidate SHA
  `6ac0601865d76f5f808952b2f58e6587d02c303ac5e9a998ae4d751fbb3dd4cc`.
- Official evidence root:
  `outputs/paper_upgrade_v2/formal_pilot/deepseek/fd89c79707414a035a9d4309c3c3125bde14f7260c0e4c9cd66088164076fbe7/`.
  Preserve its trace, record and review files; the paths are single-use.
- One call completed with 414 tokens and CNY 0.00165. No retry, Gemini call,
  tools, connectors or external effects occurred.
- `post_pilot_review_v1.json` passed all 15 checks and is ready for a separate
  matrix-design review. It does not authorize matrix execution or admit the
  single record as a paper result.
- The owner permits later controlled DeepSeek and Gemini calls. Before the
  next call, create a fresh staged freeze/admission that preserves provider
  separation, DeepSeek's CNY 27 fuse, Gemini's free-only USD 0 rule,
  no automatic retries and sandbox/in-memory-only effects.
- Current readiness: engineering 99%, scientific evidence 33%, submission
  45%. Next useful research step is a small paired falsification tranche,
  designed after this pilot review, rather than reusing the consumed path.
- Final local verification: focused 31/31; paper-v2 204/204; Ruff and
  conventions pass; full Harness 975 passed / 1 skipped / 3 known warnings in
  317.96 seconds with `Verification failed=0`.

## 2026-07-30 06:39 +08:00 — Public primary recovery still live

- Preserve the live s0/s2/s3 recovery processes and all append-only outputs.
  Latest content-free counts are 504/1265, 592/1264 and 468/1264; s1 is
  complete at 1265/1265. All three live stderr logs are empty.
- After each shard exits naturally, run its frozen v3 technical review and
  typed evidence review. After all four pass integrity, run merge v2, create
  and activate the separate result admission, then run primary analysis and
  `public_primary_analysis_review_v1`.
- The result candidate must freeze both the primary analyzer and independent
  reviewer. Do not edit either after the candidate is generated.
- Focused checks currently pass: manuscript/bibliography 7/7, independent
  reviewer/result-admission 5/5, Ruff and py_compile. Full Harness is pending.
- Public outcomes remain unread and the evidence score remains 753/1200.

## 2026-08-06 10:40 +08:00 — Authoritative current handoff

- Disregard older instructions to preserve or wait for live Public recovery
  processes: all current long-running work has ended naturally, and no related
  Harness/controller/Python process remains alive.
- Fresh Harness v7 is the current authoritative engineering baseline:
  `outputs/verification/experiment_closeout_fresh_harness_v7_20260806/receipt.json`,
  direct exit 0, evidence gate PASS, 13/13 aggregate stages, pytest
  1552/1/3, elapsed 20946.429 seconds.
- Receipt SHA-256 is
  `3f0378d30c65c4e188d878e4503abe572a305c29fb21f1f171dccff21b2de877`.
  The complete report artifact is
  `docs/research/paper_v2/reports/M3_PI_Guard_Fresh_Harness_v7_阶段收口报告_2026-08-06_artifact.json`
  with SHA-256
  `6011c2252e9662f6607f40f3fee65dfc5574e66f8eec3c97ec6ea1a23389cc93`;
  its validator and renderer both returned `ok=true`.
- Do not resume the immutable historical medium-v7 root. Do not execute the
  Adaptive Pro-50 v2 candidate without a new post-v7 non-authorizing gate,
  single-use wrapper/admission and post-integration complete Harness.
- Gemini Public-v5 segment 0 is technically valid but result-sealed. Continue
  later only as one untouched segment per frozen quota day. Independent blind
  execution cannot begin before third-party delivery of the 600-case sealed
  set and custody evidence.
- Owner requested an immediate stop after the report. Start no new API,
  provider, Adaptive, Gemini, blind or full-Harness work until a later explicit
  continuation. F-PAPER-002 remains `in_progress`.

## 2026-08-06 20:25 +08:00 — Day 2–3 authoritative handoff

- Supersede the prior stop instruction only for the completed offline
  qualification described here. No provider execution followed.
- Fresh Harness v8 is the current engineering baseline:
  `outputs/verification/experiment_closeout_fresh_harness_v8_20260806/receipt.json`.
  It directly exited 0, passed the evidence gate and all 13 aggregate stages,
  and reports pytest 1568/1/3 after 29781.25 seconds.
- Receipt SHA-256 is
  `8747437d004059615eb70615d30ebd1af7fedc093c10fa2b30ab2a038b1fb71b`.
  Gate v5 manifest is
  `ff76b53991b5b0f8f2ccdfc88aa246c9be6d7e12786bdf8c3c0d4d1b3c10e58e`.
- The only qualified next execution wrapper is
  `outputs/verification/run_adaptive_formal_pro_v2_guarded_v3.ps1`, SHA-256
  `ea2edc64c954fa3b13948b8ec5a207a4e2601e31c9b738bd72a24ef12b48614f`.
  It has not been run and is not authorized by the gate alone.
- API variables were scrubbed, provider/network authority was false, secret
  hits were zero and no Harness helper/child remains. No scientific outcome or
  blind label was accessed.
- Read the detailed report at
  `docs/research/paper_v2/reports/M3_PI_Guard_Day2-3_离线资格化收口报告_2026-08-06.md`.
- Remain stopped before Day-4 canary until a later explicit owner continuation.
  Historical medium-v7 and all terminal work keys remain immutable.

## 2026-08-07 01:50 +08:00 — Adaptive Pro-50 v2 execution handoff

- The owner explicitly resumed the 21-day closeout sequence. The exact
  `run_adaptive_formal_pro_v2_guarded_v3.ps1 -Stage pro_50` command completed
  naturally with direct OS exit 0.
- Receipt:
  `outputs/verification/adaptive_formal_pro_50_v2_guarded_v3_20260806/receipt.json`,
  SHA-256
  `714ca7186df345add63277c618f43f24e749670282a5807ce3376b0c8942a116`.
- Technical review status is `adaptive_formal_stage_technical_gate_pass` with
  32/32 terminal tasks, 1,600 calls and CNY 1.9984298 spend. Review manifest is
  `1c419d1c89ea4217a54bf7970ac25ab138a31db081991696a81f410bdebb1384`.
- No automatic retry, provider tool, external effect, secret hit or scientific
  outcome access occurred. Result admission is still false.
- Gemini Public-v5 is next. Segment s0 is immutable; s1 is the first untouched
  segment and needs a fresh admission for the current
  `America/Los_Angeles` quota day. Use the generic guarded-v2 wrapper; do not
  reuse any old admission or quota-day reservation.

## 2026-08-07 02:29 +08:00 — Gemini Public-v5 s1 handoff

- Segment s1 completed under the sole `2026-08-06` Pacific free-tier
  reservation. Do not run another Gemini formal segment for that quota day.
- Receipt:
  `outputs/verification/gemini_public_v5_recovery_s1_2026-08-06_guarded_v2/receipt.json`,
  SHA-256
  `507929977d4a78e08da94d62fda3b28920a7c7ce5a6f073933e478b9629e2997`.
- Technical review is `gemini_public_v5_recovery_segment_gate_pass`: 1/1
  record, one completed official transport, all checks true, one VIGIL runner
  failure retained in ITT, and matrix continuation eligible. Review manifest
  is `8223d08b0704b5a21f1393d29c890568cecaf540bdbda4c7780493c401a79dde`.
- Official network, exact `gemini-3.6-flash` identity and provider response ID
  are present. Paid ceiling/cost is USD 0; retries/tools/effects/result access
  remain false.
- On the next Pacific quota day, use a fresh s2 admission and the same generic
  guarded-v2 wrapper. Never reuse the s1 admission, output root or reservation.

## 2026-08-07 03:27 +08:00 — Fresh Harness v9 running handoff

- Pro-200 offline qualification is complete. It authorizes only 39 untouched
  resumable tasks from budget 50 to 200; the one historical diagnostic stays in
  ITT and is not replayed. No Pro-200 provider call has started.
- Gate-v6 manifest:
  `73a57abbd955d6b5099f3fdd1fbb0503017576e3d4758c29d7d760e3f3363a5d`.
  Candidate/admission file hashes are respectively
  `fd9b14608ea3e5218b8ca0fecc5ddeaf7589a4b82beae85c293e5d79ad118ea4`
  and `c14912e8776488c9ec7436e3eb9da4a4b64565485a6d0ac7c7a95fec84e4b922`.
- Fresh Harness v9 was launched exactly once. Monitor helper PID 43844 and
  child PID 48564 in
  `outputs/verification/experiment_closeout_fresh_harness_v9_20260807`.
  Do not kill, restart or launch a second copy.
- Launcher/verifier hashes are
  `953265905101d6683b17e8730dc65ee23c3fb8ee153bcca62558f53d666a818d`
  and `bbe29590775fbae2a43b442562a3bf094a1072c049a17cbca29f2ae678248d37`.
  Running attestation confirms scrubbed provider credentials, no network/API
  authorization and no automatic restart.
- Wait for `receipt.json`; independently verify its hashes and require a direct
  exit 0 before running
  `outputs/verification/run_adaptive_formal_pro_v2_guarded_v4.ps1 -Stage pro_200`.

## 2026-08-07 13:10 +08:00 — Pro-200 host-timeout 技术闭包 handoff

- Fresh Harness v9 已自然直接 exit 0：13/13 PASS、pytest 1584/1/3、receipt
  `14ef9b5ae618839798051a31ce4a4abc270f53f46e393e678e0f43b29f6f0e44`。
- Pro-200 已完成 39/39、6,925 calls、5,504 新增 queries、CNY 8.0544754；
  technical review manifest
  `1910ac58f6403850f9aa5ead1cca3c592dcc7cb9feee9486ef050e214a6ee349`。
- 原 wrapper 被一小时宿主上限终止，receipt 永久缺失且不可补造。execute child
  PID 9956 自然结束，但 watcher `.ExitCode=null`，因此 wrapper/execute direct exit
  均不宣称；仅 recovery technical-review child 的 direct exit=0。
- 当前不可变审计：
  `protocols/paper_upgrade_v2/adaptive_formal_pro_200_host_timeout_review_v1.json`，
  file SHA `d8d90a040a1f971775e0c5f7873ad2b6bb9bdcb9343fbcd4301e47780b2ecf9b`，
  manifest `f927367ffb658139cfe02e0309a9030930478508df0100abc4b7e52abce108fc`。
  它独立验证 PID/start/exe、唯一 execute JSON、hash-locked controller exit
  contract、01–04 replay、39 task events、6,925 budget events、7,454−1,950=5,504
  以及 checkpoint byte hashes；不读取 query ledger、provider trace、checkpoint
  语义、outcomes、标签或密钥。
- `verify.ps1` 已接入本次新增审计和三个恢复脚本。由于该源码增量晚于 Fresh Harness
  v9，v9 不能作为 Pro-500 的最终当前源码门。下一执行者应先离线生成 Pro-500
  candidate/admission、持久 wrapper/launcher 和新版非授权 gate，再取得新的完整
  Harness 直接 exit 0；此之前不得执行 Pro-500 provider call。
- F-PAPER-002 保持 `in_progress`；禁止重跑 Pro-200、覆盖旧日志/technical review、
  读取科研结果或把技术门 PASS 当成结果准入。

## 2026-08-07 19:10 +08:00 — Fresh Harness v11 启动前 handoff

- Pro-500 离线链已就绪，但仍未激活：36 tasks、200→500、CNY 35，零自动重试、
  tools、effects 与 result admission。activation artifact 尚不存在。
- Fresh Harness v10 已自然直接 exit 1。receipt
  `e8ab014c1e0383ed996e2b806e6b60a5aeabca7ad03a7acf6692588b4ae37f9d`；
  唯一测试失败与 prospective stage 失败同源于执行后重放 gate v6。
- v10 failure review:
  `protocols/paper_upgrade_v2/experiment_closeout_fresh_harness_failure_review_v10.json`；
  file SHA `78fd2ed12c209c9357a75025f5807f767852deb54d307d0d5de208450e705cb7`，
  manifest `f35a4d9f92d77ef43eb49ec9aa44e7596e6d326801502c5c3548eeeb49b480bc`。
  其单次写入、verify、44 项定向测试、Ruff/format/compile 均通过。
- 当前 verifier 改为重放该不可变 failure review；gate v6 冻结 artifact 与 Pro-200
  输出未改。下一步只允许一次性启动
  `outputs/verification/start_experiment_closeout_fresh_harness_v11.ps1`。
- v11 若非直接 exit 0，则继续 fail closed；若直接 exit 0，先单次写入并复核
  Pro-500 activation gate，再启动唯一 Pro-500 launcher。F-PAPER-002 仍为
  `in_progress`。

## 2026-08-07 22:17 +08:00 — Owner stop 与报告交付 handoff（当前权威状态）

- Owner 已要求中止。不要自动恢复或继续任何实验、API、Harness、Pro-500、Gemini
  continuation 或盲测工作；只有新的明确 Owner 指令才能恢复。
- Fresh Harness v11 已终止并封存：direct exit `-1`、evidence gate=false、9 PASS、
  1 FAIL、3 incomplete、无 aggregate marker。pytest 的 257 项错误共享一个消失的
  temp-root setup failure；不得写成 257 个产品缺陷，也不得给未终态的
  frozen-study-assets stage 指定结果。
- v11 receipt：
  `outputs/verification/experiment_closeout_fresh_harness_v11_20260807/receipt.json`，
  SHA-256
  `75f4bbb58b30e9543e6aa98498c1f44bfad882180ff25a5672b4914a6089f7da`。
- Pro-500 当前组合有效执行授权为 false：gate-v7 不授权 provider，v11 未通过，
  activation artifact 与两个执行输出根均不存在。当前相关进程为 0。
- 21 天计划未结项。核心剩余为 Gemini 1,789 条、Pro B500、hardest-20×2,000、
  DeepSeek/Gemini Flash adaptive、600 条盲测 authoring、3,600 条盲测执行/评分、
  结果准入/统计和最终 current-source Harness exit 0。
- 已交付报告：
  `docs/research/paper_v2/reports/M3_PI_Guard_实验任务中止阶段报告_2026-08-07.docx`；
  SHA-256
  `d6e5e86270307f2531066958da26709ba372488e1a21247332627e13222ffc58`。
  文档为 15 页、4 图、11 表；最终 WPS 渲染 15/15 页一致，可访问性
  high/medium/low=0/0/0，secret scan=0。
- F-PAPER-002 保持 `in_progress`。若将来恢复，必须新建版本化恢复计划与新 Harness
  身份；不得重写 v11、补造 Pro-200 wrapper receipt 或直接复用旧 activation 路径。
# 2026-08-19 — Current handoff: lean empirical study

- Active branch: `codex/q2-empirical-study`; `m3-guard` remote points to the new
  GitHub repository, with no push performed.
- v12/helper/child/watcher are stopped. Preserve its partial stdout/stderr and do
  not create a receipt, failure review or another Full Harness.
- Authoritative scope: one-pass analysis of existing Pro/Flash/medium/Adaptive
  50/200, then fixed 900-row DeepSeek and 450-row Gemini authorization studies.
- Do not execute blind, Pro-500, hardest-20×2000, full Gemini Public, full
  second-model adaptive or any recursive historical verifier.
- Verification is limited to focused tests, six-row formal prefixes and one-pass
  result integrity. Successful rows are never replayed; failures follow the
  transport-vs-post-response ITT rule in `harness/tasks/m3-paper-v2.md`.
- F-PAPER-002 remains `in_progress`; next action is the one-pass analyzer and
  deterministic 180/90/60 selection implementation.

# 2026-08-20 — Current handoff: DeepSeek results complete, Gemini pending

- Branch `codex/q2-empirical-study` is tracked on the `m3-guard` GitHub remote.
  The DeepSeek recovery closeout is pushed at commit `c7b7953`.
- DeepSeek authorization execution and analysis are complete: 900/900 latest
  ITT rows, 867 response-bearing, 33 repeated pre-response failures, zero
  retry-eligible keys, CNY 1.3888324, and zero forbidden-field/tool/effect rows.
- Analysis output:
  `docs/research/paper_v2/lean_empirical/authorization_results_deepseek_v1.json`.
  Figures and tables are in sibling `figures_deepseek_v1/` and
  `tables_deepseek_v1/` directories. Results/Discussion have been updated.
- Focused checks pass 6/6 plus Ruff and `py_compile`. Do not run a Full Harness
  or recursively verify historical evidence for this lean paper.
- Gemini has 5 response-bearing keys and is paused after free-tier 429 on the
  current Pacific quota day. After the next Pacific midnight, resume with:
  `F:\robot\Anaconda3\python.exe -B -m experiments.paper_v2.lean_empirical_runner --provider gemini --stage remaining --config config/project.local.env --retry-failed`.
  This command skips response-bearing keys, attempts only response-less or
  untouched work and stops on the first new 429.
- If Gemini remains unavailable across three quota days, retain partial rows as
  diagnostic and finish the paper without a cross-provider claim.

- The provisional abstract is now 246 words with five keywords. Five highlights
  are stored in `docs/research/paper_v2/manuscript/highlights_v1.md`, each below
  85 characters. These match the official JISA guide checked on 2026-08-20.
- Before submission, replace only the Gemini boundary sentence if its stopping
  rule permits; do not weaken or remove the unfavorable DeepSeek results.

- `conclusion_draft.md`, `figure_table_captions_v1.md`, and
  `declarations_draft.md` now complete the provisional manuscript sections.
  Declarations remain author-confirmation material, not final factual claims.
- The next data-bearing action remains the Gemini pending-only recovery after
  Pacific midnight; no additional DeepSeek execution or local evidence replay
  is required.

# 2026-08-20 — Current handoff: unified manuscript checkpoint

- Reader-facing working manuscript:
  `docs/research/paper_v2/manuscript/manuscript_deepseek_v1.md`.
- Rebuild command:
  `F:\robot\Anaconda3\python.exe -B scripts/build_lean_paper_manuscript.py`.
- The main body is 8,117 words, contains six numbered sections and embeds all
  five generated figures. Focused manuscript tests pass 6/6 plus Ruff and
  `py_compile`; do not substitute a Full Harness or historical replay.
- The draft explicitly excludes incomplete Gemini rows and makes no
  cross-provider claim. After a new Pacific quota day, the only eligible
  data-bearing action is the pending/no-response-only Gemini command already
  recorded above.
- The builder now reads the six existing result CSVs without modifying them and
  emits publication-facing Tables 1–6. Earlier source-audit, medium, Public and
  adaptive detail tables are retained as Supplementary Tables S1–S6.
- Citation syntax is normalized to the 36-entry BibTeX file; the current draft
  cites 21 unique keys in 52 citation occurrences. Raw internal literature IDs
  and implementation-only result flags are rejected by the builder.
- All scientific subsections now use hierarchical JISA numbering. Final Word or
  LaTeX packaging should remain single-column/editable and place any required
  generative-AI declaration before the reference list.

# 2026-08-20 — Current handoff: editable Word review draft

- Word draft:
  `docs/research/paper_v2/manuscript/M3_PI_Guard_JISA_working_draft.docx`.
- Builder: `scripts/build_lean_paper_docx.py`; focused tests 3/3, Ruff and
  `py_compile` pass. It uses Pandoc citeproc and then applies explicit
  single-column academic styles and fixed-DXA table geometry.
- Structural result: 269 paragraphs, 13 tables, five figures, 21 rendered
  references, zero raw citation tokens and zero replacement characters.
  Accessibility is 0 high/0 medium/21 low, with all low findings being
  reference DOI/URL display text.
- Visual rendering is pending because this host exposes no LibreOffice, Word or
  WPS executable. Do not call the review draft visually verified, final, or
  submission-ready. Gemini and author-owned declarations remain open.

# 2026-08-20 — Current handoff: Gemini-safe analysis checkpoint

- `lean_authorization_analysis.py` now separates terminal ITT rows from
  response-less recoverable rows during partial Gemini analysis. Partial rows
  receive operational accounting only; paired/cross-provider inference stays
  closed until 450 terminal work items exist.
- `lean_empirical_tables.py` includes Gemini in Tables 2–5 only when
  `cross_vendor_claim_eligible=true`; the manuscript renderer labels Provider
  in each of those tables.
- Focused verification: 20/20 pytest, Ruff and `py_compile` pass. Rebuilt output:
  9,813-word Markdown and a 683,271-byte Word draft with 282 paragraphs,
  13 tables and five figures. Visual pagination remains unverified.
- PID 7676 is the sole hidden pending-only Gemini quota-day process. At the last
  check it was alive and still waiting for 2026-08-20 15:02 +08:00; do not
  interrupt it or launch a second runner. No successful response-bearing key is
  eligible for replay.

- Discussion and the design-table note are now outcome-safe: incomplete Gemini
  rows make no external-validity contribution, while a 450/450 cohort causes
  the generated provider note to switch automatically. Focused manuscript and
  DOCX tests pass 10/10 plus Ruff and `py_compile`.
