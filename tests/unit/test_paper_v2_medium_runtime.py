from __future__ import annotations

import unittest

from experiments.paper_v2.medium_runtime import (
    ConditionDispatcher,
    MediumRuntimeError,
    _stub_attestation,
    assemble_experiment_record,
    build_runtime_plan,
    reconstruct_initial_online_state,
    validate_stub_matrix,
    verify_runtime_plan,
)


class PaperV2MediumRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.items, cls.manifest = build_runtime_plan()

    def test_v2_freezes_all_480_condition_specific_items(self) -> None:
        self.assertEqual(len(self.items), 480)
        self.assertEqual(self.manifest["work_item_counts"]["primary"], 432)
        self.assertEqual(
            self.manifest["work_item_counts"]["authorization_regime_probe"], 48
        )
        self.assertEqual(self.manifest["network_calls_made"], 0)
        self.assertEqual(self.manifest["formal_results_created"], 0)
        self.assertEqual(self.manifest["formal_executors_registered"], 0)
        self.assertFalse(self.manifest["execution_authorized"])

    def test_six_conditions_have_distinct_initial_runtime_states(self) -> None:
        first_selection = self.items[0]["selection_id"]
        core = [
            item
            for item in self.items
            if item["selection_id"] == first_selection
            and item["analysis_tier"] == "primary"
        ]
        self.assertEqual(len(core), 6)
        value_hashes = {
            item["initial_online_visible_field_digest"]["visible_values_sha256"]
            for item in core
        }
        self.assertEqual(len(value_hashes), 6)

    def test_authorization_probe_changes_m3_runtime_state(self) -> None:
        probe = next(
            item
            for item in self.items
            if item["analysis_tier"] == "authorization_regime_probe"
            and item["authorization_regime"] != "auto_compiled"
        )
        primary = next(
            item
            for item in self.items
            if item["selection_id"] == probe["selection_id"]
            and item["condition_id"] == probe["condition_id"]
            and item["analysis_tier"] == "primary"
        )
        self.assertNotEqual(
            probe["initial_online_visible_field_digest"]["visible_values_sha256"],
            primary["initial_online_visible_field_digest"][
                "visible_values_sha256"
            ],
        )

    def test_exact_authorization_is_honestly_evaluator_derived(self) -> None:
        exact = next(
            item
            for item in self.items
            if item["authorization_regime"] == "exact_gold"
        )
        state = reconstruct_initial_online_state(exact)
        authorization = state["runtime_control"]["authorization"]
        self.assertEqual(
            authorization["source_class"], "evaluator_derived_authorization"
        )
        self.assertFalse(authorization["formal_primary_endpoint_eligible"])
        digest = exact["initial_online_visible_field_digest"]
        self.assertFalse(digest["forbidden_fields_present"])
        self.assertEqual(digest["forbidden_field_paths"], [])

    def test_dispatcher_fails_closed_on_missing_or_duplicate_condition(self) -> None:
        dispatcher = ConditionDispatcher()
        with self.assertRaises(MediumRuntimeError):
            dispatcher.assert_complete()
        dispatcher.register("no_defense", lambda item, state: {})
        with self.assertRaises(MediumRuntimeError):
            dispatcher.register("no_defense", lambda item, state: {})

    def test_operational_failure_is_conservative_and_retained_in_itt(self) -> None:
        item = self.items[0]
        state = reconstruct_initial_online_state(item)
        result = {
            "initial_guard_decision": "ALLOW",
            "ask_reason": None,
            "confirmation_result": "not_requested",
            "unsafe_effect": None,
            "task_completion": True,
            "operational_status": "provider_failure",
            "provider_attestation": _stub_attestation(),
            "result_tier": "stub",
            "latency_ms": {
                "total": 0.0,
                "model": 0.0,
                "guard": 0.0,
                "tool": 0.0,
            },
            "token_usage": {
                "input": 0,
                "output": 0,
                "total": 0,
                "available": False,
            },
            "runtime_visibility_events": [],
            "recorded_at": "2026-07-23T22:05:00+08:00",
        }
        record = assemble_experiment_record(
            item, state, result, run_id="test-failure"
        )
        self.assertTrue(record["included_in_intention_to_treat"])
        self.assertTrue(record["unsafe_effect_itt"])
        self.assertFalse(record["task_completion"])
        self.assertIsNone(record["unsafe_effect"])

    def test_non_stub_execution_without_safety_receipt_is_rejected(self) -> None:
        item = self.items[0]
        state = reconstruct_initial_online_state(item)
        result = {
            "initial_guard_decision": "ALLOW",
            "ask_reason": None,
            "confirmation_result": "not_requested",
            "unsafe_effect": False,
            "task_completion": False,
            "operational_status": "completed",
            "provider_attestation": _stub_attestation(),
            "result_tier": "diagnostic",
            "latency_ms": {
                "total": 0.0,
                "model": 0.0,
                "guard": 0.0,
                "tool": 0.0,
            },
            "token_usage": {
                "input": 0,
                "output": 0,
                "total": 0,
                "available": False,
            },
            "runtime_visibility_events": [],
            "recorded_at": "2026-07-23T22:05:00+08:00",
        }
        with self.assertRaises(MediumRuntimeError):
            assemble_experiment_record(
                item, state, result, run_id="test-no-safety-receipt"
            )

    def test_stub_matrix_validates_without_persisting_results(self) -> None:
        summary = validate_stub_matrix(self.items)
        self.assertEqual(summary["validated"], 480)
        self.assertEqual(summary["itt_included"], 480)
        self.assertGreater(summary["operational_failure"], 0)
        self.assertGreater(summary["ask"], 0)
        self.assertEqual(summary["records_persisted"], 0)
        self.assertEqual(summary["network_calls_made"], 0)
        self.assertFalse(summary["scientific_result"])

    def test_frozen_v2_plan_reproduces(self) -> None:
        observed = verify_runtime_plan(validate_stubs=False)
        self.assertEqual(observed, self.manifest)


if __name__ == "__main__":
    unittest.main()
