# 旧比赛材料归档与交接指南去重

- 日期：2026-10-06；关联F-DOC-001；本次归档子任务完成，整体功能仍in_progress。
- 用户要求：旧比赛内容移入E:\M3_PI_Guard_archive；比较根目录和docs中的《LLM的千层诱惑》，仅保留最新活动版本在docs。
- 已查明：两份指南正文相同，差异是docs副本提示、相对链接及链接标签；docs版本适合作为唯一入口，根目录旧副本移出仓库保存，不永久销毁。
- 用户确认D备份已手动迁移；本轮只核对D两源不存在、E两目标存在，不读取私钥、标签或宣称备份逐文件内容已核验。

## 范围与计划

1. 仅归档明确的比赛原始资料、作品报告、早期草稿、人工图素材、比赛报告/答辩资料、停用PPT构建脚本及旧发布包。
2. 目标为E:\M3_PI_Guard_archive\competition_history\M3_PI_Guard_test，按原相对目录保留结构。根目录交接指南旧副本单独放document_duplicates。
3. 当前产品/实验源码、fixtures/protocols/outputs证据、论文模板、相关参考论文、deepseek研究计划及release/archive中的盲测工具包原位保留，避免当前研究和测试依赖损坏。
4. 移动前核对每个明确源/目标绝对路径、目标不冲突、无目录联接；整包移动后比对相对文件名与大小。不生成哈希包、不读敏感内容，不覆盖目标，不终止占用进程。
5. docs指南去掉副本说明，根README和有效目录入口改为docs唯一入口。更新归档说明与必要路径测试；历史冻结记录和旧归档包内部文本不改写。
6. 只做相关目录/路径定向测试和链接检查，不API、Full Harness、论文编译或历史重算。更新现有Harness，只提交本轮改动并推送当前新分支，保留其他dirty工作。

## 验收

- 原路径比赛材料已移出，归档文件名/大小一致；冲突或占用明确记录，不假称完成。
- 活动《LLM的千层诱惑》仅docs一份，内容和链接保留，根旧副本可从归档找回。
- 当前科研/论文/冻结输入/结果不移动或重算，相关检查通过。
- D备份状态记录更新为用户迁移、位置已核对，而不是继续误报未搬迁。

## 执行与验证

- 16个明确迁移根、299文件、38,812,720字节已通过PowerShell原生Move-Item迁入competition_history/M3_PI_Guard_test。每项先验证绝对源/目标及目标不存在、无ReparsePoint，再比较迁移前后的相对名称、类型和大小；全部一致，源路径已消失。未生成哈希包。
- 收口引用检查发现scripts/make_release_package.ps1是无活动引用的旧DAY6比赛打包脚本，会重新创建刚归档的v1.0包；补充整文件归档，未执行，6,114字节迁移后一致。前三项数量包括该补充。
- 两份指南规范化正文一致：只存在副本提示和相对链接/标签差异。docs版本为唯一入口；根旧副本52,653字节保存在外部document_duplicates，不永久删除。
- 用户搬迁的D两备份源不存在、E两目标存在；这是位置核对，不是备份完整性或私钥/标签内容审计。
- 定向pytest命令：`F:\robot\Anaconda3\python.exe -B -X utf8 -m pytest -q --basetemp=harness/tmp/pytest-competition-archive tests/unit/test_documentation_artifact_paths.py tests/unit/test_repository_layout.py::test_harness_engineering_is_separate_from_project_source tests/unit/test_repository_layout.py::test_approved_document_renames_use_exact_canonical_names tests/unit/test_repository_layout.py::test_superseded_documents_are_archived_without_breaking_current_entries tests/unit/test_repository_layout.py::test_competition_archive_and_handover_have_current_reader_entries`。
- 结果7通过、1失败。失败源于原有大写历史文件experiments/E17_SOURCE_INDEX.md及harness/tasks/M3-EXPANSION-001.md与旧小写规范期望不一致，两文件本轮未动；未放宽断言。归档与唯一指南相关检查通过，整体命名检查不能宣称通过。
- `F:\robot\Anaconda3\python.exe -B -X utf8 -m ruff check scripts/audit_project_conventions.py tests/unit/test_repository_layout.py`通过。只调用check_top_level_directories和check_active_document_links，两项均通过；没有运行会递归验证冻结证据的完整审计。
- 13份活动文档86个本地链接全部有效；feature JSON解析和scoped git diff --check通过。当前科研源码、输入、raw、统计及LaTeX未修改；无API、Full Harness、论文编译或进程终止。
- Git仅提交本轮目录迁移、阅读入口、定向检查和状态。外部归档不上传GitHub；原有科研、模板、第三方dirty工作保留。交付分支codex/directory-migration-fixes，最终提交与远端核对结果见git log和对话回执。
- 整理提交aceda6b716a510db1c74e6ba39fd3e53cfcfe04f已通过git push origin codex/directory-migration-fixes交付；git ls-remote确认同SHA。暂存300个移出的历史文件均在外部归档存在（299比赛材料+1根指南副本），24个其余变更全部属于本轮白名单；原current-task中的16行无关工作仍未提交。此回执仅文档补记。
