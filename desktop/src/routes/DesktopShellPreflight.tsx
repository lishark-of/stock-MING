import { useEffect, useState } from "react";
import { getDesktopPreflightCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

export default function DesktopShellPreflight() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);

  useEffect(() => {
    void getDesktopPreflightCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const runtime = (cache.runtime as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const apiBaseInfo = (cache.api_base_info as Record<string, unknown> | undefined) ?? {};
  const productionReadiness = (cache.production_readiness as Record<string, unknown> | undefined) ?? {};
  const productionBlockerAudit = (cache.production_blocker_audit as Record<string, unknown> | undefined) ?? {};
  const devLaunchPlan = rows(cache.dev_launch_plan);
  const productionLaunchPlan = rows(cache.production_launch_plan);
  const productionBlockerRows = rows(cache.production_blocker_rows);
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);

  return (
    <>
      <div className="page-head">
        <h1>桌面壳预检</h1>
        <StatusBadge label={String(cache.status ?? "cache_missing")} tone={cache.status === "ready" ? "good" : "warn"} />
      </div>

      <MetricGrid
        items={[
          { label: "mode", value: cache.mode as string | undefined },
          { label: "API base", value: String(cache.api_base ?? "--") },
          { label: "API localhost", value: apiBaseInfo.is_localhost === true ? "yes" : "check", tone: apiBaseInfo.is_localhost === true ? "good" : "warn" },
          { label: "required files", value: `${String(counts.required_file_ready_count ?? 0)} / ${String(counts.required_file_count ?? 0)}` },
          { label: "Node/npm", value: runtime.node_ready === true ? "ready" : "missing", tone: runtime.node_ready === true ? "good" : "warn" },
          { label: "Rust/Cargo", value: runtime.rust_ready === true ? "ready" : "missing", tone: runtime.rust_ready === true ? "good" : "warn" },
          { label: "Vite dev", value: runtime.vite_dev_ready === true ? "ready" : "blocked", tone: runtime.vite_dev_ready === true ? "good" : "warn" },
          { label: "Tauri dev", value: runtime.tauri_dev_ready === true ? "ready" : "needs Rust", tone: runtime.tauri_dev_ready === true ? "good" : "warn" },
          { label: "node_modules", value: runtime.node_modules_present === true ? "present" : "missing", tone: runtime.node_modules_present === true ? "good" : "warn" },
          { label: "dist", value: runtime.dist_present === true ? "present" : "missing" },
          { label: "backend autostart", value: runtime.backend_autostart_configured === true ? "enabled" : "manual", tone: runtime.backend_autostart_configured === true ? "warn" : "good" },
          { label: "package audit", value: productionBlockerAudit.status as string | undefined, tone: productionBlockerAudit.package_ready === true ? "good" : "warn" },
          { label: "package ready", value: productionBlockerAudit.package_ready === true ? "ready" : "blocked", tone: productionBlockerAudit.package_ready === true ? "good" : "warn" },
          { label: "tauri build", value: productionBlockerAudit.tauri_build_verified === true ? "verified" : "not verified", tone: productionBlockerAudit.tauri_build_verified === true ? "good" : "warn" },
          { label: "package blockers", value: productionBlockerAudit.blocker_count as number | undefined, tone: Number(productionBlockerAudit.blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheEnvelopeLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="桌面壳边界" subtitle="GET /api/desktop/preflight-cache 只读检查本地 scaffold" status="cache_only">
          <p>本页只读取 FastAPI desktop preflight cache，不运行 npm install、npm build、cargo 或 Tauri。</p>
          <p>不会调用 Tushare、DeepSeek 或 GitHub，不读取 token/key，不执行真实交易，不修改 strategy action。</p>
          <p>Rust/Cargo 缺失只影响 Tauri dev/build；Vite 前端和 FastAPI cache API 仍可继续推进。</p>
          <p>开发模式当前不会自动拉起 FastAPI：先运行 scripts/dev_server.sh，再运行 Vite 或 Tauri dev。</p>
        </PacketCard>

        <PacketCard title="预检策略" subtitle="cache API 永不外联；构建命令必须人工触发" status="policy">
          <p>does_not_run_npm_install: {String(policy.does_not_run_npm_install ?? true)}</p>
          <p>does_not_run_npm_build: {String(policy.does_not_run_npm_build ?? true)}</p>
          <p>does_not_run_tauri: {String(policy.does_not_run_tauri ?? true)}</p>
          <p>does_not_run_cargo: {String(policy.does_not_run_cargo ?? true)}</p>
          <p>frontend_must_use_fastapi_api_client: {String(policy.frontend_must_use_fastapi_api_client ?? true)}</p>
          <p>backend_autostart_enabled: {String(policy.backend_autostart_enabled ?? false)}</p>
          <p>api_base_must_be_localhost: {String(policy.api_base_must_be_localhost ?? true)}</p>
        </PacketCard>
      </div>

      <PacketCard title="开发启动顺序" subtitle="手动启动 FastAPI、Vite、Tauri；预检页不执行命令" status="manual">
        <DataLineageTable rows={devLaunchPlan} />
      </PacketCard>

      <PacketCard title="生产打包路线" subtitle="只展示命令顺序；本页不运行 build 或 Tauri" status="manual">
        <DataLineageTable rows={productionLaunchPlan} />
      </PacketCard>

      <PacketCard title="Tauri 生产包阻断审计" subtitle="preflight 不是 production package complete" status={String(productionBlockerAudit.status ?? "production_package_blocked")}>
        <p>scope: {String(productionBlockerAudit.scope ?? "local_preflight_not_tauri_build")}</p>
        <p>package_ready: {String(productionBlockerAudit.package_ready ?? false)}</p>
        <p>tauri_build_verified: {String(productionBlockerAudit.tauri_build_verified ?? false)}</p>
        <p>manual_backend_launch_required: {String(productionBlockerAudit.manual_backend_launch_required ?? true)}</p>
        <p>backend_offline_ui_packaged_runtime_verified: {String(productionBlockerAudit.backend_offline_ui_packaged_runtime_verified ?? false)}</p>
        <p>config_log_paths_declared: {String(productionBlockerAudit.config_log_paths_declared ?? false)}</p>
        <p>macos_signing_notarization_ready: {String(productionBlockerAudit.macos_signing_notarization_ready ?? false)}</p>
        <p>production_readiness_status: {String(productionReadiness.status ?? "desktop_scaffold_partial")}</p>
      </PacketCard>

      <PacketCard title="Tauri 生产包阻断项" subtitle="逐项说明 dev/preflight 与 production package 的缺口" status="blockers">
        <DataLineageTable rows={productionBlockerRows} />
      </PacketCard>

      <PacketCard title="FastAPI 地址合同" subtitle="前端只连接本地 FastAPI，不保存 token/key" status={String(apiBaseInfo.is_localhost === true ? "localhost" : "review")}>
        <DataLineageTable rows={Object.entries(apiBaseInfo).map(([field, value]) => ({ field, value: String(value) }))} />
      </PacketCard>

      <PacketCard title="Scaffold 文件" subtitle="React/Vite/Tauri 必要文件是否存在" status="files">
        <DataLineageTable rows={rows(cache.file_rows)} />
      </PacketCard>

      <PacketCard title="本地命令可见性" subtitle="只检查命令是否存在，不运行 --version / build / dev" status="commands">
        <DataLineageTable rows={rows(cache.command_rows)} />
      </PacketCard>

      <PacketCard title="调用血缘" subtitle="payload 内部 local_desktop_shell_preflight_cache；不外联" status="lineage">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET desktop preflight envelope call_ledger" subtitle="GET /api/desktop/preflight-cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheEnvelopeLedger} />
      </PacketCard>

      <PacketCard title="GET desktop preflight envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={cacheWarnings.map((warning, index) => ({ index: index + 1, warning }))} />
      </PacketCard>

      <PacketCard title="原始 desktop preflight cache payload" subtitle="调试用 JSON；不含 token/key" status="safe">
        <JsonDetails title="desktop shell preflight raw" data={cache} />
      </PacketCard>
    </>
  );
}
