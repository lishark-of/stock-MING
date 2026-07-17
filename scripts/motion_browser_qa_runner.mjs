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
const FASTAPI_RESPONSE_SEMANTIC_SCHEMA_VERSION = "command_center_3_motion_fastapi_response_semantic.v3";
const FASTAPI_CACHE_ENDPOINT_COUNT = 21;
// /api/migration/status is a read-only progress envelope.  Its nested
// ``safe_fields`` objects intentionally carry sanitized absence/usage metadata
// whose names contain token/nonce/secret vocabulary, but never raw material.
// Keep this allowlist endpoint-local; do not weaken the global secret scanner.
const MIGRATION_SAFE_FIELDS = new Set([
  "authorization_nonce_digest", "authorization_nonce_present", "authorization_nonce_consumed",
  "total_tokens", "retry_tokens", "token_usage_complete", "token_budget_cost_evidence_complete",
  "contains_secret",
]);
const MIGRATION_SAFE_SUMMARY_FIELDS = new Set(["requires_token_cost_redaction_review"]);

const FASTAPI_CACHE_CONTRACTS = new Map([
  ["/api/audit/cache", { schema: "call_ledger_audit_cache.v1", packet: "command_center_3_call_ledger_audit_cache", ledgerApis: ["local_call_ledger_audit_cache"] }],
  ["/api/audit/user-route-qa", { schema: "command_center_3_user_route_qa_evidence_cache.v1", packet: "command_center_3_user_route_qa_evidence_cache", strictCurrentRead: true, ledgerApis: ["GET /api/audit/user-route-qa"] }],
  ["/api/bootstrap/status", { schema: "command_center_bootstrap_runtime_mode.v1", packet: "command_center_3_bootstrap_runtime_mode_packet", ledgerApis: ["local_bootstrap_runtime_mode_cache"] }],
  ["/api/desktop/preflight-cache", { schema: "desktop_shell_preflight_cache.v1", packet: "command_center_3_desktop_shell_preflight_cache", strictCurrentRead: true, ledgerApis: ["local_desktop_shell_preflight_cache"] }],
  ["/api/factor-quant/cache", { schema: "factor_quant_hub.v1", packet: "command_center_factor_quant_hub_packet", strictCurrentRead: true, ledgerApis: ["local_factor_quant_cache"] }],
  ["/api/next-session/cache", { schema: "next_session_projection.v1", packet: "command_center_next_session_projection_packet", allowCacheMissing: true, includeMissingData: true, strictCurrentRead: true, ledgerApis: ["local_next_session_cache"] }],
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
  ["/api/data-capability/cache", { schema: "data_capability_cache.v1", packet: "command_center_3_data_capability_cache", ledgerApis: ["local_data_capability_cache"] }],
  ["/api/migration/status", { schema: "command_center_3_migration_status.v2", packet: "command_center_3_migration_status", ledgerApis: ["local_migration_status_cache"] }],
  ["/api/tasks", { schema: "command_center_3_task_status_index.v1", packet: "command_center_3_task_status_index", historicalTaskSummary: true, ledgerApis: ["local_task_status_index"] }],
  ["/api/tasks/catalog", { schema: "command_center_3_task_catalog.v1", packet: "command_center_3_task_catalog", ledgerApis: ["local_task_catalog_cache"] }],
  ["/api/worker/cache", { schema: "worker_runtime_cache.v1", packet: "command_center_3_worker_runtime_cache", strictCurrentRead: true, ledgerApis: ["local_worker_runtime_cache"] }],
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
const STRICT_CURRENT_LEDGER_FALSE_FLAGS = [
  "external", "external_calls_triggered", "provider_or_model_calls", "provider_called",
  "model_called", "worker_called", "tushare_called", "deepseek_called", "github_called",
  "trade_called", "trading_called", "broker_called", "order_called", "real_trading_enabled",
  "contains_secret"
];
const HISTORICAL_FLAG_NAMES = new Set([
  "external_calls_triggered", "tushare_called", "deepseek_called", "github_called",
  "provider_or_model_calls", "provider_called", "model_called", "worker_called",
  "trade_called", "trading_called", "broker_called", "order_called"
]);
const FORBIDDEN_SECRET_KEYS = new Set([
  "api_key", "apikey", "api_token", "access_key", "access_token", "refresh_token", "authorization",
  "password", "passwd", "secret", "token", "credential", "client_secret", "private_key",
  "bearer_token", "cookie", "set_cookie", "api_keys", "api_tokens", "access_tokens", "refresh_tokens",
  "credentials", "passwords", "secrets", "tokens", "private_keys", "bearer_tokens", "cookies", "set_cookies"
]);
const STRICT_ANY_TAIL_FORBIDDEN = new Set([
  "api_key", "apikey", "api_token", "access_key", "access_token", "refresh_token", "authorization",
  "password", "passwd", "client_secret", "private_key", "bearer_token", "cookie", "set_cookie",
  "api_keys", "api_tokens", "access_tokens", "refresh_tokens", "passwords", "private_keys",
  "bearer_tokens", "cookies", "set_cookies", "credentials", "token", "tokens", "secret", "secrets", "credential"
]);
const STRICT_STATUS_TAIL_FORBIDDEN = new Set(["current", "runtime", "active"]);
const SAFE_BOOLEAN_SECRET_POLICIES = new Map([
  ["contains_secret", false],
  ["display_strips_query_hash_username_password", true],
  ["launcher_diagnostic_urls_contain_secret", false],
  ["launcher_prints_raw_query_hash_username_password", false],
  ["authorization_header_allowed", false],
  ["authorization_nonce_caller_generated", true],
  ["authorization_nonce_present", null],
  ["authorization_nonce_raw_persisted", false],
  ["authorization_nonce_required", true],
  ["authorization_nonce_strong", null],
  ["config_audit_includes_credential_values", false],
  ["credential_value_allowed", false],
  ["credential_value_budget_log_allowed", false],
  ["credential_value_exposed", false],
  ["credential_value_read_allowed", false],
  ["credential_values_exposed", false],
  ["credential_values_read", false],
  ["credential_env_key_name_allowed", false],
  ["credential_env_key_names_exposed", false],
  ["credential_env_key_names_exposed_to_frontend", false],
  ["credential_env_key_names_included", false],
  ["does_not_scan_secret_values", true],
  ["does_not_expose_credentials", true],
  ["does_not_include_token_or_raw_log", true],
  ["does_not_read_api_keys", true],
  ["desktop_shortcut_installer_reads_credentials", false],
  ["frontend_stores_tokens", false],
  ["ledger_redaction_credential_material_exposed", false],
  ["lineage_must_exclude_credential_values", true],
  ["live_full_requires_separate_authorization", null],
  ["live_full_reserved_requires_separate_authorization", true],
  ["live_light_credential_values_exposed", false],
  ["live_light_ledger_redaction_credential_material_exposed", false],
  ["ownership_audit_includes_credential_values", false],
  ["promotion_review_scope_hash_input_includes_secret", false],
  ["promotion_scope_hash_input_includes_secret", false],
  ["reads_credential_values", false],
  ["requires_separate_live_provider_authorization", true],
  ["retirement_scope_hash_input_includes_secret", false],
  ["review_scope_hash_input_includes_secret", false],
  ["scans_secret_values", false],
  ["separate_authorization_required", true],
  ["scope_intake_secret_like_payload_fields_dropped", true],
  ["secret_like_model_value_redacted", false],
  ["secret_like_payload_fields_dropped", true],
  ["secret_like_raw_redacted", false],
  ["search_quant_projection_p1_contains_secret", false],
  ["server_secret_values_exposed", false],
  ["server_secret_values_read", false],
  ["status_get_exposes_credential_values", false],
  ["status_get_reads_credential_values", false],
  ["requires_live_provider_authorization_flag", true],
  ["token_usage_record_required", true],
  ["runtime_budget_token_usage_record_required", true],
  ["live_light_scope_intake_secret_like_payload_fields_dropped", true],
  ["live_light_runtime_budget_token_usage_record_required", true],
  ["credential_presence_check_reads_values", false],
  ["credential_presence_check_exposes_values", false],
  ["credential_presence_check_exposes_env_key_names", false],
  ["credential_presence_check_exposes_value_lengths", false],
  ["worker_execution_scope_hash_input_includes_secret", false]
]);
const SAFE_BOOLEAN_METADATA_POLICIES = new Map([
  ["cache_may_contain_token_key", false], ["contains_secret_scan_step", null],
  ["credential_missing_may_be_verified", false], ["credential_preflight_contract_visible", true],
  ["credential_preflight_ready", false], ["credential_preflight_ready_required", true],
  ["credential_presence_booleans_only", true], ["credential_presence_check_requires_post", true],
  ["credential_presence_check_requires_user_approval", true], ["credential_present", true],
  ["frontend_packet_may_contain_token_key", false], ["frontend_token_exposure_absent", true],
  ["hard_boundary_token_key_frontend_log_packet_cache_allowed", false], ["high_risk_secret_scan_step", true],
  ["live_light_credential_preflight_contract_visible", true],
  ["live_light_credential_presence_check_requires_post", true],
  ["live_light_credential_presence_check_requires_user_approval", true],
  ["live_light_status_get_checks_credential_presence", false], ["loads_token_or_key", false],
  ["logs_may_contain_token_key", false], ["payload_secret_fields_dropped", true],
  ["requires_credential_preflight_ready", true],
  ["runtime_hard_boundary_token_key_frontend_log_packet_cache_allowed", false],
  ["scope_hash_excludes_secret_fields", true],
  ["secret_artifact_allowlist_review_head_matches_current", false],
  ["secret_artifact_allowlist_review_ready", false],
  ["secret_artifact_allowlist_review_receipt_calls_no_github_api_from_cache", true],
  ["secret_artifact_allowlist_review_receipt_head_matches_current", false],
  ["secret_artifact_allowlist_review_receipt_is_local_ignored", true],
  ["secret_artifact_allowlist_review_receipt_is_not_release_review", true],
  ["secret_artifact_allowlist_review_receipt_present", true], ["secret_artifact_scan_required", true],
  ["secret_keyword_review_contract_exists", true], ["secret_keyword_review_contract_is_structured", true],
  ["secret_keyword_review_contract_step", true], ["server_secret_presence_checked", true],
  ["server_secret_present", true], ["status_get_checks_credential_presence", false],
  ["motion_tokens_present", true],
  ["live_light_runtime_budget_token_usage_required", true],
  ["server_side_tushare_credential_present", true],
  ["task_status_may_contain_token_key", false], ["tauri_app_open_autostart_loads_token_or_key", false],
  ["token_budget_cost_evidence_complete", false], ["token_budget_estimate_present", true],
  ["token_key_allowed", false], ["token_key_exposure_allowed", false],
  ["token_key_frontend_exposure", false], ["token_key_frontend_log_packet_cache_allowed", false],
  ["token_usage_required", true], ["token_usage_visible_safe_summary_only", true]
]);
const SAFE_NON_SECRET_NUMBER_KEYS = new Set([
  "blocking_credential_missing_provider_count", "credential_missing_provider_count", "credential_present_provider_count",
  "credential_required_provider_count", "credential_row_count", "deepseek_credential_missing_provider_count",
  "latest_trade_cal_provider_acceptance_dry_run_credential_row_count", "max_tokens_per_attempt", "output_token_estimate",
  "prompt_token_estimate", "provider_parity_credential_missing_count", "search_quant_projection_acceptance_credential_missing_count",
  "secret_artifact_allowlist_review_receipt_missing_evidence_count"
]);
const SAFE_NON_SECRET_TEXT_KEYS = new Set([
  "credential_missing_status", "credential_presence_check_method", "credential_presence_check_route",
  "credential_presence_status", "safe_credential_label", "secret_artifact_allowlist_review_receipt_status",
  "server_secret_presence_check"
]);
const SAFE_NON_SECRET_CONTAINER_KEYS = new Set([
  "credential_presence_summary", "latest_trade_cal_provider_acceptance_dry_run_credential_rows",
  "live_light_credential_preflight_contract", "provider_parity_credential_presence_rows",
  "search_quant_projection_credential_presence_rows", "credential_presence_rows"
]);
const SAFE_NON_SECRET_AUDIT_CONTAINER_KEYS = new Set([
  "secret_artifact_allowlist_review_receipt_missing_evidence", "secret_artifact_allowlist_review_receipt"
]);
const SECRET_MATERIAL_SUFFIXES = new Set([
  "blob", "body", "bytes", "content", "data", "document", "entry", "field", "header", "headers",
  "env", "environment", "fingerprint", "hash", "item", "json", "map", "material", "metadata",
  "name", "object", "payload", "pem", "raw", "record", "request", "response", "sha", "sha256",
  "str", "string", "text", "value", "values", "variable", "digest"
]);
const MAX_SECRET_SCAN_DEPTH = 128;
const MAX_SECRET_SCAN_NODES = 250000;
// These are explicitly sanitized metadata, not credentials or credential-derived material.
const SAFE_SENSITIVE_STATUS_VALUES = new Set([
  "all_required_env_keys_present_no_values_read", "blocked_missing_credentials_no_external_call", "credential_present",
  "credential_preflight_contract_visible_post_only", "inactive_until_live_light_mode", "missing",
  "missing_no_value_read", "not_required_by_payload", "present_no_value_read", "present_no_values_read", "present_but_not_verified",
  "provider_empty_result_not_verified", "provider_no_record_not_negative_evidence",
  "provider_permission_denied_safe_error", "required_env_key_missing_no_values_read",
  "secret_artifact_allowlist_review_ready", "secret_artifact_allowlist_review_receipt_present_but_not_verified",
  "skipped_budget_exceeded_no_external_call",
  "skipped_due_to_rate_limit_reused_existing_task", "clean", "clean_or_allowed_assets_only",
  "reviewed_no_high_risk_values", "secret_keyword_review_contract_ready_manual_review_pending", "credential_present",
  "credential_missing", "present_no_values_read"
]);
const SAFE_SENSITIVE_PROVIDER_VALUES = new Set(["deepseek", "tushare"]);
const SAFE_SENSITIVE_CREDENTIAL_REF_RE = /^(?:deepseek|tushare)_(?:primary_credential|secondary_credential_\d+)$/;
const SAFE_SENSITIVE_HASH_RE = /^(?:[0-9a-f]{16}|[0-9a-f]{40}|[0-9a-f]{64})$/;
const SAFE_SENSITIVE_ROUTE_RE = /^(?:GET|POST) \/api\/[a-z0-9/_-]+$/;
const SAFE_SENSITIVE_SCHEMA_RE = /^command_center_[a-z0-9_]+\.v\d+$/;
const SAFE_AUDIT_MISSING_EVIDENCE_VALUES = new Set([
  "periodic secret/artifact allowlist review receipt", "readable periodic secret/artifact allowlist review receipt",
  "secret/artifact allowlist review receipt schema", "secret/artifact allowlist review ready status",
  "current HEAD matching secret/artifact allowlist review", "explicit user authorization for allowlist review",
  "clean high-risk secret scan review", "structured secret keyword review", "clean generated artifact scan review",
  "cache read no-external/no-provider/no-trade boundary flags"
]);
const SAFE_AUDIT_RECEIPT_KEYS = new Set([
  "schema_version", "status", "scope", "receipt_path", "read_status", "current_head", "current_head_full",
  "current_branch", "head_matches_current", "periodic_allowlist_review_ready", "false_positive_allowlist_review_ready",
  "release_review_complete", "release_gate_complete", "production_release_complete", "cache_get_external_calls",
  "cache_get_calls_github_api", "external_calls_triggered", "tushare_called", "deepseek_called", "github_called",
  "github_api_called", "does_not_execute_trades", "does_not_modify_strategy_action", "contains_secret", "missing_evidence",
  "missing_evidence_count", "high_risk_secret_scan_status", "secret_keyword_review_status", "generated_artifact_scan_status",
  "explicit_user_allowlist_review_authorized", "call_ledger", "branch", "head", "head_full", "manual_review_note_safe",
  "receipt_writer", "reviewed_at_utc", "reviewer", "explicit_user_release_review_authorized", "can_close_goal",
  "strict_closeout_ready", "decision", "remote_artifact_digest", "remote_run_id"
]);
const SAFE_AUDIT_CALL_LEDGER_KEYS = new Set([
  "api", "source", "call_status", "periodic_allowlist_review_ready", "local_fetched_at", "external",
  "github_called", "github_api_called", "does_not_execute_trades", "does_not_modify_strategy_action"
]);
const SAFE_SENSITIVE_BOOLEAN_KEYS = new Set([
  "contains_secret", "credential_values_read", "credential_values_exposed", "env_key_names_included",
  "required", "present", "values_read", "values_exposed", "value_lengths_exposed", "credential_value_exposed",
  "credential_value_read_allowed", "credential_env_key_name_allowed", "external_calls_triggered",
  "tushare_called", "deepseek_called", "github_called", "does_not_execute_trades", "does_not_modify_strategy_action",
  "server_side_tushare_credential_present", "credential_presence_booleans_only", "credential_preflight_ready",
  "credential_preflight_ready_required", "credential_presence_check_requires_post", "credential_presence_check_requires_user_approval",
  "env_key_names_exposed", "present_no_values_read", "required_for_selected_dry_run", "safe_provider_labels_only",
  "status_get_reads_credential_values", "status_get_checks_credential_presence", "status_get_exposes_env_key_names",
  "status_get_exposes_credential_values", "status_get_exposes_value_lengths", "raw_config_dump_allowed",
  "provider_execution_allowed_from_preflight", "model_execution_allowed_from_preflight",
  "production_promotion_allowed_from_preflight", "frontend_packet_may_contain_token_key", "logs_may_contain_token_key",
  "cache_may_contain_token_key", "token_key_allowed", "token_key_exposure_allowed", "motion_tokens_present",
  "credential_presence_check_reads_values", "credential_presence_check_exposes_values", "credential_presence_check_exposes_env_key_names",
  "credential_presence_check_exposes_value_lengths", "checked_by_membership_only", "env_key_name_exposed",
  "cache_get_calls_github_api", "cache_get_external_calls", "explicit_user_allowlist_review_authorized",
  "false_positive_allowlist_review_ready", "github_api_called", "periodic_allowlist_review_ready",
  "production_release_complete", "release_gate_complete", "release_review_complete", "head_matches_current", "external"
]);
const SAFE_SENSITIVE_BOOLEAN_POLARITIES = new Map([
  ["required", null], ["present", null], ["values_read", false], ["values_exposed", false],
  ["value_lengths_exposed", false], ["env_key_names_included", false], ["credential_value_exposed", false],
  ["credential_value_read_allowed", false], ["credential_env_key_name_allowed", false],
  ["external_calls_triggered", false], ["tushare_called", false], ["deepseek_called", false],
  ["github_called", false], ["does_not_execute_trades", true], ["does_not_modify_strategy_action", true],
  ["credential_presence_booleans_only", true], ["credential_preflight_ready", false],
  ["credential_preflight_ready_required", true], ["credential_presence_check_requires_post", true],
  ["credential_presence_check_requires_user_approval", true]
  , ["env_key_names_exposed", false], ["present_no_values_read", true], ["required_for_selected_dry_run", null],
  ["safe_provider_labels_only", true], ["status_get_reads_credential_values", false],
  ["status_get_checks_credential_presence", false], ["status_get_exposes_env_key_names", false],
  ["status_get_exposes_credential_values", false], ["status_get_exposes_value_lengths", false],
  ["raw_config_dump_allowed", false], ["provider_execution_allowed_from_preflight", false],
  ["model_execution_allowed_from_preflight", false], ["production_promotion_allowed_from_preflight", false],
  ["frontend_packet_may_contain_token_key", false], ["logs_may_contain_token_key", false],
  ["cache_may_contain_token_key", false], ["token_key_allowed", false], ["token_key_exposure_allowed", false],
  ["credential_presence_check_reads_values", false], ["credential_presence_check_exposes_values", false],
  ["credential_presence_check_exposes_env_key_names", false], ["credential_presence_check_exposes_value_lengths", false],
  ["checked_by_membership_only", true], ["env_key_name_exposed", false], ["motion_tokens_present", true],
  ["head_matches_current", null], ["explicit_user_allowlist_review_authorized", null],
  ["explicit_user_release_review_authorized", null], ["false_positive_allowlist_review_ready", null],
  ["periodic_allowlist_review_ready", null], ["release_review_complete", null], ["release_gate_complete", null],
  ["production_release_complete", null], ["strict_closeout_ready", null], ["can_close_goal", null],
  ["cache_get_calls_github_api", false], ["cache_get_external_calls", false], ["explicit_user_allowlist_review_authorized", null],
  ["false_positive_allowlist_review_ready", null], ["github_api_called", false], ["periodic_allowlist_review_ready", null],
  ["production_release_complete", false], ["release_gate_complete", false], ["release_review_complete", null],
  ["head_matches_current", null], ["external", false]
]);
const SAFE_SENSITIVE_NUMBER_KEYS = new Set([
  "required_provider_count", "present_provider_count", "missing_provider_count", "credential_ref_count",
  "env_key_name_count", "credential_row_count", "row_count", "max_tokens_per_attempt", "output_token_estimate",
  "prompt_token_estimate", "cost_ceiling_usd_per_million_tokens", "present_key_count", "required_key_count", "missing_evidence_count"
]);
function safeSensitivePrimitive(key, value) {
  if (typeof value === "boolean") {
    if (!SAFE_SENSITIVE_BOOLEAN_KEYS.has(key)) return false;
    if (SAFE_SENSITIVE_BOOLEAN_POLARITIES.has(key)) {
      const expected = SAFE_SENSITIVE_BOOLEAN_POLARITIES.get(key);
      return expected === null || value === expected;
    }
    return !forbiddenSecretFieldKey(key) || safeBooleanSecretPolicy(key, value);
  }
  if (typeof value === "number") return SAFE_SENSITIVE_NUMBER_KEYS.has(key) && Number.isFinite(value) && value >= 0 && value <= 1_000_000_000;
  if (typeof value !== "string") return value === null;
  if (SAFE_SENSITIVE_STATUS_VALUES.has(value)) return true;
  if (key === "provider" || key === "provider_name") return SAFE_SENSITIVE_PROVIDER_VALUES.has(value);
  if (key === "credential_ref" || key === "credential_refs") return SAFE_SENSITIVE_CREDENTIAL_REF_RE.test(value);
  if (key === "schema_version") return /^[a-z0-9_]+\.v\d+$/.test(value) &&
    (!/(?:secret|token|password|raw|value)/.test(value) || [
      "command_center_live_light_credential_preflight_contract.v1",
      "factor_test_provider_small_pool_credential_presence.v1",
      "command_center_3_secret_artifact_allowlist_review_receipt.v1"
    ].includes(value));
  if (key === "scope_hash" || key === "scope_hash_short" || key.endsWith("_sha256") || key.endsWith("_digest")) {
    return SAFE_SENSITIVE_HASH_RE.test(value);
  }
  if (key === "presence_check_method" || key === "credential_presence_check_method") {
    return ["environment_key_membership_only", "environment_key_membership_only_no_value_read"].includes(value);
  }
  if (key === "credential_presence_check_route") return SAFE_SENSITIVE_ROUTE_RE.test(value);
  if (key === "safe_credential_label") return value === "tushare_server_token";
  if (key === "credential_presence_status") return value === "" || SAFE_SENSITIVE_STATUS_VALUES.has(value);
  if (key === "status" || key === "state" || key === "read_status" || key === "call_status") {
    return SAFE_SENSITIVE_STATUS_VALUES.has(value) ||
      (/^[a-z0-9_]+$/.test(value) && !/(?:secret|token|credential|password|raw|value)/.test(value));
  }
  if (key === "mode") return ["live_light", "cache_only"].includes(value);
  if (key === "allowed_provider_labels") return SAFE_SENSITIVE_PROVIDER_VALUES.has(value);
  if (key === "missing_evidence") return /^[a-z0-9 _/.-]+$/.test(value) && !/(?:token|password|api_key|credential_value)/.test(value);
  if (key === "current_branch") return /^[A-Za-z0-9._/-]{1,120}$/.test(value);
  if (key === "current_head" || key === "current_head_full") return /^(?:[0-9a-f]{7,40})$/.test(value);
  if (key === "head" || key === "head_full") return /^(?:[0-9a-f]{7,40})$/.test(value);
  if (key === "branch" || key === "current_branch") return /^[A-Za-z0-9._/-]{1,120}$/.test(value);
  if (key === "receipt_path") return /^(?:\.?[A-Za-z0-9_-]+\/)*[A-Za-z0-9_.-]+\.json$/.test(value);
  if (key === "scope") return value === "ignored_manual_secret_artifact_allowlist_review_no_cache_github_api";
  if (key === "api") return value === "local_secret_artifact_allowlist_review_receipt_readback";
  if (key === "source") return value === "ignored local secret/artifact allowlist review receipt";
  if (key === "local_fetched_at") return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value);
  if (key === "reviewed_at_utc") return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value);
  if (key === "receipt_writer") return /^scripts\/[a-z0-9_]+\.py$/.test(value);
  if (key === "reviewer") return /^[A-Za-z0-9 ._-]{1,120}$/.test(value);
  if (key === "manual_review_note_safe") return /^(?:Current-head|Same-head|reviewed)/.test(value) && value.length <= 400;
  if (key === "remote_artifact_digest") return /^sha256:[0-9a-f]{64}$/.test(value);
  if (key === "remote_run_id") return /^\d{1,32}$/.test(value);
  if (key === "decision") return /^[a-z0-9 _-]{1,160}$/.test(value) && !/(?:token|password|api_key|raw)/.test(value);
  if (key === "method" || key === "request_method") return ["GET", "POST"].includes(value);
  return false;
}
function safeNonSecretMetadata(key, value) {
  if (key === "authorization_nonce_digest") return typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
  if (key === "cost_ceiling_usd_per_million_tokens") {
    return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1_000_000;
  }
  if (key === "authorization_nonce_consumed_at") return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(value);
  if (key === "authorization_nonce_status") return ["issued", "not_issued", "consumed"].includes(value);
  if (key === "credential_presence_status") return typeof value === "string" && value.length <= 200 && (value === "" || SAFE_SENSITIVE_STATUS_VALUES.has(value));
  if (SAFE_NON_SECRET_NUMBER_KEYS.has(key)) return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1_000_000_000;
  if (SAFE_NON_SECRET_TEXT_KEYS.has(key)) {
    if (key === "safe_credential_label") return value === "tushare_server_token";
    if (key === "credential_presence_status") return typeof value === "string" && value.length <= 200 && (value === "" || SAFE_SENSITIVE_STATUS_VALUES.has(value));
    if (key === "credential_presence_check_method" || key === "server_secret_presence_check") {
      return ["environment_key_membership_only", "environment_key_membership_only_no_value_read"].includes(value);
    }
    if (key === "credential_presence_check_route") return typeof value === "string" && SAFE_SENSITIVE_ROUTE_RE.test(value);
    if (key === "credential_missing_status" || key === "secret_artifact_allowlist_review_receipt_status") return SAFE_SENSITIVE_STATUS_VALUES.has(value);
    return false;
  }
  if (SAFE_NON_SECRET_CONTAINER_KEYS.has(key)) return Boolean(value && typeof value === "object");
  return false;
}

function migrationSanitizedMetadataValid(key, value) {
  if (key === "authorization_nonce_digest") {
    return value === null || (typeof value === "string" && SAFE_SENSITIVE_HASH_RE.test(value));
  }
  if (["authorization_nonce_present", "authorization_nonce_consumed", "token_usage_complete", "token_budget_cost_evidence_complete"].includes(key)) {
    return value === null || typeof value === "boolean";
  }
  if (["total_tokens", "retry_tokens"].includes(key)) {
    return value === null || (Number.isSafeInteger(value) && value >= 0 && value <= 1_000_000_000);
  }
  if (key === "contains_secret") return value === null || value === false;
  if (MIGRATION_SAFE_SUMMARY_FIELDS.has(key)) return typeof value === "boolean";
  return false;
}

function migrationSafeFieldsValueValid(key, value) {
  if (MIGRATION_SAFE_FIELDS.has(key)) return migrationSanitizedMetadataValid(key, value);
  if (forbiddenSecretFieldKey(key)) return false;
  if (value === null || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value) && value >= 0 && value <= 1_000_000_000;
  if (typeof value === "string") return /^[A-Za-z0-9._:/ -]{1,200}$/.test(value);
  if (Array.isArray(value)) return value.length <= 64 && value.every(item => typeof item === "string" && /^[A-Za-z0-9._:/ -]{1,120}$/.test(item));
  return false;
}

// Remove only explicitly allowlisted sanitized metadata before the generic
// secret scan.  Invalid values remain in the scan and therefore fail closed.
function migrationStatusSecretScanValue(value) {
  let invalid = false;
  const clone = (node, path = [], inSafeFields = false) => {
    if (Array.isArray(node)) return node.map((child, index) => clone(child, path.concat(String(index)), inSafeFields));
    if (!node || typeof node !== "object") return node;
    const result = {};
    for (const [rawKey, child] of Object.entries(node)) {
      const key = canonicalSecretKey(rawKey);
      const safeField = inSafeFields;
      const safeSummary = path[0] === "data" && MIGRATION_SAFE_SUMMARY_FIELDS.has(key);
      if (safeField || safeSummary) {
        if (safeField) {
          if (!migrationSafeFieldsValueValid(key, child)) invalid = true;
          if (MIGRATION_SAFE_FIELDS.has(key)) continue;
        } else if (!migrationSanitizedMetadataValid(key, child)) invalid = true;
        if (safeSummary) continue;
      }
      if (key === "safe_fields" && (!child || typeof child !== "object" || Array.isArray(child))) invalid = true;
      result[rawKey] = clone(child, path.concat(key), key === "safe_fields");
    }
    return result;
  };
  return { value: clone(value), invalid };
}

function safeRecord(value) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function canonicalSecretKey(rawKey) {
  return rawKey
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1_$2")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function safeBooleanSecretPolicy(rawKey, value) {
  if (typeof value !== "boolean") return false;
  const key = canonicalSecretKey(rawKey);
  const policy = SAFE_BOOLEAN_SECRET_POLICIES.has(key)
    ? SAFE_BOOLEAN_SECRET_POLICIES
    : SAFE_BOOLEAN_METADATA_POLICIES;
  if (!policy.has(key)) return false;
  const expected = policy.get(key);
  return expected === null || value === expected;
}

function secretMaterialSuffix(value) {
  return SECRET_MATERIAL_SUFFIXES.has(value) ||
    /^sha\d*$/.test(value) || /^blake\d*$/.test(value) ||
    ["checksum", "hmac", "md5"].includes(value);
}

function forbiddenSecretFieldKey(rawKey) {
  const key = canonicalSecretKey(rawKey);
  for (const forbidden of FORBIDDEN_SECRET_KEYS) {
    if (key === forbidden || key.endsWith(`_${forbidden}`)) return true;
    const marker = `${forbidden}_`;
    let position = key.indexOf(marker);
    while (position >= 0) {
      const boundaryBefore = position === 0 || key[position - 1] === "_";
      const tailTokens = key.slice(position + marker.length).split("_");
      if (boundaryBefore && (
        STRICT_ANY_TAIL_FORBIDDEN.has(forbidden) ||
        STRICT_STATUS_TAIL_FORBIDDEN.has(tailTokens[0]) ||
        tailTokens.some(secretMaterialSuffix)
      )) return true;
      position = key.indexOf(marker, position + 1);
    }
  }
  return false;
}

function safeAuditReceiptContainer(value, row = false) {
  if (!value || typeof value !== "object") return false;
  if (Array.isArray(value)) {
    return row
      ? value.every(item => safeAuditReceiptContainer(item, true))
      : value.every(item => typeof item === "string" && SAFE_AUDIT_MISSING_EVIDENCE_VALUES.has(item));
  }
  const allowed = row ? SAFE_AUDIT_CALL_LEDGER_KEYS : SAFE_AUDIT_RECEIPT_KEYS;
  for (const [rawKey, child] of Object.entries(value)) {
    const key = canonicalSecretKey(rawKey);
    if (!allowed.has(key)) return false;
    if (key === "missing_evidence") {
      if (!safeAuditReceiptContainer(child, false)) return false;
      continue;
    }
    if (key === "call_ledger") {
      if (!safeAuditReceiptContainer(child, true)) return false;
      continue;
    }
    if (child && typeof child === "object") return false;
    if (!safeSensitivePrimitive(key, child) && !safeBooleanSecretPolicy(key, child) && !safeNonSecretMetadata(key, child)) return false;
  }
  return true;
}

function secretBearingFieldCount(value) {
  if (!value || typeof value !== "object") return 0;
  let count = 0;
  let scannedNodes = 0;
  const stack = [{ node: value, depth: 0, sensitiveContext: false, containerKey: "" }];
  while (stack.length) {
    const { node, depth, sensitiveContext, containerKey } = stack.pop();
    if (depth > MAX_SECRET_SCAN_DEPTH) return count + 1;
    for (const [rawKey, child] of Object.entries(node)) {
      scannedNodes += 1;
      if (scannedNodes > MAX_SECRET_SCAN_NODES) return count + 1;
      const key = canonicalSecretKey(rawKey);
      const forbiddenSecretKey = forbiddenSecretFieldKey(rawKey);
      const primitiveKey = sensitiveContext && /^\d+$/.test(rawKey) ? containerKey : key;
      if (sensitiveContext && child !== null && typeof child !== "object" && !safeSensitivePrimitive(primitiveKey, child)) count += 1;
      if (SAFE_NON_SECRET_AUDIT_CONTAINER_KEYS.has(key) && child && typeof child === "object") {
        if (!safeAuditReceiptContainer(child, key.endsWith("_missing_evidence") ? false : false)) count += 1;
        continue;
      }
      if (forbiddenSecretKey && !safeBooleanSecretPolicy(key, child) && !safeNonSecretMetadata(key, child) &&
        !(SAFE_NON_SECRET_CONTAINER_KEYS.has(key) && child && typeof child === "object")) count += 1;
      if (
        typeof child === "boolean" &&
        (key === "contains_secret" || key.endsWith("_contains_secret") || key.endsWith("_contain_secret") || key.endsWith("_includes_secret")) &&
        child === true &&
        !forbiddenSecretKey
      ) count += 1;
      if (typeof child === "string" && (/^\s*(bearer|basic)\s+\S+/i.test(child) || child.includes("-----BEGIN PRIVATE KEY-----"))) count += 1;
      if (child && typeof child === "object") {
        const childSensitive = sensitiveContext || SAFE_NON_SECRET_CONTAINER_KEYS.has(key);
        stack.push({ node: child, depth: depth + 1, sensitiveContext: childSensitive, containerKey: childSensitive ? key : "" });
      }
    }
  }
  return count;
}

function nonLocalUrlCount(value) {
  if (!value || typeof value !== "object") return 0;
  let count = 0;
  let scannedNodes = 0;
  const stack = [{ node: value, depth: 0 }];
  while (stack.length) {
    const { node, depth } = stack.pop();
    if (depth > MAX_SECRET_SCAN_DEPTH) return count + 1;
    for (const child of Object.values(node)) {
      scannedNodes += 1;
      if (scannedNodes > MAX_SECRET_SCAN_NODES) return count + 1;
      if (typeof child === "string" && /^https?:\/\//i.test(child)) {
        try {
          const parsed = new URL(child);
          if (!ALLOWED_LOCAL_HOSTS.has(parsed.hostname)) count += 1;
        } catch { count += 1; }
      } else if (child && typeof child === "object") {
        stack.push({ node: child, depth: depth + 1 });
      }
    }
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
  let scannedNodes = 0;
  const stack = [{ node: value, depth: 0, topLevel }];
  while (stack.length) {
    const { node, depth, topLevel: currentTopLevel } = stack.pop();
    if (depth > MAX_SECRET_SCAN_DEPTH) return count + 1;
    for (const [name, child] of Object.entries(node)) {
      scannedNodes += 1;
      if (scannedNodes > MAX_SECRET_SCAN_NODES) return count + 1;
      if (!currentTopLevel && HISTORICAL_FLAG_NAMES.has(name) && child === true) count += 1;
      if (child && typeof child === "object") stack.push({ node: child, depth: depth + 1, topLevel: false });
    }
  }
  return count;
}

function exactCacheMissingError(error, endpoint, packetKey) {
  const expectedRoute = endpoint.startsWith("/api/packets/")
    ? "GET /api/packets/{packet_key}"
    : `GET ${endpoint}`;
  return Boolean(safeRecord(error) && canonicalJson(Object.keys(error).sort()) === canonicalJson(["code", "details", "message"]) &&
    error.code === "cache_missing" && typeof error.message === "string" && error.message.length > 0 &&
    safeRecord(error.details) && canonicalJson(Object.keys(error.details).sort()) === canonicalJson(["cache_source", "packet_key", "route"]) &&
    error.details.cache_source === "cache_missing" && error.details.packet_key === packetKey &&
    error.details.route === expectedRoute);
}

function endpointDataIdentityValid(data, contract) {
  if (!safeRecord(data)) return false;
  if (contract.schema && data.schema_version !== contract.schema) return false;
  if (contract.packet && data.packet_key !== contract.packet) return false;
  return true;
}

function strictCurrentReadFlagsValid(record) {
  return Boolean(safeRecord(record) &&
    STRICT_CURRENT_LEDGER_FALSE_FLAGS.every(name =>
      Object.prototype.hasOwnProperty.call(record, name) && record[name] === false) &&
    CURRENT_TRUE_FLAGS.every(name =>
      Object.prototype.hasOwnProperty.call(record, name) && record[name] === true));
}

function strictCurrentReadLedgerRowValid(row, endpoint) {
  return Boolean(strictCurrentReadFlagsValid(row) &&
    row.source === `GET ${endpoint}` && row.route === `GET ${endpoint}` &&
    row.request_method === "GET" && Number.isInteger(row.row_count) && row.row_count >= 0 &&
    ((row.call_status === "cache_read") || (row.call_status === "cache_missing" && row.row_count === 0)));
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
    if (contract?.strictCurrentRead && !strictCurrentReadLedgerRowValid(row, endpoint)) sourcesAllowlisted = false;
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
    if (contract?.strictCurrentRead && !strictCurrentReadFlagsValid(data)) dataCurrentReadFlagsValid = false;
    if (contract?.strictCurrentRead && cacheMissing &&
      (data.status !== "cache_missing" || data.cache_source !== "cache_missing")) dataCurrentReadFlagsValid = false;
  }
  const strictLedgerStateValid = !contract?.strictCurrentRead || ledger.every(row =>
    safeRecord(row) && row.call_status === (cacheMissing ? "cache_missing" : "cache_read"));
  const migrationScan = endpoint === "/api/migration/status" ? migrationStatusSecretScanValue(value) : { value, invalid: false };
  const secretCount = migrationScan.invalid ? 1 : secretBearingFieldCount(migrationScan.value);
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
    data_status: typeof data.status === "string" ? data.status : "",
    data_cache_source: typeof data.cache_source === "string" ? data.cache_source : "",
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
    strict_current_read_contract: contract?.strictCurrentRead === true,
    strict_current_read_valid: Boolean(
      !contract?.strictCurrentRead || (dataCurrentReadFlagsValid && strictLedgerStateValid && ledgerResult.sourcesAllowlisted)
    ),
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
    dataCurrentReadFlagsValid && strictLedgerStateValid && secretCount === 0);
  return { valid, summary, digest: objectDigest(summary) };
}

function selfTestFastApiValidator() {
  const safeLedger = () => ({
    api: "local_call_ledger_audit_cache", external: false,
    external_calls_triggered: false, provider_or_model_calls: false,
    provider_called: false, model_called: false, tushare_called: false,
    deepseek_called: false, github_called: false, worker_called: false,
    trade_called: false, trading_called: false, broker_called: false,
    order_called: false, real_trading_enabled: false, contains_secret: false,
    does_not_execute_trades: true, does_not_modify_strategy_action: true
  });
  const safeAudit = () => ({
    ok: true,
    data: {
      schema_version: "call_ledger_audit_cache.v1",
      packet_key: "command_center_3_call_ledger_audit_cache",
      external: false, external_calls_triggered: false, provider_or_model_calls: false,
      provider_called: false, model_called: false, worker_called: false,
      tushare_called: false, deepseek_called: false, github_called: false,
      trade_called: false, trading_called: false, broker_called: false,
      order_called: false, real_trading_enabled: false, contains_secret: false,
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
  let attackCount = 0;
  const reject = (result, label) => {
    attackCount += 1;
    assert(!result.valid, label);
  };
  const safeResult = analyze(safeAudit());
  assert(FASTAPI_CACHE_CONTRACTS.size === FASTAPI_CACHE_ENDPOINT_COUNT, "exact_cache_endpoint_surface");
  assert(safeResult.valid, "safe_cache_response");
  assert(canonicalJson(safeResult.summary.ledger_contract_rows) === canonicalJson([{
    api: "local_call_ledger_audit_cache", source: "/api/audit/cache", method: "GET", path: "/api/audit/cache",
    external: false, provider: false, model: false, worker: false, trade: false, task_post: false, secret: false
  }]), "exact_normalized_ledger_contract");

  const extraTop = safeAudit();
  extraTop.malicious = true;
  reject(analyze(extraTop), "2xx_extra_top_level_json");
  const missingExternalProof = safeAudit();
  delete missingExternalProof.call_ledger[0].external;
  reject(analyze(missingExternalProof), "ledger_external_proof_missing");
  for (const [label, field] of [
    ["external_ledger", "external_calls_triggered"], ["provider_ledger", "tushare_called"],
    ["model_ledger", "deepseek_called"], ["worker_ledger", "worker_called"],
    ["trade_ledger", "trade_called"]
  ]) {
    const payload = safeAudit();
    payload.call_ledger[0][field] = true;
    reject(analyze(payload), label);
  }
  const taskPost = safeAudit();
  taskPost.call_ledger[0].request_method = "POST";
  reject(analyze(taskPost), "task_post_ledger");
  const externalUrl = safeAudit();
  externalUrl.call_ledger[0].endpoint = "https://example.invalid/api";
  reject(analyze(externalUrl), "non_local_ledger_source");
  const unrelatedApi = safeAudit();
  unrelatedApi.call_ledger[0].api = "local_task_status_index";
  reject(analyze(unrelatedApi), "endpoint_owned_api_required");
  const optionalNext = safeAudit();
  optionalNext.data.schema_version = "next_session_projection.v1";
  optionalNext.data.packet_key = "command_center_next_session_projection_packet";
  optionalNext.call_ledger = [{
    ...safeLedger(), api: "local_next_session_cache",
    source: "GET /api/next-session/cache", route: "GET /api/next-session/cache",
    request_method: "GET", row_count: 1, call_status: "cache_read"
  }];
  assert(analyze(optionalNext, "/api/next-session/cache").valid, "single_current_endpoint_ledger_row");
  const minimalPrimary = structuredClone(optionalNext);
  minimalPrimary.call_ledger[0] = { api: "local_next_session_cache", external: false, external_calls_triggered: false };
  reject(analyze(minimalPrimary, "/api/next-session/cache"), "minimal_primary_row_rejected");
  const wrongRoute = structuredClone(optionalNext);
  wrongRoute.call_ledger[0].route = "GET /api/worker/cache";
  reject(analyze(wrongRoute, "/api/next-session/cache"), "raw_route_binding_required");
  const missingWorkerProof = structuredClone(optionalNext);
  delete missingWorkerProof.call_ledger[0].worker_called;
  reject(analyze(missingWorkerProof, "/api/next-session/cache"), "explicit_worker_boundary_required");
  optionalNext.call_ledger.push({ ...safeLedger(), api: "local_next_session_production_stage_scope_manifest" });
  reject(analyze(optionalNext, "/api/next-session/cache"), "historical_row_forbidden_in_current_ledger");
  const missingEnvelope = structuredClone(optionalNext);
  missingEnvelope.call_ledger = [{
    ...safeLedger(), api: "local_next_session_cache",
    source: "GET /api/next-session/cache", route: "GET /api/next-session/cache",
    request_method: "GET", row_count: 0, call_status: "cache_missing"
  }];
  missingEnvelope.ok = false;
  missingEnvelope.error = {
    code: "cache_missing", message: "missing",
    details: { cache_source: "cache_missing", packet_key: "command_center_next_session_projection_packet", route: "GET /api/next-session/cache" }
  };
  missingEnvelope.data.status = "ready";
  missingEnvelope.data.cache_source = "cache_missing";
  reject(analyze(missingEnvelope, "/api/next-session/cache"), "missing_envelope_rejects_ready_data");
  const secret = safeAudit();
  secret.data.api_key = "dummy";
  reject(analyze(secret), "secret_field");
  const booleanSecretPolicy = safeAudit();
  booleanSecretPolicy.data.launcher_diagnostic_urls_contain_secret = false;
  booleanSecretPolicy.data.display_strips_query_hash_username_password = true;
  booleanSecretPolicy.data.launcher_prints_raw_query_hash_username_password = false;
  booleanSecretPolicy.data.live_full_requires_separate_authorization = true;
  assert(analyze(booleanSecretPolicy).valid, "boolean_secret_policy_disclosures_are_not_credentials");
  const unsafeContainsSecret = structuredClone(booleanSecretPolicy);
  unsafeContainsSecret.data.launcher_diagnostic_urls_contain_secret = true;
  reject(analyze(unsafeContainsSecret), "contains_secret_true_rejected");
  const unsafeDisplayStripping = structuredClone(booleanSecretPolicy);
  unsafeDisplayStripping.data.display_strips_query_hash_username_password = false;
  reject(analyze(unsafeDisplayStripping), "display_stripping_false_rejected");
  const unsafeApiKeyBoolean = structuredClone(booleanSecretPolicy);
  unsafeApiKeyBoolean.data.api_key = false;
  reject(analyze(unsafeApiKeyBoolean), "api_key_boolean_rejected");
  const unsafeAuthorizationBoolean = structuredClone(booleanSecretPolicy);
  unsafeAuthorizationBoolean.data.authorization = false;
  reject(analyze(unsafeAuthorizationBoolean), "authorization_boolean_rejected");
  const unsafeContainsSecretExact = structuredClone(booleanSecretPolicy);
  unsafeContainsSecretExact.data.contains_secret = true;
  reject(analyze(unsafeContainsSecretExact), "contains_secret_exact_true_rejected");
  const unsafeNestedCredential = structuredClone(booleanSecretPolicy);
  unsafeNestedCredential.data.api_key = { present: true };
  reject(analyze(unsafeNestedCredential), "nested_api_key_object_rejected");
  for (const [key, value, label] of [
    ["api_key_value", false, "api_key_boolean_material_wrapper_rejected"],
    ["authorization_header", false, "authorization_boolean_material_wrapper_rejected"],
    ["token_metadata", false, "token_boolean_material_wrapper_rejected"],
    ["private_key_pem", false, "private_key_boolean_material_wrapper_rejected"]
  ]) {
    const unsafeBooleanShape = structuredClone(booleanSecretPolicy);
    unsafeBooleanShape.data[key] = value;
    reject(analyze(unsafeBooleanShape), label);
  }
  const unsafeCompositeAuthorization = structuredClone(booleanSecretPolicy);
  unsafeCompositeAuthorization.data.api_key_requires_separate_authorization = false;
  reject(analyze(unsafeCompositeAuthorization), "composite_authorization_name_rejected");
  const unsafeUnreviewedDisclosure = structuredClone(booleanSecretPolicy);
  unsafeUnreviewedDisclosure.data.unreviewed_payload_contains_secret = false;
  reject(analyze(unsafeUnreviewedDisclosure), "unreviewed_secret_disclosure_rejected");
  for (const key of ["live_full_reserved_requires_separate_authorization", "requires_separate_live_provider_authorization"]) {
    const unsafeAuthorizationPolicy = structuredClone(booleanSecretPolicy);
    unsafeAuthorizationPolicy.data[key] = false;
    reject(analyze(unsafeAuthorizationPolicy), `${key}_false_rejected`);
  }
  for (const [key, value, label] of [
    ["apiKey", "dummy", "camel_case_api_key_rejected"],
    ["api.key", "dummy", "dotted_api_key_rejected"],
    ["api/key", "dummy", "slash_api_key_rejected"],
    ["api_key_value", "dummy", "api_key_value_rejected"],
    ["authorization_header", "dummy", "authorization_header_rejected"],
    ["token_metadata", { value: "dummy" }, "token_metadata_rejected"],
    ["credential.payload", "dummy", "credential_payload_rejected"],
    ["privateKey", "dummy", "camel_case_private_key_rejected"],
    ["private_key_pem", "dummy", "private_key_pem_rejected"],
    ["api_key_hash", "dummy", "api_key_hash_rejected"],
    ["token_digest", "dummy", "token_digest_rejected"],
    ["credential_fingerprint", "dummy", "credential_fingerprint_rejected"],
    ["api_key_env_name", "dummy", "api_key_env_name_rejected"],
    ["api_key_current_hash", "dummy", "api_key_current_hash_rejected"],
    ["api_key_runtime_value", "dummy", "api_key_runtime_value_rejected"],
    ["credential_current_payload", "dummy", "credential_current_payload_rejected"],
    ["authorization_safe_header", "dummy", "authorization_safe_header_rejected"],
    ["api_key_current", "dummy", "api_key_current_rejected"],
    ["authorization_current", "dummy", "authorization_current_rejected"],
    ["credentials_current", { value: "dummy" }, "credentials_current_rejected"],
    ["hash_api_key_current", "dummy", "hash_api_key_current_rejected"],
    ["token_current", "dummy", "token_current_rejected"],
    ["secret_current", "dummy", "secret_current_rejected"],
    ["credential_current", "dummy", "credential_current_rejected"],
    ["credentials", { value: "dummy" }, "plural_credentials_rejected"],
    ["access_tokens", ["dummy"], "plural_access_tokens_rejected"],
    ["token_sha512", "dummy", "token_sha512_rejected"],
    ["api_key_sha1", "dummy", "api_key_sha1_rejected"],
    ["credential_md5", "dummy", "credential_md5_rejected"],
    ["access_token_checksum", "dummy", "access_token_checksum_rejected"]
  ]) {
    const unsafeSecretShape = structuredClone(booleanSecretPolicy);
    unsafeSecretShape.data[key] = value;
    reject(analyze(unsafeSecretShape), label);
  }
  const validSanitizedMetadata = structuredClone(booleanSecretPolicy);
  validSanitizedMetadata.data.authorization_nonce_digest = "a".repeat(64);
  validSanitizedMetadata.data.authorization_nonce_caller_generated = true;
  validSanitizedMetadata.data.authorization_nonce_present = true;
  validSanitizedMetadata.data.authorization_nonce_raw_persisted = false;
  validSanitizedMetadata.data.authorization_nonce_required = true;
  validSanitizedMetadata.data.authorization_nonce_strong = true;
  validSanitizedMetadata.data.authorization_nonce_status = "issued";
  validSanitizedMetadata.data.authorization_nonce_consumed_at = "2026-07-16T12:34:56";
  validSanitizedMetadata.data.cost_ceiling_usd_per_million_tokens = 10;
  assert(analyze(validSanitizedMetadata).valid, "sanitized_metadata_shape_accepted");
  for (const [key, value, label] of [
    ["safe_credential_label", "opaque-secret", "safe_label_opaque_secret_rejected"],
    ["credential_presence_status", "opaque-secret", "presence_status_opaque_secret_rejected"],
    ["credential_presence_summary", { value: "opaque-secret" }, "summary_nested_opaque_secret_rejected"],
    ["credential_presence_summary", { value_length: 64 }, "summary_value_length_rejected"],
    ["credential_presence_summary", { raw_value: 123456 }, "summary_numeric_secret_rejected"],
    ["credential_presence_summary", { credential_available: true }, "summary_unknown_boolean_rejected"],
    ["credential_presence_summary", { values_exposed: true }, "summary_values_exposed_true_rejected"],
    ["credential_presence_summary", { external_calls_triggered: true }, "summary_external_true_rejected"],
    ["credential_presence_summary", { does_not_execute_trades: false }, "summary_trade_boundary_false_rejected"],
    ["provider_parity_credential_presence_rows", [{ value: "opaque-secret" }], "rows_nested_opaque_secret_rejected"],
    ["tokens_latest", "opaque-secret", "plural_tokens_tail_rejected"],
    ["secrets_previous", "opaque-secret", "plural_secrets_tail_rejected"]
  ]) {
    const unsafeSanitizedMetadata = structuredClone(validSanitizedMetadata);
    unsafeSanitizedMetadata.data[key] = value;
    reject(analyze(unsafeSanitizedMetadata), label);
  }
  for (const [key, value, label] of [
    ["authorization_nonce_digest", "dummy", "nonce_digest_raw_rejected"],
    ["authorization_nonce_digest", "a".repeat(63), "nonce_digest_short_rejected"],
    ["authorization_nonce_digest", { value: "dummy" }, "nonce_digest_object_rejected"],
    ["cost_ceiling_usd_per_million_tokens", "10", "cost_ceiling_string_rejected"],
    ["cost_ceiling_usd_per_million_tokens", { value: 10 }, "cost_ceiling_object_rejected"],
    ["cost_ceiling_usd_per_million_tokens", -1, "cost_ceiling_negative_rejected"],
    ["authorization_nonce_caller_generated", false, "nonce_caller_generated_false_rejected"],
    ["authorization_nonce_raw_persisted", true, "nonce_raw_persisted_true_rejected"],
    ["authorization_nonce_required", false, "nonce_required_false_rejected"],
    ["authorization_nonce_status", "raw_secret", "nonce_status_enum_rejected"],
    ["authorization_nonce_consumed_at", "12345678", "nonce_consumed_at_format_rejected"]
  ]) {
    const unsafeMetadata = structuredClone(booleanSecretPolicy);
    unsafeMetadata.data[key] = value;
    reject(analyze(unsafeMetadata), label);
  }
  const migration = structuredClone(booleanSecretPolicy);
  migration.data = {
    schema_version: "command_center_3_migration_status.v2",
    packet_key: "command_center_3_migration_status",
    status: "active_migration",
    safe_fields: {
      authorization_nonce_digest: null,
      authorization_nonce_present: null,
      authorization_nonce_consumed: null,
      total_tokens: null,
      retry_tokens: null,
      token_usage_complete: null,
      token_budget_cost_evidence_complete: null,
      contains_secret: null,
      selected_apis: ["trade_cal"],
      migration_status: "ready_cache_replay",
      numeric_budget: 0,
      historical_external_calls_triggered: true,
    },
    requires_token_cost_redaction_review: true,
  };
  migration.call_ledger = [{ ...safeLedger(), api: "local_migration_status_cache" }];
  assert(analyze(migration, "/api/migration/status").valid, "migration_sanitized_metadata_accepted");
  const migrationRequiresReview = structuredClone(migration);
  migrationRequiresReview.data.requires_token_cost_redaction_review = "true";
  reject(analyze(migrationRequiresReview, "/api/migration/status"), "migration_review_flag_type_rejected");
  const migrationRawDigest = structuredClone(migration);
  migrationRawDigest.data.safe_fields.authorization_nonce_digest = "opaque-secret";
  reject(analyze(migrationRawDigest, "/api/migration/status"), "migration_nonce_digest_raw_rejected");
  const migrationSecretField = structuredClone(migration);
  migrationSecretField.data.safe_fields.api_key = "opaque-secret";
  reject(analyze(migrationSecretField, "/api/migration/status"), "migration_nested_secret_rejected");
  const migrationContainsSecret = structuredClone(migration);
  migrationContainsSecret.data.safe_fields.contains_secret = true;
  reject(analyze(migrationContainsSecret, "/api/migration/status"), "migration_contains_secret_true_rejected");
  const migrationToken = structuredClone(migration);
  migrationToken.data.safe_fields.token = "opaque-secret";
  reject(analyze(migrationToken, "/api/migration/status"), "migration_unknown_token_rejected");
  const migrationArrayShape = structuredClone(migration);
  migrationArrayShape.data.safe_fields.selected_apis = [123];
  reject(analyze(migrationArrayShape, "/api/migration/status"), "migration_array_shape_rejected");
  const migrationCurrentFlag = structuredClone(migration);
  migrationCurrentFlag.data.external_calls_triggered = true;
  reject(analyze(migrationCurrentFlag, "/api/migration/status"), "migration_current_external_flag_rejected");
  const tooDeep = safeAudit();
  let nested = tooDeep.data;
  for (let depth = 0; depth <= MAX_SECRET_SCAN_DEPTH; depth += 1) {
    nested.safe_metadata = {};
    nested = nested.safe_metadata;
  }
  reject(analyze(tooDeep), "secret_scan_depth_limit_fail_closed");
  reject(analyze(safeAudit(), "/api/not-allowlisted/cache"), "unknown_endpoint");

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
  reject(analyze(taskHistory, "/api/tasks"), "task_history_current_get_attack");

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
  return { status: "motion_fastapi_validator_self_test_passed", attack_count: attackCount, external_calls_triggered: false };
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
      const warmupCoveredPaths = new Set(
        warmupRequestLedger
          .filter(entry => (
            entry.viewport === viewport.name &&
            entry.event_type === "response" &&
            entry.purpose === "vite_preview_dist_resource" &&
            entry.body_matches_dist === true &&
            entry.body_schema_valid === true
          ))
          .map(entry => entry.dist_path)
      );
      const manifestPaths = currentDistManifest.entry_graph.filter(path => !warmupCoveredPaths.has(path));
      activeSession = createSession("manifest", "#manifest", manifestRequestLedger);
      await page.evaluate(async paths => {
        for (const path of paths) {
          const url = path === "index.html" ? "/" : `/${path}`;
          const response = await fetch(url, { method: "GET", cache: "no-store", credentials: "omit" });
          if (!response.ok) throw new Error(`manifest_fetch_failed:${url}:${response.status}`);
          await response.arrayBuffer();
        }
      }, manifestPaths);
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
