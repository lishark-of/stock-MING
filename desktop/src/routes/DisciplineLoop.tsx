import { useEffect, useState } from "react";
import { getDisciplineLoopCache } from "../api/client";
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

export default function DisciplineLoop() {
  const [cache, setCache] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getDisciplineLoopCache().then((res) => setCache(res.data));
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const discipline = (cache.discipline_packet as Record<string, unknown> | undefined) ?? {};
  const loop = (cache.decision_loop_status as Record<string, unknown> | undefined) ?? {};
  const today = (cache.today_action as Record<string, unknown> | undefined) ?? {};
  const decision = (cache.decision_packet as Record<string, unknown> | undefined) ?? {};
  const strategy = (cache.strategy_packet as Record<string, unknown> | undefined) ?? {};
  const issueBrief = (cache.home_data_issue_brief as Record<string, unknown> | undefined) ?? {};
  const issueExplainer = (cache.data_issue_explainer as Record<string, unknown> | undefined) ?? {};
  const callLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <>
      <div className="page-head">
        <h1>交易纪律</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "纪律分", value: discipline.score as number | undefined },
          { label: "胜率", value: discipline.win_rate as number | undefined },
          { label: "最大回撤", value: discipline.max_drawdown as number | undefined },
          { label: "闭环 ready", value: counts.loop_ready_count as number | undefined },
          { label: "闭环 waiting", value: counts.loop_waiting_count as number | undefined },
          { label: "闭环 blocked", value: counts.loop_blocked_count as number | undefined },
          { label: "刷新完成/跳过/失败", value: `${String(counts.refresh_completed_count ?? 0)} / ${String(counts.refresh_skipped_count ?? 0)} / ${String(counts.refresh_failed_count ?? 0)}` },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "运行回测", value: policy.does_not_run_backtest === true ? "不会" : "可能", tone: policy.does_not_run_backtest === true ? "good" : "bad" },
          { label: "重算 action", value: policy.does_not_recompute_action === true ? "不会" : "可能", tone: policy.does_not_recompute_action === true ? "good" : "bad" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" }
        ]}
      />

      <div className="grid">
        <PacketCard title="纪律闭环来源" subtitle="GET /api/discipline/cache 只读读取 discipline_packet / decision_loop_status" status={String(cache.status ?? "missing")}>
          <p>{String(cache.summary ?? "交易纪律 / 决策闭环 cache 只读展示。")}</p>
          <p>本页不会运行回测、不会满血刷新、不会调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>纪律分数和胜率不是买卖指令，只用于约束、复盘和降级说明。</p>
        </PacketCard>

        <PacketCard title="今日动作摘要" subtitle="today_action / decision_packet；只读，不重算" status={String(decision.status ?? "cache")}>
          <p>overall_action: {String(today.overall_action ?? decision.overall_action ?? "--")}</p>
          <p>market_bias: {String(today.market_bias ?? decision.market_bias ?? "--")}</p>
          <p>risk_level: {String(today.risk_level ?? decision.risk_level ?? "--")}</p>
          <p>position_mode: {String(today.position_mode ?? decision.position_mode ?? "--")}</p>
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="纪律 packet" subtitle="discipline_packet；不运行 backtester" status={String(discipline.status ?? "cache")}>
          <p>action_state: {String(discipline.action_state ?? "--")}</p>
          <p>backtest_status: {String(discipline.backtest_status ?? "--")}</p>
          <p>latest_signal: {String(discipline.latest_signal ?? "--")}</p>
          <p>signal_reason: {String(discipline.signal_reason ?? "--")}</p>
        </PacketCard>
        <PacketCard title="决策闭环状态" subtitle="decision_loop_status；只读闭环/恢复队列" status={String(loop.status ?? "cache")}>
          <p>headline: {String(loop.headline ?? "--")}</p>
          <p>safe mode: {String(loop.safe_mode_text ?? "--")}</p>
          <p>summary: {String(loop.summary ?? "--")}</p>
        </PacketCard>
      </div>

      <PacketCard title="纪律指标" subtitle="metric_items；胜率/回撤只作纪律参考" status="metrics">
        <DataLineageTable rows={rows(cache.discipline_metric_rows)} />
      </PacketCard>

      <PacketCard title="纪律规则" subtitle="key_rules；只读约束，不自动下单" status="rules">
        <DataLineageTable rows={rows(cache.discipline_rule_rows)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="闭环条目" subtitle="decision_loop_status.items" status="loop">
          <DataLineageTable rows={rows(cache.decision_loop_rows)} />
        </PacketCard>
        <PacketCard title="恢复队列" subtitle="recovery_queue / recovery_actions；不执行恢复动作" status="recovery">
          <DataLineageTable rows={[...rows(cache.recovery_queue_rows), ...rows(cache.recovery_action_rows)]} />
        </PacketCard>
      </div>

      <PacketCard title="满血刷新步骤" subtitle="full_refresh_steps；这里只读历史步骤，不重新运行" status="refresh_steps">
        <DataLineageTable rows={rows(cache.refresh_step_rows)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="数据问题摘要" subtitle="home_data_issue_brief" status={String(issueBrief.status ?? "cache")}>
          <DataLineageTable rows={objectRow(issueBrief)} />
        </PacketCard>
        <PacketCard title="数据问题解释" subtitle="data_issue_explainer；不调用 DeepSeek" status={String(issueExplainer.status ?? "cache")}>
          <DataLineageTable rows={objectRow(issueExplainer)} />
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="strategy packet 摘要" subtitle="只读现有 strategy_packet，不改 action" status={String(strategy.status ?? "cache")}>
          <DataLineageTable rows={objectRow(strategy)} />
        </PacketCard>
        <PacketCard title="错误记录" subtitle="errors；脱敏只读" status="errors">
          <DataLineageTable rows={rows(cache.error_rows)} />
        </PacketCard>
      </div>

      <PacketCard title="API / 任务边界" subtitle="cache API 永不外联；复核必须走后续按钮任务" status="policy">
        <p>GET /api/discipline/cache 不调用 Tushare、AkShare、yfinance、DeepSeek 或 GitHub。</p>
        <p>不会运行 backtester、不会满血刷新、不会重算 action、不会执行真实交易、不会修改 strategy action 或 decision packet。</p>
        <p>不修改 strategy action；复核和重算必须走后续按钮任务。</p>
        <p>local_discipline_loop_cache 只读取本地 discipline_packet、decision_loop_status、today_action、full_refresh_steps 等字段。</p>
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="local_discipline_loop_cache；不外联、不写回" status="lineage">
        <DataLineageTable rows={callLedger} />
      </PacketCard>

      <PacketCard title="原始 discipline loop cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="discipline loop cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
