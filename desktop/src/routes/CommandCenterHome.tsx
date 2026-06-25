import { useEffect, useState } from "react";
import { API_BASE_CANDIDATE_DISPLAY_URLS, API_BASE_DISPLAY_URL, CONFIGURED_API_BASE_DISPLAY_URL, getAuditCache, getBootstrapStatus, getCandidateRadarCache, getChokepointCache, getDataHealthCache, getDesktopPreflightCache, getDisciplineLoopCache, getFactorQuantCache, getHealth, getLegacyBridgeCache, getMarketContextCache, getMigrationStatus, getModelStrategyCache, getNextSessionCache, getPackets, getPositionCache, getRecoveryCenterCache, getRiskGuardrailsCache, getSerenityCache, getStorageCatalog, getStorageOverview, getTaskCatalog, getTasks, getWorkerRuntimeCache, postBootstrapLiveStartup, postCandidateRadarQuantProjection, type TaskCreationEnvelope, type TaskStatusIndex } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid, { type MetricItem } from "../components/MetricGrid";
import PageStateBanner from "../components/PageStateBanner";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

const LIVE_BOOTSTRAP_SESSION_KEY = "command_center_3_live_bootstrap_session_key";

function readLiveBootstrapSessionKey(): string {
  try {
    return window.sessionStorage.getItem(LIVE_BOOTSTRAP_SESSION_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeLiveBootstrapSessionKey(value: string) {
  try {
    window.sessionStorage.setItem(LIVE_BOOTSTRAP_SESSION_KEY, value);
  } catch {
    // Session storage can be unavailable in privacy modes; backend rate-limit still protects the task.
  }
}

function normalizeHomeAshareSymbolInput(raw: string) {
  const input = raw.trim().toUpperCase().replace(/\s+/g, "");
  if (!input) return { input, normalized: "", valid: false, reason: "empty_symbol" };
  const explicit = input.match(/^(\d{6})\.(SH|SZ|BJ)$/);
  if (explicit) return { input, normalized: `${explicit[1]}.${explicit[2]}`, valid: true, reason: "explicit_market_suffix" };
  const digits = input.match(/^(\d{6})$/);
  if (!digits) return { input, normalized: "", valid: false, reason: "require_6_digits_or_suffix" };
  const symbol = digits[1];
  const inferredMarket = /^(60|68|90)/.test(symbol)
    ? "SH"
    : /^(00|30|20)/.test(symbol)
      ? "SZ"
      : /^(43|83|87|88|92)/.test(symbol)
        ? "BJ"
        : "";
  if (!inferredMarket) return { input, normalized: "", valid: false, reason: "unknown_market_prefix" };
  return { input, normalized: `${symbol}.${inferredMarket}`, valid: true, reason: "market_suffix_inferred" };
}

function dailyCommandReadableGap(value: unknown) {
  const text = String(value ?? "").trim();
  if (!text) return "";
  const known: Record<string, string> = {
    "Factor/Next/ECharts local cache replay": "量化推演、次日图谱和图表本地缓存待刷新",
    "Factor Quant Hub refresh evidence": "股票量化推演刷新证据待补",
    "Next Session/ECharts cache refresh evidence": "次日图谱和图表缓存证据待补",
    "optional DeepSeek pro model ledger": "DeepSeek governed executor 单独补",
    "freshness expected_trade_date evidence": "交易日 freshness 证据待补",
  };
  return known[text] ?? text.replace(/_/g, " ");
}

function dailyCommandReadableEntry(value: unknown) {
  const text = String(value ?? "").trim();
  const known: Record<string, string> = {
    readable_conclusion: "P3 结果速读",
    replay_quant_projection: "股票量化推演",
    replay_next_session_map: "次日图谱",
    candidate_pool: "下一票雷达",
  };
  return known[text] ?? text;
}

export default function CommandCenterHome() {
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [healthEnvelopeLedger, setHealthEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [healthEnvelopeWarnings, setHealthEnvelopeWarnings] = useState<Array<string>>([]);
  const [audit, setAudit] = useState<Record<string, unknown>>({});
  const [bootstrapStatus, setBootstrapStatus] = useState<Record<string, unknown>>({});
  const [bootstrapEnvelopeLedger, setBootstrapEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [bootstrapEnvelopeWarnings, setBootstrapEnvelopeWarnings] = useState<Array<string>>([]);
  const [liveBootstrapReceipt, setLiveBootstrapReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [liveBootstrapTaskId, setLiveBootstrapTaskId] = useState("");
  const [liveBootstrapManualStatus, setLiveBootstrapManualStatus] = useState("not_checked");
  const [homeQuantSymbol, setHomeQuantSymbol] = useState("");
  const [homeQuantSymbolTouched, setHomeQuantSymbolTouched] = useState(false);
  const [homeQuantSubmitting, setHomeQuantSubmitting] = useState(false);
  const [homeQuantReceipt, setHomeQuantReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [homeQuantTaskId, setHomeQuantTaskId] = useState("");
  const [homeQuantSubmitError, setHomeQuantSubmitError] = useState("");
  const [packets, setPackets] = useState<Record<string, unknown>>({});
  const [packetEnvelopeLedger, setPacketEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [market, setMarket] = useState<Record<string, unknown>>({});
  const [marketEnvelopeLedger, setMarketEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [marketEnvelopeWarnings, setMarketEnvelopeWarnings] = useState<Array<string>>([]);
  const [discipline, setDiscipline] = useState<Record<string, unknown>>({});
  const [disciplineEnvelopeLedger, setDisciplineEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [disciplineEnvelopeWarnings, setDisciplineEnvelopeWarnings] = useState<Array<string>>([]);
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
  const [serenityEnvelopeLedger, setSerenityEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [serenityEnvelopeWarnings, setSerenityEnvelopeWarnings] = useState<Array<string>>([]);
  const [chokepoint, setChokepoint] = useState<Record<string, unknown>>({});
  const [chokepointEnvelopeLedger, setChokepointEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [chokepointEnvelopeWarnings, setChokepointEnvelopeWarnings] = useState<Array<string>>([]);
  const [storageOverview, setStorageOverview] = useState<Record<string, unknown>>({});
  const [storageCatalog, setStorageCatalog] = useState<Record<string, unknown>>({});
  const [storageCatalogEnvelopeLedger, setStorageCatalogEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [storageCatalogEnvelopeWarnings, setStorageCatalogEnvelopeWarnings] = useState<Array<string>>([]);
  const [migration, setMigration] = useState<Record<string, unknown>>({});
  const [modelStrategy, setModelStrategy] = useState<Record<string, unknown>>({});
  const [legacyBridge, setLegacyBridge] = useState<Record<string, unknown>>({});
  const [taskCatalog, setTaskCatalog] = useState<Record<string, unknown>>({});
  const [taskCatalogEnvelopeLedger, setTaskCatalogEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [taskIndex, setTaskIndex] = useState<TaskStatusIndex | null>(null);
  const [taskIndexEnvelopeLedger, setTaskIndexEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [workerRuntime, setWorkerRuntime] = useState<Record<string, unknown>>({});
  const [tasks, setTasks] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let pending = 0;
    const track = <T extends { ok?: boolean; error?: string | null }>(
      label: string,
      promise: Promise<T>,
      onReady: (res: T) => void
    ) => {
      pending += 1;
      void promise.then((res) => {
        if (cancelled) return;
        onReady(res);
        if (res.ok === false) setError((current) => current || `${label}: ${res.error ?? "request_not_ok"}`);
      }).catch((err) => {
        if (cancelled) return;
        setError((current) => current || `${label}: ${err instanceof Error ? err.message : String(err)}`);
      }).finally(() => {
        pending -= 1;
        if (!cancelled && pending <= 0) setLoading(false);
      });
    };

    setLoading(true);
    setError("");
    track("health", getHealth(), (res) => {
      setHealth(res.data);
      setHealthEnvelopeLedger(res.call_ledger ?? []);
      setHealthEnvelopeWarnings(res.warnings ?? []);
    });
    track("audit", getAuditCache(), (res) => setAudit(res.data));
    track("bootstrap", getBootstrapStatus(), (res) => {
      setBootstrapStatus(res.data);
      setBootstrapEnvelopeLedger(res.call_ledger ?? []);
      setBootstrapEnvelopeWarnings(res.warnings ?? []);
    });
    track("packets", getPackets(), (res) => {
      setPacketEnvelopeLedger(res.call_ledger ?? []);
      setPackets(res.data);
    });
    track("market", getMarketContextCache(), (res) => {
      setMarketEnvelopeLedger(res.call_ledger ?? []);
      setMarketEnvelopeWarnings(res.warnings ?? []);
      setMarket(res.data);
    });
    track("discipline", getDisciplineLoopCache(), (res) => {
      setDisciplineEnvelopeLedger(res.call_ledger ?? []);
      setDisciplineEnvelopeWarnings(res.warnings ?? []);
      setDiscipline(res.data);
    });
    track("factor", getFactorQuantCache(), (res) => {
      setFactorEnvelopeLedger(res.call_ledger ?? []);
      setFactorEnvelopeWarnings(res.warnings ?? []);
      setFactor(res.data);
    });
    track("next", getNextSessionCache(), (res) => {
      setNextEnvelopeLedger(res.call_ledger ?? []);
      setNextEnvelopeWarnings(res.warnings ?? []);
      setNext(res.data);
    });
    track("data_health", getDataHealthCache(), (res) => setDataHealth(res.data));
    track("desktop_preflight", getDesktopPreflightCache(), (res) => setDesktopPreflight(res.data));
    track("recovery", getRecoveryCenterCache(), (res) => setRecovery(res.data));
    track("position", getPositionCache(), (res) => setPosition(res.data));
    track("candidates", getCandidateRadarCache(), (res) => setCandidates(res.data));
    track("risk", getRiskGuardrailsCache(), (res) => setRisk(res.data));
    track("serenity", getSerenityCache(), (res) => {
      setSerenityEnvelopeLedger(res.call_ledger ?? []);
      setSerenityEnvelopeWarnings(res.warnings ?? []);
      setSerenity(res.data);
    });
    track("chokepoint", getChokepointCache(), (res) => {
      setChokepointEnvelopeLedger(res.call_ledger ?? []);
      setChokepointEnvelopeWarnings(res.warnings ?? []);
      setChokepoint(res.data);
    });
    track("storage", getStorageOverview(), (res) => setStorageOverview(res.data));
    track("storage_catalog", getStorageCatalog(), (res) => {
      setStorageCatalogEnvelopeLedger(res.call_ledger ?? []);
      setStorageCatalogEnvelopeWarnings(res.warnings ?? []);
      setStorageCatalog(res.data);
    });
    track("migration", getMigrationStatus(), (res) => setMigration(res.data));
    track("model_strategy", getModelStrategyCache(), (res) => setModelStrategy(res.data));
    track("legacy", getLegacyBridgeCache(), (res) => setLegacyBridge(res.data));
    track("task_catalog", getTaskCatalog(), (res) => {
      setTaskCatalogEnvelopeLedger(res.call_ledger ?? []);
      setTaskCatalog(res.data);
    });
    track("worker", getWorkerRuntimeCache(), (res) => setWorkerRuntime(res.data));
    track("tasks", getTasks(), (res) => {
      setTaskIndexEnvelopeLedger(res.call_ledger ?? []);
      setTaskIndex(res.data);
      setTasks(res.data.tasks ?? []);
    });

    return () => {
      cancelled = true;
    };
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
  const storageCatalogRows = storageCatalog.dataset_catalog as Array<Record<string, unknown>> | undefined;
  const storageCatalogPayloadLedger = (storageCatalog.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const storageCatalogLedger = storageCatalogEnvelopeLedger.length ? storageCatalogEnvelopeLedger : storageCatalogPayloadLedger;
  const storageCatalogWarnings = storageCatalogEnvelopeWarnings.length ? storageCatalogEnvelopeWarnings : ((storageCatalog.warnings as Array<string> | undefined) ?? []);
  const deepseekModelRows = modelStrategy.model_rows as Array<Record<string, unknown>> | undefined;
  const deepseekModelCounts = modelStrategy.counts as Record<string, unknown> | undefined;
  const deepseekModelByPurpose = new Map((deepseekModelRows ?? []).map((row) => [String(row.purpose), row]));
  const deepseekPurposeGroups = (modelStrategy.purpose_groups as Record<string, unknown> | undefined) ?? {};
  const deepseekHomeRows = (deepseekModelRows ?? []).map((row) => ({
    purpose: row.purpose,
    model: row.model,
    config_keys: Array.isArray(row.config_keys) ? row.config_keys.join(" / ") : row.config_keys,
    no_hardcoded_model: row.does_not_hardcode_model === true,
    contains_secret: row.contains_secret === true,
    cache_read_external_call: row.external_call_on_cache_read === true
  }));
  const migrationProgress = migration.progress_baseline as Array<Record<string, unknown>> | undefined;
  const migrationLongTermGoals = migration.long_term_goal_rows as Array<Record<string, unknown>> | undefined;
  const migrationLongTermSummary = migration.long_term_goal_summary as Record<string, unknown> | undefined;
  const migrationTushareDeepseekLinkage = migration.tushare_deepseek_linkage_review as Record<string, unknown> | undefined;
  const migrationTushareDeepseekLinkageRows = migration.tushare_deepseek_linkage_rows as Array<Record<string, unknown>> | undefined;
  const migrationPolicy = migration.api_policy as Record<string, unknown> | undefined;
  const dataHealthCounts = dataHealth.counts as Record<string, unknown> | undefined;
  const desktopRuntime = desktopPreflight.runtime as Record<string, unknown> | undefined;
  const desktopCounts = desktopPreflight.counts as Record<string, unknown> | undefined;
  const oneClickStartupSummary = (desktopPreflight.one_click_startup_summary as Record<string, unknown> | undefined) ?? {};
  const p0RecoveryStepSourceRows = (desktopPreflight.p0_recovery_steps as Array<Record<string, unknown>> | undefined) ??
    ((oneClickStartupSummary.ordinary_recovery_steps as Array<Record<string, unknown>> | undefined) ?? []);
  const dailyCommandP0RecoveryRows = p0RecoveryStepSourceRows.length ? p0RecoveryStepSourceRows.map((row) => ({
    步骤: row.title ? `${String(row.step ?? "")}. ${String(row.title)}` : String(row.step ?? "恢复步骤"),
    何时使用: String(row.when ?? "本地联通异常或页面未打开"),
    用户动作: String(row.action ?? "回到一键启动预检查看失败段"),
    检查项: String(row.checks ?? "FastAPI / bootstrap status / desktop preflight cache / React/Vite"),
    边界: "只读展示 p0_recovery_steps；首页不启动 FastAPI/Vite、不创建 task、不调用 provider/model"
  })) : [
    {
      步骤: "1. 打开本地一键入口",
      何时使用: "页面未打开、健康页显示 check，或本地后端离线",
      用户动作: "双击 stock-MING Command Center 3.command；或运行 scripts/start_command_center_3.command。",
      检查项: "启动器会依次等待 FastAPI /health、/api/bootstrap/status、/api/desktop/preflight-cache 和 React/Vite HTML。",
      边界: "只读展示 fallback recovery steps；首页不启动 FastAPI/Vite、不创建 task、不调用 provider/model"
    },
    {
      步骤: "2. 按启动器诊断定位失败段",
      何时使用: "启动器没有自动打开页面",
      用户动作: "先看 FastAPI、bootstrap status、desktop preflight cache、React/Vite 哪一段没有 ready。",
      检查项: "对应检查 8710/5173 端口占用和本地 fastapi/vite 日志。",
      边界: "只读展示 fallback recovery steps；首页不启动 FastAPI/Vite、不创建 task、不调用 provider/model"
    },
    {
      步骤: "3. 刷新健康页确认联通",
      何时使用: "启动器显示四个检查都 ready 后",
      用户动作: "回到系统健康页，确认 P0 front/back、P0 receipt 和 one-click launcher 都为 ready。",
      检查项: "本页只读 GET /health 与 GET /api/desktop/preflight-cache。",
      边界: "只读展示 fallback recovery steps；首页不启动 FastAPI/Vite、不创建 task、不调用 provider/model"
    }
  ];
  const p0OrdinaryQuickActionRows = (desktopPreflight.p0_ordinary_quick_action_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const p0LauncherCheckOnlyRows = (desktopPreflight.p0_launcher_check_only_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const p0CurrentNextActionSourceRows = (desktopPreflight.p0_current_next_action_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const p0CurrentNextActionRows = p0CurrentNextActionSourceRows.length
    ? p0CurrentNextActionSourceRows
    : [
        {
          行动项: "1. 当前主入口",
          当前状态: "等待 desktop preflight 当前下一步回读",
          用户下一步: "先看一键启动预检；四段 ready 后再进入下一票雷达",
          入口: "#desktop",
          边界: "首页只读展示 fallback；不启动服务、不创建 task、不调用 provider/model。"
        },
        {
          行动项: "2. P1 确认按钮",
          当前状态: "等待 P0 ready",
          用户下一步: "代码通过本地校验后点击确认按钮，才创建 Tushare-first POST task；DeepSeek skipped。",
          入口: "下一票雷达确认按钮",
          边界: "页面打开、搜索输入和本表回读都不外联；只有确认按钮可进入 P1 task / worker。"
        }
      ];
  const desktopLauncherContract = (desktopPreflight.desktop_launcher_contract as Record<string, unknown> | undefined) ?? {};
  const recoveryCounts = recovery.counts as Record<string, unknown> | undefined;
  const taskCatalogPolicy = taskCatalog.policy as Record<string, unknown> | undefined;
  const taskCatalogItems = taskCatalog.tasks as Array<Record<string, unknown>> | undefined;
  const taskRouteCoverage = taskCatalog.route_coverage as Record<string, unknown> | undefined;
  const taskImplementationStatus = taskCatalog.implementation_status as Record<string, unknown> | undefined;
  const taskUncoveredPostRoutes = taskRouteCoverage?.uncovered_post_routes as unknown[] | undefined;
  const legacyCounts = legacyBridge.counts as Record<string, unknown> | undefined;
  const workerCounts = workerRuntime.counts as Record<string, unknown> | undefined;
  const workerRuntimeState = workerRuntime.runtime as Record<string, unknown> | undefined;
  const positionSummary = position.position_summary as Record<string, unknown> | undefined;
  const candidateCounts = candidates.counts as Record<string, unknown> | undefined;
  const candidatePolicy = (candidates.policy as Record<string, unknown> | undefined) ?? {};
  const candidateQuantReceipt = (candidates.search_quant_projection_receipt as Record<string, unknown> | undefined) ?? {};
  const candidateQuantSmallDataWriteback = (candidates.search_quant_projection_small_data_writeback_summary as Record<string, unknown> | undefined) ?? {};
  const candidateQuantSmallDataReadbackCheckpoint =
    (candidates.search_quant_projection_small_data_readback_checkpoint as Record<string, unknown> | undefined) ?? {};
  const candidateQuantP2ThreeSurfaceCheckpoint =
    (candidates.ordinary_p2_three_surface_checkpoint as Record<string, unknown> | undefined) ??
    (candidateQuantSmallDataWriteback.ordinary_p2_three_surface_checkpoint as Record<string, unknown> | undefined) ??
    {};
  const candidateQuantOneScreenActionRows = (candidateQuantSmallDataWriteback.ordinary_one_screen_action_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const candidateQuantConfirmOutcomeRows = (candidateQuantSmallDataWriteback.ordinary_confirm_outcome_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const candidateQuantConfirmedTaskReceiptRows =
    (candidates.search_quant_projection_confirmed_task_receipt_rows as Array<Record<string, unknown>> | undefined) ??
    (candidates.ordinary_confirmed_task_receipt_rows as Array<Record<string, unknown>> | undefined) ??
    (candidateQuantSmallDataWriteback.ordinary_confirmed_task_receipt_rows as Array<Record<string, unknown>> | undefined) ??
    [];
  const candidateQuantTaskReadbackRows =
    (candidates.search_quant_projection_task_readback_rows as Array<Record<string, unknown>> | undefined) ??
    (candidates.ordinary_task_readback_rows as Array<Record<string, unknown>> | undefined) ??
    (candidateQuantSmallDataWriteback.ordinary_task_readback_rows as Array<Record<string, unknown>> | undefined) ??
    [];
  const candidateQuantTushareFirstRows =
    (candidates.ordinary_tushare_first_chain_rows as Array<Record<string, unknown>> | undefined) ??
    (candidateQuantSmallDataWriteback.ordinary_tushare_first_chain_rows as Array<Record<string, unknown>> | undefined) ??
    [];
  const candidateQuantWritebackSurfaceRows = (candidateQuantSmallDataWriteback.ordinary_writeback_surface_summary_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const candidateQuantConfirmChainCheckpoint = (candidates.search_quant_projection_confirm_chain_checkpoint as Record<string, unknown> | undefined) ?? {};
  const dailyCommandTushareFirstLedgerReady =
    candidateQuantConfirmChainCheckpoint.provider_ledger_ready === true ||
    candidateQuantReceipt.p1_tushare_first_provider_ledger_ready === true;
  const dailyCommandTushareFirstApiCount = Number(
    candidateQuantConfirmChainCheckpoint.provider_api_call_count ??
      candidateQuantSmallDataWriteback.provider_call_ledger_api_count ??
      0
  );
  const dailyCommandTushareFirstSuccessCount = Number(
    candidateQuantConfirmChainCheckpoint.provider_api_success_count ??
      candidateQuantSmallDataWriteback.provider_api_success_count ??
      0
  );
  const dailyCommandTushareFirstStatus = String(
    candidateQuantConfirmChainCheckpoint.ordinary_status ??
      candidateQuantConfirmChainCheckpoint.status ??
      candidateQuantReceipt.p1_confirm_chain_status ??
      "等待确认按钮创建 Tushare-first task"
  );
  const dailyCommandTushareFirstLedgerLabel = dailyCommandTushareFirstLedgerReady
    ? `Tushare-first ledger 已回放：${dailyCommandTushareFirstSuccessCount}/${dailyCommandTushareFirstApiCount} 个接口`
    : "等待确认按钮后的 Tushare-first provider ledger";
  const dailyCommandTushareFirstDeepSeekLabel =
    candidateQuantConfirmChainCheckpoint.deepseek_called_from_confirm_chain === false ||
    candidateQuantReceipt.p1_deepseek_skipped_by_request === true
      ? "DeepSeek skipped：P5 governed executor 单独补"
      : "DeepSeek 等 governed executor；不阻塞 P1/P2/P3";
  const dailyCommandTushareFirstBoundary =
    "P1 只允许首页或下一票雷达确认按钮创建 Tushare-first POST task；首页回放卡只读 cache / ledger / packet，不创建第二个 task。";
  const dailyCommandTushareFirstRows = candidateQuantTushareFirstRows.length
    ? candidateQuantTushareFirstRows.map((row) => ({
        链路段: String(row["步骤"] ?? row.chain_step ?? row["链路段"] ?? "Tushare-first"),
        当前状态: String(row["当前状态"] ?? row.status ?? dailyCommandTushareFirstStatus),
        用户下一步: String(row["用户下一步"] ?? row.next_step ?? "按任务状态和本地回放继续复核"),
        证据: String(row["证据"] ?? row.evidence ?? "ordinary_tushare_first_chain_rows"),
        边界: String(row["边界"] ?? row.boundary ?? dailyCommandTushareFirstBoundary)
      }))
    : [
        {
          链路段: "1. 输入静默",
          当前状态: "等待本地格式校验",
          用户下一步: "输入 6 位 A 股代码；输入本身不创建 task",
          证据: "home symbol input local validation",
          边界: "页面打开、输入和 React render 不调用 Tushare/DeepSeek。"
        },
        {
          链路段: "2. 确认按钮",
          当前状态: dailyCommandTushareFirstStatus,
          用户下一步: "点击首页或下一票雷达确认按钮创建 Tushare-first POST task",
          证据: "POST /api/candidate-radar/quant-projection",
          边界: dailyCommandTushareFirstBoundary
        },
        {
          链路段: "3. Tushare ledger",
          当前状态: dailyCommandTushareFirstLedgerLabel,
          用户下一步: "ledger 可回放后继续看 P2 三面和 P3 结论",
          证据: "post_task_call_ledger",
          边界: "Tushare 只允许按钮门控 task / worker 调用；GET cache 只读回放。"
        },
        {
          链路段: "4. DeepSeek",
          当前状态: dailyCommandTushareFirstDeepSeekLabel,
          用户下一步: "先使用 Tushare-first 和基础图谱；DeepSeek 后续单独补证",
          证据: "deepseek_skipped_by_request",
          边界: "DeepSeek 不作为数据源，不覆盖价格、持仓、factor、operation_zones 或 strategy action。"
        }
      ];
  const dailyCommandP1ConfirmTaskReadbackRows = [
    ...candidateQuantConfirmedTaskReceiptRows.map((row) => ({
      回放项: String(row.receipt_item ?? row["回放项"] ?? "确认回执"),
      当前状态: String(row.status ?? row["当前状态"] ?? "waiting_confirm"),
      用户读法: String(row.ordinary_label ?? row["用户读法"] ?? "等待确认按钮回执"),
      来源: String(row.readback_source ?? row["来源"] ?? "CandidateRadar cache"),
      边界: String(row.boundary ?? row["边界"] ?? "GET cache 只读回放；不创建第二个 task")
    })),
    ...candidateQuantTaskReadbackRows.map((row) => ({
      回放项: String(row.surface ?? row["回放项"] ?? "任务状态"),
      当前状态: String(row.status ?? row["当前状态"] ?? "waiting_task"),
      用户读法: String(row.ordinary_label ?? row["用户读法"] ?? "等待本地 task 状态"),
      来源: String(row.readback_source ?? row["来源"] ?? "local task status"),
      边界: String(row.boundary ?? row["边界"] ?? "只读任务状态；不调用 provider/model")
    }))
  ];
  const dailyCommandSmallDataWritebackState = String(
    candidateQuantSmallDataWriteback.ordinary_readback_stage_label ??
      candidateQuantSmallDataWriteback.summary_label ??
      "等待确认按钮后的 cache / ledger / packet 回放"
  );
  const dailyCommandP2SurfaceCount = Number(
    candidateQuantP2ThreeSurfaceCheckpoint.surface_count ??
      candidateQuantSmallDataReadbackCheckpoint.surface_count ??
      3
  );
  const dailyCommandP2ReadableSurfaceCount = Number(
    candidateQuantP2ThreeSurfaceCheckpoint.readable_surface_count ??
      candidateQuantSmallDataReadbackCheckpoint.readable_surface_count ??
      0
  );
  const dailyCommandP2CompleteSurfaceCount = Number(
    candidateQuantP2ThreeSurfaceCheckpoint.complete_surface_count ??
      candidateQuantSmallDataReadbackCheckpoint.complete_surface_count ??
      0
  );
  const dailyCommandP2CheckpointLabel = String(
    candidateQuantP2ThreeSurfaceCheckpoint.ordinary_label ??
      candidateQuantSmallDataReadbackCheckpoint.ordinary_readback_summary ??
      dailyCommandSmallDataWritebackState
  );
  const dailyCommandP2CallLedgerState = String(
    candidateQuantP2ThreeSurfaceCheckpoint.call_ledger_state ??
      candidateQuantSmallDataReadbackCheckpoint.call_ledger_state ??
      candidateQuantSmallDataWriteback.provider_call_source ??
      "waiting_provider_ledger"
  );
  const dailyCommandP2SurfaceCompletionLabel =
    `${dailyCommandP2ReadableSurfaceCount}/${dailyCommandP2SurfaceCount} 面可读，${dailyCommandP2CompleteSurfaceCount}/${dailyCommandP2SurfaceCount} 面完整`;
  const dailyCommandP2ThreeSurfaceReady =
    candidateQuantP2ThreeSurfaceCheckpoint.status === "p2_three_surface_ready" ||
    candidateQuantSmallDataReadbackCheckpoint.p2_three_surface_ready === true ||
    candidateQuantSmallDataWriteback.p2_three_surface_ready === true;
  const dailyCommandP2CacheReady =
    candidateQuantSmallDataReadbackCheckpoint.cache_ready === true ||
    candidateQuantSmallDataWriteback.cache_ready === true ||
    candidates.search_quant_projection_p2_cache_ready === true;
  const dailyCommandP2LedgerReady =
    candidateQuantSmallDataReadbackCheckpoint.ledger_ready === true ||
    candidateQuantSmallDataReadbackCheckpoint.provider_ledger_ready === true ||
    candidateQuantSmallDataWriteback.ledger_ready === true ||
    candidateQuantSmallDataWriteback.provider_call_ledger_written === true ||
    candidates.search_quant_projection_p2_ledger_ready === true;
  const dailyCommandP2PacketReady =
    candidateQuantSmallDataReadbackCheckpoint.packet_ready === true ||
    candidateQuantSmallDataReadbackCheckpoint.packet_written === true ||
    candidateQuantSmallDataWriteback.packet_ready === true ||
    candidateQuantSmallDataWriteback.cache_packet_written === true ||
    candidates.search_quant_projection_p2_packet_ready === true;
  const dailyCommandSmallDataWritebackBoundary =
    "P2 小数据只从 CandidateRadar cache / call_ledger / packet 回放；首页 GET cache 不创建 task、不补调 Tushare/DeepSeek、不展示 token/key 或 raw log。";
  const dailyCommandP2ThreeSurfaceProofItems: MetricItem[] = [
    {
      label: "cache",
      value: dailyCommandP2CacheReady ? "已写入本地 cache；页面刷新只读回放" : "等待本地 cache 写入",
      tone: dailyCommandP2CacheReady ? "good" : "warn"
    },
    {
      label: "call_ledger",
      value: dailyCommandP2LedgerReady ? `已回放 POST task ledger：${dailyCommandP2CallLedgerState}` : "等待确认任务写入 call_ledger",
      tone: dailyCommandP2LedgerReady ? "good" : "warn"
    },
    {
      label: "packet",
      value: dailyCommandP2PacketReady ? "已写入 command_center_3_candidate_radar_cache；不含凭据或交易动作" : "等待 packet 写入",
      tone: dailyCommandP2PacketReady ? "good" : "warn"
    },
    {
      label: "完整度",
      value: dailyCommandP2SurfaceCompletionLabel,
      tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn"
    },
    {
      label: "现在看哪里",
      value: dailyCommandP2ThreeSurfaceReady ? "先看股票量化推演，再看次日图谱" : "先完成确认按钮链路",
      tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn"
    },
    {
      label: "安全边界",
      value: "只读三面证明；不创建 task、不补调 provider/model、不展示 token/key/raw log",
      tone: "good"
    }
  ];
  const dailyCommandSmallDataWritebackRows = candidateQuantWritebackSurfaceRows.length
    ? candidateQuantWritebackSurfaceRows.map((row) => ({
        写入面: String(row["写入面"] ?? row.surface ?? "writeback"),
        当前状态: String(row["当前状态"] ?? row.status ?? dailyCommandSmallDataWritebackState),
        普通读法: String(row["普通读法"] ?? row["普通速读"] ?? row.ordinary_label ?? "确认这一面是否已经可本地回放"),
        回放来源: String(row["回放来源"] ?? row.readback_source ?? "GET /api/candidate-radar/cache"),
        下一步: String(row["下一步"] ?? row.next_action ?? "确认任务完成后刷新本地 cache 回放"),
        边界: String(row["边界"] ?? row.boundary ?? dailyCommandSmallDataWritebackBoundary)
      }))
    : [
        {
          写入面: "cache",
          当前状态: dailyCommandSmallDataWritebackState,
          普通读法: "页面刷新后只读回放本地缓存。",
          回放来源: "search_quant_projection_small_data_writeback_summary",
          下一步: "先去下一票雷达确认输入区输入代码并点击确认",
          边界: dailyCommandSmallDataWritebackBoundary
        },
        {
          写入面: "call_ledger",
          当前状态: "等待 POST task 写入或回放 Tushare-first ledger",
          普通读法: "只确认 Tushare ledger 是否由确认任务写入。",
          回放来源: "ordinary_writeback_surface_summary_rows pending",
          下一步: "任务完成后只读查看 ledger 状态；接口明细留在雷达高级状态",
          边界: "call_ledger 只由按钮门控后台任务产生；首页不补调 provider/model。"
        },
        {
          写入面: "packet",
          当前状态: "等待 candidate radar packet 写入 task id、安全步骤和结果位置",
          普通读法: "回放 task id、安全步骤、结果入口和下一步。",
          回放来源: "command_center_3_candidate_radar_cache",
          下一步: "刷新 cache 后回放股票量化推演和次日图谱",
          边界: "packet 不含凭据、不生成交易动作、不覆盖 strategy action。"
        }
      ];
  const candidateQuantInterpretation = (candidates.search_quant_projection_interpretation_summary as Record<string, unknown> | undefined) ?? {};
  const candidateQuantResultCheckpoint = (candidates.search_quant_projection_result_checkpoint as Record<string, unknown> | undefined) ?? {};
  const candidateQuantQuickRows =
    (candidates.ordinary_result_quick_read_rows as Array<Record<string, unknown>> | undefined) ??
    (candidateQuantInterpretation.ordinary_result_quick_read_rows as Array<Record<string, unknown>> | undefined) ??
    [];
  const candidateQuantDecisionBriefRows =
    (candidates.ordinary_result_decision_brief_rows as Array<Record<string, unknown>> | undefined) ??
    (candidates.search_quant_projection_result_decision_brief_rows as Array<Record<string, unknown>> | undefined) ??
    (candidateQuantInterpretation.ordinary_result_decision_brief_rows as Array<Record<string, unknown>> | undefined) ??
    [];
  const candidateQuantHandoffRows =
    (candidates.ordinary_result_handoff_rows as Array<Record<string, unknown>> | undefined) ??
    (candidateQuantInterpretation.ordinary_result_handoff_rows as Array<Record<string, unknown>> | undefined) ??
    [];
  const candidateQuantCheckpointRows =
    (candidates.ordinary_result_checkpoint_rows as Array<Record<string, unknown>> | undefined) ??
    (candidates.search_quant_projection_result_checkpoint_rows as Array<Record<string, unknown>> | undefined) ??
    (candidateQuantInterpretation.ordinary_result_checkpoint_rows as Array<Record<string, unknown>> | undefined) ??
    [];
  const candidateQuantPostConfirmOneGlanceRows =
    (candidates.search_quant_projection_post_confirm_one_glance_items as Array<Record<string, unknown>> | undefined) ??
    (candidates.ordinary_post_confirm_one_glance_items as Array<Record<string, unknown>> | undefined) ??
    (candidateQuantInterpretation.ordinary_post_confirm_one_glance_items as Array<Record<string, unknown>> | undefined) ??
    [];
  const dailyCommandExplainableResultLabel = String(
    candidates.ordinary_result_summary ??
      candidateQuantInterpretation.ordinary_result_summary ??
      "等待搜票确认后的可解释结果"
  );
  const dailyCommandExplainableResultNext = String(
    candidates.ordinary_result_next_step ??
      candidateQuantInterpretation.ordinary_result_next_step ??
      "先进入下一票雷达输入代码并点击确认"
  );
  const dailyCommandExplainableResultBoundary = String(
    candidates.ordinary_result_boundary ??
      candidateQuantInterpretation.ordinary_result_boundary ??
      "可解释结果只从本地 cache / ledger / packet 回放；不会从结果回放卡创建 task、调用模型或生成交易动作。"
  );
  const dailyCommandConfirmedSymbol = String(
    candidates.search_quant_projection_latest_confirmed_symbol ??
      candidateQuantReceipt.symbol ??
      candidateQuantSmallDataWriteback.symbol ??
      candidateQuantInterpretation.symbol ??
      ""
  );
  useEffect(() => {
    if (homeQuantSymbolTouched) return;
    if (homeQuantSymbol.trim()) return;
    if (!dailyCommandConfirmedSymbol) return;
    setHomeQuantSymbol(dailyCommandConfirmedSymbol);
  }, [dailyCommandConfirmedSymbol, homeQuantSymbol, homeQuantSymbolTouched]);
  const dailyCommandConfirmedSymbolLabel = dailyCommandConfirmedSymbol
    ? `当前确认标的：${dailyCommandConfirmedSymbol}`
    : "等待下一票雷达确认标的";
  const dailyCommandConfirmedSourceTaskLabel = String(
    candidateQuantResultCheckpoint.source_task_id ??
      candidateQuantInterpretation.source_task_id ??
      candidateQuantSmallDataWriteback.latest_task_id ??
      candidateQuantReceipt.latest_task_id ??
      candidateQuantReceipt.task_id ??
      "等待下一票雷达确认 task"
  );
  const dailyCommandP3OneGlanceReadable =
    candidateQuantResultCheckpoint.ordinary_result_readable === true ||
    candidateQuantInterpretation.interpretation_ready === true ||
    candidateQuantQuickRows.length > 0;
  const dailyCommandP3OneGlanceProviderVerified =
    candidateQuantResultCheckpoint.provider_data_source_verified === true ||
    candidateQuantResultCheckpoint.uses_tushare_ledger === true ||
    candidateQuantInterpretation.uses_tushare_ledger === true;
  const dailyCommandP3OneGlanceEvidence = String(
    candidateQuantInterpretation.ordinary_result_evidence ??
      `source=${String(candidateQuantResultCheckpoint.evidence_source ?? "CandidateRadar cache / ledger / packet")}; missing=${String(candidateQuantResultCheckpoint.missing_evidence_count ?? 0)}`
  );
  const dailyCommandP3OneGlanceModelStateRaw = String(
    candidates.ordinary_result_deepseek_governed_executor_status ??
      candidateQuantResultCheckpoint.deepseek_state ??
      candidateQuantInterpretation.deepseek_governed_executor_status ??
      "governed_executor_pending_not_requested"
  );
  const dailyCommandP3OneGlanceUsesModelOutput =
    candidateQuantResultCheckpoint.uses_deepseek_output === true ||
    candidateQuantResultCheckpoint.uses_model_output === true ||
    candidateQuantInterpretation.uses_deepseek_output === true ||
    candidateQuantInterpretation.uses_model_output === true;
  const dailyCommandP3OneGlanceModelState = dailyCommandP3OneGlanceUsesModelOutput
    ? "检测到模型输出；需回 P5 governed executor 审核后再展示"
    : dailyCommandP3OneGlanceModelStateRaw.includes("skipped")
      ? "DeepSeek 不用等：Tushare-first 和基础图谱可先看；P5 governed executor 单独补"
      : dailyCommandP3OneGlanceModelStateRaw.includes("pending")
        ? "DeepSeek 待治理：不阻塞 Tushare-first、P2 写入或 P3 基础图谱"
        : "DeepSeek governed executor 单独补；普通结果只读本地 cache / ledger / packet";
  const dailyCommandExplainableResultRows = candidateQuantQuickRows.length
    ? candidateQuantQuickRows.map((row) => ({
        速读项: String(row["结论"] ?? row.quick_read_item ?? "结果速读"),
        当前状态: String(row["当前状态"] ?? "等待本地结果"),
        用户下一步: String(row["用户下一步"] ?? dailyCommandExplainableResultNext),
        证据: String(row["证据"] ?? row.readback_source ?? "CandidateRadar cache"),
        边界: String(row["边界"] ?? dailyCommandExplainableResultBoundary)
      }))
    : [
        {
          速读项: "现在能读什么",
          当前状态: dailyCommandExplainableResultLabel,
          用户下一步: dailyCommandExplainableResultNext,
          证据: "CandidateRadar search_quant_projection_interpretation_summary",
          边界: dailyCommandExplainableResultBoundary
        },
        {
          速读项: "结果从哪里回放",
          当前状态: "等待 CandidateRadar cache / ledger / packet 写入",
          用户下一步: "完成确认任务后回放股票量化推演和次日图谱",
          证据: "ordinary_result_quick_read_rows pending",
          边界: "首页只读展示 P3 结果速读；不补调 Tushare、DeepSeek 或 GitHub。"
        },
        {
          速读项: "还缺什么",
          当前状态: "缺口只作为待补证据",
          用户下一步: "先完成 Tushare-first 和基础图谱；DeepSeek governed executor 单独补",
          证据: "local_evidence_gap_summary",
          边界: "不把缺口、候选或解释结果当买卖指令。"
        }
      ];
  const dailyCommandP3OneGlanceQuickRows = dailyCommandExplainableResultRows;
  const dailyCommandP3CheckpointLabel = candidateQuantCheckpointRows.length
    ? `P3 检查点 ${String(candidateQuantCheckpointRows.length)} 项可回放`
    : "等待 CandidateRadar P3 结果检查点";
  const dailyCommandP3OneGlanceStatus = String(
    candidateQuantResultCheckpoint.status ??
      candidateQuantInterpretation.ordinary_result_status ??
      (dailyCommandP3OneGlanceReadable ? "readable_cache_replay" : "waiting_confirm")
  );
  const dailyCommandP3ExplainableCheckpoint =
    (candidates.ordinary_p3_explainable_result_checkpoint as Record<string, unknown> | undefined) ??
    (candidates.search_quant_projection_p3_explainable_result_checkpoint as Record<string, unknown> | undefined) ??
    (candidateQuantInterpretation.ordinary_p3_explainable_result_checkpoint as Record<string, unknown> | undefined) ??
    {};
  const dailyCommandP3OneGlanceSourceTask = String(
    candidateQuantResultCheckpoint.source_task_id ??
      candidateQuantInterpretation.source_task_id ??
      candidateQuantSmallDataWriteback.latest_task_id ??
      candidateQuantReceipt.latest_task_id ??
      candidateQuantReceipt.task_id ??
      "等待确认任务"
  );
  const dailyCommandP3ReadableEntranceNames = candidateQuantHandoffRows.length
    ? candidateQuantHandoffRows
        .map((row) => dailyCommandReadableEntry(row["入口"] ?? row.handoff_key ?? "结果入口"))
        .filter(Boolean)
    : ["下一票雷达", "股票量化推演", "次日图谱"];
  const dailyCommandP3OneGlanceResultEntrances = dailyCommandP3ReadableEntranceNames.length
    ? `结果入口 ${String(dailyCommandP3ReadableEntranceNames.length)} 个：${dailyCommandP3ReadableEntranceNames.slice(0, 3).join(" / ")}`
    : "下一票雷达 / 股票量化推演 / 次日图谱";
  const dailyCommandP3OneGlanceSource = String(
    candidateQuantResultCheckpoint.evidence_source ?? "CandidateRadar cache / ledger / packet"
  );
  const dailyCommandP3MissingEvidenceItems = Array.isArray(candidateQuantResultCheckpoint.missing_evidence)
    ? candidateQuantResultCheckpoint.missing_evidence.map(dailyCommandReadableGap).filter(Boolean)
    : [dailyCommandReadableGap(candidateQuantResultCheckpoint.missing_evidence)].filter(Boolean);
  const dailyCommandP3OneGlanceMissingEvidence = dailyCommandP3MissingEvidenceItems.length
    ? dailyCommandP3MissingEvidenceItems.join(" / ")
    : "暂无额外缺口";
  const dailyCommandP3OneGlanceSafeFields = Array.isArray(candidateQuantResultCheckpoint.safe_explanation_fields)
    ? candidateQuantResultCheckpoint.safe_explanation_fields.map(String).join(" / ")
    : "source / gap / next_step / safety_summary";
  const dailyCommandP3ExplainableMissingEvidenceCount = Number(
    dailyCommandP3ExplainableCheckpoint.missing_evidence_count ??
      candidateQuantResultCheckpoint.missing_evidence_count ??
      dailyCommandP3MissingEvidenceItems.length
  );
  const dailyCommandP3ExplainableProofItems: MetricItem[] = [
    {
      label: "结果状态",
      value: dailyCommandP3OneGlanceReadable ? `可读：${dailyCommandExplainableResultLabel}` : "等待确认后的可读结果",
      tone: dailyCommandP3OneGlanceReadable ? "good" : "warn"
    },
    {
      label: "来源证明",
      value: dailyCommandP3OneGlanceProviderVerified
        ? `Tushare-first ledger 已参与；${dailyCommandP3OneGlanceSource}`
        : dailyCommandP3OneGlanceSource,
      tone: dailyCommandP3OneGlanceProviderVerified ? "good" : "warn"
    },
    {
      label: "缺口数量",
      value: dailyCommandP3ExplainableMissingEvidenceCount
        ? `${String(dailyCommandP3ExplainableMissingEvidenceCount)} 项：${dailyCommandP3OneGlanceMissingEvidence}`
        : "暂无额外缺口",
      tone: dailyCommandP3ExplainableMissingEvidenceCount ? "warn" : "good"
    },
    {
      label: "模型状态",
      value: dailyCommandP3OneGlanceModelState,
      tone: dailyCommandP3OneGlanceUsesModelOutput ? "warn" : "good"
    },
    {
      label: "结果入口",
      value: dailyCommandP3OneGlanceResultEntrances,
      tone: candidateQuantHandoffRows.length ? "good" : "warn"
    },
    {
      label: "安全边界",
      value: "只读 P3 证明；不创建 task、不调用 DeepSeek、不交易、不改 strategy action",
      tone: "good"
    }
  ];
  const dailyCommandP3OneGlanceDecisionRows = candidateQuantDecisionBriefRows.length
    ? candidateQuantDecisionBriefRows.map((row) => ({
        读法: String(row["读法"] ?? row.brief_key ?? "结果读法"),
        当前状态: String(row["当前状态"] ?? row.ordinary_label ?? row.status ?? dailyCommandExplainableResultLabel),
        用户下一步: String(row["用户下一步"] ?? row.next_action ?? dailyCommandExplainableResultNext),
        证据: String(row["证据"] ?? row.evidence ?? dailyCommandP3OneGlanceEvidence),
        边界: String(row["边界"] ?? row.boundary ?? dailyCommandExplainableResultBoundary)
      }))
    : [
        {
          读法: "1. 先看结论",
          当前状态: dailyCommandExplainableResultLabel,
          用户下一步: dailyCommandExplainableResultNext,
          证据: dailyCommandP3OneGlanceEvidence,
          边界: dailyCommandExplainableResultBoundary
        },
        {
          读法: "2. 再看来源",
          当前状态: dailyCommandP3OneGlanceSource,
          用户下一步: "只读查看 CandidateRadar cache / ledger / packet",
          证据: "CandidateRadar cache / call_ledger / packet",
          边界: "首页只读回放来源；GET cache 和 React render 不补调 provider/model。"
        },
        {
          读法: "3. 最后定动作",
          当前状态: dailyCommandP3OneGlanceMissingEvidence || "等待本地缺口回放",
          用户下一步: dailyCommandExplainableResultNext,
          证据: "local_evidence_gap_summary",
          边界: "只作为研究线索；不下单、不改 strategy action，DeepSeek 单独等 governed executor。"
        }
      ];
  const dailyCommandConfirmOutcomeRows = candidateQuantConfirmOutcomeRows.length
    ? candidateQuantConfirmOutcomeRows.map((row) => ({
        确认结果: String(row["速读项"] ?? row.outcome_key ?? "确认结果"),
        当前状态: String(row["当前状态"] ?? row.status ?? "等待 CandidateRadar 确认结果回放"),
        用户下一步: String(row["用户下一步"] ?? row.next_step ?? dailyCommandExplainableResultNext),
        入口: String(row["入口"] ?? row.entry ?? "下一票雷达 / 股票量化推演 / 次日图谱"),
        边界: String(row["边界"] ?? row.boundary ?? "首页只读回放确认结果；不创建 task、不调用 provider/model。")
      }))
    : [
        {
          确认结果: "P1 确认结果",
          当前状态: "等待下一票雷达确认任务回放",
          用户下一步: "回下一票雷达确认输入区输入代码并点击确认按钮。",
          入口: "#candidates/candidate-radar-search-quant-projection",
          边界: "首页确认入口和下一票雷达共用同一条 P1 task；确认按钮之前不创建 Tushare-first task。"
        },
        {
          确认结果: "P2 写回结果",
          当前状态: dailyCommandSmallDataWritebackState,
          用户下一步: "确认 cache / call_ledger / packet 已能支撑首页、量化页和图谱回放。",
          入口: "CandidateRadar cache / call_ledger / packet",
          边界: "只读本地回放；不补调 Tushare、DeepSeek 或 GitHub。"
        },
        {
          确认结果: "P3 回放结果",
          当前状态: dailyCommandExplainableResultLabel,
          用户下一步: dailyCommandExplainableResultNext,
          入口: "下一票雷达 / 股票量化推演 / 次日图谱",
          边界: dailyCommandExplainableResultBoundary
        }
      ];
  const dailyCommandConfirmOutcomeLabel = dailyCommandConfirmOutcomeRows
    .map((row) => `${row.确认结果}: ${row.当前状态}`)
    .join(" / ");
  const dailyCommandP2P3ReplayChecklistRows = [
    {
      回放入口: "1. 确认回执",
      当前状态: Number(candidateCounts?.search_quant_projection_confirmed_task_receipt_row_count ?? 0) ? "可回放确认任务接收回执" : "等待确认按钮写入回执",
      用户下一步: "点击确认后看本地 task receipt，再等 TaskStatusPanel success",
      证据: "CandidateRadar ordinary_confirmed_task_receipt_rows",
      边界: candidatePolicy.search_quant_projection_confirmed_task_receipt_rows_are_cache_only === false ? "待复核，只能回雷达详情排查" : "首页只读回放；不创建第二个 task"
    },
    {
      回放入口: "2. 任务状态",
      当前状态: Number(candidateCounts?.search_quant_projection_task_readback_row_count ?? 0) ? "可回放 task id / safe current_step" : "等待本地 task id 写入 packet",
      用户下一步: "只看任务编号和安全步骤；成功后刷新本地 cache",
      证据: "CandidateRadar ordinary_task_readback_rows",
      边界: candidatePolicy.search_quant_projection_task_readback_rows_are_cache_only === false ? "待复核，只能回雷达详情排查" : "首页只读 packet；不展示 raw log、token/key 或 provider error"
    },
    {
      回放入口: "3. P2 写回三面",
      当前状态: dailyCommandSmallDataWritebackState,
      用户下一步: "按 cache、call_ledger、packet 三面确认是否可回放",
      证据: "ordinary_writeback_surface_summary_rows",
      边界: dailyCommandSmallDataWritebackBoundary
    },
    {
      回放入口: "4. P3 结果",
      当前状态: dailyCommandExplainableResultLabel,
      用户下一步: dailyCommandExplainableResultNext,
      证据: "ordinary_result_quick_read_rows / ordinary_result_checkpoint_rows",
      边界: dailyCommandExplainableResultBoundary
    }
  ];
  const dailyCommandP3CheckpointRows = candidateQuantCheckpointRows.length
    ? candidateQuantCheckpointRows.map((row) => ({
        检查点: String(row["检查点"] ?? row.checkpoint_key ?? "P3 检查点"),
        当前状态: String(row["当前状态"] ?? row.status ?? dailyCommandExplainableResultLabel),
        用户下一步: String(row["用户下一步"] ?? row.next_action ?? dailyCommandExplainableResultNext),
        证据: String(row["证据"] ?? row.evidence ?? "CandidateRadar ordinary_result_checkpoint_rows"),
        边界: String(row["边界"] ?? row.boundary ?? dailyCommandExplainableResultBoundary)
      }))
    : [
        {
          检查点: "1. 可读结论",
          当前状态: dailyCommandExplainableResultLabel,
          用户下一步: dailyCommandExplainableResultNext,
          证据: "CandidateRadar search_quant_projection_interpretation_summary",
          边界: dailyCommandExplainableResultBoundary
        },
        {
          检查点: "2. 来源状态",
          当前状态: "等待 cache / ledger / packet 三面回放",
          用户下一步: "任务完成后刷新本地 cache，再从下一票雷达、股票量化推演和次日图谱复核",
          证据: "ordinary_result_checkpoint_rows pending",
          边界: "首页只读 P3 检查点；不创建 task、不调用 Tushare/DeepSeek/GitHub、不写 cache。"
        },
        {
          检查点: "3. 缺口和安全字段",
          当前状态: "缺口只作为待补证据；安全字段只允许 source / gap / next_step / safety_summary",
          用户下一步: "把结果当研究线索；DeepSeek governed executor 和 14 LTG strict closeout 后续单独补",
          证据: "local_result_checkpoint_fallback",
          边界: "不真实交易、不下单、不改价格、持仓、因子、operation_zones 或 strategy action。"
        }
      ];
  const candidateQuantModelGovernanceRows = (candidateQuantInterpretation.ordinary_model_governance_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const candidateQuantDeepSeekReadinessRows =
    (candidateQuantInterpretation.ordinary_deepseek_governed_executor_readiness_rows as Array<Record<string, unknown>> | undefined) ??
    [];
  const modelStrategyGovernedExecutor = (modelStrategy.governed_executor as Record<string, unknown> | undefined) ?? {};
  const modelStrategyP5RealCallGateRows =
    (modelStrategyGovernedExecutor.real_call_gate_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const dailyCommandDeepSeekGovernanceBoundary =
    "DeepSeek governed executor 单独补；首页只读显示治理状态，不调用模型、不展示 prompt/output、不覆盖价格、持仓、因子、operation_zones 或 strategy action。";
  const dailyCommandDeepSeekGovernanceState = String(
    modelStrategyGovernedExecutor.ordinary_status_label ??
      modelStrategyGovernedExecutor.status ??
      candidateQuantInterpretation.deepseek_governed_executor_status ??
      "governed_executor_pending_not_requested"
  );
  const modelStrategyP5StatusLabel = String(
    modelStrategyGovernedExecutor.ordinary_status_label ??
      modelStrategyGovernedExecutor.status ??
      dailyCommandDeepSeekGovernanceState
  );
  const modelStrategyP5NextAllowedAction = String(
    modelStrategyGovernedExecutor.ordinary_next_allowed_action ??
      "先继续 Tushare-first、Factor light 和 Next Session 本地回放；DeepSeek 单独补证。"
  );
  const modelStrategyP5RequiredBeforeRealCall = String(
    modelStrategyGovernedExecutor.ordinary_required_before_real_call ??
      "等待 model_ledger / sanitizer / redaction review / cost accounting / output acceptance"
  );
  const modelStrategyP5Boundary = String(
    modelStrategyGovernedExecutor.ordinary_nonblocking_boundary ?? dailyCommandDeepSeekGovernanceBoundary
  );
  const modelStrategyP5BlockerCount = Number(
    modelStrategyGovernedExecutor.real_call_blocker_count ?? modelStrategyP5RealCallGateRows.length
  );
  const modelStrategyP5NonblockingRows = modelStrategyGovernedExecutor.status
    ? [
        {
          检查项: "1. 当前能先看什么",
          当前状态: modelStrategyP5StatusLabel,
          允许动作: modelStrategyP5NextAllowedAction,
          用户下一步: "继续 P1/P2/P3 本地回放；P5 只读治理状态在本区查看",
          边界: modelStrategyP5Boundary
        },
        {
          检查项: "2. 真实调用闸门",
          当前状态: modelStrategyGovernedExecutor.real_call_allowed_now === true ? "已放行" : `未放行：${String(modelStrategyP5BlockerCount)} 个 blocker`,
          允许动作: "只允许本地 scope ticket / execution-request 补证",
          用户下一步: modelStrategyP5RequiredBeforeRealCall,
          边界: "GET /api/model-strategy/cache 只读，不调用 DeepSeek、不创建模型任务。"
        },
        {
          检查项: "3. 不会改什么",
          当前状态: "不覆盖价格、持仓、factor、operation_zones 或 strategy action",
          允许动作: "继续基础图谱本地回放",
          用户下一步: "把 DeepSeek pending 当单独 P5 补证，不阻塞当前投研链路",
          边界: dailyCommandDeepSeekGovernanceBoundary
        }
      ]
    : [];
  const dailyCommandP5NonblockingRows = modelStrategyP5NonblockingRows.length
    ? modelStrategyP5NonblockingRows
    : candidateQuantDeepSeekReadinessRows.length
    ? candidateQuantDeepSeekReadinessRows.slice(0, 3).map((row) => ({
        检查项: String(row["检查项"] ?? row.readiness_key ?? "P5 readiness"),
        当前状态: String(row["当前状态"] ?? row.status ?? dailyCommandDeepSeekGovernanceState),
        允许动作: String(row["允许动作"] ?? row.allowed_action ?? "继续 P1/P2/P3 本地回放"),
        用户下一步: String(row["用户下一步"] ?? row.next_action ?? "先使用 Tushare-first、小数据写入和基础图谱"),
        边界: String(row["边界"] ?? row.boundary ?? dailyCommandDeepSeekGovernanceBoundary)
      }))
    : [
        {
          检查项: "1. 当前能先看什么",
          当前状态: "Tushare-first、P2 小数据和 P3 基础图谱可先读",
          允许动作: "继续本地 cache / ledger / packet 回放",
          用户下一步: dailyCommandExplainableResultNext,
          边界: "DeepSeek pending 不阻塞 P1/P2/P3；首页不调用模型。"
        },
        {
          检查项: "2. DeepSeek 还等什么",
          当前状态: dailyCommandDeepSeekGovernanceState,
          允许动作: "等待 governed executor、model_ledger、sanitizer 和 output acceptance",
          用户下一步: "需要模型解释时去 DeepSeek 模型策略页看 P5 治理状态",
          边界: "没有 model_ledger 不能当真实模型证据，也不能当 production evidence。"
        },
        {
          检查项: "3. 不会改什么",
          当前状态: "不覆盖价格、持仓、factor、operation_zones 或 strategy action",
          允许动作: "只读查看安全摘要",
          用户下一步: "把结果当研究线索，不当买卖指令",
          边界: dailyCommandDeepSeekGovernanceBoundary
        }
      ];
  const modelStrategyP5GovernanceRows = modelStrategyP5RealCallGateRows.length
    ? modelStrategyP5RealCallGateRows.slice(0, 5).map((row) => ({
        治理项: String(row.gate_key ?? "DeepSeek gate"),
        当前状态: String(row.status ?? (row.passed === true ? "passed" : "blocked")),
        用户下一步: String(row.next_evidence ?? modelStrategyP5RequiredBeforeRealCall),
        证据: String(row.evidence ?? "GET /api/model-strategy/cache governed_executor.real_call_gate_rows"),
        边界: "model-strategy cache 只读回放；不调用模型、不创建 task。"
      }))
    : [];
  const dailyCommandDeepSeekGovernanceRows = modelStrategyP5GovernanceRows.length
    ? modelStrategyP5GovernanceRows
    : candidateQuantModelGovernanceRows.length
    ? candidateQuantModelGovernanceRows.map((row) => ({
        治理项: String(row["治理项"] ?? row.governance_item ?? "DeepSeek 治理"),
        当前状态: String(row["当前状态"] ?? "等待 governed executor"),
        用户下一步: String(row["用户下一步"] ?? "先使用 Tushare-first 和基础图谱；DeepSeek 单独补"),
        证据: String(row["证据"] ?? row.readback_source ?? "search_quant_projection_interpretation_summary"),
        边界: String(row["边界"] ?? dailyCommandDeepSeekGovernanceBoundary)
      }))
    : [
        {
          治理项: "执行门控",
          当前状态: "DeepSeek 等 governed executor；未完成前不真实调用模型",
          用户下一步: "先看 Tushare-first、小数据写入和基础图谱",
          证据: "ordinary_model_governance_rows pending",
          边界: "GET cache 和 React render 不调用 DeepSeek；DeepSeek 不作为数据源。"
        },
        {
          治理项: "输出范围",
          当前状态: "只允许解释数据来源、证据缺口和下一步",
          用户下一步: "即使后续补 model_ledger，也只展示安全摘要",
          证据: "local_model_governance_policy",
          边界: "DeepSeek 输出不覆盖价格、持仓、factor、operation_zones 或 strategy action。"
        },
        {
          治理项: "不阻塞基础图谱",
          当前状态: "DeepSeek pending/skipped 不阻塞 Tushare-first 和本地结果回放",
          用户下一步: "先使用基础图谱；DeepSeek 作为单独补证",
          证据: "cache / call_ledger / packet",
          边界: "DeepSeek pending/skipped 不阻断 Tushare ledger、cache packet 或本地结果回放。"
        }
      ];
  const riskCounts = risk.counts as Record<string, unknown> | undefined;
  const liveLight = (bootstrapStatus.live_light as Record<string, unknown> | undefined) ?? {};
  const bootstrapProviderLinkageRows = (bootstrapStatus.provider_linkage_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const liveLightActivationReceipt = (bootstrapStatus.live_light_activation_receipt as Record<string, unknown> | undefined) ?? {};
  const liveLightActivationRows = (bootstrapStatus.live_light_activation_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const liveLightAcceptanceRunbook = (bootstrapStatus.live_light_provider_model_acceptance_runbook as Record<string, unknown> | undefined) ?? {};
  const liveLightAcceptanceRows = (bootstrapStatus.live_light_provider_model_acceptance_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const liveBootstrapRunKey = [
    bootstrapStatus.mode,
    liveLight.tushare_on_open,
    liveLight.deepseek_on_open,
    liveLight.symbol_limit,
    positionSummary?.ticker,
  ].map((item) => String(item ?? "")).join(":");
  const liveBootstrapTaskLedger = liveBootstrapReceipt?.call_ledger ?? liveBootstrapReceipt?.data?.task?.call_ledger ?? [];
  const liveBootstrapWarnings = liveBootstrapReceipt?.warnings ?? liveBootstrapReceipt?.data?.task?.warnings ?? [];
  const liveBootstrapPayload = (liveBootstrapReceipt?.data?.task?.payload_safe as Record<string, unknown> | undefined) ?? {};
  const liveBootstrapStageRows = (liveBootstrapPayload.bootstrap_stage_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const liveBootstrapModelLedgerRows = (liveBootstrapPayload.bootstrap_model_ledger_preview_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const factorScoreChart = factor.score_chart_payload as Record<string, unknown> | undefined;
  const factorScoreChartContract = factorScoreChart?.chart_contract as Record<string, unknown> | undefined;
  const healthWarnings = healthEnvelopeWarnings.length ? healthEnvelopeWarnings : ((health.warnings as Array<string> | undefined) ?? []);
  const packetPayloadLedger = (packets.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const marketPayloadLedger = (market.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const disciplinePayloadLedger = (discipline.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const factorPayloadLedger = (factor.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const factorCandidateHandoff =
    (factor.candidate_radar_quant_projection_handoff as Record<string, unknown> | undefined) ?? {};
  const factorCandidateHandoffRows =
    (factor.ordinary_quant_candidate_handoff_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const dailyCommandFactorCandidateHandoffReady =
    factorCandidateHandoff.p3_readable_result_ready === true || factorCandidateHandoffRows.length > 0;
  const dailyCommandFactorCandidateHandoffSymbol = String(
    factorCandidateHandoff.symbol ?? dailyCommandConfirmedSymbol ?? ""
  );
  const dailyCommandFactorCandidateHandoffTask = String(
    factorCandidateHandoff.source_task_id ?? dailyCommandP3OneGlanceSourceTask
  );
  const dailyCommandFactorCandidateHandoffLabel = dailyCommandFactorCandidateHandoffReady
    ? `Factor 已接上 ${dailyCommandFactorCandidateHandoffSymbol || "当前标的"} / task=${dailyCommandFactorCandidateHandoffTask}`
    : "Factor handoff 等待本地 cache";
  const dailyCommandFactorCandidateHandoffBoundary =
    "只读 /api/factor-quant/cache 的 CandidateRadar handoff；不创建 task、不补调 Tushare/DeepSeek、不展示 token/key/raw log。";
  const dailyCommandFactorCandidateHandoffReadbackRows = factorCandidateHandoffRows.length
    ? factorCandidateHandoffRows
    : [
        {
          handoff_step: "等待 Factor handoff",
          当前状态: dailyCommandFactorCandidateHandoffLabel,
          用户下一步: "完成下一票雷达确认任务后，再回首页或股票量化推演查看本地 handoff。",
          证据: "factor.ordinary_quant_candidate_handoff_rows pending",
          边界: dailyCommandFactorCandidateHandoffBoundary
        }
      ];
  const factorFailedCacheSummary = (factor.failed_factor_quant_cache_summary as Record<string, unknown> | undefined) ?? {};
  const dailyCommandFactorCacheFallbackActive = factor.cache_fallback_from_failed_factor_quant_packet === true;
  const dailyCommandFactorCacheFallbackLabel = dailyCommandFactorCacheFallbackActive
    ? `量化缓存已降级为本地可读：上次 ${String(factorFailedCacheSummary.task_type ?? "provider task")} ${String(factorFailedCacheSummary.status ?? "failed")}；继续按 cache-only 回放`
    : "量化缓存直接可读；未检测到失败持久化 packet 降级";
  const dailyCommandFactorCacheFallbackBoundary =
    "量化缓存降级只返回安全摘要和本地 builder 结果；首页不展开 raw failed packet、provider error、token/key 或 call_ledger。";
  const dailyCommandFactorCacheFallbackRows = [
    {
      回放项: "当前量化缓存",
      当前状态: String(factor.status ?? factor.mode ?? "等待缓存"),
      用户下一步: "打开股票量化推演只读回放支持/压制、次日图谱预览和模型治理状态",
      证据: "GET /api/factor-quant/cache",
      边界: "GET cache 不创建 task、不调用 Tushare/DeepSeek/GitHub、不写 cache"
    },
    {
      回放项: "失败持久化降级",
      当前状态: dailyCommandFactorCacheFallbackLabel,
      用户下一步: dailyCommandFactorCacheFallbackActive
        ? "继续按 P3 回放；需要更新时回下一票雷达确认按钮重新生成"
        : "继续按 P3 回放；无需展开工程审计",
      证据: dailyCommandFactorCacheFallbackActive ? "failed_factor_quant_cache_summary 安全摘要" : "cache_source / mode",
      边界: dailyCommandFactorCacheFallbackBoundary
    }
  ];
  const nextPayloadLedger = (next.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const serenityPayloadLedger = (serenity.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const chokepointPayloadLedger = (chokepoint.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const taskCatalogPayloadLedger = (taskCatalog.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const taskIndexPayloadLedger = taskIndex?.call_ledger ?? [];
  const dailyCommandCandidateLatestTaskId = String(
    candidateQuantSmallDataWriteback.latest_task_id ??
      candidateQuantReceipt.latest_task_id ??
      candidateQuantReceipt.task_id ??
      candidates.task_id ??
      ""
  );
  const dailyCommandCandidateLatestTask = dailyCommandCandidateLatestTaskId
    ? tasks.find((task) => String(task.task_id ?? "") === dailyCommandCandidateLatestTaskId) ?? {}
    : {};
  const dailyCommandLatestTask = dailyCommandCandidateLatestTaskId ? dailyCommandCandidateLatestTask : tasks[0] ?? {};
  const dailyCommandLatestTaskId = String(dailyCommandCandidateLatestTaskId || dailyCommandLatestTask.task_id || taskIndex?.latest_task_id || "");
  const dailyCommandLatestTaskType = String(
    dailyCommandLatestTask.task_type ??
      (dailyCommandCandidateLatestTaskId ? "run_candidate_radar_quant_projection_provider_model_acceptance" : taskIndex?.latest_task_type) ??
      "--"
  );
  const dailyCommandLatestTaskStatus = String(
    dailyCommandLatestTask.status ??
      candidateQuantSmallDataWriteback.latest_task_status ??
      candidateQuantReceipt.latest_task_status ??
      taskIndex?.latest_task_status ??
      "waiting"
  );
  const dailyCommandLatestTaskStep = String(
    dailyCommandLatestTask.current_step ??
      candidateQuantSmallDataWriteback.latest_task_current_step ??
      candidateQuantReceipt.latest_task_current_step ??
      "等待本地任务状态回放"
  );
  const dailyCommandLatestTaskSource = String(
    dailyCommandCandidateLatestTaskId
      ? candidateQuantSmallDataWriteback.task_readback_source ?? candidateQuantReceipt.task_readback_source ?? "candidate_radar_cache_latest_task"
      : dailyCommandLatestTask.storage_source ?? "memory_or_sqlite_fallback"
  );
  const dailyCommandLatestTaskIsCandidate =
    Boolean(dailyCommandCandidateLatestTaskId) ||
    String(dailyCommandLatestTask.output_packet_key ?? "") === "command_center_3_candidate_radar_cache" ||
    dailyCommandLatestTaskType.includes("candidate_radar_quant_projection");
  const dailyCommandLatestTaskIsReplay = dailyCommandLatestTask.cache_replay_only === true || Boolean(dailyCommandCandidateLatestTaskId && !dailyCommandLatestTask.task_id);
  const dailyCommandLatestTaskLabel = dailyCommandLatestTaskId
    ? `${dailyCommandLatestTaskStatus}: ${dailyCommandLatestTaskType}`
    : "暂无本地任务；先在首页确认股票代码，需要详情再进下一票雷达";
  const dailyCommandLatestTaskNext = dailyCommandLatestTaskId
    ? dailyCommandLatestTaskIsCandidate
      ? "看下方任务状态；成功后进入股票量化推演和次日图谱回放"
      : "看下方任务状态；按任务输出 packet 回放结果"
    : "在首页输入股票代码，点击确认并生成 3.0 量化推演";
  const dailyCommandFastApiProgressWatchLabel = dailyCommandConfirmedSymbol
    ? `${dailyCommandConfirmedSymbol} / ${dailyCommandLatestTaskStatus}`
    : dailyCommandLatestTaskId
      ? `${dailyCommandLatestTaskId} / ${dailyCommandLatestTaskStatus}`
      : "等待确认按钮后的任务进度";
  const dailyCommandFastApiProgressWatchNext = dailyCommandLatestTaskId
    ? "查看任务进度；再回股票量化推演和次日图谱"
    : "先在首页确认股票代码；输入本身保持静默";
  const dailyCommandLatestTaskRows = [
    {
      速读项: "最近任务",
      当前状态: dailyCommandLatestTaskLabel,
      用户下一步: dailyCommandLatestTaskNext,
      证据: dailyCommandLatestTaskId || "GET /api/tasks",
      边界: "首页只读任务目录；不会创建 task、不调用 Tushare/DeepSeek/GitHub、不执行真实交易。"
    },
    {
      速读项: "任务来源",
      当前状态: dailyCommandLatestTaskIsReplay ? "来自 CandidateRadar cache 只读回放" : dailyCommandLatestTaskSource,
      用户下一步: dailyCommandLatestTaskIsReplay ? "把它当最近确认链的进度回放，不当新的生产验收证据" : "继续看任务状态和输出 packet",
      证据: dailyCommandLatestTaskSource,
      边界: "cache replay 不创建任务、不补调 provider/model；只帮助普通用户看到已有进度。"
    },
    {
      速读项: "当前步骤",
      当前状态: dailyCommandLatestTaskStep,
      用户下一步: dailyCommandLatestTaskStatus === "success" ? "刷新本地结果页回放" : "等待状态变化或回到下一票雷达重新确认",
      证据: "task.current_step",
      边界: "TaskStatusPanel 只轮询本地 FastAPI；不会自动重试、不会下单、不改 strategy action。"
    }
  ];
  const envelopeLedgerRows = [
    ...healthEnvelopeLedger.map((row) => ({ scope: "health", ...row })),
    ...bootstrapEnvelopeLedger.map((row) => ({ scope: "bootstrap_status", ...row })),
    ...liveBootstrapTaskLedger.map((row) => ({ scope: "live_bootstrap", ...row })),
    ...(packetEnvelopeLedger.length ? packetEnvelopeLedger : packetPayloadLedger).map((row) => ({ scope: "packet_index", ...row })),
    ...(marketEnvelopeLedger.length ? marketEnvelopeLedger : marketPayloadLedger).map((row) => ({ scope: "market", ...row })),
    ...(disciplineEnvelopeLedger.length ? disciplineEnvelopeLedger : disciplinePayloadLedger).map((row) => ({ scope: "discipline", ...row })),
    ...(factorEnvelopeLedger.length ? factorEnvelopeLedger : factorPayloadLedger).map((row) => ({ scope: "factor_quant", ...row })),
    ...(nextEnvelopeLedger.length ? nextEnvelopeLedger : nextPayloadLedger).map((row) => ({ scope: "next_session", ...row })),
    ...(serenityEnvelopeLedger.length ? serenityEnvelopeLedger : serenityPayloadLedger).map((row) => ({ scope: "serenity", ...row })),
    ...(chokepointEnvelopeLedger.length ? chokepointEnvelopeLedger : chokepointPayloadLedger).map((row) => ({ scope: "chokepoint", ...row })),
    ...(taskCatalogEnvelopeLedger.length ? taskCatalogEnvelopeLedger : taskCatalogPayloadLedger).map((row) => ({ scope: "task_catalog", ...row })),
    ...(taskIndexEnvelopeLedger.length ? taskIndexEnvelopeLedger : taskIndexPayloadLedger).map((row) => ({ scope: "task_status_index", ...row }))
  ];
  const empty = !loading && !error && !Object.keys(health).length && !Object.keys(packets).length;
  const dailyCommandHealthOk = String(health.status ?? "") === "ok";
  const dailyCommandHealthChecked = Object.keys(health).length > 0;
  const dailyCommandCacheWarning = dailyCommandHealthOk && error ? `本地 cache 回读提示：${error}` : "";
  const dailyCommandNeedsStartupRecovery =
    !dailyCommandHealthOk && (loading || Boolean(error) || !dailyCommandHealthChecked);
  const dailyCommandP0QuickActionPacket = String(
    desktopRuntime?.p0_ordinary_quick_action_next ?? p0OrdinaryQuickActionRows[0]?.["用户下一步"] ?? ""
  );
  const dailyCommandP0QuickAction = dailyCommandNeedsStartupRecovery
    ? dailyCommandP0QuickActionPacket
    : "联通已通过，先在首页确认股票代码；需要详情再进下一票雷达";
  const dailyCommandP0CheckOnlyNext = String(
    desktopRuntime?.p0_launcher_check_only_next ?? p0LauncherCheckOnlyRows[0]?.["用户动作"] ?? "scripts/check_command_center_3.command"
  );
  const dailyCommandNextClick = dailyCommandNeedsStartupRecovery
    ? "先查看一键启动预检，恢复本地 FastAPI / React 联通"
    : dailyCommandP0QuickAction
    ? dailyCommandP0QuickAction
    : "在首页输入代码并点击确认；需要详情再进下一票雷达";
  const dailyCommandPrimaryActionLabel = dailyCommandNeedsStartupRecovery
    ? "查看一键启动预检"
    : "首页确认股票代码";
  const dailyCommandHomeConfirmHref = "#home-p1-symbol-confirm";
  const dailyCommandCandidateConfirmHref = "#candidates/candidate-radar-search-quant-projection";
  const dailyCommandPrimaryActionHref = dailyCommandNeedsStartupRecovery
    ? "#desktop"
    : dailyCommandHomeConfirmHref;
  const dailyCommandPrimaryActionBoundary = dailyCommandNeedsStartupRecovery
    ? "主下一步只打开桌面壳预检，不启动服务、不创建 task、不刷新 provider/model"
    : "主下一步可在首页输入代码并确认；输入保持静默，确认按钮才创建 Tushare-first POST task";
  const dailyCommandCacheSourceLabel = snapshotAvailable ? "本地缓存可用" : "等待本地缓存";
  const dailyCommandTushareSourceLabel = liveLight.tushare_on_open === true
    ? "live_light 已配置；仍需确认按钮触发 Tushare-first task"
    : "手动触发或关闭";
  const liveBootstrapModelCalled = liveBootstrapTaskLedger.some((row) => row.deepseek_called === true);
  const dailyCommandDeepSeekSourceLabel = liveBootstrapModelCalled
    ? "model_ledger 已记录；只读回放安全摘要"
    : liveLight.deepseek_on_open === true
      ? "待 governed executor；不随页面打开调用"
      : "手动触发或关闭";
  const dailyCommandRuntimeModeLabel = (() => {
    const mode = String(bootstrapStatus.mode ?? "cache_only");
    if (mode === "cache_only") return "只读缓存模式";
    if (mode === "manual") return "手动任务模式";
    if (mode === "live_light") return "轻量实时投研模式";
    if (mode === "live_full") return "深度实时投研预留";
    return "未知运行模式";
  })();
  const dailyCommandSourceState = [
    `本地缓存：${dailyCommandCacheSourceLabel}`,
    `Tushare 数据：${dailyCommandTushareSourceLabel}`,
    `DeepSeek 解释：${dailyCommandDeepSeekSourceLabel}`,
    `运行模式：${dailyCommandRuntimeModeLabel}`
  ].join(" / ");
  const dailyCommandBackgroundTaskState = (() => {
    if (liveBootstrapManualStatus === "creating") return "手动补证任务提交中；页面可继续查看缓存";
    if (liveBootstrapManualStatus.includes("failed")) return "手动补证未完成；已回到只读查看";
    if (liveBootstrapTaskId) return "已有本地补证任务；进度在开发详情";
    return "普通路径不自动补证；需要时在开发详情手动确认";
  })();
  const dailyCommandBackgroundTaskTone =
    dailyCommandBackgroundTaskState.includes("未完成") ? "warn" : "good";
  const dailyCommandMissingEvidence = [
    Number(dataHealthCounts?.provider_count ?? 0) ? "" : "数据健康 provider 汇总",
    Number(candidateCounts?.candidate_count ?? 0) ? "" : "下一票雷达缓存",
    next.status === "ready" ? "" : "Next Session 缓存",
    migrationLongTermSummary?.strict_closeout === "14/14" ? "" : "长期生产验收收口",
    liveLightActivationReceipt.ready_for_provider_execution === true ? "" : "数据源/模型验收"
  ].filter(Boolean).join(" / ") || "核心缓存已可见；生产级证据仍在长期验收中";
  const dailyCommandBlockedState = error
    ? `前端错误: ${error}`
    : loading
      ? "正在读取本地缓存"
      : Number(riskCounts?.active_risk_count ?? riskCounts?.risk_count ?? 0)
        ? "风险/降级状态见下方明细"
        : Number(taskUncoveredPostRoutes?.length ?? 0)
          ? "任务路由覆盖缺口见下方明细"
          : "当前缓存未标记阻断或降级";
  const dailyCommandPendingSourceLabel = dailyCommandMissingEvidence.includes("核心缓存已可见")
    ? "待补：当前摘要未标记新增待补"
    : `待补：${dailyCommandMissingEvidence}`;
  const dailyCommandDegradedSourceLabel = dailyCommandBlockedState.includes("未标记")
    ? "降级：未标记降级"
    : `降级：${dailyCommandBlockedState}`;
  const dailyCommandLastCache = String(
    packets.loaded_at ?? market.loaded_at ?? factor.loaded_at ?? next.loaded_at ?? dataHealth.loaded_at ?? "暂无最近可用缓存"
  );
  const dailyCommandTaskBoundary =
    "首页 GET cache 只读；live_light 手动补证只允许创建后台 POST task，不在 React 渲染中直连 Tushare 或 DeepSeek";
  const dailyCommandExternalTriggerBoundary =
    "页面打开、搜索输入、React render 和 GET cache 不自动外联；只有首页或下一票雷达确认按钮可创建 Tushare-first POST task，DeepSeek 等 governed executor。";
  const dailyCommandResearchOnlyLabel = "今日摘要只组织投研证据；不买卖、不下单、不改交易策略";
  const dailyCommandStatusLabel = dailyCommandHealthOk ? "只读入口可用" : "等待只读入口";
  const dailyCommandConnectionState = error
    ? dailyCommandCacheWarning || "本地前后端未联通；请使用桌面快捷方式或本地启动器重新打开"
    : dailyCommandHealthOk
      ? "本地前后端已联通"
      : "正在确认本地连接";
  const dailyCommandFrontendBackendSelectedApiBase = String(
    healthEnvelopeLedger.find(
      (row) =>
        row.api === "frontend_fastapi_request" &&
        row.frontend_backend_auto_link_success === true &&
        typeof row.api_base === "string"
    )?.api_base ?? API_BASE_DISPLAY_URL
  );
  const dailyCommandFrontendBackendAutoLinkLabel = dailyCommandHealthOk
    ? `已联通本地后端：${dailyCommandFrontendBackendSelectedApiBase}`
    : `自动尝试本地 FastAPI：${API_BASE_CANDIDATE_DISPLAY_URLS.join(" / ")}`;
  const dailyCommandFrontendBackendAutoLinkBoundary =
    "前端 API client 只在本地 FastAPI 候选地址内自动联通；失败显示离线提示，不启动服务、不创建 task、不调用 provider/model、不读取 token/key";
  const dailyCommandP0LocalConnectionReceipt =
    (desktopPreflight.p0_local_connection_receipt as Record<string, unknown> | undefined) ?? {};
  const dailyCommandP0StabilityReady =
    oneClickStartupSummary.p0_stability_check_before_open === true ||
    dailyCommandP0LocalConnectionReceipt.p0_stability_check_before_open === true;
  const dailyCommandP0LocalLinkReady =
    oneClickStartupSummary.frontend_backend_connection_ready === true &&
    dailyCommandP0LocalConnectionReceipt.status === "p0_local_connection_receipt_ready";
  const dailyCommandP0ConnectionEvidenceReady = dailyCommandP0StabilityReady || dailyCommandP0LocalLinkReady;
  const dailyCommandP0LocalReadinessReady =
    dailyCommandHealthOk &&
    bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet" &&
    desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache" &&
    dailyCommandP0ConnectionEvidenceReady;
  const dailyCommandP0LocalReadinessLabel = dailyCommandP0LocalReadinessReady
    ? `P0 ready：${dailyCommandFrontendBackendSelectedApiBase} 已联通，当前 React 页面已加载；可在首页确认股票代码`
    : "P0 check：先让 health、bootstrap status、desktop preflight cache 变绿；未 ready 不进入 P1";
  const dailyCommandP0LocalReadinessBoundary =
    "P0 ready 只证明本地前后端联通；不代表 Tushare 已调用、DeepSeek 可用、release ready 或 14 LTG 完成。";
  const dailyCommandOpenFastApiProofItems: MetricItem[] = [
    {
      label: "FastAPI health",
      value: dailyCommandHealthOk ? "已接上：health ok，启动不外联" : "等待本地 health",
      tone: dailyCommandHealthOk && health.external_calls_on_startup !== true ? "good" : "warn"
    },
    {
      label: "运行模式",
      value: bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet"
        ? `已回读：${dailyCommandRuntimeModeLabel}`
        : "等待 bootstrap runtime-mode packet",
      tone: bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet" ? "good" : "warn"
    },
    {
      label: "一键预检",
      value: desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache"
        ? "已回读：desktop preflight 一键启动 packet"
        : "等待 desktop preflight packet",
      tone: desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache" ? "good" : "warn"
    },
    {
      label: "当前页面",
      value: "React 页面已加载；只读 GET 回读中",
      tone: "good"
    },
    {
      label: "继续入口",
      value: dailyCommandP0LocalReadinessReady ? "可以确认股票代码" : "先看一键启动预检",
      tone: dailyCommandP0LocalReadinessReady ? "good" : "warn"
    },
    {
      label: "边界",
      value: "只显示本地 GET 回读；不启动服务、不创建 task、不调用 Tushare/DeepSeek",
      tone: "good"
    }
  ];
  const bootstrapPolicy = (bootstrapStatus.policy as Record<string, unknown> | undefined) ?? {};
  const homeP1ManualConfirmReady =
    bootstrapPolicy.search_quant_projection_manual_confirm_button_runtime_ready === true &&
    bootstrapPolicy.search_quant_projection_frontend_runtime_wiring_implemented === true;
  const homeP1ManualConfirmStatus = String(
    bootstrapPolicy.search_quant_projection_manual_confirm_button_status ??
      (homeP1ManualConfirmReady ? "ready_explicit_confirm_button_posts_quant_projection_task" : "waiting_p1_manual_confirm_runtime")
  );
  const homeP1ManualConfirmLabel = homeP1ManualConfirmReady
    ? "已接：按钮 -> POST task -> TaskStatusPanel -> cache 回放"
    : "待确认：P1 手动按钮 runtime 状态未回读";
  const homeP1BrowserEvidenceLabel =
    bootstrapPolicy.search_quant_projection_frontend_wiring_browser_evidence_complete === true
      ? "浏览器证据已完成"
      : "浏览器网络证据未补；不阻塞手动确认使用";
  const homeQuantSymbolValidation = normalizeHomeAshareSymbolInput(homeQuantSymbol);
  const homeQuantCanSubmit = dailyCommandP0LocalReadinessReady && homeQuantSymbolValidation.valid && !homeQuantSubmitting;
  const homeQuantUseConfirmedSymbolLabel = dailyCommandConfirmedSymbol
    ? `填入当前标的 ${dailyCommandConfirmedSymbol}`
    : "等待当前标的回放";
  const homeQuantUseConfirmedSymbolTitle = dailyCommandConfirmedSymbol
    ? "只把已回放标的填入输入框；不会创建 task，也不会调用 Tushare/DeepSeek"
    : "暂无当前确认标的；请手动输入 6 位 A 股代码或带后缀代码";
  const homeQuantSubmitDisabledReason = homeQuantSubmitting
    ? "正在创建 Tushare-first 后台 task；请等待本地任务编号"
    : !dailyCommandP0LocalReadinessReady
      ? "P0 未 ready：先让本地 FastAPI、bootstrap、desktop preflight 和 P0 connection evidence 变绿"
      : homeQuantSymbolValidation.valid
        ? `已确认 ${homeQuantSymbolValidation.normalized}；点击确认才创建 Tushare-first POST task`
        : homeQuantSymbol.trim()
          ? `代码格式阻断：${homeQuantSymbolValidation.reason}；请输入 6 位 A 股代码或 002008.SZ`
          : "先输入股票代码；输入本身不会创建 task 或调用 Tushare/DeepSeek";
  const homeQuantP0ConfirmGateEvidence = {
    schema_version: "candidate_radar_p0_confirm_gate.v1",
    p0_ready: dailyCommandP0LocalReadinessReady,
    fastapi_cache_get_ready: dailyCommandHealthOk,
    bootstrap_runtime_mode_ready: bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet",
    desktop_preflight_ready: desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache",
    p0_stability_check_ready: dailyCommandP0StabilityReady,
    p0_local_link_ready: dailyCommandP0LocalLinkReady,
    p0_connection_evidence_ready: dailyCommandP0ConnectionEvidenceReady,
    p0_local_link_is_ui_gate_only_not_release_evidence: dailyCommandP0LocalLinkReady && !dailyCommandP0StabilityReady,
    candidate_cache_ready: Boolean(candidates.status),
    candidate_cache_status: String(candidates.status ?? "missing"),
    bootstrap_packet_key: String(bootstrapStatus.packet_key ?? "missing"),
    desktop_preflight_packet_key: String(desktopPreflight.packet_key ?? "missing"),
    creates_task_only_after_button: true,
    react_render_external_calls: false,
    get_cache_external_calls: false,
    contains_sensitive_material: false
  };
  const homeQuantTaskPanelTaskId = homeQuantTaskId || String(homeQuantReceipt?.data?.task_id ?? "");
  const homeQuantRecoveredTaskId = dailyCommandCandidateLatestTaskId;
  const homeQuantVisibleTaskId = homeQuantTaskPanelTaskId || homeQuantRecoveredTaskId;
  const homeQuantVisibleTaskSource = homeQuantTaskPanelTaskId
    ? "本次首页确认按钮"
    : homeQuantRecoveredTaskId
      ? "CandidateRadar cache 最近确认 task"
      : "等待确认按钮";
  const homeQuantVisibleTaskCanPoll = Boolean(homeQuantTaskPanelTaskId || (homeQuantRecoveredTaskId && !dailyCommandLatestTaskIsReplay));
  const homeQuantReadbackStatus = homeQuantVisibleTaskId
    ? `任务已回放：${homeQuantVisibleTaskId}`
    : dailyCommandConfirmedSymbol
      ? `最近回放：${dailyCommandConfirmedSymbol}`
      : "等待首页确认按钮";
  const homeQuantP1P2P3CheckpointReady =
    Boolean(homeQuantVisibleTaskId) &&
    dailyCommandTushareFirstLedgerReady &&
    dailyCommandP2ThreeSurfaceReady &&
    dailyCommandP3OneGlanceReadable;
  const homeQuantP1P2P3CheckpointGaps = [
    homeQuantVisibleTaskId ? "" : "P1 task id",
    dailyCommandTushareFirstLedgerReady ? "" : "Tushare ledger",
    dailyCommandP2ThreeSurfaceReady ? "" : "P2 cache/ledger/packet",
    dailyCommandP3OneGlanceReadable ? "" : "P3 可读结论",
    dailyCommandFactorCandidateHandoffReady ? "" : "Factor handoff"
  ].filter(Boolean);
  const homeQuantP1P2P3CheckpointLabel = homeQuantP1P2P3CheckpointReady
    ? `已完成 P1/P2/P3 本地回放：${homeQuantVisibleTaskId}；Factor handoff ${dailyCommandFactorCandidateHandoffReady ? "已接上" : "待回放"}`
    : `等待 ${homeQuantP1P2P3CheckpointGaps.join(" / ") || "本地回放"}`;
  const homeQuantP1P2P3CheckpointItems: MetricItem[] = [
    { label: "一眼 checkpoint", value: homeQuantP1P2P3CheckpointLabel, tone: homeQuantP1P2P3CheckpointReady ? "good" : "warn" },
    { label: "P1 task", value: homeQuantVisibleTaskId || "等待确认按钮返回 task id", tone: homeQuantVisibleTaskId ? "good" : "warn" },
    { label: "Tushare ledger", value: dailyCommandTushareFirstLedgerLabel, tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn" },
    { label: "P2 三面", value: dailyCommandP2CheckpointLabel, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
    { label: "P3 结论", value: dailyCommandExplainableResultLabel, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
    { label: "Factor handoff", value: dailyCommandFactorCandidateHandoffLabel, tone: dailyCommandFactorCandidateHandoffReady ? "good" : "warn" },
    { label: "边界", value: "checkpoint 只合成现有 cache / ledger / packet；不创建 task、不补调 provider/model", tone: "good" }
  ];
  const dailyCommandCurrentResearchSnapshotItems: MetricItem[] = [
    { label: "最近标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
    { label: "确认任务", value: homeQuantVisibleTaskId ? `${homeQuantVisibleTaskId} (${homeQuantVisibleTaskSource})` : "等待确认按钮返回 task id", tone: homeQuantVisibleTaskId ? "good" : "warn" },
    { label: "数据链", value: dailyCommandTushareFirstLedgerLabel, tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn" },
    { label: "P2 写入", value: dailyCommandP2SurfaceCompletionLabel, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
    { label: "P3 结论", value: dailyCommandExplainableResultLabel, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
    { label: "下一步", value: dailyCommandP3OneGlanceReadable ? "看股票量化推演和次日图谱" : "先确认股票代码，等待本地回放", tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
    { label: "边界", value: "首屏快照只读已有 cache / ledger / packet；不会创建 task、不会补调 Tushare/DeepSeek", tone: "good" }
  ];
  const dailyCommandCurrentResearchSnapshotReadableSentence = homeQuantP1P2P3CheckpointReady
    ? `${dailyCommandConfirmedSymbolLabel} 已有最近确认结果：${dailyCommandExplainableResultLabel}；${dailyCommandTushareFirstLedgerLabel}；P2 ${dailyCommandP2SurfaceCompletionLabel}；下一步看股票量化推演和次日图谱。`
    : dailyCommandP0LocalReadinessReady
      ? dailyCommandConfirmedSymbol
        ? `${dailyCommandConfirmedSymbolLabel} 已有本地回放线索；${homeQuantP1P2P3CheckpointLabel}；需要更新时再手动点击确认按钮。`
        : "本地联通已 ready；先在首页输入股票代码并点击确认，输入本身保持静默。"
      : "P0 本地联通还没全部 ready；先看一键启动预检，等 FastAPI、bootstrap、desktop preflight 和 React 变绿。";
  const homeQuantConfirmItems: MetricItem[] = [
    { label: "输入代码", value: homeQuantSymbolValidation.valid ? homeQuantSymbolValidation.normalized : homeQuantSubmitDisabledReason, tone: homeQuantSymbolValidation.valid ? "good" : "warn" },
    { label: "确认按钮", value: homeQuantCanSubmit ? `可点击：${homeQuantSymbolValidation.normalized} 将创建 Tushare-first POST task` : `不可点击：${homeQuantSubmitDisabledReason}`, tone: homeQuantCanSubmit ? "good" : "warn" },
    { label: "P0 闸门", value: dailyCommandP0LocalReadinessReady ? "ready：可点击确认" : "check：先恢复本地联通", tone: dailyCommandP0LocalReadinessReady ? "good" : "warn" },
    { label: "P1 手动确认", value: homeP1ManualConfirmLabel, tone: homeP1ManualConfirmReady ? "good" : "warn" },
    { label: "P1 runtime", value: homeP1ManualConfirmStatus, tone: homeP1ManualConfirmReady ? "good" : "warn" },
    { label: "任务状态", value: homeQuantReadbackStatus, tone: homeQuantVisibleTaskId ? "good" : "warn" },
    { label: "链路 checkpoint", value: homeQuantP1P2P3CheckpointLabel, tone: homeQuantP1P2P3CheckpointReady ? "good" : "warn" },
    { label: "Tushare-first", value: "确认按钮才 POST；DeepSeek skipped，成功后通过 GET cache 回放", tone: "good" },
    { label: "浏览器验收", value: homeP1BrowserEvidenceLabel, tone: "warn" },
    { label: "P2/P3 回放", value: dailyCommandSmallDataWritebackState, tone: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn" },
    { label: "边界", value: "首页输入静默；不从页面打开、输入、React render 或 GET cache 外联；不交易、不改 action", tone: "good" }
  ];
  const homeQuantConfirmButtonChainRows = [
    {
      链路段: "1. 输入静默",
      当前状态: homeQuantSymbolValidation.valid ? `本地格式已通过：${homeQuantSymbolValidation.normalized}` : homeQuantSubmitDisabledReason,
      用户下一步: "输入 6 位 A 股代码或带市场后缀代码",
      证据: "normalizeHomeAshareSymbolInput",
      边界: "输入只做本地格式校验；不创建 task、不调用 Tushare/DeepSeek。"
    },
    {
      链路段: "2. P0 gate",
      当前状态: dailyCommandP0LocalReadinessReady ? "P0 ready：按钮可用" : "P0 check：按钮禁用",
      用户下一步: dailyCommandP0LocalReadinessReady ? "确认代码后点击按钮" : "先让 FastAPI、bootstrap、desktop preflight 和连接证据变绿",
      证据: "homeQuantP0ConfirmGateEvidence",
      边界: "P0 gate 只是前后端联通门槛，不代表 provider 已调用或 release ready。"
    },
    {
      链路段: "3. 确认按钮",
      当前状态: homeP1ManualConfirmReady ? "点击后创建 Tushare-first POST task" : "等待 P1 runtime ready",
      用户下一步: "点击一次确认按钮，然后看任务编号",
      证据: "POST /api/candidate-radar/quant-projection；include_tushare=true；include_deepseek=false",
      边界: "只有显式点击按钮才创建 task；页面打开、搜索输入、React render 和 GET cache 不外联。"
    },
    {
      链路段: "4. 任务进度",
      当前状态: homeQuantVisibleTaskId ? `任务来源已可见：${homeQuantVisibleTaskId}` : "等待按钮返回 task id",
      用户下一步: homeQuantVisibleTaskCanPoll ? "等待 TaskStatusPanel success 后看 P2/P3 回放" : homeQuantVisibleTaskId ? "按 cache / ledger / packet 只读回放最近确认链" : "按钮返回后先看任务进度",
      证据: "TaskStatusPanel + /api/tasks 本地轮询",
      边界: "任务进度只读本地 FastAPI；cache 恢复不会创建第二个 task、不自动重试、不下单、不改 strategy action。"
    },
    {
      链路段: "5. 写回回放",
      当前状态: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "P2/P3 已从 cache / call_ledger / packet 回放" : "等待任务写入本地三面",
      用户下一步: "看股票量化推演、次日图谱和下一票雷达详情",
      证据: "CandidateRadar cache / call_ledger / packet",
      边界: "回放不创建第二个 task、不补调 provider/model、不读取 token/key。"
    }
  ];
  const homeQuantPostConfirmNextStepLabel = dailyCommandP2ThreeSurfaceReady || dailyCommandP3OneGlanceReadable
    ? "已进入回放：先看股票量化推演，再打开次日图谱；需要换标的再点确认"
    : homeQuantVisibleTaskId
      ? "先看任务进度；success 后刷新本地回放"
      : "先输入股票代码并点击确认按钮";
  const homeQuantPostConfirmOneGlanceItems: MetricItem[] = candidateQuantPostConfirmOneGlanceRows.length
    ? candidateQuantPostConfirmOneGlanceRows.map((row) => {
        const rowTone = String(row.tone ?? "neutral");
        const tone = ["good", "warn", "bad", "neutral"].includes(rowTone) ? rowTone as MetricItem["tone"] : "neutral";
        const label = String(row.label ?? row["状态项"] ?? row.item_key ?? "确认后状态");
        const itemKey = String(row.item_key ?? row["状态项"] ?? row.label ?? "");
        return {
          label,
          value: itemKey === "next_step" || label === "先看哪里"
            ? homeQuantPostConfirmNextStepLabel
            : String(row.value ?? row["当前状态"] ?? row.status ?? "--"),
          tone
        };
      })
    : [
        { label: "任务编号", value: homeQuantVisibleTaskId || "等待确认按钮返回 task id", tone: homeQuantVisibleTaskId ? "good" : "warn" },
        { label: "任务来源", value: homeQuantVisibleTaskSource, tone: homeQuantVisibleTaskId ? "good" : "warn" },
        { label: "先看哪里", value: homeQuantPostConfirmNextStepLabel, tone: dailyCommandP2ThreeSurfaceReady || dailyCommandP3OneGlanceReadable ? "good" : "warn" },
        { label: "P2 写回", value: "cache / call_ledger / packet 三面回放", tone: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn" },
        { label: "P3 结果", value: "股票量化推演 + 次日图谱 + 下一票雷达详情", tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
        { label: "DeepSeek", value: "skipped/pending 不阻塞；P5 governed executor 单独补", tone: "good" },
        { label: "安全边界", value: "回放不创建第二个 task，不下单，不改 strategy action", tone: "good" }
      ];
  const homeQuantPostConfirmReadableSentence = homeQuantVisibleTaskId
    ? `已看到 ${homeQuantVisibleTaskId}（${homeQuantVisibleTaskSource}）；${candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "P2 三面已可读" : "P2 三面等待本地回放"}；${dailyCommandP3OneGlanceReadable ? `P3 结论：${dailyCommandExplainableResultLabel}` : "P3 结论等待本地 cache 回放"}；下一步看股票量化推演和次日图谱。`
    : "确认后会在这里显示任务编号、P2 三面、P3 结论和下一步入口。";
  const homeQuantPostConfirmReadbackState = homeQuantSubmitting
    ? "提交中：等待 FastAPI 返回 task id；不会重复创建第二个 task。"
    : homeQuantVisibleTaskCanPoll
      ? "任务已接收：TaskStatusPanel 正在轮询本地 FastAPI，success 后自动刷新 CandidateRadar / Factor / Next / tasks 回读。"
      : homeQuantVisibleTaskId
        ? "最近确认链来自本地 cache 回放；首页不启动第二个 TaskStatusPanel，也不创建第二个 task。"
        : "确认后首页会回读 CandidateRadar、股票量化推演、次日图谱和任务目录；输入代码本身保持静默。";
  const homeQuantPostConfirmHandoffRows = [
    {
      交接项: "任务进度",
      当前状态: homeQuantVisibleTaskId ? `已看到 ${homeQuantVisibleTaskId}` : "等待确认按钮",
      用户下一步: homeQuantVisibleTaskCanPoll ? "先看 TaskStatusPanel 是否 success，再看 P2/P3 回放" : homeQuantVisibleTaskId ? "按最近确认链只读回放 P2/P3；需要新标的再点击确认" : "输入代码并点击确认按钮",
      入口: "#tasks",
      边界: "只读任务进度；cache 恢复不创建第二个 Tushare-first task。"
    },
    {
      交接项: "股票量化推演",
      当前状态: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "P2/P3 本地回放已可读" : "等待 task 写入 cache / ledger / packet",
      用户下一步: "打开股票量化推演，复核支持/压制和 P3 可读结论",
      入口: "#factor",
      边界: "链接只切换本地模块；Factor 页 GET cache 不补调 Tushare/DeepSeek。"
    },
    {
      交接项: "次日图谱",
      当前状态: String(next.status ?? "等待次日图谱本地缓存"),
      用户下一步: "打开次日图谱，复核路径、参考线和 operation_zones",
      入口: "#next",
      边界: "operation_zones 只是复核区间；不是买卖、下单或 strategy action。"
    },
    {
      交接项: "下一票雷达结果",
      当前状态: dailyCommandP3OneGlanceReadable ? "P3 可解释结果可回放" : "等待 CandidateRadar checkpoint",
      用户下一步: "需要换标的时回下一票雷达确认输入区；输入仍保持静默，确认按钮才创建 task",
      入口: "#candidates/candidate-radar-search-quant-projection",
      边界: "结果回放只读 CandidateRadar cache / ledger / packet；不调用模型。"
    }
  ];
  const dailyCommandFrontendBackendAutoLinkRows = [
    {
      联通项: "前端 API client",
      当前状态: dailyCommandHealthOk ? "GET /health 已从本地后端回读" : "等待本地后端可达",
      证据: `configured=${CONFIGURED_API_BASE_DISPLAY_URL}; selected=${dailyCommandFrontendBackendSelectedApiBase}; candidates=${API_BASE_CANDIDATE_DISPLAY_URLS.join(" / ")}`,
      下一步: dailyCommandHealthOk ? "继续看 bootstrap runtime-mode packet" : "使用一键启动入口恢复本地 FastAPI / React 联通",
      边界: dailyCommandFrontendBackendAutoLinkBoundary
    },
    {
      联通项: "后端身份",
      当前状态: dailyCommandHealthOk ? String(health.service ?? "Command Center 3.0 health ok") : "等待 Command Center 3.0 health JSON",
      证据: "GET /health external_calls_on_startup=false",
      下一步: dailyCommandHealthOk ? "继续确认本地 runtime-mode packet" : "查看桌面壳预检里的 FastAPI 诊断",
      边界: "health 回读只验证本地服务身份；不刷新 provider/model、不写 cache/config"
    },
    {
      联通项: "失败回退",
      当前状态: dailyCommandCacheWarning ? "本地后端已联通；普通 cache 回读提示不阻断 P0" : error ? "显示本地后端离线提示" : "无前端联通错误",
      证据: "frontend_backend_auto_link_scope=local_fastapi_only",
      下一步: dailyCommandCacheWarning ? "继续在首页确认股票代码；普通 cache 提示留在待补证据里" : error ? "打开一键启动预检，按 FastAPI / bootstrap / desktop preflight / React 四段恢复" : "联通正常时在首页确认股票代码",
      边界: "离线提示只帮助恢复 P0；不会绕过确认按钮触发 Tushare，也不会调用 DeepSeek"
    },
    {
      联通项: "P0 可继续闸门",
      当前状态: dailyCommandP0LocalReadinessLabel,
      证据: "health ok + bootstrap runtime-mode packet + desktop preflight one-click packet + current React page",
      下一步: dailyCommandP0LocalReadinessReady ? "在首页确认股票代码；输入保持静默，确认按钮才触发 Tushare-first" : "回到一键启动预检；不要进入 P1 投研入口",
      边界: dailyCommandP0LocalReadinessBoundary
    }
  ];
  const dailyCommandHomeAggregateReadbackRows = [
    {
      回读项: "1. 本地服务身份",
      当前状态: dailyCommandHealthOk ? "已回读 Command Center 3.0 health" : "等待 /health",
      接口: "GET /health",
      用户下一步: dailyCommandHealthOk ? "继续看运行模式和桌面预检" : "先恢复本地 FastAPI",
      边界: "只确认本机后端身份；不刷新 provider/model、不创建 task"
    },
    {
      回读项: "2. 运行模式",
      当前状态: bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet" ? "runtime-mode packet 可读" : "等待 bootstrap status",
      接口: "GET /api/bootstrap/status",
      用户下一步: "确认 cache_only/manual/live_light 口径后再进入 P1",
      边界: "只读模式配置；不创建 live_light task、不外联"
    },
    {
      回读项: "3. 一键启动预检",
      当前状态: desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache" ? "desktop preflight cache 可读" : "等待 desktop preflight",
      接口: "GET /api/desktop/preflight-cache",
      用户下一步: "四段 ready 后继续首页确认股票代码",
      边界: "只读启动器回执；不启动 FastAPI/Vite、不打开浏览器"
    },
    {
      回读项: "4. 投研链路缓存",
      当前状态: [
        candidates.status ? `CandidateRadar=${String(candidates.status)}` : "CandidateRadar=waiting",
        factor.status ? `Factor=${String(factor.status)}` : "Factor=waiting",
        next.status ? `Next=${String(next.status)}` : "Next=waiting",
        taskIndex?.status ? `Tasks=${String(taskIndex.status)}` : "Tasks=waiting"
      ].join(" / "),
      接口: "GET /api/candidate-radar/cache + /api/factor-quant/cache + /api/next-session/cache + /api/tasks",
      用户下一步: dailyCommandP0LocalReadinessReady ? "可以在首页确认股票代码；已有结果直接回放 P2/P3" : "先让 P0 四段 ready",
      边界: "首页是多接口本地聚合，不依赖单个 /api/command-center/cache；这些 GET 只读回放，不补调 Tushare/DeepSeek"
    }
  ];
  const dailyCommandP0EntryGateRows = [
    {
      闸门项: "1. FastAPI health",
      当前状态: dailyCommandHealthOk ? "通过：本地后端可达" : "未通过：先恢复本地后端",
      用户下一步: dailyCommandHealthOk ? "继续看 bootstrap status" : "打开一键启动预检，按 FastAPI 诊断恢复",
      证据: "GET /health external_calls_on_startup=false",
      边界: "只读健康回读；不启动服务、不创建 task、不调用 provider/model"
    },
    {
      闸门项: "2. Bootstrap runtime",
      当前状态: bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet" ? "通过：运行模式 packet 可读" : "未通过：等待 bootstrap status",
      用户下一步: bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet" ? "继续看 desktop preflight cache" : "回一键启动预检查 bootstrap status",
      证据: "GET /api/bootstrap/status command_center_3_bootstrap_runtime_mode_packet",
      边界: "只读运行模式；不写配置、不创建 live_light task、不改外联口径"
    },
    {
      闸门项: "3. Desktop preflight",
      当前状态: desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache" ? "通过：一键启动 packet 可读" : "未通过：等待桌面预检 cache",
      用户下一步: desktopPreflight.packet_key === "command_center_3_desktop_shell_preflight_cache" ? "继续确认 React/Vite 页面" : "回桌面壳预检查本地快捷入口",
      证据: "GET /api/desktop/preflight-cache command_center_3_desktop_shell_preflight_cache",
      边界: "首页只读预检 packet；不启动 FastAPI/Vite、不打开浏览器"
    },
    {
      闸门项: "4. 进入 P1",
      当前状态: dailyCommandP0LocalReadinessReady ? "P0 ready：可以在首页确认股票代码" : "P0 未 ready：不要进入 P1",
      用户下一步: dailyCommandP0LocalReadinessReady ? "在首页输入代码；输入静默，确认按钮才创建 Tushare-first task，需要详情再进下一票雷达" : "先把前三段变绿，再回首页确认股票代码",
      证据: "health + bootstrap packet + desktop preflight packet + current React page",
      边界: "P0 ready 不代表 Tushare/DeepSeek 已调用，也不是 release ready 或 14 LTG 完成"
    }
  ];
  const dailyCommandOneScreenActionRows = candidateQuantOneScreenActionRows.length
    ? candidateQuantOneScreenActionRows.map((row) => ({
        行动: String(row["行动"] ?? row.action_key ?? "行动"),
        当前状态: String(row["当前状态"] ?? row.status ?? "等待本地回放"),
        用户下一步: String(row["用户下一步"] ?? row.next_action ?? "先完成 P0 联通，再在首页或下一票雷达确认代码"),
        入口: String(row["入口"] ?? row.entry ?? "下一票雷达"),
        边界: String(row["边界"] ?? row.boundary ?? "首页回放 CandidateRadar packet；不会从回放行创建 task 或调用模型。")
      }))
    : [
        {
          行动: "1. 确认",
          当前状态: dailyCommandP0LocalReadinessReady ? "P0 ready：可以在首页确认股票代码" : "P0 check：先恢复本地联通",
          用户下一步: dailyCommandP0LocalReadinessReady ? "在首页输入股票代码并点击确认按钮；需要详情再进下一票雷达" : "先打开一键启动预检恢复四段联通",
          入口: dailyCommandP0LocalReadinessReady ? "#home-p1-symbol-confirm" : "#desktop",
          边界: "首页确认卡和下一票雷达确认按钮都走 P1 task；页面打开、输入和 GET cache 不创建 Tushare-first task。"
        },
        {
          行动: "2. 任务",
          当前状态: "等待首页或下一票雷达确认按钮返回 task id",
          用户下一步: "确认后看 TaskStatusPanel，本地任务完成后刷新 cache",
          入口: "首页确认按钮 / 下一票雷达确认按钮 / TaskStatusPanel",
          边界: "只有首页或下一票雷达确认按钮可创建 Tushare-first POST task；回放清单不提交 task。"
        },
        {
          行动: "3. 写回",
          当前状态: dailyCommandSmallDataWritebackState,
          用户下一步: "回放 cache / call_ledger / packet 三面",
          入口: "CandidateRadar cache / ledger / packet",
          边界: dailyCommandSmallDataWritebackBoundary
        },
        {
          行动: "4. 结果",
          当前状态: String(candidateQuantInterpretation.ordinary_result_summary ?? "等待搜票确认后的可解释结果"),
          用户下一步: String(candidateQuantInterpretation.ordinary_result_next_step ?? "确认任务完成后看股票量化推演和次日图谱"),
          入口: "股票量化推演 / 次日图谱",
          边界: "结果只是研究回放；不调用 DeepSeek、不覆盖 strategy action、不生成交易指令。"
        }
      ];
  const dailyCommandOneScreenActionLabel = dailyCommandOneScreenActionRows
    .map((row) => `${row.行动}: ${row.当前状态}`)
    .join(" / ");
  const dailyCommandUsableShortestPathRows = [
    {
      阶段: "P0 一键启动和本地联通",
      当前状态: dailyCommandConnectionState,
      用户下一步: dailyCommandNeedsStartupRecovery ? "先打开一键启动预检，按四段回读恢复本地联通" : "联通已通过，先在首页输入股票代码",
      证据: "GET /health + bootstrap status + desktop preflight cache",
      边界: "页面打开、React render 和 GET cache 只读；不启动服务、不外联、不读取 token/key"
    },
    {
      阶段: "P1 确认按钮触发 Tushare-first",
      当前状态: "等待用户在首页或下一票雷达输入代码并点击确认",
      用户下一步: "输入 6 位 A 股代码，点击“确认并生成 3.0 量化推演”",
      证据: "CandidateRadar 搜票确认 POST task contract",
      边界: "搜索输入只做本地校验；只有确认按钮创建 POST task / worker，DeepSeek skipped"
    },
    {
      阶段: "P2 小数据写入 cache / ledger / packet",
      当前状态: dailyCommandSmallDataWritebackState,
      用户下一步: "看 task id 和 TaskStatusPanel，成功后刷新本地 cache / ledger / packet 回放",
      证据: "ordinary_writeback_surface_summary_rows + call_ledger + packet",
      边界: "GET cache 只读回放；不补调 Tushare、DeepSeek，不展示 token/key/raw log"
    },
    {
      阶段: "P3 候选、量化推演、次日图谱",
      当前状态: dailyCommandExplainableResultLabel,
      用户下一步: dailyCommandExplainableResultNext,
      证据: "ordinary_result_quick_read_rows + result handoff index",
      边界: "结果只整理本地证据；候选雷达不是买入指令，不交易、不下单、不改 strategy action"
    },
    {
      阶段: "P4 工程审计噪音下沉",
      当前状态: "普通入口先显示摘要、路径和结果位置",
      用户下一步: "只有排障、验收或补证时再展开开发详情",
      证据: "developer-audit-details 默认折叠",
      边界: "不把 raw packet、receipt、matrix、sanitizer 或 mock 当 production evidence"
    },
    {
      阶段: "P5 DeepSeek governed executor 单独补",
      当前状态: dailyCommandDeepSeekGovernanceState,
      用户下一步: "先使用 Tushare-first、小数据写入和基础图谱；DeepSeek 作为单独补证",
      证据: "ordinary_model_governance_rows + governed executor checklist",
      边界: "governed executor 完成前不真实调用 DeepSeek；之后也不能覆盖价格、持仓、factor、operation_zones 或 strategy action"
    },
    {
      阶段: "P6 回到 14 LTG direct evidence",
      当前状态: "re-entry gate visible；strict closeout 仍是 0/14",
      用户下一步: "按 LTG next acceptance action rows 逐项补 current-head direct evidence",
      证据: "usable_path_strict_closeout_handoff_rows.P6",
      边界: "P0-P6 当前 checkpoint 不是 14 LTG 完成；P0-P5 可用化 checkpoint 不是 14 LTG 完成；mock、matrix、sanitizer、local receipt 不能关闭 LTG"
    }
  ];
  const dailyCommandP6StrictCloseoutReentryRows = [
    {
      回归项: "1. 可用化 checkpoint",
      当前状态: "P0-P6 当前 checkpoint 已前置给使用者；P0-P5 ordinary path 是可用路径，P6 是 strict closeout 回归门",
      用户下一步: "继续按一键启动、搜票确认、小数据写回和基础图谱使用",
      入口: "今日作战台 / 下一票雷达 / 股票量化推演",
      边界: "P0-P6 当前 checkpoint 不是 14 LTG 完成；P0-P5 可用化 checkpoint 不是 14 LTG 完成"
    },
    {
      回归项: "2. strict closeout 入口",
      当前状态: "strict closeout 仍是 0/14；只按 current-head direct evidence 关闭",
      用户下一步: "打开迁移状态页，按 LTG next acceptance action rows 逐项补证",
      入口: "#migration",
      边界: "mock、matrix、sanitizer、local receipt 不能关闭 LTG"
    },
    {
      回归项: "3. 任务证据回放",
      当前状态: "cache / ledger / packet 可作为可审计回放，不等于 production acceptance",
      用户下一步: "查看任务目录和回放，只确认本地证据是否完整",
      入口: "#tasks",
      边界: "不声明 release ready、不触发 provider/model、不改变 strategy action"
    }
  ];
  const dailyCommandUsablePathP1Done = Boolean(homeQuantVisibleTaskId) || dailyCommandTushareFirstLedgerReady;
  const dailyCommandUsablePathP1State = dailyCommandUsablePathP1Done
    ? "done"
    : dailyCommandP0LocalReadinessReady
      ? "active"
      : "blocked";
  const dailyCommandUsablePathP1Detail = dailyCommandUsablePathP1Done
    ? dailyCommandTushareFirstLedgerReady
      ? "ledger ready"
      : "task visible"
    : dailyCommandP0LocalReadinessReady
      ? "confirm"
      : "blocked";
  const dailyCommandUsablePathP2State = dailyCommandP2ThreeSurfaceReady
    ? "done"
    : dailyCommandUsablePathP1Done
      ? "active"
      : "waiting";
  const dailyCommandUsablePathP2Detail = dailyCommandP2ThreeSurfaceReady
    ? "cache/ledger/packet"
    : dailyCommandUsablePathP1Done
      ? "writeback"
      : "after P1";
  const dailyCommandUsablePathP3State = dailyCommandP3OneGlanceReadable
    ? "done"
    : dailyCommandP2ThreeSurfaceReady
      ? "active"
      : "waiting";
  const dailyCommandUsablePathP3Detail = dailyCommandP3OneGlanceReadable
    ? "readable"
    : dailyCommandP2ThreeSurfaceReady
      ? "review"
      : "after P2";
  const dailyCommandUsablePathStageRailSteps = [
    {
      key: "p0",
      label: "P0 本地联通",
      state: dailyCommandP0LocalReadinessReady ? "done" : "blocked",
      detail: dailyCommandP0LocalReadinessReady ? "ready" : "check"
    },
    {
      key: "p1",
      label: "P1 确认按钮",
      state: dailyCommandUsablePathP1State,
      detail: dailyCommandUsablePathP1Detail
    },
    {
      key: "p2",
      label: "P2 小数据",
      state: dailyCommandUsablePathP2State,
      detail: dailyCommandUsablePathP2Detail
    },
    {
      key: "p3",
      label: "P3 可解释结果",
      state: dailyCommandUsablePathP3State,
      detail: dailyCommandUsablePathP3Detail
    },
    {
      key: "p4",
      label: "P4 审计下沉",
      state: "done",
      detail: "quiet"
    },
    {
      key: "p5",
      label: "P5 解释治理",
      state: "active",
      detail: "governed"
    },
    {
      key: "p6",
      label: "P6 LTG 证据",
      state: "waiting",
      detail: "0/14"
    }
  ];
  const dailyCommandUsableShortestPathPrimaryRows = dailyCommandUsableShortestPathRows.filter((row) =>
    ["P0", "P1", "P2", "P3"].some((prefix) => String(row.阶段).startsWith(prefix))
  );
  const dailyCommandUsableShortestPathAuditRows = dailyCommandUsableShortestPathRows.filter((row) =>
    ["P4", "P5", "P6"].some((prefix) => String(row.阶段).startsWith(prefix))
  );
  const dailyCommandUsablePathPrimaryStageRailSteps = dailyCommandUsablePathStageRailSteps.slice(0, 4);
  const dailyCommandUsablePathAuditStageRailSteps = dailyCommandUsablePathStageRailSteps.slice(4);
  const dailyCommandConnectivityPriority = dailyCommandNeedsStartupRecovery
    ? "先恢复本地联通；缓存和投研入口等 health/preflight 变绿后再看"
    : "本地联通可用；先在首页确认股票代码，再按最近缓存、数据健康、下一票雷达、股票量化推演复核";
  const dailyCommandLauncherState = desktopLauncherContract.launcher_executable === true
    ? "一键启动入口可用；启动器会等 FastAPI 和页面 ready"
    : "一键启动入口待检查；可先使用本地启动器恢复";
  const dailyCommandStartupRecoveryLabel = error
    ? "打开桌面壳预检，按本地快捷入口重启"
    : desktopLauncherContract.launcher_executable === true
      ? "本地快捷入口可用；需要重启时去桌面壳预检"
      : "去桌面壳预检查看启动器缺口";
  const dailyCommandStartupBoundary =
    "首页不启动服务；一键启动只由本机快捷入口执行，状态来自 health/preflight cache";
  const dailyCommandStartupSuccessCondition = String(
    oneClickStartupSummary.success_condition ??
      "FastAPI /health 必须返回 Command Center 3.0 健康 JSON，/api/bootstrap/status 必须返回 runtime-mode packet，/api/desktop/preflight-cache 必须返回一键启动 packet，React/Vite 必须返回 Command Center 3.0 前端 HTML 后才打开页面。"
  );
  const dailyCommandStartupFailureAction = String(
    oneClickStartupSummary.blocked_next_action ??
      "先看启动器的可操作诊断：FastAPI、bootstrap status、desktop preflight cache、React/Vite 哪段失败；再检查 8710/5173 是否被占用，或进入桌面壳预检。"
  );
  const dailyCommandStartupDiagnosticSurfaces = Array.isArray(oneClickStartupSummary.diagnostic_surfaces)
    ? oneClickStartupSummary.diagnostic_surfaces.join(" / ")
    : "FastAPI /health Command Center 3.0 JSON / bootstrap status runtime-mode packet / desktop preflight cache one-click packet / React/Vite Command Center 3.0 HTML / 8710/5173 port occupancy guidance";
  const dailyCommandStartupReadbackLabel = error
    ? dailyCommandCacheWarning || "重启后刷新本页；FastAPI、bootstrap、desktop preflight cache、React/Vite 变绿才继续投研"
    : dailyCommandHealthOk
      ? "联通已由 GET /health 回读；可继续看缓存和投研入口"
      : "正在等待 GET /health 和 desktop preflight cache 回读";
  const dailyCommandStartupReadbackOrder =
    "恢复回读顺序：FastAPI /health -> bootstrap status -> desktop preflight cache -> React/Vite 前端 -> 今日作战台摘要";
  const dailyCommandStartupReadbackBoundary =
    "恢复回读只读取 GET /health、GET /api/bootstrap/status、GET /api/desktop/preflight-cache；不启动服务、不创建 task、不外联";
  const dailyCommandStartupReadbackRows = [
    {
      回读项: "FastAPI health",
      当前状态: dailyCommandHealthOk ? "已联通" : "等待联通",
      证据: "GET /health",
      通过条件: "Command Center 3.0 health JSON 且 external_calls_on_startup=false",
      下一步: dailyCommandHealthOk ? "继续看 bootstrap runtime-mode packet" : "回桌面壳预检查看 FastAPI 启动诊断",
      边界: "只读健康检查，不启动服务、不创建 task"
    },
    {
      回读项: "Bootstrap status",
      当前状态: bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet" ? "runtime-mode packet 可读" : "等待 runtime-mode packet",
      证据: "GET /api/bootstrap/status",
      通过条件: "返回 cache_only/manual/live_light/live_full 运行模式口径",
      下一步: bootstrapStatus.packet_key === "command_center_3_bootstrap_runtime_mode_packet" ? "继续确认 desktop preflight cache" : "查看一键启动预检里的 bootstrap status 诊断",
      边界: "只读运行模式，不写配置、不创建 live_light task"
    },
    {
      回读项: "Desktop preflight cache",
      当前状态: desktopLauncherContract.launcher_executable === true ? "一键启动入口可用" : "等待桌面壳预检",
      证据: "GET /api/desktop/preflight-cache",
      通过条件: "返回 command_center_3_desktop_shell_preflight_cache 一键启动 packet",
      下一步: dailyCommandNeedsStartupRecovery ? "先打开一键启动预检" : "继续确认 React/Vite 前端",
      边界: "首页只展示预检 packet，不启动 FastAPI/Vite/浏览器"
    },
    {
      回读项: "React/Vite 前端",
      当前状态: desktopLauncherContract.launcher_executable === true ? "一键启动入口可验证前端" : "等待桌面壳预检",
      证据: "desktop preflight cache launcher_readback",
      通过条件: "本地启动器可检查 Command Center 3.0 前端 HTML",
      下一步: dailyCommandNeedsStartupRecovery ? "先打开一键启动预检" : "继续在首页确认股票代码，再看股票量化推演",
      边界: "首页只展示预检结果，不启动 FastAPI/Vite/浏览器"
    }
  ];
  const dailyCommandAuditDemotionRows = [
    {
      审计入口: "普通摘要",
      可见内容: "下一步、本地联通、结果位置、缺数据口径和仅供研究边界",
      用户动作: "先按最近缓存、数据健康、下一票雷达和股票量化推演复核",
      边界: "不展示 raw packet、call_ledger、runbook、LTG 表或 provider/model 明细"
    },
    {
      审计入口: "开发详情",
      可见内容: "call ledger、release gate、runtime mode、storage、task catalog 和配置状态",
      用户动作: "只有排障、验收或补证时展开",
      边界: "默认折叠，不压过 P0 联通、P1 搜票确认、P2/P3 结果回放"
    },
    {
      审计入口: "补证按钮",
      可见内容: "手动补证状态、任务状态面板和任务回执",
      用户动作: "需要时手动确认按钮门控 POST task",
      边界: "页面打开、React render 和 GET cache 不创建 task、不调用 Tushare/DeepSeek/GitHub"
    }
  ];
  const dailyCommandReviewOrder = error
    ? "先看一键启动预检恢复本地联通，再回今日作战台"
    : "先确认 P0 本地联通，再在首页确认股票代码，之后回放股票量化推演和次日图谱结果";
  const dailyCommandResultComposition = [
    `候选：${Number(candidateCounts?.candidate_count ?? 0) ? String(candidateCounts?.candidate_count) : "等待缓存"}`,
    `量化：${String(factor.status ?? factor.mode ?? "等待缓存")}`,
    `次日图谱：${String(next.status ?? "等待缓存")}`,
    `风险：${String(riskCounts?.active_risk_count ?? riskCounts?.risk_count ?? 0)} 项`
  ].join(" / ");
  const dailyCommandResultLocation =
    "结果位置：今日作战台看总览，下一票雷达看候选，股票量化推演看单票结果，次日图谱看路径；入口都只读跳转";
  const dailyCommandMissingDataBoundary =
    "缺数据先看 pending / 缺少证据；不能把空缓存当成无风险，也不能当成生产验收完成";
  const dailyCommandP3ReplayActionRows = candidateQuantHandoffRows.length
    ? candidateQuantHandoffRows.map((row) => ({
        结果入口: String(row["入口"] ?? row.handoff_key ?? "P3 结果入口"),
        当前状态: String(row["当前状态"] ?? row.status ?? "等待 CandidateRadar P3 handoff 回放"),
        用户下一步: String(row["用户下一步"] ?? row.next_step ?? dailyCommandExplainableResultNext),
        入口: String(row.href ?? row["href"] ?? row.entry ?? "#candidates"),
        边界: String(row["边界"] ?? row.boundary ?? "只读切换本地入口；不创建 task、不调用 provider/model。")
      }))
    : [
        {
          结果入口: "下一票雷达",
          当前状态: Number(candidateCounts?.candidate_count ?? 0) ? `候选=${String(candidateCounts?.candidate_count)}` : "等待候选缓存",
          用户下一步: "复核候选、确认任务状态和结果回放位置；换标的仍需点击确认按钮",
          入口: "#candidates/candidate-radar-search-quant-projection",
          边界: "只读跳转到雷达确认输入区；不会从结果入口创建 task，搜索输入仍保持静默"
        },
        {
          结果入口: "股票量化推演",
          当前状态: String(factor.status ?? factor.mode ?? "等待量化缓存"),
          用户下一步: "复核支持/压制、数据来源和缺少证据，再回到次日图谱看路径",
          入口: "#factor",
          边界: "只读跳转到量化推演模块；不会补调 Tushare、DeepSeek 或写 strategy action"
        },
        {
          结果入口: "次日图谱",
          当前状态: String(next.status ?? "等待次日图谱缓存"),
          用户下一步: "按路径、参考线、operation_zones 和缺少证据顺序复核",
          入口: "#next",
          边界: "只读跳转到次日图谱模块；不创建生成任务、不调用 Tushare/DeepSeek、不下单"
        }
      ];
  const dailyCommandResearchWorkflowReady =
    dailyCommandP0LocalReadinessReady &&
    Boolean(dailyCommandConfirmedSymbol) &&
    candidateQuantSmallDataWriteback.small_data_writeback_ready === true &&
    dailyCommandP3OneGlanceReadable;
  const dailyCommandResearchWorkflowStatus = dailyCommandResearchWorkflowReady
    ? "p0_p3_replay_ready"
    : dailyCommandP0LocalReadinessReady
      ? "ready_for_p1_confirm"
      : "p0_check_required";
  const dailyCommandResearchWorkflowNext = dailyCommandResearchWorkflowReady
    ? "直接看 P3 结果速读，再切到股票量化推演和次日图谱复核"
    : dailyCommandP0LocalReadinessReady
      ? "在首页输入股票代码，并点击确认按钮创建 Tushare-first task"
      : "先恢复 FastAPI、bootstrap、desktop preflight 和 React 四段联通";
  const dailyCommandResearchWorkflowReadableSentence = dailyCommandResearchWorkflowReady
    ? `${dailyCommandConfirmedSymbolLabel} 已完成 P1/P2/P3 本地回放；P3 结论：${dailyCommandExplainableResultLabel}；下一步看股票量化推演和次日图谱。`
    : dailyCommandP0LocalReadinessReady
      ? `本地联通已 ready；${dailyCommandConfirmedSymbol ? `${dailyCommandConfirmedSymbolLabel} 等待 P2/P3 回放补齐` : "先输入股票代码并点击确认按钮"}；下一步：${dailyCommandResearchWorkflowNext}。`
      : `P0 尚未 ready；下一步：${dailyCommandResearchWorkflowNext}。`;
  const dailyCommandResearchWorkflowRows = [
    {
      链路段: "P0 本地联通",
      当前状态: dailyCommandP0LocalReadinessReady ? "ready：本地四段已接上" : "check：先恢复本地四段",
      用户下一步: dailyCommandP0LocalReadinessReady ? "可以在首页确认股票代码" : "打开桌面壳预检恢复本地后端/前端",
      证据: "health + bootstrap packet + desktop preflight packet + current React page",
      边界: "P0 只证明本地可用；不代表 Tushare/DeepSeek 已调用，也不是 14 LTG 完成。"
    },
    {
      链路段: "P1 确认按钮",
      当前状态: dailyCommandLatestTaskId ? `已看到最近任务：${dailyCommandLatestTaskStatus}` : "等待用户确认股票代码",
      用户下一步: dailyCommandLatestTaskId ? "按任务状态和回放结果继续复核" : "在首页或下一票雷达点击确认按钮；输入本身保持静默",
      证据: dailyCommandLatestTaskId || "CandidateRadar confirm button contract",
      边界: "首页结果回放不创建第二个 task；只有确认按钮创建 P1 task。"
    },
    {
      链路段: "P2 小数据三面",
      当前状态: dailyCommandSmallDataWritebackState,
      用户下一步: "确认 cache、call_ledger、packet 三面都能回放",
      证据: "search_quant_projection_small_data_writeback_summary",
      边界: dailyCommandSmallDataWritebackBoundary
    },
    {
      链路段: "P3 可解释结果",
      当前状态: dailyCommandExplainableResultLabel,
      用户下一步: dailyCommandExplainableResultNext,
      证据: dailyCommandP3OneGlanceEvidence,
      边界: dailyCommandExplainableResultBoundary
    },
    {
      链路段: "P5 DeepSeek",
      当前状态: dailyCommandP3OneGlanceModelState,
      用户下一步: "先使用 Tushare-first、小数据和基础图谱；DeepSeek 后续单独补证",
      证据: "search_quant_projection_interpretation_summary",
      边界: dailyCommandDeepSeekGovernanceBoundary
    }
  ];
  const dailyCommandSummaryPrimaryItems: MetricItem[] = [
    { label: "下一步", value: dailyCommandNextClick },
    { label: "本地联通", value: dailyCommandConnectionState, tone: dailyCommandHealthOk ? "good" : "warn" },
    { label: "P0 可继续", value: dailyCommandP0LocalReadinessLabel, tone: dailyCommandP0LocalReadinessReady ? "good" : "warn" },
    { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
    { label: "P2 小数据", value: dailyCommandSmallDataWritebackState, tone: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn" },
    { label: "P3 可读结论", value: dailyCommandExplainableResultLabel, tone: candidateQuantInterpretation.interpretation_ready === true ? "good" : "warn" },
    { label: "今日结果位置", value: dailyCommandResultLocation, tone: "good" },
    { label: "缺少证据", value: dailyCommandMissingEvidence, tone: dailyCommandMissingEvidence.includes("缓存") || dailyCommandMissingEvidence.includes("验收") || dailyCommandMissingEvidence.includes("收口") ? "warn" : "good" },
    { label: "仅供研究", value: dailyCommandResearchOnlyLabel, tone: "good" }
  ];
  const dailyCommandSummaryTechnicalItems: MetricItem[] = [
    { label: "主下一步", value: dailyCommandPrimaryActionLabel },
    { label: "主下一步边界", value: dailyCommandPrimaryActionBoundary, tone: "good" },
    { label: "联通优先级", value: dailyCommandConnectivityPriority, tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
    { label: "一键启动", value: dailyCommandLauncherState, tone: desktopLauncherContract.launcher_executable === true ? "good" : "warn" },
    { label: "启动恢复", value: dailyCommandStartupRecoveryLabel, tone: error || desktopLauncherContract.launcher_executable !== true ? "warn" : "good" },
    { label: "启动边界", value: dailyCommandStartupBoundary, tone: "good" },
    { label: "启动成功条件", value: dailyCommandStartupSuccessCondition, tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
    { label: "启动诊断", value: dailyCommandStartupDiagnosticSurfaces, tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
    { label: "启动失败处理", value: dailyCommandStartupFailureAction, tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
    { label: "恢复回读", value: dailyCommandStartupReadbackLabel, tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
    { label: "回读顺序", value: dailyCommandStartupReadbackOrder, tone: "good" },
    { label: "回读边界", value: dailyCommandStartupReadbackBoundary, tone: "good" },
    { label: "只读自检", value: dailyCommandP0CheckOnlyNext, tone: p0LauncherCheckOnlyRows.length ? "good" : "warn" },
    { label: "自动联通", value: dailyCommandFrontendBackendAutoLinkLabel, tone: dailyCommandHealthOk ? "good" : "warn" },
    { label: "自动联通边界", value: dailyCommandFrontendBackendAutoLinkBoundary, tone: "good" },
    { label: "P0 进入 P1 闸门", value: dailyCommandP0LocalReadinessReady ? "四段已通过；可在首页确认股票代码" : "先让 health / bootstrap / preflight / React 四段变绿", tone: dailyCommandP0LocalReadinessReady ? "good" : "warn" },
    { label: "联通后行动", value: dailyCommandP0QuickAction || "等待 P0 quick action rows", tone: dailyCommandP0QuickAction ? "good" : "warn" },
    { label: "一屏行动", value: dailyCommandOneScreenActionLabel || "等待 CandidateRadar 一屏行动回放", tone: candidateQuantOneScreenActionRows.length ? "good" : "warn" },
    { label: "确认结果链", value: dailyCommandConfirmOutcomeLabel, tone: candidateQuantConfirmOutcomeRows.length ? "good" : "warn" },
    { label: "确认后回放", value: "确认回执 -> 任务状态 -> P2 写回 -> P3 结果", tone: "good" },
    { label: "股票量化推演", value: "搜票后点生成 3.0 量化推演" },
    { label: "Factor handoff", value: dailyCommandFactorCandidateHandoffLabel, tone: dailyCommandFactorCandidateHandoffReady ? "good" : "warn" },
    { label: "量化缓存回放", value: dailyCommandFactorCacheFallbackLabel, tone: dailyCommandFactorCacheFallbackActive ? "warn" : "good" },
    { label: "下一票雷达", value: Number(candidateCounts?.candidate_count ?? 0) ? `候选=${String(candidateCounts?.candidate_count)}` : "等待缓存", tone: Number(candidateCounts?.candidate_count ?? 0) ? "good" : "warn" },
    { label: "今日查看顺序", value: dailyCommandReviewOrder, tone: error ? "warn" : "good" },
    { label: "今日结果组成", value: dailyCommandResultComposition },
    { label: "次日图谱", value: String(next.status ?? "等待缓存"), tone: next.status === "ready" ? "good" : "warn" },
    { label: "P2 边界", value: dailyCommandSmallDataWritebackBoundary, tone: "good" },
    { label: "P3 下一步", value: dailyCommandExplainableResultNext },
    { label: "P3 边界", value: dailyCommandExplainableResultBoundary, tone: "good" },
    { label: "P3 检查点", value: dailyCommandP3CheckpointLabel, tone: candidateQuantCheckpointRows.length ? "good" : "warn" },
    { label: "P5 解释治理", value: dailyCommandDeepSeekGovernanceState, tone: candidateQuantInterpretation.deepseek_model_ledger_ready === true ? "warn" : "good" },
    { label: "P5 边界", value: dailyCommandDeepSeekGovernanceBoundary, tone: "good" },
    { label: "本地缓存", value: dailyCommandCacheSourceLabel },
    { label: "数据链", value: dailyCommandTushareSourceLabel },
    { label: "解释状态", value: dailyCommandDeepSeekSourceLabel },
    { label: "外联触发边界", value: dailyCommandExternalTriggerBoundary, tone: "good" },
    { label: "待补证据", value: dailyCommandPendingSourceLabel, tone: dailyCommandPendingSourceLabel.includes("待补") || dailyCommandPendingSourceLabel.includes("验收") || dailyCommandPendingSourceLabel.includes("缓存") ? "warn" : "good" },
    { label: "降级提示", value: dailyCommandDegradedSourceLabel, tone: dailyCommandDegradedSourceLabel.includes("未标记") ? "good" : "warn" },
    { label: "最近成功回放", value: dailyCommandLastCache },
    { label: "数据来源", value: dailyCommandSourceState },
    { label: "补证状态", value: dailyCommandBackgroundTaskState, tone: dailyCommandBackgroundTaskTone },
    { label: "阻断/降级", value: dailyCommandBlockedState, tone: dailyCommandBlockedState.includes("未标记") ? "good" : "warn" },
    { label: "最近可用缓存", value: dailyCommandLastCache },
    { label: "任务边界", value: dailyCommandTaskBoundary },
    { label: "缺数据口径", value: dailyCommandMissingDataBoundary, tone: "good" }
  ];

  const refreshHomeResearchReadback = () => {
    void getCandidateRadarCache().then((res) => {
      setCandidates(res.data);
      if (res.ok === false) setError((current) => current || `candidate: ${res.error ?? "request_not_ok"}`);
    }).catch((err) => {
      setError((current) => current || `candidate: ${err instanceof Error ? err.message : String(err)}`);
    });
    void getFactorQuantCache().then((res) => setFactor(res.data)).catch(() => undefined);
    void getNextSessionCache().then((res) => setNext(res.data)).catch(() => undefined);
    void getTasks().then((res) => {
      setTaskIndexEnvelopeLedger(res.call_ledger ?? []);
      setTaskIndex(res.data);
      setTasks(res.data.tasks ?? []);
    }).catch(() => undefined);
  };

  const launchHomeQuantProjection = () => {
    if (!homeQuantCanSubmit || homeQuantSubmitting) return;
    setHomeQuantSubmitting(true);
    setHomeQuantSubmitError("");
    void postCandidateRadarQuantProjection({
      scan_mode: "search_quant_projection",
      symbol: homeQuantSymbolValidation.normalized,
      include_tushare: true,
      include_deepseek: false,
      user_approved: true,
      requested_by: "command_center_home_p1_confirm",
      p0_confirm_gate_evidence: homeQuantP0ConfirmGateEvidence,
      ordinary_confirm_chain_contract: {
        schema_version: "command_center_home_p1_confirm_contract.v1",
        trigger: "home_symbol_confirm_button",
        route: "POST /api/candidate-radar/quant-projection",
        task_type: "run_candidate_radar_quant_projection",
        search_input_creates_task: false,
        confirm_button_creates_task: true,
        include_tushare_requested: true,
        include_deepseek_requested: false,
        cache_get_external_calls: false,
        react_render_external_calls: false,
        does_not_execute_trades: true,
        does_not_modify_strategy_action: true
      },
      ordinary_post_confirm_replay_contract: {
        schema_version: "command_center_home_post_confirm_replay_contract.v1",
        source: "command_center_home_p1_confirm",
        readback_route: "GET /api/candidate-radar/cache",
        writeback_surfaces: ["cache", "call_ledger", "packet"],
        result_anchors: ["#tasks", "#factor", "#next"],
        creates_second_task_from_readback: false,
        readback_calls_provider_or_model: false,
        deepseek_policy: "skipped_until_governed_executor",
        does_not_execute_trades: true,
        does_not_modify_strategy_action: true
      }
    }).then((res) => {
      setHomeQuantReceipt(res);
      const nextTaskId = String(res.data?.task_id ?? res.data?.task?.task_id ?? "");
      setHomeQuantTaskId(nextTaskId);
      if (!res.ok || !nextTaskId) {
        setHomeQuantSubmitError(res.error ?? "home_quant_projection_task_not_created");
      } else {
        refreshHomeResearchReadback();
      }
    }).catch((err) => {
      setHomeQuantSubmitError(err instanceof Error ? err.message : String(err));
    }).finally(() => {
      setHomeQuantSubmitting(false);
    });
  };

  const launchLiveBootstrap = () => {
    const mode = String(bootstrapStatus.mode ?? "cache_only");
    if (mode !== "live_light") {
      setLiveBootstrapManualStatus("disabled_not_live_light");
      return;
    }
    if (liveLight.sources_enabled !== true) {
      setLiveBootstrapManualStatus("skipped_sources_disabled");
      return;
    }
    if (liveLight.bootstrap_task_implemented !== true) {
      setLiveBootstrapManualStatus("blocked_task_not_ready");
      return;
    }
    if (liveBootstrapTaskId || liveBootstrapManualStatus === "creating") return;
    if (readLiveBootstrapSessionKey() === liveBootstrapRunKey) {
      setLiveBootstrapManualStatus("skipped_session_once");
      return;
    }
    setLiveBootstrapManualStatus("creating");
    void postBootstrapLiveStartup({
      source: "command_center_home_manual",
      requested_by: "local_user",
      current_target: positionSummary?.ticker,
    }).then((res) => {
      setLiveBootstrapReceipt(res);
      setLiveBootstrapTaskId(String(res.data?.task_id ?? ""));
      const taskStep = String(res.data?.task?.current_step ?? (res.ok ? "created" : "failed"));
      if (res.ok) writeLiveBootstrapSessionKey(liveBootstrapRunKey);
      setLiveBootstrapManualStatus(taskStep);
      if (!res.ok) setError((current) => current || `bootstrap: ${res.error ?? "request_not_ok"}`);
    }).catch((err) => {
      setLiveBootstrapManualStatus("failed_safe");
      setError((current) => current || `bootstrap: ${err instanceof Error ? err.message : String(err)}`);
    });
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>今日作战台</h1>
          <p>先看下一步、数据来源、缺少证据和仅供研究边界。</p>
        </div>
        <StatusBadge label={dailyCommandStatusLabel} tone={dailyCommandHealthOk ? "good" : "warn"} />
      </div>
      <PageStateBanner
        loading={loading}
        error={error}
        empty={empty}
        emptyTitle="暂无今日作战台本地缓存"
        emptyDetail="首页只读取本地只读缓存；不会自动刷新外部数据。若为空，请先确认本地服务已启动。"
      />
      <PacketCard title="本地 FastAPI 接线速读" subtitle="打开软件后先看这张卡；入口只做本地跳转" status={dailyCommandHealthOk ? "connected" : "checking"}>
        <MetricGrid
          items={[
            { label: "本地后端", value: dailyCommandFrontendBackendAutoLinkLabel, tone: dailyCommandHealthOk ? "good" : "warn" },
            { label: "当前页面", value: dailyCommandP0LocalReadinessReady ? "FastAPI、bootstrap、desktop preflight 和 React 已接上" : "等待本地四段联通回读", tone: dailyCommandP0LocalReadinessReady ? "good" : "warn" },
            { label: "首页读法", value: "多接口本地聚合：health / bootstrap / preflight / radar / factor / next / tasks", tone: dailyCommandP0LocalReadinessReady ? "good" : "warn" },
            { label: "边用边看", value: dailyCommandFastApiProgressWatchLabel, tone: dailyCommandLatestTaskId || dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "投研入口", value: dailyCommandNeedsStartupRecovery ? "先看一键启动预检" : "在首页确认股票代码；需要详情再进下一票雷达", tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
            { label: "安全边界", value: "打开页面和输入代码不外联；确认按钮才触发 Tushare-first", tone: "good" }
          ]}
        />
        <div aria-label="daily command local fastapi open proof">
          <h3>打开后接线证明</h3>
          <MetricGrid items={dailyCommandOpenFastApiProofItems} />
          <p className="risk-note">这条证明只合成当前页面已拿到的 health、bootstrap、desktop preflight 和 React 状态；它不启动 FastAPI/Vite、不创建 task、不调用 Tushare/DeepSeek/GitHub，也不读取或展示 token/key。</p>
        </div>
        <div className="actions" aria-label="daily command fastapi connected user actions">
          <a href={dailyCommandPrimaryActionHref} aria-label="open primary action after local fastapi connection">{dailyCommandPrimaryActionLabel}</a>
          <a href="#tasks" title="切换到任务目录；只读查看本地 task 进度" aria-label="open task progress after local fastapi connection">查看任务进度</a>
          <a href="#desktop" title="切换到桌面壳预检；只读查看本地连接诊断" aria-label="open desktop preflight after local fastapi connection">查看本地预检</a>
        </div>
        <p className="risk-note">边用边看：{dailyCommandFastApiProgressWatchNext}；这只来自首页已回读的 `/api/tasks` 和 CandidateRadar cache，不创建第二个 task。</p>
        <p className="risk-note">本卡只判断本机前后端能不能继续投研；需要排查地址或 fallback 时展开技术明细。页面打开和输入代码仍保持只读，不创建 task。</p>
        <details className="developer-audit-details" aria-label="daily command local fastapi technical connection details">
          <summary>本地接线技术明细</summary>
          <MetricGrid
            items={[
              { label: "接线地址", value: dailyCommandFrontendBackendSelectedApiBase, tone: dailyCommandHealthOk ? "good" : "warn" },
              { label: "候选地址", value: API_BASE_CANDIDATE_DISPLAY_URLS.join(" / "), tone: "good" }
            ]}
          />
          <p className="risk-note">接线地址来自前端本机 FastAPI auto-link ledger；候选地址只展示本机 127.0.0.1/localhost fallback。该卡只读 FastAPI health、bootstrap status 和 desktop preflight cache；不会启动服务、不会创建 task、不会调用 Tushare/DeepSeek/GitHub，也不会暴露 token/key。</p>
          <div aria-label="daily command home aggregate readback">
            <h3>首页多接口回读</h3>
            <p className="risk-note">首页是多个本地只读接口合成的作战台，不依赖单个总 cache URL；看到某个猜测 URL 不存在，不代表软件没接上。</p>
            <DataLineageTable rows={dailyCommandHomeAggregateReadbackRows} />
          </div>
        </details>
      </PacketCard>
      <PacketCard title="使用者可用化进度" subtitle="打开即看 P0 到 P3 当前阶段；P4-P6 下沉到摘要和审计" status={homeQuantP1P2P3CheckpointReady ? "p1_p2_p3_ready" : dailyCommandP0LocalReadinessReady ? "ready_for_confirm" : "p0_check"}>
        <div className="state-clarity-rail" aria-label="daily command usable path front stage rail">
          {dailyCommandUsablePathPrimaryStageRailSteps.map((step) => (
            <div className="state-clarity-step" data-step-state={step.state} key={step.key}>
              <span>{step.label}</span>
              <small>{step.detail}</small>
            </div>
          ))}
        </div>
        <p className="ordinary-status-note" aria-label="daily command usable path front readable status" aria-live="polite">{homeQuantP1P2P3CheckpointLabel}</p>
        <div aria-label="daily command current research snapshot">
          <h3>最近确认投研快照</h3>
          <p className="ordinary-status-note" aria-label="daily command current research snapshot readable sentence" aria-live="polite">{dailyCommandCurrentResearchSnapshotReadableSentence}</p>
          <MetricGrid items={dailyCommandCurrentResearchSnapshotItems} />
          <p className="risk-note">这张首屏快照只读最近确认 task、Tushare-first ledger、P2 三面和 P3 可读结论；不会创建第二个 task、不补调 Tushare/DeepSeek、不展示 token/key，也不交易或修改 strategy action。</p>
        </div>
        <DataLineageTable rows={dailyCommandUsableShortestPathPrimaryRows} />
        <div className="actions" aria-label="daily command usable path front actions">
          <a href={dailyCommandPrimaryActionHref} title={dailyCommandPrimaryActionBoundary} aria-label="open usable path primary action">{dailyCommandPrimaryActionLabel}</a>
          <a href="#factor/factor-score" title="切换到股票量化推演支持/压制摘要；只读回放本地 P2/P3 结果" aria-label="open stock quant from usable path progress">股票量化推演</a>
          <a href="#next/next-session-chart" title="切换到次日图谱图表区域；只读回放本地图谱数据" aria-label="open next session from usable path progress">次日图谱</a>
        </div>
        <p className="risk-note">这张进度卡只读首页已回放的 health、CandidateRadar cache、task index 和本地结果；不会创建 task、不会调用 Tushare/DeepSeek/GitHub、不会读取 token/key、不会交易或修改 strategy action。</p>
      </PacketCard>
      <PacketCard title="P0 现在能不能用" subtitle="普通用户打开软件后的 10 秒判断" status={dailyCommandP0LocalReadinessReady ? "ready" : "check"}>
        <MetricGrid
          items={[
            { label: "结论", value: dailyCommandP0LocalReadinessReady ? "可以用：本地四段已接上" : "先恢复：本地四段还没全部 ready", tone: dailyCommandP0LocalReadinessReady ? "good" : "warn" },
            { label: "现在点哪里", value: dailyCommandPrimaryActionLabel, tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
            { label: "失败看哪里", value: "桌面壳预检里的 FastAPI / bootstrap / preflight / React 分段诊断", tone: dailyCommandNeedsStartupRecovery ? "warn" : "good" },
            { label: "进入 P1 条件", value: "health、bootstrap、desktop preflight、React 四段 ready 后再确认股票代码", tone: dailyCommandP0LocalReadinessReady ? "good" : "warn" },
            { label: "边界", value: "这张卡只读本地状态；不启动服务、不创建 task、不调用 provider/model", tone: "good" }
          ]}
        />
        <div className="actions" aria-label="daily command p0 now usable actions">
          <a href={dailyCommandPrimaryActionHref} aria-label="open p0 recommended next action">{dailyCommandPrimaryActionLabel}</a>
          <a href="#desktop" title="切换到桌面壳预检；只读查看本地四段诊断" aria-label="open p0 diagnostics from now usable card">查看四段诊断</a>
          <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入仍保持静默，确认按钮才创建 Tushare-first task" aria-label="open candidate radar confirm input from p0 usable card">下一票雷达确认输入区</a>
        </div>
        <p className="risk-note">P0 ready 只说明本机前后端已接上；不代表 Tushare 已调用、DeepSeek 可用、release ready 或 14 LTG 完成。</p>
      </PacketCard>
      <PacketCard title="首页确认股票代码" subtitle="P1 普通入口：输入静默，点击确认才创建 Tushare-first task" status={homeQuantVisibleTaskId ? "task_visible" : dailyCommandP0LocalReadinessReady ? "ready" : "p0_check"}>
        <div id="home-p1-symbol-confirm" aria-label="daily command home p1 symbol confirmation">
          <MetricGrid items={homeQuantConfirmItems} />
          <div aria-label="daily command home p1 confirm button chain proof">
            <h3>确认按钮链路证明</h3>
            <p className="risk-note">点击前先看这五步：输入静默、P0 gate、确认按钮创建 task、任务进度、本地三面回放；本表只解释链路，不创建 task。</p>
            <DataLineageTable rows={homeQuantConfirmButtonChainRows} />
          </div>
          <div className="actions" aria-label="daily command home p1 symbol confirm actions">
            <input
              value={homeQuantSymbol}
              onChange={(event) => {
                setHomeQuantSymbolTouched(true);
                setHomeQuantSymbol(event.target.value);
                setHomeQuantSubmitError("");
              }}
              placeholder="002008.SZ 或 002008"
              aria-label="daily command home quant projection symbol"
              title="首页输入只做本地格式校验；不会创建 task，也不会调用 Tushare/DeepSeek"
            />
            <button
              disabled={!dailyCommandConfirmedSymbol}
              onClick={() => {
                setHomeQuantSymbolTouched(true);
                setHomeQuantSymbol(dailyCommandConfirmedSymbol);
                setHomeQuantSubmitError("");
              }}
              title={homeQuantUseConfirmedSymbolTitle}
              aria-label={homeQuantUseConfirmedSymbolTitle}
            >{homeQuantUseConfirmedSymbolLabel}</button>
            <button
              disabled={!homeQuantCanSubmit}
              onClick={launchHomeQuantProjection}
              title={homeQuantSubmitDisabledReason}
              aria-label={homeQuantSubmitDisabledReason}
            >{homeQuantSubmitting ? "提交中..." : "确认并生成 3.0 量化推演"}</button>
            <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达详情页；同一条 P1 确认链路" aria-label="open candidate radar detail from home p1 confirm">下一票雷达详情</a>
          </div>
          <p className="risk-note" aria-label="daily command home p1 symbol autofill boundary">当前标的自动填入只来自 CandidateRadar cache；不会自动点击确认、不创建 task、不调用 Tushare/DeepSeek，手动修改后不再覆盖输入。</p>
          <p className="ordinary-status-note" aria-label="daily command home post confirm readback state" aria-live="polite">{homeQuantPostConfirmReadbackState}</p>
          {homeQuantSubmitError ? <p className="risk-note" aria-live="polite">首页确认任务创建失败：{homeQuantSubmitError}</p> : null}
          {homeQuantVisibleTaskId ? (
            <div aria-label="daily command home post confirm handoff">
              <h3>确认后下一步</h3>
              <p className="risk-note">任务编号出现或从本地 cache 恢复后，先看任务进度；成功后按股票量化推演和次日图谱回放。这里的链接只切换本地页面，不创建第二个 task。</p>
              <p className="ordinary-status-note" aria-label="daily command home post confirm readable result" aria-live="polite">{homeQuantPostConfirmReadableSentence}</p>
              <div aria-label="daily command home p1 p2 p3 checkpoint">
                <h3>P1/P2/P3 一眼 checkpoint</h3>
                <MetricGrid items={homeQuantP1P2P3CheckpointItems} />
                <p className="risk-note">这条 checkpoint 只合成现有 task id、Tushare ledger、P2 三面、P3 可读结论和 Factor handoff；不创建 task、不补调 provider/model、不展示 raw packet。</p>
              </div>
              <div aria-label="daily command home post confirm one glance">
                <MetricGrid items={homeQuantPostConfirmOneGlanceItems} />
              </div>
              <DataLineageTable rows={homeQuantPostConfirmHandoffRows} />
              <div className="actions" aria-label="daily command home post confirm handoff actions">
                <a href="#tasks" title="切换到任务目录；只读查看本地 task 进度" aria-label="open task progress after home symbol confirm">查看任务进度</a>
                <a href="#factor" title="切换到股票量化推演；只读回放确认后的本地结果" aria-label="open factor after home symbol confirm">股票量化推演</a>
                <a href="#next" title="切换到次日图谱；只读回放确认后的本地图谱" aria-label="open next session after home symbol confirm">次日图谱</a>
                <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；换标的仍需确认按钮" aria-label="open candidate radar confirm input after home symbol confirm">下一票雷达确认输入区</a>
              </div>
            </div>
          ) : null}
          {homeQuantVisibleTaskCanPoll ? <TaskStatusPanel taskId={homeQuantVisibleTaskId} onSuccess={refreshHomeResearchReadback} /> : null}
          {homeQuantVisibleTaskId && !homeQuantVisibleTaskCanPoll ? (
            <p className="risk-note" aria-label="daily command home recovered task cache-only notice">最近确认 task 来自 CandidateRadar cache 只读回放；当前任务目录没有可轮询记录，首页不会启动 TaskStatusPanel，也不会创建第二个 task。</p>
          ) : null}
          {homeQuantReceipt ? (
            <details className="developer-audit-details" aria-label="daily command home p1 receipt audit details">
              <summary>任务回执 / 审计详情</summary>
              <p className="risk-note">完整 POST task receipt 默认下沉；普通路径先看上方任务进度、量化推演和次日图谱。</p>
              <TaskLaunchReceipt receipt={homeQuantReceipt} />
            </details>
          ) : null}
          <p className="risk-note">首页确认按钮复用 POST /api/candidate-radar/quant-projection：P0 gate 通过后才启用；成功后只从 CandidateRadar cache / call_ledger / packet 回放 P2/P3。P1 手动确认链路已接入本地 runtime；浏览器网络证据和自动提交仍单独补，不当作生产验收。页面打开、输入、React render 和 GET cache 不外联，不调用 DeepSeek，不交易、不改 strategy action。</p>
        </div>
      </PacketCard>
      <PacketCard title="P1 Tushare-first 链路速读" subtitle="确认按钮、Tushare ledger、DeepSeek skipped 和回放边界" status={dailyCommandTushareFirstLedgerReady ? "ledger_ready" : "waiting_confirm"}>
        <MetricGrid
          items={[
            { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "确认链", value: dailyCommandTushareFirstStatus, tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn" },
            { label: "Tushare ledger", value: dailyCommandTushareFirstLedgerLabel, tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn" },
            { label: "DeepSeek", value: dailyCommandTushareFirstDeepSeekLabel, tone: "good" },
            { label: "下一步", value: dailyCommandTushareFirstLedgerReady ? "继续看 P2 三面和 P3 结论" : "先在首页或下一票雷达点击确认按钮", tone: dailyCommandTushareFirstLedgerReady ? "good" : "warn" },
            { label: "边界", value: dailyCommandTushareFirstBoundary, tone: "good" }
          ]}
        />
        <div aria-label="daily command p1 tushare first front row">
          <h3>P1 链路四步</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_tushare_first_chain_rows：普通用户只看输入是否静默、确认按钮是否创建 task、Tushare ledger 是否回放、DeepSeek 是否 skipped；工程明细继续下沉。</p>
          <DataLineageTable rows={dailyCommandTushareFirstRows} />
        </div>
        <div aria-label="daily command p1 confirm task readback proof">
          <h3>P1 确认任务回放</h3>
          <MetricGrid
            items={[
              { label: "确认回执", value: candidateQuantConfirmedTaskReceiptRows.length ? `${candidateQuantConfirmedTaskReceiptRows.length} 行已回放` : "等待确认回执", tone: candidateQuantConfirmedTaskReceiptRows.length ? "good" : "warn" },
              { label: "任务状态", value: candidateQuantTaskReadbackRows.length ? `${candidateQuantTaskReadbackRows.length} 行已回放` : "等待 task 状态", tone: candidateQuantTaskReadbackRows.length ? "good" : "warn" },
              { label: "来源任务", value: dailyCommandConfirmedSourceTaskLabel, tone: dailyCommandConfirmedSourceTaskLabel.includes("等待") ? "warn" : "good" },
              { label: "回放边界", value: "只读 search_quant_projection_confirmed_task_receipt_rows / task_readback_rows；不创建第二个 task", tone: "good" }
            ]}
          />
          <p className="risk-note">优先读取 CandidateRadar 的 search_quant_projection_confirmed_task_receipt_rows 和 search_quant_projection_task_readback_rows，让点击确认后的 task id、安全步骤和 TaskStatusPanel 回放直接可见。</p>
          <DataLineageTable rows={dailyCommandP1ConfirmTaskReadbackRows} />
        </div>
        <div className="actions" aria-label="daily command p1 tushare first front actions">
          <a href={dailyCommandCandidateConfirmHref} title="回到下一票雷达确认输入区；输入静默，确认按钮才创建 Tushare-first task" aria-label="open candidate confirm from p1 tushare first front row">确认或换一只票</a>
          <a href="#factor" title="切换到股票量化推演；只读回放 Tushare-first 后的本地结果" aria-label="open factor after p1 tushare first front row">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读回放 Tushare-first 后的本地图谱" aria-label="open next session after p1 tushare first front row">次日图谱</a>
        </div>
        <p className="risk-note">P1 速读只回放已写入的 POST task / call_ledger / packet 证据；不会从首页回放卡创建第二个 task、补调 Tushare/DeepSeek、读取 token/key、执行交易或修改 strategy action。</p>
      </PacketCard>
      <PacketCard title="当前可用投研链路" subtitle="当前标的、P1 确认、P2 三面、P3 结论和下一步" status={dailyCommandResearchWorkflowStatus}>
        <p className="ordinary-status-note" aria-label="daily command current research workflow readable result" aria-live="polite">{dailyCommandResearchWorkflowReadableSentence}</p>
        <MetricGrid
          items={[
            { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "P1 任务", value: dailyCommandLatestTaskId ? `${dailyCommandLatestTaskStatus}: ${dailyCommandLatestTaskId}` : "等待确认按钮", tone: dailyCommandLatestTaskId ? "good" : "warn" },
            { label: "P2 三面", value: dailyCommandSmallDataWritebackState, tone: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn" },
            { label: "P3 结论", value: dailyCommandExplainableResultLabel, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
            { label: "下一步", value: dailyCommandResearchWorkflowNext },
            { label: "DeepSeek", value: dailyCommandP3OneGlanceModelState, tone: dailyCommandP3OneGlanceUsesModelOutput ? "warn" : "good" },
            { label: "边界", value: "当前链路卡只读 CandidateRadar cache / ledger / packet；只有首页确认卡创建 P1 task；不交易", tone: "good" }
          ]}
        />
        <DataLineageTable rows={dailyCommandResearchWorkflowRows} />
        <div className="actions" aria-label="daily command current research workflow actions">
          <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入代码后仍需确认按钮" aria-label="open candidate radar confirm from current research workflow">确认或换一只票</a>
          <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor replay from current research workflow">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读回放本地图谱" aria-label="open next session replay from current research workflow">次日图谱</a>
        </div>
        <p className="risk-note">这张卡把 P1/P2/P3 放到首页前排：页面打开和搜索输入不外联；只有首页或下一票雷达确认按钮可以创建 Tushare-first POST task，DeepSeek governed executor 单独补。</p>
      </PacketCard>
      <PacketCard title="P2 小数据三面速读" subtitle="确认后直接看 cache、call_ledger、packet 是否能本地回放" status={candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "ready" : "waiting_confirm"}>
        <MetricGrid
          items={[
            { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "三面状态", value: dailyCommandSmallDataWritebackState, tone: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn" },
            { label: "三面完整度", value: dailyCommandP2SurfaceCompletionLabel, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
            { label: "P2 checkpoint", value: dailyCommandP2CheckpointLabel, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
            { label: "call_ledger", value: dailyCommandP2CallLedgerState, tone: dailyCommandP2ThreeSurfaceReady ? "good" : "warn" },
            { label: "写入面", value: "cache / call_ledger / packet", tone: "good" },
            { label: "来源任务", value: dailyCommandConfirmedSourceTaskLabel, tone: dailyCommandConfirmedSourceTaskLabel.includes("等待") ? "warn" : "good" },
            { label: "下一步", value: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "打开股票量化推演和次日图谱回放" : "确认任务完成后刷新本地 cache / ledger / packet", tone: candidateQuantSmallDataWriteback.small_data_writeback_ready === true ? "good" : "warn" },
            { label: "边界", value: "这张卡只读已有 P2 写回摘要；不创建第二个 task、不补调 Tushare/DeepSeek、不展示 raw log", tone: "good" }
          ]}
        />
        <div aria-label="daily command p2 three surface proof">
          <h3>P2 三面写回证明</h3>
          <MetricGrid items={dailyCommandP2ThreeSurfaceProofItems} />
          <p className="risk-note">这条证明只合成 CandidateRadar 本地 cache 的 cache_ready、ledger_ready、packet_ready 和三面完整度；它不创建 task、不调用 Tushare/DeepSeek、不展示 token/key/raw log，也不是买卖指令。</p>
        </div>
        <div aria-label="daily command ordinary p2 writeback front row">
          <h3>P2 三面回放</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_writeback_surface_summary_rows，让普通用户确认 cache、call_ledger、packet 三面有没有本地回放；完整工程审计仍下沉在折叠明细。</p>
          <DataLineageTable rows={dailyCommandSmallDataWritebackRows} />
        </div>
        <div className="actions" aria-label="daily command p2 writeback front actions">
          <a href="#factor" title="切换到股票量化推演；只读回放本地 P2/P3 结果" aria-label="open factor after p2 writeback front row">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读回放本地 P2/P3 图谱" aria-label="open next session after p2 writeback front row">次日图谱</a>
          <a href={dailyCommandCandidateConfirmHref} title="回到下一票雷达确认输入区；输入仍保持静默" aria-label="open candidate confirm after p2 writeback front row">确认或换一只票</a>
        </div>
        <p className="risk-note">P2 三面速读只从 CandidateRadar cache / call_ledger / packet 回放；不会从首页回放卡创建 task、读取 token/key、执行真实交易或修改 strategy action。</p>
      </PacketCard>
      <PacketCard title="P3 可解释结果一眼读懂" subtitle="结论、来源、缺口、下一步和安全边界；只读 CandidateRadar checkpoint" status={dailyCommandP3OneGlanceStatus}>
        <MetricGrid
          items={[
            { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "可读结论", value: dailyCommandExplainableResultLabel, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
            { label: "数据来源", value: dailyCommandP3OneGlanceSource, tone: dailyCommandP3OneGlanceProviderVerified ? "good" : "warn" },
            { label: "结果证据", value: dailyCommandP3OneGlanceEvidence, tone: dailyCommandP3OneGlanceReadable ? "good" : "warn" },
            { label: "来源任务", value: dailyCommandP3OneGlanceSourceTask, tone: dailyCommandP3OneGlanceSourceTask === "等待确认任务" ? "warn" : "good" },
            { label: "结果入口", value: dailyCommandP3OneGlanceResultEntrances, tone: candidateQuantHandoffRows.length ? "good" : "warn" },
            { label: "Factor handoff", value: dailyCommandFactorCandidateHandoffLabel, tone: dailyCommandFactorCandidateHandoffReady ? "good" : "warn" },
            { label: "Factor 行数", value: `${String(factorCandidateHandoffRows.length)} 行只读`, tone: dailyCommandFactorCandidateHandoffReady ? "good" : "warn" },
            { label: "待补缺口", value: dailyCommandP3OneGlanceMissingEvidence, tone: dailyCommandP3MissingEvidenceItems.length ? "warn" : "good" },
            { label: "下一步", value: dailyCommandExplainableResultNext },
            { label: "模型状态", value: dailyCommandP3OneGlanceModelState, tone: dailyCommandP3OneGlanceUsesModelOutput ? "warn" : "good" },
            { label: "安全字段", value: dailyCommandP3OneGlanceSafeFields, tone: "good" },
            { label: "边界", value: dailyCommandExplainableResultBoundary, tone: "good" }
          ]}
        />
        <div aria-label="daily command p3 explainable result proof">
          <h3>P3 结果证明</h3>
          <MetricGrid items={dailyCommandP3ExplainableProofItems} />
          <p className="risk-note">这条证明只合成 CandidateRadar 本地 cache 的 P3 checkpoint、可读结论、Tushare-first 来源、缺口和模型状态；不创建 task、不调用 DeepSeek、不展示 raw packet/token/key，也不是买卖指令。</p>
        </div>
        <div aria-label="daily command p3 one glance decision brief">
          <h3>P3 一分钟决策速读</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_result_decision_brief_rows：先看结论、再看来源、最后看下一步和边界；首页只读本地证据，不创建 task。</p>
          <DataLineageTable rows={dailyCommandP3OneGlanceDecisionRows} />
        </div>
        <div aria-label="daily command p3 one glance quick rows">
          <h3>结果速读全部项</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_result_quick_read_rows 全部项：只看结论、下一步、证据、缺口和边界；不展开 raw packet、不创建 task、不调用 provider/model。</p>
          <DataLineageTable rows={dailyCommandP3OneGlanceQuickRows} />
        </div>
        <div aria-label="daily command factor candidate handoff readback">
          <h3>股票量化推演 handoff</h3>
          <p className="risk-note">优先读取 /api/factor-quant/cache 的 ordinary_quant_candidate_handoff_rows：只读确认 CandidateRadar 确认任务是否已经接到股票量化推演；不创建 task、不补调 provider/model。</p>
          <DataLineageTable rows={dailyCommandFactorCandidateHandoffReadbackRows} />
        </div>
        <div className="actions" aria-label="daily command p3 one glance actions">
          <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；只读查看 P3 结果速读" aria-label="open candidate radar confirm input p3 one glance">下一票雷达确认输入区</a>
          <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor p3 one glance">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读回放本地图谱" aria-label="open next session p3 one glance">次日图谱</a>
        </div>
        <p className="risk-note">这张卡只读 `search_quant_projection_result_checkpoint` 和 CandidateRadar 本地 cache；不会创建 task、不会调用 DeepSeek、不会交易或修改 strategy action。</p>
      </PacketCard>
      <PacketCard title="最近本地任务" subtitle="打开软件后直接看进度；只读回放 task/cache/ledger/packet" status={dailyCommandLatestTaskStatus}>
        <MetricGrid
          items={[
            { label: "任务数", value: taskIndex?.task_count ?? tasks.length, tone: (taskIndex?.task_count ?? tasks.length) ? "good" : "warn" },
            { label: "当前标的", value: dailyCommandConfirmedSymbolLabel, tone: dailyCommandConfirmedSymbol ? "good" : "warn" },
            { label: "最近任务", value: dailyCommandLatestTaskId || "暂无", tone: dailyCommandLatestTaskId ? "good" : "warn" },
            { label: "状态", value: dailyCommandLatestTaskStatus, tone: dailyCommandLatestTaskStatus === "success" ? "good" : dailyCommandLatestTaskStatus === "failed" ? "bad" : "warn" },
            { label: "来源任务", value: dailyCommandConfirmedSourceTaskLabel, tone: dailyCommandConfirmedSourceTaskLabel.includes("等待") ? "warn" : "good" },
            { label: "来源", value: dailyCommandLatestTaskIsReplay ? "cache 只读回放" : dailyCommandLatestTaskSource, tone: "good" },
            { label: "下一步", value: dailyCommandLatestTaskNext },
            { label: "边界", value: "首页只读任务状态；确认按钮之前不创建 task", tone: "good" }
          ]}
        />
        <DataLineageTable rows={dailyCommandLatestTaskRows} />
        <div className="actions" aria-label="daily command latest local task actions">
          <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入代码后仍需确认按钮" aria-label="open candidate radar confirm input from latest local task">下一票雷达确认代码</a>
          <a href="#factor" title="切换到股票量化推演；只读回放本地结果" aria-label="open factor projection from latest local task">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读回放本地图谱" aria-label="open next session map from latest local task">次日图谱</a>
          <a href="#tasks" title="切换到任务目录；只读查看完整任务列表" aria-label="open task monitor from latest local task">任务目录</a>
        </div>
        {dailyCommandLatestTaskId && !dailyCommandLatestTaskIsReplay ? <TaskStatusPanel taskId={dailyCommandLatestTaskId} /> : null}
        {dailyCommandLatestTaskId && dailyCommandLatestTaskIsReplay ? (
          <p className="risk-note">最近任务来自 CandidateRadar cache 只读回放，不启动 TaskStatusPanel 轮询；看上方 cache / ledger / packet 状态即可。</p>
        ) : null}
        <p className="risk-note">本卡只读 `/api/tasks` 和具体 task 状态；不会补调 Tushare、DeepSeek 或 GitHub，也不会真实交易或修改 strategy action。</p>
      </PacketCard>
      <PacketCard title="今日作战台摘要" subtitle="下一步、来源、缺口、边界和最近可用缓存" status={dailyCommandStatusLabel}>
        <MetricGrid items={dailyCommandSummaryPrimaryItems} />
        <details className="developer-audit-details" aria-label="daily command summary technical metrics">
          <summary>启动诊断 / 证据口径 / P5 明细</summary>
          <p className="risk-note">普通视图只保留下一步、联通、P2/P3 和缺口；启动诊断、fallback、证据口径和 P5 状态默认下沉，展开后仍只读本地 cache。</p>
          <MetricGrid items={dailyCommandSummaryTechnicalItems} />
        </details>
        <div aria-label="daily command usable shortest path">
          <h3>使用者可用化最短路径</h3>
          <p className="risk-note">当前执行目标是 Command Center 3.0 使用者可用化最短路径，不是 14 LTG strict closeout 完成声明；DeepSeek governed executor 单独补，不阻塞 Tushare-first 和基础图谱。</p>
          <div className="state-clarity-rail" aria-label="daily command usable path stage rail">
            {dailyCommandUsablePathPrimaryStageRailSteps.map((step) => (
              <div className="state-clarity-step" data-step-state={step.state} key={step.key}>
                <span>{step.label}</span>
                <small>{step.detail}</small>
              </div>
            ))}
          </div>
          <DataLineageTable rows={dailyCommandUsableShortestPathPrimaryRows} />
          <details className="developer-audit-details" aria-label="daily command usable path audit stages">
            <summary>P4-P6 补证 / 审计路径</summary>
            <p className="risk-note">P4-P6 继续保留为路线图和审计入口，但默认下沉；普通使用先看 P0-P3 的联通、确认、写回和结果回放。</p>
            <div className="state-clarity-rail" aria-label="daily command usable path audit stage rail">
              {dailyCommandUsablePathAuditStageRailSteps.map((step) => (
                <div className="state-clarity-step" data-step-state={step.state} key={step.key}>
                  <span>{step.label}</span>
                  <small>{step.detail}</small>
                </div>
              ))}
            </div>
            <DataLineageTable rows={dailyCommandUsableShortestPathAuditRows} />
          </details>
        </div>
        <div className="actions" aria-label="daily command primary next action">
          <a href={dailyCommandPrimaryActionHref} aria-label="open daily command primary next action">{dailyCommandPrimaryActionLabel}</a>
        </div>
        <div className="actions" aria-label="daily command next user actions">
          <a href={dailyCommandCandidateConfirmHref} title="切换到下一票雷达确认输入区；输入代码后仍需确认按钮" aria-label="open candidate radar confirm input from daily command">下一票雷达确认代码</a>
          <a href="#factor" title="切换到股票量化推演模块；只回放缓存结果，不创建 task" aria-label="open stock quant projection from daily command">查看股票量化推演</a>
          <a href="#next" title="切换到次日图谱模块；只回放本地次日图谱缓存，不创建 task" aria-label="open next session map from daily command">查看次日图谱</a>
          <a href="#dataHealth" title="切换到数据健康模块；只读 cache，不刷新外部数据源" aria-label="open data health from daily command">查看数据健康</a>
          <a href="#desktop" title="切换到桌面壳预检模块；只读恢复指引，不启动服务" aria-label="open one click startup preflight from daily command">查看一键启动预检</a>
        </div>
        <p className="risk-note">今日先按“P0 本地联通 → 首页确认股票代码 → 股票量化推演 / 次日图谱回放”复核；需要详情再进下一票雷达，缺数据就看 pending 和缺少证据，不把空结果当成无风险。</p>
        <p className="risk-note">{dailyCommandExternalTriggerBoundary}</p>
        <p className="risk-note">{dailyCommandResultLocation}</p>
        <p className="risk-note">如果本地联通异常，先去 <a href="#desktop">桌面壳预检</a> 查看本地快捷入口；这个跳转只切换页面，不启动 FastAPI/Vite/浏览器。</p>
        <p className="risk-note">这些入口链接只切换本地页面（本地模块路由）；不会创建 task、调用 Tushare/DeepSeek/GitHub、写 cache/config 或改变交易策略。</p>
        <p className="risk-note">live_light 补证入口下沉在开发详情；普通路径只看本地缓存、雷达和量化入口。</p>
        <details className="developer-audit-details" aria-label="daily command ordinary readback details">
          <summary>本地回放明细</summary>
          <p className="risk-note">确认链、P2 写回、P3 检查点和恢复表默认收起；普通用户先用上方主按钮在首页确认股票代码，再看股票量化推演和次日图谱。</p>
        <details className="developer-audit-details" aria-label="daily command engineering audit and strict closeout details">
          <summary>工程审计 / P6 strict closeout 明细</summary>
          <p className="risk-note">普通路径已经在上方 P1 确认、P2 三面和 P3 可解释结果；普通用户先看上方 P1 确认、P2 三面和 P3 可解释结果。这里仅供排障、验收和 14 LTG 回归，不把 P6 当今日可用化完成。</p>
          <div aria-label="daily command p6 strict closeout reentry">
            <h3>P6 strict closeout 回归入口</h3>
            <p className="risk-note">P0-P5 是使用者可用化 checkpoint；14 LTG strict closeout 仍需 current-head direct evidence、CI、浏览器、provider、worker、storage 和 package gate 逐项补证；P6 只是 strict closeout 回归门，不是 14 LTG 完成声明；P4 下沉的是工程审计明细，不压过 P0-P3 普通路径。</p>
            <DataLineageTable rows={dailyCommandP6StrictCloseoutReentryRows} />
            <div className="actions" aria-label="daily command p6 reentry links">
              <a href="#migration" title="切换到迁移状态页；只读查看 14 LTG direct evidence 缺口" aria-label="open migration status for strict closeout reentry">查看 14 LTG 迁移状态</a>
              <a href="#tasks" title="切换到任务目录；只读回放 task/cache/ledger/packet 证据" aria-label="open task catalog for evidence replay">查看任务和证据回放</a>
            </div>
          </div>
        </details>
        <div aria-label="daily command local connection readback">
          <h3>本地联通四段回读</h3>
          <p className="risk-note">先看 FastAPI、bootstrap runtime-mode packet、desktop preflight cache、React/Vite 前端四段是否变绿；这张表只读本地 GET 结果，不启动服务。</p>
          <DataLineageTable rows={dailyCommandStartupReadbackRows} />
        </div>
        <div aria-label="daily command p0 launcher check-only readback">
          <h3>一键启动只读自检</h3>
          <p className="risk-note">优先读取 desktop preflight 的 p0_launcher_check_only_rows：check-only 只打印配置，不启动 FastAPI/Vite、不探测 URL、不打开浏览器、不创建 task。</p>
          <DataLineageTable rows={p0LauncherCheckOnlyRows} />
        </div>
        <div aria-label="daily command p0 frontend backend auto link readback">
          <h3>P0 前后端自动联通回读</h3>
          <p className="risk-note">前端 API client 会在本地 FastAPI 候选地址内自动联通并回读 health；失败时只显示离线恢复，不启动服务、不创建 task。</p>
          <DataLineageTable rows={dailyCommandFrontendBackendAutoLinkRows} />
        </div>
        <div aria-label="daily command p0 p1 entry gate">
          <h3>P0 进入 P1 闸门</h3>
          <p className="risk-note">普通用户先看这张清单：health、bootstrap status、desktop preflight 和当前 React 页面四段通过后，才进入首页确认卡；输入仍保持静默，只有确认按钮创建 Tushare-first POST task。</p>
          <DataLineageTable rows={dailyCommandP0EntryGateRows} />
        </div>
        <div aria-label="daily command p0 current next action">
          <h3>P0 当前下一步</h3>
          <p className="risk-note">优先读取 desktop preflight 的 p0_current_next_action_rows：未 ready 回预检恢复，ready 后先到首页确认卡；确认按钮之前不创建 Tushare-first task。</p>
          <DataLineageTable rows={p0CurrentNextActionRows} />
        </div>
        <div aria-label="daily command one screen search actions">
          <h3>今日搜票一屏行动</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_one_screen_action_rows：确认、任务、写回、结果合成首页速读；首页只读回放，不创建 task、不调用模型。</p>
          <DataLineageTable rows={dailyCommandOneScreenActionRows} />
        </div>
        <div aria-label="daily command confirm outcome readback">
          <h3>确认结果链速读</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_confirm_outcome_rows：确认任务是否接收、P2 三面是否回放、P3 结果入口是否可读；首页只读回放，不创建第二个 task。</p>
          <DataLineageTable rows={dailyCommandConfirmOutcomeRows} />
        </div>
        <div aria-label="daily command p2 p3 replay checklist">
          <h3>确认后回放清单</h3>
          <p className="risk-note">确认按钮返回 task 后，按确认回执、任务状态、P2 写回三面、P3 结果顺序回放；本卡只读 CandidateRadar cache / ledger / packet，不创建第二个 task、不补调 Tushare/DeepSeek。</p>
          <DataLineageTable rows={dailyCommandP2P3ReplayChecklistRows} />
        </div>
        <div aria-label="daily command p0 quick action handoff">
          <h3>P0 到 P1 快速行动</h3>
          <p className="risk-note">优先读取 desktop preflight 的 p0_ordinary_quick_action_rows：联通通过后先在首页输入代码并确认；需要详情再进下一票雷达，同样只有确认按钮触发 Tushare-first 任务。</p>
          <DataLineageTable rows={p0OrdinaryQuickActionRows} />
        </div>
        <div aria-label="daily command p2 small data writeback quick read">
          <h3>P2 小数据写入速读</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_writeback_surface_summary_rows：普通入口只看 cache、call_ledger、packet 三个写入面是否可回放；不会从 P2 回放卡创建 task。</p>
          <DataLineageTable rows={dailyCommandSmallDataWritebackRows} />
        </div>
        <div aria-label="daily command p3 explainable result quick read">
          <h3>P3 可解释结果速读</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_result_quick_read_rows：普通入口只看可读结论、来源组成、回放来源和待补证据；不会从 P3 回放卡创建 task、调用 DeepSeek 或展开 raw packet。</p>
          <DataLineageTable rows={dailyCommandExplainableResultRows} />
        </div>
        <div aria-label="daily command p3 result checkpoint">
          <h3>P3 结果检查点</h3>
          <p className="risk-note">优先读取 CandidateRadar 的 ordinary_result_checkpoint_rows：把可读结论、来源状态、待补缺口和安全字段合成首页检查点；只读本地 cache / ledger / packet，不创建 task、不调用模型。</p>
          <DataLineageTable rows={dailyCommandP3CheckpointRows} />
        </div>
        <div aria-label="daily command p3 replay handoff">
          <h3>P3 结果回放入口</h3>
          <p className="risk-note">普通用户按下一票雷达、股票量化推演、次日图谱三步回放；这些入口只切换本地模块，不创建任务、不刷新 provider/model。</p>
          <DataLineageTable rows={dailyCommandP3ReplayActionRows} />
        </div>
        <div aria-label="daily command factor cache fallback readback">
          <h3>量化缓存降级回放</h3>
          <p className="risk-note">如果上次持久化量化 packet 是失败态，首页只读展示安全摘要，并继续使用本地 cache-only 回放；不展开 raw failed packet、provider error、token/key 或 call_ledger。</p>
          <DataLineageTable rows={dailyCommandFactorCacheFallbackRows} />
        </div>
        <div aria-label="daily command p5 deepseek governance quick read">
          <h3>P5 DeepSeek 单独治理</h3>
          <p className="risk-note">优先读取 /api/model-strategy/cache 的 governed_executor；CandidateRadar governance rows 只作 fallback。DeepSeek 只作为 governed executor 单独补证；pending/skipped 不阻塞 Tushare-first、小数据写入或基础图谱。</p>
          <div aria-label="daily command p5 nonblocking one minute read">
            <h3>P5 不阻塞速读</h3>
            <p className="risk-note">优先读取 modelStrategy.governed_executor 的 ordinary_status_label、real_call_gate_rows 和 nonblocking boundary；CandidateRadar readiness rows 只作 fallback。本区只读治理状态，不调用模型。</p>
            <DataLineageTable rows={dailyCommandP5NonblockingRows} />
          </div>
          <DataLineageTable rows={dailyCommandDeepSeekGovernanceRows} />
        </div>
        <div aria-label="daily command p0 startup recovery steps">
          <h3>一键启动恢复步骤</h3>
          <p className="risk-note">优先读取 desktop preflight 的 p0_recovery_steps：页面没打开或联通异常时，先按三步恢复；这张表只读展示，不补跑启动器。</p>
          <DataLineageTable rows={dailyCommandP0RecoveryRows} />
        </div>
        <p className="risk-note">本地联通状态只读来自 FastAPI health 和 desktop preflight cache；不会启动服务、不会写配置、不会调用 provider/model。</p>
        <p className="risk-note">启动诊断来自 desktop preflight cache：FastAPI /health、bootstrap status、desktop preflight cache 和 React/Vite 前端 HTML 分段检查；首页只展示，不执行。</p>
        <p className="risk-note">恢复回读只看本地 GET health/bootstrap/preflight 结果；如果没有变绿，继续回一键启动预检，不进入投研入口。</p>
        <p className="risk-note">主下一步会在联通异常时优先打开桌面壳预检；这个链接只读本地 health/preflight cache，不启动服务。</p>
        </details>
        <p className="risk-note">工程审计明细默认收起；完整 call ledger、release gate、runtime mode 和配置状态在 <a href="#audit">调用审计</a> / <a href="#settings">配置健康</a>。</p>
      </PacketCard>
      <details className="developer-audit-details">
        <summary>开发 / 审计详情</summary>
        <p>详细验收记录、开发表格和排障明细默认收起；普通用户先看上方今日作战台摘要、P1 确认、P2 三面和 P3 可解释结果。</p>
        <div aria-label="daily command engineering audit demotion rules">
          <h3>审计入口下沉规则</h3>
          <p className="risk-note">普通用户先看摘要和三入口；只有排障、验收或补证时展开开发详情。</p>
          <DataLineageTable rows={dailyCommandAuditDemotionRows} />
        </div>
        <PacketCard title="开发状态速览" subtitle="工程指标默认收进开发详情，不压过三入口" status="audit">
          <MetricGrid
            items={[
              { label: "FastAPI", value: String(health.status ?? "unknown"), tone: dailyCommandHealthOk ? "good" : "warn" },
              { label: "runtime mode", value: String(bootstrapStatus.mode ?? "cache_only"), tone: bootstrapStatus.mode === "live_light" ? "warn" : "good" },
              { label: "外部启动调用", value: health.external_calls_on_startup === true ? "存在" : "无", tone: health.external_calls_on_startup === true ? "bad" : "good" },
              { label: "manual bootstrap", value: liveBootstrapManualStatus, tone: liveBootstrapManualStatus.includes("failed") ? "bad" : liveBootstrapManualStatus.includes("disabled") || liveBootstrapManualStatus.includes("skipped") ? "good" : "warn" },
              { label: "provider linkage", value: bootstrapProviderLinkageRows.length },
              { label: "activation rows", value: liveLightActivationRows.length },
              { label: "acceptance phases", value: liveLightAcceptanceRows.length },
              { label: "health envelope ledger", value: healthEnvelopeLedger.length },
              { label: "health warnings", value: healthWarnings.length },
              { label: "本地快照", value: snapshotAvailable, tone: snapshotAvailable ? "good" : "warn" },
              { label: "cache keys", value: packetKeys?.length ?? 0 },
              { label: "packet envelope ledger", value: (packetEnvelopeLedger.length ? packetEnvelopeLedger : packetPayloadLedger).length },
              { label: "market envelope ledger", value: (marketEnvelopeLedger.length ? marketEnvelopeLedger : marketPayloadLedger).length },
              { label: "discipline envelope ledger", value: (disciplineEnvelopeLedger.length ? disciplineEnvelopeLedger : disciplinePayloadLedger).length },
              { label: "factor envelope ledger", value: (factorEnvelopeLedger.length ? factorEnvelopeLedger : factorPayloadLedger).length },
              { label: "next envelope ledger", value: (nextEnvelopeLedger.length ? nextEnvelopeLedger : nextPayloadLedger).length },
              { label: "serenity envelope ledger", value: (serenityEnvelopeLedger.length ? serenityEnvelopeLedger : serenityPayloadLedger).length },
              { label: "chokepoint envelope ledger", value: (chokepointEnvelopeLedger.length ? chokepointEnvelopeLedger : chokepointPayloadLedger).length },
              { label: "任务记录", value: taskIndex?.task_count ?? tasks.length },
              { label: "任务外联", value: taskIndex?.external_calls_triggered === true ? "存在" : "无", tone: taskIndex?.external_calls_triggered === true ? "bad" : "good" },
              { label: "任务目录", value: taskCatalogItems?.length ?? 0 },
              { label: "stub tasks", value: taskImplementationStatus?.stub_task_count as number | undefined },
              { label: "local pipelines", value: taskImplementationStatus?.local_pipeline_task_count as number | undefined },
              { label: "guarded local", value: taskImplementationStatus?.guarded_local_task_count as number | undefined },
              { label: "implemented local", value: taskImplementationStatus?.implemented_local_task_count as number | undefined },
              { label: "POST 路由", value: taskRouteCoverage?.known_post_route_count as number | undefined },
              { label: "未覆盖 POST", value: taskUncoveredPostRoutes?.length ?? 0, tone: taskUncoveredPostRoutes?.length ? "bad" : "good" },
              { label: "task catalog ledger", value: (taskCatalogEnvelopeLedger.length ? taskCatalogEnvelopeLedger : taskCatalogPayloadLedger).length },
              { label: "task index ledger", value: (taskIndexEnvelopeLedger.length ? taskIndexEnvelopeLedger : taskIndexPayloadLedger).length },
              { label: "SQLite packets", value: sqlitePackets?.length ?? 0 },
              { label: "SQLite tasks", value: sqliteTasks?.length ?? 0 },
              { label: "factor parquet", value: String(storageStatus?.factor_values ?? "missing") },
              { label: "daily parquet", value: String(storageStatus?.daily ?? "missing") },
              { label: "daily_basic parquet", value: String(storageStatus?.daily_basic ?? "missing") },
              { label: "moneyflow parquet", value: String(storageStatus?.moneyflow ?? "missing") },
              { label: "trade_cal parquet", value: String(storageStatus?.trade_cal ?? "missing") },
              { label: "backtest parquet", value: String(storageStatus?.backtest_results ?? "missing") },
              { label: "storage catalog", value: storageCatalogRows?.length ?? 0 },
              { label: "storage catalog ledger", value: storageCatalogLedger.length },
              { label: "迁移基线", value: String(migration.status ?? "loading") },
              { label: "DeepSeek explain", value: String(deepseekModelByPurpose.get("explain")?.model ?? "--") },
              { label: "DeepSeek fast", value: String(deepseekModelByPurpose.get("fast")?.model ?? "--") }
            ]}
          />
        </PacketCard>
      <div className="grid">
        <PacketCard title="live_light 手动补证" subtitle="手动确认后才会创建本地 POST task；页面打开不自动启动" status={liveBootstrapManualStatus}>
          <button onClick={launchLiveBootstrap} disabled={liveBootstrapManualStatus === "creating"}>
            确认 live_light 本地补证 task
          </button>
          <p>runtime mode: {String(bootstrapStatus.mode ?? "cache_only")}</p>
          <p>manual status: {liveBootstrapManualStatus}</p>
          <p>sources enabled: {String(liveLight.sources_enabled ?? false)}</p>
          <p>Tushare / DeepSeek configured source switches: {String(liveLight.tushare_on_open ?? false)} / {String(liveLight.deepseek_on_open ?? false)}</p>
          <p>live_light 后台审计：轻量实时后台任务只允许手动确认后的 POST task。</p>
          <p>DeepSeek model call: {liveBootstrapModelCalled ? "模型调用 ledger 已记录；ledger 显示已执行" : "待授权解释；未执行；需要明确允许白名单摘要外发后才会调用"}</p>
          <p>task skeleton / provider execution: {String(liveLight.bootstrap_task_implemented ?? false)} / {String(liveLight.provider_execution_implemented ?? false)}</p>
          <p>provider linkage rows: {String(bootstrapProviderLinkageRows.length)}</p>
          <p>live_light activation receipt: {String(liveLightActivationReceipt.status ?? "--")}</p>
          <p>provider/model acceptance runbook: {String(liveLightAcceptanceRunbook.status ?? "--")}</p>
          <p>provider/model ready: {String(liveLightActivationReceipt.ready_for_provider_execution ?? false)} / {String(liveLightActivationReceipt.ready_for_model_execution ?? false)}</p>
          <p>task_id: {String(liveBootstrapTaskId || liveBootstrapReceipt?.data?.task_id || "--")}</p>
          <p>stage rows / model ledger preview: {String(liveBootstrapStageRows.length)} / {String(liveBootstrapModelLedgerRows.length)}</p>
          <p>session dedupe key present: {String(Boolean(readLiveBootstrapSessionKey()))}</p>
          <p>React 只在用户手动确认且 live_light opt-in 后调用 FastAPI POST；页面打开、搜索输入和 render 不直接创建 task，也不调用 Tushare、DeepSeek、GitHub、Python adapter 或真实交易接口。</p>
          <TaskLaunchReceipt receipt={liveBootstrapReceipt} />
          {liveBootstrapTaskId ? <TaskStatusPanel taskId={liveBootstrapTaskId} /> : null}
          {bootstrapEnvelopeWarnings.length || liveBootstrapWarnings.length ? <p className="risk-note">{String([...bootstrapEnvelopeWarnings, ...liveBootstrapWarnings][0])}</p> : null}
          <DataLineageTable rows={[...bootstrapEnvelopeLedger, ...liveBootstrapTaskLedger]} />
          {bootstrapProviderLinkageRows.length ? <DataLineageTable rows={bootstrapProviderLinkageRows} /> : null}
          {liveLightActivationRows.length ? <DataLineageTable rows={liveLightActivationRows} /> : null}
          {liveLightAcceptanceRows.length ? <DataLineageTable rows={liveLightAcceptanceRows} /> : null}
          {liveBootstrapStageRows.length ? <DataLineageTable rows={liveBootstrapStageRows} /> : null}
          {liveBootstrapModelLedgerRows.length ? <DataLineageTable rows={liveBootstrapModelLedgerRows} /> : null}
          <JsonDetails title="live_light activation receipt" data={liveLightActivationReceipt} />
          <JsonDetails title="live_light provider/model acceptance runbook" data={liveLightAcceptanceRunbook} />
          <JsonDetails title="bootstrap status" data={bootstrapStatus} />
        </PacketCard>
        <PacketCard title="Packet Registry" subtitle="现有 packet contract 只读映射" status={snapshotAvailable ? "snapshot" : "cache"}>
          <p>本地快照路径：{String(packets.snapshot_cache_path ?? "--")}</p>
          <p>alias keys: {String((packets.snapshot_alias_keys as unknown[] | undefined)?.length ?? 0)}</p>
          <p>SQLite meta: {String(Boolean(sqliteMeta?.sqlite_meta_available))}</p>
          <JsonDetails title="packet index 明细" data={packets} />
        </PacketCard>
        <PacketCard title="Command Center 3.0 迁移基线" subtitle="用户给定长期进度表；只读展示，不重新估算" status={String(migration.status ?? "baseline")}>
          <p>progress items: {String(migrationProgress?.length ?? 0)}</p>
          <p>long-term goals: {String(migrationLongTermSummary?.strict_closeout ?? "0/14")} closed, {String(migrationLongTermGoals?.length ?? 0)} tracked</p>
          <p>foundation / production acceptance: {String(migrationLongTermSummary?.foundation_progress_estimate ?? "--")} / {String(migrationLongTermSummary?.production_acceptance_estimate ?? "--")}</p>
          <p>Tushare / DeepSeek linkage: {String(migrationTushareDeepseekLinkage?.status ?? "pending")}</p>
          <p>linkage layers / blockers: {String(migrationTushareDeepseekLinkageRows?.length ?? 0)} / {String(migrationTushareDeepseekLinkage?.blocking_row_count ?? 0)}</p>
          <p>cache only: {String(migrationPolicy?.cache_only ?? true)}</p>
          <p>external calls: {String(migrationPolicy?.external_calls_triggered ?? false)}</p>
          <JsonDetails title="迁移进度基线" data={migrationProgress ?? []} />
          <JsonDetails title="14 个长期目标" data={migrationLongTermGoals ?? []} />
        </PacketCard>
        <PacketCard title="调用审计 cache" subtitle="GET cache，聚合本地 call_ledger，不触发外部请求" status={String(audit.status ?? "cache")}>
          <p>endpoint / task: {String(auditCounts?.cache_endpoint_count ?? 0)} / {String(auditCounts?.task_count ?? 0)}</p>
          <p>call ledger: {String(auditCounts?.call_ledger_count ?? 0)}</p>
          <p>external calls: {String(audit.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="3.0 envelope 血缘总览" subtitle="首页优先读取 FastAPI 顶层 call_ledger；不钻 payload 也能判断只读边界" status="lineage">
          <p>health / packet / market / discipline / factor / next / serenity / chokepoint / catalog / task index: {String(healthEnvelopeLedger.length)} / {String(packetEnvelopeLedger.length)} / {String(marketEnvelopeLedger.length)} / {String(disciplineEnvelopeLedger.length)} / {String(factorEnvelopeLedger.length)} / {String(nextEnvelopeLedger.length)} / {String(serenityEnvelopeLedger.length)} / {String(chokepointEnvelopeLedger.length)} / {String(taskCatalogEnvelopeLedger.length)} / {String(taskIndexEnvelopeLedger.length)}</p>
          <p>health warnings: {String(healthWarnings.length)}</p>
          <p>fallback payload ledger: {String(packetPayloadLedger.length + marketPayloadLedger.length + disciplinePayloadLedger.length + factorPayloadLedger.length + nextPayloadLedger.length + serenityPayloadLedger.length + chokepointPayloadLedger.length + taskCatalogPayloadLedger.length + taskIndexPayloadLedger.length)}</p>
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
          <p>envelope ledger / warnings: {String(marketEnvelopeLedger.length)} / {String(marketEnvelopeWarnings.length)}</p>
          <p>external calls: {String(market.external_calls_triggered ?? false)}</p>
        </PacketCard>
        <PacketCard title="交易纪律 cache" subtitle="GET cache，只读纪律闭环，不运行回测" status={String(discipline.status ?? "cache")}>
          <p>discipline score: {String(disciplinePacket?.score ?? "--")}</p>
          <p>loop ready / blocked: {String(disciplineCounts?.loop_ready_count ?? 0)} / {String(disciplineCounts?.loop_blocked_count ?? 0)}</p>
          <p>refresh steps: {String(disciplineCounts?.refresh_step_count ?? 0)}</p>
          <p>envelope ledger / warnings: {String(disciplineEnvelopeLedger.length)} / {String(disciplineEnvelopeWarnings.length)}</p>
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
          <p>factor chart external calls: {String(factorScoreChartContract?.external_calls_triggered ?? false)}</p>
          <p>factor chart Tushare / DeepSeek / GitHub: {String(factorScoreChartContract?.tushare_called ?? false)} / {String(factorScoreChartContract?.deepseek_called ?? false)} / {String(factorScoreChartContract?.github_called ?? false)}</p>
          <p>factor chart real trade: {String((factorScoreChartContract?.does_not_execute_trades ?? true) === false ? "possible" : "blocked")}</p>
          <p>frontend computes trade action: {String(factorScoreChartContract?.frontend_computes_trade_action ?? false)}</p>
          <p>envelope ledger / warnings: {String(factorEnvelopeLedger.length)} / {String(factorEnvelopeWarnings.length)}</p>
          <p>core action: {String((factor.governance as Record<string, unknown> | undefined)?.allow_core_action ?? false)}</p>
        </PacketCard>
        <PacketCard title="Serenity 方法雷达 cache" subtitle="本地方法来源基线" status={String(serenity.github_status ?? "local")}>
          <p>DeepSeek: 不调用</p>
          <p>repositories: {String((serenity.repositories as unknown[] | undefined)?.length ?? 0)}</p>
          <p>envelope ledger / warnings: {String(serenityEnvelopeLedger.length)} / {String(serenityEnvelopeWarnings.length)}</p>
        </PacketCard>
        <PacketCard title="DeepSeek 模型策略" subtitle="独立 cache；不展示 token/key，不触发模型调用" status={modelStrategy.contains_secret === true ? "check" : "safe"}>
          <p>purpose count: {String(deepseekModelCounts?.purpose_count ?? 0)}</p>
          <p>explain grade: {JSON.stringify(deepseekPurposeGroups.explain_grade ?? [])}</p>
          <p>fast grade: {JSON.stringify(deepseekPurposeGroups.fast_grade ?? [])}</p>
          <p>projection: {String(deepseekModelByPurpose.get("projection")?.model ?? "--")}</p>
          <p>factor_explain: {String(deepseekModelByPurpose.get("factor_explain")?.model ?? "--")}</p>
          <p>healthcheck / feeder: {String(deepseekModelByPurpose.get("healthcheck")?.model ?? "--")} / {String(deepseekModelByPurpose.get("feeder")?.model ?? "--")}</p>
          <p>external calls: {String(modelStrategy.external_calls_triggered ?? false)}</p>
          <DataLineageTable rows={deepseekHomeRows} />
        </PacketCard>
        <PacketCard title="产业链瓶颈扫描 cache" subtitle="GET cache 不触发 DeepSeek" status={String(chokepoint.status ?? "cache")}>
          <p>{String(chokepoint.summary ?? "等待缓存")}</p>
          <p>envelope ledger / warnings: {String(chokepointEnvelopeLedger.length)} / {String(chokepointEnvelopeWarnings.length)}</p>
        </PacketCard>
        <PacketCard title="Parquet / DuckDB Storage" subtitle="daily / daily_basic / moneyflow / trade_cal / factor_values / backtest_results 只读状态，不触发刷新" status={String(storageOverview.store ?? "parquet_duckdb")}>
          <p>datasets: {String(storageDatasets?.length ?? 0)}</p>
          <p>dataset catalog: {String(storageCatalogRows?.length ?? storageOverview.dataset_count ?? 0)}</p>
          <p>catalog envelope ledger / warnings: {String(storageCatalogLedger.length)} / {String(storageCatalogWarnings.length)}</p>
          <p>factor_values: {String(storageStatus?.factor_values ?? "missing")}</p>
          <p>daily: {String(storageStatus?.daily ?? "missing")}</p>
          <p>daily_basic: {String(storageStatus?.daily_basic ?? "missing")}</p>
          <p>moneyflow: {String(storageStatus?.moneyflow ?? "missing")}</p>
          <p>trade_cal: {String(storageStatus?.trade_cal ?? "missing")}</p>
          <p>backtest_results: {String(storageStatus?.backtest_results ?? "missing")}</p>
          <DataLineageTable rows={storageCatalogRows ?? []} />
          <DataLineageTable rows={storageCatalogLedger} />
          <JsonDetails title="storage overview" data={storageOverview} />
          <JsonDetails title="storage catalog" data={storageCatalog} />
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
          <p>implementation status: {String(taskImplementationStatus?.status ?? "partial_migration")}</p>
          <p>stub / local pipeline / guarded: {String(taskImplementationStatus?.stub_task_count ?? 0)} / {String(taskImplementationStatus?.local_pipeline_task_count ?? 0)} / {String(taskImplementationStatus?.guarded_local_task_count ?? 0)}</p>
          <p>implemented local task count: {String(taskImplementationStatus?.implemented_local_task_count ?? 0)}</p>
          <p>stub tasks must not be reported as complete: {String(taskCatalogPolicy?.stub_tasks_must_not_be_reported_as_complete ?? true)}</p>
          <p>known POST routes: {String(taskRouteCoverage?.known_post_route_count ?? 0)}</p>
          <p>uncovered POST routes: {String(taskUncoveredPostRoutes?.length ?? 0)}</p>
          <p>all known POST button gated: {String(taskRouteCoverage?.all_known_post_routes_button_gated ?? true)}</p>
          <p>call ledger required for POST: {String(taskRouteCoverage?.call_ledger_required_for_all_known_post_routes ?? true)}</p>
          <p>all button gated: {String(taskCatalogPolicy?.all_tasks_button_gated ?? true)}</p>
          <p>call ledger required: {String(taskCatalogPolicy?.call_ledger_required_for_all ?? true)}</p>
          <JsonDetails title="任务目录明细" data={taskCatalogItems ?? []} />
          <JsonDetails title="POST 路由覆盖" data={taskRouteCoverage ?? {}} />
          <JsonDetails title="任务实现状态" data={taskImplementationStatus ?? {}} />
        </PacketCard>
        <PacketCard title="Worker runtime cache" subtitle="GET cache，只读 worker scaffold，不连接 Redis" status={String(workerRuntime.status ?? "cache")}>
          <p>modules ready: {String(workerCounts?.worker_module_ready_count ?? 0)} / {String(workerCounts?.worker_module_count ?? 0)}</p>
          <p>local fallback: {String(workerRuntimeState?.local_fallback_enabled ?? true)}</p>
          <p>redis pinged: {String(workerRuntime.redis_pinged ?? false)}</p>
        </PacketCard>
      </div>
      </details>
    </>
  );
}
