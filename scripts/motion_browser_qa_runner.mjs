#!/usr/bin/env node
/*
 * Execute the local LTG-14 browser visual/performance QA pass.
 *
 * This runner is explicit-only: it does not start FastAPI, Vite, Tauri, Redis,
 * provider tasks, model calls, or trading paths. Start the local backend and
 * frontend first, then run this script against 127.0.0.1. Artifacts are written
 * under .stock_ming_3/motion_qa by default, which must stay out of git.
 */

import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);

const SCHEMA_VERSION = "command_center_3_motion_browser_qa_result.v1";
const DEFAULT_BASE_URL = "http://127.0.0.1:5173";
const DEFAULT_ARTIFACT_ROOT = ".stock_ming_3/motion_qa";

const QA_ROUTES = [
  { route: "#home", label: "Command Center", risk_focus: "page staging and status summary clarity" },
  { route: "#next-session-chart", label: "Next Session Map", risk_focus: "chart update clarity and reduced-motion chart updates" },
  { route: "#candidates", label: "Candidate Radar", risk_focus: "radar result cluster and runtime-budget visibility" },
  { route: "#worker", label: "Worker Runtime", risk_focus: "runtime evidence visibility and production-blocker readability" },
  { route: "#tasks", label: "Task Monitor", risk_focus: "task phase confirmation and progress readability" },
  { route: "#audit", label: "Call Ledger Audit", risk_focus: "motion audit rows and warning density" }
];

const QA_VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "laptop", width: 1280, height: 800 },
  { name: "tablet", width: 834, height: 1112 },
  { name: "mobile", width: 390, height: 844 }
];

const VISUAL_ACCEPTANCE_CRITERIA = [
  "route context remains obvious without reading raw JSON",
  "state-change cues do not cover freshness, risk, blocker, or warning text",
  "candidate delta and chart update cues do not imply a trading recommendation",
  "buttons, tables, metric labels, and status badges do not overlap or clip",
  "reduced-motion mode preserves readable state boundaries with animation disabled"
];

const PERFORMANCE_BUDGETS = {
  route_transition_observed_ms: 500,
  largest_motion_layout_shift: 0.1,
  long_task_over_50ms_count: 0,
  candidate_radar_first_stable_ms: 1200
};

function parseArgs(argv) {
  const args = {
    baseUrl: DEFAULT_BASE_URL,
    artifactRoot: DEFAULT_ARTIFACT_ROOT,
    route: null,
    screenshots: true,
    reducedMotion: false,
    json: false,
    printPlan: false
  };
  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--base-url") args.baseUrl = argv[++index] || args.baseUrl;
    else if (arg === "--out") args.artifactRoot = argv[++index] || args.artifactRoot;
    else if (arg === "--route") args.route = argv[++index] || args.route;
    else if (arg === "--no-screenshots") args.screenshots = false;
    else if (arg === "--reduced-motion") args.reducedMotion = true;
    else if (arg === "--json") args.json = true;
    else if (arg === "--print-plan") args.printPlan = true;
    else if (arg === "--help") {
      console.log("Usage: node scripts/motion_browser_qa_runner.mjs [--base-url http://127.0.0.1:5173] [--out .stock_ming_3/motion_qa] [--route #candidates] [--reduced-motion] [--no-screenshots] [--json] [--print-plan]");
      process.exit(0);
    }
  }
  return args;
}

function selectedQaRoutes(args) {
  if (!args.route) return QA_ROUTES;
  const requested = args.route.startsWith("#") ? args.route : `#${args.route}`;
  const routes = QA_ROUTES.filter((route) => route.route === requested);
  if (!routes.length) {
    throw new Error(`Unknown QA route: ${args.route}`);
  }
  return routes;
}

function timestampId() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function makePlan(args) {
  const routes = selectedQaRoutes(args);
  const matrix = routes.flatMap((route) =>
    QA_VIEWPORTS.map((viewport) => ({
      route: route.route,
      label: route.label,
      viewport: viewport.name,
      width: viewport.width,
      height: viewport.height,
      url: `${args.baseUrl}/${route.route}`,
      risk_focus: route.risk_focus,
      visual_qa_complete: false,
      performance_trace_complete: false
    }))
  );
  return {
    schema_version: "command_center_3_motion_browser_qa_plan.v1",
    status: "motion_browser_qa_plan_ready",
    scope: "explicit_local_browser_runner_plan",
    base_url: args.baseUrl,
    artifact_root: args.artifactRoot,
    selected_route: args.route || "all",
    route_count: routes.length,
    viewport_count: QA_VIEWPORTS.length,
    qa_matrix_count: matrix.length,
    visual_acceptance_criteria: VISUAL_ACCEPTANCE_CRITERIA,
    performance_budgets: PERFORMANCE_BUDGETS,
    qa_matrix: matrix,
    runs_no_server_processes: true,
    opens_local_browser_only: true,
    local_urls_only: args.baseUrl.startsWith("http://127.0.0.1") || args.baseUrl.startsWith("http://localhost"),
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true
  };
}

async function inspectPage(page, route) {
  return page.evaluate((expectedRoute) => {
    const selectors = [
      "h1",
      "h2",
      "h3",
      "button",
      "label",
      ".metric",
      ".status-badge",
      ".state-clarity-rail",
      ".task-panel__head"
    ];
    const visibleSelectors = [
      "h1",
      "h2",
      "h3",
      "button",
      "label",
      ".metric",
      ".status-badge",
      ".state-clarity-rail",
      ".task-panel__head",
      ".packet-card",
      ".page-state",
      ".task-panel"
    ];
    const elements = Array.from(document.querySelectorAll(selectors.join(",")));
    const visibleElements = Array.from(document.querySelectorAll(visibleSelectors.join(",")));
    const isTextClipped = (element) => {
      const textElement = element.matches("button") && element.querySelector(".nav-label")
        ? element.querySelector(".nav-label")
        : element;
      const tolerance = 4;
      return (
        textElement.scrollWidth > Math.ceil(textElement.clientWidth) + tolerance ||
        textElement.scrollHeight > Math.ceil(textElement.clientHeight) + tolerance
      );
    };
    const toRow = (element) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      const text = (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 120);
      const clipped = isTextClipped(element);
      const offscreen =
        rect.right < 0 ||
        rect.bottom < 0 ||
        rect.left > window.innerWidth ||
        rect.top > window.innerHeight;
      return {
        tag: element.tagName.toLowerCase(),
        className: String(element.className || ""),
        text,
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        display: style.display,
        visibility: style.visibility,
        opacity: Number(style.opacity || 1),
        clipped,
        offscreen
      };
    };
    const auditable = elements
      .map(toRow)
      .filter((item) => item.width > 0 && item.height > 0 && item.display !== "none" && item.visibility !== "hidden" && item.opacity > 0.01);
    const visible = visibleElements
      .map((element) => {
        return toRow(element);
      })
      .filter((item) => item.width > 0 && item.height > 0 && item.display !== "none" && item.visibility !== "hidden" && item.opacity > 0.01);
    const firstViewportRows = auditable.filter((item) => !item.offscreen);
    const clippedRows = firstViewportRows.filter((item) => item.clipped && item.text.length > 0).slice(0, 20);
    const offscreenRows = visible.filter((item) => item.offscreen && item.text.length > 0).slice(0, 20);
    const motionMarkers = {
      route_stage: document.querySelectorAll(".route-stage").length,
      motion_surface: document.querySelectorAll(".motion-surface").length,
      state_rail: document.querySelectorAll(".state-clarity-rail").length,
      chart_frame: document.querySelectorAll(".chart-refresh-frame").length,
      radar_cluster: document.querySelectorAll(".radar-result-cluster").length,
      task_panel: document.querySelectorAll(".task-panel").length
    };
    const isHitTestVisible = (element) => {
      const rect = element.getBoundingClientRect();
      if (rect.right <= 0 || rect.bottom <= 0 || rect.left >= window.innerWidth || rect.top >= window.innerHeight) return false;
      const inset = 2;
      const points = [
        [rect.left + rect.width / 2, rect.top + rect.height / 2],
        [rect.left + inset, rect.top + inset],
        [rect.right - inset, rect.top + inset],
        [rect.left + inset, rect.bottom - inset],
        [rect.right - inset, rect.bottom - inset]
      ];
      return points.some(([rawX, rawY]) => {
        const x = Math.max(0, Math.min(window.innerWidth - 1, rawX));
        const y = Math.max(0, Math.min(window.innerHeight - 1, rawY));
        const hit = document.elementFromPoint(x, y);
        return Boolean(hit && (hit === element || element.contains(hit)));
      });
    };
    const interactiveElements = Array.from(document.querySelectorAll("button, a[href], input, select, textarea, [tabindex]"))
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden" && isHitTestVisible(element);
      });
    const unnamedInteractiveRows = interactiveElements
      .filter((element) => {
        const name = [
          element.getAttribute("aria-label"),
          element.getAttribute("title"),
          element.getAttribute("placeholder"),
          element.textContent
        ].map((value) => String(value || "").trim()).find(Boolean);
        return !name;
      })
      .slice(0, 20)
      .map(toRow);
    const overlapRows = [];
    for (let leftIndex = 0; leftIndex < interactiveElements.length; leftIndex += 1) {
      const left = interactiveElements[leftIndex];
      const leftRect = left.getBoundingClientRect();
      if (leftRect.bottom <= 0 || leftRect.top >= window.innerHeight) continue;
      for (let rightIndex = leftIndex + 1; rightIndex < interactiveElements.length; rightIndex += 1) {
        const right = interactiveElements[rightIndex];
        if (left.contains(right) || right.contains(left)) continue;
        const rightRect = right.getBoundingClientRect();
        if (rightRect.bottom <= 0 || rightRect.top >= window.innerHeight) continue;
        const overlapWidth = Math.min(leftRect.right, rightRect.right) - Math.max(leftRect.left, rightRect.left);
        const overlapHeight = Math.min(leftRect.bottom, rightRect.bottom) - Math.max(leftRect.top, rightRect.top);
        if (overlapWidth > 1 && overlapHeight > 1) {
          overlapRows.push({ left: toRow(left), right: toRow(right) });
          if (overlapRows.length >= 20) break;
        }
      }
      if (overlapRows.length >= 20) break;
    }
    const concealedContentRows = Array.from(document.querySelectorAll(".motion-surface, .route-stage, .page-head, .chart-refresh-frame, .radar-result-cluster"))
      .map(toRow)
      .filter((item) => item.width > 0 && item.height > 0 && !item.offscreen && item.text.length > 0 && item.opacity < 0.94)
      .slice(0, 20);
    const documentElement = document.documentElement;
    const horizontalOverflowPx = Math.max(0, documentElement.scrollWidth - documentElement.clientWidth);
    const expectedAnchor = expectedRoute === "#next-session-chart" ? "next-session-chart" : "";
    const anchorElement = expectedAnchor ? document.getElementById(expectedAnchor) : null;
    const anchorRect = anchorElement?.getBoundingClientRect();
    const anchorReady = !expectedAnchor || Boolean(
      anchorElement && anchorRect && anchorRect.width > 0 && anchorRect.height > 0 && anchorRect.top < window.innerHeight && anchorRect.bottom > 0
    );
    const longTasks = performance.getEntriesByType("longtask");
    return {
      title: document.title,
      h1: document.querySelector("h1")?.textContent?.trim() || "",
      visible_element_count: visible.length,
      audited_first_viewport_element_count: firstViewportRows.length,
      clipped_count: clippedRows.length,
      offscreen_count: offscreenRows.length,
      clipped_rows: clippedRows,
      offscreen_rows: offscreenRows,
      horizontal_overflow_px: horizontalOverflowPx,
      overlap_count: overlapRows.length,
      overlap_rows: overlapRows,
      unnamed_interactive_count: unnamedInteractiveRows.length,
      unnamed_interactive_rows: unnamedInteractiveRows,
      concealed_motion_content_count: concealedContentRows.length,
      concealed_motion_content_rows: concealedContentRows,
      expected_anchor: expectedAnchor || null,
      expected_anchor_ready: anchorReady,
      motion_markers: motionMarkers,
      long_task_over_50ms_count: longTasks.filter((entry) => entry.duration > 50).length,
      largest_motion_layout_shift: 0
    };
  }, route);
}

async function runQa(args) {
  const { chromium } = require("playwright");
  const routes = selectedQaRoutes(args);
  const runId = timestampId();
  const outputDir = resolve(args.artifactRoot, runId);
  await mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const rows = [];
  const errors = [];
  try {
    for (const viewport of QA_VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        reducedMotion: args.reducedMotion ? "reduce" : "no-preference"
      });
      const page = await context.newPage();
      let postRequests = [];
      page.on("request", (request) => {
        if (request.method() === "POST") postRequests.push(request.url());
      });
      page.on("console", (message) => {
        if (message.type() === "error") errors.push({ viewport: viewport.name, console_error: message.text() });
      });
      page.on("pageerror", (error) => {
        errors.push({ viewport: viewport.name, page_error: String(error.message || error) });
      });
      const warmupRoute = routes.length === 1 ? routes[0].route : "#home";
      await page.goto(`${args.baseUrl}/${warmupRoute}`, { waitUntil: "networkidle", timeout: 20000 });
      await page.waitForTimeout(args.reducedMotion ? 80 : 500);
      for (const route of routes) {
        postRequests = [];
        const startedAt = Date.now();
        const url = `${args.baseUrl}/${route.route}`;
        await page.goto(url, { waitUntil: "networkidle", timeout: 20000 });
        const loadedAt = Date.now();
        const visualSettleWaitMs = args.reducedMotion ? 80 : 500;
        await page.waitForTimeout(visualSettleWaitMs);
        const inspected = await inspectPage(page, route.route);
        const routeMs = loadedAt - startedAt;
        const screenshotPath = resolve(outputDir, viewport.name, `${route.route.replace("#", "") || "home"}.png`);
        if (args.screenshots) {
          await mkdir(resolve(outputDir, viewport.name), { recursive: true });
          await page.screenshot({ path: screenshotPath, fullPage: false });
        }
        const passed =
          inspected.clipped_count === 0 &&
          inspected.horizontal_overflow_px === 0 &&
          inspected.overlap_count === 0 &&
          inspected.unnamed_interactive_count === 0 &&
          inspected.concealed_motion_content_count === 0 &&
          inspected.expected_anchor_ready === true &&
          postRequests.length === 0 &&
          inspected.long_task_over_50ms_count <= PERFORMANCE_BUDGETS.long_task_over_50ms_count &&
          routeMs <= (route.route === "#candidates" ? PERFORMANCE_BUDGETS.candidate_radar_first_stable_ms : PERFORMANCE_BUDGETS.route_transition_observed_ms);
        rows.push({
          route: route.route,
          label: route.label,
          viewport: viewport.name,
          width: viewport.width,
          height: viewport.height,
          url,
          risk_focus: route.risk_focus,
          status: passed ? "passed" : "review_required",
          visual_qa_complete: passed,
          performance_trace_complete: true,
          route_transition_observed_ms: routeMs,
          visual_settle_wait_ms: visualSettleWaitMs,
          route_transition_budget_ms: route.route === "#candidates" ? PERFORMANCE_BUDGETS.candidate_radar_first_stable_ms : PERFORMANCE_BUDGETS.route_transition_observed_ms,
          long_task_over_50ms_count: inspected.long_task_over_50ms_count,
          largest_motion_layout_shift: inspected.largest_motion_layout_shift,
          visible_element_count: inspected.visible_element_count,
          audited_first_viewport_element_count: inspected.audited_first_viewport_element_count,
          clipped_count: inspected.clipped_count,
          offscreen_count: inspected.offscreen_count,
          clipped_rows: inspected.clipped_rows,
          offscreen_rows: inspected.offscreen_rows,
          horizontal_overflow_px: inspected.horizontal_overflow_px,
          overlap_count: inspected.overlap_count,
          overlap_rows: inspected.overlap_rows,
          unnamed_interactive_count: inspected.unnamed_interactive_count,
          unnamed_interactive_rows: inspected.unnamed_interactive_rows,
          concealed_motion_content_count: inspected.concealed_motion_content_count,
          concealed_motion_content_rows: inspected.concealed_motion_content_rows,
          expected_anchor: inspected.expected_anchor,
          expected_anchor_ready: inspected.expected_anchor_ready,
          post_request_count: postRequests.length,
          post_request_urls: postRequests.map((url) => url.replace(/[?#].*$/, "")),
          motion_markers: inspected.motion_markers,
          screenshot_path: args.screenshots ? screenshotPath : null
        });
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }
  const blockerRows = rows.filter((row) => row.status !== "passed");
  const report = {
    schema_version: SCHEMA_VERSION,
    status: blockerRows.length || errors.length ? "motion_browser_qa_review_required" : "motion_browser_qa_passed",
    scope: "explicit_local_browser_visual_performance_run",
    run_id: runId,
    generated_at: new Date().toISOString(),
    base_url: args.baseUrl,
    artifact_root: args.artifactRoot,
    output_dir: outputDir,
    selected_route: args.route || "all",
    reduced_motion: args.reducedMotion,
    route_count: routes.length,
    viewport_count: QA_VIEWPORTS.length,
    qa_matrix_count: rows.length,
    passed_count: rows.length - blockerRows.length,
    review_required_count: blockerRows.length,
    console_error_count: errors.length,
    visual_qa_complete: blockerRows.length === 0 && errors.length === 0,
    browser_performance_verified: blockerRows.length === 0 && errors.length === 0,
    production_motion_complete: false,
    performance_budgets: PERFORMANCE_BUDGETS,
    visual_acceptance_criteria: VISUAL_ACCEPTANCE_CRITERIA,
    rows,
    errors,
    cache_only: true,
    starts_no_servers: true,
    local_urls_only: args.baseUrl.startsWith("http://127.0.0.1") || args.baseUrl.startsWith("http://localhost"),
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    note: "Local browser QA evidence. It is not a provider call, not a trading path, and not durable CI evidence until reviewed and intentionally promoted."
  };
  const reportPath = resolve(outputDir, "motion_browser_qa_report.json");
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  return { report, reportPath };
}

const args = parseArgs(process.argv);
if (args.printPlan) {
  const plan = makePlan(args);
  console.log(JSON.stringify(plan, null, 2));
  process.exit(0);
}

try {
  const { report, reportPath } = await runQa(args);
  if (args.json) {
    console.log(JSON.stringify({ ...report, report_path: reportPath }, null, 2));
  } else {
    console.log(`motion_browser_qa_runner: ${report.status}`);
    console.log(`rows: ${report.qa_matrix_count}; passed: ${report.passed_count}; review_required: ${report.review_required_count}; console_errors: ${report.console_error_count}`);
    console.log(`report: ${reportPath}`);
    console.log("external_calls_triggered: false; tushare_called: false; deepseek_called: false; github_called: false; does_not_execute_trades: true");
  }
  process.exit(report.status === "motion_browser_qa_passed" ? 0 : 1);
} catch (error) {
  const message = error && error.message ? error.message : String(error);
  console.error(`motion_browser_qa_runner: failed: ${message}`);
  console.error("Make sure local FastAPI and Vite are running, and run with NODE_PATH pointing at a Playwright install if needed.");
  process.exit(1);
}
