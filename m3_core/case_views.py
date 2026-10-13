"""在线运行时视图与离线评测元数据字段隔离投影视图模块。

严格贯彻安全界限：仅向在线运行时暴露解密后的必要输入字段，
离线黄金标准（Ground Truth）与评测器专用答案保留在离线边界，严防数据泄漏作弊。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


RUNTIME_CASE_FIELDS = (
    "user_task",
    "document_content",
    "requires_tool",
    "authorized_actions",
    "conversation_turns",
)

EVALUATION_FIELDS = (
    "case_id",
    "sample_type",
    "template_id",
    "split",
    "mutation_id",
    "attack_family",
    "carrier",
    "language",
    "expected_safe_behavior",
    "unsafe_target_actions",
    "risk_tags",
    "severity",
    "expected_detectors",
    "success_indicators",
    "safe_indicators",
    "notes",
)

# These fields are especially dangerous because their value directly describes
# the intended answer or detector outcome.  Tests use this list as a contract.
FORBIDDEN_RUNTIME_FIELDS = frozenset(
    {
        "case_id",
        "sample_type",
        "template_id",
        "split",
        "mutation_id",
        "attack_family",
        "carrier",
        "language",
        "injected_content",
        "expected_safe_behavior",
        "unsafe_target_actions",
        "risk_tags",
        "severity",
        "expected_detectors",
        "success_indicators",
        "safe_indicators",
        "notes",
    }
)


def runtime_case_view(case: Dict[str, Any] | None) -> Dict[str, Any]:
    """向在线智能体运行时暴露的最小安全案例文本视图。"""
    source = case if isinstance(case, dict) else {}
    view: Dict[str, Any] = {}
    for field in RUNTIME_CASE_FIELDS:
        if field in source:
            view[field] = deepcopy(source[field])

    view.setdefault("user_task", "")
    view.setdefault("document_content", "")
    view.setdefault("requires_tool", False)
    view.setdefault("authorized_actions", [])
    view.setdefault("conversation_turns", [])
    return view


def evaluation_metadata(case: Dict[str, Any] | None) -> Dict[str, Any]:
    """保留在离线边界、供评测器评分使用的完整审计元数据。"""
    source = case if isinstance(case, dict) else {}
    return {
        field: deepcopy(source[field])
        for field in EVALUATION_FIELDS
        if field in source
    }
