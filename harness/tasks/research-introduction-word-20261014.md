# M3 PI Guard 研究介绍 Word 与完整实验图集

日期：2026-10-14。状态：verified。Feature：F-DOC-009。

## 用户目标与范围

制作放在 docs 的研究介绍 Word，所有文字使用纯黑色；配套科研图放在 docs/picture。追加要求覆盖权限编译 corrected_v1、corrected_v2、corrected_v3、corrected_v4，并包含之前的实验图表。采用机制、证据、发现、演进的介绍主线，集中解释关键研究边界，避免重复防御性语言。

允许：新增本次 DOCX、图表及历史图表副本，必要的 Harness 任务、脚本、临时渲染与状态记录。禁止：修改产品代码、权限逻辑、实验 raw、既有统计、论文、原图、用户改动及 Git 暂存；不调用模型、不运行新研究、不提交或推送。

## 分析与计划

1. 核对最新论文主证据、强化实证和 v3/v4 开发报告，以及四版编译器源码。版本号指 corrected 编译链，不与模型服务版本混用。
2. 建立图表目录：收集实际实验和论文研究图，排除测试夹具、渲染预览及碰撞审计覆盖图；历史、诊断、停用材料分别标识，保持原文件内容。
3. 使用已保存的 Python 绘图偏好生成介绍图、分组条形图、组成图和版本比较图；读取已有 JSON/CSV，不重新运行推断或模型。
4. 使用 Codex bundled Node/docx 生成中文研究报告，正文和图注纯黑；当前与历史图表嵌入，附完整图表来源索引。
5. 使用现有便携 LibreOffice 和 bundled renderer 实际转换、逐页检查；验证 DOCX/XML 字体颜色、嵌图、数据、目录、源文件保持及最终图片。

## 图表合同

- 目的：解释动作如何受控、授权信息如何影响效用、机制与自然提案差异、v3/v4 当前可用性。
- 数据：当前论文900/480/16与60复核；强化实验2165执行、320受控判定、358首提案回放；v3开发44响应与v4开发32任务。各队列分别报告。
- 分母：底层任务、任务条件执行、模型请求、受控判定不得混同；旧版评价端点保留历史含义；未知不补零。
- 视觉：新图中文标签纯黑，白底，克制配色；比较类别采用条形图，不制造时间连续趋势；组成图仅用于互斥部分。
- 输出：PNG用于Word及直接阅读，SVG/PDF用于缩放；自动对齐、字号、碰撞检查后人工检查。既有历史图作为原样副本，不能把复制称作重新科学验收。

## 验收标准

- DOCX和图片在用户指定目录真实存在且可打开。
- Word覆盖研究问题、流程、机制、v1至v4演进、主要结果、最新进展及讨论问题，少用重复限制类语言。
- 正文、标题、表格、页眉页脚与图注均显式000000；新图所有文字为黑色。
- 新图数字与当前源记录一致，图注交代分母和解释；历史图集有来源和阶段标识。
- DOCX实际渲染并检查所有页；未解决问题如实记录。

## 执行与验证

环境：现有便携 LibreOffice 已定位；bundled Node/docx和Python/docx可用；绘图使用现有Python/matplotlib，不新增项目依赖。


## 最终验证与交付

- 研究介绍 Word 已生成并实际渲染为57页A4；前15页研究正文，随后来源/导航及完整索引、历史图集。覆盖corrected_v1—v4、900/480/16主证据、2165强化执行、320受控判定、358首提案与最新v3/v4开发。
- 新绘15幅300dpi PNG及SVG/PDF；157组既有图317源文件原样复制，136幅不同图像入册。7张报告页面预览移出本任务图集，源文件保留。
- Word894处文字颜色均为000000；实际PDF全部文字纯黑、无文字越界、无空白页，151幅嵌图可读。全部页面联系图及重点正文原尺寸检查通过。
- 15图字号检查通过、碰撞0 FAIL；6个环图内孔文字WARN已逐图复核。源码19 PASS/0 FAIL，PNG与300dpi两个格式提示符合本任务；限定辅助脚本Ruff/编译通过。
- 7个选定科研来源及317原图/副本哈希保持，原Git暂存diff不变。0模型API/新实验/统计重跑/产品代码/权限/论文/Git交付。F-DOC-009 verified仅限文档图集，其他科研feature状态不变。
- Word：docs/M3_PI_Guard_研究介绍_2026-10-14.docx；完整图片与目录：docs/picture/。任务：harness/tasks/research-introduction-word-20261014.md。

### 实际命令

```powershell
python -X utf8 harness/scripts/prepare_research_introduction_20261014.py
python -X utf8 harness/scripts/plot_research_introduction_20261014.py
& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' harness/scripts/build_research_introduction_20261014.mjs
& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 harness/scripts/verify_research_introduction_20261014.py
python -X utf8 harness/scripts/audit_research_introduction_figures_20261014.py
$env:PATH = 'C:/Users/gaohang/.cache/codex-tools/libreoffice-26.2.4/portable/program;' + $env:PATH
& 'C:/Users/gaohang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 'C:/Users/gaohang/.codex/plugins/cache/openai-primary-runtime/documents/26.1013.11914/skills/documents/render_docx.py' 'E:/M3_PI_Guard_test/harness/workspaces/research-introduction-20261014/research_introduction_render.docx' --output_dir 'E:/M3_PI_Guard_test/harness/workspaces/research-introduction-20261014/rendered-release' --emit_pdf --width 1200 --height 1600
python -X utf8 harness/scripts/review_research_introduction_pdf_20261014.py
```

产品单元/集成测试、Full Harness与论文构建不运行：本轮仅文档与配图，以上构建/渲染/源码/颜色/数据/来源检查是相关验证。一般架构未改变，不新增架构决策。

- 最终图片目录332个本地链接全部存在；包含空格的图片名用尖括号包裹，Word正文与图像不变。
