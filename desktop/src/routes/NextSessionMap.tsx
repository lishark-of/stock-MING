import { useEffect, useState } from "react";
import { getNextSessionCache, postTask } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import NextSessionChart from "../components/NextSessionChart";
import PacketCard from "../components/PacketCard";
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
  const [taskId, setTaskId] = useState("");

  useEffect(() => {
    void getNextSessionCache().then((res) => setPacket(res.data));
  }, []);

  const legacy = packet.legacy_projection_cache as Record<string, unknown> | undefined;
  const chartPayload = packet.chart_payload as Record<string, unknown> | undefined;
  const historicalRows = rowsFromArray(chartPayload?.historical_points).slice(0, 20);
  const referenceRows = rowsFromArray(chartPayload?.reference_lines);
  const operationRows = rowsFromArray(chartPayload?.operation_zones);
  const warningRows = rowsFromArray(chartPayload?.warnings, "warning");
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
        <button onClick={() => void getNextSessionCache().then((res) => setPacket(res.data))}>查看缓存</button>
        <button onClick={() => void postTask("/api/next-session/generate").then((res) => setTaskId(res.data.task_id))}>生成任务</button>
      </div>
      <TaskStatusPanel taskId={taskId} />
      <MetricGrid
        items={[
          { label: "状态", value: String(packet.status ?? "cache") },
          { label: "cache source", value: String(packet.cache_source ?? "--") },
          { label: "本地快照", value: Boolean(packet.source_snapshot_available), tone: packet.source_snapshot_available ? "good" : "warn" },
          { label: "旧 projection", value: Boolean(legacy?.available), tone: legacy?.available ? "warn" : "neutral" },
          { label: "精确图谱", value: chartPayload?.is_exact_next_session_packet === true, tone: chartPayload?.is_exact_next_session_packet === true ? "good" : "warn" },
          { label: "真实 close", value: chartPayload?.uses_real_daily_close === true, tone: chartPayload?.uses_real_daily_close === true ? "good" : "warn" },
          { label: "情景路径", value: scenarioRows.length },
          { label: "参考线", value: referenceRows.length },
          { label: "操作区", value: operationRows.length },
          { label: "历史点样例", value: historicalRows.length },
          { label: "修改 action", value: packet.does_not_modify_action === false ? "会" : "不会", tone: packet.does_not_modify_action === false ? "bad" : "good" },
          { label: "修改 operation_zones", value: packet.does_not_modify_operation_zones === false ? "会" : "不会", tone: packet.does_not_modify_operation_zones === false ? "bad" : "good" }
        ]}
      />
      <p className="risk-note">{String(packet.summary ?? "当前只读取 cache；无缓存时不会触发 Tushare。")}</p>
      <NextSessionChart payload={chartPayload} />
      <h3>缓存边界</h3>
      <DataLineageTable rows={cacheBoundaryRows} />
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
