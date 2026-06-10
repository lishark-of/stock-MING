import { useEffect, useState } from "react";
import { getChokepointCache, postTask } from "../api/client";
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

  return (
    <PacketCard title="产业链瓶颈扫描" subtitle="运行必须按钮触发；DeepSeek 不作为数据源" status={String(packet.status ?? "cache")}>
      <div className="actions">
        <button onClick={() => void getChokepointCache().then((res) => setPacket(res.data))}>查看缓存</button>
        <button onClick={() => void postTask("/api/chokepoint/run").then((res) => setTaskId(res.data.task_id))}>运行任务</button>
      </div>
      <TaskStatusPanel taskId={taskId} />
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
      {legacy?.available ? <JsonDetails title="旧分析方法摘要" data={legacy} /> : null}
      <JsonDetails title="Chokepoint packet" data={packet} />
    </PacketCard>
  );
}
