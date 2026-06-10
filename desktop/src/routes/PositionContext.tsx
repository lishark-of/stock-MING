import { useEffect, useState } from "react";
import { getPositionCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

function objectRows(value: unknown): Array<Record<string, unknown>> {
  return value && typeof value === "object" && !Array.isArray(value) ? [value as Record<string, unknown>] : [];
}

export default function PositionContext() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);

  useEffect(() => {
    void getPositionCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const summary = (cache.position_summary as Record<string, unknown> | undefined) ?? {};
  const holdingAction = (cache.holding_action as Record<string, unknown> | undefined) ?? {};
  const riskBudget = (cache.position_risk_budget as Record<string, unknown> | undefined) ?? {};
  const riskBreakdown = (cache.risk_breakdown as Record<string, unknown> | undefined) ?? {};
  const safetyLine = (cache.safety_line as Record<string, unknown> | undefined) ?? {};
  const todayAction = (cache.today_action as Record<string, unknown> | undefined) ?? {};
  const strategyContext = (cache.strategy_context as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);
  const warningRows = cacheWarnings.map((warning, index) => ({ index: index + 1, warning }));

  return (
    <>
      <div className="page-head">
        <h1>持仓画像</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "ticker", value: summary.ticker as string | undefined },
          { label: "shares", value: summary.shares as string | number | undefined },
          { label: "cost", value: summary.cost as string | number | undefined },
          { label: "current", value: summary.current_price as string | number | undefined },
          { label: "action state", value: summary.cached_action_state as string | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "修改持仓", value: cache.does_not_modify_holdings === false ? "可能" : "不会", tone: cache.does_not_modify_holdings === false ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="持仓画像来源" subtitle="GET /api/position/cache 只读读取 command_center_latest snapshot" status={String(cache.status ?? "missing")}>
          <p>本页只展示已有 holding_action / position_risk_budget / risk_breakdown 缓存，不计算交易动作。</p>
          <p>不会调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不自动下单，不修改持仓或 strategy action。</p>
          <p>floating_pnl: {String(summary.floating_pnl_text ?? summary.floating_pnl ?? "--")}</p>
        </PacketCard>

        <PacketCard title="今日动作上下文" subtitle="来自缓存 today_action / strategy_packet；前端不改写" status={String(todayAction.status ?? strategyContext.status ?? "cache")}>
          <p>today_action: {String(todayAction.overall_action ?? todayAction.action ?? "--")}</p>
          <p>strategy_action: {String(strategyContext.action ?? "--")}</p>
          <p>strategy_confidence: {String(strategyContext.confidence ?? "--")}</p>
        </PacketCard>
      </div>

      <PacketCard title="持仓字段" subtitle="脱敏只读 holding_action；不刷新价格" status="cache">
        <DataLineageTable rows={objectRows(holdingAction)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="风险预算" subtitle="来自 position_risk_budget cache" status="risk">
          <DataLineageTable rows={objectRows(riskBudget)} />
        </PacketCard>
        <PacketCard title="风险拆解" subtitle="来自 risk_breakdown cache" status="risk">
          <DataLineageTable rows={objectRows(riskBreakdown)} />
        </PacketCard>
      </div>

      <PacketCard title="安全线" subtitle="来自 safety_line cache；前端不计算止盈止损" status="guarded">
        <DataLineageTable rows={objectRows(safetyLine)} />
      </PacketCard>

      <PacketCard title="API / 任务边界" subtitle="cache API 永不外联；缺失时只显示缺口" status="policy">
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="local_position_context_cache；不外联、不写回" status="lineage">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET position envelope call_ledger" subtitle="GET /api/position/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheCallLedger} />
      </PacketCard>

      <PacketCard title="GET position envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={warningRows} />
      </PacketCard>

      <PacketCard title="原始 position context cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="position context cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
