# paper-v2 独立盲测 authoring/ingest v2

本目录是零内容、零标签、零真实保管人数据的版本化接口包。它修复 v1
`case_template.json` 把 `offline_evaluation` 放入执行模板，以及 v1 custody
模板没有强制声明标签哈希和保管人签名的问题。v1 的全部文件保持历史不可变。

## 两侧边界

1. 独立作者/保管人在项目开发环境之外填写 `authored_pair_template.json` 的
   600 个私有 pair。每个 pair 的 `execution` 和 `label` 是两个独立对象。
2. 保管人运行 `independent_blind_closeout_v2.split_authored_bundle`，按冻结
   `slots.jsonl` 的精确顺序确定性地产生 execution JSONL 和 label JSONL。
3. 保管人运行 `validate_custodian_pre_release`。此接口会读取标签，只能在保管人
   环境运行；它不授权模型实验或结果准入。
4. 保管人计算双文件 SHA-256，填写 release chain，并对
   `custodian_signature_payload_sha256` 对应的 canonical payload 作外部签名。
5. 开发者只接收 execution JSONL 和 custody JSON。标签文件不得出现在开发者
   可见目录；`audit_developer_execution_import` 的函数签名不接受 label path。
6. 模型执行全部完成并提交 3,600 行内容无关 output package 后，标签才可由
   保管人侧评分流程使用。v2 会强制
   `execution complete -> custodian-only label release -> scoring seal` 的时间顺序；
   评分前开发者不得收到标签。

## 冻结槽位

v2 继续引用但不复制、不修改 v1 的 600 个空槽位：

`protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/slots.jsonl`

其 SHA-256 必须为
`4ec78a15bf87473d56d9c4a1bb59f6fadd0d8fed76adf66a567c5e794b79a0a8`，
分层必须为 attack 360、benign_legal_tool 120、benign_no_tool 120，作者组为
300/300。execution 行必须包含并匹配 `primary_authorization_regime`。

## 签名边界

本模块仅接受 `ed25519-detached-sha256-digest-v1`。签名对象是 manifest 中
payload SHA-256 对应的原始 32 字节，不是十六进制字符串。开发者 verifier 使用
`cryptography.Ed25519PublicKey.verify` 实际进行数学验签，并在 import 时再次验签；
手工写入 `verified=true` 不能授权执行。数学验签只能证明签名者控制对应私钥，
公钥是否属于登记的真实保管人仍由线下身份核验材料的 SHA-256 承诺证明。

## 运行目录与通用命令

所有模块命令均在仓库根目录运行。本机当前路径为：

```powershell
Set-Location 'E:\M3_PI_Guard_test'
$PY = 'F:\robot\Anaconda3\python.exe'
```

保管人的私有工作目录必须位于开发者不可访问的位置。私钥、
`authored-pairs.jsonl`、`blind-labels.jsonl` 和评分明细不得放进仓库。模块从不读取
私钥；签名须由保管人在外部通过 OpenSSL、硬件密钥或同等 Ed25519 工具完成。

可用 CLI 子命令和角色：

- `build-unsigned-registration`：保管人，第 1 天零标签登记；
- `finalize-registration`：保管人，把外部产生的 base64 签名装入登记；
- `verify-registration`：开发者/独立 verifier，数学验签；通过仅启动计时；
- `split`：保管人，600 对私有 pair 确定性分离；
- `validate-pre-release`：保管人，写出 600/600 双哈希 review；
- `build-unsigned-custody`、`finalize-custody`：保管人，生成并签署 custody；
- `verify-signature-receipt`：开发者/独立 verifier，实际验 custody 签名；
- `audit-import`：开发者，只读无标签 execution/custody/receipts/public key；
- `seal-execution-output`：开发者，执行后封存 3,600 行内容无关 output package；
- `release-labels-for-scoring`：保管人，仅在 execution seal 之后释放给评分进程；
- `seal-scoring-results`：保管人，绑定 output/label/scoring 三方哈希并封存结果。
- `build-unsigned-scoring-attestation`、`finalize-scoring-attestation`：保管人用同一
  登记 Ed25519 密钥签署最终 scoring result manifest；
- `verify-scoring-attestation`：仅在保管人私有环境执行；打开标签和私有评分原件，
  重放工件绑定并实际验最终结果签名；它不独立重算评分语义；
- `verify-scoring-integrity-only`：开发者/独立 verifier 仅使用公开 manifest、
  公钥和非私有 scoring release 验签与核验工件完整性；函数不接受标签、私有评分
  原件、execution 或 output path，也不枚举保管人目录。

查看每个子命令的精确参数：

```powershell
& $PY -m experiments.paper_v2.independent_blind_closeout_v2 --help
& $PY -m experiments.paper_v2.independent_blind_closeout_v2 audit-import --help
```

## Day-1 登记门

先用只有公钥和零标签信息的命令生成 unsigned registration。时间必须含时区，
线下身份材料只提交 SHA-256，不提交其内容：

```powershell
& $PY -m experiments.paper_v2.independent_blind_closeout_v2 build-unsigned-registration `
  --custodian-id '真实保管人ID' `
  --project-relationship '导师/未参与实现的同学/外部审查人' `
  --custodian-public-key 'D:\M3_blind_custodian\public\custodian-ed25519-public.pem' `
  --confirmed-at '2026-08-02T18:00:00+08:00' `
  --offline-identity-evidence-sha256 '<64位小写SHA-256>' `
  --write-unsigned 'D:\M3_blind_custodian\private\registration-unsigned.json'
```

保管人在外部签名，将 base64 签名保存为单行文件，再执行：

```powershell
& $PY -m experiments.paper_v2.independent_blind_closeout_v2 finalize-registration `
  --unsigned-registration 'D:\M3_blind_custodian\private\registration-unsigned.json' `
  --signature-base64-file 'D:\M3_blind_custodian\private\registration-signature.b64' `
  --write-registration 'D:\M3_blind_custodian\handoff\custodian-registration.json'
```

开发者收到 registration、公钥后运行实际验签：

```powershell
& $PY -m experiments.paper_v2.independent_blind_closeout_v2 verify-registration `
  --registration '.\blind_handoff\custodian-registration.json' `
  --custodian-public-key '.\blind_handoff\custodian-ed25519-public.pem' `
  --verifier-id 'developer-verifier-01' `
  --verified-at '2026-08-02T18:30:00+08:00' `
  --write-receipt '.\blind_handoff\registration-verifier-receipt.json'
```

只有 receipt 状态为 `custodian_registration_verified_clock_may_start` 且
`verifier_id` 与 `custodian_id` 不同，才表示**技术计时门**通过；该 receipt 明确保持
`execution_authorized=false`、`clock_start_is_technical_gate_only=true` 和
`offline_identity_not_cryptographically_proven=true`。真实姓名、单位关系和独立性仍须
由线下签署材料及其 SHA-256 保管链证明，不能由一个任意字符串或单方自签自动证明。

## 600 条封存和开发者准入

保管人运行 `split` 与 `validate-pre-release` 后，使用
`build-unsigned-custody`、外部签名和 `finalize-custody`。随后开发者先执行
`verify-signature-receipt`，再执行 `audit-import`。后者必须同时提供：execution、
custody、pre-release receipt、custody signature receipt、registration、registration
receipt 和 Ed25519 公钥。任何文件缺失、哈希漂移、字段泄漏或验签失败都会保持
`execution_authorized=false`。

执行完成封存还必须同时提供三类内容无关证据：3,600 行隔离 effect receipt、
3,600 行 provider trace summary，以及 append-only provider request chain。每个真实
provider 调用必须先有 `started` 事件（本地 request ID、canonical payload SHA-256、
带时区时间、pretransport fsync 承诺），再有引用该 started 哈希的 `completed` 或
`failed` 终态。`completed` 必须绑定官方 response ID 和精确
`deepseek-v4-pro`；超时/服务失败允许没有 response ID，但必须保留为 ITT 的
`timeout`、`provider_failure` 或 `diagnostic`。调用前即失败的条目用枚举化 zero-call
原因表示，严禁伪造 response ID。正式 blind 主模型固定
`endpoint_type=official_api`、`endpoint_host=api.deepseek.com`，并汇总缓存命中、
缓存未命中、输出 token 与 CNY 成本。标签解封前会用 registration、两个 verifier
receipt、pre-release receipt、custody、公钥和 execution set 重跑完整 import；提供的
admission 必须与重建对象逐字段一致，不能把自哈希 JSON 当成信任根。

终态还必须与 provider request chain 一致：`provider_failure` 只能由至少一个
`provider_failure` 或 `transport_failure` 的 failed terminal 支撑；`timeout` 必须由
timeout failed terminal（或精确映射的 zero-call timeout）支撑；completed-only 链只
允许 `completed`、`refusal`、`parse_failure`、`max_steps` 或 `diagnostic`。即使同步修改
output/effect/provider 三份 outer status 并重算所有绑定哈希，也不能把 completed 调用
伪装成 provider failure。

最终 `seal-scoring-results` 只是待签署的结果哈希封条，不构成“保管人已签署”的
证据。必须继续执行 `build-unsigned-scoring-attestation`，由保管人使用 Day-1
登记的同一 Ed25519 私钥在外部签名，再执行 `finalize-scoring-attestation`。

保管人私有环境随后运行 `verify-scoring-attestation`。它会打开 labels、私有
scoring 原件、execution/output 证据并重放全部工件绑定，同时校验非私有 scoring
release 与私有原件的 SHA-256 完全相同。只有 receipt 状态为
`custodian_scoring_result_artifact_full_replay_verified` 才表示该私有工件链和数学签名
通过。这里的 “full replay” 指工件、case 绑定和签名链重放，不表示本模块用另一套
确定性评分器独立重算评分语义；receipt 必须保持
`custodian_private_scoring_semantics_recomputed=false`，评分语义由独立保管人签名证明。

公开 handoff 必须包含由保管人工具**原子发布**的非私有 scoring release；其字节级
SHA-256 必须与保管人私有 scoring 原件及 scoring seal 中的哈希一致。开发者只运行
`verify-scoring-integrity-only`，且只把该公开 release 作为结果数据输入。状态
`developer_safe_scoring_signature_integrity_verified` 只证明签名、公开祖先链和发布
工件完整性；它明确保持 `private_label_payload_opened=false`、
`private_path_arguments_accepted=false`、`private_paths_enumerated=false` 和
`scoring_semantics_recomputed=false`。两个 receipt 均保持
`result_admission_authorized=false`，不能自行把结果提升为论文证据。

开发者安全 verifier 会对 scoring seal 的 `scoring_checks`、`chain_checks` 和
`execution_output_chain_checks` 使用冻结键集、布尔类型和全真值校验，并对 custody、
release chain、manifest、Ed25519 签名、时间顺序和未来时间限制重新核验。所有公开
manifest 都禁止 schema 外的递归敏感扩展；即使保管人私钥重新签名，嵌套的
`gold_label`、`answer_key`、`evaluator` 等字段也必须导致拒绝。

开发者目录禁止出现 `blind-labels.jsonl`；保管人必须长期保管：私钥、原始 600
pair、私有标签、pre-release review、两个 detached signature 原件、custody 原件、
label release seal、3,600 行评分明细及最终 scoring seal。

本目录不包含真实 candidate、label、custodian identity、signature 或科学结果。
