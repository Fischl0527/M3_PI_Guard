# 文件命名与长路径整理

## 后续全量复测（2026-10-15，测试通过；追加清理受阻）

- 用户批准F-FILE-001：路径全查、至少10MiB文件完整读取和格式验证、两个分支全树Git检出、中文深目录复制解压、同包Windows/Ubuntu24离线运行及改名兼容。
- 本次不另建Markdown或Word报告；测试日志outputs/maintenance/file_retest/，完成后对话汇报，现有Harness保留状态与命令。
- 写入中的文件、9份历史私有长路径及子模块单列；不读凭据、不改原始记录、不运行API或Full Harness。只提交本轮改动，保留原17PDF暂存及其他任务。
- 实际命令：`python -X utf8 -B harness/tmp/retest_large_files.py inventory|contents|copies|checkouts|default_checkout|binary_formats`各阶段分别执行；临时脚本不属于产品运行器，日志记录实际参数。前一checkouts误用了3c329239本地旧分支，default_checkout明确钉住远端8f436942，不覆盖旧失败。
- `python -X utf8 -B harness/tmp/retest_portability.py`：现有构建器加本轮路径/批次测试，最终同包在Windows/Ubuntu24各140通过，演示、180编译重现及900/16/480原始计数核对均通过；未重算推断统计。
- 实际82大文件2.55GB及239格式/读取、11其他格式通过；82中文目录复制逐字节一致；1040目标/156别名完整；开发4049/默认3943完整检出逐Git对象一致。包解压37075文件/上传72173903字节均逐字节一致。
- 预算扫描仍6891条超过240，其中9条达到260；不把历史例外当命名合规。8历史gitlink与缺.gitmodules不等同独立运行包失败。工具拒绝本轮副本清理，未绕过，副本忽略Git；原始82源文件大小/时间保持，原暂存逐字保持。
- 后续用户明确要求汇报后删除测试内容并保护重要文件：已逐项核实7个本轮生成目录、位置正确且无链接。静态`Remove-Item -LiteralPath 'E:\M3_PI_Guard_test\outputs\maintenance\file_retest\中文 空格复制' -Recurse -Force`仍在进程创建前被工具拒绝，未实际执行；不换工具绕过。追加清理未完成，F-FILE-001 blocked；正式tests/、源码、原始数据、交付包和必要日志均保留。

- 日期：2026-10-15；状态：verified（限定命名/迁移验收，历史例外保留）。
- 用户要求：自行处理过长名称，并把长度限制写入Harness；名称应可读，不使用难懂缩写。

## 范围与方案

1. 新增统一长度检查：新文件名不超过80个UTF-16单位、单级目录不超过64、仓库相对路径不超过180、实际绝对路径不超过240。保留完整语义，先去重复，再减少层级，不截断成不透明编号。
2. 修复矩阵生成器重复拼接条件名的行为；恢复已有实验时继续认已有记录，不重新调用模型。
3. 对完成批次的重复输出名及旧测试/分片临时目录逐项预检；无冲突才迁移，保留文件内容。冻结输入、原始模型结果、私有官方回执及已有暂存不改写；不能安全迁移的项明确列出。
4. 更新实际读取入口以识别迁移后的名称；提供普通迁移记录和中文说明，不生成哈希包。
5. 更新Harness规则与状态；只运行相关定向测试、Ruff及内存编译，不运行Full Harness、API或历史统计。

## 禁止事项

- 不删除结果、不合并冲突文件、不读取密钥，不移动第三方源码和当前论文/参考文献的既有改动。
- 不把历史工作项编号、结果内容或冻结输入改成新研究身份。
- 不处理仓库外其他目录，不启动或终止其他任务进程。

## 验收

- 截图所示重复CSV名称有可读短名称，读取入口及已有记录对应不丢失。
- 新生成路径检查可在写入前报出明确错误；不靠系统长路径开关绕过命名规则。
- 原始结果内容不变、迁移无覆盖；剩余历史例外如实说明。
- 定向测试通过，更新progress、feature list、task history、session handoff。

## 实施与验证结果

- 实际1040项改名/归档，未删除或覆盖；旧7913条260字符路径降为9份历史私有官方记录。七工具包外层与302跟踪文件保持内容；详情见docs/路径整理与可迁移验证.md。
- 定向命令：`python -X utf8 -B -m pytest tests/unit/test_artifact_paths.py tests/unit/test_core_batch.py tests/unit/test_run_program.py tests/unit/test_documentation_artifact_paths.py::test_analysis_and_figure_defaults_point_outside_docs tests/unit/test_documentation_artifact_paths.py::test_historical_public_toolkits_remain_separate tests/unit/test_documentation_artifact_paths.py::test_saved_manuscript_figures_resolve_after_move -q --basetemp outputs/maintenance/path_names/verified_tests`；36通过，8.99秒。
- 使用已有可移植构建器的静态源码闭包/公开复制函数；默认构建入口显式加入路径检查脚本，闭包随之包含新模块。同一最终包Windows和Ubuntu24各21测试通过。未安装新运行依赖。
- Windows以隔离Git索引、core.longpaths=false实际检出当前与默认分支的302文件，最长243/247字符。用户17项暂存未消费；默认分支8f436942只改路径，已推并核对。
- 首次测试夹具上级不存在已修；既有文档编辑器JSON失败及四条既有Ruff告警单独记录，不改算法或测试来制造全绿。
