import { useEffect, useState } from "react";
import { getNextSessionCache, postTask } from "../api/client";
import PacketCard from "../components/PacketCard";
import TaskStatusPanel from "../components/TaskStatusPanel";

export default function NextSessionMap() {
  const [packet, setPacket] = useState<Record<string, unknown>>({});
  const [taskId, setTaskId] = useState("");

  useEffect(() => {
    void getNextSessionCache().then((res) => setPacket(res.data));
  }, []);

  return (
    <PacketCard title="次日操作图谱" subtitle="缓存查看不触发外部刷新" status={String(packet.status ?? "cache")}>
      <div className="actions">
        <button onClick={() => void getNextSessionCache().then((res) => setPacket(res.data))}>查看缓存</button>
        <button onClick={() => void postTask("/api/next-session/generate").then((res) => setTaskId(res.data.task_id))}>生成任务</button>
      </div>
      <TaskStatusPanel taskId={taskId} />
      <pre>{JSON.stringify(packet, null, 2)}</pre>
    </PacketCard>
  );
}
