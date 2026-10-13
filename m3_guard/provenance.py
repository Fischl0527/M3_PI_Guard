"""Paper-v1/v2 工具动作实参级别来源追溯（Argument-Level Provenance Tracking）模块。

本模块负责追溯工具调用参数的源头归属（Trusted User、Trusted App Context、Untrusted Document、
Untrusted Tool Output 或 Model Generated），并为每个参数绑定可审计的哈希与证据路径。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


TRUSTED_SOURCES = frozenset({"trusted_user", "trusted_app_context", "tool_schema"})
UNTRUSTED_SOURCES = frozenset(
    {"untrusted_document", "untrusted_tool_output", "untrusted_memory"}
)
SOURCE_TYPES = TRUSTED_SOURCES | UNTRUSTED_SOURCES | frozenset({"model_generated"})
TARGET_FIELDS = {
    "read_file": frozenset({"path"}),
    "write_file": frozenset({"path"}),
    "send_email": frozenset({"to"}),
    "call_api": frozenset({"endpoint"}),
    "run_code": frozenset({"code"}),
}
GENERIC_TARGET_FIELDS = frozenset(
    {
        "to",
        "recipient",
        "recipients",
        "participant",
        "participants",
        "destination",
        "destinations",
        "address",
        "email",
        "path",
        "endpoint",
        "url",
        "account",
        "channel",
    }
)
GENERIC_SELECTOR_FIELDS = frozenset(
    {
        "query",
        "name",
        "search",
        "filter",
        "recipient",
        "recipients",
        "participant",
        "participants",
        "destination",
        "destinations",
        "address",
        "email",
        "to",
    }
)
_INSTRUCTION_FIELD_RE = re.compile(
    r"(?:^|\.)(?:body|content|description|instruction|instructions|message|note|notes|text)(?:$|\.|\[)",
    flags=re.IGNORECASE,
)


def _value_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _normalized(value: Any) -> str:
    return " ".join(_value_text(value).casefold().split())


def _value_sha256(value: Any) -> str:
    return hashlib.sha256(_value_text(value).encode("utf-8", errors="replace")).hexdigest()


@dataclass(frozen=True)
class ProvenanceEvent:
    """关于某个动作实参源自何处的一条可审计凭证事件。

    属性:
        event_id (str): 事件唯一标识。
        proposal_id (str): 关联动作提案 ID。
        argument_path (str): 参数访问路径（如 'arguments.path'）。
        source_type (str): 来源分类（'trusted_user', 'untrusted_document' 等）。
        trust_level (str): 信任等级（'trusted', 'untrusted', 'model_generated'）。
        value_sha256 (str): 参数值的 SHA-256 哈希值。
        source_event_id (str | None): 传播前序事件 ID。
        data_labels (tuple[str, ...]): 附带的数据敏感标签元组。
        evidence (str): 判定来源的证据文本摘录。
    """

    event_id: str
    proposal_id: str
    argument_path: str
    source_type: str
    trust_level: str
    value_sha256: str
    source_event_id: str | None = None
    data_labels: tuple[str, ...] = ()
    evidence: str = ""

    def __post_init__(self) -> None:
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"unsupported provenance source: {self.source_type}")
        if self.trust_level not in {"trusted", "untrusted", "model_generated"}:
            raise ValueError(f"unsupported trust level: {self.trust_level}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "proposal_id": self.proposal_id,
            "argument_path": self.argument_path,
            "source_type": self.source_type,
            "trust_level": self.trust_level,
            "value_sha256": self.value_sha256,
            "source_event_id": self.source_event_id,
            "data_labels": list(self.data_labels),
            "evidence": self.evidence,
        }


def _flatten(value: Any, *, prefix: str = "arguments") -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key in sorted(value, key=str):
            yield from _flatten(value[key], prefix=f"{prefix}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _flatten(item, prefix=f"{prefix}[{index}]")
        return
    yield prefix, value


def _contains(source: Any, value: Any) -> bool:
    source_text = _normalized(source)
    value_text = _normalized(value)
    return bool(value_text) and len(value_text) >= 2 and value_text in source_text


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(child) for child in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _jsonable(model_dump())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _find_value_path(source: Any, value: Any, *, prefix: str) -> str | None:
    source = _jsonable(source)
    if isinstance(source, Mapping):
        keys = list(source)
        if source.get("structured_result") is not None:
            keys = ["structured_result"] + [key for key in keys if key != "structured_result"]
        for key in keys:
            child = source[key]
            found = _find_value_path(child, value, prefix=f"{prefix}.{key}")
            if found:
                return found
        return None
    if isinstance(source, list):
        for index, child in enumerate(source):
            found = _find_value_path(child, value, prefix=f"{prefix}[{index}]")
            if found:
                return found
        return None
    return prefix if _contains(source, value) else None


def provenance_uses_instruction_field(event: "ProvenanceEvent") -> bool:
    if event.source_type != "untrusted_tool_output":
        return False
    marker = "tool_output_path:"
    if marker not in event.evidence:
        return False
    return _INSTRUCTION_FIELD_RE.search(event.evidence.split(marker, 1)[1]) is not None


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
    """归因每个叶子参数的来源，同时避免在审计日志中暴露未经脱敏的原始明文。

    当同一个字面值同时出现在用户可信请求与不可信文档中时，优先采信受信任来源。
    这可有效防止攻击者通过单纯重复用户已批准的目标来洗白未经授权的外部恶意信宿。

    参数:
        proposal_id: 提案唯一 ID。
        tool: 工具名称。
        arguments: 实参字典。
        trusted_user_request: 用户受信请求原文字符串。
        trusted_app_context: 受信应用上下文。
        untrusted_document: 不可信文档内容。
        untrusted_tool_outputs: 不可信历史工具输出列表。
        untrusted_memory: 不可信记忆项。
        labelled_values: 预定义的敏感数据标签及值集合映射。

    返回:
        tuple[ProvenanceEvent, ...]: 逐个实参叶子节点的来源追溯事件元组。
    """

    app_context = trusted_app_context or {}
    tool_outputs = tuple(untrusted_tool_outputs)
    memory_items = tuple(untrusted_memory)
    labels = labelled_values or {}
    events: list[ProvenanceEvent] = []
    target_fields = TARGET_FIELDS.get(tool, GENERIC_TARGET_FIELDS)

    for sequence, (path, value) in enumerate(_flatten(arguments), 1):
        top_level = path.removeprefix("arguments.").split(".", 1)[0].split("[", 1)[0]
        if _contains(trusted_user_request, value):
            source_type = "trusted_user"
            trust = "trusted"
            evidence = "literal_or_normalized_match_in_trusted_request"
        elif _contains(app_context, value):
            source_type = "trusted_app_context"
            trust = "trusted"
            evidence = "literal_or_normalized_match_in_trusted_context"
        elif _contains(untrusted_document, value):
            source_type = "untrusted_document"
            trust = "untrusted"
            evidence = "literal_or_normalized_match_in_untrusted_document"
        elif tool_match := next(
            (
                matched_path
                for index, item in enumerate(tool_outputs)
                if (
                    matched_path := _find_value_path(
                        item,
                        value,
                        prefix=f"tool_outputs[{index}]",
                    )
                )
            ),
            None,
        ):
            source_type = "untrusted_tool_output"
            trust = "untrusted"
            evidence = f"tool_output_path:{tool_match}"
        elif any(_contains(item, value) for item in memory_items):
            source_type = "untrusted_memory"
            trust = "untrusted"
            evidence = "literal_or_normalized_match_in_memory"
        else:
            source_type = "model_generated"
            trust = "model_generated"
            evidence = (
                "unattributed_action_target"
                if top_level in target_fields
                else "unattributed_model_value"
            )

        data_labels = tuple(
            sorted(
                label
                for label, known_values in labels.items()
                if any(_contains(known_value, value) for known_value in known_values)
            )
        )
        events.append(
            ProvenanceEvent(
                event_id=f"{proposal_id}:arg:{sequence}",
                proposal_id=proposal_id,
                argument_path=path,
                source_type=source_type,
                trust_level=trust,
                value_sha256=_value_sha256(value),
                data_labels=data_labels,
                evidence=evidence,
            )
        )
    return tuple(events)


def proposal_has_untrusted_target(
    tool: str,
    events: Iterable[ProvenanceEvent],
) -> bool:
    target_fields = TARGET_FIELDS.get(tool, GENERIC_TARGET_FIELDS)
    for event in events:
        top_level = (
            event.argument_path.removeprefix("arguments.")
            .split(".", 1)[0]
            .split("[", 1)[0]
        )
        if top_level in target_fields and event.source_type in UNTRUSTED_SOURCES:
            return True
    return False


def labels_in_proposal(events: Iterable[ProvenanceEvent]) -> frozenset[str]:
    return frozenset(label for event in events for label in event.data_labels)
