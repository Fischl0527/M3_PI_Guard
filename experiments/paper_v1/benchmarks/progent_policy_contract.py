"""Policy-output contract checks for Progent source-backed adapters.

The upstream Progent implementation retries policy generation when a parsed
JSON value later fails shape assumptions such as ``allowed_tool["name"]``.
For formal evidence, the adapter needs to classify that failure before runtime
execution and preserve it as policy contract evidence instead of an uncaught
``KeyError``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class PolicySchemaValidationError(ValueError):
    """Raised when a syntactically parsed Progent policy has the wrong shape."""


def _typename(value: Any) -> str:
    return type(value).__name__


def validate_generated_policy_shape(
    value: Any,
    *,
    available_tool_names: set[str] | None = None,
    allow_none: bool = False,
) -> list[dict[str, Any]] | None:
    """Validate one generated Progent policy payload.

    Parameters
    ----------
    value:
        The value returned by upstream ``extract_json``.
    available_tool_names:
        Optional frozen tool-name set.  When provided, every generated tool name
        must be present in the currently exposed AgentDojo tool schema.
    allow_none:
        Progent update policy generation uses ``None`` to mean "do not update".
        Initial policy generation should leave this false.
    """

    if value is None:
        if allow_none:
            return None
        raise PolicySchemaValidationError("policy payload is null")

    if not isinstance(value, list):
        raise PolicySchemaValidationError(
            f"policy payload must be a list, got {_typename(value)}"
        )

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise PolicySchemaValidationError(
                f"policy[{index}] must be an object, got {_typename(item)}"
            )
        if "name" not in item:
            raise PolicySchemaValidationError(f"policy[{index}].name is missing")
        name = item["name"]
        if not isinstance(name, str) or not name.strip():
            raise PolicySchemaValidationError(
                f"policy[{index}].name must be a non-empty string"
            )
        if available_tool_names is not None and name not in available_tool_names:
            raise PolicySchemaValidationError(
                f"policy[{index}].name '{name}' is not an available tool"
            )
        if "args" not in item:
            raise PolicySchemaValidationError(f"policy[{index}].args is missing")
        args = item["args"]
        if not isinstance(args, Mapping):
            raise PolicySchemaValidationError(
                f"policy[{index}].args must be an object, got {_typename(args)}"
            )
        normalized.append({"name": name, "args": dict(args)})
    return normalized
