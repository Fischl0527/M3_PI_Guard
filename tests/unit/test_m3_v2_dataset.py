from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

from m3_attacks.m3_v2_generator import (
    ATTACK_FAMILIES,
    DEFAULT_OUTPUT,
    DEFAULT_REVIEW_OUTPUT,
    audit_cases,
    build_cases,
    dataset_sha256,
    sha256_bytes,
)
from m3_core.policy_compiler import compile_task_policy
from m3_core.research_runner import paper_runtime_view
from experiments.paper_v1.benchmarks.audit_m3_v2_independent_blind import (
    EXPECTED_ATTACK_FAMILIES,
    build_independent_blind_audit,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class M3V2DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = build_cases()

    def test_exact_counts_and_balanced_family_splits(self) -> None:
        self.assertEqual(len(self.cases), 1500)
        self.assertEqual(
            Counter(case["sample_type"] for case in self.cases),
            {"attack": 900, "benign_no_tool": 300, "benign_legal_tool": 300},
        )
        self.assertEqual(
            Counter(case["split"] for case in self.cases),
            {"development": 600, "validation": 300, "sealed_holdout": 600},
        )
        family_split = Counter(
            (case["split"], case["attack_family"])
            for case in self.cases
            if case["sample_type"] == "attack"
        )
        for family in ATTACK_FAMILIES:
            self.assertEqual(family_split[("development", family)], 40)
            self.assertEqual(family_split[("validation", family)], 20)
            self.assertEqual(family_split[("sealed_holdout", family)], 40)

    def test_templates_do_not_cross_splits(self) -> None:
        splits: dict[str, set[str]] = defaultdict(set)
        mutation_keys: set[tuple[str, str]] = set()
        for case in self.cases:
            splits[case["template_id"]].add(case["split"])
            key = (case["template_id"], case["mutation_id"])
            self.assertNotIn(key, mutation_keys)
            mutation_keys.add(key)
        self.assertEqual(len(splits), 300)
        self.assertTrue(all(len(values) == 1 for values in splits.values()))

    def test_all_cases_validate_and_holdout_claim_is_honest(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "schemas" / "paper_v1" / "paper_case.schema.json").read_text(
                encoding="utf-8"
            )
        )
        validator = Draft202012Validator(schema)
        for case in self.cases:
            validator.validate(case)
            if case["split"] == "sealed_holdout":
                self.assertEqual(case["evidence_level"], "sealed_automated_holdout")

    def test_online_projection_never_contains_offline_evaluator_contract(self) -> None:
        for case in self.cases:
            view = paper_runtime_view(case)
            self.assertFalse(hasattr(view, "offline_evaluation"))
            self.assertNotIn("offline_evaluation", view.__dict__)
            manifest = compile_task_policy(
                trusted_user_request=view.trusted_user_request,
                trusted_app_context=view.trusted_app_context,
                generated_at="2026-07-18T00:00:00+00:00",
            )
            self.assertNotIn("oracle", manifest.policy_source)

    def test_build_and_release_audits_are_deterministic(self) -> None:
        rebuilt = build_cases()
        self.assertEqual(dataset_sha256(rebuilt), dataset_sha256(self.cases))
        audit = audit_cases(rebuilt)
        self.assertEqual(audit["status"], "pass")
        self.assertTrue(all(audit["gates"].values()))

    def test_written_artifacts_and_review_frame_match_manifests(self) -> None:
        manifest_path = DEFAULT_OUTPUT / "dataset_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["dataset_sha256"], dataset_sha256(self.cases))
        self.assertFalse(manifest["evidence_boundary"]["independent_blind_claimed"])
        for artifact in manifest["artifacts"].values():
            path = REPO_ROOT / artifact["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(sha256_bytes(path.read_bytes()), artifact["sha256"])

        review_manifest = json.loads(
            (DEFAULT_REVIEW_OUTPUT / "m3_v2_review_sampling_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(review_manifest["rows"], 500)
        self.assertEqual(review_manifest["status"], "sampling_frame_only")
        frame = DEFAULT_REVIEW_OUTPUT / "m3_v2_review_sampling_frame_500.csv"
        self.assertEqual(sha256_bytes(frame.read_bytes()), review_manifest["sha256"])

    def _independent_blind_candidate_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        families = sorted(EXPECTED_ATTACK_FAMILIES)
        for index in range(600):
            if index < 360:
                sample_type = "attack"
                attack_family = families[index // 40]
            elif index < 480:
                sample_type = "benign_no_tool"
                attack_family = "benign_clean"
            else:
                sample_type = "benign_legal_tool"
                attack_family = "benign_clean"
            case_id = f"M3V2-IB-{index + 1:04d}"
            rows.append(
                {
                    "case_id": case_id,
                    "template_id": f"M3V2-IB-T-{index + 1:04d}",
                    "split": "independent_blind",
                    "evidence_level": "independent_blind",
                    "sample_type": sample_type,
                    "attack_family": attack_family,
                    "trusted_user_request": f"Independent blind task {index + 1}",
                    "trusted_app_context": {"request_id": case_id},
                    "untrusted_content": f"Independent blind content {index + 1}",
                    "untrusted_memory": [],
                    "generation": {"generator": "independent_blind_authoring_program_v1"},
                    "custody": {
                        "independent_source": "reviewer_team_or_independent_script",
                        "sealed_at": "2026-07-21T00:00:00+00:00",
                    },
                }
            )
        return rows

    def _write_independent_blind_custody(self, candidate: Path, rows: list[dict[str, object]]) -> Path:
        import hashlib

        custody = candidate.with_name("m3_v2_independent_blind_custody.json")
        custody.write_text(
            json.dumps(
                {
                    "schema_version": "m3-independent-blind-custody-1.0",
                    "status": "sealed_candidate",
                    "candidate_filename": candidate.name,
                    "candidate_row_count": len(rows),
                    "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                    "custodian_id": "independent-custodian-1",
                    "independent_author_ids": ["independent-author-1"],
                    "authoring_method": "independent_program_v1",
                    "authoring_environment": "isolated-test-environment-lock-v1",
                    "developer_access_before_seal": False,
                    "sealed_at": "2026-07-21T00:00:00+00:00",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return custody

    def test_independent_blind_admission_missing_candidate_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = build_independent_blind_audit(
                candidate_path=root / "missing.jsonl",
                reference_dataset_path=root / "reference.jsonl",
                output_dir=root / "protocols",
            )

        self.assertEqual(audit["status"], "blocked_missing_candidate")
        self.assertFalse(audit["result_eligible_for_confirmatory_q2_tables"])
        self.assertEqual(audit["required_candidate_contract"]["total_cases"], 600)

    def test_independent_blind_admission_accepts_clean_600_case_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "candidate.jsonl"
            reference = root / "reference.jsonl"
            rows = self._independent_blind_candidate_rows()
            candidate.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            self._write_independent_blind_custody(candidate, rows)
            reference.write_text(
                json.dumps(
                    {
                        "case_id": "M3V2-REF-0001",
                        "template_id": "M3V2-REF-T-0001",
                        "trusted_user_request": "reference",
                        "trusted_app_context": {},
                        "untrusted_content": "reference",
                        "untrusted_memory": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            audit = build_independent_blind_audit(
                candidate_path=candidate,
                reference_dataset_path=reference,
                output_dir=root / "protocols",
            )

        self.assertEqual(audit["status"], "admitted_independent_blind")
        self.assertTrue(audit["result_eligible_for_confirmatory_q2_tables"])
        self.assertEqual(audit["counts"]["sample_type_counts"]["attack"], 360)
        self.assertEqual(audit["counts"]["attack_family_counts"][sorted(EXPECTED_ATTACK_FAMILIES)[0]], 40)

    def test_independent_blind_admission_rejects_local_generator_or_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "candidate.jsonl"
            reference = root / "reference.jsonl"
            rows = self._independent_blind_candidate_rows()
            rows[0]["generation"] = {"generator": "m3_attacks.m3_v2_generator"}
            rows[1]["template_id"] = "M3V2-REF-T-0001"
            candidate.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            self._write_independent_blind_custody(candidate, rows)
            reference.write_text(
                json.dumps(
                    {
                        "case_id": "M3V2-REF-0001",
                        "template_id": "M3V2-REF-T-0001",
                        "trusted_user_request": "reference",
                        "trusted_app_context": {},
                        "untrusted_content": "reference",
                        "untrusted_memory": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            audit = build_independent_blind_audit(
                candidate_path=candidate,
                reference_dataset_path=reference,
                output_dir=root / "protocols",
            )

        self.assertEqual(audit["status"], "blocked_candidate_failed")
        failed = {check["name"] for check in audit["error_failures"]}
        self.assertIn("not_generated_by_local_m3_v2_generator", failed)
        self.assertIn("templates_do_not_overlap_reference_dataset", failed)

    def test_independent_blind_admission_rejects_missing_or_mismatched_custody(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "candidate.jsonl"
            reference = root / "reference.jsonl"
            rows = self._independent_blind_candidate_rows()
            candidate.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            reference.write_text("", encoding="utf-8")
            missing = build_independent_blind_audit(
                candidate_path=candidate,
                reference_dataset_path=reference,
                output_dir=root / "missing-audit",
            )
            custody = self._write_independent_blind_custody(candidate, rows)
            custody_data = json.loads(custody.read_text(encoding="utf-8"))
            custody_data["candidate_sha256"] = "0" * 64
            custody_data["developer_access_before_seal"] = True
            custody.write_text(json.dumps(custody_data) + "\n", encoding="utf-8")
            mismatched = build_independent_blind_audit(
                candidate_path=candidate,
                reference_dataset_path=reference,
                output_dir=root / "mismatch-audit",
            )

        self.assertEqual(missing["status"], "blocked_candidate_failed")
        missing_failed = {check["name"] for check in missing["error_failures"]}
        self.assertIn("custody_sidecar_present", missing_failed)
        self.assertEqual(mismatched["status"], "blocked_candidate_failed")
        mismatch_failed = {check["name"] for check in mismatched["error_failures"]}
        self.assertIn("custody_candidate_sha256_matches", mismatch_failed)
        self.assertIn("custody_declares_no_developer_access_before_seal", mismatch_failed)


if __name__ == "__main__":
    unittest.main()
