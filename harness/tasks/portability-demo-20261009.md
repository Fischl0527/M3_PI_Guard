# 可迁移性验证与统一演示

目标：让当前修复版核心流程、研究输入投影和指定结果统计能在干净环境运行，提供教师能看懂的演示。不能把软件可迁移性解释为安全泛化。

范围：新增演示、可移植交付生成器、必要依赖清单、定向测试与普通说明；复用真实权限编译器、corrected_v2监视器、来源标签和模拟效果。不修改授权逻辑、历史原始记录、论文数字或第三方源码，不启动模型实验。

环境：Windows当前Python3.13.5；已连通Ubuntu24.04.4/Python3.12.3与阿里云Ubuntu22.04.5/Python3.10.12。初始Ubuntu/Kali桌面虚拟机未开机，后续均已由用户开启并完成验证：Ubuntu26.04.1/Python3.14.4、Kali2026.1/Python3.13.12。

验收：
- 一个Python入口展示任务、权限、固定提案、放行/拒绝/请求信息、模拟执行与独立评分；明确不是在线模型性能。
- 包不包含密钥、内部trace、私钥、模型缓存、旧虚拟环境或停用工具包；无永久环境变量、真实邮件/支付/宿主代码执行。
- 干净解包路径不依赖E/F/D盘、原仓库和外部运行目录；每个实测系统运行定向测试及演示。
- 当前研究输入和900/480/16公开结果可读取并派生关键原始计数，不重算10,000次统计或递归证据链。
- 报告按系统/架构/Python/检查范围记录真实结果；虚拟机未验证时整体保持in_progress。

实施顺序：检查依赖→实现演示与最小包→Windows独立路径验证→两台Linux独立用户目录验证→准备虚拟机直接运行说明→报告、状态和范围Git。

初始检查：两SSH探测exit0；Ubuntu24基础Python没有pip，阿里云pip22.0.2可用。只在新用户目录建隔离环境，不sudo、不重启服务、不修改系统Python。两个目标m3-portability-20261009-v1均不存在。

状态：verified（五个指定环境的限定交付范围）。实际命令与结果附在本记录，不新建哈希包或Runpro控制体系。历史进行中记录保留；论文整体不在本任务结项范围。

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

## Kali补验：2026-10-09已完成

- 用户提供已开机Kali登录信息并授权运行。只使用已有密码认证，不更改Kali的SSH认证配置；不保存密码或读取私钥。
- 步骤：实测OS/Python/Git及目录冲突→同包拷贝和新venv安装→演示/权限/原始计数/119定向测试/pip check→公开结果Git→文档与Harness更新及Git。
- 允许：任务独立用户目录、outputs/portability/kali/、本任务报告/运行指南/项目入口及必要Harness状态。禁止：系统包/服务/权限规则/论文/raw数据/历史重算/Full Harness/API/其他用户dirty。
- 验收：119测试无失败或跳过、180权限与参考一致、900/480/16原始计数一致；如不满足则记录真实原因，不提前将F-PORT-001设为verified。
- 实测Kali2026.1 Rolling/Py3.13.12/Git2.51.0/内核6.18.12+kali-amd64，35GB空闲；目标原不存在，在/home/kali/m3-portability-20261009-v1新建venv，从原包解压并安装原依赖。所有修改仅在任务目录，无sudo、系统Python或服务/SSH配置改动。
- 实际执行：/home/kali/m3-portability-20261009-v1/.venv/bin/python -m pip install --isolated --index-url https://pypi.org/simple --disable-pip-version-check --no-cache-dir -r requirements-portable.txt；相同绝对解释器-X utf8 -B -m scripts.portable_demo；scripts.portable_verify；pytest $(cat pytest-portable.txt) -q --tb=short --junitxml=outputs/portability/pytest.xml；pip check。全部exit0，119passed/7.39秒，0failures/errors/skips；180/0gold/0差异、900/480/16一致。
- 回收outputs/portability/kali/verification.json和本地pytest.xml，与Windows逐对象raw_counts一致；结果先提交推送c8d84cc。再更新六文档及必要Harness，94本地链接0断链，范围diff和feature JSON通过。F-PORT-001 verified，F-PAPER-002不变。
- 此前四端不重跑，原包/科研数据/统计/PDF不改，没有FullHarness或API。SSH、安装与测试都已正常退出，密码没有写入文件/仓库；原用户dirty保留。
