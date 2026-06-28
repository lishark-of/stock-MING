from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MigrationStatusLtg11ReleaseGateUiTests(unittest.TestCase):
    def test_migration_status_surfaces_current_head_publish_boundary_in_audit_layer(self) -> None:
        migration_source = (ROOT / "desktop" / "src" / "routes" / "MigrationStatus.tsx").read_text(
            encoding="utf-8"
        )
        home_source = (ROOT / "desktop" / "src" / "routes" / "CommandCenterHome.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("LTG-11 release gate 远端查收分离", migration_source)
        self.assertIn("releaseGatePublishStatusLabel", migration_source)
        self.assertIn("releaseGatePublishStepLabel", migration_source)
        self.assertIn("current_head_publish_status", migration_source)
        self.assertIn("current_head_origin_ahead_count", migration_source)
        self.assertIn("current_head_push_required_before_remote_review", migration_source)
        self.assertIn("remote_review_waiting_for_current_head_push", migration_source)
        self.assertIn("next_publish_step", migration_source)
        self.assertIn('label: "current HEAD"', migration_source)
        self.assertIn('label: "push required"', migration_source)
        self.assertIn('label: "current ahead"', migration_source)
        self.assertIn('label: "waiting push"', migration_source)
        self.assertIn('label: "next publish"', migration_source)
        self.assertIn("waiting for push", migration_source)
        self.assertIn("push after clean gate", migration_source)
        self.assertIn("inspect matching Actions", migration_source)
        self.assertIn("上一轮绿色 run 不能证明当前 HEAD", migration_source)
        self.assertIn("DataLineageTable rows={[releaseGateRemoteReviewSplitSummary]}", migration_source)
        self.assertIn("DataLineageTable rows={releaseGateRemoteReviewSplitRows}", migration_source)

        self.assertNotIn("current_head_publish_status", home_source)
        self.assertNotIn("remote_review_waiting_for_current_head_push", home_source)
        self.assertNotIn("next_publish_step", home_source)


if __name__ == "__main__":
    unittest.main()
