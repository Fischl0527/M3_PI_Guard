from __future__ import annotations

import unittest

from experiments.paper_v2.citation_integrity import (
    build_citation_manifest,
    verify_citation_manifest,
)


class PaperV2CitationIntegrityTests(unittest.TestCase):
    def test_matrix_has_34_primary_source_entries(self) -> None:
        manifest = build_citation_manifest()
        self.assertEqual(manifest["citation_count"], 34)
        self.assertEqual(manifest["peer_reviewed_count"], 24)
        self.assertEqual(manifest["preprint_only_count"], 10)
        self.assertEqual(len(manifest["entries"]), 34)
        self.assertEqual(
            manifest["status"],
            "matrix_metadata_refreshed_final_context_audit_pending",
        )
        self.assertEqual(
            manifest["authoritative_metadata_audit"]["checked_count"], 34
        )
        self.assertTrue(
            all(
                entry["stable_url"].startswith("https://")
                for entry in manifest["entries"]
            )
        )

    def test_frontier_statuses_do_not_promote_preprints(self) -> None:
        manifest = build_citation_manifest()
        statuses = manifest["critical_status_by_id"]
        self.assertEqual(statuses["L01"], "peer_reviewed")
        self.assertEqual(statuses["L02"], "peer_reviewed")
        self.assertEqual(statuses["L21"], "preprint")
        self.assertEqual(statuses["L22"], "preprint")
        self.assertEqual(statuses["L27"], "preprint")
        self.assertFalse(
            manifest["claim_controls"]["preprint_treated_as_peer_reviewed"]
        )
        self.assertTrue(
            manifest["claim_controls"]["submission_date_refresh_required"]
        )

    def test_frozen_manifest_reproduces(self) -> None:
        verify_citation_manifest()


if __name__ == "__main__":
    unittest.main()
