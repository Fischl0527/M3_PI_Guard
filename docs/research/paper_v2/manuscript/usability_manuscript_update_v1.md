# 论文更新与版式复核报告

日期：2026-09-05。状态：本次文稿更新完成；项目与投稿准备仍为 `in_progress`。
本次只使用已完成结果，没有新 API 调用、实验重跑、Full Harness 或历史递归验证。

## 1. 已更新的内容

| 位置 | 更新 | 解释边界 |
|---|---|---|
| Methods 3.17 | P0 未完成状态分区、512 个确定性探针、E7a 96 个官方模型提案与 384 个配对确认单元 | 观察性诊断、组件探针和模型提案不能混为同一种证据。 |
| Results 4.13、表 7 | 授权粒度、确认状态与执行许可结果 | 表内只统计提案获许可；没有 effect backend 提交，不是 TCR 或真实 unsafe effect。 |
| E2 Methods / Discussion / Conclusion | 合成场景和零执行原因的适用边界 | 30/30 是场景域标签，不是原生 AgentDojo 运行；历史缺少逐提案 reason，不能把每个零执行都归因于 ASK/DENY。 |
| Related Work | 新增 PIArena、AgentDyn、ASPI | PIArena 为 ACL 2026 论文；另两篇为预印本。只使用已核验的摘要级主张。 |
| Discussion / Conclusion | 许可与实际效果分开，增加原生动态验证未完成的限制 | E8 无模型结果；不增加鲁棒性、TCR、跨厂商或人体确认工作流证据。 |
| 中文对照 | 同步方法、结果、表 7、三项引用及上述限制 | 中文仍为审阅用 Markdown，本轮不生成 Word。 |

旧 E1--E6 原始记录、统计数值、5 幅图和 12 张补充表未改写。
E6-v2 仍为闭合的单执行块；Gemini 仍为 diagnostic / not estimable，
不恢复跨日期或跨厂商重复性主张。

## 2. 新结果如何写入论文

E7a 的严格 exact 对照刻意只接纳第一种合法措辞，而原请求允许两种并偏好第二种。
bounded enum 接纳两种原已授权措辞，因此比较的是过度约束策略与有界策略，
不是正确策略编译器之间的优劣。

| 模块与授权 | 良性合法提案获许可 | 攻击条件下合法提案获许可 | 非授权提案获许可 |
|---|---:|---:|---:|
| strict exact / policy | 0/12 | 0/12 | 0/12 |
| strict exact / full | 0/12 | 0/12 | 0/12 |
| bounded enum / policy | 12/12 | 12/12 | 0/12 |
| bounded enum / full | 12/12 | 12/12 | 0/12 |

此表只使用 trusted-approved 通道。0/12 的 Wilson 95% CI 为 0--24.25%，
12/12 为 75.75--100%。攻击没有诱发非授权目标提案，不能把零非授权许可写成
攻击抵抗能力。两个模块未显示差异。384 个确认单元共享 96 个模型提案，
不是 384 次独立模型执行。

表 7 从已有 `analysis_v1.json` 直接导出；生成器要求显式
`permission_eligibility_only_no_backend_state_transition`，否则拒绝构建。
原始字段名保留，但论文将其解释为合法/非授权提案获许可，未伪造后端收据。

## 3. 排版和验证

| 产物 | 页数 | PDF 大纲 | 核验结果 |
|---|---:|---:|---|
| `LaTeX通用模板/数模通用模板.pdf` | 52 | 65 | A4、模板四边 25 mm；Times New Roman 正文/标题/行内标识；数学符号保留 CMSY；底部页码正向居中。 |
| `LaTeX通用模板/M3_PI_Guard_template_review.pdf` | 52 | 65 | 兼容入口；逐页文本和大纲与母版一致。 |
| `LaTeX通用模板/M3_PI_Guard_JISA/M3_PI_Guard_JISA.pdf` | 59 | 64 | 保留 elsarticle 投稿样式及其默认字体/纸张；本轮不将其混改成数模模板。 |
| `LaTeX通用模板/M3_PI_Guard_JISA/M3_PI_Guard_JISA_supplement.pdf` | 12 | 本轮未重排 | 内容未改，页数、无旋转及作者元数据保持正常。 |

审阅稿和正式主稿均无空页、整页旋转、页面外文字、缺字、未解析引用或 Overfull。
作者元数据为空。9 个字面 `input` 均可解析，TeXstudio 能读取全文结构。
宽表沿用只旋转表体的设计，不旋转纸张和页码；新增四列表 7 正向排版。

首轮发现表 7 表注拆页，已仅将该短表改为表题/表体/表注整体浮动。
最终检查覆盖两主稿全部 111 页的缩略图，并放大复核新方法、结果、表 7 与限制页。
审阅稿物理第 40 页的表 7 与全部表注在同一页，无重叠或裁切。

最终定向检查：

```powershell
# 仓库根目录 E:\M3_PI_Guard_test
& 'F:\robot\Anaconda3\python.exe' -X utf8 -m pytest -q tests/unit/test_build_lean_paper_manuscript.py tests/unit/test_build_jisa_latex.py
& 'F:\robot\Anaconda3\python.exe' -X utf8 -m ruff check scripts/build_lean_paper_manuscript.py scripts/build_jisa_latex.py scripts/check_jisa_pdf_layout.py tests/unit/test_build_lean_paper_manuscript.py tests/unit/test_build_jisa_latex.py
& 'F:\robot\Anaconda3\python.exe' -X utf8 -m py_compile scripts/build_lean_paper_manuscript.py scripts/build_jisa_latex.py scripts/check_jisa_pdf_layout.py
& 'F:\robot\Anaconda3\python.exe' -X utf8 scripts/check_jisa_pdf_layout.py
```

- pytest：17 passed；Ruff、py_compile：通过。
- XeLaTeX/BibTeX 三个受影响入口构建完成。各入口在所在目录执行
  `latexmk -xelatex -bibtex -interaction=nonstopmode -halt-on-error -file-line-error <入口.tex>`；
  TeX Live 路径只加入当前 PowerShell 进程，没有修改永久环境变量。
- 两主稿 `layout_check.json` 均为 `errors=[]`。
- 24 个实际引用全部渲染；39 项候选库中 15 项未引用、不打印。
- 源文件保留 6 个正文章节、5 图、7 主表和 12 补充表。

保留的非致命提示：审阅稿 3 个、正式主稿 4 个 Underfull 段落提示，视觉检查无
越界/重叠；BibTeX 的 L20 缺少 pages 属于既有未核实元数据，不凭空补造页码。
本轮不是重新核验全库引用，也不是投稿日期的 JCR 核验。

## 4. outputs 目录与论文文件的区别

```text
E:\M3_PI_Guard_test\outputs\
├── experiments\
│   ├── incremental_empirical_v1\          # 既有 E1--E5，未重跑或改写
│   ├── e6_cross_provider_calibration_v2\   # 闭合 E6-v2 B1，不恢复
│   ├── authorization_usability_v1\        # P0/P2 诊断，本轮只读结果
│   ├── e7_confirmation_usability_v1\       # 96 提案/384 确认单元
│   │   └── analysis_v1.json                # 表 7 的唯一数值输入
│   └── agentdyn_native_qualification_v1\   # 加载/fixture 检查，非模型实验
└── document_qa\
    └── usability_paper_update_v1\
        ├── layout_check.json              # 两主稿一次文档 QA 汇总
        ├── review_contact_1..3.png         # 审阅稿全部页的缩略图
        ├── official_contact_1..3.png       # elsarticle 全部页的缩略图
        ├── review_page_*.png               # 新增/修改关键页放大图
        └── official_page_*.png             # 投稿样式对应关键页
```

`document_qa` 只是本地排版检查缓存，不是新增实验或证据链层级。
原始实验结果没有复制进 QA 目录；不生成请求/历史哈希包。
PDF 和可编辑 LaTeX 在 `LaTeX通用模板/`，规范英文及中文 Markdown 源在
`docs/research/paper_v2/manuscript/`。旧 Word 文件仅为历史版本，未同步此次修订。

## 5. 交付状态

本次采取局部内容整合，没有重写既有实验叙事：英文合并源（含表等）从约
14,669 词增至 15,908 词，增加约 1,239 词（8.4%）。作者信息继续留空。
本次文稿更新可交付，不代表完成 E7 端到端效用、E8 原生模型评估或正式投稿准备。
后续如继续实验，应先解决真实的隔离后端提交与独立判分契约，再报告任务完成率。

Git 目标为 `origin/codex/q2-empirical-study`，远程为
`https://github.com/Fischl0527/RedTeam_LLM_Security.git`。
本次仅提交相关源码、公开论文与简洁状态；不提交内部 trace、密钥、QA PNG 缓存、
用户未跟踪的模板字体/原始资产或无关子模块改动。确切提交号见交付消息与 Git 历史。
