import unittest
from pathlib import Path


class CandidateRadarProviderStateFrontendTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.page = (
            root / "desktop" / "src" / "routes" / "CandidateRadar.tsx"
        ).read_text(encoding="utf-8")

    def test_search_panel_replays_cached_tushare_state_without_model_claim(self):
        summary_start = self.page.index('title="普通用户雷达摘要"')
        summary_end = self.page.index('title="下一票候选池"', summary_start)
        summary_panel = self.page[summary_start:summary_end]
        search_panel_start = self.page.index('title="搜票量化推演"')
        search_panel_end = self.page.index('title="快速雷达扫描"', search_panel_start)
        search_panel = self.page[search_panel_start:search_panel_end]
        p1_p2_details_start = self.page.index(
            '<details className="developer-audit-details" aria-label="quant projection ordinary p1 p2 engineering details">',
            search_panel_start,
        )
        search_panel_top = self.page[search_panel_start:p1_p2_details_start]

        self.assertIn("searchQuantProviderModelAcceptance", self.page)
        self.assertIn("search_quant_provider_model_acceptance_receipt", self.page)
        self.assertIn("tushare_call_ledger_evidence_done", self.page)
        self.assertIn("provider_api_success_count", self.page)
        self.assertIn("provider_api_call_count", self.page)
        self.assertIn("deepseek_skipped_by_request", self.page)
        self.assertIn("Tushare ledger 已回放", self.page)
        self.assertIn("GET cache 已回放 Tushare provider ledger", self.page)
        self.assertIn("quantProjectionSmallDataReplayState", self.page)
        self.assertIn("quantProjectionSmallDataRows", self.page)
        self.assertIn("quantProjectionSmallDataWritebackSurfaces", self.page)
        self.assertIn("quantProjectionSmallDataReadbackContract", self.page)
        self.assertIn("quantProjectionSmallDataStageLabel", self.page)
        self.assertIn("quantProjectionSmallDataProvenance", self.page)
        self.assertIn("quantProjectionProviderCallSource", self.page)
        self.assertIn("quantProjectionTushareFirstChainRows", self.page)
        self.assertIn("ordinary_tushare_first_chain_rows", self.page)
        self.assertIn("优先读取服务端 ordinary_tushare_first_chain_rows", search_panel)
        self.assertIn("cache / ledger / packet 已回放", self.page)
        self.assertIn("packet=command_center_3_candidate_radar_cache", self.page)
        self.assertIn("GET cache 和 React render 不补调 provider/model", self.page)
        self.assertIn("GET cache 和 React render 不补调 provider", self.page)
        self.assertIn("当前读回来自 GET cache 的本地 packet", self.page)
        self.assertIn("quantProjectionResearchMapState", self.page)
        self.assertIn("quantProjectionMapNextStep", self.page)
        self.assertIn("quantProjectionOrdinaryResultSummary", self.page)
        self.assertIn("quantProjectionOrdinaryResultNext", self.page)
        self.assertIn("quantProjectionOrdinaryResultBoundary", self.page)
        self.assertIn("quantProjectionOrdinaryResultEvidence", self.page)
        self.assertIn("quantProjectionOrdinaryResultActionRows", self.page)
        self.assertIn("ordinary_result_action_rows", self.page)
        self.assertIn("const quantProjectionInterpretationExplicitReady", self.page)
        self.assertIn("const quantProjectionInterpretationPartialLedgerReady", self.page)
        self.assertIn("const quantProjectionInterpretationReady = quantProjectionInterpretationExplicitReady", self.page)
        self.assertIn("等待小数据三面 ready 后再开放 P3 速读", self.page)
        self.assertIn("不要把单独 call_ledger 当作 P3 结果完成", self.page)
        self.assertNotIn(
            "searchQuantProjectionInterpretation.interpretation_ready === true || quantProjectionProviderLedgerReady",
            self.page,
        )
        self.assertIn("量化推演 / Next Session 图谱等待本地 cache 写入", self.page)
        self.assertIn("查看量化推演结果，再看次日图谱预览", self.page)
        self.assertIn("解释只基于本地 cache / ledger / packet", self.page)
        self.assertIn("证据：等待 Tushare-first 账本；DeepSeek 未参与", self.page)
        self.assertIn('aria-label="quant projection ordinary explainable result actions"', search_panel)
        self.assertIn("可解释结果行动", search_panel)
        self.assertIn("优先读取服务端 ordinary_result_action_rows", search_panel)
        self.assertIn("读可读结论、回放量化推演、打开次日图谱", search_panel)
        self.assertIn("DeepSeek 已跳过：等待 governed executor", self.page)
        self.assertIn('label: "Tushare ledger"', search_panel)
        self.assertIn('label: "cache / ledger / packet"', search_panel)
        self.assertIn('label: "小数据回放"', search_panel)
        self.assertIn('label: "小数据写入"', search_panel)
        self.assertIn('label: "provider 来源"', search_panel)
        self.assertIn('label: "回放合同"', search_panel)
        self.assertIn("rows={quantProjectionSmallDataRows}", search_panel)
        self.assertIn("ordinary_readback_rows", self.page)
        self.assertIn('label: "投研图谱联动"', search_panel)
        self.assertIn('label: "可读结论"', search_panel)
        self.assertIn('label: "结论下一步"', search_panel)
        self.assertIn('label: "结论证据"', search_panel)
        self.assertIn('label: "结论边界"', search_panel)
        self.assertIn('label: "图谱下一步"', search_panel)
        self.assertIn("普通入口保留“确认并生成”作为 P1 主按钮", search_panel)
        self.assertIn("点击后在本卡显示任务接收和状态", search_panel)
        self.assertIn("title={quantProjectionSubmitButtonLabel}", search_panel)
        self.assertIn('aria-label="candidate radar ordinary visible progress watch"', summary_panel)
        self.assertIn("边用边看进度", summary_panel)
        self.assertIn("MetricGrid items={quantProjectionTaskIndexProgressItems}", summary_panel)
        self.assertIn("coarseFineScreening", self.page)
        self.assertIn("coarse_fine_screening_contract", self.page)
        self.assertIn("coarse_screening_rows", self.page)
        self.assertIn("fine_screening_rows", self.page)
        self.assertIn("top_watch_excluded_group_rows", self.page)
        self.assertIn("ordinaryCoarseFineItems", self.page)
        self.assertIn("ordinaryCoarseFineGroupRows", self.page)
        self.assertIn("ordinaryCoarseFineStageRows", self.page)
        self.assertIn('aria-label="candidate radar coarse fine screening ordinary summary"', summary_panel)
        self.assertIn("粗筛/细筛候选分组", summary_panel)
        self.assertIn("Top / Watch / Excluded", summary_panel)
        self.assertIn("cache-only / local fallback / Tushare-backed sample", summary_panel)
        self.assertIn("这条切片只说明当前候选分组可读；不是最终替代完成", summary_panel)
        self.assertIn("不声称旧雷达可以退场", summary_panel)
        self.assertIn("GET cache、搜索输入和页面渲染不补调外部数据或模型", summary_panel)
        self.assertIn('aria-label="candidate radar coarse fine screening row details"', summary_panel)
        self.assertIn("<summary>查看分组明细</summary>", summary_panel)
        self.assertIn("Top / Watch / Excluded 的明细行默认收起", summary_panel)
        self.assertIn("rows={ordinaryCoarseFineGroupRows}", summary_panel)
        self.assertIn("rows={ordinaryCoarseFineStageRows}", summary_panel)
        self.assertLess(
            summary_panel.index('aria-label="candidate radar coarse fine screening ordinary summary"'),
            summary_panel.index('aria-label="candidate radar ordinary task progress details"'),
        )
        self.assertIn('aria-label="refresh candidate radar visible progress readback"', summary_panel)
        self.assertIn("进度回放只确认 task id、任务步骤、P2/P3 和结果入口", summary_panel)
        self.assertIn('aria-label="candidate radar optional local actions details"', summary_panel)
        self.assertIn("<summary>可选本地操作</summary>", summary_panel)
        self.assertIn("这里保留缓存刷新、本地快扫和重复确认入口，默认收起", summary_panel)
        self.assertIn('aria-label="candidate radar next user actions"', summary_panel)
        self.assertLess(
            summary_panel.index('aria-label="candidate radar ordinary visible progress watch"'),
            summary_panel.index('aria-label="candidate radar ordinary task progress details"'),
        )
        self.assertLess(
            summary_panel.index('aria-label="candidate radar primary next action"'),
            summary_panel.index('aria-label="candidate radar optional local actions details"'),
        )
        self.assertLess(
            summary_panel.index('aria-label="candidate radar optional local actions details"'),
            summary_panel.index('aria-label="candidate radar ordinary audit shortcuts"'),
        )
        self.assertIn("quantProjectionOrdinaryOneGlanceItems", self.page)
        ordinary_one_glance_start = self.page.index("const quantProjectionOrdinaryOneGlanceItems")
        ordinary_one_glance_end = self.page.index("const quantProjectionFailedSubmitLedgerRows", ordinary_one_glance_start)
        ordinary_one_glance_definition = self.page[ordinary_one_glance_start:ordinary_one_glance_end]
        self.assertIn('aria-label="quant projection ordinary one glance state"', search_panel_top)
        self.assertIn("确认后一眼看懂", search_panel_top)
        self.assertIn("MetricGrid items={quantProjectionOrdinaryOneGlanceItems}", search_panel_top)
        self.assertIn('label: "结果入口"', self.page)
        self.assertIn("股票量化推演 / 次日图谱按同一次确认回放", self.page)
        self.assertIn("不交易、不改交易策略", ordinary_one_glance_definition)
        self.assertNotIn("不交易、不改 action", ordinary_one_glance_definition)
        self.assertIn('aria-label="quant projection ordinary input and submit notes"', search_panel_top)
        self.assertIn("<summary>输入与按钮状态</summary>", search_panel_top)
        ordinary_visible_end = search_panel_top.index(
            '<details className="developer-audit-details" aria-label="quant projection ordinary input and submit notes">'
        )
        ordinary_visible_top = search_panel_top[:ordinary_visible_end]
        self.assertIn("输入代码并确认后生成本地投研结果；模型解释作为高级能力单独补", ordinary_visible_top)
        self.assertIn("本地 FastAPI 已接上：可以输入股票代码；只有确认按钮会启动本地投研数据链。", self.page)
        self.assertNotIn("POST task", ordinary_visible_top)
        self.assertNotIn("DeepSeek skipped", ordinary_visible_top)
        self.assertNotIn("Tushare-first", ordinary_visible_top)
        submit_label_start = self.page.index("const quantProjectionSubmitButtonLabel")
        submit_label_end = self.page.index("const quantProjectionSubmitAriaLabel", submit_label_start)
        submit_label_definition = self.page[submit_label_start:submit_label_end]
        self.assertIn("确认 ${quantProjectionSymbolValidation.normalized} 并生成本地投研结果", submit_label_definition)
        self.assertNotIn("POST task", submit_label_definition)
        self.assertNotIn("DeepSeek skipped", submit_label_definition)
        self.assertNotIn("Tushare-first", submit_label_definition)
        self.assertNotIn("task id", submit_label_definition)
        self.assertLess(
            search_panel_top.index('aria-label="quant projection ordinary one glance state"'),
            search_panel_top.index('label="quant projection ordinary task status"'),
        )
        self.assertIn(
            'aria-label="quant projection ordinary p1 p2 engineering details"',
            search_panel,
        )
        self.assertIn("<summary>查看任务与回放明细</summary>", search_panel)
        self.assertIn("普通主视图先保留状态轨、可读结论和回放入口", search_panel)
        self.assertNotIn('aria-label="quant projection p1 confirm gate checklist"', search_panel_top)
        self.assertNotIn('aria-label="quant projection ordinary p2 writeback integrity"', search_panel_top)
        self.assertNotIn("确认任务接收回执", search_panel_top)
        self.assertIn("quantProjectionTaskVisible", self.page)
        self.assertIn("quantProjectionPersistedTaskId", self.page)
        self.assertIn("quantProjectionTaskPanelTaskId", self.page)
        self.assertIn("quantProjectionTaskVisible && taskId ? taskId : quantProjectionPersistedTaskId", self.page)
        self.assertIn("quantProjectionDisplayTaskId", self.page)
        self.assertIn("run_candidate_radar_quant_projection", self.page)
        self.assertIn("run_candidate_radar_quant_projection_provider_model_acceptance", self.page)
        self.assertIn('aria-label="quant projection tushare-first task status handoff"', search_panel)
        self.assertIn("<TaskLaunchReceipt receipt={taskReceipt} />", self.page)
        self.assertIn(
            "<TaskStatusPanel taskId={quantProjectionTaskPanelTaskId} onSuccess={refreshQuantProjectionReadback} />",
            self.page,
        )
        self.assertEqual(
            self.page.count("<TaskStatusPanel taskId={quantProjectionTaskPanelTaskId} onSuccess={refreshQuantProjectionReadback} />"),
            1,
        )
        handoff_start = search_panel.index('aria-label="quant projection tushare-first task status handoff"')
        handoff_end = search_panel.index('aria-label="quant projection confirm chain explanation details"', handoff_start)
        handoff = search_panel[handoff_start:handoff_end]
        self.assertIn("任务状态面板已固定在确认后一屏结果", handoff)
        self.assertNotIn("TaskStatusPanel", handoff)
        self.assertIn("后台补证申请待准备", self.page)
        self.assertIn("普通页只看结果状态", self.page)
        self.assertIn("不额外刷新外部数据或模型", self.page)
        self.assertNotIn("确认 Tushare-first 补证", search_panel)
        self.assertNotIn("生成 provider/model execution request", search_panel_top)
        self.assertNotIn("scope/hash", search_panel_top)
        self.assertNotIn("execution-request", search_panel_top)
        self.assertNotIn("provider/model", search_panel_top)
        self.assertIn("确认 Tushare-first 补证", self.page)
        self.assertIn(
            "Tushare ledger 来自 cache / call_ledger 回放",
            search_panel,
        )
        self.assertIn("普通页不展示 prompt/output", search_panel)
        self.assertIn("不改交易策略", self.page)
        self.assertIn("敏感凭据", self.page)
        self.assertNotIn("不改 action", self.page)
        self.assertNotIn("token/key", self.page)
        self.assertIn('className="developer-audit-details" aria-label="quant projection ordinary p1 p2 immediate readback"', search_panel_top)
        self.assertIn("<summary>P1/P2 即时回读表</summary>", search_panel_top)
        self.assertIn("P1/P2 即时回读", search_panel_top)
        self.assertIn("ordinary_confirm_outcome_rows 与 ordinary_writeback_surface_summary_rows", search_panel_top)
        self.assertIn("这两张 P1/P2 回放表默认收起", search_panel_top)
        self.assertIn("不创建第二个 task", search_panel_top)
        self.assertIn("rows={quantProjectionOrdinaryConfirmOutcomeRows}", search_panel_top)
        self.assertIn("rows={quantProjectionWritebackSurfaceRows}", search_panel_top)
        self.assertLess(
            search_panel.index('aria-label="quant projection ordinary p1 p2 immediate readback"'),
            search_panel.index('aria-label="quant projection ordinary p1 p2 engineering details"'),
        )

    def test_search_panel_keeps_external_work_button_gated(self):
        submit_start = self.page.index("const launchQuantProjection = () =>")
        submit_end = self.page.index(
            "const launchQuantProjectionAcceptanceDryRun = () =>",
            submit_start,
        )
        submit_slice = self.page[submit_start:submit_end]
        search_panel_start = self.page.index('title="搜票量化推演"')
        search_panel_end = self.page.index('title="快速雷达扫描"', search_panel_start)
        search_panel = self.page[search_panel_start:search_panel_end]

        self.assertIn("include_tushare: true", submit_slice)
        self.assertIn("include_deepseek: false", submit_slice)
        self.assertIn("user_approved: true", submit_slice)
        self.assertNotIn("run_provider_model_now", submit_slice)
        self.assertNotIn("operator_approved", submit_slice)
        self.assertIn("quantProjectionTaskBoundary", search_panel)
        self.assertIn("输入不触发外联", self.page)
        self.assertIn("POST task / worker", search_panel)
        self.assertIn("React render 不直接外联", search_panel)
        self.assertIn("React 渲染不直连 Tushare 或 DeepSeek", self.page)


if __name__ == "__main__":
    unittest.main()
