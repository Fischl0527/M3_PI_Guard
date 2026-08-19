# M3-PI Guard paper-v2 预注册 v1

状态：`frozen_design_future_results_pending`  
机器可读版本：`preregistration_v1.json`

## 冻结边界

本预注册只约束 2026-07-23 之后新生成的 paper-v2 中型证伪、公共基准、盲测和自适应攻击结果。它不把任何 paper-v1、诊断、资格验证、失败根或历史结果重新标为正式证据。

冻结内容包括：

- RQ1–RQ4；
- `exact_gold / auto_compiled / broad / underspecified / conflicting` 五种授权 regime；
- 六个核心条件；
- unsafe-effect ITT 主终点；
- TCR `-5pp` 非劣界限；
- 机制论文的安全效应、模块增益和 deny-all 止损门槛；
- 失败、超时、解析错误和服务故障的分母规则；
- 盲测降级命名规则；
- 自适应攻击预算；
- 统计方法和自动转向条件。

## 当前不能执行正式实验的原因

预注册冻结时缺少的输入仍保留在下列历史列表中；当前实时状态由
`medium_falsification_gate_v2.json` 给出：

1. 一个满足官方 API 或可审计网关要求的主模型；
2. ~~60–80 个中型配对任务的固定 case IDs~~（已冻结 72 个）；
3. ~~VIGIL 或 DRIFT 的忠实适配及源码/环境锁~~（两者零调用资格验证已通过，
   模型依赖路径仍待 provider）；
4. ~~至少 20 个 online-state 审计单元的完成证据~~（20 个单元、14 个项目已完成；
   领域级主张仍缺独立复核）；
5. 正式 API 成本上限；
6. 第三方盲测保管人。

中型实验当前只剩第 1、5 项阻塞；独立保管人不阻止中型证伪，但继续阻止
“独立盲测”声明。provider 身份和成本上限缺失时，只允许本地 stub、静态审计和
非正式适配测试，不得生成或晋升正式论文结果。

## 停止与转向

中型实验后立即应用预注册门槛。若 M3-full 不优于 policy-only、TCR 明显下降、效果主要来自拒绝全部动作，或 M3 明显不如 VIGIL/DRIFT，则停止防御领先叙事，转为授权泄漏、不确定性和安全—效用权衡的系统实证研究。
