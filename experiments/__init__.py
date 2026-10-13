"""面向 M3_PI_Guard 的可复现 E0-E17 全套实验编排系统。

管理从基础度量审计（E0）到消融验证、长上下文修正、自适应对抗以及双盲人工审查的全生命周期科研实验。
"""

from .registry import EXPERIMENT_IDS, load_registry

__all__ = ["EXPERIMENT_IDS", "load_registry"]
