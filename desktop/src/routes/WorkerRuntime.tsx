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

  useEffect(() => {
    void getWorkerRuntimeCache().then((res) => setCache(res.data));
  }, []);

  const runtime = (cache.runtime as Record<string, unknown> | undefined) ?? {};
  const summary = (cache.task_catalog_summary as Record<string, unknown> | undefined) ?? {};
  const taskStatus = (cache.task_status_summary as Record<string, unknown> | undefined) ?? {};
  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const callLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];

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
          { label: "task call ledger", value: counts.task_status_call_ledger_count as number | undefined },
          { label: "local fallback", value: runtime.local_fallback_enabled, tone: runtime.local_fallback_enabled === false ? "bad" : "good" },
          { label: "Celery", value: runtime.celery_available, tone: runtime.celery_available === true ? "good" : "warn" },
          { label: "Redis package", value: runtime.redis_package_available, tone: runtime.redis_package_available === true ? "good" : "warn" },
          { label: "APScheduler", value: runtime.apscheduler_available, tone: runtime.apscheduler_available === true ? "good" : "warn" },
          { label: "Redis ping", value: cache.redis_pinged === true ? "已 ping" : "未 ping", tone: cache.redis_pinged === true ? "bad" : "good" },
          { label: "scheduler started", value: runtime.scheduler_started === true ? "是" : "否", tone: runtime.scheduler_started === true ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" }
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
          <p>all button gated: {String(summary.all_tasks_button_gated ?? true)}</p>
          <p>call ledger required: {String(summary.call_ledger_required_for_all ?? true)}</p>
          <p>supports local cancel: {String(summary.supports_local_task_cancel ?? true)}</p>
        </PacketCard>

        <PacketCard title="Task status index 摘要" subtitle="GET /api/tasks 的本地状态汇总；不创建任务、不外联" status="task_status_index">
          <p>packet: {String(taskStatus.packet_key ?? "--")}</p>
          <p>task count: {String(taskStatus.task_count ?? 0)}</p>
          <p>status counts: {JSON.stringify(taskStatus.status_counts ?? {})}</p>
          <p>latest task: {String(taskStatus.latest_task_type ?? "--")} / {String(taskStatus.latest_task_status ?? "--")}</p>
          <p>call ledger: {String(taskStatus.call_ledger_count ?? 0)}</p>
          <p>external calls: {String(taskStatus.external_calls_triggered ?? false)}</p>
          <p>does_not_execute_trades: {String(taskStatus.does_not_execute_trades ?? true)}</p>
          <p>does_not_modify_strategy_action: {String(taskStatus.does_not_modify_strategy_action ?? true)}</p>
        </PacketCard>
      </div>

      <PacketCard title="Backend 状态" subtitle="local fallback / Celery / Redis / APScheduler；cache API 不连接外部服务" status="backends">
        <DataLineageTable rows={rows(cache.backend_rows)} />
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

      <PacketCard title="调用血缘" subtitle="local_worker_runtime_cache；不外联、不启动 worker" status="lineage">
        <DataLineageTable rows={callLedger} />
      </PacketCard>

      <PacketCard title="原始 worker runtime cache payload" subtitle="调试用 JSON；不含 token/key/Redis URL" status="safe">
        <JsonDetails title="worker runtime cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
