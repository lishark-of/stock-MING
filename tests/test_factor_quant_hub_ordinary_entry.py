import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "desktop"


class FactorQuantHubOrdinaryEntryTests(unittest.TestCase):
    def test_stock_quant_projection_summary_shows_user_decision_fields_first(self):
        source = (ROOT / "src" / "routes" / "FactorQuantHub.tsx").read_text(encoding="utf-8")

        self.assertIn('title="股票量化推演"', source)
        self.assertIn("普通用户量化推演摘要", source)
        self.assertIn("下一步、来源、缺口、边界和最近可用缓存", source)
        self.assertIn('label: "下一步"', source)
        self.assertIn('label: "运行模式"', source)
        self.assertIn('label: "数据来源状态"', source)
        self.assertIn('label: "缺少证据"', source)
        self.assertIn('label: "阻断/降级"', source)
        self.assertIn('label: "最近可用缓存"', source)
        self.assertIn('label: "任务边界"', source)
        self.assertIn('label: "仅供研究"', source)
        self.assertLess(source.index("普通用户量化推演摘要"), source.index('launchTask("/api/factor-quant/run-light"'))
        self.assertLess(source.index("普通用户量化推演摘要"), source.index("高级验收任务"))
        self.assertLess(source.index("普通用户量化推演摘要"), source.index("开发 / 审计指标"))

    def test_stock_quant_projection_reads_mode_without_bootstrap_task_launcher(self):
        source = (ROOT / "src" / "routes" / "FactorQuantHub.tsx").read_text(encoding="utf-8")

        self.assertIn("getBootstrapStatus", source)
        self.assertIn("refreshBootstrapStatus", source)
        self.assertIn("runtimeModeLabel", source)
        self.assertIn("cache_only（只读缓存，不外联）", source)
        self.assertIn("manual（仅手动按钮任务）", source)
        self.assertIn("live_light（轻量后台 task 口径，仍不在渲染中外联）", source)
        self.assertIn("live_full（预留，默认关闭）", source)
        self.assertIn("本页 GET cache 只读；手动刷新、轻量推演、模型整理或 live_light 补证都必须走 POST task", source)
        self.assertNotIn("postBootstrapLiveStartup", source)
        self.assertNotIn("/api/bootstrap/live-startup", source)
        self.assertNotIn("postBootstrapProviderModelExecutionRequest", source)
        self.assertNotIn("/api/bootstrap/provider-model-execution-request", source)

    def test_engineering_details_are_demoted_behind_details_blocks(self):
        source = (ROOT / "src" / "routes" / "FactorQuantHub.tsx").read_text(encoding="utf-8")

        self.assertIn('className="developer-audit-details"', source)
        self.assertIn("高级验收任务", source)
        self.assertIn("开发 / 审计指标", source)
        self.assertIn("评分图表 lineage 审计", source)
        self.assertIn("DeepSeek 解释治理审计", source)
        self.assertIn("Provider、model、receipt、runbook、QA blocker 和 LTG 细项默认收起", source)
        self.assertLess(source.index("开发 / 审计指标"), source.index('label: "provider blockers"'))
        self.assertLess(source.index("评分图表 lineage 审计"), source.index("评分图表数据合同"))
        self.assertLess(source.index("DeepSeek 解释"), source.index("DeepSeek 解释治理审计"))


if __name__ == "__main__":
    unittest.main()
