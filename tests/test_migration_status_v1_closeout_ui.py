import unittest
from pathlib import Path


class MigrationStatusV1CloseoutUiTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.page = (self.root / "desktop" / "src" / "routes" / "MigrationStatus.tsx").read_text(
            encoding="utf-8"
        )
        self.styles = (self.root / "desktop" / "src" / "styles.css").read_text(encoding="utf-8")
        self.panel_start = self.page.index('title="Command Center 3.0 · v1.0 本地发布候选"')
        self.summary_start = self.page.index('title="迁移状态摘要"', self.panel_start)
        self.panel = self.page[self.panel_start:self.summary_start]

    def test_v1_local_rc_panel_is_first_and_separates_production_closeout(self):
        self.assertLess(self.panel_start, self.summary_start)
        self.assertIn("command_center_3_v1_local_rc", self.page)
        self.assertIn("packet.v1_ltg_closure_rows", self.page)
        self.assertIn("commandCenterV1LocalRc.ltg_closure_rows", self.page)
        self.assertNotIn("ltg_evidence_closeout_rows", self.page)
        self.assertIn('label: "本地 RC"', self.panel)
        self.assertIn('label: "本地直接证据（版本）"', self.panel)
        self.assertIn('value: `${v1LocalVersionReadyCount}/${v1LocalVersionTotalCount}`', self.panel)
        self.assertIn('label: "生产 strict closeout"', self.panel)
        self.assertIn("v1ProductionStrictCloseoutReady", self.panel)
        self.assertIn("local RC ready 只代表本地发布候选，不代表生产 strict closeout", self.panel)

    def test_v1_contract_uses_real_backend_summary_and_fourteen_closure_rows(self):
        for field in (
            "local_direct_evidence_ready",
            "local_version_ready_count",
            "local_version_total_count",
            "production_strict_closeout_complete",
            "strict_closeout_done_count",
            "strict_closeout_remaining_count",
            "strict_closeout",
            "version_evidence_rows",
            "ltg_closure_rows",
            "production_complete",
            "can_close",
            "external_or_environment_blockers",
        ):
            self.assertIn(field, self.page)
        self.assertIn("commandCenterV1LocalRc.local_direct_evidence_ready === true", self.page)
        self.assertIn("commandCenterV1LocalRc.production_strict_closeout_complete === true", self.page)
        self.assertIn("v1StrictCloseoutDone === 14", self.page)
        self.assertIn("v1VersionEvidenceSourceRows.length || 7", self.page)

    def test_v01_to_v07_evidence_and_external_blockers_are_visible_without_greenwashing(self):
        for version in ("v0.1", "v0.2", "v0.3", "v0.4", "v0.5", "v0.6", "v0.7"):
            self.assertIn(f'"{version}"', self.page)
        self.assertIn("后端快照尚未提供该版本证据", self.page)
        self.assertIn("生产外部阻断组", self.panel)
        self.assertIn("后端快照尚未提供 external blocker groups，按未查收处理", self.panel)
        self.assertIn("provider / model / 真实 worker / signing / notarization / remote CI", self.panel)
        self.assertIn("不会因本地 RC ready 而涂绿", self.panel)
        self.assertIn('tone: v1ExternalBlockerGroups.length ? "bad" : "warn"', self.panel)

    def test_ltg12_isolation_is_completed_only_from_direct_evidence_and_keeps_trade_boundary(self):
        self.assertIn('String(row.id ?? row.goal ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "") === "LTG12"', self.page)
        self.assertIn("v1Ltg12Row.production_complete === true && v1Ltg12Row.can_close === true", self.page)
        self.assertIn("研究客户端隔离目标完成", self.panel)
        self.assertIn("研究客户端隔离证据待查收", self.panel)
        self.assertIn("真实交易仍是另立项目、未授权", self.panel)
        self.assertIn("没有 broker / order 路径", self.panel)

    def test_v1_panel_is_read_only_keyboard_focusable_and_mobile_readable(self):
        self.assertIn('aria-label="Command Center 3.0 v1.0 local release candidate closeout"', self.panel)
        self.assertIn("tabIndex={0}", self.panel)
        self.assertNotIn("<button", self.panel)
        self.assertNotIn("onClick=", self.panel)
        self.assertNotIn("postLtgNextAcceptanceLocalStep", self.panel)
        self.assertNotIn("postTushareDeepseekLinkageReview", self.panel)
        self.assertIn("本面板只读后端本地快照，没有新增按钮或 POST", self.panel)
        self.assertIn(".v1-closeout-panel:focus-visible", self.styles)
        self.assertIn(".v1-closeout-columns", self.styles)
        mobile_start = self.styles.index("@media (max-width: 760px)")
        self.assertIn(".v1-closeout-columns", self.styles[mobile_start:])
        self.assertIn("grid-template-columns: minmax(0, 1fr)", self.styles[mobile_start:])


if __name__ == "__main__":
    unittest.main()
