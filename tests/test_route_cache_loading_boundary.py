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
        self.assertIn('attributeFilter: ["data-route-cache-loading", "data-route-cache-settled"]', source)
        self.assertIn("attributes: true", source)
        self.assertIn("observerTimer = window.setTimeout(stopRetryTimers", source)
        self.assertIn('routeShell?.getAttribute("data-route-cache-settled") === "false"', source)

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

    def test_next_waits_for_core_layout_and_candidate_reveals_after_core_cache(self) -> None:
        next_source = (ROOT / "desktop/src/routes/NextSessionMap.tsx").read_text(encoding="utf-8")
        self.assertIn("Promise.allSettled([refreshCache(), refreshCandidateRadarCache(), refreshTaskIndex()])", next_source)
        candidate_source = (ROOT / "desktop/src/routes/CandidateRadar.tsx").read_text(encoding="utf-8")
        self.assertIn("const coreCache = refreshCache()", candidate_source)
        self.assertIn("void coreCache.finally", candidate_source)
        self.assertIn("data-route-cache-settled={initialLayoutSettled", candidate_source)
        self.assertIn("Promise.allSettled([", candidate_source)
        for name in (
            "refreshBootstrapStatus()",
            "refreshDesktopPreflight()",
            "refreshTaskIndex()",
            "refreshUserRouteQaEvidence()",
            "refreshDataCapabilityCache()",
        ):
            self.assertIn(name, candidate_source)
        home_source = (ROOT / "desktop/src/routes/CommandCenterHome.tsx").read_text(encoding="utf-8")
        p0_settled = home_source.index("void Promise.allSettled(p0Jobs).then")
        secondary_start = home_source.index("secondaryTimer = window.setTimeout(startOrdinaryReadback, 150)", p0_settled)
        self.assertIn("setLoading(false)", home_source[p0_settled:secondary_start])
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
        timer = runner.index("const motionAuditStartedUs")
        hash_write = runner.index("window.location.hash = hash", timer)
        route_wait = runner.index("await page.waitForFunction", hash_write)
        idle = runner.index("await waitForSessionIdle(activeSession", timer)
        inspect = runner.index("const inspected = await inspectPage", idle)
        screenshot = runner.index("page.screenshot", inspect)
        self.assertLess(timer, hash_write)
        self.assertLess(hash_write, route_wait)
        self.assertLess(timer, idle)
        self.assertLess(idle, inspect)
        self.assertLess(inspect, screenshot)
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
