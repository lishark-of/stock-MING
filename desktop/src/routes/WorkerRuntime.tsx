import { useEffect, useState } from "react";
import { getWorkerRuntimeCache, runWorkerSyntheticHealthcheck } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

export default function WorkerRuntime() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);
  const [healthcheckResult, setHealthcheckResult] = useState<Record<string, unknown>>({});
  const [healthcheckRunning, setHealthcheckRunning] = useState(false);
  const [healthcheckError, setHealthcheckError] = useState("");

  const refreshCache = () => {
    return getWorkerRuntimeCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  };

  useEffect(() => {
    void refreshCache();
  }, []);

  const launchSyntheticHealthcheck = () => {
    setHealthcheckRunning(true);
    setHealthcheckError("");
    void runWorkerSyntheticHealthcheck({ requested_from: "worker_runtime_page" })
      .then((res) => {
        setHealthcheckResult(res.data);
        return refreshCache();
      })
      .catch((err: unknown) => setHealthcheckError(err instanceof Error ? err.message : String(err)))
      .finally(() => setHealthcheckRunning(false));
  };

  const runtime = (cache.runtime as Record<string, unknown> | undefined) ?? {};
  const summary = (cache.task_catalog_summary as Record<string, unknown> | undefined) ?? {};
  const taskImplementation = (cache.task_implementation_status as Record<string, unknown> | undefined) ?? {};
  const taskStatus = (cache.task_status_summary as Record<string, unknown> | undefined) ?? {};
  const taskPersistence = (cache.task_persistence as Record<string, unknown> | undefined) ?? ((taskStatus.persistence as Record<string, unknown> | undefined) ?? {});
  const productionReadiness = (cache.production_readiness as Record<string, unknown> | undefined) ?? {};
  const productionBlockerAudit = (productionReadiness.production_blocker_audit as Record<string, unknown> | undefined) ?? ((cache.worker_production_blocker_audit as Record<string, unknown> | undefined) ?? {});
  const workerHealthcheckQa = (productionReadiness.worker_healthcheck_qa_contract as Record<string, unknown> | undefined) ?? ((cache.worker_healthcheck_qa_contract as Record<string, unknown> | undefined) ?? {});
  const workerTaskLogPersistence =
    (productionReadiness.worker_task_log_persistence_audit as Record<string, unknown> | undefined) ??
    ((cache.worker_task_log_persistence_audit as Record<string, unknown> | undefined) ?? {});
  const workerQueueRouting =
    (productionReadiness.worker_queue_routing_contract as Record<string, unknown> | undefined) ??
    ((cache.worker_queue_routing_contract as Record<string, unknown> | undefined) ?? {});
  const workerActivationReview =
    (productionReadiness.worker_activation_review_contract as Record<string, unknown> | undefined) ??
    ((cache.worker_activation_review_contract as Record<string, unknown> | undefined) ?? {});
  const workerSyntheticHealthcheck =
    (productionReadiness.worker_synthetic_healthcheck as Record<string, unknown> | undefined) ??
    ((cache.worker_synthetic_healthcheck as Record<string, unknown> | undefined) ?? {});
  const workerProductionReadinessReceipt =
    (productionReadiness.worker_production_readiness_receipt as Record<string, unknown> | undefined) ??
    ((cache.worker_production_readiness_receipt as Record<string, unknown> | undefined) ?? {});
  const workerProductionActivationReceipt =
    (productionReadiness.worker_production_activation_receipt as Record<string, unknown> | undefined) ??
    ((cache.worker_production_activation_receipt as Record<string, unknown> | undefined) ?? {});
  const visibleHealthcheck = Object.keys(healthcheckResult).length ? healthcheckResult : workerSyntheticHealthcheck;
  const dispatchPlanSummary = (cache.dispatch_plan_summary as Record<string, unknown> | undefined) ?? {};
  const dispatchPlanStatusCounts = dispatchPlanSummary.status_counts as Record<string, unknown> | undefined;
  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);
  const implementationRows = [
    { kind: "stub", count: taskImplementation.stub_task_count, task_types: Array.isArray(taskImplementation.stub_task_types) ? (taskImplementation.stub_task_types as unknown[]).join(" / ") : "" },
    { kind: "local_pipeline", count: taskImplementation.local_pipeline_task_count, task_types: Array.isArray(taskImplementation.local_pipeline_task_types) ? (taskImplementation.local_pipeline_task_types as unknown[]).join(" / ") : "" },
    { kind: "guarded_local", count: taskImplementation.guarded_local_task_count, task_types: Array.isArray(taskImplementation.guarded_local_task_types) ? (taskImplementation.guarded_local_task_types as unknown[]).join(" / ") : "" },
    { kind: "external_capable", count: taskImplementation.external_capable_task_count, task_types: Array.isArray(taskImplementation.external_capable_task_types) ? (taskImplementation.external_capable_task_types as unknown[]).join(" / ") : "" }
  ];

  return (
    <>
      <div className="page-head">
        <h1>Worker 运行时</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "backends", value: counts.backend_count as number | undefined },
          { label: "worker modules", value: counts.worker_module_count as number | undefined },
          { label: "ready modules", value: counts.worker_module_ready_count as number | undefined },
          { label: "task catalog", value: counts.task_count as number | undefined },
          { label: "task status", value: counts.task_status_count as number | undefined },
          { label: "stub tasks", value: counts.stub_task_count as number | undefined },
          { label: "local pipelines", value: counts.local_pipeline_task_count as number | undefined },
          { label: "guarded local", value: counts.guarded_local_task_count as number | undefined },
          { label: "implemented local", value: counts.implemented_local_task_count as number | undefined },
          { label: "memory tasks", value: counts.memory_task_count as number | undefined },
          { label: "sqlite tasks", value: counts.sqlite_task_count as number | undefined },
          { label: "dedup tasks", value: counts.deduplicated_task_count as number | undefined },
          { label: "task call ledger", value: counts.task_status_call_ledger_count as number | undefined },
          { label: "task logs", value: counts.worker_task_log_count ?? taskStatus.task_log_count ?? 0 },
          { label: "manual preflight", value: counts.manual_preflight_step_count as number | undefined },
          { label: "operator actions", value: counts.manual_preflight_operator_action_count as number | undefined, tone: Number(counts.manual_preflight_operator_action_count ?? 0) > 0 ? "warn" : "good" },
          { label: "dispatch tasks", value: counts.dispatch_plan_task_count as number | undefined },
          { label: "dispatch queues", value: counts.dispatch_plan_queue_count as number | undefined },
          { label: "worker blockers", value: productionBlockerAudit.blocking_criterion_count ?? counts.production_blocker_audit_count, tone: Number(productionBlockerAudit.blocking_criterion_count ?? counts.production_blocker_audit_count ?? 0) > 0 ? "warn" : "good" },
          { label: "healthcheck pending", value: workerHealthcheckQa.pending_criterion_count ?? counts.worker_healthcheck_qa_pending_count, tone: Number(workerHealthcheckQa.pending_criterion_count ?? counts.worker_healthcheck_qa_pending_count ?? 0) > 0 ? "warn" : "good" },
          { label: "synthetic check", value: visibleHealthcheck.synthetic_healthcheck_executed === true ? "已显式运行" : "未运行", tone: visibleHealthcheck.synthetic_healthcheck_executed === true ? "good" : "warn" },
          { label: "log blockers", value: workerTaskLogPersistence.production_blocker_count ?? counts.worker_task_log_persistence_blocker_count, tone: Number(workerTaskLogPersistence.production_blocker_count ?? counts.worker_task_log_persistence_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "queue routing", value: workerQueueRouting.queue_routing_contract_ready === true ? "ready" : "blocked", tone: workerQueueRouting.queue_routing_contract_ready === true ? "good" : "warn" },
          { label: "queue blockers", value: workerQueueRouting.blocking_criterion_count ?? counts.worker_queue_routing_blocker_count, tone: Number(workerQueueRouting.blocking_criterion_count ?? counts.worker_queue_routing_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "activation blockers", value: workerActivationReview.activation_blocker_count ?? counts.worker_activation_blocker_count, tone: Number(workerActivationReview.activation_blocker_count ?? counts.worker_activation_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "receipt ready", value: workerProductionReadinessReceipt.local_receipt_ready === true ? "是" : "否", tone: workerProductionReadinessReceipt.local_receipt_ready === true ? "good" : "warn" },
          { label: "receipt blockers", value: workerProductionReadinessReceipt.blocking_criterion_count ?? counts.worker_production_readiness_receipt_blocker_count, tone: Number(workerProductionReadinessReceipt.blocking_criterion_count ?? counts.worker_production_readiness_receipt_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "prod activation", value: workerProductionActivationReceipt.local_activation_receipt_ready === true ? "是" : "否", tone: workerProductionActivationReceipt.local_activation_receipt_ready === true ? "good" : "warn" },
          { label: "activation evidence", value: workerProductionActivationReceipt.blocking_criterion_count ?? counts.worker_production_activation_blocker_count, tone: Number(workerProductionActivationReceipt.blocking_criterion_count ?? counts.worker_production_activation_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "activation ready", value: workerActivationReview.activation_ready === true ? "是" : "否", tone: workerActivationReview.activation_ready === true ? "bad" : "good" },
          { label: "worker complete", value: productionBlockerAudit.production_worker_complete === true ? "是" : "否", tone: productionBlockerAudit.production_worker_complete === true ? "bad" : "good" },
          { label: "local fallback", value: runtime.local_fallback_enabled, tone: runtime.local_fallback_enabled === false ? "bad" : "good" },
          { label: "Celery", value: runtime.celery_available, tone: runtime.celery_available === true ? "good" : "warn" },
          { label: "Redis package", value: runtime.redis_package_available, tone: runtime.redis_package_available === true ? "good" : "warn" },
          { label: "APScheduler", value: runtime.apscheduler_available, tone: runtime.apscheduler_available === true ? "good" : "warn" },
          { label: "Redis ping", value: cache.redis_pinged === true ? "已 ping" : "未 ping", tone: cache.redis_pinged === true ? "bad" : "good" },
          { label: "scheduler started", value: runtime.scheduler_started === true ? "是" : "否", tone: runtime.scheduler_started === true ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheEnvelopeLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="Worker runtime 来源" subtitle="GET /api/worker/cache 只读检查 worker scaffold 和任务目录" status={String(cache.status ?? "missing")}>
          <p>GET /api/worker/cache 只读检查本地 worker scaffold、Celery/Redis/APScheduler 依赖可见性和 task catalog。</p>
          <p>不会连接 Redis，不会启动 Celery worker，不会启动 APScheduler，不会调度真实任务。</p>
          <p>不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。</p>
        </PacketCard>

        <PacketCard title="Task catalog 摘要" subtitle="全部重任务仍必须由 POST task 按钮触发" status="catalog">
          <p>task count: {String(summary.task_count ?? 0)}</p>
          <p>implementation status: {String(summary.implementation_status ?? taskImplementation.status ?? "partial_migration")}</p>
          <p>stub / local pipeline / guarded: {String(summary.stub_task_count ?? 0)} / {String(summary.local_pipeline_task_count ?? 0)} / {String(summary.guarded_local_task_count ?? 0)}</p>
          <p>all button gated: {String(summary.all_tasks_button_gated ?? true)}</p>
          <p>call ledger required: {String(summary.call_ledger_required_for_all ?? true)}</p>
          <p>supports local cancel: {String(summary.supports_local_task_cancel ?? true)}</p>
        </PacketCard>

        <PacketCard title="Task implementation status" subtitle="只读展示 stub / local pipeline / guarded local，避免把 worker scaffold 误读成完整迁移" status={String(taskImplementation.status ?? "partial_migration")}>
          <p>implemented local task count: {String(taskImplementation.implemented_local_task_count ?? 0)}</p>
          <p>stub tasks must not be reported as complete: {String(policy.stub_tasks_must_not_be_reported_as_complete ?? true)}</p>
          <p>external capable tasks button gated: {String(taskImplementation.all_external_capable_tasks_are_button_gated ?? true)}</p>
          <p>external capable tasks require call ledger: {String(taskImplementation.all_external_capable_tasks_require_call_ledger ?? true)}</p>
          <DataLineageTable rows={implementationRows} />
        </PacketCard>

        <PacketCard title="Task status index 摘要" subtitle="GET /api/tasks 的本地状态汇总；不创建任务、不外联" status="task_status_index">
          <p>packet: {String(taskStatus.packet_key ?? "--")}</p>
          <p>task count: {String(taskStatus.task_count ?? 0)}</p>
          <p>status counts: {JSON.stringify(taskStatus.status_counts ?? {})}</p>
          <p>latest task: {String(taskStatus.latest_task_type ?? "--")} / {String(taskStatus.latest_task_status ?? "--")}</p>
          <p>call ledger: {String(taskStatus.call_ledger_count ?? 0)}</p>
          <p>memory tasks: {String(taskStatus.memory_task_count ?? 0)}</p>
          <p>sqlite tasks: {String(taskStatus.sqlite_task_count ?? 0)}</p>
          <p>deduplicated tasks: {String(taskStatus.deduplicated_task_count ?? 0)}</p>
          <p>sqlite fallback enabled: {String(taskStatus.sqlite_fallback_enabled ?? true)}</p>
          <p>external calls: {String(taskStatus.external_calls_triggered ?? false)}</p>
          <p>does_not_execute_trades: {String(taskStatus.does_not_execute_trades ?? true)}</p>
          <p>does_not_modify_strategy_action: {String(taskStatus.does_not_modify_strategy_action ?? true)}</p>
        </PacketCard>
      </div>

      <PacketCard title="Task 持久化来源" subtitle="GET /api/tasks 的 memory + SQLite fallback 来源；只读展示" status="task_persistence">
        <p>storage backend: {String(taskPersistence.storage_backend ?? "memory_plus_sqlite_fallback")}</p>
        <p>memory_task_count: {String(taskPersistence.memory_task_count ?? 0)}</p>
        <p>sqlite_task_count: {String(taskPersistence.sqlite_task_count ?? 0)}</p>
        <p>deduplicated_task_count: {String(taskPersistence.deduplicated_task_count ?? taskStatus.task_count ?? 0)}</p>
        <p>task_rows_include_storage_source: {String(taskPersistence.task_rows_include_storage_source ?? true)}</p>
        <DataLineageTable rows={rows(cache.task_persistence_source_rows ?? taskStatus.persistence_source_rows)} />
      </PacketCard>

      <PacketCard title="Task log persistence audit" subtitle="本地 safe task_log 可见性；不是 Celery/Redis append-only worker log 证明" status={String(workerTaskLogPersistence.status ?? "local_task_log_persistence_ready_worker_append_only_pending")}>
        <p>schema_version: {String(workerTaskLogPersistence.schema_version ?? "worker_task_log_persistence_audit.v1")}</p>
        <p>task_log_count / call_ledger_count: {String(workerTaskLogPersistence.task_log_count ?? taskStatus.task_log_count ?? 0)} / {String(workerTaskLogPersistence.call_ledger_count ?? taskStatus.call_ledger_count ?? 0)}</p>
        <p>local_task_log_persistence_ready: {String(workerTaskLogPersistence.local_task_log_persistence_ready ?? true)}</p>
        <p>task_log_persistence_verified / append_only_worker_log_verified: {String(workerTaskLogPersistence.task_log_persistence_verified ?? false)} / {String(workerTaskLogPersistence.append_only_worker_log_verified ?? false)}</p>
        <p>cross_process_log_round_trip_verified / production_worker_complete: {String(workerTaskLogPersistence.cross_process_log_round_trip_verified ?? false)} / {String(workerTaskLogPersistence.production_worker_complete ?? false)}</p>
        <p>cache_get_reads_raw_payload / cache_get_writes_logs: {String(workerTaskLogPersistence.cache_get_reads_raw_payload ?? false)} / {String(workerTaskLogPersistence.cache_get_writes_logs ?? false)}</p>
        <DataLineageTable rows={rows(productionReadiness.worker_task_log_persistence_rows ?? cache.worker_task_log_persistence_rows)} />
      </PacketCard>

      <PacketCard title="Backend 状态" subtitle="local fallback / Celery / Redis / APScheduler；cache API 不连接外部服务" status="backends">
        <DataLineageTable rows={rows(cache.backend_rows)} />
      </PacketCard>

      <PacketCard title="Worker dispatch plan" subtitle="每类任务的未来队列、local fallback、Redis/Celery 前置条件和调度边界；只读、不派发" status={String(cache.dispatch_plan_status ?? "contract_ready_local_fallback")}>
        <p>queue names: {Array.isArray(dispatchPlanSummary.queue_names) ? dispatchPlanSummary.queue_names.join(" / ") : "--"}</p>
        <p>local fallback supported: {String(dispatchPlanSummary.local_fallback_supported_count ?? 0)}</p>
        <p>celery ready / stub pending: {String(dispatchPlanSummary.celery_ready_count ?? 0)} / {String(dispatchPlanSummary.stub_worker_pending_count ?? 0)}</p>
        <p>cache GET external calls / scheduler auto tasks: {String(dispatchPlanSummary.cache_get_external_call_count ?? 0)} / {String(dispatchPlanSummary.scheduler_auto_task_count ?? 0)}</p>
        <p>status_counts: {JSON.stringify(dispatchPlanStatusCounts ?? {})}</p>
        <DataLineageTable rows={rows(cache.dispatch_plan_rows)} />
      </PacketCard>

      <PacketCard title="Worker queue routing contract" subtitle="未来 Celery 队列路由合同；只读、不启动 Celery、不 ping Redis、不派发任务" status={String(workerQueueRouting.status ?? "worker_queue_routing_contract_ready_activation_pending")}>
        <p>schema_version: {String(workerQueueRouting.schema_version ?? "worker_queue_routing_contract.v1")}</p>
        <p>queue_routing_contract_ready: {String(workerQueueRouting.queue_routing_contract_ready ?? true)}</p>
        <p>task_count / queue_count: {String(workerQueueRouting.task_count ?? counts.worker_queue_routing_task_count ?? 0)} / {String(workerQueueRouting.queue_count ?? counts.worker_queue_routing_queue_count ?? 0)}</p>
        <p>external_capable_task_count: {String(workerQueueRouting.external_capable_task_count ?? counts.worker_queue_routing_external_capable_task_count ?? 0)}</p>
        <p>worker_started_by_contract / redis_pinged_by_contract / scheduler_started_by_contract: {String(workerQueueRouting.worker_started_by_contract ?? false)} / {String(workerQueueRouting.redis_pinged_by_contract ?? false)} / {String(workerQueueRouting.scheduler_started_by_contract ?? false)}</p>
        <p>task_dispatched_by_contract / provider_model_task_dispatched_by_contract: {String(workerQueueRouting.task_dispatched_by_contract ?? false)} / {String(workerQueueRouting.provider_model_task_dispatched_by_contract ?? false)}</p>
        <p>contract_external_calls_triggered / tushare_called / deepseek_called / github_called: {String(workerQueueRouting.contract_external_calls_triggered ?? false)} / {String(workerQueueRouting.tushare_called ?? false)} / {String(workerQueueRouting.deepseek_called ?? false)} / {String(workerQueueRouting.github_called ?? false)}</p>
        <p>production_worker_complete / activation_ready: {String(workerQueueRouting.production_worker_complete ?? false)} / {String(workerQueueRouting.activation_ready ?? false)}</p>
        <p>queue_names: {Array.isArray(workerQueueRouting.queue_names) ? workerQueueRouting.queue_names.join(" / ") : "provider_refresh / model_explain / external_probe / local_maintenance / local_compute"}</p>
        <DataLineageTable rows={rows(productionReadiness.worker_queue_routing_rows ?? cache.worker_queue_routing_rows)} />
        <DataLineageTable rows={rows(productionReadiness.worker_queue_routing_queue_rows ?? cache.worker_queue_routing_queue_rows)} />
        <DataLineageTable rows={rows(workerQueueRouting.call_ledger)} />
      </PacketCard>

      <PacketCard title="生产 worker 人工预检" subtitle="只读 checklist；不启动 Celery、不 ping Redis、不调度任务" status={String(productionReadiness.status ?? "preflight")}>
        <p>这些步骤用于后续生产化验收；GET /api/worker/cache 只展示状态，不执行任何一步。</p>
        <p>cache_api_can_execute 必须保持 false；operator_action_required 表示需要人工显式操作。</p>
        <DataLineageTable rows={rows(productionReadiness.manual_preflight_steps)} />
      </PacketCard>

      <PacketCard title="生产 worker 阻断审计" subtitle="只读 blocker audit；本地 fallback 可用不等于 Celery/Redis 生产完成" status={String(productionBlockerAudit.status ?? "production_worker_blocked")}>
        <p>production_worker_complete 必须保持 false，直到未来显式 worker health check 证明 Celery/Redis 已人工启动并可安全调度。</p>
        <p>这张表不启动 worker、不 ping Redis、不调度 Tushare/DeepSeek/GitHub，也不执行真实交易。</p>
        <DataLineageTable rows={rows(productionReadiness.production_blocker_rows ?? cache.worker_production_blocker_rows)} />
      </PacketCard>

      <PacketCard title="Worker healthcheck QA 契约" subtitle="未来生产 worker healthcheck 的验收清单；当前只读、不执行" status={String(workerHealthcheckQa.status ?? "worker_healthcheck_qa_contract_ready_execution_pending")}>
        <p>healthcheck_executed: {String(workerHealthcheckQa.healthcheck_executed ?? false)}</p>
        <p>production_worker_complete: {String(workerHealthcheckQa.production_worker_complete ?? false)}</p>
        <p>synthetic_task_only: {String(workerHealthcheckQa.synthetic_task_only ?? true)}</p>
        <p>provider_model_task_validation_in_scope: {String(workerHealthcheckQa.provider_model_task_validation_in_scope ?? false)}</p>
        <p>这张表只定义后续人工 healthcheck 要验什么；不会启动 Celery、不会 ping Redis、不会启动 scheduler、不会派发任务。</p>
        <DataLineageTable rows={rows(productionReadiness.worker_healthcheck_qa_rows ?? cache.worker_healthcheck_qa_rows)} />
      </PacketCard>

      <PacketCard title="Worker synthetic healthcheck" subtitle="显式按钮触发本地 task/status/log 往返；不是 Celery/Redis 生产证明" status={String(visibleHealthcheck.status ?? "synthetic_healthcheck_missing")}>
        <div className="actions">
          <button onClick={launchSyntheticHealthcheck} disabled={healthcheckRunning}>
            {healthcheckRunning ? "运行中" : "运行本地 healthcheck"}
          </button>
          <button onClick={() => void refreshCache()} disabled={healthcheckRunning}>刷新缓存</button>
        </div>
        {healthcheckError ? <p className="risk-note">healthcheck_error: {healthcheckError}</p> : null}
        <p>route: POST /api/worker/synthetic-healthcheck</p>
        <p>synthetic_healthcheck_executed / healthcheck_task_dispatched: {String(visibleHealthcheck.synthetic_healthcheck_executed ?? false)} / {String(visibleHealthcheck.healthcheck_task_dispatched ?? false)}</p>
        <p>local_task_round_trip_verified / task_log_round_trip_verified: {String(visibleHealthcheck.local_task_round_trip_verified ?? false)} / {String(visibleHealthcheck.task_log_round_trip_verified ?? false)}</p>
        <p>healthcheck_hash_algorithm: {String(visibleHealthcheck.healthcheck_hash_algorithm ?? "")}</p>
        <p>task_identity_sha256: {String(visibleHealthcheck.task_identity_sha256 ?? "")}</p>
        <p>readback_task_identity_sha256: {String(visibleHealthcheck.readback_task_identity_sha256 ?? "")}</p>
        <p>task_readback_hash_matches: {String(visibleHealthcheck.task_readback_hash_matches ?? false)}</p>
        <p>celery_worker_started / redis_pinged / scheduler_started: {String(visibleHealthcheck.celery_worker_started ?? false)} / {String(visibleHealthcheck.redis_pinged ?? false)} / {String(visibleHealthcheck.scheduler_started ?? false)}</p>
        <p>production_worker_complete / activation_ready: {String(visibleHealthcheck.production_worker_complete ?? false)} / {String(visibleHealthcheck.activation_ready ?? false)}</p>
        <p>不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action；GET cache 不会自动执行 healthcheck。</p>
        <DataLineageTable rows={rows(productionReadiness.worker_synthetic_healthcheck_rows ?? cache.worker_synthetic_healthcheck_rows ?? visibleHealthcheck.rows)} />
      </PacketCard>

      <PacketCard title="Worker activation review" subtitle="生产 worker 启用前的人工作业合同；不启动 Celery、不 ping Redis、不派发任务" status={String(workerActivationReview.status ?? "worker_activation_review_ready_activation_pending")}>
        <p>schema_version: {String(workerActivationReview.schema_version ?? "worker_activation_review_contract.v1")}</p>
        <p>review_policy: {String(workerActivationReview.review_policy ?? "manual_activation_required_after_blocker_and_healthcheck_review")}</p>
        <p>activation_ready / production_worker_complete: {String(workerActivationReview.activation_ready ?? false)} / {String(workerActivationReview.production_worker_complete ?? false)}</p>
        <p>manual_activation_required / healthcheck_required_before_activation: {String(workerActivationReview.manual_activation_required ?? true)} / {String(workerActivationReview.healthcheck_required_before_activation ?? true)}</p>
        <p>activation_blocker_count / operator_action_required_count: {String(workerActivationReview.activation_blocker_count ?? 0)} / {String(workerActivationReview.operator_action_required_count ?? 0)}</p>
        <p>worker_started_by_cache_api / redis_pinged_by_cache_api / scheduler_started_by_cache_api: {String(workerActivationReview.worker_started_by_cache_api ?? false)} / {String(workerActivationReview.redis_pinged_by_cache_api ?? false)} / {String(workerActivationReview.scheduler_started_by_cache_api ?? false)}</p>
        <p>task_dispatched_by_cache_api / cache_get_external_calls: {String(workerActivationReview.task_dispatched_by_cache_api ?? false)} / {String(workerActivationReview.cache_get_external_calls ?? false)}</p>
        <DataLineageTable rows={rows(productionReadiness.worker_activation_review_rows ?? cache.worker_activation_review_rows)} />
      </PacketCard>

      <PacketCard title="Worker production readiness receipt" subtitle="LTG-06 下一步收据；只允许显式 POST healthcheck 和人工 activation review" status={String(workerProductionReadinessReceipt.status ?? "worker_readiness_receipt_ready_synthetic_healthcheck_pending")}>
        <p>schema_version: {String(workerProductionReadinessReceipt.schema_version ?? "worker_production_readiness_receipt.v1")}</p>
        <p>scope: {String(workerProductionReadinessReceipt.scope ?? "local_worker_production_readiness_receipt_no_process_start")}</p>
        <p>local_receipt_ready / ready_for_explicit_synthetic_healthcheck: {String(workerProductionReadinessReceipt.local_receipt_ready ?? true)} / {String(workerProductionReadinessReceipt.ready_for_explicit_synthetic_healthcheck ?? true)}</p>
        <p>ready_for_manual_activation_review: {String(workerProductionReadinessReceipt.ready_for_manual_activation_review ?? false)}</p>
        <p>allowed_next_step: {String(workerProductionReadinessReceipt.allowed_next_step ?? "explicit_post_worker_synthetic_healthcheck_then_manual_activation_review")}</p>
        <p>production_worker_complete: {String(workerProductionReadinessReceipt.production_worker_complete ?? false)}</p>
        <p>worker_started_by_receipt / redis_pinged_by_receipt / scheduler_started_by_receipt: {String(workerProductionReadinessReceipt.worker_started_by_receipt ?? false)} / {String(workerProductionReadinessReceipt.redis_pinged_by_receipt ?? false)} / {String(workerProductionReadinessReceipt.scheduler_started_by_receipt ?? false)}</p>
        <p>task_dispatched_by_receipt / provider_model_task_dispatched_by_receipt: {String(workerProductionReadinessReceipt.task_dispatched_by_receipt ?? false)} / {String(workerProductionReadinessReceipt.provider_model_task_dispatched_by_receipt ?? false)}</p>
        <p>receipt_external_calls_triggered / tushare_called_by_receipt / deepseek_called / github_called: {String(workerProductionReadinessReceipt.receipt_external_calls_triggered ?? false)} / {String(workerProductionReadinessReceipt.tushare_called_by_receipt ?? false)} / {String(workerProductionReadinessReceipt.deepseek_called ?? false)} / {String(workerProductionReadinessReceipt.github_called ?? false)}</p>
        <p>not_allowed_next_steps: {Array.isArray(workerProductionReadinessReceipt.not_allowed_next_steps) ? workerProductionReadinessReceipt.not_allowed_next_steps.join(" / ") : "GET /api/worker/cache worker process start / GET /api/worker/cache Redis ping / automatic Tushare/DeepSeek/GitHub task scheduling / readiness receipt as production worker completion"}</p>
        <DataLineageTable rows={rows(productionReadiness.worker_production_readiness_receipt_rows ?? cache.worker_production_readiness_receipt_rows)} />
        <DataLineageTable rows={rows(workerProductionReadinessReceipt.call_ledger)} />
      </PacketCard>

      <PacketCard title="Worker production activation receipt" subtitle="LTG-06 生产启用收据；只列出人工启用前置证据，不启动 Celery、不 ping Redis、不调度任务" status={String(workerProductionActivationReceipt.status ?? "worker_activation_receipt_ready_production_blocked")}>
        <p>schema_version: {String(workerProductionActivationReceipt.schema_version ?? "worker_production_activation_receipt.v1")}</p>
        <p>scope: {String(workerProductionActivationReceipt.scope ?? "local_worker_production_activation_receipt_no_process_start")}</p>
        <p>local_activation_receipt_ready: {String(workerProductionActivationReceipt.local_activation_receipt_ready ?? false)}</p>
        <p>allowed_next_step: {String(workerProductionActivationReceipt.allowed_next_step ?? "explicit_synthetic_healthcheck_then_manual_celery_redis_activation_review")}</p>
        <p>production_worker_complete / activation_ready: {String(workerProductionActivationReceipt.production_worker_complete ?? false)} / {String(workerProductionActivationReceipt.activation_ready ?? false)}</p>
        <p>synthetic_healthcheck_executed / healthcheck_executed_by_receipt: {String(workerProductionActivationReceipt.synthetic_healthcheck_executed ?? false)} / {String(workerProductionActivationReceipt.healthcheck_executed_by_receipt ?? false)}</p>
        <p>worker_started_by_receipt / redis_pinged_by_receipt / scheduler_started_by_receipt: {String(workerProductionActivationReceipt.worker_started_by_receipt ?? false)} / {String(workerProductionActivationReceipt.redis_pinged_by_receipt ?? false)} / {String(workerProductionActivationReceipt.scheduler_started_by_receipt ?? false)}</p>
        <p>task_dispatched_by_receipt / provider_model_task_dispatched_by_receipt: {String(workerProductionActivationReceipt.task_dispatched_by_receipt ?? false)} / {String(workerProductionActivationReceipt.provider_model_task_dispatched_by_receipt ?? false)}</p>
        <p>receipt_external_calls_triggered / tushare_called_by_receipt / deepseek_called / github_called: {String(workerProductionActivationReceipt.receipt_external_calls_triggered ?? false)} / {String(workerProductionActivationReceipt.tushare_called_by_receipt ?? false)} / {String(workerProductionActivationReceipt.deepseek_called ?? false)} / {String(workerProductionActivationReceipt.github_called ?? false)}</p>
        <p>missing_evidence_items: {Array.isArray(workerProductionActivationReceipt.missing_evidence_items) ? workerProductionActivationReceipt.missing_evidence_items.join(" / ") : "explicit synthetic healthcheck execution / celery worker process evidence / redis broker reachability evidence / production worker promotion evidence"}</p>
        <p>not_allowed_next_steps: {Array.isArray(workerProductionActivationReceipt.not_allowed_next_steps) ? workerProductionActivationReceipt.not_allowed_next_steps.join(" / ") : "GET /api/worker/cache worker process start / GET /api/worker/cache Redis ping / activation receipt as production worker completion"}</p>
        <DataLineageTable rows={rows(productionReadiness.worker_production_activation_rows ?? cache.worker_production_activation_rows)} />
        <DataLineageTable rows={rows(workerProductionActivationReceipt.call_ledger)} />
      </PacketCard>

      <PacketCard title="Worker 模块" subtitle="worker.tasks_* 和 scheduler scaffold；只读文件/模块可见性" status="modules">
        <DataLineageTable rows={rows(cache.worker_module_rows)} />
      </PacketCard>

      <PacketCard title="API / 调度边界" subtitle="cache API 永不外联；POST task 才可能触发外部请求" status="policy">
        <p>does_not_ping_redis / does_not_start_celery_worker / does_not_start_scheduler 必须保持为 true。</p>
        <p>不会调度真实 Tushare、DeepSeek 或 GitHub 任务；不会执行真实交易；不修改 strategy action。</p>
        <p>local_worker_runtime_cache 只读本地 scaffold，不暴露 Redis 连接串。</p>
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="payload 内部 local_worker_runtime_cache；不外联、不启动 worker" status="lineage">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET worker envelope call_ledger" subtitle="GET /api/worker/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheEnvelopeLedger} />
      </PacketCard>

      <PacketCard title="GET worker envelope warnings" subtitle="顶层响应提示；不包含 token/key/Redis URL" status="warnings">
        <DataLineageTable rows={cacheWarnings.map((warning, index) => ({ index: index + 1, warning }))} />
      </PacketCard>

      <PacketCard title="原始 worker runtime cache payload" subtitle="调试用 JSON；不含 token/key/Redis URL" status="safe">
        <JsonDetails title="worker runtime cache raw" data={cache} />
        <JsonDetails title="worker task log persistence raw" data={workerTaskLogPersistence} />
        <JsonDetails title="worker queue routing raw" data={workerQueueRouting} />
        <JsonDetails title="worker synthetic healthcheck raw" data={visibleHealthcheck} />
        <JsonDetails title="worker activation review raw" data={workerActivationReview} />
        <JsonDetails title="worker production readiness receipt raw" data={workerProductionReadinessReceipt} />
        <JsonDetails title="worker production activation receipt raw" data={workerProductionActivationReceipt} />
      </PacketCard>
    </>
  );
}
