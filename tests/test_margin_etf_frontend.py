import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "desktop" / "src" / "routes" / "MarginEtf.tsx"


class MarginEtfFrontendTests(unittest.TestCase):
    def setUp(self):
        self.page = PAGE.read_text(encoding="utf-8")

    def test_visible_etf_rows_show_evidence_quality_without_audit_details(self):
        table_start = self.page.index('title="ETF 候选分组"')
        audit_start = self.page.index('aria-label="margin etf audit details"')
        ordinary_slice = self.page[table_start:audit_start]

        self.assertIn("function chainValue", self.page)
        self.assertIn("evidence_chain", self.page)
        self.assertIn('chainValue(row, "liquidity", row.liquidity_text)', self.page)
        self.assertIn('chainValue(row, "overlap", row.holding_overlap || row.overlap_risk)', self.page)
        self.assertIn('chainValue(row, "margin_cash", row.margin_guardrail || row.cash_buffer)', self.page)
        self.assertIn("状态: text(row.status_label || row.state || row.action_state", self.page)
        self.assertIn("来源: text(row.source, fallbackSource)", self.page)
        self.assertIn("理由: text(row.reason || row.trigger_condition || row.evidence_chain_summary || row.risk_note", self.page)
        self.assertIn("边界: text(row.action_guardrail", self.page)
        self.assertIn("流动性", ordinary_slice)
        self.assertIn("重叠", ordinary_slice)
        self.assertIn("现金/杠杆", ordinary_slice)
        self.assertIn("所有 ETF 行都不是买入、加仓或加融资指令", ordinary_slice)

    def test_margin_etf_page_keeps_render_and_local_replay_boundaries(self):
        self.assertIn("页面打开只读本地 packet", self.page)
        self.assertIn("不会自动全量发现 ETF", self.page)
        self.assertIn("不调用 Tushare/DeepSeek/GitHub", self.page)
        self.assertIn("不下单", self.page)
        self.assertIn("不把 ETF 候选写成买入或加融资指令", self.page)
        self.assertIn("/api/market/margin-etf-local-refresh", self.page)
        self.assertIn("local_packet_replay", self.page)


if __name__ == "__main__":
    unittest.main()
