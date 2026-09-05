# M3-PI Guard 授权可用性强化阶段报告

日期：2026-09-05。本阶段完成 P0、P2 和 E7a；E8 正式实验尚未开始。
所有新模型调用均来自 DeepSeek 官方 API。本阶段没有 Gemini、真实外部工具、
Full Harness、历史递归验证或旧实验成功行重跑。

## 1. 结论先行

本轮发现的主要问题是**测量边界与权限可用性**，不是缺少更多相同攻击样本。

1. 旧运行器遇到 ASK 后直接结束，因此旧 ASK 率不能当作完整确认功能的结果。
2. 旧 E2 的固定正文等字段也受到 exact 约束；240 条零执行不能解释成安全有效。
   历史结果未保存逐行 Guard reason，无法把每一条事后归为“正文不匹配”。
3. 新的96次API受控实验表明：在本来允许两种无害文字的任务里，过度精确的
   策略会阻断合法第二种表述；允许事先列明的两种表述、再取得独立确认后，
   提案可取得单次执行许可。但尚未调用后端改变任务环境，因此不是TCR证据。
4. 来源匹配和旧确认匹配都有明确实现边界。已对新实验提供更严格的确认会话；
   原历史运行时没有改动，既有结果没有被重新解释为“已修复版本”的结果。
5. AgentDyn原生环境已成功加载，但其固定示例轨迹在18个预选任务中只有8个
   满足native utility。需先理解其动态参数和判分，不能立即用低成功率做论文结论。

## 2. 一次性旧结果分解：1,560个logical work items

读取范围：E1 720、E2 240、E3 240、E4 360。按work key选择最新合法attempt，
未把工程恢复多算为独立样本。只读取这些最小raw，不重建历史证据树。

### E1 良性工具任务

以下分区互斥，合计为每条件60；这是观察分区，不是因果原因归属。

| 条件 | 完成任务 | 未完成且有ASK | 未完成、有DENY无ASK | 未完成、无记录ASK/DENY | operational failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| policy-normal | 23 | 20 | 0 | 10 | 7 |
| policy-safe | 21 | 17 | 0 | 16 | 6 |
| full-normal | 21 | 20 | 1 | 9 | 9 |
| full-safe | 19 | 22 | 1 | 10 | 8 |

不能把总ASK数与失败数简单相加：个别结果在失败或已完成前也出现ASK/DENY。
本表先分配operational failure，再分配完成任务，再按ASK/DENY分区，避免重计。
E4的良性工具完成率分别是10/30、8/30、10/30、10/30；详细分区保留在分析JSON。

### E2

| 条件/来源 | 计划数 | 动作执行 | 有ASK的行 | 有DENY的行 | operational failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| policy / trusted | 60 | 0 | 60 | 0 | 0 |
| policy / untrusted | 60 | 0 | 53 | 0 | 0 |
| full / trusted | 60 | 0 | 57 | 0 | 0 |
| full / untrusted | 60 | 0 | 0 | 55 | 1 |

源码证据：

- `experiments/paper_v2/live_condition_runtime.py` 在ASK后break，未调用独立确认接口。
- `experiments/paper_v2/incremental_empirical_plan_v1.py::_controlled_manifest`
  对全部参数（包括subject/body/content/params）使用exact。
- `_controlled_message_builder`只提供可信请求和来源块，没有把固定正文逐字
  作为可见操作要求给出。不能让模型猜隐藏的固定文案后再把不匹配称为攻击。
- E2公共raw没有逐行proposal/Guard reason；provider trace也不存完整请求/响应。
  所以“有多少旧行具体因为哪个字段被阻断”仍是不可追溯，不编造百分比。

## 3. 512个新的确定性探针

这512个探针不是重放旧API输出，也不是新增模型实验样本。

### 3.1 480个参数扰动探针

120个E2来源上下文 × 两类新参数扰动 × policy/full：只改变无害表述，或只改变
安全目标。policy对每类的120个提案都返回ASK；full对每类90ASK、30DENY。
因此，原约束确实可能同时阻断无害文字变化和目标变化，但不能反推旧模型实际
提案就是这些探针。源信息和权限信息相互作用，不能把所有阻断归功于provenance。

### 3.2 28个来源压力探针

7种来源形式 × exact/broad目标策略 × policy/full：含不可信原文、可信请求中的
否定提及、引用警告、实体编码、跨记忆拆分、工具instruction字段及合法重复。

- 否定提及/引用警告可被literal matcher标为trusted_user；它不能理解“提到某
  地址”与“授权该地址”的区别。
- 编码或拆分值可变成model_generated，不能据此认为它没有不可信影响。
- 对6种非授权目标探针，exact目标策略下两配置均没有ALLOW；broad目标策略下
  policy有6/6 ALLOW，full有4/6 ALLOW。它们是强制提案下的条件机制结果，不是
  真实攻击成功率，也不意味着本轮存在真实外部影响。
- 因此不应把“来源标记”写成可靠因果溯源；精确安全目标与独立确认仍须保留。

### 3.3 4个旧确认探针与新修正

旧匹配中无approval时ASK；构造的过期exact scope、不同proposal的部分参数scope、
仅tool scope均可ALLOW。源码未检查expires_at，并允许scope匹配替代proposal精确
匹配。**这不证明外部攻击者能取得可信审批记录**；它揭示的是组件契约过宽。

新增`confirmation_session_v1.py`仅供新实验使用：

- task、可信request、完整proposal、manifest四重绑定；
- 有效期与单次消费；拒绝不可改为批准；
- 工具/模型文本的假确认永远不进入可信controller入口；
- 不扩权，不覆盖DENY，不使用旧approval旁路。

这不是生产身份认证系统，controller是进程内模拟第三方，也不是招募真人研究。

## 4. E7a：96次官方API + 384个提案后确认条件

设计详见`protocols/paper_upgrade_v2/e7_confirmation_usability_v1/plan_v1.md`。
24个新合成任务，3种模拟工具各8条；每种4clean、4attack。四个同期条件是
strict_exact/bounded_enum × policy/full，均为normal prompt。两个module条件
共享新的确认wrapper，不能称为旧policy-only不加修改的复现。

API96/96都有官方response ID且均可解析，无operational failure。先8条正式
前缀，技术门通过后执行其余88条；request ID和response ID均96个唯一。

### 4.1 取得可信批准时：许可率，不是原生任务完成率

最终源码复核发现，当前runner在票据消费后记一个许可布尔值，没有调用effect
backend修改环境。raw中的`task_completion/simulated_effect/unsafe_effect`
命名过强，分别仅表示“合法提案获许可/任意提案获许可/非授权提案获许可”。
原raw不改，analysis加入明确字段解释；下表使用正确含义。这项实现缺口已经
登记，不能把组件许可率换名为端到端TCR，也不追加事后伪造的effect receipt。

| 新条件 | 良性合法提案获许可 | 攻击条件下合法提案获许可 | 非授权提案获许可 |
| --- | ---: | ---: | ---: |
| strict_exact / policy | 0/12 | 0/12 | 0/12 |
| strict_exact / full | 0/12 | 0/12 | 0/12 |
| bounded_enum / policy | 12/12 | 12/12 | 0/12 |
| bounded_enum / full | 12/12 | 12/12 | 0/12 |

12/12的Wilson95%区间约为75.75%–100%；0/12约为0%–24.25%。每种module内
bounded−strict的良性提案许可率差为+100pp，exact McNemar p=0.00048828125。
这些是刻意过度约束对照中的描述量，不是自然任务上的显著效用提升主张。

尤其需要注意：可信请求明确偏好第二种合法措辞，strict_exact仅接受第一种。
该设计验证的是**策略与明确任务意图不一致会制造阻断**，不是公平比较一个
正确编译的exact策略与另一通用防御。也不能据此宣称full优于policy。

### 4.2 完整确认状态

| 提案后状态 | 个数（384个条件单元） |
| --- | ---: |
| scope不允许，不能靠确认扩权 | 192 |
| 获可信批准，取得单次执行许可 | 48 |
| 可信拒绝 | 48 |
| 缺席或伪造确认，保持不执行 | 96 |

不可信假确认没有产生额外执行许可。四种channel使用同一提案的不同内存会话，
属于配对的机制条件，不能把384当作独立模型样本。模型没有进行后续多轮澄清。
攻击提案本身没有发生目标偏转，所以零非授权许可不提供攻击活性或SOTA证据。

### 4.3 API和成本

- 模型请求/返回均`deepseek-v4-pro`；官方公开服务版本为Pro-0813。
- prompt tokens 24,096，其中cache hit 13,824、miss 10,272；输出4,572。
- 按2026-09-05官方空闲价估计CNY0.1100196；不是余额差或正式账单。
- provider tools=0，real effects=0，原始gold/evaluator在线字段=0。
- raw只保留请求身份、payload digest、proposal digest、原因码、来源类别和指标；
  不保存密钥、完整模型请求/响应正文。局部锁防止并行重复写同一研究。

## 5. E8原生外部验证：已资格化的部分和未完成部分

官方源码单独缓存，未安装或覆盖AgentDojo。三个native suite各20个用户任务，
固定预选18个。首次因Windows默认编码失败；`-X utf8`修正后18条离线检查
全部执行，无异常、无物理写入/网络/子进程尝试，noop utility为0/18。

但固定GroundTruthPipeline只有8/18满足utility。其余10条需要核对动态参数、
验证码和示例轨迹的用途；不能把它们删除后宣称“通过原生复现”。也不能将
这种known-answer检查当作M3模型完成率。18个任务保持不变。

**E8尚未完成：**native正负effect fixtures、非oracle策略适配、动态registry
拦截、注入位置与目标冻结，以及108条拟定模型矩阵。下一步先处理这10条
原生控制轨迹的判分差异，再进入模型前缀。详见E8的`next_execution_plan.md`。

## 6. outputs目录怎么读

根目录是`E:\M3_PI_Guard_test\outputs`。不要把旧`experiments/E7/`语言实验与
本次小写全名`e7_confirmation_usability_v1/`混淆，它们不是同一研究。

```text
outputs/
├── experiments/                         # 研究结果主目录
│   ├── incremental_empirical_v1/         # 既有E1--E5，不改
│   ├── lean_empirical/                   # 既有授权制度结果，不改
│   ├── e6_cross_provider_calibration_v1/ # 失败的原三窗口历史，不恢复
│   ├── e6_cross_provider_calibration_v2/ # 已封存B1，Gemini仍diagnostic/NE
│   ├── authorization_usability_v1/       # 本轮P0/P2
│   │   ├── analysis_v1.json              # 1,560旧work items的聚合分解
│   │   └── offline_probes_v1.jsonl        # 512个新探针，不是旧API轨迹
│   ├── e7_confirmation_usability_v1/     # 本轮96次新API
│   │   ├── raw_records_v1.jsonl          # 96个start + 96个terminal事件
│   │   └── analysis_v1.json              # 32个cell及配对描述统计
│   └── agentdyn_native_qualification_v1/
│       ├── qualification_v1.json        # 最初18个编码错误，保留
│       └── qualification_v2.json        # UTF-8后18个native离线检查
├── metrics/                             # 旧聚合指标
├── runs/                                # 旧模型/模拟运行输出
├── paper_upgrade_v1/, paper_upgrade_v2/  # 历史协议升级输出，不递归重算
├── paper_v2/                            # 既有论文/实验中间输出
├── document_qa/, report_qa/              # 历史文档视觉检查产物
├── verification/, quality/              # 历史验证与质量产物，本轮未运行Full Harness
└── test-tmp/                            # 临时测试目录，不是正式实验结果
```

研究计划在`protocols/paper_upgrade_v2/`，代码在`experiments/paper_v2/`，
本报告和文献更新在`docs/research/paper_v2/authorization_usability_v1/`。
本轮只公开上述最小结果，没有新增递归哈希包或重复副本。

## 7. 验证、Git与剩余工作

Python：F:\robot\Anaconda3\python.exe，3.13.5。27个新增定向pytest通过，Ruff
与py_compile通过。没有Full Harness。初次Ruff一个E731已修复；原生首次
UnicodeDecodeError通过进程级UTF-8修复，两个资格结果均保留。

在仓库根目录运行的主要命令：

```powershell
& 'F:\robot\Anaconda3\python.exe' -m experiments.paper_v2.authorization_usability_diagnostics_v1
& 'F:\robot\Anaconda3\python.exe' -m experiments.paper_v2.e7_confirmation_plan_v1
& 'F:\robot\Anaconda3\python.exe' -m experiments.paper_v2.e7_confirmation_runner_v1 --canary-only
& 'F:\robot\Anaconda3\python.exe' -m experiments.paper_v2.e7_confirmation_runner_v1 --resume-pending-only
& 'F:\robot\Anaconda3\python.exe' -m experiments.paper_v2.e7_confirmation_runner_v1 --analyze
& 'F:\robot\Anaconda3\python.exe' -X utf8 -m experiments.paper_v2.agentdyn_native_qualification_v1
```

以上已完成命令无需重复运行。阶段提交`ca49a28`（设计）和`4fcbd02`（实现/
离线资格）已推送RedTeam_LLM_Security的codex/q2-empirical-study；本报告与
结果随最终阶段提交推送。不触碰旧dirty子模块、用户原始LaTeX资产或tmp。

后续优先级：E8原生判分/适配与真实内存effect receipt > 多轮确认扩展 > 论文内容整合。本阶段没有
重编LaTeX、没有把新小样本结果塞入主稿。作者信息继续留空，跨厂商和时间重复性
声明仍禁用。整体强化任务保持in_progress，不宣称全部优化或论文投稿就绪。
