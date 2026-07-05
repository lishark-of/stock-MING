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
        self.assertIn("getBootstrapStatus", self.page)
        self.assertIn("runtimeModeLabel", self.page)
        self.assertIn("cache_only（只读缓存，不外联）", self.page)
        self.assertIn("live_light（轻量 task 口径，页面渲染仍不外联）", self.page)
        self.assertIn("页面打开只读本地 packet", self.page)
        self.assertIn("不会自动全量发现 ETF", self.page)
        self.assertIn("不调用 Tushare/DeepSeek/GitHub", self.page)
        self.assertIn("不下单", self.page)
        self.assertIn("不把 ETF 候选写成买入或加融资指令", self.page)
        self.assertIn("/api/market/margin-etf-local-refresh", self.page)
        self.assertIn("local_packet_replay", self.page)
        self.assertNotIn("/api/bootstrap/live-startup", self.page)
        self.assertNotIn("postBootstrapLiveStartup", self.page)

    def test_margin_etf_mode_layers_are_visible_before_actions_and_read_only(self):
        card_start = self.page.index('title="ETF / 融资操作台"')
        actions_start = self.page.index('aria-label="margin etf primary actions"', card_start)
        audit_start = self.page.index('aria-label="margin etf audit details"')
        mode_start = self.page.index('aria-label="margin etf mode layered live light boundary"', card_start)
        mode_slice = self.page[mode_start:actions_start]

        self.assertLess(card_start, mode_start)
        self.assertLess(mode_start, actions_start)
        self.assertLess(mode_start, audit_start)
        self.assertIn("运行模式分层", mode_slice)
        self.assertIn("把本地 packet、按钮任务、数据证据、旧入口退场和交易隔离分开看", mode_slice)
        self.assertIn("live_light 也只能是可审计 task，不是页面渲染外联", mode_slice)
        self.assertIn("modeLayerItems", self.page)
        for label in (
            'label: "缓存渲染层"',
            'label: "按钮任务层"',
            'label: "数据证据层"',
            'label: "旧入口退场层"',
            'label: "交易隔离层"',
        ):
            self.assertIn(label, self.page)
        self.assertIn("GET packet + bootstrap status 只读", self.page)
        self.assertIn("页面打开、React render 和本地链接不创建 task", self.page)
        self.assertIn("刷新/重建本地包只创建 local_packet_replay POST task，不调用 provider/model", self.page)
        self.assertIn("缺 ETF 或融资数据只显示 degraded，不当作无风险，也不自动补调 Tushare", self.page)
        self.assertIn("不打开 Streamlit，不移除 fallback，不把本地 packet 回放当 LTG-10 strict closeout", self.page)
        self.assertIn("ETF 候选和融资比例只供研究复核；不接 broker、不创建 order endpoint", self.page)
        self.assertNotIn("onClick=", mode_slice)
        self.assertNotIn("postTask(", mode_slice)


if __name__ == "__main__":
    unittest.main()
