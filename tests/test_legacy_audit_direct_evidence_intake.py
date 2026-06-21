import unittest
from pathlib import Path


class LegacyAuditDirectEvidenceIntakeTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.migration_map = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")

    def test_direct_evidence_intake_template_has_required_slots(self):
        self.assertIn("第一轮 Legacy Bug / UX Audit 的直接取证模板", self.migration_map)
        for required_slot in (
            "user_observation",
            "legacy_ux_bug_or_patchwork",
            "data_lineage_observation",
            "replacement_user_path",
            "frozen_legacy_path",
            "evidence_attachment",
            "keep_promotion_decision",
        ):
            self.assertIn(required_slot, self.migration_map)

    def test_first_intake_does_not_promote_seed_rows_to_keep_or_evidence(self):
        for required_boundary in (
            "no_keep_promotion_this_round",
            "不是新 contract、receipt、matrix 或 production evidence",
            "不要求打开 Streamlit",
            "不调用 Tushare/DeepSeek/GitHub",
            "不创建 task",
            "不读取 token/key",
            "不能把 route inventory、本地 receipt、no-feature-loss matrix、mock、sanitizer 或 docs/config scaffold 当作直接 UX/bug evidence",
        ):
            self.assertIn(required_boundary, self.migration_map)

        for allowed_status in (
            "direct_evidence_intake_pending",
            "direct_evidence_observed_redesign_required",
            "blocked_by_lineage",
            "legacy_debug_retained",
            "retire_confirmed",
        ):
            self.assertIn(allowed_status, self.migration_map)

        self.assertIn("`KEEP` 仍然保持禁止", self.migration_map)
        self.assertIn("不能把本轮取证当作生产验收", self.migration_map)


if __name__ == "__main__":
    unittest.main()
