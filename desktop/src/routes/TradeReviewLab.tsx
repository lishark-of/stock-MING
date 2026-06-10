import { useEffect, useState } from "react";
import { getTradeReviewCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function TradeReviewLab() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);

  useEffect(() => {
    void getTradeReviewCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const summary = (cache.summary as Record<string, unknown> | undefined) ?? {};
  const records = (cache.records as Array<Record<string, unknown>> | undefined) ?? [];
  const latest = (summary.latest as Record<string, unknown> | undefined) ?? {};
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);
  const warningRows = cacheWarnings.map((warning, index) => ({ index: index + 1, warning }));
  const decisionCounts = summary.user_decisions as Record<string, unknown> | undefined;
  const actionCounts = summary.overall_actions as Record<string, unknown> | undefined;

  const recordRows = records.map((record) => ({
    created_at: record.created_at,
    ticker: record.ticker,
    user_decision: record.user_decision,
    overall_action: record.overall_action,
    strategy_action: record.strategy_action,
    follow_up_date: record.follow_up_date,
    deepseek_used: record.deepseek_used
  }));

  const decisionRows = Object.entries(decisionCounts ?? {}).map(([decision, count]) => ({ decision, count }));
  const actionRows = Object.entries(actionCounts ?? {}).map(([action, count]) => ({ action, count }));

  return (
    <>
      <div className="page-head">
        <h1>交易复盘</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "records", value: cache.record_count as number | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "read only", value: cache.read_only, tone: cache.read_only === false ? "bad" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "Tushare", value: cache.tushare_called === true ? "已调用" : "未调用", tone: cache.tushare_called === true ? "bad" : "good" },
          { label: "DeepSeek", value: cache.deepseek_called === true ? "已调用" : "未调用", tone: cache.deepseek_called === true ? "bad" : "good" },
          { label: "GitHub", value: cache.github_called === true ? "已调用" : "未调用", tone: cache.github_called === true ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="交易记录实验室 3.0" subtitle="GET /api/trade-review/cache 只读读取本地复盘日志" status="cache_only">
          <p>本页只展示本地 trade_review_log.jsonl 的复盘记录；cache-only，不创建记录，不刷新数据，不外联。</p>
          <p>不会调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不自动下单。</p>
          <p>复盘记录只作为纪律反馈和行为审计，不会修改 strategy_execution_packet.action。</p>
        </PacketCard>

        <PacketCard title="最新复盘" subtitle="安全摘要；敏感字段已过滤" status={String(cache.status ?? "missing")}>
          <p>标的：{String(latest.ticker ?? "--")}</p>
          <p>用户决策：{String(latest.user_decision ?? "--")}</p>
          <p>本地动作：{String(latest.overall_action ?? "--")}</p>
          <p>复盘时间：{String(latest.created_at ?? "--")}</p>
        </PacketCard>
      </div>

      <PacketCard title="复盘记录" subtitle="只读表格；不提交表单、不写日志" status="read_only">
        <DataLineageTable rows={recordRows} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="用户决策分布" subtitle="用于纪律回看，不生成交易建议" status="summary">
          <DataLineageTable rows={decisionRows} />
        </PacketCard>
        <PacketCard title="本地动作分布" subtitle="来自历史复盘记录，不改当前 action" status="summary">
          <DataLineageTable rows={actionRows} />
        </PacketCard>
      </div>

      <PacketCard title="调用血缘" subtitle="local_trade_review_log；cache API 永不外联" status="lineage">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET trade review envelope call_ledger" subtitle="GET /api/trade-review/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheCallLedger} />
      </PacketCard>

      <PacketCard title="GET trade review envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={warningRows} />
      </PacketCard>

      <PacketCard title="原始 trade review cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="trade review cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
