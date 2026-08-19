from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from experiments.paper_v2.public_matrix_controller_v4 import (
    DEFAULT_CANDIDATE,
    DEFAULT_QUALIFICATION,
    validate_candidate,
)


def _load_json(path: Any) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_public_v4_qualification_covers_actual_m3_evaluator() -> None:
    value = _load_json(DEFAULT_QUALIFICATION)

    assert value["status"] == "public_v4_controller_qualified_offline"
    assert value["plan"]["records"] == 6873
    assert value["condition_shells"]["qualified_pairs"] == 18
    assert value["public_m3_evaluator"]["qualification_probes"] == 4
    assert value["public_m3_evaluator"][
        "all_binding_digests_match"
    ] is True
    assert value["public_m3_evaluator"][
        "all_evaluator_probes_completed"
    ] is True
    assert value["public_v3_abort"]["record_count"] == 12
    assert value["public_v3_abort"]["provider_calls_completed"] == 33
    assert value["public_v3_abort"]["run_resumable"] is False
    assert value["public_v3_abort"][
        "result_admission_authorized"
    ] is False
    assert value["public_v3_abort"][
        "binding_digest_matches_active_material"
    ] is False
    assert value["evidence_boundary"]["network_calls_made"] == 0


def test_public_v4_candidate_is_fresh_and_non_executable() -> None:
    value = validate_candidate(_load_json(DEFAULT_CANDIDATE))

    assert value["scope"]["records"] == 6873
    assert value["scope"]["qualification"][
        "public_m3_evaluator_probes"
    ] == 4
    assert value["scope"]["scientific_boundary"][
        "partial_v3_records_admissible"
    ] is False
    assert value["scope"]["remediation"][
        "active_execution_identity_injected_into_resolver"
    ] is True
    assert value["authorization"] == {
        "candidate_only": True,
        "canary_execution_authorized": False,
        "matrix_continuation_authorized": False,
        "result_admission_authorized": False,
        "active_admission_present": False,
    }
    for role in ("primary", "second"):
        model = value["scope"]["model_roles"][role]
        run = value["scope"]["runs"][role]
        assert model["execution_identity"] != model[
            "source_execution_identity"
        ]
        assert model["source_execution_identity"] == model[
            "public_v3_execution_identity"
        ]
        assert run["run_id"].startswith(f"paper-v2-public-v4-{role}-")
        assert f"public-v4-{role}-{model['execution_identity']}" in run[
            "output_root"
        ]


def test_public_v4_candidate_rejects_scope_digest_drift() -> None:
    value = _load_json(DEFAULT_CANDIDATE)
    drifted = copy.deepcopy(value)
    drifted["scope"]["records"] = 6872

    with pytest.raises(Exception):
        validate_candidate(drifted)
