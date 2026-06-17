import { useEffect, useState } from "react";
import { getBootstrapStatus, getCandidateRadarCache, postCandidateRadarBrowserQaReview, postCandidateRadarDeepScanLocalReview, postCandidateRadarDeepScanPlan, postCandidateRadarDeepScanWorker, postCandidateRadarFullPoolLocalScan, postCandidateRadarFullPoolPlan, postCandidateRadarFullPoolWorkerScan, postCandidateRadarLegacyRetirementReview, postCandidateRadarProductionPromotionDryRun, postCandidateRadarProductionPromotionReview, postCandidateRadarProductionReplacementReview, postCandidateRadarProviderParityDryRun, postCandidateRadarQuantProjection, postCandidateRadarQuantProjectionAcceptanceDryRun, postCandidateRadarQuantProjectionExecutionRequest, postCandidateRadarQuickScan, postCandidateRadarWorkerExecutionRequest, type TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StateClarityRail from "../components/StateClarityRail";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function objectRow(value: unknown): Array<Record<string, unknown>> {
  return value && typeof value === "object" && !Array.isArray(value) ? [value as Record<string, unknown>] : [];
}

export default function CandidateRadar() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);
  const [bootstrapStatus, setBootstrapStatus] = useState<Record<string, unknown>>({});
  const [bootstrapEnvelopeLedger, setBootstrapEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [bootstrapEnvelopeWarnings, setBootstrapEnvelopeWarnings] = useState<Array<string>>([]);
  const [taskId, setTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [customPoolText, setCustomPoolText] = useState("");
  const [searchSymbol, setSearchSymbol] = useState("");

  const refreshCache = () => {
    void getCandidateRadarCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  };
  const refreshBootstrapStatus = () => {
    void getBootstrapStatus().then((res) => {
      setBootstrapStatus(res.data);
      setBootstrapEnvelopeLedger(res.call_ledger ?? []);
      setBootstrapEnvelopeWarnings(res.warnings ?? []);
    });
  };
  const launchQuickScan = () =>
    void postCandidateRadarQuickScan({ scan_mode: "quick_cache_scan", universe_mode: "cache_snapshot" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchQuantProjection = () =>
    void postCandidateRadarQuantProjection({
      scan_mode: "search_quant_projection",
      symbol: searchSymbol,
      include_tushare: true,
      include_deepseek: true,
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchQuantProjectionAcceptanceDryRun = () =>
    void postCandidateRadarQuantProjectionAcceptanceDryRun({
      scan_mode: "search_quant_projection",
      symbol: searchSymbol || String(searchQuantProjectionReceipt.symbol ?? ""),
      include_tushare: true,
      include_deepseek: true,
      user_approved: true,
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchProviderParityDryRun = () =>
    void postCandidateRadarProviderParityDryRun({
      scan_mode: "provider_parity_dry_run",
      candidate_symbols: searchSymbol || String(searchQuantProjectionReceipt.symbol ?? ""),
      selected_signal_groups: ["moneyflow", "dragon_tiger", "limit_emotion", "chip_radar", "hard_risk"],
      include_tushare: true,
      include_deepseek: true,
      user_approved: true,
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchWatchlistScan = () =>
    void postCandidateRadarQuickScan({ scan_mode: "watchlist_scan", universe_mode: "local_watchlist" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchCustomScan = () =>
    void postCandidateRadarQuickScan({
      scan_mode: "custom_pool_scan",
      universe_mode: "manual_input",
      custom_pool_text: customPoolText
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchFullPoolPlan = () =>
    void postCandidateRadarFullPoolPlan({ scan_mode: "full_pool_scan", plan_only: true }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchFullPoolLocalScan = () =>
    void postCandidateRadarFullPoolLocalScan({ scan_mode: "full_pool_local_scan", local_execution_only: true }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchDeepScanPlan = () =>
    void postCandidateRadarDeepScanPlan({ scan_mode: "deep_scan", plan_only: true, scan_depth: "legacy_parity_first" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchDeepScanLocalReview = () =>
    void postCandidateRadarDeepScanLocalReview({ scan_mode: "deep_scan_local_review", local_review_only: true, scan_depth: "legacy_parity_first" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchBrowserQaReview = () =>
    void postCandidateRadarBrowserQaReview({ review_scope: "candidate_route_browser_qa_local_artifact" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });

  useEffect(() => {
    refreshCache();
    refreshBootstrapStatus();
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const scanCoverage = (cache.scan_coverage as Record<string, unknown> | undefined) ?? {};
  const coverageDetail = (cache.coverage_detail_summary as Record<string, unknown> | undefined) ?? {};
  const scanExecutionSummary = (cache.scan_execution_summary as Record<string, unknown> | undefined) ?? {};
  const quickScanReceipt = (cache.quick_scan_execution_receipt as Record<string, unknown> | undefined) ?? {};
  const fastScanTaskPipeline = (cache.fast_scan_task_pipeline_contract as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionReceipt = (cache.search_quant_projection_receipt as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionActivation = (cache.search_quant_projection_activation_receipt as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionAcceptanceDryRun = (cache.search_quant_projection_acceptance_dry_run_receipt as Record<string, unknown> | undefined) ?? {};
  const searchQuantProjectionExecutionRequest = (cache.search_quant_projection_execution_request_receipt as Record<string, unknown> | undefined) ?? {};
  const providerParityDryRun = (cache.provider_parity_dry_run_receipt as Record<string, unknown> | undefined) ?? {};
  const fastScanRuntimeBudget = (cache.fast_scan_runtime_budget_contract as Record<string, unknown> | undefined) ?? {};
  const fastScanReadinessAudit = (cache.fast_scan_readiness_audit as Record<string, unknown> | undefined) ?? {};
  const noFeatureLossAcceptance = (cache.no_feature_loss_acceptance_contract as Record<string, unknown> | undefined) ?? {};
  const replacementGapTriage = (cache.replacement_gap_triage_contract as Record<string, unknown> | undefined) ?? {};
  const promotionBlockerAudit = (cache.candidate_radar_promotion_blocker_audit as Record<string, unknown> | undefined) ?? {};
  const activationReceipt = (cache.candidate_radar_production_activation_receipt as Record<string, unknown> | undefined) ?? {};
  const nextExecutionRecipe = (cache.candidate_radar_next_execution_recipe as Record<string, unknown> | undefined) ?? {};
  const workerExecutionRecipe = (cache.candidate_radar_worker_execution_recipe as Record<string, unknown> | undefined) ?? {};
  const workerExecutionRequest = (cache.candidate_radar_worker_execution_request_receipt as Record<string, unknown> | undefined) ?? {};
  const fullPoolWorkerFallback = (cache.candidate_radar_full_pool_worker_fallback_receipt as Record<string, unknown> | undefined) ?? {};
  const deepScanWorkerFallback = (cache.candidate_radar_deep_scan_worker_fallback_receipt as Record<string, unknown> | undefined) ?? {};
  const workerRuntimeLinkedEvidence = (cache.candidate_radar_worker_runtime_linked_evidence as Record<string, unknown> | undefined) ?? {};
  const productionReplacementReview = (cache.candidate_radar_production_replacement_review_receipt as Record<string, unknown> | undefined) ?? {};
  const productionPromotionDryRun = (cache.candidate_radar_production_promotion_dry_run_receipt as Record<string, unknown> | undefined) ?? {};
  const legacyRetirementReview = (cache.candidate_radar_legacy_retirement_review_receipt as Record<string, unknown> | undefined) ?? {};
  const productionPromotionReview = (cache.candidate_radar_production_promotion_review_receipt as Record<string, unknown> | undefined) ?? {};
  const launchQuantProjectionExecutionRequest = () =>
    void postCandidateRadarQuantProjectionExecutionRequest({
      scan_mode: "quant_projection_execution_request",
      operator_approved: true,
      acceptance_scope_hash: String(searchQuantProjectionAcceptanceDryRun.acceptance_scope_hash ?? ""),
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchWorkerExecutionRequest = () =>
    void postCandidateRadarWorkerExecutionRequest({
      scan_mode: "worker_execution_request",
      operator_approved: true,
      worker_execution_scope_hash: String(workerExecutionRecipe.worker_execution_scope_hash ?? ""),
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchFullPoolWorkerFallback = () =>
    void postCandidateRadarFullPoolWorkerScan({
      scan_mode: "full_pool_worker_fallback",
      operator_approved: true,
      worker_execution_scope_hash: String(workerExecutionRequest.worker_execution_scope_hash ?? workerExecutionRecipe.worker_execution_scope_hash ?? ""),
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchDeepScanWorkerFallback = () =>
    void postCandidateRadarDeepScanWorker({
      scan_mode: "deep_scan_worker_fallback",
      operator_approved: true,
      worker_execution_scope_hash: String(workerExecutionRequest.worker_execution_scope_hash ?? workerExecutionRecipe.worker_execution_scope_hash ?? ""),
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchProductionReplacementReview = () =>
    void postCandidateRadarProductionReplacementReview({
      review_scope: "candidate_radar_production_replacement_local_review",
      approved_by_user: true,
      reviewer: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchProductionPromotionDryRun = () =>
    void postCandidateRadarProductionPromotionDryRun({
      promotion_scope: "candidate_radar_production_promotion_local_dry_run",
      operator_approved: true,
      review_scope_hash: String(productionReplacementReview.review_scope_hash ?? ""),
      requested_by: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchLegacyRetirementReview = () =>
    void postCandidateRadarLegacyRetirementReview({
      review_scope: "candidate_radar_legacy_retirement_local_review",
      operator_approved: true,
      reviewer: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchProductionPromotionReview = () =>
    void postCandidateRadarProductionPromotionReview({
      review_scope: "candidate_radar_production_promotion_local_review",
      operator_approved: true,
      promotion_scope_hash: String(productionPromotionDryRun.promotion_scope_hash ?? ""),
      reviewer: "candidate_radar_page"
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const durableEvidenceRecipe = (cache.candidate_radar_durable_evidence_recipe as Record<string, unknown> | undefined) ?? {};
  const productionStageScopeManifest = (cache.candidate_radar_production_stage_scope_manifest as Record<string, unknown> | undefined) ?? {};
  const resultDeltaClarity = (cache.result_delta_clarity_contract as Record<string, unknown> | undefined) ?? {};
  const candidatePriorityExplanation = (cache.candidate_priority_explanation_contract as Record<string, unknown> | undefined) ?? {};
  const browserQaRunbook = (cache.candidate_browser_qa_runbook_contract as Record<string, unknown> | undefined) ?? {};
  const browserQaEvidence = (cache.candidate_browser_qa_evidence_summary as Record<string, unknown> | undefined) ?? {};
  const browserQaReview = (cache.candidate_browser_qa_review_contract as Record<string, unknown> | undefined) ?? {};
  const freshnessState = (cache.freshness_state as Record<string, unknown> | undefined) ?? {};
  const fullPoolPlan = (cache.full_pool_scan_plan as Record<string, unknown> | undefined) ?? {};
  const fullPoolLocalExecutionReceipt = (cache.full_pool_local_execution_receipt as Record<string, unknown> | undefined) ?? {};
  const deepScanPlan = (cache.deep_scan_plan as Record<string, unknown> | undefined) ?? {};
  const deepScanLocalReviewReceipt = (cache.deep_scan_local_review_receipt as Record<string, unknown> | undefined) ?? {};
  const legacyParityInventory = (cache.legacy_parity_inventory as Record<string, unknown> | undefined) ?? {};
  const legacyParityAcceptanceReceipt = (cache.legacy_parity_acceptance_receipt as Record<string, unknown> | undefined) ?? {};
  const localPoolAudit = (cache.local_candidate_pool_audit as Record<string, unknown> | undefined) ?? {};
  const overview = (cache.candidate_execution_evidence_overview as Record<string, unknown> | undefined) ?? {};
  const radarPacket = (cache.radar_packet as Record<string, unknown> | undefined) ?? {};
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);
  const warningRows = cacheWarnings.map((warning, index) => ({ index: index + 1, warning }));
  const legacySignalRows = rows(cache.legacy_signal_group_rows);
  const legacyParityRows = rows(cache.legacy_parity_rows);
  const legacyOutputRows = rows(cache.legacy_output_contract_rows);
  const legacyParityAcceptanceRows = rows(cache.legacy_parity_acceptance_rows);
  const scanModeRows = rows(cache.scan_mode_status_rows);
  const scanAcceptanceRows = rows(cache.scan_acceptance_rows);
  const quickScanReceiptRows = rows(cache.quick_scan_execution_receipt_rows);
  const fastScanTaskPipelineRows = rows(cache.fast_scan_task_pipeline_rows);
  const searchQuantProjectionRows = rows(cache.search_quant_projection_rows);
  const searchQuantProjectionActivationRows = rows(cache.search_quant_projection_activation_rows);
  const searchQuantProjectionAcceptanceDryRunRows = rows(cache.search_quant_projection_acceptance_dry_run_rows);
  const searchQuantProjectionCredentialRows = rows(cache.search_quant_projection_credential_presence_rows);
  const searchQuantProjectionExecutionRequestRows = rows(cache.search_quant_projection_execution_request_rows);
  const providerParityDryRunRows = rows(cache.provider_parity_dry_run_rows);
  const providerParityCredentialRows = rows(cache.provider_parity_credential_presence_rows);
  const fastScanRuntimeBudgetRows = rows(cache.fast_scan_runtime_budget_rows);
  const fastScanReadinessRows = rows(cache.fast_scan_readiness_rows);
  const noFeatureLossAcceptanceRows = rows(cache.no_feature_loss_acceptance_rows);
  const replacementGapTriageRows = rows(cache.replacement_gap_triage_rows);
  const promotionBlockerRows = rows(cache.candidate_radar_promotion_blocker_rows);
  const activationReceiptRows = rows(cache.candidate_radar_production_activation_rows);
  const nextExecutionRecipeRows = rows(cache.candidate_radar_next_execution_rows);
  const workerExecutionRows = rows(cache.candidate_radar_worker_execution_rows);
  const workerExecutionRequestRows = rows(cache.candidate_radar_worker_execution_request_rows);
  const fullPoolWorkerFallbackRows = rows(cache.candidate_radar_full_pool_worker_fallback_rows);
  const deepScanWorkerFallbackRows = rows(cache.candidate_radar_deep_scan_worker_fallback_rows);
  const workerRuntimeLinkedRows = rows(cache.candidate_radar_worker_runtime_link_rows);
  const productionReplacementReviewRows = rows(cache.candidate_radar_production_replacement_review_rows);
  const productionPromotionDryRunRows = rows(cache.candidate_radar_production_promotion_dry_run_rows);
  const legacyRetirementReviewRows = rows(cache.candidate_radar_legacy_retirement_review_rows);
  const productionPromotionReviewRows = rows(cache.candidate_radar_production_promotion_review_rows);
  const durableEvidenceRows = rows(cache.candidate_radar_durable_evidence_rows);
  const productionStageScopeRows = rows(cache.candidate_radar_production_stage_scope_rows);
  const resultDeltaClarityRows = rows(cache.result_delta_clarity_rows);
  const previousCacheDiffRows = rows(cache.previous_cache_diff_rows);
  const candidatePriorityExplanationRows = rows(cache.candidate_priority_explanation_rows);
  const browserQaRunbookRows = rows(cache.candidate_browser_qa_runbook_rows);
  const browserQaMatrixRows = rows(cache.candidate_browser_qa_matrix_rows);
  const browserQaEvidenceRows = rows(cache.candidate_browser_qa_evidence_rows);
  const browserQaReviewRows = rows(cache.candidate_browser_qa_review_rows);
  const providerCoverageRows = rows(cache.provider_coverage_rows);
  const degradedModeRows = rows(cache.degraded_mode_rows);
  const bootstrapLiveLight = (bootstrapStatus.live_light as Record<string, unknown> | undefined) ?? {};
  const bootstrapModeRows = rows(bootstrapStatus.mode_rows);
  const bootstrapConfigRows = rows(bootstrapStatus.config_rows);
  const bootstrapProviderLinkageRows = rows(bootstrapStatus.provider_linkage_rows);
  const bootstrapActivationReceipt = (bootstrapStatus.live_light_activation_receipt as Record<string, unknown> | undefined) ?? {};
  const bootstrapWarningRows = bootstrapEnvelopeWarnings.map((warning, index) => ({ index: index + 1, warning }));
  const fullPoolStageRows = rows(cache.full_pool_plan_stage_rows);
  const fullPoolFilterRows = rows(cache.full_pool_plan_filter_rows);
  const fullPoolSignalRows = rows(cache.full_pool_required_signal_rows);
  const fullPoolBlockerRows = rows(cache.full_pool_blocker_rows);
  const fullPoolLocalExecutionRows = rows(cache.full_pool_local_execution_rows);
  const deepScanStageRows = rows(cache.deep_scan_stage_rows);
  const deepScanParityRows = rows(cache.deep_scan_parity_rows);
  const deepScanSignalRows = rows(cache.deep_scan_required_signal_rows);
  const deepScanBlockerRows = rows(cache.deep_scan_blocker_rows);
  const deepScanLocalReviewRows = rows(cache.deep_scan_local_review_rows);
  const radarMotionState = [
    String(cache.status ?? "cache_missing"),
    String(cache.scan_mode ?? "no_scan_mode"),
    Number(scanCoverage.missing_signal_group_count ?? 0) ? "coverage_gap" : "coverage_ok",
    Number(counts.provider_blocked_group_count ?? 0) ? "provider_blocked" : "provider_clear",
    Number(counts.result_delta_clarity_visible_gap_count ?? 0) ? "result_delta_gap" : "result_delta_clear",
    Number(counts.degraded_mode_active_count ?? 0) ? "degraded" : "steady"
  ].join(" ");

  return (
    <>
      <div className="page-head">
        <h1>候选雷达</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "runtime mode", value: String(bootstrapStatus.mode ?? "cache_only"), tone: bootstrapStatus.mode === "live_light" ? "warn" : "good" },
          { label: "live_light", value: bootstrapLiveLight.enabled === true ? "enabled" : "off", tone: bootstrapLiveLight.enabled === true ? "warn" : "good" },
          { label: "auto Tushare", value: bootstrapLiveLight.tushare_on_open === true ? "on" : "off", tone: bootstrapLiveLight.tushare_on_open === true ? "warn" : "good" },
          { label: "auto DeepSeek", value: bootstrapLiveLight.deepseek_on_open === true ? "on" : "off", tone: bootstrapLiveLight.deepseek_on_open === true ? "warn" : "good" },
          { label: "bootstrap task", value: bootstrapLiveLight.bootstrap_task_implemented === true ? "ready" : "pending", tone: bootstrapLiveLight.bootstrap_task_implemented === true ? "good" : "warn" },
          { label: "候选数", value: counts.candidate_count as number | undefined },
          { label: "可准备", value: counts.ready_count as number | undefined },
          { label: "只观察", value: counts.observe_count as number | undefined },
          { label: "待验证", value: counts.verify_count as number | undefined },
          { label: "scan mode", value: String(cache.scan_mode ?? "--") },
          { label: "scan family", value: String(scanExecutionSummary.scan_family ?? "--") },
          { label: "quick receipt", value: String(quickScanReceipt.status ?? "missing"), tone: quickScanReceipt.local_quick_scan_receipt_ready === true ? "good" : "warn" },
          { label: "task pipeline", value: String(fastScanTaskPipeline.status ?? "missing"), tone: fastScanTaskPipeline.local_task_pipeline_ready === true ? "good" : "warn" },
          { label: "pipeline blockers", value: counts.fast_scan_task_pipeline_production_blocker_count as number | undefined, tone: Number(counts.fast_scan_task_pipeline_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "receipt blockers", value: counts.quick_scan_receipt_production_blocker_count as number | undefined, tone: Number(counts.quick_scan_receipt_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "receipt provider", value: counts.quick_scan_receipt_provider_gap_count as number | undefined, tone: Number(counts.quick_scan_receipt_provider_gap_count ?? 0) ? "warn" : "good" },
          { label: "receipt rows", value: counts.quick_scan_receipt_row_count as number | undefined },
          { label: "quant projection", value: String(searchQuantProjectionReceipt.status ?? "missing"), tone: searchQuantProjectionReceipt.symbol_valid === true ? "good" : "warn" },
          { label: "quant symbol", value: String(searchQuantProjectionReceipt.symbol ?? "--") },
          { label: "quant blockers", value: counts.search_quant_projection_production_blocker_count as number | undefined, tone: Number(counts.search_quant_projection_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "quant rows", value: counts.search_quant_projection_row_count as number | undefined },
          { label: "quant activation", value: String(searchQuantProjectionActivation.status ?? "missing"), tone: searchQuantProjectionActivation.local_activation_receipt_ready === true ? "good" : "warn" },
          { label: "quant activation blockers", value: counts.search_quant_projection_activation_blocker_count as number | undefined, tone: Number(counts.search_quant_projection_activation_blocker_count ?? 0) ? "warn" : "good" },
          { label: "quant dry-run", value: String(searchQuantProjectionAcceptanceDryRun.status ?? "missing"), tone: searchQuantProjectionAcceptanceDryRun.ready_for_user_approved_real_acceptance === true ? "good" : "warn" },
          { label: "dry-run blockers", value: counts.search_quant_projection_acceptance_dry_run_blocking_count as number | undefined, tone: Number(counts.search_quant_projection_acceptance_dry_run_blocking_count ?? 0) ? "warn" : "good" },
          { label: "credential missing", value: counts.search_quant_projection_acceptance_credential_missing_count as number | undefined, tone: Number(counts.search_quant_projection_acceptance_credential_missing_count ?? 0) ? "warn" : "good" },
          { label: "quant request", value: String(searchQuantProjectionExecutionRequest.status ?? "missing"), tone: searchQuantProjectionExecutionRequest.local_execution_request_ready === true ? "good" : "warn" },
          { label: "quant request blockers", value: counts.search_quant_projection_execution_request_local_blocker_count as number | undefined, tone: Number(counts.search_quant_projection_execution_request_local_blocker_count ?? 0) ? "warn" : "good" },
          { label: "quant request prod", value: counts.search_quant_projection_execution_request_production_blocker_count as number | undefined, tone: Number(counts.search_quant_projection_execution_request_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "provider parity", value: String(providerParityDryRun.status ?? "missing"), tone: providerParityDryRun.ready_for_user_approved_provider_parity === true ? "good" : "warn" },
          { label: "parity blockers", value: counts.provider_parity_dry_run_blocking_count as number | undefined, tone: Number(counts.provider_parity_dry_run_blocking_count ?? 0) ? "warn" : "good" },
          { label: "parity symbols", value: counts.provider_parity_candidate_symbol_count as number | undefined },
          { label: "parity credential", value: counts.provider_parity_credential_missing_count as number | undefined, tone: Number(counts.provider_parity_credential_missing_count ?? 0) ? "warn" : "good" },
          { label: "fast readiness", value: String(fastScanReadinessAudit.status ?? "missing"), tone: fastScanReadinessAudit.local_fast_scan_ready === true ? "good" : "warn" },
          { label: "fast blockers", value: counts.fast_scan_readiness_blocker_count as number | undefined, tone: Number(counts.fast_scan_readiness_blocker_count ?? 0) ? "bad" : "good" },
          { label: "no-loss QA", value: String(noFeatureLossAcceptance.status ?? "missing"), tone: noFeatureLossAcceptance.local_no_feature_loss_contract_ready === true ? "good" : "warn" },
          { label: "no-loss gaps", value: counts.no_feature_loss_visible_gap_count as number | undefined, tone: Number(counts.no_feature_loss_visible_gap_count ?? 0) ? "warn" : "good" },
          { label: "radar prod blockers", value: counts.no_feature_loss_production_blocker_count as number | undefined, tone: Number(counts.no_feature_loss_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "retire gate", value: String(replacementGapTriage.status ?? "missing"), tone: replacementGapTriage.legacy_retirement_ready === true ? "good" : "warn" },
          { label: "retire blockers", value: counts.replacement_gap_triage_blocking_count as number | undefined, tone: Number(counts.replacement_gap_triage_blocking_count ?? 0) ? "warn" : "good" },
          { label: "critical gaps", value: counts.replacement_gap_triage_critical_count as number | undefined, tone: Number(counts.replacement_gap_triage_critical_count ?? 0) ? "bad" : "good" },
          { label: "promotion gate", value: String(promotionBlockerAudit.status ?? "missing"), tone: promotionBlockerAudit.promotion_ready === true ? "good" : "warn" },
          { label: "promotion blockers", value: counts.candidate_radar_promotion_blocking_count as number | undefined, tone: Number(counts.candidate_radar_promotion_blocking_count ?? 0) ? "warn" : "good" },
          { label: "provider blockers", value: counts.candidate_radar_promotion_provider_blocker_count as number | undefined, tone: Number(counts.candidate_radar_promotion_provider_blocker_count ?? 0) ? "warn" : "good" },
          { label: "worker blockers", value: counts.candidate_radar_promotion_worker_blocker_count as number | undefined, tone: Number(counts.candidate_radar_promotion_worker_blocker_count ?? 0) ? "warn" : "good" },
          { label: "activation receipt", value: String(activationReceipt.status ?? "missing"), tone: activationReceipt.local_activation_receipt_ready === true ? "good" : "warn" },
          { label: "activation blockers", value: counts.candidate_radar_activation_blocker_count as number | undefined, tone: Number(counts.candidate_radar_activation_blocker_count ?? 0) ? "warn" : "good" },
          { label: "activation pending", value: counts.candidate_radar_activation_pending_evidence_count as number | undefined, tone: Number(counts.candidate_radar_activation_pending_evidence_count ?? 0) ? "warn" : "good" },
          { label: "next recipe", value: String(nextExecutionRecipe.status ?? "missing"), tone: nextExecutionRecipe.recipe_ready_for_user_fast_scan === true ? "good" : "warn" },
          { label: "recipe blockers", value: counts.candidate_radar_next_execution_blocker_count as number | undefined, tone: Number(counts.candidate_radar_next_execution_blocker_count ?? 0) ? "warn" : "good" },
          { label: "recipe pending", value: counts.candidate_radar_next_execution_production_pending_count as number | undefined, tone: Number(counts.candidate_radar_next_execution_production_pending_count ?? 0) ? "warn" : "good" },
          { label: "worker recipe", value: String(workerExecutionRecipe.status ?? "missing"), tone: workerExecutionRecipe.local_worker_execution_recipe_ready === true ? "good" : "warn" },
          { label: "worker recipe blockers", value: counts.candidate_radar_worker_execution_recipe_production_blocker_count as number | undefined, tone: Number(counts.candidate_radar_worker_execution_recipe_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "worker request", value: String(workerExecutionRequest.status ?? "missing"), tone: workerExecutionRequest.local_execution_request_ready === true ? "good" : "warn" },
          { label: "request blockers", value: counts.candidate_radar_worker_execution_request_local_blocker_count as number | undefined, tone: Number(counts.candidate_radar_worker_execution_request_local_blocker_count ?? 0) ? "warn" : "good" },
          { label: "full fallback", value: String(fullPoolWorkerFallback.status ?? "missing"), tone: fullPoolWorkerFallback.local_worker_fallback_full_pool_done === true ? "good" : "warn" },
          { label: "full fallback blockers", value: counts.candidate_radar_full_pool_worker_fallback_local_blocker_count as number | undefined, tone: Number(counts.candidate_radar_full_pool_worker_fallback_local_blocker_count ?? 0) ? "warn" : "good" },
          { label: "deep fallback", value: String(deepScanWorkerFallback.status ?? "missing"), tone: deepScanWorkerFallback.local_worker_fallback_deep_scan_done === true ? "good" : "warn" },
          { label: "deep fallback blockers", value: counts.candidate_radar_deep_scan_worker_fallback_local_blocker_count as number | undefined, tone: Number(counts.candidate_radar_deep_scan_worker_fallback_local_blocker_count ?? 0) ? "warn" : "good" },
          { label: "worker runtime link", value: String(workerRuntimeLinkedEvidence.status ?? "missing"), tone: workerRuntimeLinkedEvidence.worker_runtime_local_evidence_linked === true ? "good" : "warn" },
          { label: "runtime link blockers", value: counts.candidate_radar_worker_runtime_link_production_blocker_count as number | undefined, tone: Number(counts.candidate_radar_worker_runtime_link_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "replacement review", value: String(productionReplacementReview.status ?? "missing"), tone: productionReplacementReview.local_review_ready === true ? "good" : "warn" },
          { label: "review blockers", value: counts.candidate_radar_production_replacement_review_production_blocker_count as number | undefined, tone: Number(counts.candidate_radar_production_replacement_review_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "promotion dry-run", value: String(productionPromotionDryRun.status ?? "missing"), tone: productionPromotionDryRun.ready_for_local_promotion_review === true ? "good" : "warn" },
          { label: "promotion blockers", value: counts.candidate_radar_production_promotion_dry_run_production_blocker_count as number | undefined, tone: Number(counts.candidate_radar_production_promotion_dry_run_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "durable recipe", value: String(durableEvidenceRecipe.status ?? "missing"), tone: durableEvidenceRecipe.local_recipe_ready === true ? "good" : "warn" },
          { label: "durable blockers", value: counts.candidate_radar_durable_evidence_blocker_count as number | undefined, tone: Number(counts.candidate_radar_durable_evidence_blocker_count ?? 0) ? "warn" : "good" },
          { label: "stage manifest", value: String(productionStageScopeManifest.status ?? "missing"), tone: productionStageScopeManifest.local_manifest_ready === true ? "good" : "warn" },
          { label: "stage direct", value: counts.candidate_radar_production_stage_scope_direct_evidence_count as number | undefined, tone: Number(counts.candidate_radar_production_stage_scope_direct_evidence_count ?? 0) ? "good" : "warn" },
          { label: "stage pending", value: counts.candidate_radar_production_stage_scope_pending_count as number | undefined, tone: Number(counts.candidate_radar_production_stage_scope_pending_count ?? 0) ? "warn" : "good" },
          { label: "delta clarity", value: String(resultDeltaClarity.status ?? "missing"), tone: resultDeltaClarity.local_result_delta_clarity_ready === true ? "good" : "warn" },
          { label: "delta gaps", value: counts.result_delta_clarity_visible_gap_count as number | undefined, tone: Number(counts.result_delta_clarity_visible_gap_count ?? 0) ? "warn" : "good" },
          { label: "delta pending", value: counts.result_delta_clarity_pending_count as number | undefined, tone: Number(counts.result_delta_clarity_pending_count ?? 0) ? "warn" : "good" },
          { label: "prev diff", value: resultDeltaClarity.previous_cache_diff_done === true ? "done" : "pending", tone: resultDeltaClarity.previous_cache_diff_done === true ? "good" : "warn" },
          { label: "browser QA", value: String(browserQaRunbook.status ?? "missing"), tone: browserQaRunbook.local_runbook_ready === true ? "good" : "warn" },
          { label: "QA matrix", value: browserQaRunbook.qa_matrix_count as number | undefined },
          { label: "visual QA done", value: browserQaRunbook.visual_qa_complete === true ? "done" : "pending", tone: browserQaRunbook.visual_qa_complete === true ? "bad" : "good" },
          { label: "radar QA evidence", value: String(browserQaEvidence.status ?? "missing"), tone: browserQaEvidence.local_browser_qa_evidence_found === true ? "good" : "warn" },
          { label: "radar QA rows", value: counts.candidate_browser_qa_evidence_row_count as number | undefined },
          { label: "motion coverage", value: browserQaEvidence.motion_viewport_coverage_complete === true ? "complete" : "missing", tone: browserQaEvidence.motion_viewport_coverage_complete === true ? "good" : "warn" },
          { label: "default viewports", value: browserQaEvidence.default_motion_viewport_count as number | undefined },
          { label: "reduced viewports", value: browserQaEvidence.reduced_motion_viewport_count as number | undefined },
          { label: "QA review rows", value: counts.candidate_browser_qa_evidence_review_required_count as number | undefined, tone: Number(counts.candidate_browser_qa_evidence_review_required_count ?? 0) ? "warn" : "good" },
          { label: "QA review", value: String(browserQaReview.status ?? "missing"), tone: browserQaReview.local_browser_qa_review_ready === true ? "good" : "warn" },
          { label: "review blockers", value: counts.candidate_browser_qa_review_blocking_count as number | undefined, tone: Number(counts.candidate_browser_qa_review_blocking_count ?? 0) ? "warn" : "good" },
          { label: "added", value: counts.result_delta_added_count as number | undefined },
          { label: "removed", value: counts.result_delta_removed_count as number | undefined },
          { label: "rank delta", value: counts.result_delta_rank_changed_count as number | undefined },
          { label: "priority explain", value: String(candidatePriorityExplanation.status ?? "missing"), tone: candidatePriorityExplanation.priority_explanation_is_not_trade_signal === true ? "good" : "warn" },
          { label: "explain gaps", value: counts.priority_explanation_gap_count as number | undefined, tone: Number(counts.priority_explanation_gap_count ?? 0) ? "warn" : "good" },
          { label: "data-gap visible", value: counts.priority_explanation_data_gap_visible_count as number | undefined, tone: Number(counts.priority_explanation_data_gap_visible_count ?? 0) ? "warn" : "good" },
          { label: "full replacement", value: fastScanReadinessAudit.production_radar_replacement_complete === true ? "完成" : "未完成", tone: fastScanReadinessAudit.production_radar_replacement_complete === true ? "bad" : "good" },
          { label: "universe", value: coverageDetail.universe_size as number | undefined },
          { label: "input rows", value: coverageDetail.candidate_input_count as number | undefined },
          { label: "display cap", value: coverageDetail.candidate_display_limit as number | undefined },
          { label: "truncated", value: coverageDetail.candidate_display_truncated_count as number | undefined, tone: Number(coverageDetail.candidate_display_truncated_count ?? 0) ? "warn" : "good" },
          { label: "worker needed", value: fastScanRuntimeBudget.large_universe_worker_required === true ? "yes" : "no", tone: fastScanRuntimeBudget.large_universe_worker_required === true ? "warn" : "good" },
          { label: "覆盖组", value: scanCoverage.mapped_signal_group_count as number | undefined },
          { label: "缺口组", value: scanCoverage.missing_signal_group_count as number | undefined, tone: scanCoverage.missing_signal_group_count ? "warn" : "good" },
          { label: "provider blocked", value: counts.provider_blocked_group_count as number | undefined, tone: counts.provider_blocked_group_count ? "warn" : "good" },
          { label: "stale inputs", value: counts.stale_input_group_count as number | undefined, tone: counts.stale_input_group_count ? "warn" : "good" },
          { label: "missing provider", value: counts.missing_provider_data_group_count as number | undefined, tone: counts.missing_provider_data_group_count ? "warn" : "good" },
          { label: "degraded modes", value: counts.degraded_mode_active_count as number | undefined, tone: counts.degraded_mode_active_count ? "warn" : "good" },
          { label: "parity gap", value: counts.legacy_parity_gap_count as number | undefined, tone: counts.legacy_parity_gap_count ? "warn" : "good" },
          { label: "parity mapped", value: counts.legacy_parity_mapped_count as number | undefined },
          { label: "parity receipt", value: String(legacyParityAcceptanceReceipt.status ?? "missing"), tone: legacyParityAcceptanceReceipt.local_acceptance_receipt_ready === true ? "good" : "warn" },
          { label: "parity blockers", value: counts.legacy_parity_acceptance_production_blocker_count as number | undefined, tone: Number(counts.legacy_parity_acceptance_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "parity ready", value: counts.legacy_parity_acceptance_ready_count as number | undefined },
          { label: "跳过原因", value: scanCoverage.skipped_reason_count as number | undefined, tone: scanCoverage.skipped_reason_count ? "warn" : "good" },
          { label: "验收行", value: scanAcceptanceRows.length },
          { label: "freshness", value: String(freshnessState.state ?? "unknown"), tone: freshnessState.source === "missing" ? "warn" : "good" },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "市场扫描", value: policy.does_not_scan_market === true ? "不会" : "可能", tone: policy.does_not_scan_market === true ? "good" : "bad" },
          { label: "quick scan", value: policy.quick_scan_reads_cache_only === true ? "本地" : "未知", tone: policy.quick_scan_reads_cache_only === true ? "good" : "warn" },
          { label: "full-pool plan", value: String(fullPoolPlan.status ?? "missing"), tone: fullPoolPlan.status === "full_pool_plan_ready" ? "good" : "neutral" },
          { label: "local full-pool", value: String(fullPoolLocalExecutionReceipt.status ?? "missing"), tone: fullPoolLocalExecutionReceipt.local_full_pool_execution_done === true ? "good" : "warn" },
          { label: "local universe", value: counts.full_pool_local_execution_candidate_count as number | undefined },
          { label: "local prod blockers", value: counts.full_pool_local_execution_production_blocker_count as number | undefined, tone: Number(counts.full_pool_local_execution_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "full-pool done", value: fullPoolPlan.full_pool_scan_done === true ? "完成" : "未执行", tone: fullPoolPlan.full_pool_scan_done === true ? "bad" : "good" },
          { label: "full-pool blockers", value: fullPoolPlan.blocking_issue_count as number | undefined, tone: Number(fullPoolPlan.blocking_issue_count ?? 0) ? "warn" : "good" },
          { label: "deep-scan plan", value: String(deepScanPlan.status ?? "missing"), tone: deepScanPlan.status === "deep_scan_plan_ready" ? "good" : "neutral" },
          { label: "deep local review", value: String(deepScanLocalReviewReceipt.status ?? "missing"), tone: deepScanLocalReviewReceipt.local_deep_scan_review_done === true ? "good" : "warn" },
          { label: "deep review rows", value: counts.deep_scan_local_review_candidate_count as number | undefined },
          { label: "deep prod blockers", value: counts.deep_scan_local_review_production_blocker_count as number | undefined, tone: Number(counts.deep_scan_local_review_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "deep-scan done", value: deepScanPlan.deep_scan_done === true ? "完成" : "未执行", tone: deepScanPlan.deep_scan_done === true ? "bad" : "good" },
          { label: "deep blockers", value: deepScanPlan.blocking_issue_count as number | undefined, tone: Number(deepScanPlan.blocking_issue_count ?? 0) ? "warn" : "good" },
          { label: "feature gaps", value: deepScanPlan.legacy_feature_gap_count as number | undefined, tone: Number(deepScanPlan.legacy_feature_gap_count ?? 0) ? "warn" : "good" },
          { label: "local pool", value: localPoolAudit.normalized_candidate_count as number | undefined },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid radar-result-cluster" data-radar-state={radarMotionState}>
        <PacketCard title="下一票候选池" subtitle="GET /api/candidate-radar/cache 只读读取 radar_packet / next_ticket_candidates" status={String(cache.status ?? "missing")}>
          <p>{String(cache.summary ?? "候选雷达 cache 只读展示。")}</p>
          <p>{String(cache.manual_required_text ?? "页面打开不会自动全市场扫描。")}</p>
          <p>候选不是买入指令；必须经过证据链、触发条件、纪律和仓位预算复核。</p>
          <StateClarityRail
            label="candidate radar visual state"
            state={radarMotionState}
            steps={[
              { label: "cache", state: cache.status === "ready" ? "done" : "waiting", detail: String(cache.status ?? "missing") },
              { label: "coverage", state: Number(scanCoverage.missing_signal_group_count ?? 0) ? "blocked" : "done", detail: String(scanCoverage.missing_signal_group_count ?? 0) },
              { label: "deep plan", state: deepScanPlan.status === "deep_scan_plan_ready" ? "done" : "waiting", detail: String(deepScanPlan.status ?? "missing") },
              { label: "trade guard", state: cache.does_not_execute_trades === false ? "blocked" : "done", detail: "safe" }
            ]}
          />
        </PacketCard>

        <PacketCard title="雷达运行模式分层" subtitle="GET /api/bootstrap/status；雷达页只读展示 cache_only / manual / live_light 边界" status={String(bootstrapStatus.status ?? "cache_only")}>
          <p>runtime mode: {String(bootstrapStatus.mode ?? "cache_only")}；live_light enabled: {String(bootstrapLiveLight.enabled === true)}</p>
          <p>Tushare 自动刷新 / DeepSeek pro 自动解释: {String(bootstrapLiveLight.tushare_on_open === true)} / {String(bootstrapLiveLight.deepseek_on_open === true)}</p>
          <p>symbol_limit / rate_limit_seconds: {String(bootstrapLiveLight.symbol_limit ?? "--")} / {String(bootstrapLiveLight.rate_limit_seconds ?? "--")}</p>
          <p>bootstrap_task_implemented: {String(bootstrapLiveLight.bootstrap_task_implemented === true)}；provider_execution_implemented / model_execution_implemented: {String(bootstrapLiveLight.provider_execution_implemented === true)} / {String(bootstrapLiveLight.model_execution_implemented === true)}</p>
          <p>activation receipt: {String(bootstrapActivationReceipt.status ?? "--")}；雷达页不会直接调用 Tushare、DeepSeek、GitHub，也不会从 render 启动 full-pool 或 deep-scan。</p>
          <DataLineageTable rows={bootstrapModeRows} />
          <DataLineageTable rows={bootstrapConfigRows} />
          <DataLineageTable rows={bootstrapProviderLinkageRows} />
          <DataLineageTable rows={bootstrapEnvelopeLedger} />
          {bootstrapWarningRows.length ? <DataLineageTable rows={bootstrapWarningRows} /> : null}
        </PacketCard>

        <PacketCard title="搜票量化推演" subtitle="POST /api/candidate-radar/quant-projection；本地回执，不调用 Tushare/DeepSeek" status={String(searchQuantProjectionReceipt.status ?? "local_receipt")}>
          <div className="actions">
            <input
              value={searchSymbol}
              onChange={(event) => setSearchSymbol(event.target.value)}
              placeholder="002008.SZ 或 002008"
              aria-label="search quant projection symbol"
            />
            <button onClick={launchQuantProjection}>生成 3.0 量化推演</button>
          </div>
          <p>一键生成量化投研图谱 当前只写本地回执：校验股票代码，列出 Tushare / Factor / Next Session / DeepSeek / ECharts 待补证据。</p>
          <p>symbol: {String(searchQuantProjectionReceipt.symbol ?? "--")}；symbol_valid: {String(searchQuantProjectionReceipt.symbol_valid === true)}；ready_for_real_provider_model_projection: {String(searchQuantProjectionReceipt.ready_for_real_provider_model_projection === true)}</p>
          <p>provider_execution_implemented: {String(searchQuantProjectionReceipt.provider_execution_implemented === true)}；model_execution_implemented: {String(searchQuantProjectionReceipt.model_execution_implemented === true)}；production_quant_projection_complete: {String(searchQuantProjectionReceipt.production_quant_projection_complete === true)}</p>
          <p>tushare_called: {String(searchQuantProjectionReceipt.tushare_called === true)}；deepseek_called: {String(searchQuantProjectionReceipt.deepseek_called === true)}；candidate_is_not_buy_instruction: {String(searchQuantProjectionReceipt.candidate_is_not_buy_instruction !== false)}</p>
          <DataLineageTable rows={objectRow(searchQuantProjectionReceipt)} />
          <DataLineageTable rows={searchQuantProjectionRows} />
        </PacketCard>

        <PacketCard title="Tushare/DeepSeek 联动审查" subtitle="search_quant_projection_activation_receipt / rows；只组织下一步验收，不代表真实外联完成" status={String(searchQuantProjectionActivation.status ?? "missing")}>
          <div className="actions">
            <button onClick={launchQuantProjectionAcceptanceDryRun}>运行联动 dry-run</button>
          </div>
          <p>local_activation_receipt_ready: {String(searchQuantProjectionActivation.local_activation_receipt_ready === true)}</p>
          <p>allowed_next_step: {String(searchQuantProjectionActivation.allowed_next_step ?? "--")}</p>
          <p>ready_for_real_provider_model_projection: {String(searchQuantProjectionActivation.ready_for_real_provider_model_projection === true)}；production_quant_projection_complete: {String(searchQuantProjectionActivation.production_quant_projection_complete === true)}</p>
          <p>provider_execution_implemented: {String(searchQuantProjectionActivation.provider_execution_implemented === true)}；model_execution_implemented: {String(searchQuantProjectionActivation.model_execution_implemented === true)}</p>
          <p>factor_refresh_executed: {String(searchQuantProjectionActivation.factor_refresh_executed === true)}；next_session_refresh_executed: {String(searchQuantProjectionActivation.next_session_refresh_executed === true)}；echarts_payload_refreshed: {String(searchQuantProjectionActivation.echarts_payload_refreshed === true)}</p>
          <p>tushare_called: {String(searchQuantProjectionActivation.tushare_called === true)}；deepseek_called: {String(searchQuantProjectionActivation.deepseek_called === true)}；github_called: {String(searchQuantProjectionActivation.github_called === true)}</p>
          <p>这个收据把真实 Tushare light call_ledger、可选 DeepSeek pro model_ledger、Factor/Next/ECharts 刷新、浏览器非阻塞证据和 promotion review 分层列出；它不会从 render 调 provider，也不会生成交易指令。</p>
          <DataLineageTable rows={objectRow(searchQuantProjectionActivation)} />
          <DataLineageTable rows={searchQuantProjectionActivationRows} />
          <p>search_quant_projection_acceptance_dry_run_receipt: {String(searchQuantProjectionAcceptanceDryRun.status ?? "missing")}；ready_for_user_approved_real_acceptance: {String(searchQuantProjectionAcceptanceDryRun.ready_for_user_approved_real_acceptance === true)}</p>
          <p>acceptance_scope_hash_short: {String(searchQuantProjectionAcceptanceDryRun.acceptance_scope_hash_short ?? "--")}；credential_missing_provider_count: {String(searchQuantProjectionAcceptanceDryRun.credential_missing_provider_count ?? "--")}</p>
          <p>credential_values_read: {String(searchQuantProjectionAcceptanceDryRun.credential_values_read === true)}；credential_values_exposed: {String(searchQuantProjectionAcceptanceDryRun.credential_values_exposed === true)}；env_key_names_included: {String(searchQuantProjectionAcceptanceDryRun.env_key_names_included === true)}</p>
          <DataLineageTable rows={objectRow(searchQuantProjectionAcceptanceDryRun)} />
          <DataLineageTable rows={searchQuantProjectionAcceptanceDryRunRows} />
          <DataLineageTable rows={searchQuantProjectionCredentialRows} />
          <div className="actions">
            <button onClick={launchQuantProjectionExecutionRequest} disabled={!searchQuantProjectionAcceptanceDryRun.acceptance_scope_hash}>
              生成 provider/model execution request
            </button>
          </div>
          <p>search_quant_projection_execution_request_receipt: {String(searchQuantProjectionExecutionRequest.status ?? "missing")}；local_execution_request_ready: {String(searchQuantProjectionExecutionRequest.local_execution_request_ready === true)}</p>
          <p>requested scope matches latest: {String(searchQuantProjectionExecutionRequest.requested_acceptance_scope_hash_matches_latest === true)}；scope: {String(searchQuantProjectionExecutionRequest.acceptance_scope_hash_short ?? "--")}</p>
          <p>target: {String(searchQuantProjectionExecutionRequest.target_provider_model_route ?? "future POST /api/candidate-radar/quant-projection-provider-model-acceptance")}</p>
          <p>provider_model_task_created / dispatched: {String(searchQuantProjectionExecutionRequest.provider_model_task_created === true)} / {String(searchQuantProjectionExecutionRequest.provider_model_task_dispatched === true)}</p>
          <p>provider_execution_implemented / model_execution_implemented: {String(searchQuantProjectionExecutionRequest.provider_execution_implemented === true)} / {String(searchQuantProjectionExecutionRequest.model_execution_implemented === true)}</p>
          <p>factor / next / echarts refreshed: {String(searchQuantProjectionExecutionRequest.factor_refresh_executed === true)} / {String(searchQuantProjectionExecutionRequest.next_session_refresh_executed === true)} / {String(searchQuantProjectionExecutionRequest.echarts_payload_refreshed === true)}</p>
          <p>tushare_called / deepseek_called / github_called: {String(searchQuantProjectionExecutionRequest.tushare_called === true)} / {String(searchQuantProjectionExecutionRequest.deepseek_called === true)} / {String(searchQuantProjectionExecutionRequest.github_called === true)}</p>
          <p>这个 execution request 只绑定 dry-run scope hash 和用户确认；它不创建真实 provider/model task，不调用 Tushare/DeepSeek，不刷新图谱，不生成交易指令。</p>
          <DataLineageTable rows={objectRow(searchQuantProjectionExecutionRequest)} />
          <DataLineageTable rows={searchQuantProjectionExecutionRequestRows} />
        </PacketCard>

        <PacketCard title="雷达 provider parity dry-run" subtitle="POST /api/candidate-radar/provider-parity-dry-run；本地预检，不调用 Tushare/DeepSeek" status={String(providerParityDryRun.status ?? "missing")}>
          <div className="actions">
            <button onClick={launchProviderParityDryRun}>运行雷达 provider parity dry-run</button>
          </div>
          <p>ready_for_user_approved_provider_parity: {String(providerParityDryRun.ready_for_user_approved_provider_parity === true)}；ready_to_execute_real_provider_parity_task: {String(providerParityDryRun.ready_to_execute_real_provider_parity_task === true)}</p>
          <p>candidate_symbol_count: {String(providerParityDryRun.candidate_symbol_count ?? 0)}；provider_coverage_gap_count: {String(providerParityDryRun.provider_coverage_gap_count ?? 0)}；acceptance_scope_hash_short: {String(providerParityDryRun.acceptance_scope_hash_short ?? "--")}</p>
          <p>provider_execution_implemented: {String(providerParityDryRun.provider_execution_implemented === true)}；model_execution_implemented: {String(providerParityDryRun.model_execution_implemented === true)}；production_radar_replacement_complete: {String(providerParityDryRun.production_radar_replacement_complete === true)}</p>
          <p>credential_values_read: {String(providerParityDryRun.credential_values_read === true)}；credential_values_exposed: {String(providerParityDryRun.credential_values_exposed === true)}；env_key_names_included: {String(providerParityDryRun.env_key_names_included === true)}</p>
          <p>这个 dry-run 只把下一票雷达的 provider-backed parity、full-pool worker、deep-scan worker、浏览器性能和 DeepSeek model ledger 验收范围固定住；它不会从 render 调 provider，也不会退掉 legacy fallback。</p>
          <DataLineageTable rows={objectRow(providerParityDryRun)} />
          <DataLineageTable rows={providerParityDryRunRows} />
          <DataLineageTable rows={providerParityCredentialRows} />
        </PacketCard>

        <PacketCard title="快速雷达扫描" subtitle="POST /api/candidate-radar/scan-quick 只读取本地 snapshot/cache" status={String(scanCoverage.coverage_status ?? "cache")}>
          <div className="actions">
            <button onClick={refreshCache}>查看缓存</button>
            <button onClick={launchQuickScan}>运行 quick scan</button>
            <button onClick={launchWatchlistScan}>运行 watchlist scan</button>
          </div>
          <textarea
            value={customPoolText}
            onChange={(event) => setCustomPoolText(event.target.value)}
            placeholder="002008.SZ, 002837.SZ"
            rows={3}
          />
          <div className="actions">
            <button onClick={launchCustomScan}>运行 custom pool scan</button>
            <button onClick={launchFullPoolPlan}>生成 full-pool 计划</button>
            <button onClick={launchFullPoolLocalScan}>运行本地 full-pool</button>
            <button onClick={launchDeepScanPlan}>生成 deep-scan 清单</button>
            <button onClick={launchDeepScanLocalReview}>运行本地 deep review</button>
          </div>
          <TaskLaunchReceipt receipt={taskReceipt} />
          <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
          <p>quick scan 只做本地 cache 快速重建和覆盖缺口标记，不调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>scan_coverage 和 legacy_signal_group_rows 用来确认旧模块下一票雷达能力没有被静默丢失。</p>
          <p>skipped_reason_rows 和 freshness_state 会把缺失、跳过、陈旧或未知输入直接显示出来。</p>
          <p>任务血缘写入 local_candidate_radar_[scan_mode]，GET cache 仍然只读。</p>
          <p>quick_scan_reads_cache_only: {String(policy.quick_scan_reads_cache_only === true)}</p>
          <DataLineageTable rows={objectRow(scanCoverage)} />
        </PacketCard>

        <PacketCard title="执行证据概览" subtitle="候选证据只作补证路线，不生成交易动作" status={String(overview.tone ?? overview.status ?? "cache")}>
          <p>headline: {String(overview.headline ?? "--")}</p>
          <p>stage: {String(overview.stage_text ?? "--")}</p>
          <p>guardrail: {String(overview.decision_guardrail ?? "--")}</p>
        </PacketCard>
      </div>

      <PacketCard title="旧雷达信号组覆盖" subtitle="legacy_signal_group_rows；缺口只报告，不静默降能" status={String(scanCoverage.coverage_status ?? "coverage")}>
        <DataLineageTable rows={legacySignalRows} />
      </PacketCard>

      <PacketCard title="扫描覆盖明细" subtitle="coverage_detail_summary / provider_coverage_rows / degraded_mode_rows；缺失不静默降能" status={String(coverageDetail.degraded_mode_active ? "degraded" : "coverage")}>
        <p>universe size、provider-blocked groups、stale inputs、missing provider data 和 degraded modes 必须显式展示；页面渲染不会补数或触发 full-pool scan。</p>
        <p>missing provider data is reported, not dropped；quick scan 仍是 research-only，不替代 legacy full scan。</p>
        <DataLineageTable rows={objectRow(coverageDetail)} />
        <DataLineageTable rows={providerCoverageRows} />
        <DataLineageTable rows={degradedModeRows} />
      </PacketCard>

      <PacketCard title="扫描执行验收" subtitle="scan_execution_summary / scan_acceptance_rows；区分 cache、local scan 和 plan-only" status={String(scanExecutionSummary.scan_family ?? "audit")}>
        <p>scan_execution_summary 只总结本地执行边界，不证明 full-pool scan 已完成。</p>
        <p>scan_acceptance_rows 把 provider gap、freshness、local pool、full-pool 和交易隔离逐项展示。</p>
        <DataLineageTable rows={objectRow(scanExecutionSummary)} />
        <DataLineageTable rows={scanAcceptanceRows} />
      </PacketCard>

      <PacketCard title="快扫执行回执" subtitle="quick_scan_execution_receipt；把本次 cache/quick/watchlist/custom scan 的覆盖、截断和阻断项集中展示" status={String(quickScanReceipt.status ?? "missing")}>
        <p>local_quick_scan_receipt_ready: {String(quickScanReceipt.local_quick_scan_receipt_ready === true)}</p>
        <p>scan_mode: {String(quickScanReceipt.scan_mode ?? "--")}；scan_family: {String(quickScanReceipt.scan_family ?? "--")}；writes_sqlite_packet: {String(quickScanReceipt.writes_sqlite_packet === true)}</p>
        <p>candidate_input_count: {String(quickScanReceipt.candidate_input_count ?? 0)}；candidate_row_count: {String(quickScanReceipt.candidate_row_count ?? 0)}；truncated: {String(quickScanReceipt.candidate_display_truncated_count ?? 0)}</p>
        <p>provider_gap_count: {String(quickScanReceipt.provider_gap_count ?? 0)}；missing_signal_group_count: {String(quickScanReceipt.missing_signal_group_count ?? 0)}；freshness: {String(quickScanReceipt.freshness_source ?? "missing")}:{String(quickScanReceipt.freshness_state ?? "unknown")}</p>
        <p>production_radar_replacement_complete: {String(quickScanReceipt.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(quickScanReceipt.legacy_retirement_ready === true)}；provider_backed_acceptance_done: {String(quickScanReceipt.provider_backed_acceptance_done === true)}</p>
        <p>这个回执是本地可见性证明：它说明快扫没有静默降能、没有外联、没有改 action；它不等于 full-pool、deep-scan、provider-backed 或浏览器性能验收完成。</p>
        <DataLineageTable rows={objectRow(quickScanReceipt)} />
        <DataLineageTable rows={quickScanReceiptRows} />
      </PacketCard>

      <PacketCard title="快扫任务流水线合同" subtitle="fast_scan_task_pipeline_contract；证明先渲染 cache，再通过 POST task 快扫，失败和缺口都可见" status={String(fastScanTaskPipeline.status ?? "missing")}>
        <p>local_task_pipeline_ready: {String(fastScanTaskPipeline.local_task_pipeline_ready === true)}</p>
        <p>initial_render_nonblocking: {String(fastScanTaskPipeline.initial_render_nonblocking === true)}；post_task_boundary_visible: {String(fastScanTaskPipeline.post_task_boundary_visible === true)}</p>
        <p>task_id_visible: {String(fastScanTaskPipeline.task_id_visible === true)}；task_status_panel_required: {String(fastScanTaskPipeline.task_status_panel_required === true)}</p>
        <p>last_success_cache_fallback_visible: {String(fastScanTaskPipeline.last_success_cache_fallback_visible === true)}；safe_failure_boundary_visible: {String(fastScanTaskPipeline.safe_failure_boundary_visible === true)}</p>
        <p>async_worker_execution_done: {String(fastScanTaskPipeline.async_worker_execution_done === true)}；provider_backed_acceptance_done: {String(fastScanTaskPipeline.provider_backed_acceptance_done === true)}；production_radar_replacement_complete: {String(fastScanTaskPipeline.production_radar_replacement_complete === true)}</p>
        <p>这个合同只证明 3.0 本地快扫流水线形状：页面不等待扫描、按钮发起 POST task、TaskStatusPanel 轮询状态、上次 cache 仍可读、输入预算和 feature gap 可见；它不是 worker 全量扫描、provider-backed parity、浏览器性能或生产替代完成。</p>
        <DataLineageTable rows={objectRow(fastScanTaskPipeline)} />
        <DataLineageTable rows={fastScanTaskPipelineRows} />
      </PacketCard>

      <PacketCard title="快扫运行预算" subtitle="fast_scan_runtime_budget_contract；控制同步展示规模，超限必须可见并转 worker" status={String(fastScanRuntimeBudget.status ?? "missing")}>
        <p>display_candidate_limit: {String(fastScanRuntimeBudget.display_candidate_limit ?? "--")}</p>
        <p>candidate_input_count: {String(fastScanRuntimeBudget.candidate_input_count ?? 0)}</p>
        <p>candidate_display_truncated_count: {String(fastScanRuntimeBudget.candidate_display_truncated_count ?? 0)}</p>
        <p>large_universe_worker_required: {String(fastScanRuntimeBudget.large_universe_worker_required ?? false)}</p>
        <p>browser_performance_trace_done: {String(fastScanRuntimeBudget.browser_performance_trace_done ?? false)}</p>
        <p>快扫预算只限制本地同步展示和输入规范化；超出时报告截断与 worker 边界，不隐藏 provider、freshness 或 legacy parity 缺口。</p>
        <DataLineageTable rows={objectRow(fastScanRuntimeBudget)} />
        <DataLineageTable rows={fastScanRuntimeBudgetRows} />
      </PacketCard>

      <PacketCard title="快扫 readiness 审计" subtitle="fast_scan_readiness_audit / rows；证明本地快扫不阻塞、不静默降能，但不代表 full-pool/deep-scan 完成" status={String(fastScanReadinessAudit.status ?? "missing")}>
        <p>local_fast_scan_ready: {String(fastScanReadinessAudit.local_fast_scan_ready ?? false)}</p>
        <p>production_radar_replacement_complete: {String(fastScanReadinessAudit.production_radar_replacement_complete ?? false)}</p>
        <p>provider_backed_acceptance_done: {String(fastScanReadinessAudit.provider_backed_acceptance_done ?? false)}</p>
        <p>full_pool_scan_done: {String(fastScanReadinessAudit.full_pool_scan_done ?? false)}</p>
        <p>deep_scan_done: {String(fastScanReadinessAudit.deep_scan_done ?? false)}</p>
        <DataLineageTable rows={objectRow(fastScanReadinessAudit)} />
        <DataLineageTable rows={fastScanReadinessRows} />
      </PacketCard>

      <PacketCard title="快扫不降能验收" subtitle="no_feature_loss_acceptance_contract；本地 QA 面可见，但不是生产雷达替代完成" status={String(noFeatureLossAcceptance.status ?? "missing")}>
        <p>local_no_feature_loss_contract_ready: {String(noFeatureLossAcceptance.local_no_feature_loss_contract_ready ?? false)}</p>
        <p>production_radar_replacement_complete: {String(noFeatureLossAcceptance.production_radar_replacement_complete ?? false)}</p>
        <p>legacy_fallback_required: {String(noFeatureLossAcceptance.legacy_fallback_required ?? true)}</p>
        <p>browser_performance_trace_done: {String(noFeatureLossAcceptance.browser_performance_trace_done ?? false)}</p>
        <p>此合同汇总旧信号组、输出字段、provider/freshness 缺口、运行预算、full-pool/deep-scan 边界和交易隔离；gap 可见不等于真实 full-pool/deep-scan/provider-backed 验收完成。</p>
        <DataLineageTable rows={objectRow(noFeatureLossAcceptance)} />
        <DataLineageTable rows={noFeatureLossAcceptanceRows} />
      </PacketCard>

      <PacketCard title="旧雷达退场缺口分诊" subtitle="replacement_gap_triage_contract；分清 critical、pending 和已通过项，仍不是生产替代完成" status={String(replacementGapTriage.status ?? "missing")}>
        <p>legacy_retirement_ready: {String(replacementGapTriage.legacy_retirement_ready ?? false)}</p>
        <p>blocking_gap_count: {String(replacementGapTriage.blocking_gap_count ?? 0)}；critical_gap_count: {String(replacementGapTriage.critical_gap_count ?? 0)}；pending_gap_count: {String(replacementGapTriage.pending_gap_count ?? 0)}</p>
        <p>此分诊只读取本地合同，把旧信号组、输出字段、provider、freshness、浏览器视觉 QA、性能 trace、full/deep worker 执行和交易隔离分层显示；不能当作 full-pool/deep-scan 或 provider-backed 验收。</p>
        <DataLineageTable rows={objectRow(replacementGapTriage)} />
        <DataLineageTable rows={replacementGapTriageRows} />
      </PacketCard>

      <PacketCard title="雷达生产替代阻断审计" subtitle="candidate_radar_promotion_blocker_audit；列出 quick radar 升级为生产替代前必须清掉的阻断项" status={String(promotionBlockerAudit.status ?? "missing")}>
        <p>local_promotion_audit_ready: {String(promotionBlockerAudit.local_promotion_audit_ready === true)}</p>
        <p>promotion_ready: {String(promotionBlockerAudit.promotion_ready === true)}；production_radar_replacement_complete: {String(promotionBlockerAudit.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(promotionBlockerAudit.legacy_retirement_ready === true)}</p>
        <p>blocking_promotion_count: {String(promotionBlockerAudit.blocking_promotion_count ?? 0)}；provider_acceptance_blocker_count: {String(promotionBlockerAudit.provider_acceptance_blocker_count ?? 0)}；worker_execution_blocker_count: {String(promotionBlockerAudit.worker_execution_blocker_count ?? 0)}；browser_evidence_blocker_count: {String(promotionBlockerAudit.browser_evidence_blocker_count ?? 0)}</p>
        <p>full_pool_scan_done: {String(promotionBlockerAudit.full_pool_scan_done === true)}；deep_scan_done: {String(promotionBlockerAudit.deep_scan_done === true)}；provider_backed_acceptance_done: {String(promotionBlockerAudit.provider_backed_acceptance_done === true)}</p>
        <p>此审计只读本地 cache 和合同，把 full-pool、deep-scan、provider-backed、browser QA、freshness 与交易隔离的生产阻断项集中显示；它不会运行扫描、不会调用 provider/model、不会解除旧雷达 fallback。</p>
        <DataLineageTable rows={objectRow(promotionBlockerAudit)} />
        <DataLineageTable rows={promotionBlockerRows} />
      </PacketCard>

      <PacketCard title="雷达生产化激活收据" subtitle="candidate_radar_production_activation_receipt；统一说明下一步可执行验收和仍缺的生产证据" status={String(activationReceipt.status ?? "missing")}>
        <p>local_activation_receipt_ready: {String(activationReceipt.local_activation_receipt_ready === true)}</p>
        <p>allowed_next_step: {String(activationReceipt.allowed_next_step ?? "--")}</p>
        <p>production_radar_replacement_complete: {String(activationReceipt.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(activationReceipt.legacy_retirement_ready === true)}</p>
        <p>full_pool_scan_done: {String(activationReceipt.full_pool_scan_done === true)}；deep_scan_done: {String(activationReceipt.deep_scan_done === true)}；provider_backed_acceptance_done: {String(activationReceipt.provider_backed_acceptance_done === true)}</p>
        <p>pending_evidence_count: {String(activationReceipt.pending_evidence_count ?? 0)}；production_blocker_count: {String(activationReceipt.production_blocker_count ?? 0)}</p>
        <p>此收据只把 full-pool worker、deep-scan worker、provider-backed parity、browser visual/performance 和 legacy retirement 证据串成下一步清单；它不会运行扫描、不会调用 provider/model、不会把候选变成买入指令。</p>
        <DataLineageTable rows={objectRow(activationReceipt)} />
        <DataLineageTable rows={activationReceiptRows} />
      </PacketCard>

      <PacketCard title="雷达下一步执行配方" subtitle="candidate_radar_next_execution_recipe；快扫优先，不降能证据可见，生产替代仍需后续验收" status={String(nextExecutionRecipe.status ?? "missing")}>
        <p>recipe_ready_for_user_fast_scan: {String(nextExecutionRecipe.recipe_ready_for_user_fast_scan === true)}</p>
        <p>allowed_next_step: {String(nextExecutionRecipe.allowed_next_step ?? "resolve_local_candidate_radar_fast_scan_blockers")}</p>
        <p>recommended_fast_scan_route: {String(nextExecutionRecipe.recommended_fast_scan_route ?? "POST /api/candidate-radar/scan-quick")}</p>
        <p>recommended_full_pool_local_route: {String(nextExecutionRecipe.recommended_full_pool_local_route ?? "POST /api/candidate-radar/full-pool-local-scan")}；recommended_deep_scan_local_review_route: {String(nextExecutionRecipe.recommended_deep_scan_local_review_route ?? "POST /api/candidate-radar/deep-scan-local-review")}</p>
        <p>recommended_worker_full_pool_route: {String(nextExecutionRecipe.recommended_worker_full_pool_route ?? "POST /api/candidate-radar/full-pool-worker-scan")}；recommended_worker_deep_scan_route: {String(nextExecutionRecipe.recommended_worker_deep_scan_route ?? "POST /api/candidate-radar/deep-scan-worker")}</p>
        <p>provider/model/browser 验收路线: {String(nextExecutionRecipe.provider_parity_dry_run_route ?? "POST /api/candidate-radar/provider-parity-dry-run")} / {String(nextExecutionRecipe.quant_projection_acceptance_dry_run_route ?? "POST /api/candidate-radar/quant-projection-acceptance-dry-run")} / {String(nextExecutionRecipe.quant_projection_execution_request_route ?? "POST /api/candidate-radar/quant-projection-execution-request")} / {String(nextExecutionRecipe.browser_qa_review_route ?? "POST /api/candidate-radar/browser-qa-review")}</p>
        <p>ready_to_execute_from_cache: {String(nextExecutionRecipe.ready_to_execute_from_cache === true)}；worker_execution_recipe_ready: {String(nextExecutionRecipe.worker_execution_recipe_ready === true)}；worker_execution_implemented: {String(nextExecutionRecipe.worker_execution_implemented === true)}</p>
        <p>production_radar_replacement_complete: {String(nextExecutionRecipe.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(nextExecutionRecipe.legacy_retirement_ready === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(nextExecutionRecipe.tushare_called === true)} / {String(nextExecutionRecipe.deepseek_called === true)} / {String(nextExecutionRecipe.github_called === true)}</p>
        <p>not_allowed_next_steps: {Array.isArray(nextExecutionRecipe.not_allowed_next_steps) ? nextExecutionRecipe.not_allowed_next_steps.join(" / ") : "scan from render / quick scan as production replacement / provider/model calls from render / candidate rows as buy instructions / retire legacy fallback early"}</p>
        <DataLineageTable rows={objectRow(nextExecutionRecipe)} />
        <DataLineageTable rows={nextExecutionRecipeRows} />
      </PacketCard>

      <PacketCard title="雷达 worker 执行配方" subtitle="candidate_radar_worker_execution_recipe；全池/深扫的 future worker 验收路线，不启动 worker、不调用 provider/model" status={String(workerExecutionRecipe.status ?? "missing")}>
        <p>local_worker_execution_recipe_ready: {String(workerExecutionRecipe.local_worker_execution_recipe_ready === true)}</p>
        <p>worker_execution_scope_hash_short: {String(workerExecutionRecipe.worker_execution_scope_hash_short ?? "--")}</p>
        <p>recommended_worker_full_pool_route: {String(workerExecutionRecipe.recommended_worker_full_pool_route ?? "POST /api/candidate-radar/full-pool-worker-scan")}</p>
        <p>recommended_worker_deep_scan_route: {String(workerExecutionRecipe.recommended_worker_deep_scan_route ?? "POST /api/candidate-radar/deep-scan-worker")}</p>
        <p>worker_task_created / worker_execution_implemented: {String(workerExecutionRecipe.worker_task_created === true)} / {String(workerExecutionRecipe.worker_execution_implemented === true)}</p>
        <p>full_pool_scan_done / deep_scan_done / provider_backed_acceptance_done: {String(workerExecutionRecipe.full_pool_scan_done === true)} / {String(workerExecutionRecipe.deep_scan_done === true)} / {String(workerExecutionRecipe.provider_backed_acceptance_done === true)}</p>
        <p>required_storage_datasets: {Array.isArray(workerExecutionRecipe.required_storage_datasets) ? workerExecutionRecipe.required_storage_datasets.join(" / ") : "daily / daily_basic / moneyflow / trade_cal"}</p>
        <p>not_allowed_next_steps: {Array.isArray(workerExecutionRecipe.not_allowed_next_steps) ? workerExecutionRecipe.not_allowed_next_steps.join(" / ") : "start worker from render / treat recipe as execution done / retire legacy early"}</p>
        <p>tushare_called / deepseek_called / github_called: {String(workerExecutionRecipe.tushare_called === true)} / {String(workerExecutionRecipe.deepseek_called === true)} / {String(workerExecutionRecipe.github_called === true)}</p>
        <DataLineageTable rows={objectRow(workerExecutionRecipe)} />
        <DataLineageTable rows={workerExecutionRows} />
      </PacketCard>

      <PacketCard title="雷达 worker 执行申请" subtitle="POST /api/candidate-radar/worker-execution-request；绑定 worker recipe hash，不启动 worker、不执行全池/深扫" status={String(workerExecutionRequest.status ?? "missing")}>
        <div className="actions">
          <button onClick={launchWorkerExecutionRequest} disabled={!workerExecutionRecipe.worker_execution_scope_hash}>
            生成 worker execution request
          </button>
        </div>
        <p>local_execution_request_ready: {String(workerExecutionRequest.local_execution_request_ready === true)}；ready_for_manual_worker_task_submission: {String(workerExecutionRequest.ready_for_manual_worker_task_submission === true)}</p>
        <p>requested hash matches latest: {String(workerExecutionRequest.requested_worker_execution_scope_hash_matches_latest === true)}；scope: {String(workerExecutionRequest.worker_execution_scope_hash_short ?? "--")}</p>
        <p>local full-pool / deep review / provider parity: {String(workerExecutionRequest.local_full_pool_receipt_visible === true)} / {String(workerExecutionRequest.local_deep_scan_review_visible === true)} / {String(workerExecutionRequest.provider_parity_scope_ticket_visible === true)}</p>
        <p>quant projection scope visible: {String(workerExecutionRequest.quant_projection_scope_ticket_visible === true)}</p>
        <p>target: {String(workerExecutionRequest.target_worker_full_pool_route ?? "POST /api/candidate-radar/full-pool-worker-scan")} / {String(workerExecutionRequest.target_worker_deep_scan_route ?? "POST /api/candidate-radar/deep-scan-worker")}</p>
        <p>worker_task_created / worker_task_executed / worker_started: {String(workerExecutionRequest.worker_task_created === true)} / {String(workerExecutionRequest.worker_task_executed === true)} / {String(workerExecutionRequest.worker_started === true)}</p>
        <p>full_pool_scan_done / deep_scan_done / production_replacement: {String(workerExecutionRequest.full_pool_scan_done === true)} / {String(workerExecutionRequest.deep_scan_done === true)} / {String(workerExecutionRequest.production_radar_replacement_complete === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(workerExecutionRequest.tushare_called === true)} / {String(workerExecutionRequest.deepseek_called === true)} / {String(workerExecutionRequest.github_called === true)}</p>
        <p>not_allowed_next_steps: {Array.isArray(workerExecutionRequest.not_allowed_next_steps) ? workerExecutionRequest.not_allowed_next_steps.join(" / ") : "create worker task / start worker / run full-pool or deep-scan / call provider/model / retire legacy fallback"}</p>
        <DataLineageTable rows={objectRow(workerExecutionRequest)} />
        <DataLineageTable rows={workerExecutionRequestRows} />
      </PacketCard>

      <PacketCard title="Full-pool worker fallback" subtitle="POST /api/candidate-radar/full-pool-worker-scan；显式按钮触发的本地 worker-shaped fallback，不启动 Redis/Celery" status={String(fullPoolWorkerFallback.status ?? "missing")}>
        <div className="actions">
          <button onClick={launchFullPoolWorkerFallback} disabled={!workerExecutionRequest.worker_execution_scope_hash}>
            运行 full-pool worker fallback
          </button>
        </div>
        <p>local_worker_fallback_full_pool_done: {String(fullPoolWorkerFallback.local_worker_fallback_full_pool_done === true)}；ready_for_worker_runtime_promotion: {String(fullPoolWorkerFallback.ready_for_worker_runtime_promotion === true)}</p>
        <p>scope match: {String(fullPoolWorkerFallback.requested_worker_execution_scope_hash_matches_latest === true)}；scope: {String(fullPoolWorkerFallback.worker_execution_scope_hash_short ?? "--")}</p>
        <p>candidate_row_count: {String(fullPoolWorkerFallback.candidate_row_count ?? 0)}；local_blocker_count / production_blocker_count: {String(fullPoolWorkerFallback.local_blocker_count ?? 0)} / {String(fullPoolWorkerFallback.production_blocker_count ?? 0)}</p>
        <p>worker_started / celery_worker_started / redis_broker_used: {String(fullPoolWorkerFallback.worker_started === true)} / {String(fullPoolWorkerFallback.celery_worker_started === true)} / {String(fullPoolWorkerFallback.redis_broker_used === true)}</p>
        <p>production_full_pool_scan_done / provider_backed_acceptance_done / legacy_retirement_ready: {String(fullPoolWorkerFallback.production_full_pool_scan_done === true)} / {String(fullPoolWorkerFallback.provider_backed_acceptance_done === true)} / {String(fullPoolWorkerFallback.legacy_retirement_ready === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(fullPoolWorkerFallback.tushare_called === true)} / {String(fullPoolWorkerFallback.deepseek_called === true)} / {String(fullPoolWorkerFallback.github_called === true)}</p>
        <DataLineageTable rows={objectRow(fullPoolWorkerFallback)} />
        <DataLineageTable rows={fullPoolWorkerFallbackRows} />
      </PacketCard>

      <PacketCard title="Deep-scan worker fallback" subtitle="POST /api/candidate-radar/deep-scan-worker；消费本地 deep-scan review，不启动 Redis/Celery/DeepSeek" status={String(deepScanWorkerFallback.status ?? "missing")}>
        <div className="actions">
          <button onClick={launchDeepScanWorkerFallback} disabled={!workerExecutionRequest.worker_execution_scope_hash}>
            运行 deep-scan worker fallback
          </button>
        </div>
        <p>local_worker_fallback_deep_scan_done: {String(deepScanWorkerFallback.local_worker_fallback_deep_scan_done === true)}；ready_for_worker_runtime_promotion: {String(deepScanWorkerFallback.ready_for_worker_runtime_promotion === true)}</p>
        <p>scope match: {String(deepScanWorkerFallback.requested_worker_execution_scope_hash_matches_latest === true)}；scope: {String(deepScanWorkerFallback.worker_execution_scope_hash_short ?? "--")}</p>
        <p>candidate_row_count: {String(deepScanWorkerFallback.candidate_row_count ?? 0)}；local_blocker_count / production_blocker_count: {String(deepScanWorkerFallback.local_blocker_count ?? 0)} / {String(deepScanWorkerFallback.production_blocker_count ?? 0)}</p>
        <p>worker_started / celery_worker_started / redis_broker_used: {String(deepScanWorkerFallback.worker_started === true)} / {String(deepScanWorkerFallback.celery_worker_started === true)} / {String(deepScanWorkerFallback.redis_broker_used === true)}</p>
        <p>production_deep_scan_done / deepseek_model_ledger_complete / legacy_retirement_ready: {String(deepScanWorkerFallback.production_deep_scan_done === true)} / {String(deepScanWorkerFallback.deepseek_model_ledger_complete === true)} / {String(deepScanWorkerFallback.legacy_retirement_ready === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(deepScanWorkerFallback.tushare_called === true)} / {String(deepScanWorkerFallback.deepseek_called === true)} / {String(deepScanWorkerFallback.github_called === true)}</p>
        <DataLineageTable rows={objectRow(deepScanWorkerFallback)} />
        <DataLineageTable rows={deepScanWorkerFallbackRows} />
      </PacketCard>

      <PacketCard title="雷达 worker runtime link" subtitle="candidate_radar_worker_runtime_linked_evidence；只读连接 LTG-06 本地 runtime QA 证据，不启动 worker、不外联" status={String(workerRuntimeLinkedEvidence.status ?? "missing")}>
        <p>worker_runtime_local_evidence_linked: {String(workerRuntimeLinkedEvidence.worker_runtime_local_evidence_linked === true)}；direct layer: {String(workerRuntimeLinkedEvidence.worker_runtime_direct_evidence_layer ?? "--")}</p>
        <p>source packet: {String(workerRuntimeLinkedEvidence.source_packet_key ?? "command_center_3_worker_runtime_qa_execution_packet")}；read status: {String(workerRuntimeLinkedEvidence.source_packet_read_status ?? "missing")}</p>
        <p>execution task: {String(workerRuntimeLinkedEvidence.worker_runtime_execution_task_id ?? "--")}；runtime scope: {String(workerRuntimeLinkedEvidence.worker_runtime_qa_scope_hash_short ?? "--")}</p>
        <p>local fallback / task log / append-only / cross-process: {String(workerRuntimeLinkedEvidence.local_fallback_round_trip_verified === true)} / {String(workerRuntimeLinkedEvidence.task_log_round_trip_verified === true)} / {String(workerRuntimeLinkedEvidence.append_only_worker_log_verified === true)} / {String(workerRuntimeLinkedEvidence.cross_process_task_control_verified === true)}</p>
        <p>scheduler off / provider-model no autoschedule / no-trade: {String(workerRuntimeLinkedEvidence.scheduler_default_off_runtime_verified === true)} / {String(workerRuntimeLinkedEvidence.provider_model_no_autoschedule_boundary_verified === true)} / {String(workerRuntimeLinkedEvidence.no_trade_no_action_boundary_verified === true)}</p>
        <p>production worker / radar replacement / provider-backed: {String(workerRuntimeLinkedEvidence.production_worker_complete === true)} / {String(workerRuntimeLinkedEvidence.production_radar_replacement_complete === true)} / {String(workerRuntimeLinkedEvidence.provider_backed_acceptance_done === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(workerRuntimeLinkedEvidence.tushare_called === true)} / {String(workerRuntimeLinkedEvidence.deepseek_called === true)} / {String(workerRuntimeLinkedEvidence.github_called === true)}</p>
        <p>这个 link 只证明已有 LTG-06 本地 runtime QA 证据可被雷达迁移审查看见；真实 Redis/Celery worker、全池/深扫、provider parity、browser promotion 和 legacy retirement 仍未完成。</p>
        <DataLineageTable rows={objectRow(workerRuntimeLinkedEvidence)} />
        <DataLineageTable rows={workerRuntimeLinkedRows} />
      </PacketCard>

      <PacketCard title="雷达生产替代审查" subtitle="POST /api/candidate-radar/production-replacement-review；汇总快扫、不降能、worker/provider/browser 缺口，不执行外部任务" status={String(productionReplacementReview.status ?? "missing")}>
        <div className="actions">
          <button onClick={launchProductionReplacementReview}>生成 production replacement review</button>
        </div>
        <p>local_review_ready: {String(productionReplacementReview.local_review_ready === true)}；ready_for_production_replacement: {String(productionReplacementReview.ready_for_production_replacement === true)}</p>
        <p>production_radar_replacement_complete: {String(productionReplacementReview.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(productionReplacementReview.legacy_retirement_ready === true)}；legacy_fallback_required: {String(productionReplacementReview.legacy_fallback_required !== false)}</p>
        <p>fast_scan_ready: {String(productionReplacementReview.fast_scan_ready === true)}；no_feature_loss_local_surface_ready: {String(productionReplacementReview.no_feature_loss_local_surface_ready === true)}；legacy_parity_receipt_ready: {String(productionReplacementReview.legacy_parity_receipt_ready === true)}</p>
        <p>local full/deep/full fallback/deep fallback: {String(productionReplacementReview.local_full_pool_receipt_visible === true)} / {String(productionReplacementReview.local_deep_scan_review_visible === true)} / {String(productionReplacementReview.full_pool_worker_fallback_visible === true)} / {String(productionReplacementReview.deep_scan_worker_fallback_visible === true)}；provider scope / worker request / quant request / browser review: {String(productionReplacementReview.provider_parity_scope_ticket_visible === true)} / {String(productionReplacementReview.worker_execution_request_visible === true)} / {String(productionReplacementReview.quant_projection_execution_request_visible === true)} / {String(productionReplacementReview.browser_qa_review_visible === true)}</p>
        <p>worker full/deep / provider backed / DeepSeek ledger / browser promoted: {String(productionReplacementReview.worker_full_pool_execution_done === true)} / {String(productionReplacementReview.worker_deep_scan_execution_done === true)} / {String(productionReplacementReview.provider_backed_acceptance_done === true)} / {String(productionReplacementReview.deepseek_model_ledger_complete === true)} / {String(productionReplacementReview.browser_visual_performance_promoted === true)}</p>
        <p>local_blocker_count / production_blocker_count: {String(productionReplacementReview.local_blocker_count ?? 0)} / {String(productionReplacementReview.production_blocker_count ?? 0)}；review_scope_hash_short: {String(productionReplacementReview.review_scope_hash_short ?? "--")}</p>
        <p>tushare_called / deepseek_called / github_called: {String(productionReplacementReview.tushare_called === true)} / {String(productionReplacementReview.deepseek_called === true)} / {String(productionReplacementReview.github_called === true)}</p>
        <p>这个审查只把 3.0 雷达迁移能不能退旧模块讲清楚：本地快扫可以 ready，但生产替代仍要真实 worker 全池/深扫、provider call ledger、可选 DeepSeek model ledger、浏览器性能和 legacy retirement review。</p>
        <DataLineageTable rows={objectRow(productionReplacementReview)} />
        <DataLineageTable rows={productionReplacementReviewRows} />
      </PacketCard>

      <PacketCard title="雷达 production promotion dry-run" subtitle="POST /api/candidate-radar/production-promotion-dry-run；绑定 replacement review scope，不运行 worker/provider/model/browser" status={String(productionPromotionDryRun.status ?? "missing")}>
        <div className="actions">
          <button onClick={launchProductionPromotionDryRun} disabled={!productionReplacementReview.review_scope_hash}>
            生成 production promotion dry-run
          </button>
        </div>
        <p>ready_for_local_promotion_review: {String(productionPromotionDryRun.ready_for_local_promotion_review === true)}；ready_to_mark_production: {String(productionPromotionDryRun.ready_to_mark_production_radar_replacement_complete === true)}</p>
        <p>review scope match: {String(productionPromotionDryRun.requested_review_scope_hash_matches_latest === true)}；review scope: {String(productionPromotionDryRun.production_replacement_review_scope_hash_short ?? "--")}；promotion scope: {String(productionPromotionDryRun.promotion_scope_hash_short ?? "--")}</p>
        <p>local_blocker_count / production_blocker_count: {String(productionPromotionDryRun.local_blocker_count ?? 0)} / {String(productionPromotionDryRun.production_blocker_count ?? 0)}</p>
        <p>worker full/deep / provider / DeepSeek ledger: {String(productionPromotionDryRun.worker_full_pool_execution_done === true)} / {String(productionPromotionDryRun.worker_deep_scan_execution_done === true)} / {String(productionPromotionDryRun.provider_backed_acceptance_done === true)} / {String(productionPromotionDryRun.deepseek_model_ledger_complete === true)}</p>
        <p>browser promoted / durable evidence / legacy retirement: {String(productionPromotionDryRun.browser_visual_performance_promoted === true)} / {String(productionPromotionDryRun.durable_evidence_complete === true)} / {String(productionPromotionDryRun.legacy_retirement_ready === true)}</p>
        <p>worker_started / provider_model_task / production complete: {String(productionPromotionDryRun.worker_started === true)} / {String(productionPromotionDryRun.creates_provider_model_task === true)} / {String(productionPromotionDryRun.production_radar_replacement_complete === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(productionPromotionDryRun.tushare_called === true)} / {String(productionPromotionDryRun.deepseek_called === true)} / {String(productionPromotionDryRun.github_called === true)}</p>
        <p>这个 dry-run 只把“可以进入提升审查的本地 scope”绑定起来；真实 worker、provider call ledger、DeepSeek model ledger、浏览器 promotion 和 legacy retirement 仍是直接证据缺口。</p>
        <DataLineageTable rows={objectRow(productionPromotionDryRun)} />
        <DataLineageTable rows={productionPromotionDryRunRows} />
      </PacketCard>

      <PacketCard title="雷达 legacy retirement review" subtitle="POST /api/candidate-radar/legacy-retirement-review；审查旧雷达退场边界，不退掉 legacy、不运行外部任务" status={String(legacyRetirementReview.status ?? "missing")}>
        <div className="actions">
          <button onClick={launchLegacyRetirementReview} disabled={!productionPromotionDryRun.promotion_scope_hash}>
            生成 legacy retirement review
          </button>
        </div>
        <p>local_review_ready: {String(legacyRetirementReview.local_review_ready === true)}；ready_to_retire_legacy: {String(legacyRetirementReview.ready_to_retire_legacy === true)}</p>
        <p>legacy_retirement_ready: {String(legacyRetirementReview.legacy_retirement_ready === true)}；legacy_fallback_required: {String(legacyRetirementReview.legacy_fallback_required !== false)}；production_radar_replacement_complete: {String(legacyRetirementReview.production_radar_replacement_complete === true)}</p>
        <p>replacement review / promotion dry-run / durable recipe / stage manifest: {String(legacyRetirementReview.production_replacement_review_ready === true)} / {String(legacyRetirementReview.production_promotion_dry_run_visible === true)} / {String(legacyRetirementReview.durable_evidence_recipe_visible === true)} / {String(legacyRetirementReview.production_stage_manifest_visible === true)}</p>
        <p>worker full/deep / provider / DeepSeek ledger / browser promoted: {String(legacyRetirementReview.worker_full_pool_execution_done === true)} / {String(legacyRetirementReview.worker_deep_scan_execution_done === true)} / {String(legacyRetirementReview.provider_backed_acceptance_done === true)} / {String(legacyRetirementReview.deepseek_model_ledger_complete === true)} / {String(legacyRetirementReview.browser_visual_performance_promoted === true)}</p>
        <p>local_blocker_count / production_blocker_count: {String(legacyRetirementReview.local_blocker_count ?? 0)} / {String(legacyRetirementReview.production_blocker_count ?? 0)}；retirement scope: {String(legacyRetirementReview.retirement_scope_hash_short ?? "--")}</p>
        <p>worker_started / provider_model_task / production complete: {String(legacyRetirementReview.worker_started === true)} / {String(legacyRetirementReview.creates_provider_model_task === true)} / {String(legacyRetirementReview.production_radar_replacement_complete === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(legacyRetirementReview.tushare_called === true)} / {String(legacyRetirementReview.deepseek_called === true)} / {String(legacyRetirementReview.github_called === true)}</p>
        <p>这个 review 只把旧雷达何时可以退场讲清楚；真实 worker/provider/model/browser 证据和发布证据没有完成前，legacy/admin/debug fallback 继续保留。</p>
        <DataLineageTable rows={objectRow(legacyRetirementReview)} />
        <DataLineageTable rows={legacyRetirementReviewRows} />
      </PacketCard>

      <PacketCard title="雷达 production promotion review" subtitle="POST /api/candidate-radar/production-promotion-review；审查 promotion 边界，不运行 worker/provider/model/browser" status={String(productionPromotionReview.status ?? "missing")}>
        <div className="actions">
          <button onClick={launchProductionPromotionReview} disabled={!productionPromotionDryRun.promotion_scope_hash || !legacyRetirementReview.local_review_ready}>
            生成 production promotion review
          </button>
        </div>
        <p>local_review_ready: {String(productionPromotionReview.local_review_ready === true)}；ready_to_mark_production: {String(productionPromotionReview.ready_to_mark_production_radar_replacement_complete === true)}</p>
        <p>promotion scope match: {String(productionPromotionReview.requested_promotion_scope_hash_matches_latest === true)}；promotion scope: {String(productionPromotionReview.promotion_scope_hash_short ?? "--")}；review scope: {String(productionPromotionReview.promotion_review_scope_hash_short ?? "--")}</p>
        <p>replacement review / promotion dry-run / legacy review / durable recipe: {String(productionPromotionReview.production_replacement_review_ready === true)} / {String(productionPromotionReview.production_promotion_dry_run_visible === true)} / {String(productionPromotionReview.legacy_retirement_review_visible === true)} / {String(productionPromotionReview.durable_evidence_recipe_visible === true)}</p>
        <p>worker full/deep / provider / DeepSeek ledger / browser promoted: {String(productionPromotionReview.worker_full_pool_execution_done === true)} / {String(productionPromotionReview.worker_deep_scan_execution_done === true)} / {String(productionPromotionReview.provider_backed_acceptance_done === true)} / {String(productionPromotionReview.deepseek_model_ledger_complete === true)} / {String(productionPromotionReview.browser_visual_performance_promoted === true)}</p>
        <p>local_blocker_count / production_blocker_count: {String(productionPromotionReview.local_blocker_count ?? 0)} / {String(productionPromotionReview.production_blocker_count ?? 0)}</p>
        <p>worker_started / provider_model_task / production complete: {String(productionPromotionReview.worker_started === true)} / {String(productionPromotionReview.creates_provider_model_task === true)} / {String(productionPromotionReview.production_radar_replacement_complete === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(productionPromotionReview.tushare_called === true)} / {String(productionPromotionReview.deepseek_called === true)} / {String(productionPromotionReview.github_called === true)}</p>
        <p>这个 review 只把 LTG-13 promotion 边界写成可审计本地收据；真实 worker/provider/model/browser/release 证据未完成前，不能标记生产替代。</p>
        <DataLineageTable rows={objectRow(productionPromotionReview)} />
        <DataLineageTable rows={productionPromotionReviewRows} />
      </PacketCard>

      <PacketCard title="雷达耐久证据配方" subtitle="candidate_radar_durable_evidence_recipe；生产替代前的直接证据清单，不运行扫描、不外联" status={String(durableEvidenceRecipe.status ?? "missing")}>
        <p>scope: {String(durableEvidenceRecipe.scope ?? "local_candidate_radar_durable_evidence_recipe_no_scan_or_provider_call")}</p>
        <p>local_recipe_ready: {String(durableEvidenceRecipe.local_recipe_ready === true)}；durable_evidence_complete: {String(durableEvidenceRecipe.durable_evidence_complete === true)}；durable_promotion_ready: {String(durableEvidenceRecipe.durable_promotion_ready === true)}</p>
        <p>production_radar_replacement_complete: {String(durableEvidenceRecipe.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(durableEvidenceRecipe.legacy_retirement_ready === true)}；legacy_fallback_required: {String(durableEvidenceRecipe.legacy_fallback_required !== false)}</p>
        <p>full_pool_scan_done / deep_scan_done / provider_backed_acceptance_done: {String(durableEvidenceRecipe.full_pool_scan_done === true)} / {String(durableEvidenceRecipe.deep_scan_done === true)} / {String(durableEvidenceRecipe.provider_backed_acceptance_done === true)}</p>
        <p>browser_visual_performance_reviewed: {String(durableEvidenceRecipe.browser_visual_performance_reviewed === true)}；deepseek_model_ledger_complete: {String(durableEvidenceRecipe.deepseek_model_ledger_complete === true)}</p>
        <p>cache_get_external_calls / react_render_external_calls: {String(durableEvidenceRecipe.cache_get_external_calls === true)} / {String(durableEvidenceRecipe.react_render_external_calls === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(durableEvidenceRecipe.tushare_called === true)} / {String(durableEvidenceRecipe.deepseek_called === true)} / {String(durableEvidenceRecipe.github_called === true)}</p>
        <p>missing_durable_evidence: {Array.isArray(durableEvidenceRecipe.missing_durable_evidence) ? durableEvidenceRecipe.missing_durable_evidence.join(" / ") : "--"}</p>
        <p>not_allowed_next_steps: {Array.isArray(durableEvidenceRecipe.not_allowed_next_steps) ? durableEvidenceRecipe.not_allowed_next_steps.join(" / ") : "quick scan as production replacement / provider calls from render / legacy retirement from local recipe"}</p>
        <DataLineageTable rows={objectRow(durableEvidenceRecipe)} />
        <DataLineageTable rows={durableEvidenceRows} />
      </PacketCard>

      <PacketCard title="雷达生产阶段清单" subtitle="candidate_radar_production_stage_scope_manifest；本地 direct evidence / pending manifest，不执行扫描、不外联" status={String(productionStageScopeManifest.status ?? "missing")}>
        <p>scope: {String(productionStageScopeManifest.scope ?? "local_candidate_radar_production_stage_scope_manifest_no_execution")}</p>
        <p>local_manifest_ready: {String(productionStageScopeManifest.local_manifest_ready === true)}；production_radar_replacement_complete: {String(productionStageScopeManifest.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(productionStageScopeManifest.legacy_retirement_ready === true)}</p>
        <p>stage_key_count / direct_evidence_stage_count / pending_stage_count / local_evidence_stage_count: {String(productionStageScopeManifest.stage_key_count ?? 0)} / {String(productionStageScopeManifest.direct_evidence_stage_count ?? 0)} / {String(productionStageScopeManifest.pending_stage_count ?? 0)} / {String(productionStageScopeManifest.local_evidence_stage_count ?? 0)}</p>
        <p>direct_evidence_stage_keys: {Array.isArray(productionStageScopeManifest.direct_evidence_stage_keys) ? productionStageScopeManifest.direct_evidence_stage_keys.join(" / ") : "--"}</p>
        <p>pending_stage_keys: {Array.isArray(productionStageScopeManifest.pending_stage_keys) ? productionStageScopeManifest.pending_stage_keys.join(" / ") : "--"}</p>
        <p>full_pool_scan_done / deep_scan_done / provider_backed_acceptance_done: {String(productionStageScopeManifest.full_pool_scan_done === true)} / {String(productionStageScopeManifest.deep_scan_done === true)} / {String(productionStageScopeManifest.provider_backed_acceptance_done === true)}</p>
        <p>worker_backed_execution_done / browser_visual_delta_qa_done / durable_ci_evidence_complete: {String(productionStageScopeManifest.worker_backed_execution_done === true)} / {String(productionStageScopeManifest.browser_visual_delta_qa_done === true)} / {String(productionStageScopeManifest.durable_ci_evidence_complete === true)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(productionStageScopeManifest.tushare_called === true)} / {String(productionStageScopeManifest.deepseek_called === true)} / {String(productionStageScopeManifest.github_called === true)}</p>
        <p>not_allowed_next_steps: {Array.isArray(productionStageScopeManifest.not_allowed_next_steps) ? productionStageScopeManifest.not_allowed_next_steps.join(" / ") : "treat stage manifest as execution / provider parity / browser promotion / legacy retirement / buy instruction"}</p>
        <DataLineageTable rows={objectRow(productionStageScopeManifest)} />
        <DataLineageTable rows={productionStageScopeRows} />
      </PacketCard>

      <PacketCard title="雷达结果变化清晰度" subtitle="result_delta_clarity_contract；有上一版持久化 cache 时执行本地 previous-cache diff，浏览器视觉验收仍需单独跑" status={String(resultDeltaClarity.status ?? "missing")}>
        <p>local_result_delta_clarity_ready: {String(resultDeltaClarity.local_result_delta_clarity_ready ?? false)}</p>
        <p>previous_cache_diff_done: {String(resultDeltaClarity.previous_cache_diff_done ?? false)}</p>
        <p>browser_visual_delta_qa_done: {String(resultDeltaClarity.browser_visual_delta_qa_done ?? false)}</p>
        <p>candidate_delta_signature: {String(resultDeltaClarity.candidate_delta_signature ?? "--")}</p>
        <p>previous_candidate_count: {String(resultDeltaClarity.previous_candidate_count ?? 0)}；added: {String(resultDeltaClarity.candidate_added_count ?? 0)}；removed: {String(resultDeltaClarity.candidate_removed_count ?? 0)}；rank_changed: {String(resultDeltaClarity.candidate_rank_changed_count ?? 0)}</p>
        <p>候选数量、截断、跳过原因、provider gap、freshness、scan mode、上一版 diff 和 full/deep 边界必须可见；浏览器视觉 QA 仍是 pending，不能当生产雷达替代完成。</p>
        <DataLineageTable rows={objectRow(resultDeltaClarity)} />
        <DataLineageTable rows={resultDeltaClarityRows} />
        <DataLineageTable rows={previousCacheDiffRows} />
      </PacketCard>

      <PacketCard title="候选优先级说明" subtitle="candidate_priority_explanation_contract；只解释现有缓存排名，不重排、不打新分" status={String(candidatePriorityExplanation.status ?? "missing")}>
        <p>sort_order_source: {String(candidatePriorityExplanation.sort_order_source ?? "existing_candidate_rows_order")}</p>
        <p>explained_candidate_count: {String(candidatePriorityExplanation.explained_candidate_count ?? 0)}；explanation_gap_count: {String(candidatePriorityExplanation.explanation_gap_count ?? 0)}；data_gap_visible_count: {String(candidatePriorityExplanation.data_gap_visible_count ?? 0)}</p>
        <p>uses_existing_rank_only: {String(candidatePriorityExplanation.uses_existing_rank_only === true)}；uses_existing_score_only: {String(candidatePriorityExplanation.uses_existing_score_only === true)}；priority_explanation_is_not_trade_signal: {String(candidatePriorityExplanation.priority_explanation_is_not_trade_signal === true)}</p>
        <p>本面板只说明缓存里的 rank、score、证据摘要、触发/失效条件和 data_gaps；不会重新排序、不会计算 action、不会刷新 provider。</p>
        <DataLineageTable rows={objectRow(candidatePriorityExplanation)} />
        <DataLineageTable rows={candidatePriorityExplanationRows} />
      </PacketCard>

      <PacketCard title="候选雷达浏览器 QA 手册" subtitle="candidate_browser_qa_runbook_contract；复用本地 runner，不打开浏览器、不写 artifact" status={String(browserQaRunbook.status ?? "missing")}>
        <p>route: {String(browserQaRunbook.candidate_route ?? "#candidates")}</p>
        <p>runner: {String(browserQaRunbook.shared_runner_script ?? "scripts/motion_browser_qa_runner.mjs")}</p>
        <p>visual_qa_complete: {String(browserQaRunbook.visual_qa_complete === true)}</p>
        <p>browser_performance_trace_done: {String(browserQaRunbook.browser_performance_trace_done === true)}</p>
        <p>production_radar_replacement_complete: {String(browserQaRunbook.production_radar_replacement_complete === true)}</p>
        <DataLineageTable rows={objectRow(browserQaRunbook)} />
        <DataLineageTable rows={browserQaRunbookRows} />
        <DataLineageTable rows={browserQaMatrixRows} />
      </PacketCard>

      <PacketCard title="候选雷达浏览器 QA 证据" subtitle="candidate_browser_qa_evidence_summary；只读本地 ignored runner 报告，不打开浏览器、不提交截图" status={String(browserQaEvidence.status ?? "missing")}>
        <div className="actions">
          <button onClick={launchBrowserQaReview}>审查 browser QA 本地证据</button>
        </div>
        <p>local_browser_qa_evidence_found: {String(browserQaEvidence.local_browser_qa_evidence_found === true)}</p>
        <p>candidate_visual_qa_evidence_passed: {String(browserQaEvidence.candidate_visual_qa_evidence_passed === true)}</p>
        <p>candidate_browser_performance_evidence_passed: {String(browserQaEvidence.candidate_browser_performance_evidence_passed === true)}</p>
        <p>motion_viewport_coverage_complete: {String(browserQaEvidence.motion_viewport_coverage_complete === true)}</p>
        <p>default_motion_viewports: {Array.isArray(browserQaEvidence.default_motion_viewports) ? browserQaEvidence.default_motion_viewports.join(" / ") : "--"}</p>
        <p>reduced_motion_viewports: {Array.isArray(browserQaEvidence.reduced_motion_viewports) ? browserQaEvidence.reduced_motion_viewports.join(" / ") : "--"}</p>
        <p>missing_default_motion_viewports / missing_reduced_motion_viewports: {Array.isArray(browserQaEvidence.missing_default_motion_viewports) ? browserQaEvidence.missing_default_motion_viewports.join(" / ") : "--"} / {Array.isArray(browserQaEvidence.missing_reduced_motion_viewports) ? browserQaEvidence.missing_reduced_motion_viewports.join(" / ") : "--"}</p>
        <p>review_required_count: {String(browserQaEvidence.review_required_count ?? 0)}</p>
        <p>latest_report_path: {String(browserQaEvidence.latest_report_path ?? "--")}</p>
        <p>production_radar_replacement_complete: {String(browserQaEvidence.production_radar_replacement_complete === true)}</p>
        <p>legacy_retirement_ready: {String(browserQaEvidence.legacy_retirement_ready === true)}</p>
        <p>该证据只说明本机显式 browser runner 的 `#candidates` 路由结果；不会启动服务、不会打开浏览器、不会调用 provider/model/GitHub，也不能替代 full-pool/deep-scan/provider-backed 验收。</p>
        <DataLineageTable rows={objectRow(browserQaEvidence)} />
        <DataLineageTable rows={browserQaEvidenceRows} />
      </PacketCard>

      <PacketCard title="候选雷达 browser QA 审查" subtitle="candidate_browser_qa_review_contract；POST 按钮门控，只审查本地 ignored artifact" status={String(browserQaReview.status ?? "missing")}>
        <p>explicit_review_task_done: {String(browserQaReview.explicit_review_task_done === true)}</p>
        <p>local_browser_qa_review_ready: {String(browserQaReview.local_browser_qa_review_ready === true)}</p>
        <p>blocking_review_count: {String(browserQaReview.blocking_review_count ?? 0)}</p>
        <p>default_motion_passed: {String(browserQaReview.default_motion_passed === true)}；reduced_motion_passed: {String(browserQaReview.reduced_motion_passed === true)}</p>
        <p>motion_viewport_coverage_complete: {String(browserQaReview.motion_viewport_coverage_complete === true)}</p>
        <p>missing_default_motion_viewports / missing_reduced_motion_viewports: {Array.isArray(browserQaReview.missing_default_motion_viewports) ? browserQaReview.missing_default_motion_viewports.join(" / ") : "--"} / {Array.isArray(browserQaReview.missing_reduced_motion_viewports) ? browserQaReview.missing_reduced_motion_viewports.join(" / ") : "--"}</p>
        <p>production_radar_replacement_complete: {String(browserQaReview.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(browserQaReview.legacy_retirement_ready === true)}</p>
        <p>browser QA review 不运行浏览器、不写 artifact、不提交截图；即使本地审查 ready，也不能解除 full-pool/deep-scan/provider-backed 阻断项。</p>
        <DataLineageTable rows={objectRow(browserQaReview)} />
        <DataLineageTable rows={browserQaReviewRows} />
      </PacketCard>

      <PacketCard title="Deep-scan 准备清单" subtitle="POST /api/candidate-radar/deep-scan-plan；只生成不降能验收单，不执行 deep_scan" status={String(deepScanPlan.status ?? "plan_missing")}>
        <p>deep_scan_plan 是 plan-only：不刷新 provider、不调用 DeepSeek、不执行 deep_scan、不生成买入候选、不修改 strategy action。</p>
        <p>feature_loss_gaps_visible: {String(policy.deep_scan_feature_loss_gaps_visible === true)}</p>
        <p>page_render_starts_deep_scan: {String(deepScanPlan.page_render_starts_deep_scan === true)}</p>
        <DataLineageTable rows={objectRow(deepScanPlan)} />
        <DataLineageTable rows={deepScanStageRows} />
        <DataLineageTable rows={deepScanParityRows} />
        <DataLineageTable rows={deepScanSignalRows} />
        <DataLineageTable rows={deepScanBlockerRows} />
      </PacketCard>

      <PacketCard title="Deep-scan 本地审查收据" subtitle="POST /api/candidate-radar/deep-scan-local-review；只审查本地证据和缺口，不调用 DeepSeek" status={String(deepScanLocalReviewReceipt.status ?? "local_review_missing")}>
        <p>local_deep_scan_review_done: {String(deepScanLocalReviewReceipt.local_deep_scan_review_done === true)}；deep_scan_done: {String(deepScanLocalReviewReceipt.deep_scan_done === true)}</p>
        <p>deepseek_called: {String(deepScanLocalReviewReceipt.deepseek_called === true)}；provider_backed_acceptance_done: {String(deepScanLocalReviewReceipt.provider_backed_acceptance_done === true)}</p>
        <p>本地 deep review 只审查候选证据、触发/失效、legacy parity、provider 和 freshness 缺口；不刷新 provider、不调用模型、不生成买入指令。</p>
        <DataLineageTable rows={objectRow(deepScanLocalReviewReceipt)} />
        <DataLineageTable rows={deepScanLocalReviewRows} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="旧雷达 parity inventory" subtitle="legacy_parity_rows；映射、缺口、未来任务必须分清" status={String(legacyParityInventory.status ?? "partial_parity")}>
          <p>quick_scan_is_full_replacement: {String(legacyParityInventory.quick_scan_is_full_replacement === true)}</p>
          <p>slow_paths_are_future_button_tasks: {String(legacyParityInventory.slow_paths_are_future_button_tasks !== false)}</p>
          <DataLineageTable rows={legacyParityRows} />
        </PacketCard>
        <PacketCard title="旧雷达输出合同" subtitle="legacy_output_contract_rows；字段缺失不造假" status="contract">
          <DataLineageTable rows={legacyOutputRows} />
        </PacketCard>
      </div>

      <PacketCard title="旧雷达 parity 验收收据" subtitle="legacy_parity_acceptance_receipt；把旧雷达能力逐项转成 production replacement 前置条件" status={String(legacyParityAcceptanceReceipt.status ?? "missing")}>
        <p>local_acceptance_receipt_ready: {String(legacyParityAcceptanceReceipt.local_acceptance_receipt_ready === true)}</p>
        <p>production_radar_replacement_complete: {String(legacyParityAcceptanceReceipt.production_radar_replacement_complete === true)}；legacy_retirement_ready: {String(legacyParityAcceptanceReceipt.legacy_retirement_ready === true)}；legacy_fallback_required: {String(legacyParityAcceptanceReceipt.legacy_fallback_required !== false)}</p>
        <p>parity_item_count: {String(legacyParityAcceptanceReceipt.parity_item_count ?? 0)}；output_contract_field_count: {String(legacyParityAcceptanceReceipt.output_contract_field_count ?? 0)}；production_ready_count: {String(legacyParityAcceptanceReceipt.production_ready_count ?? 0)}；production_blocker_count: {String(legacyParityAcceptanceReceipt.production_blocker_count ?? 0)}</p>
        <p>full_pool_scan_done: {String(legacyParityAcceptanceReceipt.full_pool_scan_done === true)}；deep_scan_done: {String(legacyParityAcceptanceReceipt.deep_scan_done === true)}；provider_backed_acceptance_done: {String(legacyParityAcceptanceReceipt.provider_backed_acceptance_done === true)}</p>
        <p>这个收据把 Top/Watch/Excluded、证据链、评分维度、触发/失效、持仓对比、候选池来源、扫描过滤、超时回退和手动深研逐项转成验收门槛；gap_reported 不能当不降能完成，不能提前退掉 Streamlit fallback。</p>
        <DataLineageTable rows={objectRow(legacyParityAcceptanceReceipt)} />
        <DataLineageTable rows={legacyParityAcceptanceRows} />
        <DataLineageTable rows={rows(legacyParityAcceptanceReceipt.call_ledger)} />
      </PacketCard>

      <PacketCard title="扫描模式状态" subtitle="scan_mode_status_rows；当前本地实现 quick/watchlist/custom，full pool 仍是未来任务" status="mode">
        <DataLineageTable rows={scanModeRows} />
      </PacketCard>

      <PacketCard title="Full-pool 准备计划" subtitle="POST /api/candidate-radar/full-pool-plan；只生成计划，不扫描全市场" status={String(fullPoolPlan.status ?? "plan_missing")}>
        <p>full_pool_scan_plan 是 plan-only：不刷新 provider、不执行 full_pool_scan、不生成买入候选、不修改 strategy action。</p>
        <p>page_render_starts_full_pool: {String(fullPoolPlan.page_render_starts_full_pool === true)}</p>
        <p>worker_task_required: {String(fullPoolPlan.worker_task_required === true)}</p>
        <DataLineageTable rows={objectRow(fullPoolPlan)} />
        <DataLineageTable rows={fullPoolStageRows} />
        <DataLineageTable rows={fullPoolFilterRows} />
        <DataLineageTable rows={fullPoolSignalRows} />
        <DataLineageTable rows={fullPoolBlockerRows} />
      </PacketCard>

      <PacketCard title="Full-pool 本地执行收据" subtitle="POST /api/candidate-radar/full-pool-local-scan；只消费本地 universe，不代表 provider-backed 全市场验收" status={String(fullPoolLocalExecutionReceipt.status ?? "local_execution_missing")}>
        <p>local_full_pool_execution_done: {String(fullPoolLocalExecutionReceipt.local_full_pool_execution_done === true)}；production_full_pool_scan_done: {String(fullPoolLocalExecutionReceipt.production_full_pool_scan_done === true)}</p>
        <p>provider_backed_acceptance_done: {String(fullPoolLocalExecutionReceipt.provider_backed_acceptance_done === true)}；legacy_retirement_ready: {String(fullPoolLocalExecutionReceipt.legacy_retirement_ready === true)}</p>
        <p>本地 full-pool 只证明显式 POST 消费了本地 universe 并写入 packet；不刷新 provider、不打开模型、不生成买入指令。</p>
        <DataLineageTable rows={objectRow(fullPoolLocalExecutionReceipt)} />
        <DataLineageTable rows={fullPoolLocalExecutionRows} />
      </PacketCard>

      <PacketCard title="本地候选池审计" subtitle="local_candidate_pool_audit；watchlist/custom 只读本地输入" status={String(localPoolAudit.input_source ?? "cache")}>
        <DataLineageTable rows={objectRow(localPoolAudit)} />
        <DataLineageTable rows={rows(cache.local_candidate_pool_skipped_rows)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="跳过原因" subtitle="skipped_reason_rows；缺失和降级不会被隐藏" status="coverage">
          <DataLineageTable rows={rows(cache.skipped_reason_rows)} />
        </PacketCard>
        <PacketCard title="Freshness 状态" subtitle="freshness_state；未知或陈旧只作为 research-only 缺口展示" status={String(freshnessState.state ?? "unknown")}>
          <DataLineageTable rows={objectRow(freshnessState)} />
        </PacketCard>
      </div>

      <PacketCard title="候选列表" subtitle="只读 candidate_rows；不扫描、不排序重算" status="cache">
        <DataLineageTable rows={rows(cache.candidate_rows)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="证据恢复动作" subtitle="只展示后续手动补证路线；不自动执行旧工具" status="recovery">
          <DataLineageTable rows={rows(cache.evidence_recovery_actions)} />
        </PacketCard>
        <PacketCard title="排除候选" subtitle="来自 radar_packet.excluded_candidates；不做交易判断" status="excluded">
          <DataLineageTable rows={rows(cache.excluded_candidates)} />
        </PacketCard>
      </div>

      <PacketCard title="3.0 候选雷达边界" subtitle="cache API 永不外联；扫描必须走后续按钮任务" status="policy">
        <p>本页不会调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不自动下单，不修改 strategy action。</p>
        <p>候选分数只显示本地缓存，不进入 core action，也不改持仓。</p>
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="旧工作台桥接" subtitle="只读 old_workspace_packet_bridge" status="bridge">
          <DataLineageTable rows={objectRow(cache.old_workspace_packet_bridge)} />
        </PacketCard>
        <PacketCard title="雷达 packet 摘要" subtitle="脱敏只读 radar_packet" status={String(radarPacket.status ?? "cache")}>
          <DataLineageTable rows={objectRow(radarPacket)} />
        </PacketCard>
      </div>

      <PacketCard title="调用血缘" subtitle="local_candidate_radar_cache；不外联、不写回" status="lineage">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET candidate envelope call_ledger" subtitle="GET /api/candidate-radar/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheCallLedger} />
      </PacketCard>

      <PacketCard title="GET candidate envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={warningRows} />
      </PacketCard>

      <PacketCard title="原始 candidate radar cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="candidate radar cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
