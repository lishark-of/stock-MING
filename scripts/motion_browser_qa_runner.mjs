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
import { createHash, createHmac, randomBytes } from "node:crypto";
import { execFileSync } from "node:child_process";
import { constants as fsConstants } from "node:fs";
import { chmod, lstat, mkdir, open, readFile, readdir, realpath, rename, stat, unlink } from "node:fs/promises";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { inflateSync } from "node:zlib";

const require = createRequire(import.meta.url);

const SCHEMA_VERSION = "command_center_3_motion_browser_qa_result.v6";
const TRACE_SCHEMA_VERSION = "command_center_3_motion_browser_performance_trace.v5";
const STATE_SCHEMA_VERSION = "command_center_3_motion_runner_attestation_state.v3";
const EVENT_SCHEMA_VERSION = "command_center_3_motion_runner_attestation_event.v3";
const ANCHOR_SCHEMA_VERSION = "command_center_3_motion_runner_high_water_anchor.v2";
const IDENTITY_SCHEMA_VERSION = "command_center_3_motion_runner_installation_identity.v1";
const TERMINAL_SCHEMA_VERSION = "command_center_3_motion_runner_terminal_high_water.v1";
const DIST_MANIFEST_SCHEMA_VERSION = "command_center_3_motion_dist_manifest.v1";
const SERVICE_IDENTITY_SCHEMA_VERSION = "command_center_3_motion_frontend_service_identity.v1";
const PACKAGE_BINDING_SCHEMA_VERSION = "command_center_3_motion_package_binding.v1";
const FASTAPI_IDENTITY_SCHEMA_VERSION = "command_center_3_motion_fastapi_service_identity.v1";
const DEFAULT_BASE_URL = "http://127.0.0.1:4173";
const DEFAULT_ARTIFACT_ROOT = ".stock_ming_3/motion_qa";
const TRUST_DIR_NAME = ".runner_attestation_v4";
const IDENTITY_FILE_NAME = ".runner_installation_identity.json";
const TERMINAL_FILE_NAME = ".runner_terminal_high_water.json";
const PROJECT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const FRONTEND_ROOT = resolve(PROJECT_ROOT, "desktop");
const HEX_HEAD = /^[0-9a-f]{40}$/;
const HEX_64 = /^[0-9a-f]{64}$/;
const ALLOWED_LOCAL_HOSTS = new Set(["127.0.0.1", "localhost"]);
const ALLOWED_LOCAL_PORTS = new Set(["4173", "8710"]);
const ALLOWED_READ_METHODS = new Set(["GET"]);
const NETWORK_IDLE_TIMEOUT_MS = 20000;
const NETWORK_QUIET_WINDOW_MS = 250;
const CANONICAL_TEST_VECTOR = { a: [0, 1, 500000, 100000], b: { enabled: true, name: "动效" }, z: null };
const CANONICAL_TEST_JSON = "{\"a\":[0,1,500000,100000],\"b\":{\"enabled\":true,\"name\":\"动效\"},\"z\":null}";
const CANONICAL_TEST_SHA256 = "d2f24c1ce9fd8f27a693ba2e09f7291c2535eb30f5e037e2627c1a928e3ddb1b";
const MAX_PNG_FILE_BYTES = 16 * 1024 * 1024;
const MAX_PNG_IDAT_BYTES = 12 * 1024 * 1024;
const MAX_PNG_DECODED_BYTES = 64 * 1024 * 1024;
const MAX_FASTAPI_RESPONSE_BYTES = 32 * 1024 * 1024;
const FASTAPI_RESPONSE_SEMANTIC_SCHEMA_VERSION = "command_center_3_motion_fastapi_response_semantic.v2";
const FASTAPI_CACHE_ENDPOINT_COUNT = 19;

const FASTAPI_CACHE_CONTRACTS = new Map([
  ["/api/audit/cache", { schema: "call_ledger_audit_cache.v1", packet: "command_center_3_call_ledger_audit_cache", ledgerApis: ["local_call_ledger_audit_cache"] }],
  ["/api/audit/user-route-qa", { schema: "command_center_3_user_route_qa_evidence_cache.v1", packet: "command_center_3_user_route_qa_evidence_cache", ledgerApis: ["GET /api/audit/user-route-qa"] }],
  ["/api/bootstrap/status", { schema: "command_center_bootstrap_runtime_mode.v1", packet: "command_center_3_bootstrap_runtime_mode_packet", ledgerApis: ["local_bootstrap_runtime_mode_cache"] }],
  ["/api/desktop/preflight-cache", { schema: "desktop_shell_preflight_cache.v1", packet: "command_center_3_desktop_shell_preflight_cache", ledgerApis: [
    "local_desktop_shell_preflight_cache", "local_tauri_release_manifest_contract", "local_one_click_startup_summary",
    "local_p0_frontend_backend_connection_receipt", "local_p0_ordinary_connection_rows", "local_p0_post_startup_readback_rows",
    "local_p0_failure_diagnostic_rows", "local_p0_to_p1_ordinary_handoff_rows", "local_p0_ordinary_reconnect_rows",
    "local_p0_launcher_check_only_rows", "local_p0_ordinary_quick_action_rows", "local_p0_current_next_action_rows",
    "local_p0_startup_30s_quick_read_rows", "local_p0_ordinary_one_screen_rows", "local_command_center_3_launcher_contract",
    "local_tauri_production_package_readiness_receipt", "local_tauri_package_durable_evidence_recipe"
  ] }],
  ["/api/factor-quant/cache", { schema: "factor_quant_hub.v1", packet: "command_center_factor_quant_hub_packet", ledgerApis: [
    "local_factor_quant_cache", "local_factor_universe_rank_zscore_dry_run", "local_factor_universe_execution_readiness_receipt",
    "local_factor_universe_execution_activation_receipt", "local_factor_universe_worker_batch_execution_recipe",
    "local_factor_universe_worker_batch_execution_request", "local_factor_universe_worker_batch_research_receipt",
    "local_factor_universe_durable_evidence_recipe", "local_deepseek_production_activation_receipt",
    "local_deepseek_provider_benchmark_execution_recipe", "local_deepseek_provider_benchmark_scope_ticket",
    "local_deepseek_provider_benchmark_execution_request", "local_deepseek_durable_evidence_recipe",
    "local_factor_test_storage_query_consumption", "local_factor_test_local_dataset_sample_evidence",
    "local_factor_test_production_validation_qa_contract", "local_factor_test_provider_validation_blocker_audit",
    "local_factor_test_provider_sample_readiness_receipt", "local_factor_test_provider_sample_activation_receipt",
    "local_factor_test_provider_small_pool_execution_recipe", "local_factor_test_provider_small_pool_execution_request",
    "local_factor_test_provider_small_pool_forward_return_label_audit", "local_factor_test_provider_small_pool_metric_validation_audit",
    "local_factor_test_provider_small_pool_pit_bias_audit", "local_factor_test_durable_evidence_recipe",
    "local_factor_test_production_stage_scope_manifest"
  ] }],
  ["/api/next-session/cache", { schema: "next_session_operation_projection.v1", packet: "command_center_next_session_projection_packet", allowCacheMissing: true, includeMissingData: true, ledgerApis: [
    "local_next_session_cache", "local_next_session_browser_qa_review", "local_next_session_streamlit_parity_review",
    "local_next_session_production_promotion_review", "local_next_session_candidate_radar_p3_handoff",
    "local_next_session_durable_evidence_recipe", "local_next_session_production_stage_scope_manifest"
  ] }],
  ["/api/position/cache", { schema: "position_context_cache.v1", packet: "command_center_3_position_context_cache", ledgerApis: ["local_position_context_cache"] }],
  ["/api/candidate-radar/cache", { schema: "candidate_radar_cache.v1", packet: "command_center_3_candidate_radar_cache", ledgerApis: [
    "local_candidate_radar_cache", "local_candidate_radar_legacy_parity_acceptance_receipt",
    "local_candidate_radar_production_activation_receipt", "local_candidate_radar_quant_projection_execution_request",
    "local_candidate_radar_provider_parity_execution_request", "local_candidate_radar_worker_execution_recipe",
    "local_candidate_radar_worker_execution_request", "local_candidate_radar_full_pool_worker_fallback_preview",
    "local_candidate_radar_deep_scan_worker_fallback_preview", "local_candidate_radar_worker_runtime_linked_evidence",
    "local_candidate_radar_next_execution_recipe", "local_candidate_radar_durable_evidence_recipe",
    "local_candidate_radar_production_replacement_review_preview", "local_candidate_radar_production_promotion_dry_run_preview",
    "local_candidate_radar_legacy_retirement_review_preview", "local_candidate_radar_production_promotion_review_preview",
    "local_candidate_radar_production_stage_scope_manifest"
  ] }],
  ["/api/storage", { schema: "command_center_3_storage_overview.v1", ledgerApis: ["local_storage_overview_cache"] }],
  ["/api/storage/catalog", { schema: "command_center_3_storage_dataset_catalog.v1", ledgerApis: ["local_storage_dataset_catalog_cache"] }],
  ["/api/storage/current-result", { schema: "command_center_3_storage_current_result_cache.v1", ledgerApis: ["local_storage_current_result_cache"] }],
  ["/api/data-health/cache", { schema: "data_health_timeline_cache.v1", packet: "command_center_3_data_health_timeline_cache", ledgerApis: ["local_data_health_timeline_cache", "local_freshness_durable_evidence_recipe"] }],
  ["/api/tasks", { schema: "command_center_3_task_status_index.v1", packet: "command_center_3_task_status_index", historicalTaskSummary: true, ledgerApis: ["local_task_status_index"] }],
  ["/api/tasks/catalog", { schema: "command_center_3_task_catalog.v1", packet: "command_center_3_task_catalog", ledgerApis: ["local_task_catalog_cache"] }],
  ["/api/worker/cache", { schema: "worker_runtime_cache.v1", packet: "command_center_3_worker_runtime_cache", ledgerApis: [
    "local_worker_runtime_cache", "local_worker_queue_routing_contract", "local_worker_production_readiness_receipt",
    "local_worker_production_activation_receipt", "local_worker_runtime_qa_execution_recipe",
    "local_worker_runtime_qa_execution_request", "local_worker_runtime_qa_dry_run", "local_worker_runtime_qa_execution",
    "local_worker_runtime_durable_evidence_recipe"
  ] }],
  ["/api/packets", { schema: "command_center_3_packet_index.v1", ledgerApis: ["local_packet_registry_cache"] }],
  ["/api/packets/command_center_etf_packet", { packet: "command_center_etf_packet", allowCacheMissing: true, packetDetail: true, ledgerApis: ["local_packet_cache_read"] }],
  ["/api/packets/command_center_margin_packet", { packet: "command_center_margin_packet", allowCacheMissing: true, packetDetail: true, ledgerApis: ["local_packet_cache_read"] }],
  ["/api/packets/command_center_margin_etf_refresh_receipt", { packet: "command_center_margin_etf_refresh_receipt", allowCacheMissing: true, packetDetail: true, ledgerApis: ["local_packet_cache_read"] }]
]);

const QA_ROUTES = [
  { route: "#home", navigation_hash: "#home/home-p1-symbol-confirm", label: "Command Center", heading: "今日作战台", anchor: "#home-p1-symbol-confirm", marker: "state_rail", marker_minimum: 1, risk_focus: "page staging and status summary clarity" },
  { route: "#next-session-chart", label: "Next Session Map", heading: "次日图谱", anchor: "#next-session-chart", marker: "route_stage", marker_minimum: 1, risk_focus: "chart update clarity and reduced-motion chart updates" },
  { route: "#candidates", navigation_hash: "#candidates/candidate-pool", label: "Candidate Radar", heading: "下一票雷达", anchor: "#candidate-pool", marker: "radar_cluster", marker_minimum: 1, risk_focus: "radar result cluster and runtime-budget visibility" },
  { route: "#worker", label: "Worker Runtime", heading: "Worker 运行时", anchor: ".route-stage", marker: "route_stage", marker_minimum: 1, risk_focus: "runtime evidence visibility and production-blocker readability" },
  { route: "#tasks", label: "Task Monitor", heading: "Task Monitor / 任务监控", anchor: ".route-stage", marker: "route_stage", marker_minimum: 1, risk_focus: "task phase confirmation and progress readability" },
  { route: "#audit", label: "Call Ledger Audit", heading: "调用审计", anchor: ".route-stage", marker: "route_stage", marker_minimum: 1, risk_focus: "motion audit rows and warning density" }
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
  route_transition_observed_us: 500000,
  largest_motion_layout_shift_ppm: 100000,
  long_task_over_50ms_count: 0,
  candidate_radar_first_stable_us: 1200000
};

function parseArgs(argv) {
  const args = {
    baseUrl: DEFAULT_BASE_URL,
    artifactRoot: DEFAULT_ARTIFACT_ROOT,
    route: null,
    screenshots: true,
    reducedMotion: false,
    expectedHeadFull: null,
    json: false,
    printPlan: false,
    selfTestFastApiValidator: false,
    initializeRunnerTrust: false
  };
  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--base-url") args.baseUrl = argv[++index] || args.baseUrl;
    else if (arg === "--out") args.artifactRoot = argv[++index] || args.artifactRoot;
    else if (arg === "--route") args.route = argv[++index] || args.route;
    else if (arg === "--no-screenshots") args.screenshots = false;
    else if (arg === "--reduced-motion") args.reducedMotion = true;
    else if (arg === "--expected-head-full") args.expectedHeadFull = argv[++index] || null;
    else if (arg === "--json") args.json = true;
    else if (arg === "--print-plan") args.printPlan = true;
    else if (arg === "--self-test-fastapi-validator") args.selfTestFastApiValidator = true;
    else if (arg === "--initialize-runner-trust") args.initializeRunnerTrust = true;
    else if (arg === "--help") {
      console.log("Usage: node scripts/motion_browser_qa_runner.mjs --expected-head-full <40-hex> [--base-url http://127.0.0.1:4173] [--reduced-motion] [--initialize-runner-trust] [--self-test-fastapi-validator] [--json] [--print-plan]");
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

function sortedValue(value) {
  if (Array.isArray(value)) return value.map(sortedValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortedValue(value[key])]));
  }
  if (typeof value === "number" && !Number.isSafeInteger(value)) {
    throw new Error("Motion evidence canonical JSON permits safe integers only");
  }
  return value;
}

function canonicalJson(value) {
  return JSON.stringify(sortedValue(value));
}

function sha256Bytes(value) {
  return createHash("sha256").update(value).digest("hex");
}

function objectDigest(value) {
  return sha256Bytes(Buffer.from(canonicalJson(value), "utf8"));
}

function verifyCanonicalVector() {
  if (canonicalJson(CANONICAL_TEST_VECTOR) !== CANONICAL_TEST_JSON || objectDigest(CANONICAL_TEST_VECTOR) !== CANONICAL_TEST_SHA256) {
    throw new Error("Node motion canonicalization self-test failed");
  }
}

function exactLocalUrl(rawUrl) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    throw new Error(`Motion QA URL is invalid: ${rawUrl}`);
  }
  if (
    parsed.protocol !== "http:" || !ALLOWED_LOCAL_HOSTS.has(parsed.hostname) ||
    !ALLOWED_LOCAL_PORTS.has(parsed.port) || parsed.username || parsed.password
  ) {
    throw new Error(`Motion QA URL is outside the exact local allowlist: ${parsed.protocol}//${parsed.hostname}:${parsed.port}`);
  }
  return parsed;
}

const CURRENT_FALSE_FLAGS = [
  "external", "external_calls_triggered", "readback_external_calls_triggered",
  "cache_api_external_calls_triggered", "page_render_external_calls",
  "provider_or_model_calls", "provider_called", "model_called", "worker_called",
  "tushare_called", "deepseek_called", "github_called", "trade_called",
  "trading_called", "broker_called", "order_called", "real_trading_enabled"
];
const CURRENT_TRUE_FLAGS = ["does_not_execute_trades", "does_not_modify_strategy_action"];
const HISTORICAL_FLAG_NAMES = new Set([
  "external_calls_triggered", "tushare_called", "deepseek_called", "github_called",
  "provider_or_model_calls", "provider_called", "model_called", "worker_called",
  "trade_called", "trading_called", "broker_called", "order_called"
]);
const FORBIDDEN_SECRET_KEYS = new Set([
  "api_key", "apikey", "api_token", "access_key", "access_token", "refresh_token", "authorization",
  "password", "passwd", "secret", "token", "credential", "client_secret", "private_key",
  "bearer_token", "cookie", "set_cookie"
]);

function safeRecord(value) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function secretBearingFieldCount(value) {
  if (!value || typeof value !== "object") return 0;
  let count = 0;
  for (const [rawKey, child] of Object.entries(value)) {
    const key = rawKey.toLowerCase().replace(/[ -]/g, "_");
    const benignNegativeDisclosure = key === "contains_secret" && child === false;
    if (!benignNegativeDisclosure && (FORBIDDEN_SECRET_KEYS.has(key) || [...FORBIDDEN_SECRET_KEYS].some(name => key.endsWith(`_${name}`)))) count += 1;
    if (key === "contains_secret" && child === true) count += 1;
    if (typeof child === "string" && (/^\s*(bearer|basic)\s+\S+/i.test(child) || child.includes("-----BEGIN PRIVATE KEY-----"))) count += 1;
    count += secretBearingFieldCount(child);
  }
  return count;
}

function nonLocalUrlCount(value) {
  if (!value || typeof value !== "object") return 0;
  let count = 0;
  for (const child of Object.values(value)) {
    if (typeof child === "string" && /^https?:\/\//i.test(child)) {
      try {
        const parsed = new URL(child);
        if (!ALLOWED_LOCAL_HOSTS.has(parsed.hostname)) count += 1;
      } catch { count += 1; }
    } else count += nonLocalUrlCount(child);
  }
  return count;
}

function flagViolationCount(record, names, expected) {
  if (!safeRecord(record)) return 1;
  return names.reduce((count, name) => {
    if (!Object.prototype.hasOwnProperty.call(record, name)) return count;
    return count + (typeof record[name] !== "boolean" || record[name] !== expected ? 1 : 0);
  }, 0);
}

function historicalProvenanceCount(value, topLevel = false) {
  if (!value || typeof value !== "object") return 0;
  let count = 0;
  for (const [name, child] of Object.entries(value)) {
    if (!topLevel && HISTORICAL_FLAG_NAMES.has(name) && child === true) count += 1;
    count += historicalProvenanceCount(child, false);
  }
  return count;
}

function exactCacheMissingError(error, endpoint, packetKey) {
  return Boolean(safeRecord(error) && canonicalJson(Object.keys(error).sort()) === canonicalJson(["code", "details", "message"]) &&
    error.code === "cache_missing" && typeof error.message === "string" && error.message.length > 0 &&
    safeRecord(error.details) && canonicalJson(Object.keys(error.details).sort()) === canonicalJson(["cache_source", "packet_key", "route"]) &&
    error.details.cache_source === "cache_missing" && error.details.packet_key === packetKey &&
    (error.details.route === endpoint || (endpoint.startsWith("/api/packets/") && error.details.route === "GET /api/packets/{packet_key}")));
}

function endpointDataIdentityValid(data, contract) {
  if (!safeRecord(data)) return false;
  if (contract.schema && data.schema_version !== contract.schema) return false;
  if (contract.packet && data.packet_key !== contract.packet) return false;
  return true;
}

function taskHistorySummaryValid(data) {
  if (!safeRecord(data) || data.readback_external_calls_triggered !== false) return false;
  const pairs = [
    ["external_calls_triggered", "call_ledger_external_calls_replayed"],
    ["tushare_called", "call_ledger_tushare_replayed"],
    ["deepseek_called", "call_ledger_deepseek_replayed"],
    ["github_called", "call_ledger_github_replayed"]
  ];
  return pairs.every(([historical, replayed]) =>
    typeof data[historical] === "boolean" && typeof data[replayed] === "boolean" && (!data[historical] || data[replayed]));
}

function ledgerAnalysis(ledger, endpoint, contract) {
  let currentExternal = 0;
  let currentProvider = 0;
  let currentModel = 0;
  let currentWorker = 0;
  let currentTrade = 0;
  let taskPosts = 0;
  let rowsTyped = true;
  let sourcesAllowlisted = true;
  const contractRows = [];
  const expectedApis = contract?.ledgerApis || (endpoint === "/health" ? ["local_health_check"] : []);
  if (FASTAPI_CACHE_CONTRACTS.size !== FASTAPI_CACHE_ENDPOINT_COUNT || !ledger.length || ledger.length > expectedApis.length) {
    sourcesAllowlisted = false;
  }
  let previousApiPosition = -1;
  for (let index = 0; index < ledger.length; index += 1) {
    const row = ledger[index];
    if (!safeRecord(row)) { rowsTyped = false; continue; }
    const api = row.api;
    const apiPosition = typeof api === "string" ? expectedApis.indexOf(api) : -1;
    if (apiPosition < 0 || (index === 0 && apiPosition !== 0) || apiPosition <= previousApiPosition) sourcesAllowlisted = false;
    previousApiPosition = apiPosition;
    if (nonLocalUrlCount(row) > 0) sourcesAllowlisted = false;
    const external = row.external !== false || flagViolationCount(row, ["external_calls_triggered"], false) > 0;
    const provider = flagViolationCount(row, ["provider_or_model_calls", "provider_called", "tushare_called"], false) > 0;
    const model = flagViolationCount(row, ["model_called", "deepseek_called", "github_called"], false) > 0;
    const worker = flagViolationCount(row, ["worker_called"], false) > 0;
    const trade = flagViolationCount(row, ["trade_called", "trading_called", "broker_called", "order_called", "real_trading_enabled"], false) > 0 ||
      flagViolationCount(row, CURRENT_TRUE_FLAGS, true) > 0;
    const method = String(row.method || row.request_method || "").toUpperCase();
    const taskPost = method === "POST" || (typeof api === "string" && api.startsWith("POST /api/"));
    const secret = secretBearingFieldCount(row) > 0;
    if (external) currentExternal += 1;
    if (provider) currentProvider += 1;
    if (model) currentModel += 1;
    if (worker) currentWorker += 1;
    if (trade) currentTrade += 1;
    if (taskPost) taskPosts += 1;
    contractRows.push({
      api, source: endpoint, method: "GET", path: endpoint,
      external, provider, model, worker, trade, task_post: taskPost, secret
    });
  }
  return { currentExternal, currentProvider, currentModel, currentWorker, currentTrade, taskPosts, rowsTyped, sourcesAllowlisted, contractRows };
}

function analyzeFastApiResponse(value, { endpoint, method, statusCode, bodySha256, bodySizeBytes, health = false }) {
  const contract = health ? null : FASTAPI_CACHE_CONTRACTS.get(endpoint);
  const closedSchema = Boolean(safeRecord(value) &&
    canonicalJson(Object.keys(value).sort()) === canonicalJson(["call_ledger", "data", "error", "ok", "warnings"]));
  const warningsValid = closedSchema && Array.isArray(value.warnings) && value.warnings.every(item => typeof item === "string");
  const ledger = closedSchema && Array.isArray(value.call_ledger) ? value.call_ledger : [];
  const ledgerResult = ledgerAnalysis(ledger, endpoint, contract);
  const cacheMissing = Boolean(contract?.allowCacheMissing && value?.ok === false && exactCacheMissingError(value.error, endpoint, contract.packet));
  const envelopeState = cacheMissing ? "cache_missing" : value?.ok === true && value?.error === null ? "ok" : "invalid";
  const dataIdentity = health
    ? Boolean(fastApiHealthContract(value))
    : cacheMissing && !contract?.includeMissingData
      ? value.data === null
      : endpointDataIdentityValid(value.data, contract || {});
  const data = safeRecord(value?.data) ? value.data : {};
  let dataCurrentReadFlagsValid = true;
  if (!health) {
    dataCurrentReadFlagsValid = contract?.historicalTaskSummary
      ? taskHistorySummaryValid(data) && flagViolationCount(data, ["readback_external_calls_triggered"], false) === 0
      : contract?.packetDetail
        ? flagViolationCount(data, ["readback_external_calls_triggered", "cache_api_external_calls_triggered", "page_render_external_calls"], false) === 0
      : flagViolationCount(data, CURRENT_FALSE_FLAGS, false) === 0;
    if (flagViolationCount(data, CURRENT_TRUE_FLAGS, true) > 0) dataCurrentReadFlagsValid = false;
  }
  const secretCount = secretBearingFieldCount(value);
  const summary = {
    schema_version: FASTAPI_RESPONSE_SEMANTIC_SCHEMA_VERSION,
    endpoint,
    method,
    status_code: statusCode,
    raw_body_sha256: bodySha256,
    raw_body_size_bytes: bodySizeBytes,
    envelope_state: envelopeState,
    envelope_ok: value?.ok === true,
    error_code: cacheMissing ? "cache_missing" : "",
    data_schema_version: typeof data.schema_version === "string" ? data.schema_version : "",
    data_packet_key: typeof data.packet_key === "string" ? data.packet_key : "",
    ledger_count: ledger.length,
    ledger_rows_typed: ledgerResult.rowsTyped,
    ledger_sources_allowlisted: ledgerResult.sourcesAllowlisted,
    ledger_current_external_count: ledgerResult.currentExternal,
    ledger_current_provider_count: ledgerResult.currentProvider,
    ledger_current_model_count: ledgerResult.currentModel,
    ledger_current_worker_count: ledgerResult.currentWorker,
    ledger_current_trade_count: ledgerResult.currentTrade,
    task_post_count: ledgerResult.taskPosts,
    data_current_read_flags_valid: dataCurrentReadFlagsValid,
    historical_provenance_count: historicalProvenanceCount(
      data, !(contract?.historicalTaskSummary || contract?.packetDetail)
    ),
    secret_bearing_field_count: secretCount,
    ledger_contract_rows: ledgerResult.contractRows
  };
  const valid = Boolean(closedSchema && (health || contract) && warningsValid && ledger.length > 0 && dataIdentity &&
    envelopeState !== "invalid" && ledgerResult.rowsTyped && ledgerResult.sourcesAllowlisted &&
    ledgerResult.currentExternal === 0 && ledgerResult.currentProvider === 0 && ledgerResult.currentModel === 0 &&
    ledgerResult.currentWorker === 0 && ledgerResult.currentTrade === 0 && ledgerResult.taskPosts === 0 &&
    dataCurrentReadFlagsValid && secretCount === 0);
  return { valid, summary, digest: objectDigest(summary) };
}

function selfTestFastApiValidator() {
  const safeLedger = () => ({
    api: "local_call_ledger_audit_cache", external: false,
    external_calls_triggered: false, provider_or_model_calls: false,
    tushare_called: false, deepseek_called: false, github_called: false,
    worker_called: false, trade_called: false, does_not_execute_trades: true,
    does_not_modify_strategy_action: true
  });
  const safeAudit = () => ({
    ok: true,
    data: {
      schema_version: "call_ledger_audit_cache.v1",
      packet_key: "command_center_3_call_ledger_audit_cache",
      external_calls_triggered: false, provider_or_model_calls: false,
      tushare_called: false, deepseek_called: false, github_called: false,
      real_trading_enabled: false, contains_secret: false,
      does_not_execute_trades: true, does_not_modify_strategy_action: true
    },
    error: null,
    call_ledger: [safeLedger()],
    warnings: []
  });
  const analyze = (payload, endpoint = "/api/audit/cache") => {
    const bytes = Buffer.from(canonicalJson(payload), "utf8");
    return analyzeFastApiResponse(payload, {
      endpoint, method: "GET", statusCode: 200,
      bodySha256: sha256Bytes(bytes), bodySizeBytes: bytes.length
    });
  };
  const assert = (condition, label) => { if (!condition) throw new Error(`FastAPI validator self-test failed: ${label}`); };
  const safeResult = analyze(safeAudit());
  assert(FASTAPI_CACHE_CONTRACTS.size === 19, "exact_19_endpoint_surface");
  assert(safeResult.valid, "safe_cache_response");
  assert(canonicalJson(safeResult.summary.ledger_contract_rows) === canonicalJson([{
    api: "local_call_ledger_audit_cache", source: "/api/audit/cache", method: "GET", path: "/api/audit/cache",
    external: false, provider: false, model: false, worker: false, trade: false, task_post: false, secret: false
  }]), "exact_normalized_ledger_contract");

  const extraTop = safeAudit();
  extraTop.malicious = true;
  assert(!analyze(extraTop).valid, "2xx_extra_top_level_json");
  const missingExternalProof = safeAudit();
  delete missingExternalProof.call_ledger[0].external;
  assert(!analyze(missingExternalProof).valid, "ledger_external_proof_missing");
  for (const [label, field] of [
    ["external_ledger", "external_calls_triggered"], ["provider_ledger", "tushare_called"],
    ["model_ledger", "deepseek_called"], ["worker_ledger", "worker_called"],
    ["trade_ledger", "trade_called"]
  ]) {
    const payload = safeAudit();
    payload.call_ledger[0][field] = true;
    assert(!analyze(payload).valid, label);
  }
  const taskPost = safeAudit();
  taskPost.call_ledger[0].request_method = "POST";
  assert(!analyze(taskPost).valid, "task_post_ledger");
  const externalUrl = safeAudit();
  externalUrl.call_ledger[0].endpoint = "https://example.invalid/api";
  assert(!analyze(externalUrl).valid, "non_local_ledger_source");
  const unrelatedApi = safeAudit();
  unrelatedApi.call_ledger[0].api = "local_task_status_index";
  assert(!analyze(unrelatedApi).valid, "endpoint_owned_api_required");
  const optionalNext = safeAudit();
  optionalNext.data.schema_version = "next_session_operation_projection.v1";
  optionalNext.data.packet_key = "command_center_next_session_projection_packet";
  optionalNext.call_ledger = [
    { ...safeLedger(), api: "local_next_session_cache" },
    { ...safeLedger(), api: "local_next_session_production_stage_scope_manifest" }
  ];
  assert(analyze(optionalNext, "/api/next-session/cache").valid, "ordered_optional_endpoint_ledger_rows");
  optionalNext.call_ledger.reverse();
  assert(!analyze(optionalNext, "/api/next-session/cache").valid, "primary_cache_row_must_be_first");
  const secret = safeAudit();
  secret.data.api_key = "dummy";
  assert(!analyze(secret).valid, "secret_field");
  assert(!analyze(safeAudit(), "/api/not-allowlisted/cache").valid, "unknown_endpoint");

  const cachedHistory = safeAudit();
  cachedHistory.data.historical_provider_receipt = { tushare_called: true, provider_or_model_calls: true };
  const cachedHistoryResult = analyze(cachedHistory);
  assert(cachedHistoryResult.valid && cachedHistoryResult.summary.historical_provenance_count === 2, "historical_cache_distinguished");

  const taskHistory = {
    ok: true,
    data: {
      schema_version: "command_center_3_task_status_index.v1",
      packet_key: "command_center_3_task_status_index",
      external_calls_triggered: true, call_ledger_external_calls_replayed: true,
      tushare_called: true, call_ledger_tushare_replayed: true,
      deepseek_called: false, call_ledger_deepseek_replayed: false,
      github_called: false, call_ledger_github_replayed: false,
      readback_external_calls_triggered: false,
      does_not_execute_trades: true, does_not_modify_strategy_action: true,
      tasks: [{ source_task_external_calls_triggered: true, tushare_called: true }]
    },
    error: null,
    call_ledger: [{ ...safeLedger(), api: "local_task_status_index" }],
    warnings: []
  };
  assert(analyze(taskHistory, "/api/tasks").valid, "task_history_not_current_get");
  taskHistory.data.readback_external_calls_triggered = true;
  assert(!analyze(taskHistory, "/api/tasks").valid, "task_history_current_get_attack");

  const cacheMissing = {
    ok: false, data: null,
    error: {
      code: "cache_missing", message: "missing",
      details: {
        route: "GET /api/packets/{packet_key}",
        packet_key: "command_center_etf_packet", cache_source: "cache_missing"
      }
    },
    call_ledger: [{ ...safeLedger(), api: "local_packet_cache_read" }], warnings: []
  };
  assert(analyze(cacheMissing, "/api/packets/command_center_etf_packet").valid, "exact_cache_missing_contract");
  return { status: "motion_fastapi_validator_self_test_passed", attack_count: 16, external_calls_triggered: false };
}

function fastApiHealthContract(value) {
  if (!safeRecord(value) || canonicalJson(Object.keys(value).sort()) !== canonicalJson(["call_ledger", "data", "error", "ok", "warnings"]) ||
      value.ok !== true || value.error !== null || !Array.isArray(value.call_ledger) || !Array.isArray(value.warnings)) return null;
  const data = value.data;
  const ledger = value.call_ledger[0];
  if (!data || typeof data !== "object" || Array.isArray(data) || !ledger || typeof ledger !== "object" || Array.isArray(ledger)) return null;
  const contract = {
    service: data.service,
    status: data.status,
    cache_only: data.cache_only,
    read_only: data.read_only,
    external_calls_on_startup: data.external_calls_on_startup,
    external_calls_triggered: data.external_calls_triggered,
    tushare_called: data.tushare_called,
    deepseek_called: data.deepseek_called,
    github_called: data.github_called,
    provider_or_model_calls: data.provider_or_model_calls,
    real_trading_enabled: data.real_trading_enabled,
    does_not_execute_trades: data.does_not_execute_trades,
    does_not_modify_strategy_action: data.does_not_modify_strategy_action,
    does_not_modify_operation_zones: data.does_not_modify_operation_zones,
    contains_secret: data.contains_secret,
    ledger_api: ledger.api,
    ledger_external: ledger.external,
    ledger_external_calls_triggered: ledger.external_calls_triggered,
    ledger_tushare_called: ledger.tushare_called,
    ledger_deepseek_called: ledger.deepseek_called,
    ledger_github_called: ledger.github_called,
    ledger_does_not_execute_trades: ledger.does_not_execute_trades,
    ledger_does_not_modify_strategy_action: ledger.does_not_modify_strategy_action
  };
  const expected = {
    service: "stock-MING Command Center 3.0", status: "ok", cache_only: true, read_only: true,
    external_calls_on_startup: false, external_calls_triggered: false, tushare_called: false,
    deepseek_called: false, github_called: false, provider_or_model_calls: false,
    real_trading_enabled: false, does_not_execute_trades: true,
    does_not_modify_strategy_action: true, does_not_modify_operation_zones: true,
    contains_secret: false, ledger_api: "local_health_check", ledger_external: false,
    ledger_external_calls_triggered: false, ledger_tushare_called: false,
    ledger_deepseek_called: false, ledger_github_called: false,
    ledger_does_not_execute_trades: true, ledger_does_not_modify_strategy_action: true
  };
  return canonicalJson(contract) === canonicalJson(expected) ? contract : null;
}

async function fastApiServiceIdentity() {
  const endpoint = "http://127.0.0.1:8710/health";
  let response;
  try {
    response = await fetch(endpoint, {
      method: "GET", redirect: "error", cache: "no-store",
      headers: { Accept: "application/json" }, signal: AbortSignal.timeout(5000)
    });
  } catch (error) {
    throw new Error(`Formal FastAPI health identity request failed: ${error.message || error}`);
  }
  const contentType = String(response.headers.get("content-type") || "");
  const mediaType = contentType.split(";", 1)[0].trim().toLowerCase();
  const bytes = Buffer.from(await response.arrayBuffer());
  if (response.status !== 200 || mediaType !== "application/json" || bytes.length < 2 || bytes.length > 1024 * 1024) {
    throw new Error("Formal FastAPI health identity requires HTTP 200 application/json with a bounded body");
  }
  let payload;
  try { payload = JSON.parse(bytes.toString("utf8")); } catch { throw new Error("Formal FastAPI health identity JSON is invalid"); }
  const contract = fastApiHealthContract(payload);
  if (!contract) throw new Error("Formal FastAPI health identity schema or safety contract is invalid");
  const unsigned = {
    schema_version: FASTAPI_IDENTITY_SCHEMA_VERSION,
    endpoint,
    status_code: response.status,
    content_type: mediaType,
    service: contract.service,
    response_body_sha256: sha256Bytes(bytes),
    response_size_bytes: bytes.length,
    health_contract_digest: objectDigest(contract),
    health_schema_valid: true
  };
  return { ...unsigned, identity_digest: objectDigest(unsigned) };
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function decodePng(buffer, expectedWidth, expectedHeight) {
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  if (!Buffer.isBuffer(buffer) || buffer.length < 45 || buffer.length > MAX_PNG_FILE_BYTES || !buffer.subarray(0, 8).equals(signature)) {
    throw new Error("Screenshot is not a complete PNG");
  }
  let offset = 8;
  let ihdr = null;
  const idat = [];
  let idatBytes = 0;
  let chunkCount = 0;
  let seenIend = false;
  while (offset < buffer.length) {
    chunkCount += 1;
    if (chunkCount > 4096) throw new Error("PNG chunk count exceeds the bounded parser limit");
    if (offset + 12 > buffer.length) throw new Error("PNG chunk header is truncated");
    const length = buffer.readUInt32BE(offset);
    if (length > MAX_PNG_FILE_BYTES) throw new Error("PNG chunk exceeds the bounded parser limit");
    const end = offset + 12 + length;
    if (end > buffer.length) throw new Error("PNG chunk is truncated");
    const type = buffer.subarray(offset + 4, offset + 8).toString("ascii");
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    const expectedCrc = buffer.readUInt32BE(offset + 8 + length);
    if (crc32(buffer.subarray(offset + 4, offset + 8 + length)) !== expectedCrc) throw new Error(`PNG ${type} CRC mismatch`);
    if (type === "IHDR") {
      if (ihdr || length !== 13 || offset !== 8) throw new Error("PNG IHDR is invalid");
      ihdr = {
        width: data.readUInt32BE(0), height: data.readUInt32BE(4), bitDepth: data[8],
        colorType: data[9], compression: data[10], filter: data[11], interlace: data[12]
      };
    } else if (type === "IDAT") {
      if (!ihdr || seenIend) throw new Error("PNG IDAT order is invalid");
      idat.push(data);
      idatBytes += data.length;
      if (idatBytes > MAX_PNG_IDAT_BYTES) throw new Error("PNG IDAT payload exceeds the bounded parser limit");
    } else if (type === "IEND") {
      if (length !== 0 || !ihdr || !idat.length) throw new Error("PNG IEND is invalid");
      seenIend = true;
      if (end !== buffer.length) throw new Error("PNG has bytes after IEND");
    }
    offset = end;
  }
  if (!ihdr || !seenIend || ihdr.width !== expectedWidth || ihdr.height !== expectedHeight) {
    throw new Error("PNG viewport dimensions do not match the pinned matrix");
  }
  if (ihdr.compression !== 0 || ihdr.filter !== 0 || ihdr.interlace !== 0) throw new Error("PNG encoding is unsupported or interlaced");
  const channels = ({ 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 })[ihdr.colorType];
  if (!channels || ![1, 2, 4, 8, 16].includes(ihdr.bitDepth)) throw new Error("PNG color format is invalid");
  const rowBytes = Math.ceil(ihdr.width * channels * ihdr.bitDepth / 8);
  const expectedDecodedBytes = ihdr.height * (rowBytes + 1);
  if (expectedDecodedBytes <= 0 || expectedDecodedBytes > MAX_PNG_DECODED_BYTES) throw new Error("PNG decoded payload exceeds the bounded parser limit");
  const decoded = inflateSync(Buffer.concat(idat), { maxOutputLength: expectedDecodedBytes + 1 });
  if (decoded.length !== expectedDecodedBytes) throw new Error("PNG decoded payload length is invalid");
  for (let row = 0; row < ihdr.height; row += 1) {
    if (decoded[row * (rowBytes + 1)] > 4) throw new Error("PNG decoded row filter is invalid");
  }
  return { width: ihdr.width, height: ihdr.height };
}

async function readRegularFile(path, expectedMode = null, maxBytes = null) {
  const before = await lstat(path);
  if (!before.isFile() || before.isSymbolicLink() || (expectedMode !== null && (before.mode & 0o777) !== expectedMode)) {
    throw new Error(`Unsafe regular file: ${path}`);
  }
  if (maxBytes !== null && before.size > maxBytes) throw new Error(`Regular file exceeds the bounded read limit: ${path}`);
  const handle = await open(path, fsConstants.O_RDONLY | (fsConstants.O_NOFOLLOW || 0));
  try {
    const during = await handle.stat();
    if (!during.isFile() || during.dev !== before.dev || during.ino !== before.ino) throw new Error(`File changed during secure open: ${path}`);
    if (maxBytes !== null && during.size > maxBytes) throw new Error(`Regular file exceeds the bounded read limit: ${path}`);
    return await handle.readFile();
  } finally {
    await handle.close();
  }
}

async function writeExclusiveFile(path, bytes, mode = 0o600) {
  const handle = await open(path, "wx", mode);
  try {
    await handle.writeFile(bytes);
    await handle.sync();
  } finally {
    await handle.close();
  }
}

async function fileDigest(path) {
  return sha256Bytes(await readFile(path));
}

async function listFiles(root) {
  const output = [];
  async function visit(directory) {
    const entries = await readdir(directory, { withFileTypes: true });
    entries.sort((left, right) => left.name < right.name ? -1 : left.name > right.name ? 1 : 0);
    for (const entry of entries) {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) await visit(path);
      else if (entry.isFile()) output.push(path);
      else throw new Error(`Frontend identity contains an unsupported or symbolic entry: ${path}`);
    }
  }
  await visit(root);
  return output;
}

async function treeDigest(root) {
  const files = await listFiles(root);
  const rows = [];
  for (const path of files) {
    rows.push({ path: relative(root, path).split("\\").join("/"), sha256: await fileDigest(path) });
  }
  return objectDigest(rows);
}

function webContentType(path) {
  if (path.endsWith(".html")) return "text/html";
  if (path.endsWith(".js")) return "text/javascript";
  if (path.endsWith(".css")) return "text/css";
  return "";
}

async function distManifest() {
  const distRoot = resolve(FRONTEND_ROOT, "dist");
  const files = await listFiles(distRoot);
  const entries = [];
  for (const path of files) {
    const relpath = relative(distRoot, path).split("\\").join("/");
    const contentType = webContentType(relpath);
    if (!contentType) continue;
    const bytes = await readRegularFile(path);
    entries.push({ path: relpath, sha256: sha256Bytes(bytes), size_bytes: bytes.length, content_type: contentType });
  }
  entries.sort((left, right) => left.path < right.path ? -1 : left.path > right.path ? 1 : 0);
  const entryGraph = entries.map((entry) => entry.path);
  if (!entries.length || !entryGraph.includes("index.html")) throw new Error("desktop/dist lacks the pinned HTML/JS/CSS entry graph");
  const unsigned = {
    schema_version: DIST_MANIFEST_SCHEMA_VERSION,
    entry_html: "index.html",
    entries,
    entry_graph: entryGraph,
    entry_graph_digest: objectDigest(entryGraph)
  };
  return { ...unsigned, manifest_digest: objectDigest(unsigned) };
}

async function frontendIdentity() {
  const sourceDigest = await treeDigest(resolve(FRONTEND_ROOT, "src"));
  const distRoot = resolve(FRONTEND_ROOT, "dist");
  try {
    if (!(await stat(distRoot)).isDirectory()) throw new Error("desktop/dist is not a directory");
  } catch (error) {
    throw new Error(`Current frontend build is required before motion QA: ${error.message || error}`);
  }
  const distDigest = await treeDigest(distRoot);
  const manifest = await distManifest();
  const inputs = [];
  for (const name of ["package.json", "package-lock.json", "vite.config.ts", "tsconfig.json"]) {
    const path = resolve(FRONTEND_ROOT, name);
    try {
      inputs.push({ path: `desktop/${name}`, sha256: await fileDigest(path) });
    } catch (error) {
      if (error?.code !== "ENOENT") throw error;
    }
  }
  return {
    frontendSourceDigest: sourceDigest,
    buildIdentityDigest: objectDigest({
      frontend_source_digest: sourceDigest,
      dist_digest: distDigest,
      dist_manifest_digest: manifest.manifest_digest,
      build_inputs: inputs
    }),
    distManifest: manifest
  };
}

function repositoryIdentity(expectedHeadFull) {
  if (!HEX_HEAD.test(String(expectedHeadFull || ""))) {
    throw new Error("--expected-head-full must be the exact 40-character lowercase commit SHA");
  }
  const actualHeadFull = execFileSync("git", ["-C", PROJECT_ROOT, "rev-parse", "HEAD"], { encoding: "utf8" }).trim();
  const status = execFileSync("git", ["-C", PROJECT_ROOT, "status", "--porcelain=v1", "--untracked-files=all"], { encoding: "utf8" }).trim();
  if (!HEX_HEAD.test(actualHeadFull) || actualHeadFull !== expectedHeadFull) {
    throw new Error(`Expected HEAD ${expectedHeadFull} does not match actual repository HEAD ${actualHeadFull || "missing"}`);
  }
  if (status) throw new Error("Motion QA requires a completely clean worktree, including relevant untracked files, so HEAD and frontend identity cannot diverge");
  return { actualHeadFull, worktreeClean: true };
}

async function frontendServiceIdentity(baseUrl, manifestDigest) {
  if (baseUrl.port !== "4173") throw new Error("Attested motion QA must use the built Vite preview on exact port 4173");
  let listenerOutput;
  try {
    listenerOutput = execFileSync("lsof", ["-nP", `-iTCP:${baseUrl.port}`, "-sTCP:LISTEN", "-Fp"], { encoding: "utf8" });
  } catch (error) {
    throw new Error(`Unable to identify the exact frontend listener: ${error.message || error}`);
  }
  const pids = [...new Set(listenerOutput.split(/\r?\n/).filter((line) => /^p[0-9]+$/.test(line)).map((line) => Number(line.slice(1))))];
  if (pids.length !== 1 || !Number.isSafeInteger(pids[0]) || pids[0] <= 1) throw new Error("Frontend port must have exactly one identifiable listener process");
  const listenerPid = pids[0];
  const cwdOutput = execFileSync("lsof", ["-a", "-p", String(listenerPid), "-d", "cwd", "-Fn"], { encoding: "utf8" });
  const cwdRows = cwdOutput.split(/\r?\n/).filter((line) => line.startsWith("n")).map((line) => line.slice(1));
  if (cwdRows.length !== 1 || await realpath(cwdRows[0]) !== await realpath(FRONTEND_ROOT)) {
    throw new Error("Frontend listener cwd is not the repository desktop directory");
  }
  const command = execFileSync("ps", ["-p", String(listenerPid), "-o", "command="], { encoding: "utf8" }).trim();
  if (!command || !command.includes("vite") || !command.includes("preview")) throw new Error("Frontend listener is not the repository Vite preview process");
  const servedRoot = resolve(FRONTEND_ROOT, "dist");
  if (await realpath(servedRoot) !== servedRoot) throw new Error("desktop/dist served root must be a real, non-redirected directory");
  const unsigned = {
    schema_version: SERVICE_IDENTITY_SCHEMA_VERSION,
    listener_pid: listenerPid,
    protocol: baseUrl.protocol,
    hostname: baseUrl.hostname,
    port: baseUrl.port,
    base_url: baseUrl.toString().replace(/\/$/, ""),
    process_cwd: "desktop",
    command_sha256: sha256Bytes(Buffer.from(command, "utf8")),
    served_root: "desktop/dist",
    served_root_manifest_digest: manifestDigest
  };
  return { ...unsigned, identity_digest: objectDigest(unsigned) };
}

async function formalPackageBinding(expectedHeadFull) {
  const python = resolve(PROJECT_ROOT, ".venv", "bin", "python");
  const validatorScript = [
    "import json,sys",
    "from pathlib import Path",
    "from server.services.tauri_package_verifier import validate_tauri_production_package",
    "print(json.dumps(validate_tauri_production_package(Path(sys.argv[1]) / '.stock_ming_3', expected_head_full=sys.argv[2], write_manifest=False), sort_keys=True))"
  ].join("; ");
  let verification;
  try {
    verification = JSON.parse(execFileSync(python, ["-c", validatorScript, PROJECT_ROOT, expectedHeadFull], {
      cwd: PROJECT_ROOT,
      encoding: "utf8",
      env: { ...process.env, PYTHONPATH: PROJECT_ROOT, PYTHONDONTWRITEBYTECODE: "1" },
      maxBuffer: 8 * 1024 * 1024
    }));
  } catch (error) {
    throw new Error(`Formal current-head Tauri package verification failed: ${error.message || error}`);
  }
  const packageRoot = resolve(PROJECT_ROOT, ".stock_ming_3", "desktop_runtime");
  const buildBytes = await readRegularFile(resolve(packageRoot, "tauri_build_receipt.json"));
  const manifest = JSON.parse((await readRegularFile(resolve(packageRoot, "tauri_production_package_manifest.json"))).toString("utf8"));
  const pointer = JSON.parse((await readRegularFile(resolve(packageRoot, "tauri_production_package_pointer.json"))).toString("utf8"));
  const { manifest_digest: manifestDigest, ...manifestMaterial } = manifest;
  if (
    verification.production_package_complete !== true || verification.head_full !== expectedHeadFull ||
    manifest.production_package_complete !== true || manifest.head_full !== expectedHeadFull ||
    manifestDigest !== objectDigest(manifestMaterial) || pointer.head_full !== expectedHeadFull ||
    pointer.manifest_digest !== manifestDigest || pointer.artifact_set_sha256 !== verification.artifact_set_sha256 ||
    pointer.immutable !== true
  ) throw new Error("Formal package manifest/pointer is not bound to the exact current HEAD and disk artifacts");
  const unsigned = {
    schema_version: PACKAGE_BINDING_SCHEMA_VERSION,
    head_full: expectedHeadFull,
    build_receipt_sha256: sha256Bytes(buildBytes),
    package_manifest_digest: manifestDigest,
    artifact_set_sha256: verification.artifact_set_sha256,
    app_bundle_sha256: verification.app_bundle_sha256,
    app_executable_sha256: verification.app_executable_sha256,
    dmg_sha256: verification.dmg_sha256,
    production_package_complete: true
  };
  for (const key of ["build_receipt_sha256", "package_manifest_digest", "artifact_set_sha256", "app_bundle_sha256", "app_executable_sha256", "dmg_sha256"]) {
    if (!HEX_64.test(String(unsigned[key] || ""))) throw new Error(`Formal package binding field is invalid: ${key}`);
  }
  return { ...unsigned, identity_digest: objectDigest(unsigned) };
}

function relativeArtifactPath(artifactRoot, path) {
  const value = relative(resolve(artifactRoot), path).split("\\").join("/");
  if (!value || value.startsWith("../") || value === "..") throw new Error(`Artifact escaped motion root: ${path}`);
  return value;
}

async function atomicJson(path, value, mode = 0o600, replaceExisting = true) {
  await mkdir(dirname(path), { recursive: true });
  try {
    const existing = await lstat(path);
    if (existing.isSymbolicLink() || !existing.isFile() || !replaceExisting) throw new Error(`Refusing to replace unsafe or unexpected path: ${path}`);
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }
  const temp = `${path}.tmp-${process.pid}-${Date.now()}`;
  await writeExclusiveFile(temp, Buffer.from(`${JSON.stringify(value, null, 2)}\n`, "utf8"), mode);
  await rename(temp, path);
}

function exactKeys(value, keys) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).sort().join(",") === [...keys].sort().join(","));
}

function utcTimestamp(value) {
  return typeof value === "string" && value.endsWith("Z") && Number.isFinite(Date.parse(value));
}

async function initializeRunnerTrust(artifactRoot) {
  const trustDir = resolve(artifactRoot, TRUST_DIR_NAME);
  const identityPath = resolve(artifactRoot, IDENTITY_FILE_NAME);
  const terminalPath = resolve(artifactRoot, TERMINAL_FILE_NAME);
  try {
    const existing = await readdir(artifactRoot);
    if (existing.length) throw new Error("Existing motion evidence or trust material forbids automatic chain replacement");
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }
  await mkdir(artifactRoot, { recursive: true });
  await mkdir(trustDir, { mode: 0o700 });
  await chmod(trustDir, 0o700);
  const key = randomBytes(32);
  const installationId = randomBytes(32).toString("hex");
  const createdAt = new Date().toISOString();
  const state = { schema_version: STATE_SCHEMA_VERSION, updated_at: createdAt, events: [] };
  const unsignedIdentity = { schema_version: IDENTITY_SCHEMA_VERSION, installation_id: installationId, created_at: createdAt };
  const identity = {
    ...unsignedIdentity,
    identity_mac: createHmac("sha256", key).update(canonicalJson(unsignedIdentity), "utf8").digest("hex")
  };
  const unsignedAnchor = {
    schema_version: ANCHOR_SCHEMA_VERSION,
    installation_id: installationId,
    sequence_no: 0,
    updated_at: createdAt,
    latest_event_mac: "0".repeat(64),
    state_digest: objectDigest(state)
  };
  const anchor = {
    ...unsignedAnchor,
    anchor_mac: createHmac("sha256", key).update(canonicalJson(unsignedAnchor), "utf8").digest("hex")
  };
  const unsignedTerminal = {
    schema_version: TERMINAL_SCHEMA_VERSION,
    installation_id: installationId,
    sequence_no: 0,
    updated_at: createdAt,
    latest_event_mac: "0".repeat(64),
    state_digest: objectDigest(state),
    anchor_digest: objectDigest(anchor)
  };
  const terminal = {
    ...unsignedTerminal,
    terminal_mac: createHmac("sha256", key).update(canonicalJson(unsignedTerminal), "utf8").digest("hex")
  };
  await writeExclusiveFile(resolve(trustDir, "runner.key"), key);
  await writeExclusiveFile(identityPath, Buffer.from(`${JSON.stringify(identity, null, 2)}\n`, "utf8"));
  await writeExclusiveFile(resolve(trustDir, "state.json"), Buffer.from(`${JSON.stringify(state, null, 2)}\n`, "utf8"));
  await writeExclusiveFile(resolve(trustDir, "high_water.json"), Buffer.from(`${JSON.stringify(anchor, null, 2)}\n`, "utf8"));
  await writeExclusiveFile(terminalPath, Buffer.from(`${JSON.stringify(terminal, null, 2)}\n`, "utf8"));
  return { installation_id: installationId, initialized_at: createdAt };
}

async function loadRunnerKey(trustDir) {
  const trustStat = await lstat(trustDir);
  if (!trustStat.isDirectory() || trustStat.isSymbolicLink() || (trustStat.mode & 0o777) !== 0o700) {
    throw new Error("Runner trust directory is missing or unsafe; use explicit trust initialization only when no old evidence exists");
  }
  const key = await readRegularFile(resolve(trustDir, "runner.key"), 0o600);
  if (key.length !== 32) throw new Error("Runner attestation key is invalid and will not be created or repaired automatically");
  return key;
}

async function readAttestationState(artifactRoot, key) {
  const trustDir = resolve(artifactRoot, TRUST_DIR_NAME);
  const statePath = resolve(trustDir, "state.json");
  const anchorPath = resolve(trustDir, "high_water.json");
  const identityPath = resolve(artifactRoot, IDENTITY_FILE_NAME);
  const terminalPath = resolve(artifactRoot, TERMINAL_FILE_NAME);
  try {
    const identity = JSON.parse((await readRegularFile(identityPath, 0o600)).toString("utf8"));
    if (!exactKeys(identity, ["schema_version", "installation_id", "created_at", "identity_mac"])) throw new Error("installation identity schema mismatch");
    const { identity_mac: identityMac, ...unsignedIdentity } = identity;
    if (
      identity.schema_version !== IDENTITY_SCHEMA_VERSION || !HEX_64.test(String(identity.installation_id || "")) ||
      !utcTimestamp(identity.created_at) || identityMac !== createHmac("sha256", key).update(canonicalJson(unsignedIdentity), "utf8").digest("hex")
    ) throw new Error("installation identity MAC mismatch");
    const state = JSON.parse((await readRegularFile(statePath, 0o600)).toString("utf8"));
    if (!exactKeys(state, ["events", "schema_version", "updated_at"]) || state.schema_version !== STATE_SCHEMA_VERSION || !Array.isArray(state.events) || !utcTimestamp(state.updated_at)) {
      throw new Error("state schema mismatch");
    }
    const anchor = JSON.parse((await readRegularFile(anchorPath, 0o600)).toString("utf8"));
    if (!exactKeys(anchor, ["anchor_mac", "installation_id", "latest_event_mac", "schema_version", "sequence_no", "state_digest", "updated_at"])) {
      throw new Error("high-water anchor schema mismatch");
    }
    const { anchor_mac: anchorMac, ...unsignedAnchor } = anchor;
    const lastEvent = state.events[state.events.length - 1];
    if (
      anchor.schema_version !== ANCHOR_SCHEMA_VERSION || anchor.installation_id !== identity.installation_id ||
      !Number.isSafeInteger(anchor.sequence_no) || anchor.sequence_no !== state.events.length ||
      anchor.state_digest !== objectDigest(state) || anchor.updated_at !== state.updated_at ||
      anchor.latest_event_mac !== (lastEvent?.event_mac || "0".repeat(64)) ||
      !HEX_64.test(String(anchorMac || "")) || anchorMac !== createHmac("sha256", key).update(canonicalJson(unsignedAnchor), "utf8").digest("hex")
    ) throw new Error("high-water anchor does not match state");
    const terminal = JSON.parse((await readRegularFile(terminalPath, 0o600)).toString("utf8"));
    if (!exactKeys(terminal, ["anchor_digest", "installation_id", "latest_event_mac", "schema_version", "sequence_no", "state_digest", "terminal_mac", "updated_at"])) {
      throw new Error("terminal high-water schema mismatch");
    }
    const { terminal_mac: terminalMac, ...unsignedTerminal } = terminal;
    if (
      terminal.schema_version !== TERMINAL_SCHEMA_VERSION || terminal.installation_id !== identity.installation_id ||
      terminal.sequence_no !== state.events.length || terminal.updated_at !== state.updated_at ||
      terminal.latest_event_mac !== (lastEvent?.event_mac || "0".repeat(64)) ||
      terminal.state_digest !== objectDigest(state) || terminal.anchor_digest !== objectDigest(anchor) ||
      terminalMac !== createHmac("sha256", key).update(canonicalJson(unsignedTerminal), "utf8").digest("hex")
    ) throw new Error("independent terminal high-water detects rollback or replacement");
    return { state, statePath, anchorPath, terminalPath, installationId: identity.installation_id };
  } catch (error) {
    throw new Error(`Runner attestation identity/state/anchor is invalid and will not be created or repaired: ${error.message || error}`);
  }
}

async function appendAttestationUnlocked({ artifactRoot, reportPath, reportRelpath, unsignedReport, generatedAt, headFull, runMode, frontendSourceDigest, buildIdentityDigest }) {
  const trustDir = resolve(artifactRoot, TRUST_DIR_NAME);
  const key = await loadRunnerKey(trustDir);
  const { state, statePath, anchorPath, terminalPath, installationId } = await readAttestationState(artifactRoot, key);
  let previousEventMac = "0".repeat(64);
  const eventKeys = [
    "schema_version", "sequence_no", "created_at", "report_relpath", "report_digest",
    "head_full", "run_mode", "frontend_source_digest", "build_identity_digest",
    "dist_manifest_digest", "entry_graph_digest", "frontend_service_identity_digest", "package_identity_digest",
    "previous_event_mac", "event_mac"
  ].sort().join(",");
  for (let index = 0; index < state.events.length; index += 1) {
    const event = state.events[index];
    if (!event || typeof event !== "object" || Array.isArray(event) || Object.keys(event).sort().join(",") !== eventKeys) {
      throw new Error("Runner attestation event schema is invalid; state will not be repaired");
    }
    const { event_mac: eventMac, ...unsigned } = event;
    const expectedMac = createHmac("sha256", key).update(canonicalJson(unsigned), "utf8").digest("hex");
    if (
      event.schema_version !== EVENT_SCHEMA_VERSION || event.sequence_no !== index + 1 ||
      event.previous_event_mac !== previousEventMac || eventMac !== expectedMac
    ) throw new Error("Runner attestation chain is invalid; state will not be repaired");
    if (index > 0 && event.created_at < state.events[index - 1].created_at) {
      throw new Error("Runner attestation timestamps are not monotonic; state will not be repaired");
    }
    if (state.events.slice(0, index).some((prior) => prior.report_relpath === event.report_relpath)) {
      throw new Error("Runner attestation report path was reused; state will not be repaired");
    }
    previousEventMac = eventMac;
  }
  if (state.events.length && state.updated_at !== state.events[state.events.length - 1].created_at) {
    throw new Error("Runner attestation state timestamp is not bound to its latest event");
  }
  const reportDigest = objectDigest(unsignedReport);
  const unsignedEvent = {
    schema_version: EVENT_SCHEMA_VERSION,
    sequence_no: state.events.length + 1,
    created_at: generatedAt,
    report_relpath: reportRelpath,
    report_digest: reportDigest,
    head_full: headFull,
    run_mode: runMode,
    frontend_source_digest: frontendSourceDigest,
    build_identity_digest: buildIdentityDigest,
    dist_manifest_digest: unsignedReport.dist_manifest.manifest_digest,
    entry_graph_digest: unsignedReport.dist_manifest.entry_graph_digest,
    frontend_service_identity_digest: unsignedReport.frontend_service_identity.identity_digest,
    package_identity_digest: unsignedReport.package_binding.identity_digest,
    previous_event_mac: previousEventMac
  };
  const eventMac = createHmac("sha256", key).update(canonicalJson(unsignedEvent), "utf8").digest("hex");
  const event = { ...unsignedEvent, event_mac: eventMac };
  const report = {
    ...unsignedReport,
    report_digest: reportDigest,
    runner_attestation: {
      sequence_no: event.sequence_no,
      previous_event_mac: event.previous_event_mac,
      event_mac: event.event_mac,
      state_schema_version: STATE_SCHEMA_VERSION,
      anchor_schema_version: ANCHOR_SCHEMA_VERSION,
      identity_schema_version: IDENTITY_SCHEMA_VERSION,
      terminal_schema_version: TERMINAL_SCHEMA_VERSION
    }
  };
  const nextState = {
    schema_version: STATE_SCHEMA_VERSION,
    updated_at: generatedAt,
    events: [...state.events, event]
  };
  const unsignedAnchor = {
    schema_version: ANCHOR_SCHEMA_VERSION,
    installation_id: installationId,
    sequence_no: event.sequence_no,
    updated_at: generatedAt,
    latest_event_mac: event.event_mac,
    state_digest: objectDigest(nextState)
  };
  const anchor = {
    ...unsignedAnchor,
    anchor_mac: createHmac("sha256", key).update(canonicalJson(unsignedAnchor), "utf8").digest("hex")
  };
  const unsignedTerminal = {
    schema_version: TERMINAL_SCHEMA_VERSION,
    installation_id: installationId,
    sequence_no: event.sequence_no,
    updated_at: generatedAt,
    latest_event_mac: event.event_mac,
    state_digest: objectDigest(nextState),
    anchor_digest: objectDigest(anchor)
  };
  const terminal = {
    ...unsignedTerminal,
    terminal_mac: createHmac("sha256", key).update(canonicalJson(unsignedTerminal), "utf8").digest("hex")
  };
  // Evidence becomes durable before the chain advances. A crash after this point
  // is fail-closed and never produces a state entry for a missing report.
  await atomicJson(reportPath, report, 0o600, false);
  await atomicJson(statePath, nextState);
  await atomicJson(anchorPath, anchor);
  await atomicJson(terminalPath, terminal);
  return { event, report };
}

async function appendAttestation(args) {
  const trustDir = resolve(args.artifactRoot, TRUST_DIR_NAME);
  await loadRunnerKey(trustDir);
  const lockPath = resolve(trustDir, "append.lock");
  let lockHandle;
  try {
    lockHandle = await open(lockPath, "wx", 0o600);
  } catch (error) {
    throw new Error(`Another motion runner owns the append lock; no evidence was registered: ${error.message || error}`);
  }
  try {
    return await appendAttestationUnlocked(args);
  } finally {
    await lockHandle.close();
    await unlink(lockPath).catch(() => {});
  }
}

function timestampId(runMode) {
  return `${new Date().toISOString().replace(/[:.]/g, "-")}-${runMode}`;
}

function makePlan(args) {
  const routes = selectedQaRoutes(args);
  const base = exactLocalUrl(args.baseUrl);
  const matrix = routes.flatMap((route) =>
    QA_VIEWPORTS.map((viewport) => ({
      route: route.route,
      label: route.label,
      viewport: viewport.name,
      width: viewport.width,
      height: viewport.height,
      url: new URL(`/${route.navigation_hash || route.route}`, base).toString(),
      risk_focus: route.risk_focus,
      visual_qa_complete: false,
      performance_trace_complete: false
    }))
  );
  return {
    schema_version: "command_center_3_motion_browser_qa_plan.v1",
    status: "motion_browser_qa_plan_ready",
    scope: "explicit_local_browser_runner_plan",
    base_url: base.origin,
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
    local_urls_only: true,
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true
  };
}

async function inspectPage(page, route, transitionStartedUs) {
  return page.evaluate(({ expected, startedUs }) => {
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
        opacity_ppm: Math.round(Number(style.opacity || 1) * 1000000),
        clipped,
        offscreen
      };
    };
    const auditable = elements
      .map(toRow)
      .filter((item) => item.width > 0 && item.height > 0 && item.display !== "none" && item.visibility !== "hidden" && item.opacity_ppm > 10000);
    const visible = visibleElements
      .map((element) => {
        return toRow(element);
      })
      .filter((item) => item.width > 0 && item.height > 0 && item.display !== "none" && item.visibility !== "hidden" && item.opacity_ppm > 10000);
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
      .filter((item) => item.width > 0 && item.height > 0 && !item.offscreen && item.text.length > 0 && item.opacity_ppm < 940000)
      .slice(0, 20);
    const documentElement = document.documentElement;
    const horizontalOverflowPx = Math.max(0, documentElement.scrollWidth - documentElement.clientWidth);
    const anchorElement = document.querySelector(expected.anchor);
    const anchorRect = anchorElement?.getBoundingClientRect();
    const anchorReady = Boolean(
      anchorElement && anchorRect && anchorRect.width > 0 && anchorRect.height > 0 && anchorRect.top < window.innerHeight && anchorRect.bottom > 0
    );
    const perf = window.__commandCenterMotionQaPerformance || { longTasks: [], layoutShifts: [] };
    const longTasks = perf.longTasks.filter((entry) => entry.start_us >= startedUs && entry.duration_us > 50000);
    const layoutShifts = perf.layoutShifts.filter((entry) => entry.start_us >= startedUs && entry.had_recent_input === false);
    const largestLayoutShiftPpm = layoutShifts.reduce((largest, entry) => Math.max(largest, entry.value_ppm), 0);
    const headingText = document.querySelector(".route-stage h1")?.textContent?.trim() || "";
    return {
      title: document.title,
      heading_text: headingText,
      expected_heading_ready: headingText === expected.heading,
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
      expected_anchor: expected.anchor,
      expected_anchor_ready: anchorReady,
      motion_markers: motionMarkers,
      motion_marker_minimum_ready: Number(motionMarkers[expected.marker] || 0) >= expected.marker_minimum,
      long_task_observer_ready: perf.longTaskObserver === true,
      layout_shift_observer_ready: perf.layoutShiftObserver === true,
      long_task_over_50ms_count: longTasks.length,
      largest_motion_layout_shift_ppm: largestLayoutShiftPpm
    };
  }, { expected: route, startedUs: transitionStartedUs });
}

async function runQa(args) {
  const { chromium } = require("playwright");
  const routes = selectedQaRoutes(args);
  if (args.route) throw new Error("Attested motion evidence requires the complete pinned route matrix; omit --route");
  if (!args.screenshots) throw new Error("Attested motion evidence requires raw screenshots; omit --no-screenshots");
  if (args.artifactRoot !== DEFAULT_ARTIFACT_ROOT) throw new Error(`Attested motion evidence must use ${DEFAULT_ARTIFACT_ROOT}`);
  const baseUrl = exactLocalUrl(args.baseUrl);
  if (baseUrl.port !== "4173" || baseUrl.pathname !== "/" || baseUrl.search || baseUrl.hash) {
    throw new Error("Attested motion evidence requires the exact built preview origin http://127.0.0.1:4173 or http://localhost:4173");
  }
  const { actualHeadFull, worktreeClean } = repositoryIdentity(args.expectedHeadFull);
  const { frontendSourceDigest, buildIdentityDigest, distManifest: currentDistManifest } = await frontendIdentity();
  const frontendService = await frontendServiceIdentity(baseUrl, currentDistManifest.manifest_digest);
  const fastapiService = await fastApiServiceIdentity();
  const packageBinding = await formalPackageBinding(actualHeadFull);
  const runMode = args.reducedMotion ? "reduced" : "normal";
  const runId = timestampId(runMode);
  const artifactRoot = resolve(PROJECT_ROOT, args.artifactRoot);
  const outputDir = resolve(artifactRoot, runId);
  await mkdir(artifactRoot, { recursive: true });
  const artifactRootStat = await lstat(artifactRoot);
  if (!artifactRootStat.isDirectory() || artifactRootStat.isSymbolicLink()) throw new Error("Motion artifact root must be a real directory");
  const trustKey = await loadRunnerKey(resolve(artifactRoot, TRUST_DIR_NAME));
  await readAttestationState(artifactRoot, trustKey);
  await mkdir(outputDir);
  const outputDirStat = await lstat(outputDir);
  if (!outputDirStat.isDirectory() || outputDirStat.isSymbolicLink()) throw new Error("Motion run directory must be a real directory");
  const browser = await chromium.launch({ headless: true });
  const rows = [];
  const errors = [];
  const warmupRequestLedger = [];
  const warmupNavigationLedger = [];
  const manifestRequestLedger = [];
  const lateNetworkEvents = [];
  try {
    for (const viewport of QA_VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        reducedMotion: args.reducedMotion ? "reduce" : "no-preference",
        serviceWorkers: "block"
      });
      await context.addInitScript(() => {
        const state = { longTasks: [], layoutShifts: [], longTaskObserver: false, layoutShiftObserver: false };
        window.__commandCenterMotionQaPerformance = state;
        try {
          const observer = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
              state.longTasks.push({
                start_us: Math.round(entry.startTime * 1000),
                duration_us: Math.round(entry.duration * 1000)
              });
            }
          });
          observer.observe({ type: "longtask", buffered: true });
          state.longTaskObserver = true;
        } catch {}
        try {
          const observer = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
              state.layoutShifts.push({
                start_us: Math.round(entry.startTime * 1000),
                value_ppm: Math.round(entry.value * 1000000),
                had_recent_input: entry.hadRecentInput === true
              });
            }
          });
          observer.observe({ type: "layout-shift", buffered: true });
          state.layoutShiftObserver = true;
        } catch {}
      });
      let sessionCounter = 0;
      let requestCounter = 0;
      let eventIndex = 0;
      let fatalNetworkError = null;
      const responseTasks = new Set();
      const requestOrigins = new WeakMap();
      const inflightRequests = new Map();
      const terminalRequestIds = new Set();
      const closedSessions = new Set();
      const sessionActivity = new Map();
      const manifestEntries = new Map(currentDistManifest.entries.map((entry) => [entry.path, entry]));
      const createSession = (phase, route, ledger) => Object.freeze({
        session_id: `${viewport.name}:${++sessionCounter}:${phase}:${route}`,
        phase,
        route,
        ledger
      });
      let activeSession = createSession("warmup", "#health", warmupRequestLedger);
      const describeUrl = (rawUrl) => {
        try {
          const parsed = new URL(rawUrl);
          return {
            url: parsed.toString(), protocol: parsed.protocol, hostname: parsed.hostname,
            port: parsed.port, path: `${parsed.pathname}${parsed.search}`
          };
        } catch {
          return { url: String(rawUrl || ""), protocol: "", hostname: "", port: "", path: "" };
        }
      };
      const appendNetworkEntry = (session, entry) => {
        sessionActivity.set(session.session_id, Date.now());
        if (closedSessions.has(session.session_id)) {
          lateNetworkEvents.push(entry);
          fatalNetworkError = new Error(`Late network activity for closed session ${session.session_id}`);
        } else {
          session.ledger.push(entry);
        }
      };
      const purposeFor = (parsed) => {
        if (!parsed) return "blocked_or_unknown";
        if (parsed.port === "4173" && parsed.origin === baseUrl.origin && !parsed.search && parsed.pathname.startsWith("/")) {
          return "vite_preview_dist_resource";
        }
        if (parsed.port === "8710" && !parsed.search && parsed.pathname === "/health") {
          return "fastapi_health_identity";
        }
        if (parsed.port === "8710" && !parsed.search && FASTAPI_CACHE_CONTRACTS.has(parsed.pathname)) {
          return "fastapi_cache_read";
        }
        return "blocked_or_unknown";
      };
      const baseNetworkEntry = (origin, eventType, allowed) => ({
        event_index: ++eventIndex,
        event_type: eventType,
        request_id: origin.request_id,
        session_id: origin.session.session_id,
        phase: origin.session.phase,
        route: origin.session.route,
        viewport: viewport.name,
        method: origin.method,
        ...describeUrl(origin.url),
        purpose: origin.purpose,
        allowed,
        status_code: null,
        content_type: "",
        body_sha256: "",
        body_size_bytes: null,
        dist_path: "",
        expected_dist_sha256: "",
        body_matches_dist: false,
        body_schema_valid: false,
        response_semantic_summary: {},
        response_semantic_digest: "",
        failure_text: ""
      });
      const flushResponseTasks = async () => {
        if (!responseTasks.size) return;
        let timeout;
        try {
          await Promise.race([
            Promise.all([...responseTasks]),
            new Promise((_, reject) => {
              timeout = setTimeout(() => reject(new Error("Timed out waiting for response body validation")), NETWORK_IDLE_TIMEOUT_MS);
            })
          ]);
        } finally {
          if (timeout) clearTimeout(timeout);
        }
      };
      const assertNetworkBoundary = async (stage, session) => {
        await flushResponseTasks();
        if (fatalNetworkError) throw new Error(`${stage}: ${fatalNetworkError.message || fatalNetworkError}`);
        if (lateNetworkEvents.length) throw new Error(`${stage}: late network activity was observed after a phase closed`);
        const inflight = [...inflightRequests.values()].filter((item) => item.session.session_id === session.session_id);
        if (inflight.length) throw new Error(`${stage}: ${inflight.length} request(s) remain inflight for ${session.session_id}`);
      };
      const closeSession = async (session, stage) => {
        if (activeSession.session_id !== session.session_id || closedSessions.has(session.session_id)) {
          throw new Error(`${stage}: attempted to close a stale or already closed network session`);
        }
        await page.waitForLoadState("networkidle", { timeout: NETWORK_IDLE_TIMEOUT_MS });
        const deadline = Date.now() + NETWORK_IDLE_TIMEOUT_MS;
        while (true) {
          await flushResponseTasks();
          const inflight = [...inflightRequests.values()].filter((item) => item.session.session_id === session.session_id);
          const lastActivity = sessionActivity.get(session.session_id) || 0;
          if (!inflight.length && Date.now() - lastActivity >= NETWORK_QUIET_WINDOW_MS) break;
          if (Date.now() >= deadline) throw new Error(`${stage}: network did not become idle with inflight=0`);
          await page.waitForTimeout(25);
        }
        await assertNetworkBoundary(stage, session);
        closedSessions.add(session.session_id);
        await page.waitForTimeout(50);
        await assertNetworkBoundary(`${stage}:sealed`, session);
      };
      if (typeof context.routeWebSocket !== "function") throw new Error("Playwright WebSocket routing is required for fail-closed motion QA");
      await context.routeWebSocket("**/*", socketRoute => {
        const session = activeSession;
        const origin = Object.freeze({
          request_id: `${viewport.name}:ws:${++requestCounter}`,
          session,
          method: "GET",
          url: socketRoute.url(),
          purpose: "blocked_or_unknown"
        });
        const entry = baseNetworkEntry(origin, "websocket", false);
        entry.failure_text = "websocket_blocked_before_server_connection";
        appendNetworkEntry(session, entry);
        fatalNetworkError = new Error(`WebSocket was recorded and blocked before server connection: ${socketRoute.url()}`);
        socketRoute.close({ code: 1008, reason: "motion_qa_websocket_forbidden" });
      });
      await context.route("**/*", async intercepted => {
        const session = activeSession;
        const request = intercepted.request();
        const method = request.method().toUpperCase();
        let parsed = null;
        try {
          parsed = exactLocalUrl(request.url());
        } catch {}
        const purpose = purposeFor(parsed);
        const allowed = Boolean(parsed && ALLOWED_READ_METHODS.has(method) && purpose !== "blocked_or_unknown");
        const origin = Object.freeze({
          request_id: `${viewport.name}:http:${++requestCounter}`,
          session,
          method,
          url: request.url(),
          purpose
        });
        requestOrigins.set(request, origin);
        inflightRequests.set(origin.request_id, origin);
        const entry = baseNetworkEntry(origin, "request", allowed);
        appendNetworkEntry(session, entry);
        if (!allowed) {
          fatalNetworkError = new Error(`Blocked motion QA request before network dispatch (${method} ${request.url()})`);
          await intercepted.abort("blockedbyclient");
          return;
        }
        await intercepted.continue();
      });
      const page = await context.newPage();
      context.on("response", (response) => {
        const request = response.request();
        const origin = requestOrigins.get(request);
        if (!origin) {
          fatalNetworkError = new Error(`Response has no immutable request origin: ${response.url()}`);
          return;
        }
        if (terminalRequestIds.has(origin.request_id)) fatalNetworkError = new Error(`Request has duplicate terminal events: ${origin.request_id}`);
        terminalRequestIds.add(origin.request_id);
        const entry = baseNetworkEntry(origin, "response", true);
        entry.status_code = response.status();
        entry.content_type = String(response.headers()["content-type"] || "");
        appendNetworkEntry(origin.session, entry);
        const task = (async () => {
          try {
            const bytes = await response.body();
            entry.body_sha256 = sha256Bytes(bytes);
            entry.body_size_bytes = bytes.length;
            if (bytes.length > MAX_FASTAPI_RESPONSE_BYTES && origin.purpose !== "vite_preview_dist_resource") {
              throw new Error(`FastAPI response exceeds bounded evidence limit: ${response.url()}`);
            }
            const mediaType = entry.content_type.split(";", 1)[0].trim().toLowerCase();
            if (entry.status_code < 200 || entry.status_code >= 300) {
              throw new Error(`Allowed local response must be 2xx: ${response.url()} (${entry.status_code})`);
            }
            if (origin.purpose === "vite_preview_dist_resource") {
              const parsed = exactLocalUrl(response.url());
              entry.dist_path = parsed.pathname === "/" ? "index.html" : decodeURIComponent(parsed.pathname.replace(/^\//, ""));
              const expected = manifestEntries.get(entry.dist_path);
              entry.expected_dist_sha256 = expected?.sha256 || "";
              entry.body_matches_dist = Boolean(
                parsed.port === baseUrl.port && expected && expected.sha256 === entry.body_sha256 &&
                expected.size_bytes === entry.body_size_bytes &&
                (expected.content_type === mediaType || (expected.content_type === "text/javascript" && mediaType === "application/javascript"))
              );
              entry.body_schema_valid = entry.body_matches_dist;
              if (!entry.body_matches_dist) throw new Error(`Served response is not the pinned desktop/dist artifact: ${response.url()}`);
            } else if (origin.purpose === "fastapi_health_identity" || origin.purpose === "fastapi_cache_read") {
              if (mediaType !== "application/json") throw new Error(`FastAPI response is not application/json: ${response.url()}`);
              let payload;
              try { payload = JSON.parse(bytes.toString("utf8")); } catch { throw new Error(`FastAPI response JSON is invalid: ${response.url()}`); }
              const parsed = exactLocalUrl(response.url());
              const analysis = analyzeFastApiResponse(payload, {
                endpoint: parsed.pathname,
                method: origin.method,
                statusCode: entry.status_code,
                bodySha256: entry.body_sha256,
                bodySizeBytes: entry.body_size_bytes,
                health: origin.purpose === "fastapi_health_identity"
              });
              entry.response_semantic_summary = analysis.summary;
              entry.response_semantic_digest = analysis.digest;
              entry.body_schema_valid = analysis.valid;
              if (!entry.body_schema_valid) throw new Error(`FastAPI response envelope failed closed-schema validation: ${response.url()}`);
            } else {
              throw new Error(`Response purpose is not allowlisted: ${origin.purpose}`);
            }
          } catch (error) {
            entry.failure_text = String(error.message || error);
            fatalNetworkError = new Error(`Failed to validate browser response body: ${entry.failure_text}`);
          } finally {
            inflightRequests.delete(origin.request_id);
          }
        })();
        responseTasks.add(task);
        task.finally(() => responseTasks.delete(task));
      });
      context.on("requestfailed", (request) => {
        const origin = requestOrigins.get(request);
        if (!origin) {
          fatalNetworkError = new Error(`Failed request has no immutable request origin: ${request.url()}`);
          return;
        }
        if (terminalRequestIds.has(origin.request_id)) fatalNetworkError = new Error(`Request has duplicate terminal events: ${origin.request_id}`);
        terminalRequestIds.add(origin.request_id);
        const entry = baseNetworkEntry(origin, "requestfailed", false);
        entry.failure_text = String(request.failure()?.errorText || "request_failed");
        appendNetworkEntry(origin.session, entry);
        inflightRequests.delete(origin.request_id);
        fatalNetworkError = new Error(`Browser request failed: ${request.url()} (${entry.failure_text})`);
      });
      page.on("console", (message) => {
        if (message.type() === "error") errors.push({ viewport: viewport.name, console_error: message.text() });
      });
      page.on("pageerror", (error) => {
        errors.push({ viewport: viewport.name, page_error: String(error.message || error) });
      });
      page.on("websocket", (socket) => {
        const session = activeSession;
        const origin = Object.freeze({
          request_id: `${viewport.name}:ws:${++requestCounter}`,
          session,
          method: "GET",
          url: socket.url(),
          purpose: "blocked_or_unknown"
        });
        const entry = baseNetworkEntry(origin, "websocket", false);
        entry.failure_text = "websocket_forbidden";
        appendNetworkEntry(session, entry);
        fatalNetworkError = new Error(`WebSocket is forbidden during motion QA: ${socket.url()}`);
        if (typeof socket.close === "function") socket.close();
      });
      const warmupUrl = new URL("/#health", baseUrl).toString();
      warmupNavigationLedger.push({ sequence_no: 1, viewport: viewport.name, url: warmupUrl });
      await page.goto(warmupUrl, { waitUntil: "networkidle", timeout: 20000 });
      await page.waitForTimeout(args.reducedMotion ? 80 : 500);
      await closeSession(activeSession, `warmup:${viewport.name}`);
      activeSession = createSession("manifest", "#manifest", manifestRequestLedger);
      await page.evaluate(async paths => {
        for (const path of paths) {
          const url = path === "index.html" ? "/" : `/${path}`;
          const response = await fetch(url, { method: "GET", cache: "no-store", credentials: "omit" });
          if (!response.ok) throw new Error(`manifest_fetch_failed:${url}:${response.status}`);
          await response.arrayBuffer();
        }
      }, currentDistManifest.entry_graph);
      await closeSession(activeSession, `manifest:${viewport.name}`);
      for (const route of routes) {
        const activeRequestLedger = [];
        activeSession = createSession("route", route.route, activeRequestLedger);
        const transitionStartedUs = await page.evaluate(() => Math.round(performance.now() * 1000));
        await page.evaluate(hash => { window.location.hash = hash; }, route.navigation_hash || route.route);
        await page.waitForFunction(
          expected => document.querySelector(".route-stage h1")?.textContent?.trim() === expected.heading && Boolean(document.querySelector(expected.anchor)),
          route,
          { timeout: 20000 }
        );
        const routeBudgetUs = route.route === "#candidates" ? PERFORMANCE_BUDGETS.candidate_radar_first_stable_us : PERFORMANCE_BUDGETS.route_transition_observed_us;
        const animationObservation = await page.evaluate(async budgetUs => {
          const stage = document.querySelector(".route-stage");
          const animations = document.getAnimations().filter(animation => {
            const target = animation.effect?.target;
            return target instanceof Element && Boolean(stage && (target === stage || stage.contains(target)));
          });
          let timedOut = false;
          await Promise.race([
            Promise.allSettled(animations.map(animation => animation.finished)),
            new Promise(resolve => window.setTimeout(() => { timedOut = true; resolve(); }, Math.ceil(budgetUs / 1000)))
          ]);
          return { count: animations.length, completed: !timedOut };
        }, routeBudgetUs);
        const routeTransitionUs = (await page.evaluate(() => Math.round(performance.now() * 1000))) - transitionStartedUs;
        const visualSettleWaitMs = args.reducedMotion ? 80 : 500;
        await page.waitForTimeout(visualSettleWaitMs);
        await assertNetworkBoundary(`pre-inspect:${viewport.name}:${route.route}`, activeSession);
        const inspected = await inspectPage(page, route, transitionStartedUs);
        const currentUrl = exactLocalUrl(page.url());
        const screenshotPath = resolve(outputDir, viewport.name, `${route.route.replace("#", "") || "home"}.png`);
        const viewportDir = resolve(outputDir, viewport.name);
        try { await mkdir(viewportDir); } catch (error) { if (error?.code !== "EEXIST") throw error; }
        const viewportDirStat = await lstat(viewportDir);
        if (!viewportDirStat.isDirectory() || viewportDirStat.isSymbolicLink()) throw new Error("Motion viewport directory must be a real directory");
        const screenshotBytes = await page.screenshot({ fullPage: false, type: "png" });
        decodePng(screenshotBytes, viewport.width, viewport.height);
        await writeExclusiveFile(screenshotPath, screenshotBytes);
        await closeSession(activeSession, `post-screenshot:${viewport.name}:${route.route}`);
        const postRequests = activeRequestLedger.filter(item => item.method === "POST");
        const passed =
          inspected.expected_heading_ready === true &&
          animationObservation.count >= 1 &&
          animationObservation.completed === true &&
          inspected.long_task_observer_ready === true &&
          inspected.layout_shift_observer_ready === true &&
          inspected.clipped_count === 0 &&
          inspected.horizontal_overflow_px === 0 &&
          inspected.overlap_count === 0 &&
          inspected.unnamed_interactive_count === 0 &&
          inspected.concealed_motion_content_count === 0 &&
          inspected.expected_anchor_ready === true &&
          inspected.motion_marker_minimum_ready === true &&
          postRequests.length === 0 &&
          inspected.long_task_over_50ms_count <= PERFORMANCE_BUDGETS.long_task_over_50ms_count &&
          inspected.largest_motion_layout_shift_ppm <= PERFORMANCE_BUDGETS.largest_motion_layout_shift_ppm &&
          routeTransitionUs <= routeBudgetUs;
        rows.push({
          route: route.route,
          label: route.label,
          viewport: viewport.name,
          width: viewport.width,
          height: viewport.height,
          url: currentUrl.toString(),
          risk_focus: route.risk_focus,
          status: passed ? "passed" : "review_required",
          visual_qa_complete: passed,
          performance_trace_complete: true,
          route_transition_observed_us: routeTransitionUs,
          visual_settle_wait_ms: visualSettleWaitMs,
          route_transition_budget_us: routeBudgetUs,
          navigation_animation_count: animationObservation.count,
          navigation_animation_wait_completed: animationObservation.completed,
          long_task_over_50ms_count: inspected.long_task_over_50ms_count,
          largest_motion_layout_shift_ppm: inspected.largest_motion_layout_shift_ppm,
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
          expected_heading: route.heading,
          heading_text: inspected.heading_text,
          expected_anchor: inspected.expected_anchor,
          expected_anchor_ready: inspected.expected_anchor_ready,
          motion_marker_name: route.marker,
          motion_marker_minimum: route.marker_minimum,
          motion_marker_minimum_ready: inspected.motion_marker_minimum_ready,
          long_task_observer_ready: inspected.long_task_observer_ready,
          layout_shift_observer_ready: inspected.layout_shift_observer_ready,
          request_count: activeRequestLedger.length,
          request_ledger: activeRequestLedger,
          post_request_count: postRequests.length,
          post_request_urls: postRequests.map(item => `${item.protocol}//${item.hostname}:${item.port}${item.path}`),
          motion_markers: inspected.motion_markers,
          screenshot_path: relativeArtifactPath(artifactRoot, screenshotPath)
        });
      }
      await context.close();
      await flushResponseTasks();
      if (fatalNetworkError || lateNetworkEvents.length || inflightRequests.size) {
        throw fatalNetworkError || new Error(`final:${viewport.name}: late network activity detected`);
      }
    }
  } finally {
    await browser.close();
  }
  if (lateNetworkEvents.length) throw new Error("Final all-stage network check detected activity after a phase was sealed");
  const finalRepository = repositoryIdentity(args.expectedHeadFull);
  const finalFrontend = await frontendIdentity();
  const finalFrontendService = await frontendServiceIdentity(baseUrl, finalFrontend.distManifest.manifest_digest);
  const finalFastapiService = await fastApiServiceIdentity();
  const finalPackageBinding = await formalPackageBinding(actualHeadFull);
  if (
    finalRepository.actualHeadFull !== actualHeadFull || finalRepository.worktreeClean !== worktreeClean ||
    finalFrontend.frontendSourceDigest !== frontendSourceDigest ||
    finalFrontend.buildIdentityDigest !== buildIdentityDigest ||
    canonicalJson(finalFrontend.distManifest) !== canonicalJson(currentDistManifest) ||
    finalFrontendService.identity_digest !== frontendService.identity_digest ||
    finalFastapiService.health_contract_digest !== fastapiService.health_contract_digest ||
    finalFastapiService.service !== fastapiService.service ||
    finalPackageBinding.identity_digest !== packageBinding.identity_digest
  ) {
    throw new Error("Repository, frontend source/dist, service listener, or formal package changed during motion QA; artifacts were not attested");
  }
  const blockerRows = rows.filter((row) => row.status !== "passed");
  const allNetworkEvents = [
    ...warmupRequestLedger,
    ...manifestRequestLedger,
    ...rows.flatMap((row) => row.request_ledger)
  ];
  const requestFailedCount = allNetworkEvents.filter((entry) => entry.event_type === "requestfailed").length;
  const websocketCount = allNetworkEvents.filter((entry) => entry.event_type === "websocket").length;
  if (requestFailedCount || websocketCount || lateNetworkEvents.length) throw new Error("Final network ledger contains a failed request, WebSocket, or late event");
  const requestsById = new Map();
  const terminalsById = new Map();
  for (const entry of allNetworkEvents) {
    const target = entry.event_type === "request" ? requestsById : terminalsById;
    if (target.has(entry.request_id)) throw new Error(`Final network ledger has duplicate ${entry.event_type === "request" ? "request" : "terminal"} entry: ${entry.request_id}`);
    target.set(entry.request_id, entry);
  }
  if (requestsById.size !== terminalsById.size) throw new Error("Final network ledger has unpaired inflight requests");
  for (const [requestId, request] of requestsById) {
    const terminal = terminalsById.get(requestId);
    if (!terminal || ["session_id", "phase", "route", "viewport", "method", "url", "purpose"].some(key => terminal[key] !== request[key])) {
      throw new Error(`Final network ledger request/terminal origin mismatch: ${requestId}`);
    }
  }
  const generatedAt = new Date().toISOString();
  const rawTracePath = resolve(outputDir, "motion_performance_trace.json");
  const rawTrace = {
    schema_version: TRACE_SCHEMA_VERSION,
    generated_at: generatedAt,
    head_full: actualHeadFull,
    run_mode: runMode,
    frontend_source_digest: frontendSourceDigest,
    build_identity_digest: buildIdentityDigest,
    row_count: rows.length,
    rows,
    warmup_request_count: warmupRequestLedger.length,
    warmup_request_ledger: warmupRequestLedger,
    warmup_navigation_count: warmupNavigationLedger.length,
    warmup_navigation_ledger: warmupNavigationLedger,
    manifest_request_count: manifestRequestLedger.length,
    manifest_request_ledger: manifestRequestLedger,
    late_network_events: lateNetworkEvents,
    inflight_request_ids: [],
    network_event_count: allNetworkEvents.length,
    request_failed_count: requestFailedCount,
    websocket_count: websocketCount,
    dist_manifest_digest: currentDistManifest.manifest_digest,
    frontend_service_identity_digest: frontendService.identity_digest,
    fastapi_service_identity_digest: fastapiService.identity_digest,
    package_identity_digest: packageBinding.identity_digest,
    error_count: errors.length,
    errors
  };
  await atomicJson(rawTracePath, rawTrace, 0o600, false);
  const rawTraceBytes = await readRegularFile(rawTracePath, 0o600);
  const screenshotArtifacts = [];
  for (const row of rows) {
    const screenshotPath = resolve(artifactRoot, row.screenshot_path);
    const screenshotBytes = await readRegularFile(screenshotPath, 0o600, MAX_PNG_FILE_BYTES);
    const decoded = decodePng(screenshotBytes, row.width, row.height);
    screenshotArtifacts.push({
      path: row.screenshot_path,
      sha256: sha256Bytes(screenshotBytes),
      size_bytes: screenshotBytes.length,
      route: row.route,
      viewport: row.viewport,
      width: decoded.width,
      height: decoded.height
    });
  }
  const unsignedReport = {
    schema_version: SCHEMA_VERSION,
    status: blockerRows.length || errors.length ? "motion_browser_qa_review_required" : "motion_browser_qa_passed",
    scope: "explicit_local_browser_visual_performance_run",
    run_id: runId,
    generated_at: generatedAt,
    expected_head_full: args.expectedHeadFull,
    head_full: actualHeadFull,
    worktree_clean: worktreeClean,
    run_mode: runMode,
    reduced_motion: args.reducedMotion,
    base_url: baseUrl.origin,
    artifact_root: args.artifactRoot,
    selected_route: args.route || "all",
    frontend_source_digest: frontendSourceDigest,
    build_identity_digest: buildIdentityDigest,
    route_count: routes.length,
    viewport_count: QA_VIEWPORTS.length,
    qa_matrix_count: rows.length,
    passed_count: rows.length - blockerRows.length,
    review_required_count: blockerRows.length,
    console_error_count: errors.length,
    visual_qa_complete: blockerRows.length === 0 && errors.length === 0,
    browser_performance_verified: blockerRows.length === 0 && errors.length === 0,
    performance_budgets: PERFORMANCE_BUDGETS,
    visual_acceptance_criteria: VISUAL_ACCEPTANCE_CRITERIA,
    rows,
    errors,
    warmup_request_count: warmupRequestLedger.length,
    warmup_request_ledger: warmupRequestLedger,
    warmup_navigation_count: warmupNavigationLedger.length,
    warmup_navigation_ledger: warmupNavigationLedger,
    manifest_request_count: manifestRequestLedger.length,
    manifest_request_ledger: manifestRequestLedger,
    late_network_events: lateNetworkEvents,
    inflight_request_ids: [],
    network_event_count: allNetworkEvents.length,
    request_failed_count: requestFailedCount,
    websocket_count: websocketCount,
    service_workers_blocked: true,
    dist_manifest: currentDistManifest,
    frontend_service_identity: frontendService,
    fastapi_service_identity: fastapiService,
    package_binding: packageBinding,
    raw_trace: {
      path: relativeArtifactPath(artifactRoot, rawTracePath),
      sha256: sha256Bytes(rawTraceBytes),
      size_bytes: rawTraceBytes.length
    },
    screenshots: screenshotArtifacts,
    cache_only: true,
    starts_no_servers: true,
    local_urls_only: true,
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    note: "Local browser QA evidence. It is not a provider call, not a trading path, and not durable CI evidence until reviewed and intentionally promoted."
  };
  const reportPath = resolve(outputDir, "motion_browser_qa_report.json");
  const reportRelpath = relativeArtifactPath(artifactRoot, reportPath);
  const { report } = await appendAttestation({
    artifactRoot,
    reportPath,
    reportRelpath,
    unsignedReport,
    generatedAt,
    headFull: actualHeadFull,
    runMode,
    frontendSourceDigest,
    buildIdentityDigest
  });
  return { report, reportPath };
}

verifyCanonicalVector();
const args = parseArgs(process.argv);
if (args.selfTestFastApiValidator) {
  try {
    if (process.argv.length !== 3) throw new Error("FastAPI validator self-test accepts no other arguments");
    console.log(JSON.stringify(selfTestFastApiValidator(), null, 2));
    process.exit(0);
  } catch (error) {
    console.error(`motion_browser_qa_runner: FastAPI validator self-test failed: ${error.message || error}`);
    process.exit(1);
  }
}
if (args.initializeRunnerTrust) {
  try {
    if (args.artifactRoot !== DEFAULT_ARTIFACT_ROOT || args.route || !args.screenshots || args.reducedMotion) {
      throw new Error("Trust initialization accepts only --expected-head-full and the default artifact root");
    }
    repositoryIdentity(args.expectedHeadFull);
    const initialized = await initializeRunnerTrust(resolve(PROJECT_ROOT, DEFAULT_ARTIFACT_ROOT));
    console.log(JSON.stringify({
      schema_version: IDENTITY_SCHEMA_VERSION,
      status: "motion_runner_trust_initialized_explicitly",
      installation_id: initialized.installation_id,
      initialized_at: initialized.initialized_at,
      key_or_fingerprint_exposed: false
    }, null, 2));
    process.exit(0);
  } catch (error) {
    console.error(`motion_browser_qa_runner: trust initialization failed: ${error.message || error}`);
    process.exit(1);
  }
}
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
