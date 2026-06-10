import { useEffect, useState } from "react";
import { getLegacyBridgeCache } from "../api/client";
import PacketCard from "../components/PacketCard";
import MetricGrid from "../components/MetricGrid";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";

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

  useEffect(() => {
    void getLegacyBridgeCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const capability = (cache.old_workspace_capability_overview as Record<string, unknown> | undefined) ?? {};
  const absence = (cache.old_workspace_data_absence_ledger as Record<string, unknown> | undefined) ?? {};
  const bridge = (cache.old_workspace_packet_bridge as Record<string, unknown> | undefined) ?? {};
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);

  return (
    <>
      <PacketCard title="Legacy / Admin / Debug" subtitle="Streamlit 2.0 保留为 legacy，不再作为正式主应用" status="legacy">
        <MetricGrid
          items={[
            { label: "正式入口", value: "Command Center 3" },
            { label: "Streamlit", value: "legacy/admin/debug" },
            { label: "bridge status", value: String(cache.status ?? "cache") },
            { label: "checklist", value: `${String(counts.checklist_done_count ?? 0)} / ${String(counts.checklist_pending_count ?? 0)}` },
            { label: "bridge items", value: counts.bridge_item_count as number | undefined },
            { label: "absence items", value: counts.absence_item_count as number | undefined },
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
        <p>Legacy 页面不会创建任务，不调用 Tushare、DeepSeek 或 GitHub，也不会打开 Streamlit 或运行旧工具。</p>
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
      </PacketCard>
    </>
  );
}
