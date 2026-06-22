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
        self.assertIn("ordinaryOptionalNextClick", self.page)
        self.assertIn("需要更新时再运行本地快扫", self.page)
        self.assertIn("搜单票时输入代码后点击生成 3.0 量化推演", self.page)
        self.assertIn("ordinaryPendingSourceLabel", self.page)
        self.assertIn("ordinaryDegradedSourceLabel", self.page)
        self.assertIn("pending：", self.page)
        self.assertIn("degraded：", self.page)
        self.assertIn("本地候选缓存可用", self.page)
        self.assertIn("手动触发或关闭", self.page)
        self.assertIn("雷达摘要只读展示候选缓存", self.page)
        self.assertIn("manual/live_light 补证必须走 POST task / worker", self.page)
        self.assertIn('aria-label="candidate radar primary next action"', self.page)
        self.assertIn('href="#candidate-pool"', self.page)
        self.assertIn('id="candidate-pool"', self.page)
        self.assertIn("候选不是买入指令；不真实交易、不下单、不改交易策略", self.page)
        self.assertIn("普通用户先看上方雷达摘要、候选池和搜票量化推演", self.page)

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
        self.assertIn("quantProjectionConfirmedSymbol", self.page)
        self.assertIn("quantProjectionSummaryGuidance", self.page)
        self.assertIn('label: "确认代码"', self.page)
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
        self.assertIn("仅输入不会创建 task，也不会调用 Tushare 或 DeepSeek", self.page)
        self.assertIn("点击确认后创建 Tushare-first POST task / worker", self.page)
        self.assertIn("DeepSeek 默认 skipped，需 governed executor 完成后再单独补", self.page)
        self.assertIn('aria-live="polite"', self.page)
        quant_projection_start = self.page.index('title="搜票量化推演"')
        self.assertLess(
            self.page.index('label: "确认代码"', quant_projection_start),
            self.page.index('label: "任务边界"', quant_projection_start),
        )
        self.assertIn("输入不触发外联；点击确认后只经 POST task / worker 后台运行", self.page)
        self.assertIn("React 渲染不直连 Tushare 或 DeepSeek", self.page)
        self.assertIn("Tushare 小全量数据写入 call_ledger", self.page)
        self.assertIn("待 governed executor / model_ledger 后再展示缓存", self.page)
        self.assertIn("DeepSeek 保持 skipped", self.page)
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
