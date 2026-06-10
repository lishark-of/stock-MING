import { useEffect, useState } from "react";
import { getSerenityCache, postTask } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import PacketCard from "../components/PacketCard";
import TaskStatusPanel from "../components/TaskStatusPanel";

export default function SerenityMethodRadar() {
  const [packet, setPacket] = useState<Record<string, any>>({});
  const [taskId, setTaskId] = useState("");

  useEffect(() => {
    void getSerenityCache().then((res) => setPacket(res.data));
  }, []);

  return (
    <PacketCard title="Serenity 方法来源雷达" subtitle="一次性本地方法基线；只读说明，不参与交易评分" status={String(packet.github_status ?? "unverified")}>
      <div className="actions">
        <button onClick={() => void getSerenityCache().then((res) => setPacket(res.data))}>查看缓存</button>
        <button onClick={() => void postTask("/api/serenity/github-probe").then((res) => setTaskId(res.data.task_id))}>GitHub 校验任务</button>
      </div>
      <TaskStatusPanel taskId={taskId} />
      <DataLineageTable rows={packet.repositories ?? []} />
    </PacketCard>
  );
}
