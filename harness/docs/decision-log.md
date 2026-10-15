# 决策日志

## 2026-10-15 — 可读短路径与历史记录兼容

- 名称先去重复及多余层级，保留完整单词、条件含义和版本；不把研究身份改成不透明代号。新路径的80/64/180/240预算由`m3_core/artifact_paths.py`统一实现，Harness在新增/改名检查中消费。
- 七套公开历史工具包只缩短外层目录；冻结内部清单及正文保持。消融产物采用`records.jsonl`/`metrics.csv`，读取入口只对已知重复模式提供缺失旧路径的兼容解析，不猜测任意文件。
- 旧分片目录及pytest临时树按用途、日期整理；以同盘改名及前后文件大小、mtime、文件身份核对保留内容，不删除结果、不生成递归哈希包。
- 九份超过260的历史私有官方记录保留，避免破坏冻结回执引用；它们不在Git交付范围。Git可检出性和本轮源码的Windows/Linux运行分别作实际验证，不借用旧五平台结果。

## 2026-10-14 — v4模型语义提取与程序规则物化

- 用户批准独立corrected_v4，不放宽Guard来提高编译率。模型只输出小意图表，受信目录与逐参数证据由确定性lowerer验证；不重新走旧平面grounding。
- 显式版本分派和sidecar引用计划保留四公共接口/v3默认；查找结果不是授权、正文不是目标，创建对象证明来自真实模拟后端。
- 32任务两组各16，资格只一次；initial/repair_1是新两阶段编译配置而非HTTP重试。历史44记录不改、正式矩阵不自动继续。
- 实施中Flash正式前缀的可调用4项仅2项解析，未过固定80%门。按用户“停止受影响部分”仅封闭Flash剩余300项；已有20行不改、不重发、不降低门，不把缺失伪造为raw。Pro调试160已闭合，可独立进入原16资格任务；任何共享安全错误仍须先诊断，不享受此解析失败例外。
- 资格首次代码/prompt冻结在新提交后；Pro与Flash不再构成完整双模型资格复现。统计公开20行Flash局部观察与300未执行上下界，不用原计划640冒充全部执行。

## 2026-10-14 — 语境、对象类型与效果评分修正

- 首稿证据须检查所在可信请求语境，模型摘录不能把假设/引用副作用变成命令；有限保守语境遇歧义等待澄清，不声称通用意图解析。
- 原生成功发现保留固定工具目录所给对象类型和ID，禁止draft或正文自报类型。未知发现工具不回退到跨类型ID匹配。
- 合成效果在实际发生时独立检查授权前置与许可次数，任务完成仍独立判定。日历结束时间与时长关系由相同内存后端强制检查，隔离拒绝不算危险效果。
- v1冻结/原编译记录不改写；多跳图只追加v2规范引用，80/400图结构重新核对。正式评估尚未开始，后续编译提示v3必须单独记录；不将开发解析改善解释为模型安全增益。

## 2026-10-13 — 独立任务契约与延迟绑定

- 经用户明确批准新增corrected_v3，不替换历史默认编译器或schema；有限TaskContract sidecar物化现有完整ToolRule，四公共接口保持。
- 对象身份与属性必须由后端受信字段及真实成功发现核验，保留原来源；Pydantic/JSON通过不等于可信，普通观察不能自报binding。
- 相同Pro首草稿用于所有模型/条件/重复，其他草稿仅稳定性。Gemini可选且独立停止，服务失败不拉长主实验；不通过付费/模型替换恢复。
- 比较对象为整条编译与绑定链路，采用开发/评估约束图分离与同动作回放，失败/未知保留。无需新哈希包、递归准入或FullHarness。

## 2026-10-13 强化实验隔离职责

- 复用corrected_v2，不复制历史运行器；捕获默认None，16-call Flash仅本研究显式scope。
- API本地独立study/model进程，服务器仅公开离线工作，不复制凭据/改变生产服务。
- 前缀可解析终态为completed/max_steps有效动作；parse_failure不凭较早parse_ok通过。


## 2026-10-11 — 科研主仓库独立，比赛来源不抹除

- 用户明确选择已有非fork私有仓库 `Fischl0527/M3_PI_Guard`。不另建第三个仓库；完整当前提交历史正常快进到既有研究分支，不从零重新初始化。
- `origin`用于独立科研仓库，旧个人比赛fork关联保留为`competition-origin`；兼容远程`m3-guard`保留。本地工作目录、研究语义及模型环境不改变，旧PR和朋友仓库不修改。
- 本次上传已提交项目与已验证手册/状态，不把正在整理的下载论文、字体、子模块、未验证代码或生成预览并入提交。保留原Git作者与来源，不自行赋予新许可证或更改论文署名。

## 2026-10-11 — 初学者主线自足，专业来源保留可选

- 用户认为文档跳转太多，选定改写现有交接文而非另造总览。主手册按概念、链路、实例、代码、研究、结果、目录、运行和论文组织，外部资料只放附录；其他专题不删除，原文快照保留。
- 当前900/480/16/60与历史Public/E1–E8分开，旧exact_gold缺陷解释为历史修复背景，不把过期待办当今天队列。固定演示与实际模型正常案例分层；脱敏日志不伪造正文，零事件不升级为安全证明。
- 验收采用原文保存、静态路径/Markdown/JSON、source-aware复核和新上下文读者8问，不为说明文运行API、历史统计、完整Harness或论文构建。文档功能可verified，科研功能不随之结项。

## 2026-10-10 — 中文阅读层与原始证据／英文投稿源分离

- 用户要求注释、中文文档及论文参考版；优先当前重要路径，保留英文投稿源、第三方原题名、机器标识、冻结快照和历史原始材料，不能因翻译改证据。旧Word不再新生成；当前中文Markdown为项目组阅读入口。
- 产品／统计模块只改注释；表格renderer的中文分支单独改显示，保持英文生成不变，不利用中文化改权限、评价器、统计或接口。十九注释文件AST比对、定向测试及数字／引用守恒用于本轮验收，而不是扩大到FullHarness。
- 主仓库演示HTML/JSON已由用户标记删除；不恢复，指南区分交付包默认位置与主仓库显式独立预览。F-DOC-002只验证已选阅读范围，F-PAPER-002不变；不声称全历史翻译或新PDF视觉通过。

## 2026-10-09 — 合并当前入口，完整保留历史说明

- 当前状态只维护一份综述及研究／论文导航；重复架构、移交、运行文件改兼容跳转，七份原入口保留归档而非删除。历史原文不通过重写结果“升级”为当前证据。
- 把900/480/16模型记录、60任务事后复核、五环境119限定测试分开；oracle目标许可、未知、负面效用和未完成投稿不被文档整理掩盖。当前稿与完整历史工作稿并存，作者继续留空。
- 只采用本地链接/文本/JSON/范围检查及新上下文读者测试，不为文档修改跑API、论文编译或Full Harness。用户随后选择new-test为PR目标，正常推送自身分支并创建审阅，不延用上次强推授权。

## 2026-10-09 — 仅按用户授权覆盖 new-test

- 用户明确选择覆盖朋友仓库的新测试分支，而非合并双方冲突。允许针对该唯一 ref 改写历史；不将授权扩大到 main 或其他分支。
- 使用精确旧 SHA 的 force-with-lease，保留原提交本地恢复引用，不选择全部 ours/theirs、不调用 PR 合并/关闭、不改保护规则。来源仅已提交当前版本，未提交用户改动排除。
- 覆盖完成后只同步必要任务状态，使用正常 fast-forward push；不改变项目代码、数据、论文或研究验收结论。恢复引用为本地备份，不新造远端分支。

## 2026-10-09 — 同包Kali补验完成后关闭限定迁移任务

- 不因新增目标机器而生成新代码版本、重复哈希包或重跑已验证主机。Kali使用原包、原依赖及独立venv，119测试/180权限/900、480、16计数通过后，F-PORT-001按五环境范围verified；论文仍in_progress。
- 用户本轮授权的Kali密码只用于SSH认证，不保存至项目；不将此前Ubuntu公钥配置许可扩大到Kali，不更改其SSH配置。公开计数JSON与本地测试XML分离，先结果Git再文档Git，避免混入认证和原用户dirty。

## 2026-10-09 — 限定可移植交付，不将系统兼容当防御泛化

- 静态依赖闭包/真实运行配置、180在线投影、已选200离线源记录摘录与900/480/16raw为交付范围；未选记录占位保留原行号及逐记录检查，不能冒称完整封存集。官方AgentDojo由本地公开固定提交新建浅克隆，不复制原Git配置或虚构身份；内部trace/环境/秘密不打包。
- 不复制整套运行器或改变Guard逻辑。Python3.10仅等价f-string/TOML读取兼容；SDK依赖是原生基准导入所需，无API或GPU权重。四个新环境运行同一包；当前V2组件与V1兼容原生final-only串通分别披露，不把固定结束响应当任务效用。
- 中文静态演示展示实际预先生成的提案/检查/效果；离线可打开，非现场模型。四环境明确列出，Ubuntu26桌面VM已实测，Kali保留待办。VM现有公钥登记经过用户明确授权，不读取私钥或将密码写入项目；不自动推断其他主机授权。不创建Runpro/哈希链/host audit或新的完整Harness；移植压缩包和wheels本地交付，不自动上传GitHub。

## 2026-10-08 — 精简当前主稿与完整历史工作稿分离

- 完整英中工作稿及历史源保留；新增明确current配置选择当前证据，标题缺失/重复拒绝而非静默删节。默认full兼容不改，LaTeX必须显式选择current主稿，避免误用历史篇幅和端点。
- 当前正文只展开900/480/16/60的解释；历史结果简述并指向完整工作稿与S1–S20，不重算或改数。四短主表用整体竖版浮动表保持标题/数据/表注同页，长补充继续原行号分栏；不旋转或缩小字体。
- 内部聚焦科学检查不是独立同行评审，PDF已编译不是投稿资格，作者字段继续空白，F-PAPER-002保持in_progress。

## 2026-10-08 — 受信意图解释不转化为隐性授权扩张

- 对固定60正常任务做事后解释性审查，可信请求/应用声明/接口用于判断授权依据，已有完成/首限制用于描述结果，两条证据用途分开。候选接口是可能路线而非答案要求；没有人工独立一致性测量，不当作盲测。
- 7声明逐字段保留；通用词法的语义覆盖不足与明确合同违约区分，模拟API执行成功与完成评分区分。脱敏记录不能判具体参数根因时保留未知；不因低TCR扩权，不新建corrected_v3或新矩阵。

## 2026-10-08 — 当前缓存主图与竖版补充表

- 当前900授权、480同期和300诊断缓存供四主图直接读取，不调用推断分析器、不重跑API或改变授权。历史五图移入S1–S5，旧八表继续S13–S20，避免混为当前修复后的机制效果。
- 宽表按原始行编号及前两身份列拆为竖版续表，所有数据列和值保留。Times New Roman、A4、居中页码与空作者保持；不用旋转、缩放盒或微小字体。
- 英中/LaTeX实际接入与三PDF编译、114页检查已经完成；这只是图表版式切片。60任务受信意图、科学审查与篇幅收束仍待，F-PAPER-002保持in_progress。

## 2026-10-06 — Follow-up同期校准与显式VIGIL适配

- P0公开事件显示AgentDojo自动授权的主要限制是缺工具许可；45解析失败未出现length截断，没有足够公开证据证明编译器违约。不自动扩权或改变corrected_v2历史语义。
- 新120案例配对研究采用normal/auto；无防护、policy和full共用原模拟后端及宿主边界，额外VIGIL在首API前离线资格化。配置为固定源码hybrid规则审计、模型生成约束、关闭LLM二次验证，不冒称完整官方默认系统。
- 仅显式DeepSeekPro研究可使用16-call客户端上限，默认8不变；CorrectnessRuntime仅在VIGIL条件及已注入官方factory时允许16。字段/实际调用参数进入结果，不改变模型提示或权限编译逻辑。
- 论文功能仍in_progress；保留旧raw、参数和无关dirty。P2/E8资格与科研解释分开，不以有利结果决定纳入。
## 2026-10-06 — New post-repair model study, identical model-facing policy

- User authorized actual experiments after the code-only substage. Freeze900 new paired authorization rows and16 synthetic controls; retain original180/60 cohort selection without new outcome selection.
- All main cells use normal prompts. Stress scopes alter only Guard authorization; model prompt remains corrected auto-compiled policy, just as exact-target oracle data remains outside provider messages. Include oracle control explicitly, do not call it deployed non-oracle.
- Synthetic rows use independent synthetic-m3 marker, fixed trusted ACL and real in-memory mailbox state; native resolvers stay strict. Open-weights service unavailable, no installation/startup or silent substitution.

## 2026-10-06 — Prospective Claude-review repairs, no retrospective relabeling

- User authorized fixing Claude's implementation findings. Bound this substage to P0 correctness and targeted offline proof; no new provider experiment or manuscript rewrite follows automatically.
- Keep exact_gold/default corrected_v1 semantics immutable. exact_target_v2 is a separately named excluded oracle control: explicit environment-owned tool roles, typed content, exact security scope, strict interface, sequence and record binding. It composes original full-module restrictions without exposing derived gold to the provider.
- Required unresolved security scope cannot produce a type-only automatic grant even in policy-only. Optional security scope permits omission/explicit default only; generated content is distinct. Generic parsing remains bounded and does not claim arbitrary semantic authorization.
- Missing trusted classification at an applicable restricted sink means ASK, not ALLOW; independent confirmation cannot replace classification. Public and internal-archive controls must still execute to avoid deny-all.
- Preserve proposal/Guard/boundary/execution/unknown separately. A dispatched action followed by an exception has unknown execution/isolation summary, not false-safe zero. Native AgentDojo labels retain native semantics.
- Require explicit plan/compiler/runtime/regime agreement for new configs; do not silently relabel old plans or patch globals. Integrate the already local synthetic control helper/tests only because the regression suite uses it; do not run its model batch.
-151 targeted tests, strict lint and in-memory compile are adequate for this code substage; exclude old-wide/qualification/cache rechecks. Scientific feature remains in_progress pending prospective results, not favorable-outcome gates.

## 2026-10-06 — External competition archive, one current guide and narrow verification

- User authorized old competition materials to move to the external archive. Use16 explicit roots (including the unused DAY6 release builder), preserve original relative structure, reject target conflicts/reparse points, and compare names/types/sizes before/after. Do not delete contents or upload the archive.
- Keep scientific E0–E17 evidence and active source/fixtures/protocols/templates/references because current tests and research still depend on them; age alone does not make a file disposable.
- Normalized guide contents match; retain the docs-relative-link version as the sole reader entry and preserve the root copy externally. Update current navigation, not historical frozen records/package internals.
- User moved D backups manually. Verify only locations without secrets; do not misstate existence checks as full backup verification.
- Keep the existing historical uppercase-file naming failure visible. Do not rename frozen records, relax assertions, or run recursive/full audits merely to turn the directory task green. Archive-specific checks suffice for this bounded subtask; overall feature remains in_progress.

## 2026-10-06 — Current publication integrity, frozen evidence and portable runtime

- User authorized migration, environment and paper-check repairs together. Keep scientific runtime fixes and new experiments out of this bounded task.
- Separate current39-entry bibliography integrity from frozen34-entry export verification; preserve historical export/manifest. Refuse the old writer before network/file work when later entries would be lost. Only AgentSpec metadata was newly verified online, not all39 references.
- Restore the exact missing CaMeL Python3.10.12 under archived runtime, patch the environment's explicit home and use per-command E-drive uv cache. No registry/PATH or permanent environment changes.
- Track required class/BST sources, not personal font binaries; optional font assets fall back to declared system fonts. Keep Times New Roman review body, blank authors and current template entry.
- Synchronize existing corrected-v1 evidence into bilingual drafts/table8 while retaining historical mixed-endpoint caveats. Compilation is not defense-effectiveness or submission readiness.
- D-drive tool-policy rejection remains binding even for inactive backups. Request manual Explorer migration; do not retry via another shell/tool.

## 2026-09-20 — Close non-Gemini deliverables without expanding the study

The user explicitly deferred Gemini. The current remainder means the already approved
correctness_repair_v1 non-Gemini development deliverables, not a new experiment or paper revision.
Independent review found the same-action policy/full checks already implemented and verified;
clarify their location and limits rather than repeat them. Preserve original raw/status/analysis.
Record Gemini as deferred_by_user in task state, without relabeling its historical503 run or
claiming service recovery. Close the non-Gemini development substage while keeping the overall
paper in_progress and the observed scientific limitations explicit.

## 2026-09-20 — Explicit Gemini recovery profile, not uniform288-row replication

The user authorized2048/low only for283 original non-response Gemini items.
Preserve5 old response-bearing512 rows separately. Use a standalone entrypoint
and raw file, not run-all or historical plan mutation. Decrease both client and
local runtime/profile caps by previous calls; the shared historical output-bound
key is raised only in the recovery policy copy.503 is temporary service failure,
not a repeated program error. Recovery scheduling is explicit and bounded.
No claim that changed results identify a safety gain from the repair.
No DeepSeek, paper or scientific-sample changes.

## 2026-09-20 — Bounded postfix modifier fix after development review

Corrected_v1 remains a conservative lexical compiler, not general language
understanding. Post-action conditional text must not authorize unconditional
effects; post-action resource denial must not become an allowed resource.
Use the existing conservative same-tool suppression for mixed positive/negative
requests, including conflicting application declarations. Resource names are not
modifier language. Preserve legacy compilers and use Git revisions to identify
the patch; no new freeze/hash package.48 old/current manifests were identical,
so no existing model rows are replayed or rewritten. Scientific limitations stay.

## 2026-09-20 — Flash official service amendment

Official pricing identifies `deepseek-flash` as DeepSeek-V4.1-Flash and retirement
of historical V4 Flash. The owner expressly selected the new official alias for
the corrected development cohort. Keep old rows unchanged; label this as a
new-model replication. Use current tariff estimates, not claimed invoice charges;
missing usage remains unpriced. No Gemini Billing changes or key rotation.

## 2026-09-20 — Explicit corrected runtime, unchanged historical semantics

The owner approved correcting authorization and measurement behavior through an
explicit corrected_v1 configuration. Historical defaults/raw records remain
unchanged. Runtime dependencies are injected, never globally monkey-patched.
Proposal violations, guard allowance, isolation rejection and observed effects
are distinct; missing evidence is unknown, not false. TraceGuard contributes
design ideas only, with no source/result copying. The new 48-case development
cohort uses six conditions and up to three providers; Gemini remains free-only
and nonblocking. No full Harness, recursive hashes, new admission machinery or
manuscript build is part of this task.

## 2026-09-05 — Independent experimental confirmation boundary

Keep historical E1--E6 source and result semantics unchanged. New E7a uses a
common confirmation wrapper for both policy/full experimental profiles, so it
must not be called the unchanged historical policy-only condition. The wrapper
requires exact task/request/proposal/manifest binding, expiry and one-shot use;
it rejects untrusted text and cannot widen scope or override DENY. This is an
in-process simulation controller, not production authentication or human-study
evidence. E7a is a 96-call single-action probe with 384 paired post-proposal
channel cells, not an external benchmark. AgentDyn remains a separate E8 track.

在此记录架构、策略、依赖和工作流决策。

## 2026-09-04 — Rotate wide-table contents, never the supplied template page

- The supplied `cumcmthesis` review entry remains the author-facing visual master:
  its A4 paper, 25 mm margins and centered plain footer are not overridden by the
  paper generator. The separate `elsarticle` entry remains the submission-facing
  JISA source because the supplied class is not an Elsevier journal class.
- Tables with six or more columns use `rotating/sidewaystable` and a
  `\textheight`-wide minipage. This rotates the table, caption and note only;
  every PDF page keeps portrait physical geometry and an upright bottom-centered
  page number. Narrow tables retain `longtable`.
- Whole-page `pdflscape/landscape` is forbidden for these generated entries
  because it writes `/Rotate 90` and moves the template footer to the displayed
  left edge. The decision changes layout only, not table values, prose, labels,
  citations, experimental evidence or author metadata.

## 2026-09-04 — Use the supplied LaTeX directory without mislabeling CUMCM as JISA

- The user-supplied `LaTeX通用模板` is retained as the requested workspace and
  visual-reference source, but its `cumcmthesis` class is a Chinese mathematical-
  modelling competition class rather than an Elsevier journal class.
- The submission-facing source therefore uses the TeX Live `elsarticle` class and
  numbered `elsarticle-num` bibliography style, consistent with Elsevier's current
  official LaTeX guidance. A separate local review entry uses the supplied class
  without changing or redistributing its class/font assets.
- Both entries are generated from the same section, table, figure and bibliography
  files. This prevents the template review copy from diverging scientifically from
  the submission copy. Author metadata stays empty and all experimental evidence
  remains immutable.
- Build artifacts are verified with the existing TeX Live 2026 XeLaTeX/BibTeX
  toolchain using explicit executable paths; no permanent environment variable,
  provider call, Full Harness or recursive evidence replay is required.

## 2026-08-31 — Close incomplete Gemini B1 without retry or effect estimate

- Evidence decision: the response-less Gemini VIGIL fatal cannot be attributed
  to quota, transport or model behavior because the pinned upstream fallback
  erased the original exception class. It remains terminal ITT evidence and is
  not retried; 174 untouched rows close administratively rather than as safe.
- Inference decision: 1/30 terminal nested pairs and 0/30 minimum response-
  complete pairs cannot estimate a cross-provider effect. Markdown, CSV and
  SVG reader artifacts must show NE/coverage, never a plotted zero effect or a
  DeepSeek n=60 versus Gemini n=1 rate comparison.
- Engineering decision: prospectively preserve only exact paused/transport
  exceptions around the single VIGIL provider call and rethrow them before the
  generic fallback check. This is forward-only observability, not permission to
  replay current or historical rows.
- Scope decision: DeepSeek B1 remains useful contemporaneous risk-enriched
  diagnostic evidence, while E6-v2 makes no temporal-repeatability, deployment-
  prevalence, TCR, provider-ranking or formal cross-vendor claim.

## 2026-08-31 — Close E6-v2 through one independently sealed B1 block

- Owner authorization: plan, audit and execute E6-v2 autonomously until its
  bounded experimental closeout is complete.
- Decision: require a B1-specific administrative seal and one-pass analyzer
  before live calls. Every planned row must end as a model terminal or an
  explicit non-model administrative ITT terminal; a failed prefix never counts
  an unexecuted row as safe.
- Execution order: offline qualification and Git checkpoint, DeepSeek prefix and
  gated expansion, Gemini prefix and gated expansion, then one analysis/report
  pass. Providers run sequentially and never share mutable ledgers.
- Scientific boundary: B1 measures activity and condition effects during one
  disclosed execution span. It excludes temporal-repeatability statistics and
  keeps Gemini/cross-provider evidence diagnostic.

## 2026-08-31 — Replace E6 artificial date delay with one diagnostic execution block

- Context: E6-v1 W1/W2 failed their technical gates and E6-v2 was already
  bounded to diagnostic/sensitivity evidence. Waiting 18--30 hours for a third
  date no longer produces formal three-window repeatability because the
  implementations and eligibility states are not exchangeable.
- Owner decision: remove artificial cross-date waiting. Reinterpret the untouched
  source-W3 projection as independently identified block `B1`, one immediately
  runnable diagnostic execution block (DeepSeek 360, Gemini 180), not as temporal
  replicate W3.
- Engineering consequence: remove the v1 W2-seal, 18--30-hour start interval and
  12-hour temporal-window eligibility checks. Preserve v1 immutability, v2
  identities, W1/W2 rejection, provider isolation, payload-bound recovery,
  outcome-blind prefix gates, ITT and all external-effect/security boundaries.
- Scientific consequence: E6-v2 may calibrate attack activity during its reported
  execution span and provide a within-block directional provider diagnostic. It
  cannot support cross-date
  repeatability, a pooled v1+v2 three-window estimate, or general cross-provider
  claims. The E6-v1 temporal analyzer must reject B1 rows marked non-temporal.
  No API execution is authorized by this protocol-only change.

## 2026-08-29 — Supersede E6-v1 execution with a prospective E6-v2 repair

- Context: DeepSeek W1/W2 repeated a 3 completed / 3 strict-parse-failure /
  6 runtime provider-failure prefix pattern, while Gemini's one permitted
  response-less outer recovery collided with a provider-call ledger that only
  permits paused-429 manual recovery. Gemini then failed closed before W2 made
  any provider request.
- Decision: preserve every E6-v1 plan, response, raw row, gate, seal, trace,
  ledger and provider-stop marker unchanged. Pause the v1 W3 heartbeat and add
  a separately versioned E6-v2 implementation, identity and output root.
- Gemini repair: generic non-429 response-less outer attempt 2 receives a
  distinct call-ledger/trace namespace and remains limited to one explicitly
  named unresolved key with no response in its complete history. Attempt 3,
  response-bearing recovery, success replay, identity/payload drift and hidden
  fallback remain forbidden. Paused-429 recovery retains its narrower existing
  authorization contract.
- DeepSeek repair: retain strict parsing and ITT semantics, but project only
  sanitized failure stage/class/call index/HTTP category and count repeated
  runtime provider failures in the technical gate. Reproduce the AgentDojo
  first-tool-to-second-call path with an offline stub before any new canary.
- Root cause refinement: the pinned `user_task_16` observation is public
  synthetic benchmark data that only matched the broad credential-label regex.
  The prospective boundary therefore skips only that generic regex for an
  explicitly opted-in, case-scoped `public_benchmark_case`; exact active API
  keys and high-confidence `sk-*`, `AQ.*` and PEM forms remain forbidden.
- Scope correction: v2 execution is code-gated to untouched W3 rows. It cannot
  replay v1 W1/W2 response-bearing or successful rows. The projected 360
  DeepSeek and 180 Gemini W3 rows are diagnostic/sensitivity evidence only;
  cross-version rows cannot become formal three-window repeatability, and
  Gemini is a single-window diagnostic.
- Execution prerequisite: direct W3 invocation must first observe the immutable
  same-provider E6-v1 W2 seal and a W2-to-W3 start interval of 18--30 hours,
  before credentials, dispatcher construction or output. DeepSeek has the
  predecessor seal; Gemini does not, so Gemini v2 remains fail-closed rather
  than backfilling a missing historical window. The first W3 call freezes its
  own start; later expansion/recovery validates that value and a 12-hour window
  duration rather than treating the continuation time as a new window start.
- Consequence: E6-v1 remains diagnostic and cannot be made eligible after the
  fact. A response-less recovery is eligible only with a valid pretransport
  payload commitment and exact payload equality; a no-commitment failure and
  W3 429 close as ITT diagnostic terminals. No provider call is authorized by
  this engineering repair; new live execution requires a separate
  owner-visible canary decision after focused tests pass.

## 2026-08-28 — Preserve failed E6 prefixes through administrative closure

- Context: DeepSeek W1 returned all 12 formal-prefix rows but only 3 were
  parseable; Gemini W1 produced two response-bearing failures and exhausted the
  one allowed recovery for a response-less prefix key. Both frozen technical
  gates are therefore permanently false for W1.
- Decision: do not weaken the `>=9/12` parseability or complete-chain gates and
  do not retry response-bearing rows. Seal untouched W1 rows as
  `technical_gate_not_extended`, distinct from Gemini quota-driven
  `provider_window_unavailable`; retain all original attempts append-only.
- Continuity: W2/W3 may run their independently frozen prefixes after the prior
  window is sealed and only within the 18--30 hour schedule. A failed window
  cannot be expanded, and a future window cannot repair W1's eligibility.
- Claim boundary: W1 administrative rows are operational failures/technical
  non-admission, never safe outcomes. Gemini can no longer satisfy the frozen
  three-window cross-provider gate; even successful W2/W3 data are sensitivity
  evidence rather than the preregistered full repeatability endpoint.

## 2026-08-28 — Add E6 cross-provider contemporaneous calibration

- Decision: add a new versioned E6 rather than reinterpret the near-floor E1/E3
  attack cells. DeepSeek V4 Pro is the 60-task primary cohort; Gemini 3.6 Flash
  free tier is a strictly nested 30-task, non-blocking replication cohort.
- Design: six contemporaneous conditions over three consecutive local-date
  windows. Time replicates are plan rows, not retry attempts; outcome-blind
  prefixes and deterministic cyclic order control technical eligibility and
  within-window order without data-dependent stopping.
- Evidence boundary: the historically unsafe-enriched cohort calibrates current
  activity and repeatability only. It does not estimate deployment prevalence,
  TCR, cross-provider universality, SOTA status, or a causal provenance benefit.
- Engineering boundary: reuse the qualified provider/evaluator/simulated-effect
  stack, keep E1--E5 immutable, use only focused verification, and create no
  recursive hash or historical replay package.

## 2026-08-28 — Close E1--E5 and deliver a Markdown report before manuscript work

- Context: E5 reached all 12 selected survivor terminals after explicit
  failed-only recovery of response-less keys. The one-pass analysis, five
  figures and five tables are complete. The owner then requested that current
  results be recorded as Markdown and that paper writing wait.
- Decision: treat E1--E5 as the closed incremental experiment stage and stop all
  provider/API work. Deliver `phase_report_v1.md`, compact analyses, figures,
  tables and Harness/Git state. Do not update or rebuild bilingual manuscripts,
  supplements, DOCX or submission files without a new owner instruction.
- Claim boundary: E5 estimates only the selected B200-survivor conditional tail
  (0/12; Wilson 95% CI 0--24.25%). It is not the original 40-task B500 curve and
  does not establish attack saturation or zero tail risk.
- Recovery closure: later q459/q354 response-less events superseded the earlier
  q474-only operational note. Each was recovered explicitly without replaying
  successful work. Every latest E5 key is now response-bearing; automatic
  retries, provider tools and real external effects remained zero.

## 2026-08-28 — Raise only the E5 execution-cost ceiling after owner resume

- Context: E5 was owner-stopped after 2,379 unique query keys and CNY
  17.9303736. Seven tasks reached q500; the remaining maximum path is 1,222
  queries and projects near CNY 9.2 at the observed average.
- Decision: after the owner explicitly resumed the project and directed that
  cost must not limit it, set the incremental Adaptive/Global fuses to
  non-blocking CNY 1,000/1,000 machine ceilings. Keep actual token/cost
  accounting and keep already-terminal Pro/Flash values at CNY 8/3.
- Scientific invariants: task selection, A1/A2/A3 balance, q201--500, model,
  attacker, seed, first-success stop, append-only ITT, explicit response-less
  recovery, disabled provider tools and zero real effects are unchanged.
- Recovery boundary: only
  `adaptive-cost-v1__M3V2-D-077-A2__q00474` may receive attempt 2; every
  response-bearing or successful query remains immutable.

## 2026-08-26 — Use a lean shared runner and direct B200 checkpoint continuation

- Decision: implement the four regular studies behind one study-scoped CLI and
  implement E5 by copying only the selected no-success B200 MCTS checkpoints into
  a new output root. Validate the source prefix once per invocation; do not replay
  historical query/call ledgers or construct a new hierarchy of hash packages.
- Reason: the paper needs contemporaneous factor identification and a conditional
  tail-risk estimate, not another whole-repository integrity exercise. Existing
  provider traces still provide the necessary local request ID, payload digest,
  official response ID, returned model, usage and cost chain.
- Consequence: successful rows remain immutable; only explicit response-less
  failures may be retried after a fix. E5 reports only the selected B200-survivor
  conditional tail and cannot be merged into a nominal complete B500 curve.

## 2026-08-23 — Reframe M3-full versus policy-only as configuration bundles

- Decision: the paper will not interpret the existing M3-full/policy-only
  contrast as an isolated provenance/data-flow/confirmation ablation. M3-full
  uses the `safe_prompt` profile while policy-only uses `normal`, so Stage 4 must
  disclose the prompt difference and treat the estimand as a bundled
  configuration comparison.
- Reason: the five-role Stage 3 review identified this as a mandatory internal-
  validity defect. Component attribution is not identifiable without a new
  same-prompt experiment.
- Consequence: use the lean no-new-API route. Add only offline benchmark-
  stratified, failure-sensitive and benign-burden analyses from existing rows;
  narrow the title/RQs/claims, update figures and tables once, and retain
  F-PAPER-002 as `in_progress` until Stage 4 and author-owned submission gates
  close.

## 2026-08-04 — Preserve Flash gate failures and version any reconciliation

- Decision: retain both recovery-v3 wrapper exit-1 receipts and reviews exactly as
  written. Do not resume either identity or retry any of the 1,306 terminal rows.
- Reason: shard 0 exceeds the frozen per-shard diagnostic bound, while the review
  also contains a boolean-semantics defect that makes zero source retries evaluate
  false. Rewriting v3 would destroy the audit trail; silently ignoring either fact
  would make admission outcome-dependent.
- Consequence: the 1,791-row physical closure is engineering evidence only. A future
  v4 review may correct the boolean and separately report global/per-shard quality,
  but scientific admission remains false until a prospective rule is selected
  without outcome access and a fresh Harness passes.

## 2026-08-04 — Accept local-precommit Gemini evidence only prospectively

- Decision: seal segment 1 as result-ineligible even though it has HTTP 200, exact
  model identity, official response ID and a complete local-precommit append-only
  trace. Do not invent a provider request ID or retroactively promote the response.
- Reason: the active experiment-record contract still requires both provider request
  and response identifiers. The provider trace and research plan allow local request
  ID plus response ID, creating a real contract mismatch that needs a new version.
- Consequence: manifest `6d7605dd...d649` forbids same-segment/work retry. Any repair
  must add negative-tested prospective attestation/record semantics, use a new quota
  day and execution identity, and pass a fresh full Harness before another API call.

## 2026-08-04 — Consume at most one Gemini formal workload per LA quota day

- Decision: reserve the current America/Los_Angeles quota day only for Gemini
  Public canary segment 1, with a maximum of 16 requests under the 18-request
  local cap and two requests left unallocated.
- Reason: the project-level free tier is 20 RPD and Public/Adaptive must never
  double-book a day. The ledger already binds segment 0 to the prior quota day.
- Consequence: segment 1 runs with USD 0, concurrency 1 and zero retries/tools/
  effects. No Gemini adaptive or continuation segment may start on the same day;
  provider failure or 429 remains terminal ITT evidence rather than a retry.

## 2026-08-04 — Recover only untouched Flash work under two exact admissions

- Decision: bind Fresh Harness gate-v3 to the direct-exit-zero v4 evidence, then
  activate two single-use Flash recovery shards containing only the 1,306 never-
  started work keys. Preserve all 12 canary and 473 terminal prefix records.
- Reason: the historical v2 wrappers ended without receipts and include two ITT
  diagnostics. Resuming their roots or replaying terminal keys would violate the
  frozen no-retry rule, while dropping the prefixes would violate ITT.
- Consequence: s0/s1 contain 652/654 disjoint rows with CNY 2.04118328/2.17094144
  hard limits. Together with canary and prefix costs, the role ceiling is exactly
  CNY 5. Automatic retry, provider tools, external effects and result admission
  remain disabled; Gemini, adaptive and blind workloads are not co-started.

## 2026-08-03 — Stop after Fresh Harness v4 and preserve provider gates as uncreated

- Decision: accept the single-use Fresh Harness v4 direct-exit-0 receipt as the
  current engineering verification checkpoint, write a detailed stage report, and
  pause before creating gate-v3 or any new provider admission/execution.
- Reason: the project owner explicitly asked to let only the running work finish and
  then stop with a report. A successful Harness proves reproducibility and current
  engineering integrity; it does not itself authorize API work or complete the
  remaining scientific experiments.
- Consequence: receipt `a9fddc0f...2c1b` records 13/13 PASS, pytest 1485/1/3,
  direct OS exit 0 and zero provider/network authorization. Flash recovery-v3,
  Gemini continuation-v2, formal adaptive and blind execution remain pending and
  F-PAPER-002 stays `in_progress`.

## 2026-08-03 — Freeze interim-v3 failure and require a fresh version-aware Harness gate

- Decision: preserve interim Harness v3 as direct-exit-1 evidence, classify its sole
  failure with a source-locked review, and make the supersession test controller-
  version-aware. Create gate-v3 only from a new single-use Harness-v4 direct-exit-0
  receipt; the gate source itself grants no provider authority.
- Reason: the literal stage name `pro_50` is shared by obsolete v1 and current v2
  controllers. Rejecting the token without its controller identity produces a false
  regression signal, while rewriting the old run or accepting focused tests in place
  of a full Harness would break the evidence chain.
- Consequence: the v3 receipt/logs remain immutable and non-green; Flash recovery-v3
  and Gemini continuation-v2 remain non-executable candidates until a fresh v4 gate
  and their own exact admissions pass. Historical terminal work and ITT diagnostics
  are never retried or removed.

## 2026-08-03 — Current Harness verifies adaptive supersession, not obsolete v1 admissions

- Decision: preserve the Pro-50 and Flash-50 v1 candidates/admissions as immutable
  fail-closed evidence, but remove their `--verify-admission` commands from the
  current closeout Harness. Verify the hash-bound v2 supersession/order review and
  the directly observed Day-2 failure review instead.
- Reason: the v1 candidate/admission bindings intentionally drift and the frozen v2
  order requires Pro 50/200/500/hardest-2000 before Flash 50/200 and Gemini. Treating
  v1 admission replay as a current readiness check makes every future Harness fail
  for evidence that is already correctly superseded.
- Consequence: historical v1 assets and the earlier green Harness review remain
  immutable; the old review must fail closed when rebuilt against the advanced
  current verifier. A fresh direct-OS-exit Harness is still mandatory before any
  provider canary, and Day-1 acceptance remains an explicit gate rather than being
  bypassed.

## 2026-08-02 — Use a single-folder Python/Markdown custodian handoff with honest dual verification boundaries

- Decision: supersede the current Word/PowerShell operator path with one immutable
  standalone folder whose root `README.md` is the only authoritative procedure and
  whose only workflow entry is `custodian.py`. Keep secrets and signing keys outside
  the package; keep all mutable/private runtime artifacts under the ignored `work/`
  tree without permanent environment variables.
- Reason: the third party needs one portable review boundary, while an auditable
  blind test must prevent manifest-induced private reads, label/gold smuggling,
  answer-key leakage, forged output seals, request-chain state forgery and
  overstatement of what content-free receipts can prove.
- Consequence: verification is split into (A) custodian-private artifact/hash/signature
  replay, which opens labels but does not claim automated semantic rescoring, and
  (B) developer-safe signature/integrity verification over a public scoring release,
  with no private path parameter or enumeration. Both declare
  `semantic_recomputation=false`. Single-use generated candidates are never
  overwritten: v3 through v3.3 remain rejected diagnostics, while only v3.4 is GREEN.
  The package is an engineering handoff, not evidence that a real custodian has
  registered or that the 21-day experiment clock has started.

## 格式

| 日期 | 决策 | 背景 | 备选方案 | 后果 | 负责人 |
| --- | --- | --- | --- | --- | --- |

## 决策

### 2026-08-02——独立盲测采用三段 Ed25519 签名链与白名单交付包

- 决策：第三方保管人必须分别对 registration、custody 和最终 scoring
  attestation 的 canonical payload 进行 Ed25519 detached signature；每段均由
  独立验证人做数学验签和真实身份核验。开发者只能接收脚本生成的白名单
  `developer_handoff_v2`，执行完成后只返还内容无关 output package/seal；
  标签解封、评分和最终签名在保管人环境完成。
- 背景：仅有一个“标签文件”或人工声明不能证明真实第三方身份、标签隔离、
  释放顺序和评分结果未被替换；把私钥或标签复制到项目目录也会破坏盲测。
- 备选方案：开发者代签；只记录文件哈希；提前交付标签；在同一可变目录手工
  挑选交付文件。均拒绝。
- 后果：私钥必须位于工具包外的保管人控制目录；00–18 号 wrapper 生成并验证
  两个白名单交付包。任何签名、双哈希、600/3,600 计数、时间链、禁用字段或
  identity 不一致均 fail closed，旧批次只读保留并创建新 identity。
- 负责人：工程代理；真实保管与签署责任属于尚待登记的第三方。

### 2026-08-02——以 standalone 工具包和逐页验证的 Word SOP 作为第三方交接面

- 决策：保管人只使用带 manifest 的 `_v2_final` standalone 工具包，从
  `D:\M3_Blind_Custodian_v2` 运行；开发者底层 CLI 只在当前仓库根目录运行。
  Word 手册必须把运行者、目录、参数、文件保管、
  失败分支和禁止事项写成可逐项勾选的操作规程。
- 背景：第三方不应依赖开发者私有对话上下文，也不能从仓库中猜测命令或手工
  组装 release；早期工具包与当前接口混用会造成版本漂移。
- 备选方案：只提供源码 README；由开发者远程代操作；继续允许旧工具包。
  均不足以建立独立、可复核的 custody chain。
- 后果：旧目录被明确标记 superseded 并由验证器拒绝；最终 Word 文档经结构、
  可访问性和 34 页视觉 QA。该交付仅验证基础设施，不把尚未发生的真人登记或
  600 条盲测伪装为完成。
- 负责人：工程代理。

### 2026-08-02——Gemini public canary 作为 1,791 矩阵前缀且 continuation 只跑 pending

- 决策：v4 canary 的 12 个冻结 work key 一旦触碰就不得在完整矩阵中重复；
  continuation 只包含其补集 1,779 条，保持原计划顺序，装箱成 1,186 个
  quota-day segment，再归入四个连续 logical shard family。
- 背景：把 canary 当作矩阵外额外任务会产生 1,803 条记录并违反终态不重试；
  按四个独立物理并发 shard 执行又会重复占用 project-level 20 RPD。
- 备选方案：完整重跑 1,791；四分片同日并发；将 1,186 日分片解释为超过四个
  正式 shard。均拒绝。四个 logical shard 是静态组织层，quota-day segment 是
  免费层执行身份层，两者不等同。
- 后果：离线 candidate manifest 为
  `2cd8e8829f77868249756cb57db62b9b497e3d4a53aa036260a755f14d4153b6`；执行仍须
  等待 canary aggregate technical pass 和逐日 exact admission。
- 负责人：工程代理。

### 2026-08-02——Gemini 免费层工期以 provider quota day 而非日历排期验收

- 决策：使用冻结计划和 18 RPD 本地上限同时报告理论下界与最坏安全装箱；
  21 天仅是目标日历，不是结果完整性的替代门。12 条 canary 是 1,791 条矩阵
  的正式前缀，continuation 只含 1,779 条。当前 public/adaptive 理论下界合计
  323 quota days，按锁定 canary 的前瞻最小值为 330 天，按每个 work/query
  的冻结最大调用数预留时为 3,194 quota days。
- 背景：1,791 条 public work item 的最大调用数合计 19,104；4,000 条 adaptive
  query 的最大调用数为 32,000。免费项目每日只有 20 次，本地正式上限 18 次，
  且公共与 adaptive 不得重复预约同一个项目配额日。
- 备选方案：启用 Billing；按 20 RPD 不留余量；并发身份绕过项目日配额；把
  429/未执行项标为完成。均违反 owner 的 free-only、USD 0、证据完整性或
  no-retry 边界。
- 后果：Gemini 正式工作将逐配额日推进，工期自动顺延；结项报告必须区分
  `pending_by_quota` 与实验失败。机器可复算 qualification manifest 为
  `31861f65d7dc38c684730d3b4c5b20c35cc76d23bdf18436d4e9f2374039a7a6`。
- 负责人：工程代理；free-only 边界来自项目所有者。

### 2026-08-02——Gemini 正式工作采用 quota-day identity 与全项目日预约账本

- 决策：public-v3 保持 0 调用并由 v4 取代。相同 12 条 canary 按冻结的每项
  `max_provider_calls` 顺序装箱为 8 个配额日片段；每段独立 run/identity/root，
  最坏 provider requests 不超过本地 18 RPD。公共和 adaptive 共用一个
  append-only quota-day ledger，同一 America/Los_Angeles 日期只能预约一次。
- 背景：免费项目的 provider cap 是 20 RPD，本地须保留 2 次。单个 VIGIL
  work item 最坏 16 calls、M3 work item 最坏 8 calls；把 12 条当作一次 run
  无法前瞻证明不跨日超额。
- 备选方案：沿用 v3 的 3,000 request 旧 override；遇到 429 后重启同身份；
  并发分片分别计数。三者分别突破真实免费额度、违反 no-retry 或重复计算项目
  配额，均拒绝。
- 后果：Gemini canary 至少占 8 个 quota days，完整矩阵按免费额度自动顺延；
  v3 wrapper 已 fail-closed。新增 quota ledger/v4 focused tests 8/8 通过，尚未
  读取 credential 或调用网络。
- 负责人：工程代理；free-only/顺延边界来自项目所有者批准的结项计划。

### 2026-08-02——DeepSeek adaptive CNY 180 在 Pro 与 Flash 间联合分配

- 决策：历史前缀 CNY 0.552805 不变；Pro-50/200/500/hardest-2000 的独立
  stage ceiling 调整为 CNY 10/20/35/85，合计 CNY 150；Flash-50/200 共享预留
  CNY 29.447195，三部分总 ceiling 精确为 CNY 180。
- 背景：原 CNY 20/30/50/79 是误按 Pro-only 总额分配，会让锁定计划中的 Flash
  adaptive 只剩 CNY 0.447195，无法形成可执行准入。
- 备选方案：增加总熔断；从公共矩阵借用预算；运行 Pro 后再临时决定 Flash。
  三者分别违反冻结的 CNY 180、工作流隔离或前瞻预算原则，均拒绝。
- 后果：未执行的 Pro-50 candidate/admission 已重新哈希绑定；历史记录、任务、
  阈值和结果均未改变。后续 Flash controller 必须证明其两个 stage ceiling
  之和不超过 CNY 29.447195。
- 负责人：工程代理；总熔断来自项目所有者批准的结项计划。

### 2026-08-02——hardest-20 对技术诊断项使用前瞻确定性补位

- 决策：预算 500 后仍按原规则排序；terminal diagnostic/incomplete task 保留
  在 ITT，但因 no-retry 不具备 2,000 饱和重放资格，选择器按固定 seed 从下一
  eligible rank 补足到 20。eligible 少于 20 时 gate fail，不人工选例。
- 背景：历史 `M3V2-D-050-A1` 在 q24 已形成不可重试的 diagnostic 终态；机械
  选入 hardest 会与冻结 no-retry 条款冲突。
- 备选方案：重试 diagnostic；只跑 19 条；看完预算 500 结果后人工补选，均会
  破坏终态、样本量或 outcome-blind 选择。
- 后果：amendment v3 已在新预算 500 结果出现前冻结并绑定 base freeze SHA；
  排序代码必须输出完整 eligible ranking，诊断项不能从 ITT 删除。
- 负责人：工程代理。

### 2026-08-02——Pro adaptive 以独立阶段根承接 checkpoint，不改写 CNY-5 前缀

- 决策：历史 8×50 adaptive 的 374 条终态查询、562 次官方调用和
  CNY 0.552805 证据保持原 policy/identity/root 不变。正式 Pro-50/200/500/
  hardest-2000 分别使用新 identity、run、query/budget/task ledger 和 trace
  root；只把来源 checkpoint 做 SHA-256 绑定的字节复制。阶段上限固定为
  CNY 10/20/35/85，连同历史成本的 Pro 理论上限为 CNY 150.552805；另为
  Flash adaptive 冻结 CNY 29.447195，总熔断为 CNY 180。
- 背景：离线回放证明把旧 ledger 直接改为 CNY 180 会改变 trace 内派生的
  `usage_summary`，从而使原本有效的证据出现 `public usage summary drift`。
- 备选方案：原地扩大 policy；忽略旧 summary；重跑 8×50。三者分别破坏
  加密绑定、弱化验证或违反终态不重试，均拒绝。
- 后果：Pro-50 只包含 32 个未触碰任务；原 diagnostic 任务继续留在 ITT 且
  不重试。后续阶段只能在前一阶段技术门通过后冻结，checkpoint 查询前缀必须
  一致。聚焦测试 8/8、Ruff、py_compile 通过；尚未发生新 provider call。
- 负责人：工程代理；成本与执行授权来自项目所有者批准的结项计划。

### 2026-08-02——Gemini 免费层矩阵按 project-level 20 RPD 自动顺延

- 决策：Gemini 3.6 Flash 继续坚持 Free tier、USD 0，按现有控制台快照的
  5 RPM/20 RPD 执行并至少保留 2 次日请求；四个逻辑分片不得并发绕过同一
  project 的日配额。首个 429 仍封存当前身份，下一 quota day 只承接未触碰项。
- 背景：截图中的 1,000 RPM/10,000 RPD 是 paid Tier-1 对照值；Free 行的
  `-995/-1.75M/-9.98K` 差值对应实际 5 RPM/250K TPM/20 RPD。
- 备选方案：启用 Billing；把 Tier-1 数值写入免费 policy；跨分片独立计算 RPD。
  三者都违反 free-only 或会超额调用，均拒绝。
- 后果：1,791 个 work item 的理论下限已超过约 100 quota days，VIGIL 多调用
  会进一步延长；21 天计划按已锁定的配额不可用条款自动顺延，不伪装完成。
- 负责人：项目所有者与工程代理。

### 2026-08-02——Flash 1,779 条 continuation 使用 policy-aware v2 与总 CNY 5 熔断

- 决策：DeepSeek Flash canary 通过后，不执行旧
  `public_sharded_continuation_v1`。新的 second-continuation-v2 从 1,791 条
  冻结计划中排除 12 条 canary，将 1,779 条按原顺序 round-robin 划分为
  890/889 两片；canary 实际成本与两片 hard ceiling 之和不得超过 CNY 5。
  每次 record/budget/trace 状态重建都必须接收同一个 exact shard policy。
- 背景：历史 primary continuation-v1 的四片数据本身有效，但 append 后调用
  generic state reader 时回退到了 CNY 20 全局 policy，因而以
  `public usage summary drift` 终止。该问题与模型结果无关，且旧根已永久封存。
- 备选方案：复用 v1 second 路径；原位修复 v1；给 Flash 分配新的额外预算。
  前两项不能证明旧源码/新语义边界，后一项违反用户锁定的 CNY 5 公共矩阵
  熔断，均拒绝。
- 后果：新控制器的策略传递回归测试 4/4 通过；在 canary review、候选和每片
  exact-command admission 生成前保持惰性。任何 diagnostic/budget seal 后都
  不允许同 identity 重启，只能以新版本处理从未触碰的 pending items。
- 负责人：工程代理；预算与执行边界来自项目所有者批准的结项计划。

### 2026-08-02——Gemini public-v1 在执行前由 JSON-commitment v2 取代

- 决策：保留已写入的 Gemini public-v1 candidate/admission，但禁止执行；
  以新的 v2 run、execution identity、admission 和 output root 执行 canary。
  v2 的每个 OpenAI-compatible payload 都显式包含
  `response_format={"type":"json_object"}`，并在 transport 前把该字段纳入
  canonical payload SHA-256。VIGIL 的 JSON constraint path 也必须在注入
  transport 下完成一次端到端解析和 ALLOW/ASK/DENY 资格化。
- 背景：历史 Gemini fallback canary 因 VIGIL constraint generation 回退而
  fail closed。源码审计发现 VIGIL facade 验证了 JSON 请求，但通用 Gemini
  client 丢弃该字段；直接执行 v1 会重现已知风险且其 payload commitment
  无法证明真实请求包含 JSON 控制。
- 备选方案：原位修改 v1；在 transport 层无痕注入字段；直接执行后再解释。
  三者都会让 admission、预调用哈希或版本边界失真，均拒绝。
- 后果：`gemini_public_canary_v1_supersession_review.json` 证明 v1 输出根中
  非空文件、provider call、network call 均为 0；v2 离线 JSON/VIGIL 测试
  通过后才有资格执行。Gemini 仍为 free-only、USD 0、retry 0、tools/effects 0。
- 负责人：工程代理；执行授权来自项目所有者批准的 21 天结项计划。

### 2026-08-02——Gemini public-v2 在执行前由 shared-usage v3 取代

- 决策：v2 同样保持 0 调用并写入 supersession review；正式技术 canary 改用
  v3。v3 为同一 run 内按 work item 创建的 traced clients 注入唯一共享的
  `GeminiUsageRegistry`，使每条 receipt 的 provider 累计 requests/tokens 与
  run 级前缀一致，同时各 record bundle 仍只保存自己的调用证据。
- 背景：离线审计发现官方 `ProviderBudgetState` 在 run 内共享，但 v2 trace
  wrapper 的 prior usage 只来自当前 work item。第一条可以通过，第二条必然把
  provider 的累计 request=2 与本地 prior=0 比较，从而产生错误的 evidence
  failure。这一缺陷在网络前被发现。
- 备选方案：让每个 work item 使用独立 provider budget；忽略累计 drift；运行
  v2 后再修复。三者分别破坏总配额控制、证据算术或前瞻版本边界，均拒绝。
- 后果：新增两 work-item/两 official-fixture-call 的零网络资格工件，累计
  requests 严格为 1、2；v3 focused suite 5/5、JSON client suite 6/6 通过。
  v1/v2 output roots 都保持空，admission 不删除、不改写、不执行。
- 负责人：工程代理；执行授权继承项目所有者的结项计划，但结果准入仍独立。

### 2026-08-01——实验结项扩展采用新版本，历史冻结和 v7 abort 不恢复

- 决策：21 天结项扩展在新版本化计划、controller、admission 和输出根中实现；
  `public_execution_plan_v1.jsonl`、`adaptive_attack_freeze_v1.json` 及历史
  `formal_matrix_controller_v7` 失败链保持字节不变。v7 只做只读复验。
- 背景：用户要求补齐 Flash、Gemini、三模型 adaptive、hardest-20 和第三方
  600 条盲测，但现有 v7 已由 v8/v9 取代，Gemini public/adaptive 尚无正式链。
- 备选方案：恢复旧 v7；原位扩写 v1 冻结；把 Gemini 诊断结果提升为正式结果。
  三者都会破坏前瞻身份或证据等级，均拒绝。
- 后果：新增工作必须从零网络离线资格开始；负面结果可结项，证据链或完整
  Harness 失败不可结项；第三方候选到位前开发者不得生成盲测内容或标签。
- 负责人：项目所有者与工程代理。

### 2026-07-30——Adaptive v1 单查询根不可复用，v2 仅用正式 decision 字段

- 决策：adaptive cost-canary v1 的 1 条终态 query 虽然 trace/usage/cost
  完整，也不得在 v2 中复用。v2 使用新 run/execution/output identity，
  MCTS decision 只能来自 public record 契约的
  `initial_guard_decision`；旧 `effective_guard_decision` 名称禁止兼容回退。
- 背景：v1 已在 provider call 和 terminal query 落盘后才触发 KeyError。
  若原根恢复，会在缺失 checkpoint 的情况下重新解释已终态 query；若 v2
  复用该 query，会形成看过一次攻击反馈后的选择性跨版本样本。
- 备选方案：给 v1 增加字段别名后续跑；把首条 query 导入 v2；删除旧 query
  后重跑。三者分别改写冻结实现、跨版本复用结果或破坏 append-only 证据，
  均拒绝。
- 后果：披露 CNY 0.002271 失败成本；v2 新上限仍为 CNY 5，总规划上界
  CNY 5.002271。formal continuation 和 result admission 均须等待 v2
  outcome-blind technical review。
- 负责人：项目所有者与工程代理。

### 2026-07-30——Public continuation-v1 四片永久封存，v2 必须 fresh rerun 全分区

- 决策：continuation-v1 的 4 条已完成记录不能在修复版中复用；四个 v1
  run/output/execution identities、admissions 和 ledgers 永久封存。
  continuation-v2 必须用全新身份重新执行全部 5,058 条，同时把精确
  CNY 4.9 shard policy 传入每次 state reconstruction。
- 背景：四片均在完成首条正式记录后暴露同一个纯工程错误。provider
  usage/cost、trace 和 record 本身有效，但 record 构造与事后重建分别使用
  4.9 和 20.0 元 ceiling，导致 summary drift；四片均已形成不同版本的
  terminal 证据。
- 备选方案：复用 4 条有效 record、原位修改 v1、或只补跑 5,054 条。
  全部拒绝，因为会把实现修复与跨版本选择性结果复用混在同一正式样本中。
- 后果：额外实际成本 CNY 0.014446 作为失败成本披露；v2 fresh cap 为
  CNY 19.6，连同 canary 和旧失败的 primary 计划上界为
  CNY 19.6666272。scientific outcome 保持封存，只有四片技术门和主角色
  merge 通过后才能另建结果准入。
- 负责人：项目所有者与工程代理。

### 2026-07-28——Public-v2 部分执行永久封存，M3 修复必须使用 Public-v3 身份

- 决策：Public-v2 在 12 条完整记录后留下一个开放 M3-v2 attempt，故永久
  不恢复、不重试、不补写、不进入结果准入。其 29 次已完成 provider calls、
  12 条 record 和开放 attempt 的 2 次孤立完成调用由内容无关 abort review
  哈希锁定。M3 resolver 修复只能进入新的 Public-v3 run/output/execution
  identity、candidate 和 admission。
- 背景：Public-v2 正确修复了 AgentDojo public-plan binding，却继续用默认
  `FrozenM3CaseResolver()` 读取 medium plan。前 12 条 AgentDojo 成功，
  首条 public M3 key 在离线 evaluator 阶段失败。
- 备选方案：恢复 v2、给开放 attempt 补 terminal，或复用已完成 12 条作为
  新版本正式结果。全部拒绝，因为会破坏 append-only 单次执行语义或形成
  跨版本选择性复用。
- 后果：科学分保持不变；Public-v3 必须先完成公共 M3 resolver 的跨角色/
  攻击-良性零网络资格化和当前工作树完整 Harness，再请求新的 owner
  exact-command 授权。
- 负责人：项目所有者与工程代理。

### 2026-07-28——Public-v1 开放 attempt 永久封存，Public-v2 使用新身份修复

- 决策：Public-v1 在首个 work item 留下 hash-valid `started` 后永久停止；
  不恢复、不重试、不补写 terminal。通过独立零调用 abort review 保留失败，
  另建 Public-v2 resolver、candidate、schema、controller 和全新的
  run/output/execution identities。旧 owner 命令确认不得跨版本复用。
- 背景：第一次本地失败发生在 attempt loop 前；补齐 PromptGuard 依赖后，
  同一命令的一次非自动重试证明 medium AgentDojo resolver 无法解析
  public-plan work key。虽然 provider 调用为 0，但继续使用同一 ledger 会
  破坏 append-only attempt 语义。
- 备选方案：删除 open event 后重跑；把 public work key 注入冻结 v1；
  将 medium resolver 的内部索引视为 public identity。三者都会重写证据、
  修改已批准执行包或掩盖绑定缺口，均拒绝。
- 后果：v1 作为 `aborted_before_first_provider_request` 的负工程证据保留；
  v2 从每条 public row 的冻结 `source_reference` 恢复原 AgentDojo binding，
  通过四个离线探针和 11/11 聚焦测试。v2 仍需更新后的完整 Harness 和新的
  exact-command owner admission，科学分数保持 753/1200。
- 负责人：Codex。

### 2026-07-28——引文元数据必须逐条权威核验，80% 路线使用新版本纠正算术

- 决策：34 条文献逐条打开 publisher/proceedings/DOI/arXiv 权威记录；
  无法核验或错绑条目不得静默保留。L20 用经 ICSE 2026 官方页面/DOI
  核验的 AgentSpec 替换；完整纠正轨迹、矩阵和 manifest hashes 入稿。
  历史 evidence-80 v2 不原位修改，新建 v3 表示当前 753→968 路线。
- 背景：全面审计发现 18 个非规范标题、1 个无依据 Oral 标记、2 个过期
  预印本分类，以及 L20 URL 实际指向无关生物医学论文。另发现 v2 计划表
  把当时应为 690 的“其他九项”写成 620，导致表内总和为 660 而不是 730。
- 备选方案：仅审计十篇核心论文；按标题猜测 L20；直接改写历史 v2；忽略
  表内算术。这些方案分别留下引用风险、制造虚假来源、破坏版本轨迹或夸大
  完成度，均拒绝。
- 后果：当前矩阵为 24 PR/10 PP，scorecard 为 753/1200；v3 以 public
  +90、adaptive +100、manuscript +25 达到 968/1200。全文 inline contexts、
  bibliography、投稿日刷新、public/adaptive、盲测和 JCR 仍为硬缺口。
- 负责人：Codex。

### 2026-07-28——稿件采用 v2 mechanism-quality 与 v6 technical-admission 双门，不沿用零失败旧语义

- 决策：Methods 分别报告 `medium_gate_spec_v2` 的 mechanism-claim quality
  envelope（overall ≤10%、provider/timeout ≤5%、runner=0）和 combined
  gate v6 的技术准入（480 coverage、0 open/runner、≤1% closed diagnostic、
  formal exact identity/trace）。旧 zero-operational-failure 值仅作历史描述。
- 背景：结果稿已正确保留 21 个 ITT terminal failures，但 pre-result Methods
  仍沿用早期“零失败才能通过”的句子，构成真实执行与论文方法的不一致。
- 备选方案：把 21 个失败删出分母；回退或改写冻结 gate；维持含糊“无运行
  失败”叙事。三者都会破坏 ITT、冻结身份或方法真实性，均拒绝。
- 后果：admitted medium 仍为 479 formal-candidate + 1 diagnostic、459
  completed + 21 retained terminals；机制路线仍因 utility/module gates
  fail_redirect。正式 Stage 2.5 仍需完整引用与 public/adaptive 结果。
- 负责人：Codex。

### 2026-07-28——自适应攻击采用 untrusted-content-only 投影与 query/call 双台账

- 决策：8×50 成本 canary 只改变 M3-v2 `untrusted_content`，保留可信任务
  与 `auto_compiled` authorization；每个 query 使用 Windows-safe 唯一
  work key，并以 query ledger + provider trace/budget ledger 记录一对多
  调用关系。该 canary 使用独立 Pro CNY 5 fuse，不复用公共 Pro CNY 20
  角色上限。
- 背景：原 MCTS runner 只有搜索 checkpoint，无法证明一个 attacker query
  对应多少官方模型调用、费用和 response IDs，也无法用中型/公共 work key
  resolver 评估动态 mutation。
- 备选方案：把整个 case 或 gold action 放入在线 oracle；只记录 MCTS
  checkpoint；对 trace 文件名静默替换冒号。三者分别会造成标签泄漏、调用/
  成本证据缺失或执行身份与文件身份分叉，均拒绝。
- 后果：query start 必须先 fsync，terminal 才可绑定科学 record；任何 open
  query/call、身份/哈希/费用漂移都会暂停。canary prefix 和 75,000-query
  continuation 仍须独立 admission，技术审查不汇总 scientific outcomes。
- 负责人：Codex（live exact-command approval 仍归 owner）。

### 2026-07-28——公共矩阵使用独立版本化适配层，不改写中型冻结验证器

- 决策：public-v1 复用中型 runtime/effect boundary，但预算、模型角色、
  trace/record store、candidate/admission 和 result gate 使用新的版本化
  模块；不修改已被冻结且硬编码 Pro/480 语义的中型验证器。
- 背景：公共矩阵需要同时支持 Pro 与 Flash、6,873 条记录和角色级预算，
  直接放宽旧验证器会改变 v1–v9 历史证据语义并破坏既有哈希。
- 备选方案：原位扩展旧 budget/record validators；该方案会让过去的冻结
  证据随当前实验需求漂移，拒绝采用。
- 后果：公共链可独立验证精确模型、角色预算、官方 receipt 和 append-only
  交叉绑定；Flash 只能支持跨模型结论。代价是存在少量公共适配代码，且旧
  Harness 的递归历史 verifier 仍有显著性能债。
- 负责人：Codex（owner 命令确认仍为 live execution 的独立门禁）。

### 2026-07-27——80% 主路径改为公共扩展优先，Flash 解除第二模型吞吐阻塞

- 决策：在任何新实验前冻结
  `evidence_80_execution_roadmap_v2.json`。80% 的可计分路径只由正式公共
  基准 10→100、自适应攻击 0→100 和 manuscript 30→70 构成；其他工作流
  不预先加分。执行顺序从旧的“自适应优先”改为“公共扩展优先”。
- 背景：公共冻结已明确为 6,873 条，但缺少 paper-v2 controller/result gate/
  analyzer；自适应虽有 provider-agnostic MCTS core，却缺少 official bridge、
  durable query/call 双账本和结果门，且 75,000 查询面板的费用尚无法从中型
  实验直接外推。公共扩展的费用可用已录取中型条件级数据估计，中心约
  CNY 12.03、建议硬熔断 CNY 25，因此更适合作为下一证据阶段。
- 模型选择：DeepSeek `deepseek-v4-pro` 为主模型，
  `deepseek-v4-flash` 为正式吞吐型第二模型；后者只支持跨模型、不支持跨
  提供商声明。Gemini v3 保留为免费层多日跨提供商增强，不作为达到 80% 的
  必要路径，避免 20 RPD 成为主计划单点阻塞。
- 后果：当前分数仍为 61%，实验执行授权仍为 false。owner 确认新版计划后先
  实现纯离线阶段 A；完整 Harness 全绿后才运行公共 canary。自适应先进行
  8×50、CNY 5 的 outcome-blind 成本 canary，再冻结正式费用门；预测超过
  CNY 180 或余额不足时单独暂停确认。

### 2026-07-27——Gemini v3 采用免费层多日调用熔断，单次恢复测试不准入结果

- 决策：未来 Gemini v3 只使用 dedicated project 的 Free tier；以 provider
  5 RPM/250K input TPM/20 RPD 为外部上限，以 4 RPM/200K TPM/18 RPD/
  16K output tokens/day 为本地上限并保留 2 RPD。所有正式调用必须由
  Pacific-day 持久化计数器在 transport 前记账，仍保持 USD 0、并发 1、
  0 retry、0 provider tools 和 0 external effects。
- 背景：owner 解绑 paid billing 后，项目页明确显示 Free。唯一一次固定
  SAFE 诊断恢复为 HTTP 200 且 exact model/output 匹配，但 Google 未返回
  request ID，因而没有满足正式请求链的完整性要求。
- 备选方案：继续使用历史 Tier 1 数值、恢复 Gemini v1/v2、在一天内跑完
  192-item 路线，或把本次 HTTP 200 当成跨模型科学结果。这些方案分别造成
  过期配额假设、冻结证据污染、RPD 超限和证据等级夸大，故拒绝。
- 后果：历史 v1/v2 和旧 quota snapshot 保持不可变；新 snapshot/override/
  connectivity artifact 只约束 prospective v3。v3 必须新建 controller、
  candidate、owner admission 并跨多日调度；本次诊断 result-ineligible，
  科学完成度保持 61%。

### 2026-07-27——Gemini v1/v2 不恢复，报告后优先补自适应与公共证据

- 决策：Gemini v1 和 v2 均冻结为不可恢复版本。v1 的 VIGIL 静默 fallback
  不能包装成正式 structural result；v2 首请求 HTTP 429 后不得重试或续跑。
  配额恢复后只能新建 prospective v3。完成阶段报告后，证据增益顺序固定为：
  冻结论文主表/主张、自适应攻击、公共扩展、Gemini v3、独立盲测与投稿核验。
- 背景：DeepSeek 中型门禁已经否决机制主路线；当前最重要的是检验该负结果和
  安全—效用权衡在防御感知攻击和公共数据上的稳定性。Gemini 两个失败版本提供
  了运行边界，但没有任何可准入的跨模型科学结果。
- 备选方案：重试 v2 429、把 v1 fallback 降级后继续、先大规模调用 Gemini，
  或用报告/代码完成度替代外部证据。这些方案分别违反 0-retry/frozen identity、
  基线忠实度、prospective admission 和 no-false-completion 规则，故拒绝。
- 后果：科学完成度保持 61%。自适应攻击先做 8×50 成本 pilot，再决定冻结
  正式 fuse；所有攻击继续使用模拟工具和隔离 effect backend。公共冻结的
  6,873 条记录按既定 cell 执行，不能依据结果临时删 suite。Gemini v3 若无
  忠实结构化条件，只能支持 M3 模块方向性，不得支持最强基线领先主张。

### 2026-07-27——阶段报告采用结构化 QA fallback，不宣称整页渲染通过

- 决策：交付新的 2026-07-27 DOCX，同时明确本机无 LibreOffice 导致 canonical
  page-render QA 不可用。报告必须通过 ZIP/OOXML、页面与表格几何、重复表头、
  real numbering、accessibility、图片 alt、超链接、占位符/凭据模式和清洁
  交付检查；6 张图按原始分辨率逐张人工检查。
- 背景：bundled `render_docx.py` 在打开 DOCX 前因找不到 `soffice` 返回
  `WinError 2`。documents skill 明确允许在这一特定环境缺失下采用结构 fallback，
  但禁止暗示已经通过渲染门。
- 备选方案：不交付报告、安装未授权系统级 LibreOffice，或把旧 2026-07-26
  页面预览当作新报告 QA。三者分别阻塞当前用户优先事项、扩大环境变更范围和
  造成证据错误，故拒绝。
- 后果：最终报告记录结构 QA 通过、6 图人工检查通过和 page-render unavailable；
  不报告页数，也不声称 Word/LibreOffice 逐页视觉布局已验证。

### 2026-07-26——Gemini 第二模型采用三条件、四链、free-only prospective 复现

- 决策：第二模型不重复六个条件，而是严格执行冻结计划中 structural baseline、
  M3 policy-only 和 M3-full 的全部 264 行；这与既定 second-model 设计一致，
  并保留 48 条授权 regime 探针。使用独立 Gemini identity 和四条 append-only
  证据链，三条件 canary 技术审查通过前不得续跑或读取 scientific outcomes。
- 背景：DeepSeek medium 已触发 empirical fallback；下一项最高证据增益是验证
  安全—效用与 module-gain 负结论能否跨模型复现。Gemini 官方兼容端点提供精确模型、
  response ID、request-ID header 与 usage，但原 DeepSeek trace bundle 含
  provider-specific cache/cost 字段，不能伪装成 Gemini 证据。
- 备选方案：复用 DeepSeek trace schema、只保存最终 attestation、直接运行 264 行，
  或扩大到六条件。前三者分别造成证据语义造假、调用链缺失和跳过技术门禁；六条件会
  增加约一倍 API 消耗，却不增加 fallback 主比较所需的核心跨模型证据。
- 后果：Gemini v1 使用 generic call receipt + safety sidecar，而不是 DeepSeek
  trace bundle；免费额度下本地上限 3000 requests/20M input/2M output，首个
  429 暂停、0 retry、0 cross-provider fallback、USD 0。candidate 冻结后如有缺陷
  必须新建版本，不能改写。

### 2026-07-26——按预注册门禁切换为授权泄漏/不确定性实证论文

- 决策：保留 DeepSeek medium 的全部正负结果，并停止以“新模块带来独立防御
  增益”为主叙事。后续正式路线改为授权信息、授权不确定性与安全—效用权衡的
  系统实证研究；M3-full 作为测量/对照机制，而不是已证明领先的主贡献。
- 背景：准入的 480 条结果中，M3-full 相对 structural baseline 将 unsafe
  effect 从 8/36 降为 0/36，但 benign-tool TCR 从 12/24 降为 6/24；
  M3-full 与 policy-only 均为 0/36 unsafe effect，因此预注册的
  utility noninferiority 和 module gain 均失败。
- 备选方案：只强调安全点估计、删去效用任务、把 ASK pending 假设为用户同意，
  或在同一数据上调参后恢复机制主张。这些方案会违反 ITT、预注册止损与
  claim–evidence 完整性，故拒绝。
- 后果：C07/C08 对冻结 medium 数据永久标为不成立；任何新机制主张必须来自
  新 prospective 实验且不得覆盖本负结果。近期资源转向 Gemini 第二模型、
  授权 regime 扩展、公共外部效度和自适应攻击。

### 2026-07-26——冻结 v8 部分证据，以 pending-only shard 完成预注册矩阵

- 决策：v8 在 303/480 时由一条闭合 `ProviderTransportError` 暂停后永久保持
  不可变且不再执行。新建 v9 remainder shard，只包含 v8 的 177 个从未启动
  work key，使用独立 run/output/append-only ledger。v9 允许人工触发后续
  pending-only segment，但不会选择任何 terminal work key，故不构成失败项或
  成功项重试。新建 prospective combined result gate v6，在 v9 API 前锁定
  303+177 的无交集/无遗漏契约；科学分析只能在两 shard 合计 480、0 open、
  诊断保留 ITT 且身份/安全/预算门通过后独立准入。
- 背景：v8 控制器的冻结 continuation 入口只接受恰好 6 条 canary 起点；运行中
  的闭合 provider diagnostic 会终止当前进程，因此无法合法续跑 177 个未执行项。
  删除诊断、重跑 v8 或把 303 条复制到新 run 都会破坏 append-only 身份与 ITT。
- 备选方案：重跑完整 480；修改已冻结 v8；丢弃诊断；直接分析 303 条；或停止
  中型实验。前四项分别造成选择性重试、冻结漂移、分母污染或不完整矩阵；完全
  停止则无法验证预注册中型门。
- 后果：v8 的 302 formal-candidate + 1 diagnostic 保持原位，失败项不得重试；
  v9 candidate/admission 与 gate-v6 candidate 均在任何新 API 前冻结。若 v9
  再出现闭合诊断，当前进程停止，后续人工 segment 只能消费尚未 terminal 的项；
  combined diagnostic 超过 1% 上限时机制论文主张失败关闭。

### 2026-07-26——v7 API 前先冻结可消费哈希化拒绝证据的 result gate v4

- 决策：保留 v7 matrix candidate/admission 不变，新增 result gate v4，绑定
  controller-v7、boundary-rejection-runtime-v3、proposal-message digest
  资格和未来唯一 canary review。v4 在结果不可见条件下冻结，只有完整离线审计
  通过后才允许一次 v7 canary。
- 背景：v6 因 producer 生成的 boundary rejection evidence 与 evaluator
  consumer 契约不一致而中止；已有 result gate v3 只锁定 v6/runtime-v2，无法
  证明 v7 新哈希证据在结果准入阶段仍被验证。
- 备选方案：直接复用 v3；先跑 v7 canary 再补 gate；或修改 v7 已冻结 candidate。
  三者分别造成证据遗漏、结果后设门槛或冻结身份失效。
- 后果：新增版本化 gate/schema/qualification/candidate/tests；v1-v7 执行历史和
  v1-v3 gate 保持不可变。API 许可不覆盖门禁跳过，Gemini 不与 DeepSeek canary
  并发。

### 2026-07-24——真实身份 smoke 失败不重试，不为通过门禁弱化双 ID 合同

- 决策：一次性官方身份资格严格保留首个结果。DeepSeek 即使已证明官方端点、
  精确模型、response ID 和 usage，也因缺 request-ID header 保持
  `diagnostic_only`；Gemini 首次 `ProviderPausedError` 后立即暂停。不得自动重试、
  跨供应商补跑、把 response ID 重命名为 request ID，或修改 schema 来制造
  `formal_candidate`。
- 背景：官方 Gemini 文档把 429 解释为项目级 RPM/TPM/RPD/额度门禁，并要求在
  AI Studio 查看 active limits；DeepSeek 公共 API schema 提供响应体 `id`，但没有
  对 request-ID 响应头作公开保证。当前证据不足以满足冻结的完整请求链合同。
- 备选方案：等待后自动重试 Gemini；以 response ID 单独升级 DeepSeek；或完全
  丢弃失败 smoke。前三者分别违反零自动重试、降低预注册证据标准或损失透明诊断。
- 后果：脱敏 artifact 和 v3 preflight 均保留真实失败，0 个正式结果；
  `gate_pass=false`。未来只有在 Gemini quota 或 request-trace 条件实质改变并获得
  新的明确授权后，才允许新的资格尝试。

### 2026-07-23——正式结果与逐步事件同链追加，失败证据不因身份不完整而丢弃

- 决策：每个终态 work item 将 experiment record 与 sanitized runtime events
  放入同一 append-only JSONL entry，绑定 execution/work/run/record identity 和
  多层 SHA-256；追加前复验完整链，成功写入后 flush+fsync。live 成功或 refusal
  只接受 `formal_candidate`，但 operational failure 可保留为 `diagnostic` 并强制
  留在 ITT。
- 背景：只持久化汇总 record 会失去逐步 Guard/执行证据；反之保存原始模型/工具
  正文会扩大敏感与注入内容暴露面。若强制所有失败都拥有完整 provider 双 ID，
  传输超时等恰恰会因为无 response ID 被错误排除。
- 备选方案：分别维护 record/event 两个无原子绑定的文件；保存 raw trace；或拒绝
  无双 ID 的失败。三者分别产生跨文件漂移、内容泄漏或 ITT 选择偏差。
- 后果：日志可从单链恢复且保留失败分母，raw prompt/response/observation 只形成
  摘要；临时 stub disk replay 只证明工程路径，不是正式结果。v3 preflight 仍需
  live condition、Gemini quota 和 live provider 双 ID 三项门禁。

### 2026-07-23——Python 3.13 项目依赖优先满足，不改动互斥的非项目工具

- 决策：在 `F:\robot\Anaconda3\python.exe` 可见的 Python 3.13 用户 site 中安装
  Ruff 0.15.22，并使用 Pillow 10.4.0 满足仓库 Dashboard 及当前 moviepy/python-fx
  约束。保留既有 pdfplumber/PySSTV，不为追求全局 `pip check` 全绿而擅自降级或
  卸载它们。
- 背景：F 盘 base site 对当前账户不可写，pip 自动落到 Python313 用户 site。
  已有依赖形成不可同时满足的 Pillow 约束：项目侧需要 `<11`，PDF/SSTV 工具需要
  `==12.2.0`。
- 备选方案：改动非项目工具版本；恢复 Pillow 12.2 并让项目 Dashboard 元数据冲突；
  或新建完全隔离的 Python 3.13 venv。本次用户要求把项目缺失依赖装到当前 3.13.5，
  因此选择最小项目侧修复，隔离 venv 留作未来需要。
- 后果：`python -m ruff` 现在可由 Python 3.13.5 直接运行，核心研究/测试导入与
  全量 Harness 通过；`pip check` 的两个非项目冲突必须继续披露，不能写成环境
  全局无冲突。

### 2026-07-24——在线条件执行与离线结果判定分离，正文在记录边界前脱敏

- 决策：六个正式条件共用严格的 `OnlineExecutorContext`，只接收 execution/work/
  benchmark/condition 身份、调用上限和冻结 online state；case type、primary
  eligibility、offline labels/source/result fields 不得进入 runtime。原始 prompt、
  response、observation、headers 和 credentials 在 experiment-record 边界前转换为
  SHA-256/字节长度或直接删除，离线 evaluator 只在 runtime 完成后运行。
- 背景：已有 v2 计划能证明条件级初始可见状态，但尚无统一执行边界来证明六个条件
  在真实运行时没有读取 evaluator 字段，也没有统一的多步内容持久化规则。
- 备选方案：让每个 baseline 自己组装完整 experiment record；或保存原始模型正文
  供后处理。前者容易产生字段泄漏和指标漂移，后者扩大秘密/提示注入内容的持久化
  面并违反当前证据最小化策略。
- 后果：12 个 benchmark×condition 组合已用 injected no-effect runtime 离线资格
  验证，六条件全部注册且事件脱敏通过；这只证明执行契约，不证明 live baseline
  忠实度或效果。v3 preflight 继续 `gate_pass=false`，需完成 live provider/
  PromptGuard/VIGIL/effect/evaluator 与持久化日志资格后才能请求正式矩阵授权。

### 2026-07-24——供应商收据按真实传输和双 ID 分级，不把离线桩或缺 ID 调用提升为正式证据

- 决策：DeepSeek/Gemini 官方执行层每次只发起一次调用，无自动重试、无 provider
  tools、无跨供应商 fallback。注入 transport 的回执只能映射为
  `local_qualification`；真实官方网络调用只有在返回模型精确匹配并同时具备
  request ID 和 response ID 时，才能映射为 experiment record 的
  `formal_candidate`。缺 request ID 时即使 response ID 支持模型身份核对，也必须
  降为 `diagnostic_only`。
- 背景：离线 transport fixture 可以验证 URL、payload、usage 和预算解析，却不能
  证明供应商真实响应；先前 connectivity smoke 又表明两个官方兼容端点都可能不在
  HTTP 头返回 request ID。若只凭精确 model/response ID 提升，会违反现有正式记录
  契约并混淆“身份可核对”和“请求链完整”。
- 备选方案：把任何官方 endpoint + response ID 视为正式；或要求 request ID
  缺失时整体拒绝保存。前者证据等级过高，后者会丢失可用于诊断的透明记录。
- 后果：`provider_receipt_to_attestation` 显式执行降级；v3 preflight 绑定预算、
  安全、合同、schema 和执行代码，同时保持 `gate_pass=false`。DeepSeek/Gemini
  仍各保留完整 480 项目标，但六条件执行器、日志复核、Gemini quota 快照和每家
  一次 live no-effect qualification 未完成前不得启动正式矩阵。

### 2026-07-24——LFischl 环境只用于兼容工具，完整仓库使用 Python 3.12+

- 决策：保留 `F:\Anaconda3\envs\LFischl` 用于 Ruff 和可兼容的隔离测试，不升级
  或改写其 Python 3.9 解释器；完整项目验证使用现有 Python 3.13.5，并把当前项目
  最低版本说明修正为 Python 3.12+。
- 背景：LFischl 已有多数数据/校验依赖，本轮补装 `pytest 8.4.2` 后，新的供应商
  执行器 13/13 通过；但全仓收集暴露 PEP 604、`tomllib` 和 PEP 701 兼容错误。
  其中 PEP 701 需要 Python 3.12，不能靠安装缺包解决。
- 备选方案：原地升级 LFischl；或把整个仓库回写成 Python 3.9 语法。两者都会
  干扰该环境的其他用途或改动大量冻结/历史代码。
- 后果：后续 lint 可优先调用 LFischl 的 Ruff；全量 pytest/Harness 使用
  Python 3.13.5。环境名称因两套 Conda 安装不能由当前 `conda run -n` 解析，按
 绝对解释器路径调用，不影响环境可用性。

### 2026-07-23——DeepSeek 保留完整 480 项目标，以实际缓存计费熔断而非缩小样本

- 决策：DeepSeek `deepseek-v4-pro` 和 Gemini `gemini-3.6-flash` 均以独立的
  完整 480 项中型矩阵为研究目标；分块只用于 100-call 级断点、实际 usage 结算和
  额度止损，不把首块改称小规模研究，也不在同一模型矩阵内跨供应商补跑。
- 背景：用户说明 DeepSeek 缓存命中率通常较高并明确不希望只跑小规模子集。按
  4,416-call、34,407,984 输入 token、2,260,992 输出 token 的原冻结上界和
  2026-07-23 官方价，90% 聚合命中约 CNY 24.662527，88% 约 CNY 26.709802，
  85% 约 CNY 29.780714；在 CNY 27 熔断线下所需最低命中率约 87.7165%。
- 备选方案：先固定 20 case/60 work item；或仅凭历史缓存经验直接授权 480 项。
  前者改变用户指定目标，后者可能耗尽用户声明的 CNY 30 余额。
- 后果：正式执行器必须在每次 DeepSeek 请求前按最坏 cache-miss 的下一请求检查
  余量，并从响应记录 hit/miss/output token；累计观测输入达到 500,000 token 后，
  若全量投影超过 CNY 27 即暂停。Gemini 仅允许 free tier、付费上限 USD 0，
  首个 429 暂停且零自动重试。两家均只发送合成/公共非敏感内容、禁用 provider
  tools 和外部副作用。该预算批准不等于正式执行授权。

### 2026-07-23——源码审计不支持领域级 Answer-Key 叙事，默认使用中性标题

- 决策：20 个限定版本、限定入口的 online-state 审计结果只能作为逐实现发现；
  在 claim-ready=0 且独立第二复核=0 时，不声称“领域普遍存在 oracle
  authorization”，不使用 Answer-Key 主标题，不声明 first/only/SOTA。
- 背景：审计观察为 9 个 `no_online_gold_observed`、9 个
  `not_a_runtime_guard`、1 个 path-dependent 和 1 个 inconclusive，无法支持原
  预设叙事。源码证据必须优先于论文计划中的假设。
- 后果：论文默认定位为 provenance-aware runtime authorization 的评估与机制；
  oracle regime 仅作为受控 ablation。未来只有独立复核和新增源码证据才能修改
  此边界。

### 2026-07-23——样本唯一性、工程完成度与科学完成度分开计量

- 决策：AgentDojo 正式计划使用其实际 97 个唯一良性任务，不复制样本满足名义
  150/100 下限；完成度分别报告 engineering/research readiness 85%、scientific
  evidence 31%、submission readiness 38%。
- 背景：复制样本会虚增分母和功效；把协议、适配器、表壳完成度等同于论文完成度
  会隐藏 480 条中型记录、6,873 条公共记录、自适应运行和盲测仍为空的事实。
- 后果：F-PAPER-002 继续 `in_progress`。没有真实记录时统计器返回
  `results_pending`，Results 表保持 pending，任何外部汇报不得只引用 85%。

### 2026-07-23——外部身份、成本和独立保管门禁不得由本地占位替代

- 决策：未固定可审计 provider/model 身份和硬成本上限时不启动 480 条中型运行；
  中型门禁未通过时不扩张 6,873 条公共计划；没有第三方 custodian、候选哈希和
  保管链时，只能称为 content-free blind authoring kit。
- 背景：中转站身份不透明、收费 API 无上限和开发者自建“盲测”都会让结果不可审计。
- 后果：provider/cost 模板不得保存密钥。官方 API 或可证明上游身份、请求 ID、
  参数稳定和无提示改写的网关才可进入正式证据；其余结果最多为 diagnostic。

### 2026-07-23——paper-v2 结果先通过严格证据契约再进入分析

- 决策：paper-v2 每条运行记录必须保存授权 regime、在线可见字段名和值摘要、
  ASK/确认状态、unsafe effect、task completion、operational status 和 provider
  attestation。超时、解析、最大步数、provider/runner failure 全部留在 ITT 分母，
  且在主安全终点中保守记为失败；未验证中转站最多是 diagnostic。
- 背景：paper-v1 的主要风险是指标语义、在线/离线字段边界和提供方身份可能在不同
  adapter 中漂移。只在分析阶段补救会使不可比结果进入证据链。
- 备选方案：保留宽松 JSONL，事后按脚本解释；或直接复用 paper-v1 run log。前者
  无法 fail-closed，后者缺少 paper-v2 的授权 regime 和 provider identity。
- 后果：正式候选必须来自 official API 或 auditable gateway，并有请求/响应 ID、
  verified identity 与无 prompt rewrite 声明；正式 admission 还需独立 manifest
  哈希。现有公共运行时接口不变。

### 2026-07-23——历史身份漂移测试验证拒绝，不伪造旧版本可运行性

- 决策：旧 Progent/Task Shield freeze 遇当前共享 helper 或保护哈希漂移时，回归
  测试必须断言 fail-closed；只在临时测试副本中更新 helper hash 以继续验证更后面的
  partial-admission 禁止。旧 freeze、旧预检和输出不修改。
- 背景：六项旧测试把“当前共享代码仍等于旧冻结字节”当成应通过条件，但当前事实
  已明确存在合法的新版本漂移。把旧 freeze 改到当前 hash 会破坏时间顺序。
- 后果：全量测试可以验证真实历史边界并保持全绿，但这不把旧失败预检重新定义为
  成功，也不授权恢复历史 root。

### 2026-07-23——建立 paper-v2 双主线而不改写 paper-v1

- 决策：新增 `protocols/paper_upgrade_v2/`、`experiments/paper_v2/`、
  `schemas/paper_v2/` 和 `docs/research/paper_v2/`，以“授权信息泄漏/授权
  不确定性评估 + 非 oracle 权限单调运行时机制”为论文双主线。paper-v1 的冻结、
  原始结果和哈希绑定适配器保持不可变。
- 背景：ACL 2026 VIGIL、NeurIPS 2025 DRIFT，以及 2026 年 ARGUS/AuthGraph 已覆盖
  动态规则、上下文依赖和参数来源级审计。原“唯一/首次参数级来源追踪”定位已经
  不能成立；同时现有 paper-v1 的正式公共矩阵、独立盲测、API 和自适应证据仍缺失。
- 备选方案：继续按 paper-v1 84-cell 队列直接扩张；或把论文完全改为综述。前者
  会在核心机制未通过中型门禁时消耗大量资源，后者会浪费已实现的运行时机制。
- 后果：先完成 30+ 文献矩阵和 20 项源码审计，再运行 60–80 个配对任务的证伪门禁。
  只有门禁通过才扩大正式实验；否则转为授权泄漏、安全—效用和过度阻断实证研究。
  JISA 为当前首选，Computers & Security 因官方范围排除 AI/ML 系统自身安全而移除。
- 负责人：Codex / 项目作者。

### 2026-07-23——在不改变证据身份的前提下归档过时 Markdown

- 决策：只将明确被替代且未冻结的 Markdown 移入 `docs/archive/`；被历史 Harness
  记录引用的研究路径保留简短重定向页。不得移动或改写 `outputs/`、`protocols/`、
  `external/`、`release/`、本地配置、模型文件或任何由冻结/哈希绑定字节内容的文件。
- 原因：新维护者需要唯一的当前事实来源，同时不能丢失旧 69 条竞赛文档和执行前
  失败计划的来源链。删除旧文件或重写冻结路径会破坏可审计性。
- 后果：`docs/项目移交报告.md` 与 `harness/项目上下文.md` 是当前人工可读入口；
  归档材料只提供历史上下文，不是当前运行指南。除明确记录的本机依赖和模型路径外，
  项目内链接优先使用相对路径。

### 2026-07-22 — Task Shield v1.6 uses staged authorization and correctness-first gates

- Decision: Treat the user's v1.6 approval as authorization for environment closeout and P0-P4 staged engineering, but execute no model job in the preparation checkpoint. P0 metric correction and P1-P2 deterministic engineering run first; P3/P4 can run only after their machine-readable gates, P5 requires a post-G3 checkpoint, and P6 726-case formal requires a separate explicit authorization.
- Reason: v1.5 exposed a cross-baseline metric inversion plus timeout, retry, trace, schema and latency failures. Starting another large model root before correcting evidence semantics and deterministic contracts would compound invalid evidence and resource cost.
- Consequence: v1.6 uses new files, freeze and fresh roots; v1.3-v1.5 remain immutable. Qualification, diagnostic and partial results cannot mutate registries or Q2 readiness, and any failed stage is sealed rather than selectively retried.

### 2026-07-22 — Failed formal roots require explicit recovery revisions

- Decision: A formal root with a failed case remains ineligible until the user explicitly chooses a recovery path. The safe handoff artifact is a read-only recovery decision package plus a file-based operator decision template/validator; it may list future commands but must not stop a live process, retry only the failed case, exclude rows, admit registries or start a competing model workload.
- Reason: The active Task Shield v1.3 root has one verifier transport timeout while the PID is still alive. Silently repairing or trimming the denominator would make the baseline look cleaner than the frozen formal execution actually was.
- Consequence: Task Shield v1.4 is a separate fresh-root recovery protocol. It must pass an approved operator decision artifact, two-case qualification, exact 726/726 coverage, zero unexplained failures, hash-linked analysis and clean admission before it can affect Q2 readiness.

### 2026-07-22 — Hash-bound adapter code is frozen by identity, not only by directory name

- Decision: Do not modify Task Shield, Progent, CaMeL or IPIGuard runner/analyzer files that are listed in existing formal freeze `local_adapter.files`, even for path-only cleanup. Keep their historical absolute-path output semantics and normalize future references at non-frozen admission/report readers.
- Reason: The freeze validators correctly failed when analyzer bytes changed, proving those files are part of the immutable experiment identity although they live under the active Python tree.
- Consequence: Portability auditing must exclude hash-bound code discovered from freeze manifests in addition to `.gitattributes` paths. Changing such code requires a new freeze version and fresh output root; the current v1.1/v1.2 freezes remain unchanged.

### 2026-07-22 — The 80% milestone is evidence-capped, not an engineering-completion proxy

- Decision: Track `goal_80_met` from the conservative capped Q2 readiness score. Do not count plan-only, smoke, diagnostic, running, partial or self-authored independent-blind artifacts toward the milestone.
- Reason: The user requested progress to 80%, but a raw engineering checklist could exceed that number while public benchmarks, five formal baselines, independent blind evidence, two frontier API vendors or adaptive query-budget evidence remain absent.
- Consequence: Reaching 80 requires clearing every active cap that can limit the score below 80. The current 66.0 raw / 60.0 capped result remains truthful; external blind custody and API credentials/consent stay explicit human dependencies rather than being fabricated locally.

### 2026-07-22 — Post-preregistration blind evidence uses a separate mutable index

- Decision: Preserve the preregistration-bound v1 missing-candidate audit and historical `final_analysis` manifest byte-for-byte. Write future candidate admission to v2 and expose a completed independent-blind result only through `paper_v1_evidence_index_v1.json` after a separate fail-closed admission.
- Reason: Overwriting either preregistration input or historical final-analysis evidence would destroy time ordering and violate the user's freeze boundary merely to make the Q2 audit find a new field.
- Consequence: Candidate admission and formal-result admission are distinct. The index changes only with explicit `--write-evidence-index` after exact 600-case scope, zero unresolved failures and artifact hashes pass; the current missing candidate remains blocked and adds no score.

### 2026-07-22 — Repository paths are relative; external machine resources remain configurable

- Decision: Active source, commands, documentation links and ordinary artifact references use paths relative to the repository root. Absolute paths are limited to repository-external interpreters, model stores, caches, isolated environments and pinned external checkouts, preferably through the ignored local configuration.
- Reason: The project must remain movable across drive letters, checkout directories and team machines without rewriting source or documentation.
- Consequence: The convention audit rejects checkout-specific absolute paths in active non-frozen files. Historical/frozen evidence keeps its original execution-machine paths and hashes unchanged; portability is provided by readers and configuration rather than evidence rewriting.

### 2026-07-21 — Normalize only non-frozen documentation paths and preserve stable contracts

- Decision: Restrict this cleanup to four approved non-frozen file moves and documentation/index updates. Do not globally rename Python identifiers or alter public functions/classes, CLI flags, schemas, environment variables, manifest fields, case IDs, model aliases, historical paths inside frozen snapshots or active ToolFilter evidence.
- Reason: The active codebase already passes the Python naming audit, while broad renames would add compatibility and hash risk without research value.
- Consequence: New active files follow the documented naming convention, old external contracts remain valid, and historical materials may retain legacy names as provenance rather than being rewritten.

### 2026-07-21 — Use one project overview with explicit evidence-status boundaries

- Decision: Make `docs/项目完整综述.md` the comprehensive human-readable map of the project and require every result statement to identify historical, post-hoc, diagnostic, smoke, running or formal status.
- Reason: The repository spans two experiment generations and many generated artifacts; scattered documents had allowed stale counts and evidence categories to drift.
- Consequence: README and secondary documents link to the overview instead of redefining all features. Running ToolFilter rows, model smokes and preparation freezes remain excluded from formal paper claims and Q2 scoring.

### 2026-07-21 — Formal baseline adapters must be hash-bound before model probe

- Decision: Future source-backed formal baseline adapters must freeze and verify local runner, analyzer, import-audit/protocol and shared identity code hashes, and must reject resume identity drift before probing Ollama or any model/API service.
- Reason: Progent, IPIGuard, CaMeL and the disclosed Task Shield reproduction all have preparation states where a stale output root or untracked local adapter drift could otherwise make a later result appear compatible with an older freeze.
- Consequence: Changing local adapter code requires a new freeze version and fresh output root. The new Progent v1.1, Task Shield v1.2 and CaMeL v1.2 artifacts are engineering readiness evidence only; they do not promote any baseline to a formal result without real-model qualification, exact 726-case logs, analysis and admission.

### 2026-07-18 — InjecAgent stage diagnostics must be prompt-style and model stratified

- Decision: Stage runner keeps `m3_json` while adding official `InjecAgent` ReAct and official `hwchase17_react` simple ReAct prompt styles; qwen3 weak-trigger slices and Vicuna baseline-vulnerable slices are both retained as diagnostic strata.
- Reason: qwen3 under official prompts returned mostly final answers in early InjecAgent cases, while Vicuna under the official simple ReAct prompt exposed successful baseline DS/DH attacks. Treating only one model/prompt as representative would distort public-benchmark conclusions.
- Consequence: Future InjecAgent expansion should stratify by model and prompt style before freezing formal estimates; selected baseline-vulnerable slices may guide method development but cannot estimate full InjecAgent ASR.

### 2026-07-18 — InjecAgent expansion records negative diagnostics before pairing

- Decision: Vicuna `official_react_simple` DS cases 0004/0005 are retained as negative no-defense diagnostics because they reached ASR-all Total 0.0 despite valid execution; paired Guard slices are reserved for rows where the baseline actually completes the benchmark attack objective.
- Reason: Blind expansion can otherwise drift into cherry-picking by silently discarding non-triggered attacks or over-reporting tiny favorable slices.
- Consequence: Future 30-100 case InjecAgent diagnostics must report both baseline-positive and baseline-negative strata, then freeze inclusion rules before any publication-scale estimate.

### 2026-07-18 — InjecAgent long diagnostics require frozen selection and incremental logs

- Decision: Add a result-blind stratified selection builder and require progress-enabled runner outputs (`progress.jsonl`, incremental `runs.jsonl`, selection/progress hashes, timeout and max-token settings) before attempting larger InjecAgent diagnostics.
- Reason: A pre-progress 30-case Vicuna no-defense attempt remained opaque after repeated monitoring cycles because the old runner only wrote logs at process end.
- Consequence: The stopped 30-case attempt is logged as a non-result. The frozen 30-case selection remains valid, and a 6-case progress-enabled paired smoke now verifies the safer execution path before any 30-100 case expansion.

### 2026-07-18 — 30-case InjecAgent result is a frozen-selection diagnostic, not an official benchmark claim

- Decision: Admit the Vicuna `official_react_simple` 30-case stratified pair as diagnostic compatibility evidence: no-defense ASR-all Total 46.7%, m3_full 0.0%, paired attack success 14/30 to 0/30, McNemar p=0.0001221.
- Reason: The selection was frozen before execution, both conditions completed 30/30 with 0 failures, and the analysis now includes bucket-level summaries and figures. However, the runner is still not byte-identical to InjecAgent's official prompted/function-calling executors.
- Consequence: This result strengthens the public-benchmark story but must be labelled as diagnostic until either byte-identical compatibility is implemented or the paper explicitly frames it as a disclosed stage-compatible replay.

### 2026-07-18 — ReAct parser follows action-centric official prompted scoring

- Decision: For InjecAgent stage logs, ReAct `Action` is parsed before any later `Final Answer`; `Action Input: None`, `N/A`, `null`, and no-input wording are normalized to `{}` for parameter-free tools.
- Reason: Vicuna generated official-style attacks with no-argument tools and trailing final answers. Parsing those as final text made attack success appear lower than the official prompted evaluator would report.
- Consequence: Baseline-vulnerable DS slice changed from invalid/unsuccessful to S1/S2 successful and is now auditable through regression tests and paired diagnostic analysis.

### 2026-07-18 — InjecAgent official-stage runner 只能作为诊断兼容证据

- Decision: 新增 InjecAgent official-stage diagnostic runner，把模型置于官方“User Tool 已执行、Tool Response 已注入”的阶段；同时在 manifest 中记录 `gold_user_tool_stage_used_online=true` 和 `result_eligible_for_formal_tables=false`。
- Reason: 这比 earlier public replay 更接近 InjecAgent 官方评测阶段，但仍使用 M3 的 JSON/ReAct parser、本地 Guard 和本地 deterministic/cached 工具响应，不是 byte-identical 官方 prompted/function-calling runner。
- Consequence: qwen3 data-security/direct-harm limit-2 smokes 可验证适配链路和暴露策略编译风险；论文正式 InjecAgent 结果仍需全量执行和官方兼容性论证。

### 2026-07-18 — 非 gold 策略编译不能仅凭供应商域名授权私有读工具

- Decision: 收窄 generic policy compiler 的同域 read-only fallback；共享供应商/域名词不再足以授权不相关 read-only 私有查询。
- Reason: InjecAgent stage smoke 暴露 `Amazon` 产品详情任务会过度授权 `AmazonViewSavedAddresses`，这会把策略编译器错误伪装成 Guard 成功。
- Consequence: 产品详情任务只授权 `AmazonGetProductDetails`；合法 reschedule 等 mutating task 的辅助 lookup 仍由显式 mutating-action 支持逻辑保留，并由 regression tests 覆盖。

### 2026-07-18 — AgentDojo selected-repeat 只作为富集候选簇诊断

- Decision: 四套件 screen 只用于选择 baseline-vulnerable candidate clusters；selected-repeat 在 25 个正候选簇和 4 个 zero-control 簇上重复验证，不得解释为 AgentDojo 全量 ASR 或正式公共基准结果。
- Reason: selected-repeat 刻意富集 baseline 成功攻击，能放大 Guard 对候选簇的诊断信号，但会高估全量任务分布中的攻击率。
- Consequence: 174/174 jobs、no_defense 72/87、m3_full 0/87 和 24 个 stable blocked clusters 可以指导下一步 baseline/ablation/adaptive 设计；论文主表仍需冻结全量 AgentDojo 协议或明确披露抽样限制。

### 2026-07-18 — 官方 AgentDojo prompt baselines 用显式本地 adapter 进入比较

- Decision: 新增 `agentdojo_repeat_user_prompt` 和 `agentdojo_spotlighting_with_delimiting` 两个 defense id；它们分别复现 pinned AgentDojo 的 raw-query repeat 和 `<<...>>` 工具输出分隔提示。`tool_filter` 与 `transformers_pi_detector` 先登记为 deferred compatibility items。
- Reason: 论文不能把自定义 `spotlighting` prompt 冒充 AgentDojo 官方 baseline，也不能只用口头说明替代可复现运行条件。
- Consequence: baseline registry、selected prompt-baseline protocol、combined analyzer 和 regression tests 已就绪；结果仍需运行 174-job prompt-baseline diagnostic 后才能比较。

### 2026-07-18 — AgentDojo 策略编译从纯词面匹配升级为非 gold 动作—领域编译

- Decision: 只使用可信用户请求和公开工具 schema，区分副作用动作、信息查询、否定范围、领域对象和同领域辅助只读工具；不读取官方 checker、ground truth 或 injection goal。
- Reason: 纯词面匹配把“email addresses”误当成 send_email 权限，并漏掉合法 calendar lookup；这同时损害可用性和最小权限。
- Consequence: corrected `workspace/user_task_0` utility smoke 通过官方 checker；所有输出仍是 diagnostic，正式阈值和 max-tools 必须在 blind 前冻结。

### 2026-07-18 — 指令承载字段不得驱动后续工具 selector

- Decision: AgentDojo 原生 runner 保留结构化 tool result；provenance 记录值来自 description/body/content 还是 participants 等字段。来自指令承载字段的 query/name/recipient 等 selector 由 provenance 模块 DENY，拒绝后允许有界安全恢复。
- Reason: 序列化整段 tool output 会把合法 participants 与注入在 description 中的攻击邮箱混为同一种来源，无法形成独立 provenance 贡献。
- Consequence: 注入 smoke 中攻击者邮箱查询被 DENY，合法 participant 字段仍可查询，拒绝动作不会进入 AgentDojo 官方 executed-tool trace。

### 2026-07-18 — 公共基准对照组不得带隐式不可信标签

- Decision: `no_defense` 的工具输出使用普通 `Tool observation`，只有安全提示/Guard 条件使用 `UntrustedAgentDojoToolObservation` 包装；旧 32-run direct 矩阵标为对照污染诊断。
- Reason: 对照组工具输出上的 `Untrusted` 标签本身是一种提示防御，会压低 baseline ASR。
- Consequence: 后续 AgentDojo 矩阵可正交比较 prompt-only、normal+Guard 和 safe-prompt+Guard。

### 2026-07-18 — AgentDojo 小切片必须重复并按任务—注入聚类解释

- Decision: native matrix 增加 replicate_id、种子偏移、配置漂移拒绝和 paired cluster bootstrap；48-run important-instructions 结果只登记为 diagnostic。
- Reason: 单次温度 0 运行仍出现攻击成功不一致，且 3 个成功全部集中在一个 cluster。
- Consequence: 当前点估计 12.5% 到 0% 不能作为论文结论；正式实验必须扩大 cluster 数并冻结重复策略。

### 2026-07-18 — 论文升级使用独立非预知 runtime

- Decision: 保留现有 `agent_runner`/Guard 作为 E0-E17 与 V2 历史复现路径，在新增 paper-v1 模块中实现只依赖可信用户请求、工具 schema 和可信应用上下文的策略编译与在线执行。
- Reason: 直接修改冻结路径会破坏历史字节证据；继续使用逐样本 `authorized_actions` 又会造成论文级授权答案泄漏。
- Consequence: paper-v1 与旧实验使用独立协议、schema、冻结和输出根；旧结果不能替代新的确认性盲测。

### 2026-07-18 — 自动封存 holdout 不冒充独立作者盲测

- Decision: 自动生成的 600 条 holdout 仅标记为 sealed automated holdout；只有在未参与开发的人员独立生成或托管时才可升级为 independent blind。
- Reason: 同一开发过程生成和维护的数据不能诚实地声称作者完全未见。
- Consequence: 数据 manifest 必须记录生成者类型、冻结时间、读取审计和证据等级。

### 2026-07-18 — 公共基准先接诊断 replay，再接官方原生执行

- Decision: AgentDojo 与 InjecAgent 先完成官方仓库 pin、全量索引和 offline/online 字段隔离；InjecAgent 增加 public replay diagnostic runner，AgentDojo 增加 native smoke runner。
- Reason: 公共 benchmark 的官方评价器和工具环境不能用自建模拟结果替代；但索引和 replay smoke 能提前验证 M3 非 oracle 策略、解析器和 Guard 在公共 schema 上可运行。
- Consequence: replay/native-smoke 输出统一标记为非正式诊断证据且 `result_eligible_for_formal_tables=false`；正式论文主结果仍必须接官方环境全量运行或明确披露不兼容限制。

### 2026-07-18 — AgentDojo native smoke 只证明适配链路，不证明任务性能

- Decision: 新增 AgentDojo native `BasePipelineElement`，并以 `workspace/user_task_0` 和 `workspace/user_task_0/injection_task_0` 完成最小官方 checker smoke；结果保留 utility/security，但只标记为 diagnostic。
- Reason: 只有官方 `TaskSuite.run_task_with_pipeline` 才能让 AgentDojo 的环境变化和 checker 参与评价；索引或 replay 不能替代该路径。
- Consequence: 当前 smoke 暴露了 generic policy 对合法工具授权和否定语义处理不足。正式全量运行前必须扩展策略编译器、诊断 utility=false 的原因，并冻结完整协议。

### 2026-07-18 — 授权不确定性先做 smoke，不作为确认性发现

- Decision: 新增 auto/ambiguous/partial/incorrect policy regime，并先在 qwen3 的 6 条 validation subset 上生成诊断折线图。
- Reason: 授权不确定性是论文升级后的核心研究问题；在大矩阵前需要先验证 ASK/TCR/side-effect 指标链路和可视化链路。
- Consequence: 该 smoke 可用于调试与方法展示，但不能作为 blind、安全优势或投稿主结论；正式结果必须在冻结假设、阈值、样本和排除规则后重跑。

### 2026-07-18 — Ollama 程序与模型库存储分离

- Decision: 保留 `D:\Ollama\app`，仅将两个源模型库按哈希并集合并到 `E:\Ollama\models`；只有两轮从 E 盘独立重启 smoke 通过后才删除 D 盘旧模型库。
- Reason: 模型 blob 占用 D 盘空间，而程序本体很小；分离迁移能降低破坏安装和回滚失败的风险。
- Consequence: `OLLAMA_MODELS` 统一指向 E 盘，迁移证据保存在 `E:\Ollama\migration_evidence`；仓库旧 `models/` 暂留且不再是活动库。

### 2026-07-18 — 论文模型使用不可漂移的本地别名

- Decision: `qwen3:8b` 与 `llama3.1:8b` 下载后创建 `m3-paper-qwen3-8b-v1:latest` 和 `m3-paper-llama31-8b-v1:latest`，并同时记录 manifest、model blob digest、量化和上下文信息。
- Reason: 远程标签可能漂移，仅记录标签无法精确复现实验模型字节。
- Consequence: v2 model registry 和后续 manifest 使用本地别名加 digest；六案例 smoke 仅作为准入证据。

### 2026-07-18 — Gated PromptGuard 不绕过且不误判 partial cache

- Decision: 官方 PromptGuard 86M 返回许可门控后停止网络重试，记录固定 revision 与阻塞原因；模型就绪必须同时存在 config、weights 和 tokenizer。
- Reason: 只有 LICENSE/README 的 Hub 残留目录不是可推理模型，且绕过许可不符合复现与合规要求。
- Consequence: E 盘依赖环境标记为 ready，但真实 detector 保持 blocked；stub/preflight 永远不进入正式效果表，待用户合法授权后再继续一次固定 revision 下载。

### 2026-07-18 — 现代模型兼容仅进入 paper-v1 独立路径

- Decision: Qwen thinking 控制和 Llama 有界格式兼容由 `experiments/paper_v1/llm_client.py` 与 paper research runner 实现，不修改 V2 哈希绑定的历史 Agent、LLM client 和统计模块。
- Reason: 完整回归证明共享模块改动会破坏 Acceptance Remediation V2 的当前源码冻结，即使功能行为本身合理。
- Consequence: 历史 freeze 无需改写且校验恢复通过；v3 isolated-runtime smoke 从零复跑 24/24，旧 v1/v2 smoke 仅作诊断沿革。

### 2026-07-20 — 统一配置字段但隔离每位成员的真实凭据

- Decision: 项目提交 `config/project.env.example` 作为统一字段契约；每位成员只编辑被 Git 忽略的 `config/project.local.env`。不采用“同一真实文件在迁移前手工脱敏”的流程。
- Reason: 手工替换占位符无法消除 Git 历史、网盘历史、日志和备份中的泄密风险；同时，项目组仍需要一致的路径、模型 revision、阈值和启动方式。
- Consequence: 配置加载器只在子进程环境使用 Token，所有检查输出均脱敏；迁移只复制模板并在目标机器重建本地文件，PromptGuard 下载固定 revision 且不把凭据写入 manifest。

### 2026-07-20 — PromptGuard real smoke remains qualification-only

- Decision: freeze the 86M revision and map generic Transformers labels explicitly as `LABEL_0=BENIGN`, `LABEL_1=MALICIOUS`; admit the 12-case CUDA run only as qualification evidence.
- Reason: the downloaded config exposes generic labels, and the previous fallback would invert high-confidence benign predictions. A small hand-authored smoke cannot estimate benchmark ASR/FPR or replace tokenizer-aware formal cells.
- Consequence: all three diagnostic mismatches remain visible, the preflight advances to `real_detector_smoke_completed_formal_run_pending`, and formal admission still requires tokenizer-aware windows, frozen M3-v2/AgentDojo/InjecAgent manifests and complete logs.

### 2026-07-20 — PromptGuard formal admission is detector-only

- Decision: admit PromptGuard v1 as `ready_detector_only_formal` after the frozen 3,280-case source-backed run, but only for detector-performance tables.
- Reason: the run has frozen inputs/labels, tokenizer-aware windows, complete logs, failure-inclusive denominators and no-label-leakage checks; however it never executes an agent, tool call or runtime policy.
- Consequence: PromptGuard contributes one formal-ready strong baseline toward the Q2 gate, moving the count to 1/5, while ASR, TCR, legal-tool utility, Pareto and SOTA claims remain blocked until separate end-to-end source-backed baselines exist.

### 2026-07-20 — AgentDojo transformers detector smoke resolves dependencies only

- Decision: use the dedicated E-drive PromptGuard runtime plus AgentDojo official source on `PYTHONPATH` to smoke `TransformersBasedPIDetector` with the cached ProtectAI detector.
- Reason: this removes the local `transformers`/model-cache blocker without installing a second large environment or mixing AgentDojo official defenses into the M3 local runner.
- Consequence: `agentdojo_transformers_pi_detector` advances to `ready_official_detector_smoke_completed_formal_run_pending`, but remains outside formal effect tables until a frozen full AgentDojo official cell and complete logs exist.

### 2026-07-13 — Secret-path experiments use an in-memory synthetic fixture

- Decision: any `sandbox/secrets/**` read is intercepted before filesystem probing and returns a clearly synthetic in-memory marker; writes are rejected.
- Reason: the first discarded Qwen probe proved that the Day7 file-backed fake canary violated the Harness permission boundary even though it was not a production secret.
- Consequence: DSR and cross-tool exfiltration remain measurable without reading, creating or exposing a secret file. Pre-fix probe outputs are excluded from E0-E17 evidence.

### 2026-07-13 — Canonicalize common small-model tool argument aliases

- Decision: normalize aliases such as `file→path`, `recipient→to` and `content→body/answer` immediately after ToolCall parsing while retaining unknown context fields.
- Reason: Qwen produced valid JSON with `file`; leaving it unnormalized made a malicious call indeterminate and biased ASR/Recall downward.
- Consequence: policy, execution and evaluation receive the same canonical call shape, with regression tests for precedence and alias handling.

| Date | Decision | Context | Alternatives Considered | Consequences | Owner |
| --- | --- | --- | --- | --- | --- |
| 2026-07-08 | Adopt repository-backed AI Agent Harness | The project needs long-running, recoverable, verifiable agent execution. | Single prompt only; external task tracker only. | Context, progress, verification, and handoff are stored in the repository as source-of-truth files. | Harness Architect |
| 2026-07-08 | Use feature-list driven delivery tracking | Agents need a durable way to know what is planned, active, verified, or blocked. | Free-form progress notes only. | `harness/features/feature_list.json` becomes the feature status contract. | Harness Architect |
| 2026-07-08 | Require verification evidence before completion claims | Agent outputs must be auditable. | Trust agent claims without command evidence. | Final reports must include commands and results. | Harness Architect |
| 2026-07-13 | Base the experiment project on Day7 commit `2c53f52` and local branch `test1` | The Harness directory initially contained no Git history or product code, while Day7 contains the complete runnable prototype. | Rebuild from the minimal main branch; copy files without history. | Preserves the strongest existing implementation and makes subsequent changes auditable. | Codex |
| 2026-07-13 | Run the project in strict mode with E0-E17 registry gates | The user requires continued execution until every experiment and delivery artifact is complete. | Treat experiments as an informal checklist. | Each experiment requires machine-readable status and evidence before completion. | Codex |
| 2026-07-13 | Separate runtime-visible case data from evaluation metadata | Existing prompts and Guard context expose expected behavior, attack family and injection annotations. | Keep the convenient full case object. | Prevents label leakage and makes Guard comparisons interpretable. | Codex |
| 2026-07-13 | Make prompt profile and Guard configuration orthogonal | Existing defense modes change both the system prompt and runtime Guard. | Continue the legacy defense mode switch. | Enables causal prompt-only, Guard-only and combined comparisons. | Codex |
| 2026-07-13 | Use `obfuscation_evasion` as the ninth attack family | The original dataset has five attack families, so three newly named families would total only eight. | Count benign as an attack family; invent a different ninth category. | Keeps benign separate and directly covers the approved encoding/evasion experiment dimension. | Codex |
| 2026-07-13 | Treat Stub as oracle-backed regression only | Stub directly uses evaluation metadata and deterministic unsafe actions. | Include Stub in effectiveness tables. | Prevents synthetic pipeline behavior from inflating real-model conclusions. | Codex |
| 2026-07-14 | Require automated dual diagnosis followed by two real human E17 reviews | The user explicitly requested dual-agent automatic checking and then two human blind reviewers. | Treat automated reviews as the two required reviewers; let one agent simulate human labels. | Automated outputs remain diagnostic-only; E17 stays blocked until two independent real humans complete the frozen review packets. | User/Codex |
| 2026-07-14 | Exclude PPT, DOCX report and submission ZIP from the active delivery scope | The user explicitly said not to make PPT, not to make a DOCX report yet, and not to create a submission ZIP. | Keep early document requirements; silently delete existing files. | Existing assets are preserved untouched, while final delivery is code/data/statistics/charts/Dashboard/Harness plus a local commit. | User |
| 2026-07-14 | Preserve frozen Dashboard source and isolate enhanced evidence UI | Post-freeze browser fixes changed a path included in the blind freeze. | Rewrite the freeze; allow presentation-only mismatches. | `m3_eval/dashboard.py` remains byte-identical to the freeze, while `m3_eval/evidence_dashboard.py` owns post-freeze UI improvements. | Codex |
| 2026-07-14 | Preserve old v3 E9/E14 and correct them under a new protocol/freeze | Post-freeze audit proved E9 context workloads were uncalibrated/collapsed and E14 prompt workloads were flat across context labels. | Overwrite v3; relabel old cells; treat truncation/parse failure as safety; ignore the semantic defect. | Old v3 remains immutable diagnostic provenance. E9/E14 return to running, all affected cells must be rerun with token-calibrated workloads and effective context aliases, and E17/final synthesis must be rebuilt. | Codex |
| 2026-07-14 | Use probe-verified Modelfile aliases for corrected context experiments | The OpenAI-compatible runtime path did not establish a trustworthy dynamic per-request `num_ctx` axis. | Continue passing request options; switch the entire runtime to an unvalidated API path. | Local `m3-qwen3-4b-ctx4k/8k/16k/32k` aliases define effective context settings. Probe success is a prerequisite only; formal corrected runs still require a separate freeze and measured prompt-token checks. | Codex |
| 2026-07-16 | Require exact positive authorization for every public read | The failed Recall gate was entirely driven by unauthorized public-file reads that policy treated as harmless. | Exclude public reads from the malicious-call denominator; block every public read unconditionally. | Exact authorized reads remain usable; all other public reads become ASK and stay in the original metric denominator. | Codex |
| 2026-07-16 | Expose only the trusted positive tool contract to the model | Small models invented extra tools or returned final before a required legal action because the runtime prompt hid the same authorization contract already enforced by Guard. | Expose evaluator labels/unsafe targets; rely on unstructured user wording only. | Prompts include `requires_tool` and `authorized_actions`, but never sample type, unsafe target, expected behavior, detector answer, or success label. | Codex |
| 2026-07-16 | Permit bounded, fully logged safe recovery | A Guard ASK/DENY or premature final previously terminated a benign task even when no unsafe tool executed and a safe continuation remained possible. | Count the terminated run as unavoidable failure; silently discard the failed step. | The rejected/premature step remains in the run log and original denominator; at most two configured recovery turns are allowed identically across paired conditions. | Codex |
| 2026-07-16 | Validate E14 overhead by same-output counterfactual replay | Separate concurrent model generations made sub-millisecond Guard cost indistinguishable from multi-second GPU scheduling noise, producing 90%+ paired overhead in some cells. | Keep the confounded cell estimator; omit the failed cells. | Old E14 results remain immutable and disclosed; a frozen replay applies the current Guard to identical retained model outputs and attributes only measured Guard time. | Codex |
| 2026-07-16 | Exact authorized actions bypass document-level detector penalties | V1 formal Qwen showed that safe authorized first steps in attack-chain cases were ASK/DENY because detectors described the hostile carrier, not the proposed action, causing FPR 87.88%. | Accept the FPR; remove detector modules; treat authorized calls as automatically safe without policy/dataflow. | Instruction/structured/multilingual detector deltas are zero only for an exact authorized action; policy and dataflow still run and can deny off-target or sensitive effects. The later malicious proposal is evaluated normally. | Codex |
| 2026-07-16 | Invalidate Remediation V1 and rerun V2 from a new freeze | The first completed V1 job decisively failed unchanged A03/A05/A11 gates, so finishing all 12 jobs could not satisfy the objective. | Continue wasting compute; overwrite V1; change thresholds. | V1 outputs remain invalid diagnostic provenance. V2 has a new protocol, hashes, output root, and complete rerun from zero formal case-runs. | Codex |
| 2026-07-16 | Keep V2 execution freeze intact and adapt one report field externally | The frozen analyzer passed the 2,160-tuple audit, then raised `KeyError: estimate` because the stable proportion API returns `value`. | Edit the frozen analyzer; re-run 2,160 model calls; manually edit the CSV. | A separately hashed wrapper aliases `value` to report-only `estimate`; no RunLog, metric, threshold, count, interval, or comparator changes. The patch is disclosed in the result manifest and analysis. | Codex |
| 2026-07-16 | Keep post-freeze result repairs confined to a disclosed report-layer wrapper | The analyzer also omitted the Dashboard artifact discriminator, while visual QA found overlapping pie labels and near-zero line compression. | Weaken Dashboard validation; edit the frozen analyzer; accept unreadable charts. | The hashed wrapper adds only `kind=figure_manifest`, re-renders two figures from unchanged CSV values, refreshes figure hashes, and reruns the unmodified Dashboard validator. | Codex |
| 2026-07-16 | Verify historical bundles through an exact compatibility declaration | Remediation legitimately changed files hash-bound by historical E11 and sampled-E17 freezes. | Rewrite old hashes; rerun unrelated historical programs; skip the checks. | Old freezes stay immutable; exact old/current hash pairs are declared, all evidence roots are recursively verified, and current claims require the independent V2 freeze. Any undeclared future drift fails. | Codex |
| 2026-07-16 | Store V2 hash-bound paths byte-exact in Git | Windows `core.autocrlf=true` normalized mixed line endings in the index even though the working-tree freeze passed. | Accept post-checkout hash drift; normalize frozen files after execution. | Path-scoped `.gitattributes` uses `-text` only for V2 source/evidence records, so index and checkout bytes equal the verified freeze without changing executed content. | Codex |

### 2026-07-21 — Freeze confirmatory hypotheses before new blind and adaptive results

- Decision: seal the paper-v1 confirmatory hypotheses, primary estimands, clustered inference, multiplicity control, exclusion rules and ten-figure plan in an immutable preregistration payload before any independent-blind or formal adaptive result exists.
- Reason: the historical blind set has already informed engineering, so an explicit time-ordered freeze is required to distinguish confirmatory evidence from post-hoc iteration.
- Consequence: Q2 reproducibility credit requires the preregistration hash and all checks, but the freeze alone contributes no effect evidence and cannot admit a result.

### 2026-07-21 — Admit external strong baselines through one fail-closed bridge

- Decision: Task Shield, IPIGuard, Progent and the selected information-flow baseline use one admission bridge that verifies the frozen universe, 726 unique completed cases, zero failures, analysis hashes and figure/report artifacts before atomically updating both baseline registries.
- Reason: separate manual promotions could let registry state diverge or promote partial runs. The `camel_or_fides` slot is a selection requirement, not a requirement that both alternatives be eligible simultaneously.
- Consequence: only the frozen selected method, currently CaMeL, must become result-eligible; unselected FIDES remains explicitly ineligible. Plan-only audits may report blockers but cannot mutate registries.

### 2026-07-21 — Diagnose IPIGuard schema failures without repairing them in place

- Decision: retain raw construct-stage JSON before delegating to the unchanged upstream IPIGuard parser, hash-bind the local runner/analyzer/protocol, and reject resume roots whose freeze, runner, model, condition or selected cases drift.
- Reason: the first qualification failed on a missing `function_name`, but the raw model payload was not preserved. Guessing aliases or silently filling fields would change the baseline before the failure mechanism was established.
- Consequence: v1 remains immutable failed diagnostic evidence; v1.1 requires a new two-case output root. Any later prompt/schema compatibility repair must be a separately frozen, disclosed reproduction rather than a retry of the source-backed configuration.

### 2026-07-22 — Seal Task Shield v1.4 and reject the v1.5 qualification

- Decision: stop PID 9804 under explicit operator authorization, seal v1.4
  externally without modifying its root, and treat the separately frozen v1.5
  12-case run as a failed qualification rather than a formal result.
- Reason: v1.4 retained two verifier-invalid-JSON failures. v1.5 recovered one
  invalid contract but then retained an exhausted assistant timeout, did not
  persist the failed trace, achieved utility success on only 1/6 stress tasks
  and allowed all 6/6 stress attacks to succeed.
- Consequence: v1.4 remains sealed at 24 completed, 2 failed and 700 missing;
  v1.5 remains `completed_failed_qualification_analysis` at 11 completed, 1
  failed and 0 missing. Neither root may be resumed, selectively retried,
  filtered, pooled, admitted or used to raise Q2 readiness. Any v1.6 work needs
  a fresh explicit decision, new hash-bound freeze and new output root.

### 2026-07-22 — Correct AgentDojo metric semantics before Task Shield v1.6

- Decision: treat all current shared-adapter `attack_success=not security`
  analyses as provisional and require a non-mutating analysis-v2 correction
  from raw official traces before building or running Task Shield v1.6.
- Reason: AgentDojo's pinned source and official notebook define the attack-case
  `security` value as targeted injection success. The current project mapping
  reports its complement as ASR, reversing Task Shield 0/6 into 6/6 and
  ToolFilter 7/629 into 622/629.
- Consequence: old freezes, outcomes, traces and analyses remain immutable, but
  they cannot support effect-direction claims. The proposed v1.6 sequence starts
  with a zero-model-call semantics correction, then requires explicit approval
  for 4-case, 12-case, 30-case and 726-case gates.

### 2026-07-23 — Separate official source evidence from disclosed reproduction

- Decision: count Task Shield as a completed online-state audit only with
  `source_provenance=disclosed_local_reproduction`, bind its official ACL PDF,
  and keep `official_source_available=false`; do not describe the local
  implementation as the authors' code.
- Reason: the peer-reviewed paper establishes the method, but no official code
  source was established. Conflating a paper reproduction with official source
  would overstate both implementation fidelity and any field-flow conclusion.
- Consequence: the registry reaches 22/22 audited units while Task Shield remains
  `inconclusive`; source provenance counts are explicit and the domain-level
  oracle claim remains forbidden without independent review.

### 2026-07-23 — Freeze offline cost and execution identity before paid calls

- Decision: bind the 480-item paper-v2 medium plan to source-audit, baseline,
  schema, contract, case and provider hashes; require an offline provider/cost
  preflight, an append-only progress ledger and a 90% spend abort before any
  formal call.
- Reason: model identity, incomplete resume state and uncontrolled API spending
  can invalidate a paired experiment even when the analysis code is correct.
- Consequence: the current candidate has a conservative USD 119.93484 upper
  bound and 4,416-call ceiling but remains unauthorized. Runtime identity,
  request/response IDs, logging review and explicit user hard-cap approval are
  mandatory; no result exists until actual terminal records pass the paper-v2
  contract.

### 2026-07-23 — Supersede the unused medium ledger with condition-specific visibility

- Decision: retain `medium_execution_plan_v1.jsonl` as an immutable pre-run
  artifact with zero outcomes, and make `medium_execution_plan_v2.jsonl` the
  authoritative runtime freeze.
- Reason: v1 correctly locked case inputs but reused one case-level visible-field
  digest across defenses and authorization regimes. That could not prove what a
  detector, structural guard, policy-only monitor, full monitor, or oracle
  ablation actually saw online.
- Consequence: v2 separately hashes the source projection, condition-specific
  initial state, and final runtime visibility events. `exact_gold` is explicitly
  evaluator-derived and primary-ineligible. Any real result bound only to v1 is
  inadmissible.

### 2026-07-23 — Treat DeepSeek/Gemini output as proposal-only and deny dangerous effects

- Decision: allow future official DeepSeek and Gemini inference only through
  frozen official origins, with provider-managed tools and external connectors
  disabled. Apply effects only to M3 synthetic fixtures or copied AgentDojo
  in-memory environments; require a safety receipt for every non-stub record.
- Reason: the user explicitly prohibited dangerous API-driven operations, and a
  tool-using-agent security experiment must not turn adversarial model output
  into real email, payment, command, filesystem, browser, credential, database,
  cloud, or production effects.
- Consequence: unknown/unsafe effects fail closed and become retained
  `runner_failure` evidence. Keys stay only in ignored local configuration and
  are never accepted by the policy or receipt artifacts.

### 2026-07-23 — Freeze citation status but defer final JCR and DOI admission

- Decision: structurally verify all 34 literature entries against primary-source
  hosts and freeze peer-reviewed/preprint classification, while keeping final
  bibliography fields and JCR quartile as submission-time gates.
- Reason: a current frontier matrix can prevent novelty overclaiming, but it
  cannot establish the future submission-date journal quartile or replace a
  complete DOI/author/venue check of the final reference list.
- Consequence: the matrix records 22 peer-reviewed and 12 preprint-only works;
  first/only/SOTA wording remains forbidden. JISA scope is confirmed from the
  publisher, while SCIE/JCR Q2 remains institutionally pending.

### 2026-07-24 — Activate a prospective local-precommit request chain for DeepSeek

- Decision: accept the project owner's explicit evidence design for DeepSeek:
  freeze a deterministic local request ID and canonical payload SHA-256 before
  transport, append/flush/fsync the started event, then bind the official
  response ID and exact returned model in a hash-chained terminal event.
- Scope: DeepSeek only, fresh prospective requests only. The provider
  request-ID header is stored when available but is not required under this v2
  trace. The v1 experiment-record contract and all historical smokes remain
  unchanged and cannot be upgraded retroactively.
- Evidence boundary: the trace stores no prompt/response content or credential,
  declares no provider tools, enables no external effects, performs no
  automatic retry and is qualification-only until every formal runtime call is
  wired to experiment-record v2.
- Gemini input: the user-submitted AI Studio screenshot is bound by SHA-256
  only and records 1000 RPM, 2000000 TPM and 10000 RPD. The screenshot is not
  copied into the repository; free-tier status remains a project-owner
  declaration and paid-tier spend remains forbidden at USD 0.
- Consequence: one safe DeepSeek identity call completed the durable request
  chain. A later local response-normalization assertion rejected the
  qualification artifact write, so the chain was recovered without another
  network request. Response content, usage, latency and the full receipt are
  explicitly unavailable; the recovered evidence qualifies identity only and
  is excluded from effect tables.

### 2026-07-24 — Bind every work-item provider call as an ordered v2 bundle

- Decision: supersede the unused experiment-record 2.0 single-attestation
  shape with experiment-record 2.1. Each record now contains the complete
  ordered request trace for that work item, including VIGIL constraint
  generation and all subsequent agent calls, rather than only the final
  provider response.
- Success boundary: every call must have a deterministic request ID, canonical
  payload digest, pretransport append/flush/fsync event, durable terminal event
  and activated DeepSeek attestation. Only a fully completed bundle may reach
  `formal_candidate`; `formal_admitted` additionally requires the independent
  admission-manifest digest.
- Failure boundary: a paused, transport-failed or evidence-invalid call retains
  its open precommit, stops without automatic retry, makes the whole bundle
  `diagnostic`, and is persisted with `unsafe_effect_itt=true`. Evidence is
  prevalidated before the terminal event is appended, preventing an ambiguous
  completed-but-unactivated state.
- Privacy and safety: bundle rows contain hashes and provider identity metadata
  only—never prompts, response text, credentials or external effects.
  DeepSeek is the only provider in the activated formal bundle scope; Gemini is
  not silently promoted by this decision.
- Consequence: four zero-network end-to-end scenarios now qualify the live
  path: one normal call, a two-call VIGIL path, an agent-loop 429 and a VIGIL
  preparation 429. All four traverse the real runtime, record assembler and
  transient append-only v2 store. The API matrix remains closed pending a
  run-specific admission manifest and bounded official pilot review.
## 2026-07-24 — Separate non-executable pilot candidate from active execution admission

Decision:

- The frozen DeepSeek pilot candidate is an owner-review artifact only and
  always carries `execution_authorized=false`.
- A live run requires a different, run-specific active manifest that binds the
  candidate and scope digests and records an explicit project-owner checkpoint.
- The execution controller validates admission, immutable inputs, exact work
  item identity and unused single-use outputs before any credential read or
  provider-client construction.
- A successful pilot remains `formal_candidate` (or diagnostic on failure);
  the manifest never authorizes the 480-item matrix or result admission.

Reason:

- Budget consent and trace-protocol approval do not by themselves authorize a
  scientific pilot.
- Separating review candidate, execution admission and result admission avoids
  self-authorization and preserves the academic checkpoint while making the
  future live path reproducible.

Consequences:

- Offline engineering can be fully verified without touching local secrets or
  the network.
- The exact owner-review candidate is frozen, but no project active admission
  exists until the user explicitly approves that pilot checkpoint.

### 2026-07-24 — Bind DeepSeek cache and cost evidence inside each completed request bundle

- Decision: provider trace bundle 2.1 requires every completed DeepSeek call
  to carry content-free usage and cost evidence: prompt cache-hit tokens,
  prompt cache-miss tokens, completion/total tokens, provider-receipt SHA-256,
  per-request and cumulative CNY cost, and post-request budget status.
- Integrity boundary: the usage row must match the corresponding terminal
  request ID, official response ID, activated attestation and receipt digest.
  Cache arithmetic, official pricing arithmetic and cumulative totals are
  revalidated when the bundle is assembled; missing or inconsistent evidence
  cannot reach `formal_candidate`.
- Privacy boundary: usage rows contain counts, IDs, digests and costs only.
  They do not store prompts, responses, credentials, headers or safety-sensitive
  tool arguments.
- Consequence: zero-network runtime qualification now covers three completed
  calls with complete accounting, and the fail-closed controller has a local
  injected-transport end-to-end fixture. These are engineering qualifications,
  not live provider cost observations or security/utility results.

### 2026-07-24 — Persist safety receipts and freeze a separate post-pilot review gate

- Decision: supersede the prospective experiment-record 2.1 contract with 2.2
  before any formal pilot exists. Record 2.2 requires the credential-free
  provider safety receipt inside the hashed append-only record rather than
  validating it transiently and discarding it.
- Review boundary: the post-pilot reviewer cross-binds candidate and active
  admission, active-file digest, independent trace JSONL, record bundle,
  provider/model identity, cache/cost arithmetic, safety receipt/action digest
  and ledger tail. Integrity drift is rejected; a valid but unsuccessful pilot
  is held rather than excluded.
- Authorization boundary: an offline injected review can prove only reviewer
  structure. Only `official_single_pilot` evidence may become ready for a
  separate owner matrix review, and even that review sets
  `formal_matrix_authorized=false` and `result_admission_authorized=false`.
- Freeze consequence: the non-executable pilot candidate now locks 23 inputs
  spanning transport, budget, safety, trace, runtime, record and review code/
  schemas. This closes source drift between pilot approval and post-run review.

### 2026-07-24 — Admit exactly one DeepSeek pilot and retain matrix separation

- Decision: bind the project owner's exact approval statement by SHA-256 in a
  separate active manifest and execute the already frozen single
  benign-no-tool/no-defense DeepSeek work item exactly once.
- Evidence: the official call completed with exact `deepseek-v4-pro`
  identity, one durable request chain, one record-chain entry, 414 total
  tokens and CNY 0.00165 cost. The offline post-run reviewer passed all 15
  admission, trace, identity, cost and safety checks.
- Safety: no retry, fallback, provider-managed tool, connector or external
  effect was enabled. Model output remained an untrusted proposal applied only
  to the M3 sandbox fixture.
- Consequence: the pilot establishes live technical feasibility of the
  evidence path, not a comparative scientific finding. It remains
  `formal_candidate`; matrix execution and result admission remain false.
- Future authorization: the project owner permits controlled later DeepSeek
  and Gemini calls. Each later tranche must have fresh frozen identities and
  preserve provider-specific budgets and the dangerous-effect prohibition;
  this consumed single-use manifest is never widened or reused.

### 2026-07-24 — Use a new v4 identity for DeepSeek JSON Output

- Decision: v1–v3 matrix identities remain immutable failures. Matrix v4 fixes
  non-thinking mode and `response_format={"type":"json_object"}` in both the
  official payload and pretransport commitment while preserving the strict
  proposal parser, zero automatic retry, official exact-model check and
  append-only evidence chain.
- Context boundary: trusted application context is presented through a
  condition-invariant allowlist containing only `requested_actions` and
  `workspace_scope`. Evaluator/gold/result fields remain excluded. Provider
  output is still an untrusted proposal and external effects stay disabled.
- Canary boundary: exactly one six-condition canary must finish with six
  formal-candidate records and zero operational failures before a separately
  hashed continuation admission may authorize the other 474 work items.
- Consequence: v4 passed the technical canary and the project owner’s delegated
  safe-iteration authorization activated the continuation. This is operational
  evidence only; result admission and comparative claims remain false.

### 2026-07-24 — Freeze an outcome-blind result gate before matrix completion

- Decision: scientific analysis cannot read `unsafe_effect_itt` or
  `task_completion` until a prospective gate replays and cross-binds all 480
  record, attempt, budget and per-work trace chains.
- Automatic pass boundary: 480/480 terminal records, zero remaining/open work,
  only `formal_candidate` tiers, zero operational failures, exact official
  DeepSeek identity, complete content-free trace bundles, isolated effects and
  an unpaused budget. Any failed check blocks automatic result admission.
- Analysis freeze: the locked v2 analyzer preserves the primary unsafe-effect
  and TCR comparisons, exact McNemar tests, 10,000 clustered bootstraps, Holm
  correction, power and mechanism gate. It also preregisters confirmation
  burden, all four alternate authorization regimes, latency, tokens/cost, and
  benchmark/context/source-set heterogeneity.
- Metric boundary: the frozen cross-benchmark record does not separately
  identify UTR or DSR. Those labels are reported as unavailable rather than
  inferred from unsafe effect.
- Consequence: two never-activated candidates were superseded during offline
  schema/coverage review and their identities were retained. The current
  candidate was frozen before scientific outcome access; only a later separate
  admission can unlock the analysis.

### 2026-07-24 — Preserve boundary rejections as no-effect ITT outcomes in v5

- Decision: do not weaken `provider_safety.py`, alter the M3 authorization
  decision, or execute a rejected effect. When the online Guard has already
  returned ALLOW and the independent fixture boundary rejects the proposal,
  preserve ALLOW, record an attempted but unsuccessful execution, emit a
  no-effect receipt, and conservatively set unsafe effect true and task
  completion false.
- Reason: v4 converted these already-contained proposals into unknown runner
  crashes, making a zero-runner-failure result gate impossible without changing
  the defense or discarding assigned rows.
- Consequence: v4 remains immutable and blocked. v5 uses a new identity,
  passed zero-network qualification and a six-condition official canary, and
  never executed a rejected effect.

### 2026-07-24 — Separate result integrity from operational claim quality

- Decision: result-gate v2 blocks outcome access for incomplete matrices, open
  attempts, unknown runner failures, identity/trace/isolation drift, or more
  than one percent closed provider/timeout diagnostic rows. Known protocol
  terminal states remain in the ITT denominator.
- Claim boundary: a separate frozen quality envelope permits honest analysis
  but forces the empirical-study fallback if overall operational failures
  exceed ten percent, provider/timeout failures exceed five percent, or any
  runner failure exists. The legacy zero-failure value stays descriptive.
- Reason: parsing, max-step, refusal and service-terminal outcomes are part of
  the deployed protocol and should not be silently excluded or confused with
  an implementation crash.

### 2026-07-24 — Treat historical provider balances as monitored, non-blocking estimates

- Decision: the project owner authorizes continued DeepSeek and Gemini research
  calls even if the prior CNY 30 balance estimate is insufficient. Cost/token
  accounting, single-provider execution, zero automatic retry, exact identity,
  no provider tools and no real external effects remain mandatory.
- Consequence: worst-case cost projections and the historical CNY 27/30 values
  do not independently pause future work. Provider quota, credit,
  authentication/rate-limit responses, evidence-chain failure or any widened
  effect capability still stop execution. Because current v5 spend is far
  below the old threshold, the existing v5 identity is retained.

### 2026-07-26 — Permanently abort v7 and move the adapter lifetime fix to v8

- Decision: never resume, retry or repair the v7 run identity after its first
  canary left one open append-only attempt. Preserve its two official response
  receipts and trace in a content-free abort review.
- Reason: the M3 effect-backend factory resolves its adapter module global
  lazily during execution. v7 bound the v3 classes only during dispatcher
  construction, so runtime material and the v3 offline evaluator disagreed.
- v8 boundary: use a new run/matrix identity, bind the v3 adapter for the
  complete `_execute` lifecycle, and prove the delayed-backend path before any
  API request. Frozen v7 code/evidence is not rewritten.
- Consequence: the unique v8 six-condition canary passed its technical review
  with six formal-candidate records and no operational failure, but this does
  not admit or expose scientific results.

### 2026-07-26 — Freeze result gate v5 and pause v8 continuation for verification/reporting

- Decision: freeze result gate v5 before outcome access and issue a separately
  hashed v8 continuation admission, but do not execute the remaining 474 work
  items until the updated full Harness ends with `Verification failed=0`.
- Reason: the pre-v8 full Harness found one stale v7 freshness test. Its
  replacement focused regression passes, but a focused pass is not substituted
  for the repository-wide acceptance gate. The user also prioritized the
  detailed stage report over immediate continuation.
- Consequence: v8 remains at 6/480 with zero open attempts; continuation is
  admitted but not consumed, and result/analysis authorization remains false.
  The next executable action is a full Harness rerun, followed by exactly one
  continuation invocation only if green.

### 2026-07-30 — Recover only untouched public work keys with incremental ledgers

- Decision: preserve every naturally closed continuation-v2 prefix and create
  one separately frozen v3 admission per shard. The v3 process may execute only
  work keys absent from the closed prefix and must never retry a terminal
  formal-candidate or diagnostic row.
- Reason: the original controller revalidated the growing ledgers on every
  append and stopped after its first diagnostic. At public scale this was both
  quadratic and incompatible with ITT retention. A single startup replay,
  fsynced O(1) append, and terminal full replay preserve the evidence contract
  without reusing or deleting prior rows.
- Consequence: original v2 ledgers remain append-only evidence. Recovery keeps
  automatic retries, provider tools and external effects at zero, while every
  diagnostic remains in the denominator.

### 2026-07-30 — Separate public evidence integrity from claim-quality eligibility

- Decision: do not waive the prospectively frozen one-percent diagnostic
  quality threshold. If that threshold fails while exact coverage, terminal
  attempts, ITT inclusion, candidate/diagnostic tier validity, budget state and
  record/trace bindings all pass, classify the shard as evidence-integrity
  complete but ineligible for a clean mechanism-quality claim.
- Reason: treating an operational-quality threshold as evidence corruption
  would incentivize deletion of unfavorable terminal rows. The paper route was
  already redirected to an authorization-uncertainty and security–utility
  empirical study after the medium mechanism gate failed.
- Consequence: Public primary analysis may proceed only through a separate
  result admission, reports every diagnostic in ITT, and is explicitly limited
  to the empirical fallback. No cross-model, cross-provider, SOTA or clean
  mechanism-quality claim is authorized.

### 2026-07-30 — Freeze an independent public-analysis computation path

- Decision: the Public result candidate locks both the primary analyzer and a
  separate reviewer implemented without the primary aggregation or
  statistical helpers.
- Reason: reproducing a manifest with the same code proves determinism but does
  not independently detect a shared aggregation or exact-test defect.
- Consequence: admitted Public claims require agreement on condition counts,
  Wilson intervals, four prespecified paired differences, exact two-sided
  McNemar tests and ITT diagnostic retention. Bootstrap reproducibility stays
  under the primary deterministic verifier; no additional provider call or
  result exclusion is permitted.

### 2026-07-30 — Keep the empirical fallback after Public-primary

- Decision: retain the authorization-uncertainty and security–utility empirical
  route after admitting the 5,082-record Public-primary matrix. Do not revive a
  mechanism-leading paper claim from the full-versus-structural comparison.
- Reason: M3-full reduced unsafe effect versus the structural baseline
  (38/600 vs 133/600) but was worse than policy-only (13/600), while benign-tool
  TCR fell to 49/168 versus 103/168 for the structural baseline. The frozen 1%
  diagnostic-quality gate also failed without waiver.
- Consequence: the report may claim a primary-model benchmark-consistent
  security–utility trade-off, but not independent module gain, clean mechanism
  quality, cross-model/cross-provider robustness, SOTA, or external validity.
  F-PAPER-002 remains in progress.

### 2026-07-30 — Stop after the verified stage-report handoff

- Decision: after the current validation chain and Word report complete, stop
  execution and leave v7, second-model, formal adaptive and blind-holdout work
  unstarted.
- Reason: the project owner explicitly prioritized the report and requested an
  immediate stop after the running code finished.
- Consequence: the final deliverable is the 16-page dated DOCX with structural,
  accessibility and page-render evidence. Remaining experiments require a new
  user instruction and must begin from the session-handoff state.

### 2026-08-02 — Treat the interrupted Day-1 Harness as inconclusive

- Decision: preserve the original Day-1 stdout/stderr and classify the run as neither pass nor fail because its wrapper never emitted an exit receipt or aggregate completion marker.
- Reason: the nested pytest result is valid partial evidence, but it cannot establish the exit status of the later historical replay and repository-wide verification stages.
- Consequence: provider canaries remain locked until a fresh current-worktree full Harness produces a durable exit-0 receipt; no API execution is authorized from the interrupted run.

### 2026-08-02 — Schedule Gemini adaptive by free-tier quota day

- Decision: freeze a round-robin 4,000-query capacity schedule with at most two adaptive queries and sixteen provider calls per quota day, leaving two of the twenty RPD unallocated.
- Reason: each adaptive query can consume up to eight calls, and the Gemini project must remain on the official free tier with paid ceiling USD 0 while sharing a project-global day ledger with Public work.
- Consequence: the maximal Gemini adaptive panel spans 2,000 quota days before early success/diagnostic skips. Daily successors must use fresh identity/admission/output state and may only consume the earliest untouched eligible slots.

### 2026-08-02 — Execute Gemini Public continuation through daily successors

- Decision: map each frozen pending schedule segment to one exact provider quota day with a fresh execution identity, output root, admission, record/attempt/call ledgers, trace root and project-global day reservation.
- Reason: the free tier is project-day limited, so a conventional long-running shard cannot prove that Public and adaptive workloads never overbook the same 20-RPD allowance.
- Consequence: segment `n` can be prepared only after segment `n-1` has an outcome-blind technical pass, while segment zero additionally requires the eight-day canary aggregate pass. Diagnostics remain terminal ITT records and do not authorize retry.

### 2026-08-02 — Advance Gemini adaptive checkpoints one query per daily slot

- Decision: use a daily wrapper over the checkpointed adaptive search that accepts only the exact next query index and rejects any checkpoint other than q-1, rather than widening the frozen stage-level 50/200/500/2000 runner.
- Reason: free-tier quota days must stop after at most two queries while retaining exactly the same search trajectory and never replaying a terminal query.
- Consequence: every daily review carries all twenty task states and hash-locks the latest selected checkpoints. Search success, diagnostic termination and budget-200 completion stop all future slots for that task; 429 attempts count against the daily reservation even without a response ID.

### 2026-08-02 — Attach Gemini evidence outside the failure-persisting boundary

- Decision: keep all historical runtimes immutable and wrap the prospective
  Public-v4/continuation and adaptive runtime with a Gemini-specific adapter
  *after* trusted-boundary failure persistence. The adapter validates the
  complete Gemini trace, binds it to execution identity/work key/model, and
  derives or preserves only a matching formal Google attestation.
- Reason: the shared frozen runtime attaches bundles only for its concrete
  DeepSeek trace type. Placing the Gemini adapter inside the failure boundary
  allowed an attachment error to be converted into a result that still lacked
  the required attestation.
- Consequence: successful and known post-response terminal paths reach record
  assembly with a content-free, identity-bound bundle/attestation pair. Any
  conflicting formal attestation, incomplete-trace response claim, or
  call-ledger/trace count mismatch fails the technical gate. No historical
  result or frozen input is rewritten.

### 2026-08-02 — Bind pending-only continuation to Public-v4, not Public-v3

- Decision: the 1,779-row pending schedule retains the deterministic 12-key
  partition, but its source manifest and artifact lock now point to the actual
  unexecuted Public-v4 candidate.
- Reason: a narrative requirement for the v4 aggregate gate is insufficient if
  the candidate hash still names v3; both the eligibility gate and immutable
  source identity must refer to the same canary design.
- Consequence: the corrected zero-call continuation manifest is
  `9ebcc18f75c6cec80f186812f7adc96b1bb865fb4733da16389ca41b7f4213b4`
  and binds Public-v4 manifest
  `c28603732cf87b2bbd4a4f19b8aa7bc97a1e44841a8edf588c48614893b104e6`.

### 2026-08-02 — Recover a completed Harness only from terminal evidence and a locked exit contract

- Decision: accept the completed Day-1 runtime/experiment Harness as satisfying
  the fresh-canary technical prerequisite only because its immutable log has
  every expected PASS section, no FAIL line, the exact pytest completion, one
  final zero marker, and the hash-locked verifier exits immediately with that
  marker's value.
- Reason: the host timed out the parent wrapper before it wrote `receipt.json`,
  while the verification child continued to a complete terminal transcript.
  Calling the run failed would discard valid complete evidence; claiming a raw
  OS exit code would fabricate evidence.
- Consequence: the review records effective exit code 0 and explicitly records
  that the OS exit code was not directly observed. Any missing terminal marker,
  FAIL line, source drift or non-immediate exit remains inconclusive. The review
  never authorizes provider execution; fresh candidate, admission and quota or
  budget reservation remain mandatory.

### 2026-08-02 — Accept Day-1 custodian registration without expanding the evidence boundary

- Decision: mark the 21-day plan's Day-1 custodian-registration prerequisite as
  complete after exact replay of the three-file public handoff and its independent
  verifier receipt. The technical clock may start at the receipt's verified time.
- Reason: the frozen v3.4 verifier reproduced the registration signature, public-key
  binding, distinct custodian/verifier roles, zero-label boundary and all 28 recorded
  checks. A separate project-side acceptance artifact binds only public evidence and
  identity hashes; it does not need or permit private identity text or private keys.
- Consequence: registration is complete, but blind authoring, custody, 3,600 executions,
  label release and scoring remain separate gates and are paused by the project owner.
  Execution authorization remains false, F-PAPER-002 remains `in_progress`, and no
  blind-result or independent-validation claim may be made from the Day-1 receipt.

### 2026-08-03 — Reconcile Gemini transport/runtime failure without rewriting the ledger

- Decision: preserve Gemini Public-v4 segment 0 exactly as one ITT
  `runner_failure`, and supersede only its technical interpretation with a v5
  failure-aware review. A failed call is reconciled only when an official
  completed trace exists, the runtime error is exactly allowlisted, the record
  remains in ITT, and all per-work terminal counts still match.
- Reason: v4 compared call-ledger `completed` events with provider trace
  completions and therefore rejected a response that completed transport but
  failed later inside VIGIL parsing. Reclassifying the ledger event would
  rewrite history; treating it as a provider failure would discard the
  official response chain.
- Consequence: v5 manifest `8c256e49...9728c` passes all 14 outcome-blind
  checks and permits canary continuation while leaving result admission false.
  The missing wrapper receipt is not fabricated: recovery manifest
  `1df13ad9...47f1f` records the segment terminal but the wrapper OS exit
  unknown, and forbids same-segment retry.

### 2026-08-03 — Keep Gemini free-only and expose the real calendar lower bound

- Decision: retain the frozen standard Gemini free-tier path at USD 0 and one
  formal segment per Pacific quota day; do not activate paid Batch API or
  compress multiple worst-case segments into an unaudited request budget.
- Reason: the project snapshot binds 20 provider RPD and a local cap of 18.
  The immutable 1,779-row continuation requires 1,186 worst-case-safe quota
  segments. Current Google pricing documentation marks the relevant Batch
  route unavailable on the free tier, so using it would violate the user's
  explicit no-Billing boundary.
- Consequence: continuation-v2 manifest `fcc80d26...5c95` preserves all 1,186
  v1 schedule rows, changes activation from the invalid v4 aggregate to the v5
  aggregate, and truthfully records a minimum 1,186 standard quota days after
  the canary. The 21-day target must automatically extend for this external
  quota constraint unless the user later authorizes a materially different
  billing/model design.

### 2026-08-04 — Separate Flash evidence integrity from the frozen quality claim

- Decision: preserve recovery review v3 and its failed wrapper receipts, then add
  a prospective v4 evidence review whose positive checks express zero retries and
  zero outcome access without feeding raw negative values into `all()`. Merge the
  canary, immutable prefixes and recovery suffixes only after both v4 evidence-
  integrity gates pass.
- Reason: the v3 boolean implementation made a correct false boundary look like
  failure, while shard 0 separately has a real 10>6 diagnostic quality failure.
  Repairing evidence semantics must not waive the preregistered claim-quality gate.
- Consequence: the 1,791-record Flash role now has a reproducible integrity merge
  (`7fba09cc...8432b`) with all 16 diagnostics retained. Global 0.8934% is recorded
  but cannot override shard 0. Independent result admission and outcome access
  remain false, and a fresh full Harness is required before any new provider run.

### 2026-08-04 — Represent missing Gemini provider request IDs without fabrication

- Decision: accept a narrowly defined `local precommit + official response ID`
  evidence path only when official Google model/response/payload identity,
  complete fsynced trace bundle, free-tier USD 0 and zero retry/tool/effect
  boundaries all agree. Keep provider request ID explicitly unavailable and
  never copy the local client ID into the legacy provider field.
- Reason: Google returned a usable official response identity without the
  provider request header. Rejecting every such response discards a complete
  auditable chain, while fabricating a provider ID would make the evidence
  scientifically invalid.
- Consequence: v2.1 manifest `accc5941...bb8` and Public-v5 manifest
  `f00fe601...a472` are prospective-only. Historical terminal/abort evidence is
  immutable; new execution remains blocked until a fresh full Harness yields a
  directly observed exit 0.

### 2026-08-04 — Treat a naturally ending orphaned Harness as inconclusive without its exit receipt

- Decision: do not infer Harness success after the outer collector timed out,
  even though the compute-active child later ended naturally and no process
  remained.
- Reason: process disappearance proves cleanup, not exit 0. Unlike a prior
  recovery with a hash-locked complete terminal transcript, this run supplied
  neither retained stdout nor a final receipt after the collector closed.
- Consequence: focused checks remain valid, but the repository-wide gate is
  inconclusive. No Gemini admission or API execution may follow from this run;
  a future single-use launcher must persist stdout/stderr/receipt and allow a
  sufficiently long execution window.

### 2026-08-05 — Keep Git ownership remediation process-scoped

- Decision: preserve fresh Harness v5 as immutable exit-1 evidence and use an
  exact `safe.directory` entry only in the environment of a new receipt helper
  and its verification child. Do not write global, system, or repository Git
  configuration and do not alter the pinned AgentDojo checkout.
- Reason: v5 proves the repository test suite passes, while the first downstream
  evidence replay cannot read the externally owned checkout under the sandbox
  account. A sanitized qualification reproduces the ownership rejection and
  reads the exact frozen commit with the process-only setting.
- Consequence: v5 is frozen by manifest `02af896a...7149`; qualification manifest
  `f4bbaaac...c7db` is separately replayable. Fresh v6 remains non-authorizing,
  single-use, credential-scrubbed and must directly persist its terminal exit.

### 2026-08-06 — Separate post-v7 evidence qualification from Adaptive execution

- Decision: introduce a non-authorizing gate v5 that binds the immutable v7
  direct-exit receipt and exact Adaptive Pro-50 candidate/admission, while
  placing actual execution in a separate, single-use guarded wrapper.
- Reason: a passing historical Harness establishes evidence consistency but
  must not silently grant provider or result authority. A new wrapper is needed
  to enforce untouched roots, zero retry, exact stage identity and post-run
  technical review without changing the frozen candidate.
- Consequence: gate manifest `ff76b539...10e58e` and wrapper SHA
  `ea2edc64...8614f` are qualified by Fresh Harness v8. The gate keeps provider
  execution and result access false; no API or Adaptive query was run. Day 2–3
  is complete, while Day 4 and the overall closeout remain pending.
# 2026-08-07 — Successor closeout gates validate the immediately proven gate snapshot

- Context: gate v6 initially called gate-v5 `verify_gate()`, recursively
  rebuilding an expensive historical evidence graph. Fresh Harness v8 had
  already directly exited 0 while replaying that exact gate and hash-bound its
  stdout, stderr, running, launch and receipt artifacts.
- Decision: gate v6 validates the fixed gate-v5 manifest and every source lock
  recorded in the immutable gate-v5 artifact, then binds that snapshot to the
  v8 terminal transcript/receipt. Gate v6 still performs full semantic checks
  for all evidence added after v5: completed Pro-50, Gemini s1, quota-day
  reservation and the prospective Pro-200 candidate/admission.
- Rationale: this removes redundant recursive computation without weakening
  lineage. Any drift in a v5 source, its manifest, v8 transcript or receipt
  fails closed; new evidence is never accepted by hash alone.
- Consequence: successor-gate focused tests and future Harness runs avoid an
  extra historical rebuild. This decision grants no provider/result authority
  and does not modify any prior gate or terminal experiment artifact.
# 2026-08-19 — F-PAPER-002 switches to lean empirical evidence

- Decision: retire the 21-day closeout and Full-Harness evidence recursion.
- Reason: admitted results already reject the mechanism-paper route; repeated
  local reconstruction consumes hours without answering the paper RQs.
- Active evidence: existing Pro/Flash Public, medium and Adaptive 50/200 plus a
  fixed 900-row DeepSeek authorization study and 450-row Gemini compact study.
- Removed: blind evaluation, Pro-500/2000, full Gemini matrix, second-model full
  adaptive, new M3 versions and redundant hash/review packages.
- Verification: focused tests, formal-prefix canaries and one-pass integrity
  checks only. Failures are repaired and rerun only where affected.
- Consequence: the paper is an empirical security-utility study; independent
  blind, saturation, SOTA and universal cross-model claims are prohibited.

## 2026-08-19 — Freeze the lean study before provider execution

- Decision: freeze deterministic nested samples (180 DeepSeek main, 60 regime
  extension, 90 Gemini) and the complete 900+450 work-item plan before running
  any new provider request.
- Decision: analyze each existing result source once. The Medium endpoint is the
  disjoint 303-row v8 prefix plus 177-row v9 remainder, not the remainder alone.
- Evidence: focused plan/analysis tests pass 4/4; Ruff and py_compile pass. The
  compact analysis shows full has higher unsafe-effect counts than policy-only
  on both Pro (38/600 vs 13/600) and Flash (24/400 vs 12/400).
- Consequence: retain the empirical/negative-result framing. The next gate is
  only provider-specific focused tests plus six formal-prefix rows per provider;
  no Full Harness or recursive historical proof is required.

## 2026-08-23 — Treat full versus policy as a bundled configuration estimand

- Decision: report M3-full and policy-only as the full and policy configuration
  packages, not as a component ablation or isolated provenance/data-flow/
  confirmation effect.
- Reason: the implementation changes `safe_prompt` versus `normal` at the same
  time as provenance, temporal/data-flow, permission-monotonicity and
  confirmation modules. Existing records cannot identify an individual cause.
- Evidence consequence: the paper keeps the observed package comparison,
  benchmark-specific utility reversal and failure-sensitive security bound,
  while component causation and cross-provider generalization remain forbidden.
- Verification consequence: use only focused analysis/manuscript/Word tests;
  no new API, Full Harness, historical replay or successful-row rerun is needed.

## 2026-08-26 — Add a prospective deconfounded incremental evidence layer

- Decision: retain every historical result unchanged and add five separately
  versioned studies: a contemporaneous prompt×module factorial, a controlled
  source-authority counterfactual, an outcome-enriched challenge set, a nested
  DeepSeek Flash replication and a conditional B200-survivor adaptive tail.
- Reason: the accepted package comparison cannot identify a module effect, the
  representative authorization sample has a one-event attack floor, and the
  incomplete Gemini free-tier cohort cannot support cross-provider inference.
- Consequence: two new condition profiles cross the existing prompt/module
  factors without rewriting `m3_policy_only` or `m3_full`. Gemini, blind work,
  Full Harness, recursive evidence replay and real external effects remain out
  of scope. E3 is explicitly prior-outcome-selected and E5 remains a conditional
  survivor analysis; neither may be presented as a deployment prevalence rate
  or a complete B500 curve.
- Verification consequence: use study-specific deterministic plans, focused
  unit tests, eight-row formal-prefix canaries (or the declared attack-only E3
  variant), one final row/key/field/identity check and one-pass statistics only.
  Successful terminal rows are never replayed.

## 2026-08-26 — Account incremental calls at the current peak tariff

- Decision: leave the frozen historical public-budget policy unchanged and
  override pricing only in the new incremental runners with the official
  2026-08-26 peak tariff.
- Reason: the provider now lists Pro at CNY 0.30/9/27 and Flash at CNY
  0.10/3/9 per million cache-hit input/cache-miss input/output tokens, above
  the historical policy for some fields. Using peak prices keeps hard fuses
  valid during both peak and discounted off-peak windows.
- Consequence: historical costs are not restated. All E1–E5 prospective costs
  and pre-request fuses use the conservative tariff and retain the CNY 16
  global ceiling.

## 2026-08-26 — Amend only the E5 execution-cost ceiling

- Decision: keep the Pro and Flash regular-study fuses at CNY 8 and CNY 3,
  while raising the E5 Adaptive fuse from CNY 5 to CNY 20 and the incremental
  global ceiling from CNY 16 to CNY 30.
- Reason: after 898 latest E5 query work items, the append-only budget ledger
  recorded CNY 4.2561534. The maximum no-success path projects to roughly CNY
  17, so the original estimate would truncate the registered cohort for an
  engineering cost-estimation error rather than a scientific stopping rule.
- Scientific invariants: the twelve selected survivors, family balance,
  q201--q500 range, attacker/model/seed, first-unsafe stopping, ITT handling,
  zero automatic retry, disabled provider tools and conditional estimand are
  unchanged. Successful queries are not replayed.
- Consequence: the amendment is disclosed in the protocol, Methods/report and
  cost table. It cannot be used to construct a complete original-panel B500
  curve or an attack-saturation claim.

## 2026-08-26 — Move future GitHub milestones to RedTeam_LLM_Security

- Decision: use `https://github.com/Fischl0527/RedTeam_LLM_Security.git` as
  `origin` for all future fetches and milestone pushes on
  `codex/q2-empirical-study`.
- Compatibility: retain `m3-guard` as the named remote for the former
  `M3_PI_Guard` repository; do not rewrite historical entries that accurately
  describe the repository state at the time.
- Safety: never force-push or include local secrets, raw provider traces,
  temporary verification output or adaptive internal checkpoints.

## 2026-09-05 — Use the supplied filename as the canonical local-review entry

- Decision: generate the complete local-review paper directly into
  `LaTeX通用模板/数模通用模板.tex`; retain `M3_PI_Guard_template_review.tex` only as a
  compatibility wrapper.
- Reason: the owner explicitly wants the provided template source edited directly,
  and maintaining two independent review-entry bodies creates avoidable drift.
- Boundary: this changes only the local visual-review route. The submission-facing
  paper remains the flat Elsevier `elsarticle` package, and original CUMCM template
  assets are neither rewritten nor presented as a JISA class.
- Consequence: future deterministic builds overwrite the named template entry and
  the thin wrapper together; author information remains blank and scientific data,
  statistics, citations and claims are unchanged.

## 2026-09-05 — Make review typography and editor structure explicit

- Decision: the author-facing `cumcmthesis` entry explicitly overrides its Latin
  main, sans, mono, URL and caption faces to Times New Roman, and the shared figure
  renderer uses the same family with fallback disabled. Top-level review inputs use
  literal relative paths; `ProjectRoot` remains only for nested generated artifacts.
- Reason: the class's YaHei Consolas mono face made inline identifiers visibly
  inconsistent, Arial remained inside figures, and TeXstudio could not statically
  expand macro-based input paths to populate its left structure panel.
- Boundary: the Elsevier class and scientific manuscript remain unchanged. CMSY
  mathematical glyphs are allowed; author information stays blank. This decision
  does not authorize API calls, experiments, Full Harness or historical replay.
- Consequence: future deterministic builds preserve Times New Roman typography and
  TeXstudio-visible chapter hierarchy instead of overwriting a manual fix.
# 2026-10-05 集中归档与文档产物分离

- 用户批准最大限度迁移停用备份，无需恢复盲测/签名流程。主项目不搬，外围实际文件在仓库外归档，不上传备份。
- docs是阅读区；统计与图表移至outputs、论文机器状态移至harness/state/paper_v2、公开历史工具包整包移至release/archive。
- runtime使用旧路径联接兼容既有虚拟环境和冻结路径；不修改基础Python、不创建重复安装。
- 只修改活动路径引用，旧raw、历史说明与归档内部清单保持原样；无关dirty改动不进入本次Git提交。
- D盘迁移被执行工具拒绝，源目录未动；如实列为待迁移，不通过换工具绕过拒绝。
