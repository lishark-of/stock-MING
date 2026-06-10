import { useEffect, useState } from "react";
import { getSerenityCache, postTask } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import TaskStatusPanel from "../components/TaskStatusPanel";

export default function SerenityMethodRadar() {
  const [packet, setPacket] = useState<Record<string, any>>({});
  const [taskId, setTaskId] = useState("");

  useEffect(() => {
    void getSerenityCache().then((res) => setPacket(res.data));
  }, []);

  const policy = packet.decision_usage_policy ?? {};
  const repositories = packet.repositories ?? [];

  return (
    <PacketCard title="Serenity 方法来源雷达" subtitle="一次性本地方法基线；只读说明，不参与交易评分" status={String(packet.github_status ?? "unverified")}>
      <div className="actions">
        <button onClick={() => void getSerenityCache().then((res) => setPacket(res.data))}>查看缓存</button>
        <button onClick={() => void postTask("/api/serenity/github-probe").then((res) => setTaskId(res.data.task_id))}>GitHub 校验任务</button>
      </div>
      <TaskStatusPanel taskId={taskId} />
      <MetricGrid
        items={[
          { label: "来源", value: String(packet.source_type ?? "local_baseline") },
          { label: "repo 数", value: repositories.length },
          { label: "GitHub 状态", value: String(packet.github_status ?? "未校验") },
          { label: "DeepSeek", value: packet.deepseek_called === true ? "已调用" : "不调用", tone: packet.deepseek_called === true ? "bad" : "good" },
          { label: "进入评分", value: policy.enters_chokepoint_score === true ? "会" : "不会", tone: policy.enters_chokepoint_score === true ? "bad" : "good" },
          { label: "进入 action", value: policy.enters_strategy_action === true ? "会" : "不会", tone: policy.enters_strategy_action === true ? "bad" : "good" }
        ]}
      />
      <h3>仓库方法雷达</h3>
      <DataLineageTable rows={repositories} />
      <JsonDetails title="防幻觉演进" data={packet.hallucination_defense_evolution ?? []} />
      <JsonDetails title="方法归纳" data={packet.method_summaries ?? {}} />
      <JsonDetails title="Serenity packet" data={packet} />
    </PacketCard>
  );
}
