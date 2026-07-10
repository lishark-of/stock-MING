import { useEffect, useState } from "react";
import { getHealth, getMigrationStatus, postLegacyAuditObservationDryRun, postLtgNextAcceptanceLocalStep, postTushareDeepseekLinkageReview, type TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid, { type MetricItem } from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

const DEFAULT_LTG_QUEUE_SYMBOL = "002008.SZ";

function dateToYyyymmdd(date: Date): string {
  return date.toISOString().slice(0, 10).replace(/-/g, "");
}

function tradeCalWindow() {
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - 730);
  return { start_date: dateToYyyymmdd(start), end_date: dateToYyyymmdd(end) };
}

function localStep(row: Record<string, unknown>, phaseKey: string): Record<string, unknown> {
  const steps = (row.local_step_rows as Array<Record<string, unknown>> | undefined) ?? [];
  return steps.find((step) => step.phase_key === phaseKey) ?? {};
}

function scopeHash(row: Record<string, unknown>, phaseKey: string): string {
  const step = localStep(row, phaseKey);
  return String(step.receipt_scope_hash ?? step.receipt_scope_hash_short ?? "");
}

function scopeHashShort(row: Record<string, unknown>, phaseKey: string): string {
  const step = localStep(row, phaseKey);
  return String(step.receipt_scope_hash_short ?? step.receipt_scope_hash ?? "");
}

function taskId(row: Record<string, unknown>, phaseKey: string): string {
  return String(localStep(row, phaseKey).latest_task_id ?? "");
}

function nextLocalStepPreview(row: Record<string, unknown>): Record<string, unknown> {
  const previews = (row.next_local_step_preview_rows as Array<Record<string, unknown>> | undefined) ?? [];
  return previews[0] ?? {};
}

function stringArray(value: unknown, fallback: Array<string>): Array<string> {
  return Array.isArray(value) && value.every((item) => typeof item === "string")
    ? value as Array<string>
    : fallback;
}

function ordinaryMigrationText(value: unknown, fallback = "--"): string {
  let result = String(value ?? fallback);
  const replacements: Array<[RegExp, string]> = [
    [/LTG-?0?1/gi, "交易日历新鲜度"],
    [/LTG-?0?2/gi, "外部数据接口样本"],
    [/LTG-?0?3/gi, "量化验证"],
    [/LTG-?0?4/gi, "股票池和因子"],
    [/LTG-?0?5/gi, "本地数据存储"],
    [/LTG-?0?6/gi, "后台任务"],
    [/LTG-?0?7/gi, "模型解释治理"],
    [/LTG-?0?8/gi, "次日图谱"],
    [/LTG-?0?9/gi, "桌面打包"],
    [/LTG-?10/gi, "旧入口退场"],
    [/LTG-?11/gi, "测试和发布检查"],
    [/LTG-?12/gi, "交易隔离"],
    [/LTG-?13/gi, "下一票雷达"],
    [/LTG-?14/gi, "动效体验"],
    [/strict closeout/gi, "最终收口"],
    [/direct evidence/gi, "直接证据"],
    [/remote CI/gi, "远端检查"],
    [/release review/gi, "发布复核"],
    [/provider/gi, "外部数据"],
    [/DeepSeek/gi, "模型解释"],
    [/Tushare/gi, "外部数据"],
    [/GitHub/gi, "远端仓库"],
    [/worker/gi, "后台任务"],
    [/cache/gi, "本地缓存"],
    [/ledger/gi, "调用记录"],
    [/packet/gi, "结果包"],
    [/receipt/gi, "回执"],
    [/scope hash/gi, "范围校验"],
    [/payload/gi, "请求范围"],
    [/task[_ -]?id/gi, "任务编号"],
    [/\btask\b/gi, "后台任务"],
    [/blocked/gi, "待处理"],
    [/pending/gi, "等待"],
    [/dry-run/gi, "本地预检"],
    [/execution-request/gi, "执行申请"],
    [/matrix/gi, "检查表"],
    [/sanitizer/gi, "脱敏检查"],
    [/mock/gi, "模拟样本"]
  ];
  for (const [pattern, replacement] of replacements) {
    result = result.replace(pattern, replacement);
  }
  return result
    .replace(/[_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim() || fallback;
}

function releaseGatePublishStatusLabel(value: unknown): string {
  const status = String(value ?? "");
  if (status === "current_head_unpushed_for_remote_ci") return "waiting for push";
  if (status === "current_head_has_no_unpushed_commits_for_remote_ci") return "no unpushed commits";
  return status || "missing";
}

function releaseGatePublishStepLabel(value: unknown): string {
  const step = String(value ?? "");
  if (step === "explicit_user_authorized_push_after_clean_local_gate") return "push after clean gate";
  if (step === "inspect_matching_remote_actions_after_push") return "inspect matching Actions";
  return step || "missing";
}

function ltgNextStepPayload(row: Record<string, unknown>): Record<string, unknown> {
  const route = String(row.next_local_step ?? "");
  if (route === "POST /api/data-health/trade-cal-provider-acceptance-dry-run") {
    return {
      approved_by_user: true,
      apis: ["trade_cal"],
      exchange: ["SSE", "SZSE"],
      ...tradeCalWindow(),
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/data-health/trade-cal-provider-acceptance-execution-request") {
    return {
      approved_by_user: true,
      acceptance_scope_hash_short: scopeHashShort(row, "trade_cal_dry_run_scope_ticket"),
      apis: ["trade_cal"],
      exchange: ["SSE", "SZSE"],
      ...tradeCalWindow(),
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/data-health/trade-cal-provider-acceptance-promotion-review") {
    return {
      approved_by_user: true,
      latest_execution_request_task_id: taskId(row, "trade_cal_execution_request_ticket"),
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/tasks/tushare-provider-target-sample-execution-request") {
    const preview = nextLocalStepPreview(row);
    return {
      operator_approved: true,
      execution_recipe_scope_hash: String(preview.prepared_execution_recipe_scope_hash_short ?? ""),
      target_sample_acceptance_groups: stringArray(preview.prepared_target_sample_acceptance_groups, ["margin_financing"]),
      apis: stringArray(preview.prepared_apis, ["margin_detail"]),
      ts_code: DEFAULT_LTG_QUEUE_SYMBOL,
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/factor-quant/provider-small-pool-dry-run") {
    return {
      approved_by_user: true,
      symbols: [DEFAULT_LTG_QUEUE_SYMBOL, "000001.SZ", "600000.SH", "600519.SH", "300750.SZ"],
      metrics: ["ic", "rank_ic", "icir", "group_return", "top_bottom", "max_drawdown", "neutral_ic", "out_of_sample_decay", "cost_model"],
      forward_return_horizons: ["1d", "5d"],
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/factor-quant/provider-small-pool-execution-request") {
    return {
      approved_by_user: true,
      acceptance_scope_hash: scopeHash(row, "factor_small_pool_dry_run_scope_ticket"),
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/factor-quant/universe-worker-batch-dry-run") {
    return {
      approved_by_user: true,
      universe_mode: "full_pool",
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/factor-quant/universe-worker-batch-execution-request") {
    return {
      approved_by_user: true,
      worker_batch_scope_hash: scopeHash(row, "factor_universe_worker_batch_dry_run_scope_ticket"),
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/factor-quant/universe-worker-batch-research") {
    return {
      approved_by_user: true,
      worker_batch_scope_hash: scopeHash(row, "factor_universe_worker_batch_execution_request_ticket"),
      execution_request_task_id: taskId(row, "factor_universe_worker_batch_execution_request_ticket"),
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/candidate-radar/quant-projection-acceptance-dry-run") {
    return {
      symbol: DEFAULT_LTG_QUEUE_SYMBOL,
      include_tushare: true,
      include_deepseek: true,
      user_approved: true,
      selected_apis: ["trade_cal", "daily", "daily_basic", "moneyflow"],
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/candidate-radar/quant-projection-execution-request") {
    return {
      scan_mode: "quant_projection_execution_request",
      operator_approved: true,
      acceptance_scope_hash: scopeHash(row, "radar_quant_projection_dry_run_scope_ticket"),
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/candidate-radar/provider-parity-dry-run") {
    return {
      candidate_symbols: [DEFAULT_LTG_QUEUE_SYMBOL, "002837.SZ"],
      selected_signal_groups: ["moneyflow", "dragon_tiger", "hard_risk"],
      include_tushare: true,
      include_deepseek: false,
      user_approved: true,
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/candidate-radar/provider-parity-execution-request") {
    return {
      operator_approved: true,
      acceptance_scope_hash: scopeHash(row, "radar_provider_parity_dry_run_scope_ticket"),
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/candidate-radar/worker-execution-request") {
    const preview = nextLocalStepPreview(row);
    return {
      requested_from: "migration_status_ltg_next_action",
      operator_approved: true,
      worker_execution_scope_hash: String(preview.prepared_worker_execution_scope_hash ?? ""),
      provider_parity_scope_hash: String(preview.prepared_provider_parity_scope_hash ?? ""),
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/candidate-radar/full-pool-worker-scan") {
    return {
      scan_mode: "full_pool_worker_fallback",
      operator_approved: true,
      worker_execution_scope_hash: scopeHash(row, "radar_worker_execution_request_ticket"),
      local_universe_candidates: [
        { ticker: DEFAULT_LTG_QUEUE_SYMBOL, name: "migration-status-local-candidate", score: 0 },
        { ticker: "002837.SZ", name: "migration-status-local-candidate", score: 0 }
      ],
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/candidate-radar/deep-scan-worker") {
    return {
      scan_mode: "deep_scan_worker_fallback",
      operator_approved: true,
      worker_execution_scope_hash: scopeHash(row, "radar_full_pool_worker_fallback_receipt"),
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/candidate-radar/production-promotion-dry-run") {
    const preview = nextLocalStepPreview(row);
    return {
      promotion_scope: "candidate_radar_production_promotion_local_dry_run",
      operator_approved: true,
      review_scope_hash: String(preview.prepared_review_scope_hash ?? ""),
      requested_by: "migration_status_ltg_queue",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/storage/backtest-results/schema-seed") {
    return {
      source: "migration_status_ltg_next_action",
      confirm_schema_seed: true,
      target_dataset: "backtest_results",
      write_backtest_rows_allowed: false
    };
  }
  if (route === "POST /api/storage/physical-execution-request") {
    const preview = nextLocalStepPreview(row);
    return {
      source: "migration_status_ltg_next_action",
      approved_by_user: true,
      physical_execution_scope_hash: String(preview.prepared_physical_execution_scope_hash ?? "")
    };
  }
  if (route === "POST /api/worker/synthetic-healthcheck") {
    return {
      requested_from: "migration_status_ltg_next_action",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/worker/activation-review") {
    return {
      requested_from: "migration_status_ltg_next_action",
      operator_approved: true,
      approved_by_user: true,
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/worker/production-evidence-plan") {
    return {
      requested_from: "migration_status_ltg_next_action",
      operator_approved: true,
      approved_by_user: true,
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/worker/runtime-qa-execution-request") {
    const preview = nextLocalStepPreview(row);
    return {
      requested_from: "migration_status_ltg_next_action",
      operator_approved: true,
      evidence_plan_scope_hash: String(preview.prepared_evidence_plan_scope_hash ?? ""),
      runtime_qa_scope_hash: String(preview.prepared_runtime_qa_scope_hash ?? ""),
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/worker/runtime-qa-dry-run") {
    const preview = nextLocalStepPreview(row);
    return {
      requested_from: "migration_status_ltg_next_action",
      operator_approved: true,
      request_task_id: String(preview.prepared_runtime_qa_request_task_id ?? ""),
      evidence_plan_scope_hash: String(preview.prepared_evidence_plan_scope_hash ?? ""),
      runtime_qa_scope_hash: String(preview.prepared_runtime_qa_scope_hash ?? ""),
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/worker/runtime-qa-execution") {
    const preview = nextLocalStepPreview(row);
    return {
      requested_from: "migration_status_ltg_next_action",
      operator_approved: true,
      dry_run_task_id: String(preview.prepared_runtime_qa_dry_run_task_id ?? ""),
      evidence_plan_scope_hash: String(preview.prepared_evidence_plan_scope_hash ?? ""),
      runtime_qa_scope_hash: String(preview.prepared_runtime_qa_scope_hash ?? ""),
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/factor-quant/deepseek-provider-benchmark-scope-ticket") {
    return {
      requested_from: "migration_status_ltg_next_action",
      approved_by_user: true,
      sample_count: 40,
      response_format: "json_schema",
      max_retry_per_sample: 2,
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/next-session/browser-qa-review") {
    return {
      requested_from: "migration_status_ltg_next_action",
      reviewer: "migration_status_ltg_queue",
      review_scope: "next_session_browser_qa_local_artifact",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/audit/motion-browser-qa-review") {
    return {
      requested_from: "migration_status_ltg_next_action",
      reviewer: "migration_status_ltg_queue",
      review_scope: "motion_browser_qa_local_artifact",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/audit/motion-production-promotion-dry-run") {
    return {
      requested_from: "migration_status_ltg_next_action",
      user_approved: true,
      promote_visual: true,
      promote_performance: true,
      promotion_scope: "motion_visual_performance_local_promotion_dry_run",
      source: "migration_status_ltg_next_action"
    };
  }
  if (route === "POST /api/audit/motion-visual-performance-promotion-review") {
    return {
      requested_from: "migration_status_ltg_next_action",
      user_approved: true,
      review_scope: "motion_visual_performance_local_promotion_review",
      source: "migration_status_ltg_next_action"
    };
  }
  return { requested_by: "migration_status_ltg_queue", source: "migration_status_ltg_next_action" };
}

export default function MigrationStatus() {
  const [packet, setPacket] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);
  const [linkageReviewTask, setLinkageReviewTask] = useState<Record<string, unknown>>({});
  const [linkageReviewError, setLinkageReviewError] = useState<string>("");
  const [legacyAuditObservationReceipt, setLegacyAuditObservationReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [legacyAuditObservationTaskId, setLegacyAuditObservationTaskId] = useState("");
  const [legacyAuditObservationError, setLegacyAuditObservationError] = useState("");
  const [ltgNextActionReceipt, setLtgNextActionReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [ltgNextActionTaskId, setLtgNextActionTaskId] = useState("");
  const [ltgNextActionError, setLtgNextActionError] = useState("");
  const [healthReady, setHealthReady] = useState(false);

  useEffect(() => {
    void getHealth().then((res) => {
      setHealthReady(res.ok && String((res.data as Record<string, unknown>)?.status ?? "") === "ok");
    });
    void getMigrationStatus().then((res) => {
      setPacket(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const progress = (packet.progress_baseline as Array<Record<string, unknown>> | undefined) ?? [];
  const longTermGoalRows = (packet.long_term_goal_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const candidateRadarGoalRow = longTermGoalRows.find((row) => row.id === "LTG-13") ?? {};
  const longTermGoalSummary = (packet.long_term_goal_summary as Record<string, unknown> | undefined) ?? {};
  const longTermBucketCounts = (longTermGoalSummary.bucket_counts as Record<string, unknown> | undefined) ?? {};
  const longTermNextPriority = (longTermGoalSummary.next_priority_order as Array<string> | undefined) ?? [];
  const ltgStageScopeObservedRows = (packet.ltg_stage_scope_observed_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const motionGoalObservedRow = ltgStageScopeObservedRows.find((row) => row.id === "LTG-14") ?? {};
  const tradeIsolationGoalObservedRow = ltgStageScopeObservedRows.find((row) => row.id === "LTG-12") ?? {};
  const tushareDeepseekLinkage = (packet.tushare_deepseek_linkage_review as Record<string, unknown> | undefined) ?? {};
  const tushareDeepseekLinkageRows = (packet.tushare_deepseek_linkage_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const tushareDeepseekModeLayerRows = (packet.tushare_deepseek_mode_layer_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const latestTushareDeepseekLinkageReview = (packet.latest_tushare_deepseek_linkage_review as Record<string, unknown> | undefined) ?? {};
  const legacyAuditFirstRoundIntake = (packet.legacy_audit_first_round_intake as Record<string, unknown> | undefined) ?? {};
  const legacyAuditFirstRoundIntakeRows = (packet.legacy_audit_first_round_intake_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const legacyAuditLatestObservation = (packet.legacy_audit_latest_observation as Record<string, unknown> | undefined) ?? {};
  const legacyAuditLatestObservationRows = (packet.legacy_audit_latest_observation_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const legacyAuditFirstRoundRequiredFields = stringArray(legacyAuditFirstRoundIntake.required_fields, []);
  const legacyAuditSafeAttachmentSources = stringArray(legacyAuditFirstRoundIntake.safe_attachment_sources, []);
  const legacyAuditForbiddenAttachmentSources = stringArray(legacyAuditFirstRoundIntake.forbidden_attachment_sources, []);
  const legacyAuditFirstRoundFocusRows = legacyAuditFirstRoundIntakeRows.map((row) => ({
    workflow_group: row.workflow_group,
    allowed_initial_status: row.allowed_initial_status,
    next_action: row.next_action,
    keep_promotion_allowed_this_round: row.keep_promotion_allowed_this_round,
    ordinary_entry_promotion_allowed_this_round: row.ordinary_entry_promotion_allowed_this_round
  }));
  const legacyAuditRequiredFieldRows = legacyAuditFirstRoundRequiredFields.map((field, index) => ({
    field_order: index + 1,
    required_field: field,
    status: "must_collect_before_keep_or_ordinary_entry_review"
  }));
  const legacyAuditAttachmentSourceRows = [
    ...legacyAuditSafeAttachmentSources.map((source) => ({
      source,
      source_type: "safe_reference_allowed",
      raw_content_allowed: false
    })),
    ...legacyAuditForbiddenAttachmentSources.map((source) => ({
      source,
      source_type: "forbidden_raw_or_generated_source",
      raw_content_allowed: false
    }))
  ];
  const linkageReviewPayload = (linkageReviewTask.payload_safe as Record<string, unknown> | undefined) ?? {};
  const postLinkageReviewReceipt = (linkageReviewPayload.tushare_deepseek_linkage_review_receipt as Record<string, unknown> | undefined) ?? {};
  const latestLinkageReviewRows = (packet.latest_tushare_deepseek_linkage_review_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const postLinkageReviewRows = (linkageReviewPayload.tushare_deepseek_linkage_review_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const linkageReviewReceipt = Object.keys(postLinkageReviewReceipt).length ? postLinkageReviewReceipt : latestTushareDeepseekLinkageReview;
  const linkageReviewRows = postLinkageReviewRows.length ? postLinkageReviewRows : latestLinkageReviewRows;
  const principles = Array.isArray(packet.principles) ? packet.principles : [];
  const packetAcceptanceRunwayRows = (packet.ltg_acceptance_runway_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const usablePathCurrentCheckpointRows = (packet.usable_path_current_checkpoint_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const usablePathStrictCloseoutHandoffRows = (packet.usable_path_strict_closeout_handoff_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const p6DirectEvidenceReentryRows = (packet.p6_direct_evidence_reentry_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const releaseGateRemoteReviewSplitSummary = (packet.release_gate_remote_review_split_summary as Record<string, unknown> | undefined) ?? {};
  const releaseGateRemoteReviewSplitRows = (packet.release_gate_remote_review_split_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const releaseGateCurrentHeadPublishStatus = String(releaseGateRemoteReviewSplitSummary.current_head_publish_status ?? "");
  const releaseGateCurrentHeadAheadCount = Number(releaseGateRemoteReviewSplitSummary.current_head_origin_ahead_count ?? releaseGateRemoteReviewSplitSummary.local_push_gate_receipt_current_origin_ahead_count ?? 0);
  const releaseGateCurrentHeadPushRequired = releaseGateRemoteReviewSplitSummary.current_head_push_required_before_remote_review === true;
  const releaseGateRemoteReviewWaitingForPush = releaseGateRemoteReviewSplitSummary.remote_review_waiting_for_current_head_push === true;
  const releaseGateNextPublishStep = String(releaseGateRemoteReviewSplitSummary.next_publish_step ?? "");
  const productionHardeningSummary = (packet.production_hardening_summary as Record<string, unknown> | undefined) ?? {};
  const productionHardeningRows = (packet.production_hardening_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const productionHardeningLtgRows = (packet.production_hardening_ltg_direct_evidence_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const productionHardeningGateSummary = (packet.production_hardening_gate_summary as Record<string, unknown> | undefined) ?? {};
  const productionHardeningGateRows = (packet.production_hardening_gate_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const ltgStrictCloseoutWorkOrderSummary = (packet.ltg_strict_closeout_work_order_summary as Record<string, unknown> | undefined) ?? {};
  const ltgStrictCloseoutWorkOrderRows = (packet.ltg_strict_closeout_work_order_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const ltgStrictCloseoutEvidenceSpineSummary = (packet.ltg_strict_closeout_evidence_spine_summary as Record<string, unknown> | undefined) ?? {};
  const ltgStrictCloseoutEvidenceSpineRows = (packet.ltg_strict_closeout_evidence_spine_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const ltgStrictCloseoutEvidenceSpineReadableRows = ltgStrictCloseoutEvidenceSpineRows.map((row) => ({
    id: row.id,
    handoff_status: row.handoff_visible === true ? "visible" : "missing",
    handoff_count: `${Number(row.handoff_count ?? 0)}/${Number(row.expected_handoff_count ?? 0)}`,
    handoff_keys: Array.isArray(row.handoff_keys) ? row.handoff_keys.join(", ") : "",
    strict_closeout: row.strict_closeout,
    closeout_claim_allowed: row.strict_closeout_claim_allowed,
    remote_review_split_required: row.remote_review_split_required,
    release_review_required: row.requires_release_review_after_remote_green,
    production_complete: row.production_complete,
    external_calls_triggered: row.external_calls_triggered,
    does_not_execute_trades: row.does_not_execute_trades,
    evidence_boundary: row.evidence_boundary
  }));
  const ltgNextAcceptanceActionRows = (packet.ltg_next_acceptance_action_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const ltgNextAcceptanceReceiptRows = ltgNextAcceptanceActionRows.map((row) => ({
    queue_id: row.queue_id,
    priority: row.priority,
    action_label: row.action_label,
    local_receipt_status: row.local_receipt_status,
    observed_steps: row.observed_local_receipt_step_count,
    missing_steps: row.missing_local_receipt_step_count,
    ready_steps: row.ready_local_receipt_step_count,
    blocked_steps: row.blocked_local_receipt_step_count,
    durable_steps: row.durable_local_receipt_step_count,
    memory_only_steps: row.memory_only_local_receipt_step_count,
    all_receipts_durable: row.local_receipts_all_durable,
    next_local_step: row.next_local_step,
    lookup_creates_task: row.local_receipt_lookup_creates_task,
    lookup_calls_provider: row.local_receipt_lookup_calls_provider,
    provider_execution: row.provider_execution_implemented,
    model_execution: row.model_execution_implemented,
    can_close: row.can_close_goal === true
  }));
  const ltgNextAcceptanceLocalStepRows = ltgNextAcceptanceActionRows.flatMap((row) => {
    const localSteps = (row.local_step_rows as Array<Record<string, unknown>> | undefined) ?? [];
    return localSteps.map((step) => ({
      queue_id: row.queue_id,
      priority: row.priority,
      phase_key: step.phase_key,
      route: step.route,
      receipt_visible: step.receipt_visible,
      task_found: step.task_found,
      storage_source: step.latest_task_storage_source,
      receipt_durable_in_sqlite: step.receipt_durable_in_sqlite,
      receipt_memory_only: step.receipt_memory_only,
      receipt_durability_state: step.receipt_durability_state,
      local_ready: step.local_ready,
      local_blocked: step.local_blocked,
      receipt_status: step.receipt_status,
      blocker_count: step.receipt_blocker_count,
      lookup_calls_provider: step.lookup_calls_provider,
      creates_task_from_lookup: step.creates_task_from_lookup
    }));
  });
  const ltgNextAcceptancePreviewRows = ltgNextAcceptanceActionRows.flatMap((row) => {
    const previews = (row.next_local_step_preview_rows as Array<Record<string, unknown>> | undefined) ?? [];
    return previews.map((preview) => ({
      queue_id: row.queue_id,
      priority: row.priority,
      next_local_step: preview.next_local_step,
      step_kind: preview.step_kind,
      ready_for_clean_local_receipt: preview.ready_for_clean_local_receipt,
      disabled_reason: preview.disabled_reason,
      safe_payload_summary: preview.safe_payload_summary,
      required_prior_phase_key: preview.required_prior_phase_key,
      required_prior_material: preview.required_prior_material,
      required_prior_receipt_visible: preview.required_prior_receipt_visible,
      required_prior_material_visible: preview.required_prior_material_visible,
      manual_scope_hash_required: preview.manual_scope_hash_required,
      prepared_execution_recipe_scope_hash_short: preview.prepared_execution_recipe_scope_hash_short,
      prepared_target_sample_acceptance_groups: preview.prepared_target_sample_acceptance_groups,
      prepared_apis: preview.prepared_apis,
      prepared_context_status: preview.prepared_context_status,
      prepared_context_source_packet_key: preview.prepared_context_source_packet_key,
      prepared_context_source_receipt_key: preview.prepared_context_source_receipt_key,
      prepared_review_scope_hash_short: preview.prepared_review_scope_hash_short,
      prepared_physical_execution_scope_hash_short: preview.prepared_physical_execution_scope_hash_short,
      prepared_evidence_plan_scope_hash_short: preview.prepared_evidence_plan_scope_hash_short,
      prepared_runtime_qa_scope_hash_short: preview.prepared_runtime_qa_scope_hash_short,
      prepared_runtime_qa_request_task_id: preview.prepared_runtime_qa_request_task_id,
      prepared_runtime_qa_dry_run_task_id: preview.prepared_runtime_qa_dry_run_task_id,
      would_create_provider_task: preview.would_create_provider_task,
      would_start_worker: preview.would_start_worker,
      would_call_model: preview.would_call_model,
      external_calls_triggered: preview.external_calls_triggered
    }));
  });
  const ltgFutureHandoffPreviewRows = ltgNextAcceptanceActionRows.flatMap((row) => {
    const handoffs = (row.future_handoff_preview_rows as Array<Record<string, unknown>> | undefined) ?? [];
    return handoffs.map((handoff) => ({
      queue_id: row.queue_id,
      priority: row.priority,
      status: handoff.status,
      future_route: handoff.future_route,
      future_task_type: handoff.future_task_type,
      target_acceptance_mode: handoff.target_acceptance_mode,
      target_payload_apis: handoff.target_payload_apis,
      target_payload_groups: handoff.target_payload_groups,
      target_payload_ts_code: handoff.target_payload_ts_code,
      target_payload_trade_date: handoff.target_payload_trade_date,
      target_payload_start_date: handoff.target_payload_start_date,
      target_payload_end_date: handoff.target_payload_end_date,
      source_local_phase_key: handoff.source_local_phase_key,
      source_local_task_id: handoff.source_local_task_id,
      source_local_storage_source: handoff.source_local_storage_source,
      source_local_receipt_durable_in_sqlite: handoff.source_local_receipt_durable_in_sqlite,
      source_local_receipt_memory_only: handoff.source_local_receipt_memory_only,
      durable_local_receipt_required_for_handoff: handoff.durable_local_receipt_required_for_handoff,
      handoff_ready_from_local_receipt: handoff.handoff_ready_from_local_receipt,
      disabled_reason: handoff.disabled_reason,
      creates_provider_task_from_preview: handoff.creates_provider_task_from_preview,
      provider_execution_implemented_by_preview: handoff.provider_execution_implemented_by_preview,
      external_calls_triggered: handoff.external_calls_triggered
    }));
  });
  const ltgTradeCalProviderAcceptanceEvidenceHandoffRows = ltgNextAcceptanceActionRows
    .flatMap((row) => {
      const handoff = (row.supporting_trade_cal_provider_acceptance_evidence_handoff as Record<string, unknown> | undefined) ?? {};
      if (!Object.keys(handoff).length) {
        return [];
      }
      return [{
        queue_id: row.queue_id,
        priority: row.priority,
        status: handoff.status,
        provider_direct_evidence_source: handoff.provider_direct_evidence_source,
        provider_direct_evidence_status: handoff.provider_direct_evidence_status,
        provider_direct_evidence_layer: handoff.provider_direct_evidence_layer,
        provider_evidence_visible: handoff.provider_evidence_visible,
        promotion_audit_status: handoff.promotion_audit_status,
        promotion_audit_ready: handoff.promotion_audit_ready,
        durable_recipe_status: handoff.durable_recipe_status,
        durable_recipe_ready: handoff.durable_recipe_ready,
        durable_evidence_complete: handoff.durable_evidence_complete,
        durable_promotion_ready: handoff.durable_promotion_ready,
        local_complete: handoff.local_complete,
        local_completion_status: handoff.local_completion_status,
        local_blocker_count: handoff.local_blocker_count,
        local_promotion_review_ready_for_release: handoff.local_promotion_review_ready_for_release,
        local_promotion_review_status: handoff.local_promotion_review_status,
        local_promotion_review_creates_provider_task: handoff.local_promotion_review_creates_provider_task,
        local_promotion_review_calls_provider: handoff.local_promotion_review_calls_provider,
        local_promotion_review_is_not_production_completion: handoff.local_promotion_review_is_not_production_completion,
        production_promotion_review_done: handoff.production_promotion_review_done,
        local_release_gate_complete: handoff.local_release_gate_complete,
        local_release_gate_evidence_status: handoff.local_release_gate_evidence_status,
        local_worktree_clean_required_before_gate_receipt: handoff.local_worktree_clean_required_before_gate_receipt,
        local_worktree_raw_paths_emitted: handoff.local_worktree_raw_paths_emitted,
        local_worktree_raw_status_lines_emitted: handoff.local_worktree_raw_status_lines_emitted,
        fresh_local_gate_run_observed: handoff.fresh_local_gate_run_observed,
        local_push_gate_receipt_head_matches_current: handoff.local_push_gate_receipt_head_matches_current,
        required_local_gate_checks_present: handoff.required_local_gate_checks_present,
        remote_ci_review_required: handoff.remote_ci_review_required,
        remote_review_status: handoff.remote_review_status,
        remote_review_pending: handoff.remote_review_pending,
        remote_review_pending_count: handoff.remote_review_pending_count,
        remote_actions_status_known: handoff.remote_actions_status_known,
        latest_remote_run_verified_green: handoff.latest_remote_run_verified_green,
        release_review_pending: handoff.release_review_pending,
        release_review_pending_count: handoff.release_review_pending_count,
        release_review_complete: handoff.release_review_complete,
        strict_closeout_ready: handoff.strict_closeout_ready,
        allowed_next_step: handoff.allowed_next_step,
        provider_backed_acceptance_done_by_blocker_audit: handoff.provider_backed_acceptance_done_by_blocker_audit,
        provider_backed_acceptance_done_by_durable_recipe: handoff.provider_backed_acceptance_done_by_durable_recipe,
        trade_cal_provider_call_ledger_observed_count: handoff.trade_cal_provider_call_ledger_observed_count,
        trade_cal_provider_observed_row_count: handoff.trade_cal_provider_observed_row_count,
        freshness_replay_provider_evidence_done: handoff.freshness_replay_provider_evidence_done,
        failure_mode_provider_evidence_done: handoff.failure_mode_provider_evidence_done,
        latest_dry_run_found: handoff.latest_dry_run_found,
        latest_execution_request_found: handoff.latest_execution_request_found,
        latest_promotion_review_found: handoff.latest_promotion_review_found,
        next_local_step: handoff.next_local_step,
        requires_promotion_review_task: handoff.requires_promotion_review_task,
        requires_release_review_after_remote_green: handoff.requires_release_review_after_remote_green,
        cache_get_creates_task: handoff.cache_get_creates_task,
        cache_get_calls_provider: handoff.cache_get_calls_provider,
        provider_execution_implemented_by_handoff: handoff.provider_execution_implemented_by_handoff,
        production_freshness_gate_complete: handoff.production_freshness_gate_complete,
        external_calls_triggered: handoff.external_calls_triggered,
        tushare_called: handoff.tushare_called,
        deepseek_called: handoff.deepseek_called,
        does_not_execute_trades: handoff.does_not_execute_trades,
        can_close_goal: handoff.can_close_goal,
        evidence_boundary: handoff.evidence_boundary
      }];
    });
  const ltgTushareTargetSampleEvidenceHandoffRows = ltgNextAcceptanceActionRows
    .flatMap((row) => {
      const handoff = (row.supporting_tushare_target_sample_evidence_handoff as Record<string, unknown> | undefined) ?? {};
      if (!Object.keys(handoff).length) {
        return [];
      }
      return [{
        queue_id: row.queue_id,
        priority: row.priority,
        status: handoff.status,
        latest_execution_request_found: handoff.latest_execution_request_found,
        latest_execution_request_status: handoff.latest_execution_request_status,
        latest_execution_request_ready_for_manual_provider_task_submission: handoff.latest_execution_request_ready_for_manual_provider_task_submission,
        latest_execution_request_scope_hash_matches: handoff.latest_execution_request_scope_hash_matches,
        latest_execution_request_row_count: handoff.latest_execution_request_row_count,
        target_post_task_route: handoff.target_post_task_route,
        target_acceptance_mode: handoff.target_acceptance_mode,
        requested_target_count: handoff.requested_target_count,
        selected_api_count: handoff.selected_api_count,
        target_sample_acceptance_ready_for_review: handoff.target_sample_acceptance_ready_for_review,
        target_sample_acceptance_ready_count: handoff.target_sample_acceptance_ready_count,
        provider_call_ledger_visible: handoff.provider_call_ledger_visible,
        full_interface_selection_done: handoff.full_interface_selection_done,
        failure_mode_evidence_done: handoff.failure_mode_evidence_done,
        request_parameter_provider_window_done: handoff.request_parameter_provider_window_done,
        durable_recipe_ready: handoff.durable_recipe_ready,
        durable_evidence_complete: handoff.durable_evidence_complete,
        next_local_step: handoff.next_local_step,
        requires_separate_user_approved_provider_task: handoff.requires_separate_user_approved_provider_task,
        requires_full_interface_selection: handoff.requires_full_interface_selection,
        requires_remote_ci_review_after_local_complete: handoff.requires_remote_ci_review_after_local_complete,
        cache_get_creates_task: handoff.cache_get_creates_task,
        cache_get_calls_provider: handoff.cache_get_calls_provider,
        provider_execution_implemented_by_handoff: handoff.provider_execution_implemented_by_handoff,
        production_tushare_pipeline_complete: handoff.production_tushare_pipeline_complete,
        external_calls_triggered: handoff.external_calls_triggered,
        tushare_called: handoff.tushare_called,
        deepseek_called: handoff.deepseek_called,
        does_not_execute_trades: handoff.does_not_execute_trades,
        can_close_goal: handoff.can_close_goal,
        evidence_boundary: handoff.evidence_boundary
      }];
    });
  const ltgFactorTestProviderValidationHandoffRows = ltgNextAcceptanceActionRows
    .flatMap((row) => {
      const handoff = (row.supporting_factor_test_lab_provider_validation_handoff as Record<string, unknown> | undefined) ?? {};
      if (!Object.keys(handoff).length) {
        return [];
      }
      return [{
        queue_id: row.queue_id,
        priority: row.priority,
        status: handoff.status,
        direct_evidence_status: handoff.direct_evidence_status,
        direct_evidence_layer: handoff.direct_evidence_layer,
        local_light_metric_baseline_verified: handoff.local_light_metric_baseline_verified,
        provider_small_pool_scope_ticket_verified: handoff.provider_small_pool_scope_ticket_verified,
        provider_small_pool_dry_run_ready: handoff.provider_small_pool_dry_run_ready,
        provider_small_pool_execution_recipe_ready: handoff.provider_small_pool_execution_recipe_ready,
        provider_small_pool_execution_request_ready: handoff.provider_small_pool_execution_request_ready,
        ready_for_explicit_provider_small_pool_task: handoff.ready_for_explicit_provider_small_pool_task,
        activation_ready_for_provider_task: handoff.activation_ready_for_provider_task,
        provider_validation_blocker_count: handoff.provider_validation_blocker_count,
        durable_recipe_ready: handoff.durable_recipe_ready,
        durable_evidence_complete: handoff.durable_evidence_complete,
        provider_task_created: handoff.provider_task_created,
        provider_execution_implemented_by_handoff: handoff.provider_execution_implemented_by_handoff,
        provider_call_ledger_evidence_done: handoff.provider_call_ledger_evidence_done,
        sample_rows_collected: handoff.sample_rows_collected,
        rolling_window_validation_done: handoff.rolling_window_validation_done,
        neutralization_stability_done: handoff.neutralization_stability_done,
        provider_backed_small_pool_validation_done: handoff.provider_backed_small_pool_validation_done,
        full_market_validation_done: handoff.full_market_validation_done,
        production_factor_test_validation_complete: handoff.production_factor_test_validation_complete,
        next_local_step: handoff.next_local_step,
        requires_separate_user_approved_provider_task: handoff.requires_separate_user_approved_provider_task,
        requires_provider_call_ledger: handoff.requires_provider_call_ledger,
        requires_full_market_boundary_review: handoff.requires_full_market_boundary_review,
        requires_remote_ci_review_after_local_complete: handoff.requires_remote_ci_review_after_local_complete,
        cache_get_creates_task: handoff.cache_get_creates_task,
        cache_get_calls_provider: handoff.cache_get_calls_provider,
        external_calls_triggered: handoff.external_calls_triggered,
        tushare_called: handoff.tushare_called,
        deepseek_called: handoff.deepseek_called,
        does_not_execute_trades: handoff.does_not_execute_trades,
        can_close_goal: handoff.can_close_goal,
        evidence_boundary: handoff.evidence_boundary
      }];
    });
  const ltgFactorUniverseWorkerBatchHandoffRows = ltgNextAcceptanceActionRows
    .flatMap((row) => {
      const handoff = (row.supporting_factor_universe_worker_batch_handoff as Record<string, unknown> | undefined) ?? {};
      if (!Object.keys(handoff).length) {
        return [];
      }
      return [{
        queue_id: row.queue_id,
        priority: row.priority,
        status: handoff.status,
        direct_evidence_status: handoff.direct_evidence_status,
        direct_evidence_layer: handoff.direct_evidence_layer,
        local_rank_zscore_research_preview_verified: handoff.local_rank_zscore_research_preview_verified,
        worker_batch_dry_run_ready: handoff.worker_batch_dry_run_ready,
        worker_batch_execution_recipe_ready: handoff.worker_batch_execution_recipe_ready,
        worker_batch_execution_request_ready: handoff.worker_batch_execution_request_ready,
        worker_batch_research_receipt_ready: handoff.worker_batch_research_receipt_ready,
        ready_for_worker_runtime_evidence_collection: handoff.ready_for_worker_runtime_evidence_collection,
        worker_dependency_preflight_visible: handoff.worker_dependency_preflight_visible,
        worker_dependency_preflight_status: handoff.worker_dependency_preflight_status,
        worker_dependency_preflight_blocker_count: handoff.worker_dependency_preflight_blocker_count,
        worker_dependency_local_non_redis_runtime_ready: handoff.worker_dependency_local_non_redis_runtime_ready,
        durable_recipe_ready: handoff.durable_recipe_ready,
        durable_evidence_complete: handoff.durable_evidence_complete,
        worker_task_created: handoff.worker_task_created,
        worker_task_executed: handoff.worker_task_executed,
        worker_execution_implemented: handoff.worker_execution_implemented,
        worker_started: handoff.worker_started,
        celery_worker_started: handoff.celery_worker_started,
        redis_pinged: handoff.redis_pinged,
        large_universe_pipeline_done: handoff.large_universe_pipeline_done,
        cross_sectional_rank_zscore_done: handoff.cross_sectional_rank_zscore_done,
        neutralization_done: handoff.neutralization_done,
        factor_combination_research_done: handoff.factor_combination_research_done,
        full_pool_validation_done: handoff.full_pool_validation_done,
        production_factor_universe_complete: handoff.production_factor_universe_complete,
        partial_pool_is_full_market_proof: handoff.partial_pool_is_full_market_proof,
        frontend_computes_rank_zscore: handoff.frontend_computes_rank_zscore,
        next_local_step: handoff.next_local_step,
        requires_separate_user_approved_worker_task: handoff.requires_separate_user_approved_worker_task,
        requires_worker_runtime_binding: handoff.requires_worker_runtime_binding,
        requires_storage_read_execution: handoff.requires_storage_read_execution,
        requires_full_pool_validation: handoff.requires_full_pool_validation,
        cache_get_creates_task: handoff.cache_get_creates_task,
        cache_get_starts_worker: handoff.cache_get_starts_worker,
        external_calls_triggered: handoff.external_calls_triggered,
        tushare_called: handoff.tushare_called,
        deepseek_called: handoff.deepseek_called,
        does_not_execute_trades: handoff.does_not_execute_trades,
        can_close_goal: handoff.can_close_goal,
        evidence_boundary: handoff.evidence_boundary
      }];
    });
  const ltgStoragePhysicalExecutionHandoffRows = ltgNextAcceptanceActionRows
    .flatMap((row) => {
      const handoff = (row.supporting_storage_physical_execution_handoff as Record<string, unknown> | undefined) ?? {};
      if (!Object.keys(handoff).length) {
        return [];
      }
      return [{
        queue_id: row.queue_id,
        priority: row.priority,
        status: handoff.status,
        direct_evidence_status: handoff.direct_evidence_status,
        direct_evidence_layer: handoff.direct_evidence_layer,
        direct_evidence_stage_count: handoff.direct_evidence_stage_count,
        readiness_status: handoff.readiness_status,
        activation_status: handoff.activation_status,
        execution_recipe_status: handoff.execution_recipe_status,
        execution_request_status: handoff.execution_request_status,
        durable_recipe_status: handoff.durable_recipe_status,
        phase_a_status: handoff.phase_a_status,
        storage_physical_execution_request_ready: handoff.storage_physical_execution_request_ready,
        storage_physical_execution_phase_a_visible: handoff.storage_physical_execution_phase_a_visible,
        phase_a_local_evidence_done: handoff.phase_a_local_evidence_done,
        production_promotion_review_done: handoff.production_promotion_review_done,
        production_promotion_review_status: handoff.production_promotion_review_status,
        production_promotion_review_production_blocker_count: handoff.production_promotion_review_production_blocker_count,
        physical_execution_scope_hash_short: handoff.physical_execution_scope_hash_short,
        target_storage_task_route: handoff.target_storage_task_route,
        target_storage_task_type: handoff.target_storage_task_type,
        target_acceptance_mode: handoff.target_acceptance_mode,
        next_local_step: handoff.next_local_step,
        requires_schema_migration_execution: handoff.requires_schema_migration_execution,
        requires_manifest_validation: handoff.requires_manifest_validation,
        requires_partition_migration: handoff.requires_partition_migration,
        requires_physical_compaction: handoff.requires_physical_compaction,
        requires_cache_ttl_refresh: handoff.requires_cache_ttl_refresh,
        requires_artifact_cleanup_review: handoff.requires_artifact_cleanup_review,
        requires_duckdb_post_migration_validation: handoff.requires_duckdb_post_migration_validation,
        requires_production_promotion_closeout: handoff.requires_production_promotion_closeout,
        requires_remote_ci_review_after_local_complete: handoff.requires_remote_ci_review_after_local_complete,
        physical_task_created: handoff.physical_task_created,
        physical_task_executed: handoff.physical_task_executed,
        physical_execution_implemented: handoff.physical_execution_implemented,
        physical_execution_complete: handoff.physical_execution_complete,
        writes_parquet: handoff.writes_parquet,
        writes_manifest: handoff.writes_manifest,
        deletes_artifacts: handoff.deletes_artifacts,
        refreshes_providers: handoff.refreshes_providers,
        cache_get_creates_task: handoff.cache_get_creates_task,
        cache_get_writes_parquet: handoff.cache_get_writes_parquet,
        cache_get_writes_manifest: handoff.cache_get_writes_manifest,
        cache_get_deletes_artifacts: handoff.cache_get_deletes_artifacts,
        external_calls_triggered: handoff.external_calls_triggered,
        tushare_called: handoff.tushare_called,
        deepseek_called: handoff.deepseek_called,
        github_called: handoff.github_called,
        does_not_execute_trades: handoff.does_not_execute_trades,
        production_storage_complete: handoff.production_storage_complete,
        can_close_goal: handoff.can_close_goal,
        evidence_boundary: handoff.evidence_boundary
      }];
    });
  const ltgWorkerRuntimeQaHandoffRows = ltgNextAcceptanceActionRows
    .flatMap((row) => {
      const handoff = (row.supporting_worker_runtime_qa_handoff as Record<string, unknown> | undefined) ?? {};
      if (!Object.keys(handoff).length) {
        return [];
      }
      return [{
        queue_id: row.queue_id,
        priority: row.priority,
        status: handoff.status,
        direct_evidence_status: handoff.direct_evidence_status,
        direct_evidence_layer: handoff.direct_evidence_layer,
        direct_evidence_stage_count: handoff.direct_evidence_stage_count,
        dependency_preflight_status: handoff.dependency_preflight_status,
        evidence_plan_status: handoff.evidence_plan_status,
        execution_recipe_status: handoff.execution_recipe_status,
        execution_request_status: handoff.execution_request_status,
        dry_run_status: handoff.dry_run_status,
        runtime_execution_status: handoff.runtime_execution_status,
        durable_recipe_status: handoff.durable_recipe_status,
        production_promotion_review_status: handoff.production_promotion_review_status,
        local_non_redis_runtime_ready: handoff.local_non_redis_runtime_ready,
        redis_manual_resolution_required: handoff.redis_manual_resolution_required,
        evidence_plan_ready: handoff.evidence_plan_ready,
        runtime_qa_execution_recipe_ready: handoff.runtime_qa_execution_recipe_ready,
        runtime_qa_execution_request_ready: handoff.runtime_qa_execution_request_ready,
        runtime_qa_dry_run_ready: handoff.runtime_qa_dry_run_ready,
        runtime_qa_execution_done: handoff.runtime_qa_execution_done,
        production_promotion_review_ready: handoff.production_promotion_review_ready,
        durable_recipe_ready: handoff.durable_recipe_ready,
        durable_evidence_complete: handoff.durable_evidence_complete,
        celery_process_evidence_verified: handoff.celery_process_evidence_verified,
        redis_broker_evidence_verified: handoff.redis_broker_evidence_verified,
        local_fallback_round_trip_verified: handoff.local_fallback_round_trip_verified,
        cross_process_task_control_verified: handoff.cross_process_task_control_verified,
        append_only_worker_log_verified: handoff.append_only_worker_log_verified,
        scheduler_default_off_runtime_verified: handoff.scheduler_default_off_runtime_verified,
        provider_model_no_autoschedule_boundary_verified: handoff.provider_model_no_autoschedule_boundary_verified,
        no_trade_no_action_boundary_verified: handoff.no_trade_no_action_boundary_verified,
        runtime_qa_scope_hash_short: handoff.runtime_qa_scope_hash_short,
        target_worker_task_route: handoff.target_worker_task_route,
        target_worker_task_type: handoff.target_worker_task_type,
        target_acceptance_mode: handoff.target_acceptance_mode,
        next_local_step: handoff.next_local_step,
        requires_production_worker_closeout: handoff.requires_production_worker_closeout,
        requires_remote_ci_review_after_local_complete: handoff.requires_remote_ci_review_after_local_complete,
        local_runtime_qa_task_created: handoff.local_runtime_qa_task_created,
        local_runtime_qa_task_executed: handoff.local_runtime_qa_task_executed,
        runtime_qa_execution_implemented: handoff.runtime_qa_execution_implemented,
        worker_started: handoff.worker_started,
        celery_worker_started: handoff.celery_worker_started,
        redis_pinged: handoff.redis_pinged,
        scheduler_started: handoff.scheduler_started,
        task_dispatched: handoff.task_dispatched,
        provider_model_task_dispatched: handoff.provider_model_task_dispatched,
        cache_get_creates_task: handoff.cache_get_creates_task,
        cache_get_starts_worker: handoff.cache_get_starts_worker,
        cache_get_pings_redis: handoff.cache_get_pings_redis,
        cache_get_dispatches_task: handoff.cache_get_dispatches_task,
        external_calls_triggered: handoff.external_calls_triggered,
        tushare_called: handoff.tushare_called,
        deepseek_called: handoff.deepseek_called,
        github_called: handoff.github_called,
        does_not_execute_trades: handoff.does_not_execute_trades,
        production_worker_complete: handoff.production_worker_complete,
        can_close_goal: handoff.can_close_goal,
        evidence_boundary: handoff.evidence_boundary
      }];
    });
  const ltgCurrentEvidenceProducerCacheRefreshHandoffRows = ltgNextAcceptanceActionRows
    .flatMap((row) => {
      const handoff = (row.supporting_current_evidence_producer_cache_refresh_handoff as Record<string, unknown> | undefined) ?? {};
      if (!Object.keys(handoff).length) {
        return [];
      }
      return [{
        queue_id: row.queue_id,
        priority: row.priority,
        status: handoff.status,
        readiness_status: handoff.readiness_status,
        next_local_step: handoff.next_local_step,
        execution_request_route: handoff.execution_request_route,
        target_local_refresh_route: handoff.target_local_refresh_route,
        readiness_scope_hash_short: handoff.readiness_scope_hash_short,
        current_cache_refresh_required_count: handoff.current_cache_refresh_required_count,
        local_cache_refresh_ready: handoff.local_cache_refresh_ready,
        latest_execution_request_found: handoff.latest_execution_request_found,
        requires_user_confirmation: handoff.requires_user_confirmation,
        requires_execution_request_before_refresh: handoff.requires_execution_request_before_refresh,
        cache_get_creates_task: handoff.cache_get_creates_task,
        cache_get_writes_snapshot_cache: handoff.cache_get_writes_snapshot_cache,
        cache_get_external_calls: handoff.cache_get_external_calls,
        provider_execution_implemented: handoff.provider_execution_implemented,
        production_freshness_gate_complete: handoff.production_freshness_gate_complete,
        external_calls_triggered: handoff.external_calls_triggered,
        tushare_called: handoff.tushare_called,
        deepseek_called: handoff.deepseek_called,
        does_not_execute_trades: handoff.does_not_execute_trades,
        can_close_goal: handoff.can_close_goal,
        evidence_boundary: handoff.evidence_boundary
      }];
    });
  const tradeIsolationReleaseGuardQueueRow = ltgNextAcceptanceActionRows.find(
    (row) => row.queue_id === "p10_trade_isolation_release_guard"
  ) ?? {};
  const motionProductionQueueRow = ltgNextAcceptanceActionRows.find(
    (row) => row.queue_id === "p8_motion_production_promotion_review"
  ) ?? {};
  const motionProductionHandoff =
    (motionProductionQueueRow.supporting_motion_production_handoff as Record<string, unknown> | undefined) ?? {};
  const motionProductionReviewGateRows = [
    {
      evidence_slice: "local_motion_review_chain",
      queue_id: motionProductionQueueRow.queue_id,
      status: motionProductionHandoff.status,
      next_local_step: motionProductionQueueRow.next_local_step,
      next_local_step_ready: motionProductionQueueRow.next_local_step_ready_for_clean_receipt,
      review_chain_ready_for_release_evidence:
        motionProductionQueueRow.supporting_motion_production_review_chain_ready_for_release_evidence === true,
      visual_performance_review_ready:
        motionProductionHandoff.motion_visual_performance_promotion_review_ready === true,
      durable_evidence_recipe_ready: motionProductionHandoff.motion_durable_evidence_recipe_ready === true,
      evidence_boundary: motionProductionHandoff.evidence_boundary
    },
    {
      evidence_slice: "visual_performance_local_promotion",
      browser_visual_qa_promoted: motionProductionHandoff.browser_visual_qa_promoted,
      browser_performance_promoted: motionProductionHandoff.browser_performance_promoted,
      reduced_motion_durable_evidence_promoted:
        motionProductionHandoff.reduced_motion_durable_evidence_promoted,
      direct_evidence_stage_count: motionProductionHandoff.direct_evidence_stage_count,
      direct_evidence_stage_keys: Array.isArray(motionProductionHandoff.direct_evidence_stage_keys)
        ? motionProductionHandoff.direct_evidence_stage_keys.join(", ")
        : "",
      production_motion_complete: motionProductionHandoff.production_motion_complete
    },
    {
      evidence_slice: "durable_ci_release_blocker",
      durable_ci_evidence_complete: motionProductionHandoff.durable_ci_evidence_complete,
      requires_durable_ci_release_evidence:
        motionProductionHandoff.requires_durable_ci_release_evidence,
      requires_production_motion_review: motionProductionHandoff.requires_production_motion_review,
      requires_remote_ci_review_after_local_complete:
        motionProductionHandoff.requires_remote_ci_review_after_local_complete,
      requires_release_review_after_remote_green:
        motionProductionHandoff.requires_release_review_after_remote_green,
      can_close_goal: motionProductionHandoff.can_close_goal
    },
    {
      evidence_slice: "ltg12_trade_isolation_support",
      external_calls_triggered: motionProductionHandoff.external_calls_triggered,
      tushare_called: motionProductionHandoff.tushare_called,
      deepseek_called: motionProductionHandoff.deepseek_called,
      github_called: motionProductionHandoff.github_called,
      does_not_execute_trades: motionProductionHandoff.does_not_execute_trades,
      does_not_modify_strategy_action: motionProductionHandoff.does_not_modify_strategy_action
    }
  ];
  const tradeIsolationReleaseGuardRows = [
    {
      evidence_slice: "research_release_trade_isolation_receipt",
      queue_id: tradeIsolationReleaseGuardQueueRow.queue_id,
      status: tradeIsolationGoalObservedRow.status,
      receipt_ready: tradeIsolationGoalObservedRow.trade_isolation_release_receipt_ready === true,
      receipt_status: tradeIsolationGoalObservedRow.trade_isolation_release_receipt_status,
      direct_evidence_stage_count: tradeIsolationGoalObservedRow.direct_evidence_stage_count,
      pending_stage_count: tradeIsolationGoalObservedRow.pending_stage_count,
      release_receipt_is_trading_approval: tradeIsolationGoalObservedRow.release_receipt_is_trading_approval,
      evidence_boundary: tradeIsolationGoalObservedRow.evidence_boundary
    },
    {
      evidence_slice: "no_broker_order_or_trade_execution_api",
      real_trading_connected: tradeIsolationGoalObservedRow.real_trading_connected,
      broker_adapter_connected: tradeIsolationGoalObservedRow.broker_adapter_connected,
      order_endpoint_present: tradeIsolationGoalObservedRow.order_endpoint_present,
      trade_execution_api_enabled: tradeIsolationGoalObservedRow.trade_execution_api_enabled,
      order_route_present: tradeIsolationGoalObservedRow.order_route_present,
      frontend_trade_controls_present: tradeIsolationGoalObservedRow.frontend_trade_controls_present,
      broker_called: tradeIsolationGoalObservedRow.broker_called,
      order_submitted: tradeIsolationGoalObservedRow.order_submitted
    },
    {
      evidence_slice: "no_action_mutation_from_model_provider_or_cache",
      model_or_provider_can_modify_action: tradeIsolationGoalObservedRow.model_or_provider_can_modify_action,
      strategy_action_mutated_by_contract: tradeIsolationGoalObservedRow.strategy_action_mutated_by_contract,
      does_not_execute_trades: tradeIsolationGoalObservedRow.does_not_execute_trades,
      does_not_modify_strategy_action: tradeIsolationGoalObservedRow.does_not_modify_strategy_action,
      does_not_modify_holdings: tradeIsolationGoalObservedRow.does_not_modify_holdings,
      external_calls_triggered: tradeIsolationGoalObservedRow.external_calls_triggered,
      tushare_called: tradeIsolationGoalObservedRow.tushare_called,
      deepseek_called: tradeIsolationGoalObservedRow.deepseek_called,
      github_called: tradeIsolationGoalObservedRow.github_called
    },
    {
      evidence_slice: "separate_real_trading_project_required",
      ready_for_real_trading_integration: tradeIsolationGoalObservedRow.ready_for_real_trading_integration,
      future_real_trading_requires_separate_project: tradeIsolationGoalObservedRow.future_real_trading_requires_separate_project,
      separate_project_approved: tradeIsolationGoalObservedRow.separate_project_approved,
      paper_trading_sandbox_ready: tradeIsolationGoalObservedRow.paper_trading_sandbox_ready,
      continued_no_broker_proof_required: tradeIsolationGoalObservedRow.continued_no_broker_proof_required,
      continued_no_order_proof_required: tradeIsolationGoalObservedRow.continued_no_order_proof_required,
      continued_no_action_mutation_proof_required: tradeIsolationGoalObservedRow.continued_no_action_mutation_proof_required
    },
    {
      evidence_slice: "remote_review_split_before_strict_closeout",
      local_complete: tradeIsolationGoalObservedRow.local_complete,
      local_completion_status: tradeIsolationGoalObservedRow.local_completion_status,
      remote_review_required_after_local_complete: tradeIsolationGoalObservedRow.remote_review_required_after_local_complete,
      remote_review_pending: tradeIsolationGoalObservedRow.remote_review_pending,
      release_review_required_after_remote_green: tradeIsolationGoalObservedRow.release_review_required_after_remote_green,
      release_review_pending: tradeIsolationGoalObservedRow.release_review_pending,
      strict_closeout_ready: tradeIsolationGoalObservedRow.strict_closeout_ready,
      can_close_from_observed_row: tradeIsolationGoalObservedRow.can_close_from_observed_row
    }
  ];
  const missingLocalReceiptSteps = ltgNextAcceptanceActionRows.reduce(
    (total, row) => total + Number(row.missing_local_receipt_step_count ?? 0),
    0
  );
  const observedLocalReceiptSteps = ltgNextAcceptanceActionRows.reduce(
    (total, row) => total + Number(row.observed_local_receipt_step_count ?? 0),
    0
  );
  const readyLocalReceiptSteps = ltgNextAcceptanceActionRows.reduce(
    (total, row) => total + Number(row.ready_local_receipt_step_count ?? 0),
    0
  );
  const blockedLocalReceiptSteps = ltgNextAcceptanceActionRows.reduce(
    (total, row) => total + Number(row.blocked_local_receipt_step_count ?? 0),
    0
  );
  const durableLocalReceiptSteps = ltgNextAcceptanceActionRows.reduce(
    (total, row) => total + Number(row.durable_local_receipt_step_count ?? 0),
    0
  );
  const memoryOnlyLocalReceiptSteps = ltgNextAcceptanceActionRows.reduce(
    (total, row) => total + Number(row.memory_only_local_receipt_step_count ?? 0),
    0
  );
  const policy = packet.api_policy as Record<string, unknown> | undefined;
  const baselinePolicy = packet.baseline_policy as Record<string, unknown> | undefined;
  const payloadCallLedger = (packet.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((packet.warnings as Array<string> | undefined) ?? []);
  const warningRows = cacheWarnings.map((warning, index) => ({ index: index + 1, warning }));
  const principleRows = principles.map((principle, index) => {
    const text = String(principle ?? "");
    const category = text.includes("git add") || text.includes("push")
      ? "提交 / 推送纪律"
      : text.includes("Tushare") || text.includes("DeepSeek") || text.includes("GitHub") || text.includes("外部请求")
        ? "外部调用边界"
        : text.includes("交易") || text.includes("下单") || text.includes("strategy")
          ? "交易边界"
          : "迁移原则";
    return { index: index + 1, category, principle: text };
  });
  const localAcceptanceRunwayRows = longTermGoalRows.map((row) => {
    const id = String(row.id ?? "");
    const priorityStep = longTermNextPriority.find((item) => String(item).includes(id));
    return {
      id,
      priority: priorityStep ?? "ongoing",
      goal: row.goal,
      bucket: row.completion_bucket,
      completion_estimate: row.completion_estimate,
      observed_pending: Number(row.observed_stage_scope_pending_count ?? 0),
      next_step: row.next_step,
      can_close_goal: row.production_complete === true || row.observed_stage_scope_can_close_goal === true
    };
  });
  const ltgAcceptanceRunwayRows = packetAcceptanceRunwayRows.length ? packetAcceptanceRunwayRows : localAcceptanceRunwayRows;
  const legacyAuditObservationTargets = [
    {
      key: "legacy_intake_home_daily_command",
      workflow_group: "home/daily command",
      next_click: "记录首页 / 今日作战台 UX 观察",
      user_observation: "Reviewer observed that daily command needs one clear first-view next step instead of legacy home rerun buttons and engineering tables.",
      legacy_ux_bug_or_patchwork: "Legacy home/rerun flow mixes refresh buttons, status coupling, and engineering tables before daily summary, making the next click unclear.",
      data_lineage_observation: "Check whether cache/provider/pending source, missing evidence, blocked/degraded state, and last-good cache are visible before audit tables.",
      replacement_user_path: "今日作战台 / Daily Command Center first-view summary",
      frozen_legacy_path: "旧 Streamlit 首页按钮 / rerun flow"
    },
    {
      key: "searched_symbol_quant_projection",
      workflow_group: "searched-symbol quant projection",
      next_click: "记录搜票量化观察 dry-run",
      user_observation: "Reviewer observed that searched-symbol projection needs one clear next click instead of hunting through legacy tabs.",
      legacy_ux_bug_or_patchwork: "Legacy tab/radio flow makes the next projection action hard to find; synchronous old path can feel blocking.",
      data_lineage_observation: "Provider/cache/model/pending states need to be separated before the workflow enters an ordinary user path.",
      replacement_user_path: "股票量化推演 / Stock Quant Projection -> 生成 3.0 量化推演",
      frozen_legacy_path: "legacy searched-symbol synchronous projection path stays admin/debug fallback until redesigned"
    },
    {
      key: "legacy_intake_candidate_radar",
      workflow_group: "candidate radar",
      next_click: "记录下一票雷达 UX 观察",
      user_observation: "Reviewer observed that candidate review must distinguish Top/Watch/Excluded, scan scope, and no-buy boundary before legacy fallback or promotion details.",
      legacy_ux_bug_or_patchwork: "Legacy radar fallback can blur quick-scan/full-pool/deep-scan boundaries, make candidates look like buy instructions, and hide provider/performance gaps.",
      data_lineage_observation: "Check whether candidate source, last radar cache, provider gap, pending/degraded state, browser/CI/provider missing evidence, and no-buy boundary are visible.",
      replacement_user_path: "下一票雷达 / Candidate Radar ordinary summary and 搜票量化推演",
      frozen_legacy_path: "旧 fallback 雷达路径、推荐式文案和未证明性能路径"
    },
    {
      key: "factor_risk_provider_health",
      workflow_group: "factor/risk/provider health",
      next_click: "记录 factor/provider 大表观察 dry-run",
      user_observation: "Reviewer observed that factor/provider health detail should not dominate ordinary pages; users need factor/risk summary first.",
      legacy_ux_bug_or_patchwork: "Legacy provider-health tables can bury ordinary signal, auto/TTL probing may look like page-open external calls, and small samples can look like production proof.",
      data_lineage_observation: "Factor support/suppress, risk summary, provider/cache/pending, missing evidence, and last successful cache must be visible before provider-health details.",
      replacement_user_path: "股票量化推演 / Stock Quant Projection and 今日作战台 / Daily Command Center summaries; provider detail goes to Settings / Developer / Audit",
      frozen_legacy_path: "legacy provider-health table stays admin/debug fallback until redesigned"
    }
  ];
  const legacyAuditObservationFocusWorkflow = legacyAuditObservationTargets.map((target) => target.workflow_group).join(" / ");
  const legacyAuditObservationNextClick = "记录 Legacy UX 观察 dry-run";
  const legacyAuditObservationEvidenceRule = "只允许 redacted reviewer note；不贴 raw packet/raw log/token/key/未脱敏模型输出";
  const legacyAuditObservationBoundary =
    "只生成本地 observation dry-run；不打开 Streamlit、不调用 provider/model、不升级 KEEP 或 ordinary entry";
  const refreshMigrationStatus = () => void getMigrationStatus().then((res) => {
    setPacket(res.data);
    setCacheEnvelopeLedger(res.call_ledger ?? []);
    setCacheEnvelopeWarnings(res.warnings ?? []);
  });
  const launchLinkageReview = () => {
    setLinkageReviewError("");
    void postTushareDeepseekLinkageReview({
      approved_by_user: true,
      review_scope: "tushare_deepseek_mode_layer_linkage",
      reviewer: "local_ui"
    }).then((res) => {
      if (!res.ok) {
        setLinkageReviewError(String(res.error ?? "tushare_deepseek_linkage_review_failed"));
        return;
      }
      setLinkageReviewTask(res.data.task as unknown as Record<string, unknown>);
      refreshMigrationStatus();
    });
  };
  const launchLegacyAuditObservationDryRun = (target = legacyAuditObservationTargets[0]) => {
    setLegacyAuditObservationError("");
    void postLegacyAuditObservationDryRun({
      workflow_group: target.workflow_group,
      user_observation: target.user_observation,
      legacy_ux_bug_or_patchwork: target.legacy_ux_bug_or_patchwork,
      data_lineage_observation: target.data_lineage_observation,
      replacement_user_path: target.replacement_user_path,
      frozen_legacy_path: target.frozen_legacy_path,
      evidence_attachment: "redacted_reviewer_note: migration-status-observation-dry-run",
      evidence_attachment_type: "redacted_reviewer_note",
      requested_status: "direct_evidence_observed_redesign_required",
      keep_promotion_decision: "no_keep_promotion_this_round",
      requested_by: "migration_status_legacy_audit_workbench",
      source: "migration_status_legacy_audit_workbench"
    }).then((res) => {
      setLegacyAuditObservationReceipt(res);
      if (res.ok) {
        setLegacyAuditObservationTaskId(res.data.task_id);
        refreshMigrationStatus();
      } else {
        setLegacyAuditObservationError(String(res.error ?? "legacy_audit_observation_dry_run_failed"));
      }
    });
  };
  const launchLtgNextAction = (row: Record<string, unknown>) => {
    const route = String(row.next_local_step ?? "");
    setLtgNextActionError("");
    void postLtgNextAcceptanceLocalStep(route, ltgNextStepPayload(row)).then((res) => {
      setLtgNextActionReceipt(res);
      if (res.ok) {
        setLtgNextActionTaskId(res.data.task_id);
        refreshMigrationStatus();
      } else {
        setLtgNextActionError(String(res.error ?? "ltg_next_acceptance_local_step_failed"));
      }
    });
  };
  const migrationPacketLoaded = Object.keys(packet).length > 0;
  const migrationLocalConnected = migrationPacketLoaded || healthReady;
  const migrationStrictCloseoutLabel = String(longTermGoalSummary.strict_closeout ?? "0/14");
  const migrationGoalCountLabel = String(longTermGoalSummary.goal_count ?? 14);
  const migrationCurrentMainFocus = ordinaryMigrationText(
    longTermNextPriority[0] ?? "普通用户可用化并行修补；长期主线继续收证据"
  );
  const migrationOrdinaryNextStep = ordinaryMigrationText(
    usablePathCurrentCheckpointRows[0]?.["用户下一步"] ??
      usablePathCurrentCheckpointRows[0]?.next_action ??
      "先看今日作战台、下一票雷达、股票量化推演和次日图谱；工程详情留在折叠区"
  );
  const migrationAheadLabel = releaseGateCurrentHeadAheadCount > 0
    ? `当前本地领先 ${releaseGateCurrentHeadAheadCount}`
    : "当前本地领先数量待复核";
  const migrationBlockerSummary = ordinaryMigrationText(
    releaseGateCurrentHeadPushRequired || releaseGateRemoteReviewWaitingForPush
      ? `长期主线还缺本地门禁、发布和同版本远端查收；${migrationAheadLabel}`
      : "外部数据验收、远端自动检查、发布复核和生产证据未完全收口，不能称为长期目标全部完成"
  );
  const migrationOrdinaryStatusItems: MetricItem[] = [
    {
      label: "当前状态",
      value: migrationPacketLoaded
        ? "本地迁移摘要已接上"
        : healthReady
          ? "本地已接上，迁移摘要读取中"
          : "正在读取本地迁移摘要"
    },
    {
      label: "长期目标",
      value: `${migrationStrictCloseoutLabel} 完成最终收口 / 共 ${migrationGoalCountLabel} 个`
    },
    {
      label: "当前主攻",
      value: migrationCurrentMainFocus
    },
    {
      label: "下一步",
      value: String(migrationOrdinaryNextStep)
    },
    {
      label: "阻断原因",
      value: migrationBlockerSummary
    },
    {
      label: "普通入口",
      value: "今日作战台 / 下一票雷达 / 股票量化推演 / 次日图谱"
    },
    {
      label: "安全边界",
      value: "本页只读查看；不创建任务、不调用外部服务、不交易"
    },
    {
      label: "说明",
      value: "这里不是长期目标全部完成声明；工程查收、队列和原始表在下方详情"
    }
  ];

  return (
    <>
      <PacketCard title="迁移状态摘要" subtitle="普通用户只看当前进度、主攻方向、下一步和阻断原因" status={migrationLocalConnected ? "本地已接上" : undefined}>
        <p className="ordinary-status-note">这张卡只回答现在迁移到哪、下一步去哪、为什么不能说长期目标全部完成；工程表和开发按钮默认下沉。</p>
        <MetricGrid items={migrationOrdinaryStatusItems} />
        <div className="actions" aria-label="migration ordinary summary actions">
          <button onClick={refreshMigrationStatus} title="只刷新本地迁移摘要；不创建任务、不外联">刷新本地摘要</button>
          <a href="#home" title="回今日作战台；普通用户主入口">今日作战台</a>
          <a href="#candidates/candidate-radar-search-quant-projection" title="去下一票雷达确认输入区；输入静默">下一票雷达</a>
          <a href="#factor" title="打开股票量化推演；只读本地结果">股票量化推演</a>
          <a href="#next" title="打开次日图谱；只读本地缓存">次日图谱</a>
        </div>
        <p className="risk-note">页面打开和刷新摘要只读本地结果；不调用外部数据、模型、远端检查、后台执行或交易路径。</p>
      </PacketCard>

      <details className="developer-audit-details" aria-label="migration status developer audit details">
        <summary>研究辅助 / 工程迁移详情</summary>
        <PacketCard title="Command Center 3.0 迁移状态" subtitle="固定长期参考基线；只读、不重新估算、不外联" status={String(packet.status ?? "loading")}>
      <div className="actions">
        <button onClick={refreshMigrationStatus}>查看迁移基线</button>
        <button onClick={launchLinkageReview}>生成联动 review 收据</button>
      </div>
      {linkageReviewError && <p className="risk-note">{linkageReviewError}</p>}
      <MetricGrid
        items={[
          { label: "baseline items", value: progress.length },
          { label: "LTG goals", value: longTermGoalSummary.goal_count as number | undefined },
          { label: "LTG closed", value: String(longTermGoalSummary.strict_closeout ?? "0/14"), tone: longTermGoalSummary.closed_count === 0 ? "warn" : "good" },
          { label: "observed manifests", value: Number(longTermGoalSummary.observed_stage_scope_manifest_count ?? 0), tone: Number(longTermGoalSummary.observed_stage_scope_manifest_count ?? 0) ? "good" : "warn" },
          { label: "observed pending", value: Number(longTermGoalSummary.observed_stage_scope_pending_count ?? 0), tone: Number(longTermGoalSummary.observed_stage_scope_pending_count ?? 0) ? "warn" : "good" },
          { label: "foundation", value: String(longTermGoalSummary.foundation_progress_estimate ?? "--") },
          { label: "production acceptance", value: String(longTermGoalSummary.production_acceptance_estimate ?? "--") },
          { label: "Tushare/DeepSeek linkage", value: String(tushareDeepseekLinkage.status ?? "pending") },
          { label: "linkage layers", value: tushareDeepseekLinkageRows.length },
          { label: "mode layers", value: tushareDeepseekModeLayerRows.length },
          { label: "linkage blockers", value: Number(tushareDeepseekLinkage.blocking_row_count ?? 0), tone: Number(tushareDeepseekLinkage.blocking_row_count ?? 0) ? "bad" : "good" },
          { label: "latest linkage review", value: String(linkageReviewReceipt.status ?? "not_run") },
          { label: "review blockers", value: Number(linkageReviewReceipt.blocking_row_count ?? 0), tone: Number(linkageReviewReceipt.blocking_row_count ?? 0) ? "warn" : "good" },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length },
          { label: "P0-P6 checkpoint rows", value: usablePathCurrentCheckpointRows.length, tone: usablePathCurrentCheckpointRows.length ? "good" : "warn" },
          { label: "hardening areas", value: productionHardeningRows.length, tone: productionHardeningRows.length ? "warn" : "neutral" },
          { label: "LTG evidence rows", value: productionHardeningLtgRows.length, tone: productionHardeningLtgRows.length ? "warn" : "neutral" },
          { label: "hardening gates", value: productionHardeningGateRows.length, tone: productionHardeningGateRows.length ? "warn" : "neutral" },
          { label: "LTG work orders", value: ltgStrictCloseoutWorkOrderRows.length, tone: ltgStrictCloseoutWorkOrderRows.length ? "warn" : "neutral" },
          { label: "planning baseline", value: baselinePolicy?.use_as_planning_baseline === true, tone: baselinePolicy?.use_as_planning_baseline === true ? "good" : "warn" },
          { label: "cache only", value: policy?.cache_only === true, tone: policy?.cache_only === true ? "good" : "warn" },
          { label: "external calls", value: policy?.external_calls_triggered === true ? "存在" : "无", tone: policy?.external_calls_triggered === true ? "bad" : "good" },
          { label: "real trading", value: policy?.does_not_execute_trades === false ? "可能" : "禁止", tone: policy?.does_not_execute_trades === false ? "bad" : "good" },
          { label: "strategy action", value: policy?.does_not_modify_strategy_action === false ? "会修改" : "不修改", tone: policy?.does_not_modify_strategy_action === false ? "bad" : "good" }
        ]}
      />
      <h3>固定进度表</h3>
      <DataLineageTable rows={progress} />
      <div aria-label="usable path current checkpoint quick read">
        <h3>P0-P6 当前可用化 checkpoint 速读</h3>
        <p className="risk-note">这张表只说明普通用户当前能先做什么和下一步去哪；它只读本地状态，不创建 task、不调用外部服务，也不能关闭 14 LTG。</p>
        <DataLineageTable rows={usablePathCurrentCheckpointRows} />
      </div>
      <div aria-label="production hardening direct evidence matrix">
        <h3>生产硬化 direct evidence 准备矩阵</h3>
        <p className="risk-note">Storage、Worker、Tauri、CI/smoke/安全、DeepSeek governed executor、Streamlit legacy 和 14 LTG 下一步证据集中展示；只读，不创建 task，不外联，不关闭 LTG。</p>
        <MetricGrid
          items={[
            { label: "matrix status", value: String(productionHardeningSummary.status ?? "missing"), tone: productionHardeningRows.length ? "warn" : "neutral" },
            { label: "hardening areas", value: Number(productionHardeningSummary.hardening_area_count ?? productionHardeningRows.length) },
            { label: "LTG rows", value: Number(productionHardeningSummary.ltg_direct_evidence_row_count ?? productionHardeningLtgRows.length) },
            { label: "strict closeout", value: String(productionHardeningSummary.strict_closeout ?? "0/14"), tone: Number(productionHardeningSummary.strict_closeout_done_count ?? 0) === 0 ? "warn" : "good" },
            { label: "storage", value: productionHardeningSummary.storage_boundary_visible === true ? "visible" : "missing", tone: productionHardeningSummary.storage_boundary_visible === true ? "warn" : "neutral" },
            { label: "worker", value: productionHardeningSummary.worker_boundary_visible === true ? "visible" : "missing", tone: productionHardeningSummary.worker_boundary_visible === true ? "warn" : "neutral" },
            { label: "tauri", value: productionHardeningSummary.tauri_boundary_visible === true ? "visible" : "missing", tone: productionHardeningSummary.tauri_boundary_visible === true ? "warn" : "neutral" },
            { label: "CI/smoke/safety", value: productionHardeningSummary.ci_smoke_security_boundary_visible === true ? "visible" : "missing", tone: productionHardeningSummary.ci_smoke_security_boundary_visible === true ? "warn" : "neutral" },
            { label: "DeepSeek", value: productionHardeningSummary.deepseek_governed_executor_nonblocking === true ? "nonblocking" : "missing", tone: productionHardeningSummary.deepseek_governed_executor_nonblocking === true ? "good" : "neutral" },
            { label: "Streamlit", value: productionHardeningSummary.streamlit_legacy_admin_debug_only === true ? "legacy/admin/debug" : "missing", tone: productionHardeningSummary.streamlit_legacy_admin_debug_only === true ? "good" : "neutral" },
            { label: "safe closeout start", value: productionHardeningSummary.safe_to_start_one_ltg_strict_closeout === true ? "ready" : "blocked", tone: productionHardeningSummary.safe_to_start_one_ltg_strict_closeout === true ? "bad" : "good" },
            { label: "external calls", value: productionHardeningSummary.external_calls_triggered === true ? "存在" : "无", tone: productionHardeningSummary.external_calls_triggered === true ? "bad" : "good" }
          ]}
        />
        <MetricGrid
          items={[
            { label: "gate status", value: String(productionHardeningGateSummary.status ?? "missing"), tone: productionHardeningGateRows.length ? "warn" : "neutral" },
            { label: "gate rows", value: Number(productionHardeningGateSummary.gate_row_count ?? productionHardeningGateRows.length) },
            { label: "local evidence areas", value: Number(productionHardeningGateSummary.local_direct_evidence_area_count ?? 0), tone: Number(productionHardeningGateSummary.local_direct_evidence_area_count ?? 0) ? "warn" : "neutral" },
            { label: "remote CI review", value: productionHardeningGateSummary.latest_remote_run_verified_green === true ? "green" : "pending", tone: productionHardeningGateSummary.latest_remote_run_verified_green === true ? "bad" : "good" },
            { label: "read only gates", value: productionHardeningGateSummary.all_gates_are_read_only === true, tone: productionHardeningGateSummary.all_gates_are_read_only === true ? "good" : "warn" },
            { label: "closeout blocked", value: productionHardeningGateSummary.all_gates_block_strict_closeout === true, tone: productionHardeningGateSummary.all_gates_block_strict_closeout === true ? "good" : "bad" },
            { label: "production pending", value: productionHardeningGateSummary.all_gates_production_pending === true, tone: productionHardeningGateSummary.all_gates_production_pending === true ? "warn" : "bad" },
            { label: "external calls", value: productionHardeningGateSummary.external_calls_triggered === true ? "存在" : "无", tone: productionHardeningGateSummary.external_calls_triggered === true ? "bad" : "good" }
          ]}
        />
        <p className="risk-note">Gate 表只把散落的 Storage / Worker / Tauri / release gate / DeepSeek / Streamlit 证据摘要接到同一处；local evidence 只是下一步收口依据，remote CI 和 safety gate 未满足前仍不能 strict closeout。</p>
        <MetricGrid
          items={[
            { label: "work order status", value: String(ltgStrictCloseoutWorkOrderSummary.status ?? "missing"), tone: ltgStrictCloseoutWorkOrderRows.length ? "warn" : "neutral" },
            { label: "work orders", value: Number(ltgStrictCloseoutWorkOrderSummary.work_order_row_count ?? ltgStrictCloseoutWorkOrderRows.length) },
            { label: "recommended first", value: Number(ltgStrictCloseoutWorkOrderSummary.recommended_first_candidate_count ?? 0), tone: Number(ltgStrictCloseoutWorkOrderSummary.recommended_first_candidate_count ?? 0) ? "warn" : "neutral" },
            { label: "select one LTG", value: ltgStrictCloseoutWorkOrderSummary.ready_to_select_one_ltg_next_slice === true, tone: ltgStrictCloseoutWorkOrderSummary.ready_to_select_one_ltg_next_slice === true ? "warn" : "neutral" },
            { label: "closeout claim", value: ltgStrictCloseoutWorkOrderSummary.strict_closeout_claim_allowed === true ? "allowed" : "blocked", tone: ltgStrictCloseoutWorkOrderSummary.strict_closeout_claim_allowed === true ? "bad" : "good" },
            { label: "current-head required", value: ltgStrictCloseoutWorkOrderSummary.all_rows_require_current_head_direct_evidence === true, tone: ltgStrictCloseoutWorkOrderSummary.all_rows_require_current_head_direct_evidence === true ? "good" : "warn" },
            { label: "remote CI required", value: ltgStrictCloseoutWorkOrderSummary.all_rows_require_remote_ci_review === true, tone: ltgStrictCloseoutWorkOrderSummary.all_rows_require_remote_ci_review === true ? "good" : "warn" },
            { label: "external calls", value: ltgStrictCloseoutWorkOrderSummary.external_calls_triggered === true ? "存在" : "无", tone: ltgStrictCloseoutWorkOrderSummary.external_calls_triggered === true ? "bad" : "good" }
          ]}
        />
        <p className="risk-note">Work order 可以用来选择下一轮只做一个 LTG 的 direct evidence 收集；它不代表已经能关闭 LTG，也不允许把 local receipt、matrix、mock、sanitizer 或 dry-run 当 production evidence。</p>
        <MetricGrid
          items={[
            { label: "spine status", value: String(ltgStrictCloseoutEvidenceSpineSummary.status ?? "missing"), tone: ltgStrictCloseoutEvidenceSpineRows.length ? "warn" : "neutral" },
            { label: "LTG spine", value: `${Number(ltgStrictCloseoutEvidenceSpineSummary.spine_visible_count ?? 0)}/${Number(ltgStrictCloseoutEvidenceSpineSummary.spine_total_count ?? 14)}`, tone: ltgStrictCloseoutEvidenceSpineSummary.all_ltg_handoffs_visible === true ? "good" : "bad" },
            { label: "handoff summaries", value: `${Number(ltgStrictCloseoutEvidenceSpineSummary.handoff_summary_visible_count ?? 0)}/${Number(ltgStrictCloseoutEvidenceSpineSummary.handoff_summary_total_count ?? 0)}`, tone: ltgStrictCloseoutEvidenceSpineSummary.all_handoff_summaries_visible === true ? "good" : "warn" },
            { label: "missing LTG", value: Array.isArray(ltgStrictCloseoutEvidenceSpineSummary.spine_missing_ltg_ids) ? ltgStrictCloseoutEvidenceSpineSummary.spine_missing_ltg_ids.length : 0, tone: Array.isArray(ltgStrictCloseoutEvidenceSpineSummary.spine_missing_ltg_ids) && ltgStrictCloseoutEvidenceSpineSummary.spine_missing_ltg_ids.length ? "bad" : "good" },
            { label: "strict closeout", value: String(ltgStrictCloseoutEvidenceSpineSummary.strict_closeout ?? "0/14"), tone: Number(ltgStrictCloseoutEvidenceSpineSummary.strict_closeout_done_count ?? 0) === 0 ? "warn" : "good" },
            { label: "closeout claim", value: ltgStrictCloseoutEvidenceSpineSummary.strict_closeout_claim_allowed === true ? "allowed" : "blocked", tone: ltgStrictCloseoutEvidenceSpineSummary.strict_closeout_claim_allowed === true ? "bad" : "good" },
            { label: "remote split", value: ltgStrictCloseoutEvidenceSpineSummary.remote_review_split_required === true ? "required" : "missing", tone: ltgStrictCloseoutEvidenceSpineSummary.remote_review_split_required === true ? "good" : "bad" },
            { label: "release review", value: ltgStrictCloseoutEvidenceSpineSummary.requires_release_review_after_remote_green === true ? "required" : "missing", tone: ltgStrictCloseoutEvidenceSpineSummary.requires_release_review_after_remote_green === true ? "good" : "bad" },
            { label: "external calls", value: ltgStrictCloseoutEvidenceSpineSummary.external_calls_triggered === true ? "存在" : "无", tone: ltgStrictCloseoutEvidenceSpineSummary.external_calls_triggered === true ? "bad" : "good" },
            { label: "real trading", value: ltgStrictCloseoutEvidenceSpineSummary.does_not_execute_trades === true ? "禁止" : "可能", tone: ltgStrictCloseoutEvidenceSpineSummary.does_not_execute_trades === true ? "good" : "bad" }
          ]}
        />
        <p className="risk-note">Strict closeout evidence spine 只把 14 个 LTG 的顶层 handoff 串成可查收清单；14/14 可见仍不是生产完成证据，必须继续经过 fresh local gate、匹配远端 CI、release review 和 safety scan。</p>
        <DataLineageTable rows={productionHardeningRows} />
        <DataLineageTable rows={productionHardeningGateRows} />
        <DataLineageTable rows={ltgStrictCloseoutWorkOrderRows} />
        <DataLineageTable rows={ltgStrictCloseoutEvidenceSpineReadableRows} />
        <DataLineageTable rows={productionHardeningLtgRows} />
      </div>
      <h3>14 个长期目标完成度</h3>
      <p className="risk-note">严格关闭数保持 {String(longTermGoalSummary.strict_closeout ?? "0/14")}；scaffold / preflight / mock / matrix / sanitizer / dry-run / local receipt 不能作为生产完成证据。</p>
      <MetricGrid
        items={[
          { label: "strict closeout", value: String(longTermGoalSummary.strict_closeout ?? "0/14"), tone: Number(longTermGoalSummary.strict_closeout_done_count ?? 0) === 0 ? "warn" : "good" },
          { label: "goals closed", value: Number(longTermGoalSummary.strict_closeout_done_count ?? 0) },
          { label: "goals total", value: Number(longTermGoalSummary.strict_closeout_total_count ?? 14) },
          { label: "goals remaining", value: Number(longTermGoalSummary.strict_closeout_remaining_count ?? 14), tone: Number(longTermGoalSummary.strict_closeout_remaining_count ?? 14) ? "warn" : "good" },
          { label: "review split coverage", value: `${Number(longTermGoalSummary.observed_review_split_complete_count ?? 0)}/${Number(longTermGoalSummary.goal_count ?? 14)}`, tone: longTermGoalSummary.observed_review_split_all_goals_covered === true ? "good" : "bad" },
          { label: "review split missing", value: Number(longTermGoalSummary.observed_review_split_missing_count ?? 0), tone: Number(longTermGoalSummary.observed_review_split_missing_count ?? 0) ? "bad" : "good" },
          { label: "local complete", value: Number(longTermGoalSummary.observed_local_complete_count ?? 0), tone: Number(longTermGoalSummary.observed_local_complete_count ?? 0) ? "warn" : "neutral" },
          { label: "remote review pending", value: Number(longTermGoalSummary.observed_remote_review_pending_count ?? 0), tone: Number(longTermGoalSummary.observed_remote_review_pending_count ?? 0) ? "warn" : "good" },
          { label: "release review pending", value: Number(longTermGoalSummary.observed_release_review_pending_count ?? 0), tone: Number(longTermGoalSummary.observed_release_review_pending_count ?? 0) ? "warn" : "good" },
          { label: "strict-ready goals", value: Number(longTermGoalSummary.observed_strict_closeout_ready_count ?? 0), tone: Number(longTermGoalSummary.observed_strict_closeout_ready_count ?? 0) ? "bad" : "good" },
          { label: "P6 handoff rows", value: usablePathStrictCloseoutHandoffRows.length, tone: usablePathStrictCloseoutHandoffRows.length ? "good" : "warn" },
          { label: "P6 direct evidence gates", value: p6DirectEvidenceReentryRows.length, tone: p6DirectEvidenceReentryRows.length ? "warn" : "good" },
          { label: "mostly stable guardrails", value: Number(longTermBucketCounts.mostly_stable_guardrail ?? 0) },
          { label: "real validation required", value: Number(longTermBucketCounts.real_validation_required ?? 0) },
          { label: "productionization required", value: Number(longTermBucketCounts.productionization_required ?? 0) },
          { label: "dependent retirement", value: Number(longTermBucketCounts.dependent_retirement_goal ?? 0) },
          { label: "later polish", value: Number(longTermBucketCounts.later_polish_goal ?? 0) }
        ]}
      />
      <div aria-label="usable path strict closeout handoff">
        <h3>P6 可用化到 14 LTG strict closeout 交接</h3>
        <p className="risk-note">这张表把 P0-P6 当前 checkpoint 对应回 14 LTG 的 direct evidence 下一步；P0-P5 是可用化路径，P6 是 strict closeout 回归门；它只读本地状态，不创建 task、不调用外部服务，也不能关闭任何 LTG。</p>
        <DataLineageTable rows={usablePathStrictCloseoutHandoffRows} />
      </div>
      <div aria-label="p6 direct evidence reentry gates">
        <h3>P6 direct evidence 回归门禁</h3>
        <p className="risk-note">这张表只列出回到 14 LTG strict closeout 前必须满足的 current-head direct evidence 门禁；它不是完成声明，也不会从页面渲染、搜索输入或 GET cache 创建 task。</p>
        <DataLineageTable rows={p6DirectEvidenceReentryRows} />
      </div>
      <div aria-label="ltg11 release gate remote review split">
        <h3>LTG-11 release gate 远端查收分离</h3>
        <p className="risk-note">这里把本地 gate、push 边界、匹配 HEAD 的远端 Actions 查收和 release review 拆开显示；本地领先远端或 receipt head 不匹配时，上一轮绿色 run 不能证明当前 HEAD，也不能关闭 LTG。</p>
        <MetricGrid
          items={[
            {
              label: "split status",
              value: String(releaseGateRemoteReviewSplitSummary.status ?? "missing"),
              tone: releaseGateRemoteReviewSplitSummary.latest_remote_run_verified_green === true ? "warn" : "good"
            },
            {
              label: "current HEAD",
              value: releaseGatePublishStatusLabel(releaseGateCurrentHeadPublishStatus),
              tone: releaseGateCurrentHeadPushRequired ? "warn" : "good"
            },
            {
              label: "push required",
              value: releaseGateCurrentHeadPushRequired,
              tone: releaseGateCurrentHeadPushRequired ? "warn" : "good"
            },
            {
              label: "current ahead",
              value: releaseGateCurrentHeadAheadCount,
              tone: releaseGateCurrentHeadAheadCount ? "warn" : "good"
            },
            {
              label: "waiting push",
              value: releaseGateRemoteReviewWaitingForPush,
              tone: releaseGateRemoteReviewWaitingForPush ? "warn" : "good"
            },
            {
              label: "next publish",
              value: releaseGatePublishStepLabel(releaseGateNextPublishStep),
              tone: releaseGateCurrentHeadPushRequired ? "warn" : "good"
            },
            {
              label: "remote receipt head",
              value: releaseGateRemoteReviewSplitSummary.remote_ci_review_receipt_head_matches_current === true ? "matches" : "mismatch",
              tone: releaseGateRemoteReviewSplitSummary.remote_ci_review_receipt_head_matches_current === true ? "good" : "warn"
            },
            {
              label: "remote green",
              value: releaseGateRemoteReviewSplitSummary.latest_remote_run_verified_green === true,
              tone: releaseGateRemoteReviewSplitSummary.latest_remote_run_verified_green === true ? "warn" : "good"
            },
            {
              label: "worktree clean",
              value: releaseGateRemoteReviewSplitSummary.local_worktree_clean === true,
              tone: releaseGateRemoteReviewSplitSummary.local_worktree_clean === true ? "good" : "warn"
            },
            {
              label: "release gate",
              value: releaseGateRemoteReviewSplitSummary.release_gate_complete === true ? "complete" : "blocked",
              tone: releaseGateRemoteReviewSplitSummary.release_gate_complete === true ? "bad" : "good"
            },
            {
              label: "strict closeout",
              value: releaseGateRemoteReviewSplitSummary.strict_closeout_ready === true ? "ready" : "blocked",
              tone: releaseGateRemoteReviewSplitSummary.strict_closeout_ready === true ? "bad" : "good"
            },
            {
              label: "GitHub API from GET",
              value: releaseGateRemoteReviewSplitSummary.github_api_called === true ? "called" : "not called",
              tone: releaseGateRemoteReviewSplitSummary.github_api_called === true ? "bad" : "good"
            }
          ]}
        />
        <DataLineageTable rows={[releaseGateRemoteReviewSplitSummary]} />
        <DataLineageTable rows={releaseGateRemoteReviewSplitRows} />
      </div>
      <h3>14 LTG acceptance runway</h3>
      <p className="risk-note">这张表把每个长期目标的优先级、下一步验收动作和 observed pending 数集中到一处；它只读已有 roadmap/cache 合同，不创建任务、不调用外部服务，也不能关闭目标。</p>
      <DataLineageTable rows={ltgAcceptanceRunwayRows} />
      <h3>Legacy Bug / UX Audit first-round intake</h3>
      <p className="risk-note">这张审计 intake 只在迁移状态页展示：它告诉下一次复核要收集哪些用户观察、lineage、替代入口和冻结路径；第一轮不能升级 KEEP，也不能让旧模块进入普通用户入口。</p>
      <MetricGrid
        items={[
          { label: "intake status", value: String(legacyAuditFirstRoundIntake.status ?? "missing") },
          { label: "focus workflows", value: Number(legacyAuditFirstRoundIntake.focus_workflow_count ?? legacyAuditFirstRoundIntakeRows.length) },
          { label: "required fields", value: legacyAuditFirstRoundRequiredFields.length },
          { label: "safe refs", value: legacyAuditSafeAttachmentSources.length },
          { label: "forbidden refs", value: legacyAuditForbiddenAttachmentSources.length, tone: legacyAuditForbiddenAttachmentSources.length ? "warn" : "good" },
          { label: "row count", value: legacyAuditFirstRoundIntakeRows.length },
          { label: "KEEP promotion", value: legacyAuditFirstRoundIntake.keep_promotion_allowed_this_round === true ? "allowed" : "blocked", tone: legacyAuditFirstRoundIntake.keep_promotion_allowed_this_round === true ? "bad" : "good" },
          { label: "ordinary entry", value: legacyAuditFirstRoundIntake.ordinary_entry_promotion_allowed_this_round === true ? "allowed" : "blocked", tone: legacyAuditFirstRoundIntake.ordinary_entry_promotion_allowed_this_round === true ? "bad" : "good" },
          { label: "external calls", value: legacyAuditFirstRoundIntake.external_calls_triggered === true ? "存在" : "无", tone: legacyAuditFirstRoundIntake.external_calls_triggered === true ? "bad" : "good" },
          { label: "real trading", value: legacyAuditFirstRoundIntake.does_not_execute_trades === false ? "可能" : "禁止", tone: legacyAuditFirstRoundIntake.does_not_execute_trades === false ? "bad" : "good" },
          { label: "production evidence", value: String(legacyAuditFirstRoundIntake.production_evidence_rule ?? "not_production_evidence") }
        ]}
      />
      <PacketCard title="Legacy audit first-round workbench" subtitle="focus workflow / required fields / safe attachment sources；只读，不升级 KEEP" status="legacy_audit_first_round_workbench">
        <p className="risk-note">首轮只收集用户观察、legacy UX/bug or patchwork、data lineage、替代入口、冻结旧路径和安全附件引用；不能贴 raw packet、raw log、token/key、未脱敏模型输出或 generated artifact。</p>
        <p className="risk-note">这些表是 reviewer checklist，不是 direct UX/bug evidence；没有 safe screenshot reference、redacted reviewer note 或 safe log summary 前，KEEP 和 ordinary entry 仍然 blocked。</p>
        <MetricGrid
          items={[
            { label: "本轮审计对象", value: legacyAuditObservationFocusWorkflow },
            { label: "下一步", value: legacyAuditObservationNextClick },
            { label: "附件规则", value: legacyAuditObservationEvidenceRule, tone: "warn" },
            { label: "任务边界", value: legacyAuditObservationBoundary, tone: "good" }
          ]}
        />
        <div className="actions">
          {legacyAuditObservationTargets.map((target) => (
            <button key={target.key} onClick={() => launchLegacyAuditObservationDryRun(target)}>
              {target.next_click}
            </button>
          ))}
        </div>
        {legacyAuditObservationError && <p className="risk-note">{legacyAuditObservationError}</p>}
        <MetricGrid
          items={[
            { label: "latest observation", value: String(legacyAuditLatestObservation.status ?? "not_run") },
            { label: "observation task", value: String(legacyAuditLatestObservation.task_status ?? "missing") },
            { label: "direct evidence", value: legacyAuditLatestObservation.direct_user_evidence_recorded === true, tone: legacyAuditLatestObservation.direct_user_evidence_recorded === true ? "good" : "warn" },
            { label: "KEEP review", value: legacyAuditLatestObservation.direct_evidence_ready_for_keep_review === true ? "ready" : "blocked", tone: legacyAuditLatestObservation.direct_evidence_ready_for_keep_review === true ? "bad" : "good" },
            { label: "KEEP promotion", value: legacyAuditLatestObservation.keep_promotion_allowed_this_round === true ? "allowed" : "blocked", tone: legacyAuditLatestObservation.keep_promotion_allowed_this_round === true ? "bad" : "good" },
            { label: "ordinary entry", value: legacyAuditLatestObservation.ordinary_entry_promotion_allowed_this_round === true ? "allowed" : "blocked", tone: legacyAuditLatestObservation.ordinary_entry_promotion_allowed_this_round === true ? "bad" : "good" },
            { label: "Streamlit fallback", value: legacyAuditLatestObservation.streamlit_fallback_retirement_allowed === true ? "retirement allowed" : "retained", tone: legacyAuditLatestObservation.streamlit_fallback_retirement_allowed === true ? "bad" : "good" },
            { label: "production evidence", value: legacyAuditLatestObservation.production_evidence === true, tone: legacyAuditLatestObservation.production_evidence === true ? "bad" : "good" },
            { label: "external calls", value: legacyAuditLatestObservation.external_calls_triggered === true ? "存在" : "无", tone: legacyAuditLatestObservation.external_calls_triggered === true ? "bad" : "good" },
            { label: "row count", value: Number(legacyAuditLatestObservation.row_count ?? legacyAuditLatestObservationRows.length) }
          ]}
        />
        <p className="risk-note">Latest observation 只是 direct-evidence intake 回放；KEEP review、ordinary entry 和 Streamlit fallback retirement 都保持 blocked，直到单独补齐完整 Legacy Bug / UX Audit 直接证据。</p>
        <TaskLaunchReceipt receipt={legacyAuditObservationReceipt} />
        <TaskStatusPanel taskId={legacyAuditObservationTaskId} onSuccess={refreshMigrationStatus} />
        <DataLineageTable rows={[legacyAuditLatestObservation]} />
        <DataLineageTable rows={legacyAuditLatestObservationRows} />
        <DataLineageTable rows={legacyAuditObservationTargets} />
        <DataLineageTable rows={legacyAuditFirstRoundFocusRows} />
        <DataLineageTable rows={legacyAuditRequiredFieldRows} />
        <DataLineageTable rows={legacyAuditAttachmentSourceRows} />
      </PacketCard>
      <DataLineageTable rows={[legacyAuditFirstRoundIntake]} />
      <DataLineageTable rows={legacyAuditFirstRoundIntakeRows} />
      <h3>LTG next acceptance action queue</h3>
      <p className="risk-note">这里集中显示 P1-P5 的下一步显式验收路径：只读展示允许的 POST 路由、未来 provider/worker/model/browser/storage 证据和禁止事项；GET cache 和页面渲染不会创建任务或调用外部服务。</p>
      <p className="risk-note">按钮会先看 `next_local_step_preview_rows`：如果缺前置本地回执、scope hash、review hash 或执行请求 task id，就只展示缺口并禁用按钮，避免生成已知 blocked 的回执。</p>
      <p className="risk-note">`future_handoff_preview_rows` 只把本地 execution-request 已绑定的未来 provider/worker payload 摘要列出来；它不提交 provider task、不调用 Tushare/DeepSeek/GitHub，也不能关闭 LTG。</p>
      <p className="risk-note">LTG-01 producer cache refresh 支撑 handoff 只显示本地 readiness 和 execution-request route；它不新增按钮、不写 cache、不调用 provider，也不是 trade_cal provider-backed acceptance。</p>
      <p className="risk-note">handoff ready 还要求本地 execution-request receipt 已落到 SQLite；memory-only receipt 只算临时可见，不作为跨进程验收证据。</p>
      <div className="actions">
        {ltgNextAcceptanceActionRows.map((row) => {
          const nextLocalStep = String(row.next_local_step ?? "");
          const nextLocalStepReady = row.next_local_step_ready_for_clean_receipt === true;
          const disabled = !nextLocalStep.startsWith("POST /api/") || !nextLocalStepReady;
          return (
            <button
              title={disabled ? String(row.next_local_step_disabled_reason ?? "local receipt prerequisite missing") : ""}
              disabled={disabled}
              key={String(row.queue_id ?? row.action_label)}
              onClick={() => launchLtgNextAction(row)}
            >
              {String(row.priority ?? "LTG")} {String(row.action_label ?? row.queue_id ?? "next action")}
            </button>
          );
        })}
      </div>
      {ltgNextActionError && <p className="risk-note">{ltgNextActionError}</p>}
      <TaskLaunchReceipt receipt={ltgNextActionReceipt} />
      <TaskStatusPanel taskId={ltgNextActionTaskId} onSuccess={refreshMigrationStatus} />
      <MetricGrid
        items={[
          { label: "near-term actions", value: ltgNextAcceptanceActionRows.length },
          { label: "observed local receipts", value: observedLocalReceiptSteps, tone: observedLocalReceiptSteps ? "good" : "warn" },
          { label: "ready local receipts", value: readyLocalReceiptSteps, tone: readyLocalReceiptSteps ? "good" : "warn" },
          { label: "blocked local receipts", value: blockedLocalReceiptSteps, tone: blockedLocalReceiptSteps ? "bad" : "good" },
          { label: "missing local receipts", value: missingLocalReceiptSteps, tone: missingLocalReceiptSteps ? "warn" : "good" },
          { label: "durable local receipts", value: durableLocalReceiptSteps, tone: durableLocalReceiptSteps ? "good" : "warn" },
          { label: "memory-only receipts", value: memoryOnlyLocalReceiptSteps, tone: memoryOnlyLocalReceiptSteps ? "bad" : "good" },
          { label: "local step rows", value: ltgNextAcceptanceLocalStepRows.length },
          {
            label: "ready local buttons",
            value: ltgNextAcceptanceActionRows.filter((row) => row.next_local_step_ready_for_clean_receipt === true).length,
            tone: ltgNextAcceptanceActionRows.some((row) => row.next_local_step_ready_for_clean_receipt === true) ? "good" : "warn"
          },
          {
            label: "handoff previews ready",
            value: ltgFutureHandoffPreviewRows.filter((row) => row.handoff_ready_from_local_receipt === true).length,
            tone: ltgFutureHandoffPreviewRows.some((row) => row.handoff_ready_from_local_receipt === true) ? "good" : "warn"
          },
          {
            label: "producer refresh handoffs",
            value: ltgCurrentEvidenceProducerCacheRefreshHandoffRows.length,
            tone: ltgCurrentEvidenceProducerCacheRefreshHandoffRows.length ? "good" : "warn"
          },
          {
            label: "trade_cal evidence handoffs",
            value: ltgTradeCalProviderAcceptanceEvidenceHandoffRows.length,
            tone: ltgTradeCalProviderAcceptanceEvidenceHandoffRows.length ? "good" : "warn"
          },
          {
            label: "lookup creates task",
            value: ltgNextAcceptanceActionRows.some((row) => row.local_receipt_lookup_creates_task === true),
            tone: ltgNextAcceptanceActionRows.some((row) => row.local_receipt_lookup_creates_task === true) ? "bad" : "good"
          },
          {
            label: "lookup calls provider",
            value: ltgNextAcceptanceActionRows.some((row) => row.local_receipt_lookup_calls_provider === true),
            tone: ltgNextAcceptanceActionRows.some((row) => row.local_receipt_lookup_calls_provider === true) ? "bad" : "good"
          }
        ]}
      />
      <DataLineageTable rows={ltgNextAcceptanceReceiptRows} />
      <DataLineageTable rows={ltgNextAcceptancePreviewRows} />
      <DataLineageTable rows={ltgFutureHandoffPreviewRows} />
      <p className="risk-note">LTG-01 provider acceptance handoff 只显示 prior provider call-ledger / freshness replay / failure-mode evidence、本地 promotion review、fresh local gate、remote CI review、release review 和 strict closeout 的分离状态；它不从 GET cache 创建任务、不调用 Tushare/GitHub，也不能关闭 freshness production gate。</p>
      <DataLineageTable rows={ltgTradeCalProviderAcceptanceEvidenceHandoffRows} />
      <p className="risk-note">LTG-02 target-sample handoff 只显示本地 execution-request、已有 provider call-ledger 可见性、durable recipe 和仍缺的 full-interface / storage promotion / remote review；它不从 GET cache 创建任务、不调用 Tushare，也不能关闭 Tushare 生产流水线。</p>
      <DataLineageTable rows={ltgTushareTargetSampleEvidenceHandoffRows} />
      <p className="risk-note">LTG-03 Factor Test handoff 只显示本地 scope ticket、execution recipe、execution-request、durable recipe 和仍缺的 provider call-ledger / sample rows / rolling-cost-neutralization-bias / full-market / promotion review；它不从 GET cache 创建任务、不调用 Tushare，也不能关闭 Factor Test 生产验证。</p>
      <DataLineageTable rows={ltgFactorTestProviderValidationHandoffRows} />
      <p className="risk-note">LTG-04 Factor Universe handoff 只显示本地 worker-batch scope ticket、execution-request、local research receipt、worker dependency preflight 和仍缺的 worker runtime / storage-read / rank-zscore-neutralization / full-pool / promotion review；它不从 GET cache 创建任务、不启动 Celery/Redis，也不能关闭 Factor Universe 生产验证。</p>
      <DataLineageTable rows={ltgFactorUniverseWorkerBatchHandoffRows} />
      <p className="risk-note">LTG-05 Storage handoff 只显示本地 readiness / activation / execution recipe / execution-request / phase-A evidence / durable recipe 和仍缺的 production promotion closeout / remote CI review；它不从 GET cache 创建任务、不写 Parquet/manifest、不删除 artifacts，也不能关闭 Storage 生产验证。</p>
      <DataLineageTable rows={ltgStoragePhysicalExecutionHandoffRows} />
      <p className="risk-note">LTG-06 Worker handoff 只显示本地 dependency preflight / runtime QA request / dry-run / local fallback execution / durable recipe / promotion review 和仍缺的 production worker closeout / remote CI review；它不从 GET cache 创建任务、不启动 Celery/Redis、不派发 provider/model task，也不能关闭 Worker 生产验证。</p>
      <DataLineageTable rows={ltgWorkerRuntimeQaHandoffRows} />
      <DataLineageTable rows={ltgCurrentEvidenceProducerCacheRefreshHandoffRows} />
      <DataLineageTable rows={ltgNextAcceptanceLocalStepRows} />
      <DataLineageTable rows={ltgNextAcceptanceActionRows} />
      <DataLineageTable rows={longTermGoalRows} />
      <h3>LTG-13 下一票雷达 promotion / legacy review</h3>
      <p className="risk-note">这里单独展示下一票雷达的本地 promotion dry-run 与 legacy retirement review：它们只说明本地审查票据是否可见、是否进入 local review、还有多少生产证据 blocker；不能关闭 LTG-13，也不能退掉 legacy fallback。</p>
      <MetricGrid
        items={[
          {
            label: "promotion dry-run",
            value: String(candidateRadarGoalRow.observed_production_promotion_dry_run_status ?? "missing"),
            tone: candidateRadarGoalRow.observed_production_promotion_dry_run_ready_for_local_review === true ? "warn" : "neutral"
          },
          {
            label: "receipt visible",
            value: candidateRadarGoalRow.observed_production_promotion_dry_run_visible === true,
            tone: candidateRadarGoalRow.observed_production_promotion_dry_run_visible === true ? "good" : "warn"
          },
          {
            label: "local review ready",
            value: candidateRadarGoalRow.observed_production_promotion_dry_run_ready_for_local_review === true,
            tone: candidateRadarGoalRow.observed_production_promotion_dry_run_ready_for_local_review === true ? "warn" : "neutral"
          },
          {
            label: "production blockers",
            value: Number(candidateRadarGoalRow.observed_production_promotion_dry_run_production_blocker_count ?? 0),
            tone: Number(candidateRadarGoalRow.observed_production_promotion_dry_run_production_blocker_count ?? 0) ? "bad" : "good"
          },
          {
            label: "can close LTG-13",
            value: candidateRadarGoalRow.observed_production_promotion_dry_run_can_close_goal === true,
            tone: candidateRadarGoalRow.observed_production_promotion_dry_run_can_close_goal === true ? "bad" : "good"
          },
          {
            label: "legacy review",
            value: String(candidateRadarGoalRow.observed_legacy_retirement_review_status ?? "missing"),
            tone: candidateRadarGoalRow.observed_legacy_retirement_review_ready_for_local_review === true ? "warn" : "neutral"
          },
          {
            label: "legacy receipt visible",
            value: candidateRadarGoalRow.observed_legacy_retirement_review_visible === true,
            tone: candidateRadarGoalRow.observed_legacy_retirement_review_visible === true ? "good" : "warn"
          },
          {
            label: "legacy blockers",
            value: Number(candidateRadarGoalRow.observed_legacy_retirement_review_production_blocker_count ?? 0),
            tone: Number(candidateRadarGoalRow.observed_legacy_retirement_review_production_blocker_count ?? 0) ? "bad" : "good"
          },
          {
            label: "can retire legacy",
            value: candidateRadarGoalRow.observed_legacy_retirement_review_can_close_goal === true,
            tone: candidateRadarGoalRow.observed_legacy_retirement_review_can_close_goal === true ? "bad" : "good"
          }
        ]}
      />
      <DataLineageTable rows={[candidateRadarGoalRow]} />
      <h3>LTG-14 动效生产证据</h3>
      <p className="risk-note">这里单独展示动效生产阶段证据：只读取本地静态合同和按钮门控本地回执，显示视觉 QA、性能 trace、CI/release evidence 和 production motion 仍是否 pending；不会打开浏览器、调用 GitHub 或推广截图。</p>
      <MetricGrid
        items={[
          {
            label: "motion stage scope",
            value: String(motionGoalObservedRow.status ?? "missing"),
            tone: motionGoalObservedRow.status ? "good" : "warn"
          },
          {
            label: "motion pending",
            value: Number(motionGoalObservedRow.pending_stage_count ?? 0),
            tone: Number(motionGoalObservedRow.pending_stage_count ?? 0) ? "warn" : "good"
          },
          {
            label: "local evidence rows",
            value: Number(motionGoalObservedRow.local_evidence_stage_count ?? 0),
            tone: Number(motionGoalObservedRow.local_evidence_stage_count ?? 0) ? "good" : "warn"
          },
          {
            label: "visual QA promoted",
            value: motionGoalObservedRow.browser_visual_qa_promoted === true,
            tone: motionGoalObservedRow.browser_visual_qa_promoted === true ? "good" : "warn"
          },
          {
            label: "performance promoted",
            value: motionGoalObservedRow.browser_performance_promoted === true,
            tone: motionGoalObservedRow.browser_performance_promoted === true ? "good" : "warn"
          },
          {
            label: "durable CI evidence",
            value: motionGoalObservedRow.durable_ci_evidence_complete === true,
            tone: motionGoalObservedRow.durable_ci_evidence_complete === true ? "good" : "warn"
          },
          {
            label: "production motion",
            value: motionGoalObservedRow.production_motion_complete === true,
            tone: motionGoalObservedRow.production_motion_complete === true ? "good" : "warn"
          },
          {
            label: "review gate",
            value: String(motionProductionHandoff.motion_visual_performance_promotion_review_status ?? "missing"),
            tone: motionProductionHandoff.motion_visual_performance_promotion_review_ready === true ? "good" : "warn"
          },
          {
            label: "next motion step",
            value: String(motionProductionQueueRow.next_local_step ?? "pending"),
            tone: motionProductionQueueRow.next_local_step_ready_for_clean_receipt === true ? "good" : "warn"
          },
          {
            label: "release evidence",
            value: motionProductionHandoff.requires_durable_ci_release_evidence === true ? "pending" : "ready",
            tone: motionProductionHandoff.requires_durable_ci_release_evidence === true ? "warn" : "good"
          }
        ]}
      />
      <p className="risk-note">Motion visual/performance promotion review 只把已审查的本地 visual/performance/reduced-motion evidence 接到 durable-local 链上；CI/release evidence、最终生产动效 review 和 LTG-12 交易隔离仍继续阻断 strict closeout。</p>
      <DataLineageTable rows={motionProductionReviewGateRows} />
      <DataLineageTable rows={[motionGoalObservedRow]} />
      <h3>LTG-12 真实交易隔离 release guard</h3>
      <p className="risk-note">release receipt 可作为研究客户端发布证据，但不是真实交易批准；这里单独下沉 p10_trade_isolation_release_guard，确认它不是 broker/order/trade-execution 集成，也不能绕过远端查收和 release review。</p>
      <MetricGrid
        items={[
          {
            label: "release receipt",
            value: String(tradeIsolationGoalObservedRow.trade_isolation_release_receipt_status ?? "missing"),
            tone: tradeIsolationGoalObservedRow.trade_isolation_release_receipt_ready === true ? "good" : "warn"
          },
          {
            label: "direct evidence",
            value: Number(tradeIsolationGoalObservedRow.direct_evidence_stage_count ?? 0),
            tone: Number(tradeIsolationGoalObservedRow.direct_evidence_stage_count ?? 0) ? "warn" : "neutral"
          },
          {
            label: "pending stages",
            value: Number(tradeIsolationGoalObservedRow.pending_stage_count ?? 0),
            tone: Number(tradeIsolationGoalObservedRow.pending_stage_count ?? 0) ? "warn" : "good"
          },
          {
            label: "real trading",
            value: tradeIsolationGoalObservedRow.real_trading_connected === true ? "connected" : "isolated",
            tone: tradeIsolationGoalObservedRow.real_trading_connected === true ? "bad" : "good"
          },
          {
            label: "broker adapter",
            value: tradeIsolationGoalObservedRow.broker_adapter_connected === true ? "connected" : "absent",
            tone: tradeIsolationGoalObservedRow.broker_adapter_connected === true ? "bad" : "good"
          },
          {
            label: "order endpoint",
            value: tradeIsolationGoalObservedRow.order_endpoint_present === true ? "present" : "absent",
            tone: tradeIsolationGoalObservedRow.order_endpoint_present === true ? "bad" : "good"
          },
          {
            label: "separate project",
            value: tradeIsolationGoalObservedRow.future_real_trading_requires_separate_project === true ? "required" : "missing",
            tone: tradeIsolationGoalObservedRow.future_real_trading_requires_separate_project === true ? "good" : "bad"
          },
          {
            label: "strict closeout",
            value: tradeIsolationGoalObservedRow.can_close_from_observed_row === true ? "ready" : "blocked",
            tone: tradeIsolationGoalObservedRow.can_close_from_observed_row === true ? "bad" : "good"
          }
        ]}
      />
      <DataLineageTable rows={tradeIsolationReleaseGuardRows} />
      <DataLineageTable rows={[tradeIsolationGoalObservedRow]} />
      <h3>LTG stage-scope observed rows</h3>
      <p className="risk-note">这些 observed rows 只读取本地 cache 或静态合同里的阶段清单，用来让长期目标总览对齐具体页面证据；它们不是生产完成证据。</p>
      <DataLineageTable rows={ltgStageScopeObservedRows} />
      <h3>Tushare / DeepSeek 联动审查</h3>
      <p className="risk-note">按四层审查：cache/render 安静、POST task 门控、task 内真实 provider/model execution、production promotion ledger；真实执行仍需后续显式验收。</p>
      <DataLineageTable rows={[tushareDeepseekLinkage]} />
      <DataLineageTable rows={tushareDeepseekModeLayerRows} />
      <DataLineageTable rows={tushareDeepseekLinkageRows} />
      <h3>Tushare / DeepSeek 联动 review 收据</h3>
      <p className="risk-note">该按钮只生成本地审查收据：不调用 Tushare、DeepSeek 或 GitHub，不创建 provider/model task，不执行真实交易，不修改 strategy action。</p>
      <DataLineageTable rows={[linkageReviewReceipt]} />
      <DataLineageTable rows={linkageReviewRows} />
      <h3>长期迁移原则</h3>
      <p className="risk-note">这组原则来自用户长期基线；React/Tauri 主入口只读展示，不重新估算、不创建任务。</p>
      <DataLineageTable rows={principleRows} />
      <h3>GET migration envelope call_ledger</h3>
      <DataLineageTable rows={cacheCallLedger} />
      <h3>GET migration envelope warnings</h3>
      <DataLineageTable rows={warningRows} />
      <JsonDetails title="长期目标优先级" data={longTermNextPriority} />
      <JsonDetails title="目标技术栈" data={packet.target_stack ?? []} />
      <JsonDetails title="迁移原则" data={packet.principles ?? []} />
      <JsonDetails title="迁移状态 packet" data={packet} />
    </PacketCard>
    </details>
    </>
  );
}
