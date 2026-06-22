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
        self.assertIn('label: "本地联通"', source)
        self.assertIn('label: "一键启动"', source)
        self.assertIn('label: "cache"', source)
        self.assertIn('label: "Tushare"', source)
        self.assertIn('label: "DeepSeek"', source)
        self.assertIn('label: "pending"', source)
        self.assertIn('label: "degraded"', source)
        self.assertIn('label: "last_successful_cache/result"', source)
        self.assertIn('label: "数据来源"', source)
        self.assertIn('label: "缺少证据"', source)
        self.assertIn('label: "阻断/降级"', source)
        self.assertIn('label: "最近可用缓存"', source)
        self.assertIn('label: "任务边界"', source)
        self.assertIn('label: "仅供研究"', source)
        self.assertLess(source.index("今日作战台摘要"), source.index("开发 / 审计详情"))
        self.assertLess(source.index("今日作战台摘要"), source.index("live_light bootstrap"))
        self.assertLess(source.index('label: "本地联通"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "一键启动"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "cache"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "last_successful_cache/result"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))

    def test_daily_command_center_source_and_boundary_are_visible(self):
        source = (ROOT / "src" / "routes" / "CommandCenterHome.tsx").read_text(encoding="utf-8")

        self.assertIn("dailyCommandSourceState", source)
        self.assertIn("dailyCommandConnectionState", source)
        self.assertIn("dailyCommandLauncherState", source)
        self.assertIn("本地前后端未联通；请使用桌面快捷方式或本地启动器重新打开", source)
        self.assertIn("本地前后端已联通", source)
        self.assertIn("一键启动入口可用；启动器会等 FastAPI 和页面 ready", source)
        self.assertIn("本地联通状态只读来自 FastAPI health 和 desktop preflight cache", source)
        self.assertIn("不会启动服务、不会写配置、不会调用 provider/model", source)
        self.assertIn("本地缓存：${dailyCommandCacheSourceLabel}", source)
        self.assertIn("Tushare 数据：${dailyCommandTushareSourceLabel}", source)
        self.assertIn("DeepSeek 解释：${dailyCommandDeepSeekSourceLabel}", source)
        self.assertIn("运行模式：${dailyCommandRuntimeModeLabel}", source)
        self.assertIn("dailyCommandPendingSourceLabel", source)
        self.assertIn("dailyCommandDegradedSourceLabel", source)
        self.assertIn("pending：", source)
        self.assertIn("degraded：未标记降级", source)
        self.assertIn("首页 GET cache 只读；live_light 只允许创建后台 POST task", source)
        self.assertIn("不在 React 渲染中直连 Tushare 或 DeepSeek", source)
        self.assertIn("今日摘要只组织投研证据；不买卖、不下单、不改交易策略", source)
        self.assertNotIn("/api/bootstrap/provider-model-execution-request", source)
        self.assertNotIn("postBootstrapProviderModelExecutionRequest", source)

    def test_engineering_metrics_are_demoted_behind_details(self):
        source = (ROOT / "src" / "routes" / "CommandCenterHome.tsx").read_text(encoding="utf-8")

        self.assertIn('className="developer-audit-details"', source)
        self.assertIn("开发 / 审计详情", source)
        self.assertIn("详细验收记录、开发表格和排障明细默认收起", source)
        self.assertNotIn("工程合同、receipt、runbook、LTG audit 和 lineage 明细默认收起", source)
        self.assertIn("开发状态速览", source)
        self.assertLess(source.index("开发 / 审计详情"), source.index("开发状态速览"))
        self.assertLess(source.index("开发状态速览"), source.index('label: "FastAPI"'))
        self.assertLess(source.index("开发状态速览"), source.index('label: "runtime mode"'))

    def test_daily_command_summary_shows_background_task_state_before_audit(self):
        source = (ROOT / "src" / "routes" / "CommandCenterHome.tsx").read_text(encoding="utf-8")

        self.assertIn("dailyCommandBackgroundTaskState", source)
        self.assertIn('label: "后台状态"', source)
        self.assertIn("等待手动确认按钮", source)
        self.assertIn("cache_only/manual 不创建后台任务", source)
        self.assertIn("来源关闭，未创建后台任务", source)
        self.assertIn("后台任务未接入", source)
        self.assertIn("本会话已创建过，不重复", source)
        self.assertIn("正在创建本地后台 task", source)
        self.assertIn("创建失败，已降级为只读", source)
        self.assertLess(source.index('label: "后台状态"'), source.index("<summary>开发 / 审计详情</summary>"))

    def test_live_light_bootstrap_requires_manual_button_not_page_open_autostart(self):
        source = (ROOT / "src" / "routes" / "CommandCenterHome.tsx").read_text(encoding="utf-8")

        self.assertIn("const launchLiveBootstrap = () => {", source)
        self.assertIn('source: "command_center_home_manual"', source)
        self.assertIn("确认 live_light 本地补证 task", source)
        self.assertIn("手动确认后才会创建本地 POST task；页面打开不自动启动", source)
        self.assertIn("页面打开、搜索输入和 render 不直接创建 task", source)
        self.assertNotIn('source: "command_center_home_auto"', source)
        self.assertNotIn("cache 渲染完成后才会在 live_light 模式创建一次本地 POST task", source)

    def test_daily_command_page_does_not_embed_provider_model_or_trade_calls(self):
        source = (ROOT / "src" / "routes" / "CommandCenterHome.tsx").read_text(encoding="utf-8")
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
