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

实现进行中，尚未启动API。最终逐项写入实际命令、测试数、完成量及阻塞，不用计划数冒充结果。

### 2026-10-13 启动前资格化

- 本地七套定向测试148 passed/55.71秒，1条VIGIL/Pydantic弃用警告；Reviewer发现并发孤儿风险、早期解析被误计为终态，两处先新增负例确认失败，再修复后3 passed。
- 服务器补传复用E6统计模块，并固定int.from_bytes(byteorder="big")兼容Python3.10；Ubuntu24与阿里云Ubuntu22分别22 passed/2 deselected。排除项为完整运行时所需中型计划及AgentDojo Git checkout未随精简离线包上传，本地完整对应测试已通过，不伪称服务器全项目验证。
- 计划实生成Pro效用1085、Flash效用600、Pro活性320、Flash活性160；两模型仍未调用。R3正式回放等待本研究捕获完成后一次生成。
- Git仅新模块/测试/计划、三运行接口增量和本任务状态；原17暂存PDF以及另一任务的注释汉化、论文改动不进入本轮提交。

- 集成37项测试通过/56.22秒，1条VIGIL第三方弃用警告保留；Ruff首次E731后改def。Flash专用新scope红→绿通过，历史Flash16上限拒绝回归保持。
- 两服务器旧portable环境无numpy；新分析需要numpy，仅在新任务用户级环境安装，不修改系统Python。图像若缺依赖可本地绘制，统计仍在服务器运行。
