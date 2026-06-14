import { useEffect, useState } from "react";
import { getMigrationStatus } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";

export default function MigrationStatus() {
  const [packet, setPacket] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);

  useEffect(() => {
    void getMigrationStatus().then((res) => {
      setPacket(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const progress = (packet.progress_baseline as Array<Record<string, unknown>> | undefined) ?? [];
  const longTermGoalRows = (packet.long_term_goal_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const longTermGoalSummary = (packet.long_term_goal_summary as Record<string, unknown> | undefined) ?? {};
  const longTermBucketCounts = (longTermGoalSummary.bucket_counts as Record<string, unknown> | undefined) ?? {};
  const longTermNextPriority = (longTermGoalSummary.next_priority_order as Array<string> | undefined) ?? [];
  const tushareDeepseekLinkage = (packet.tushare_deepseek_linkage_review as Record<string, unknown> | undefined) ?? {};
  const principles = Array.isArray(packet.principles) ? packet.principles : [];
  const policy = packet.api_policy as Record<string, unknown> | undefined;
  const baselinePolicy = packet.baseline_policy as Record<string, unknown> | undefined;
  const payloadCallLedger = (packet.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((packet.warnings as Array<string> | undefined) ?? []);
  const warningRows = cacheWarnings.map((warning, index) => ({ index: index + 1, warning }));
  const principleRows = principles.map((principle, index) => {
    const text = String(principle ?? "");
    const category = text.includes("git add") || text.includes("push")
      ? "提交 / 推送纪律"
      : text.includes("Tushare") || text.includes("DeepSeek") || text.includes("GitHub") || text.includes("外部请求")
        ? "外部调用边界"
        : text.includes("交易") || text.includes("下单") || text.includes("strategy")
          ? "交易边界"
          : "迁移原则";
    return { index: index + 1, category, principle: text };
  });

  return (
    <PacketCard title="Command Center 3.0 迁移状态" subtitle="固定长期参考基线；只读、不重新估算、不外联" status={String(packet.status ?? "loading")}>
      <div className="actions">
        <button onClick={() => void getMigrationStatus().then((res) => {
          setPacket(res.data);
          setCacheEnvelopeLedger(res.call_ledger ?? []);
          setCacheEnvelopeWarnings(res.warnings ?? []);
        })}>查看迁移基线</button>
      </div>
      <MetricGrid
        items={[
          { label: "baseline items", value: progress.length },
          { label: "LTG goals", value: longTermGoalSummary.goal_count as number | undefined },
          { label: "LTG closed", value: String(longTermGoalSummary.strict_closeout ?? "0/14"), tone: longTermGoalSummary.closed_count === 0 ? "warn" : "good" },
          { label: "foundation", value: String(longTermGoalSummary.foundation_progress_estimate ?? "--") },
          { label: "production acceptance", value: String(longTermGoalSummary.production_acceptance_estimate ?? "--") },
          { label: "Tushare/DeepSeek linkage", value: String(tushareDeepseekLinkage.status ?? "pending") },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length },
          { label: "planning baseline", value: baselinePolicy?.use_as_planning_baseline === true, tone: baselinePolicy?.use_as_planning_baseline === true ? "good" : "warn" },
          { label: "cache only", value: policy?.cache_only === true, tone: policy?.cache_only === true ? "good" : "warn" },
          { label: "external calls", value: policy?.external_calls_triggered === true ? "存在" : "无", tone: policy?.external_calls_triggered === true ? "bad" : "good" },
          { label: "real trading", value: policy?.does_not_execute_trades === false ? "可能" : "禁止", tone: policy?.does_not_execute_trades === false ? "bad" : "good" },
          { label: "strategy action", value: policy?.does_not_modify_strategy_action === false ? "会修改" : "不修改", tone: policy?.does_not_modify_strategy_action === false ? "bad" : "good" }
        ]}
      />
      <h3>固定进度表</h3>
      <DataLineageTable rows={progress} />
      <h3>14 个长期目标完成度</h3>
      <p className="risk-note">严格关闭数保持 {String(longTermGoalSummary.strict_closeout ?? "0/14")}；scaffold / preflight / mock / matrix / sanitizer / dry-run / local receipt 不能作为生产完成证据。</p>
      <MetricGrid
        items={[
          { label: "mostly stable guardrails", value: Number(longTermBucketCounts.mostly_stable_guardrail ?? 0) },
          { label: "real validation required", value: Number(longTermBucketCounts.real_validation_required ?? 0) },
          { label: "productionization required", value: Number(longTermBucketCounts.productionization_required ?? 0) },
          { label: "dependent retirement", value: Number(longTermBucketCounts.dependent_retirement_goal ?? 0) },
          { label: "later polish", value: Number(longTermBucketCounts.later_polish_goal ?? 0) }
        ]}
      />
      <DataLineageTable rows={longTermGoalRows} />
      <h3>Tushare / DeepSeek 联动审查</h3>
      <p className="risk-note">cache GET 和 React render 仍保持安静；真实 provider/model execution 与 production promotion 仍需后续显式验收。</p>
      <DataLineageTable rows={[tushareDeepseekLinkage]} />
      <h3>长期迁移原则</h3>
      <p className="risk-note">这组原则来自用户长期基线；React/Tauri 主入口只读展示，不重新估算、不创建任务。</p>
      <DataLineageTable rows={principleRows} />
      <h3>GET migration envelope call_ledger</h3>
      <DataLineageTable rows={cacheCallLedger} />
      <h3>GET migration envelope warnings</h3>
      <DataLineageTable rows={warningRows} />
      <JsonDetails title="长期目标优先级" data={longTermNextPriority} />
      <JsonDetails title="目标技术栈" data={packet.target_stack ?? []} />
      <JsonDetails title="迁移原则" data={packet.principles ?? []} />
      <JsonDetails title="迁移状态 packet" data={packet} />
    </PacketCard>
  );
}
