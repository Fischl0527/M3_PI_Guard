# 可迁移性验证与统一演示

目标：让当前修复版核心流程、研究输入投影和指定结果统计能在干净环境运行，提供教师能看懂的演示。不能把软件可迁移性解释为安全泛化。

范围：新增演示、可移植交付生成器、必要依赖清单、定向测试与普通说明；复用真实权限编译器、corrected_v2监视器、来源标签和模拟效果。不修改授权逻辑、历史原始记录、论文数字或第三方源码，不启动模型实验。

环境：Windows当前Python3.13.5；已连通Ubuntu24.04.4/Python3.12.3与阿里云Ubuntu22.04.5/Python3.10.12。初始Ubuntu/Kali桌面虚拟机未开机；本轮用户打开Ubuntu，经授权公钥登记后实测Ubuntu26.04.1/Python3.14.4；Kali仍待验证。

验收：
- 一个Python入口展示任务、权限、固定提案、放行/拒绝/请求信息、模拟执行与独立评分；明确不是在线模型性能。
- 包不包含密钥、内部trace、私钥、模型缓存、旧虚拟环境或停用工具包；无永久环境变量、真实邮件/支付/宿主代码执行。
- 干净解包路径不依赖E/F/D盘、原仓库和外部运行目录；每个实测系统运行定向测试及演示。
- 当前研究输入和900/480/16公开结果可读取并派生关键原始计数，不重算10,000次统计或递归证据链。
- 报告按系统/架构/Python/检查范围记录真实结果；虚拟机未验证时整体保持in_progress。

实施顺序：检查依赖→实现演示与最小包→Windows独立路径验证→两台Linux独立用户目录验证→准备虚拟机直接运行说明→报告、状态和范围Git。

初始检查：两SSH探测exit0；Ubuntu24基础Python没有pip，阿里云pip22.0.2可用。只在新用户目录建隔离环境，不sudo、不重启服务、不修改系统Python。两个目标m3-portability-20261009-v1均不存在。

状态：in_progress。后续实际命令与结果附在本记录，不新建哈希包或Runpro控制体系。

## 已实施与验证

- 新增真实corrected_v2演示/导出/离线验证和27个新测试；依赖公共原生AgentDojo固定提交，通过新建浅克隆保留Git身份，不复制原配置。导出已选200离线源记录，不分发完整封存集。
- 许可范围补充：仅为Python3.10语法兼容，policy_compiler的相同正则片段预计算；structural_baselines使用tomli回退。未修改授权语义。修复前后180投影完全相同，三端重新编译一致。
- 最终包生成：F:/robot/Anaconda3/python.exe -X utf8 -B -m scripts.build_portable_package --output release/M3_PI_Guard_portable_20261009，exit0，115Python源码/200selected sources/0API。
- 三端最终命令：新env的python -X utf8 -B -m scripts.portable_demo；scripts.portable_verify；pytest按pytest-portable.txt -q --tb=short --junitxml=outputs/portability/pytest.xml。Windows3.13.5/Ubuntu24Python3.12.3/Ubuntu22Python3.10.12各119passed，耗时25.54/40.89/26.21秒；三端pip check通过。
- 每端180权限一致/0gold，900/480/16raw计数一致。包含真实V2编译/监视器/受控效果与V1兼容原生288final-only串通，不把后者当新模型实验或任务效用。
- 27新pytest/Ruff通过；浏览器desktop/mobile、private/full/policy/ASK交互与390px无横向溢出检查完成，favicon404非JS问题披露。临时浏览器与HTTP已关闭。
- 新开机桌面VM在用户明确授权的一次认证及公钥登记后BatchMode通过，实测Ubuntu26.04.1/Python3.14.4/Git2.53.0；同包上传至/home/fischl/m3-portability-20261009-v1，新venv安装requirements-portable.txt成功，不改系统Python或服务。没有读取私钥或将密码写入项目。
- VM同样执行portable_demo、portable_verify、pytest按清单、pip check，exit0：119passed/8.51秒、180/0gold/0差异、900/480/16一致。Google SDK一条弃用警告保留；../解释器路径prefix提示使用规范绝对路径探测消失，不重跑测试。verification.json和本地pytest.xml已收回，四端raw_counts对象一致。
- 报告docs/可迁移性验证报告_2026-10-09.md含outputs/路径/错误修复/教师讲解/论文边界。Kali仍待验；本任务整体in_progress，四环境实施切片已完成。原userdirty保留，范围Git不强推。
