import unittest
from pathlib import Path


class HandoffLegacyAuditIntakeTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.protocol = (root / "docs" / "codex_handoff_protocol.md").read_text(
            encoding="utf-8"
        )

    def test_handoff_requires_legacy_direct_evidence_intake_slots(self):
        self.assertIn("Legacy direct-evidence intake", self.protocol)
        for slot in (
            "user_observation",
            "legacy_ux_bug_or_patchwork",
            "data_lineage_observation",
            "replacement_user_path",
            "frozen_legacy_path",
            "evidence_attachment",
            "keep_promotion_decision",
        ):
            self.assertIn(slot, self.protocol)

    def test_first_pass_intake_cannot_be_reported_as_keep_promotion(self):
        self.assertIn("no_keep_promotion_this_round", self.protocol)
        for forbidden_evidence in (
            "seed inventory",
            "route inventory",
            "local receipts",
            "no-feature-loss matrix",
            "mock",
            "sanitizer",
            "docs/config scaffold",
            "checklist wording",
        ):
            self.assertIn(forbidden_evidence, self.protocol)
        self.assertIn("must not be described as direct UX/bug evidence", self.protocol)


if __name__ == "__main__":
    unittest.main()
