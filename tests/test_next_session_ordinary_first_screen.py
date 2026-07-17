from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "desktop" / "src" / "routes" / "NextSessionMap.tsx"
PAGE_CSS = ROOT / "desktop" / "src" / "routes" / "NextSessionMap.css"
CHART = ROOT / "desktop" / "src" / "components" / "NextSessionChart.tsx"
GATE = ROOT / "desktop" / "src" / "routes" / "nextSessionOrdinaryGate.ts"


class NextSessionOrdinaryFirstScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PAGE.read_text(encoding="utf-8")
        cls.css = PAGE_CSS.read_text(encoding="utf-8")
        cls.chart = CHART.read_text(encoding="utf-8")
        cls.gate = GATE.read_text(encoding="utf-8")
        start = cls.source.index('className="next-session-ordinary-dashboard"')
        end = cls.source.index('className="next-session-research-technical-details"', start)
        cls.visible = cls.source[start:end]

    def test_first_screen_has_only_the_five_user_categories(self) -> None:
        for label in (
            "当前标的",
            "数据日期",
            "次日路径",
            "支撑参考",
            "压力参考",
            "触发观察",
            "失效条件",
            "仅作研究辅助，不下单、不改任何研究结论",
        ):
            self.assertIn(label, self.visible)
        for engineering_surface in (
            "<MetricGrid",
            "<DataLineageTable",
            "<TaskLaunchReceipt",
            "LTG-",
            "P0",
            "operation_zones",
            "fail-closed",
            "strategy action",
            "历史 close",
        ):
            self.assertNotIn(engineering_surface, self.visible)

    def test_chart_is_bound_to_same_packet_symbol_task_date_and_freshness(self) -> None:
        self.assertIn("evaluateNextSessionOrdinaryGate", self.source)
        self.assertIn('CURRENT_FRESHNESS = new Set(["fresh", "current", "today"])', self.gate)
        self.assertIn("freshness.expected_trade_date_calendar_validated === true", self.gate)
        self.assertIn("strictOrdinaryDate", self.gate)
        self.assertIn("strictOrdinarySymbol", self.gate)
        self.assertIn("strictOrdinaryScopeHash", self.gate)
        self.assertIn("lineageSymbol === payloadSymbol", self.gate)
        self.assertIn("lineageSymbol === summarySymbol", self.gate)
        self.assertIn("!input.loading && input.error ===", self.gate)
        self.assertIn("input.cacheEnvelopeWarnings", self.gate)
        self.assertIn("input.taskEnvelopeWarnings", self.gate)
        self.assertIn("input.packet.warnings", self.gate)
        self.assertIn("chart.warnings", self.gate)
        self.assertIn("const ordinaryNextSessionChartPayload = ordinaryNextSessionChartReady ? chartPayload : undefined", self.source)
        self.assertIn("旧图、日期不明、日历未验证或仍有提示的结果都不会作为次日结论", self.source)
        self.assertIn("<NextSessionChart payload={ordinaryNextSessionChartPayload} ordinary />", self.visible)

    def test_page_open_is_read_only_and_runtime_renders_one_primary_action(self) -> None:
        self.assertEqual(self.visible.count('className="next-session-ordinary-primary-action"'), 1)
        self.assertIn("initialLayoutLoading || loading", self.visible)
        self.assertIn("!candidateRadarConfirmedSymbol", self.visible)
        self.assertIn("!ordinaryNextSessionChartReady", self.visible)
        self.assertIn("onClick={() => void refreshCache()}", self.visible)
        self.assertIn("只刷新本地只读状态", self.visible)
        self.assertIn("刷新本地图谱状态", self.visible)
        self.assertNotIn("launchTask", self.visible)
        self.assertNotIn("postTask(", self.visible)
        self.assertNotIn("getCandidateRadarCache(", self.visible)

    def test_raw_and_engineering_surfaces_are_closed_by_default(self) -> None:
        details_start = self.source.index('className="next-session-research-technical-details"')
        summary = self.source.index("<summary>研究与技术详情</summary>", details_start)
        first_metric = self.source.index("<MetricGrid", summary)
        self.assertNotIn(" open", self.source[details_start:summary])
        self.assertLess(summary, first_metric)
        self.assertIn(
            ".next-session-research-technical-details:not([open]) > :not(summary)",
            self.css,
        )

    def test_ordinary_chart_hides_raw_legends_and_engineering_strips(self) -> None:
        self.assertIn("ordinary = false", self.chart)
        self.assertIn("!ordinary ? <ChartSafetyStrip", self.chart)
        self.assertIn("!ordinary && (referenceLegend.length || operationLegend.length)", self.chart)
        self.assertIn("!ordinary && selectedInsight", self.chart)
        self.assertIn("onChartClick={ordinary ? undefined : handleChartClick}", self.chart)
        self.assertIn('const historicalSeriesName = ordinary ? "近期走势" : "历史 close"', self.chart)

    def test_mobile_and_reduced_motion_are_route_scoped(self) -> None:
        self.assertIn("@media (max-width: 760px)", self.css)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", self.css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertIn(".next-session-ordinary-dashboard *", self.css)


if __name__ == "__main__":
    unittest.main()
