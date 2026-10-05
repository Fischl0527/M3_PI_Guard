# 集中归档与文档整理

- 日期：2026-10-05；关联 F-DOC-001；状态：in_progress（内部/E盘完成，D盘工具拒绝待迁移）。
- 用户批准主项目原位、五个外围目录集中至 E:\M3_PI_Guard_archive；D盘两处为停用备份，整包迁移，不打开私钥或标签。
- 范围：docs 中七套工具包、实验统计/表图、机器状态和报告预览；相关活动路径引用；外围目录及运行环境兼容联接。
- 禁止：API/模型实验、Full Harness、历史递归重算、论文正文或原始结果改写、私钥内容读取、无关未提交改动进入提交。
- 起点：4195f1f78122a52fc8460ef101fdb826efc06842，codex/q2-empirical-study；origin 为 RedTeam_LLM_Security。
- 已有未提交实验、论文生成器、测试、模板与第三方改动保留；重叠文件仅提交本次路径变更。

## 步骤和验收

1. 核对迁移源/目标、计数与冲突，移动仓库内文件并更新活动引用。
2. 定向测试路径、表图/论文构建器；临时输出不覆盖主稿。
3. 归档 E盘历史项目、审阅包、运行环境；保留 runtime 旧路径联接。
4. D盘跨盘迁移确认文件数量/大小/结构后清除源目录，停用工具不执行。
5. 目录指南、迁移报告、Harness状态、范围化Git提交及推送。

仅采用必要文件系统和定向检查，不生成哈希包。发生占用或冲突记录并停止对应项。

## 验证记录

- 内部：24迁移根/368文件，数量和大小匹配；Git368个R100内容不变。
- 定向pytest：test_documentation_artifact_paths、lean_empirical_tables/figures、incremental_tables/figures、build_lean_paper_manuscript、manuscript_workspace：30 passed；完整命令在docs报告。
- 受影响源/测试Ruff通过；Git diff --check/cached --check通过。
- 4195f1f已提交LaTeX构建器仅叠加目录修改，在harness/tmp临时构建成功，五PDF图到位，临时目录清理，主稿/模板不改。
- E盘原项目、E17_reviews、runtime迁移完成；旧runtime建立Junction；旧仓库HEAD75285ec保留。
- PromptGuard Python3.13.5、numpy2.1.3、transformers4.57.6导入成功；bootstrap3.13.5启动成功；CaMeL原基础Python路径缺失，未修。
- D盘命令被工具策略拒绝，未启动，两个源仍在、两个目标不存在；不换工具绕过拒绝。
- 初始较宽测试25 passed/7 failed：本次路径遗漏已修，另4个论文章节缺失/2个参考文献历史漂移不在整理范围；后续迁移相关30全通过。
- cd90bb3推送成功；第二提交为指南/报告/Harness收口。F-DOC-001仍in_progress，未宣称全计划完成。
- 收口：19源文件内存编译通过、118本地文档链接0断链、feature JSON有效；旧dirty源码/稿件/模板/第三方状态保留。
