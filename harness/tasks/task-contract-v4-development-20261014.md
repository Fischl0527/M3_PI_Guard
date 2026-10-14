# 权限编译v4开发验证任务

- 用户批准：2026-10-14；F-EXP-TASK-CONTRACT-004 in_progress。
- 范围：新显式v4编译/引用装配、32未触碰开发任务、双模型640项上限、文献26/27、中文MD和限定Git；不正式大矩阵。
- 计划：docs/权限编译v4改进与双模型开发验证计划_2026-10-14.md。
- Builder所有权：core与对应tests；runtime/monitor与tests；开发selection/compiler/runner与tests；根代理文献/状态/集成/模型/分析交付。
- 风险：类型化新建收据、逐记录关联和参数证据不可仅提示模拟；ready率不等于权限正确。资格组一轮，修复后不能伪称未触碰。
- 验证：受影响pytest/Ruff/编译、原v3兼容、实际模拟后端链、前缀技术门80%；尚未运行v4 API。
- 安全：无Gemini、无真实tools/effects、无secret输出、原44raw/600正式样本/17暂存只读保留。
- Git起点：index tree53fccb7f7260e275ae728dad51d7e0939db49afd；当前origin个人M3，分支codex/claude-review-repairs。

## 实施与验证记录

- 文献20–22已核验PDF头、页数、题名及版本；26/PICARD（7页）及27/世界模型规划（14页）已从官方页面下载，中文导读落盘。全文本地保留，不纳入Git。
- prepare实际生成32独立开发任务：调试16、资格16；每模型320计划项，共640，尚无新研究API响应。与原44已响应项无交集，600正式评估未接触。
- 客户端/统计定向11 passed（2.24秒）；扩大v3/v4相关回归164 passed（12.38秒），包含重叠用例，不相加为独立测试数。runtime/runner仍在共同集成，不视为工程全部通过。
- 同模型640项分母包括编译失败、澄清及未知；编译首次/唯一技术修订、调试/资格、Pro/Flash分别分析。经验bootstrap退化不输出确定性[0,0]。
- 用户确认后仅删除旧空Git锁；原暂存tree53fccb7f7260e275ae728dad51d7e0939db49afd保持。尚未创建v4实现提交。

### 共同工程验收（2026-10-14）

- 精确pytest命令：`F:\robot\Anaconda3\python.exe -X utf8 -m pytest tests/unit/test_policy_compiler_corrected_v4.py tests/unit/test_task_contract_runtime_v4.py tests/unit/test_task_contract_v4_development_v1.py tests/unit/test_task_contract_v4_provider_scope.py tests/unit/test_task_contract_v4_development_analysis_v1.py tests/unit/test_task_contract_runtime_v1.py tests/unit/test_task_contract_monitor_v1.py tests/unit/test_task_contract_compilation_v1.py tests/unit/test_task_contract_review_regressions_v1.py tests/unit/test_correctness_provider_v1.py tests/unit/test_task_contract_v1.py tests/unit/test_task_contract_integration_v1.py -q`：237 passed，12.19秒，exit0。
- Ruff：8个本轮实现/修改模块、5个本轮测试文件，全部通过；8模块py_compile通过。此前164/223/236均重叠阶段检查，不相加。未运行FullHarness。
- 补齐缺条件/缺步骤依赖负例：初检45通过2失败；v4现在对遗漏明确条件或顺序进入不可技术修订的澄清，保留真实用户确认与禁止。
- 实际八类模拟合法链、逐对象来源、创建收据、顺序/重复及未知保存通过定向测试。它们是程序受控测试，不是模型编译或端到端效果。
- 计划compiler_version与运行compiler_revision分开，避免成功记录保存后无法续跑；任务限定scope12次、Pro编译4096、执行512、HTTP自动重试0、Gemini禁止。
- 统计图源码20项静态检查通过、1项PNG非TIFF提示（本轮报告不投稿，不需要TIFF）；尚无真实数据出图，不把源码检查当作视觉验收。

### 实际调试编译与原生装配

- 388c012实现已推origin当前分支，ls-remote一致；原17暂存逐字节保持。
- debug16任务同期v3/v4编译34官方请求、34响应：v3最终3ready/16；v4最终0ready/16，包含2次预定技术修订。全部保留，不重发响应行、不把澄清当作通过。
- 执行前缀初始化发现旧原生resolver缺selection_id，尚未发执行请求。新增显式内存兼容映射和可选resolver输入，不改冻结输入或旧默认。
- 新实际冻结计划装配/沙箱/评分冒烟及runtime23测试通过（2.66秒），Ruff通过。受控回放3定向测试通过（0.92秒），缺真实32编译时拒绝而非打印假计数；M3无完整参考链明示not_applicable，不凑合法TCR。
- 下一步：兼容修复Git后，双模型20项技术前缀；通过才续debug pending。资格16组仍未接触。
- be9d063兼容修复已推并核对远端；Pro前缀4/4可调用项解析，调试160实际记录完成（44response-bearing执行项/146官方调用）。Flash前缀4可调用仅2解析，正式20记录保留、未扩展。
- Flash原生2项完成，合成2项StrictProposalError（均HTTP200、58输出token），不能指称传输故障；不存响应正文，不能事后猜测或重解析。按固定技术门封闭剩余300项，JSON状态声明未运行范围，不生成300假raw行。
- 仅Pro继续原16资格任务；资格首次前固定实现/prompt。解析门例外仅用于明确封闭模型，不放行共享安全问题。53相关测试/7.11秒和Ruff通过（与此前重叠）。
