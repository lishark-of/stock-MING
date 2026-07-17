export type GateRecord = Record<string, unknown>;

export type NextSessionOrdinaryGateInput = {
  loading: boolean;
  error: string;
  packet: GateRecord;
  chartPayload?: GateRecord;
  chartSummary: GateRecord;
  lineage: GateRecord;
  confirmedSymbol: unknown;
  cacheEnvelopeWarnings: unknown;
  taskEnvelopeWarnings: unknown;
  taskIndex: GateRecord | null;
  durableEvidence: GateRecord;
};

export type NextSessionOrdinaryGateResult = {
  ready: boolean;
  reasonKey: string;
  reason: string;
  symbol: string;
  dataDate: string;
  expectedTradeDate: string;
  chartDataDate: string;
  sourceTaskId: string;
  resultVersion: string;
  scopeHash: string;
  freshnessState: string;
  calendarValidated: boolean;
  hasWarnings: boolean;
  hasBlockingStatus: boolean;
  safetyReady: boolean;
};

const STRICT_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$/;
const STRICT_SCOPE_HASH = /^[0-9a-f]{64}$/;
const STRICT_SYMBOL = /^[0-9]{6}\.(?:SH|SZ|BJ)$/;
const BLOCKING_STATUS = /(?:^|[_:-])(blocked|failed|error|degraded|unknown)(?:$|[_:-])/i;
const CURRENT_FRESHNESS = new Set(["fresh", "current", "today"]);
const PACKET_READY_STATUS = new Set(["ready", "ready_cache_replay"]);
const INTERACTION_READY_STATUS = new Set([
  "interaction_ready",
  "interaction_contract_ready_parity_pending",
]);

function record(value: unknown): GateRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as GateRecord
    : {};
}

function strictString(value: unknown, pattern: RegExp): string {
  if (typeof value !== "string") return "";
  const normalized = value.trim();
  return pattern.test(normalized) ? normalized : "";
}

export function strictOrdinaryId(value: unknown): string {
  return strictString(value, STRICT_ID);
}

export function strictOrdinaryScopeHash(value: unknown): string {
  return strictString(value, STRICT_SCOPE_HASH);
}

export function strictOrdinarySymbol(value: unknown): string {
  if (typeof value !== "string") return "";
  const normalized = value.trim().toUpperCase();
  return STRICT_SYMBOL.test(normalized) ? normalized : "";
}

export function strictOrdinaryDate(value: unknown): string {
  if (typeof value !== "string") return "";
  const match = value.trim().match(/^(\d{4})-?(\d{2})-?(\d{2})$/);
  if (!match) return "";
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const candidate = new Date(Date.UTC(year, month - 1, day));
  if (
    candidate.getUTCFullYear() !== year ||
    candidate.getUTCMonth() !== month - 1 ||
    candidate.getUTCDate() !== day
  ) return "";
  return `${yearText}${monthText}${dayText}`;
}

function strictStatus(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function warningsAreEmpty(value: unknown): boolean {
  return Array.isArray(value) && value.length === 0;
}

function containsBlockingStatus(values: unknown[]): boolean {
  return values.some((value) => {
    if (typeof value !== "string") return false;
    return BLOCKING_STATUS.test(value.trim());
  });
}

export function evaluateNextSessionOrdinaryGate(
  input: NextSessionOrdinaryGateInput
): NextSessionOrdinaryGateResult {
  const chart = record(input.chartPayload);
  const contract = record(chart.chart_contract);
  const freshness = record(input.lineage.freshness_state);
  const taskIndex = record(input.taskIndex);

  const lineageStatus = strictStatus(input.lineage.status);
  const chartLineageStatus = strictStatus(chart.candidate_radar_v05_lineage_status);
  const packetStatus = strictStatus(input.packet.status);
  const chartStatus = strictStatus(chart.status);
  const summaryStatus = strictStatus(input.chartSummary.status);
  const freshnessState = strictStatus(freshness.state);
  const genericFreshnessState = freshness.freshness_state === undefined
    ? freshnessState
    : strictStatus(freshness.freshness_state);

  const lineageSymbol = strictOrdinarySymbol(input.lineage.symbol);
  const confirmedSymbol = strictOrdinarySymbol(input.confirmedSymbol);
  const payloadSymbol = strictOrdinarySymbol(
    chart.symbol ?? chart.ts_code ?? chart.confirmed_symbol
  );
  const summarySymbol = strictOrdinarySymbol(
    input.chartSummary.symbol ?? input.chartSummary.ts_code ?? input.chartSummary.confirmed_symbol
  );
  const sourceTaskId = strictOrdinaryId(input.lineage.candidate_task_id);
  const chartSourceTaskId = strictOrdinaryId(chart.source_task_id);
  const resultVersion = strictOrdinaryId(input.lineage.candidate_result_version);
  const chartResultVersion = strictOrdinaryId(chart.result_version);
  const scopeHash = strictOrdinaryScopeHash(input.lineage.candidate_scope_hash);
  const chartScopeHash = strictOrdinaryScopeHash(chart.candidate_scope_hash);
  const taskIndexSourceTaskId = strictOrdinaryId(taskIndex.latest_confirmed_task_id);
  const taskIndexSymbol = strictOrdinarySymbol(taskIndex.latest_confirmed_symbol);
  const dataDate = strictOrdinaryDate(input.lineage.data_date);
  const chartDataDate = strictOrdinaryDate(chart.data_date ?? chart.base_date);
  const freshnessDataDate = strictOrdinaryDate(freshness.data_date);
  const expectedTradeDate = strictOrdinaryDate(freshness.expected_trade_date);

  const genericCalendarMarker = freshness.calendar_validated;
  const calendarValidated =
    freshness.expected_trade_date_calendar_validated === true &&
    (genericCalendarMarker === undefined || genericCalendarMarker === true);
  const freshnessReady =
    CURRENT_FRESHNESS.has(freshnessState) &&
    genericFreshnessState === freshnessState &&
    calendarValidated &&
    Boolean(dataDate) &&
    dataDate === expectedTradeDate &&
    dataDate === freshnessDataDate;

  const hasWarnings = ![
    input.cacheEnvelopeWarnings,
    input.taskEnvelopeWarnings,
    input.packet.warnings,
    chart.warnings,
  ].every(warningsAreEmpty);

  const hasBlockingStatus = containsBlockingStatus([
    packetStatus,
    chartStatus,
    summaryStatus,
    lineageStatus,
    chartLineageStatus,
    freshnessState,
    genericFreshnessState,
    input.chartSummary.maturity_status,
    record(chart.chart_maturity).status,
    record(chart.interaction_readiness_audit).status,
    record(input.packet.ordinary_result_replay_summary).status,
    taskIndex.status,
    taskIndex.latest_confirmed_task_status,
  ]);

  const sourcePacket = strictOrdinaryId(chart.source_packet);
  const contractSourcePacket = strictOrdinaryId(contract.source_packet);
  const summarySourcePacket = strictOrdinaryId(input.chartSummary.source_packet);
  const taskPolicy = record(taskIndex.policy);
  const statusesReady = Boolean(
    PACKET_READY_STATUS.has(packetStatus) &&
    chartStatus === "ready" &&
    summaryStatus === "ready" &&
    lineageStatus === "same_packet_lineage_ready" &&
    chartLineageStatus === "same_packet_lineage_ready" &&
    CURRENT_FRESHNESS.has(freshnessState) &&
    genericFreshnessState === freshnessState &&
    strictStatus(record(chart.chart_maturity).status) === "ready" &&
    INTERACTION_READY_STATUS.has(strictStatus(record(chart.interaction_readiness_audit).status)) &&
    strictStatus(record(input.packet.ordinary_result_replay_summary).status) === "ready_cache_replay" &&
    strictStatus(taskIndex.status) === "ready" &&
    strictStatus(taskIndex.latest_confirmed_task_status) === "success" &&
    strictStatus(input.durableEvidence.status) === "next_session_durable_evidence_recipe_ready_production_pending"
  );
  const safetyReady = Boolean(
    input.packet.packet_key === "command_center_next_session_projection_packet" &&
    input.packet.schema_version === "next_session_projection.v1" &&
    input.packet.cache_only === true &&
    input.packet.read_only === true &&
    input.packet.external_calls_triggered === false &&
    input.packet.tushare_called === false &&
    input.packet.deepseek_called === false &&
    input.packet.github_called === false &&
    input.packet.provider_or_model_calls === false &&
    input.packet.does_not_execute_trades === true &&
    input.packet.does_not_modify_action === true &&
    input.packet.does_not_modify_strategy_action === true &&
    input.packet.does_not_modify_operation_zones === true &&
    input.packet.contains_secret === false &&
    input.lineage.research_only === true &&
    input.lineage.no_buy === true &&
    input.lineage.no_action === true &&
    input.lineage.no_trade === true &&
    input.lineage.external_calls_triggered === false &&
    input.lineage.tushare_called === false &&
    input.lineage.deepseek_called === false &&
    input.lineage.github_called === false &&
    input.lineage.does_not_modify_strategy_action === true &&
    input.lineage.does_not_modify_operation_zones === true &&
    input.lineage.contains_secret === false &&
    contract.contract_key === "next_session_echarts_payload" &&
    contract.schema_version === "next_session_echarts_payload.v1" &&
    contract.renderer === "ECharts" &&
    contract.cache_only === true &&
    contract.external_calls_triggered === false &&
    contract.tushare_called === false &&
    contract.deepseek_called === false &&
    contract.github_called === false &&
    contract.does_not_execute_trades === true &&
    contract.frontend_computes_trade_action === false &&
    contract.does_not_modify_action === true &&
    contract.does_not_modify_operation_zones === true &&
    contract.requires_button_task_for_refresh === true &&
    sourcePacket === "command_center_next_session_projection_packet" &&
    contractSourcePacket === sourcePacket &&
    input.chartSummary.renderer === "ECharts" &&
    summarySourcePacket === sourcePacket &&
    input.chartSummary.is_exact_next_session_packet === true &&
    input.chartSummary.uses_real_daily_close === true &&
    input.chartSummary.frontend_computes_trade_action === false &&
    input.chartSummary.does_not_modify_action === true &&
    input.chartSummary.does_not_modify_operation_zones === true &&
    input.chartSummary.cache_only === true &&
    input.chartSummary.external_calls_triggered === false &&
    input.chartSummary.tushare_called === false &&
    input.chartSummary.deepseek_called === false &&
    input.chartSummary.github_called === false &&
    input.chartSummary.does_not_execute_trades === true &&
    input.durableEvidence.schema_version === "next_session_durable_evidence_recipe.v1" &&
    input.durableEvidence.provider_execution_implemented === false &&
    input.durableEvidence.model_execution_implemented === false &&
    input.durableEvidence.worker_execution_implemented === false &&
    taskIndex.external_calls_triggered === false &&
    taskIndex.tushare_called === false &&
    taskIndex.deepseek_called === false &&
    taskIndex.github_called === false &&
    taskIndex.readback_external_calls_triggered === false &&
    taskIndex.does_not_execute_trades === true &&
    taskIndex.does_not_modify_strategy_action === true &&
    taskIndex.packet_key === "command_center_3_task_status_index" &&
    taskIndex.schema_version === "command_center_3_task_status_index.v1" &&
    taskIndex.mode === "cache_only" &&
    taskPolicy.get_tasks_cache_only === true &&
    taskPolicy.does_not_create_tasks === true &&
    taskPolicy.does_not_call_external_sources === true &&
    taskPolicy.latest_confirmed_readback_calls_external_sources === false &&
    taskPolicy.latest_confirmed_readback_creates_task === false &&
    taskPolicy.does_not_execute_trades === true &&
    taskPolicy.does_not_modify_strategy_action === true &&
    taskPolicy.contains_secret === false
  );

  const loadingReady = !input.loading && input.error === "";
  const lineageReady =
    lineageStatus === "same_packet_lineage_ready" &&
    chartLineageStatus === "same_packet_lineage_ready" &&
    Boolean(sourceTaskId && resultVersion && scopeHash && lineageSymbol && dataDate);
  const symbolReady = Boolean(
    lineageSymbol && confirmedSymbol && payloadSymbol && summarySymbol &&
    lineageSymbol === confirmedSymbol &&
    lineageSymbol === payloadSymbol &&
    lineageSymbol === summarySymbol
  );
  const bindingReady = Boolean(
    sourceTaskId && chartSourceTaskId && sourceTaskId === chartSourceTaskId &&
    taskIndexSourceTaskId && taskIndexSourceTaskId === sourceTaskId &&
    taskIndexSymbol && taskIndexSymbol === lineageSymbol &&
    resultVersion && chartResultVersion && resultVersion === chartResultVersion &&
    scopeHash && chartScopeHash && scopeHash === chartScopeHash &&
    dataDate && chartDataDate && dataDate === chartDataDate
  );
  const chartReady =
    chartStatus === "ready" &&
    summaryStatus === "ready" &&
    chart.is_exact_next_session_packet === true &&
    chart.uses_real_daily_close === true &&
    input.chartSummary.has_drawable_data === true;

  const checks: Array<[boolean, string, string]> = [
    [loadingReady, "loading_or_error", "本地图谱仍在读取或读取失败"],
    [!hasWarnings, "warning_present", "本地结果仍有待处理提示"],
    [!hasBlockingStatus && statusesReady, "blocking_status", "本地结果处于暂停、失败或信息不完整状态"],
    [lineageReady, "lineage_invalid", "结果来源信息不完整"],
    [symbolReady, "symbol_mismatch", "当前标的与图谱标的不一致"],
    [bindingReady, "binding_mismatch", "图谱版本、范围、任务或日期不一致"],
    [freshnessReady, "freshness_invalid", "数据日期或交易日历尚未通过验证"],
    [safetyReady, "safety_incomplete", "只读与安全边界尚未完整验证"],
    [chartReady, "chart_not_ready", "当前没有可安全展示的次日走势"],
  ];
  const failed = checks.find(([passed]) => !passed);
  return {
    ready: failed === undefined,
    reasonKey: failed?.[1] ?? "ready",
    reason: failed?.[2] ?? "同源结果已通过验证",
    symbol: lineageSymbol,
    dataDate,
    expectedTradeDate,
    chartDataDate,
    sourceTaskId,
    resultVersion,
    scopeHash,
    freshnessState,
    calendarValidated,
    hasWarnings,
    hasBlockingStatus,
    safetyReady,
  };
}
