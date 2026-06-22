import { useEffect, useState } from "react";
import { getDesktopPreflightCache, getHealth, getMigrationStatus } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function HealthStatus() {
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [healthEnvelopeLedger, setHealthEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [healthEnvelopeWarnings, setHealthEnvelopeWarnings] = useState<Array<string>>([]);
  const [migration, setMigration] = useState<Record<string, unknown>>({});
  const [desktopPreflight, setDesktopPreflight] = useState<Record<string, unknown>>({});
  const [desktopPreflightEnvelopeLedger, setDesktopPreflightEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [desktopPreflightEnvelopeWarnings, setDesktopPreflightEnvelopeWarnings] = useState<Array<string>>([]);

  useEffect(() => {
    void getHealth().then((res) => {
      setHealth(res.data);
      setHealthEnvelopeLedger(res.call_ledger ?? []);
      setHealthEnvelopeWarnings(res.warnings ?? []);
    });
    void getMigrationStatus().then((res) => setMigration(res.data));
    void getDesktopPreflightCache().then((res) => {
      setDesktopPreflight(res.data);
      setDesktopPreflightEnvelopeLedger(res.call_ledger ?? []);
      setDesktopPreflightEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const modelStrategy = health.deepseek_model_strategy as Record<string, unknown> | undefined;
  const modelStrategyRows = [
    { purpose: "default", model: modelStrategy?.default ?? "--", grade: "解释默认" },
    { purpose: "explain", model: modelStrategy?.explain ?? "--", grade: "解释" },
    { purpose: "projection", model: modelStrategy?.projection ?? "--", grade: "次日图谱解释" },
    { purpose: "factor_explain", model: modelStrategy?.factor_explain ?? "--", grade: "因子解释" },
    { purpose: "fast", model: modelStrategy?.fast ?? "--", grade: "轻量" },
    { purpose: "healthcheck", model: modelStrategy?.healthcheck ?? "--", grade: "健康检查" },
    { purpose: "feeder", model: modelStrategy?.feeder ?? "--", grade: "自动喂数" }
  ];
  const progress = (migration.progress_baseline as Array<Record<string, unknown>> | undefined) ?? [];
  const migrationPolicy = migration.api_policy as Record<string, unknown> | undefined;
  const healthWarnings = healthEnvelopeWarnings.length ? healthEnvelopeWarnings : ((health.warnings as Array<string> | undefined) ?? []);
  const oneClickStartupSummary = (desktopPreflight.one_click_startup_summary as Record<string, unknown> | undefined) ?? {};
  const desktopLauncherContract = (desktopPreflight.desktop_launcher_contract as Record<string, unknown> | undefined) ?? {};
  const oneClickConnectionRows = (desktopPreflight.one_click_connection_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const desktopPreflightWarnings = desktopPreflightEnvelopeWarnings.length ? desktopPreflightEnvelopeWarnings : ((desktopPreflight.warnings as Array<string> | undefined) ?? []);
  const p0ConnectionReady = oneClickStartupSummary.frontend_backend_connection_ready === true;

  return (
    <>
      <div className="page-head">
        <h1>系统健康</h1>
        <StatusBadge label={String(health.status ?? "loading")} tone={health.status === "ok" ? "good" : "warn"} />
      </div>

      <PacketCard title="P0 前后端联通摘要" subtitle="普通用户先确认本地 FastAPI / React 是否已联通" status={String(oneClickStartupSummary.status ?? "preflight_cache_loading")}>
        <p>联通状态：{p0ConnectionReady ? "已具备本地一键联通条件" : "需要检查本地一键入口"}</p>
        <p>下一步：{String(oneClickStartupSummary.what_user_should_click_next ?? "打开桌面壳预检，按本地快捷入口重启。")}</p>
        <p>快捷入口：{String(desktopLauncherContract.desktop_shortcut_target_name ?? "stock-MING Command Center 3.command")}</p>
        <p>成功条件：{String(oneClickStartupSummary.success_condition ?? "FastAPI /health 必须返回 Command Center 3.0 健康 JSON，/api/bootstrap/status 必须返回 runtime-mode packet，React/Vite 必须返回 Command Center 3.0 前端 HTML 后才打开页面。")}</p>
        <p>失败处理：{String(oneClickStartupSummary.blocked_next_action ?? "先看启动器的可操作诊断：FastAPI、bootstrap status、React/Vite 哪段失败；再检查 8710/5173 是否被占用，或进入桌面壳预检。")}</p>
        <p>诊断分段：{Array.isArray(oneClickStartupSummary.diagnostic_surfaces) ? oneClickStartupSummary.diagnostic_surfaces.join(" / ") : "FastAPI /health Command Center 3.0 JSON / bootstrap status runtime-mode packet / React/Vite Command Center 3.0 HTML / 8710/5173 port occupancy guidance"}</p>
        <p>只读边界：本卡只读取 GET /health 与 GET /api/desktop/preflight-cache；不会启动 FastAPI/Vite、不会创建 task、不会调用 Tushare/DeepSeek/GitHub 或交易路径。</p>
        <DataLineageTable rows={oneClickConnectionRows} />
      </PacketCard>

      <MetricGrid
        items={[
          { label: "FastAPI", value: health.status as string | undefined, tone: health.status === "ok" ? "good" : "warn" },
          { label: "P0 front/back", value: p0ConnectionReady ? "ready" : "check", tone: p0ConnectionReady ? "good" : "warn" },
          { label: "one-click launcher", value: desktopLauncherContract.launcher_executable === true ? "ready" : "check", tone: desktopLauncherContract.launcher_executable === true ? "good" : "warn" },
          { label: "startup external calls", value: health.external_calls_on_startup === true ? "存在" : "无", tone: health.external_calls_on_startup === true ? "bad" : "good" },
          { label: "Tushare", value: health.tushare_called === true ? "已调用" : "未调用", tone: health.tushare_called === true ? "bad" : "good" },
          { label: "DeepSeek", value: health.deepseek_called === true ? "已调用" : "未调用", tone: health.deepseek_called === true ? "bad" : "good" },
          { label: "GitHub", value: health.github_called === true ? "已调用" : "未调用", tone: health.github_called === true ? "bad" : "good" },
          { label: "真实交易", value: health.real_trading_enabled === true ? "启用" : "禁用", tone: health.real_trading_enabled === true ? "bad" : "good" },
          { label: "Streamlit", value: String(health.legacy_streamlit ?? "legacy/admin/debug") },
          { label: "迁移基线", value: String(migration.status ?? "loading") },
          { label: "cache only", value: migrationPolicy?.cache_only, tone: migrationPolicy?.cache_only === false ? "bad" : "good" },
          { label: "health envelope ledger", value: healthEnvelopeLedger.length },
          { label: "desktop preflight ledger", value: desktopPreflightEnvelopeLedger.length },
          { label: "health warnings", value: healthWarnings.length },
          { label: "desktop preflight warnings", value: desktopPreflightWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="启动安全边界" subtitle="GET /health 只读；不触发 Tushare、DeepSeek 或 GitHub" status="read_only">
          <p>Command Center 3.0 启动健康检查只展示服务状态，不创建任务，不读取 token/key，不执行真实交易。</p>
          <p>所有重计算和外部请求仍必须通过按钮门控 POST task，并由 call_ledger 审计。</p>
        </PacketCard>

        <PacketCard title="DeepSeek 模型策略" subtitle="可配置模型名；不在调用点硬编码；不展示密钥" status="config">
          <DataLineageTable rows={modelStrategyRows} />
          <p>contains_secret: {String(modelStrategy?.contains_secret ?? false)}</p>
          <p>source: {String(modelStrategy?.source ?? "config")}</p>
        </PacketCard>
      </div>

      <PacketCard title="迁移基线" subtitle="用户给定长期参考进度；只读展示，不重新估算" status={String(migration.status ?? "baseline")}>
        <DataLineageTable rows={progress} />
      </PacketCard>

      <PacketCard title="GET health envelope call_ledger" subtitle="GET /health 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={healthEnvelopeLedger} />
      </PacketCard>

      <PacketCard title="GET health envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={healthWarnings.map((warning, index) => ({ index: index + 1, warning }))} />
      </PacketCard>

      <PacketCard title="原始健康 payload" subtitle="调试用 JSON；不含 token/key" status="safe">
        <JsonDetails title="health raw" data={health} />
        <JsonDetails title="migration raw" data={migration} />
      </PacketCard>
    </>
  );
}
