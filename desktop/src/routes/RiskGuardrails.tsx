import { useEffect, useState } from "react";
import { getRiskGuardrailsCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function objectRow(value: unknown): Array<Record<string, unknown>> {
  return value && typeof value === "object" && !Array.isArray(value) ? [value as Record<string, unknown>] : [];
}

export default function RiskGuardrails() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);

  useEffect(() => {
    void getRiskGuardrailsCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const execution = (cache.execution_guardrail_overview as Record<string, unknown> | undefined) ?? {};
  const legacy = (cache.legacy_decision_chain_summary as Record<string, unknown> | undefined) ?? {};
  const recovery = (cache.strategy_prerequisite_recovery_ledger as Record<string, unknown> | undefined) ?? {};
  const budget = (cache.position_risk_budget as Record<string, unknown> | undefined) ?? {};
  const tradeIsolationAudit = (cache.trade_isolation_audit as Record<string, unknown> | undefined) ?? {};
  const tradeIsolationReleaseReceipt = (cache.trade_isolation_release_receipt as Record<string, unknown> | undefined) ?? {};
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);
  const warningRows = cacheWarnings.map((warning, index) => ({ index: index + 1, warning }));

  return (
    <>
      <div className="page-head">
        <h1>风险护栏</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "数据缺口", value: counts.data_gap_count as number | undefined },
          { label: "硬风险", value: counts.hard_risk_alert_count as number | undefined },
          { label: "禁止事项", value: counts.must_not_do_count as number | undefined },
          { label: "降风险条件", value: counts.reduce_condition_count as number | undefined },
          { label: "执行阻断", value: counts.execution_blocked_count as number | undefined },
          { label: "旧链阻断", value: counts.legacy_blocked_count as number | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "修改持仓", value: cache.does_not_modify_holdings === false ? "可能" : "不会", tone: cache.does_not_modify_holdings === false ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" },
          { label: "交易隔离审计", value: tradeIsolationAudit.status as string | undefined, tone: tradeIsolationAudit.status === "trade_isolation_ready" ? "good" : "warn" },
          { label: "交易隔离阻断", value: counts.trade_isolation_blocker_count as number | undefined, tone: Number(counts.trade_isolation_blocker_count ?? 0) > 0 ? "bad" : "good" },
          { label: "release receipt", value: tradeIsolationReleaseReceipt.local_receipt_ready === true ? "research only" : "review", tone: tradeIsolationReleaseReceipt.local_receipt_ready === true ? "good" : "warn" },
          { label: "release blockers", value: tradeIsolationReleaseReceipt.blocking_criterion_count ?? counts.trade_isolation_release_receipt_blocker_count, tone: Number(tradeIsolationReleaseReceipt.blocking_criterion_count ?? counts.trade_isolation_release_receipt_blocker_count ?? 0) > 0 ? "bad" : "good" },
          { label: "POST 边界行", value: counts.task_trade_boundary_row_count as number | undefined },
          { label: "边界页面", value: counts.trade_boundary_frontend_surface_count as number | undefined },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="风险护栏来源" subtitle="GET /api/risk/cache 只读读取 risk_alerts / execution_guardrail_overview" status={String(cache.status ?? "missing")}>
          <p>{String(cache.summary ?? "风险护栏 cache 只读展示。")}</p>
          <p>本页不会调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不自动下单，不修改 strategy action。</p>
          <p>风险护栏不是交易指令；它只集中展示本地缓存里的“不能做什么”和“需要先核验什么”。</p>
        </PacketCard>

        <PacketCard title="安全线" subtitle="safety_line cache；不刷新价格、不改仓位" status="cache">
          <p>{String(cache.safety_line ?? "未发现安全线缓存")}</p>
          <p>不清除风险标记；风险缺失不能写成无风险。</p>
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="禁止事项" subtitle="risk_alerts.must_not_do；只读纪律边界" status="must_not_do">
          <DataLineageTable rows={rows(cache.must_not_do_rows)} />
        </PacketCard>
        <PacketCard title="减仓/降风险条件" subtitle="risk_alerts.reduce_conditions；条件触发，不是立即卖出" status="reduce">
          <DataLineageTable rows={rows(cache.reduce_condition_rows)} />
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="数据缺口" subtitle="risk_alerts.data_gaps；缺失数据只进入风险提示" status="gaps">
          <DataLineageTable rows={rows(cache.data_gap_rows)} />
        </PacketCard>
        <PacketCard title="硬风险提示" subtitle="risk_alerts.hard_risk_alerts；不自动下单" status="hard_risk">
          <DataLineageTable rows={rows(cache.hard_risk_rows)} />
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="执行护栏" subtitle="execution_guardrail_overview；不修改 strategy action" status={String(execution.tone ?? execution.status ?? "cache")}>
          <p>headline: {String(execution.headline ?? "--")}</p>
          <p>safe mode: {String(execution.safe_mode_text ?? "--")}</p>
          <p>next action: {String(execution.next_action ?? "--")}</p>
          <DataLineageTable rows={objectRow(execution)} />
        </PacketCard>
        <PacketCard title="旧能力链" subtitle="legacy_decision_chain_summary；只读旧链状态" status={String(legacy.status ?? "cache")}>
          <p>headline: {String(legacy.headline ?? "--")}</p>
          <p>blocked / waiting: {String(legacy.blocked_count ?? 0)} / {String(legacy.waiting_count ?? 0)}</p>
          <DataLineageTable rows={rows(legacy.items)} />
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="策略前置恢复" subtitle="strategy_prerequisite_recovery_ledger；只展示恢复路线" status={String(recovery.status ?? "cache")}>
          <p>headline: {String(recovery.headline ?? "--")}</p>
          <p>next action: {String(recovery.next_action ?? "--")}</p>
          <DataLineageTable rows={rows(recovery.items)} />
        </PacketCard>
        <PacketCard title="风险预算" subtitle="position_risk_budget；不改持仓或 action" status={String(budget.status ?? budget.risk_level ?? "cache")}>
          <DataLineageTable rows={objectRow(budget)} />
        </PacketCard>
      </div>

      <PacketCard title="风险拆解" subtitle="risk_breakdown；只读风险来源" status="risk_breakdown">
        <DataLineageTable rows={rows(cache.risk_rows)} />
      </PacketCard>

      <PacketCard title="API / 任务边界" subtitle="cache API 永不外联；刷新必须走后续按钮任务" status="policy">
        <p>不会调用 Tushare、DeepSeek 或 GitHub；不执行真实交易；不自动下单；不修改 strategy action；不清除风险标记。</p>
        <p>local_risk_guardrails_cache 只读取 risk_alerts、execution_guardrail_overview、legacy_decision_chain_summary 等本地字段。</p>
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <PacketCard title="交易隔离审计" subtitle="trade_isolation_audit：本地 task catalog + 前端边界合同，不接入券商或订单接口" status={String(tradeIsolationAudit.status ?? "missing")}>
        <p>schema_version: {String(tradeIsolationAudit.schema_version ?? "--")}</p>
        <p>scope: {String(tradeIsolationAudit.scope ?? "command_center_3_cache_task_frontend_contract")}</p>
        <p>known_post_route_count: {String(tradeIsolationAudit.known_post_route_count ?? 0)}</p>
        <p>no_automatic_order_path_in_task_catalog: {String(tradeIsolationAudit.no_automatic_order_path_in_task_catalog ?? false)}</p>
        <p>research_paths_cannot_mutate_strategy_action: {String(tradeIsolationAudit.research_paths_cannot_mutate_strategy_action ?? false)}</p>
        <p>future_trade_integration_out_of_roadmap: {String(tradeIsolationAudit.future_trade_integration_out_of_roadmap ?? true)}</p>
      </PacketCard>

      <PacketCard title="交易隔离检查项" subtitle="trade_isolation_rows；任务目录、POST 路由、前端边界和未来交易隔离要求" status="trade_isolation_rows">
        <DataLineageTable rows={rows(cache.trade_isolation_rows)} />
      </PacketCard>

      <PacketCard title="交易隔离边界行" subtitle="trade_isolation_boundary_rows；task/lifecycle routes 与前端页面边界清单" status="trade_isolation_boundary_rows">
        <DataLineageTable rows={rows(cache.trade_isolation_boundary_rows)} />
      </PacketCard>

      <PacketCard title="交易隔离 release receipt" subtitle="LTG-12 研究客户端发布收据；不批准真实交易、不接入券商、不创建订单接口" status={String(tradeIsolationReleaseReceipt.status ?? "trade_isolation_release_receipt_ready_research_release_only")}>
        <p>schema_version: {String(tradeIsolationReleaseReceipt.schema_version ?? "command_center_3_trade_isolation_release_receipt.v1")}</p>
        <p>scope: {String(tradeIsolationReleaseReceipt.scope ?? "local_trade_isolation_release_receipt_no_broker_or_order_execution")}</p>
        <p>research_client_release_safe / ready_for_real_trading_integration: {String(tradeIsolationReleaseReceipt.research_client_release_safe ?? true)} / {String(tradeIsolationReleaseReceipt.ready_for_real_trading_integration ?? false)}</p>
        <p>real_trading_connected / broker_adapter_connected / order_endpoint_present / trade_execution_api_enabled: {String(tradeIsolationReleaseReceipt.real_trading_connected ?? false)} / {String(tradeIsolationReleaseReceipt.broker_adapter_connected ?? false)} / {String(tradeIsolationReleaseReceipt.order_endpoint_present ?? false)} / {String(tradeIsolationReleaseReceipt.trade_execution_api_enabled ?? false)}</p>
        <p>future_real_trading_requires_separate_project: {String(tradeIsolationReleaseReceipt.future_real_trading_requires_separate_project ?? true)}</p>
        <p>allowed_next_step: {String(tradeIsolationReleaseReceipt.allowed_next_step ?? "continue_research_client_release_or_create_separate_real_trading_project_design")}</p>
        <p>not_allowed_next_steps: {Array.isArray(tradeIsolationReleaseReceipt.not_allowed_next_steps) ? tradeIsolationReleaseReceipt.not_allowed_next_steps.join(" / ") : "connect broker adapter inside Command Center 3 migration / add order endpoint to cache/task API / let model or factor output become orders / treat release receipt as real-trading approval"}</p>
        <p>missing_evidence_items_for_real_trading_project: {Array.isArray(tradeIsolationReleaseReceipt.missing_evidence_items_for_real_trading_project) ? tradeIsolationReleaseReceipt.missing_evidence_items_for_real_trading_project.join(" / ") : "separate_project_approval / broker_adapter_design / sandbox_order_execution_tests / risk_limits_and_kill_switch"}</p>
        <DataLineageTable rows={rows(cache.trade_isolation_release_receipt_rows)} />
        <DataLineageTable rows={rows(tradeIsolationReleaseReceipt.call_ledger)} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="local_risk_guardrails_cache；不外联、不写回" status="lineage">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET risk envelope call_ledger" subtitle="GET /api/risk/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheCallLedger} />
      </PacketCard>

      <PacketCard title="GET risk envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={warningRows} />
      </PacketCard>

      <PacketCard title="原始 risk guardrails cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="risk guardrails cache raw" data={cache} />
        <JsonDetails title="trade isolation release receipt raw" data={tradeIsolationReleaseReceipt} />
      </PacketCard>
    </>
  );
}
