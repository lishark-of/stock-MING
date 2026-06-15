import { useEffect, useState } from "react";
import { getMigrationStatus, postLtgNextAcceptanceLocalStep, postTushareDeepseekLinkageReview, type TaskCreationEnvelope } from "../api/client";
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
    return {
      operator_approved: true,
      execution_recipe_scope_hash: "",
      target_sample_acceptance_groups: ["margin_financing"],
      apis: ["margin_detail"],
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
    return {
      promotion_scope: "candidate_radar_production_promotion_local_dry_run",
      operator_approved: true,
      review_scope_hash: "",
      requested_by: "migration_status_ltg_queue",
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
  const linkageReviewPayload = (linkageReviewTask.payload_safe as Record<string, unknown> | undefined) ?? {};
  const postLinkageReviewReceipt = (linkageReviewPayload.tushare_deepseek_linkage_review_receipt as Record<string, unknown> | undefined) ?? {};
  const latestLinkageReviewRows = (packet.latest_tushare_deepseek_linkage_review_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const postLinkageReviewRows = (linkageReviewPayload.tushare_deepseek_linkage_review_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const linkageReviewReceipt = Object.keys(postLinkageReviewReceipt).length ? postLinkageReviewReceipt : latestTushareDeepseekLinkageReview;
  const linkageReviewRows = postLinkageReviewRows.length ? postLinkageReviewRows : latestLinkageReviewRows;
  const principles = Array.isArray(packet.principles) ? packet.principles : [];
  const packetAcceptanceRunwayRows = (packet.ltg_acceptance_runway_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const ltgNextAcceptanceActionRows = (packet.ltg_next_acceptance_action_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const ltgNextAcceptanceReceiptRows = ltgNextAcceptanceActionRows.map((row) => ({
    queue_id: row.queue_id,
    priority: row.priority,
    action_label: row.action_label,
    local_receipt_status: row.local_receipt_status,
    observed_steps: row.observed_local_receipt_step_count,
    missing_steps: row.missing_local_receipt_step_count,
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
      receipt_status: step.receipt_status,
      blocker_count: step.receipt_blocker_count,
      lookup_calls_provider: step.lookup_calls_provider,
      creates_task_from_lookup: step.creates_task_from_lookup
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
          { label: "planning baseline", value: baselinePolicy?.use_as_planning_baseline === true, tone: baselinePolicy?.use_as_planning_baseline === true ? "good" : "warn" },
          { label: "cache only", value: policy?.cache_only === true, tone: policy?.cache_only === true ? "good" : "warn" },
          { label: "external calls", value: policy?.external_calls_triggered === true ? "存在" : "无", tone: policy?.external_calls_triggered === true ? "bad" : "good" },
          { label: "real trading", value: policy?.does_not_execute_trades === false ? "可能" : "禁止", tone: policy?.does_not_execute_trades === false ? "bad" : "good" },
          { label: "strategy action", value: policy?.does_not_modify_strategy_action === false ? "会修改" : "不修改", tone: policy?.does_not_modify_strategy_action === false ? "bad" : "good" }
        ]}
      />
      <h3>固定进度表</h3>
      <DataLineageTable rows={progress} />
      <h3>14 个长期目标完成度</h3>
      <p className="risk-note">严格关闭数保持 {String(longTermGoalSummary.strict_closeout ?? "0/14")}；scaffold / preflight / mock / matrix / sanitizer / dry-run / local receipt 不能作为生产完成证据。</p>
      <MetricGrid
        items={[
          { label: "strict closeout", value: String(longTermGoalSummary.strict_closeout ?? "0/14"), tone: Number(longTermGoalSummary.strict_closeout_done_count ?? 0) === 0 ? "warn" : "good" },
          { label: "goals closed", value: Number(longTermGoalSummary.strict_closeout_done_count ?? 0) },
          { label: "goals total", value: Number(longTermGoalSummary.strict_closeout_total_count ?? 14) },
          { label: "goals remaining", value: Number(longTermGoalSummary.strict_closeout_remaining_count ?? 14), tone: Number(longTermGoalSummary.strict_closeout_remaining_count ?? 14) ? "warn" : "good" },
          { label: "mostly stable guardrails", value: Number(longTermBucketCounts.mostly_stable_guardrail ?? 0) },
          { label: "real validation required", value: Number(longTermBucketCounts.real_validation_required ?? 0) },
          { label: "productionization required", value: Number(longTermBucketCounts.productionization_required ?? 0) },
          { label: "dependent retirement", value: Number(longTermBucketCounts.dependent_retirement_goal ?? 0) },
          { label: "later polish", value: Number(longTermBucketCounts.later_polish_goal ?? 0) }
        ]}
      />
      <h3>14 LTG acceptance runway</h3>
      <p className="risk-note">这张表把每个长期目标的优先级、下一步验收动作和 observed pending 数集中到一处；它只读已有 roadmap/cache 合同，不创建任务、不调用外部服务，也不能关闭目标。</p>
      <DataLineageTable rows={ltgAcceptanceRunwayRows} />
      <h3>LTG next acceptance action queue</h3>
      <p className="risk-note">这里集中显示 P1/P2/P3 的下一步显式验收路径：只读展示允许的 POST 路由、未来 provider/worker 证据和禁止事项；GET cache 和页面渲染不会创建任务或调用外部服务。</p>
      <div className="actions">
        {ltgNextAcceptanceActionRows.map((row) => {
          const nextLocalStep = String(row.next_local_step ?? "");
          const disabled = !nextLocalStep.startsWith("POST /api/");
          return (
            <button
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
          { label: "missing local receipts", value: missingLocalReceiptSteps, tone: missingLocalReceiptSteps ? "warn" : "good" },
          { label: "local step rows", value: ltgNextAcceptanceLocalStepRows.length },
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
      <DataLineageTable rows={ltgNextAcceptanceLocalStepRows} />
      <DataLineageTable rows={ltgNextAcceptanceActionRows} />
      <DataLineageTable rows={longTermGoalRows} />
      <h3>LTG-13 下一票雷达 promotion dry-run</h3>
      <p className="risk-note">这里单独展示下一票雷达的本地 promotion dry-run：它只说明本地审查票据是否可见、是否进入 local review、还有多少生产证据 blocker；不能关闭 LTG-13。</p>
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
