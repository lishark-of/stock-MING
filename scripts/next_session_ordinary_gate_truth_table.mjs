import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const desktopRequire = createRequire(new URL("../desktop/package.json", import.meta.url));
const ts = desktopRequire("typescript");
const sourceUrl = new URL("../desktop/src/routes/nextSessionOrdinaryGate.ts", import.meta.url);
const source = await readFile(sourceUrl, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020 },
  fileName: sourceUrl.pathname,
}).outputText;
const moduleUrl = `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`;
const { evaluateNextSessionOrdinaryGate } = await import(moduleUrl);

const scope = "a".repeat(64);
const makeInput = () => ({
  loading: false,
  error: "",
  cacheEnvelopeWarnings: [],
  taskEnvelopeWarnings: [],
  confirmedSymbol: "000001.SZ",
  packet: {
    packet_key: "command_center_next_session_projection_packet",
    schema_version: "next_session_projection.v1",
    status: "ready_cache_replay",
    cache_only: true,
    read_only: true,
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    provider_or_model_calls: false,
    does_not_execute_trades: true,
    does_not_modify_action: true,
    does_not_modify_strategy_action: true,
    does_not_modify_operation_zones: true,
    contains_secret: false,
    warnings: [],
    ordinary_result_replay_summary: { status: "ready_cache_replay" },
  },
  lineage: {
    status: "same_packet_lineage_ready",
    candidate_task_id: "local-abc123",
    candidate_scope_hash: scope,
    candidate_result_version: "candidate-v05-0123456789abcdef",
    symbol: "000001.SZ",
    data_date: "2026-07-16",
    freshness_state: {
      state: "fresh",
      freshness_state: "fresh",
      data_date: "2026-07-16",
      expected_trade_date: "2026-07-16",
      expected_trade_date_calendar_validated: true,
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
  },
  chartPayload: {
    status: "ready",
    source_packet: "command_center_next_session_projection_packet",
    symbol: "000001.SZ",
    source_task_id: "local-abc123",
    result_version: "candidate-v05-0123456789abcdef",
    candidate_scope_hash: scope,
    data_date: "2026-07-16",
    candidate_radar_v05_lineage_status: "same_packet_lineage_ready",
    is_exact_next_session_packet: true,
    uses_real_daily_close: true,
    warnings: [],
    chart_maturity: { status: "ready" },
    interaction_readiness_audit: { status: "interaction_ready" },
    chart_contract: {
      contract_key: "next_session_echarts_payload",
      schema_version: "next_session_echarts_payload.v1",
      renderer: "ECharts",
      source_packet: "command_center_next_session_projection_packet",
      cache_only: true,
      external_calls_triggered: false,
      tushare_called: false,
      deepseek_called: false,
      github_called: false,
      does_not_execute_trades: true,
      frontend_computes_trade_action: false,
      does_not_modify_action: true,
      does_not_modify_operation_zones: true,
      requires_button_task_for_refresh: true,
    },
  },
  chartSummary: {
    status: "ready",
    symbol: "000001.SZ",
    renderer: "ECharts",
    source_packet: "command_center_next_session_projection_packet",
    is_exact_next_session_packet: true,
    uses_real_daily_close: true,
    has_drawable_data: true,
    frontend_computes_trade_action: false,
    does_not_modify_action: true,
    does_not_modify_operation_zones: true,
    cache_only: true,
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    maturity_status: "ready",
  },
  taskIndex: {
    packet_key: "command_center_3_task_status_index",
    schema_version: "command_center_3_task_status_index.v1",
    mode: "cache_only",
    status: "ready",
    latest_confirmed_task_id: "local-abc123",
    latest_confirmed_symbol: "000001.SZ",
    latest_confirmed_task_status: "success",
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    readback_external_calls_triggered: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    warnings: [],
    policy: {
      get_tasks_cache_only: true,
      does_not_create_tasks: true,
      does_not_call_external_sources: true,
      latest_confirmed_readback_calls_external_sources: false,
      latest_confirmed_readback_creates_task: false,
      does_not_execute_trades: true,
      does_not_modify_strategy_action: true,
      contains_secret: false,
    },
  },
  durableEvidence: {
    schema_version: "next_session_durable_evidence_recipe.v1",
    status: "next_session_durable_evidence_recipe_ready_production_pending",
    provider_execution_implemented: false,
    model_execution_implemented: false,
    worker_execution_implemented: false,
  },
});

const rows = [
  ["valid_same_packet", true, () => {}],
  ["validated_is_not_fresh", false, (v) => { v.lineage.freshness_state.state = "validated"; v.lineage.freshness_state.freshness_state = "validated"; }],
  ["generic_calendar_conflict", false, (v) => { v.lineage.freshness_state.calendar_validated = false; }],
  ["authoritative_calendar_missing", false, (v) => { delete v.lineage.freshness_state.expected_trade_date_calendar_validated; }],
  ["invalid_calendar_date", false, (v) => { v.lineage.data_date = "2026-02-30"; v.lineage.freshness_state.data_date = "2026-02-30"; v.lineage.freshness_state.expected_trade_date = "2026-02-30"; v.chartPayload.data_date = "2026-02-30"; }],
  ["boolean_task_rejected", false, (v) => { v.lineage.candidate_task_id = true; v.chartPayload.source_task_id = true; }],
  ["number_result_rejected", false, (v) => { v.lineage.candidate_result_version = 123; v.chartPayload.result_version = 123; }],
  ["malformed_scope_rejected", false, (v) => { v.lineage.candidate_scope_hash = "scope"; v.chartPayload.candidate_scope_hash = "scope"; }],
  ["malformed_symbol_rejected", false, (v) => { v.lineage.symbol = "000001"; v.confirmedSymbol = "000001"; v.chartPayload.symbol = "000001"; v.chartSummary.symbol = "000001"; }],
  ["payload_symbol_missing", false, (v) => { delete v.chartPayload.symbol; }],
  ["summary_symbol_mismatch", false, (v) => { v.chartSummary.symbol = "600000.SH"; }],
  ["cache_envelope_warning", false, (v) => { v.cacheEnvelopeWarnings = ["warning"]; }],
  ["task_envelope_warning", false, (v) => { v.taskEnvelopeWarnings = ["warning"]; }],
  ["packet_warning", false, (v) => { v.packet.warnings = ["warning"]; }],
  ["chart_warning", false, (v) => { v.chartPayload.warnings = ["warning"]; }],
  ["packet_degraded", false, (v) => { v.packet.status = "cache_degraded"; }],
  ["packet_status_missing", false, (v) => { delete v.packet.status; }],
  ["chart_blocked", false, (v) => { v.chartPayload.status = "blocked"; }],
  ["summary_status_missing", false, (v) => { delete v.chartSummary.status; }],
  ["lineage_status_missing", false, (v) => { delete v.lineage.status; }],
  ["task_status_missing", false, (v) => { delete v.taskIndex.status; }],
  ["durable_status_missing", false, (v) => { delete v.durableEvidence.status; }],
  ["freshness_unknown", false, (v) => { v.lineage.freshness_state.state = "unknown"; v.lineage.freshness_state.freshness_state = "unknown"; }],
  ["loading", false, (v) => { v.loading = true; }],
  ["read_error", false, (v) => { v.error = "offline"; }],
  ["packet_boundary_missing", false, (v) => { delete v.packet.does_not_modify_action; }],
  ["chart_renderer_wrong", false, (v) => { v.chartPayload.chart_contract.renderer = "svg"; }],
  ["refresh_contract_missing", false, (v) => { delete v.chartPayload.chart_contract.requires_button_task_for_refresh; }],
  ["provider_execution_true", false, (v) => { v.durableEvidence.provider_execution_implemented = true; }],
  ["model_execution_true", false, (v) => { v.durableEvidence.model_execution_implemented = true; }],
  ["worker_execution_true", false, (v) => { v.durableEvidence.worker_execution_implemented = true; }],
];

const results = rows.map(([name, expected, mutate]) => {
  const input = makeInput();
  mutate(input);
  const result = evaluateNextSessionOrdinaryGate(input);
  if (result.ready !== expected) {
    throw new Error(`${name}: expected ready=${expected}, received ${result.ready} (${result.reasonKey})`);
  }
  return { name, expected, ready: result.ready, reason_key: result.reasonKey };
});

process.stdout.write(JSON.stringify({
  status: "passed",
  module: pathToFileURL(sourceUrl.pathname).href,
  row_count: results.length,
  passed_count: results.length,
  results,
}, null, 2));
