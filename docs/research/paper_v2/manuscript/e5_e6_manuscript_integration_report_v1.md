# E5/E6 论文证据整合阶段报告

日期：2026-09-04
状态：科学内容整合与审阅件复核完成；作者与机构准入仍待完成

## 1. 本阶段完成内容

本阶段没有启动新实验，也没有调用 DeepSeek、Gemini 或其他 provider。工作只使用
已经封存、并按各自推断边界使用的紧凑分析结果，将 E5 与 E6 补入英文稿、中文对照稿、图表、补充材料
和 active claim ledger。

- E5：12 个预算 200 时仍未成功的任务继续观察到预算 500，共 3,600 个最新查询键；
  预算 201--500 内新增 unsafe effect 为 `0/12`，Wilson 95% CI 为
  `0.00%--24.25%`。该结果仅描述条件性尾部，不构成完整原始 40 任务 B500 曲线，
  也不能证明攻击饱和或风险为零。
- E6 DeepSeek：风险富集单执行块共 360 个 response-bearing 逻辑项。六条件 unsafe
  effect 分别为 no-defense `17/60`、source-pinned VIGIL `16/60`、policy/normal
  `2/60`、policy/safe `1/60`、full/normal `0/60`、full/safe `0/60`。该设计不含良性
  任务，不增加 TCR 证据，也不支持部署流行率或跨日期重复性主张。E6 是另行执行，
  但不是独立样本复现：`47/60` 个任务同时是 E3 锚点。单块中观察到攻击活性，
  但不满足也不检验原三窗口设计的活性门。
- E6 Gemini：5 条 response-bearing、1 条 response-less VIGIL fatal、174 条行政
  closure；最小 response-complete 嵌套成对覆盖为 `0/30`，其中 `29/30` 个任务同时
  是 E3 锚点。E6-v2 从设计上只把 Gemini 用作诊断；所有 Gemini 配对、因子和跨
  provider 效应均标为 `NE`。
- E2 分母更正：480 次离线 Guard 决策由 240 个未授权提案和 240 个授权提案组成；
  false allow 为 `0/240`，false block 为 `30/240`。
- E6 统计实现使用双侧 exact McNemar 检验，并同时报告 Newcombe 配对区间、按任务
  聚类且按基准分层的 bootstrap 区间和 Holm 校正。该实现替代了计划中的 cluster
  sign-flip 检验，已作为分析方法偏离在中英文稿与补充表 S12 中透明披露。

## 2. 交付物

当前可编辑审阅件位于 `E:\M3_PI_Guard_test\docs\research\paper_v2\manuscript\`：

- `M3_PI_Guard_JISA_working_draft.docx`：英文主稿，作者信息留空；
- `M3_PI_Guard_JISA_chinese_comparison.docx`：中文内部对照稿，不作为 JISA 上传稿；
- `M3_PI_Guard_JISA_supplementary_tables.docx`：十二张补充表；
- `M3_PI_Guard_JISA_highlights.docx`：五条不超过 85 字符的投稿 Highlights；
- `M3_PI_Guard_JISA_cover_letter.docx`：一页式投稿 Cover Letter，作者字段留空；
- `manuscript_deepseek_v1.md`、`manuscript_zh_v1.md`、
  `supplementary_tables_v1.md`：上述 Word 文件的可审计文本源；
- `claim_evidence_ledger_lean_v1.json`：E1--E6 当前 claim--evidence 边界；
- `submission_package_index_v1.md`：投稿文件、图件和作者待办的单一索引。

## 3. outputs 目录的证据结构

`E:\M3_PI_Guard_test\outputs\` 是实验执行与分析证据区，不是投稿稿件目录。本阶段只读
使用其中两组已经闭合的结果：

```text
outputs/
└── experiments/
    ├── incremental_empirical_v1/
    │   ├── factorial/            # E1 同期 2×2 因子实验
    │   ├── provenance/           # E2 端到端来源权威实验
    │   ├── provenance-replay/    # E2 无 API 的确定性 Guard 回放
    │   ├── challenge/            # E3 outcome-enriched 风险挑战集
    │   ├── flash/                # E4 DeepSeek Flash 因子复现
    │   └── adaptive-tail/        # E5 B200-survivor→B500 条件尾部
    └── e6_cross_provider_calibration_v2/
        ├── deepseek_pro/         # E6 DeepSeek B1 原始记录与门禁
        ├── gemini_flash/         # E6 Gemini 失败前缀与行政闭合
        ├── analysis_v2.json      # E6 一次性诊断分析结果
        ├── tables/               # E6 公开统计表
        ├── figures/              # E6 公开诊断图
        └── report_v2.md          # E6 技术结项报告
```

论文使用的六张主表和五幅主图位于
`docs/research/paper_v2/incremental_empirical_v1/`。这样区分了“执行/分析证据”和
“投稿表达产物”，避免把 provider 内部 trace、密钥配置或运行中间件带入稿件。

## 4. 构建与复核结果

- 英文 Markdown 构建：14,669 words、六个科学章节；
- 英文 Word：349 paragraphs、7 个 Word 表格（六张编号主表加一张内嵌决策表）、
  5 幅图；
- 中文 Word：290 paragraphs、7 表、5 图；
- 补充材料：12 表；
- 中英文数值 parity 检查通过；
- 定向 pytest：审计后首轮 `25 passed / 1 failed`，唯一失败是跨行文本断言；修正
  断言后只重跑该失败节点并得到 `1 passed`，因此当前 26 个定向节点均有通过证据；
- Highlights/Cover Letter 同步后，受影响测试首轮 `31 passed / 3 failed`；三项均为
  测试契约问题（一个措辞断言、两个已过时的历史稿件/哈希假设），修正后只重跑
  失败节点并得到 `3 passed`。Ruff 和 `py_compile` 通过；
- 英文、中文、补充材料及两个小型投稿附件的构建入口均成功。
- 五份 DOCX 可访问性审计均为 `0 high / 0 medium`；英文与中文稿各有 21 条参考文献
  以裸 URL 显示的 low 级提示，其余三份为 0 low。两份主稿各含 5 个 inline 图，
  没有浮动图对象。
- DOCX 元数据复核：英文、中文、补充材料、Highlights 和 Cover Letter 的内部题名
  与当前内容一致；作者与
  `lastModifiedBy` 保持空白；自定义属性不包含项目绝对路径。

本机没有 LibreOffice `soffice`，因此打包渲染器无法启动。随后使用仓库已有的 WPS
只读临时副本流程完成逐页复核：英文 `35/35` 页、中文 `30/30` 页、补充材料 `4/4`
页、Highlights `1/1` 页、Cover Letter `1/1` 页。未发现文字或表格截断、对象重叠、
缺图或页码异常；英文原第 14 页孤立表头已移至第 15 页并与首行同页。补充材料 S10
正常跨页并重复表头，最后一行单独位于第 4 页，属于非阻断排版瑕疵。临时渲染结果
留在系统临时目录，没有加入仓库。

独立只读核心稿审查最初指出五项高优先级问题：E6 活性门表述、Gemini 推断资格、
E3/E6 样本重叠、S12 检验说明和 DOCX 内部标题。随后投稿包审查又发现 Highlights/
Cover Letter 的 Word 附件滞后于文本源，以及英文稿一处孤立表头。上述问题均按最小
修改原则修正，并重新完成对应附件的逐页复核；没有改变冻结实验记录、重新执行任何
样本或删除不利结果。

## 5. 当前论文判断与剩余工作

从实验覆盖角度，E1--E6 已足以支撑一篇“授权制度、运行时配置与证据边界”的实证稿，
目前不需要为了堆数量再启动低价值矩阵。稿件应继续保留以下限制：不宣称 first、only
或 SOTA；不宣称 Gemini 跨厂商复现；不把 E6 解释为时间重复性；不把 E5 解释为攻击
饱和；不把来源机制的确定性回放正确率等同于端到端安全增益。

仍需由作者或机构完成：

1. 填写作者顺序、单位、通讯作者、ORCID、CRediT、基金、利益冲突和致谢；
2. 人工压缩与润色英文稿，重点控制 14,669-word 工作稿的篇幅和重复解释；
3. 作者侧相似性/自我抄袭检查，并确认所有作者同意最终文本；
4. 补齐代码/数据公开版本或永久标识；
5. 投稿当日通过学校数据库核验 JISA 的 SCIE 与 JCR Q2 状态；
6. 在 Editorial Manager 上传前，再做一次作者填充后的 Word 页面检查。

因此，实验与当前科学内容集成可视为完成，但 `F-PAPER-002` 仍应保持
`in_progress`，直到上述作者和机构准入闭合。
