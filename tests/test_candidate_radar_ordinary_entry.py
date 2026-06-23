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

    def test_candidate_radar_has_ordinary_user_summary_before_audit_details(self):
        self.assertIn("<h1>下一票雷达</h1>", self.page)
        self.assertIn('title="普通用户雷达摘要"', self.page)
        self.assertIn('title="下一票候选池"', self.page)
        self.assertIn('title="搜票量化推演"', self.page)
        self.assertIn("生成 3.0 量化推演", self.page)

        for required_label in (
            'label: "下一步"',
            'label: "主下一步"',
            'label: "主下一步边界"',
            'label: "候选分组"',
            'label: "扫描范围"',
            'label: "候选来源"',
            'label: "评分说明"',
            'label: "可选补证"',
            'label: "cache"',
            'label: "Tushare"',
            'label: "DeepSeek"',
            'label: "pending"',
            'label: "degraded"',
            'label: "last_successful_cache/result"',
            'label: "缺少证据"',
            'label: "阻断/降级"',
            'label: "最近可用缓存"',
            'label: "任务边界"',
            'label: "仅供研究"',
        ):
            self.assertIn(required_label, self.page)

        self.assertLess(self.page.index('title="普通用户雷达摘要"'), self.page.index("<summary>开发 / 审计指标</summary>"))
        self.assertLess(self.page.index('title="下一票候选池"'), self.page.index("<summary>扫描覆盖 / 验收审计</summary>"))
        self.assertIn('const ordinaryNextClick = Number(counts.candidate_count ?? 0)', self.page)
        self.assertIn('    ? "先查看本地候选摘要"', self.page)
        self.assertIn('    : "先点击运行本地快扫";', self.page)
        self.assertIn("ordinaryPrimaryActionLabel", self.page)
        self.assertIn("ordinaryPrimaryActionBoundary", self.page)
        self.assertIn("查看本地候选池", self.page)
        self.assertIn("主下一步只跳转本地候选池，不创建 task、不刷新外部数据或模型", self.page)
        self.assertIn("主下一步只创建按钮门控本地快扫 POST task，不直连 Tushare/DeepSeek", self.page)
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
        self.assertIn("需要更新时再运行本地快扫", self.page)
        self.assertIn("搜单票时输入代码后点击生成 3.0 量化推演", self.page)
        self.assertIn("ordinaryPendingSourceLabel", self.page)
        self.assertIn("ordinaryDegradedSourceLabel", self.page)
        self.assertIn("pending：", self.page)
        self.assertIn("degraded：", self.page)
        self.assertIn("本地候选缓存可用", self.page)
        self.assertIn("手动触发或关闭", self.page)
        self.assertIn("待 governed executor；不作为数据源或动作", self.page)
        self.assertIn("雷达摘要只读展示候选缓存", self.page)
        self.assertIn("manual/live_light 补证必须走 POST task / worker", self.page)
        self.assertIn('aria-label="candidate radar primary next action"', self.page)
        self.assertIn('href="#candidate-pool"', self.page)
        self.assertIn('id="candidate-pool"', self.page)
        self.assertIn("候选不是买入指令；不真实交易、不下单、不改交易策略", self.page)
        self.assertIn("普通用户先看上方雷达摘要、候选池和搜票量化推演", self.page)
        self.assertIn('<a href="#audit">调用审计</a>', self.page)
        self.assertIn('<a href="#settings">配置健康</a>', self.page)
        self.assertIn('id="settings" className="developer-audit-details"', self.page)
        self.assertIn('aria-label="candidate radar settings audit details"', self.page)
        self.assertIn('id="audit" className="developer-audit-details"', self.page)
        self.assertIn('aria-label="candidate radar developer audit details"', self.page)
        self.assertLess(self.page.index('title="搜票量化推演"'), self.page.index('id="settings" className="developer-audit-details"'))
        self.assertLess(self.page.index('title="搜票量化推演"'), self.page.index('id="audit" className="developer-audit-details"'))
        deepseek_label_start = self.page.index("const ordinaryDeepSeekSourceLabel")
        deepseek_label_end = self.page.index("const ordinaryProviderGapLabel", deepseek_label_start)
        deepseek_label_slice = self.page[deepseek_label_start:deepseek_label_end]
        summary_start = self.page.index('title="普通用户雷达摘要"')
        summary_end = self.page.index('title="下一票候选池"', summary_start)
        summary_slice = self.page[summary_start:summary_end]
        self.assertIn("待 governed executor；不作为数据源或动作", deepseek_label_slice)
        self.assertNotIn("轻量实时后台任务", deepseek_label_slice)
        self.assertIn('{ label: "DeepSeek", value: ordinaryDeepSeekSourceLabel }', summary_slice)
        self.assertNotIn('DeepSeek", value: bootstrapLiveLight.deepseek_on_open === true ? "轻量实时后台任务"', summary_slice)

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
        self.assertIn("quantProjectionCanLaunch", self.page)
        self.assertIn("quantProjectionConfirmedSymbol", self.page)
        self.assertIn("quantProjectionSummaryGuidance", self.page)
        self.assertIn("quantProjectionConfirmChainState", self.page)
        self.assertIn('label: "确认代码"', self.page)
        self.assertIn('label: "确认链路"', self.page)
        self.assertIn("未确认；输入框不会创建任务", self.page)
        self.assertIn("已确认输入：${quantProjectionSymbolValidation.normalized}", self.page)
        self.assertIn("摘要搜票已确认 ${quantProjectionSymbolValidation.normalized}", self.page)
        self.assertIn("下一步点击“确认并生成 3.0 量化推演”，创建 Tushare-first 按钮门控 POST task，DeepSeek skipped", self.page)
        self.assertIn("摘要搜票暂未通过本地校验：${quantProjectionSymbolValidation.reason}；不会创建 task", self.page)
        self.assertIn("摘要搜票等待输入代码；输入框只做本地校验，不创建 task", self.page)
        self.assertIn("请输入 6 位 A 股代码或 002008.SZ 这类后缀", self.page)
        self.assertIn("本地确认代码：${quantProjectionSymbolValidation.normalized}", self.page)
        self.assertIn("本地格式阻断：${quantProjectionSymbolValidation.reason}", self.page)
        self.assertIn("先输入并确认股票代码，按钮启用后再点击生成 3.0 量化推演", self.page)
        self.assertIn("确认代码后点击生成 3.0 量化推演", self.page)
        self.assertIn("quantProjectionSubmitHint", self.page)
        self.assertIn("任务提交中：正在创建 Tushare-first POST task", self.page)
        self.assertIn("正在提交 Tushare-first 后台任务；请等待本地 task id", self.page)
        self.assertIn("确认任务正在提交：按钮已暂时禁用", self.page)
        self.assertIn("disabled={!quantProjectionCanLaunch}", self.page)
        self.assertIn('{quantProjectionSubmitting ? "提交中..." : "确认并生成 3.0 量化推演"}', self.page)
        self.assertIn("仅输入不会创建 task，也不会调用 Tushare 或 DeepSeek", self.page)
        self.assertIn("点击确认后提交 Tushare-first 后台链", self.page)
        self.assertIn("服务端凭据缺失时只写本地阻断", self.page)
        self.assertIn("确认任务已接收：先看 TaskStatusPanel，再通过 GET cache 回放 Tushare ledger、量化推演和次日图谱", self.page)
        self.assertIn("凭据可用才写 provider ledger，凭据缺失只写本地阻断；DeepSeek skipped", self.page)
        self.assertIn("quantProjectionPersistedTaskId", self.page)
        self.assertIn("quantProjectionPersistedTaskStep", self.page)
        self.assertIn("quantProjectionTaskReadbackState", self.page)
        self.assertIn("quantProjectionTaskCacheReadbackRows", self.page)
        self.assertIn("ordinary_task_readback_rows", self.page)
        self.assertIn("quantProjectionOrdinaryResultRows", self.page)
        self.assertIn("ordinary_result_readback_rows", self.page)
        self.assertIn('label: "确认状态"', self.page)
        self.assertIn('label: "安全边界"', self.page)
        self.assertIn("不交易、不改 strategy action；DeepSeek 等 governed executor", self.page)
        self.assertIn("任务回放：${quantProjectionPersistedTaskId} /", self.page)
        self.assertIn("cache 回放", self.page)
        self.assertIn('label: "任务回放"', self.page)
        self.assertIn("quantProjectionConfirmHandoffRows", self.page)
        self.assertIn('aria-label="quant projection ordinary confirmation handoff"', self.page)
        self.assertIn("确认后链路回放：输入只校验；点击确认才创建 Tushare-first 后台任务；结果只从本地 cache / ledger / packet 回放。", self.page)
        self.assertIn('步骤: "输入校验"', self.page)
        self.assertIn('步骤: "点击确认"', self.page)
        self.assertIn('步骤: "Tushare 写入"', self.page)
        self.assertIn('步骤: "结果回放"', self.page)
        self.assertIn("搜索输入、React render、GET cache 不外联", self.page)
        self.assertIn("只有用户确认后才进入后台链", self.page)
        self.assertIn("凭据缺失只写本地阻断，不补调 DeepSeek", self.page)
        self.assertIn("不交易、不改 strategy action", self.page)
        self.assertIn('aria-label="quant projection task cache packet readback"', self.page)
        self.assertIn("任务回放清单", self.page)
        self.assertIn("任务编号和安全步骤优先从本地 cache / packet 回放", self.page)
        self.assertIn("TaskStatusPanel 只轮询本地 FastAPI 任务状态", self.page)
        self.assertIn('回放项: "task_id"', self.page)
        self.assertIn('回放项: "current_step"', self.page)
        self.assertIn('回放项: "TaskStatusPanel"', self.page)
        self.assertIn("GET cache 只读回放 task id，不创建 task、不补调 provider/model", self.page)
        self.assertIn("只展示 safe current_step；不展示 raw log、token/key 或 provider error", self.page)
        self.assertIn("轮询本地任务状态，不调用 Tushare/DeepSeek/GitHub、不写交易动作", self.page)
        self.assertIn('aria-label="quant projection ordinary explainable result readback"', self.page)
        self.assertIn("解释结果清单", self.page)
        self.assertIn("普通入口只回放数据来源、量化推演、次日图谱和安全边界", self.page)
        self.assertIn("原始 receipt、prompt 或审计字段仍下沉在详情中", self.page)
        self.assertIn('回放项: "数据来源"', self.page)
        self.assertIn('回放项: "量化推演"', self.page)
        self.assertIn('回放项: "次日图谱"', self.page)
        self.assertIn('回放项: "安全边界"', self.page)
        self.assertIn("GET cache 只读回放已有账本；不补调 Tushare、DeepSeek 或 worker", self.page)
        self.assertIn("次日图谱只读回放本地 cache；缺口只作为待补证据，不创建交易动作", self.page)
        self.assertIn("DeepSeek 未参与；候选雷达不是买入指令；真实交易路径隔离", self.page)
        self.assertIn('aria-label="quant projection replay destinations"', self.page)
        self.assertIn('href="#factor" aria-label="replay generated stock quant projection"', self.page)
        self.assertIn('href="#next" aria-label="replay generated next session map"', self.page)
        self.assertIn("回放股票量化推演", self.page)
        self.assertIn("回放次日图谱", self.page)
        self.assertIn('aria-label="quant projection advanced status readback"', self.page)
        self.assertIn("<summary>高级状态回放</summary>", self.page)
        quant_projection_start = self.page.index('title="搜票量化推演"')
        compact_confirm_index = self.page.index('label: "确认状态"', quant_projection_start)
        ordinary_result_index = self.page.index('aria-label="quant projection ordinary explainable result readback"', quant_projection_start)
        replay_destinations_index = self.page.index('aria-label="quant projection replay destinations"', quant_projection_start)
        task_readback_index = self.page.index('aria-label="quant projection task cache packet readback"', quant_projection_start)
        advanced_index = self.page.index("<summary>高级状态回放</summary>", quant_projection_start)
        provider_replay_index = self.page.index('aria-label="quant projection tushare light api replay"', quant_projection_start)
        record_details_index = self.page.index("<summary>搜票推演记录详情</summary>", quant_projection_start)
        self.assertLess(compact_confirm_index, advanced_index)
        self.assertLess(ordinary_result_index, replay_destinations_index)
        self.assertLess(replay_destinations_index, task_readback_index)
        self.assertLess(task_readback_index, advanced_index)
        self.assertLess(advanced_index, provider_replay_index)
        self.assertLess(provider_replay_index, record_details_index)
        self.assertIn("页面刷新后，最近任务会优先从本地 cache / packet 回放 task id 和安全 current_step", self.page)
        self.assertIn("GET cache 不会因此补调 provider", self.page)
        self.assertIn("确认按钮只提交后台链路", self.page)
        self.assertIn("服务端凭据可用才写入 Tushare call_ledger / cache / packet", self.page)
        self.assertIn("GET cache 和 React render 不补调 provider", self.page)
        self.assertIn("DeepSeek 默认 skipped，需 governed executor 完成后再单独补", self.page)
        self.assertIn('aria-live="polite"', self.page)
        self.assertLess(
            self.page.index('label: "确认代码"', quant_projection_start),
            self.page.index('label: "任务边界"', quant_projection_start),
        )
        self.assertIn("输入不触发外联；点击确认后只经 POST task / worker 后台运行", self.page)
        self.assertIn("React 渲染不直连 Tushare 或 DeepSeek", self.page)
        self.assertIn("Tushare 小全量数据写入 call_ledger", self.page)
        self.assertIn("待 governed executor / model_ledger 后再展示缓存", self.page)
        self.assertIn("DeepSeek 保持 skipped", self.page)
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

    def test_ordinary_quant_projection_submit_does_not_auto_chain_provider_model(self):
        submit_start = self.page.index("const launchQuantProjection = () =>")
        submit_end = self.page.index("const launchQuantProjectionAcceptanceDryRun = () =>", submit_start)
        submit_slice = self.page[submit_start:submit_end]
        summary_start = self.page.index('title="普通用户雷达摘要"')
        summary_end = self.page.index('title="下一票候选池"', summary_start)
        summary_slice = self.page[summary_start:summary_end]

        self.assertIn("postCandidateRadarQuantProjection({", submit_slice)
        self.assertIn('scan_mode: "search_quant_projection"', submit_slice)
        self.assertIn("symbol: normalizeAshareSymbolInput(searchSymbol).normalized", submit_slice)
        self.assertIn("include_tushare: true", submit_slice)
        self.assertIn("include_deepseek: false", submit_slice)
        self.assertIn("user_approved: true", submit_slice)
        self.assertIn('requested_by: "candidate_radar_page"', submit_slice)
        self.assertNotIn("run_provider_model_now", submit_slice)
        self.assertNotIn("operator_approved", submit_slice)
        self.assertNotIn("quant-projection-provider-model-acceptance", submit_slice)

        self.assertIn("查看本地缓存", summary_slice)
        self.assertIn("运行本地快扫", summary_slice)
        self.assertIn("确认并生成 3.0 量化推演", summary_slice)
        self.assertIn("disabled={!quantProjectionCanLaunch}", summary_slice)
        self.assertIn('{quantProjectionSubmitting ? "提交中..." : "确认并生成 3.0 量化推演"}', summary_slice)
        self.assertIn('href="#factor"', summary_slice)
        self.assertIn("{quantProjectionSummaryGuidance}", summary_slice)
        self.assertIn('aria-live="polite"', summary_slice)
        self.assertIn('aria-label="candidate radar primary next action"', summary_slice)
        self.assertIn('aria-label="candidate radar next user actions"', summary_slice)
        self.assertLess(summary_slice.index('aria-label="candidate radar primary next action"'), summary_slice.index('aria-label="candidate radar next user actions"'))
        self.assertLess(summary_slice.index('aria-label="candidate radar next user actions"'), summary_slice.index("{quantProjectionSummaryGuidance}"))
        self.assertNotIn("launchQuantProjectionAcceptanceDryRun", summary_slice)
        self.assertNotIn("launchQuantProjectionExecutionRequest", summary_slice)
        self.assertNotIn("launchProviderParityDryRun", summary_slice)
        self.assertNotIn("provider-model", summary_slice)

    def test_tushare_first_handoff_matches_ordinary_submit_boundary(self):
        self.assertIn("Candidate Radar searched-symbol confirmation must be reported through the active checkpoint", self.handoff)
        self.assertIn("confirmed search may submit bounded Tushare provider work through POST task and call ledger", self.handoff)
        self.assertIn("ordinary confirm action may create the Tushare-first backend task chain", self.handoff)
        self.assertIn("keeps DeepSeek skipped", self.handoff)
        self.assertIn("does not require the old `run_provider_model_now` switch", self.handoff)
        self.assertIn("page open, search typing, React render, and GET cache stay silent", self.handoff)
        self.assertNotIn("DeepSeek is requested into the explanation ledger/governance path", self.handoff)
        self.assertNotIn("automatic v4/pro execution", self.handoff)

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
