import { useEffect, useState } from "react";
import { getMigrationStatus, postLegacyAuditObservationDryRun, postLtgNextAcceptanceLocalStep, postTushareDeepseekLinkageReview, type TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
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

  useEffect(() => {
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

  return (
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
      <h3>14 个长期目标完成度</h3>
      <p className="risk-note">严格关闭数保持 {String(longTermGoalSummary.strict_closeout ?? "0/14")}；scaffold / preflight / mock / matrix / sanitizer / dry-run / local receipt 不能作为生产完成证据。</p>
      <MetricGrid
        items={[
          { label: "strict closeout", value: String(longTermGoalSummary.strict_closeout ?? "0/14"), tone: Number(longTermGoalSummary.strict_closeout_done_count ?? 0) === 0 ? "warn" : "good" },
          { label: "goals closed", value: Number(longTermGoalSummary.strict_closeout_done_count ?? 0) },
          { label: "goals total", value: Number(longTermGoalSummary.strict_closeout_total_count ?? 14) },
          { label: "goals remaining", value: Number(longTermGoalSummary.strict_closeout_remaining_count ?? 14), tone: Number(longTermGoalSummary.strict_closeout_remaining_count ?? 14) ? "warn" : "good" },
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
      <p className="risk-note">这里单独展示动效生产阶段证据：只读取本地静态合同，显示视觉 QA、性能 trace、CI/release evidence 和 production motion 仍是否 pending；不会打开浏览器或推广截图。</p>
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
          }
        ]}
      />
      <DataLineageTable rows={[motionGoalObservedRow]} />
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
  );
}
