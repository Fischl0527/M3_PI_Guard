"""本地 M3 智能体安全防护包（Guard Package）。

本包提供可配置的运行时防护引擎、安全策略清单契约、动作监视器、
来源追溯追踪器与提示注入检测器，用于拦截不可信间接提示注入与越权动作。
"""

from .config import GuardConfig
from .guard_engine import GuardResult, evaluate_guard, guard_decide

__all__ = ["GuardConfig", "GuardResult", "evaluate_guard", "guard_decide"]
