import { useEffect, useState } from "react";
import { getLegacyBridgeCache } from "../api/client";
import PacketCard from "../components/PacketCard";
import MetricGrid from "../components/MetricGrid";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import PageStateBanner from "../components/PageStateBanner";

const LEGACY_BOUNDARIES = [
  { boundary: "正式主入口", status: "Command Center 3 React/Tauri", note: "普通主流程请使用 3.0 前端和 FastAPI cache/task API。" },
  { boundary: "Streamlit 定位", status: "legacy/admin/debug", note: "保留用于回退、排查、旧功能兼容和管理操作。" },
  { boundary: "外部请求", status: "button_gated", note: "Tushare、DeepSeek、GitHub 校验不得在旧入口启动时自动触发。" },
  { boundary: "任务路径", status: "FastAPI task pipeline", note: "重计算应逐步迁移到 POST task，并写入 call_ledger。" },
  { boundary: "真实交易", status: "disabled", note: "不执行真实交易，不自动下单，不绕过 strategy_execution_packet。" },
  { boundary: "功能保留", status: "no feature cuts", note: "旧工作台功能保留到 3.0 页面/API 等价迁移完成。" }
];

const LEGACY_ALLOWED_USES = [
  { use_case: "旧功能回退", allowed: true, route: "app.py", guard: "legacy/admin/debug only" },
  { use_case: "开发调试", allowed: true, route: "app.py", guard: "不绕过按钮门控" },
  { use_case: "管理与诊断", allowed: true, route: "app.py", guard: "不自动外联" },
  { use_case: "普通主流程", allowed: false, route: "React/Tauri", guard: "迁往 Command Center 3" },
  { use_case: "真实交易", allowed: false, route: "none", guard: "永不自动触发" }
];

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function objectRow(value: unknown): Array<Record<string, unknown>> {
  return value && typeof value === "object" && !Array.isArray(value) ? [value as Record<string, unknown>] : [];
}

export default function LegacyTools() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    void getLegacyBridgeCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
      if (!res.ok) setError(res.error ?? "legacy_cache_not_ok");
    }).catch((err) => {
      setError(err instanceof Error ? err.message : String(err));
    }).finally(() => setLoading(false));
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const capability = (cache.old_workspace_capability_overview as Record<string, unknown> | undefined) ?? {};
  const absence = (cache.old_workspace_data_absence_ledger as Record<string, unknown> | undefined) ?? {};
  const bridge = (cache.old_workspace_packet_bridge as Record<string, unknown> | undefined) ?? {};
  const primaryExitAudit = (cache.primary_workflow_exit_audit as Record<string, unknown> | undefined) ?? {};
  const primaryExitRows = rows(cache.primary_workflow_exit_rows);
  const primaryWorkflowRouteRows = rows(cache.primary_workflow_route_rows);
  const fallbackDependencyContract = (cache.streamlit_fallback_dependency_contract as Record<string, unknown> | undefined) ?? {};
  const fallbackDependencyRows = rows(cache.streamlit_fallback_dependency_rows);
  const streamlitRetirementReadinessReceipt = (cache.streamlit_retirement_readiness_receipt as Record<string, unknown> | undefined) ?? {};
  const streamlitRetirementReadinessRows = rows(cache.streamlit_retirement_readiness_rows);
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);
  const empty = !loading && !error && !Object.keys(cache).length;

  return (
    <>
      <PacketCard title="Legacy / Admin / Debug" subtitle="Streamlit 2.0 保留为 legacy，不再作为正式主应用" status="legacy">
        <PageStateBanner
          loading={loading}
          error={error}
          empty={empty}
          emptyTitle="暂无 Legacy 桥接缓存"
          emptyDetail="Legacy 页面只读展示旧工作台边界，不启动 Streamlit 或运行旧工具。"
        />
        <MetricGrid
          items={[
            { label: "正式入口", value: "Command Center 3" },
            { label: "Streamlit", value: "legacy/admin/debug" },
            { label: "Streamlit 主入口", value: policy.streamlit_is_official_primary_entry === true ? "仍是" : "不是", tone: policy.streamlit_is_official_primary_entry === true ? "bad" : "good" },
            { label: "启动创建任务", value: policy.legacy_startup_task_creation === true ? "会" : "不会", tone: policy.legacy_startup_task_creation === true ? "bad" : "good" },
            { label: "绕过 guard", value: policy.legacy_can_bypass_guardrails === true ? "可能" : "禁止", tone: policy.legacy_can_bypass_guardrails === true ? "bad" : "good" },
            { label: "bridge status", value: String(cache.status ?? "cache") },
            { label: "checklist", value: `${String(counts.checklist_done_count ?? 0)} / ${String(counts.checklist_pending_count ?? 0)}` },
            { label: "bridge items", value: counts.bridge_item_count as number | undefined },
            { label: "absence items", value: counts.absence_item_count as number | undefined },
            { label: "exit audit", value: primaryExitAudit.status as string | undefined, tone: primaryExitAudit.ordinary_workflow_exit_complete === true ? "good" : "warn" },
            { label: "exit complete", value: primaryExitAudit.ordinary_workflow_exit_complete === true ? "完成" : "未完成", tone: primaryExitAudit.ordinary_workflow_exit_complete === true ? "good" : "warn" },
            { label: "fallback rows", value: primaryExitAudit.ordinary_workflow_still_needs_fallback_count as number | undefined, tone: Number(primaryExitAudit.ordinary_workflow_still_needs_fallback_count ?? 0) > 0 ? "warn" : "good" },
            { label: "exit blockers", value: primaryExitAudit.blocker_count as number | undefined, tone: Number(primaryExitAudit.blocker_count ?? 0) > 0 ? "warn" : "good" },
            { label: "fallback deps", value: fallbackDependencyContract.full_streamlit_removal_blocker_count ?? counts.streamlit_fallback_dependency_count, tone: Number(fallbackDependencyContract.full_streamlit_removal_blocker_count ?? counts.streamlit_fallback_dependency_count ?? 0) > 0 ? "warn" : "good" },
            { label: "ordinary deps", value: fallbackDependencyContract.ordinary_fallback_dependency_count ?? counts.ordinary_fallback_dependency_count, tone: Number(fallbackDependencyContract.ordinary_fallback_dependency_count ?? counts.ordinary_fallback_dependency_count ?? 0) > 0 ? "warn" : "good" },
            { label: "retirement receipt", value: streamlitRetirementReadinessReceipt.local_receipt_ready === true ? "ready" : "review", tone: streamlitRetirementReadinessReceipt.local_receipt_ready === true ? "good" : "warn" },
            { label: "retirement blockers", value: streamlitRetirementReadinessReceipt.blocking_criterion_count ?? counts.streamlit_retirement_readiness_blocker_count, tone: Number(streamlitRetirementReadinessReceipt.blocking_criterion_count ?? counts.streamlit_retirement_readiness_blocker_count ?? 0) > 0 ? "warn" : "good" },
            { label: "普通主流程", value: "迁往 React/Tauri", tone: "good" },
            { label: "自动外联", value: "禁止", tone: "good" },
            { label: "真实交易", value: "禁止", tone: "good" },
            { label: "自动下单", value: "禁止", tone: "good" },
            { label: "cache envelope ledger", value: cacheEnvelopeLedger.length },
            { label: "cache warnings", value: cacheWarnings.length }
          ]}
        />
        <p>旧版 Streamlit 入口仍保留在 app.py，用于排查、管理、旧功能回退和阶段性兼容。</p>
        <p>普通主流程请使用 Command Center 3；3.0 正式主路径会逐步迁移到 React + FastAPI + Tauri。</p>
        <p>Streamlit 不是正式主入口；Legacy 页面不会创建任务，不调用 Tushare、DeepSeek 或 GitHub，也不会打开 Streamlit 或运行旧工具。</p>
        <p>GET /api/legacy/cache 只读展示旧工作台桥接和迁移清单，不会绕过 strategy_execution_packet。</p>
      </PacketCard>

      <PacketCard title="旧工作台桥接 cache" subtitle="old_workspace_packet_bridge / legacy_packet_migration_checklist" status={String(cache.status ?? "cache")}>
        <p>{String(cache.summary ?? "旧工作台桥接 cache 只读展示。")}</p>
        <p>local_legacy_bridge_cache 只读取 legacy_migration_map、legacy_packet_migration_checklist、old_workspace_packet_bridge 等本地字段。</p>
        <DataLineageTable rows={objectRow(bridge)} />
      </PacketCard>

      <PacketCard title="Legacy 边界" subtitle="旧入口保留，但不得重新成为主路径" status="read_only">
        <DataLineageTable rows={LEGACY_BOUNDARIES} />
      </PacketCard>

      <PacketCard title="Legacy Policy" subtitle="Streamlit 退出普通主流程；React/Tauri 为正式入口" status="policy">
        <DataLineageTable rows={objectRow(policy)} />
      </PacketCard>

      <PacketCard title="Streamlit 主流程退出审计" subtitle="本地 route inventory；不打开 Streamlit" status={String(primaryExitAudit.status ?? "ordinary_workflow_exit_partial_fallback_required")}>
        <p>scope: {String(primaryExitAudit.scope ?? "local_legacy_policy_and_route_inventory_not_streamlit_execution")}</p>
        <p>ordinary_workflow_exit_complete: {String(primaryExitAudit.ordinary_workflow_exit_complete ?? false)}</p>
        <p>streamlit_fallback_retained: {String(primaryExitAudit.streamlit_fallback_retained ?? true)}</p>
        <p>streamlit_fallback_removal_ready: {String(primaryExitAudit.streamlit_fallback_removal_ready ?? false)}</p>
        <p>ordinary_workflow_still_needs_fallback_count: {String(primaryExitAudit.ordinary_workflow_still_needs_fallback_count ?? 0)}</p>
        <p>blocker_count: {String(primaryExitAudit.blocker_count ?? 0)}</p>
      </PacketCard>

      <PacketCard title="Streamlit 退出审计明细" subtitle="安全边界通过项与仍需保留 fallback 的阻断项" status="exit_audit">
        <DataLineageTable rows={primaryExitRows} />
      </PacketCard>

      <PacketCard title="普通主流程迁移覆盖" subtitle="Command Center 3 route coverage；partial/fallback 必须明示" status="route_inventory">
        <DataLineageTable rows={primaryWorkflowRouteRows} />
      </PacketCard>

      <PacketCard title="Streamlit fallback 依赖契约" subtitle="逐项说明哪些普通工作流仍依赖旧入口；不打开 Streamlit、不执行旧工具" status={String(fallbackDependencyContract.status ?? "streamlit_fallback_dependencies_visible_retirement_pending")}>
        <p>scope: {String(fallbackDependencyContract.scope ?? "local_route_dependency_contract_not_streamlit_execution")}</p>
        <p>ordinary_primary_exit_ready: {String(fallbackDependencyContract.ordinary_primary_exit_ready ?? false)}</p>
        <p>full_streamlit_removal_ready: {String(fallbackDependencyContract.full_streamlit_removal_ready ?? false)}</p>
        <p>ordinary_fallback_dependency_count: {String(fallbackDependencyContract.ordinary_fallback_dependency_count ?? 0)}</p>
        <p>full_streamlit_removal_blocker_count: {String(fallbackDependencyContract.full_streamlit_removal_blocker_count ?? 0)}</p>
        <DataLineageTable rows={fallbackDependencyRows} />
      </PacketCard>

      <PacketCard title="Streamlit retirement readiness receipt" subtitle="LTG-10 下一步收据；只能进入显式 parity / fallback retirement review" status={String(streamlitRetirementReadinessReceipt.status ?? "streamlit_retirement_receipt_ready_fallback_blocked")}>
        <p>schema_version: {String(streamlitRetirementReadinessReceipt.schema_version ?? "streamlit_retirement_readiness_receipt.v1")}</p>
        <p>scope: {String(streamlitRetirementReadinessReceipt.scope ?? "local_streamlit_retirement_readiness_receipt_no_streamlit_execution")}</p>
        <p>local_receipt_ready: {String(streamlitRetirementReadinessReceipt.local_receipt_ready ?? true)}</p>
        <p>ready_for_ordinary_primary_exit_review / ready_for_full_streamlit_retirement_review: {String(streamlitRetirementReadinessReceipt.ready_for_ordinary_primary_exit_review ?? false)} / {String(streamlitRetirementReadinessReceipt.ready_for_full_streamlit_retirement_review ?? false)}</p>
        <p>ordinary_workflow_exit_complete / full_streamlit_removal_ready: {String(streamlitRetirementReadinessReceipt.ordinary_workflow_exit_complete ?? false)} / {String(streamlitRetirementReadinessReceipt.full_streamlit_removal_ready ?? false)}</p>
        <p>streamlit_fallback_retained: {String(streamlitRetirementReadinessReceipt.streamlit_fallback_retained ?? true)}</p>
        <p>allowed_next_step: {String(streamlitRetirementReadinessReceipt.allowed_next_step ?? "explicit_replacement_parity_review_then_streamlit_fallback_retirement_review")}</p>
        <p>ordinary_blocking_workflows: {Array.isArray(streamlitRetirementReadinessReceipt.ordinary_blocking_workflows) ? streamlitRetirementReadinessReceipt.ordinary_blocking_workflows.join(" / ") : "candidate_radar_quick_scan"}</p>
        <p>full_removal_blocking_workflows: {Array.isArray(streamlitRetirementReadinessReceipt.full_removal_blocking_workflows) ? streamlitRetirementReadinessReceipt.full_removal_blocking_workflows.join(" / ") : "legacy_admin_debug_tools"}</p>
        <p>streamlit_opened_by_receipt / legacy_tools_run_by_receipt / tasks_created_by_receipt: {String(streamlitRetirementReadinessReceipt.streamlit_opened_by_receipt ?? false)} / {String(streamlitRetirementReadinessReceipt.legacy_tools_run_by_receipt ?? false)} / {String(streamlitRetirementReadinessReceipt.tasks_created_by_receipt ?? false)}</p>
        <p>fallback_removed_by_receipt / app_py_deleted_by_receipt: {String(streamlitRetirementReadinessReceipt.fallback_removed_by_receipt ?? false)} / {String(streamlitRetirementReadinessReceipt.app_py_deleted_by_receipt ?? false)}</p>
        <p>receipt_external_calls_triggered / tushare_called / deepseek_called / github_called: {String(streamlitRetirementReadinessReceipt.receipt_external_calls_triggered ?? false)} / {String(streamlitRetirementReadinessReceipt.tushare_called ?? false)} / {String(streamlitRetirementReadinessReceipt.deepseek_called ?? false)} / {String(streamlitRetirementReadinessReceipt.github_called ?? false)}</p>
        <p>not_allowed_next_steps: {Array.isArray(streamlitRetirementReadinessReceipt.not_allowed_next_steps) ? streamlitRetirementReadinessReceipt.not_allowed_next_steps.join(" / ") : "GET /api/legacy/cache opens Streamlit / page render retires Streamlit fallback / delete app.py before replacement parity or explicit retirement decision / treat local receipt as Streamlit retirement completion"}</p>
        <DataLineageTable rows={streamlitRetirementReadinessRows} />
        <DataLineageTable rows={rows(streamlitRetirementReadinessReceipt.call_ledger)} />
      </PacketCard>

      <PacketCard title="允许用途" subtitle="回退和调试可保留，普通主流程逐步迁出" status="guarded">
        <DataLineageTable rows={LEGACY_ALLOWED_USES} />
      </PacketCard>

      <PacketCard title="迁移清单" subtitle="legacy_packet_migration_checklist；只读，不执行迁移任务" status="checklist">
        <DataLineageTable rows={rows(cache.checklist_items)} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="迁移地图" subtitle="legacy_migration_map；只读 lanes/items" status="migration">
          <DataLineageTable rows={[...rows(cache.migration_lanes), ...rows(cache.migration_items)]} />
        </PacketCard>
        <PacketCard title="旧能力概览" subtitle="old_workspace_capability_overview" status={String(capability.status ?? "capability")}>
          <DataLineageTable rows={rows(cache.capability_items)} />
        </PacketCard>
      </div>

      <div className="grid">
        <PacketCard title="旧数据缺失账本" subtitle="old_workspace_data_absence_ledger；只读缺口" status={String(absence.status ?? "absence")}>
          <DataLineageTable rows={rows(cache.absence_items)} />
        </PacketCard>
        <PacketCard title="旧 A 股恢复动作" subtitle="legacy_a_share_fact_recovery_actions；不执行旧工具" status="legacy_recovery">
          <DataLineageTable rows={rows(cache.fact_recovery_action_rows)} />
        </PacketCard>
      </div>

      <PacketCard title="旧决策链摘要" subtitle="legacy_decision_chain_summary；不重算 action" status="decision_chain">
        <DataLineageTable rows={rows(cache.decision_chain_items)} />
      </PacketCard>

      <PacketCard title="API / 任务边界" subtitle="cache API 永不外联；迁移工作必须走后续按钮任务" status="policy">
        <p>GET /api/legacy/cache 不调用 Tushare、DeepSeek 或 GitHub，不打开 Streamlit，不运行旧工具。</p>
        <p>不执行真实交易，不自动下单，不修改 strategy action 或持仓；旧桥接不是交易指令。</p>
        <DataLineageTable rows={[policy]} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="payload 内部 local_legacy_bridge_cache；不外联、不写回" status="lineage">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET legacy envelope call_ledger" subtitle="GET /api/legacy/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheEnvelopeLedger} />
      </PacketCard>

      <PacketCard title="GET legacy envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={cacheWarnings.map((warning, index) => ({ index: index + 1, warning }))} />
      </PacketCard>

      <PacketCard title="原始 legacy bridge cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="legacy bridge cache raw" data={cache} />
        <JsonDetails title="streamlit retirement readiness receipt raw" data={streamlitRetirementReadinessReceipt} />
      </PacketCard>
    </>
  );
}
