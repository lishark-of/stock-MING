from pathlib import Path
import unittest


class CandidateRadarFocusFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.page = (root / "desktop" / "src" / "routes" / "CandidateRadar.tsx").read_text(encoding="utf-8")
        cls.styles = (root / "desktop" / "src" / "routes" / "CandidateRadar.css").read_text(encoding="utf-8")

    def test_focus_dashboard_precedes_default_closed_research_details(self) -> None:
        focus_start = self.page.index('aria-label="下一票雷达简洁工作台"')
        details_start = self.page.index('aria-label="下一票雷达研究与审计详情"')
        self.assertLess(focus_start, details_start)
        details_tag = self.page[self.page.rfind("<details", 0, details_start):details_start]
        self.assertNotIn(" open", details_tag)

    def test_first_screen_contains_only_the_user_decision_surfaces(self) -> None:
        focus_start = self.page.index('aria-label="下一票雷达简洁工作台"')
        details_start = self.page.index('aria-label="下一票雷达研究与审计详情"')
        focus = self.page[focus_start:details_start]

        for text in (
            "输入股票代码",
            "当前候选",
            "TOP",
            "WATCH",
            "EXCLUDED",
            "数据新鲜度",
            "下一步",
        ):
            self.assertIn(text, focus)

        for engineering_surface in (
            "DataLineageTable",
            "TaskStatusPanel",
            "JsonDetails",
            "call_ledger",
            "task_type",
            "schema_version",
            "production blocker",
        ):
            self.assertNotIn(engineering_surface, focus)

    def test_first_screen_preserves_button_gated_boundary(self) -> None:
        focus_start = self.page.index('aria-label="下一票雷达简洁工作台"')
        details_start = self.page.index('aria-label="下一票雷达研究与审计详情"')
        focus = self.page[focus_start:details_start]
        self.assertIn('renderQuantProjectionPrimaryAction("candidate-focus-symbol-help")', focus)
        self.assertIn("输入只做本地校验，不会自动刷新外部数据", focus)
        self.assertNotIn("postCandidateRadar", focus)
        self.assertNotIn("launchQuickScan", focus)

    def test_styles_are_route_scoped_and_responsive(self) -> None:
        self.assertIn(".candidate-focus-dashboard", self.styles)
        self.assertIn(".candidate-research-details", self.styles)
        self.assertIn("@media (max-width: 720px)", self.styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.styles)
        self.assertNotIn("\nbody {", self.styles)
        self.assertNotIn("\n:root {", self.styles)


if __name__ == "__main__":
    unittest.main()
