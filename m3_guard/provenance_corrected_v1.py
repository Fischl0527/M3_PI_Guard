"""Opt-in literal provenance and trusted observation labels for corrected_v1.

This module does not alter the historical provenance implementation. Labels
come only from a separate, typed effect-backend metadata channel after a tool
has actually returned data. Matching is literal/whitespace/case normalized;
encoding, paraphrase and arbitrary semantic transformations are not covered.
"""

from __future__ import annotations

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
    """A labelled source value must occur inside an outgoing argument.

    The historical check used the reverse direction. Very short source values
    are exact-only: e.g. labelled ``key`` must not taint ``monkey`` or every
    sentence containing those three letters. Empty/nontext values never taint.
    """
    needle = _normalized(known_value)
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
    """Keep the public signature and source attribution; correct label flow."""
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
    """Constructed by the effect backend, never parsed from model/tool text.

    ``data_labels=()`` means that the backend classified this returned data as
    unlabelled; ``None`` at the observe boundary means no classification exists.
    The label vocabulary is the manifest's vocabulary (e.g. ``private``), not
    an inferred answer/evaluator label. Metadata classifies the whole returned
    data, so structured responses with differently classified fields require
    a backend projection before calling this interface.
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
    """Run-local labels for returned data; raw values never appear in summaries."""

    def __init__(self) -> None:
        self._values: dict[str, list[str]] = {}
        self._classified_observations = 0
        self._unclassified_observations = 0
        self._failed_observations = 0

    @property
    def labelled_values(self) -> dict[str, tuple[str, ...]]:
        """Internal matching input only; do not put this property into logs."""
        return {label: tuple(values) for label, values in self._values.items()}

    def observe(
        self,
        tool: str,
        args: Mapping[str, Any],
        observation: Any,
        trusted_metadata: TrustedObservationMetadata | None = None,
    ) -> dict[str, Any]:
        """Accept actual tool output plus a separate backend classification.

        Only call after an attempted tool execution. The caller must not pass
        predicted/unexecuted observations. An arbitrary observation dictionary
        cannot self-declare labels, execution success or authority.
        """
        del tool, args
        if trusted_metadata is None:
            self._unclassified_observations += 1
            return self.summary()
        if not isinstance(trusted_metadata, TrustedObservationMetadata):
            raise TypeError(
                "trusted_metadata must be backend-created TrustedObservationMetadata"
            )
        if not trusted_metadata.execution_succeeded:
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
        """Report applicability/input coverage, not a second Guard decision.

        ``triggered`` means a matching dataflow constraint was identified; a
        Guard can still terminate earlier at a different check. Persist its
        actual decision separately. No constraint is introduced here.
        """
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
