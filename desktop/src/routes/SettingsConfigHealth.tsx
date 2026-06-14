import { useEffect, useState } from "react";
import {
  getDataHealthCache,
  getDesktopPreflightCache,
  getBootstrapStatus,
  getHealth,
  getMigrationStatus,
  getModelStrategyCache,
  getStorageOverview,
  getTaskCatalog,
  postBootstrapLiveStartup,
} from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import PageStateBanner from "../components/PageStateBanner";
import StatusBadge from "../components/StatusBadge";

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function warningRows(warnings: Array<unknown>) {
  return warnings.map((warning, index) => ({ index: index + 1, warning: String(warning ?? "") }));
}

function safeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error ?? "unknown_error");
}

export default function SettingsConfigHealth() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [bootstrapStatus, setBootstrapStatus] = useState<Record<string, unknown>>({});
  const [modelStrategy, setModelStrategy] = useState<Record<string, unknown>>({});
  const [dataHealth, setDataHealth] = useState<Record<string, unknown>>({});
  const [desktopPreflight, setDesktopPreflight] = useState<Record<string, unknown>>({});
  const [storage, setStorage] = useState<Record<string, unknown>>({});
  const [taskCatalog, setTaskCatalog] = useState<Record<string, unknown>>({});
  const [migration, setMigration] = useState<Record<string, unknown>>({});
  const [bootstrapTask, setBootstrapTask] = useState<Record<string, unknown>>({});
  const [bootstrapActionLoading, setBootstrapActionLoading] = useState(false);
  const [ledgerRows, setLedgerRows] = useState<Array<Record<string, unknown>>>([]);
  const [warnings, setWarnings] = useState<Array<unknown>>([]);

  const refreshCache = () => {
    setLoading(true);
    setError("");
    const calls = [
      getHealth().then((res) => {
        setHealth(res.data);
        return { scope: "health", res };
      }),
      getBootstrapStatus().then((res) => {
        setBootstrapStatus(res.data);
        return { scope: "bootstrap_status", res };
      }),
      getModelStrategyCache().then((res) => {
        setModelStrategy(res.data);
        return { scope: "model_strategy", res };
      }),
      getDataHealthCache().then((res) => {
        setDataHealth(res.data);
        return { scope: "data_health", res };
      }),
      getDesktopPreflightCache().then((res) => {
        setDesktopPreflight(res.data);
        return { scope: "desktop_preflight", res };
      }),
      getStorageOverview().then((res) => {
        setStorage(res.data);
        return { scope: "storage", res };
      }),
      getTaskCatalog().then((res) => {
        setTaskCatalog(res.data);
        return { scope: "task_catalog", res };
      }),
      getMigrationStatus().then((res) => {
        setMigration(res.data);
        return { scope: "migration", res };
      }),
    ];

    void Promise.allSettled(calls).then((results) => {
      const nextLedger: Array<Record<string, unknown>> = [];
      const nextWarnings: Array<unknown> = [];
      const rejected = results.filter((item) => item.status === "rejected");
      results.forEach((item) => {
        if (item.status !== "fulfilled") return;
        item.value.res.call_ledger.forEach((row) => nextLedger.push({ scope: item.value.scope, ...row }));
        item.value.res.warnings.forEach((warning) => nextWarnings.push(`${item.value.scope}: ${String(warning)}`));
        if (!item.value.res.ok) nextWarnings.push(`${item.value.scope}: ${item.value.res.error ?? "request_not_ok"}`);
      });
      setLedgerRows(nextLedger);
      setWarnings(nextWarnings);
      if (rejected.length) {
        setError(rejected.map((item) => safeError(item.reason)).join(" / "));
      }
      setLoading(false);
    });
  };

  const createBootstrapTask = () => {
    setBootstrapActionLoading(true);
    setError("");
    void postBootstrapLiveStartup({
      source: "settings_config_health",
      requested_by: "local_user",
    }).then((res) => {
      const task = (res.data.task as Record<string, unknown> | undefined) ?? {};
      setBootstrapTask(task);
      setLedgerRows((current) => [
        ...res.call_ledger.map((row) => ({ scope: "bootstrap_live_startup", ...row })),
        ...current,
      ]);
      setWarnings((current) => [
        ...res.warnings.map((warning) => `bootstrap_live_startup: ${String(warning)}`),
        ...current,
      ]);
      if (!res.ok) {
        setError(String(res.error ?? "bootstrap_live_startup_failed"));
      }
    }).catch((nextError) => {
      setError(safeError(nextError));
    }).finally(() => {
      setBootstrapActionLoading(false);
    });
  };

  useEffect(() => {
    refreshCache();
  }, []);

  const modelRows = rows(modelStrategy.model_rows);
  const modeRows = rows(bootstrapStatus.mode_rows);
  const configRuntimeRows = rows(bootstrapStatus.config_rows);
  const dataHealthCounts = (dataHealth.counts as Record<string, unknown> | undefined) ?? {};
  const desktopRuntime = (desktopPreflight.runtime as Record<string, unknown> | undefined) ?? {};
  const storageStatus = (storage.dataset_status as Record<string, unknown> | undefined) ?? {};
  const taskPolicy = (taskCatalog.policy as Record<string, unknown> | undefined) ?? {};
  const migrationPolicy = (migration.api_policy as Record<string, unknown> | undefined) ?? {};
  const liveLight = (bootstrapStatus.live_light as Record<string, unknown> | undefined) ?? {};
  const hasBootstrapTask = Object.keys(bootstrapTask).length > 0;
  const empty = !loading && !error && !Object.keys(health).length && !Object.keys(modelStrategy).length;

  const configRows = [
    { config: "DEEPSEEK_EXPLAIN_MODEL", status: "configurable", note: "解释/投影/因子解释优先使用；不展示 token/key。" },
    { config: "DEEPSEEK_FAST_MODEL", status: "configurable", note: "健康检查、feeder、轻量任务优先使用。" },
    { config: "DEEPSEEK_DEFAULT_MODEL", status: "fallback", note: "模型策略 fallback；调用点不得硬编码模型名。" },
    { config: "服务端 Tushare 凭据", status: "server_only", note: "前端不保存、不读取；按钮任务才可能使用。" },
    { config: "GitHub 校验凭据", status: "not_required", note: "Serenity GitHub 校验走按钮任务；前端不保存凭据。" },
  ];

  const boundaryRows = [
    { boundary: "default_load", value: "GET cache only", note: "cache_only 和初始 render 不调用 Tushare、DeepSeek、GitHub。" },
    { boundary: "post_task", value: "mode gated", note: "外部请求只能经模式/按钮/显式 payload 门控的 POST task。" },
    { boundary: "live_light", value: "local bootstrap task", note: "用户点击可创建本地 task skeleton；provider 执行仍待后续验收。" },
    { boundary: "frontend_access", value: "FastAPI only", note: "React 前端不直接调用 Python、不保存 token/key。" },
    { boundary: "strategy_action", value: "read_only", note: "配置健康页不修改 strategy action。" },
    { boundary: "real_trade", value: "disabled", note: "不执行真实交易，不自动下单。" },
  ];

  return (
    <>
      <div className="page-head">
        <h1>Settings / Config Health</h1>
        <StatusBadge label={String(health.status ?? "cache")} tone={health.status === "ok" ? "good" : "warn"} />
      </div>

      <PageStateBanner
        loading={loading}
        error={error}
        empty={empty}
        emptyTitle="暂无配置健康缓存"
        emptyDetail="请先确认 FastAPI 服务已启动；本页不会自动触发外部刷新。"
      />

      <div className="actions">
        <button onClick={refreshCache}>查看配置健康缓存</button>
        <button onClick={createBootstrapTask} disabled={bootstrapActionLoading}>
          {bootstrapActionLoading ? "创建中" : "启动 live_light 本地任务"}
        </button>
      </div>

      <MetricGrid
        items={[
          { label: "FastAPI", value: health.status as string | undefined, tone: health.status === "ok" ? "good" : "warn" },
          { label: "runtime mode", value: String(bootstrapStatus.mode ?? "--"), tone: bootstrapStatus.mode === "cache_only" ? "good" : "warn" },
          { label: "live light", value: liveLight.enabled === true ? "opt-in" : "off", tone: liveLight.enabled === true ? "warn" : "good" },
          { label: "bootstrap task", value: liveLight.bootstrap_task_implemented === true ? "ready" : "pending", tone: liveLight.bootstrap_task_implemented === true ? "good" : "warn" },
          { label: "startup external", value: health.external_calls_on_startup === true ? "存在" : "无", tone: health.external_calls_on_startup === true ? "bad" : "good" },
          { label: "model purposes", value: modelRows.length },
          { label: "data health rows", value: dataHealthCounts.timeline_count as number | undefined },
          { label: "desktop node", value: String(desktopRuntime.node ?? "--") },
          { label: "factor parquet", value: String(storageStatus.factor_values ?? "missing") },
          { label: "task button gated", value: taskPolicy.all_tasks_button_gated, tone: taskPolicy.all_tasks_button_gated === false ? "bad" : "good" },
          { label: "migration cache only", value: migrationPolicy.cache_only, tone: migrationPolicy.cache_only === false ? "bad" : "good" },
          { label: "call ledger", value: ledgerRows.length },
          { label: "warnings", value: warnings.length },
        ]}
      />

      <div className="grid">
        <PacketCard title="配置边界" subtitle="只读配置健康；不会读取或展示 token/key" status="read_only">
          <p>本页聚合 health、bootstrap status、model strategy、data health、desktop preflight、storage、task catalog 和 migration cache。</p>
          <p>所有数据来自 FastAPI GET cache API；不会自动调用 Tushare、DeepSeek、GitHub 或真实交易接口。</p>
          <DataLineageTable rows={boundaryRows} />
        </PacketCard>

        <PacketCard title="运行模式分层" subtitle="cache_only / manual / live_light / live_full，只读展示" status={String(bootstrapStatus.status ?? "cache_only")}>
          <DataLineageTable rows={modeRows} />
        </PacketCard>

        <PacketCard title="live_light 配置合同" subtitle="显示安全配置状态；手动按钮只创建本地 task skeleton" status={String(liveLight.enabled === true ? "review_pending" : "cache_only")}>
          <DataLineageTable rows={configRuntimeRows} />
          <JsonDetails title="live_light policy" data={liveLight} />
        </PacketCard>

        <PacketCard title="最近 bootstrap task" subtitle="按钮创建的本地任务；不外联、不交易" status={String(bootstrapTask.status ?? (hasBootstrapTask ? "created" : "idle"))}>
          <p>task_id: {String(bootstrapTask.task_id ?? "--")}</p>
          <p>current_step: {String(bootstrapTask.current_step ?? "--")}</p>
          <p>external / Tushare / DeepSeek / GitHub: {String(bootstrapTask.external_calls_triggered ?? false)} / {String(bootstrapTask.tushare_called ?? false)} / {String(bootstrapTask.deepseek_called ?? false)} / {String(bootstrapTask.github_called ?? false)}</p>
          <JsonDetails title="bootstrap task" data={bootstrapTask} />
        </PacketCard>

        <PacketCard title="关键配置项" subtitle="只展示配置键名和用途，不展示值" status="safe">
          <DataLineageTable rows={configRows} />
        </PacketCard>
      </div>

      <PacketCard title="DeepSeek 模型用途" subtitle="模型名可配置；cache read 不调用 DeepSeek" status={String(modelStrategy.status ?? "cache")}>
        <DataLineageTable rows={modelRows} />
      </PacketCard>

      <PacketCard title="配置健康 call_ledger" subtitle="各 cache API 顶层响应血缘；不外联、不交易" status="lineage">
        <DataLineageTable rows={ledgerRows} />
      </PacketCard>

      <PacketCard title="配置健康 warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={warningRows(warnings)} />
      </PacketCard>

      <PacketCard title="原始配置健康 payload" subtitle="调试用 JSON；只读 cache" status="safe">
        <JsonDetails title="health" data={health} />
        <JsonDetails title="bootstrap status" data={bootstrapStatus} />
        <JsonDetails title="model strategy" data={modelStrategy} />
        <JsonDetails title="data health" data={dataHealth} />
        <JsonDetails title="desktop preflight" data={desktopPreflight} />
        <JsonDetails title="storage" data={storage} />
        <JsonDetails title="task catalog" data={taskCatalog} />
        <JsonDetails title="migration" data={migration} />
      </PacketCard>
    </>
  );
}
