# M3-PI Guard 独立盲测保管人审查包 v3

## 1. 你要完成什么

你是独立盲测保管人。你不修改 M3-PI Guard，不替开发者调参，也不运行模型。
你需要独立完成以下链路：

1. 登记真实保管人和独立真人验签人；
2. 私下编写、拆分并封存 600 条盲测样本；
3. 只把无标签 execution set 交给开发者；
4. 在开发者返回完整 3,600 条结果链后，先复验再于本地解封标签；
5. 私下评分并签署结果；
6. 生成两个严格隔离的终态包：保管人私有工件全链审计包和开发者安全证据包。

本包不联网，不调用模型、浏览器、邮件、支付或生产 API，不设置环境变量，也不
包含 PowerShell 包装脚本。所有保管流程只通过根目录的 `custodian.py`；所有正式
时间由程序自动记录为带时区 UTC，不允许在正式命令中手工回填时间。

## 2. 固定工作目录

把整个审查包原样放到保管人独立控制的电脑或账户，例如：

`D:\M3_Blind_Custodian_Python_v3`

下文每条命令都在这个目录运行。正确目录必须同时看到：

- `README.md`
- `custodian.py`
- `review_manifest_v3.json`
- `review_package_config.json`
- `requirements-review.txt`
- `review_source`
- `schemas`
- `tests`
- `work`

不要进入子目录后运行命令。不要把项目仓库的 `.env`、API key 或历史输出复制
进来。

### 2.1 运行位置只有一个

打开终端后先执行：

```text
cd /d D:\M3_Blind_Custodian_Python_v3
```

PowerShell 中也可以执行：

```text
Set-Location -LiteralPath 'D:\M3_Blind_Custodian_Python_v3'
```

之后本手册中每条 `custodian.py` 命令都必须在这个包根目录运行。不要在 M3-PI
Guard 项目仓库运行，也不要在 `work`、`review_source`、`tests` 或 `scripts`
子目录运行。命令里的 `<CUSTODIAN_ID>` 等尖括号文本是说明占位符，实际执行时
必须替换，不能连同尖括号原样提交。

### 2.2 文件保管与交付总表

| 文件或目录 | 谁保管 | 是否交开发者 | 用途 |
|---|---|---:|---|
| 整个原始 v3 包及 `review_manifest_v3.json` | 保管人 | 可只读共享 | 证明审查源码、模板和哈希起点 |
| `work/private/registration` | 保管人 | 否 | 真人身份声明；不得装入开发者包 |
| `work/private/authored_pairs` | 保管人 | 否 | 600 条候选与标签配对的原始私有稿 |
| `work/private/labels` | 保管人 | 否 | 独立标签；模型执行结束前绝不解封给评分流程 |
| `work/private/scoring` | 保管人 | 否 | 私下逐行评分工作态 |
| `work/private/audit_bundle_v3` | 保管人/隔离复核人 | **绝对否** | 含标签，可重放工件、哈希和签名链；不自动重算人工评分语义 |
| `work/generated/release/scoring_release_v3` | 程序原子生成 | 是，仅随终态包 | exact-schema 3,600 行评分副本及绑定 seal；不含标签 |
| 包外 Ed25519 私钥或硬件 signer | 保管人/组织 signer | **绝对否** | 三个阶段的密码学签名 |
| `work/handoff/execution_only_v3` | 保管人生成 | 是，只交此目录 | 首次交付的无标签执行集 |
| `work/handoff/developer_evidence_v3` | 保管人生成 | 是，只交此目录 | 登记、custody、签名及审查祖先 |
| `work/incoming_from_developer` 中固定六项 | 开发者返回、保管人复验 | 已是双方证据 | 完整 3,600 行输出及 effect/provider 请求链 |
| `work/handoff/developer_safe_final_v3` | 保管人生成 | 是，只交此目录 | 不含标签的最终签名证据包 |
| 外部 signing request/signature 文件 | 保管人/外部 signer | 按组织规则 | 私钥盲签名中转；不得替代包内验签 |

保管人应保留整个工作目录的只读备份、包外签名系统的审计凭据和文件交接记录；但
最终交给开发者时只交表中明确标为“是”的目录。不要凭人工复制单个散文件来拼包。

## 3. 第一次验包与 Python 环境

在产生任何工作文件前，用可信 Python 3.13 验证初始包：

```text
py -3.13 -B .\custodian.py verify-pristine
```

必须返回 `review_package_verified`。该检查只枚举代码中固定的不可变目录和初始
空目录结构，不读取私有文件正文，也不信任 manifest 自己提供的读取路径。

然后在被忽略的 `work/runtime` 创建虚拟环境：

```text
py -3.13 -m venv .\work\runtime\venv
```

不要 activate，不要 `setx`，不要创建任何用户或系统环境变量。此后直接调用：

```text
.\work\runtime\venv\Scripts\python.exe -B -m pip install --no-index --find-links D:\trusted-wheelhouse -r .\requirements-review.txt
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py verify
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py self-test --with-pytest
```

wheelhouse 必须由保管人信任的渠道准备。创建虚拟环境后，`verify-pristine` 会因
`work/runtime` 不再为空而按设计失败；日常使用 `verify`。

以后可随时执行：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py status
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py show-next
```

这两个命令不是单纯看“文件是否存在”，而会重放已经完成的前序验证链。已有工件
无效时会停止，不会建议继续下一步。

### 3.1 每次操作前后的固定检查

每天开始工作、接收开发者文件后、签名前以及交付最终包前，都运行：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py verify
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py status
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py show-next
```

只执行 `show-next` 指出的下一阶段。不要因为“目标文件看起来存在”就跳过 replay。
`verify` 或 replay 失败后，不要修改 manifest、config 或源码来继续。

## 4. 文件夹职责与保管边界

### 4.1 不可变审查区

- `review_source`：core、接口、冻结槽位、模板和审查源；不能修改。
- `schemas`：review config/manifest schema；不能修改。
- `tests`：包内自检；不能修改。
- `review_manifest_v3.json`：逐文件 SHA-256、core/CLI/config 绑定；不能修改。

`review_source` 内的 v1 `README.md` 只是为了复验历史 hash lock 而原样保留的证据，
不是当前操作说明。整个 v3 包唯一权威的操作入口是包根目录本文件；不得按照历史
README 执行当前流程。

### 4.2 保管人私有区：永远不交开发者

- `work/private/registration/offline_identity_attestation.txt`
- `work/private/authored_pairs/authored_pairs.jsonl`
- `work/private/labels/blind_labels_v2.jsonl`
- `work/private/scoring/scoring_results_v2.jsonl` 的评分工作态
- `work/private/audit_bundle_v3`：含标签、可全链复算的私有审计包
- 包外 Ed25519 私钥或硬件 signer

`work/private/audit_bundle_v3` 只能由保管人或另一个隔离的独立审查者访问。自动
verifier 可以重放工件、哈希、时序和签名链，但不会、也不能替代人工判断来重算逐
案例 `unsafe_effect`。若要第二人复核逐案例语义，必须由隔离的独立审查者在这个
权限域中人工复核；绝不能把该目录交给开发者。

### 4.3 可以按阶段交开发者的目录

- `work/handoff/execution_only_v3`：仅无标签 execution set、release receipt 和
  逐文件 manifest；
- `work/handoff/developer_evidence_v3`：登记、pre-release、custody、签名和审查
  源祖先，不含标签；
- `work/handoff/developer_safe_final_v3`：签署后的结果及完整来源/哈希证据，不含
  标签和 authored pairs。

开发者安全终态包能复验来源、请求链、哈希、时序和保管人签名，但因为没有私有
标签，不能独立复算逐案例评分语义。不能把它描述为“完整评分语义可复算包”。

## 5. 外部签名：私钥盲主流程

正式默认使用组织批准的包外或硬件 Ed25519 signer。私钥从不进入本包、config、
manifest、命令行或环境变量。先由外部 signer 生成密钥，并把 Ed25519 公钥 PEM
放在本包外，例如 `D:\M3_Signer\custodian_public.pem`，然后登记公钥：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py register-public-key --public-key D:\M3_Signer\custodian_public.pem
```

每个签名阶段都遵循同一三步：

1. `export-signing-request` 把待签 raw SHA-256 digest、阶段和公钥指纹输出到包外；
2. 用批准的外部 signer 对 **32 字节 raw digest** 做 Ed25519 签名，输出 64 字节
   signature 的单行 canonical base64；
3. `import-detached-signature` 会用登记公钥先做数学验签，再写入包内签名工件。

示例（registration 阶段）：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py export-signing-request --stage registration --output D:\M3_Signer\registration_request.json
<使用组织批准的外部或硬件 signer，产生 D:\M3_Signer\registration_signature.txt>
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py import-detached-signature --stage registration --signature-file D:\M3_Signer\registration_signature.txt
```

若没有外部 signer，可使用同一 `custodian.py` 的明确本地备选，但只接受包外、已
加密的 Ed25519 PKCS#8 PEM；口令只能由 `getpass` 交互输入，不接受命令行、配置或
环境变量，也拒绝未加密私钥：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py sign-request --stage registration --request D:\M3_Signer\registration_request.json --encrypted-private-key D:\M3_Signer\custodian_encrypted_private.pem --signature-out D:\M3_Signer\registration_signature.txt
```

本包不提供明文 keygen。签名数学有效只证明相同私钥控制权，不证明真人姓名或
独立性；真人身份仍需线下核验。

## 6. Day 1：登记保管人

生成私有身份声明模板：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py prepare-identity-template
```

打开 `work/private/registration/offline_identity_attestation.txt`，删除所有尖括号
占位符并如实填写。不要写身份证号、API key、密码或其他高敏感信息。

构建零标签登记：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py registration-build --custodian-id <保管人稳定身份> --project-relationship <真实项目关系>
```

按第 5 节以 `--stage registration` 导出、签署并导入 detached signature，然后：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py registration-finalize
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py registration-verify --verifier-id <不同于保管人的真人验签人稳定身份>
```

`verifier_id` 必须与 `custodian_id` 不同。状态必须为
`custodian_registration_verified_clock_may_start`。

Day 1 通过的最低交付不是一句口头确认，而是以下工件均存在且可重放：

- `work/generated/release/custodian_public_key.pem`
- `work/private/registration/offline_identity_attestation.txt`（仍留在私有区）
- `work/generated/release/custodian_registration_v2.json`
- `work/generated/receipts/custodian_registration_verifier_receipt_v2.json`

其中只可把登记 JSON、验签回执和公钥放进后续开发者证据包；身份声明正文不交。

## 7. 私下编写、拆分并封存 600 条

保管人在隔离环境创建：

`work/private/authored_pairs/authored_pairs.jsonl`

依据以下不可变材料逐行编写：

- 冻结槽位：
  `review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/slots.jsonl`
- pair/case/execution/label 模板：
  `review_source/protocols/paper_upgrade_v2/independent_blind_authoring_kit_v2`

必须严格按槽位顺序、每行一个 JSON、恰好 600 行：360 attack、120
benign-tool、120 benign-no-tool，两个作者批次各 300。不得包含真实 credential、
生产标识或可触发真实外部效果的数据。

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py split
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py validate-pre-release
```

第二条必须返回 `custodian_pre_release_passed`。程序自动生成并绑定 authoring/split
UTC 时序、无标签 execution set、私有 labels 和回执；所有终态拒绝覆盖。

## 8. 只交无标签执行集并完成 custody

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py stage-execution-set
```

只把 `work/handoff/execution_only_v3` 整目录交开发者。开发者明确确认收到后：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py record-developer-receipt --receiver-id <开发者接收人稳定身份>
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py custody-build
```

按第 5 节以 `--stage custody` 导出、签署并导入 detached signature，然后：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py custody-finalize
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py custody-verify --verifier-id <不同于保管人的真人验签人稳定身份>
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py stage-developer-handoff
```

只把 `work/handoff/developer_evidence_v3` 整目录补交开发者。程序在 staging 前重放
登记、pre-release、时序、custody 和签名，不只看一个 `status` 字段。

## 9. 收到 3,600 条结果后，先复验再解封标签

开发者必须原样返回六项到固定目录：

1. `work/incoming_from_developer/execution_admission_v2.json`
2. `work/incoming_from_developer/execution_output_seal_v2.json`
3. `work/incoming_from_developer/output_package_v2.jsonl`（完整 3,600 行）
4. `work/incoming_from_developer/effect_receipt_bundle_v2.jsonl`（完整 3,600 行）
5. `work/incoming_from_developer/provider_trace_receipt_bundle_v2.jsonl`（完整
   3,600 行）
6. `work/incoming_from_developer/provider_request_chain_bundle_v2.jsonl`（每次
   provider 调用的 started/terminal append-only 事件；零调用项须由第 5 项明确
   说明零调用原因）

不能只给截图、汇总数字或一个自哈希 seal。output package 中的 content-free trace
必须绑定完整请求链：调用前 local request ID、canonical payload hash、官方 response
ID、精确返回模型、usage，以及 append-only previous/entry chain。DeepSeek 正式证据
必须是 `official_api`、`api.deepseek.com` 和冻结的 exact provider/model；汇总必须
分别记录 input/output/cache-hit/cache-miss tokens 与 CNY 成本。自由字符串只能是
短 opaque ID 或枚举，不能承载 prompt、label、gold 或回答正文。摘要 receipt 不能
冒充完整请求链。

六项齐全后，先运行 `status`；它应指向标签释放步骤。然后运行：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py release-labels-for-scoring --output-package .\work\incoming_from_developer\output_package_v2.jsonl
```

`--output-package` 必填且只能指向固定文件。core 会在打开私有 labels 前从冻结
execution set、admission、完整 3,600 行 output package、3,600 行隔离 effect
receipts、3,600 行 provider 汇总 receipts、逐调用 request chain 和 output seal
重建验证；缺行、重复 work key、真实外部 effect、开放 attempt、自动重试、
trace/provider/model/usage/cost/chain 漂移、哈希或时序不符都会拒绝标签释放。成功只
表示标签可进入保管人本地评分进程，仍不能交开发者。

所有 seal、receipt、diagnostics、evidence boundary 和 scoring binding 的嵌套对象也
必须是 exact schema；即使攻击者重新计算自哈希并重新签名，额外插入
`gold_label`、`label`、`score` 等字段仍必须被拒绝。request chain 中 `completed`
terminal 只能对应成功类运行状态；`provider_failure` 等失败状态必须对应 `failed`
terminal，不能借一个有官方 response ID 的 completed 事件伪装失败并绕过 ITT。

## 10. 私下评分、签署和双包终态

结合已复验 output package 和私有 labels，创建恰好 3,600 行：

`work/private/scoring/scoring_results_v2.jsonl`

必须保留 timeout、parse failure、refusal、max-steps 和 provider failure，不得因
结果不利选择性删除。然后：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py seal-scoring-results
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py scoring-attestation-build
```

`seal-scoring-results` 只在私有评分原件通过 exact schema 和 3,600 行校验后，原子
创建 `work/generated/release/scoring_release_v3`。该目录严格只含
`scoring_results_v2.jsonl` 与 `custodian_scoring_result_seal_v2.json` 两项；A 路径
会核对私有原件与 release 副本哈希相同，B 路径只读取 release 副本。

按第 5 节以 `--stage scoring` 导出、签署并导入 detached signature，然后：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py scoring-attestation-finalize
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py scoring-attestation-verify --verifier-id <不同于保管人的真人验签人稳定身份>
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py stage-private-audit
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py scoring-attestation-verify-integrity-only --verifier-id <不同于保管人的真人验签人稳定身份>
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py stage-developer-safe-final
```

两项 staging 的边界必须分清：

- A：`custodian_private_artifact_full_replay`，对应
  `work/private/audit_bundle_v3`。它含 labels/authored pairs，可完整重放工件、哈希、
  时序和签名链，但自动 verifier 不重算人工评分语义；只能私有留存或交另一个隔离
  审查者，绝不交开发者；
- B：`developer_safe_signature_integrity_only`，对应
  `work/handoff/developer_safe_final_v3`。它不含 labels/authored pairs，只交开发者，
  只能验证来源、请求链哈希、签名和已签评分的完整性，既不开 labels，也不能独立
  重算逐案例语义。

两种 verifier 均明确 `semantic_recomputation=false`。A 的评分语义由保管人签名
attest，必要时由另一个隔离人工审查者复核；B 不能借由签名有效推导人工评分正确。
B verifier 的函数参数和固定输入全部指向 `work/generated/release`、
`work/generated/receipts` 或其他公开 release 工件；它不接受 label、private scoring
原件、output content 或任意目录参数，也不枚举 `work/private`。

## 11. 失败、封存和绝对禁止

- 任一命令返回 `command_rejected`：停止，保存 stdout/stderr 和整个目录。
- 不修改 core、CLI、config、schema、slots 或 manifest 来绕过失败。
- 不删除、覆盖或重试已终态工件；需要重做时封存旧目录并领取新的空包身份。
- 不因结果好坏更改样本、阈值、排除规则或冻结条件。
- 不把私钥、labels、authored pairs、身份声明或私有审计包交开发者。
- 不使用 `.env`、命令行参数或环境变量传私钥口令。
- 不执行真实邮件、支付、浏览器、生产 API 或其他外部效果。
- 不把 self-hash、签名数学有效或开发者安全包夸称为真人身份、独立性或评分语义
  已由开发者独立复算。

最后运行：

```text
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py verify
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py status
.\work\runtime\venv\Scripts\python.exe -B .\custodian.py show-next
```

`verify` 必须通过，`show-next` 必须返回 `custodian_workflow_complete`。这只说明证据
流程完成；正面或负面结果都可以结项，不能为了得到有利结果改写封存证据。

## 12. 全流程命令核对表

以下顺序用于人工核对；权威下一步仍以 `show-next` 的 replay 结果为准。全部命令
都在 `D:\M3_Blind_Custodian_Python_v3` 包根目录运行。

| 顺序 | 操作或命令 | 主要终态工件 |
|---:|---|---|
| 1 | `py -3.13 -B .\custodian.py verify-pristine` | 初始包完整性通过 |
| 2 | 创建 venv、安装离线依赖、`custodian.py verify` | 本地执行环境合格 |
| 3 | `register-public-key --public-key <包外绝对路径>` | `custodian_public_key.pem` |
| 4 | `prepare-identity-template`，线下填写身份声明 | 私有身份声明 |
| 5 | `registration-build ...` | unsigned registration |
| 6 | export → 外部签名 → import，stage=`registration` | registration detached signature |
| 7 | `registration-finalize` | signed registration |
| 8 | `registration-verify --verifier-id <不同真人>` | registration verifier receipt |
| 9 | 私下创建恰好 600 行 `authored_pairs.jsonl` | 私有 authored pairs |
| 10 | `split` | 600 行 execution、600 行 labels、split receipts |
| 11 | `validate-pre-release` | pre-release receipt |
| 12 | `stage-execution-set` | `execution_only_v3` |
| 13 | 开发者确认后 `record-developer-receipt ...` | developer receipt |
| 14 | `custody-build` | unsigned custody |
| 15 | export → 外部签名 → import，stage=`custody` | custody detached signature |
| 16 | `custody-finalize`、`custody-verify ...` | signed custody 与验签回执 |
| 17 | `stage-developer-handoff` | `developer_evidence_v3` |
| 18 | 接收并固定六项开发者返回证据 | `incoming_from_developer` 六项齐全 |
| 19 | `release-labels-for-scoring --output-package <固定路径>` | label release seal |
| 20 | 私下创建恰好 3,600 行 `scoring_results_v2.jsonl` | 私有评分结果 |
| 21 | `seal-scoring-results` | 原子的两文件 `scoring_release_v3` |
| 22 | `scoring-attestation-build` | unsigned scoring attestation |
| 23 | export → 外部签名 → import，stage=`scoring` | scoring detached signature |
| 24 | `scoring-attestation-finalize`、`scoring-attestation-verify ...` | 最终签名及验签回执 |
| 25 | `stage-private-audit` | 私有工件全链审计包；不自动重算语义；不得交开发者 |
| 26 | `scoring-attestation-verify-integrity-only ...` | B 路径无标签完整性回执 |
| 27 | `stage-developer-safe-final` | 可交开发者的无标签终态包 |
| 28 | `verify`、`status`、`show-next` | `custodian_workflow_complete` |

## 13. 交付前最后检查

交付 `work/handoff/developer_safe_final_v3` 前逐项确认：

- 没有 `.env`、API key、密码、私钥、明文 prompt/response 正文；
- 没有 `blind_labels_v2.jsonl`、`authored_pairs.jsonl`、身份声明或
  `audit_bundle_v3`；
- 包内 manifest 的文件集合与实际集合严格相等，不是“只校验已列文件”；
- effect receipts 明确 `real_external_effect_count=0`，provider tools 和外部连接关闭；
- provider 请求链没有 open attempt、自动重试或模型身份漂移；
- timeout、parse failure、refusal、max-steps、provider failure 均留在 ITT 分母；
- `verifier_id` 与 `custodian_id` 不同，三次 detached signature 均通过数学验签；
- 开发者安全包没有标签，因此只声明“签名与来源链可验证”，不声明“开发者可独立
  重算逐案例评分语义”。
