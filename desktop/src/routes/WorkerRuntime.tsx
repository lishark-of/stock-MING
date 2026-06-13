import { useEffect, useState } from "react";
import { getWorkerRuntimeCache } from "../api/client";
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

  useEffect(() => {
    void getWorkerRuntimeCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const runtime = (cache.runtime as Record<string, unknown> | undefined) ?? {};
  const summary = (cache.task_catalog_summary as Record<string, unknown> | undefined) ?? {};
  const taskImplementation = (cache.task_implementation_status as Record<string, unknown> | undefined) ?? {};
  const taskStatus = (cache.task_status_summary as Record<string, unknown> | undefined) ?? {};
  const taskPersistence = (cache.task_persistence as Record<string, unknown> | undefined) ?? ((taskStatus.persistence as Record<string, unknown> | undefined) ?? {});
  const productionReadiness = (cache.production_readiness as Record<string, unknown> | undefined) ?? {};
  const productionBlockerAudit = (productionReadiness.production_blocker_audit as Record<string, unknown> | undefined) ?? ((cache.worker_production_blocker_audit as Record<string, unknown> | undefined) ?? {});
  const workerHealthcheckQa = (productionReadiness.worker_healthcheck_qa_contract as Record<string, unknown> | undefined) ?? ((cache.worker_healthcheck_qa_contract as Record<string, unknown> | undefined) ?? {});
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
          { label: "manual preflight", value: counts.manual_preflight_step_count as number | undefined },
          { label: "operator actions", value: counts.manual_preflight_operator_action_count as number | undefined, tone: Number(counts.manual_preflight_operator_action_count ?? 0) > 0 ? "warn" : "good" },
          { label: "dispatch tasks", value: counts.dispatch_plan_task_count as number | undefined },
          { label: "dispatch queues", value: counts.dispatch_plan_queue_count as number | undefined },
          { label: "worker blockers", value: productionBlockerAudit.blocking_criterion_count ?? counts.production_blocker_audit_count, tone: Number(productionBlockerAudit.blocking_criterion_count ?? counts.production_blocker_audit_count ?? 0) > 0 ? "warn" : "good" },
          { label: "healthcheck pending", value: workerHealthcheckQa.pending_criterion_count ?? counts.worker_healthcheck_qa_pending_count, tone: Number(workerHealthcheckQa.pending_criterion_count ?? counts.worker_healthcheck_qa_pending_count ?? 0) > 0 ? "warn" : "good" },
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
      </PacketCard>
    </>
  );
}
