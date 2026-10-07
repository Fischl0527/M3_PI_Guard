# 综合后续研究实施

## 2026-10-08 60正常任务解释已实际完成

不另写计划。读固定60个受信请求/可信应用声明及工具接口，生成一个版本化只读解释器trusted_intent_review_v1.py；候选接口由逐项阅读注释，不是gold必需列表。联结四条件240既有记录，输出trusted_intent_review/review.csv（60行）和report.md，无内部正文/目标值/新哈希包。

验证：Python3.13.5 -m pytest tests/unit/test_trusted_intent_review_v1.py -q：9passed；Ruff两文件通过。-m experiments.paper_v2.trusted_intent_review_v1实际exit0，60任务/两个基准各30/established contract violations0/API0。负例验证声明缺失、unknown保持、完成后失败、缺失/重复/越界/身份变化结果及未审查任务不会被自动编解释。源码和对应输出不改变旧runtime或raw。

解释：M37可信声明逐字段保留、13直接目标有规则、10须独立确认且没有具体目标；AgentDojo30通用词法路线不保证任意表达。三个模拟API任务有执行/final但评分未完成，脱敏参数不足，保留原因未知。没有足够证据要求新增有界合同修复，不能为效用扩权。最终科学审查/正文收束仍待，整体in_progress。

## 2026-10-08 本切片已执行与验证

从既有缓存实现四当前主图、英中接入与旧五图历史补充；三当前PDF实际构建。源figure12文件、四主表、20补充表保持独立来源。宽表每部分最大五列，原始行号/前两列重复作连接键；原数据列全部保留，无旋转、缩放、scriptsize。图件9pt，最终PDF字最小8.229/8.229/8.635pt。

命令：Python3.13.5运行-m scripts.current_evidence_figures、-m scripts.build_lean_paper_manuscript --sync-chinese-figures、-m scripts.build_lean_paper_supplement --markdown-only、-m scripts.build_jisa_latex；pytest五组43passed，五源码/五测试Ruff通过。绝对latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error -file-line-error -cd三个入口，均exit0。旧check_jisa_pdf_layout.inspect在当前114页输出结构0错误；只保存必要派生预览，未写QA JSON/哈希包。联系图与当前主图/表、补充宽表大图已查看。

首次发现图裁切、图例碰撞、旧补充入口仅12表、续表链接重复、长条件名溢出与字体字框页码误报；逐项修复并通过负例。普通报告manuscript_figures/README.md完整说明outputs结构与区间/未知边界。没有API/服务/统计重算/权限改变/Full Harness/raw覆盖。保持60任务解释与方法/主张审查未完成，不把版式闭合当研究或投稿闭合。

## 2026-10-07 续推：四当前主图

上一目标轮计划交付属于no progress。本轮以当前表3dd0137为基线，先实现scripts/current_evidence_figures.py和定向测试，读取900/480/诊断缓存，画边界、授权完成与配对差、分基准同期安全/效用、首次阻断与终态四图。数值与区间直接取缓存，不统计重算/模型请求。Times New Roman，175mm宽，正文图字至少8pt；Python既有工作流，图/脚本之外不新建审计包。

图1是边界解释，不是有效性证明；图2区分Wilson观察区间与配对Newcombe差；图3明确未知/ITT、AgentDojo原生和M3模拟端点、适配VIGIL；图4为每cell30个正常任务的首个限制/终态分解，不称已证明根因。定向测试覆盖漏字段、重复单元、未知、不一致分母、缓存配对、字体与PDF渲染。导出后直接检查字形、碰撞、轴区对齐及四PNG；普通说明记录结果，不新增alignment/collision JSON。真实当前PDF和60任务解释未验收前整体in_progress。

## 2026-10-07 持续实施：当前表提交与缓存主图

上一目标回合只有综合计划，按no progress处理；本轮实际推进已有设计。先提交已完成四当前主表、历史S13–S20、英中文引用和对应测试（既有32项通过），以及已交付普通规划文件/状态。只提交本轮明确拥有的路径，current-task保留用户原16行，第三方/模板资产/其他未完成工作不纳入。

随后用既有Python绘图工作流从cached900/480/16读取当前图数据，不调用统计分析器、模型或历史重放。科学图技能用于可读Times New Roman、缓存区间、未知分母和实际渲染检查；用户禁止额外工程包，故不建立签名、递归哈希、figure gate体系。允许新图脚本、定向测试、必要图件和普通说明；历史图/数据不覆盖，当前PDF和60意图审查保持未完成直到实际验收。

## 2026-10-06 当前切片：引言、结果层级与中文科学口径

沿用已批准的必要稿件同步，不新建实验或规划。允许修改Introduction、中文对照、英文结果排列生成逻辑、对应定向测试、生成英文MD及既有Harness/总报告。先明确当前900/480/16与历史研究的层级，再同步核心摘要、研究问题、方法、结果、讨论和结论。旧数字保留为历史标签；旧表图仍待下一切片重排，不借本切片宣称最终双语/PDF完成。

验收：英文Results以修正版研究开头且旧段落不丢失/不重复；引言不再将旧exact效用崩溃及旧E6当当前机制效果；中文核心数字、未知、oracle与端点边界与英文一致；定向pytest/Ruff/文稿生成通过。原raw/分析JSON与CSV不改、不API、不启动服务、不做统计重算、Full Harness或LaTeX编译。无关dirty保留，范围提交并推送。

相邻生成冒烟发现`build_jisa_latex.py`将图表插入锚点硬编码为旧小节号，重排后4项测试失败。必要范围扩展仅修该生成器与其定向测试，改为唯一语义标题匹配；仍只在测试临时目录生成，不覆盖模板、不编译PDF。

### 本切片已执行

- Introduction改为三项当前RQ，保留历史六问题为研究演进；Methods补齐相同映射及基准安全定义。Results层级生成只移位current节，旧内容字项守恒、缺失/重复当前标题fail-closed。
- 中文核心改为当前900/480/16叙事，历史章节显式标注；新增4.1及3.17，当前未知/478与476分母/oracle/完成后失败等与英文一致。旧8表5图尚待下一切片，不说最新PDF或完整版式验收完成。
- `F:\robot\Anaconda3\python.exe -X utf8 -B -m pytest tests/unit/test_build_lean_paper_manuscript.py -q`：18passed/0.35s；`-m ruff check scripts/build_lean_paper_manuscript.py tests/unit/test_build_lean_paper_manuscript.py`：通过。
- `-m scripts.build_lean_paper_manuscript`：exit0，6主节/17904全文件词数（含表/引用）。初始3失败确认旧口径与层级，后来断言措辞/换行问题已修；最终没有削弱端点、数字和内容保留约束。
- 原raw与分析输出不变，不API/统计重算/权限修改/Full Harness/当前LaTeX编译。整体目标保持active，主表图与最新PDF、60任务受信意图及可选研究仍未闭合。
- 相邻生成器首次4失败暴露旧4.8锚点，改用既有`_strip_number`解析唯一语义标题，未改表图/模板。`-m pytest tests/unit/test_build_lean_paper_manuscript.py tests/unit/test_build_jisa_latex.py -q`：24passed/0.76s；四相关源码/测试的Ruff通过。只在测试tmp生成，未编译或覆盖主LaTeX/PDF。
- 范围提交a44281cdf54dd46e85121d4a763d4d39d561d208（17文件）推送RedTeam_LLM_Security的codex/claude-review-repairs，远端精确核验一致；保留current-task原16行和其他用户dirty。未公开内部trace/密钥/第三方或模板字体资产，目标active。

## 2026-10-06 当前稿件科学修订切片

持续目标继续实施，前一目标轮的延迟修复是实际进展。最新v3规划已交付；本切片按既有论文同步授权修改英文abstract/methods/results/discussion/conclusion源，先纠正旧exact和旧安全端点强解释，并加入900/16/480及延迟说明。保留原始结果，不API、不统计重算、不修改授权、不Full Harness。

允许本切片修改上述五份源、必要的文稿内容定向测试和既有Harness。先核对原段落及已有结果→精确apply_patch修订→内存文稿生成/定向pytest/Ruff及格式检查。英文生成稿、中文、图表主次重排和当前PDF如未完成，须明确保持待办，不把局部文字修正称为完整论文同步。

使用学术研究技能做忠实修订；用户禁止额外工程包装，故使用普通源码补丁和Git差异，不新增ARS哈希/锚点/签名/Revision Bundle，也不声称通过那些契约。

### 本切片实际结果

- 英文五份源已修订：撤回旧exact崩溃/固有反转与旧E6强效果叙事，加入新版900授权、16合成、480同期、缺失收据和延迟边界。历史原raw/统计不改，oracle派生权限和模型原始答案隔离明确区分。
- `F:\robot\Anaconda3\python.exe -X utf8 -B -m pytest tests/unit/test_build_lean_paper_manuscript.py -q`：15passed；`-m ruff check tests/unit/test_build_lean_paper_manuscript.py`：通过。新增内容负例约束旧强结论不回流、未知VIGIL边界和模型/模块贡献限制。
- `F:\robot\Anaconda3\python.exe -X utf8 -B -m scripts.build_lean_paper_manuscript`：exit0，实际更新manuscript_deepseek_v1.md，6主节；生成器全文件计数18117词（含表/引用等），不是已完成的目标正文篇幅验收。
- 中文仍旧版本，主表/主图仍以前期研究为主，Introduction与整体章节主次尚须同步整理；没有本轮PDF编译/版式验收。不要将局部源修订及生成成功解释为投稿就绪。
- 无API、授权行为修改、历史统计重算、Full Harness、服务启动或成功实验重跑。60任务受信意图核对仍待，可选180/108仍未合格。
- 本切片及新计划17文件提交6eefc97e6da1d366de678b4d8f4dd356a82892b1已推送origin/codex/claude-review-repairs，远端精确匹配；原16行current-task与其他用户dirty保留，未纳入internal/模板资产/第三方改动。此行是推送后回执，不再循环提交。

日期：2026-10-06。功能F-PAPER-002。状态：in_progress。

## 授权与范围

用户授权按docs/research/paper_v2/M3_PI_Guard_综合评估与后续研究计划_2026-10-06.md最大限度推进。不是重复运行已完成916条。主线P0诊断、P1同期校准；P2独立本地模型、P3原生动态基准与VIGIL按适配资格条件推进。

允许：新experiments/paper_v2实现、必要最小定向测试、新outputs/experiments/research_followup_20261006_v1产物、报告及必要论文/构建同步、Harness状态、范围Git提交推送。只有可复现实现违约才新增修复版本。

禁止：改写旧raw/冻结输入、成功行重复、无条件权限扩大、Gemini、Full Harness、历史递归验证、盲测、日期等待、真实邮件/支付/生产接口/宿主代码执行、上传内部请求/密钥、打包其他dirty或强推。

## 步骤与验收

1. 一次读取本研究900公开事件，覆盖240主良性及105非正常终态，分开记录首次阻断、完成和失败。未知保留，不从内部正文猜原因。
2. 紧凑复现必要接口问题，只在违约成立时修复；保留corrected_v2历史语义。测试先于API。
3. 在查看新结果前固定120配对案例及normal/auto三条件，12正式前缀包含在总数内；无防护与防护共用相同模拟能力与宿主边界。VIGIL调用前决定资格，不按结果筛选。
4. P1只运行pending新项；各任务独立状态、最多并发2、8请求/180秒超时/无自动重试。取得模型响应的行不重跑；未知/失败/未运行分别报告。
5. P2本地180和P3原生108先离线和格式资格化；不能忠实适配时透明说明，不伪造正式结果。
6. 一次重建各新研究统计/图表/Markdown报告，按批准路线更新解释边界和必要双语/LaTeX稿件；作者空白。
7. 代码资格化、结果、报告/稿件三个范围Git节点推送当前origin/codex/claude-review-repairs；不强推。

## 初始事实与假设

- 当前HEAD44ea311，当前无Python/Ollama实验进程。已有900主研究0/490攻击效果，但没有同期no-defense，不能证明防御有效。
- 低效用候选原因：①编译器缺工具/目标权限；②动态参数或非预期动作；③格式/长度/步数；④执行后评分条件未完成。仅是待检验假设。
- 首条抽查正常AgentDojo任务第一步ASK/permission_expansion/tool_outside_current_permission；只能确认缺工具许可，不说明许可必然应生成。
- 现有CorrectnessRuntime尚未注入VIGIL live factory且8-call硬限制；若添加基线需专用显式适配，不能把默认失败路径当合格基线。

## 验证记录

已运行Python3.13.5：pytest diagnosis4通过；P0一次性读取900，输出240主良性+105非正常的去重300行解释表。AgentDojoauto两条件26/30首先缺工具许可；length截断0，完成后失败2；不能单凭公开事件认定动态目标或编译器缺陷。

初次新资格+相邻回归83通过/8失败：6个错误布尔断言、2个无效VIGIL空约束fixture；未改源码安全行为，只纠正fixture。受影响8项再跑通过/5未选择，既有第三方Pydantic弃用警告保留。Ruff发现一个新文件未使用Path导入，删除后待复查。

VIGIL适配使用既有固定源码bridge（单次约束生成、禁止静默fallback）和确定性hybrid审计；这是明确配置的对照，不冒称完整默认VIGIL。P1冻结480=360主线+120VIGIL；12主前缀+4基线前缀均计入总数。已有normal/512/180秒不改。

## 实际运行与恢复

- 资格5676768已push/远端一致。16正式前缀全部completed，主12均可解析、VIGIL4合格；核心/基线门均passed。
- 第一扩展记录到120/480后停止：109completed/2max_steps/6parse_failure/2runner_failure/1provider_failure。两VIGIL失败有HTTP200、精确身份与length截断；Stop信号使一条已有响应ND任务终止。三者已有响应全部保留，禁止重跑。
- 新研究telemetry_v1.1仅修复线程输出和截断错误分类，512/T0/提示/权限/任务/工作键不变。当前线程logger过滤不替换stdout/stderr；身份有效length约束失败记parse_failure且端点未知；其他系统错误仍停。2定向回归通过，Ruff/编译通过。即将继续未触碰360；不恢复任何120终态。
- P2隐藏启动被工具策略执行前拒绝，不绕过；本地180未执行。P3新18参考链诊断0API、8true/10false、无物理效果；叶子动态调用监控和合法/越权状态评分对照尚不合格，不启动108模型研究。
- 分析模块4定向测试通过：未知ITT、Holm家族、退化CI、完成与失败共存、身份/成功重复。实际480统计尚待终态一次执行。

## 动态占位评分控制及当前进度

- 当前95802正常运行，已记录400/480，无新stop。d0d0e2d日志修正已推送；第一阶段所有120记录原样保留，新续跑不重发其请求。
- 新agentdyn_followup_controls_v1是离线oracle夹具控制，仅为verify_shopping/github的原固定占位参数读取当前虚拟账户唯一待验证队列，不改变工具、评分或原参考；歧义队列拒绝，不记录虚拟值/正文，也不进入在线授权。
- 4单元测试及Ruff通过；fresh UTF8进程执行18控制，15参考完成、3仍false、无操作0/18，0 API。原8true/10false不改写。shopping_task4参考购买quantity1而评分要求quantity2，源内不一致已看到；github9与dailylife5仍需进一步评分状态分析，不声称修好上游。
- 原生动态网页注册函数及验证码回调在外层runtime下面执行，叶子Guard全覆盖未合格；108模型项不启动。先交付诊断，不凭15/18将整个原生环境判为可部署。

## 本研究批次收尾

运行器95802正常exit0，480唯一work key/attempt1，443completed/9max_steps/25parse_failure/2runner_failure/1provider_failure，1172官方响应/1578814tokens。首次120全部保留，其余360telemetry_v1.1不改科学条件。无活动研究进程。

`python -X utf8 -m experiments.paper_v2.research_followup_analysis_v1`仅执行一次；Newcombe/10k任务聚类/Holm/Wilson/McNemar实际表图完成，图目视通过。随后只补公共收据计数和说明，不重做统计。478字段投影明确false、2缺；476结构化效果收据、4缺（VIGIL约束生成失败），旧记录不后补。

最终`pytest tests/unit/test_research_followup_diagnosis_v1.py tests/unit/test_research_followup_calibration_v1.py tests/unit/test_research_followup_analysis_v1.py tests/unit/test_agentdyn_followup_controls_v1.py -q`：27passed/1既有Pydantic warning；收据计数负例后`pytest tests/unit/test_research_followup_analysis_v1.py -q`：5passed。范围Ruff全通过。批次重叠不相加；不Full Harness或历史复验。

根report.md已记录实际480、P0原因、P2策略拒绝/P3离线15/18和安全资格缺口，清楚解释outputs目录。AgentDojo正常任务17/30→2/30代价显著，安全3/30→0/30区间跨零；M3无防护仍全零，不支持模块领先。科研整体和论文未完成，F-PAPER-002保持in_progress，下一步批准的稿件/LaTeX同步。

公开结果提交7b1114f43f4cbf21e933b48ad064b287726ed38f已push，ls-remote精确一致。21范围文件；内部trace未上传，原其他dirty和current-task16行保留。后续纸稿同步有明确批准范围，不能因为本批480完成就把整体目标标complete。

## 继续实施：已确认的测量缺陷

持续目标下先实施v2计划P0-A。原480条中476条latency_ms为包含total/model/guard/tool的对象，4条缺失；现有分析器只采集标量，使p50/p95为空。修复不改变许可或评分，不重复调用模型，也不重新计算已完成的bootstrap/配对分析。

本切片允许修改research_followup_analysis_v1.py及其定向测试、当前calibration下独立延迟派生表/JSON和简短说明，以及本任务/必要Harness。禁止改raw、原analysis.json/cells.csv、历史计划、推断结果、模型参数、权限逻辑或内部trace。

步骤：①针对真实对象格式新增可复现测试；②兼容对象total和旧标量，拒绝bool/非有限/负数，保留缺失和分项；③新增显式latency-only入口，读缓存推断结果但不调用analyze/paired，输出独立版本化延迟产物；④一次运行与定向pytest/Ruff/内存编译；⑤记录量、字段与原科学统计保持不变，范围Git推送。

验收：476可用/4缺失如实反映，任务总延迟与分项分开，统计刷新不触发配对/bootstrap，旧raw与主统计未改，失败/未运行仍保留。论文及可选研究不因这个修复被标为完成。

实际验证：初始真实对象负例1failed/5deselected，随后完整受影响统计测试16passed in0.62s，Ruff passed。`python -X utf8 -B -m experiments.paper_v2.research_followup_analysis_v1 --refresh-latency-only`只运行一次，exit0；480原记录、476可用/4缺失/0非法、16分层cell。`git diff --exit-code`针对raw_records.jsonl/analysis.json/tables/cells.csv为0；没有重新模型请求或原推断。派生表与普通说明独立，根报告目录入口更新。论文同步仍待，不能据此结项。

本次有限源码查找确认generic-v2会删除必填目标未解析的工具规则（policy_compiler_corrected_v2.py），说明“词法选中后因范围未解而不允许”可解释某些缺许可，但未对60个受信任务完成个案核对，不能直接认定新缺陷或放宽全部参数。

Git修复节点：a3ed482262b87d0187e7d094d157c3eb10135305，15文件；已推送origin/codex/claude-review-repairs，远端SHA与本地一致。最后追加writer不覆盖原文件的1项测试再通过（属于同16项，不相加），Ruff/两源内存编译/JSON/16行延迟计数及暂存diff检查通过。原current-task16行保留未提交，其他dirty未打包；该节点不含论文科学同步。
## 继续实施：当前主表与历史补充表

上一目标回合仅交付v4计划，无实施进展；当前安全可执行步骤是缓存证据的稿件集成。范围：现有稿件/补充/LaTeX生成器、对应测试、双语表与引用、必要报告和状态。四张当前主表读取900/480/16缓存JSON；旧八表原数据和注释移到S13–S20，原S1–S12保留。不API、统计重算、权限改动、Full Harness或当前PDF构建。主图与PDF仍待下一切片，不能宣称整体排版完成。

验证计划：数值/未知/观察与计划分母测试、历史表内容保留、英中文表同源、四张主表与二十张补充表及临时LaTeX语义定位测试；Ruff和内存编译。实际只生成Markdown（无新Word），相关Git里程碑推送，保留无关dirty和current-task原16行。

实际完成：四主表、S1–S20补充及英中引用生成。`python -X utf8 -B -m scripts.build_lean_paper_manuscript --sync-chinese-tables`和`python -X utf8 -B -m scripts.build_lean_paper_supplement --markdown-only`exit0；前者全文件16949词（最终引用补充前），不是目标正文词数。表格/文稿26passed，LaTeX临时生成6passed，范围Ruff通过。三项初始失败为缓存区间测试值及旧注释读取位置，纠正后通过，未改统计。现有八历史表的全部数字/注释及S1–S12正文由定向测试保留；主表最多五列、不旋转。旧宽补充布局与当前主图/PDF仍待，未实际构建模板、不称视觉通过。

最终合并定向pytest（current_evidence_tables、build_lean_paper_manuscript、build_lean_paper_supplement、build_jisa_latex四模块）32passed in1.09s；之后仅格式化新增helper/test并复查同32项通过。范围Ruff与四源码内存compile通过，最终英文16987全文件词数。Git差异检查确认900/16/480的raw、analysis与原cells.csv未修改；feature JSON合法且in_progress。原始统计只格式转换，不重新做推断。
