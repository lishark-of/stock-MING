import { useEffect, useState } from "react";
import {
  getDataHealthCache,
  postProducerCacheRefreshExecutionRequest,
  postTradeCalProviderAcceptanceDryRun,
  postTradeCalProviderAcceptanceExecutionRequest,
  type TaskCreationEnvelope
} from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";

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
  const [tradeCalDryRunReceipt, setTradeCalDryRunReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [tradeCalDryRunError, setTradeCalDryRunError] = useState("");
  const [tradeCalExecutionRequestReceipt, setTradeCalExecutionRequestReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [tradeCalExecutionRequestError, setTradeCalExecutionRequestError] = useState("");
  const [producerCacheRefreshRequestReceipt, setProducerCacheRefreshRequestReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [producerCacheRefreshRequestError, setProducerCacheRefreshRequestError] = useState("");

  useEffect(() => {
    void getDataHealthCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  function launchTradeCalDryRun() {
    const end = new Date();
    const start = new Date(end);
    start.setDate(start.getDate() - 730);
    const yyyymmdd = (date: Date) => date.toISOString().slice(0, 10).replace(/-/g, "");
    setTradeCalDryRunError("");
    void postTradeCalProviderAcceptanceDryRun({
      approved_by_user: true,
      apis: ["trade_cal"],
      exchange: ["SSE", "SZSE"],
      start_date: yyyymmdd(start),
      end_date: yyyymmdd(end),
      requested_by: "command_center_3_data_health",
      source: "data_health_page"
    }).then((res) => {
      setTradeCalDryRunReceipt(res);
      if (!res.ok) {
        setTradeCalDryRunError(String(res.error ?? "trade_cal_provider_acceptance_dry_run_failed"));
      }
    }).catch((err: unknown) => {
      setTradeCalDryRunError(err instanceof Error ? err.message : String(err));
    });
  }

  function launchTradeCalExecutionRequest() {
    const scopeHash = String(tradeCalDryRun.acceptance_scope_hash_short ?? tradeCalDryRun.latest_dry_run_scope_hash_short ?? "");
    setTradeCalExecutionRequestError("");
    void postTradeCalProviderAcceptanceExecutionRequest({
      approved_by_user: true,
      acceptance_scope_hash_short: scopeHash,
      apis: ["trade_cal"],
      exchange: tradeCalDryRun.exchange ?? ["SSE", "SZSE"],
      start_date: tradeCalDryRun.start_date,
      end_date: tradeCalDryRun.end_date,
      requested_by: "command_center_3_data_health",
      source: "data_health_page"
    }).then((res) => {
      setTradeCalExecutionRequestReceipt(res);
      if (!res.ok) {
        setTradeCalExecutionRequestError(String(res.error ?? "trade_cal_provider_acceptance_execution_request_failed"));
      }
    }).catch((err: unknown) => {
      setTradeCalExecutionRequestError(err instanceof Error ? err.message : String(err));
    });
  }

  function launchProducerCacheRefreshExecutionRequest() {
    const scopeHash = String(producerCacheRefreshReadiness.readiness_scope_hash_short ?? "");
    setProducerCacheRefreshRequestError("");
    void postProducerCacheRefreshExecutionRequest({
      approved_by_user: true,
      readiness_scope_hash_short: scopeHash,
      producer_keys: producerCacheRefreshReadiness.producer_keys ?? ["candidate_radar", "a_share_evidence_radar", "market_context"],
      requested_by: "command_center_3_data_health",
      source: "data_health_page"
    }).then((res) => {
      setProducerCacheRefreshRequestReceipt(res);
      if (!res.ok) {
        setProducerCacheRefreshRequestError(String(res.error ?? "producer_cache_refresh_execution_request_failed"));
      }
    }).catch((err: unknown) => {
      setProducerCacheRefreshRequestError(err instanceof Error ? err.message : String(err));
    });
  }

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const visibility = (cache.data_health_visibility_summary as Record<string, unknown> | undefined) ?? {};
  const providerCockpit = (cache.provider_data_capability_cockpit as Record<string, unknown> | undefined) ?? {};
  const freshnessAcceptance = (cache.freshness_acceptance_summary as Record<string, unknown> | undefined) ?? {};
  const freshnessSample = (cache.freshness_long_window_sample_validation as Record<string, unknown> | undefined) ?? {};
  const tradeCalPhysical = (cache.trade_cal_physical_validation as Record<string, unknown> | undefined) ?? {};
  const tradeCalProviderRunbook = (cache.trade_cal_provider_acceptance_runbook as Record<string, unknown> | undefined) ?? {};
  const tradeCalPromotionAudit = (cache.trade_cal_provider_acceptance_promotion_audit as Record<string, unknown> | undefined) ?? {};
  const freshnessProductionBlockerAudit = (cache.freshness_production_blocker_audit as Record<string, unknown> | undefined) ?? {};
  const freshnessProviderReadinessReceipt = (cache.freshness_provider_acceptance_readiness_receipt as Record<string, unknown> | undefined) ?? {};
  const freshnessProviderActivationReceipt = (cache.freshness_provider_acceptance_activation_receipt as Record<string, unknown> | undefined) ?? {};
  const latestTradeCalDryRun = (cache.latest_trade_cal_provider_acceptance_dry_run as Record<string, unknown> | undefined) ?? {};
  const tradeCalNextExecutionRecipe = (cache.trade_cal_provider_acceptance_next_execution_recipe as Record<string, unknown> | undefined) ?? {};
  const latestTradeCalExecutionRequest = (cache.latest_trade_cal_provider_acceptance_execution_request as Record<string, unknown> | undefined) ?? {};
  const latestTushareTargetSampleExecutionRequest = (cache.latest_tushare_provider_target_sample_execution_request as Record<string, unknown> | undefined) ?? {};
  const freshnessDurableEvidenceRecipe = (cache.freshness_durable_evidence_recipe as Record<string, unknown> | undefined) ?? {};
  const freshnessDurableEvidenceRows = rows(cache.freshness_durable_evidence_rows);
  const latestTradeCalDryRunReceipt = latestTradeCalDryRun.receipt as Record<string, unknown> | undefined;
  const currentEvidenceFreshness = (cache.current_evidence_freshness_qa_contract as Record<string, unknown> | undefined) ?? {};
  const decisionSurfaceAudit = (cache.current_evidence_decision_surface_audit as Record<string, unknown> | undefined) ?? {};
  const producerCoverageAudit = (cache.current_evidence_producer_coverage_audit as Record<string, unknown> | undefined) ?? {};
  const producerGenerationContract = (cache.current_evidence_producer_generation_contract as Record<string, unknown> | undefined) ?? {};
  const producerCacheRefreshReadiness = (cache.current_evidence_producer_cache_refresh_readiness as Record<string, unknown> | undefined) ?? {};
  const latestProducerCacheRefreshRequest = (cache.latest_producer_cache_refresh_execution_request as Record<string, unknown> | undefined) ?? {};
  const latestProducerCacheRefreshRequestReceipt = latestProducerCacheRefreshRequest.receipt as Record<string, unknown> | undefined;
  const producerCacheRefreshRequestPayload = (producerCacheRefreshRequestReceipt?.data?.task?.payload_safe as Record<string, unknown> | undefined) ?? {};
  const postProducerCacheRefreshRequestReceipt = producerCacheRefreshRequestPayload.producer_cache_refresh_execution_request_receipt as Record<string, unknown> | undefined;
  const producerCacheRefreshRequest = postProducerCacheRefreshRequestReceipt ?? latestProducerCacheRefreshRequestReceipt ?? latestProducerCacheRefreshRequest;
  const producerCacheRefreshRequestRows = rows(producerCacheRefreshRequestPayload.producer_cache_refresh_execution_request_rows ?? cache.latest_producer_cache_refresh_execution_request_rows);
  const tradeCalDryRunPayload = (tradeCalDryRunReceipt?.data?.task?.payload_safe as Record<string, unknown> | undefined) ?? {};
  const postTradeCalDryRunReceipt = tradeCalDryRunPayload.trade_cal_provider_acceptance_dry_run_receipt as Record<string, unknown> | undefined;
  const tradeCalDryRun = postTradeCalDryRunReceipt ?? latestTradeCalDryRunReceipt ?? latestTradeCalDryRun;
  const tradeCalDryRunRows = rows(tradeCalDryRunPayload.trade_cal_provider_acceptance_dry_run_rows ?? cache.latest_trade_cal_provider_acceptance_dry_run_rows);
  const tradeCalDryRunCredentialRows = rows(tradeCalDryRunPayload.credential_presence_rows ?? cache.latest_trade_cal_provider_acceptance_dry_run_credential_rows);
  const latestTradeCalExecutionRequestReceipt = latestTradeCalExecutionRequest.receipt as Record<string, unknown> | undefined;
  const tradeCalExecutionRequestPayload = (tradeCalExecutionRequestReceipt?.data?.task?.payload_safe as Record<string, unknown> | undefined) ?? {};
  const postTradeCalExecutionRequestReceipt = tradeCalExecutionRequestPayload.trade_cal_provider_acceptance_execution_request_receipt as Record<string, unknown> | undefined;
  const tradeCalExecutionRequest = postTradeCalExecutionRequestReceipt ?? latestTradeCalExecutionRequestReceipt ?? latestTradeCalExecutionRequest;
  const tradeCalExecutionRequestRows = rows(tradeCalExecutionRequestPayload.trade_cal_provider_acceptance_execution_request_rows ?? cache.latest_trade_cal_provider_acceptance_execution_request_rows);
  const latestTushareTargetSampleExecutionRequestReceipt = latestTushareTargetSampleExecutionRequest.receipt as Record<string, unknown> | undefined;
  const tushareTargetSampleExecutionRequest = latestTushareTargetSampleExecutionRequestReceipt ?? latestTushareTargetSampleExecutionRequest;
  const tushareTargetSampleExecutionRequestRows = rows(cache.latest_tushare_provider_target_sample_execution_request_rows);
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
          { label: "provider runbook", value: tradeCalProviderRunbook.status as string | undefined, tone: tradeCalProviderRunbook.local_runbook_ready === true ? "good" : "warn" },
          { label: "provider pending", value: counts.trade_cal_provider_acceptance_pending_count as number | undefined, tone: Number(counts.trade_cal_provider_acceptance_pending_count ?? 0) > 0 ? "warn" : "good" },
          { label: "提升审计", value: tradeCalPromotionAudit.status as string | undefined, tone: tradeCalPromotionAudit.promotion_ready === true ? "good" : "warn" },
          { label: "提升 blockers", value: counts.trade_cal_provider_acceptance_promotion_blocker_count as number | undefined, tone: Number(counts.trade_cal_provider_acceptance_promotion_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "provider 证据行", value: counts.trade_cal_provider_acceptance_evidence_row_count as number | undefined },
          { label: "生产 blockers", value: counts.freshness_production_blocker_count as number | undefined, tone: Number(counts.freshness_production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "provider 准入", value: freshnessProviderReadinessReceipt.status as string | undefined, tone: freshnessProviderReadinessReceipt.ready_for_explicit_provider_task === true ? "good" : "warn" },
          { label: "准入 blockers", value: counts.freshness_provider_acceptance_readiness_blocker_count as number | undefined, tone: Number(counts.freshness_provider_acceptance_readiness_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "provider 启用", value: freshnessProviderActivationReceipt.status as string | undefined, tone: freshnessProviderActivationReceipt.local_activation_receipt_ready === true ? "good" : "warn" },
          { label: "启用 blockers", value: counts.freshness_provider_acceptance_activation_blocker_count as number | undefined, tone: Number(counts.freshness_provider_acceptance_activation_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "latest dry-run", value: latestTradeCalDryRun.latest_task_found === true ? "可见" : "未运行", tone: latestTradeCalDryRun.latest_task_found === true ? "good" : "neutral" },
          { label: "dry-run rows", value: counts.latest_trade_cal_provider_acceptance_dry_run_row_count as number | undefined },
          { label: "dry-run blockers", value: counts.latest_trade_cal_provider_acceptance_dry_run_blocking_row_count as number | undefined, tone: Number(counts.latest_trade_cal_provider_acceptance_dry_run_blocking_row_count ?? 0) > 0 ? "warn" : "good" },
          { label: "下一步配方", value: tradeCalNextExecutionRecipe.status as string | undefined, tone: tradeCalNextExecutionRecipe.recipe_ready_for_user_confirmation === true ? "good" : "warn" },
          { label: "配方 blockers", value: counts.trade_cal_provider_acceptance_next_execution_blocker_count as number | undefined, tone: Number(counts.trade_cal_provider_acceptance_next_execution_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "执行请求", value: latestTradeCalExecutionRequest.latest_task_found === true ? "可见" : "未运行", tone: latestTradeCalExecutionRequest.latest_task_found === true ? "good" : "neutral" },
          { label: "请求 blockers", value: counts.latest_trade_cal_provider_acceptance_execution_request_blocking_row_count as number | undefined, tone: Number(counts.latest_trade_cal_provider_acceptance_execution_request_blocking_row_count ?? 0) > 0 ? "warn" : "good" },
          { label: "Tushare 样本请求", value: latestTushareTargetSampleExecutionRequest.latest_task_found === true ? "可见" : "未运行", tone: latestTushareTargetSampleExecutionRequest.latest_task_found === true ? "good" : "neutral" },
          { label: "样本请求 blockers", value: counts.latest_tushare_provider_target_sample_execution_request_blocking_row_count as number | undefined, tone: Number(counts.latest_tushare_provider_target_sample_execution_request_blocking_row_count ?? 0) > 0 ? "warn" : "good" },
          { label: "durable recipe", value: freshnessDurableEvidenceRecipe.status as string | undefined, tone: freshnessDurableEvidenceRecipe.local_recipe_ready === true ? "good" : "warn" },
          { label: "durable blockers", value: freshnessDurableEvidenceRecipe.durable_evidence_blocker_count ?? counts.freshness_durable_evidence_blocker_count, tone: Number(freshnessDurableEvidenceRecipe.durable_evidence_blocker_count ?? counts.freshness_durable_evidence_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "当前证据 QA", value: currentEvidenceFreshness.status as string | undefined, tone: currentEvidenceFreshness.provider_backed_long_window_acceptance_done === true ? "good" : "warn" },
          { label: "当前证据准入", value: currentEvidenceFreshness.current_evidence_candidate_status as string | undefined, tone: currentEvidenceFreshness.current_evidence_candidate_status === "current_evidence_ready" ? "good" : "warn" },
          { label: "证据 blockers", value: counts.current_evidence_freshness_qa_blocker_count as number | undefined, tone: counts.current_evidence_freshness_qa_blocker_count === 0 ? "good" : "warn" },
          { label: "可见面审计", value: decisionSurfaceAudit.status as string | undefined, tone: Number(counts.current_evidence_decision_surface_blocker_count ?? 0) > 0 ? "bad" : "good" },
          { label: "可见面 blockers", value: counts.current_evidence_decision_surface_blocker_count as number | undefined, tone: Number(counts.current_evidence_decision_surface_blocker_count ?? 0) > 0 ? "bad" : "good" },
          { label: "producer 覆盖", value: producerCoverageAudit.status as string | undefined, tone: Number(counts.current_evidence_producer_coverage_blocker_count ?? 0) > 0 ? "bad" : "good" },
          { label: "producer blockers", value: counts.current_evidence_producer_coverage_blocker_count as number | undefined, tone: Number(counts.current_evidence_producer_coverage_blocker_count ?? 0) > 0 ? "bad" : "good" },
          { label: "producer 生成", value: producerGenerationContract.status as string | undefined, tone: producerGenerationContract.local_generation_contract_ready === true ? "good" : "warn" },
          { label: "cache refresh", value: producerCacheRefreshReadiness.status as string | undefined, tone: producerCacheRefreshReadiness.local_cache_refresh_ready === true ? "good" : "warn" },
          { label: "refresh required", value: counts.current_evidence_producer_cache_refresh_required_count as number | undefined },
          { label: "refresh request", value: latestProducerCacheRefreshRequest.latest_task_found === true ? "可见" : "未运行", tone: latestProducerCacheRefreshRequest.latest_task_found === true ? "good" : "neutral" },
          { label: "request blockers", value: counts.latest_producer_cache_refresh_execution_request_blocking_row_count as number | undefined, tone: Number(counts.latest_producer_cache_refresh_execution_request_blocking_row_count ?? 0) > 0 ? "warn" : "good" },
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

      <PacketCard title="当前证据 Freshness QA" subtitle="current_evidence_freshness_qa_contract；锁定当前证据和历史样本边界" status={String(currentEvidenceFreshness.status ?? "current_evidence_qa")}>
        <p>当前证据必须有 expected trade date，且 data date 与 expected trade date 对齐；stale、expired、historical、unknown 和 future-unavailable 只能作为 research-only 展示。</p>
        <p>synthetic sample、历史样本、本地 trade_cal 文件验收都不能替代 provider-backed trade_cal 长窗口验收，也不能把数据送入 composite score、support factors、evidence preview、next-session bridge preview 或 strategy action。</p>
        <DataLineageTable rows={objectRow(currentEvidenceFreshness)} />
        <DataLineageTable rows={rows(cache.current_evidence_freshness_qa_rows)} />
      </PacketCard>

      <PacketCard title="当前证据可见面审计" subtitle="current_evidence_decision_surface_audit；只读 snapshot，不重新评分、不改 action" status={String(decisionSurfaceAudit.status ?? "decision_surface_audit")}>
        <p>审计 composite_score、support_factors、evidence_preview、next_session_bridge.preview 和 strategy_action 的本地可见字段；看不见的字段只标记 not_observed，不当作生产验收完成。</p>
        <p>如果当前证据是 research-only，但可见面仍有 score/support/preview 值，会列为 blocker；本页不会过滤 packet、不会重算分数、不会修改 strategy action。</p>
        <DataLineageTable rows={objectRow(decisionSurfaceAudit)} />
        <DataLineageTable rows={rows(cache.current_evidence_decision_surface_rows)} />
      </PacketCard>

      <PacketCard title="当前证据 Producer 覆盖" subtitle="current_evidence_producer_coverage_audit；检查 expected_trade_date / data_date / freshness_state 字段" status={String(producerCoverageAudit.status ?? "producer_coverage")}>
        <p>只读检查 data_freshness、Factor Quant Hub、下一票雷达、次日图谱、A 股证据雷达和市场环境等本地可见 producer；缺失 producer 标记 not_observed，不当作生产验收完成。</p>
        <p>已观察到的 producer 必须显式带 expected_trade_date、data_date 和 freshness_state；本页不会构建缺失 packet、不会刷新 provider、不会修改 action。</p>
        <DataLineageTable rows={objectRow(producerCoverageAudit)} />
        <DataLineageTable rows={rows(cache.current_evidence_producer_coverage_rows)} />
      </PacketCard>

      <PacketCard title="当前证据 Producer 生成合同" subtitle="current_evidence_producer_generation_contract；本地生成器字段合同，不写 cache" status={String(producerGenerationContract.status ?? "producer_generation")}>
        <p>local_generation_contract_ready: {String(producerGenerationContract.local_generation_contract_ready === true)}</p>
        <p>current_cache_refresh_pending: {String(producerGenerationContract.current_cache_refresh_pending === true)}</p>
        <p>writes_snapshot_cache / builds_missing_packets: {String(producerGenerationContract.writes_snapshot_cache ?? false)} / {String(producerGenerationContract.builds_missing_packets_in_current_cache ?? false)}</p>
        <p>provider_backed_long_window_acceptance_done / production_freshness_gate_complete: {String(producerGenerationContract.provider_backed_long_window_acceptance_done ?? false)} / {String(producerGenerationContract.production_freshness_gate_complete ?? false)}</p>
        <DataLineageTable rows={objectRow(producerGenerationContract)} />
        <DataLineageTable rows={rows(cache.current_evidence_producer_generation_rows)} />
      </PacketCard>

      <PacketCard title="Producer cache refresh 请求 ticket" subtitle="按钮生成本地 execution-request；绑定 readiness hash，不写 cache、不创建刷新任务" status={String(producerCacheRefreshRequest.status ?? producerCacheRefreshRequest.execution_request_status ?? "not_run")}>
        <div className="actions">
          <button onClick={launchProducerCacheRefreshExecutionRequest}>生成 producer refresh 请求 ticket</button>
        </div>
        <p>readiness status: {String(producerCacheRefreshReadiness.status ?? "--")}</p>
        <p>readiness scope hash: {String(producerCacheRefreshReadiness.readiness_scope_hash_short ?? "--")}</p>
        <p>request status: {String(producerCacheRefreshRequest.status ?? producerCacheRefreshRequest.execution_request_status ?? "not_run")}</p>
        <p>requested scope hash: {String(producerCacheRefreshRequest.requested_scope_hash_short ?? "--")}</p>
        <p>scope_hash_matches_readiness: {String(producerCacheRefreshRequest.scope_hash_matches_readiness === true)}</p>
        <p>ready_for_manual_local_refresh_task_submission: {String(producerCacheRefreshRequest.ready_for_manual_local_refresh_task_submission === true)}</p>
        <p>writes_snapshot_cache / creates_task / executes_local_refresh: {String(producerCacheRefreshRequest.writes_snapshot_cache ?? false)} / {String(producerCacheRefreshRequest.creates_task ?? false)} / {String(producerCacheRefreshRequest.executes_local_refresh ?? false)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(producerCacheRefreshRequest.tushare_called ?? false)} / {String(producerCacheRefreshRequest.deepseek_called ?? false)} / {String(producerCacheRefreshRequest.github_called ?? false)}</p>
        <p>provider_backed_long_window_acceptance_done / production_freshness_gate_complete: {String(producerCacheRefreshRequest.provider_backed_long_window_acceptance_done ?? false)} / {String(producerCacheRefreshRequest.production_freshness_gate_complete ?? false)}</p>
        <p>allowed_next_step: {String(producerCacheRefreshRequest.allowed_next_step ?? "--")}</p>
        <p>GET cache 只读取 latest request metadata；该 ticket 不刷新当前 cache、不构建缺失 packet、不证明 provider-backed freshness。</p>
        {producerCacheRefreshRequestError ? <p className="risk-note">{producerCacheRefreshRequestError}</p> : null}
        <TaskLaunchReceipt receipt={producerCacheRefreshRequestReceipt} />
        <DataLineageTable rows={objectRow(producerCacheRefreshReadiness)} />
        <DataLineageTable rows={rows(cache.current_evidence_producer_cache_refresh_rows)} />
        <DataLineageTable rows={objectRow(producerCacheRefreshRequest)} />
        <DataLineageTable rows={producerCacheRefreshRequestRows} />
        <JsonDetails title="latest producer cache refresh execution request raw" data={latestProducerCacheRefreshRequest} />
      </PacketCard>

      <PacketCard title="Trade_cal 本地文件验收" subtitle="只读已有 Parquet/DuckDB cache；不是页面启动外联" status={String(tradeCalPhysical.status ?? "local_trade_cal_validation")}>
        <p>如果本地 trade_cal Parquet 已存在，这里只读取 schema、日期窗口、开闭市行和当前日期覆盖；不会调用 Tushare，也不会写文件。</p>
        <p>通过只代表本地物理文件可用于 freshness 长窗口验收，不代表本次页面打开执行了 provider 刷新，也不代表 provider-backed acceptance。</p>
        <DataLineageTable rows={objectRow(tradeCalPhysical)} />
        <DataLineageTable rows={rows(cache.trade_cal_physical_validation_rows)} />
      </PacketCard>

      <PacketCard title="Trade_cal provider 验收 Runbook" subtitle="trade_cal_provider_acceptance_runbook；固定真实长窗口验收要求，不调用 Tushare" status={String(tradeCalProviderRunbook.status ?? "provider_acceptance_runbook")}>
        <p>provider_backed_long_window_acceptance_done: {String(tradeCalProviderRunbook.provider_backed_long_window_acceptance_done ?? false)}</p>
        <p>post_task_route: {String(tradeCalProviderRunbook.post_task_route ?? "POST /api/tasks/refresh-tushare-facts")}</p>
        <p>minimum_acceptance_window_days: {String(tradeCalProviderRunbook.minimum_acceptance_window_days ?? 730)}</p>
        <p>runbook 只固定 payload、call_ledger、schema、长窗口、失败模式、artifact promotion 和 current evidence 边界；真实 provider-backed 验收仍需后续显式按钮任务。</p>
        <DataLineageTable rows={objectRow(tradeCalProviderRunbook)} />
        <DataLineageTable rows={rows(cache.trade_cal_provider_acceptance_runbook_rows)} />
      </PacketCard>

      <PacketCard title="Trade_cal provider 验收 dry-run ticket" subtitle="按钮生成本地 scope ticket；不调用 Tushare、不写 Parquet、不完成验收" status={String(tradeCalDryRun.status ?? "not_run")}>
        <div className="actions">
          <button onClick={launchTradeCalDryRun}>生成 trade_cal 验收 ticket</button>
        </div>
        <p>status: {String(tradeCalDryRun.status ?? "not_run")}</p>
        <p>scope hash: {String(tradeCalDryRun.acceptance_scope_hash_short ?? "--")}</p>
        <p>window: {String(tradeCalDryRun.start_date ?? "--")} - {String(tradeCalDryRun.end_date ?? "--")} ({String(tradeCalDryRun.window_days ?? "--")} days)</p>
        <p>credential presence: {String((tradeCalDryRun.credential_presence_summary as Record<string, unknown> | undefined)?.status ?? "--")}</p>
        <p>provider_execution_implemented / production_freshness_gate_complete: {String(tradeCalDryRun.provider_execution_implemented ?? false)} / {String(tradeCalDryRun.production_freshness_gate_complete ?? false)}</p>
        <p>allowed_next_step: {String(tradeCalDryRun.allowed_next_step ?? "--")}</p>
        <p>latest_task_found: {String(latestTradeCalDryRun.latest_task_found === true)}</p>
        <p>latest task: {String(latestTradeCalDryRun.latest_task_id ?? "--")} / {String(latestTradeCalDryRun.latest_task_status ?? "--")} / {String(latestTradeCalDryRun.latest_task_current_step ?? "--")}</p>
        <p>GET cache 只读取本地 task metadata，不创建 dry-run、不调用 Tushare。</p>
        <p>dry-run 只绑定未来真实验收的范围；真实 Tushare call ledger、freshness replay、failure modes、redaction review 和 production promotion 仍未执行。</p>
        {tradeCalDryRunError ? <p className="risk-note">{tradeCalDryRunError}</p> : null}
        <TaskLaunchReceipt receipt={tradeCalDryRunReceipt} />
        <DataLineageTable rows={objectRow(tradeCalDryRun)} />
        <DataLineageTable rows={tradeCalDryRunRows} />
        <DataLineageTable rows={tradeCalDryRunCredentialRows} />
        <JsonDetails title="latest trade_cal provider acceptance dry-run raw" data={latestTradeCalDryRun} />
      </PacketCard>

      <PacketCard title="Trade_cal provider 验收提升审计" subtitle="trade_cal_provider_acceptance_promotion_audit；只读本地证据，不调用 Tushare" status={String(tradeCalPromotionAudit.status ?? "provider_acceptance_promotion")}>
        <p>promotion_ready: {String(tradeCalPromotionAudit.promotion_ready === true)}</p>
        <p>provider_evidence_from_prior_task: {String(tradeCalPromotionAudit.provider_evidence_from_prior_task === true)}</p>
        <p>explicit_promotion_marker_found: {String(tradeCalPromotionAudit.explicit_promotion_marker_found === true)}</p>
        <p>blocking_criterion_count: {String(tradeCalPromotionAudit.blocking_criterion_count ?? 0)}</p>
        <p>只有看到显式 provider call ledger、长窗口、schema、本地 artifact 交叉检查、freshness replay、失败模式和当前证据边界全部通过时，才允许把 trade_cal 验收从 pending 提升。</p>
        <DataLineageTable rows={objectRow(tradeCalPromotionAudit)} />
        <DataLineageTable rows={rows(cache.trade_cal_provider_acceptance_promotion_rows)} />
      </PacketCard>

      <PacketCard title="Freshness 生产 blocker 审计" subtitle="freshness_production_blocker_audit；汇总 LTG-01 剩余阻断项，不调用 provider" status={String(freshnessProductionBlockerAudit.status ?? "freshness_production_blockers")}>
        <p>production_ready: {String(freshnessProductionBlockerAudit.production_ready === true)}</p>
        <p>production_blocker_count: {String(freshnessProductionBlockerAudit.production_blocker_count ?? 0)}</p>
        <p>production_blockers: {String((freshnessProductionBlockerAudit.production_blockers as Array<unknown> | undefined)?.join(", ") ?? "--")}</p>
        <p>该审计只汇总 freshness matrix、长窗口样本、本地 trade_cal artifact、provider promotion、current evidence、decision surface 和 producer 覆盖的本地阻断项；它不刷新 Tushare、不重算分数、不修改 strategy action。</p>
        <DataLineageTable rows={objectRow(freshnessProductionBlockerAudit)} />
        <DataLineageTable rows={rows(cache.freshness_production_blocker_rows)} />
      </PacketCard>

      <PacketCard title="Freshness provider 准入回执" subtitle="freshness_provider_acceptance_readiness_receipt；说明下一步能否进入显式 provider 验收" status={String(freshnessProviderReadinessReceipt.status ?? "provider_acceptance_readiness")}>
        <p>ready_for_explicit_provider_task: {String(freshnessProviderReadinessReceipt.ready_for_explicit_provider_task === true)}</p>
        <p>allowed_next_step: {String(freshnessProviderReadinessReceipt.allowed_next_step ?? "--")}</p>
        <p>provider_backed_long_window_acceptance_done: {String(freshnessProviderReadinessReceipt.provider_backed_long_window_acceptance_done === true)}</p>
        <p>production_freshness_gate_complete: {String(freshnessProviderReadinessReceipt.production_freshness_gate_complete === true)}</p>
        <p>回执只汇总 runbook、promotion audit、生产 blocker、current evidence、decision surface 和 producer 覆盖的本地状态；不会调用 Tushare，不会把 fixture、Parquet 或 runbook 提升为真实验收。</p>
        <DataLineageTable rows={objectRow(freshnessProviderReadinessReceipt)} />
        <DataLineageTable rows={rows(cache.freshness_provider_acceptance_readiness_rows)} />
      </PacketCard>

      <PacketCard title="Freshness provider 启用回执" subtitle="freshness_provider_acceptance_activation_receipt；显式 provider 验收前的本地清单，不调用 Tushare" status={String(freshnessProviderActivationReceipt.status ?? "provider_acceptance_activation")}>
        <p>local_activation_receipt_ready: {String(freshnessProviderActivationReceipt.local_activation_receipt_ready === true)}</p>
        <p>ready_for_explicit_provider_task: {String(freshnessProviderActivationReceipt.ready_for_explicit_provider_task === true)}</p>
        <p>allowed_next_step: {String(freshnessProviderActivationReceipt.allowed_next_step ?? "explicit_post_task_trade_cal_provider_acceptance")}</p>
        <p>provider_acceptance_task_executed_by_receipt: {String(freshnessProviderActivationReceipt.provider_acceptance_task_executed_by_receipt ?? false)}</p>
        <p>provider_refresh_called_by_receipt / cache_get_external_calls / react_render_external_calls: {String(freshnessProviderActivationReceipt.provider_refresh_called_by_receipt ?? false)} / {String(freshnessProviderActivationReceipt.cache_get_external_calls ?? false)} / {String(freshnessProviderActivationReceipt.react_render_external_calls ?? false)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(freshnessProviderActivationReceipt.tushare_called ?? false)} / {String(freshnessProviderActivationReceipt.deepseek_called ?? false)} / {String(freshnessProviderActivationReceipt.github_called ?? false)}</p>
        <p>provider_backed_long_window_acceptance_done / production_freshness_gate_complete: {String(freshnessProviderActivationReceipt.provider_backed_long_window_acceptance_done ?? false)} / {String(freshnessProviderActivationReceipt.production_freshness_gate_complete ?? false)}</p>
        <p>missing_evidence_items: {Array.isArray(freshnessProviderActivationReceipt.missing_evidence_items) ? freshnessProviderActivationReceipt.missing_evidence_items.join(" / ") : "provider-backed trade_cal task execution / provider call ledger with safe fields / explicit production promotion marker"}</p>
        <p>not_allowed_next_steps: {Array.isArray(freshnessProviderActivationReceipt.not_allowed_next_steps) ? freshnessProviderActivationReceipt.not_allowed_next_steps.join(" / ") : "GET /api/data-health/cache provider refresh / React render provider refresh / activation receipt as production freshness completion"}</p>
        <DataLineageTable rows={objectRow(freshnessProviderActivationReceipt)} />
        <DataLineageTable rows={rows(cache.freshness_provider_acceptance_activation_rows)} />
        <DataLineageTable rows={rows(freshnessProviderActivationReceipt.call_ledger)} />
      </PacketCard>

      <PacketCard title="Trade_cal 下一次 provider 验收配方" subtitle="trade_cal_provider_acceptance_next_execution_recipe；只读说明下一次 POST 验收，不调用 Tushare" status={String(tradeCalNextExecutionRecipe.status ?? "provider_acceptance_next_execution_recipe")}>
        <p>recipe_ready_for_user_confirmation: {String(tradeCalNextExecutionRecipe.recipe_ready_for_user_confirmation === true)}</p>
        <p>requires_prior_dry_run_scope_ticket: {String(tradeCalNextExecutionRecipe.requires_prior_dry_run_scope_ticket !== false)}</p>
        <p>latest_dry_run_scope_ticket_visible: {String(tradeCalNextExecutionRecipe.latest_dry_run_scope_ticket_visible === true)}</p>
        <p>allowed_next_step: {String(tradeCalNextExecutionRecipe.allowed_next_step ?? "run_trade_cal_provider_acceptance_dry_run_scope_ticket")}</p>
        <p>target: {String(tradeCalNextExecutionRecipe.target_post_task_route ?? "POST /api/tasks/refresh-tushare-facts")} / {String(tradeCalNextExecutionRecipe.target_acceptance_mode ?? "provider_backed_trade_cal_long_window")}</p>
        <p>provider_refresh_called_by_recipe / ready_to_execute_from_cache: {String(tradeCalNextExecutionRecipe.provider_refresh_called_by_recipe ?? false)} / {String(tradeCalNextExecutionRecipe.ready_to_execute_from_cache ?? false)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(tradeCalNextExecutionRecipe.tushare_called ?? false)} / {String(tradeCalNextExecutionRecipe.deepseek_called ?? false)} / {String(tradeCalNextExecutionRecipe.github_called ?? false)}</p>
        <p>not_allowed_next_steps: {Array.isArray(tradeCalNextExecutionRecipe.not_allowed_next_steps) ? tradeCalNextExecutionRecipe.not_allowed_next_steps.join(" / ") : "GET cache provider refresh / React render provider refresh / skip dry-run scope ticket / skip user confirmation / promote recipe to provider-backed acceptance"}</p>
        <DataLineageTable rows={objectRow(tradeCalNextExecutionRecipe)} />
        <DataLineageTable rows={rows(cache.trade_cal_provider_acceptance_next_execution_rows)} />
      </PacketCard>

      <PacketCard title="Trade_cal provider 执行请求 ticket" subtitle="按钮生成本地 request；绑定 dry-run scope hash，不调用 Tushare、不创建 provider task" status={String(tradeCalExecutionRequest.status ?? "not_run")}>
        <div className="actions">
          <button onClick={launchTradeCalExecutionRequest}>生成执行请求 ticket</button>
        </div>
        <p>status: {String(tradeCalExecutionRequest.status ?? tradeCalExecutionRequest.execution_request_status ?? "not_run")}</p>
        <p>latest dry-run scope hash: {String(tradeCalExecutionRequest.latest_dry_run_scope_hash_short ?? "--")}</p>
        <p>requested scope hash: {String(tradeCalExecutionRequest.requested_scope_hash_short ?? "--")}</p>
        <p>scope_hash_matches_latest_dry_run: {String(tradeCalExecutionRequest.scope_hash_matches_latest_dry_run === true)}</p>
        <p>ready_for_manual_provider_task_submission: {String(tradeCalExecutionRequest.ready_for_manual_provider_task_submission === true)}</p>
        <p>ready_to_execute_from_cache / creates_provider_task: {String(tradeCalExecutionRequest.ready_to_execute_from_cache ?? false)} / {String(tradeCalExecutionRequest.creates_provider_task ?? false)}</p>
        <p>provider_task_executed_by_request / provider_execution_implemented: {String(tradeCalExecutionRequest.provider_task_executed_by_request ?? false)} / {String(tradeCalExecutionRequest.provider_execution_implemented ?? false)}</p>
        <p>provider_backed_long_window_acceptance_done / production_freshness_gate_complete: {String(tradeCalExecutionRequest.provider_backed_long_window_acceptance_done ?? false)} / {String(tradeCalExecutionRequest.production_freshness_gate_complete ?? false)}</p>
        <p>allowed_next_step: {String(tradeCalExecutionRequest.allowed_next_step ?? "--")}</p>
        <p>not_allowed_next_steps: {Array.isArray(tradeCalExecutionRequest.not_allowed_next_steps) ? tradeCalExecutionRequest.not_allowed_next_steps.join(" / ") : "GET cache provider refresh / React render provider refresh / execute provider from execution request ticket / promote execution request to provider-backed acceptance"}</p>
        <p>GET cache 只读取 latest execution request metadata；它不是 provider call ledger，也不是 LTG-01/02 生产验收完成。</p>
        {tradeCalExecutionRequestError ? <p className="risk-note">{tradeCalExecutionRequestError}</p> : null}
        <TaskLaunchReceipt receipt={tradeCalExecutionRequestReceipt} />
        <DataLineageTable rows={objectRow(tradeCalExecutionRequest)} />
        <DataLineageTable rows={tradeCalExecutionRequestRows} />
        <JsonDetails title="latest trade_cal provider acceptance execution request raw" data={latestTradeCalExecutionRequest} />
      </PacketCard>

      <PacketCard title="Tushare target-sample 执行请求 ticket" subtitle="Data Health 只读展示 latest target-sample request；不调用 Tushare、不创建 provider task" status={String(tushareTargetSampleExecutionRequest.status ?? tushareTargetSampleExecutionRequest.execution_request_status ?? "not_run")}>
        <p>status: {String(tushareTargetSampleExecutionRequest.status ?? tushareTargetSampleExecutionRequest.execution_request_status ?? "not_run")}</p>
        <p>latest task: {String(latestTushareTargetSampleExecutionRequest.latest_task_id ?? "--")} / {String(latestTushareTargetSampleExecutionRequest.latest_task_status ?? "--")} / {String(latestTushareTargetSampleExecutionRequest.latest_task_current_step ?? "--")}</p>
        <p>target route: {String(tushareTargetSampleExecutionRequest.target_post_task_route ?? "POST /api/tasks/refresh-tushare-facts")} / {String(tushareTargetSampleExecutionRequest.target_acceptance_mode ?? "provider_target_sample_acceptance")}</p>
        <p>requested targets: {Array.isArray(tushareTargetSampleExecutionRequest.requested_targets) ? tushareTargetSampleExecutionRequest.requested_targets.join(" / ") : "--"}</p>
        <p>selected APIs: {Array.isArray(tushareTargetSampleExecutionRequest.selected_apis) ? tushareTargetSampleExecutionRequest.selected_apis.join(" / ") : "--"}</p>
        <p>scope hash match / operator confirmation: {String(tushareTargetSampleExecutionRequest.execution_recipe_scope_hash_matches_latest === true)} / {String(tushareTargetSampleExecutionRequest.operator_confirmation_recorded === true)}</p>
        <p>ready_for_manual_provider_task_submission: {String(tushareTargetSampleExecutionRequest.ready_for_manual_provider_task_submission === true)}</p>
        <p>ready_to_execute_from_cache / creates_provider_task: {String(tushareTargetSampleExecutionRequest.ready_to_execute_from_cache ?? false)} / {String(tushareTargetSampleExecutionRequest.creates_provider_task ?? false)}</p>
        <p>provider_task_executed_by_request / provider_execution_implemented: {String(tushareTargetSampleExecutionRequest.provider_task_executed_by_request ?? false)} / {String(tushareTargetSampleExecutionRequest.provider_execution_implemented ?? false)}</p>
        <p>provider_backed_target_sample_acceptance_done / full_interface_acceptance_done: {String(tushareTargetSampleExecutionRequest.provider_backed_target_sample_acceptance_done ?? false)} / {String(tushareTargetSampleExecutionRequest.full_interface_acceptance_done ?? false)}</p>
        <p>production_tushare_pipeline_complete: {String(tushareTargetSampleExecutionRequest.production_tushare_pipeline_complete ?? false)}</p>
        <p>cache_get_external_calls / react_render_external_calls: {String(tushareTargetSampleExecutionRequest.cache_get_external_calls ?? false)} / {String(tushareTargetSampleExecutionRequest.react_render_external_calls ?? false)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(tushareTargetSampleExecutionRequest.tushare_called ?? false)} / {String(tushareTargetSampleExecutionRequest.deepseek_called ?? false)} / {String(tushareTargetSampleExecutionRequest.github_called ?? false)}</p>
        <p>GET cache 只读取 latest Tushare target-sample execution request metadata；它不是 provider call ledger，也不是 LTG-02 provider-backed target-sample acceptance。</p>
        <DataLineageTable rows={objectRow(tushareTargetSampleExecutionRequest)} />
        <DataLineageTable rows={tushareTargetSampleExecutionRequestRows} />
        <JsonDetails title="latest Tushare target-sample execution request raw" data={latestTushareTargetSampleExecutionRequest} />
      </PacketCard>

      <PacketCard title="Freshness durable evidence recipe" subtitle="LTG-01 生产验收证据配方；固定 provider trade_cal 直接证据清单，不调用 Tushare" status={String(freshnessDurableEvidenceRecipe.status ?? "freshness_durable_evidence_recipe_not_loaded")}>
        <p>schema_version: {String(freshnessDurableEvidenceRecipe.schema_version ?? "data_health_freshness_durable_evidence_recipe.v1")}</p>
        <p>scope: {String(freshnessDurableEvidenceRecipe.scope ?? "local_freshness_durable_evidence_recipe_no_provider_execution")}</p>
        <p>local_recipe_ready: {String(freshnessDurableEvidenceRecipe.local_recipe_ready ?? false)}</p>
        <p>durable_evidence_complete / durable_promotion_ready: {String(freshnessDurableEvidenceRecipe.durable_evidence_complete ?? false)} / {String(freshnessDurableEvidenceRecipe.durable_promotion_ready ?? false)}</p>
        <p>provider_backed_trade_cal_acceptance_done / production_freshness_gate_complete: {String(freshnessDurableEvidenceRecipe.provider_backed_trade_cal_acceptance_done ?? false)} / {String(freshnessDurableEvidenceRecipe.production_freshness_gate_complete ?? false)}</p>
        <p>real_trade_cal_long_window_validation_done / provider_execution_implemented: {String(freshnessDurableEvidenceRecipe.real_trade_cal_long_window_validation_done ?? false)} / {String(freshnessDurableEvidenceRecipe.provider_execution_implemented ?? false)}</p>
        <p>durable_evidence_blocker_count: {String(freshnessDurableEvidenceRecipe.durable_evidence_blocker_count ?? 0)}</p>
        <p>blocking_evidence_keys: {Array.isArray(freshnessDurableEvidenceRecipe.blocking_evidence_keys) ? freshnessDurableEvidenceRecipe.blocking_evidence_keys.join(" / ") : "explicit_provider_trade_cal_task / safe_provider_call_ledger / provider_freshness_replay / provider_failure_mode_evidence / current_evidence_producer_coverage / decision_surface_isolation / production_promotion_review"}</p>
        <p>allowed_next_step: {String(freshnessDurableEvidenceRecipe.allowed_next_step ?? "collect_direct_trade_cal_provider_call_ledger_replay_failure_mode_and_promotion_evidence")}</p>
        <p>not_allowed_next_steps: {Array.isArray(freshnessDurableEvidenceRecipe.not_allowed_next_steps) ? freshnessDurableEvidenceRecipe.not_allowed_next_steps.join(" / ") : "treat durable recipe as provider-backed trade_cal acceptance / treat dry-run scope ticket as provider execution / treat synthetic replay as provider replay / treat local trade_cal artifact as provider acceptance / set production_freshness_gate_complete from cache/render"}</p>
        <p>provider_refresh_called_by_recipe / cache_get_external_calls / react_render_external_calls: {String(freshnessDurableEvidenceRecipe.provider_refresh_called_by_recipe ?? false)} / {String(freshnessDurableEvidenceRecipe.cache_get_external_calls ?? false)} / {String(freshnessDurableEvidenceRecipe.react_render_external_calls ?? false)}</p>
        <p>tushare_called / deepseek_called / github_called: {String(freshnessDurableEvidenceRecipe.tushare_called ?? false)} / {String(freshnessDurableEvidenceRecipe.deepseek_called ?? false)} / {String(freshnessDurableEvidenceRecipe.github_called ?? false)}</p>
        <DataLineageTable rows={freshnessDurableEvidenceRows} />
        <DataLineageTable rows={rows(freshnessDurableEvidenceRecipe.call_ledger)} />
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
