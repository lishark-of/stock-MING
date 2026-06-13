import { useEffect, useState } from "react";
import { getAuditCache, postMotionBrowserQaReview } from "../api/client";
import type { TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

export default function CallLedgerAudit() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<unknown>>([]);
  const [reviewReceipt, setReviewReceipt] = useState<TaskCreationEnvelope | null>(null);

  useEffect(() => {
    void getAuditCache().then((res) => {
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
      setCache(res.data);
    });
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const getRouteCoverage = (cache.get_route_coverage as Record<string, unknown> | undefined) ?? {};
  const taskPersistence = (cache.task_persistence as Record<string, unknown> | undefined) ?? {};
  const taskImplementation = (cache.task_implementation_status as Record<string, unknown> | undefined) ?? {};
  const releaseGateAudit = (cache.release_gate_readiness_audit as Record<string, unknown> | undefined) ?? {};
  const releaseGateRows = rows(cache.release_gate_readiness_rows);
  const releaseGateWorkflowRows = rows(cache.release_gate_workflow_rows);
  const ciNotificationTriage = (cache.ci_notification_triage_contract as Record<string, unknown> | undefined) ?? {};
  const ciNotificationTriageRows = rows(cache.ci_notification_triage_rows);
  const motionClarityAudit = (cache.motion_clarity_audit as Record<string, unknown> | undefined) ?? {};
  const motionClarityRows = rows(cache.motion_clarity_rows);
  const motionProductionQa = (cache.motion_production_qa_contract as Record<string, unknown> | undefined) ?? {};
  const motionProductionQaRows = rows(cache.motion_production_qa_rows);
  const motionKeynoteRoadmap = (cache.motion_keynote_roadmap_audit as Record<string, unknown> | undefined) ?? {};
  const motionKeynoteRoadmapRows = rows(cache.motion_keynote_roadmap_rows);
  const motionBrowserQaRunbook = (cache.motion_browser_qa_runbook_contract as Record<string, unknown> | undefined) ?? {};
  const motionBrowserQaRunbookRows = rows(cache.motion_browser_qa_runbook_rows);
  const motionBrowserQaMatrixRows = rows(cache.motion_browser_qa_matrix_rows);
  const motionBrowserQaEvidence = (cache.motion_browser_qa_evidence_contract as Record<string, unknown> | undefined) ?? {};
  const motionBrowserQaEvidenceRows = rows(cache.motion_browser_qa_evidence_rows);
  const motionBrowserQaReview = (cache.motion_browser_qa_review_contract as Record<string, unknown> | undefined) ?? {};
  const motionBrowserQaReviewRows = rows(cache.motion_browser_qa_review_rows);
  const parameterizedRoutes = rows(getRouteCoverage.parameterized_local_routes);
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const callLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<unknown> | undefined) ?? []);
  const modelStrategyRows = rows(cache.model_strategy_rows);
  const implementationRows = [
    { kind: "stub", count: taskImplementation.stub_task_count, task_types: Array.isArray(taskImplementation.stub_task_types) ? (taskImplementation.stub_task_types as unknown[]).join(" / ") : "" },
    { kind: "local_pipeline", count: taskImplementation.local_pipeline_task_count, task_types: Array.isArray(taskImplementation.local_pipeline_task_types) ? (taskImplementation.local_pipeline_task_types as unknown[]).join(" / ") : "" },
    { kind: "guarded_local", count: taskImplementation.guarded_local_task_count, task_types: Array.isArray(taskImplementation.guarded_local_task_types) ? (taskImplementation.guarded_local_task_types as unknown[]).join(" / ") : "" },
    { kind: "external_capable", count: taskImplementation.external_capable_task_count, task_types: Array.isArray(taskImplementation.external_capable_task_types) ? (taskImplementation.external_capable_task_types as unknown[]).join(" / ") : "" }
  ];

  async function launchMotionBrowserQaReview() {
    const response = await postMotionBrowserQaReview({
      review_scope: "motion_browser_qa_local_artifact",
      review_note: "button_gated_local_review_only"
    });
    setReviewReceipt(response);
    const refreshed = await getAuditCache();
    setCacheEnvelopeLedger(refreshed.call_ledger ?? []);
    setCacheEnvelopeWarnings(refreshed.warnings ?? []);
    setCache(refreshed.data);
  }

  return (
    <>
      <div className="page-head">
        <h1>调用审计</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "cache endpoints", value: counts.cache_endpoint_count as number | undefined },
          { label: "GET routes", value: counts.known_get_route_count as number | undefined },
          { label: "uncovered GET", value: counts.uncovered_get_route_count as number | undefined, tone: Number(counts.uncovered_get_route_count ?? 0) > 0 ? "bad" : "good" },
          { label: "tasks", value: counts.task_count as number | undefined },
          { label: "stub tasks", value: counts.stub_task_count as number | undefined },
          { label: "local pipelines", value: counts.local_pipeline_task_count as number | undefined },
          { label: "guarded local", value: counts.guarded_local_task_count as number | undefined },
          { label: "implemented local", value: counts.implemented_local_task_count as number | undefined },
          { label: "memory tasks", value: counts.memory_task_count as number | undefined },
          { label: "sqlite tasks", value: counts.sqlite_task_count as number | undefined },
          { label: "dedup tasks", value: counts.deduplicated_task_count as number | undefined },
          { label: "call ledger", value: counts.call_ledger_count as number | undefined },
          { label: "endpoint ledger", value: counts.endpoint_call_ledger_count as number | undefined },
          { label: "task ledger", value: counts.task_call_ledger_count as number | undefined },
          { label: "external calls", value: counts.external_call_count as number | undefined, tone: Number(counts.external_call_count ?? 0) > 0 ? "bad" : "good" },
          { label: "action risk", value: counts.action_risk_count as number | undefined, tone: Number(counts.action_risk_count ?? 0) > 0 ? "bad" : "good" },
          { label: "missing ledger", value: counts.missing_call_ledger_count as number | undefined, tone: Number(counts.missing_call_ledger_count ?? 0) > 0 ? "warn" : "good" },
          { label: "model strategy purposes", value: counts.model_strategy_purpose_count as number | undefined },
          { label: "model cache外联", value: counts.model_strategy_cache_read_external_call_count as number | undefined, tone: Number(counts.model_strategy_cache_read_external_call_count ?? 0) > 0 ? "bad" : "good" },
          { label: "release gate", value: releaseGateAudit.status as string | undefined, tone: releaseGateAudit.local_gate_ready === true ? "good" : "warn" },
          { label: "local gate ready", value: counts.release_gate_local_ready, tone: counts.release_gate_local_ready === true ? "good" : "warn" },
          { label: "CI mirror", value: counts.release_gate_ci_mirror_ready, tone: counts.release_gate_ci_mirror_ready === true ? "good" : "warn" },
          { label: "gate blockers", value: counts.release_gate_blocker_count as number | undefined, tone: Number(counts.release_gate_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "gate checks", value: counts.release_gate_check_count as number | undefined },
          { label: "workflow files", value: counts.release_gate_workflow_count as number | undefined },
          { label: "CI mail triage", value: ciNotificationTriage.status as string | undefined, tone: ciNotificationTriage.remote_actions_status_known === true ? "good" : "warn" },
          { label: "remote log needed", value: counts.ci_notification_pending_remote_evidence_count as number | undefined, tone: Number(counts.ci_notification_pending_remote_evidence_count ?? 0) > 0 ? "warn" : "good" },
          { label: "motion clarity", value: motionClarityAudit.status as string | undefined, tone: motionClarityAudit.static_ready === true ? "good" : "warn" },
          { label: "motion blockers", value: counts.motion_clarity_blocker_count as number | undefined, tone: Number(counts.motion_clarity_blocker_count ?? 0) > 0 ? "bad" : "good" },
          { label: "motion visual QA", value: motionClarityAudit.visual_qa_complete === true ? "完成" : "待验收", tone: motionClarityAudit.visual_qa_complete === true ? "good" : "warn" },
          { label: "motion prod QA", value: motionProductionQa.status as string | undefined, tone: motionProductionQa.local_motion_qa_ready === true ? "good" : "warn" },
          { label: "motion prod blockers", value: counts.motion_production_blocker_count as number | undefined, tone: Number(counts.motion_production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "motion perf pending", value: counts.motion_performance_pending_count as number | undefined, tone: Number(counts.motion_performance_pending_count ?? 0) > 0 ? "warn" : "good" },
          { label: "keynote roadmap", value: motionKeynoteRoadmap.status as string | undefined, tone: motionKeynoteRoadmap.roadmap_ready === true ? "good" : "warn" },
          { label: "keynote blockers", value: counts.motion_keynote_promotion_blocker_count as number | undefined, tone: Number(counts.motion_keynote_promotion_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "keynote visual", value: counts.motion_keynote_visual_required_count as number | undefined, tone: Number(counts.motion_keynote_visual_required_count ?? 0) > 0 ? "warn" : "good" },
          { label: "keynote perf", value: counts.motion_keynote_performance_required_count as number | undefined, tone: Number(counts.motion_keynote_performance_required_count ?? 0) > 0 ? "warn" : "good" },
          { label: "motion runbook", value: motionBrowserQaRunbook.status as string | undefined, tone: motionBrowserQaRunbook.local_runbook_ready === true ? "good" : "warn" },
          { label: "motion QA matrix", value: counts.motion_browser_qa_matrix_count as number | undefined },
          { label: "motion budgets", value: counts.motion_browser_qa_performance_budget_count as number | undefined },
          { label: "motion evidence", value: motionBrowserQaEvidence.status as string | undefined, tone: motionBrowserQaEvidence.visual_qa_complete === true ? "good" : "warn" },
          { label: "motion QA review", value: motionBrowserQaReview.status as string | undefined, tone: motionBrowserQaReview.local_browser_qa_review_ready === true ? "good" : "warn" },
          { label: "review blockers", value: counts.motion_browser_qa_review_blocking_count as number | undefined, tone: Number(counts.motion_browser_qa_review_blocking_count ?? 0) > 0 ? "warn" : "good" },
          { label: "browser reports", value: counts.motion_browser_qa_evidence_report_count as number | undefined },
          { label: "reduced pass", value: counts.motion_browser_qa_reduced_motion_passed === true ? "yes" : "pending", tone: counts.motion_browser_qa_reduced_motion_passed === true ? "good" : "warn" },
          { label: "audit envelope ledger", value: callLedger.length },
          { label: "audit warnings", value: cacheWarnings.length },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "外部调用", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" }
        ]}
      />

      <div className="grid">
        <PacketCard title="调用审计来源" subtitle="GET /api/audit/cache 聚合 cache API 与 task call_ledger" status={String(cache.status ?? "missing")}>
          <p>{String(cache.summary ?? "调用审计 cache 只读展示。")}</p>
          <p>审计范围包含 GET /health、GET cache API 与本地 task call_ledger。</p>
          <p>GET route coverage 会把参数化详情路由单列为 local detail，不会为了审计去构造 packet_key、dataset 或 task_id。</p>
          <p>GET /api/audit/cache 只读聚合本地 call_ledger，不调用 Tushare、DeepSeek、GitHub 或 Redis。</p>
          <p>审计页不刷新数据、不运行回测、不执行真实交易、不修改 strategy action。</p>
        </PacketCard>

        <PacketCard title="审计边界" subtitle="cache API 永不外联；POST task 才可能触发外部工作" status="policy">
          <p>audit_is_read_only: {String(policy.audit_is_read_only ?? true)}</p>
          <p>post_task_required_for_external_work: {String(policy.post_task_required_for_external_work ?? true)}</p>
          <p>contains_secret: {String(policy.contains_secret ?? false)}</p>
        </PacketCard>
      </div>

      <PacketCard title="Cache endpoint 审计" subtitle="每个 GET cache 的外部调用标志、call_ledger 数量和交易边界" status="endpoints">
        <DataLineageTable rows={rows(cache.endpoint_rows)} />
      </PacketCard>

      <PacketCard title="GET 路由覆盖" subtitle="可直接审计的 cache GET 与参数化 local detail GET 分开登记" status="get_route_coverage">
        <p>known_get_route_count: {String(getRouteCoverage.known_get_route_count ?? 0)}</p>
        <p>audited_cache_route_count: {String(getRouteCoverage.audited_cache_route_count ?? 0)}</p>
        <p>uncovered_get_routes: {String((getRouteCoverage.uncovered_get_routes as unknown[] | undefined)?.length ?? 0)}</p>
        <p>cache_routes_create_no_tasks: {String(getRouteCoverage.cache_routes_create_no_tasks ?? true)}</p>
        <DataLineageTable rows={parameterizedRoutes} />
      </PacketCard>

      <PacketCard title="任务审计" subtitle="GET /api/tasks 只读任务状态；不创建任务" status="tasks">
        <p>任务状态 index（command_center_3_task_status_index）会作为 cache endpoint 进入审计，同时任务明细会单独聚合 call_ledger。</p>
        <p>任务行会显示 storage_source，用来区分 memory、sqlite_meta 和 memory_and_sqlite。</p>
        <DataLineageTable rows={rows(cache.task_rows)} />
      </PacketCard>

      <PacketCard title="Task implementation audit" subtitle="只读展示 stub / local pipeline / guarded local，避免把任务系统误读成完整生产迁移" status={String(taskImplementation.status ?? "partial_migration")}>
        <p>implemented local task count: {String(taskImplementation.implemented_local_task_count ?? 0)}</p>
        <p>stub tasks must not be reported as complete: {String(policy.stub_tasks_must_not_be_reported_as_complete ?? true)}</p>
        <p>external capable tasks button gated: {String(taskImplementation.all_external_capable_tasks_are_button_gated ?? true)}</p>
        <p>external capable tasks require call ledger: {String(taskImplementation.all_external_capable_tasks_require_call_ledger ?? true)}</p>
        <DataLineageTable rows={implementationRows} />
      </PacketCard>

      <PacketCard title="Task 持久化审计" subtitle="memory + SQLite fallback 来源；审计页只读汇总" status="task_persistence">
        <p>storage_backend: {String(taskPersistence.storage_backend ?? "memory_plus_sqlite_fallback")}</p>
        <p>memory_task_count: {String(taskPersistence.memory_task_count ?? 0)}</p>
        <p>sqlite_task_count: {String(taskPersistence.sqlite_task_count ?? 0)}</p>
        <p>deduplicated_task_count: {String(taskPersistence.deduplicated_task_count ?? counts.task_count ?? 0)}</p>
        <p>task_rows_include_storage_source: {String(taskPersistence.task_rows_include_storage_source ?? true)}</p>
        <DataLineageTable rows={rows(cache.task_persistence_source_rows)} />
      </PacketCard>

      <PacketCard title="DeepSeek 模型策略审计" subtitle="从 local_deepseek_model_strategy_cache 提取；cache read 不外联、不含凭据" status="model_strategy">
        <p>model_strategy_purpose_count: {String(counts.model_strategy_purpose_count ?? 0)}</p>
        <p>model_strategy_cache_read_external_call_count: {String(counts.model_strategy_cache_read_external_call_count ?? 0)}</p>
        <DataLineageTable rows={modelStrategyRows} />
      </PacketCard>

      <PacketCard title="Release gate readiness" subtitle="release_gate_readiness_audit：本地静态 push gate 合同，不代表 CI 状态" status={String(releaseGateAudit.status ?? "missing")}>
        <p>scope: {String(releaseGateAudit.scope ?? "local_static_push_gate_contract_not_ci_status")}</p>
        <p>local_gate_ready: {String(releaseGateAudit.local_gate_ready ?? false)}</p>
        <p>release_gate_complete: {String(releaseGateAudit.release_gate_complete ?? false)}</p>
        <p>ci_mirror_ready: {String(releaseGateAudit.ci_mirror_ready ?? false)}</p>
        <p>secret_keyword_review_contract_ready: {String(releaseGateAudit.secret_keyword_review_contract_exists === true && releaseGateAudit.secret_keyword_review_contract_step === true)}</p>
        <p>keyword_review_raw_lines_suppressed: {String(releaseGateAudit.keyword_review_raw_lines_suppressed ?? false)}</p>
        <p>ci_mirror_not_proven: {String(Array.isArray(releaseGateAudit.blockers) && (releaseGateAudit.blockers as unknown[]).includes("ci_mirror_not_proven"))}</p>
        <p>false_positive_allowlist_review_pending: {String(Array.isArray(releaseGateAudit.soft_blockers) && (releaseGateAudit.soft_blockers as unknown[]).includes("false_positive_allowlist_review_pending"))}</p>
        <p>PUSH_GATE_REPORT_PATH local report is optional evidence, not production completion proof.</p>
      </PacketCard>

      <PacketCard title="Release gate checklist" subtitle="release_gate_readiness_rows：测试、build、smoke、安全扫描、artifact 扫描和 no-push 边界" status="release_gate_readiness_rows">
        <DataLineageTable rows={releaseGateRows} />
      </PacketCard>

      <PacketCard title="CI mirror static inventory" subtitle="只读列出 .github/workflows；不调用 GitHub API" status="ci_static_inventory">
        <DataLineageTable rows={releaseGateWorkflowRows} />
      </PacketCard>

      <PacketCard title="CI failure email triage" subtitle="ci_notification_triage_contract：本地分流失败邮件，不读取 GitHub run 日志" status={String(ciNotificationTriage.status ?? "missing")}>
        <p>scope: {String(ciNotificationTriage.scope ?? "local_ci_failure_email_triage_no_github_api")}</p>
        <p>local_gate_ready: {String(ciNotificationTriage.local_gate_ready ?? false)}；ci_mirror_ready: {String(ciNotificationTriage.ci_mirror_ready ?? false)}</p>
        <p>remote_actions_status_known: {String(ciNotificationTriage.remote_actions_status_known === true)}；remote_failure_logs_available: {String(ciNotificationTriage.remote_failure_logs_available === true)}</p>
        <p>remote_logs_required_for_root_cause: {String(ciNotificationTriage.remote_logs_required_for_root_cause === true)}</p>
        <p>can_dismiss_failure_email_without_matching_head_and_logs: {String(ciNotificationTriage.can_dismiss_failure_email_without_matching_head_and_logs === true)}</p>
        <p>requires_failed_step_name: {String(ciNotificationTriage.requires_failed_step_name === true)}；requires_failed_log_excerpt: {String(ciNotificationTriage.requires_failed_log_excerpt === true)}</p>
        <p>local_pass_is_not_ci_status: {String(ciNotificationTriage.local_pass_is_not_ci_status === true)}；old_email_may_be_stale: {String(ciNotificationTriage.old_email_may_be_stale === true)}</p>
        <p>该分流只读本地 workflow 和 push gate 合同；失败邮件的根因仍必须用 Actions 页面里的失败步骤名和日志片段确认。</p>
        <DataLineageTable rows={[ciNotificationTriage]} />
        <DataLineageTable rows={ciNotificationTriageRows} />
      </PacketCard>

      <PacketCard title="Motion clarity readiness" subtitle="LTG-14：只读静态审计 React/CSS 动效边界，不代表浏览器视觉验收完成" status={String(motionClarityAudit.status ?? "missing")}>
        <p>scope: {String(motionClarityAudit.scope ?? "local_static_source_audit_not_browser_visual_qa")}</p>
        <p>static_ready: {String(motionClarityAudit.static_ready ?? false)}</p>
        <p>production_motion_complete: {String(motionClarityAudit.production_motion_complete ?? false)}</p>
        <p>visual_qa_complete: {String(motionClarityAudit.visual_qa_complete ?? false)}</p>
        <p>browser_performance_verified: {String(motionClarityAudit.browser_performance_verified ?? false)}</p>
      </PacketCard>

      <PacketCard title="Motion clarity checklist" subtitle="motion_clarity_rows：tokens、reduced-motion、finite animation、no timer loop、chart/radar clarity" status="motion_clarity_rows">
        <DataLineageTable rows={motionClarityRows} />
      </PacketCard>

      <PacketCard title="Motion production QA" subtitle="motion_production_qa_contract：本地生产验收清单，不代表浏览器视觉或性能验收完成" status={String(motionProductionQa.status ?? "missing")}>
        <p>design_intent: {String(motionProductionQa.design_intent ?? "state_clarity_first_restrained_keynote_motion")}</p>
        <p>local_motion_qa_ready: {String(motionProductionQa.local_motion_qa_ready ?? false)}</p>
        <p>production_motion_complete: {String(motionProductionQa.production_motion_complete ?? false)}</p>
        <p>visual_qa_complete: {String(motionProductionQa.visual_qa_complete ?? false)}</p>
        <p>browser_performance_verified: {String(motionProductionQa.browser_performance_verified ?? false)}</p>
        <p>动效用于状态清晰度、图谱/雷达变化和任务反馈；视觉 QA 与性能 trace 未完成前不能标记为 production motion complete。</p>
        <DataLineageTable rows={[motionProductionQa]} />
        <DataLineageTable rows={motionProductionQaRows} />
      </PacketCard>

      <PacketCard title="Keynote motion roadmap" subtitle="motion_keynote_roadmap_audit：把发布会级动效目标拆成可验收路线，不运行浏览器、不推广本地 artifact" status={String(motionKeynoteRoadmap.status ?? "missing")}>
        <p>scope: {String(motionKeynoteRoadmap.scope ?? "local_keynote_motion_roadmap_not_browser_execution")}</p>
        <p>design_target: {String(motionKeynoteRoadmap.design_target ?? "apple_keynote_grade_clarity_restrained_motion")}</p>
        <p>roadmap_ready: {String(motionKeynoteRoadmap.roadmap_ready ?? false)}</p>
        <p>production_motion_complete: {String(motionKeynoteRoadmap.production_motion_complete ?? false)}</p>
        <p>promotion_blocker_count: {String(motionKeynoteRoadmap.promotion_blocker_count ?? 0)}</p>
        <p>visual_qa_required_count: {String(motionKeynoteRoadmap.visual_qa_required_count ?? 0)}；performance_trace_required_count: {String(motionKeynoteRoadmap.performance_trace_required_count ?? 0)}；browser_review_required_count: {String(motionKeynoteRoadmap.browser_review_required_count ?? 0)}</p>
        <p>路线图覆盖状态清晰基础、route staging、图表/雷达 delta choreography、任务反馈微交互、dense data readability、reduced-motion、performance trace、视觉证据推广和禁止交易紧迫感边界。</p>
        <DataLineageTable rows={[motionKeynoteRoadmap]} />
        <DataLineageTable rows={motionKeynoteRoadmapRows} />
      </PacketCard>

      <PacketCard title="Motion browser QA runbook" subtitle="motion_browser_qa_runbook_contract：本地浏览器 QA 执行手册，不打开浏览器、不写截图、不代表完成" status={String(motionBrowserQaRunbook.status ?? "missing")}>
        <p>scope: {String(motionBrowserQaRunbook.scope ?? "local_browser_qa_runbook_not_browser_execution")}</p>
        <p>local_runbook_ready: {String(motionBrowserQaRunbook.local_runbook_ready ?? false)}</p>
        <p>visual_qa_complete: {String(motionBrowserQaRunbook.visual_qa_complete ?? false)}</p>
        <p>browser_performance_verified: {String(motionBrowserQaRunbook.browser_performance_verified ?? false)}</p>
        <p>local_vite_base: {String(motionBrowserQaRunbook.local_vite_base ?? "http://127.0.0.1:5173")}</p>
        <p>artifact_root: {String(motionBrowserQaRunbook.artifact_root ?? ".stock_ming_3/motion_qa")}</p>
        <p>该 runbook 只固定本地启动顺序、route/viewport 矩阵、视觉验收标准和性能预算；真正浏览器截图/trace 仍需后续显式执行。</p>
        <DataLineageTable rows={[motionBrowserQaRunbook]} />
        <DataLineageTable rows={motionBrowserQaRunbookRows} />
        <DataLineageTable rows={motionBrowserQaMatrixRows} />
      </PacketCard>

      <PacketCard title="Motion browser QA evidence" subtitle="motion_browser_qa_evidence_contract：读取本地 ignored 报告摘要，不提交截图/报告" status={String(motionBrowserQaEvidence.status ?? "missing")}>
        <p>scope: {String(motionBrowserQaEvidence.scope ?? "local_ignored_browser_qa_reports_summary_not_tracked_artifact")}</p>
        <p>report_count: {String(motionBrowserQaEvidence.report_count ?? 0)}；passing_report_count: {String(motionBrowserQaEvidence.passing_report_count ?? 0)}</p>
        <p>default_motion_passed: {String(motionBrowserQaEvidence.default_motion_passed === true)}；reduced_motion_passed: {String(motionBrowserQaEvidence.reduced_motion_passed === true)}</p>
        <p>visual_qa_complete: {String(motionBrowserQaEvidence.visual_qa_complete === true)}；browser_performance_verified: {String(motionBrowserQaEvidence.browser_performance_verified === true)}</p>
        <p>production_motion_complete: {String(motionBrowserQaEvidence.production_motion_complete === true)}</p>
        <p>artifact_root: {String(motionBrowserQaEvidence.artifact_root ?? ".stock_ming_3/motion_qa")}</p>
        <p>该证据来自显式本地浏览器 QA；报告和截图必须保持 ignored，不等于 CI 状态或生产动效完成。</p>
        <button type="button" onClick={launchMotionBrowserQaReview}>审查 motion browser QA 本地证据</button>
        {reviewReceipt ? <TaskLaunchReceipt receipt={reviewReceipt} /> : null}
        <DataLineageTable rows={[motionBrowserQaEvidence]} />
        <DataLineageTable rows={motionBrowserQaEvidenceRows} />
      </PacketCard>

      <PacketCard title="Motion browser QA review" subtitle="motion_browser_qa_review_contract：POST 按钮门控，只审查本地 ignored artifact" status={String(motionBrowserQaReview.status ?? "missing")}>
        <p>scope: {String(motionBrowserQaReview.scope ?? "button_gated_local_motion_browser_qa_review_no_browser_execution")}</p>
        <p>explicit_review_task_done: {String(motionBrowserQaReview.explicit_review_task_done === true)}</p>
        <p>local_browser_qa_review_ready: {String(motionBrowserQaReview.local_browser_qa_review_ready === true)}</p>
        <p>blocking_review_count: {String(motionBrowserQaReview.blocking_review_count ?? 0)}</p>
        <p>default_motion_passed: {String(motionBrowserQaReview.default_motion_passed === true)}；reduced_motion_passed: {String(motionBrowserQaReview.reduced_motion_passed === true)}</p>
        <p>visual_qa_complete: {String(motionBrowserQaReview.visual_qa_complete === true)}；browser_performance_verified: {String(motionBrowserQaReview.browser_performance_verified === true)}</p>
        <p>production_motion_complete: {String(motionBrowserQaReview.production_motion_complete === true)}</p>
        <p>browser_visual_qa_promoted: {String(motionBrowserQaReview.browser_visual_qa_promoted === true)}；browser_performance_promoted: {String(motionBrowserQaReview.browser_performance_promoted === true)}</p>
        <p>ci_evidence_complete: {String(motionBrowserQaReview.ci_evidence_complete === true)}</p>
        <p>Motion browser QA review 不运行浏览器、不写 artifact、不提交截图；即使本地审查 ready，也不能解除 CI evidence、browser visual promotion、performance promotion 或 production motion completion 阻断项。</p>
        <DataLineageTable rows={[motionBrowserQaReview]} />
        <DataLineageTable rows={motionBrowserQaReviewRows} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="外部调用行" subtitle="external_calls_triggered 为 true 的本地记录；默认应为空" status="external">
          <DataLineageTable rows={rows(cache.external_call_rows)} />
        </PacketCard>
        <PacketCard title="Action 风险行" subtitle="does_not_execute_trades / does_not_modify_strategy_action 失败的记录；默认应为空" status="action_risk">
          <DataLineageTable rows={rows(cache.action_risk_rows)} />
        </PacketCard>
      </div>

      <PacketCard title="缺失 call_ledger 的本地项" subtitle="缺失血缘只代表本地返回包未附带 ledger，不代表自动外联" status="missing_ledger">
        <DataLineageTable rows={rows(cache.missing_call_ledger_rows)} />
      </PacketCard>

      <PacketCard title="调用血缘总表" subtitle="endpoint + task call_ledger 聚合；本页自身使用 local_call_ledger_audit_cache" status="lineage">
        <DataLineageTable rows={rows(cache.call_ledger_rows)} />
      </PacketCard>

      <PacketCard title="审计页自身调用血缘" subtitle="local_call_ledger_audit_cache；不外联、不写回业务 packet" status="self_lineage">
        <DataLineageTable rows={callLedger} />
      </PacketCard>

      <PacketCard title="审计页 envelope warnings" subtitle="GET /api/audit/cache 顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={cacheWarnings.map((warning, index) => ({ index: index + 1, warning: String(warning ?? "") }))} />
      </PacketCard>

      <PacketCard title="原始 call ledger audit cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="call ledger audit raw" data={cache} />
      </PacketCard>
    </>
  );
}
