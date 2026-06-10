import { useEffect, useState } from "react";
import { getDataHealthCache } from "../api/client";
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

export default function DataHealthTimeline() {
  const [cache, setCache] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getDataHealthCache().then((res) => setCache(res.data));
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const visibility = (cache.data_health_visibility_summary as Record<string, unknown> | undefined) ?? {};
  const providerCockpit = (cache.provider_data_capability_cockpit as Record<string, unknown> | undefined) ?? {};
  const callLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <>
      <div className="page-head">
        <h1>数据健康</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "健康时间线", value: counts.timeline_count as number | undefined },
          { label: "Provider", value: counts.provider_count as number | undefined },
          { label: "能力矩阵", value: counts.capability_count as number | undefined },
          { label: "恢复动作", value: counts.recovery_action_count as number | undefined },
          { label: "数据缺口", value: counts.gap_count as number | undefined },
          { label: "健康账本", value: counts.ledger_count as number | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "provider ping", value: policy.post_task_required_for_provider_probe === true ? "需任务" : "可能直接", tone: policy.post_task_required_for_provider_probe === true ? "good" : "bad" },
          { label: "刷新数据", value: policy.does_not_refresh_data === true ? "不会" : "可能", tone: policy.does_not_refresh_data === true ? "good" : "bad" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" }
        ]}
      />

      <div className="grid">
        <PacketCard title="数据健康来源" subtitle="GET /api/data-health/cache 只读读取 data_health_timeline / provider_data_capability_cockpit" status={String(cache.status ?? "missing")}>
          <p>{String(cache.summary ?? "数据健康时间线 cache 只读展示。")}</p>
          <p>不会 ping Tushare、AkShare、yfinance、Supabase；不会刷新数据。</p>
          <p>不调用 DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。</p>
        </PacketCard>

        <PacketCard title="可见性摘要" subtitle="data_health_visibility_summary；只做诊断说明" status={String(visibility.status ?? "visibility")}>
          <p>headline: {String(visibility.headline ?? visibility.summary ?? "--")}</p>
          <DataLineageTable rows={objectRow(visibility)} />
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="Provider 诊断" subtitle="provider_data_capability_cockpit；不 ping provider" status={String(providerCockpit.status ?? "provider")}>
          <DataLineageTable rows={rows(cache.provider_rows)} />
        </PacketCard>
        <PacketCard title="能力矩阵" subtitle="a_share_capability_matrix；只读能力状态" status="capability">
          <DataLineageTable rows={rows(cache.capability_rows)} />
        </PacketCard>
      </div>

      <PacketCard title="健康时间线" subtitle="data_health_timeline / data_freshness / data_coverage；不会重新探测接口" status="timeline">
        <DataLineageTable rows={rows(cache.timeline_rows)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="恢复动作" subtitle="data_health_timeline_recovery_actions；只读建议，不执行恢复" status="recovery_actions">
          <DataLineageTable rows={rows(cache.recovery_action_rows)} />
        </PacketCard>
        <PacketCard title="数据缺口" subtitle="data_gap_report / home_data_issue_brief / data_issue_explainer；缺口不是无风险" status="gaps">
          <DataLineageTable rows={rows(cache.gap_rows)} />
        </PacketCard>
      </div>

      <PacketCard title="健康账本" subtitle="data_health_ledger；只读历史健康记录" status="ledger">
        <DataLineageTable rows={rows(cache.ledger_rows)} />
      </PacketCard>

      <PacketCard title="API / 任务边界" subtitle="cache API 永不外联；Provider probe 必须走后续 POST task" status="policy">
        <p>GET /api/data-health/cache 只读取本地 data_health_timeline、provider_data_capability_cockpit、a_share_capability_matrix 和 data_health_ledger。</p>
        <p>不会 ping Tushare、AkShare、yfinance、Supabase；不调用 DeepSeek 或 GitHub；不会刷新数据；不修改 strategy action。</p>
        <p>local_data_health_timeline_cache 只读本地 snapshot，不运行恢复动作或回测。</p>
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="local_data_health_timeline_cache；不外联、不写回" status="lineage">
        <DataLineageTable rows={callLedger} />
      </PacketCard>

      <PacketCard title="原始 data health cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="data health cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
