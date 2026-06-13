import { useEffect, useState } from "react";
import { getAuditCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

export default function CallLedgerAudit() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<unknown>>([]);

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
  const motionClarityAudit = (cache.motion_clarity_audit as Record<string, unknown> | undefined) ?? {};
  const motionClarityRows = rows(cache.motion_clarity_rows);
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
          { label: "motion clarity", value: motionClarityAudit.status as string | undefined, tone: motionClarityAudit.static_ready === true ? "good" : "warn" },
          { label: "motion blockers", value: counts.motion_clarity_blocker_count as number | undefined, tone: Number(counts.motion_clarity_blocker_count ?? 0) > 0 ? "bad" : "good" },
          { label: "motion visual QA", value: motionClarityAudit.visual_qa_complete === true ? "完成" : "待验收", tone: motionClarityAudit.visual_qa_complete === true ? "good" : "warn" },
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
