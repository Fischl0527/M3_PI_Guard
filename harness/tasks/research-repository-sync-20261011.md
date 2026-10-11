# 独立科研仓库同步

## 目标、范围与非目标

- 用户授权使用已有 `Fischl0527/M3_PI_Guard`，将当前研究同步过去；不是创建新仓库、重新初始化项目或删除比赛来源。
- 当前 HEAD `619cf24`，目标研究分支 `codex/q2-empirical-study` 原 tip `0c7a905`；真实祖先检查为0/76，可正常快进。
- 同步完整当前已提交树与历史，以及已验证主手册/旧文快照、本次入口/工作流及必要 Harness。
- 允许本轮修改：根 README、docs/README、harness/config/workflow、功能/当前任务/进度/历史/移交/决策，以及本任务记录。
- 上轮主手册、旧文快照、单篇手册任务与相关失败记录可一并交付；旧失败记录不删。
- 排除：用户正在搬移的参考论文与Obsidian配置、字体、模板杂项、未验证旧端点代码/测试、子模块dirty、生成预览/XML、默认demo删除、模型/环境、内部API日志、凭据及保管备份。它们在本地原样保留，不通过本轮推送伪称已验证。
- 不做API、软件或研究重跑、Full Harness、LaTeX编译、依赖安装、旧PR变更、朋友仓库操作、许可证或作者变更。

## 保护与执行计划

1. 核对远端非fork/私有/默认分支和正常快进关系。
2. 更新当前入口与Git工作流，保留原团队来源。
3. 使用明确文件清单核对暂存范围、静态链接、JSON及新增大文件；当前用户17条PDF暂存搬移不纳入提交。
4. 正常提交和推送当前版本到独立仓库研究分支及开发同名分支；不强推、不镜像所有refs。
5. 旧个人比赛remote保留为`competition-origin`，`origin`改指独立科研仓库，`m3-guard`兼容别名保留；当前分支跟踪独立仓库同名分支。
6. 核对远端commit、默认分支和本地upstream；更新功能为verified，范围提交一次交付回执并推送，不递归登记自身提交。

## 验收与验证

- 两个远端研究分支与发布commit一致，默认分支仍q2，仓库仍独立私有。
- 原用户暂存PDF路径/blob不变，进行中的工作文件不改写，范围不包含秘密、内部trace或临时产物。
- 已验证手册及原文快照同步；入口相对链接、feature JSON及活动范围空白检查通过。
- 当前科研完成度不因Git交付提高，F-PAPER-002不变。

## 实际命令与回执

- 元数据：`gh api repos/Fischl0527/M3_PI_Guard`确认非fork/私有、默认q2、当前账号有管理权限；`git fetch --no-tags m3-guard`成功。
- `git rev-list --left-right --count m3-guard/codex/q2-empirical-study...HEAD`输出0/76；`git merge-base --is-ancestor ... HEAD`exit0。没有强推需求。
- 静态校验首次失败仅为旧文快照多两个EOF换行，诊断正文归一化一致；采用原文快照的既有归一化定义，不改归档。
- 后续暂存、提交、推送及远端核对待执行，不以计划代替成功。

本地三入口静态检查通过：72个本地链接、feature JSON和旧文归一化保存均通过。提交树检查进一步发现1个仅本地生成包链接，将它改为路径说明；后续按Git索引中的实际文件验证，而不是用本地文件存在冒充GitHub可访问。临时独立index基于HEAD，只加入14个明确文件，17条原用户PDF暂存不消费；current-task原有两段用户历史修改只保留本地，不混入本次提交。

修正后实际检查exit0：14个暂存文件与允许清单完全一致，三入口在实际提交树中的71个本地链接均存在，围栏/feature JSON通过，F-PAPER-002仍in_progress；旧文归一化一致、新文件均小于1MB。活动范围`git diff --cached --check`通过，原样归档不为格式警告改写。原索引`git diff --cached --raw --no-renames`前后逐字相同，17条用户PDF搬移仍在。

本轮不修改Python或科研执行逻辑，故不运行pytest/Ruff/编译或软件全量验收；Git交付成功不等于模型实验、完整论文或所有本地未提交工作已验收。

### 实际Git交付

- `git commit -m 'docs: establish independent research repository and publish Chinese manual'`在临时独立index中完成14文件提交`3cc6bd350575741561d60e53ebde4db406d220f9`；随后仅将允许文件的原index与HEAD对齐，用户17条PDF暂存前后raw逐字一致、current-task既有16行仍为未提交。
- `git push m3-guard HEAD:refs/heads/codex/q2-empirical-study HEAD:refs/heads/codex/claude-review-repairs`成功，q2正常快进、claude新分支创建。`git ls-remote`确认两者均为上述提交；没有force/mirror或历史改写。
- GitHub仅提示历史raw56.13MB与PDF53.33MB大于建议50MB，推送exit0；不进行LFS迁移、额外打包或重复研究哈希。
- `git remote rename origin competition-origin`、`git remote rename m3-guard origin`、`git remote add m3-guard https://github.com/Fischl0527/M3_PI_Guard.git`与`git branch --set-upstream-to=origin/codex/claude-review-repairs codex/claude-review-repairs`均成功；远程host/path与branch remote/merge核对正确，没有认证或GitHub权限变化。
- GitHub API再次确认仓库private=true/fork=false/default_branch=q2；F-GIT-002设verified，其他科研状态保持。该回执追加提交后正常推送一次，最终commit由Git及对话核对，不循环记录回执自身SHA。
