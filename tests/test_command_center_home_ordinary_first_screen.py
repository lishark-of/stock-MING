from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "desktop" / "src" / "routes" / "CommandCenterHome.tsx"
HOME_CSS = ROOT / "desktop" / "src" / "routes" / "CommandCenterHome.css"


class CommandCenterHomeOrdinaryFirstScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = HOME.read_text(encoding="utf-8")
        cls.css = HOME_CSS.read_text(encoding="utf-8")
        start = cls.source.index('className="home-ordinary-dashboard"')
        end = cls.source.index('className="home-research-technical-details', start)
        cls.visible = cls.source[start:end]

    def test_first_screen_keeps_only_the_five_user_categories(self) -> None:
        for expected in (
            "当前标的",
            "数据日期",
            "当前结论",
            "确认研究标的",
            "市场与新鲜度",
            "仅作研究辅助，不下单、不改交易策略",
        ):
            self.assertIn(expected, self.visible)
        for engineering_surface in ("<MetricGrid", "<DataLineageTable", "<TaskLaunchReceipt", "LTG", "P0–P6"):
            self.assertNotIn(engineering_surface, self.visible)

    def test_research_and_engineering_surfaces_are_closed_by_default(self) -> None:
        details_start = self.source.index('className="home-research-technical-details')
        summary = self.source.index("<summary>研究与技术详情</summary>", details_start)
        first_metric = self.source.index("<MetricGrid", summary)
        self.assertLess(summary, first_metric)
        self.assertNotIn(" open", self.source[details_start:summary])
        self.assertIn(
            ".home-research-technical-details:not([open]) > :not(summary)",
            self.css,
        )

    def test_stale_or_unverified_data_fails_closed(self) -> None:
        self.assertIn("!ordinaryHomeFreshnessIsFresh", self.source)
        self.assertIn("本轮不按今日数据展示", self.source)
        self.assertIn('ordinaryHomeFirstScreenActionHref = !dailyCommandNeedsStartupRecovery && !ordinaryHomeFreshnessIsFresh', self.source)
        self.assertIn('"#dataHealth"', self.source)

    def test_input_is_silent_and_only_primary_action_reuses_existing_handlers(self) -> None:
        self.assertIn('id="home-p1-symbol-confirm"', self.visible)
        self.assertIn('title="输入只做本地校验"', self.visible)
        self.assertIn("ordinaryHomeFirstScreenActionKind === \"refresh\" ? refreshHomeResearchReadback : launchHomeQuantProjection", self.visible)
        self.assertNotIn("postCandidateRadarQuantProjection(", self.visible)

    def test_mobile_and_reduced_motion_contracts_are_route_scoped(self) -> None:
        self.assertIn("@media (max-width: 760px)", self.css)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", self.css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertIn(".home-ordinary-dashboard *", self.css)


if __name__ == "__main__":
    unittest.main()
