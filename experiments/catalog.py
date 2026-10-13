"""规范的 E0-E17 实验目录与固定的条件对比网格清单。

声明性定义各个实验代号（如 E9 上下文、E13 阈值、E16 红队）的测试用例规模、模型矩阵与防护条件对照表。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


CORE_MODELS = (
    "qwen3:4b-instruct",
    "phi4-mini:3.8b",
    "llama3.2:3b",
    "gemma3:4b",
)
LEGACY_MODEL = "vicuna:7b"
ALL_MODELS = (*CORE_MODELS, LEGACY_MODEL)

MAIN_SEEDS = (104729, 130363, 155921)
STABILITY_SEEDS = (11, 23, 37, 53, 71, 89, 107, 131, 163, 197)
STABILITY_TEMPERATURES = (0.0, 0.2, 0.7)
CONTEXT_LENGTHS = (2048, 4096, 8192, 16384)
INJECTION_POSITIONS = (0, 25, 50, 75, 100)
TURN_COUNTS = (1, 3, 5, 10)
PERFORMANCE_CONCURRENCY = (1, 2, 4)


@dataclass(frozen=True)
class Condition:
    id: str
    prompt_profile: str
    guard_mode: str
    guard_modules: tuple[str, ...] = ()
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["guard_modules"] = list(self.guard_modules)
        return payload


CORE_CONDITIONS = (
    Condition("regular_none", "normal", "none", description="Regular prompt, no Guard"),
    Condition("hardened_none", "hardened", "none", description="Hardened prompt, no Guard"),
    Condition("regular_keyword", "normal", "keyword_only", description="Regular prompt, keyword detector only"),
    Condition("regular_policy", "normal", "policy_only", description="Regular prompt, policy engine only"),
    Condition("regular_full", "normal", "full_guard", description="Regular prompt, full Guard"),
    Condition("hardened_full", "hardened", "full_guard", description="Hardened prompt, full Guard"),
)

ABLATION_CONDITIONS = (
    Condition("regular_detector_only", "normal", "custom", ("detector",), "Detector only"),
    Condition("regular_dataflow_only", "normal", "custom", ("dataflow",), "Dataflow only"),
    Condition("regular_intent_action_only", "normal", "custom", ("intent_action",), "Intent-action policy only"),
    Condition("regular_no_dataflow", "normal", "full_guard", ("detector", "intent_action"), "Full Guard without dataflow"),
    Condition("regular_no_intent_action", "normal", "full_guard", ("detector", "dataflow"), "Full Guard without intent-action"),
    Condition(
        "regular_no_structured_detector",
        "normal",
        "full_guard",
        ("keyword", "multilingual", "dataflow", "intent_action"),
        "Full Guard without structured detector",
    ),
    Condition(
        "regular_no_multilingual_detector",
        "normal",
        "full_guard",
        ("keyword", "structured", "dataflow", "intent_action"),
        "Full Guard without multilingual detector",
    ),
)


@dataclass(frozen=True)
class ExperimentDefinition:
    id: str
    name: str
    question: str
    dataset_scope: str
    formal_backend: str = "ollama"


EXPERIMENTS = (
    ExperimentDefinition("E0", "measurement_integrity", "Are labels, denominators and prompts trustworthy?", "legacy + canonical"),
    ExperimentDefinition("E1", "main_guard_effect", "What is the same-prompt incremental effect of full Guard?", "blind"),
    ExperimentDefinition("E2", "prompt_hardening", "What does prompt hardening achieve without Guard?", "blind"),
    ExperimentDefinition("E3", "guard_incremental_effect", "Does Guard add protection after prompt hardening?", "blind"),
    ExperimentDefinition("E4", "component_ablation", "Which Guard components contribute protection and utility cost?", "validation"),
    ExperimentDefinition("E5", "cross_model_generalization", "Does the effect generalize across local models?", "blind"),
    ExperimentDefinition("E6", "attack_family_effect", "Which attack families retain residual success?", "blind"),
    ExperimentDefinition("E7", "multilingual_robustness", "How robust is the system across language forms?", "dedicated"),
    ExperimentDefinition("E8", "encoding_evasion", "How robust is the system to encoded and hidden variants?", "dedicated"),
    ExperimentDefinition("E9", "long_context_position", "How do context length and injection position change outcomes?", "dedicated"),
    ExperimentDefinition("E10", "multi_turn_attack", "How do delayed and cumulative attacks change outcomes?", "dedicated"),
    ExperimentDefinition("E11", "cross_tool_chain", "Can attacks propagate across authorized tool chains?", "blind + dedicated"),
    ExperimentDefinition("E12", "benign_utility", "What normal-task utility and false-positive cost remain?", "blind"),
    ExperimentDefinition("E13", "threshold_calibration", "Which validation-only operating point meets security/utility goals?", "validation"),
    ExperimentDefinition("E14", "performance_resources", "What latency, throughput and VRAM overhead does protection add?", "dedicated"),
    ExperimentDefinition("E15", "random_stability", "How stable are outcomes across seeds and temperatures?", "representative"),
    ExperimentDefinition("E16", "adaptive_red_team", "Does reason-guided rewriting recover attack success?", "dedicated"),
    ExperimentDefinition("E17", "explanation_failure_review", "What failure modes remain and how consistently are they reviewed?", "all failures"),
)

EXPERIMENT_BY_ID = {item.id: item for item in EXPERIMENTS}


def validate_catalog() -> None:
    expected = [f"E{index}" for index in range(18)]
    actual = [item.id for item in EXPERIMENTS]
    if actual != expected:
        raise ValueError(f"experiment catalogue order mismatch: {actual}")
    condition_ids = [item.id for item in (*CORE_CONDITIONS, *ABLATION_CONDITIONS)]
    if len(condition_ids) != len(set(condition_ids)):
        raise ValueError("duplicate experiment condition id")
    if len(CORE_CONDITIONS) != 6:
        raise ValueError("the frozen main matrix must contain exactly six conditions")
    if len(CORE_MODELS) != 4 or len(MAIN_SEEDS) != 3:
        raise ValueError("the frozen main matrix requires four models and three repeats")


validate_catalog()
