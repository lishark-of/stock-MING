import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "desktop"


class CommandCenterHomeOrdinaryEntryTests(unittest.TestCase):
    def test_daily_command_center_summary_shows_user_decision_fields_first(self):
        source = (ROOT / "src" / "routes" / "CommandCenterHome.tsx").read_text(encoding="utf-8")

        self.assertIn("<h1>今日作战台</h1>", source)
        self.assertIn("先看下一步、数据来源、缺少证据和仅供研究边界", source)
        self.assertIn('title="今日作战台摘要"', source)
        self.assertIn("下一步、来源、缺口、边界和最近可用缓存", source)
        self.assertIn('label: "下一步"', source)
        self.assertIn('label: "数据来源"', source)
        self.assertIn('label: "缺少证据"', source)
        self.assertIn('label: "阻断/降级"', source)
        self.assertIn('label: "最近可用缓存"', source)
        self.assertIn('label: "任务边界"', source)
        self.assertIn('label: "仅供研究"', source)
        self.assertLess(source.index("今日作战台摘要"), source.index("开发 / 审计详情"))
        self.assertLess(source.index("今日作战台摘要"), source.index("live_light bootstrap"))

    def test_daily_command_center_source_and_boundary_are_visible(self):
        source = (ROOT / "src" / "routes" / "CommandCenterHome.tsx").read_text(encoding="utf-8")

        self.assertIn("dailyCommandSourceState", source)
        self.assertIn("本地缓存：${dailyCommandCacheSourceLabel}", source)
        self.assertIn("Tushare 数据：${dailyCommandTushareSourceLabel}", source)
        self.assertIn("DeepSeek 解释：${dailyCommandDeepSeekSourceLabel}", source)
        self.assertIn("运行模式：${dailyCommandRuntimeModeLabel}", source)
        self.assertIn("首页 GET cache 只读；live_light 只允许创建后台 POST task", source)
        self.assertIn("不在 React 渲染中直连 Tushare 或 DeepSeek", source)
        self.assertIn("今日摘要只组织投研证据；不买卖、不下单、不改交易策略", source)
        self.assertNotIn("/api/bootstrap/provider-model-execution-request", source)
        self.assertNotIn("postBootstrapProviderModelExecutionRequest", source)

    def test_engineering_metrics_are_demoted_behind_details(self):
        source = (ROOT / "src" / "routes" / "CommandCenterHome.tsx").read_text(encoding="utf-8")

        self.assertIn('className="developer-audit-details"', source)
        self.assertIn("开发 / 审计详情", source)
        self.assertIn("工程合同、receipt、runbook、LTG audit 和 lineage 明细默认收起", source)
        self.assertIn("开发状态速览", source)
        self.assertLess(source.index("开发 / 审计详情"), source.index("开发状态速览"))
        self.assertLess(source.index("开发状态速览"), source.index('label: "FastAPI"'))
        self.assertLess(source.index("开发状态速览"), source.index('label: "runtime mode"'))


if __name__ == "__main__":
    unittest.main()
