import { useEffect, useState } from "react";
import { getMarketContextCache } from "../api/client";
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

export default function MarketContext() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);

  useEffect(() => {
    void getMarketContextCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const market = (cache.market_packet as Record<string, unknown> | undefined) ?? {};
  const profile = (cache.market_profile_evidence as Record<string, unknown> | undefined) ?? {};
  const moneyflow = (cache.moneyflow_packet as Record<string, unknown> | undefined) ?? {};
  const margin = (cache.margin_packet as Record<string, unknown> | undefined) ?? {};
  const limit = (cache.limit_emotion_packet as Record<string, unknown> | undefined) ?? {};
  const chip = (cache.chip_packet as Record<string, unknown> | undefined) ?? {};
  const etf = (cache.etf_packet as Record<string, unknown> | undefined) ?? {};
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);
  const warningRows = cacheWarnings.map((warning, index) => ({ index: index + 1, warning }));

  return (
    <>
      <div className="page-head">
        <h1>市场环境</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "trade date", value: String(cache.trade_date ?? "--") },
          { label: "packets", value: counts.packet_count as number | undefined },
          { label: "ready", value: counts.ready_count as number | undefined },
          { label: "missing", value: counts.missing_count as number | undefined },
          { label: "concepts", value: counts.concept_count as number | undefined },
          { label: "limit records", value: counts.limit_record_count as number | undefined },
          { label: "龙虎榜机构", value: counts.dragon_tiger_inst_count as number | undefined },
          { label: "筹码区", value: counts.chip_area_count as number | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="市场环境来源" subtitle="GET /api/market/cache 只读读取 market_packet / market_profile_evidence" status={String(cache.status ?? "missing")}>
          <p>{String(cache.summary ?? "市场环境 cache 只读展示。")}</p>
          <p>本页不会调用 Tushare、AkShare、yfinance、DeepSeek 或 GitHub，不刷新行情、资金流或两融数据。</p>
          <p>市场环境不是交易指令；只进入证据解释和路径置信度说明，不修改 strategy action。</p>
        </PacketCard>

        <PacketCard title="盘面画像" subtitle="market_profile_evidence；只读分析摘要" status={String(profile.status ?? "cache")}>
          <p>label: {String(profile.market_label ?? profile.market_type ?? "--")}</p>
          <p>{String(profile.summary ?? profile.manual_required_text ?? "--")}</p>
          <DataLineageTable rows={objectRow(profile)} />
        </PacketCard>
      </div>

      <PacketCard title="市场 packet 总览" subtitle="market / moneyflow / margin / limit / dragon tiger / chip / ETF" status="packets">
        <DataLineageTable rows={rows(cache.packet_rows)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="资金流" subtitle="moneyflow_packet；不刷新 Tushare" status={String(moneyflow.status ?? "cache")}>
          <p>flow: {String(moneyflow.flow_state ?? moneyflow.direction ?? "--")}</p>
          <p>main net yi: {String(moneyflow.main_net_yi ?? "--")}</p>
          <DataLineageTable rows={objectRow(moneyflow)} />
        </PacketCard>
        <PacketCard title="融资融券" subtitle="margin_packet；只读杠杆状态" status={String(margin.status ?? "cache")}>
          <p>leverage: {String(margin.leverage_state ?? "--")}</p>
          <p>margin balance yi: {String(margin.margin_balance_yi ?? "--")}</p>
          <DataLineageTable rows={objectRow(margin)} />
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="涨跌停情绪" subtitle="limit_emotion_packet；只读边界和概念热度" status={String(limit.status ?? "cache")}>
          <p>emotion: {String(limit.emotion_state ?? "--")}</p>
          <p>up / down limit: {String(limit.up_limit ?? "--")} / {String(limit.down_limit ?? "--")}</p>
          <DataLineageTable rows={rows(cache.limit_records)} />
        </PacketCard>
        <PacketCard title="龙虎榜" subtitle="dragon_tiger_packet；只读席位和机构摘要" status="dragon_tiger">
          <DataLineageTable rows={rows(cache.dragon_tiger_inst_rows)} />
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="筹码结构" subtitle="chip_packet；胜率/筹码不等于买点" status={String(chip.status ?? "cache")}>
          <p>winner rate: {String(chip.winner_rate ?? "--")}</p>
          <p>pressure: {String(chip.pressure_state ?? "--")}</p>
          <DataLineageTable rows={rows(cache.chip_pressure_rows)} />
        </PacketCard>
        <PacketCard title="ETF / 融资替代" subtitle="etf_packet / margin_etf_summary；只做替代方案说明" status={String(etf.status ?? "cache")}>
          <p>risk: {String(etf.risk_state ?? "--")}</p>
          <p>hint: {String(etf.etf_replacement_hint ?? "--")}</p>
          <DataLineageTable rows={objectRow(cache.margin_etf_summary)} />
        </PacketCard>
      </div>

      <PacketCard title="概念强度" subtitle="concept_strength_top / concept_top5；概念热度不等于交易胜率" status="concepts">
        <DataLineageTable rows={rows(cache.concept_strength_top)} />
      </PacketCard>

      <PacketCard title="API / 任务边界" subtitle="cache API 永不外联；刷新行情必须走后续按钮任务" status="policy">
        <p>GET /api/market/cache 不调用 Tushare、AkShare、yfinance、DeepSeek 或 GitHub。</p>
        <p>不会刷新行情、不会刷新资金流、不会执行真实交易、不会修改 strategy action 或持仓。</p>
        <p>local_market_context_cache 只读取本地 market_packet、moneyflow_packet、margin_packet、limit_emotion_packet 等字段。</p>
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="local_market_context_cache；不外联、不写回" status="lineage">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET market envelope call_ledger" subtitle="GET /api/market/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheCallLedger} />
      </PacketCard>

      <PacketCard title="GET market envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={warningRows} />
      </PacketCard>

      <PacketCard title="原始 market context cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="market context cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
