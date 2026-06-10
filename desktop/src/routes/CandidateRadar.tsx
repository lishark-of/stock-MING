import { useEffect, useState } from "react";
import { getCandidateRadarCache } from "../api/client";
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

export default function CandidateRadar() {
  const [cache, setCache] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getCandidateRadarCache().then((res) => setCache(res.data));
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const overview = (cache.candidate_execution_evidence_overview as Record<string, unknown> | undefined) ?? {};
  const radarPacket = (cache.radar_packet as Record<string, unknown> | undefined) ?? {};
  const callLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <>
      <div className="page-head">
        <h1>候选雷达</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "候选数", value: counts.candidate_count as number | undefined },
          { label: "可准备", value: counts.ready_count as number | undefined },
          { label: "只观察", value: counts.observe_count as number | undefined },
          { label: "待验证", value: counts.verify_count as number | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "市场扫描", value: policy.does_not_scan_market === true ? "不会" : "可能", tone: policy.does_not_scan_market === true ? "good" : "bad" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" }
        ]}
      />

      <div className="grid">
        <PacketCard title="下一票候选池" subtitle="GET /api/candidate-radar/cache 只读读取 radar_packet / next_ticket_candidates" status={String(cache.status ?? "missing")}>
          <p>{String(cache.summary ?? "候选雷达 cache 只读展示。")}</p>
          <p>{String(cache.manual_required_text ?? "页面打开不会自动全市场扫描。")}</p>
          <p>候选不是买入指令；必须经过证据链、触发条件、纪律和仓位预算复核。</p>
        </PacketCard>

        <PacketCard title="执行证据概览" subtitle="候选证据只作补证路线，不生成交易动作" status={String(overview.tone ?? overview.status ?? "cache")}>
          <p>headline: {String(overview.headline ?? "--")}</p>
          <p>stage: {String(overview.stage_text ?? "--")}</p>
          <p>guardrail: {String(overview.decision_guardrail ?? "--")}</p>
        </PacketCard>
      </div>

      <PacketCard title="候选列表" subtitle="只读 candidate_rows；不扫描、不排序重算" status="cache">
        <DataLineageTable rows={rows(cache.candidate_rows)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="证据恢复动作" subtitle="只展示后续手动补证路线；不自动执行旧工具" status="recovery">
          <DataLineageTable rows={rows(cache.evidence_recovery_actions)} />
        </PacketCard>
        <PacketCard title="排除候选" subtitle="来自 radar_packet.excluded_candidates；不做交易判断" status="excluded">
          <DataLineageTable rows={rows(cache.excluded_candidates)} />
        </PacketCard>
      </div>

      <PacketCard title="3.0 候选雷达边界" subtitle="cache API 永不外联；扫描必须走后续按钮任务" status="policy">
        <p>本页不会调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不自动下单，不修改 strategy action。</p>
        <p>候选分数只显示本地缓存，不进入 core action，也不改持仓。</p>
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="旧工作台桥接" subtitle="只读 old_workspace_packet_bridge" status="bridge">
          <DataLineageTable rows={objectRow(cache.old_workspace_packet_bridge)} />
        </PacketCard>
        <PacketCard title="雷达 packet 摘要" subtitle="脱敏只读 radar_packet" status={String(radarPacket.status ?? "cache")}>
          <DataLineageTable rows={objectRow(radarPacket)} />
        </PacketCard>
      </div>

      <PacketCard title="调用血缘" subtitle="local_candidate_radar_cache；不外联、不写回" status="lineage">
        <DataLineageTable rows={callLedger} />
      </PacketCard>

      <PacketCard title="原始 candidate radar cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="candidate radar cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
