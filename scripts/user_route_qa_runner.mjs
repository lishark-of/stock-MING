#!/usr/bin/env node
/*
 * Explicit local browser QA for ordinary Command Center 3 routes.
 *
 * This runner does not start FastAPI, Vite, providers, models, workers, or
 * trading paths. Start the local app first, then run this against 127.0.0.1.
 * Artifacts are written under .stock_ming_3/user_route_qa, which is ignored.
 */

import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(SCRIPT_DIR, "..");
const DESKTOP_PACKAGE_JSON = resolve(REPO_ROOT, "desktop/package.json");
const desktopRequire = existsSync(DESKTOP_PACKAGE_JSON) ? createRequire(DESKTOP_PACKAGE_JSON) : null;

const SCHEMA_VERSION = "command_center_3_user_route_qa_result.v1";
const DEFAULT_BASE_URL = "http://127.0.0.1:5173";
const DEFAULT_API_BASE = "http://127.0.0.1:8710";
const DEFAULT_ARTIFACT_ROOT = ".stock_ming_3/user_route_qa";
const SYSTEM_CHROMIUM_EXECUTABLE_PATHS = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
];
const CHROMIUM_EXECUTABLE_PATH =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
  SYSTEM_CHROMIUM_EXECUTABLE_PATHS.find((path) => existsSync(path)) ||
  "";

function requirePlaywright() {
  try {
    return require("playwright");
  } catch (rootError) {
    if (desktopRequire) {
      try {
        return desktopRequire("playwright");
      } catch {
        // Fall through to the clearer error below.
      }
    }
    throw new Error(
      `Cannot find module 'playwright'. Run PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm --prefix desktop install, or set NODE_PATH to a Playwright install. Original error: ${rootError.message}`
    );
  }
}

function chromiumLaunchOptions() {
  return {
    headless: true,
    ...(CHROMIUM_EXECUTABLE_PATH ? { executablePath: CHROMIUM_EXECUTABLE_PATH } : {})
  };
}

const QA_ROUTES = [
  { route: "#home", label: "Daily Command Center", focus: "first-card readiness, current symbol, next action, source state" },
  { route: "#candidates", label: "Candidate Radar", focus: "candidate pool, confirm button, local-only controls, no-buy boundary" },
  { route: "#marginEtf", label: "ETF / Margin", focus: "confirmed radar bridge, ETF row evidence, cash/leverage guardrail, degraded task reason" },
  { route: "#factor", label: "Stock Quant Projection", focus: "symbol result, factor support/suppression, provider gaps" },
  { route: "#next", label: "Next Session Map", focus: "operation zones as conditions, chart readability, no-action boundary" }
];

const QA_VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 }
];

function routeSpecificCheckName(route) {
  if (route === "#marginEtf") return "margin_etf_confirmed_data_bridge_visible";
  if (["#candidates", "#factor", "#next"].includes(route)) return "search_quant_same_result_chain_visible";
  return "generic_route_heading_visible";
}

function parseArgs(argv) {
  const args = {
    baseUrl: DEFAULT_BASE_URL,
    apiBase: DEFAULT_API_BASE,
    artifactRoot: DEFAULT_ARTIFACT_ROOT,
    route: null,
    candidateResultScenario: "live",
    screenshots: true,
    json: false,
    printPlan: false
  };
  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--base-url") args.baseUrl = argv[++index] || args.baseUrl;
    else if (arg === "--api-base") args.apiBase = argv[++index] || args.apiBase;
    else if (arg === "--out") args.artifactRoot = argv[++index] || args.artifactRoot;
    else if (arg === "--route") args.route = argv[++index] || args.route;
    else if (arg === "--candidate-result-scenario") args.candidateResultScenario = argv[++index] || args.candidateResultScenario;
    else if (arg === "--no-screenshots") args.screenshots = false;
    else if (arg === "--json") args.json = true;
    else if (arg === "--print-plan") args.printPlan = true;
    else if (arg === "--help") {
      console.log("Usage: node scripts/user_route_qa_runner.mjs [--base-url http://127.0.0.1:5173] [--api-base http://127.0.0.1:8710] [--out .stock_ming_3/user_route_qa] [--route #home] [--candidate-result-scenario live|degraded-last-good] [--no-screenshots] [--json] [--print-plan]");
      process.exit(0);
    }
  }
  if (!["live", "degraded-last-good"].includes(args.candidateResultScenario)) {
    throw new Error(`Unknown candidate result scenario: ${args.candidateResultScenario}`);
  }
  return args;
}

function selectedRoutes(args) {
  if (!args.route) return QA_ROUTES;
  const requested = args.route.startsWith("#") ? args.route : `#${args.route}`;
  const routes = QA_ROUTES.filter((route) => route.route === requested);
  if (!routes.length) throw new Error(`Unknown ordinary route: ${args.route}`);
  return routes;
}

function isLocalUrl(value) {
  try {
    const parsed = new URL(value);
    return ["127.0.0.1", "localhost", "::1", "[::1]"].includes(parsed.hostname);
  } catch {
    return false;
  }
}

function timestampId() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function makePlan(args) {
  const routes = selectedRoutes(args);
  const qaMatrix = routes.flatMap((route) =>
    QA_VIEWPORTS.map((viewport) => ({
      route: route.route,
      label: route.label,
      viewport: viewport.name,
      width: viewport.width,
      height: viewport.height,
      url: `${args.baseUrl}/${route.route}`,
      focus: route.focus,
      route_specific_check: routeSpecificCheckName(route.route),
      route_specific_check_required: true,
      visual_qa_complete: false,
      typing_silence_verified: false
    }))
  );
  return {
    schema_version: "command_center_3_user_route_qa_plan.v1",
    status: "user_route_qa_plan_ready",
    scope: "explicit_local_ordinary_route_browser_qa_plan",
    route_count: routes.length,
    viewport_count: QA_VIEWPORTS.length,
    qa_matrix_count: qaMatrix.length,
    qa_matrix: qaMatrix,
    checks: [
      "first viewport has a clear route title",
      "primary buttons and status labels do not clip",
      "audit details do not dominate the first viewport",
      "typing into visible inputs does not create a task",
      "visible editable inputs must be typed before typing silence is accepted",
      "candidate/factor/next routes display the same symbol, task id, and result_version when current result cache exists",
      "optional degraded-last-good replay proves visible degraded reason, last-good retention, and stale-result overwrite guard without writing cache",
      "route-specific checks verify the margin ETF confirmed data bridge is visible",
      "screenshots and JSON report stay under ignored .stock_ming_3"
    ],
    base_url: args.baseUrl,
    api_base: args.apiBase,
    artifact_root: args.artifactRoot,
    candidate_result_scenario: args.candidateResultScenario,
    candidate_result_scenario_replay: args.candidateResultScenario !== "live",
    local_urls_only: isLocalUrl(args.baseUrl) && isLocalUrl(args.apiBase),
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true
  };
}

async function fetchTaskCount(apiBase) {
  const response = await fetch(`${apiBase.replace(/\/$/, "")}/api/tasks`);
  const payload = await response.json();
  const data = payload && typeof payload === "object" ? payload.data || payload : {};
  const taskCount = Number(data.task_count ?? (Array.isArray(data.tasks) ? data.tasks.length : 0));
  return Number.isFinite(taskCount) ? taskCount : 0;
}

function safeString(value) {
  return String(value ?? "").trim();
}

function safeStringList(value) {
  return Array.isArray(value) ? value.map((item) => safeString(item)).filter(Boolean) : [];
}

async function fetchCandidateCacheEnvelope(apiBase) {
  const response = await fetch(`${apiBase.replace(/\/$/, "")}/api/candidate-radar/cache`);
  return response.json();
}

function buildDegradedLastGoodCandidateEnvelope(livePayload) {
  const envelope = JSON.parse(JSON.stringify(livePayload && typeof livePayload === "object" ? livePayload : {}));
  const data = envelope.data && typeof envelope.data === "object" ? envelope.data : {};
  const summary = data.search_quant_result_version_summary || {};
  const currentLineage = data.search_quant_current_result_lineage || data.search_quant_result_lineage || {};
  const currentSymbol = safeString(summary.current_result_symbol || currentLineage.symbol || "002008.SZ");
  const currentVersion = safeString(summary.current_result_version || currentLineage.result_version || "qrv_last_good_browser_qa");
  const degradedLineage = {
    schema_version: "candidate_radar_search_quant_projection_result_lineage.v1",
    task_id: "local-qa-degraded-task",
    symbol: "000001.SZ",
    scope_hash: "qa-degraded-scope-hash",
    scope_hash_short: "qa-degraded-scope",
    provider_call_ledger_ids: ["pcl_qa_trade_cal_only"],
    input_packet_keys: [
      "command_center_candidate_radar_quant_projection_receipt",
      "command_center_candidate_radar_quant_projection_tushare_light_packet"
    ],
    output_packet_keys: ["command_center_3_candidate_radar_cache"],
    data_date: safeString(summary.current_result_data_date || currentLineage.data_date || "20260711"),
    freshness_state: "partial_provider",
    model_ledger_id: "mlg_qa_skipped_missing_facts",
    result_version: "qrv_degraded_browser_qa",
    facts_packet_key: "command_center_candidate_radar_quant_projection_tushare_light_packet",
    facts_package_status: "partial_provider",
    factor_next_same_result_ready: false,
    current_result_promoted: false,
    last_good_policy: "promote_current_result_only_after_tushare_facts_factor_next_same_result_ready",
    late_task_overwrite_guard: "symbol_and_result_version_must_match",
    old_task_can_overwrite_current: false,
    deepseek_status: "skipped_missing_facts",
    deepseek_skipped_missing_facts: true,
    deepseek_is_data_source: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    does_not_override_numeric_values: true,
    contains_secret: false
  };
  data.latest_confirmed_symbol = degradedLineage.symbol;
  data.search_quant_result_lineage = degradedLineage;
  data.search_quant_degraded_result_lineage = degradedLineage;
  data.search_quant_current_result_lineage = currentLineage;
  data.search_quant_last_good_result_lineage = currentLineage;
  data.search_quant_result_version_summary = {
    schema_version: "candidate_radar_search_quant_projection_result_version_summary.v1",
    status: "degraded_result_recorded_last_good_retained",
    latest_task_id: degradedLineage.task_id,
    latest_task_symbol: degradedLineage.symbol,
    latest_task_result_version: degradedLineage.result_version,
    latest_result_version: degradedLineage.result_version,
    latest_task_scope_hash: degradedLineage.scope_hash,
    latest_task_scope_hash_short: degradedLineage.scope_hash_short,
    latest_task_provider_call_ledger_ids: degradedLineage.provider_call_ledger_ids,
    latest_task_input_packet_keys: degradedLineage.input_packet_keys,
    latest_task_output_packet_keys: degradedLineage.output_packet_keys,
    latest_task_data_date: degradedLineage.data_date,
    latest_task_freshness_state: degradedLineage.freshness_state,
    latest_task_model_ledger_id: degradedLineage.model_ledger_id,
    current_result_version: currentVersion,
    current_result_task_id: safeString(currentLineage.task_id || "local-last-good-task"),
    current_result_symbol: currentSymbol,
    current_result_scope_hash_short: safeString(currentLineage.scope_hash_short || "last-good-scope"),
    current_result_provider_call_ledger_ids: safeStringList(currentLineage.provider_call_ledger_ids),
    current_result_input_packet_keys: safeStringList(currentLineage.input_packet_keys),
    current_result_output_packet_keys: safeStringList(currentLineage.output_packet_keys),
    current_result_data_date: safeString(currentLineage.data_date || degradedLineage.data_date),
    current_result_freshness_state: safeString(currentLineage.freshness_state || "fresh_provider"),
    current_result_model_ledger_id: safeString(currentLineage.model_ledger_id || ""),
    last_good_result_version: currentVersion,
    last_good_task_id: safeString(currentLineage.task_id || "local-last-good-task"),
    last_good_result_symbol: currentSymbol,
    degraded_result_version: degradedLineage.result_version,
    degraded_task_id: degradedLineage.task_id,
    degraded_result_symbol: degradedLineage.symbol,
    degraded_scope_hash: degradedLineage.scope_hash,
    degraded_scope_hash_short: degradedLineage.scope_hash_short,
    degraded_provider_call_ledger_ids: degradedLineage.provider_call_ledger_ids,
    degraded_input_packet_keys: degradedLineage.input_packet_keys,
    degraded_output_packet_keys: degradedLineage.output_packet_keys,
    degraded_data_date: degradedLineage.data_date,
    degraded_freshness_state: degradedLineage.freshness_state,
    degraded_model_ledger_id: degradedLineage.model_ledger_id,
    degraded_deepseek_status: "skipped_missing_facts",
    degraded_deepseek_skipped_missing_facts: true,
    degraded_reason: "skipped_missing_facts",
    current_result_promoted: false,
    current_result_matches_latest_task: false,
    last_good_result_available: true,
    degraded_result_visible: true,
    last_good_policy: degradedLineage.last_good_policy,
    late_task_overwrite_guard: degradedLineage.late_task_overwrite_guard,
    old_task_can_overwrite_current: false,
    ordinary_summary: "本次确认已标记 degraded；页面保留上一条 last-good current result，不让失败任务覆盖当前结果。",
    ordinary_next_step: "先按 last-good 只读回放；本次 degraded 只用于查看缺口和重试条件。",
    readback_route: "GET /api/candidate-radar/cache",
    cache_only_readback: true,
    creates_task_from_readback: false,
    readback_external_calls_triggered: false,
    tushare_called_from_readback: false,
    deepseek_called_from_readback: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    candidate_is_not_buy_instruction: true,
    contains_secret: false
  };
  data.search_quant_provider_model_acceptance_receipt = {
    ...(data.search_quant_provider_model_acceptance_receipt || {}),
    status: "search_quant_provider_model_acceptance_degraded_tushare_facts_missing_deepseek_skipped",
    task_id: degradedLineage.task_id,
    symbol: degradedLineage.symbol,
    result_version: degradedLineage.result_version,
    result_version_summary: data.search_quant_result_version_summary,
    provider_call_ledger_ids: degradedLineage.provider_call_ledger_ids,
    provider_api_call_count: 4,
    provider_api_success_count: 1,
    tushare_call_ledger_evidence_done: false,
    deepseek_model_ledger_recorded: true,
    deepseek_skipped_missing_facts: true,
    deepseek_safe_failure_mode: "skipped_missing_facts",
    deepseek_called: false,
    old_task_can_overwrite_current: false,
    contains_secret: false
  };
  data.search_quant_deepseek_model_ledger = {
    schema_version: "candidate_radar_search_quant_projection_deepseek_model_ledger.v1",
    status: "skipped_missing_facts",
    model_call_status: "skipped_missing_facts",
    model_ledger_id: degradedLineage.model_ledger_id,
    deepseek_called: false,
    external_calls_triggered: false,
    raw_prompt_stored: false,
    raw_output_stored: false,
    safe_failure_mode: "skipped_missing_facts",
    contains_secret: false
  };
  data.search_quant_deepseek_explanation = {
    schema_version: "candidate_radar_search_quant_projection_deepseek_explanation.v1",
    status: "skipped_missing_facts",
    source: "safe_degraded_status",
    model_ledger_id: degradedLineage.model_ledger_id,
    error_message_safe: "skipped_missing_facts",
    explanation_only: true,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    contains_secret: false
  };
  envelope.data = data;
  envelope.call_ledger = Array.isArray(envelope.call_ledger) ? envelope.call_ledger : [];
  envelope.warnings = [
    ...(Array.isArray(envelope.warnings) ? envelope.warnings : []),
    "local_browser_qa_degraded_last_good_replay_only_no_cache_write_no_provider_model_call"
  ];
  return envelope;
}

function buildCandidateEnvelopeForScenario(livePayload, scenario) {
  if (scenario === "degraded-last-good") return buildDegradedLastGoodCandidateEnvelope(livePayload);
  return livePayload;
}

function candidateResultChainFromEnvelope(payload, scenario = "live") {
  const data = payload && typeof payload === "object" ? payload.data || payload : {};
  const summary = data.search_quant_result_version_summary || {};
  const currentLineage = data.search_quant_current_result_lineage || {};
  const resultLineage = data.search_quant_result_lineage || {};
  const degradedLineage = data.search_quant_degraded_result_lineage || {};
  const providerReceipt = data.search_quant_provider_model_acceptance_receipt || {};
  const modelLedger = data.search_quant_deepseek_model_ledger || {};
  const currentSymbol = safeString(summary.current_result_symbol || currentLineage.symbol || resultLineage.symbol || providerReceipt.symbol || data.latest_confirmed_symbol);
  const latestSymbol = safeString(summary.latest_task_symbol || resultLineage.symbol || providerReceipt.symbol || data.latest_confirmed_symbol || currentSymbol);
  const currentVersion = safeString(summary.current_result_version || currentLineage.result_version || resultLineage.result_version || providerReceipt.result_version || data.search_quant_result_version);
  const latestVersion = safeString(summary.latest_task_result_version || summary.latest_result_version || resultLineage.result_version || providerReceipt.result_version || currentVersion);
  const degradedVersion = safeString(summary.degraded_result_version || degradedLineage.result_version || "");
  const degradedVisible = summary.degraded_result_visible === true || Boolean(degradedVersion);
  const providerLedgerIds = safeStringList(
    summary.current_result_provider_call_ledger_ids ||
      summary.latest_task_provider_call_ledger_ids ||
      currentLineage.provider_call_ledger_ids ||
      resultLineage.provider_call_ledger_ids ||
      providerReceipt.provider_call_ledger_ids
  );
  const degradedProviderLedgerIds = safeStringList(
    summary.degraded_provider_call_ledger_ids || degradedLineage.provider_call_ledger_ids
  );
  return {
    available: Boolean(currentSymbol && currentVersion),
    scenario,
    symbol: currentSymbol,
    result_version: currentVersion,
    task_id: safeString(summary.current_result_task_id || summary.latest_task_id || currentLineage.task_id || resultLineage.task_id || providerReceipt.task_id || data.latest_confirmed_task_id),
    latest_symbol: latestSymbol,
    latest_result_version: latestVersion,
    latest_task_id: safeString(summary.latest_task_id || resultLineage.task_id || providerReceipt.task_id || data.latest_confirmed_task_id),
    degraded_result_visible: degradedVisible,
    degraded_symbol: safeString(summary.degraded_result_symbol || degradedLineage.symbol || (degradedVisible ? latestSymbol : "")),
    degraded_result_version: degradedVersion,
    degraded_reason: safeString(summary.degraded_reason || providerReceipt.deepseek_safe_failure_mode || degradedLineage.freshness_state || ""),
    scope_hash_short: safeString(summary.current_result_scope_hash_short || summary.latest_task_scope_hash_short || currentLineage.scope_hash_short || resultLineage.scope_hash_short || providerReceipt.acceptance_scope_hash_short),
    data_date: safeString(summary.current_result_data_date || summary.latest_task_data_date || currentLineage.data_date || resultLineage.data_date || providerReceipt.data_date),
    freshness_state: safeString(summary.current_result_freshness_state || summary.latest_task_freshness_state || currentLineage.freshness_state || resultLineage.freshness_state || providerReceipt.freshness_state),
    model_ledger_id: safeString(summary.current_result_model_ledger_id || summary.latest_task_model_ledger_id || currentLineage.model_ledger_id || resultLineage.model_ledger_id || providerReceipt.model_ledger_id || modelLedger.model_ledger_id),
    provider_call_ledger_ids: providerLedgerIds,
    provider_call_ledger_count: providerLedgerIds.length || degradedProviderLedgerIds.length,
    degraded_provider_call_ledger_ids: degradedProviderLedgerIds,
    status: safeString(summary.status || providerReceipt.status || resultLineage.facts_package_status),
    current_result_matches_latest_task: summary.current_result_matches_latest_task === true,
    old_task_can_overwrite_current: summary.old_task_can_overwrite_current === true,
    old_task_overwrite_guard_ready: summary.old_task_can_overwrite_current === false || resultLineage.old_task_can_overwrite_current === false,
    readback_route: "GET /api/candidate-radar/cache",
    cache_only_readback: true,
    creates_task_from_readback: false,
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    contains_secret: false
  };
}

async function fetchCandidateResultChain(apiBase, scenarioEnvelope = null, scenario = "live") {
  try {
    const payload = scenarioEnvelope || (await fetchCandidateCacheEnvelope(apiBase));
    return candidateResultChainFromEnvelope(payload, scenario);
  } catch (error) {
    return {
      available: false,
      scenario,
      error_message_safe: `candidate_result_chain_unavailable:${error && error.message ? error.message : String(error)}`,
      readback_route: "GET /api/candidate-radar/cache",
      cache_only_readback: true,
      creates_task_from_readback: false,
      external_calls_triggered: false,
      tushare_called: false,
      deepseek_called: false,
      github_called: false,
      does_not_execute_trades: true,
      does_not_modify_strategy_action: true,
      contains_secret: false
    };
  }
}

async function inspectPage(page) {
  return page.evaluate(() => {
    const selectors = [
      "h1",
      "h2",
      "h3",
      "button",
      "a",
      "label",
      ".metric",
      ".status-badge",
      ".ordinary-status-note",
      ".risk-note",
      ".packet-card"
    ];
    const candidates = Array.from(document.querySelectorAll(selectors.join(",")));
    const isVisible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0.01;
    };
    const isClipped = (element) => {
      const tolerance = 4;
      return element.scrollWidth > Math.ceil(element.clientWidth) + tolerance || element.scrollHeight > Math.ceil(element.clientHeight) + tolerance;
    };
    const isEditableTextInput = (element) => {
      if (!(element instanceof HTMLInputElement) && !(element instanceof HTMLTextAreaElement)) return false;
      if (element.disabled || element.readOnly) return false;
      if (element instanceof HTMLTextAreaElement) return true;
      const type = (element.getAttribute("type") || "text").toLowerCase();
      return !["button", "checkbox", "color", "file", "hidden", "image", "radio", "range", "reset", "submit"].includes(type);
    };
    const rowFor = (element) => {
      const rect = element.getBoundingClientRect();
      return {
        tag: element.tagName.toLowerCase(),
        className: String(element.className || ""),
        text: (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 140),
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        clipped: isClipped(element),
        in_first_viewport: rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth
      };
    };
    const visibleRows = candidates.filter(isVisible).map(rowFor);
    const firstViewportRows = visibleRows.filter((row) => row.in_first_viewport);
    const clippedRows = firstViewportRows.filter((row) => row.clipped && row.text).slice(0, 12);
    const auditNoiseText = firstViewportRows
      .map((row) => row.text)
      .filter((text) => /审计|audit|developer|raw json|生产阻断|manifest/i.test(text));
    const disabledButtonsWithoutReason = Array.from(document.querySelectorAll("button:disabled"))
      .filter(isVisible)
      .map((button) => ({
        text: (button.textContent || "").trim().replace(/\s+/g, " ").slice(0, 80),
        title: button.getAttribute("title") || "",
        aria_label: button.getAttribute("aria-label") || ""
      }))
      .filter((button) => !button.title && !button.aria_label)
      .slice(0, 12);
    const visibleInputs = Array.from(document.querySelectorAll("input, textarea")).filter(isVisible);
    return {
      title: document.title,
      route_heading: document.querySelector("h1, h2, h3")?.textContent?.trim() || "",
      first_viewport_element_count: firstViewportRows.length,
      clipped_count: clippedRows.length,
      clipped_rows: clippedRows,
      audit_noise_count: auditNoiseText.length,
      audit_noise_text: auditNoiseText.slice(0, 8),
      disabled_buttons_without_reason_count: disabledButtonsWithoutReason.length,
      disabled_buttons_without_reason: disabledButtonsWithoutReason,
      visible_input_count: visibleInputs.length,
      editable_visible_input_count: visibleInputs.filter(isEditableTextInput).length
    };
  });
}

async function inspectRouteSpecific(page, route, candidateResultChain) {
  if (["#candidates", "#factor", "#next"].includes(route)) {
    const check = "search_quant_same_result_chain_visible";
    if (!candidateResultChain.available) {
      return {
        check,
        passed: true,
        evidence: ["no current search quant result chain in cache; generic route and task-silence checks apply"],
        missing: [],
        candidate_result_chain: candidateResultChain
      };
    }
    await page
      .waitForFunction(
        ({ symbol, resultVersion, taskId, latestTaskId, latestSymbol, degradedResultVersion, degradedResultVisible }) => {
          const bodyText = (document.body?.innerText || "").replace(/\s+/g, " ");
          const taskVisible = degradedResultVisible
            ? Boolean((latestTaskId && bodyText.includes(latestTaskId)) || (taskId && bodyText.includes(taskId)))
            : (!taskId || bodyText.includes(taskId));
          return (
            Boolean(symbol && bodyText.includes(symbol)) &&
            Boolean(resultVersion && bodyText.includes(resultVersion)) &&
            taskVisible &&
            (!degradedResultVisible ||
              (
                Boolean(latestSymbol && bodyText.includes(latestSymbol)) &&
                Boolean(degradedResultVersion && bodyText.includes(degradedResultVersion))
              ))
          );
        },
        {
          symbol: candidateResultChain.symbol,
          resultVersion: candidateResultChain.result_version,
          taskId: candidateResultChain.task_id,
          latestTaskId: candidateResultChain.latest_task_id,
          latestSymbol: candidateResultChain.latest_symbol,
          degradedResultVersion: candidateResultChain.degraded_result_version,
          degradedResultVisible: candidateResultChain.degraded_result_visible
        },
        { timeout: 4000 }
      )
      .catch(() => {});
    return page.evaluate((chain) => {
      const bodyText = (document.body?.innerText || "").replace(/\s+/g, " ");
      const textChecks = [
        { label: "same_result_symbol", ok: Boolean(chain.symbol && bodyText.includes(chain.symbol)) },
        { label: "same_result_version", ok: Boolean(chain.result_version && bodyText.includes(chain.result_version)) },
        { label: "same_result_task_id", ok: chain.degraded_result_visible ? Boolean((chain.latest_task_id && bodyText.includes(chain.latest_task_id)) || (chain.task_id && bodyText.includes(chain.task_id))) : (!chain.task_id || bodyText.includes(chain.task_id)) },
        { label: "latest_degraded_symbol", ok: !chain.degraded_result_visible || Boolean(chain.latest_symbol && bodyText.includes(chain.latest_symbol)) },
        { label: "latest_degraded_version", ok: !chain.degraded_result_visible || Boolean(chain.degraded_result_version && bodyText.includes(chain.degraded_result_version)) },
        { label: "degraded_reason_visible", ok: !chain.degraded_result_visible || /skipped_missing_facts|缺事实|degraded|降级|partial_provider/.test(bodyText) },
        { label: "last_good_retention_visible", ok: !chain.degraded_result_visible || /last-good|current\/last-good|保留上一条|不覆盖 current/.test(bodyText) },
        { label: "stale_overwrite_guard_visible", ok: !chain.degraded_result_visible || /旧任务不能覆盖|不覆盖 current|symbol \\+ result_version|覆盖保护/.test(bodyText) },
        { label: "result_version_label", ok: /结果版本|result_version/i.test(bodyText) },
        { label: "tushare_source_visible", ok: /Tushare|真实数据链|数据来源/.test(bodyText) },
        { label: "deepseek_boundary_visible", ok: /DeepSeek|模型解释|解释状态/.test(bodyText) },
        { label: "no_trade_boundary_visible", ok: /不交易|不下单|不改(写)?(交易策略| strategy action|操作区)|不构成交易指令/.test(bodyText) },
      ];
      const missing = textChecks.filter((item) => !item.ok).map((item) => item.label);
      return {
        check: "search_quant_same_result_chain_visible",
        passed: missing.length === 0,
        evidence: [
          `symbol=${chain.symbol}`,
          `task_id=${chain.task_id || "missing"}`,
          `result_version=${chain.result_version}`,
          `provider_call_ledger_count=${chain.provider_call_ledger_count || 0}`,
          `data_date=${chain.data_date || "missing"}`,
          `freshness_state=${chain.freshness_state || "missing"}`,
          `model_ledger_id=${chain.model_ledger_id || "missing"}`,
          `current_result_matches_latest_task=${chain.current_result_matches_latest_task === true}`,
          `old_task_can_overwrite_current=${chain.old_task_can_overwrite_current === true}`,
          `degraded_result_visible=${chain.degraded_result_visible === true}`,
          `degraded_symbol=${chain.degraded_symbol || "missing"}`,
          `degraded_result_version=${chain.degraded_result_version || "missing"}`,
          `degraded_reason=${chain.degraded_reason || "missing"}`,
          `scenario=${chain.scenario || "live"}`
        ],
        missing,
        candidate_result_chain: chain
      };
    }, candidateResultChain);
  }
  if (route !== "#marginEtf") {
    return {
      check: "generic_route_heading_visible",
      passed: true,
      evidence: ["generic route heading and task-silence checks apply"],
      missing: []
    };
  }
  return page.evaluate(() => {
    const isVisible = (element) => {
      if (!element) return false;
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0.01;
    };
    const selectorChecks = [
      { selector: '[aria-label="margin etf app visible now summary"]', label: "app_visible_now_summary" },
      { selector: '[aria-label="margin etf candidate radar confirmed data bridge"]', label: "confirmed_data_bridge_card" },
      { selector: '[aria-label="return candidate radar confirm input from margin etf data bridge"]', label: "return_confirm_input_link" },
      { selector: '[aria-label="open factor from margin etf data bridge"]', label: "open_factor_link" },
      { selector: '[aria-label="open next session from margin etf data bridge"]', label: "open_next_link" },
      { selector: '[aria-label="open data capability from margin etf data bridge"]', label: "open_data_capability_link" }
    ];
    const visibleMissing = selectorChecks
      .filter((item) => !isVisible(document.querySelector(item.selector)))
      .map((item) => item.label);
    const bodyText = (document.body?.innerText || "").replace(/\s+/g, " ");
    const textChecks = [
      { label: "confirmed_bridge_heading", pattern: /确认结果承接/ },
      { label: "confirmed_symbol_field", pattern: /当前确认标的/ },
      { label: "source_and_date_fields", pattern: /数据来源/ },
      { label: "tushare_chain_field", pattern: /Tushare 数据链/ },
      { label: "result_version_field", pattern: /结果版本/ },
      { label: "same_provider_ledger_field", pattern: /同源账本/ },
      { label: "deepseek_explanation_field", pattern: /DeepSeek 解释/ },
      { label: "etf_margin_handoff_field", pattern: /ETF\/融资承接/ },
      { label: "read_boundary_field", pattern: /读取边界/ },
      { label: "no_task_on_open_boundary", pattern: /不会因为打开 ETF\/融资页而创建 task/ },
      { label: "no_provider_model_trade_boundary", pattern: /调用 Tushare\/DeepSeek、启动 worker、交易、加融资或改写 strategy action/ }
    ];
    const textMissing = textChecks.filter((item) => !item.pattern.test(bodyText)).map((item) => item.label);
    const missing = [...visibleMissing, ...textMissing];
    return {
      check: "margin_etf_confirmed_data_bridge_visible",
      passed: missing.length === 0,
      evidence: [
        "margin ETF visible-now summary rendered",
        "confirmed data bridge rendered before local refresh/audit details",
        "factor/next/data-capability/candidate links are local anchors",
        "Tushare/result-version/provider-ledger/DeepSeek/boundary labels are visible"
      ],
      missing
    };
  });
}

async function typeWithoutSubmit(page) {
  const target = await page.evaluate(() => {
    const isVisible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0.01;
    };
    const isEditableTextInput = (element) => {
      if (!(element instanceof HTMLInputElement) && !(element instanceof HTMLTextAreaElement)) return false;
      if (element.disabled || element.readOnly) return false;
      if (element instanceof HTMLTextAreaElement) return true;
      const type = (element.getAttribute("type") || "text").toLowerCase();
      return !["button", "checkbox", "color", "file", "hidden", "image", "radio", "range", "reset", "submit"].includes(type);
    };
    document.querySelectorAll("[data-user-route-qa-input]").forEach((element) => element.removeAttribute("data-user-route-qa-input"));
    const input = Array.from(document.querySelectorAll("input, textarea")).find((element) => isVisible(element) && isEditableTextInput(element));
    if (!input) return { found: false, selector: "", reason: "no_editable_visible_input" };
    input.setAttribute("data-user-route-qa-input", "true");
    const label = input.getAttribute("aria-label") || input.getAttribute("placeholder") || input.getAttribute("name") || input.id || input.tagName.toLowerCase();
    return { found: true, selector: label, reason: "editable_visible_input_found" };
  });
  if (!target.found) return { typed: false, selector: "", reason: target.reason };
  await page.locator("[data-user-route-qa-input='true']").first().fill("000001.SZ");
  await page.waitForTimeout(150);
  return { typed: true, selector: target.selector || "first editable visible input/textarea", reason: "typed_editable_visible_input" };
}

async function runQa(args) {
  if (!isLocalUrl(args.baseUrl) || !isLocalUrl(args.apiBase)) {
    throw new Error("base-url and api-base must be local 127.0.0.1/localhost URLs");
  }
  const { chromium } = requirePlaywright();
  const routes = selectedRoutes(args);
  const runId = timestampId();
  const outputDir = resolve(args.artifactRoot, runId);
  await mkdir(outputDir, { recursive: true });
  const liveCandidateEnvelope = await fetchCandidateCacheEnvelope(args.apiBase).catch(() => ({ ok: false, data: {} }));
  const candidateScenarioEnvelope = buildCandidateEnvelopeForScenario(
    liveCandidateEnvelope,
    args.candidateResultScenario
  );
  const browser = await chromium.launch(chromiumLaunchOptions());
  const rows = [];
  const errors = [];
  try {
    for (const viewport of QA_VIEWPORTS) {
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
      const page = await context.newPage();
      if (args.candidateResultScenario !== "live") {
        await page.route("**/api/candidate-radar/cache", async (routeHandle) =>
          routeHandle.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(candidateScenarioEnvelope)
          })
        );
      }
      page.on("console", (message) => {
        if (message.type() === "error") errors.push({ viewport: viewport.name, console_error: message.text() });
      });
      page.on("pageerror", (error) => errors.push({ viewport: viewport.name, page_error: String(error.message || error) }));
      for (const route of routes) {
        const beforeTaskCount = await fetchTaskCount(args.apiBase);
        const startedAt = Date.now();
        const url = `${args.baseUrl.replace(/\/$/, "")}/${route.route}`;
        await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
        await page.waitForSelector("h1, h2, h3", { state: "attached", timeout: 10000 });
        await page.waitForTimeout(800);
        const candidateResultChain = await fetchCandidateResultChain(
          args.apiBase,
          args.candidateResultScenario !== "live" ? candidateScenarioEnvelope : null,
          args.candidateResultScenario
        );
        const inspected = await inspectPage(page);
        const routeSpecific = await inspectRouteSpecific(page, route.route, candidateResultChain);
        const typing = await typeWithoutSubmit(page);
        const afterTaskCount = await fetchTaskCount(args.apiBase);
        const screenshotPath = resolve(outputDir, viewport.name, `${route.route.replace("#", "") || "home"}.png`);
        if (args.screenshots) {
          await mkdir(resolve(outputDir, viewport.name), { recursive: true });
          await page.screenshot({ path: screenshotPath, fullPage: false });
        }
        const elapsedMs = Date.now() - startedAt;
        const noTaskCreated = afterTaskCount === beforeTaskCount;
        const typingRequired = inspected.editable_visible_input_count > 0;
        const typingCovered = !typingRequired || typing.typed === true;
        const passed =
          Boolean(inspected.route_heading) &&
          inspected.clipped_count === 0 &&
          inspected.disabled_buttons_without_reason_count === 0 &&
          noTaskCreated &&
          typingCovered &&
          routeSpecific.passed;
        rows.push({
          route: route.route,
          label: route.label,
          viewport: viewport.name,
          width: viewport.width,
          height: viewport.height,
          url,
          focus: route.focus,
          status: passed ? "passed" : "review_required",
          route_heading: inspected.route_heading,
          first_viewport_element_count: inspected.first_viewport_element_count,
          clipped_count: inspected.clipped_count,
          clipped_rows: inspected.clipped_rows,
          audit_noise_count: inspected.audit_noise_count,
          audit_noise_text: inspected.audit_noise_text,
          route_specific_check: routeSpecific.check,
          route_specific_check_passed: routeSpecific.passed,
          route_specific_evidence: routeSpecific.evidence,
          route_specific_missing: routeSpecific.missing,
          candidate_result_chain: routeSpecific.candidate_result_chain || null,
          candidate_result_scenario: args.candidateResultScenario,
          candidate_result_scenario_replay: args.candidateResultScenario !== "live",
          disabled_buttons_without_reason_count: inspected.disabled_buttons_without_reason_count,
          disabled_buttons_without_reason: inspected.disabled_buttons_without_reason,
          visible_input_count: inspected.visible_input_count,
          editable_visible_input_count: inspected.editable_visible_input_count,
          typing_required: typingRequired,
          typing_covered: typingCovered,
          typed_without_submit: typing.typed,
          typing_selector: typing.selector,
          typing_reason: typing.reason,
          task_count_before: beforeTaskCount,
          task_count_after: afterTaskCount,
          task_created_by_render_or_typing: !noTaskCreated,
          route_observed_ms: elapsedMs,
          screenshot_path: args.screenshots ? screenshotPath : null,
          visual_qa_complete: passed,
          typing_silence_verified: noTaskCreated
        });
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }
  const reviewRows = rows.filter((row) => row.status !== "passed");
  const routeSpecificReviewRows = rows.filter((row) => row.route_specific_check_passed === false);
  const marginEtfBridgeRows = rows.filter((row) => row.route === "#marginEtf" && row.route_specific_check === "margin_etf_confirmed_data_bridge_visible");
  const marginEtfBridgePassed = marginEtfBridgeRows.length > 0 && marginEtfBridgeRows.every((row) => row.route_specific_check_passed === true);
  const report = {
    schema_version: SCHEMA_VERSION,
    status: reviewRows.length || errors.length ? "user_route_qa_review_required" : "user_route_qa_passed",
    scope: "explicit_local_ordinary_route_browser_qa",
    run_id: runId,
    generated_at: new Date().toISOString(),
    base_url: args.baseUrl,
    api_base: args.apiBase,
    candidate_result_scenario: args.candidateResultScenario,
    candidate_result_scenario_replay: args.candidateResultScenario !== "live",
    candidate_result_scenario_writes_cache: false,
    artifact_root: args.artifactRoot,
    output_dir: outputDir,
    route_count: routes.length,
    viewport_count: QA_VIEWPORTS.length,
    qa_matrix_count: rows.length,
    passed_count: rows.length - reviewRows.length,
    review_required_count: reviewRows.length,
    route_specific_review_required_count: routeSpecificReviewRows.length,
    margin_etf_confirmed_bridge_row_count: marginEtfBridgeRows.length,
    margin_etf_confirmed_bridge_passed: marginEtfBridgePassed,
    console_error_count: errors.length,
    visual_qa_complete: reviewRows.length === 0 && errors.length === 0,
    typing_silence_verified: rows.every((row) => row.task_created_by_render_or_typing === false && row.typing_covered === true),
    production_replacement_complete: false,
    streamlit_fallback_retirement_ready: false,
    rows,
    errors,
    cache_only: true,
    starts_no_servers: true,
    local_urls_only: true,
    screenshots_are_not_tracked: true,
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    note: "Local ordinary-route browser QA evidence. It is not provider/model evidence, not remote CI, and not Streamlit retirement proof."
  };
  const reportPath = resolve(outputDir, "user_route_qa_report.json");
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  return { report, reportPath };
}

const args = parseArgs(process.argv);
if (args.printPlan) {
  console.log(JSON.stringify(makePlan(args), null, 2));
  process.exit(0);
}

try {
  const { report, reportPath } = await runQa(args);
  if (args.json) {
    console.log(JSON.stringify({ ...report, report_path: reportPath }, null, 2));
  } else {
    console.log(`user_route_qa_runner: ${report.status}`);
    console.log(`rows: ${report.qa_matrix_count}; passed: ${report.passed_count}; review_required: ${report.review_required_count}; console_errors: ${report.console_error_count}`);
    console.log(`typing_silence_verified: ${report.typing_silence_verified}`);
    console.log(`report: ${reportPath}`);
    console.log("external_calls_triggered: false; tushare_called: false; deepseek_called: false; github_called: false; does_not_execute_trades: true");
  }
  process.exit(report.status === "user_route_qa_passed" ? 0 : 1);
} catch (error) {
  const message = error && error.message ? error.message : String(error);
  console.error(`user_route_qa_runner: failed: ${message}`);
  console.error("Start local FastAPI/Vite first. The runner resolves Playwright from desktop/node_modules when available; set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH only if no system Chrome/Chromium is installed.");
  process.exit(1);
}
