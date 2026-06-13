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
  const launchTask = (path: string, payload: Record<string, unknown> = {}) =>
    void postTask(path, payload).then((res) => {
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
  const universeResearch = packet.universe_research_contract ?? {};
  const universeExecutionReadiness = packet.universe_execution_readiness_audit ?? {};
  const universeResearchTaskPlan = packet.universe_research_task_plan ?? {};
  const factorLibrary = packet.factor_library ?? {};
  const factorTests = packet.factor_tests ?? {};
  const factorTestQuality = factorTests.quality_summary ?? {};
  const factorTestAcceptance = factorTests.acceptance_contract ?? {};
  const factorTestStorageQuery = factorTests.storage_query_consumption ?? {};
  const factorTestSmallPool = factorTests.small_pool_acceptance ?? {};
  const factorTestProductionValidation = factorTests.production_validation_qa_contract ?? {};
  const tushareFailureModeQa = packet.failure_mode_qa_contract ?? {};
  const tushareRequestParameterQa = packet.request_parameter_qa_contract ?? {};
  const tushareProviderTargetSamplePlan = packet.provider_target_sample_plan_contract ?? {};
  const tushareProviderPromotionAudit = packet.provider_acceptance_promotion_audit ?? {};
  const dataLedger = packet.data_ledger ?? {};
  const researchContext = packet.research_context ?? {};
  const linkedPackets = packet.linked_packets ?? {};
  const deepseek = packet.deepseek_explanation ?? {};
  const deepseekGovernance = packet.deepseek_explain_governance ?? {};
  const deepseekValidation = packet.deepseek_validation_summary ?? {};
  const deepseekJsonStability = packet.deepseek_json_stability_audit ?? {};
  const deepseekResponseFormatReview = packet.deepseek_response_format_review_contract ?? {};
  const scoreChart = packet.score_chart_payload ?? {};
  const scoreChartContract = scoreChart.chart_contract ?? {};
  const scoreChartRows = toRows(scoreChart.bucket_rows);
  const scoreChartContractRows = objectRows(scoreChartContract as Record<string, unknown>, "chart_contract");
  const deepseekValidationRows = objectRows(deepseekValidation as Record<string, unknown>, "deepseek_validation");
  const deepseekJsonStabilityRows = toRows(packet.deepseek_json_stability_rows);
  const deepseekResponseFormatReviewRows = toRows(packet.deepseek_response_format_review_rows);
  const universeResearchRows = objectRows(universeResearch as Record<string, unknown>, "universe_contract");
  const universeModeRows = toRows(packet.universe_research_mode_rows);
  const universeExecutionReadinessRows = objectRows(universeExecutionReadiness as Record<string, unknown>, "universe_execution_readiness");
  const universeExecutionCriterionRows = toRows(packet.universe_execution_readiness_rows);
  const universeResearchTaskPlanRows = objectRows(universeResearchTaskPlan as Record<string, unknown>, "universe_read_plan");
  const universeResearchDatasetRows = toRows(packet.universe_research_task_plan_rows);
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
  const factorTestSmallPoolRows = objectRows(factorTestSmallPool as Record<string, unknown>, "small_pool_acceptance");
  const factorTestSmallPoolCriterionRows = toRows(factorTests.small_pool_acceptance_rows);
  const factorTestProductionValidationRows = objectRows(factorTestProductionValidation as Record<string, unknown>, "production_validation");
  const factorTestProductionValidationCriterionRows = toRows(factorTests.production_validation_qa_rows);
  const tushareFailureModeQaRows = objectRows(tushareFailureModeQa as Record<string, unknown>, "failure_mode_contract");
  const tushareFailureModeCriterionRows = toRows(packet.failure_mode_qa_rows);
  const tushareRequestParameterQaRows = objectRows(tushareRequestParameterQa as Record<string, unknown>, "request_parameter_contract");
  const tushareRequestParameterCriterionRows = toRows(packet.request_parameter_qa_rows);
  const tushareProviderTargetSamplePlanRows = objectRows(tushareProviderTargetSamplePlan as Record<string, unknown>, "target_sample_plan");
  const tushareProviderTargetSamplePlanCriterionRows = toRows(packet.provider_target_sample_plan_rows);
  const tushareProviderPromotionAuditRows = objectRows(tushareProviderPromotionAudit as Record<string, unknown>, "provider_promotion_audit");
  const tushareProviderPromotionCriterionRows = toRows(packet.provider_acceptance_promotion_rows);
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
        <label className="inline-toggle">
          <input
            type="checkbox"
            checked={autoAfterTask}
            onChange={(event) => setAutoAfterTask(event.target.checked)}
          />
          run-light 成功后尝试自动排队解释
        </label>
        <button onClick={() => launchTask("/api/factor-quant/run-light", { auto_after_task: autoAfterTask })}>运行计算</button>
        <button onClick={() => launchTask("/api/factor-quant/universe-research-plan", { universe_mode: "full_pool" })}>生成读取计划</button>
        <button onClick={() => launchTask("/api/factor-quant/deepseek-explain")}>DeepSeek 整理</button>
      </div>
      <p className="risk-note">DeepSeek 解释模式：{String(deepseekGovernance.mode ?? "manual_only")}；auto_after_task 默认关闭。自动解释已关闭时，可手动点击生成解释。</p>
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
          { label: "universe", value: universeResearch.current_universe_type ?? "current_target" },
          { label: "universe size", value: universeResearch.current_universe_size ?? 0 },
          { label: "full pool", value: universeResearch.full_pool_validation_done === true ? "完成" : "未完成", tone: universeResearch.full_pool_validation_done === true ? "good" : "neutral" },
          { label: "render scan", value: universeResearch.page_render_starts_full_pool === true ? "会启动" : "不启动", tone: universeResearch.page_render_starts_full_pool === true ? "bad" : "good" },
          { label: "frontend rank/zscore", value: universeResearch.frontend_computes_rank_zscore === true ? "会计算" : "不计算", tone: universeResearch.frontend_computes_rank_zscore === true ? "bad" : "good" },
          { label: "partial pool proof", value: universeExecutionReadiness.partial_pool_is_full_market_proof === true ? "误作全市场" : "不是全市场证明", tone: universeExecutionReadiness.partial_pool_is_full_market_proof === true ? "bad" : "good" },
          { label: "universe read plan", value: universeResearchTaskPlan.status ?? "missing", tone: universeResearchTaskPlan.status === "read_plan_ready" ? "good" : "neutral" },
          { label: "universe exec audit", value: universeExecutionReadiness.status ?? "missing", tone: universeExecutionReadiness.read_plan_ready === true ? "good" : "warn" },
          { label: "universe blockers", value: universeExecutionReadiness.production_blocker_count ?? 0, tone: Number(universeExecutionReadiness.production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "worker plan", value: universeResearchTaskPlan.worker_task_consumption_plan_ready === true ? "ready" : "missing", tone: universeResearchTaskPlan.worker_task_consumption_plan_ready === true ? "good" : "neutral" },
          { label: "read plan datasets", value: universeResearchTaskPlan.dataset_count ?? 0 },
          { label: "plan full pool done", value: universeResearchTaskPlan.full_pool_validation_done === true ? "完成" : "未完成", tone: universeResearchTaskPlan.full_pool_validation_done === true ? "bad" : "good" },
          { label: "rank/zscore", value: universeExecutionReadiness.cross_sectional_rank_zscore_done === true ? "完成" : "未完成", tone: universeExecutionReadiness.cross_sectional_rank_zscore_done === true ? "good" : "warn" },
          { label: "neutralization", value: universeExecutionReadiness.neutralization_done === true ? "完成" : "未完成", tone: universeExecutionReadiness.neutralization_done === true ? "good" : "warn" },
          { label: "universe production", value: universeExecutionReadiness.production_factor_universe_complete === true ? "完成" : "未完成", tone: universeExecutionReadiness.production_factor_universe_complete === true ? "good" : "warn" },
          { label: "score band", value: score.score_band ?? "missing" },
          { label: "factor tests", value: factorTests.status ?? "scaffold_missing", tone: factorTests.status === "scaffold_ready" ? "warn" : "neutral" },
          { label: "test rows", value: factorTestRows.length },
          { label: "test quality", value: factorTestQuality.status ?? "scaffold_only", tone: factorTestQuality.status === "computed_light_metrics_ready" ? "good" : "warn" },
          { label: "storage query", value: factorTestStorageQuery.status ?? "missing", tone: factorTestStorageQuery.external_calls_triggered === true ? "bad" : "neutral" },
          { label: "storage query rows", value: factorTestStorageQuery.returned_row_count ?? 0 },
          { label: "storage query metrics", value: factorTestStorageQuery.metrics_computed_from_storage_query === true ? "会计算" : "不计算", tone: factorTestStorageQuery.metrics_computed_from_storage_query === true ? "bad" : "good" },
          { label: "small pool audit", value: factorTestSmallPool.status ?? "missing", tone: factorTestSmallPool.status === "local_small_pool_acceptance_ready" ? "good" : "warn" },
          { label: "local small pool", value: factorTestSmallPool.local_light_observation_acceptance_done === true ? "ready" : "pending", tone: factorTestSmallPool.local_light_observation_acceptance_done === true ? "good" : "warn" },
          { label: "real small pool", value: factorTestSmallPool.real_small_pool_validation_done === true ? "完成" : "未完成", tone: factorTestSmallPool.real_small_pool_validation_done === true ? "bad" : "good" },
          { label: "production QA", value: factorTestProductionValidation.status ?? "missing", tone: factorTestProductionValidation.production_factor_test_validation_complete === true ? "good" : "warn" },
          { label: "provider small pool", value: factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "完成" : "未完成", tone: factorTestProductionValidation.provider_backed_small_pool_validation_done === true ? "good" : "warn" },
          { label: "factor test production", value: factorTestProductionValidation.production_factor_test_validation_complete === true ? "完成" : "未完成", tone: factorTestProductionValidation.production_factor_test_validation_complete === true ? "good" : "warn" },
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
          { label: "DS auto ready", value: deepseekJsonStability.auto_after_task_production_ready === true ? "ready" : "blocked", tone: deepseekJsonStability.auto_after_task_production_ready === true ? "good" : "warn" },
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
          { label: "provider evidence rows", value: tushareProviderPromotionAudit.provider_evidence_row_count ?? 0, tone: Number(tushareProviderPromotionAudit.provider_evidence_row_count ?? 0) > 0 ? "warn" : "neutral" }
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
      </PacketCard>
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
      <h3>Factor Test 小股票池验收</h3>
      <p className="risk-note">small_pool_acceptance 只审计本地 light observations 的 IC / Rank IC / ICIR / 分组收益 / 成本 / 回撤 / 中性 IC / 样本外与偏差检查；不把 storage query rows 当指标样本，不代表真实小股票池或全市场生产验收。</p>
      <DataLineageTable rows={factorTestSmallPoolCriterionRows} />
      <DataLineageTable rows={factorTestSmallPoolRows} />
      <h3>Factor Test 生产验证 QA 契约</h3>
      <p className="risk-note">production_validation_qa_contract 只定义后续真实小股票池、多周期、多窗口、成本、中性稳定性和偏差控制验收；当前不跑 provider-backed 样本、不跑 full-market、不进入 strategy action。</p>
      <DataLineageTable rows={factorTestProductionValidationCriterionRows} />
      <DataLineageTable rows={factorTestProductionValidationRows} />
      <h3>Factor Test 指标 schema</h3>
      <DataLineageTable rows={factorTestMetricRows} />
      <h3>Factor Test 阶段计划</h3>
      <DataLineageTable rows={factorTestModeRows} />
      <h3>Factor Test 状态验收合同</h3>
      <p className="risk-note">research_pass / watchlist / disabled / invalid / not_enough_data 都是研究状态；research_pass 也不是买入信号，不进入 strategy action、core action、evidence_effects 或 next-session projection。</p>
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
