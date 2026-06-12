import { useEffect, useState } from "react";
import type { EChartsOption } from "echarts";
import { getFactorQuantCache, postTask, type TaskCreationEnvelope } from "../api/client";
import ChartSafetyStrip from "../components/ChartSafetyStrip";
import DataLineageTable from "../components/DataLineageTable";
import EChartPanel from "../components/EChartPanel";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PageStateBanner from "../components/PageStateBanner";
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshCache = () => {
    setLoading(true);
    setError("");
    void getFactorQuantCache().then((res) => {
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
      setPacket(res.data);
      if (!res.ok) setError(res.error ?? "factor_quant_cache_not_ok");
    }).catch((err) => {
      setError(err instanceof Error ? err.message : String(err));
    }).finally(() => setLoading(false));
  };
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
  const freshnessGate = packet.data_freshness_gate ?? {};
  const factorLibrary = packet.factor_library ?? {};
  const factorTests = packet.factor_tests ?? {};
  const factorTestQuality = factorTests.quality_summary ?? {};
  const dataLedger = packet.data_ledger ?? {};
  const researchContext = packet.research_context ?? {};
  const linkedPackets = packet.linked_packets ?? {};
  const deepseek = packet.deepseek_explanation ?? {};
  const scoreChart = packet.score_chart_payload ?? {};
  const scoreChartContract = scoreChart.chart_contract ?? {};
  const scoreChartRows = toRows(scoreChart.bucket_rows);
  const scoreChartContractRows = objectRows(scoreChartContract as Record<string, unknown>, "chart_contract");
  const factorTestRows = toRows(factorTests.items);
  const factorTestMetricRows = toRows(factorTests.metric_schema);
  const factorTestModeRows = toRows(factorTests.mode_plan);
  const factorTestStatusRows = objectRows((factorTests.status_counts ?? {}) as Record<string, unknown>, "factor_test_status");
  const factorTestQualityRows = objectRows(factorTestQuality as Record<string, unknown>, "quality_metric");
  const factorTestMetricGapRows = objectRows((factorTests.required_metric_gap_counts ?? factorTestQuality.required_metric_gap_counts ?? {}) as Record<string, unknown>, "metric_gap");
  const factorTestWindowRows = objectRows((factorTests.window_summary ?? factorTestQuality.window_summary ?? {}) as Record<string, unknown>, "window_metric");
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
  const freshnessRows = objectRows(freshnessGate, "freshness_gate");
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
  const empty = !loading && !error && (packet.status === "cache_missing" || !Object.keys(packet).length);

  return (
    <PacketCard title="2.0 多因子量化图谱" subtitle="只进入 evidence_effects 预览，不修改 action" status={String(packet.mode ?? "cache_only")}>
      <PageStateBanner
        loading={loading}
        error={error}
        empty={empty}
        emptyTitle="暂无多因子图谱缓存"
        emptyDetail="查看缓存不会刷新 Tushare；运行 light mode 必须手动点击任务按钮。"
      />
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
          { label: "freshness", value: freshnessGate.status ?? "unknown", tone: freshnessGate.usable_for_score === false ? "bad" : "good" },
          { label: "latest data", value: freshnessGate.latest_data_date ?? "unknown" },
          { label: "expected data", value: freshnessGate.expected_data_date ?? "unknown" },
          { label: "market phase", value: freshnessGate.market_phase ?? "unknown" },
          { label: "calendar", value: freshnessGate.calendar_source ?? "unknown", tone: freshnessGate.calendar_validated === true ? "good" : "warn" },
          { label: "max age days", value: freshnessGate.max_data_age_days ?? "unknown", tone: freshnessGate.usable_for_score === false ? "bad" : "neutral" },
          { label: "trading lag", value: freshnessGate.max_trading_day_lag ?? "unknown", tone: freshnessGate.usable_for_score === false ? "bad" : "neutral" },
          { label: "coverage", value: runtime.coverage ?? 0 },
          { label: "missing", value: runtime.missing_count ?? 0 },
          { label: "score band", value: score.score_band ?? "missing" },
          { label: "factor tests", value: factorTests.status ?? "scaffold_missing", tone: factorTests.status === "scaffold_ready" ? "warn" : "neutral" },
          { label: "test rows", value: factorTestRows.length },
          { label: "test quality", value: factorTestQuality.status ?? "scaffold_only", tone: factorTestQuality.status === "computed_light_metrics_ready" ? "good" : "warn" },
          { label: "research pass", value: factorTestQuality.research_pass_count ?? 0 },
          { label: "watchlist", value: factorTestQuality.watchlist_count ?? 0 },
          { label: "metric gaps", value: factorTestQuality.largest_required_metric_gap ?? 0, tone: Number(factorTestQuality.largest_required_metric_gap ?? 0) > 0 ? "warn" : "good" },
          { label: "test core action", value: factorTests.governance?.allow_core_action === true ? "允许" : "禁止", tone: factorTests.governance?.allow_core_action === true ? "bad" : "good" },
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
          { label: "DS model", value: deepseek.model_used ?? "not_called" },
          { label: "DS parse_failed", value: deepseek.parse_failed === true ? "是" : "否", tone: deepseek.parse_failed === true ? "bad" : "good" },
          { label: "DS token estimate", value: deepseek.token_estimate ?? 0 },
          { label: "snapshot", value: packet.source_snapshot_available === true, tone: packet.source_snapshot_available === true ? "good" : "warn" }
        ]}
      />
      <EChartPanel option={option} />
      <ChartSafetyStrip
        contract={scoreChartContract}
        source={scoreChart.source_packet ?? "factor_quant_cache"}
        extraItems={[
          { label: "改因子分数", value: scoreChartContract.does_not_modify_factor_score === false ? "可能" : "不会" }
        ]}
      />
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
        <p>model_used: {String(deepseek.model_used ?? "not_called")}</p>
        <p>input_hash: {String(deepseek.input_hash ?? "")}</p>
        <p>output_hash: {String(deepseek.output_hash ?? "")}</p>
        <p>parse_failed: {String(deepseek.parse_failed ?? false)}</p>
        <p>token_estimate: {String(deepseek.token_estimate ?? 0)}</p>
        <p>allowed: summary / support_notes / suppress_notes / conflict_notes / missing_data_notes / discipline_notes</p>
      </PacketCard>
      <h3>因子库</h3>
      <DataLineageTable rows={toRows(factorLibrary.factors)} />
      <h3>运行值</h3>
      <DataLineageTable rows={toRows(runtime.factor_values)} />
      <h3>Factor Test Lab</h3>
      <p className="risk-note">当前为研究指标 scaffold：IC / Rank IC / ICIR / 分组收益 / 换手 / 成本后收益尚未代表已验证交易信号。</p>
      <DataLineageTable rows={factorTestRows} />
      <h3>Factor Test 指标 schema</h3>
      <DataLineageTable rows={factorTestMetricRows} />
      <h3>Factor Test 阶段计划</h3>
      <DataLineageTable rows={factorTestModeRows} />
      <h3>Factor Test 状态分布</h3>
      <DataLineageTable rows={factorTestStatusRows} />
      <h3>Factor Test 质量摘要</h3>
      <DataLineageTable rows={factorTestQualityRows} />
      <h3>Factor Test 必需指标缺口</h3>
      <DataLineageTable rows={factorTestMetricGapRows} />
      <h3>Factor Test 样本窗口</h3>
      <DataLineageTable rows={factorTestWindowRows} />
      <h3>评分桶</h3>
      <DataLineageTable rows={scoreRows} />
      <h3>治理边界</h3>
      <DataLineageTable rows={governanceRows} />
      <h3>数据时效门控</h3>
      <p className="risk-note">stale / expired 数据只允许审计展示，不进入 composite score、强 support 或交易解释。</p>
      <DataLineageTable rows={freshnessRows} />
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
