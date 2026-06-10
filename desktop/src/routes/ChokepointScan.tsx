import { useEffect, useState } from "react";
import { getChokepointCache, postTask } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import TaskStatusPanel from "../components/TaskStatusPanel";

export default function ChokepointScan() {
  const [packet, setPacket] = useState<Record<string, unknown>>({});
  const [taskId, setTaskId] = useState("");

  useEffect(() => {
    void getChokepointCache().then((res) => setPacket(res.data));
  }, []);

  const legacy = packet.legacy_analysis_method_cache as Record<string, unknown> | undefined;
  const boundaryRows = [
    { boundary: "GET /api/chokepoint/cache", value: "cache_only", note: "只读本地缓存，不调用 DeepSeek/Tushare/GitHub。" },
    { boundary: "POST /api/chokepoint/run", value: "button_gated_task", note: "手动 POST task 才能创建瓶颈扫描任务。" },
    { boundary: "DeepSeek", value: packet.deepseek_called === true ? "called" : "not_called", note: "DeepSeek 只可整理解释，不作为数据源。" },
    { boundary: "strategy action", value: packet.enters_strategy_action === true ? "enters" : "blocked", note: "研究解释不进入 strategy action。" },
    { boundary: "next session projection", value: packet.enters_next_session_projection === true ? "enters" : "blocked", note: "不写回次日操作图谱。" },
    { boundary: "real trading", value: "disabled", note: "不执行真实交易，不自动下单。" }
  ];
  const sourceRows = [
    { field: "packet_key", value: String(packet.packet_key ?? "command_center_chokepoint_scan_packet") },
    { field: "schema_version", value: String(packet.schema_version ?? "--") },
    { field: "status", value: String(packet.status ?? "cache") },
    { field: "cache_source", value: String(packet.cache_source ?? "--") },
    { field: "source_snapshot_available", value: String(packet.source_snapshot_available ?? false) },
    { field: "cache_api_external_calls_triggered", value: String(packet.cache_api_external_calls_triggered ?? false) },
    { field: "legacy_analysis_method_cache", value: String(Boolean(legacy?.available)) }
  ];

  return (
    <PacketCard title="产业链瓶颈扫描" subtitle="运行必须按钮触发；DeepSeek 不作为数据源" status={String(packet.status ?? "cache")}>
      <div className="actions">
        <button onClick={() => void getChokepointCache().then((res) => setPacket(res.data))}>查看缓存</button>
        <button onClick={() => void postTask("/api/chokepoint/run").then((res) => setTaskId(res.data.task_id))}>运行任务</button>
      </div>
      <TaskStatusPanel taskId={taskId} />
      <p className="risk-note">GET cache 不运行瓶颈扫描；cache API 永不外联。运行任务必须手动 POST task，且只进入研究解释层。</p>
      <MetricGrid
        items={[
          { label: "状态", value: String(packet.status ?? "cache") },
          { label: "cache source", value: String(packet.cache_source ?? "--") },
          { label: "本地快照", value: Boolean(packet.source_snapshot_available), tone: packet.source_snapshot_available ? "good" : "warn" },
          { label: "DeepSeek", value: packet.deepseek_called === true ? "已调用" : "不调用", tone: packet.deepseek_called === true ? "bad" : "good" },
          { label: "进入 action", value: packet.enters_strategy_action === true ? "会" : "不会", tone: packet.enters_strategy_action === true ? "bad" : "good" },
          { label: "进入次日图谱", value: packet.enters_next_session_projection === true ? "会" : "不会", tone: packet.enters_next_session_projection === true ? "bad" : "good" }
        ]}
      />
      <p className="risk-note">{String(packet.summary ?? "GET cache 不运行瓶颈扫描。")}</p>
      <h3>执行边界</h3>
      <DataLineageTable rows={boundaryRows} />
      <h3>缓存血缘</h3>
      <DataLineageTable rows={sourceRows} />
      {legacy?.available ? <JsonDetails title="旧分析方法摘要" data={legacy} /> : null}
      <JsonDetails title="Chokepoint packet" data={packet} />
    </PacketCard>
  );
}
