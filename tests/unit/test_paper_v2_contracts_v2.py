from __future__ import annotations

import copy
import hashlib
import json

import pytest
from jsonschema import ValidationError

from experiments.paper_v2.contracts import (
    PaperV2ContractError,
    compute_online_visible_field_digest,
    sha256_canonical_json,
)
from experiments.paper_v2.contracts_v2 import (
    validate_experiment_record_v2,
)
from experiments.paper_v2.formal_record_store import _load_plan
from experiments.paper_v2.formal_record_store_v2 import (
    _qualification_record,
)
from experiments.paper_v2.medium_runtime import (
    reconstruct_initial_online_state,
)


def _record(tmp_path):
    item = _load_plan()[0]
    record, events = _qualification_record(
        tmp_path,
        item=item,
        run_id="run-v2-test",
        index=1,
    )
    projection = {
        "initial_online_state": reconstruct_initial_online_state(item),
        "runtime_visibility_events": events,
    }
    return record, projection


def test_ordered_deepseek_trace_validates_as_v2_record(tmp_path) -> None:
    record, projection = _record(tmp_path)

    validate_experiment_record_v2(
        record,
        online_projection=projection,
    )


def test_v2_rejects_activation_drift_and_oracle_visibility(
    tmp_path,
) -> None:
    record, projection = _record(tmp_path)
    drifted = copy.deepcopy(record)
    bundle = drifted["provider_trace_bundle"]
    bundle["activated_attestations"][0][
        "activation_manifest_sha256"
    ] = hashlib.sha256(b"other-activation").hexdigest()
    bundle["bundle_sha256"] = sha256_canonical_json(
        {
            key: value
            for key, value in bundle.items()
            if key != "bundle_sha256"
        }
    )
    with pytest.raises(
        PaperV2ContractError,
        match="approval manifest",
    ):
        validate_experiment_record_v2(drifted)

    leaked_projection = copy.deepcopy(projection)
    leaked_projection["initial_online_state"]["answer_key"] = "forbidden"
    leaked = copy.deepcopy(record)
    leaked["online_visible_field_digest"] = (
        compute_online_visible_field_digest(leaked_projection)
    )
    with pytest.raises(ValidationError):
        validate_experiment_record_v2(
            leaked,
            online_projection=leaked_projection,
        )


def test_v2_formal_admission_requires_manifest(tmp_path) -> None:
    record, _projection = _record(tmp_path)
    record["result_tier"] = "formal_admitted"
    with pytest.raises(ValidationError):
        validate_experiment_record_v2(record)

    record["admission_manifest_sha256"] = "a" * 64
    validate_experiment_record_v2(record)


def test_v2_record_serialization_contains_no_response_content(
    tmp_path,
) -> None:
    record, _projection = _record(tmp_path)
    serialized = json.dumps(record, sort_keys=True)

    assert '"response_text":' not in serialized
    assert '"api_key":' not in serialized
    assert '"credential":' not in serialized


def test_v2_persists_and_validates_provider_safety_receipt(
    tmp_path,
) -> None:
    record, projection = _record(tmp_path)
    receipt = record["provider_safety_receipt"]

    assert receipt["credentials_stored"] is False
    assert receipt["evidence"]["external_connectors_enabled"] is False
    assert receipt["evidence"]["provider_managed_tools_enabled"] is False
    validate_experiment_record_v2(record, online_projection=projection)

    missing = copy.deepcopy(record)
    del missing["provider_safety_receipt"]
    with pytest.raises(ValidationError):
        validate_experiment_record_v2(missing)

    weakened = copy.deepcopy(record)
    weakened["provider_safety_receipt"]["evidence"][
        "external_connectors_enabled"
    ] = True
    weakened["provider_safety_receipt"]["evidence_sha256"] = (
        sha256_canonical_json(
            weakened["provider_safety_receipt"]["evidence"]
        )
    )
    with pytest.raises(ValidationError):
        validate_experiment_record_v2(weakened)
