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
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);

  useEffect(() => {
    void getDataHealthCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const visibility = (cache.data_health_visibility_summary as Record<string, unknown> | undefined) ?? {};
  const providerCockpit = (cache.provider_data_capability_cockpit as Record<string, unknown> | undefined) ?? {};
  const freshnessAcceptance = (cache.freshness_acceptance_summary as Record<string, unknown> | undefined) ?? {};
  const freshnessSample = (cache.freshness_long_window_sample_validation as Record<string, unknown> | undefined) ?? {};
  const tradeCalPhysical = (cache.trade_cal_physical_validation as Record<string, unknown> | undefined) ?? {};
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);

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
          { label: "freshness 场景", value: counts.freshness_acceptance_scenario_count as number | undefined },
          { label: "长窗样本", value: counts.freshness_long_window_sample_scenario_count as number | undefined },
          { label: "样本通过", value: counts.freshness_long_window_sample_passed_count as number | undefined, tone: counts.freshness_long_window_sample_failed_count === 0 ? "good" : "bad" },
          { label: "trade_cal 长窗", value: freshnessAcceptance.trade_cal_long_window_validation_done === true ? "完成" : "待验收", tone: freshnessAcceptance.trade_cal_long_window_validation_done === true ? "good" : "neutral" },
          { label: "本地 trade_cal", value: tradeCalPhysical.status as string | undefined, tone: tradeCalPhysical.local_trade_cal_physical_validation_done === true ? "good" : "warn" },
          { label: "物理验收", value: tradeCalPhysical.trade_cal_long_window_validation_done === true ? "通过" : "待验收", tone: tradeCalPhysical.trade_cal_long_window_validation_done === true ? "good" : "neutral" },
          { label: "trade_cal 行数", value: tradeCalPhysical.local_trade_cal_row_count as number | undefined },
          { label: "样本类型", value: freshnessSample.fixture_is_synthetic === true ? "fixture" : "unknown", tone: freshnessSample.fixture_is_synthetic === true ? "warn" : "neutral" },
          { label: "stale 边界", value: freshnessAcceptance.stale_expired_historical_unknown_are_research_only === true ? "research-only" : "需检查", tone: freshnessAcceptance.stale_expired_historical_unknown_are_research_only === true ? "good" : "bad" },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "provider ping", value: policy.post_task_required_for_provider_probe === true ? "需任务" : "可能直接", tone: policy.post_task_required_for_provider_probe === true ? "good" : "bad" },
          { label: "刷新数据", value: policy.does_not_refresh_data === true ? "不会" : "可能", tone: policy.does_not_refresh_data === true ? "good" : "bad" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheEnvelopeLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
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

      <PacketCard title="Freshness 验收矩阵" subtitle="LTG-01 A 股交易日历级 freshness；本地合同，不是真实 trade_cal 长窗口验收" status={String(freshnessAcceptance.status ?? "acceptance_matrix")}>
        <p>盘前、盘中、收盘集合竞价、16:30 后、周末/节假日、trade_cal 缺失、provider delay grace 和 stale/expired/historical/unknown 都必须显式说明 expected trade date 与 research-only 边界。</p>
        <p>不合格数据不能进入 composite score、support factors、evidence preview、next-session bridge preview 或 strategy action。</p>
        <DataLineageTable rows={objectRow(freshnessAcceptance)} />
        <DataLineageTable rows={rows(cache.freshness_acceptance_matrix)} />
      </PacketCard>

      <PacketCard title="Trade_cal 本地文件验收" subtitle="只读已有 Parquet/DuckDB cache；不是页面启动外联" status={String(tradeCalPhysical.status ?? "local_trade_cal_validation")}>
        <p>如果本地 trade_cal Parquet 已存在，这里只读取 schema、日期窗口、开闭市行和当前日期覆盖；不会调用 Tushare，也不会写文件。</p>
        <p>通过只代表本地物理文件可用于 freshness 长窗口验收，不代表本次页面打开执行了 provider 刷新。</p>
        <DataLineageTable rows={objectRow(tradeCalPhysical)} />
        <DataLineageTable rows={rows(cache.trade_cal_physical_validation_rows)} />
      </PacketCard>

      <PacketCard title="Freshness 长窗口样本验收" subtitle="local synthetic trade_cal fixture；使用实际 freshness gate，不调用 Tushare" status={String(freshnessSample.status ?? "sample_validation")}>
        <p>样本覆盖盘前、盘中、收盘集合竞价、16:30 后、provider grace、节假日簇、长周末和缺今日行；它验证本地 gate 行为，但仍不是真实 trade_cal 长窗口验收。</p>
        <p>sample fixture 不能替代后续 Tushare trade_cal 真实长窗口验收；失败、陈旧、未来不可得或未知状态仍只允许 research-only 审计展示。</p>
        <DataLineageTable rows={objectRow(freshnessSample)} />
        <DataLineageTable rows={rows(cache.freshness_long_window_sample_rows)} />
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

      <PacketCard title="调用血缘" subtitle="payload 内部 local_data_health_timeline_cache；不外联、不写回" status="lineage">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET data health envelope call_ledger" subtitle="GET /api/data-health/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheEnvelopeLedger} />
      </PacketCard>

      <PacketCard title="GET data health envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={cacheWarnings.map((warning, index) => ({ index: index + 1, warning }))} />
      </PacketCard>

      <PacketCard title="原始 data health cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="data health cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
