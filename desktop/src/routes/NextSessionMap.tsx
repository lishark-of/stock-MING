import { useEffect, useState } from "react";
import { getNextSessionCache, postTask, type TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import NextSessionChart from "../components/NextSessionChart";
import PacketCard from "../components/PacketCard";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

function rowsFromArray(items: unknown, fallbackKey = "value"): Array<Record<string, unknown>> {
  if (!Array.isArray(items)) return [];
  return items.map((item, index) => {
    if (item && typeof item === "object" && !Array.isArray(item)) {
      return item as Record<string, unknown>;
    }
    return { index: index + 1, [fallbackKey]: String(item ?? "") };
  });
}

export default function NextSessionMap() {
  const [packet, setPacket] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<unknown>>([]);
  const [taskId, setTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);

  const refreshCache = () =>
    void getNextSessionCache().then((res) => {
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
      setPacket(res.data);
    });
  const launchTask = () =>
    void postTask("/api/next-session/generate").then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });

  useEffect(() => {
    refreshCache();
  }, []);

  const legacy = packet.legacy_projection_cache as Record<string, unknown> | undefined;
  const chartPayload = packet.chart_payload as Record<string, unknown> | undefined;
  const chartSummary = (packet.chart_summary as Record<string, unknown> | undefined) ?? (chartPayload?.chart_summary as Record<string, unknown> | undefined) ?? {};
  const chartContract = chartPayload?.chart_contract as Record<string, unknown> | undefined;
  const chartContractCounts = chartContract?.series_counts as Record<string, unknown> | undefined;
  const historicalRows = rowsFromArray(chartPayload?.historical_points).slice(0, 20);
  const referenceRows = rowsFromArray(chartPayload?.reference_lines);
  const operationRows = rowsFromArray(chartPayload?.operation_zones);
  const warningRows = rowsFromArray(chartPayload?.warnings, "warning");
  const chartContractRows = chartContract
    ? [
        { field: "schema_version", value: chartContract.schema_version, note: "ECharts payload 合同版本" },
        { field: "renderer", value: chartContract.renderer, note: "前端渲染器" },
        { field: "cache_only", value: String(chartContract.cache_only === true), note: "只读 cache 数据" },
        { field: "external_calls_triggered", value: String(chartContract.external_calls_triggered === true), note: "必须为 false" },
        { field: "tushare_called", value: String(chartContract.tushare_called === true), note: "必须为 false" },
        { field: "deepseek_called", value: String(chartContract.deepseek_called === true), note: "必须为 false" },
        { field: "github_called", value: String(chartContract.github_called === true), note: "必须为 false" },
        { field: "does_not_execute_trades", value: String(chartContract.does_not_execute_trades !== false), note: "必须为 true" },
        { field: "frontend_computes_trade_action", value: String(chartContract.frontend_computes_trade_action === true), note: "必须为 false" },
        { field: "does_not_modify_action", value: String(chartContract.does_not_modify_action !== false), note: "不得改 strategy action" },
        { field: "does_not_modify_operation_zones", value: String(chartContract.does_not_modify_operation_zones !== false), note: "不得改 operation_zones" },
        { field: "historical_points", value: chartContractCounts?.historical_points ?? 0, note: "历史 close 点数" },
        { field: "scenario_series", value: chartContractCounts?.scenario_series ?? 0, note: "情景路径数量" },
        { field: "reference_lines", value: chartContractCounts?.reference_lines ?? 0, note: "参考线数量" },
        { field: "operation_zones", value: chartContractCounts?.operation_zones ?? 0, note: "操作区数量" }
      ]
    : [];
  const payloadCallLedger = (packet.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((packet.warnings as Array<unknown> | undefined) ?? []);
  const scenarioRows = rowsFromArray(chartPayload?.scenario_series).map((row) => ({
    scenario_key: row.scenario_key ?? row.scenario_name,
    scenario_name: row.scenario_name,
    probability: row.probability,
    point_count: Array.isArray(row.points) ? row.points.length : 0,
    source: row.source,
    risk_note: row.risk_note
  }));
  const cacheBoundaryRows = [
    { boundary: "GET /api/next-session/cache", value: "cache_only", note: "只读缓存，不触发 Tushare、DeepSeek 或 GitHub。" },
    { boundary: "POST /api/next-session/generate", value: "button_gated_task", note: "手动任务才可能生成/刷新图谱。" },
    { boundary: "does_not_modify_action", value: String(packet.does_not_modify_action !== false), note: "前端只读，不改 strategy action。" },
    { boundary: "does_not_modify_operation_zones", value: String(packet.does_not_modify_operation_zones !== false), note: "前端只读，不改 operation_zones。" },
    { boundary: "is_exact_next_session_packet", value: String(chartPayload?.is_exact_next_session_packet === true), note: "非精确 packet 时只显示 legacy/cache 投影。" },
    { boundary: "uses_real_daily_close", value: String(chartPayload?.uses_real_daily_close === true), note: "未验证真实 close 时必须展示风险提示。" }
  ];

  return (
    <PacketCard title="次日操作图谱" subtitle="缓存查看不触发外部刷新" status={String(packet.status ?? "cache")}>
      <div className="actions">
        <button onClick={refreshCache}>查看缓存</button>
        <button onClick={launchTask}>生成任务</button>
      </div>
      <TaskLaunchReceipt receipt={taskReceipt} />
      <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
      <MetricGrid
        items={[
          { label: "状态", value: String(packet.status ?? "cache") },
          { label: "cache source", value: String(packet.cache_source ?? "--") },
          { label: "本地快照", value: Boolean(packet.source_snapshot_available), tone: packet.source_snapshot_available ? "good" : "warn" },
          { label: "旧 projection", value: Boolean(legacy?.available), tone: legacy?.available ? "warn" : "neutral" },
          { label: "精确图谱", value: chartSummary.is_exact_next_session_packet === true, tone: chartSummary.is_exact_next_session_packet === true ? "good" : "warn" },
          { label: "真实 close", value: chartSummary.uses_real_daily_close === true, tone: chartSummary.uses_real_daily_close === true ? "good" : "warn" },
          { label: "可绘制", value: chartSummary.has_drawable_data === true, tone: chartSummary.has_drawable_data === true ? "good" : "warn" },
          { label: "图表合同", value: String(chartContract?.schema_version ?? "missing"), tone: chartContract ? "good" : "warn" },
          { label: "情景路径", value: chartSummary.scenario_series_count as number | undefined },
          { label: "参考线", value: chartSummary.reference_line_count as number | undefined },
          { label: "操作区", value: chartSummary.operation_zone_count as number | undefined },
          { label: "历史点", value: chartSummary.historical_point_count as number | undefined },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length },
          { label: "修改 action", value: packet.does_not_modify_action === false ? "会" : "不会", tone: packet.does_not_modify_action === false ? "bad" : "good" },
          { label: "修改 operation_zones", value: packet.does_not_modify_operation_zones === false ? "会" : "不会", tone: packet.does_not_modify_operation_zones === false ? "bad" : "good" }
        ]}
      />
      <p className="risk-note">{String(packet.summary ?? "当前只读取 cache；无缓存时不会触发 Tushare。")}</p>
      <NextSessionChart payload={chartPayload} />
      <h3>ECharts 图表摘要</h3>
      <DataLineageTable rows={[chartSummary]} />
      <h3>ECharts 图表数据合同</h3>
      <DataLineageTable rows={chartContractRows} />
      <h3>缓存边界</h3>
      <DataLineageTable rows={cacheBoundaryRows} />
      <h3>GET cache envelope call_ledger</h3>
      <DataLineageTable rows={cacheCallLedger} />
      <h3>GET cache envelope warnings</h3>
      <DataLineageTable rows={rowsFromArray(cacheWarnings, "warning")} />
      <h3>情景路径</h3>
      <DataLineageTable rows={scenarioRows} />
      <h3>参考线</h3>
      <DataLineageTable rows={referenceRows} />
      <h3>操作区</h3>
      <DataLineageTable rows={operationRows} />
      <h3>历史 close 样例</h3>
      <DataLineageTable rows={historicalRows} />
      <h3>图表风险提示</h3>
      <DataLineageTable rows={warningRows} />
      {legacy?.available ? <JsonDetails title="legacy projection 摘要" data={legacy} /> : null}
      <JsonDetails title="次日图谱 cache packet" data={packet} />
    </PacketCard>
  );
}
