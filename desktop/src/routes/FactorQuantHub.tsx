import { useEffect, useState } from "react";
import type { EChartsOption } from "echarts";
import { getBootstrapStatus, getCandidateRadarCache, getFactorQuantCache, postTask, type TaskCreationEnvelope } from "../api/client";
import { getTasks, type TaskStatusIndex } from "../api/client";
import ChartSafetyStrip from "../components/ChartSafetyStrip";
import DataLineageTable from "../components/DataLineageTable";
import EChartPanel from "../components/EChartPanel";
import JsonDetails from "../components/JsonDetails";
import MetricGrid, { type MetricItem } from "../components/MetricGrid";
import PageStateBanner from "../components/PageStateBanner";
import PacketCard from "../components/PacketCard";
import StateClarityRail from "../components/StateClarityRail";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

// Legacy marker: plain href="#candidates" module-top links are superseded by the confirm-input deep link.
const CANDIDATE_CONFIRM_HREF = "#candidates/candidate-radar-search-quant-projection";
const NEXT_SESSION_CHART_HREF = "#next/next-session-chart";
const DATA_CAPABILITY_HREF = "#dataCapability";

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

const runtimeModeLabels: Record<string, string> = {
  cache_only: "cache_only（只读缓存，不外联）",
  manual: "manual（仅手动按钮任务）",
  live_light: "live_light（轻量后台 task 口径，仍不在渲染中外联）",
  live_full: "live_full（预留，默认关闭）"
};

function runtimeModeLabel(value: unknown): string {
  const mode = typeof value === "string" && value ? value : "cache_only";
  return runtimeModeLabels[mode] ?? `未知运行模式：${mode}`;
}

export default function FactorQuantHub() {
  const [packet, setPacket] = useState<Record<string, any>>({});
  const [candidateRadarCache, setCandidateRadarCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<unknown>>([]);
  const [bootstrapStatus, setBootstrapStatus] = useState<Record<string, unknown>>({});
  const [taskIndex, setTaskIndex] = useState<TaskStatusIndex | null>(null);
  const [taskId, setTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [autoAfterTask, setAutoAfterTask] = useState(false);
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
  const refreshBootstrapStatus = () =>
    void getBootstrapStatus().then((res) => {
      setBootstrapStatus(res.data);
    });
  const refreshCandidateRadarCache = () =>
    void getCandidateRadarCache().then((res) => {
      if (res.ok !== false) setCandidateRadarCache(res.data ?? {});
    });
  const refreshTaskIndex = () =>
    void getTasks().then((res) => setTaskIndex(res.data));
  const launchTask = (path: string, payload: Record<string, unknown> = {}) =>
    void postTask(path, payload).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
      if (res.ok) refreshTaskIndex();
    });

  useEffect(() => {
    refreshCache();
    refreshBootstrapStatus();
    refreshCandidateRadarCache();
    refreshTaskIndex();
  }, []);

  const score = packet.score ?? {};
  const factorPacketCandidateHandoff = (packet.candidate_radar_quant_projection_handoff as Record<string, unknown> | undefined) ?? {};
  const factorPacketCandidateHandoffRows = toRows(packet.ordinary_quant_candidate_handoff_rows);
  const factorPacketP3OneScreenSummary = (packet.ordinary_quant_p3_one_screen_summary as Record<string, unknown> | undefined) ?? {};
  const factorPacketP3OneScreenRows = toRows(packet.ordinary_quant_p3_one_screen_items);
  const candidateRadarP1ShortestPathCheckpoint = (candidateRadarCache.ordinary_p1_shortest_path_checkpoint as Record<string, unknown> | undefined) ?? {};
  const candidateRadarSmallDataWriteback = (candidateRadarCache.search_quant_projection_small_data_writeback_summary as Record<string, unknown> | undefined) ?? {};
  const candidateRadarOneScreenRows = toRows(candidateRadarSmallDataWriteback.ordinary_one_screen_action_rows);
  const candidateRadarConfirmOutcomeRows = toRows(candidateRadarSmallDataWriteback.ordinary_confirm_outcome_rows);
  const candidateRadarWritebackSurfaceRows = toRows(candidateRadarSmallDataWriteback.ordinary_writeback_surface_summary_rows);
  const candidateRadarProviderApiRows = toRows(candidateRadarSmallDataWriteback.ordinary_provider_api_rows);
  const candidateRadarInterpretation = (candidateRadarCache.search_quant_projection_interpretation_summary as Record<string, unknown> | undefined) ?? {};
  const candidateRadarPostConfirmOneGlanceRows = toRows(
    candidateRadarCache.search_quant_projection_post_confirm_one_glance_items ??
      candidateRadarInterpretation.ordinary_post_confirm_one_glance_items
  );
  const candidateRadarReceipt = (candidateRadarCache.search_quant_projection_receipt as Record<string, unknown> | undefined) ?? {};
  const candidateRadarReceiptCallLedger = toRows(candidateRadarReceipt.call_ledger);
  const candidateRadarReceiptRequestParams =
    (candidateRadarReceiptCallLedger[0]?.request_params_safe as Record<string, unknown> | undefined) ?? {};
  const ordinaryQuantPostConfirmReplayContract =
    (candidateRadarReceiptRequestParams.ordinary_post_confirm_replay_contract as Record<string, unknown> | undefined) ?? {};
  const candidateRadarConfirmedSymbol = String(
    packet.latest_confirmed_symbol ??
      candidateRadarCache.latest_confirmed_symbol ??
      factorPacketCandidateHandoff.symbol ??
      candidateRadarReceipt.symbol ??
      candidateRadarSmallDataWriteback.symbol ??
      candidateRadarInterpretation.symbol ??
      ""
  );
  const candidateRadarLatestTaskId = String(
    packet.latest_confirmed_task_id ??
      candidateRadarCache.latest_confirmed_task_id ??
      factorPacketCandidateHandoff.source_task_id ??
      candidateRadarCache.search_quant_projection_latest_task_id ??
      candidateRadarCache.latest_task_id ??
      candidateRadarReceipt.latest_task_id ??
      candidateRadarReceipt.task_id ??
      candidateRadarSmallDataWriteback.latest_task_id ??
      ""
  );
  const candidateRadarConfirmedTaskReceiptRows = toRows(
    candidateRadarCache.search_quant_projection_confirmed_task_receipt_rows ??
      candidateRadarSmallDataWriteback.ordinary_confirmed_task_receipt_rows
  );
  const candidateRadarTaskReadbackRows = toRows(
    candidateRadarCache.search_quant_projection_task_readback_rows ??
      candidateRadarSmallDataWriteback.ordinary_task_readback_rows
  );
  const candidateRadarLatestTaskStep = String(
    packet.latest_confirmed_task_current_step ??
      candidateRadarCache.latest_confirmed_task_current_step ??
      factorPacketCandidateHandoff.source_task_current_step ??
      candidateRadarReceipt.latest_task_current_step ??
      candidateRadarSmallDataWriteback.latest_task_current_step ??
      factorPacketCandidateHandoff.status ??
      candidateRadarReceipt.status ??
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
  const ordinaryQuantProgressWatchTaskId = taskIndexLatestConfirmedTaskId || candidateRadarLatestTaskId;
  const ordinaryQuantProgressWatchSymbol = taskIndexLatestConfirmedSymbol || candidateRadarConfirmedSymbol;
  const ordinaryQuantProgressWatchStatus =
    taskIndexLatestConfirmedStatus ||
    (candidateRadarLatestTaskId ? "cache_replay" : "waiting_confirm");
  const ordinaryQuantProgressWatchStep =
    taskIndexLatestConfirmedStep ||
    candidateRadarLatestTaskStep ||
    "等待确认按钮后的本地任务状态";
  const ordinaryQuantProgressWatchLabel = ordinaryQuantProgressWatchTaskId
    ? `${ordinaryQuantProgressWatchSymbol || "当前标的"} / ${ordinaryQuantProgressWatchStatus}`
    : "等待确认按钮后的任务进度";
  const ordinaryQuantProgressWatchNext = ordinaryQuantProgressWatchTaskId
    ? "查看任务目录；成功后继续读支持/压制和次日图谱"
    : "先回下一票雷达输入股票代码并点击确认按钮；输入本身保持静默";
  const ordinaryQuantTaskIndexProgressItems: MetricItem[] = [
    {
      label: "边用边看",
      value: ordinaryQuantProgressWatchLabel,
      tone: ordinaryQuantProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "最新确认标的",
      value: ordinaryQuantProgressWatchSymbol || "等待确认股票代码",
      tone: ordinaryQuantProgressWatchSymbol ? "good" : "neutral"
    },
    {
      label: "最新任务",
      value: ordinaryQuantProgressWatchTaskId || "等待确认按钮",
      tone: ordinaryQuantProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "当前步骤",
      value: ordinaryQuantProgressWatchStep,
      tone: ordinaryQuantProgressWatchTaskId ? "good" : "warn"
    },
    {
      label: "只读来源",
      value: "GET /api/tasks + Factor cache + CandidateRadar cache",
      tone: "good"
    },
    {
      label: "安全边界",
      value: taskIndexReadbackSafe ? "任务索引回读未触发外联、未创建 task" : "等待任务索引只读边界回放",
      tone: taskIndexReadbackSafe ? "good" : "warn"
    }
  ];
  const candidateRadarConfirmChainStatus = String(
    candidateRadarCache.search_quant_projection_confirm_chain_status ??
      candidateRadarReceipt.p1_confirm_chain_status ??
      factorPacketCandidateHandoff.status ??
      candidateRadarLatestTaskStep
  );
  const candidateRadarSmallDataStateLabel = String(
    candidateRadarSmallDataWriteback.ordinary_readback_stage_label ??
      candidateRadarSmallDataWriteback.summary_label ??
      factorPacketCandidateHandoff.status ??
      "等待确认按钮后的 cache / ledger / packet 回放"
  );
  const candidateRadarResultQuickRows = toRows(
    candidateRadarCache.ordinary_result_quick_read_rows ??
      candidateRadarInterpretation.ordinary_result_quick_read_rows ??
      packet.ordinary_quant_candidate_handoff_rows
  );
  const candidateRadarResultCheckpointRows = toRows(
    candidateRadarCache.ordinary_result_checkpoint_rows ??
      candidateRadarCache.search_quant_projection_result_checkpoint_rows ??
      candidateRadarInterpretation.ordinary_result_checkpoint_rows ??
      packet.ordinary_quant_candidate_handoff_rows
  );
  const candidateRadarReadableResult = String(
    factorPacketP3OneScreenSummary.result_summary ??
      candidateRadarCache.ordinary_result_summary ??
      candidateRadarInterpretation.ordinary_result_summary ??
      factorPacketCandidateHandoff.ordinary_result_summary ??
      "等待下一票雷达确认后的可读结论"
  );
  const candidateRadarReadableNextStep = String(
    factorPacketP3OneScreenSummary.result_next_step ??
      candidateRadarCache.ordinary_result_next_step ??
      candidateRadarInterpretation.ordinary_result_next_step ??
      factorPacketCandidateHandoff.ordinary_result_next_step ??
      "先回下一票雷达确认输入区输入代码并点击确认按钮"
  );
  const candidateRadarReadableBoundary = String(
    factorPacketP3OneScreenSummary.result_boundary ??
      candidateRadarCache.ordinary_result_boundary ??
      candidateRadarInterpretation.ordinary_result_boundary ??
      factorPacketCandidateHandoff.ordinary_result_boundary ??
      "量化页只读 CandidateRadar cache / ledger / packet 的可读结论；不创建 task、不调用 Tushare/DeepSeek、不改交易动作。"
  );
  const candidateRadarDeepSeekStateRaw = String(
    factorPacketP3OneScreenSummary.deepseek_governed_executor_status ??
      candidateRadarCache.ordinary_result_deepseek_governed_executor_status ??
      candidateRadarInterpretation.deepseek_governed_executor_status ??
      factorPacketCandidateHandoff.deepseek_governed_executor_status ??
      "governed_executor_pending"
  );
  const candidateRadarUsesModelOutput =
    candidateRadarInterpretation.uses_deepseek_output === true ||
    candidateRadarInterpretation.uses_model_output === true;
  const candidateRadarOrdinaryDeepSeekState = candidateRadarUsesModelOutput
    ? "检测到模型输出；需回 P5 governed executor 审核后再展示"
    : candidateRadarDeepSeekStateRaw.includes("skipped")
      ? "DeepSeek 不用等：Tushare-first、支持/压制和次日图谱可先看"
      : candidateRadarDeepSeekStateRaw.includes("pending")
        ? "DeepSeek 待治理：不阻塞 Tushare-first、支持/压制和次日图谱"
        : "DeepSeek governed executor 单独补；普通结果只读本地 cache / ledger / packet";
  const ordinaryQuantCandidateRadarP3Ready =
    factorPacketP3OneScreenSummary.p3_readable_result_ready === true ||
    candidateRadarResultQuickRows.length > 0 ||
    factorPacketCandidateHandoff.p3_readable_result_ready === true ||
    (
      candidateRadarInterpretation.interpretation_ready === true &&
      Boolean(String(candidateRadarInterpretation.ordinary_result_summary ?? "").trim())
    );
  const runtime = packet.runtime ?? {};
  const governance = packet.governance ?? {};
  const bridge = packet.next_session_bridge ?? {};
  const freshnessGate = packet.data_freshness_gate ?? {};
  const universeResearch = packet.universe_research_contract ?? {};
  const universeExecutionReadiness = packet.universe_execution_readiness_audit ?? {};
  const universeExecutionReadinessReceipt = packet.universe_execution_readiness_receipt ?? {};
  const universeExecutionActivationReceipt = packet.universe_execution_activation_receipt ?? {};
  const universeWorkerBatchDryRun = packet.universe_worker_batch_dry_run_receipt ?? {};
  const universeWorkerBatchExecutionRecipe = packet.universe_worker_batch_execution_recipe ?? {};
  const universeWorkerBatchExecutionRequest = packet.universe_worker_batch_execution_request_receipt ?? {};
  const universeWorkerBatchResearchReceipt = packet.universe_worker_batch_research_receipt ?? {};
  const universeDurableEvidenceRecipe = packet.universe_durable_evidence_recipe ?? {};
  const universeResearchTaskPlan = packet.universe_research_task_plan ?? {};
  const universeLocalRankZscore = packet.universe_local_rank_zscore_dry_run ?? {};
  const factorLibrary = packet.factor_library ?? {};
  const factorTests = packet.factor_tests ?? {};
  const factorTestQuality = factorTests.quality_summary ?? {};
  const factorTestAcceptance = factorTests.acceptance_contract ?? {};
  const factorTestStorageQuery = factorTests.storage_query_consumption ?? {};
  const factorTestLocalDataset = factorTests.local_dataset_sample_evidence ?? {};
  const factorTestSmallPool = factorTests.small_pool_acceptance ?? {};
  const factorTestProductionValidation = factorTests.production_validation_qa_contract ?? {};
  const factorTestProviderValidationBlocker = factorTests.provider_validation_blocker_audit ?? {};
  const factorTestProviderSampleReadinessReceipt = factorTests.provider_sample_readiness_receipt ?? {};
  const factorTestProviderSampleActivationReceipt = factorTests.provider_sample_activation_receipt ?? {};
  const factorTestProviderSmallPoolDryRun = factorTests.provider_small_pool_acceptance_dry_run_receipt ?? {};
  const factorTestProviderSmallPoolExecutionRecipe = factorTests.provider_small_pool_execution_recipe ?? {};
  const factorTestProviderSmallPoolExecutionRequest = factorTests.provider_small_pool_execution_request_receipt ?? {};
  const factorTestProviderSmallPoolAcceptance = factorTests.provider_small_pool_acceptance_receipt ?? {};
  const factorTestDurableEvidenceRecipe = factorTests.durable_evidence_recipe ?? {};
  const factorTestProductionStageScopeManifest = factorTests.production_stage_scope_manifest ?? {};
  const tushareFailureModeQa = packet.failure_mode_qa_contract ?? {};
  const tushareRequestParameterQa = packet.request_parameter_qa_contract ?? {};
  const tushareProviderTargetSamplePlan = packet.provider_target_sample_plan_contract ?? {};
  const tushareProviderPromotionAudit = packet.provider_acceptance_promotion_audit ?? {};
  const tushareProviderEvidenceGapAudit = packet.provider_evidence_gap_audit ?? {};
  const tushareProviderSampleReadinessReceipt = packet.provider_sample_readiness_receipt ?? {};
  const tushareDurableEvidenceRecipe = packet.tushare_durable_evidence_recipe ?? {};
  const dataLedger = packet.data_ledger ?? {};
  const researchContext = packet.research_context ?? {};
  const linkedPackets = packet.linked_packets ?? {};
  const deepseek = packet.deepseek_explanation ?? {};
  const deepseekGovernance = packet.deepseek_explain_governance ?? {};
  const deepseekValidation = packet.deepseek_validation_summary ?? {};
  const deepseekJsonStability = packet.deepseek_json_stability_audit ?? {};
  const deepseekResponseFormatReview = packet.deepseek_response_format_review_contract ?? {};
  const deepseekRetryRepairDryRun = packet.deepseek_retry_repair_dry_run_contract ?? {};
  const deepseekProductionActivationReceipt = packet.deepseek_production_activation_receipt ?? {};
  const deepseekProviderBenchmarkScopeTicket = packet.deepseek_provider_benchmark_scope_ticket_receipt ?? {};
  const deepseekProviderBenchmarkExecutionRequest = packet.deepseek_provider_benchmark_execution_request_receipt ?? {};
  const deepseekDurableEvidenceRecipe = packet.deepseek_durable_evidence_recipe ?? {};
  const scoreChart = packet.score_chart_payload ?? {};
  const scoreChartContract = scoreChart.chart_contract ?? {};
  const scoreChartRows = toRows(scoreChart.bucket_rows);
  const scoreChartContractRows = objectRows(scoreChartContract as Record<string, unknown>, "chart_contract");
  const deepseekValidationRows = objectRows(deepseekValidation as Record<string, unknown>, "deepseek_validation");
  const deepseekJsonStabilityRows = toRows(packet.deepseek_json_stability_rows);
  const deepseekResponseFormatReviewRows = toRows(packet.deepseek_response_format_review_rows);
  const deepseekRetryRepairDryRunRows = toRows(packet.deepseek_retry_repair_dry_run_rows);
  const deepseekProductionActivationRows = toRows(packet.deepseek_production_activation_rows);
  const deepseekProductionActivationReceiptRows = objectRows(deepseekProductionActivationReceipt as Record<string, unknown>, "deepseek_activation_receipt");
  const deepseekProviderBenchmarkScopeRows = toRows(packet.deepseek_provider_benchmark_scope_ticket_rows);
  const deepseekProviderBenchmarkScopeReceiptRows = objectRows(deepseekProviderBenchmarkScopeTicket as Record<string, unknown>, "deepseek_benchmark_scope_ticket");
  const deepseekProviderBenchmarkExecutionRequestRows = toRows(packet.deepseek_provider_benchmark_execution_request_rows);
  const deepseekProviderBenchmarkExecutionRequestReceiptRows = objectRows(deepseekProviderBenchmarkExecutionRequest as Record<string, unknown>, "deepseek_benchmark_execution_request");
  const deepseekDurableEvidenceRows = toRows(packet.deepseek_durable_evidence_rows);
  const universeResearchRows = objectRows(universeResearch as Record<string, unknown>, "universe_contract");
  const universeModeRows = toRows(packet.universe_research_mode_rows);
  const universeExecutionReadinessRows = objectRows(universeExecutionReadiness as Record<string, unknown>, "universe_execution_readiness");
  const universeExecutionCriterionRows = toRows(packet.universe_execution_readiness_rows);
  const universeExecutionReceiptRows = objectRows(universeExecutionReadinessReceipt as Record<string, unknown>, "universe_execution_receipt");
  const universeExecutionReceiptCriterionRows = toRows(packet.universe_execution_readiness_receipt_rows);
  const universeExecutionActivationRows = objectRows(universeExecutionActivationReceipt as Record<string, unknown>, "universe_execution_activation");
  const universeExecutionActivationCriterionRows = toRows(packet.universe_execution_activation_rows);
  const universeWorkerBatchDryRunRows = objectRows(universeWorkerBatchDryRun as Record<string, unknown>, "universe_worker_batch_dry_run");
  const universeWorkerBatchDryRunCriterionRows = toRows(packet.universe_worker_batch_dry_run_rows);
  const universeWorkerBatchExecutionRecipeRows = objectRows(universeWorkerBatchExecutionRecipe as Record<string, unknown>, "universe_worker_batch_execution_recipe");
  const universeWorkerBatchExecutionPhaseRows = toRows(packet.universe_worker_batch_execution_rows);
  const universeWorkerBatchExecutionRequestRows = objectRows(universeWorkerBatchExecutionRequest as Record<string, unknown>, "universe_worker_batch_execution_request");
  const universeWorkerBatchExecutionRequestCriterionRows = toRows(packet.universe_worker_batch_execution_request_rows);
  const universeWorkerBatchResearchRows = objectRows(universeWorkerBatchResearchReceipt as Record<string, unknown>, "universe_worker_batch_research_receipt");
  const universeWorkerBatchResearchCriterionRows = toRows(packet.universe_worker_batch_research_rows);
  const universeDurableEvidenceRecipeRows = objectRows(universeDurableEvidenceRecipe as Record<string, unknown>, "universe_durable_evidence_recipe");
  const universeDurableEvidenceRows = toRows(packet.universe_durable_evidence_rows);
  const universeResearchTaskPlanRows = objectRows(universeResearchTaskPlan as Record<string, unknown>, "universe_read_plan");
  const universeResearchDatasetRows = toRows(packet.universe_research_task_plan_rows);
  const universeLocalRankZscoreRows = objectRows(universeLocalRankZscore as Record<string, unknown>, "local_rank_zscore");
  const universeLocalRankZscoreCriterionRows = toRows(packet.universe_local_rank_zscore_rows);
  const universeLocalRankZscorePreviewRows = toRows(packet.universe_local_rank_zscore_preview_rows);
  const factorTestRows = toRows(factorTests.items);
  const factorTestMetricRows = toRows(factorTests.metric_schema);
  const factorTestModeRows = toRows(factorTests.mode_plan);
  const factorTestStateRows = toRows(factorTests.state_transition_rows);
  const factorTestAcceptanceRows = objectRows(factorTestAcceptance as Record<string, unknown>, "factor_test_contract");
  const factorTestStatusRows = objectRows((factorTests.status_counts ?? {}) as Record<string, unknown>, "factor_test_status");
  const factorTestQualityRows = objectRows(factorTestQuality as Record<string, unknown>, "quality_metric");
  const factorTestMetricGapRows = objectRows((factorTests.required_metric_gap_counts ?? factorTestQuality.required_metric_gap_counts ?? {}) as Record<string, unknown>, "metric_gap");
  const factorTestWindowRows = objectRows((factorTests.window_summary ?? factorTestQuality.window_summary ?? {}) as Record<string, unknown>, "window_metric");
  const factorTestStorageQueryRows = objectRows(factorTestStorageQuery as Record<string, unknown>, "storage_query_contract");
  const factorTestStorageQueryTableRows = toRows(factorTests.storage_query_consumption_rows);
  const factorTestLocalDatasetRows = objectRows(factorTestLocalDataset as Record<string, unknown>, "local_dataset_sample");
  const factorTestLocalDatasetCriterionRows = toRows(factorTests.local_dataset_sample_evidence_rows);
  const factorTestSmallPoolRows = objectRows(factorTestSmallPool as Record<string, unknown>, "small_pool_acceptance");
  const factorTestSmallPoolCriterionRows = toRows(factorTests.small_pool_acceptance_rows);
  const factorTestProductionValidationRows = objectRows(factorTestProductionValidation as Record<string, unknown>, "production_validation");
  const factorTestProductionValidationCriterionRows = toRows(factorTests.production_validation_qa_rows);
  const factorTestProviderValidationBlockerRows = objectRows(factorTestProviderValidationBlocker as Record<string, unknown>, "provider_validation_blocker");
  const factorTestProviderValidationBlockerCriterionRows = toRows(factorTests.provider_validation_blocker_rows);
  const factorTestProviderSampleReadinessRows = objectRows(factorTestProviderSampleReadinessReceipt as Record<string, unknown>, "provider_sample_readiness");
  const factorTestProviderSampleReadinessCriterionRows = toRows(factorTests.provider_sample_readiness_rows);
  const factorTestProviderSampleActivationRows = objectRows(factorTestProviderSampleActivationReceipt as Record<string, unknown>, "provider_sample_activation");
  const factorTestProviderSampleActivationCriterionRows = toRows(factorTests.provider_sample_activation_rows);
  const factorTestProviderSmallPoolDryRunRows = objectRows(factorTestProviderSmallPoolDryRun as Record<string, unknown>, "provider_small_pool_dry_run");
  const factorTestProviderSmallPoolDryRunCriterionRows = toRows(factorTests.provider_small_pool_acceptance_dry_run_rows);
  const factorTestProviderSmallPoolExecutionRecipeRows = objectRows(factorTestProviderSmallPoolExecutionRecipe as Record<string, unknown>, "provider_small_pool_execution_recipe");
  const factorTestProviderSmallPoolExecutionPhaseRows = toRows(factorTests.provider_small_pool_execution_rows);
  const factorTestProviderSmallPoolExecutionRequestRows = objectRows(factorTestProviderSmallPoolExecutionRequest as Record<string, unknown>, "provider_small_pool_execution_request");
  const factorTestProviderSmallPoolExecutionRequestCriterionRows = toRows(factorTests.provider_small_pool_execution_request_rows);
  const factorTestProviderSmallPoolAcceptanceRows = objectRows(factorTestProviderSmallPoolAcceptance as Record<string, unknown>, "provider_small_pool_acceptance_gate");
  const factorTestProviderSmallPoolAcceptanceCriterionRows = toRows(factorTests.provider_small_pool_acceptance_rows);
  const factorTestDurableEvidenceRecipeRows = objectRows(factorTestDurableEvidenceRecipe as Record<string, unknown>, "factor_test_durable_evidence_recipe");
  const factorTestDurableEvidenceRows = toRows(factorTests.durable_evidence_rows);
  const factorTestProductionStageScopeManifestRows = objectRows(factorTestProductionStageScopeManifest as Record<string, unknown>, "factor_test_production_stage_scope_manifest");
  const factorTestProductionStageScopeRows = toRows(factorTests.production_stage_scope_rows);
  const tushareFailureModeQaRows = objectRows(tushareFailureModeQa as Record<string, unknown>, "failure_mode_contract");
  const tushareFailureModeCriterionRows = toRows(packet.failure_mode_qa_rows);
  const tushareRequestParameterQaRows = objectRows(tushareRequestParameterQa as Record<string, unknown>, "request_parameter_contract");
  const tushareRequestParameterCriterionRows = toRows(packet.request_parameter_qa_rows);
  const tushareProviderTargetSamplePlanRows = objectRows(tushareProviderTargetSamplePlan as Record<string, unknown>, "target_sample_plan");
  const tushareProviderTargetSamplePlanCriterionRows = toRows(packet.provider_target_sample_plan_rows);
  const tushareProviderPromotionAuditRows = objectRows(tushareProviderPromotionAudit as Record<string, unknown>, "provider_promotion_audit");
  const tushareProviderPromotionCriterionRows = toRows(packet.provider_acceptance_promotion_rows);
  const tushareProviderEvidenceGapAuditRows = objectRows(tushareProviderEvidenceGapAudit as Record<string, unknown>, "provider_evidence_gap_audit");
  const tushareProviderEvidenceGapRows = toRows(packet.provider_evidence_gap_rows);
  const tushareProviderSampleReadinessRows = objectRows(tushareProviderSampleReadinessReceipt as Record<string, unknown>, "provider_sample_readiness");
  const tushareProviderSampleReadinessCriterionRows = toRows(packet.provider_sample_readiness_rows);
  const tushareDurableEvidenceRows = toRows(packet.tushare_durable_evidence_rows);
  const tushareDurableEvidenceRecipeRows = objectRows(tushareDurableEvidenceRecipe as Record<string, unknown>, "tushare_durable_evidence_recipe");
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
  const ordinaryQuantNextClick = empty
    ? ordinaryQuantCandidateRadarP3Ready
      ? "先读最近搜票可读结论；支持/压制缓存待刷新，必要时再手动运行轻量推演"
      : "先从下一票雷达确认输入区输入股票代码并生成 3.0 量化推演；本页查看本地缓存，不自动刷新外部数据或模型解释"
    : "先看支持/压制与次日图谱预览；换标的从下一票雷达确认输入区点生成 3.0 量化推演；需要更新时再手动刷新数据、运行轻量推演或整理模型解释";
  const ordinaryQuantPrimaryActionLabel = empty
    ? ordinaryQuantCandidateRadarP3Ready
      ? "查看最近搜票结论"
      : "去下一票雷达生成推演"
    : "查看支持/压制";
  const ordinaryQuantPrimaryActionHref = empty
    ? ordinaryQuantCandidateRadarP3Ready
      ? "#stock-quant-readable-result"
      : CANDIDATE_CONFIRM_HREF
    : "#factor-score";
  const ordinaryQuantPrimaryActionBoundary = empty
    ? "主下一步直达下一票雷达确认输入区；输入代码和生成推演仍需按钮确认"
    : "主下一步只跳转本地支持/压制摘要；不刷新 provider/model、不写 cache";
  const ordinaryQuantSymbolEntryBoundary =
    "本页不提供股票代码输入；换标的必须回下一票雷达确认输入区点击确认生成，输入本身不创建 task";
  const ordinaryQuantCacheSourceLabel = empty ? "等待本地量化缓存" : "本地量化缓存可用";
  const ordinaryQuantGlobalTushareSourceLabel =
    Number(tushareProviderPromotionAudit.provider_evidence_row_count ?? 0) > 0 ? "Tushare 数据有本地记录" : "等待手动补充 Tushare 数据";
  const ordinaryQuantTushareFirstProviderSuccessCount = Number(
    factorPacketCandidateHandoff.provider_api_success_count ??
      candidateRadarSmallDataWriteback.provider_api_success_count ??
      candidateRadarInterpretation.provider_api_success_count ??
      candidateRadarP1ShortestPathCheckpoint.provider_api_success_count ??
      0
  );
  const ordinaryQuantTushareFirstProviderCallCount = Number(
    factorPacketCandidateHandoff.provider_api_call_count ??
      candidateRadarSmallDataWriteback.provider_api_call_count ??
      candidateRadarInterpretation.provider_api_call_count ??
      candidateRadarP1ShortestPathCheckpoint.provider_api_call_count ??
      ordinaryQuantTushareFirstProviderSuccessCount
  );
  const ordinaryQuantTushareFirstProviderLedgerRatio = ordinaryQuantTushareFirstProviderCallCount > 0
    ? `${ordinaryQuantTushareFirstProviderSuccessCount}/${ordinaryQuantTushareFirstProviderCallCount}`
    : `${ordinaryQuantTushareFirstProviderSuccessCount}`;
  const ordinaryQuantTushareFirstDataChainLabel = (() => {
    const upstreamStage = String(
      candidateRadarSmallDataWriteback.ordinary_readback_stage_label ??
        candidateRadarSmallDataWriteback.summary_label ??
        ""
    );
    if (ordinaryQuantTushareFirstProviderSuccessCount > 0) {
      const symbolLabel = candidateRadarConfirmedSymbol ? `${candidateRadarConfirmedSymbol} ` : "";
      return `${symbolLabel}Tushare-first：数据已回放 ${ordinaryQuantTushareFirstProviderLedgerRatio} 个接口`;
    }
    if (candidateRadarConfirmedSymbol && upstreamStage) return `${candidateRadarConfirmedSymbol} Tushare-first：${upstreamStage}`;
    if (upstreamStage) return `Tushare-first：${upstreamStage}`;
    return ordinaryQuantGlobalTushareSourceLabel;
  })();
  const ordinaryQuantDeepSeekSourceLabel =
    deepseek.called === true ? "DeepSeek 解释已有本地结果；只解释不改数值或动作" : "DeepSeek 待 governed executor；普通页只读状态";
  const ordinaryQuantModelSourceLabel =
    deepseekValidation.model_call_status && deepseekValidation.model_call_status !== "not_called" ? "模型状态已有本地记录" : "模型未调用或等待 governed executor";
  const ordinaryQuantRuntimeMode = String(bootstrapStatus.mode ?? packet.mode ?? "cache_only");
  const ordinaryQuantHasPendingEvidence =
    empty ||
    Number(runtime.missing_count ?? 0) > 0 ||
    factorTestProductionValidation.provider_backed_small_pool_validation_done !== true ||
    deepseekProductionActivationReceipt.provider_benchmark_done !== true ||
    tushareProviderPromotionAudit.promotion_ready !== true;
  const ordinaryQuantPendingStateLabel = empty
    ? "等待从下一票雷达生成本地量化推演"
    : ordinaryQuantHasPendingEvidence
      ? "存在待补证据或待确认任务"
      : "当前摘要未标记 pending 项";
  const ordinaryQuantEvidenceTaskState = (() => {
    if (empty) return "等待本地缓存后再确认补证方式";
    if (!ordinaryQuantHasPendingEvidence) return "暂无待补任务，继续只读查看";
    if (ordinaryQuantRuntimeMode === "cache_only") return "cache_only 只读查看，不创建补证任务";
    if (ordinaryQuantRuntimeMode === "manual") return "manual 只允许用户按钮创建 POST task";
    if (ordinaryQuantRuntimeMode === "live_light") return "live_light 可由后台 task 补证；本页仍只读轮询缓存";
    if (ordinaryQuantRuntimeMode === "live_full") return "live_full 深度补证预留，默认关闭";
    return "未知运行模式，按手动按钮补证口径处理";
  })();
  const ordinaryQuantSourceState = [
    `本地缓存：${ordinaryQuantCacheSourceLabel}`,
    `Tushare-first：${ordinaryQuantTushareFirstDataChainLabel}`,
    `DeepSeek 解释：${ordinaryQuantDeepSeekSourceLabel}`,
    `模型状态：${ordinaryQuantModelSourceLabel}`,
    `Pending 状态：${ordinaryQuantPendingStateLabel}`
  ].join(" / ");
  const ordinaryQuantDataLedgerRows = toRows(dataLedger.ledger_rows);
  const ordinaryQuantLedgerSourceLabel =
    cacheCallLedger.length || ordinaryQuantDataLedgerRows.length ? "ledger 回放可用" : "等待本地 ledger 回放";
  const ordinaryQuantPacketSourceLabel =
    Object.keys(packet).length ? "packet 回放可用" : "等待本地 packet";
  const ordinaryQuantP2CacheReady =
    candidateRadarSmallDataWriteback.cache_ready === true ||
    candidateRadarSmallDataWriteback.cache_written === true ||
    candidateRadarSmallDataWriteback.small_data_writeback_ready === true ||
    candidateRadarWritebackSurfaceRows.some((row) =>
      String(row["写入面"] ?? row.surface ?? "").toLowerCase().includes("cache") &&
      !String(row["当前状态"] ?? row.status ?? "").includes("等待")
    );
  const ordinaryQuantP2LedgerReady =
    candidateRadarSmallDataWriteback.provider_call_ledger_replayed_from_source_task === true ||
    candidateRadarSmallDataWriteback.provider_call_ledger_written === true ||
    candidateRadarReceiptCallLedger.length > 0 ||
    candidateRadarWritebackSurfaceRows.some((row) =>
      String(row["写入面"] ?? row.surface ?? "").toLowerCase().includes("ledger") &&
      !String(row["当前状态"] ?? row.status ?? "").includes("等待")
    );
  const ordinaryQuantP2PacketReady =
    candidateRadarSmallDataWriteback.packet_ready === true ||
    candidateRadarSmallDataWriteback.packet_written === true ||
    candidateRadarSmallDataWriteback.cache_packet_written === true ||
    Boolean(candidateRadarReceipt.status) ||
    candidateRadarWritebackSurfaceRows.some((row) =>
      String(row["写入面"] ?? row.surface ?? "").toLowerCase().includes("packet") &&
      !String(row["当前状态"] ?? row.status ?? "").includes("等待")
    );
  const ordinaryQuantP2ReadySurfaceCount = [
    ordinaryQuantP2CacheReady,
    ordinaryQuantP2LedgerReady,
    ordinaryQuantP2PacketReady
  ].filter(Boolean).length;
  const ordinaryQuantP2MissingSurfaces = [
    ordinaryQuantP2CacheReady ? "" : "本地缓存",
    ordinaryQuantP2LedgerReady ? "" : "数据凭证",
    ordinaryQuantP2PacketReady ? "" : "结果包"
  ].filter(Boolean);
  const ordinaryQuantP2MissingSurfaceLabel = ordinaryQuantP2MissingSurfaces.length
    ? ordinaryQuantP2MissingSurfaces.join(" / ")
    : "无缺口";
  const ordinaryQuantP2ThreeSurfaceFrontSentence = ordinaryQuantP2ReadySurfaceCount === 3
    ? `${candidateRadarConfirmedSymbol || "当前标的"} P2 本地数据已可从量化页回放：本地缓存、数据凭证、结果包都已接上；继续看支持/压制和次日图谱。`
    : `${candidateRadarConfirmedSymbol || "当前标的"} P2 三面还缺 ${ordinaryQuantP2MissingSurfaceLabel}；先看任务进度或回下一票雷达确认，不从量化页重复创建任务。`;
  const ordinaryQuantP2ThreeSurfaceFrontItems: MetricItem[] = [
    {
      label: "本地缓存",
      value: ordinaryQuantP2CacheReady ? "已回放到本地缓存" : "等待确认后写入本地缓存",
      tone: ordinaryQuantP2CacheReady ? "good" : "warn"
    },
    {
      label: "数据凭证",
      value: ordinaryQuantP2LedgerReady ? "已看到确认后的数据凭证" : "等待确认后写入数据凭证",
      tone: ordinaryQuantP2LedgerReady ? "good" : "warn"
    },
    {
      label: "结果包",
      value: ordinaryQuantP2PacketReady ? "已接上结果包回放" : "等待结果包回放",
      tone: ordinaryQuantP2PacketReady ? "good" : "warn"
    },
    {
      label: "缺口",
      value: ordinaryQuantP2MissingSurfaceLabel,
      tone: ordinaryQuantP2ReadySurfaceCount === 3 ? "good" : "warn"
    },
    {
      label: "下一步",
      value: ordinaryQuantP2ReadySurfaceCount === 3 ? "看支持/压制和次日图谱" : "先看任务进度；需要换标的再回下一票雷达确认",
      tone: ordinaryQuantP2ReadySurfaceCount === 3 ? "good" : "warn"
    },
    {
      label: "边界",
      value: "量化页只读三面回放；不创建第二个 task、不补调 Tushare/DeepSeek、不展示敏感凭据",
      tone: "good"
    }
  ];
  const ordinaryQuantP2P3ConnectionReady =
    ordinaryQuantP2ReadySurfaceCount === 3 && ordinaryQuantCandidateRadarP3Ready;
  const ordinaryQuantP2P3ConnectionPrimaryHref = ordinaryQuantP2P3ConnectionReady
    ? "#factor-score"
    : candidateRadarLatestTaskId
      ? "#tasks"
      : CANDIDATE_CONFIRM_HREF;
  const ordinaryQuantP2P3ConnectionPrimaryLabel = ordinaryQuantP2P3ConnectionReady
    ? "看支持/压制"
    : candidateRadarLatestTaskId
      ? "看任务进度"
      : "回下一票雷达确认";
  const ordinaryQuantP2P3ConnectionSentence = ordinaryQuantP2P3ConnectionReady
    ? `${candidateRadarConfirmedSymbol || "当前标的"} P2/P3 已从同一条确认链接到量化页：三面可读，P3 结果可解释；下一步复核支持/压制和次日图谱。`
    : `${candidateRadarConfirmedSymbol || "当前标的"} P2/P3 仍在接通中：P2 三面 ${ordinaryQuantP2ReadySurfaceCount}/3，P3=${ordinaryQuantCandidateRadarP3Ready ? "可读" : "等待可读结果"}；缺口只显示待回放。`;
  const ordinaryQuantP2P3ConnectionItems: MetricItem[] = [
    {
      label: "同源结果",
      value: candidateRadarLatestTaskId ? "最近确认结果已接上" : "等待下一票雷达确认",
      tone: candidateRadarLatestTaskId ? "good" : "warn"
    },
    {
      label: "P2 三面",
      value: ordinaryQuantP2ReadySurfaceCount === 3 ? "本地缓存 / 数据凭证 / 结果包已可读" : `缺 ${ordinaryQuantP2MissingSurfaceLabel}`,
      tone: ordinaryQuantP2ReadySurfaceCount === 3 ? "good" : "warn"
    },
    {
      label: "P3 结果",
      value: ordinaryQuantCandidateRadarP3Ready ? candidateRadarReadableResult : "等待可读结果回放",
      tone: ordinaryQuantCandidateRadarP3Ready ? "good" : "warn"
    },
    {
      label: "主入口",
      value: ordinaryQuantP2P3ConnectionPrimaryLabel,
      tone: ordinaryQuantP2P3ConnectionReady ? "good" : candidateRadarLatestTaskId ? "warn" : "neutral"
    },
    {
      label: "边界",
      value: "量化页只读合成 P2/P3 本地回放；入口只切换本地页面或锚点，不创建 task、不调用 Tushare/DeepSeek",
      tone: "good"
    }
  ];
  const ordinaryQuantHandoffLocation =
    "交接清单：下一票雷达确认按钮 → Tushare-first task → Factor cache / call_ledger / packet → 次日图谱预览";
  const ordinaryQuantMissingEvidence = [
    Number(runtime.missing_count ?? 0) ? `待补因子数量=${String(runtime.missing_count)}` : "",
    factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "" : "真实小股票池研究证据待确认",
    deepseekProductionActivationReceipt.provider_benchmark_done === true ? "" : "模型解释质量证据待确认",
    tushareProviderPromotionAudit.promotion_ready === true ? "" : "Tushare 数据质量证据待确认"
  ].filter(Boolean).join(" / ") || "本地因子缓存已有；真实数据质量证据仍待补";
  const ordinaryQuantBlockedState = [
    freshnessGate.usable_for_score === false ? "数据太旧，暂不适合推演" : "",
    Number(factorTestProviderValidationBlocker.production_blocker_count ?? 0) > 0 ? "真实数据补证存在阻断" : "",
    Number(deepseekProductionActivationReceipt.blocking_criterion_count ?? 0) > 0 ? "模型解释补证存在阻断" : "",
    bridge.does_not_modify_action === false ? "交易动作边界异常" : ""
  ].filter(Boolean).join(" / ") || "当前缓存未标记阻断或降级";
  const ordinaryQuantDegradedSourceLabel = ordinaryQuantBlockedState.includes("未标记")
    ? "degraded：未标记降级"
    : `degraded：${ordinaryQuantBlockedState}`;
  const ordinaryQuantLastCache = String(
    packet.loaded_at ?? packet.updated_at ?? packet.generated_at ?? freshnessGate.latest_data_date ?? "暂无最近可用缓存"
  );
  const ordinaryQuantRadarHandoffState = empty
    ? "等待下一票雷达搜票生成本地量化推演"
    : `已读取本地量化缓存；搜票结果回放看 ${ordinaryQuantLastCache}`;
  const ordinaryQuantReplayLocation =
    "回放位置：Factor cache / Next Session preview / DeepSeek status；不从本页补调 provider/model";
  const ordinaryQuantResultLocation =
    "结果位置：本页看支持/压制与模型解释状态，次日图谱预览复核路径，下一票雷达回到代码确认入口；三个位置都只读回放";
  const ordinaryQuantRouteHandoffBoundary =
    "回放入口只切换本地页面/锚点（#next 是本地模块路由，#candidates/... 直达确认输入区，#factor-* 是页内锚点）；不创建 task、不调用 Tushare 或 DeepSeek、不写 cache、不改交易策略";
  const ordinaryQuantFullNextSessionHandoff =
    "完整次日图谱入口：从量化推演摘要打开 #next/next-session-chart 图表区域，复核路径、参考线和操作区；只做本地页面切换";
  const ordinaryQuantFullNextSessionBoundary =
    "打开完整次日图谱不创建 task、不刷新 Tushare/DeepSeek、不写 cache、不改 operation_zones 或 strategy action";
  const ordinaryQuantFullNextSessionRows = [
    {
      交接项: "预览状态",
      当前状态: String(bridge.status ?? bridge.bridge_status ?? (empty ? "等待本地量化缓存" : "等待 next-session bridge cache")),
      用户下一步: empty ? "先回下一票雷达确认代码并生成推演" : "先读本页次日图谱预览，再按需打开完整图谱",
      边界: "预览只读本地 bridge cache；不会补调 Tushare/DeepSeek，也不会写 operation_zones"
    },
    {
      交接项: "完整图谱入口",
      当前状态: ordinaryQuantFullNextSessionHandoff,
      用户下一步: "点击“打开完整次日图谱”只切换到 #next/next-session-chart，本地复核路径、参考线和操作区",
      边界: ordinaryQuantFullNextSessionBoundary
    },
    {
      交接项: "阅读顺序",
      当前状态: "支持/压制 -> 次日图谱预览 -> 完整次日图谱 -> 缺少证据",
      用户下一步: "完整图谱页继续按路径、参考线、操作区、缺口边界复核",
      边界: "完整图谱仍是研究回放，不是买卖、下单或 strategy action"
    }
  ];
  const ordinaryQuantReviewOrder = empty
    ? "先回下一票雷达确认输入区输入代码并确认生成；本页只等本地结果回放"
    : "先看支持/压制，再看次日图谱预览，最后看模型解释状态；不要从工程审计表开始";
  const ordinaryQuantResultComposition = [
    `支持 ${String(score.support_factors?.length ?? 0)} / 压制 ${String(score.suppress_factors?.length ?? 0)} / 冲突 ${String(score.conflict_factors?.length ?? 0)} / 缺失 ${String(score.missing_factors?.length ?? 0)}`,
    `次日图谱：${String(bridge.status ?? bridge.bridge_status ?? "等待本地缓存")}`,
    `模型解释：${ordinaryQuantDeepSeekSourceLabel}`
  ].join(" / ");
  const ordinaryQuantP3ReadableConclusion = ordinaryQuantCandidateRadarP3Ready
    ? `P3 可读结论：${candidateRadarReadableResult}`
    : empty
      ? "P3 可读结论：暂无本地量化推演；先回下一票雷达确认代码"
      : `P3 可读结论：${ordinaryQuantResultComposition}`;
  const ordinaryQuantP3NextStep = ordinaryQuantCandidateRadarP3Ready
    ? `P3 下一步：${candidateRadarReadableNextStep}`
    : empty
      ? "P3 下一步：回下一票雷达确认输入区输入代码并点击确认；输入股票代码本身不创建 task"
      : "P3 下一步：按支持/压制 -> 次日图谱预览 -> DeepSeek 状态复核；需要更新才点击按钮创建 POST task";
  const ordinaryQuantP3Boundary = ordinaryQuantCandidateRadarP3Ready
    ? `P3 边界：${candidateRadarReadableBoundary}`
    : "P3 边界：普通摘要只读 Factor cache、Next Session preview 和 DeepSeek status；不创建 task、不调用 Tushare/DeepSeek、不写 cache、不改 operation_zones 或 strategy action";
  const ordinaryQuantTushareDataCardLedgerReady =
    ordinaryQuantTushareFirstProviderSuccessCount > 0 ||
    factorPacketCandidateHandoff.provider_call_ledger_replayed_from_source_task === true ||
    factorPacketCandidateHandoff.source_task_tushare_provider_ledger_ready === true ||
    candidateRadarSmallDataWriteback.provider_call_ledger_replayed_from_source_task === true ||
    candidateRadarSmallDataWriteback.provider_call_ledger_written === true ||
    candidateRadarSmallDataWriteback.source_task_tushare_provider_ledger_ready === true;
  const ordinaryQuantTushareDataCardSummary = ordinaryQuantTushareDataCardLedgerReady
    ? `${candidateRadarConfirmedSymbol || "当前标的"} Tushare 数据卡：${ordinaryQuantTushareFirstProviderLedgerRatio} 个接口已从 CandidateRadar 本地账本回放。`
    : candidateRadarLatestTaskId
      ? "Tushare 数据卡等待任务回写：先看任务进度，成功后刷新本地 cache。"
      : "Tushare 数据卡等待确认：先回下一票雷达输入股票代码并点击确认。";
  const ordinaryQuantTushareDataCardGap = ordinaryQuantTushareDataCardLedgerReady
    ? ordinaryQuantP2ReadySurfaceCount === 3
      ? "Tushare 账本和 P2 三面都已进入本地回放。"
      : `已有 Tushare 账本；P2 三面还缺 ${ordinaryQuantP2MissingSurfaceLabel}。`
    : "缺 Tushare call_ledger；等待确认任务、本地阻断或后续授权回写。";
  const ordinaryQuantTushareDataCardNext = ordinaryQuantTushareDataCardLedgerReady
    ? ordinaryQuantP2ReadySurfaceCount === 3
      ? "看支持/压制和完整次日图谱。"
      : "继续看任务进度或刷新本地 cache，等 P2 三面齐备。"
    : "回下一票雷达确认输入区，确认后再回量化页读数据卡。";
  const ordinaryQuantTushareDataCapabilityHandoff = ordinaryQuantTushareDataCardLedgerReady
    ? "已有确认后数据账本；接口受限、空窗口或待补原因可去数据能力页复核。"
    : "等待确认后数据账本；先去数据能力页看 Tushare 可用、受限和待补状态。";
  const ordinaryQuantTushareDataCardItems: MetricItem[] = [
    {
      label: "Tushare 数据卡",
      value: ordinaryQuantTushareDataCardSummary,
      tone: ordinaryQuantTushareDataCardLedgerReady ? "good" : candidateRadarLatestTaskId ? "warn" : "neutral"
    },
    {
      label: "接口回放",
      value: ordinaryQuantTushareDataCardLedgerReady ? ordinaryQuantTushareFirstProviderLedgerRatio : "等待本地账本",
      tone: ordinaryQuantTushareDataCardLedgerReady ? "good" : "warn"
    },
    {
      label: "P2 三面",
      value: `${ordinaryQuantP2ReadySurfaceCount}/3；${ordinaryQuantP2MissingSurfaceLabel}`,
      tone: ordinaryQuantP2ReadySurfaceCount === 3 ? "good" : "warn"
    },
    {
      label: "P3 结论",
      value: ordinaryQuantP3ReadableConclusion,
      tone: ordinaryQuantCandidateRadarP3Ready || !empty ? "good" : "warn"
    },
    {
      label: "模型解释",
      value: candidateRadarOrdinaryDeepSeekState,
      tone: candidateRadarUsesModelOutput ? "warn" : "good"
    },
    {
      label: "缺口",
      value: ordinaryQuantTushareDataCardGap,
      tone: ordinaryQuantTushareDataCardLedgerReady && ordinaryQuantP2ReadySurfaceCount === 3 ? "good" : "warn"
    },
    {
      label: "下一步",
      value: ordinaryQuantTushareDataCardNext,
      tone: ordinaryQuantTushareDataCardLedgerReady ? "good" : "warn"
    },
    {
      label: "数据能力回看",
      value: ordinaryQuantTushareDataCapabilityHandoff,
      tone: ordinaryQuantTushareDataCardLedgerReady ? "good" : "warn"
    },
    {
      label: "边界",
      value: "只读 CandidateRadar cache / call_ledger / packet；不会从 Factor 页调用 Tushare/DeepSeek、创建第二个 task 或交易",
      tone: "good"
    }
  ];
  const ordinaryQuantTushareDataCardRows = candidateRadarProviderApiRows.length
    ? candidateRadarProviderApiRows.slice(0, 6).map((row) => ({
        接口: String(row.api ?? row.interface ?? row.name ?? row.provider_api ?? row["接口"] ?? "Tushare light"),
        当前状态: String(row.ordinary_label ?? row.status ?? row.call_status ?? row["当前状态"] ?? "等待回放"),
        证据: String(row.evidence ?? row.call_ledger_key ?? row.scope_hash_short ?? "CandidateRadar provider api row"),
        用户下一步: String(row.next_action ?? row["用户下一步"] ?? ordinaryQuantTushareDataCardNext),
        边界: String(row.boundary ?? row["边界"] ?? "接口回放只读本地账本；不会补调数据源、模型或交易")
      }))
    : [
        {
          接口: "trade_cal / daily / daily_basic / moneyflow",
          当前状态: ordinaryQuantTushareDataCardLedgerReady
            ? `已看到 Tushare 账本 ${ordinaryQuantTushareFirstProviderLedgerRatio}`
            : "等待 Tushare 账本或本地阻断回放",
          证据: String(candidateRadarSmallDataWriteback.provider_call_source ?? "pending_no_provider_call"),
          用户下一步: ordinaryQuantTushareDataCardNext,
          边界: "接口明细只读 CandidateRadar cache；不会补调数据源、模型或交易"
        }
      ];
  const ordinaryQuantP3ExplainableSourceLine = ordinaryQuantCandidateRadarP3Ready
    ? `来源已接上：最近确认结果已回放；${ordinaryQuantTushareFirstDataChainLabel}；P2 三面 ${ordinaryQuantP2ReadySurfaceCount}/3`
    : empty
      ? "来源待确认：先回下一票雷达确认代码，等待本地缓存、数据凭证和结果包回放"
      : `来源回放：Factor cache / Next Session preview；${ordinaryQuantTushareFirstDataChainLabel}`;
  const ordinaryQuantP3ExplainableGapLine = ordinaryQuantP2ReadySurfaceCount < 3
    ? `P2 三面还缺 ${ordinaryQuantP2MissingSurfaceLabel}；先看任务进度或回下一票雷达确认`
    : ordinaryQuantCandidateRadarP3Ready
      ? "暂无阻断性 P3 缺口；仍只作为研究线索"
      : ordinaryQuantMissingEvidence;
  const ordinaryQuantP3ExplainableNextStep = ordinaryQuantCandidateRadarP3Ready
    ? candidateRadarReadableNextStep
    : empty
      ? "回下一票雷达确认输入区输入代码并点击确认"
      : "先看支持/压制，再看次日图谱预览；DeepSeek 状态只作 P5 治理提示";
  const ordinaryQuantP3ExplainableSentence = ordinaryQuantCandidateRadarP3Ready
    ? `P3 可解释结果：${candidateRadarReadableResult}；${ordinaryQuantP3ExplainableSourceLine}；${ordinaryQuantP3ExplainableGapLine}；下一步=${ordinaryQuantP3ExplainableNextStep}。`
    : `P3 等待可解释结果：${ordinaryQuantP3ExplainableSourceLine}；${ordinaryQuantP3ExplainableGapLine}；下一步=${ordinaryQuantP3ExplainableNextStep}。`;
  const ordinaryQuantP3ExplainableFrontItems: MetricItem[] = [
    {
      label: "结论",
      value: ordinaryQuantCandidateRadarP3Ready ? candidateRadarReadableResult : ordinaryQuantP3ReadableConclusion,
      tone: ordinaryQuantCandidateRadarP3Ready || !empty ? "good" : "warn"
    },
    {
      label: "来源",
      value: ordinaryQuantP3ExplainableSourceLine,
      tone: ordinaryQuantCandidateRadarP3Ready || !empty ? "good" : "warn"
    },
    {
      label: "缺口",
      value: ordinaryQuantP3ExplainableGapLine,
      tone: ordinaryQuantP2ReadySurfaceCount === 3 && ordinaryQuantCandidateRadarP3Ready ? "good" : "warn"
    },
    {
      label: "下一步",
      value: ordinaryQuantP3ExplainableNextStep,
      tone: ordinaryQuantCandidateRadarP3Ready || !empty ? "good" : "warn"
    },
    {
      label: "图谱入口",
      value: "打开完整次日图谱只切换本地 #next/next-session-chart",
      tone: "good"
    },
    {
      label: "边界",
      value: "P3 解释条只读本地结果与次日图谱预览；不调用 DeepSeek、不下单、不改交易策略",
      tone: "good"
    }
  ];
  const ordinaryQuantResultRouteReady = ordinaryQuantCandidateRadarP3Ready || !empty;
  const ordinaryQuantResultRouteSentence = ordinaryQuantResultRouteReady
    ? `${candidateRadarConfirmedSymbol || "当前标的"} 量化结果路标：先看支持/压制，再打开完整次日图谱；换标的回下一票雷达确认。`
    : "量化结果路标：先回下一票雷达确认代码；确认完成后再看支持/压制和完整次日图谱。";
  const ordinaryQuantResultRouteBoundary =
    "量化结果路标只切换本地页面或锚点；不创建 task、不调用 Tushare/DeepSeek、不写 cache、不交易、不改交易策略";
  const ordinaryQuantResultRouteItems: MetricItem[] = [
    { label: "当前结果", value: ordinaryQuantP3ReadableConclusion, tone: ordinaryQuantResultRouteReady ? "good" : "warn" },
    { label: "先看哪里", value: ordinaryQuantResultRouteReady ? "支持/压制摘要" : "下一票雷达确认输入区", tone: ordinaryQuantResultRouteReady ? "good" : "warn" },
    { label: "图谱", value: ordinaryQuantFullNextSessionHandoff, tone: ordinaryQuantResultRouteReady ? "good" : "warn" },
    { label: "换标的", value: "回下一票雷达确认输入区；输入静默，确认按钮才创建 Tushare-first task", tone: "good" },
    { label: "边界", value: ordinaryQuantResultRouteBoundary, tone: "good" }
  ];
  const ordinaryQuantP3OneScreenItems: MetricItem[] = factorPacketP3OneScreenRows.length
    ? factorPacketP3OneScreenRows.map((row) => {
        const tone = String(row.tone ?? "neutral");
        return {
          label: String(row.label ?? row["状态项"] ?? "P3 一屏项"),
          value: String(row.value ?? row["当前状态"] ?? "--"),
          tone: (["good", "warn", "bad", "neutral"].includes(tone) ? tone : "neutral") as MetricItem["tone"]
        };
      })
    : [
        { label: "当前结论", value: candidateRadarReadableResult, tone: ordinaryQuantCandidateRadarP3Ready ? "good" : "warn" },
        { label: "来源状态", value: candidateRadarLatestTaskId ? "最近确认结果已回放" : "等待下一票雷达确认", tone: candidateRadarLatestTaskId ? "good" : "warn" },
        { label: "Tushare-first", value: ordinaryQuantTushareFirstDataChainLabel, tone: ordinaryQuantTushareFirstProviderSuccessCount > 0 ? "good" : "warn" },
        { label: "支持/压制", value: ordinaryQuantResultComposition, tone: empty ? "warn" : "good" },
        { label: "下一步", value: candidateRadarReadableNextStep },
        { label: "DeepSeek", value: candidateRadarOrdinaryDeepSeekState, tone: candidateRadarUsesModelOutput ? "warn" : "good" },
        { label: "边界", value: "只读 cache / handoff；不创建 task、不外联、不交易、不改 action", tone: "good" }
      ];
  const ordinaryQuantCrossPageReplayItems: MetricItem[] = [
    {
      label: "同源标的",
      value: candidateRadarConfirmedSymbol || "等待下一票雷达确认",
      tone: candidateRadarConfirmedSymbol ? "good" : "warn"
    },
    {
      label: "来源任务",
      value: candidateRadarLatestTaskId || "等待确认 task",
      tone: candidateRadarLatestTaskId ? "good" : "warn"
    },
    {
      label: "本页结果",
      value: ordinaryQuantP3ReadableConclusion,
      tone: ordinaryQuantCandidateRadarP3Ready || !empty ? "good" : "warn"
    },
    {
      label: "去图谱",
      value: ordinaryQuantFullNextSessionHandoff,
      tone: ordinaryQuantCandidateRadarP3Ready || !empty ? "good" : "warn"
    },
    {
      label: "换标的",
      value: "回下一票雷达确认输入区；输入仍静默，确认按钮才创建 Tushare-first task",
      tone: "good"
    },
    {
      label: "边界",
      value: "Factor / Next / Radar 只做本地路由回放；不创建第二个 task、不调用 Tushare/DeepSeek、不改交易策略",
      tone: "good"
    }
  ];
  const ordinaryQuantPostConfirmReplayContractReady =
    ordinaryQuantPostConfirmReplayContract.schema_version === "candidate_radar_search_quant_projection_post_confirm_replay_contract.v1";
  const ordinaryQuantPostConfirmReplaySequence = Array.isArray(ordinaryQuantPostConfirmReplayContract.readback_sequence)
    ? ordinaryQuantPostConfirmReplayContract.readback_sequence.map(String).join(" -> ")
    : "等待下一票雷达确认任务回放后端合同";
  const ordinaryQuantPostConfirmReplaySurfaces = Array.isArray(ordinaryQuantPostConfirmReplayContract.writeback_surfaces)
    ? ordinaryQuantPostConfirmReplayContract.writeback_surfaces.map(String).join(" / ")
    : "cache / call_ledger / packet";
  const ordinaryQuantPostConfirmReplayAnchors = Array.isArray(ordinaryQuantPostConfirmReplayContract.result_anchors)
    ? ordinaryQuantPostConfirmReplayContract.result_anchors.map(String).join(" / ")
    : "#tasks / #factor / #next";
  const ordinaryQuantPostConfirmReplayContractRows = [
    {
      合同项: "任务回执",
      当前状态: ordinaryQuantPostConfirmReplayContractReady ? "CandidateRadar call_ledger safe params 已回放后端合同" : "等待下一票雷达确认按钮返回后端合同",
      用户下一步: ordinaryQuantPostConfirmReplayContractReady ? "按合同顺序回读任务编号、TaskStatusPanel 和本地 cache" : "回下一票雷达确认输入区输入代码并点击确认",
      证据: "ordinary_post_confirm_replay_contract",
      边界: "量化页只读合同；不会从量化页创建第二个 task"
    },
    {
      合同项: "回放顺序",
      当前状态: ordinaryQuantPostConfirmReplaySequence,
      用户下一步: "先看任务编号，再等 TaskStatusPanel success，最后刷新本地 cache",
      证据: "readback_sequence",
      边界: "React render 不补调 provider/model；GET cache 只读"
    },
    {
      合同项: "P2 三面",
      当前状态: ordinaryQuantPostConfirmReplaySurfaces,
      用户下一步: "确认 cache、call_ledger、packet 是否可回放",
      证据: "writeback_surfaces",
      边界: "call_ledger 只由下一票雷达 POST task / worker 产生；量化页不展示凭据或 raw log"
    },
    {
      合同项: "结果入口",
      当前状态: ordinaryQuantPostConfirmReplayAnchors,
      用户下一步: "任务成功后打开任务进度、量化推演和次日图谱",
      证据: "result_anchors",
      边界: "结果入口只切换本地模块；不交易、不下单、不改 strategy action"
    }
  ];
  const ordinaryQuantBackendPostConfirmOneGlanceItems: MetricItem[] = candidateRadarPostConfirmOneGlanceRows.map((row) => {
    const tone = String(row.tone ?? "neutral");
    return {
      label: String(row.label ?? row["状态项"] ?? row.item_key ?? "确认后状态"),
      value: String(row.value ?? row["当前状态"] ?? row.status ?? "--"),
      tone: (["good", "warn", "bad", "neutral"].includes(tone) ? tone : "neutral") as MetricItem["tone"]
    };
  });
  const ordinaryQuantFallbackLatestCandidateCheckpointItems: MetricItem[] = [
    {
      label: "确认标的",
      value: candidateRadarConfirmedSymbol || "--",
      tone: candidateRadarConfirmedSymbol ? "good" : "warn"
    },
    {
      label: "任务编号",
      value: candidateRadarLatestTaskId ? `task_id=${candidateRadarLatestTaskId}` : "等待 CandidateRadar 确认任务",
      tone: candidateRadarLatestTaskId ? "good" : "warn"
    },
    {
      label: "P1 确认",
      value: candidateRadarConfirmChainStatus || "等待确认按钮",
      tone: candidateRadarLatestTaskId ? "good" : "warn"
    },
    {
      label: "P2 三面",
      value: candidateRadarSmallDataWriteback.small_data_writeback_ready === true
        ? "cache / call_ledger / packet 已回放"
        : candidateRadarSmallDataStateLabel,
      tone: candidateRadarSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn"
    },
    {
      label: "P3 结论",
      value: ordinaryQuantP3ReadableConclusion,
      tone: ordinaryQuantCandidateRadarP3Ready || !empty ? "good" : "warn"
    },
    {
      label: "后端回放合同",
      value: ordinaryQuantPostConfirmReplayContractReady ? "已从 CandidateRadar call_ledger safe params 回放" : "等待下一票雷达确认后回放",
      tone: ordinaryQuantPostConfirmReplayContractReady ? "good" : "warn"
    },
    {
      label: "下一步",
      value: ordinaryQuantP3NextStep,
      tone: "neutral"
    },
    {
      label: "边界",
      value: "本 checkpoint 只读 CandidateRadar cache / ledger / packet；不创建 task、不补调 Tushare/DeepSeek、不改 action",
      tone: "good"
    }
  ];
  const ordinaryQuantLatestCandidateCheckpointItems: MetricItem[] = ordinaryQuantBackendPostConfirmOneGlanceItems.length
    ? ordinaryQuantBackendPostConfirmOneGlanceItems
    : ordinaryQuantFallbackLatestCandidateCheckpointItems;
  const ordinaryQuantTaskSourceReadbackItems: MetricItem[] = [
    {
      label: "来源 task",
      value: candidateRadarLatestTaskId ? `task_id=${candidateRadarLatestTaskId}` : "等待下一票雷达确认 task",
      tone: candidateRadarLatestTaskId ? "good" : "warn"
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
      value: "量化页只读 CandidateRadar cache；不创建第二个 task、不补调 Tushare/DeepSeek",
      tone: "good"
    }
  ];
  const ordinaryQuantResultBoundary =
    "结果只用于研究复核；支持/压制、次日图谱和模型解释都不能直接变成买卖指令";
  const ordinaryDeepSeekGovernedExecutorState =
    deepseek.called === true
      ? "已有本地模型解释缓存；仍只解释不改数值或动作"
      : "等待 governed executor；不阻塞 Tushare-first、支持/压制和次日图谱";
  const ordinaryQuantResultRailState = [
    empty ? "waiting_radar_confirm" : "factor_cache_visible",
    bridge.status || bridge.bridge_status ? "next_preview_visible" : "next_preview_waiting",
    deepseek.called === true ? "deepseek_cache_visible" : "deepseek_governed_pending"
  ].join(" ");
  const ordinaryQuantResultRailSteps = [
    {
      label: "雷达确认",
      state: empty ? ("waiting" as const) : ("done" as const),
      detail: empty ? "回下一票雷达确认输入区输入代码并点击确认" : ordinaryQuantRadarHandoffState
    },
    {
      label: "Factor cache",
      state: empty ? ("waiting" as const) : ("done" as const),
      detail: ordinaryQuantCacheSourceLabel
    },
    {
      label: "次日图谱",
      state: empty ? ("waiting" as const) : (bridge.status || bridge.bridge_status) ? ("done" as const) : ("active" as const),
      detail: String(bridge.status ?? bridge.bridge_status ?? "等待本地 bridge cache")
    },
    {
      label: "DeepSeek 状态",
      state: deepseek.called === true ? ("done" as const) : empty ? ("waiting" as const) : ("active" as const),
      detail: ordinaryDeepSeekGovernedExecutorState
    }
  ];
  const ordinaryQuantUpstreamOneScreenRows = candidateRadarOneScreenRows.length
    ? candidateRadarOneScreenRows.map((row) => ({
        行动: String(row["行动"] ?? row.action_key ?? "行动"),
        当前状态: String(row["当前状态"] ?? row.status ?? "等待上游回放"),
        用户下一步: String(row["用户下一步"] ?? row.next_action ?? ordinaryQuantP3NextStep),
        入口: String(row["入口"] ?? row.entry ?? "下一票雷达"),
        边界: String(row["边界"] ?? row.boundary ?? "量化页只读回放 CandidateRadar packet；不会从结果页创建 task 或调用模型。")
      }))
    : [
        {
          行动: "1. 确认",
          当前状态: empty ? "等待下一票雷达确认代码" : ordinaryQuantRadarHandoffState,
          用户下一步: empty ? "回下一票雷达确认输入区输入代码并点击确认按钮" : ordinaryQuantReviewOrder,
          入口: "#candidates",
          边界: "本页不接收代码输入；换标的必须回下一票雷达确认按钮，页面链接只做本地切换。"
        },
        {
          行动: "2. 任务",
          当前状态: "等待 CandidateRadar task id / TaskStatusPanel 回放",
          用户下一步: "确认任务完成后刷新本地 cache，再回到量化推演页读结果",
          入口: "下一票雷达确认按钮 / TaskStatusPanel",
          边界: "只有下一票雷达确认按钮可创建 Tushare-first POST task；本页不提交上游 task。"
        },
        {
          行动: "3. 写回",
          当前状态: `${ordinaryQuantLedgerSourceLabel} / ${ordinaryQuantPacketSourceLabel}`,
          用户下一步: "按 cache、call_ledger、packet 三面确认结果来源",
          入口: "Factor cache / call_ledger / packet",
          边界: "写回只读本地 cache / ledger / packet；不补调 provider/model、不展示敏感凭据。"
        },
        {
          行动: "4. 结果",
          当前状态: ordinaryQuantP3ReadableConclusion,
          用户下一步: ordinaryQuantP3NextStep,
          入口: "支持/压制 / 次日图谱预览 / DeepSeek 状态",
          边界: ordinaryQuantP3Boundary
        }
      ];
  const ordinaryQuantUpstreamOneScreenLabel = ordinaryQuantUpstreamOneScreenRows
    .map((row) => `${row.行动}: ${row.当前状态}`)
    .join(" / ");
  const ordinaryQuantUpstreamConfirmOutcomeRows = candidateRadarConfirmOutcomeRows.length
    ? candidateRadarConfirmOutcomeRows.map((row) => ({
        确认结果: String(row["速读项"] ?? row.outcome_key ?? "确认结果"),
        当前状态: String(row["当前状态"] ?? row.status ?? "等待 CandidateRadar 确认结果回放"),
        用户下一步: String(row["用户下一步"] ?? row.next_step ?? ordinaryQuantP3NextStep),
        入口: String(row["入口"] ?? row.entry ?? "下一票雷达 / 股票量化推演"),
        边界: String(row["边界"] ?? row.boundary ?? "量化页只读回放确认结果；不创建 task、不调用 provider/model。")
      }))
    : [
        {
          确认结果: "P1 确认结果",
          当前状态: "等待下一票雷达确认任务回放",
          用户下一步: "回下一票雷达确认输入区输入代码并点击确认按钮。",
          入口: "#candidates",
          边界: "量化页不接收换标的输入；确认按钮之前不创建 Tushare-first task。"
        },
        {
          确认结果: "P2 写回结果",
          当前状态: `${ordinaryQuantLedgerSourceLabel} / ${ordinaryQuantPacketSourceLabel}`,
          用户下一步: "确认 cache / call_ledger / packet 已能支撑量化推演回放。",
          入口: "Factor cache / call_ledger / packet",
          边界: "只读本地回放；不补调 Tushare、DeepSeek 或 GitHub。"
        },
        {
          确认结果: "P3 回放结果",
          当前状态: ordinaryQuantP3ReadableConclusion,
          用户下一步: ordinaryQuantP3NextStep,
          入口: "支持/压制 / 次日图谱预览 / DeepSeek 状态",
          边界: ordinaryQuantP3Boundary
        }
      ];
  const ordinaryQuantUpstreamConfirmOutcomeLabel = ordinaryQuantUpstreamConfirmOutcomeRows
    .map((row) => `${row.确认结果}: ${row.当前状态}`)
    .join(" / ");
  const ordinaryQuantSmallDataWritebackState = candidateRadarSmallDataStateLabel;
  const ordinaryQuantP2WritebackBoundary =
    "P2 小数据只从 CandidateRadar cache / call_ledger / packet 回放；Factor 页 GET cache 不创建 task、不补调 Tushare/DeepSeek、不展示 token/key 或 raw log；不展示敏感凭据或 raw log。";
  const ordinaryQuantUpstreamP2WritebackRows = candidateRadarWritebackSurfaceRows.length
    ? candidateRadarWritebackSurfaceRows.map((row) => ({
        写入面: String(row["写入面"] ?? row.surface ?? "writeback"),
        当前状态: String(row["当前状态"] ?? row.status ?? ordinaryQuantSmallDataWritebackState),
        回放来源: String(row["回放来源"] ?? row.readback_source ?? "GET /api/candidate-radar/cache"),
        下一步: String(row["下一步"] ?? row.next_action ?? "确认任务完成后刷新本地 cache 回放"),
        边界: String(row["边界"] ?? row.boundary ?? ordinaryQuantP2WritebackBoundary)
      }))
    : [
        {
          写入面: "cache",
          当前状态: ordinaryQuantSmallDataWritebackState,
          回放来源: "search_quant_projection_small_data_writeback_summary",
          下一步: "先去下一票雷达确认输入区输入代码并点击确认",
          边界: ordinaryQuantP2WritebackBoundary
        },
        {
          写入面: "call_ledger",
          当前状态: ordinaryQuantLedgerSourceLabel,
          回放来源: "ordinary_writeback_surface_summary_rows pending",
          下一步: "任务完成后只读查看 ledger 状态；接口明细留在雷达高级状态",
          边界: "call_ledger 只由按钮门控后台任务产生；Factor 页不补调 provider/model。"
        },
        {
          写入面: "packet",
          当前状态: ordinaryQuantPacketSourceLabel,
          回放来源: "command_center_3_candidate_radar_cache",
          下一步: "刷新 cache 后回放股票量化推演和次日图谱",
          边界: "packet 不含凭据、不生成交易动作、不覆盖 strategy action。"
        }
      ];
  const ordinaryQuantUpstreamP2WritebackLabel = ordinaryQuantUpstreamP2WritebackRows
    .map((row) => `${row.写入面}: ${row.当前状态}`)
    .join(" / ");
  const ordinaryQuantResultReplayRows = [
    {
      结果段: "支持/压制",
      可读结论: empty ? "等待下一票雷达生成本地量化推演" : `支持 ${String(score.support_factors?.length ?? 0)} / 压制 ${String(score.suppress_factors?.length ?? 0)} / 冲突 ${String(score.conflict_factors?.length ?? 0)} / 缺失 ${String(score.missing_factors?.length ?? 0)}`,
      证据: ordinaryQuantCacheSourceLabel,
      下一步: "先看因子方向和缺失项，再决定是否需要手动刷新或回到雷达换标的",
      边界: "只读 Factor cache，不创建 task、不调用 Tushare/DeepSeek"
    },
    {
      结果段: "次日图谱预览",
      可读结论: `图谱状态：${String(bridge.status ?? bridge.bridge_status ?? "等待本地缓存")}`,
      证据: "Next Session preview / bridge cache",
      下一步: "再打开次日图谱复核路径、参考线和操作区",
      边界: "预览不改 operation_zones，不写交易动作"
    },
    {
      结果段: "模型解释状态",
      可读结论: ordinaryQuantDeepSeekSourceLabel,
      证据: ordinaryQuantModelSourceLabel,
      下一步: "DeepSeek governed executor 完成前只看 skipped/pending 状态",
      边界: "模型解释不覆盖价格、因子、持仓、操作区或 strategy action"
    }
  ];
  const ordinaryFactorReviewRows = [
    {
      复核项: "支持",
      当前数量: String(score.support_factors?.length ?? 0),
      看什么: empty ? "等待本地量化推演结果" : "先看支持因子是否来自当前 cache，并和压制、冲突一起读",
      下一步: "支持项多时仍要检查压制和缺失；不能直接当买入理由",
      边界: "支持因子只作研究解释，不生成买入指令、不写 strategy action"
    },
    {
      复核项: "压制",
      当前数量: String(score.suppress_factors?.length ?? 0),
      看什么: empty ? "等待本地量化推演结果" : "看哪些因素压制推演，以及是否来自数据缺口或真实风险",
      下一步: "压制项明显时优先复核次日图谱和风险提示",
      边界: "压制因子只提示复核方向，不生成卖出或减仓指令"
    },
    {
      复核项: "冲突",
      当前数量: String(score.conflict_factors?.length ?? 0),
      看什么: empty ? "等待本地量化推演结果" : "看支持和压制是否互相抵消，避免只读单边结论",
      下一步: "冲突存在时先回到证据来源和图谱路径，不急着推演动作",
      边界: "冲突只表示证据分歧，不重排候选、不修改交易动作"
    },
    {
      复核项: "缺失",
      当前数量: String(score.missing_factors?.length ?? 0),
      看什么: empty ? "等待本地量化推演结果" : "看哪些因子缺数据，避免把空值误读成中性或无风险",
      下一步: "缺失项多时优先看 cache / ledger / packet 和待补证据",
      边界: "缺失只提示后续补证，不从页面渲染补调 Tushare/DeepSeek"
    }
  ];
  const ordinaryQuantHandoffRows = [
    {
      交接段: "按钮确认",
      用户看到: empty ? "先回下一票雷达确认输入区输入代码并确认生成" : "已从本地量化缓存读取确认后的推演结果",
      写入位置: "确认按钮创建 POST task 后才可写入本地 cache / ledger / packet",
      边界: "输入股票代码、页面打开、React render 和 GET cache 都不自动外联"
    },
    {
      交接段: "Factor cache",
      用户看到: ordinaryQuantCacheSourceLabel,
      写入位置: "小数据结果回放在 Factor cache；本页只读展示支持/压制",
      边界: "查看本地缓存不创建 task、不调用 Tushare 或 DeepSeek"
    },
    {
      交接段: "call_ledger",
      用户看到: ordinaryQuantLedgerSourceLabel,
      写入位置: "外联证据只看 task/worker 留下的 call_ledger 或 cache envelope ledger",
      边界: "ledger 只展示状态、接口、行数和时间；敏感凭据不进前端、日志、packet 或 cache"
    },
    {
      交接段: "packet",
      用户看到: ordinaryQuantPacketSourceLabel,
      写入位置: "packet 回放用于连接支持/压制、次日图谱预览和模型状态",
      边界: "packet 是研究回放，不覆盖价格、持仓、operation_zones 或 strategy action"
    },
    {
      交接段: "次日图谱",
      用户看到: `桥接状态：${String(bridge.status ?? bridge.bridge_status ?? "等待本地缓存")}`,
      写入位置: "Next Session preview 只读取本地 bridge cache",
      边界: "预览是条件路径复核，不是买入指令、不真实交易、不下单"
    }
  ];
  const ordinaryDeepSeekGovernedExecutorRows = [
    {
      治理段: "基础结果先行",
      当前状态: empty ? "等待本地量化缓存" : "Tushare-first / Factor cache / Next Session preview 可先读",
      用户看到: "支持/压制和次日图谱先显示；DeepSeek 不作为数据源",
      边界: "DeepSeek 不阻塞 Tushare-first、支持/压制和次日图谱"
    },
    {
      治理段: "P5 governed executor 准入",
      当前状态:
        deepseekValidation.model_call_status && deepseekValidation.model_call_status !== "not_called"
          ? "已有受控模型状态记录；仍需检查 model ledger 和脱敏验收"
          : "当前只允许本地 prompt preview / sanitizer / cache ledger；真实模型调用仍待 governed executor",
      用户看到: `validation=${String(deepseekValidation.validation_mode ?? "local_sanitizer_only")} / model_call=${String(deepseekValidation.model_call_status ?? "not_called")}`,
      边界: "P5 不阻塞 Tushare-first、Factor cache 或 Next Session；DeepSeek 不写价格、因子、持仓、operation_zones 或 strategy action"
    },
    {
      治理段: "真实调用门槛",
      当前状态:
        deepseekProductionActivationReceipt.provider_benchmark_done === true &&
        deepseekRetryRepairDryRun.bounded_retry_repair_ready === true &&
        deepseekJsonStability.response_format_enforced === true
          ? "关键门槛已有本地通过记录"
          : "真实调用只能在 governed executor 完成后进入受控按钮任务",
      用户看到: `结构化输出 ${String(deepseekJsonStability.status ?? "missing")} / 修复预检 ${String(deepseekRetryRepairDryRun.status ?? "missing")} / 样本验收 ${String(deepseekProviderBenchmarkScopeTicket.status ?? "missing")}`,
      边界: "结构化输出、重试修复、样本验收和成本证据未齐前不自动调用"
    },
    {
      治理段: "普通页降噪",
      当前状态: "prompt/output 和模型调用明细留在高级审计",
      用户看到: "普通页不展示 prompt/output，只显示是否 skipped/pending/ready",
      边界: "不把本地预检、票据或矩阵当成生产证据"
    },
    {
      治理段: "输出约束",
      当前状态: ordinaryQuantDeepSeekSourceLabel,
      用户看到: "模型解释只辅助阅读，不覆盖价格、factor、持仓、operation_zones 或 strategy action",
      边界: "不真实交易、不下单、不生成买入指令"
    }
  ];
  const ordinaryQuantP5StandaloneGovernanceReady =
    Boolean(deepseekValidation.model_call_status && deepseekValidation.model_call_status !== "not_called");
  const ordinaryQuantP5StandaloneGovernanceSentence = ordinaryQuantP5StandaloneGovernanceReady
    ? "P5 单独补证：已有受控模型状态记录；仍需复核 model_ledger / sanitizer / output acceptance / 白名单字段 / fallback 后再开放真实模型解释。DeepSeek 当前不参与 P1-P3 数据链。"
    : "P5 单独补证：DeepSeek 当前不参与 P1-P3 数据链；Tushare-first、cache/ledger/packet 和次日图谱先可用，真实模型解释等待 governed executor。";
  const ordinaryQuantP5StandaloneGovernanceItems: MetricItem[] = [
    {
      label: "P5 单独补证",
      value: ordinaryDeepSeekGovernedExecutorState,
      tone: candidateRadarUsesModelOutput ? "warn" : "good"
    },
    {
      label: "不阻塞",
      value: "DeepSeek 当前不参与 P1-P3 数据链；P1 Tushare-first、P2 cache/ledger/packet、P3 支持/压制和次日图谱可先读",
      tone: "good"
    },
    {
      label: "放行条件",
      value: "model_ledger / sanitizer / output acceptance / 白名单字段 / fallback 齐备后，才进入 governed executor 按钮任务",
      tone: "warn"
    },
    {
      label: "输出边界",
      value: "模型解释不覆盖价格、因子、operation_zones 或 strategy action；不作为数据源、不真实交易、不下单",
      tone: "good"
    }
  ];
  const ordinaryQuantRuntimeModeLabel = `运行模式：${runtimeModeLabel(ordinaryQuantRuntimeMode)}`;
  const ordinaryQuantTaskBoundary =
    "本页 GET cache 只读；手动刷新、轻量推演、模型整理或 live_light 补证都必须走 POST task，不在 React 渲染中直连 Tushare 或 DeepSeek";
  const ordinaryQuantCacheButtonLabel = "查看本地缓存只读取 GET cache；不会创建 task、不会调用 Tushare 或 DeepSeek";
  const ordinaryQuantRefreshButtonLabel = "手动刷新数据会创建按钮门控 POST task；不从 React render 直连 provider/model";
  const ordinaryQuantRunLightButtonLabel = "运行轻量推演会创建按钮门控 POST task；DeepSeek 整理仍在高级开关";
  const ordinaryQuantStatusLabel = empty
    ? ordinaryQuantCandidateRadarP3Ready
      ? "已回放搜票结论，量化缓存待刷新"
      : "等待量化缓存"
    : "量化缓存可用";
  const ordinaryQuantUserFirstItems: MetricItem[] = [
    {
      label: "当前标的",
      value: candidateRadarConfirmedSymbol || "等待下一票雷达确认",
      tone: candidateRadarConfirmedSymbol ? "good" : "warn"
    },
    {
      label: "现在看什么",
      value: ordinaryQuantCandidateRadarP3Ready || !empty ? candidateRadarReadableResult : ordinaryQuantNextClick,
      tone: ordinaryQuantCandidateRadarP3Ready || !empty ? "good" : "warn"
    },
    {
      label: "下一步",
      value: ordinaryQuantPrimaryActionLabel,
      tone: ordinaryQuantPrimaryActionHref === CANDIDATE_CONFIRM_HREF ? "warn" : "good"
    },
    {
      label: "数据链",
      value: ordinaryQuantTushareFirstDataChainLabel,
      tone: ordinaryQuantTushareFirstProviderSuccessCount > 0 ? "good" : "warn"
    },
    {
      label: "图谱/解释",
      value: `次日图谱：${String(bridge.status ?? bridge.bridge_status ?? "等待本地缓存")} / ${candidateRadarOrdinaryDeepSeekState}`,
      tone: candidateRadarUsesModelOutput ? "warn" : "good"
    },
    {
      label: "边界",
      value: "只读本地结果；不自动外联、不真实交易、不下单、不改 strategy action",
      tone: "good"
    }
  ];
  const ordinaryQuantPlainResultSentence = ordinaryQuantCandidateRadarP3Ready
    ? `${candidateRadarConfirmedSymbol || "当前标的"} 当前结论：${candidateRadarReadableResult}`
    : empty
      ? "还没有可读的本地量化结果；先去下一票雷达确认一只股票。"
      : `${candidateRadarConfirmedSymbol || "当前标的"} 已有本地量化结果；先看支持 ${String(score.support_factors?.length ?? 0)} / 压制 ${String(score.suppress_factors?.length ?? 0)}，再看次日图谱。`;
  const ordinaryQuantPlainGap = empty
    ? "缺少确认后的本地结果；输入股票代码本身保持静默，确认按钮后再回放结果。"
    : ordinaryQuantP2ReadySurfaceCount < 3
      ? `结果链还缺 ${ordinaryQuantP2MissingSurfaceLabel}；先看任务进度或回下一票雷达确认。`
      : ordinaryQuantMissingEvidence.includes("待")
        ? "真实数据质量、小池研究或模型解释证据还没补齐；当前结果先按本地回放阅读。"
        : "暂无页面阻断；当前结果仍只作为研究线索。";
  const ordinaryQuantPlainNow = empty
    ? "去下一票雷达确认股票代码"
    : ordinaryQuantCandidateRadarP3Ready
      ? "先看支持/压制和完整次日图谱；需要补新结果或换标的，再回下一票雷达确认。"
      : "先看支持/压制，再打开完整次日图谱；需要换标的再回下一票雷达确认。";
  const ordinaryQuantPlainSafety = "这只是研究辅助，不是买入、卖出、加仓或减仓指令。";
  const ordinaryQuantPlainConclusionItems: MetricItem[] = [
    {
      label: "一句话",
      value: ordinaryQuantPlainResultSentence,
      tone: ordinaryQuantCandidateRadarP3Ready || !empty ? "good" : "warn"
    },
    {
      label: "缺口",
      value: ordinaryQuantPlainGap,
      tone: ordinaryQuantP2ReadySurfaceCount === 3 && !empty ? "good" : "warn"
    },
    {
      label: "现在做什么",
      value: ordinaryQuantPlainNow,
      tone: empty ? "warn" : "good"
    },
    {
      label: "安全说明",
      value: ordinaryQuantPlainSafety,
      tone: "good"
    }
  ];
  const ordinaryFactorTestProviderSmallPoolState =
    factorTestProductionValidation.provider_backed_small_pool_validation_done === true
      ? "真实小池验收已有直接证据"
      : "真实小池验收未运行；等待授权";
  const ordinaryFactorTestProviderScopeState =
    factorTestProviderSmallPoolDryRun.preflight_ready_for_user_approved_real_task === true
      ? `本地 scope 已就绪：${String(factorTestProviderSmallPoolDryRun.acceptance_scope_hash_short ?? factorTestProviderSmallPoolDryRun.acceptance_scope_hash ?? "已生成")}`
      : "等待小池预检 scope";
  const ordinaryFactorTestProviderRequestState =
    factorTestProviderSmallPoolExecutionRequest.local_execution_request_ready === true
      ? "本地执行请求已绑定 scope；下一步只能是用户授权后的 provider task"
      : "等待本地执行请求；真实任务仍需授权";
  const ordinaryFactorTestProviderEvidenceGap =
    factorTestProductionValidation.provider_backed_small_pool_validation_done === true
      ? "真实小池样本和指标已回放"
      : "还缺真实 provider task、样本行、rolling IC/ICIR、成本、中性化、PIT/bias 和 promotion review";
  const factorTestProviderSmallPoolCredential = (factorTestProviderSmallPoolDryRun.credential_presence_summary as Record<string, unknown> | undefined) ?? {};
  const factorTestProviderSmallPoolBlockers = Array.isArray(factorTestProviderSmallPoolDryRun.blocking_criteria)
    ? factorTestProviderSmallPoolDryRun.blocking_criteria.map((item: unknown) => String(item)).filter(Boolean)
    : [];
  const ordinaryFactorTestProviderCurrentBlockerSentence =
    factorTestProductionValidation.provider_backed_small_pool_validation_done === true
      ? "真实小池 provider-backed 直接证据已可见；仍需按生产阶段清单完成 promotion/release 边界。"
      : `LTG-03 当前 degraded：dry-run=${String(factorTestProviderSmallPoolDryRun.status ?? "missing")}，credential=${String(factorTestProviderSmallPoolCredential.status ?? "unknown")}，blocker=${factorTestProviderSmallPoolBlockers.join(" / ") || "provider_task_and_sample_rows_pending"}；本地 execution request 不能替代真实 provider task，下一步只能是用户授权后的 provider-backed 小池验收。`;
  const ordinaryFactorTestProviderBoundary =
    "本卡只读 Factor cache；不触发 dry-run、execution request 或 provider task；真实小池验收只能在用户明确授权后走 POST task";
  const ordinaryFactorTestProviderQuickReadItems: MetricItem[] = [
    {
      label: "真实验证",
      value: ordinaryFactorTestProviderSmallPoolState,
      tone: factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "good" : "warn"
    },
    {
      label: "授权状态",
      value: ordinaryFactorTestProviderRequestState,
      tone: factorTestProviderSmallPoolExecutionRequest.local_execution_request_ready === true ? "good" : "warn"
    },
    {
      label: "缺口",
      value: ordinaryFactorTestProviderEvidenceGap,
      tone: factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "good" : "warn"
    },
    {
      label: "下一步",
      value: "先看本地 scope / execution request；真实小池验证必须另行授权",
      tone: "warn"
    },
    {
      label: "边界",
      value: "打开页面、查看速读和切换锚点都只读本地 cache；不调用 Tushare/DeepSeek/GitHub、不创建 provider task、不交易",
      tone: "good"
    }
  ];
  const ordinaryQuantVisibleNowItems: MetricItem[] = [
    {
      label: "现在能看到",
      value: `${candidateRadarConfirmedSymbol || "等待确认标的"}；${ordinaryQuantPlainResultSentence}`,
      tone: ordinaryQuantCandidateRadarP3Ready || !empty ? "good" : "warn"
    },
    {
      label: "现在能操作",
      value: ordinaryQuantPrimaryActionLabel,
      tone: ordinaryQuantPrimaryActionHref === CANDIDATE_CONFIRM_HREF ? "warn" : "good"
    },
    {
      label: "真实数据状态",
      value: `${ordinaryFactorTestProviderSmallPoolState}；${ordinaryFactorTestProviderRequestState}`,
      tone: factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "good" : "warn"
    },
    {
      label: "授权后产物",
      value: "scope hash、payload、call_ledger、样本行和 failure-mode evidence",
      tone: "warn"
    },
    {
      label: "下一步入口",
      value: "支持/压制 / 次日图谱 / 下一票雷达确认 / LTG-03 安全闸门",
      tone: "good"
    },
    {
      label: "不会发生",
      value: "页面打开、查看结果和本地跳转不会创建 provider task、不会调用 Tushare/DeepSeek/GitHub、不会交易",
      tone: "good"
    }
  ];
  const ordinaryQuantModeLayeredLiveLightItems: MetricItem[] = [
    {
      label: "缓存渲染层",
      value: "GET cache / React render 只读；页面打开、查看结果和本地路由切换不创建 task、不外联",
      tone: "good"
    },
    {
      label: "按钮任务层",
      value: `${ordinaryQuantRuntimeModeLabel}；manual 或 live_light 补证只能进入显式 POST task / worker / local fallback，本页不自启小池`,
      tone: ordinaryQuantRuntimeMode === "cache_only" ? "good" : "warn"
    },
    {
      label: "真实数据层",
      value: factorTestProductionValidation.provider_backed_small_pool_validation_done === true
        ? "provider-backed 小池直接证据已可见；继续复核样本行、call_ledger 和 failure-mode evidence"
        : `provider-backed 小池仍待授权；需要 scope hash、payload、call_ledger、样本行和 failure-mode evidence；${ordinaryFactorTestProviderEvidenceGap}`,
      tone: factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "good" : "warn"
    },
    {
      label: "模型解释层",
      value: "DeepSeek governed executor 单独排期；不作为数据源，不覆盖价格、因子、operation_zones 或 strategy action",
      tone: "good"
    },
    {
      label: "生产验收层",
      value: "LTG-03 strict closeout 仍按 snapshot；local ticket、dry-run、execution request、matrix 或 sanitizer 不等于 production complete",
      tone: "warn"
    },
    {
      label: "交易隔离层",
      value: "Factor 分数只做研究复核；不接 broker、不创建 order endpoint、不真实交易、不改 strategy action",
      tone: "good"
    }
  ];
  const ordinaryFactorTestProductionStageCount = Number(factorTestProductionStageScopeManifest.stage_count ?? factorTestProductionStageScopeRows.length ?? 0);
  const ordinaryFactorTestProductionStagePendingCount = Number(factorTestProductionStageScopeManifest.pending_stage_count ?? factorTestProductionStageScopeRows.length ?? 0);
  const ordinaryFactorTestProductionStageLocalCount = Number(factorTestProductionStageScopeManifest.local_surface_stage_count ?? 0);
  const ordinaryFactorTestProductionStageDirectCount = Number(factorTestProductionStageScopeManifest.provider_direct_evidence_stage_count ?? 0);
  const ordinaryFactorTestProductionStageStatus =
    ordinaryFactorTestProductionStagePendingCount > 0
      ? `${ordinaryFactorTestProductionStagePendingCount}/${ordinaryFactorTestProductionStageCount || ordinaryFactorTestProductionStagePendingCount} 项仍待真实 provider 直接证据`
      : "生产阶段清单无 pending 项";
  const ordinaryFactorTestProductionStageItems: MetricItem[] = [
    {
      label: "生产阶段",
      value: ordinaryFactorTestProductionStageStatus,
      tone: ordinaryFactorTestProductionStagePendingCount > 0 ? "warn" : "good"
    },
    {
      label: "本地可见",
      value: `${ordinaryFactorTestProductionStageLocalCount} 项 local surface：local light / scope ticket 只证明边界可见`,
      tone: ordinaryFactorTestProductionStageLocalCount > 0 ? "good" : "warn"
    },
    {
      label: "直接证据",
      value: `${ordinaryFactorTestProductionStageDirectCount} 项真实 provider evidence；生产完成前必须补真实 provider task、ledger 和样本行`,
      tone: ordinaryFactorTestProductionStageDirectCount > 0 ? "good" : "warn"
    },
    {
      label: "scope 状态",
      value: String(factorTestProductionStageScopeManifest.scope_ticket_status ?? factorTestProviderSmallPoolDryRun.status ?? "missing"),
      tone: factorTestProviderSmallPoolDryRun.preflight_ready_for_user_approved_real_task === true ? "good" : "warn"
    },
    {
      label: "执行请求",
      value: String(factorTestProductionStageScopeManifest.execution_request_status ?? factorTestProviderSmallPoolExecutionRequest.status ?? "missing"),
      tone: factorTestProviderSmallPoolExecutionRequest.local_execution_request_ready === true ? "good" : "warn"
    },
    {
      label: "边界",
      value: "factor_test_production_stage_scope_manifest 只展示 direct evidence / pending 缺口；不创建 provider task、不调用 Tushare、不标记 production complete",
      tone: "good"
    }
  ];
  const ordinaryFactorTestProviderSmallPoolItems: MetricItem[] = [
    {
      label: "LTG-03",
      value: "Factor Test Lab 真实小股票池研究",
      tone: "warn"
    },
    {
      label: "本地样本",
      value: factorTestSmallPool.local_light_observation_acceptance_done === true ? "local light observations 可回放" : "等待本地 light observations",
      tone: factorTestSmallPool.local_light_observation_acceptance_done === true ? "good" : "warn"
    },
    {
      label: "真实验收",
      value: ordinaryFactorTestProviderSmallPoolState,
      tone: factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "good" : "warn"
    },
    {
      label: "本地 scope",
      value: ordinaryFactorTestProviderScopeState,
      tone: factorTestProviderSmallPoolDryRun.preflight_ready_for_user_approved_real_task === true ? "good" : "warn"
    },
    {
      label: "授权前置",
      value: ordinaryFactorTestProviderRequestState,
      tone: factorTestProviderSmallPoolExecutionRequest.local_execution_request_ready === true ? "good" : "warn"
    },
    {
      label: "还缺",
      value: ordinaryFactorTestProviderEvidenceGap,
      tone: factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "good" : "warn"
    },
    {
      label: "边界",
      value: ordinaryFactorTestProviderBoundary,
      tone: "good"
    }
  ];
  const ordinaryFactorTestSmallPoolEvidenceDone =
    factorTestProductionValidation.provider_backed_small_pool_validation_done === true;
  const ordinaryFactorTestSmallPoolSampleRowsDone =
    ordinaryFactorTestSmallPoolEvidenceDone ||
    factorTestProviderSmallPoolAcceptance.sample_rows_done === true ||
    factorTestProviderSmallPoolAcceptance.sample_rows_written === true;
  const ordinaryFactorTestSmallPoolRollingDone =
    ordinaryFactorTestSmallPoolEvidenceDone ||
    factorTestProviderSmallPoolAcceptance.rolling_validation_done === true ||
    factorTestProviderSmallPoolAcceptance.rolling_ic_done === true ||
    factorTestProviderSmallPoolAcceptance.rolling_icir_done === true;
  const ordinaryFactorTestSmallPoolCostDone =
    ordinaryFactorTestSmallPoolEvidenceDone ||
    factorTestProviderSmallPoolAcceptance.cost_validation_done === true ||
    factorTestProviderSmallPoolAcceptance.cost_model_done === true;
  const ordinaryFactorTestSmallPoolNeutralizationDone =
    ordinaryFactorTestSmallPoolEvidenceDone ||
    factorTestProviderSmallPoolAcceptance.neutralization_done === true ||
    factorTestProviderSmallPoolAcceptance.neutralized_metric_done === true;
  const ordinaryFactorTestSmallPoolBiasDone =
    ordinaryFactorTestSmallPoolEvidenceDone ||
    factorTestProviderSmallPoolAcceptance.pit_bias_review_done === true ||
    factorTestProviderSmallPoolAcceptance.bias_review_done === true;
  const ordinaryFactorTestSmallPoolPromotionDone =
    ordinaryFactorTestSmallPoolEvidenceDone ||
    factorTestProviderSmallPoolAcceptance.promotion_review_done === true ||
    factorTestProviderSmallPoolAcceptance.production_promotion_review_done === true;
  const ordinaryFactorTestSmallPoolEvidenceSentence =
    ordinaryFactorTestSmallPoolEvidenceDone
      ? "真实小池样本证据已回放；继续按样本、滚动、成本、中性化、偏差和推广复核检查生产阶段。"
      : "真实小池样本证据仍待授权：样本、滚动、成本、中性化、偏差和推广复核都要由 future provider task 留痕。";
  const ordinaryFactorTestSmallPoolEvidenceItems: MetricItem[] = [
    {
      label: "样本行",
      value: ordinaryFactorTestSmallPoolSampleRowsDone ? "真实样本行已回放" : "等待 provider task 写入样本行",
      tone: ordinaryFactorTestSmallPoolSampleRowsDone ? "good" : "warn"
    },
    {
      label: "滚动验证",
      value: ordinaryFactorTestSmallPoolRollingDone ? "rolling IC/ICIR 已回放" : "等待 rolling IC/ICIR 证据",
      tone: ordinaryFactorTestSmallPoolRollingDone ? "good" : "warn"
    },
    {
      label: "交易成本",
      value: ordinaryFactorTestSmallPoolCostDone ? "成本假设已回放" : "等待 cost / slippage 证据",
      tone: ordinaryFactorTestSmallPoolCostDone ? "good" : "warn"
    },
    {
      label: "中性化",
      value: ordinaryFactorTestSmallPoolNeutralizationDone ? "中性化结果已回放" : "等待行业/市值中性化证据",
      tone: ordinaryFactorTestSmallPoolNeutralizationDone ? "good" : "warn"
    },
    {
      label: "PIT/bias",
      value: ordinaryFactorTestSmallPoolBiasDone ? "PIT/bias review 已回放" : "等待 point-in-time 和偏差复核",
      tone: ordinaryFactorTestSmallPoolBiasDone ? "good" : "warn"
    },
    {
      label: "推广复核",
      value: ordinaryFactorTestSmallPoolPromotionDone ? "promotion review 已回放" : "等待生产推广复核",
      tone: ordinaryFactorTestSmallPoolPromotionDone ? "good" : "warn"
    },
    {
      label: "授权前",
      value: "只读看本地 scope、execution request、数据能力和任务目录；不把 ticket 当生产验收",
      tone: "good"
    },
    {
      label: "不会发生",
      value: "不会创建 provider task、不会调用 Tushare/DeepSeek/GitHub、不会交易、不改 strategy action",
      tone: "good"
    }
  ];
  const ordinaryFactorTestSmallPoolEvidenceRows = [
    {
      检查项: "1. 样本行",
      当前状态: ordinaryFactorTestSmallPoolSampleRowsDone ? "已回放真实样本行" : "等待真实 provider task 写入样本行",
      用户下一步: "先看本地 scope 和 execution request；授权后才允许生成 provider task。",
      生产口径: "样本行必须和 scope hash、payload、call_ledger 对齐。",
      边界: "本页只读 cache，不补调 Tushare。"
    },
    {
      检查项: "2. 滚动验证",
      当前状态: ordinaryFactorTestSmallPoolRollingDone ? "rolling IC/ICIR 已回放" : "等待多周期 rolling IC/ICIR",
      用户下一步: "授权任务完成后复核窗口、股票池、指标和 failure-mode evidence。",
      生产口径: "rolling 结果必须能解释稳定性，不用单次 light observation 代替。",
      边界: "不从 React render 或 GET cache 计算生产 IC。"
    },
    {
      检查项: "3. 成本和中性化",
      当前状态: ordinaryFactorTestSmallPoolCostDone && ordinaryFactorTestSmallPoolNeutralizationDone ? "成本和中性化已回放" : "等待成本与行业/市值中性化",
      用户下一步: "确认成本假设、slippage、行业和市值中性化都在 provider-backed 包里。",
      生产口径: "成本和中性化必须是同一 scope 的直接证据。",
      边界: "不把本地矩阵或 sanitizer 当生产验收。"
    },
    {
      检查项: "4. PIT/bias",
      当前状态: ordinaryFactorTestSmallPoolBiasDone ? "PIT/bias 已复核" : "等待 point-in-time 和偏差复核",
      用户下一步: "检查未来数据穿越、幸存者偏差和样本选择偏差是否有明示结论。",
      生产口径: "偏差复核必须能和样本行及 ledger 一起回放。",
      边界: "不由模型解释或普通摘要补证。"
    },
    {
      检查项: "5. 推广复核",
      当前状态: ordinaryFactorTestSmallPoolPromotionDone ? "生产推广复核已回放" : "等待 promotion / release review",
      用户下一步: "真实证据齐备后再走 promotion review；strict closeout 仍按 snapshot。",
      生产口径: "promotion review 只能在真实 provider evidence 齐备后推进。",
      边界: "不交易、不下单、不接 broker、不改 strategy action。"
    }
  ];
  const ordinaryFactorTestProviderAcceptanceGateState =
    factorTestProviderSmallPoolAcceptance.status
      ? String(factorTestProviderSmallPoolAcceptance.status)
      : "acceptance gate 未记录；真实 provider task 仍需单独授权";
  const ordinaryFactorTestProviderNextGateItems: MetricItem[] = [
    {
      label: "当前可做",
      value: factorTestProviderSmallPoolExecutionRequest.local_execution_request_ready === true
        ? "只读复核 scope-bound execution request"
        : "先看本地 scope / execution request 是否齐备",
      tone: factorTestProviderSmallPoolExecutionRequest.local_execution_request_ready === true ? "good" : "warn"
    },
    {
      label: "验收门槛",
      value: ordinaryFactorTestProviderAcceptanceGateState,
      tone: factorTestProviderSmallPoolAcceptance.provider_execution_implemented === true ? "bad" : "warn"
    },
    {
      label: "真实 provider",
      value: "必须另行授权 provider-backed 小池任务；本页不自动提交",
      tone: "warn"
    },
    {
      label: "生产结论",
      value: factorTestProductionValidation.production_factor_test_validation_complete === true ? "complete" : "仍未完成",
      tone: factorTestProductionValidation.production_factor_test_validation_complete === true ? "good" : "warn"
    },
    {
      label: "交易隔离",
      value: "Factor 分数只做研究复核；不接 broker、不创建 order、不改 strategy action",
      tone: "good"
    }
  ];
  const ordinaryFactorTestProviderNextGateRows = [
    {
      闸门: "1. 本地 scope ticket",
      当前状态: factorTestProviderSmallPoolDryRun.preflight_ready_for_user_approved_real_task === true ? "ready：scope hash 可复核" : "check：scope ticket 不完整",
      用户下一步: "只读复核 dry-run scope、symbols、window、metrics 和 credential presence boolean。",
      证据: String(factorTestProviderSmallPoolDryRun.acceptance_scope_hash_short ?? factorTestProviderSmallPoolDryRun.acceptance_scope_hash ?? "missing_scope_hash"),
      边界: "本地 dry-run 只生成范围票据；不调用 Tushare、不采集样本、不计算生产 IC。"
    },
    {
      闸门: "2. 本地 execution request",
      当前状态: factorTestProviderSmallPoolExecutionRequest.local_execution_request_ready === true ? "ready：已绑定 latest scope" : "check：等待本地 execution request",
      用户下一步: "只读确认 request 是否绑定 latest scope；不要把它当 provider task。",
      证据: String(factorTestProviderSmallPoolExecutionRequest.status ?? "missing_execution_request"),
      边界: "execution request 不创建 provider task、不调用 provider/model/GitHub、不证明 provider-backed validation。"
    },
    {
      闸门: "3. acceptance gate",
      当前状态: ordinaryFactorTestProviderAcceptanceGateState,
      用户下一步: "只有在另行明确授权 provider-backed 小池任务后，才进入未来真实 provider 验收。",
      证据: String(factorTestProviderSmallPoolAcceptance.scope ?? "local_factor_test_provider_small_pool_acceptance_gate_no_provider_execution"),
      边界: "acceptance gate 是本地门槛记录；默认不授权 live provider、不采集样本、不生产 promotion。"
    },
    {
      闸门: "4. 真实证据包",
      当前状态: ordinaryFactorTestProviderEvidenceGap,
      用户下一步: "需要真实 task id、safe provider call_ledger、样本行、多周期/rolling/cost/neutralization/bias 和 promotion review。",
      证据: String(factorTestDurableEvidenceRecipe.status ?? "factor_test_durable_evidence_recipe_ready_production_pending"),
      边界: "durable recipe 只列缺口；不能把 local light、storage rows、QA rows 或 ticket 当生产验收。"
    },
    {
      闸门: "5. LTG-12 支撑边界",
      当前状态: "research client only",
      用户下一步: "只按研究证据复核支持/压制；不从 Factor 分数生成交易动作。",
      证据: "no broker / no order endpoint / no strategy action mutation",
      边界: "不真实交易、不下单、不接 broker、不创建 order endpoint。"
    }
  ];
  const ordinaryQuantCompactVerticalSliceItems: MetricItem[] = [
    {
      label: "确认链",
      value: candidateRadarLatestTaskId
        ? `已接上 ${candidateRadarConfirmedSymbol || "当前标的"}；task=${candidateRadarLatestTaskId}`
        : "等待下一票雷达确认；本页不接收股票输入",
      tone: candidateRadarLatestTaskId ? "good" : "warn"
    },
    {
      label: "P2/P3",
      value: ordinaryQuantP2P3ConnectionSentence,
      tone: ordinaryQuantP2P3ConnectionReady ? "good" : "warn"
    },
    {
      label: "支持/压制",
      value: ordinaryQuantResultComposition,
      tone: empty ? "warn" : "good"
    },
    {
      label: "小池验收",
      value: `${ordinaryFactorTestProviderSmallPoolState}；${ordinaryFactorTestProviderEvidenceGap}`,
      tone: factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "good" : "warn"
    },
    {
      label: "降级/缺口",
      value: `${ordinaryQuantDegradedSourceLabel}；${ordinaryQuantMissingEvidence}`,
      tone: ordinaryQuantDegradedSourceLabel.includes("未标记") && !ordinaryQuantMissingEvidence.includes("待") ? "good" : "warn"
    },
    {
      label: "边界",
      value: "因子结果只做研究复核；不创建 provider task、不交易、不改策略",
      tone: "good"
    }
  ];
  const ordinaryQuantPrimarySummaryItems: MetricItem[] = [
    { label: "下一步", value: ordinaryQuantNextClick },
    { label: "数据链", value: ordinaryQuantTushareFirstDataChainLabel },
    { label: "P2 三面回放", value: ordinaryQuantUpstreamP2WritebackLabel, tone: candidateRadarWritebackSurfaceRows.length ? "good" : "warn" },
    { label: "P3 可读结论", value: ordinaryQuantP3ReadableConclusion, tone: ordinaryQuantCandidateRadarP3Ready || !empty ? "good" : "warn" },
    { label: "P3 下一步", value: ordinaryQuantP3NextStep },
    { label: "解释状态", value: ordinaryQuantDeepSeekSourceLabel },
    { label: "仅供研究", value: "量化推演不是买卖指令；不真实交易、不下单、不改交易策略或操作区", tone: "good" }
  ];
  const ordinaryQuantPostConfirmOneMinuteSentence = ordinaryQuantResultRouteReady
    ? `${candidateRadarConfirmedSymbol || "当前标的"} 确认后一眼读图：先看支持/压制，再看完整次日图谱；缺口看 P2 三面和降级提示。`
    : "确认后一眼读图等待结果：先回下一票雷达确认代码；本页会显示支持/压制、图谱入口和缺口。";
  const ordinaryQuantPostConfirmOneMinuteItems: MetricItem[] = [
    {
      label: "当前标的",
      value: candidateRadarConfirmedSymbol || "等待下一票雷达确认",
      tone: candidateRadarConfirmedSymbol ? "good" : "warn"
    },
    {
      label: "一句话结论",
      value: ordinaryQuantP3ReadableConclusion,
      tone: ordinaryQuantResultRouteReady ? "good" : "warn"
    },
    {
      label: "先看",
      value: "支持/压制摘要",
      tone: ordinaryQuantResultRouteReady ? "good" : "warn"
    },
    {
      label: "再看",
      value: "完整次日图谱",
      tone: ordinaryQuantResultRouteReady ? "good" : "warn"
    },
    {
      label: "缺口",
      value: ordinaryQuantP3ExplainableGapLine,
      tone: ordinaryQuantP2ReadySurfaceCount === 3 && ordinaryQuantResultRouteReady ? "good" : "warn"
    },
    {
      label: "非交易边界",
      value: "支持/压制和图谱只供研究复核，不是买卖、加仓、减仓或融资指令",
      tone: "good"
    }
  ];
  const ordinaryQuantExpandedSummaryItems: MetricItem[] = [
    { label: "主下一步", value: ordinaryQuantPrimaryActionLabel },
    { label: "主下一步边界", value: ordinaryQuantPrimaryActionBoundary, tone: "good" },
    { label: "换标的入口", value: ordinaryQuantSymbolEntryBoundary, tone: "good" },
    { label: "运行模式", value: ordinaryQuantRuntimeModeLabel },
    { label: "本地缓存", value: ordinaryQuantCacheSourceLabel },
    { label: "待补证据", value: ordinaryQuantPendingStateLabel, tone: ordinaryQuantPendingStateLabel.includes("待补") || ordinaryQuantPendingStateLabel.includes("等待") ? "warn" : "good" },
    { label: "降级提示", value: ordinaryQuantDegradedSourceLabel, tone: ordinaryQuantDegradedSourceLabel.includes("未标记") ? "good" : "warn" },
    { label: "最近成功回放", value: ordinaryQuantLastCache },
    { label: "雷达搜票回放", value: ordinaryQuantRadarHandoffState, tone: empty ? "warn" : "good" },
    { label: "上游确认链", value: ordinaryQuantUpstreamOneScreenLabel, tone: candidateRadarOneScreenRows.length ? "good" : "warn" },
    { label: "确认结果链", value: ordinaryQuantUpstreamConfirmOutcomeLabel, tone: candidateRadarConfirmOutcomeRows.length ? "good" : "warn" },
    { label: "最近搜票结论", value: candidateRadarReadableResult, tone: candidateRadarInterpretation.interpretation_ready === true ? "good" : "warn" },
    { label: "回放位置", value: ordinaryQuantReplayLocation, tone: "good" },
    { label: "结果位置", value: ordinaryQuantResultLocation, tone: "good" },
    { label: "回放入口边界", value: ordinaryQuantRouteHandoffBoundary, tone: "good" },
    { label: "完整图谱入口", value: ordinaryQuantFullNextSessionHandoff, tone: "good" },
    { label: "完整图谱边界", value: ordinaryQuantFullNextSessionBoundary, tone: "good" },
    { label: "查看顺序", value: ordinaryQuantReviewOrder },
    { label: "结果组成", value: ordinaryQuantResultComposition },
    { label: "P3 边界", value: ordinaryQuantP3Boundary, tone: "good" },
    { label: "数据来源状态", value: ordinaryQuantSourceState },
    { label: "交接清单", value: ordinaryQuantHandoffLocation, tone: "good" },
    { label: "调用记录", value: ordinaryQuantLedgerSourceLabel, tone: ordinaryQuantLedgerSourceLabel.includes("等待") ? "warn" : "good" },
    { label: "结果包", value: ordinaryQuantPacketSourceLabel, tone: ordinaryQuantPacketSourceLabel.includes("等待") ? "warn" : "good" },
    { label: "P5 解释治理", value: ordinaryDeepSeekGovernedExecutorState, tone: deepseek.called === true ? "warn" : "good" },
    { label: "补证方式", value: ordinaryQuantEvidenceTaskState, tone: ordinaryQuantEvidenceTaskState.includes("等待") || ordinaryQuantEvidenceTaskState.includes("待补") || ordinaryQuantEvidenceTaskState.includes("未知") ? "warn" : "good" },
    { label: "缺少证据", value: ordinaryQuantMissingEvidence, tone: ordinaryQuantMissingEvidence.includes("待补") || ordinaryQuantMissingEvidence.includes("待确认") ? "warn" : "good" },
    { label: "阻断/降级", value: ordinaryQuantBlockedState, tone: ordinaryQuantBlockedState.includes("未标记") ? "good" : "warn" },
    { label: "最近可用缓存", value: ordinaryQuantLastCache },
    { label: "任务边界", value: ordinaryQuantTaskBoundary },
    { label: "结果边界", value: ordinaryQuantResultBoundary, tone: "good" }
  ];

  return (
    <PacketCard title="股票量化推演" subtitle="因子、次日图谱和模型解释状态一屏看清；只做研究预览，不修改交易动作" status={ordinaryQuantStatusLabel}>
      <PageStateBanner
        loading={loading}
        error={error}
        empty={empty}
        emptyTitle="暂无股票量化推演本地缓存"
        emptyDetail="本页只读取本地缓存；不会自动刷新外部数据。若需要更新，请手动点击任务按钮。"
      />
      <PacketCard title="普通用户量化推演摘要" subtitle="下一步、来源、缺口、边界和最近可用缓存" status={ordinaryQuantStatusLabel}>
        <div aria-label="stock quant ordinary user first summary">
          <div aria-label="stock quant ordinary plain conclusion">
            <h3>普通结论</h3>
            <p className="ordinary-status-note" aria-label="stock quant ordinary plain conclusion sentence" aria-live="polite">{ordinaryQuantPlainResultSentence}</p>
            <MetricGrid items={ordinaryQuantPlainConclusionItems} />
            <div className="actions" aria-label="stock quant ordinary plain conclusion actions">
              <a href={ordinaryQuantPrimaryActionHref} title="只切换本地页面或锚点；不会自动调用外部数据或模型服务" aria-label="open stock quant plain conclusion next action">{ordinaryQuantPrimaryActionLabel}</a>
            </div>
            <p className="risk-note">普通结论只读本地结果、数据凭证和次日图谱预览；页面打开、查看结果和切换入口都不会自动创建任务或调用外部服务。</p>
          </div>
          <h3>一屏速读</h3>
          <p className="risk-note">默认先看当前标的、结论、下一步、数据链、图谱/解释和边界；任务记录、数据凭证、合同和回放细节继续收起在下方。</p>
          <MetricGrid items={ordinaryQuantUserFirstItems} />
          <div aria-label="stock quant post confirm one minute read">
            <h3>确认后一眼读图</h3>
            <p className="ordinary-status-note" aria-label="stock quant post confirm one minute sentence" aria-live="polite">{ordinaryQuantPostConfirmOneMinuteSentence}</p>
            <MetricGrid items={ordinaryQuantPostConfirmOneMinuteItems} />
            <div className="actions" aria-label="stock quant post confirm one minute actions">
              <a href="#factor-score" title="跳到支持/压制摘要；只读 Factor cache" aria-label="open support suppress from stock quant one minute read">支持/压制</a>
              <a href={NEXT_SESSION_CHART_HREF} title="切换到完整次日图谱图表区域；只读本地次日图谱数据" aria-label="open next chart from stock quant one minute read">完整次日图谱</a>
              <a href={CANDIDATE_CONFIRM_HREF} title="回下一票雷达确认输入区；换标的仍需确认按钮" aria-label="open candidate confirm from stock quant one minute read">换一只票</a>
            </div>
            <p className="risk-note">这张一眼读图只读本地量化缓存、下一票雷达回放和次日图谱预览；本地链接只切换页面或锚点，不创建确认流程、不调用外部数据或模型、不交易、不改策略。</p>
          </div>
          <div aria-label="stock quant visible now app result">
            <h3>打开 app 能看到什么</h3>
            <p className="ordinary-status-note">这张速读只合成 Factor 页当前本地状态：可读结论、下一步入口、LTG-03 真实数据授权状态和授权后应产出的证据；它不创建 task、不调用 provider/model。</p>
            <MetricGrid items={ordinaryQuantVisibleNowItems} />
            <div className="actions" aria-label="stock quant visible now app result actions">
              <a href="#factor-score" title="跳到支持/压制摘要；只读 Factor cache" aria-label="open support suppress from stock quant visible now">支持/压制</a>
              <a href={NEXT_SESSION_CHART_HREF} title="切换到完整次日图谱；只读本地次日图谱数据" aria-label="open next chart from stock quant visible now">次日图谱</a>
              <a href={CANDIDATE_CONFIRM_HREF} title="回下一票雷达确认输入区；输入静默，确认按钮才创建任务" aria-label="open candidate confirm from stock quant visible now">确认或换一只票</a>
              <a href="#factor-provider-small-pool-gate" title="跳到 LTG-03 安全闸门；只读本地 scope 和 execution request" aria-label="open ltg03 provider gate from stock quant visible now">LTG-03 安全闸门</a>
            </div>
          </div>
          <div aria-label="stock quant compact vertical slice status">
            <h3>当前纵切状态</h3>
            <p className="ordinary-status-note">确认链、P2/P3、支持/压制、小池验收和缺口先给结论；需要真实 provider 小池时只显示授权边界，不自动创建任务。</p>
            <MetricGrid items={ordinaryQuantCompactVerticalSliceItems} />
          </div>
          <div aria-label="stock quant ordinary tushare data card">
            <h3>确认后 Tushare 数据卡</h3>
            <p className="ordinary-status-note" aria-label="stock quant ordinary tushare data card summary" aria-live="polite">{ordinaryQuantTushareDataCardSummary}</p>
            <MetricGrid items={ordinaryQuantTushareDataCardItems} />
            <div className="actions" aria-label="stock quant ordinary tushare data capability handoff actions">
              <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读查看 Tushare 可用、受限和待补原因" aria-label="open data capability from stock quant tushare data card">复核数据能力</a>
              <a href={CANDIDATE_CONFIRM_HREF} title="回下一票雷达确认输入区；输入静默，确认按钮才创建任务" aria-label="return candidate confirm from stock quant tushare data card">确认或换一只票</a>
            </div>
            <details className="developer-audit-details" aria-label="stock quant ordinary tushare data card rows">
              <summary>查看接口回放</summary>
              <p className="risk-note">这张明细只读 CandidateRadar 的 Tushare light 接口回放；没有账本时显示等待或阻断，不从 Factor 页补调数据。</p>
              <DataLineageTable rows={ordinaryQuantTushareDataCardRows} />
            </details>
            <p className="risk-note">数据卡只整理确认后已有的本地 cache / call_ledger / packet；不会调用 Tushare、DeepSeek、GitHub，不交易、不改交易策略。</p>
          </div>
          <div aria-label="stock quant provider validation ordinary quick read">
            <h3>真实验证速读</h3>
            <p className="ordinary-status-note" aria-label="stock quant provider validation quick read sentence" aria-live="polite">{ordinaryFactorTestProviderCurrentBlockerSentence}</p>
            <MetricGrid items={ordinaryFactorTestProviderQuickReadItems} />
          </div>
          <div aria-label="stock quant mode layered live light evidence boundary">
            <h3>运行模式分层</h3>
            <p className="ordinary-status-note">cache/render、按钮任务、真实数据、模型解释、生产验收和交易隔离分开显示；live_light 也只能是可审计 task，不是页面渲染外联。</p>
            <MetricGrid items={ordinaryQuantModeLayeredLiveLightItems} />
          </div>
          <div className="actions" aria-label="stock quant projection primary next action">
            <a href={ordinaryQuantPrimaryActionHref} aria-label="open stock quant primary next action">{ordinaryQuantPrimaryActionLabel}</a>
          </div>
        </div>
        <div aria-label="stock quant p3 one screen explanation">
          <h3>P3 一屏结论</h3>
          <MetricGrid items={ordinaryQuantP3OneScreenItems} />
          <p className="risk-note">优先读取 /api/factor-quant/cache 的 ordinary_quant_p3_one_screen_summary；只读本地 cache / CandidateRadar handoff，不创建 task、不调用 Tushare/DeepSeek、不交易、不改 strategy action。</p>
        </div>
        <div id="stock-quant-readable-result" aria-label="stock quant p3 explainable front result">
          <h3>P3 可解释结果</h3>
          <p className="ordinary-status-note" aria-label="stock quant p3 explainable front sentence" aria-live="polite">{ordinaryQuantP3ExplainableSentence}</p>
          <MetricGrid items={ordinaryQuantP3ExplainableFrontItems} />
          <div aria-label="stock quant result route strip">
            <h3>量化结果路标</h3>
            <p className="ordinary-status-note" aria-label="stock quant result route sentence" aria-live="polite">{ordinaryQuantResultRouteSentence}</p>
            <MetricGrid items={ordinaryQuantResultRouteItems} />
            <div className="actions" aria-label="stock quant result route actions">
              <a href="#factor-score" title="跳到支持/压制摘要；只读 Factor cache" aria-label="open support suppress from stock quant result route">支持/压制</a>
              <a href={NEXT_SESSION_CHART_HREF} title="切换到完整次日图谱图表区域；只读本地次日图谱数据" aria-label="open next chart from stock quant result route">完整次日图谱</a>
              <a href={CANDIDATE_CONFIRM_HREF} title="回下一票雷达确认输入区；换标的仍需确认按钮" aria-label="open candidate confirm from stock quant result route">换一只票</a>
            </div>
            <p className="risk-note">{ordinaryQuantResultRouteBoundary}</p>
          </div>
          <p className="risk-note">这张解释条只把结论、来源、缺口、下一步和次日图谱入口合成普通读法；不调用 DeepSeek、不生成买卖动作、不覆盖 operation_zones。</p>
        </div>
        <div aria-label="stock quant cross page replay handoff">
          <h3>跨页面同源回放</h3>
          <MetricGrid items={ordinaryQuantCrossPageReplayItems} />
          <p className="risk-note">这一条把下一票雷达、股票量化推演和次日图谱连成同一条本地回放线；只切换本地页面或锚点，不创建第二个 task。</p>
        </div>
        <div aria-label="stock quant p2 three surface front status">
          <h3>P2 三面状态</h3>
          <p className="ordinary-status-note" aria-label="stock quant p2 three surface front sentence" aria-live="polite">{ordinaryQuantP2ThreeSurfaceFrontSentence}</p>
          <MetricGrid items={ordinaryQuantP2ThreeSurfaceFrontItems} />
          <p className="risk-note">这张状态条只合成下一票雷达确认后的本地缓存、数据凭证和结果包三面；量化页只读回放，不创建第二个确认任务。</p>
        </div>
        <div aria-label="stock quant p2 p3 connection handoff">
          <h3>P2/P3 接通和下一步</h3>
          <p className="ordinary-status-note" aria-label="stock quant p2 p3 connection sentence" aria-live="polite">{ordinaryQuantP2P3ConnectionSentence}</p>
          <MetricGrid items={ordinaryQuantP2P3ConnectionItems} />
          <div className="actions" aria-label="stock quant p2 p3 connection actions">
            <a href={ordinaryQuantP2P3ConnectionPrimaryHref} title="只切换本地页面或锚点；不创建 task、不调用 Tushare/DeepSeek" aria-label="open stock quant p2 p3 primary action">{ordinaryQuantP2P3ConnectionPrimaryLabel}</a>
            <a href="#factor-score" title="跳到支持/压制摘要；只读 Factor cache" aria-label="open support suppress from stock quant p2 p3 handoff">支持/压制</a>
            <a href={NEXT_SESSION_CHART_HREF} title="切换到完整次日图谱；只读本地次日图谱数据" aria-label="open next session from stock quant p2 p3 handoff">次日图谱</a>
            <a href={CANDIDATE_CONFIRM_HREF} title="回下一票雷达确认输入区；输入仍静默" aria-label="open candidate confirm from stock quant p2 p3 handoff">确认或换一只票</a>
          </div>
          <p className="risk-note">这条行动条只把下一票雷达确认、P2 三面和 P3 可读结果在量化页串成同一条本地回放；缺口只提示待回放，不补调数据源或模型。</p>
        </div>
        <div aria-label="stock quant ordinary factor test provider small pool status">
          <h3>LTG-03 真实小池验收</h3>
          <p className="ordinary-status-note">普通页先说明真实小池验收是否已经运行、下一步是否需要授权、哪些证据仍缺；当前只读本地 cache 和历史 ticket，不从页面渲染或查看结果创建 provider 任务。</p>
          <p className="ordinary-status-note" aria-label="stock quant factor small pool degraded sentence" aria-live="polite">{ordinaryFactorTestProviderCurrentBlockerSentence}</p>
          <MetricGrid items={ordinaryFactorTestProviderSmallPoolItems} />
          <p className="risk-note">{ordinaryFactorTestProviderBoundary}；本地 light observations、本地 scope 或执行请求都不能当作生产级 Factor Test 验收完成。</p>
        </div>
        <div aria-label="stock quant ordinary factor small pool evidence checklist">
          <h3>小池样本证据怎么看</h3>
          <p className="ordinary-status-note" aria-label="stock quant factor small pool evidence sentence" aria-live="polite">{ordinaryFactorTestSmallPoolEvidenceSentence}</p>
          <MetricGrid items={ordinaryFactorTestSmallPoolEvidenceItems} />
          <div className="actions" aria-label="stock quant factor small pool evidence local actions">
            <a href="#factor-provider-small-pool-gate" title="跳到授权闸门；只读本地 scope / execution request" aria-label="open factor provider gate from small pool evidence">看授权闸门</a>
            <a href={DATA_CAPABILITY_HREF} title="切换到数据能力；只读查看数据和外联边界" aria-label="open data capability from small pool evidence">数据能力</a>
            <a href="#tasks" title="切换到任务目录；只读查看本地 task / receipt 状态" aria-label="open tasks from small pool evidence">任务目录</a>
            <a href="#factor-score" title="回到支持/压制摘要；只读 Factor cache" aria-label="open factor score from small pool evidence">支持/压制</a>
          </div>
          <details className="developer-audit-details" aria-label="stock quant factor small pool evidence rows">
            <summary>查看小池证据读法</summary>
            <p className="risk-note">这些行把样本、滚动、成本、中性化、偏差和推广复核拆成普通检查项；只读本地 cache，不创建 provider task、不调用 Tushare/DeepSeek/GitHub。</p>
            <DataLineageTable rows={ordinaryFactorTestSmallPoolEvidenceRows} />
          </details>
          <p className="risk-note">这张卡只帮助用户判断授权后要看什么；授权前不会提交 provider task，不会把 local ticket / dry-run / execution request 当作 production complete。</p>
        </div>
        <div id="factor-provider-small-pool-gate" aria-label="stock quant ordinary factor provider next gate">
          <h3>LTG-03 下一步安全闸门</h3>
          <p className="ordinary-status-note">先按这张闸门表确认：本地 scope、execution request 和 acceptance gate 都只是 future provider-backed 小池任务的前置证据；真实 provider 小池样本必须另行授权。</p>
          <MetricGrid items={ordinaryFactorTestProviderNextGateItems} />
          <DataLineageTable rows={ordinaryFactorTestProviderNextGateRows} />
          <div className="actions" aria-label="stock quant ordinary factor provider next gate actions">
            <a href="#tasks" title="切换到任务目录；只读查看本地 task / receipt 状态" aria-label="open task catalog from factor provider gate">任务目录</a>
            <a href="#audit" title="切换到调用审计；只读查看 call ledger 和外联边界" aria-label="open audit from factor provider gate">调用审计</a>
            <a href="#factor-score" title="回到支持/压制摘要；只读 Factor cache" aria-label="return factor score from provider gate">支持/压制</a>
          </div>
          <p className="risk-note">这张闸门只读 Factor cache 和本地 ticket；不触发小池预检、不创建 execution request、不提交 provider task、不调用 Tushare/DeepSeek/GitHub、不真实交易。</p>
        </div>
        <div aria-label="stock quant ordinary factor test production stage scope">
          <h3>LTG-03 生产阶段清单</h3>
          <p className="ordinary-status-note">普通页直接显示 factor_test_production_stage_scope_manifest：本地可见阶段、provider 直接证据和仍待补的生产阶段分开看；清单只读 cache，不创建 provider 任务。</p>
          <MetricGrid items={ordinaryFactorTestProductionStageItems} />
          <details className="developer-audit-details" aria-label="stock quant ordinary factor test production stage rows">
            <summary>LTG-03 生产阶段明细</summary>
            <p className="risk-note">这些行只展示 local surface 与 provider direct evidence 的缺口；不调用 Tushare/DeepSeek/GitHub、不计算生产 IC/Rank IC/ICIR、不进入 strategy action。</p>
            <DataLineageTable rows={factorTestProductionStageScopeRows} />
          </details>
        </div>
        <details className="developer-audit-details" aria-label="stock quant ordinary summary extra details">
          <summary>更多量化摘要字段</summary>
          <p className="risk-note">普通首屏只保留当前标的、结论、下一步、数据链、图谱/解释和安全边界；P1/P2/P3 完整字段、运行模式、回放位置、缺口和补证方式默认收起。</p>
          <MetricGrid items={ordinaryQuantPrimarySummaryItems} />
          <MetricGrid items={ordinaryQuantExpandedSummaryItems} />
        </details>
        <StateClarityRail
          label="stock quant ordinary result replay status"
          state={ordinaryQuantResultRailState}
          steps={ordinaryQuantResultRailSteps}
        />
        <p className="risk-note">普通结果状态：雷达确认 / Factor cache / 次日图谱 / DeepSeek 状态；这条状态轨只读本地 cache，不创建 task、不补调 Tushare 或 DeepSeek。</p>
        <span hidden aria-label="stock quant latest candidate readable result" />
        <details className="developer-audit-details" aria-label="stock quant latest candidate readable result demoted">
          <summary>最近搜票明细 / 旧结果回放</summary>
          <h3>最近搜票可读结论</h3>
          <p className="risk-note">普通路径先看上方 P3 可解释结果；这块保留旧结果回放、来源行和本地跳转，排查或复核时再展开。</p>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_result_quick_read_rows / ordinary_result_checkpoint_rows，旧 cache 再回退 search_quant_projection_interpretation_summary；确认后的 Tushare-first、P2 三面和 P3 结论在量化页首屏直接回放；本卡不创建 task、不补调数据源或模型。</p>
          <MetricGrid
            items={[
              { label: "标的", value: candidateRadarConfirmedSymbol || "--", tone: candidateRadarConfirmedSymbol ? "good" : "warn" },
              { label: "可读结论", value: candidateRadarReadableResult, tone: candidateRadarInterpretation.interpretation_ready === true ? "good" : "warn" },
              { label: "下一步", value: candidateRadarReadableNextStep },
              { label: "P2 小数据", value: String(candidateRadarSmallDataWriteback.small_data_writeback_ready === true ? "已回放" : "等待回放"), tone: candidateRadarSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn" },
              { label: "模型解释", value: candidateRadarOrdinaryDeepSeekState, tone: candidateRadarUsesModelOutput ? "warn" : "good" },
              { label: "边界", value: candidateRadarReadableBoundary, tone: "good" }
            ]}
          />
          <div className="actions" aria-label="stock quant readable result local actions">
            <a href="#factor-score" title="跳到本页支持/压制摘要；只读 Factor cache" aria-label="open factor support suppress from readable result">查看支持/压制</a>
            <a href={NEXT_SESSION_CHART_HREF} title="切换到完整次日图谱图表区域；只读本地次日图谱数据" aria-label="open full next session from readable result">打开完整次日图谱</a>
            <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需输入代码并确认" aria-label="return candidate radar confirm input from readable result">回下一票雷达确认</a>
          </div>
          <p className="risk-note">这组入口只切换本地页面或锚点；不创建 task、不调用 Tushare/DeepSeek/GitHub、不写 cache，也不改变 strategy action。</p>
          <details className="developer-audit-details" aria-label="stock quant readable result source rows">
            <summary>可读结论来源明细</summary>
            <p className="risk-note">这些来源行用于复核 CandidateRadar quick rows、checkpoint rows 和 Factor handoff；默认收起，避免普通阅读从工程表开始。</p>
            {candidateRadarResultQuickRows.length ? <DataLineageTable rows={candidateRadarResultQuickRows} /> : null}
            {candidateRadarResultCheckpointRows.length ? <DataLineageTable rows={candidateRadarResultCheckpointRows} /> : null}
            {factorPacketCandidateHandoffRows.length ? <DataLineageTable rows={factorPacketCandidateHandoffRows} /> : null}
          </details>
        </details>
        <details className="developer-audit-details" aria-label="stock quant ordinary task provenance details">
          <summary>任务来源和回放细节</summary>
          <p className="risk-note">task id、P1 确认、P2 三面、任务索引和后端回放合同默认收起；需要排查来源时再展开。本区仍只读 cache / ledger / packet，不创建 task、不补调 Tushare/DeepSeek。</p>
          <div aria-label="stock quant latest candidate post confirm checkpoint">
            <h3>确认后量化 checkpoint</h3>
            <p className="risk-note">最近一只票的 task id、P1 确认、P2 三面和 P3 可读结论在量化页可展开复核；本 checkpoint 只读 CandidateRadar cache / ledger / packet，不创建 task、不补调 Tushare/DeepSeek。</p>
            <MetricGrid items={ordinaryQuantLatestCandidateCheckpointItems} />
          </div>
          <div aria-label="stock quant local task index progress watch">
            <h3>本地任务进度</h3>
            <MetricGrid items={ordinaryQuantTaskIndexProgressItems} />
            <div className="actions" aria-label="stock quant local task index progress actions">
              <a href="#tasks" title="切换到任务目录；只读查看本地 task 进度" aria-label="open task catalog from stock quant progress watch">任务目录</a>
              <a href="#factor-score" title="跳到本页支持/压制摘要；只读 Factor cache" aria-label="open factor support suppress from stock quant progress watch">支持/压制</a>
              <a href={NEXT_SESSION_CHART_HREF} title="切换到完整次日图谱图表区域；只读本地次日图谱数据" aria-label="open next session from stock quant progress watch">次日图谱</a>
            </div>
            <p className="risk-note">边用边看：{ordinaryQuantProgressWatchNext}；这只来自 GET /api/tasks、Factor cache 和 CandidateRadar cache，不创建第二个 task、不补调 Tushare/DeepSeek、不真实交易。</p>
          </div>
          <div aria-label="stock quant p1 task source readback">
            <h3>P1 任务来源回放</h3>
            <p className="risk-note">这张小表只告诉普通用户 P3 结论来自哪次确认 task，以及确认回执和 task_readback 是否已经本地回放；详细回放合同继续收起。</p>
            <MetricGrid items={ordinaryQuantTaskSourceReadbackItems} />
          </div>
          <div aria-label="stock quant post confirm backend replay contract">
            <h3>后端回放合同</h3>
            <p className="risk-note">优先读取 CandidateRadar call_ledger safe params 里的 ordinary_post_confirm_replay_contract：量化页按同一条确认后合同回放任务、P2 三面和结果入口；本卡只读 cache / ledger / packet，不创建 task。</p>
            <DataLineageTable rows={ordinaryQuantPostConfirmReplayContractRows} />
          </div>
        </details>
        <details className="developer-audit-details" aria-label="stock quant ordinary expanded replay details">
          <summary>更多量化回放明细</summary>
          <p className="risk-note">普通主视图保留一屏速读、P3 可读结论和下一步入口；上游确认、P2 三面、三段解释、完整图谱交接和因子复核默认收起。</p>
          <div aria-label="stock quant ordinary upstream one screen actions">
            <h3>上游确认一屏行动</h3>
            <p className="risk-note">优先读取 CandidateRadar 的 ordinary_one_screen_action_rows：确认、任务、写回、结果合成量化页上游速读；本页只读回放，不创建 task、不调用模型。</p>
            <DataLineageTable rows={ordinaryQuantUpstreamOneScreenRows} />
          </div>
          <div aria-label="stock quant upstream confirm outcome readback">
            <h3>上游确认结果速读</h3>
            <p className="risk-note">优先读取 CandidateRadar 的 ordinary_confirm_outcome_rows：确认任务是否接收、P2 三面是否回放、P3 量化结果是否可读；本页只读回放，不创建第二个 task。</p>
            <DataLineageTable rows={ordinaryQuantUpstreamConfirmOutcomeRows} />
          </div>
          <div aria-label="stock quant upstream p2 writeback quick read">
            <h3>P2 小数据三面写回速读</h3>
            <p className="risk-note">优先读取 CandidateRadar 的 ordinary_writeback_surface_summary_rows：普通入口只看 cache、call_ledger、packet 三个写入面是否可回放；Factor 页只读回放，不创建 task、不补调 Tushare/DeepSeek。</p>
            <DataLineageTable rows={ordinaryQuantUpstreamP2WritebackRows} />
          </div>
          <div aria-label="stock quant ordinary cache ledger packet handoff">
            <h3>cache / ledger / packet 交接清单</h3>
            <p className="risk-note">确认按钮之后的轻量结果按 cache、ledger、packet、次日图谱预览回放；普通页只看交接状态，完整审计留在下方。</p>
            <DataLineageTable rows={ordinaryQuantHandoffRows} />
          </div>
          <div aria-label="stock quant ordinary explainable result replay">
            <h3>三段可解释结果</h3>
            <p className="risk-note">普通结果先按支持/压制、次日图谱预览、模型解释状态阅读；每段只回放本地 cache，不把解释变成交易动作。</p>
            <DataLineageTable rows={ordinaryQuantResultReplayRows} />
          </div>
          <div aria-label="stock quant ordinary full next session handoff">
            <h3>完整次日图谱交接</h3>
            <p className="ordinary-status-note">从本页打开完整次日图谱只切换 #next/next-session-chart 本地图表区域；先看本页预览，再去完整图谱复核路径、参考线、操作区和缺口边界。</p>
            <DataLineageTable rows={ordinaryQuantFullNextSessionRows} />
          </div>
          <div aria-label="stock quant ordinary factor review checklist">
            <h3>因子复核清单</h3>
            <p className="risk-note">按支持、压制、冲突、缺失四类复核；普通页只读本地 score cache，不重新排序、不补调 provider/model。</p>
            <DataLineageTable rows={ordinaryFactorReviewRows} />
          </div>
        </details>
        <details className="developer-audit-details" aria-label="stock quant ordinary p5 governance details">
          <summary>P5 解释治理单独补证状态</summary>
          <p className="risk-note">普通主线先复核 P3 支持/压制、次日图谱预览和缺失证据；DeepSeek governed executor 状态默认收起，只作为高级补证参考。</p>
          <div aria-label="stock quant p5 standalone governance status">
            <h3>P5 模型解释补证</h3>
            <p className="ordinary-status-note" aria-label="stock quant p5 standalone governance sentence" aria-live="polite">{ordinaryQuantP5StandaloneGovernanceSentence}</p>
            <MetricGrid items={ordinaryQuantP5StandaloneGovernanceItems} />
            <p className="risk-note">P5 只说明模型解释是否达到 governed executor 放行条件；普通投研主线仍先使用 P1/P2/P3 的本地回放结果。</p>
          </div>
          <div aria-label="stock quant ordinary deepseek governance">
            <h3>DeepSeek 单独治理状态</h3>
            <p className="risk-note">DeepSeek 解释单独补证；不阻塞 Tushare-first、支持/压制和次日图谱；普通页不展示 prompt/output。</p>
            <DataLineageTable rows={ordinaryDeepSeekGovernedExecutorRows} />
          </div>
        </details>
        <div className="actions" aria-label="stock quant projection source actions">
          <a href="#factor-score" title="跳到本页支持/压制摘要；只读 Factor cache" aria-label="view factor support suppress summary">查看支持/压制</a>
          <a href="#factor-next-session" title="跳到本页次日图谱预览；不刷新 provider/model" aria-label="view next session bridge preview">查看次日图谱预览</a>
          <a href={NEXT_SESSION_CHART_HREF} title="切换到完整次日图谱图表区域；只读本地次日图谱数据" aria-label="open full next session map from stock quant replay">打开完整次日图谱</a>
          <a href="#factor-deepseek" title="跳到本页模型解释状态；DeepSeek 仍等 governed executor" aria-label="view model explanation status">查看模型解释状态</a>
          <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；换标的仍需输入代码并确认" aria-label="return to candidate radar confirm input without creating a task">去下一票雷达确认生成</a>
        </div>
        <p className="risk-note">没有标的时先去 <a href={CANDIDATE_CONFIRM_HREF}>下一票雷达确认输入区</a> 输入代码并点击生成 3.0 量化推演；这个链接只切换本地页面，不创建 task。</p>
        <p className="risk-note">本页不接收股票代码输入；换标的必须回下一票雷达确认输入区，避免把查看缓存误当成重新推演。</p>
        <p className="risk-note">来自下一票雷达的搜票结果在本页只回放 Factor cache、次日图谱预览和模型解释状态；本页链接不重新触发 Tushare-first 或 DeepSeek。</p>
        <p className="risk-note">{ordinaryQuantResultLocation}</p>
        <p className="risk-note">{ordinaryQuantFullNextSessionBoundary}。</p>
        <p className="risk-note">生成后先按“支持/压制 → 次日图谱预览 → 模型解释状态”复核；缺数据就看 pending/缺少证据，不把空结果当成无风险。</p>
        <p className="risk-note">{ordinaryQuantRouteHandoffBoundary}。</p>
        <p className="risk-note">工程审计明细默认收起；完整 factor/provider/model ledger 和配置状态在 <a href="#audit">调用审计</a> / <a href="#settings">配置健康</a>。</p>
      </PacketCard>
      <div className="actions">
        <button onClick={refreshCache} title={ordinaryQuantCacheButtonLabel} aria-label={ordinaryQuantCacheButtonLabel}>查看本地缓存</button>
        <button onClick={() => launchTask("/api/factor-quant/refresh-data")} title={ordinaryQuantRefreshButtonLabel} aria-label={ordinaryQuantRefreshButtonLabel}>手动刷新数据</button>
        <button onClick={() => launchTask("/api/factor-quant/run-light", { auto_after_task: autoAfterTask })} title={ordinaryQuantRunLightButtonLabel} aria-label={ordinaryQuantRunLightButtonLabel}>运行轻量推演</button>
      </div>
      <p className="risk-note">普通路径只保留查看缓存、手动刷新和轻量推演；DeepSeek 解释入口下沉为高级开关，不阻塞 Tushare-first 和基础图谱。</p>
      <details className="developer-audit-details">
        <summary>模型解释 / 高级开关</summary>
        <p className="risk-note">DeepSeek governed executor 单独补；这里的按钮只走受控任务，不在页面渲染中调用模型，也不覆盖价格、因子、持仓、操作区或交易策略。</p>
        <p className="risk-note">模型解释默认手动触发；勾选自动整理后，轻量推演完成可继续整理解释。</p>
        <div className="actions">
          <label className="inline-toggle">
            <input
              type="checkbox"
              checked={autoAfterTask}
              onChange={(event) => setAutoAfterTask(event.target.checked)}
            />
            轻量推演完成后自动整理解释
          </label>
          <button onClick={() => launchTask("/api/factor-quant/deepseek-explain")}>整理模型解释</button>
        </div>
      </details>
      <details className="developer-audit-details">
        <summary>高级验收任务</summary>
        <div className="actions">
          <button onClick={() => launchTask("/api/factor-quant/universe-research-plan", { universe_mode: "full_pool" })}>生成读取计划</button>
          <button onClick={() => launchTask("/api/factor-quant/universe-worker-batch-dry-run", { approved_by_user: true, universe_mode: "full_pool" })}>批量研究预检</button>
          <button onClick={() => launchTask("/api/factor-quant/universe-worker-batch-execution-request", { approved_by_user: true, worker_batch_scope_hash: String(universeWorkerBatchDryRun.worker_batch_scope_hash ?? "") })}>批量执行请求</button>
          <button onClick={() => launchTask("/api/factor-quant/universe-worker-batch-research", { approved_by_user: true, worker_batch_scope_hash: String(universeWorkerBatchExecutionRequest.worker_batch_scope_hash ?? universeWorkerBatchDryRun.worker_batch_scope_hash ?? ""), execution_request_task_id: String(universeWorkerBatchExecutionRequest.task_id ?? "") })}>批量研究回执</button>
          <button onClick={() => launchTask("/api/factor-quant/provider-small-pool-dry-run", { approved_by_user: true, symbols: ["002008.SZ", "000001.SZ", "600000.SH", "600519.SH", "300750.SZ"], forward_return_horizons: ["1d", "5d"] })}>小池验收预检</button>
          <button onClick={() => launchTask("/api/factor-quant/provider-small-pool-execution-request", { approved_by_user: true, acceptance_scope_hash: String(factorTestProviderSmallPoolDryRun.acceptance_scope_hash ?? "") })}>小池执行请求</button>
          <button onClick={() => launchTask("/api/factor-quant/provider-small-pool-acceptance", { approved_by_user: true, acceptance_scope_hash: String(factorTestProviderSmallPoolExecutionRequest.acceptance_scope_hash ?? "") })}>真实小池验收门槛</button>
          <button onClick={() => launchTask("/api/factor-quant/deepseek-provider-benchmark-scope-ticket", { approved_by_user: true, sample_count: 40, response_format: "json_schema", max_retry_per_sample: 2 })}>DeepSeek benchmark 预检</button>
          <button onClick={() => launchTask("/api/factor-quant/deepseek-provider-benchmark-execution-request", { approved_by_user: true, benchmark_scope_hash: String(deepseekProviderBenchmarkScopeTicket.benchmark_scope_hash ?? "") })}>DeepSeek benchmark 执行请求</button>
        </div>
      </details>
      <p className="risk-note">多因子量化不是交易建议；不真实交易、不下单，不改价格、持仓、操作区或交易策略。</p>
      <details className="developer-audit-details">
        <summary>最近任务回执</summary>
        <TaskLaunchReceipt receipt={taskReceipt} />
        <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
      </details>
      <details className="developer-audit-details">
        <summary>开发 / 审计指标</summary>
        <p>Provider、model、receipt、runbook、QA blocker 和 LTG 细项默认收起；普通用户先看上方量化推演摘要、评分图表和支持/压制。</p>
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
          { label: "universe", value: universeResearch.current_universe_type ?? "current_target" },
          { label: "universe size", value: universeResearch.current_universe_size ?? 0 },
          { label: "full pool", value: universeResearch.full_pool_validation_done === true ? "完成" : "未完成", tone: universeResearch.full_pool_validation_done === true ? "good" : "neutral" },
          { label: "render scan", value: universeResearch.page_render_starts_full_pool === true ? "会启动" : "不启动", tone: universeResearch.page_render_starts_full_pool === true ? "bad" : "good" },
          { label: "frontend rank/zscore", value: universeResearch.frontend_computes_rank_zscore === true ? "会计算" : "不计算", tone: universeResearch.frontend_computes_rank_zscore === true ? "bad" : "good" },
          { label: "partial pool proof", value: universeExecutionReadiness.partial_pool_is_full_market_proof === true ? "误作全市场" : "不是全市场证明", tone: universeExecutionReadiness.partial_pool_is_full_market_proof === true ? "bad" : "good" },
          { label: "universe read plan", value: universeResearchTaskPlan.status ?? "missing", tone: universeResearchTaskPlan.status === "read_plan_ready" ? "good" : "neutral" },
          { label: "universe exec audit", value: universeExecutionReadiness.status ?? "missing", tone: universeExecutionReadiness.read_plan_ready === true ? "good" : "warn" },
          { label: "universe receipt", value: universeExecutionReadinessReceipt.status ?? "missing", tone: universeExecutionReadinessReceipt.ready_for_explicit_worker_batch_task === true ? "good" : "warn" },
          { label: "receipt worker ready", value: universeExecutionReadinessReceipt.ready_for_explicit_worker_batch_task === true ? "ready" : "blocked", tone: universeExecutionReadinessReceipt.ready_for_explicit_worker_batch_task === true ? "good" : "warn" },
          { label: "universe activation", value: universeExecutionActivationReceipt.status ?? "missing", tone: universeExecutionActivationReceipt.ready_for_explicit_worker_batch_task === true ? "good" : "warn" },
          { label: "worker-batch dry-run", value: universeWorkerBatchDryRun.status ?? "missing", tone: universeWorkerBatchDryRun.local_dry_run_ready === true ? "good" : "warn" },
          { label: "worker execution recipe", value: universeWorkerBatchExecutionRecipe.status ?? "missing", tone: universeWorkerBatchExecutionRecipe.local_recipe_ready === true ? "good" : "warn" },
          { label: "worker execution request", value: universeWorkerBatchExecutionRequest.status ?? "missing", tone: universeWorkerBatchExecutionRequest.local_execution_request_ready === true ? "good" : "warn" },
          { label: "worker recipe phases", value: universeWorkerBatchExecutionRecipe.pending_phase_count ?? 0, tone: Number(universeWorkerBatchExecutionRecipe.pending_phase_count ?? 0) > 0 ? "warn" : "neutral" },
          { label: "worker dry-run blockers", value: universeWorkerBatchDryRun.blocking_criterion_count ?? 0, tone: Number(universeWorkerBatchDryRun.blocking_criterion_count ?? 0) > 0 ? "warn" : "good" },
          { label: "activation blockers", value: universeExecutionActivationReceipt.production_blocker_count ?? 0, tone: Number(universeExecutionActivationReceipt.production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "universe blockers", value: universeExecutionReadiness.production_blocker_count ?? 0, tone: Number(universeExecutionReadiness.production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "worker plan", value: universeResearchTaskPlan.worker_task_consumption_plan_ready === true ? "ready" : "missing", tone: universeResearchTaskPlan.worker_task_consumption_plan_ready === true ? "good" : "neutral" },
          { label: "read plan datasets", value: universeResearchTaskPlan.dataset_count ?? 0 },
          { label: "plan full pool done", value: universeResearchTaskPlan.full_pool_validation_done === true ? "完成" : "未完成", tone: universeResearchTaskPlan.full_pool_validation_done === true ? "bad" : "good" },
          { label: "rank/zscore", value: universeExecutionReadiness.cross_sectional_rank_zscore_done === true ? "完成" : "未完成", tone: universeExecutionReadiness.cross_sectional_rank_zscore_done === true ? "good" : "warn" },
          { label: "rank/zscore dry-run", value: universeLocalRankZscore.status ?? "missing", tone: universeLocalRankZscore.rank_zscore_dry_run_executed === true ? "good" : "warn" },
          { label: "eligible groups", value: universeLocalRankZscore.eligible_group_count ?? 0, tone: Number(universeLocalRankZscore.eligible_group_count ?? 0) > 0 ? "good" : "warn" },
          { label: "rank preview rows", value: universeLocalRankZscore.rank_zscore_preview_row_count ?? 0, tone: Number(universeLocalRankZscore.rank_zscore_preview_row_count ?? 0) > 0 ? "good" : "neutral" },
          { label: "neutralization", value: universeExecutionReadiness.neutralization_done === true ? "完成" : "未完成", tone: universeExecutionReadiness.neutralization_done === true ? "good" : "warn" },
          { label: "universe production", value: universeExecutionReadiness.production_factor_universe_complete === true ? "完成" : "未完成", tone: universeExecutionReadiness.production_factor_universe_complete === true ? "good" : "warn" },
          { label: "score band", value: score.score_band ?? "missing" },
          { label: "factor tests", value: factorTests.status ?? "scaffold_missing", tone: factorTests.status === "scaffold_ready" ? "warn" : "neutral" },
          { label: "test rows", value: factorTestRows.length },
          { label: "test quality", value: factorTestQuality.status ?? "scaffold_only", tone: factorTestQuality.status === "computed_light_metrics_ready" ? "good" : "warn" },
          { label: "storage query", value: factorTestStorageQuery.status ?? "missing", tone: factorTestStorageQuery.external_calls_triggered === true ? "bad" : "neutral" },
          { label: "storage query rows", value: factorTestStorageQuery.returned_row_count ?? 0 },
          { label: "storage query metrics", value: factorTestStorageQuery.metrics_computed_from_storage_query === true ? "会计算" : "不计算", tone: factorTestStorageQuery.metrics_computed_from_storage_query === true ? "bad" : "good" },
          { label: "local dataset sample", value: factorTestLocalDataset.status ?? "missing", tone: factorTestLocalDataset.production_factor_test_validation_complete === true ? "bad" : "warn" },
          { label: "sample tickers", value: factorTestLocalDataset.unique_factor_ticker_count ?? 0, tone: Number(factorTestLocalDataset.unique_factor_ticker_count ?? 0) >= 5 ? "good" : "warn" },
          { label: "usable factor rows", value: factorTestLocalDataset.usable_factor_value_count ?? 0, tone: Number(factorTestLocalDataset.usable_factor_value_count ?? 0) >= 100 ? "good" : "warn" },
          { label: "dataset sample metrics", value: factorTestLocalDataset.metrics_computed_from_local_dataset === true ? "会计算" : "不计算", tone: factorTestLocalDataset.metrics_computed_from_local_dataset === true ? "bad" : "good" },
          { label: "small pool audit", value: factorTestSmallPool.status ?? "missing", tone: factorTestSmallPool.status === "local_small_pool_acceptance_ready" ? "good" : "warn" },
          { label: "local small pool", value: factorTestSmallPool.local_light_observation_acceptance_done === true ? "ready" : "pending", tone: factorTestSmallPool.local_light_observation_acceptance_done === true ? "good" : "warn" },
          { label: "real small pool", value: factorTestSmallPool.real_small_pool_validation_done === true ? "完成" : "未完成", tone: factorTestSmallPool.real_small_pool_validation_done === true ? "bad" : "good" },
          { label: "production QA", value: factorTestProductionValidation.status ?? "missing", tone: factorTestProductionValidation.production_factor_test_validation_complete === true ? "good" : "warn" },
          { label: "provider small pool", value: factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "完成" : "未完成", tone: factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "good" : "warn" },
          { label: "factor test production", value: factorTestProductionValidation.production_factor_test_validation_complete === true ? "完成" : "未完成", tone: factorTestProductionValidation.production_factor_test_validation_complete === true ? "good" : "warn" },
          { label: "provider blockers", value: factorTestProviderValidationBlocker.production_blocker_count ?? 0, tone: Number(factorTestProviderValidationBlocker.production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "provider validation", value: factorTestProviderValidationBlocker.provider_validation_ready === true ? "ready" : "blocked", tone: factorTestProviderValidationBlocker.provider_validation_ready === true ? "good" : "warn" },
          { label: "provider receipt", value: factorTestProviderSampleReadinessReceipt.status ?? "missing", tone: factorTestProviderSampleReadinessReceipt.ready_for_explicit_provider_small_pool_task === true ? "good" : "warn" },
          { label: "receipt blockers", value: factorTestProviderSampleReadinessReceipt.blocked_readiness_count ?? 0, tone: Number(factorTestProviderSampleReadinessReceipt.blocked_readiness_count ?? 0) > 0 ? "warn" : "good" },
          { label: "small-pool dry-run", value: factorTestProviderSmallPoolDryRun.status ?? "not_run", tone: factorTestProviderSmallPoolDryRun.preflight_ready_for_user_approved_real_task === true ? "good" : "warn" },
          { label: "small-pool recipe", value: factorTestProviderSmallPoolExecutionRecipe.status ?? "missing", tone: factorTestProviderSmallPoolExecutionRecipe.local_recipe_ready === true ? "good" : "warn" },
          { label: "recipe phases", value: factorTestProviderSmallPoolExecutionRecipe.pending_phase_count ?? 0, tone: Number(factorTestProviderSmallPoolExecutionRecipe.pending_phase_count ?? 0) > 0 ? "warn" : "neutral" },
          { label: "request ticket", value: factorTestProviderSmallPoolExecutionRequest.status ?? "missing", tone: factorTestProviderSmallPoolExecutionRequest.local_execution_request_ready === true ? "good" : "warn" },
          { label: "request blockers", value: factorTestProviderSmallPoolExecutionRequest.blocking_criterion_count ?? 0, tone: Number(factorTestProviderSmallPoolExecutionRequest.blocking_criterion_count ?? 0) > 0 ? "warn" : "good" },
          { label: "dry-run blockers", value: factorTestProviderSmallPoolDryRun.blocking_criterion_count ?? 0, tone: Number(factorTestProviderSmallPoolDryRun.blocking_criterion_count ?? 0) > 0 ? "warn" : "good" },
          { label: "research pass", value: factorTestQuality.research_pass_count ?? 0 },
          { label: "watchlist", value: factorTestQuality.watchlist_count ?? 0 },
          { label: "state contract", value: factorTestAcceptance.status ?? "missing", tone: factorTestAcceptance.all_result_states_are_research_only === false ? "bad" : "good" },
          { label: "research-pass signal", value: factorTestAcceptance.research_pass_is_not_trade_signal === false ? "可能交易" : "非交易", tone: factorTestAcceptance.research_pass_is_not_trade_signal === false ? "bad" : "good" },
          { label: "state rows", value: factorTestStateRows.length },
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
          { label: "DS mode", value: deepseekGovernance.mode ?? "manual_only", tone: deepseekGovernance.mode === "disabled" ? "bad" : "neutral" },
          { label: "DS auto_after_task", value: deepseekGovernance.auto_after_task === true ? "开启" : "关闭", tone: deepseekGovernance.auto_after_task === true ? "warn" : "good" },
          { label: "DS configured auto", value: deepseekGovernance.configured_auto_after_task === true ? "开启" : "关闭", tone: deepseekGovernance.configured_auto_after_task === true ? "warn" : "good" },
          { label: "DS model", value: deepseek.model_used ?? "not_called" },
          { label: "DS parse_failed", value: deepseek.parse_failed === true ? "是" : "否", tone: deepseek.parse_failed === true ? "bad" : "good" },
          { label: "DS validation", value: deepseekValidation.validation_mode ?? "local_sanitizer_only" },
          { label: "DS model call", value: deepseekValidation.model_call_status ?? "not_called", tone: deepseekValidation.model_call_status === "not_called" ? "good" : "warn" },
          { label: "DS invalid discarded", value: deepseekValidation.invalid_output_discarded === true ? "是" : "否", tone: deepseekValidation.invalid_output_discarded === true ? "warn" : "good" },
          { label: "DS token estimate", value: deepseek.token_estimate ?? 0 },
          { label: "DS JSON audit", value: deepseekJsonStability.status ?? "missing", tone: deepseekJsonStability.production_ready === true ? "good" : "warn" },
          { label: "DS JSON target", value: deepseekJsonStability.required_json_success_rate ?? 0.9 },
          { label: "DS JSON last", value: deepseekJsonStability.last_known_mini_benchmark_success_rate ?? 0.75, tone: deepseekJsonStability.production_ready === true ? "good" : "warn" },
          { label: "DS benchmark", value: deepseekJsonStability.larger_benchmark_done === true ? "完成" : "未完成", tone: deepseekJsonStability.larger_benchmark_done === true ? "good" : "warn" },
          { label: "DS response_format", value: deepseekJsonStability.response_format_enforced === true ? "强约束" : "未强约束", tone: deepseekJsonStability.response_format_enforced === true ? "good" : "warn" },
          { label: "DS retry dry-run", value: deepseekRetryRepairDryRun.status ?? "missing", tone: deepseekRetryRepairDryRun.local_retry_repair_dry_run_ready === true ? "good" : "warn" },
          { label: "DS retry production", value: deepseekRetryRepairDryRun.bounded_retry_repair_ready === true ? "ready" : "blocked", tone: deepseekRetryRepairDryRun.bounded_retry_repair_ready === true ? "good" : "warn" },
          { label: "DS auto ready", value: deepseekJsonStability.auto_after_task_production_ready === true ? "ready" : "blocked", tone: deepseekJsonStability.auto_after_task_production_ready === true ? "good" : "warn" },
          { label: "DS activation", value: deepseekProductionActivationReceipt.status ?? "missing", tone: deepseekProductionActivationReceipt.local_activation_receipt_ready === true ? "good" : "warn" },
          { label: "DS provider benchmark", value: deepseekProductionActivationReceipt.provider_benchmark_done === true ? "完成" : "未完成", tone: deepseekProductionActivationReceipt.provider_benchmark_done === true ? "good" : "warn" },
          { label: "DS scope ticket", value: deepseekProviderBenchmarkScopeTicket.status ?? "missing", tone: deepseekProviderBenchmarkScopeTicket.local_scope_ticket_ready === true ? "good" : "warn" },
          { label: "DS scope hash", value: deepseekProviderBenchmarkScopeTicket.benchmark_scope_hash_short ?? "missing", tone: deepseekProviderBenchmarkScopeTicket.benchmark_scope_hash_short ? "good" : "neutral" },
          { label: "DS activation blockers", value: deepseekProductionActivationReceipt.blocking_criterion_count ?? 0, tone: Number(deepseekProductionActivationReceipt.blocking_criterion_count ?? 0) > 0 ? "warn" : "good" },
          { label: "DS durable evidence", value: deepseekDurableEvidenceRecipe.status ?? "missing", tone: deepseekDurableEvidenceRecipe.local_recipe_ready === true ? "good" : "warn" },
          { label: "DS durable blockers", value: deepseekDurableEvidenceRecipe.durable_evidence_blocker_count ?? 0, tone: Number(deepseekDurableEvidenceRecipe.durable_evidence_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "snapshot", value: packet.source_snapshot_available === true, tone: packet.source_snapshot_available === true ? "good" : "warn" },
          { label: "Tushare failure QA", value: tushareFailureModeQa.status ?? "missing", tone: tushareFailureModeQa.status === "failure_mode_qa_blocked" ? "bad" : "warn" },
          { label: "failure modes", value: tushareFailureModeQa.observed_mode_count ?? 0 },
          { label: "failure unsafe rows", value: tushareFailureModeQa.unsafe_row_count ?? 0, tone: Number(tushareFailureModeQa.unsafe_row_count ?? 0) > 0 ? "bad" : "good" },
          { label: "Tushare param QA", value: tushareRequestParameterQa.status ?? "missing", tone: tushareRequestParameterQa.status === "request_parameter_qa_blocked" ? "bad" : "warn" },
          { label: "missing params", value: tushareRequestParameterQa.missing_required_preflight_api_count ?? 0, tone: Number(tushareRequestParameterQa.missing_required_preflight_api_count ?? 0) > 0 ? "warn" : "good" },
          { label: "param unsafe rows", value: tushareRequestParameterQa.unsafe_request_param_api_count ?? 0, tone: Number(tushareRequestParameterQa.unsafe_request_param_api_count ?? 0) > 0 ? "bad" : "good" },
          { label: "Tushare sample plan", value: tushareProviderTargetSamplePlan.status ?? "missing", tone: tushareProviderTargetSamplePlan.provider_backed_acceptance_done === true ? "good" : "warn" },
          { label: "sample plan ready", value: tushareProviderTargetSamplePlan.ready_to_execute_target_count ?? 0, tone: Number(tushareProviderTargetSamplePlan.ready_to_execute_target_count ?? 0) > 0 ? "warn" : "neutral" },
          { label: "sample plan pending", value: tushareProviderTargetSamplePlan.pending_or_blocked_target_count ?? 0, tone: Number(tushareProviderTargetSamplePlan.pending_or_blocked_target_count ?? 0) > 0 ? "warn" : "good" },
          { label: "Tushare promotion", value: tushareProviderPromotionAudit.status ?? "missing", tone: tushareProviderPromotionAudit.promotion_ready === true ? "good" : "warn" },
          { label: "promotion blockers", value: tushareProviderPromotionAudit.blocking_criterion_count ?? 0, tone: Number(tushareProviderPromotionAudit.blocking_criterion_count ?? 0) > 0 ? "warn" : "good" },
          { label: "provider evidence rows", value: tushareProviderPromotionAudit.provider_evidence_row_count ?? 0, tone: Number(tushareProviderPromotionAudit.provider_evidence_row_count ?? 0) > 0 ? "warn" : "neutral" },
          { label: "sample receipt", value: tushareProviderSampleReadinessReceipt.status ?? "missing", tone: tushareProviderSampleReadinessReceipt.ready_for_explicit_provider_sample_task === true ? "good" : "warn" },
          { label: "sample receipt blockers", value: tushareProviderSampleReadinessReceipt.blocked_readiness_count ?? 0, tone: Number(tushareProviderSampleReadinessReceipt.blocked_readiness_count ?? 0) > 0 ? "warn" : "good" }
          ]}
        />
      </details>
      <section id="factor-score" aria-label="factor support suppress summary">
        <EChartPanel option={option} />
        <ChartSafetyStrip
          contract={scoreChartContract}
          source={scoreChart.source_packet ?? "factor_quant_cache"}
          extraItems={[
            { label: "改因子分数", value: scoreChartContract.does_not_modify_factor_score === false ? "可能" : "不会" }
          ]}
        />
      </section>
      <details className="developer-audit-details">
        <summary>评分图表 lineage 审计</summary>
        <h3>评分图表数据合同</h3>
        <DataLineageTable rows={scoreChartContractRows} />
        <h3>评分图表 buckets</h3>
        <DataLineageTable rows={scoreChartRows} />
      </details>
      <div className="grid compact-grid">
        <PacketCard title="支持 / 压制" subtitle="只用于研究预览">
          <p>支持因子：{String(score.support_factors?.length ?? 0)} 个</p>
          <p>压制因子：{String(score.suppress_factors?.length ?? 0)} 个</p>
          <p>冲突因子：{String(score.conflict_factors?.length ?? 0)} 个</p>
        </PacketCard>
        <PacketCard title="本地上下文" subtitle="只读本地缓存，不触发外联">
          <p>策略上下文：{Boolean(linkedPackets.strategy_execution_packet) ? "已连接" : "未连接"}</p>
          <p>决策上下文：{Boolean(linkedPackets.decision_packet) ? "已连接" : "未连接"}</p>
          <p>旧版量化缓存：{Boolean(linkedPackets.legacy_quant_packet) ? "已连接" : "未连接"}</p>
        </PacketCard>
      </div>
      <section id="factor-next-session" aria-label="next session bridge preview">
        <h3>次日图谱预览</h3>
        <p>桥接状态：{String(bridge.status ?? bridge.bridge_status ?? "等待本地缓存")}</p>
        <p>动作边界：{bridge.does_not_modify_action === false ? "边界异常：需要审计" : "只读条件预览，不修改交易动作"}</p>
        <p>最近可用结果：{ordinaryQuantLastCache}</p>
      </section>
      <PacketCard title="DeepSeek 解释" subtitle="按钮触发；只整理已有结构化结果，不覆盖数值">
        <section id="factor-deepseek" aria-label="model explanation status">
        <p>解释状态：{Boolean(deepseek.called) ? "已有本地解释" : "未生成或等待手动任务"}</p>
        <p>触发方式：{String(deepseekGovernance.mode ?? "manual_only") === "disabled" ? "关闭" : String(deepseekGovernance.mode ?? "manual_only") === "manual_only" ? "手动按钮" : "按当前运行模式"}</p>
        <p>自动整理解释：{deepseekGovernance.auto_after_task === true ? "开启" : "关闭"}</p>
        <p>缓存读取：{deepseekGovernance.cache_reads_never_call_deepseek === false || deepseekGovernance.react_render_never_calls_deepseek === false ? "边界异常：缓存或页面渲染可能调用模型" : "只读本地缓存，不调用模型"}</p>
        <p>输出边界：{deepseek.parse_failed === true ? "解析失败，结果只留审计" : "只整理文字说明，不改数值或交易动作"}</p>
        <p>可整理内容：摘要、支持/压制、冲突、缺失数据、纪律提示</p>
        </section>
      </PacketCard>
      <details className="developer-audit-details">
        <summary>DeepSeek 解释治理审计</summary>
      <h3>DeepSeek 原始解释审计</h3>
        <p>called: {String(Boolean(deepseek.called))}</p>
        <p>mode: {String(deepseekGovernance.mode ?? "manual_only")}</p>
        <p>auto_after_task: {String(deepseekGovernance.auto_after_task ?? false)}</p>
        <p>cache_reads_never_call_deepseek: {String(deepseekGovernance.cache_reads_never_call_deepseek ?? true)}</p>
        <p>react_render_never_calls_deepseek: {String(deepseekGovernance.react_render_never_calls_deepseek ?? true)}</p>
        <p>status: {String(deepseek.status ?? "not_called")}</p>
        <p>model_used: {String(deepseek.model_used ?? "not_called")}</p>
        <p>input_hash: {String(deepseek.input_hash ?? "")}</p>
        <p>output_hash: {String(deepseek.output_hash ?? "")}</p>
        <p>cache_key: {JSON.stringify(packet.deepseek_explanation_cache_key ?? {})}</p>
        <p>parse_failed: {String(deepseek.parse_failed ?? false)}</p>
        <p>token_estimate: {String(deepseek.token_estimate ?? 0)}</p>
        <p>validation_mode: {String(deepseekValidation.validation_mode ?? "local_sanitizer_only")}</p>
        <p>model_call_status: {String(deepseekValidation.model_call_status ?? "not_called")}</p>
        <p>invalid_output_discarded: {String(deepseekValidation.invalid_output_discarded ?? false)}</p>
        <p>allowed: summary / support_notes / suppress_notes / conflict_notes / missing_data_notes / discipline_notes</p>
      <h3>DeepSeek 解释校验</h3>
      <DataLineageTable rows={deepseekValidationRows} />
      <PacketCard title="DeepSeek JSON 稳定性审计" subtitle="本地 sanitizer/prompt 合同；不调用模型">
        <p>status: {String(deepseekJsonStability.status ?? "missing")}</p>
        <p>scope: {String(deepseekJsonStability.scope ?? "local_sanitizer_prompt_contract_not_model_call")}</p>
        <p>required_json_success_rate: {String(deepseekJsonStability.required_json_success_rate ?? 0.9)}</p>
        <p>last_known_mini_benchmark_success_rate: {String(deepseekJsonStability.last_known_mini_benchmark_success_rate ?? 0.75)}</p>
        <p>larger_benchmark_done: {String(deepseekJsonStability.larger_benchmark_done ?? false)}</p>
        <p>response_format_enforced: {String(deepseekJsonStability.response_format_enforced ?? false)}</p>
        <p>auto_after_task_production_ready: {String(deepseekJsonStability.auto_after_task_production_ready ?? false)}</p>
        <p>model_call_status: {String(deepseekJsonStability.model_call_status ?? "not_called")}</p>
      </PacketCard>
      <h3>DeepSeek JSON 稳定性审计明细</h3>
      <DataLineageTable rows={deepseekJsonStabilityRows} />
      <PacketCard title="DeepSeek response format review" subtitle="本地 response-format / retry-repair 合同；不调用模型、不把 sanitizer 当生产验收">
        <p>status: {String(deepseekResponseFormatReview.status ?? "missing")}</p>
        <p>scope: {String(deepseekResponseFormatReview.scope ?? "local_response_format_review_no_model_call")}</p>
        <p>review_policy: {String(deepseekResponseFormatReview.review_policy ?? "manual_explanation_only_until_response_format_retry_and_benchmark_pass")}</p>
        <p>provider_response_format_enforced: {String(deepseekResponseFormatReview.provider_response_format_enforced ?? false)}</p>
        <p>retry_repair_policy_ready: {String(deepseekResponseFormatReview.retry_repair_policy_ready ?? false)}</p>
        <p>production_ready: {String(deepseekResponseFormatReview.production_ready ?? false)}</p>
        <p>model_call_status: {String(deepseekResponseFormatReview.model_call_status ?? "not_called")}</p>
        <p>allowed_top_level_keys: {JSON.stringify(deepseekResponseFormatReview.allowed_top_level_keys ?? ["summary", "support_notes", "suppress_notes", "conflict_notes", "missing_data_notes", "discipline_notes"])}</p>
      </PacketCard>
      <h3>DeepSeek response format review rows</h3>
      <DataLineageTable rows={deepseekResponseFormatReviewRows} />
      <PacketCard title="DeepSeek retry/repair dry-run" subtitle="本地 JSON 提取/修复样本；不调用模型，不证明 provider retry/repair">
        <p>status: {String(deepseekRetryRepairDryRun.status ?? "missing")}</p>
        <p>scope: {String(deepseekRetryRepairDryRun.scope ?? "local_retry_repair_dry_run_no_model_call")}</p>
        <p>local_retry_repair_dry_run_ready: {String(deepseekRetryRepairDryRun.local_retry_repair_dry_run_ready ?? false)}</p>
        <p>case_count / passed_case_count: {String(deepseekRetryRepairDryRun.case_count ?? 0)} / {String(deepseekRetryRepairDryRun.passed_case_count ?? 0)}</p>
        <p>parse_failed_case_count: {String(deepseekRetryRepairDryRun.parse_failed_case_count ?? 0)}</p>
        <p>bounded_retry_repair_ready: {String(deepseekRetryRepairDryRun.bounded_retry_repair_ready ?? false)}</p>
        <p>provider_retry_repair_executed: {String(deepseekRetryRepairDryRun.provider_retry_repair_executed ?? false)}</p>
        <p>production_deepseek_explanation_complete: {String(deepseekRetryRepairDryRun.production_deepseek_explanation_complete ?? false)}</p>
        <p className="risk-note">local retry/repair dry-run 只验证 fenced JSON、embedded JSON、非法字段清洗和 parse_failed discard；provider response_format、真实 retry/repair、benchmark 和 cost evidence 仍未完成。</p>
      </PacketCard>
      <h3>DeepSeek retry/repair dry-run rows</h3>
      <DataLineageTable rows={deepseekRetryRepairDryRunRows} />
      <PacketCard title="DeepSeek production activation receipt" subtitle="下一步生产解释验收收据；不调用模型、不把 sanitizer 当 provider benchmark">
        <p>status: {String(deepseekProductionActivationReceipt.status ?? "missing")}</p>
        <p>local_activation_receipt_ready: {String(deepseekProductionActivationReceipt.local_activation_receipt_ready ?? false)}</p>
        <p>allowed_next_step: {String(deepseekProductionActivationReceipt.allowed_next_step ?? "explicit_provider_benchmark_then_response_format_enforcement_retry_repair_cost_review")}</p>
        <p>provider_benchmark_done: {String(deepseekProductionActivationReceipt.provider_benchmark_done ?? false)}</p>
        <p>provider_response_format_enforced: {String(deepseekProductionActivationReceipt.provider_response_format_enforced ?? false)}</p>
        <p>bounded_retry_repair_ready: {String(deepseekProductionActivationReceipt.bounded_retry_repair_ready ?? false)}</p>
        <p>token_budget_cost_evidence_complete: {String(deepseekProductionActivationReceipt.token_budget_cost_evidence_complete ?? false)}</p>
        <p>auto_after_task_production_ready: {String(deepseekProductionActivationReceipt.auto_after_task_production_ready ?? false)}</p>
        <p>production_deepseek_explanation_complete: {String(deepseekProductionActivationReceipt.production_deepseek_explanation_complete ?? false)}</p>
        <p>provider_model_called_by_receipt: {String(deepseekProductionActivationReceipt.provider_model_called_by_receipt ?? false)}</p>
      </PacketCard>
      <h3>DeepSeek production activation rows</h3>
      <p className="risk-note">activation receipt 只允许后续显式 provider benchmark、response_format 强约束、retry/repair 和 cost review；GET cache 和页面渲染仍不调用 DeepSeek，不覆盖数值或 action。</p>
      <DataLineageTable rows={deepseekProductionActivationRows} />
      <DataLineageTable rows={deepseekProductionActivationReceiptRows} />
      <PacketCard title="DeepSeek provider benchmark scope ticket" subtitle="显式 POST 预检票据；不调用模型、不证明 provider benchmark">
        <p>status: {String(deepseekProviderBenchmarkScopeTicket.status ?? "missing")}</p>
        <p>local_scope_ticket_ready / ready_for_explicit_provider_benchmark_task: {String(deepseekProviderBenchmarkScopeTicket.local_scope_ticket_ready ?? false)} / {String(deepseekProviderBenchmarkScopeTicket.ready_for_explicit_provider_benchmark_task ?? false)}</p>
        <p>benchmark_scope_hash_short: {String(deepseekProviderBenchmarkScopeTicket.benchmark_scope_hash_short ?? "")}</p>
        <p>requested_sample_count / required_sample_count: {String(deepseekProviderBenchmarkScopeTicket.requested_sample_count ?? 0)} / {String(deepseekProviderBenchmarkScopeTicket.required_sample_count ?? 40)}</p>
        <p>response_format / max_retry_per_sample: {String(deepseekProviderBenchmarkScopeTicket.response_format ?? "json_schema")} / {String(deepseekProviderBenchmarkScopeTicket.max_retry_per_sample ?? 2)}</p>
        <p>server_secret_present / credential_values_exposed / env_key_names_exposed: {String(deepseekProviderBenchmarkScopeTicket.server_secret_present ?? false)} / {String(deepseekProviderBenchmarkScopeTicket.credential_values_exposed ?? false)} / {String(deepseekProviderBenchmarkScopeTicket.env_key_names_exposed ?? false)}</p>
        <p>provider_benchmark_done / production_deepseek_explanation_complete: {String(deepseekProviderBenchmarkScopeTicket.provider_benchmark_done ?? false)} / {String(deepseekProviderBenchmarkScopeTicket.production_deepseek_explanation_complete ?? false)}</p>
        <p>model_call_status / deepseek_called: {String(deepseekProviderBenchmarkScopeTicket.model_call_status ?? "not_called")} / {String(deepseekProviderBenchmarkScopeTicket.deepseek_called ?? false)}</p>
        <p>not_allowed_next_steps: {Array.isArray(deepseekProviderBenchmarkScopeTicket.not_allowed_next_steps) ? deepseekProviderBenchmarkScopeTicket.not_allowed_next_steps.join(" / ") : "scope ticket as provider benchmark evidence / call DeepSeek from scope ticket / auto_after_task promotion from scope ticket"}</p>
      </PacketCard>
      <h3>DeepSeek provider benchmark scope rows</h3>
      <DataLineageTable rows={deepseekProviderBenchmarkScopeRows} />
      <DataLineageTable rows={deepseekProviderBenchmarkScopeReceiptRows} />
      <PacketCard title="DeepSeek provider benchmark execution request" subtitle="显式 POST 执行请求票据；不调用模型、不创建 model task、不证明 provider benchmark">
        <p>status: {String(deepseekProviderBenchmarkExecutionRequest.status ?? "missing")}</p>
        <p>local_execution_request_ready / ready_for_manual_model_task_submission: {String(deepseekProviderBenchmarkExecutionRequest.local_execution_request_ready ?? false)} / {String(deepseekProviderBenchmarkExecutionRequest.ready_for_manual_model_task_submission ?? false)}</p>
        <p>benchmark_scope_hash_short: {String(deepseekProviderBenchmarkExecutionRequest.benchmark_scope_hash_short ?? "")}</p>
        <p>requested_scope_hash_matches_latest: {String(deepseekProviderBenchmarkExecutionRequest.requested_scope_hash_matches_latest ?? false)}</p>
        <p>model_task_created / model_execution_implemented / provider_benchmark_done: {String(deepseekProviderBenchmarkExecutionRequest.model_task_created ?? false)} / {String(deepseekProviderBenchmarkExecutionRequest.model_execution_implemented ?? false)} / {String(deepseekProviderBenchmarkExecutionRequest.provider_benchmark_done ?? false)}</p>
        <p>deepseek_called / external_calls_triggered: {String(deepseekProviderBenchmarkExecutionRequest.deepseek_called ?? false)} / {String(deepseekProviderBenchmarkExecutionRequest.external_calls_triggered ?? false)}</p>
        <p>not_allowed_next_steps: {Array.isArray(deepseekProviderBenchmarkExecutionRequest.not_allowed_next_steps) ? deepseekProviderBenchmarkExecutionRequest.not_allowed_next_steps.join(" / ") : "treat execution request as provider benchmark / call DeepSeek from execution request / production completion from execution request"}</p>
      </PacketCard>
      <h3>DeepSeek provider benchmark execution request rows</h3>
      <DataLineageTable rows={deepseekProviderBenchmarkExecutionRequestRows} />
      <DataLineageTable rows={deepseekProviderBenchmarkExecutionRequestReceiptRows} />
      <PacketCard title="DeepSeek durable evidence recipe" subtitle="LTG-07 durable evidence 缺口清单；只读、不调用模型、不把 recipe 当 benchmark">
        <p>schema_version: {String(deepseekDurableEvidenceRecipe.schema_version ?? "factor_deepseek_durable_evidence_recipe.v1")}</p>
        <p>status: {String(deepseekDurableEvidenceRecipe.status ?? "missing")}</p>
        <p>scope: {String(deepseekDurableEvidenceRecipe.scope ?? "local_deepseek_durable_evidence_recipe_no_model_call")}</p>
        <p>local_recipe_ready / durable_evidence_complete: {String(deepseekDurableEvidenceRecipe.local_recipe_ready ?? false)} / {String(deepseekDurableEvidenceRecipe.durable_evidence_complete ?? false)}</p>
        <p>provider_benchmark_done / provider_response_format_enforced: {String(deepseekDurableEvidenceRecipe.provider_benchmark_done ?? false)} / {String(deepseekDurableEvidenceRecipe.provider_response_format_enforced ?? false)}</p>
        <p>bounded_retry_repair_executed / token_budget_cost_evidence_complete: {String(deepseekDurableEvidenceRecipe.bounded_retry_repair_executed ?? false)} / {String(deepseekDurableEvidenceRecipe.token_budget_cost_evidence_complete ?? false)}</p>
        <p>auto_after_task_production_ready / production_deepseek_explanation_complete: {String(deepseekDurableEvidenceRecipe.auto_after_task_production_ready ?? false)} / {String(deepseekDurableEvidenceRecipe.production_deepseek_explanation_complete ?? false)}</p>
        <p>provider_model_called_by_recipe / cache_get_external_calls: {String(deepseekDurableEvidenceRecipe.provider_model_called_by_recipe ?? false)} / {String(deepseekDurableEvidenceRecipe.cache_get_external_calls ?? false)}</p>
        <p>tushare / deepseek / github: {String(deepseekDurableEvidenceRecipe.tushare_called ?? false)} / {String(deepseekDurableEvidenceRecipe.deepseek_called ?? false)} / {String(deepseekDurableEvidenceRecipe.github_called ?? false)}</p>
        <p>missing_durable_evidence: {Array.isArray(deepseekDurableEvidenceRecipe.missing_durable_evidence) ? deepseekDurableEvidenceRecipe.missing_durable_evidence.join(" / ") : ""}</p>
        <p>not_allowed_next_steps: {Array.isArray(deepseekDurableEvidenceRecipe.not_allowed_next_steps) ? deepseekDurableEvidenceRecipe.not_allowed_next_steps.join(" / ") : "treat_durable_recipe_as_provider_benchmark / call DeepSeek from GET cache / durable recipe as production completion"}</p>
      </PacketCard>
      <h3>DeepSeek durable evidence rows</h3>
      <DataLineageTable rows={deepseekDurableEvidenceRows} />
      </details>
      <details className="developer-audit-details">
        <summary>工程审计详情</summary>
        <p>因子库、Universe、Provider、Tushare、cache ledger 和原始 packet 默认收起；普通用户先看上方量化摘要、评分图表、支持/压制、本地上下文和 DeepSeek 解释状态。</p>
      <h3>因子库</h3>
      <DataLineageTable rows={toRows(factorLibrary.factors)} />
      <h3>运行值</h3>
      <DataLineageTable rows={toRows(runtime.factor_values)} />
      <h3>Factor Universe 研究合同</h3>
      <p className="risk-note">current_target / watchlist / custom_pool / full_pool 是研究 universe 合同；页面渲染不启动 full-pool，不在前端计算 rank/zscore，也不把 partial pool 当全市场证明。</p>
      <DataLineageTable rows={universeResearchRows} />
      <DataLineageTable rows={universeModeRows} />
      <h3>Factor Universe 执行 readiness 审计</h3>
      <p className="risk-note">universe_execution_readiness_audit 汇总 read-plan、storage 查询合同、worker 批量执行、rank/zscore、中性化和 full-pool 验收状态；read_plan_ready_execution_pending 不代表全市场研究生产完成。</p>
      <DataLineageTable rows={universeExecutionCriterionRows} />
      <DataLineageTable rows={universeExecutionReadinessRows} />
      <h3>Factor Universe 执行准入回执</h3>
      <p className="risk-note">universe_execution_readiness_receipt 只说明下一步是否可以进入显式 worker batch 研究任务；它不运行 full-pool，不在前端算 rank/zscore，不把 read-plan 或 partial pool 当生产完成。</p>
      <DataLineageTable rows={universeExecutionReceiptCriterionRows} />
      <DataLineageTable rows={universeExecutionReceiptRows} />
      <h3>Factor Universe execution activation receipt</h3>
      <p className="risk-note">universe_execution_activation_receipt 把下一步固定为显式 worker batch 生产验收；它不创建任务、不启动 worker、不跑 full-pool，不计算生产 rank/zscore 或 neutralization，也不把 readiness receipt 当生产完成。</p>
      <DataLineageTable rows={universeExecutionActivationCriterionRows} />
      <DataLineageTable rows={universeExecutionActivationRows} />
      <h3>Factor Universe worker-batch dry-run ticket</h3>
      <p className="risk-note">universe_worker_batch_dry_run_receipt 只绑定未来显式 worker batch 的 universe 范围、stage scope 和 scope hash；不创建任务、不启动 worker、不调用 Tushare/DeepSeek/GitHub，不代表 worker-backed batch execution 或 production_factor_universe_complete。</p>
      <DataLineageTable rows={universeWorkerBatchDryRunCriterionRows} />
      <DataLineageTable rows={universeWorkerBatchDryRunRows} />
      <h3>Factor Universe worker-batch execution recipe</h3>
      <p className="risk-note">universe_worker_batch_execution_recipe 只固定未来显式 worker batch execution 的顺序和验收证据；它不创建 worker task、不启动 worker、不计算 rank/zscore/neutralization、不调用 Tushare/DeepSeek/GitHub，也不代表 production_factor_universe_complete。</p>
      <DataLineageTable rows={universeWorkerBatchExecutionPhaseRows} />
      <DataLineageTable rows={universeWorkerBatchExecutionRecipeRows} />
      <h3>Factor Universe worker-batch execution request</h3>
      <p className="risk-note">universe_worker_batch_execution_request_receipt 只绑定 latest dry-run scope hash、用户确认和未来 worker task 目标；不创建 worker task、不启动 worker、不调用 Tushare/DeepSeek/GitHub、不计算 rank/zscore/neutralization，也不代表 full-pool production research。</p>
      <DataLineageTable rows={universeWorkerBatchExecutionRequestCriterionRows} />
      <DataLineageTable rows={universeWorkerBatchExecutionRequestRows} />
      <h3>Factor Universe worker-batch research receipt</h3>
      <p className="risk-note">universe_worker_batch_research_receipt 只记录按钮门控的本地 task receipt 和 scope lineage；不启动 worker、不 ping Redis/Celery、不调用 Tushare/DeepSeek/GitHub、不计算 production rank/zscore/neutralization，也不代表 full-pool production research。</p>
      <DataLineageTable rows={universeWorkerBatchResearchCriterionRows} />
      <DataLineageTable rows={universeWorkerBatchResearchRows} />
      <h3>Factor Universe durable evidence recipe</h3>
      <p className="risk-note">factor_universe_durable_evidence_recipe 只固定 LTG-04 worker-backed / full-pool 生产验收直接证据清单；不启动 worker、不调用 Tushare/DeepSeek/GitHub、不在前端计算 rank/zscore、不进入 strategy action，也不代表 production_factor_universe_complete。</p>
      <DataLineageTable rows={universeDurableEvidenceRows} />
      <DataLineageTable rows={universeDurableEvidenceRecipeRows} />
      <h3>Factor Universe 本地 Rank/Zscore Dry-run</h3>
      <p className="risk-note">universe_local_rank_zscore_dry_run 只读本地 factor_values 样本；样本不足时显示 blocked。预览行只用于 research，不代表 full-pool、provider-backed 或生产级 universe 研究完成，前端不计算 rank/zscore。</p>
      <DataLineageTable rows={universeLocalRankZscoreCriterionRows} />
      <DataLineageTable rows={universeLocalRankZscorePreviewRows} />
      <DataLineageTable rows={universeLocalRankZscoreRows} />
      <h3>Factor Universe 任务化读取计划</h3>
      <p className="risk-note">universe_research_task_plan 由按钮任务生成；只读本地 storage 查询合同和分页元信息，不跑 full-pool 研究、不在页面渲染时读取全市场、不进入 strategy action。</p>
      <DataLineageTable rows={universeResearchDatasetRows} />
      <DataLineageTable rows={universeResearchTaskPlanRows} />
      <h3>Factor Test Lab</h3>
      <p className="risk-note">当前为 light 小样本研究指标：IC / Rank IC / ICIR / 分组收益 / 换手 / 成本后收益只用于研究检验，不代表已验证交易信号。</p>
      <DataLineageTable rows={factorTestRows} />
      <h3>Factor Test Storage 查询消费合同</h3>
      <p className="risk-note">Factor Test Lab 只消费 factor_values DuckDB 查询合同、投影列和分页元信息；不把查询样本当作生产 IC 验收，不进入 strategy action。</p>
      <DataLineageTable rows={factorTestStorageQueryTableRows} />
      <DataLineageTable rows={factorTestStorageQueryRows} />
      <h3>Factor Test 本地样本证据审计</h3>
      <p className="risk-note">local_dataset_sample_evidence 只统计本地 Parquet 样本是否足够做后续真实小股票池研究；不从本地查询行计算 IC / Rank IC / ICIR，不代表 provider-backed 或生产级 Factor Test 验收完成。</p>
      <DataLineageTable rows={factorTestLocalDatasetCriterionRows} />
      <DataLineageTable rows={factorTestLocalDatasetRows} />
      <h3>Factor Test 小股票池验收</h3>
      <p className="risk-note">small_pool_acceptance 只审计本地 light observations 的 IC / Rank IC / ICIR / 分组收益 / 成本 / 回撤 / 中性 IC / 样本外与偏差检查；不把 storage query rows 当指标样本，不代表真实小股票池或全市场生产验收。</p>
      <DataLineageTable rows={factorTestSmallPoolCriterionRows} />
      <DataLineageTable rows={factorTestSmallPoolRows} />
      <h3>Factor Test 生产验证 QA 契约</h3>
      <p className="risk-note">production_validation_qa_contract 只定义后续真实小股票池、多周期、多窗口、成本、中性稳定性和偏差控制验收；当前不跑 provider-backed 样本、不跑 full-market、不进入 strategy action。</p>
      <DataLineageTable rows={factorTestProductionValidationCriterionRows} />
      <DataLineageTable rows={factorTestProductionValidationRows} />
      <h3>Factor Test provider 验证 blocker 审计</h3>
      <p className="risk-note">provider_validation_blocker_audit 只汇总真实小股票池、multi-window、成本/中性/偏差控制、full-market 和交易隔离缺口；不调用 Tushare/DeepSeek/GitHub，不从本地样本计算生产 IC，不把 ready 当生产完成。</p>
      <DataLineageTable rows={factorTestProviderValidationBlockerCriterionRows} />
      <DataLineageTable rows={factorTestProviderValidationBlockerRows} />
      <h3>Factor Test provider 小股票池准入回执</h3>
      <p className="risk-note">provider_sample_readiness_receipt 只说明下一步是否可以进入显式 POST 小股票池 provider 验收；它不调用 provider，不把本地样本、light metrics、QA rows 或 blocker audit 提升为生产验收。</p>
      <DataLineageTable rows={factorTestProviderSampleReadinessCriterionRows} />
      <DataLineageTable rows={factorTestProviderSampleReadinessRows} />
      <h3>Factor Test provider 小股票池 activation 回执</h3>
      <p className="risk-note">provider_sample_activation_receipt 是真实小股票池 provider 验收前的本地清单：不调用 provider、不创建任务、不把本地样本/QA/blocker rows 当 production validation，也不进入 strategy action。</p>
      <DataLineageTable rows={factorTestProviderSampleActivationCriterionRows} />
      <DataLineageTable rows={factorTestProviderSampleActivationRows} />
      <h3>Factor Test provider 小股票池 dry-run ticket</h3>
      <p className="risk-note">provider_small_pool_acceptance_dry_run 只绑定未来真实小池验收范围、凭据存在布尔和 scope hash；不调用 Tushare，不计算生产 IC，不泄露敏感凭据，不代表 provider-backed validation。</p>
      <DataLineageTable rows={factorTestProviderSmallPoolDryRunCriterionRows} />
      <DataLineageTable rows={factorTestProviderSmallPoolDryRunRows} />
      <h3>Factor Test provider 小股票池 execution recipe</h3>
      <p className="risk-note">provider_small_pool_execution_recipe 只固定未来真实 provider-backed 小股票池验收顺序和证据清单；不创建 provider task、不调用 Tushare/DeepSeek/GitHub、不计算生产 IC/Rank IC/ICIR、不进入 strategy action，也不代表 production_factor_test_validation_complete。</p>
      <DataLineageTable rows={factorTestProviderSmallPoolExecutionPhaseRows} />
      <DataLineageTable rows={factorTestProviderSmallPoolExecutionRecipeRows} />
      <h3>Factor Test provider 小股票池 execution request</h3>
      <p className="risk-note">provider_small_pool_execution_request 只绑定 latest dry-run scope hash、用户确认和未来 provider task 目标；不创建 provider task、不调用 Tushare/DeepSeek/GitHub、不计算生产指标，也不代表 provider-backed validation。</p>
      <DataLineageTable rows={factorTestProviderSmallPoolExecutionRequestCriterionRows} />
      <DataLineageTable rows={factorTestProviderSmallPoolExecutionRequestRows} />
      <h3>Factor Test provider 小股票池 acceptance gate</h3>
      <p className="risk-note">provider_small_pool_acceptance_gate 只记录显式小池验收门槛、scope hash 和缺失证据；默认不授权 live provider、不调用 Tushare、不采集样本、不计算生产指标，也不代表 provider-backed validation。</p>
      <DataLineageTable rows={factorTestProviderSmallPoolAcceptanceCriterionRows} />
      <DataLineageTable rows={factorTestProviderSmallPoolAcceptanceRows} />
      <h3>Factor Test durable evidence recipe</h3>
      <p className="risk-note">factor_test_durable_evidence_recipe 只固定 LTG-03 真实小股票池生产验收直接证据清单；不调用 Tushare/DeepSeek/GitHub、不计算生产 IC/Rank IC/ICIR、不进入 strategy action，也不代表 provider-backed 或 production Factor Test 完成。</p>
      <DataLineageTable rows={factorTestDurableEvidenceRows} />
      <DataLineageTable rows={factorTestDurableEvidenceRecipeRows} />
      <h3>Factor Test production stage scope manifest</h3>
      <p className="risk-note">factor_test_production_stage_scope_manifest 只把 LTG-03 生产阶段的 local surface、provider direct evidence 和 pending blockers 展示到 cache/UI；不创建 provider task、不调用 Tushare/DeepSeek/GitHub、不计算生产指标、不代表 production Factor Test complete。</p>
      <DataLineageTable rows={factorTestProductionStageScopeRows} />
      <DataLineageTable rows={factorTestProductionStageScopeManifestRows} />
      <h3>Factor Test 指标 schema</h3>
      <DataLineageTable rows={factorTestMetricRows} />
      <h3>Factor Test 阶段计划</h3>
      <DataLineageTable rows={factorTestModeRows} />
      <h3>Factor Test 状态验收合同</h3>
      <p className="risk-note">research_pass / watchlist / disabled / invalid / not_enough_data 都是研究状态；research_pass 也不是买入信号，不进入交易动作、交易核心动作、研究预览或次日图谱推演。</p>
      <DataLineageTable rows={factorTestAcceptanceRows} />
      <DataLineageTable rows={factorTestStateRows} />
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
      <h3>Tushare 失败模式 QA</h3>
      <p className="risk-note">failure_mode_qa_contract 只分类按钮任务已有 call_ledger：empty / no record / empty window、permission denied、parse failure / invalid result、missing required parameter、provider error 和 matrix-only；它不调用 Tushare，不证明 provider-backed 全接口生产验收。</p>
      <DataLineageTable rows={tushareFailureModeCriterionRows} />
      <DataLineageTable rows={tushareFailureModeQaRows} />
      <h3>Tushare 请求参数 QA</h3>
      <p className="risk-note">request_parameter_qa_contract 只审计按钮任务的安全参数、ts_code 预检阻断、日期上下文字段和 matrix-only 边界；date context 可见不等于 provider-backed 接口验收完成。</p>
      <DataLineageTable rows={tushareRequestParameterCriterionRows} />
      <DataLineageTable rows={tushareRequestParameterQaRows} />
      <h3>Tushare 目标样本计划</h3>
      <p className="risk-note">provider_target_sample_plan_contract 只声明后续真实验收的目标域、必选接口、样本窗口、成功证据和失败证据；ready_to_execute_provider_sample 也只是计划就绪，不等于 provider-backed acceptance。</p>
      <DataLineageTable rows={tushareProviderTargetSamplePlanCriterionRows} />
      <DataLineageTable rows={tushareProviderTargetSamplePlanRows} />
      <h3>Tushare provider 验收提升审计</h3>
      <p className="risk-note">provider_acceptance_promotion_audit 只读按钮任务已有 call_ledger；matrix、local QA、fake adapter 样本和 readiness audit 都不能单独提升 provider-backed 全接口验收。</p>
      <DataLineageTable rows={tushareProviderPromotionCriterionRows} />
      <DataLineageTable rows={tushareProviderPromotionAuditRows} />
      <h3>Tushare provider 证据缺口台账</h3>
      <p className="risk-note">provider_evidence_gap_audit 只读本地 call_ledger、目标域计划和提升审计，逐目标域显示缺失的真实 provider 证据；它不调用 Tushare，也不把缺口清单当生产验收。</p>
      <DataLineageTable rows={tushareProviderEvidenceGapRows} />
      <DataLineageTable rows={tushareProviderEvidenceGapAuditRows} />
      <h3>Tushare provider 样本准入回执</h3>
      <p className="risk-note">provider_sample_readiness_receipt 只说明下一步是否可以进入显式 POST 样本验收任务；它不调用 Tushare，不把 matrix、fake/local adapter、local QA 或 gap ledger 提升为生产验收。</p>
      <DataLineageTable rows={tushareProviderSampleReadinessCriterionRows} />
      <DataLineageTable rows={tushareProviderSampleReadinessRows} />
      <PacketCard title="Tushare durable evidence recipe" subtitle="LTG-02 全接口生产验收证据配方；只读缺口，不调用 Tushare" status={String(tushareDurableEvidenceRecipe.status ?? "missing")}>
        <p>schema_version: {String(tushareDurableEvidenceRecipe.schema_version ?? "tushare_durable_evidence_recipe.v1")}</p>
        <p>scope: {String(tushareDurableEvidenceRecipe.scope ?? "local_tushare_durable_evidence_recipe_no_provider_execution")}</p>
        <p>local_recipe_ready / durable_evidence_complete: {String(tushareDurableEvidenceRecipe.local_recipe_ready ?? false)} / {String(tushareDurableEvidenceRecipe.durable_evidence_complete ?? false)}</p>
        <p>provider_backed_acceptance_done / full_interface_acceptance_done: {String(tushareDurableEvidenceRecipe.provider_backed_acceptance_done ?? false)} / {String(tushareDurableEvidenceRecipe.full_interface_acceptance_done ?? false)}</p>
        <p>production_tushare_pipeline_complete: {String(tushareDurableEvidenceRecipe.production_tushare_pipeline_complete ?? false)}</p>
        <p>durable_evidence_blocker_count: {String(tushareDurableEvidenceRecipe.durable_evidence_blocker_count ?? 0)}</p>
        <p>blocking_evidence_keys: {Array.isArray(tushareDurableEvidenceRecipe.blocking_evidence_keys) ? tushareDurableEvidenceRecipe.blocking_evidence_keys.join(" / ") : ""}</p>
        <p>allowed_next_step: {String(tushareDurableEvidenceRecipe.allowed_next_step ?? "collect_provider_target_sample_call_ledger_failure_mode_full_interface_storage_promotion_evidence")}</p>
        <p>not_allowed_next_steps: {Array.isArray(tushareDurableEvidenceRecipe.not_allowed_next_steps) ? tushareDurableEvidenceRecipe.not_allowed_next_steps.join(" / ") : "treat durable recipe as provider-backed Tushare acceptance / call Tushare from GET cache / call Tushare from React render"}</p>
        <p>provider_refresh_called_by_recipe / cache_get_external_calls / react_render_external_calls: {String(tushareDurableEvidenceRecipe.provider_refresh_called_by_recipe ?? false)} / {String(tushareDurableEvidenceRecipe.cache_get_external_calls ?? false)} / {String(tushareDurableEvidenceRecipe.react_render_external_calls ?? false)}</p>
        <p>tushare / deepseek / github: {String(tushareDurableEvidenceRecipe.tushare_called_by_recipe ?? false)} / {String(tushareDurableEvidenceRecipe.deepseek_called ?? false)} / {String(tushareDurableEvidenceRecipe.github_called ?? false)}</p>
      </PacketCard>
      <h3>Tushare durable evidence rows</h3>
      <DataLineageTable rows={tushareDurableEvidenceRows} />
      <DataLineageTable rows={tushareDurableEvidenceRecipeRows} />
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
      </details>
    </PacketCard>
  );
}
