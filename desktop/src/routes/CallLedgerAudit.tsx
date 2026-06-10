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
  const parameterizedRoutes = rows(getRouteCoverage.parameterized_local_routes);
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const callLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<unknown> | undefined) ?? []);

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
          { label: "call ledger", value: counts.call_ledger_count as number | undefined },
          { label: "endpoint ledger", value: counts.endpoint_call_ledger_count as number | undefined },
          { label: "task ledger", value: counts.task_call_ledger_count as number | undefined },
          { label: "external calls", value: counts.external_call_count as number | undefined, tone: Number(counts.external_call_count ?? 0) > 0 ? "bad" : "good" },
          { label: "action risk", value: counts.action_risk_count as number | undefined, tone: Number(counts.action_risk_count ?? 0) > 0 ? "bad" : "good" },
          { label: "missing ledger", value: counts.missing_call_ledger_count as number | undefined, tone: Number(counts.missing_call_ledger_count ?? 0) > 0 ? "warn" : "good" },
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
        <DataLineageTable rows={rows(cache.task_rows)} />
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
