# M3-PI Guard 独立盲测保管人工具包 v2（Ed25519 完整链）

## 1. 工作目录与边界

把整个目录放在保管人独立控制的电脑或账户，例如：

```powershell
Set-Location -LiteralPath 'D:\M3_Blind_Custodian_v2'
```

这一级必须能看到 `experiments`、`protocols`、`private`、`release`、
`incoming_from_developer`、`receipts`、`signatures`、`scripts`。下文所有脚本都
从此根目录运行。工具包初始状态不含真实样本、标签、身份、签名、密钥、API
配置或结果；脚本不联网，也不调用任何模型或外部效果工具。

每条命令的工作目录固定如下，运行前都应先执行本节的 `Set-Location`：

| 命令 | 固定工作目录 |
|---|---|
| Python 依赖检查/离线安装 | 工具包根目录 |
| OpenSSL 生成私钥、导出公钥 | 工具包根目录（私钥输出路径必须指向根目录外） |
| `00` 至 `11` 的登记、拆分、封存、验签、首次 staging | 工具包根目录 |
| `12` 至 `18` 的标签释放、评分封存、签名验算、最终 staging | 工具包根目录 |

不要进入 `scripts`、`private` 或 `release` 后运行命令；文中的相对路径全部以
工具包根目录为基准。

Python 必须可导入 `cryptography`。离线环境若缺失，只能从可信 wheelhouse 安装：

```powershell
python -m pip install --no-index --find-links 'D:\trusted-wheelhouse' -r '.\requirements-custodian.txt'
```

## 2. 必须长期保管什么

始终不交开发者：

- `private\registration\offline_identity_attestation.txt`；
- `private\authored_pairs\authored_pairs.jsonl`（600 个私有 pair）；
- `private\labels\blind_labels_v2.jsonl`（600 个私有标签）；
- 工具包外部的 Ed25519 私钥；
- `receipts\split_receipt_v2.json` 和 `signatures` 中的待签名/签名过程文件。

执行前先把 verifier/pre-release 回执写入 `receipts`，验证通过后由固定 staging
脚本单向复制到 `release\developer_handoff_v2`。只把这个目录交开发者；它
必须包含且仅包含以下公开证据（另有一个逐文件 SHA-256 清单）：

1. `blind_execution_v2.jsonl`；
2. `blind_custody_v2.json`；
3. `pre_release_review_v2.json`；
4. `custodian_registration_v2.json`；
5. `custodian_registration_verifier_receipt_v2.json`；
6. `custody_signature_verifier_receipt_v2.json`；
7. `custodian_public_key.pem`；
8. 根目录 `toolkit_manifest_v2.json`。

标签文件绝不能进入 release、开发仓库、邮件附件或共享盘。Ed25519 私钥必须
保存在工具包根目录之外；脚本只把外部私钥路径传给本机 OpenSSL，不复制、
不记录私钥路径或密钥内容。

## 3. Day-1：登记真实保管人（零标签）

### 3.1 验证初始包

```powershell
& '.\scripts\00_VERIFY_PRISTINE_TOOLKIT.ps1' -PythonExe 'python'
```

必须出现 `toolkit_verified`，且 closeout 模块 help 正常。

### 3.2 在工具包外生成 Ed25519 私钥并导出公钥

以下私钥目录只是示例，必须由保管人独占且位于工具包外：

```powershell
New-Item -ItemType Directory -Path 'D:\M3_Custodian_PrivateKey' -ErrorAction Stop
openssl genpkey -algorithm ED25519 -out 'D:\M3_Custodian_PrivateKey\custodian_ed25519_private.pem'
openssl pkey -in 'D:\M3_Custodian_PrivateKey\custodian_ed25519_private.pem' -pubout -out '.\release\custodian_public_key.pem'
```

不得把私钥复制进工具包。把
`templates\offline_identity_attestation_template.txt` 复制为
`private\registration\offline_identity_attestation.txt`，由真人填写并删除所有
占位符。不要写身份证号、API key 等高敏感信息。

### 3.3 构建、签名、完成并验算登记

```powershell
& '.\scripts\01_BUILD_UNSIGNED_REGISTRATION.ps1' -PythonExe 'python' `
  -CustodianId '真实姓名或登记的稳定身份' `
  -ProjectRelationship '与项目的真实关系' `
  -ConfirmedAt '2026-08-03T09:00:00+08:00'

& '.\scripts\02_SIGN_REGISTRATION.ps1' -OpenSSLExe 'openssl' `
  -PrivateKeyPath 'D:\M3_Custodian_PrivateKey\custodian_ed25519_private.pem'

& '.\scripts\03_FINALIZE_REGISTRATION.ps1' -PythonExe 'python'

& '.\scripts\04_VERIFY_REGISTRATION.ps1' -PythonExe 'python' `
  -VerifierId '真实验签人稳定身份' `
  -VerifiedAt '2026-08-03T09:20:00+08:00'
```

所有示例时间必须换成真实、带时区且顺序正确的时间。最后 receipt 状态必须为
`custodian_registration_verified_clock_may_start`。数学验签只证明公钥控制权；
真人身份仍由线下核验声明负责，不能夸称密码学证明了真实姓名。

## 4. 编写与封存 600 条

### 4.1 编写

逐行参考 v2 `authored_pair_template.json`，严格按 v1 `slots.jsonl` 顺序写入：

`private\authored_pairs\authored_pairs.jsonl`

必须恰好 600 行：attack 360、benign_legal_tool 120、benign_no_tool 120；作者组
300/300。不得含真实 credential、生产标识或可触发真实外部效果的数据。

### 4.2 拆分和保管人侧检查

```powershell
& '.\scripts\05_SPLIT_PRIVATE.ps1' -PythonExe 'python'
& '.\scripts\06_VALIDATE_PRE_RELEASE.ps1' -PythonExe 'python'
```

第二条必须返回 `custodian_pre_release_passed`。两条命令会读取私有 label，因此
只能在保管人环境运行；所有输出均拒绝覆盖。

### 4.3 构建并签署 custody

```powershell
& '.\scripts\07_BUILD_UNSIGNED_CUSTODY.ps1' -PythonExe 'python' `
  -AuthoringCompletedAt '2026-08-05T10:00:00+08:00' `
  -SplitCompletedAt '2026-08-05T10:10:00+08:00' `
  -SealedAt '2026-08-05T10:20:00+08:00' `
  -ExecutionReleasedAt '2026-08-05T10:30:00+08:00' `
  -DeveloperReceivedAt '2026-08-05T10:40:00+08:00'

& '.\scripts\08_SIGN_CUSTODY.ps1' -OpenSSLExe 'openssl' `
  -PrivateKeyPath 'D:\M3_Custodian_PrivateKey\custodian_ed25519_private.pem'

& '.\scripts\09_FINALIZE_CUSTODY.ps1' -PythonExe 'python'

& '.\scripts\10_VERIFY_CUSTODY_SIGNATURE.ps1' -PythonExe 'python' `
  -VerifierId '真实验签人稳定身份' `
  -VerifiedAt '2026-08-05T10:50:00+08:00'
```

最后状态必须为 `custody_signature_cryptographically_verified`。此时还不能手工
挑文件发送。仍在工具包根目录运行固定白名单 staging：

```powershell
& '.\scripts\11_STAGE_DEVELOPER_HANDOFF.ps1'
```

脚本从 `receipts` 与公开工作文件复制八项证据到
`release\developer_handoff_v2`，生成逐文件 SHA-256 清单，并拒绝 label JSONL、
authored pair 和 private key。只移交该完整目录；继续独占全部 private、
receipts、signatures 和外部私钥。

## 5. 开发者完成 3,600 条后，保管人评分

在收到开发者返回文件前不执行本节。先把以下两项放入固定目录：

- `incoming_from_developer\execution_output_seal_v2.json`；
- `incoming_from_developer\output_package_v2.jsonl`（3,600 行、内容无关引用）。

确认 output seal 表明完整执行已发生后，才运行：

```powershell
& '.\scripts\12_RELEASE_LABELS_FOR_SCORING.ps1' -PythonExe 'python' `
  -ReleasedAt '2026-08-20T10:00:00+08:00'
```

这只允许标签进入保管人评分进程，不允许交开发者。参考
`templates\scoring_entry_template.json`，结合私有标签与 output package 产生恰好
3,600 行 `private\scoring\scoring_results_v2.jsonl`，然后运行：

```powershell
& '.\scripts\13_SEAL_SCORING_RESULTS.ps1' -PythonExe 'python' `
  -ScoredAt '2026-08-21T10:00:00+08:00'
```

评分 seal 还不是最终签名证据。使用与登记/custody 相同的外部 Ed25519 私钥，
按顺序构建、签名、完成和由具名 verifier 数学复核结果 manifest：

```powershell
& '.\scripts\14_BUILD_UNSIGNED_SCORING_ATTESTATION.ps1' -PythonExe 'python' `
  -SignedAt '2026-08-21T10:10:00+08:00'

& '.\scripts\15_SIGN_SCORING_ATTESTATION.ps1' -OpenSSLExe 'openssl' `
  -PrivateKeyPath 'D:\M3_Custodian_PrivateKey\custodian_ed25519_private.pem'

& '.\scripts\16_FINALIZE_SCORING_ATTESTATION.ps1' -PythonExe 'python'

& '.\scripts\17_VERIFY_SCORING_ATTESTATION.ps1' -PythonExe 'python' `
  -VerifierId '真实验签人稳定身份' `
  -VerifiedAt '2026-08-21T10:20:00+08:00'
```

receipt 状态必须为 `custodian_scoring_result_signature_verified`。随后仍从工具包
根目录执行：

```powershell
& '.\scripts\18_STAGE_SCORING_HANDOFF.ps1'
```

它只把 `scoring_results_v2.jsonl`、`label_release_seal_v2.json`、结果 seal、
已签署 scoring attestation、验签 receipt 及逐文件 SHA-256 清单放入
`release\scoring_handoff_v2`。只交该目录；仍不交私有 label JSONL。

## 6. 绝对禁止

- 不修改冻结 `slots.jsonl`、历史 v1 文件或任何已终态输出；
- 不把 `.env`、API key、签名私钥、密码、真实隐私或生产凭据放进工具包；
- 不允许开发者在执行完成前看到 label、规则、答案或案例级判定；
- 不执行真实邮件、支付、浏览器、生产 API 或任何真实外部效果；
- 不因结果好坏删除、改写或重跑终态记录；
- 不把字段完整性检查冒充 Ed25519 数学验签，也不把公钥控制权冒充真人身份。
