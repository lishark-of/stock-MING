import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "desktop" / "src" / "routes" / "QmtReplayLab.tsx"
ROUTE_STYLES = ROOT / "desktop" / "src" / "routes" / "QmtReplayLab.css"
ORDINARY_GATE = ROOT / "desktop" / "src" / "routes" / "qmtReplayOrdinaryGate.ts"


class QmtReplayProductSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = ROUTE.read_text(encoding="utf-8")
        cls.styles = ROUTE_STYLES.read_text(encoding="utf-8")
        cls.gate = ORDINARY_GATE.read_text(encoding="utf-8")

    def test_ordinary_surface_has_exactly_five_user_facing_blocks(self):
        self.assertIn('import "./QmtReplayLab.css";', self.page)
        self.assertEqual(self.page.count("data-qmt-ordinary-block="), 5)
        for block in ("safety", "source", "controls", "timeline", "result"):
            self.assertIn(f'data-qmt-ordinary-block="{block}"', self.page)

    def test_raw_evidence_is_inside_default_closed_technical_details(self):
        details = self.page.index('className="qmt-technical-details developer-audit-details"')
        closing = self.page.index("</details>", details)
        technical = self.page[details:closing]
        self.assertNotIn(" open", self.page[details:details + 120])
        for token in (
            "<MetricGrid",
            "<DataLineageTable rows={lineageRows}",
            "<TaskLaunchReceipt",
            "<TaskStatusPanel",
            "<DataLineageTable rows={virtualResearchEvents}",
            "call ledger / warnings / raw status",
        ):
            self.assertIn(token, technical)
        ordinary = self.page[self.page.index("return ("):details]
        self.assertNotIn("<TaskLaunchReceipt", ordinary)
        self.assertNotIn("<TaskStatusPanel", ordinary)
        self.assertNotIn("<MetricGrid", ordinary)
        self.assertIn("cache_error: cacheError", technical)
        self.assertIn("submit_error: submitError", technical)
        self.assertNotIn("本次未生成：{submitError}", ordinary)

    def test_ordinary_copy_never_presents_replay_as_broker_or_order_execution(self):
        details = self.page.index('className="qmt-technical-details developer-audit-details"')
        ordinary = self.page[self.page.index("return ("):details]
        self.assertIn("全程不触达交易系统", ordinary)
        self.assertIn("不是订单、成交或持仓动作", ordinary)
        self.assertIn("不产生交易动作", ordinary)
        self.assertNotIn("连接 QMT 并", ordinary)
        self.assertNotIn("创建订单", ordinary.replace("不会连接券商、创建订单", ""))

    def test_timeline_has_compact_visual_and_accessible_text_equivalent(self):
        self.assertIn("visibleResearchEvents = virtualResearchEvents.slice(0, 8)", self.page)
        self.assertIn('aria-label="QMT local virtual research event track"', self.page)
        self.assertIn('className="qmt-timeline-table"', self.page)
        self.assertIn("本地研究事件等价文本", self.page)
        self.assertIn("researchStateLabel", self.page)

    def test_result_has_a_plain_language_receipt_without_raw_task_identity(self):
        self.assertIn('className="qmt-result-receipt task-panel--receipt"', self.page)
        self.assertIn("本地研究演示已接收，结果会在当前页面更新", self.page)

    def test_status_tone_is_fail_closed_for_not_ready(self):
        self.assertIn("not_ready|not_available", self.page)
        self.assertIn('new Set(["ready", "success", "succeeded", "passed", "match", "preserved", "fresh"])', self.page)
        self.assertNotIn("/ready|success|passed|match/i", self.page)
        self.assertIn('new Set(["fresh", "current", "today"])', self.gate)
        self.assertIn("freshness.expected_trade_date_calendar_validated === true", self.gate)
        self.assertIn("dataDate === expectedDataDate", self.gate)
        self.assertIn("candidateLineage.dataDate === nextLineage.dataDate", self.gate)
        self.assertNotIn("/fresh|today/i", self.page)

    def test_unexpected_external_activity_blocks_the_local_replay_boundary(self):
        self.assertIn("const externalCallsTriggered =", self.page)
        self.assertIn("const safetyExplicitSafe = qmtGate.safetyReady && qmtGate.ledgersReady", self.page)
        self.assertIn("function envelopeLedgerSafe", self.gate)
        self.assertIn("function qmtBoundarySafe", self.gate)
        self.assertIn("function qmtPayloadLedgerSafe", self.gate)
        self.assertIn('row.api === "frontend_fastapi_request"', self.gate)
        self.assertIn("QMT_FALSE_FIELDS.every((field) => row[field] === false)", self.gate)
        self.assertIn("QMT_ZERO_FIELDS.every((field) => row[field] === 0)", self.gate)
        self.assertIn("QMT_TRUE_FIELDS.every((field) => row[field] === true)", self.gate)
        self.assertIn("frontend[0].endpoint === spec.endpoint", self.gate)
        self.assertIn("backend[0].call_status === spec.backendCallStatus", self.gate)
        self.assertIn("const safetyUnknown = !unsafeBoundary && !safetyExplicitSafe", self.page)
        for token in (
            "qmt_external_connection_attempted",
            "broker_session_opened",
            "account_query_executed",
            "real_order_submitted",
            "real_trade_executed",
            "real_holdings_modified",
        ):
            self.assertIn(token, self.gate)
        self.assertIn("approved && qmtGate.launchReady && !submitting", self.page)

    def test_unknown_isolation_never_claims_disconnected_or_allows_launch(self):
        self.assertIn("连接与交易隔离证据不完整｜已停止本地回放", self.page)
        self.assertIn("缺失或未知不会被解释成安全", self.page)
        self.assertIn('safetyUnknown ? "安全证据待确认"', self.page)
        self.assertNotIn("QMT未连接｜券商未连接", self.page)

    def test_historical_replay_requires_exact_current_lineage(self):
        self.assertIn("const qmtResultBound = qmtGate.resultReady", self.page)
        self.assertIn('qmtStatus === "ready_cache_replay"', self.gate)
        self.assertIn("qmtSourceReady", self.gate)
        self.assertIn("qmtResultIntegrityReady", self.gate)
        self.assertIn("const resultReady = baseReady", self.gate)
        self.assertIn("const rawVirtualEvents = qmtResultBound ? rawVirtualEventsUnbound : []", self.page)
        for token in (
            "strictQmtSymbol(source.source_symbol) === candidateLineage.symbol",
            "strictQmtId(source.source_task_id) === candidateLineage.taskId",
            "strictQmtId(source.source_result_version) === candidateLineage.resultVersion",
            "strictQmtScope(source.source_scope_hash) === candidateLineage.scopeHash",
            "strictQmtDate(source.source_data_date) === candidateLineage.dataDate",
        ):
            self.assertIn(token, self.gate)

    def test_route_css_has_mobile_and_reduced_motion_contracts(self):
        self.assertIn("@media (max-width: 420px)", self.styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.styles)
        self.assertIn("grid-template-columns: 1fr;", self.styles)
        self.assertIn("overflow-x: auto;", self.styles)
        self.assertIn("animation-duration: 0.001ms !important;", self.styles)
        self.assertIn("outline: 3px solid var(--qmt-accent)", self.styles)


if __name__ == "__main__":
    unittest.main()
