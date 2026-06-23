import { useEffect, useState } from "react";
import type { EChartsOption } from "echarts";
import { getBootstrapStatus, getFactorQuantCache, postTask, type TaskCreationEnvelope } from "../api/client";
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
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<unknown>>([]);
  const [bootstrapStatus, setBootstrapStatus] = useState<Record<string, unknown>>({});
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
  const launchTask = (path: string, payload: Record<string, unknown> = {}) =>
    void postTask(path, payload).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });

  useEffect(() => {
    refreshCache();
    refreshBootstrapStatus();
  }, []);

  const score = packet.score ?? {};
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
  const factorTestDurableEvidenceRecipe = factorTests.durable_evidence_recipe ?? {};
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
  const factorTestDurableEvidenceRecipeRows = objectRows(factorTestDurableEvidenceRecipe as Record<string, unknown>, "factor_test_durable_evidence_recipe");
  const factorTestDurableEvidenceRows = toRows(factorTests.durable_evidence_rows);
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
    ? "先从下一票雷达输入股票代码并生成 3.0 量化推演；本页查看本地缓存，不自动刷新外部数据或模型解释"
    : "先看支持/压制与次日图谱预览；换标的从下一票雷达输入代码并点生成 3.0 量化推演；需要更新时再手动刷新数据、运行轻量推演或整理模型解释";
  const ordinaryQuantPrimaryActionLabel = empty ? "去下一票雷达生成推演" : "查看支持/压制";
  const ordinaryQuantPrimaryActionHref = empty ? "#candidates" : "#factor-score";
  const ordinaryQuantPrimaryActionBoundary = empty
    ? "主下一步只切换到下一票雷达；输入代码和生成推演仍需按钮确认"
    : "主下一步只跳转本地支持/压制摘要；不刷新 provider/model、不写 cache";
  const ordinaryQuantSymbolEntryBoundary =
    "本页不提供股票代码输入；换标的必须回下一票雷达输入代码并点击确认生成，输入本身不创建 task";
  const ordinaryQuantCacheSourceLabel = empty ? "等待本地量化缓存" : "本地量化缓存可用";
  const ordinaryQuantTushareSourceLabel =
    Number(tushareProviderPromotionAudit.provider_evidence_row_count ?? 0) > 0 ? "Tushare 数据有本地记录" : "等待手动补充 Tushare 数据";
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
    `Tushare 数据：${ordinaryQuantTushareSourceLabel}`,
    `DeepSeek 解释：${ordinaryQuantDeepSeekSourceLabel}`,
    `模型状态：${ordinaryQuantModelSourceLabel}`,
    `Pending 状态：${ordinaryQuantPendingStateLabel}`
  ].join(" / ");
  const ordinaryQuantDataLedgerRows = toRows(dataLedger.ledger_rows);
  const ordinaryQuantLedgerSourceLabel =
    cacheCallLedger.length || ordinaryQuantDataLedgerRows.length ? "ledger 回放可用" : "等待本地 ledger 回放";
  const ordinaryQuantPacketSourceLabel =
    Object.keys(packet).length ? "packet 回放可用" : "等待本地 packet";
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
  const ordinaryQuantReviewOrder = empty
    ? "先回下一票雷达输入代码并确认生成；本页只等本地结果回放"
    : "先看支持/压制，再看次日图谱预览，最后看模型解释状态；不要从工程审计表开始";
  const ordinaryQuantResultComposition = [
    `支持 ${String(score.support_factors?.length ?? 0)} / 压制 ${String(score.suppress_factors?.length ?? 0)} / 冲突 ${String(score.conflict_factors?.length ?? 0)} / 缺失 ${String(score.missing_factors?.length ?? 0)}`,
    `次日图谱：${String(bridge.status ?? bridge.bridge_status ?? "等待本地缓存")}`,
    `模型解释：${ordinaryQuantDeepSeekSourceLabel}`
  ].join(" / ");
  const ordinaryQuantResultBoundary =
    "结果只用于研究复核；支持/压制、次日图谱和模型解释都不能直接变成买卖指令";
  const ordinaryDeepSeekGovernedExecutorState =
    deepseek.called === true
      ? "已有本地模型解释缓存；仍只解释不改数值或动作"
      : "等待 governed executor；不阻塞 Tushare-first、支持/压制和次日图谱";
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
  const ordinaryQuantHandoffRows = [
    {
      交接段: "按钮确认",
      用户看到: empty ? "先回下一票雷达输入代码并确认生成" : "已从本地量化缓存读取确认后的推演结果",
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
      边界: "ledger 只展示状态、接口、行数和时间；token/key 不进前端、日志、packet 或 cache"
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
  const ordinaryQuantRuntimeModeLabel = `运行模式：${runtimeModeLabel(ordinaryQuantRuntimeMode)}`;
  const ordinaryQuantTaskBoundary =
    "本页 GET cache 只读；手动刷新、轻量推演、模型整理或 live_light 补证都必须走 POST task，不在 React 渲染中直连 Tushare 或 DeepSeek";
  const ordinaryQuantCacheButtonLabel = "查看本地缓存只读取 GET cache；不会创建 task、不会调用 Tushare 或 DeepSeek";
  const ordinaryQuantRefreshButtonLabel = "手动刷新数据会创建按钮门控 POST task；不从 React render 直连 provider/model";
  const ordinaryQuantRunLightButtonLabel = "运行轻量推演会创建按钮门控 POST task；DeepSeek 整理仍在高级开关";
  const ordinaryQuantStatusLabel = empty ? "等待量化缓存" : "量化缓存可用";

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
        <MetricGrid
          items={[
            { label: "下一步", value: ordinaryQuantNextClick },
            { label: "主下一步", value: ordinaryQuantPrimaryActionLabel },
            { label: "主下一步边界", value: ordinaryQuantPrimaryActionBoundary, tone: "good" },
            { label: "换标的入口", value: ordinaryQuantSymbolEntryBoundary, tone: "good" },
            { label: "运行模式", value: ordinaryQuantRuntimeModeLabel },
            { label: "cache", value: ordinaryQuantCacheSourceLabel },
            { label: "Tushare", value: ordinaryQuantTushareSourceLabel },
            { label: "DeepSeek", value: ordinaryQuantDeepSeekSourceLabel },
            { label: "pending", value: ordinaryQuantPendingStateLabel, tone: ordinaryQuantPendingStateLabel.includes("待补") || ordinaryQuantPendingStateLabel.includes("等待") ? "warn" : "good" },
            { label: "degraded", value: ordinaryQuantDegradedSourceLabel, tone: ordinaryQuantDegradedSourceLabel.includes("未标记") ? "good" : "warn" },
            { label: "last_successful_cache/result", value: ordinaryQuantLastCache },
            { label: "雷达搜票回放", value: ordinaryQuantRadarHandoffState, tone: empty ? "warn" : "good" },
            { label: "回放位置", value: ordinaryQuantReplayLocation, tone: "good" },
            { label: "结果位置", value: ordinaryQuantResultLocation, tone: "good" },
            { label: "查看顺序", value: ordinaryQuantReviewOrder },
            { label: "结果组成", value: ordinaryQuantResultComposition },
            { label: "数据来源状态", value: ordinaryQuantSourceState },
            { label: "交接清单", value: ordinaryQuantHandoffLocation, tone: "good" },
            { label: "ledger", value: ordinaryQuantLedgerSourceLabel, tone: ordinaryQuantLedgerSourceLabel.includes("等待") ? "warn" : "good" },
            { label: "packet", value: ordinaryQuantPacketSourceLabel, tone: ordinaryQuantPacketSourceLabel.includes("等待") ? "warn" : "good" },
            { label: "P5 DeepSeek", value: ordinaryDeepSeekGovernedExecutorState, tone: deepseek.called === true ? "warn" : "good" },
            { label: "补证方式", value: ordinaryQuantEvidenceTaskState, tone: ordinaryQuantEvidenceTaskState.includes("等待") || ordinaryQuantEvidenceTaskState.includes("待补") || ordinaryQuantEvidenceTaskState.includes("未知") ? "warn" : "good" },
            { label: "缺少证据", value: ordinaryQuantMissingEvidence, tone: ordinaryQuantMissingEvidence.includes("待补") || ordinaryQuantMissingEvidence.includes("待确认") ? "warn" : "good" },
            { label: "阻断/降级", value: ordinaryQuantBlockedState, tone: ordinaryQuantBlockedState.includes("未标记") ? "good" : "warn" },
            { label: "最近可用缓存", value: ordinaryQuantLastCache },
            { label: "任务边界", value: ordinaryQuantTaskBoundary },
            { label: "结果边界", value: ordinaryQuantResultBoundary, tone: "good" },
            { label: "仅供研究", value: "量化推演不是买卖指令；不真实交易、不下单、不改交易策略或操作区", tone: "good" }
          ]}
        />
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
        <div aria-label="stock quant ordinary deepseek governance">
          <h3>DeepSeek 单独治理状态</h3>
          <p className="risk-note">DeepSeek 解释单独补证；不阻塞 Tushare-first、支持/压制和次日图谱；普通页不展示 prompt/output。</p>
          <DataLineageTable rows={ordinaryDeepSeekGovernedExecutorRows} />
        </div>
        <div className="actions" aria-label="stock quant projection primary next action">
          <a href={ordinaryQuantPrimaryActionHref} aria-label="open stock quant primary next action">{ordinaryQuantPrimaryActionLabel}</a>
        </div>
        <div className="actions" aria-label="stock quant projection source actions">
          <a href="#factor-score" aria-label="view factor support suppress summary">查看支持/压制</a>
          <a href="#factor-next-session" aria-label="view next session bridge preview">查看次日图谱预览</a>
          <a href="#factor-deepseek" aria-label="view model explanation status">查看模型解释状态</a>
          <a href="#candidates">去下一票雷达生成推演</a>
        </div>
        <p className="risk-note">没有标的时先去 <a href="#candidates">下一票雷达</a> 输入代码并点击生成 3.0 量化推演；这个链接只切换本地页面，不创建 task。</p>
        <p className="risk-note">本页不接收股票代码输入；换标的必须回下一票雷达确认按钮，避免把查看缓存误当成重新推演。</p>
        <p className="risk-note">来自下一票雷达的搜票结果在本页只回放 Factor cache、次日图谱预览和模型解释状态；本页链接不重新触发 Tushare-first 或 DeepSeek。</p>
        <p className="risk-note">{ordinaryQuantResultLocation}</p>
        <p className="risk-note">生成后先按“支持/压制 → 次日图谱预览 → 模型解释状态”复核；缺数据就看 pending/缺少证据，不把空结果当成无风险。</p>
        <p className="risk-note">摘要里的查看链接只是本地锚点跳转，不创建 task、不调用 Tushare 或 DeepSeek、不写 cache，也不改变交易策略。</p>
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
          <button onClick={() => launchTask("/api/factor-quant/provider-small-pool-dry-run", { approved_by_user: true, symbols: ["002008.SZ", "000001.SZ", "600000.SH", "600519.SH", "300750.SZ"], forward_return_horizons: ["1d", "5d"] })}>小池验收预检</button>
          <button onClick={() => launchTask("/api/factor-quant/provider-small-pool-execution-request", { approved_by_user: true, acceptance_scope_hash: String(factorTestProviderSmallPoolDryRun.acceptance_scope_hash ?? "") })}>小池执行请求</button>
          <button onClick={() => launchTask("/api/factor-quant/deepseek-provider-benchmark-scope-ticket", { approved_by_user: true, sample_count: 40, response_format: "json_schema", max_retry_per_sample: 2 })}>DeepSeek benchmark 预检</button>
        </div>
      </details>
      <p className="risk-note">模型解释默认手动触发；勾选自动整理后，轻量推演完成可继续整理解释。</p>
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
      <p className="risk-note">provider_small_pool_acceptance_dry_run 只绑定未来真实小池验收范围、凭据存在布尔和 scope hash；不调用 Tushare，不计算生产 IC，不泄露 token/key，不代表 provider-backed validation。</p>
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
      <h3>Factor Test durable evidence recipe</h3>
      <p className="risk-note">factor_test_durable_evidence_recipe 只固定 LTG-03 真实小股票池生产验收直接证据清单；不调用 Tushare/DeepSeek/GitHub、不计算生产 IC/Rank IC/ICIR、不进入 strategy action，也不代表 provider-backed 或 production Factor Test 完成。</p>
      <DataLineageTable rows={factorTestDurableEvidenceRows} />
      <DataLineageTable rows={factorTestDurableEvidenceRecipeRows} />
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
