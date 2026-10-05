# REJECTED DIAGNOSTIC — DO NOT USE

此目录是被拒绝的诊断快照，禁止作为保管人审查包交付或运行。

该快照的可移植性测试源码包含本机检出路径字面量。当前修正和本标记均不在原
manifest 中，因此该目录会按设计产生文件集合及哈希失配，`verify-pristine` 和
`verify` 必须拒绝。不得重算或修改旧 manifest 来恢复使用。

请改用更新、重新生成且通过完整验收的审查包。
