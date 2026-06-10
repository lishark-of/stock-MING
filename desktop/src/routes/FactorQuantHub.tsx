import { useEffect, useState } from "react";
import type { EChartsOption } from "echarts";
import { getFactorQuantCache, postTask } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import EChartPanel from "../components/EChartPanel";
import PacketCard from "../components/PacketCard";
import TaskStatusPanel from "../components/TaskStatusPanel";

export default function FactorQuantHub() {
  const [packet, setPacket] = useState<Record<string, any>>({});
  const [taskId, setTaskId] = useState("");

  useEffect(() => {
    void getFactorQuantCache().then((res) => setPacket(res.data));
  }, []);

  const score = packet.score ?? {};
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
      <EChartPanel option={option} />
      <h3>数据血缘</h3>
      <DataLineageTable rows={packet.data_ledger?.ledger_rows ?? []} />
    </PacketCard>
  );
}
