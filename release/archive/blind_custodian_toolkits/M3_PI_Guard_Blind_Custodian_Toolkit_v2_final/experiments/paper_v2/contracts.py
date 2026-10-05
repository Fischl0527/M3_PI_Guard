"""Minimal canonical-JSON contract used by the offline custodian toolkit."""
from __future__ import annotations

import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Match the paper-v2 canonical JSON representation without dependencies."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
