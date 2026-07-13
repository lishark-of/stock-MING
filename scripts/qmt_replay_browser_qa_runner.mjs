#!/usr/bin/env node
/*
 * Explicit local browser QA for the v0.7 QMT-ready local replay surface.
 *
 * Start Vite first. This runner intercepts every local FastAPI request with a
 * deterministic in-memory contract. It does not start FastAPI, QMT, a broker,
 * a provider, a model, a worker, or a trading path. Artifacts are ignored under
 * .stock_ming_3/qmt_replay_qa by default.
 */

import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const desktopRequire = createRequire(resolve("desktop/package.json"));
const { chromium } = desktopRequire("playwright");

const SCHEMA_VERSION = "command_center_3_qmt_replay_browser_qa.v1";
const DEFAULT_BASE_URL = "http://127.0.0.1:5173";
const DEFAULT_OUTPUT_ROOT = ".stock_ming_3/qmt_replay_qa";
const SAFETY_TEXT = "QMT未连接｜券商未连接｜无账户绑定｜无订单接口｜不会下单｜仅本地研究回放";
const API_PATTERN = /^http:\/\/(?:127\.0\.0\.1|localhost):8710\//;
const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "tablet", width: 834, height: 1112 },
  { name: "mobile", width: 390, height: 844 }
];
const MOTION_MODES = [
  { name: "normal", reducedMotion: "no-preference" },
  { name: "reduced", reducedMotion: "reduce" }
];

function parseArgs(argv) {
  const args = { baseUrl: DEFAULT_BASE_URL, outputRoot: DEFAULT_OUTPUT_ROOT, screenshots: true, json: false };
  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--base-url") args.baseUrl = argv[++index] || args.baseUrl;
    else if (arg === "--out") args.outputRoot = argv[++index] || args.outputRoot;
    else if (arg === "--no-screenshots") args.screenshots = false;
    else if (arg === "--json") args.json = true;
    else if (arg === "--help") {
      console.log("Usage: node scripts/qmt_replay_browser_qa_runner.mjs [--base-url http://127.0.0.1:5173] [--out .stock_ming_3/qmt_replay_qa] [--no-screenshots] [--json]");
      process.exit(0);
    }
  }
  return args;
}

function envelope(data, warnings = []) {
  return { ok: true, data, error: null, call_ledger: [], warnings };
}

function localLedger(api, callStatus, rowCount = 0) {
  return {
    api,
    call_status: callStatus,
    row_count: rowCount,
    external: false,
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    qmt_called: false,
    broker_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true
  };
}

function taskRecord(payload) {
  return {
    task_id: "local-qmt-replay-browser-qa",
    task_type: "run_qmt_local_replay",
    status: "success",
    created_at: "2026-07-13T08:00:00",
    started_at: "2026-07-13T08:00:00",
    finished_at: "2026-07-13T08:00:01",
    progress: 1,
    current_step: "qmt_local_research_replay_ready",
    output_packet_key: "command_center_3_qmt_local_replay_packet",
    payload_safe: payload,
    backend: "local_in_process_replay",
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    call_ledger: [localLedger("local_qmt_research_replay", "success", 3)],
    status_history: [
      { status: "pending", progress: 0, current_step: "queued" },
      { status: "running", progress: 0.5, current_step: "building_virtual_research_events" },
      { status: "success", progress: 1, current_step: "qmt_local_research_replay_ready" }
    ],
    warnings: ["Browser QA task is deterministic local replay only; QMT, broker, account, order and real-trade paths stay disconnected."]
  };
}

function createApiState() {
  const source = {
    source_symbol: "600519.SH",
    source_task_id: "local-candidate-v05-browser-qa",
    source_result_version: "candidate-v05-browser-qa",
    source_scope_hash: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  };
  const candidateLineage = {
    schema_version: "candidate_radar_v05_next_session_lineage.v1",
    status: "same_packet_lineage_ready",
    symbol: source.source_symbol,
    candidate_task_id: source.source_task_id,
    candidate_result_version: source.source_result_version,
    candidate_scope_hash: source.source_scope_hash,
    data_date: "2026-07-10",
    research_only: true,
    no_action: true,
    no_trade: true
  };
  const safety = {
    qmt_connection_attempted: false,
    qmt_connected: false,
    broker_connected: false,
    account_bound: false,
    market_subscription_started: false,
    order_endpoint_present: false,
    orders_created: 0,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true
  };
  return {
    source,
    candidate: {
      status: "candidate_radar_v05_local_batch_ready",
      latest_confirmed_symbol: source.source_symbol,
      latest_confirmed_task_id: source.source_task_id,
      candidate_radar_v05_result_version: source.source_result_version,
      candidate_radar_v05_scope_hash: source.source_scope_hash,
      candidate_radar_v05_top_rows: [{ symbol: source.source_symbol, candidate_bucket: "Top", runtime_score: 0.82 }],
      candidate_radar_v05_next_session_lineage: candidateLineage,
      data_date: "2026-07-10",
      freshness_state: { state: "fresh", data_date: "2026-07-10" },
      external_calls_triggered: false,
      does_not_execute_trades: true,
      does_not_modify_strategy_action: true
    },
    nextSession: {
      status: "ready_cache_replay",
      latest_confirmed_symbol: source.source_symbol,
      source_task_id: source.source_task_id,
      result_version: source.source_result_version,
      candidate_scope_hash: source.source_scope_hash,
      candidate_radar_v05_lineage: candidateLineage,
      external_calls_triggered: false,
      does_not_execute_trades: true,
      does_not_modify_strategy_action: true
    },
    qmt: {
      status: "qmt_read_only_disconnected_local_replay_ready",
      mode: "qmt_read_only_disconnected_local_replay",
      safety_boundary: safety,
      source_lineage: source,
      lineage_validation: { status: "same_source_lineage_ready", passed: true },
      replay: { status: "waiting_for_explicit_local_replay", virtual_research_events: [] },
      current_result: {},
      last_good_result: {},
      virtual_research_events: [],
      call_ledger: [localLedger("local_qmt_replay_cache", "cache_read", 0)],
      external_calls_triggered: false,
      does_not_execute_trades: true,
      does_not_modify_strategy_action: true,
      warnings: ["QMT is not connected; this cache is local research replay only."]
    },
    task: null,
    observedRequests: [],
    replayPayloads: []
  };
}

function virtualResearchEvents(payload) {
  return [
    { frame: 1, label: `${payload.scenario} 来源确认`, event: "observe", reference_value: 100, evidence: "Candidate v0.5 same-source cache", boundary: "local research only" },
    { frame: 2, label: "缺口复核", event: "watch", reference_value: 98, evidence: "Next Session lineage", boundary: "no broker or account" },
    { frame: 3, label: "失效样本隔离", event: "excluded", reference_value: 94, evidence: "local deterministic rule", boundary: "no order or real trade" }
  ];
}

async function installApiStubs(page, state) {
  await page.route(API_PATTERN, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method().toUpperCase();
    state.observedRequests.push({ method, pathname: url.pathname });
    const respond = (payload, status = 200) => route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(payload),
      headers: { "access-control-allow-origin": "*" }
    });

    if (method === "OPTIONS") return respond({}, 204);
    if (method === "GET" && url.pathname === "/health") return respond(envelope({ status: "ok" }));
    if (method === "GET" && url.pathname === "/api/candidate-radar/cache") return respond(envelope(state.candidate));
    if (method === "GET" && url.pathname === "/api/next-session/cache") return respond(envelope(state.nextSession));
    if (method === "GET" && url.pathname === "/api/qmt-replay/cache") return respond(envelope(state.qmt, state.qmt.warnings));
    if (method === "GET" && url.pathname === "/api/tasks") {
      const tasks = state.task ? [state.task] : [];
      return respond(envelope({
        status: "ready",
        tasks,
        task_count: tasks.length,
        latest_confirmed_symbol: state.source.source_symbol,
        latest_confirmed_task_id: state.task?.task_id || "",
        latest_confirmed_task_status: state.task?.status || "",
        external_calls_triggered: false,
        does_not_execute_trades: true,
        does_not_modify_strategy_action: true
      }));
    }
    if (method === "GET" && url.pathname.startsWith("/api/tasks/")) {
      return state.task ? respond(envelope(state.task)) : respond({ ok: false, data: {}, error: "task_not_found", call_ledger: [], warnings: [] }, 404);
    }
    if (method === "POST" && url.pathname === "/api/qmt-replay/local-simulate") {
      const payload = request.postDataJSON();
      state.replayPayloads.push(payload);
      const events = virtualResearchEvents(payload);
      state.task = taskRecord(payload);
      state.qmt = {
        ...state.qmt,
        status: "qmt_local_research_replay_ready",
        replay: { status: "qmt_local_research_replay_ready", scenario: payload.scenario, frame_count: events.length, research_events: events },
        current_result: { status: "qmt_local_research_replay_ready", scenario: payload.scenario, frame_count: events.length },
        last_good_result: { status: "preserved", source_result_version: payload.source_result_version, frame_count: events.length },
        virtual_research_events: [],
        call_ledger: [localLedger("local_qmt_research_replay", "success", events.length)]
      };
      return respond(envelope({ task_id: state.task.task_id, task: state.task }));
    }
    return respond(envelope({ status: "local_browser_qa_stub" }));
  });
}

async function inspectPage(page) {
  return page.evaluate((safetyText) => {
    const visible = (element) => {
      if (!element) return false;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0.01;
    };
    const row = (element) => {
      const rect = element.getBoundingClientRect();
      return {
        tag: element.tagName.toLowerCase(),
        text: String(element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 120),
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      };
    };
    const hitTestVisible = (element) => {
      const rect = element.getBoundingClientRect();
      if (rect.right <= 0 || rect.bottom <= 0 || rect.left >= innerWidth || rect.top >= innerHeight) return false;
      const inset = 2;
      const points = [
        [rect.left + rect.width / 2, rect.top + rect.height / 2],
        [rect.left + inset, rect.top + inset],
        [rect.right - inset, rect.top + inset],
        [rect.left + inset, rect.bottom - inset],
        [rect.right - inset, rect.bottom - inset]
      ];
      return points.some(([rawX, rawY]) => {
        const x = Math.max(0, Math.min(innerWidth - 1, rawX));
        const y = Math.max(0, Math.min(innerHeight - 1, rawY));
        const hit = document.elementFromPoint(x, y);
        return Boolean(hit && (hit === element || element.contains(hit)));
      });
    };
    const interactive = Array.from(document.querySelectorAll("button, a[href], input, select, textarea, [tabindex]"))
      .filter((element) => visible(element) && hitTestVisible(element));
    const unnamed = interactive.filter((element) => ![
      element.getAttribute("aria-label"),
      element.getAttribute("aria-labelledby"),
      element.getAttribute("title"),
      element.getAttribute("placeholder"),
      element.textContent,
      element.id && document.querySelector(`label[for=\"${CSS.escape(element.id)}\"]`)?.textContent
    ].some((value) => String(value || "").trim())).map(row).slice(0, 20);
    const overlap = [];
    for (let leftIndex = 0; leftIndex < interactive.length; leftIndex += 1) {
      const left = interactive[leftIndex];
      const leftRect = left.getBoundingClientRect();
      if (leftRect.bottom <= 0 || leftRect.top >= innerHeight) continue;
      for (let rightIndex = leftIndex + 1; rightIndex < interactive.length; rightIndex += 1) {
        const right = interactive[rightIndex];
        if (left.contains(right) || right.contains(left)) continue;
        const rightRect = right.getBoundingClientRect();
        if (rightRect.bottom <= 0 || rightRect.top >= innerHeight) continue;
        const width = Math.min(leftRect.right, rightRect.right) - Math.max(leftRect.left, rightRect.left);
        const height = Math.min(leftRect.bottom, rightRect.bottom) - Math.max(leftRect.top, rightRect.top);
        if (width > 1 && height > 1) overlap.push({ left: row(left), right: row(right) });
      }
    }
    const clipped = Array.from(document.querySelectorAll("h1, h2, h3, button, a[href], label, .status-badge"))
      .filter(visible)
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        if (rect.bottom <= 0 || rect.top >= innerHeight) return false;
        return element.scrollWidth > element.clientWidth + 4 || element.scrollHeight > element.clientHeight + 4;
      })
      .map(row)
      .slice(0, 20);
    const concealed = Array.from(document.querySelectorAll(".qmt-safety-boundary, .packet-card, .task-panel, .chart-refresh-frame"))
      .filter(visible)
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return rect.bottom > 0 && rect.top < innerHeight && Number(getComputedStyle(element).opacity || 1) < 0.94;
      })
      .map(row)
      .slice(0, 20);
    const safety = document.querySelector("[data-qmt-permanent-safety-boundary=true]");
    const safetyRect = safety?.getBoundingClientRect();
    const replayRegion = document.querySelector("[aria-label='QMT local virtual research event track']");
    const describedBy = replayRegion?.getAttribute("aria-describedby") || "";
    const eventStates = Array.from(document.querySelectorAll("[data-research-state]"))
      .map((element) => element.getAttribute("data-research-state"));
    const reducedMotionQuery = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const routeStage = document.querySelector(".route-stage");
    const routeAnimationMs = routeStage ? parseFloat(getComputedStyle(routeStage).animationDuration || "0") * 1000 : 0;
    return {
      h1: document.querySelector("h1")?.textContent?.trim() || "",
      safety_text_visible: Boolean(safety && safety.textContent?.includes(safetyText) && visible(safety)),
      safety_in_first_viewport: Boolean(safetyRect && safetyRect.top >= 0 && safetyRect.bottom <= innerHeight),
      horizontal_overflow_px: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
      clipped_count: clipped.length,
      clipped_rows: clipped,
      overlap_count: overlap.length,
      overlap_rows: overlap.slice(0, 20),
      unnamed_interactive_count: unnamed.length,
      unnamed_interactive_rows: unnamed,
      concealed_count: concealed.length,
      concealed_rows: concealed,
      replay_region_keyboard_focusable: replayRegion?.getAttribute("tabindex") === "0",
      replay_region_described: Boolean(describedBy && document.getElementById(describedBy)),
      table_fallback_visible: Array.from(document.querySelectorAll("table")).some(visible),
      event_states: eventStates,
      event_states_allowed: eventStates.every((state) => ["observe", "watch", "excluded"].includes(String(state))),
      reduced_motion_query: reducedMotionQuery,
      route_animation_ms: routeAnimationMs,
      long_task_over_50ms_count: performance.getEntriesByType("longtask").filter((entry) => entry.duration > 50).length
    };
  }, SAFETY_TEXT);
}

async function runCase(browser, args, viewport, motionMode, outputDir) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    reducedMotion: motionMode.reducedMotion
  });
  const page = await context.newPage();
  const state = createApiState();
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push({ kind: "console", message: message.text() });
  });
  page.on("pageerror", (error) => errors.push({ kind: "pageerror", message: String(error.message || error) }));
  await installApiStubs(page, state);

  await page.goto(`${args.baseUrl}/#qmt-replay`, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForSelector("[data-qmt-permanent-safety-boundary=true]", { timeout: 10000 });
  await page.waitForTimeout(motionMode.name === "reduced" ? 80 : 720);
  const initialInspect = await inspectPage(page);
  const postsAfterRender = state.observedRequests.filter((request) => request.method === "POST").length;

  await page.locator("#qmt-replay-demo-label").fill("浏览器 脱敏 演示");
  await page.locator("#qmt-replay-scenario").selectOption("stress");
  await page.locator("#qmt-replay-max-frames").selectOption("12");
  await page.locator("#qmt-replay-demo-label").focus();
  await page.keyboard.press("Tab");
  const postsAfterInput = state.observedRequests.filter((request) => request.method === "POST").length;

  await page.locator("#qmt-replay-approved").check();
  await page.locator("button.qmt-replay-launch").click();
  await page.waitForSelector("[data-qmt-replay-event-count='3']", { timeout: 10000 });
  await page.waitForSelector(".task-panel--receipt", { timeout: 10000 });
  await page.waitForTimeout(motionMode.name === "reduced" ? 80 : 720);

  const inspected = await inspectPage(page);
  const postRequests = state.observedRequests.filter((request) => request.method === "POST");
  const payload = state.replayPayloads[0] || {};
  const payloadReady = payload.approved_by_user === true &&
    payload.mode === "local_research_replay" &&
    payload.scenario === "stress" &&
    payload.max_frames === 12 &&
    payload.source_symbol === state.source.source_symbol &&
    payload.source_task_id === state.source.source_task_id &&
    payload.source_result_version === state.source.source_result_version &&
    payload.source_scope_hash === state.source.source_scope_hash;
  const reducedMotionReady = motionMode.name === "normal" || (inspected.reduced_motion_query && inspected.route_animation_ms <= 1.1);
  const passed = postsAfterRender === 0 &&
    postsAfterInput === 0 &&
    postRequests.length === 1 &&
    postRequests[0]?.pathname === "/api/qmt-replay/local-simulate" &&
    payloadReady &&
    inspected.h1 === "QMT 本地回放" &&
    initialInspect.safety_text_visible &&
    initialInspect.safety_in_first_viewport &&
    inspected.horizontal_overflow_px === 0 &&
    inspected.clipped_count === 0 &&
    inspected.overlap_count === 0 &&
    inspected.unnamed_interactive_count === 0 &&
    inspected.concealed_count === 0 &&
    inspected.replay_region_keyboard_focusable &&
    inspected.replay_region_described &&
    inspected.table_fallback_visible &&
    inspected.event_states.length === 3 &&
    inspected.event_states_allowed &&
    inspected.long_task_over_50ms_count === 0 &&
    reducedMotionReady &&
    errors.length === 0;

  const caseId = `${viewport.name}-${motionMode.name}`;
  let screenshotPath = null;
  if (args.screenshots) {
    screenshotPath = resolve(outputDir, `${caseId}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
  }
  await context.close();
  return {
    case_id: caseId,
    viewport: viewport.name,
    width: viewport.width,
    height: viewport.height,
    motion: motionMode.name,
    status: passed ? "passed" : "review_required",
    posts_after_render: postsAfterRender,
    posts_after_input_select_tab: postsAfterInput,
    post_request_count: postRequests.length,
    post_request_paths: postRequests.map((request) => request.pathname),
    replay_payload_contract_ready: payloadReady,
    reduced_motion_ready: reducedMotionReady,
    errors,
    screenshot_path: screenshotPath,
    initial_safety_text_visible: initialInspect.safety_text_visible,
    initial_safety_in_first_viewport: initialInspect.safety_in_first_viewport,
    ...inspected
  };
}

async function run(args) {
  if (!/^http:\/\/(?:127\.0\.0\.1|localhost):\d+$/.test(args.baseUrl)) {
    throw new Error("base URL must be an explicit localhost HTTP origin");
  }
  const runId = new Date().toISOString().replace(/[:.]/g, "-");
  const outputDir = resolve(args.outputRoot, runId);
  await mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const rows = [];
  try {
    for (const viewport of VIEWPORTS) {
      for (const motionMode of MOTION_MODES) {
        rows.push(await runCase(browser, args, viewport, motionMode, outputDir));
      }
    }
  } finally {
    await browser.close();
  }
  const blockers = rows.filter((row) => row.status !== "passed");
  const report = {
    schema_version: SCHEMA_VERSION,
    status: blockers.length ? "qmt_replay_browser_qa_review_required" : "qmt_replay_browser_qa_passed",
    scope: "explicit_local_qmt_ready_replay_ui_with_in_memory_api_contract",
    generated_at: new Date().toISOString(),
    base_url: args.baseUrl,
    output_dir: outputDir,
    case_count: rows.length,
    passed_count: rows.length - blockers.length,
    review_required_count: blockers.length,
    rows,
    starts_no_backend: true,
    qmt_connected: false,
    broker_connected: false,
    account_bound: false,
    order_endpoint_present: false,
    orders_created: 0,
    external_calls_triggered: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true
  };
  const reportPath = resolve(outputDir, "qmt_replay_browser_qa_report.json");
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  return { report, reportPath };
}

const args = parseArgs(process.argv);
try {
  const { report, reportPath } = await run(args);
  if (args.json) console.log(JSON.stringify({ ...report, report_path: reportPath }, null, 2));
  else {
    console.log(`qmt_replay_browser_qa_runner: ${report.status}`);
    console.log(`cases: ${report.case_count}; passed: ${report.passed_count}; review_required: ${report.review_required_count}`);
    console.log(`report: ${reportPath}`);
    console.log("QMT=false; broker=false; account=false; order_endpoint=false; orders_created=0; external_calls_triggered=false; does_not_execute_trades=true");
  }
  process.exit(report.status === "qmt_replay_browser_qa_passed" ? 0 : 1);
} catch (error) {
  console.error(`qmt_replay_browser_qa_runner: failed: ${String(error?.message || error)}`);
  process.exit(1);
}
