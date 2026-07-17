from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RouteCacheLoadingBoundaryTests(unittest.TestCase):
    def test_loading_overlay_is_visible_and_accessible(self) -> None:
        source = (ROOT / "desktop/src/components/RouteCacheLoadingBoundary.tsx").read_text(encoding="utf-8")
        self.assertIn("route-cache-loading-overlay", source)
        self.assertIn('role="status"', source)
        self.assertIn('aria-live="polite"', source)

    def test_app_rejects_busy_anchor_and_observes_settled_attribute(self) -> None:
        source = (ROOT / "desktop/src/App.tsx").read_text(encoding="utf-8")
        self.assertIn("target.closest('[data-route-cache-loading=\"true\"]')", source)
        self.assertIn('attributeFilter: ["data-route-cache-loading", "data-route-cache-settled", "class", "style", "hidden", "open"]', source)
        self.assertIn("characterData: true", source)
        self.assertIn("attributes: true", source)
        self.assertIn("observerTimer = window.setTimeout(() =>", source)
        self.assertIn("ROUTE_ANCHOR_HARD_DEADLINE_MS = 25000", source)
        self.assertIn("const scheduleAnchorStabilityRetries = () =>", source)
        self.assertIn("if (anchorRetryScheduled) return", source)
        self.assertIn("stabilityWindowElapsed = true", source)
        self.assertIn("hardStopTimer = window.setTimeout(stopAnchorRetries", source)
        self.assertIn('const routeShell = target.closest("[data-route-cache-loading]")', source)
        self.assertIn('const routeSettled = routeShell?.getAttribute("data-route-cache-settled")', source)
        self.assertIn('routeSettled === "true"', source)
        self.assertIn("const runningAnimations = document.getAnimations().filter", source)
        self.assertIn("settledScrollScheduled = true", source)
        self.assertIn("Promise.allSettled(runningAnimations.map", source)
        self.assertIn("CANDIDATE_SETTLED_ANCHOR_QUIET_MS = 48", source)
        self.assertIn("CANDIDATE_SETTLED_ANCHOR_MAX_WAIT_MS = 400", source)
        self.assertIn('route !== "candidates"', source)
        self.assertIn("settledScrollQuietTimer = window.setTimeout", source)
        self.assertIn("settledScrollMaxTimer = window.setTimeout", source)
        self.assertIn("scheduleSettledAnchorScroll();\n        return;", source)
        self.assertIn("window.clearTimeout(settledScrollQuietTimer)", source)
        self.assertIn("settledScrollFrame = window.requestAnimationFrame", source)
        self.assertIn("window.cancelAnimationFrame(settledScrollFrame)", source)
        self.assertIn("if (cancelled || stopped) return", source)
        self.assertIn('stabilityWindowElapsed && routeSettled !== "false"', source)
        self.assertIn("scheduleAnchorStabilityRetries();", source)
        self.assertIn('window.addEventListener("wheel", stopAnchorRetries', source)
        self.assertIn('window.removeEventListener("wheel", stopAnchorRetries)', source)

    def test_four_cache_routes_expose_fail_closed_ready_state(self) -> None:
        routes = {
            "CommandCenterHome.tsx": "initialLayoutReady",
            "NextSessionMap.tsx": "initialLayoutReady",
            "CandidateRadar.tsx": "initialLayoutReady",
            "TaskCatalog.tsx": "initialLayoutReady",
        }
        for name, signal in routes.items():
            with self.subTest(route=name):
                source = (ROOT / "desktop/src/routes" / name).read_text(encoding="utf-8")
                self.assertIn(signal, source)
                self.assertIn("data-route-cache-loading=", source)
                self.assertIn("data-route-cache-ready=", source)
                self.assertIn("aria-busy=", source)
                self.assertIn("<RouteCacheLoadingOverlay", source)

    def test_next_and_candidate_wait_for_required_first_layout_reads(self) -> None:
        next_source = (ROOT / "desktop/src/routes/NextSessionMap.tsx").read_text(encoding="utf-8")
        self.assertIn("Promise.allSettled([refreshCache(), refreshTaskIndex()])", next_source)
        initial_effect = next_source[next_source.index("useEffect(() => {"):next_source.index("const legacy = packet")]
        self.assertNotIn("refreshCandidateRadarCache()", initial_effect)
        self.assertIn('aria-label="next session explicit candidate radar cache read"', next_source)
        self.assertIn('onClick={() => { void refreshCandidateRadarCache(); }}', next_source)
        self.assertIn('title="只读取本机 CandidateRadar cache；不创建任务、不调用外部数据或模型"', next_source)
        self.assertIn('candidateRadarDetailStatus === "loading"', next_source)
        self.assertIn('"正在读取本地上游明细；普通图谱继续使用同包交接证据。"', next_source)
        self.assertIn('candidateRadarDetailStatus === "empty"', next_source)
        self.assertIn('candidateRadarDetailStatus === "error"', next_source)
        self.assertIn('const candidateRadarCache = EMPTY_CANDIDATE_RADAR_ORDINARY_FALLBACK', next_source)
        self.assertIn('setCandidateRadarDetailCache(nextCandidateRadarCache)', next_source)
        self.assertIn('const candidateRadarDetailHasLastGood = Object.keys(candidateRadarDetailCache).length > 0', next_source)
        self.assertIn('"本地上游明细重新读取失败；已保留上次成功读取的明细，普通图谱仍使用同包交接证据。"', next_source)
        self.assertIn('"候选详情不参与普通结论；降级状态请在高级诊断按需查看"', next_source)
        self.assertIn('"GET /api/tasks + 本地次日图谱数据；CandidateRadar 完整详情仅在高级诊断按需读取"', next_source)
        self.assertIn('{candidateRadarDetailHasLastGood', next_source)
        self.assertIn('<JsonDetails title="CandidateRadar 按需本地明细" data={candidateRadarDetailCache} />', next_source)
        self.assertIn('const taskIndexConfirmedSymbol = String(taskIndex?.latest_confirmed_symbol ?? "")', next_source)
        self.assertIn('const taskIndexConfirmedTaskId = String(taskIndex?.latest_confirmed_task_id ?? "")', next_source)
        confirmed_symbol = next_source[next_source.index("const candidateRadarConfirmedSymbol"):next_source.index("const candidateRadarConfirmedSymbolLabel")]
        self.assertLess(confirmed_symbol.index("packetCandidateRadarP3HandoffSymbol"), confirmed_symbol.index("taskIndexConfirmedSymbol"))
        self.assertLess(confirmed_symbol.index("taskIndexConfirmedSymbol"), confirmed_symbol.index("candidateRadarCache.latest_confirmed_symbol"))
        candidate_source = (ROOT / "desktop/src/routes/CandidateRadar.tsx").read_text(encoding="utf-8")
        self.assertNotIn("const coreCache = refreshCache()", candidate_source)
        self.assertNotIn("void coreCache.finally", candidate_source)
        self.assertIn("initialLayoutSettled && !initialLayoutLoading && !error", candidate_source)
        self.assertIn("data-route-cache-settled={initialLayoutSettled", candidate_source)
        self.assertIn("Promise.allSettled([", candidate_source)
        for name in (
            "refreshCache()",
            "refreshBootstrapStatus()",
            "refreshDesktopPreflight()",
            "refreshTaskIndex()",
            "refreshUserRouteQaEvidence()",
            "refreshDataCapabilityCache()",
        ):
            self.assertIn(name, candidate_source)
        first_layout_settled = candidate_source.index("setInitialLayoutSettled(true)")
        first_reveal_frame = candidate_source.index("window.requestAnimationFrame", first_layout_settled)
        second_reveal_frame = candidate_source.index("window.requestAnimationFrame", first_reveal_frame + 1)
        first_layout_revealed = candidate_source.index("setInitialLayoutLoading(false)", second_reveal_frame)
        self.assertLess(first_layout_settled, first_reveal_frame)
        self.assertLess(first_reveal_frame, second_reveal_frame)
        self.assertLess(first_layout_settled, first_layout_revealed)
        self.assertIn("window.cancelAnimationFrame(revealFrameOne)", candidate_source)
        self.assertIn("window.cancelAnimationFrame(revealFrameTwo)", candidate_source)
        home_source = (ROOT / "desktop/src/routes/CommandCenterHome.tsx").read_text(encoding="utf-8")
        p0_settled = home_source.index("void Promise.allSettled(p0Jobs).then")
        secondary_start = home_source.index("secondaryTimer = window.setTimeout(startOrdinaryReadback, 650)", p0_settled)
        self.assertIn("setLoading(false)", home_source[p0_settled:secondary_start])
        self.assertIn('"home_margin_etf_receipt",', home_source)
        self.assertIn('getPacket("command_center_margin_etf_refresh_receipt")', home_source)
        self.assertIn("{ allowCacheMissing: true }", home_source)
        self.assertIn('res.error?.startsWith("cache_missing:") === true', home_source)
        self.assertIn('label === "home_margin_etf_receipt"', home_source)
        self.assertIn("res.ok === false && !allowedOptionalCacheMiss", home_source)
        self.assertIn("home-primary-status-stability-frame", home_source)
        self.assertIn("home-confirm-status-line", home_source)
        self.assertIn("home-status-metrics-stability-slot", home_source)
        self.assertIn("home-market-freshness-stability-slot", home_source)

    def test_local_api_reads_have_a_bounded_abort_timeout(self) -> None:
        source = (ROOT / "desktop/src/api/client.ts").read_text(encoding="utf-8")
        self.assertIn("LOCAL_API_FETCH_TIMEOUT_MS = 7000", source)
        self.assertIn("LOCAL_AUDIT_CACHE_FETCH_TIMEOUT_MS = 12000", source)
        self.assertIn("TAURI_GET_STARTUP_DEADLINE_MS = 25000", source)
        self.assertIn("fetchTimeoutMs = LOCAL_API_FETCH_TIMEOUT_MS", source)
        self.assertIn("const requestDeadlineAt = Date.now() +", source)
        self.assertIn("const remainingStartupMs = requestDeadlineAt - Date.now()", source)
        self.assertIn("Math.min(fetchTimeoutMs, remainingStartupMs)", source)
        self.assertIn(
            'request<Record<string, unknown>>("/api/audit/cache", undefined, LOCAL_AUDIT_CACHE_FETCH_TIMEOUT_MS)',
            source,
        )
        self.assertIn("new AbortController()", source)
        self.assertIn('new DOMException("local_api_timeout", "TimeoutError")', source)
        self.assertIn("signal: controller.signal", source)

    def test_css_keeps_hidden_content_in_flow_and_overlay_out_of_flow(self) -> None:
        source = (ROOT / "desktop/src/styles.css").read_text(encoding="utf-8")
        self.assertIn('.route-cache-loading-shell[data-route-cache-loading="true"]', source)
        self.assertIn("visibility: hidden", source)
        self.assertNotIn('.route-cache-loading-shell[data-route-cache-loading="true"] > :not(.route-cache-loading-overlay) {\n  display: none', source)
        self.assertIn(".route-cache-loading-overlay", source)
        self.assertIn("position: absolute", source)
        self.assertIn("min-height: min(720px, calc(100vh - 96px))", source)

    def test_motion_timer_and_network_gate_remain_stronger_than_ready_gate(self) -> None:
        runner = (ROOT / "scripts/motion_browser_qa_runner.mjs").read_text(encoding="utf-8")
        transition_timer = runner.index("const transitionStartedUs")
        hash_write = runner.index("window.location.hash = expected.hash", transition_timer)
        route_wait = runner.index("await page.waitForFunction", hash_write)
        layout_timer = runner.index("const motionBaseline = await page.evaluate", route_wait)
        idle = runner.index("await waitForSessionIdle(activeSession", layout_timer)
        inspect = runner.index("const inspected = await inspectPage", idle)
        screenshot = runner.index("page.screenshot", inspect)
        self.assertLess(transition_timer, hash_write)
        self.assertLess(hash_write, route_wait)
        self.assertLess(route_wait, layout_timer)
        self.assertLess(layout_timer, idle)
        self.assertLess(idle, inspect)
        self.assertLess(inspect, screenshot)
        self.assertIn("scheduleMountedRouteBaseline", runner)
        self.assertIn("requestAnimationFrame(() => requestAnimationFrame(() =>", runner)
        self.assertIn("cacheLoadingObserved", runner)
        self.assertIn("Motion layout window missed the route loading boundary", runner)
        self.assertIn("route_motion_baseline_timeout", runner)
        self.assertIn("entry.start_us >= transitionUs", runner)
        self.assertIn("entry.start_us >= motionUs", runner)
        self.assertIn("largest_motion_layout_shift_ppm: 100000", runner)
        self.assertIn("hasEffectivePaintStyle", runner)
        self.assertNotIn("anchorHit.contains(anchorElement)", runner)
        for gate in (
            "route_cache_boundary_present",
            "route_cache_ready",
            "route_cache_not_busy",
            "route_cache_shell_visible",
            "route_cache_overlay_absent",
            "route_cache_not_degraded",
            "route_cache_content_visible",
            "expected_heading_paint_visible",
            "expected_anchor_paint_visible",
            "expected_anchor_sticky_clearance",
        ):
            self.assertIn(gate, runner)
            self.assertIn(gate, (ROOT / "server/services/motion_evidence_service.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
