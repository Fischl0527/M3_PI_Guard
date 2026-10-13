"""M3 智能体核心基础设施包（Agent Core Package）。

提供智能体执行主循环（agent_runner）、策略词法编译器（policy_compiler）、
内存沙箱隔离工具环境（tool_sandbox）、模型推理客户端（llm_client）以及批量矩阵运行器。
"""

__all__ = [
    "agent_runner",
    "case_views",
    "llm_client",
    "run_batch",
    "run_matrix",
    "tool_sandbox",
]
