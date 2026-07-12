import unittest
from pathlib import Path


class CandidateRadarOrdinaryEntryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.page = (self.root / "desktop" / "src" / "routes" / "CandidateRadar.tsx").read_text(
            encoding="utf-8"
        )
        self.handoff = (self.root / "docs" / "codex_handoff_protocol.md").read_text(
            encoding="utf-8"
        )
        self.task_status_panel = (
            self.root / "desktop" / "src" / "components" / "TaskStatusPanel.tsx"
        ).read_text(encoding="utf-8")

    def test_candidate_radar_has_ordinary_user_summary_before_audit_details(self):
        self.assertIn("<h1>下一票雷达</h1>", self.page)
        self.assertIn('title="普通用户雷达摘要"', self.page)
        self.assertIn('title="下一票候选池"', self.page)
        self.assertIn('title="搜票量化推演"', self.page)
        self.assertIn("生成 3.0 量化推演", self.page)
        operator_start = self.page.index('title="下一票雷达操作台"')
        operator_end = self.page.index('title="普通用户雷达摘要"', operator_start)
        page_state_start = self.page.index("<PageStateBanner")
        operator_slice = self.page[operator_start:operator_end]
        self.assertLess(operator_start, page_state_start)
        self.assertLess(self.page.index('title="普通用户雷达摘要"'), page_state_start)
        self.assertLess(page_state_start, self.page.index('title="下一票候选池"'))
        self.assertIn("candidateRadarCompactVerticalSliceItems", self.page)
        self.assertIn('aria-label="candidate radar compact vertical slice status"', operator_slice)
        self.assertIn("当前纵切状态", operator_slice)
        self.assertIn("输入、确认、最近结果、候选池和缺口先给结论", operator_slice)
        for compact_label in (
            'label: "输入到确认"',
            'label: "结果回放"',
            'label: "候选池"',
            'label: "降级/缺口"',
            'label: "边界"',
        ):
            self.assertIn(compact_label, self.page)
        self.assertIn("无 active degraded；缺口：", self.page)
        self.assertIn("只做本地投研证据回放；不是买入/卖出/加仓指令", self.page)
        self.assertLess(
            operator_slice.index('aria-label="candidate radar compact operator actions"'),
            operator_slice.index("MetricGrid"),
        )
        self.assertLess(
            operator_slice.index('aria-label="candidate radar compact operator actions"'),
            operator_slice.index('aria-label="candidate radar compact vertical slice status"'),
        )
        self.assertIn('aria-label="candidate radar operator input confirm first sentence"', operator_slice)
        self.assertIn("输入确认速读：输入只做本地校验", operator_slice)
        self.assertIn("确认后看最近结果、候选池、量化推演、次日图谱和 ETF/融资风险", operator_slice)
        self.assertLess(
            operator_slice.index('aria-label="candidate radar operator input confirm first sentence"'),
            operator_slice.index('aria-label="candidate radar compact operator actions"'),
        )
        self.assertIn('aria-label="candidate radar operator symbol input"', operator_slice)
        self.assertIn("renderQuantProjectionPrimaryAction(candidateRadarOperatorSubmitHelpId)", operator_slice)
        self.assertIn("查看最近结果", self.page)
        self.assertIn("刷新本地回放", operator_slice)
        compact_actions_start = operator_slice.index('aria-label="candidate radar compact operator actions"')
        compact_actions_end = operator_slice.index("</div>", compact_actions_start)
        compact_actions_slice = operator_slice[compact_actions_start:compact_actions_end]
        self.assertIn('href="#factor/factor-score"', compact_actions_slice)
        self.assertIn('href="#next/next-session-chart"', compact_actions_slice)
        self.assertIn("candidateRadarOperatorPostConfirmOneGlanceItems", self.page)
        self.assertIn('aria-label="candidate radar operator post confirm one glance result"', operator_slice)
        self.assertIn("确认后马上看这里", operator_slice)
        self.assertIn('aria-label="candidate radar operator post confirm one glance sentence"', operator_slice)
        self.assertIn("MetricGrid items={ordinaryUserMetricItems(candidateRadarOperatorPostConfirmOneGlanceItems)}", operator_slice)
        self.assertIn("candidateRadarPostConfirmDataCapabilitySentence", self.page)
        self.assertIn("candidateRadarPostConfirmDataCapabilityItems", self.page)
        self.assertIn('aria-label="candidate radar post confirm data capability card"', operator_slice)
        self.assertIn("确认后数据能力", operator_slice)
        self.assertIn('aria-label="candidate radar post confirm data capability sentence"', operator_slice)
        self.assertIn("MetricGrid items={ordinaryUserMetricItems(candidateRadarPostConfirmDataCapabilityItems)}", operator_slice)
        self.assertIn('aria-label="candidate radar operator post confirm one glance actions"', operator_slice)
        self.assertIn("操作台确认后结果条只读本地确认记录、本地缓存、数据记录和结果包", operator_slice)
        operator_post_confirm_start = operator_slice.index('aria-label="candidate radar operator post confirm one glance result"')
        operator_post_confirm_end = operator_slice.index('aria-label="candidate radar operator input confirm first read"', operator_post_confirm_start)
        operator_post_confirm_slice = operator_slice[operator_post_confirm_start:operator_post_confirm_end]
        for operator_post_confirm_label in (
            'label: "任务接收"',
            'label: "P2/P3"',
            'label: "下一步入口"',
            'label: "数据卡状态"',
            'label: "运行模式"',
            'label: "证据血缘"',
            'label: "补证缺口"',
            'label: "结果旁边看"',
            'label: "安全边界"',
        ):
            self.assertIn(operator_post_confirm_label, self.page)
        self.assertIn('href="#tasks"', operator_post_confirm_slice)
        self.assertIn('href={DATA_CAPABILITY_HREF}', operator_post_confirm_slice)
        self.assertIn('href="#factor/factor-score"', operator_post_confirm_slice)
        self.assertIn('href="#next/next-session-chart"', operator_post_confirm_slice)
        self.assertIn('href="#marginEtf"', operator_post_confirm_slice)
        self.assertIn("真实数据补证仍需单独授权；本页不会自动补调", self.page)
        self.assertIn("数据能力页只读；不创建后台流程、不刷新外部数据或模型、不交易", self.page)
        self.assertIn("不会创建第二个后台流程，不交易、不改交易策略", operator_post_confirm_slice)
        self.assertNotIn("onClick=", operator_post_confirm_slice)
        self.assertNotIn("postCandidateRadar", operator_post_confirm_slice)
        self.assertNotIn("launchQuantProjection", operator_post_confirm_slice)
        self.assertIn('aria-label="candidate radar operator input confirm first read"', operator_slice)
        self.assertIn("输入确认速读", operator_slice)
        self.assertIn("输入股票后先看本地校验和确认按钮", operator_slice)
        self.assertIn("确认后再看最近结果、候选池、量化推演、次日图谱和 ETF/融资风险", operator_slice)
        self.assertIn("MetricGrid items={candidateRadarVisibleNowItems}", operator_slice)
        self.assertIn('aria-label="candidate radar operator input confirm first read links"', operator_slice)
        self.assertIn('aria-label="open confirm input from operator first read"', operator_slice)
        self.assertIn('aria-label="open candidate pool from operator first read"', operator_slice)
        self.assertIn('aria-label="open factor from operator first read"', operator_slice)
        self.assertIn('aria-label="open next session from operator first read"', operator_slice)
        self.assertIn('aria-label="open margin etf from operator first read"', operator_slice)
        self.assertIn("操作台速读只读本地页面状态", operator_slice)
        operator_first_read_start = operator_slice.index('aria-label="candidate radar operator input confirm first read"')
        operator_first_read_end = operator_slice.index('aria-label="candidate radar single ticket closed loop"', operator_first_read_start)
        operator_first_read_slice = operator_slice[operator_first_read_start:operator_first_read_end]
        self.assertNotIn("onClick=", operator_first_read_slice)
        self.assertNotIn("postCandidateRadar", operator_first_read_slice)
        self.assertNotIn("launchQuantProjection", operator_first_read_slice)
        self.assertLess(
            operator_slice.index('aria-label="candidate radar compact operator actions"'),
            operator_post_confirm_start,
        )
        self.assertLess(operator_post_confirm_start, operator_first_read_start)
        self.assertIn("candidateRadarCompactLeadCandidateItems", self.page)
        self.assertIn("candidateRadarCompactOperatorSubtitle", self.page)
        self.assertIn("candidateRadarCompactRecentResultText", self.page)
        self.assertIn("candidateRadarCompactResultStatusLabel", self.page)
        self.assertIn("candidateRadarCompactGroupStatusLabel", self.page)
        self.assertIn("candidateRadarCompactResultGroupItems", self.page)
        self.assertIn("最近：${candidateRadarCompactResultStatusLabel}", self.page)
        self.assertIn("先看一票：", self.page)
        self.assertIn("缺口：${candidatePoolLeadCandidateGap}", self.page)
        self.assertIn("Top/Watch/Excluded 理由见下方速读", self.page)
        self.assertIn("候选池暂无候选；Top/Watch/Excluded 暂无理由；${candidatePoolPlainConclusionMissing}", self.page)
        self.assertIn("等待候选缓存；Top/Watch/Excluded 暂无理由；先确认一只股票或刷新本地回放", self.page)
        self.assertIn("本地回放已接上，但候选池暂无候选；先看来源和缺口，再回确认输入区解释单票。", self.page)
        self.assertIn("缺 Top / Watch / Excluded 候选；不是本地连接故障", self.page)
        self.assertIn("回确认输入区解释单票，或等待下一次按钮门控快扫补候选", self.page)
        self.assertIn('subtitle={candidateRadarCompactOperatorSubtitle}', operator_slice)
        self.assertIn('aria-label="candidate radar compact result and group bridge"', operator_slice)
        self.assertIn("结果和分组一屏速读", operator_slice)
        self.assertIn("最近结果、Top/Watch/Excluded 理由、来源和缺口先合成一张短卡", operator_slice)
        self.assertIn("MetricGrid items={ordinaryUserMetricItems(candidateRadarCompactResultGroupItems)}", operator_slice)
        self.assertIn('aria-label="candidate radar single ticket closed loop"', operator_slice)
        self.assertIn("单票闭环", operator_slice)
        self.assertIn('aria-label="candidate radar single ticket closed loop sentence"', operator_slice)
        self.assertIn("MetricGrid items={ordinaryUserMetricItems(candidateRadarSingleTicketLoopItems)}", operator_slice)
        self.assertIn('aria-label="candidate radar single ticket closed loop actions"', operator_slice)
        self.assertIn('href="#candidate-pool"', operator_slice)
        self.assertIn('href="#candidate-radar-search-quant-projection"', operator_slice)
        self.assertIn('href="#tasks"', operator_slice)
        self.assertIn('href="#factor/factor-score"', operator_slice)
        self.assertIn('href="#next/next-session-chart"', operator_slice)
        self.assertIn('href="#marginEtf"', operator_slice)
        self.assertIn("不提交、不重试、不刷新外部数据或模型、不改交易策略", operator_slice)
        self.assertEqual(self.page.count('aria-label="candidate radar single ticket closed loop"'), 1)
        self.assertIn('aria-label="candidate radar compact lead candidate result"', operator_slice)
        self.assertIn("首位候选速读", operator_slice)
        self.assertIn('aria-label="candidate radar compact lead candidate sentence"', operator_slice)
        self.assertIn("MetricGrid items={candidateRadarCompactLeadCandidateItems}", operator_slice)
        self.assertIn("candidateRadarCompactGroupDecisionItems", self.page)
        self.assertIn("candidateRadarGroupBriefRow", self.page)
        self.assertIn("candidateRadarGroupBriefText", self.page)
        self.assertIn('aria-label="candidate radar compact top watch excluded reasons"', operator_slice)
        self.assertIn("分组理由速读", operator_slice)
        self.assertIn("Top 先复核，Watch 只观察，Excluded 是排除或等待", operator_slice)
        self.assertIn("MetricGrid items={candidateRadarCompactGroupDecisionItems}", operator_slice)
        single_ticket_start = operator_slice.index('aria-label="candidate radar single ticket closed loop"')
        bridge_start = operator_slice.index('aria-label="candidate radar compact result and group bridge"', single_ticket_start)
        bridge_end = operator_slice.index('aria-label="candidate radar compact lead candidate result"', bridge_start)
        single_ticket_end = bridge_start
        bridge_slice = operator_slice[bridge_start:bridge_end]
        single_ticket_slice = operator_slice[single_ticket_start:single_ticket_end]
        compact_lead_start = operator_slice.index('aria-label="candidate radar compact lead candidate result"')
        compact_lead_end = operator_slice.index('aria-label="candidate radar compact vertical slice status"', compact_lead_start)
        compact_lead_slice = operator_slice[compact_lead_start:compact_lead_end]
        for bridge_label in (
            'label: "最近结果"',
            'label: "分组理由"',
            'label: "来源/缺口"',
            'label: "下一步"',
            'label: "边界"',
        ):
            self.assertIn(bridge_label, self.page)
        self.assertIn("结果和分组只做研究复核；不买卖、不加仓、不交易", self.page)
        self.assertNotIn("onClick=", bridge_slice)
        self.assertNotIn("postCandidateRadar", bridge_slice)
        self.assertNotIn("launchQuantProjection", bridge_slice)
        self.assertNotIn("onClick=", single_ticket_slice)
        self.assertNotIn("postCandidateRadar", single_ticket_slice)
        self.assertNotIn("launchQuantProjection", single_ticket_slice)
        for compact_lead_label in (
            'label: "先看一票"',
            'label: "分组/评分"',
            'label: "来源/缺口"',
            'label: "下一步"',
            'label: "边界"',
            'label: "Top 先看"',
            'label: "Watch 观察"',
            'label: "Excluded 排除/等待"',
            'label: "评分理由"',
        ):
            self.assertIn(compact_lead_label, self.page)
        self.assertIn("理由待补", self.page)
        self.assertIn("分组只决定复核顺序；不是买入、卖出、加仓或清仓指令", self.page)
        self.assertIn("首位候选只是复核对象；不预填、不提交、不买入", self.page)
        self.assertIn("candidatePoolLeadReviewSentence", compact_lead_slice)
        self.assertNotIn("onClick=", compact_lead_slice)
        self.assertNotIn("postCandidateRadar", compact_lead_slice)
        self.assertNotIn("launchQuantProjection", compact_lead_slice)
        self.assertLess(
            operator_slice.index('aria-label="candidate radar compact operator actions"'),
            operator_first_read_start,
        )
        self.assertLess(
            operator_first_read_start,
            single_ticket_start,
        )
        self.assertLess(
            single_ticket_start,
            bridge_start,
        )
        self.assertLess(
            bridge_start,
            compact_lead_start,
        )
        self.assertLess(
            compact_lead_start,
            operator_slice.index('aria-label="candidate radar compact vertical slice status"'),
        )

        for required_label in (
            'label: "下一步"',
            'label: "主下一步"',
            'label: "主下一步边界"',
            'label: "P0 交接"',
            'label: "P1 主路径"',
            'label: "P1 主路径边界"',
            'label: "P2 三面"',
            'label: "候选分组"',
            'label: "扫描范围"',
            'label: "候选来源"',
            'label: "评分说明"',
            'label: "可选补证"',
            'label: "本地缓存"',
            'label: "数据链"',
            'label: "解释状态"',
            'label: "待补证据"',
            'label: "降级提示"',
            'label: "最近成功回放"',
            'label: "缺少证据"',
            'label: "阻断/降级"',
            'label: "最近可用缓存"',
            'label: "任务边界"',
            'label: "仅供研究"',
        ):
            self.assertIn(required_label, self.page)
        summary_start = self.page.index('title="普通用户雷达摘要"')
        summary_end = self.page.index('title="下一票候选池"', summary_start)
        summary_slice = self.page[summary_start:summary_end]
        for engineering_label in (
            'label: "cache"',
            'label: "Tushare"',
            'label: "DeepSeek"',
            'label: "pending"',
            'label: "degraded"',
            'label: "last_successful_cache/result"',
        ):
            self.assertNotIn(engineering_label, summary_slice)
        self.assertIn('aria-label="candidate radar ordinary summary extra details"', summary_slice)
        self.assertIn("<summary>摘要细节</summary>", summary_slice)
        summary_extra_start = summary_slice.index('aria-label="candidate radar ordinary summary extra details"')
        summary_extra_end = summary_slice.index('aria-label="candidate radar first screen quant projection confirmation"', summary_extra_start)
        summary_primary_slice = summary_slice[:summary_extra_start]
        summary_extra_slice = summary_slice[summary_extra_start:summary_extra_end]
        self.assertIn("candidateRadarUserFirstItems", self.page)
        self.assertIn('aria-label="candidate radar ordinary user first summary"', summary_primary_slice)
        self.assertIn("一屏确认", summary_primary_slice)
        self.assertIn("默认先看现在做什么、输入状态、确认按钮、最近结果、下一步入口和边界", summary_primary_slice)
        self.assertIn('label: "现在做什么"', self.page)
        self.assertIn('label: "输入状态"', self.page)
        self.assertIn('label: "最近结果"', self.page)
        self.assertIn('label: "下一步入口"', self.page)
        self.assertIn('label: "边界"', self.page)
        self.assertIn("candidateRadarVisibleNowItems", self.page)
        self.assertIn("DATA_CAPABILITY_HREF", self.page)
        self.assertIn('aria-label="candidate radar visible now app result"', summary_primary_slice)
        self.assertIn("打开 app 能看到什么", summary_primary_slice)
        self.assertIn("这张速读只合成当前本地页面状态", summary_primary_slice)
        self.assertIn('label: "现在能看到"', self.page)
        self.assertIn('label: "现在能操作"', self.page)
        self.assertIn('label: "现在能跳转"', self.page)
        self.assertIn('label: "来源层"', self.page)
        self.assertIn('label: "数据能力"', self.page)
        self.assertIn('label: "还缺什么"', self.page)
        self.assertIn('label: "不会发生"', self.page)
        self.assertIn("真实数据、权限、空窗口或本地结果缺口去数据能力页复核", self.page)
        self.assertIn("候选池 / 搜票确认 / 量化推演 / 次日图谱 / ETF 融资风险", self.page)
        self.assertIn("页面打开、搜索输入和本地跳转不会启动确认流程、不会刷新外部数据或模型、不会交易", self.page)
        visible_now_start = summary_primary_slice.index('aria-label="candidate radar visible now app result"')
        visible_now_end = summary_primary_slice.index('aria-label="candidate radar typed symbol immediate readback"', visible_now_start)
        visible_now_slice = summary_primary_slice[visible_now_start:visible_now_end]
        self.assertIn('aria-label="candidate radar visible now app result actions"', visible_now_slice)
        self.assertIn('href="#candidate-pool"', visible_now_slice)
        self.assertIn('href="#candidate-radar-search-quant-projection"', visible_now_slice)
        self.assertIn('href={DATA_CAPABILITY_HREF}', visible_now_slice)
        self.assertIn('href="#marginEtf"', visible_now_slice)
        self.assertNotIn("onClick=", visible_now_slice)
        self.assertNotIn("postCandidateRadar", visible_now_slice)
        self.assertNotIn("launchQuantProjection", visible_now_slice)
        self.assertLess(
            summary_primary_slice.index('aria-label="candidate radar ordinary user first summary"'),
            visible_now_start,
        )
        self.assertLess(
            visible_now_start,
            summary_primary_slice.index('aria-label="candidate radar ordinary vertical slice readback"'),
        )
        self.assertIn("candidateRadarTypedSymbolSentence", self.page)
        self.assertIn("candidateRadarTypedSymbolItems", self.page)
        self.assertIn("candidateRadarTypedSymbolRows", self.page)
        self.assertIn('aria-label="candidate radar typed symbol immediate readback"', summary_primary_slice)
        self.assertIn("输入股票后先看这里", summary_primary_slice)
        self.assertIn('aria-label="candidate radar typed symbol immediate sentence"', summary_primary_slice)
        self.assertIn("MetricGrid items={candidateRadarTypedSymbolItems}", summary_primary_slice)
        self.assertIn('aria-label="candidate radar typed symbol immediate actions"', summary_primary_slice)
        self.assertIn('aria-label="candidate radar typed symbol immediate rows"', summary_primary_slice)
        self.assertIn("<summary>查看输入链路</summary>", summary_primary_slice)
        self.assertIn("DataLineageTable rows={candidateRadarTypedSymbolRows}", summary_primary_slice)
        self.assertIn("输入股票只是本地会话状态；只有确认按钮点击才启动本地确认流程", summary_primary_slice)
        typed_symbol_start = summary_primary_slice.index('aria-label="candidate radar typed symbol immediate readback"')
        typed_symbol_end = summary_primary_slice.index('aria-label="candidate radar confirm button primary status card"', typed_symbol_start)
        typed_symbol_slice = summary_primary_slice[typed_symbol_start:typed_symbol_end]
        for typed_symbol_label in (
            'label: "当前输入"',
            'label: "本地校验"',
            'label: "最近结果归属"',
            'label: "确认按钮"',
            'label: "结果入口"',
            'label: "不会发生"',
        ):
            self.assertIn(typed_symbol_label, self.page)
        for typed_symbol_row in (
            '检查项: "1. 输入股票"',
            '检查项: "2. 归属最近结果"',
            '检查项: "3. 点击确认"',
            '检查项: "4. 看结果"',
        ):
            self.assertIn(typed_symbol_row, self.page)
        self.assertIn('href="#candidate-radar-search-quant-projection"', typed_symbol_slice)
        self.assertIn('href="#factor/factor-score"', typed_symbol_slice)
        self.assertIn('href="#next/next-session-chart"', typed_symbol_slice)
        self.assertIn('href="#candidate-pool"', typed_symbol_slice)
        self.assertIn("不会启动确认流程、不会刷新外部数据或模型", typed_symbol_slice)
        self.assertNotIn("onClick=", typed_symbol_slice)
        self.assertNotIn("postCandidateRadar", typed_symbol_slice)
        self.assertNotIn("launchQuantProjection", typed_symbol_slice)
        self.assertLess(visible_now_start, typed_symbol_start)
        self.assertIn("candidateRadarConfirmButtonPrimarySentence", self.page)
        self.assertIn("candidateRadarConfirmButtonPrimaryItems", self.page)
        self.assertIn("candidateRadarConfirmButtonPrimaryRows", self.page)
        self.assertIn('aria-label="candidate radar confirm button primary status card"', summary_primary_slice)
        self.assertIn("确认按钮现在能不能点", summary_primary_slice)
        self.assertIn('aria-label="candidate radar confirm button primary status sentence"', summary_primary_slice)
        self.assertIn("MetricGrid items={candidateRadarConfirmButtonPrimaryItems}", summary_primary_slice)
        self.assertIn('aria-label="candidate radar confirm button primary status links"', summary_primary_slice)
        self.assertIn('aria-label="candidate radar confirm button primary status rows"', summary_primary_slice)
        self.assertIn("<summary>查看按钮状态读法</summary>", summary_primary_slice)
        self.assertIn("DataLineageTable rows={candidateRadarConfirmButtonPrimaryRows}", summary_primary_slice)
        self.assertIn("真正会创建本地研究任务的只有确认输入区的确认按钮", summary_primary_slice)
        confirm_button_status_start = summary_primary_slice.index('aria-label="candidate radar confirm button primary status card"')
        confirm_button_status_end = summary_primary_slice.index('aria-label="candidate radar recent research result card"', confirm_button_status_start)
        confirm_button_status_slice = summary_primary_slice[confirm_button_status_start:confirm_button_status_end]
        for confirm_button_status_label in (
            'label: "当前输入"',
            'label: "确认按钮"',
            'label: "主动作"',
            'label: "提交后看"',
            'label: "禁用原因"',
            'label: "不会发生"',
            'label: "边界"',
        ):
            self.assertIn(confirm_button_status_label, self.page)
        for confirm_button_status_row in (
            '读法: "1. 输入校验"',
            '读法: "2. 按钮状态"',
            '读法: "3. 点击后看"',
            '读法: "4. 安全边界"',
        ):
            self.assertIn(confirm_button_status_row, self.page)
        self.assertIn('href="#candidate-radar-search-quant-projection"', confirm_button_status_slice)
        self.assertIn('href="#tasks"', confirm_button_status_slice)
        self.assertIn('href="#factor"', confirm_button_status_slice)
        self.assertIn('href="#next"', confirm_button_status_slice)
        self.assertIn("不会提交表单、不会启动确认流程、不会刷新外部数据或模型", confirm_button_status_slice)
        self.assertNotIn("onClick=", confirm_button_status_slice)
        self.assertNotIn("launchQuantProjection", confirm_button_status_slice)
        self.assertNotIn("postCandidateRadar", confirm_button_status_slice)
        self.assertLess(typed_symbol_start, confirm_button_status_start)
        self.assertIn("quantProjectionPostConfirmWaitLabel", self.page)
        self.assertIn("下一步打开量化结果区和次日图谱结果区只读复核", self.page)
        self.assertIn("最后回放量化结果区和次日图谱结果区", self.page)
        self.assertIn("quantProjectionPostConfirmOneScreenItems", self.page)
        self.assertIn('aria-label="candidate radar post confirm one glance result card"', summary_primary_slice)
        self.assertIn("确认后马上看这里", summary_primary_slice)
        self.assertIn('aria-label="candidate radar post confirm one glance result sentence"', summary_primary_slice)
        self.assertIn("MetricGrid items={ordinaryUserMetricItems(quantProjectionPostConfirmOneScreenItems)}", summary_primary_slice)
        self.assertIn('aria-label="candidate radar post confirm one glance result actions"', summary_primary_slice)
        self.assertIn("这张确认后一眼结果卡只读 task receipt、cache、call_ledger 和 packet", summary_primary_slice)
        post_confirm_result_start = summary_primary_slice.index('aria-label="candidate radar post confirm one glance result card"')
        post_confirm_result_end = summary_primary_slice.index('aria-label="candidate radar one path p1 p2 p3 route"', post_confirm_result_start)
        post_confirm_result_slice = summary_primary_slice[post_confirm_result_start:post_confirm_result_end]
        for post_confirm_result_label in (
            'label: "任务接收"',
            'label: "P1 最短链路"',
            'label: "当前阶段"',
            'label: "P2 三面"',
            'label: "P3 结论"',
            'label: "下一步入口"',
            'label: "只读边界"',
        ):
            self.assertIn(post_confirm_result_label, self.page)
        self.assertIn('href="#tasks"', post_confirm_result_slice)
        self.assertIn('href="#factor/factor-score"', post_confirm_result_slice)
        self.assertIn('href="#next/next-session-chart"', post_confirm_result_slice)
        self.assertIn('href="#marginEtf"', post_confirm_result_slice)
        self.assertIn('href="#candidate-radar-search-quant-projection"', post_confirm_result_slice)
        self.assertIn("不创建第二个 task、不调用 Tushare/DeepSeek/GitHub、不交易、不改 strategy action", post_confirm_result_slice)
        self.assertNotIn("onClick=", post_confirm_result_slice)
        self.assertNotIn("launchQuantProjection", post_confirm_result_slice)
        self.assertNotIn("postCandidateRadar", post_confirm_result_slice)
        self.assertLess(confirm_button_status_start, post_confirm_result_start)
        self.assertIn("candidateRadarOnePathSentence", self.page)
        self.assertIn("candidateRadarOnePathItems", self.page)
        self.assertIn("candidateRadarOnePathRows", self.page)
        self.assertIn('aria-label="candidate radar one path p1 p2 p3 route"', summary_primary_slice)
        self.assertIn("下一票主路径", summary_primary_slice)
        self.assertIn('aria-label="candidate radar one path p1 p2 p3 sentence"', summary_primary_slice)
        self.assertIn("MetricGrid items={candidateRadarOnePathItems}", summary_primary_slice)
        self.assertIn('aria-label="candidate radar one path p1 p2 p3 links"', summary_primary_slice)
        self.assertIn('aria-label="candidate radar one path p1 p2 p3 rows"', summary_primary_slice)
        self.assertIn("<summary>查看主路径读法</summary>", summary_primary_slice)
        self.assertIn("DataLineageTable rows={candidateRadarOnePathRows}", summary_primary_slice)
        self.assertIn("确认、进度、结果、风险四步", summary_primary_slice)
        self.assertIn("不会启动确认流程、不会刷新外部数据或模型", summary_primary_slice)
        one_path_start = summary_primary_slice.index('aria-label="candidate radar one path p1 p2 p3 route"')
        one_path_end = summary_primary_slice.index('aria-label="candidate radar recent research result card"', one_path_start)
        one_path_slice = summary_primary_slice[one_path_start:one_path_end]
        self.assertLess(post_confirm_result_start, one_path_start)
        for one_path_label in (
            'label: "1. 确认"',
            'label: "2. 进度"',
            'label: "3. 结果"',
            'label: "4. 风险"',
            'label: "不会发生"',
            'label: "边界"',
        ):
            self.assertIn(one_path_label, self.page)
        for one_path_row in (
            '步骤: "1. 输入并确认"',
            '步骤: "2. 看任务"',
            '步骤: "3. 回放结果"',
            '步骤: "4. 补看风险"',
        ):
            self.assertIn(one_path_row, self.page)
        self.assertIn('href="#candidate-radar-search-quant-projection"', one_path_slice)
        self.assertIn('href="#tasks"', one_path_slice)
        self.assertIn('href="#factor/factor-score"', one_path_slice)
        self.assertIn('href="#next/next-session-chart"', one_path_slice)
        self.assertIn('href="#marginEtf"', one_path_slice)
        self.assertIn("不是买入、卖出、加仓、融资或下单指令", one_path_slice)
        self.assertNotIn("onClick=", one_path_slice)
        self.assertNotIn("launchQuantProjection", one_path_slice)
        self.assertNotIn("postCandidateRadar", one_path_slice)
        self.assertLess(confirm_button_status_start, one_path_start)
        self.assertIn("candidateRadarRecentResearchResultSentence", self.page)
        self.assertIn("candidateRadarRecentResearchResultItems", self.page)
        self.assertIn("candidateRadarRecentResearchResultRows", self.page)
        self.assertIn('aria-label="candidate radar recent research result card"', summary_primary_slice)
        self.assertIn("确认后最近投研结果", summary_primary_slice)
        self.assertIn('aria-label="candidate radar recent research result sentence"', summary_primary_slice)
        self.assertIn("MetricGrid items={candidateRadarRecentResearchResultItems}", summary_primary_slice)
        self.assertIn('aria-label="candidate radar recent research result actions"', summary_primary_slice)
        self.assertIn('aria-label="candidate radar recent research result rows"', summary_primary_slice)
        self.assertIn("<summary>查看结果读法</summary>", summary_primary_slice)
        self.assertIn("DataLineageTable rows={candidateRadarRecentResearchResultRows}", summary_primary_slice)
        self.assertIn("最近投研结果卡只帮助复核来源、缺口和下一步", summary_primary_slice)
        recent_result_start = summary_primary_slice.index('aria-label="candidate radar recent research result card"')
        recent_result_end = summary_primary_slice.index('aria-label="candidate radar lead candidate review card"', recent_result_start)
        recent_result_slice = summary_primary_slice[recent_result_start:recent_result_end]
        for recent_result_label in (
            'label: "最近结果"',
            'label: "结果归属"',
            'label: "当前票"',
            'label: "最近任务"',
            'label: "P2/P3 去向"',
            'label: "来源状态"',
            'label: "数据能力"',
            'label: "degraded / 缺口"',
            'label: "下一步"',
            'label: "研究边界"',
        ):
            self.assertIn(recent_result_label, self.page)
        self.assertIn("真实数据、权限、空窗口和降级原因去数据能力页复核", self.page)
        for recent_result_row in (
            '读法: "1. 先看结论"',
            '读法: "2. 再看来源"',
            '读法: "3. 识别降级"',
            '读法: "4. 去哪里看"',
            '读法: "5. 当前票和任务"',
            '读法: "6. P2/P3 回放"',
        ):
            self.assertIn(recent_result_row, self.page)
        self.assertIn("quantProjectionLatestTaskState", self.page)
        self.assertIn("quantProjectionP2P3ConnectionReady", self.page)
        self.assertIn("这行只读当前票和本地任务索引；不提交、不轮询外部、不补调 provider/model", self.page)
        self.assertIn("P2/P3 去向只切换本地结果页；不创建第二个 task、不交易、不改 strategy action", self.page)
        self.assertIn('href="#factor"', recent_result_slice)
        self.assertIn('href="#next/next-session-chart"', recent_result_slice)
        self.assertIn('href={DATA_CAPABILITY_HREF}', recent_result_slice)
        self.assertIn('href="#marginEtf"', recent_result_slice)
        self.assertIn('href="#candidate-radar-search-quant-projection"', recent_result_slice)
        self.assertIn("不会启动确认流程、不会刷新外部数据或模型", recent_result_slice)
        self.assertIn("不是买卖建议，不下单、不改持仓、不改 strategy action", recent_result_slice)
        self.assertNotIn("onClick=", recent_result_slice)
        self.assertNotIn("postCandidateRadar", recent_result_slice)
        self.assertNotIn("launchQuantProjection", recent_result_slice)
        self.assertLess(one_path_start, recent_result_start)
        self.assertLess(confirm_button_status_start, recent_result_start)
        self.assertIn("candidatePoolLeadReviewSentence", self.page)
        self.assertIn("candidatePoolLeadReviewItems", self.page)
        self.assertIn("candidatePoolLeadReviewRows", self.page)
        self.assertIn('aria-label="candidate radar lead candidate review card"', summary_primary_slice)
        self.assertIn("候选池首位复核", summary_primary_slice)
        self.assertIn('aria-label="candidate radar lead candidate review sentence"', summary_primary_slice)
        self.assertIn("MetricGrid items={candidatePoolLeadReviewItems}", summary_primary_slice)
        self.assertIn('aria-label="candidate radar lead candidate review actions"', summary_primary_slice)
        self.assertIn('aria-label="candidate radar lead candidate review rows"', summary_primary_slice)
        self.assertIn("<summary>查看复核读法</summary>", summary_primary_slice)
        self.assertIn("DataLineageTable rows={candidatePoolLeadReviewRows}", summary_primary_slice)
        self.assertIn("首位候选只是复核顺序，不是推荐买入", summary_primary_slice)
        lead_candidate_start = summary_primary_slice.index('aria-label="candidate radar lead candidate review card"')
        lead_candidate_end = summary_primary_slice.index('aria-label="candidate radar lead candidate handoff card"', lead_candidate_start)
        lead_candidate_slice = summary_primary_slice[lead_candidate_start:lead_candidate_end]
        for lead_candidate_label in (
            'label: "首个候选"',
            'label: "分组"',
            'label: "评分/理由"',
            'label: "来源"',
            'label: "缺口"',
            'label: "下一步"',
            'label: "非买入边界"',
        ):
            self.assertIn(lead_candidate_label, self.page)
        for lead_candidate_row in (
            '读法: "1. 首位候选"',
            '读法: "2. 评分理由"',
            '读法: "3. 来源和缺口"',
            '读法: "4. 复核入口"',
        ):
            self.assertIn(lead_candidate_row, self.page)
        self.assertIn('href="#candidate-pool"', lead_candidate_slice)
        self.assertIn('href="#candidate-radar-search-quant-projection"', lead_candidate_slice)
        self.assertIn('href="#factor"', lead_candidate_slice)
        self.assertIn('href="#next"', lead_candidate_slice)
        self.assertIn('href="#marginEtf"', lead_candidate_slice)
        self.assertIn("不会创建 task、不会运行快扫、不会调用 Tushare/DeepSeek/GitHub、不启动 worker", lead_candidate_slice)
        self.assertNotIn("onClick=", lead_candidate_slice)
        self.assertNotIn("launchQuickScan", lead_candidate_slice)
        self.assertNotIn("postCandidateRadar", lead_candidate_slice)
        self.assertLess(recent_result_start, lead_candidate_start)
        self.assertIn("candidatePoolLeadHandoffSentence", self.page)
        self.assertIn("candidatePoolLeadHandoffItems", self.page)
        self.assertIn("candidatePoolLeadHandoffRows", self.page)
        self.assertIn('const [leadCandidatePrefillSymbol, setLeadCandidatePrefillSymbol] = useState("");', self.page)
        self.assertIn("candidatePoolLeadCandidateCanPrefill", self.page)
        self.assertIn("leadCandidatePrefillValidation", self.page)
        self.assertIn("candidatePoolLeadHandoffPrefillFeedback", self.page)
        self.assertIn("const prefillLeadCandidateIntoConfirmInput = () =>", self.page)
        self.assertIn('updateSearchSymbolInput(candidatePoolLeadCandidateTicker, "lead_candidate_prefill");', self.page)
        self.assertIn('document.getElementById("candidate-radar-search-quant-projection")?.scrollIntoView({ block: "start" });', self.page)
        self.assertIn('aria-label="candidate radar lead candidate handoff card"', summary_primary_slice)
        self.assertIn("首位候选怎么继续", summary_primary_slice)
        self.assertIn('aria-label="candidate radar lead candidate handoff sentence"', summary_primary_slice)
        self.assertIn("MetricGrid items={candidatePoolLeadHandoffItems}", summary_primary_slice)
        self.assertIn('aria-label="candidate radar lead candidate handoff actions"', summary_primary_slice)
        self.assertIn('aria-label="candidate radar lead candidate prefill feedback"', summary_primary_slice)
        self.assertIn('aria-label="candidate radar lead candidate handoff rows"', summary_primary_slice)
        self.assertIn("<summary>查看交接读法</summary>", summary_primary_slice)
        self.assertIn("DataLineageTable rows={candidatePoolLeadHandoffRows}", summary_primary_slice)
        self.assertIn("首位候选交接只是把“下一票”变成可复核的当前标的路径", summary_primary_slice)
        lead_handoff_start = summary_primary_slice.index('aria-label="candidate radar lead candidate handoff card"')
        lead_handoff_end = summary_primary_slice.index('aria-label="candidate radar empty pool primary action card"', lead_handoff_start)
        lead_handoff_slice = summary_primary_slice[lead_handoff_start:lead_handoff_end]
        for lead_handoff_label in (
            'label: "候选代码"',
            'label: "主动作"',
            'label: "复核顺序"',
            'label: "数据缺口"',
            'label: "不会发生"',
            'label: "非买入边界"',
        ):
            self.assertIn(lead_handoff_label, self.page)
        for lead_handoff_row in (
            '步骤: "1. 拿到代码"',
            '步骤: "2. 解释单票"',
            '步骤: "3. 看三面结果"',
            '步骤: "4. 保持研究边界"',
        ):
            self.assertIn(lead_handoff_row, self.page)
        self.assertIn('href="#candidate-radar-search-quant-projection"', lead_handoff_slice)
        self.assertIn('href="#factor"', lead_handoff_slice)
        self.assertIn('href="#next"', lead_handoff_slice)
        self.assertIn('href={DATA_CAPABILITY_HREF}', lead_handoff_slice)
        self.assertIn('href="#marginEtf"', lead_handoff_slice)
        self.assertIn('aria-label="prefill lead candidate into confirm input without submit"', lead_handoff_slice)
        self.assertIn("带入确认框", lead_handoff_slice)
        self.assertIn("disabled={!candidatePoolLeadCandidateCanPrefill}", lead_handoff_slice)
        self.assertIn("onClick={prefillLeadCandidateIntoConfirmInput}", lead_handoff_slice)
        self.assertIn("把 ${candidatePoolLeadCandidateTicker} 填入确认输入框；不会提交", lead_handoff_slice)
        self.assertIn("已把 ${leadCandidatePrefillValidation.normalized} 带入确认输入框；下一步由你手动点确认，页面不会自动提交。", self.page)
        self.assertIn("可把 ${candidatePoolLeadCandidateTicker} 带入确认输入框；带入后仍需你手动确认。", self.page)
        self.assertIn("暂无可带入的首位候选；可以先手动输入股票代码。", self.page)
        self.assertIn("只在点击带入时写入本地输入框；不提交、不快扫、不外联、不启动 worker 或交易", self.page)
        self.assertIn("点击带入只改本地输入，不自动提交", self.page)
        self.assertIn("只有点击“带入确认框”才写入本地输入框，不提交、不快扫、不调用 Tushare/DeepSeek/GitHub、不启动 worker、不交易", lead_handoff_slice)
        self.assertNotIn("launchQuickScan", lead_handoff_slice)
        self.assertNotIn("postCandidateRadar", lead_handoff_slice)
        self.assertNotIn("launchQuantProjection", lead_handoff_slice)
        self.assertLess(lead_candidate_start, lead_handoff_start)
        self.assertIn("candidatePoolEmptyStatePrimarySentence", self.page)
        self.assertIn("candidatePoolEmptyStatePrimaryItems", self.page)
        self.assertIn("candidatePoolEmptyStatePrimaryRows", self.page)
        self.assertIn('aria-label="candidate radar empty pool primary action card"', summary_primary_slice)
        self.assertIn("候选池为空时现在点哪", summary_primary_slice)
        self.assertIn('aria-label="candidate radar empty pool primary action sentence"', summary_primary_slice)
        self.assertIn("MetricGrid items={candidatePoolEmptyStatePrimaryItems}", summary_primary_slice)
        self.assertIn('aria-label="candidate radar empty pool primary action links"', summary_primary_slice)
        self.assertIn('aria-label="candidate radar empty pool primary action rows"', summary_primary_slice)
        self.assertIn("<summary>查看空池读法</summary>", summary_primary_slice)
        self.assertIn("DataLineageTable rows={candidatePoolEmptyStatePrimaryRows}", summary_primary_slice)
        self.assertIn("空候选池不是买入或清仓信号", summary_primary_slice)
        empty_pool_action_start = summary_primary_slice.index('aria-label="candidate radar empty pool primary action card"')
        empty_pool_action_end = summary_primary_slice.index('aria-label="candidate radar user route qa latest evidence"', empty_pool_action_start)
        empty_pool_action_slice = summary_primary_slice[empty_pool_action_start:empty_pool_action_end]
        for empty_pool_action_label in (
            'label: "当前状态"',
            'label: "主动作"',
            'label: "可回放"',
            'label: "来源"',
            'label: "缺口"',
            'label: "不会发生"',
            'label: "边界"',
        ):
            self.assertIn(empty_pool_action_label, self.page)
        for empty_pool_action_row in (
            '读法: "1. 空候选判断"',
            '读法: "2. 主动作"',
            '读法: "3. 本地回放"',
            '读法: "4. 边界"',
        ):
            self.assertIn(empty_pool_action_row, self.page)
        self.assertIn('href="#candidate-radar-search-quant-projection"', empty_pool_action_slice)
        self.assertIn('href="#candidate-pool"', empty_pool_action_slice)
        self.assertIn('href="#factor"', empty_pool_action_slice)
        self.assertIn('href="#next"', empty_pool_action_slice)
        self.assertIn("不会创建 task、不会快扫、不会调用 Tushare/DeepSeek/GitHub、不启动 worker", empty_pool_action_slice)
        self.assertNotIn("onClick=", empty_pool_action_slice)
        self.assertNotIn("launchQuickScan", empty_pool_action_slice)
        self.assertNotIn("postCandidateRadar", empty_pool_action_slice)
        self.assertNotIn("launchQuantProjection", empty_pool_action_slice)
        self.assertLess(lead_handoff_start, empty_pool_action_start)
        self.assertLess(empty_pool_action_start, summary_primary_slice.index('aria-label="candidate radar user route qa latest evidence"'))
        self.assertIn("getAuditUserRouteQa", self.page)
        self.assertNotIn("getAuditCache", self.page)
        self.assertIn("user_route_qa_evidence_contract", self.page)
        self.assertIn("candidateRadarUserRouteQaSummary", self.page)
        self.assertIn("candidateRadarUserRouteQaItems", self.page)
        self.assertIn("candidateRadarUserRouteQaRows", self.page)
        self.assertIn('aria-label="candidate radar user route qa latest evidence"', summary_primary_slice)
        self.assertIn("本轮路线 QA", summary_primary_slice)
        self.assertIn('aria-label="candidate radar user route qa summary"', summary_primary_slice)
        self.assertIn("本轮本地路线 QA 已覆盖下一票雷达", self.page)
        self.assertIn("等待本地路线 QA 报告；不影响当前候选缓存和确认按钮使用。", self.page)
        self.assertIn("MetricGrid items={candidateRadarUserRouteQaItems}", summary_primary_slice)
        for qa_label in (
            'label: "路线 QA"',
            'label: "视口"',
            'label: "路线"',
            'label: "输入静默"',
            'label: "最新报告"',
            'label: "边界"',
        ):
            self.assertIn(qa_label, self.page)
        qa_start = summary_primary_slice.index('aria-label="candidate radar user route qa latest evidence"')
        qa_end = summary_primary_slice.index('aria-label="candidate radar post confirm next step bridge"', qa_start)
        qa_slice = summary_primary_slice[qa_start:qa_end]
        self.assertIn('aria-label="candidate radar user route qa local actions"', qa_slice)
        self.assertIn('href="#candidate-pool"', qa_slice)
        self.assertIn('href="#candidate-radar-search-quant-projection"', qa_slice)
        self.assertIn('href="#audit"', qa_slice)
        self.assertIn('aria-label="candidate radar user route qa evidence rows"', qa_slice)
        self.assertIn("<summary>查看 QA 明细</summary>", qa_slice)
        self.assertIn("DataLineageTable rows={candidateRadarUserRouteQaRows}", qa_slice)
        self.assertIn("`/api/audit/user-route-qa`", qa_slice)
        self.assertIn("不会打开浏览器、不会写截图、不会创建任务", qa_slice)
        self.assertIn("不是 provider/model 证据、不是远端 CI，也不代表旧雷达可以退场", qa_slice)
        self.assertNotIn("onClick=", qa_slice)
        self.assertNotIn("postCandidateRadar", qa_slice)
        self.assertNotIn("launchQuantProjection", qa_slice)
        self.assertLess(lead_candidate_start, qa_start)
        self.assertLess(recent_result_start, qa_start)
        self.assertLess(typed_symbol_start, qa_start)
        self.assertLess(visible_now_start, qa_start)
        self.assertIn("candidateRadarPostConfirmNextStepSentence", self.page)
        self.assertIn("candidateRadarPostConfirmNextStepItems", self.page)
        self.assertIn("candidateRadarSingleTicketLoopSentence", self.page)
        self.assertIn("candidateRadarSingleTicketLoopItems", self.page)
        self.assertIn('aria-label="candidate radar post confirm next step bridge"', summary_primary_slice)
        self.assertIn("确认后看这 3 处", summary_primary_slice)
        self.assertIn('aria-label="candidate radar post confirm next step sentence"', summary_primary_slice)
        self.assertIn("Factor、Next 和 ETF/融资都只读已有 cache / packet", summary_primary_slice)
        post_confirm_start = summary_primary_slice.index('aria-label="candidate radar post confirm next step bridge"')
        post_confirm_end = summary_primary_slice.index('aria-label="candidate radar ordinary vertical slice readback"', post_confirm_start)
        post_confirm_slice = summary_primary_slice[post_confirm_start:post_confirm_end]
        self.assertIn("MetricGrid items={candidateRadarPostConfirmNextStepItems}", post_confirm_slice)
        self.assertIn('aria-label="candidate radar post confirm next step actions"', post_confirm_slice)
        self.assertIn('href="#factor/factor-score"', post_confirm_slice)
        self.assertIn('href="#next/next-session-chart"', post_confirm_slice)
        self.assertIn('href="#marginEtf"', post_confirm_slice)
        self.assertIn('href="#candidate-radar-search-quant-projection"', post_confirm_slice)
        self.assertIn('aria-label="open factor after candidate radar confirm"', post_confirm_slice)
        self.assertIn('aria-label="open next session after candidate radar confirm"', post_confirm_slice)
        self.assertIn('aria-label="open margin etf after candidate radar confirm"', post_confirm_slice)
        self.assertIn('aria-label="return confirm input after candidate radar confirm bridge"', post_confirm_slice)
        self.assertIn('aria-label="candidate radar post confirm factor next alignment details"', post_confirm_slice)
        self.assertIn("Factor/Next 对齐明细", post_confirm_slice)
        self.assertNotIn("onClick=", post_confirm_slice)
        self.assertNotIn("postCandidateRadar", post_confirm_slice)
        self.assertNotIn("launchQuantProjection", post_confirm_slice)
        self.assertNotIn('aria-label="candidate radar single ticket closed loop"', summary_primary_slice)
        post_confirm_items_start = self.page.index("const candidateRadarPostConfirmNextStepItems")
        post_confirm_items_end = self.page.index("const ordinaryCandidateReviewCompassItems", post_confirm_items_start)
        post_confirm_items_slice = self.page[post_confirm_items_start:post_confirm_items_end]
        for post_confirm_label in (
            'label: "候选来源"',
            'label: "确认动作"',
            'label: "先看量化推演"',
            'label: "再看次日图谱"',
            'label: "Factor/Next 对齐"',
            'label: "风险补看"',
            'label: "边界"',
        ):
            self.assertIn(post_confirm_label, post_confirm_items_slice)
        self.assertIn("quantProjectionCrossModuleAlignmentRows", self.page)
        self.assertIn("只读本地 packet；不创建 task、不调用 Tushare/DeepSeek/worker、不交易、不改 strategy action", self.page)
        self.assertIn("const quantProjectionResultSymbol", self.page)
        self.assertIn("quantProjectionAcceptedTaskSymbol ||", self.page)
        self.assertIn("String(searchQuantProviderModelAcceptance.symbol ?? \"\")", self.page)
        self.assertIn('label: quantProjectionInterpretationReady || quantProjectionSmallDataReady ? "1. 确认股票" : "1. 解释 Top"', post_confirm_items_slice)
        self.assertIn('`${quantProjectionResultSymbol || "当前标的"} 已有本地结果`', post_confirm_items_slice)
        self.assertIn('`最近结果归属 ${quantProjectionResultSymbol || "当前标的"}；换票时回确认输入区重新输入并点击确认`', post_confirm_items_slice)
        for single_ticket_label in (
            'label: "2. 确认输入"',
            'label: "3. 任务进度"',
            'label: "4. 最近结果"',
            'label: "5. 后续入口"',
        ):
            self.assertIn(single_ticket_label, post_confirm_items_slice)
        self.assertIn("ETF/融资风险只读本地预算，不生成加仓或加融资指令", post_confirm_items_slice)
        self.assertIn("不创建第二个 task、不调用 Tushare/DeepSeek、不交易", post_confirm_items_slice)
        self.assertLess(visible_now_start, post_confirm_start)
        self.assertLess(post_confirm_start, summary_primary_slice.index('aria-label="candidate radar ordinary vertical slice readback"'))
        self.assertIn('aria-label="candidate radar user first actions"', summary_primary_slice)
        self.assertIn('href={candidateRadarP0Blocked ? "#desktop" : "#candidate-radar-search-quant-projection"}', summary_primary_slice)
        self.assertIn('aria-label="candidate radar denoised first screen guide"', summary_primary_slice)
        self.assertIn("普通首屏去噪", summary_primary_slice)
        self.assertIn("这不是 acceptance report，也不是 provider 审计入口", summary_primary_slice)
        for denoised_label in (
            'label: "先看"',
            'label: "候选池"',
            'label: "确认按钮"',
            'label: "进度"',
            'label: "下沉"',
            'label: "边界"',
        ):
            self.assertIn(denoised_label, summary_primary_slice)
        self.assertIn("Top / Watch / Excluded 仍在候选池首位", summary_primary_slice)
        self.assertIn("TaskStatusPanel 和刷新本地回放保留；GET cache 只读", summary_primary_slice)
        self.assertIn("重复 P1/P2/P3 表、ledger 和补证路线在详情中", summary_primary_slice)
        self.assertIn("candidateRadarLtg13NextDirectEvidenceItems", self.page)
        self.assertIn("candidateRadarLtg13NextDirectEvidenceRows", self.page)
        self.assertIn('aria-label="candidate radar ltg13 next direct evidence quick read"', summary_primary_slice)
        self.assertIn("LTG-13 下一条直接证据", summary_primary_slice)
        self.assertIn("搜票真实数据账本和最终推广复核这两类缺口", summary_primary_slice)
        self.assertIn("不自动运行 Tushare、DeepSeek、GitHub 或 worker", summary_primary_slice)
        self.assertIn('aria-label="candidate radar ltg13 next direct evidence actions"', summary_primary_slice)
        self.assertIn('aria-label="open searched symbol confirm from ltg13 next evidence"', summary_primary_slice)
        self.assertIn('href="#candidate-radar-ltg13-data-ledger-audit"', summary_primary_slice)
        self.assertIn("真实数据补证需授权", summary_primary_slice)
        self.assertIn("需要用户明确授权真实数据账本补证后", summary_primary_slice)
        self.assertIn('aria-label="candidate radar ltg13 next direct evidence rows"', summary_primary_slice)
        self.assertIn("<summary>查看两项缺口</summary>", summary_primary_slice)
        self.assertIn("不把本地 receipt、dry-run、execution request、matrix、browser artifact 或 local review 当 production replacement complete", summary_primary_slice)
        self.assertIn('id="candidate-radar-ltg13-data-ledger-audit"', self.page)
        self.assertNotIn("launchQuantProjectionProviderModelAcceptance", summary_primary_slice)
        self.assertNotIn("postCandidateRadarQuantProjectionProviderModelAcceptance", summary_primary_slice)
        self.assertNotIn("quant-projection-provider-model-acceptance", summary_primary_slice)
        self.assertIn("candidateRadarRealDataPreflightState", self.page)
        self.assertIn("candidateRadarRealDataPreflightItems", self.page)
        self.assertIn("candidateRadarRealDataPreflightRows", self.page)
        self.assertIn('aria-label="candidate radar real data preflight"', summary_primary_slice)
        self.assertIn("真实数据补证授权前状态", summary_primary_slice)
        self.assertIn("为什么现在是禁用/降级", summary_primary_slice)
        self.assertIn("MetricGrid items={candidateRadarRealDataPreflightItems}", summary_primary_slice)
        self.assertIn('aria-label="candidate radar real data preflight local actions"', summary_primary_slice)
        self.assertIn('href="#candidate-pool"', summary_primary_slice)
        self.assertIn('href="#candidate-radar-search-quant-projection"', summary_primary_slice)
        self.assertIn('href="#factor/factor-score"', summary_primary_slice)
        self.assertIn('href="#next/next-session-chart"', summary_primary_slice)
        self.assertIn('href="#marginEtf"', summary_primary_slice)
        self.assertIn('aria-label="candidate radar real data preflight rows"', summary_primary_slice)
        self.assertIn("<summary>查看授权前检查项</summary>", summary_primary_slice)
        self.assertIn("不创建 task、不调用 Tushare/DeepSeek/GitHub、不启动 worker", summary_primary_slice)
        self.assertIn("DataLineageTable rows={candidateRadarRealDataPreflightRows}", summary_primary_slice)
        self.assertIn("scope-bound provider run", summary_primary_slice)
        real_data_preflight_start = summary_primary_slice.index('aria-label="candidate radar real data preflight"')
        real_data_preflight_end = summary_primary_slice.index(
            'aria-label="candidate radar user first actions"',
            real_data_preflight_start,
        )
        real_data_preflight_slice = summary_primary_slice[real_data_preflight_start:real_data_preflight_end]
        for real_data_label in (
            'label: "当前状态"',
            'label: "授权前提"',
            'label: "安全载荷"',
            'label: "必须留痕"',
            'label: "现在可做"',
            'label: "不会发生"',
            'label: "交易边界"',
        ):
            self.assertIn(real_data_label, self.page)
        for real_data_row in (
            '检查项: "1. 明确授权"',
            '检查项: "2. 绑定 scope"',
            '检查项: "3. 留痕回放"',
            '检查项: "4. 推广复核"',
            '检查项: "5. 交易隔离"',
        ):
            self.assertIn(real_data_row, self.page)
        self.assertIn("需要用户明确授权本轮真实数据补证；未授权就保持 disabled/degraded", self.page)
        self.assertIn("需要 scope hash + safe payload；敏感凭据不进前端、日志、packet 或报告", self.page)
        self.assertIn("provider call_ledger、failure-mode evidence、redaction/no-secret 边界", self.page)
        self.assertIn("先看候选池、确认单票、回放 Factor / Next / ETF 风险", self.page)
        self.assertIn("打开页面、输入、GET cache、本地链接不会调用 Tushare/DeepSeek/GitHub/worker", self.page)
        self.assertNotIn("onClick=", real_data_preflight_slice)
        self.assertNotIn("postCandidateRadar", real_data_preflight_slice)
        self.assertNotIn("launchQuantProjection", real_data_preflight_slice)
        self.assertNotIn("launchProductionPromotionReview", real_data_preflight_slice)
        self.assertLess(
            summary_primary_slice.index('aria-label="candidate radar ltg13 next direct evidence quick read"'),
            real_data_preflight_start,
        )
        self.assertLess(
            real_data_preflight_start,
            summary_primary_slice.index('aria-label="candidate radar ordinary candidate review compass"'),
        )
        self.assertLess(
            summary_primary_slice.index('aria-label="candidate radar ltg13 next direct evidence quick read"'),
            summary_primary_slice.index('aria-label="candidate radar ordinary candidate review compass"'),
        )
        self.assertIn('aria-label="candidate radar ordinary candidate review compass"', summary_primary_slice)
        self.assertIn("候选复核顺序", summary_primary_slice)
        self.assertIn("打开下一票雷达后先按 Top / Watch / Excluded 复核，再决定是否对单票点确认", summary_primary_slice)
        self.assertIn("ordinaryCandidateReviewCompassItems", self.page)
        self.assertIn("ordinaryCandidateReviewCompassRows", self.page)
        self.assertIn('label: "先看哪组"', self.page)
        self.assertIn('label: "怎么复核"', self.page)
        self.assertIn('label: "看哪三列"', self.page)
        self.assertIn('label: "安全边界"', self.page)
        self.assertIn('aria-label="candidate radar ordinary candidate review compass actions"', summary_primary_slice)
        self.assertIn('aria-label="candidate radar ordinary candidate review compass rows"', summary_primary_slice)
        self.assertIn("<summary>查看复核顺序明细</summary>", summary_primary_slice)
        self.assertIn("复核顺序明细默认收起", summary_primary_slice)
        self.assertIn("候选复核顺序只帮助用户看懂现有缓存", summary_primary_slice)
        self.assertIn("不交易、不下单、不改交易策略，也不声称 LTG-13 已完成", summary_primary_slice)
        compass_start = summary_primary_slice.index('aria-label="candidate radar ordinary candidate review compass"')
        compass_end = summary_primary_slice.index(
            'aria-label="candidate radar ordinary group action strip"',
            compass_start,
        )
        compass_slice = summary_primary_slice[compass_start:compass_end]
        self.assertIn('href="#candidate-pool"', compass_slice)
        self.assertIn('href="#candidate-radar-search-quant-projection"', compass_slice)
        self.assertIn('href="#factor"', compass_slice)
        self.assertIn("DataLineageTable rows={ordinaryCandidateReviewCompassRows}", compass_slice)
        self.assertIn("Top 只表示优先复核，不是买入指令", self.page)
        self.assertIn("Watch 不是加仓或追买提示", self.page)
        self.assertIn("Excluded 不会改交易策略，也不会删除旧证据", self.page)
        self.assertNotIn("onClick=", compass_slice)
        self.assertNotIn("launchQuickScan", compass_slice)
        self.assertNotIn("postCandidateRadar", compass_slice)
        self.assertLess(
            summary_primary_slice.index('aria-label="candidate radar denoised first screen guide"'),
            compass_start,
        )
        self.assertLess(
            compass_start,
            summary_primary_slice.index('aria-label="candidate radar ordinary retirement readiness quick read"'),
        )
        self.assertIn("ordinaryCandidateGroupActionSentence", self.page)
        self.assertIn("ordinaryCandidateGroupActionItems", self.page)
        self.assertIn("ordinaryCandidateGroupActionRows", self.page)
        self.assertIn('aria-label="candidate radar ordinary group action strip"', summary_primary_slice)
        self.assertIn("分组后下一步", summary_primary_slice)
        self.assertIn('aria-label="candidate radar ordinary group action sentence"', summary_primary_slice)
        self.assertIn("Top ${ordinaryCandidateTopCount} 先解释首位候选", self.page)
        self.assertIn("Watch ${ordinaryCandidateWatchCount} 只观察触发条件", self.page)
        self.assertIn("Excluded ${ordinaryCandidateExcludedCount} 先看排除原因", self.page)
        for group_action_label in (
            'label: "Top 下一步"',
            'label: "Watch 下一步"',
            'label: "Excluded 下一步"',
            'label: "结果入口"',
            'label: "数据缺口"',
            'label: "不会发生"',
        ):
            self.assertIn(group_action_label, self.page)
        for group_action_row in (
            '分组: "Top"',
            '分组: "Watch"',
            '分组: "Excluded"',
            '分组: "结果回放"',
        ):
            self.assertIn(group_action_row, self.page)
        group_action_start = summary_primary_slice.index('aria-label="candidate radar ordinary group action strip"')
        group_action_end = summary_primary_slice.index(
            'aria-label="candidate radar ordinary retirement readiness quick read"',
            group_action_start,
        )
        group_action_slice = summary_primary_slice[group_action_start:group_action_end]
        self.assertIn("MetricGrid items={ordinaryCandidateGroupActionItems}", group_action_slice)
        self.assertIn('aria-label="candidate radar ordinary group action local links"', group_action_slice)
        self.assertIn('href="#candidate-pool"', group_action_slice)
        self.assertIn('href="#candidate-radar-search-quant-projection"', group_action_slice)
        self.assertIn('href="#factor"', group_action_slice)
        self.assertIn('href={DATA_CAPABILITY_HREF}', group_action_slice)
        self.assertIn('href="#marginEtf"', group_action_slice)
        self.assertIn('aria-label="candidate radar ordinary group action rows"', group_action_slice)
        self.assertIn("<summary>查看分组动作读法</summary>", group_action_slice)
        self.assertIn("DataLineageTable rows={ordinaryCandidateGroupActionRows}", group_action_slice)
        self.assertIn("不运行快扫、不创建 task、不调用 Tushare/DeepSeek/GitHub、不启动 worker", group_action_slice)
        self.assertIn("不会买入、卖出、加仓、加融资、下单或修改 strategy action", group_action_slice)
        self.assertIn("本行动条只切换本地页面；不快扫、不 POST、不调用 provider/model/worker、不交易", self.page)
        self.assertIn("Watch 不代表追买、不代表提高仓位，也不会改交易策略", self.page)
        self.assertIn("Excluded 只保留研究排除理由；不删除旧证据、不创建交易动作", self.page)
        self.assertNotIn("onClick=", group_action_slice)
        self.assertNotIn("launchQuickScan", group_action_slice)
        self.assertNotIn("postCandidateRadar", group_action_slice)
        self.assertLess(compass_start, group_action_start)
        self.assertLess(
            group_action_start,
            summary_primary_slice.index('aria-label="candidate radar ordinary retirement readiness quick read"'),
        )
        self.assertLess(
            compass_start,
            self.page.index('title="下一票候选池"'),
        )
        self.assertIn('aria-label="candidate radar ordinary retirement readiness quick read"', summary_primary_slice)
        production_blocker_start = summary_primary_slice.index(
            'aria-label="candidate radar ordinary retirement readiness quick read"'
        )
        production_blocker_end = summary_primary_slice.index(
            'aria-label="candidate radar coarse fine screening ordinary summary"',
            production_blocker_start,
        )
        production_blocker_slice = summary_primary_slice[production_blocker_start:production_blocker_end]
        self.assertIn("退旧雷达前还缺什么", production_blocker_slice)
        self.assertIn("退掉旧雷达前还要补全池/深研、真实数据覆盖、浏览器验收和旧雷达退场审查", production_blocker_slice)
        self.assertIn("ordinaryRetirementReadinessItems", production_blocker_slice)
        self.assertIn("ordinaryRetirementReadinessGapRows", production_blocker_slice)
        self.assertIn('aria-label="candidate radar ordinary retirement readiness row details"', production_blocker_slice)
        self.assertIn("<summary>查看退场缺口明细</summary>", production_blocker_slice)
        self.assertIn("缺口行表默认收起，避免普通首屏变成 acceptance report", production_blocker_slice)
        self.assertIn("DataLineageTable rows={ordinaryRetirementReadinessGapRows}", production_blocker_slice)
        self.assertIn('aria-label="candidate radar ordinary browser qa quick read"', production_blocker_slice)
        self.assertIn("本地页面 QA 速读", production_blocker_slice)
        self.assertIn("ordinaryBrowserQaItems", production_blocker_slice)
        self.assertIn("ordinaryBrowserQaReadbackRows", production_blocker_slice)
        self.assertIn('aria-label="candidate radar ordinary browser qa readback rows"', production_blocker_slice)
        self.assertIn("<summary>查看本地页面 QA 分层</summary>", production_blocker_slice)
        self.assertIn("这里不打开浏览器、不写 artifact、不创建 POST task", production_blocker_slice)
        self.assertIn("DataLineageTable rows={ordinaryBrowserQaReadbackRows}", production_blocker_slice)
        for production_label in (
            'label: "退旧雷达"',
            'label: "缺口进度"',
            'label: "还缺"',
            'label: "别误判"',
            'label: "研究边界"',
            'label: "本地页面 QA"',
            'label: "覆盖"',
            'label: "复核"',
            'label: "不能证明"',
        ):
            self.assertIn(production_label, self.page)
        self.assertIn("本地收据、dry-run 和浏览器手册都不是最终完成证据", self.page)
        self.assertIn("只读本地阶段清单；不创建 task、不调用 Tushare/DeepSeek/GitHub、不交易", self.page)
        self.assertIn("本地收据、dry-run 和浏览器手册都不能当最终完成证据", production_blocker_slice)
        self.assertIn("普通页只读 candidate_browser_qa_evidence_summary；不打开浏览器、不创建 task、不调用 provider/model", self.page)
        self.assertIn("不是 durable CI、不是 provider-backed 验收、不是旧雷达退场", self.page)
        self.assertNotIn("onClick=", production_blocker_slice)
        self.assertNotIn("launchProductionReplacementReview", production_blocker_slice)
        self.assertNotIn("postCandidateRadarProductionReplacementReview", production_blocker_slice)
        self.assertNotIn("launchBrowserQaReview", production_blocker_slice)
        self.assertNotIn("postCandidateRadarBrowserQaReview", production_blocker_slice)
        self.assertIn('aria-label="candidate radar ordinary repeated result progress details"', summary_primary_slice)
        self.assertIn("<summary>Research Assist / Audit Details：结果和进度明细</summary>", summary_primary_slice)
        self.assertIn("最近 P3、P2/P3 checkpoint 和进度 watch 默认收起", summary_primary_slice)
        self.assertIn("普通首屏先看操作台、确认按钮、TaskStatusPanel 和确认后一屏结果", summary_primary_slice)
        repeated_progress_start = summary_primary_slice.index(
            'aria-label="candidate radar ordinary repeated result progress details"'
        )
        repeated_progress_end = summary_primary_slice.index(
            'aria-label="candidate radar ordinary task progress details"',
            repeated_progress_start,
        )
        repeated_progress_slice = summary_primary_slice[repeated_progress_start:repeated_progress_end]
        self.assertIn('aria-label="candidate radar ordinary p3 one minute result"', repeated_progress_slice)
        self.assertIn('aria-label="candidate radar p2 p3 connection checkpoint"', repeated_progress_slice)
        self.assertIn('aria-label="candidate radar ordinary visible progress watch"', repeated_progress_slice)
        self.assertIn("最近任务、当前步骤和回放入口收在普通摘要明细里", repeated_progress_slice)
        self.assertNotIn("postCandidateRadar", repeated_progress_slice)
        self.assertNotIn("launchQuantProjectionProviderModelAcceptance", repeated_progress_slice)
        self.assertLess(
            repeated_progress_start,
            summary_primary_slice.index('aria-label="candidate radar ordinary task progress details"'),
        )
        self.assertIn('aria-label="candidate radar ordinary usable now strip"', summary_primary_slice)
        self.assertIn("现在可用状态", summary_primary_slice)
        self.assertIn("quantProjectionUsableNowItems", summary_primary_slice)
        self.assertIn('aria-label="candidate radar ordinary task progress details"', summary_primary_slice)
        self.assertIn("<summary>任务和回放状态</summary>", summary_primary_slice)
        self.assertIn("任务编号、任务索引、checkpoint 和 P2/P3 回放状态默认收起", summary_primary_slice)
        for usable_label in (
            'label: "本地 FastAPI"',
            'label: "确认按钮"',
            'label: "最近任务"',
            'label: "结果回放"',
            'label: "边用边看"',
            'label: "现在点哪"',
        ):
            self.assertIn(usable_label, self.page)
        self.assertIn("这条只合成本地 FastAPI、确认按钮、最近任务和 P2/P3 回放状态", summary_primary_slice)
        self.assertIn("getTasks", self.page)
        self.assertIn("const [taskIndex, setTaskIndex] = useState<TaskStatusIndex | null>(null);", self.page)
        self.assertIn("taskIndex?.latest_confirmed_symbol", self.page)
        self.assertIn("taskIndex?.latest_confirmed_task_id", self.page)
        self.assertIn("taskIndex?.latest_confirmed_task_status", self.page)
        self.assertIn("taskIndex?.latest_confirmed_task_current_step", self.page)
        self.assertIn("quantProjectionTaskIndexProgressItems", summary_primary_slice)
        self.assertIn('aria-label="candidate radar local task index progress watch"', summary_primary_slice)
        self.assertIn("本地任务进度", summary_primary_slice)
        self.assertIn("GET /api/tasks + CandidateRadar cache", self.page)
        self.assertIn("任务索引回读未触发外联、未创建 task", self.page)
        self.assertIn("边用边看：{quantProjectionProgressWatchNext}", summary_primary_slice)
        self.assertIn("这只来自 GET /api/tasks 和 CandidateRadar cache，不创建第二个 task", summary_primary_slice)
        self.assertLess(
            summary_primary_slice.index('aria-label="candidate radar ordinary usable now strip"'),
            summary_primary_slice.index('aria-label="candidate radar local task index progress watch"'),
        )
        self.assertLess(
            summary_primary_slice.index('aria-label="candidate radar local task index progress watch"'),
            summary_primary_slice.index('aria-label="candidate radar ordinary progress checkpoint"'),
        )
        for downshifted_label in (
            'label: "候选来源"',
            'label: "评分说明"',
            'label: "P1 回放顺序"',
            'label: "P1 确认后等待"',
            'label: "P2 checkpoint"',
            'label: "P2 写入边界"',
            'label: "任务边界"',
            'label: "结果位置"',
        ):
            self.assertNotIn(downshifted_label, summary_primary_slice)
            self.assertIn(downshifted_label, summary_extra_slice)
        self.assertIn("P0/P1/P2 checkpoint、候选来源、评分说明、P1 回放顺序、P2 checkpoint 和结果位置默认收起", summary_extra_slice)

        self.assertLess(self.page.index('title="普通用户雷达摘要"'), self.page.index("<summary>开发 / 审计指标</summary>"))
        self.assertLess(self.page.index('title="下一票候选池"'), self.page.index("<summary>扫描覆盖 / 验收审计</summary>"))
        self.assertIn("const candidateRadarP0Blocked = Boolean(error)", self.page)
        self.assertIn('    ? "先恢复 P0 本地联通"', self.page)
        self.assertIn('    : "输入股票代码并点击确认";', self.page)
        self.assertIn("ordinaryPrimaryActionLabel", self.page)
        self.assertIn("ordinaryPrimaryActionBoundary", self.page)
        self.assertIn("回一键启动预检恢复联通", self.page)
        self.assertIn("输入代码并确认", self.page)
        self.assertIn("P0 未联通时主下一步只跳转一键启动预检", self.page)
        self.assertIn("不创建快扫 task、不调用 provider/model", self.page)
        self.assertIn("主下一步跳到搜票确认区；输入只做本地校验，只有确认按钮创建 Tushare-first POST task", self.page)
        self.assertIn("本地快扫和输入股票池保留为可选补证；主路径走搜票确认", self.page)
        self.assertIn('href="#candidate-radar-search-quant-projection"', self.page)
        self.assertIn('id="candidate-radar-search-quant-projection"', self.page)
        first_screen_confirm_start = self.page.index('id="candidate-radar-search-quant-projection"')
        self.assertLess(
            first_screen_confirm_start,
            self.page.index('aria-label="candidate radar first screen quant projection actions"', first_screen_confirm_start),
        )
        self.assertLess(
            first_screen_confirm_start,
            self.page.index('aria-label="candidate radar next user actions"', first_screen_confirm_start),
        )
        first_screen_actions_start = self.page.index('aria-label="candidate radar first screen quant projection actions"', first_screen_confirm_start)
        first_screen_actions_end = self.page.index('className="ordinary-status-note"', first_screen_actions_start)
        first_screen_actions = self.page[first_screen_actions_start:first_screen_actions_end]
        self.assertIn('href="#factor/factor-score"', first_screen_actions)
        self.assertIn('href="#next/next-session-chart"', first_screen_actions)
        self.assertIn("candidateRadarP0HandoffPacketRows", self.page)
        self.assertIn("desktopPreflight.p0_to_p1_ordinary_handoff_rows", self.page)
        self.assertIn("candidateRadarP0HandoffRows", self.page)
        self.assertIn("candidateRadarP0HandoffLabel", self.page)
        self.assertIn('<details className="developer-audit-details" aria-label="candidate radar ordinary p0 local connection diagnostics">', self.page)
        self.assertIn("<summary>查看本地联通</summary>", self.page)
        self.assertIn("首页已经提供本地 FastAPI 接线速读", self.page)
        self.assertIn("普通主线默认收起 P0 联通表", self.page)
        self.assertIn('aria-label="candidate radar p0 to p1 preflight handoff"', self.page)
        self.assertIn("P0 到 P1 交接回读", self.page)
        self.assertIn("优先读取 desktop preflight 的 p0_to_p1_ordinary_handoff_rows", self.page)
        self.assertIn("四段 ready 后只切到搜票量化推演卡；输入保持静默，确认按钮才创建 Tushare-first POST task", self.page)
        self.assertIn("ordinaryP1ConfirmPathLabel", self.page)
        self.assertIn("ordinaryP1ConfirmPathBoundary", self.page)
        self.assertIn("ordinaryP1ConfirmPathRows", self.page)
        self.assertIn("ordinaryP1ToP3StageRailState", self.page)
        self.assertIn("ordinaryP1ToP3StageRailSteps", self.page)
        self.assertIn('aria-label="candidate radar p1 direct confirmation handoff"', self.page)
        self.assertIn("P1 直接确认入口", self.page)
        self.assertIn("这个入口只做本地锚点跳转", self.page)
        self.assertIn('<details className="developer-audit-details" aria-label="candidate radar denoised p1 p3 details">', self.page)
        self.assertIn("<summary>Research Assist / Audit Details：P1/P2/P3 回放明细</summary>", self.page)
        self.assertIn("普通首屏保留确认按钮、TaskStatusPanel、刷新本地回放和候选池", self.page)
        self.assertIn("避免打开 #candidates 时像 acceptance report", self.page)
        self.assertIn('aria-label="candidate radar p2 three surface quick status"', self.page)
        self.assertIn("P2 三面速读", self.page)
        self.assertIn("cache、call_ledger、packet 是否进入本地回放", self.page)
        self.assertIn('aria-label="candidate radar p3 first screen result quick read"', self.page)
        self.assertIn("P3 结果首屏速读", self.page)
        self.assertIn("本速读不创建 task、不调用 DeepSeek、不生成交易动作", self.page)
        self.assertIn("首屏直接回放服务端 ordinary_result_quick_read_rows", self.page)
        self.assertIn("P1 主路径：点击确认创建 ${quantProjectionSymbolValidation.normalized} 的 Tushare-first POST task", self.page)
        self.assertIn("P1 主路径：先输入股票代码；输入只做本地校验，确认按钮才创建 Tushare-first task", self.page)
        self.assertIn("P1 主路径只允许确认按钮创建 Tushare-first task", self.page)
        self.assertIn("搜索输入、页面打开、React render、GET cache 和结果链接都不外联", self.page)
        self.assertIn('aria-label="candidate radar ordinary p1 to p3 stage rail"', self.page)
        self.assertIn("P1 到 P3 阶段速览", self.page)
        self.assertIn("这条状态轨只读本地输入、task receipt 和 cache 回放", self.page)
        self.assertIn('label: "输入静默"', self.page)
        self.assertIn('label: "确认按钮"', self.page)
        self.assertIn('label: "任务接收"', self.page)
        self.assertIn('label: "P2 三面"', self.page)
        self.assertIn('label: "P3 速读"', self.page)
        self.assertIn('"POST task ready"', self.page)
        self.assertIn('"cache/ledger/packet"', self.page)
        self.assertIn('"可解释结果"', self.page)
        p0_diagnostics_index = self.page.index('aria-label="candidate radar ordinary p0 local connection diagnostics"')
        p0_gate_index = self.page.index('aria-label="candidate radar ordinary p0 frontend backend readiness"', p0_diagnostics_index)
        p0_handoff_index = self.page.index('aria-label="candidate radar p0 to p1 preflight handoff"', p0_gate_index)
        primary_action_index = self.page.index('aria-label="candidate radar primary next action"', p0_gate_index)
        next_user_actions_index = self.page.index('aria-label="candidate radar next user actions"', primary_action_index)
        p1_to_p3_rail_index = self.page.index('aria-label="candidate radar ordinary p1 to p3 stage rail"', p0_gate_index)
        p5_detail_index = self.page.index('aria-label="candidate radar audit p5 governance details"')
        p6_detail_index = self.page.index('aria-label="candidate radar audit p6 strict closeout handoff"', p5_detail_index)
        action_slice_end = self.page.index('aria-label="candidate radar ordinary audit shortcuts"', next_user_actions_index)
        action_slice = self.page[primary_action_index:action_slice_end]
        direct_handoff_index = self.page.index('aria-label="candidate radar p1 direct confirmation handoff"')
        p2_quick_status_index = self.page.index('aria-label="candidate radar p2 three surface quick status"')
        p3_first_screen_index = self.page.index('aria-label="candidate radar p3 first screen result quick read"')
        denoised_detail_index = self.page.index('aria-label="candidate radar denoised p1 p3 details"')
        denoised_detail_slice = self.page[denoised_detail_index:p0_diagnostics_index]
        p3_first_screen_slice = self.page[p3_first_screen_index:p0_diagnostics_index]
        self.assertIn('aria-label="candidate radar p1 direct confirmation handoff"', denoised_detail_slice)
        self.assertIn('aria-label="candidate radar p2 three surface quick status"', denoised_detail_slice)
        self.assertIn('aria-label="candidate radar p3 first screen result quick read"', denoised_detail_slice)
        self.assertIn('aria-label="candidate radar p3 one minute decision brief"', p3_first_screen_slice)
        self.assertIn("P3 一分钟决策速读", p3_first_screen_slice)
        self.assertIn("ordinary_result_decision_brief_rows", p3_first_screen_slice)
        self.assertIn("先看结论、再看来源、最后看下一步和边界", p3_first_screen_slice)
        self.assertIn("rows={quantProjectionP3DecisionBriefRows}", p3_first_screen_slice)
        self.assertIn("<MetricGrid items={quantProjectionP3ResultSummaryItems} />", p3_first_screen_slice)
        self.assertIn('label: "P3 结果证据"', self.page)
        self.assertIn("quantProjectionP3ExplainableResultCheckpointLabel", self.page)
        self.assertIn("rows={quantProjectionOrdinaryResultQuickRows}", p3_first_screen_slice)
        self.assertIn("现在能读什么、结果从哪里来、还缺什么", p3_first_screen_slice)
        self.assertNotIn("postCandidateRadarQuantProjection", p3_first_screen_slice)
        self.assertNotIn("launchQuantProjection", p3_first_screen_slice)
        self.assertLess(p0_gate_index, p0_handoff_index)
        self.assertLess(direct_handoff_index, p0_gate_index)
        self.assertLess(denoised_detail_index, direct_handoff_index)
        self.assertLess(direct_handoff_index, p2_quick_status_index)
        self.assertLess(p2_quick_status_index, p3_first_screen_index)
        self.assertLess(p3_first_screen_index, p0_diagnostics_index)
        self.assertLess(p0_diagnostics_index, p0_gate_index)
        self.assertLess(p3_first_screen_index, p0_gate_index)
        self.assertLess(p2_quick_status_index, p0_gate_index)
        self.assertLess(p0_handoff_index, p1_to_p3_rail_index)
        self.assertLess(p0_gate_index, p1_to_p3_rail_index)
        self.assertLess(p1_to_p3_rail_index, primary_action_index)
        self.assertLess(primary_action_index, next_user_actions_index)
        self.assertLess(next_user_actions_index, action_slice_end)
        self.assertLess(action_slice_end, self.page.index('id="audit" className="developer-audit-details"'))
        self.assertLess(p5_detail_index, p6_detail_index)
        self.assertIn('aria-label="radar summary quant projection symbol"', action_slice)
        self.assertIn("renderQuantProjectionPrimaryAction(quantProjectionSummarySubmitHelpId)", action_slice)
        self.assertIn("renderQuantProjectionPrimaryAction", self.page)
        self.assertIn('href="#factor"', action_slice)
        self.assertIn('href="#next"', action_slice)
        self.assertNotIn("postCandidateRadarQuantProjectionProviderModelAcceptance", action_slice)
        self.assertNotIn("launchQuantProjectionAcceptanceDryRun", action_slice)
        self.assertIn("quantProjectionOneScreenPacketRows", self.page)
        self.assertIn("searchQuantProjectionSmallDataWriteback.ordinary_one_screen_action_rows", self.page)
        self.assertIn("quantProjectionOneScreenActionRows", self.page)
        self.assertIn('aria-label="candidate radar ordinary one screen actions"', self.page)
        self.assertIn("一屏行动摘要", self.page)
        self.assertIn("优先读取服务端 ordinary_one_screen_action_rows", self.page)
        self.assertIn("确认、任务、写回、结果合成一张普通用户表", self.page)
        self.assertIn("只读回放本地状态，不从摘要创建 task", self.page)
        self.assertIn("rows={quantProjectionOneScreenActionRows}", self.page)
        self.assertIn('aria-label="candidate radar ordinary p2 p3 replay checklist"', self.page)
        self.assertIn("确认后先看这张只读索引", self.page)
        self.assertIn("确认回执、任务回放、数据接口和 P3 结果速读都来自本地 cache / ledger / packet", self.page)
        self.assertIn("不会创建 task、不会补调 Tushare/DeepSeek", self.page)
        self.assertIn("rows={quantProjectionReadbackIndexRows}", self.page)
        self.assertIn('行动: "1. 确认"', self.page)
        self.assertIn('行动: "2. 任务"', self.page)
        self.assertIn('行动: "3. 写回"', self.page)
        self.assertIn('行动: "4. 结果"', self.page)
        self.assertIn('aria-label="candidate radar ordinary p1 p2 detail readback"', self.page)
        self.assertIn("<summary>查看 P1/P2 回放明细</summary>", self.page)
        self.assertIn("一屏行动摘要已经覆盖普通下一步", self.page)
        self.assertIn("确认链路、P1 路径和 P2 三面核对默认收起", self.page)
        self.assertIn("quantProjectionConfirmedChainQuickRows", self.page)
        self.assertIn('aria-label="candidate radar ordinary confirmed chain quick read"', self.page)
        self.assertIn("确认后链路速读", self.page)
        self.assertIn("普通用户先看这张确认后链路速读", self.page)
        self.assertIn('链路节点: "1. 点击确认"', self.page)
        self.assertIn('链路节点: "2. Tushare-first"', self.page)
        self.assertIn('链路节点: "3. P2 三面写回"', self.page)
        self.assertIn('链路节点: "4. P3 可解释结果"', self.page)
        self.assertIn('链路节点: "5. 结果入口"', self.page)
        self.assertIn("只有确认按钮会创建 POST task；页面打开、搜索输入、React render 和 GET cache 不外联", self.page)
        self.assertIn("Tushare 只允许在 POST task / worker 内调用；DeepSeek 只读取安全事实摘要，可成功或安全降级", self.page)
        self.assertIn("quantProjectionOrdinaryProgressCheckpointItems", self.page)
        self.assertIn("quantProjectionOrdinaryProgressCheckpointAnchor", self.page)
        self.assertIn("quantProjectionOrdinaryProgressCheckpointLabel", self.page)
        self.assertIn('aria-label="candidate radar ordinary progress checkpoint"', self.page)
        self.assertIn("当前进度 checkpoint", self.page)
        self.assertIn('label: "当前 checkpoint"', self.page)
        self.assertIn('label: "确认标的"', self.page)
        self.assertIn('label: "任务编号"', self.page)
        self.assertIn('label: "下一步入口"', self.page)
        self.assertIn('label: "结果状态"', self.page)
        self.assertIn("只读回放；确认按钮之外不创建 task；不交易、不改交易策略", self.page)
        self.assertIn("checkpoint 只汇总当前输入、task id、P2/P3 回放和下一步入口", self.page)
        self.assertIn("链接只切换本地页面或锚点，不创建 task、不调用 Tushare/DeepSeek、不改 strategy action", self.page)
        self.assertIn('href={quantProjectionOrdinaryProgressCheckpointAnchor}', self.page)
        self.assertIn("{quantProjectionOrdinaryProgressCheckpointLabel}</a>", self.page)
        self.assertIn('aria-label="candidate radar ordinary p1 confirm path"', self.page)
        self.assertIn("P1 普通确认路径", self.page)
        self.assertIn("普通用户先看这条 P1 路径", self.page)
        self.assertIn('阶段: "1. 输入股票代码"', self.page)
        self.assertIn('阶段: "2. 点击确认按钮"', self.page)
        self.assertIn('阶段: "3. 看任务接收"', self.page)
        self.assertIn('阶段: "4. 回放本地结果"', self.page)
        self.assertIn("只有确认按钮会 POST /api/candidate-radar/quant-projection", self.page)
        primary_action_start = self.page.index('aria-label="candidate radar primary next action"')
        primary_action_end = self.page.index('aria-label="candidate radar next user actions"', primary_action_start)
        primary_action_slice = self.page[primary_action_start:primary_action_end]
        self.assertIn('href="#candidate-radar-search-quant-projection"', primary_action_slice)
        self.assertNotIn("launchQuickScan", primary_action_slice)
        self.assertIn('href="#desktop"', self.page)
        self.assertIn('aria-label="open p0 desktop preflight from radar summary"', self.page)
        self.assertIn("ordinaryCandidateGroupLabel", self.page)
        self.assertIn("ordinaryScanScopeLabel", self.page)
        self.assertIn("ordinaryCandidateSourceLabel", self.page)
        self.assertIn("ordinaryScoringReasonLabel", self.page)
        self.assertIn("Top ${ordinaryCandidateTopCount} / Watch ${ordinaryCandidateWatchCount} / Excluded ${ordinaryCandidateExcludedCount}", self.page)
        self.assertIn("模式：${String(cache.scan_mode ?? \"cache_only\")}", self.page)
        self.assertIn("范围：${String(scanExecutionSummary.scan_family ?? localPoolAudit.input_source ?? \"本地缓存\")}", self.page)
        self.assertIn("按本地缓存顺序展示；评分理由不足会作为缺口显示", self.page)
        self.assertIn("不重排、不生成交易动作", self.page)
        self.assertIn("候选分组：{ordinaryCandidateGroupLabel}", self.page)
        self.assertIn("ordinaryOptionalNextClick", self.page)
        self.assertIn("ordinaryCandidateReviewRows", self.page)
        self.assertIn("证据摘要: displayText(row.evidence_chain_summary", self.page)
        self.assertIn("按本地缓存顺序复核；不重排、不重算分数、不生成交易动作", self.page)
        self.assertIn('title="候选复核清单"', self.page)
        self.assertIn("普通入口只显示标的、分数、状态、证据摘要和边界；原始 candidate_rows 下沉到详情", self.page)
        self.assertIn("<summary>原始 candidate_rows 审计</summary>", self.page)
        self.assertLess(self.page.index('title="候选复核清单"'), self.page.index("<summary>原始 candidate_rows 审计</summary>"))
        self.assertIn("需要更新时再运行本地快扫", self.page)
        self.assertIn("搜单票时输入代码后点击生成 3.0 量化推演", self.page)
        self.assertIn("ordinaryPendingSourceLabel", self.page)
        self.assertIn("ordinaryDegradedSourceLabel", self.page)
        self.assertIn("pending：", self.page)
        self.assertIn("degraded：", self.page)
        self.assertIn("本地候选缓存可用", self.page)
        self.assertIn("手动触发或关闭", self.page)
        self.assertIn("live_light 已配置；仍需确认按钮触发 Tushare-first task", self.page)
        self.assertIn("待 governed executor；不作为数据源或动作", self.page)
        self.assertIn("雷达摘要只读展示候选缓存", self.page)
        self.assertIn("manual/live_light 补证必须走 POST task / worker", self.page)
        self.assertIn('aria-label="candidate radar primary next action"', self.page)
        self.assertIn('href="#candidate-pool"', self.page)
        self.assertIn('id="candidate-pool"', self.page)
        self.assertIn("候选不是买入指令；不真实交易、不下单、不改交易策略", self.page)
        summary_start = self.page.index('title="普通用户雷达摘要"')
        self.assertIn("普通用户先看上方雷达摘要、候选池和搜票量化推演", self.page)
        self.assertIn("普通用户无需先打开工程审计；默认先看候选、确认结果和本地回放。", self.page)
        self.assertIn('aria-label="candidate radar ordinary audit shortcuts"', self.page)
        self.assertIn("<summary>高级诊断入口</summary>", self.page)
        self.assertIn("工程审计明细继续默认收起", self.page)
        self.assertIn("完整 call ledger、release gate 和配置状态下沉", self.page)
        self.assertIn('<a href="#audit">调用审计</a>', self.page)
        self.assertIn('<a href="#settings">配置健康</a>', self.page)
        self.assertIn('id="settings" className="developer-audit-details"', self.page)
        self.assertIn('aria-label="candidate radar settings audit details"', self.page)
        self.assertIn('id="audit" className="developer-audit-details"', self.page)
        self.assertIn('aria-label="candidate radar developer audit details"', self.page)
        self.assertIn('aria-label="candidate radar audit evidence route details"', self.page)
        self.assertIn("<summary>补证路线 / 缺口审计</summary>", self.page)
        self.assertIn("P4 将补证路线从普通主卡下沉到开发审计区", self.page)
        self.assertIn('aria-label="candidate radar evidence recovery audit details"', self.page)
        self.assertIn("<summary>后续补证路线审计</summary>", self.page)
        self.assertIn("P4 将手动补证步骤默认收起", self.page)
        self.assertIn('<details className="developer-audit-details" aria-label="candidate radar result delta audit details">', self.page)
        self.assertIn("<summary>结果变化 / 浏览器差异审计</summary>", self.page)
        self.assertIn("结果变化 diff 和 browser visual delta 属于 P4/P6 审计补证", self.page)
        result_delta_audit_index = self.page.index('aria-label="candidate radar result delta audit details"')
        candidate_priority_index = self.page.index('title="候选优先级说明"')
        self.assertLess(result_delta_audit_index, candidate_priority_index)
        result_delta_audit = self.page[result_delta_audit_index:candidate_priority_index]
        self.assertIn('title="雷达结果变化清晰度"', result_delta_audit)
        self.assertIn("普通路径继续先看候选优先级说明、候选复核清单和搜票结果", result_delta_audit)
        ordinary_audit_shortcuts_index = self.page.index('aria-label="candidate radar ordinary audit shortcuts"')
        self.assertLess(self.page.index('title="搜票量化推演"'), self.page.index('id="settings" className="developer-audit-details"'))
        self.assertLess(self.page.index('title="搜票量化推演"'), self.page.index('id="audit" className="developer-audit-details"'))
        self.assertLess(summary_start, ordinary_audit_shortcuts_index)
        self.assertLess(ordinary_audit_shortcuts_index, self.page.index('id="settings" className="developer-audit-details"'))
        self.assertLess(ordinary_audit_shortcuts_index, self.page.index('id="audit" className="developer-audit-details"'))
        self.assertLess(self.page.index('id="audit" className="developer-audit-details"'), self.page.index('aria-label="candidate radar audit evidence route details"'))
        self.assertLess(self.page.index('aria-label="candidate radar audit evidence route details"'), self.page.index("补证路线概览"))
        self.assertIn('<details className="developer-audit-details" aria-label="candidate radar audit p5 governance details">', self.page)
        self.assertIn("<summary>DeepSeek 解释治理状态</summary>", self.page)
        self.assertIn("P4 将模型治理状态下沉到开发审计区", self.page)
        self.assertIn("P4 将 14 LTG strict closeout 交接下沉到开发审计区", self.page)
        summary_end = self.page.index('title="下一票候选池"', summary_start)
        summary_slice = self.page[summary_start:summary_end]
        self.assertNotIn('aria-label="candidate radar audit p5 governance details"', summary_slice)
        self.assertNotIn('aria-label="candidate radar audit p6 strict closeout handoff"', summary_slice)
        self.assertNotIn("<summary>DeepSeek 解释治理状态</summary>", summary_slice)
        self.assertNotIn("<summary>P6 14 LTG strict closeout 交接</summary>", summary_slice)
        self.assertLess(self.page.index('aria-label="candidate radar ordinary p3 result handoff index"'), self.page.index('id="audit" className="developer-audit-details"'))
        self.assertLess(self.page.index('aria-label="candidate radar primary next action"'), self.page.index('id="audit" className="developer-audit-details"'))
        self.assertLess(ordinary_audit_shortcuts_index, self.page.index('id="audit" className="developer-audit-details"'))
        self.assertLess(self.page.index('id="audit" className="developer-audit-details"'), self.page.index('aria-label="candidate radar audit p5 governance details"'))
        self.assertLess(self.page.index('title="候选复核清单"'), self.page.index('aria-label="candidate radar evidence recovery audit details"'))
        self.assertLess(self.page.index('aria-label="candidate radar evidence recovery audit details"'), self.page.index('title="排除候选"'))
        self.assertLess(self.page.index('aria-label="candidate radar audit p5 governance details"'), self.page.index('aria-label="candidate radar audit p6 strict closeout handoff"'))
        self.assertLess(
            self.page.index('aria-label="candidate radar ordinary p1 to p3 stage rail"'),
            self.page.index('aria-label="candidate radar ordinary one screen actions"'),
        )
        self.assertLess(
            self.page.index('aria-label="candidate radar ordinary progress checkpoint"'),
            self.page.index('aria-label="candidate radar first screen quant projection confirmation"'),
        )
        self.assertLess(
            self.page.index('aria-label="candidate radar ordinary one screen actions"'),
            self.page.index('aria-label="quant projection submit recovery quick read"'),
        )
        self.assertLess(
            self.page.index('aria-label="quant projection submit recovery quick read"'),
            self.page.index('aria-label="quant projection ordinary confirm outcome quick read"'),
        )
        self.assertLess(
            self.page.index('aria-label="quant projection ordinary confirm outcome quick read"'),
            self.page.index('aria-label="candidate radar p1 tushare first chain quick read"'),
        )
        self.assertLess(
            self.page.index('aria-label="candidate radar p1 tushare first chain quick read"'),
            self.page.index('aria-label="candidate radar ordinary p3 explainable result quick read"'),
        )
        self.assertLess(
            self.page.index('aria-label="candidate radar ordinary one screen actions"'),
            self.page.index('aria-label="candidate radar ordinary p2 p3 replay checklist"'),
        )
        self.assertLess(
            self.page.index('aria-label="candidate radar ordinary p2 p3 replay checklist"'),
            self.page.index('aria-label="candidate radar ordinary p1 p2 detail readback"'),
        )
        self.assertLess(
            self.page.index('aria-label="candidate radar ordinary p1 p2 detail readback"'),
            self.page.index('aria-label="candidate radar ordinary p3 result handoff index"'),
        )
        self.assertLess(
            self.page.index('aria-label="candidate radar ordinary p1 p2 detail readback"'),
            self.page.index('aria-label="candidate radar ordinary confirmed chain quick read"'),
        )
        self.assertLess(
            self.page.index('aria-label="candidate radar ordinary p1 to p3 stage rail"'),
            self.page.index('aria-label="candidate radar ordinary confirmed chain quick read"'),
        )
        self.assertLess(
            self.page.index('aria-label="candidate radar ordinary confirmed chain quick read"'),
            self.page.index('aria-label="candidate radar ordinary p1 confirm path"'),
        )
        self.assertNotIn(
            '工程审计明细默认收起；完整 call ledger、release gate 和配置状态在 <a href="#audit">调用审计</a> / <a href="#settings">配置健康</a>。',
            self.page,
        )
        deepseek_label_start = self.page.index("const ordinaryDeepSeekSourceLabel")
        deepseek_label_end = self.page.index("const ordinaryProviderGapLabel", deepseek_label_start)
        deepseek_label_slice = self.page[deepseek_label_start:deepseek_label_end]
        summary_end = self.page.index('title="下一票候选池"', summary_start)
        summary_slice = self.page[summary_start:summary_end]
        self.assertIn("待 governed executor；不作为数据源或动作", deepseek_label_slice)
        self.assertNotIn("轻量实时后台任务", deepseek_label_slice)
        self.assertNotIn("轻量实时后台任务", summary_slice)
        self.assertIn('{ label: "解释状态", value: ordinaryDeepSeekSourceLabel }', summary_slice)
        self.assertNotIn('DeepSeek", value: bootstrapLiveLight.deepseek_on_open === true ? "轻量实时后台任务"', summary_slice)

    def test_candidate_pool_current_result_card_is_local_navigation_only(self):
        pool_start = self.page.index('title="下一票候选池"')
        pool_end = self.page.index('title="搜票量化推演"', pool_start)
        pool = self.page[pool_start:pool_end]

        self.assertIn("candidatePoolLeadCandidateRow", self.page)
        self.assertIn("candidatePoolLeadCandidateDisplay", self.page)
        self.assertIn("candidatePoolCurrentResultSentence", self.page)
        self.assertIn("candidatePoolCurrentResultItems", self.page)
        self.assertIn("candidatePoolGroupActionItems", self.page)
        self.assertIn("当前候选池可继续复核：先看", self.page)
        self.assertIn("这张卡只帮你挑复核对象；不生成买入、卖出、加仓或融资指令", self.page)
        self.assertIn('aria-label="candidate pool current result card"', pool)
        self.assertIn("当前候选怎么用", pool)
        self.assertIn('aria-label="candidate pool current result sentence"', pool)
        self.assertIn("MetricGrid items={candidatePoolCurrentResultItems}", pool)
        for label in (
            'label: "当前候选池"',
            'label: "先看一票"',
            'label: "为什么能看"',
            'label: "还缺什么"',
            'label: "下一步"',
            'label: "非买入边界"',
        ):
            self.assertIn(label, self.page)
        self.assertIn('aria-label="candidate pool current result actions"', pool)
        self.assertIn('aria-label="explain lead candidate from current result card"', pool)
        self.assertIn('aria-label="open factor from current result card"', pool)
        self.assertIn('aria-label="open next session from current result card"', pool)
        self.assertIn('aria-label="open margin etf from current result card"', pool)
        self.assertIn('href="#candidate-radar-search-quant-projection"', pool)
        self.assertIn('href="#factor"', pool)
        self.assertIn('href="#next"', pool)
        self.assertIn('href="#marginEtf"', pool)
        self.assertIn("只读候选池当前缓存和本地来源状态", pool)
        self.assertIn("链接只切换本地页面，不刷新外部数据、不创建新任务、不交易、不改策略", pool)
        self.assertIn('aria-label="candidate pool top watch excluded direct actions"', pool)
        self.assertIn("按分组直接下一步", pool)
        self.assertIn("Top 先解释单票，Watch 只观察触发条件，Excluded 先看排除原因", pool)
        self.assertIn("MetricGrid items={candidatePoolGroupActionItems}", pool)
        for group_label in (
            'label: "Top"',
            'label: "Watch"',
            'label: "Excluded"',
            'label: "结果回放"',
            'label: "边界"',
        ):
            self.assertIn(group_label, self.page)
        self.assertIn('aria-label="candidate pool top watch excluded direct action links"', pool)
        self.assertIn('aria-label="explain top candidate from candidate pool group actions"', pool)
        self.assertIn('aria-label="watch candidates stay in candidate pool group actions"', pool)
        self.assertIn('aria-label="review excluded candidates in candidate pool group actions"', pool)
        self.assertIn('aria-label="open factor from candidate pool group actions"', pool)
        self.assertIn('aria-label="open next session from candidate pool group actions"', pool)
        self.assertIn('aria-label="open margin etf from candidate pool group actions"', pool)
        self.assertIn("不会买入、卖出、加仓、加融资、下单或修改 strategy action", pool)

        plain_start = pool.index('aria-label="candidate pool plain result conclusion"')
        current_start = pool.index('aria-label="candidate pool current result card"')
        first_screen_items_start = pool.index("MetricGrid items={candidatePoolFirstScreenItems}", current_start)
        group_direct_start = pool.index('aria-label="candidate pool top watch excluded direct actions"', first_screen_items_start)
        group_direct_end = pool.index('<p>{String(cache.summary', group_direct_start)
        self.assertLess(plain_start, current_start)
        self.assertLess(current_start, first_screen_items_start)
        self.assertLess(first_screen_items_start, group_direct_start)
        current = pool[current_start:first_screen_items_start]
        group_direct = pool[group_direct_start:group_direct_end]
        self.assertNotIn("onClick=", current)
        self.assertNotIn("fetch(", current)
        self.assertNotIn("postCandidateRadar", current)
        self.assertNotIn("launchQuantProjection", current)
        self.assertNotIn("TaskStatusPanel", current)
        self.assertNotIn("onClick=", group_direct)
        self.assertNotIn("fetch(", group_direct)
        self.assertNotIn("postCandidateRadar", group_direct)
        self.assertNotIn("launchQuickScan", group_direct)
        self.assertNotIn("TaskStatusPanel", group_direct)

    def test_candidate_radar_progress_checkpoint_is_navigation_only(self):
        summary_start = self.page.index('title="普通用户雷达摘要"')
        summary_end = self.page.index('aria-label="candidate radar first screen quant projection confirmation"', summary_start)
        summary = self.page[summary_start:summary_end]
        checkpoint_start = summary.index('aria-label="candidate radar ordinary progress checkpoint"')
        checkpoint = summary[checkpoint_start:]

        self.assertIn("当前进度 checkpoint", checkpoint)
        self.assertIn("quantProjectionOrdinaryProgressCheckpointItems", checkpoint)
        self.assertIn('aria-label="candidate radar ordinary progress checkpoint actions"', checkpoint)
        self.assertIn('href={quantProjectionOrdinaryProgressCheckpointAnchor}', checkpoint)
        self.assertIn('href="#tasks"', checkpoint)
        self.assertIn('href="#next"', checkpoint)
        self.assertIn("链接只切换本地页面或锚点", checkpoint)
        self.assertNotIn("onClick=", checkpoint)
        self.assertNotIn("postCandidateRadarQuantProjection", checkpoint)
        self.assertNotIn("launchQuantProjection", checkpoint)

    def test_candidate_radar_task_index_progress_watch_is_read_only(self):
        summary_start = self.page.index('title="普通用户雷达摘要"')
        summary_end = self.page.index('aria-label="candidate radar ordinary progress checkpoint"', summary_start)
        summary = self.page[summary_start:summary_end]
        watch_start = summary.index('aria-label="candidate radar local task index progress watch"')
        watch = summary[watch_start:]

        self.assertIn("本地任务进度", watch)
        self.assertIn("quantProjectionTaskIndexProgressItems", watch)
        self.assertIn('label: "边用边看"', self.page)
        self.assertIn('label: "最新确认标的"', self.page)
        self.assertIn('label: "最新任务"', self.page)
        self.assertIn('label: "当前步骤"', self.page)
        self.assertIn('label: "只读来源"', self.page)
        self.assertIn("GET /api/tasks + CandidateRadar cache", self.page)
        self.assertIn("taskIndexReadbackSafe", self.page)
        self.assertIn("taskIndex.external_calls_triggered !== true", self.page)
        self.assertIn("taskIndex.latest_confirmed_symbol_creates_task_from_readback !== true", self.page)
        self.assertIn('aria-label="candidate radar local task index progress actions"', watch)
        self.assertIn('href="#tasks"', watch)
        self.assertIn('href="#factor"', watch)
        self.assertIn('href="#next"', watch)
        self.assertIn("这只来自 GET /api/tasks 和 CandidateRadar cache", watch)
        self.assertIn("不创建第二个 task、不补调 Tushare/DeepSeek、不真实交易", watch)
        self.assertNotIn("onClick=", watch)
        self.assertNotIn("postCandidateRadarQuantProjection", watch)
        self.assertNotIn("launchQuantProjection", watch)

    def test_candidate_radar_mode_layered_live_light_boundaries_are_first_screen_read_only(self):
        summary_start = self.page.index('title="普通用户雷达摘要"')
        summary_end = self.page.index('title="下一票候选池"', summary_start)
        summary = self.page[summary_start:summary_end]
        factory_start = summary.index('aria-label="candidate radar ordinary live light evidence factory"')
        mode_layer_start = summary.index('aria-label="candidate radar mode layered live light boundaries"', factory_start)
        denoise_start = summary.index('aria-label="candidate radar denoised first screen guide"', mode_layer_start)
        audit_start = self.page.index('id="audit" className="developer-audit-details"')
        mode_layer = summary[mode_layer_start:denoise_start]
        source_before_audit = self.page[:audit_start]

        self.assertLess(factory_start, mode_layer_start)
        self.assertLess(mode_layer_start, denoise_start)
        self.assertIn("ordinaryModeLayeredLiveLightItems", source_before_audit)
        self.assertIn("运行模式分层", mode_layer)
        self.assertIn("MetricGrid items={ordinaryModeLayeredLiveLightItems}", mode_layer)
        self.assertIn('label: "cache/render 层"', source_before_audit)
        self.assertIn('label: "button/task 层"', source_before_audit)
        self.assertIn('label: "provider/model 层"', source_before_audit)
        self.assertIn('label: "worker/browser 层"', source_before_audit)
        self.assertIn('label: "production 层"', source_before_audit)
        self.assertIn('label: "交易隔离"', source_before_audit)
        self.assertIn("GET cache 和 React render 只读，不创建 task", source_before_audit)
        self.assertIn("等待有效代码；输入本身保持静默", source_before_audit)
        self.assertIn("全池/深研/browser QA 需显式任务", source_before_audit)
        self.assertIn("LTG-13 未关闭", source_before_audit)
        self.assertIn("不下单、不改持仓、不改 strategy action", source_before_audit)
        self.assertIn("分层速读只解释 cache/render、button/task、provider/model、worker/browser 和 production 边界", summary)
        self.assertIn("不会因为页面打开、输入、React render 或本地链接调用 Tushare/DeepSeek/GitHub", summary)
        self.assertIn("不证明 LTG-13 production replacement complete", summary)
        self.assertNotIn("production_radar_replacement_complete: true", mode_layer)
        self.assertNotIn("onClick=", mode_layer)
        self.assertNotIn("postCandidateRadar", mode_layer)
        self.assertNotIn("launchQuantProjection", mode_layer)

    def test_candidate_radar_p1_direct_handoff_is_local_navigation_only(self):
        direct_start = self.page.index('aria-label="candidate radar p1 direct confirmation handoff"')
        direct_end = self.page.index('aria-label="candidate radar p2 three surface quick status"', direct_start)
        direct = self.page[direct_start:direct_end]

        self.assertIn('aria-label="candidate radar p1 direct confirmation handoff"', direct)
        self.assertIn("P1 直接确认入口", direct)
        self.assertIn("先确认本地 FastAPI 已接上", direct)
        self.assertIn("跳到搜票确认区输入代码", direct)
        self.assertIn("输入仍然静默", direct)
        self.assertIn("只有确认按钮会创建 Tushare-first POST task", direct)
        self.assertIn('aria-label="candidate radar p1 direct confirmation actions"', direct)
        self.assertIn('href={candidateRadarP0Blocked ? "#desktop" : "#candidate-radar-search-quant-projection"}', direct)
        self.assertIn('href="#tasks"', direct)
        self.assertNotIn("onClick=", direct)
        self.assertNotIn("postCandidateRadarQuantProjection", direct)
        self.assertNotIn("launchQuantProjection", direct)

    def test_candidate_radar_p2_three_surface_quick_status_is_read_only(self):
        summary_start = self.page.index('aria-label="candidate radar p2 three surface quick status"')
        summary_end = self.page.index('aria-label="candidate radar ordinary p0 frontend backend readiness"', summary_start)
        quick = self.page[summary_start:summary_end]

        self.assertIn("P2 三面速读", quick)
        self.assertIn("确认按钮完成后先看这里", quick)
        self.assertIn("cache、call_ledger、packet 是否进入本地回放", quick)
        self.assertIn("不创建 task、不补调 Tushare/DeepSeek", quick)
        self.assertIn('label: "三面状态"', quick)
        self.assertIn("quantProjectionSmallDataStageLabel", quick)
        self.assertIn('label: "三面组成"', quick)
        self.assertIn("quantProjectionSmallDataWritebackSurfaces", quick)
        self.assertIn('label: "完整度"', quick)
        self.assertIn("quantProjectionWritebackCheckpointLabel", quick)
        self.assertIn('label: "P2 写入证据"', quick)
        self.assertIn("quantProjectionP2ThreeSurfaceCheckpointLabel", quick)
        self.assertIn('label: "边界"', quick)
        self.assertIn("quantProjectionSmallDataReadbackContract", quick)
        self.assertIn('aria-label="candidate radar p2 first screen three surface rail"', quick)
        self.assertIn('label="candidate radar p2 first screen three surface rail"', quick)
        self.assertIn("cache、call_ledger、packet 三面状态直接在首屏显示", quick)
        self.assertIn("state={quantProjectionP2WritebackRailState}", quick)
        self.assertIn("steps={quantProjectionP2WritebackRailSteps}", quick)
        rail_start = quick.index('aria-label="candidate radar p2 first screen three surface rail"')
        actions_start = quick.index('aria-label="candidate radar p2 three surface local replay actions"')
        rail_slice = quick[rail_start:actions_start]
        self.assertNotIn("onClick=", rail_slice)
        self.assertNotIn("postCandidateRadarQuantProjection", rail_slice)
        self.assertIn('aria-label="candidate radar p2 three surface local replay actions"', quick)
        self.assertIn('href="#tasks"', quick)
        self.assertIn('href="#factor"', quick)
        self.assertIn('href="#next"', quick)
        self.assertIn("查看任务进度", quick)
        self.assertIn("查看量化推演", quick)
        self.assertIn("查看次日图谱", quick)
        self.assertIn("P2 三面入口只切换本地页面", quick)
        self.assertIn("不会创建第二个 task、不补调 Tushare/DeepSeek、不写 cache，也不改 strategy action", quick)
        self.assertNotIn("onClick=", quick)
        self.assertNotIn("postCandidateRadarQuantProjection", quick)
        self.assertNotIn("launchQuantProjection", quick)

    def test_candidate_radar_p3_first_screen_result_quick_read_is_read_only(self):
        summary_start = self.page.index('aria-label="candidate radar p3 first screen result quick read"')
        summary_end = self.page.index('aria-label="candidate radar ordinary p0 frontend backend readiness"', summary_start)
        quick = self.page[summary_start:summary_end]

        self.assertIn("P3 结果首屏速读", quick)
        self.assertIn("P2 三面之后直接看这里", quick)
        self.assertIn("可读结论、来源、下一步和安全边界", quick)
        self.assertIn("本地 cache / ledger / packet", quick)
        self.assertIn("本速读不创建 task、不调用 DeepSeek、不生成交易动作", quick)
        self.assertIn('aria-label="candidate radar p3 ordinary readable sentence"', quick)
        self.assertIn("{quantProjectionP3OrdinaryReadableSentence}", quick)
        self.assertIn('aria-label="candidate radar p3 first screen local result actions"', quick)
        self.assertIn('aria-label="open factor replay from p3 first screen result"', quick)
        self.assertIn('aria-label="open next session replay from p3 first screen result"', quick)
        self.assertIn('aria-label="return candidate pool from p3 first screen result"', quick)
        self.assertIn('href="#factor"', quick)
        self.assertIn('href="#next"', quick)
        self.assertIn('href="#candidate-pool"', quick)
        self.assertIn("P3 结果入口只切换本地页面或锚点", quick)
        self.assertIn("不会创建 task、不调用 Tushare/DeepSeek、不写 cache，也不改 strategy action", quick)
        self.assertIn("<MetricGrid items={quantProjectionP3ResultSummaryItems} />", quick)
        self.assertLess(
            quick.index('aria-label="candidate radar p3 ordinary readable sentence"'),
            quick.index('aria-label="candidate radar p3 first screen local result actions"'),
        )
        self.assertLess(
            quick.index('aria-label="candidate radar p3 first screen local result actions"'),
            quick.index('aria-label="candidate radar p3 one minute decision brief"'),
        )
        self.assertNotIn("onClick=", quick)
        self.assertNotIn("postCandidateRadarQuantProjection", quick)
        self.assertNotIn("launchQuantProjection", quick)

    def test_candidate_radar_p1_to_p3_stage_rail_is_read_only_before_tables(self):
        summary_start = self.page.index('title="普通用户雷达摘要"')
        summary_end = self.page.index('title="下一票候选池"', summary_start)
        summary = self.page[summary_start:summary_end]
        rail_start = summary.index('aria-label="candidate radar ordinary p1 to p3 stage rail"')
        p1_table_start = summary.index('aria-label="candidate radar ordinary p1 confirm path"')
        rail = summary[rail_start:p1_table_start]

        self.assertLess(rail_start, p1_table_start)
        self.assertIn("<StateClarityRail", rail)
        self.assertIn('label="candidate radar ordinary p1 to p3 stage rail"', rail)
        self.assertIn("state={ordinaryP1ToP3StageRailState}", rail)
        self.assertIn("steps={ordinaryP1ToP3StageRailSteps}", rail)
        self.assertNotIn("onClick=", rail)
        self.assertNotIn("postCandidateRadarQuantProjection", rail)
        self.assertNotIn("launchQuantProjection", rail)

    def test_candidate_radar_confirmed_chain_quick_read_is_read_only_before_p1_details(self):
        summary_start = self.page.index('title="普通用户雷达摘要"')
        summary_end = self.page.index('title="下一票候选池"', summary_start)
        summary = self.page[summary_start:summary_end]
        quick_start = summary.index('aria-label="candidate radar ordinary confirmed chain quick read"')
        p1_table_start = summary.index('aria-label="candidate radar ordinary p1 confirm path"')
        quick = summary[quick_start:p1_table_start]

        self.assertLess(quick_start, p1_table_start)
        self.assertIn("确认后链路速读", quick)
        self.assertIn("quantProjectionConfirmedChainQuickRows", quick)
        self.assertIn("<DataLineageTable", quick)
        self.assertNotIn("onClick=", quick)
        self.assertNotIn("postCandidateRadarQuantProjection", quick)
        self.assertNotIn("launchQuantProjection", quick)

    def test_three_ordinary_entrances_show_summaries_before_developer_audit(self):
        pages = {
            "daily": {
                "path": self.root / "desktop" / "src" / "routes" / "CommandCenterHome.tsx",
                "summary": 'title="今日作战台摘要"',
                "audit": "<summary>开发 / 审计详情</summary>",
                "boundary": "dailyCommandTaskBoundary",
            },
            "quant": {
                "path": self.root / "desktop" / "src" / "routes" / "FactorQuantHub.tsx",
                "summary": 'title="普通用户量化推演摘要"',
                "audit": "<summary>开发 / 审计指标</summary>",
                "boundary": "ordinaryQuantTaskBoundary",
            },
            "radar": {
                "path": self.root / "desktop" / "src" / "routes" / "CandidateRadar.tsx",
                "summary": 'title="普通用户雷达摘要"',
                "audit": "<summary>开发 / 审计指标</summary>",
                "boundary": "ordinaryTaskBoundary",
            },
        }

        for name, config in pages.items():
            with self.subTest(name=name):
                text = config["path"].read_text(encoding="utf-8")
                self.assertLess(text.index(config["summary"]), text.index(config["audit"]))
                self.assertLess(text.index('label: "任务边界"'), text.index(config["audit"]))
                self.assertIn(config["boundary"], text)
                self.assertIn("不在 React 渲染中直连 Tushare 或 DeepSeek", text)
                if name == "daily":
                    self.assertIn("dailyCommandUsableShortestPathRows", text)
                    self.assertIn("dailyCommandCandidateLatestTaskId", text)
                    self.assertIn("candidateQuantSmallDataWriteback.latest_task_id", text)
                    self.assertIn("candidateQuantReceipt.latest_task_id", text)
                    self.assertIn("candidate_radar_cache_latest_task", text)
                    self.assertIn("dailyCommandLatestTaskIsReplay = dailyCommandLatestTask.cache_replay_only === true || Boolean(dailyCommandCandidateLatestTaskId && !dailyCommandLatestTask.task_id)", text)
                    self.assertIn("dailyCommandLatestTaskId && !dailyCommandLatestTaskIsReplay ? <TaskStatusPanel taskId={dailyCommandLatestTaskId} /> : null", text)
                    self.assertIn("最近任务来自 CandidateRadar cache 只读回放，不启动 TaskStatusPanel 轮询", text)
                    self.assertIn('title="当前可用投研链路"', text)
                    self.assertIn("dailyCommandResearchWorkflowRows", text)
                    self.assertIn("当前标的、P1 确认、P2 三面、P3 结论和下一步", text)
                    self.assertIn("当前链路卡只读 CandidateRadar cache / ledger / packet；只有首页确认卡创建 P1 task；不交易", text)
                    self.assertIn('title="首页确认股票代码"', text)
                    self.assertIn('aria-label="daily command home p1 symbol confirmation"', text)
                    self.assertIn("首页输入只做本地格式校验；不会创建 task，也不会调用 Tushare/DeepSeek", text)
                    self.assertIn("candidateQuantProviderApiRows", text)
                    self.assertIn("candidateQuantSmallDataWriteback.ordinary_provider_api_rows", text)
                    self.assertIn("dailyCommandTushareDataCardSummary", text)
                    self.assertIn("dailyCommandTushareDataCardItems", text)
                    self.assertIn('aria-label="daily command p1 tushare data card"', text)
                    self.assertIn("确认后数据回放", text)
                    self.assertIn('aria-label="daily command p1 tushare data card summary"', text)
                    self.assertIn("MetricGrid items={ordinaryHomeMetricItems(dailyCommandTushareDataCardItems)}", text)
                    self.assertIn('label: "确认后数据链"', text)
                    self.assertIn('label: "接口回放"', text)
                    self.assertIn('label: "接口明细"', text)
                    self.assertIn("首页只把确认后已有的 Tushare-first 本地回放整理成数据卡", text)
                    self.assertIn("接口明细继续在下一票雷达和股票量化推演页展开", text)
                    self.assertIn("首页数据卡只读本地确认记录、数据调用记录和结果摘要；不创建第二次确认、不补调外部数据或模型、不交易", text)
                    data_card_start = text.index('aria-label="daily command p1 tushare data card"')
                    data_card_end = text.index('aria-label="daily command p1 shortest path checkpoint"', data_card_start)
                    data_card_slice = text[data_card_start:data_card_end]
                    self.assertLess(data_card_start, text.index("<summary>开发 / 审计详情</summary>"))
                    self.assertNotIn("onClick=", data_card_slice)
                    self.assertNotIn("fetch(", data_card_slice)
                    self.assertNotIn("postCandidateRadarQuantProjection", data_card_slice)
                    self.assertNotIn("launchQuantProjection", data_card_slice)
                    self.assertNotIn("TaskStatusPanel", data_card_slice)
                    self.assertLess(
                        text.index('title="当前可用投研链路"'),
                        text.index('title="今日作战台摘要"'),
                    )
                    self.assertIn('aria-label="daily command usable shortest path"', text)
                    self.assertIn("使用者可用化最短路径", text)
                    self.assertIn("当前执行目标是 Command Center 3.0 使用者可用化最短路径，不是 14 LTG strict closeout 完成声明", text)
                    self.assertIn('阶段: "P0 一键启动和本地联通"', text)
                    self.assertIn('阶段: "P1 确认按钮触发 Tushare-first"', text)
                    self.assertIn('阶段: "P2 小数据写入 cache / ledger / packet"', text)
                    self.assertIn('阶段: "P3 候选、量化推演、次日图谱"', text)
                    self.assertIn('阶段: "P4 工程审计噪音下沉"', text)
                    self.assertIn('阶段: "P5 DeepSeek governed executor 单独补"', text)
                    self.assertIn('阶段: "P6 回到 14 LTG direct evidence"', text)
                    self.assertIn("页面打开、React render 和 GET cache 只读；不启动服务、不外联、不读取 token/key", text)
                    self.assertIn("只有确认按钮创建 POST task / worker，模型解释单独补证", text)
                    self.assertIn("governed executor 完成前不真实调用 DeepSeek", text)
                    self.assertIn("strict closeout ${dailyCommandP6StrictCloseoutState}", text)
                    self.assertIn("P0-P5 可用化 checkpoint 不是 14 LTG 完成", text)
                    self.assertIn("mock、matrix、sanitizer、local receipt 不能关闭 LTG", text)
                    self.assertLess(
                        text.index('aria-label="daily command usable shortest path"'),
                        text.index(config["audit"]),
                    )
                    ordinary_readback_start = text.index('aria-label="daily command ordinary readback details"')
                    strict_closeout_start = text.index('aria-label="daily command engineering audit and strict closeout details"')
                    ordinary_readback_slice = text[ordinary_readback_start:strict_closeout_start]
                    self.assertLess(ordinary_readback_start, strict_closeout_start)
                    self.assertLess(strict_closeout_start, text.index(config["audit"]))
                    self.assertIn("P2 小数据写入速读", ordinary_readback_slice)
                    self.assertIn("P3 可解释结果速读", ordinary_readback_slice)
                    self.assertNotIn("P6 strict closeout 回归入口", ordinary_readback_slice)
                    self.assertIn("P6 strict closeout 回归入口", text[strict_closeout_start:text.index(config["audit"])])

    def test_search_quant_projection_keeps_task_boundary_visible(self):
        self.assertIn("normalizeAshareSymbolInput", self.page)
        self.assertIn("explicit_market_suffix", self.page)
        self.assertIn("inferred_market_suffix", self.page)
        self.assertIn("require_6_digits_or_suffix", self.page)
        self.assertIn("unsupported_a_share_prefix", self.page)
        self.assertIn("symbol: normalizeAshareSymbolInput(searchSymbol).normalized", self.page)
        self.assertIn("searchSymbol.trim()", self.page)
        self.assertIn("quantProjectionSymbolValidation.valid", self.page)
        self.assertIn("quantProjectionSubmitting", self.page)
        self.assertIn("quantProjectionSubmitError", self.page)
        self.assertIn("quantProjectionSubmitErrorLabel", self.page)
        self.assertIn("quantProjectionFailedSubmitLedgerRows", self.page)
        self.assertIn("quantProjectionP0SubmitRecoveryRows", self.page)
        self.assertIn("frontend_backend_auto_link_attempted", self.page)
        self.assertIn("frontend_backend_auto_link_next_action", self.page)
        self.assertIn("scripts/check_command_center_3.command", self.page)
        self.assertIn("scripts/start_command_center_3.command", self.page)
        self.assertIn("quantProjectionSubmitFailureMessage", self.page)
        self.assertIn("quantProjectionTaskReceiptInputMismatch", self.page)
        self.assertIn("quantProjectionInputSessionState", self.page)
        self.assertIn("Boolean(taskReceipt?.ok || quantProjectionPersistedTaskId)", self.page)
        self.assertIn("quantProjectionCanLaunch", self.page)
        self.assertIn("quantProjectionConfirmedSymbol", self.page)
        self.assertIn("quantProjectionSummaryGuidance", self.page)
        self.assertIn("quantProjectionValidationReasonLabel", self.page)
        self.assertIn("quantProjectionConfirmChainState", self.page)
        self.assertIn("searchQuantProjectionConfirmChainCheckpoint", self.page)
        self.assertIn("cache.search_quant_projection_confirm_chain_checkpoint", self.page)
        self.assertIn("quantProjectionConfirmChainCheckpointLabel", self.page)
        self.assertIn('label: "确认代码"', self.page)
        self.assertIn('label: "确认链路"', self.page)
        self.assertIn('label: "P1 checkpoint"', self.page)
        self.assertIn('String(searchQuantProjectionConfirmChainCheckpoint.status ?? "等待确认按钮")', self.page)
        self.assertIn("未确认；输入框不会创建任务", self.page)
        self.assertIn("已确认输入：${quantProjectionSymbolValidation.normalized}", self.page)
        self.assertIn("摘要搜票已识别 ${quantProjectionSymbolValidation.normalized}", self.page)
        self.assertIn("只由确认按钮启动本地投研流程；DeepSeek 解释留给明确授权的单独治理验收", self.page)
        self.assertIn("确认按钮在等本地联通闸门变绿，输入和页面打开不会创建后台流程", self.page)
        self.assertIn("摘要搜票格式未通过：${quantProjectionValidationReasonLabel}；不会创建后台流程", self.page)
        self.assertIn("摘要搜票等待输入代码；输入框只做本地校验，不创建后台流程", self.page)
        self.assertIn("请输入 6 位 A 股代码或 002008.SZ 这类后缀", self.page)
        self.assertIn("本地确认代码：${quantProjectionSymbolValidation.normalized}", self.page)
        self.assertIn("本地格式阻断：${quantProjectionSymbolValidation.reason}", self.page)
        self.assertIn("先输入并确认股票代码，按钮启用后再点击生成 3.0 量化推演", self.page)
        self.assertIn("确认代码后点击生成 3.0 量化推演", self.page)
        self.assertIn("quantProjectionSubmitHint", self.page)
        self.assertIn("任务提交中：正在创建 Tushare-first POST task", self.page)
        self.assertIn("正在提交 Tushare-first 后台任务；请等待本地 task id", self.page)
        self.assertIn("确认任务正在提交：按钮已暂时禁用", self.page)
        self.assertIn("const [searchSymbolTouched, setSearchSymbolTouched] = useState(false);", self.page)
        self.assertIn('import { useEffect, useRef, useState } from "react";', self.page)
        self.assertIn('const searchSymbolRef = useRef("");', self.page)
        self.assertIn("const searchSymbolTouchedRef = useRef(false);", self.page)
        self.assertIn('const updateSearchSymbolInput = (value: string, source: "manual" | "lead_candidate_prefill" = "manual") =>', self.page)
        self.assertIn('setLeadCandidatePrefillSymbol(source === "lead_candidate_prefill" ? value : "");', self.page)
        self.assertIn("const prefillSearchSymbolFromCache = (value: string) =>", self.page)
        self.assertIn("cachedQuantProjectionReceipt", self.page)
        self.assertIn("cachedQuantProjectionSymbol", self.page)
        self.assertIn("!searchSymbolTouchedRef.current", self.page)
        self.assertIn("!searchSymbolRef.current.trim()", self.page)
        self.assertIn("prefillSearchSymbolFromCache(cachedQuantProjectionSymbol);", self.page)
        self.assertIn("页面打开可从本地 cache 预填最近标的", self.page)
        self.assertIn('if (error === "missing_task_id")', self.page)
        self.assertIn("const acceptedTaskId = String(res.data?.task_id ?? res.data?.task?.task_id ?? \"\");", self.page)
        self.assertIn("if (res.ok && acceptedTaskId) {", self.page)
        self.assertIn("setTaskId(acceptedTaskId);", self.page)
        self.assertIn("const refreshQuantProjectionReadback = () =>", self.page)
        self.assertIn("refreshBootstrapStatus();", self.page)
        self.assertIn("refreshQuantProjectionReadback();", self.page)
        self.assertIn('setQuantProjectionSubmitError(quantProjectionSubmitFailureMessage("missing_task_id"));', self.page)
        self.assertIn("setTaskReceipt(null);", self.page)
        submit_start = self.page.index("const launchQuantProjection = () =>")
        submit_end = self.page.index("const launchQuantProjectionAcceptanceDryRun = () =>", submit_start)
        submit_slice = self.page[submit_start:submit_end]
        self.assertEqual(submit_slice.count('setTaskId("");'), 3)
        self.assertIn("P0 未联通：先用一键启动预检恢复 FastAPI、bootstrap status、desktop preflight、本机连接证据和 candidate cache", self.page)
        self.assertIn("P0 stability check", self.page)
        self.assertIn("p0_stability=${desktopP0StabilityReady}", self.page)
        self.assertIn("p0_local_link=${desktopP0LocalLinkReady}", self.page)
        self.assertIn("p0_connection_evidence=${desktopP0ConnectionEvidenceReady}", self.page)
        self.assertIn("stability check 或本机连接回读只作为 P1 UI 闸门证据", self.page)
        self.assertIn("本页不会从输入或渲染创建 Tushare-first task", self.page)
        self.assertIn("正在提交 Tushare-first 后台链；请等待本地 task id，页面不会重复创建第二个 task。", self.page)
        self.assertIn("当前输入与最近任务不一致：先重新点击确认创建当前代码的 task，旧回执只作为历史回放。", self.page)
        self.assertIn("当前输入已有历史 task 回放", self.page)
        self.assertIn("再次点击确认会创建新的 Tushare-first POST task，旧回放只作为参考。", self.page)
        self.assertIn("当前代码已有历史回放；再次点击确认会创建新的 Tushare-first 后台链，旧回放保留为参考。", self.page)
        self.assertIn("当前代码已在本地显示；按钮未启用时先看不可用原因，输入本身不会启动数据链。", self.page)
        self.assertIn("旧 task 属于 ${quantProjectionAcceptedTaskSymbol}", self.page)
        self.assertIn("当前输入 ${quantProjectionSymbolValidation.normalized} 需重新点击确认", self.page)
        self.assertIn("页面不会把旧回执归属到新代码", self.page)
        self.assertIn("quantProjectionTaskPanelStaleForCurrentInput", self.page)
        self.assertIn("quantProjectionTaskPanelStaleNotice", self.page)
        self.assertIn("旧任务面板暂不显示，避免把旧 task 当成当前输入的回放", self.page)
        self.assertIn("旧任务面板暂不显示，需重新点击确认", self.page)
        self.assertIn("修改输入只切换本地输入会话", self.page)
        self.assertIn("不会取消已创建后台 task、不创建新 task、不调用 Tushare/DeepSeek", self.page)
        self.assertIn("最近任务属于 ${quantProjectionAcceptedTaskSymbol}", self.page)
        self.assertIn("task_receipt_stale_for_input", self.page)
        self.assertIn("确认任务创建失败：未生成 task id；请检查本地后端连接后重试", self.page)
        self.assertIn("确认任务创建失败：${quantProjectionSubmitError}", self.page)
        self.assertIn("本地 FastAPI 后端未连接；请先用一键启动器恢复连接。", self.page)
        self.assertIn("frontend_submit_exception", self.page)
        self.assertIn("确认按钮请求未完成；请确认本地后端连接后重试。", self.page)
        self.assertIn("本地任务接口返回失败；请稍后重试或查看系统健康页。", self.page)
        self.assertIn("未创建可回放 task", self.page)
        self.assertIn('setQuantProjectionSubmitError("")', self.page)
        self.assertIn('setQuantProjectionSubmitError(quantProjectionSubmitFailureMessage("frontend_submit_exception"))', self.page)
        self.assertIn("disabled={quantProjectionSubmitDisabled}", self.page)
        self.assertIn('{quantProjectionSubmitting ? "提交中..." : "确认并生成 3.0 量化推演"}', self.page)
        self.assertIn("仅输入不会创建 task，也不会调用 Tushare 或 DeepSeek", self.page)
        self.assertIn("点击确认后提交 Tushare-first 后台链", self.page)
        self.assertIn("服务端凭据缺失时只写本地阻断", self.page)
        self.assertIn("确认任务已接收：先看 TaskStatusPanel，再通过 GET cache 回放 Tushare ledger、量化推演和次日图谱", self.page)
        self.assertIn("凭据可用才写 provider ledger；Tushare 缺失只写本地阻断，DeepSeek 不编造事实", self.page)
        self.assertIn("quantProjectionPersistedTaskId", self.page)
        self.assertIn("quantProjectionPersistedTaskStep", self.page)
        self.assertIn("quantProjectionTaskReadbackState", self.page)
        self.assertIn("quantProjectionTaskCacheReadbackRows", self.page)
        self.assertIn("confirmedTaskReceiptLabel", self.page)
        self.assertIn("quantProjectionPersistedConfirmedTaskReceiptRows", self.page)
        self.assertIn("quantProjectionConfirmedTaskReceiptRows", self.page)
        self.assertIn("quantProjectionAcceptedPayload", self.page)
        self.assertIn("ordinary_confirmed_task_receipt_rows", self.page)
        self.assertIn("ordinary_task_readback_rows", self.page)
        self.assertIn("ordinary_confirm_trigger_boundary_rows", self.page)
        self.assertIn("ordinary_confirm_outcome_rows", self.page)
        self.assertIn("quantProjectionConfirmOutcomePacketRows", self.page)
        self.assertIn("quantProjectionConfirmTriggerPacketRows", self.page)
        self.assertIn("quantProjectionConfirmTriggerBoundaryRows", self.page)
        self.assertIn("quantProjectionOrdinaryResultRows", self.page)
        self.assertIn("quantProjectionOrdinaryResultQuickReadRows", self.page)
        self.assertIn("quantProjectionOrdinaryResultQuickRows", self.page)
        self.assertIn("quantProjectionModelGovernanceRows", self.page)
        self.assertIn("quantProjectionDeepSeekGovernanceRows", self.page)
        self.assertIn("ordinary_result_readback_rows", self.page)
        self.assertIn("ordinary_result_quick_read_rows", self.page)
        self.assertIn("ordinary_model_governance_rows", self.page)
        self.assertIn('label: "确认状态"', self.page)
        self.assertIn('label: "安全边界"', self.page)
        self.assertIn("不交易、不改 strategy action；DeepSeek 只读解释可安全降级", self.page)
        self.assertIn("任务回放：${quantProjectionPersistedTaskId} /", self.page)
        self.assertIn("cache 回放", self.page)
        self.assertIn('label: "任务回放"', self.page)
        self.assertIn("quantProjectionConfirmHandoffRows", self.page)
        self.assertIn("quantProjectionOrdinaryEndToEndRows", self.page)
        self.assertIn('aria-label="quant projection ordinary end to end path"', self.page)
        self.assertIn("四步端到端路径", self.page)
        self.assertIn("先确认本地连接，再输入代码、点击确认、回放结果", self.page)
        self.assertIn('步骤: "1. 打开 3.0"', self.page)
        self.assertIn('步骤: "2. 输入代码"', self.page)
        self.assertIn('步骤: "3. 点击确认"', self.page)
        self.assertIn('步骤: "4. 回放结果"', self.page)
        self.assertIn("用一键启动器打开页面；若确认失败，先恢复本地 FastAPI 连接", self.page)
        self.assertIn("页面已进入只读 cache 状态", self.page)
        self.assertIn("FastAPI 启动、页面打开、React render、GET cache 不调用 Tushare/DeepSeek/GitHub", self.page)
        self.assertIn("只有确认按钮创建 Tushare-first POST task / worker；DeepSeek 只读解释可安全降级，不交易", self.page)
        self.assertIn("结果只从 cache / ledger / packet 回放；链接不重新创建 task、不改 strategy action", self.page)
        self.assertIn('aria-label="quant projection ordinary confirmation handoff"', self.page)
        self.assertIn("确认后链路回放：优先读取服务端 ordinary_tushare_first_chain_rows；输入只校验，点击确认才创建 Tushare-first 后台任务，结果只从本地 cache / ledger / packet 回放。", self.page)
        self.assertIn('aria-label="quant projection ordinary confirm trigger boundary"', self.page)
        self.assertIn("P1 触发边界", self.page)
        self.assertIn("优先读取服务端 ordinary_confirm_trigger_boundary_rows", self.page)
        self.assertIn("输入只校验，确认按钮才创建 Tushare-first POST task，GET cache 和 React render 只回放本地结果", self.page)
        self.assertIn('触发点: "1. 输入股票代码"', self.page)
        self.assertIn('触发点: "2. 确认按钮"', self.page)
        self.assertIn('触发点: "3. Tushare-first task ledger"', self.page)
        self.assertIn('触发点: "4. GET cache 回放"', self.page)
        self.assertIn("输入框只做本地校验；不创建 task、不调用 Tushare/DeepSeek/GitHub", self.page)
        self.assertIn("POST /api/candidate-radar/quant-projection", self.page)
        self.assertIn("Tushare 只允许在按钮门控 POST task / worker 内调用", self.page)
        self.assertIn("GET cache、React render、结果链接只回放本地结果；不创建第二个 task", self.page)
        self.assertIn('aria-label="quant projection confirmed task receipt readback"', self.page)
        self.assertIn("确认任务接收回执", self.page)
        self.assertIn("点击确认后先看这张回执：它只回放本地 POST task 是否接收、Tushare-first / DeepSeek 只读解释参数和安全步骤；回放本身不补调数据源或模型。", self.page)
        self.assertIn('回执项: "task_id"', self.page)
        self.assertIn('回执项: "Tushare-first 链路"', self.page)
        self.assertIn('回执项: "安全步骤"', self.page)
        self.assertIn('回执项: "结果去向"', self.page)
        self.assertIn("include_tushare=${String(quantProjectionAcceptedPayload.include_tushare ?? true)}", self.page)
        self.assertIn("include_deepseek=${String(quantProjectionAcceptedPayload.include_deepseek ?? false)}", self.page)
        self.assertIn("回执项: confirmedTaskReceiptLabel(row.receipt_item)", self.page)
        self.assertIn("GET cache 只读回放；不创建任务、不补调数据源或模型", self.page)
        self.assertIn("task id 来自按钮门控 POST 或 cache packet 回放；GET cache 不创建任务", self.page)
        self.assertIn("只有 POST task / worker 可调用 Tushare；React render、搜索输入、GET cache 不外联", self.page)
        self.assertIn("DeepSeek 只读解释可安全降级；不真实交易、不改 strategy action", self.page)
        self.assertIn("quantProjectionPostConfirmActionRows", self.page)
        self.assertIn("quantProjectionOrdinaryConfirmOutcomeRows", self.page)
        self.assertIn("quantProjectionConfirmReplayStage", self.page)
        self.assertIn("quantProjectionConfirmReplayStageRows", self.page)
        self.assertIn("searchQuantProjectionSmallDataWriteback.ordinary_confirm_replay_stage_rows", self.page)
        self.assertIn("quantProjectionConfirmReplayStageRows.length ? quantProjectionConfirmReplayStageRows", self.page)
        self.assertIn('label: "P1/P2 当前阶段"', self.page)
        self.assertIn("P1 ready：点击确认后创建 Tushare-first POST task", self.page)
        self.assertIn("P1 accepted：任务已接收；等待 TaskStatusPanel success 后刷新 cache", self.page)
        self.assertIn("P2 ready：cache / ledger / packet 已进入本地回放", self.page)
        self.assertIn("P1 blocked：确认任务未创建；先恢复本地 FastAPI 连接", self.page)
        self.assertIn('aria-label="quant projection ordinary confirm outcome quick read"', self.page)
        self.assertIn("P1 确认结果速读", self.page)
        self.assertIn("优先读取服务端 ordinary_confirm_outcome_rows：点击确认后先看任务是否接收、P2 三面是否回放、P3 入口是否可读；这张速读表不创建第二个任务。", self.page)
        self.assertIn('速读项: "P1/P2 当前阶段"', self.page)
        self.assertIn('速读项: displayText(row["速读项"] ?? row.stage_key)', self.page)
        self.assertIn("阶段只由本地 task receipt / cache 推导；不创建 task、不补调 provider/model", self.page)
        self.assertIn("GET cache 只读回放；不创建 task、不补调 provider/model", self.page)
        self.assertIn('速读项: "确认任务"', self.page)
        self.assertIn('速读项: "任务编号"', self.page)
        self.assertIn('速读项: "结果回放"', self.page)
        self.assertIn("只解释确认按钮是否创建本地 POST task；不会从摘要补调 provider/model", self.page)
        self.assertIn("TaskStatusPanel 只轮询本地 FastAPI，完成后刷新 cache", self.page)
        self.assertIn("结果只从 cache / ledger / packet 回放；不交易、不改 strategy action", self.page)
        self.assertIn("quantProjectionPostConfirmPacketRows", self.page)
        self.assertIn("searchQuantProjectionSmallDataWriteback.ordinary_post_confirm_action_rows", self.page)
        self.assertIn("quantProjectionPostConfirmPacketRows.length ? quantProjectionPostConfirmPacketRows", self.page)
        self.assertIn("quantProjectionTaskSuccessRefreshRows", self.page)
        self.assertIn("quantProjectionPostConfirmOneScreenItems", self.page)
        self.assertIn("searchQuantProjectionP1ShortestPathCheckpoint", self.page)
        self.assertIn("ordinary_p1_shortest_path_checkpoint", self.page)
        self.assertIn('aria-label="candidate radar post confirm one screen outcome"', self.page)
        self.assertIn("确认后一屏结果", self.page)
        self.assertIn("任务是否接收、P2 三面是否回放、P3 结论是否可读和下一步入口都在一屏内", self.page)
        self.assertIn("这条结果条只读本地 task receipt 与 cache / ledger / packet，不创建第二个 task", self.page)
        self.assertIn('label: "任务接收"', self.page)
        self.assertIn('label: "P1 最短链路"', self.page)
        self.assertIn("displayText(searchQuantProjectionP1ShortestPathCheckpoint.ordinary_label, quantProjectionTushareFirstState)", self.page)
        self.assertIn('label: "当前阶段"', self.page)
        self.assertIn('label: "P2 三面"', self.page)
        self.assertIn('label: "P3 结论"', self.page)
        self.assertIn('label: "下一步入口"', self.page)
        self.assertIn('label: "只读边界"', self.page)
        self.assertIn("操作台确认后结果条只读本地确认记录、本地缓存、数据记录和结果包", self.page)
        self.assertIn("quantProjectionFirstScreenTaskContractItems", self.page)
        self.assertIn('aria-label="candidate radar first screen p1 task contract quick read"', self.page)
        self.assertIn("确认后会发生什么", self.page)
        self.assertIn("普通用户不用展开技术明细也能看到", self.page)
        self.assertIn('aria-label="candidate radar ordinary tushare first readiness strip"', self.page)
        self.assertIn("Tushare-first 当前进度", self.page)
        self.assertIn("这条进度条把“能不能点确认、任务是否接收、Tushare 账本是否回放、下一步看哪里”合成四格", self.page)
        self.assertIn("quantProjectionTushareFirstOrdinaryReadinessItems", self.page)
        self.assertIn('label: "当前进度"', self.page)
        self.assertIn('label: "下一步"', self.page)
        self.assertIn('label: "回放依据"', self.page)
        self.assertIn("只有确认按钮创建本地 POST task；DeepSeek 只读解释可安全降级；不交易", self.page)
        self.assertIn('label: "POST 路由"', self.page)
        self.assertIn('value: "POST /api/candidate-radar/quant-projection"', self.page)
        self.assertIn('label: "task_type"', self.page)
        self.assertIn('value: "run_candidate_radar_quant_projection"', self.page)
        self.assertIn('label: "触发方式"', self.page)
        self.assertIn("只在确认按钮点击后创建；输入、页面打开、React render 和 GET cache 静默", self.page)
        self.assertIn('label: "写回三面"', self.page)
        self.assertIn('value: "cache / call_ledger / packet"', self.page)
        self.assertIn('label: "交易边界"', self.page)
        self.assertIn("不真实交易、不下单、不改 strategy action", self.page)
        first_screen_start = self.page.index('aria-label="candidate radar first screen quant projection confirmation"')
        first_screen_recovery_index = self.page.index('aria-label="candidate radar first screen p0 submit failure recovery"', first_screen_start)
        first_screen_contract_index = self.page.index('aria-label="candidate radar first screen p1 task contract quick read"', first_screen_start)
        tushare_first_readiness_index = self.page.index('aria-label="candidate radar ordinary tushare first readiness strip"', first_screen_start)
        one_screen_result_index = self.page.index('aria-label="candidate radar post confirm one screen outcome"', first_screen_start)
        p1_chain_details_index = self.page.index('aria-label="candidate radar first screen p1 chain details"', first_screen_start)
        post_confirm_guide_index = self.page.index('aria-label="candidate radar first screen post confirm readback guide"', first_screen_start)
        p1_details_index = self.page.index('aria-label="candidate radar ordinary p1 p2 detail readback"', first_screen_start)
        self.assertIn("<summary>查看确认后清单</summary>", self.page)
        self.assertIn("按钮路由、回放清单和链路排障默认收起", self.page)
        self.assertLess(first_screen_recovery_index, first_screen_contract_index)
        self.assertLess(first_screen_contract_index, tushare_first_readiness_index)
        self.assertLess(tushare_first_readiness_index, one_screen_result_index)
        self.assertLess(first_screen_contract_index, p1_chain_details_index)
        self.assertLess(one_screen_result_index, post_confirm_guide_index)
        self.assertLess(one_screen_result_index, p1_chain_details_index)
        self.assertLess(p1_chain_details_index, post_confirm_guide_index)
        self.assertLess(one_screen_result_index, p1_details_index)
        first_screen_recovery_slice = self.page[first_screen_recovery_index:first_screen_contract_index]
        self.assertIn("确认按钮失败后就在这里看本地联通恢复包", first_screen_recovery_slice)
        self.assertIn("DataLineageTable rows={quantProjectionP0SubmitRecoveryRows}", first_screen_recovery_slice)
        self.assertIn("不自动重试、不创建 task", first_screen_recovery_slice)
        self.assertNotIn("postCandidateRadarQuantProjection", first_screen_recovery_slice)
        self.assertNotIn("onClick=", first_screen_recovery_slice)
        first_screen_contract_slice = self.page[first_screen_contract_index:one_screen_result_index]
        self.assertIn("MetricGrid items={quantProjectionFirstScreenTaskContractItems}", first_screen_contract_slice)
        self.assertNotIn("postCandidateRadarQuantProjection", first_screen_contract_slice)
        self.assertNotIn("postTask(", first_screen_contract_slice)
        self.assertNotIn("onClick=", first_screen_contract_slice)
        one_screen_result_slice = self.page[one_screen_result_index:post_confirm_guide_index]
        backend_one_glance_index = self.page.index(
            'aria-label="candidate radar backend post confirm one glance"',
            one_screen_result_index,
        )
        ordinary_one_screen_intro_slice = self.page[one_screen_result_index:backend_one_glance_index]
        backend_one_glance_end = self.page.index(
            "MetricGrid items={quantProjectionPostConfirmOneScreenItems}",
            backend_one_glance_index,
        )
        backend_one_glance_slice = self.page[backend_one_glance_index:backend_one_glance_end]
        self.assertIn("MetricGrid items={quantProjectionPostConfirmOneScreenItems}", one_screen_result_slice)
        one_screen_items_start = self.page.index("const quantProjectionPostConfirmOneScreenItems")
        one_screen_items_end = self.page.index("const searchQuantResultCurrentSymbol", one_screen_items_start)
        one_screen_items_definition = self.page[one_screen_items_start:one_screen_items_end]
        self.assertIn('label: "结果状态"', one_screen_items_definition)
        self.assertIn("searchQuantResultVersionSummary.ordinary_summary", one_screen_items_definition)
        self.assertIn('label: "结果下一步"', one_screen_items_definition)
        self.assertIn("searchQuantResultVersionSummary.ordinary_next_step", one_screen_items_definition)
        self.assertIn("degraded_result_visible", one_screen_items_definition)
        self.assertNotIn("search_quant_projection_post_confirm_one_glance_items", ordinary_one_screen_intro_slice)
        self.assertIn('aria-label="candidate radar same task result version card"', one_screen_result_slice)
        self.assertIn("同次结果版本", one_screen_result_slice)
        self.assertIn("ordinaryUserText(searchQuantSameTaskResultVersionLabel)", one_screen_result_slice)
        self.assertIn("MetricGrid items={quantProjectionSameTaskResultVersionItems}", one_screen_result_slice)
        self.assertIn("同一 task、同一事实包、同一结果版本才提升 current", one_screen_result_slice)
        self.assertIn("DeepSeek 只作为解释层，失败时不覆盖事实包", one_screen_result_slice)
        self.assertIn("const quantProjectionSameTaskResultVersionItems", self.page)
        self.assertIn("searchQuantSameTaskResultVersionLabel", self.page)
        self.assertIn('label: "task / symbol / version"', self.page)
        self.assertIn('label: "scope / facts / freshness"', self.page)
        self.assertIn('label: "provider ledger"', self.page)
        self.assertIn('label: "DeepSeek overlay"', self.page)
        self.assertIn('label: "last-good / degraded"', self.page)
        self.assertIn(
            '<details className="developer-audit-details" aria-label="candidate radar backend post confirm one glance">',
            one_screen_result_slice,
        )
        self.assertIn("<summary>查看同源回放</summary>", one_screen_result_slice)
        self.assertIn("search_quant_projection_post_confirm_one_glance_items", backend_one_glance_slice)
        self.assertIn("MetricGrid items={quantProjectionBackendPostConfirmOneGlanceItems}", backend_one_glance_slice)
        self.assertIn("MetricGrid items={quantProjectionResultLineageItems}", one_screen_result_slice)
        result_lineage_helpers_start = self.page.index("const searchQuantResultCurrentSymbol")
        result_lineage_definition_start = self.page.index("const quantProjectionResultLineageItems")
        result_lineage_definition_end = self.page.index(
            "const candidateRadarOperatorPostConfirmOneGlanceItems",
            result_lineage_definition_start,
        )
        result_lineage_helpers = self.page[result_lineage_helpers_start:result_lineage_definition_start]
        result_lineage_definition = self.page[result_lineage_definition_start:result_lineage_definition_end]
        self.assertIn("searchQuantCurrentResultLabel", result_lineage_definition)
        self.assertIn("searchQuantLatestTaskResultLabel", result_lineage_definition)
        self.assertIn("searchQuantLastGoodResultLabel", result_lineage_definition)
        self.assertIn("searchQuantDegradedResultLabel", result_lineage_definition)
        self.assertIn("degraded_result_symbol", result_lineage_helpers)
        self.assertIn("degraded_result_version", result_lineage_helpers)
        self.assertIn("last_good_result_symbol", result_lineage_helpers)
        self.assertIn("last_good_result_version", result_lineage_helpers)
        self.assertIn("不覆盖 current", result_lineage_helpers)
        self.assertIn('label: "同源标的"', result_lineage_definition)
        self.assertIn("searchQuantResultSymbolLabel", result_lineage_definition)
        self.assertIn('label: "确认范围"', result_lineage_definition)
        self.assertIn("searchQuantResultScopeLabel", result_lineage_definition)
        self.assertIn('label: "输入包"', result_lineage_definition)
        self.assertIn("searchQuantResultInputPacketKeys", result_lineage_definition)
        self.assertIn("quantProjectionPostConfirmReplayContract", self.page)
        self.assertIn("ordinary_post_confirm_replay_contract", self.page)
        self.assertIn("quantProjectionReceiptRequestParams", self.page)
        self.assertIn("quantProjectionPostConfirmReplayContractRows", self.page)
        self.assertIn(
            '<details className="developer-audit-details" aria-label="candidate radar post confirm backend replay contract">',
            one_screen_result_slice,
        )
        self.assertIn("<summary>查看回放顺序</summary>", one_screen_result_slice)
        self.assertIn("查看回放顺序", one_screen_result_slice)
        self.assertIn("这里展示确认后的回放顺序", one_screen_result_slice)
        self.assertIn("先看任务编号和状态，再看本地 cache、三面回放、量化推演和次日图谱", one_screen_result_slice)
        self.assertIn("DataLineageTable rows={quantProjectionPostConfirmReplayContractRows}", one_screen_result_slice)
        self.assertIn('合同项: "任务回执"', self.page)
        self.assertIn('合同项: "回放顺序"', self.page)
        self.assertIn('合同项: "P2 三面"', self.page)
        self.assertIn('合同项: "结果入口"', self.page)
        self.assertIn("合同只描述确认后的只读回放；不会从本表创建第二个 task", self.page)
        self.assertIn("GET cache / bootstrap status 只读；React render 不补调 provider/model", self.page)
        self.assertIn('aria-label="candidate radar post confirm local replay actions"', one_screen_result_slice)
        self.assertIn("onClick={refreshQuantProjectionReadback}", one_screen_result_slice)
        self.assertIn("disabled={loading}", one_screen_result_slice)
        self.assertIn("刷新本地回放", one_screen_result_slice)
        self.assertIn('href="#tasks"', one_screen_result_slice)
        self.assertIn('href="#factor/factor-score"', one_screen_result_slice)
        self.assertIn('href="#next/next-session-chart"', one_screen_result_slice)
        self.assertIn("只调用 GET cache / bootstrap status", one_screen_result_slice)
        self.assertIn("不会创建第二个 task、不补调 Tushare/DeepSeek、不写交易动作", one_screen_result_slice)
        self.assertNotIn("postCandidateRadarQuantProjection", one_screen_result_slice)
        self.assertNotIn("postCandidateRadarQuantProjectionProviderModelAcceptance", one_screen_result_slice)
        self.assertNotIn("launchQuantProjectionAcceptanceDryRun", one_screen_result_slice)
        self.assertNotIn("postTask(", one_screen_result_slice)
        self.assertIn('aria-label="quant projection post confirm user actions"', self.page)
        self.assertIn("确认后看什么", self.page)
        self.assertIn("点击确认后先看任务编号和 TaskStatusPanel，再刷新本地 cache，最后回放量化推演和次日图谱", self.page)
        self.assertIn('行动: "1. 看任务编号"', self.page)
        self.assertIn('行动: "2. 看任务进度"', self.page)
        self.assertIn('行动: "3. 刷新本地 cache"', self.page)
        self.assertIn('行动: "4. 回放结果"', self.page)
        self.assertIn("TaskStatusPanel 可轮询本地 FastAPI", self.page)
        self.assertIn("等待 success 后刷新本地 cache", self.page)
        self.assertIn("GET cache 只读回放，不补调 provider/model、不泄露敏感凭据", self.page)
        self.assertIn("只切换 #factor/#next 锚点，不重新创建 task、不改 strategy action", self.page)
        self.assertIn('aria-label="quant projection task success refresh checklist"', self.page)
        self.assertIn("任务成功后自动回读", self.page)
        self.assertIn("TaskStatusPanel success 后调用 refreshQuantProjectionReadback：只回读 CandidateRadar cache 和 bootstrap status", self.page)
        self.assertIn("再让用户看 P2 三面与 P3 结果入口；不会创建第二个 task", self.page)
        self.assertIn("DataLineageTable rows={quantProjectionTaskSuccessRefreshRows}", self.page)
        self.assertIn('回读项: "1. TaskStatusPanel success"', self.page)
        self.assertIn('回读项: "2. cache / ledger / packet"', self.page)
        self.assertIn('回读项: "3. 结果入口"', self.page)
        self.assertIn("调用 refreshQuantProjectionReadback，回读 CandidateRadar cache 和 bootstrap status", self.page)
        self.assertIn("refreshCache() 只读取 GET /api/candidate-radar/cache", self.page)
        self.assertIn("TaskStatusPanel 只轮询本地 FastAPI；success 回调不创建第二个 task、不补调 Tushare/DeepSeek", self.page)
        self.assertIn("GET cache 只读；不展示 raw log、敏感凭据或 provider error", self.page)
        self.assertIn('步骤: "输入校验"', self.page)
        self.assertIn('步骤: "点击确认"', self.page)
        self.assertIn('步骤: "Tushare 写入"', self.page)
        self.assertIn('步骤: "结果回放"', self.page)
        self.assertIn("搜索输入、React render、GET cache 不外联", self.page)
        self.assertIn("只有用户确认后才进入后台链", self.page)
        self.assertIn("Tushare 缺失只写本地阻断，DeepSeek 不编造事实", self.page)
        self.assertIn("不交易、不改 strategy action", self.page)
        self.assertIn("quantProjectionSmallDataWritebackStatus", self.page)
        self.assertIn("quantProjectionSmallDataWritebackRows", self.page)
        self.assertIn("quantProjectionSmallDataTargetRows", self.page)
        self.assertIn("quantProjectionSmallDataActionRows", self.page)
        self.assertIn("quantProjectionWritebackSurfaceSummaryRows", self.page)
        self.assertIn("quantProjectionWritebackSurfaceRows", self.page)
        self.assertIn("quantProjectionWritebackRecoveryRows", self.page)
        self.assertIn("quantProjectionWritebackRecoveryDisplayRows", self.page)
        self.assertIn("quantProjectionP2WritebackRailState", self.page)
        self.assertIn("quantProjectionP2WritebackRailSteps", self.page)
        self.assertIn("searchQuantProjectionP2ThreeSurfaceCheckpoint", self.page)
        self.assertIn("ordinary_p2_three_surface_checkpoint", self.page)
        self.assertIn("const quantProjectionP2ThreeSurfaceCheckpointLabel", self.page)
        self.assertIn("const quantProjectionSmallDataExplicitReady", self.page)
        self.assertIn("const quantProjectionSmallDataPartialLedgerReady", self.page)
        self.assertIn("const quantProjectionSmallDataReady = quantProjectionSmallDataExplicitReady", self.page)
        self.assertIn("cache / packet 仍等待小数据三面 ready", self.page)
        self.assertIn("部分恢复：call_ledger 已回放，cache / packet 仍等待小数据三面 ready。", self.page)
        self.assertNotIn(
            "small_data_writeback_ready === true || quantProjectionProviderLedgerReady",
            self.page,
        )
        self.assertIn("ordinary_writeback_target_rows", self.page)
        self.assertIn("ordinary_writeback_action_rows", self.page)
        self.assertIn("ordinary_writeback_surface_summary_rows", self.page)
        self.assertIn("ordinary_writeback_recovery_rows", self.page)
        self.assertLess(
            self.page.index("quantProjectionSmallDataTargetRows.length"),
            self.page.index("quantProjectionSmallDataOrdinaryReadbackRows.length"),
        )
        self.assertIn('aria-label="quant projection ordinary small data writeback targets"', self.page)
        self.assertIn('aria-label="quant projection ordinary writeback surface summary"', self.page)
        self.assertIn('aria-label="quant projection ordinary small data writeback actions"', self.page)
        self.assertIn('aria-label="candidate radar ordinary p2 writeback rail"', self.page)
        self.assertIn('label="candidate radar ordinary p2 writeback rail"', self.page)
        self.assertIn("P2 三面状态轨", self.page)
        self.assertIn("先扫 cache、call_ledger、packet 三面是否可读", self.page)
        self.assertIn("这条状态轨只读本地回放，不展示接口级 raw log", self.page)
        self.assertIn('label: "cache"', self.page)
        self.assertIn('label: "call_ledger"', self.page)
        self.assertIn('label: "packet"', self.page)
        self.assertIn('label: "只读边界"', self.page)
        p2_rail_start = self.page.index('aria-label="candidate radar ordinary p2 writeback rail"')
        p2_surface_start = self.page.index('aria-label="candidate radar ordinary p2 writeback surfaces"')
        p2_rail_slice = self.page[p2_rail_start:p2_surface_start]
        self.assertIn("<StateClarityRail", p2_rail_slice)
        self.assertNotIn("onClick=", p2_rail_slice)
        self.assertNotIn("postCandidateRadarQuantProjection", p2_rail_slice)
        self.assertIn("小数据写入位置", self.page)
        self.assertIn("P2 写入面速读", self.page)
        self.assertIn("优先读取服务端 ordinary_writeback_surface_summary_rows", self.page)
        self.assertIn("普通入口只看 cache、call_ledger、packet 三个写入面是否可回放", self.page)
        self.assertIn("GET cache 不创建 task", self.page)
        self.assertIn('aria-label="candidate radar ordinary p2 writeback recovery"', self.page)
        self.assertIn("P2 阻断恢复速读", self.page)
        self.assertIn("区分任务等待、服务端凭据阻断和 DeepSeek 安全降级", self.page)
        self.assertIn("它只读本地 cache，不创建任务", self.page)
        self.assertIn("确认按钮是唯一可创建 Tushare-first 后台链路的普通入口。", self.page)
        self.assertIn("DeepSeek 解释只读回放或安全降级；P2 阻断恢复不等待模型。", self.page)
        self.assertIn("不会创建 task、不调用 provider/model", self.page)
        self.assertIn("小数据行动清单", self.page)
        self.assertIn("优先读取服务端 ordinary_writeback_action_rows", self.page)
        self.assertIn("看任务、看 ledger、刷新 cache、回放结果", self.page)
        self.assertIn("不会从回放行创建 task", self.page)
        self.assertIn("小数据写入位置可回放：cache、call_ledger、packet 已有本地读回；普通入口只显示位置和状态。", self.page)
        self.assertIn("小数据写入等待后台完成：先看任务状态，成功后刷新本地 cache 回放 cache、call_ledger、packet。", self.page)
        self.assertIn("小数据写入等待确认按钮：输入或搜索不会写 cache、call_ledger、packet。", self.page)
        self.assertIn('写入位置: "cache"', self.page)
        self.assertIn('写入位置: "call_ledger"', self.page)
        self.assertIn('写入位置: "packet"', self.page)
        self.assertIn("接口级明细下沉到高级状态", self.page)
        self.assertIn("普通页面不展示敏感凭据、raw log 或 provider error", self.page)
        self.assertIn("packet 不包含凭据、不生成交易动作、不覆盖 strategy action", self.page)
        self.assertIn(
            '<details className="developer-audit-details" aria-label="quant projection task cache packet readback">',
            self.page,
        )
        self.assertIn("<summary>任务 / cache packet 回放详情</summary>", self.page)
        self.assertIn("任务回放清单", self.page)
        self.assertIn(
            "普通入口只保留任务状态轨和结果速读；task id、safe current_step、cache packet 明细默认收起。",
            self.page,
        )
        self.assertIn("任务编号和安全步骤优先从本地 cache / packet 回放", self.page)
        self.assertIn("TaskStatusPanel 只轮询本地 FastAPI 任务状态", self.page)
        self.assertIn('回放项: "task_id"', self.page)
        self.assertIn('回放项: "current_step"', self.page)
        self.assertIn('回放项: "TaskStatusPanel"', self.page)
        self.assertIn("GET cache 只读回放 task id，不创建 task、不补调 provider/model", self.page)
        self.assertIn("只展示 safe current_step；不展示 raw log、敏感凭据或 provider error", self.page)
        self.assertIn("轮询本地任务状态，不调用 Tushare/DeepSeek/GitHub、不写交易动作", self.page)
        self.assertIn('aria-label="quant projection ordinary explainable result readback"', self.page)
        self.assertIn('id="factor" aria-label="quant projection factor replay anchor"', self.page)
        self.assertIn('id="next" aria-label="quant projection ordinary explainable result readback"', self.page)
        self.assertIn("quantProjectionReadbackIndexRows", self.page)
        self.assertIn('aria-label="quant projection ordinary readback index"', self.page)
        self.assertIn('aria-label="quant projection ordinary explainable result quick read"', self.page)
        self.assertIn('aria-label="quant projection ordinary deepseek governance status"', self.page)
        self.assertIn("解释结果清单", self.page)
        self.assertIn("P2/P3 回放清单", self.page)
        self.assertIn("读取本地 packet 回放索引", self.page)
        self.assertIn("确认回执、任务回放、数据接口和 P3 结果速读都只做本地回放", self.page)
        self.assertIn('回放清单: "确认回执"', self.page)
        self.assertIn('回放清单: "任务回放"', self.page)
        self.assertIn('回放清单: "数据接口回放"', self.page)
        self.assertIn('回放清单: "P3 结果速读"', self.page)
        self.assertIn("可回放项: Number(counts.search_quant_projection_confirmed_task_receipt_row_count", self.page)
        self.assertIn('只读边界: policy.search_quant_projection_confirmed_task_receipt_rows_are_cache_only === false ? "待复核" : "只读回放"', self.page)
        self.assertIn("counts.search_quant_projection_confirmed_task_receipt_row_count", self.page)
        self.assertIn("counts.search_quant_projection_task_readback_row_count", self.page)
        self.assertIn("counts.search_quant_projection_provider_api_row_count", self.page)
        self.assertIn("policy.search_quant_projection_confirmed_task_receipt_rows_are_cache_only", self.page)
        self.assertIn("policy.search_quant_projection_task_readback_rows_are_cache_only", self.page)
        self.assertIn("policy.search_quant_projection_provider_api_rows_are_cache_only", self.page)
        self.assertIn("数据接口行只读回放 ledger 状态；React render 不调用 provider/model", self.page)
        self.assertIn("结果速读不创建 task、不调用模型、不生成交易动作", self.page)
        result_readback_start = self.page.index('aria-label="quant projection ordinary explainable result readback"')
        result_quick_start = self.page.index('aria-label="quant projection ordinary explainable result quick read"', result_readback_start)
        result_checkpoint_start = self.page.index('aria-label="quant projection ordinary result checkpoint"', result_quick_start)
        result_handoff_start = self.page.index('aria-label="quant projection ordinary result handoff index"', result_checkpoint_start)
        ordinary_readback_slice = self.page[result_readback_start:result_quick_start]
        self.assertNotIn("直接读取 packet 顶层 counts / policy", ordinary_readback_slice)
        self.assertNotIn('索引: "Provider API"', ordinary_readback_slice)
        self.assertNotIn('只读策略:', ordinary_readback_slice)
        self.assertLess(result_quick_start, result_checkpoint_start)
        self.assertLess(result_checkpoint_start, result_handoff_start)
        self.assertIn("function readableSentencePart", self.page)
        self.assertIn("quantProjectionP3OrdinaryReadableSentence", self.page)
        self.assertIn("searchQuantProjectionP3ExplainableResultCheckpoint", self.page)
        self.assertIn("ordinary_p3_explainable_result_checkpoint", self.page)
        self.assertIn("search_quant_projection_p3_explainable_result_checkpoint", self.page)
        self.assertIn("const quantProjectionP3ExplainableResultCheckpointLabel", self.page)
        self.assertIn('readableSentencePart("结论", quantProjectionOrdinaryResultSummary, ["结论：", "可读结论："])', self.page)
        self.assertIn('readableSentencePart("下一步", quantProjectionOrdinaryResultNext, ["下一步："])', self.page)
        self.assertIn('readableSentencePart("证据", quantProjectionOrdinaryResultEvidence, ["证据："])', self.page)
        self.assertIn('readableSentencePart("边界", quantProjectionOrdinaryResultBoundary, ["边界："])', self.page)
        self.assertNotIn("证据：${quantProjectionOrdinaryResultEvidence}", self.page)
        self.assertNotIn("结论：${quantProjectionOrdinaryResultSummary}", self.page)
        self.assertIn('aria-label="quant projection ordinary p3 readable sentence"', self.page)
        self.assertLess(
            self.page.index('aria-label="quant projection ordinary p3 readable sentence"', result_quick_start),
            result_checkpoint_start,
        )
        self.assertIn("P3 结果速读", self.page)
        self.assertIn("优先读取服务端 ordinary_result_quick_read_rows", self.page)
        self.assertIn('aria-label="candidate radar ordinary p3 result checkpoint"', self.page)
        self.assertIn('aria-label="quant projection ordinary result checkpoint"', self.page)
        self.assertIn("P3 结果检查点", self.page)
        self.assertIn("ordinary_result_checkpoint_rows", self.page)
        self.assertIn("rows={quantProjectionOrdinaryResultCheckpointRows}", self.page)
        self.assertIn("确认可读结论、来源、缺口和安全字段", self.page)
        self.assertIn("这张检查点表只读本地 cache，不创建 task、不调用模型", self.page)
        self.assertIn("quantProjectionOrdinaryResultHandoffRows", self.page)
        self.assertIn("ordinary_result_handoff_rows", self.page)
        self.assertIn('aria-label="quant projection ordinary result handoff index"', self.page)
        self.assertIn("P3 结果入口索引", self.page)
        self.assertIn("优先读取服务端 ordinary_result_handoff_rows", self.page)
        self.assertIn("把可读结论、量化推演、次日图谱和候选池绑定到同一个本地来源任务", self.page)
        self.assertIn("链接只切换入口，不创建 task", self.page)
        self.assertIn('来源任务: displayText(row["来源任务"] ?? row.source_task_id, "waiting_confirm_task")', self.page)
        self.assertIn("先看可读结论、来源组成、回放来源和待补证据", self.page)
        self.assertIn("不会从结果速读创建 task 或调用模型", self.page)
        self.assertIn("高级：DeepSeek 解释治理", self.page)
        self.assertIn("按钮门控模型解释何时可回放或安全降级", self.page)
        self.assertIn("不作为数据源，不阻塞 P1/P2/P3 本地回放", self.page)
        self.assertIn("优先读取 ordinary_model_governance_rows", self.page)
        self.assertIn("不会从治理状态创建 task 或调用模型", self.page)
        self.assertIn("quantProjectionDeepSeekChecklistRows", self.page)
        self.assertIn("quantProjectionDeepSeekReadinessRows", self.page)
        self.assertIn("quantProjectionDeepSeekContractRows", self.page)
        self.assertIn("ordinary_deepseek_governed_executor_checklist_rows", self.page)
        self.assertIn("ordinary_deepseek_governed_executor_readiness_rows", self.page)
        self.assertIn("ordinary_deepseek_governed_executor_contract_rows", self.page)
        self.assertIn('aria-label="candidate radar audit p5 governed executor contract"', self.page)
        self.assertIn('aria-label="quant projection ordinary deepseek governed executor contract"', self.page)
        self.assertIn("DeepSeek 解释治理合同", self.page)
        self.assertIn("DeepSeek 解释必须有 model_ledger、sanitizer、output acceptance 和安全摘要字段", self.page)
        self.assertIn("确认按钮后的解释必须有 model_ledger、sanitizer、output acceptance、安全字段和不阻塞 P1/P2/P3", self.page)
        self.assertIn('aria-label="quant projection ordinary deepseek governed executor checklist"', self.page)
        self.assertIn('aria-label="quant projection ordinary deepseek governed executor readiness"', self.page)
        self.assertIn("P5 governed executor readiness", self.page)
        self.assertIn("说明何时允许 DeepSeek 解释、当前是否安全降级、以及只能写安全摘要", self.page)
        self.assertIn("这张表只读回放，不创建 task、不调用模型", self.page)
        self.assertIn("P5 governed executor 补证清单", self.page)
        self.assertIn("model_ledger、sanitizer/redaction、output acceptance、安全回退和不覆盖 action 都必须先满足", self.page)
        self.assertIn("这张清单不创建 task、不调用模型", self.page)
        deepseek_details_start = self.page.index('aria-label="quant projection ordinary deepseek governance status"')
        deepseek_contract_index = self.page.index('aria-label="quant projection ordinary deepseek governed executor contract"', deepseek_details_start)
        deepseek_readiness_index = self.page.index('aria-label="quant projection ordinary deepseek governed executor readiness"', deepseek_details_start)
        deepseek_checklist_index = self.page.index('aria-label="quant projection ordinary deepseek governed executor checklist"', deepseek_details_start)
        self.assertLess(deepseek_contract_index, deepseek_readiness_index)
        self.assertLess(deepseek_readiness_index, deepseek_checklist_index)
        self.assertIn('检查项: displayText(row["检查项"] ?? row.check_key)', self.page)
        self.assertIn("普通入口只回放数据来源、量化推演、次日图谱和安全边界", self.page)
        self.assertIn("原始 receipt、prompt 或审计字段仍下沉在详情中", self.page)
        self.assertIn('结论: "现在能读什么"', self.page)
        self.assertIn('结论: "结果从哪里回放"', self.page)
        self.assertIn('结论: "还缺什么"', self.page)
        self.assertIn('治理项: "执行门控"', self.page)
        self.assertIn('治理项: "输出范围"', self.page)
        self.assertIn('治理项: "不阻塞基础图谱"', self.page)
        self.assertIn('回放项: "数据来源"', self.page)
        self.assertIn('回放项: "量化推演"', self.page)
        self.assertIn('回放项: "次日图谱"', self.page)
        self.assertIn('回放项: "安全边界"', self.page)
        self.assertIn("GET cache 只读回放已有账本；不补调 Tushare、DeepSeek 或 worker", self.page)
        self.assertIn("次日图谱只读回放本地 cache；缺口只作为待补证据，不创建交易动作", self.page)
        self.assertIn("DeepSeek 只解释不覆盖数据", self.page)
        self.assertIn("候选雷达不是买入指令；真实交易路径隔离", self.page)
        self.assertIn('aria-label="quant projection replay destinations"', self.page)
        self.assertIn('href="#factor/factor-score" title="切换到股票量化推演结果区；只读 cache / ledger / packet，不创建 task" aria-label="replay generated stock quant projection"', self.page)
        self.assertIn('href="#next/next-session-chart" title="切换到次日图谱结果区；只读本地 next-session cache，不创建 task" aria-label="replay generated next session map"', self.page)
        self.assertIn('href="#candidate-pool" title="跳回本页候选池锚点；不重新扫描、不创建 task" aria-label="return to candidate pool after quant projection"', self.page)
        self.assertLess(self.page.index('id="factor"'), self.page.index('title="搜票量化推演"'))
        self.assertLess(self.page.index('id="next"'), self.page.index('href="#next/next-session-chart" title="切换到次日图谱结果区；只读本地 next-session cache，不创建 task" aria-label="replay generated next session map"'))
        self.assertIn("回放股票量化推演", self.page)
        self.assertIn("回放次日图谱", self.page)
        self.assertIn("回放入口区分本地模块路由和页内锚点", self.page)
        self.assertIn("#factor/factor-score 和 #next/next-session-chart 切换到量化结果区和次日图谱结果区", self.page)
        self.assertIn("#candidate-pool 留在候选池", self.page)
        self.assertIn("quantProjectionReplayDestinationState", self.page)
        self.assertIn("quantProjectionReplayDestinationNextStep", self.page)
        self.assertIn("quantProjectionReplayDestinationPacketRows", self.page)
        self.assertIn("quantProjectionReplayDestinationRows", self.page)
        self.assertIn("searchQuantProjectionSmallDataWriteback.ordinary_replay_destination_rows", self.page)
        self.assertIn("const quantProjectionReplayDestinationRows = quantProjectionReplayDestinationPacketRows.length ? quantProjectionReplayDestinationPacketRows", self.page)
        self.assertIn('aria-label="quant projection replay destination readiness"', self.page)
        self.assertIn("结果入口待确认：当前只是本地导航；不会创建 task 或刷新 provider/model", self.page)
        self.assertIn("结果入口等待缓存：先看 TaskStatusPanel，任务完成并刷新 cache 后再回放", self.page)
        self.assertIn("结果入口可回放：读取本地 cache / ledger / packet，不额外刷新外部数据或模型", self.page)
        self.assertIn("结果入口暂停：确认任务未创建；先恢复本地后端连接，再重新点击确认", self.page)
        self.assertIn('入口: "股票量化推演"', self.page)
        self.assertIn('入口: "次日图谱"', self.page)
        self.assertIn('入口: "候选池"', self.page)
        self.assertIn("href #factor 是本地量化推演模块路由；只切换模块，不发 POST task、不调 Tushare/DeepSeek", self.page)
        self.assertIn("href #next 是本地次日图谱模块路由；只切换模块，不生成交易动作、不覆盖 strategy action", self.page)
        self.assertIn("href #candidate-pool 是本页候选池锚点；Radar candidate 不是交易指令；真实交易路径继续隔离", self.page)
        self.assertIn('aria-label="quant projection advanced status readback"', self.page)
        self.assertIn("<summary>高级状态回放</summary>", self.page)
        quant_projection_start = self.page.index('title="搜票量化推演"')
        p1_p2_details_index = self.page.index('aria-label="quant projection ordinary p1 p2 engineering details"', quant_projection_start)
        trigger_boundary_index = self.page.index('aria-label="quant projection ordinary confirm trigger boundary"', quant_projection_start)
        compact_confirm_index = self.page.index('label: "确认状态"', quant_projection_start)
        end_to_end_index = self.page.index('aria-label="quant projection ordinary end to end path"', quant_projection_start)
        handoff_index = self.page.index('aria-label="quant projection ordinary confirmation handoff"', quant_projection_start)
        receipt_index = self.page.index('aria-label="quant projection confirmed task receipt readback"', quant_projection_start)
        post_confirm_index = self.page.index('aria-label="quant projection post confirm user actions"', quant_projection_start)
        small_data_writeback_index = self.page.index('aria-label="quant projection ordinary small data writeback targets"', quant_projection_start)
        writeback_surface_index = self.page.index('aria-label="quant projection ordinary writeback surface summary"', quant_projection_start)
        ordinary_result_index = self.page.index('aria-label="quant projection ordinary explainable result readback"', quant_projection_start)
        readback_index = self.page.index('aria-label="quant projection ordinary readback index"', quant_projection_start)
        ordinary_result_quick_index = self.page.index('aria-label="quant projection ordinary explainable result quick read"', quant_projection_start)
        ordinary_result_checkpoint_index = self.page.index('aria-label="quant projection ordinary result checkpoint"', quant_projection_start)
        ordinary_result_handoff_index = self.page.index('aria-label="quant projection ordinary result handoff index"', quant_projection_start)
        deepseek_governance_index = self.page.index('aria-label="quant projection ordinary deepseek governance status"', quant_projection_start)
        replay_destinations_index = self.page.index('aria-label="quant projection replay destinations"', quant_projection_start)
        replay_readiness_index = self.page.index('aria-label="quant projection replay destination readiness"', quant_projection_start)
        task_readback_index = self.page.index('aria-label="quant projection task cache packet readback"', quant_projection_start)
        advanced_index = self.page.index("<summary>高级状态回放</summary>", quant_projection_start)
        provider_replay_index = self.page.index('aria-label="quant projection tushare light api replay"', quant_projection_start)
        record_details_index = self.page.index("<summary>搜票推演记录详情</summary>", quant_projection_start)
        self.assertIn("<summary>查看任务与回放明细</summary>", self.page)
        self.assertLess(p1_p2_details_index, trigger_boundary_index)
        self.assertLess(trigger_boundary_index, compact_confirm_index)
        self.assertLess(trigger_boundary_index, advanced_index)
        self.assertLess(compact_confirm_index, advanced_index)
        self.assertLess(compact_confirm_index, end_to_end_index)
        self.assertLess(end_to_end_index, handoff_index)
        self.assertLess(handoff_index, small_data_writeback_index)
        self.assertLess(handoff_index, receipt_index)
        self.assertLess(receipt_index, post_confirm_index)
        self.assertLess(post_confirm_index, small_data_writeback_index)
        self.assertLess(small_data_writeback_index, writeback_surface_index)
        self.assertLess(writeback_surface_index, ordinary_result_index)
        self.assertLess(ordinary_result_index, readback_index)
        self.assertLess(readback_index, ordinary_result_quick_index)
        self.assertLess(ordinary_result_quick_index, ordinary_result_checkpoint_index)
        self.assertLess(ordinary_result_checkpoint_index, ordinary_result_handoff_index)
        self.assertLess(ordinary_result_handoff_index, deepseek_governance_index)
        self.assertLess(ordinary_result_index, ordinary_result_quick_index)
        self.assertLess(deepseek_governance_index, replay_destinations_index)
        self.assertLess(small_data_writeback_index, ordinary_result_index)
        self.assertLess(ordinary_result_index, replay_destinations_index)
        self.assertLess(replay_destinations_index, replay_readiness_index)
        self.assertLess(replay_readiness_index, task_readback_index)
        self.assertLess(task_readback_index, advanced_index)
        self.assertLess(advanced_index, provider_replay_index)
        self.assertLess(provider_replay_index, record_details_index)
        self.assertIn("最近任务优先显示本次确认返回的 task id", self.page)
        self.assertIn("页面刷新后再从本地 cache / packet 回放 task id 和安全 current_step", self.page)
        self.assertIn("GET cache 不会因此补调 provider", self.page)
        self.assertIn("确认按钮只提交后台链路", self.page)
        self.assertIn("服务端凭据可用才写入 Tushare call_ledger / cache / packet", self.page)
        self.assertIn("GET cache 和 React render 不补调 provider", self.page)
        self.assertIn("DeepSeek 按按钮任务治理或安全降级", self.page)
        self.assertIn('aria-live="polite"', self.page)
        self.assertLess(
            self.page.index('label: "确认代码"', quant_projection_start),
            self.page.index('label: "任务边界"', quant_projection_start),
        )
        self.assertIn("输入不触发外联；点击确认后只经 POST task / worker 后台运行", self.page)
        self.assertIn("React 渲染不直连 Tushare 或 DeepSeek", self.page)
        self.assertIn("Tushare 小全量数据写入 call_ledger", self.page)
        self.assertIn("sanitized explanation / model_ledger", self.page)
        self.assertIn("DeepSeek 只读解释可成功或安全降级", self.page)
        self.assertIn("ordinary_readback_summary", self.page)
        self.assertIn("ordinary_readback_next_step", self.page)
        self.assertIn("ordinary_readback_boundary", self.page)
        self.assertIn("ordinary_readback_surfaces_label", self.page)
        self.assertIn("ordinary_provider_api_rows", self.page)
        self.assertIn("quantProjectionProviderApiRows", self.page)
        self.assertIn('aria-label="quant projection tushare light api replay"', self.page)
        self.assertIn("Tushare light 接口回放", self.page)
        self.assertIn("trade_cal / daily / daily_basic / moneyflow", self.page)
        self.assertIn("表格只读，不补调数据源或模型", self.page)
        self.assertIn('label: "小数据下一步"', self.page)
        self.assertIn("小数据回放只读取本地 cache / ledger / packet", self.page)
        self.assertIn("推演解释只整理已有证据；不覆盖价格、持仓、因子、操作区或交易策略", self.page)

    def test_p1_symbol_input_is_shared_and_silent_until_confirm(self):
        self.assertIn(
            "const quantProjectionCanSubmit = quantProjectionSymbolReady && quantProjectionConfirmGateReady;",
            self.page,
        )
        self.assertIn("const quantProjectionHistoricalTaskMatchesInput =", self.page)
        self.assertNotIn("quantProjectionTaskAlreadyAcceptedForInput", self.page)
        self.assertIn("const quantProjectionSubmitDisabled = !quantProjectionCanSubmit || quantProjectionSubmitting;", self.page)
        self.assertEqual(self.page.count("updateSearchSymbolInput(event.target.value);"), 4)
        self.assertIn("searchSymbolTouchedRef.current = true;", self.page)
        self.assertEqual(self.page.count("setSearchSymbolTouched(true);"), 1)
        self.assertEqual(self.page.count("renderQuantProjectionPrimaryAction("), 4)
        self.assertEqual(self.page.count("onClick={launchQuantProjection}"), 1)
        self.assertIn('aria-label="candidate radar operator symbol input"', self.page)
        self.assertIn('aria-label="candidate radar first screen quant projection symbol"', self.page)
        self.assertIn('aria-label="radar summary quant projection symbol"', self.page)
        self.assertIn('aria-label="search quant projection symbol"', self.page)
        self.assertIn("candidate-radar-operator-symbol-help", self.page)
        self.assertIn("candidate-radar-operator-confirm-help", self.page)
        self.assertIn("输入股票代码只做本地校验；不会创建任务，也不会调用 Tushare 或 DeepSeek", self.page)
        self.assertIn("点击确认才创建 ${quantProjectionSymbolValidation.normalized} 的 Tushare-first POST task", self.page)
        primary_action_start = self.page.index("const renderQuantProjectionPrimaryAction =")
        primary_action_end = self.page.index(") : (", primary_action_start)
        primary_action_slice = self.page[primary_action_start:primary_action_end]
        self.assertIn('href="#factor/factor-score"', primary_action_slice)
        self.assertIn(">查看最近结果</a>", primary_action_slice)
        submit_start = self.page.index("const launchQuantProjection = () =>")
        submit_end = self.page.index("const launchQuantProjectionAcceptanceDryRun = () =>", submit_start)
        submit_slice = self.page[submit_start:submit_end]
        self.assertIn("const quantProjectionSubmittingRef = useRef(false);", self.page)
        self.assertIn("!quantProjectionCanSubmit ||", submit_slice)
        self.assertIn("quantProjectionUseRecentResultInsteadOfSubmit ||", submit_slice)
        self.assertIn("quantProjectionSubmittingRef.current", submit_slice)
        self.assertIn("quantProjectionSubmittingRef.current = true;", submit_slice)
        self.assertIn("quantProjectionSubmittingRef.current = false;", submit_slice)
        self.assertIn("void postCandidateRadarQuantProjection({", submit_slice)
        self.assertNotIn("updateSearchSymbolInput(event.target.value);", submit_slice)

    def test_p1_confirm_gate_uses_runtime_packet_contract_evidence(self):
        gate_start = self.page.index("const desktopP0QuickActionReady =")
        gate_end = self.page.index("const ordinaryCacheSourceLabel =", gate_start)
        gate = self.page[gate_start:gate_end]

        self.assertIn("const candidateRadarCacheGetReadable = !error && Boolean(cache.status);", self.page)
        self.assertIn("const candidateRadarStatusLabel = candidateRadarCacheReady", self.page)
        self.assertIn('? "本地回放可用"', self.page)
        self.assertIn("本地回放可用：${String(cache.status)}", self.page)
        self.assertIn('tone={candidateRadarCacheGetReadable ? "good" : "neutral"}', self.page)
        self.assertIn('{ label: "本地缓存", state: candidateRadarCacheGetReadable ? "done" : "waiting", detail: candidatePoolCacheDetail }', self.page)
        self.assertIn("bootstrapRuntimeModeReady", gate)
        self.assertIn('desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache"', gate)
        self.assertIn("const desktopP0QuickActionReady = desktopP0CurrentNextActionRows.some", gate)
        self.assertIn("row.p1_entry_enabled === true || row.p0_ready_now === true", gate)
        self.assertIn("const desktopP0RuntimeModeOrHandoffReady = bootstrapRuntimeModeReady || desktopP0QuickActionReady", gate)
        self.assertIn("const quantProjectionLocalAppReady =", self.page)
        self.assertIn("const desktopP0ContractEvidenceReady =", gate)
        self.assertIn('desktopOneClickStartupSummary.status === "one_click_frontend_backend_ready"', gate)
        self.assertIn('desktopP0LocalConnectionReceipt.status === "p0_local_connection_receipt_ready"', gate)
        self.assertIn("desktopP0RuntimePacketsReady &&", gate)
        self.assertIn("quantProjectionLocalAppReady ||", gate)
        self.assertIn("desktopP0ContractEvidenceReady &&", gate)
        self.assertIn("desktopP0RuntimeModeOrHandoffReady &&", gate)
        self.assertNotIn("desktopPreflightReady &&\n    desktopP0ConnectionEvidenceReady", gate)

        submit_start = self.page.index("const launchQuantProjection = () =>")
        submit_end = self.page.index("const launchQuantProjectionAcceptanceDryRun = () =>", submit_start)
        submit_slice = self.page[submit_start:submit_end]
        self.assertIn("p0_runtime_packets_ready: desktopP0RuntimePacketsReady || quantProjectionLocalAppReady", submit_slice)
        self.assertIn("p0_runtime_mode_or_handoff_ready: desktopP0RuntimeModeOrHandoffReady || quantProjectionLocalAppReady", submit_slice)
        self.assertIn("p0_quick_action_ready: desktopP0QuickActionReady", submit_slice)
        self.assertIn("p0_contract_evidence_ready: desktopP0ContractEvidenceReady || quantProjectionLocalAppReady", submit_slice)

    def test_ordinary_quant_projection_submit_does_not_auto_chain_provider_model(self):
        submit_start = self.page.index("const launchQuantProjection = () =>")
        submit_end = self.page.index("const launchQuantProjectionAcceptanceDryRun = () =>", submit_start)
        submit_slice = self.page[submit_start:submit_end]
        summary_start = self.page.index('title="普通用户雷达摘要"')
        summary_end = self.page.index('title="下一票候选池"', summary_start)
        summary_slice = self.page[summary_start:summary_end]
        confirm_quick_start = self.page.index('aria-label="quant projection ordinary confirm outcome quick read"', summary_start)
        post_confirm_start = self.page.index('aria-label="quant projection post confirm user actions"')
        post_confirm_end = self.page.index('aria-label="quant projection ordinary small data writeback targets"', post_confirm_start)
        post_confirm_slice = self.page[post_confirm_start:post_confirm_end]
        task_status_start = self.page.index('aria-label="candidate radar first screen task status"')
        task_status_end = self.page.index('aria-label="candidate radar post confirm one screen outcome"', task_status_start)
        task_status_slice = self.page[task_status_start:task_status_end]

        self.assertIn("postCandidateRadarQuantProjection({", submit_slice)
        self.assertIn('scan_mode: "search_quant_projection"', submit_slice)
        self.assertIn("symbol: normalizeAshareSymbolInput(searchSymbol).normalized", submit_slice)
        self.assertIn("include_tushare: true", submit_slice)
        self.assertIn("include_deepseek: false", submit_slice)
        self.assertIn('deepseek_policy: "separate_governed_executor_after_explicit_authorization"', submit_slice)
        self.assertIn("user_approved: true", submit_slice)
        self.assertIn('requested_by: "candidate_radar_page"', submit_slice)
        self.assertIn('.catch(() => {', submit_slice)
        self.assertIn('quantProjectionSubmitFailureMessage("frontend_submit_exception")', submit_slice)
        self.assertIn("setQuantProjectionSubmitting(false)", submit_slice)
        self.assertNotIn("run_provider_model_now", submit_slice)
        self.assertNotIn("operator_approved", submit_slice)
        self.assertNotIn("quant-projection-provider-model-acceptance", submit_slice)

        self.assertIn("查看本地缓存", summary_slice)
        self.assertIn("运行本地快扫", summary_slice)
        self.assertIn("renderQuantProjectionPrimaryAction(quantProjectionSummarySubmitHelpId)", summary_slice)
        self.assertIn("disabled={quantProjectionSubmitDisabled}", self.page)
        self.assertIn('{quantProjectionSubmitting ? "提交中..." : "确认并生成 3.0 量化推演"}', self.page)
        self.assertIn("quantProjectionSubmitErrorLabel", summary_slice)
        self.assertIn('aria-label="candidate radar p0 submit failure recovery"', summary_slice)
        self.assertIn("优先读取 POST 失败 envelope 里的 frontend_backend_auto_link ledger", summary_slice)
        self.assertIn("恢复提示只读展示，不自动重试、不创建 task", summary_slice)
        self.assertIn('aria-label="candidate radar ordinary expanded p1 p3 readback details"', summary_slice)
        self.assertIn("<summary>更多回放明细</summary>", summary_slice)
        self.assertIn("普通主视图保留 P1 确认、任务状态、P2 三面速读和 P3 首屏结果", summary_slice)
        self.assertIn("{quantProjectionInputSessionState}", summary_slice)
        self.assertIn('href="#factor"', summary_slice)
        self.assertIn("{ordinaryUserText(quantProjectionSummaryGuidance)}", summary_slice)
        self.assertIn("quantProjectionOrdinaryConfirmOutcomeRows", summary_slice)
        self.assertIn("P1 确认结果速读", summary_slice)
        self.assertIn("优先读取服务端 ordinary_confirm_outcome_rows", summary_slice)
        self.assertIn("任务是否接收、P2 三面是否回放、P3 入口是否可读", summary_slice)
        self.assertIn("quantProjectionOneScreenActionRows", summary_slice)
        self.assertIn('aria-label="candidate radar ordinary one screen actions"', summary_slice)
        self.assertIn("一屏行动摘要", summary_slice)
        self.assertIn("确认、任务、写回、结果合成一张普通用户表", summary_slice)
        self.assertIn("rows={quantProjectionOneScreenActionRows}", summary_slice)
        self.assertIn('aria-label="candidate radar ordinary p2 p3 replay checklist"', summary_slice)
        self.assertIn("确认后先看这张只读索引", summary_slice)
        self.assertIn("确认回执、任务回放、数据接口和 P3 结果速读都来自本地 cache / ledger / packet", summary_slice)
        self.assertIn("不会创建 task、不会补调 Tushare/DeepSeek", summary_slice)
        self.assertIn("rows={quantProjectionReadbackIndexRows}", summary_slice)
        self.assertIn('aria-label="candidate radar ordinary p1 p2 detail readback"', summary_slice)
        self.assertIn("<summary>查看 P1/P2 回放明细</summary>", summary_slice)
        self.assertIn("确认链路、P1 路径和 P2 三面核对默认收起", summary_slice)
        self.assertIn("ordinaryP1ConfirmPathRows", summary_slice)
        self.assertIn("P1 普通确认路径", summary_slice)
        self.assertIn('aria-label="candidate radar ordinary p1 confirm path"', summary_slice)
        self.assertIn("普通用户先看这条 P1 路径", summary_slice)
        self.assertIn('aria-label="candidate radar ordinary p2 writeback rail"', summary_slice)
        self.assertIn("P2 三面状态轨", summary_slice)
        self.assertIn("state={quantProjectionP2WritebackRailState}", summary_slice)
        self.assertIn("steps={quantProjectionP2WritebackRailSteps}", summary_slice)
        self.assertIn('aria-label="candidate radar ordinary p2 writeback surfaces"', summary_slice)
        self.assertIn("P2 小数据三面回放", summary_slice)
        self.assertIn("普通用户确认后看这张表：cache、call_ledger、packet 三面是否可回放", summary_slice)
        self.assertIn("它只读取本地 cache，不创建 task、不补调 Tushare/DeepSeek", summary_slice)
        self.assertIn("rows={quantProjectionWritebackSurfaceRows}", summary_slice)
        self.assertIn("quantProjectionP3ResultSummaryItems", self.page)
        self.assertIn('aria-label="candidate radar ordinary p3 result summary strip"', summary_slice)
        self.assertIn("<MetricGrid items={quantProjectionP3ResultSummaryItems} />", summary_slice)
        self.assertIn('aria-label="quant projection ordinary p3 result summary strip"', self.page)
        self.assertIn('label: "可读结论"', self.page)
        self.assertIn('label: "数据来源"', self.page)
        self.assertIn('label: "安全边界"', self.page)
        self.assertIn('aria-label="quant projection p0 submit failure recovery"', self.page)
        self.assertIn("确认按钮失败后先看本地联通恢复包", self.page)
        self.assertIn("check-only 不启动服务", self.page)
        self.assertIn("页面不会补调数据源或模型", self.page)
        self.assertIn('aria-label="candidate radar ordinary p2 writeback recovery"', summary_slice)
        self.assertIn("rows={quantProjectionWritebackRecoveryDisplayRows}", summary_slice)
        self.assertIn('label: "P2 三面"', summary_slice)
        self.assertIn('aria-live="polite"', summary_slice)
        self.assertIn('aria-label="candidate radar primary next action"', summary_slice)
        self.assertIn('aria-label="candidate radar next user actions"', summary_slice)
        self.assertLess(summary_slice.index('aria-label="candidate radar primary next action"'), summary_slice.index('aria-label="candidate radar next user actions"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar p3 first screen result quick read"'), summary_slice.index('aria-label="candidate radar ordinary expanded p1 p3 readback details"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary expanded p1 p3 readback details"'), summary_slice.index('aria-label="candidate radar ordinary p1 to p3 stage rail"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary p1 to p3 stage rail"'), summary_slice.index('aria-label="candidate radar ordinary one screen actions"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary one screen actions"'), summary_slice.index('aria-label="quant projection submit recovery quick read"'))
        self.assertLess(summary_slice.index('aria-label="quant projection submit recovery quick read"'), summary_slice.index('aria-label="quant projection ordinary confirm outcome quick read"'))
        self.assertLess(summary_slice.index('aria-label="quant projection ordinary confirm outcome quick read"'), summary_slice.index('aria-label="candidate radar p1 tushare first chain quick read"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar p1 tushare first chain quick read"'), summary_slice.index('aria-label="candidate radar ordinary p2 p3 replay checklist"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary one screen actions"'), summary_slice.index('aria-label="candidate radar ordinary p2 p3 replay checklist"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary p2 p3 replay checklist"'), summary_slice.index('aria-label="candidate radar ordinary p1 p2 detail readback"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary p1 p2 detail readback"'), summary_slice.index('aria-label="candidate radar ordinary p1 confirm path"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary p1 confirm path"'), summary_slice.index('aria-label="candidate radar ordinary p2 writeback rail"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary p2 writeback rail"'), summary_slice.index('aria-label="candidate radar ordinary p2 writeback surfaces"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary p1 p2 detail readback"'), summary_slice.index('aria-label="candidate radar ordinary p3 explainable result quick read"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary p3 result summary strip"'), summary_slice.index('aria-label="candidate radar ordinary p3 explainable result quick read"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary p3 explainable result quick read"'), summary_slice.index('aria-label="candidate radar ordinary p3 result checkpoint"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar ordinary p3 result checkpoint"'), summary_slice.index('aria-label="candidate radar ordinary p3 result handoff index"'))
        self.assertNotIn('aria-label="candidate radar audit p5 governance details"', summary_slice)
        self.assertNotIn('aria-label="candidate radar audit p6 strict closeout handoff"', summary_slice)
        self.assertNotIn("<summary>DeepSeek 解释治理状态</summary>", summary_slice)
        self.assertNotIn("<summary>P6 14 LTG strict closeout 交接</summary>", summary_slice)
        self.assertLess(summary_slice.index("{ordinaryUserText(quantProjectionSummaryGuidance)}"), summary_slice.index('aria-label="candidate radar next user actions"'))
        self.assertNotIn("launchQuantProjectionAcceptanceDryRun", summary_slice)
        self.assertNotIn("launchQuantProjectionExecutionRequest", summary_slice)
        self.assertNotIn("launchProviderParityDryRun", summary_slice)
        self.assertNotIn("provider-model", summary_slice)
        self.assertNotIn("launchQuantProjectionAcceptanceDryRun", self.page[confirm_quick_start:summary_end])
        self.assertNotIn("launchQuantProjectionExecutionRequest", self.page[confirm_quick_start:summary_end])
        self.assertNotIn("launchQuantProjectionProviderModelAcceptance", self.page[confirm_quick_start:summary_end])
        self.assertIn("quantProjectionPostConfirmActionRows", post_confirm_slice)
        self.assertIn("刷新本地 cache", post_confirm_slice)
        self.assertNotIn("launchQuantProjectionAcceptanceDryRun", post_confirm_slice)
        self.assertNotIn("launchQuantProjectionExecutionRequest", post_confirm_slice)
        self.assertNotIn("launchQuantProjectionProviderModelAcceptance", post_confirm_slice)
        self.assertNotIn("quant-projection-provider-model-acceptance", post_confirm_slice)
        self.assertIn("quantProjectionTaskSuccessRefreshRows", task_status_slice)
        self.assertIn("TaskStatusPanel", task_status_slice)
        self.assertIn("任务成功后自动回读", task_status_slice)
        self.assertEqual(
            self.page.count("<TaskStatusPanel taskId={quantProjectionTaskPanelTaskId} onSuccess={refreshQuantProjectionReadback} />"),
            1,
        )
        self.assertIn('aria-label="quant projection tushare-first task status handoff"', self.page)
        handoff_slice = self.page[
            self.page.index('aria-label="quant projection tushare-first task status handoff"') :
            self.page.index('aria-label="quant projection confirm chain explanation details"')
        ]
        self.assertIn("任务状态面板已固定在确认后一屏结果", handoff_slice)
        self.assertNotIn("TaskStatusPanel", handoff_slice)
        self.assertNotIn("launchQuantProjectionAcceptanceDryRun", task_status_slice)
        self.assertNotIn("launchQuantProjectionExecutionRequest", task_status_slice)
        self.assertNotIn("launchQuantProjectionProviderModelAcceptance", task_status_slice)
        self.assertNotIn("quant-projection-provider-model-acceptance", task_status_slice)

    def test_tushare_first_handoff_matches_ordinary_submit_boundary(self):
        self.assertIn("Candidate Radar searched-symbol confirmation must be reported through the active checkpoint", self.handoff)
        self.assertIn("confirmed search may submit bounded Tushare provider work through POST task and call ledger", self.handoff)
        self.assertIn("ordinary confirm action may create the Tushare-first backend task chain", self.handoff)
        self.assertIn("keeps DeepSeek skipped", self.handoff)
        self.assertIn("does not require the old `run_provider_model_now` switch", self.handoff)
        self.assertIn("page open, search typing, React render, and GET cache stay silent", self.handoff)
        self.assertNotIn("DeepSeek is requested into the explanation ledger/governance path", self.handoff)
        self.assertNotIn("automatic v4/pro execution", self.handoff)

    def test_task_status_panel_surfaces_tushare_first_ledger_for_ordinary_users(self):
        panel = self.task_status_panel
        self.assertIn("const tushareProviderRows = callLedger.filter(isTushareProviderLedgerRow)", panel)
        self.assertIn("const tushareProviderSuccessCount", panel)
        self.assertIn("Tushare ${tushareProviderSuccessCount}/${tushareProviderRows.length} 个接口已写入主任务 call_ledger", panel)
        self.assertIn('aria-label="task status tushare first ledger quick read"', panel)
        self.assertIn("Tushare-first 速读：普通用户先看主任务是否已回放接口级 ledger", panel)
        self.assertIn("Tushare ${tushareProviderSuccessCount}/${tushareProviderRows.length} 个接口已写入 task.call_ledger", panel)
        self.assertIn('aria-label="task status p2 writeback quick read"', panel)
        self.assertIn("P2 写回速读：普通用户先看 cache、call_ledger、packet 三面是否有本地回放信号", panel)
        self.assertIn('写回面: "cache"', panel)
        self.assertIn('写回面: "call_ledger"', panel)
        self.assertIn('写回面: "packet"', panel)
        self.assertIn('aria-label="task status p3 result replay quick read"', panel)
        self.assertIn("P3 结果入口速读：任务写回后按本地入口回放可解释结果", panel)
        self.assertIn('结果入口: "股票量化推演"', panel)
        self.assertIn('结果入口: "次日图谱"', panel)
        self.assertLess(
            panel.index('aria-label="task status ordinary summary"'),
            panel.index('aria-label="task status tushare first ledger quick read"'),
        )
        self.assertLess(
            panel.index('aria-label="task status tushare first ledger quick read"'),
            panel.index('aria-label="task status p2 writeback quick read"'),
        )
        self.assertLess(
            panel.index('aria-label="task status p2 writeback quick read"'),
            panel.index('aria-label="task status p3 result replay quick read"'),
        )
        self.assertLess(
            panel.index('aria-label="task status p3 result replay quick read"'),
            panel.index('aria-label="task status p3 result replay links"'),
        )
        self.assertLess(
            panel.index('aria-label="task status p3 result replay quick read"'),
            panel.index('aria-label="task status audit details"'),
        )
        self.assertIn("未检测到模型账本；Tushare-first 和基础图谱不等待模型", panel)
        self.assertIn("DeepSeek 解释只读回放或安全降级，不阻塞 Tushare-first 和基础图谱", panel)
        self.assertIn("TaskStatusPanel 只读当前 task.call_ledger；不补调 Tushare、DeepSeek 或 GitHub。", panel)
        self.assertIn('const CANDIDATE_CONFIRM_HREF = "#candidates/candidate-radar-search-quant-projection";', panel)
        self.assertIn('结果入口: "下一票雷达确认输入区"', panel)
        self.assertIn("入口: CANDIDATE_CONFIRM_HREF", panel)
        self.assertIn("href: CANDIDATE_CONFIRM_HREF", panel)
        self.assertIn("open candidate radar confirm input from task status", panel)
        self.assertNotIn('入口: "#candidates"', panel)
        self.assertNotIn('href: "#candidates"', panel)
        self.assertIn("不交易、不改 strategy action", panel)
        self.assertNotIn("postCandidateRadarQuantProjectionProviderModelAcceptance", panel)
        self.assertNotIn("launchQuantProjectionProviderModelAcceptance", panel)

    def test_candidate_radar_restores_persisted_task_panel_without_creating_new_task(self):
        self.assertIn(
            "TaskStatusPanel 可恢复本地状态轮询，不创建新 task、不补调 Tushare/DeepSeek",
            self.page,
        )
        self.assertIn("(quantProjectionTaskVisible || Boolean(quantProjectionPersistedTaskId)) && !quantProjectionTaskPanelStaleForCurrentInput", self.page)
        self.assertIn(
            'quantProjectionTaskPanelStaleForCurrentInput ? "" : quantProjectionTaskVisible && taskId ? taskId : quantProjectionPersistedTaskId',
            self.page,
        )
        self.assertIn("const manualTaskPanelVisible = Boolean(taskId);", self.page)
        self.assertIn(
            "暂无可轮询任务；点击确认按钮或手动任务后才显示 TaskStatusPanel",
            self.page,
        )

    def test_candidate_radar_page_does_not_embed_provider_or_trade_calls(self):
        forbidden_fragments = (
            "tushare.pro_api",
            "ts.pro_api",
            "deepseek.chat",
            "api.github.com",
            "fetch(",
            "executeTrade(",
            "placeOrder(",
            "broker.submit",
            "live_order",
        )
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, self.page)


if __name__ == "__main__":
    unittest.main()
