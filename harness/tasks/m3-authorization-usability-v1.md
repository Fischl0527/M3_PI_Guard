# 文献驱动研究强化：授权可用性、确认闭环与外部动态任务

日期：2026-09-05。关联 F-PAPER-002。状态：in_progress。

## 阶段交付

- P0/P2/E7a已完成并验证；E8仅完成原生资格检查，不声称整体完成。
- 新API96/96终态；确认384单元；成本估计0.1100196元，非账单。
- 当前27个新增定向pytest通过。旧runtime/raw不变；报告详见docs同名目录。
- E8保留18个固定task IDs；无异常后固定示例utility仍8/18。下一工作是解释
  10条差异并实现非oracle适配，正式外部模型结果尚不存在。

## 已批准范围与顺序

1. P0：对现有 E1/E2/E3/E4 的最新 logical attempt 做一次性分解。只输出原始
   分子/分母、失败类别、ASK/DENY；没有保存 reason code 的历史行不可猜测原因。
2. P0：核对策略编译与 evaluator，使用新标记的确定性探针验证假设，不将探针
   当作旧 API 轨迹。补充最新原始论文和边界说明。
3. P2：离线测试重复来源、否定提及、编码变化和多步来源，分别报告 attribution
   与 Guard effect；不因归因不完美就宣称执行绕过。
4. E7：在诊断之后预先固定授权粒度 × 确认通道的受控实验。可信确认必须绑定
   task/tool/arguments/request；支持批准、拒绝、缺席、伪造。模拟确认不代表真人。
   精确安全目标和敏感正文约束不因提高完成率而放松。先定向测试，再正式前缀。
5. E8：审阅 AgentDyn 官方代码及原生 evaluator，选择与结果无关的小规模
   clean/attack 配对子集；独立环境，不覆盖已安装 AgentDojo。先做离线适配，
   正式执行只使用内存模拟工具。若只能做改写版，不能称原生 AgentDyn 验证。

## 最小产物及验收

- 新诊断代码及 tests；`outputs/experiments/authorization_usability_v1/` 中的
  一个聚合分析 JSON 与离线探针 JSONL；文献/阶段报告放在同名 docs 目录。
- 新研究计划置于 protocols/paper_upgrade_v2，不改变任何旧冻结记录。
- 单元测试覆盖分母、重复 attempt、未知原因、字段隔离、确认绑定与伪造来源。
- 不对旧数据做因果归因；区分源代码证据、确定性实验和模型实验。
- 所有失败保留；小样本与富集样本的结论仅限实际测试范围。
- 仅 pytest 定向节点、Ruff、py_compile、git diff --check。禁止 Full Harness。
- Git 阶段：设计/诊断；运行器离线资格；新增实验结果。推送 origin，不 force。
- 不触碰 dirty external 子模块、tmp、用户未跟踪 LaTeX 原始资产及秘密配置。

## 当前发现（实现前）

- E2 公共 raw 保存动作计数和 ASK/DENY，但不保存 proposal/Guard reason 轨迹；
  provider trace 也不保存提示或响应正文。不能追溯每行 constraint mismatch。
- E2 manifest 将 target 与固定 subject/body/content/params 一并精确约束，
  requires_confirmation=False；原运行时的 ASK 处理需检查，不能直接归为真人拒绝。
- 现有 infer_argument_provenance 是值包含匹配并优先可信来源，不是因果溯源。
- 本轮不预设改进方向一定有效；发现新安全缺陷时先隔离验证，保留旧实现。
