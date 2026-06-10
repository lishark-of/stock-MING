import { useEffect, useState } from "react";
import { getQuantCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function QuantBacktestLab() {
  const [cache, setCache] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getQuantCache().then((res) => setCache(res.data));
  }, []);

  const quantPacket = (cache.quant_packet as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const decisionBrief = (cache.decision_brief as Record<string, unknown> | undefined) ?? {};
  const metricItems = (cache.metric_items as Array<Record<string, unknown>> | undefined) ?? [];
  const evidenceItems = ((cache.evidence_items as Array<unknown> | undefined) ?? []).map((item, idx) => ({
    index: idx + 1,
    evidence: String(item ?? "")
  }));
  const riskNotes = ((cache.risk_notes as Array<unknown> | undefined) ?? []).map((item, idx) => ({
    index: idx + 1,
    risk_note: String(item ?? "")
  }));
  const callLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <>
      <div className="page-head">
        <h1>量化 / 回测</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "score", value: quantPacket.score as string | number | undefined },
          { label: "confidence", value: quantPacket.confidence as string | undefined },
          { label: "action state", value: quantPacket.action_state as string | undefined },
          { label: "data status", value: quantPacket.data_status as string | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "run backtest", value: policy.does_not_run_backtest === true ? "不会" : "可能", tone: policy.does_not_run_backtest === true ? "good" : "bad" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" }
        ]}
      />

      <div className="grid">
        <PacketCard title="旧量化 / 回测缓存" subtitle="GET /api/quant/cache 只读展示 command_center_quant_packet" status="cache_only">
          <p>本页只读取本地量化推演和回测缓存，不运行 backtester，不调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>回测收益不代表未来收益；量化分数只能作为证据层参考，不能直接修改 strategy action。</p>
          <p>{String(cache.manual_required_text ?? "完整量化推演、回测和 DeepSeek 解释必须手动触发。")}</p>
        </PacketCard>

        <PacketCard title="决策摘要" subtitle="来自缓存 packet；前端不计算交易动作" status={String(decisionBrief.status ?? cache.status ?? "missing")}>
          <p>headline: {String(decisionBrief.headline ?? "--")}</p>
          <p>action_label: {String(decisionBrief.action_label ?? "--")}</p>
          <p>guardrail: {String(decisionBrief.guardrail_text ?? quantPacket.decision_guardrail ?? "--")}</p>
          <p>backtest_reference: {String(cache.backtest_reference ?? "--")}</p>
        </PacketCard>
      </div>

      <PacketCard title="量化指标" subtitle="只读 metric_items；不会触发重算" status="metrics">
        <DataLineageTable rows={metricItems} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="证据项" subtitle="缓存中的量化证据；不生成买卖指令" status="evidence">
          <DataLineageTable rows={evidenceItems} />
        </PacketCard>
        <PacketCard title="风险提示" subtitle="缺回测或缓存陈旧时自动降级" status="guarded">
          <DataLineageTable rows={riskNotes} />
        </PacketCard>
      </div>

      <PacketCard title="API / 任务边界" subtitle="cache API 永不外联；重算必须走后续 POST task" status="policy">
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="local_quant_backtest_cache；不运行回测" status="lineage">
        <DataLineageTable rows={callLedger} />
      </PacketCard>

      <PacketCard title="原始 quant cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="quant cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
