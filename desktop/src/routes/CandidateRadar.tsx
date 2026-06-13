import { useEffect, useState } from "react";
import { getCandidateRadarCache, postCandidateRadarDeepScanPlan, postCandidateRadarFullPoolPlan, postCandidateRadarQuickScan, type TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StateClarityRail from "../components/StateClarityRail";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function objectRow(value: unknown): Array<Record<string, unknown>> {
  return value && typeof value === "object" && !Array.isArray(value) ? [value as Record<string, unknown>] : [];
}

export default function CandidateRadar() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);
  const [taskId, setTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [customPoolText, setCustomPoolText] = useState("");

  const refreshCache = () => {
    void getCandidateRadarCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  };
  const launchQuickScan = () =>
    void postCandidateRadarQuickScan({ scan_mode: "quick_cache_scan", universe_mode: "cache_snapshot" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchWatchlistScan = () =>
    void postCandidateRadarQuickScan({ scan_mode: "watchlist_scan", universe_mode: "local_watchlist" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchCustomScan = () =>
    void postCandidateRadarQuickScan({
      scan_mode: "custom_pool_scan",
      universe_mode: "manual_input",
      custom_pool_text: customPoolText
    }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchFullPoolPlan = () =>
    void postCandidateRadarFullPoolPlan({ scan_mode: "full_pool_scan", plan_only: true }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });
  const launchDeepScanPlan = () =>
    void postCandidateRadarDeepScanPlan({ scan_mode: "deep_scan", plan_only: true, scan_depth: "legacy_parity_first" }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) setTaskId(res.data.task_id);
    });

  useEffect(() => {
    refreshCache();
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const scanCoverage = (cache.scan_coverage as Record<string, unknown> | undefined) ?? {};
  const coverageDetail = (cache.coverage_detail_summary as Record<string, unknown> | undefined) ?? {};
  const scanExecutionSummary = (cache.scan_execution_summary as Record<string, unknown> | undefined) ?? {};
  const fastScanRuntimeBudget = (cache.fast_scan_runtime_budget_contract as Record<string, unknown> | undefined) ?? {};
  const fastScanReadinessAudit = (cache.fast_scan_readiness_audit as Record<string, unknown> | undefined) ?? {};
  const noFeatureLossAcceptance = (cache.no_feature_loss_acceptance_contract as Record<string, unknown> | undefined) ?? {};
  const freshnessState = (cache.freshness_state as Record<string, unknown> | undefined) ?? {};
  const fullPoolPlan = (cache.full_pool_scan_plan as Record<string, unknown> | undefined) ?? {};
  const deepScanPlan = (cache.deep_scan_plan as Record<string, unknown> | undefined) ?? {};
  const legacyParityInventory = (cache.legacy_parity_inventory as Record<string, unknown> | undefined) ?? {};
  const localPoolAudit = (cache.local_candidate_pool_audit as Record<string, unknown> | undefined) ?? {};
  const overview = (cache.candidate_execution_evidence_overview as Record<string, unknown> | undefined) ?? {};
  const radarPacket = (cache.radar_packet as Record<string, unknown> | undefined) ?? {};
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);
  const warningRows = cacheWarnings.map((warning, index) => ({ index: index + 1, warning }));
  const legacySignalRows = rows(cache.legacy_signal_group_rows);
  const legacyParityRows = rows(cache.legacy_parity_rows);
  const legacyOutputRows = rows(cache.legacy_output_contract_rows);
  const scanModeRows = rows(cache.scan_mode_status_rows);
  const scanAcceptanceRows = rows(cache.scan_acceptance_rows);
  const fastScanRuntimeBudgetRows = rows(cache.fast_scan_runtime_budget_rows);
  const fastScanReadinessRows = rows(cache.fast_scan_readiness_rows);
  const noFeatureLossAcceptanceRows = rows(cache.no_feature_loss_acceptance_rows);
  const providerCoverageRows = rows(cache.provider_coverage_rows);
  const degradedModeRows = rows(cache.degraded_mode_rows);
  const fullPoolStageRows = rows(cache.full_pool_plan_stage_rows);
  const fullPoolFilterRows = rows(cache.full_pool_plan_filter_rows);
  const fullPoolSignalRows = rows(cache.full_pool_required_signal_rows);
  const fullPoolBlockerRows = rows(cache.full_pool_blocker_rows);
  const deepScanStageRows = rows(cache.deep_scan_stage_rows);
  const deepScanParityRows = rows(cache.deep_scan_parity_rows);
  const deepScanSignalRows = rows(cache.deep_scan_required_signal_rows);
  const deepScanBlockerRows = rows(cache.deep_scan_blocker_rows);
  const radarMotionState = [
    String(cache.status ?? "cache_missing"),
    String(cache.scan_mode ?? "no_scan_mode"),
    Number(scanCoverage.missing_signal_group_count ?? 0) ? "coverage_gap" : "coverage_ok",
    Number(counts.provider_blocked_group_count ?? 0) ? "provider_blocked" : "provider_clear",
    Number(counts.degraded_mode_active_count ?? 0) ? "degraded" : "steady"
  ].join(" ");

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
          { label: "scan mode", value: String(cache.scan_mode ?? "--") },
          { label: "scan family", value: String(scanExecutionSummary.scan_family ?? "--") },
          { label: "fast readiness", value: String(fastScanReadinessAudit.status ?? "missing"), tone: fastScanReadinessAudit.local_fast_scan_ready === true ? "good" : "warn" },
          { label: "fast blockers", value: counts.fast_scan_readiness_blocker_count as number | undefined, tone: Number(counts.fast_scan_readiness_blocker_count ?? 0) ? "bad" : "good" },
          { label: "no-loss QA", value: String(noFeatureLossAcceptance.status ?? "missing"), tone: noFeatureLossAcceptance.local_no_feature_loss_contract_ready === true ? "good" : "warn" },
          { label: "no-loss gaps", value: counts.no_feature_loss_visible_gap_count as number | undefined, tone: Number(counts.no_feature_loss_visible_gap_count ?? 0) ? "warn" : "good" },
          { label: "radar prod blockers", value: counts.no_feature_loss_production_blocker_count as number | undefined, tone: Number(counts.no_feature_loss_production_blocker_count ?? 0) ? "warn" : "good" },
          { label: "full replacement", value: fastScanReadinessAudit.production_radar_replacement_complete === true ? "完成" : "未完成", tone: fastScanReadinessAudit.production_radar_replacement_complete === true ? "bad" : "good" },
          { label: "universe", value: coverageDetail.universe_size as number | undefined },
          { label: "input rows", value: coverageDetail.candidate_input_count as number | undefined },
          { label: "display cap", value: coverageDetail.candidate_display_limit as number | undefined },
          { label: "truncated", value: coverageDetail.candidate_display_truncated_count as number | undefined, tone: Number(coverageDetail.candidate_display_truncated_count ?? 0) ? "warn" : "good" },
          { label: "worker needed", value: fastScanRuntimeBudget.large_universe_worker_required === true ? "yes" : "no", tone: fastScanRuntimeBudget.large_universe_worker_required === true ? "warn" : "good" },
          { label: "覆盖组", value: scanCoverage.mapped_signal_group_count as number | undefined },
          { label: "缺口组", value: scanCoverage.missing_signal_group_count as number | undefined, tone: scanCoverage.missing_signal_group_count ? "warn" : "good" },
          { label: "provider blocked", value: counts.provider_blocked_group_count as number | undefined, tone: counts.provider_blocked_group_count ? "warn" : "good" },
          { label: "stale inputs", value: counts.stale_input_group_count as number | undefined, tone: counts.stale_input_group_count ? "warn" : "good" },
          { label: "missing provider", value: counts.missing_provider_data_group_count as number | undefined, tone: counts.missing_provider_data_group_count ? "warn" : "good" },
          { label: "degraded modes", value: counts.degraded_mode_active_count as number | undefined, tone: counts.degraded_mode_active_count ? "warn" : "good" },
          { label: "parity gap", value: counts.legacy_parity_gap_count as number | undefined, tone: counts.legacy_parity_gap_count ? "warn" : "good" },
          { label: "parity mapped", value: counts.legacy_parity_mapped_count as number | undefined },
          { label: "跳过原因", value: scanCoverage.skipped_reason_count as number | undefined, tone: scanCoverage.skipped_reason_count ? "warn" : "good" },
          { label: "验收行", value: scanAcceptanceRows.length },
          { label: "freshness", value: String(freshnessState.state ?? "unknown"), tone: freshnessState.source === "missing" ? "warn" : "good" },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "市场扫描", value: policy.does_not_scan_market === true ? "不会" : "可能", tone: policy.does_not_scan_market === true ? "good" : "bad" },
          { label: "quick scan", value: policy.quick_scan_reads_cache_only === true ? "本地" : "未知", tone: policy.quick_scan_reads_cache_only === true ? "good" : "warn" },
          { label: "full-pool plan", value: String(fullPoolPlan.status ?? "missing"), tone: fullPoolPlan.status === "full_pool_plan_ready" ? "good" : "neutral" },
          { label: "full-pool done", value: fullPoolPlan.full_pool_scan_done === true ? "完成" : "未执行", tone: fullPoolPlan.full_pool_scan_done === true ? "bad" : "good" },
          { label: "full-pool blockers", value: fullPoolPlan.blocking_issue_count as number | undefined, tone: Number(fullPoolPlan.blocking_issue_count ?? 0) ? "warn" : "good" },
          { label: "deep-scan plan", value: String(deepScanPlan.status ?? "missing"), tone: deepScanPlan.status === "deep_scan_plan_ready" ? "good" : "neutral" },
          { label: "deep-scan done", value: deepScanPlan.deep_scan_done === true ? "完成" : "未执行", tone: deepScanPlan.deep_scan_done === true ? "bad" : "good" },
          { label: "deep blockers", value: deepScanPlan.blocking_issue_count as number | undefined, tone: Number(deepScanPlan.blocking_issue_count ?? 0) ? "warn" : "good" },
          { label: "feature gaps", value: deepScanPlan.legacy_feature_gap_count as number | undefined, tone: Number(deepScanPlan.legacy_feature_gap_count ?? 0) ? "warn" : "good" },
          { label: "local pool", value: localPoolAudit.normalized_candidate_count as number | undefined },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid radar-result-cluster" data-radar-state={radarMotionState}>
        <PacketCard title="下一票候选池" subtitle="GET /api/candidate-radar/cache 只读读取 radar_packet / next_ticket_candidates" status={String(cache.status ?? "missing")}>
          <p>{String(cache.summary ?? "候选雷达 cache 只读展示。")}</p>
          <p>{String(cache.manual_required_text ?? "页面打开不会自动全市场扫描。")}</p>
          <p>候选不是买入指令；必须经过证据链、触发条件、纪律和仓位预算复核。</p>
          <StateClarityRail
            label="candidate radar visual state"
            state={radarMotionState}
            steps={[
              { label: "cache", state: cache.status === "ready" ? "done" : "waiting", detail: String(cache.status ?? "missing") },
              { label: "coverage", state: Number(scanCoverage.missing_signal_group_count ?? 0) ? "blocked" : "done", detail: String(scanCoverage.missing_signal_group_count ?? 0) },
              { label: "deep plan", state: deepScanPlan.status === "deep_scan_plan_ready" ? "done" : "waiting", detail: String(deepScanPlan.status ?? "missing") },
              { label: "trade guard", state: cache.does_not_execute_trades === false ? "blocked" : "done", detail: "safe" }
            ]}
          />
        </PacketCard>

        <PacketCard title="快速雷达扫描" subtitle="POST /api/candidate-radar/scan-quick 只读取本地 snapshot/cache" status={String(scanCoverage.coverage_status ?? "cache")}>
          <div className="actions">
            <button onClick={refreshCache}>查看缓存</button>
            <button onClick={launchQuickScan}>运行 quick scan</button>
            <button onClick={launchWatchlistScan}>运行 watchlist scan</button>
          </div>
          <textarea
            value={customPoolText}
            onChange={(event) => setCustomPoolText(event.target.value)}
            placeholder="002008.SZ, 002837.SZ"
            rows={3}
          />
          <div className="actions">
            <button onClick={launchCustomScan}>运行 custom pool scan</button>
            <button onClick={launchFullPoolPlan}>生成 full-pool 计划</button>
            <button onClick={launchDeepScanPlan}>生成 deep-scan 清单</button>
          </div>
          <TaskLaunchReceipt receipt={taskReceipt} />
          <TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />
          <p>quick scan 只做本地 cache 快速重建和覆盖缺口标记，不调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>scan_coverage 和 legacy_signal_group_rows 用来确认旧模块下一票雷达能力没有被静默丢失。</p>
          <p>skipped_reason_rows 和 freshness_state 会把缺失、跳过、陈旧或未知输入直接显示出来。</p>
          <p>任务血缘写入 local_candidate_radar_[scan_mode]，GET cache 仍然只读。</p>
          <p>quick_scan_reads_cache_only: {String(policy.quick_scan_reads_cache_only === true)}</p>
          <DataLineageTable rows={objectRow(scanCoverage)} />
        </PacketCard>

        <PacketCard title="执行证据概览" subtitle="候选证据只作补证路线，不生成交易动作" status={String(overview.tone ?? overview.status ?? "cache")}>
          <p>headline: {String(overview.headline ?? "--")}</p>
          <p>stage: {String(overview.stage_text ?? "--")}</p>
          <p>guardrail: {String(overview.decision_guardrail ?? "--")}</p>
        </PacketCard>
      </div>

      <PacketCard title="旧雷达信号组覆盖" subtitle="legacy_signal_group_rows；缺口只报告，不静默降能" status={String(scanCoverage.coverage_status ?? "coverage")}>
        <DataLineageTable rows={legacySignalRows} />
      </PacketCard>

      <PacketCard title="扫描覆盖明细" subtitle="coverage_detail_summary / provider_coverage_rows / degraded_mode_rows；缺失不静默降能" status={String(coverageDetail.degraded_mode_active ? "degraded" : "coverage")}>
        <p>universe size、provider-blocked groups、stale inputs、missing provider data 和 degraded modes 必须显式展示；页面渲染不会补数或触发 full-pool scan。</p>
        <p>missing provider data is reported, not dropped；quick scan 仍是 research-only，不替代 legacy full scan。</p>
        <DataLineageTable rows={objectRow(coverageDetail)} />
        <DataLineageTable rows={providerCoverageRows} />
        <DataLineageTable rows={degradedModeRows} />
      </PacketCard>

      <PacketCard title="扫描执行验收" subtitle="scan_execution_summary / scan_acceptance_rows；区分 cache、local scan 和 plan-only" status={String(scanExecutionSummary.scan_family ?? "audit")}>
        <p>scan_execution_summary 只总结本地执行边界，不证明 full-pool scan 已完成。</p>
        <p>scan_acceptance_rows 把 provider gap、freshness、local pool、full-pool 和交易隔离逐项展示。</p>
        <DataLineageTable rows={objectRow(scanExecutionSummary)} />
        <DataLineageTable rows={scanAcceptanceRows} />
      </PacketCard>

      <PacketCard title="快扫运行预算" subtitle="fast_scan_runtime_budget_contract；控制同步展示规模，超限必须可见并转 worker" status={String(fastScanRuntimeBudget.status ?? "missing")}>
        <p>display_candidate_limit: {String(fastScanRuntimeBudget.display_candidate_limit ?? "--")}</p>
        <p>candidate_input_count: {String(fastScanRuntimeBudget.candidate_input_count ?? 0)}</p>
        <p>candidate_display_truncated_count: {String(fastScanRuntimeBudget.candidate_display_truncated_count ?? 0)}</p>
        <p>large_universe_worker_required: {String(fastScanRuntimeBudget.large_universe_worker_required ?? false)}</p>
        <p>browser_performance_trace_done: {String(fastScanRuntimeBudget.browser_performance_trace_done ?? false)}</p>
        <p>快扫预算只限制本地同步展示和输入规范化；超出时报告截断与 worker 边界，不隐藏 provider、freshness 或 legacy parity 缺口。</p>
        <DataLineageTable rows={objectRow(fastScanRuntimeBudget)} />
        <DataLineageTable rows={fastScanRuntimeBudgetRows} />
      </PacketCard>

      <PacketCard title="快扫 readiness 审计" subtitle="fast_scan_readiness_audit / rows；证明本地快扫不阻塞、不静默降能，但不代表 full-pool/deep-scan 完成" status={String(fastScanReadinessAudit.status ?? "missing")}>
        <p>local_fast_scan_ready: {String(fastScanReadinessAudit.local_fast_scan_ready ?? false)}</p>
        <p>production_radar_replacement_complete: {String(fastScanReadinessAudit.production_radar_replacement_complete ?? false)}</p>
        <p>provider_backed_acceptance_done: {String(fastScanReadinessAudit.provider_backed_acceptance_done ?? false)}</p>
        <p>full_pool_scan_done: {String(fastScanReadinessAudit.full_pool_scan_done ?? false)}</p>
        <p>deep_scan_done: {String(fastScanReadinessAudit.deep_scan_done ?? false)}</p>
        <DataLineageTable rows={objectRow(fastScanReadinessAudit)} />
        <DataLineageTable rows={fastScanReadinessRows} />
      </PacketCard>

      <PacketCard title="快扫不降能验收" subtitle="no_feature_loss_acceptance_contract；本地 QA 面可见，但不是生产雷达替代完成" status={String(noFeatureLossAcceptance.status ?? "missing")}>
        <p>local_no_feature_loss_contract_ready: {String(noFeatureLossAcceptance.local_no_feature_loss_contract_ready ?? false)}</p>
        <p>production_radar_replacement_complete: {String(noFeatureLossAcceptance.production_radar_replacement_complete ?? false)}</p>
        <p>legacy_fallback_required: {String(noFeatureLossAcceptance.legacy_fallback_required ?? true)}</p>
        <p>browser_performance_trace_done: {String(noFeatureLossAcceptance.browser_performance_trace_done ?? false)}</p>
        <p>此合同汇总旧信号组、输出字段、provider/freshness 缺口、运行预算、full-pool/deep-scan 边界和交易隔离；gap 可见不等于真实 full-pool/deep-scan/provider-backed 验收完成。</p>
        <DataLineageTable rows={objectRow(noFeatureLossAcceptance)} />
        <DataLineageTable rows={noFeatureLossAcceptanceRows} />
      </PacketCard>

      <PacketCard title="Deep-scan 准备清单" subtitle="POST /api/candidate-radar/deep-scan-plan；只生成不降能验收单，不执行 deep_scan" status={String(deepScanPlan.status ?? "plan_missing")}>
        <p>deep_scan_plan 是 plan-only：不刷新 provider、不调用 DeepSeek、不执行 deep_scan、不生成买入候选、不修改 strategy action。</p>
        <p>feature_loss_gaps_visible: {String(policy.deep_scan_feature_loss_gaps_visible === true)}</p>
        <p>page_render_starts_deep_scan: {String(deepScanPlan.page_render_starts_deep_scan === true)}</p>
        <DataLineageTable rows={objectRow(deepScanPlan)} />
        <DataLineageTable rows={deepScanStageRows} />
        <DataLineageTable rows={deepScanParityRows} />
        <DataLineageTable rows={deepScanSignalRows} />
        <DataLineageTable rows={deepScanBlockerRows} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="旧雷达 parity inventory" subtitle="legacy_parity_rows；映射、缺口、未来任务必须分清" status={String(legacyParityInventory.status ?? "partial_parity")}>
          <p>quick_scan_is_full_replacement: {String(legacyParityInventory.quick_scan_is_full_replacement === true)}</p>
          <p>slow_paths_are_future_button_tasks: {String(legacyParityInventory.slow_paths_are_future_button_tasks !== false)}</p>
          <DataLineageTable rows={legacyParityRows} />
        </PacketCard>
        <PacketCard title="旧雷达输出合同" subtitle="legacy_output_contract_rows；字段缺失不造假" status="contract">
          <DataLineageTable rows={legacyOutputRows} />
        </PacketCard>
      </div>

      <PacketCard title="扫描模式状态" subtitle="scan_mode_status_rows；当前本地实现 quick/watchlist/custom，full pool 仍是未来任务" status="mode">
        <DataLineageTable rows={scanModeRows} />
      </PacketCard>

      <PacketCard title="Full-pool 准备计划" subtitle="POST /api/candidate-radar/full-pool-plan；只生成计划，不扫描全市场" status={String(fullPoolPlan.status ?? "plan_missing")}>
        <p>full_pool_scan_plan 是 plan-only：不刷新 provider、不执行 full_pool_scan、不生成买入候选、不修改 strategy action。</p>
        <p>page_render_starts_full_pool: {String(fullPoolPlan.page_render_starts_full_pool === true)}</p>
        <p>worker_task_required: {String(fullPoolPlan.worker_task_required === true)}</p>
        <DataLineageTable rows={objectRow(fullPoolPlan)} />
        <DataLineageTable rows={fullPoolStageRows} />
        <DataLineageTable rows={fullPoolFilterRows} />
        <DataLineageTable rows={fullPoolSignalRows} />
        <DataLineageTable rows={fullPoolBlockerRows} />
      </PacketCard>

      <PacketCard title="本地候选池审计" subtitle="local_candidate_pool_audit；watchlist/custom 只读本地输入" status={String(localPoolAudit.input_source ?? "cache")}>
        <DataLineageTable rows={objectRow(localPoolAudit)} />
        <DataLineageTable rows={rows(cache.local_candidate_pool_skipped_rows)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="跳过原因" subtitle="skipped_reason_rows；缺失和降级不会被隐藏" status="coverage">
          <DataLineageTable rows={rows(cache.skipped_reason_rows)} />
        </PacketCard>
        <PacketCard title="Freshness 状态" subtitle="freshness_state；未知或陈旧只作为 research-only 缺口展示" status={String(freshnessState.state ?? "unknown")}>
          <DataLineageTable rows={objectRow(freshnessState)} />
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
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET candidate envelope call_ledger" subtitle="GET /api/candidate-radar/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheCallLedger} />
      </PacketCard>

      <PacketCard title="GET candidate envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={warningRows} />
      </PacketCard>

      <PacketCard title="原始 candidate radar cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="candidate radar cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
