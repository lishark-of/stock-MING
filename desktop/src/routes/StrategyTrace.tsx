import { useEffect, useState } from "react";
import { getStrategyCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

function tableRows(items: unknown): Array<Record<string, unknown>> {
  return Array.isArray(items) ? (items as Array<Record<string, unknown>>) : [];
}

export default function StrategyTrace() {
  const [cache, setCache] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getStrategyCache().then((res) => setCache(res.data));
  }, []);

  const actionSummary = (cache.action_summary as Record<string, unknown> | undefined) ?? {};
  const decisionSummary = (cache.decision_summary as Record<string, unknown> | undefined) ?? {};
  const strategyTrace = (cache.strategy_trace as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const strategyPacket = (cache.strategy_packet as Record<string, unknown> | undefined) ?? {};
  const decisionPacket = (cache.decision_packet as Record<string, unknown> | undefined) ?? {};
  const inputSources = tableRows(strategyTrace.input_sources);
  const rulesFired = tableRows(strategyTrace.rules_fired);
  const missingInputs = ((strategyTrace.missing_inputs as Array<unknown> | undefined) ?? []).map((item, idx) => ({
    index: idx + 1,
    missing_input: String(item ?? "")
  }));
  const callLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <>
      <div className="page-head">
        <h1>策略 Trace</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "action", value: actionSummary.action_label as string | undefined },
          { label: "confidence", value: actionSummary.confidence_label as string | undefined },
          { label: "decision", value: decisionSummary.overall_action as string | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "DeepSeek", value: cache.deepseek_called === true ? "已调用" : "未调用", tone: cache.deepseek_called === true ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" }
        ]}
      />

      <div className="grid">
        <PacketCard title="策略动作来源" subtitle="GET /api/strategy/cache 只读读取 strategy_execution_packet" status={String(cache.status ?? "missing")}>
          <p>action_source: {String(actionSummary.action_source ?? policy.action_source ?? "strategy_execution_packet")}</p>
          <p>action: {String(actionSummary.action ?? "--")}</p>
          <p>position_advice: {String(actionSummary.position_advice ?? "--")}</p>
          <p>summary: {String(actionSummary.summary ?? "--")}</p>
        </PacketCard>

        <PacketCard title="决策摘要" subtitle="读取 command_center_decision_packet；不改写策略动作" status={String(decisionSummary.status ?? "missing")}>
          <p>overall_action: {String(decisionSummary.overall_action ?? "--")}</p>
          <p>market_bias: {String(decisionSummary.market_bias ?? "--")}</p>
          <p>risk_level: {String(decisionSummary.risk_level ?? "--")}</p>
          <p>source: {String(decisionSummary.source ?? "command_center_decision_packet")}</p>
        </PacketCard>
      </div>

      <PacketCard title="3.0 只读边界" subtitle="cache API 永不外联；不会重新计算或执行交易" status="policy">
        <p>本页只展示已有 strategy_execution_packet / command_center_decision_packet；不会调用 Tushare、DeepSeek 或 GitHub。</p>
        <p>不会运行 backtester，不执行真实交易，不自动下单，不修改 strategy action 或 decision packet。</p>
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="输入来源" subtitle="来自 strategy_execution_trace.input_sources" status="trace">
          <DataLineageTable rows={inputSources} />
        </PacketCard>
        <PacketCard title="触发规则" subtitle="来自 strategy_execution_trace.rules_fired" status="rules">
          <DataLineageTable rows={rulesFired} />
        </PacketCard>
      </div>

      <PacketCard title="缺失输入" subtitle="缺失只用于降级说明，不生成 suppress 或买卖指令" status="guarded">
        <DataLineageTable rows={missingInputs} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="local_strategy_trace_cache；不外联、不写回" status="lineage">
        <DataLineageTable rows={callLedger} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="strategy_execution_packet" subtitle="脱敏只读 payload" status="safe">
          <JsonDetails title="strategy packet" data={strategyPacket} />
        </PacketCard>
        <PacketCard title="command_center_decision_packet" subtitle="脱敏只读 payload" status="safe">
          <JsonDetails title="decision packet" data={decisionPacket} />
        </PacketCard>
      </div>

      <PacketCard title="原始 strategy trace cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="strategy trace cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
