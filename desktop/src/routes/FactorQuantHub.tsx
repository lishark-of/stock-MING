import { useEffect, useState } from "react";
import type { EChartsOption } from "echarts";
import { getFactorQuantCache, postTask } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import EChartPanel from "../components/EChartPanel";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import TaskStatusPanel from "../components/TaskStatusPanel";

function toRows(items: unknown, bucket?: string): Array<Record<string, unknown>> {
  if (!Array.isArray(items)) return [];
  return items.map((item, index) => {
    if (item && typeof item === "object" && !Array.isArray(item)) {
      return bucket ? { bucket, ...(item as Record<string, unknown>) } : (item as Record<string, unknown>);
    }
    return { bucket: bucket ?? "item", index: index + 1, value: String(item ?? "") };
  });
}

function objectRows(record: Record<string, unknown>, labelKey = "field") {
  return Object.entries(record).map(([key, value]) => ({ [labelKey]: key, value: String(value) }));
}

export default function FactorQuantHub() {
  const [packet, setPacket] = useState<Record<string, any>>({});
  const [taskId, setTaskId] = useState("");

  const refreshCache = () => void getFactorQuantCache().then((res) => setPacket(res.data));

  useEffect(() => {
    refreshCache();
  }, []);

  const score = packet.score ?? {};
  const runtime = packet.runtime ?? {};
  const governance = packet.governance ?? {};
  const bridge = packet.next_session_bridge ?? {};
  const factorLibrary = packet.factor_library ?? {};
  const dataLedger = packet.data_ledger ?? {};
  const researchContext = packet.research_context ?? {};
  const linkedPackets = packet.linked_packets ?? {};
  const deepseek = packet.deepseek_explanation ?? {};
  const scoreRows = [
    ...toRows(score.support_factors, "support"),
    ...toRows(score.suppress_factors, "suppress"),
    ...toRows(score.neutral_factors, "neutral"),
    ...toRows(score.missing_factors, "missing"),
    ...toRows(score.conflict_factors, "conflict")
  ];
  const bridgeRows = objectRows(bridge, "next_session_bridge");
  const governanceRows = objectRows(governance, "governance");
  const riskRows = toRows(factorLibrary.risk_boundaries).map((row) => ({ risk_boundary: row.value ?? row.item ?? "", ...row }));
  const researchRows = Object.entries(researchContext).map(([key, value]) => ({
    context: key,
    ...(value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : { value: String(value ?? "") })
  }));
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
      <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
      <MetricGrid
        items={[
          { label: "mode", value: packet.mode ?? "cache_only" },
          { label: "runtime", value: runtime.status ?? "not_run" },
          { label: "coverage", value: runtime.coverage ?? 0 },
          { label: "missing", value: runtime.missing_count ?? 0 },
          { label: "score band", value: score.score_band ?? "missing" },
          { label: "core action", value: governance.allow_core_action === true ? "允许" : "禁止", tone: governance.allow_core_action === true ? "bad" : "good" },
          { label: "evidence preview", value: bridge.enters_evidence_effects === true ? "预览" : "关闭" },
          { label: "modify action", value: bridge.does_not_modify_action === false ? "会" : "不会", tone: bridge.does_not_modify_action === false ? "bad" : "good" },
          { label: "modify operation_zones", value: bridge.does_not_modify_operation_zones === false ? "会" : "不会", tone: bridge.does_not_modify_operation_zones === false ? "bad" : "good" },
          { label: "DeepSeek", value: deepseek.status ?? "not_called", tone: deepseek.called === true ? "warn" : "good" },
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
      <PacketCard title="DeepSeek 解释" subtitle="按钮门控；只整理已有结构化结果，不覆盖数值">
        <p>called: {String(Boolean(deepseek.called))}</p>
        <p>status: {String(deepseek.status ?? "not_called")}</p>
        <p>allowed: summary / support_notes / suppress_notes / conflict_notes / missing_data_notes / discipline_notes</p>
      </PacketCard>
      <h3>因子库</h3>
      <DataLineageTable rows={toRows(factorLibrary.factors)} />
      <h3>运行值</h3>
      <DataLineageTable rows={toRows(runtime.factor_values)} />
      <h3>评分桶</h3>
      <DataLineageTable rows={scoreRows} />
      <h3>治理边界</h3>
      <DataLineageTable rows={governanceRows} />
      <h3>次日图谱桥接</h3>
      <DataLineageTable rows={bridgeRows} />
      <h3>研究上下文</h3>
      <DataLineageTable rows={researchRows} />
      <h3>风险边界</h3>
      <DataLineageTable rows={riskRows} />
      <h3>数据血缘</h3>
      <DataLineageTable rows={dataLedger.ledger_rows ?? []} />
      <JsonDetails title="Factor Quant Hub packet" data={packet} />
    </PacketCard>
  );
}
