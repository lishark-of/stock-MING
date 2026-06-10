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

  const refreshCache = () => void getSerenityCache().then((res) => setPacket(res.data));

  useEffect(() => {
    refreshCache();
  }, []);

  const policy = packet.decision_usage_policy ?? {};
  const repositories = packet.repositories ?? [];
  const defenseRows = packet.hallucination_defense_evolution ?? [];
  const methodRows = packet.method_summaries ?? [];
  const decisionRows = Object.entries(policy).map(([key, value]) => ({ boundary: key, value: String(value) }));
  const sourceRows = [
    { field: "source_label", value: "本地方法来源基线" },
    { field: "source_type", value: String(packet.source_type ?? "user_screenshot_baseline") },
    { field: "github_status", value: String(packet.github_status ?? "未校验") },
    { field: "deepseek_called", value: String(packet.deepseek_called === true) },
    { field: "cache_external_calls", value: String(packet.cache_api_external_calls_triggered ?? false) },
    { field: "enters_strategy_action", value: String(policy.enters_strategy_action === true) },
    { field: "enters_chokepoint_score", value: String(policy.enters_chokepoint_score === true) },
    { field: "enters_next_session_projection", value: String(policy.enters_next_session_projection === true) }
  ];

  return (
    <PacketCard title="Serenity 方法来源雷达" subtitle="一次性本地方法基线；只读说明，不参与交易评分" status={String(packet.github_status ?? "unverified")}>
      <div className="actions">
        <button onClick={refreshCache}>查看缓存</button>
        <button onClick={() => void postTask("/api/serenity/github-probe").then((res) => setTaskId(res.data.task_id))}>GitHub 校验任务</button>
      </div>
      <p className="risk-note">默认只读本地方法来源基线；GitHub 当前状态为未校验。GitHub 校验只在手动 POST task 后进入任务队列。</p>
      <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
      <MetricGrid
        items={[
          { label: "来源", value: "本地方法来源基线" },
          { label: "repo 数", value: repositories.length },
          { label: "GitHub 状态", value: String(packet.github_status ?? "未校验") },
          { label: "DeepSeek", value: packet.deepseek_called === true ? "已调用" : "不调用", tone: packet.deepseek_called === true ? "bad" : "good" },
          { label: "进入评分", value: policy.enters_chokepoint_score === true ? "会" : "不会", tone: policy.enters_chokepoint_score === true ? "bad" : "good" },
          { label: "进入 action", value: policy.enters_strategy_action === true ? "会" : "不会", tone: policy.enters_strategy_action === true ? "bad" : "good" },
          { label: "进入次日图谱", value: policy.enters_next_session_projection === true ? "会" : "不会", tone: policy.enters_next_session_projection === true ? "bad" : "good" },
          { label: "进入 DeepSeek prompt", value: policy.enters_deepseek_prompt === true ? "会" : "不会", tone: policy.enters_deepseek_prompt === true ? "bad" : "good" }
        ]}
      />
      <h3>仓库方法雷达</h3>
      <DataLineageTable rows={repositories} />
      <h3>防幻觉演进</h3>
      <DataLineageTable rows={defenseRows} />
      <h3>方法归纳</h3>
      <DataLineageTable rows={methodRows} />
      <h3>决策边界</h3>
      <DataLineageTable rows={decisionRows} />
      <h3>技术血缘</h3>
      <DataLineageTable rows={sourceRows} />
      <JsonDetails title="防幻觉演进 raw" data={defenseRows} />
      <JsonDetails title="方法归纳 raw" data={methodRows} />
      <JsonDetails title="Serenity packet" data={packet} />
    </PacketCard>
  );
}
