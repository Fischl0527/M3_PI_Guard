# 综合后续研究实施

日期：2026-10-06。功能F-PAPER-002。状态：in_progress。

## 授权与范围

用户授权按docs/research/paper_v2/M3_PI_Guard_综合评估与后续研究计划_2026-10-06.md最大限度推进。不是重复运行已完成916条。主线P0诊断、P1同期校准；P2独立本地模型、P3原生动态基准与VIGIL按适配资格条件推进。

允许：新experiments/paper_v2实现、必要最小定向测试、新outputs/experiments/research_followup_20261006_v1产物、报告及必要论文/构建同步、Harness状态、范围Git提交推送。只有可复现实现违约才新增修复版本。

禁止：改写旧raw/冻结输入、成功行重复、无条件权限扩大、Gemini、Full Harness、历史递归验证、盲测、日期等待、真实邮件/支付/生产接口/宿主代码执行、上传内部请求/密钥、打包其他dirty或强推。

## 步骤与验收

1. 一次读取本研究900公开事件，覆盖240主良性及105非正常终态，分开记录首次阻断、完成和失败。未知保留，不从内部正文猜原因。
2. 紧凑复现必要接口问题，只在违约成立时修复；保留corrected_v2历史语义。测试先于API。
3. 在查看新结果前固定120配对案例及normal/auto三条件，12正式前缀包含在总数内；无防护与防护共用相同模拟能力与宿主边界。VIGIL调用前决定资格，不按结果筛选。
4. P1只运行pending新项；各任务独立状态、最多并发2、8请求/180秒超时/无自动重试。取得模型响应的行不重跑；未知/失败/未运行分别报告。
5. P2本地180和P3原生108先离线和格式资格化；不能忠实适配时透明说明，不伪造正式结果。
6. 一次重建各新研究统计/图表/Markdown报告，按批准路线更新解释边界和必要双语/LaTeX稿件；作者空白。
7. 代码资格化、结果、报告/稿件三个范围Git节点推送当前origin/codex/claude-review-repairs；不强推。

## 初始事实与假设

- 当前HEAD44ea311，当前无Python/Ollama实验进程。已有900主研究0/490攻击效果，但没有同期no-defense，不能证明防御有效。
- 低效用候选原因：①编译器缺工具/目标权限；②动态参数或非预期动作；③格式/长度/步数；④执行后评分条件未完成。仅是待检验假设。
- 首条抽查正常AgentDojo任务第一步ASK/permission_expansion/tool_outside_current_permission；只能确认缺工具许可，不说明许可必然应生成。
- 现有CorrectnessRuntime尚未注入VIGIL live factory且8-call硬限制；若添加基线需专用显式适配，不能把默认失败路径当合格基线。

## 验证记录

已运行Python3.13.5：pytest diagnosis4通过；P0一次性读取900，输出240主良性+105非正常的去重300行解释表。AgentDojoauto两条件26/30首先缺工具许可；length截断0，完成后失败2；不能单凭公开事件认定动态目标或编译器缺陷。

初次新资格+相邻回归83通过/8失败：6个错误布尔断言、2个无效VIGIL空约束fixture；未改源码安全行为，只纠正fixture。受影响8项再跑通过/5未选择，既有第三方Pydantic弃用警告保留。Ruff发现一个新文件未使用Path导入，删除后待复查。

VIGIL适配使用既有固定源码bridge（单次约束生成、禁止静默fallback）和确定性hybrid审计；这是明确配置的对照，不冒称完整默认VIGIL。P1冻结480=360主线+120VIGIL；12主前缀+4基线前缀均计入总数。已有normal/512/180秒不改。

## 实际运行与恢复

- 资格5676768已push/远端一致。16正式前缀全部completed，主12均可解析、VIGIL4合格；核心/基线门均passed。
- 第一扩展记录到120/480后停止：109completed/2max_steps/6parse_failure/2runner_failure/1provider_failure。两VIGIL失败有HTTP200、精确身份与length截断；Stop信号使一条已有响应ND任务终止。三者已有响应全部保留，禁止重跑。
- 新研究telemetry_v1.1仅修复线程输出和截断错误分类，512/T0/提示/权限/任务/工作键不变。当前线程logger过滤不替换stdout/stderr；身份有效length约束失败记parse_failure且端点未知；其他系统错误仍停。2定向回归通过，Ruff/编译通过。即将继续未触碰360；不恢复任何120终态。
- P2隐藏启动被工具策略执行前拒绝，不绕过；本地180未执行。P3新18参考链诊断0API、8true/10false、无物理效果；叶子动态调用监控和合法/越权状态评分对照尚不合格，不启动108模型研究。
- 分析模块4定向测试通过：未知ITT、Holm家族、退化CI、完成与失败共存、身份/成功重复。实际480统计尚待终态一次执行。

## 动态占位评分控制及当前进度

- 当前95802正常运行，已记录400/480，无新stop。d0d0e2d日志修正已推送；第一阶段所有120记录原样保留，新续跑不重发其请求。
- 新agentdyn_followup_controls_v1是离线oracle夹具控制，仅为verify_shopping/github的原固定占位参数读取当前虚拟账户唯一待验证队列，不改变工具、评分或原参考；歧义队列拒绝，不记录虚拟值/正文，也不进入在线授权。
- 4单元测试及Ruff通过；fresh UTF8进程执行18控制，15参考完成、3仍false、无操作0/18，0 API。原8true/10false不改写。shopping_task4参考购买quantity1而评分要求quantity2，源内不一致已看到；github9与dailylife5仍需进一步评分状态分析，不声称修好上游。
- 原生动态网页注册函数及验证码回调在外层runtime下面执行，叶子Guard全覆盖未合格；108模型项不启动。先交付诊断，不凭15/18将整个原生环境判为可部署。

## 本研究批次收尾

运行器95802正常exit0，480唯一work key/attempt1，443completed/9max_steps/25parse_failure/2runner_failure/1provider_failure，1172官方响应/1578814tokens。首次120全部保留，其余360telemetry_v1.1不改科学条件。无活动研究进程。

`python -X utf8 -m experiments.paper_v2.research_followup_analysis_v1`仅执行一次；Newcombe/10k任务聚类/Holm/Wilson/McNemar实际表图完成，图目视通过。随后只补公共收据计数和说明，不重做统计。478字段投影明确false、2缺；476结构化效果收据、4缺（VIGIL约束生成失败），旧记录不后补。

最终`pytest tests/unit/test_research_followup_diagnosis_v1.py tests/unit/test_research_followup_calibration_v1.py tests/unit/test_research_followup_analysis_v1.py tests/unit/test_agentdyn_followup_controls_v1.py -q`：27passed/1既有Pydantic warning；收据计数负例后`pytest tests/unit/test_research_followup_analysis_v1.py -q`：5passed。范围Ruff全通过。批次重叠不相加；不Full Harness或历史复验。

根report.md已记录实际480、P0原因、P2策略拒绝/P3离线15/18和安全资格缺口，清楚解释outputs目录。AgentDojo正常任务17/30→2/30代价显著，安全3/30→0/30区间跨零；M3无防护仍全零，不支持模块领先。科研整体和论文未完成，F-PAPER-002保持in_progress，下一步批准的稿件/LaTeX同步。
