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

    def test_margin_etf_first_screen_shows_ordinary_quick_read_before_actions(self):
        card_start = self.page.index('title="ETF / 融资操作台"')
        plain_start = self.page.index('aria-label="margin etf ordinary plain conclusion"', card_start)
        quick_read_start = self.page.index('aria-label="margin etf ordinary first screen quick read"', card_start)
        mode_start = self.page.index('aria-label="margin etf mode layered live light boundary"', card_start)
        actions_start = self.page.index('aria-label="margin etf primary actions"', card_start)
        audit_start = self.page.index('aria-label="margin etf audit details"')
        plain_slice = self.page[plain_start:quick_read_start]
        quick_read_slice = self.page[quick_read_start:mode_start]

        self.assertLess(card_start, plain_start)
        self.assertLess(plain_start, quick_read_start)
        self.assertLess(card_start, quick_read_start)
        self.assertLess(quick_read_start, mode_start)
        self.assertLess(quick_read_start, actions_start)
        self.assertLess(quick_read_start, audit_start)
        self.assertIn("ordinaryPlainConclusion", self.page)
        self.assertIn("ordinaryPlainGap", self.page)
        self.assertIn("ordinaryPlainNow", self.page)
        self.assertIn("ordinaryPlainSafety", self.page)
        self.assertIn("ordinaryPlainItems", self.page)
        self.assertIn("普通结论", plain_slice)
        self.assertIn('aria-label="margin etf ordinary plain conclusion sentence"', plain_slice)
        self.assertIn("MetricGrid items={ordinaryPlainItems}", plain_slice)
        self.assertIn("还没有可读 ETF 候选；先看融资现金线，保持观察，不新增融资。", self.page)
        self.assertIn("当前有 ${allVisibleEtfRows.length} 行 ETF 候选", self.page)
        self.assertIn("ETF 候选只供研究，不是买入、加仓、加融资或下单指令。", self.page)
        for plain_label in (
            'label: "一句话"',
            'label: "缺口"',
            'label: "现在做什么"',
            'label: "安全说明"',
        ):
            self.assertIn(plain_label, self.page)
        self.assertIn("页面打开、查看结果和切换入口都不会自动创建任务、调用外部服务或改写交易策略", plain_slice)
        self.assertNotIn("onClick=", plain_slice)
        self.assertNotIn("postTask(", plain_slice)
        self.assertNotIn("fetch(", plain_slice)
        self.assertNotIn("packet", plain_slice)
        self.assertNotIn("task", plain_slice)
        self.assertIn("ordinaryQuickReadSummary", self.page)
        self.assertIn("ordinaryMissingEvidence", self.page)
        self.assertIn("ordinaryQuickReadItems", self.page)
        self.assertIn("现在能看什么", quick_read_slice)
        self.assertIn('aria-label="margin etf ordinary quick read summary"', quick_read_slice)
        self.assertIn("MetricGrid items={ordinaryQuickReadItems}", quick_read_slice)
        self.assertIn("当前没有可读 ETF 候选：先看本地快照状态和融资现金线", self.page)
        self.assertIn("当前可读 ${allVisibleEtfRows.length} 行 ETF 候选", self.page)
        for label in (
            'label: "现在能看"',
            'label: "数据来源"',
            'label: "融资动作"',
            'label: "先看哪儿"',
            'label: "缺什么"',
            'label: "不要做"',
        ):
            self.assertIn(label, self.page)
        self.assertIn("不要把 ETF 候选当买入、加仓或加融资指令", self.page)
        self.assertIn("不会新建任务、不会调用外部数据或模型服务、不会交易或改写策略", quick_read_slice)
        self.assertNotIn("onClick=", quick_read_slice)
        self.assertNotIn("postTask(", quick_read_slice)
        self.assertNotIn("fetch(", quick_read_slice)

    def test_margin_etf_local_refresh_result_quick_read_after_button(self):
        card_start = self.page.index('title="ETF / 融资操作台"')
        actions_start = self.page.index('aria-label="margin etf primary actions"', card_start)
        result_start = self.page.index('aria-label="margin etf local refresh result quick read"', actions_start)
        receipt_start = self.page.index("<TaskLaunchReceipt receipt={taskReceipt} />", result_start)
        audit_start = self.page.index('aria-label="margin etf audit details"')
        result_slice = self.page[result_start:receipt_start]

        self.assertLess(actions_start, result_start)
        self.assertLess(result_start, receipt_start)
        self.assertLess(result_start, audit_start)
        self.assertIn("localRefreshReadableSummary", self.page)
        self.assertIn("localRefreshResultItems", self.page)
        self.assertIn("localRefreshPayload.degraded_reason", self.page)
        self.assertIn("localRefreshPayload.scope_hash_short", self.page)
        self.assertIn("localRefreshPayload.etf_row_count", self.page)
        self.assertIn("(taskReceipt || taskSubmitting || taskError || taskId)", self.page)
        self.assertIn("刷新后结果", result_slice)
        self.assertIn('aria-label="margin etf local refresh result summary"', result_slice)
        self.assertIn("MetricGrid items={localRefreshResultItems}", result_slice)
        for label in (
            'label: "本地回执"',
            'label: "本地结果"',
            'label: "降级原因"',
            'label: "ETF 行数"',
            'label: "范围校验"',
            'label: "安全说明"',
        ):
            self.assertIn(label, self.page)
        self.assertIn("本地刷新已返回降级结果", self.page)
        self.assertIn("点击刷新/重建本地包后，这里会显示回执、降级原因、行数和安全说明。", self.page)
        self.assertIn("只读按钮返回的本地回执和本地审计记录", result_slice)
        self.assertIn("缺 ETF 或融资包时只显示降级原因", result_slice)
        self.assertIn("不会补外部数据、调用模型、交易或改写策略", result_slice)
        self.assertNotIn("onClick=", result_slice)
        self.assertNotIn("postTask(", result_slice)
        self.assertNotIn("fetch(", result_slice)

    def test_margin_etf_risk_card_is_first_screen_read_only(self):
        card_start = self.page.index('title="ETF / 融资操作台"')
        quick_read_start = self.page.index('aria-label="margin etf ordinary first screen quick read"', card_start)
        risk_card_start = self.page.index('aria-label="margin etf ordinary risk card"', card_start)
        mode_start = self.page.index('aria-label="margin etf mode layered live light boundary"', card_start)
        actions_start = self.page.index('aria-label="margin etf primary actions"', card_start)
        audit_start = self.page.index('aria-label="margin etf audit details"')
        risk_card = self.page[risk_card_start:mode_start]

        self.assertLess(quick_read_start, risk_card_start)
        self.assertLess(risk_card_start, mode_start)
        self.assertLess(risk_card_start, actions_start)
        self.assertLess(risk_card_start, audit_start)
        self.assertIn("marginEtfRiskCardStatus", self.page)
        self.assertIn("marginEtfRiskCardItems", self.page)
        self.assertIn("marginEtfRiskCardRows", self.page)
        self.assertIn("等待 ETF 候选：先看融资现金线，不新增融资。", self.page)
        self.assertIn("有 ETF 候选，但融资只允许现金优先、小额待条件。", self.page)
        self.assertIn("有 ETF 候选，但当前结论仍是不新增融资。", self.page)
        self.assertIn("ETF / 融资风险卡", risk_card)
        self.assertIn('aria-label="margin etf ordinary risk card summary"', risk_card)
        self.assertIn("{marginEtfRiskCardStatus}", risk_card)
        self.assertIn("MetricGrid items={marginEtfRiskCardItems}", risk_card)
        for label in (
            'label: "ETF 候选"',
            'label: "融资现金线"',
            'label: "风险口径"',
            'label: "缺口"',
            'label: "下一步"',
            'label: "禁令"',
        ):
            self.assertIn(label, self.page)
        self.assertIn('aria-label="margin etf ordinary risk card rows"', risk_card)
        self.assertIn("<summary>风险复核顺序</summary>", risk_card)
        self.assertIn("DataLineageTable rows={marginEtfRiskCardRows}", risk_card)
        self.assertIn('复核项: "1. ETF 候选"', self.page)
        self.assertIn('复核项: "2. 融资现金线"', self.page)
        self.assertIn('复核项: "3. 缺口"', self.page)
        self.assertIn('复核项: "4. 回流"', self.page)
        self.assertIn("候选只表示研究优先级，不是买入、加仓或加融资指令。", self.page)
        self.assertIn("融资比例不是加杠杆许可；缺数据时按保守处理。", self.page)
        self.assertIn("缺口只提示补证，不自动调用外部数据或模型。", self.page)
        self.assertIn("本地链接只切换页面，不创建任务、不交易、不改策略。", self.page)
        self.assertIn("风险卡只读本地 ETF/融资快照", risk_card)
        self.assertIn("ETF 候选不是买入指令", risk_card)
        self.assertIn("融资比例不是加杠杆许可", risk_card)
        self.assertIn("缺数据时按保守处理", risk_card)
        self.assertNotIn("onClick=", risk_card)
        self.assertNotIn("postTask(", risk_card)
        self.assertNotIn("fetch(", risk_card)
        self.assertNotIn("TaskStatusPanel", risk_card)

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
