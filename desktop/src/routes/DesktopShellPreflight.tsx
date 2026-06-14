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
  const tauriBuildArtifact = (cache.tauri_build_artifact as Record<string, unknown> | undefined) ?? {};
  const productionReadiness = (cache.production_readiness as Record<string, unknown> | undefined) ?? {};
  const productionRuntimeContract = (cache.production_runtime_contract as Record<string, unknown> | undefined) ?? {};
  const backendOfflineUxContract = (cache.backend_offline_ux_contract as Record<string, unknown> | undefined) ?? {};
  const productionBlockerAudit = (cache.production_blocker_audit as Record<string, unknown> | undefined) ?? {};
  const packagedRuntimeQaContract = (cache.packaged_runtime_qa_contract as Record<string, unknown> | undefined) ?? {};
  const tauriReleaseManifestContract = (cache.tauri_release_manifest_contract as Record<string, unknown> | undefined) ?? {};
  const productionPackageReadinessReceipt = (cache.production_package_readiness_receipt as Record<string, unknown> | undefined) ?? {};
  const devLaunchPlan = rows(cache.dev_launch_plan);
  const productionLaunchPlan = rows(cache.production_launch_plan);
  const productionRuntimeRows = rows(cache.production_runtime_contract_rows);
  const backendOfflineUxRows = rows(cache.backend_offline_ux_rows);
  const productionBlockerRows = rows(cache.production_blocker_rows);
  const packagedRuntimeQaRows = rows(cache.packaged_runtime_qa_rows);
  const tauriReleaseManifestRows = rows(cache.tauri_release_manifest_rows);
  const productionPackageReadinessReceiptRows = rows(cache.production_package_readiness_receipt_rows);
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
          { label: "release binary", value: tauriBuildArtifact.binary_exists === true ? "detected" : "missing", tone: tauriBuildArtifact.binary_exists === true ? "good" : "warn" },
          { label: "binary executable", value: tauriBuildArtifact.binary_executable === true ? "yes" : "no", tone: tauriBuildArtifact.binary_executable === true ? "good" : "warn" },
          { label: "binary kind", value: tauriBuildArtifact.binary_kind as string | undefined },
          { label: "app bundle", value: tauriBuildArtifact.packaged_app_bundle_detected === true ? "detected" : "missing", tone: tauriBuildArtifact.packaged_app_bundle_detected === true ? "good" : "warn" },
          { label: "DMG", value: tauriBuildArtifact.distribution_dmg_detected === true ? "detected" : "missing", tone: tauriBuildArtifact.distribution_dmg_detected === true ? "good" : "warn" },
          { label: "backend autostart", value: runtime.backend_autostart_configured === true ? "enabled" : "manual", tone: runtime.backend_autostart_configured === true ? "warn" : "good" },
          { label: "package audit", value: productionBlockerAudit.status as string | undefined, tone: productionBlockerAudit.package_ready === true ? "good" : "warn" },
          { label: "runtime contract", value: productionRuntimeContract.status as string | undefined, tone: productionRuntimeContract.config_paths_declared === true ? "good" : "warn" },
          { label: "offline UX contract", value: backendOfflineUxContract.frontend_contract_ready === true ? "source ready" : "review", tone: backendOfflineUxContract.frontend_contract_ready === true ? "good" : "warn" },
          { label: "package ready", value: productionBlockerAudit.package_ready === true ? "ready" : "blocked", tone: productionBlockerAudit.package_ready === true ? "good" : "warn" },
          { label: "tauri build", value: productionBlockerAudit.tauri_build_verified === true ? "verified" : "not verified", tone: productionBlockerAudit.tauri_build_verified === true ? "good" : "warn" },
          { label: "config/log paths", value: productionBlockerAudit.config_log_paths_declared === true ? "declared" : "pending", tone: productionBlockerAudit.config_log_paths_declared === true ? "good" : "warn" },
          { label: "packaged offline UX", value: productionRuntimeContract.backend_offline_ui_packaged_runtime_verified === true ? "verified" : "pending", tone: productionRuntimeContract.backend_offline_ui_packaged_runtime_verified === true ? "good" : "warn" },
          { label: "packaged QA", value: packagedRuntimeQaContract.status as string | undefined, tone: packagedRuntimeQaContract.packaged_runtime_validated === true ? "good" : "warn" },
          { label: "binary QA", value: packagedRuntimeQaContract.release_binary_qa_passed === true ? "passed" : "pending", tone: packagedRuntimeQaContract.release_binary_qa_passed === true ? "good" : "warn" },
          { label: "pending QA", value: packagedRuntimeQaContract.pending_qa_count as number | undefined, tone: Number(packagedRuntimeQaContract.pending_qa_count ?? 0) > 0 ? "warn" : "good" },
          { label: "release manifest", value: tauriReleaseManifestContract.local_release_manifest_ready === true ? "ready" : "review", tone: tauriReleaseManifestContract.local_release_manifest_ready === true ? "good" : "warn" },
          { label: "manifest blockers", value: tauriReleaseManifestContract.production_blocker_count as number | undefined, tone: Number(tauriReleaseManifestContract.production_blocker_count ?? 0) > 0 ? "warn" : "good" },
          { label: "receipt ready", value: productionPackageReadinessReceipt.local_receipt_ready === true ? "yes" : "review", tone: productionPackageReadinessReceipt.local_receipt_ready === true ? "good" : "warn" },
          { label: "receipt blockers", value: productionPackageReadinessReceipt.blocking_criterion_count ?? counts.production_package_readiness_receipt_blocker_count, tone: Number(productionPackageReadinessReceipt.blocking_criterion_count ?? counts.production_package_readiness_receipt_blocker_count ?? 0) > 0 ? "warn" : "good" },
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
          <p>production_runtime_contract_is_path_only: {String(policy.production_runtime_contract_is_path_only ?? true)}</p>
          <p>does_not_read_config_values: {String(policy.does_not_read_config_values ?? true)}</p>
          <p>does_not_write_log_files: {String(policy.does_not_write_log_files ?? true)}</p>
        </PacketCard>
      </div>

      <PacketCard title="开发启动顺序" subtitle="手动启动 FastAPI、Vite、Tauri；预检页不执行命令" status="manual">
        <DataLineageTable rows={devLaunchPlan} />
      </PacketCard>

      <PacketCard title="生产打包路线" subtitle="只展示命令顺序；本页不运行 build 或 Tauri" status="manual">
        <DataLineageTable rows={productionLaunchPlan} />
      </PacketCard>

      <PacketCard title="Tauri production runtime contract" subtitle="路径和启动策略只读声明；不读取配置、不写日志、不启动后端" status={String(productionRuntimeContract.status ?? "runtime_contract_ready_packaged_validation_pending")}>
        <p>backend_startup_strategy: {String(productionRuntimeContract.backend_startup_strategy ?? "manual_fastapi_process_current_sidecar_pending")}</p>
        <p>config_file_policy: {String(productionRuntimeContract.config_file_policy ?? "~/.stock_ming_3/desktop.local.json")}</p>
        <p>log_file_policy: {String(productionRuntimeContract.log_file_policy ?? "~/.stock_ming_3/logs/command_center_3.log")}</p>
        <p>packaged_runtime_validated: {String(productionRuntimeContract.packaged_runtime_validated ?? false)}</p>
        <p>token_key_frontend_exposure: {String(productionRuntimeContract.token_key_frontend_exposure ?? false)}</p>
        <DataLineageTable rows={productionRuntimeRows} />
      </PacketCard>

      <PacketCard title="Tauri backend offline UX contract" subtitle="源码合同已可审计；packaged runtime 仍需真实打开验证" status={String(backendOfflineUxContract.status ?? "frontend_offline_notice_contract_incomplete")}>
        <p>backend_offline_error_code: {String(backendOfflineUxContract.backend_offline_error_code ?? "backend_offline_or_unreachable")}</p>
        <p>frontend_contract_ready: {String(backendOfflineUxContract.frontend_contract_ready ?? false)}</p>
        <p>api_client_fetch_error_fallback_ready: {String(backendOfflineUxContract.api_client_fetch_error_fallback_ready ?? false)}</p>
        <p>api_base_display_sanitized: {String(backendOfflineUxContract.api_base_display_sanitized ?? false)}</p>
        <p>offline_notice_component_ready: {String(backendOfflineUxContract.offline_notice_component_ready ?? false)}</p>
        <p>page_state_banner_integration_ready: {String(backendOfflineUxContract.page_state_banner_integration_ready ?? false)}</p>
        <p>backend_offline_ui_packaged_runtime_verified: {String(backendOfflineUxContract.backend_offline_ui_packaged_runtime_verified ?? false)}</p>
        <DataLineageTable rows={backendOfflineUxRows} />
      </PacketCard>

      <PacketCard title="Tauri 生产包阻断审计" subtitle="preflight 不是 production package complete" status={String(productionBlockerAudit.status ?? "production_package_blocked")}>
        <p>scope: {String(productionBlockerAudit.scope ?? "local_preflight_optional_build_artifact_detection_not_packaged_runtime_qa")}</p>
        <p>package_ready: {String(productionBlockerAudit.package_ready ?? false)}</p>
        <p>tauri_build_verified: {String(productionBlockerAudit.tauri_build_verified ?? false)}</p>
        <p>tauri_build_artifact_status: {String(productionBlockerAudit.tauri_build_artifact_status ?? tauriBuildArtifact.status ?? "artifact_missing")}</p>
        <p>tauri_build_artifact_path: {String(productionBlockerAudit.tauri_build_artifact_path ?? tauriBuildArtifact.binary_path ?? "desktop/src-tauri/target/release/stock_ming_command_center")}</p>
        <p>tauri_build_artifact_size_bytes: {String(productionBlockerAudit.tauri_build_artifact_size_bytes ?? tauriBuildArtifact.binary_size_bytes ?? 0)}</p>
        <p>binary_executable / binary_kind: {String(tauriBuildArtifact.binary_executable ?? false)} / {String(tauriBuildArtifact.binary_kind ?? "missing")}</p>
        <p>bundle_app_count / packaged_app_bundle_detected: {String(tauriBuildArtifact.bundle_app_count ?? 0)} / {String(tauriBuildArtifact.packaged_app_bundle_detected ?? false)}</p>
        <p>bundle_dmg_count / distribution_dmg_detected: {String(tauriBuildArtifact.bundle_dmg_count ?? 0)} / {String(tauriBuildArtifact.distribution_dmg_detected ?? false)}</p>
        <p>manual_backend_launch_required: {String(productionBlockerAudit.manual_backend_launch_required ?? true)}</p>
        <p>backend_offline_ui_packaged_runtime_verified: {String(productionBlockerAudit.backend_offline_ui_packaged_runtime_verified ?? false)}</p>
        <p>backend_offline_ux_contract_status: {String(productionBlockerAudit.backend_offline_ux_contract_status ?? backendOfflineUxContract.status ?? "frontend_offline_notice_contract_incomplete")}</p>
        <p>backend_offline_ux_frontend_contract_ready: {String(productionBlockerAudit.backend_offline_ux_frontend_contract_ready ?? false)}</p>
        <p>config_log_paths_declared: {String(productionBlockerAudit.config_log_paths_declared ?? false)}</p>
        <p>production_runtime_contract_status: {String(productionBlockerAudit.production_runtime_contract_status ?? "runtime_contract_ready_packaged_validation_pending")}</p>
        <p>macos_signing_notarization_ready: {String(productionBlockerAudit.macos_signing_notarization_ready ?? false)}</p>
        <p>production_readiness_status: {String(productionReadiness.status ?? "desktop_scaffold_partial")}</p>
      </PacketCard>

      <PacketCard title="Tauri 生产包阻断项" subtitle="逐项说明 dev/preflight 与 production package 的缺口" status="blockers">
        <DataLineageTable rows={productionBlockerRows} />
      </PacketCard>

      <PacketCard title="Tauri packaged runtime QA contract" subtitle="生产包验收矩阵；只读合同，不运行 Tauri、不打开 packaged app" status={String(packagedRuntimeQaContract.status ?? "packaged_runtime_qa_contract_missing")}>
        <p>scope: {String(packagedRuntimeQaContract.scope ?? "local_static_qa_matrix_not_packaged_runtime_execution")}</p>
        <p>qa_contract_ready: {String(packagedRuntimeQaContract.qa_contract_ready ?? false)}</p>
        <p>packaged_runtime_validated: {String(packagedRuntimeQaContract.packaged_runtime_validated ?? false)}</p>
        <p>release_binary_qa_passed / release_binary_executable: {String(packagedRuntimeQaContract.release_binary_qa_passed ?? false)} / {String(packagedRuntimeQaContract.release_binary_executable ?? false)}</p>
        <p>packaged_app_bundle_detected / distribution_dmg_detected: {String(packagedRuntimeQaContract.packaged_app_bundle_detected ?? false)} / {String(packagedRuntimeQaContract.distribution_dmg_detected ?? false)}</p>
        <p>browser_or_packaged_app_opened: {String(packagedRuntimeQaContract.browser_or_packaged_app_opened ?? false)}</p>
        <p>npm_or_cargo_executed: {String(packagedRuntimeQaContract.npm_or_cargo_executed ?? false)}</p>
        <p>config_values_read: {String(packagedRuntimeQaContract.config_values_read ?? false)}</p>
        <p>log_files_written: {String(packagedRuntimeQaContract.log_files_written ?? false)}</p>
        <DataLineageTable rows={packagedRuntimeQaRows} />
      </PacketCard>

      <PacketCard title="Tauri release manifest contract" subtitle="发布清单合同；只读检查身份、dist、artifact ignore、后端策略、配置/日志路径和签名缺口" status={String(tauriReleaseManifestContract.status ?? "release_manifest_contract_missing")}>
        <p>schema_version: {String(tauriReleaseManifestContract.schema_version ?? "tauri_release_manifest_contract.v1")}</p>
        <p>scope: {String(tauriReleaseManifestContract.scope ?? "local_tauri_release_manifest_contract_no_build_or_runtime_execution")}</p>
        <p>product / version / identifier: {String(tauriReleaseManifestContract.product_name ?? "stock-MING Command Center")} / {String(tauriReleaseManifestContract.app_version ?? "3.0.0")} / {String(tauriReleaseManifestContract.bundle_identifier ?? "com.stockming.commandcenter")}</p>
        <p>frontend_dist / before_build_command / dev_url: {String(tauriReleaseManifestContract.frontend_dist ?? "../dist")} / {String(tauriReleaseManifestContract.before_build_command ?? "npm run build")} / {String(tauriReleaseManifestContract.dev_url ?? "http://127.0.0.1:5173")}</p>
        <p>icon_asset_present / desktop_dist_gitignored / tauri_target_gitignored: {String(tauriReleaseManifestContract.icon_asset_present ?? false)} / {String(tauriReleaseManifestContract.desktop_dist_gitignored ?? false)} / {String(tauriReleaseManifestContract.tauri_target_gitignored ?? false)}</p>
        <p>backend_startup_strategy: {String(tauriReleaseManifestContract.backend_startup_strategy ?? "manual_fastapi_process_current_sidecar_pending")}</p>
        <p>config_file_policy / log_file_policy: {String(tauriReleaseManifestContract.config_file_policy ?? "~/.stock_ming_3/desktop.local.json")} / {String(tauriReleaseManifestContract.log_file_policy ?? "~/.stock_ming_3/logs/command_center_3.log")}</p>
        <p>local_release_manifest_ready / ready_for_production_package_promotion: {String(tauriReleaseManifestContract.local_release_manifest_ready ?? false)} / {String(tauriReleaseManifestContract.ready_for_production_package_promotion ?? false)}</p>
        <p>tauri_build_executed / packaged_app_opened / fastapi_started: {String(tauriReleaseManifestContract.tauri_build_executed ?? false)} / {String(tauriReleaseManifestContract.packaged_app_opened ?? false)} / {String(tauriReleaseManifestContract.fastapi_started ?? false)}</p>
        <p>config_values_read / log_files_written / signing_notarization_done: {String(tauriReleaseManifestContract.config_values_read ?? false)} / {String(tauriReleaseManifestContract.log_files_written ?? false)} / {String(tauriReleaseManifestContract.signing_notarization_done ?? false)}</p>
        <p>external_calls_triggered / tushare_called / deepseek_called / github_called: {String(tauriReleaseManifestContract.external_calls_triggered ?? false)} / {String(tauriReleaseManifestContract.tushare_called ?? false)} / {String(tauriReleaseManifestContract.deepseek_called ?? false)} / {String(tauriReleaseManifestContract.github_called ?? false)}</p>
        <DataLineageTable rows={tauriReleaseManifestRows} />
        <DataLineageTable rows={rows(tauriReleaseManifestContract.call_ledger)} />
      </PacketCard>

      <PacketCard title="Tauri production package readiness receipt" subtitle="LTG-09 下一步收据；只允许显式 build / packaged runtime QA review" status={String(productionPackageReadinessReceipt.status ?? "tauri_package_readiness_receipt_ready_build_pending")}>
        <p>schema_version: {String(productionPackageReadinessReceipt.schema_version ?? "tauri_production_package_readiness_receipt.v1")}</p>
        <p>scope: {String(productionPackageReadinessReceipt.scope ?? "local_tauri_production_package_readiness_receipt_no_build_or_runtime_execution")}</p>
        <p>local_receipt_ready / ready_for_explicit_tauri_build: {String(productionPackageReadinessReceipt.local_receipt_ready ?? true)} / {String(productionPackageReadinessReceipt.ready_for_explicit_tauri_build ?? true)}</p>
        <p>ready_for_packaged_runtime_qa / ready_for_production_package_promotion: {String(productionPackageReadinessReceipt.ready_for_packaged_runtime_qa ?? false)} / {String(productionPackageReadinessReceipt.ready_for_production_package_promotion ?? false)}</p>
        <p>allowed_next_step: {String(productionPackageReadinessReceipt.allowed_next_step ?? "explicit_tauri_build_then_packaged_runtime_qa_review")}</p>
        <p>production_package_complete: {String(productionPackageReadinessReceipt.production_package_complete ?? false)}</p>
        <p>tauri_build_executed_by_receipt / npm_or_cargo_executed_by_receipt: {String(productionPackageReadinessReceipt.tauri_build_executed_by_receipt ?? false)} / {String(productionPackageReadinessReceipt.npm_or_cargo_executed_by_receipt ?? false)}</p>
        <p>tauri_runtime_started_by_receipt / packaged_app_opened_by_receipt / fastapi_started_by_receipt: {String(productionPackageReadinessReceipt.tauri_runtime_started_by_receipt ?? false)} / {String(productionPackageReadinessReceipt.packaged_app_opened_by_receipt ?? false)} / {String(productionPackageReadinessReceipt.fastapi_started_by_receipt ?? false)}</p>
        <p>config_values_read_by_receipt / log_files_written_by_receipt: {String(productionPackageReadinessReceipt.config_values_read_by_receipt ?? false)} / {String(productionPackageReadinessReceipt.log_files_written_by_receipt ?? false)}</p>
        <p>receipt_external_calls_triggered / tushare_called / deepseek_called / github_called: {String(productionPackageReadinessReceipt.receipt_external_calls_triggered ?? false)} / {String(productionPackageReadinessReceipt.tushare_called ?? false)} / {String(productionPackageReadinessReceipt.deepseek_called ?? false)} / {String(productionPackageReadinessReceipt.github_called ?? false)}</p>
        <p>not_allowed_next_steps: {Array.isArray(productionPackageReadinessReceipt.not_allowed_next_steps) ? productionPackageReadinessReceipt.not_allowed_next_steps.join(" / ") : "GET /api/desktop/preflight-cache npm build / GET /api/desktop/preflight-cache tauri build / GET /api/desktop/preflight-cache packaged app launch / release artifact detection as packaged runtime QA / preflight receipt as production package completion"}</p>
        <DataLineageTable rows={productionPackageReadinessReceiptRows} />
        <DataLineageTable rows={rows(productionPackageReadinessReceipt.call_ledger)} />
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
        <JsonDetails title="tauri release manifest raw" data={tauriReleaseManifestContract} />
        <JsonDetails title="tauri production package readiness receipt raw" data={productionPackageReadinessReceipt} />
      </PacketCard>
    </>
  );
}
