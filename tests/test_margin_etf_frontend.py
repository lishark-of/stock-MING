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

    def test_margin_etf_candidate_row_reading_guide_explains_each_visible_row(self):
        table_start = self.page.index('title="ETF 候选分组"')
        guide_start = self.page.index('aria-label="margin etf candidate row reading guide"', table_start)
        table_rows_start = self.page.index("DataLineageTable rows={allVisibleEtfRows}", guide_start)
        audit_start = self.page.index('aria-label="margin etf audit details"')
        guide = self.page[guide_start:table_rows_start]

        self.assertLess(table_start, guide_start)
        self.assertLess(guide_start, table_rows_start)
        self.assertLess(guide_start, audit_start)
        self.assertIn("marginEtfCandidateReadingSummary", self.page)
        self.assertIn("marginEtfCandidateReadingItems", self.page)
        self.assertIn("marginEtfCandidateReadingRows", self.page)
        self.assertIn("每行怎么读", guide)
        self.assertIn('aria-label="margin etf candidate row reading summary"', guide)
        self.assertIn("MetricGrid items={marginEtfCandidateReadingItems}", guide)
        self.assertIn('aria-label="margin etf candidate row reading rows"', guide)
        self.assertIn("<summary>查看逐行读法</summary>", guide)
        self.assertIn("DataLineageTable rows={marginEtfCandidateReadingRows}", guide)
        for label in (
            'label: "逐行读法"',
            'label: "状态含义"',
            'label: "风险核对"',
            'label: "缺口处理"',
            'label: "边界"',
        ):
            self.assertIn(label, self.page)
        self.assertIn("推荐=优先复核；观察=等触发；回避/排除=不要追高", self.page)
        self.assertIn("流动性、同类重叠、现金/杠杆必须一起看", self.page)
        self.assertIn("ETF 行只是风险预算参考，不是买入、加仓、加融资或下单指令", self.page)
        self.assertIn("怎么读", self.page)
        self.assertIn("风险核对", self.page)
        self.assertIn("缺数据时保持观察，不新增融资、不追高、不下单", self.page)
        self.assertIn("逐行读法只重排本地候选行", guide)
        self.assertIn("不刷新外部数据、不启动刷新流程、不交易", guide)
        self.assertIn("推荐不是买入，观察不是加仓，回避/排除不是反向交易信号", guide)
        self.assertNotIn("onClick=", guide)
        self.assertNotIn("postTask(", guide)
        self.assertNotIn("fetch(", guide)
        self.assertNotIn("TaskStatusPanel", guide)

    def test_margin_etf_page_keeps_render_and_local_replay_boundaries(self):
        self.assertIn("getBootstrapStatus", self.page)
        self.assertIn("runtimeModeLabel", self.page)
        self.assertIn("cache_only（只读缓存，不外联）", self.page)
        self.assertIn("live_light（轻量后台口径，页面渲染仍不外联）", self.page)
        self.assertIn("页面打开只读本地快照", self.page)
        self.assertIn("不会自动全量发现 ETF", self.page)
        self.assertIn("不刷新外部数据或模型", self.page)
        self.assertIn("不下单", self.page)
        self.assertIn("不把 ETF 候选写成买入或加融资指令", self.page)
        self.assertIn("/api/market/margin-etf-local-refresh", self.page)
        self.assertIn("local_packet_replay", self.page)
        self.assertNotIn("/api/bootstrap/live-startup", self.page)
        self.assertNotIn("postBootstrapLiveStartup", self.page)

    def test_margin_etf_first_screen_shows_ordinary_quick_read_before_actions(self):
        card_start = self.page.index('title="ETF / 融资操作台"')
        plain_start = self.page.index('aria-label="margin etf ordinary plain conclusion"', card_start)
        viewport_action_start = self.page.index('aria-label="margin etf first viewport action strip"', card_start)
        quick_read_start = self.page.index('aria-label="margin etf ordinary first screen quick read"', card_start)
        mode_start = self.page.index('aria-label="margin etf mode layered live light boundary"', card_start)
        actions_start = self.page.index('aria-label="margin etf primary actions"', card_start)
        audit_start = self.page.index('aria-label="margin etf audit details"')
        plain_slice = self.page[plain_start:viewport_action_start]
        quick_read_slice = self.page[quick_read_start:mode_start]

        self.assertLess(card_start, plain_start)
        self.assertLess(plain_start, viewport_action_start)
        self.assertLess(viewport_action_start, quick_read_start)
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
        self.assertIn("页面打开、查看结果和切换入口都不会启动刷新流程、刷新外部数据或模型、改写交易策略", plain_slice)
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
        self.assertIn("不会启动刷新流程、不会调用外部数据或模型服务、不会交易或改写策略", quick_read_slice)
        self.assertNotIn("onClick=", quick_read_slice)
        self.assertNotIn("postTask(", quick_read_slice)
        self.assertNotIn("fetch(", quick_read_slice)

    def test_margin_etf_first_viewport_risk_summary_card_combines_etf_and_cash_line(self):
        card_start = self.page.index('title="ETF / 融资操作台"')
        plain_start = self.page.index('aria-label="margin etf ordinary plain conclusion"', card_start)
        risk_start = self.page.index('aria-label="margin etf first viewport risk summary card"', card_start)
        action_start = self.page.index('aria-label="margin etf first viewport action strip"', card_start)
        visible_start = self.page.index('aria-label="margin etf app visible now summary"', card_start)
        primary_actions_start = self.page.index('aria-label="margin etf primary actions"', card_start)
        audit_start = self.page.index('aria-label="margin etf audit details"')
        risk_slice = self.page[risk_start:action_start]

        self.assertLess(plain_start, risk_start)
        self.assertLess(risk_start, action_start)
        self.assertLess(risk_start, visible_start)
        self.assertLess(risk_start, primary_actions_start)
        self.assertLess(risk_start, audit_start)
        self.assertIn("marginEtfFirstViewportRiskSentence", self.page)
        self.assertIn("marginEtfFirstViewportRiskItems", self.page)
        self.assertIn("首屏风险卡：暂无 ETF 候选", self.page)
        self.assertIn("首屏风险卡：${allVisibleEtfRows.length} 行 ETF 候选只做风险预算参考", self.page)
        self.assertIn("ETF / 融资一屏风险卡", risk_slice)
        self.assertIn('aria-label="margin etf first viewport risk sentence"', risk_slice)
        self.assertIn("MetricGrid items={marginEtfFirstViewportRiskItems}", risk_slice)
        for label in (
            'label: "候选/现金线"',
            'label: "缺口读法"',
            'label: "禁令"',
        ):
            self.assertIn(label, self.page)
        self.assertIn("ETF 候选暂无；融资现金线 当前", self.page)
        self.assertIn("ETF 候选 ${allVisibleEtfRows.length} 行；融资现金线 当前", self.page)
        self.assertIn("ETF 候选不是买入指令；融资比例不是加杠杆许可", self.page)
        self.assertIn("这张风险卡只合成本地 ETF 候选、融资现金线和缺口", risk_slice)
        self.assertIn("不启动刷新流程、不刷新外部数据或模型、不交易、不加融资", risk_slice)
        self.assertNotIn("onClick=", risk_slice)
        self.assertNotIn("postTask(", risk_slice)
        self.assertNotIn("fetch(", risk_slice)
        self.assertNotIn("TaskStatusPanel", risk_slice)

    def test_margin_etf_app_visible_now_summary_is_first_screen_read_only(self):
        card_start = self.page.index('title="ETF / 融资操作台"')
        audit_start = self.page.index('aria-label="margin etf audit details"')
        quick_read_start = self.page.index('aria-label="margin etf ordinary first screen quick read"', card_start)
        visible_start = self.page.index('aria-label="margin etf app visible now summary"', card_start)
        risk_card_start = self.page.index('aria-label="margin etf ordinary risk card"', card_start)
        actions_start = self.page.index('aria-label="margin etf primary actions"', card_start)
        visible_slice = self.page[visible_start:risk_card_start]
        source_before_audit = self.page[:audit_start]

        self.assertLess(quick_read_start, visible_start)
        self.assertLess(visible_start, risk_card_start)
        self.assertLess(visible_start, actions_start)
        self.assertLess(visible_start, audit_start)
        self.assertIn("marginEtfAppVisibleNowSentence", source_before_audit)
        self.assertIn("marginEtfAppVisibleNowItems", source_before_audit)
        self.assertIn("DATA_CAPABILITY_HREF", source_before_audit)
        self.assertIn("打开 app 能看到 ETF/融资的降级等待态", source_before_audit)
        self.assertIn("打开 app 能看到 ${allVisibleEtfRows.length} 行 ETF 候选", source_before_audit)
        for label in (
            'label: "打开可见"',
            'label: "ETF 候选"',
            'label: "融资现金线"',
            'label: "来源层"',
            'label: "数据能力"',
            'label: "明确降级"',
            'label: "下一步入口"',
            'label: "安全边界"',
        ):
            self.assertIn(label, source_before_audit)
        self.assertIn("ETF/融资缺口去数据能力页复核真实数据、权限、空窗口和本地结果状态", source_before_audit)
        self.assertIn("打开 app 能看到什么", visible_slice)
        self.assertIn('aria-label="margin etf app visible now sentence"', visible_slice)
        self.assertIn("{marginEtfAppVisibleNowSentence}", visible_slice)
        self.assertIn("MetricGrid items={marginEtfAppVisibleNowItems}", visible_slice)
        self.assertIn('aria-label="margin etf app visible now local actions"', visible_slice)
        self.assertIn('href="#candidates"', visible_slice)
        self.assertIn('href="#risk"', visible_slice)
        self.assertIn('href={DATA_CAPABILITY_HREF}', visible_slice)
        self.assertIn('href="#home"', visible_slice)
        self.assertIn("看数据能力", visible_slice)
        self.assertIn("这个条带只回答普通用户打开页面能看到什么", visible_slice)
        self.assertIn("普通链接只切换本地页面", visible_slice)
        self.assertIn("不启动刷新流程、不刷新外部数据或模型、不交易、不加融资", visible_slice)
        self.assertNotIn("onClick=", visible_slice)
        self.assertNotIn("postTask(", visible_slice)
        self.assertNotIn("fetch(", visible_slice)
        self.assertNotIn("TaskStatusPanel", visible_slice)

    def test_margin_etf_first_viewport_action_strip_links_to_local_sections(self):
        card_start = self.page.index('title="ETF / 融资操作台"')
        plain_start = self.page.index('aria-label="margin etf ordinary plain conclusion"', card_start)
        quick_read_start = self.page.index('aria-label="margin etf ordinary first screen quick read"', card_start)
        visible_start = self.page.index('aria-label="margin etf app visible now summary"', card_start)
        action_start = self.page.index('aria-label="margin etf first viewport action strip"', card_start)
        post_research_start = self.page.index('aria-label="margin etf post research risk path"', card_start)
        primary_actions_start = self.page.index('aria-label="margin etf primary actions"', card_start)
        audit_start = self.page.index('aria-label="margin etf audit details"')
        action_slice = self.page[action_start:quick_read_start]

        self.assertLess(plain_start, action_start)
        self.assertLess(action_start, quick_read_start)
        self.assertLess(action_start, visible_start)
        self.assertLess(action_start, post_research_start)
        self.assertLess(action_start, primary_actions_start)
        self.assertLess(action_start, audit_start)
        self.assertIn("marginEtfFirstViewportActionSentence", self.page)
        self.assertIn("marginEtfFirstViewportActionItems", self.page)
        self.assertIn("首屏下一步：先看融资现金线", self.page)
        self.assertIn("首屏下一步：先看 ${allVisibleEtfRows.length} 行 ETF 候选", self.page)
        self.assertIn("首屏下一步", action_slice)
        self.assertIn('aria-label="margin etf first viewport action sentence"', action_slice)
        self.assertIn("MetricGrid items={marginEtfFirstViewportActionItems}", action_slice)
        for label in (
            'label: "先点哪里"',
            'label: "看 ETF"',
            'label: "看现金线"',
            'label: "刷新方式"',
            'label: "边界"',
        ):
            self.assertIn(label, self.page)
        self.assertIn('aria-label="margin etf first viewport local links"', action_slice)
        self.assertIn('href="#margin-etf-candidate-rows"', action_slice)
        self.assertIn('href="#margin-etf-cash-line"', action_slice)
        self.assertIn('href="#margin-etf-local-refresh-actions"', action_slice)
        self.assertIn('href="#candidates"', action_slice)
        self.assertIn('href={DATA_CAPABILITY_HREF}', action_slice)
        self.assertIn('id="margin-etf-candidate-rows"', self.page)
        self.assertIn('id="margin-etf-cash-line"', self.page)
        self.assertIn('id="margin-etf-local-refresh-actions"', self.page)
        self.assertIn("首屏操作条只做本地锚点跳转", action_slice)
        self.assertIn("不会自动刷新 ETF、不会调用 Tushare/DeepSeek/GitHub、不会创建 task", action_slice)
        self.assertIn("不会交易或改写策略", action_slice)
        self.assertNotIn("onClick=", action_slice)
        self.assertNotIn("postTask(", action_slice)
        self.assertNotIn("fetch(", action_slice)
        self.assertNotIn("TaskStatusPanel", action_slice)

    def test_margin_etf_post_research_risk_path_is_first_screen_read_only(self):
        card_start = self.page.index('title="ETF / 融资操作台"')
        visible_start = self.page.index('aria-label="margin etf app visible now summary"', card_start)
        post_research_start = self.page.index('aria-label="margin etf post research risk path"', card_start)
        bridge_start = self.page.index('aria-label="margin etf candidate radar risk budget bridge"', card_start)
        actions_start = self.page.index('aria-label="margin etf primary actions"', card_start)
        audit_start = self.page.index('aria-label="margin etf audit details"')
        post_research = self.page[post_research_start:bridge_start]

        self.assertLess(visible_start, post_research_start)
        self.assertLess(post_research_start, bridge_start)
        self.assertLess(post_research_start, actions_start)
        self.assertLess(post_research_start, audit_start)
        self.assertIn("marginEtfPostResearchRiskPathSentence", self.page)
        self.assertIn("marginEtfPostResearchRiskPathItems", self.page)
        self.assertIn("marginEtfPostResearchRiskPathRows", self.page)
        self.assertIn("从量化推演或次日图谱过来后", self.page)
        self.assertIn("确认结果后查风险预算", post_research)
        self.assertIn('aria-label="margin etf post research risk path sentence"', post_research)
        self.assertIn("MetricGrid items={marginEtfPostResearchRiskPathItems}", post_research)
        for label in (
            'label: "来自结果"',
            'label: "先看 ETF"',
            'label: "再看现金线"',
            'label: "缺口"',
            'label: "回流入口"',
            'label: "边界"',
        ):
            self.assertIn(label, self.page)
        self.assertIn('aria-label="margin etf post research risk path actions"', post_research)
        self.assertIn('href="#factor/factor-score"', post_research)
        self.assertIn('href="#next/next-session-chart"', post_research)
        self.assertIn('href={DATA_CAPABILITY_HREF}', post_research)
        self.assertIn('href="#candidates"', post_research)
        self.assertIn('href="#risk"', post_research)
        self.assertIn('aria-label="margin etf post research risk path rows"', post_research)
        self.assertIn("<summary>查看结果到风险预算路径</summary>", post_research)
        self.assertIn("DataLineageTable rows={marginEtfPostResearchRiskPathRows}", post_research)
        for row in (
            '步骤: "1. 从结果页过来"',
            '步骤: "2. 看 ETF 候选"',
            '步骤: "3. 看融资现金线"',
            '步骤: "4. 处理缺口"',
            '步骤: "5. 回到主路径"',
        ):
            self.assertIn(row, self.page)
        self.assertIn("不把量化结果、ETF 强弱或融资比例变成买入、加仓、加融资或下单指令", self.page)
        self.assertIn("不启动刷新流程、不刷新外部数据或模型、不交易", post_research)
        self.assertIn("ETF 候选不是买入，融资比例不是加杠杆许可，缺数据按保守处理", post_research)
        self.assertNotIn("onClick=", post_research)
        self.assertNotIn("postTask(", post_research)
        self.assertNotIn("fetch(", post_research)
        self.assertNotIn("TaskStatusPanel", post_research)

    def test_margin_etf_candidate_bridge_is_first_screen_read_only(self):
        card_start = self.page.index('title="ETF / 融资操作台"')
        visible_start = self.page.index('aria-label="margin etf app visible now summary"', card_start)
        post_research_start = self.page.index('aria-label="margin etf post research risk path"', card_start)
        bridge_start = self.page.index('aria-label="margin etf candidate radar risk budget bridge"', card_start)
        cash_line_start = self.page.index('aria-label="margin etf cash line quick read"', card_start)
        risk_card_start = self.page.index('aria-label="margin etf ordinary risk card"', card_start)
        actions_start = self.page.index('aria-label="margin etf primary actions"', card_start)
        audit_start = self.page.index('aria-label="margin etf audit details"')
        bridge = self.page[bridge_start:cash_line_start]

        self.assertLess(visible_start, bridge_start)
        self.assertLess(visible_start, post_research_start)
        self.assertLess(post_research_start, bridge_start)
        self.assertLess(bridge_start, cash_line_start)
        self.assertLess(cash_line_start, risk_card_start)
        self.assertLess(bridge_start, actions_start)
        self.assertLess(bridge_start, audit_start)
        self.assertIn("marginEtfCandidateBridgeSentence", self.page)
        self.assertIn("marginEtfCandidateBridgeItems", self.page)
        self.assertIn("marginEtfCandidateBridgeRows", self.page)
        self.assertIn("从下一票雷达跳过来后，先看融资现金线和缺口", self.page)
        self.assertIn("从下一票雷达跳过来后，先把 ${allVisibleEtfRows.length} 行 ETF 候选当风险预算参考", self.page)
        self.assertIn("从候选页过来怎么看", bridge)
        self.assertIn('aria-label="margin etf candidate bridge sentence"', bridge)
        self.assertIn("MetricGrid items={marginEtfCandidateBridgeItems}", bridge)
        for label in (
            'label: "候选承接"',
            'label: "先看风险"',
            'label: "融资口径"',
            'label: "缺口处理"',
            'label: "回到候选"',
            'label: "安全边界"',
        ):
            self.assertIn(label, self.page)
        self.assertIn('aria-label="margin etf candidate bridge local actions"', bridge)
        self.assertIn('aria-label="return candidate radar from margin etf bridge"', bridge)
        self.assertIn('aria-label="open risk guardrails from margin etf bridge"', bridge)
        self.assertIn('aria-label="open home from margin etf bridge"', bridge)
        self.assertIn('href="#candidates"', bridge)
        self.assertIn('href="#risk"', bridge)
        self.assertIn('href="#home"', bridge)
        self.assertIn('aria-label="margin etf candidate bridge rows"', bridge)
        self.assertIn("<summary>查看承接顺序</summary>", bridge)
        self.assertIn("DataLineageTable rows={marginEtfCandidateBridgeRows}", bridge)
        self.assertIn('步骤: "1. 从候选页过来"', self.page)
        self.assertIn('步骤: "2. 看 ETF 替代风险"', self.page)
        self.assertIn('步骤: "3. 看融资现金线"', self.page)
        self.assertIn('步骤: "4. 回流"', self.page)
        self.assertIn("融资比例不是加杠杆许可", self.page)
        self.assertIn("普通链接只切换本地页面，不刷新外部数据、不启动刷新流程、不交易、不改策略", bridge)
        self.assertNotIn("onClick=", bridge)
        self.assertNotIn("postTask(", bridge)
        self.assertNotIn("fetch(", bridge)
        self.assertNotIn("TaskStatusPanel", bridge)

    def test_margin_etf_cash_line_quick_read_is_first_screen_read_only(self):
        card_start = self.page.index('title="ETF / 融资操作台"')
        bridge_start = self.page.index('aria-label="margin etf candidate radar risk budget bridge"', card_start)
        cash_line_start = self.page.index('aria-label="margin etf cash line quick read"', card_start)
        risk_card_start = self.page.index('aria-label="margin etf ordinary risk card"', card_start)
        actions_start = self.page.index('aria-label="margin etf primary actions"', card_start)
        audit_start = self.page.index('aria-label="margin etf audit details"')
        cash_line = self.page[cash_line_start:risk_card_start]

        self.assertLess(bridge_start, cash_line_start)
        self.assertLess(cash_line_start, risk_card_start)
        self.assertLess(cash_line_start, actions_start)
        self.assertLess(cash_line_start, audit_start)
        self.assertIn("marginEtfCashLineSentence", self.page)
        self.assertIn("marginEtfCashLineItems", self.page)
        self.assertIn("marginEtfCashLineRows", self.page)
        self.assertIn("融资现金线显示仍要现金优先", self.page)
        self.assertIn("融资现金线当前结论是不新增融资", self.page)
        self.assertIn("融资现金线怎么读", cash_line)
        self.assertIn('aria-label="margin etf cash line sentence"', cash_line)
        self.assertIn("MetricGrid items={marginEtfCashLineItems}", cash_line)
        for label in (
            'label: "当前融资"',
            'label: "建议融资"',
            'label: "现金缓冲"',
            'label: "读法"',
            'label: "缺口"',
            'label: "禁令"',
        ):
            self.assertIn(label, self.page)
        self.assertIn('aria-label="margin etf cash line local actions"', cash_line)
        self.assertIn('href="#candidates"', cash_line)
        self.assertIn('href={DATA_CAPABILITY_HREF}', cash_line)
        self.assertIn('href="#risk"', cash_line)
        self.assertIn('aria-label="margin etf cash line rows"', cash_line)
        self.assertIn("<summary>查看现金线读法</summary>", cash_line)
        self.assertIn("DataLineageTable rows={marginEtfCashLineRows}", cash_line)
        for row in (
            '读法: "1. 当前融资"',
            '读法: "2. 建议融资"',
            '读法: "3. 现金缓冲"',
            '读法: "4. 回流复核"',
        ):
            self.assertIn(row, self.page)
        self.assertIn("缺数据按保守处理", cash_line)
        self.assertIn("ETF 强弱不能变成买入、加仓、加融资或下单指令", cash_line)
        self.assertIn("不会刷新外部数据、不启动刷新流程、不交易、不改策略", cash_line)
        self.assertNotIn("onClick=", cash_line)
        self.assertNotIn("postTask(", cash_line)
        self.assertNotIn("fetch(", cash_line)
        self.assertNotIn("TaskStatusPanel", cash_line)

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
        self.assertIn("缺 ETF 或融资本地快照时只显示降级原因", result_slice)
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
        self.assertIn("本地链接只切换页面，不启动刷新流程、不交易、不改策略。", self.page)
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
        self.assertIn("把本地快照、按钮刷新、数据证据、旧入口退场和交易隔离分开看", mode_slice)
        self.assertIn("live_light 也只能是可审计后台流程，不是页面渲染外联", mode_slice)
        self.assertIn("modeLayerItems", self.page)
        for label in (
            'label: "本地读取层"',
            'label: "按钮刷新层"',
            'label: "数据证据层"',
            'label: "旧入口退场层"',
            'label: "交易隔离层"',
        ):
            self.assertIn(label, self.page)
        self.assertIn("本地快照和运行状态只读", self.page)
        self.assertIn("页面打开、React render 和本地链接不启动刷新流程", self.page)
        self.assertIn("刷新/重建本地包只走用户点击后的本地流程，不刷新外部数据或模型", self.page)
        self.assertIn("缺 ETF 或融资数据只显示 degraded，不当作无风险，也不自动补外部数据", self.page)
        self.assertIn("不打开 Streamlit，不移除 fallback，不把本地回放当 LTG-10 strict closeout", self.page)
        self.assertIn("ETF 候选和融资比例只供研究复核；不接券商、不下单、不改交易策略", self.page)
        self.assertNotIn("onClick=", mode_slice)
        self.assertNotIn("postTask(", mode_slice)


if __name__ == "__main__":
    unittest.main()
