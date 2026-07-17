export type QmtGateRecord = Record<string, unknown>;

export type QmtReplayGateInput = {
  loading: boolean;
  error: string;
  candidate: QmtGateRecord;
  candidateWarnings: unknown;
  candidateLedger: unknown;
  nextSession: QmtGateRecord;
  nextWarnings: unknown;
  nextLedger: unknown;
  qmt: QmtGateRecord;
  qmtWarnings: unknown;
  qmtLedger: unknown;
};

export type QmtReplayGateResult = {
  launchReady: boolean;
  resultReady: boolean;
  reasonKey: string;
  symbol: string;
  taskId: string;
  resultVersion: string;
  scopeHash: string;
  dataDate: string;
  qmtStatus: string;
  lineageReady: boolean;
  safetyReady: boolean;
  ledgersReady: boolean;
  warningsReady: boolean;
};

const SYMBOL = /^\d{6}\.(?:SH|SZ|BJ)$/;
const ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$/;
const SCOPE = /^[0-9a-f]{64}$/;
const FRESH = new Set(["fresh", "current", "today"]);
const QMT_FALSE_FIELDS = [
  "external_calls_triggered",
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
  "tushare_called",
  "deepseek_called",
  "github_called",
  "provider_called",
  "model_called",
  "provider_or_model_calls",
  "worker_called",
  "worker_dispatched",
  "contains_secret",
] as const;
const QMT_ZERO_FIELDS = [
  "external_call_count",
  "qmt_connection_count",
  "broker_session_count",
  "real_order_count",
  "real_trade_count",
] as const;
const QMT_TRUE_FIELDS = [
  "does_not_execute_trades",
  "does_not_modify_strategy_action",
  "does_not_modify_holdings",
] as const;
const CANDIDATE_GET_LEDGER_APIS = [
  "local_candidate_radar_cache",
  "local_candidate_radar_legacy_parity_acceptance_receipt",
  "local_candidate_radar_production_activation_receipt",
  "local_candidate_radar_quant_projection_execution_request",
  "local_candidate_radar_provider_parity_execution_request",
  "local_candidate_radar_worker_execution_recipe",
  "local_candidate_radar_worker_execution_request",
  "local_candidate_radar_full_pool_worker_fallback_preview",
  "local_candidate_radar_deep_scan_worker_fallback_preview",
  "local_candidate_radar_worker_runtime_linked_evidence",
  "local_candidate_radar_next_execution_recipe",
  "local_candidate_radar_durable_evidence_recipe",
  "local_candidate_radar_production_replacement_review_preview",
  "local_candidate_radar_production_promotion_dry_run_preview",
  "local_candidate_radar_legacy_retirement_review_preview",
  "local_candidate_radar_production_promotion_review_preview",
  "local_candidate_radar_production_stage_scope_manifest",
] as const;

function record(value: unknown): QmtGateRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as QmtGateRecord
    : {};
}

function text(value: unknown, pattern: RegExp): string {
  if (typeof value !== "string") return "";
  const normalized = value.trim();
  return pattern.test(normalized) ? normalized : "";
}

export function strictQmtSymbol(value: unknown): string {
  if (typeof value !== "string") return "";
  const normalized = value.trim().toUpperCase();
  return SYMBOL.test(normalized) ? normalized : "";
}

export function strictQmtId(value: unknown): string {
  return text(value, ID);
}

export function strictQmtScope(value: unknown): string {
  return text(value, SCOPE);
}

export function strictQmtDate(value: unknown): string {
  if (typeof value !== "string") return "";
  const match = value.trim().match(/^(\d{4})-?(\d{2})-?(\d{2})$/);
  if (!match) return "";
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) return "";
  return `${match[1]}${match[2]}${match[3]}`;
}

function exactFreshness(value: unknown, expectedDataDate: string): boolean {
  const freshness = record(value);
  const state = typeof freshness.state === "string" ? freshness.state.trim().toLowerCase() : "";
  const genericState = typeof freshness.freshness_state === "string"
    ? freshness.freshness_state.trim().toLowerCase()
    : "";
  const genericCalendar = freshness.calendar_validated;
  const dataDate = strictQmtDate(freshness.data_date);
  const expectedTradeDate = strictQmtDate(freshness.expected_trade_date);
  return FRESH.has(state) &&
    genericState === state &&
    freshness.expected_trade_date_calendar_validated === true &&
    (genericCalendar === undefined || genericCalendar === true) &&
    Boolean(expectedDataDate) &&
    dataDate === expectedDataDate &&
    expectedTradeDate === expectedDataDate;
}

function exactSourceLineage(packet: QmtGateRecord, key: string) {
  const lineage = record(packet[key]);
  const dataDate = strictQmtDate(lineage.data_date);
  const ready = lineage.schema_version === "candidate_radar_v05_next_session_lineage.v1" &&
    lineage.status === "same_packet_lineage_ready" &&
    lineage.candidate_packet_key === "command_center_3_candidate_radar_cache" &&
    lineage.research_only === true &&
    lineage.no_buy === true &&
    lineage.no_action === true &&
    lineage.no_trade === true &&
    lineage.external_calls_triggered === false &&
    lineage.tushare_called === false &&
    lineage.deepseek_called === false &&
    lineage.github_called === false &&
    lineage.does_not_modify_strategy_action === true &&
    lineage.does_not_modify_operation_zones === true &&
    lineage.contains_secret === false &&
    exactFreshness(lineage.freshness_state, dataDate);
  return {
    ready,
    symbol: strictQmtSymbol(lineage.symbol),
    taskId: strictQmtId(lineage.candidate_task_id),
    resultVersion: strictQmtId(lineage.candidate_result_version),
    scopeHash: strictQmtScope(lineage.candidate_scope_hash),
    dataDate,
  };
}

function warningsEmpty(value: unknown): boolean {
  return Array.isArray(value) && value.length === 0;
}

function commonLedgerRowSafe(row: QmtGateRecord): boolean {
  return row.external === false &&
    QMT_FALSE_FIELDS.every((field) => row[field] === false) &&
    QMT_ZERO_FIELDS.every((field) => row[field] === 0) &&
    QMT_TRUE_FIELDS.every((field) => row[field] === true);
}

function envelopeLedgerSafe(
  value: unknown,
  spec: {
    endpoint: string;
    backendApi: string;
    backendCallStatus: string;
    allowedBackendApis: readonly string[];
  },
): boolean {
  if (!Array.isArray(value) || value.length < 2) return false;
  const rows = value.map(record);
  const frontend = rows.filter((row) => row.api === "frontend_fastapi_request");
  const backendRows = rows.filter((row) => row.api !== "frontend_fastapi_request");
  const backend = backendRows.filter((row) => row.api === spec.backendApi);
  const allowedBackendApis = new Set(spec.allowedBackendApis);
  return frontend.length === 1 &&
    backendRows.length === rows.length - 1 &&
    backend.length === 1 &&
    new Set(backendRows.map((row) => row.api)).size === backendRows.length &&
    backendRows.every((row) => typeof row.api === "string" && allowedBackendApis.has(row.api)) &&
    frontend[0].endpoint === spec.endpoint &&
    frontend[0].frontend_backend_auto_link_success === true &&
    frontend[0].frontend_backend_auto_link_scope === "local_fastapi_only" &&
    frontend[0].call_status === "frontend_backend_auto_link_success" &&
    frontend[0].page_render_external_calls === false &&
    frontend[0].provider_or_model_calls === false &&
    backend[0].call_status === spec.backendCallStatus &&
    backendRows.every((row) => typeof row.call_status === "string" && row.call_status.trim().length > 0) &&
    backendRows.every((row) => typeof row.row_count === "number" && Number.isInteger(row.row_count) && row.row_count >= 0) &&
    rows.every(commonLedgerRowSafe);
}

function qmtBoundarySafe(value: unknown): boolean {
  const boundary = record(value);
  return QMT_FALSE_FIELDS.every((field) => boundary[field] === false) &&
    QMT_ZERO_FIELDS.every((field) => boundary[field] === 0) &&
    QMT_TRUE_FIELDS.every((field) => boundary[field] === true);
}

function qmtPayloadLedgerSafe(value: unknown): boolean {
  if (!Array.isArray(value) || value.length !== 1) return false;
  const row = record(value[0]);
  return row.api === "local_qmt_readonly_decimal_replay" &&
    commonLedgerRowSafe(row) &&
    qmtBoundarySafe(row);
}

export function evaluateQmtReplayOrdinaryGate(input: QmtReplayGateInput): QmtReplayGateResult {
  const candidateLineage = exactSourceLineage(input.candidate, "candidate_radar_v05_next_session_lineage");
  const nextLineage = exactSourceLineage(input.nextSession, "candidate_radar_v05_lineage");
  const candidatePacketReady = input.candidate.packet_key === "command_center_3_candidate_radar_cache" &&
    input.candidate.schema_version === "candidate_radar_cache.v1" &&
    input.candidate.status === "candidate_radar_v05_local_batch_ready" &&
    input.candidate.mode === "v05_candidate_local_batch" &&
    input.candidate.cache_only === true && input.candidate.read_only === true;
  const nextPacketReady = input.nextSession.packet_key === "command_center_next_session_projection_packet" &&
    input.nextSession.schema_version === "next_session_projection.v1" &&
    input.nextSession.status === "ready_cache_replay" &&
    input.nextSession.mode === "cache_only" &&
    input.nextSession.cache_only === true && input.nextSession.read_only === true;
  const lineageReady = candidatePacketReady && nextPacketReady &&
    candidateLineage.ready && nextLineage.ready &&
    Boolean(candidateLineage.symbol && candidateLineage.taskId && candidateLineage.resultVersion && candidateLineage.scopeHash && candidateLineage.dataDate) &&
    candidateLineage.symbol === nextLineage.symbol &&
    candidateLineage.taskId === nextLineage.taskId &&
    candidateLineage.resultVersion === nextLineage.resultVersion &&
    candidateLineage.scopeHash === nextLineage.scopeHash &&
    candidateLineage.dataDate === nextLineage.dataDate;

  const qmtStatus = typeof input.qmt.status === "string" ? input.qmt.status : "";
  const qmtPacketReady = input.qmt.packet_key === "command_center_3_qmt_replay_cache" &&
    input.qmt.schema_version === "qmt_readonly_local_replay_cache.v1" &&
    new Set(["cache_missing", "ready_cache_replay"]).has(qmtStatus) &&
    input.qmt.mode === "cache_only" && input.qmt.cache_only === true && input.qmt.read_only === true;
  const safetyReady = qmtBoundarySafe(input.qmt.safety_boundary);
  const ledgersReady = envelopeLedgerSafe(input.candidateLedger, {
    endpoint: "/api/candidate-radar/cache",
    backendApi: "local_candidate_radar_cache",
    backendCallStatus: "cache_read_persisted_v05_candidate_local_batch",
    allowedBackendApis: CANDIDATE_GET_LEDGER_APIS,
  }) && envelopeLedgerSafe(input.nextLedger, {
    endpoint: "/api/next-session/cache",
    backendApi: "local_next_session_cache",
    backendCallStatus: "cache_read",
    allowedBackendApis: ["local_next_session_cache"],
  }) && envelopeLedgerSafe(input.qmtLedger, {
    endpoint: "/api/qmt-replay/cache",
    backendApi: "local_qmt_readonly_decimal_replay",
    backendCallStatus: "cache_read_no_external_call",
    allowedBackendApis: ["local_qmt_readonly_decimal_replay"],
  }) &&
    qmtPayloadLedgerSafe(input.qmt.call_ledger);
  const warningsReady = warningsEmpty(input.candidateWarnings) && warningsEmpty(input.nextWarnings) && warningsEmpty(input.qmtWarnings) &&
    warningsEmpty(input.candidate.warnings) && warningsEmpty(input.nextSession.warnings) && warningsEmpty(input.qmt.warnings);
  const source = record(input.qmt.source_lineage);
  const qmtSourceReady = strictQmtSymbol(source.source_symbol) === candidateLineage.symbol &&
    strictQmtId(source.source_task_id) === candidateLineage.taskId &&
    strictQmtId(source.source_result_version) === candidateLineage.resultVersion &&
    strictQmtScope(source.source_scope_hash) === candidateLineage.scopeHash &&
    strictQmtDate(source.source_data_date) === candidateLineage.dataDate;
  const qmtResultIntegrityReady = input.qmt.result_integrity_validated === true &&
    input.qmt.result_integrity_status === "result_integrity_validated" &&
    record(input.qmt.lineage_validation).schema_version === "qmt_readonly_source_lineage_validation.v1" &&
    record(input.qmt.lineage_validation).status === "source_result_integrity_validated" &&
    record(input.qmt.lineage_validation).passed === true;
  const baseReady = !input.loading && input.error === "" && lineageReady && qmtPacketReady && safetyReady && ledgersReady && warningsReady;
  const resultReady = baseReady && qmtStatus === "ready_cache_replay" && qmtSourceReady && qmtResultIntegrityReady;
  const checks: Array<[boolean, string]> = [
    [!input.loading && input.error === "", "loading_or_error"],
    [warningsReady, "warning_present"],
    [ledgersReady, "ledger_invalid"],
    [candidatePacketReady && nextPacketReady && candidateLineage.ready && nextLineage.ready, "source_contract_invalid"],
    [lineageReady, "lineage_mismatch"],
    [qmtPacketReady, "qmt_packet_invalid"],
    [safetyReady, "qmt_safety_invalid"],
  ];
  const failed = checks.find(([passed]) => !passed);
  return {
    launchReady: baseReady,
    resultReady,
    reasonKey: failed?.[1] ?? "ready",
    symbol: candidateLineage.symbol,
    taskId: candidateLineage.taskId,
    resultVersion: candidateLineage.resultVersion,
    scopeHash: candidateLineage.scopeHash,
    dataDate: candidateLineage.dataDate,
    qmtStatus,
    lineageReady,
    safetyReady,
    ledgersReady,
    warningsReady,
  };
}
