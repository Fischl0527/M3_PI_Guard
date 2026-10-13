"""显式选用的字面来源与受信任观测数据标签追踪模块（corrected_v1 修复版）。

本模块不破坏历史来源追踪的实现。其关键修复在于：
1. 标签只能来自于工具实际返回数据后、由隔离环境所提供的结构化元数据通道，模型无法自报标签；
2. 修正了子串污染匹配方向（原版是反向包含导致误判，修复为严格的受限值出站检测）；
3. 避免极短字符串（如 'key'）对长单词（如 'monkey'）的无界假阳性污点蔓延。
"""

from __future__ import annotations

# 来源（谁提供参数）与保密标签（数据能去哪里）是两种不同约束。
# 标签只来自实际工具返回后的可信元数据通道；模型或工具正文不能自行盖章。
# 本实现只识别字面值及大小写/空白归一化，不声称覆盖编码或语义改写泄漏。

import re
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from .provenance import (
    ProvenanceEvent,
    _flatten,
    infer_argument_provenance as _historical_infer,
)
from .task_policy import DataFlowConstraint


VERSION = "provenance_corrected_v1"
_MIN_SUBSTRING_LENGTH = 4
_LABEL_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_TARGET_FIELDS = frozenset({"to", "path", "endpoint"})


def _text_leaves(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _text_leaves(child)
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        for child in value:
            yield from _text_leaves(child)


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _carries_value(argument: Any, known_value: str) -> bool:
    """判断出站实参中是否携带有受保护标签的敏感数据原值。

    历史实现使用了相反的包含方向。超短字符串必须完全匹配；
    例如带有标签的 'key' 绝不能污染 'monkey' 或任何包含这 3 个字母的句子。
    空值或非文本对象绝不传播标签。
    """
    needle = _normalized(known_value)
    # 正确方向是“受保护原值出现在出站参数里”；短值仅完全相等才传播标签。
    if not needle:
        return False
    for text in _text_leaves(argument):
        haystack = _normalized(text)
        if haystack == needle:
            return True
        if len(needle) >= _MIN_SUBSTRING_LENGTH and needle in haystack:
            return True
    return False


def infer_argument_provenance(
    *,
    proposal_id: str,
    tool: str,
    arguments: Mapping[str, Any],
    trusted_user_request: str,
    trusted_app_context: Mapping[str, Any] | None = None,
    untrusted_document: str = "",
    untrusted_tool_outputs: Iterable[Any] = (),
    untrusted_memory: Iterable[Any] = (),
    labelled_values: Mapping[str, Iterable[Any]] | None = None,
) -> tuple[ProvenanceEvent, ...]:
    """保持公共签名与来源归因算法；修复标签流动方向与短词污染。"""
    historical = _historical_infer(
        proposal_id=proposal_id,
        tool=tool,
        arguments=arguments,
        trusted_user_request=trusted_user_request,
        trusted_app_context=trusted_app_context,
        untrusted_document=untrusted_document,
        untrusted_tool_outputs=untrusted_tool_outputs,
        untrusted_memory=untrusted_memory,
        labelled_values=None,
    )
    labels = {
        str(label): tuple(_text_leaves(values))
        for label, values in (labelled_values or {}).items()
    }
    leaves = dict(_flatten(arguments))
    return tuple(
        replace(
            event,
            data_labels=tuple(
                sorted(
                    label
                    for label, values in labels.items()
                    if any(
                        _carries_value(leaves[event.argument_path], value)
                        for value in values
                    )
                )
            ),
        )
        for event in historical
    )


@dataclass(frozen=True)
class TrustedObservationMetadata:
    """由副作用后端构造的元数据，绝不从模型/工具文本中解析。

    ``data_labels=()`` 表示后端将返回的数据分类为未打标；
    观察边界处的 ``None`` 表示不存在分类。
    标签词表使用清单的词表（例如 ``private``），而非推断出的答案/评测者标签。
    元数据对整个返回数据进行分类，因此包含不同分类字段的结构化响应在调用此接口前需要后端投影。
    """

    execution_succeeded: bool
    observation_is_data: bool
    data_labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self.execution_succeeded) is not bool
            or type(self.observation_is_data) is not bool
        ):
            raise TypeError("trusted observation flags must be booleans")
        if not isinstance(self.data_labels, tuple) or any(
            not isinstance(label, str) or _LABEL_NAME.fullmatch(label) is None
            for label in self.data_labels
        ):
            raise ValueError(
                "trusted labels must be a tuple of bounded label identifiers"
            )


class TrustedDataLabelTracker:
    """用于在单次运行局部追踪受信任数据流动与敏感标签的追踪器。"""

    def __init__(self) -> None:
        # 每次运行单独建立实例，禁止任务之间共享敏感值或分类历史。
        self._values: dict[str, list[str]] = {}
        self._classified_observations = 0
        self._unclassified_observations = 0
        self._failed_observations = 0

    @property
    def labelled_values(self) -> dict[str, tuple[str, ...]]:
        """获取各标签所关联的已知敏感文本值元组映射。"""
        return {label: tuple(values) for label, values in self._values.items()}

    def observe(
        self,
        tool: str,
        args: Mapping[str, Any],
        observation: Any,
        trusted_metadata: TrustedObservationMetadata | None = None,
    ) -> dict[str, Any]:
        """接收实际工具输出以及独立的后端分类结果。

        仅在尝试执行工具后调用。调用方绝不可传入预测的/未执行的观察结果。
        任意观察字典无法自行声明标签、执行成功状态或授权。
        """
        del tool, args
        # None 表示分类缺失；明确提供空标签元组才表示“已分类且无保密标签”。
        if trusted_metadata is None:
            self._unclassified_observations += 1
            return self.summary()
        if not isinstance(trusted_metadata, TrustedObservationMetadata):
            raise TypeError(
                "trusted_metadata must be backend-created TrustedObservationMetadata"
            )
        if not trusted_metadata.execution_succeeded:
            # 读取被隔离层拒绝时没有真实返回数据，不能登记预测内容。
            self._failed_observations += 1
            return self.summary()
        if not trusted_metadata.observation_is_data:
            return self.summary()
        self._classified_observations += 1
        values = tuple(text for text in _text_leaves(observation) if _normalized(text))
        for label in trusted_metadata.data_labels:
            bucket = self._values.setdefault(label, [])
            for value in values:
                if value not in bucket:
                    bucket.append(value)
        return self.summary()

    def infer_argument_provenance(self, **kwargs: Any) -> tuple[ProvenanceEvent, ...]:
        if kwargs.get("labelled_values") is not None:
            raise ValueError(
                "tracker label values must come from observed backend data"
            )
        kwargs["labelled_values"] = self.labelled_values
        return infer_argument_provenance(**kwargs)

    def summary(self) -> dict[str, Any]:
        # 公共记录仅含计数/标签名，内部用于匹配的原始值不进入日志。
        return {
            "version": VERSION,
            "classified_observation_count": self._classified_observations,
            "unclassified_observation_count": self._unclassified_observations,
            "failed_observation_count": self._failed_observations,
            "label_names": sorted(self._values),
            "labelled_value_count": sum(
                len(values) for values in self._values.values()
            ),
            "raw_values_logged": False,
            "matching_scope": "literal_case_whitespace_normalized_short_exact_only",
        }

    def summarize_dataflow(
        self,
        *,
        tool: str,
        arguments: Mapping[str, Any],
        events: Iterable[ProvenanceEvent],
        constraints: Iterable[DataFlowConstraint],
        module_enabled: bool = True,
    ) -> dict[str, Any]:
        """对拟议工具调用的数据流向进行诊断审计。"""
        events = tuple(events)
        labels = {label for event in events for label in event.data_labels}
        targets = [
            str(value)
            for key, value in arguments.items()
            if str(key).casefold() in _TARGET_FIELDS
        ]
        applicable = tuple(
            constraint
            for constraint in constraints
            if tool in constraint.forbidden_tools
            or any(
                re.search(pattern, target, flags=re.IGNORECASE)
                for pattern in constraint.forbidden_target_patterns
                for target in targets
            )
        )
        triggered = tuple(item for item in applicable if item.data_label in labels)
        if not module_enabled:
            # 四类状态分开报告：不适用、触发、缺输入、检查通过。缺输入不是通过。
            status, reason = "not_applicable", "module_disabled"
        elif not applicable:
            status, reason = "not_applicable", "no_applicable_constraint"
        elif triggered:
            status, reason = "triggered", "labelled_value_matches_restricted_sink"
        elif self._classified_observations == 0 or self._unclassified_observations:
            status, reason = (
                "missing_input",
                "trusted_observation_classification_incomplete",
            )
        else:
            status, reason = "passed", "no_labelled_value_matches_restricted_sink"
        return {
            **self.summary(),
            "status": status,
            "reason": reason,
            "applicable_constraint_count": len(applicable) if module_enabled else 0,
            "triggered_constraint_ids": [item.constraint_id for item in triggered]
            if module_enabled
            else [],
            "matched_label_names": sorted(labels),
            "labelled_argument_count": sum(bool(event.data_labels) for event in events),
        }
