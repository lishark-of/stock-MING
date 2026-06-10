import { useEffect, useState } from "react";
import { getMigrationStatus } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";

export default function MigrationStatus() {
  const [packet, setPacket] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getMigrationStatus().then((res) => setPacket(res.data));
  }, []);

  const progress = (packet.progress_baseline as Array<Record<string, unknown>> | undefined) ?? [];
  const policy = packet.api_policy as Record<string, unknown> | undefined;
  const baselinePolicy = packet.baseline_policy as Record<string, unknown> | undefined;

  return (
    <PacketCard title="Command Center 3.0 迁移状态" subtitle="固定长期参考基线；只读、不重新估算、不外联" status={String(packet.status ?? "loading")}>
      <div className="actions">
        <button onClick={() => void getMigrationStatus().then((res) => setPacket(res.data))}>查看迁移基线</button>
      </div>
      <MetricGrid
        items={[
          { label: "baseline items", value: progress.length },
          { label: "planning baseline", value: baselinePolicy?.use_as_planning_baseline === true, tone: baselinePolicy?.use_as_planning_baseline === true ? "good" : "warn" },
          { label: "cache only", value: policy?.cache_only === true, tone: policy?.cache_only === true ? "good" : "warn" },
          { label: "external calls", value: policy?.external_calls_triggered === true ? "存在" : "无", tone: policy?.external_calls_triggered === true ? "bad" : "good" },
          { label: "real trading", value: policy?.does_not_execute_trades === false ? "可能" : "禁止", tone: policy?.does_not_execute_trades === false ? "bad" : "good" },
          { label: "strategy action", value: policy?.does_not_modify_strategy_action === false ? "会修改" : "不修改", tone: policy?.does_not_modify_strategy_action === false ? "bad" : "good" }
        ]}
      />
      <h3>固定进度表</h3>
      <DataLineageTable rows={progress} />
      <JsonDetails title="目标技术栈" data={packet.target_stack ?? []} />
      <JsonDetails title="迁移原则" data={packet.principles ?? []} />
      <JsonDetails title="迁移状态 packet" data={packet} />
    </PacketCard>
  );
}
