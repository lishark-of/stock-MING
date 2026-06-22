from __future__ import annotations

import unittest
from pathlib import Path


class CallLedgerAuditReleaseGateSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.page = (root / "desktop" / "src" / "routes" / "CallLedgerAudit.tsx").read_text(
            encoding="utf-8"
        )

    def test_release_gate_principle_guard_is_visible_on_audit_page(self) -> None:
        self.assertIn("release_gate_readiness_audit", self.page)
        self.assertIn("release_gate_readiness_rows", self.page)
        self.assertIn("Release gate readiness", self.page)
        self.assertIn("Release gate checklist", self.page)
        self.assertIn("CI原则守护", self.page)
        self.assertIn("ci_mirror_principle_guard", self.page)
        self.assertIn("ci_mirror_includes_migration_principle_docs_guard", self.page)
        self.assertIn("本地静态 push gate 合同，不代表 CI 状态", self.page)

    def test_remote_ci_seed_stays_visible_as_unverified_non_evidence(self) -> None:
        self.assertIn("remote_ci_review_seed_contract", self.page)
        self.assertIn("remoteCiReviewSeedContract", self.page)
        self.assertIn("remoteCiReviewSeedRows", self.page)
        self.assertIn("Remote CI review seed row", self.page)
        self.assertIn("P0 blocker 模板，不读取 GitHub、不代表 CI 证据", self.page)
        self.assertIn("local_checkpoint_seed_row_no_github_api_no_push", self.page)
        self.assertIn("remote_ci_review_seed_row_keeps_p0_blocked_until_matching_remote_run_review", self.page)
        self.assertIn("remote_status", self.page)
        self.assertIn("remote_ci_unverified", self.page)
        self.assertIn("failed_step_or_green_status", self.page)
        self.assertIn("not_reviewed", self.page)
        self.assertIn("release_claim_decision", self.page)
        self.assertIn("blocked_remote_ci_unverified", self.page)
        self.assertIn("seed_row_is_not_remote_ci_evidence", self.page)
        self.assertIn("P0 仍需匹配 HEAD 的远端 Actions run 或安全失败日志复核", self.page)
        self.assertIn("不能放行 release claim", self.page)


if __name__ == "__main__":
    unittest.main()
