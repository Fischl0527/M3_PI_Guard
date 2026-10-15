# 文件命名与长路径整理

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
