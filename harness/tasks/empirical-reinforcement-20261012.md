# 强化实验实施

- Feature：F-EXP-REINFORCE-001；状态in_progress。
- 已批准目标：R1效用/授权扩样、R2攻击活性、R3同动作机制回放；计划2,165模型项及320受控判定。
- 允许：新experiments/paper_v2/empirical_reinforcement*模块/测试、运行时可选捕获接口、对应新outputs、计划与必要Harness状态。
- 禁止：历史输入/raw覆盖、论文/LaTeX正文修改、Gemini、FullHarness、真实外部效果、密钥读取/打印/复制、用户dirty清理。
- 基线：codex/claude-review-repairs；原17条暂存PDF移动保持，论文修订与其他dirty不并入提交。
- 分工：Builder样本计划；Builder捕获/机制；Builder统计；root运行器、集成、执行、服务器与Git。
- 验证先于模型：计划数量/唯一性/嵌套/前缀；capture默认兼容、数据隔离；显式一次恢复及调用上限；统计配对/未知/全零界限。只定向pytest、Ruff、py_compile。
- 服务器：2026-10-12 SSH LFischl连通，实测Ubuntu22.04.5/Python3.10.12/2核；LFS及LFischl-local连接关闭。服务器先承担离线工作，不搬运API密钥，不影响其他服务。
- 完整设计见docs/research/paper_v2/强化实验计划_2026-10-12.md。

## 进度与验证

- 用户补充实际地址后，`ssh lfischl@10.210.13.167`实测成功：Ubuntu24.04.4/Python3.12.3/4核。原LFS/Tailscale地址不可用不代表此主机离线。仅新隔离研究工作区，不重启既有服务。
- 测试边界沿用已批准计划：公开样本/CLI、可选捕获/回放、收据隔离、显式恢复、配对统计。新增Flash VIGIL16请求只在显式empirical_reinforcement_v1 scope开放；旧调用默认不变，红测试TypeError后绿色1项通过。

以下按阶段保留实施记录。当前四个API队列2165/2165均封闭，R3正式回放及一次统计已生成，报告/Git收尾中；不将执行数冒充任务成功数。

### 2026-10-13 启动前资格化

- 本地七套定向测试148 passed/55.71秒，1条VIGIL/Pydantic弃用警告；Reviewer发现并发孤儿风险、早期解析被误计为终态，两处先新增负例确认失败，再修复后3 passed。
- 服务器补传复用E6统计模块，并固定int.from_bytes(byteorder="big")兼容Python3.10；Ubuntu24与阿里云Ubuntu22分别22 passed/2 deselected。排除项为完整运行时所需中型计划及AgentDojo Git checkout未随精简离线包上传，本地完整对应测试已通过，不伪称服务器全项目验证。
- 计划实生成Pro效用1085、Flash效用600、Pro活性320、Flash活性160；两模型仍未调用。R3正式回放等待本研究捕获完成后一次生成。
- Git仅新模块/测试/计划、三运行接口增量和本任务状态；原17暂存PDF以及另一任务的注释汉化、论文改动不进入本轮提交。

### 正式启动

- 最终四套强化单测55 passed/22.41秒，Ruff通过。Reviewer两处建议已以红→绿修复。
- 155e0cc已推送origin/codex/claude-review-repairs并ls-remote一致；短暂index锁后一次性index-info恢复本轮路径，原17暂存不变，不删除锁或改变用户工作树。
- 实际命令（F:/robot/Anaconda3/python.exe）：`python -X utf8 -B -m experiments.paper_v2.empirical_reinforcement_v1 --study utility --model pro --canary-only`及flash版本。均30终态，29可解析，门通过。
- 已以同一入口`--resume-pending-only`并行扩展Pro剩余1055、Flash剩余570项，不重复正式前缀。

- 独立Reviewer只读复核各30前缀：各6任务/5cell各6行/attempt1，Pro79/Flash74实际调用ID及digest完整；首载荷一致，512参数/call caps/安全收据通过，tools/external=0，公开字段无正文/参数/密钥。未按安全结果改变准入。

- 北京时间2026-10-13 01:37，Flash utility 600/600唯一终态完成（578 completed、19 max_steps、3 parse_failure；这些状态不是任务完成率）；无重试/停止原因。对应模型已退出后才启动activity flash 16项正式前缀，Pro utility仍运行。

- Flash activity 16项前缀完成，核心10/12、VIGIL3/4可解析终态，技术门通过；已继续144项pending。前缀3 parse_failure原样保留，不重跑、不依据unsafe扩展。

- 北京时间2026-10-13 01:42，Flash activity 160/160终态完成（148 completed、6 max_steps、6 parse_failure），无stop_reason/重试。Flash共760项均封闭；Pro utility仍运行，未启动下一同模型任务以保持并发上限2。

- Flash全批独立只读审查通过：600/160计划key完全一致，1494/385官方调用身份/参数/caps及安全收据完整，工具/真实effect/在线forbidden=0，无正文泄漏/重复attempt；utility120组五cell、activity40组三核心cell首载荷一致。一条VIGIL约束length截断未生成动作，unsafe/TCR正确unknown；其约束生成子计数字段缺失，但总调用1已保留，不改raw、不重跑，报告披露。

- 北京时间2026-10-13 01:57，Pro utility 1085/1085终态、955 completed/54 parse_failure/76 max_steps，无stop_reason；原进程exit0且无活动runner后才启动Pro activity 16项正式前缀。本研究模型调用仍限已批准2165计划项。

- Pro activity前缀16/16结束exit0，核心12/12及VIGIL4/4可解析，技术门通过；只扩展304项pending（同CLI --resume-pending-only），无新研究或已有响应行重跑。

- 集成37项测试通过/56.22秒，1条VIGIL第三方弃用警告保留；Ruff首次E731后改def。Flash专用新scope红→绿通过，历史Flash16上限拒绝回归保持。
- 两服务器旧portable环境无numpy；新分析需要numpy，仅在新任务用户级环境安装，不修改系统Python。图像若缺依赖可本地绘制，统计仍在服务器运行。

### 分析器负担及身份披露补充（Builder）

- 仅修改本研究分析器和其单元测试。各condition/model/cell按所有实际尝试累计模型请求、每任务调用分布、输入/输出/总token及CNY峰值费率成本估算；未知、非法及缺失字段独立计数，不补零。显式恢复调用计入用量，不重复增加终态任务分母。
- CSV和报告披露VIGIL每任务最多16次请求、其他条件最多8次；约束生成子计数只读取显式字段，截断行缺子计数仍保留已有总调用，不推断分项。成本是记录中的费率估算，不是账单实付。
- 请求模型别名、实际官方响应别名、冻结服务元数据版本分别记录；Pro服务版本DeepSeek-V4-Pro-0813与当前DeepSeek-V4.1-Flash由计划元数据披露，不冒充官方响应model别名或权重快照。当前Flash不能当作旧V4 Flash或跨厂商复现。
- 红测试先暴露缺负担字段及全缺失成本报告格式错误；修复后：`F:/robot/Anaconda3/python.exe -X utf8 -m pytest tests/unit/test_empirical_reinforcement_analysis_v1.py -q` →22 passed/0.86秒；同Python `-m ruff check experiments/paper_v2/empirical_reinforcement_analysis_v1.py tests/unit/test_empirical_reinforcement_analysis_v1.py` →All checks passed；`-m py_compile`对应两文件 →exit0。
- 以上仅临时测试夹具；未读取internal、修改raw、调用API或重算正式统计，主终点、配对结构、Holm家族及失败分母未改变。正式分析/图表由root在运行封闭后执行。

- Root复核实际VIGIL工厂/adapter配置后，补充集中解释：模型二次验证和模型约束二次验证均关闭，不将当前适配当官方完整默认系统。报告文字负例先失败后修复；不改变基线代码或实验行。Ubuntu24与阿里云Python3.10本次成本/身份补充各22测试通过。

### 全批封闭及一次分析（2026-10-13）

- Pro activity320/320终态，296 completed、13 parse_failure、11 max_steps，exit0且无活动API runner。四批2165 work key全部唯一且attempt1；5463官方调用及local/response ID跨队列唯一，无自动重试、身份漂移、在线字段泄漏、provider tools或真实effects。
- 独立Reviewer技术审查四批通过。VIGIL创建环境前输出截断5项（Pro4/Flash1），安全/完成结局为unknown；总调用完整，约束生成子计数字段缺5项，不填造或删行。
- `--study mechanism --resume-pending-only`单次exit0：40基础夹具/320判定，358实际捕获回放、457可捕获ND项上界，0新provider调用/真实effects。分析器检查160完整受控对及同输入，40夹具四家族各10；80受控对变更、实捕获仅3对ASK→DENY，不等同端到端效益。
- 仅20个公开case/plan/raw/status/机制文件传Ubuntu24隔离工作区；未传internal或凭据。服务器`python -B -m experiments.paper_v2.empirical_reinforcement_analysis_v1 --output-root outputs/experiments/empirical_reinforcement_v1 --no-figures`一次完成10000次分层任务bootstrap。取回analysis JSON，本地write_outputs只渲染，不再运行统计。
- 总体1977 completed、76 parse_failure、112 max_steps；188为响应输出/步数失败，未运行0；5个评分未知保留在ITT。tokens6412110，峰值费率估计CNY12.18708388，不是实付账单。
- R3可选study_part缺标签：真实plan使用study。实际形状测试先失败，未来捕获投影已修并新增模型身份标签，机制7单测通过；原358 capture和公开回放不重写，来源以work_key唯一匹配当前plan，模型实验、正式回放和统计均不重跑。两次抽查用了不存在/空展示字段，改实际schema后通过，不是模型/结果故障。
- 两幅SVG已本地实际渲染视觉核对；临时PDF文本最低10pt，collision各0fail/0warn，预览仅harness/tmp，不冒充论文投稿排版完成。
