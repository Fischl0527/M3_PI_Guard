# 当前论文证据复核与集中局限修订

日期：2026-10-12。状态：verified（本任务，未Git交付）。对应功能：F-PAPER-003；论文整体 F-PAPER-002 仍in_progress。

## 目标与范围

按用户要求复核当前论文的实验论据和证据缺口，使用 nature-statistics、nature-polishing，将重复防御性表达集中到 Discussion 的一个 Limitations 小节。同步当前英文、中文参考稿及现有 LaTeX入口，不新增科研主张。

允许：当前论文源章节、构建/表注的必要修订及定向测试、报告和既有 Harness 状态。禁止：修改原始记录、历史统计/冻结计划、科研运行语义、密钥、用户资料及原有 Git 暂存；不启动 API、实验、Full Harness、历史递归验证、提交或推送。

## 分析和风险

- 授权900条、校准480条和合成16条已由只读 Reviewer 对公开原始结果进行一次计数/唯一性/缓存对照。
- 校准120案例严格嵌套授权180案例；授权180案例对应153底层任务。执行分配数不等于独立样本数。
- 校准缺2份投影收据、4份结构化安全收据及4份结局；必须保留未知，不由摘要补造或重标安全零。
- 当前可支持授权语义、效用代价和有界组件行为；不能据此增强机制领先、普遍安全有效或跨厂商主张。
- 现有测试有若干固定免责声明/词数下限，修订为结构、数据、范围与必要限定的语义检查，不为通过而删除负例。
- 维护仓库地址已变为 Fischl0527/M3_PI_Guard，公开发布/DOI仍未完成。

## 执行计划

1. 只读核对关键主张、计划/raw/缓存/主表图/当前版本，列出必要剩余事项。
2. 修正RQ1比较对象、队列嵌套及独立单位说明，保留原统计和显著性家族。
3. 将重复结论边界合并到一个局限小节；方法保留定义、结果保留负面数据与缺失计数。同步英文及中文。
4. 用现有 current 构建入口更新稿件与LaTeX，运行受影响测试/引用/数字/排版检查，不重算科研结果。
5. 写单一Markdown复核报告，更新feature/progress/history/handoff，明确投稿未完成事项。

## 验收

- 关键论据有可定位的当前源记录与缓存，真实缺口明确而非伪造完整链。
- RQ1不暗示存在旧匹配器的同期cell；180/153及120严格嵌套明确。
- 一个集中局限小节，无重复整套免责声明；CI跨零、效用下降、失败未知仍清楚可见。
- 四图四表、统计数值/区间/引文键/作者留白/原始科研数据保持；当前双语与LaTeX一致。
- 定向检查通过，原有用户改动/暂存保留；论文整体仍in_progress。

## 执行与验证记录

### 实施

- 公开结果与现有统计缓存只读核对；修比较对象、样本/嵌套、方法前缀及仓库URL，按统计与润色技能集中双语局限，历史结果不改义。
- 构建器真实BUG：英文弯撇号混入宋体；先加 `_inline` 弯引号回归并确认失败，再修 `scripts/build_jisa_latex.py` 的Markdown保护后标点转换，不调整字体检查或科研运行语义。
- 英文正文8256→6132词；当前中英各24相同引文键、4图4表；作者仍留空。

### 实际验证命令与结果

在 `E:\M3_PI_Guard_test` 执行，Python为 `F:\robot\Anaconda3\python.exe`。

```powershell
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m pytest tests/unit/test_build_lean_paper_manuscript.py tests/unit/test_current_evidence_tables.py tests/unit/test_build_jisa_latex.py tests/unit/test_generic_policy_corrected_v2.py tests/unit/test_correctness_effects_v1.py tests/unit/test_correctness_runtime_v1.py tests/unit/test_provenance_corrected_v1.py tests/unit/test_corrected_v1_policy.py tests/unit/test_correctness_analysis_v1.py tests/unit/test_research_followup_calibration_v1.py tests/unit/test_trusted_intent_review_v1.py -q -p no:cacheprovider
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m ruff check scripts/build_lean_paper_manuscript.py scripts/current_evidence_tables.py scripts/build_jisa_latex.py tests/unit/test_build_lean_paper_manuscript.py tests/unit/test_build_jisa_latex.py
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m py_compile scripts/build_lean_paper_manuscript.py scripts/current_evidence_tables.py scripts/build_jisa_latex.py
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m scripts.build_lean_paper_manuscript --profile current --sync-chinese-tables
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -m scripts.build_jisa_latex --main-markdown manuscript_current_v2.md
$texBin = 'D:\TeXLive\texlive\2026\bin\windows'
$env:Path = "$texBin;$env:Path"
& "$texBin\latexmk.exe" -xelatex -bibtex -interaction=nonstopmode -halt-on-error -file-line-error -cd 'E:\M3_PI_Guard_test\LaTeX通用模板\M3_PI_Guard_JISA\M3_PI_Guard_JISA.tex'
& "$texBin\latexmk.exe" -xelatex -bibtex -interaction=nonstopmode -halt-on-error -file-line-error -cd 'E:\M3_PI_Guard_test\LaTeX通用模板\数模通用模板.tex'
& 'F:\robot\Anaconda3\python.exe' -X utf8 -B -c "from pathlib import Path; from scripts import check_jisa_pdf_layout as q; q.OUTPUT=Path('outputs/manuscript/previews/paper_evidence_review_20261012'); q.main()"
```

- pytest：186通过、1第三方Pydantic弃用警告、51.54秒；Ruff全部通过；py_compile退出0。
- current构建：body_words6132、总计8043、sections6；LaTeX生成和两个latexmk退出0。
- PDF检查：正式23页39导航、模板30页40导航；A4竖版/作者空/Times字体/页码/边界/引用PASS。3/1个Underfull提示仍保留，视觉无问题；所有页面联系图及主表/局限关键页已实际查看。
- Nature `check_consistency.py` 实际退出0，机械整数/百分比/标题编号精度提示人工分类，不更改真实数字消警告；不当作独立文献/统计重算。
- 原有17暂存、raw/计划/缓存无本轮修改，必要状态JSON/范围diff/文档链接由最后收尾核对；没有Git提交推送PR。
- 最终收尾：当前双语逐字等于生成器输出；24活动引文键均解析、集合相同；45本地链接及代码围栏通过；feature/claim台账JSON解析通过，F-PAPER-002仍in_progress。明确路径`git diff --check`退出0；`git diff --name-only -- outputs/experiments/claude_revision_v1 outputs/experiments/research_followup_20261006_v1 protocols`为空；起始与最终17条cached name-status逐字相同。

### 剩余与移交

报告包含30任务精度、已修BUG、历史角色、4未知及缺2/4收据、输出目录结构。没有新科研运行缺陷被公开脱敏摘要充分证明，未猜测修补H-059/H-065/V-005。整体论文待作者确认、真正外部方法审阅、数据代码归档及投稿期刊资格核验；不自动扩样或调用API。
