from __future__ import annotations

import re

import pytest

from experiments.paper_v1.benchmarks.progent_policy_contract import (
    PolicySchemaValidationError,
    validate_generated_policy_shape,
)


def test_validate_generated_policy_shape_accepts_minimal_valid_policy() -> None:
    value = [{"name": "send_email", "args": {"recipient": {"type": "string"}}}]

    assert validate_generated_policy_shape(
        value, available_tool_names={"send_email"}
    ) == value


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (None, "policy payload is null"),
        ({"name": "send_email", "args": {}}, "must be a list"),
        ([{"args": {}}], "policy[0].name is missing"),
        ([{"name": "", "args": {}}], "name must be a non-empty string"),
        ([{"name": "unknown", "args": {}}], "not an available tool"),
        ([{"name": "send_email"}], "policy[0].args is missing"),
        ([{"name": "send_email", "args": []}], "args must be an object"),
        (["send_email"], "policy[0] must be an object"),
    ],
)
def test_validate_generated_policy_shape_rejects_contract_failures(
    value: object, message: str
) -> None:
    with pytest.raises(PolicySchemaValidationError, match=re.escape(message)):
        validate_generated_policy_shape(value, available_tool_names={"send_email"})


def test_validate_generated_policy_shape_allows_none_for_update_path() -> None:
    assert validate_generated_policy_shape(None, allow_none=True) is None
