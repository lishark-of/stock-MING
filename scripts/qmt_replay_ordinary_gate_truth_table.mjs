import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const desktopRequire = createRequire(new URL("../desktop/package.json", import.meta.url));
const ts = desktopRequire("typescript");
const sourceUrl = new URL("../desktop/src/routes/qmtReplayOrdinaryGate.ts", import.meta.url);
const source = await readFile(sourceUrl, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020 },
  fileName: sourceUrl.pathname,
}).outputText;
const moduleUrl = `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`;
const { evaluateQmtReplayOrdinaryGate } = await import(moduleUrl);

const scope = "a".repeat(64);
const commonSafe = (api, callStatus = "verified", rowCount = 0) => ({
  api,
  call_status: callStatus,
  row_count: rowCount,
  external: false,
  external_calls_triggered: false,
  external_call_count: 0,
  tushare_called: false,
  deepseek_called: false,
  github_called: false,
  provider_or_model_calls: false,
  provider_called: false,
  model_called: false,
  worker_called: false,
  worker_dispatched: false,
  qmt_called: false,
  qmt_connection_count: 0,
  qmt_external_connection_attempted: false,
  qmt_process_discovered: false,
  qmt_client_imported: false,
  xtquant_imported: false,
  trade_called: false,
  trading_called: false,
  broker_called: false,
  broker_session_opened: false,
  broker_session_count: 0,
  account_query_executed: false,
  order_called: false,
  real_order_submitted: false,
  real_order_count: 0,
  real_order_cancelled: false,
  real_trade_executed: false,
  real_trade_count: 0,
  real_holdings_modified: false,
  real_trading_enabled: false,
  contains_secret: false,
  does_not_execute_trades: true,
  does_not_modify_strategy_action: true,
  does_not_modify_holdings: true,
});
const frontend = (endpoint) => ({
  ...commonSafe("frontend_fastapi_request", "frontend_backend_auto_link_success"),
  endpoint,
  frontend_backend_auto_link_success: true,
  frontend_backend_auto_link_scope: "local_fastapi_only",
  page_render_external_calls: false,
});
const envelopeLedger = (endpoint, api, callStatus) => [
  frontend(endpoint),
  commonSafe(api, callStatus),
];
const boundary = () => ({
  ...commonSafe("local_qmt_readonly_decimal_replay"),
  external_call_count: 0,
  qmt_connection_count: 0,
  qmt_external_connection_attempted: false,
  qmt_process_discovered: false,
  qmt_client_imported: false,
  xtquant_imported: false,
  broker_session_opened: false,
  broker_session_count: 0,
  real_order_count: 0,
  real_order_cancelled: false,
  real_trade_count: 0,
  real_holdings_modified: false,
  real_trading_enabled: false,
  contains_secret: false,
  does_not_modify_holdings: true,
});
const lineage = () => ({
  schema_version: "candidate_radar_v05_next_session_lineage.v1",
  status: "same_packet_lineage_ready",
  candidate_packet_key: "command_center_3_candidate_radar_cache",
  symbol: "000001.SZ",
  candidate_task_id: "local-task-123",
  candidate_result_version: "candidate-v05-abc123",
  candidate_scope_hash: scope,
  data_date: "2026-07-16",
  freshness_state: {
    state: "fresh",
    freshness_state: "fresh",
    data_date: "2026-07-16",
    expected_trade_date: "2026-07-16",
    expected_trade_date_calendar_validated: true,
    calendar_validated: true,
  },
  research_only: true,
  no_buy: true,
  no_action: true,
  no_trade: true,
  external_calls_triggered: false,
  tushare_called: false,
  deepseek_called: false,
  github_called: false,
  does_not_modify_strategy_action: true,
  does_not_modify_operation_zones: true,
  contains_secret: false,
});
const makeInput = () => ({
  loading: false,
  error: "",
  candidate: {
    packet_key: "command_center_3_candidate_radar_cache",
    schema_version: "candidate_radar_cache.v1",
    status: "candidate_radar_v05_local_batch_ready",
    mode: "v05_candidate_local_batch",
    cache_only: true,
    read_only: true,
    warnings: [],
    candidate_radar_v05_next_session_lineage: lineage(),
  },
  candidateWarnings: [],
  candidateLedger: envelopeLedger(
    "/api/candidate-radar/cache",
    "local_candidate_radar_cache",
    "cache_read_persisted_v05_candidate_local_batch",
  ),
  nextSession: {
    packet_key: "command_center_next_session_projection_packet",
    schema_version: "next_session_projection.v1",
    status: "ready_cache_replay",
    mode: "cache_only",
    cache_only: true,
    read_only: true,
    warnings: [],
    candidate_radar_v05_lineage: lineage(),
  },
  nextWarnings: [],
  nextLedger: envelopeLedger("/api/next-session/cache", "local_next_session_cache", "cache_read"),
  qmt: {
    packet_key: "command_center_3_qmt_replay_cache",
    schema_version: "qmt_readonly_local_replay_cache.v1",
    status: "cache_missing",
    mode: "cache_only",
    cache_only: true,
    read_only: true,
    warnings: [],
    safety_boundary: boundary(),
    call_ledger: [boundary()],
    source_lineage: {},
    result_integrity_validated: false,
    result_integrity_status: "result_packet_missing",
    lineage_validation: {
      schema_version: "qmt_readonly_source_lineage_validation.v1",
      status: "waiting_for_first_result",
      passed: false,
    },
  },
  qmtWarnings: [],
  qmtLedger: envelopeLedger(
    "/api/qmt-replay/cache",
    "local_qmt_readonly_decimal_replay",
    "cache_read_no_external_call",
  ),
});
const makeReadyResult = (input) => {
  input.qmt.status = "ready_cache_replay";
  input.qmt.source_lineage = {
    source_symbol: "000001.SZ",
    source_task_id: "local-task-123",
    source_result_version: "candidate-v05-abc123",
    source_scope_hash: scope,
    source_data_date: "20260716",
  };
  input.qmt.result_integrity_validated = true;
  input.qmt.result_integrity_status = "result_integrity_validated";
  input.qmt.lineage_validation = {
    schema_version: "qmt_readonly_source_lineage_validation.v1",
    status: "source_result_integrity_validated",
    passed: true,
  };
};

const rows = [
  ["valid_first_launch", "launchReady", true, () => {}],
  ["valid_bound_result", "resultReady", true, makeReadyResult],
  ["valid_candidate_optional_allowlisted_ledgers", "launchReady", true, (v) => {
    v.candidateLedger.push(commonSafe(
      "local_candidate_radar_worker_execution_recipe",
      "candidate_radar_worker_execution_recipe_ready_production_pending",
      13,
    ));
  }],
  ["loading", "launchReady", false, (v) => { v.loading = true; }],
  ["read_error", "launchReady", false, (v) => { v.error = "offline"; }],
  ["candidate_warning", "launchReady", false, (v) => { v.candidateWarnings = ["warning"]; }],
  ["next_warning", "launchReady", false, (v) => { v.nextWarnings = ["warning"]; }],
  ["qmt_warning", "launchReady", false, (v) => { v.qmtWarnings = ["warning"]; }],
  ["candidate_packet_warning", "launchReady", false, (v) => { v.candidate.warnings = ["warning"]; }],
  ["next_packet_warning", "launchReady", false, (v) => { v.nextSession.warnings = ["warning"]; }],
  ["qmt_packet_warning", "launchReady", false, (v) => { v.qmt.warnings = ["warning"]; }],
  ["candidate_ledger_missing", "launchReady", false, (v) => { v.candidateLedger = []; }],
  ["next_ledger_missing", "launchReady", false, (v) => { v.nextLedger = []; }],
  ["qmt_envelope_ledger_missing", "launchReady", false, (v) => { v.qmtLedger = []; }],
  ["qmt_payload_ledger_missing", "launchReady", false, (v) => { v.qmt.call_ledger = []; }],
  ["frontend_ledger_duplicate", "launchReady", false, (v) => { v.candidateLedger.push(frontend("/api/candidate-radar/cache")); }],
  ["ledger_provider_call", "launchReady", false, (v) => { v.nextLedger[1].provider_called = true; }],
  ["candidate_status_missing", "launchReady", false, (v) => { delete v.candidate.status; }],
  ["next_status_failed", "launchReady", false, (v) => { v.nextSession.status = "failed"; }],
  ["lineage_status_missing", "launchReady", false, (v) => { delete v.candidate.candidate_radar_v05_next_session_lineage.status; }],
  ["lineage_symbol_mismatch", "launchReady", false, (v) => { v.nextSession.candidate_radar_v05_lineage.symbol = "600000.SH"; }],
  ["lineage_task_number", "launchReady", false, (v) => { v.nextSession.candidate_radar_v05_lineage.candidate_task_id = 123; }],
  ["lineage_scope_short", "launchReady", false, (v) => { v.candidate.candidate_radar_v05_next_session_lineage.candidate_scope_hash = "abc"; }],
  ["invalid_calendar_date", "launchReady", false, (v) => { const l = v.candidate.candidate_radar_v05_next_session_lineage; l.data_date = "2026-02-30"; l.freshness_state.data_date = "2026-02-30"; l.freshness_state.expected_trade_date = "2026-02-30"; }],
  ["embedded_date_junk", "launchReady", false, (v) => { v.candidate.candidate_radar_v05_next_session_lineage.data_date = "x20260716"; }],
  ["authoritative_calendar_missing", "launchReady", false, (v) => { delete v.nextSession.candidate_radar_v05_lineage.freshness_state.expected_trade_date_calendar_validated; }],
  ["generic_calendar_conflict", "launchReady", false, (v) => { v.nextSession.candidate_radar_v05_lineage.freshness_state.calendar_validated = false; }],
  ["next_freshness_stale", "launchReady", false, (v) => { v.nextSession.candidate_radar_v05_lineage.freshness_state.state = "stale"; v.nextSession.candidate_radar_v05_lineage.freshness_state.freshness_state = "stale"; }],
  ["qmt_status_degraded", "launchReady", false, (v) => { v.qmt.status = "degraded_last_good_replay"; }],
  ["qmt_mode_wrong", "launchReady", false, (v) => { v.qmt.mode = "local_research_replay"; }],
  ["qmt_boundary_field_missing", "launchReady", false, (v) => { delete v.qmt.safety_boundary.qmt_called; }],
  ["qmt_boundary_provider_call", "launchReady", false, (v) => { v.qmt.safety_boundary.provider_called = true; }],
  ["qmt_boundary_trade", "launchReady", false, (v) => { v.qmt.safety_boundary.real_trade_executed = true; }],
  ["qmt_payload_cross_object_mix", "launchReady", false, (v) => { delete v.qmt.call_ledger[0].model_called; v.qmt.safety_boundary.model_called = false; }],
  ["ready_result_integrity_missing", "resultReady", false, (v) => { makeReadyResult(v); delete v.qmt.result_integrity_validated; }],
  ["ready_result_source_date_mismatch", "resultReady", false, (v) => { makeReadyResult(v); v.qmt.source_lineage.source_data_date = "20260715"; }],
  ["ready_result_source_scope_mismatch", "resultReady", false, (v) => { makeReadyResult(v); v.qmt.source_lineage.source_scope_hash = "b".repeat(64); }],
  ["ready_result_lineage_pass_missing", "resultReady", false, (v) => { makeReadyResult(v); delete v.qmt.lineage_validation.passed; }],
];

for (const field of [
  "external",
  "external_calls_triggered",
  "tushare_called",
  "deepseek_called",
  "github_called",
  "provider_called",
  "model_called",
  "provider_or_model_calls",
  "worker_called",
  "worker_dispatched",
  "qmt_called",
  "qmt_external_connection_attempted",
  "qmt_process_discovered",
  "qmt_client_imported",
  "xtquant_imported",
  "trade_called",
  "trading_called",
  "broker_called",
  "broker_session_opened",
  "account_query_executed",
  "order_called",
  "real_order_submitted",
  "real_order_cancelled",
  "real_trade_executed",
  "real_holdings_modified",
  "real_trading_enabled",
  "contains_secret",
]) {
  rows.push([`candidate_ledger_${field}_true`, "launchReady", false, (v) => { v.candidateLedger[1][field] = true; }]);
}
for (const field of [
  "external_call_count",
  "qmt_connection_count",
  "broker_session_count",
  "real_order_count",
  "real_trade_count",
]) {
  rows.push([`candidate_ledger_${field}_nonzero`, "launchReady", false, (v) => { v.candidateLedger[1][field] = 1; }]);
}
for (const field of [
  "does_not_execute_trades",
  "does_not_modify_strategy_action",
  "does_not_modify_holdings",
]) {
  rows.push([`candidate_ledger_${field}_false`, "launchReady", false, (v) => { v.candidateLedger[1][field] = false; }]);
}
rows.push(
  ["candidate_next_ledger_swap", "launchReady", false, (v) => { v.candidateLedger = v.nextLedger; }],
  ["next_qmt_ledger_swap", "launchReady", false, (v) => { v.nextLedger = v.qmtLedger; }],
  ["qmt_candidate_ledger_swap", "launchReady", false, (v) => { v.qmtLedger = v.candidateLedger; }],
  ["candidate_backend_status_wrong", "launchReady", false, (v) => { v.candidateLedger[1].call_status = "cache_read"; }],
  ["candidate_backend_unknown", "launchReady", false, (v) => { v.candidateLedger.push(commonSafe("local_unknown_candidate_cache", "cache_read", 1)); }],
  ["candidate_backend_duplicate", "launchReady", false, (v) => { v.candidateLedger.push({ ...v.candidateLedger[1] }); }],
  ["qmt_frontend_endpoint_wrong", "launchReady", false, (v) => { v.qmtLedger[0].endpoint = "/api/candidate-radar/cache"; }],
);

const results = rows.map(([name, field, expected, mutate]) => {
  const input = makeInput();
  mutate(input);
  const result = evaluateQmtReplayOrdinaryGate(input);
  if (result[field] !== expected) {
    throw new Error(`${name}: expected ${field}=${expected}, got ${result[field]} (${result.reasonKey})`);
  }
  return { name, field, expected, actual: result[field], reason_key: result.reasonKey };
});

process.stdout.write(JSON.stringify({
  status: "passed",
  module: pathToFileURL(sourceUrl.pathname).href,
  row_count: results.length,
  passed_count: results.length,
  results,
}, null, 2));
