"""防护模块配置与规范消融配置文件（Ablation Profiles）。

本模块定义 Guard 的各种防御模式（如 baseline/off, policy_only, full_guard 等）
以及各模式所激活的防御子模块集合，同时提供防御阈值（ASK/DENY 阈值）解析。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

# 防护引擎所支持的全部子模块集合
ALL_MODULES = frozenset(
    {
        "policy",                   # 策略检查引擎（基于 TaskPolicyManifest 校验）
        "dataflow",                 # 数据流与污点分析（检查敏感数据流向受限信宿）
        "instruction_detector",     # 注入指令特征检测器
        "tool_lure_detector",       # 工具诱导调用检测器
        "structured_detector",      # 结构化注入格式检测器（代码块、JSON、特殊标记）
        "multilingual_detector",    # 多语言/翻译跨语言攻击检测器
        "intent_action",            # 意图与动作对齐分析模块
        "output_dlp",               # 输出数据防泄露 (Data Loss Prevention) 检查
    }
)

# 纯文本提示注入检测相关的子模块集合
TEXT_DETECTOR_MODULES = frozenset(
    {
        "instruction_detector",
        "tool_lure_detector",
        "structured_detector",
        "multilingual_detector",
    }
)

# 各防御模式及其对应的激活子模块映射表
MODE_MODULES = {
    "off": frozenset(),                                                          # 关闭所有防护（基线对照）
    "keyword_only": frozenset({"instruction_detector", "tool_lure_detector"}),  # 仅关键字/简单检测
    "detector_only": TEXT_DETECTOR_MODULES,                                      # 仅文本检测器
    "policy_only": frozenset({"policy"}),                                        # 仅策略约束检查
    "full_guard": ALL_MODULES,                                                   # 完整防御模块
    "no_dataflow": ALL_MODULES - {"dataflow"},                                   # 消融实验：去除数据流检查
    "no_intent_action": ALL_MODULES - {"intent_action"},                         # 消融实验：去除意图动作检查
    "no_structured_detector": ALL_MODULES - {"structured_detector"},             # 消融实验：去除结构化检测
    "no_multilingual_detector": ALL_MODULES - {"multilingual_detector"},         # 消融实验：去除多语言检测
}

# 模式别名映射表
MODE_ALIASES = {
    "baseline": "off",
    "guarded": "full_guard",
}


def canonical_guard_mode(mode: Any) -> str:
    """归一化防护模式名称。

    参数:
        mode: 输入的模式名称（字符串或其它类型，大小写不敏感）。

    返回:
        str: 规范化的模式名称（小写标准名称）。

    异常:
        ValueError: 当模式名称不在已知支持列表中时抛出。
    """
    value = str(mode or "full_guard").strip().lower()
    value = MODE_ALIASES.get(value, value)
    if value not in MODE_MODULES:
        raise ValueError(
            "guard_mode must be one of: " + ", ".join(sorted(MODE_MODULES))
        )
    return value


def parse_modules(value: Any) -> frozenset[str] | None:
    """解析显式指定的模块覆盖列表；若为 None 则使用所选模式的默认模块集合。

    参数:
        value: 逗号分隔的模块名字符串、可迭代集合或 None。

    返回:
        frozenset[str] | None: 归一化后的模块名称冻结集合；若未指定则返回 None。

    异常:
        TypeError: 输入类型既非字符串也非可迭代对象时抛出。
        ValueError: 包含未知的未知模块名时抛出。
    """
    if value is None or value == "":
        return None
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, Iterable):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        raise TypeError("guard_modules must be a comma-separated string or iterable")

    unknown = sorted(set(items) - ALL_MODULES)
    if unknown:
        raise ValueError("unknown Guard modules: " + ", ".join(unknown))
    return frozenset(items)


@dataclass(frozen=True)
class GuardConfig:
    """单个实验条件下完全解析的 Guard 防护配置。

    属性:
        mode (str): 防御模式名称（如 'full_guard', 'baseline', 'policy_only' 等）。
        modules (frozenset[str] | None): 具体启用的子模块集合。
        ask_threshold (float): 触发人工确认 (ASK) 的风险分数阈值（默认 0.35）。
        deny_threshold (float): 触发直接拒绝 (DENY) 的风险分数阈值（默认 0.65）。
    """

    mode: str = "full_guard"
    modules: frozenset[str] | None = None
    ask_threshold: float = 0.35
    deny_threshold: float = 0.65

    def __post_init__(self) -> None:
        """校验阈值范围以及模块有效性，并固化规范配置。"""
        canonical = canonical_guard_mode(self.mode)
        resolved = MODE_MODULES[canonical] if self.modules is None else parse_modules(self.modules)
        resolved = resolved if resolved is not None else MODE_MODULES[canonical]
        ask = float(self.ask_threshold)
        deny = float(self.deny_threshold)
        if not 0.0 <= ask <= 1.0 or not 0.0 <= deny <= 1.0:
            raise ValueError("Guard thresholds must be between 0 and 1")
        if ask > deny:
            raise ValueError("ask_threshold cannot exceed deny_threshold")
        object.__setattr__(self, "mode", canonical)
        object.__setattr__(self, "modules", frozenset(resolved))
        object.__setattr__(self, "ask_threshold", ask)
        object.__setattr__(self, "deny_threshold", deny)

    @classmethod
    def resolve(
        cls,
        mode: Any = "full_guard",
        *,
        modules: Any = None,
        ask_threshold: float = 0.35,
        deny_threshold: float = 0.65,
    ) -> "GuardConfig":
        """解析并构造 GuardConfig 实例。

        参数:
            mode: 防护模式名称。
            modules: 显式覆盖的模块集合或逗号分隔字符串。
            ask_threshold: ASK 风险阈值。
            deny_threshold: DENY 风险阈值。

        返回:
            GuardConfig: 初始化完成并校验通过的配置对象。
        """
        return cls(
            mode=canonical_guard_mode(mode),
            modules=parse_modules(modules),
            ask_threshold=ask_threshold,
            deny_threshold=deny_threshold,
        )

    def enabled(self, module: str) -> bool:
        """检查特定防御子模块是否已启用。"""
        return module in (self.modules or frozenset())

    def as_dict(self) -> dict[str, Any]:
        """将配置序列化为普通字典表示。"""
        return {
            "mode": self.mode,
            "modules": sorted(self.modules or frozenset()),
            "ask_threshold": self.ask_threshold,
            "deny_threshold": self.deny_threshold,
        }
