import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "desktop" / "src" / "routes" / "FactorQuantHub.tsx"
STYLES = ROOT / "desktop" / "src" / "routes" / "FactorQuantHub.css"


class FactorQuantFocusFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROUTE.read_text(encoding="utf-8")
        cls.styles = STYLES.read_text(encoding="utf-8")
        cls.focus_start = cls.source.index('<section id="factor-score" className="factor-focus-dashboard"')
        cls.details_start = cls.source.index('<details className="factor-research-details">', cls.focus_start)
        cls.focus = cls.source[cls.focus_start:cls.details_start]

    def test_first_view_is_a_human_factor_snapshot(self):
        for visible_copy in (
            "当前标的量化结论",
            "当前标的",
            "综合得分",
            "正向因素",
            "负向因素",
            "样本日期",
            "因子覆盖",
            "当前限制",
            "下一步",
            "查看次日图谱",
            "确认或更换标的",
        ):
            self.assertIn(visible_copy, self.focus)

        self.assertIn("factorFocusConclusion", self.focus)
        self.assertIn("factorFocusSupportFactors", self.focus)
        self.assertIn("factorFocusSuppressFactors", self.focus)
        self.assertIn("factorFocusNeutralFactors", self.focus)
        self.assertIn("factorFocusMissingFactors", self.focus)
        self.assertIn('href={NEXT_SESSION_CHART_HREF}', self.focus)
        self.assertIn('href={CANDIDATE_CONFIRM_HREF}', self.focus)
        self.assertNotIn("onClick=", self.focus)
        self.assertNotIn("post" + "Task(", self.focus)
        self.assertNotIn("launch" + "Task", self.focus)

    def test_engineering_surfaces_are_default_closed_after_focus(self):
        details_tag_end = self.source.index(">", self.details_start)
        details_tag = self.source[self.details_start:details_tag_end]
        self.assertNotIn(" open", details_tag)
        self.assertIn("研究与审计详情", self.source[self.details_start:])
        self.assertIn("factor-research-details__content", self.source[self.details_start:])
        self.assertLess(self.focus_start, self.details_start)
        self.assertLess(self.details_start, self.source.index("DataLineageTable", self.details_start))
        self.assertLess(self.details_start, self.source.index("TaskStatusPanel", self.details_start))
        self.assertLess(self.details_start, self.source.index("JsonDetails", self.details_start))

        for engineering_copy in (
            "metric contract",
            "call_ledger",
            "schema_version",
            "task_type",
            "promotion",
            "receipt",
            "raw_value",
        ):
            self.assertNotIn(engineering_copy, self.focus)

    def test_factor_names_cover_current_packet_shapes(self):
        helper_start = self.source.index("function factorDisplayName")
        helper_end = self.source.index("type FactorTaskLike", helper_start)
        helper = self.source[helper_start:helper_end]
        for field in ("factor_name", "display_name", "label", "title", "name", "factor_key"):
            self.assertIn(f"row.{field}", helper)

    def test_stale_or_not_ready_evidence_cannot_show_directional_conclusion(self):
        self.assertIn('freshnessGate.usable_for_score === false', self.source)
        self.assertIn('"stale"', self.source)
        self.assertIn('"expired"', self.source)
        self.assertIn('"not_ready"', self.source)
        self.assertIn('"blocked"', self.source)
        self.assertIn('state.includes("not_ready")', self.source)
        self.assertIn('state.endsWith("_blocked")', self.source)
        self.assertIn('factorFocusFreshnessBlocked ? "--" : factorFocusScoreLabel', self.source)
        self.assertIn('factorFocusFreshnessBlocked ? 0 : factorFocusScorePercent', self.source)
        self.assertIn('factorFocusFreshnessBlocked ? "历史 / 不可用"', self.source)
        self.assertIn("旧分数和因子覆盖只作历史回看，不能作为当前结论", self.source)
        conclusion_start = self.source.index("const factorFocusConclusion =")
        conclusion_end = self.source.index("const factorFocusTone", conclusion_start)
        conclusion = self.source[conclusion_start:conclusion_end]
        self.assertLess(conclusion.index("factorFocusFreshnessBlocked"), conclusion.index("factorFocusSupportBands"))
        self.assertIn('"数据待更新"', conclusion)

    def test_styles_are_route_scoped_and_small_viewport_safe(self):
        self.assertIn(".factor-focus-dashboard", self.styles)
        self.assertIn(".factor-research-details", self.styles)
        self.assertIn("@media (max-width: 430px)", self.styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.styles)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", self.styles)
        self.assertNotRegex(self.styles, re.compile(r"(?m)^\s*(body|:root|html|#root)\s*\{"))
        self.assertNotIn("overflow-wrap: anywhere", self.styles)


if __name__ == "__main__":
    unittest.main()
