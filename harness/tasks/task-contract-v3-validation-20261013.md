# 复杂任务权限编译v3与三模型验证

- 功能：F-EXP-TASK-CONTRACT-003，in_progress。
- 批准依据：用户2026-10-13明确要求实施完整修订计划，包括权限逻辑和三模型官方推理；Gemini可跳过。
- 当前阶段：开发资格化和反例修复；已调用44次Pro开发编译，正式矩阵尚未启动。
- 执行环境：主路径E:\M3_PI_Guard_test，F:\robot\Anaconda3\python.exe / Python3.13.5。
- 主交付计划：docs/复杂任务权限编译改进与验证计划_2026-10-13.md。

## 范围及所有权

核心Builder新增m3_core编译v3、m3_guard契约/monitor及测试；数据Builder新增task_contract_cases/plan/synthetic与测试；运行Builder新增task_contract_runtime/study/compilation、受限可选装配与provider参数兼容；根代理负责文献、统计、报告、集成验证、Harness与限定Git。

禁改：历史原始记录/输入、论文/LaTeX、盲测材料、密钥及17原有暂存PDF。当前worktree有大量既有论文、翻译、Harness改动，全部保留。代码注释中文，标识符/CLI保持英文。

## 决策与风险

- 新任务约束不能被输出正文自报；schema通过不等于来源可信。
- 原生后端目前没有可信对象Resolver；新增字段白名单与真实成功发现绑定，不能整对象提权。
- 新合同固定首草稿，全模型/两重复共用；生成失败不择优。
- 原生AgentDojo非盲测且组合复用；新400评估必须去除仅参数/语言变化的重复约束图。
- 模型前缀必须先等离线验证；不FullHarness、不历史重算。
- 客户端本研究12调用、编译4096/Gem2048参数要同步请求校验和保存；不放宽旧范围。
- API程序从Git忽略的既有配置加载，代理不查看、输出或复制凭据。

## 验收

1. 公共类型兼容、无gold/evaluator在线字段、无provider工具/外部effects。
2. 开发/评估结构隔离、600评估基础项、36000主矩阵＋960Pro消融上限。
3. 16000离线判定、定向测试、首草稿不选优、失败/未知/未执行分开。
4. 正式模型/参数/ID收据、pending-only与响应项不可重跑；Gem服务故障独立结束。
5. 聚类/配对统计和MD报告能从本研究raw一次重建，全部计划项有明确状态。

## 验证记录

待实现后记录精确命令、结果和失败。当前已核对AGENTS/Harness/permissions、分支origin/codex/claude-review-repairs及Python3.13.5；未新增实验响应，不声称完成。

- 文献：nature-downloader的batch_download.mjs使用四个官方固定PDF URL、--route open_access --no-si，全部exit0；不使用机构登录或API凭据。
- 原件复制到docs/文档资料21–24，不覆盖旧件；PyMuPDF逐个校验版本标识及页数，20 Progent17、21 PACT24、22 AgentSpec12、23 CaMeL125、24 AuthGraph19，五文件首页文字可读。中文导读已落盘；PDF不自动公开Git。
- 当前参考文献已交付不代表编译器或模型实验已完成。

## 集成复核与最新执行决定

- 用户确认当前Gemini免费层无法确认，要求跳过；本轮Gemini调用为0，原因current_free_tier_unconfirmed_user_skipped，不能记成模型失败。
- 新统计模块18项测试通过（0.43秒），Ruff通过；重复先在基础任务内汇总，再按复用组/模板/约束图聚类。已测试未知保留、响应项禁止重发、12调用累计上限、全零区间退化和预选消融复用new_full。
- 核心/运行Builder定向测试持续推进；扩大离线回归91通过/1失败，失败是旧PromptGuard固定缓存目录缺失，不在本轮新增模块。禁止为绿色结果关闭原测试或下载大模型；最终相关窄回归单列该环境依赖。
- 正式资产尚未生成。复核发现合成评分将任务完成与unsafe耦合、八类部分缺实际日期/多跳/硬禁止机制、可信标签未接入完整合成循环；已要求修复并增加真实执行负例。这些问题修完再冻结资产，不把计数当运行证据。
- 开发157任务（17AgentDojo+60M3+80新任务），开发先单稿；600评估各三稿，编译最多1957请求，不在开发阶段额外三稿择优。
- 2026-10-13核对官方中文价格页面：Pro峰时缓存命中/未命中/输出为0.30/9/27元每百万tokens，Flash为0.04/2/8；闲时减半。本研究记录调用与区间估算，不当作账单，既有核价时间戳不改写。

## 第一实施节点

- 已用`python -X utf8 -m experiments.paper_v2.task_contract_plan_v1`生成600评估/157开发及36000主矩阵+960消融计划，模型响应0；资产不写入论文，原始历史不改。
- `python -X utf8 -m pytest tests/unit/test_task_contract_cases_v1.py tests/unit/test_task_contract_integration_v1.py tests/unit/test_task_contract_analysis_v1.py tests/unit/test_task_contract_v1.py tests/unit/test_task_contract_monitor_v1.py tests/unit/test_task_contract_runtime_v1.py tests/unit/test_task_contract_study_v1.py tests/unit/test_task_contract_compilation_v1.py tests/unit/test_correctness_provider_v1.py tests/unit/test_gemini_correctness_recovery_v1.py tests/unit/test_generic_policy_corrected_v2.py -q`：174通过，15.84秒。
- 合成评分耦合/缺字段的负例首次5失败6通过，修复后12个数据/结构/后端测试通过；后端日期必须真实修改对象，二跳有限集合查找必须实际返回联系人。新增四个跨组件边界测试通过。
- Ruff和10新模块py_compile通过；全量模型矩阵、消融、16000离线判定及正式统计尚未完成，功能保持in_progress。
- 报告入口outputs/experiments/task_contract_compiler_v3_validation_v1/report.md，独立说明完成范围及所有目录。

## 真实开发诊断（原记录保留）

- 修复c36b67e已推送且远端精确一致；之后一次性`python -X utf8 -m harness.tmp.qualify_task_contract_development`选8未调用M3+8未调用合成开发项，exit0。新增16响应/2compiled/14失败，原28条逐项保持；累计44响应、4compiled/40失败。版本初始3/v2 25/v3 16分开报告；新复杂任务0/16尚不具备正式扩展开发证据。
- development_summary_v1.json只评估开发资格，正式终点字段null/未评估，不能靠硬编码0假称未来矩阵状态。原始44条usage129208 tokens、ID完整、provider tools/external effect均0；当前本研究正式pro/flash原始结果文件确实尚不存在。
- 最终可信工具类型检查新增后，只重跑直接涉及的五模块：70 passed，3.22秒；Ruff与两模块py_compile通过。与194相关回归有重叠，不求和；无任何原响应再执行。

- 最终本轮离线命令在原11相关测试模块基础上加入test_task_contract_offline_replay_v1.py和test_task_contract_review_regressions_v1.py：194 passed，26.04秒，exit0。新增反例首次9失败/3通过，修复后全相关通过；未FullHarness。
- `python -X utf8 -c "from experiments.paper_v2.task_contract_cases_v1 import write_semantic_metadata_v2; print(write_semantic_metadata_v2())"`：480元数据行、修60图、80/400唯一、重叠0、模型调用0。只新增v2映射，未覆盖v1资产或参考动作。
- `python -X utf8 -m experiments.paper_v2.task_contract_study_v1 --offline-replay`：明确missing_fixed_first_evaluation_contracts、400首稿缺失、实际Guard决策0；无回放raw产生。这是预期资格拒绝，不作为完成或绿色运行。

- 2026-10-14续行：28次Pro开发编译均取得响应，原记录2compiled/26compile_failure（17AgentDojo、3M3、8合成开发项）。Gemini12000可选项明确not_run、0调用，不恢复旧批次。正式Pro/Flash执行、评估三稿、16000回放尚未运行。
- 只读复核以纯内存反例证实：假设/引述动作语境可能误授权；native发现ID丢对象类型；效果评分遗漏顺序和重复次数；日历跨参数关系未检查；多跳规范图手填引用不一致。批准研究内修复并加负例；原冻结v1文件不覆盖，规范图修正若采用需独立版本与逐项验证。
- 修复顺序：先语境与类型边界，再效果/日历及图引用；运行定向pytest/Ruff；现有28模型响应不重发、不覆盖。离线回放需400实际首稿，缺失时执行数0并明确拒绝；不得用计数打印代替判定。

- `python -X utf8 -m experiments.paper_v2.task_contract_study_v1 --compile-contracts --compile-stage development --compile-limit 3`：3次HTTP200、固定Pro模型身份；原始编译失败invalid_identifier因为数字动作标签。
- 修有限数字标签、问题式请求的必要查找与状态not误判；禁止路径/代码/评价字段、不能以读取闭包扩大副作用。46相关测试/Ruff通过。不重发原3请求，原失败草稿不覆盖；正式评估尚无响应。
- 新开发提示version task-contract-prompt-v2，逐条记录指令digest/编译revision；评估固定首稿不得选优。已有开发原版本单列，不冒称整个统一版本。
- 设计ccba131、实现790268b都已推送并核对；原17暂存保持。隔离状态暂存首次因PowerShell stdin增加空行及旧字符解码而预检失败，后以原Git对象字节+当前任务章节修复，预检通过后才提交；无用户原文件回写。
