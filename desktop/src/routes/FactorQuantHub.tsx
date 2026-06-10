import { useEffect, useState } from "react";
import type { EChartsOption } from "echarts";
import { getFactorQuantCache, postTask } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import EChartPanel from "../components/EChartPanel";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import TaskStatusPanel from "../components/TaskStatusPanel";

export default function FactorQuantHub() {
  const [packet, setPacket] = useState<Record<string, any>>({});
  const [taskId, setTaskId] = useState("");

  useEffect(() => {
    void getFactorQuantCache().then((res) => setPacket(res.data));
  }, []);

  const score = packet.score ?? {};
  const runtime = packet.runtime ?? {};
  const governance = packet.governance ?? {};
  const bridge = packet.next_session_bridge ?? {};
  const linkedPackets = packet.linked_packets ?? {};
  const option: EChartsOption = {
    tooltip: {},
    xAxis: { type: "category", data: ["支持", "压制", "中性", "缺失", "冲突"] },
    yAxis: { type: "value" },
    series: [
      {
        type: "bar",
        data: [
          score.support_factors?.length ?? 0,
          score.suppress_factors?.length ?? 0,
          score.neutral_factors?.length ?? 0,
          score.missing_factors?.length ?? 0,
          score.conflict_factors?.length ?? 0
        ]
      }
    ]
  };

  return (
    <PacketCard title="2.0 多因子量化图谱" subtitle="只进入 evidence_effects 预览，不修改 action" status={String(packet.mode ?? "cache_only")}>
      <div className="actions">
        <button onClick={() => void getFactorQuantCache().then((res) => setPacket(res.data))}>查看缓存</button>
        <button onClick={() => void postTask("/api/factor-quant/refresh-data").then((res) => setTaskId(res.data.task_id))}>刷新数据</button>
        <button onClick={() => void postTask("/api/factor-quant/run-light").then((res) => setTaskId(res.data.task_id))}>运行计算</button>
        <button onClick={() => void postTask("/api/factor-quant/deepseek-explain").then((res) => setTaskId(res.data.task_id))}>DeepSeek 整理</button>
      </div>
      <p className="risk-note">多因子量化不是交易建议；不改价格、持仓、operation_zones 或 strategy action。</p>
      <TaskStatusPanel taskId={taskId} />
      <MetricGrid
        items={[
          { label: "mode", value: packet.mode ?? "cache_only" },
          { label: "runtime", value: runtime.status ?? "not_run" },
          { label: "coverage", value: runtime.coverage ?? 0 },
          { label: "missing", value: runtime.missing_count ?? 0 },
          { label: "score band", value: score.score_band ?? "missing" },
          { label: "core action", value: governance.allow_core_action === true ? "允许" : "禁止", tone: governance.allow_core_action === true ? "bad" : "good" },
          { label: "evidence preview", value: bridge.enters_evidence_effects === true ? "预览" : "关闭" },
          { label: "snapshot", value: packet.source_snapshot_available === true, tone: packet.source_snapshot_available === true ? "good" : "warn" }
        ]}
      />
      <EChartPanel option={option} />
      <div className="grid compact-grid">
        <PacketCard title="支持 / 压制" subtitle="只用于 evidence_effects 预览">
          <p>support: {String(score.support_factors?.length ?? 0)}</p>
          <p>suppress: {String(score.suppress_factors?.length ?? 0)}</p>
          <p>conflict: {String(score.conflict_factors?.length ?? 0)}</p>
        </PacketCard>
        <PacketCard title="现有上下文链接" subtitle="来自本地 packet/cache">
          <p>strategy: {String(Boolean(linkedPackets.strategy_execution_packet))}</p>
          <p>decision: {String(Boolean(linkedPackets.decision_packet))}</p>
          <p>legacy quant: {String(Boolean(linkedPackets.legacy_quant_packet))}</p>
        </PacketCard>
      </div>
      <h3>数据血缘</h3>
      <DataLineageTable rows={packet.data_ledger?.ledger_rows ?? []} />
      <JsonDetails title="Factor Quant Hub packet" data={packet} />
    </PacketCard>
  );
}
