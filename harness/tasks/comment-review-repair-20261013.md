# 中文注释审查、勘误与限定 Git 交付

- 用户授权：抽查 Gemini 中文注释；确认问题后仅修正注释并提交、推送 GitHub。
- 审查基准：`c5cc2cd8a2f667febb992260a64a4b44c8d57a10`。当前提交父级为强化实验功能提交 `155e0ccd632eb45eadb78c2da3051c6d33efe2ea`；不回退或重新实现该功能。
- 功能：F-DOC-007，in_progress。
- 允许范围：五个文件的六处已确认注释错误、其余剥离文档字符串后 AST 与当前 HEAD 一致的已跟踪 Python 注释改动，以及本任务记录和必要 Harness 状态增量。
- 排除范围：当前七个包含非注释工作区变更的 Python 文件、未跟踪代码、论文及 PDF、实验输出、子模块和其他任务的 Harness 改动；既有17个PDF暂存原样保留。
- 计划：核对六处真实行为；修正文档字符串；全批次执行 AST 对比和 Git 空白检查；运行离线定向测试；隔离暂存仅提交选定内容；推送当前 origin 分支并核对远端提交。
- 修正：过度授权率；规则缺失返回 ASK；沙箱内临时文件写入；JSONL 原子覆盖；run_case 参数、5步默认值和日志列表返回值；逗号配置值拆分。
- 验收：五个修复文件的执行 AST 不变；本次提交全部 Python 文件仅含注释/文档字符串变化；定向离线测试通过；原暂存和无关工作区变更保留；远端分支指向本次提交。
- 定向测试：`python -X utf8 -B -m pytest -q -p no:cacheprovider tests/unit/test_paper_metrics.py tests/unit/test_guard_engine.py tests/unit/test_correctness_runtime_v1.py tests/unit/test_tool_sandbox_safety.py tests/unit/test_portable_verify.py`，64 passed in 32.57s。
- 静态验证：365个已跟踪Python文件剥离真正module/class/function docstring后与155e0cc执行AST一致，全部可在内存编译；五个勘误文件与修复前执行AST一致。
- 格式检查：首次`git diff --check HEAD -- <365个显式路径>`发现19处新增docstring尾随空格；只清理这些docstring空白，等待复核。自动补丁首次因hunk头格式不兼容失败，改用工具支持的裸`@@`后应用成功。
- 当前排除源码：`empirical_reinforcement_analysis_v1.py`、`build_jisa_latex.py`、`build_lean_paper_manuscript.py`、`current_evidence_tables.py`及三个相关分析/构建测试，不混入本次注释提交。
- Git交付：目标`origin/codex/claude-review-repairs`，已核对GitHub仓库`Fischl0527/M3_PI_Guard`及远端155e0cc；隔离暂存只提交注释和本任务状态增量，提交/推送待执行。未调用模型、未重跑实验、未修改认证授权逻辑。
