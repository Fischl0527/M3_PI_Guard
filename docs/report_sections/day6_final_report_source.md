# M3-PI Guard：面向工具调用智能体的提示注入行为监督系统

## 摘要

随着大模型智能体逐步具备文件读写、邮件发送、接口调用和代码执行等工具能力，提示注入与越狱攻击的风险从文本输出扩展为可观测的外部行为风险。本作品围绕工具调用边界构建 M3-PI Guard 行为监督系统，通过规则化归一、指令型文本检测、JSON/RPC 结构化注入识别、多语言与字符混淆检测、敏感数据流分析和意图-动作一致性校验，对每一次工具调用输出 allow、ask、deny 决策和可解释风险原因。系统不依赖远程评审模型，可在本地靶场稳定复现实验。测试结果显示，在 stub 全量矩阵中，baseline 的 ASR 和 DSR 均为 0.5507，full_guard 模式均降至 0.0000，WRS 从 0.4891 提升至 0.9826；在 Qwen2.5 代表样本中，full_guard 同样将 ASR、UTR、DSR 降至 0.0000。作品具有本地可复现、行为指标可量化、阻断原因可解释和演示闭环完整等特点，可用于智能体安全评测、教学演示和防护原型验证。

## 第一章 作品概述

### 1.1 背景分析

大模型正在从问答系统演进为可调用工具的智能体。智能体能够读取本地文件、写入结果、调用接口或生成自动化动作，这提升了任务完成能力，也扩大了攻击面。
传统提示注入主要关注模型是否输出违规文本，而在工具调用场景中，更关键的问题是模型是否被诱导执行越权动作，例如读取 sandbox/secrets、外发 canary、调用非预期接口或执行代码。
因此，本作品将安全目标从文本拒答扩展到行为监督：在工具调用执行前进行风险评分和策略裁决。

### 1.2 相关工作

相关研究覆盖越狱攻击、间接提示注入、RAG 数据污染、工具调用劫持和智能体安全评测。现有方法常见路线包括提示词加固、输入过滤、策略沙箱、LLM Judge 和日志审计。
本作品采用本地规则与行为指标结合的方案，强调可复现与可解释，避免依赖远程模型或不可控服务。

### 1.3 作品目标

作品目标包括：构建可拦截危险工具调用的 Guard；形成覆盖多类攻击的本地评测集；输出 ASR、UTR、DSR、BSR、FPR、AvgRisk、WRS 等行为指标；提供 Dashboard 演示和单案例回放。

### 1.4 特色与应用前景

系统特色是将安全判断绑定到工具执行边界，并将每次阻断转化为明确原因码。该能力可应用于智能体安全测试、课程实验、企业内部工具代理审计和提示注入防护原型验证。

## 第二章 作品设计与实现

### 2.1 系统方案

系统由攻击样本、智能体运行器、工具沙箱、行为监督 Guard、指标评测和 Dashboard 六部分组成。运行器读取 AttackCase，模型或 stub 后端输出 ToolCall，Guard 在工具执行前给出 allow、ask 或 deny。
工具沙箱仅模拟本地文件、邮件、API 和代码执行结果，不访问真实公网业务系统。

### 2.2 实现原理

Guard 采用分层检测：normalizer 负责 Unicode NFKC 归一化、零宽字符删除和混合脚本识别；detector 识别指令型文本、工具诱导、JSON/RPC 字段和多语言混淆；dataflow 标记 canary、api_key、token、password 等敏感数据流；policy_engine 实现工具策略矩阵；guard_engine 汇总风险并按阈值裁决。
风险阈值为 risk >= 0.65 时 deny，0.35 <= risk < 0.65 时 ask，risk < 0.35 时 allow。run_code、secret 路径读取、非 sandbox 路径、非 /mock endpoint 和敏感数据外发属于强规则拒绝。

### 2.3 软件流程

流程为：加载攻击样本；构造上下文；模型生成 ToolCall；Guard 归一化输入并计算风险；根据策略输出决策；允许时执行本地模拟工具，拒绝或确认时写入阻断日志；评测脚本聚合 RunLog 并生成指标。

### 2.4 模块功能

m3_guard 提供工具调用风险裁决；m3_eval.evaluate 生成 CSV/JSON 指标；m3_eval.dashboard 提供总览、分组、阻断记录、单案例回放和原始日志查看；plot_metrics 生成答辩图表。

### 2.5 指标体系

指标包括 ASR、UTR、DSR、BSR、FPR、AvgRisk 和 WRS。其中 ASR 衡量攻击成功率，UTR 衡量未授权工具调用率，DSR 衡量敏感数据外泄率，BSR 衡量阻断成功率，WRS 综合反映系统韧性。

## 第三章 作品测试与分析

### 3.1 测试环境

测试在本地 Windows 环境完成，使用 Python 脚本运行 stub 后端和 Qwen2.5 代表样本。工具调用均为本地模拟，邮件写入 outbox 文件，API 返回 mock JSON，代码执行工具默认禁用。

### 3.2 测试数据与方案

测试数据包括 stub 全量四模式矩阵、Qwen2.5 代表样本和 demo case。攻击类型覆盖 direct_jailbreak、rag_indirect、json_rpc、multilingual_t2l、tool_output_injection 和 benign_clean 等类别。
防御模式包括 baseline、keyword_only、policy_only 和 full_guard，用于分析不同防护组件的贡献。

### 3.3 实验结果

stub 全量矩阵中，baseline 的 ASR 为 0.5507、DSR 为 0.5507；full_guard 的 ASR、UTR、DSR 均为 0.0000，BSR 为 0.8841，WRS 达到 0.9826。
Qwen2.5 代表样本中，baseline 的 ASR 为 0.0833、DSR 为 0.0417；full_guard 将 ASR、UTR、DSR 均降为 0.0000，WRS 提升至 0.9187。
demo case 中 full_guard 的 BSR 为 1.0000，适合展示阻断原因和单案例回放。

### 3.4 案例分析

在 RAG 间接提示注入案例中，文档隐藏 read_file 和 send_email 指令，Guard 会同时给出 tool_lure、structured_injection 或 sensitive_data_flow 相关原因。
在 JSON/RPC 注入案例中，method、params、execute、next_step 等字段会增加结构化注入风险。
在多语言/T2L 案例中，系统通过混合脚本、工具词和拼音规避信号提高风险评分。

## 第四章 创新性说明

### 4.1 行为边界监督

作品将提示注入防护点从模型输出文本前移到工具执行边界，直接降低越权读取、外发和代码执行风险。

### 4.2 多信号可解释风险评分

系统将工具类型、路径、endpoint、敏感数据流、结构化注入、多语言混淆和意图-动作不一致合并为可解释风险原因，便于复盘和展示。

### 4.3 本地可复现实验闭环

作品提供攻击样本、运行日志、评测脚本、图表和 Dashboard，形成无需远程服务的完整本地评测闭环。

## 第五章 总结

### 5.1 工作总结

本作品实现了面向工具调用智能体的行为监督 Guard，并通过多组日志验证其对未授权工具调用和敏感数据外发的抑制效果。实验表明，full_guard 能显著降低 ASR、UTR 和 DSR，并提供可解释的阻断原因。

### 5.2 后续工作

后续可扩展更丰富的 clean case 以增强 FPR 解释力，引入语义级检测以覆盖深度改写攻击，并将 Dashboard 扩展为长期实验管理与审计平台。

## 参考文献

[1] Perez F, Ribeiro I. Ignore Previous Prompt: Attack Techniques For Language Models[C]//NeurIPS ML Safety Workshop. 2022.
[2] Greshake K, Abdelnabi S, Mishra S, et al. Not what you have signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection[C]//AISec. 2023.
[3] OWASP Foundation. OWASP Top 10 for Large Language Model Applications[EB/OL]. 2025.
[4] Yao S, Zhao J, Yu D, et al. ReAct: Synergizing Reasoning and Acting in Language Models[C]//ICLR. 2023.
[5] Wei A, Haghtalab N, Steinhardt J. Jailbroken: How Does LLM Safety Training Fail?[C]//NeurIPS. 2023.
[6] 中国国家标准化管理委员会. 信息与文献 参考文献著录规则: GB/T 7714-2015[S]. 北京: 中国标准出版社, 2015.
