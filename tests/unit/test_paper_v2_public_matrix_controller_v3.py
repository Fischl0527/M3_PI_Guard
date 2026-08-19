from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from experiments.paper_v2.public_matrix_controller_v3 import (
    DEFAULT_CANDIDATE,
    DEFAULT_QUALIFICATION,
    validate_candidate,
)


def _load_json(path: Any) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_public_v3_qualification_covers_both_public_resolvers() -> None:
    value = _load_json(DEFAULT_QUALIFICATION)

    assert value["status"] == "public_v3_controller_qualified_offline"
    assert value["plan"]["records"] == 6873
    assert value["condition_shells"]["qualified_pairs"] == 18
    assert value["public_agentdojo_resolver"]["qualification_probes"] == 4
    assert value["public_m3_resolver"] == {
        "network_calls_made": 0,
        "online_state_mutated": False,
        "private_selection_bindings": 750,
        "public_work_items": 3600,
        "qualification_probes": 4,
        "qualification_sha256": (
            "afb003bf858b1234dafb929a3d2c9120ad001546fd8ad0b62099c5dddcfe3af3"
        ),
    }
    assert value["public_v2_abort"]["record_count"] == 12
    assert value["public_v2_abort"]["provider_calls_completed"] == 29
    assert value["public_v2_abort"]["run_resumable"] is False
    assert value["public_v2_abort"]["result_admission_authorized"] is False
    assert value["evidence_boundary"] == {
        "credentials_read": False,
        "network_calls_made": 0,
        "model_calls_made": 0,
        "experiment_records_persisted": 0,
        "formal_results_created": 0,
        "scientific_outcomes_accessed": False,
    }


def test_public_v3_candidate_is_fresh_and_non_executable() -> None:
    value = validate_candidate(_load_json(DEFAULT_CANDIDATE))

    assert value["scope"]["records"] == 6873
    assert value["scope"]["qualification"]["public_m3_probes"] == 4
    assert value["scope"]["scientific_boundary"][
        "partial_v2_records_admissible"
    ] is False
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
        assert run["run_id"].startswith(f"paper-v2-public-v3-{role}-")
        assert f"public-v3-{role}-{model['execution_identity']}" in run[
            "output_root"
        ]


def test_public_v3_candidate_rejects_scope_digest_drift() -> None:
    value = _load_json(DEFAULT_CANDIDATE)
    drifted = copy.deepcopy(value)
    drifted["scope"]["records"] = 6872

    with pytest.raises(Exception):
        validate_candidate(drifted)
