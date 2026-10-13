# 复杂任务权限编译v3与三模型验证

- 功能：F-EXP-TASK-CONTRACT-003，in_progress。
- 批准依据：用户2026-10-13明确要求实施完整修订计划，包括权限逻辑和三模型官方推理；Gemini可跳过。
- 当前阶段：实现与定向测试；尚未调用本研究模型。
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
