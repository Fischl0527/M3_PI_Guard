from __future__ import annotations

import copy

import experiments.paper_v2.formal_matrix_controller_v8 as v8
from experiments.paper_v2.boundary_rejection_runtime_v3 import (
    BOUNDARY_REJECTION_REASON,
    BoundaryAwareM3EffectBackendV3,
    validate_boundary_rejections_v3,
)
from experiments.paper_v2.formal_matrix_abort_review_v3 import (
    verify_abort_review,
)


def test_v8_qualification_covers_delayed_backend_resolution() -> None:
    qualification = v8.build_controller_qualification()

    assert qualification["status"] == (
        "matrix_controller_v8_qualified_offline"
    )
    assert qualification["adapter_binding_scope"] == "full_execute_scope"
    assert qualification["delayed_backend_resolution_scenarios"] == len(
        v8.PROPOSAL_EFFECT_REJECTION_MESSAGES
    )
    assert qualification["network_calls_made"] == 0
    assert qualification["scientific_outcomes_read"] == 0


def test_v8_execute_keeps_v3_adapter_bound_for_lazy_runtime(
    monkeypatch,
) -> None:
    base = v8.previous.previous.base
    original = base.BoundaryAwareM3EffectBackend

    def delayed_execute(
        authorization,
        *,
        values,
        dispatcher_factory,
        max_new_items,
    ):
        del authorization, values, dispatcher_factory, max_new_items
        assert base.BoundaryAwareM3EffectBackend is (
            BoundaryAwareM3EffectBackendV3
        )
        backend = base.BoundaryAwareM3EffectBackend(
            v8._RejectingDelegate(
                next(iter(v8.PROPOSAL_EFFECT_REJECTION_MESSAGES))
            )
        )
        result = backend.execute("synthetic_tool", {"value": 1})
        assert result["error"] == BOUNDARY_REJECTION_REASON
        assert validate_boundary_rejections_v3(
            backend.evaluator_material()
        ) == 1
        return {"status": "matrix_v2_paused"}

    monkeypatch.setattr(base.v2, "_execute", delayed_execute)
    result = v8._execute(
        object(),
        values={},
        dispatcher_factory=lambda *args: None,
        max_new_items=1,
    )

    assert result["status"] == "matrix_v8_paused"
    assert result["adapter_binding_scope"] == "full_execute_scope"
    assert base.BoundaryAwareM3EffectBackend is original


def test_v7_abort_review_is_content_free_and_reproducible() -> None:
    review = verify_abort_review()

    assert review["operational_summary"]["record_count"] == 0
    assert review["operational_summary"]["open_attempt_count"] == 1
    assert review["operational_summary"]["provider_calls_completed"] == 2
    assert review["evidence_boundary"]["scientific_outcomes_reviewed"] is False
    assert review["evidence_boundary"]["prior_run_resumable"] is False


def test_v8_frozen_candidate_and_canary_admission_reproduce() -> None:
    candidate = v8.verify_matrix_candidate()
    admission = v8.verify_canary_admission()
    scope = candidate["scope"]

    assert scope["run_id"] == v8.RUN_ID
    assert scope["lifecycle_binding_repair"] == {
        "binding_scope": "full_execute_scope",
        "lazy_backend_resolution_qualified": True,
        "scientific_outcomes_read": False,
        "v7_open_attempt_count": 1,
        "v7_provider_calls_completed": 2,
        "v7_record_count": 0,
        "v7_resumable": False,
    }
    assert admission["authorization"]["canary_execution_authorized"] is True
    assert admission["authorization"]["matrix_continuation_authorized"] is False
    assert admission["authorization"]["result_admission_authorized"] is False
    assert admission["scope"]["candidate_scope_sha256"] == (
        candidate["scope_sha256"]
    )
    assert copy.deepcopy(scope["provider"])["automatic_retries"] == 0
