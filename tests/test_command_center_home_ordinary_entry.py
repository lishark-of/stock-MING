import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "desktop"


class CommandCenterHomeOrdinaryEntryTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "src" / "routes" / "CommandCenterHome.tsx").read_text(encoding="utf-8")

    def test_daily_command_center_summary_shows_user_decision_fields_first(self):
        source = self.source

        self.assertIn("<h1>今日作战台</h1>", source)
        self.assertIn("先看下一步、数据来源、缺少证据和仅供研究边界", source)
        self.assertIn('title="今日作战台摘要"', source)
        self.assertIn("下一步、来源、缺口、边界和最近可用缓存", source)
        self.assertIn('label: "下一步"', source)
        self.assertIn('label: "主下一步"', source)
        self.assertIn('label: "主下一步边界"', source)
        self.assertIn('label: "本地联通"', source)
        self.assertIn('label: "一键启动"', source)
        self.assertIn('label: "启动恢复"', source)
        self.assertIn('label: "启动边界"', source)
        self.assertIn('label: "启动成功条件"', source)
        self.assertIn('label: "启动诊断"', source)
        self.assertIn('label: "启动失败处理"', source)
        self.assertIn('label: "恢复回读"', source)
        self.assertIn('label: "回读顺序"', source)
        self.assertIn('label: "回读边界"', source)
        self.assertIn("dailyCommandStartupReadbackRows", source)
        self.assertIn('aria-label="daily command local connection readback"', source)
        self.assertIn("本地联通三段回读", source)
        self.assertIn("先看 FastAPI、bootstrap runtime-mode packet、React/Vite 前端三段是否变绿", source)
        self.assertIn('回读项: "FastAPI health"', source)
        self.assertIn('回读项: "Bootstrap status"', source)
        self.assertIn('回读项: "React/Vite 前端"', source)
        self.assertIn("Command Center 3.0 health JSON 且 external_calls_on_startup=false", source)
        self.assertIn("只读运行模式，不写配置、不创建 live_light task", source)
        self.assertIn("首页只展示预检结果，不启动 FastAPI/Vite/浏览器", source)
        self.assertIn('label: "股票量化推演"', source)
        self.assertIn('label: "下一票雷达"', source)
        self.assertIn('label: "今日查看顺序"', source)
        self.assertIn('label: "今日结果组成"', source)
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
        self.assertIn('label: "缺数据口径"', source)
        self.assertIn('label: "仅供研究"', source)
        self.assertLess(source.index("今日作战台摘要"), source.index("开发 / 审计详情"))
        self.assertLess(source.index("今日作战台摘要"), source.index("live_light bootstrap"))
        self.assertLess(source.index('label: "本地联通"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "一键启动"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "启动诊断"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "恢复回读"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "回读边界"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index("本地联通三段回读"), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "cache"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "last_successful_cache/result"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "今日查看顺序"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "今日结果组成"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertLess(source.index('label: "缺数据口径"', source.index("今日作战台摘要")), source.index("开发 / 审计详情"))
        self.assertNotIn('{ label: "今日作战台"', source)

    def test_daily_command_center_source_and_boundary_are_visible(self):
        source = self.source

        self.assertIn("dailyCommandSourceState", source)
        self.assertIn("dailyCommandConnectionState", source)
        self.assertIn("dailyCommandLauncherState", source)
        self.assertIn("dailyCommandReviewOrder", source)
        self.assertIn("dailyCommandResultComposition", source)
        self.assertIn("dailyCommandMissingDataBoundary", source)
        self.assertIn("dailyCommandPrimaryActionLabel", source)
        self.assertIn("dailyCommandPrimaryActionHref", source)
        self.assertIn("dailyCommandPrimaryActionBoundary", source)
        self.assertIn("先确认最近缓存和数据健康，再看下一票雷达，最后看股票量化推演结果", source)
        self.assertIn("先看一键启动预检恢复本地联通，再回今日作战台", source)
        self.assertIn("候选：${Number(candidateCounts?.candidate_count ?? 0) ? String(candidateCounts?.candidate_count) : \"等待缓存\"}", source)
        self.assertIn("量化：${String(factor.status ?? factor.mode ?? \"等待缓存\")}", source)
        self.assertIn("风险：${String(riskCounts?.active_risk_count ?? riskCounts?.risk_count ?? 0)} 项", source)
        self.assertIn("缺数据先看 pending / 缺少证据；不能把空缓存当成无风险", source)
        self.assertIn("不能把空缓存当成无风险，也不能当成生产验收完成", source)
        self.assertIn("今日先按“最近缓存/数据健康 → 下一票雷达 → 股票量化推演”复核", source)
        self.assertIn("不把空结果当成无风险", source)
        self.assertIn("主下一步只切换到下一票雷达；不创建 task、不刷新 provider/model", source)
        self.assertIn("主下一步只查看本地数据健康；运行快扫仍需进入下一票雷达手动点击", source)
        self.assertIn("本地前后端未联通；请使用桌面快捷方式或本地启动器重新打开", source)
        self.assertIn("本地前后端已联通", source)
        self.assertIn("一键启动入口可用；启动器会等 FastAPI 和页面 ready", source)
        self.assertIn("dailyCommandStartupSuccessCondition", source)
        self.assertIn("dailyCommandStartupFailureAction", source)
        self.assertIn("dailyCommandStartupDiagnosticSurfaces", source)
        self.assertIn("dailyCommandStartupReadbackLabel", source)
        self.assertIn("dailyCommandStartupReadbackOrder", source)
        self.assertIn("dailyCommandStartupReadbackBoundary", source)
        self.assertIn("dailyCommandStartupReadbackRows", source)
        self.assertIn("FastAPI /health 必须返回 Command Center 3.0 健康 JSON", source)
        self.assertIn("/api/bootstrap/status 必须返回 runtime-mode packet", source)
        self.assertIn("React/Vite 必须返回 Command Center 3.0 前端 HTML", source)
        self.assertIn("先看启动器的可操作诊断：FastAPI、bootstrap status、React/Vite 哪段失败", source)
        self.assertIn("8710/5173 是否被占用", source)
        self.assertIn("重启后刷新本页；FastAPI、bootstrap、React/Vite 变绿才继续投研", source)
        self.assertIn("联通已由 GET /health 回读；可继续看缓存和投研入口", source)
        self.assertIn("恢复回读顺序：FastAPI /health -> bootstrap status -> React/Vite 前端 -> 今日作战台摘要", source)
        self.assertIn("恢复回读只读取 GET /health、GET /api/bootstrap/status、GET /api/desktop/preflight-cache；不启动服务、不创建 task、不外联", source)
        self.assertIn("只读健康检查，不启动服务、不创建 task", source)
        self.assertIn("只读运行模式，不写配置、不创建 live_light task", source)
        self.assertIn("首页只展示预检结果，不启动 FastAPI/Vite/浏览器", source)
        self.assertIn("恢复回读只看本地 GET health/bootstrap/preflight 结果", source)
        self.assertIn("如果没有变绿，继续回一键启动预检，不进入投研入口", source)
        self.assertIn("FastAPI /health Command Center 3.0 JSON", source)
        self.assertIn("bootstrap status runtime-mode packet", source)
        self.assertIn("React/Vite Command Center 3.0 HTML", source)
        self.assertIn("8710/5173 port occupancy guidance", source)
        self.assertIn("启动诊断来自 desktop preflight cache", source)
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

    def test_daily_command_summary_links_are_local_navigation_only(self):
        summary_start = self.source.index('title="今日作战台摘要"')
        summary_end = self.source.index("<summary>开发 / 审计详情</summary>", summary_start)
        summary = self.source[summary_start:summary_end]

        self.assertIn('aria-label="daily command primary next action"', summary)
        self.assertIn('aria-label="open daily command primary next action"', summary)
        self.assertIn('aria-label="daily command next user actions"', summary)
        self.assertIn('href="#candidates"', summary)
        self.assertIn('href="#factor"', summary)
        self.assertIn('href="#dataHealth"', summary)
        self.assertIn('href="#desktop"', summary)
        self.assertIn("这些入口链接只切换本地页面", summary)
        self.assertIn("不会创建 task、调用 Tushare/DeepSeek/GitHub、写 cache/config 或改变交易策略", summary)
        self.assertLess(summary.index('aria-label="daily command primary next action"'), summary.index('aria-label="daily command next user actions"'))
        self.assertNotIn("onClick=", summary)
        self.assertNotIn("launchLiveBootstrap", summary)
        self.assertNotIn("postBootstrapLiveStartup", summary)

    def test_engineering_metrics_are_demoted_behind_details(self):
        source = self.source

        self.assertIn('className="developer-audit-details"', source)
        self.assertIn("开发 / 审计详情", source)
        self.assertIn("详细验收记录、开发表格和排障明细默认收起", source)
        self.assertIn("dailyCommandAuditDemotionRows", source)
        self.assertIn('aria-label="daily command engineering audit demotion rules"', source)
        self.assertIn("审计入口下沉规则", source)
        self.assertIn("普通用户先看摘要和三入口；只有排障、验收或补证时展开开发详情。", source)
        self.assertIn("不展示 raw packet、call_ledger、runbook、LTG 表或 provider/model 明细", source)
        self.assertIn("默认折叠，不压过 P0 联通、P1 搜票确认、P2/P3 结果回放", source)
        self.assertIn("手动补证状态、任务状态面板和任务回执", source)
        self.assertIn("页面打开、React render 和 GET cache 不创建 task、不调用 Tushare/DeepSeek/GitHub", source)
        self.assertNotIn("工程合同、receipt、runbook、LTG audit 和 lineage 明细默认收起", source)
        self.assertIn("开发状态速览", source)
        self.assertLess(source.index("开发 / 审计详情"), source.index("开发状态速览"))
        self.assertLess(source.index("开发 / 审计详情"), source.index("审计入口下沉规则"))
        self.assertLess(source.index("审计入口下沉规则"), source.index("开发状态速览"))
        self.assertLess(source.index("今日作战台摘要"), source.index("审计入口下沉规则"))
        self.assertLess(source.index("开发状态速览"), source.index('label: "FastAPI"'))
        self.assertLess(source.index("开发状态速览"), source.index('label: "runtime mode"'))

    def test_daily_command_summary_uses_user_facing_backfill_state_before_audit(self):
        source = self.source
        summary_start = source.index('title="今日作战台摘要"')
        summary_end = source.index("<summary>开发 / 审计详情</summary>", summary_start)
        summary = source[summary_start:summary_end]
        audit = source[summary_end:]

        self.assertIn("dailyCommandBackgroundTaskState", source)
        self.assertIn('label: "补证状态"', summary)
        self.assertNotIn('label: "后台状态"', source)
        self.assertIn("普通路径不自动补证；需要时在开发详情手动确认", source)
        self.assertIn("正在准备本地补证；页面可继续查看缓存", source)
        self.assertIn("补证未完成；已回到只读查看", source)
        self.assertIn("已有本地补证任务；进度在开发详情", source)
        self.assertIn("live_light 补证入口下沉在开发详情；普通路径只看本地缓存、雷达和量化入口", summary)
        self.assertNotIn("等待手动确认按钮", source)
        self.assertNotIn("cache_only/manual 不创建后台任务", source)
        self.assertNotIn("来源关闭，未创建后台任务", source)
        self.assertNotIn("后台任务未接入", source)
        self.assertNotIn("本会话已创建过，不重复", source)
        self.assertNotIn("正在创建本地后台 task", source)
        self.assertNotIn("创建失败，已降级为只读", source)
        self.assertNotIn("liveBootstrapAutoStatus", summary)
        self.assertIn("auto status: {liveBootstrapAutoStatus}", audit)
        self.assertLess(source.index('label: "补证状态"'), source.index("<summary>开发 / 审计详情</summary>"))

    def test_live_light_bootstrap_requires_manual_button_not_page_open_autostart(self):
        source = self.source

        self.assertIn("const launchLiveBootstrap = () => {", source)
        self.assertIn('source: "command_center_home_manual"', source)
        self.assertIn("确认 live_light 本地补证 task", source)
        self.assertIn("手动确认后才会创建本地 POST task；页面打开不自动启动", source)
        self.assertIn("页面打开、搜索输入和 render 不直接创建 task", source)
        self.assertNotIn('source: "command_center_home_auto"', source)
        self.assertNotIn("cache 渲染完成后才会在 live_light 模式创建一次本地 POST task", source)

    def test_daily_command_page_does_not_embed_provider_model_or_trade_calls(self):
        source = self.source
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
