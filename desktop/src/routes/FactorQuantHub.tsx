import { useEffect, useState } from "react";
import type { EChartsOption } from "echarts";
import { getFactorQuantCache, postTask, type TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import EChartPanel from "../components/EChartPanel";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
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
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<unknown>>([]);
  const [taskId, setTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);

  const refreshCache = () =>
    void getFactorQuantCache().then((res) => {
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
      setPacket(res.data);
    });
  const launchTask = (path: string) =>
    void postTask(path).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });

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
  const scoreChart = packet.score_chart_payload ?? {};
  const scoreChartContract = scoreChart.chart_contract ?? {};
  const scoreChartRows = toRows(scoreChart.bucket_rows);
  const scoreChartContractRows = objectRows(scoreChartContract as Record<string, unknown>, "chart_contract");
  const payloadCallLedger = (packet.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((packet.warnings as Array<unknown> | undefined) ?? []);
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
    xAxis: { type: "category", data: scoreChart.x_axis_labels ?? ["支持", "压制", "中性", "缺失", "冲突"] },
    yAxis: { type: "value" },
    series: Array.isArray(scoreChart.series) ? scoreChart.series : [{ type: "bar", data: [] }]
  };

  return (
    <PacketCard title="2.0 多因子量化图谱" subtitle="只进入 evidence_effects 预览，不修改 action" status={String(packet.mode ?? "cache_only")}>
      <div className="actions">
        <button onClick={refreshCache}>查看缓存</button>
        <button onClick={() => launchTask("/api/factor-quant/refresh-data")}>刷新数据</button>
        <button onClick={() => launchTask("/api/factor-quant/run-light")}>运行计算</button>
        <button onClick={() => launchTask("/api/factor-quant/deepseek-explain")}>DeepSeek 整理</button>
      </div>
      <p className="risk-note">多因子量化不是交易建议；不改价格、持仓、operation_zones 或 strategy action。</p>
      <TaskLaunchReceipt receipt={taskReceipt} />
      <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
      <MetricGrid
        items={[
          { label: "mode", value: packet.mode ?? "cache_only" },
          { label: "runtime", value: runtime.status ?? "not_run" },
          { label: "coverage", value: runtime.coverage ?? 0 },
          { label: "missing", value: runtime.missing_count ?? 0 },
          { label: "score band", value: score.score_band ?? "missing" },
          { label: "score chart", value: scoreChartContract.schema_version ?? "missing", tone: scoreChartContract.schema_version ? "good" : "warn" },
          { label: "chart external", value: scoreChartContract.external_calls_triggered === true ? "存在" : "无", tone: scoreChartContract.external_calls_triggered === true ? "bad" : "good" },
          { label: "chart Tushare", value: scoreChartContract.tushare_called === true ? "调用" : "不调用", tone: scoreChartContract.tushare_called === true ? "bad" : "good" },
          { label: "chart DeepSeek", value: scoreChartContract.deepseek_called === true ? "调用" : "不调用", tone: scoreChartContract.deepseek_called === true ? "bad" : "good" },
          { label: "chart GitHub", value: scoreChartContract.github_called === true ? "调用" : "不调用", tone: scoreChartContract.github_called === true ? "bad" : "good" },
          { label: "chart real trade", value: scoreChartContract.does_not_execute_trades === false ? "可能" : "禁止", tone: scoreChartContract.does_not_execute_trades === false ? "bad" : "good" },
          { label: "frontend_computes_trade_action", value: scoreChartContract.frontend_computes_trade_action === true ? "会" : "不会", tone: scoreChartContract.frontend_computes_trade_action === true ? "bad" : "good" },
          { label: "core action", value: governance.allow_core_action === true ? "允许" : "禁止", tone: governance.allow_core_action === true ? "bad" : "good" },
          { label: "evidence preview", value: bridge.enters_evidence_effects === true ? "预览" : "关闭" },
          { label: "modify action", value: bridge.does_not_modify_action === false ? "会" : "不会", tone: bridge.does_not_modify_action === false ? "bad" : "good" },
          { label: "modify operation_zones", value: bridge.does_not_modify_operation_zones === false ? "会" : "不会", tone: bridge.does_not_modify_operation_zones === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length },
          { label: "DeepSeek", value: deepseek.status ?? "not_called", tone: deepseek.called === true ? "warn" : "good" },
          { label: "snapshot", value: packet.source_snapshot_available === true, tone: packet.source_snapshot_available === true ? "good" : "warn" }
        ]}
      />
      <EChartPanel option={option} />
      <div className="chart-safety-strip">
        <span>来源：{String(scoreChartContract.source_packet ?? scoreChart.source_packet ?? "factor_quant_cache")}</span>
        <span>外部调用：{scoreChartContract.external_calls_triggered === true ? "存在" : "无"}</span>
        <span>Tushare：{scoreChartContract.tushare_called === true ? "已调用" : "未调用"}</span>
        <span>DeepSeek：{scoreChartContract.deepseek_called === true ? "已调用" : "未调用"}</span>
        <span>GitHub：{scoreChartContract.github_called === true ? "已调用" : "未调用"}</span>
        <span>真实交易：{scoreChartContract.does_not_execute_trades === false ? "可能" : "禁止"}</span>
        <span>前端算交易动作：{scoreChartContract.frontend_computes_trade_action === true ? "是" : "否"}</span>
        <span>改 action：{scoreChartContract.does_not_modify_action === false ? "可能" : "不会"}</span>
        <span>改操作区：{scoreChartContract.does_not_modify_operation_zones === false ? "可能" : "不会"}</span>
        <span>改因子分数：{scoreChartContract.does_not_modify_factor_score === false ? "可能" : "不会"}</span>
      </div>
      <h3>评分图表数据合同</h3>
      <DataLineageTable rows={scoreChartContractRows} />
      <h3>评分图表 buckets</h3>
      <DataLineageTable rows={scoreChartRows} />
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
      <h3>GET cache envelope call_ledger</h3>
      <DataLineageTable rows={cacheCallLedger} />
      <h3>GET cache envelope warnings</h3>
      <DataLineageTable rows={toRows(cacheWarnings, "warning")} />
      <JsonDetails title="Factor Quant Hub packet" data={packet} />
    </PacketCard>
  );
}
