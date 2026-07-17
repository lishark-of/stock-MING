import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "desktop" / "src" / "routes" / "MarginEtf.tsx"
STYLE = ROOT / "desktop" / "src" / "routes" / "MarginEtf.css"


class MarginEtfFocusFrontendTests(unittest.TestCase):
    def setUp(self):
        self.page = PAGE.read_text(encoding="utf-8")
        self.style = STYLE.read_text(encoding="utf-8")
        focus_start = self.page.index('<main className="margin-etf-focus"')
        details_start = self.page.index('<details className="margin-etf-technical-details', focus_start)
        self.focus = self.page[focus_start:details_start]
        self.details = self.page[details_start:]

    def test_focus_precedes_one_default_closed_technical_details_container(self):
        self.assertIn('import "./MarginEtf.css";', self.page)
        self.assertIn('aria-label="ETF 融资普通用户摘要"', self.focus)
        self.assertIn('aria-label="ETF 融资研究与技术详情"', self.details)
        opening_tag = self.details.split(">", 1)[0]
        self.assertNotIn(" open", opening_tag)
        self.assertIn("完整候选表、回放操作、记录和审计信息默认收起", self.details)

    def test_focus_has_exactly_five_categories_and_one_next_step(self):
        self.assertEqual(self.focus.count('data-focus-category="'), 5)
        for category in ("cash-risk", "core-etfs", "guardrails", "freshness", "next-step"):
            self.assertIn(f'data-focus-category="{category}"', self.focus)
        self.assertEqual(self.focus.count("<a "), 1)
        self.assertIn('href={DATA_CAPABILITY_HREF}', self.focus)
        self.assertNotIn("<button", self.focus)
        self.assertNotIn("onClick=", self.focus)
        self.assertNotIn("postTask", self.focus)

    def test_focus_hides_engineering_language_and_full_tables(self):
        for forbidden in (
            "DataLineageTable",
            "TaskStatusPanel",
            "TaskLaunchReceipt",
            "call_ledger",
            "schema_version",
            "LTG",
            "P1",
            "P2",
            "P3",
        ):
            self.assertNotIn(forbidden, self.focus)
        self.assertIn("DataLineageTable", self.details)
        self.assertIn("TaskStatusPanel", self.details)

    def test_current_values_require_same_packet_date_and_freshness_binding(self):
        for required in (
            "same_margin_etf_packet_date_bound",
            "same_packet_date_bound",
            '"command_center_etf_packet"',
            '"command_center_margin_packet"',
            "task_id",
            "result_version",
            "data_date",
            "expected_trade_date",
            "usable_for_risk_budget === true",
            '["fresh", "current", "today"]',
            "calendar_validated === true",
            "marginEtfFocusDataDate === marginEtfFocusExpectedTradeDate",
            "marginEtfFocusBindingsMatch",
            "marginEtfMarginBinding.usable_for_risk_budget === true",
            "marginEtfMarginBinding.calendar_validated === true",
        ):
            self.assertIn(required, self.page)
        self.assertIn("marginEtfFocusCurrentEvidenceUsable", self.page)
        self.assertIn('? percent(recommendedCashRatio)\n    : "--"', self.page)
        self.assertIn("当前不展示历史 ETF 名单", self.focus)
        self.assertIn("数据待确认；不开放融资判断", self.page)

    def test_focus_never_promotes_research_to_trading_or_financing_instruction(self):
        self.assertIn("研究结论不等于执行许可", self.focus)
        self.assertIn("不能把 ETF 候选、比例或强弱描述转换成买入、加仓、融资、下单或策略动作", self.focus)
        self.assertIn("当前不展示历史 ETF 名单，也不据此生成买入或融资动作", self.focus)
        self.assertNotIn("建议买入", self.focus)
        self.assertNotIn("立即融资", self.focus)

    def test_route_style_is_scoped_responsive_and_reduced_motion_safe(self):
        self.assertIn(".margin-etf-focus {", self.style)
        self.assertNotIn("body {", self.style)
        self.assertNotIn("#root {", self.style)
        self.assertIn("@media (max-width: 860px)", self.style)
        self.assertIn("@media (max-width: 520px)", self.style)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.style)
        self.assertIn("overflow-wrap: break-word", self.style)
        self.assertNotIn("overflow-wrap: anywhere", self.style)


if __name__ == "__main__":
    unittest.main()
