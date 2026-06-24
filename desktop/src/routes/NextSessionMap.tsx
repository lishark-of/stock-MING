import { useEffect, useState } from "react";
import { getCandidateRadarCache, getNextSessionCache, postTask, type TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import NextSessionChart from "../components/NextSessionChart";
import PageStateBanner from "../components/PageStateBanner";
import PacketCard from "../components/PacketCard";
import StateClarityRail from "../components/StateClarityRail";
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
  const [candidateRadarCache, setCandidateRadarCache] = useState<Record<string, unknown>>({});
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
  const refreshCandidateRadarCache = () =>
    void getCandidateRadarCache().then((res) => {
      if (res.ok !== false) setCandidateRadarCache(res.data ?? {});
    });

  useEffect(() => {
    refreshCache();
    refreshCandidateRadarCache();
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
  const nextSessionTushareSourceLabel = chartSummary.uses_real_daily_close === true ? "真实 daily close 已在本地缓存" : "待 Tushare/cache 补证";
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
  const nextSessionTaskBoundary = "GET cache 只读；生成或审查都必须走按钮门控 POST task；React 渲染不直连 Tushare 或 DeepSeek，不改 operation_zones";
  const nextSessionResearchOnlyLabel = "次日图谱只解释缓存场景；不是买卖指令，不真实交易、不下单、不改 strategy action";
  const nextSessionChartReviewOrder = chartSummary.has_drawable_data === true
    ? "先看图表路径、参考线和操作区，再看缺少证据；工程审计在开发详情"
    : "先点击生成任务或查看缓存状态；有图表后再按路径、参考线、操作区复核";
  const nextSessionCacheButtonLabel = "查看缓存只读取本地 GET cache；复核顺序是图表路径、参考线、操作区、缺少证据";
  const nextSessionGenerateButtonLabel = "生成任务只创建按钮门控 POST task；完成后按图表路径、参考线、操作区、缺少证据复核";
  const nextSessionChartReviewRegionLabel = "次日图谱复核区域：先看图表路径，再看参考线、操作区和缺少证据";
  const nextSessionReplayOrigin = chartSummary.is_exact_next_session_packet === true
    ? "来自精确 next-session cache；可从下一票雷达/量化推演回放到本页"
    : "来自 legacy/cache 投影或暂无精确 packet；只作降级预览";
  const nextSessionReplayPath =
    "回放路径：下一票雷达确认代码 -> 股票量化推演支持/压制 -> 次日图谱路径/参考线/操作区";
  const nextSessionReplayDestinationBoundary =
    "回放入口只切换本地模块路由（#candidates/#factor）；不创建 task、不调用 Tushare/DeepSeek、不写 cache、不改 operation_zones";
  const nextSessionOperationZoneBoundary = "operation_zones 只表示条件区间和复核提示；不是买卖指令，不写交易动作，不改 strategy action";
  const packetOrdinaryResultReplayRows = rowsFromArray(packet.ordinary_result_replay_rows);
  const packetOrdinaryChartReviewRows = rowsFromArray(packet.ordinary_chart_review_rows);
  const packetOrdinaryConditionQuickReadRows = rowsFromArray(packet.ordinary_condition_quick_read_rows);
  const candidateRadarSmallDataWriteback = (candidateRadarCache.search_quant_projection_small_data_writeback_summary as Record<string, unknown> | undefined) ?? {};
  const candidateRadarOneScreenRows = rowsFromArray(candidateRadarSmallDataWriteback.ordinary_one_screen_action_rows);
  const candidateRadarConfirmOutcomeRows = rowsFromArray(candidateRadarSmallDataWriteback.ordinary_confirm_outcome_rows);
  const candidateRadarInterpretation = (candidateRadarCache.search_quant_projection_interpretation_summary as Record<string, unknown> | undefined) ?? {};
  const candidateRadarReceipt = (candidateRadarCache.search_quant_projection_receipt as Record<string, unknown> | undefined) ?? {};
  const candidateRadarResultQuickRows = rowsFromArray(
    candidateRadarCache.ordinary_result_quick_read_rows ??
      candidateRadarInterpretation.ordinary_result_quick_read_rows
  );
  const candidateRadarResultHandoffRows = rowsFromArray(
    candidateRadarCache.ordinary_result_handoff_rows ??
      candidateRadarInterpretation.ordinary_result_handoff_rows
  );
  const candidateRadarReadableResult = String(
    candidateRadarInterpretation.ordinary_result_summary ??
      "等待下一票雷达确认后的可读结论"
  );
  const candidateRadarReadableNextStep = String(
    candidateRadarInterpretation.ordinary_result_next_step ??
      "先回下一票雷达输入代码并点击确认按钮"
  );
  const candidateRadarReadableBoundary = String(
    candidateRadarInterpretation.ordinary_result_boundary ??
      "次日图谱只读 CandidateRadar cache / ledger / packet 的可读结论；不创建 task、不调用 Tushare/DeepSeek、不改 operation_zones 或 strategy action。"
  );
  const ordinaryResultReplayStatus = String(
    packet.ordinary_result_replay_status ??
      (chartSummary.has_drawable_data === true ? "ready_cache_replay" : "waiting_for_cache_or_manual_task")
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
        : "暂无可绘制图谱；可手动生成本地任务。",
      evidence: nextSessionLastCache,
      next_step: nextSessionChartReviewOrder,
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
      边界: "只读本地 next-session cache；不会从页面打开或普通链接创建任务。"
    },
    {
      交接段: "2. 结论",
      当前状态: nextSessionLastResultLabel,
      用户下一步: chartSummary.has_drawable_data === true ? "先读图表路径和参考线，再看操作区。" : "先查看缓存状态或手动生成按钮任务。",
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
      用户下一步: "把 operation_zones 当条件区间和复核提示，继续人工判断。",
      边界: "operation_zones 不是买卖指令，不下单，不写 strategy action。"
    }
  ];
  const nextSessionP3OneMinuteReadRows = [
    {
      读图顺序: "1. 来源",
      当前状态: nextSessionReplayOrigin,
      用户下一步: "确认来源来自下一票雷达 / 股票量化推演后的本地回放。",
      证据: "next-session cache / chart_summary",
      边界: "GET cache 只读；不创建 task、不调用 Tushare/DeepSeek/GitHub。"
    },
    {
      读图顺序: "2. 可读结论",
      当前状态: nextSessionLastResultLabel,
      用户下一步: chartSummary.has_drawable_data === true ? "先读图表路径和参考线，再读操作区。" : "先查看缓存状态或手动生成按钮任务。",
      证据: "chart_summary",
      边界: nextSessionResearchOnlyLabel
    },
    {
      读图顺序: "3. 操作区",
      当前状态: Number(chartSummary.operation_zone_count ?? 0) > 0
        ? `operation_zones ${String(chartSummary.operation_zone_count ?? 0)} 个；只表示条件区间和复核提示`
        : "等待 operation_zones cache；不能把空操作区解释成无风险",
      用户下一步: "把 operation_zones 当条件区间复核。",
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
      证据: "local route handoff #candidates/#factor",
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
          用户下一步: chartSummary.has_drawable_data === true ? nextSessionChartReviewOrder : "回下一票雷达输入代码并点击确认按钮",
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
          入口: "next-session cache / call_ledger / packet",
          边界: "写回只读本地 cache / ledger / packet；不补调 provider/model、不展示 token/key。"
        },
        {
          行动: "4. 结果",
          当前状态: nextSessionLastResultLabel,
          用户下一步: nextSessionChartReviewOrder,
          入口: "图表路径 / 参考线 / operation_zones",
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
          用户下一步: "回下一票雷达输入代码并点击确认按钮。",
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
          入口: "次日图谱路径 / 参考线 / operation_zones",
          边界: nextSessionResearchOnlyLabel
        }
      ];
  const nextSessionUpstreamConfirmOutcomeLabel = nextSessionUpstreamConfirmOutcomeRows
    .map((row) => `${row.确认结果}: ${row.当前状态}`)
    .join(" / ");
  const empty = !loading && !error && (packet.status === "cache_missing" || !Object.keys(packet).length);
  const nextSessionOrdinaryReplayBoundaryBlocked =
    packet.does_not_modify_action === false || packet.does_not_modify_operation_zones === false;
  const fallbackNextSessionOperationZoneQuickReadRows = [
    {
      速读项: "1. 先读路径",
      当前状态: chartSummary.has_drawable_data === true ? nextSessionLastResultLabel : "暂无可绘制路径；先看缓存状态或手动生成任务",
      用户下一步: "先看图表路径和参考线，再看 operation_zones 对哪些条件敏感。",
      边界: "只读 chart cache；不重算价格、不调用 Tushare/DeepSeek、不写 cache。"
    },
    {
      速读项: "2. 再读操作区",
      当前状态: Number(chartSummary.operation_zone_count ?? 0) > 0
        ? `operation_zones ${String(chartSummary.operation_zone_count ?? 0)} 个；只表示条件区间和复核提示`
        : "等待 operation_zones cache；不能把空操作区解释成无风险",
      用户下一步: "把操作区当作人工复核条件，回到证据和风险来源确认。",
      边界: nextSessionOperationZoneBoundary
    },
    {
      速读项: "3. 动作隔离",
      当前状态: nextSessionOrdinaryReplayBoundaryBlocked ? "边界异常：先停在审计检查" : "边界正常：前端只读，不改 action 或 operation_zones",
      用户下一步: nextSessionOrdinaryReplayBoundaryBlocked ? "不要继续解释图谱；先看开发审计里的边界异常" : "继续按缺口和仅供研究边界复核。",
      边界: "次日图谱不下单、不写 strategy action；DeepSeek 也不能覆盖 operation_zones。"
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
        ? `operation_zones ${String(chartSummary.operation_zone_count ?? 0)} 个`
        : "等待 operation_zones cache",
      用户下一步: "把操作区当条件区间和复核提示，回到风险/证据源确认",
      证据: nextSessionOperationZoneBoundary,
      边界: "不改 operation_zones、不下单、不把区域当交易指令。"
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
      当前状态: "次日图谱只读取 chart cache、reference_lines 和 operation_zones",
      用户下一步: "先按图谱路径、参考线和操作区复核基础结果",
      边界: "DeepSeek 不作为数据源，不覆盖图谱路径、价格、参考线或 operation_zones。"
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
        : "等待 operation_zones cache",
      证据: nextSessionOperationZoneBoundary,
      边界: "不改 operation_zones、不下单、不写 strategy action"
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
    { boundary: "does_not_modify_operation_zones", value: String(packet.does_not_modify_operation_zones !== false), note: "前端只读，不改 operation_zones。" },
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
      state: chartSummary.has_drawable_data === true ? ("done" as const) : empty ? ("waiting" as const) : ("active" as const),
      detail: nextSessionReplayOrigin
    },
    {
      label: "图表路径",
      state: chartSummary.has_drawable_data === true ? ("done" as const) : ("waiting" as const),
      detail: nextSessionLastResultLabel
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

  return (
    <>
    <PacketCard title="普通用户次日图谱摘要" subtitle="下一步、来源、缺口、边界和最近结果" status={nextSessionStatusLabel}>
      <PageStateBanner
        loading={loading}
        error={error}
        empty={empty}
        emptyTitle="暂无已缓存次日操作图谱"
        emptyDetail={cacheMissingMessage || "请在允许按钮任务的情况下点击生成任务；查看缓存不会触发 Tushare。"}
      />
      <MetricGrid
        items={[
          { label: "主下一步", value: nextSessionNextClick },
          { label: "本地缓存", value: nextSessionCacheSourceLabel },
          { label: "数据链", value: nextSessionTushareSourceLabel },
          { label: "解释状态", value: nextSessionDeepSeekSourceLabel },
          { label: "P5 解释治理", value: nextSessionP5GovernanceLabel, tone: "good" },
          { label: "待补证据", value: nextSessionPendingSourceLabel, tone: Number(productionStageScope.pending_stage_count ?? 0) > 0 ? "warn" : "good" },
          { label: "降级提示", value: nextSessionDegradedSourceLabel, tone: chartSummary.is_exact_next_session_packet === true ? "good" : "warn" },
          { label: "缺少证据", value: nextSessionMissingEvidence, tone: nextSessionMissingEvidence === "当前摘要未标记缺口" ? "good" : "warn" },
          { label: "最近结果", value: nextSessionLastResultLabel },
          { label: "查看顺序", value: nextSessionChartReviewOrder },
          { label: "回放来源", value: nextSessionReplayOrigin, tone: chartSummary.is_exact_next_session_packet === true ? "good" : "warn" },
          { label: "上游确认链", value: nextSessionUpstreamOneScreenLabel, tone: candidateRadarOneScreenRows.length ? "good" : "warn" },
          { label: "确认结果链", value: nextSessionUpstreamConfirmOutcomeLabel, tone: candidateRadarConfirmOutcomeRows.length ? "good" : "warn" },
          { label: "最近搜票结论", value: candidateRadarReadableResult, tone: candidateRadarInterpretation.interpretation_ready === true ? "good" : "warn" },
          { label: "回放路径", value: nextSessionReplayPath, tone: "good" },
          { label: "回放入口边界", value: nextSessionReplayDestinationBoundary, tone: "good" },
          { label: "操作区边界", value: nextSessionOperationZoneBoundary, tone: "good" },
          { label: "结果回放", value: ordinaryResultReplayStatus, tone: chartSummary.has_drawable_data === true ? "good" : "warn" },
          { label: "任务边界", value: nextSessionTaskBoundary, tone: "good" },
          { label: "仅供研究", value: nextSessionResearchOnlyLabel },
          { label: "P3 可读结论", value: nextSessionLastResultLabel, tone: chartSummary.has_drawable_data === true ? "good" : "warn" },
          { label: "P3 下一步", value: nextSessionChartReviewOrder },
          { label: "P3 边界", value: nextSessionResearchOnlyLabel, tone: "good" }
        ]}
      />
      <StateClarityRail
        label="next session ordinary replay status"
        state={nextSessionOrdinaryReplayRailState}
        steps={nextSessionOrdinaryReplayRailSteps}
      />
      <p className="risk-note">普通图谱状态：雷达/量化回放 / 图表路径 / 操作区 / 缺口边界；这条状态轨只读本地 next-session cache，不创建 task、不补调 Tushare 或 DeepSeek，P5 解释治理继续收起为单独补证。</p>
      <div aria-label="next session latest candidate readable result">
        <h3>最近搜票可读结论</h3>
        <p className="risk-note">优先读取 CandidateRadar 的 ordinary_result_quick_read_rows / ordinary_result_handoff_rows，旧 cache 再回退 search_quant_projection_interpretation_summary；确认后的 Tushare-first、P2 三面和 P3 结论在图谱页首屏直接回放；本卡不创建 task、不补调数据源或模型，也不改 operation_zones。</p>
        <MetricGrid
          items={[
            { label: "标的", value: String(candidateRadarReceipt.symbol ?? "--"), tone: candidateRadarReceipt.symbol ? "good" : "warn" },
            { label: "可读结论", value: candidateRadarReadableResult, tone: candidateRadarInterpretation.interpretation_ready === true ? "good" : "warn" },
            { label: "下一步", value: candidateRadarReadableNextStep },
            { label: "P2 小数据", value: String(candidateRadarSmallDataWriteback.small_data_writeback_ready === true ? "已回放" : "等待回放"), tone: candidateRadarSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn" },
            { label: "DeepSeek", value: String(candidateRadarInterpretation.deepseek_governed_executor_status ?? "governed_executor_pending"), tone: "good" },
            { label: "边界", value: candidateRadarReadableBoundary, tone: "good" }
          ]}
        />
        {candidateRadarResultQuickRows.length ? <DataLineageTable rows={candidateRadarResultQuickRows} /> : null}
        {candidateRadarResultHandoffRows.length ? <DataLineageTable rows={candidateRadarResultHandoffRows} /> : null}
      </div>
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
      <div aria-label="next session p3 one minute read">
        <h3>P3 一分钟读图</h3>
        <p className="risk-note">普通用户先看这张表：用一分钟确认来源、可读结论、operation_zones、缺口和回流入口；它只读本地 next-session cache。</p>
        <DataLineageTable rows={nextSessionP3OneMinuteReadRows} />
      </div>
      <div aria-label="next session p3 result handoff quick read">
        <h3>P3 结果交接速读</h3>
        <p className="risk-note">先看来源、结论、缺口和操作区边界；这张表只做本地结果交接，不展开 QA、promotion 或 raw packet 审计。</p>
        <DataLineageTable rows={nextSessionResultHandoffRows} />
      </div>
      <div aria-label="next session ordinary operation zone quick read">
        <h3>操作区解释速读</h3>
        <p className="risk-note">普通用户先按路径、参考线、操作区的顺序读；operation_zones 只是条件区间和复核提示，不是买卖、下单或 strategy action。优先读取本地缓存里的条件速读；旧缓存缺字段时才使用前端 fallback。</p>
        <DataLineageTable rows={nextSessionOperationZoneQuickReadRows} />
      </div>
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
        <p className="risk-note">普通主线先复核 P3 图谱来源、路径、参考线和 operation_zones；DeepSeek governed executor 状态默认收起，只作为高级补证参考。</p>
        <div aria-label="next session ordinary deepseek governance">
          <h3>解释治理单独补证状态</h3>
          <p className="risk-note">DeepSeek 解释单独补证；基础图谱先按本地 cache 回放，普通页不展示 prompt/output，也不让模型改写图谱或动作。</p>
          <DataLineageTable rows={ordinaryDeepSeekGovernanceRows} />
        </div>
      </details>
      <div className="actions" aria-label="next session replay handoff actions">
        <a href="#candidates" title="切换到下一票雷达模块；换标的仍需确认按钮" aria-label="return to candidate radar confirmed symbol entry">回到下一票雷达</a>
        <a href="#factor" title="切换到股票量化推演模块；只读 Factor cache 回放" aria-label="open stock quant projection replay">查看股票量化推演</a>
      </div>
      <div className="actions">
        <button onClick={refreshCache} title={nextSessionCacheButtonLabel} aria-label={nextSessionCacheButtonLabel}>查看缓存</button>
        <button onClick={launchTask} title={nextSessionGenerateButtonLabel} aria-label={nextSessionGenerateButtonLabel}>生成任务</button>
      </div>
      <p className="risk-note">{nextSessionReplayPath}；这些回放入口只做本地模块路由切换，不创建任务、不刷新 Tushare/DeepSeek。</p>
      <p className="risk-note">摘要里的查看缓存只读取本地 GET cache；生成任务只创建按钮门控 POST task，不调用 Tushare 或 DeepSeek，不写交易动作。</p>
      <p className="risk-note">普通用户先按“图表路径 -&gt; 参考线 -&gt; 操作区 -&gt; 缺少证据”复核；operation_zones 只是条件区间，不是买卖或下单指令。</p>
      <details className="ordinary-audit-shortcuts" aria-label="next session ordinary audit shortcuts">
        <summary>高级诊断入口</summary>
        <p className="risk-note">工程审计明细继续默认收起；QA、promotion、cache ledger 和原始 packet 下沉到 <a href="#next-session-audit">开发审计</a>。</p>
      </details>
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
      <div className="next-session-chart-review" role="region" aria-label={nextSessionChartReviewRegionLabel} title={nextSessionChartReviewRegionLabel}>
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
