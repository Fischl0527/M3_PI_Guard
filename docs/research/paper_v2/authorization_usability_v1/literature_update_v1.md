# 2026-09-05 文献更新及本轮采用边界

这是研究开发补充，不直接重生成现有 LaTeX 主稿。同行评审与预印本分别标注，
不把不同 threat model、oracle feedback 或 evaluator 的数字直接横比。

| 工作与原始来源 | 状态 | 对 M3 本轮的具体影响 | 不采用的推断 |
| --- | --- | --- | --- |
| [PIArena](https://aclanthology.org/2026.acl-long.1533/)，Geng 等，DOI 10.18653/v1/2026.acl-long.1533 | ACL 2026，7 月，同行评审 | 跨任务可迁移性与 task-aligned injection 比继续堆同源矩阵更重要；外部验证优先原生 AgentDyn | 不把不同平台的输出判分和 unsafe effect 当同一指标 |
| [AgentDyn](https://arxiv.org/abs/2602.03117)，Li 等；[官方代码](https://github.com/SaFo-Lab/AgentDyn) | arXiv，2026；本次未核实正式发表状态 | 独立加载 Shopping/GitHub/Daily Life 的原生环境和 utility；检查动态权限需求 | 代码里的 28 个 injection task 类不是论文 560 个测试实例的同一计数单位 |
| [ASPI](https://arxiv.org/abs/2605.17324)，Sehwag 等，2026-05-17 | 预印本 | 确认渠道必须独立于工具文本；批准、拒绝、缺席和伪造都应测量 | E7a 单动作的模拟票据不能代表多轮自然澄清或真人可用性 |
| [AgentAntibody](https://arxiv.org/abs/2608.04053)，Weng 等，2026-08-04 | 预印本 | 关注授权边界和反馈后的策略更新，但明确其反馈条件 | 其稀疏事后标签反馈不能未经源码核对就指控为在线 gold 泄漏；本轮不增加在线学习 |
| [Auditing Provenance Sensitivity](https://arxiv.org/abs/2607.20827) | 预印本 | 区分来源标签、来源影响和最终动作；增加否定提及/编码/拆分来源探针 | literal matching 不等于真实因果溯源；强制提案回放不等于端到端攻击 |
| [AuthGraph](https://arxiv.org/abs/2605.26497)，Aligning Provenance with Authorization | 预印本 | 保持参数来源与授权对齐的直接竞争定位 | 不恢复“首个参数级来源系统”或机制领先声明 |

## 当下的实现决策

1. 不新增大型防御矩阵。先解释现有低完成率，补齐可检验的确认边界。
2. 不用增大攻击预算掩盖评估质量问题。E8 的原生 utility 与动态工具适配必须
   分别检查，不能拿模板改写任务冒充公共基准。
3. E7a 的 strict_exact 是刻意过度约束对照；bounded_enum 只允许可信任务的两
   种既定无害表达，不是对任意正文或目标放权。效果属于受控机制演示。
4. 跨厂商、跨日期与真人确认仍没有新增证据；旧 Gemini diagnostic/NE 不变。

## 模型服务变化的记录

执行前读取 [DeepSeek 官方价格页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)
确认 Pro 当前公开版本为 DeepSeek-V4-Pro-0813，API 请求标识仍使用
deepseek-v4-pro。Pro 峰值每百万 token 为命中 0.30 元、未命中 9 元、输出
27 元；空闲时段减半。不能再沿用旧计划 0.025/3/6 作为新执行成本。
E7a 每条记录保存实际请求/返回标识及按请求时间的费用估计；此估计不是账单，
别名一致也不构成服务端权重不可变证明。原始旧账本保持不变。
