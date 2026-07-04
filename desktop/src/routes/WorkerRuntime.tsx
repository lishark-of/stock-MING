import { useEffect, useState } from "react";
import {
  getWorkerRuntimeCache,
  runWorkerActivationReview,
  runWorkerProductionEvidencePlan,
  runWorkerRuntimeQaDryRun,
  runWorkerRuntimeQaExecution,
  runWorkerRuntimeQaExecutionRequest,
  runWorkerSyntheticHealthcheck
} from "../api/client";
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
  const [activationReviewResult, setActivationReviewResult] = useState<Record<string, unknown>>({});
  const [activationReviewRunning, setActivationReviewRunning] = useState(false);
  const [activationReviewError, setActivationReviewError] = useState("");
  const [productionEvidencePlanResult, setProductionEvidencePlanResult] = useState<Record<string, unknown>>({});
  const [productionEvidencePlanRunning, setProductionEvidencePlanRunning] = useState(false);
  const [productionEvidencePlanError, setProductionEvidencePlanError] = useState("");
  const [runtimeQaExecutionRequestResult, setRuntimeQaExecutionRequestResult] = useState<Record<string, unknown>>({});
  const [runtimeQaExecutionRequestRunning, setRuntimeQaExecutionRequestRunning] = useState(false);
  const [runtimeQaExecutionRequestError, setRuntimeQaExecutionRequestError] = useState("");
  const [runtimeQaDryRunResult, setRuntimeQaDryRunResult] = useState<Record<string, unknown>>({});
  const [runtimeQaDryRunRunning, setRuntimeQaDryRunRunning] = useState(false);
  const [runtimeQaDryRunError, setRuntimeQaDryRunError] = useState("");
  const [runtimeQaExecutionResult, setRuntimeQaExecutionResult] = useState<Record<string, unknown>>({});
  const [runtimeQaExecutionRunning, setRuntimeQaExecutionRunning] = useState(false);
  const [runtimeQaExecutionError, setRuntimeQaExecutionError] = useState("");

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

  const launchActivationReview = () => {
    setActivationReviewRunning(true);
    setActivationReviewError("");
    void runWorkerActivationReview({
      requested_from: "worker_runtime_page",
      operator_approved: true,
      review_scope: "worker_activation_local_review_no_process_start"
    })
      .then((res) => {
        setActivationReviewResult(res.data);
        return refreshCache();
      })
      .catch((err: unknown) => setActivationReviewError(err instanceof Error ? err.message : String(err)))
      .finally(() => setActivationReviewRunning(false));
  };

  const launchProductionEvidencePlan = () => {
    setProductionEvidencePlanRunning(true);
    setProductionEvidencePlanError("");
    void runWorkerProductionEvidencePlan({
      requested_from: "worker_runtime_page",
      operator_approved: true,
      plan_scope: "worker_production_runtime_evidence_plan_no_process_start"
    })
      .then((res) => {
        setProductionEvidencePlanResult(res.data);
        return refreshCache();
      })
      .catch((err: unknown) => setProductionEvidencePlanError(err instanceof Error ? err.message : String(err)))
      .finally(() => setProductionEvidencePlanRunning(false));
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
  const workerActivationReviewTaskReceipt =
    (productionReadiness.worker_activation_review_task_receipt as Record<string, unknown> | undefined) ??
    ((cache.worker_activation_review_task_receipt as Record<string, unknown> | undefined) ?? {});
  const workerProductionEvidencePlanReceipt =
    (productionReadiness.worker_production_evidence_plan_receipt as Record<string, unknown> | undefined) ??
    ((cache.worker_production_evidence_plan_receipt as Record<string, unknown> | undefined) ?? {});
  const workerRuntimeQaExecutionRecipe =
    (productionReadiness.worker_runtime_qa_execution_recipe as Record<string, unknown> | undefined) ??
    ((cache.worker_runtime_qa_execution_recipe as Record<string, unknown> | undefined) ?? {});
  const workerRuntimeQaExecutionRows =
    (productionReadiness.worker_runtime_qa_execution_recipe_rows as Array<Record<string, unknown>> | undefined) ??
    ((cache.worker_runtime_qa_execution_recipe_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const workerRuntimeQaExecutionRequest =
    (productionReadiness.worker_runtime_qa_execution_request_receipt as Record<string, unknown> | undefined) ??
    ((cache.worker_runtime_qa_execution_request_receipt as Record<string, unknown> | undefined) ?? {});
  const workerRuntimeQaExecutionRequestRows =
    (productionReadiness.worker_runtime_qa_execution_request_rows as Array<Record<string, unknown>> | undefined) ??
    ((cache.worker_runtime_qa_execution_request_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const workerRuntimeQaDryRun =
    (productionReadiness.worker_runtime_qa_dry_run_receipt as Record<string, unknown> | undefined) ??
    ((cache.worker_runtime_qa_dry_run_receipt as Record<string, unknown> | undefined) ?? {});
  const workerRuntimeQaDryRunRows =
    (productionReadiness.worker_runtime_qa_dry_run_rows as Array<Record<string, unknown>> | undefined) ??
    ((cache.worker_runtime_qa_dry_run_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const workerRuntimeQaDryRunPhaseRows =
    (productionReadiness.worker_runtime_qa_dry_run_phase_rows as Array<Record<string, unknown>> | undefined) ??
    ((cache.worker_runtime_qa_dry_run_phase_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const workerRuntimeQaExecutionReceipt =
    (productionReadiness.worker_runtime_qa_execution_receipt as Record<string, unknown> | undefined) ??
    ((cache.worker_runtime_qa_execution_receipt as Record<string, unknown> | undefined) ?? {});
  const workerRuntimeQaExecutionEvidenceRows =
    (productionReadiness.worker_runtime_qa_execution_rows as Array<Record<string, unknown>> | undefined) ??
    ((cache.worker_runtime_qa_execution_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const workerRuntimeQaExecutionPhaseRows =
    (productionReadiness.worker_runtime_qa_execution_phase_rows as Array<Record<string, unknown>> | undefined) ??
    ((cache.worker_runtime_qa_execution_phase_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const workerRuntimeDurableEvidenceRecipe =
    (productionReadiness.worker_runtime_durable_evidence_recipe as Record<string, unknown> | undefined) ??
    ((cache.worker_runtime_durable_evidence_recipe as Record<string, unknown> | undefined) ?? {});
  const workerRuntimeDurableEvidenceRows =
    (productionReadiness.worker_runtime_durable_evidence_rows as Array<Record<string, unknown>> | undefined) ??
    ((cache.worker_runtime_durable_evidence_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const visibleHealthcheck = Object.keys(healthcheckResult).length ? healthcheckResult : workerSyntheticHealthcheck;
  const visibleActivationReview = Object.keys(activationReviewResult).length
    ? ((activationReviewResult.worker_activation_review_task_receipt as Record<string, unknown> | undefined) ?? activationReviewResult)
    : workerActivationReviewTaskReceipt;
  const visibleProductionEvidencePlan = Object.keys(productionEvidencePlanResult).length
    ? ((productionEvidencePlanResult.worker_production_evidence_plan_receipt as Record<string, unknown> | undefined) ?? productionEvidencePlanResult)
    : workerProductionEvidencePlanReceipt;
  const visibleRuntimeQaExecutionRequest = Object.keys(runtimeQaExecutionRequestResult).length
    ? ((runtimeQaExecutionRequestResult.worker_runtime_qa_execution_request_receipt as Record<string, unknown> | undefined) ?? runtimeQaExecutionRequestResult)
    : workerRuntimeQaExecutionRequest;
  const visibleRuntimeQaDryRun = Object.keys(runtimeQaDryRunResult).length
    ? ((runtimeQaDryRunResult.worker_runtime_qa_dry_run_receipt as Record<string, unknown> | undefined) ?? runtimeQaDryRunResult)
    : workerRuntimeQaDryRun;
  const visibleRuntimeQaExecution = Object.keys(runtimeQaExecutionResult).length
    ? ((runtimeQaExecutionResult.worker_runtime_qa_execution_receipt as Record<string, unknown> | undefined) ?? runtimeQaExecutionResult)
    : workerRuntimeQaExecutionReceipt;
  const launchRuntimeQaExecutionRequest = () => {
    setRuntimeQaExecutionRequestRunning(true);
    setRuntimeQaExecutionRequestError("");
    void runWorkerRuntimeQaExecutionRequest({
      requested_from: "worker_runtime_page",
      operator_approved: true,
      evidence_plan_scope_hash: String(visibleProductionEvidencePlan.scope_ticket_sha256 ?? ""),
      runtime_qa_scope_hash: String(workerRuntimeQaExecutionRecipe.runtime_qa_scope_hash ?? "")
    })
      .then((res) => {
        setRuntimeQaExecutionRequestResult(res.data);
        return refreshCache();
      })
      .catch((err: unknown) => setRuntimeQaExecutionRequestError(err instanceof Error ? err.message : String(err)))
      .finally(() => setRuntimeQaExecutionRequestRunning(false));
  };
  const launchRuntimeQaDryRun = () => {
    setRuntimeQaDryRunRunning(true);
    setRuntimeQaDryRunError("");
    void runWorkerRuntimeQaDryRun({
      requested_from: "worker_runtime_page",
      operator_approved: true,
      request_task_id: String(visibleRuntimeQaExecutionRequest.request_task_id ?? ""),
      evidence_plan_scope_hash: String(visibleRuntimeQaExecutionRequest.production_evidence_plan_scope_hash ?? ""),
      runtime_qa_scope_hash: String(visibleRuntimeQaExecutionRequest.runtime_qa_scope_hash ?? "")
    })
      .then((res) => {
        setRuntimeQaDryRunResult(res.data);
        return refreshCache();
      })
      .catch((err: unknown) => setRuntimeQaDryRunError(err instanceof Error ? err.message : String(err)))
      .finally(() => setRuntimeQaDryRunRunning(false));
  };
  const launchRuntimeQaExecution = () => {
    setRuntimeQaExecutionRunning(true);
    setRuntimeQaExecutionError("");
    void runWorkerRuntimeQaExecution({
      requested_from: "worker_runtime_page",
      operator_approved: true,
      dry_run_task_id: String(visibleRuntimeQaDryRun.dry_run_task_id ?? ""),
      evidence_plan_scope_hash: String(visibleRuntimeQaDryRun.production_evidence_plan_scope_hash ?? ""),
      runtime_qa_scope_hash: String(visibleRuntimeQaDryRun.runtime_qa_scope_hash ?? "")
    })
      .then((res) => {
        setRuntimeQaExecutionResult(res.data);
        return refreshCache();
      })
      .catch((err: unknown) => setRuntimeQaExecutionError(err instanceof Error ? err.message : String(err)))
      .finally(() => setRuntimeQaExecutionRunning(false));
  };
  const workerPacketEvidenceRows = [
    {
      packet: "synthetic_healthcheck",
      route: "POST /api/worker/synthetic-healthcheck",
      source_packet_read_status:
        workerSyntheticHealthcheck.source_packet_read_status ??
        productionReadiness.worker_synthetic_healthcheck_source_packet_read_status ??
        cache.worker_synthetic_healthcheck_source_packet_read_status ??
        "meta_missing",
      source_packet_present:
        workerSyntheticHealthcheck.source_packet_present ??
        productionReadiness.worker_synthetic_healthcheck_source_packet_present ??
        cache.worker_synthetic_healthcheck_source_packet_present ??
        false,
      cache_get_initializes_meta_store: workerSyntheticHealthcheck.cache_get_initializes_meta_store ?? false,
      worker_started: false,
      redis_pinged: false,
      task_dispatched_by_get: false,
      external_calls_triggered: false
    },
    {
      packet: "activation_review",
      route: "POST /api/worker/activation-review",
      source_packet_read_status:
        workerActivationReviewTaskReceipt.source_packet_read_status ??
        productionReadiness.worker_activation_review_source_packet_read_status ??
        cache.worker_activation_review_source_packet_read_status ??
        "meta_missing",
      source_packet_present:
        workerActivationReviewTaskReceipt.source_packet_present ??
        productionReadiness.worker_activation_review_source_packet_present ??
        cache.worker_activation_review_source_packet_present ??
        false,
      cache_get_initializes_meta_store: workerActivationReviewTaskReceipt.cache_get_initializes_meta_store ?? false,
      worker_started: false,
      redis_pinged: false,
      task_dispatched_by_get: false,
      external_calls_triggered: false
    },
    {
      packet: "production_evidence_plan",
      route: "POST /api/worker/production-evidence-plan",
      source_packet_read_status:
        workerProductionEvidencePlanReceipt.source_packet_read_status ??
        productionReadiness.worker_production_evidence_plan_source_packet_read_status ??
        cache.worker_production_evidence_plan_source_packet_read_status ??
        "meta_missing",
      source_packet_present:
        workerProductionEvidencePlanReceipt.source_packet_present ??
        productionReadiness.worker_production_evidence_plan_source_packet_present ??
        cache.worker_production_evidence_plan_source_packet_present ??
        false,
      cache_get_initializes_meta_store: workerProductionEvidencePlanReceipt.cache_get_initializes_meta_store ?? false,
      worker_started: false,
      redis_pinged: false,
      task_dispatched_by_get: false,
      external_calls_triggered: false
    },
    {
      packet: "runtime_qa_execution_request",
      route: "POST /api/worker/runtime-qa-execution-request",
      source_packet_read_status:
        workerRuntimeQaExecutionRequest.source_packet_read_status ??
        productionReadiness.worker_runtime_qa_execution_request_source_packet_read_status ??
        cache.worker_runtime_qa_execution_request_source_packet_read_status ??
        "meta_missing",
      source_packet_present:
        workerRuntimeQaExecutionRequest.source_packet_present ??
        productionReadiness.worker_runtime_qa_execution_request_source_packet_present ??
        cache.worker_runtime_qa_execution_request_source_packet_present ??
        false,
      cache_get_initializes_meta_store: workerRuntimeQaExecutionRequest.cache_get_initializes_meta_store ?? false,
      worker_started: false,
      redis_pinged: false,
      task_dispatched_by_get: false,
      external_calls_triggered: false
    },
    {
      packet: "runtime_qa_dry_run",
      route: "POST /api/worker/runtime-qa-dry-run",
      source_packet_read_status:
        workerRuntimeQaDryRun.source_packet_read_status ??
        productionReadiness.worker_runtime_qa_dry_run_source_packet_read_status ??
        cache.worker_runtime_qa_dry_run_source_packet_read_status ??
        "meta_missing",
      source_packet_present:
        workerRuntimeQaDryRun.source_packet_present ??
        productionReadiness.worker_runtime_qa_dry_run_source_packet_present ??
        cache.worker_runtime_qa_dry_run_source_packet_present ??
        false,
      cache_get_initializes_meta_store: workerRuntimeQaDryRun.cache_get_initializes_meta_store ?? false,
      worker_started: false,
      redis_pinged: false,
      task_dispatched_by_get: false,
      external_calls_triggered: false
    },
    {
      packet: "runtime_qa_execution",
      route: "POST /api/worker/runtime-qa-execution",
      source_packet_read_status:
        workerRuntimeQaExecutionReceipt.source_packet_read_status ??
        productionReadiness.worker_runtime_qa_execution_source_packet_read_status ??
        cache.worker_runtime_qa_execution_source_packet_read_status ??
        "meta_missing",
      source_packet_present:
        workerRuntimeQaExecutionReceipt.source_packet_present ??
        productionReadiness.worker_runtime_qa_execution_source_packet_present ??
        cache.worker_runtime_qa_execution_source_packet_present ??
        false,
      cache_get_initializes_meta_store: workerRuntimeQaExecutionReceipt.cache_get_initializes_meta_store ?? false,
      worker_started: false,
      redis_pinged: false,
      task_dispatched_by_get: false,
      external_calls_triggered: false
    }
  ];
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
  const workerRuntimeStateLabel = runtime.local_fallback_enabled === false
    ? "local fallback 不可用，先看任务目录和 cache 状态"
    : visibleRuntimeQaExecution.local_runtime_qa_execution_done === true
      ? "本地 fallback runtime QA 已有可读 evidence；Celery/Redis 仍未作为生产完成"
      : visibleRuntimeQaDryRun.local_dry_run_ready === true
        ? "runtime QA dry-run 已可读；真实 runtime QA execution 需显式按钮"
        : visibleRuntimeQaExecutionRequest.local_execution_request_ready === true
          ? "runtime QA execution request 已绑定 scope；dry-run 待显式按钮"
          : "local fallback 可读，Celery/Redis 生产 QA 仍待显式任务";
  const workerRuntimeNextStep = visibleRuntimeQaExecution.local_runtime_qa_execution_done === true
    ? "查看 durable evidence recipe 和 promotion blocker；不要把 local fallback 当 Celery/Redis 生产完成"
    : visibleRuntimeQaDryRun.local_dry_run_ready === true
      ? "下方显式运行 runtime QA execution；它只做本地 fallback round-trip，不启动 Celery/Redis"
      : visibleRuntimeQaExecutionRequest.local_execution_request_ready === true
        ? "下方显式运行 runtime QA dry-run；仍不启动 worker、不 ping Redis"
        : "先看 synthetic healthcheck、activation review 和 evidence plan 的缺口";
  const workerOrdinaryFirstScreenSentence =
    `Worker 运行时：${workerRuntimeStateLabel}；下一步：${workerRuntimeNextStep}；边界：GET cache 不启动 Celery/Redis，不派发 provider/model task。`;
  const workerOrdinaryFirstScreenItems = [
    {
      label: "运行方式",
      value: workerRuntimeStateLabel,
      tone: runtime.local_fallback_enabled === false ? "bad" as const : "good" as const
    },
    {
      label: "本地任务",
      value: `tasks=${String(counts.task_count ?? 0)} / local=${String(counts.implemented_local_task_count ?? taskImplementation.implemented_local_task_count ?? 0)} / logs=${String(counts.worker_task_log_count ?? taskStatus.task_log_count ?? 0)}`,
      tone: "good" as const
    },
    {
      label: "Runtime QA",
      value: workerRuntimeNextStep,
      tone: visibleRuntimeQaExecution.local_runtime_qa_execution_done === true ? "good" as const : "warn" as const
    },
    {
      label: "Celery/Redis",
      value: `Celery=${String(runtime.celery_available ?? false)} / Redis package=${String(runtime.redis_package_available ?? false)} / Redis ping=${String(cache.redis_pinged ?? false)}`,
      tone: cache.redis_pinged === true || runtime.scheduler_started === true ? "bad" as const : "warn" as const
    },
    {
      label: "Storage 支撑",
      value: "Storage 页面只读展示 DuckDB/Parquet/SQLite；Worker GET 不写 storage、不启动迁移",
      tone: "good" as const
    },
    {
      label: "安全边界",
      value: "GET worker 只读；不启动 Celery/Redis/APScheduler、不派发任务、不调用 provider/model、不交易",
      tone: "good" as const
    }
  ];

  return (
    <>
      <div className="page-head">
        <h1>Worker 运行时</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <div aria-label="worker ordinary first screen status">
        <h3>运行时一眼状态</h3>
        <p className="ordinary-status-note" aria-label="worker ordinary first screen sentence" aria-live="polite">{workerOrdinaryFirstScreenSentence}</p>
        <MetricGrid items={workerOrdinaryFirstScreenItems} />
        <div className="actions" aria-label="worker ordinary first screen safe actions">
          <button onClick={refreshCache} aria-label="refresh local worker cache only">刷新本地 worker cache</button>
          <a href="#storage" aria-label="open storage support from worker">看 Storage 支撑</a>
          <a href="#tasks" aria-label="open task catalog from worker runtime">看任务目录</a>
        </div>
        <p className="risk-note">首屏只汇总 local fallback、task/log 状态、runtime QA 下一步和 Storage 支撑边界；刷新只读取本地 GET cache，链接只切换本地页面，不启动 Celery/Redis/APScheduler、不创建 task、不调用 Tushare/DeepSeek/GitHub、不下单。</p>
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
          { label: "review task", value: visibleActivationReview.activation_review_ready === true ? "ready" : "pending", tone: visibleActivationReview.activation_review_ready === true ? "good" : "warn" },
          { label: "review task blockers", value: visibleActivationReview.production_blocker_count ?? counts.worker_activation_review_task_production_blocker_count, tone: Number(visibleActivationReview.production_blocker_count ?? counts.worker_activation_review_task_production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "evidence plan", value: visibleProductionEvidencePlan.evidence_plan_ready === true ? "ready" : "pending", tone: visibleProductionEvidencePlan.evidence_plan_ready === true ? "good" : "warn" },
          { label: "runtime QA gaps", value: visibleProductionEvidencePlan.production_blocker_count ?? counts.worker_production_evidence_plan_production_blocker_count, tone: Number(visibleProductionEvidencePlan.production_blocker_count ?? counts.worker_production_evidence_plan_production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "runtime request", value: visibleRuntimeQaExecutionRequest.local_execution_request_ready === true ? "ready" : "pending", tone: visibleRuntimeQaExecutionRequest.local_execution_request_ready === true ? "good" : "warn" },
          { label: "runtime dry-run", value: visibleRuntimeQaDryRun.local_dry_run_ready === true ? "ready" : "pending", tone: visibleRuntimeQaDryRun.local_dry_run_ready === true ? "good" : "warn" },
          { label: "runtime recipe", value: String(workerRuntimeQaExecutionRecipe.status ?? "missing"), tone: workerRuntimeQaExecutionRecipe.local_recipe_ready === true ? "good" : "warn" },
          { label: "runtime phases", value: counts.worker_runtime_qa_execution_recipe_pending_phase_count ?? workerRuntimeQaExecutionRecipe.pending_phase_count ?? workerRuntimeQaExecutionRows.length, tone: Number(counts.worker_runtime_qa_execution_recipe_pending_phase_count ?? workerRuntimeQaExecutionRecipe.pending_phase_count ?? workerRuntimeQaExecutionRows.length) > 0 ? "warn" : "good" },
          { label: "durable evidence", value: String(workerRuntimeDurableEvidenceRecipe.status ?? "missing"), tone: workerRuntimeDurableEvidenceRecipe.local_recipe_ready === true ? "good" : "warn" },
          { label: "durable blockers", value: counts.worker_runtime_durable_evidence_production_blocker_count ?? workerRuntimeDurableEvidenceRecipe.production_blocker_count ?? workerRuntimeDurableEvidenceRows.length, tone: Number(counts.worker_runtime_durable_evidence_production_blocker_count ?? workerRuntimeDurableEvidenceRecipe.production_blocker_count ?? workerRuntimeDurableEvidenceRows.length) > 0 ? "warn" : "good" },
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

      <PacketCard title="Worker persisted packet evidence" subtitle="只读展示显式 POST 证据包读取状态；证据缺失时不初始化 SQLite meta" status="packet_reader_no_init">
        <p>synthetic / activation / evidence plan / request source: {String(workerPacketEvidenceRows[0].source_packet_read_status)} / {String(workerPacketEvidenceRows[1].source_packet_read_status)} / {String(workerPacketEvidenceRows[2].source_packet_read_status)} / {String(workerPacketEvidenceRows[3].source_packet_read_status)}</p>
        <p>source_packet_present: {String(workerPacketEvidenceRows[0].source_packet_present)} / {String(workerPacketEvidenceRows[1].source_packet_present)} / {String(workerPacketEvidenceRows[2].source_packet_present)} / {String(workerPacketEvidenceRows[3].source_packet_present)}</p>
        <p>这张表只说明 cache 读取显式 POST 留下的 packet，不启动 worker、不 ping Redis、不派发任务、不调用 Tushare/DeepSeek/GitHub。</p>
        <DataLineageTable rows={workerPacketEvidenceRows} />
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

      <PacketCard title="Worker activation review task" subtitle="POST /api/worker/activation-review：按钮门控审查本地 healthcheck 与 activation receipt，不启动进程" status={String(visibleActivationReview.status ?? "worker_activation_review_task_pending")}>
        <div className="actions">
          <button onClick={launchActivationReview} disabled={activationReviewRunning || healthcheckRunning}>
            {activationReviewRunning ? "审查中" : "审查 activation 本地证据"}
          </button>
        </div>
        {activationReviewError ? <p className="risk-note">activation_review_error: {activationReviewError}</p> : null}
        <p>schema_version: {String(visibleActivationReview.schema_version ?? "worker_activation_review_task_receipt.v1")}</p>
        <p>scope: {String(visibleActivationReview.scope ?? "button_gated_worker_activation_review_no_process_start")}</p>
        <p>explicit_activation_review_done: {String(visibleActivationReview.explicit_activation_review_done === true)}</p>
        <p>operator_approved: {String(visibleActivationReview.operator_approved === true)}</p>
        <p>activation_review_ready / ready_for_manual_celery_redis_activation_review: {String(visibleActivationReview.activation_review_ready === true)} / {String(visibleActivationReview.ready_for_manual_celery_redis_activation_review === true)}</p>
        <p>production_worker_complete / activation_ready: {String(visibleActivationReview.production_worker_complete === true)} / {String(visibleActivationReview.activation_ready === true)}</p>
        <p>synthetic_healthcheck_executed / task_log_round_trip_verified: {String(visibleActivationReview.synthetic_healthcheck_executed === true)} / {String(visibleActivationReview.task_log_round_trip_verified === true)}</p>
        <p>starts_celery_worker / pings_redis / starts_scheduler / task_dispatched: {String(visibleActivationReview.starts_celery_worker === true)} / {String(visibleActivationReview.pings_redis === true)} / {String(visibleActivationReview.starts_scheduler === true)} / {String(visibleActivationReview.task_dispatched === true)}</p>
        <p>external_calls_triggered / tushare_called / deepseek_called / github_called: {String(visibleActivationReview.external_calls_triggered === true)} / {String(visibleActivationReview.tushare_called === true)} / {String(visibleActivationReview.deepseek_called === true)} / {String(visibleActivationReview.github_called === true)}</p>
        <p>not_allowed_next_steps: {Array.isArray(visibleActivationReview.not_allowed_next_steps) ? visibleActivationReview.not_allowed_next_steps.join(" / ") : "start Celery from activation review / ping Redis from activation review / activation review as production worker completion"}</p>
        <p>该任务只把本地 healthcheck 与 activation receipt 审查成票据；不能当作 Celery/Redis process proof 或 production worker complete。</p>
        <DataLineageTable rows={rows(productionReadiness.worker_activation_review_task_rows ?? cache.worker_activation_review_task_rows ?? visibleActivationReview.rows)} />
      </PacketCard>


      <PacketCard title="Worker production evidence plan" subtitle="POST /api/worker/production-evidence-plan：生成后续 Celery/Redis runtime QA scope ticket，不启动进程" status={String(visibleProductionEvidencePlan.status ?? "worker_production_evidence_plan_pending_activation_review")}>
        <div className="actions">
          <button onClick={launchProductionEvidencePlan} disabled={productionEvidencePlanRunning || activationReviewRunning || healthcheckRunning}>
            {productionEvidencePlanRunning ? "生成中" : "生成 runtime QA 证据计划"}
          </button>
        </div>
        {productionEvidencePlanError ? <p className="risk-note">production_evidence_plan_error: {productionEvidencePlanError}</p> : null}
        <p>schema_version: {String(visibleProductionEvidencePlan.schema_version ?? "worker_production_evidence_plan_receipt.v1")}</p>
        <p>scope: {String(visibleProductionEvidencePlan.scope ?? "button_gated_worker_production_evidence_plan_no_process_start")}</p>
        <p>explicit_evidence_plan_done / operator_approved: {String(visibleProductionEvidencePlan.explicit_evidence_plan_done === true)} / {String(visibleProductionEvidencePlan.operator_approved === true)}</p>
        <p>evidence_plan_ready / ready_for_manual_runtime_qa: {String(visibleProductionEvidencePlan.evidence_plan_ready === true)} / {String(visibleProductionEvidencePlan.ready_for_manual_runtime_qa === true)}</p>
        <p>activation_review_task_ready / synthetic_healthcheck_executed: {String(visibleProductionEvidencePlan.activation_review_task_ready === true)} / {String(visibleProductionEvidencePlan.synthetic_healthcheck_executed === true)}</p>
        <p>scope_ticket_sha256: {String(visibleProductionEvidencePlan.scope_ticket_sha256 ?? "")}</p>
        <p>production_worker_complete / activation_ready: {String(visibleProductionEvidencePlan.production_worker_complete === true)} / {String(visibleProductionEvidencePlan.activation_ready === true)}</p>
        <p>starts_celery_worker / pings_redis / starts_scheduler / task_dispatched: {String(visibleProductionEvidencePlan.starts_celery_worker === true)} / {String(visibleProductionEvidencePlan.pings_redis === true)} / {String(visibleProductionEvidencePlan.starts_scheduler === true)} / {String(visibleProductionEvidencePlan.task_dispatched === true)}</p>
        <p>external_calls_triggered / tushare_called / deepseek_called / github_called: {String(visibleProductionEvidencePlan.external_calls_triggered === true)} / {String(visibleProductionEvidencePlan.tushare_called === true)} / {String(visibleProductionEvidencePlan.deepseek_called === true)} / {String(visibleProductionEvidencePlan.github_called === true)}</p>
        <p>missing_evidence_items: {Array.isArray(visibleProductionEvidencePlan.missing_evidence_items) ? visibleProductionEvidencePlan.missing_evidence_items.join(" / ") : "celery worker process evidence / redis broker reachability evidence / cross-process controls / append-only worker logs / scheduler runtime evidence"}</p>
        <p>not_allowed_next_steps: {Array.isArray(visibleProductionEvidencePlan.not_allowed_next_steps) ? visibleProductionEvidencePlan.not_allowed_next_steps.join(" / ") : "start Celery from evidence plan / ping Redis from evidence plan / evidence plan as production worker completion"}</p>
        <p>该计划只生成后续 runtime QA 的安全 scope ticket；不能当作 Celery/Redis process proof 或 production worker complete。</p>
        <DataLineageTable rows={rows(productionReadiness.worker_production_evidence_plan_rows ?? cache.worker_production_evidence_plan_rows ?? visibleProductionEvidencePlan.rows)} />
      </PacketCard>

      <PacketCard title="Worker runtime QA execution request" subtitle="POST /api/worker/runtime-qa-execution-request：绑定 evidence plan 与 runtime recipe scope；不启动进程" status={String(visibleRuntimeQaExecutionRequest.status ?? "worker_runtime_qa_execution_request_missing")}>
        <div className="actions">
          <button
            onClick={launchRuntimeQaExecutionRequest}
            disabled={
              runtimeQaExecutionRequestRunning ||
              productionEvidencePlanRunning ||
              activationReviewRunning ||
              healthcheckRunning ||
              !visibleProductionEvidencePlan.scope_ticket_sha256 ||
              !workerRuntimeQaExecutionRecipe.runtime_qa_scope_hash
            }
          >
            {runtimeQaExecutionRequestRunning ? "生成中" : "生成 runtime QA request"}
          </button>
        </div>
        {runtimeQaExecutionRequestError ? <p className="risk-note">runtime_qa_execution_request_error: {runtimeQaExecutionRequestError}</p> : null}
        <p>schema_version: {String(visibleRuntimeQaExecutionRequest.schema_version ?? "worker_runtime_qa_execution_request_receipt.v1")}</p>
        <p>scope: {String(visibleRuntimeQaExecutionRequest.scope ?? "button_gated_worker_runtime_qa_execution_request_no_process_start")}</p>
        <p>explicit_execution_request_done / operator_approved: {String(visibleRuntimeQaExecutionRequest.explicit_execution_request_done === true)} / {String(visibleRuntimeQaExecutionRequest.operator_approved === true)}</p>
        <p>local_execution_request_ready / ready_for_manual_runtime_qa_task_submission: {String(visibleRuntimeQaExecutionRequest.local_execution_request_ready === true)} / {String(visibleRuntimeQaExecutionRequest.ready_for_manual_runtime_qa_task_submission === true)}</p>
        <p>evidence_plan_ready / recipe_ready: {String(visibleRuntimeQaExecutionRequest.production_evidence_plan_ready === true)} / {String(visibleRuntimeQaExecutionRequest.runtime_qa_execution_recipe_ready === true)}</p>
        <p>evidence_plan_scope_hash_short / runtime_qa_scope_hash_short: {String(visibleRuntimeQaExecutionRequest.production_evidence_plan_scope_hash_short ?? "")} / {String(visibleRuntimeQaExecutionRequest.runtime_qa_scope_hash_short ?? "")}</p>
        <p>requested hash matches: {String(visibleRuntimeQaExecutionRequest.requested_evidence_plan_scope_hash_matches_latest === true)} / {String(visibleRuntimeQaExecutionRequest.requested_runtime_qa_scope_hash_matches_latest === true)}</p>
        <p>target: {String(visibleRuntimeQaExecutionRequest.target_worker_task_route ?? "future POST /api/worker/runtime-qa-execution")} / {String(visibleRuntimeQaExecutionRequest.target_worker_task_type ?? "run_worker_runtime_qa_execution")}</p>
        <p>runtime_qa_task_created / runtime_qa_task_executed: {String(visibleRuntimeQaExecutionRequest.runtime_qa_task_created === true)} / {String(visibleRuntimeQaExecutionRequest.runtime_qa_task_executed === true)}</p>
        <p>worker_started / redis_pinged / scheduler_started / task_dispatched: {String(visibleRuntimeQaExecutionRequest.worker_started === true)} / {String(visibleRuntimeQaExecutionRequest.redis_pinged === true)} / {String(visibleRuntimeQaExecutionRequest.scheduler_started === true)} / {String(visibleRuntimeQaExecutionRequest.task_dispatched === true)}</p>
        <p>external_calls_triggered / tushare_called / deepseek_called / github_called: {String(visibleRuntimeQaExecutionRequest.external_calls_triggered === true)} / {String(visibleRuntimeQaExecutionRequest.tushare_called === true)} / {String(visibleRuntimeQaExecutionRequest.deepseek_called === true)} / {String(visibleRuntimeQaExecutionRequest.github_called === true)}</p>
        <p>not_allowed_next_steps: {Array.isArray(visibleRuntimeQaExecutionRequest.not_allowed_next_steps) ? visibleRuntimeQaExecutionRequest.not_allowed_next_steps.join(" / ") : "start Celery from execution request / ping Redis from execution request / mark_production_worker_complete_from_execution_request"}</p>
        <p>该 request 只绑定后续 runtime QA scope；不会创建或执行 runtime QA task，不能当作 production worker complete。</p>
        <DataLineageTable rows={rows(productionReadiness.worker_runtime_qa_execution_request_rows ?? cache.worker_runtime_qa_execution_request_rows ?? visibleRuntimeQaExecutionRequest.rows)} />
      </PacketCard>

      <PacketCard title="Worker runtime QA dry-run" subtitle="POST /api/worker/runtime-qa-dry-run：审查 request ticket 与 runtime recipe；不启动进程、不派发任务" status={String(visibleRuntimeQaDryRun.status ?? "worker_runtime_qa_dry_run_missing")}>
        <div className="actions">
          <button
            onClick={launchRuntimeQaDryRun}
            disabled={
              runtimeQaDryRunRunning ||
              runtimeQaExecutionRequestRunning ||
              productionEvidencePlanRunning ||
              activationReviewRunning ||
              healthcheckRunning ||
              !visibleRuntimeQaExecutionRequest.request_task_id ||
              !visibleRuntimeQaExecutionRequest.production_evidence_plan_scope_hash ||
              !visibleRuntimeQaExecutionRequest.runtime_qa_scope_hash
            }
          >
            {runtimeQaDryRunRunning ? "演练中" : "生成 runtime QA dry-run"}
          </button>
        </div>
        {runtimeQaDryRunError ? <p className="risk-note">runtime_qa_dry_run_error: {runtimeQaDryRunError}</p> : null}
        <p>schema_version: {String(visibleRuntimeQaDryRun.schema_version ?? "worker_runtime_qa_dry_run_receipt.v1")}</p>
        <p>scope: {String(visibleRuntimeQaDryRun.scope ?? "button_gated_worker_runtime_qa_dry_run_no_process_start_no_dispatch")}</p>
        <p>explicit_runtime_qa_dry_run_done / operator_approved: {String(visibleRuntimeQaDryRun.explicit_runtime_qa_dry_run_done === true)} / {String(visibleRuntimeQaDryRun.operator_approved === true)}</p>
        <p>local_dry_run_ready / ready_for_separate_runtime_qa_execution: {String(visibleRuntimeQaDryRun.local_dry_run_ready === true)} / {String(visibleRuntimeQaDryRun.ready_for_separate_runtime_qa_execution === true)}</p>
        <p>request_ready / recipe_ready: {String(visibleRuntimeQaDryRun.runtime_qa_execution_request_ready === true)} / {String(visibleRuntimeQaDryRun.runtime_qa_execution_recipe_ready === true)}</p>
        <p>request_task_id matches latest: {String(visibleRuntimeQaDryRun.requested_runtime_qa_execution_request_task_id_matches_latest === true)}</p>
        <p>evidence_plan_scope_hash_short / runtime_qa_scope_hash_short: {String(visibleRuntimeQaDryRun.production_evidence_plan_scope_hash_short ?? "")} / {String(visibleRuntimeQaDryRun.runtime_qa_scope_hash_short ?? "")}</p>
        <p>requested hash matches: {String(visibleRuntimeQaDryRun.requested_evidence_plan_scope_hash_matches_latest === true)} / {String(visibleRuntimeQaDryRun.requested_runtime_qa_scope_hash_matches_latest === true)}</p>
        <p>target: {String(visibleRuntimeQaDryRun.target_worker_task_route ?? "future POST /api/worker/runtime-qa-execution")} / {String(visibleRuntimeQaDryRun.target_worker_task_type ?? "run_worker_runtime_qa_execution")}</p>
        <p>runtime_qa_task_created / runtime_qa_task_executed: {String(visibleRuntimeQaDryRun.runtime_qa_task_created === true)} / {String(visibleRuntimeQaDryRun.runtime_qa_task_executed === true)}</p>
        <p>worker_started / redis_pinged / scheduler_started / task_dispatched: {String(visibleRuntimeQaDryRun.worker_started === true)} / {String(visibleRuntimeQaDryRun.redis_pinged === true)} / {String(visibleRuntimeQaDryRun.scheduler_started === true)} / {String(visibleRuntimeQaDryRun.task_dispatched === true)}</p>
        <p>external_calls_triggered / tushare_called / deepseek_called / github_called: {String(visibleRuntimeQaDryRun.external_calls_triggered === true)} / {String(visibleRuntimeQaDryRun.tushare_called === true)} / {String(visibleRuntimeQaDryRun.deepseek_called === true)} / {String(visibleRuntimeQaDryRun.github_called === true)}</p>
        <p>not_allowed_next_steps: {Array.isArray(visibleRuntimeQaDryRun.not_allowed_next_steps) ? visibleRuntimeQaDryRun.not_allowed_next_steps.join(" / ") : "start Celery from runtime QA dry-run / ping Redis from runtime QA dry-run / mark_production_worker_complete_from_runtime_qa_dry_run"}</p>
        <p>该 dry-run 只审查 request ticket 与 runtime recipe；不会创建或执行 runtime QA task，不能当作 production worker complete。</p>
        <DataLineageTable rows={rows(productionReadiness.worker_runtime_qa_dry_run_rows ?? cache.worker_runtime_qa_dry_run_rows ?? visibleRuntimeQaDryRun.rows ?? workerRuntimeQaDryRunRows)} />
        <DataLineageTable rows={rows(productionReadiness.worker_runtime_qa_dry_run_phase_rows ?? cache.worker_runtime_qa_dry_run_phase_rows ?? visibleRuntimeQaDryRun.phase_rows ?? workerRuntimeQaDryRunPhaseRows)} />
      </PacketCard>

      <PacketCard title="Worker runtime QA execution" subtitle="POST /api/worker/runtime-qa-execution：本地 fallback round-trip，不启动 Celery/Redis" status={String(visibleRuntimeQaExecution.status ?? "worker_runtime_qa_execution_missing")}>
        <div className="actions">
          <button
            onClick={launchRuntimeQaExecution}
            disabled={
              runtimeQaExecutionRunning ||
              runtimeQaDryRunRunning ||
              runtimeQaExecutionRequestRunning ||
              productionEvidencePlanRunning ||
              activationReviewRunning ||
              healthcheckRunning ||
              !visibleRuntimeQaDryRun.dry_run_task_id ||
              !visibleRuntimeQaDryRun.production_evidence_plan_scope_hash ||
              !visibleRuntimeQaDryRun.runtime_qa_scope_hash
            }
          >
            {runtimeQaExecutionRunning ? "执行中" : "运行 runtime QA execution"}
          </button>
        </div>
        {runtimeQaExecutionError ? <p className="risk-note">runtime_qa_execution_error: {runtimeQaExecutionError}</p> : null}
        <p>schema_version: {String(visibleRuntimeQaExecution.schema_version ?? "worker_runtime_qa_execution_receipt.v1")}</p>
        <p>scope: {String(visibleRuntimeQaExecution.scope ?? "button_gated_worker_runtime_qa_execution_local_fallback_no_process_start")}</p>
        <p>explicit_runtime_qa_execution_done / operator_approved: {String(visibleRuntimeQaExecution.explicit_runtime_qa_execution_done === true)} / {String(visibleRuntimeQaExecution.operator_approved === true)}</p>
        <p>local_runtime_qa_execution_done / runtime_qa_done: {String(visibleRuntimeQaExecution.local_runtime_qa_execution_done === true)} / {String(visibleRuntimeQaExecution.runtime_qa_done === true)}</p>
        <p>local_fallback_round_trip / task_log_round_trip: {String(visibleRuntimeQaExecution.local_fallback_round_trip_verified === true)} / {String(visibleRuntimeQaExecution.task_log_round_trip_verified === true)}</p>
        <p>task_control_metadata / cross_process_probe / append_only_log: {String(visibleRuntimeQaExecution.local_task_control_metadata_verified === true)} / {String(visibleRuntimeQaExecution.cross_process_task_control_verified === true)} / {String(visibleRuntimeQaExecution.append_only_worker_log_verified === true)}</p>
        <p>scheduler_default_off / provider_model_no_autoschedule: {String(visibleRuntimeQaExecution.scheduler_default_off_runtime_verified === true)} / {String(visibleRuntimeQaExecution.provider_model_no_autoschedule_boundary_verified === true)}</p>
        <p>dry_run_task_id: {String(visibleRuntimeQaExecution.runtime_qa_dry_run_task_id ?? visibleRuntimeQaDryRun.dry_run_task_id ?? "")}</p>
        <p>evidence_plan_scope_hash_short / runtime_qa_scope_hash_short: {String(visibleRuntimeQaExecution.production_evidence_plan_scope_hash_short ?? "")} / {String(visibleRuntimeQaExecution.runtime_qa_scope_hash_short ?? "")}</p>
        <p>production_blocker_count: {String(visibleRuntimeQaExecution.production_blocker_count ?? 0)}；production_blockers: {Array.isArray(visibleRuntimeQaExecution.production_blockers) ? visibleRuntimeQaExecution.production_blockers.join(" / ") : ""}</p>
        <p>worker_started / redis_pinged / scheduler_started / task_dispatched: {String(visibleRuntimeQaExecution.worker_started === true)} / {String(visibleRuntimeQaExecution.redis_pinged === true)} / {String(visibleRuntimeQaExecution.scheduler_started === true)} / {String(visibleRuntimeQaExecution.task_dispatched === true)}</p>
        <p>external_calls_triggered / tushare_called / deepseek_called / github_called: {String(visibleRuntimeQaExecution.external_calls_triggered === true)} / {String(visibleRuntimeQaExecution.tushare_called === true)} / {String(visibleRuntimeQaExecution.deepseek_called === true)} / {String(visibleRuntimeQaExecution.github_called === true)}</p>
        <p>does_not_execute_trades / does_not_modify_strategy_action / contains_secret: {String(visibleRuntimeQaExecution.does_not_execute_trades === true)} / {String(visibleRuntimeQaExecution.does_not_modify_strategy_action === true)} / {String(visibleRuntimeQaExecution.contains_secret === true)}</p>
        <p>该 execution 只证明本地 fallback、task readback、append-only JSONL 和本地 Python process probe；不能当作 Celery/Redis process proof、live queue proof 或 production worker complete。</p>
        <DataLineageTable rows={rows(productionReadiness.worker_runtime_qa_execution_rows ?? cache.worker_runtime_qa_execution_rows ?? visibleRuntimeQaExecution.rows ?? workerRuntimeQaExecutionEvidenceRows)} />
        <DataLineageTable rows={rows(productionReadiness.worker_runtime_qa_execution_phase_rows ?? cache.worker_runtime_qa_execution_phase_rows ?? visibleRuntimeQaExecution.phase_rows ?? workerRuntimeQaExecutionPhaseRows)} />
        <DataLineageTable rows={rows(visibleRuntimeQaExecution.call_ledger ?? runtimeQaExecutionResult.call_ledger)} />
      </PacketCard>

      <PacketCard title="Worker runtime QA execution recipe" subtitle="LTG-06 runtime QA 执行顺序 recipe；只读、不启动 Celery、不 ping Redis、不派发任务" status={String(workerRuntimeQaExecutionRecipe.status ?? "missing")}>
        <p>schema_version: {String(workerRuntimeQaExecutionRecipe.schema_version ?? "worker_runtime_qa_execution_recipe.v1")}</p>
        <p>scope: {String(workerRuntimeQaExecutionRecipe.scope ?? "local_worker_runtime_qa_execution_recipe_no_process_start")}</p>
        <p>runtime_qa_scope_hash_short: {String(workerRuntimeQaExecutionRecipe.runtime_qa_scope_hash_short ?? "")}</p>
        <p>local_recipe_ready / runtime_qa_done: {String(workerRuntimeQaExecutionRecipe.local_recipe_ready ?? false)} / {String(workerRuntimeQaExecutionRecipe.runtime_qa_done ?? false)}</p>
        <p>production_worker_complete: {String(workerRuntimeQaExecutionRecipe.production_worker_complete ?? false)}</p>
        <p>worker_started / redis_pinged / scheduler_started / task_dispatched: {String(workerRuntimeQaExecutionRecipe.worker_started ?? false)} / {String(workerRuntimeQaExecutionRecipe.redis_pinged ?? false)} / {String(workerRuntimeQaExecutionRecipe.scheduler_started ?? false)} / {String(workerRuntimeQaExecutionRecipe.task_dispatched ?? false)}</p>
        <p>provider_model_task_dispatched / healthcheck_executed: {String(workerRuntimeQaExecutionRecipe.provider_model_task_dispatched ?? false)} / {String(workerRuntimeQaExecutionRecipe.healthcheck_executed ?? false)}</p>
        <p>tushare / deepseek / github: {String(workerRuntimeQaExecutionRecipe.tushare_called ?? false)} / {String(workerRuntimeQaExecutionRecipe.deepseek_called ?? false)} / {String(workerRuntimeQaExecutionRecipe.github_called ?? false)}</p>
        <p>not_allowed_next_steps: {Array.isArray(workerRuntimeQaExecutionRecipe.not_allowed_next_steps) ? workerRuntimeQaExecutionRecipe.not_allowed_next_steps.join(" / ") : "treat_recipe_as_runtime_qa_evidence / start Celery from GET cache / mark_production_worker_complete_from_scope_ticket"}</p>
        <DataLineageTable rows={workerRuntimeQaExecutionRows} />
      </PacketCard>

      <PacketCard title="Worker runtime durable evidence recipe" subtitle="LTG-06 durable evidence 缺口清单；本地只读、不启动进程、不调用 provider" status={String(workerRuntimeDurableEvidenceRecipe.status ?? "missing")}>
        <p>schema_version: {String(workerRuntimeDurableEvidenceRecipe.schema_version ?? "worker_runtime_durable_evidence_recipe.v1")}</p>
        <p>scope: {String(workerRuntimeDurableEvidenceRecipe.scope ?? "local_worker_runtime_durable_evidence_recipe_no_process_start_no_dispatch")}</p>
        <p>local_recipe_ready / durable_evidence_complete: {String(workerRuntimeDurableEvidenceRecipe.local_recipe_ready ?? false)} / {String(workerRuntimeDurableEvidenceRecipe.durable_evidence_complete ?? false)}</p>
        <p>durable_promotion_ready / production_worker_complete: {String(workerRuntimeDurableEvidenceRecipe.durable_promotion_ready ?? false)} / {String(workerRuntimeDurableEvidenceRecipe.production_worker_complete ?? false)}</p>
        <p>missing_durable_evidence: {Array.isArray(workerRuntimeDurableEvidenceRecipe.missing_durable_evidence) ? workerRuntimeDurableEvidenceRecipe.missing_durable_evidence.join(" / ") : ""}</p>
        <p>worker_started / redis_pinged / scheduler_started / task_dispatched: {String(workerRuntimeDurableEvidenceRecipe.worker_started ?? false)} / {String(workerRuntimeDurableEvidenceRecipe.redis_pinged ?? false)} / {String(workerRuntimeDurableEvidenceRecipe.scheduler_started ?? false)} / {String(workerRuntimeDurableEvidenceRecipe.task_dispatched ?? false)}</p>
        <p>provider_model_task_dispatched / healthcheck_executed: {String(workerRuntimeDurableEvidenceRecipe.provider_model_task_dispatched ?? false)} / {String(workerRuntimeDurableEvidenceRecipe.healthcheck_executed ?? false)}</p>
        <p>tushare / deepseek / github: {String(workerRuntimeDurableEvidenceRecipe.tushare_called ?? false)} / {String(workerRuntimeDurableEvidenceRecipe.deepseek_called ?? false)} / {String(workerRuntimeDurableEvidenceRecipe.github_called ?? false)}</p>
        <p>not_allowed_next_steps: {Array.isArray(workerRuntimeDurableEvidenceRecipe.not_allowed_next_steps) ? workerRuntimeDurableEvidenceRecipe.not_allowed_next_steps.join(" / ") : "treat_durable_recipe_as_runtime_qa_execution / start Celery from durable recipe / mark_production_worker_complete_from_durable_recipe"}</p>
        <DataLineageTable rows={workerRuntimeDurableEvidenceRows} />
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
        <JsonDetails title="worker activation review task raw" data={visibleActivationReview} />
        <JsonDetails title="worker production evidence plan raw" data={visibleProductionEvidencePlan} />
        <JsonDetails title="worker runtime QA execution request raw" data={visibleRuntimeQaExecutionRequest} />
        <JsonDetails title="worker runtime QA dry-run raw" data={visibleRuntimeQaDryRun} />
      </PacketCard>
    </>
  );
}
