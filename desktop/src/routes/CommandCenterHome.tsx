import { useEffect, useState } from "react";
import { getAuditCache, getCandidateRadarCache, getChokepointCache, getDataHealthCache, getDesktopPreflightCache, getDisciplineLoopCache, getFactorQuantCache, getHealth, getLegacyBridgeCache, getMarketContextCache, getMigrationStatus, getModelStrategyCache, getNextSessionCache, getPackets, getPositionCache, getRecoveryCenterCache, getRiskGuardrailsCache, getSerenityCache, getStorageOverview, getTaskCatalog, getTasks, getWorkerRuntimeCache, type TaskStatusIndex } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function CommandCenterHome() {
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [healthEnvelopeLedger, setHealthEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [healthEnvelopeWarnings, setHealthEnvelopeWarnings] = useState<Array<string>>([]);
  const [audit, setAudit] = useState<Record<string, unknown>>({});
  const [packets, setPackets] = useState<Record<string, unknown>>({});
  const [packetEnvelopeLedger, setPacketEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [market, setMarket] = useState<Record<string, unknown>>({});
  const [discipline, setDiscipline] = useState<Record<string, unknown>>({});
  const [factor, setFactor] = useState<Record<string, unknown>>({});
  const [factorEnvelopeLedger, setFactorEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [factorEnvelopeWarnings, setFactorEnvelopeWarnings] = useState<Array<string>>([]);
  const [next, setNext] = useState<Record<string, unknown>>({});
  const [nextEnvelopeLedger, setNextEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [nextEnvelopeWarnings, setNextEnvelopeWarnings] = useState<Array<string>>([]);
  const [dataHealth, setDataHealth] = useState<Record<string, unknown>>({});
  const [desktopPreflight, setDesktopPreflight] = useState<Record<string, unknown>>({});
  const [recovery, setRecovery] = useState<Record<string, unknown>>({});
  const [position, setPosition] = useState<Record<string, unknown>>({});
  const [candidates, setCandidates] = useState<Record<string, unknown>>({});
  const [risk, setRisk] = useState<Record<string, unknown>>({});
  const [serenity, setSerenity] = useState<Record<string, unknown>>({});
  const [chokepoint, setChokepoint] = useState<Record<string, unknown>>({});
  const [storageOverview, setStorageOverview] = useState<Record<string, unknown>>({});
  const [migration, setMigration] = useState<Record<string, unknown>>({});
  const [modelStrategy, setModelStrategy] = useState<Record<string, unknown>>({});
  const [legacyBridge, setLegacyBridge] = useState<Record<string, unknown>>({});
  const [taskCatalog, setTaskCatalog] = useState<Record<string, unknown>>({});
  const [taskCatalogEnvelopeLedger, setTaskCatalogEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [taskIndex, setTaskIndex] = useState<TaskStatusIndex | null>(null);
  const [taskIndexEnvelopeLedger, setTaskIndexEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [workerRuntime, setWorkerRuntime] = useState<Record<string, unknown>>({});
  const [tasks, setTasks] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    void getHealth().then((res) => {
      setHealth(res.data);
      setHealthEnvelopeLedger(res.call_ledger ?? []);
      setHealthEnvelopeWarnings(res.warnings ?? []);
    });
    void getAuditCache().then((res) => setAudit(res.data));
    void getPackets().then((res) => {
      setPacketEnvelopeLedger(res.call_ledger ?? []);
      setPackets(res.data);
    });
    void getMarketContextCache().then((res) => setMarket(res.data));
    void getDisciplineLoopCache().then((res) => setDiscipline(res.data));
    void getFactorQuantCache().then((res) => {
      setFactorEnvelopeLedger(res.call_ledger ?? []);
      setFactorEnvelopeWarnings(res.warnings ?? []);
      setFactor(res.data);
    });
    void getNextSessionCache().then((res) => {
      setNextEnvelopeLedger(res.call_ledger ?? []);
      setNextEnvelopeWarnings(res.warnings ?? []);
      setNext(res.data);
    });
    void getDataHealthCache().then((res) => setDataHealth(res.data));
    void getDesktopPreflightCache().then((res) => setDesktopPreflight(res.data));
    void getRecoveryCenterCache().then((res) => setRecovery(res.data));
    void getPositionCache().then((res) => setPosition(res.data));
    void getCandidateRadarCache().then((res) => setCandidates(res.data));
    void getRiskGuardrailsCache().then((res) => setRisk(res.data));
    void getSerenityCache().then((res) => setSerenity(res.data));
    void getChokepointCache().then((res) => setChokepoint(res.data));
    void getStorageOverview().then((res) => setStorageOverview(res.data));
    void getMigrationStatus().then((res) => setMigration(res.data));
    void getModelStrategyCache().then((res) => setModelStrategy(res.data));
    void getLegacyBridgeCache().then((res) => setLegacyBridge(res.data));
    void getTaskCatalog().then((res) => {
      setTaskCatalogEnvelopeLedger(res.call_ledger ?? []);
      setTaskCatalog(res.data);
    });
    void getWorkerRuntimeCache().then((res) => setWorkerRuntime(res.data));
    void getTasks().then((res) => {
      setTaskIndexEnvelopeLedger(res.call_ledger ?? []);
      setTaskIndex(res.data);
      setTasks(res.data.tasks ?? []);
    });
  }, []);

  const packetKeys = packets.available_cache_keys as unknown[] | undefined;
  const auditCounts = audit.counts as Record<string, unknown> | undefined;
  const snapshotAvailable = Boolean(packets.snapshot_available);
  const sqliteMeta = packets.sqlite_meta as Record<string, unknown> | undefined;
  const sqlitePackets = sqliteMeta?.packet_metadata as unknown[] | undefined;
  const sqliteTasks = sqliteMeta?.task_metadata as unknown[] | undefined;
  const marketCounts = market.counts as Record<string, unknown> | undefined;
  const disciplineCounts = discipline.counts as Record<string, unknown> | undefined;
  const disciplinePacket = discipline.discipline_packet as Record<string, unknown> | undefined;
  const storageStatus = storageOverview.dataset_status as Record<string, unknown> | undefined;
  const storageDatasets = storageOverview.datasets as Array<Record<string, unknown>> | undefined;
  const deepseekModelRows = modelStrategy.model_rows as Array<Record<string, unknown>> | undefined;
  const deepseekModelCounts = modelStrategy.counts as Record<string, unknown> | undefined;
  const deepseekModelByPurpose = new Map((deepseekModelRows ?? []).map((row) => [String(row.purpose), row]));
  const migrationProgress = migration.progress_baseline as Array<Record<string, unknown>> | undefined;
  const migrationPolicy = migration.api_policy as Record<string, unknown> | undefined;
  const dataHealthCounts = dataHealth.counts as Record<string, unknown> | undefined;
  const desktopRuntime = desktopPreflight.runtime as Record<string, unknown> | undefined;
  const desktopCounts = desktopPreflight.counts as Record<string, unknown> | undefined;
  const recoveryCounts = recovery.counts as Record<string, unknown> | undefined;
  const taskCatalogPolicy = taskCatalog.policy as Record<string, unknown> | undefined;
  const taskCatalogItems = taskCatalog.tasks as Array<Record<string, unknown>> | undefined;
  const legacyCounts = legacyBridge.counts as Record<string, unknown> | undefined;
  const workerCounts = workerRuntime.counts as Record<string, unknown> | undefined;
  const workerRuntimeState = workerRuntime.runtime as Record<string, unknown> | undefined;
  const positionSummary = position.position_summary as Record<string, unknown> | undefined;
  const candidateCounts = candidates.counts as Record<string, unknown> | undefined;
  const riskCounts = risk.counts as Record<string, unknown> | undefined;
  const factorScoreChart = factor.score_chart_payload as Record<string, unknown> | undefined;
  const factorScoreChartContract = factorScoreChart?.chart_contract as Record<string, unknown> | undefined;
  const healthWarnings = healthEnvelopeWarnings.length ? healthEnvelopeWarnings : ((health.warnings as Array<string> | undefined) ?? []);
  const packetPayloadLedger = (packets.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const factorPayloadLedger = (factor.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const nextPayloadLedger = (next.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const taskCatalogPayloadLedger = (taskCatalog.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const taskIndexPayloadLedger = taskIndex?.call_ledger ?? [];
  const envelopeLedgerRows = [
    ...healthEnvelopeLedger.map((row) => ({ scope: "health", ...row })),
    ...(packetEnvelopeLedger.length ? packetEnvelopeLedger : packetPayloadLedger).map((row) => ({ scope: "packet_index", ...row })),
    ...(factorEnvelopeLedger.length ? factorEnvelopeLedger : factorPayloadLedger).map((row) => ({ scope: "factor_quant", ...row })),
    ...(nextEnvelopeLedger.length ? nextEnvelopeLedger : nextPayloadLedger).map((row) => ({ scope: "next_session", ...row })),
    ...(taskCatalogEnvelopeLedger.length ? taskCatalogEnvelopeLedger : taskCatalogPayloadLedger).map((row) => ({ scope: "task_catalog", ...row })),
    ...(taskIndexEnvelopeLedger.length ? taskIndexEnvelopeLedger : taskIndexPayloadLedger).map((row) => ({ scope: "task_status_index", ...row }))
  ];

  return (
    <>
      <div className="page-head">
        <h1>Command Center 3.0</h1>
        <StatusBadge label={health.status === "ok" ? "FastAPI online" : "waiting"} tone={health.status === "ok" ? "good" : "warn"} />
      </div>
      <MetricGrid
        items={[
          { label: "FastAPI", value: String(health.status ?? "unknown"), tone: health.status === "ok" ? "good" : "warn" },
          { label: "health envelope ledger", value: healthEnvelopeLedger.length },
          { label: "health warnings", value: healthWarnings.length },
          { label: "本地快照", value: snapshotAvailable, tone: snapshotAvailable ? "good" : "warn" },
          { label: "cache keys", value: packetKeys?.length ?? 0 },
          { label: "packet envelope ledger", value: (packetEnvelopeLedger.length ? packetEnvelopeLedger : packetPayloadLedger).length },
          { label: "factor envelope ledger", value: (factorEnvelopeLedger.length ? factorEnvelopeLedger : factorPayloadLedger).length },
          { label: "next envelope ledger", value: (nextEnvelopeLedger.length ? nextEnvelopeLedger : nextPayloadLedger).length },
          { label: "任务记录", value: taskIndex?.task_count ?? tasks.length },
          { label: "任务外联", value: taskIndex?.external_calls_triggered === true ? "存在" : "无", tone: taskIndex?.external_calls_triggered === true ? "bad" : "good" },
          { label: "任务目录", value: taskCatalogItems?.length ?? 0 },
          { label: "task catalog ledger", value: (taskCatalogEnvelopeLedger.length ? taskCatalogEnvelopeLedger : taskCatalogPayloadLedger).length },
          { label: "task index ledger", value: (taskIndexEnvelopeLedger.length ? taskIndexEnvelopeLedger : taskIndexPayloadLedger).length },
          { label: "SQLite packets", value: sqlitePackets?.length ?? 0 },
          { label: "SQLite tasks", value: sqliteTasks?.length ?? 0 },
          { label: "factor parquet", value: String(storageStatus?.factor_values ?? "missing") },
          { label: "daily parquet", value: String(storageStatus?.daily ?? "missing") },
          { label: "moneyflow parquet", value: String(storageStatus?.moneyflow ?? "missing") },
          { label: "迁移基线", value: String(migration.status ?? "loading") },
          { label: "DeepSeek explain", value: String(deepseekModelByPurpose.get("explain")?.model ?? "--") },
          { label: "DeepSeek fast", value: String(deepseekModelByPurpose.get("fast")?.model ?? "--") },
          { label: "外部启动调用", value: health.external_calls_on_startup === true ? "存在" : "无", tone: health.external_calls_on_startup === true ? "bad" : "good" }
        ]}
      />
      <div className="grid">
        <PacketCard title="Packet Registry" subtitle="现有 packet contract 只读映射" status={snapshotAvailable ? "snapshot" : "cache"}>
          <p>本地快照路径：{String(packets.snapshot_cache_path ?? "--")}</p>
          <p>alias keys: {String((packets.snapshot_alias_keys as unknown[] | undefined)?.length ?? 0)}</p>
          <p>SQLite meta: {String(Boolean(sqliteMeta?.sqlite_meta_available))}</p>
          <JsonDetails title="packet index 明细" data={packets} />
        </PacketCard>
        <PacketCard title="Command Center 3.0 迁移基线" subtitle="用户给定长期进度表；只读展示，不重新估算" status={String(migration.status ?? "baseline")}>
          <p>progress items: {String(migrationProgress?.length ?? 0)}</p>
          <p>cache only: {String(migrationPolicy?.cache_only ?? true)}</p>
          <p>external calls: {String(migrationPolicy?.external_calls_triggered ?? false)}</p>
          <JsonDetails title="迁移进度基线" data={migrationProgress ?? []} />
        </PacketCard>
        <PacketCard title="调用审计 cache" subtitle="GET cache，聚合本地 call_ledger，不触发外部请求" status={String(audit.status ?? "cache")}>
          <p>endpoint / task: {String(auditCounts?.cache_endpoint_count ?? 0)} / {String(auditCounts?.task_count ?? 0)}</p>
          <p>call ledger: {String(auditCounts?.call_ledger_count ?? 0)}</p>
          <p>external calls: {String(audit.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="3.0 envelope 血缘总览" subtitle="首页优先读取 FastAPI 顶层 call_ledger；不钻 payload 也能判断只读边界" status="lineage">
          <p>health / packet / factor / next / catalog / task index: {String(healthEnvelopeLedger.length)} / {String(packetEnvelopeLedger.length)} / {String(factorEnvelopeLedger.length)} / {String(nextEnvelopeLedger.length)} / {String(taskCatalogEnvelopeLedger.length)} / {String(taskIndexEnvelopeLedger.length)}</p>
          <p>health warnings: {String(healthWarnings.length)}</p>
          <p>fallback payload ledger: {String(packetPayloadLedger.length + factorPayloadLedger.length + nextPayloadLedger.length + taskCatalogPayloadLedger.length + taskIndexPayloadLedger.length)}</p>
          <p>GET cache 仍不调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。</p>
          <DataLineageTable rows={envelopeLedgerRows} />
        </PacketCard>
        <PacketCard title="Legacy bridge cache" subtitle="GET cache，只读旧工作台桥接，不运行旧工具" status={String(legacyBridge.status ?? "cache")}>
          <p>checklist done/pending: {String(legacyCounts?.checklist_done_count ?? 0)} / {String(legacyCounts?.checklist_pending_count ?? 0)}</p>
          <p>bridge / absence: {String(legacyCounts?.bridge_item_count ?? 0)} / {String(legacyCounts?.absence_item_count ?? 0)}</p>
          <p>external calls: {String(legacyBridge.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="市场环境 cache" subtitle="GET cache，只读盘面资金/情绪/两融，不刷新行情" status={String(market.status ?? "cache")}>
          <p>trade date: {String(market.trade_date ?? "--")}</p>
          <p>packets ready/missing: {String(marketCounts?.ready_count ?? 0)} / {String(marketCounts?.missing_count ?? 0)}</p>
          <p>external calls: {String(market.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="交易纪律 cache" subtitle="GET cache，只读纪律闭环，不运行回测" status={String(discipline.status ?? "cache")}>
          <p>discipline score: {String(disciplinePacket?.score ?? "--")}</p>
          <p>loop ready / blocked: {String(disciplineCounts?.loop_ready_count ?? 0)} / {String(disciplineCounts?.loop_blocked_count ?? 0)}</p>
          <p>refresh steps: {String(disciplineCounts?.refresh_step_count ?? 0)}</p>
        </PacketCard>
        <PacketCard title="次日操作图谱 cache" subtitle="GET cache，不刷新，不改 action" status={String(next.status ?? "cache")}>
          <p>{String(next.summary ?? "等待缓存")}</p>
          <p>legacy projection: {String((next.legacy_projection_cache as Record<string, unknown> | undefined)?.available ?? false)}</p>
          <p>envelope ledger / warnings: {String(nextEnvelopeLedger.length)} / {String(nextEnvelopeWarnings.length)}</p>
        </PacketCard>
        <PacketCard title="恢复中心 cache" subtitle="GET cache，只读恢复路线，不执行恢复动作" status={String(recovery.status ?? "cache")}>
          <p>actions / timeline: {String(recoveryCounts?.action_count ?? 0)} / {String(recoveryCounts?.timeline_count ?? 0)}</p>
          <p>provider recovery: {String(recoveryCounts?.provider_recovery_count ?? 0)}</p>
          <p>external calls: {String(recovery.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="数据健康 cache" subtitle="GET cache，只读健康时间线，不 ping provider" status={String(dataHealth.status ?? "cache")}>
          <p>timeline / provider: {String(dataHealthCounts?.timeline_count ?? 0)} / {String(dataHealthCounts?.provider_count ?? 0)}</p>
          <p>capability / gaps: {String(dataHealthCounts?.capability_count ?? 0)} / {String(dataHealthCounts?.gap_count ?? 0)}</p>
          <p>external calls: {String(dataHealth.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="桌面壳预检 cache" subtitle="GET cache，只读 React/Tauri scaffold，不运行构建命令" status={String(desktopPreflight.status ?? "cache")}>
          <p>required files: {String(desktopCounts?.required_file_ready_count ?? 0)} / {String(desktopCounts?.required_file_count ?? 0)}</p>
          <p>vite dev ready: {String(desktopRuntime?.vite_dev_ready ?? false)}</p>
          <p>tauri dev ready: {String(desktopRuntime?.tauri_dev_ready ?? false)}</p>
          <p>external calls: {String(desktopPreflight.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="持仓画像 cache" subtitle="GET cache，只读持仓上下文，不改 action" status={String(position.status ?? "cache")}>
          <p>ticker: {String(positionSummary?.ticker ?? "--")}</p>
          <p>shares: {String(positionSummary?.shares ?? "--")}</p>
          <p>external calls: {String(position.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="候选雷达 cache" subtitle="GET cache，只读下一票候选，不扫描" status={String(candidates.status ?? "cache")}>
          <p>candidate count: {String(candidateCounts?.candidate_count ?? 0)}</p>
          <p>ready / observe / verify: {String(candidateCounts?.ready_count ?? 0)} / {String(candidateCounts?.observe_count ?? 0)} / {String(candidateCounts?.verify_count ?? 0)}</p>
          <p>external calls: {String(candidates.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="风险护栏 cache" subtitle="GET cache，只读风险边界，不清除风险标记" status={String(risk.status ?? "cache")}>
          <p>data gaps: {String(riskCounts?.data_gap_count ?? 0)}</p>
          <p>must not do / reduce: {String(riskCounts?.must_not_do_count ?? 0)} / {String(riskCounts?.reduce_condition_count ?? 0)}</p>
          <p>external calls: {String(risk.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="Factor Quant Hub cache" subtitle="多因子量化图谱 cache-only" status={String((factor.runtime as Record<string, unknown> | undefined)?.status ?? "cache")}>
          <p>mode: {String(factor.mode ?? "cache_only")}</p>
          <p>coverage: {String((factor.runtime as Record<string, unknown> | undefined)?.coverage ?? "--")}</p>
          <p>score chart: {String(factorScoreChartContract?.schema_version ?? "missing")}</p>
          <p>frontend computes trade action: {String(factorScoreChartContract?.frontend_computes_trade_action ?? false)}</p>
          <p>envelope ledger / warnings: {String(factorEnvelopeLedger.length)} / {String(factorEnvelopeWarnings.length)}</p>
          <p>core action: {String((factor.governance as Record<string, unknown> | undefined)?.allow_core_action ?? false)}</p>
        </PacketCard>
        <PacketCard title="Serenity 方法雷达 cache" subtitle="本地方法来源基线" status={String(serenity.github_status ?? "local")}>
          <p>DeepSeek: 不调用</p>
          <p>repositories: {String((serenity.repositories as unknown[] | undefined)?.length ?? 0)}</p>
        </PacketCard>
        <PacketCard title="DeepSeek 模型策略" subtitle="独立 cache；不展示 token/key，不触发模型调用" status={modelStrategy.contains_secret === true ? "check" : "safe"}>
          <p>purpose count: {String(deepseekModelCounts?.purpose_count ?? 0)}</p>
          <p>explain: {String(deepseekModelByPurpose.get("explain")?.model ?? "--")}</p>
          <p>fast: {String(deepseekModelByPurpose.get("fast")?.model ?? "--")}</p>
          <p>default: {String(deepseekModelByPurpose.get("default")?.model ?? "--")}</p>
          <p>external calls: {String(modelStrategy.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="产业链瓶颈扫描 cache" subtitle="GET cache 不触发 DeepSeek" status={String(chokepoint.status ?? "cache")}>
          <p>{String(chokepoint.summary ?? "等待缓存")}</p>
        </PacketCard>
        <PacketCard title="Parquet / DuckDB Storage" subtitle="daily / moneyflow / factor_values 只读状态，不触发刷新" status={String(storageOverview.store ?? "parquet_duckdb")}>
          <p>datasets: {String(storageDatasets?.length ?? 0)}</p>
          <p>factor_values: {String(storageStatus?.factor_values ?? "missing")}</p>
          <p>daily: {String(storageStatus?.daily ?? "missing")}</p>
          <p>moneyflow: {String(storageStatus?.moneyflow ?? "missing")}</p>
          <JsonDetails title="storage overview" data={storageOverview} />
        </PacketCard>
        <PacketCard title="任务状态" subtitle="POST 返回 task_id，页面轮询 FastAPI" status="local">
          <p>task_status_index: {String(taskIndex?.packet_key ?? "--")}</p>
          <p>最近任务数：{String(taskIndex?.task_count ?? tasks.length)}</p>
          <p>status counts: {JSON.stringify(taskIndex?.status_counts ?? {})}</p>
          <p>call ledger: {String(taskIndex?.call_ledger_count ?? 0)}</p>
          <p>external calls: {String(taskIndex?.external_calls_triggered ?? false)}</p>
          <p>does_not_execute_trades: {String(taskIndex?.does_not_execute_trades ?? true)}</p>
          <p>does_not_modify_strategy_action: {String(taskIndex?.does_not_modify_strategy_action ?? true)}</p>
          <JsonDetails title="任务状态总览" data={taskIndex ?? {}} />
          <JsonDetails title="任务列表" data={tasks} />
        </PacketCard>
        <PacketCard title="任务目录" subtitle="只读 catalog；POST task 才可能触发外部请求" status={String(taskCatalog.status ?? "catalog")}>
          <p>catalog tasks: {String(taskCatalogItems?.length ?? 0)}</p>
          <p>all button gated: {String(taskCatalogPolicy?.all_tasks_button_gated ?? true)}</p>
          <p>call ledger required: {String(taskCatalogPolicy?.call_ledger_required_for_all ?? true)}</p>
          <JsonDetails title="任务目录明细" data={taskCatalogItems ?? []} />
        </PacketCard>
        <PacketCard title="Worker runtime cache" subtitle="GET cache，只读 worker scaffold，不连接 Redis" status={String(workerRuntime.status ?? "cache")}>
          <p>modules ready: {String(workerCounts?.worker_module_ready_count ?? 0)} / {String(workerCounts?.worker_module_count ?? 0)}</p>
          <p>local fallback: {String(workerRuntimeState?.local_fallback_enabled ?? true)}</p>
          <p>redis pinged: {String(workerRuntime.redis_pinged ?? false)}</p>
        </PacketCard>
      </div>
    </>
  );
}
