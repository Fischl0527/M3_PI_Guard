"""Guard module configuration and canonical ablation profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


ALL_MODULES = frozenset(
    {
        "policy",
        "dataflow",
        "instruction_detector",
        "tool_lure_detector",
        "structured_detector",
        "multilingual_detector",
        "intent_action",
        "output_dlp",
    }
)

TEXT_DETECTOR_MODULES = frozenset(
    {
        "instruction_detector",
        "tool_lure_detector",
        "structured_detector",
        "multilingual_detector",
    }
)

MODE_MODULES = {
    "off": frozenset(),
    "keyword_only": frozenset({"instruction_detector", "tool_lure_detector"}),
    "detector_only": TEXT_DETECTOR_MODULES,
    "policy_only": frozenset({"policy"}),
    "full_guard": ALL_MODULES,
    "no_dataflow": ALL_MODULES - {"dataflow"},
    "no_intent_action": ALL_MODULES - {"intent_action"},
    "no_structured_detector": ALL_MODULES - {"structured_detector"},
    "no_multilingual_detector": ALL_MODULES - {"multilingual_detector"},
}

MODE_ALIASES = {
    "baseline": "off",
    "guarded": "full_guard",
}


def canonical_guard_mode(mode: Any) -> str:
    value = str(mode or "full_guard").strip().lower()
    value = MODE_ALIASES.get(value, value)
    if value not in MODE_MODULES:
        raise ValueError(
            "guard_mode must be one of: " + ", ".join(sorted(MODE_MODULES))
        )
    return value


def parse_modules(value: Any) -> frozenset[str] | None:
    """Parse a module override; None means use the selected mode profile."""

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
    """Fully resolved Guard behavior for one experimental condition."""

    mode: str = "full_guard"
    modules: frozenset[str] | None = None
    ask_threshold: float = 0.35
    deny_threshold: float = 0.65

    def __post_init__(self) -> None:
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
        return cls(
            mode=canonical_guard_mode(mode),
            modules=parse_modules(modules),
            ask_threshold=ask_threshold,
            deny_threshold=deny_threshold,
        )

    def enabled(self, module: str) -> bool:
        return module in (self.modules or frozenset())

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "modules": sorted(self.modules or frozenset()),
            "ask_threshold": self.ask_threshold,
            "deny_threshold": self.deny_threshold,
        }
