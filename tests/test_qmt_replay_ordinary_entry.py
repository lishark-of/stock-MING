import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"


class QmtReplayOrdinaryEntryTests(unittest.TestCase):
    def setUp(self):
        self.page = (DESKTOP / "src" / "routes" / "QmtReplayLab.tsx").read_text(encoding="utf-8")
        self.client = (DESKTOP / "src" / "api" / "client.ts").read_text(encoding="utf-8")
        self.app = (DESKTOP / "src" / "App.tsx").read_text(encoding="utf-8")
        self.layout = (DESKTOP / "src" / "components" / "Layout.tsx").read_text(encoding="utf-8")
        self.styles = (DESKTOP / "src" / "styles.css").read_text(encoding="utf-8")
        self.runner = (ROOT / "scripts" / "qmt_replay_browser_qa_runner.mjs").read_text(encoding="utf-8")

    def test_qmt_replay_is_a_dedicated_ordinary_route(self):
        self.assertIn('const QmtReplayLab = lazy(() => import("./routes/QmtReplayLab"));', self.app)
        self.assertIn('"qmt-replay"', self.app)
        self.assertIn('"qmt-replay": QmtReplayLab', self.app)
        self.assertIn('{ key: "qmt-replay", label: "QMT 回放" }', self.layout)
        self.assertIn('"qmt-replay": { href: "#qmt-replay/qmt-replay-operator"', self.layout)
        ordinary = self.layout[self.layout.index('title: "普通入口"'):self.layout.index('title: "研究辅助"')]
        self.assertIn('key: "qmt-replay"', ordinary)
        self.assertNotIn('key: "tradeReview", label: "QMT', self.layout)

    def test_permanent_safety_boundary_is_first_screen_and_explicit(self):
        page_head = self.page.index('className="page-head"')
        safety = self.page.index('data-qmt-permanent-safety-boundary="true"')
        metrics = self.page.index("<MetricGrid")
        operator = self.page.index('id="qmt-replay-operator"')

        self.assertLess(page_head, safety)
        self.assertLess(safety, metrics)
        self.assertLess(safety, operator)
        self.assertIn("QMT未连接｜券商未连接｜无账户绑定｜无订单接口｜不会下单｜仅本地研究回放", self.page)
        self.assertIn("不会探测 QMT 进程、端口或账户", self.page)
        self.assertIn("不会连接券商、创建订单、修改持仓或改写 strategy action", self.page)
        self.assertIn('role="status"', self.page[safety - 240:safety + 240])

    def test_get_render_and_inputs_do_not_launch_tasks(self):
        effect_start = self.page.index("useEffect(() =>")
        effect_end = self.page.index("}, [refreshCache]);", effect_start)
        effect = self.page[effect_start:effect_end]
        controls_start = self.page.index('className="qmt-replay-controls"')
        controls_end = self.page.index('className="qmt-replay-confirm"', controls_start)
        controls = self.page[controls_start:controls_end]

        self.assertIn("getQmtReplayCache()", self.page)
        self.assertIn("getCandidateRadarCache()", self.page)
        self.assertIn("getNextSessionCache()", self.page)
        self.assertNotIn("postQmtLocalReplay", effect)
        self.assertIn("setScenario", controls)
        self.assertIn("setMaxFrames", controls)
        self.assertIn("setDemoLabel", controls)
        self.assertNotIn("postQmtLocalReplay", controls)
        self.assertNotIn("launchReplay", controls)
        self.assertIn("输入、选择、Tab 和页面渲染均 POST=0", self.page)

    def test_only_explicit_confirmed_launch_posts_local_replay(self):
        launch_start = self.page.index("const launchReplay = () =>")
        launch_end = self.page.index("const payloadCallLedger", launch_start)
        launch = self.page[launch_start:launch_end]

        self.assertEqual(self.page.count("postQmtLocalReplay("), 1)
        self.assertIn("if (!launchAllowed) return", launch)
        self.assertIn("approved_by_user: true", launch)
        self.assertIn('mode: "local_research_replay"', launch)
        self.assertIn("source_symbol: candidateSymbol", launch)
        self.assertIn("source_task_id: candidateTaskId", launch)
        self.assertIn("source_result_version: candidateResultVersion", launch)
        self.assertIn("source_scope_hash: candidateScopeHash", launch)
        self.assertIn("approved && lineageReady && !unsafeBoundary && !submitting", self.page)
        self.assertIn("运行本地研究回放（不连接 QMT）", self.page)
        self.assertIn('method: "POST"', self.client[self.client.index("export function postQmtLocalReplay"):])
        self.assertIn('"/api/qmt-replay/local-simulate"', self.client)

    def test_lineage_requires_candidate_and_next_session_to_match(self):
        for token in (
            "candidate_radar_v05_result_version",
            "candidate_radar_v05_scope_hash",
            "candidate_radar_v05_next_session_lineage",
            "candidate_radar_v05_lineage",
            "symbolMatches",
            "taskMatches",
            "resultVersionMatches",
            "scopeMatches",
            "qmtSourceMatches",
            "backendLineageBlocked",
        ):
            self.assertIn(token, self.page)
        self.assertIn("标的、任务、结果版本和范围全部同源", self.page)
        self.assertIn("缺口不会被解释成安全", self.page)
        self.assertIn("失败不得覆盖 last-good", self.page)

    def test_virtual_events_use_research_only_states_and_accessible_fallback(self):
        self.assertIn('type ResearchState = "observe" | "watch" | "excluded";', self.page)
        self.assertIn('new Set<ResearchState>(["observe", "watch", "excluded"])', self.page)
        self.assertIn('role="region"', self.page)
        self.assertIn("tabIndex={0}", self.page)
        self.assertIn('aria-describedby="qmt-replay-track-hint"', self.page)
        self.assertIn("下方表格提供等价文本，不依赖 hover 或颜色理解", self.page)
        self.assertIn("<DataLineageTable rows={virtualResearchEvents} />", self.page)
        self.assertIn("空结果不表示无风险", self.page)
        self.assertIn("不是订单、成交或持仓动作", self.page)
        self.assertIn("replaySummary.research_events", self.page)
        self.assertIn("event.research_state ?? event.event ?? event.state", self.page)
        self.assertIn("qmtCache.source_result_version", self.page)
        self.assertIn("qmtCache.source_scope_hash", self.page)
        self.assertIn('event: "observe"', self.runner)
        self.assertIn('research_events: events', self.runner)
        self.assertNotIn('research_state: "buy"', self.page)
        self.assertNotIn('research_state: "sell"', self.page)

    def test_styles_preserve_mobile_and_keyboard_access(self):
        for selector in (
            ".qmt-safety-boundary",
            ".qmt-replay-controls",
            ".qmt-replay-confirm",
            ".qmt-replay-track",
        ):
            self.assertIn(selector, self.styles)
        self.assertIn("a:focus-visible", self.styles)
        self.assertIn("select:focus-visible", self.styles)
        mobile = self.styles[self.styles.index("@media (max-width: 760px)"):]
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr));", mobile)
        self.assertIn(".qmt-replay-controls", mobile)
        self.assertIn("grid-template-columns: 1fr;", mobile)
        self.assertIn("body:has(.qmt-safety-boundary) .sidebar", mobile)
        self.assertIn("position: relative;", mobile)

    def test_browser_runner_stubs_backend_and_checks_exact_post_boundary(self):
        self.assertIn("command_center_3_qmt_replay_browser_qa.v1", self.runner)
        self.assertIn("installApiStubs", self.runner)
        self.assertIn("starts_no_backend: true", self.runner)
        self.assertIn('posts_after_render', self.runner)
        self.assertIn('posts_after_input_select_tab', self.runner)
        self.assertIn('postRequests.length === 1', self.runner)
        self.assertIn('postRequests[0]?.pathname === "/api/qmt-replay/local-simulate"', self.runner)
        self.assertIn('payload.approved_by_user === true', self.runner)
        self.assertIn('payload.mode === "local_research_replay"', self.runner)
        self.assertIn('reduced_motion_ready', self.runner)
        self.assertIn('horizontal_overflow_px', self.runner)
        self.assertIn('overlap_count', self.runner)
        self.assertIn('unnamed_interactive_count', self.runner)
        self.assertIn('event_states_allowed', self.runner)
        self.assertIn('QMT=false; broker=false; account=false; order_endpoint=false; orders_created=0', self.runner)


if __name__ == "__main__":
    unittest.main()
