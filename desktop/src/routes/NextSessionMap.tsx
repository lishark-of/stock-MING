import { useEffect, useState } from "react";
import { getNextSessionCache, postTask, type TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import NextSessionChart from "../components/NextSessionChart";
import PageStateBanner from "../components/PageStateBanner";
import PacketCard from "../components/PacketCard";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

function rowsFromArray(items: unknown, fallbackKey = "value"): Array<Record<string, unknown>> {
  if (!Array.isArray(items)) return [];
  return items.map((item, index) => {
    if (item && typeof item === "object" && !Array.isArray(item)) {
      return item as Record<string, unknown>;
    }
    return { index: index + 1, [fallbackKey]: String(item ?? "") };
  });
}

function isCacheMissingError(message: string | null | undefined): boolean {
  return typeof message === "string" && message.startsWith("cache_missing:");
}

export default function NextSessionMap() {
  const [packet, setPacket] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<unknown>>([]);
  const [cacheMissingMessage, setCacheMissingMessage] = useState("");
  const [taskId, setTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [browserQaReceipt, setBrowserQaReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [streamlitParityReceipt, setStreamlitParityReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [productionPromotionReceipt, setProductionPromotionReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshCache = () => {
    setLoading(true);
    setError("");
    setCacheMissingMessage("");
    void getNextSessionCache().then((res) => {
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
      setPacket(res.data);
      if (!res.ok) {
        if (isCacheMissingError(res.error)) {
          setCacheMissingMessage(res.error ?? "cache_missing: 暂无已缓存次日操作图谱。");
          setPacket({ ...res.data, status: "cache_missing", summary: res.error });
          return;
        }
        setError(res.error ?? "next_session_cache_not_ok");
      }
    }).catch((err) => {
      setError(err instanceof Error ? err.message : String(err));
    }).finally(() => setLoading(false));
  };
  const launchTask = () =>
    void postTask("/api/next-session/generate").then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const reviewBrowserQa = () =>
    void postTask("/api/next-session/browser-qa-review", { review_scope: "next_session_browser_qa_local_artifact" }).then((res) => {
      setBrowserQaReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const reviewStreamlitParity = () =>
    void postTask("/api/next-session/streamlit-parity-review", { review_scope: "next_session_same_packet_no_loss" }).then((res) => {
      setStreamlitParityReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const reviewProductionPromotion = () =>
    void postTask("/api/next-session/production-promotion-review", { review_scope: "next_session_local_promotion_blocker_review" }).then((res) => {
      setProductionPromotionReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });

  useEffect(() => {
    refreshCache();
  }, []);

  const legacy = packet.legacy_projection_cache as Record<string, unknown> | undefined;
  const chartPayload = packet.chart_payload as Record<string, unknown> | undefined;
  const chartSummary = (packet.chart_summary as Record<string, unknown> | undefined) ?? (chartPayload?.chart_summary as Record<string, unknown> | undefined) ?? {};
  const chartContract = chartPayload?.chart_contract as Record<string, unknown> | undefined;
  const chartContractCounts = chartContract?.series_counts as Record<string, unknown> | undefined;
  const chartMaturity = (chartPayload?.chart_maturity as Record<string, unknown> | undefined) ?? {};
  const interactionReadinessAudit = (chartPayload?.interaction_readiness_audit as Record<string, unknown> | undefined) ?? {};
  const replacementActivation = (packet.next_session_replacement_activation_receipt as Record<string, unknown> | undefined) ?? {};
  const replacementActivationRows = rowsFromArray(packet.next_session_replacement_activation_rows);
  const browserQaRunbook = (packet.next_session_browser_qa_runbook_contract as Record<string, unknown> | undefined) ?? {};
  const browserQaRunbookRows = rowsFromArray(packet.next_session_browser_qa_runbook_rows);
  const browserQaMatrixRows = rowsFromArray(packet.next_session_browser_qa_matrix_rows);
  const browserQaEvidence = (packet.next_session_browser_qa_evidence_summary as Record<string, unknown> | undefined) ?? {};
  const browserQaEvidenceRows = rowsFromArray(packet.next_session_browser_qa_evidence_rows);
  const browserQaReview = (packet.next_session_browser_qa_review_contract as Record<string, unknown> | undefined) ?? {};
  const browserQaReviewRows = rowsFromArray(packet.next_session_browser_qa_review_rows);
  const streamlitParityReview = (packet.next_session_streamlit_parity_review_contract as Record<string, unknown> | undefined) ?? {};
  const streamlitParityReviewRows = rowsFromArray(packet.next_session_streamlit_parity_review_rows);
  const productionPromotionReview = (packet.next_session_production_promotion_review_contract as Record<string, unknown> | undefined) ?? {};
  const productionPromotionReviewRows = rowsFromArray(packet.next_session_production_promotion_review_rows);
  const durableEvidenceRecipe = (packet.next_session_durable_evidence_recipe as Record<string, unknown> | undefined) ?? {};
  const durableEvidenceRows = rowsFromArray(packet.next_session_durable_evidence_rows);
  const productionStageScope = (packet.next_session_production_stage_scope_manifest as Record<string, unknown> | undefined) ?? {};
  const productionStageScopeRows = rowsFromArray(packet.next_session_production_stage_scope_rows);
  const latestCloseAnchor = (chartPayload?.latest_close_anchor as Record<string, unknown> | undefined) ?? {};
  const dataTrustSummary = (chartPayload?.data_trust_summary as Record<string, unknown> | undefined) ?? {};
  const positionConflict = (chartPayload?.position_conflict as Record<string, unknown> | undefined) ?? {};
  const historicalRows = rowsFromArray(chartPayload?.historical_points).slice(0, 20);
  const referenceRows = rowsFromArray(chartPayload?.reference_lines);
  const operationRows = rowsFromArray(chartPayload?.operation_zones);
  const referenceLineRows = rowsFromArray(chartPayload?.reference_line_rows);
  const zoneInteractionRows = rowsFromArray(chartPayload?.zone_interaction_rows);
  const interactionReadinessRows = rowsFromArray(chartPayload?.interaction_readiness_rows);
  const scenarioAnchorRows = rowsFromArray(chartPayload?.scenario_anchor_rows);
  const dataTrustRows = rowsFromArray(dataTrustSummary.facts);
  const humanTrustRows = rowsFromArray(dataTrustSummary.human_summary, "summary");
  const positionConflictRows = rowsFromArray(positionConflict.conflict_flags, "conflict_flag");
  const warningRows = rowsFromArray(chartPayload?.warnings, "warning");
  const chartContractRows = chartContract
    ? [
        { field: "schema_version", value: chartContract.schema_version, note: "ECharts payload 合同版本" },
        { field: "renderer", value: chartContract.renderer, note: "前端渲染器" },
        { field: "cache_only", value: String(chartContract.cache_only === true), note: "只读 cache 数据" },
        { field: "external_calls_triggered", value: String(chartContract.external_calls_triggered === true), note: "必须为 false" },
        { field: "tushare_called", value: String(chartContract.tushare_called === true), note: "必须为 false" },
        { field: "deepseek_called", value: String(chartContract.deepseek_called === true), note: "必须为 false" },
        { field: "github_called", value: String(chartContract.github_called === true), note: "必须为 false" },
        { field: "does_not_execute_trades", value: String(chartContract.does_not_execute_trades !== false), note: "必须为 true" },
        { field: "frontend_computes_trade_action", value: String(chartContract.frontend_computes_trade_action === true), note: "必须为 false" },
        { field: "does_not_modify_action", value: String(chartContract.does_not_modify_action !== false), note: "不得改 strategy action" },
        { field: "does_not_modify_operation_zones", value: String(chartContract.does_not_modify_operation_zones !== false), note: "不得改 operation_zones" },
        { field: "historical_points", value: chartContractCounts?.historical_points ?? 0, note: "历史 close 点数" },
        { field: "scenario_series", value: chartContractCounts?.scenario_series ?? 0, note: "情景路径数量" },
        { field: "reference_lines", value: chartContractCounts?.reference_lines ?? 0, note: "参考线数量" },
        { field: "operation_zones", value: chartContractCounts?.operation_zones ?? 0, note: "操作区数量" }
      ]
    : [];
  const payloadCallLedger = (packet.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((packet.warnings as Array<unknown> | undefined) ?? []);
  const scenarioRows = rowsFromArray(chartPayload?.scenario_series).map((row) => ({
    scenario_key: row.scenario_key ?? row.scenario_name,
    scenario_name: row.scenario_name,
    probability: row.probability,
    point_count: Array.isArray(row.points) ? row.points.length : 0,
    source: row.source,
    risk_note: row.risk_note
  }));
  const cacheBoundaryRows = [
    { boundary: "GET /api/next-session/cache", value: "cache_only", note: "只读缓存，不触发 Tushare、DeepSeek 或 GitHub。" },
    { boundary: "POST /api/next-session/generate", value: "button_gated_task", note: "手动任务才可能生成/刷新图谱。" },
    { boundary: "does_not_modify_action", value: String(packet.does_not_modify_action !== false), note: "前端只读，不改 strategy action。" },
    { boundary: "does_not_modify_operation_zones", value: String(packet.does_not_modify_operation_zones !== false), note: "前端只读，不改 operation_zones。" },
    { boundary: "is_exact_next_session_packet", value: String(chartPayload?.is_exact_next_session_packet === true), note: "非精确 packet 时只显示 legacy/cache 投影。" },
    { boundary: "uses_real_daily_close", value: String(chartPayload?.uses_real_daily_close === true), note: "未验证真实 close 时必须展示风险提示。" }
  ];
  const empty = !loading && !error && (packet.status === "cache_missing" || !Object.keys(packet).length);

  return (
    <PacketCard title="次日操作图谱" subtitle="缓存查看不触发外部刷新" status={String(packet.status ?? "cache")}>
      <PageStateBanner
        loading={loading}
        error={error}
        empty={empty}
        emptyTitle="暂无已缓存次日操作图谱"
        emptyDetail={cacheMissingMessage || "请在允许按钮任务的情况下点击生成任务；查看缓存不会触发 Tushare。"}
      />
      <div className="actions">
        <button onClick={refreshCache}>查看缓存</button>
        <button onClick={launchTask}>生成任务</button>
        <button onClick={reviewBrowserQa}>审查本地 QA</button>
        <button onClick={reviewStreamlitParity}>审查信号/能力 parity</button>
        <button onClick={reviewProductionPromotion}>审查 promotion</button>
      </div>
      <TaskLaunchReceipt receipt={taskReceipt} />
      <TaskLaunchReceipt receipt={browserQaReceipt} />
      <TaskLaunchReceipt receipt={streamlitParityReceipt} />
      <TaskLaunchReceipt receipt={productionPromotionReceipt} />
      <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
      <MetricGrid
        items={[
          { label: "状态", value: String(packet.status ?? "cache") },
          { label: "cache source", value: String(packet.cache_source ?? "--") },
          { label: "本地快照", value: Boolean(packet.source_snapshot_available), tone: packet.source_snapshot_available ? "good" : "warn" },
          { label: "旧 projection", value: Boolean(legacy?.available), tone: legacy?.available ? "warn" : "neutral" },
          { label: "精确图谱", value: chartSummary.is_exact_next_session_packet === true, tone: chartSummary.is_exact_next_session_packet === true ? "good" : "warn" },
          { label: "真实 close", value: chartSummary.uses_real_daily_close === true, tone: chartSummary.uses_real_daily_close === true ? "good" : "warn" },
          { label: "可绘制", value: chartSummary.has_drawable_data === true, tone: chartSummary.has_drawable_data === true ? "good" : "warn" },
          { label: "图表合同", value: String(chartContract?.schema_version ?? "missing"), tone: chartContract ? "good" : "warn" },
          { label: "情景路径", value: chartSummary.scenario_series_count as number | undefined },
          { label: "参考线", value: chartSummary.reference_line_count as number | undefined },
          { label: "操作区", value: chartSummary.operation_zone_count as number | undefined },
          { label: "历史点", value: chartSummary.historical_point_count as number | undefined },
          { label: "成熟度", value: String(chartMaturity.status ?? chartSummary.maturity_status ?? "partial"), tone: chartMaturity.status === "ready" ? "good" : "warn" },
          { label: "交互审计", value: String(interactionReadinessAudit.status ?? chartSummary.interaction_readiness_status ?? "missing"), tone: interactionReadinessAudit.status === "interaction_blocked" ? "bad" : "warn" },
          { label: "交互阻断", value: Number(interactionReadinessAudit.blocking_count ?? chartSummary.interaction_blocking_count ?? 0), tone: Number(interactionReadinessAudit.blocking_count ?? chartSummary.interaction_blocking_count ?? 0) ? "bad" : "good" },
          { label: "信号/能力 parity", value: interactionReadinessAudit.streamlit_parity_complete === true ? "完成" : "待验收", tone: interactionReadinessAudit.streamlit_parity_complete === true ? "good" : "warn" },
          { label: "替代激活收据", value: String(replacementActivation.status ?? "missing"), tone: replacementActivation.local_activation_receipt_ready === true ? "good" : "warn" },
          { label: "替代阻断", value: Number(replacementActivation.production_blocker_count ?? 0), tone: Number(replacementActivation.production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "缺失证据", value: Number(replacementActivation.missing_evidence_count ?? 0), tone: Number(replacementActivation.missing_evidence_count ?? 0) > 0 ? "warn" : "good" },
          { label: "QA runbook", value: String(browserQaRunbook.status ?? "missing"), tone: browserQaRunbook.local_runbook_ready === true ? "good" : "warn" },
          { label: "QA evidence", value: String(browserQaEvidence.status ?? "missing"), tone: browserQaEvidence.next_browser_qa_evidence_ready === true ? "good" : "warn" },
          { label: "QA review", value: String(browserQaReview.status ?? "missing"), tone: browserQaReview.local_browser_qa_review_ready === true ? "good" : "warn" },
          { label: "QA 阻断", value: Number(browserQaReview.blocking_review_count ?? 0), tone: Number(browserQaReview.blocking_review_count ?? 0) > 0 ? "warn" : "good" },
          { label: "parity review", value: String(streamlitParityReview.status ?? "missing"), tone: streamlitParityReview.local_streamlit_parity_review_ready === true ? "good" : "warn" },
          { label: "parity 阻断", value: Number(streamlitParityReview.blocking_review_count ?? 0), tone: Number(streamlitParityReview.blocking_review_count ?? 0) > 0 ? "warn" : "good" },
          { label: "durable evidence", value: String(durableEvidenceRecipe.status ?? "missing"), tone: durableEvidenceRecipe.local_recipe_ready === true ? "good" : "warn" },
          { label: "durable 阻断", value: Number(durableEvidenceRecipe.durable_evidence_blocker_count ?? 0), tone: Number(durableEvidenceRecipe.durable_evidence_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "promotion review", value: String(productionPromotionReview.status ?? "missing"), tone: productionPromotionReview.local_production_promotion_review_ready === true ? "good" : "warn" },
          { label: "promotion 阻断", value: Number(productionPromotionReview.production_blocker_count ?? 0), tone: Number(productionPromotionReview.production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "阶段清单", value: String(productionStageScope.status ?? "missing"), tone: productionStageScope.local_manifest_ready === true ? "good" : "warn" },
          { label: "阶段 direct evidence", value: Number(productionStageScope.direct_evidence_stage_count ?? 0), tone: Number(productionStageScope.direct_evidence_stage_count ?? 0) > 0 ? "good" : "warn" },
          { label: "阶段 pending", value: Number(productionStageScope.pending_stage_count ?? 0), tone: Number(productionStageScope.pending_stage_count ?? 0) > 0 ? "warn" : "good" },
          { label: "路径锚定", value: `${String(chartMaturity.scenario_anchored_count ?? chartSummary.scenario_anchored_count ?? 0)}/${String(chartMaturity.scenario_anchor_count ?? 0)}` },
          { label: "最新 close", value: String(latestCloseAnchor.price ?? "--") },
          { label: "持仓冲突", value: positionConflict.has_conflict === true ? "有" : "无", tone: positionConflict.has_conflict === true ? "bad" : "good" },
          { label: "DeepSeek", value: String(chartPayload?.deepseek_status ?? chartSummary.deepseek_status ?? "not_called"), tone: chartPayload?.deepseek_status === "success" ? "good" : "neutral" },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length },
          { label: "修改 action", value: packet.does_not_modify_action === false ? "会" : "不会", tone: packet.does_not_modify_action === false ? "bad" : "good" },
          { label: "修改 operation_zones", value: packet.does_not_modify_operation_zones === false ? "会" : "不会", tone: packet.does_not_modify_operation_zones === false ? "bad" : "good" }
        ]}
      />
      <p className="risk-note">{String(packet.summary ?? "当前只读取 cache；无缓存时不会触发 Tushare。")}</p>
      <NextSessionChart payload={chartPayload} />
      <h3>ECharts 图表摘要</h3>
      <DataLineageTable rows={[chartSummary]} />
      <h3>ECharts 交互成熟度审计</h3>
      <DataLineageTable rows={[interactionReadinessAudit]} />
      <DataLineageTable rows={interactionReadinessRows} />
      <h3>ECharts 生产替代激活收据</h3>
      <p className="risk-note">next_session_replacement_activation_receipt 只把 legacy signal/capability parity、浏览器视觉 QA、性能 trace、durable evidence 和只读边界串成下一步清单；它不运行浏览器、不调用 provider/model、不证明生产替代完成，也不代表复制旧 Streamlit 图表 UI。</p>
      <p>allowed_next_step: {String(replacementActivation.allowed_next_step ?? "explicit_signal_capability_parity_browser_visual_performance_review_then_replacement_promotion")}</p>
      <p>production_replacement_complete: {String(replacementActivation.production_replacement_complete === true)}；browser_visual_qa_done: {String(replacementActivation.browser_visual_qa_done === true)}；browser_performance_trace_done: {String(replacementActivation.browser_performance_trace_done === true)}</p>
      <DataLineageTable rows={[replacementActivation]} />
      <DataLineageTable rows={replacementActivationRows} />
      <h3>ECharts 本地浏览器 QA</h3>
      <p className="risk-note">next_session_browser_qa_* 只读取 ignored 本地 runner 报告并支持按钮审查；它不打开浏览器、不提交截图/报告、不替代 legacy signal/capability parity、不证明生产替代完成。</p>
      <p>route: {String(browserQaRunbook.next_route ?? "#next")}；artifact_root: {String(browserQaRunbook.artifact_root ?? ".stock_ming_3/motion_qa")}</p>
      <p>local_browser_qa_review_ready: {String(browserQaReview.local_browser_qa_review_ready === true)}；production_replacement_complete: {String(browserQaReview.production_replacement_complete === true)}；streamlit_parity_complete: {String(browserQaReview.streamlit_parity_complete === true)}</p>
      <DataLineageTable rows={[browserQaRunbook]} />
      <DataLineageTable rows={browserQaRunbookRows} />
      <DataLineageTable rows={browserQaMatrixRows} />
      <h3>ECharts 本地 QA 证据摘要</h3>
      <DataLineageTable rows={[browserQaEvidence]} />
      <DataLineageTable rows={browserQaEvidenceRows} />
      <h3>ECharts 本地 QA 审查</h3>
      <DataLineageTable rows={[browserQaReview]} />
      <DataLineageTable rows={browserQaReviewRows} />
      <h3>ECharts same-packet signal/capability parity 审查</h3>
      <p className="risk-note">next_session signal/capability parity review 只审查本地同包 no-feature-loss 合同；它不打开 Streamlit、不运行浏览器、不移除 fallback、不证明生产替代完成。</p>
      <p>local_signal_capability_parity_review_ready: {String(streamlitParityReview.local_streamlit_parity_review_ready === true)}；same_packet_no_loss_review_ready: {String(streamlitParityReview.same_packet_no_loss_review_ready === true)}；signal_capability_parity_complete: {String(streamlitParityReview.streamlit_parity_complete === true)}</p>
      <DataLineageTable rows={[streamlitParityReview]} />
      <DataLineageTable rows={streamlitParityReviewRows} />
      <h3>ECharts durable evidence recipe</h3>
      <p className="risk-note">next_session_durable_evidence_recipe 只固定生产替代前的直接证据清单；它不打开浏览器、不启动服务、不调用 provider/model、不证明 legacy signal/capability parity、不证明生产替代完成。</p>
      <p>scope: {String(durableEvidenceRecipe.scope ?? "local_next_session_durable_evidence_recipe_no_browser_no_provider")}</p>
      <p>local_recipe_ready: {String(durableEvidenceRecipe.local_recipe_ready === true)}；durable_evidence_complete: {String(durableEvidenceRecipe.durable_evidence_complete === true)}；durable_promotion_ready: {String(durableEvidenceRecipe.durable_promotion_ready === true)}</p>
      <p>allowed_next_step: {String(durableEvidenceRecipe.allowed_next_step ?? "run_same_packet_signal_capability_parity_then_browser_visual_performance_then_durable_promotion_review")}</p>
      <p>not_allowed_next_steps: {Array.isArray(durableEvidenceRecipe.not_allowed_next_steps) ? durableEvidenceRecipe.not_allowed_next_steps.join(" / ") : "local browser artifact as durable evidence / interaction readiness as parity / provider calls from render / frontend action computation"}</p>
      <DataLineageTable rows={[durableEvidenceRecipe]} />
      <DataLineageTable rows={durableEvidenceRows} />
      <h3>ECharts production promotion review</h3>
      <p className="risk-note">next_session_production_promotion_review 只审查本地 promotion 阻断状态；它不调用 provider/model/GitHub、不移除 fallback、不证明生产替代完成。</p>
      <p>local_production_promotion_review_ready: {String(productionPromotionReview.local_production_promotion_review_ready === true)}；ready_to_mark_production_replacement_complete: {String(productionPromotionReview.ready_to_mark_production_replacement_complete === true)}；production_replacement_complete: {String(productionPromotionReview.production_replacement_complete === true)}</p>
      <DataLineageTable rows={[productionPromotionReview]} />
      <DataLineageTable rows={productionPromotionReviewRows} />
      <h3>ECharts production stage scope</h3>
      <p className="risk-note">next_session_production_stage_scope_manifest 只把本地阶段证据和剩余阻断展示到 cache/UI；它不运行浏览器、不调用 provider/model/GitHub、不计算 action、不证明生产替代完成。</p>
      <p>scope: {String(productionStageScope.scope ?? "next_session_production_replacement_stage_scope_manifest")}</p>
      <p>direct_evidence_stage_count: {String(productionStageScope.direct_evidence_stage_count ?? 0)}；pending_stage_count: {String(productionStageScope.pending_stage_count ?? 0)}；production_replacement_complete: {String(productionStageScope.production_replacement_complete === true)}</p>
      <p>direct_evidence_stage_keys: {Array.isArray(productionStageScope.direct_evidence_stage_keys) ? productionStageScope.direct_evidence_stage_keys.join(" / ") : ""}</p>
      <DataLineageTable rows={[productionStageScope]} />
      <DataLineageTable rows={productionStageScopeRows} />
      <h3>ECharts 图表数据合同</h3>
      <DataLineageTable rows={chartContractRows} />
      <h3>缓存边界</h3>
      <DataLineageTable rows={cacheBoundaryRows} />
      <h3>GET cache envelope call_ledger</h3>
      <DataLineageTable rows={cacheCallLedger} />
      <h3>GET cache envelope warnings</h3>
      <DataLineageTable rows={rowsFromArray(cacheWarnings, "warning")} />
      <h3>情景路径</h3>
      <DataLineageTable rows={scenarioRows} />
      <h3>路径锚定校验</h3>
      <DataLineageTable rows={scenarioAnchorRows} />
      <h3>参考线</h3>
      <DataLineageTable rows={referenceRows} />
      <h3>参考线来源</h3>
      <DataLineageTable rows={referenceLineRows} />
      <h3>操作区</h3>
      <DataLineageTable rows={operationRows} />
      <h3>操作区点击说明</h3>
      <DataLineageTable rows={zoneInteractionRows} />
      <h3>数据可信度</h3>
      <DataLineageTable rows={dataTrustRows} />
      <DataLineageTable rows={humanTrustRows} />
      <h3>持仓冲突提示</h3>
      <DataLineageTable rows={positionConflictRows} />
      <h3>历史 close 样例</h3>
      <DataLineageTable rows={historicalRows} />
      <h3>图表风险提示</h3>
      <DataLineageTable rows={warningRows} />
      {legacy?.available ? <JsonDetails title="legacy projection 摘要" data={legacy} /> : null}
      <JsonDetails title="次日图谱 cache packet" data={packet} />
    </PacketCard>
  );
}
