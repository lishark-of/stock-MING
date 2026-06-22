import unittest
from pathlib import Path


class CandidateRadarOrdinaryEntryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.page = (self.root / "desktop" / "src" / "routes" / "CandidateRadar.tsx").read_text(
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
        self.assertIn('    ? "先查看下一票候选池"', self.page)
        self.assertIn('    : "先点击运行本地快扫";', self.page)
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
        self.assertIn("searchSymbol.trim()", self.page)
        self.assertIn("quantProjectionConfirmedSymbol", self.page)
        self.assertIn('label: "确认代码"', self.page)
        self.assertIn("未确认；输入框不会创建任务", self.page)
        self.assertIn("已确认输入：${searchSymbol.trim()}", self.page)
        self.assertIn("先输入并确认股票代码，按钮启用后再点击生成 3.0 量化推演", self.page)
        self.assertIn("确认代码后点击生成 3.0 量化推演", self.page)
        self.assertIn("quantProjectionSubmitHint", self.page)
        self.assertIn("仅输入不会创建 task，也不会调用 Tushare 或 DeepSeek", self.page)
        self.assertIn("点击按钮只创建本地量化推演记录", self.page)
        self.assertIn('aria-live="polite"', self.page)
        quant_projection_start = self.page.index('title="搜票量化推演"')
        self.assertLess(
            self.page.index('label: "确认代码"', quant_projection_start),
            self.page.index('label: "任务边界"', quant_projection_start),
        )
        self.assertIn("当前只创建本地记录", self.page)
        self.assertIn("live_light 补证也必须经 POST task / worker", self.page)
        self.assertIn("不在页面渲染中直连 Tushare 或 DeepSeek", self.page)
        self.assertIn("真实补证只走后台任务血缘", self.page)
        self.assertIn("推演解释只整理已有证据；不覆盖价格、持仓、因子、操作区或交易策略", self.page)

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
