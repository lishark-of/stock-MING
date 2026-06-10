import { useEffect, useState } from "react";
import { getEvidenceCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function AShareEvidenceRadar() {
  const [cache, setCache] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getEvidenceCache().then((res) => setCache(res.data));
  }, []);

  const radar = (cache.evidence_radar as Record<string, unknown> | undefined) ?? {};
  const lineage = (cache.fact_lineage as Record<string, unknown> | undefined) ?? {};
  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const recoverySummary = (cache.recovery_summary as Record<string, unknown> | undefined) ?? {};
  const radarItems = (radar.items as Array<Record<string, unknown>> | undefined) ?? [];
  const lineageItems = (lineage.items as Array<Record<string, unknown>> | undefined) ?? [];
  const nextActions = (radar.next_evidence_actions as Array<Record<string, unknown>> | undefined) ?? [];
  const callLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];

  const radarRows = radarItems.map((item) => ({
    key: item.key,
    label: item.label,
    status_label: item.status_label,
    evidence_state: item.evidence_state,
    evidence_label: item.evidence_label,
    decision_role: item.decision_role,
    writes_packet: (item.manual_action as Record<string, unknown> | undefined)?.writes_packet
  }));

  const lineageRows = lineageItems.map((item) => ({
    fact_key: item.fact_key,
    fact_name: item.fact_name,
    status_label: item.status_label,
    data_date: item.data_date,
    local_fetched_at: item.local_fetched_at,
    source_packet: item.source_packet,
    enters_core_action: item.enters_core_action,
    enters_projection: item.enters_projection
  }));

  const actionRows = nextActions.map((item) => ({
    key: item.key,
    label: item.label,
    evidence_state: item.evidence_state,
    action_label: item.action_label,
    refresh_policy: item.refresh_policy,
    writes_packet: item.writes_packet
  }));

  return (
    <>
      <div className="page-head">
        <h1>A 股证据雷达</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "ready", value: counts.ready as number | undefined },
          { label: "cached", value: counts.cached as number | undefined },
          { label: "failed", value: counts.failed as number | undefined },
          { label: "missing", value: counts.missing as number | undefined },
          { label: "lineage verified", value: counts.lineage_verified as number | undefined },
          { label: "lineage missing", value: counts.lineage_missing as number | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" }
        ]}
      />

      <div className="grid">
        <PacketCard title="证据雷达 cache" subtitle="GET /api/evidence/cache 只读整理本地 A 股证据" status="cache_only">
          <p>{String(radar.summary ?? "A 股证据雷达暂未生成精确缓存。")}</p>
          <p>{String(radar.decision_summary ?? "支持/阻断/缓存/缺失状态仅用于证据解释。")}</p>
          <p>cache API 永不外联：不调用 Tushare、DeepSeek、GitHub，不运行回测，不执行真实交易。</p>
        </PacketCard>

        <PacketCard title="事实血缘边界" subtitle="data_date / local_fetched_at / source packet" status={String(lineage.schema_version ?? "lineage")}>
          <p>{String(lineage.summary ?? "--")}</p>
          <p>{String(lineage.boundary_note ?? "事实血缘不直接覆盖核心交易 action 或 strategy action。")}</p>
          <p>lineage_enters_core_action: {String(policy.lineage_enters_core_action ?? false)}</p>
        </PacketCard>
      </div>

      <PacketCard title="证据项" subtitle="资金流、硬风险、融资融券、情绪、龙虎榜、筹码/胜率" status="radar">
        <DataLineageTable rows={radarRows} />
      </PacketCard>

      <PacketCard title="事实血缘" subtitle="所有外部接口只作为历史来源说明；GET 不刷新" status="lineage">
        <DataLineageTable rows={lineageRows} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="手动补齐建议" subtitle="这里只展示建议；不触发按钮任务" status={String(recoverySummary.status ?? "ready")}>
          <p>{String(recoverySummary.summary ?? "--")}</p>
          <DataLineageTable rows={actionRows} />
        </PacketCard>

        <PacketCard title="API 边界" subtitle="cache API 永不外联，POST task 才可能刷新" status="policy">
          <DataLineageTable rows={[policy]} />
        </PacketCard>
      </div>

      <PacketCard title="调用血缘" subtitle="local_a_share_evidence_cache；不刷新 Tushare" status="call_ledger">
        <DataLineageTable rows={callLedger} />
      </PacketCard>

      <PacketCard title="原始 evidence cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="A share evidence cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
