import { useEffect, useState } from "react";
import { getDataCapabilityCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function DataCapabilityConsole() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);

  useEffect(() => {
    void getDataCapabilityCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const dashboard = (cache.dashboard as Record<string, unknown> | undefined) ?? {};
  const consolePacket = (cache.console as Record<string, unknown> | undefined) ?? {};
  const healthLedger = (cache.data_health_ledger as Record<string, unknown> | undefined) ?? {};
  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const providerCards = (cache.provider_cards as Array<Record<string, unknown>> | undefined) ?? [];
  const recoveryActions = (cache.recovery_actions as Array<Record<string, unknown>> | undefined) ?? [];
  const healthRows = (healthLedger.rows as Array<Record<string, unknown>> | undefined) ?? [];
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);

  const providerRows = providerCards.map((card) => ({
    provider: card.provider,
    tone: card.tone,
    summary: card.summary,
    available_count: card.available_count,
    restricted_count: card.restricted_count,
    pending_count: card.pending_count
  }));

  const actionRows = recoveryActions.map((action) => ({
    provider: action.provider,
    label: action.label,
    api: action.api,
    state: action.state,
    action_label: action.action_label,
    writes_packet: action.writes_packet,
    toolbox_entry: action.toolbox_entry
  }));

  return (
    <>
      <div className="page-head">
        <h1>数据能力</h1>
        <StatusBadge label={String(cache.status ?? "missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "available", value: counts.available as number | undefined },
          { label: "restricted", value: counts.restricted as number | undefined },
          { label: "pending", value: counts.pending as number | undefined },
          { label: "blocked", value: counts.blocked as number | undefined },
          { label: "manual", value: counts.manual as number | undefined },
          { label: "stale", value: counts.stale as number | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheEnvelopeLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="数据能力 cache" subtitle="GET /api/data-capability/cache 只读展示本地检测结果" status="cache_only">
          <p>{String(dashboard.summary ?? consolePacket.headline ?? "尚未检测数据能力；页面打开不会自动请求外部接口。")}</p>
          <p>{String(consolePacket.safe_mode_text ?? "只允许读取本地缓存；刷新必须通过按钮门控任务。")}</p>
          <p>cache API 永不外联：不 ping Tushare、AkShare、yfinance、Supabase，不调用 DeepSeek 或 GitHub。</p>
        </PacketCard>

        <PacketCard title="决策边界" subtitle="数据能力只影响证据置信度和手动恢复建议" status={String(consolePacket.decision_readiness ?? "missing")}>
          <p>readiness: {String(consolePacket.decision_readiness_label ?? "--")}</p>
          <p>short_answer: {String(consolePacket.short_answer ?? "--")}</p>
          <p>strategy action: {cache.does_not_modify_strategy_action === false ? "可能被修改" : "不会被修改"}</p>
        </PacketCard>
      </div>

      <PacketCard title="Provider 状态" subtitle="Tushare / AkShare / yfinance / Supabase 本地检测摘要" status="providers">
        <DataLineageTable rows={providerRows} />
      </PacketCard>

      <PacketCard title="接口级健康账本" subtitle="只读 rows；不会尝试恢复或探测接口" status={String(healthLedger.status ?? "missing")}>
        <DataLineageTable rows={healthRows} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="手动恢复建议" subtitle="这里只展示建议；不触发刷新任务" status="manual_actions">
          <DataLineageTable rows={actionRows} />
        </PacketCard>

        <PacketCard title="API 边界" subtitle="GET cache 永不外联，POST task 才可能刷新" status="policy">
          <DataLineageTable rows={[policy]} />
        </PacketCard>
      </div>

      <PacketCard title="调用血缘" subtitle="payload 内部 local_data_capability_cache；不 ping 外部接口" status="call_ledger">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET data capability envelope call_ledger" subtitle="GET /api/data-capability/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheEnvelopeLedger} />
      </PacketCard>

      <PacketCard title="GET data capability envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={cacheWarnings.map((warning, index) => ({ index: index + 1, warning }))} />
      </PacketCard>

      <PacketCard title="原始 data capability cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="data capability cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
