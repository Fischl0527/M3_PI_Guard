# E8 原生 AgentDyn：当前资格检查及下一实施步骤

2026-09-05。状态：in_progress；**未启动正式模型实验**。

## 已完成

- 独立源码缓存：external/benchmarks/agentdyn，官方 commit
  5353cf7615b135cace8d07c8f12dac53a16b6db3；MIT。没有修改上游文件或 pip 安装。
- Python 3.13.5 成功导入 3 个套件；每套 20 个 user tasks，注入任务类9/9/10。
- 用固定 seed 在每套挑选 6 个 task ID，共18个，在查看 fixture结果之前写入
  qualification_sample_v1.json；后续不得为了好结果删换这18个任务。
- 原生加载需 `python -X utf8`，只影响当前进程。最初18个 encoding failure
  留在 qualification_v1.json；修复后 v2 单独记录，不覆盖错误证据。
- v2：18个任务均完成原生离线检查；noop utility 0/18，但上游固定
  GroundTruthPipeline 只满足 utility 8/18，另10条返回false、无异常。
  这不是模型失败率，也不能仅凭它断言上游 evaluator 有缺陷。

## 在正式 API 前必须完成的实质工作

1. 对10个原生示例轨迹 utility=false 的任务逐一核对：固定 ground_truth 是否
   只是占位/注入定位轨迹，是否缺少动态验证码或多步参数。生成最小的**离线**
   合法/非法 effect fixtures，确认 native utility/security 真正测的是什么。
   gold轨迹和 fixture绝不进入在线策略。
2. 实现只暴露可调用 schema、可信用户任务和当前模拟观察的 runtime adapter。
   初始授权只由可信任务编译；不能从 ground_truth 提取目标、工具集合或参数。
   动态 tool registry 的开放动作必须经过同一 wrapper，不能从网页函数旁路执行。
3. 固定每任务的 attack placement、native injection目标和无攻击对照。当前
   18 task IDs 已定，但注入实例尚未冻结，不能宣称完整 E8 计划已完成。
4. 拟运行18任务 × clean/attack × no-defense/policy/full（相同 normal prompt）
   =108条新模型执行；若部分任务无法安全/忠实适配，保留其状态、不得悄悄换题。
   前缀6条（三条件×clean/attack）只看技术质量；新 DeepSeek 身份与 E7分开。
5. 报告原生 utility、安全端点、ASK及失败；若校准仍未能确认端点有效性，只能
   作为适配诊断。保持历史 E1--E7a 不变，不扩展 Gemini，不做 Full Harness。

## 现有离线命令

在 E:\M3_PI_Guard_test 目录下使用：

```powershell
& 'F:\robot\Anaconda3\python.exe' -X utf8 -m experiments.paper_v2.agentdyn_native_qualification_v1
```

此命令不是正式 benchmark，也不会调用 API；已完成资格结果无需无理由重跑。
原生执行时有当前进程内的物理写入、socket、子进程阻断。它是测试边界，不是
可对任意恶意 Python 提供隔离保证的生产 sandbox。
