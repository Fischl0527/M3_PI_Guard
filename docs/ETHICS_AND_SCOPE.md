# Ethics And Scope

## 1. 项目性质

M3-PI Guard 是面向大模型智能体工具链的本地授权安全评测作品。项目目标是研究提示注入、越狱提示和工具输出污染是否会诱导 Agent 触发未授权 mock 工具动作，并验证行为监督模块的告警、确认和阻断能力。

## 2. 本地沙箱边界

所有样本均运行在本地 `sandbox` mock 环境中。项目不攻击真实模型服务、真实账号、真实邮箱、真实 API、真实网站或第三方系统。

## 3. Mock 工具限定

样本只允许引用以下本地 mock 动作：

- `read_file:sandbox/secrets/api_key.txt`
- `send_email:redteam@example.test`
- `write_file:sandbox/public/notes.txt`
- `call_api:/mock/external/submit`
- `run_code:mock_only`

其中 `send_email` 不真实发送邮件，`call_api` 不访问公网，`run_code` 不执行模型生成的真实代码。

## 4. Secret 与数据

项目中的 secret、token、api_key、password 和 canary 均为本地假数据。样本不读取真实敏感文件，不包含真实凭证，不包含真实外发地址。

## 5. 不包含真实恶意代码

样本不提供真实漏洞利用步骤，不包含真实恶意命令，不包含真实网络攻击 payload，不引导攻击第三方系统。

## 6. 报告与演示口径

展示时应明确说明：红队攻击链仅用于本地授权沙箱复现，目标是验证防护机制是否能识别未授权工具调用、敏感路径访问、结构化注入和工具输出污染。

## 7. 预期用途

本项目适用于：

- 大模型 Agent 安全课程实验
- 信息安全竞赛作品展示
- 本地行为监督策略验证
- mock 工具链红队评测

不适用于真实系统攻击、真实凭证处理或未授权安全测试。
