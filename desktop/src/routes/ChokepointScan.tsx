import { useEffect, useState } from "react";
import { getChokepointCache, postTask } from "../api/client";
import PacketCard from "../components/PacketCard";
import TaskStatusPanel from "../components/TaskStatusPanel";

export default function ChokepointScan() {
  const [packet, setPacket] = useState<Record<string, unknown>>({});
  const [taskId, setTaskId] = useState("");

  useEffect(() => {
    void getChokepointCache().then((res) => setPacket(res.data));
  }, []);

  return (
    <PacketCard title="产业链瓶颈扫描" subtitle="运行必须按钮触发；DeepSeek 不作为数据源" status={String(packet.status ?? "cache")}>
      <div className="actions">
        <button onClick={() => void getChokepointCache().then((res) => setPacket(res.data))}>查看缓存</button>
        <button onClick={() => void postTask("/api/chokepoint/run").then((res) => setTaskId(res.data.task_id))}>运行任务</button>
      </div>
      <TaskStatusPanel taskId={taskId} />
      <pre>{JSON.stringify(packet, null, 2)}</pre>
    </PacketCard>
  );
}
