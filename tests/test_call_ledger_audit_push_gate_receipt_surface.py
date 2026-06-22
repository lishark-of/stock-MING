from __future__ import annotations

import unittest
from pathlib import Path


class CallLedgerAuditPushGateReceiptSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.page = (root / "desktop" / "src" / "routes" / "CallLedgerAudit.tsx").read_text(
            encoding="utf-8"
        )

    def test_local_push_gate_run_receipt_is_visible_as_local_non_ci_evidence(self) -> None:
        self.assertIn("local_push_gate_run_receipt", self.page)
        self.assertIn("localPushGateRunReceipt", self.page)
        self.assertIn("Local push gate run receipt", self.page)
        self.assertIn(".stock_ming_3/release_gate/local_push_gate_run_receipt.json", self.page)
        self.assertIn("本地门禁通过证据，不代表远端 CI", self.page)
        self.assertIn("fresh_local_gate_run_observed", self.page)
        self.assertIn("head_matches_current", self.page)
        self.assertIn("local_gate_pass_is_not_ci_status", self.page)
        self.assertIn("did_not_push", self.page)
        self.assertIn("github_api_called", self.page)

    def test_push_gate_receipt_keeps_remote_actions_separate(self) -> None:
        self.assertIn("scripts/push_gate_3_0.sh", self.page)
        self.assertIn("已在本机对当前 HEAD 通过", self.page)
        self.assertIn("远端 Actions 仍需单独确认", self.page)
        self.assertIn("Push readiness receipt", self.page)
        self.assertIn("release_gate_push_readiness_receipt", self.page)
        self.assertIn("本地收据，只选择显式 gate/push/远端复核路径", self.page)
        self.assertIn("remote_actions_status_known", self.page)
        self.assertIn("latest_remote_run_verified_green", self.page)
        self.assertIn("static_ci_mirror_is_not_ci_status", self.page)
        self.assertIn("can_clear_failure_email_without_matching_head_and_logs", self.page)
        self.assertIn("该收据不运行 push gate、不调用 GitHub、不推送代码", self.page)


if __name__ == "__main__":
    unittest.main()
