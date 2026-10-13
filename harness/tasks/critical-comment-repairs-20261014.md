# 重要代码中文注释勘误与限定交付

- 用户授权：修正上一轮重要代码审查确认的24项注释问题并提交、推送。
- 功能：F-DOC-008，verified；仅24项重要注释勘误及限定交付，不代表全项目注释审查完成。
- 起始提交：`790268b126834eac9c11376f48d5c54b41c0c31b`。历史审查基准c5cc2cd；不回退后续功能提交。
- 允许：13个已审源码文件中的文档字符串/说明，本任务记录与必要Harness状态增量。
- 禁止：修改执行逻辑、接口、字段、常量、认证授权算法、v3新代码、模型实验、论文/PDF/产物以及其他任务改动。原17个PDF暂存保持。
- 计划：逐项按实现修正文档；检查13文件执行AST不变及补丁仅改docstring；运行最相关离线测试；限定暂存并检查Git差异；正常提交/推送和核对远端；补齐验证记录。
- 验收：24项全部有对应勘误；13文件AST与起始提交一致；选定测试及Git空白检查通过；提交仅包含本任务，原暂存保持，GitHub分支核对一致。

## 勘误清单

1. task_policy：审批记录的内容摘要不是数字签名，也不认证签署主体。
2. runtime_monitor：前置工具只检查已出现，不检查彼此次序。
3. runtime_monitor_corrected_v1.evaluate_action：决策审计信息不是执行收据。
4. runtime_monitor_corrected_v1._matches：已提供的可选参数也必须满足约束。
5. statistics.latency_summary：没有P99字段。
6. paper_statistics.paired_binary_family：输出McNemar/Holm结果，不计算置信区间。
7. policy_compiler_corrected_v2：未解析必需非内容安全参数不自动授权；内容字段与显式应用声明有独立处理。
8. tool_sandbox.sandbox_seed_sha256：只哈希运行时版本和seed，不哈希夹具或实际初始状态。
9. policy_regimes.build_policy_regime：返回策略清单对象，不是编译器函数。
10. project_config.validate_project_config：只校验配置字段/格式/数值，不检查目录或运行依赖。
11. agent_runner._trusted_tool_authorization：渲染已有authorized_actions，不从用户文本推断权限。
12. agent_runner._model_authorization_contract：返回结构化列表，不是文本。
13. agent_runner._single_quotes_to_double_quotes：仅替换引号，不保证标准JSON。
14. run_batch._completed_case_ids：收集终态，不限定成功。
15. run_batch._error_log：构造并返回字典，不写日志。
16. run_batch._csv_cell：转换字段表示；CSV转义由DictWriter完成。
17. run_batch._order_and_limit_cases：保留原序或按seed打乱，再截断，不按字段排序。
18. run_batch模块：当前逐条件/案例顺序运行，不提供并发调度。
19. agent_runner._loads_relaxed_json：解析JSON/Python字面量及修复final回答；一般候选文本修复另在_json_candidates。
20. project_config.load_project_config：每次读文件并按override更新进程环境，不是单例。
21. case_views：字段白名单投影与深拷贝，不涉及解密。
22. check_logs：只审计RunLog JSONL，不检查清册/manifest。
23. tool_sandbox模块与init_sandbox：使用隔离临时磁盘沙箱，不是完全内存。
24. tool_sandbox.record_tool_event：只记录审计事件，不执行工具，不含耗时字段。

## 验证与交付

- 源码验证：13文件在内存编译通过，剥离真正module/class/function docstring后执行AST与790268b及修改前快照相同；逐行补丁检查确认所有新增/删除行都位于docstring中。
- 测试命令：`python -X utf8 -B -m pytest -q -p no:cacheprovider tests/unit/test_core_runtime.py tests/unit/test_core_batch.py tests/unit/test_project_config.py tests/unit/test_paper_v1_runtime.py tests/unit/test_paper_metrics.py tests/unit/test_statistics_formal.py tests/unit/test_tool_sandbox_safety.py tests/unit/test_check_logs.py -k 'not test_frontier_api_audit_redacts_configured_credentials_and_keeps_registry_gate'`。
- 测试结果：91 passed, 1 deselected in 7.97s；退出码0。排除的一项会写入固定`config/project.local.env.frontier-test`路径，避免触碰配置目录；不是因测试失败而排除。
- 首次收集失败：ApprovalRecord.__post_init__的docstring缩进错误，已恢复方法体8空格后重新编译/AST检查与上述测试通过。未提交语法错误，详情登记failure-log。
- Git差异与隔离暂存空白检查通过；提交`6f56e06f916c704b1b3547da90fa23b72e09ea05`，父级790268b，包含13源码文件及7个本任务状态/记录增量，不包含其他任务内容。
- `git push origin 6f56e06f916c704b1b3547da90fa23b72e09ea05:refs/heads/codex/claude-review-repairs`成功；`git ls-remote origin refs/heads/codex/claude-review-repairs`核对远端6f56e06一致。原17个PDF暂存原始差异哈希保持`88e0c85ab9d266796cda65774808f483f4e4b9a85917cd0a3d2b81c5a724b2e7`。
- 验证记录作为独立收尾提交正常推送并核对；本任务不改变v3研究状态或科研结论。
- 不调用模型、不重跑实验、不创建PR；不代表全部科研代码或新v3已审查。
