import { useEffect, useState } from "react";
import { getRecoveryCenterCache } from "../api/client";
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

export default function RecoveryCenter() {
  const [cache, setCache] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getRecoveryCenterCache().then((res) => setCache(res.data));
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const statusStrip = (cache.recovery_result_status_strip as Record<string, unknown> | undefined) ?? {};
  const factSummary = (cache.a_share_fact_recovery_summary as Record<string, unknown> | undefined) ?? {};
  const absenceLedger = (cache.old_workspace_data_absence_ledger as Record<string, unknown> | undefined) ?? {};
  const gapReport = (cache.data_gap_report as Record<string, unknown> | undefined) ?? {};
  const callLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <>
      <div className="page-head">
        <h1>数据恢复中心</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "恢复动作", value: counts.action_count as number | undefined },
          { label: "时间线", value: counts.timeline_count as number | undefined },
          { label: "数据恢复", value: counts.data_recovery_action_count as number | undefined },
          { label: "工具恢复", value: counts.tool_recovery_action_count as number | undefined },
          { label: "证据恢复", value: counts.evidence_recovery_count as number | undefined },
          { label: "旧链动作", value: counts.legacy_action_count as number | undefined },
          { label: "Provider 恢复", value: counts.provider_recovery_count as number | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "执行恢复动作", value: policy.does_not_run_recovery_actions === true ? "不会" : "可能", tone: policy.does_not_run_recovery_actions === true ? "good" : "bad" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" }
        ]}
      />

      <div className="grid">
        <PacketCard title="恢复中心来源" subtitle="GET /api/recovery/cache 只读读取 data_recovery_actions / recovery_result_timeline" status={String(cache.status ?? "missing")}>
          <p>{String(cache.summary ?? "数据恢复中心 cache 只读展示。")}</p>
          <p>恢复动作只是手动建议；必须通过后续按钮门控任务才能触发外部请求。</p>
          <p>本页不会调用 Tushare、AkShare、yfinance、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。</p>
        </PacketCard>

        <PacketCard title="恢复状态条" subtitle="recovery_result_status_strip；只读结果摘要" status={String(statusStrip.status ?? "cache")}>
          <p>headline: {String(statusStrip.headline ?? "--")}</p>
          <p>next action: {String(statusStrip.next_action ?? "--")}</p>
          <DataLineageTable rows={objectRow(statusStrip)} />
        </PacketCard>
      </div>

      <PacketCard title="恢复动作总表" subtitle="只读 action_rows；不会自动执行恢复" status="manual_actions">
        <DataLineageTable rows={rows(cache.action_rows)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="数据恢复动作" subtitle="data_recovery_actions；后续应走 POST task" status="data_recovery">
          <DataLineageTable rows={rows(cache.data_recovery_actions)} />
        </PacketCard>
        <PacketCard title="工具恢复动作" subtitle="tool_recovery_actions；不直接打开旧工具" status="tool_recovery">
          <DataLineageTable rows={rows(cache.tool_recovery_actions)} />
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="证据恢复" subtitle="a_share_evidence_recovery_ledger；只做补证路线" status="evidence_recovery">
          <DataLineageTable rows={rows(cache.evidence_recovery_rows)} />
        </PacketCard>
        <PacketCard title="旧工作台恢复动作" subtitle="legacy_a_share_fact_recovery_actions；只读兼容信息" status="legacy_recovery">
          <DataLineageTable rows={rows(cache.legacy_actions)} />
        </PacketCard>
      </div>

      <PacketCard title="恢复时间线" subtitle="recovery_result_timeline / data_health_timeline；不重新探测接口" status="timeline">
        <DataLineageTable rows={rows(cache.timeline_rows)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="A 股事实恢复摘要" subtitle="a_share_fact_recovery_summary" status={String(factSummary.status ?? "summary")}>
          <DataLineageTable rows={objectRow(factSummary)} />
        </PacketCard>
        <PacketCard title="数据缺口报告" subtitle="data_gap_report；缺口不是无风险" status={String(gapReport.status ?? "gap")}>
          <DataLineageTable rows={objectRow(gapReport)} />
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="Provider 恢复矩阵" subtitle="provider_recovery_matrix；不 ping provider" status="provider_matrix">
          <DataLineageTable rows={rows(cache.provider_matrix_rows)} />
        </PacketCard>
        <PacketCard title="旧工作台缺失账本" subtitle="old_workspace_data_absence_ledger；只读迁移参考" status="absence">
          <DataLineageTable rows={objectRow(absenceLedger)} />
        </PacketCard>
      </div>

      <PacketCard title="API / 任务边界" subtitle="cache API 永不外联；POST task 才可能刷新" status="policy">
        <p>GET /api/recovery/cache 不调用 Tushare、AkShare、yfinance、DeepSeek 或 GitHub。</p>
        <p>不会执行恢复动作、不会刷新数据、不会执行真实交易、不会修改 strategy action 或持仓。</p>
        <p>local_recovery_center_cache 只读取本地 data_recovery_actions、tool_recovery_actions、recovery_result_timeline 等字段。</p>
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="local_recovery_center_cache；不外联、不写回" status="lineage">
        <DataLineageTable rows={callLedger} />
      </PacketCard>

      <PacketCard title="原始 recovery center cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="recovery center cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
