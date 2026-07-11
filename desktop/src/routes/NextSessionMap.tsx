import { useEffect, useState } from "react";
import { getCandidateRadarCache, getNextSessionCache, postTask, type TaskCreationEnvelope } from "../api/client";
import { getTasks, type TaskStatusIndex } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid, { type MetricItem } from "../components/MetricGrid";
import NextSessionChart from "../components/NextSessionChart";
import PacketCard from "../components/PacketCard";
import StateClarityRail from "../components/StateClarityRail";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

const CANDIDATE_CONFIRM_HREF = "#candidates/candidate-radar-search-quant-projection";
const DATA_CAPABILITY_HREF = "#dataCapability";

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

function ordinaryNextText(value: unknown, fallback = "--"): string {
  if (value === null || value === undefined || value === "") return fallback;
  const text = typeof value === "boolean" ? (value ? "是" : "否") : String(value);
  return text
    .replace(/Tushare 数据卡/g, "数据链状态")
    .replace(/Tushare-first/g, "真实数据链")
    .replace(/Tushare light/g, "轻量数据接口")
    .replace(/Tushare/g, "真实数据")
    .replace(/DeepSeek/g, "模型解释")
    .replace(/GitHub/g, "远端检查")
    .replace(/CandidateRadar/g, "下一票雷达")
    .replace(/\bFactor\b/g, "量化推演")
    .replace(/call_ledger/g, "数据记录")
    .replace(/ledger/g, "数据记录")
    .replace(/packet/g, "本地结果包")
    .replace(/cache/g, "本地缓存")
    .replace(/POST task/g, "手动后台流程")
    .replace(/task_readback/g, "任务回放")
    .replace(/task/g, "后台流程")
    .replace(/scope hash/g, "范围校验")
    .replace(/safe payload/g, "安全请求范围")
    .replace(/payload/g, "请求范围")
    .replace(/provider\/model\/worker/g, "数据接口、模型和后台执行器")
    .replace(/CandidateRadar cache/g, "下一票雷达本地回放")
    .replace(/GET tasks/g, "本地进度")
    .replace(/sqlite_meta/g, "本地结果")
    .replace(/retained signal\/capability coverage/g, "保留信号和能力覆盖")
    .replace(/real close/g, "真实收口")
    .replace(/provider/g, "数据接口")
    .replace(/model/g, "模型")
    .replace(/worker/g, "后台执行器")
    .replace(/strategy action/g, "交易动作")
    .replace(/operation_zones/g, "操作区")
    .replace(/governed executor/g, "受控解释流程")
    .replace(/React render/g, "页面渲染")
    .replace(/GET cache/g, "本地缓存读取")
    .replace(/LTG-\d+/g, "长期目标")
    .replace(/production replacement complete/g, "生产替代验收完成")
    .replace(/degraded/g, "待补")
    .replace(/pending/g, "待补")
    .replace(/真实数据链 数据卡/g, "数据链卡")
    .replace(/真实数据 数据卡/g, "数据卡")
    .replace(/真实数据 数据凭证/g, "真实数据凭证")
    .replace(/真实数据链 账本/g, "真实数据记录")
    .replace(/真实数据链 结论/g, "真实数据链结论")
    .replace(/本地 数据记录/g, "本地数据记录")
    .replace(/本地 本地缓存/g, "本地缓存")
    .replace(/数据接口 后台流程/g, "数据后台流程")
    .replace(/按钮门控 数据后台流程/g, "确认后数据回写")
    .replace(/确认后数据回写 回写/g, "确认后数据回写")
    .replace(/确认后数据回写 数据记录/g, "确认后数据回写")
    .replace(/candidate_radar_p3_handoff_readonly/g, "下一票雷达回放")
    .replace(/legacy\/本地缓存 投影/g, "旧缓存回放")
    .replace(/降级预览/g, "待补预览")
    .replace(/真实 close/g, "真实收口")
    .replace(/GET 后台流程s/g, "本地进度")
    .replace(/下一票雷达 本地缓存/g, "下一票雷达本地回放")
    .replace(/不调用 真实数据\/模型解释\/远端检查/g, "不刷新外部数据或模型")
    .replace(/证据缺口/g, "缺口原因")
    .replace(/证据来源/g, "只读来源")
    .replace(/浏览器视觉 QA/g, "图谱显示检查")
    .replace(/证据待确认/g, "仍待确认")
    .replace(/生产替代证据/g, "完整验收材料")
    .replace(/生产替代/g, "完整替代")
    .replace(/保留信号和能力覆盖/g, "图谱覆盖")
    .replace(/真实收口/g, "最终复核");
}

function ordinaryNextMetricItems(items: MetricItem[]): MetricItem[] {
  return items.map((item) => ({
    ...item,
    label: ordinaryNextText(item.label),
    value: ordinaryNextText(item.value),
    tone: undefined
  }));
}

export default function NextSessionMap() {
  const [packet, setPacket] = useState<Record<string, unknown>>({});
  const [candidateRadarCache, setCandidateRadarCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<unknown>>([]);
  const [cacheMissingMessage, setCacheMissingMessage] = useState("");
  const [taskIndex, setTaskIndex] = useState<TaskStatusIndex | null>(null);
  const [taskId, setTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [browserQaReceipt, setBrowserQaReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [streamlitParityReceipt, setStreamlitParityReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [productionPromotionReceipt, setProductionPromotionReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [browserQaTaskId, setBrowserQaTaskId] = useState("");
  const [streamlitParityTaskId, setStreamlitParityTaskId] = useState("");
  const [productionPromotionTaskId, setProductionPromotionTaskId] = useState("");
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
  const launchTask = () => {
    if (!candidateRadarConfirmedSymbol) return;
    void postTask("/api/next-session/generate", nextSessionGeneratePayload).then((res) => {
      setTaskReceipt(res);
      if (res.ok) {
        setTaskId(res.data.task_id);
        refreshTaskIndex();
        refreshCache();
      }
    });
  };
  const reviewBrowserQa = () =>
    void postTask("/api/next-session/browser-qa-review", { review_scope: "next_session_browser_qa_local_artifact" }).then((res) => {
      setBrowserQaReceipt(res);
      if (res.ok) {
        setBrowserQaTaskId(res.data.task_id);
        setTaskId(res.data.task_id);
        refreshTaskIndex();
      }
    });
  const reviewStreamlitParity = () =>
    void postTask("/api/next-session/streamlit-parity-review", { review_scope: "next_session_same_packet_no_loss" }).then((res) => {
      setStreamlitParityReceipt(res);
      if (res.ok) {
        setStreamlitParityTaskId(res.data.task_id);
        setTaskId(res.data.task_id);
        refreshTaskIndex();
      }
    });
  const reviewProductionPromotion = () =>
    void postTask("/api/next-session/production-promotion-review", { review_scope: "next_session_local_promotion_blocker_review" }).then((res) => {
      setProductionPromotionReceipt(res);
      if (res.ok) {
        setProductionPromotionTaskId(res.data.task_id);
        setTaskId(res.data.task_id);
        refreshTaskIndex();
      }
    });
  const refreshCandidateRadarCache = () =>
    void getCandidateRadarCache().then((res) => {
      if (res.ok !== false) setCandidateRadarCache(res.data ?? {});
    });
  const refreshTaskIndex = () =>
    void getTasks().then((res) => setTaskIndex(res.data));

  useEffect(() => {
    refreshCache();
    refreshCandidateRadarCache();
    refreshTaskIndex();
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
  const nextSessionStatusLabel = chartSummary.has_drawable_data === true ? "可查看缓存图谱" : "等待缓存图谱";
  const nextSessionNextClick = chartSummary.has_drawable_data === true ? "先查看图谱；需要刷新时再点击生成任务" : "点击生成任务创建按钮门控图谱任务";
  const nextSessionCacheSourceLabel = packet.status === "cache_missing" ? "暂无缓存" : String(packet.cache_source ?? "本地缓存");
  const packetOrdinaryResultReplayRows = rowsFromArray(packet.ordinary_result_replay_rows);
  const packetOrdinaryChartReviewRows = rowsFromArray(packet.ordinary_chart_review_rows);
  const packetOrdinaryConditionQuickReadRows = rowsFromArray(packet.ordinary_condition_quick_read_rows);
  const packetCandidateRadarP3Handoff = (packet.candidate_radar_p3_handoff as Record<string, unknown> | undefined) ?? {};
  const packetCandidateRadarP3HandoffReady = packetCandidateRadarP3Handoff.p3_readable_result_ready === true;
  const packetCandidateRadarP2HandoffReady = packetCandidateRadarP3Handoff.p2_small_data_ready === true;
  const packetCandidateRadarP3HandoffSymbol = String(packetCandidateRadarP3Handoff.symbol ?? "");
  const packetCandidateRadarP3HandoffSourceTask = String(packetCandidateRadarP3Handoff.source_task_id ?? "");
  const packetCandidateRadarP3HandoffSummary = String(packetCandidateRadarP3Handoff.ordinary_result_summary ?? "");
  const packetCandidateRadarP3HandoffNextStep = String(packetCandidateRadarP3Handoff.ordinary_result_next_step ?? "");
  const packetCandidateRadarP3HandoffBoundary = String(packetCandidateRadarP3Handoff.ordinary_result_boundary ?? "");
  const packetCandidateRadarP3HandoffDeepSeekState = String(
    packetCandidateRadarP3Handoff.deepseek_governed_executor_status ?? ""
  );
  const candidateRadarP1ShortestPathCheckpoint = (candidateRadarCache.ordinary_p1_shortest_path_checkpoint as Record<string, unknown> | undefined) ?? {};
  const candidateRadarSmallDataWriteback = (candidateRadarCache.search_quant_projection_small_data_writeback_summary as Record<string, unknown> | undefined) ?? {};
  const packetCandidateRadarProviderSuccessFromHandoff = Number(packetCandidateRadarP3Handoff.provider_api_success_count ?? 0);
  const packetCandidateRadarProviderSuccessFromCandidateCache = Number(
    candidateRadarSmallDataWriteback.provider_api_success_count ??
      candidateRadarP1ShortestPathCheckpoint.provider_api_success_count ??
      0
  );
  const packetCandidateRadarProviderSuccessCount =
    packetCandidateRadarProviderSuccessFromHandoff > 0 ? packetCandidateRadarProviderSuccessFromHandoff : packetCandidateRadarProviderSuccessFromCandidateCache;
  const packetCandidateRadarProviderCallFromHandoff = Number(packetCandidateRadarP3Handoff.provider_api_call_count ?? 0);
  const packetCandidateRadarProviderCallFromCandidateCache = Number(
    candidateRadarSmallDataWriteback.provider_api_call_count ??
      candidateRadarP1ShortestPathCheckpoint.provider_api_call_count ??
      packetCandidateRadarProviderSuccessCount
  );
  const packetCandidateRadarProviderCallCount =
    packetCandidateRadarProviderCallFromHandoff > 0 ? packetCandidateRadarProviderCallFromHandoff : packetCandidateRadarProviderCallFromCandidateCache;
  const packetCandidateRadarProviderLedgerLabel = packetCandidateRadarProviderSuccessCount > 0
    ? `${String(packetCandidateRadarProviderSuccessCount)}/${String(packetCandidateRadarProviderCallCount || packetCandidateRadarProviderSuccessCount)} 个接口`
    : "本地 ledger 可读";
  const candidateRadarProviderApiRows = rowsFromArray(candidateRadarSmallDataWriteback.ordinary_provider_api_rows);
  const nextSessionTushareSourceLabel = chartSummary.uses_real_daily_close === true
    ? "真实 daily close 已在本地缓存"
    : packetCandidateRadarP3HandoffReady || packetCandidateRadarP2HandoffReady || packetCandidateRadarProviderSuccessCount > 0
      ? `Tushare-first 已从 CandidateRadar 回放：${packetCandidateRadarProviderLedgerLabel}；完整图谱锚点待本地 cache`
      : "待 Tushare/cache 补证";
  const nextSessionDeepSeekSourceLabel = chartPayload?.deepseek_status === "success" ? "已有本地解释记录" : "未调用或待 governed executor";
  const nextSessionP5GovernanceLabel = "P5 解释治理：DeepSeek 单独补证，不阻塞 P3 图谱复核";
  const nextSessionPendingSourceLabel = Number(productionStageScope.pending_stage_count ?? 0) > 0 ? "生产替代证据仍有 pending" : "当前图谱摘要未标记 pending";
  const nextSessionDegradedSourceLabel = chartSummary.is_exact_next_session_packet === true ? "精确 packet 可用" : "非精确 packet 时只显示 legacy/cache 投影";
  const nextSessionMissingEvidence = [
    Number(replacementActivation.missing_evidence_count ?? 0) > 0 ? "替代激活证据未齐" : "",
    browserQaEvidence.next_browser_qa_evidence_ready === true ? "" : "浏览器视觉 QA 未完成",
    streamlitParityReview.streamlit_parity_complete === true ? "" : "retained signal/capability coverage 未完成",
    chartSummary.uses_real_daily_close === true ? "" : "真实 close 证据待确认"
  ].filter(Boolean).join("；") || "当前摘要未标记缺口";
  const nextSessionLastCache = [
    String(packet.cache_source ?? "cache source unknown"),
    chartSummary.has_drawable_data === true ? `情景=${String(chartSummary.scenario_series_count ?? 0)} / 参考线=${String(chartSummary.reference_line_count ?? 0)} / 操作区=${String(chartSummary.operation_zone_count ?? 0)}` : "",
    latestCloseAnchor.price ? `latest close=${String(latestCloseAnchor.price)}` : ""
  ].filter(Boolean).join("；") || "暂无最近可用缓存";
  const nextSessionLastResultLabel = chartSummary.has_drawable_data === true
    ? `最近结果：${String(chartSummary.scenario_series_count ?? 0)} 条路径、${String(chartSummary.reference_line_count ?? 0)} 条参考线、${String(chartSummary.operation_zone_count ?? 0)} 个操作区；${latestCloseAnchor.price ? `最新收盘 ${String(latestCloseAnchor.price)}` : "等待最新收盘锚点"}`
    : "暂无最近结果；先查看缓存状态或手动生成任务。";
  const nextSessionTaskBoundary = "GET cache 只读；生成或审查都必须走按钮门控 POST task；React 渲染不直连 Tushare 或 DeepSeek，不改操作区";
  const nextSessionResearchOnlyLabel = "次日图谱只解释缓存场景；不是买卖指令，不真实交易、不下单、不改 strategy action";
  const nextSessionChartReviewOrder = chartSummary.has_drawable_data === true
    ? "先看图表路径、参考线和操作区，再看缺少证据；工程审计在开发详情"
    : "先点击生成任务或查看缓存状态；有图表后再按路径、参考线、操作区复核";
  const nextSessionCacheButtonLabel = "查看缓存只读取本地 GET cache；复核顺序是图表路径、参考线、操作区、缺少证据";
  const nextSessionChartReviewRegionLabel = "次日图谱复核区域：先看图表路径，再看参考线、操作区和缺少证据";
  const nextSessionReplayOrigin = chartSummary.is_exact_next_session_packet === true
    ? "来自精确本地次日图谱数据；可从下一票雷达/量化推演回放到本页"
    : "来自 legacy/cache 投影或暂无精确 packet；只作降级预览";
  const nextSessionReplayPath =
    "回放路径：下一票雷达确认代码 -> 股票量化推演支持/压制 -> 次日图谱路径/参考线/操作区";
  const nextSessionReplayDestinationBoundary =
    "回放入口只切换本地模块路由（#candidates/... 直达确认输入区，#factor 到量化推演）；不创建 task、不调用 Tushare/DeepSeek、不写 cache、不改操作区";
  const nextSessionOperationZoneBoundary = "操作区只表示条件区间和复核提示；不是买卖指令，不写交易动作，不改 strategy action";
  const nextSessionPacketHandoffLabel = packetCandidateRadarP3HandoffReady
    ? `本地次日图谱数据已接上 ${packetCandidateRadarP3HandoffSymbol || "当前标的"}`
    : "本地次日图谱数据等待 CandidateRadar P3 结果";
  const candidateRadarWritebackSurfaceRows = rowsFromArray(candidateRadarSmallDataWriteback.ordinary_writeback_surface_summary_rows);
  const candidateRadarWritebackSurfaceReady =
    packetCandidateRadarP2HandoffReady ||
    (
      candidateRadarWritebackSurfaceRows.length >= 3 &&
      candidateRadarSmallDataWriteback.cache_packet_written === true &&
      candidateRadarSmallDataWriteback.provider_call_ledger_written === true &&
      candidateRadarSmallDataWriteback.small_data_writeback_ready === true
    );
  const candidateRadarWritebackSurfaceStatus = candidateRadarWritebackSurfaceReady
    ? packetCandidateRadarP2HandoffReady
      ? "P2 三面已由 next-session handoff 回放：本地缓存、数据凭证、结果包可读；cache / call_ledger / packet 可读"
      : "P2 三面已回放：本地缓存、数据凭证、结果包可读；cache / call_ledger / packet 都可读"
    : `P2 三面等待：${String(
        candidateRadarSmallDataWriteback.ordinary_readback_stage_label ??
          candidateRadarSmallDataWriteback.summary_label ??
          "等待确认按钮后的本地写回"
      )}`;
  const candidateRadarWritebackSurfaceBoundary =
    "P2 三面只读 CandidateRadar cache / call_ledger / packet；图谱页不创建 task、不补调 Tushare/DeepSeek。";
  const candidateRadarOneScreenRows = rowsFromArray(candidateRadarSmallDataWriteback.ordinary_one_screen_action_rows);
  const candidateRadarConfirmOutcomeRows = rowsFromArray(candidateRadarSmallDataWriteback.ordinary_confirm_outcome_rows);
  const candidateRadarInterpretation = (candidateRadarCache.search_quant_projection_interpretation_summary as Record<string, unknown> | undefined) ?? {};
  const candidateRadarPostConfirmOneGlanceRows = rowsFromArray(
    candidateRadarCache.search_quant_projection_post_confirm_one_glance_items ??
      candidateRadarInterpretation.ordinary_post_confirm_one_glance_items
  );
  const candidateRadarReceipt = (candidateRadarCache.search_quant_projection_receipt as Record<string, unknown> | undefined) ?? {};
  const candidateRadarProviderModelAcceptance =
    (candidateRadarCache.search_quant_provider_model_acceptance_receipt as Record<string, unknown> | undefined) ?? {};
  const candidateRadarResultLineage =
    (candidateRadarCache.search_quant_result_lineage as Record<string, unknown> | undefined) ?? {};
  const candidateRadarResultVersionSummary =
    (candidateRadarCache.search_quant_result_version_summary as Record<string, unknown> | undefined) ?? {};
  const candidateRadarCurrentResultVersion = String(
    candidateRadarResultVersionSummary.current_result_version ??
      candidateRadarResultLineage.result_version ??
      candidateRadarProviderModelAcceptance.result_version ??
      ""
  );
  const candidateRadarLatestResultVersion = String(
    candidateRadarResultVersionSummary.latest_task_result_version ??
      candidateRadarResultVersionSummary.latest_result_version ??
      candidateRadarResultLineage.result_version ??
      ""
  );
  const candidateRadarResultVersionLabel = candidateRadarCurrentResultVersion
    ? `当前结果版本 ${candidateRadarCurrentResultVersion}; latest ${candidateRadarLatestResultVersion || candidateRadarCurrentResultVersion}`
    : "等待 result_version 回放";
  const candidateRadarConfirmedSymbol = String(
    packet.latest_confirmed_symbol ||
      candidateRadarCache.latest_confirmed_symbol ||
      packetCandidateRadarP3HandoffSymbol ||
      candidateRadarReceipt.symbol ||
      candidateRadarSmallDataWriteback.symbol ||
      candidateRadarInterpretation.symbol ||
      ""
  );
  const candidateRadarConfirmedSymbolLabel = candidateRadarConfirmedSymbol
    ? `当前确认标的：${candidateRadarConfirmedSymbol}`
    : "等待下一票雷达确认标的";
  const nextSessionGenerateButtonDisabled = !candidateRadarConfirmedSymbol;
  const nextSessionGenerateButtonLabel = candidateRadarConfirmedSymbol
    ? `为 ${candidateRadarConfirmedSymbol} 生成完整次日图谱；按钮门控 POST task，只带当前确认标的和来源 task 的 safe payload`
    : "等待下一票雷达确认标的后才能生成完整次日图谱；输入、页面打开和 GET cache 不创建 task";
  const nextSessionGenerateButtonText = candidateRadarConfirmedSymbol
    ? `为 ${candidateRadarConfirmedSymbol} 生成完整图谱`
    : "等待确认标的";
  const candidateRadarSourceTaskLabel = String(
    packet.latest_confirmed_task_id ||
      candidateRadarCache.latest_confirmed_task_id ||
      packetCandidateRadarP3HandoffSourceTask ||
      candidateRadarCache.search_quant_projection_latest_task_id ||
      candidateRadarCache.latest_task_id ||
      candidateRadarReceipt.latest_task_id ||
      candidateRadarReceipt.task_id ||
      candidateRadarSmallDataWriteback.latest_task_id ||
      "等待下一票雷达确认 task"
  );
  const candidateRadarSourceTaskStep = String(
    packet.latest_confirmed_task_current_step ||
      candidateRadarCache.latest_confirmed_task_current_step ||
      packetCandidateRadarP3Handoff.status ||
      candidateRadarReceipt.latest_task_current_step ||
      candidateRadarSmallDataWriteback.latest_task_current_step ||
      candidateRadarReceipt.status ||
      "waiting_confirm"
  );
  const taskIndexLatestTask = taskIndex?.tasks?.[0];
  const taskIndexLatestConfirmedSymbol = String(
    taskIndex?.latest_confirmed_symbol ??
      (taskIndexLatestTask?.payload_safe as Record<string, unknown> | undefined)?.symbol ??
      ""
  );
  const taskIndexLatestConfirmedTaskId = String(
    taskIndex?.latest_confirmed_task_id ??
      taskIndex?.latest_task_id ??
      taskIndexLatestTask?.task_id ??
      ""
  );
  const taskIndexLatestConfirmedStatus = String(
    taskIndex?.latest_confirmed_task_status ??
      taskIndex?.latest_task_status ??
      taskIndexLatestTask?.status ??
      ""
  );
  const taskIndexLatestConfirmedStep = String(
    taskIndex?.latest_confirmed_task_current_step ??
      taskIndexLatestTask?.current_step ??
      ""
  );
  const taskIndexReadbackSafe =
    taskIndex !== null &&
    taskIndex.external_calls_triggered !== true &&
    taskIndex.readback_external_calls_triggered !== true &&
    taskIndex.latest_confirmed_symbol_readback_external_calls_triggered !== true &&
    taskIndex.latest_confirmed_symbol_creates_task_from_readback !== true;
  const nextSessionProgressWatchTaskId = taskIndexLatestConfirmedTaskId || (candidateRadarSourceTaskLabel.includes("等待") ? "" : candidateRadarSourceTaskLabel);
  const nextSessionProgressWatchSymbol = taskIndexLatestConfirmedSymbol || candidateRadarConfirmedSymbol;
  const nextSessionProgressWatchStatus =
    taskIndexLatestConfirmedStatus ||
    (nextSessionProgressWatchTaskId ? "cache_replay" : "waiting_confirm");
  const nextSessionProgressWatchStep =
    taskIndexLatestConfirmedStep ||
    candidateRadarSourceTaskStep ||
    "等待确认按钮后的本地任务状态";
  const nextSessionProgressWatchLabel = nextSessionProgressWatchTaskId
    ? `${nextSessionProgressWatchSymbol || "当前标的"} / ${nextSessionProgressWatchStatus}`
    : "等待确认按钮后的任务进度";
  const nextSessionProgressWatchNext = nextSessionProgressWatchTaskId
    ? "查看任务目录；成功后继续读图表路径、参考线和操作区"
    : "先回下一票雷达输入股票代码并点击确认按钮；输入本身保持静默";
  const nextSessionTaskIndexProgressItems: MetricItem[] = [
    {
      label: "边用边看",
      value: nextSessionProgressWatchLabel,
      tone: nextSessionProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "最新确认标的",
      value: nextSessionProgressWatchSymbol || "等待确认股票代码",
      tone: nextSessionProgressWatchSymbol ? "good" : "neutral"
    },
    {
      label: "最新任务",
      value: nextSessionProgressWatchTaskId || "等待确认按钮",
      tone: nextSessionProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "当前步骤",
      value: nextSessionProgressWatchStep,
      tone: nextSessionProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "只读来源",
      value: "GET /api/tasks + 本地次日图谱数据 + CandidateRadar cache",
      tone: "good"
    },
    {
      label: "安全边界",
      value: taskIndexReadbackSafe ? "任务索引回读未触发外联、未创建 task" : "等待任务索引只读边界回放",
      tone: taskIndexReadbackSafe ? "good" : "warn"
    }
  ];
  const candidateRadarConfirmedTaskReceiptRows = rowsFromArray(
    candidateRadarCache.search_quant_projection_confirmed_task_receipt_rows ??
      candidateRadarSmallDataWriteback.ordinary_confirmed_task_receipt_rows
  );
  const candidateRadarTaskReadbackRows = rowsFromArray(
    candidateRadarCache.search_quant_projection_task_readback_rows ??
      candidateRadarSmallDataWriteback.ordinary_task_readback_rows
  );
  const candidateRadarResultQuickRows = rowsFromArray(
    candidateRadarCache.ordinary_result_quick_read_rows ??
      candidateRadarInterpretation.ordinary_result_quick_read_rows
  );
  const candidateRadarResultHandoffRows = rowsFromArray(
    candidateRadarCache.ordinary_result_handoff_rows ??
      candidateRadarInterpretation.ordinary_result_handoff_rows
  );
  const candidateRadarReadableResult = String(
    packetCandidateRadarP3HandoffSummary ||
      candidateRadarCache.ordinary_result_summary ||
      candidateRadarInterpretation.ordinary_result_summary ||
      "等待下一票雷达确认后的可读结论"
  );
  const candidateRadarReadableNextStep = String(
    packetCandidateRadarP3HandoffNextStep ||
      candidateRadarCache.ordinary_result_next_step ||
      candidateRadarInterpretation.ordinary_result_next_step ||
      "先回下一票雷达确认输入区输入代码并点击确认按钮"
  );
  const candidateRadarReadableBoundary = String(
    packetCandidateRadarP3HandoffBoundary ||
      candidateRadarCache.ordinary_result_boundary ||
      candidateRadarInterpretation.ordinary_result_boundary ||
      "次日图谱只读 CandidateRadar cache / ledger / packet 的可读结论；不创建 task、不调用 Tushare/DeepSeek、不改操作区或 strategy action。"
  );
  const candidateRadarDeepSeekStateRaw = String(
    packetCandidateRadarP3HandoffDeepSeekState ||
      candidateRadarCache.ordinary_result_deepseek_governed_executor_status ||
      candidateRadarInterpretation.deepseek_governed_executor_status ||
      "governed_executor_pending"
  );
  const candidateRadarUsesModelOutput =
    packetCandidateRadarP3Handoff.uses_deepseek_output === true ||
    packetCandidateRadarP3Handoff.uses_model_output === true ||
    candidateRadarInterpretation.uses_deepseek_output === true ||
    candidateRadarInterpretation.uses_model_output === true;
  const candidateRadarOrdinaryDeepSeekState = candidateRadarUsesModelOutput
    ? "检测到模型输出；需回 P5 governed executor 审核后再展示"
    : candidateRadarDeepSeekStateRaw.includes("skipped")
      ? "DeepSeek 不用等：Tushare-first 和次日图谱可先看"
      : candidateRadarDeepSeekStateRaw.includes("pending")
        ? "DeepSeek 待治理：不阻塞 Tushare-first、P2 写入或 P3 图谱"
        : "DeepSeek governed executor 单独补；普通结果只读本地 cache / ledger / packet";
  const nextSessionBackendPostConfirmOneGlanceItems: MetricItem[] = candidateRadarPostConfirmOneGlanceRows.map((row) => {
    const tone = String(row.tone ?? "neutral");
    return {
      label: String(row.label ?? row["状态项"] ?? row.item_key ?? "确认后状态"),
      value: String(row.value ?? row["当前状态"] ?? row.status ?? "--"),
      tone: (["good", "warn", "bad", "neutral"].includes(tone) ? tone : "neutral") as MetricItem["tone"]
    };
  });
  const candidateRadarReadableResultReady =
    Boolean(candidateRadarConfirmedSymbol) &&
    (
      packetCandidateRadarP3HandoffReady ||
      candidateRadarInterpretation.interpretation_ready === true ||
      candidateRadarResultQuickRows.length > 0 ||
      candidateRadarReadableResult !== "等待下一票雷达确认后的可读结论"
    );
  const nextSessionReadableStatusLabel = chartSummary.has_drawable_data === true
    ? nextSessionStatusLabel
    : candidateRadarReadableResultReady
      ? "已回放搜票结论，图谱待生成"
      : nextSessionStatusLabel;
  const nextSessionReadableNextClick = chartSummary.has_drawable_data === true
    ? nextSessionNextClick
    : candidateRadarReadableResultReady
      ? "先看已确认标的和 Tushare-first 结论；完整图谱可手动生成"
      : nextSessionNextClick;
  const nextSessionReadableLastResultLabel = chartSummary.has_drawable_data === true
    ? nextSessionLastResultLabel
    : candidateRadarReadableResultReady
      ? `上游结果：${candidateRadarConfirmedSymbol}；${candidateRadarReadableResult}`
      : nextSessionLastResultLabel;
  const nextSessionReadableChartReviewOrder = chartSummary.has_drawable_data === true
    ? nextSessionChartReviewOrder
    : candidateRadarReadableResultReady
      ? "先读已确认标的、Tushare-first 结论和 P2 三面；完整图谱可手动生成"
      : nextSessionChartReviewOrder;
  const nextSessionLatestCandidateReadableSentence = candidateRadarReadableResultReady
    ? `${candidateRadarConfirmedSymbolLabel}；P3 结论：${candidateRadarReadableResult}；${chartSummary.has_drawable_data === true ? "完整图谱已可读" : "完整图谱等待手动生成"}；下一步：${nextSessionReadableChartReviewOrder}。`
    : `等待下一票雷达确认标的；下一步：${nextSessionReadableChartReviewOrder}。`;
  const nextSessionLiveLightModeLabel = chartSummary.has_drawable_data === true
    ? "cache-live: 本地次日图谱可读"
    : candidateRadarReadableResultReady
      ? "handoff-light: 上游搜票结论可读，完整图谱待按钮生成"
      : packet.status === "cache_missing"
        ? "degraded-light: 暂无本地 cache，只显示等待和回流入口"
        : "cache-check: 等待可绘制图谱，先看本地 cache 状态";
  const nextSessionLiveLightNextStep = chartSummary.has_drawable_data === true
    ? "看图表路径、参考线和操作区"
    : candidateRadarReadableResultReady
      ? "确认上游结论和 P2 三面后，再手动生成完整图谱"
      : "回下一票雷达输入股票代码并点击确认";
  const nextSessionLiveLightEvidenceItems: MetricItem[] = [
    {
      label: "运行模式",
      value: nextSessionLiveLightModeLabel,
      tone: chartSummary.has_drawable_data === true ? "good" : candidateRadarReadableResultReady ? "warn" : "neutral"
    },
    {
      label: "数据层",
      value: nextSessionTushareSourceLabel,
      tone: chartSummary.uses_real_daily_close === true || packetCandidateRadarProviderSuccessCount > 0 ? "good" : "warn"
    },
    {
      label: "证据层",
      value: `${nextSessionCacheSourceLabel} / ${nextSessionReplayOrigin}`,
      tone: chartSummary.is_exact_next_session_packet === true ? "good" : "warn"
    },
    {
      label: "模型层",
      value: `DeepSeek 不在首屏执行；${nextSessionP5GovernanceLabel}`,
      tone: "good"
    },
    {
      label: "缺口层",
      value: nextSessionMissingEvidence,
      tone: nextSessionMissingEvidence === "当前摘要未标记缺口" ? "good" : "warn"
    },
    {
      label: "动作层",
      value: "仅供研究；不下单、不改操作区或 strategy action",
      tone: "good"
    },
    {
      label: "轻量下一步",
      value: nextSessionLiveLightNextStep,
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    }
  ];
  const nextSessionTushareDataCardReady =
    packetCandidateRadarProviderSuccessCount > 0 ||
    candidateRadarWritebackSurfaceReady ||
    packetCandidateRadarP2HandoffReady ||
    packetCandidateRadarP3HandoffReady;
  const nextSessionTushareDataCardSummary = nextSessionTushareDataCardReady
    ? `${candidateRadarConfirmedSymbol || "当前标的"} 确认后 Tushare 数据卡可读：${packetCandidateRadarProviderLedgerLabel}；${candidateRadarWritebackSurfaceReady ? "P2 三面已回放" : "P2 三面待完整回放"}。`
    : "确认后 Tushare 数据卡等待回写：先回下一票雷达输入股票代码并点击确认按钮。";
  const nextSessionTushareDataCardGap = nextSessionTushareDataCardReady
    ? chartSummary.has_drawable_data === true
      ? "Tushare-first 账本和完整次日图谱都已进入本地回放。"
      : "Tushare-first 账本可读；完整次日图谱还需手动生成或等待本地 cache。"
    : "缺 Tushare call_ledger；等待确认任务、本地阻断或后续授权回写。";
  const nextSessionTushareDataCardNext = nextSessionTushareDataCardReady
    ? chartSummary.has_drawable_data === true
      ? "先看图表路径、参考线和操作区。"
      : "先看上游 Tushare-first 结论，再手动生成完整次日图谱。"
    : "回下一票雷达确认输入区，输入股票代码并点击确认按钮。";
  const nextSessionDataCapabilityReviewLabel = nextSessionTushareDataCardReady
    ? "Tushare 数据凭证已有本地回放；图谱缺口、空窗口和结果包去数据能力页复核。"
    : "Tushare 数据凭证、权限、空窗口或本地结果包缺口去数据能力页复核；本页不探测接口。";
  const nextSessionTushareDataCardItems: MetricItem[] = [
    {
      label: "Tushare 数据卡",
      value: nextSessionTushareDataCardSummary,
      tone: nextSessionTushareDataCardReady ? "good" : "warn"
    },
    {
      label: "接口回放",
      value: nextSessionTushareDataCardReady ? packetCandidateRadarProviderLedgerLabel : "等待本地 call_ledger",
      tone: nextSessionTushareDataCardReady ? "good" : "warn"
    },
    {
      label: "P2 三面",
      value: candidateRadarWritebackSurfaceStatus,
      tone: candidateRadarWritebackSurfaceReady ? "good" : "warn"
    },
    {
      label: "P3 图谱",
      value: nextSessionReadableStatusLabel,
      tone: chartSummary.has_drawable_data === true ? "good" : candidateRadarReadableResultReady ? "warn" : "neutral"
    },
    {
      label: "缺口",
      value: nextSessionTushareDataCardGap,
      tone: nextSessionTushareDataCardReady && chartSummary.has_drawable_data === true ? "good" : "warn"
    },
    {
      label: "下一步",
      value: nextSessionTushareDataCardNext,
      tone: nextSessionTushareDataCardReady ? "good" : "warn"
    },
    {
      label: "边界",
      value: "只读已有本地结果、数据记录和次日图谱缓存；不刷新外部数据或模型、不交易",
      tone: "good"
    }
  ];
  const nextSessionTushareDataCardRows = candidateRadarProviderApiRows.length
    ? candidateRadarProviderApiRows.map((row) => ({
        接口: String(row.api ?? row.interface ?? row.name ?? row.provider_api ?? row["接口"] ?? "Tushare light"),
        当前状态: String(row.status ?? row.state ?? row.current_status ?? row["当前状态"] ?? "本地回放"),
        证据: String(row.evidence ?? row.source ?? row.ledger ?? row["证据"] ?? "CandidateRadar ordinary_provider_api_rows"),
        用户下一步: String(row.next_action ?? row.next_step ?? row["用户下一步"] ?? nextSessionTushareDataCardNext),
        边界: String(row.boundary ?? row["边界"] ?? "只读本地账本；不从次日图谱页补调 provider/model。")
      }))
    : [
        {
          接口: "trade_cal / daily / daily_basic / moneyflow",
          当前状态: nextSessionTushareDataCardReady
            ? `已看到 Tushare-first 回放 ${packetCandidateRadarProviderLedgerLabel}`
            : "等待 Tushare call_ledger 或本地阻断回放",
          证据: nextSessionTushareSourceLabel,
          用户下一步: nextSessionTushareDataCardNext,
          边界: "次日图谱只读本地 cache / call_ledger / packet；不创建第二个 task、不补调 Tushare/DeepSeek。"
        }
      ];
  const nextSessionGeneratePayload = {
    schema_version: "next_session_confirmed_symbol_generate_payload.v1",
    source: "next_session_map_manual_generate_button",
    symbol: candidateRadarConfirmedSymbol,
    source_task_id: candidateRadarSourceTaskLabel.includes("等待") ? "" : candidateRadarSourceTaskLabel,
    candidate_readback_source: "CandidateRadar cache / ledger / packet",
    p2_small_data_ready: candidateRadarWritebackSurfaceReady,
    p3_readable_result_ready: candidateRadarReadableResultReady,
    manual_button_required: true,
    cache_get_external_calls_triggered: false,
    react_render_external_calls_triggered: false,
    deepseek_execution_requested: false,
    does_not_include_token_or_raw_log: true,
    does_not_execute_trades: true,
    does_not_modify_operation_zones: true
  };
  const nextSessionOrdinaryProgressCheckpointAnchor = chartSummary.has_drawable_data === true
    ? "#next-session-chart"
    : candidateRadarReadableResultReady
      ? "#next-session-generate-actions"
      : CANDIDATE_CONFIRM_HREF;
  const nextSessionOrdinaryProgressCheckpointLabel = chartSummary.has_drawable_data === true
    ? "查看完整图谱"
    : candidateRadarReadableResultReady
      ? "去生成完整图谱"
      : "回下一票雷达确认";
  const nextSessionOrdinaryProgressCheckpointItems: MetricItem[] = [
    {
      label: "当前 checkpoint",
      value: chartSummary.has_drawable_data === true
        ? "完整次日图谱可读：先看图表路径、参考线和操作区"
        : candidateRadarReadableResultReady
          ? "上游搜票结论可读：完整图谱等待手动生成"
          : "等待下一票雷达确认标的",
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "确认标的",
      value: candidateRadarConfirmedSymbolLabel,
      tone: candidateRadarConfirmedSymbol ? "good" : "warn"
    },
    {
      label: "来源 task",
      value: candidateRadarSourceTaskLabel,
      tone: candidateRadarSourceTaskLabel.includes("等待") ? "warn" : "good"
    },
    {
      label: "结果版本",
      value: candidateRadarResultVersionLabel,
      tone: candidateRadarCurrentResultVersion ? "good" : "warn"
    },
    {
      label: "上游结论",
      value: candidateRadarReadableResult,
      tone: candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "图谱状态",
      value: nextSessionReadableStatusLabel,
      tone: chartSummary.has_drawable_data === true ? "good" : candidateRadarReadableResultReady ? "warn" : "neutral"
    },
    {
      label: "安全边界",
      value: "只读回放；生成必须手动按钮；不调用 DeepSeek、不交易、不改操作区",
      tone: "good"
    }
  ];
  const nextSessionFirstScreenReadableSentence = `${candidateRadarConfirmedSymbolLabel}；${nextSessionReadableLastResultLabel}；下一步：${nextSessionReadableChartReviewOrder}；缺口：${nextSessionMissingEvidence}。`;
  const nextSessionFirstScreenItems: MetricItem[] = [
    {
      label: "当前股票",
      value: candidateRadarConfirmedSymbolLabel,
      tone: candidateRadarConfirmedSymbol ? "good" : "warn"
    },
    {
      label: "最近结果",
      value: nextSessionReadableLastResultLabel,
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "下一步",
      value: nextSessionReadableChartReviewOrder,
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "证据缺口",
      value: nextSessionMissingEvidence,
      tone: nextSessionMissingEvidence === "当前摘要未标记缺口" ? "good" : "warn"
    },
    {
      label: "只读来源",
      value: `${nextSessionCacheSourceLabel} / CandidateRadar cache / GET tasks`,
      tone: "good"
    },
    {
      label: "操作边界",
      value: nextSessionOperationZoneBoundary,
      tone: "good"
    }
  ];
  const nextSessionPostConfirmOneMinuteSentence = chartSummary.has_drawable_data === true
    ? `${candidateRadarConfirmedSymbol || "当前标的"} 确认后一眼读图：先看 ${String(chartSummary.scenario_series_count ?? 0)} 条图表路径，再看 ${String(chartSummary.reference_line_count ?? 0)} 条参考线和 ${String(chartSummary.operation_zone_count ?? 0)} 个操作区；最后核对证据缺口。`
    : candidateRadarReadableResultReady
      ? `${candidateRadarConfirmedSymbol || "当前标的"} 已有上游搜票结论；完整次日图谱等待手动生成，先看来源、缺口和支持/压制。`
      : "确认后一眼读图等待标的：先回下一票雷达输入股票代码并点击确认，再回本页看路径、参考线和操作区。";
  const nextSessionPostConfirmOneMinuteItems: MetricItem[] = [
    {
      label: "当前标的",
      value: candidateRadarConfirmedSymbolLabel,
      tone: candidateRadarConfirmedSymbol ? "good" : "warn"
    },
    {
      label: "图表路径",
      value: chartSummary.has_drawable_data === true ? `${String(chartSummary.scenario_series_count ?? 0)} 条路径` : "等待完整图谱",
      tone: chartSummary.has_drawable_data === true ? "good" : candidateRadarReadableResultReady ? "warn" : "neutral"
    },
    {
      label: "参考线",
      value: chartSummary.has_drawable_data === true ? `${String(chartSummary.reference_line_count ?? 0)} 条参考线` : "等待参考线",
      tone: chartSummary.has_drawable_data === true ? "good" : "warn"
    },
    {
      label: "操作区",
      value: chartSummary.has_drawable_data === true ? `${String(chartSummary.operation_zone_count ?? 0)} 个操作区` : "等待操作区",
      tone: Number(chartSummary.operation_zone_count ?? 0) > 0 ? "good" : chartSummary.has_drawable_data === true ? "warn" : "neutral"
    },
    {
      label: "证据缺口",
      value: nextSessionMissingEvidence,
      tone: nextSessionMissingEvidence === "当前摘要未标记缺口" ? "good" : "warn"
    },
    {
      label: "下一步",
      value: nextSessionReadableChartReviewOrder,
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "非交易边界",
      value: "路径、参考线和操作区只供研究复核，不是买卖、下单或改策略指令",
      tone: "good"
    }
  ];
  const nextSessionAppVisibleNowSentence = chartSummary.has_drawable_data === true
    ? `打开 app 能看到 ${candidateRadarConfirmedSymbolLabel} 的完整次日图谱：路径、参考线、操作区和证据缺口都在首屏可读。`
    : candidateRadarReadableResultReady
      ? `打开 app 能看到 ${candidateRadarConfirmedSymbolLabel} 的上游搜票结论、Tushare-first 数据卡和生成完整图谱入口。`
      : "打开 app 能看到降级等待态：先回下一票雷达输入股票并点击确认，本页只保留本地回流入口。";
  const nextSessionAppVisibleNowItems: MetricItem[] = [
    {
      label: "打开可见",
      value: nextSessionAppVisibleNowSentence,
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "当前股票",
      value: candidateRadarConfirmedSymbolLabel,
      tone: candidateRadarConfirmedSymbol ? "good" : "warn"
    },
    {
      label: "先读哪里",
      value: chartSummary.has_drawable_data === true
        ? "完整图谱区域：路径、参考线、操作区"
        : candidateRadarReadableResultReady
          ? "上游结论、Tushare 数据卡、生成完整图谱入口"
          : "下一票雷达确认输入区",
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "来源层",
      value: `${nextSessionCacheSourceLabel} / CandidateRadar cache / 本地任务索引`,
      tone: "good"
    },
    {
      label: "明确降级",
      value: nextSessionDegradedSourceLabel,
      tone: chartSummary.is_exact_next_session_packet === true ? "good" : "warn"
    },
    {
      label: "数据能力",
      value: nextSessionDataCapabilityReviewLabel,
      tone: nextSessionTushareDataCardReady ? "good" : "warn"
    },
    {
      label: "下一步按钮",
      value: nextSessionOrdinaryProgressCheckpointLabel,
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "安全边界",
      value: "页面打开和本地链接只读；不自动创建任务、不调用 Tushare/DeepSeek/GitHub、不交易、不改操作区",
      tone: "good"
    }
  ];
  const nextSessionAppFirstResearchReadSentence = chartSummary.has_drawable_data === true
    ? `${candidateRadarConfirmedSymbol || "当前标的"} 次日图谱已可读：先看路径、参考线和操作区，再看缺口。`
    : candidateRadarReadableResultReady
      ? `${candidateRadarConfirmedSymbol || "当前标的"} 上游结论已可读；完整图谱仍是 degraded 等待，需要手动生成或等待本地 cache。`
      : "次日图谱当前是 degraded 等待态：先回下一票雷达确认股票，本页不会自动补调数据。";
  const nextSessionAppFirstResearchReadItems: MetricItem[] = [
    {
      label: "现在能看",
      value: nextSessionAppFirstResearchReadSentence,
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "读图顺序",
      value: chartSummary.has_drawable_data === true
        ? "路径 -> 参考线 -> 操作区 -> 缺口"
        : candidateRadarReadableResultReady
          ? "上游结论 -> 生成完整图谱入口 -> 支持/压制"
          : "下一票雷达确认 -> 本地缓存回放 -> 图谱复核",
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "证据来源",
      value: `${nextSessionCacheSourceLabel} / ${nextSessionReplayOrigin}`,
      tone: chartSummary.is_exact_next_session_packet === true ? "good" : "warn"
    },
    {
      label: "degraded 缺口",
      value: nextSessionMissingEvidence,
      tone: nextSessionMissingEvidence === "当前摘要未标记缺口" ? "good" : "warn"
    },
    {
      label: "下一步入口",
      value: nextSessionOrdinaryProgressCheckpointLabel,
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "研究边界",
      value: "图谱和操作区只做条件复核；查看页面和链接跳转不创建后台流程、不外联、不交易、不改策略",
      tone: "good"
    }
  ];
  const nextSessionPlainConclusion = chartSummary.has_drawable_data === true
    ? `完整次日图谱可读：${String(chartSummary.scenario_series_count ?? 0)} 条路径、${String(chartSummary.reference_line_count ?? 0)} 条参考线、${String(chartSummary.operation_zone_count ?? 0)} 个操作区。`
    : candidateRadarReadableResultReady
      ? `${candidateRadarConfirmedSymbol || "当前标的"} 的上游结论已可读；完整次日图谱还要手动生成。`
      : "还没有可读次日图谱；先回下一票雷达确认股票。";
  const nextSessionPlainGap = chartSummary.has_drawable_data === true
    ? nextSessionMissingEvidence === "当前摘要未标记缺口"
      ? "暂无页面阻断；仍只作为研究复核。"
      : "生产替代证据还没补齐；当前图谱先按本地路径、参考线和操作区阅读。"
    : candidateRadarReadableResultReady
      ? "完整图谱还没生成；先确认上游结论，再手动生成。"
      : "缺少确认标的或本地图谱数据；不要把空图谱解释成无风险。";
  const nextSessionPlainNow = chartSummary.has_drawable_data === true
    ? "先看图表路径和参考线，再看操作区。"
    : candidateRadarReadableResultReady
      ? "生成完整图谱，或回股票量化推演看支持/压制。"
      : "回下一票雷达确认股票代码。";
  const nextSessionPlainSafety = "图谱只做条件路径复核，不是买入、卖出、加仓或下单指令。";
  const nextSessionPlainConclusionItems: MetricItem[] = [
    {
      label: "一句话",
      value: nextSessionPlainConclusion,
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "缺口",
      value: nextSessionPlainGap,
      tone: chartSummary.has_drawable_data === true && nextSessionMissingEvidence === "当前摘要未标记缺口" ? "good" : "warn"
    },
    {
      label: "现在做什么",
      value: nextSessionPlainNow,
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "安全说明",
      value: nextSessionPlainSafety,
      tone: "good"
    }
  ];
  const nextSessionStrictCloseoutGateRows = [
    {
      gate_key: "local_echarts_packet_visible",
      current_status: nextSessionReadableStatusLabel,
      strict_closeout_state: "strict closeout remains blocked",
      can_close_ltg08_now: false,
      evidence_required: "retained signal/capability and durable browser evidence before strict closeout",
      browser_visual_qa_done: false,
      browser_performance_trace_done: false,
      durable_ci_evidence_complete: false,
      production_replacement_complete: false,
      opens_browser: false,
      writes_artifacts: false,
      external_calls_triggered: false,
      tushare_called: false,
      deepseek_called: false,
      github_called: false,
      does_not_execute_trades: true,
      does_not_modify_strategy_action: true,
      does_not_modify_operation_zones: true,
      operation_zones_are_conditions: true
    },
    {
      gate_key: "browser_evidence_authorization_required",
      current_status: "future explicit next-session retained signal/capability coverage and production replacement task",
      strict_closeout_state: "strict closeout remains blocked",
      can_close_ltg08_now: false,
      evidence_required: "durable browser visual QA, performance trace, retained coverage, CI/release evidence, and production promotion review",
      browser_visual_qa_done: false,
      browser_performance_trace_done: false,
      durable_ci_evidence_complete: false,
      production_replacement_complete: false,
      opens_browser: false,
      writes_artifacts: false,
      external_calls_triggered: false,
      tushare_called: false,
      deepseek_called: false,
      github_called: false,
      does_not_execute_trades: true,
      does_not_modify_strategy_action: true,
      does_not_modify_operation_zones: true,
      operation_zones_are_conditions: true
    },
    {
      gate_key: "LTG-12 交易隔离支撑",
      current_status: "operation zones are conditions, not broker orders or strategy action mutation",
      strict_closeout_state: "strict closeout remains blocked",
      can_close_ltg08_now: false,
      evidence_required: "research-only boundary remains visible while LTG-08 waits for direct production replacement evidence",
      browser_visual_qa_done: false,
      browser_performance_trace_done: false,
      durable_ci_evidence_complete: false,
      production_replacement_complete: false,
      opens_browser: false,
      writes_artifacts: false,
      external_calls_triggered: false,
      tushare_called: false,
      deepseek_called: false,
      github_called: false,
      does_not_execute_trades: true,
      does_not_modify_strategy_action: true,
      does_not_modify_operation_zones: true,
      operation_zones_are_conditions: true
    }
  ];
  const nextSessionUsableNowItems: MetricItem[] = [
    {
      label: "图谱状态",
      value: chartSummary.has_drawable_data === true
        ? `完整图谱可读：${nextSessionReadableLastResultLabel}`
        : candidateRadarReadableResultReady
          ? "上游结论可读，完整图谱等待手动生成"
          : "等待确认标的或本地缓存",
      tone: chartSummary.has_drawable_data === true ? "good" : candidateRadarReadableResultReady ? "warn" : "neutral"
    },
    {
      label: "Next cache handoff",
      value: nextSessionPacketHandoffLabel,
      tone: packetCandidateRadarP3HandoffReady ? "good" : "warn"
    },
    {
      label: "P3 结论",
      value: candidateRadarReadableResult,
      tone: candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "P2 三面",
      value: candidateRadarWritebackSurfaceReady
        ? "已回放：本地缓存、数据凭证、结果包"
        : candidateRadarWritebackSurfaceStatus,
      tone: candidateRadarWritebackSurfaceReady ? "good" : "warn"
    },
    {
      label: "操作区",
      value: chartSummary.has_drawable_data === true
        ? `操作区 ${String(chartSummary.operation_zone_count ?? 0)} 个；${nextSessionOperationZoneBoundary}`
        : `等待完整图谱；${nextSessionOperationZoneBoundary}`,
      tone: Number(chartSummary.operation_zone_count ?? 0) > 0 ? "good" : chartSummary.has_drawable_data === true ? "warn" : "neutral"
    },
    {
      label: "现在点哪",
      value: nextSessionReadableChartReviewOrder,
      tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn"
    },
    {
      label: "安全边界",
      value: "只读回放；生成必须手动按钮；DeepSeek 单独补；不交易、不改操作区",
      tone: "good"
    }
  ];
  const nextSessionTaskSourceReadbackItems: MetricItem[] = [
    {
      label: "来源 task",
      value: candidateRadarSourceTaskLabel,
      tone: candidateRadarSourceTaskLabel.includes("等待") ? "warn" : "good"
    },
    {
      label: "确认回执",
      value: candidateRadarConfirmedTaskReceiptRows.length
        ? `${candidateRadarConfirmedTaskReceiptRows.length} 行已从 CandidateRadar cache 回放`
        : "等待 search_quant_projection_confirmed_task_receipt_rows",
      tone: candidateRadarConfirmedTaskReceiptRows.length ? "good" : "warn"
    },
    {
      label: "任务回放",
      value: candidateRadarTaskReadbackRows.length
        ? `${candidateRadarTaskReadbackRows.length} 行 task_readback 已回放`
        : "等待 search_quant_projection_task_readback_rows",
      tone: candidateRadarTaskReadbackRows.length ? "good" : "warn"
    },
    {
      label: "读取边界",
      value: "图谱页只读 CandidateRadar cache；不创建第二个 task、不补调 Tushare/DeepSeek、不改操作区",
      tone: "good"
    }
  ];
  const ordinaryResultReplayStatus = String(
    packet.ordinary_result_replay_status ??
      (
        chartSummary.has_drawable_data === true
          ? "ready_cache_replay"
          : candidateRadarReadableResultReady
            ? "candidate_readable_result_replay_chart_pending"
            : "waiting_for_cache_or_manual_task"
      )
  );
  const fallbackOrdinaryResultReplayRows = [
    {
      step: "1",
      surface: "下一票雷达",
      readable_result: chartSummary.has_drawable_data === true ? "可从已确认标的继续复核" : "先回到雷达输入代码并点击确认",
      evidence: "候选池和搜票确认按钮在 #candidates；本页不扫描、不搜票。",
      next_step: "需要新标的时回到下一票雷达确认代码。",
      boundary: "输入和页面打开不外联；只有确认按钮可创建 Tushare-first 后台 task。"
    },
    {
      step: "2",
      surface: "股票量化推演",
      readable_result: chartSummary.uses_real_daily_close === true ? "上游 Tushare daily close 已在本地缓存参与图谱" : "等待上游 Tushare ledger 或本地阻断回放",
      evidence: nextSessionTushareSourceLabel,
      next_step: "先看支持/压制摘要，再回到次日图谱复核路径和操作区。",
      boundary: "本页只读 cache，不补调 Tushare 或 DeepSeek；DeepSeek governed executor 单独补。"
    },
    {
      step: "3",
      surface: "次日图谱",
      readable_result: chartSummary.has_drawable_data === true
        ? `情景=${String(chartSummary.scenario_series_count ?? 0)} / 参考线=${String(chartSummary.reference_line_count ?? 0)} / 操作区=${String(chartSummary.operation_zone_count ?? 0)}`
        : candidateRadarReadableResultReady ? candidateRadarReadableResult : "暂无可绘制图谱；可手动生成本地任务。",
      evidence: candidateRadarReadableResultReady ? "CandidateRadar ordinary_result_quick_read_rows / interpretation_summary" : nextSessionLastCache,
      next_step: nextSessionReadableChartReviewOrder,
      boundary: nextSessionOperationZoneBoundary
    }
  ];
  const ordinaryResultReplayRows = packetOrdinaryResultReplayRows.length
    ? packetOrdinaryResultReplayRows
    : fallbackOrdinaryResultReplayRows;
  const nextSessionResultHandoffRows = [
    {
      交接段: "1. 来源",
      当前状态: nextSessionReplayOrigin,
      用户下一步: "先确认这张图谱来自下一票雷达 / 股票量化推演后的本地回放。",
      边界: "只读本地次日图谱数据；不会从页面打开或普通链接创建任务。"
    },
    {
      交接段: "2. 结论",
      当前状态: nextSessionReadableLastResultLabel,
      用户下一步: chartSummary.has_drawable_data === true ? "先读图表路径和参考线，再看操作区。" : nextSessionReadableChartReviewOrder,
      边界: nextSessionResearchOnlyLabel
    },
    {
      交接段: "3. 缺口",
      当前状态: nextSessionMissingEvidence,
      用户下一步: "缺口回到下一票雷达或股票量化推演补证；不要把空图谱解释成无风险。",
      边界: "缺口只提示下一步；GET cache 和 React render 不补调 Tushare、DeepSeek 或 GitHub。"
    },
    {
      交接段: "4. 操作区",
      当前状态: nextSessionOperationZoneBoundary,
      用户下一步: "把操作区当条件区间和复核提示，继续人工判断。",
      边界: "操作区不是买卖指令，不下单，不写 strategy action。"
    }
  ];
  const nextSessionP3OneMinuteReadRows = [
    {
      读图顺序: "1. 来源",
      当前状态: nextSessionReplayOrigin,
      用户下一步: "确认来源来自下一票雷达 / 股票量化推演后的本地回放。",
      证据: "本地次日图谱数据 / chart_summary",
      边界: "GET cache 只读；不创建 task、不调用 Tushare/DeepSeek/GitHub。"
    },
    {
      读图顺序: "2. 可读结论",
      当前状态: nextSessionReadableLastResultLabel,
      用户下一步: chartSummary.has_drawable_data === true ? "先读图表路径和参考线，再读操作区。" : nextSessionReadableChartReviewOrder,
      证据: candidateRadarReadableResultReady ? "CandidateRadar readable result fallback" : "chart_summary",
      边界: nextSessionResearchOnlyLabel
    },
    {
      读图顺序: "3. 操作区",
      当前状态: Number(chartSummary.operation_zone_count ?? 0) > 0
        ? `操作区 ${String(chartSummary.operation_zone_count ?? 0)} 个；只表示条件区间和复核提示`
        : "等待操作区 cache；不能把空操作区解释成无风险",
      用户下一步: "把操作区当条件区间复核。",
      证据: "chart_payload.operation_zones",
      边界: nextSessionOperationZoneBoundary
    },
    {
      读图顺序: "4. 缺口",
      当前状态: nextSessionMissingEvidence,
      用户下一步: "缺口回到下一票雷达或股票量化推演补证。",
      证据: "production_stage_scope / browser QA / real close evidence",
      边界: "缺口只提示下一步；GET cache 和 React render 不补调 provider/model。"
    },
    {
      读图顺序: "5. 回流",
      当前状态: nextSessionChartReviewOrder,
      用户下一步: "需要换标的回下一票雷达；需要支持/压制回股票量化推演。",
      证据: "local route handoff #candidates/.../#factor",
      边界: nextSessionReplayDestinationBoundary
    }
  ];
  const nextSessionUpstreamOneScreenRows = candidateRadarOneScreenRows.length
    ? candidateRadarOneScreenRows.map((row) => ({
        行动: String(row["行动"] ?? row.action_key ?? "行动"),
        当前状态: String(row["当前状态"] ?? row.status ?? "等待上游回放"),
        用户下一步: String(row["用户下一步"] ?? row.next_action ?? nextSessionChartReviewOrder),
        入口: String(row["入口"] ?? row.entry ?? "下一票雷达"),
        边界: String(row["边界"] ?? row.boundary ?? "次日图谱页只读回放 CandidateRadar packet；不会从图谱页创建 task 或调用模型。")
      }))
    : [
        {
          行动: "1. 确认",
          当前状态: chartSummary.has_drawable_data === true ? "上游确认链等待 CandidateRadar packet 回放" : "等待下一票雷达确认代码",
          用户下一步: chartSummary.has_drawable_data === true ? nextSessionChartReviewOrder : "回下一票雷达确认输入区输入代码并点击确认按钮",
          入口: "#candidates",
          边界: "图谱页不接收代码输入；换标的必须回下一票雷达确认按钮，链接只做本地切换。"
        },
        {
          行动: "2. 任务",
          当前状态: "等待 CandidateRadar task id / TaskStatusPanel 回放",
          用户下一步: "确认任务完成后刷新本地 cache，再回到次日图谱读路径和操作区",
          入口: "下一票雷达确认按钮 / TaskStatusPanel",
          边界: "只有下一票雷达确认按钮可创建 Tushare-first POST task；图谱页不提交上游 task。"
        },
        {
          行动: "3. 写回",
          当前状态: ordinaryResultReplayStatus,
          用户下一步: "确认 cache、call_ledger、packet 已经能支撑图谱回放",
          入口: "本地次日图谱数据 / call_ledger / packet",
          边界: "写回只读本地 cache / ledger / packet；不补调 provider/model、不展示 token/key。"
        },
        {
          行动: "4. 结果",
          当前状态: nextSessionLastResultLabel,
          用户下一步: nextSessionChartReviewOrder,
          入口: "图表路径 / 参考线 / 操作区",
          边界: nextSessionResearchOnlyLabel
        }
      ];
  const nextSessionUpstreamOneScreenLabel = nextSessionUpstreamOneScreenRows
    .map((row) => `${row.行动}: ${row.当前状态}`)
    .join(" / ");
  const nextSessionUpstreamConfirmOutcomeRows = candidateRadarConfirmOutcomeRows.length
    ? candidateRadarConfirmOutcomeRows.map((row) => ({
        确认结果: String(row["速读项"] ?? row.outcome_key ?? "确认结果"),
        当前状态: String(row["当前状态"] ?? row.status ?? "等待 CandidateRadar 确认结果回放"),
        用户下一步: String(row["用户下一步"] ?? row.next_step ?? nextSessionChartReviewOrder),
        入口: String(row["入口"] ?? row.entry ?? "下一票雷达 / 股票量化推演 / 次日图谱"),
        边界: String(row["边界"] ?? row.boundary ?? "次日图谱只读回放确认结果；不创建 task、不调用 provider/model。")
      }))
    : [
        {
          确认结果: "P1 确认结果",
          当前状态: "等待下一票雷达确认任务回放",
          用户下一步: "回下一票雷达确认输入区输入代码并点击确认按钮。",
          入口: "#candidates",
          边界: "图谱页不接收代码输入；确认按钮之前不创建 Tushare-first task。"
        },
        {
          确认结果: "P2 写回结果",
          当前状态: ordinaryResultReplayStatus,
          用户下一步: "确认 cache / call_ledger / packet 已能支撑图谱回放。",
          入口: "cache / call_ledger / packet",
          边界: "只读本地回放；不补调 Tushare、DeepSeek 或 GitHub。"
        },
        {
          确认结果: "P3 回放结果",
          当前状态: nextSessionLastResultLabel,
          用户下一步: nextSessionChartReviewOrder,
          入口: "次日图谱路径 / 参考线 / 操作区",
          边界: nextSessionResearchOnlyLabel
        }
      ];
  const nextSessionUpstreamConfirmOutcomeLabel = nextSessionUpstreamConfirmOutcomeRows
    .map((row) => `${row.确认结果}: ${row.当前状态}`)
    .join(" / ");
  const empty = !loading && !error && !candidateRadarReadableResultReady && (packet.status === "cache_missing" || !Object.keys(packet).length);
  const nextSessionOrdinaryReplayBoundaryBlocked =
    packet.does_not_modify_action === false || packet.does_not_modify_operation_zones === false;
  const fallbackNextSessionOperationZoneQuickReadRows = [
    {
      速读项: "1. 先读路径",
      当前状态: chartSummary.has_drawable_data === true ? nextSessionLastResultLabel : "暂无可绘制路径；先看缓存状态或手动生成任务",
      用户下一步: "先看图表路径和参考线，再看操作区对哪些条件敏感。",
      边界: "只读 chart cache；不重算价格、不调用 Tushare/DeepSeek、不写 cache。"
    },
    {
      速读项: "2. 再读操作区",
      当前状态: Number(chartSummary.operation_zone_count ?? 0) > 0
        ? `操作区 ${String(chartSummary.operation_zone_count ?? 0)} 个；只表示条件区间和复核提示`
        : "等待操作区 cache；不能把空操作区解释成无风险",
      用户下一步: "把操作区当作人工复核条件，回到证据和风险来源确认。",
      边界: nextSessionOperationZoneBoundary
    },
    {
      速读项: "3. 动作隔离",
      当前状态: nextSessionOrdinaryReplayBoundaryBlocked ? "边界异常：先停在审计检查" : "边界正常：前端只读，不改 action 或操作区",
      用户下一步: nextSessionOrdinaryReplayBoundaryBlocked ? "不要继续解释图谱；先看开发审计里的边界异常" : "继续按缺口和仅供研究边界复核。",
      边界: "次日图谱不下单、不写 strategy action；DeepSeek 也不能覆盖操作区。"
    }
  ];
  const nextSessionOperationZoneQuickReadRows = packetOrdinaryConditionQuickReadRows.length
    ? packetOrdinaryConditionQuickReadRows
    : fallbackNextSessionOperationZoneQuickReadRows;
  const ordinaryInterpretationActionRows = [
    {
      行动: "1. 确认图谱状态",
      当前状态: chartSummary.has_drawable_data === true ? "可绘制图谱已从本地 cache 回放" : "暂无可绘制图谱",
      用户下一步: chartSummary.has_drawable_data === true ? "继续看图表路径和参考线" : "先查看缓存状态或点击生成任务",
      证据: nextSessionLastResultLabel,
      边界: "只读 chart_summary；不创建 task、不调用 Tushare/DeepSeek/GitHub。"
    },
    {
      行动: "2. 读路径和参考线",
      当前状态: chartSummary.has_drawable_data === true
        ? `情景路径 ${String(chartSummary.scenario_series_count ?? 0)} 条 / 参考线 ${String(chartSummary.reference_line_count ?? 0)} 条`
        : "等待 scenario_series / reference_lines cache",
      用户下一步: "用路径方向和最新收盘锚点解释压力/支撑，不生成买卖动作",
      证据: latestCloseAnchor.price ? `latest close=${String(latestCloseAnchor.price)}` : nextSessionLastCache,
      边界: "只解释本地路径和参考线；不重算价格、不写 strategy action。"
    },
    {
      行动: "3. 读操作区",
      当前状态: chartSummary.has_drawable_data === true
        ? `操作区 ${String(chartSummary.operation_zone_count ?? 0)} 个`
        : "等待操作区 cache",
      用户下一步: "把操作区当条件区间和复核提示，回到风险/证据源确认",
      证据: nextSessionOperationZoneBoundary,
      边界: "不改操作区、不下单、不把区域当交易指令。"
    },
    {
      行动: "4. 读缺口并回流",
      当前状态: nextSessionMissingEvidence,
      用户下一步: "缺口回到下一票雷达或股票量化推演补证；不要把空图谱解释成无风险",
      证据: "replacement / browser QA / retained signal / real close evidence",
      边界: "缺口只提示后续按钮门控补证；GET cache 和 React render 不补调 provider/model。"
    }
  ];
  const ordinaryDeepSeekGovernanceRows = [
    {
      治理段: "数据源边界",
      当前状态: "次日图谱只读取 chart cache、reference_lines 和操作区",
      用户下一步: "先按图谱路径、参考线和操作区复核基础结果",
      边界: "DeepSeek 不作为数据源，不覆盖图谱路径、价格、参考线或操作区。"
    },
    {
      治理段: "模型状态",
      当前状态: nextSessionDeepSeekSourceLabel,
      用户下一步: "governed executor 完成前只看 skipped/pending/ready 状态",
      边界: "普通页不展示 prompt/output，不从页面渲染调用模型。"
    },
    {
      治理段: "阻塞关系",
      当前状态: "P5 DeepSeek 不阻塞 Tushare-first、Factor cache 或次日基础图谱",
      用户下一步: "基础图谱先行；模型解释作为后续单独补证",
      边界: "模型缺口不能把空图谱解释成无风险，也不能生成 strategy action。"
    },
    {
      治理段: "真实调用门槛",
      当前状态: "等待 governed executor、model_ledger、结构化输出和成本证据",
      用户下一步: "未来只在受控按钮任务或 executor 中补模型证据",
      边界: "GET cache、React render 和普通链接都不调用 DeepSeek。"
    }
  ];
  const fallbackOrdinaryChartReviewRows = [
    {
      复核项: "图表路径",
      看什么: chartSummary.has_drawable_data === true
        ? `情景路径 ${String(chartSummary.scenario_series_count ?? 0)} 条；先看基准、乐观和压力路径的方向`
        : "暂无可绘制路径；先看缓存状态或点击生成任务",
      证据: nextSessionLastCache,
      边界: "只读取图表路径；不重算价格、不调用数据源或模型"
    },
    {
      复核项: "参考线",
      看什么: chartSummary.has_drawable_data === true
        ? `参考线 ${String(chartSummary.reference_line_count ?? 0)} 条；用于定位压力、支撑和最新收盘锚点`
        : "等待 reference_lines 写入本地 cache",
      证据: latestCloseAnchor.price ? `latest close=${String(latestCloseAnchor.price)}` : "等待 latest close anchor",
      边界: "参考线只作研究复核，不生成买卖动作"
    },
    {
      复核项: "操作区",
      看什么: chartSummary.has_drawable_data === true
        ? `操作区 ${String(chartSummary.operation_zone_count ?? 0)} 个；只看条件区间、触发条件和风险提示`
        : "等待操作区 cache",
      证据: nextSessionOperationZoneBoundary,
      边界: "不改操作区、不下单、不写 strategy action"
    },
    {
      复核项: "缺少证据",
      看什么: nextSessionMissingEvidence,
      证据: "replacement / browser QA / retained signal / real close evidence",
      边界: "缺口只提示后续补证，不把空结果解释成无风险"
    }
  ];
  const ordinaryChartReviewRows = packetOrdinaryChartReviewRows.length
    ? packetOrdinaryChartReviewRows
    : fallbackOrdinaryChartReviewRows;
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
    { boundary: "does_not_modify_operation_zones", value: String(packet.does_not_modify_operation_zones !== false), note: "前端只读，不改操作区。" },
    { boundary: "is_exact_next_session_packet", value: String(chartPayload?.is_exact_next_session_packet === true), note: "非精确 packet 时只显示 legacy/cache 投影。" },
    { boundary: "uses_real_daily_close", value: String(chartPayload?.uses_real_daily_close === true), note: "未验证真实 close 时必须展示风险提示。" }
  ];
  const nextSessionOrdinaryReplayRailState = [
    chartSummary.has_drawable_data === true ? "chart_cache_visible" : "chart_cache_waiting",
    chartSummary.is_exact_next_session_packet === true ? "exact_packet_visible" : "legacy_projection_or_missing",
    Number(chartSummary.operation_zone_count ?? 0) > 0 ? "operation_zones_visible" : "operation_zones_waiting",
    nextSessionMissingEvidence === "当前摘要未标记缺口" ? "evidence_gap_clear" : "evidence_gap_visible",
    nextSessionOrdinaryReplayBoundaryBlocked ? "research_boundary_blocked" : "research_boundary_ready"
  ].join(" ");
  const nextSessionOrdinaryReplayRailSteps = [
    {
      label: "雷达/量化回放",
      state: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? ("done" as const) : empty ? ("waiting" as const) : ("active" as const),
      detail: nextSessionReplayOrigin
    },
    {
      label: "图表路径",
      state: chartSummary.has_drawable_data === true ? ("done" as const) : candidateRadarReadableResultReady ? ("active" as const) : ("waiting" as const),
      detail: nextSessionReadableLastResultLabel
    },
    {
      label: "操作区",
      state: Number(chartSummary.operation_zone_count ?? 0) > 0 ? ("done" as const) : chartSummary.has_drawable_data === true ? ("active" as const) : ("waiting" as const),
      detail: nextSessionOperationZoneBoundary
    },
    {
      label: "缺口边界",
      state: nextSessionOrdinaryReplayBoundaryBlocked
        ? ("blocked" as const)
        : nextSessionMissingEvidence === "当前摘要未标记缺口" ? ("done" as const) : ("active" as const),
      detail: `${nextSessionMissingEvidence}；${nextSessionResearchOnlyLabel}`
    }
  ];
  const nextSessionOrdinaryReviewCompassItems: MetricItem[] = [
    {
      label: "先看哪里",
      value: chartSummary.has_drawable_data === true ? "图表路径和参考线" : "最近搜票结论和缓存状态",
      tone: chartSummary.has_drawable_data === true ? "good" : "warn"
    },
    {
      label: "再看什么",
      value: Number(chartSummary.operation_zone_count ?? 0) > 0
        ? `操作区 ${String(chartSummary.operation_zone_count ?? 0)} 个`
        : "操作区等待缓存",
      tone: Number(chartSummary.operation_zone_count ?? 0) > 0 ? "good" : "warn"
    },
    { label: "怎么判断", value: nextSessionMissingEvidence === "当前摘要未标记缺口" ? "按路径、参考线、操作区复核" : "先读缺口，再回流补证", tone: nextSessionMissingEvidence === "当前摘要未标记缺口" ? "good" : "warn" },
    { label: "回流入口", value: candidateRadarConfirmedSymbol ? "换标的回雷达；看因子回量化推演" : "先回下一票雷达确认标的" },
    { label: "只读来源", value: nextSessionReplayOrigin },
    { label: "安全边界", value: "条件区间不是买卖或下单指令", tone: "good" }
  ];
  const nextSessionOrdinaryReviewCompassRows = [
    {
      复核顺序: "1. 图表路径",
      看什么: chartSummary.has_drawable_data === true ? nextSessionLastResultLabel : "暂无完整图谱时先读最近搜票可读结论和缓存状态",
      用户下一步: chartSummary.has_drawable_data === true ? "看情景路径和参考线，再进入操作区复核。" : "需要完整图谱时先确认标的，再用手动生成按钮。",
      入口: "#next-session-chart",
      边界: "只读本地 chart cache；不会从页面打开或链接切换创建任务。"
    },
    {
      复核顺序: "2. 参考线和操作区",
      看什么: Number(chartSummary.operation_zone_count ?? 0) > 0
        ? `操作区 ${String(chartSummary.operation_zone_count ?? 0)} 个；只表示条件区间和复核提示`
        : "等待操作区 cache；不能把空操作区解释成无风险",
      用户下一步: "把操作区当条件区间，回到证据来源和缺口确认。",
      入口: "#next-session-chart",
      边界: nextSessionOperationZoneBoundary
    },
    {
      复核顺序: "3. 缺口和回流",
      看什么: nextSessionMissingEvidence,
      用户下一步: candidateRadarConfirmedSymbol ? "需要换标的回下一票雷达；需要支持/压制回股票量化推演。" : "先回下一票雷达确认输入区，确认标的后再读图。",
      入口: "#candidates / #factor",
      边界: "缺口只提示后续补证；GET cache、React render 和普通链接不补调 provider/model。"
    },
    {
      复核顺序: "4. 仅供研究",
      看什么: nextSessionResearchOnlyLabel,
      用户下一步: "人工复核条件和证据，不把图谱当买入、卖出、下单或加仓指令。",
      入口: "本页普通摘要",
      边界: "不真实交易、不下单、不改 strategy action 或操作区。"
    }
  ];
  const nextSessionEvidenceFactoryItems: MetricItem[] = [
    {
      label: "Browser QA review",
      value: String(browserQaReview.status ?? "browser_qa_review_pending"),
      tone: browserQaReview.local_browser_qa_review_ready === true ? "good" : "warn"
    },
    {
      label: "Coverage review",
      value: String(streamlitParityReview.status ?? "retained_coverage_review_pending"),
      tone: streamlitParityReview.local_streamlit_parity_review_ready === true || streamlitParityReview.same_packet_no_loss_review_ready === true ? "good" : "warn"
    },
    {
      label: "Promotion review",
      value: String(productionPromotionReview.status ?? "production_promotion_review_pending"),
      tone: productionPromotionReview.local_production_promotion_review_ready === true ? "good" : "warn"
    },
    {
      label: "Stage scope",
      value: `${String(productionStageScope.direct_evidence_stage_count ?? 0)} direct / ${String(productionStageScope.pending_stage_count ?? 0)} pending`,
      tone: Number(productionStageScope.pending_stage_count ?? 0) > 0 ? "warn" : "good"
    },
    {
      label: "生产边界",
      value: "只审查本地 artifact、同包 coverage 和 promotion blocker；不打开浏览器、不写 artifact、不完成 production replacement",
      tone: "good"
    },
    { label: "交易边界", value: nextSessionResearchOnlyLabel, tone: "good" }
  ];

  return (
    <>
    <PacketCard title="普通用户次日图谱摘要" subtitle="下一步、来源、缺口、边界和最近结果" status={nextSessionReadableStatusLabel}>
      <div aria-label="next session app first research read">
        <h3>本地投研速读</h3>
        <p className="ordinary-status-note" aria-label="next session app first research read sentence" aria-live="polite">{ordinaryNextText(nextSessionAppFirstResearchReadSentence)}</p>
        <MetricGrid items={ordinaryNextMetricItems(nextSessionAppFirstResearchReadItems)} />
        <div className="actions" aria-label="next session app first research read actions">
          <a href={nextSessionOrdinaryProgressCheckpointAnchor} title="跳到当前最短可读位置；只切换本地锚点" aria-label="open current next session research read target">{nextSessionOrdinaryProgressCheckpointLabel}</a>
          <a href="#next-session-chart" title="跳到完整次日图谱区域；只读本地次日图谱数据" aria-label="open chart from next session research read">图谱区域</a>
          <a href="#factor" title="切换到股票量化推演模块；只读 Factor cache 回放" aria-label="open factor from next session research read">支持/压制</a>
          <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="return candidate radar from next session research read">确认或换一只票</a>
        </div>
        <p className="risk-note">这张首屏只回答用户打开次日图谱能先读什么：路径、参考线、操作区、缺口和下一步入口；链接只切换本地页面或锚点，不创建后台流程、不刷新外部数据或模型、不真实交易。</p>
      </div>
      {(loading || error || empty) ? (
        <div className="page-state page-state-empty motion-surface" data-page-state="next_session_ordinary_cache_state" data-motion-scope="ordinary_user_next_session_clarity" data-motion-purpose="readable_cache_state">
          <strong>{loading ? "正在读取本地图谱" : error ? "本地图谱待补" : "暂无已缓存次日操作图谱"}</strong>
          <p>{ordinaryNextText(error ? cacheMissingMessage || error : loading ? "正在读取本地图谱；页面不会自动刷新外部数据或模型。" : "请回下一票雷达确认股票，或使用手动按钮生成本地图谱；查看缓存不会刷新外部数据。")}</p>
          <MetricGrid
            items={ordinaryNextMetricItems([
              { label: "当前状态", value: loading ? "正在读取本地图谱" : error ? "本地图谱待补" : "等待本地图谱" },
              { label: "下一步", value: candidateRadarConfirmedSymbol ? "查看缓存或手动生成本地图谱" : "先回下一票雷达确认股票" },
              { label: "安全边界", value: "页面打开只读本地缓存；不刷新外部数据或模型、不交易" }
            ])}
          />
        </div>
      ) : null}
      <div aria-label="next session ordinary plain conclusion">
        <h3>普通结论</h3>
        <p className="ordinary-status-note" aria-label="next session ordinary plain conclusion sentence" aria-live="polite">{ordinaryNextText(nextSessionPlainConclusion)}</p>
        <MetricGrid items={ordinaryNextMetricItems(nextSessionPlainConclusionItems)} />
        <p className="risk-note">普通结论只读本地次日图谱和上游确认结果；页面打开、查看结果和切换入口都不会自动创建任务、调用外部服务或改写操作区。</p>
      </div>
      <div aria-label="next session first screen readable decision">
        <h3>一眼结论</h3>
        <p className="ordinary-status-note" aria-label="next session first screen readable sentence" aria-live="polite">{ordinaryNextText(nextSessionFirstScreenReadableSentence)}</p>
        <MetricGrid items={ordinaryNextMetricItems(nextSessionFirstScreenItems)} />
        <div className="actions" aria-label="next session first screen safe actions">
          <a href={nextSessionOrdinaryProgressCheckpointAnchor} aria-label="open next session first screen primary next step">{nextSessionOrdinaryProgressCheckpointLabel}</a>
          <button onClick={refreshCache} title={nextSessionCacheButtonLabel} aria-label="refresh next session cache from first screen">查看缓存</button>
          <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="return candidate radar confirm input from next session first screen">换标的</a>
        </div>
        <p className="risk-note">首屏只汇总当前股票、最近结果、下一步、缺口原因和操作区边界；查看缓存只读本地缓存，链接只切换本地锚点，不创建后台流程、不刷新外部数据或模型、不下单。</p>
      </div>
      <div aria-label="next session post confirm one minute chart read">
        <h3>确认后一眼读图</h3>
        <p className="ordinary-status-note" aria-label="next session post confirm one minute sentence" aria-live="polite">{ordinaryNextText(nextSessionPostConfirmOneMinuteSentence)}</p>
        <MetricGrid items={ordinaryNextMetricItems(nextSessionPostConfirmOneMinuteItems)} />
        <div className="actions" aria-label="next session post confirm one minute actions">
          <a href="#next-session-chart" title="跳到完整次日图谱区域；只读本地次日图谱数据" aria-label="open next session chart from post confirm one minute read">看图表</a>
          <a href="#factor" title="切换到股票量化推演模块；只读 Factor cache 回放" aria-label="open factor from post confirm one minute read">看支持/压制</a>
          <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="return candidate radar from post confirm one minute read">换一只票</a>
        </div>
        <p className="risk-note">这张一眼读图只读本地次日图谱数据和下一票雷达回放；本地链接只切换页面或锚点，不生成新图谱、不调用外部数据或模型、不交易、不改策略。</p>
      </div>
      <div aria-label="next session app visible now summary">
        <h3>打开 app 能看到什么</h3>
        <p className="ordinary-status-note" aria-label="next session app visible now sentence" aria-live="polite">{ordinaryNextText(nextSessionAppVisibleNowSentence)}</p>
        <MetricGrid items={ordinaryNextMetricItems(nextSessionAppVisibleNowItems)} />
        <div className="actions" aria-label="next session app visible now local actions">
          <a href={nextSessionOrdinaryProgressCheckpointAnchor} title="跳到当前最短可读位置；只切换本地锚点" aria-label="open current visible next session area">{nextSessionOrdinaryProgressCheckpointLabel}</a>
          <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="return candidate radar from visible now summary">换标的</a>
          <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读复核真实数据凭证、权限、空窗口和本地结果包缺口" aria-label="open data capability from next session visible now summary">数据能力</a>
          <a href="#factor" title="切换到股票量化推演模块；只读 Factor cache 回放" aria-label="open factor from visible now summary">看支持/压制</a>
        </div>
        <p className="risk-note">这个条带只回答普通用户打开页面能看到什么：股票、图谱状态、来源层、缺口原因和下一步入口；普通链接只切换本地页面或锚点，不创建后台流程、不刷新外部数据或模型、不交易、不改操作区。</p>
      </div>
      <details className="developer-audit-details" aria-label="next session live light evidence layers">
        <summary>运行模式分层</summary>
        <MetricGrid items={ordinaryNextMetricItems(nextSessionLiveLightEvidenceItems)} />
        <p className="risk-note">轻量实时证据只读本地缓存、下一票雷达回放和任务索引；不会因为页面打开、页面渲染或本地链接刷新外部数据或模型，也不证明长期目标生产替代完成。</p>
      </details>
      <div aria-label="next session ordinary tushare data card">
        <h3>确认后数据链状态</h3>
        <p className="ordinary-status-note" aria-label="next session ordinary tushare data card summary" aria-live="polite">{ordinaryNextText(nextSessionTushareDataCardSummary)}</p>
        <MetricGrid items={ordinaryNextMetricItems(nextSessionTushareDataCardItems)} />
        <details className="developer-audit-details" aria-label="next session ordinary tushare data card rows">
          <summary>接口回放明细</summary>
          <p className="risk-note">这张明细优先读取下一票雷达的普通接口回放；旧缓存缺字段时显示轻量接口回退，不从次日图谱页补调数据。</p>
          <DataLineageTable rows={nextSessionTushareDataCardRows} />
        </details>
        <p className="risk-note">确认后数据链状态只整理已有下一票雷达回放和本地次日图谱缓存；不会创建第二个后台流程、刷新外部数据或模型，不交易、不改操作区或交易动作。</p>
      </div>
      <div aria-label="next session ordinary review compass">
        <h3>次日图谱复核顺序</h3>
        <p className="ordinary-status-note">先看图表路径和参考线，再看操作区条件，最后看缺口和回流入口；这只是研究复核顺序，不是买卖、下单或加仓指令。</p>
        <MetricGrid items={ordinaryNextMetricItems(nextSessionOrdinaryReviewCompassItems)} />
        <div className="actions" aria-label="next session ordinary review compass actions">
          <a href="#next-session-chart" title="跳到本页完整次日图谱区域；只读本地次日图谱数据" aria-label="open chart from next session review compass">看图表</a>
          <a href="#factor" title="切换到股票量化推演模块；只读 Factor cache 回放" aria-label="open factor from next session review compass">看支持/压制</a>
          <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="return candidate radar from next session review compass">换标的</a>
        </div>
        <details className="developer-audit-details" aria-label="next session ordinary review compass rows">
          <summary>复核顺序明细</summary>
          <p className="risk-note">明细只解释本地缓存的读图顺序；不会打开浏览器 QA，不创建 provider/model/worker task，也不证明 LTG-08 production replacement。</p>
          <DataLineageTable rows={nextSessionOrdinaryReviewCompassRows} />
        </details>
        <p className="risk-note">读图罗盘只切换本地锚点和页面入口；本地缓存读取、页面渲染、普通链接都不刷新外部数据或模型，不真实交易，也不改操作区或 strategy action。</p>
      </div>
      <details className="developer-audit-details" aria-label="next session ordinary evidence factory task strip">
        <summary>研究辅助 / 审计按钮</summary>
        <h3>LTG-08 本地证据按钮</h3>
        <p className="ordinary-status-note" aria-label="next session ordinary evidence factory sentence">
          用户现在可以从首屏读取本地 browser QA artifact、same-packet retained signal/capability coverage 和 promotion blocker 的审查状态；这些按钮只创建本地 review task，不打开浏览器、不写 artifact、不调用 provider/model/GitHub。
        </p>
        <MetricGrid items={nextSessionEvidenceFactoryItems} />
        <div className="actions" aria-label="next session ordinary evidence factory actions">
          <button onClick={reviewBrowserQa} title="只读取 ignored 本地 QA artifact 摘要，不打开浏览器或写截图" aria-label="review next session local browser qa evidence from first screen">审查 QA artifact</button>
          <button onClick={reviewStreamlitParity} title="只审查同包 retained signal/capability coverage，不复制旧 Streamlit UI" aria-label="review next session same packet retained coverage from first screen">审查 same-packet coverage</button>
          <button onClick={reviewProductionPromotion} title="只审查本地 production promotion blocker，不推广生产替代" aria-label="review next session promotion blockers from first screen">审查 promotion blocker</button>
          <a href="#next-session-audit" aria-label="open next session audit evidence details from first screen">查看审计详情</a>
        </div>
        <TaskLaunchReceipt receipt={browserQaReceipt} />
        <TaskStatusPanel taskId={browserQaTaskId} onSuccess={refreshCache} />
        <TaskLaunchReceipt receipt={streamlitParityReceipt} />
        <TaskStatusPanel taskId={streamlitParityTaskId} onSuccess={refreshCache} />
        <TaskLaunchReceipt receipt={productionPromotionReceipt} />
        <TaskStatusPanel taskId={productionPromotionTaskId} onSuccess={refreshCache} />
        <p className="risk-note">LTG-08 首屏按钮是显式 POST local review task：不打开浏览器、不写 screenshots/report artifact、不调用 Tushare/DeepSeek/GitHub，不真实交易，不改操作区或 strategy action；local review 仍不是 production replacement complete。</p>
      </details>
      <MetricGrid
        items={[
          { label: "主下一步", value: nextSessionReadableNextClick },
          { label: "当前标的", value: candidateRadarConfirmedSymbolLabel, tone: candidateRadarConfirmedSymbol ? "good" : "warn" },
          { label: "本地缓存", value: nextSessionCacheSourceLabel },
          { label: "数据链", value: nextSessionTushareSourceLabel },
          { label: "解释状态", value: nextSessionDeepSeekSourceLabel },
          { label: "P5 解释治理", value: nextSessionP5GovernanceLabel, tone: "good" },
          { label: "待补证据", value: nextSessionPendingSourceLabel, tone: Number(productionStageScope.pending_stage_count ?? 0) > 0 ? "warn" : "good" },
          { label: "降级提示", value: nextSessionDegradedSourceLabel, tone: chartSummary.is_exact_next_session_packet === true ? "good" : "warn" },
          { label: "缺少证据", value: nextSessionMissingEvidence, tone: nextSessionMissingEvidence === "当前摘要未标记缺口" ? "good" : "warn" },
          { label: "最近结果", value: nextSessionReadableLastResultLabel },
          { label: "查看顺序", value: nextSessionReadableChartReviewOrder },
          { label: "回放来源", value: nextSessionReplayOrigin, tone: chartSummary.is_exact_next_session_packet === true ? "good" : "warn" },
          { label: "上游确认链", value: nextSessionUpstreamOneScreenLabel, tone: candidateRadarOneScreenRows.length ? "good" : "warn" },
          { label: "确认结果链", value: nextSessionUpstreamConfirmOutcomeLabel, tone: candidateRadarConfirmOutcomeRows.length ? "good" : "warn" },
          { label: "最近搜票结论", value: candidateRadarReadableResult, tone: candidateRadarInterpretation.interpretation_ready === true ? "good" : "warn" },
          { label: "回放路径", value: nextSessionReplayPath, tone: "good" },
          { label: "回放入口边界", value: nextSessionReplayDestinationBoundary, tone: "good" },
          { label: "操作区边界", value: nextSessionOperationZoneBoundary, tone: "good" },
          { label: "结果回放", value: ordinaryResultReplayStatus, tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn" },
          { label: "生成血缘", value: nextSessionGeneratePayload.source_task_id ? `${nextSessionGeneratePayload.symbol} / ${nextSessionGeneratePayload.source_task_id}` : "等待确认标的后再绑定生成任务", tone: nextSessionGeneratePayload.source_task_id ? "good" : "warn" },
          { label: "任务边界", value: nextSessionTaskBoundary, tone: "good" },
          { label: "仅供研究", value: nextSessionResearchOnlyLabel },
          { label: "P3 可读结论", value: nextSessionReadableLastResultLabel, tone: chartSummary.has_drawable_data === true || candidateRadarReadableResultReady ? "good" : "warn" },
          { label: "P3 下一步", value: nextSessionReadableChartReviewOrder },
          { label: "P3 边界", value: nextSessionResearchOnlyLabel, tone: "good" }
        ]}
      />
      <div aria-label="next session ordinary usable now strip">
        <h3>现在可读状态</h3>
        <MetricGrid items={nextSessionUsableNowItems} />
        <p className="risk-note">这条只合成图谱可绘制、P3 结论、P2 三面、操作区和下一步；不创建 task、不调用 Tushare/DeepSeek、不改操作区或 strategy action。</p>
      </div>
      <details className="developer-audit-details" aria-label="next session local task index progress watch">
        <summary>研究辅助 / 本地进度</summary>
        <h3>本地任务进度</h3>
        <MetricGrid items={nextSessionTaskIndexProgressItems} />
        <div className="actions" aria-label="next session local task index progress actions">
          <a href="#tasks" title="切换到任务目录；只读查看本地 task 进度" aria-label="open task catalog from next session progress watch">任务目录</a>
          <a href="#next-session-chart" title="跳到本页完整次日图谱区域；只读本地次日图谱数据" aria-label="open chart area from next session progress watch">图谱区域</a>
          <a href="#factor" title="切换到股票量化推演模块；只读 Factor cache 回放" aria-label="open stock quant from next session progress watch">股票量化推演</a>
        </div>
        <p className="risk-note">边用边看：{nextSessionProgressWatchNext}；这只来自 GET /api/tasks、本地次日图谱数据和 CandidateRadar cache，不创建第二个 task、不补调 Tushare/DeepSeek、不真实交易，也不改操作区。</p>
      </details>
      <div aria-label="next session ordinary progress checkpoint">
        <h3>当前图谱 checkpoint</h3>
        <MetricGrid items={nextSessionOrdinaryProgressCheckpointItems} />
        <div className="actions" aria-label="next session ordinary progress checkpoint actions">
          <a href={nextSessionOrdinaryProgressCheckpointAnchor} aria-label="open next session ordinary progress checkpoint next step">{nextSessionOrdinaryProgressCheckpointLabel}</a>
          <a href="#next-session-chart" title="跳到本页完整次日图谱区域；只读本地次日图谱数据" aria-label="open chart area from next session checkpoint">图谱区域</a>
          <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="return candidate radar confirm input from next session checkpoint">下一票雷达确认</a>
        </div>
        <p className="risk-note">checkpoint 只汇总下一票雷达上游结论、来源流程、图谱状态和下一步入口；链接只切换本地页面或锚点，不创建 task、不调用 Tushare/DeepSeek，也不改操作区或交易动作。</p>
      </div>
      <StateClarityRail
        label="next session ordinary replay status"
        state={nextSessionOrdinaryReplayRailState}
        steps={nextSessionOrdinaryReplayRailSteps}
      />
      <p className="risk-note">普通图谱状态：雷达/量化回放 / 图表路径 / 操作区 / 缺口边界；这条状态轨只读本地次日图谱数据，不创建 task、不补调 Tushare 或 DeepSeek，P5 解释治理继续收起为单独补证。</p>
      <div aria-label="next session latest candidate readable result">
        <h3>最近搜票可读结论</h3>
        <p className="ordinary-status-note" aria-label="next session latest candidate readable sentence" aria-live="polite">{nextSessionLatestCandidateReadableSentence}</p>
        <p className="risk-note">优先读取 CandidateRadar 的 search_quant_projection_post_confirm_one_glance_items；没有后端一屏结果时，fallback 仍读取 CandidateRadar 的 ordinary_result_quick_read_rows / ordinary_result_handoff_rows，并优先读取 CandidateRadar 的 ordinary_result_quick_read_rows / ordinary_result_handoff_rows 作为可读行，旧 cache 再回退 search_quant_projection_interpretation_summary；确认后的 Tushare-first、P2 三面和 P3 结论在图谱页首屏直接回放。本卡不创建 task、不补调数据源或模型，也不改操作区；只读本地 cache。</p>
        <MetricGrid
          items={nextSessionBackendPostConfirmOneGlanceItems.length ? nextSessionBackendPostConfirmOneGlanceItems : [
            { label: "标的", value: candidateRadarConfirmedSymbolLabel, tone: candidateRadarConfirmedSymbol ? "good" : "warn" },
            { label: "来源任务", value: candidateRadarSourceTaskLabel, tone: candidateRadarSourceTaskLabel.includes("等待") ? "warn" : "good" },
            { label: "可读结论", value: candidateRadarReadableResult, tone: candidateRadarInterpretation.interpretation_ready === true ? "good" : "warn" },
            { label: "下一步", value: candidateRadarReadableNextStep },
            { label: "P2 小数据", value: candidateRadarSmallDataWriteback.small_data_writeback_ready === true ? "CandidateRadar P2 small_data_writeback_ready 已回放" : candidateRadarWritebackSurfaceStatus, tone: candidateRadarWritebackSurfaceReady ? "good" : "warn" },
            { label: "P2 边界", value: candidateRadarWritebackSurfaceBoundary, tone: "good" },
            { label: "DeepSeek", value: candidateRadarOrdinaryDeepSeekState, tone: candidateRadarUsesModelOutput ? "warn" : "good" },
            { label: "边界", value: candidateRadarReadableBoundary, tone: "good" }
          ]}
        />
        <div aria-label="next session p1 task source readback">
          <h3>P1 任务来源回放</h3>
          <p className="risk-note">这张小表只说明 P3 图谱结论来自哪次确认 task，以及确认回执和 task_readback 是否已经本地回放；完整上游链路继续收起。</p>
          <MetricGrid items={nextSessionTaskSourceReadbackItems} />
        </div>
        <div className="actions" aria-label="next session readable result local actions">
          <a href="#next-session-chart" title="跳到本页完整次日图谱区域；只读本地次日图谱数据" aria-label="open local next session chart from readable result">查看图谱区域</a>
          <a href="#factor" title="切换到股票量化推演模块；只读 Factor cache 回放" aria-label="open stock quant replay from next session readable result">查看支持/压制</a>
          <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需输入代码并确认" aria-label="return candidate radar confirm input from next session readable result">回下一票雷达确认</a>
        </div>
        <p className="risk-note">这组入口只切换本地页面或锚点；不创建 task、不调用 Tushare/DeepSeek/GitHub、不写 cache，也不改变操作区或 strategy action。</p>
        {candidateRadarResultQuickRows.length ? <DataLineageTable rows={candidateRadarResultQuickRows} /> : null}
        {candidateRadarResultHandoffRows.length ? <DataLineageTable rows={candidateRadarResultHandoffRows} /> : null}
      </div>
      <div aria-label="next session p3 one minute read">
        <h3>P3 一分钟读图</h3>
        <p className="risk-note">普通用户先看这张表：用一分钟确认来源、可读结论、操作区、缺口和回流入口；它只读本地次日图谱数据。</p>
        <DataLineageTable rows={nextSessionP3OneMinuteReadRows} />
      </div>
      <div aria-label="next session p3 result handoff quick read">
        <h3>P3 结果交接速读</h3>
        <p className="risk-note">先看来源、结论、缺口和操作区边界；这张表只做本地结果交接，不展开 QA、promotion 或 raw packet 审计。</p>
        <DataLineageTable rows={nextSessionResultHandoffRows} />
      </div>
      <div aria-label="next session ordinary operation zone quick read">
        <h3>操作区解释速读</h3>
        <p className="risk-note">普通用户先按路径、参考线、操作区的顺序读；操作区只是条件区间和复核提示，不是买卖、下单或 strategy action。优先读取本地缓存里的条件速读；旧缓存缺字段时才使用前端 fallback。</p>
        <DataLineageTable rows={nextSessionOperationZoneQuickReadRows} />
      </div>
      <details className="developer-audit-details" aria-label="next session upstream readback details">
        <summary>上游确认链路详情</summary>
        <p className="risk-note">普通首屏先读 P3 图谱；上游确认、任务、P2 写回和结果入口的链路回放默认收起，需要排查来源时再展开。</p>
        <div aria-label="next session upstream one screen actions">
          <h3>上游确认一屏行动</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_one_screen_action_rows：确认、任务、写回、结果合成图谱页上游速读；本页只读回放，不创建 task、不调用模型。</p>
          <DataLineageTable rows={nextSessionUpstreamOneScreenRows} />
        </div>
        <div aria-label="next session upstream confirm outcome readback">
          <h3>上游确认结果速读</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_confirm_outcome_rows：确认任务是否接收、P2 三面是否回放、P3 图谱入口是否可读；本页只读回放，不创建第二个 task。</p>
          <DataLineageTable rows={nextSessionUpstreamConfirmOutcomeRows} />
        </div>
      </details>
      <details className="developer-audit-details" aria-label="next session ordinary expanded chart replay details">
        <summary>更多图谱回放明细</summary>
        <p className="risk-note">普通主视图保留 P3 一分钟读图、结果交接和操作区速读；三段回放、解释行动和图谱复核清单默认收起。</p>
        <h3>三段结果回放</h3>
        <p className="risk-note">三段结果回放优先读取服务端 ordinary_result_replay_rows；旧 packet 缺字段时才使用前端 fallback，且两者都只读 cache。</p>
        <DataLineageTable rows={ordinaryResultReplayRows} />
        <div aria-label="next session ordinary interpretation actions">
          <h3>解释性行动清单</h3>
          <p className="risk-note">先确认图谱是否可绘制，再读路径/参考线、操作区和缺口；这些行动只解释本地 cache，不生成交易动作。</p>
          <DataLineageTable rows={ordinaryInterpretationActionRows} />
        </div>
        <div aria-label="next session ordinary chart review checklist">
          <h3>图谱复核清单</h3>
          <p className="risk-note">按图表路径、参考线、操作区、缺少证据复核；优先读取服务端 ordinary_chart_review_rows，只读取本地 chart cache，不触发刷新或交易动作。</p>
          <DataLineageTable rows={ordinaryChartReviewRows} />
        </div>
      </details>
      <details className="developer-audit-details" aria-label="next session ordinary p5 governance details">
        <summary>P5 解释治理单独补证状态</summary>
        <p className="risk-note">普通主线先复核 P3 图谱来源、路径、参考线和操作区；DeepSeek governed executor 状态默认收起，只作为高级补证参考。</p>
        <div aria-label="next session ordinary deepseek governance">
          <h3>解释治理单独补证状态</h3>
          <p className="risk-note">DeepSeek 解释单独补证；基础图谱先按本地 cache 回放，普通页不展示 prompt/output，也不让模型改写图谱或动作。</p>
          <DataLineageTable rows={ordinaryDeepSeekGovernanceRows} />
        </div>
      </details>
      <div className="actions" aria-label="next session replay handoff actions">
        <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="return to candidate radar confirm input">回到下一票雷达确认</a>
        <a href="#factor" title="切换到股票量化推演模块；只读 Factor cache 回放" aria-label="open stock quant projection replay">查看股票量化推演</a>
      </div>
      <div id="next-session-generate-actions" className="actions" aria-label="next session manual generate actions">
        <button onClick={refreshCache} title={nextSessionCacheButtonLabel} aria-label={nextSessionCacheButtonLabel}>查看缓存</button>
        <button onClick={launchTask} disabled={nextSessionGenerateButtonDisabled} title={nextSessionGenerateButtonLabel} aria-label={nextSessionGenerateButtonLabel}>{nextSessionGenerateButtonText}</button>
      </div>
      <p className="risk-note">{nextSessionReplayPath}；这些回放入口只做本地模块路由切换，不创建任务、不刷新 Tushare/DeepSeek。</p>
      <p className="risk-note">摘要里的查看缓存只读取本地 GET cache；生成任务只创建按钮门控 POST task，不调用 Tushare 或 DeepSeek，不写交易动作。</p>
      <p className="risk-note">普通用户先按“图表路径 -&gt; 参考线 -&gt; 操作区 -&gt; 缺少证据”复核；操作区只是条件区间，不是买卖或下单指令。</p>
      <details className="ordinary-audit-shortcuts" aria-label="next session ordinary audit shortcuts">
        <summary>高级诊断入口</summary>
        <p className="risk-note">工程审计明细继续默认收起；QA、promotion、cache ledger 和原始 packet 下沉到 <a href="#next-session-audit">开发审计</a>。</p>
      </details>
    </PacketCard>

    <PacketCard title="LTG-08 next-session strict closeout gate" subtitle="纵切先让本地 ECharts 证据可读；production replacement 仍等待 retained signal/capability 与 durable browser evidence" status="strict_closeout_blocked">
      <p className="ordinary-status-note">production_replacement_complete: false；can_close_ltg08_now: false；strict closeout remains blocked。</p>
      <p className="risk-note">next_authorized_next_session_step: future explicit next-session retained signal/capability coverage and production replacement task。</p>
      <p className="risk-note">LTG-12 boundary: operation zones are conditions, not broker orders or strategy action mutation。</p>
      <p className="risk-note">GET cache / React render / local links do not create tasks, open browsers, write artifacts, call providers/models/GitHub, or trade.</p>
      <DataLineageTable rows={nextSessionStrictCloseoutGateRows} />
    </PacketCard>

    <PacketCard title="次日操作图谱" subtitle="缓存查看不触发外部刷新" status={String(packet.status ?? "cache")}>
      <details className="developer-audit-details" aria-label="next session task receipt details">
        <summary>任务回执详情</summary>
        <p className="ordinary-status-note">普通用户先看任务状态和图谱；本地 POST task 回执、QA 审查回执和 promotion 审查回执默认收起，只作为审计参考。</p>
        <TaskLaunchReceipt receipt={taskReceipt} />
        <TaskLaunchReceipt receipt={browserQaReceipt} />
        <TaskLaunchReceipt receipt={streamlitParityReceipt} />
        <TaskLaunchReceipt receipt={productionPromotionReceipt} />
      </details>
      <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
      <MetricGrid
        items={[
          { label: "状态", value: String(packet.status ?? "cache") },
          { label: "cache source", value: String(packet.cache_source ?? "--") },
          { label: "精确图谱", value: chartSummary.is_exact_next_session_packet === true, tone: chartSummary.is_exact_next_session_packet === true ? "good" : "warn" },
          { label: "真实 close", value: chartSummary.uses_real_daily_close === true, tone: chartSummary.uses_real_daily_close === true ? "good" : "warn" },
          { label: "可绘制", value: chartSummary.has_drawable_data === true, tone: chartSummary.has_drawable_data === true ? "good" : "warn" },
          { label: "情景路径", value: chartSummary.scenario_series_count as number | undefined },
          { label: "参考线", value: chartSummary.reference_line_count as number | undefined },
          { label: "操作区", value: chartSummary.operation_zone_count as number | undefined },
          { label: "历史点", value: chartSummary.historical_point_count as number | undefined },
          { label: "最新 close", value: String(latestCloseAnchor.price ?? "--") },
          { label: "持仓冲突", value: positionConflict.has_conflict === true ? "有" : "无", tone: positionConflict.has_conflict === true ? "bad" : "good" },
          { label: "DeepSeek", value: String(chartPayload?.deepseek_status ?? chartSummary.deepseek_status ?? "not_called"), tone: chartPayload?.deepseek_status === "success" ? "good" : "neutral" },
          { label: "修改 action", value: packet.does_not_modify_action === false ? "会" : "不会", tone: packet.does_not_modify_action === false ? "bad" : "good" },
          { label: "修改 operation_zones", value: packet.does_not_modify_operation_zones === false ? "会" : "不会", tone: packet.does_not_modify_operation_zones === false ? "bad" : "good" }
        ]}
      />
      <p className="risk-note">{String(packet.summary ?? "当前只读取 cache；无缓存时不会触发 Tushare。")}</p>
      <div id="next-session-chart" className="next-session-chart-review" role="region" aria-label={nextSessionChartReviewRegionLabel} title={nextSessionChartReviewRegionLabel}>
        <NextSessionChart payload={chartPayload} />
      </div>
      <details id="next-session-audit" className="developer-audit-details" aria-label="next session developer audit details">
        <summary>开发 / 审计指标</summary>
        <p className="risk-note">普通用户先看上方次日图谱摘要和图表；QA、coverage、promotion、cache ledger 和原始 packet 默认收起。</p>
        <p className="risk-note">审计索引：图表合同、交互审计、交互阻断、信号/能力覆盖、替代激活收据、替代阻断、缺失证据、local_activation_receipt_ready、production_blocker_count、missing_evidence_count、cache envelope ledger、cache warnings。</p>
        <div className="actions" aria-label="next session developer audit gated review actions">
          <button onClick={reviewBrowserQa}>审查本地 QA</button>
          <button onClick={reviewStreamlitParity}>审查信号/能力覆盖</button>
          <button onClick={reviewProductionPromotion}>审查 promotion</button>
        </div>
        <p className="risk-note">这些按钮只创建本地审计 review task；不触发 Tushare、DeepSeek、GitHub、浏览器运行或交易路径。</p>
      <h3>ECharts 图表摘要</h3>
      <DataLineageTable rows={[chartSummary]} />
      <h3>ECharts 交互成熟度审计 / 交互审计 / 交互阻断</h3>
      <DataLineageTable rows={[interactionReadinessAudit]} />
      <DataLineageTable rows={interactionReadinessRows} />
      <h3>ECharts 生产替代激活收据</h3>
      <p className="risk-note">next_session_replacement_activation_receipt 只把 retained signal/capability no-feature-loss coverage review、浏览器视觉 QA、性能 trace、durable evidence 和只读边界串成下一步清单；它不运行浏览器、不调用 provider/model、不证明生产替代完成，也不代表复制旧 Streamlit 图表 UI。</p>
      <p>allowed_next_step: {String(replacementActivation.allowed_next_step ?? "explicit_retained_signal_capability_coverage_browser_visual_performance_review_then_replacement_promotion")}</p>
      <p>production_replacement_complete: {String(replacementActivation.production_replacement_complete === true)}；browser_visual_qa_done: {String(replacementActivation.browser_visual_qa_done === true)}；browser_performance_trace_done: {String(replacementActivation.browser_performance_trace_done === true)}</p>
      <DataLineageTable rows={[replacementActivation]} />
      <DataLineageTable rows={replacementActivationRows} />
      <h3>ECharts 本地浏览器 QA</h3>
      <p className="risk-note">next_session_browser_qa_* 只读取 ignored 本地 runner 报告并支持按钮审查；它不打开浏览器、不提交截图/报告、不替代 retained signal/capability coverage evidence、不证明生产替代完成。</p>
      <p>route: {String(browserQaRunbook.next_route ?? "#next")}；artifact_root: {String(browserQaRunbook.artifact_root ?? ".stock_ming_3/motion_qa")}</p>
      <p>local_browser_qa_review_ready: {String(browserQaReview.local_browser_qa_review_ready === true)}；production_replacement_complete: {String(browserQaReview.production_replacement_complete === true)}；retained_coverage_complete: {String(browserQaReview.streamlit_parity_complete === true)}</p>
      <DataLineageTable rows={[browserQaRunbook]} />
      <DataLineageTable rows={browserQaRunbookRows} />
      <DataLineageTable rows={browserQaMatrixRows} />
      <h3>ECharts 本地 QA 证据摘要</h3>
      <DataLineageTable rows={[browserQaEvidence]} />
      <DataLineageTable rows={browserQaEvidenceRows} />
      <h3>ECharts 本地 QA 审查</h3>
      <DataLineageTable rows={[browserQaReview]} />
      <DataLineageTable rows={browserQaReviewRows} />
      <h3>ECharts same-packet retained signal/capability coverage 审查</h3>
      <p className="risk-note">next_session retained signal/capability no-feature-loss review 只审查本地同包覆盖合同；它不打开 Streamlit、不运行浏览器、不移除 fallback、不证明生产替代完成。</p>
      <p>local_retained_coverage_review_ready: {String(streamlitParityReview.local_streamlit_parity_review_ready === true)}；same_packet_no_loss_review_ready: {String(streamlitParityReview.same_packet_no_loss_review_ready === true)}；retained_coverage_complete: {String(streamlitParityReview.streamlit_parity_complete === true)}</p>
      <DataLineageTable rows={[streamlitParityReview]} />
      <DataLineageTable rows={streamlitParityReviewRows} />
      <h3>ECharts durable evidence recipe</h3>
      <p className="risk-note">next_session_durable_evidence_recipe 只固定生产替代前的直接证据清单；它不打开浏览器、不启动服务、不调用 provider/model、不证明 retained signal/capability coverage evidence、不证明生产替代完成。</p>
      <p>scope: {String(durableEvidenceRecipe.scope ?? "local_next_session_durable_evidence_recipe_no_browser_no_provider")}</p>
      <p>local_recipe_ready: {String(durableEvidenceRecipe.local_recipe_ready === true)}；durable_evidence_complete: {String(durableEvidenceRecipe.durable_evidence_complete === true)}；durable_promotion_ready: {String(durableEvidenceRecipe.durable_promotion_ready === true)}</p>
      <p>allowed_next_step: {String(durableEvidenceRecipe.allowed_next_step ?? "run_same_packet_retained_signal_capability_coverage_then_browser_visual_performance_then_durable_promotion_review")}</p>
      <p>not_allowed_next_steps: {Array.isArray(durableEvidenceRecipe.not_allowed_next_steps) ? durableEvidenceRecipe.not_allowed_next_steps.join(" / ") : "local browser artifact as durable evidence / interaction readiness as coverage completion / provider calls from render / frontend action computation"}</p>
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
      <h3>ECharts 图表数据合同 / 图表合同</h3>
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
      </details>
    </PacketCard>
    </>
  );
}
