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
        self.assertIn('label: "cache"', source)
        self.assertIn('label: "Tushare"', source)
        self.assertIn('label: "DeepSeek"', source)
        self.assertIn('label: "pending"', source)
        self.assertIn('label: "degraded"', source)
        self.assertIn('label: "last_successful_cache/result"', source)
        self.assertIn('label: "雷达搜票回放"', source)
        self.assertIn('label: "回放位置"', source)
        self.assertIn('label: "数据来源状态"', source)
        self.assertIn('label: "补证方式"', source)
        self.assertIn('label: "缺少证据"', source)
        self.assertIn('label: "阻断/降级"', source)
        self.assertIn('label: "最近可用缓存"', source)
        self.assertIn('label: "任务边界"', source)
        self.assertIn('label: "仅供研究"', source)
        self.assertLess(source.index("普通用户量化推演摘要"), source.index('launchTask("/api/factor-quant/run-light"'))
        self.assertLess(source.index("普通用户量化推演摘要"), source.index("高级验收任务"))
        self.assertLess(source.index("普通用户量化推演摘要"), source.index("开发 / 审计指标"))
        self.assertLess(source.index('label: "cache"'), source.index("开发 / 审计指标"))
        self.assertLess(source.index('label: "last_successful_cache/result"'), source.index("开发 / 审计指标"))
        self.assertIn("ordinaryQuantDegradedSourceLabel", source)
        self.assertIn("degraded：未标记降级", source)
        self.assertIn("ordinaryQuantRadarHandoffState", source)
        self.assertIn("ordinaryQuantReplayLocation", source)
        self.assertIn("等待下一票雷达搜票生成本地量化推演", source)
        self.assertIn("Factor cache / Next Session preview / DeepSeek status", source)
        self.assertIn("不从本页补调 provider/model", source)
        self.assertIn("本页链接不重新触发 Tushare-first 或 DeepSeek", source)
        self.assertLess(source.index('label: "雷达搜票回放"'), source.index("高级验收任务"))

    def test_stock_quant_projection_explains_evidence_task_mode(self):
        source = (ROOT / "src" / "routes" / "FactorQuantHub.tsx").read_text(encoding="utf-8")

        self.assertIn("ordinaryQuantEvidenceTaskState", source)
        self.assertIn("等待本地缓存后再确认补证方式", source)
        self.assertIn("cache_only 只读查看，不创建补证任务", source)
        self.assertIn("manual 只允许用户按钮创建 POST task", source)
        self.assertIn("live_light 可由后台 task 补证；本页仍只读轮询缓存", source)
        self.assertIn("live_full 深度补证预留，默认关闭", source)
        self.assertLess(source.index('label: "补证方式"'), source.index("高级验收任务"))

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

    def test_stock_quant_projection_page_does_not_embed_provider_model_or_trade_calls(self):
        source = (ROOT / "src" / "routes" / "FactorQuantHub.tsx").read_text(encoding="utf-8")
        forbidden_fragments = (
            "tushare.pro_api",
            "ts.pro_api",
            "deepseek.chat",
            "api.github.com",
            "executeTrade(",
            "placeOrder(",
            "broker.submit",
            "live_order",
        )
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, source)


if __name__ == "__main__":
    unittest.main()
